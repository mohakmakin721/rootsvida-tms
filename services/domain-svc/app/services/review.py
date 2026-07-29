"""Review-queue domain logic (Milestone 8).

Enqueue candidates, list/fetch them, and record a human decision (approve /
reject / edit) with a full audit trail. Decisions are only valid on a *pending*
item — a second decision on the same item is a conflict, not a silent overwrite.

Applying an approved candidate to canonical tables is the *producer's*
responsibility (e.g. the dedup merge in M10, or future rate extraction): this
layer owns the decision and its provenance, not the downstream write. Functions
flush but never commit — the caller (the request session) owns the transaction.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RawImportRow, ReviewItem
from app.models.enums import RawParseStatus, ReviewEntityType, ReviewStatus


class ReviewStateError(Exception):
    """Raised when a decision is attempted on an already-decided item."""


def enqueue(
    session: Session,
    org_id: uuid.UUID,
    *,
    entity_type: ReviewEntityType,
    proposed: dict[str, Any],
    existing: dict[str, Any] | None = None,
    source_document_id: uuid.UUID | None = None,
    agent_run_id: uuid.UUID | None = None,
    confidence: float | None = None,
    dedupe_key: str | None = None,
) -> ReviewItem:
    """Add a candidate to the queue. Idempotent when `dedupe_key` is given: an
    existing item with the same (org, key) is returned untouched."""
    if dedupe_key is not None:
        existing_item = session.scalar(
            select(ReviewItem).where(
                ReviewItem.org_id == org_id, ReviewItem.dedupe_key == dedupe_key
            )
        )
        if existing_item is not None:
            return existing_item

    item = ReviewItem(
        org_id=org_id,
        entity_type=entity_type,
        proposed=proposed,
        existing=existing,
        source_document_id=source_document_id,
        agent_run_id=agent_run_id,
        confidence=confidence,
        dedupe_key=dedupe_key,
        status=ReviewStatus.PENDING,
    )
    session.add(item)
    session.flush()
    return item


def get_item(session: Session, org_id: uuid.UUID, item_id: uuid.UUID) -> ReviewItem | None:
    """Fetch one item, scoped to the org (returns None if absent/other-org)."""
    return session.scalar(
        select(ReviewItem).where(ReviewItem.org_id == org_id, ReviewItem.id == item_id)
    )


def list_items(
    session: Session,
    org_id: uuid.UUID,
    *,
    status: ReviewStatus | None = None,
    entity_type: ReviewEntityType | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ReviewItem]:
    """List items for an org, newest first, with optional status/type filters."""
    stmt = select(ReviewItem).where(ReviewItem.org_id == org_id)
    if status is not None:
        stmt = stmt.where(ReviewItem.status == status)
    if entity_type is not None:
        stmt = stmt.where(ReviewItem.entity_type == entity_type)
    stmt = stmt.order_by(ReviewItem.created_at.desc()).limit(limit).offset(offset)
    return list(session.scalars(stmt).all())


def _decide(
    session: Session,
    item: ReviewItem,
    new_status: ReviewStatus,
    reviewed_by: uuid.UUID | None,
    notes: str | None,
) -> ReviewItem:
    if item.status is not ReviewStatus.PENDING:
        raise ReviewStateError(
            f"item {item.id} is already {item.status.value}; cannot re-decide"
        )
    item.status = new_status
    item.reviewed_by = reviewed_by
    item.reviewed_at = datetime.now(UTC)
    item.reviewer_notes = notes
    session.flush()
    return item


def approve(
    session: Session, item: ReviewItem, reviewed_by: uuid.UUID | None = None,
    notes: str | None = None,
) -> ReviewItem:
    return _decide(session, item, ReviewStatus.APPROVED, reviewed_by, notes)


def reject(
    session: Session, item: ReviewItem, reviewed_by: uuid.UUID | None = None,
    notes: str | None = None,
) -> ReviewItem:
    return _decide(session, item, ReviewStatus.REJECTED, reviewed_by, notes)


def edit(
    session: Session,
    item: ReviewItem,
    proposed: dict[str, Any],
    reviewed_by: uuid.UUID | None = None,
    notes: str | None = None,
) -> ReviewItem:
    """Accept the candidate with human corrections: replace `proposed`, mark edited."""
    item.proposed = proposed
    return _decide(session, item, ReviewStatus.EDITED, reviewed_by, notes)


def enqueue_needs_review(session: Session, org_id: uuid.UUID) -> int:
    """Enqueue a supplier candidate for every staged row the migration could not
    identify (parse_status = needs_review). Idempotent per row (dedupe_key)."""
    rows = session.scalars(
        select(RawImportRow).where(
            RawImportRow.org_id == org_id,
            RawImportRow.parse_status == RawParseStatus.NEEDS_REVIEW,
        )
    ).all()
    created = 0
    for row in rows:
        key = f"needs_review:{row.id}"
        before = session.scalar(
            select(ReviewItem.id).where(
                ReviewItem.org_id == org_id, ReviewItem.dedupe_key == key
            )
        )
        if before is not None:
            continue
        enqueue(
            session,
            org_id,
            entity_type=ReviewEntityType.SUPPLIER,
            proposed={
                "sheet_name": row.sheet_name,
                "row_number": row.row_number,
                "raw_values": row.raw_values,
                "reason": "no usable name in source row",
            },
            source_document_id=row.source_document_id,
            dedupe_key=key,
        )
        created += 1
    return created
