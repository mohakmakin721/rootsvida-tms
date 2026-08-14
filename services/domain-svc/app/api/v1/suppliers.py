"""Supplier & rate browser endpoints (Phase 3 M6; CRUD added later).

Read (search/filter + per-supplier detail) is open to any signed-in user. Managing
suppliers, rates, room types and contacts is gated to owner/ops_manager — it's
operational/cost data. Commercial commission/margin is never touched here (D-0002).
Direct edits here are the manual-management path; the review queue remains the
gated ingestion path for extracted data (D-0010).
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import current_org_id, require_permission
from app.db import get_session
from app.models import (
    ActivityRate,
    GuideRate,
    Rate,
    RoomType,
    Supplier,
    SupplierContact,
    TransportRate,
)
from app.models.enums import (
    MealPlan,
    Occupancy,
    PaxClass,
    SupplierKind,
    TaxBasis,
    TransportBasis,
)
from app.security.permissions import SUPPLIERS_MANAGE
from app.services import bulk_import, suppliers

router = APIRouter(prefix="/suppliers", tags=["suppliers"])

# Managing the supplier book is operational data — gated on suppliers.manage.
_manage = require_permission(SUPPLIERS_MANAGE)


# --------------------------------------------------------------------------- #
# read schemas
# --------------------------------------------------------------------------- #


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
    id: uuid.UUID
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


class TransportRateOut(BaseModel):
    id: uuid.UUID
    vehicle_class: str
    vehicle_model: str | None
    seats: int | None
    basis: str
    amount: str
    includes_driver_da: bool
    includes_fuel: bool
    includes_tolls: bool
    valid_from: str
    valid_to: str
    freshness: str


class GuideRateOut(BaseModel):
    id: uuid.UUID
    languages: list[str]
    per_day: str | None
    per_half_day: str | None
    specialisation: str | None
    valid_from: str
    valid_to: str
    freshness: str


class ActivityRateOut(BaseModel):
    id: uuid.UUID
    name: str
    pax_class: str
    price_per_pax: str
    child_price: str | None
    valid_from: str
    valid_to: str
    freshness: str


class SupplierDetail(SupplierSummary):
    gstin: str | None
    pan: str | None
    notes: str | None
    contacts: list[Contact]
    room_types: list[RoomTypeOut]
    rates: list[RateOut]
    transport_rates: list[TransportRateOut] = []
    guide_rates: list[GuideRateOut] = []
    activity_rates: list[ActivityRateOut] = []


class DestinationFacet(BaseModel):
    id: uuid.UUID
    name: str
    state: str | None
    supplier_count: int


class Facets(BaseModel):
    destinations: list[DestinationFacet]
    states: list[str]
    categories: list[str]


# --------------------------------------------------------------------------- #
# write schemas
# --------------------------------------------------------------------------- #


class SupplierIn(BaseModel):
    kind: SupplierKind
    legal_name: str
    display_name: str
    destination_id: uuid.UUID | None = None
    category: str | None = None
    property_type: str | None = None
    status: str = "prospect"
    gstin: str | None = None
    pan: str | None = None
    tags: list[str] = []
    notes: str | None = None


class SupplierUpdate(BaseModel):
    kind: SupplierKind | None = None
    legal_name: str | None = None
    display_name: str | None = None
    destination_id: uuid.UUID | None = None
    category: str | None = None
    property_type: str | None = None
    status: str | None = None
    gstin: str | None = None
    pan: str | None = None
    tags: list[str] | None = None
    notes: str | None = None


class RateIn(BaseModel):
    room_type_id: uuid.UUID | None = None
    # Meal plan applies to stay + meal vendors; occupancy to stay only. Both default
    # so transport/guide/activity/permit/misc rates can send just an amount + dates.
    meal_plan: MealPlan = MealPlan.EP
    occupancy: Occupancy = Occupancy.SINGLE
    amount: Decimal
    currency: str = "INR"
    tax_basis: TaxBasis = TaxBasis.GROSS_OF_TAX
    tax_pct: Decimal | None = None
    valid_from: date
    valid_to: date
    season_label: str | None = None
    min_nights: int = 1


class RateUpdate(BaseModel):
    room_type_id: uuid.UUID | None = None
    meal_plan: MealPlan | None = None
    occupancy: Occupancy | None = None
    amount: Decimal | None = None
    currency: str | None = None
    tax_basis: TaxBasis | None = None
    tax_pct: Decimal | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    season_label: str | None = None
    min_nights: int | None = None


class RoomTypeIn(BaseModel):
    name: str
    max_adults: int = 2
    max_children: int = 1
    extra_bed_allowed: bool = True


class ContactIn(BaseModel):
    person_name: str | None = None
    role: str | None = None
    phone_e164: str | None = None
    phone_raw: str | None = None
    email: str | None = None
    website: str | None = None
    preferred_channel: str | None = None
    is_primary: bool = False


class TransportRateIn(BaseModel):
    vehicle_class: str
    vehicle_model: str | None = None
    seats: int | None = None
    basis: TransportBasis = TransportBasis.PER_DAY_8HR_80KM
    amount: Decimal
    includes_driver_da: bool = False
    includes_fuel: bool = True
    includes_tolls: bool = False
    valid_from: date
    valid_to: date


class GuideRateIn(BaseModel):
    languages: list[str] = []
    per_day: Decimal | None = None
    per_half_day: Decimal | None = None
    specialisation: str | None = None
    valid_from: date
    valid_to: date


class ActivityRateIn(BaseModel):
    name: str
    pax_class: PaxClass = PaxClass.FOREIGN
    price_per_pax: Decimal
    child_price: Decimal | None = None
    valid_from: date
    valid_to: date


# --------------------------------------------------------------------------- #
# read endpoints
# --------------------------------------------------------------------------- #


@router.get("", response_model=SupplierPage)
def list_suppliers(
    q: str | None = Query(default=None, description="Search display/legal name"),
    destination_id: uuid.UUID | None = None,
    state: str | None = None,
    category: str | None = None,
    kind: str | None = Query(
        default=None, description="One kind, or several comma-separated (e.g. hotel,homestay)"
    ),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
) -> SupplierPage:
    kinds = [k.strip() for k in kind.split(",") if k.strip()] if kind else None
    items, total = suppliers.search(
        session, org_id, today=date.today(), q=q, destination_id=destination_id,
        state=state, category=category, kinds=kinds, status=status_filter,
        limit=limit, offset=offset,
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


# --------------------------------------------------------------------------- #
# write endpoints (owner / ops_manager)
# --------------------------------------------------------------------------- #


def _require_supplier(session: Session, org_id: uuid.UUID, supplier_id: uuid.UUID) -> Supplier:
    s = session.scalar(
        select(Supplier).where(
            Supplier.id == supplier_id, Supplier.org_id == org_id,
            Supplier.deleted_at.is_(None),
        )
    )
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="supplier not found")
    return s


def _detail(session: Session, org_id: uuid.UUID, supplier_id: uuid.UUID) -> SupplierDetail:
    d = suppliers.get_detail(session, org_id, supplier_id, today=date.today())
    assert d is not None
    return SupplierDetail(**d)


@router.post("", response_model=SupplierDetail, status_code=status.HTTP_201_CREATED)
def create_supplier(
    body: SupplierIn,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    _user: object = Depends(_manage),
) -> SupplierDetail:
    supplier = Supplier(org_id=org_id, **body.model_dump())
    session.add(supplier)
    session.flush()
    return _detail(session, org_id, supplier.id)


_XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/import/template")
def import_template(_user: object = Depends(_manage)) -> Response:
    """Download the blank Vendors + Rates .xlsx template to bulk-import into the book."""
    filename = "rootsvida_vendor_import_template.xlsx"
    return Response(
        content=bulk_import.build_template(),
        media_type=_XLSX_MEDIA,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import")
async def import_vendors(
    file: UploadFile = File(...),
    commit: bool = Query(
        default=False, description="false = validate/dry-run; true = write"
    ),
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    _user: object = Depends(_manage),
) -> dict[str, object]:
    """Bulk-import vendors + rates from the filled template. Call with commit=false
    first to preview (validate everything, persist nothing), then commit=true to
    write. Imported vendors are 'prospect' + rates 'on_file' — reviewed later."""
    data = await file.read()
    return bulk_import.run_import(session, org_id, data, commit=commit).as_dict()


@router.patch("/{supplier_id}", response_model=SupplierDetail)
def update_supplier(
    supplier_id: uuid.UUID,
    body: SupplierUpdate,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    _user: object = Depends(_manage),
) -> SupplierDetail:
    supplier = _require_supplier(session, org_id, supplier_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(supplier, field, value)
    session.flush()
    return _detail(session, org_id, supplier_id)


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_supplier(
    supplier_id: uuid.UUID,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    _user: object = Depends(_manage),
) -> None:
    supplier = _require_supplier(session, org_id, supplier_id)
    supplier.deleted_at = datetime.now(UTC)
    session.flush()


@router.post("/{supplier_id}/rates", response_model=RateOut, status_code=status.HTTP_201_CREATED)
def create_rate(
    supplier_id: uuid.UUID,
    body: RateIn,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    _user: object = Depends(_manage),
) -> RateOut:
    _require_supplier(session, org_id, supplier_id)
    rate = Rate(org_id=org_id, supplier_id=supplier_id, **body.model_dump())
    session.add(rate)
    try:
        session.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="a rate for this room/plan/occupancy overlaps these dates",
        ) from exc
    return RateOut(**suppliers._rate_dict(rate, date.today()))


@router.patch("/rates/{rate_id}", response_model=RateOut)
def update_rate(
    rate_id: uuid.UUID,
    body: RateUpdate,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    _user: object = Depends(_manage),
) -> RateOut:
    rate = session.scalar(
        select(Rate).where(Rate.id == rate_id, Rate.org_id == org_id, Rate.deleted_at.is_(None))
    )
    if rate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="rate not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(rate, field, value)
    try:
        session.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="a rate for this room/plan/occupancy overlaps these dates",
        ) from exc
    return RateOut(**suppliers._rate_dict(rate, date.today()))


@router.delete("/rates/{rate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rate(
    rate_id: uuid.UUID,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    _user: object = Depends(_manage),
) -> None:
    rate = session.scalar(select(Rate).where(Rate.id == rate_id, Rate.org_id == org_id))
    if rate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="rate not found")
    rate.deleted_at = datetime.now(UTC)
    session.flush()


@router.post("/{supplier_id}/room-types", response_model=RoomTypeOut,
             status_code=status.HTTP_201_CREATED)
def create_room_type(
    supplier_id: uuid.UUID,
    body: RoomTypeIn,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    _user: object = Depends(_manage),
) -> RoomType:
    _require_supplier(session, org_id, supplier_id)
    rt = RoomType(org_id=org_id, supplier_id=supplier_id, **body.model_dump())
    session.add(rt)
    session.flush()
    return rt


@router.delete("/room-types/{room_type_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_room_type(
    room_type_id: uuid.UUID,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    _user: object = Depends(_manage),
) -> None:
    rt = session.scalar(
        select(RoomType).where(RoomType.id == room_type_id, RoomType.org_id == org_id)
    )
    if rt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="room type not found")
    session.delete(rt)
    try:
        session.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="this room type is used by a rate; delete the rate first",
        ) from exc


@router.post("/{supplier_id}/contacts", response_model=Contact,
             status_code=status.HTTP_201_CREATED)
def create_contact(
    supplier_id: uuid.UUID,
    body: ContactIn,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    _user: object = Depends(_manage),
) -> Contact:
    _require_supplier(session, org_id, supplier_id)
    contact = SupplierContact(org_id=org_id, supplier_id=supplier_id, **body.model_dump())
    session.add(contact)
    session.flush()
    return Contact(**suppliers._contact_dict(contact))


@router.delete("/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(
    contact_id: uuid.UUID,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    _user: object = Depends(_manage),
) -> None:
    contact = session.scalar(
        select(SupplierContact).where(
            SupplierContact.id == contact_id, SupplierContact.org_id == org_id
        )
    )
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="contact not found")
    session.delete(contact)
    session.flush()


# --------------------------------------------------------------------------- #
# type-specific rates (transport / guide / activity) — vendor-kind aware CRUD
# --------------------------------------------------------------------------- #


@router.post("/{supplier_id}/transport-rates", response_model=TransportRateOut,
             status_code=status.HTTP_201_CREATED)
def create_transport_rate(
    supplier_id: uuid.UUID,
    body: TransportRateIn,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    _user: object = Depends(_manage),
) -> TransportRateOut:
    _require_supplier(session, org_id, supplier_id)
    rate = TransportRate(org_id=org_id, supplier_id=supplier_id, **body.model_dump())
    session.add(rate)
    session.flush()
    return TransportRateOut(**suppliers._transport_rate_dict(rate, date.today()))


@router.delete("/transport-rates/{rate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transport_rate(
    rate_id: uuid.UUID,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    _user: object = Depends(_manage),
) -> None:
    rate = session.scalar(
        select(TransportRate).where(TransportRate.id == rate_id, TransportRate.org_id == org_id)
    )
    if rate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="rate not found")
    rate.deleted_at = datetime.now(UTC)
    session.flush()


@router.post("/{supplier_id}/guide-rates", response_model=GuideRateOut,
             status_code=status.HTTP_201_CREATED)
def create_guide_rate(
    supplier_id: uuid.UUID,
    body: GuideRateIn,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    _user: object = Depends(_manage),
) -> GuideRateOut:
    _require_supplier(session, org_id, supplier_id)
    rate = GuideRate(org_id=org_id, supplier_id=supplier_id, **body.model_dump())
    session.add(rate)
    session.flush()
    return GuideRateOut(**suppliers._guide_rate_dict(rate, date.today()))


@router.delete("/guide-rates/{rate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_guide_rate(
    rate_id: uuid.UUID,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    _user: object = Depends(_manage),
) -> None:
    rate = session.scalar(
        select(GuideRate).where(GuideRate.id == rate_id, GuideRate.org_id == org_id)
    )
    if rate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="rate not found")
    rate.deleted_at = datetime.now(UTC)
    session.flush()


@router.post("/{supplier_id}/activity-rates", response_model=ActivityRateOut,
             status_code=status.HTTP_201_CREATED)
def create_activity_rate(
    supplier_id: uuid.UUID,
    body: ActivityRateIn,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    _user: object = Depends(_manage),
) -> ActivityRateOut:
    _require_supplier(session, org_id, supplier_id)
    rate = ActivityRate(org_id=org_id, supplier_id=supplier_id, **body.model_dump())
    session.add(rate)
    session.flush()
    return ActivityRateOut(**suppliers._activity_rate_dict(rate, date.today()))


@router.delete("/activity-rates/{rate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_activity_rate(
    rate_id: uuid.UUID,
    session: Session = Depends(get_session),
    org_id: uuid.UUID = Depends(current_org_id),
    _user: object = Depends(_manage),
) -> None:
    rate = session.scalar(
        select(ActivityRate).where(ActivityRate.id == rate_id, ActivityRate.org_id == org_id)
    )
    if rate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="rate not found")
    rate.deleted_at = datetime.now(UTC)
    session.flush()
