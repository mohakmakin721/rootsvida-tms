"""Registry of per-sheet ingestion specs.

Each source sheet resolves to a `SheetSpec` describing where to find it and how
its rows are laid out, plus the parser tier from the plan (§1.2):

  - MECHANICAL — shared header vocabulary, column-mapping config (Tier A).
  - ASSISTED   — LLM-assisted parsing of price strings (Tier B). DORMANT in
                 Phase 1: staging still captures the rows verbatim; no LLM runs.
  - BESPOKE    — a throwaway parser per sheet (Tier C).
  - MANUAL     — re-keyed by hand; staging just preserves the source (Tier C).

Only header positions that have actually been inspected are asserted here. Any
unregistered sheet falls back to `_DEFAULT` (mechanical, header on row 1); the
real per-sheet tuning happens when that sheet is migrated, not speculatively now.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import ParserStrategy

HOTELS_DB = "Hotels Database.xlsx"
VENDORS = "Vendors.xlsx"


@dataclass(frozen=True)
class SheetSpec:
    """How one source sheet is read into staging."""

    sheet_name: str
    parser_strategy: ParserStrategy
    workbook: str | None = None
    # 1-based index of the header row (the row holding column names).
    header_row: int = 1
    # 1-based index of the first data row. Defaults to the row after the header.
    first_data_row: int | None = None

    @property
    def data_start(self) -> int:
        return self.first_data_row if self.first_data_row is not None else self.header_row + 1


# Tier C — bespoke/manual sheets called out by name in the plan (§1.2). They do
# not share the mechanical header vocabulary; staging still captures them verbatim.
_BESPOKE_SHEETS = (
    "Shortlisted",
    "Ron - Ruthie",
    "COSTING SHEET",
    "Details of hotel IPD",
    "Homestay Details - LADAKH",
    "Info for Shally",
)

_SPECS: dict[str, SheetSpec] = {
    # Verified by inspection: title in row 1, header ("S.no., Name, Place, ...")
    # in row 2, data from row 3. This is Milestone 6's migration target.
    "Rajasthan": SheetSpec(
        "Rajasthan", ParserStrategy.MECHANICAL, workbook=HOTELS_DB, header_row=2
    ),
}
for _name in _BESPOKE_SHEETS:
    _SPECS[_name] = SheetSpec(_name, ParserStrategy.BESPOKE, workbook=HOTELS_DB)


def _default(sheet_name: str) -> SheetSpec:
    """Fallback for an unregistered sheet: mechanical, header on row 1, workbook
    unknown (the caller must supply the file explicitly)."""
    return SheetSpec(sheet_name, ParserStrategy.MECHANICAL)


def resolve_spec(sheet_name: str) -> SheetSpec:
    """Return the spec for `sheet_name`, or a mechanical default if unregistered."""
    return _SPECS.get(sheet_name, _default(sheet_name))
