import Link from "next/link";

import {
  getClient,
  getItinerary,
  getProject,
  getSupplierFacets,
  listMarkupRules,
} from "@/lib/api";
import type {
  ClientDetail,
  DestinationFacet,
  ItineraryDetail,
  MarkupRule,
  Project,
} from "@/lib/types";

import { type EditContext, ItineraryBuilder } from "./itinerary-builder";

export const dynamic = "force-dynamic";

export default async function BuildPage({
  searchParams,
}: {
  searchParams: Promise<{ itinerary?: string }>;
}) {
  const { itinerary: editId } = await searchParams;
  let markupRules: MarkupRule[] = [];
  let destinations: DestinationFacet[] = [];
  let edit: EditContext | null = null;
  let error: string | null = null;
  try {
    const [rules, facets] = await Promise.all([
      listMarkupRules(),
      getSupplierFacets(),
    ]);
    markupRules = rules;
    destinations = facets.destinations;

    if (editId) {
      const itinerary: ItineraryDetail = await getItinerary(editId);
      const project: Project = await getProject(itinerary.project_id);
      let client: ClientDetail | null = null;
      if (project.client_id) {
        client = await getClient(project.client_id).catch(() => null);
      }
      edit = { itinerary, project, client };
    }
  } catch (e) {
    error = e instanceof Error ? e.message : "Unknown error";
  }

  return (
    <main className="mx-auto max-w-7xl px-6 py-10">
      <header className="mb-6">
        <Link href="/" className="text-sm text-neutral-500 hover:text-neutral-800">
          ← RootsVida TMS
        </Link>
        <h1 className="mt-1 text-2xl font-semibold">
          {edit ? "Edit itinerary" : "Itinerary builder"}
        </h1>
        <p className="mt-1 text-sm text-neutral-600">
          {edit
            ? `Editing “${edit.itinerary.title}” — change any input and save to update it in place.`
            : "Enter the client & trip, define traveller groups, then add the day-by-day services. The sidebar prices live — every number comes from the deterministic engine, never a guess."}
        </p>
      </header>

      {error ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-6 text-sm text-amber-800">
          <p className="font-medium">Could not load builder data.</p>
          <p className="mt-1">{error}</p>
          <p className="mt-2 text-amber-700">
            Is the domain service running on <code>:8000</code>? Start it with{" "}
            <code>make api</code>.
          </p>
        </div>
      ) : (
        <ItineraryBuilder
          initialMarkupRules={markupRules}
          destinations={destinations}
          edit={edit}
        />
      )}
    </main>
  );
}
