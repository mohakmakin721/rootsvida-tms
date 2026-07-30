"""Pricing domain model — the typed inputs and outputs (Part 2 §5).

Frozen dataclasses in, a `PricedQuote` out. The engine (M3+) is a pure function
over these; this module only defines the shapes and the small, total helpers on
them (occupancy divisor, markup application). Money-typed fields are coerced
through `money()` on construction, so an inexact `float` can never enter a quote.

Design note vs Part 2 §5: rates arrive **already resolved** by date/season, so
each `Stay` carries its resolved per-occupancy room rate directly rather than an
external `rate_snapshot` id map — the resolution happens in the caller (Phase 3),
before a `PricingInput` exists.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, IntEnum

from pricing.money import Money, money

Id = str  # engine ids are opaque strings; the DB layer maps its UUIDs to these


class Occupancy(IntEnum):
    """Room occupancy. The value **is** the per-pax divisor (single→1, double→2)."""

    SINGLE = 1
    DOUBLE = 2
    TRIPLE = 3

    @property
    def divisor(self) -> Money:
        return money(self.value)


class ComponentKind(Enum):
    """How a non-accommodation cost is allocated to a pax."""

    SHARED = "shared"  # total cost split across the bucket: total ÷ Σ pax
    DIRECT = "direct"  # a per-pax cost applied to each pax in the bucket


class MarkupBasis(Enum):
    """The two markup conventions — never left ambiguous (Part 2 §5).

    `markup_on_cost` (× (1+m)) is what the source workbook uses; `margin_on_sell`
    (÷ (1−m)) is the true-margin convention. A 15% figure means different money
    under each, so the choice is explicit.
    """

    MARKUP_ON_COST = "markup_on_cost"
    MARGIN_ON_SELL = "margin_on_sell"


class TaxTreatment(Enum):
    """Place-of-supply outcome (resolved upstream; split happens at invoice time)."""

    CGST_SGST = "cgst_sgst"  # intra-state: 2.5% + 2.5%
    IGST = "igst"  # inter-state: single 5%
    EXPORT = "export"  # zero-rated export of service


class RoundingPolicy(Enum):
    """When and how the final rounding happens."""

    NEAREST_1 = "nearest_1"  # round each segment's sell to the rupee (workbook)
    GROSS_NEAREST_100 = "gross_nearest_100"  # price to a round gross (invoice, M6)


# --------------------------------------------------------------------------- #
# inputs
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Segment:
    """A traveller type: an occupancy, a headcount, and which markup applies."""

    id: Id
    label: str
    occupancy: Occupancy
    pax: int
    markup_rule_id: Id

    def __post_init__(self) -> None:
        if self.pax < 1:
            raise ValueError(f"segment {self.id!r}: pax must be >= 1, got {self.pax}")


@dataclass(frozen=True)
class Stay:
    """One accommodation line — a night (or block) with its resolved room rate.

    `room_rate` is the per-room contracted rate for each occupancy; the per-pax
    cost is `room_rate[occupancy] × nights ÷ occupancy.divisor`. `present_segment_ids`
    records who actually stays (foreign pax may have extra nights Indians do not).
    """

    id: Id
    label: str
    nights: int
    room_rate: Mapping[Occupancy, Money]
    present_segment_ids: frozenset[Id]

    def __post_init__(self) -> None:
        if self.nights < 1:
            raise ValueError(f"stay {self.id!r}: nights must be >= 1")
        if not self.room_rate:
            raise ValueError(f"stay {self.id!r}: room_rate is empty")
        if not self.present_segment_ids:
            raise ValueError(f"stay {self.id!r}: no segments present")
        object.__setattr__(
            self, "room_rate", {occ: money(v) for occ, v in self.room_rate.items()}
        )


@dataclass(frozen=True)
class Component:
    """A non-accommodation cost (transport, guide, tickets) and its bucket.

    `applies_to` is the set of segment ids that share/receive the cost. For a
    SHARED component the per-pax cost is `amount ÷ Σ pax in applies_to`; for a
    DIRECT component `amount` is already per-pax.
    """

    id: Id
    label: str
    kind: ComponentKind
    amount: Money
    applies_to: frozenset[Id]

    def __post_init__(self) -> None:
        if not self.applies_to:
            raise ValueError(f"component {self.id!r}: applies_to is empty")
        amount = money(self.amount)
        if amount < 0:
            raise ValueError(f"component {self.id!r}: amount must be >= 0")
        object.__setattr__(self, "amount", amount)


@dataclass(frozen=True)
class MarkupRule:
    id: Id
    basis: MarkupBasis
    rate: Money

    def __post_init__(self) -> None:
        rate = money(self.rate)
        if rate < 0:
            raise ValueError(f"markup {self.id!r}: rate must be >= 0")
        if self.basis is MarkupBasis.MARGIN_ON_SELL and rate >= 1:
            raise ValueError(f"markup {self.id!r}: margin_on_sell rate must be < 1")
        object.__setattr__(self, "rate", rate)

    def apply(self, cost: Money) -> Money:
        """Cost → selling price before tax (exact; no rounding here)."""
        if self.basis is MarkupBasis.MARKUP_ON_COST:
            return cost * (money(1) + self.rate)
        return cost / (money(1) - self.rate)


@dataclass(frozen=True)
class TaxRule:
    rate: Money
    treatment: TaxTreatment
    hsn: str | None = None

    def __post_init__(self) -> None:
        rate = money(self.rate)
        if rate < 0:
            raise ValueError("tax rate must be >= 0")
        object.__setattr__(self, "rate", rate)


@dataclass(frozen=True)
class FxRate:
    """INR per one unit of `currency` (e.g. USD @ 95 → 1 USD = 95 INR)."""

    currency: str
    inr_per_unit: Money

    def __post_init__(self) -> None:
        rate = money(self.inr_per_unit)
        if rate <= 0:
            raise ValueError("fx inr_per_unit must be > 0")
        object.__setattr__(self, "inr_per_unit", rate)


@dataclass(frozen=True)
class PricingInput:
    segments: tuple[Segment, ...]
    stays: tuple[Stay, ...]
    components: tuple[Component, ...]
    markup_rules: Mapping[Id, MarkupRule]
    tax_rule: TaxRule
    rounding: RoundingPolicy
    fx: FxRate | None = None
    margin_floor: Money | None = None  # guardrail (M7)

    def __post_init__(self) -> None:
        if not self.segments:
            raise ValueError("pricing input has no segments")
        ids = {s.id for s in self.segments}
        if len(ids) != len(self.segments):
            raise ValueError("duplicate segment ids")
        for s in self.segments:
            if s.markup_rule_id not in self.markup_rules:
                raise ValueError(
                    f"segment {s.id!r} references unknown markup rule {s.markup_rule_id!r}"
                )
        for stay in self.stays:
            unknown = stay.present_segment_ids - ids
            if unknown:
                raise ValueError(f"stay {stay.id!r} references unknown segment(s) {unknown}")
        for c in self.components:
            unknown = c.applies_to - ids
            if unknown:
                raise ValueError(f"component {c.id!r} references unknown segment(s) {unknown}")


# --------------------------------------------------------------------------- #
# outputs
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class TraceRef:
    """One line of the audit trail behind a number: what it was and how much."""

    kind: str  # accommodation | shared | direct | markup | tax
    label: str
    amount: Money


@dataclass(frozen=True)
class SegmentPrice:
    segment_id: Id
    label: str
    pax: int
    accommodation: Money
    shared: Money
    direct: Money
    base_cost: Money
    sell_per_pax: Money
    group_total: Money
    trace: tuple[TraceRef, ...] = ()


@dataclass(frozen=True)
class TaxBreakdown:
    """The tax split behind an invoice total (Part 2 §4.6).

    Invariant, enforced on construction: taxable + cgst + sgst + igst +
    rounding_adjustment == total. The `rounding_adjustment` is the (often −0.01)
    residual that reconciles the tax halves back to the round gross.
    """

    taxable: Money
    cgst: Money
    sgst: Money
    igst: Money
    rounding_adjustment: Money
    total: Money

    def __post_init__(self) -> None:
        for name in ("taxable", "cgst", "sgst", "igst", "rounding_adjustment", "total"):
            object.__setattr__(self, name, money(getattr(self, name)))
        parts = self.taxable + self.cgst + self.sgst + self.igst + self.rounding_adjustment
        if parts != self.total:
            raise ValueError(f"tax breakdown does not reconcile: {parts} != {self.total}")


@dataclass(frozen=True)
class PricedQuote:
    segments: tuple[SegmentPrice, ...]
    group_total: Money
    total_cost: Money
    profit: Money
    engine_version: str
    fx: Mapping[str, Money] | None = None
    tax: TaxBreakdown | None = None
