"""Phase 2 M9 — snapshot regression guard.

Pins the structured output of a representative quote (Part 2 §5). Any diff means
the engine's output changed — which must be a deliberate, reviewed edit to this
expected snapshot, not an accident.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pricing.engine import price
from pricing.model import PricedQuote

from tests.test_golden_jaipur import jaipur_input


def _snapshot(quote: PricedQuote) -> dict[str, Any]:
    """A stable, JSON-ish view of the headline outputs (Decimals as strings)."""
    q2 = Decimal("0.01")
    return {
        "engine_version": quote.engine_version,
        "group_total": str(quote.group_total),
        "total_cost": str(quote.total_cost),
        "profit": str(quote.profit),
        "revenue_ex_tax": str(quote.revenue_ex_tax),
        "margin_pct": str(quote.margin_pct),
        "fx": {k: str(v) for k, v in (quote.fx or {}).items()},
        "segments": [
            {
                "id": s.segment_id,
                "base_cost": str(s.base_cost.quantize(q2)),
                "sell_per_pax": str(s.sell_per_pax),
                "group_total": str(s.group_total),
            }
            for s in quote.segments
        ],
    }


# Regenerate deliberately if the engine's output intentionally changes.
_JAIPUR_SNAPSHOT = {
    "engine_version": "pricing@0.1.0",
    "group_total": "403327",
    "total_cost": "336050.00",
    "profit": "67277.00",
    "revenue_ex_tax": "384123.61",
    "margin_pct": "0.1252",
    "fx": {"USD": "4245.55"},
    "segments": [
        {"id": "fs", "base_cost": "54324.60", "sell_per_pax": "65597", "group_total": "65597"},
        {"id": "fd", "base_cost": "39174.60", "sell_per_pax": "47303", "group_total": "283818"},
        {"id": "id", "base_cost": "23338.89", "sell_per_pax": "26956", "group_total": "53912"},
    ],
}


def test_jaipur_quote_snapshot() -> None:
    assert _snapshot(price(jaipur_input())) == _JAIPUR_SNAPSHOT
