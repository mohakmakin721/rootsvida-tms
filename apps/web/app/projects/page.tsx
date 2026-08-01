import Link from "next/link";

import { listProjects } from "@/lib/api";
import type { Project } from "@/lib/types";

export const dynamic = "force-dynamic";

const STATUS_TONE: Record<string, string> = {
  enquiry: "bg-neutral-100 text-neutral-600",
  quoted: "bg-blue-100 text-blue-700",
  confirmed: "bg-emerald-100 text-emerald-700",
  operating: "bg-amber-100 text-amber-700",
  closed: "bg-neutral-200 text-neutral-500",
  lost: "bg-red-100 text-red-600",
};

export default async function ProjectsPage() {
  let projects: Project[] = [];
  let error: string | null = null;
  try {
    projects = await listProjects();
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
          <h1 className="mt-1 text-2xl font-semibold">Projects &amp; quotes</h1>
          <p className="mt-1 text-sm text-neutral-600">
            Every enquiry and its quotes. Open a project to price an itinerary, issue a
            quote, or revise one.
          </p>
        </div>
        <Link
          href="/builder"
          className="rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800"
        >
          + New itinerary
        </Link>
      </header>

      {error ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-6 text-sm text-amber-800">
          <p className="font-medium">Could not load projects.</p>
          <p className="mt-1">{error}</p>
        </div>
      ) : projects.length === 0 ? (
        <p className="rounded-lg border border-dashed border-neutral-200 p-8 text-center text-sm text-neutral-400">
          No projects yet. Build an itinerary to create your first one.
        </p>
      ) : (
        <div className="overflow-hidden rounded-lg border border-neutral-200">
          <table className="w-full text-left text-sm">
            <thead className="bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
              <tr>
                <th className="px-4 py-2 font-medium">Code</th>
                <th className="px-4 py-2 font-medium">Client</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium text-right">Open</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {projects.map((p) => (
                <tr key={p.id} className="hover:bg-neutral-50">
                  <td className="px-4 py-3 font-medium text-neutral-900">{p.code}</td>
                  <td className="px-4 py-3 text-neutral-600">{p.client_name}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${
                        STATUS_TONE[p.status] ?? "bg-neutral-100 text-neutral-600"
                      }`}
                    >
                      {p.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link href={`/projects/${p.id}`} className="text-sm font-medium text-neutral-700 underline hover:text-neutral-900">
                      Open →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
