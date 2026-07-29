"""Service-level tests for the Milestone 8 review queue (DB-backed, rolled back)."""

from __future__ import annotations

import uuid

import pytest
from app.models import Organization, RawImportRow, SourceDocument, User
from app.models.enums import (
    ParserStrategy,
    RawParseStatus,
    ReviewEntityType,
    ReviewStatus,
    SourceKind,
    UserRole,
)
from app.services import review
from sqlalchemy.orm import Session


def _fresh_org(session: Session) -> uuid.UUID:
    org = Organization(name="Review QA", slug=f"rq-{uuid.uuid4().hex[:8]}")
    session.add(org)
    session.flush()
    return org.id


def _proposed() -> dict[str, str]:
    return {"display_name": "Some Hotel", "place": "Jaipur"}


def test_enqueue_is_idempotent_on_dedupe_key(db_session: Session) -> None:
    org_id = _fresh_org(db_session)
    first = review.enqueue(
        db_session, org_id, entity_type=ReviewEntityType.SUPPLIER,
        proposed=_proposed(), dedupe_key="k1",
    )
    again = review.enqueue(
        db_session, org_id, entity_type=ReviewEntityType.SUPPLIER,
        proposed={"display_name": "Different"}, dedupe_key="k1",
    )
    assert first.id == again.id
    assert again.proposed == _proposed()  # untouched — existing item returned


def test_list_filters_and_get_is_org_scoped(db_session: Session) -> None:
    org_id = _fresh_org(db_session)
    other_org = _fresh_org(db_session)
    a = review.enqueue(db_session, org_id, entity_type=ReviewEntityType.SUPPLIER, proposed={})
    review.enqueue(db_session, org_id, entity_type=ReviewEntityType.RATE, proposed={})
    review.approve(db_session, a)

    pending = review.list_items(db_session, org_id, status=ReviewStatus.PENDING)
    assert [i.entity_type for i in pending] == [ReviewEntityType.RATE]

    suppliers = review.list_items(db_session, org_id, entity_type=ReviewEntityType.SUPPLIER)
    assert len(suppliers) == 1

    assert review.get_item(db_session, org_id, a.id) is not None
    assert review.get_item(db_session, other_org, a.id) is None  # scoped out


def test_approve_records_audit_and_blocks_second_decision(db_session: Session) -> None:
    org_id = _fresh_org(db_session)
    user = User(
        org_id=org_id, email=f"r-{uuid.uuid4().hex[:6]}@example.com",
        role=UserRole.OPS_MANAGER,
    )
    db_session.add(user)
    db_session.flush()
    item = review.enqueue(db_session, org_id, entity_type=ReviewEntityType.SUPPLIER, proposed={})

    decided = review.approve(db_session, item, reviewed_by=user.id, notes="looks good")
    assert decided.status is ReviewStatus.APPROVED
    assert decided.reviewed_by == user.id
    assert decided.reviewed_at is not None
    assert decided.reviewer_notes == "looks good"

    with pytest.raises(review.ReviewStateError):
        review.reject(db_session, item)


def test_edit_replaces_proposed_and_marks_edited(db_session: Session) -> None:
    org_id = _fresh_org(db_session)
    item = review.enqueue(
        db_session, org_id, entity_type=ReviewEntityType.SUPPLIER, proposed=_proposed()
    )
    fixed = {"display_name": "Corrected Hotel", "place": "Jodhpur"}
    out = review.edit(db_session, item, fixed, notes="named it")
    assert out.status is ReviewStatus.EDITED
    assert out.proposed == fixed


def test_enqueue_needs_review_from_staging(db_session: Session) -> None:
    org_id = _fresh_org(db_session)
    doc = SourceDocument(
        org_id=org_id, kind=SourceKind.LEGACY_XLSX, filename="H.xlsx",
        origin="H.xlsx", sha256=uuid.uuid4().hex,
    )
    db_session.add(doc)
    db_session.flush()
    for rn, status in ((3, RawParseStatus.NEEDS_REVIEW), (4, RawParseStatus.NEEDS_REVIEW),
                       (5, RawParseStatus.PARSED)):
        db_session.add(
            RawImportRow(
                org_id=org_id, source_document_id=doc.id, sheet_name="Rajasthan",
                row_number=rn, raw_values={"x": rn}, parser_strategy=ParserStrategy.MECHANICAL,
                parse_status=status,
            )
        )
    db_session.flush()

    created = review.enqueue_needs_review(db_session, org_id)
    assert created == 2  # only the two needs_review rows
    assert review.enqueue_needs_review(db_session, org_id) == 0  # idempotent re-run

    items = review.list_items(db_session, org_id)
    assert len(items) == 2
    assert all(i.entity_type is ReviewEntityType.SUPPLIER for i in items)
    assert all(i.source_document_id == doc.id for i in items)
