"""Project endpoints — an enquiry is a project (holds itineraries + quotes).

A project can be created against an existing client (`client_id`) or with an
inline new client (`client`), which is saved to the client book (M8). Either way
`client_name` is stored as a denormalised snapshot. `GET /projects?code=` powers
the builder's "is this code already taken / a repeat project?" check.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_org_id
from app.api.v1.clients import ClientIn
from app.db import get_session
from app.models import Client, Project, ProjectMilestone
from app.models.enums import ProjectStatus

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectIn(BaseModel):
    code: str
    status: str = "enquiry"
    # Provide exactly one buyer identity: an existing client_id, an inline new
    # `client`, or a bare client_name (legacy / quick draft).
    client_id: uuid.UUID | None = None
    client: ClientIn | None = None
    client_name: str | None = None
    client_country: str | None = None

    @model_validator(mode="after")
    def _needs_a_client(self) -> ProjectIn:
        if self.client_id is None and self.client is None and not self.client_name:
            raise ValueError("provide client_id, client, or client_name")
        return self


class ProjectUpdate(BaseModel):
    status: ProjectStatus | None = None
    travel_start: date | None = None
    travel_end: date | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    client_id: uuid.UUID | None
    client_name: str
    client_country: str | None
    status: str
    status_changed_at: datetime | None
    travel_start: date | None
    travel_end: date | None
    created_at: datetime


class MilestoneIn(BaseModel):
    kind: str = "note"  # payment|payment_deadline|invoice|note
    title: str
    done: bool = False
    due_date: date | None = None
    amount: Decimal | None = None
    notes: str | None = None


class MilestoneUpdate(BaseModel):
    kind: str | None = None
    title: str | None = None
    due_date: date | None = None
    amount: Decimal | None = None
    done: bool | None = None
    notes: str | None = None


class MilestoneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    kind: str
    title: str
    due_date: date | None
    amount: Decimal | None
    done: bool
    notes: str | None


def _require(session: Session, org_id: uuid.UUID, project_id: uuid.UUID) -> Project:
    project = session.scalar(
        select(Project).where(Project.id == project_id, Project.org_id == org_id)
    )
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="project not found")
    return project


def _resolve_client(
    session: Session, org_id: uuid.UUID, body: ProjectIn
) -> tuple[uuid.UUID | None, str, str | None]:
    """Return (client_id, client_name snapshot, client_country) for the project."""
    if body.client_id is not None:
        client = session.scalar(
            select(Client).where(Client.id == body.client_id, Client.org_id == org_id)
        )
        if client is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="client not found")
        return client.id, client.name, client.country
    if body.client is not None:
        client = Client(org_id=org_id, **body.client.model_dump())
        session.add(client)
        session.flush()
        return client.id, client.name, client.country
    # Legacy: a bare name with no saved client record.
    assert body.client_name is not None
    return None, body.client_name, body.client_country


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    body: ProjectIn,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> Project:
    client_id, client_name, client_country = _resolve_client(session, org_id, body)
    existing = session.scalar(
        select(Project).where(Project.org_id == org_id, Project.code == body.code)
    )
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=f"project code {body.code!r} already exists"
        )
    project = Project(
        org_id=org_id, code=body.code, status=body.status, client_id=client_id,
        client_name=client_name, client_country=client_country,
    )
    session.add(project)
    session.flush()
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(
    code: str | None = Query(default=None),
    client_id: uuid.UUID | None = Query(default=None),
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> list[Project]:
    stmt = select(Project).where(Project.org_id == org_id)
    if code is not None:
        stmt = stmt.where(Project.code == code)
    if client_id is not None:
        stmt = stmt.where(Project.client_id == client_id)
    return list(session.scalars(stmt.order_by(Project.created_at.desc())))


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: uuid.UUID,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> Project:
    return _require(session, org_id, project_id)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> Project:
    """Advance the project's status and/or set its travel window. Changing the
    status stamps `status_changed_at` so the timeline records when it moved."""
    project = _require(session, org_id, project_id)
    patch = body.model_dump(exclude_unset=True)
    if "status" in patch and patch["status"] is not None:
        new_status = ProjectStatus(patch["status"]).value
        if new_status != project.status:
            project.status = new_status
            project.status_changed_at = datetime.now(UTC)
    if "travel_start" in patch:
        project.travel_start = patch["travel_start"]
    if "travel_end" in patch:
        project.travel_end = patch["travel_end"]
    session.flush()
    return project


# --------------------------------------------------------------------------- #
# timeline milestones
# --------------------------------------------------------------------------- #


def _require_milestone(
    session: Session, org_id: uuid.UUID, milestone_id: uuid.UUID
) -> ProjectMilestone:
    m = session.scalar(
        select(ProjectMilestone).where(
            ProjectMilestone.id == milestone_id, ProjectMilestone.org_id == org_id
        )
    )
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="milestone not found")
    return m


@router.get("/{project_id}/milestones", response_model=list[MilestoneOut])
def list_milestones(
    project_id: uuid.UUID,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> list[ProjectMilestone]:
    _require(session, org_id, project_id)
    return list(session.scalars(
        select(ProjectMilestone)
        .where(ProjectMilestone.project_id == project_id)
        .order_by(ProjectMilestone.due_date.is_(None), ProjectMilestone.due_date)
    ))


@router.post("/{project_id}/milestones", response_model=MilestoneOut,
             status_code=status.HTTP_201_CREATED)
def create_milestone(
    project_id: uuid.UUID,
    body: MilestoneIn,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> ProjectMilestone:
    _require(session, org_id, project_id)
    milestone = ProjectMilestone(org_id=org_id, project_id=project_id, **body.model_dump())
    session.add(milestone)
    session.flush()
    return milestone


@router.patch("/milestones/{milestone_id}", response_model=MilestoneOut)
def update_milestone(
    milestone_id: uuid.UUID,
    body: MilestoneUpdate,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> ProjectMilestone:
    milestone = _require_milestone(session, org_id, milestone_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(milestone, field, value)
    session.flush()
    return milestone


@router.delete("/milestones/{milestone_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_milestone(
    milestone_id: uuid.UUID,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> None:
    milestone = _require_milestone(session, org_id, milestone_id)
    session.delete(milestone)
    session.flush()
