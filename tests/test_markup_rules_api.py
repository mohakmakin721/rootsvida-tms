"""Phase 3 M8 — markup-rule management (add / edit / remove)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from app.api.deps import current_org_id, current_user
from app.db import get_session
from app.main import app
from app.models import Organization, User
from app.models.enums import UserRole
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


@pytest.fixture
def api(db_session: Session) -> Iterator[TestClient]:
    org = Organization(name="Markup QA", slug=f"mk-{uuid.uuid4().hex[:8]}",
                       gst_state_code="05", gst_state_name="Uttarakhand")
    db_session.add(org)
    db_session.flush()
    owner = User(org_id=org.id, email="owner@qa.local", role=UserRole.OWNER, is_active=True)
    db_session.add(owner)
    db_session.flush()

    def _session() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[current_org_id] = lambda: org.id
    app.dependency_overrides[current_user] = lambda: owner
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_create_edit_delete_rule(api: TestClient) -> None:
    rule = api.post("/api/v1/markup-rules", json={
        "label": "Foreign 15%", "basis": "markup_on_cost", "rate": "0.15"}).json()

    edited = api.patch(f"/api/v1/markup-rules/{rule['id']}", json={"label": "Foreign 18%", "rate": "0.18"})
    assert edited.status_code == 200
    assert edited.json()["label"] == "Foreign 18%"
    assert edited.json()["rate"] == "0.18"

    deleted = api.delete(f"/api/v1/markup-rules/{rule['id']}")
    assert deleted.status_code == 204
    assert api.get("/api/v1/markup-rules").json() == []


def test_delete_rule_in_use_is_409(api: TestClient) -> None:
    rule = api.post("/api/v1/markup-rules", json={
        "label": "Foreign 15%", "basis": "markup_on_cost", "rate": "0.15"}).json()
    project = api.post("/api/v1/projects", json={"code": "MK-1", "client_name": "X"}).json()
    api.post(f"/api/v1/projects/{project['id']}/itineraries", json={
        "title": "T", "start_date": "2026-07-18", "end_date": "2026-07-19",
        "segments": [{"key": "a", "label": "A", "pax_class": "foreign",
                      "occupancy": "double", "pax_count": 2, "markup_rule_id": rule["id"]}],
        "days": [],
    })
    resp = api.delete(f"/api/v1/markup-rules/{rule['id']}")
    assert resp.status_code == 409
    assert "used by" in resp.json()["detail"]


def test_patch_unknown_rule_is_404(api: TestClient) -> None:
    resp = api.patch(f"/api/v1/markup-rules/{uuid.uuid4()}", json={"label": "x"})
    assert resp.status_code == 404
