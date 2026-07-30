"""Project endpoints — an enquiry is a project (holds itineraries + quotes)."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_org_id
from app.db import get_session
from app.models import Project

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectIn(BaseModel):
    code: str
    client_name: str
    client_country: str | None = None
    status: str = "enquiry"


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    client_name: str
    client_country: str | None
    status: str
    created_at: datetime


def _require(session: Session, org_id: uuid.UUID, project_id: uuid.UUID) -> Project:
    project = session.scalar(
        select(Project).where(Project.id == project_id, Project.org_id == org_id)
    )
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="project not found")
    return project


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    body: ProjectIn,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> Project:
    project = Project(org_id=org_id, **body.model_dump())
    session.add(project)
    session.flush()
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> list[Project]:
    return list(
        session.scalars(
            select(Project).where(Project.org_id == org_id).order_by(Project.created_at.desc())
        )
    )


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: uuid.UUID,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> Project:
    return _require(session, org_id, project_id)
