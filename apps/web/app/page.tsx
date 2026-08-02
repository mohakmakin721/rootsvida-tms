import Link from "next/link";

import { getMe } from "@/lib/api";

import { UserBadge } from "./user-badge";

export const dynamic = "force-dynamic";

export default async function Home() {
  const me = await getMe();
  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <div className="flex items-start justify-between gap-4">
        <h1 className="text-2xl font-semibold">RootsVida TMS</h1>
        <div className="flex items-center gap-3">
          {me?.permissions?.includes("users.manage") && (
            <Link href="/users" className="text-sm text-neutral-500 underline hover:text-neutral-800">
              Users &amp; roles
            </Link>
          )}
          {me && <UserBadge email={me.email} role={me.role} />}
        </div>
      </div>
      <p className="mt-2 text-neutral-600">
        Internal travel-management workspace — projects, itineraries and the
        vendor book.
      </p>
      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        <div className="rounded-lg border border-neutral-200 p-5">
          <h2 className="font-medium">Itinerary builder</h2>
          <p className="mt-1 text-sm text-neutral-500">
            Compose a trip day by day — traveller groups, presence and costs — with
            a live cost sidebar that reprices as you go.
          </p>
          <Link
            href="/builder"
            className="mt-4 inline-block rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800"
          >
            Open builder →
          </Link>
        </div>
        <div className="rounded-lg border border-neutral-200 p-5">
          <h2 className="font-medium">Projects &amp; quotes</h2>
          <p className="mt-1 text-sm text-neutral-500">
            Every enquiry and its quotes. Price an itinerary, issue a quote, or
            revise one into a new version.
          </p>
          <Link
            href="/projects"
            className="mt-4 inline-block rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800"
          >
            Open projects →
          </Link>
        </div>
        <div className="rounded-lg border border-neutral-200 p-5">
          <h2 className="font-medium">Vendor &amp; rate browser</h2>
          <p className="mt-1 text-sm text-neutral-500">
            Search the vendor book, filter by destination and category, and open
            any vendor to see contacts, room types and rate freshness.
          </p>
          <Link
            href="/suppliers"
            className="mt-4 inline-block rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800"
          >
            Browse vendors →
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
