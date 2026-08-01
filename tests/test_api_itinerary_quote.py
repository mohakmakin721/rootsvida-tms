"""Phase 3 M4 — REST API: project → itinerary → quote, reproducing Jaipur over HTTP.

Dependencies are overridden so endpoints run in the test's rolled-back
transaction under a fresh org (with GST identity + tax rules seeded).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from decimal import Decimal

import pytest
from app.api.deps import current_org_id
from app.db import get_session
from app.main import app
from app.models import Organization
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

_NIGHTS = [(7300, 7300), (5500, 5500), (5500, 5500), (5000, 6000), (5000, 5500), (4000, 4500)]
_SHARED = [  # (desc, amount, allocation, pax_class)
    ("Transport", 41000, "all_pax", None), ("Jaipur Guide", 4000, "all_pax", None),
    ("Agra Guide", 2500, "all_pax", None), ("Rohan TA/DA", 25000, "all_pax", None),
    ("Rohan Fee", 21000, "all_pax", None),
    ("Delhi Urbania", 8000, "by_pax_class", "foreign"),
    ("Jaipur Mon F", 18900, "by_pax_class", "foreign"),
    ("Agra Mon F", 13650, "by_pax_class", "foreign"),
    ("Delhi Mon F", 10500, "by_pax_class", "foreign"),
    ("Delhi Cycle", 15400, "by_pax_class", "foreign"),
    ("Misc", 15000, "by_pax_class", "foreign"),
    ("Jaipur Mon I", 1000, "by_pax_class", "indian"),
    ("Agra Mon I", 600, "by_pax_class", "indian"),
    ("Delhi Mon I", 0, "by_pax_class", "indian"),
]


@pytest.fixture
def api(db_session: Session) -> Iterator[TestClient]:
    from scripts.seed_org import seed_tax_rules

    org = Organization(name="API QA", slug=f"api-{uuid.uuid4().hex[:8]}",
                       gst_state_code="05", gst_state_name="Uttarakhand")
    db_session.add(org)
    db_session.flush()
    seed_tax_rules(db_session, org.id)

    def _session() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[current_org_id] = lambda: org.id
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _itinerary_payload(foreign: str, indian: str) -> dict:
    segments = [
        {"key": "fs", "label": "Foreign Single", "pax_class": "foreign",
         "occupancy": "single", "pax_count": 1, "markup_rule_id": foreign},
        {"key": "fd", "label": "Foreign Double", "pax_class": "foreign",
         "occupancy": "double", "pax_count": 6, "markup_rule_id": foreign},
        {"key": "id", "label": "Indian Double", "pax_class": "indian",
         "occupancy": "double", "pax_count": 2, "markup_rule_id": indian},
    ]
    days = []
    for i, (single_rate, double_rate) in enumerate(_NIGHTS, start=1):
        comps: list[dict] = [
            {"kind": "stay", "description": "Single room", "override_amount": str(single_rate),
             "override_reason": "manual", "applies_to_segment_keys": ["fs"]},
            {"kind": "stay", "description": "Double room", "override_amount": str(double_rate),
             "override_reason": "manual", "applies_to_segment_keys": ["fd", "id"]},
        ]
        if i == 1:
            for desc, amount, alloc, cls in _SHARED:
                c: dict = {"kind": "misc", "description": desc, "override_amount": str(amount),
                           "override_reason": "manual", "allocation": alloc}
                if cls:
                    c["applies_to_pax_class"] = cls
                comps.append(c)
        days.append({
            "day_number": i, "date": f"2026-07-{17 + i:02d}",
            "present_segment_keys": ["fs", "fd", "id"] if i <= 4 else ["fs", "fd"],
            "components": comps,
        })
    return {"title": "Jaipur / Golden Triangle", "start_date": "2026-07-18",
            "end_date": "2026-07-23", "segments": segments, "days": days}


def _setup(api: TestClient) -> tuple[str, str]:
    """Create markup rules + a project + the Jaipur itinerary; return (itinerary_id, project_id)."""
    foreign = api.post("/api/v1/markup-rules", json={
        "label": "Foreign 15%", "basis": "markup_on_cost", "rate": "0.15"}).json()["id"]
    indian = api.post("/api/v1/markup-rules", json={
        "label": "Indian 10%", "basis": "markup_on_cost", "rate": "0.10"}).json()["id"]
    project = api.post("/api/v1/projects", json={
        "code": "TP-JP", "client_name": "Golden Triangle"}).json()
    resp = api.post(f"/api/v1/projects/{project['id']}/itineraries",
                    json=_itinerary_payload(foreign, indian))
    assert resp.status_code == 201, resp.text
    return resp.json()["id"], project["id"]


def _d(v: object) -> Decimal:
    return Decimal(str(v))


def test_itinerary_read_back(api: TestClient) -> None:
    itinerary_id, _ = _setup(api)
    it = api.get(f"/api/v1/itineraries/{itinerary_id}").json()
    assert len(it["segments"]) == 3
    assert len(it["days"]) == 6
    assert len(it["days"][4]["present_segment_ids"]) == 2  # day 5 Delhi: foreigners only


def test_list_project_itineraries(api: TestClient) -> None:
    itinerary_id, project_id = _setup(api)
    listed = api.get(f"/api/v1/projects/{project_id}/itineraries").json()
    assert len(listed) == 1
    assert listed[0]["id"] == itinerary_id
    assert listed[0]["title"] == "Jaipur / Golden Triangle"


def test_quote_in_eur(api: TestClient) -> None:
    itinerary_id, _ = _setup(api)
    quote = api.post(f"/api/v1/itineraries/{itinerary_id}/quotes",
                     json={"buyer_state_code": "05", "fx_currency": "EUR", "fx_rate": "90"}).json()
    assert quote["fx_currency"] == "EUR"
    assert _d(quote["total_gross"]) == Decimal("403327.00")  # ₹ unchanged


def test_quote_reproduces_jaipur_over_http(api: TestClient) -> None:
    itinerary_id, project_id = _setup(api)
    resp = api.post(f"/api/v1/itineraries/{itinerary_id}/quotes",
                    json={"buyer_state_code": "05", "buyer_country": "IN",
                          "rounding": "nearest_1", "fx_currency": "USD", "fx_rate": "95"})
    assert resp.status_code == 201, resp.text
    quote = resp.json()

    assert _d(quote["total_gross"]) == Decimal("403327.00")
    assert _d(quote["total_cost"]) == Decimal("336050.00")
    assert _d(quote["margin_pct"]) == Decimal("12.52")
    assert quote["gst_treatment"] == "cgst_sgst"
    assert quote["fx_currency"] == "USD"
    sells = {ln["description"]: _d(ln["sell_per_pax"]) for ln in quote["lines"]}
    assert sells["Foreign Single"] == Decimal(65597)
    assert sells["Foreign Double"] == Decimal(47303)
    assert sells["Indian Double"] == Decimal(26956)

    # issue → frozen; then revise → a new draft version
    issued = api.post(f"/api/v1/quotes/{quote['id']}/issue", json={}).json()
    assert issued["status"] == "issued"
    revised = api.post(f"/api/v1/quotes/{quote['id']}/revise",
                       json={"buyer_state_code": "05", "fx_rate": "95"})
    assert revised.status_code == 201
    assert revised.json()["version"] == 2

    listed = api.get(f"/api/v1/projects/{project_id}/quotes").json()
    assert {q["version"] for q in listed} == {1, 2}


def test_margin_floor_returns_422(api: TestClient) -> None:
    itinerary_id, _ = _setup(api)
    resp = api.post(f"/api/v1/itineraries/{itinerary_id}/quotes",
                    json={"buyer_state_code": "05", "margin_floor": "0.20"})
    assert resp.status_code == 422
    assert "margin" in resp.json()["detail"].lower()
