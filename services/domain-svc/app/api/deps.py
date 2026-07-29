"""Shared FastAPI dependencies.

`get_session` (from `app.db`) yields a request-scoped session that commits on
success and rolls back on error. `current_org_id` resolves the active tenant —
Phase 1 has one seeded org (real auth + per-user org lands in Phase 3, D-0002).
"""

from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.models import Organization


def current_org_id(session: Session = Depends(get_session)) -> uuid.UUID:
    slug = get_settings().rv_org_slug
    org_id = session.scalar(select(Organization.id).where(Organization.slug == slug))
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"organization {slug!r} not seeded — run scripts/seed_org.py",
        )
    return org_id
