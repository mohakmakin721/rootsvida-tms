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
from app.api.deps import current_org_id, current_user
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
    User,
)
from app.models.enums import MealPlan, Occupancy, SupplierKind, UserRole
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
    taj = Supplier(org_id=org.id, kind=SupplierKind.STAY, legal_name="Taj Jai Mahal Palace",
                   display_name="Taj Jai Mahal", destination_id=jaipur.id,
                   category="Luxury", property_type="Heritage", status="active")
    # A budget Jaipur hotel with only an EXPIRED rate.
    zostel = Supplier(org_id=org.id, kind=SupplierKind.STAY, legal_name="Zostel Jaipur",
                      display_name="Zostel Jaipur", destination_id=jaipur.id,
                      category="Budget", status="prospect")
    # A Udaipur hotel with no rates at all.
    lake = Supplier(org_id=org.id, kind=SupplierKind.STAY, legal_name="Lake Palace",
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

    owner = User(org_id=org.id, email="owner@qa.local", role=UserRole.OWNER, is_active=True)
    db_session.add(owner)
    db_session.flush()

    def _session() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[current_org_id] = lambda: org.id
    app.dependency_overrides[current_user] = lambda: owner
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

    # All three are 'stay' vendors now (accommodation consolidated).
    body = client.get("/api/v1/suppliers", params={"kind": "stay"}).json()
    assert {s["display_name"] for s in body["items"]} == {
        "Taj Jai Mahal", "Zostel Jaipur", "Lake Palace"
    }

    # Several kinds, comma-separated (still supported).
    body = client.get("/api/v1/suppliers", params={"kind": "stay,meal"}).json()
    assert len(body["items"]) == 3
    body = client.get("/api/v1/suppliers", params={"kind": "transport,guide"}).json()
    assert body["items"] == []


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


def test_type_specific_rates_per_vendor_kind(seeded) -> None:
    """Transport / guide / activity vendors capture their own rate shape, and the
    detail returns them with a freshness rollup across all rate types (#3)."""
    client, _ = seeded
    today = TODAY.isoformat()
    later = (TODAY + timedelta(days=300)).isoformat()

    # Transport vendor + a vehicle rate.
    tr = client.post("/api/v1/suppliers", json={
        "kind": "transport", "legal_name": "Rajasthan Cabs",
        "display_name": "Rajasthan Cabs", "status": "active"}).json()
    r = client.post(f"/api/v1/suppliers/{tr['id']}/transport-rates", json={
        "vehicle_class": "SUV", "vehicle_model": "Innova Crysta", "seats": 6,
        "basis": "per_day_8hr_80km", "amount": "4500",
        "valid_from": today, "valid_to": later})
    assert r.status_code == 201, r.text
    detail = client.get(f"/api/v1/suppliers/{tr['id']}").json()
    assert len(detail["transport_rates"]) == 1
    assert detail["transport_rates"][0]["vehicle_class"] == "SUV"
    assert detail["rate_count"] == 1 and detail["freshness"] == "fresh"

    # Guide vendor + a guide rate.
    gd = client.post("/api/v1/suppliers", json={
        "kind": "guide", "legal_name": "Jai Guide", "display_name": "Jai Guide",
        "status": "active"}).json()
    assert client.post(f"/api/v1/suppliers/{gd['id']}/guide-rates", json={
        "languages": ["English", "French"], "per_day": "3000",
        "valid_from": today, "valid_to": later}).status_code == 201
    gdetail = client.get(f"/api/v1/suppliers/{gd['id']}").json()
    assert gdetail["guide_rates"][0]["languages"] == ["English", "French"]

    # Activity vendor + a per-nationality ticket.
    ac = client.post("/api/v1/suppliers", json={
        "kind": "activity", "legal_name": "Amber Fort", "display_name": "Amber Fort",
        "status": "active"}).json()
    assert client.post(f"/api/v1/suppliers/{ac['id']}/activity-rates", json={
        "name": "Amber Fort entry", "pax_class": "foreign", "price_per_pax": "600",
        "valid_from": today, "valid_to": later}).status_code == 201
    adetail = client.get(f"/api/v1/suppliers/{ac['id']}").json()
    assert adetail["activity_rates"][0]["pax_class"] == "foreign"


def test_commercials_never_leak(seeded) -> None:
    """D-0002 — commission/margin must not appear in any browser payload."""
    client, ids = seeded
    listed = client.get("/api/v1/suppliers").text.lower()
    detail = client.get(f"/api/v1/suppliers/{ids['taj']}").text.lower()
    for blob in (listed, detail):
        assert "commission" not in blob
        assert "margin" not in blob
        assert "secret" not in blob


def test_facets_expose_destinations_states_and_categories(seeded) -> None:
    client, _ = seeded
    facets = client.get("/api/v1/suppliers/facets").json()
    names = {d["name"]: d["supplier_count"] for d in facets["destinations"]}
    assert names == {"Jaipur": 2, "Udaipur": 1}
    assert all(d["state"] == "Rajasthan" for d in facets["destinations"])
    assert facets["states"] == ["Rajasthan"]
    assert facets["categories"] == ["Budget", "Luxury"]


def test_filter_by_state(seeded) -> None:
    client, _ = seeded
    body = client.get("/api/v1/suppliers", params={"state": "Rajasthan"}).json()
    assert body["total"] == 3  # all three are in Rajasthan
    body = client.get("/api/v1/suppliers", params={"state": "Kerala"}).json()
    assert body["total"] == 0


def test_supplier_crud(seeded) -> None:
    client, ids = seeded
    # Create a supplier.
    created = client.post("/api/v1/suppliers", json={
        "kind": "stay", "legal_name": "New Hotel Pvt Ltd", "display_name": "New Hotel",
        "destination_id": str(ids["jaipur"]), "category": "Mid", "status": "prospect",
    })
    assert created.status_code == 201, created.text
    sid = created.json()["id"]

    # Edit it.
    edited = client.patch(f"/api/v1/suppliers/{sid}", json={"status": "active", "category": "Luxury"})
    assert edited.status_code == 200
    assert edited.json()["status"] == "active"

    # Add a room type, then a rate for it.
    rt = client.post(f"/api/v1/suppliers/{sid}/room-types", json={"name": "Suite"})
    assert rt.status_code == 201
    rate = client.post(f"/api/v1/suppliers/{sid}/rates", json={
        "room_type_id": rt.json()["id"], "meal_plan": "CP", "occupancy": "double",
        "amount": "9000", "valid_from": str(TODAY), "valid_to": str(TODAY + timedelta(days=90)),
    })
    assert rate.status_code == 201, rate.text
    assert client.get(f"/api/v1/suppliers/{sid}").json()["rate_count"] == 1

    # Add a contact.
    ct = client.post(f"/api/v1/suppliers/{sid}/contacts",
                     json={"person_name": "Asha", "email": "asha@new.example", "is_primary": True})
    assert ct.status_code == 201

    # Delete the rate → freshness drops to none.
    assert client.delete(f"/api/v1/suppliers/rates/{rate.json()['id']}").status_code == 204
    assert client.get(f"/api/v1/suppliers/{sid}").json()["rate_count"] == 0

    # Delete the supplier → it disappears from the browser.
    assert client.delete(f"/api/v1/suppliers/{sid}").status_code == 204
    assert client.get(f"/api/v1/suppliers/{sid}").status_code == 404


def test_overlapping_rate_is_409(seeded) -> None:
    client, ids = seeded
    # taj already has a CP/double rate (on its Deluxe room) spanning today; another
    # for the same room/plan/occupancy on overlapping dates conflicts (rates_no_overlap).
    existing = client.get(f"/api/v1/suppliers/{ids['taj']}").json()["rates"][0]
    resp = client.post(f"/api/v1/suppliers/{ids['taj']}/rates", json={
        "room_type_id": existing["room_type_id"],
        "meal_plan": "CP", "occupancy": "double", "amount": "8000",
        "valid_from": str(TODAY), "valid_to": str(TODAY + timedelta(days=5)),
    })
    assert resp.status_code == 409
