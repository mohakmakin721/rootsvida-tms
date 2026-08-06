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
  id: string;
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

export interface TransportRate {
  id: string;
  vehicle_class: string;
  vehicle_model: string | null;
  seats: number | null;
  basis: string;
  amount: string;
  includes_driver_da: boolean;
  includes_fuel: boolean;
  includes_tolls: boolean;
  valid_from: string;
  valid_to: string;
  freshness: Freshness;
}

export interface GuideRate {
  id: string;
  languages: string[];
  per_day: string | null;
  per_half_day: string | null;
  specialisation: string | null;
  valid_from: string;
  valid_to: string;
  freshness: Freshness;
}

export interface ActivityRate {
  id: string;
  name: string;
  pax_class: string;
  price_per_pax: string;
  child_price: string | null;
  valid_from: string;
  valid_to: string;
  freshness: Freshness;
}

export interface SupplierDetail extends SupplierSummary {
  gstin: string | null;
  pan: string | null;
  notes: string | null;
  contacts: SupplierContact[];
  room_types: RoomType[];
  rates: Rate[];
  transport_rates: TransportRate[];
  guide_rates: GuideRate[];
  activity_rates: ActivityRate[];
}

export interface DestinationFacet {
  id: string;
  name: string;
  state: string | null;
  supplier_count: number;
}

export interface Facets {
  destinations: DestinationFacet[];
  states: string[];
  categories: string[];
}

// --- Auth ---

export interface CurrentUser {
  id: string;
  email: string;
  name: string | null;
  role: string;
  is_active: boolean;
  permissions?: string[];
}

// --- Roles & permissions (D-0015) ---

export interface Permission {
  key: string;
  label: string;
  description: string;
  group: string;
}

export interface Role {
  id: string;
  key: string;
  label: string;
  description: string | null;
  is_system: boolean;
  permissions: string[];
  user_count: number;
}

// --- Clients & projects (Phase 3 M8) ---

export type ClientType = "individual" | "family" | "group" | "corporate";

export interface ClientSummary {
  id: string;
  name: string;
  client_type: ClientType;
  corporate_name: string | null;
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

export interface ActivityRow {
  id: string;
  project_id: string;
  project_code: string;
  client_name: string;
  project_status: string;
  kind: string;
  title: string;
  due_date: string | null;
  amount: string | null;
  done: boolean;
  notes: string | null;
}

export interface ClientDetail extends ClientSummary {
  projects: ProjectBrief[];
}

// --- Projects & quotes (Phase 3 M9) ---

export type ProjectStatus =
  | "enquiry"
  | "quoted"
  | "confirmed"
  | "operating"
  | "closed"
  | "lost";

export interface Project {
  id: string;
  code: string;
  client_id: string | null;
  client_name: string;
  client_country: string | null;
  status: string;
  status_changed_at: string | null;
  travel_start: string | null;
  travel_end: string | null;
  created_at: string;
}

export interface Milestone {
  id: string;
  project_id: string;
  kind: string;
  title: string;
  due_date: string | null;
  amount: string | null; // decimal string
  done: boolean;
  notes: string | null;
}

export interface ItineraryBrief {
  id: string;
  project_id: string;
  title: string;
  start_date: string;
  end_date: string;
  version: number;
  status: string;
  created_at: string;
}

// Full itinerary graph (for loading into the builder to edit) — mirrors ItineraryOut.
export interface ItinerarySegmentOut {
  id: string;
  label: string;
  pax_class: PaxClass;
  occupancy: Occupancy;
  pax_count: number;
  markup_rule_id: string | null;
}

export interface ItineraryComponentOut {
  id: string;
  kind: ComponentKind;
  description: string | null;
  override_amount: string | null;
  allocation: AllocationBasis;
  applies_to_segment_ids: string[] | null;
  applies_to_pax_class: PaxClass | null;
  supplier_id: string | null;
  rate_id: string | null;
  transport_rate_id: string | null;
  supplier_name: string | null;
  rate_amount: string | null;
  rate_meal_plan: string | null;
  rate_occupancy: string | null;
}

export interface ItineraryDayOut {
  id: string;
  day_number: number;
  date: string;
  destination_id: string | null;
  narrative: string | null;
  present_segment_ids: string[];
  components: ItineraryComponentOut[];
}

export interface ItineraryDetail {
  id: string;
  project_id: string;
  title: string;
  start_date: string;
  end_date: string;
  version: number;
  status: string;
  created_at: string | null;
  segments: ItinerarySegmentOut[];
  days: ItineraryDayOut[];
}

// Money fields arrive as decimal strings (FastAPI serializes Decimal as a string).
export interface QuoteLine {
  description: string;
  cost_per_pax: string | null;
  sell_per_pax: string | null;
  pax_count: number | null;
  line_total: string | null;
}

export interface Quote {
  id: string;
  project_id: string;
  itinerary_id: string;
  version: number;
  status: string;
  gst_rate: string;
  gst_treatment: string;
  fx_currency: string | null;
  fx_rate_inr_usd: string | null;
  rounding_policy: string;
  total_cost: string | null;
  total_taxable: string | null;
  total_tax: string | null;
  total_gross: string | null;
  margin_pct: string | null;
  engine_version: string | null;
  issued_at: string | null;
  valid_until: string | null;
  created_at: string;
  lines: QuoteLine[];
  pricing_snapshot: Record<string, unknown> | null;
}

// --- Invoices (Phase 4) — money fields are decimal strings ---

export interface InvoiceLine {
  description: string;
  hsn: string | null;
  quantity: string;
  taxable_value: string;
}

export interface Invoice {
  id: string;
  number: string;
  fiscal_year: string;
  serial: number;
  kind: string; // invoice | credit_note
  status: string; // issued | cancelled
  invoice_date: string;
  project_id: string;
  quote_id: string;
  project_code: string | null;
  credit_note_of_id: string | null;
  seller_name: string;
  buyer_name: string;
  buyer_country: string | null;
  place_of_supply: string | null;
  hsn: string | null;
  gst_rate: string;
  gst_treatment: string;
  taxable: string;
  cgst: string;
  sgst: string;
  igst: string;
  rounding_adjustment: string;
  total: string;
  notes: string | null;
  created_at: string;
  lines: InvoiceLine[];
}

// --- Itinerary builder + live pricing preview (Phase 3 M7) ---

export type PaxClass = "indian" | "foreign";
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
  // Supplier/rate linkage (M3): when a rate is picked, its amount drives pricing
  // and `override_amount` is left blank. rate_label/rate_amount are display-only.
  supplier_id: string | null;
  rate_id: string | null;
  rate_label: string | null;
  rate_amount: string | null;
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
