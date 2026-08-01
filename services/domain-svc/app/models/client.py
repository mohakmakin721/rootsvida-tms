"""Client (buyer) records — the people and organisations trips are planned for.

A client is a first-class record (Phase 3 M8) so the builder can autopick an
existing client, group repeat business under one buyer, and carry forward the
free-text preferences the future agentic itinerary system will draw on. Projects
link to a client via `client_id`; one client can hold many projects (repeat trips).
"""

from __future__ import annotations

from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    OrgScopedMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.models.enums import ClientType
from app.models.types import pg_enum


class Client(
    UUIDPrimaryKeyMixin, OrgScopedMixin, TimestampMixin, SoftDeleteMixin, Base
):
    __tablename__ = "clients"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    client_type: Mapped[ClientType] = mapped_column(
        pg_enum(ClientType, "client_type"),
        nullable=False,
        server_default=ClientType.INDIVIDUAL.value,
    )
    country: Mapped[str | None] = mapped_column(Text)  # ISO-2, e.g. 'US'
    email: Mapped[str | None] = mapped_column(CITEXT)
    phone: Mapped[str | None] = mapped_column(Text)
    # Travel agent or company the booking comes through, if any.
    referral: Mapped[str | None] = mapped_column(Text)
    # Free-text preferences / interests / budget — raw material for the agentic
    # itinerary drafter (Phase 5). Human-owned; never priced from.
    notes: Mapped[str | None] = mapped_column(Text)
