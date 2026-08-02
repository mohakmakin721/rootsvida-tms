"""Shared FastAPI dependencies.

`get_session` (from `app.db`) yields a request-scoped session that commits on
success and rolls back on error. Authentication is required across the API:
`current_user` resolves the caller from their Bearer token, and `current_org_id`
derives the active tenant from that user — so every endpoint that depends on the
org is authenticated by construction. Sensitive endpoints additionally gate on
`require_permission(...)`, which resolves the caller's role → permission set
(D-0002 / D-0014 / D-0015 dynamic roles).
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
from app.security.tokens import TokenError, verify_token
from app.services import roles as roles_service

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


def require_permission(*permissions: str) -> Callable[..., User]:
    """Dependency factory: allow only callers whose role grants every listed
    permission. Roles are resolved per request from the DB (D-0015); the owner
    role always holds every permission."""
    needed = set(permissions)

    def _dep(
        user: User = Depends(current_user),
        session: Session = Depends(get_session),
    ) -> User:
        granted = roles_service.permissions_for_role(session, user.org_id, user.role)
        if not needed <= granted:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail=f"requires permission {sorted(needed)}",
            )
        return user

    return _dep
