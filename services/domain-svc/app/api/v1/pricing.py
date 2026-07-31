"""Live pricing preview endpoint (Phase 3 M7).

`POST /pricing/preview` prices a draft itinerary and returns the per-segment and
group breakdown for the builder's live cost sidebar — without persisting anything
(see `app.services.preview`). It is a pure read from the client's point of view:
safe to call on every keystroke.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import current_org_id
from app.db import get_session
from app.models.enums import PlaceOfSupply
from app.services import preview
from app.services.itinerary import ItineraryDraft, KeyResolutionError
from pricing import model as pm

router = APIRouter(prefix="/pricing", tags=["pricing"])


class PreviewIn(BaseModel):
    itinerary: ItineraryDraft
    buyer_state_code: str | None = None
    buyer_country: str | None = "IN"
    tax_override: PlaceOfSupply | None = None
    rounding: pm.RoundingPolicy = pm.RoundingPolicy.NEAREST_1
    fx_inr_per_usd: Decimal | None = None
    margin_floor: Decimal | None = None


class SegmentPreview(BaseModel):
    label: str
    pax: int
    base_cost: str
    sell_per_pax: str
    group_total: str


class PreviewOut(BaseModel):
    engine_version: str
    segments: list[SegmentPreview]
    total_cost: str
    group_total: str
    profit: str
    revenue_ex_tax: str
    margin_pct: str
    gst_rate: str
    gst_treatment: str
    fx: dict[str, str] | None
    margin_floor: str | None
    below_floor: bool


@router.post("/preview", response_model=PreviewOut)
def preview_pricing(
    body: PreviewIn,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> PreviewOut:
    try:
        result = preview.preview_pricing(
            session, org_id, body.itinerary,
            buyer_state_code=body.buyer_state_code, buyer_country=body.buyer_country,
            tax_override=body.tax_override, rounding=body.rounding,
            fx_inr_per_usd=body.fx_inr_per_usd, margin_floor=body.margin_floor,
        )
    except KeyResolutionError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from None
    return PreviewOut(**result)
