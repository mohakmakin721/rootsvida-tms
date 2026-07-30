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


class ReviewEntityType(StrEnum):
    """What a review_queue item proposes (Part 2 §4.6). Nothing on the untrusted/
    extraction path writes to canonical directly — it lands here first."""

    RATE = "rate"
    SUPPLIER = "supplier"
    TRANSPORT_RATE = "transport_rate"
    MERGE_CANDIDATE = "merge_candidate"


class SourceKind(StrEnum):
    """Origin of a source document (Part 2 §4.6, plan §13)."""

    LEGACY_XLSX = "legacy_xlsx"
    VENDOR_EMAIL = "vendor_email"
    RATE_CARD_PDF = "rate_card_pdf"
    WHATSAPP_IMAGE = "whatsapp_image"


class ParserStrategy(StrEnum):
    """How a given sheet is ingested (plan §20)."""

    MECHANICAL = "mechanical"
    ASSISTED = "assisted"
    BESPOKE = "bespoke"
    MANUAL = "manual"


class RawParseStatus(StrEnum):
    """Classification of a staged raw row (plan §17, §32). Not the same as the
    canonical rate lifecycle — this is about how far ingestion got with the row."""

    PENDING = "pending"
    PARSED = "parsed"
    PARTIAL = "partial"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"
    ERROR = "error"


class ComponentKind(StrEnum):
    """What kind of thing an itinerary component is (Part 2 §4.3)."""

    STAY = "stay"
    TRANSPORT = "transport"
    ACTIVITY = "activity"
    GUIDE = "guide"
    MEAL = "meal"
    PERMIT = "permit"
    MISC = "misc"


class MarkupBasis(StrEnum):
    """Markup convention — mirrors pricing.model.MarkupBasis (Part 2 §5)."""

    MARKUP_ON_COST = "markup_on_cost"  # × (1 + m)
    MARGIN_ON_SELL = "margin_on_sell"  # ÷ (1 − m)


class PlaceOfSupply(StrEnum):
    """GST place-of-supply scenario, relative to the seller's state (Part 2 §1.4).
    Determines which tax_rules row applies to a booking."""

    INTRA_STATE = "intra_state"  # buyer in the seller's state → CGST + SGST
    INTER_STATE = "inter_state"  # buyer in another Indian state → IGST
    INTERNATIONAL = "international"  # buyer outside India


class GstTreatment(StrEnum):
    """How GST is levied on an invoice. Mirrors pricing.model.TaxTreatment values
    so a DB row maps 1:1 to the pure engine's tax split."""

    CGST_SGST = "cgst_sgst"
    IGST = "igst"
    EXPORT = "export"


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
    ReviewEntityType: "review_entity_type",
    SourceKind: "source_kind",
    ParserStrategy: "parser_strategy",
    RawParseStatus: "raw_parse_status",
    PlaceOfSupply: "place_of_supply",
    GstTreatment: "gst_treatment",
    ComponentKind: "component_kind",
    MarkupBasis: "markup_basis",
}
