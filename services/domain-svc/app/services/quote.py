"""Quote issuance + the frozen snapshot (Phase 3 M3, Part 2 §4.4).

The system's data-integrity backbone: a quote captures its assumptions and a full
`pricing_snapshot` (every input rate/pax/rule + the priced output + engine
version), so it is reproducible and **never recomputed from live rates**. A draft
may be re-priced; issuing freezes it; a correction supersedes and creates a new
version (v2 never mutates v1). Immutability is also enforced by a DB trigger.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Itinerary, Quote, QuoteLine
from app.models.enums import GstTreatment, PlaceOfSupply
from app.services.pricing_bridge import build_pricing_input
from pricing import model as pm
from pricing.engine import price
from pricing.money import quantize

_HUNDRED = Decimal(100)


def _snapshot(inp: pm.PricingInput, quote: pm.PricedQuote) -> dict[str, Any]:
    """A JSON-safe, reproducible record: the frozen inputs + the priced output."""
    inputs = {
        "segments": [
            {"id": s.id, "label": s.label, "occupancy": s.occupancy.name,
             "pax": s.pax, "markup_rule_id": s.markup_rule_id}
            for s in inp.segments
        ],
        "stays": [
            {"id": st.id, "label": st.label, "nights": st.nights,
             "room_rate": {o.name: str(v) for o, v in st.room_rate.items()},
             "present": sorted(st.present_segment_ids)}
            for st in inp.stays
        ],
        "components": [
            {"id": c.id, "label": c.label, "kind": c.kind.value,
             "amount": str(c.amount), "applies_to": sorted(c.applies_to)}
            for c in inp.components
        ],
        "markup_rules": {
            k: {"basis": r.basis.value, "rate": str(r.rate)}
            for k, r in inp.markup_rules.items()
        },
        "tax_rule": {"rate": str(inp.tax_rule.rate),
                     "treatment": inp.tax_rule.treatment.value, "hsn": inp.tax_rule.hsn},
        "rounding": inp.rounding.value,
        "fx": ({"currency": inp.fx.currency, "inr_per_unit": str(inp.fx.inr_per_unit)}
               if inp.fx else None),
        "margin_floor": str(inp.margin_floor) if inp.margin_floor is not None else None,
    }
    output = {
        "segments": [
            {"segment_id": s.segment_id, "label": s.label, "pax": s.pax,
             "accommodation": str(s.accommodation), "shared": str(s.shared),
             "direct": str(s.direct), "base_cost": str(s.base_cost),
             "sell_per_pax": str(s.sell_per_pax), "group_total": str(s.group_total),
             "trace": [{"kind": t.kind, "label": t.label, "amount": str(t.amount)}
                       for t in s.trace]}
            for s in quote.segments
        ],
        "group_total": str(quote.group_total),
        "total_cost": str(quote.total_cost),
        "profit": str(quote.profit),
        "revenue_ex_tax": str(quote.revenue_ex_tax),
        "margin_pct": str(quote.margin_pct),
        "fx": {k: str(v) for k, v in quote.fx.items()} if quote.fx else None,
        "tax": (
            {"taxable": str(quote.tax.taxable), "cgst": str(quote.tax.cgst),
             "sgst": str(quote.tax.sgst), "igst": str(quote.tax.igst),
             "rounding_adjustment": str(quote.tax.rounding_adjustment),
             "total": str(quote.tax.total)}
            if quote.tax else None
        ),
    }
    return {"engine_version": quote.engine_version, "inputs": inputs, "output": output}


def _totals(priced: pm.PricedQuote) -> tuple[Decimal, Decimal, Decimal]:
    """(taxable, tax, gross) — from the tax breakdown if present, else derived."""
    if priced.tax is not None:
        return (priced.tax.taxable, priced.tax.cgst + priced.tax.sgst + priced.tax.igst,
                priced.tax.total)
    taxable = priced.revenue_ex_tax
    return taxable, quantize(priced.group_total - taxable), priced.group_total


def _next_version(session: Session, project_id: uuid.UUID) -> int:
    current = session.scalar(select(func.max(Quote.version)).where(Quote.project_id == project_id))
    return (current or 0) + 1


def create_quote(
    session: Session,
    itinerary_id: uuid.UUID,
    *,
    buyer_state_code: str | None = None,
    buyer_country: str | None = "IN",
    tax_override: PlaceOfSupply | None = None,
    rounding: pm.RoundingPolicy = pm.RoundingPolicy.NEAREST_1,
    fx_inr_per_usd: Decimal | None = None,
    margin_floor: Decimal | None = None,
) -> Quote:
    """Price an itinerary and persist a **draft** quote (with snapshot + lines).

    Raises `MarginBelowFloor` if a floor is set and breached (the caller may pass
    a margin override upstream to permit issuance)."""
    itinerary = session.get(Itinerary, itinerary_id)
    if itinerary is None:
        raise LookupError(f"itinerary {itinerary_id!r} not found")

    inp = build_pricing_input(
        session, itinerary_id, buyer_state_code=buyer_state_code, buyer_country=buyer_country,
        tax_override=tax_override, rounding=rounding, fx_inr_per_usd=fx_inr_per_usd,
        margin_floor=margin_floor,
    )
    priced = price(inp)
    taxable, tax_total, gross = _totals(priced)

    quote = Quote(
        org_id=itinerary.org_id,
        project_id=itinerary.project_id,
        itinerary_id=itinerary_id,
        version=_next_version(session, itinerary.project_id),
        status="draft",
        gst_rate=quantize(inp.tax_rule.rate * _HUNDRED),
        gst_treatment=GstTreatment(inp.tax_rule.treatment.value),
        fx_rate_inr_usd=inp.fx.inr_per_unit if inp.fx is not None else None,
        rounding_policy=inp.rounding.value,
        total_cost=priced.total_cost,
        total_taxable=quantize(taxable),
        total_tax=quantize(tax_total),
        total_gross=quantize(gross),
        margin_pct=quantize(priced.margin_pct * _HUNDRED),
        pricing_snapshot=_snapshot(inp, priced),
        engine_version=priced.engine_version,
    )
    session.add(quote)
    session.flush()

    for seg in priced.segments:
        session.add(QuoteLine(
            org_id=itinerary.org_id, quote_id=quote.id, description=seg.label,
            cost_per_pax=quantize(seg.base_cost), sell_per_pax=seg.sell_per_pax,
            pax_count=seg.pax, line_total=seg.group_total,
        ))
    session.flush()
    return quote


def issue_quote(
    session: Session,
    quote: Quote,
    *,
    issued_by: uuid.UUID | None = None,
    valid_until: date | None = None,
) -> Quote:
    """Freeze a draft: draft → issued, locking FX and stamping issuance. After this
    the DB trigger makes the quote immutable (only → 'superseded')."""
    if quote.status != "draft":
        raise ValueError(f"only a draft quote can be issued (status={quote.status!r})")
    now = datetime.now(UTC)
    quote.status = "issued"
    quote.issued_at = now
    quote.issued_by = issued_by
    quote.fx_rate_locked_at = now if quote.fx_rate_inr_usd is not None else None
    quote.valid_until = valid_until
    session.flush()
    return quote


def revise_issued_quote(
    session: Session, quote: Quote, **assumptions: Any
) -> Quote:
    """Correct an issued quote: supersede it and create a fresh draft at the next
    version (v2 never mutates v1). `assumptions` are passed to `create_quote`."""
    if quote.status not in ("issued", "accepted", "expired"):
        raise ValueError(f"only an issued quote can be revised (status={quote.status!r})")
    quote.status = "superseded"  # the one transition the trigger permits
    session.flush()
    return create_quote(session, quote.itinerary_id, **assumptions)
