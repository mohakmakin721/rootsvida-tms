"""Phase 3 M1 — itinerary/quote schema (DB-backed; rolled back).

Verifies the tables exist and the load-bearing constraints hold — including the
quote-immutability trigger, which is the system's most important data-integrity
rule (Part 2 §4.4).
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from app.models import (
    Itinerary,
    ItineraryDay,
    Organization,
    Project,
    Quote,
    TravellerSegment,
)
from app.models.enums import GstTreatment, Occupancy, PaxClass
from sqlalchemy import inspect, text
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.orm import Session


def _org(session: Session) -> uuid.UUID:
    org = Organization(name="Itin QA", slug=f"itin-{uuid.uuid4().hex[:8]}")
    session.add(org)
    session.flush()
    return org.id


def _project(session: Session, org_id: uuid.UUID) -> Project:
    p = Project(org_id=org_id, code=f"TP{uuid.uuid4().hex[:4]}", client_name="BE Mass SpA")
    session.add(p)
    session.flush()
    return p


def _itinerary(session: Session, org_id: uuid.UUID, project_id: uuid.UUID) -> Itinerary:
    it = Itinerary(
        org_id=org_id, project_id=project_id, title="Golden Triangle",
        start_date=date(2026, 7, 18), end_date=date(2026, 7, 21),
    )
    session.add(it)
    session.flush()
    return it


def _quote(session: Session, org_id: uuid.UUID, status: str = "draft", version: int = 1) -> Quote:
    project = _project(session, org_id)
    itinerary = _itinerary(session, org_id, project.id)
    q = Quote(
        org_id=org_id, project_id=project.id, itinerary_id=itinerary.id, version=version,
        status=status, gst_rate=Decimal("5.00"), gst_treatment=GstTreatment.CGST_SGST,
        rounding_policy="gross_nearest_100",
    )
    session.add(q)
    session.flush()
    return q


def test_all_phase3_tables_exist(db_session: Session) -> None:
    tables = set(inspect(db_session.get_bind()).get_table_names())
    expected = {
        "projects", "itineraries", "traveller_segments", "itinerary_days",
        "day_segment_presence", "itinerary_components", "quotes", "quote_lines",
        "markup_rules",
    }
    assert expected <= tables


def test_segment_pax_count_must_be_positive(db_session: Session) -> None:
    org_id = _org(db_session)
    project = _project(db_session, org_id)
    it = _itinerary(db_session, org_id, project.id)
    db_session.add(TravellerSegment(
        org_id=org_id, itinerary_id=it.id, label="Bad", pax_class=PaxClass.FOREIGN,
        occupancy=Occupancy.SINGLE, pax_count=0,
    ))
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.flush()


def test_itinerary_day_number_is_unique(db_session: Session) -> None:
    org_id = _org(db_session)
    project = _project(db_session, org_id)
    it = _itinerary(db_session, org_id, project.id)
    db_session.add(ItineraryDay(org_id=org_id, itinerary_id=it.id, day_number=1,
                                date=date(2026, 7, 18)))
    db_session.flush()
    db_session.add(ItineraryDay(org_id=org_id, itinerary_id=it.id, day_number=1,
                                date=date(2026, 7, 19)))
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.flush()


def test_quote_version_is_unique_per_project(db_session: Session) -> None:
    org_id = _org(db_session)
    q = _quote(db_session, org_id, version=1)
    dup = Quote(
        org_id=org_id, project_id=q.project_id, itinerary_id=q.itinerary_id, version=1,
        gst_rate=Decimal("5.00"), gst_treatment=GstTreatment.CGST_SGST,
        rounding_policy="nearest_1",
    )
    db_session.add(dup)
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.flush()


def test_issued_quote_is_immutable(db_session: Session) -> None:
    org_id = _org(db_session)
    q = _quote(db_session, org_id, status="issued")
    # Any edit to an issued quote must be refused by the trigger.
    q.total_cost = Decimal("100.00")
    with pytest.raises(DatabaseError), db_session.begin_nested():
        db_session.flush()


def test_issued_quote_may_be_superseded(db_session: Session) -> None:
    org_id = _org(db_session)
    q = _quote(db_session, org_id, status="issued")
    q.status = "superseded"  # the one permitted transition
    db_session.flush()
    reloaded = db_session.execute(
        text("SELECT status FROM quotes WHERE id = :id"), {"id": str(q.id)}
    ).scalar_one()
    assert reloaded == "superseded"
