"""Migration 0022 — pure category-normalization rules (no DB)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_MIG = (
    Path(__file__).resolve().parents[1]
    / "db" / "migrations" / "versions" / "0022_normalize_stay_categories.py"
)
_spec = importlib.util.spec_from_file_location("mig0022", _MIG)
assert _spec and _spec.loader
mig = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mig)


def test_property_type_wins() -> None:
    assert mig._canonical("Luxury", "Homestay") == "Homestays"
    assert mig._canonical("Budget", "Hostel") == "Hostels"


def test_budget_mid_lux_to_stars() -> None:
    assert mig._canonical("Budget", None) == "2 Star"
    assert mig._canonical("Budget to Mid range", None) == "2 Star"
    assert mig._canonical("Bud - lux", None) == "3 Star"
    assert mig._canonical("Mid", None) == "3 Star"
    assert mig._canonical("Mid Range", None) == "3 Star"
    assert mig._canonical("Mid-Lux", None) == "4 Star"
    assert mig._canonical("Lux", None) == "5 Star"
    assert mig._canonical("Luxury", None) == "5 Star"
    assert mig._canonical("Super Lux", None) == "7 Star"
    assert mig._canonical("Super Luxury", None) == "7 Star"


def test_case_and_spacing_insensitive() -> None:
    # The messy real-world variants from the browser dropdown all normalize.
    assert mig._canonical("MId range", None) == "3 Star"
    assert mig._canonical("mid - lux", None) == "4 Star"
    assert mig._canonical("  SUPER   LUX ", None) == "7 Star"


def test_unrecognized_left_untouched() -> None:
    assert mig._canonical("Boutique", None) is None
    assert mig._canonical(None, None) is None
    assert mig._canonical("", "") is None
