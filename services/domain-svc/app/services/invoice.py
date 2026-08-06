"""Invoice generation (Phase 4) — the immutable GST document from an issued quote.

The tax is done by the pure engine (`split_tax`), so an invoice reproduces the
golden fixture REPL/2627/TP10 to the paisa (D-0001). Numbering is gapless per
financial year via a locked `DocumentCounter`. A correction cancels the original
and raises a negated **credit note** — invoices are never edited.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    DocumentCounter,
    Invoice,
    InvoiceLine,
    Itinerary,
    Organization,
    Project,
    ProjectMilestone,
    Quote,
)
from app.models.enums import GstTreatment
from pricing import model as pm
from pricing.money import money
from pricing.tax import split_tax

_HUNDRED = Decimal(100)
# Split the quote's exact gross without re-rounding it (the rounding policy was a
# quote-time decision); a tiny step just backs out the taxable + tax halves.
_NO_REROUND = money("0.01")


class InvoiceError(Exception):
    """A business rule blocked invoice generation (bad state, already invoiced)."""


def fiscal_year(d: date) -> str:
    """Indian financial year for a date — April→March. 2026-08-02 → '2026-27'."""
    if d.month >= 4:
        return f"{d.year}-{(d.year + 1) % 100:02d}"
    return f"{d.year - 1}-{d.year % 100:02d}"


def _reserve_serial(session: Session, org_id: uuid.UUID, kind: str, fy: str) -> int:
    """Atomically claim the next number for (org, kind, FY). Gapless: the counter
    row is locked FOR UPDATE so concurrent invoices cannot skip or reuse a number."""
    counter = session.execute(
        select(DocumentCounter)
        .where(
            DocumentCounter.org_id == org_id,
            DocumentCounter.kind == kind,
            DocumentCounter.fiscal_year == fy,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if counter is None:
        counter = DocumentCounter(org_id=org_id, kind=kind, fiscal_year=fy, last_number=0)
        session.add(counter)
        session.flush()
    counter.last_number += 1
    session.flush()
    return counter.last_number


def _tax_rule_from_quote(quote: Quote) -> pm.TaxRule:
    """Rebuild the pure tax rule from the quote's frozen fields (reproducible)."""
    snapshot = quote.pricing_snapshot or {}
    hsn = (((snapshot.get("inputs") or {}).get("tax_rule")) or {}).get("hsn")
    return pm.TaxRule(
        rate=quote.gst_rate / _HUNDRED,
        treatment=pm.TaxTreatment(quote.gst_treatment.value),
        hsn=hsn,
    )


def _place_of_supply(
    treatment: GstTreatment, client_country: str | None, seller_state: str | None
) -> str:
    if client_country and client_country.upper() != "IN":
        return f"{client_country} (outside India)"
    if treatment is GstTreatment.IGST:
        return "Other state (inter-state)"
    return seller_state or "Intra-state"


def generate_invoice(
    session: Session,
    org_id: uuid.UUID,
    quote_id: uuid.UUID,
    *,
    invoice_date: date | None = None,
    place_of_supply: str | None = None,
) -> Invoice:
    """Generate the GST invoice for an issued quote. Persists nothing on failure."""
    quote = session.scalar(select(Quote).where(Quote.id == quote_id, Quote.org_id == org_id))
    if quote is None:
        raise InvoiceError("quote not found")
    if quote.status not in ("issued", "accepted"):
        raise InvoiceError(f"only an issued quote can be invoiced (status={quote.status!r})")
    if quote.total_gross is None:
        raise InvoiceError("quote has no total to invoice")

    existing = session.scalar(
        select(Invoice).where(
            Invoice.quote_id == quote_id, Invoice.org_id == org_id,
            Invoice.kind == "invoice", Invoice.status == "issued",
        )
    )
    if existing is not None:
        raise InvoiceError(f"quote already invoiced as {existing.number}")

    project = session.get(Project, quote.project_id)
    itinerary = session.get(Itinerary, quote.itinerary_id)
    org = session.get(Organization, org_id)
    settings = get_settings()

    rule = _tax_rule_from_quote(quote)
    breakdown = split_tax(money(quote.total_gross), rule, step=_NO_REROUND)

    d = invoice_date or date.today()
    fy = fiscal_year(d)
    serial = _reserve_serial(session, org_id, "invoice", fy)
    number = f"{settings.rv_invoice_prefix}/{fy}/{serial:04d}"

    pos = place_of_supply or _place_of_supply(
        quote.gst_treatment, project.client_country if project else None,
        org.gst_state_name if org else settings.rv_gst_state_name,
    )

    invoice = Invoice(
        org_id=org_id, number=number, fiscal_year=fy, serial=serial,
        kind="invoice", status="issued", invoice_date=d,
        project_id=quote.project_id, quote_id=quote_id,
        project_code=project.code if project else None,
        seller_name=(org.name if org else settings.rv_org_name),
        seller_gstin=(org.gstin if org else settings.rv_gstin),
        seller_pan=(org.pan if org else settings.rv_pan),
        seller_state_code=(org.gst_state_code if org else settings.rv_gst_state_code),
        seller_state_name=(org.gst_state_name if org else settings.rv_gst_state_name),
        seller_address=settings.rv_seller_address or None,
        buyer_name=(project.client_name if project else "Client"),
        buyer_country=(project.client_country if project else None),
        place_of_supply=pos,
        hsn=rule.hsn,
        gst_rate=quote.gst_rate / _HUNDRED,
        gst_treatment=quote.gst_treatment,
        taxable=breakdown.taxable, cgst=breakdown.cgst, sgst=breakdown.sgst,
        igst=breakdown.igst, rounding_adjustment=breakdown.rounding_adjustment,
        total=breakdown.total,
        engine_version=quote.engine_version,
    )
    session.add(invoice)
    session.flush()

    session.add(InvoiceLine(
        org_id=org_id, invoice_id=invoice.id,
        description=f"Tour package — {itinerary.title}" if itinerary else "Tour package",
        hsn=rule.hsn, quantity=Decimal(1), taxable_value=breakdown.taxable,
    ))
    # Auto-track the invoice on the project timeline (a completed, dated event).
    session.add(ProjectMilestone(
        org_id=org_id, project_id=quote.project_id, kind="invoice",
        title=f"Invoice {number} raised", due_date=d, amount=breakdown.total, done=True,
    ))
    session.flush()
    return invoice


def generate_credit_note(
    session: Session,
    org_id: uuid.UUID,
    invoice_id: uuid.UUID,
    *,
    invoice_date: date | None = None,
    reason: str | None = None,
) -> Invoice:
    """Cancel an issued invoice and raise a negated credit note against it."""
    original = session.scalar(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.org_id == org_id)
    )
    if original is None:
        raise InvoiceError("invoice not found")
    if original.kind != "invoice" or original.status != "issued":
        raise InvoiceError("only an issued invoice can be credited")

    original.status = "cancelled"
    session.flush()

    d = invoice_date or date.today()
    fy = fiscal_year(d)
    serial = _reserve_serial(session, org_id, "credit_note", fy)
    number = f"{get_settings().rv_invoice_prefix}/CN/{fy}/{serial:04d}"

    def neg(v: Decimal) -> Decimal:
        return -v

    credit = Invoice(
        org_id=org_id, number=number, fiscal_year=fy, serial=serial,
        kind="credit_note", status="issued", invoice_date=d,
        project_id=original.project_id, quote_id=original.quote_id,
        project_code=original.project_code, credit_note_of_id=original.id,
        seller_name=original.seller_name, seller_gstin=original.seller_gstin,
        seller_pan=original.seller_pan, seller_state_code=original.seller_state_code,
        seller_state_name=original.seller_state_name, seller_address=original.seller_address,
        buyer_name=original.buyer_name, buyer_country=original.buyer_country,
        place_of_supply=original.place_of_supply,
        hsn=original.hsn, gst_rate=original.gst_rate, gst_treatment=original.gst_treatment,
        taxable=neg(original.taxable), cgst=neg(original.cgst), sgst=neg(original.sgst),
        igst=neg(original.igst), rounding_adjustment=neg(original.rounding_adjustment),
        total=neg(original.total),
        notes=reason, engine_version=original.engine_version,
    )
    session.add(credit)
    session.flush()
    session.add(InvoiceLine(
        org_id=org_id, invoice_id=credit.id,
        description=f"Credit note against {original.number}"
        + (f" — {reason}" if reason else ""),
        hsn=original.hsn, quantity=Decimal(1), taxable_value=neg(original.taxable),
    ))
    session.flush()
    return credit
