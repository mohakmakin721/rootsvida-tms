"""Internal costing workbook (Phase 4) — the confidential cost→sell build-up.

The opposite of the client proposal: this is for the operator (and their CA). It
reads the quote's frozen `pricing_snapshot` — the exact inputs and outputs the
deterministic engine produced — and lays out, per traveller group, how the base
cost becomes the selling price (markup, GST, rounding), plus the raw supplier cost
inputs and a full trace. It shows margin. Never send it to a client.
"""

from __future__ import annotations

from io import BytesIO
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from app.models import Itinerary, Project, Quote

INR_FMT = "#,##0.00"
_INK = "14211F"
_BAND = "14211F"
_ACCENT = "0E7C6B"
_SOFT = "EDF2F0"

_HEAD_FONT = Font(bold=True, color="FFFFFF", size=10)
_HEAD_FILL = PatternFill("solid", fgColor=_ACCENT)
_TITLE_FONT = Font(bold=True, color="FFFFFF", size=14)
_TITLE_FILL = PatternFill("solid", fgColor=_BAND)
_LABEL_FONT = Font(bold=True, color=_INK)
_TOTAL_FONT = Font(bold=True, color=_INK, size=11)
_TOTAL_FILL = PatternFill("solid", fgColor=_SOFT)
_MUTED_FONT = Font(color="5B6B65", size=9, italic=True)


def _f(value: Any) -> float:
    return float(value) if value not in (None, "") else 0.0


def _trace_amount(traces: list[dict[str, Any]], kind: str) -> float:
    return sum(_f(t["amount"]) for t in traces if t.get("kind") == kind)


def _money_cell(ws: Worksheet, row: int, col: int, value: Any) -> None:
    cell = ws.cell(row=row, column=col, value=_f(value))
    cell.number_format = INR_FMT


def _summary(ws: Worksheet, quote: Quote, project: Project | None,
             itinerary: Itinerary | None, inp: dict[str, Any], out: dict[str, Any]) -> None:
    ws.title = "Costing"
    ws.sheet_view.showGridLines = False

    ws.merge_cells("A1:K1")
    t = ws.cell(row=1, column=1, value="INTERNAL COSTING — CONFIDENTIAL (do not send to client)")
    t.font = _TITLE_FONT
    t.fill = _TITLE_FILL
    t.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 24

    meta = [
        ("Project", (project.code if project else "—")),
        ("Client", (project.client_name if project else "—")),
        ("Itinerary", (itinerary.title if itinerary else "—")),
        ("Dates", f"{itinerary.start_date} to {itinerary.end_date}" if itinerary else "—"),
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
            value="Per-traveller-group build-up (per person unless noted)").font = _LABEL_FONT
    row += 1

    headers = ["Group", "Pax", "Accom", "Shared", "Direct", "Base cost",
               "Markup", "Sell ex-tax", "GST", "Round", "Sell/pax", "Group total"]
    for c, h in enumerate(headers, start=1):
        cell = ws.cell(row=row, column=c, value=h)
        cell.font = _HEAD_FONT
        cell.fill = _HEAD_FILL
        cell.alignment = Alignment(horizontal="right" if c > 2 else "left")
    row += 1

    for seg in out.get("segments", []):
        traces = seg.get("trace", [])
        markup_amt = _trace_amount(traces, "markup")
        tax_amt = _trace_amount(traces, "tax")
        round_amt = _trace_amount(traces, "rounding")
        base = _f(seg["base_cost"])

        ws.cell(row=row, column=1, value=seg["label"])
        ws.cell(row=row, column=2, value=int(seg["pax"])).alignment = Alignment(horizontal="right")
        _money_cell(ws, row, 3, seg["accommodation"])
        _money_cell(ws, row, 4, seg["shared"])
        _money_cell(ws, row, 5, seg["direct"])
        _money_cell(ws, row, 6, base)
        _money_cell(ws, row, 7, markup_amt)
        _money_cell(ws, row, 8, base + markup_amt)
        _money_cell(ws, row, 9, tax_amt)
        _money_cell(ws, row, 10, round_amt)
        _money_cell(ws, row, 11, seg["sell_per_pax"])
        _money_cell(ws, row, 12, seg["group_total"])
        row += 1

    # Totals block
    row += 1
    totals: list[tuple[str, Any]] = [
        ("Total cost", out.get("total_cost")),
        ("Revenue (ex-tax)", out.get("revenue_ex_tax")),
        ("Profit", out.get("profit")),
    ]
    for k, v in totals:
        ws.cell(row=row, column=1, value=k).font = _TOTAL_FONT
        _money_cell(ws, row, 2, v)
        ws.cell(row=row, column=2).font = _TOTAL_FONT
        row += 1
    ws.cell(row=row, column=1, value="True margin").font = _TOTAL_FONT
    # Snapshot margin_pct is a fraction (0.1252); Excel's % format shows 12.52%.
    mc = ws.cell(row=row, column=2, value=_f(out.get("margin_pct")))
    mc.number_format = "0.00%"
    mc.font = Font(bold=True, color=_ACCENT, size=11)
    row += 1
    ws.cell(row=row, column=1, value="Group total (gross)").font = _TOTAL_FONT
    _money_cell(ws, row, 2, out.get("group_total"))
    ws.cell(row=row, column=2).font = _TOTAL_FONT
    for r in range(row - 4, row + 1):
        for c in range(1, 3):
            ws.cell(row=r, column=c).fill = _TOTAL_FILL

    # Tax breakdown, if present (gross_nearest_100 quotes carry one).
    tax = out.get("tax")
    if tax:
        row += 2
        ws.cell(row=row, column=1, value="GST breakdown").font = _LABEL_FONT
        row += 1
        for k in ("taxable", "cgst", "sgst", "igst", "rounding_adjustment", "total"):
            ws.cell(row=row, column=1, value=k)
            _money_cell(ws, row, 2, tax[k])
            row += 1

    widths = [22, 6, 12, 12, 12, 12, 12, 12, 12, 10, 12, 14]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _inputs(ws: Worksheet, inp: dict[str, Any]) -> None:
    ws.sheet_view.showGridLines = False
    ws.cell(row=1, column=1, value="Cost inputs (what the engine priced)").font = _LABEL_FONT

    row = 3
    ws.cell(row=row, column=1, value="Accommodation").font = _LABEL_FONT
    row += 1
    for h, c in [("Stay", 1), ("Nights", 2), ("Occupancy", 3), ("Room rate", 4)]:
        cell = ws.cell(row=row, column=c, value=h)
        cell.font = _HEAD_FONT
        cell.fill = _HEAD_FILL
    row += 1
    for st in inp.get("stays", []):
        for occ, rate in (st.get("room_rate") or {}).items():
            ws.cell(row=row, column=1, value=st["label"])
            ws.cell(row=row, column=2, value=int(st["nights"]))
            ws.cell(row=row, column=3, value=occ)
            _money_cell(ws, row, 4, rate)
            row += 1

    row += 2
    ws.cell(row=row, column=1, value="Other components").font = _LABEL_FONT
    row += 1
    for h, c in [("Component", 1), ("Kind", 2), ("Amount", 3)]:
        cell = ws.cell(row=row, column=c, value=h)
        cell.font = _HEAD_FONT
        cell.fill = _HEAD_FILL
    row += 1
    for comp in inp.get("components", []):
        ws.cell(row=row, column=1, value=comp["label"])
        ws.cell(row=row, column=2, value=comp.get("kind"))
        _money_cell(ws, row, 3, comp["amount"])
        row += 1

    for i, w in enumerate([26, 12, 12, 12], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _trace(ws: Worksheet, out: dict[str, Any]) -> None:
    ws.sheet_view.showGridLines = False
    heading = "Build-up trace — every contribution to each per-person number"
    ws.cell(row=1, column=1, value=heading).font = _LABEL_FONT
    row = 3
    for h, c in [("Group", 1), ("Kind", 2), ("Item", 3), ("Amount", 4)]:
        cell = ws.cell(row=row, column=c, value=h)
        cell.font = _HEAD_FONT
        cell.fill = _HEAD_FILL
    row += 1
    for seg in out.get("segments", []):
        for t in seg.get("trace", []):
            ws.cell(row=row, column=1, value=seg["label"])
            ws.cell(row=row, column=2, value=t.get("kind"))
            ws.cell(row=row, column=3, value=t.get("label"))
            _money_cell(ws, row, 4, t.get("amount"))
            row += 1
    for i, w in enumerate([22, 14, 30, 12], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def render_costing_xlsx(
    quote: Quote, project: Project | None, itinerary: Itinerary | None
) -> bytes:
    snap = quote.pricing_snapshot or {}
    inp = snap.get("inputs", {})
    out = snap.get("output", {})

    wb = Workbook()
    _summary(wb.active, quote, project, itinerary, inp, out)
    _inputs(wb.create_sheet("Cost inputs"), inp)
    _trace(wb.create_sheet("Build-up"), out)

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
