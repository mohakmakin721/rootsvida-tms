"""Phase 5 (5a-M4) — the pure candidate-scoring heuristic. No DB required."""

from __future__ import annotations

from app.planning import Priority
from app.services.planning import score_supplier


def test_luxury_scores_high_comfort() -> None:
    s = score_supplier("stay", "Luxury", "Palace", [], [])
    assert s[Priority.COMFORT] >= 85


def test_budget_scores_low_comfort() -> None:
    s = score_supplier("stay", "Budget", None, [], [])
    assert s[Priority.COMFORT] <= 45


def test_homestay_scores_high_authenticity() -> None:
    s = score_supplier("stay", "Mid range", "Homestay", [], [])
    assert s[Priority.AUTHENTICITY] >= 85


def test_theme_hit_raises_experience_match() -> None:
    hit = score_supplier("activity", "", "yoga retreat", ["yoga"], ["Yoga"])
    miss = score_supplier("activity", "", "generic hall", [], ["Yoga"])
    assert hit[Priority.EXPERIENCE_MATCH] > miss[Priority.EXPERIENCE_MATCH]


def test_no_themes_is_neutralish_experience() -> None:
    s = score_supplier("stay", "", None, [], [])
    assert 40 <= s[Priority.EXPERIENCE_MATCH] <= 60
