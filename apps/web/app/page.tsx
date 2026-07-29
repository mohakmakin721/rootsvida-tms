import Link from "next/link";

export default function Home() {
  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <h1 className="text-2xl font-semibold">RootsVida TMS</h1>
      <p className="mt-2 text-neutral-600">
        Internal data-curation foundation — Phase 1.
      </p>
      <div className="mt-8 rounded-lg border border-neutral-200 p-5">
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
    </main>
  );
}
