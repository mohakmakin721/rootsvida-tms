"""Tests for Milestone 10 deduplication: detection, candidate enqueue, merge."""

from __future__ import annotations

import uuid

from app.models import (
    Destination,
    RawImportRow,
    ReviewItem,
    SourceDocument,
    Supplier,
    SupplierContact,
)
from app.models.enums import (
    ParserStrategy,
    RawParseStatus,
    ReviewEntityType,
    SourceKind,
    SupplierKind,
)
from app.services import merge, review
from sqlalchemy.orm import Session

from ingestion.dedup import (
    SupplierRec,
    enqueue_merge_candidates,
    find_duplicate_pairs,
    normalize_name,
)

# --------------------------------------------------------------------------- #
# detection (no DB)
# --------------------------------------------------------------------------- #


def _rec(name: str, dest: uuid.UUID | None = None) -> SupplierRec:
    return SupplierRec(uuid.uuid4(), name, dest)


def test_normalize_name_strips_punct_and_case() -> None:
    assert normalize_name("The Taj-Hari Mahal!") == "the taj hari mahal"


def test_exact_duplicate_within_destination_scores_one() -> None:
    d = uuid.uuid4()
    pairs = find_duplicate_pairs([_rec("28 Kothi", d), _rec("28 kothi ", d)])
    assert len(pairs) == 1
    assert pairs[0].score == 1.0


def test_pairs_are_scoped_to_destination() -> None:
    # Identical names in DIFFERENT destinations are not a pair.
    assert find_duplicate_pairs([_rec("Utsav Camp", uuid.uuid4()),
                                 _rec("Utsav Camp", uuid.uuid4())]) == []


def test_fuzzy_match_respects_threshold() -> None:
    d = uuid.uuid4()
    near = [_rec("Samode Haveli", d), _rec("Samode Havelli", d)]
    assert len(find_duplicate_pairs(near, threshold=0.8)) == 1
    assert find_duplicate_pairs(near, threshold=0.99) == []
    far = [_rec("Ananta Spa", d), _rec("Taj Palace", d)]
    assert find_duplicate_pairs(far, threshold=0.6) == []


# --------------------------------------------------------------------------- #
# enqueue + merge (DB-backed; rolled back)
# --------------------------------------------------------------------------- #


def _fresh_org(session: Session) -> uuid.UUID:
    from app.models import Organization

    org = Organization(name="Dedup QA", slug=f"dd-{uuid.uuid4().hex[:8]}")
    session.add(org)
    session.flush()
    return org.id


def _supplier(session: Session, org_id: uuid.UUID, name: str, dest: uuid.UUID) -> Supplier:
    s = Supplier(
        org_id=org_id, kind=SupplierKind.HOTEL, legal_name=name,
        display_name=name, destination_id=dest,
    )
    session.add(s)
    session.flush()
    return s


def _dest(session: Session, org_id: uuid.UUID) -> uuid.UUID:
    d = Destination(org_id=org_id, name="Jaipur", state="Rajasthan", country="IN")
    session.add(d)
    session.flush()
    return d.id


def test_enqueue_merge_candidates_is_idempotent(db_session: Session) -> None:
    org_id = _fresh_org(db_session)
    dest = _dest(db_session, org_id)
    _supplier(db_session, org_id, "Samode House", dest)
    _supplier(db_session, org_id, "samode house", dest)
    _supplier(db_session, org_id, "Alila Fort", dest)  # unrelated

    assert enqueue_merge_candidates(db_session, org_id, threshold=0.9) == 1
    assert enqueue_merge_candidates(db_session, org_id, threshold=0.9) == 0  # idempotent

    items = review.list_items(db_session, org_id, entity_type=ReviewEntityType.MERGE_CANDIDATE)
    assert len(items) == 1
    assert {"primary", "duplicate", "score"} <= set(items[0].proposed)
    assert items[0].confidence is not None


def test_apply_merge_repoints_and_soft_deletes(db_session: Session) -> None:
    org_id = _fresh_org(db_session)
    dest = _dest(db_session, org_id)
    _supplier(db_session, org_id, "Taj Hari Mahal", dest)
    _supplier(db_session, org_id, "taj hari mahal", dest)

    assert enqueue_merge_candidates(db_session, org_id, threshold=0.9) == 1
    item = review.list_items(db_session, org_id, entity_type=ReviewEntityType.MERGE_CANDIDATE)[0]
    primary_id = uuid.UUID(str(item.proposed["primary"]["id"]))
    dup_id = uuid.UUID(str(item.proposed["duplicate"]["id"]))

    # Attach a contact and a staged-row link to the duplicate, to be repointed.
    contact = SupplierContact(
        org_id=org_id, supplier_id=dup_id, is_primary=True, phone_e164="+919000000000"
    )
    doc = SourceDocument(
        org_id=org_id, kind=SourceKind.LEGACY_XLSX, filename="H.xlsx",
        origin="H.xlsx", sha256=uuid.uuid4().hex,
    )
    db_session.add_all([contact, doc])
    db_session.flush()
    raw = RawImportRow(
        org_id=org_id, source_document_id=doc.id, sheet_name="Rajasthan",
        row_number=9, raw_values={}, parser_strategy=ParserStrategy.MECHANICAL,
        parse_status=RawParseStatus.PARSED, normalized_supplier_id=dup_id,
    )
    db_session.add(raw)
    db_session.flush()

    result = merge.apply_merge(db_session, org_id, item)
    assert result["merged"] is True

    assert db_session.get(Supplier, dup_id).deleted_at is not None
    assert db_session.get(Supplier, primary_id).deleted_at is None
    assert db_session.get(SupplierContact, contact.id).supplier_id == primary_id
    assert db_session.get(RawImportRow, raw.id).normalized_supplier_id == primary_id

    # Re-applying is a no-op (duplicate already merged).
    assert merge.apply_merge(db_session, org_id, item)["merged"] is False


def test_apply_merge_rejects_non_merge_item(db_session: Session) -> None:
    import pytest

    org_id = _fresh_org(db_session)
    item = review.enqueue(
        db_session, org_id, entity_type=ReviewEntityType.SUPPLIER, proposed={}
    )
    with pytest.raises(merge.MergeError):
        merge.apply_merge(db_session, org_id, item)


def test_merge_candidate_count_matches_items(db_session: Session) -> None:
    org_id = _fresh_org(db_session)
    dest = _dest(db_session, org_id)
    _supplier(db_session, org_id, "Utsav Camp", dest)
    _supplier(db_session, org_id, "Utsav Camp", dest)
    enqueue_merge_candidates(db_session, org_id, threshold=0.9)
    n = db_session.query(ReviewItem).filter(
        ReviewItem.org_id == org_id,
        ReviewItem.entity_type == ReviewEntityType.MERGE_CANDIDATE,
    ).count()
    assert n == 1
