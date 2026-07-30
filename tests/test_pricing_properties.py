"""Phase 2 M9 — property-based tests (Hypothesis).

Throw thousands of random traveller mixes / itineraries at the engine and assert
the invariants that must hold for *every* input (Part 2 §5): the segment totals
reconcile to the group, margins never go negative under non-negative markups, and
pricing is deterministic and drift-free even over long itineraries.
"""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st
from pricing.engine import price
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

_OCCUPANCIES = [Occupancy.SINGLE, Occupancy.DOUBLE, Occupancy.TRIPLE]
_RATE = TaxRule(Decimal("0.05"), TaxTreatment.CGST_SGST)


@st.composite
def pricing_inputs(draw: st.DrawFn) -> PricingInput:
    seg_ids = [f"s{i}" for i in range(draw(st.integers(1, 3)))]
    segments = tuple(
        Segment(sid, sid, draw(st.sampled_from(_OCCUPANCIES)), draw(st.integers(1, 12)), "m")
        for sid in seg_ids
    )
    markup = draw(st.decimals(min_value=0, max_value=1, places=2, allow_nan=False,
                              allow_infinity=False))

    stays = []
    for j in range(draw(st.integers(1, 6))):
        present = draw(st.lists(st.sampled_from(seg_ids), min_size=1, unique=True))
        rate = draw(st.integers(500, 20000))
        stays.append(
            Stay(f"d{j}", f"d{j}", draw(st.integers(1, 3)),
                 {occ: rate for occ in _OCCUPANCIES}, frozenset(present))
        )

    components = []
    for k in range(draw(st.integers(0, 4))):
        applies = draw(st.lists(st.sampled_from(seg_ids), min_size=1, unique=True))
        components.append(
            Component(f"c{k}", f"c{k}", ComponentKind.SHARED,
                      draw(st.integers(0, 60000)), frozenset(applies))
        )

    return PricingInput(
        segments=segments,
        stays=tuple(stays),
        components=tuple(components),
        markup_rules={"m": MarkupRule("m", MarkupBasis.MARKUP_ON_COST, markup)},
        tax_rule=_RATE,
        rounding=RoundingPolicy.NEAREST_1,
    )


@settings(max_examples=100, deadline=None)
@given(pricing_inputs())
def test_segments_reconcile_to_group_total(inp: PricingInput) -> None:
    quote = price(inp)
    assert sum((s.group_total for s in quote.segments), Decimal(0)) == quote.group_total


@settings(max_examples=100, deadline=None)
@given(pricing_inputs())
def test_margin_never_negative_with_nonnegative_markup(inp: PricingInput) -> None:
    assert price(inp).margin_pct >= 0


@settings(max_examples=100, deadline=None)
@given(pricing_inputs())
def test_pricing_is_deterministic(inp: PricingInput) -> None:
    assert price(inp) == price(inp)


@settings(max_examples=100, deadline=None)
@given(pricing_inputs())
def test_profit_reconciles(inp: PricingInput) -> None:
    quote = price(inp)
    assert quote.profit == (quote.group_total - quote.total_cost).quantize(Decimal("0.01"))


def test_markup_on_cost_margin_is_closed_form() -> None:
    # margin_on_cost margin = m / (1+m), independent of cost magnitude.
    from pricing.money import money

    inp = PricingInput(
        segments=(Segment("s", "s", Occupancy.SINGLE, 3, "m"),),
        stays=(Stay("d", "d", 2, {Occupancy.SINGLE: 5000}, frozenset({"s"})),),
        components=(Component("c", "c", ComponentKind.SHARED, 9000, frozenset({"s"})),),
        markup_rules={"m": MarkupRule("m", MarkupBasis.MARKUP_ON_COST, Decimal("0.25"))},
        tax_rule=_RATE,
        rounding=RoundingPolicy.NEAREST_1,
    )
    # m/(1+m) = 0.25/1.25 = 0.20
    assert price(inp).margin_pct == money("0.2000")
