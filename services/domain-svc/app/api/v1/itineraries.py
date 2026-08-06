"""Itinerary endpoints — nested create + read.

The create payload references segments by a client-chosen `key` so that day
presence and components can point at segments before the server assigns UUIDs.
The request schemas and the build logic live in `app.services.itinerary` so the
pricing preview (M7) assembles the exact same graph without persisting.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_org_id
from app.db import get_session
from app.models import (
    DaySegmentPresence,
    Itinerary,
    ItineraryComponent,
    ItineraryDay,
    Project,
    TravellerSegment,
)
from app.models.enums import AllocationBasis, ComponentKind, Occupancy, PaxClass
from app.services.itinerary import (
    ItineraryDraft as ItineraryCreateIn,
)
from app.services.itinerary import (
    KeyResolutionError,
    build_itinerary,
)

router = APIRouter(tags=["itineraries"])


# --------------------------------------------------------------------------- #
# response
# --------------------------------------------------------------------------- #


class ComponentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: ComponentKind
    description: str | None
    override_amount: Decimal | None
    allocation: AllocationBasis
    applies_to_segment_ids: list[uuid.UUID] | None
    applies_to_pax_class: PaxClass | None
    supplier_id: uuid.UUID | None
    rate_id: uuid.UUID | None
    transport_rate_id: uuid.UUID | None


class DayOut(BaseModel):
    id: uuid.UUID
    day_number: int
    date: date
    destination_id: uuid.UUID | None
    narrative: str | None
    present_segment_ids: list[uuid.UUID]
    components: list[ComponentOut]


class SegmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str
    pax_class: PaxClass
    occupancy: Occupancy
    pax_count: int
    markup_rule_id: uuid.UUID | None


class ItineraryOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    start_date: date
    end_date: date
    version: int
    status: str
    created_at: datetime | None = None
    segments: list[SegmentOut]
    days: list[DayOut]


class ItineraryBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    start_date: date
    end_date: date
    version: int
    status: str
    created_at: datetime


@router.get("/projects/{project_id}/itineraries", response_model=list[ItineraryBrief])
def list_project_itineraries(
    project_id: uuid.UUID,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> list[Itinerary]:
    return list(session.scalars(
        select(Itinerary)
        .where(Itinerary.project_id == project_id, Itinerary.org_id == org_id)
        .order_by(Itinerary.created_at.desc())
    ))


@router.post("/projects/{project_id}/itineraries", response_model=ItineraryOut,
             status_code=status.HTTP_201_CREATED)
def create_itinerary(
    project_id: uuid.UUID,
    body: ItineraryCreateIn,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> ItineraryOut:
    project = session.scalar(
        select(Project).where(Project.id == project_id, Project.org_id == org_id)
    )
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="project not found")

    try:
        itinerary = build_itinerary(session, org_id, project_id, body)
    except KeyResolutionError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from None
    return _serialize(session, itinerary)


@router.get("/itineraries/{itinerary_id}", response_model=ItineraryOut)
def get_itinerary(
    itinerary_id: uuid.UUID,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> ItineraryOut:
    itinerary = session.scalar(
        select(Itinerary).where(Itinerary.id == itinerary_id, Itinerary.org_id == org_id)
    )
    if itinerary is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="itinerary not found")
    return _serialize(session, itinerary)


def _serialize(session: Session, itinerary: Itinerary) -> ItineraryOut:
    segments = list(session.scalars(
        select(TravellerSegment).where(TravellerSegment.itinerary_id == itinerary.id)
    ))
    days = list(session.scalars(
        select(ItineraryDay).where(ItineraryDay.itinerary_id == itinerary.id)
        .order_by(ItineraryDay.day_number)
    ))
    day_out: list[DayOut] = []
    for d in days:
        present = list(session.scalars(
            select(DaySegmentPresence.traveller_segment_id).where(
                DaySegmentPresence.itinerary_day_id == d.id
            )
        ))
        comps = list(session.scalars(
            select(ItineraryComponent).where(ItineraryComponent.itinerary_day_id == d.id)
        ))
        day_out.append(DayOut(
            id=d.id, day_number=d.day_number, date=d.date, destination_id=d.destination_id,
            narrative=d.narrative, present_segment_ids=present,
            components=[ComponentOut.model_validate(c) for c in comps],
        ))
    return ItineraryOut(
        id=itinerary.id, project_id=itinerary.project_id, title=itinerary.title,
        start_date=itinerary.start_date, end_date=itinerary.end_date,
        version=itinerary.version, status=itinerary.status,
        created_at=itinerary.created_at,
        segments=[SegmentOut.model_validate(s) for s in segments], days=day_out,
    )
