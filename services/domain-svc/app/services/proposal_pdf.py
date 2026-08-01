"""Render a client travel proposal to PDF (Phase 4).

A sales document, not an accounting one: itinerary-forward, per-person pricing,
no internal figures. Pure formatting over the dict from `proposal.build_proposal`.
ReportLab (FOSS). Amounts as `Rs.`/currency-code to stay glyph-safe.
"""

from __future__ import annotations

from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.services.invoice_pdf import _group_indian

_INK = colors.HexColor("#14211F")
_ACCENT = colors.HexColor("#0E7C6B")
_MUTED = colors.HexColor("#5B6B65")
_LINE = colors.HexColor("#C9D4D0")
_BAND = colors.HexColor("#14211F")
_SOFT = colors.HexColor("#EDF2F0")


def _money(value: str | None, currency: str | None = None) -> str:
    """'47303.00' -> 'Rs. 47,303' or 'USD 498' (whole rupees/units, no paise)."""
    if value is None:
        return "—"
    whole = value.split(".")[0]
    grouped = _group_indian(whole.lstrip("-"))
    prefix = f"{currency} " if currency else "Rs. "
    return f"{prefix}{grouped}"


def render_proposal_pdf(data: dict[str, Any]) -> bytes:
    styles = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=styles["Normal"], fontSize=9.5, textColor=_INK, leading=14)
    muted = ParagraphStyle("m", parent=body, textColor=_MUTED, fontSize=8.5)
    right = ParagraphStyle("r", parent=body, alignment=TA_RIGHT)
    right_b = ParagraphStyle("rb", parent=right, textColor=_INK)
    band_title = ParagraphStyle("bt", parent=body, textColor=colors.white, fontSize=17, leading=20)
    band_sub = ParagraphStyle("bs", parent=body, textColor=colors.HexColor("#AEC6C0"),
                              fontSize=9, leading=12)
    h_title = ParagraphStyle("ht", parent=body, fontSize=20, leading=24, textColor=_INK,
                             spaceBefore=4)
    section = ParagraphStyle("sec", parent=body, fontSize=12, textColor=_ACCENT, leading=15,
                             spaceBefore=6, spaceAfter=4)
    day_head = ParagraphStyle("dh", parent=body, fontSize=10.5, textColor=_INK, leading=14)
    total_style = ParagraphStyle("tot", parent=body, fontSize=16, textColor=_ACCENT,
                                 alignment=TA_RIGHT, leading=18)

    from io import BytesIO

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=14 * mm, bottomMargin=16 * mm, title=f"Proposal — {data['title']}",
    )
    el: list[Any] = []

    # Branded band
    band = Table(
        [[Paragraph(data["seller_name"], band_title)],
         [Paragraph("TRAVEL PROPOSAL", band_sub)]],
        colWidths=[174 * mm],
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), _BAND),
            ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (0, 0), 12), ("BOTTOMPADDING", (0, 0), (0, 0), 0),
            ("TOPPADDING", (0, 1), (0, 1), 0), ("BOTTOMPADDING", (0, 1), (0, 1), 12),
        ]),
    )
    el.append(band)
    el.append(Spacer(1, 12))

    el.append(Paragraph(data["title"], h_title))
    meta_bits = [f"<b>Prepared for</b> {data['client_name']}",
                 f"<b>{data['nights']} nights</b> · {data['start_date']} to {data['end_date']}"]
    if data.get("project_code"):
        meta_bits.append(f"Ref {data['project_code']}")
    el.append(Paragraph("  ·  ".join(meta_bits), muted))
    el.append(Spacer(1, 6))
    el.append(HRFlowable(width="100%", thickness=0.6, color=_LINE))
    el.append(Spacer(1, 8))

    # Day by day
    el.append(Paragraph("Your journey, day by day", section))
    for d in data["days"]:
        where = d["destination"] or ""
        head = f"<b>Day {d['day_number']}</b>  ·  {d['date']}" + (f"  ·  {where}" if where else "")
        block: list[Any] = [Paragraph(head, day_head)]
        if d.get("narrative"):
            block.append(Paragraph(d["narrative"], body))
        block.append(Spacer(1, 6))
        el.append(KeepTogether(block))

    # Inclusions
    if data["inclusions"]:
        el.append(Spacer(1, 2))
        el.append(Paragraph("What's included", section))
        for inc in data["inclusions"]:
            el.append(Paragraph(f"•  {inc}", body))
        el.append(Spacer(1, 8))

    # Pricing
    price_block: list[Any] = [Paragraph("Your investment", section)]
    cur = data.get("fx_currency")
    header = [Paragraph("<b>Travellers</b>", muted), Paragraph("<b>Group</b>", muted),
              Paragraph("<b>Per person</b>", right)]
    rows = [header]
    for g in data["groups"]:
        pp = _money(g["per_pax_inr"])
        if g.get("per_pax_fx") and cur:
            pp += f"   ({_money(g['per_pax_fx'], cur)})"
        rows.append([
            Paragraph(g["label"], body),
            Paragraph(f"{g['pax']} pax", body),
            Paragraph(pp, right_b),
        ])
    price_block.append(Table(
        rows, colWidths=[80 * mm, 30 * mm, 64 * mm],
        style=TableStyle([
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, _LINE),
            ("LINEBELOW", (0, 1), (-1, -1), 0.4, _SOFT),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]),
    ))
    total_txt = _money(data["total_inr"])
    if data.get("total_fx") and cur:
        total_txt += f"   ({_money(data['total_fx'], cur)})"
    price_block.append(Spacer(1, 6))
    price_block.append(Paragraph(f"Total  {total_txt}", total_style))
    price_block.append(Paragraph("Per-person prices are inclusive of GST.", muted))
    el.append(KeepTogether(price_block))

    # Footer
    el.append(Spacer(1, 16))
    el.append(HRFlowable(width="100%", thickness=0.6, color=_LINE))
    el.append(Spacer(1, 8))
    valid = (f"This proposal is valid until <b>{data['valid_until']}</b>. "
             if data.get("valid_until") else "")
    el.append(Paragraph(
        f"{valid}We would be delighted to host you. Reply to confirm and we'll "
        f"reserve your dates.", body))
    el.append(Spacer(1, 6))
    el.append(Paragraph(f"With warm regards,<br/><b>{data['seller_name']}</b>", body))

    doc.build(el)
    return buf.getvalue()
