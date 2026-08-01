"""Security hardening — authentication is required app-wide and sensitive
endpoints are role-gated. Exercises the REAL auth stack (no dependency overrides
for current_user / current_org_id) with tokens minted for seeded users.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from app.db import get_session
from app.main import app
from app.models import Organization
from app.models.enums import UserRole
from app.services.auth import create_user, token_for
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


@pytest.fixture
def client(db_session: Session) -> Iterator[tuple[TestClient, str, str]]:
    from scripts.seed_org import seed_tax_rules

    org = Organization(name="Authz QA", slug=f"az-{uuid.uuid4().hex[:8]}",
                       gst_state_code="05", gst_state_name="Uttarakhand")
    db_session.add(org)
    db_session.flush()
    seed_tax_rules(db_session, org.id)
    owner = create_user(db_session, org.id, email="owner@az.local", password="pw",
                        role=UserRole.OWNER)
    readonly = create_user(db_session, org.id, email="ro@az.local", password="pw",
                           role=UserRole.READONLY)

    def _session() -> Iterator[Session]:
        yield db_session

    # Only the session is overridden — current_user / current_org_id run for real.
    app.dependency_overrides[get_session] = _session
    try:
        yield TestClient(app), token_for(owner), token_for(readonly)
    finally:
        app.dependency_overrides.clear()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_unauthenticated_requests_are_401(client: tuple[TestClient, str, str]) -> None:
    c, _, _ = client
    assert c.get("/api/v1/projects").status_code == 401
    assert c.get("/api/v1/suppliers").status_code == 401
    assert c.post("/api/v1/markup-rules", json={"label": "x", "rate": "0.1"}).status_code == 401


def test_bad_token_is_401(client: tuple[TestClient, str, str]) -> None:
    c, _, _ = client
    assert c.get("/api/v1/projects", headers=_auth("not-a-real-token")).status_code == 401


def test_authenticated_user_can_read(client: tuple[TestClient, str, str]) -> None:
    c, owner, readonly = client
    assert c.get("/api/v1/projects", headers=_auth(owner)).status_code == 200
    assert c.get("/api/v1/suppliers", headers=_auth(readonly)).status_code == 200


def test_readonly_is_forbidden_from_commercial_actions(client: tuple[TestClient, str, str]) -> None:
    c, owner, readonly = client
    body = {"label": "Foreign 15%", "basis": "markup_on_cost", "rate": "0.15"}
    # Readonly may not change markup policy…
    assert c.post("/api/v1/markup-rules", json=body, headers=_auth(readonly)).status_code == 403
    # …but an owner may.
    assert c.post("/api/v1/markup-rules", json=body, headers=_auth(owner)).status_code == 201


def test_login_flow(client: tuple[TestClient, str, str]) -> None:
    c, _, _ = client
    ok = c.post("/api/v1/auth/login", json={"email": "owner@az.local", "password": "pw"})
    assert ok.status_code == 200
    payload = ok.json()
    assert payload["token_type"] == "bearer"
    assert payload["user"]["role"] == "owner"
    # The freshly minted token works against a protected endpoint.
    assert c.get("/api/v1/projects", headers=_auth(payload["token"])).status_code == 200

    bad = c.post("/api/v1/auth/login", json={"email": "owner@az.local", "password": "nope"})
    assert bad.status_code == 401
