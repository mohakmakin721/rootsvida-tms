"""Phase 2 M5 — GOLDEN FIXTURE: the Jaipur / Golden Triangle costing workbook.

The non-negotiable acceptance test (plan Phase 2, Part 2 §5.test suite). The
engine must reproduce the workbook's numbers **to the rupee**:

    Foreign Single  65,597    Foreign Double  47,303    Indian Double  26,956
    Group total  4,03,327     Profit  67,277            USD @95  4,245.55

Encoded directly from `Jaipur_Dynamic_Costing_Workbook_Revised.xlsx`
(Inputs / Hotels_DB / Itinerary / Other_Costs / Summary). If this test ever goes
red, either the engine drifted or someone changed the fixture — both must be
deliberate. This runs in CI on every commit, forever.
"""

from __future__ import annotations

from decimal import Decimal

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

# Allocation buckets (Other_Costs "Allocation Basis").
_ALL = frozenset({"fs", "fd", "id"})  # 9 pax
_FOREIGN = frozenset({"fs", "fd"})  # 7 pax
_INDIAN = frozenset({"id"})  # 2 pax

_SHARED = ComponentKind.SHARED


def jaipur_input() -> PricingInput:
    """The workbook, as a PricingInput. 1 Foreign Single + 6 Foreign Double +
    2 Indian Double; foreign present all 6 nights, Indian only the first 4."""
    return PricingInput(
        segments=(
            Segment("fs", "Foreign Single", Occupancy.SINGLE, 1, "foreign"),
            Segment("fd", "Foreign Double", Occupancy.DOUBLE, 6, "foreign"),
            Segment("id", "Indian Double", Occupancy.DOUBLE, 2, "indian"),
        ),
        # Itinerary: (single_rate, double_rate) per night; Delhi (d5,d6) foreign-only.
        stays=(
            Stay("d1", "Jaipur — Shahpura House (MAP)", 1,
                 {Occupancy.SINGLE: 7300, Occupancy.DOUBLE: 7300}, _ALL),
            Stay("d2", "Jaipur — Shahpura House (CP)", 1,
                 {Occupancy.SINGLE: 5500, Occupancy.DOUBLE: 5500}, _ALL),
            Stay("d3", "Jaipur — Shahpura House (CP)", 1,
                 {Occupancy.SINGLE: 5500, Occupancy.DOUBLE: 5500}, _ALL),
            Stay("d4", "Agra — Grand Imperial (MAP)", 1,
                 {Occupancy.SINGLE: 5000, Occupancy.DOUBLE: 6000}, _ALL),
            Stay("d5", "Delhi — Orion Plaza / Grand Ffour (MAP)", 1,
                 {Occupancy.SINGLE: 5000, Occupancy.DOUBLE: 5500}, _FOREIGN),
            Stay("d6", "Delhi — Orion Plaza / Grand Ffour (CP)", 1,
                 {Occupancy.SINGLE: 4000, Occupancy.DOUBLE: 4500}, _FOREIGN),
        ),
        # Other_Costs — all shared by their allocation bucket.
        components=(
            Component("transport", "Transport Jaipur-Agra-Delhi", _SHARED, 41000, _ALL),
            Component("delhi_urbania", "Delhi Urbania + Airport", _SHARED, 8000, _FOREIGN),
            Component("jaipur_guide", "Jaipur Guide", _SHARED, 4000, _ALL),
            Component("agra_guide", "Agra Guide", _SHARED, 2500, _ALL),
            Component("rohan_tada", "Rohan TA/DA", _SHARED, 25000, _ALL),
            Component("rohan_fee", "Rohan Professional Fee", _SHARED, 21000, _ALL),
            Component("jaipur_mon_f", "Jaipur Monuments (Foreign)", _SHARED, 18900, _FOREIGN),
            Component("jaipur_mon_i", "Jaipur Monuments (Indian)", _SHARED, 1000, _INDIAN),
            Component("agra_mon_f", "Agra Monuments (Foreign)", _SHARED, 13650, _FOREIGN),
            Component("agra_mon_i", "Agra Monuments (Indian)", _SHARED, 600, _INDIAN),
            Component("delhi_mon_f", "Delhi Monuments (Foreign)", _SHARED, 10500, _FOREIGN),
            Component("delhi_mon_i", "Delhi Monuments (Indian)", _SHARED, 0, _INDIAN),
            Component("delhi_cycle", "Delhi by Cycle", _SHARED, 15400, _FOREIGN),
            Component("misc", "Miscellaneous", _SHARED, 15000, _FOREIGN),
        ),
        markup_rules={
            "foreign": MarkupRule("foreign", MarkupBasis.MARKUP_ON_COST, Decimal("0.15")),
            "indian": MarkupRule("indian", MarkupBasis.MARKUP_ON_COST, Decimal("0.10")),
        },
        tax_rule=TaxRule(Decimal("0.05"), TaxTreatment.CGST_SGST, hsn="998555"),
        rounding=RoundingPolicy.NEAREST_1,
        fx=FxRate("USD", 95),
    )


def test_golden_jaipur_to_the_rupee() -> None:
    quote = price(jaipur_input())
    sell = {s.segment_id: s.sell_per_pax for s in quote.segments}

    assert sell["fs"] == Decimal(65597)
    assert sell["fd"] == Decimal(47303)
    assert sell["id"] == Decimal(26956)
    assert quote.group_total == Decimal(403327)
    assert quote.total_cost == Decimal("336050.00")
    assert quote.profit == Decimal("67277.00")
    assert quote.fx is not None and quote.fx["USD"] == Decimal("4245.55")


def test_golden_jaipur_base_costs() -> None:
    # The exact per-pax base costs behind the sell prices (workbook Summary).
    base = {s.segment_id: s.base_cost for s in price(jaipur_input()).segments}
    q2 = Decimal("0.01")
    assert base["fs"].quantize(q2) == Decimal("54324.60")
    assert base["fd"].quantize(q2) == Decimal("39174.60")
    assert base["id"].quantize(q2) == Decimal("23338.89")


def test_golden_jaipur_group_total_equals_sum_of_segments() -> None:
    quote = price(jaipur_input())
    assert sum((s.group_total for s in quote.segments), Decimal(0)) == quote.group_total
