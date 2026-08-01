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

// --- Clients & projects (Phase 3 M8) ---

export type ClientType = "individual" | "family" | "group" | "corporate";

export interface ClientSummary {
  id: string;
  name: string;
  client_type: ClientType;
  country: string | null;
  email: string | null;
  phone: string | null;
  referral: string | null;
  notes: string | null;
  project_count: number;
}

export interface ProjectBrief {
  id: string;
  code: string;
  status: string;
  created_at: string;
}

export interface ClientDetail extends ClientSummary {
  projects: ProjectBrief[];
}

// --- Itinerary builder + live pricing preview (Phase 3 M7) ---

export type PaxClass = "indian" | "foreign" | "saarc";
export type Occupancy =
  | "single"
  | "double"
  | "triple"
  | "extra_adult"
  | "child_wb"
  | "child_nb";
export type MarkupBasis = "markup_on_cost" | "margin_on_sell";
export type AllocationBasis =
  | "all_pax"
  | "by_pax_class"
  | "per_segment"
  | "per_pax_direct"
  | "fixed_group";
export type ComponentKind =
  | "stay"
  | "transport"
  | "activity"
  | "guide"
  | "meal"
  | "permit"
  | "misc";

export interface MarkupRule {
  id: string;
  label: string;
  basis: MarkupBasis;
  rate: string;
  is_default: boolean;
}

export interface SegmentDraft {
  key: string;
  label: string;
  pax_class: PaxClass;
  occupancy: Occupancy;
  pax_count: number;
  markup_rule_id: string;
}

export interface ComponentDraft {
  kind: ComponentKind;
  description: string;
  override_amount: string;
  override_reason: string;
  allocation: AllocationBasis;
  applies_to_segment_keys: string[] | null;
  applies_to_pax_class: PaxClass | null;
}

export interface DayDraft {
  day_number: number;
  date: string;
  destination_id: string | null;
  present_segment_keys: string[];
  components: ComponentDraft[];
}

export interface SegmentPreview {
  label: string;
  pax: number;
  base_cost: string;
  sell_per_pax: string;
  group_total: string;
}

export interface PreviewOut {
  engine_version: string;
  segments: SegmentPreview[];
  total_cost: string;
  group_total: string;
  profit: string;
  revenue_ex_tax: string;
  margin_pct: string;
  gst_rate: string;
  gst_treatment: string;
  fx: Record<string, string> | null;
  margin_floor: string | null;
  below_floor: boolean;
}
