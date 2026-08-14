"""Bulk import of vendors + rates from an Excel template (owner batch).

Design (matches the owner's governance): the template has two data sheets — Vendors
(all seven kinds) and Rates (the standard amount + validity window, plus meal plan /
occupancy for stay & meal). An import runs in two phases the caller drives:

  • dry-run  — parse + validate every row, report what WOULD happen, persist nothing;
  • commit   — do the same, then upsert.

Imported vendors land as `prospect` (unverified — D-0009) and rates as `on_file`
with the chosen `rate_source`, so nothing is auto-trusted; a human still promotes /
verifies in the vendor book. Vendors dedupe by (kind, display_name, city); an unknown
city is created inline. Bad rows never abort the batch — each is isolated in a
savepoint and reported.

`build_template()` emits the .xlsx; `run_import()` does the parse→validate→(commit).
Row validation is pure (`validate_vendor_row` / `validate_rate_row`) so it is tested
without a DB or Excel.
"""

from __future__ import annotations

import io
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Destination, Supplier
from app.models.enums import MealPlan, Occupancy, PriceStatus, RateSource, SupplierKind
from app.models.rate import Rate

VENDOR_SHEET = "Vendors"
RATE_SHEET = "Rates"

VENDOR_COLUMNS = [
    "kind", "display_name", "legal_name", "city", "category",
    "property_type", "status", "gstin", "pan", "notes",
]
RATE_COLUMNS = [
    "vendor_display_name", "city", "meal_plan", "occupancy", "amount",
    "currency", "valid_from", "valid_to", "season_label", "min_nights", "rate_source",
]

_KINDS = {k.value for k in SupplierKind}
_STATUSES = {"prospect", "active", "contacted", "blacklisted"}
_MEAL_PLANS = {m.value for m in MealPlan}

# Room occupancies offered in the template — the friendly stay vocabulary, NOT the
# full Occupancy enum (which also has child_nb/child_wb child-pricing values that
# don't belong on a room-rate import). The label shown maps to the DB enum value.
TEMPLATE_OCCUPANCIES = ["single", "double", "triple", "extra bed", "twin bed"]
_OCCUPANCY_ALIASES: dict[str, str] = {
    "single": Occupancy.SINGLE.value,
    "double": Occupancy.DOUBLE.value,
    "triple": Occupancy.TRIPLE.value,
    "extra bed": Occupancy.EXTRA_ADULT.value,
    "extra": Occupancy.EXTRA_ADULT.value,
    "extra_adult": Occupancy.EXTRA_ADULT.value,
    "twin bed": Occupancy.TWIN.value,
    "twin": Occupancy.TWIN.value,
}
_RATE_SOURCES = {r.value for r in RateSource}


@dataclass
class RowError:
    sheet: str
    row: int  # 1-based row number as seen in Excel (incl. the header row)
    message: str


@dataclass
class ImportResult:
    committed: bool
    vendors_created: int = 0
    vendors_matched: int = 0
    rates_created: int = 0
    skipped: int = 0
    errors: list[RowError] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        d = asdict(self)
        d["error_count"] = len(self.errors)
        d["ok"] = not self.errors
        return d


# ------------------------------ pure validation ------------------------------ #

def _s(value: object) -> str:
    """Trim a cell to a clean string ('' for blanks/None)."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _coerce_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _s(value)
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"bad date {text!r} (use YYYY-MM-DD)")


@dataclass
class VendorRow:
    kind: str
    display_name: str
    legal_name: str
    city: str
    category: str | None
    property_type: str | None
    status: str
    gstin: str | None
    pan: str | None
    notes: str | None


def validate_vendor_row(row: dict[str, object]) -> tuple[VendorRow | None, str | None]:
    """Pure: normalize + validate one Vendors row. Returns (clean, None) or (None, err)."""
    kind = _s(row.get("kind")).lower()
    display = _s(row.get("display_name"))
    if not kind and not display:
        return None, ""  # blank row — silently ignored (empty message)
    if kind not in _KINDS:
        return None, f"kind {kind!r} must be one of {sorted(_KINDS)}"
    if not display:
        return None, "display_name is required"
    status = _s(row.get("status")).lower() or "prospect"
    if status not in _STATUSES:
        return None, f"status {status!r} must be one of {sorted(_STATUSES)}"
    return (
        VendorRow(
            kind=kind,
            display_name=display,
            legal_name=_s(row.get("legal_name")) or display,
            city=_s(row.get("city")),
            category=_s(row.get("category")) or None,
            property_type=_s(row.get("property_type")) or None,
            status=status,
            gstin=_s(row.get("gstin")) or None,
            pan=_s(row.get("pan")) or None,
            notes=_s(row.get("notes")) or None,
        ),
        None,
    )


@dataclass
class RateRow:
    vendor_display_name: str
    city: str
    meal_plan: str
    occupancy: str
    amount: Decimal
    currency: str
    valid_from: date
    valid_to: date
    season_label: str | None
    min_nights: int
    rate_source: str


def validate_rate_row(row: dict[str, object]) -> tuple[RateRow | None, str | None]:
    """Pure: normalize + validate one Rates row. Returns (clean, None) or (None, err)."""
    vendor = _s(row.get("vendor_display_name"))
    amount_raw = _s(row.get("amount"))
    if not vendor and not amount_raw:
        return None, ""  # blank row
    if not vendor:
        return None, "vendor_display_name is required"
    try:
        amount = Decimal(amount_raw)
    except (InvalidOperation, ValueError):
        return None, f"amount {amount_raw!r} is not a number"
    if amount < 0:
        return None, "amount must be >= 0"
    meal_plan = (_s(row.get("meal_plan")) or "EP").upper()
    if meal_plan not in _MEAL_PLANS:
        return None, f"meal_plan {meal_plan!r} must be one of {sorted(_MEAL_PLANS)}"
    occ_raw = (_s(row.get("occupancy")) or "double").lower()
    occupancy = _OCCUPANCY_ALIASES.get(occ_raw)
    if occupancy is None:
        return None, (
            f"occupancy {occ_raw!r} must be one of: " + ", ".join(TEMPLATE_OCCUPANCIES)
        )
    source = (_s(row.get("rate_source")) or "b2b").lower()
    if source not in _RATE_SOURCES:
        return None, f"rate_source {source!r} must be one of {sorted(_RATE_SOURCES)}"
    try:
        vfrom = _coerce_date(row.get("valid_from"))
        vto = _coerce_date(row.get("valid_to"))
    except ValueError as exc:
        return None, str(exc)
    if vfrom is None or vto is None:
        return None, "valid_from and valid_to are required (YYYY-MM-DD)"
    if vto < vfrom:
        return None, "valid_to must be on/after valid_from"
    min_nights_raw = _s(row.get("min_nights"))
    try:
        min_nights = int(min_nights_raw) if min_nights_raw else 1
    except ValueError:
        return None, f"min_nights {min_nights_raw!r} is not a whole number"
    currency = (_s(row.get("currency")) or "INR").upper()
    if len(currency) != 3:
        return None, f"currency {currency!r} must be a 3-letter code"
    return (
        RateRow(
            vendor_display_name=vendor, city=_s(row.get("city")),
            meal_plan=meal_plan, occupancy=occupancy, amount=amount,
            currency=currency, valid_from=vfrom, valid_to=vto,
            season_label=_s(row.get("season_label")) or None,
            min_nights=min_nights, rate_source=source,
        ),
        None,
    )


# ------------------------------ template (.xlsx) ------------------------------ #

def build_template() -> bytes:
    """A ready-to-fill .xlsx: an Instructions sheet + empty Vendors & Rates sheets."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = Workbook()
    info = wb.active
    info.title = "Instructions"
    lines = [
        ["RootsVida — bulk vendor & rate import"],
        [""],
        ["Fill the 'Vendors' and 'Rates' sheets, then upload on the Vendors page."],
        ["Imported vendors are saved as 'prospect' (unverified) and rates as 'on_file'."],
        ["Nothing is auto-trusted — review/verify in the vendor book afterwards."],
        [""],
        ["Vendors sheet columns:"],
        ["  kind*", "one of: " + ", ".join(sorted(_KINDS))],
        ["  display_name*", "the vendor's name (required)"],
        ["  legal_name", "defaults to display_name if blank"],
        ["  city", "created automatically if new; used to dedupe + link rates"],
        ["  category", "e.g. Homestays, Hostels, 2 Star, 3 Star, 5 Star, 7 Star"],
        ["  property_type", "e.g. Hotel, Homestay, Resort, Camp"],
        ["  status", "one of: " + ", ".join(sorted(_STATUSES)) + " (default prospect)"],
        ["  gstin / pan / notes", "optional"],
        [""],
        ["Rates sheet columns:"],
        ["  vendor_display_name*", "must match a Vendors row (or an existing vendor)"],
        ["  city", "same city as the vendor (disambiguates duplicates)"],
        ["  amount*", "number, INR by default"],
        ["  valid_from* / valid_to*", "YYYY-MM-DD"],
        ["  meal_plan", "stay/meal only: " + ", ".join(sorted(_MEAL_PLANS)) + " (default EP)"],
        ["  occupancy", "stay only: " + ", ".join(TEMPLATE_OCCUPANCIES) + " (default double)"],
        ["  currency", "3-letter code (default INR)"],
        ["  min_nights", "whole number (default 1)"],
        ["  rate_source", "one of: " + ", ".join(sorted(_RATE_SOURCES)) + " (default b2b)"],
        ["  season_label", "optional"],
        ["", ""],
        ["* = required"],
    ]
    for r in lines:
        info.append(r)
    info["A1"].font = Font(bold=True, size=14, color="1F3864")
    info.column_dimensions["A"].width = 24
    info.column_dimensions["B"].width = 80
    for row in info.iter_rows(min_row=8):
        row[0].font = Font(bold=True)  # column names in the left column

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="1F3864")
    center = Alignment(horizontal="center")

    # Per-column widths + which columns get a dropdown of allowed values.
    vendor_widths = [12, 28, 26, 18, 14, 16, 12, 20, 14, 34]
    rate_widths = [28, 18, 12, 12, 12, 10, 14, 14, 18, 11, 12]
    vendor_lists = {"kind": sorted(_KINDS), "status": sorted(_STATUSES)}
    rate_lists = {
        "meal_plan": sorted(_MEAL_PLANS),
        "occupancy": TEMPLATE_OCCUPANCIES,
        "rate_source": sorted(_RATE_SOURCES),
    }

    def _style(name: str, columns: list[str], widths: list[int],
               dropdowns: dict[str, list[str]]) -> None:
        ws = wb.create_sheet(name)
        ws.append(columns)
        for i, cell in enumerate(ws[1]):
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center
            ws.column_dimensions[get_column_letter(i + 1)].width = widths[i]
        ws.freeze_panes = "A2"  # keep the header visible while scrolling
        ws.auto_filter.ref = f"A1:{get_column_letter(len(columns))}1"
        for col_name, allowed in dropdowns.items():
            letter = get_column_letter(columns.index(col_name) + 1)
            dv = DataValidation(
                type="list", formula1='"' + ",".join(allowed) + '"', allow_blank=True
            )
            ws.add_data_validation(dv)
            dv.add(f"{letter}2:{letter}1000")

    _style(VENDOR_SHEET, VENDOR_COLUMNS, vendor_widths, vendor_lists)
    _style(RATE_SHEET, RATE_COLUMNS, rate_widths, rate_lists)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# --------------------------------- import ------------------------------------ #

def _read_sheet(wb: Any, name: str, columns: list[str]) -> list[tuple[int, dict[str, object]]]:
    """Return [(excel_row_number, {col: value})] for a sheet, mapped by header names."""
    if name not in wb.sheetnames:
        return []
    ws = wb[name]
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    header = [(_s(h)).lower() for h in rows[0]]
    out: list[tuple[int, dict[str, object]]] = []
    for i, raw in enumerate(rows[1:], start=2):  # row 1 is the header
        record: dict[str, object] = {}
        for col in columns:
            idx = header.index(col) if col in header else -1
            record[col] = raw[idx] if 0 <= idx < len(raw) else None
        if any(_s(v) for v in record.values()):
            out.append((i, record))
    return out


def run_import(
    session: Session, org_id: uuid.UUID, data: bytes, *, commit: bool
) -> ImportResult:
    """Parse the workbook, validate every row, and (if commit) upsert vendors + rates.

    Dry-run and commit share one code path: work happens in the session; if not
    committing, the session is rolled back at the end so nothing persists."""
    from openpyxl import load_workbook

    result = ImportResult(committed=commit)
    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception:  # noqa: BLE001 — any unreadable file is a user error, not a crash
        result.errors.append(
            RowError(sheet="(file)", row=0, message="could not read the .xlsx file")
        )
        return result

    # City cache (lower name -> Destination) so repeated cities resolve/create once.
    city_cache: dict[str, Destination] = {}

    def resolve_city(name: str) -> Destination | None:
        if not name:
            return None
        key = name.lower()
        if key in city_cache:
            return city_cache[key]
        dest = session.scalars(
            select(Destination).where(
                Destination.org_id == org_id, func.lower(Destination.name) == key
            )
        ).first()
        if dest is None:
            dest = Destination(org_id=org_id, name=name, country="IN")
            session.add(dest)
            session.flush()
        city_cache[key] = dest
        return dest

    # (kind, lower(name), city_id or "") -> Supplier, for dedupe + rate linking.
    vendor_index: dict[tuple[str, str, str], Supplier] = {}

    def vendor_key(kind: str, name: str, city_id: uuid.UUID | None) -> tuple[str, str, str]:
        return kind, name.lower(), str(city_id or "")

    # --- Vendors ---
    for excel_row, raw in _read_sheet(wb, VENDOR_SHEET, VENDOR_COLUMNS):
        vrow, verr = validate_vendor_row(raw)
        if verr:
            result.errors.append(RowError(VENDOR_SHEET, excel_row, verr))
            continue
        if vrow is None:
            continue
        try:
            with session.begin_nested():
                dest = resolve_city(vrow.city)
                key = vendor_key(vrow.kind, vrow.display_name, dest.id if dest else None)
                existing = session.scalars(
                    select(Supplier).where(
                        Supplier.org_id == org_id,
                        Supplier.kind == SupplierKind(vrow.kind),
                        func.lower(Supplier.display_name) == vrow.display_name.lower(),
                        Supplier.destination_id == (dest.id if dest else None),
                        Supplier.deleted_at.is_(None),
                    )
                ).first()
                if existing is not None:
                    vendor_index[key] = existing
                    result.vendors_matched += 1
                else:
                    supplier = Supplier(
                        org_id=org_id, kind=SupplierKind(vrow.kind),
                        display_name=vrow.display_name, legal_name=vrow.legal_name,
                        destination_id=dest.id if dest else None,
                        category=vrow.category, property_type=vrow.property_type,
                        status=vrow.status, gstin=vrow.gstin, pan=vrow.pan,
                        notes=vrow.notes,
                    )
                    session.add(supplier)
                    session.flush()
                    vendor_index[key] = supplier
                    result.vendors_created += 1
        except IntegrityError:
            result.errors.append(
                RowError(VENDOR_SHEET, excel_row, "database rejected the row")
            )

    # --- Rates ---
    for excel_row, raw in _read_sheet(wb, RATE_SHEET, RATE_COLUMNS):
        rrow, rerr = validate_rate_row(raw)
        if rerr:
            result.errors.append(RowError(RATE_SHEET, excel_row, rerr))
            continue
        if rrow is None:
            continue
        dest = resolve_city(rrow.city) if rrow.city else None
        rvendor = _find_vendor_for_rate(
            vendor_index, session, org_id, rrow.vendor_display_name, dest,
        )
        if rvendor is None:
            result.errors.append(RowError(
                RATE_SHEET, excel_row,
                f"no vendor named {rrow.vendor_display_name!r}"
                + (f" in {rrow.city}" if rrow.city else "")
                + " (add it on the Vendors sheet)",
            ))
            continue
        try:
            with session.begin_nested():
                session.add(Rate(
                    org_id=org_id, supplier_id=rvendor.id,
                    meal_plan=MealPlan(rrow.meal_plan), occupancy=Occupancy(rrow.occupancy),
                    amount=rrow.amount, currency=rrow.currency,
                    valid_from=rrow.valid_from, valid_to=rrow.valid_to,
                    season_label=rrow.season_label, min_nights=rrow.min_nights,
                    price_status=PriceStatus.ON_FILE, rate_source=RateSource(rrow.rate_source),
                ))
                session.flush()
            result.rates_created += 1
        except IntegrityError:
            result.skipped += 1
            result.errors.append(RowError(
                RATE_SHEET, excel_row,
                "overlapping/duplicate rate for this vendor+plan+occupancy+dates — skipped",
            ))

    if commit:
        session.flush()
    else:
        session.rollback()  # dry-run: discard everything we tried
    return result


def _find_vendor_for_rate(
    vendor_index: dict[tuple[str, str, str], Supplier],
    session: Session,
    org_id: uuid.UUID,
    name: str,
    dest: Destination | None,
) -> Supplier | None:
    """Link a rate to a vendor: prefer one imported/matched in this file (any kind),
    else fall back to an existing vendor in the book by name (+ city if given)."""
    name_l = name.lower()
    city_id = str(dest.id) if dest else ""
    # Exact (name, city) among this file's vendors, across kinds.
    for (_kind, n, c), sup in vendor_index.items():
        if n == name_l and (c == city_id or not city_id):
            return sup
    stmt = select(Supplier).where(
        Supplier.org_id == org_id,
        func.lower(Supplier.display_name) == name_l,
        Supplier.deleted_at.is_(None),
    )
    if dest is not None:
        stmt = stmt.where(Supplier.destination_id == dest.id)
    return session.scalars(stmt).first()
