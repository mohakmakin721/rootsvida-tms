"""Phase 3 M10 — first-class project timeline: status, travel window, milestones."""

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
    org = Organization(name="Timeline QA", slug=f"tl-{uuid.uuid4().hex[:8]}",
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


def _project(api: TestClient, code: str = "TL-1") -> str:
    return api.post("/api/v1/projects", json={"code": code, "client_name": "X"}).json()["id"]


def test_status_change_stamps_and_validates(api: TestClient) -> None:
    pid = _project(api)
    before = api.get(f"/api/v1/projects/{pid}").json()
    assert before["status"] == "enquiry"
    assert before["status_changed_at"] is None

    moved = api.patch(f"/api/v1/projects/{pid}", json={"status": "quoted"}).json()
    assert moved["status"] == "quoted"
    assert moved["status_changed_at"] is not None

    bad = api.patch(f"/api/v1/projects/{pid}", json={"status": "banana"})
    assert bad.status_code == 422


def test_set_travel_window(api: TestClient) -> None:
    pid = _project(api, "TL-2")
    out = api.patch(f"/api/v1/projects/{pid}",
                    json={"travel_start": "2026-11-10", "travel_end": "2026-11-18"}).json()
    assert out["travel_start"] == "2026-11-10"
    assert out["travel_end"] == "2026-11-18"


def test_milestone_crud_and_ordering(api: TestClient) -> None:
    pid = _project(api, "TL-3")
    api.post(f"/api/v1/projects/{pid}/milestones",
             json={"kind": "payment", "title": "Balance", "due_date": "2026-10-01", "amount": "50000"})
    m_early = api.post(f"/api/v1/projects/{pid}/milestones",
                       json={"kind": "payment", "title": "Deposit", "due_date": "2026-09-01"}).json()
    api.post(f"/api/v1/projects/{pid}/milestones",
             json={"kind": "note", "title": "No date"})

    listed = api.get(f"/api/v1/projects/{pid}/milestones").json()
    # Dated milestones first (earliest → latest), undated last.
    assert [m["title"] for m in listed] == ["Deposit", "Balance", "No date"]

    done = api.patch(f"/api/v1/projects/milestones/{m_early['id']}", json={"done": True}).json()
    assert done["done"] is True

    assert api.delete(f"/api/v1/projects/milestones/{m_early['id']}").status_code == 204
    assert len(api.get(f"/api/v1/projects/{pid}/milestones").json()) == 2


def test_milestone_404(api: TestClient) -> None:
    assert api.patch(f"/api/v1/projects/milestones/{uuid.uuid4()}", json={"done": True}).status_code == 404


def test_activity_log_aggregates_and_filters(api: TestClient) -> None:
    p1 = api.post("/api/v1/projects", json={"code": "AC-1", "client_name": "Acme"}).json()["id"]
    p2 = api.post("/api/v1/projects", json={"code": "AC-2", "client_name": "Beta"}).json()["id"]
    api.post(f"/api/v1/projects/{p1}/milestones",
             json={"kind": "payment", "title": "Deposit", "due_date": "2026-09-01",
                   "amount": "10000", "done": True})
    api.post(f"/api/v1/projects/{p1}/milestones",
             json={"kind": "payment_deadline", "title": "Balance", "due_date": "2026-10-01"})
    api.post(f"/api/v1/projects/{p2}/milestones",
             json={"kind": "note", "title": "Called client"})

    # Org-wide, enriched with project code + client name.
    all_rows = api.get("/api/v1/projects/activity-log").json()
    assert len(all_rows) == 3
    assert {r["project_code"] for r in all_rows} == {"AC-1", "AC-2"}
    assert all("client_name" in r and "project_status" in r for r in all_rows)

    # Filter by client name.
    beta = api.get("/api/v1/projects/activity-log", params={"q": "Beta"}).json()
    assert [r["project_code"] for r in beta] == ["AC-2"]

    # Filter by kind + pending.
    due = api.get("/api/v1/projects/activity-log",
                  params={"kind": "payment_deadline", "done": "false"}).json()
    assert [r["title"] for r in due] == ["Balance"]
