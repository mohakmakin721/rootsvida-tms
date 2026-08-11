import Link from "next/link";

import { getMe } from "@/lib/api";

import { UserBadge } from "./user-badge";

export const dynamic = "force-dynamic";

export default async function Home() {
  const me = await getMe();
  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <header className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 border-b border-neutral-200 pb-5">
        <div className="flex items-center gap-3">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/roots-logo.png" alt="RootsVida" className="h-10 w-10 object-contain" />
          <h1 className="whitespace-nowrap text-2xl font-semibold tracking-tight">RootsVida TMS</h1>
        </div>
        <nav className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
          <Link
            href="/activity"
            className="whitespace-nowrap text-neutral-500 underline-offset-2 hover:text-neutral-900 hover:underline"
          >
            Activity log
          </Link>
          {me?.permissions?.includes("users.manage") && (
            <Link
              href="/users"
              className="whitespace-nowrap text-neutral-500 underline-offset-2 hover:text-neutral-900 hover:underline"
            >
              Users &amp; roles
            </Link>
          )}
          {me && <UserBadge email={me.email} role={me.role} />}
        </nav>
      </header>
      <p className="mt-6 text-neutral-600">
        Internal travel-management workspace — projects, itineraries and the
        vendor book.
      </p>
      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        <div className="rounded-lg border border-neutral-200 p-5 transition hover:border-neutral-300 hover:shadow-sm">
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
        <div className="rounded-lg border border-neutral-200 p-5 transition hover:border-neutral-300 hover:shadow-sm">
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
        <div className="rounded-lg border border-neutral-200 p-5 transition hover:border-neutral-300 hover:shadow-sm">
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
        <div className="rounded-lg border border-neutral-200 p-5 transition hover:border-neutral-300 hover:shadow-sm">
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
