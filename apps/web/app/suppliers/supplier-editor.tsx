"use client";

import { useState } from "react";

import { Combobox } from "@/components/combobox";
import { ACCOMMODATION_TIERS } from "@/lib/constants";

// Vendor kinds — 1:1 with the itinerary cost kinds (owner decision 2026-08).
export const VENDOR_KINDS = [
  "stay", "transport", "guide", "activity", "meal", "permit", "misc",
];
export const SUPPLIER_KINDS = VENDOR_KINDS; // back-compat alias
export const SUPPLIER_STATUSES = ["active", "blacklisted", "contacted", "prospect"];
export const MEAL_PLANS = ["EP", "CP", "MAP", "AP", "CPAI", "MAPAI", "APAI", "CAPAI"];
// "single / double / triple" rooms + an extra-bed option (the bedding part).
export const OCCUPANCIES = ["single", "double", "triple", "extra_adult"];
export const OCCUPANCY_LABEL: Record<string, string> = {
  single: "single", double: "double", triple: "triple", extra_adult: "extra bed",
};

// Which extra rate fields a vendor kind needs (use common sense per kind):
//  • stay  → meal plan + occupancy (bedding)
//  • meal  → meal plan only
//  • everything else → just the rate (amount + validity)
export const usesMealPlan = (kind: string) => kind === "stay" || kind === "meal";
export const usesOccupancy = (kind: string) => kind === "stay";
export const ACCOMMODATION_KINDS = ["stay"];

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}
function inAYearISO(): string {
  const d = new Date();
  d.setUTCFullYear(d.getUTCFullYear() + 1);
  return d.toISOString().slice(0, 10);
}

export interface DestOption {
  id: string;
  name: string;
  state: string | null;
}

export const inputCls =
  "w-full rounded-md border border-neutral-300 bg-white px-2 py-1.5 text-sm text-neutral-900 focus:border-neutral-500 focus:outline-none";
export const btnDark =
  "inline-flex items-center rounded-md bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-neutral-800 disabled:opacity-50";
export const btnLight =
  "inline-flex items-center rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-xs font-medium text-neutral-700 hover:bg-neutral-50";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs text-neutral-500">{label}</span>
      {children}
    </label>
  );
}

/** Destination picker: type-ahead over existing cities, plus an inline creator. */
function DestinationField({
  value,
  onChange,
  destinations,
  onDestinationsChanged,
}: {
  value: string | null;
  onChange: (v: string | null) => void;
  destinations: DestOption[];
  onDestinationsChanged: () => void;
}) {
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [state, setState] = useState("");

  async function createCity() {
    if (!name.trim()) return;
    const res = await fetch("/api/v1/destinations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name.trim(), state: state.trim() || null }),
    });
    if (res.ok) {
      const d = await res.json();
      onDestinationsChanged();
      onChange(d.id);
      setAdding(false);
      setName("");
      setState("");
    }
  }

  return (
    <div>
      <Combobox
        placeholder="City…"
        value={value}
        onChange={onChange}
        options={destinations.map((d) => ({
          value: d.id,
          label: d.name,
          sublabel: d.state ?? undefined,
        }))}
      />
      {adding ? (
        <div className="mt-1 flex items-center gap-1">
          <input className={inputCls} placeholder="New city" value={name} onChange={(e) => setName(e.target.value)} />
          <input className={inputCls} placeholder="State" value={state} onChange={(e) => setState(e.target.value)} />
          <button type="button" className={btnDark} onClick={createCity}>Add</button>
          <button type="button" className="text-xs text-neutral-400" onClick={() => setAdding(false)}>✕</button>
        </div>
      ) : (
        <button type="button" className="mt-1 text-xs text-neutral-500 underline hover:text-neutral-800" onClick={() => setAdding(true)}>
          + new city
        </button>
      )}
    </div>
  );
}

export interface SupplierFormValues {
  kind: string;
  legal_name: string;
  display_name: string;
  destination_id: string | null;
  category: string;
  property_type: string;
  status: string;
  gstin: string;
  pan: string;
  notes: string;
}

export const emptySupplier: SupplierFormValues = {
  kind: "stay", legal_name: "", display_name: "", destination_id: null,
  category: "", property_type: "", status: "prospect", gstin: "", pan: "", notes: "",
};

export function SupplierForm({
  initial,
  destinations,
  onDestinationsChanged,
  onSubmit,
  onCancel,
  submitLabel,
}: {
  initial: SupplierFormValues;
  destinations: DestOption[];
  onDestinationsChanged: () => void;
  onSubmit: (body: Record<string, unknown>) => Promise<void>;
  onCancel: () => void;
  submitLabel: string;
}) {
  const [v, setV] = useState<SupplierFormValues>(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (patch: Partial<SupplierFormValues>) => setV({ ...v, ...patch });

  async function submit() {
    if (!v.display_name.trim() || !v.legal_name.trim()) {
      setError("Legal name and display name are required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await onSubmit({
        kind: v.kind,
        legal_name: v.legal_name.trim(),
        display_name: v.display_name.trim(),
        destination_id: v.destination_id,
        category: v.category.trim() || null,
        property_type: v.property_type.trim() || null,
        status: v.status,
        gstin: v.gstin.trim() || null,
        pan: v.pan.trim() || null,
        notes: v.notes.trim() || null,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-md border border-neutral-200 bg-neutral-50 p-3">
      {error && <p className="mb-2 text-xs text-red-600">{error}</p>}
      <div className="grid gap-2 sm:grid-cols-2">
        <Field label="Kind">
          <select className={inputCls} value={v.kind} onChange={(e) => set({ kind: e.target.value })}>
            {SUPPLIER_KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
          </select>
        </Field>
        <Field label="Status">
          <select className={inputCls} value={v.status} onChange={(e) => set({ status: e.target.value })}>
            {SUPPLIER_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </Field>
        <Field label="Display name">
          <input className={inputCls} value={v.display_name} onChange={(e) => set({ display_name: e.target.value })} />
        </Field>
        <Field label="Legal name">
          <input className={inputCls} value={v.legal_name} onChange={(e) => set({ legal_name: e.target.value })} />
        </Field>
        <Field label="City">
          <DestinationField
            value={v.destination_id}
            onChange={(id) => set({ destination_id: id })}
            destinations={destinations}
            onDestinationsChanged={onDestinationsChanged}
          />
        </Field>
        <Field label="Category">
          {ACCOMMODATION_KINDS.includes(v.kind) ? (
            <>
              <input
                className={inputCls}
                list="accommodation-tiers"
                placeholder="Homestays, 3 Star, 5 Star…"
                value={v.category}
                onChange={(e) => set({ category: e.target.value })}
              />
              <datalist id="accommodation-tiers">
                {ACCOMMODATION_TIERS.map((t) => <option key={t} value={t} />)}
              </datalist>
            </>
          ) : (
            <input className={inputCls} placeholder="Luxury, Mid…" value={v.category} onChange={(e) => set({ category: e.target.value })} />
          )}
        </Field>
        {ACCOMMODATION_KINDS.includes(v.kind) && (
          <Field label="Property type">
            <input className={inputCls} placeholder="Hotel, Homestay, Resort, Camp…" value={v.property_type} onChange={(e) => set({ property_type: e.target.value })} />
          </Field>
        )}
        <Field label="GSTIN">
          <input className={inputCls} value={v.gstin} onChange={(e) => set({ gstin: e.target.value })} />
        </Field>
        <label className="flex flex-col gap-1 sm:col-span-2">
          <span className="text-xs text-neutral-500">Notes</span>
          <textarea className={`${inputCls} h-16 resize-y`} value={v.notes} onChange={(e) => set({ notes: e.target.value })} />
        </label>
      </div>
      <div className="mt-3 flex gap-2">
        <button className={btnDark} disabled={busy} onClick={submit}>{busy ? "Saving…" : submitLabel}</button>
        <button className={btnLight} onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}

/** Small add-a-rate form. */
/** Kind-aware rate: amount + validity always; meal plan for stay & meal;
 *  occupancy (bedding) for stay only. Returns a field-level error to fix. */
export function AddRateForm({
  supplierId,
  kind,
  onAdded,
}: {
  supplierId: string;
  kind: string;
  onAdded: () => void;
}) {
  const [v, setV] = useState({
    meal_plan: "MAP", occupancy: "double", amount: "",
    valid_from: todayISO(), valid_to: inAYearISO(),
  });
  const [error, setError] = useState<string | null>(null);
  const set = (patch: Partial<typeof v>) => setV({ ...v, ...patch });
  const showMeal = usesMealPlan(kind);
  const showOcc = usesOccupancy(kind);

  async function add() {
    const amt = Number(v.amount);
    if (v.amount.trim() === "" || Number.isNaN(amt) || amt < 0) {
      setError("Enter the rate amount (a number in ₹).");
      return;
    }
    if (v.valid_to < v.valid_from) {
      setError("“Valid to” must be on or after “Valid from”.");
      return;
    }
    setError(null);
    const body: Record<string, unknown> = {
      amount: v.amount, valid_from: v.valid_from, valid_to: v.valid_to,
    };
    if (showMeal) body.meal_plan = v.meal_plan;
    if (showOcc) body.occupancy = v.occupancy;
    const res = await fetch(`/api/v1/suppliers/${supplierId}/rates`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (res.ok) { onAdded(); set({ amount: "" }); }
    else {
      const d = await res.json().catch(() => null);
      setError(typeof d?.detail === "string" ? d.detail : `Could not add rate (${res.status}).`);
    }
  }

  return (
    <div className="mt-2 rounded-md border border-neutral-200 bg-neutral-50 p-2 text-xs">
      {error && <p className="mb-1 text-red-600">{error}</p>}
      <div className="flex flex-wrap items-end gap-1.5">
        {showMeal && (
          <label className="flex flex-col gap-0.5">
            <span className="text-[10px] text-neutral-500">Meal plan</span>
            <select className={`${inputCls} w-20`} value={v.meal_plan} onChange={(e) => set({ meal_plan: e.target.value })}>
              {MEAL_PLANS.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </label>
        )}
        {showOcc && (
          <label className="flex flex-col gap-0.5">
            <span className="text-[10px] text-neutral-500">Occupancy</span>
            <select className={`${inputCls} w-24`} value={v.occupancy} onChange={(e) => set({ occupancy: e.target.value })}>
              {OCCUPANCIES.map((o) => <option key={o} value={o}>{OCCUPANCY_LABEL[o] ?? o}</option>)}
            </select>
          </label>
        )}
        <label className="flex flex-col gap-0.5">
          <span className="text-[10px] text-neutral-500">Amount ₹</span>
          <input className={`${inputCls} w-24`} placeholder="Amount" value={v.amount} onChange={(e) => set({ amount: e.target.value })} />
        </label>
        <label className="flex flex-col gap-0.5">
          <span className="text-[10px] text-neutral-500">Valid from</span>
          <input type="date" className={`${inputCls} w-36`} value={v.valid_from} onChange={(e) => set({ valid_from: e.target.value })} />
        </label>
        <label className="flex flex-col gap-0.5">
          <span className="text-[10px] text-neutral-500">Valid to</span>
          <input type="date" className={`${inputCls} w-36`} value={v.valid_to} onChange={(e) => set({ valid_to: e.target.value })} />
        </label>
        <button className={btnDark} onClick={add}>+ Rate</button>
      </div>
    </div>
  );
}

/** Transport rate: vehicle + basis + amount (no room type / meal plan). */
export function AddContactForm({ supplierId, onAdded }: { supplierId: string; onAdded: () => void }) {
  const [v, setV] = useState({ person_name: "", role: "", phone_raw: "", email: "" });
  const set = (patch: Partial<typeof v>) => setV({ ...v, ...patch });
  async function add() {
    if (!v.person_name.trim() && !v.email.trim() && !v.phone_raw.trim()) return;
    const res = await fetch(`/api/v1/suppliers/${supplierId}/contacts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        person_name: v.person_name.trim() || null,
        role: v.role.trim() || null,
        phone_raw: v.phone_raw.trim() || null,
        email: v.email.trim() || null,
      }),
    });
    if (res.ok) {
      onAdded();
      setV({ person_name: "", role: "", phone_raw: "", email: "" });
    }
  }
  return (
    <div className="mt-2 flex flex-wrap items-end gap-1.5 text-xs">
      <input className={`${inputCls} w-32`} placeholder="Name" value={v.person_name} onChange={(e) => set({ person_name: e.target.value })} />
      <input className={`${inputCls} w-24`} placeholder="Role" value={v.role} onChange={(e) => set({ role: e.target.value })} />
      <input className={`${inputCls} w-32`} placeholder="Phone" value={v.phone_raw} onChange={(e) => set({ phone_raw: e.target.value })} />
      <input className={`${inputCls} w-40`} placeholder="Email" value={v.email} onChange={(e) => set({ email: e.target.value })} />
      <button className={btnDark} onClick={add}>+ Contact</button>
    </div>
  );
}
