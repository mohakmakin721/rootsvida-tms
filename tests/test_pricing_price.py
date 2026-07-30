"""Phase 2 M4 — the sell pass (markup, tax, round once, roll up)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pricing import ENGINE_VERSION
from pricing.engine import price
from pricing.model import (
    Component,
    ComponentKind,
    FxRate,
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
            Stay("d1", "Jaipur", 1, {Occupancy.SINGLE: 7300, Occupancy.DOUBLE: 7300},
                 frozenset({"fs", "fd"})),
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
        "fx": FxRate("USD", 95),
    }
    base.update(over)
    return PricingInput(**base)  # type: ignore[arg-type]


def test_sell_applies_markup_then_gst_then_rounds() -> None:
    quote = price(_input())
    by_id = {s.segment_id: s for s in quote.segments}
    # fs base = 11300 + 1000 = 12300 -> round(12300 * 1.15 * 1.05) = round(14852.25) = 14852
    assert by_id["fs"].base_cost == Decimal(12300)
    assert by_id["fs"].sell_per_pax == Decimal(14852)
    # fd base = 3650 + 300 + 100 = 4050 -> round(4050 * 1.15 * 1.05) = round(4890.375) = 4890
    assert by_id["fd"].sell_per_pax == Decimal(4890)


def test_group_total_cost_and_profit() -> None:
    quote = price(_input())
    # group = 14852*1 + 4890*2 = 24632 ; cost = 12300*1 + 4050*2 = 20400
    assert quote.group_total == Decimal(24632)
    assert quote.total_cost == Decimal("20400.00")
    assert quote.profit == Decimal("4232.00")


def test_fx_equivalent_is_two_places() -> None:
    quote = price(_input())
    assert quote.fx is not None
    # 24632 / 95 = 259.284... -> quantised to paise -> 259.28
    assert quote.fx["USD"] == Decimal("259.28")
    assert quote.fx["USD"] == (Decimal(24632) / Decimal(95)).quantize(Decimal("0.01"))


def test_trace_amounts_sum_to_sell_per_pax() -> None:
    quote = price(_input())
    for seg in quote.segments:
        assert sum((t.amount for t in seg.trace), Decimal(0)) == seg.sell_per_pax


def test_quote_records_engine_version() -> None:
    assert price(_input()).engine_version == ENGINE_VERSION


def test_margin_on_sell_convention() -> None:
    markups = {"g": MarkupRule("g", MarkupBasis.MARGIN_ON_SELL, Decimal("0.15"))}
    seg = Segment("fs", "x", Occupancy.SINGLE, 1, "g")
    inp = _input(segments=(seg,), markup_rules=markups, components=(), fx=None,
                 stays=(Stay("d1", "x", 1, {Occupancy.SINGLE: 10000}, frozenset({"fs"})),))
    quote = price(inp)
    # base 10000 -> 10000/0.85 * 1.05 = 12352.94... -> round -> 12353
    assert quote.segments[0].sell_per_pax == Decimal(12353)


def test_gross_nearest_100_not_yet_implemented() -> None:
    with pytest.raises(NotImplementedError, match="Milestone 6"):
        price(_input(rounding=RoundingPolicy.GROSS_NEAREST_100))
