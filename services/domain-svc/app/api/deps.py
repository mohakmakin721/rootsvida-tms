"""Shared FastAPI dependencies.

`get_session` (from `app.db`) yields a request-scoped session that commits on
success and rolls back on error. `current_org_id` resolves the active tenant —
Phase 1 has one seeded org (real auth + per-user org lands in Phase 3, D-0002).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.models import Organization, User
from app.models.enums import UserRole
from app.security.tokens import TokenError, verify_token

_bearer = HTTPBearer(auto_error=False)


def current_org_id(session: Session = Depends(get_session)) -> uuid.UUID:
    slug = get_settings().rv_org_slug
    org_id = session.scalar(select(Organization.id).where(Organization.slug == slug))
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"organization {slug!r} not seeded — run scripts/seed_org.py",
        )
    return org_id


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: Session = Depends(get_session),
) -> User:
    """Resolve the authenticated user from the Bearer token, or 401."""
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="not authenticated",
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        subject = verify_token(credentials.credentials, get_settings().rv_auth_secret)
        user = session.get(User, uuid.UUID(subject))
    except (TokenError, ValueError):
        user = None
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid or expired token",
                            headers={"WWW-Authenticate": "Bearer"})
    return user


def require_role(*roles: UserRole) -> Callable[[User], User]:
    """Dependency factory: allow only users whose role is in `roles`."""
    allowed = {r.value for r in roles}

    def _dep(user: User = Depends(current_user)) -> User:
        if user.role.value not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                detail=f"requires role in {sorted(allowed)}")
        return user

    return _dep
