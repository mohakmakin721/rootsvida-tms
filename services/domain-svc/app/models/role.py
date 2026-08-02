"""Role model — a named, org-scoped bundle of permissions (D-0015).

Roles were originally a fixed PG enum on `users.role`. They are now data: the owner
can create custom role types and toggle each role's permissions in the UI. The five
built-ins (owner, ops_manager, sales, accounts, readonly) are seeded as `is_system`
roles; the owner role always holds every permission (a safety invariant enforced in
`app.services.roles`). A user's `role` column stores a role's `key`.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, OrgScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Role(UUIDPrimaryKeyMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("org_id", "key"),)

    key: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    permissions: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
