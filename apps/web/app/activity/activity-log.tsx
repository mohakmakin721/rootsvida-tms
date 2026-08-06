"use client";

import { useEffect, useMemo, useState } from "react";

import Link from "next/link";

import { inr } from "@/lib/constants";
import type { ActivityRow } from "@/lib/types";

const KIND: Record<string, { label: string; badge: string; dot: string }> = {
  payment: { label: "Payment received", badge: "bg-emerald-100 text-emerald-700", dot: "bg-emerald-500" },
  payment_deadline: { label: "Payment due", badge: "bg-amber-100 text-amber-800", dot: "bg-amber-500" },
  invoice: { label: "Invoice", badge: "bg-blue-100 text-blue-700", dot: "bg-blue-500" },
  note: { label: "Note", badge: "bg-neutral-100 text-neutral-500", dot: "bg-neutral-400" },
};

const KIND_FILTERS = [
  { value: "", label: "All types" },
  { value: "payment", label: "Payment received" },
  { value: "payment_deadline", label: "Payment due" },
  { value: "invoice", label: "Invoice" },
  { value: "note", label: "Note" },
];

const STATUSES = ["enquiry", "quoted", "confirmed", "operating", "closed", "lost"];
const TODAY = new Date().toISOString().slice(0, 10);

const inputCls =
  "rounded-md border border-neutral-300 bg-white px-2 py-1.5 text-sm focus:border-neutral-500 focus:outline-none";

export function ActivityLog({ initial }: { initial: ActivityRow[] }) {
  const [rows, setRows] = useState<ActivityRow[]>(initial);
  const [q, setQ] = useState("");
  const [kind, setKind] = useState("");
  const [status, setStatus] = useState("");
  const [pending, setPending] = useState<"" | "pending" | "done">("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const t = setTimeout(async () => {
      setLoading(true);
      const params = new URLSearchParams();
      if (q.trim()) params.set("q", q.trim());
      if (kind) params.set("kind", kind);
      if (status) params.set("status", status);
      if (pending === "pending") params.set("done", "false");
      if (pending === "done") params.set("done", "true");
      try {
        const res = await fetch(`/api/v1/projects/activity-log?${params.toString()}`, { cache: "no-store" });
        if (res.ok) setRows((await res.json()) as ActivityRow[]);
      } finally {
        setLoading(false);
      }
    }, 250);
    return () => clearTimeout(t);
  }, [q, kind, status, pending]);

  const counts = useMemo(() => {
    const c = { payment: 0, payment_deadline: 0, invoice: 0, note: 0, overdue: 0 };
    for (const r of rows) {
      c[r.kind as keyof typeof c] = (c[r.kind as keyof typeof c] ?? 0) + 1;
      if (r.kind === "payment_deadline" && !r.done && r.due_date && r.due_date < TODAY) c.overdue += 1;
    }
    return c;
  }, [rows]);

  return (
    <div className="space-y-4">
      {/* filters */}
      <div className="flex flex-wrap items-center gap-2">
        <input
          className={`${inputCls} w-64`}
          placeholder="Search project code or client name…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select className={inputCls} value={kind} onChange={(e) => setKind(e.target.value)}>
          {KIND_FILTERS.map((k) => (
            <option key={k.value} value={k.value}>{k.label}</option>
          ))}
        </select>
        <select className={inputCls} value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s} className="capitalize">{s}</option>
          ))}
        </select>
        <select className={inputCls} value={pending} onChange={(e) => setPending(e.target.value as "" | "pending" | "done")}>
          <option value="">Done &amp; pending</option>
          <option value="pending">Pending only</option>
          <option value="done">Done only</option>
        </select>
        {loading && <span className="text-xs text-neutral-400">loading…</span>}
      </div>

      {/* quick counts */}
      <div className="flex flex-wrap gap-2 text-xs">
        <Count dot={KIND.payment.dot} label="received" n={counts.payment} />
        <Count dot={KIND.payment_deadline.dot} label="due" n={counts.payment_deadline} />
        <Count dot={KIND.invoice.dot} label="invoices" n={counts.invoice} />
        <Count dot={KIND.note.dot} label="notes" n={counts.note} />
        {counts.overdue > 0 && (
          <span className="rounded-full bg-red-100 px-2 py-0.5 font-medium text-red-700">
            {counts.overdue} overdue
          </span>
        )}
      </div>

      {/* log table */}
      {rows.length === 0 ? (
        <p className="rounded-md border border-dashed border-neutral-200 px-3 py-6 text-center text-sm text-neutral-400">
          No activity matches these filters.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-neutral-200">
          <table className="w-full min-w-[52rem] text-left text-sm">
            <thead className="bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
              <tr>
                <th className="px-3 py-2 font-medium">Date</th>
                <th className="px-3 py-2 font-medium">Type</th>
                <th className="px-3 py-2 font-medium">Project</th>
                <th className="px-3 py-2 font-medium">Client</th>
                <th className="px-3 py-2 font-medium">Detail</th>
                <th className="px-3 py-2 font-medium text-right">Amount</th>
                <th className="px-3 py-2 font-medium">Project status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {rows.map((r) => {
                const k = KIND[r.kind] ?? KIND.note;
                const overdue = r.kind === "payment_deadline" && !r.done && r.due_date && r.due_date < TODAY;
                return (
                  <tr key={r.id} className="hover:bg-neutral-50">
                    <td className={`whitespace-nowrap px-3 py-2 ${overdue ? "font-medium text-red-600" : "text-neutral-600"}`}>
                      {r.due_date ?? "—"}
                      {overdue ? " · overdue" : ""}
                    </td>
                    <td className="px-3 py-2">
                      <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium uppercase ${k.badge}`}>
                        <span className={`h-1.5 w-1.5 rounded-full ${k.dot}`} />
                        {k.label}
                        {r.done && r.kind === "payment_deadline" ? " ✓" : ""}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <Link href={`/projects/${r.project_id}`} className="font-medium text-neutral-800 underline hover:text-neutral-950">
                        {r.project_code}
                      </Link>
                    </td>
                    <td className="px-3 py-2 text-neutral-700">{r.client_name}</td>
                    <td className="px-3 py-2 text-neutral-700">{r.title}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-neutral-800">
                      {r.amount != null ? inr(r.amount) : "—"}
                    </td>
                    <td className="px-3 py-2 capitalize text-neutral-500">{r.project_status}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Count({ dot, label, n }: { dot: string; label: string; n: number }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-neutral-100 px-2 py-0.5 text-neutral-600">
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
      {n} {label}
    </span>
  );
}
