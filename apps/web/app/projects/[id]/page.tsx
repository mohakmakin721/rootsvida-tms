import Link from "next/link";

import {
  getProject,
  listProjectInvoices,
  listProjectItineraries,
  listProjectMilestones,
  listProjectQuotes,
} from "@/lib/api";
import type { Invoice, ItineraryBrief, Milestone, Project, Quote } from "@/lib/types";

import { ProjectWorkspace } from "./project-workspace";

export const dynamic = "force-dynamic";

export default async function ProjectPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let project: Project | null = null;
  let itineraries: ItineraryBrief[] = [];
  let quotes: Quote[] = [];
  let milestones: Milestone[] = [];
  let invoices: Invoice[] = [];
  let error: string | null = null;
  try {
    [project, itineraries, quotes, milestones, invoices] = await Promise.all([
      getProject(id),
      listProjectItineraries(id),
      listProjectQuotes(id),
      listProjectMilestones(id),
      listProjectInvoices(id),
    ]);
  } catch (e) {
    error = e instanceof Error ? e.message : "Unknown error";
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <Link href="/projects" className="text-sm text-neutral-500 hover:text-neutral-800">
        ← Projects
      </Link>
      {error || !project ? (
        <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-6 text-sm text-amber-800">
          <p className="font-medium">Could not load this project.</p>
          <p className="mt-1">{error ?? "Not found."}</p>
        </div>
      ) : (
        <ProjectWorkspace
          project={project}
          initialItineraries={itineraries}
          initialQuotes={quotes}
          initialMilestones={milestones}
          initialInvoices={invoices}
        />
      )}
    </main>
  );
}
