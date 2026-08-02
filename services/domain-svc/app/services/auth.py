"""Authentication service — verify credentials, mint tokens, create users."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User
from app.models.enums import UserRole
from app.security.passwords import hash_password, verify_password
from app.security.tokens import create_token


def authenticate(session: Session, email: str, password: str) -> User | None:
    """Return the active user for these credentials, or None."""
    user = session.scalar(
        select(User).where(User.email == email, User.deleted_at.is_(None))
    )
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def token_for(user: User) -> str:
    settings = get_settings()
    return create_token(str(user.id), settings.rv_auth_secret,
                        settings.rv_auth_token_ttl_hours * 3600)


def create_user(
    session: Session,
    org_id: uuid.UUID,
    *,
    email: str,
    password: str,
    role: UserRole = UserRole.READONLY,
    name: str | None = None,
) -> User:
    """Create a user with a hashed password (org-scoped, unique email per org)."""
    user = User(
        org_id=org_id, email=email, name=name, role=role,
        password_hash=hash_password(password),
    )
    session.add(user)
    session.flush()
    return user


def change_password(session: Session, user: User, current: str, new: str) -> bool:
    """Change `user`'s password after verifying the current one. False if it's wrong."""
    if not verify_password(current, user.password_hash):
        return False
    user.password_hash = hash_password(new)
    session.flush()
    return True


def set_password(session: Session, user: User, new: str) -> None:
    """Set a password without the current one — for an owner resetting a teammate."""
    user.password_hash = hash_password(new)
    session.flush()
