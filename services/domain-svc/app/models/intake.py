"""Itinerary intake (Phase 5) — the structured client brief the drafter works from.

Captured during a client call, either typed manually or parsed from a pasted form
response (the two Google intake forms map onto these fields). The rule engine reads
the structured columns to derive per-client priority weights and rank candidates;
`raw` keeps the full original blob (contact/meta and anything not modelled) and
`priority_weights` stores the derived + owner-overridden weight vector.

An intake may exist before a project/client is created, then be linked — both FKs
are nullable. Nothing here is priced or published on its own (D-0001 / review gate).
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import Date, ForeignKey, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    OrgScopedMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.models.enums import PaxClass
from app.models.types import pg_enum


class ItineraryIntake(
    UUIDPrimaryKeyMixin, OrgScopedMixin, TimestampMixin, SoftDeleteMixin, Base
):
    __tablename__ = "itinerary_intakes"

    # Linkage — both nullable; an intake can precede the project/client it feeds.
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"))
    client_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clients.id"))

    # --- trip brief (rule-engine inputs) ---
    destination: Mapped[str | None] = mapped_column(Text)
    group_size: Mapped[int | None] = mapped_column(Integer)
    themes: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    duration_days: Mapped[int | None] = mapped_column(Integer)
    travel_start: Mapped[date | None] = mapped_column(Date)
    travel_end: Mapped[date | None] = mapped_column(Date)
    # Accommodation preference (hostel / homestay / budget_hotel / luxury_hotel /
    # other). Free text, not an enum, because the form allows "Other".
    tier: Mapped[str | None] = mapped_column(Text)
    budget_inr: Mapped[float | None] = mapped_column(Numeric(14, 2))
    pax_class: Mapped[PaxClass | None] = mapped_column(pg_enum(PaxClass, "pax_class"))
    nationality: Mapped[str | None] = mapped_column(Text)
    age_band: Mapped[str | None] = mapped_column(Text)  # 18-24 / 25-40 / 40+ / other
    transport: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    service_types: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    must_include: Mapped[str | None] = mapped_column(Text)
    must_exclude: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)  # special requests

    # Derived (rule engine) + owner-overridden priority weights, e.g.
    # {"experience_match": 35, "budget_fit": 15, ...}. Null until computed.
    priority_weights: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # Full original intake (contact/meta + anything not modelled above).
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
