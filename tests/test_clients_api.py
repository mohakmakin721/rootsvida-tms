"""Phase 3 M8 — client records + project continuity.

The builder's intake: search/create clients, then create projects against an
existing client (repeat trips) or an inline new one — with a code-collision guard.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from app.api.deps import current_org_id
from app.db import get_session
from app.main import app
from app.models import Organization
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


@pytest.fixture
def api(db_session: Session) -> Iterator[TestClient]:
    org = Organization(name="Client QA", slug=f"cl-{uuid.uuid4().hex[:8]}",
                       gst_state_code="05", gst_state_name="Uttarakhand")
    db_session.add(org)
    db_session.flush()

    def _session() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[current_org_id] = lambda: org.id
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_create_and_search_client(api: TestClient) -> None:
    created = api.post("/api/v1/clients", json={
        "name": "Ana García", "client_type": "family", "country": "CL",
        "email": "ana@example.com", "notes": "Loves forts; mid-range budget"}).json()
    assert created["client_type"] == "family"
    assert created["project_count"] == 0

    found = api.get("/api/v1/clients", params={"q": "garc"}).json()
    assert [c["name"] for c in found] == ["Ana García"]
    assert found[0]["email"] == "ana@example.com"


def test_project_against_existing_client_and_continuity(api: TestClient) -> None:
    client = api.post("/api/v1/clients", json={"name": "Globus Tours", "client_type": "corporate"}).json()

    p1 = api.post("/api/v1/projects", json={"code": "GT-01", "client_id": client["id"]})
    assert p1.status_code == 201, p1.text
    assert p1.json()["client_id"] == client["id"]
    assert p1.json()["client_name"] == "Globus Tours"

    # A second trip for the same client — a new project under the same buyer.
    p2 = api.post("/api/v1/projects", json={"code": "GT-02", "client_id": client["id"]})
    assert p2.status_code == 201

    detail = api.get(f"/api/v1/clients/{client['id']}").json()
    assert detail["project_count"] == 2
    assert {p["code"] for p in detail["projects"]} == {"GT-01", "GT-02"}


def test_project_with_inline_new_client_saves_client(api: TestClient) -> None:
    resp = api.post("/api/v1/projects", json={
        "code": "NEW-1",
        "client": {"name": "Kenji Tan", "client_type": "individual", "country": "SG"},
    })
    assert resp.status_code == 201, resp.text
    cid = resp.json()["client_id"]
    assert cid is not None
    # The client is now searchable in the book.
    found = api.get("/api/v1/clients", params={"q": "kenji"}).json()
    assert found[0]["id"] == cid
    assert found[0]["country"] == "SG"


def test_duplicate_project_code_is_409(api: TestClient) -> None:
    api.post("/api/v1/projects", json={"code": "DUP-1", "client_name": "Someone"})
    dup = api.post("/api/v1/projects", json={"code": "DUP-1", "client_name": "Another"})
    assert dup.status_code == 409
    assert "already exists" in dup.json()["detail"]


def test_projects_filter_by_code(api: TestClient) -> None:
    api.post("/api/v1/projects", json={"code": "FIND-ME", "client_name": "X"})
    hit = api.get("/api/v1/projects", params={"code": "FIND-ME"}).json()
    assert len(hit) == 1 and hit[0]["code"] == "FIND-ME"
    miss = api.get("/api/v1/projects", params={"code": "NOPE"}).json()
    assert miss == []


def test_legacy_bare_client_name_still_works(api: TestClient) -> None:
    resp = api.post("/api/v1/projects", json={"code": "LEG-1", "client_name": "Walk-in"})
    assert resp.status_code == 201
    assert resp.json()["client_id"] is None
    assert resp.json()["client_name"] == "Walk-in"


def test_project_requires_some_client(api: TestClient) -> None:
    resp = api.post("/api/v1/projects", json={"code": "NOCLIENT"})
    assert resp.status_code == 422
