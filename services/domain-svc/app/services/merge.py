"""Execute an approved supplier merge (Milestone 10).

Only ever called *after* a human approves a `merge_candidate` review item — the
plan forbids auto-merging (§1.3). The older supplier survives (chosen at detection
time); the duplicate's references are repointed to it and the duplicate is
soft-deleted, so nothing is destroyed and the merge is reversible by clearing
`deleted_at`. Idempotent: a merge whose duplicate is already soft-deleted is a
no-op.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import (
    ActivityRate,
    GuideRate,
    MiscCost,
    Rate,
    RawImportRow,
    ReviewItem,
    RoomType,
    Supplier,
    SupplierCommercials,
    SupplierContact,
    TransportRate,
)
from app.models.enums import ReviewEntityType

# Tables with a plain supplier_id FK, repointed wholesale from duplicate to primary.
_SUPPLIER_FK_MODELS = (
    SupplierContact,
    RoomType,
    Rate,
    TransportRate,
    ActivityRate,
    GuideRate,
    MiscCost,
)


class MergeError(Exception):
    """Raised when a merge cannot be applied (bad item, missing/other-org rows)."""


def apply_merge(session: Session, org_id: uuid.UUID, item: ReviewItem) -> dict[str, Any]:
    """Repoint the duplicate's references onto the primary and soft-delete it."""
    if item.entity_type is not ReviewEntityType.MERGE_CANDIDATE:
        raise MergeError(f"item {item.id} is not a merge candidate")

    try:
        primary_id = uuid.UUID(str(item.proposed["primary"]["id"]))
        dup_id = uuid.UUID(str(item.proposed["duplicate"]["id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise MergeError("merge candidate is missing primary/duplicate ids") from exc

    primary = session.get(Supplier, primary_id)
    duplicate = session.get(Supplier, dup_id)
    if primary is None or primary.org_id != org_id:
        raise MergeError("primary supplier not found in this org")
    if duplicate is None or duplicate.org_id != org_id:
        raise MergeError("duplicate supplier not found in this org")
    if duplicate.deleted_at is not None:
        return {"merged": False, "reason": "duplicate already merged"}

    for model in _SUPPLIER_FK_MODELS:
        session.execute(
            update(model).where(model.supplier_id == dup_id).values(supplier_id=primary_id)
        )
    session.execute(
        update(RawImportRow)
        .where(RawImportRow.normalized_supplier_id == dup_id)
        .values(normalized_supplier_id=primary_id)
    )
    # supplier_commercials is unique per supplier: only move it if the primary
    # has none (otherwise leave the duplicate's, which follows it into soft-delete).
    primary_has_commercials = session.scalar(
        select(SupplierCommercials.id).where(SupplierCommercials.supplier_id == primary_id)
    )
    if primary_has_commercials is None:
        session.execute(
            update(SupplierCommercials)
            .where(SupplierCommercials.supplier_id == dup_id)
            .values(supplier_id=primary_id)
        )

    duplicate.deleted_at = datetime.now(UTC)
    session.flush()
    return {"merged": True, "primary": str(primary_id), "duplicate": str(dup_id)}
