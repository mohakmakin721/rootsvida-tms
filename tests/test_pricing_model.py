"""Phase 2 M2 — pricing domain model (pure, no DB)."""

from __future__ import annotations

from decimal import Decimal

import pytest
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


def _seg(seg_id: str = "fs", markup: str = "m") -> Segment:
    return Segment(seg_id, "Foreign Single", Occupancy.SINGLE, 1, markup)


def _markups() -> dict[str, MarkupRule]:
    return {"m": MarkupRule("m", MarkupBasis.MARKUP_ON_COST, Decimal("0.15"))}


def _tax() -> TaxRule:
    return TaxRule(Decimal("0.05"), TaxTreatment.CGST_SGST, hsn="998555")


def test_occupancy_divisor() -> None:
    assert Occupancy.SINGLE.divisor == Decimal(1)
    assert Occupancy.DOUBLE.divisor == Decimal(2)
    assert Occupancy.TRIPLE.divisor == Decimal(3)


def test_markup_on_cost() -> None:
    rule = MarkupRule("m", MarkupBasis.MARKUP_ON_COST, Decimal("0.15"))
    assert rule.apply(Decimal(100)) == Decimal("115.00")


def test_margin_on_sell_is_different_money() -> None:
    rule = MarkupRule("m", MarkupBasis.MARGIN_ON_SELL, Decimal("0.15"))
    # 100 / 0.85 = 117.647... — the "15%" that really yields a 15% margin.
    assert rule.apply(Decimal(100)) == Decimal(100) / Decimal("0.85")
    assert rule.apply(Decimal(100)) != Decimal(115)


def test_margin_on_sell_rejects_rate_ge_1() -> None:
    with pytest.raises(ValueError):
        MarkupRule("m", MarkupBasis.MARGIN_ON_SELL, Decimal(1))


def test_segment_requires_positive_pax() -> None:
    with pytest.raises(ValueError):
        Segment("s", "x", Occupancy.DOUBLE, 0, "m")


def test_money_fields_reject_float() -> None:
    with pytest.raises(TypeError):
        Component("c", "x", ComponentKind.SHARED, 41000.0, frozenset({"fs"}))
    with pytest.raises(TypeError):
        Stay("d1", "x", 1, {Occupancy.SINGLE: 7300.0}, frozenset({"fs"}))


def test_money_fields_are_coerced_to_decimal() -> None:
    c = Component("c", "x", ComponentKind.SHARED, 41000, frozenset({"fs"}))
    assert c.amount == Decimal(41000) and isinstance(c.amount, Decimal)
    stay = Stay("d1", "x", 1, {Occupancy.SINGLE: 7300}, frozenset({"fs"}))
    assert stay.room_rate[Occupancy.SINGLE] == Decimal(7300)


def test_stay_and_component_validation() -> None:
    with pytest.raises(ValueError):
        Stay("d1", "x", 0, {Occupancy.SINGLE: 100}, frozenset({"fs"}))
    with pytest.raises(ValueError):
        Stay("d1", "x", 1, {}, frozenset({"fs"}))
    with pytest.raises(ValueError):
        Component("c", "x", ComponentKind.SHARED, -1, frozenset({"fs"}))
    with pytest.raises(ValueError):
        Component("c", "x", ComponentKind.SHARED, 10, frozenset())


def test_fx_rate_must_be_positive() -> None:
    with pytest.raises(ValueError):
        FxRate("USD", Decimal(0))
    assert FxRate("USD", 95).inr_per_unit == Decimal(95)


def test_pricing_input_validates_references() -> None:
    # unknown markup rule
    with pytest.raises(ValueError):
        PricingInput(
            segments=(_seg(markup="ghost"),),
            stays=(),
            components=(),
            markup_rules=_markups(),
            tax_rule=_tax(),
            rounding=RoundingPolicy.NEAREST_1,
        )
    # duplicate segment ids
    with pytest.raises(ValueError):
        PricingInput(
            segments=(_seg("dup"), _seg("dup")),
            stays=(),
            components=(),
            markup_rules=_markups(),
            tax_rule=_tax(),
            rounding=RoundingPolicy.NEAREST_1,
        )


def test_pricing_input_accepts_a_valid_shape() -> None:
    inp = PricingInput(
        segments=(_seg(),),
        stays=(Stay("d1", "Jaipur", 1, {Occupancy.SINGLE: 7300}, frozenset({"fs"})),),
        components=(Component("t", "Transport", ComponentKind.SHARED, 41000, frozenset({"fs"})),),
        markup_rules=_markups(),
        tax_rule=_tax(),
        rounding=RoundingPolicy.NEAREST_1,
        fx=FxRate("USD", 95),
    )
    assert inp.segments[0].markup_rule_id in inp.markup_rules
