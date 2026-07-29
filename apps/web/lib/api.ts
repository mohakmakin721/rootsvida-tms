import type { ReviewItem, ReviewStatus } from "@/lib/types";

// Server-side base URL for the domain service. The browser talks to the API via
// the Next.js rewrite in next.config.mjs (relative /api/v1/*); server components
// fetch it directly here.
const SERVER_API_BASE =
  process.env.API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://localhost:8000/api/v1";

/** Fetch review-queue items by status (server-side, never cached). */
export async function listReviewItems(
  status: ReviewStatus = "pending",
): Promise<ReviewItem[]> {
  const res = await fetch(
    `${SERVER_API_BASE}/review-queue?status=${status}&limit=200`,
    { cache: "no-store" },
  );
  if (!res.ok) {
    throw new Error(`Domain service returned ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as ReviewItem[];
}
