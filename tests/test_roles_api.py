"""Dynamic roles & permissions (D-0015) — the RBAC management surface and the
permission-based gating it drives. Uses the REAL auth stack (tokens for seeded
users), like test_authz.
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
from app.services.roles import ensure_system_roles
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


@pytest.fixture
def client(db_session: Session) -> Iterator[tuple[TestClient, dict[str, str]]]:
    from scripts.seed_org import seed_tax_rules

    org = Organization(name="Roles QA", slug=f"roles-{uuid.uuid4().hex[:8]}",
                       gst_state_code="05", gst_state_name="Uttarakhand")
    db_session.add(org)
    db_session.flush()
    seed_tax_rules(db_session, org.id)
    ensure_system_roles(db_session, org.id)
    owner = create_user(db_session, org.id, email="owner@r.local", password="pw",
                        role=UserRole.OWNER.value)
    readonly = create_user(db_session, org.id, email="ro@r.local", password="pw",
                           role=UserRole.READONLY.value)

    def _session() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_session] = _session
    try:
        tokens = {"owner": token_for(owner), "readonly": token_for(readonly),
                  "readonly_id": str(readonly.id)}
        yield TestClient(app), tokens
    finally:
        app.dependency_overrides.clear()


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_catalog_and_roles_are_listed(client: tuple[TestClient, dict[str, str]]) -> None:
    c, t = client
    perms = c.get("/api/v1/roles/permissions", headers=_h(t["owner"]))
    assert perms.status_code == 200
    keys = {p["key"] for p in perms.json()}
    assert {"users.manage", "suppliers.manage", "quotes.issue", "invoices.manage"} <= keys

    roles = c.get("/api/v1/roles", headers=_h(t["owner"]))
    assert roles.status_code == 200
    by_key = {r["key"]: r for r in roles.json()}
    assert set(by_key) == {"owner", "ops_manager", "sales", "accounts", "readonly"}
    assert "users.manage" in by_key["owner"]["permissions"]
    assert by_key["readonly"]["permissions"] == []

    # A non-admin can't see or manage roles.
    assert c.get("/api/v1/roles", headers=_h(t["readonly"])).status_code == 403


def test_create_custom_role_then_gate_follows_it(
    client: tuple[TestClient, dict[str, str]]
) -> None:
    c, t = client
    # Readonly can't manage suppliers yet.
    supplier = {"kind": "stay", "legal_name": "X", "display_name": "X"}
    assert c.post("/api/v1/suppliers", json=supplier,
                  headers=_h(t["readonly"])).status_code == 403

    # Create a custom role that CAN manage suppliers, and assign it to the user.
    made = c.post("/api/v1/roles", headers=_h(t["owner"]),
                  json={"label": "Reservations", "permissions": ["suppliers.manage"]})
    assert made.status_code == 201
    assert made.json()["key"] == "reservations"
    upd = c.patch(f"/api/v1/auth/users/{t['readonly_id']}",
                  json={"role": "reservations"}, headers=_h(t["owner"]))
    assert upd.status_code == 200 and upd.json()["role"] == "reservations"

    # Same user, same token — now allowed to manage suppliers, still not to issue.
    assert c.post("/api/v1/suppliers", json=supplier,
                  headers=_h(t["readonly"])).status_code == 201
    # /me reflects the new permission set.
    me = c.get("/api/v1/auth/me", headers=_h(t["readonly"])).json()
    assert me["permissions"] == ["suppliers.manage"]


def test_roles_can_be_renamed(client: tuple[TestClient, dict[str, str]]) -> None:
    c, t = client
    roles = {r["key"]: r for r in c.get("/api/v1/roles", headers=_h(t["owner"])).json()}
    # A built-in role's display name can be changed (its key is unaffected).
    r = c.patch(f"/api/v1/roles/{roles['sales']['id']}",
                json={"label": "Travel Consultant"}, headers=_h(t["owner"]))
    assert r.status_code == 200
    assert r.json()["label"] == "Travel Consultant" and r.json()["key"] == "sales"


def test_owner_role_cannot_lose_permissions(
    client: tuple[TestClient, dict[str, str]]
) -> None:
    c, t = client
    roles = {r["key"]: r for r in c.get("/api/v1/roles", headers=_h(t["owner"])).json()}
    owner_id = roles["owner"]["id"]
    resp = c.patch(f"/api/v1/roles/{owner_id}",
                   json={"permissions": ["users.manage"]}, headers=_h(t["owner"]))
    assert resp.status_code == 400


def test_unknown_permission_is_rejected(
    client: tuple[TestClient, dict[str, str]]
) -> None:
    c, t = client
    resp = c.post("/api/v1/roles", headers=_h(t["owner"]),
                  json={"label": "Bad", "permissions": ["does.not.exist"]})
    assert resp.status_code == 422


def test_system_and_in_use_roles_are_protected(
    client: tuple[TestClient, dict[str, str]]
) -> None:
    c, t = client
    roles = {r["key"]: r for r in c.get("/api/v1/roles", headers=_h(t["owner"])).json()}
    # A built-in role can't be deleted.
    assert c.delete(f"/api/v1/roles/{roles['sales']['id']}",
                    headers=_h(t["owner"])).status_code == 400

    # A custom role in use can't be deleted until users are reassigned.
    made = c.post("/api/v1/roles", headers=_h(t["owner"]),
                  json={"label": "Temp", "permissions": []}).json()
    c.patch(f"/api/v1/auth/users/{t['readonly_id']}",
            json={"role": "temp"}, headers=_h(t["owner"]))
    assert c.delete(f"/api/v1/roles/{made['id']}",
                    headers=_h(t["owner"])).status_code == 409
    c.patch(f"/api/v1/auth/users/{t['readonly_id']}",
            json={"role": "readonly"}, headers=_h(t["owner"]))
    assert c.delete(f"/api/v1/roles/{made['id']}",
                    headers=_h(t["owner"])).status_code == 204
