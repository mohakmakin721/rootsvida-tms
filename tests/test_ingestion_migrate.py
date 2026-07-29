"""Tests for the Milestone 6 migration (staged rows -> canonical suppliers).

Pure-unit tests for the mechanical normaliser, plus DB-backed tests for the
idempotent upsert into `suppliers` / `supplier_contacts` / `destinations`
(skipped without Postgres, run in a rolled-back transaction).
"""

from __future__ import annotations

import uuid

from app.models import (
    Destination,
    RawImportRow,
    SourceDocument,
    Supplier,
    SupplierContact,
)
from app.models.enums import ParserStrategy, RawParseStatus, SourceKind, SupplierKind
from sqlalchemy import select
from sqlalchemy.orm import Session

from ingestion.migrate import get_or_create_destination, migrate_sheet
from ingestion.normalize import NormalizedContact, normalize_phone, normalize_rajasthan

# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _row(**over: object) -> dict[str, object]:
    """A Rajasthan-shaped raw row with sensible defaults, overridable per test."""
    base: dict[str, object] = {
        "S.no.": 1.0,
        "Name": "Paawana Haveli",
        "Place": "Mandawa",
        "Category": "Luxury",
        "Type": "Heritage Hotel",
        "Contact": 9928655588.0,
        "Extra features": "Rural Feel",
        "Website": "http://paawanahaveli.com/",
        "Email id": None,
        "Price Range": "5000-8000",
        "Status": None,
        "Remarks": "no reply so far ",
    }
    base.update(over)
    return base


def _ensure_org(session: Session) -> uuid.UUID:
    from app.config import get_settings
    from app.models import Organization

    s = get_settings()
    org = session.scalar(select(Organization).where(Organization.slug == s.rv_org_slug))
    if org is None:
        org = Organization(name=s.rv_org_name, slug=s.rv_org_slug)
        session.add(org)
        session.flush()
    return org.id


def _seed_source(
    session: Session, org_id: uuid.UUID, rows: list[tuple[int, dict[str, object]]]
) -> SourceDocument:
    doc = SourceDocument(
        org_id=org_id,
        kind=SourceKind.LEGACY_XLSX,
        filename="Hotels Database.xlsx",
        origin="Hotels Database.xlsx",
        sha256=uuid.uuid4().hex,
    )
    session.add(doc)
    session.flush()
    for row_number, values in rows:
        session.add(
            RawImportRow(
                org_id=org_id,
                source_document_id=doc.id,
                sheet_name="Rajasthan",
                row_number=row_number,
                raw_values=values,
                row_hash=uuid.uuid4().hex,
                parser_strategy=ParserStrategy.MECHANICAL,
                parse_status=RawParseStatus.PENDING,
            )
        )
    session.flush()
    return doc


def _row_of(session: Session, doc: SourceDocument, row_number: int) -> RawImportRow:
    """Fetch a staged row scoped to `doc` — the dev DB may already hold committed
    Rajasthan rows from a real ingest, so tests must never query by row_number alone."""
    row = session.scalar(
        select(RawImportRow).where(
            RawImportRow.source_document_id == doc.id,
            RawImportRow.row_number == row_number,
        )
    )
    assert row is not None
    return row


# --------------------------------------------------------------------------- #
# normalisation (no DB)
# --------------------------------------------------------------------------- #


def test_normalize_phone_indian_mobile() -> None:
    assert normalize_phone(9928655588.0) == ("9928655588", "+919928655588")


def test_normalize_phone_strips_country_and_trunk_prefixes() -> None:
    assert normalize_phone("919928655588")[1] == "+919928655588"
    assert normalize_phone("09928655588")[1] == "+919928655588"


def test_normalize_phone_keeps_unrecognised_raw_without_guessing() -> None:
    raw, e164 = normalize_phone("via mail only info@x.com")
    assert raw == "via mail only info@x.com"
    assert e164 is None  # a landline / prose is preserved, never invented


def test_normalize_phone_none() -> None:
    assert normalize_phone(None) == (None, None)


def test_normalize_rajasthan_maps_core_fields() -> None:
    norm = normalize_rajasthan(_row())
    assert norm is not None
    assert norm.kind is SupplierKind.HOTEL
    assert norm.display_name == "Paawana Haveli"
    assert norm.category == "Luxury"
    assert norm.property_type == "Heritage Hotel"
    assert norm.destination_name == "Mandawa"
    assert norm.destination_state == "Rajasthan"
    assert norm.tags == ["Rural Feel"]
    assert norm.has_destination is True
    assert isinstance(norm.contact, NormalizedContact)
    assert norm.contact.phone_e164 == "+919928655588"


def test_normalize_rajasthan_detects_homestay() -> None:
    norm = normalize_rajasthan(_row(Name="Green Homestay", Type=None))
    assert norm is not None
    assert norm.kind is SupplierKind.HOMESTAY


def test_normalize_rajasthan_blank_name_is_unmappable() -> None:
    assert normalize_rajasthan(_row(Name=None)) is None
    assert normalize_rajasthan(_row(Name="   ")) is None


def test_normalize_rajasthan_missing_place_has_no_destination() -> None:
    norm = normalize_rajasthan(_row(Place=None))
    assert norm is not None
    assert norm.has_destination is False


def test_normalize_rajasthan_flags_unusable_contact_from_remarks() -> None:
    # No parseable phone + a "no reply" remark -> unusable_reason surfaced.
    norm = normalize_rajasthan(_row(Contact=None, Remarks="no reply so far"))
    assert norm is not None
    assert norm.contact is not None
    assert norm.contact.unusable_reason == "no reply so far"


# --------------------------------------------------------------------------- #
# migration (DB-backed; rolled back)
# --------------------------------------------------------------------------- #


def test_migrate_creates_supplier_contact_and_destination(db_session: Session) -> None:
    org_id = _ensure_org(db_session)
    doc = _seed_source(db_session, org_id, [(3, _row())])

    result = migrate_sheet(db_session, doc, "Rajasthan")
    assert (result.created, result.updated, result.needs_review) == (1, 0, 0)

    row = _row_of(db_session, doc, 3)
    assert row.parse_status is RawParseStatus.PARSED

    supplier = db_session.get(Supplier, row.normalized_supplier_id)
    assert supplier is not None
    assert supplier.display_name == "Paawana Haveli"
    assert supplier.kind is SupplierKind.HOTEL
    assert supplier.status == "prospect"

    dest = db_session.get(Destination, supplier.destination_id)
    assert dest is not None and dest.name == "Mandawa" and dest.state == "Rajasthan"

    contact = db_session.scalar(
        select(SupplierContact).where(SupplierContact.supplier_id == supplier.id)
    )
    assert contact is not None and contact.phone_e164 == "+919928655588"


def test_migrate_is_idempotent(db_session: Session) -> None:
    org_id = _ensure_org(db_session)
    doc = _seed_source(db_session, org_id, [(3, _row()), (4, _row(Name="Tree of Life"))])

    first = migrate_sheet(db_session, doc, "Rajasthan")
    assert first.created == 2

    second = migrate_sheet(db_session, doc, "Rajasthan")
    assert (second.created, second.updated) == (0, 2)

    # Scoped to this doc's rows: two distinct suppliers, no duplication on re-run.
    linked = db_session.scalars(
        select(RawImportRow.normalized_supplier_id).where(
            RawImportRow.source_document_id == doc.id,
            RawImportRow.normalized_supplier_id.is_not(None),
        )
    ).all()
    assert len(linked) == 2 and len(set(linked)) == 2


def test_migrate_flags_blank_name_as_needs_review(db_session: Session) -> None:
    org_id = _ensure_org(db_session)
    doc = _seed_source(db_session, org_id, [(3, _row(Name=None))])

    result = migrate_sheet(db_session, doc, "Rajasthan")
    assert result.needs_review == 1
    assert result.created == 0

    row = _row_of(db_session, doc, 3)
    assert row.parse_status is RawParseStatus.NEEDS_REVIEW
    assert row.normalized_supplier_id is None


def test_migrate_marks_missing_place_partial(db_session: Session) -> None:
    org_id = _ensure_org(db_session)
    doc = _seed_source(db_session, org_id, [(3, _row(Place=None))])

    result = migrate_sheet(db_session, doc, "Rajasthan")
    assert result.partial == 1
    assert result.created == 1

    row = _row_of(db_session, doc, 3)
    assert row.parse_status is RawParseStatus.PARTIAL


def test_migrate_unknown_sheet_raises(db_session: Session) -> None:
    import pytest

    org_id = _ensure_org(db_session)
    doc = _seed_source(db_session, org_id, [])
    with pytest.raises(KeyError):
        migrate_sheet(db_session, doc, "Not A Registered Sheet")


def test_get_or_create_destination_dedupes(db_session: Session) -> None:
    org_id = _ensure_org(db_session)
    d1 = get_or_create_destination(db_session, org_id, "Jaipur", "Rajasthan")
    d2 = get_or_create_destination(db_session, org_id, "Jaipur", "Rajasthan")
    assert d1.id == d2.id
