"""One-command rebuild of the whole pipeline from source (Milestone 11).

Plan Phase-1 exit criterion: "a repeatable `make reingest` that rebuilds from
source with zero manual steps." Because every step is idempotent — staging
upserts on (source, sheet, row), migration upserts via
`raw_import_rows.normalized_supplier_id`, and both candidate producers key on a
`dedupe_key` — running this repeatedly converges to the same state with no
duplicates. It re-derives (upserts), it does not drop-and-recreate.

For each sheet that has both a registry entry (with a workbook) and a normaliser,
it stages then migrates; afterwards it refreshes the merge and needs-review
candidates. The whole run is one transaction (the CLI commits once), so a rebuild
is all-or-nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings
from app.services.review import enqueue_needs_review
from sqlalchemy.orm import Session

from ingestion.dedup import enqueue_merge_candidates
from ingestion.mappings import resolve_spec
from ingestion.migrate import MigrateResult, migrate_sheet
from ingestion.normalize import NORMALIZERS
from ingestion.source import resolve_org_id
from ingestion.staging import StageResult, stage_sheet


@dataclass(frozen=True)
class SheetOutcome:
    sheet: str
    ok: bool
    workbook: str | None = None
    staged: StageResult | None = None
    migrated: MigrateResult | None = None
    error: str | None = None


@dataclass(frozen=True)
class ReingestReport:
    sheets: list[SheetOutcome]
    merge_candidates: int
    needs_review: int

    @property
    def ok_sheets(self) -> int:
        return sum(1 for s in self.sheets if s.ok)


def _ingestable_sheets() -> list[str]:
    """Sheets that can be rebuilt end to end: they have a normaliser and a
    registry entry that names a workbook."""
    out = []
    for sheet in sorted(NORMALIZERS):
        if resolve_spec(sheet).workbook is not None:
            out.append(sheet)
    return out


def reingest_all(session: Session) -> ReingestReport:
    """Stage + migrate every ingestable sheet, then refresh review candidates.

    The whole pipeline operates under the single configured org (Phase 1 is
    single-tenant): `stage_sheet` resolves it, and the candidate producers use the
    same one — so every step stays consistent."""
    settings = get_settings()
    outcomes: list[SheetOutcome] = []
    for sheet in _ingestable_sheets():
        spec = resolve_spec(sheet)
        assert spec.workbook is not None  # guaranteed by _ingestable_sheets
        path = Path(settings.source_data_dir) / spec.workbook
        if not path.exists():
            outcomes.append(
                SheetOutcome(sheet, False, spec.workbook, error=f"file not found: {path}")
            )
            continue
        staged = stage_sheet(session, str(path), sheet)
        migrated = migrate_sheet(session, staged.source_document, sheet)
        outcomes.append(
            SheetOutcome(sheet, True, spec.workbook, staged.result, migrated)
        )

    org_id = resolve_org_id(session)
    merge_candidates = enqueue_merge_candidates(session, org_id)
    needs_review = enqueue_needs_review(session, org_id)
    return ReingestReport(outcomes, merge_candidates, needs_review)


def render_reingest(report: ReingestReport) -> str:
    """Format the reingest outcome as plain ASCII text for the CLI."""
    lines = ["Reingest summary", ""]
    for o in report.sheets:
        if o.ok and o.staged and o.migrated:
            s, m = o.staged, o.migrated
            lines.append(
                f"  {o.sheet}: staged +{s.inserted}/~{s.updated}/={s.unchanged}"
                f"  ->  canonical +{m.created}/~{m.updated}"
                f" (partial {m.partial}, needs_review {m.needs_review})"
            )
        else:
            lines.append(f"  {o.sheet}: SKIPPED - {o.error}")
    lines += [
        "",
        f"merge candidates enqueued: {report.merge_candidates}",
        f"needs-review enqueued:     {report.needs_review}",
        "",
        "Run `make dq` for the full data-quality report.",
    ]
    return "\n".join(lines)
