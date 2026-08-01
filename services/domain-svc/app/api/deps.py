"""Shared FastAPI dependencies.

`get_session` (from `app.db`) yields a request-scoped session that commits on
success and rolls back on error. Authentication is required across the API:
`current_user` resolves the caller from their Bearer token, and `current_org_id`
derives the active tenant from that user — so every endpoint that depends on the
org is authenticated by construction. Sensitive endpoints additionally gate on
`require_role(...)`. (D-0002 / D-0014.)
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.models import User
from app.models.enums import UserRole
from app.security.tokens import TokenError, verify_token

_bearer = HTTPBearer(auto_error=False)


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


def current_org_id(user: User = Depends(current_user)) -> uuid.UUID:
    """The active tenant — the authenticated user's org. Requiring this dependency
    therefore requires authentication (a valid Bearer token)."""
    return user.org_id


def require_role(*roles: UserRole) -> Callable[[User], User]:
    """Dependency factory: allow only users whose role is in `roles`."""
    allowed = {r.value for r in roles}

    def _dep(user: User = Depends(current_user)) -> User:
        if user.role.value not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                detail=f"requires role in {sorted(allowed)}")
        return user

    return _dep
