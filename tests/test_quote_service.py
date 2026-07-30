"""Phase 3 M3 — quote issuance + frozen snapshot."""

from __future__ import annotations

from decimal import Decimal

import pytest
from app.models import Quote
from app.services.quote import (
    create_quote,
    issue_quote,
    revise_issued_quote,
)
from pricing import model as pm
from pricing.engine import MarginBelowFloor
from sqlalchemy.orm import Session

from tests.test_pricing_bridge import _seed_jaipur


def _draft(session: Session, **over: object) -> Quote:
    itinerary_id = _seed_jaipur(session)
    kw: dict[str, object] = {
        "buyer_state_code": "05", "buyer_country": "IN",
        "rounding": pm.RoundingPolicy.NEAREST_1, "fx_inr_per_usd": Decimal(95),
    }
    kw.update(over)
    return create_quote(session, itinerary_id, **kw)  # type: ignore[arg-type]


def test_create_quote_captures_totals_and_lines(db_session: Session) -> None:
    q = _draft(db_session)
    assert q.status == "draft"
    assert q.version == 1
    assert q.total_gross == Decimal("403327.00")
    assert q.total_cost == Decimal("336050.00")
    assert q.gst_rate == Decimal("5.00")
    assert q.gst_treatment.value == "cgst_sgst"
    assert q.margin_pct == Decimal("12.52")
    assert q.engine_version.startswith("pricing@")

    sells = {line.description: line.sell_per_pax for line in q.lines}
    assert sells["Foreign Single"] == Decimal(65597)
    assert sells["Foreign Double"] == Decimal(47303)
    assert sells["Indian Double"] == Decimal(26956)


def test_snapshot_is_frozen_and_reproducible(db_session: Session) -> None:
    q = _draft(db_session)
    snap = q.pricing_snapshot
    assert snap is not None
    assert snap["engine_version"] == q.engine_version
    # inputs (every rate/pax/rule) and output are both frozen as strings
    assert snap["output"]["group_total"] == "403327"
    assert len(snap["inputs"]["segments"]) == 3
    assert Decimal(snap["inputs"]["tax_rule"]["rate"]) == Decimal("0.05")
    assert any(st["room_rate"] for st in snap["inputs"]["stays"])


def test_version_increments_per_project(db_session: Session) -> None:
    itinerary_id = _seed_jaipur(db_session)
    v1 = create_quote(db_session, itinerary_id, buyer_state_code="05")
    v2 = create_quote(db_session, itinerary_id, buyer_state_code="05")
    assert (v1.version, v2.version) == (1, 2)


def test_issue_freezes_and_blocks_further_edits(db_session: Session) -> None:
    from sqlalchemy.exc import DatabaseError

    q = _draft(db_session)
    issue_quote(db_session, q, valid_until=None)
    assert q.status == "issued"
    assert q.issued_at is not None
    assert q.fx_rate_locked_at is not None  # FX locked (fx was provided)

    # The trigger now refuses any edit to the issued quote.
    q.total_cost = Decimal("1.00")
    with pytest.raises(DatabaseError), db_session.begin_nested():
        db_session.flush()


def test_only_a_draft_can_be_issued(db_session: Session) -> None:
    q = _draft(db_session)
    issue_quote(db_session, q)
    with pytest.raises(ValueError, match="only a draft"):
        issue_quote(db_session, q)


def test_revise_supersedes_and_creates_next_version(db_session: Session) -> None:
    q1 = _draft(db_session)
    issue_quote(db_session, q1)
    q2 = revise_issued_quote(db_session, q1, buyer_state_code="05", buyer_country="IN",
                             fx_inr_per_usd=Decimal(95))
    assert q1.status == "superseded"
    assert q2.status == "draft"
    assert q2.version == 2
    assert q2.project_id == q1.project_id


def test_margin_floor_blocks_quote_creation(db_session: Session) -> None:
    # Jaipur's blended margin is ~12.5%; a 20% floor must block.
    with pytest.raises(MarginBelowFloor):
        _draft(db_session, margin_floor=Decimal("0.20"))
