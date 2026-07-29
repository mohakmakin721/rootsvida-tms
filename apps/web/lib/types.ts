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
