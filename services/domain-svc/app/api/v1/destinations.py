"""Destination endpoints — searchable city list + create (for the type-aheads)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_org_id
from app.db import get_session
from app.models import Destination

router = APIRouter(prefix="/destinations", tags=["destinations"])


class DestinationIn(BaseModel):
    name: str
    state: str | None = None
    country: str = "IN"


class DestinationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    state: str | None
    country: str


@router.get("", response_model=list[DestinationOut])
def search_destinations(
    q: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> list[Destination]:
    stmt = select(Destination).where(Destination.org_id == org_id).order_by(Destination.name)
    if q:
        stmt = stmt.where(Destination.name.ilike(f"%{q.strip()}%"))
    return list(session.scalars(stmt.limit(limit)))


@router.post("", response_model=DestinationOut, status_code=status.HTTP_201_CREATED)
def create_destination(
    body: DestinationIn,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> Destination:
    # A city is innocuous reference data that itinerary-builders (incl. Sales, who
    # hold no manage permissions) create inline from the Day rows, so this needs only
    # authentication — not suppliers.manage. Reuse an existing city (case-insensitive)
    # instead of piling up duplicates.
    name = body.name.strip()
    existing = session.scalars(
        select(Destination).where(
            Destination.org_id == org_id, Destination.name.ilike(name)
        )
    ).first()
    if existing is not None:
        return existing
    dest = Destination(org_id=org_id, name=name,
                       state=(body.state or None), country=body.country or "IN")
    session.add(dest)
    session.flush()
    return dest
