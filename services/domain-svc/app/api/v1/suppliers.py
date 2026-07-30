"""Supplier & rate browser endpoints (Phase 3 M6).

Read-only search/filter over the canonical supplier book plus a full per-supplier
profile (contacts, room types, rates with freshness badges). Powers the browser UI.

Commercial data (commission/margin) is deliberately absent — the service layer
never touches `supplier_commercials` (D-0002). These reads carry only non-sensitive
supplier data, so they stay open like the other browse endpoints; `require_role(...)`
lands on the sensitive surfaces (commercial data, issuing quotes) as the UI grows.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import current_org_id
from app.db import get_session
from app.services import suppliers

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


class SupplierSummary(BaseModel):
    id: uuid.UUID
    kind: str
    display_name: str
    legal_name: str
    destination_id: uuid.UUID | None
    destination_name: str | None
    category: str | None
    property_type: str | None
    status: str
    tags: list[str]
    rate_count: int
    freshness: str


class SupplierPage(BaseModel):
    items: list[SupplierSummary]
    total: int
    limit: int
    offset: int


class Contact(BaseModel):
    person_name: str | None
    role: str | None
    phone_e164: str | None
    phone_raw: str | None
    email: str | None
    website: str | None
    preferred_channel: str | None
    is_primary: bool
    unusable_reason: str | None


class RoomTypeOut(BaseModel):
    id: uuid.UUID
    name: str
    max_adults: int
    max_children: int
    extra_bed_allowed: bool


class RateOut(BaseModel):
    id: uuid.UUID
    room_type_id: uuid.UUID | None
    meal_plan: str
    occupancy: str
    amount: str
    currency: str
    tax_basis: str
    tax_pct: str | None
    valid_from: str
    valid_to: str
    season_label: str | None
    min_nights: int
    freshness: str


class SupplierDetail(SupplierSummary):
    gstin: str | None
    pan: str | None
    notes: str | None
    contacts: list[Contact]
    room_types: list[RoomTypeOut]
    rates: list[RateOut]


class DestinationFacet(BaseModel):
    id: uuid.UUID
    name: str
    supplier_count: int


class Facets(BaseModel):
    destinations: list[DestinationFacet]
    categories: list[str]


@router.get("", response_model=SupplierPage)
def list_suppliers(
    q: str | None = Query(default=None, description="Search display/legal name"),
    destination_id: uuid.UUID | None = None,
    category: str | None = None,
    kind: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> SupplierPage:
    items, total = suppliers.search(
        session, org_id, today=date.today(), q=q, destination_id=destination_id,
        category=category, kind=kind, status=status_filter, limit=limit, offset=offset,
    )
    return SupplierPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/facets", response_model=Facets)
def supplier_facets(
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> Facets:
    return Facets(**suppliers.facets(session, org_id))


@router.get("/{supplier_id}", response_model=SupplierDetail)
def get_supplier(
    supplier_id: uuid.UUID,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> SupplierDetail:
    detail = suppliers.get_detail(session, org_id, supplier_id, today=date.today())
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="supplier not found")
    return SupplierDetail(**detail)
