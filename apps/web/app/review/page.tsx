import Link from "next/link";

import { listReviewItems } from "@/lib/api";
import type { ReviewItem } from "@/lib/types";

import { ReviewList } from "./review-list";

// Always fetch fresh — the queue changes as reviewers act.
export const dynamic = "force-dynamic";

export default async function ReviewPage() {
  let items: ReviewItem[] = [];
  let error: string | null = null;
  try {
    items = await listReviewItems("pending");
  } catch (e) {
    error = e instanceof Error ? e.message : "Unknown error";
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <header className="mb-6 flex items-baseline justify-between">
        <div>
          <Link href="/" className="text-sm text-neutral-500 hover:text-neutral-800">
            ← RootsVida TMS
          </Link>
          <h1 className="mt-1 text-2xl font-semibold">Review queue</h1>
          <p className="mt-1 text-sm text-neutral-600">
            Candidate records awaiting a human decision. Nothing here is trusted
            until you approve it.
          </p>
        </div>
        {!error && (
          <span className="rounded-full bg-neutral-100 px-3 py-1 text-sm font-medium text-neutral-700">
            {items.length} pending
          </span>
        )}
      </header>

      {error ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-6 text-sm text-amber-800">
          <p className="font-medium">Could not load the review queue.</p>
          <p className="mt-1">{error}</p>
          <p className="mt-2 text-amber-700">
            Is the domain service running on <code>:8000</code>? Start it with{" "}
            <code>make api</code>.
          </p>
        </div>
      ) : (
        <ReviewList initialItems={items} />
      )}
    </main>
  );
}
