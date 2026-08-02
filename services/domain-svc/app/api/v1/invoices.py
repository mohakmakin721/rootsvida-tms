"""Invoice endpoints (Phase 4) — generate from a quote, fetch, list, credit."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_org_id, require_permission
from app.config import get_settings
from app.db import get_session
from app.models import Invoice
from app.models.enums import GstTreatment
from app.security.permissions import INVOICES_MANAGE
from app.services import invoice as invoice_service
from app.services.invoice_pdf import render_invoice_pdf

router = APIRouter(tags=["invoices"])

# Raising invoices / credit notes is a billing action — gated on invoices.manage.
_billing = require_permission(INVOICES_MANAGE)


class GenerateInvoiceIn(BaseModel):
    invoice_date: date | None = None
    place_of_supply: str | None = None


class CreditNoteIn(BaseModel):
    invoice_date: date | None = None
    reason: str | None = None


class InvoiceLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    description: str
    hsn: str | None
    quantity: Decimal
    taxable_value: Decimal


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    number: str
    fiscal_year: str
    serial: int
    kind: str
    status: str
    invoice_date: date
    project_id: uuid.UUID
    quote_id: uuid.UUID
    project_code: str | None
    credit_note_of_id: uuid.UUID | None
    seller_name: str
    seller_gstin: str | None
    seller_pan: str | None
    seller_state_code: str | None
    seller_state_name: str | None
    seller_address: str | None
    buyer_name: str
    buyer_country: str | None
    buyer_gstin: str | None
    place_of_supply: str | None
    hsn: str | None
    gst_rate: Decimal
    gst_treatment: GstTreatment
    taxable: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    rounding_adjustment: Decimal
    total: Decimal
    notes: str | None
    engine_version: str | None
    created_at: datetime
    lines: list[InvoiceLineOut]


def _require(session: Session, org_id: uuid.UUID, invoice_id: uuid.UUID) -> Invoice:
    inv = session.scalar(select(Invoice).where(Invoice.id == invoice_id, Invoice.org_id == org_id))
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="invoice not found")
    return inv


@router.post("/quotes/{quote_id}/invoice", response_model=InvoiceOut,
             status_code=status.HTTP_201_CREATED)
def generate_invoice(
    quote_id: uuid.UUID,
    body: GenerateInvoiceIn | None = None,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    _user: object = Depends(_billing),
) -> Invoice:
    body = body or GenerateInvoiceIn()
    try:
        return invoice_service.generate_invoice(
            session, org_id, quote_id,
            invoice_date=body.invoice_date, place_of_supply=body.place_of_supply,
        )
    except invoice_service.InvoiceError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from None


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
def get_invoice(
    invoice_id: uuid.UUID,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> Invoice:
    return _require(session, org_id, invoice_id)


@router.get("/invoices/{invoice_id}/pdf")
def invoice_pdf(
    invoice_id: uuid.UUID,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> Response:
    invoice = _require(session, org_id, invoice_id)
    pdf = render_invoice_pdf(invoice, bank_details=get_settings().rv_seller_bank_details or None)
    filename = invoice.number.replace("/", "-") + ".pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/projects/{project_id}/invoices", response_model=list[InvoiceOut])
def list_project_invoices(
    project_id: uuid.UUID,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> list[Invoice]:
    return list(session.scalars(
        select(Invoice).where(Invoice.org_id == org_id, Invoice.project_id == project_id)
        .order_by(Invoice.created_at.desc())
    ))


@router.post("/invoices/{invoice_id}/credit-note", response_model=InvoiceOut,
             status_code=status.HTTP_201_CREATED)
def create_credit_note(
    invoice_id: uuid.UUID,
    body: CreditNoteIn | None = None,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    _user: object = Depends(_billing),
) -> Invoice:
    body = body or CreditNoteIn()
    try:
        return invoice_service.generate_credit_note(
            session, org_id, invoice_id, invoice_date=body.invoice_date, reason=body.reason,
        )
    except invoice_service.InvoiceError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from None
