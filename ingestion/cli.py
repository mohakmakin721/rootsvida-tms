"""Ingestion command-line interface.

Milestone 1 wires the command surface referenced by the Makefile
(`make ingest`, `make reingest`, `make dq`) so the contract is stable. The
subcommands are declared but NOT YET IMPLEMENTED — they exit with a clear,
labelled message rather than pretending to do work (see project rule §44).
Implementation lands in Milestone 5 (framework) and Milestone 6 (Rajasthan).
"""

from __future__ import annotations

import argparse
import sys

_NOT_IMPLEMENTED = 2


def _stub(command: str, milestone: str) -> int:
    print(
        f"[NOT IMPLEMENTED] `{command}` is scaffolded but lands in {milestone}.\n"
        "Milestone 1 only establishes the command surface and repo. No ingestion "
        "runs yet — this is intentional, not a failure.",
        file=sys.stderr,
    )
    return _NOT_IMPLEMENTED


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ingestion.cli", description="RootsVida ingestion")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", help="Ingest a single source sheet")
    p_ingest.add_argument("--sheet", required=True, help="Sheet name, e.g. Rajasthan")

    sub.add_parser("reingest", help="Rebuild all staging + candidates from source")
    sub.add_parser("report", help="Print the data-quality report for the last run")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "ingest":
        return _stub(f"ingest --sheet {args.sheet}", "Milestone 6")
    if args.command == "reingest":
        return _stub("reingest", "Milestone 11")
    if args.command == "report":
        return _stub("report", "Milestone 7")
    return _NOT_IMPLEMENTED


if __name__ == "__main__":
    raise SystemExit(main())
