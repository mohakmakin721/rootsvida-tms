"""Client proposal — assemble the data for the sales PDF (Phase 4).

A proposal is a client-facing sales document rendered on demand from a quote (its
per-person pricing, currency and validity) and that quote's itinerary (the day-by-
day outline). It is NOT a stored record and carries **no internal figures** — no
costs, no margin, no per-component amounts. Inclusions are friendly labels derived
from the *kinds* of component present, never the raw cost-line descriptions.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Destination,
    Itinerary,
    ItineraryComponent,
    ItineraryDay,
    Organization,
    Project,
    Quote,
    QuoteLine,
)

# Component kind → the client-friendly inclusion line it implies.
_INCLUSION_LABELS: dict[str, str] = {
    "stay": "Accommodation as per the itinerary",
    "transport": "Private transfers and ground transport",
    "guide": "Expert local guides",
    "activity": "Sightseeing, experiences and entry fees",
    "meal": "Meals as specified",
    "permit": "Permits and monument fees",
    # 'misc' is deliberately excluded — it often carries internal fee lines.
}
_INCLUSION_ORDER = ["stay", "transport", "guide", "activity", "meal", "permit"]


class ProposalError(Exception):
    """Blocks proposal generation (e.g. the quote or itinerary is missing)."""


def build_proposal(session: Session, org_id: uuid.UUID, quote_id: uuid.UUID) -> dict[str, Any]:
    quote = session.scalar(select(Quote).where(Quote.id == quote_id, Quote.org_id == org_id))
    if quote is None:
        raise ProposalError("quote not found")
    itinerary = session.get(Itinerary, quote.itinerary_id)
    if itinerary is None:
        raise ProposalError("itinerary not found")
    project = session.get(Project, quote.project_id)
    org = session.get(Organization, org_id)

    days = list(session.scalars(
        select(ItineraryDay)
        .where(ItineraryDay.itinerary_id == itinerary.id)
        .order_by(ItineraryDay.day_number)
    ))
    dest_names: dict[uuid.UUID, str] = {
        did: name
        for did, name in session.execute(select(Destination.id, Destination.name)).all()
    }

    kinds_present: set[str] = set()
    day_out: list[dict[str, Any]] = []
    for d in days:
        comps = session.scalars(
            select(ItineraryComponent).where(ItineraryComponent.itinerary_day_id == d.id)
        )
        for c in comps:
            kinds_present.add(c.kind.value)
        day_out.append({
            "day_number": d.day_number,
            "date": d.date.isoformat(),
            "destination": dest_names.get(d.destination_id) if d.destination_id else None,
            "narrative": d.narrative,
        })

    inclusions = [_INCLUSION_LABELS[k] for k in _INCLUSION_ORDER if k in kinds_present]

    fx_rate = quote.fx_rate_inr_usd
    groups: list[dict[str, Any]] = []
    for ln in session.scalars(
        select(QuoteLine).where(QuoteLine.quote_id == quote.id).order_by(QuoteLine.description)
    ):
        per_pax = ln.sell_per_pax
        groups.append({
            "label": ln.description,
            "pax": ln.pax_count,
            "per_pax_inr": None if per_pax is None else str(per_pax),
            "per_pax_fx": (
                str((per_pax / fx_rate).quantize(Decimal("0.01")))
                if per_pax is not None and fx_rate else None
            ),
        })

    nights = (itinerary.end_date - itinerary.start_date).days

    return {
        "seller_name": (org.name if org else "RootsVida"),
        "client_name": (project.client_name if project else "Guest"),
        "project_code": (project.code if project else None),
        "title": itinerary.title,
        "start_date": itinerary.start_date.isoformat(),
        "end_date": itinerary.end_date.isoformat(),
        "nights": nights,
        "valid_until": quote.valid_until.isoformat() if quote.valid_until else None,
        "fx_currency": quote.fx_currency,
        "total_inr": None if quote.total_gross is None else str(quote.total_gross),
        "total_fx": (
            str((quote.total_gross / fx_rate).quantize(Decimal("0.01")))
            if quote.total_gross is not None and fx_rate else None
        ),
        "days": day_out,
        "inclusions": inclusions,
        "groups": groups,
    }
