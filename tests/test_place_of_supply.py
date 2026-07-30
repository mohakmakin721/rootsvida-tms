"""Phase 2 M7 — place-of-supply resolution + DB tax rules.

Pure classifier + adapter (no DB), then the DB resolver end-to-end and its
integration with the pure tax split. Seller is Uttarakhand (05).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from app.models import Organization, TaxRule
from app.models.enums import GstTreatment, PlaceOfSupply
from app.services.tax import (
    classify_place_of_supply,
    resolve_tax_rule,
    to_pricing_tax_rule,
)
from pricing.money import money
from pricing.tax import split_tax
from sqlalchemy.orm import Session

_UK = "05"  # Uttarakhand


# --------------------------------------------------------------------------- #
# pure classifier
# --------------------------------------------------------------------------- #


def test_same_state_is_intra() -> None:
    got = classify_place_of_supply(seller_state_code=_UK, buyer_state_code="05", buyer_country="IN")
    assert got is PlaceOfSupply.INTRA_STATE


def test_leading_zero_insensitive() -> None:
    got = classify_place_of_supply(seller_state_code=_UK, buyer_state_code="5", buyer_country="IN")
    assert got is PlaceOfSupply.INTRA_STATE


def test_other_indian_state_is_inter() -> None:
    got = classify_place_of_supply(seller_state_code=_UK, buyer_state_code="07", buyer_country="IN")
    assert got is PlaceOfSupply.INTER_STATE


def test_domestic_without_state_defaults_inter() -> None:
    got = classify_place_of_supply(seller_state_code=_UK, buyer_state_code=None, buyer_country="IN")
    assert got is PlaceOfSupply.INTER_STATE


def test_outside_india_is_international() -> None:
    for country in ("CL", "US", "Chile", "GB"):
        got = classify_place_of_supply(
            seller_state_code=_UK, buyer_state_code=None, buyer_country=country
        )
        assert got is PlaceOfSupply.INTERNATIONAL


def test_adapter_maps_to_pricing_tax_rule() -> None:
    row = TaxRule(
        scenario=PlaceOfSupply.INTRA_STATE,
        treatment=GstTreatment.CGST_SGST,
        gst_rate=Decimal("0.05"),
        hsn="998555",
    )
    from pricing.model import TaxTreatment

    adapted = to_pricing_tax_rule(row)
    assert adapted.rate == Decimal("0.05")
    assert adapted.treatment is TaxTreatment.CGST_SGST
    assert adapted.hsn == "998555"


# --------------------------------------------------------------------------- #
# DB resolver (rolled back; fresh org so counts are deterministic)
# --------------------------------------------------------------------------- #


def _org_with_rules(session: Session) -> uuid.UUID:
    from scripts.seed_org import seed_tax_rules

    org = Organization(
        name="POS QA", slug=f"pos-{uuid.uuid4().hex[:8]}", gst_state_code=_UK,
        gst_state_name="Uttarakhand",
    )
    session.add(org)
    session.flush()
    seed_tax_rules(session, org.id)
    session.flush()
    return org.id


def test_resolver_picks_the_right_rule(db_session: Session) -> None:
    org_id = _org_with_rules(db_session)

    intra = resolve_tax_rule(db_session, org_id, buyer_state_code="05", buyer_country="IN")
    assert intra.treatment is GstTreatment.CGST_SGST

    inter = resolve_tax_rule(db_session, org_id, buyer_state_code="07", buyer_country="IN")
    assert inter.treatment is GstTreatment.IGST

    intl = resolve_tax_rule(db_session, org_id, buyer_state_code=None, buyer_country="CL")
    assert intl.scenario is PlaceOfSupply.INTERNATIONAL
    assert intl.treatment is GstTreatment.CGST_SGST  # user's choice


def test_override_wins(db_session: Session) -> None:
    org_id = _org_with_rules(db_session)
    # A Uttarakhand buyer would be intra-state, but an explicit override forces IGST.
    rule = resolve_tax_rule(
        db_session, org_id, buyer_state_code="05", buyer_country="IN",
        override=PlaceOfSupply.INTER_STATE,
    )
    assert rule.treatment is GstTreatment.IGST


def test_resolver_integrates_with_the_tax_split(db_session: Session) -> None:
    org_id = _org_with_rules(db_session)
    # International (Chile) -> CGST+SGST -> reproduces the TP10 invoice split.
    rule = resolve_tax_rule(db_session, org_id, buyer_state_code=None, buyer_country="CL")
    breakdown = split_tax(money(169700), to_pricing_tax_rule(rule))
    assert breakdown.cgst == Decimal("4040.48")
    assert breakdown.sgst == Decimal("4040.48")
    assert breakdown.igst == Decimal(0)

    # A Delhi buyer -> IGST -> a single levy instead.
    rule2 = resolve_tax_rule(db_session, org_id, buyer_state_code="07", buyer_country="IN")
    b2 = split_tax(money(169700), to_pricing_tax_rule(rule2))
    assert b2.igst == Decimal("8080.95")
    assert b2.cgst == Decimal(0) and b2.sgst == Decimal(0)


def test_missing_rule_raises(db_session: Session) -> None:
    org = Organization(name="Bare", slug=f"bare-{uuid.uuid4().hex[:8]}", gst_state_code=_UK)
    db_session.add(org)
    db_session.flush()
    with pytest.raises(LookupError):
        resolve_tax_rule(db_session, org.id, buyer_state_code="05", buyer_country="IN")
