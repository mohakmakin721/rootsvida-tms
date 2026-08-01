"use client";

import { useState } from "react";

import { inr } from "@/lib/constants";
import type { Milestone, Project } from "@/lib/types";

import { btnDark, btnLight, Field, inputCls } from "@/app/builder/ui";

const STAGES: { key: string; label: string }[] = [
  { key: "enquiry", label: "Enquiry" },
  { key: "quoted", label: "Quoted" },
  { key: "confirmed", label: "Confirmed" },
  { key: "operating", label: "Operating" },
  { key: "closed", label: "Closed" },
];

const KIND_BADGE: Record<string, string> = {
  payment: "bg-emerald-100 text-emerald-700",
  invoice: "bg-blue-100 text-blue-700",
  deadline: "bg-amber-100 text-amber-700",
  note: "bg-neutral-100 text-neutral-500",
  other: "bg-neutral-100 text-neutral-500",
};

const TODAY = new Date().toISOString().slice(0, 10);

function dueTone(m: Milestone): string {
  if (m.done || !m.due_date) return "";
  if (m.due_date < TODAY) return "text-red-600 font-medium";
  const soon = new Date(TODAY);
  soon.setDate(soon.getDate() + 7);
  if (m.due_date <= soon.toISOString().slice(0, 10)) return "text-amber-600";
  return "";
}

export function ProjectTimeline({
  project: initialProject,
  initialMilestones,
}: {
  project: Project;
  initialMilestones: Milestone[];
}) {
  const [project, setProject] = useState<Project>(initialProject);
  const [milestones, setMilestones] = useState<Milestone[]>(initialMilestones);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState({ kind: "payment", title: "", due_date: "", amount: "" });

  async function patchProject(patch: Record<string, unknown>) {
    setError(null);
    const res = await fetch(`/api/v1/projects/${project.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    if (res.ok) setProject((await res.json()) as Project);
    else setError("Could not update the project.");
  }

  async function addMilestone() {
    if (!draft.title.trim()) return;
    setError(null);
    const res = await fetch(`/api/v1/projects/${project.id}/milestones`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kind: draft.kind,
        title: draft.title.trim(),
        due_date: draft.due_date || null,
        amount: draft.amount ? draft.amount : null,
      }),
    });
    if (res.ok) {
      await refreshMilestones();
      setDraft({ kind: "payment", title: "", due_date: "", amount: "" });
    } else {
      setError("Could not add the milestone.");
    }
  }

  async function refreshMilestones() {
    const res = await fetch(`/api/v1/projects/${project.id}/milestones`, { cache: "no-store" });
    if (res.ok) setMilestones((await res.json()) as Milestone[]);
  }

  async function toggleDone(m: Milestone) {
    const res = await fetch(`/api/v1/projects/milestones/${m.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ done: !m.done }),
    });
    if (res.ok) setMilestones((prev) => prev.map((x) => (x.id === m.id ? { ...x, done: !x.done } : x)));
  }

  async function removeMilestone(id: string) {
    const res = await fetch(`/api/v1/projects/milestones/${id}`, { method: "DELETE" });
    if (res.ok) setMilestones((prev) => prev.filter((x) => x.id !== id));
  }

  const currentIndex = STAGES.findIndex((s) => s.key === project.status);
  const isLost = project.status === "lost";

  return (
    <section className="mb-8 rounded-lg border border-neutral-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-neutral-800">Timeline</h2>
        {project.status_changed_at && (
          <span className="text-xs text-neutral-400">
            status set {new Date(project.status_changed_at).toLocaleDateString()}
          </span>
        )}
      </div>

      {error && <p className="mb-3 text-xs text-red-600">{error}</p>}

      {/* status stepper */}
      <div className="mb-5 flex flex-wrap items-center gap-1.5">
        {STAGES.map((s, i) => {
          const done = !isLost && i < currentIndex;
          const current = !isLost && i === currentIndex;
          return (
            <button
              key={s.key}
              onClick={() => patchProject({ status: s.key })}
              className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                current
                  ? "bg-neutral-900 text-white"
                  : done
                    ? "bg-emerald-100 text-emerald-700"
                    : "bg-neutral-100 text-neutral-500 hover:bg-neutral-200"
              }`}
              title={`Set status to ${s.label}`}
            >
              {done ? "✓ " : ""}
              {s.label}
            </button>
          );
        })}
        <span className="mx-1 text-neutral-300">·</span>
        <button
          onClick={() => patchProject({ status: "lost" })}
          className={`rounded-full px-3 py-1 text-xs font-medium ${
            isLost ? "bg-red-600 text-white" : "bg-neutral-100 text-neutral-500 hover:bg-red-50 hover:text-red-600"
          }`}
        >
          Lost
        </button>
      </div>

      {/* travel window */}
      <div className="mb-5 grid gap-3 sm:grid-cols-2">
        <Field label="Travel start">
          <input
            type="date"
            className={inputCls}
            value={project.travel_start ?? ""}
            onChange={(e) => patchProject({ travel_start: e.target.value || null })}
          />
        </Field>
        <Field label="Travel end">
          <input
            type="date"
            className={inputCls}
            value={project.travel_end ?? ""}
            onChange={(e) => patchProject({ travel_end: e.target.value || null })}
          />
        </Field>
      </div>

      {/* milestones */}
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">
        Milestones &amp; deadlines
      </h3>
      {milestones.length === 0 ? (
        <p className="mb-3 rounded-md border border-dashed border-neutral-200 px-3 py-2 text-xs text-neutral-400">
          No milestones yet — add a payment, an invoice due date, or any deadline below.
        </p>
      ) : (
        <ul className="mb-3 space-y-1.5">
          {milestones.map((m) => (
            <li key={m.id} className="flex items-center gap-3 rounded-md border border-neutral-200 px-3 py-2 text-sm">
              <input type="checkbox" checked={m.done} onChange={() => toggleDone(m)} className="h-4 w-4" />
              <span className={`rounded px-1.5 py-0.5 text-[10px] uppercase ${KIND_BADGE[m.kind] ?? KIND_BADGE.other}`}>
                {m.kind}
              </span>
              <span className={`flex-1 ${m.done ? "text-neutral-400 line-through" : "text-neutral-800"}`}>
                {m.title}
              </span>
              {m.amount != null && <span className="tabular-nums text-neutral-600">{inr(m.amount)}</span>}
              <span className={`w-24 text-right text-xs ${dueTone(m)}`}>
                {m.due_date ?? "—"}
                {dueTone(m).includes("red") ? " · overdue" : ""}
              </span>
              <button onClick={() => removeMilestone(m.id)} className="text-neutral-400 hover:text-red-600" aria-label="Remove">
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}

      {/* add milestone */}
      <div className="flex flex-wrap items-end gap-2 rounded-md border border-neutral-200 bg-neutral-50 p-2">
        <select className={inputCls} value={draft.kind} onChange={(e) => setDraft({ ...draft, kind: e.target.value })}>
          <option value="payment">payment</option>
          <option value="invoice">invoice</option>
          <option value="deadline">deadline</option>
          <option value="note">note</option>
        </select>
        <input
          className={`${inputCls} flex-1`}
          placeholder="Title (e.g. Deposit 25%)"
          value={draft.title}
          onChange={(e) => setDraft({ ...draft, title: e.target.value })}
        />
        <input type="date" className={inputCls} value={draft.due_date} onChange={(e) => setDraft({ ...draft, due_date: e.target.value })} />
        <input className={`${inputCls} w-28`} placeholder="Amount ₹" value={draft.amount} onChange={(e) => setDraft({ ...draft, amount: e.target.value })} />
        <button className={draft.title.trim() ? btnDark : btnLight} onClick={addMilestone}>
          + Add
        </button>
      </div>
    </section>
  );
}
