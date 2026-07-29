"""Review queue — the single human gate between candidate data and canonical
truth (Part 2 §4.6, §8.4).

Everything on the untrusted/extraction path and the bulk-migration path produces
*candidates* here; a human approves, edits, or rejects them. Nothing auto-writes
to `rates`/`quotes`/`invoices`. Each item keeps the `proposed` payload (and, for
updates/merges, the `existing` snapshot), its provenance, a confidence, and — once
decided — who decided, when, and why.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, OrgScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ReviewEntityType, ReviewStatus
from app.models.types import pg_enum


class ReviewItem(UUIDPrimaryKeyMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "review_queue"
    # A producer may set `dedupe_key` so re-running it upserts one item per target
    # (plan §29) instead of piling up duplicates. NULL keys are unconstrained.
    __table_args__ = (UniqueConstraint("org_id", "dedupe_key"),)

    entity_type: Mapped[ReviewEntityType] = mapped_column(
        pg_enum(ReviewEntityType, "review_entity_type"), nullable=False
    )
    proposed: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    existing: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_documents.id")
    )
    # FK to agent_runs is deferred to the agent layer (Phase 5); the column exists
    # now so extraction runs can be attributed without a later schema change.
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column()
    confidence: Mapped[float | None] = mapped_column(Numeric(3, 2))
    status: Mapped[ReviewStatus] = mapped_column(
        pg_enum(ReviewStatus, "review_status"),
        nullable=False,
        default=ReviewStatus.PENDING,
        server_default=ReviewStatus.PENDING.value,
    )
    dedupe_key: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewer_notes: Mapped[str | None] = mapped_column(Text)
