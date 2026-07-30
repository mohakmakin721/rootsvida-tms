"""Phase 3 M2 — pricing bridge: a DB itinerary reproduces the Jaipur golden.

Seeds the full Jaipur trip as real rows (project, itinerary, segments, days,
presence, stay + shared components, markup rules), runs it through the bridge and
the pure engine, and asserts the same to-the-rupee golden numbers as the pure
fixture — proving the DB → engine mapping is faithful.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.models import (
    DaySegmentPresence,
    Itinerary,
    ItineraryComponent,
    ItineraryDay,
    MarkupRule,
    Organization,
    Project,
    TravellerSegment,
)
from app.models.enums import (
    AllocationBasis,
    ComponentKind,
    MarkupBasis,
    Occupancy,
    PaxClass,
)
from app.services.pricing_bridge import build_pricing_input
from pricing import model as pm
from pricing.engine import price
from sqlalchemy.orm import Session

# Itinerary: (single_rate, double_rate) per night; days 5-6 are Delhi (no Indians).
_NIGHTS = [(7300, 7300), (5500, 5500), (5500, 5500), (5000, 6000), (5000, 5500), (4000, 4500)]
# Other costs: (label, amount, allocation, pax_class)
_SHARED = [
    ("Transport", 41000, AllocationBasis.ALL_PAX, None),
    ("Jaipur Guide", 4000, AllocationBasis.ALL_PAX, None),
    ("Agra Guide", 2500, AllocationBasis.ALL_PAX, None),
    ("Rohan TA/DA", 25000, AllocationBasis.ALL_PAX, None),
    ("Rohan Fee", 21000, AllocationBasis.ALL_PAX, None),
    ("Delhi Urbania", 8000, AllocationBasis.BY_PAX_CLASS, PaxClass.FOREIGN),
    ("Jaipur Mon F", 18900, AllocationBasis.BY_PAX_CLASS, PaxClass.FOREIGN),
    ("Agra Mon F", 13650, AllocationBasis.BY_PAX_CLASS, PaxClass.FOREIGN),
    ("Delhi Mon F", 10500, AllocationBasis.BY_PAX_CLASS, PaxClass.FOREIGN),
    ("Delhi Cycle", 15400, AllocationBasis.BY_PAX_CLASS, PaxClass.FOREIGN),
    ("Misc", 15000, AllocationBasis.BY_PAX_CLASS, PaxClass.FOREIGN),
    ("Jaipur Mon I", 1000, AllocationBasis.BY_PAX_CLASS, PaxClass.INDIAN),
    ("Agra Mon I", 600, AllocationBasis.BY_PAX_CLASS, PaxClass.INDIAN),
    ("Delhi Mon I", 0, AllocationBasis.BY_PAX_CLASS, PaxClass.INDIAN),
]


def _seed_jaipur(session: Session) -> uuid.UUID:
    from scripts.seed_org import seed_tax_rules

    org = Organization(name="Jaipur QA", slug=f"jp-{uuid.uuid4().hex[:8]}", gst_state_code="05")
    session.add(org)
    session.flush()
    seed_tax_rules(session, org.id)

    foreign = MarkupRule(org_id=org.id, label="Foreign 15%", basis=MarkupBasis.MARKUP_ON_COST,
                         rate=Decimal("0.15"))
    indian = MarkupRule(org_id=org.id, label="Indian 10%", basis=MarkupBasis.MARKUP_ON_COST,
                        rate=Decimal("0.10"))
    session.add_all([foreign, indian])
    session.flush()

    project = Project(org_id=org.id, code="TP-JP", client_name="Golden Triangle")
    session.add(project)
    session.flush()
    itinerary = Itinerary(org_id=org.id, project_id=project.id, title="Jaipur / Golden Triangle",
                          start_date=date(2026, 7, 18), end_date=date(2026, 7, 23))
    session.add(itinerary)
    session.flush()

    def _seg(label: str, occ: Occupancy, cls: PaxClass, n: int, rule: MarkupRule) -> TravellerSegment:
        s = TravellerSegment(org_id=org.id, itinerary_id=itinerary.id, label=label,
                             pax_class=cls, occupancy=occ, pax_count=n, markup_rule_id=rule.id)
        session.add(s)
        session.flush()
        return s

    fs = _seg("Foreign Single", Occupancy.SINGLE, PaxClass.FOREIGN, 1, foreign)
    fd = _seg("Foreign Double", Occupancy.DOUBLE, PaxClass.FOREIGN, 6, foreign)
    ind = _seg("Indian Double", Occupancy.DOUBLE, PaxClass.INDIAN, 2, indian)

    days = []
    for i, (single_rate, double_rate) in enumerate(_NIGHTS, start=1):
        day = ItineraryDay(org_id=org.id, itinerary_id=itinerary.id, day_number=i,
                           date=date(2026, 7, 17) + timedelta(days=i))
        session.add(day)
        session.flush()
        days.append(day)
        present = [fs, fd, ind] if i <= 4 else [fs, fd]  # Indians only days 1-4
        for seg in present:
            session.add(DaySegmentPresence(org_id=org.id, itinerary_day_id=day.id,
                                           traveller_segment_id=seg.id))
        # one stay per occupancy
        session.add(ItineraryComponent(
            org_id=org.id, itinerary_day_id=day.id, kind=ComponentKind.STAY,
            override_amount=Decimal(single_rate), override_reason="manual",
            applies_to_segment_ids=[fs.id], description="Single room",
        ))
        session.add(ItineraryComponent(
            org_id=org.id, itinerary_day_id=day.id, kind=ComponentKind.STAY,
            override_amount=Decimal(double_rate), override_reason="manual",
            applies_to_segment_ids=[fd.id, ind.id], description="Double room",
        ))

    for label, amount, alloc, cls in _SHARED:  # all shared costs on day 1
        session.add(ItineraryComponent(
            org_id=org.id, itinerary_day_id=days[0].id, kind=ComponentKind.MISC,
            override_amount=Decimal(amount), override_reason="manual",
            allocation=alloc, applies_to_pax_class=cls, description=label,
        ))
    session.flush()
    return itinerary.id


def test_bridge_reproduces_jaipur_golden(db_session: Session) -> None:
    itinerary_id = _seed_jaipur(db_session)
    inp = build_pricing_input(
        db_session, itinerary_id, buyer_state_code="05", buyer_country="IN",
        rounding=pm.RoundingPolicy.NEAREST_1, fx_inr_per_usd=Decimal(95),
    )
    quote = price(inp)
    sell = {s.label: s.sell_per_pax for s in quote.segments}

    assert sell["Foreign Single"] == Decimal(65597)
    assert sell["Foreign Double"] == Decimal(47303)
    assert sell["Indian Double"] == Decimal(26956)
    assert quote.group_total == Decimal(403327)
    assert quote.profit == Decimal("67277.00")
    assert quote.fx is not None and quote.fx["USD"] == Decimal("4245.55")


def test_bridge_resolves_place_of_supply(db_session: Session) -> None:
    itinerary_id = _seed_jaipur(db_session)
    # A Delhi buyer -> inter-state -> IGST rule flows through to the engine input.
    inp = build_pricing_input(db_session, itinerary_id, buyer_state_code="07", buyer_country="IN")
    assert inp.tax_rule.treatment is pm.TaxTreatment.IGST
    assert inp.tax_rule.rate == Decimal("0.05")
