"""Rate freshness — a pure, deterministic classifier (Phase 3 M6).

Turns a rate's validity window into a green/amber/red badge so the supplier & rate
browser can show, at a glance, whether a supplier has usable current rates. Pure
(no I/O) so it is trivially testable and reused by the API's supplier rollup.

Bands (relative to a reference `today`):
  * FRESH   (green)  — currently valid with comfortable runway (> `EXPIRING_DAYS`).
  * EXPIRING (amber) — valid today but lapses within `EXPIRING_DAYS`, or not yet in
                       effect (future-dated) — either way it needs a human's eye.
  * EXPIRED  (red)   — the window has already closed (`today` past `valid_to`).

A supplier with no rates rolls up to NONE (grey) — honest for prospects that carry
no priced rates yet (D-0009).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta
from enum import StrEnum

# A rate lapsing within this many days is "expiring" — flag it before it bites a quote.
EXPIRING_DAYS = 30


class Freshness(StrEnum):
    FRESH = "fresh"
    EXPIRING = "expiring"
    EXPIRED = "expired"
    NONE = "none"  # supplier-level only: no rates at all


def classify(valid_from: date, valid_to: date, today: date) -> Freshness:
    """Classify one rate's validity window against `today`."""
    if today > valid_to:
        return Freshness.EXPIRED
    if valid_from > today or valid_to <= today + timedelta(days=EXPIRING_DAYS):
        return Freshness.EXPIRING
    return Freshness.FRESH


# Best-first: a supplier is as fresh as its healthiest rate.
_RANK = (Freshness.FRESH, Freshness.EXPIRING, Freshness.EXPIRED)


def rollup(freshnesses: Iterable[Freshness]) -> Freshness:
    """Roll individual rate freshnesses into one supplier-level badge.

    The best available rate wins — a supplier with any fresh rate reads green even
    if it also carries expired ones. No rates at all rolls up to NONE.
    """
    present = set(freshnesses)
    for band in _RANK:
        if band in present:
            return band
    return Freshness.NONE
