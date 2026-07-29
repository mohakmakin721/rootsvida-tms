"""Miscellaneous cost model (plan §22).

Location extras, permits, local services, special charges. The allocation basis
is modelled now (All Pax / by class / per segment / per pax / fixed group), but
the pricing engine that *uses* it is Phase 2 — not built here.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import CHAR, CheckConstraint, Date, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    OrgScopedMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.models.enums import AllocationBasis
from app.models.mixins import ProvenanceMixin
from app.models.types import pg_enum


class MiscCost(
    UUIDPrimaryKeyMixin,
    OrgScopedMixin,
    ProvenanceMixin,
    TimestampMixin,
    SoftDeleteMixin,
    Base,
):
    __tablename__ = "misc_costs"
    __table_args__ = (
        CheckConstraint("amount IS NULL OR amount >= 0", name="amount_non_negative"),
        CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
            name="valid_dates",
        ),
    )

    supplier_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("suppliers.id"))
    destination_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("destinations.id")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[float | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, server_default="INR")
    allocation: Mapped[AllocationBasis] = mapped_column(
        pg_enum(AllocationBasis, "allocation_basis"),
        nullable=False,
        server_default=AllocationBasis.ALL_PAX.value,
    )
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
