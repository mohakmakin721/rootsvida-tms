"""Planning endpoints (Phase 5, 5a-M4) — the builder's AI intake + suggestions.

- POST /planning/intakes        save a structured client intake
- GET  /planning/intakes/{id}   load one
- POST /planning/parse          paste a form response → structured fields (LLM)
- POST /planning/suggest        intake → weights + ranked candidates + a draft

All require auth (current_org_id). `suggest`/`parse` use the active LLM provider —
the deterministic stub unless Gemini is configured — so they work with no key.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.deps import current_org_id
from app.db import get_session
from app.llm import IntakeParse, get_provider
from app.models import ItineraryIntake
from app.services import planning

router = APIRouter(prefix="/planning", tags=["planning"])


class IntakeIn(BaseModel):
    project_id: uuid.UUID | None = None
    client_id: uuid.UUID | None = None
    destination: str | None = None
    origin: str | None = None
    group_size: int | None = None
    themes: list[str] = []
    duration_days: int | None = None
    travel_start: date | None = None
    travel_end: date | None = None
    tier: str | None = None
    budget_inr: Decimal | None = None
    nationality: str | None = None
    age_band: str | None = None
    transport: list[str] = []
    service_types: list[str] = []
    must_include: str | None = None
    must_exclude: str | None = None
    notes: str | None = None


class IntakeOut(IntakeIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


class ParseIn(BaseModel):
    text: str


class SegmentBrief(BaseModel):
    pax_class: str | None = None  # indian | foreign
    occupancy: str | None = None  # single | double | triple | ...
    pax_count: int = 0


class SuggestIn(BaseModel):
    destination: str | None = None
    origin: str | None = None  # travellers' start point (for transport)
    duration_days: int | None = None
    group_size: int | None = None
    themes: list[str] = []
    tier: str | None = None
    budget_inr: Decimal | None = None
    age_band: str | None = None
    transport: list[str] = []
    # Traveller groups from the builder — pax mix drives foreigner-aware pricing hints
    # and accommodation choice.
    segments: list[SegmentBrief] = []


@router.post("/intakes", response_model=IntakeOut, status_code=status.HTTP_201_CREATED)
def create_intake(
    body: IntakeIn,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> ItineraryIntake:
    intake = ItineraryIntake(org_id=org_id, **body.model_dump())
    session.add(intake)
    session.flush()
    return intake


@router.get("/intakes/{intake_id}", response_model=IntakeOut)
def get_intake(
    intake_id: uuid.UUID,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> ItineraryIntake:
    intake = session.get(ItineraryIntake, intake_id)
    if intake is None or intake.org_id != org_id or intake.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="intake not found")
    return intake


@router.post("/parse", response_model=IntakeParse)
def parse_intake(
    body: ParseIn,
    _org_id: uuid.UUID = Depends(current_org_id),
) -> IntakeParse:
    """Parse a pasted client-form response into structured fields (LLM/stub)."""
    return get_provider().parse_intake(body.text)


@router.post("/suggest", response_model=planning.SuggestResult)
def suggest(
    body: SuggestIn,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> planning.SuggestResult:
    """Rank DB candidates by the intake's priorities and return an itinerary draft."""
    return planning.suggest(
        session, org_id,
        destination=body.destination, origin=body.origin,
        duration_days=body.duration_days,
        group_size=body.group_size, themes=body.themes, tier=body.tier,
        budget_inr=body.budget_inr, age_band=body.age_band, transport=body.transport,
        segments=[s.model_dump() for s in body.segments],
    )
