// Types mirroring the domain service's ReviewItemOut (app/api/v1/review.py).
// Kept in sync by hand for Phase 1; a generated client can replace this later.

export type ReviewStatus = "pending" | "approved" | "rejected" | "edited";

export type ReviewEntityType =
  | "rate"
  | "supplier"
  | "transport_rate"
  | "merge_candidate";

export interface ReviewItem {
  id: string;
  entity_type: ReviewEntityType;
  status: ReviewStatus;
  proposed: Record<string, unknown>;
  existing: Record<string, unknown> | null;
  source_document_id: string | null;
  confidence: number | null;
  dedupe_key: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  reviewer_notes: string | null;
  created_at: string;
}

export type DecisionAction = "approve" | "reject" | "edit";

// --- Supplier & rate browser (Phase 3 M6), mirrors app/api/v1/suppliers.py ---

export type Freshness = "fresh" | "expiring" | "expired" | "none";

export interface SupplierSummary {
  id: string;
  kind: string;
  display_name: string;
  legal_name: string;
  destination_id: string | null;
  destination_name: string | null;
  category: string | null;
  property_type: string | null;
  status: string;
  tags: string[];
  rate_count: number;
  freshness: Freshness;
}

export interface SupplierPage {
  items: SupplierSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface SupplierContact {
  person_name: string | null;
  role: string | null;
  phone_e164: string | null;
  phone_raw: string | null;
  email: string | null;
  website: string | null;
  preferred_channel: string | null;
  is_primary: boolean;
  unusable_reason: string | null;
}

export interface RoomType {
  id: string;
  name: string;
  max_adults: number;
  max_children: number;
  extra_bed_allowed: boolean;
}

export interface Rate {
  id: string;
  room_type_id: string | null;
  meal_plan: string;
  occupancy: string;
  amount: string;
  currency: string;
  tax_basis: string;
  tax_pct: string | null;
  valid_from: string;
  valid_to: string;
  season_label: string | null;
  min_nights: number;
  freshness: Freshness;
}

export interface SupplierDetail extends SupplierSummary {
  gstin: string | null;
  pan: string | null;
  notes: string | null;
  contacts: SupplierContact[];
  room_types: RoomType[];
  rates: Rate[];
}

export interface DestinationFacet {
  id: string;
  name: string;
  supplier_count: number;
}

export interface Facets {
  destinations: DestinationFacet[];
  categories: string[];
}
