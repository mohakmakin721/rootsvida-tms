"""Phase 3 M6 — supplier & rate browser API.

Search/filter, per-supplier detail with freshness badges, and the load-bearing
guarantee: commission/margin (supplier_commercials) never leak into a browser view
(D-0002).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import date, timedelta

import pytest
from app.api.deps import current_org_id
from app.db import get_session
from app.main import app
from app.models import (
    Destination,
    Organization,
    Rate,
    RoomType,
    Supplier,
    SupplierCommercials,
    SupplierContact,
)
from app.models.enums import MealPlan, Occupancy, SupplierKind
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

TODAY = date.today()


@pytest.fixture
def seeded(db_session: Session) -> Iterator[tuple[TestClient, dict[str, uuid.UUID]]]:
    org = Organization(name="Browser QA", slug=f"br-{uuid.uuid4().hex[:8]}",
                       gst_state_code="05", gst_state_name="Uttarakhand")
    db_session.add(org)
    db_session.flush()

    jaipur = Destination(org_id=org.id, name="Jaipur", state="Rajasthan", country="IN")
    udaipur = Destination(org_id=org.id, name="Udaipur", state="Rajasthan", country="IN")
    db_session.add_all([jaipur, udaipur])
    db_session.flush()

    # A luxury Jaipur hotel with a fresh rate + contact + room type + COMMERCIALS.
    taj = Supplier(org_id=org.id, kind=SupplierKind.HOTEL, legal_name="Taj Jai Mahal Palace",
                   display_name="Taj Jai Mahal", destination_id=jaipur.id,
                   category="Luxury", property_type="Heritage", status="active")
    # A budget Jaipur hotel with only an EXPIRED rate.
    zostel = Supplier(org_id=org.id, kind=SupplierKind.HOMESTAY, legal_name="Zostel Jaipur",
                      display_name="Zostel Jaipur", destination_id=jaipur.id,
                      category="Budget", status="prospect")
    # A Udaipur hotel with no rates at all.
    lake = Supplier(org_id=org.id, kind=SupplierKind.HOTEL, legal_name="Lake Palace",
                    display_name="Lake Palace", destination_id=udaipur.id,
                    category="Luxury", status="active")
    db_session.add_all([taj, zostel, lake])
    db_session.flush()

    db_session.add(SupplierCommercials(org_id=org.id, supplier_id=taj.id,
                                       commission_pct=15, margin_pct=8,
                                       commission_notes="SECRET — do not expose"))
    db_session.add(SupplierContact(org_id=org.id, supplier_id=taj.id,
                                   person_name="Ravi", email="ravi@taj.example",
                                   is_primary=True))
    rt = RoomType(org_id=org.id, supplier_id=taj.id, name="Deluxe")
    db_session.add(rt)
    db_session.flush()
    db_session.add(Rate(org_id=org.id, supplier_id=taj.id, room_type_id=rt.id,
                        meal_plan=MealPlan.CP, occupancy=Occupancy.DOUBLE, amount=7300,
                        valid_from=TODAY - timedelta(days=10), valid_to=TODAY + timedelta(days=200)))
    db_session.add(Rate(org_id=org.id, supplier_id=zostel.id,
                        meal_plan=MealPlan.EP, occupancy=Occupancy.DOUBLE, amount=1500,
                        valid_from=TODAY - timedelta(days=400), valid_to=TODAY - timedelta(days=30)))
    db_session.flush()

    def _session() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[current_org_id] = lambda: org.id
    ids = {"taj": taj.id, "zostel": zostel.id, "lake": lake.id, "jaipur": jaipur.id,
           "udaipur": udaipur.id}
    try:
        yield TestClient(app), ids
    finally:
        app.dependency_overrides.clear()


def test_list_returns_all_with_freshness_rollup(seeded) -> None:
    client, _ = seeded
    body = client.get("/api/v1/suppliers").json()
    assert body["total"] == 3
    by_name = {s["display_name"]: s for s in body["items"]}
    assert by_name["Taj Jai Mahal"]["freshness"] == "fresh"
    assert by_name["Taj Jai Mahal"]["rate_count"] == 1
    assert by_name["Zostel Jaipur"]["freshness"] == "expired"
    assert by_name["Lake Palace"]["freshness"] == "none"
    assert by_name["Lake Palace"]["rate_count"] == 0


def test_search_by_name(seeded) -> None:
    client, _ = seeded
    body = client.get("/api/v1/suppliers", params={"q": "zostel"}).json()
    assert [s["display_name"] for s in body["items"]] == ["Zostel Jaipur"]


def test_filter_by_destination_and_category(seeded) -> None:
    client, ids = seeded
    body = client.get("/api/v1/suppliers",
                      params={"destination_id": str(ids["udaipur"])}).json()
    assert [s["display_name"] for s in body["items"]] == ["Lake Palace"]

    body = client.get("/api/v1/suppliers", params={"category": "Budget"}).json()
    assert [s["display_name"] for s in body["items"]] == ["Zostel Jaipur"]


def test_filter_by_status_and_kind(seeded) -> None:
    client, _ = seeded
    body = client.get("/api/v1/suppliers", params={"status": "active"}).json()
    assert {s["display_name"] for s in body["items"]} == {"Taj Jai Mahal", "Lake Palace"}

    body = client.get("/api/v1/suppliers", params={"kind": "homestay"}).json()
    assert [s["display_name"] for s in body["items"]] == ["Zostel Jaipur"]


def test_pagination(seeded) -> None:
    client, _ = seeded
    body = client.get("/api/v1/suppliers", params={"limit": 2, "offset": 0}).json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["limit"] == 2


def test_detail_includes_contacts_room_types_rates(seeded) -> None:
    client, ids = seeded
    detail = client.get(f"/api/v1/suppliers/{ids['taj']}").json()
    assert detail["display_name"] == "Taj Jai Mahal"
    assert detail["destination_name"] == "Jaipur"
    assert len(detail["contacts"]) == 1
    assert detail["contacts"][0]["email"] == "ravi@taj.example"
    assert [rt["name"] for rt in detail["room_types"]] == ["Deluxe"]
    assert len(detail["rates"]) == 1
    assert detail["rates"][0]["freshness"] == "fresh"
    assert detail["rates"][0]["amount"] == "7300.00"


def test_detail_404_for_unknown(seeded) -> None:
    client, _ = seeded
    res = client.get(f"/api/v1/suppliers/{uuid.uuid4()}")
    assert res.status_code == 404


def test_commercials_never_leak(seeded) -> None:
    """D-0002 — commission/margin must not appear in any browser payload."""
    client, ids = seeded
    listed = client.get("/api/v1/suppliers").text.lower()
    detail = client.get(f"/api/v1/suppliers/{ids['taj']}").text.lower()
    for blob in (listed, detail):
        assert "commission" not in blob
        assert "margin" not in blob
        assert "secret" not in blob


def test_facets_expose_destinations_and_categories(seeded) -> None:
    client, _ = seeded
    facets = client.get("/api/v1/suppliers/facets").json()
    names = {d["name"]: d["supplier_count"] for d in facets["destinations"]}
    assert names == {"Jaipur": 2, "Udaipur": 1}
    assert facets["categories"] == ["Budget", "Luxury"]
