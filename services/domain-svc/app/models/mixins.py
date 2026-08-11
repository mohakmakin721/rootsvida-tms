"""Shared provenance mixin for rate-bearing tables.

Principle 2 (Part 2 §1): every rate carries its source document, extractor
confidence, verifier, validity, and lifecycle state. This mixin gives all rate
tables (hotel/transport/activity/guide/misc) the same provenance surface so a
rate without provenance is structurally the exception, not the norm.

`source_document_id` is a nullable FK to `source_documents` (declared via
`declared_attr` so each rate table gets its own column + constraint). It stays
nullable: a rate may be staged before its source document is fully resolved.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.models.enums import PriceStatus, RateLifecycle, RateSource
from app.models.types import pg_enum


class ProvenanceMixin:
    """Provenance + trust-lifecycle columns for anything quotable."""

    # Pricing confidence + commercial origin (Phase 5, amends D-0001). `lifecycle`
    # above is the data-trust pipeline; these two say whether a number is safe to
    # quote and where it came from. Existing rows default to on_file / internal.
    price_status: Mapped[PriceStatus] = mapped_column(
        pg_enum(PriceStatus, "price_status"),
        nullable=False,
        default=PriceStatus.ON_FILE,
        server_default=PriceStatus.ON_FILE.value,
    )
    rate_source: Mapped[RateSource] = mapped_column(
        pg_enum(RateSource, "rate_source"),
        nullable=False,
        default=RateSource.INTERNAL,
        server_default=RateSource.INTERNAL.value,
    )

    @declared_attr
    def source_document_id(cls) -> Mapped[uuid.UUID | None]:  # noqa: N805
        return mapped_column(
            UUID(as_uuid=True),
            ForeignKey("source_documents.id"),
            nullable=True,
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
