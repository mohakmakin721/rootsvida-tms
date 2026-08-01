import { cookies } from "next/headers";

import type {
  CurrentUser,
  Facets,
  Invoice,
  ItineraryBrief,
  MarkupRule,
  Milestone,
  Project,
  Quote,
  ReviewItem,
  ReviewStatus,
  SupplierPage,
} from "@/lib/types";

// Server-side base URL for the domain service. The browser talks to the API via
// the Next.js rewrite in next.config.mjs (relative /api/v1/*, with middleware
// injecting the Bearer header); server components fetch it directly here and must
// forward the caller's token from the httpOnly cookie themselves.
const SERVER_API_BASE =
  process.env.API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://localhost:8000/api/v1";

async function getJSON<T>(path: string): Promise<T> {
  const token = (await cookies()).get("rv_token")?.value;
  const res = await fetch(`${SERVER_API_BASE}${path}`, {
    cache: "no-store",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    throw new Error(`Domain service returned ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

/** The signed-in user, or null if the token is missing/expired. */
export async function getMe(): Promise<CurrentUser | null> {
  try {
    return await getJSON<CurrentUser>("/auth/me");
  } catch {
    return null;
  }
}

/** All users in the org (owner-only — throws 403 otherwise). */
export function listUsers(): Promise<CurrentUser[]> {
  return getJSON<CurrentUser[]>("/auth/users");
}

/** Fetch review-queue items by status (server-side, never cached). */
export function listReviewItems(status: ReviewStatus = "pending"): Promise<ReviewItem[]> {
  return getJSON<ReviewItem[]>(`/review-queue?status=${status}&limit=200`);
}

/** First page of suppliers for the browser's initial server render. */
export function listSuppliers(limit = 50): Promise<SupplierPage> {
  return getJSON<SupplierPage>(`/suppliers?limit=${limit}`);
}

/** Filter options (destinations + categories) for the browser's controls. */
export function getSupplierFacets(): Promise<Facets> {
  return getJSON<Facets>("/suppliers/facets");
}

/** The org's markup rules — the builder assigns one per traveller segment. */
export function listMarkupRules(): Promise<MarkupRule[]> {
  return getJSON<MarkupRule[]>("/markup-rules");
}

/** All projects, newest first (the projects & quotes index). */
export function listProjects(): Promise<Project[]> {
  return getJSON<Project[]>("/projects");
}

export function getProject(id: string): Promise<Project> {
  return getJSON<Project>(`/projects/${id}`);
}

export function listProjectItineraries(id: string): Promise<ItineraryBrief[]> {
  return getJSON<ItineraryBrief[]>(`/projects/${id}/itineraries`);
}

export function listProjectQuotes(id: string): Promise<Quote[]> {
  return getJSON<Quote[]>(`/projects/${id}/quotes`);
}

export function listProjectMilestones(id: string): Promise<Milestone[]> {
  return getJSON<Milestone[]>(`/projects/${id}/milestones`);
}

export function listProjectInvoices(id: string): Promise<Invoice[]> {
  return getJSON<Invoice[]>(`/projects/${id}/invoices`);
}
