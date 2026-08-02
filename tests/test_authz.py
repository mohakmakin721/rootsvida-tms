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


def test_owner_manages_users(client: tuple[TestClient, str, str]) -> None:
    c, owner, readonly = client
    listed = c.get("/api/v1/auth/users", headers=_auth(owner))
    assert listed.status_code == 200
    users = {u["email"]: u for u in listed.json()}
    assert {"owner@az.local", "ro@az.local"} <= set(users)

    # A non-owner may not list or manage users.
    assert c.get("/api/v1/auth/users", headers=_auth(readonly)).status_code == 403

    # Owner promotes the readonly user to sales.
    ro_id = users["ro@az.local"]["id"]
    upd = c.patch(f"/api/v1/auth/users/{ro_id}", json={"role": "sales"}, headers=_auth(owner))
    assert upd.status_code == 200
    assert upd.json()["role"] == "sales"

    # Owner cannot demote or deactivate themselves (no self-lockout).
    owner_id = users["owner@az.local"]["id"]
    assert c.patch(f"/api/v1/auth/users/{owner_id}", json={"role": "readonly"},
                   headers=_auth(owner)).status_code == 400
    assert c.patch(f"/api/v1/auth/users/{owner_id}", json={"is_active": False},
                   headers=_auth(owner)).status_code == 400


def test_owner_deletes_teammate(client: tuple[TestClient, str, str]) -> None:
    c, owner, readonly = client
    users = {u["email"]: u for u in c.get("/api/v1/auth/users", headers=_auth(owner)).json()}
    ro_id = users["ro@az.local"]["id"]

    # A non-owner may not delete users.
    assert c.delete(f"/api/v1/auth/users/{ro_id}", headers=_auth(readonly)).status_code == 403
    # Owner deletes the teammate…
    assert c.delete(f"/api/v1/auth/users/{ro_id}", headers=_auth(owner)).status_code == 204
    # …who now drops off the list and can no longer log in.
    remaining = {u["email"] for u in c.get("/api/v1/auth/users", headers=_auth(owner)).json()}
    assert "ro@az.local" not in remaining
    assert c.post("/api/v1/auth/login",
                  json={"email": "ro@az.local", "password": "pw"}).status_code == 401


def test_owner_cannot_delete_self_or_last_owner(client: tuple[TestClient, str, str]) -> None:
    c, owner, _ = client
    users = {u["email"]: u for u in c.get("/api/v1/auth/users", headers=_auth(owner)).json()}
    owner_id = users["owner@az.local"]["id"]
    # The sole owner is both "yourself" and "the last owner" — deletion is blocked.
    assert c.delete(f"/api/v1/auth/users/{owner_id}", headers=_auth(owner)).status_code == 400


def test_change_own_password(client: tuple[TestClient, str, str]) -> None:
    c, owner, _ = client
    # Wrong current password is rejected.
    assert c.post("/api/v1/auth/change-password",
                  json={"current_password": "wrong", "new_password": "newpass1"},
                  headers=_auth(owner)).status_code == 400
    # Correct current password succeeds…
    assert c.post("/api/v1/auth/change-password",
                  json={"current_password": "pw", "new_password": "newpass1"},
                  headers=_auth(owner)).status_code == 204
    # …and the new password now works while the old one does not.
    assert c.post("/api/v1/auth/login",
                  json={"email": "owner@az.local", "password": "newpass1"}).status_code == 200
    assert c.post("/api/v1/auth/login",
                  json={"email": "owner@az.local", "password": "pw"}).status_code == 401


def test_owner_resets_teammate_password(client: tuple[TestClient, str, str]) -> None:
    c, owner, readonly = client
    users = {u["email"]: u for u in c.get("/api/v1/auth/users", headers=_auth(owner)).json()}
    ro_id = users["ro@az.local"]["id"]
    # Readonly may not reset anyone.
    assert c.post(f"/api/v1/auth/users/{ro_id}/reset-password",
                  json={"new_password": "x123456"}, headers=_auth(readonly)).status_code == 403
    # Owner resets the teammate, who can then log in with the new password.
    assert c.post(f"/api/v1/auth/users/{ro_id}/reset-password",
                  json={"new_password": "reset123"}, headers=_auth(owner)).status_code == 204
    assert c.post("/api/v1/auth/login",
                  json={"email": "ro@az.local", "password": "reset123"}).status_code == 200


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
