"""Data-quality validation + reporting (Milestone 7).

Turns the ingestion outcome into an actionable, human-readable summary: how far
each staged row got (parse_status), what the canonical migration produced, and a
set of validation checks that flag records a human should look at — rows that
need review, suppliers with no destination or no usable contact, phone numbers
that couldn't be normalised, and possible duplicates.

This is a *report*, never a gate: it blocks nothing and changes no data. It is
the input to the review queue (M8) and the dedup pass (M10). Everything is
org-scoped and read-only.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.models import (
    Organization,
    RawImportRow,
    SourceDocument,
    Supplier,
    SupplierContact,
)
from app.models.enums import RawParseStatus
from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session

_SAMPLE = 5  # how many example records to show per check


@dataclass(frozen=True)
class Check:
    """One validation rule's outcome."""

    key: str
    severity: str  # "warn" | "info"
    count: int
    description: str
    sample: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class QualityReport:
    org_slug: str
    generated_at: datetime
    staging: dict[str, int]
    canonical: dict[str, int]
    checks: list[Check]

    @property
    def flagged(self) -> list[Check]:
        return [c for c in self.checks if c.count]

    @property
    def warnings(self) -> int:
        return sum(1 for c in self.flagged if c.severity == "warn")

    @property
    def infos(self) -> int:
        return sum(1 for c in self.flagged if c.severity == "info")


def _count(session: Session, model: type, *where: ColumnElement[bool]) -> int:
    return session.scalar(select(func.count()).select_from(model).where(*where)) or 0


def _alive(org_id: uuid.UUID) -> tuple[ColumnElement[bool], ...]:
    """Common filter: this org's non-soft-deleted suppliers."""
    return (Supplier.org_id == org_id, Supplier.deleted_at.is_(None))


def _staging_stats(session: Session, org_id: uuid.UUID) -> dict[str, int]:
    stats: dict[str, int] = {
        "source_documents": _count(session, SourceDocument, SourceDocument.org_id == org_id),
        "raw_rows": _count(session, RawImportRow, RawImportRow.org_id == org_id),
    }
    by_status = session.execute(
        select(RawImportRow.parse_status, func.count())
        .where(RawImportRow.org_id == org_id)
        .group_by(RawImportRow.parse_status)
    ).all()
    for status, n in by_status:
        stats[status.value] = n
    parsed = stats.get(RawParseStatus.PARSED.value, 0)
    total = stats["raw_rows"]
    stats["parsed_pct"] = round(parsed / total * 100) if total else 0
    return stats


def _canonical_stats(session: Session, org_id: uuid.UUID) -> dict[str, int]:
    from app.models import Destination

    return {
        "suppliers": _count(session, Supplier, *_alive(org_id)),
        "destinations": _count(session, Destination, Destination.org_id == org_id),
        "contacts": _count(session, SupplierContact, SupplierContact.org_id == org_id),
    }


def _supplier_samples(session: Session, *where: ColumnElement[bool]) -> list[str]:
    names = session.scalars(
        select(Supplier.display_name).where(*where).order_by(Supplier.display_name).limit(_SAMPLE)
    ).all()
    return list(names)


def _reachable(org_id: uuid.UUID) -> ColumnElement[bool]:
    """A supplier is reachable if it has any contact with a phone/email/website."""
    return (
        select(SupplierContact.id)
        .where(
            SupplierContact.supplier_id == Supplier.id,
            or_(
                SupplierContact.phone_e164.is_not(None),
                SupplierContact.email.is_not(None),
                SupplierContact.website.is_not(None),
            ),
        )
        .exists()
    )


def _checks(session: Session, org_id: uuid.UUID) -> list[Check]:
    checks: list[Check] = []

    # Rows the migration deliberately did not write to canonical.
    for status, sev, desc in (
        (RawParseStatus.NEEDS_REVIEW, "warn", "staged rows with no usable identity"),
        (RawParseStatus.PARTIAL, "warn", "rows mapped but missing a destination"),
        (RawParseStatus.ERROR, "warn", "rows that errored during parsing"),
    ):
        rows = session.scalars(
            select(RawImportRow)
            .where(RawImportRow.org_id == org_id, RawImportRow.parse_status == status)
            .order_by(RawImportRow.sheet_name, RawImportRow.row_number)
            .limit(_SAMPLE)
        ).all()
        checks.append(
            Check(
                key=f"rows_{status.value}",
                severity=sev,
                count=_count(
                    session, RawImportRow,
                    RawImportRow.org_id == org_id, RawImportRow.parse_status == status,
                ),
                description=desc,
                sample=[f"{r.sheet_name} row {r.row_number}" for r in rows],
            )
        )

    # Suppliers with no destination resolved.
    no_dest = (*_alive(org_id), Supplier.destination_id.is_(None))
    checks.append(
        Check(
            "supplier_without_destination", "warn",
            _count(session, Supplier, *no_dest),
            "suppliers with no destination",
            _supplier_samples(session, *no_dest),
        )
    )

    # Suppliers with no usable way to contact them.
    unreachable = (*_alive(org_id), ~_reachable(org_id))
    checks.append(
        Check(
            "supplier_unreachable", "warn",
            _count(session, Supplier, *unreachable),
            "suppliers with no phone, email or website",
            _supplier_samples(session, *unreachable),
        )
    )

    # Contacts kept but not usable as-is (phone couldn't be normalised, or a
    # "no reply / via website" remark) — human follow-up, not a blocker.
    unnormalised = (
        SupplierContact.org_id == org_id,
        SupplierContact.phone_raw.is_not(None),
        SupplierContact.phone_e164.is_(None),
    )
    checks.append(
        Check(
            "phone_unnormalised", "info",
            _count(session, SupplierContact, *unnormalised),
            "contacts whose phone couldn't be parsed to E.164",
        )
    )
    checks.append(
        Check(
            "contact_unusable", "info",
            _count(
                session, SupplierContact,
                SupplierContact.org_id == org_id,
                SupplierContact.unusable_reason.is_not(None),
            ),
            "contacts flagged unusable (e.g. 'no reply')",
        )
    )

    # Possible duplicates: same normalised name within the same destination.
    # Full fuzzy dedup is M10; this is the cheap exact-ish signal.
    name = func.lower(func.trim(Supplier.display_name))
    dup_groups = session.execute(
        select(name, func.count())
        .where(*_alive(org_id))
        .group_by(name, Supplier.destination_id)
        .having(func.count() > 1)
        .order_by(func.count().desc())
        .limit(_SAMPLE)
    ).all()
    dup_total = len(
        session.execute(
            select(name)
            .where(*_alive(org_id))
            .group_by(name, Supplier.destination_id)
            .having(func.count() > 1)
        ).all()
    )
    checks.append(
        Check(
            "duplicate_name_in_destination", "warn",
            dup_total,
            "name+destination groups with more than one supplier",
            [f"{nm} (x{n})" for nm, n in dup_groups],
        )
    )
    return checks


def build_report(session: Session, org_id: uuid.UUID) -> QualityReport:
    """Assemble the data-quality report for one org (read-only)."""
    slug = session.scalar(select(Organization.slug).where(Organization.id == org_id)) or "?"
    return QualityReport(
        org_slug=slug,
        generated_at=datetime.now(UTC),
        staging=_staging_stats(session, org_id),
        canonical=_canonical_stats(session, org_id),
        checks=_checks(session, org_id),
    )


def render_report(report: QualityReport) -> str:
    """Format a report as plain text for the CLI."""
    s, c = report.staging, report.canonical
    timestamp = report.generated_at.strftime("%Y-%m-%d %H:%M:%S")
    raw_rows = (
        f"  raw rows         : {s.get('raw_rows', 0)} "
        f"(parsed {s.get('parsed', 0)}/{s.get('parsed_pct', 0)}%, "
        f"partial {s.get('partial', 0)}, needs_review {s.get('needs_review', 0)}, "
        f"pending {s.get('pending', 0)})"
    )
    lines = [
        f"Data-quality report | {report.org_slug} | {timestamp} UTC",
        "",
        "Staging",
        f"  source documents : {s.get('source_documents', 0)}",
        raw_rows,
        "",
        "Canonical",
        f"  suppliers    : {c.get('suppliers', 0)}",
        f"  destinations : {c.get('destinations', 0)}",
        f"  contacts     : {c.get('contacts', 0)}",
        "",
        "Checks",
    ]
    if not report.flagged:
        lines.append("  (all clear - no records flagged)")
    for chk in report.flagged:
        tag = f"[{chk.severity}]".ljust(7)
        lines.append(f"  {tag} {chk.description}: {chk.count}")
        if chk.sample:
            lines.append(f"          e.g. {', '.join(chk.sample)}")
    lines += ["", f"{report.warnings} warning(s), {report.infos} info - nothing blocks."]
    return "\n".join(lines)
