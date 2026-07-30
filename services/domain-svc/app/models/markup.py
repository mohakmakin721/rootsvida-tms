"""Markup rules — stored markup policy referenced by traveller segments.

The DB counterpart of the pure engine's `pricing.model.MarkupRule`. A segment
points at one of these (e.g. "Foreign 15%", "Indian 10%"); the pricing bridge
adapts it into the engine's rule at quote time.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, Numeric, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, OrgScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import MarkupBasis
from app.models.types import pg_enum


class MarkupRule(UUIDPrimaryKeyMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "markup_rules"
    __table_args__ = (UniqueConstraint("org_id", "label"),)

    label: Mapped[str] = mapped_column(Text, nullable=False)  # 'Foreign 15%'
    basis: Mapped[MarkupBasis] = mapped_column(
        pg_enum(MarkupBasis, "markup_basis"),
        nullable=False,
        server_default=MarkupBasis.MARKUP_ON_COST.value,
    )
    rate: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)  # 0.1500
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
