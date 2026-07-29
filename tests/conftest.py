"""Shared pytest fixtures and import-path setup.

Puts the domain service and ingestion packages on sys.path so tests can import
them without an install step (mirrors how Alembic's env.py resolves the app).
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SVC_DIR = REPO_ROOT / "services" / "domain-svc"

for p in (str(SVC_DIR), str(REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest
from sqlalchemy.orm import Session


def _db_reachable() -> bool:
    """True if the configured Postgres accepts a connection."""
    from app.db import get_engine
    from sqlalchemy import text

    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 — any connection failure means "skip DB tests"
        return False


@pytest.fixture
def db_session() -> Iterator[Session]:
    """A session wrapped in a transaction that is rolled back after the test.

    Skips the test when no database is reachable, so the suite still runs (and
    the DB-free smoke tests pass) on a machine without Postgres.
    """
    if not _db_reachable():
        pytest.skip("no database reachable (set DATABASE_URL / start docker compose)")

    from app.db import get_engine

    connection = get_engine().connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
