"""Place-of-supply resolution: booking → the GST rule that applies (Part 2 §1.4).

`classify_place_of_supply` is pure (seller vs buyer state/country). `resolve_tax_rule`
looks up the matching `tax_rules` row for the org, and `to_pricing_tax_rule` adapts
it to the pure engine's `pricing.model.TaxRule`. The rule set lives in the DB
(D-0013), so the operator can change a treatment without a code change; an explicit
`override` (with a reason recorded by the caller) wins over the computed scenario.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Organization, TaxRule
from app.models.enums import PlaceOfSupply
from pricing.model import TaxRule as PricingTaxRule
from pricing.model import TaxTreatment

_INDIA = {"IN", "IND", "INDIA"}


def _norm_state(code: str | None) -> str | None:
    """GST state code, leading-zero-insensitive ('05' == '5')."""
    if code is None:
        return None
    stripped = code.strip().lstrip("0")
    return stripped or "0"


def classify_place_of_supply(
    *, seller_state_code: str | None, buyer_state_code: str | None, buyer_country: str | None
) -> PlaceOfSupply:
    """Which GST scenario applies. International if the buyer is outside India;
    otherwise intra-state when the states match, else inter-state. A domestic
    buyer with no state resolves conservatively to inter-state (IGST)."""
    if (buyer_country or "IN").strip().upper() not in _INDIA:
        return PlaceOfSupply.INTERNATIONAL
    if buyer_state_code is not None and _norm_state(buyer_state_code) == _norm_state(
        seller_state_code
    ):
        return PlaceOfSupply.INTRA_STATE
    return PlaceOfSupply.INTER_STATE


def resolve_tax_rule(
    session: Session,
    org_id: uuid.UUID,
    *,
    buyer_state_code: str | None = None,
    buyer_country: str | None = "IN",
    override: PlaceOfSupply | None = None,
) -> TaxRule:
    """Return the `tax_rules` row for this booking's scenario (or `override`)."""
    seller_state_code = session.scalar(
        select(Organization.gst_state_code).where(Organization.id == org_id)
    )
    scenario = override or classify_place_of_supply(
        seller_state_code=seller_state_code,
        buyer_state_code=buyer_state_code,
        buyer_country=buyer_country,
    )
    rule = session.scalar(
        select(TaxRule).where(TaxRule.org_id == org_id, TaxRule.scenario == scenario)
    )
    if rule is None:
        raise LookupError(
            f"no tax rule for scenario {scenario.value!r} — run scripts/seed_org.py"
        )
    return rule


def to_pricing_tax_rule(rule: TaxRule) -> PricingTaxRule:
    """Adapt a DB tax rule to the pure engine's TaxRule (values map 1:1)."""
    return PricingTaxRule(
        rate=rule.gst_rate,
        treatment=TaxTreatment(rule.treatment.value),
        hsn=rule.hsn,
    )
