"""DB-backed tests for the Milestone 3 canonical schema.

Requires a reachable Postgres (skipped otherwise); runs in a rolled-back
transaction. Uses SAVEPOINTs around statements expected to violate a constraint
so the session stays usable.
"""

from __future__ import annotations

from datetime import date

import pytest
from app.config import get_settings
from app.models import Organization, Rate, RoomType, Supplier
from app.models.enums import MealPlan, Occupancy, RateLifecycle, SupplierKind
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def _org_id(session: Session):
    """The org id, creating it if absent so the test is self-contained.

    CI applies migrations but does not seed, so `organizations` is empty there;
    locally it's seeded. Get-or-create by slug works either way (and is rolled
    back with the test's transaction), mirroring tests/test_ingestion_migrate.py.
    """
    s = get_settings()
    org = session.scalar(select(Organization).where(Organization.slug == s.rv_org_slug))
    if org is None:
        org = Organization(name=s.rv_org_name, slug=s.rv_org_slug)
        session.add(org)
        session.flush()
    return org.id


def _supplier(session: Session, **kw) -> Supplier:
    s = Supplier(
        org_id=_org_id(session),
        kind=SupplierKind.STAY,
        legal_name="Test Hotel",
        display_name="Test Hotel",
        **kw,
    )
    session.add(s)
    session.flush()
    return s


def test_all_canonical_tables_exist(db_session: Session) -> None:
    tables = set(inspect(db_session.get_bind()).get_table_names())
    expected = {
        "destinations", "suppliers", "supplier_commercials", "supplier_contacts",
        "room_types", "rates", "transport_rates", "activity_rates",
        "guide_rates", "misc_costs",
    }
    assert expected <= tables


def test_commission_isolated_from_suppliers(db_session: Session) -> None:
    """Commission must NOT be a column on suppliers; it lives in the restricted
    supplier_commercials table (DECISIONS.md D-0002)."""
    insp = inspect(db_session.get_bind())
    supplier_cols = {c["name"] for c in insp.get_columns("suppliers")}
    assert "commission_pct" not in supplier_cols
    assert "commission_notes" not in supplier_cols
    commercial_cols = {c["name"] for c in insp.get_columns("supplier_commercials")}
    assert {"commission_pct", "commission_notes"} <= commercial_cols


def test_rate_lifecycle_defaults_to_candidate(db_session: Session) -> None:
    s = _supplier(db_session)
    r = Rate(
        org_id=s.org_id, supplier_id=s.id,
        meal_plan=MealPlan.CP, occupancy=Occupancy.DOUBLE,
        amount=5000, valid_from=date(2026, 1, 1), valid_to=date(2026, 12, 31),
    )
    db_session.add(r)
    db_session.flush()
    db_session.expire(r)
    # Nothing auto-verifies: a fresh rate is a candidate, never 'verified'.
    assert r.lifecycle is RateLifecycle.CANDIDATE


def test_overlapping_rates_rejected_with_room_type(db_session: Session) -> None:
    s = _supplier(db_session)
    rt = RoomType(org_id=s.org_id, supplier_id=s.id, name="Deluxe")
    db_session.add(rt)
    db_session.flush()

    common = {
        "org_id": s.org_id, "supplier_id": s.id, "room_type_id": rt.id,
        "meal_plan": MealPlan.CP, "occupancy": Occupancy.DOUBLE,
    }
    db_session.add(Rate(amount=5000, valid_from=date(2026, 1, 1),
                        valid_to=date(2026, 12, 31), **common))
    db_session.flush()

    with pytest.raises(IntegrityError), db_session.begin_nested():  # rates_no_overlap
        db_session.add(Rate(amount=6000, valid_from=date(2026, 6, 1),
                            valid_to=date(2026, 7, 1), **common))
        db_session.flush()


def test_negative_amount_rejected(db_session: Session) -> None:
    s = _supplier(db_session)
    # ck_rates_amount_non_negative
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(Rate(
            org_id=s.org_id, supplier_id=s.id,
            meal_plan=MealPlan.CP, occupancy=Occupancy.DOUBLE,
            amount=-1, valid_from=date(2026, 1, 1), valid_to=date(2026, 12, 31),
        ))
        db_session.flush()
