"use client";

import { useEffect, useRef, useState } from "react";

import type { ComponentKind, Rate, SupplierDetail, SupplierSummary } from "@/lib/types";

import { btnDark, btnLight, inputCls } from "./ui";

export interface RatePick {
  supplier_id: string | null;
  rate_id: string | null;
  rate_label: string | null;
  rate_amount: string | null;
}

// Each component kind restricts the vendor search to matching vendor type(s) — so
// a "guide" cost only suggests guide vendors, a "stay" only hotels/homestays, etc.
const KIND_FILTER: Record<ComponentKind, string[]> = {
  stay: ["hotel", "homestay"],
  transport: ["transport"],
  guide: ["guide"],
  activity: ["activity"],
  meal: ["meal"],
  permit: ["permit"],
  misc: ["misc", "facilitator", "photographer"],
};

// The default vendor kind to pre-select when adding a new vendor for this component.
const NEW_VENDOR_KIND: Record<ComponentKind, string> = {
  stay: "hotel",
  transport: "transport",
  guide: "guide",
  activity: "activity",
  meal: "meal",
  permit: "permit",
  misc: "misc",
};

const MEAL_PLANS = ["EP", "CP", "MAP", "AP", "CPAI", "MAPAI", "APAI", "CAPAI"];
const OCCUPANCIES = ["single", "double", "triple", "extra_adult", "child_wb", "child_nb"];

function today(): string {
  return new Date().toISOString().slice(0, 10);
}
function inAYear(): string {
  const d = new Date();
  d.setUTCFullYear(d.getUTCFullYear() + 1);
  return d.toISOString().slice(0, 10);
}

function rateLabel(supplierName: string, r: Rate): string {
  return `${supplierName} · ${r.meal_plan} · ${r.occupancy}`;
}

export function SupplierRatePicker({
  kind,
  destinationId,
  supplierId,
  rateId,
  rateLabel: pickedLabel,
  onPick,
}: {
  kind: ComponentKind;
  destinationId: string | null;
  supplierId: string | null;
  rateId: string | null;
  rateLabel: string | null;
  onPick: (p: RatePick) => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SupplierSummary[]>([]);
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<SupplierDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  // Debounced supplier search while the dropdown is open and no supplier is chosen.
  useEffect(() => {
    if (!open || supplierId) return;
    const handle = setTimeout(async () => {
      const params = new URLSearchParams({ limit: "15" });
      if (query.trim()) params.set("q", query.trim());
      const kf = KIND_FILTER[kind];
      if (kf && kf.length) params.set("kind", kf.join(","));
      if (destinationId) params.set("destination_id", destinationId);
      try {
        const res = await fetch(`/api/v1/suppliers?${params.toString()}`);
        if (res.ok) setResults(((await res.json()).items as SupplierSummary[]) ?? []);
      } catch {
        /* ignore — leave prior results */
      }
    }, 250);
    return () => clearTimeout(handle);
  }, [open, query, kind, destinationId, supplierId]);

  // Load the chosen supplier's rates so they can be picked.
  useEffect(() => {
    if (!supplierId) {
      setDetail(null);
      return;
    }
    if (detail?.id === supplierId) return;
    setLoadingDetail(true);
    fetch(`/api/v1/suppliers/${supplierId}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setDetail(d as SupplierDetail | null))
      .catch(() => setDetail(null))
      .finally(() => setLoadingDetail(false));
  }, [supplierId, detail?.id]);

  function chooseSupplier(s: SupplierSummary) {
    setOpen(false);
    setQuery("");
    setError(null);
    // Select the supplier; rate still to be chosen.
    onPick({ supplier_id: s.id, rate_id: null, rate_label: s.display_name, rate_amount: null });
  }

  function chooseRate(r: Rate) {
    if (!detail) return;
    onPick({
      supplier_id: detail.id,
      rate_id: r.id,
      rate_label: rateLabel(detail.display_name, r),
      rate_amount: r.amount,
    });
  }

  function clearAll() {
    setError(null);
    onPick({ supplier_id: null, rate_id: null, rate_label: null, rate_amount: null });
  }

  // ---- selected state: rate picked ----
  if (supplierId && rateId) {
    return (
      <div className="flex items-center gap-2">
        <span className="inline-flex items-center gap-1 rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs text-emerald-800">
          {pickedLabel}
          <button type="button" onClick={clearAll} aria-label="Clear rate" className="text-emerald-500 hover:text-emerald-800">
            ✕
          </button>
        </span>
      </div>
    );
  }

  // ---- supplier chosen, need a rate ----
  if (supplierId && !adding) {
    const rates = detail?.rates ?? [];
    return (
      <div className="space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1 text-xs text-neutral-700">
            {detail?.display_name ?? "…"}
          </span>
          {loadingDetail ? (
            <span className="text-xs text-neutral-400">loading rates…</span>
          ) : rates.length > 0 ? (
            <select
              className={`${inputCls} text-xs`}
              value=""
              onChange={(e) => {
                const r = rates.find((x) => x.id === e.target.value);
                if (r) chooseRate(r);
              }}
            >
              <option value="">— pick a rate —</option>
              {rates.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.meal_plan} · {r.occupancy} · ₹{Number(r.amount).toLocaleString("en-IN")}
                  {r.freshness !== "fresh" ? ` (${r.freshness})` : ""}
                </option>
              ))}
            </select>
          ) : (
            <span className="text-xs text-amber-600">no rates on file</span>
          )}
          <button type="button" onClick={() => setAdding(true)} className={btnLight}>
            + Rate
          </button>
          <button type="button" onClick={clearAll} className="text-xs text-neutral-400 underline hover:text-neutral-700">
            change supplier
          </button>
        </div>
        {error && <p className="text-xs text-red-600">{error}</p>}
      </div>
    );
  }

  // ---- inline: add a rate to the chosen supplier, or a whole new supplier ----
  if (adding) {
    return (
      <AddSupplierRate
        kind={kind}
        destinationId={destinationId}
        existing={supplierId ? detail : null}
        onCancel={() => setAdding(false)}
        onDone={(p) => {
          setAdding(false);
          setDetail(null); // force reload so the new rate shows if user clears
          onPick(p);
        }}
        onError={setError}
      />
    );
  }

  // ---- nothing chosen: search or add ----
  return (
    <div ref={ref} className="relative">
      <div className="flex items-center gap-2">
        <input
          className={`${inputCls} w-56`}
          placeholder="Find supplier / hotel…"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
        />
        <button type="button" onClick={() => setAdding(true)} className={btnLight}>
          + New supplier
        </button>
      </div>
      {open && (
        <ul className="absolute z-30 mt-1 max-h-56 w-72 overflow-auto rounded-md border border-neutral-200 bg-white text-sm shadow-lg">
          {results.length === 0 ? (
            <li className="px-3 py-2 text-xs text-neutral-400">
              No matches — use “+ New supplier”.
            </li>
          ) : (
            results.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  className="flex w-full items-center justify-between gap-3 px-3 py-1.5 text-left hover:bg-neutral-50"
                  onClick={() => chooseSupplier(s)}
                >
                  <span className="text-neutral-800">{s.display_name}</span>
                  <span className="text-xs text-neutral-400">
                    {s.destination_name ?? s.kind} · {s.rate_count} rate{s.rate_count === 1 ? "" : "s"}
                  </span>
                </button>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}

function AddSupplierRate({
  kind,
  destinationId,
  existing,
  onCancel,
  onDone,
  onError,
}: {
  kind: ComponentKind;
  destinationId: string | null;
  existing: SupplierDetail | null;
  onCancel: () => void;
  onDone: (p: RatePick) => void;
  onError: (msg: string | null) => void;
}) {
  const [name, setName] = useState(existing?.display_name ?? "");
  const [supplierKind, setSupplierKind] = useState(NEW_VENDOR_KIND[kind] ?? "misc");
  const [mealPlan, setMealPlan] = useState(kind === "stay" ? "MAP" : "EP");
  const [occupancy, setOccupancy] = useState(kind === "stay" ? "double" : "single");
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!existing && !name.trim()) {
      onError("Give the new supplier a name.");
      return;
    }
    if (amount === "" || Number(amount) < 0) {
      onError("Enter the rate amount.");
      return;
    }
    setBusy(true);
    onError(null);
    try {
      let supplierId = existing?.id;
      let supplierName = existing?.display_name ?? name.trim();
      if (!supplierId) {
        const sRes = await fetch("/api/v1/suppliers", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            kind: supplierKind,
            legal_name: name.trim(),
            display_name: name.trim(),
            destination_id: destinationId,
            status: "active",
          }),
        });
        if (!sRes.ok) {
          const d = await sRes.json().catch(() => null);
          onError(
            sRes.status === 403
              ? "You don't have permission to add suppliers."
              : typeof d?.detail === "string" ? d.detail : `Could not add supplier (${sRes.status}).`,
          );
          return;
        }
        const s = await sRes.json();
        supplierId = s.id as string;
        supplierName = s.display_name as string;
      }
      const rRes = await fetch(`/api/v1/suppliers/${supplierId}/rates`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          meal_plan: mealPlan,
          occupancy,
          amount,
          currency: "INR",
          tax_basis: "gross_of_tax",
          valid_from: today(),
          valid_to: inAYear(),
        }),
      });
      if (!rRes.ok) {
        const d = await rRes.json().catch(() => null);
        onError(
          rRes.status === 403
            ? "You don't have permission to add rates."
            : typeof d?.detail === "string" ? d.detail : `Could not add rate (${rRes.status}).`,
        );
        return;
      }
      const r = await rRes.json();
      onDone({
        supplier_id: supplierId!,
        rate_id: r.id as string,
        rate_label: `${supplierName} · ${mealPlan} · ${occupancy}`,
        rate_amount: String(amount),
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-md border border-neutral-300 bg-white p-2">
      <p className="mb-1 text-xs font-medium text-neutral-600">
        {existing ? `Add a rate to ${existing.display_name}` : "Add a new supplier & its rate"}
      </p>
      <div className="flex flex-wrap items-center gap-1.5">
        {!existing && (
          <>
            <input
              className={`${inputCls} w-40 text-xs`}
              placeholder="Supplier / hotel name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <select className={`${inputCls} text-xs`} value={supplierKind} onChange={(e) => setSupplierKind(e.target.value)}>
              {["hotel", "homestay", "transport", "guide", "activity", "meal", "facilitator", "permit", "misc"].map((k) => (
                <option key={k} value={k}>{k}</option>
              ))}
            </select>
          </>
        )}
        <select className={`${inputCls} text-xs`} value={mealPlan} onChange={(e) => setMealPlan(e.target.value)}>
          {MEAL_PLANS.map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
        <select className={`${inputCls} text-xs`} value={occupancy} onChange={(e) => setOccupancy(e.target.value)}>
          {OCCUPANCIES.map((o) => (
            <option key={o} value={o}>{o}</option>
          ))}
        </select>
        <input
          type="number"
          min={0}
          className={`${inputCls} w-24 text-xs`}
          placeholder="Amount ₹"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
        />
        <button type="button" onClick={submit} disabled={busy} className={`${btnDark} disabled:opacity-50`}>
          {busy ? "Saving…" : "Save & use"}
        </button>
        <button type="button" onClick={onCancel} className="text-xs text-neutral-400 underline hover:text-neutral-700">
          Cancel
        </button>
      </div>
    </div>
  );
}
