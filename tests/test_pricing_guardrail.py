"""Phase 2 M8 — the minimum-margin guardrail."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pricing.engine import MarginBelowFloor, price
from pricing.model import (
    MarginOverride,
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


def _input(markup_rate: str = "0.25", floor: Decimal | None = None, gst: str = "0") -> PricingInput:
    """One pax, base cost 100, so margin is exactly controllable."""
    return PricingInput(
        segments=(Segment("s", "One", Occupancy.SINGLE, 1, "m"),),
        stays=(Stay("d1", "Hotel", 1, {Occupancy.SINGLE: 100}, frozenset({"s"})),),
        components=(),
        markup_rules={"m": MarkupRule("m", MarkupBasis.MARKUP_ON_COST, Decimal(markup_rate))},
        tax_rule=TaxRule(Decimal(gst), TaxTreatment.CGST_SGST),
        rounding=RoundingPolicy.NEAREST_1,
        margin_floor=floor,
    )


def test_true_margin_is_on_ex_tax_revenue() -> None:
    # base 100, +25% -> revenue_ex_tax 125; margin = 25/125 = 0.20 exactly.
    quote = price(_input(markup_rate="0.25", gst="0.05"))
    assert quote.revenue_ex_tax == Decimal("125.00")
    assert quote.margin_pct == Decimal("0.2000")


def test_no_floor_never_blocks() -> None:
    assert price(_input(floor=None)).margin_pct == Decimal("0.2000")


def test_margin_above_floor_passes() -> None:
    quote = price(_input(markup_rate="0.25", floor=Decimal("0.15")))  # 0.20 > 0.15
    assert quote.margin_pct == Decimal("0.2000")


def test_margin_below_floor_blocks_issuance() -> None:
    with pytest.raises(MarginBelowFloor) as exc:
        price(_input(markup_rate="0.25", floor=Decimal("0.30")))  # 0.20 < 0.30
    assert exc.value.margin_pct == Decimal("0.2000")
    assert exc.value.floor == Decimal("0.30")


def test_override_permits_issuance_and_is_recorded() -> None:
    override = MarginOverride(reason="strategic account, approved by owner", approved_by="owner")
    quote = price(_input(markup_rate="0.25", floor=Decimal("0.30")), margin_override=override)
    assert quote.margin_override is override


def test_override_requires_a_reason() -> None:
    with pytest.raises(ValueError):
        MarginOverride(reason="   ")


def test_jaipur_blended_margin_is_about_12_5_percent() -> None:
    from tests.test_golden_jaipur import jaipur_input

    quote = price(jaipur_input())
    assert Decimal("0.12") < quote.margin_pct < Decimal("0.13")  # not the naive 13%+
