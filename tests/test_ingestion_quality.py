"""Tests for the Milestone 7 data-quality report.

The DB-backed test seeds a *fresh* org (everything is org-scoped) so the counts
are deterministic regardless of the Rajasthan data already committed to the dev
DB. A separate no-DB test covers rendering.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.models import (
    Destination,
    Organization,
    RawImportRow,
    SourceDocument,
    Supplier,
    SupplierContact,
)
from app.models.enums import ParserStrategy, RawParseStatus, SourceKind, SupplierKind
from sqlalchemy.orm import Session

from ingestion.quality import Check, QualityReport, build_report, render_report


def _chk(report: QualityReport, key: str) -> Check:
    return next(c for c in report.checks if c.key == key)


def _fresh_org(session: Session) -> uuid.UUID:
    org = Organization(name="QA Org", slug=f"qa-{uuid.uuid4().hex[:8]}")
    session.add(org)
    session.flush()
    return org.id


def _seed(session: Session, org_id: uuid.UUID) -> None:
    doc = SourceDocument(
        org_id=org_id,
        kind=SourceKind.LEGACY_XLSX,
        filename="H.xlsx",
        origin="H.xlsx",
        sha256=uuid.uuid4().hex,
    )
    session.add(doc)
    session.flush()
    for row_number, status in (
        (3, RawParseStatus.PARSED),
        (4, RawParseStatus.PARSED),
        (5, RawParseStatus.PARTIAL),
        (6, RawParseStatus.NEEDS_REVIEW),
    ):
        session.add(
            RawImportRow(
                org_id=org_id,
                source_document_id=doc.id,
                sheet_name="Rajasthan",
                row_number=row_number,
                raw_values={},
                parser_strategy=ParserStrategy.MECHANICAL,
                parse_status=status,
            )
        )

    dest = Destination(org_id=org_id, name="Jaipur", state="Rajasthan", country="IN")
    session.add(dest)
    session.flush()

    def _supplier(name: str, destination_id: uuid.UUID | None) -> Supplier:
        s = Supplier(
            org_id=org_id,
            kind=SupplierKind.HOTEL,
            legal_name=name,
            display_name=name,
            destination_id=destination_id,
        )
        session.add(s)
        session.flush()
        return s

    reachable = _supplier("Alpha", dest.id)  # has destination + reachable contact
    session.add(
        SupplierContact(
            org_id=org_id, supplier_id=reachable.id, is_primary=True,
            phone_e164="+919000000000",
        )
    )
    _supplier("Beta", None)  # no destination, no contact -> unreachable
    dup1 = _supplier("Dup Hotel", dest.id)
    _supplier("dup hotel ", dest.id)  # same normalised name+destination as dup1
    session.add(
        SupplierContact(
            org_id=org_id, supplier_id=dup1.id, is_primary=True,
            phone_raw="0141-landline",  # kept, but not E.164 -> unreachable + unnormalised
        )
    )
    session.flush()


def test_report_summarises_staging_and_canonical(db_session: Session) -> None:
    org_id = _fresh_org(db_session)
    _seed(db_session, org_id)

    report = build_report(db_session, org_id)

    assert report.staging["raw_rows"] == 4
    assert report.staging["parsed"] == 2
    assert report.staging["partial"] == 1
    assert report.staging["needs_review"] == 1
    assert report.staging["parsed_pct"] == 50

    assert report.canonical == {"suppliers": 4, "destinations": 1, "contacts": 2}


def test_report_checks_flag_the_right_records(db_session: Session) -> None:
    org_id = _fresh_org(db_session)
    _seed(db_session, org_id)

    report = build_report(db_session, org_id)

    assert _chk(report, "rows_needs_review").count == 1
    assert _chk(report, "rows_partial").count == 1
    assert _chk(report, "supplier_without_destination").count == 1  # Beta
    # Beta (no contact), both Dup rows: Dup1's only contact has no E.164/email/site,
    # Dup2 has no contact -> 3 unreachable; Alpha is reachable.
    assert _chk(report, "supplier_unreachable").count == 3
    assert _chk(report, "phone_unnormalised").count == 1  # Dup1's landline
    assert _chk(report, "duplicate_name_in_destination").count == 1  # "dup hotel" x2


def test_render_is_ascii_and_has_headline() -> None:
    report = QualityReport(
        org_slug="acme",
        generated_at=datetime(2026, 7, 30, 12, 0, 0, tzinfo=timezone.utc),
        staging={
            "source_documents": 1, "raw_rows": 10, "parsed": 8, "parsed_pct": 80,
            "partial": 1, "needs_review": 1, "pending": 0,
        },
        canonical={"suppliers": 8, "destinations": 3, "contacts": 6},
        checks=[
            Check("rows_needs_review", "warn", 1, "staged rows with no usable identity",
                  ["Rajasthan row 5"]),
            Check("phone_unnormalised", "info", 2, "unnormalised phones"),
            Check("rows_error", "warn", 0, "errors"),  # not flagged (count 0)
        ],
    )
    out = render_report(report)

    assert out.isascii()  # CLI output must survive a Windows console
    assert "Data-quality report | acme |" in out
    assert "parsed 8/80%" in out
    assert "e.g. Rajasthan row 5" in out
    assert "1 warning(s), 1 info" in out  # the count-0 check is not flagged
    assert "errors" not in out
