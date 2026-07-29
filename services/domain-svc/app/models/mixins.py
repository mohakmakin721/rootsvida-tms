"""Shared provenance mixin for rate-bearing tables.

Principle 2 (Part 2 §1): every rate carries its source document, extractor
confidence, verifier, validity, and lifecycle state. This mixin gives all rate
tables (hotel/transport/activity/guide/misc) the same provenance surface so a
rate without provenance is structurally the exception, not the norm.

`source_document_id` is a plain nullable column here; its FK to `source_documents`
is added in Milestone 4, when that table exists (expand-then-contract).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.models.enums import RateLifecycle
from app.models.types import pg_enum


class ProvenanceMixin:
    """Provenance + trust-lifecycle columns for anything quotable."""

    # FK constraint to source_documents added in Milestone 4.
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    raw_source_text: Mapped[str | None] = mapped_column(Text)
    extraction_confidence: Mapped[float | None] = mapped_column(Numeric(3, 2))
    lifecycle: Mapped[RateLifecycle] = mapped_column(
        pg_enum(RateLifecycle, "rate_lifecycle"),
        nullable=False,
        default=RateLifecycle.CANDIDATE,
        server_default=RateLifecycle.CANDIDATE.value,
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @declared_attr
    def verified_by(cls) -> Mapped[uuid.UUID | None]:  # noqa: N805
        return mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
