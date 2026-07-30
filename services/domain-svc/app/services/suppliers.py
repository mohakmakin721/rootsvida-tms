"""Supplier & rate browsing — read-only queries for the browser UI (Phase 3 M6).

Search/filter suppliers and fetch one supplier's full public profile (contacts,
room types, rates) with a freshness badge per rate and a supplier-level rollup.

**D-0002 boundary:** this service NEVER reads `supplier_commercials`. Every field
returned is assembled explicitly below, so commission/margin cannot leak into a
browser view no matter how the callers evolve. Sensitive commercial data has its
own gated surface; the browser is not it.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models import Destination, Rate, RoomType, Supplier, SupplierContact
from app.services import freshness
from app.services.freshness import Freshness


def _base_query(org_id: uuid.UUID) -> Select[Any]:
    return (
        select(Supplier, Destination.name)
        .outerjoin(Destination, Supplier.destination_id == Destination.id)
        .where(Supplier.org_id == org_id, Supplier.deleted_at.is_(None))
    )


def _apply_filters(
    stmt: Select[Any],
    *,
    q: str | None,
    destination_id: uuid.UUID | None,
    category: str | None,
    kind: str | None,
    status: str | None,
) -> Select[Any]:
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(Supplier.display_name.ilike(like), Supplier.legal_name.ilike(like))
        )
    if destination_id is not None:
        stmt = stmt.where(Supplier.destination_id == destination_id)
    if category:
        stmt = stmt.where(Supplier.category == category)
    if kind:
        stmt = stmt.where(Supplier.kind == kind)
    if status:
        stmt = stmt.where(Supplier.status == status)
    return stmt


def _freshness_by_supplier(
    session: Session, supplier_ids: list[uuid.UUID], today: date
) -> dict[uuid.UUID, tuple[int, Freshness]]:
    """(rate_count, rolled-up freshness) for each supplier, in one query."""
    out: dict[uuid.UUID, tuple[int, Freshness]] = {
        sid: (0, Freshness.NONE) for sid in supplier_ids
    }
    if not supplier_ids:
        return out
    rows = session.execute(
        select(Rate.supplier_id, Rate.valid_from, Rate.valid_to).where(
            Rate.supplier_id.in_(supplier_ids), Rate.deleted_at.is_(None)
        )
    )
    bands: dict[uuid.UUID, list[Freshness]] = {}
    for supplier_id, valid_from, valid_to in rows:
        bands.setdefault(supplier_id, []).append(
            freshness.classify(valid_from, valid_to, today)
        )
    for supplier_id, band_list in bands.items():
        out[supplier_id] = (len(band_list), freshness.rollup(band_list))
    return out


def search(
    session: Session,
    org_id: uuid.UUID,
    *,
    today: date,
    q: str | None = None,
    destination_id: uuid.UUID | None = None,
    category: str | None = None,
    kind: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Return (page of supplier summaries, total matching count)."""
    filtered = _apply_filters(
        _base_query(org_id),
        q=q, destination_id=destination_id, category=category, kind=kind, status=status,
    )
    total = session.scalar(
        select(func.count()).select_from(filtered.order_by(None).subquery())
    ) or 0

    rows = session.execute(
        filtered.order_by(Supplier.display_name).limit(limit).offset(offset)
    ).all()
    suppliers = [s for s, _ in rows]
    fresh = _freshness_by_supplier(session, [s.id for s in suppliers], today)

    summaries: list[dict[str, Any]] = []
    for supplier, dest_name in rows:
        rate_count, band = fresh[supplier.id]
        summaries.append(
            {
                "id": supplier.id,
                "kind": supplier.kind.value,
                "display_name": supplier.display_name,
                "legal_name": supplier.legal_name,
                "destination_id": supplier.destination_id,
                "destination_name": dest_name,
                "category": supplier.category,
                "property_type": supplier.property_type,
                "status": supplier.status,
                "tags": list(supplier.tags),
                "rate_count": rate_count,
                "freshness": band.value,
            }
        )
    return summaries, total


def _contact_dict(c: SupplierContact) -> dict[str, Any]:
    return {
        "person_name": c.person_name,
        "role": c.role,
        "phone_e164": c.phone_e164,
        "phone_raw": c.phone_raw,
        "email": c.email,
        "website": c.website,
        "preferred_channel": c.preferred_channel,
        "is_primary": c.is_primary,
        "unusable_reason": c.unusable_reason,
    }


def _rate_dict(r: Rate, today: date) -> dict[str, Any]:
    return {
        "id": r.id,
        "room_type_id": r.room_type_id,
        "meal_plan": r.meal_plan.value,
        "occupancy": r.occupancy.value,
        "amount": str(r.amount),
        "currency": r.currency,
        "tax_basis": r.tax_basis.value,
        "tax_pct": None if r.tax_pct is None else str(r.tax_pct),
        "valid_from": r.valid_from.isoformat(),
        "valid_to": r.valid_to.isoformat(),
        "season_label": r.season_label,
        "min_nights": r.min_nights,
        "freshness": freshness.classify(r.valid_from, r.valid_to, today).value,
    }


def get_detail(
    session: Session, org_id: uuid.UUID, supplier_id: uuid.UUID, *, today: date
) -> dict[str, Any] | None:
    """One supplier's full public profile, or None if not found in this org."""
    row = session.execute(
        _base_query(org_id).where(Supplier.id == supplier_id)
    ).first()
    if row is None:
        return None
    supplier, dest_name = row

    contacts = session.scalars(
        select(SupplierContact)
        .where(SupplierContact.supplier_id == supplier_id)
        .order_by(SupplierContact.is_primary.desc())
    ).all()
    room_types = session.scalars(
        select(RoomType).where(RoomType.supplier_id == supplier_id).order_by(RoomType.name)
    ).all()
    rates = session.scalars(
        select(Rate)
        .where(Rate.supplier_id == supplier_id, Rate.deleted_at.is_(None))
        .order_by(Rate.valid_from.desc())
    ).all()

    return {
        "id": supplier.id,
        "kind": supplier.kind.value,
        "display_name": supplier.display_name,
        "legal_name": supplier.legal_name,
        "destination_id": supplier.destination_id,
        "destination_name": dest_name,
        "gstin": supplier.gstin,
        "pan": supplier.pan,
        "category": supplier.category,
        "property_type": supplier.property_type,
        "status": supplier.status,
        "tags": list(supplier.tags),
        "notes": supplier.notes,
        "rate_count": len(rates),
        "freshness": freshness.rollup(
            freshness.classify(r.valid_from, r.valid_to, today) for r in rates
        ).value,
        "contacts": [_contact_dict(c) for c in contacts],
        "room_types": [
            {
                "id": rt.id,
                "name": rt.name,
                "max_adults": rt.max_adults,
                "max_children": rt.max_children,
                "extra_bed_allowed": rt.extra_bed_allowed,
            }
            for rt in room_types
        ],
        "rates": [_rate_dict(r, today) for r in rates],
    }


def facets(session: Session, org_id: uuid.UUID) -> dict[str, Any]:
    """Filter options for the browser: destinations (with counts) and categories."""
    dest_rows = session.execute(
        select(Destination.id, Destination.name, func.count(Supplier.id))
        .join(Supplier, Supplier.destination_id == Destination.id)
        .where(
            Supplier.org_id == org_id,
            Supplier.deleted_at.is_(None),
            Destination.org_id == org_id,
        )
        .group_by(Destination.id, Destination.name)
        .order_by(func.count(Supplier.id).desc(), Destination.name)
    ).all()
    categories = session.scalars(
        select(Supplier.category)
        .where(
            Supplier.org_id == org_id,
            Supplier.deleted_at.is_(None),
            Supplier.category.is_not(None),
        )
        .distinct()
        .order_by(Supplier.category)
    ).all()
    return {
        "destinations": [
            {"id": did, "name": name, "supplier_count": count}
            for did, name, count in dest_rows
        ],
        "categories": list(categories),
    }
