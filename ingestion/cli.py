"""Ingestion command-line interface.

All subcommands are live as of Milestone 11:
  - `stage`    (M5) upsert a sheet's rows verbatim into `raw_import_rows`
  - `ingest`   (M6) stage + normalise a sheet into canonical `suppliers`
  - `dedup`    (M10) queue duplicate suppliers as merge candidates
  - `reingest` (M11) rebuild the whole pipeline from source, idempotently
  - `report`   (M7) print the org's data-quality summary
No LLM runs in Phase 1 (D-0007).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ERROR = 1
_OK = 0


def _resolve_workbook(sheet: str, file: str | None) -> Path | None:
    """Locate the workbook for `sheet`: an explicit `--file`, else the registry's
    workbook under SOURCE_DATA_DIR. Returns None if neither resolves."""
    from app.config import get_settings

    from ingestion.mappings import resolve_spec

    if file is not None:
        return Path(file)
    spec = resolve_spec(sheet)
    if spec.workbook is not None:
        return Path(get_settings().source_data_dir) / spec.workbook
    return None


def _run_stage(sheet: str, file: str | None) -> int:
    from app.db import get_engine
    from sqlalchemy.orm import Session

    from ingestion.staging import stage_sheet

    path = _resolve_workbook(sheet, file)
    if path is None:
        print(
            f"[error] sheet {sheet!r} is not in the registry; pass --file <workbook.xlsx>",
            file=sys.stderr,
        )
        return _ERROR
    if not path.exists():
        print(f"[error] workbook not found: {path}", file=sys.stderr)
        return _ERROR

    with Session(get_engine(), expire_on_commit=False) as session:
        try:
            report = stage_sheet(session, str(path), sheet)
            session.commit()
        except Exception:
            session.rollback()
            raise

    r = report.result
    doc = report.source_document
    source_state = "created" if report.source_created else "reused"
    print(
        f"staged {sheet!r} from {path.name} "
        f"[{report.spec.parser_strategy.value}] "
        f"(source {source_state} {doc.id})\n"
        f"  inserted={r.inserted} updated={r.updated} "
        f"unchanged={r.unchanged} total={r.total}"
    )
    return _OK


def _run_ingest(sheet: str, file: str | None) -> int:
    """End-to-end: stage the sheet, then normalise it into canonical suppliers."""
    from app.db import get_engine
    from sqlalchemy.orm import Session

    from ingestion.migrate import migrate_sheet
    from ingestion.staging import stage_sheet

    path = _resolve_workbook(sheet, file)
    if path is None:
        print(
            f"[error] sheet {sheet!r} is not in the registry; pass --file <workbook.xlsx>",
            file=sys.stderr,
        )
        return _ERROR
    if not path.exists():
        print(f"[error] workbook not found: {path}", file=sys.stderr)
        return _ERROR

    with Session(get_engine(), expire_on_commit=False) as session:
        try:
            staged = stage_sheet(session, str(path), sheet)
            migrated = migrate_sheet(session, staged.source_document, sheet)
            session.commit()
        except KeyError as exc:
            session.rollback()
            print(f"[error] {exc}", file=sys.stderr)
            return _ERROR
        except Exception:
            session.rollback()
            raise

    s, m = staged.result, migrated
    print(
        f"ingested {sheet!r} from {path.name} "
        f"(source {'created' if staged.source_created else 'reused'} "
        f"{staged.source_document.id})\n"
        f"  staged:    inserted={s.inserted} updated={s.updated} unchanged={s.unchanged}\n"
        f"  canonical: created={m.created} updated={m.updated} "
        f"partial={m.partial} needs_review={m.needs_review} (of {m.total})"
    )
    return _OK


def _run_dedup(threshold: float) -> int:
    """Detect duplicate suppliers and enqueue them as merge candidates."""
    from app.db import get_engine
    from sqlalchemy.orm import Session

    from ingestion.dedup import enqueue_merge_candidates
    from ingestion.source import resolve_org_id

    with Session(get_engine()) as session:
        try:
            org_id = resolve_org_id(session)
        except LookupError as exc:
            print(f"[error] {exc}", file=sys.stderr)
            return _ERROR
        n = enqueue_merge_candidates(session, org_id, threshold)
        session.commit()
    print(f"dedup: enqueued {n} new merge candidate(s) at threshold {threshold}")
    return _OK


def _run_reingest() -> int:
    """Rebuild the whole pipeline from source in one idempotent transaction."""
    from app.db import get_engine
    from sqlalchemy.orm import Session

    from ingestion.reingest import reingest_all, render_reingest

    with Session(get_engine()) as session:
        try:
            report = reingest_all(session)
            session.commit()
        except LookupError as exc:
            session.rollback()
            print(f"[error] {exc}", file=sys.stderr)
            return _ERROR
        except Exception:
            session.rollback()
            raise
    print(render_reingest(report))
    return _OK


def _run_report() -> int:
    """Print the data-quality report for the current org (read-only)."""
    from app.db import get_engine
    from sqlalchemy.orm import Session

    from ingestion.quality import build_report, render_report
    from ingestion.source import resolve_org_id

    with Session(get_engine()) as session:
        try:
            org_id = resolve_org_id(session)
        except LookupError as exc:
            print(f"[error] {exc}", file=sys.stderr)
            return _ERROR
        report = build_report(session, org_id)
    print(render_report(report))
    return _OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ingestion.cli", description="RootsVida ingestion")
    sub = parser.add_subparsers(dest="command", required=True)

    p_stage = sub.add_parser("stage", help="Stage one source sheet into raw_import_rows")
    p_stage.add_argument("--sheet", required=True, help="Sheet name, e.g. Rajasthan")
    p_stage.add_argument("--file", help="Workbook path (overrides the registry default)")

    p_ingest = sub.add_parser("ingest", help="Stage + normalise a sheet into canonical")
    p_ingest.add_argument("--sheet", required=True, help="Sheet name, e.g. Rajasthan")
    p_ingest.add_argument("--file", help="Workbook path (overrides the registry default)")

    p_dedup = sub.add_parser("dedup", help="Queue duplicate suppliers as merge candidates")
    p_dedup.add_argument("--threshold", type=float, default=0.84,
                         help="Name-similarity threshold 0..1 (default 0.84)")

    sub.add_parser("reingest", help="Rebuild all staging + candidates from source")
    sub.add_parser("report", help="Print the data-quality report for the current org")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "stage":
        return _run_stage(args.sheet, args.file)
    if args.command == "ingest":
        return _run_ingest(args.sheet, args.file)
    if args.command == "dedup":
        return _run_dedup(args.threshold)
    if args.command == "reingest":
        return _run_reingest()
    if args.command == "report":
        return _run_report()
    return _ERROR  # unreachable: subparsers are required


if __name__ == "__main__":
    raise SystemExit(main())
