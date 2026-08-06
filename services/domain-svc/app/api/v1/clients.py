"""Client endpoints — the buyer book behind the builder's intake (Phase 3 M8).

Search powers the client autopicker; a client's projects power the project-code
continuity suggestions (is this a repeat trip for an existing buyer, or a new
one?). Creating a client here, or inline when a project is created, saves the full
record the future agentic itinerary system will read.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_org_id
from app.db import get_session
from app.models import Client, Project
from app.models.enums import ClientType

router = APIRouter(prefix="/clients", tags=["clients"])


class ClientIn(BaseModel):
    name: str
    client_type: ClientType = ClientType.INDIVIDUAL
    corporate_name: str | None = None
    country: str | None = None
    email: str | None = None
    phone: str | None = None
    referral: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _corporate_needs_name(self) -> ClientIn:
        if self.client_type is ClientType.CORPORATE and not (self.corporate_name or "").strip():
            raise ValueError("Corporate name is required for a corporate client.")
        return self


class ClientSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    client_type: ClientType
    corporate_name: str | None = None
    country: str | None
    email: str | None
    phone: str | None
    referral: str | None
    notes: str | None
    project_count: int = 0


class ProjectBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    status: str
    created_at: datetime


class ClientDetail(ClientSummary):
    projects: list[ProjectBrief] = []


def _project_count(session: Session, org_id: uuid.UUID, client_id: uuid.UUID) -> int:
    return session.scalar(
        select(func.count()).select_from(Project).where(
            Project.org_id == org_id, Project.client_id == client_id
        )
    ) or 0


@router.get("", response_model=list[ClientSummary])
def search_clients(
    q: str | None = Query(default=None, description="Search by name"),
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> list[ClientSummary]:
    stmt = (
        select(Client, func.count(Project.id))
        .outerjoin(Project, Project.client_id == Client.id)
        .where(Client.org_id == org_id, Client.deleted_at.is_(None))
        .group_by(Client.id)
        .order_by(Client.name)
        .limit(limit)
    )
    if q:
        stmt = stmt.where(Client.name.ilike(f"%{q.strip()}%"))
    out: list[ClientSummary] = []
    for client, count in session.execute(stmt).all():
        summary = ClientSummary.model_validate(client)
        summary.project_count = count
        out.append(summary)
    return out


@router.post("", response_model=ClientSummary, status_code=status.HTTP_201_CREATED)
def create_client(
    body: ClientIn,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> ClientSummary:
    client = Client(org_id=org_id, **body.model_dump())
    session.add(client)
    session.flush()
    return ClientSummary.model_validate(client)


@router.get("/{client_id}", response_model=ClientDetail)
def get_client(
    client_id: uuid.UUID,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> ClientDetail:
    client = session.scalar(
        select(Client).where(Client.id == client_id, Client.org_id == org_id)
    )
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="client not found")
    projects = list(session.scalars(
        select(Project).where(Project.org_id == org_id, Project.client_id == client_id)
        .order_by(Project.created_at.desc())
    ))
    detail = ClientDetail.model_validate(client)
    detail.project_count = len(projects)
    detail.projects = [ProjectBrief.model_validate(p) for p in projects]
    return detail
