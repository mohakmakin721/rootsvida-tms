import Link from "next/link";

export default function Home() {
  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <h1 className="text-2xl font-semibold">RootsVida TMS</h1>
      <p className="mt-2 text-neutral-600">
        Internal travel-management workspace — projects, itineraries and the
        supplier book.
      </p>
      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        <div className="rounded-lg border border-neutral-200 p-5">
          <h2 className="font-medium">Supplier &amp; rate browser</h2>
          <p className="mt-1 text-sm text-neutral-500">
            Search the supplier book, filter by destination and category, and open
            any supplier to see contacts, room types and rate freshness.
          </p>
          <Link
            href="/suppliers"
            className="mt-4 inline-block rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800"
          >
            Browse suppliers →
          </Link>
        </div>
        <div className="rounded-lg border border-neutral-200 p-5">
          <h2 className="font-medium">Review queue</h2>
          <p className="mt-1 text-sm text-neutral-500">
            Work through candidate records awaiting a human decision — approve,
            edit, or reject, with the source shown alongside.
          </p>
          <Link
            href="/review"
            className="mt-4 inline-block rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800"
          >
            Open review queue →
          </Link>
        </div>
      </div>
    </main>
  );
}
