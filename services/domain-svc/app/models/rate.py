"""Hotel rate model (Part 2 §4.1) — the heart of the canonical data.

Carries structured pricing (meal plan, occupancy, tax basis), a validity window,
full provenance, and an exclusion constraint that makes two conflicting rates for
the same room/plan/occupancy on overlapping dates structurally impossible.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, DATERANGE, ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    OrgScopedMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.models.enums import MealPlan, Occupancy, TaxBasis
from app.models.mixins import ProvenanceMixin
from app.models.supplier import Supplier
from app.models.types import pg_enum


class Rate(
    UUIDPrimaryKeyMixin,
    OrgScopedMixin,
    ProvenanceMixin,
    TimestampMixin,
    SoftDeleteMixin,
    Base,
):
    __tablename__ = "rates"
    __table_args__ = (
        CheckConstraint("valid_to >= valid_from", name="valid_dates"),
        CheckConstraint("amount >= 0", name="amount_non_negative"),
        Index(
            "ix_rates_lookup",
            "supplier_id", "meal_plan", "occupancy", "valid_from", "valid_to",
        ),
        # Two conflicting rates for the same room/plan/occupancy on overlapping
        # dates cannot coexist (Part 2 §4.1 — "the quiet hero").
        ExcludeConstraint(
            ("supplier_id", "="),
            ("room_type_id", "="),
            ("meal_plan", "="),
            ("occupancy", "="),
            (text("daterange(valid_from, valid_to, '[]')"), "&&"),
            using="gist",
            where=text("deleted_at IS NULL"),
            name="rates_no_overlap",
        ),
    )

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id"), nullable=False
    )
    room_type_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("room_types.id")
    )
    meal_plan: Mapped[MealPlan] = mapped_column(
        pg_enum(MealPlan, "meal_plan"), nullable=False
    )
    occupancy: Mapped[Occupancy] = mapped_column(
        pg_enum(Occupancy, "occupancy"), nullable=False
    )
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, server_default="INR")
    tax_basis: Mapped[TaxBasis] = mapped_column(
        pg_enum(TaxBasis, "tax_basis"),
        nullable=False,
        server_default=TaxBasis.GROSS_OF_TAX.value,
    )
    tax_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date] = mapped_column(Date, nullable=False)
    season_label: Mapped[str | None] = mapped_column(Text)
    min_nights: Mapped[int] = mapped_column(nullable=False, server_default="1")
    blackout_dates: Mapped[list[Any] | None] = mapped_column(ARRAY(DATERANGE))
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rates.id"))

    supplier: Mapped[Supplier] = relationship()
