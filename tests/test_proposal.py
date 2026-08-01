"""Phase 4 — client proposal: data assembly (no internal figures) + PDF render.

Uses the Jaipur golden itinerary/quote over HTTP so the proposal reflects real
day/component/pricing data.
"""

from __future__ import annotations

from decimal import Decimal

from app.services.proposal_pdf import render_proposal_pdf
from fastapi.testclient import TestClient

from tests.test_api_itinerary_quote import _setup, api  # noqa: F401 — `api` is a fixture


def test_proposal_hides_internal_lines_and_prices_per_person(api: TestClient) -> None:
    itinerary_id, _ = _setup(api)
    quote = api.post(f"/api/v1/itineraries/{itinerary_id}/quotes",
                     json={"buyer_state_code": "05", "fx_currency": "USD", "fx_rate": "95"}).json()

    from app.api.deps import current_org_id
    from app.db import get_session
    from app.main import app
    from app.services.proposal import build_proposal

    session = next(app.dependency_overrides[get_session]())
    org_id = app.dependency_overrides[current_org_id]()
    data = build_proposal(session, org_id, quote["id"])

    assert data["title"] == "Jaipur / Golden Triangle"
    assert data["nights"] == 5
    assert len(data["days"]) == 6
    # Per-person prices come through per traveller group.
    prices = {g["label"]: g["per_pax_inr"] for g in data["groups"]}
    assert prices["Foreign Double"] == "47303.00"
    assert data["total_inr"] == "403327.00"
    assert data["total_fx"] == "4245.55"  # 403327 / 95
    # Inclusions are friendly labels; the raw internal cost lines never leak.
    blob = " ".join(data["inclusions"]).lower()
    assert "accommodation" in blob
    assert "rohan" not in blob and "misc" not in blob and "ta/da" not in blob


def test_proposal_pdf_endpoint(api: TestClient) -> None:
    itinerary_id, _ = _setup(api)
    quote = api.post(f"/api/v1/itineraries/{itinerary_id}/quotes",
                     json={"buyer_state_code": "05", "fx_rate": "95"}).json()
    res = api.get(f"/api/v1/quotes/{quote['id']}/proposal.pdf")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content[:5] == b"%PDF-"


def test_render_from_minimal_data() -> None:
    pdf = render_proposal_pdf({
        "seller_name": "RootsVida", "client_name": "Guest", "project_code": "TP1",
        "title": "Sample", "start_date": "2026-07-18", "end_date": "2026-07-20",
        "nights": 2, "valid_until": "2026-07-01", "fx_currency": "USD",
        "total_inr": "100000.00", "total_fx": str(Decimal("1052.63")),
        "days": [{"day_number": 1, "date": "2026-07-18", "destination": "Jaipur",
                  "narrative": "Arrive and explore."}],
        "inclusions": ["Accommodation as per the itinerary"],
        "groups": [{"label": "Foreign Double", "pax": 2, "per_pax_inr": "50000.00",
                    "per_pax_fx": "526.32"}],
    })
    assert pdf[:5] == b"%PDF-"
