import Link from "next/link";

import { getSupplierFacets, listMarkupRules } from "@/lib/api";
import type { DestinationFacet, MarkupRule } from "@/lib/types";

import { ItineraryBuilder } from "./itinerary-builder";

export const dynamic = "force-dynamic";

export default async function BuildPage() {
  let markupRules: MarkupRule[] = [];
  let destinations: DestinationFacet[] = [];
  let error: string | null = null;
  try {
    const [rules, facets] = await Promise.all([
      listMarkupRules(),
      getSupplierFacets(),
    ]);
    markupRules = rules;
    destinations = facets.destinations;
  } catch (e) {
    error = e instanceof Error ? e.message : "Unknown error";
  }

  return (
    <main className="mx-auto max-w-7xl px-6 py-10">
      <header className="mb-6">
        <Link href="/" className="text-sm text-neutral-500 hover:text-neutral-800">
          ← RootsVida TMS
        </Link>
        <h1 className="mt-1 text-2xl font-semibold">Itinerary builder</h1>
        <p className="mt-1 text-sm text-neutral-600">
          Define traveller groups, lay out the days, and add costs. The sidebar
          reprices live — every number comes from the deterministic engine, never a
          guess.
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
        />
      )}
    </main>
  );
}
