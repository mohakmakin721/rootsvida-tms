"""Live pricing preview (Phase 3 M7) — price a draft itinerary without saving it.

Powers the builder's live cost sidebar. The draft is materialised into real rows
inside a SAVEPOINT, priced through the **exact** golden path (`build_pricing_input`
+ the pure engine), then the savepoint is rolled back — so a preview reproduces a
saved quote to the rupee while persisting nothing (D-0001: determinism owns every
number; this endpoint only computes).

Unlike issuing a quote, a preview never *raises* on a thin margin — it returns the
number with a `below_floor` flag so the builder can warn while still showing where
the price stands.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models import Project
from app.models.enums import PlaceOfSupply
from app.services.itinerary import ItineraryDraft, build_itinerary
from app.services.pricing_bridge import build_pricing_input
from pricing import model as pm
from pricing.engine import price

_HUNDRED = Decimal(100)


def _serialize(inp: pm.PricingInput, priced: pm.PricedQuote,
               margin_floor: Decimal | None) -> dict[str, Any]:
    margin_pct = priced.margin_pct * _HUNDRED
    return {
        "engine_version": priced.engine_version,
        "segments": [
            {
                "label": s.label,
                "pax": s.pax,
                "base_cost": str(s.base_cost.quantize(Decimal("0.01"))),
                "sell_per_pax": str(s.sell_per_pax),
                "group_total": str(s.group_total),
            }
            for s in priced.segments
        ],
        "total_cost": str(priced.total_cost),
        "group_total": str(priced.group_total),
        "profit": str(priced.profit),
        "revenue_ex_tax": str(priced.revenue_ex_tax),
        "margin_pct": str(margin_pct.quantize(Decimal("0.01"))),
        "gst_rate": str((inp.tax_rule.rate * _HUNDRED).quantize(Decimal("0.01"))),
        "gst_treatment": inp.tax_rule.treatment.value,
        "fx": {k: str(v) for k, v in priced.fx.items()} if priced.fx else None,
        "margin_floor": None if margin_floor is None else str(margin_floor * _HUNDRED),
        "below_floor": margin_floor is not None and priced.margin_pct < margin_floor,
    }


def preview_pricing(
    session: Session,
    org_id: uuid.UUID,
    draft: ItineraryDraft,
    *,
    buyer_state_code: str | None = None,
    buyer_country: str | None = "IN",
    tax_override: PlaceOfSupply | None = None,
    rounding: pm.RoundingPolicy = pm.RoundingPolicy.NEAREST_1,
    fx_inr_per_usd: Decimal | None = None,
    margin_floor: Decimal | None = None,
) -> dict[str, Any]:
    """Price `draft` and return the breakdown for the sidebar. Persists nothing."""
    savepoint = session.begin_nested()
    try:
        project = Project(
            org_id=org_id, code=f"__preview_{uuid.uuid4().hex[:12]}",
            client_name="(preview)",
        )
        session.add(project)
        session.flush()
        itinerary = build_itinerary(session, org_id, project.id, draft)

        # The floor is applied by us (below_floor), not by the engine — a preview
        # must show a thin-margin number rather than raise on it.
        inp = build_pricing_input(
            session, itinerary.id, buyer_state_code=buyer_state_code,
            buyer_country=buyer_country, tax_override=tax_override, rounding=rounding,
            fx_inr_per_usd=fx_inr_per_usd, margin_floor=None,
        )
        priced = price(inp)
        return _serialize(inp, priced, margin_floor)
    finally:
        savepoint.rollback()
