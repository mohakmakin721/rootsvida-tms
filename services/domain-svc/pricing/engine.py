"""The cost pass — accommodation + shared + direct, per segment (Part 2 §5).

Reproduces the source workbook's cost logic, generalised:

    accommodation(s) = Σ over stays where s is present:
                         room_rate[occupancy(s)] × nights ÷ occupancy_divisor(s)
    shared(s)        = Σ over SHARED components applying to s:
                         amount ÷ Σ pax in the component's bucket
    direct(s)        = Σ over DIRECT components applying to s: amount   (already per-pax)
    base_cost(s)     = accommodation + shared + direct

Everything here stays **exact** — no rounding. Rounding is the sell pass's job
(M4), once, at the policy boundary. Each contribution is recorded as a `TraceRef`
so every number can explain itself.
"""

from __future__ import annotations

from dataclasses import dataclass

from pricing.model import (
    ComponentKind,
    Id,
    PricingInput,
    Segment,
    TraceRef,
)
from pricing.money import Money, money


@dataclass(frozen=True)
class SegmentCost:
    """The exact, pre-markup cost of one pax in a segment, with its audit trail."""

    accommodation: Money
    shared: Money
    direct: Money
    trace: tuple[TraceRef, ...]

    @property
    def base_cost(self) -> Money:
        return self.accommodation + self.shared + self.direct


def _bucket_pax(seg_by_id: dict[Id, Segment], applies_to: frozenset[Id]) -> Money:
    """Total headcount of the segments a component is shared across."""
    return money(sum(seg_by_id[sid].pax for sid in applies_to))


def _accommodation(inp: PricingInput, seg: Segment) -> tuple[Money, list[TraceRef]]:
    total = money(0)
    trace: list[TraceRef] = []
    for stay in inp.stays:
        if seg.id not in stay.present_segment_ids:
            continue
        rate = stay.room_rate.get(seg.occupancy)
        if rate is None:
            raise ValueError(
                f"stay {stay.id!r} has no {seg.occupancy.name} rate for segment {seg.id!r}"
            )
        per_pax = rate * money(stay.nights) / seg.occupancy.divisor
        total += per_pax
        trace.append(TraceRef("accommodation", stay.label, per_pax))
    return total, trace


def _shared_and_direct(
    inp: PricingInput, seg: Segment, seg_by_id: dict[Id, Segment]
) -> tuple[Money, Money, list[TraceRef]]:
    shared = money(0)
    direct = money(0)
    trace: list[TraceRef] = []
    for comp in inp.components:
        if seg.id not in comp.applies_to:
            continue
        if comp.kind is ComponentKind.SHARED:
            per_pax = comp.amount / _bucket_pax(seg_by_id, comp.applies_to)
            shared += per_pax
            trace.append(TraceRef("shared", comp.label, per_pax))
        else:  # DIRECT — amount is already per-pax
            direct += comp.amount
            trace.append(TraceRef("direct", comp.label, comp.amount))
    return shared, direct, trace


def compute_segment_cost(
    inp: PricingInput, seg: Segment, seg_by_id: dict[Id, Segment]
) -> SegmentCost:
    accommodation, accom_trace = _accommodation(inp, seg)
    shared, direct, cost_trace = _shared_and_direct(inp, seg, seg_by_id)
    return SegmentCost(
        accommodation=accommodation,
        shared=shared,
        direct=direct,
        trace=tuple(accom_trace + cost_trace),
    )


def compute_costs(inp: PricingInput) -> dict[Id, SegmentCost]:
    """Exact per-segment base cost for every segment in the input."""
    seg_by_id = {s.id: s for s in inp.segments}
    return {s.id: compute_segment_cost(inp, s, seg_by_id) for s in inp.segments}
