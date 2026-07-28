"""Milestone 1 smoke tests — no database required.

These assert the scaffold is wired correctly: the app imports, the health and
API-ping endpoints work, config loads, and the ingestion CLI presents its
(intentionally not-yet-implemented) command surface.
"""

from __future__ import annotations

from app.config import get_settings
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_ok() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_api_v1_ping() -> None:
    resp = client.get("/api/v1/ping")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "api": "v1"}


def test_openapi_generates() -> None:
    # The frontend contract depends on this document generating cleanly.
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["title"].startswith("RootsVida TMS")


def test_settings_defaults() -> None:
    settings = get_settings()
    assert settings.rv_org_name == "Rootsvida Experiences Private Limited"
    # Phase 1 guardrails: LLM dormant by default.
    assert settings.rv_enable_llm is False


def test_commercial_visibility_rules() -> None:
    settings = get_settings()
    assert settings.can_view_commercials("owner") is True
    assert settings.can_view_commercials("ops_manager") is True
    # Below Ops Manager must never see commission/margin (DECISIONS.md D-0002).
    assert settings.can_view_commercials("sales") is False
    assert settings.can_view_commercials("accounts") is False
    assert settings.can_view_commercials("readonly") is False


def test_ingestion_cli_surface() -> None:
    from ingestion.cli import build_parser

    parser = build_parser()
    ns = parser.parse_args(["ingest", "--sheet", "Rajasthan"])
    assert ns.command == "ingest"
    assert ns.sheet == "Rajasthan"
