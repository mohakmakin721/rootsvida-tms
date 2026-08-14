"""Project-code sequencing — pure serial logic (RV/<calendar-year>/<0001..>)."""

from __future__ import annotations

from app.api.v1.projects import next_project_code_for


def test_first_code_of_the_year() -> None:
    assert next_project_code_for([], 2026) == "RV/2026/0001"


def test_continues_past_highest_serial() -> None:
    codes = ["RV/2026/0001", "RV/2026/0003", "RV/2026/0002"]
    assert next_project_code_for(codes, 2026) == "RV/2026/0004"


def test_ignores_other_years_and_legacy_codes() -> None:
    codes = ["RV/2025/0009", "TP-JP-01", "RV/2026/0001", "RV/2026-27/0007"]
    assert next_project_code_for(codes, 2026) == "RV/2026/0002"


def test_pads_to_four_digits() -> None:
    assert next_project_code_for(["RV/2026/0042"], 2026) == "RV/2026/0043"
    assert next_project_code_for(["RV/2026/9999"], 2026) == "RV/2026/10000"
