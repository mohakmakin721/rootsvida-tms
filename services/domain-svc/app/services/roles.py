"""Roles service — seed the built-in roles, resolve a user's permissions, CRUD.

The owner role is special: `permissions_for_role` and `ensure_system_roles` both
force it to hold every permission, so the org can never be locked out of user
management no matter what is toggled in the UI. Everything else is data the owner
controls.
"""

from __future__ import annotations

import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Role, User
from app.models.enums import UserRole
from app.security.permissions import (
    ALL_PERMISSION_KEYS,
    COSTING_VIEW,
    INVOICES_MANAGE,
    MARKUP_MANAGE,
    QUOTES_ISSUE,
    SUPPLIERS_MANAGE,
    USERS_MANAGE,
)

# The built-in roles seeded for every org: key -> (label, description, permissions).
# Reproduces the pre-D-0015 hardcoded gates exactly.
DEFAULT_ROLES: dict[str, tuple[str, str, set[str]]] = {
    UserRole.OWNER.value: (
        "Owner",
        "Full access, including managing users and roles.",
        set(ALL_PERMISSION_KEYS),
    ),
    UserRole.OPS_MANAGER.value: (
        "Operations manager",
        "The supplier book, pricing, issuing quotes, costing and invoicing.",
        {SUPPLIERS_MANAGE, MARKUP_MANAGE, QUOTES_ISSUE, COSTING_VIEW, INVOICES_MANAGE},
    ),
    UserRole.SALES.value: (
        "Sales",
        "Build itineraries, price drafts and send proposals.",
        set(),
    ),
    UserRole.ACCOUNTS.value: (
        "Accounts",
        "Generate invoices and credit notes.",
        {INVOICES_MANAGE},
    ),
    UserRole.READONLY.value: (
        "Read only",
        "View-only access.",
        set(),
    ),
}

_OWNER = UserRole.OWNER.value


def ensure_system_roles(session: Session, org_id: uuid.UUID) -> None:
    """Idempotently seed the built-in roles for `org_id`. Existing non-owner roles
    are left untouched (the owner may have customised them); the owner role is
    always re-synced to hold every permission."""
    existing = {r.key: r for r in session.scalars(select(Role).where(Role.org_id == org_id))}
    for key, (label, description, perms) in DEFAULT_ROLES.items():
        role = existing.get(key)
        if role is None:
            session.add(Role(
                org_id=org_id, key=key, label=label, description=description,
                is_system=True, permissions=sorted(perms),
            ))
        elif key == _OWNER:
            role.permissions = sorted(ALL_PERMISSION_KEYS)
            role.is_system = True
    session.flush()


def permissions_for_role(session: Session, org_id: uuid.UUID, role_key: str) -> set[str]:
    """The permission set granted to `role_key` in `org_id`. The owner role always
    resolves to every permission; an unknown role grants nothing."""
    if role_key == _OWNER:
        return set(ALL_PERMISSION_KEYS)
    role = session.scalar(
        select(Role).where(Role.org_id == org_id, Role.key == role_key)
    )
    if role is None:
        return set()
    return set(role.permissions or [])


def _user_counts(session: Session, org_id: uuid.UUID) -> dict[str, int]:
    rows = session.execute(
        select(User.role, func.count())
        .where(User.org_id == org_id, User.deleted_at.is_(None))
        .group_by(User.role)
    ).all()
    return {role: count for role, count in rows}


def list_roles(session: Session, org_id: uuid.UUID) -> list[dict[str, object]]:
    """All roles for the org (system first, then alphabetical) with a live count of
    how many active users hold each."""
    counts = _user_counts(session, org_id)
    roles = session.scalars(
        select(Role)
        .where(Role.org_id == org_id)
        .order_by(Role.is_system.desc(), Role.label)
    ).all()
    return [
        {
            "id": r.id,
            "key": r.key,
            "label": r.label,
            "description": r.description,
            "is_system": r.is_system,
            "permissions": list(r.permissions or []),
            "user_count": counts.get(r.key, 0),
        }
        for r in roles
    ]


def admin_role_keys(session: Session, org_id: uuid.UUID) -> set[str]:
    """Role keys that can manage users (hold users.manage). Owner always qualifies."""
    keys = {_OWNER}
    for r in session.scalars(select(Role).where(Role.org_id == org_id)):
        if USERS_MANAGE in (r.permissions or []):
            keys.add(r.key)
    return keys


def remaining_admin_count(
    session: Session, org_id: uuid.UUID, *, excluding_user_id: uuid.UUID | None = None
) -> int:
    """How many active users would still be able to manage users if
    `excluding_user_id` were removed/demoted. Used to prevent org lockout."""
    keys = admin_role_keys(session, org_id)
    stmt = select(func.count()).where(
        User.org_id == org_id,
        User.role.in_(keys),
        User.is_active.is_(True),
        User.deleted_at.is_(None),
    )
    if excluding_user_id is not None:
        stmt = stmt.where(User.id != excluding_user_id)
    return session.scalar(stmt) or 0


def slugify_key(label: str) -> str:
    """Turn a role label into a stable snake_case key."""
    key = re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")
    return key or "role"
