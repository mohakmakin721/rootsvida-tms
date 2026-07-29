"""Supplier core: suppliers, isolated commercials, contacts, room types.

Commission/margin live in a SEPARATE `supplier_commercials` table, not on
`suppliers` — the structural isolation approved in DECISIONS.md D-0002. Agent
tools and client-facing views never select from it; below-ops roles never read it.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    OrgScopedMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.models.enums import SupplierKind
from app.models.types import pg_enum


class Supplier(
    UUIDPrimaryKeyMixin, OrgScopedMixin, TimestampMixin, SoftDeleteMixin, Base
):
    __tablename__ = "suppliers"

    kind: Mapped[SupplierKind] = mapped_column(
        pg_enum(SupplierKind, "supplier_kind"), nullable=False
    )
    legal_name: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    destination_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("destinations.id")
    )
    gstin: Mapped[str | None] = mapped_column(Text)
    pan: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)  # Budget|Mid range|Luxury|...
    property_type: Mapped[str | None] = mapped_column(Text)  # Resort|Heritage|Camp|...
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="prospect"
    )  # prospect|contacted|active|blacklisted
    notes: Mapped[str | None] = mapped_column(Text)
    # NOTE: `embedding vector(1024)` (Part 2 §4.1) is deferred to the semantic-
    # search milestone so the schema applies without pgvector (DECISIONS.md D-0005).

    commercials: Mapped[SupplierCommercials | None] = relationship(
        back_populates="supplier", uselist=False
    )
    contacts: Mapped[list[SupplierContact]] = relationship(back_populates="supplier")
    room_types: Mapped[list[RoomType]] = relationship(back_populates="supplier")


class SupplierCommercials(
    UUIDPrimaryKeyMixin, OrgScopedMixin, TimestampMixin, Base
):
    """RESTRICTED. Owner/Ops-Manager only (Part 2 §8.3). One row per supplier."""

    __tablename__ = "supplier_commercials"
    __table_args__ = (UniqueConstraint("supplier_id"),)

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id"), nullable=False
    )
    commission_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    margin_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
    # e.g. verbatim "Give us good commission - Do not share with Hotel Owners".
    commission_notes: Mapped[str | None] = mapped_column(Text)
    criteria_of_shortlisting: Mapped[str | None] = mapped_column(Text)

    supplier: Mapped[Supplier] = relationship(back_populates="commercials")


class SupplierContact(UUIDPrimaryKeyMixin, OrgScopedMixin, TimestampMixin, Base):
    """Normalised contacts. Raw values preserved (Part 1 §1.1.3, plan §10)."""

    __tablename__ = "supplier_contacts"

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id"), nullable=False
    )
    person_name: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str | None] = mapped_column(Text)
    phone_e164: Mapped[str | None] = mapped_column(Text)
    phone_raw: Mapped[str | None] = mapped_column(Text)  # '9352604997\n87428 55465'
    email: Mapped[str | None] = mapped_column(CITEXT)
    website: Mapped[str | None] = mapped_column(Text)
    preferred_channel: Mapped[str | None] = mapped_column(Text)  # whatsapp|email|...
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    # 'via website', 'no reply so far' — never silently drop a contact.
    unusable_reason: Mapped[str | None] = mapped_column(Text)

    supplier: Mapped[Supplier] = relationship(back_populates="contacts")


class RoomType(UUIDPrimaryKeyMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "room_types"

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)  # 'Deluxe','Suite',...
    max_adults: Mapped[int] = mapped_column(nullable=False, server_default="2")
    max_children: Mapped[int] = mapped_column(nullable=False, server_default="1")
    extra_bed_allowed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    supplier: Mapped[Supplier] = relationship(back_populates="room_types")
