"""Ingestion command-line interface.

`stage` is live as of Milestone 5: it reads one source sheet and upserts its rows
verbatim into `raw_import_rows` (no canonical writes, no LLM). The remaining
subcommands are still scaffolds that exit with a labelled message rather than
pretending to do work (project rule §44):

  - `ingest`   — staging + normalisation into canonical + review queue (M6)
  - `reingest` — rebuild all staging + candidates from source (M11)
  - `report`   — data-quality report for the last run (M7)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_NOT_IMPLEMENTED = 2
_ERROR = 1
_OK = 0


def _stub(command: str, milestone: str) -> int:
    print(
        f"[NOT IMPLEMENTED] `{command}` is scaffolded but lands in {milestone}.",
        file=sys.stderr,
    )
    return _NOT_IMPLEMENTED


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ingestion.cli", description="RootsVida ingestion")
    sub = parser.add_subparsers(dest="command", required=True)

    p_stage = sub.add_parser("stage", help="Stage one source sheet into raw_import_rows")
    p_stage.add_argument("--sheet", required=True, help="Sheet name, e.g. Rajasthan")
    p_stage.add_argument("--file", help="Workbook path (overrides the registry default)")

    p_ingest = sub.add_parser("ingest", help="Ingest a single source sheet (M6)")
    p_ingest.add_argument("--sheet", required=True, help="Sheet name, e.g. Rajasthan")

    sub.add_parser("reingest", help="Rebuild all staging + candidates from source (M11)")
    sub.add_parser("report", help="Print the data-quality report for the last run (M7)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "stage":
        return _run_stage(args.sheet, args.file)
    if args.command == "ingest":
        return _stub(f"ingest --sheet {args.sheet}", "Milestone 6")
    if args.command == "reingest":
        return _stub("reingest", "Milestone 11")
    if args.command == "report":
        return _stub("report", "Milestone 7")
    return _NOT_IMPLEMENTED


if __name__ == "__main__":
    raise SystemExit(main())
