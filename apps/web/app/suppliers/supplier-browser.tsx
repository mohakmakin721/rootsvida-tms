"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type {
  Facets,
  Freshness,
  Rate,
  SupplierDetail,
  SupplierPage,
  SupplierSummary,
} from "@/lib/types";

const PAGE_SIZE = 50;

const FRESHNESS: Record<Freshness, { dot: string; label: string; text: string }> = {
  fresh: { dot: "bg-emerald-500", label: "Fresh", text: "text-emerald-700" },
  expiring: { dot: "bg-amber-500", label: "Expiring", text: "text-amber-700" },
  expired: { dot: "bg-red-500", label: "Expired", text: "text-red-700" },
  none: { dot: "bg-neutral-300", label: "No rates", text: "text-neutral-500" },
};

function Badge({ freshness, count }: { freshness: Freshness; count: number }) {
  const f = FRESHNESS[freshness];
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${f.text}`}>
      <span className={`h-2 w-2 rounded-full ${f.dot}`} aria-hidden />
      {f.label}
      {count > 0 && <span className="text-neutral-400">· {count}</span>}
    </span>
  );
}

interface Filters {
  q: string;
  destination_id: string;
  category: string;
  kind: string;
  status: string;
}

const EMPTY: Filters = { q: "", destination_id: "", category: "", kind: "", status: "" };

const KINDS = ["hotel", "homestay", "transport", "guide", "activity"];
const STATUSES = ["prospect", "contacted", "active", "blacklisted"];

function buildQuery(filters: Filters, offset: number): string {
  const p = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
  if (filters.q.trim()) p.set("q", filters.q.trim());
  if (filters.destination_id) p.set("destination_id", filters.destination_id);
  if (filters.category) p.set("category", filters.category);
  if (filters.kind) p.set("kind", filters.kind);
  if (filters.status) p.set("status", filters.status);
  return p.toString();
}

export function SupplierBrowser({
  initialPage,
  facets,
}: {
  initialPage: SupplierPage;
  facets: Facets;
}) {
  const [filters, setFilters] = useState<Filters>(EMPTY);
  const [page, setPage] = useState<SupplierPage>(initialPage);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const first = useRef(true);

  const fetchPage = useCallback(async (f: Filters, off: number) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/v1/suppliers?${buildQuery(f, off)}`, {
        cache: "no-store",
      });
      if (!res.ok) throw new Error(`Request failed (${res.status}).`);
      setPage((await res.json()) as SupplierPage);
    } catch {
      setError("Could not reach the domain service.");
    } finally {
      setLoading(false);
    }
  }, []);

  // Debounce filter changes; skip the very first render (server already fetched it).
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    const t = setTimeout(() => fetchPage(filters, offset), 250);
    return () => clearTimeout(t);
  }, [filters, offset, fetchPage]);

  function update(patch: Partial<Filters>) {
    setOffset(0);
    setFilters((prev) => ({ ...prev, ...patch }));
  }

  const showing = page.items.length;
  const pageStart = page.total === 0 ? 0 : offset + 1;
  const pageEnd = offset + showing;

  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-6">
        <input
          className="md:col-span-2 rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm focus:border-neutral-500 focus:outline-none"
          placeholder="Search name…"
          value={filters.q}
          onChange={(e) => update({ q: e.target.value })}
        />
        <Select
          value={filters.destination_id}
          onChange={(v) => update({ destination_id: v })}
          placeholder="All destinations"
          options={facets.destinations.map((d) => ({
            value: d.id,
            label: `${d.name} (${d.supplier_count})`,
          }))}
        />
        <Select
          value={filters.category}
          onChange={(v) => update({ category: v })}
          placeholder="All categories"
          options={facets.categories.map((c) => ({ value: c, label: c }))}
        />
        <Select
          value={filters.kind}
          onChange={(v) => update({ kind: v })}
          placeholder="All kinds"
          options={KINDS.map((k) => ({ value: k, label: k }))}
        />
        <Select
          value={filters.status}
          onChange={(v) => update({ status: v })}
          placeholder="All statuses"
          options={STATUSES.map((s) => ({ value: s, label: s }))}
        />
      </div>

      <div className="flex items-center justify-between text-sm text-neutral-500">
        <span>
          {page.total === 0
            ? "No suppliers match these filters."
            : `Showing ${pageStart}–${pageEnd} of ${page.total}`}
          {loading && <span className="ml-2 text-neutral-400">loading…</span>}
        </span>
        {(filters.q ||
          filters.destination_id ||
          filters.category ||
          filters.kind ||
          filters.status) && (
          <button
            className="text-neutral-500 underline hover:text-neutral-800"
            onClick={() => update(EMPTY)}
          >
            Clear filters
          </button>
        )}
      </div>

      {error && (
        <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      <div className="overflow-hidden rounded-lg border border-neutral-200">
        <table className="w-full text-left text-sm">
          <thead className="bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
            <tr>
              <th className="px-4 py-2 font-medium">Supplier</th>
              <th className="px-4 py-2 font-medium">Destination</th>
              <th className="px-4 py-2 font-medium">Category</th>
              <th className="px-4 py-2 font-medium">Status</th>
              <th className="px-4 py-2 font-medium">Rates</th>
              <th className="px-4 py-2 font-medium text-right">Open</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-100">
            {page.items.map((s) => (
              <SupplierRow key={s.id} supplier={s} />
            ))}
            {page.items.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-neutral-400">
                  Nothing to show.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {page.total > PAGE_SIZE && (
        <div className="flex items-center justify-end gap-2 text-sm">
          <button
            disabled={offset === 0 || loading}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            className="rounded-md border border-neutral-300 px-3 py-1.5 disabled:opacity-40"
          >
            ← Prev
          </button>
          <button
            disabled={pageEnd >= page.total || loading}
            onClick={() => setOffset(offset + PAGE_SIZE)}
            className="rounded-md border border-neutral-300 px-3 py-1.5 disabled:opacity-40"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}

function Select({
  value,
  onChange,
  placeholder,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  options: { value: string; label: string }[];
}) {
  return (
    <select
      className="rounded-md border border-neutral-300 bg-white px-2 py-2 text-sm focus:border-neutral-500 focus:outline-none"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="">{placeholder}</option>
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

function SupplierRow({ supplier }: { supplier: SupplierSummary }) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <tr className="cursor-pointer hover:bg-neutral-50" onClick={() => setOpen((o) => !o)}>
        <td className="px-4 py-3">
          <div className="font-medium text-neutral-900">{supplier.display_name}</div>
          <div className="text-xs text-neutral-500 capitalize">{supplier.kind}</div>
        </td>
        <td className="px-4 py-3 text-neutral-600">{supplier.destination_name ?? "—"}</td>
        <td className="px-4 py-3 text-neutral-600">{supplier.category ?? "—"}</td>
        <td className="px-4 py-3 text-neutral-600 capitalize">{supplier.status}</td>
        <td className="px-4 py-3">
          <Badge freshness={supplier.freshness} count={supplier.rate_count} />
        </td>
        <td className="px-4 py-3 text-right text-neutral-400">{open ? "▲" : "▼"}</td>
      </tr>
      {open && (
        <tr className="bg-neutral-50/60">
          <td colSpan={6} className="px-4 py-4">
            <SupplierDetailPanel supplierId={supplier.id} />
          </td>
        </tr>
      )}
    </>
  );
}

function SupplierDetailPanel({ supplierId }: { supplierId: string }) {
  const [detail, setDetail] = useState<SupplierDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    fetch(`/api/v1/suppliers/${supplierId}`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((d: SupplierDetail) => live && setDetail(d))
      .catch(() => live && setError("Could not load supplier detail."));
    return () => {
      live = false;
    };
  }, [supplierId]);

  if (error) return <p className="text-sm text-red-700">{error}</p>;
  if (!detail) return <p className="text-sm text-neutral-400">Loading…</p>;

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <section>
        <SectionTitle>Contacts</SectionTitle>
        {detail.contacts.length === 0 ? (
          <Empty>No contacts recorded.</Empty>
        ) : (
          <ul className="space-y-2">
            {detail.contacts.map((c, i) => (
              <li key={i} className="rounded-md border border-neutral-200 bg-white px-3 py-2 text-sm">
                <div className="font-medium text-neutral-800">
                  {c.person_name ?? "—"}
                  {c.is_primary && (
                    <span className="ml-2 rounded bg-neutral-100 px-1.5 py-0.5 text-xs text-neutral-500">
                      primary
                    </span>
                  )}
                </div>
                <div className="text-xs text-neutral-600">
                  {[c.role, c.phone_e164 ?? c.phone_raw, c.email, c.website]
                    .filter(Boolean)
                    .join(" · ") || "no reachable details"}
                </div>
                {c.unusable_reason && (
                  <div className="text-xs text-amber-700">⚠ {c.unusable_reason}</div>
                )}
              </li>
            ))}
          </ul>
        )}

        <SectionTitle className="mt-4">Room types</SectionTitle>
        {detail.room_types.length === 0 ? (
          <Empty>No room types recorded.</Empty>
        ) : (
          <div className="flex flex-wrap gap-2">
            {detail.room_types.map((rt) => (
              <span
                key={rt.id}
                className="rounded-md border border-neutral-200 bg-white px-2 py-1 text-xs text-neutral-700"
              >
                {rt.name} · {rt.max_adults}A/{rt.max_children}C
              </span>
            ))}
          </div>
        )}
      </section>

      <section>
        <SectionTitle>Rates</SectionTitle>
        {detail.rates.length === 0 ? (
          <Empty>
            No rates yet — this supplier is a prospect. Rates land through the review
            queue.
          </Empty>
        ) : (
          <div className="overflow-hidden rounded-md border border-neutral-200 bg-white">
            <table className="w-full text-left text-xs">
              <thead className="bg-neutral-50 text-neutral-500">
                <tr>
                  <th className="px-2 py-1.5 font-medium">Plan / Occ</th>
                  <th className="px-2 py-1.5 font-medium text-right">Amount</th>
                  <th className="px-2 py-1.5 font-medium">Validity</th>
                  <th className="px-2 py-1.5 font-medium">Freshness</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {detail.rates.map((r) => (
                  <RateRow key={r.id} rate={r} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function RateRow({ rate }: { rate: Rate }) {
  return (
    <tr>
      <td className="px-2 py-1.5 text-neutral-700">
        {rate.meal_plan} · {rate.occupancy}
      </td>
      <td className="px-2 py-1.5 text-right font-medium text-neutral-900">
        {rate.currency} {rate.amount}
      </td>
      <td className="px-2 py-1.5 text-neutral-600">
        {rate.valid_from} → {rate.valid_to}
      </td>
      <td className="px-2 py-1.5">
        <Badge freshness={rate.freshness} count={0} />
      </td>
    </tr>
  );
}

function SectionTitle({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <h3
      className={`mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500 ${className}`}
    >
      {children}
    </h3>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-md border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-400">
      {children}
    </p>
  );
}
