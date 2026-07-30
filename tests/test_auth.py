"""Phase 3 M5 — self-hosted auth (passwords, tokens, login, RBAC)."""

from __future__ import annotations

import time
import uuid
from collections.abc import Iterator

import pytest
from app.api.deps import current_org_id
from app.db import get_session
from app.main import app
from app.models import Organization
from app.models.enums import UserRole
from app.security.passwords import hash_password, verify_password
from app.security.tokens import TokenError, create_token, verify_token
from app.services.auth import create_user
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

_SECRET = "unit-test-secret"


# --------------------------------------------------------------------------- #
# primitives (no DB)
# --------------------------------------------------------------------------- #


def test_password_hash_round_trip() -> None:
    stored = hash_password("s3cret!")
    assert stored.startswith("pbkdf2_sha256$")
    assert verify_password("s3cret!", stored)
    assert not verify_password("wrong", stored)
    assert not verify_password("s3cret!", None)


def test_hashes_are_salted_unique() -> None:
    assert hash_password("same") != hash_password("same")


def test_token_round_trip_and_tamper() -> None:
    token = create_token("user-123", _SECRET, ttl_seconds=60)
    assert verify_token(token, _SECRET) == "user-123"
    with pytest.raises(TokenError):
        verify_token(token, "other-secret")  # bad signature
    with pytest.raises(TokenError):
        verify_token(token + "x", _SECRET)  # tampered
    with pytest.raises(TokenError):
        verify_token("not-a-token", _SECRET)


def test_token_expiry() -> None:
    token = create_token("u", _SECRET, ttl_seconds=-1)  # already expired
    with pytest.raises(TokenError):
        verify_token(token, _SECRET)
    assert create_token("u", _SECRET, ttl_seconds=1).split(".")[0]  # sanity
    time.sleep(0)  # no real wait needed


# --------------------------------------------------------------------------- #
# API (rolled back)
# --------------------------------------------------------------------------- #


@pytest.fixture
def api(db_session: Session) -> Iterator[tuple[TestClient, Organization]]:
    org = Organization(name="Auth QA", slug=f"auth-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    db_session.flush()

    def _session() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[current_org_id] = lambda: org.id
    try:
        yield TestClient(app), org
    finally:
        app.dependency_overrides.clear()


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def test_login_and_me(api: tuple[TestClient, Organization], db_session: Session) -> None:
    client, org = api
    create_user(db_session, org.id, email="ops@x.com", password="pw", role=UserRole.OPS_MANAGER)

    token = _login(client, "ops@x.com", "pw")
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["email"] == "ops@x.com"
    assert me["role"] == "ops_manager"


def test_login_rejects_bad_credentials(api: tuple[TestClient, Organization],
                                       db_session: Session) -> None:
    client, org = api
    create_user(db_session, org.id, email="ops@x.com", password="pw")
    assert client.post("/api/v1/auth/login",
                       json={"email": "ops@x.com", "password": "nope"}).status_code == 401
    assert client.post("/api/v1/auth/login",
                       json={"email": "ghost@x.com", "password": "pw"}).status_code == 401


def test_me_requires_a_valid_token(api: tuple[TestClient, Organization]) -> None:
    client, _ = api
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me",
                      headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_user_creation_is_owner_only(api: tuple[TestClient, Organization],
                                     db_session: Session) -> None:
    client, org = api
    create_user(db_session, org.id, email="owner@x.com", password="pw", role=UserRole.OWNER)
    create_user(db_session, org.id, email="sales@x.com", password="pw", role=UserRole.SALES)

    body = {"email": "new@x.com", "password": "pw", "role": "sales"}
    assert client.post("/api/v1/auth/users", json=body).status_code == 401  # no token

    sales = _login(client, "sales@x.com", "pw")
    resp = client.post("/api/v1/auth/users", json=body,
                       headers={"Authorization": f"Bearer {sales}"})
    assert resp.status_code == 403  # not an owner

    owner = _login(client, "owner@x.com", "pw")
    resp = client.post("/api/v1/auth/users", json=body,
                       headers={"Authorization": f"Bearer {owner}"})
    assert resp.status_code == 201
    assert resp.json()["role"] == "sales"
