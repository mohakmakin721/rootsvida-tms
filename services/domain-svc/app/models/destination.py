"""Destination reference data (Part 2 §4.1)."""

from __future__ import annotations

from sqlalchemy import Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, OrgScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Destination(UUIDPrimaryKeyMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "destinations"
    __table_args__ = (
        UniqueConstraint("org_id", "name", "state", "country"),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)  # 'Jaipur'
    state: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str] = mapped_column(Text, nullable=False, default="IN")
    lat: Mapped[float | None] = mapped_column(Numeric(9, 6))
    lng: Mapped[float | None] = mapped_column(Numeric(9, 6))
    # 'Kerela' -> 'Kerala'; used for fuzzy destination resolution during ingest.
    aliases: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
