"""Phase 4 — internal costing XLSX: build-up + totals from the frozen snapshot."""

from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from tests.test_api_itinerary_quote import _setup, api  # noqa: F401 — `api` is a fixture


def _quote_orm(quote_id: str):
    from app.api.deps import current_org_id
    from app.db import get_session
    from app.main import app
    from app.models import Itinerary, Project, Quote

    session = next(app.dependency_overrides[get_session]())
    org_id = app.dependency_overrides[current_org_id]()
    quote = session.get(Quote, quote_id)
    assert quote is not None and quote.org_id == org_id
    return quote, session.get(Project, quote.project_id), session.get(Itinerary, quote.itinerary_id)


def test_costing_workbook_has_buildup_and_margin(api: TestClient) -> None:
    itinerary_id, _ = _setup(api)
    quote = api.post(f"/api/v1/itineraries/{itinerary_id}/quotes",
                     json={"buyer_state_code": "05", "fx_currency": "USD", "fx_rate": "95"}).json()

    from app.services.costing_xlsx import render_costing_xlsx

    q, project, itinerary = _quote_orm(quote["id"])
    xlsx = render_costing_xlsx(q, project, itinerary)
    assert xlsx[:2] == b"PK"  # a zip / xlsx

    wb = load_workbook(BytesIO(xlsx))
    assert wb.sheetnames == ["Costing", "Cost inputs", "Build-up"]

    numbers = {round(c.value, 4) for row in wb["Costing"].iter_rows() for c in row
               if isinstance(c.value, (int, float))}
    assert 336050.0 in numbers   # total cost
    assert 67277.0 in numbers    # profit
    assert 403327.0 in numbers   # group gross
    assert round(0.1252, 4) in numbers  # true margin as a fraction

    # The build-up trace sheet carries the per-contribution lines.
    trace_labels = [c.value for row in wb["Build-up"].iter_rows() for c in row]
    assert "accommodation" in trace_labels or "shared" in trace_labels


def test_costing_endpoint(api: TestClient) -> None:
    itinerary_id, _ = _setup(api)
    quote = api.post(f"/api/v1/itineraries/{itinerary_id}/quotes",
                     json={"buyer_state_code": "05", "fx_rate": "95"}).json()
    res = api.get(f"/api/v1/quotes/{quote['id']}/costing.xlsx")
    assert res.status_code == 200
    assert "spreadsheetml" in res.headers["content-type"]
    assert res.content[:2] == b"PK"
