"use client";

import { useState } from "react";

import { Combobox } from "@/components/combobox";

// Ascending, tidy pickers.
export const SUPPLIER_KINDS = [
  "activity", "facilitator", "guide", "homestay", "hotel", "meal", "misc", "permit",
  "photographer", "transport",
];
export const SUPPLIER_STATUSES = ["active", "blacklisted", "contacted", "prospect"];
export const MEAL_PLANS = ["AP", "APAI", "CAPAI", "CP", "CPAI", "EP", "MAP", "MAPAI"];
export const OCCUPANCIES = ["double", "single", "triple"];
export const TAX_BASES = ["gross_of_tax", "net_of_tax", "plus_percent"];
export const TRANSPORT_BASES = [
  "per_day_8hr_80km", "per_km", "per_transfer", "per_extra_hour", "per_day_12hr", "fixed_route",
];
export const PAX_CLASSES = ["foreign", "indian"];

// Vendor kinds that use hotel-style data (room types, meal-plan/occupancy rates).
export const HOTEL_KINDS = ["hotel", "homestay"];

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
  kind: "hotel", legal_name: "", display_name: "", destination_id: null,
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
          <input className={inputCls} placeholder="Luxury, Mid…" value={v.category} onChange={(e) => set({ category: e.target.value })} />
        </Field>
        {HOTEL_KINDS.includes(v.kind) && (
          <Field label="Property type">
            <input className={inputCls} placeholder="Heritage, Resort…" value={v.property_type} onChange={(e) => set({ property_type: e.target.value })} />
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
export function AddRateForm({
  supplierId,
  roomTypes,
  onAdded,
}: {
  supplierId: string;
  roomTypes: { id: string; name: string }[];
  onAdded: () => void;
}) {
  const today = new Date().toISOString().slice(0, 10);
  const [v, setV] = useState({
    room_type_id: "", meal_plan: "CP", occupancy: "double", amount: "",
    currency: "INR", valid_from: today, valid_to: today, min_nights: "1",
  });
  const [error, setError] = useState<string | null>(null);
  const set = (patch: Partial<typeof v>) => setV({ ...v, ...patch });

  async function add() {
    if (!v.amount) {
      setError("Enter an amount.");
      return;
    }
    setError(null);
    const res = await fetch(`/api/v1/suppliers/${supplierId}/rates`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        room_type_id: v.room_type_id || null,
        meal_plan: v.meal_plan,
        occupancy: v.occupancy,
        amount: v.amount,
        currency: v.currency,
        valid_from: v.valid_from,
        valid_to: v.valid_to,
        min_nights: Number(v.min_nights) || 1,
      }),
    });
    if (res.ok) {
      onAdded();
      set({ amount: "" });
    } else {
      const d = await res.json().catch(() => null);
      setError(typeof d?.detail === "string" ? d.detail : `Could not add rate (${res.status}).`);
    }
  }

  return (
    <div className="mt-2 rounded-md border border-neutral-200 bg-neutral-50 p-2 text-xs">
      {error && <p className="mb-1 text-red-600">{error}</p>}
      <div className="flex flex-wrap items-end gap-1.5">
        <select className={`${inputCls} w-28`} value={v.room_type_id} onChange={(e) => set({ room_type_id: e.target.value })}>
          <option value="">no room type</option>
          {roomTypes.map((rt) => <option key={rt.id} value={rt.id}>{rt.name}</option>)}
        </select>
        <select className={`${inputCls} w-20`} value={v.meal_plan} onChange={(e) => set({ meal_plan: e.target.value })}>
          {MEAL_PLANS.map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
        <select className={`${inputCls} w-24`} value={v.occupancy} onChange={(e) => set({ occupancy: e.target.value })}>
          {OCCUPANCIES.map((o) => <option key={o} value={o}>{o}</option>)}
        </select>
        <input className={`${inputCls} w-24`} placeholder="Amount" value={v.amount} onChange={(e) => set({ amount: e.target.value })} />
        <input type="date" className={`${inputCls} w-36`} value={v.valid_from} onChange={(e) => set({ valid_from: e.target.value })} />
        <input type="date" className={`${inputCls} w-36`} value={v.valid_to} onChange={(e) => set({ valid_to: e.target.value })} />
        <button className={btnDark} onClick={add}>+ Rate</button>
      </div>
    </div>
  );
}

/** Add-a-room-type inline. */
export function AddRoomTypeForm({ supplierId, onAdded }: { supplierId: string; onAdded: () => void }) {
  const [name, setName] = useState("");
  async function add() {
    if (!name.trim()) return;
    const res = await fetch(`/api/v1/suppliers/${supplierId}/room-types`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name.trim() }),
    });
    if (res.ok) {
      onAdded();
      setName("");
    }
  }
  return (
    <div className="mt-2 flex items-center gap-1.5">
      <input className={`${inputCls} w-40`} placeholder="Room type (e.g. Suite)" value={name} onChange={(e) => setName(e.target.value)} />
      <button className={btnDark} onClick={add}>+ Room type</button>
    </div>
  );
}

/** Transport rate: vehicle + basis + amount (no room type / meal plan). */
export function AddTransportRateForm({ supplierId, onAdded }: { supplierId: string; onAdded: () => void }) {
  const [v, setV] = useState({
    vehicle_class: "", vehicle_model: "", seats: "", basis: "per_day_8hr_80km",
    amount: "", valid_from: todayISO(), valid_to: inAYearISO(),
  });
  const [error, setError] = useState<string | null>(null);
  const set = (patch: Partial<typeof v>) => setV({ ...v, ...patch });
  async function add() {
    if (!v.vehicle_class.trim() || !v.amount) { setError("Vehicle class and amount are required."); return; }
    setError(null);
    const res = await fetch(`/api/v1/suppliers/${supplierId}/transport-rates`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        vehicle_class: v.vehicle_class.trim(), vehicle_model: v.vehicle_model.trim() || null,
        seats: v.seats ? Number(v.seats) : null, basis: v.basis, amount: v.amount,
        valid_from: v.valid_from, valid_to: v.valid_to,
      }),
    });
    if (res.ok) { onAdded(); set({ amount: "", vehicle_class: "", vehicle_model: "", seats: "" }); }
    else { const d = await res.json().catch(() => null); setError(typeof d?.detail === "string" ? d.detail : `Could not add rate (${res.status}).`); }
  }
  return (
    <div className="mt-2 rounded-md border border-neutral-200 bg-neutral-50 p-2 text-xs">
      {error && <p className="mb-1 text-red-600">{error}</p>}
      <div className="flex flex-wrap items-end gap-1.5">
        <input className={`${inputCls} w-28`} placeholder="Class (Sedan/SUV)" value={v.vehicle_class} onChange={(e) => set({ vehicle_class: e.target.value })} />
        <input className={`${inputCls} w-28`} placeholder="Model (Innova…)" value={v.vehicle_model} onChange={(e) => set({ vehicle_model: e.target.value })} />
        <input className={`${inputCls} w-16`} placeholder="Seats" value={v.seats} onChange={(e) => set({ seats: e.target.value })} />
        <select className={`${inputCls} w-40`} value={v.basis} onChange={(e) => set({ basis: e.target.value })}>
          {TRANSPORT_BASES.map((b) => <option key={b} value={b}>{b}</option>)}
        </select>
        <input className={`${inputCls} w-24`} placeholder="Amount" value={v.amount} onChange={(e) => set({ amount: e.target.value })} />
        <input type="date" className={`${inputCls} w-36`} value={v.valid_from} onChange={(e) => set({ valid_from: e.target.value })} />
        <input type="date" className={`${inputCls} w-36`} value={v.valid_to} onChange={(e) => set({ valid_to: e.target.value })} />
        <button className={btnDark} onClick={add}>+ Rate</button>
      </div>
    </div>
  );
}

/** Guide rate: languages + per-day / per-half-day (no room type / meal plan). */
export function AddGuideRateForm({ supplierId, onAdded }: { supplierId: string; onAdded: () => void }) {
  const [v, setV] = useState({
    languages: "", per_day: "", per_half_day: "", specialisation: "",
    valid_from: todayISO(), valid_to: inAYearISO(),
  });
  const [error, setError] = useState<string | null>(null);
  const set = (patch: Partial<typeof v>) => setV({ ...v, ...patch });
  async function add() {
    if (!v.per_day && !v.per_half_day) { setError("Enter a per-day or per-half-day rate."); return; }
    setError(null);
    const res = await fetch(`/api/v1/suppliers/${supplierId}/guide-rates`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        languages: v.languages.split(",").map((s) => s.trim()).filter(Boolean),
        per_day: v.per_day || null, per_half_day: v.per_half_day || null,
        specialisation: v.specialisation.trim() || null,
        valid_from: v.valid_from, valid_to: v.valid_to,
      }),
    });
    if (res.ok) { onAdded(); set({ per_day: "", per_half_day: "", specialisation: "" }); }
    else { const d = await res.json().catch(() => null); setError(typeof d?.detail === "string" ? d.detail : `Could not add rate (${res.status}).`); }
  }
  return (
    <div className="mt-2 rounded-md border border-neutral-200 bg-neutral-50 p-2 text-xs">
      {error && <p className="mb-1 text-red-600">{error}</p>}
      <div className="flex flex-wrap items-end gap-1.5">
        <input className={`${inputCls} w-40`} placeholder="Languages (comma-sep)" value={v.languages} onChange={(e) => set({ languages: e.target.value })} />
        <input className={`${inputCls} w-24`} placeholder="Per day ₹" value={v.per_day} onChange={(e) => set({ per_day: e.target.value })} />
        <input className={`${inputCls} w-24`} placeholder="Per half-day" value={v.per_half_day} onChange={(e) => set({ per_half_day: e.target.value })} />
        <input className={`${inputCls} w-32`} placeholder="Specialisation" value={v.specialisation} onChange={(e) => set({ specialisation: e.target.value })} />
        <input type="date" className={`${inputCls} w-36`} value={v.valid_from} onChange={(e) => set({ valid_from: e.target.value })} />
        <input type="date" className={`${inputCls} w-36`} value={v.valid_to} onChange={(e) => set({ valid_to: e.target.value })} />
        <button className={btnDark} onClick={add}>+ Rate</button>
      </div>
    </div>
  );
}

/** Activity rate: per-pax by nationality (Indian vs foreign), optional child price. */
export function AddActivityRateForm({ supplierId, onAdded }: { supplierId: string; onAdded: () => void }) {
  const [v, setV] = useState({
    name: "", pax_class: "foreign", price_per_pax: "", child_price: "",
    valid_from: todayISO(), valid_to: inAYearISO(),
  });
  const [error, setError] = useState<string | null>(null);
  const set = (patch: Partial<typeof v>) => setV({ ...v, ...patch });
  async function add() {
    if (!v.name.trim() || !v.price_per_pax) { setError("Name and price per pax are required."); return; }
    setError(null);
    const res = await fetch(`/api/v1/suppliers/${supplierId}/activity-rates`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: v.name.trim(), pax_class: v.pax_class, price_per_pax: v.price_per_pax,
        child_price: v.child_price || null, valid_from: v.valid_from, valid_to: v.valid_to,
      }),
    });
    if (res.ok) { onAdded(); set({ name: "", price_per_pax: "", child_price: "" }); }
    else { const d = await res.json().catch(() => null); setError(typeof d?.detail === "string" ? d.detail : `Could not add rate (${res.status}).`); }
  }
  return (
    <div className="mt-2 rounded-md border border-neutral-200 bg-neutral-50 p-2 text-xs">
      {error && <p className="mb-1 text-red-600">{error}</p>}
      <div className="flex flex-wrap items-end gap-1.5">
        <input className={`${inputCls} w-40`} placeholder="Activity (Amber Fort…)" value={v.name} onChange={(e) => set({ name: e.target.value })} />
        <select className={`${inputCls} w-24`} value={v.pax_class} onChange={(e) => set({ pax_class: e.target.value })}>
          {PAX_CLASSES.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <input className={`${inputCls} w-24`} placeholder="Per pax ₹" value={v.price_per_pax} onChange={(e) => set({ price_per_pax: e.target.value })} />
        <input className={`${inputCls} w-24`} placeholder="Child ₹" value={v.child_price} onChange={(e) => set({ child_price: e.target.value })} />
        <input type="date" className={`${inputCls} w-36`} value={v.valid_from} onChange={(e) => set({ valid_from: e.target.value })} />
        <input type="date" className={`${inputCls} w-36`} value={v.valid_to} onChange={(e) => set({ valid_to: e.target.value })} />
        <button className={btnDark} onClick={add}>+ Rate</button>
      </div>
    </div>
  );
}

/** Add-a-contact inline. */
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
