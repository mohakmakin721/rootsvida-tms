"""Seed (or update) the initial organization and its GST tax rules.

Idempotent: the org is keyed on slug, tax rules on (org, scenario). Later
milestones (ingestion, review, pricing) need a valid `org_id` and the place-of-
supply rule set; this provides both. Run:  python scripts/seed_org.py
"""

from __future__ import annotations

import sys
import uuid
from decimal import Decimal
from pathlib import Path

SVC_DIR = Path(__file__).resolve().parents[1] / "services" / "domain-svc"
sys.path.insert(0, str(SVC_DIR))

from app.config import get_settings
from app.db import get_session
from app.models import Organization, TaxRule, User
from app.models.enums import GstTreatment, PlaceOfSupply, UserRole
from app.security.passwords import hash_password
from app.services.roles import ensure_system_roles
from sqlalchemy import select
from sqlalchemy.orm import Session

# The place-of-supply rule set (D-0013). Seller = Uttarakhand (05).
# scenario -> (treatment, cgst, sgst, igst, description)
_HALF = Decimal("0.025")
_FULL = Decimal("0.05")
_TAX_RULES = {
    PlaceOfSupply.INTRA_STATE: (
        GstTreatment.CGST_SGST, _HALF, _HALF, Decimal(0),
        "Buyer in Uttarakhand (same state): CGST 2.5% + SGST 2.5%.",
    ),
    PlaceOfSupply.INTER_STATE: (
        GstTreatment.IGST, Decimal(0), Decimal(0), _FULL,
        "Buyer in another Indian state: IGST 5%.",
    ),
    PlaceOfSupply.INTERNATIONAL: (
        GstTreatment.CGST_SGST, _HALF, _HALF, Decimal(0),
        "Buyer outside India: CGST 2.5% + SGST 2.5% (per current practice / "
        "sample invoice REPL/2627/TP10; confirm export/LUT treatment with CA). "
        "Overridable per booking.",
    ),
}


def seed_tax_rules(session: Session, org_id: uuid.UUID) -> int:
    """Upsert the three place-of-supply tax rules for the org. Returns count changed."""
    changed = 0
    for scenario, (treatment, cgst, sgst, igst, desc) in _TAX_RULES.items():
        row = session.scalar(
            select(TaxRule).where(TaxRule.org_id == org_id, TaxRule.scenario == scenario)
        )
        if row is None:
            row = TaxRule(org_id=org_id, scenario=scenario)
            session.add(row)
            changed += 1
        row.treatment = treatment
        row.gst_rate = _FULL
        row.cgst_rate = cgst
        row.sgst_rate = sgst
        row.igst_rate = igst
        row.hsn = "998555"
        row.rounding_policy = "gross_nearest_100"
        row.description = desc
        row.is_default = True
    return changed


def seed_org() -> None:
    settings = get_settings()
    gen = get_session()
    session = next(gen)
    try:
        org = session.scalar(
            select(Organization).where(Organization.slug == settings.rv_org_slug)
        )
        if org is None:
            org = Organization(name=settings.rv_org_name, slug=settings.rv_org_slug)
            session.add(org)
            action = "created"
        else:
            action = "already present (synced)"
        org.name = settings.rv_org_name
        org.gstin = settings.rv_gstin
        org.pan = settings.rv_pan
        org.gst_state_code = settings.rv_gst_state_code
        org.gst_state_name = settings.rv_gst_state_name
        session.flush()

        rules_changed = seed_tax_rules(session, org.id)
        ensure_system_roles(session, org.id)

        owner = session.scalar(
            select(User).where(User.org_id == org.id, User.email == settings.rv_owner_email)
        )
        if owner is None:
            owner = User(org_id=org.id, email=settings.rv_owner_email, name="Owner",
                         role=UserRole.OWNER.value,
                         password_hash=hash_password(settings.rv_owner_password))
            session.add(owner)
            owner_action = f"created ({settings.rv_owner_email})"
        else:
            owner_action = "already present"

        print(f"Organization {action}: {org.slug} -> {org.id}")
        print(f"  GST: {org.gstin} ({org.gst_state_name} / {org.gst_state_code})")
        print(f"  Tax rules seeded (3 scenarios; {rules_changed} newly created)")
        print(f"  Owner user {owner_action} [role=owner] — rotate RV_OWNER_PASSWORD in .env")
        next(gen, None)  # trigger commit in the generator's commit path
    finally:
        gen.close()


if __name__ == "__main__":
    seed_org()
