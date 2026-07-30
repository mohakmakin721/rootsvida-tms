"""Phase 2 M3 — the cost pass (accommodation + shared + direct)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pricing.engine import compute_costs
from pricing.model import (
    Component,
    ComponentKind,
    MarkupBasis,
    MarkupRule,
    Occupancy,
    PricingInput,
    RoundingPolicy,
    Segment,
    Stay,
    TaxRule,
    TaxTreatment,
)

_MARKUPS = {"m": MarkupRule("m", MarkupBasis.MARKUP_ON_COST, Decimal("0.15"))}
_TAX = TaxRule(Decimal("0.05"), TaxTreatment.CGST_SGST)


def _input(**over: object) -> PricingInput:
    base: dict[str, object] = {
        "segments": (
            Segment("fs", "Foreign Single", Occupancy.SINGLE, 1, "m"),
            Segment("fd", "Foreign Double", Occupancy.DOUBLE, 2, "m"),
        ),
        "stays": (
            # both present, day 1
            Stay("d1", "Jaipur", 1, {Occupancy.SINGLE: 7300, Occupancy.DOUBLE: 7300},
                 frozenset({"fs", "fd"})),
            # foreign single gets an extra night the double does not
            Stay("d2", "Delhi", 1, {Occupancy.SINGLE: 4000, Occupancy.DOUBLE: 4500},
                 frozenset({"fs"})),
        ),
        "components": (
            Component("t", "Transport", ComponentKind.SHARED, 900, frozenset({"fs", "fd"})),
            Component("fo", "Foreign only", ComponentKind.SHARED, 700, frozenset({"fs"})),
            Component("tk", "Ticket", ComponentKind.DIRECT, 100, frozenset({"fd"})),
        ),
        "markup_rules": _MARKUPS,
        "tax_rule": _TAX,
        "rounding": RoundingPolicy.NEAREST_1,
    }
    base.update(over)
    return PricingInput(**base)  # type: ignore[arg-type]


def test_accommodation_uses_occupancy_divisor_and_presence() -> None:
    costs = compute_costs(_input())
    # single: full single rate each night, present both nights
    assert costs["fs"].accommodation == Decimal(7300) + Decimal(4000)
    # double: double rate halved, present only the first night
    assert costs["fd"].accommodation == Decimal(7300) / Decimal(2)


def test_shared_allocation_divides_by_bucket_pax() -> None:
    costs = compute_costs(_input())
    # transport 900 over bucket {fs(1), fd(2)} = 3 pax -> 300 each
    # foreign-only 700 over bucket {fs(1)} = 1 pax -> 700 (fs only)
    assert costs["fs"].shared == Decimal(300) + Decimal(700)
    assert costs["fd"].shared == Decimal(300)


def test_direct_is_per_pax_and_scoped() -> None:
    costs = compute_costs(_input())
    assert costs["fd"].direct == Decimal(100)
    assert costs["fs"].direct == Decimal(0)


def test_base_cost_is_the_sum() -> None:
    costs = compute_costs(_input())
    fs = costs["fs"]
    assert fs.base_cost == fs.accommodation + fs.shared + fs.direct
    assert fs.base_cost == Decimal(11300) + Decimal(1000)
    assert costs["fd"].base_cost == Decimal(3650) + Decimal(300) + Decimal(100)


def test_trace_records_every_contribution() -> None:
    fs = compute_costs(_input())["fs"]
    kinds = [t.kind for t in fs.trace]
    assert kinds.count("accommodation") == 2  # two nights
    assert kinds.count("shared") == 2  # transport + foreign-only
    assert "direct" not in kinds


def test_missing_rate_for_present_occupancy_raises() -> None:
    # fd (double) present but the stay only quotes a single rate.
    bad = _input(
        stays=(Stay("d1", "x", 1, {Occupancy.SINGLE: 100}, frozenset({"fd"})),),
        components=(),
    )
    with pytest.raises(ValueError, match="no DOUBLE rate"):
        compute_costs(bad)
