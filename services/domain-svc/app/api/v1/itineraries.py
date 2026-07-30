"""Itinerary endpoints — nested create + read.

The create payload references segments by a client-chosen `key` so that day
presence and components can point at segments before the server assigns UUIDs.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
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

router = APIRouter(tags=["itineraries"])


# --------------------------------------------------------------------------- #
# request
# --------------------------------------------------------------------------- #


class SegmentIn(BaseModel):
    key: str  # client-side reference used by presence + components
    label: str
    pax_class: PaxClass
    occupancy: Occupancy
    pax_count: int = Field(gt=0)
    markup_rule_id: uuid.UUID


class ComponentIn(BaseModel):
    kind: ComponentKind
    description: str | None = None
    override_amount: Decimal | None = None
    override_reason: str | None = None
    allocation: AllocationBasis = AllocationBasis.ALL_PAX
    applies_to_segment_keys: list[str] | None = None
    applies_to_pax_class: PaxClass | None = None
    supplier_id: uuid.UUID | None = None
    rate_id: uuid.UUID | None = None
    transport_rate_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _override_needs_reason(self) -> ComponentIn:
        if self.override_amount is not None and not self.override_reason:
            raise ValueError("override_amount requires override_reason")
        return self


class DayIn(BaseModel):
    day_number: int
    date: date
    destination_id: uuid.UUID | None = None
    narrative: str | None = None
    present_segment_keys: list[str] = []
    components: list[ComponentIn] = []


class ItineraryCreateIn(BaseModel):
    title: str
    start_date: date
    end_date: date
    generated_by: str | None = None
    segments: list[SegmentIn]
    days: list[DayIn] = []


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
    segments: list[SegmentOut]
    days: list[DayOut]


def _keys(session: Session, itinerary_id: uuid.UUID, keys: list[str],
          mapping: dict[str, uuid.UUID]) -> list[uuid.UUID]:
    try:
        return [mapping[k] for k in keys]
    except KeyError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"unknown segment key {exc.args[0]!r}") from None


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

    itinerary = Itinerary(org_id=org_id, project_id=project_id, title=body.title,
                          start_date=body.start_date, end_date=body.end_date,
                          generated_by=body.generated_by)
    session.add(itinerary)
    session.flush()

    key_to_id: dict[str, uuid.UUID] = {}
    for s in body.segments:
        seg = TravellerSegment(org_id=org_id, itinerary_id=itinerary.id, label=s.label,
                               pax_class=s.pax_class, occupancy=s.occupancy,
                               pax_count=s.pax_count, markup_rule_id=s.markup_rule_id)
        session.add(seg)
        session.flush()
        key_to_id[s.key] = seg.id

    for d in body.days:
        day = ItineraryDay(org_id=org_id, itinerary_id=itinerary.id, day_number=d.day_number,
                           date=d.date, destination_id=d.destination_id, narrative=d.narrative)
        session.add(day)
        session.flush()
        for seg_id in _keys(session, itinerary.id, d.present_segment_keys, key_to_id):
            session.add(DaySegmentPresence(org_id=org_id, itinerary_day_id=day.id,
                                           traveller_segment_id=seg_id))
        for c in d.components:
            applies = _keys(session, itinerary.id, c.applies_to_segment_keys or [], key_to_id)
            session.add(ItineraryComponent(
                org_id=org_id, itinerary_day_id=day.id, kind=c.kind, description=c.description,
                override_amount=c.override_amount, override_reason=c.override_reason,
                allocation=c.allocation, applies_to_segment_ids=applies or None,
                applies_to_pax_class=c.applies_to_pax_class, supplier_id=c.supplier_id,
                rate_id=c.rate_id, transport_rate_id=c.transport_rate_id,
            ))
    session.flush()
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
        segments=[SegmentOut.model_validate(s) for s in segments], days=day_out,
    )
