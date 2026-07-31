"""Itinerary assembly — build the nested itinerary graph from a draft payload.

Extracted from the itineraries router (Phase 3 M4) so both the persisting create
endpoint and the non-persisting pricing **preview** (M7) build the exact same
rows through one code path. The request schemas live here too; the router imports
them, and the preview endpoint reuses them so a draft prices identically whether
or not it is ever saved.

Segments are referenced by a client-chosen `key` so day-presence and components
can point at segments before the server assigns UUIDs.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.models import (
    DaySegmentPresence,
    Itinerary,
    ItineraryComponent,
    ItineraryDay,
    TravellerSegment,
)
from app.models.enums import AllocationBasis, ComponentKind, Occupancy, PaxClass


class KeyResolutionError(ValueError):
    """A day/component referenced a segment key that was never declared."""

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"unknown segment key {key!r}")


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


class ItineraryDraft(BaseModel):
    title: str
    start_date: date
    end_date: date
    generated_by: str | None = None
    segments: list[SegmentIn]
    days: list[DayIn] = []


def _resolve(keys: list[str], mapping: dict[str, uuid.UUID]) -> list[uuid.UUID]:
    try:
        return [mapping[k] for k in keys]
    except KeyError as exc:
        raise KeyResolutionError(exc.args[0]) from None


def build_itinerary(
    session: Session,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    draft: ItineraryDraft,
) -> Itinerary:
    """Persist the itinerary graph (segments, days, presence, components) and
    return the flushed `Itinerary`. Raises `KeyResolutionError` on a bad key."""
    itinerary = Itinerary(
        org_id=org_id, project_id=project_id, title=draft.title,
        start_date=draft.start_date, end_date=draft.end_date,
        generated_by=draft.generated_by,
    )
    session.add(itinerary)
    session.flush()

    key_to_id: dict[str, uuid.UUID] = {}
    for s in draft.segments:
        seg = TravellerSegment(
            org_id=org_id, itinerary_id=itinerary.id, label=s.label,
            pax_class=s.pax_class, occupancy=s.occupancy, pax_count=s.pax_count,
            markup_rule_id=s.markup_rule_id,
        )
        session.add(seg)
        session.flush()
        key_to_id[s.key] = seg.id

    for d in draft.days:
        day = ItineraryDay(
            org_id=org_id, itinerary_id=itinerary.id, day_number=d.day_number,
            date=d.date, destination_id=d.destination_id, narrative=d.narrative,
        )
        session.add(day)
        session.flush()
        for seg_id in _resolve(d.present_segment_keys, key_to_id):
            session.add(DaySegmentPresence(
                org_id=org_id, itinerary_day_id=day.id, traveller_segment_id=seg_id
            ))
        for c in d.components:
            applies = _resolve(c.applies_to_segment_keys or [], key_to_id)
            session.add(ItineraryComponent(
                org_id=org_id, itinerary_day_id=day.id, kind=c.kind,
                description=c.description, override_amount=c.override_amount,
                override_reason=c.override_reason, allocation=c.allocation,
                applies_to_segment_ids=applies or None,
                applies_to_pax_class=c.applies_to_pax_class, supplier_id=c.supplier_id,
                rate_id=c.rate_id, transport_rate_id=c.transport_rate_id,
            ))
    session.flush()
    return itinerary
