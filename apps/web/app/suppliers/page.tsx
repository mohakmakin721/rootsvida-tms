import Link from "next/link";

import { getMe, getSupplierFacets, listSuppliers } from "@/lib/api";
import type { Facets, SupplierPage } from "@/lib/types";

import { SupplierBrowser } from "./supplier-browser";

// The book changes as ingestion and review run — always fetch fresh.
export const dynamic = "force-dynamic";

export default async function SuppliersPage() {
  let page: SupplierPage | null = null;
  let facets: Facets = { destinations: [], states: [], categories: [] };
  let error: string | null = null;
  const me = await getMe();
  const canEdit = me?.permissions?.includes("suppliers.manage") ?? false;
  try {
    [page, facets] = await Promise.all([listSuppliers(50), getSupplierFacets()]);
  } catch (e) {
    error = e instanceof Error ? e.message : "Unknown error";
  }

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <header className="mb-6">
        <Link href="/" className="text-sm text-neutral-500 hover:text-neutral-800">
          ← RootsVida TMS
        </Link>
        <h1 className="mt-1 text-2xl font-semibold">Supplier &amp; rate browser</h1>
        <p className="mt-1 text-sm text-neutral-600">
          Search the supplier book and open any supplier to see its contacts, room
          types and rates. The badge shows rate freshness at a glance — commission
          and margin are never shown here.
          {canEdit && " You can add, edit and remove suppliers and rates here."}
        </p>
      </header>

      {error ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-6 text-sm text-amber-800">
          <p className="font-medium">Could not load suppliers.</p>
          <p className="mt-1">{error}</p>
          <p className="mt-2 text-amber-700">
            Is the domain service running on <code>:8000</code>? Start it with{" "}
            <code>make api</code>.
          </p>
        </div>
      ) : (
        <SupplierBrowser initialPage={page!} facets={facets} canEdit={canEdit} />
      )}
    </main>
  );
}
