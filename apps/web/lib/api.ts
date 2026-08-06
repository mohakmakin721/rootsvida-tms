import { cookies } from "next/headers";

import type {
  ActivityRow,
  ClientDetail,
  CurrentUser,
  Facets,
  Invoice,
  ItineraryBrief,
  ItineraryDetail,
  MarkupRule,
  Milestone,
  Permission,
  Project,
  Quote,
  ReviewItem,
  ReviewStatus,
  Role,
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

/** All users in the org (needs users.manage — throws 403 otherwise). */
export function listUsers(): Promise<CurrentUser[]> {
  return getJSON<CurrentUser[]>("/auth/users");
}

/** The org's roles with their permissions + user counts (needs users.manage). */
export function listRoles(): Promise<Role[]> {
  return getJSON<Role[]>("/roles");
}

/** The fixed permission catalog — the toggles the roles UI offers. */
export function listPermissions(): Promise<Permission[]> {
  return getJSON<Permission[]>("/roles/permissions");
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

/** Org-wide milestone/activity log (date-ordered) for the activity screen. */
export function listActivity(): Promise<ActivityRow[]> {
  return getJSON<ActivityRow[]>("/projects/activity-log");
}

export function getProject(id: string): Promise<Project> {
  return getJSON<Project>(`/projects/${id}`);
}

/** Full itinerary graph (for loading into the builder to edit). */
export function getItinerary(id: string): Promise<ItineraryDetail> {
  return getJSON<ItineraryDetail>(`/itineraries/${id}`);
}

/** One client with its projects (to prefill the builder intake when editing). */
export function getClient(id: string): Promise<ClientDetail> {
  return getJSON<ClientDetail>(`/clients/${id}`);
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
