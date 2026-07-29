"""Organization (tenant) and user models — the org-scoping foundation.

Every business table carries `org_id` (added from Milestone 3) so PostgreSQL
Row-Level Security can be switched on in Phase 3 without a schema rewrite
(DECISIONS.md D-0002). The initial org is seeded from `RV_ORG_NAME`/`RV_ORG_SLUG`.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import UserRole
from app.models.types import pg_enum


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)

    users: Mapped[list[User]] = relationship(back_populates="org")


class User(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("org_id", "email"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    name: Mapped[str | None] = mapped_column(Text)
    role: Mapped[UserRole] = mapped_column(
        pg_enum(UserRole, "user_role"),
        nullable=False,
        default=UserRole.READONLY,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    org: Mapped[Organization] = relationship(back_populates="users")
