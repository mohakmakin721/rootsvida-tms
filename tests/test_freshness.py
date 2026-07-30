"""Unit tests for the pure rate-freshness classifier (Phase 3 M6)."""

from __future__ import annotations

from datetime import date, timedelta

from app.services.freshness import EXPIRING_DAYS, Freshness, classify, rollup

TODAY = date(2026, 7, 30)


def test_currently_valid_with_runway_is_fresh() -> None:
    assert classify(date(2026, 1, 1), date(2026, 12, 31), TODAY) is Freshness.FRESH


def test_expired_window_is_expired() -> None:
    assert classify(date(2025, 1, 1), date(2025, 12, 31), TODAY) is Freshness.EXPIRED


def test_lapses_within_window_is_expiring() -> None:
    soon = TODAY + timedelta(days=EXPIRING_DAYS - 1)
    assert classify(date(2026, 1, 1), soon, TODAY) is Freshness.EXPIRING


def test_boundary_exactly_at_window_edge_is_expiring() -> None:
    edge = TODAY + timedelta(days=EXPIRING_DAYS)
    assert classify(date(2026, 1, 1), edge, TODAY) is Freshness.EXPIRING
    # One day past the window is comfortably fresh.
    assert classify(date(2026, 1, 1), edge + timedelta(days=1), TODAY) is Freshness.FRESH


def test_valid_to_today_is_expiring_not_expired() -> None:
    assert classify(date(2026, 1, 1), TODAY, TODAY) is Freshness.EXPIRING


def test_future_dated_rate_is_expiring() -> None:
    """Not yet in effect — flagged so a human confirms before it is quoted."""
    assert classify(TODAY + timedelta(days=10), date(2027, 12, 31), TODAY) is Freshness.EXPIRING


def test_rollup_prefers_best_band() -> None:
    assert rollup([Freshness.EXPIRED, Freshness.FRESH, Freshness.EXPIRING]) is Freshness.FRESH
    assert rollup([Freshness.EXPIRED, Freshness.EXPIRING]) is Freshness.EXPIRING
    assert rollup([Freshness.EXPIRED]) is Freshness.EXPIRED


def test_rollup_empty_is_none() -> None:
    assert rollup([]) is Freshness.NONE
