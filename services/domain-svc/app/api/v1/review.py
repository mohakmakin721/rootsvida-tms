"""Review-queue REST endpoints (Milestone 8).

The API the review-queue UI (Milestone 9) is built against: list/fetch pending
candidates and record a decision. Producers enqueue via `POST /review-queue`
(or the bulk `POST /review-queue/import-staging`); a second decision on an
already-decided item returns 409.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import current_org_id
from app.db import get_session
from app.models import ReviewItem
from app.models.enums import ReviewEntityType, ReviewStatus
from app.services import review

router = APIRouter(prefix="/review-queue", tags=["review"])


class ReviewItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_type: ReviewEntityType
    status: ReviewStatus
    proposed: dict[str, Any]
    existing: dict[str, Any] | None
    source_document_id: uuid.UUID | None
    confidence: float | None
    dedupe_key: str | None
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    reviewer_notes: str | None
    created_at: datetime


class ReviewCreateIn(BaseModel):
    entity_type: ReviewEntityType
    proposed: dict[str, Any]
    existing: dict[str, Any] | None = None
    source_document_id: uuid.UUID | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    dedupe_key: str | None = None


class DecisionIn(BaseModel):
    reviewed_by: uuid.UUID | None = None
    notes: str | None = None


class EditIn(DecisionIn):
    proposed: dict[str, Any]


def _require(session: Session, org_id: uuid.UUID, item_id: uuid.UUID) -> ReviewItem:
    item = review.get_item(session, org_id, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="review item not found")
    return item


@router.get("", response_model=list[ReviewItemOut])
def list_review_items(
    status_filter: ReviewStatus | None = Query(default=None, alias="status"),
    entity_type: ReviewEntityType | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> list[ReviewItem]:
    return review.list_items(
        session, org_id, status=status_filter, entity_type=entity_type,
        limit=limit, offset=offset,
    )


@router.post("", response_model=ReviewItemOut, status_code=status.HTTP_201_CREATED)
def create_review_item(
    body: ReviewCreateIn,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> ReviewItem:
    return review.enqueue(session, org_id, **body.model_dump())


@router.post("/import-staging")
def import_staging(
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> dict[str, int]:
    """Bulk-enqueue supplier candidates for staged rows that need review."""
    return {"created": review.enqueue_needs_review(session, org_id)}


@router.get("/{item_id}", response_model=ReviewItemOut)
def get_review_item(
    item_id: uuid.UUID,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> ReviewItem:
    return _require(session, org_id, item_id)


@router.post("/{item_id}/approve", response_model=ReviewItemOut)
def approve_item(
    item_id: uuid.UUID,
    body: DecisionIn | None = None,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> ReviewItem:
    body = body or DecisionIn()
    item = _require(session, org_id, item_id)
    try:
        return review.approve(session, item, body.reviewed_by, body.notes)
    except review.ReviewStateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{item_id}/reject", response_model=ReviewItemOut)
def reject_item(
    item_id: uuid.UUID,
    body: DecisionIn | None = None,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> ReviewItem:
    body = body or DecisionIn()
    item = _require(session, org_id, item_id)
    try:
        return review.reject(session, item, body.reviewed_by, body.notes)
    except review.ReviewStateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{item_id}/edit", response_model=ReviewItemOut)
def edit_item(
    item_id: uuid.UUID,
    body: EditIn,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> ReviewItem:
    item = _require(session, org_id, item_id)
    try:
        return review.edit(session, item, body.proposed, body.reviewed_by, body.notes)
    except review.ReviewStateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
