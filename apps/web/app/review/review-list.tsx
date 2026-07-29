"use client";

import { useState } from "react";

import type { DecisionAction, ReviewItem } from "@/lib/types";

/** The source cells behind an item: a needs-review supplier candidate carries the
 *  verbatim row under `proposed.raw_values`; otherwise show the proposal itself. */
function sourceEntries(item: ReviewItem): [string, unknown][] {
  const raw = item.proposed["raw_values"];
  const obj =
    raw && typeof raw === "object" ? (raw as Record<string, unknown>) : item.proposed;
  return Object.entries(obj);
}

function named(value: unknown): string | null {
  if (value && typeof value === "object") {
    const dn = (value as Record<string, unknown>)["display_name"];
    if (dn) return String(dn);
  }
  return null;
}

function summarise(item: ReviewItem): string {
  // Merge candidates carry a primary/duplicate pair.
  if (item.entity_type === "merge_candidate") {
    const a = named(item.proposed["primary"]);
    const b = named(item.proposed["duplicate"]);
    if (a && b) return `${a} ↔ ${b}`;
  }
  const raw = item.proposed["raw_values"];
  const obj =
    raw && typeof raw === "object" ? (raw as Record<string, unknown>) : item.proposed;
  const name = obj["Name"] ?? obj["display_name"] ?? obj["name"];
  const place = obj["Place"] ?? obj["place"] ?? obj["destination_name"];
  if (name) return place ? `${String(name)} — ${String(place)}` : String(name);
  return item.dedupe_key ?? item.id.slice(0, 8);
}

function cell(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function ReviewList({ initialItems }: { initialItems: ReviewItem[] }) {
  const [items, setItems] = useState<ReviewItem[]>(initialItems);
  const [openId, setOpenId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function open(item: ReviewItem) {
    setError(null);
    if (openId === item.id) {
      setOpenId(null);
      return;
    }
    setOpenId(item.id);
    setDraft(JSON.stringify(item.proposed, null, 2));
    setNotes("");
  }

  async function decide(item: ReviewItem, action: DecisionAction) {
    setError(null);
    let body: Record<string, unknown> = { notes: notes || null };
    if (action === "edit") {
      try {
        body = { proposed: JSON.parse(draft), notes: notes || null };
      } catch {
        setError("Edited proposal is not valid JSON.");
        return;
      }
    }
    setBusy(true);
    try {
      const res = await fetch(`/api/v1/review-queue/${item.id}/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setError(detail?.detail ?? `Request failed (${res.status}).`);
        return;
      }
      // Decided items leave the pending view.
      setItems((prev) => prev.filter((i) => i.id !== item.id));
      setOpenId(null);
    } catch {
      setError("Could not reach the domain service.");
    } finally {
      setBusy(false);
    }
  }

  if (items.length === 0) {
    return (
      <p className="rounded-lg border border-neutral-200 bg-neutral-50 p-6 text-sm text-neutral-500">
        No pending items. The queue is clear.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {error && (
        <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      <div className="overflow-hidden rounded-lg border border-neutral-200">
        <table className="w-full text-left text-sm">
          <thead className="bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
            <tr>
              <th className="px-4 py-2 font-medium">Candidate</th>
              <th className="px-4 py-2 font-medium">Type</th>
              <th className="px-4 py-2 font-medium">Confidence</th>
              <th className="px-4 py-2 font-medium text-right">Review</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-100">
            {items.map((item) => (
              <FragmentRow
                key={item.id}
                item={item}
                open={openId === item.id}
                busy={busy}
                draft={draft}
                notes={notes}
                onToggle={() => open(item)}
                onDraft={setDraft}
                onNotes={setNotes}
                onDecide={(action) => decide(item, action)}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function FragmentRow({
  item,
  open,
  busy,
  draft,
  notes,
  onToggle,
  onDraft,
  onNotes,
  onDecide,
}: {
  item: ReviewItem;
  open: boolean;
  busy: boolean;
  draft: string;
  notes: string;
  onToggle: () => void;
  onDraft: (v: string) => void;
  onNotes: (v: string) => void;
  onDecide: (action: DecisionAction) => void;
}) {
  return (
    <>
      <tr className="cursor-pointer hover:bg-neutral-50" onClick={onToggle}>
        <td className="px-4 py-3 font-medium text-neutral-900">{summarise(item)}</td>
        <td className="px-4 py-3 text-neutral-600">{item.entity_type}</td>
        <td className="px-4 py-3 text-neutral-600">
          {item.confidence === null ? "—" : `${Math.round(item.confidence * 100)}%`}
        </td>
        <td className="px-4 py-3 text-right text-neutral-400">{open ? "▲" : "▼"}</td>
      </tr>
      {open && (
        <tr className="bg-neutral-50/60">
          <td colSpan={4} className="px-4 py-4">
            <div className="grid gap-4 md:grid-cols-2">
              <section>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">
                  Source
                </h3>
                <dl className="divide-y divide-neutral-100 rounded-md border border-neutral-200 bg-white">
                  {sourceEntries(item).map(([k, v]) => (
                    <div key={k} className="grid grid-cols-3 gap-2 px-3 py-1.5">
                      <dt className="col-span-1 truncate text-xs text-neutral-500">{k}</dt>
                      <dd className="col-span-2 break-words text-sm text-neutral-800">
                        {cell(v)}
                      </dd>
                    </div>
                  ))}
                </dl>
              </section>

              <section>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">
                  Proposed (editable)
                </h3>
                <textarea
                  className="h-48 w-full rounded-md border border-neutral-300 bg-white p-2 font-mono text-xs text-neutral-800 focus:border-neutral-500 focus:outline-none"
                  value={draft}
                  onChange={(e) => onDraft(e.target.value)}
                  spellCheck={false}
                />
                <input
                  className="mt-2 w-full rounded-md border border-neutral-300 bg-white px-2 py-1.5 text-sm focus:border-neutral-500 focus:outline-none"
                  placeholder="Reviewer notes (optional)"
                  value={notes}
                  onChange={(e) => onNotes(e.target.value)}
                />
                <div className="mt-3 flex gap-2">
                  <button
                    disabled={busy}
                    onClick={() => onDecide("approve")}
                    className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                  >
                    Approve
                  </button>
                  <button
                    disabled={busy}
                    onClick={() => onDecide("edit")}
                    className="rounded-md bg-neutral-800 px-3 py-1.5 text-sm font-medium text-white hover:bg-neutral-900 disabled:opacity-50"
                  >
                    Save &amp; accept
                  </button>
                  <button
                    disabled={busy}
                    onClick={() => onDecide("reject")}
                    className="rounded-md border border-red-300 px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
                  >
                    Reject
                  </button>
                </div>
              </section>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
