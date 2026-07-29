"""Migrate staged rows into canonical supplier candidates (Milestone 6).

The end-to-end step after staging: read `raw_import_rows` for a sheet, normalise
each mechanically (`ingestion.normalize`), and upsert canonical `suppliers` +
`supplier_contacts` + `destinations`. Idempotent via `raw_import_rows.
normalized_supplier_id` — a re-run updates the same supplier instead of
duplicating it. Each row's `parse_status` records the outcome:

  - PARSED       — mapped with a destination
  - PARTIAL      — mapped but missing a place/destination
  - NEEDS_REVIEW — no usable identity; deliberately NOT written to canonical

Nothing here creates a rate or asserts a price: these are unverified prospects,
exactly what the review/dedup milestones (M8+) then curate.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.models import (
    Destination,
    RawImportRow,
    SourceDocument,
    Supplier,
    SupplierContact,
)
from app.models.enums import RawParseStatus
from sqlalchemy import select
from sqlalchemy.orm import Session

from ingestion.normalize import NORMALIZERS, NormalizedContact, NormalizedSupplier


@dataclass(frozen=True)
class MigrateResult:
    created: int = 0
    updated: int = 0
    partial: int = 0
    needs_review: int = 0

    @property
    def total(self) -> int:
        return self.created + self.updated + self.needs_review


def get_or_create_destination(
    session: Session, org_id: uuid.UUID, name: str, state: str | None
) -> Destination:
    """Fetch-or-create a destination (reference data, keyed on org+name+state+country)."""
    existing = session.scalar(
        select(Destination).where(
            Destination.org_id == org_id,
            Destination.name == name,
            Destination.state == state,
            Destination.country == "IN",
        )
    )
    if existing is not None:
        return existing
    dest = Destination(org_id=org_id, name=name, state=state, country="IN")
    session.add(dest)
    session.flush()
    return dest


def _upsert_primary_contact(
    session: Session, supplier: Supplier, org_id: uuid.UUID, contact: NormalizedContact
) -> None:
    """Upsert the single primary contact carried by a supplier's source row."""
    existing = session.scalar(
        select(SupplierContact).where(
            SupplierContact.supplier_id == supplier.id,
            SupplierContact.is_primary.is_(True),
        )
    )
    target = existing or SupplierContact(
        org_id=org_id, supplier_id=supplier.id, is_primary=True
    )
    target.phone_raw = contact.phone_raw
    target.phone_e164 = contact.phone_e164
    target.email = contact.email
    target.website = contact.website
    target.unusable_reason = contact.unusable_reason
    if existing is None:
        session.add(target)


def _apply(
    session: Session,
    row: RawImportRow,
    org_id: uuid.UUID,
    norm: NormalizedSupplier,
) -> bool:
    """Create or update the supplier for `row`. Returns True if newly created."""
    destination = (
        get_or_create_destination(session, org_id, norm.destination_name, norm.destination_state)
        if norm.destination_name
        else None
    )

    supplier: Supplier | None = None
    if row.normalized_supplier_id is not None:
        supplier = session.get(Supplier, row.normalized_supplier_id)
    created = supplier is None
    if supplier is None:
        supplier = Supplier(org_id=org_id, legal_name=norm.display_name, display_name=norm.display_name)
        session.add(supplier)

    supplier.kind = norm.kind
    supplier.legal_name = norm.display_name
    supplier.display_name = norm.display_name
    supplier.destination_id = destination.id if destination else None
    supplier.category = norm.category
    supplier.property_type = norm.property_type
    supplier.tags = norm.tags
    supplier.status = norm.status
    supplier.notes = norm.notes
    session.flush()  # assign supplier.id before linking the row/contact

    row.normalized_supplier_id = supplier.id
    if norm.contact is not None:
        _upsert_primary_contact(session, supplier, org_id, norm.contact)
    return created


def migrate_sheet(
    session: Session, source_document: SourceDocument, sheet_name: str
) -> MigrateResult:
    """Normalise every staged row of `sheet_name` under `source_document`."""
    normalizer = NORMALIZERS.get(sheet_name)
    if normalizer is None:
        raise KeyError(f"no normaliser registered for sheet {sheet_name!r}")

    rows = session.scalars(
        select(RawImportRow)
        .where(
            RawImportRow.source_document_id == source_document.id,
            RawImportRow.sheet_name == sheet_name,
        )
        .order_by(RawImportRow.row_number)
    ).all()

    created = updated = partial = needs_review = 0
    for row in rows:
        norm = normalizer(row.raw_values)
        if norm is None:
            row.parse_status = RawParseStatus.NEEDS_REVIEW
            needs_review += 1
            continue
        was_created = _apply(session, row, source_document.org_id, norm)
        if norm.has_destination:
            row.parse_status = RawParseStatus.PARSED
        else:
            row.parse_status = RawParseStatus.PARTIAL
            partial += 1
        if was_created:
            created += 1
        else:
            updated += 1
    session.flush()
    return MigrateResult(
        created=created, updated=updated, partial=partial, needs_review=needs_review
    )
