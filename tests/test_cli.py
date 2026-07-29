"""Milestone 12 — coverage for the ingestion CLI command surface.

Parsing only (no DB), so these run everywhere and guard the contract the
Makefile targets depend on.
"""

from __future__ import annotations

import pytest

from ingestion.cli import build_parser


def test_parser_accepts_every_subcommand() -> None:
    p = build_parser()
    assert p.parse_args(["stage", "--sheet", "Rajasthan"]).command == "stage"
    assert p.parse_args(["ingest", "--sheet", "Rajasthan"]).command == "ingest"
    assert p.parse_args(["dedup"]).command == "dedup"
    assert p.parse_args(["reingest"]).command == "reingest"
    assert p.parse_args(["report"]).command == "report"


def test_dedup_threshold_defaults_and_overrides() -> None:
    p = build_parser()
    assert p.parse_args(["dedup"]).threshold == 0.84
    assert p.parse_args(["dedup", "--threshold", "0.9"]).threshold == 0.9


def test_stage_supports_file_override() -> None:
    ns = build_parser().parse_args(["stage", "--sheet", "X", "--file", "wb.xlsx"])
    assert ns.sheet == "X"
    assert ns.file == "wb.xlsx"


def test_a_subcommand_is_required() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_stage_requires_sheet() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["stage"])
