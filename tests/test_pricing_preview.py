"""Phase 3 M7 — live pricing preview.

The builder's cost sidebar is powered by `POST /pricing/preview`, which prices a
draft itinerary WITHOUT persisting. Exit test: the preview reproduces the Jaipur
golden numbers to the rupee (same engine, same path), and leaves no rows behind.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from decimal import Decimal

import pytest
from app.api.deps import current_org_id, current_user
from app.db import get_session
from app.main import app
from app.models import Itinerary, Organization, Project, User
from app.models.enums import UserRole
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tests.test_api_itinerary_quote import _itinerary_payload


@pytest.fixture
def api(db_session: Session) -> Iterator[tuple[TestClient, Session]]:
    from scripts.seed_org import seed_tax_rules

    org = Organization(name="Preview QA", slug=f"pv-{uuid.uuid4().hex[:8]}",
                       gst_state_code="05", gst_state_name="Uttarakhand")
    db_session.add(org)
    db_session.flush()
    seed_tax_rules(db_session, org.id)
    owner = User(org_id=org.id, email="owner@qa.local", role=UserRole.OWNER, is_active=True)
    db_session.add(owner)
    db_session.flush()

    def _session() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[current_org_id] = lambda: org.id
    app.dependency_overrides[current_user] = lambda: owner
    try:
        yield TestClient(app), db_session
    finally:
        app.dependency_overrides.clear()


def _markup_rules(client: TestClient) -> tuple[str, str]:
    foreign = client.post("/api/v1/markup-rules", json={
        "label": "Foreign 15%", "basis": "markup_on_cost", "rate": "0.15"}).json()["id"]
    indian = client.post("/api/v1/markup-rules", json={
        "label": "Indian 10%", "basis": "markup_on_cost", "rate": "0.10"}).json()["id"]
    return foreign, indian


def _d(v: object) -> Decimal:
    return Decimal(str(v))


def test_preview_reproduces_jaipur_golden(api: tuple[TestClient, Session]) -> None:
    client, _ = api
    foreign, indian = _markup_rules(client)
    resp = client.post("/api/v1/pricing/preview", json={
        "itinerary": _itinerary_payload(foreign, indian),
        "buyer_state_code": "05", "buyer_country": "IN",
        "rounding": "nearest_1", "fx_currency": "USD", "fx_rate": "95",
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert _d(body["group_total"]) == Decimal("403327.00")
    assert _d(body["total_cost"]) == Decimal("336050.00")
    assert _d(body["profit"]) == Decimal("67277.00")
    assert _d(body["margin_pct"]) == Decimal("12.52")
    assert body["gst_treatment"] == "cgst_sgst"
    assert body["fx"] == {"USD": "4245.55"}
    sells = {s["label"]: _d(s["sell_per_pax"]) for s in body["segments"]}
    assert sells["Foreign Single"] == Decimal(65597)
    assert sells["Foreign Double"] == Decimal(47303)
    assert sells["Indian Double"] == Decimal(26956)


def test_preview_converts_to_chosen_currency(api: tuple[TestClient, Session]) -> None:
    client, _ = api
    foreign, indian = _markup_rules(client)
    resp = client.post("/api/v1/pricing/preview", json={
        "itinerary": _itinerary_payload(foreign, indian),
        "buyer_state_code": "05", "fx_currency": "EUR", "fx_rate": "90",
    })
    assert resp.status_code == 200, resp.text
    # 403327 / 90 = 4481.41 — INR stays authoritative, EUR is the display convert.
    assert resp.json()["fx"] == {"EUR": "4481.41"}


def test_preview_persists_nothing(api: tuple[TestClient, Session]) -> None:
    client, session = api
    foreign, indian = _markup_rules(client)
    before_p = session.scalar(select(func.count()).select_from(Project))
    before_i = session.scalar(select(func.count()).select_from(Itinerary))

    client.post("/api/v1/pricing/preview", json={
        "itinerary": _itinerary_payload(foreign, indian), "buyer_state_code": "05"})

    assert session.scalar(select(func.count()).select_from(Project)) == before_p
    assert session.scalar(select(func.count()).select_from(Itinerary)) == before_i


def test_preview_flags_below_floor_without_raising(api: tuple[TestClient, Session]) -> None:
    client, _ = api
    foreign, indian = _markup_rules(client)
    resp = client.post("/api/v1/pricing/preview", json={
        "itinerary": _itinerary_payload(foreign, indian),
        "buyer_state_code": "05", "margin_floor": "0.20",
    })
    # A quote would 422 here; a preview shows the number and flags it.
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["below_floor"] is True
    assert _d(body["margin_pct"]) == Decimal("12.52")


def test_preview_unknown_segment_key_is_422(api: tuple[TestClient, Session]) -> None:
    client, _ = api
    foreign, _indian = _markup_rules(client)
    draft = {
        "title": "Bad", "start_date": "2026-07-18", "end_date": "2026-07-19",
        "segments": [{"key": "fs", "label": "FS", "pax_class": "foreign",
                      "occupancy": "single", "pax_count": 1, "markup_rule_id": foreign}],
        "days": [{"day_number": 1, "date": "2026-07-18",
                  "present_segment_keys": ["ghost"], "components": []}],
    }
    resp = client.post("/api/v1/pricing/preview",
                       json={"itinerary": draft, "buyer_state_code": "05"})
    assert resp.status_code == 422
