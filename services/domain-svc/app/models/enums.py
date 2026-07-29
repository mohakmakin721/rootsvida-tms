"""Domain enumerations, mirrored 1:1 to PostgreSQL ENUM types.

Defining these as Python `str, Enum` gives type-safe app code; the matching
PG ENUM types are created explicitly in migrations so the database enforces the
same closed vocabulary. Enum *names* here must equal the PG type names.
"""

from __future__ import annotations

from enum import Enum, StrEnum


class UserRole(StrEnum):
    """Access roles (Part 2 §8.1). Commission/margin visible to owner/ops_manager."""

    OWNER = "owner"
    OPS_MANAGER = "ops_manager"
    SALES = "sales"
    ACCOUNTS = "accounts"
    READONLY = "readonly"


class SupplierKind(StrEnum):
    """Kinds of supplier the canonical model can represent (Part 2 §4.1)."""

    HOTEL = "hotel"
    HOMESTAY = "homestay"
    TRANSPORT = "transport"
    GUIDE = "guide"
    ACTIVITY = "activity"
    FACILITATOR = "facilitator"
    PHOTOGRAPHER = "photographer"
    PERMIT = "permit"
    MISC = "misc"


class MealPlan(StrEnum):
    EP = "EP"
    CP = "CP"
    MAP = "MAP"
    AP = "AP"
    CPAI = "CPAI"
    MAPAI = "MAPAI"
    APAI = "APAI"
    CAPAI = "CAPAI"


class Occupancy(StrEnum):
    SINGLE = "single"
    DOUBLE = "double"
    TRIPLE = "triple"
    EXTRA_ADULT = "extra_adult"
    CHILD_WB = "child_wb"  # child with bed
    CHILD_NB = "child_nb"  # child no bed


class TaxBasis(StrEnum):
    """How a stored rate relates to tax (Part 1 §1.3 — do not collapse these)."""

    NET_OF_TAX = "net_of_tax"
    GROSS_OF_TAX = "gross_of_tax"
    PLUS_PERCENT = "plus_percent"


class TransportBasis(StrEnum):
    PER_DAY_8HR_80KM = "per_day_8hr_80km"
    PER_KM = "per_km"
    PER_TRANSFER = "per_transfer"
    PER_EXTRA_HOUR = "per_extra_hour"
    PER_DAY_12HR = "per_day_12hr"
    FIXED_ROUTE = "fixed_route"


class PaxClass(StrEnum):
    """Traveller class — a first-class concept (Part 1 §1.3, Part 2 §4.2)."""

    INDIAN = "indian"
    FOREIGN = "foreign"
    SAARC = "saarc"


class AllocationBasis(StrEnum):
    """How a shared cost is split across travellers (Part 2 §4.3)."""

    ALL_PAX = "all_pax"
    BY_PAX_CLASS = "by_pax_class"
    PER_SEGMENT = "per_segment"
    PER_PAX_DIRECT = "per_pax_direct"
    FIXED_GROUP = "fixed_group"


class RateLifecycle(StrEnum):
    """Rate trust state (Part 1 §46). NOT collapsed to active/inactive."""

    RAW = "raw"
    CANDIDATE = "candidate"
    REVIEWED = "reviewed"
    VERIFIED = "verified"
    STALE = "stale"
    EXPIRED = "expired"
    REJECTED = "rejected"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"


# Names used for the PostgreSQL ENUM types. Referenced by models and migrations
# so the Python enum and the DB type never drift.
PG_ENUM_NAMES: dict[type[Enum], str] = {
    UserRole: "user_role",
    SupplierKind: "supplier_kind",
    MealPlan: "meal_plan",
    Occupancy: "occupancy",
    TaxBasis: "tax_basis",
    TransportBasis: "transport_basis",
    PaxClass: "pax_class",
    AllocationBasis: "allocation_basis",
    RateLifecycle: "rate_lifecycle",
    ReviewStatus: "review_status",
}
