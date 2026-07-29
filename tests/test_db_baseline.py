"""DB-backed tests for the Milestone 2 baseline.

Requires a reachable Postgres (skipped otherwise). Runs inside a rolled-back
transaction so it leaves no data behind.
"""

from __future__ import annotations

from app.models import Organization, User
from app.models.enums import UserRole
from sqlalchemy import text
from sqlalchemy.orm import Session


def test_extensions_installed(db_session: Session) -> None:
    rows = db_session.execute(
        text(
            "select extname from pg_extension "
            "where extname in ('pg_trgm','btree_gist','citext')"
        )
    ).scalars().all()
    assert {"pg_trgm", "btree_gist", "citext"} <= set(rows)


def test_user_role_enum_persists_lowercase_value(db_session: Session) -> None:
    """Regression guard: the DB must store the enum VALUE ('owner'), not the
    member NAME ('OWNER'). See app/models/types.pg_enum."""
    org = Organization(name="Test Org", slug="test-org-enum")
    db_session.add(org)
    db_session.flush()

    user = User(org_id=org.id, email="owner@example.com", role=UserRole.OWNER)
    db_session.add(user)
    db_session.flush()

    # Read the raw text of the enum column straight from Postgres.
    stored = db_session.execute(
        text("select role::text from users where id = :id"), {"id": user.id}
    ).scalar_one()
    assert stored == "owner"

    # And the ORM round-trips it back to the enum member.
    db_session.expire(user)
    assert user.role is UserRole.OWNER


def test_citext_email_is_case_insensitive(db_session: Session) -> None:
    org = Organization(name="CI Org", slug="ci-org")
    db_session.add(org)
    db_session.flush()
    db_session.add(User(org_id=org.id, email="Mixed@Case.com"))
    db_session.flush()

    found = db_session.execute(
        text("select count(*) from users where email = :e"),
        {"e": "mixed@case.com"},
    ).scalar_one()
    assert found == 1
