"""Seed (or update) the initial organization.

Idempotent: keyed on slug. Later milestones (ingestion, review) need a valid
`org_id`; this provides it without hardcoding the company into business tables
(DECISIONS.md — org scoping). Run:  python scripts/seed_org.py
"""

from __future__ import annotations

import sys
from pathlib import Path

SVC_DIR = Path(__file__).resolve().parents[1] / "services" / "domain-svc"
sys.path.insert(0, str(SVC_DIR))

from app.config import get_settings
from app.db import get_session
from app.models import Organization
from sqlalchemy import select


def seed_org() -> None:
    settings = get_settings()
    gen = get_session()
    session = next(gen)
    try:
        org = session.scalar(
            select(Organization).where(Organization.slug == settings.rv_org_slug)
        )
        if org is None:
            org = Organization(name=settings.rv_org_name, slug=settings.rv_org_slug)
            session.add(org)
            session.flush()
            action = "created"
        else:
            org.name = settings.rv_org_name
            action = "already present (name synced)"
        print(f"Organization {action}: {org.slug} -> {org.id}")
        next(gen, None)  # trigger commit in the generator's finally/commit path
    finally:
        gen.close()


if __name__ == "__main__":
    seed_org()
