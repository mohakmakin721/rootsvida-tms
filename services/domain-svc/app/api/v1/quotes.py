"""Quote endpoints — price a draft, fetch, issue (freeze), revise (new version)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_org_id, require_permission
from app.db import get_session
from app.models import Itinerary, Project, Quote
from app.models.enums import GstTreatment, PlaceOfSupply
from app.security.permissions import COSTING_VIEW, QUOTES_ISSUE
from app.services import proposal as proposal_service
from app.services import quote as quote_service
from app.services.costing_xlsx import render_costing_xlsx
from app.services.proposal_pdf import render_proposal_pdf
from pricing import model as pm
from pricing.engine import MarginBelowFloor

_XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

router = APIRouter(tags=["quotes"])

# Committing a price (issuing) and seeing margin (costing) are distinct commercial
# capabilities, gated separately.
_can_issue = require_permission(QUOTES_ISSUE)
_can_view_costing = require_permission(COSTING_VIEW)


class QuoteCreateIn(BaseModel):
    buyer_state_code: str | None = None
    buyer_country: str | None = "IN"
    tax_override: PlaceOfSupply | None = None
    rounding: pm.RoundingPolicy = pm.RoundingPolicy.NEAREST_1
    fx_currency: str = "USD"
    fx_rate: Decimal | None = None
    margin_floor: Decimal | None = None


class IssueIn(BaseModel):
    issued_by: uuid.UUID | None = None
    valid_until: date | None = None


class QuoteLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    description: str
    cost_per_pax: Decimal | None
    sell_per_pax: Decimal | None
    pax_count: int | None
    line_total: Decimal | None


class QuoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    itinerary_id: uuid.UUID
    version: int
    status: str
    gst_rate: Decimal
    gst_treatment: GstTreatment
    fx_currency: str | None
    fx_rate_inr_usd: Decimal | None
    rounding_policy: str
    total_cost: Decimal | None
    total_taxable: Decimal | None
    total_tax: Decimal | None
    total_gross: Decimal | None
    margin_pct: Decimal | None
    engine_version: str | None
    issued_at: datetime | None
    valid_until: date | None
    created_at: datetime
    lines: list[QuoteLineOut]
    pricing_snapshot: dict[str, Any] | None


def _require(session: Session, org_id: uuid.UUID, quote_id: uuid.UUID) -> Quote:
    quote = session.scalar(select(Quote).where(Quote.id == quote_id, Quote.org_id == org_id))
    if quote is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="quote not found")
    return quote


@router.post("/itineraries/{itinerary_id}/quotes", response_model=QuoteOut,
             status_code=status.HTTP_201_CREATED)
def create_quote(
    itinerary_id: uuid.UUID,
    body: QuoteCreateIn,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> Quote:
    try:
        return quote_service.create_quote(session, itinerary_id, **body.model_dump())
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
    except MarginBelowFloor as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"margin {exc.margin_pct} is below the floor {exc.floor}",
        ) from None


@router.get("/quotes/{quote_id}", response_model=QuoteOut)
def get_quote(
    quote_id: uuid.UUID,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> Quote:
    return _require(session, org_id, quote_id)


@router.get("/quotes/{quote_id}/proposal.pdf")
def quote_proposal_pdf(
    quote_id: uuid.UUID,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> Response:
    try:
        data = proposal_service.build_proposal(session, org_id, quote_id)
    except proposal_service.ProposalError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
    pdf = render_proposal_pdf(data)
    code = data.get("project_code") or "proposal"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="proposal-{code}.pdf"'},
    )


@router.get("/quotes/{quote_id}/costing.xlsx")
def quote_costing_xlsx(
    quote_id: uuid.UUID,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    _user: object = Depends(_can_view_costing),
) -> Response:
    """INTERNAL costing workbook (shows margin) — needs costing.view."""
    quote = _require(session, org_id, quote_id)
    project = session.get(Project, quote.project_id)
    itinerary = session.get(Itinerary, quote.itinerary_id)
    xlsx = render_costing_xlsx(quote, project, itinerary)
    code = (project.code if project else "quote")
    filename = f"costing-{code}-v{quote.version}.xlsx"
    return Response(
        content=xlsx,
        media_type=_XLSX_MEDIA,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/projects/{project_id}/quotes", response_model=list[QuoteOut])
def list_project_quotes(
    project_id: uuid.UUID,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> list[Quote]:
    return list(session.scalars(
        select(Quote).where(Quote.org_id == org_id, Quote.project_id == project_id)
        .order_by(Quote.version)
    ))


@router.post("/quotes/{quote_id}/issue", response_model=QuoteOut)
def issue_quote(
    quote_id: uuid.UUID,
    body: IssueIn,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    _user: object = Depends(_can_issue),
) -> Quote:
    quote = _require(session, org_id, quote_id)
    try:
        return quote_service.issue_quote(session, quote, issued_by=body.issued_by,
                                         valid_until=body.valid_until)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from None


@router.post("/quotes/{quote_id}/revise", response_model=QuoteOut,
             status_code=status.HTTP_201_CREATED)
def revise_quote(
    quote_id: uuid.UUID,
    body: QuoteCreateIn,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> Quote:
    quote = _require(session, org_id, quote_id)
    try:
        return quote_service.revise_issued_quote(session, quote, **body.model_dump())
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from None
    except MarginBelowFloor as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"margin {exc.margin_pct} is below the floor {exc.floor}",
        ) from None
