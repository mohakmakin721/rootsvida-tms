"""Pricing bridge — a DB itinerary → the pure engine's PricingInput (Phase 3 M2).

Reads an itinerary (segments, days, presence, components, markup rules) and the
resolved GST rule, and assembles the frozen dataclasses the Phase-2 engine prices.
The engine stays pure; all DB access lives here.

Component → engine mapping:
  * STAY      → a `Stay` with room_rate {occupancy: amount} for the segments the
                room is assigned to (`applies_to_segment_ids`, else the linked
                rate's occupancy), intersected with who is present that day.
  * otherwise → a `Component`; the allocation basis picks the bucket and whether
                it is SHARED (split ÷ bucket pax) or DIRECT (per-pax).

Amounts come from `override_amount` (which requires a reason) or the linked
canonical rate's `amount`.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    DaySegmentPresence,
    Itinerary,
    ItineraryComponent,
    ItineraryDay,
    MarkupRule,
    Rate,
    TransportRate,
    TravellerSegment,
)
from app.models.enums import AllocationBasis, PlaceOfSupply
from app.models.enums import ComponentKind as DbComponentKind
from app.models.enums import Occupancy as DbOccupancy
from app.services.tax import resolve_tax_rule, to_pricing_tax_rule
from pricing import model as pm
from pricing.money import money

_OCCUPANCY = {
    DbOccupancy.SINGLE: pm.Occupancy.SINGLE,
    DbOccupancy.DOUBLE: pm.Occupancy.DOUBLE,
    DbOccupancy.TRIPLE: pm.Occupancy.TRIPLE,
}


def _to_pricing_occupancy(occ: DbOccupancy) -> pm.Occupancy:
    try:
        return _OCCUPANCY[occ]
    except KeyError:
        raise NotImplementedError(f"occupancy {occ.value!r} not yet priced") from None


def _dec(value: object) -> Decimal:
    """Coerce a stored money value to Decimal. Numeric columns are typed `float`
    in the models but are Decimal at runtime; `str()` keeps them exact either way."""
    return money(value) if isinstance(value, (int, str, Decimal)) else money(Decimal(str(value)))


def _resolve_amount(session: Session, comp: ItineraryComponent) -> Decimal:
    if comp.override_amount is not None:
        return _dec(comp.override_amount)
    if comp.rate_id is not None:
        rate = session.get(Rate, comp.rate_id)
        if rate is not None:
            return _dec(rate.amount)
    if comp.transport_rate_id is not None:
        transport = session.get(TransportRate, comp.transport_rate_id)
        if transport is not None:
            return _dec(transport.amount)
    raise ValueError(f"component {comp.id!r} has neither an override nor a resolvable rate")


def _markup_rules(session: Session, segments: list[TravellerSegment]) -> dict[str, pm.MarkupRule]:
    ids = {s.markup_rule_id for s in segments if s.markup_rule_id is not None}
    rules: dict[str, pm.MarkupRule] = {}
    for row in session.scalars(select(MarkupRule).where(MarkupRule.id.in_(ids))):
        rules[str(row.id)] = pm.MarkupRule(
            id=str(row.id), basis=pm.MarkupBasis(row.basis.value), rate=money(row.rate)
        )
    return rules


def _segments(rows: list[TravellerSegment]) -> tuple[pm.Segment, ...]:
    out = []
    for s in rows:
        if s.markup_rule_id is None:
            raise ValueError(f"segment {s.id!r} has no markup rule")
        out.append(
            pm.Segment(
                id=str(s.id), label=s.label, occupancy=_to_pricing_occupancy(s.occupancy),
                pax=s.pax_count, markup_rule_id=str(s.markup_rule_id),
            )
        )
    return tuple(out)


def _bucket(
    comp: ItineraryComponent, all_ids: frozenset[str], seg_by_id: dict[str, TravellerSegment]
) -> frozenset[str]:
    a = comp.allocation
    if a in (AllocationBasis.ALL_PAX, AllocationBasis.FIXED_GROUP):
        return all_ids
    if a == AllocationBasis.BY_PAX_CLASS:
        return frozenset(
            sid for sid, s in seg_by_id.items() if s.pax_class == comp.applies_to_pax_class
        )
    return frozenset(str(x) for x in (comp.applies_to_segment_ids or []))


def _stay(
    session: Session,
    comp: ItineraryComponent,
    present: frozenset[str],
    seg_by_id: dict[str, TravellerSegment],
) -> pm.Stay | None:
    assigned = frozenset(str(x) for x in (comp.applies_to_segment_ids or [])) or present
    here = assigned & present
    if not here:
        return None  # a room nobody present uses
    occupancies = {seg_by_id[sid].occupancy for sid in here}
    if len(occupancies) != 1:
        raise ValueError(f"stay {comp.id!r} mixes occupancies {occupancies}")
    occ = _to_pricing_occupancy(next(iter(occupancies)))
    return pm.Stay(
        id=str(comp.id),
        label=comp.description or "stay",
        nights=int(comp.quantity),
        room_rate={occ: _resolve_amount(session, comp)},
        present_segment_ids=here,
    )


def build_pricing_input(
    session: Session,
    itinerary_id: uuid.UUID,
    *,
    buyer_state_code: str | None = None,
    buyer_country: str | None = "IN",
    tax_override: PlaceOfSupply | None = None,
    rounding: pm.RoundingPolicy = pm.RoundingPolicy.NEAREST_1,
    fx_inr_per_usd: Decimal | None = None,
    margin_floor: Decimal | None = None,
) -> pm.PricingInput:
    """Assemble the engine input for `itinerary_id` under the resolved GST rule."""
    itinerary = session.get(Itinerary, itinerary_id)
    if itinerary is None:
        raise LookupError(f"itinerary {itinerary_id!r} not found")

    seg_rows = list(
        session.scalars(
            select(TravellerSegment).where(TravellerSegment.itinerary_id == itinerary_id)
        )
    )
    seg_by_id = {str(s.id): s for s in seg_rows}
    all_ids = frozenset(seg_by_id)

    tax_rule = to_pricing_tax_rule(
        resolve_tax_rule(
            session, itinerary.org_id, buyer_state_code=buyer_state_code,
            buyer_country=buyer_country, override=tax_override,
        )
    )

    days = list(
        session.scalars(
            select(ItineraryDay).where(ItineraryDay.itinerary_id == itinerary_id)
        )
    )
    presence: dict[uuid.UUID, frozenset[str]] = {}
    for d in days:
        ids = session.scalars(
            select(DaySegmentPresence.traveller_segment_id).where(
                DaySegmentPresence.itinerary_day_id == d.id
            )
        )
        presence[d.id] = frozenset(str(x) for x in ids)

    stays: list[pm.Stay] = []
    components: list[pm.Component] = []
    for d in days:
        present = presence.get(d.id, frozenset())
        for comp in session.scalars(
            select(ItineraryComponent).where(ItineraryComponent.itinerary_day_id == d.id)
        ):
            if comp.kind == DbComponentKind.STAY:
                stay = _stay(session, comp, present, seg_by_id)
                if stay is not None:
                    stays.append(stay)
            else:
                kind = (
                    pm.ComponentKind.DIRECT
                    if comp.allocation == AllocationBasis.PER_PAX_DIRECT
                    else pm.ComponentKind.SHARED
                )
                bucket = _bucket(comp, all_ids, seg_by_id)
                if not bucket:
                    continue
                components.append(
                    pm.Component(
                        id=str(comp.id), label=comp.description or comp.kind.value,
                        kind=kind, amount=_resolve_amount(session, comp), applies_to=bucket,
                    )
                )

    fx = pm.FxRate("USD", money(fx_inr_per_usd)) if fx_inr_per_usd is not None else None
    return pm.PricingInput(
        segments=_segments(seg_rows),
        stays=tuple(stays),
        components=tuple(components),
        markup_rules=_markup_rules(session, seg_rows),
        tax_rule=tax_rule,
        rounding=rounding,
        fx=fx,
        margin_floor=margin_floor,
    )
