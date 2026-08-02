"""Internal costing workbook (Phase 4; dynamic rebuild) — the confidential
cost→sell build-up as a *live* Excel model, modelled on the owner's
Jaipur_Dynamic_Costing_Workbook_Revised.

Unlike the first version (a static dump of the engine's numbers), this workbook is
formula-driven: the yellow input cells (pax, markup %, GST %, FX rate, per-group
cost build-up) are editable and every total recomputes in Excel. Seeded from the
quote's frozen `pricing_snapshot`, it reproduces the engine's totals to the rupee
when left untouched, then becomes a what-if tool.

Sheets:
  * Inputs            — assumptions: GST %, FX, per-group pax + markup % (editable).
  * Cost build-up     — per-group accommodation/shared/direct → base → sell → totals
                        (all via formulae referencing Inputs). Reproduces the quote.
  * Rates applied     — every rate/amount captured in the builder (stays, other
                        costs, markup rules, tax) with hotel + meal-plan detail.
  * Hotels & meal plans — the stays: hotel, city, meal plan, occupancy, nights,
                        room rate (editable) and cost/pax formula.

D-0001: the engine still owns the authoritative issued numbers; this is a tool.
Never send it to a client — it shows margin.
"""

from __future__ import annotations

import uuid
from io import BytesIO
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Destination,
    Itinerary,
    ItineraryComponent,
    ItineraryDay,
    Project,
    Quote,
    Rate,
    Supplier,
)

INR_FMT = "#,##0.00"
PCT_FMT = "0.00%"
_INK = "14211F"
_BAND = "14211F"
_ACCENT = "0E7C6B"
_SOFT = "EDF2F0"
_INPUT = "FFF6CC"  # yellow — "edit these cells"

_HEAD_FONT = Font(bold=True, color="FFFFFF", size=10)
_HEAD_FILL = PatternFill("solid", fgColor=_ACCENT)
_TITLE_FONT = Font(bold=True, color="FFFFFF", size=14)
_TITLE_FILL = PatternFill("solid", fgColor=_BAND)
_LABEL_FONT = Font(bold=True, color=_INK)
_TOTAL_FONT = Font(bold=True, color=_INK, size=11)
_TOTAL_FILL = PatternFill("solid", fgColor=_SOFT)
_MUTED_FONT = Font(color="5B6B65", size=9, italic=True)
_INPUT_FILL = PatternFill("solid", fgColor=_INPUT)

# occupancy name (as stored in the snapshot, upper-cased pm.Occupancy) -> room divisor
_DIVISOR = {"SINGLE": 1, "DOUBLE": 2, "TRIPLE": 3}


def _f(value: Any) -> float:
    return float(value) if value not in (None, "") else 0.0


def _title(ws: Worksheet, text: str, span: str) -> None:
    ws.sheet_view.showGridLines = False
    ws.merge_cells(span)
    first = span.split(":")[0]
    c = ws[first]
    c.value = text
    c.font = _TITLE_FONT
    c.fill = _TITLE_FILL
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 24


def _headers(ws: Worksheet, row: int, headers: list[str], *, right_from: int = 99) -> None:
    for c, h in enumerate(headers, start=1):
        cell = ws.cell(row=row, column=c, value=h)
        cell.font = _HEAD_FONT
        cell.fill = _HEAD_FILL
        cell.alignment = Alignment(horizontal="right" if c >= right_from else "left")


def _input_cell(ws: Worksheet, row: int, col: int, value: Any, fmt: str | None = INR_FMT) -> str:
    cell = ws.cell(row=row, column=col, value=_f(value))
    if fmt:
        cell.number_format = fmt
    cell.fill = _INPUT_FILL
    return f"{get_column_letter(col)}{row}"


# --------------------------------------------------------------------------- #
# Inputs sheet
# --------------------------------------------------------------------------- #

def _inputs_sheet(
    ws: Worksheet, segments: list[dict[str, Any]], markup_by_seg: dict[str, float],
    gst_rate: float, fx: dict[str, Any] | None,
) -> dict[str, Any]:
    """Editable assumptions. Returns the cell addresses other sheets reference."""
    ws.title = "Inputs"
    _title(ws, "Inputs — edit the yellow cells; everything recalculates", "A1:D1")
    ws.cell(row=2, column=1,
            value="Pax, markup %, GST % and FX drive the Cost build-up sheet.").font = _MUTED_FONT

    gst_addr = f"Inputs!${'B'}$4"
    ws.cell(row=4, column=1, value="GST %").font = _LABEL_FONT
    _input_cell(ws, 4, 2, gst_rate, PCT_FMT)
    ws.cell(row=5, column=1, value="FX currency").font = _LABEL_FONT
    cur = (fx or {}).get("currency") or "USD"
    fc = ws.cell(row=5, column=2, value=cur)
    fc.fill = _INPUT_FILL
    ws.cell(row=6, column=1, value="FX rate (₹ per unit)").font = _LABEL_FONT
    fx_addr = "Inputs!$B$6"
    _input_cell(ws, 6, 2, _f((fx or {}).get("inr_per_unit")) or 0.0, INR_FMT)

    header_row = 8
    ws.cell(row=header_row, column=1, value="Traveller group").font = _LABEL_FONT
    _headers(ws, header_row, ["Traveller group", "Pax", "Markup %"], right_from=2)

    seg_rows: dict[str, dict[str, str]] = {}
    r = header_row + 1
    for seg in segments:
        ws.cell(row=r, column=1, value=seg["label"])
        pax_addr = _input_cell(ws, r, 2, seg["pax"], "0")
        mk_addr = _input_cell(ws, r, 3, markup_by_seg.get(seg["id"], 0.0), PCT_FMT)
        seg_rows[seg["id"]] = {"pax": f"Inputs!${'B'}${r}", "markup": f"Inputs!${'C'}${r}",
                               "pax_local": pax_addr, "markup_local": mk_addr}
        r += 1
    ws.cell(row=r, column=1, value="Total pax").font = _TOTAL_FONT
    if segments:
        tot = ws.cell(row=r, column=2, value=f"=SUM(B9:B{r - 1})")
        tot.font = _TOTAL_FONT

    for i, w in enumerate([26, 12, 12], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    return {"gst": gst_addr, "fx": fx_addr, "currency": cur, "segments": seg_rows}


# --------------------------------------------------------------------------- #
# Cost build-up sheet (the dynamic summary)
# --------------------------------------------------------------------------- #

def _buildup_sheet(
    ws: Worksheet, quote: Quote, project: Project | None, itinerary: Itinerary | None,
    segments: list[dict[str, Any]], out_by_seg: dict[str, dict[str, Any]],
    refs: dict[str, Any], out: dict[str, Any],
) -> None:
    _title(ws, "INTERNAL COST BUILD-UP — CONFIDENTIAL (do not send to client)", "A1:I1")

    meta = [
        ("Project", project.code if project else "—"),
        ("Client", project.client_name if project else "—"),
        ("Itinerary", itinerary.title if itinerary else "—"),
        ("Quote", f"v{quote.version} ({quote.status})"),
        ("GST", f"{quote.gst_treatment.value} @ {quote.gst_rate}%"),
        ("Engine", quote.engine_version or "—"),
    ]
    row = 3
    for k, v in meta:
        ws.cell(row=row, column=1, value=k).font = _LABEL_FONT
        ws.cell(row=row, column=2, value=str(v))
        row += 1

    row += 1
    ws.cell(row=row, column=1,
            value="Per-group build-up (yellow = editable; grey = formula)").font = _LABEL_FONT
    row += 1
    header = ["Group", "Pax", "Accom/pax", "Shared/pax", "Direct/pax",
              "Base cost/pax", "Markup %", "Sell/pax", "Group total"]
    _headers(ws, row, header, right_from=2)
    row += 1

    first_data = row
    for seg in segments:
        sid = seg["id"]
        oseg = out_by_seg.get(sid, {})
        sref = refs["segments"].get(sid, {})
        ws.cell(row=row, column=1, value=seg["label"])
        # Pax + markup pull from Inputs so editing there flows here.
        ws.cell(row=row, column=2, value=f"={sref.get('pax', seg['pax'])}").number_format = "0"
        _input_cell(ws, row, 3, oseg.get("accommodation"))
        _input_cell(ws, row, 4, oseg.get("shared"))
        _input_cell(ws, row, 5, oseg.get("direct"))
        base = ws.cell(row=row, column=6, value=f"=C{row}+D{row}+E{row}")
        base.number_format = INR_FMT
        ws.cell(row=row, column=7, value=f"={sref.get('markup', 0)}").number_format = PCT_FMT
        sell = ws.cell(row=row, column=8,
                       value=f"=ROUND(F{row}*(1+G{row})*(1+{refs['gst']}),0)")
        sell.number_format = INR_FMT
        gt = ws.cell(row=row, column=9, value=f"=H{row}*B{row}")
        gt.number_format = INR_FMT
        row += 1
    last_data = row - 1

    row += 1
    # Total cost
    ws.cell(row=row, column=1, value="Total cost").font = _TOTAL_FONT
    cost_f = f"=SUMPRODUCT(F{first_data}:F{last_data},B{first_data}:B{last_data})"
    tc = ws.cell(row=row, column=2, value=cost_f)
    tc.number_format = INR_FMT
    tc.font = _TOTAL_FONT
    tc_addr = f"B{row}"
    row += 1
    ws.cell(row=row, column=1, value="Package (gross)").font = _TOTAL_FONT
    pk = ws.cell(row=row, column=2, value=f"=SUM(I{first_data}:I{last_data})")
    pk.number_format = INR_FMT
    pk.font = _TOTAL_FONT
    pk_addr = f"B{row}"
    row += 1
    ws.cell(row=row, column=1, value="Profit").font = _TOTAL_FONT
    pf = ws.cell(row=row, column=2, value=f"={pk_addr}-{tc_addr}")
    pf.number_format = INR_FMT
    pf.font = _TOTAL_FONT
    pf_addr = f"B{row}"
    row += 1
    ws.cell(row=row, column=1, value="Margin on gross").font = _TOTAL_FONT
    mg = ws.cell(row=row, column=2, value=f"=IFERROR({pf_addr}/{pk_addr},0)")
    mg.number_format = PCT_FMT
    mg.font = Font(bold=True, color=_ACCENT, size=11)
    row += 1
    ws.cell(row=row, column=1, value=f"{refs['currency']} equivalent").font = _TOTAL_FONT
    fxv = ws.cell(row=row, column=2, value=f"=IFERROR({pk_addr}/{refs['fx']},0)")
    fxv.number_format = INR_FMT
    fxv.font = _TOTAL_FONT
    row += 2

    # The engine's authoritative figures, for cross-checking the live model.
    engine_cell = ws.cell(row=row, column=1, value="Engine (authoritative, from the frozen quote)")
    engine_cell.font = _LABEL_FONT
    row += 1
    for label, key, fmt in [
        ("True margin (ex-tax)", "margin_pct", PCT_FMT),
        ("Total cost", "total_cost", INR_FMT),
        ("Package (gross)", "group_total", INR_FMT),
        ("Profit", "profit", INR_FMT),
    ]:
        ws.cell(row=row, column=1, value=label).font = _MUTED_FONT
        # margin_pct is stored as a fraction (0.1252) — the % format renders 12.52%.
        cell = ws.cell(row=row, column=2, value=_f(out.get(key)))
        cell.number_format = fmt
        cell.font = _MUTED_FONT
        row += 1

    for i, w in enumerate([22, 10, 12, 12, 12, 13, 10, 12, 14], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


# --------------------------------------------------------------------------- #
# Rates applied sheet (every input captured on the UI)
# --------------------------------------------------------------------------- #

def _label_for_segments(ids: list[str], seg_label: dict[str, str]) -> str:
    return ", ".join(seg_label.get(i, i) for i in ids) or "all"


def _rates_sheet(
    ws: Worksheet, inp: dict[str, Any], meta: dict[str, dict[str, Any]],
    seg_label: dict[str, str],
) -> None:
    _title(ws, "Rates applied — everything captured in the builder", "A1:G1")
    row = 3
    ws.cell(row=row, column=1, value="Stays (accommodation)").font = _LABEL_FONT
    row += 1
    _headers(ws, row, ["Hotel", "City", "Meal plan", "Occupancy", "Nights",
                       "Room rate ₹", "Present groups"], right_from=5)
    row += 1
    for st in inp.get("stays", []):
        m = meta.get(st["id"], {})
        hotel = m.get("supplier") or st.get("label") or "stay"
        present = _label_for_segments(st.get("present", []), seg_label)
        for occ, rate in (st.get("room_rate") or {}).items():
            ws.cell(row=row, column=1, value=hotel)
            ws.cell(row=row, column=2, value=m.get("city") or "—")
            ws.cell(row=row, column=3, value=m.get("meal_plan") or "—")
            ws.cell(row=row, column=4, value=occ.lower())
            nc = ws.cell(row=row, column=5, value=int(st.get("nights") or 0))
            nc.alignment = Alignment(horizontal="right")
            rc = ws.cell(row=row, column=6, value=_f(rate))
            rc.number_format = INR_FMT
            ws.cell(row=row, column=7, value=present)
            row += 1

    row += 1
    ws.cell(row=row, column=1, value="Other costs").font = _LABEL_FONT
    row += 1
    _headers(ws, row, ["Item", "Kind", "Supplier", "Amount ₹", "Applies to"], right_from=4)
    row += 1
    for c in inp.get("components", []):
        m = meta.get(c["id"], {})
        ws.cell(row=row, column=1, value=c.get("label"))
        ws.cell(row=row, column=2, value=c.get("kind"))
        ws.cell(row=row, column=3, value=m.get("supplier") or "—")
        ac = ws.cell(row=row, column=4, value=_f(c.get("amount")))
        ac.number_format = INR_FMT
        ws.cell(row=row, column=5, value=_label_for_segments(c.get("applies_to", []), seg_label))
        row += 1

    row += 1
    ws.cell(row=row, column=1, value="Markup rules").font = _LABEL_FONT
    row += 1
    _headers(ws, row, ["Group", "Markup basis", "Rate %"], right_from=3)
    row += 1
    rules = inp.get("markup_rules", {})
    for seg in inp.get("segments", []):
        rid = seg.get("markup_rule_id")
        rule = rules.get(str(rid), {}) if rid else {}
        ws.cell(row=row, column=1, value=seg["label"])
        ws.cell(row=row, column=2, value=rule.get("basis") or "—")
        mc = ws.cell(row=row, column=3, value=_f(rule.get("rate")))
        mc.number_format = PCT_FMT
        row += 1

    row += 1
    ws.cell(row=row, column=1, value="Tax").font = _LABEL_FONT
    row += 1
    tax = inp.get("tax_rule", {})
    ws.cell(row=row, column=1, value="GST rate")
    gc = ws.cell(row=row, column=2, value=_f(tax.get("rate")))
    gc.number_format = PCT_FMT
    row += 1
    ws.cell(row=row, column=1, value="Treatment")
    ws.cell(row=row, column=2, value=tax.get("treatment") or "—")

    for i, w in enumerate([26, 14, 16, 12, 22], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


# --------------------------------------------------------------------------- #
# Hotels & meal plans sheet
# --------------------------------------------------------------------------- #

def _hotels_sheet(
    ws: Worksheet, inp: dict[str, Any], meta: dict[str, dict[str, Any]],
) -> None:
    _title(ws, "Hotels & meal plans — edit a room rate to reprice the stay", "A1:H1")
    row = 3
    _headers(ws, row, ["Hotel", "City", "Meal plan", "Occupancy", "Nights",
                       "Room rate ₹", "Divisor", "Cost / pax"], right_from=5)
    row += 1
    any_stay = False
    for st in inp.get("stays", []):
        m = meta.get(st["id"], {})
        hotel = m.get("supplier") or st.get("label") or "stay"
        for occ, rate in (st.get("room_rate") or {}).items():
            any_stay = True
            ws.cell(row=row, column=1, value=hotel)
            ws.cell(row=row, column=2, value=m.get("city") or "—")
            ws.cell(row=row, column=3, value=m.get("meal_plan") or "—")
            ws.cell(row=row, column=4, value=occ.lower())
            nights = int(st.get("nights") or 0)
            nc = ws.cell(row=row, column=5, value=nights)
            nc.alignment = Alignment(horizontal="right")
            _input_cell(ws, row, 6, rate)  # editable room rate (yellow)
            dc = ws.cell(row=row, column=7, value=_DIVISOR.get(occ.upper(), 1))
            dc.alignment = Alignment(horizontal="right")
            cp = ws.cell(row=row, column=8, value=f"=F{row}*E{row}/G{row}")
            cp.number_format = INR_FMT
            row += 1
    if not any_stay:
        ws.cell(row=row, column=1, value="No stays on this itinerary.").font = _MUTED_FONT

    for i, w in enumerate([26, 14, 12, 12, 8, 12, 8, 12], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


# --------------------------------------------------------------------------- #
# Assembly
# --------------------------------------------------------------------------- #

def component_meta(session: Session, itinerary_id: uuid.UUID) -> dict[str, dict[str, Any]]:
    """Resolve each itinerary component's hotel / meal plan / city for the
    descriptive sheets, keyed by component id (matching the snapshot's ids)."""
    meta: dict[str, dict[str, Any]] = {}
    days = list(session.scalars(
        select(ItineraryDay).where(ItineraryDay.itinerary_id == itinerary_id)
    ))
    for day in days:
        city = None
        if day.destination_id is not None:
            dest = session.get(Destination, day.destination_id)
            city = dest.name if dest else None
        for comp in session.scalars(
            select(ItineraryComponent).where(ItineraryComponent.itinerary_day_id == day.id)
        ):
            supplier = session.get(Supplier, comp.supplier_id) if comp.supplier_id else None
            rate = session.get(Rate, comp.rate_id) if comp.rate_id else None
            meta[str(comp.id)] = {
                "supplier": supplier.display_name if supplier else None,
                "meal_plan": rate.meal_plan.value if rate else None,
                "occupancy": rate.occupancy.value if rate else None,
                "city": city,
            }
    return meta


def render_costing_xlsx(
    quote: Quote,
    project: Project | None,
    itinerary: Itinerary | None,
    meta: dict[str, dict[str, Any]] | None = None,
) -> bytes:
    snap = quote.pricing_snapshot or {}
    inp = snap.get("inputs", {})
    out = snap.get("output", {})
    meta = meta or {}

    segments = inp.get("segments", [])
    seg_label = {s["id"]: s["label"] for s in segments}
    out_by_seg = {s["segment_id"]: s for s in out.get("segments", [])}
    rules = inp.get("markup_rules", {})
    markup_by_seg = {
        s["id"]: _f(rules.get(str(s.get("markup_rule_id")), {}).get("rate"))
        for s in segments
    }
    gst_rate = _f(inp.get("tax_rule", {}).get("rate"))
    fx = inp.get("fx")

    wb = Workbook()
    refs = _inputs_sheet(wb.active, segments, markup_by_seg, gst_rate, fx)
    _buildup_sheet(wb.create_sheet("Cost build-up"), quote, project, itinerary,
                   segments, out_by_seg, refs, out)
    _rates_sheet(wb.create_sheet("Rates applied"), inp, meta, seg_label)
    _hotels_sheet(wb.create_sheet("Hotels & meal plans"), inp, meta)

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
