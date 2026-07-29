"""Transport rate model (Part 2 §4.2).

Pricing basis is a first-class enum from day one (Part 1 §1.2): the vendor sheets
already mix per-8hr/80km, per-km and per-extra-hour on the same agency block.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    OrgScopedMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.models.enums import TransportBasis
from app.models.mixins import ProvenanceMixin
from app.models.types import pg_enum


class TransportRate(
    UUIDPrimaryKeyMixin,
    OrgScopedMixin,
    ProvenanceMixin,
    TimestampMixin,
    SoftDeleteMixin,
    Base,
):
    __tablename__ = "transport_rates"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="amount_non_negative"),
        CheckConstraint("valid_to >= valid_from", name="valid_dates"),
    )

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id"), nullable=False
    )
    vehicle_class: Mapped[str] = mapped_column(Text, nullable=False)  # Sedan|SUV|...
    vehicle_model: Mapped[str | None] = mapped_column(Text)  # Dzire|Innova Crysta|...
    seats: Mapped[int | None] = mapped_column()
    basis: Mapped[TransportBasis] = mapped_column(
        pg_enum(TransportBasis, "transport_basis"), nullable=False
    )
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    origin_destination_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("destinations.id")
    )
    route_to_destination_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("destinations.id")
    )
    includes_driver_da: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    includes_fuel: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    includes_tolls: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date] = mapped_column(Date, nullable=False)
