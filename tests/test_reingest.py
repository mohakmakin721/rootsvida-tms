"""Tests for Milestone 11 repeatable reingestion.

The pipeline is single-tenant (Phase 1): every step runs under the configured
org. The DB tests ensure that org exists, then drive the real pipeline against
the on-disk Rajasthan workbook and prove that a second run is a no-op (the
idempotency guarantee). Skipped if the source workbook is absent (git-ignored,
D-0006).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.config import get_settings
from app.models import Organization
from app.models.enums import ReviewEntityType
from sqlalchemy import select
from sqlalchemy.orm import Session

from ingestion.mappings import resolve_spec
from ingestion.reingest import (
    ReingestReport,
    SheetOutcome,
    reingest_all,
    render_reingest,
)

_RAJASTHAN_FILE = (
    Path(get_settings().source_data_dir) / (resolve_spec("Rajasthan").workbook or "")
)
_needs_workbook = pytest.mark.skipif(
    not _RAJASTHAN_FILE.exists(), reason="source workbook not present (git-ignored)"
)


def _ensure_org(session: Session) -> None:
    """Make sure the configured org exists so the pipeline can resolve it."""
    s = get_settings()
    org = session.scalar(select(Organization).where(Organization.slug == s.rv_org_slug))
    if org is None:
        session.add(Organization(name=s.rv_org_name, slug=s.rv_org_slug))
        session.flush()


def test_render_reports_skipped_sheet() -> None:
    report = ReingestReport(
        sheets=[SheetOutcome("Ghost", ok=False, workbook="X.xlsx", error="file not found: X")],
        merge_candidates=0,
        needs_review=0,
    )
    out = render_reingest(report)
    assert out.isascii()
    assert "Ghost: SKIPPED - file not found: X" in out


@_needs_workbook
def test_reingest_second_run_is_a_no_op(db_session: Session) -> None:
    _ensure_org(db_session)

    reingest_all(db_session)  # converge (may insert on a fresh org, or be a no-op)
    second = reingest_all(db_session)  # must change nothing

    raj = next(s for s in second.sheets if s.sheet == "Rajasthan")
    assert raj.ok
    assert raj.staged is not None and raj.migrated is not None
    assert (raj.staged.inserted, raj.staged.updated) == (0, 0)  # all unchanged
    assert raj.migrated.created == 0  # every supplier already existed
    assert second.merge_candidates == 0  # no new candidates enqueued
    assert second.needs_review == 0


@_needs_workbook
def test_reingest_populates_both_candidate_kinds(db_session: Session) -> None:
    _ensure_org(db_session)
    reingest_all(db_session)

    from app.services import review

    org_id = db_session.scalar(
        select(Organization.id).where(Organization.slug == get_settings().rv_org_slug)
    )
    assert org_id is not None
    merges = review.list_items(db_session, org_id, entity_type=ReviewEntityType.MERGE_CANDIDATE)
    suppliers = review.list_items(db_session, org_id, entity_type=ReviewEntityType.SUPPLIER)
    # Rajasthan has duplicate pairs and name-less rows, so both kinds appear.
    assert len(merges) >= 1
    assert len(suppliers) >= 1
