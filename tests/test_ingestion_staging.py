"""Tests for the Milestone 5 raw ingestion / staging framework.

Split in two: pure-unit tests for hashing and workbook reading (no database),
and DB-backed tests for the idempotent upsert into `raw_import_rows` (skipped
when no Postgres is reachable, run in a rolled-back transaction).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from app.models import RawImportRow, SourceDocument
from app.models.enums import ParserStrategy, RawParseStatus, SourceKind
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from ingestion.hashing import content_fingerprint, sha256_file
from ingestion.mappings import SheetSpec, resolve_spec
from ingestion.source import get_or_create_source_document, resolve_org_id
from ingestion.staging import StagedRow, stage_rows, stage_sheet
from ingestion.workbook import read_sheet_rows

# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _make_workbook(path: Path, sheet: str, matrix: list[list[object]]) -> Path:
    """Write `matrix` (list of rows) to `sheet` in a new .xlsx at `path`."""
    wb = Workbook()
    ws = wb.active
    ws.title = sheet
    for row in matrix:
        ws.append(row)
    wb.save(path)
    return path


def _ensure_org(session: Session) -> uuid.UUID:
    """Ensure the configured org exists in the current transaction; return its id."""
    from app.config import get_settings
    from app.models import Organization

    s = get_settings()
    org = session.scalar(select(Organization).where(Organization.slug == s.rv_org_slug))
    if org is None:
        org = Organization(name=s.rv_org_name, slug=s.rv_org_slug)
        session.add(org)
        session.flush()
    return org.id


# --------------------------------------------------------------------------- #
# hashing (no DB)
# --------------------------------------------------------------------------- #


def test_sha256_file_matches_known_bytes(tmp_path: Path) -> None:
    import hashlib

    p = tmp_path / "blob.bin"
    p.write_bytes(b"rootsvida")
    assert sha256_file(p) == hashlib.sha256(b"rootsvida").hexdigest()


def test_content_fingerprint_is_key_order_independent() -> None:
    a = content_fingerprint({"name": "Paawana", "place": "Mandawa"})
    b = content_fingerprint({"place": "Mandawa", "name": "Paawana"})
    assert a == b


def test_content_fingerprint_changes_with_value() -> None:
    a = content_fingerprint({"price": "5000-8000"})
    b = content_fingerprint({"price": "10000 and above"})
    assert a != b


# --------------------------------------------------------------------------- #
# workbook reading (no DB)
# --------------------------------------------------------------------------- #


def test_read_sheet_captures_rows_verbatim(tmp_path: Path) -> None:
    wb = _make_workbook(
        tmp_path / "w.xlsx",
        "S",
        [
            ["Name", "Price"],
            ["Paawana Haveli", "5000-8000"],
            ["Tree of Life", "5000-8000"],
        ],
    )
    rows = list(read_sheet_rows(wb, SheetSpec("S", ParserStrategy.MECHANICAL)))
    assert [r.row_number for r in rows] == [2, 3]  # real Excel row numbers
    assert rows[0].values == {"Name": "Paawana Haveli", "Price": "5000-8000"}


def test_read_sheet_honours_header_row_and_skips_empties(tmp_path: Path) -> None:
    wb = _make_workbook(
        tmp_path / "w.xlsx",
        "Rajasthan",
        [
            ["We need some budget properties too", None],  # title row
            ["S.no.", "Name"],  # header on row 2
            [1, "Homestay"],
            [None, None],  # fully empty -> skipped
            [2, "Paawana Haveli"],
        ],
    )
    spec = SheetSpec("Rajasthan", ParserStrategy.MECHANICAL, header_row=2)
    rows = list(read_sheet_rows(wb, spec))
    assert [r.row_number for r in rows] == [3, 5]
    assert rows[0].values == {"S.no.": 1, "Name": "Homestay"}


def test_read_sheet_names_blank_headers_positionally(tmp_path: Path) -> None:
    wb = _make_workbook(
        tmp_path / "w.xlsx", "S", [["Name", None, "Name"], ["a", "b", "c"]]
    )
    rows = list(read_sheet_rows(wb, SheetSpec("S", ParserStrategy.MECHANICAL)))
    # blank header -> positional; duplicate "Name" -> suffixed
    assert rows[0].values == {"Name": "a", "column_2": "b", "Name_2": "c"}


def test_read_sheet_coerces_datetime_to_iso(tmp_path: Path) -> None:
    wb = _make_workbook(
        tmp_path / "w.xlsx",
        "S",
        [["When"], [datetime(2026, 7, 30, 9, 0, 0)]],  # noqa: DTZ001 — Excel datetimes are naive
    )
    rows = list(read_sheet_rows(wb, SheetSpec("S", ParserStrategy.MECHANICAL)))
    assert rows[0].values["When"] == "2026-07-30T09:00:00"


# --------------------------------------------------------------------------- #
# registry (no DB)
# --------------------------------------------------------------------------- #


def test_registry_knows_rajasthan_header_offset() -> None:
    spec = resolve_spec("Rajasthan")
    assert spec.header_row == 2
    assert spec.parser_strategy is ParserStrategy.MECHANICAL


def test_registry_defaults_unknown_sheet_to_mechanical() -> None:
    spec = resolve_spec("Some Unseen Sheet")
    assert spec.parser_strategy is ParserStrategy.MECHANICAL
    assert spec.workbook is None  # caller must supply the file


# --------------------------------------------------------------------------- #
# staging (DB-backed; rolled back)
# --------------------------------------------------------------------------- #


def test_source_document_is_idempotent_on_bytes(db_session: Session, tmp_path: Path) -> None:
    org_id = _ensure_org(db_session)
    wb = _make_workbook(tmp_path / "w.xlsx", "S", [["Name"], ["Paawana"]])

    doc1, created1 = get_or_create_source_document(db_session, org_id, wb)
    doc2, created2 = get_or_create_source_document(db_session, org_id, wb)

    assert created1 is True and created2 is False
    assert doc1.id == doc2.id
    assert doc1.kind is SourceKind.LEGACY_XLSX


def test_stage_sheet_end_to_end_and_idempotent(db_session: Session, tmp_path: Path) -> None:
    _ensure_org(db_session)
    wb = _make_workbook(
        tmp_path / "w.xlsx",
        "TestSheet",
        [["Name", "Price"], ["Paawana", "5000-8000"], ["Serai", "10000+"]],
    )

    first = stage_sheet(db_session, str(wb), "TestSheet")
    assert first.source_created is True
    assert (first.result.inserted, first.result.updated, first.result.unchanged) == (2, 0, 0)

    # Re-staging the identical file reuses the source and touches nothing.
    second = stage_sheet(db_session, str(wb), "TestSheet")
    assert second.source_created is False
    assert (second.result.inserted, second.result.updated, second.result.unchanged) == (0, 0, 2)

    staged = db_session.scalars(
        select(RawImportRow).where(
            RawImportRow.source_document_id == first.source_document.id
        )
    ).all()
    assert len(staged) == 2
    assert {r.row_number for r in staged} == {2, 3}
    assert all(r.parse_status is RawParseStatus.PENDING for r in staged)
    row2 = next(r for r in staged if r.row_number == 2)
    assert row2.raw_values == {"Name": "Paawana", "Price": "5000-8000"}


def test_stage_rows_updates_changed_content(db_session: Session) -> None:
    org_id = _ensure_org(db_session)
    doc = SourceDocument(
        org_id=org_id,
        kind=SourceKind.LEGACY_XLSX,
        filename="synthetic.xlsx",
        origin="synthetic.xlsx",
        sha256=uuid.uuid4().hex,  # unique so (org, sha256) never collides
    )
    db_session.add(doc)
    db_session.flush()
    spec = SheetSpec("S", ParserStrategy.MECHANICAL)

    assert stage_rows(db_session, doc, spec, [StagedRow(2, {"a": "1"})]).inserted == 1
    assert stage_rows(db_session, doc, spec, [StagedRow(2, {"a": "1"})]).unchanged == 1

    changed = stage_rows(db_session, doc, spec, [StagedRow(2, {"a": "2"})])
    assert changed.updated == 1

    row = db_session.scalar(
        select(RawImportRow).where(
            RawImportRow.source_document_id == doc.id, RawImportRow.row_number == 2
        )
    )
    assert row is not None
    assert row.raw_values == {"a": "2"}
    assert row.parse_status is RawParseStatus.PENDING


def test_resolve_org_id_raises_when_unseeded(db_session: Session) -> None:
    import pytest

    with pytest.raises(LookupError):
        resolve_org_id(db_session, slug="definitely-not-a-seeded-slug")
