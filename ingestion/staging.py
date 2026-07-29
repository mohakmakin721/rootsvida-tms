"""Stage verbatim rows into `raw_import_rows`, idempotently.

The staging framework's core operation (plan §30). Each row is upserted on its
natural key `(source_document, sheet, row_number)`:

  - not seen before        -> insert  (status PENDING)
  - seen, content changed   -> update  (new values + hash, status reset to PENDING)
  - seen, content identical -> skip    (nothing written)

The row hash is what makes a re-run cheap and safe: an unchanged source row does
no work, a changed one is refreshed and re-queued for parsing, and nothing is
ever duplicated. This is the guarantee `make reingest` (Milestone 11) relies on.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.models import RawImportRow, SourceDocument
from app.models.enums import RawParseStatus
from sqlalchemy import select
from sqlalchemy.orm import Session

from ingestion.hashing import content_fingerprint
from ingestion.mappings import SheetSpec, resolve_spec
from ingestion.source import get_or_create_source_document, resolve_org_id
from ingestion.workbook import StagedRow, read_sheet_rows


@dataclass(frozen=True)
class StageResult:
    """Per-sheet staging tally."""

    inserted: int = 0
    updated: int = 0
    unchanged: int = 0

    @property
    def total(self) -> int:
        return self.inserted + self.updated + self.unchanged


@dataclass(frozen=True)
class StageReport:
    """Outcome of staging one sheet: the source document plus the row tally."""

    source_document: SourceDocument
    source_created: bool
    spec: SheetSpec
    result: StageResult


def stage_rows(
    session: Session,
    source_document: SourceDocument,
    spec: SheetSpec,
    rows: Iterable[StagedRow],
) -> StageResult:
    """Upsert `rows` under `source_document`; return the insert/update/skip tally."""
    inserted = updated = unchanged = 0
    for row in rows:
        row_hash = content_fingerprint(row.values)
        existing = session.scalar(
            select(RawImportRow).where(
                RawImportRow.source_document_id == source_document.id,
                RawImportRow.sheet_name == spec.sheet_name,
                RawImportRow.row_number == row.row_number,
            )
        )
        if existing is None:
            session.add(
                RawImportRow(
                    org_id=source_document.org_id,
                    source_document_id=source_document.id,
                    sheet_name=spec.sheet_name,
                    row_number=row.row_number,
                    raw_values=row.values,
                    row_hash=row_hash,
                    parser_strategy=spec.parser_strategy,
                    parse_status=RawParseStatus.PENDING,
                )
            )
            inserted += 1
        elif existing.row_hash != row_hash:
            existing.raw_values = row.values
            existing.row_hash = row_hash
            existing.parser_strategy = spec.parser_strategy
            existing.parse_status = RawParseStatus.PENDING
            updated += 1
        else:
            unchanged += 1
    session.flush()
    return StageResult(inserted=inserted, updated=updated, unchanged=unchanged)


def stage_sheet(session: Session, workbook_path: str, sheet_name: str) -> StageReport:
    """End-to-end staging of one sheet: resolve org + source document, read the
    sheet verbatim, and upsert its rows. Commit/rollback is the caller's to own.
    """
    spec = resolve_spec(sheet_name)
    org_id = resolve_org_id(session)
    document, created = get_or_create_source_document(session, org_id, workbook_path)
    result = stage_rows(session, document, spec, read_sheet_rows(workbook_path, spec))
    return StageReport(
        source_document=document, source_created=created, spec=spec, result=result
    )
