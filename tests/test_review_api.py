"""API-level tests for the Milestone 8 review-queue endpoints.

The FastAPI `get_session` and `current_org_id` dependencies are overridden so the
endpoints run inside the test's rolled-back transaction under a fresh, isolated
org — no commit reaches the dev DB.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from app.api.deps import current_org_id
from app.db import get_session
from app.main import app
from app.models import Organization, RawImportRow, SourceDocument
from app.models.enums import ParserStrategy, RawParseStatus, SourceKind
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


@pytest.fixture
def api(db_session: Session) -> Iterator[tuple[TestClient, uuid.UUID]]:
    org = Organization(name="API QA", slug=f"api-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    db_session.flush()

    def _session_override() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_session] = _session_override
    app.dependency_overrides[current_org_id] = lambda: org.id
    try:
        yield TestClient(app), org.id
    finally:
        app.dependency_overrides.clear()


def _create(client: TestClient, **over: object) -> dict:
    body = {"entity_type": "supplier", "proposed": {"display_name": "Test Hotel"}}
    body.update(over)
    resp = client.post("/api/v1/review-queue", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_create_list_get(api: tuple[TestClient, uuid.UUID]) -> None:
    client, _ = api
    created = _create(client)
    assert created["status"] == "pending"
    assert created["entity_type"] == "supplier"

    listed = client.get("/api/v1/review-queue").json()
    assert any(i["id"] == created["id"] for i in listed)

    fetched = client.get(f"/api/v1/review-queue/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == created["id"]


def test_get_missing_is_404(api: tuple[TestClient, uuid.UUID]) -> None:
    client, _ = api
    resp = client.get(f"/api/v1/review-queue/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_approve_then_second_decision_conflicts(api: tuple[TestClient, uuid.UUID]) -> None:
    client, _ = api
    item = _create(client)
    approved = client.post(
        f"/api/v1/review-queue/{item['id']}/approve", json={"notes": "ok"}
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["reviewer_notes"] == "ok"

    conflict = client.post(f"/api/v1/review-queue/{item['id']}/reject", json={})
    assert conflict.status_code == 409


def test_edit_changes_proposed_and_status(api: tuple[TestClient, uuid.UUID]) -> None:
    client, _ = api
    item = _create(client)
    resp = client.post(
        f"/api/v1/review-queue/{item['id']}/edit",
        json={"proposed": {"display_name": "Edited Hotel"}, "notes": "fixed name"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "edited"
    assert body["proposed"] == {"display_name": "Edited Hotel"}


def test_list_status_filter(api: tuple[TestClient, uuid.UUID]) -> None:
    client, _ = api
    keep = _create(client)
    decided = _create(client)
    client.post(f"/api/v1/review-queue/{decided['id']}/reject", json={})

    pending = client.get("/api/v1/review-queue", params={"status": "pending"}).json()
    ids = {i["id"] for i in pending}
    assert keep["id"] in ids
    assert decided["id"] not in ids


def test_import_staging_enqueues_needs_review(
    api: tuple[TestClient, uuid.UUID], db_session: Session
) -> None:
    client, org_id = api
    doc = SourceDocument(
        org_id=org_id, kind=SourceKind.LEGACY_XLSX, filename="H.xlsx",
        origin="H.xlsx", sha256=uuid.uuid4().hex,
    )
    db_session.add(doc)
    db_session.flush()
    for rn in (3, 4):
        db_session.add(
            RawImportRow(
                org_id=org_id, source_document_id=doc.id, sheet_name="Rajasthan",
                row_number=rn, raw_values={"x": rn},
                parser_strategy=ParserStrategy.MECHANICAL,
                parse_status=RawParseStatus.NEEDS_REVIEW,
            )
        )
    db_session.flush()

    resp = client.post("/api/v1/review-queue/import-staging")
    assert resp.status_code == 200
    assert resp.json() == {"created": 2}


def test_approving_merge_candidate_executes_merge(
    api: tuple[TestClient, uuid.UUID], db_session: Session
) -> None:
    from app.models import Destination, Supplier
    from app.models.enums import SupplierKind

    from ingestion.dedup import enqueue_merge_candidates

    client, org_id = api
    dest = Destination(org_id=org_id, name="Jaipur", state="Rajasthan", country="IN")
    db_session.add(dest)
    db_session.flush()
    for name in ("Utsav Camp", "utsav camp"):
        db_session.add(
            Supplier(
                org_id=org_id, kind=SupplierKind.STAY, legal_name=name,
                display_name=name, destination_id=dest.id,
            )
        )
    db_session.flush()
    assert enqueue_merge_candidates(db_session, org_id, threshold=0.9) == 1

    items = client.get(
        "/api/v1/review-queue",
        params={"status": "pending", "entity_type": "merge_candidate"},
    ).json()
    assert len(items) == 1
    item = items[0]

    resp = client.post(f"/api/v1/review-queue/{item['id']}/approve", json={})
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"

    dup_id = uuid.UUID(str(item["proposed"]["duplicate"]["id"]))
    assert db_session.get(Supplier, dup_id).deleted_at is not None
