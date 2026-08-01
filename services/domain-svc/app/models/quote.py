"""Quotes — immutable by design (Part 2 §4.4).

A quote freezes its assumptions (GST, FX, rounding) and, on issue, a full
`pricing_snapshot` (every rate, pax count and rule used) plus the `engine_version`
that produced it. It is **never recomputed from live rates** afterwards — the
single most important data-integrity rule in the system. Immutability is enforced
by a DB trigger (see migration 0007), not merely by convention: an issued quote
can only move to 'superseded'; a correction is a new version.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, OrgScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import GstTreatment
from app.models.types import pg_enum


class Quote(UUIDPrimaryKeyMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "quotes"
    __table_args__ = (UniqueConstraint("project_id", "version"),)

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    itinerary_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("itineraries.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="draft"
    )  # draft|issued|accepted|expired|superseded

    # Frozen assumptions.
    gst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    gst_treatment: Mapped[GstTreatment] = mapped_column(
        pg_enum(GstTreatment, "gst_treatment"), nullable=False
    )
    # The client-facing currency and its rate. `fx_rate_inr_usd` holds INR per one
    # unit of `fx_currency` (the column name predates multi-currency support, M9).
    fx_currency: Mapped[str | None] = mapped_column(Text)
    fx_rate_inr_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fx_rate_locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # nearest_1 | gross_nearest_100
    rounding_policy: Mapped[str] = mapped_column(Text, nullable=False)

    # Computed outputs.
    total_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    total_taxable: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    total_tax: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    total_gross: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    margin_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    # The frozen snapshot + the engine version that produced it.
    pricing_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    engine_version: Mapped[str | None] = mapped_column(Text)

    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    issued_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    valid_until: Mapped[date | None] = mapped_column(Date)

    lines: Mapped[list[QuoteLine]] = relationship(back_populates="quote")


class QuoteLine(UUIDPrimaryKeyMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "quote_lines"

    quote_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quotes.id"), nullable=False)
    traveller_segment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("traveller_segments.id")
    )
    component_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("itinerary_components.id"))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    cost_per_pax: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    sell_per_pax: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    pax_count: Mapped[int | None] = mapped_column(Integer)
    line_total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))

    quote: Mapped[Quote] = relationship(back_populates="lines")
