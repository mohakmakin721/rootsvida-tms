import Link from "next/link";

import { listActivity } from "@/lib/api";
import type { ActivityRow } from "@/lib/types";

import { ActivityLog } from "./activity-log";

export const dynamic = "force-dynamic";

export default async function ActivityPage() {
  let rows: ActivityRow[] = [];
  let error: string | null = null;
  try {
    rows = await listActivity();
  } catch (e) {
    error = e instanceof Error ? e.message : "Unknown error";
  }

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <header className="mb-6">
        <Link href="/" className="text-sm text-neutral-500 hover:text-neutral-800">
          ← RootsVida TMS
        </Link>
        <h1 className="mt-1 text-2xl font-semibold">Activity log</h1>
        <p className="mt-1 text-sm text-neutral-600">
          A date-ordered log of every payment, invoice, deadline and note across all
          projects. Search by project code or client, and filter by type, status, or
          done/pending.
        </p>
      </header>

      {error ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-6 text-sm text-amber-800">
          <p className="font-medium">Could not load the activity log.</p>
          <p className="mt-1">{error}</p>
        </div>
      ) : (
        <ActivityLog initial={rows} />
      )}
    </main>
  );
}
