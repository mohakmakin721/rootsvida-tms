"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Combobox } from "@/components/combobox";
import type {
  Facets,
  Freshness,
  SupplierDetail,
  SupplierPage,
  SupplierSummary,
} from "@/lib/types";

import {
  AddContactForm,
  AddRateForm,
  btnDark,
  btnLight,
  type DestOption,
  emptySupplier,
  OCCUPANCY_LABEL,
  SupplierForm,
  type SupplierFormValues,
  usesMealPlan,
  usesOccupancy,
  VENDOR_KINDS,
} from "./supplier-editor";

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
  state: string;
  destination_id: string;
  category: string;
  kind: string;
  status: string;
}

const EMPTY: Filters = { q: "", state: "", destination_id: "", category: "", kind: "", status: "" };

// Ascending, tidy pickers.
const KINDS = VENDOR_KINDS;
const STATUSES = ["active", "blacklisted", "contacted", "prospect"];

function buildQuery(filters: Filters, offset: number): string {
  const p = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
  if (filters.q.trim()) p.set("q", filters.q.trim());
  if (filters.state) p.set("state", filters.state);
  if (filters.destination_id) p.set("destination_id", filters.destination_id);
  if (filters.category) p.set("category", filters.category);
  if (filters.kind) p.set("kind", filters.kind);
  if (filters.status) p.set("status", filters.status);
  return p.toString();
}

export function SupplierBrowser({
  initialPage,
  facets: initialFacets,
  canEdit = false,
}: {
  initialPage: SupplierPage;
  facets: Facets;
  canEdit?: boolean;
}) {
  const [filters, setFilters] = useState<Filters>(EMPTY);
  const [page, setPage] = useState<SupplierPage>(initialPage);
  const [facets, setFacets] = useState<Facets>(initialFacets);
  const [allDestinations, setAllDestinations] = useState<DestOption[]>([]);
  const [adding, setAdding] = useState(false);
  const [importing, setImporting] = useState(false);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const first = useRef(true);

  const refreshFacets = useCallback(async () => {
    const res = await fetch("/api/v1/suppliers/facets", { cache: "no-store" });
    if (res.ok) setFacets((await res.json()) as Facets);
  }, []);

  const refreshDestinations = useCallback(async () => {
    const res = await fetch("/api/v1/destinations?limit=200", { cache: "no-store" });
    if (res.ok) setAllDestinations((await res.json()) as DestOption[]);
  }, []);

  useEffect(() => {
    if (canEdit) refreshDestinations();
  }, [canEdit, refreshDestinations]);

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

  const reload = useCallback(() => {
    fetchPage(filters, offset);
    refreshFacets();
  }, [fetchPage, filters, offset, refreshFacets]);

  async function createSupplier(body: Record<string, unknown>) {
    const res = await fetch("/api/v1/suppliers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const d = await res.json().catch(() => null);
      throw new Error(typeof d?.detail === "string" ? d.detail : `Could not create vendor (${res.status}).`);
    }
    setAdding(false);
    reload();
  }

  const showing = page.items.length;
  const pageStart = page.total === 0 ? 0 : offset + 1;
  const pageEnd = offset + showing;

  return (
    <div className="space-y-4">
      {canEdit && (
        <div>
          <div className="flex justify-end gap-2">
            <button className={btnLight} onClick={() => setImporting((v) => !v)}>
              {importing ? "Close import" : "⬆ Bulk import"}
            </button>
            <button className={btnDark} onClick={() => setAdding((a) => !a)}>
              {adding ? "Cancel" : "+ Add vendor"}
            </button>
          </div>
          {importing && <div className="mt-2"><BulkImport onDone={reload} /></div>}
          {adding && (
            <div className="mt-2">
              <SupplierForm
                initial={emptySupplier as SupplierFormValues}
                destinations={allDestinations}
                onDestinationsChanged={refreshDestinations}
                onSubmit={createSupplier}
                onCancel={() => setAdding(false)}
                submitLabel="Create vendor"
              />
            </div>
          )}
        </div>
      )}

      <div className="space-y-3">
        <input
          className="w-full rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm focus:border-neutral-500 focus:outline-none"
          placeholder="Search vendor name…"
          value={filters.q}
          onChange={(e) => update({ q: e.target.value })}
        />
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
          <Combobox
            placeholder="State…"
            value={filters.state || null}
            onChange={(v) => update({ state: v ?? "", destination_id: "" })}
            options={facets.states.map((s) => ({ value: s, label: s }))}
          />
          <Combobox
            placeholder="City…"
            value={filters.destination_id || null}
            onChange={(v) => update({ destination_id: v ?? "" })}
            options={facets.destinations
              .filter((d) => !filters.state || d.state === filters.state)
              .map((d) => ({
                value: d.id,
                label: `${d.name} (${d.supplier_count})`,
                sublabel: d.state ?? undefined,
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
      </div>

      <div className="flex items-center justify-between text-sm text-neutral-500">
        <span>
          {page.total === 0
            ? "No vendors match these filters."
            : `Showing ${pageStart}–${pageEnd} of ${page.total}`}
          {loading && <span className="ml-2 text-neutral-400">loading…</span>}
        </span>
        {(filters.q ||
          filters.state ||
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
              <th className="px-4 py-2 font-medium">Vendor</th>
              <th className="px-4 py-2 font-medium">Destination</th>
              <th className="px-4 py-2 font-medium">Category</th>
              <th className="px-4 py-2 font-medium">Status</th>
              <th className="px-4 py-2 font-medium">Rates</th>
              <th className="px-4 py-2 font-medium text-right">Open</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-100">
            {page.items.map((s) => (
              <SupplierRow
                key={s.id}
                supplier={s}
                canEdit={canEdit}
                destinations={allDestinations}
                onDestinationsChanged={refreshDestinations}
                onChanged={reload}
              />
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

function SupplierRow({
  supplier,
  canEdit,
  destinations,
  onDestinationsChanged,
  onChanged,
}: {
  supplier: SupplierSummary;
  canEdit: boolean;
  destinations: DestOption[];
  onDestinationsChanged: () => void;
  onChanged: () => void;
}) {
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
            <SupplierDetailPanel
              supplierId={supplier.id}
              canEdit={canEdit}
              destinations={destinations}
              onDestinationsChanged={onDestinationsChanged}
              onChanged={onChanged}
            />
          </td>
        </tr>
      )}
    </>
  );
}

function SupplierDetailPanel({
  supplierId,
  canEdit,
  destinations,
  onDestinationsChanged,
  onChanged,
}: {
  supplierId: string;
  canEdit: boolean;
  destinations: DestOption[];
  onDestinationsChanged: () => void;
  onChanged: () => void;
}) {
  const [detail, setDetail] = useState<SupplierDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const reload = () => {
    setReloadKey((k) => k + 1); // refetch this panel
    onChanged(); // refresh the list row
  };

  useEffect(() => {
    let live = true;
    fetch(`/api/v1/suppliers/${supplierId}`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((d: SupplierDetail) => live && setDetail(d))
      .catch(() => live && setError("Could not load vendor detail."));
    return () => {
      live = false;
    };
  }, [supplierId, reloadKey]);

  async function saveEdit(body: Record<string, unknown>) {
    const res = await fetch(`/api/v1/suppliers/${supplierId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const d = await res.json().catch(() => null);
      throw new Error(typeof d?.detail === "string" ? d.detail : `Could not save (${res.status}).`);
    }
    setEditing(false);
    reload();
  }

  async function deleteSupplier() {
    if (!confirm("Delete this vendor? It will be removed from the browser.")) return;
    await fetch(`/api/v1/suppliers/${supplierId}`, { method: "DELETE" });
    onChanged();
  }

  async function del(path: string) {
    await fetch(`/api/v1/suppliers/${path}`, { method: "DELETE" });
    reload();
  }

  if (error) return <p className="text-sm text-red-700">{error}</p>;
  if (!detail) return <p className="text-sm text-neutral-400">Loading…</p>;

  return (
    <div className="space-y-4">
      {canEdit && (
        <div className="flex items-center justify-between">
          <div className="flex gap-2">
            <button className={btnLight} onClick={() => setEditing((e) => !e)}>
              {editing ? "Cancel" : "Edit vendor"}
            </button>
            <button className={`${btnLight} text-red-600`} onClick={deleteSupplier}>
              Delete
            </button>
          </div>
          {detail.notes && !editing && (
            <span className="text-xs text-neutral-400">{detail.notes}</span>
          )}
        </div>
      )}

      {editing && (
        <SupplierForm
          initial={{
            kind: detail.kind, legal_name: detail.legal_name, display_name: detail.display_name,
            destination_id: detail.destination_id, category: detail.category ?? "",
            property_type: detail.property_type ?? "", status: detail.status,
            gstin: detail.gstin ?? "", pan: detail.pan ?? "", notes: detail.notes ?? "",
          }}
          destinations={destinations}
          onDestinationsChanged={onDestinationsChanged}
          onSubmit={saveEdit}
          onCancel={() => setEditing(false)}
          submitLabel="Save changes"
        />
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <section>
          <SectionTitle>Contacts</SectionTitle>
          {detail.contacts.length === 0 ? (
            <Empty>No contacts recorded.</Empty>
          ) : (
            <ul className="space-y-2">
              {detail.contacts.map((c) => (
                <li key={c.id} className="flex items-start justify-between rounded-md border border-neutral-200 bg-white px-3 py-2 text-sm">
                  <div>
                    <div className="font-medium text-neutral-800">
                      {c.person_name ?? "—"}
                      {c.is_primary && (
                        <span className="ml-2 rounded bg-neutral-100 px-1.5 py-0.5 text-xs text-neutral-500">primary</span>
                      )}
                    </div>
                    <div className="text-xs text-neutral-600">
                      {[c.role, c.phone_e164 ?? c.phone_raw, c.email, c.website].filter(Boolean).join(" · ") || "no reachable details"}
                    </div>
                  </div>
                  {canEdit && (
                    <button className="text-neutral-400 hover:text-red-600" onClick={() => del(`contacts/${c.id}`)} aria-label="Delete contact">✕</button>
                  )}
                </li>
              ))}
            </ul>
          )}
          {canEdit && <AddContactForm supplierId={supplierId} onAdded={reload} />}
        </section>

        <section>
          <VendorRates
            detail={detail}
            supplierId={supplierId}
            canEdit={canEdit}
            onDelete={del}
            onReload={reload}
          />
        </section>
      </div>
    </div>
  );
}

/** The rate section — a single unified table for every vendor kind. The first
 *  column adapts: stay shows meal plan + bedding, meal shows the meal plan, other
 *  kinds show just the rate. */
function VendorRates({
  detail,
  supplierId,
  canEdit,
  onDelete,
  onReload,
}: {
  detail: SupplierDetail;
  supplierId: string;
  canEdit: boolean;
  onDelete: (path: string) => void;
  onReload: () => void;
}) {
  const kind = detail.kind;
  const showDetailCol = usesMealPlan(kind);
  return (
    <>
      <SectionTitle>Rates</SectionTitle>
      {detail.rates.length === 0 ? (
        <Empty>No rates yet.</Empty>
      ) : (
        <div className="overflow-x-auto rounded-md border border-neutral-200 bg-white">
          <table className="w-full text-left text-xs">
            <thead className="bg-neutral-50 text-neutral-500">
              <tr>
                {showDetailCol && <th className="px-2 py-1.5 font-medium">{usesOccupancy(kind) ? "Plan / bedding" : "Meal plan"}</th>}
                <th className="px-2 py-1.5 font-medium text-right">Amount</th>
                <th className="px-2 py-1.5 font-medium">Validity</th>
                <th className="px-2 py-1.5 font-medium">Freshness</th>
                {canEdit && <th className="px-2 py-1.5" />}
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {detail.rates.map((r) => (
                <tr key={r.id}>
                  {showDetailCol && (
                    <td className="px-2 py-1.5 text-neutral-700">
                      {r.meal_plan}{usesOccupancy(kind) ? ` · ${OCCUPANCY_LABEL[r.occupancy] ?? r.occupancy}` : ""}
                    </td>
                  )}
                  <td className="px-2 py-1.5 text-right font-medium text-neutral-900">
                    ₹{Number(r.amount).toLocaleString("en-IN")}
                  </td>
                  <td className="px-2 py-1.5 text-neutral-600">{r.valid_from} → {r.valid_to}</td>
                  <td className="px-2 py-1.5">
                    <span className={`inline-block h-2 w-2 rounded-full ${FRESHNESS[r.freshness].dot}`} title={FRESHNESS[r.freshness].label} />
                  </td>
                  {canEdit && (
                    <td className="px-2 py-1.5 text-right">
                      <button className="text-neutral-400 hover:text-red-600" onClick={() => onDelete(`rates/${r.id}`)} aria-label="Delete rate">✕</button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {canEdit && <AddRateForm supplierId={supplierId} kind={kind} onAdded={onReload} />}
    </>
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

interface ImportResult {
  committed: boolean;
  vendors_created: number;
  vendors_matched: number;
  rates_created: number;
  skipped: number;
  error_count: number;
  ok: boolean;
  errors: { sheet: string; row: number; message: string }[];
}

/** Download the template, validate a filled file (dry-run), then commit. Imported
 *  vendors land as unverified 'prospect' + rates 'on_file' for later review. */
function BulkImport({ onDone }: { onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportResult | null>(null);
  const [committed, setCommitted] = useState<ImportResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function downloadTemplate() {
    setError(null);
    try {
      const res = await fetch("/api/v1/suppliers/import/template");
      if (!res.ok) throw new Error();
      const url = URL.createObjectURL(await res.blob());
      const a = document.createElement("a");
      a.href = url;
      a.download = "rootsvida_vendor_import_template.xlsx";
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Could not download the template.");
    }
  }

  async function send(commit: boolean) {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`/api/v1/suppliers/import?commit=${commit}`, {
        method: "POST",
        body: fd,
      });
      if (!res.ok) throw new Error(`Import failed (${res.status})`);
      const result = (await res.json()) as ImportResult;
      if (commit) {
        setCommitted(result);
        setPreview(null);
        onDone();
      } else {
        setPreview(result);
        setCommitted(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Import failed.");
    } finally {
      setBusy(false);
    }
  }

  const summary = committed ?? preview;

  return (
    <div className="space-y-3 rounded-md border border-indigo-200 bg-indigo-50/40 p-4">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <button className={btnLight} onClick={downloadTemplate}>⬇ Download template</button>
        <label className={`${btnLight} cursor-pointer`}>
          ⬆ Choose file
          <input
            type="file"
            accept=".xlsx"
            className="hidden"
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              setPreview(null);
              setCommitted(null);
            }}
          />
        </label>
        <span className="max-w-[16rem] truncate text-xs text-neutral-600">
          {file ? file.name : "No file chosen"}
        </span>
        <button className={btnLight} disabled={!file || busy} onClick={() => send(false)}>
          {busy && !committed ? "Checking…" : "Validate"}
        </button>
      </div>
      <p className="text-xs text-neutral-500">
        Fill the template’s <b>Vendors</b> and <b>Rates</b> sheets. Imported vendors are
        saved as <b>prospect</b> (unverified) and rates as <b>on_file</b> — review them
        afterwards. Validate first to preview; nothing is written until you confirm.
      </p>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {summary && (
        <div className="rounded-md border border-neutral-200 bg-white p-3 text-sm">
          <p className="font-medium text-neutral-800">
            {committed ? "Imported ✓" : "Preview (nothing written yet)"}
          </p>
          <ul className="mt-1 text-xs text-neutral-600">
            <li>Vendors created: {summary.vendors_created}</li>
            <li>Vendors matched (existing): {summary.vendors_matched}</li>
            <li>Rates created: {summary.rates_created}</li>
            <li>Skipped (overlapping rates): {summary.skipped}</li>
            <li className={summary.error_count ? "text-amber-700" : ""}>
              Rows with problems: {summary.error_count}
            </li>
          </ul>
          {summary.errors.length > 0 && (
            <ul className="mt-2 max-h-40 space-y-0.5 overflow-auto border-t border-neutral-100 pt-2 text-xs text-amber-800">
              {summary.errors.slice(0, 50).map((e, i) => (
                <li key={i}>
                  {e.sheet} row {e.row}: {e.message}
                </li>
              ))}
            </ul>
          )}
          {preview && !committed && (
            <button
              className={`${btnDark} mt-3`}
              disabled={busy}
              onClick={() => send(true)}
            >
              {busy ? "Importing…" : `Confirm import (${preview.vendors_created} vendors, ${preview.rates_created} rates)`}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
