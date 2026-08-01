"""Render a GST invoice (or credit note) to a PDF (Phase 4 M2).

Pure formatting over an already-frozen `Invoice` — it invents no numbers, it only
lays out what the invoice record holds (D-0001). Uses ReportLab (FOSS, pure-Python,
no native deps). Amounts print as `Rs.` with Indian digit grouping to avoid any
₹-glyph font dependency; a words line spells the total the way an Indian invoice does.
"""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models import Invoice
from app.models.enums import GstTreatment

_INK = colors.HexColor("#14211F")
_MUTED = colors.HexColor("#5B6B65")
_LINE = colors.HexColor("#C9D4D0")
_HEAD_BG = colors.HexColor("#EDF2F0")


def _group_indian(digits: str) -> str:
    """'169700' -> '1,69,700' (last 3, then groups of 2)."""
    if len(digits) <= 3:
        return digits
    head, tail = digits[:-3], digits[-3:]
    parts: list[str] = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    parts.insert(0, head)
    return ",".join(parts) + "," + tail


def rupees(value: Decimal) -> str:
    """Decimal -> 'Rs. 1,69,700.00' (or '(Rs. …)' for a negative credit line)."""
    neg = value < 0
    whole, frac = f"{abs(value):.2f}".split(".")
    out = f"Rs. {_group_indian(whole)}.{frac}"
    return f"({out})" if neg else out


_ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
         "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
         "Seventeen", "Eighteen", "Nineteen"]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _two(n: int) -> str:
    if n < 20:
        return _ONES[n]
    return (_TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else "")).strip()


def _three(n: int) -> str:
    h, rest = divmod(n, 100)
    out = (f"{_ONES[h]} Hundred" if h else "")
    if rest:
        out += (" " if out else "") + _two(rest)
    return out


def _in_words(n: int) -> str:
    """Indian-system words for a non-negative integer (crore/lakh/thousand)."""
    if n == 0:
        return "Zero"
    crore, n = divmod(n, 10_000_000)
    lakh, n = divmod(n, 100_000)
    thousand, n = divmod(n, 1_000)
    parts = []
    if crore:
        parts.append(f"{_in_words(crore)} Crore")
    if lakh:
        parts.append(f"{_two(lakh)} Lakh")
    if thousand:
        parts.append(f"{_two(thousand)} Thousand")
    if n:
        parts.append(_three(n))
    return " ".join(parts)


def amount_in_words(value: Decimal) -> str:
    """'Rupees One Lakh Sixty Nine Thousand Seven Hundred and Zero Paise Only'."""
    sign = "Minus " if value < 0 else ""
    whole, frac = f"{abs(value):.2f}".split(".")
    rupees_words = _in_words(int(whole))
    paise = int(frac)
    tail = f" and {_two(paise)} Paise" if paise else ""
    return f"{sign}Rupees {rupees_words}{tail} Only"


def render_invoice_pdf(invoice: Invoice, *, bank_details: str | None = None) -> bytes:
    is_credit = invoice.kind == "credit_note"
    title = "CREDIT NOTE" if is_credit else "TAX INVOICE"

    styles = getSampleStyleSheet()
    normal = ParagraphStyle("n", parent=styles["Normal"], fontSize=9, textColor=_INK, leading=13)
    small = ParagraphStyle("s", parent=normal, fontSize=8, textColor=_MUTED)
    right = ParagraphStyle("r", parent=normal, alignment=TA_RIGHT)
    label = ParagraphStyle("l", parent=small, spaceAfter=1)
    seller_name = ParagraphStyle("sn", parent=normal, fontSize=13, textColor=_INK, leading=16)
    title_style = ParagraphStyle("t", parent=normal, fontSize=15, alignment=TA_CENTER,
                                 textColor=_INK, spaceAfter=2)
    title_sub = ParagraphStyle("ts", parent=small, alignment=TA_CENTER, spaceAfter=8)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm, title=invoice.number,
    )
    el: list[Any] = []

    el.append(Paragraph(title, title_style))
    if is_credit and invoice.credit_note_of_id:
        el.append(Paragraph("issued against the referenced tax invoice", title_sub))
    else:
        el.append(Paragraph("(original for recipient)", title_sub))

    # Seller block
    seller_lines = [Paragraph(invoice.seller_name, seller_name)]
    if invoice.seller_address:
        for line in invoice.seller_address.splitlines():
            seller_lines.append(Paragraph(line, small))
    ident = "  ·  ".join(
        p for p in [
            f"GSTIN: {invoice.seller_gstin}" if invoice.seller_gstin else "",
            f"PAN: {invoice.seller_pan}" if invoice.seller_pan else "",
            f"State: {invoice.seller_state_name} ({invoice.seller_state_code})"
            if invoice.seller_state_name else "",
        ] if p
    )
    if ident:
        seller_lines.append(Paragraph(ident, small))
    el.append(Table([[seller_lines]], colWidths=[174 * mm],
                    style=TableStyle([("BOTTOMPADDING", (0, 0), (-1, -1), 8)])))

    # Meta grid: number/date/ref | buyer
    meta = [
        [Paragraph("Invoice No." if not is_credit else "Credit Note No.", label),
         Paragraph(f"<b>{invoice.number}</b>", normal),
         Paragraph("Bill To", label),
         Paragraph(f"<b>{invoice.buyer_name}</b>", normal)],
        [Paragraph("Date", label), Paragraph(invoice.invoice_date.isoformat(), normal),
         Paragraph("Buyer country", label),
         Paragraph(invoice.buyer_country or "—", normal)],
        [Paragraph("Ref (project)", label), Paragraph(invoice.project_code or "—", normal),
         Paragraph("Place of supply", label),
         Paragraph(invoice.place_of_supply or "—", normal)],
    ]
    el.append(Table(
        meta, colWidths=[26 * mm, 61 * mm, 26 * mm, 61 * mm],
        style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LINEBELOW", (0, -1), (-1, -1), 0.5, _LINE),
            ("LINEABOVE", (0, 0), (-1, 0), 0.5, _LINE),
        ]),
    ))
    el.append(Spacer(1, 8))

    # Line items
    rows = [[Paragraph("<b>#</b>", small), Paragraph("<b>Description</b>", small),
             Paragraph("<b>HSN/SAC</b>", small), Paragraph("<b>Taxable value</b>", right)]]
    for i, ln in enumerate(invoice.lines, start=1):
        rows.append([
            Paragraph(str(i), normal), Paragraph(ln.description, normal),
            Paragraph(ln.hsn or "—", normal), Paragraph(rupees(ln.taxable_value), right),
        ])
    el.append(Table(
        rows, colWidths=[10 * mm, 104 * mm, 24 * mm, 36 * mm],
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _HEAD_BG),
            ("GRID", (0, 0), (-1, -1), 0.5, _LINE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]),
    ))

    # Tax summary
    rate_pct = (invoice.gst_rate * Decimal(100)).quantize(Decimal("0.01"))
    half = (rate_pct / 2).quantize(Decimal("0.01"))
    summary: list[list[Any]] = [["Taxable value", rupees(invoice.taxable)]]
    if invoice.gst_treatment is GstTreatment.CGST_SGST:
        summary.append([f"CGST @ {half}%", rupees(invoice.cgst)])
        summary.append([f"SGST @ {half}%", rupees(invoice.sgst)])
    elif invoice.gst_treatment is GstTreatment.IGST:
        summary.append([f"IGST @ {rate_pct}%", rupees(invoice.igst)])
    else:
        summary.append(["GST (export / zero-rated)", rupees(Decimal(0))])
    if invoice.rounding_adjustment != 0:
        summary.append(["Rounding", rupees(invoice.rounding_adjustment)])
    summary.append([f"<b>{'TOTAL CREDIT' if is_credit else 'TOTAL'}</b>",
                    f"<b>{rupees(invoice.total)}</b>"])

    summary_tbl = Table(
        [[Paragraph(a, normal), Paragraph(b, right)] for a, b in summary],
        colWidths=[42 * mm, 36 * mm],
        style=TableStyle([
            ("LINEABOVE", (0, -1), (-1, -1), 0.75, _INK),
            ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]),
    )
    el.append(Table([["", summary_tbl]], colWidths=[96 * mm, 78 * mm],
                    style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                      ("TOPPADDING", (0, 0), (-1, -1), 8)])))

    el.append(Spacer(1, 6))
    el.append(Paragraph(f"<b>Amount in words:</b> {amount_in_words(invoice.total)}", small))

    footer: list[Any] = [Spacer(1, 14)]
    if bank_details:
        footer.append(Paragraph("<b>Payment details</b>", small))
        for line in bank_details.splitlines():
            footer.append(Paragraph(line, small))
        footer.append(Spacer(1, 10))
    footer.append(Paragraph(
        "Whether GST is payable under reverse charge: No. &nbsp;&nbsp; "
        "This is a computer-generated document.", small))
    footer.append(Spacer(1, 14))
    footer.append(Paragraph(f"For <b>{invoice.seller_name}</b>", normal))
    footer.append(Spacer(1, 14))
    footer.append(Paragraph("Authorised signatory", small))
    el.append(KeepTogether(footer))

    doc.build(el)
    return buf.getvalue()
