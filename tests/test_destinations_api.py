"""Destination search + create (powers the city type-aheads)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from app.api.deps import current_org_id, current_user
from app.db import get_session
from app.main import app
from app.models import Destination, Organization, User
from app.models.enums import UserRole
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


@pytest.fixture
def api(db_session: Session) -> Iterator[TestClient]:
    org = Organization(name="Dest QA", slug=f"ds-{uuid.uuid4().hex[:8]}",
                       gst_state_code="05", gst_state_name="Uttarakhand")
    db_session.add(org)
    db_session.flush()
    db_session.add_all([
        Destination(org_id=org.id, name="Jaipur", state="Rajasthan", country="IN"),
        Destination(org_id=org.id, name="Jaisalmer", state="Rajasthan", country="IN"),
        Destination(org_id=org.id, name="Munnar", state="Kerala", country="IN"),
    ])
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


def test_search_destinations_typeahead(api: TestClient) -> None:
    all_dest = api.get("/api/v1/destinations").json()
    assert [d["name"] for d in all_dest] == ["Jaipur", "Jaisalmer", "Munnar"]  # ascending
    jai = api.get("/api/v1/destinations", params={"q": "jai"}).json()
    assert {d["name"] for d in jai} == {"Jaipur", "Jaisalmer"}


def test_create_destination(api: TestClient) -> None:
    created = api.post("/api/v1/destinations", json={"name": "Kochi", "state": "Kerala"})
    assert created.status_code == 201
    assert created.json()["state"] == "Kerala"
    assert any(d["name"] == "Kochi" for d in api.get("/api/v1/destinations", params={"q": "koch"}).json())
