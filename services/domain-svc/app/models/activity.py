"""Activity and guide rate models (Part 2 §4.2).

Nationality-differentiated pricing is structural: monument/activity tickets are
stored as separate `pax_class` rows (Indian vs foreign), not a single figure with
a note (Part 1 §1.3).
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    OrgScopedMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.models.enums import PaxClass
from app.models.mixins import ProvenanceMixin
from app.models.types import pg_enum


class ActivityRate(
    UUIDPrimaryKeyMixin,
    OrgScopedMixin,
    ProvenanceMixin,
    TimestampMixin,
    SoftDeleteMixin,
    Base,
):
    """Monuments, experiences, permits — priced per pax and per nationality."""

    __tablename__ = "activity_rates"
    __table_args__ = (
        CheckConstraint("price_per_pax >= 0", name="price_non_negative"),
        CheckConstraint("valid_to >= valid_from", name="valid_dates"),
    )

    destination_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("destinations.id")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)  # 'Amber Fort','Taj Mahal'
    pax_class: Mapped[PaxClass] = mapped_column(
        pg_enum(PaxClass, "pax_class"), nullable=False
    )
    price_per_pax: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    child_price: Mapped[float | None] = mapped_column(Numeric(14, 2))
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("suppliers.id"))
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date] = mapped_column(Date, nullable=False)


class GuideRate(
    UUIDPrimaryKeyMixin,
    OrgScopedMixin,
    ProvenanceMixin,
    TimestampMixin,
    SoftDeleteMixin,
    Base,
):
    __tablename__ = "guide_rates"
    __table_args__ = (
        CheckConstraint("valid_to >= valid_from", name="valid_dates"),
    )

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id"), nullable=False
    )
    destination_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("destinations.id")
    )
    languages: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    per_day: Mapped[float | None] = mapped_column(Numeric(14, 2))
    per_half_day: Mapped[float | None] = mapped_column(Numeric(14, 2))
    specialisation: Mapped[str | None] = mapped_column(Text)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date] = mapped_column(Date, nullable=False)
