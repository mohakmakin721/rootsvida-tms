"""Phase 5 (5a-M4) — planning endpoints: intake save/get, paste-parse, suggest.

DB-backed (runs in CI's Postgres). Uses the deterministic stub provider, so no LLM
key or network is needed.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from app.api.deps import current_org_id
from app.db import get_session
from app.main import app
from app.models import Destination, Organization, Supplier
from app.models.enums import SupplierKind
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


@pytest.fixture
def api(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    # Force the deterministic stub so the suggest test never calls a live LLM (would
    # be non-deterministic and quota-limited when a key is set in a local .env).
    from app.llm import StubProvider
    stub = lambda *a, **k: StubProvider()  # noqa: E731
    monkeypatch.setattr("app.services.planning.get_provider", stub)
    monkeypatch.setattr("app.api.v1.planning.get_provider", stub)

    org = Organization(name="Plan QA", slug=f"pl-{uuid.uuid4().hex[:8]}",
                       gst_state_code="05", gst_state_name="Uttarakhand")
    db_session.add(org)
    db_session.flush()

    dest = Destination(org_id=org.id, name="Rishikesh", country="India")
    db_session.add(dest)
    db_session.flush()
    db_session.add(Supplier(
        org_id=org.id, kind=SupplierKind.STAY,
        legal_name="Riverside Retreat", display_name="Riverside Retreat",
        destination_id=dest.id, category="Luxury", property_type="Resort",
        tags=["wellness", "yoga"],
    ))
    db_session.flush()

    def _session() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[current_org_id] = lambda: org.id
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_create_and_get_intake(api: TestClient) -> None:
    created = api.post("/api/v1/planning/intakes", json={
        "destination": "Rishikesh", "group_size": 5, "themes": ["Yoga"],
        "duration_days": 3, "budget_inr": "300000", "tier": "Luxury Hotel"}).json()
    got = api.get(f"/api/v1/planning/intakes/{created['id']}").json()
    assert got["destination"] == "Rishikesh"
    assert got["themes"] == ["Yoga"]
    assert got["group_size"] == 5


def test_get_missing_intake_is_404(api: TestClient) -> None:
    assert api.get(f"/api/v1/planning/intakes/{uuid.uuid4()}").status_code == 404


def test_parse_preserves_raw_via_stub(api: TestClient) -> None:
    r = api.post("/api/v1/planning/parse", json={"text": "Budget 300000, 5 days"})
    assert r.status_code == 200
    assert r.json()["raw"] == "Budget 300000, 5 days"


def test_suggest_returns_weights_ranked_and_draft(api: TestClient) -> None:
    r = api.post("/api/v1/planning/suggest", json={
        "destination": "Rishikesh", "duration_days": 3, "group_size": 5,
        "themes": ["Yoga", "Wellness"], "tier": "Luxury Hotel"})
    assert r.status_code == 200
    body = r.json()
    assert abs(sum(body["weights"].values()) - 100.0) < 0.1
    assert body["draft"]["duration_days"] == 3
    assert len(body["draft"]["days"]) == 3
    # The seeded Rishikesh stay is ranked and shows up as a candidate.
    assert "Riverside Retreat" in [c["name"] for c in body["candidates"]]
