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


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    # Seller GST identity — drives place-of-supply (Part 2 §1.4, invoice §1.4).
    # RootsVida: GSTIN 05AANCR1978G1Z1, Uttarakhand (state code 05), PAN AANCR1978G.
    gstin: Mapped[str | None] = mapped_column(Text)
    pan: Mapped[str | None] = mapped_column(Text)
    gst_state_code: Mapped[str | None] = mapped_column(Text)  # '05'
    gst_state_name: Mapped[str | None] = mapped_column(Text)  # 'Uttarakhand'

    users: Mapped[list[User]] = relationship(back_populates="org")


class User(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("org_id", "email"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    name: Mapped[str | None] = mapped_column(Text)
    # A role's `key` (see app.models.role.Role). Roles are dynamic/DB-backed
    # (D-0015); this is plain text, not the old fixed `user_role` enum.
    role: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=UserRole.READONLY.value,
        server_default=UserRole.READONLY.value,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    # PBKDF2 hash (`pbkdf2_sha256$iters$salt$hash`); NULL = cannot log in yet.
    # Self-hosted auth, no external service (D-0014).
    password_hash: Mapped[str | None] = mapped_column(Text)

    org: Mapped[Organization] = relationship(back_populates="users")
