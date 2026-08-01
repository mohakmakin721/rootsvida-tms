"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import Link from "next/link";

import type {
  AllocationBasis,
  ComponentDraft,
  ComponentKind,
  DayDraft,
  DestinationFacet,
  MarkupRule,
  Occupancy,
  PaxClass,
  PreviewOut,
  SegmentDraft,
} from "@/lib/types";

import { CURRENCIES, GST_STATES, inr } from "@/lib/constants";

import { ClientIntake, type IntakeValue } from "./client-intake";
import { btnDark, btnLight, Card, Empty, Field, inputCls, Req } from "./ui";

const OCCUPANCIES: Occupancy[] = ["single", "double", "triple"];
const PAX_CLASSES: PaxClass[] = ["foreign", "indian", "saarc"];
const KINDS: ComponentKind[] = [
  "stay",
  "transport",
  "guide",
  "activity",
  "meal",
  "permit",
  "misc",
];
const ALLOCATIONS: { value: AllocationBasis; label: string }[] = [
  { value: "all_pax", label: "All travellers (shared)" },
  { value: "by_pax_class", label: "By pax class (shared)" },
  { value: "per_segment", label: "Specific groups (shared)" },
  { value: "per_pax_direct", label: "Per-pax (direct)" },
];

function nextKey(existing: SegmentDraft[]): string {
  let i = 1;
  const used = new Set(existing.map((s) => s.key));
  while (used.has(`s${i}`)) i += 1;
  return `s${i}`;
}

function addDays(iso: string, n: number): string {
  const d = new Date(iso + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

const TODAY = new Date().toISOString().slice(0, 10);

export function ItineraryBuilder({
  initialMarkupRules,
  destinations,
}: {
  initialMarkupRules: MarkupRule[];
  destinations: DestinationFacet[];
}) {
  const [markupRules, setMarkupRules] = useState<MarkupRule[]>(initialMarkupRules);
  const [intake, setIntake] = useState<IntakeValue | null>(null);
  const handleIntake = useCallback((v: IntakeValue) => setIntake(v), []);
  const [segments, setSegments] = useState<SegmentDraft[]>([]);
  const [days, setDays] = useState<DayDraft[]>([]);
  const [buyerStateCode, setBuyerStateCode] = useState("05");
  const [fxCurrency, setFxCurrency] = useState("USD");
  const [fxRate, setFxRate] = useState("");
  const [marginFloor, setMarginFloor] = useState("");

  const [preview, setPreview] = useState<PreviewOut | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [save, setSave] = useState<{
    busy: boolean;
    error: string | null;
    okId: string | null;
    okProjectId: string | null;
  }>({ busy: false, error: null, okId: null, okProjectId: null });

  // ---- segment mutations -------------------------------------------------- //
  function addSegment() {
    setSegments((prev) => {
      const key = nextKey(prev);
      const rule = markupRules[0]?.id ?? "";
      const seg: SegmentDraft = {
        key,
        label: "",
        pax_class: "foreign",
        occupancy: "double",
        pax_count: 2,
        markup_rule_id: rule,
      };
      // New segment is present on every existing day by default.
      setDays((ds) => ds.map((d) => ({ ...d, present_segment_keys: [...d.present_segment_keys, key] })));
      return [...prev, seg];
    });
  }

  function updateSegment(key: string, patch: Partial<SegmentDraft>) {
    setSegments((prev) => prev.map((s) => (s.key === key ? { ...s, ...patch } : s)));
  }

  function removeSegment(key: string) {
    setSegments((prev) => prev.filter((s) => s.key !== key));
    setDays((prev) =>
      prev.map((d) => ({
        ...d,
        present_segment_keys: d.present_segment_keys.filter((k) => k !== key),
        components: d.components.map((c) => ({
          ...c,
          applies_to_segment_keys:
            c.applies_to_segment_keys?.filter((k) => k !== key) ?? null,
        })),
      })),
    );
  }

  // ---- day mutations ------------------------------------------------------ //
  function addDay() {
    setDays((prev) => {
      const n = prev.length + 1;
      const date = prev.length
        ? addDays(prev[prev.length - 1].date, 1)
        : intake?.start_date ?? TODAY;
      const day: DayDraft = {
        day_number: n,
        date,
        destination_id: null,
        present_segment_keys: segments.map((s) => s.key),
        components: [],
      };
      return [...prev, day];
    });
  }

  function updateDay(idx: number, patch: Partial<DayDraft>) {
    setDays((prev) => prev.map((d, i) => (i === idx ? { ...d, ...patch } : d)));
  }

  function removeDay(idx: number) {
    setDays((prev) =>
      prev.filter((_, i) => i !== idx).map((d, i) => ({ ...d, day_number: i + 1 })),
    );
  }

  function togglePresence(idx: number, key: string) {
    setDays((prev) =>
      prev.map((d, i) => {
        if (i !== idx) return d;
        const has = d.present_segment_keys.includes(key);
        return {
          ...d,
          present_segment_keys: has
            ? d.present_segment_keys.filter((k) => k !== key)
            : [...d.present_segment_keys, key],
        };
      }),
    );
  }

  // ---- component mutations ------------------------------------------------ //
  function addComponent(dayIdx: number) {
    const comp: ComponentDraft = {
      kind: "misc",
      description: "",
      override_amount: "",
      override_reason: "manual entry",
      allocation: "all_pax",
      applies_to_segment_keys: null,
      applies_to_pax_class: null,
    };
    setDays((prev) =>
      prev.map((d, i) => (i === dayIdx ? { ...d, components: [...d.components, comp] } : d)),
    );
  }

  function updateComponent(dayIdx: number, compIdx: number, patch: Partial<ComponentDraft>) {
    setDays((prev) =>
      prev.map((d, i) =>
        i === dayIdx
          ? {
              ...d,
              components: d.components.map((c, j) => (j === compIdx ? { ...c, ...patch } : c)),
            }
          : d,
      ),
    );
  }

  function removeComponent(dayIdx: number, compIdx: number) {
    setDays((prev) =>
      prev.map((d, i) =>
        i === dayIdx ? { ...d, components: d.components.filter((_, j) => j !== compIdx) } : d,
      ),
    );
  }

  // ---- payload + preview -------------------------------------------------- //
  const ready =
    segments.length > 0 &&
    segments.every((s) => s.label.trim() && s.markup_rule_id && s.pax_count > 0);

  // Only the itinerary-relevant intake fields feed pricing — so typing a client
  // name or notes never re-triggers the live preview.
  const iTitle = intake?.title ?? "";
  const iStart = intake?.start_date ?? TODAY;
  const iEnd = intake?.end_date ?? addDays(TODAY, 3);

  const payload = useMemo(() => {
    const seg = segments.map((s) => ({
      key: s.key,
      label: s.label.trim() || s.key,
      pax_class: s.pax_class,
      occupancy: s.occupancy,
      pax_count: s.pax_count,
      markup_rule_id: s.markup_rule_id,
    }));
    const dayList = days.map((d) => ({
      day_number: d.day_number,
      date: d.date,
      destination_id: d.destination_id || null,
      present_segment_keys: d.present_segment_keys,
      components: d.components
        .filter((c) => c.override_amount !== "" && Number(c.override_amount) >= 0)
        .map((c) => {
          const out: Record<string, unknown> = {
            kind: c.kind,
            description: c.description || null,
            override_amount: c.override_amount,
            override_reason: c.override_reason || "manual entry",
            allocation: c.kind === "stay" ? "all_pax" : c.allocation,
          };
          if (c.kind === "stay") {
            out.applies_to_segment_keys = c.applies_to_segment_keys ?? [];
          } else if (c.allocation === "by_pax_class") {
            out.applies_to_pax_class = c.applies_to_pax_class;
          } else if (c.allocation === "per_segment" || c.allocation === "per_pax_direct") {
            out.applies_to_segment_keys = c.applies_to_segment_keys ?? [];
          }
          return out;
        }),
    }));
    return {
      itinerary: {
        title: iTitle.trim() || "Untitled itinerary",
        start_date: iStart,
        end_date: iEnd,
        generated_by: "human",
        segments: seg,
        days: dayList,
      },
      buyer_state_code: buyerStateCode || null,
      buyer_country: "IN",
      rounding: "nearest_1",
      fx_currency: fxCurrency,
      fx_rate: fxRate ? fxRate : null,
      margin_floor: marginFloor ? marginFloor : null,
    };
  }, [segments, days, iTitle, iStart, iEnd, buyerStateCode, fxCurrency, fxRate, marginFloor]);

  const runPreview = useCallback(async (body: unknown) => {
    setLoading(true);
    setPreviewError(null);
    try {
      const res = await fetch("/api/v1/pricing/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        const msg =
          typeof detail?.detail === "string"
            ? detail.detail
            : `Could not price this draft (${res.status}).`;
        setPreviewError(msg);
        return;
      }
      setPreview((await res.json()) as PreviewOut);
    } catch {
      setPreviewError("Could not reach the domain service.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!ready) {
      setPreview(null);
      return;
    }
    const t = setTimeout(() => runPreview(payload), 400);
    return () => clearTimeout(t);
  }, [ready, payload, runPreview]);

  // ---- markup rule inline creation ---------------------------------------- //
  async function createMarkupRule(label: string, basis: string, rate: string) {
    const res = await fetch("/api/v1/markup-rules", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ label, basis, rate }),
    });
    if (res.ok) {
      const rule = (await res.json()) as MarkupRule;
      setMarkupRules((prev) => [...prev, rule]);
      // Assign to any segment that has no rule yet.
      setSegments((prev) =>
        prev.map((s) => (s.markup_rule_id ? s : { ...s, markup_rule_id: rule.id })),
      );
    }
  }

  async function updateMarkupRule(id: string, patch: { label?: string; rate?: string; basis?: string }) {
    const res = await fetch(`/api/v1/markup-rules/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    if (res.ok) {
      const rule = (await res.json()) as MarkupRule;
      setMarkupRules((prev) => prev.map((r) => (r.id === id ? rule : r)));
    }
  }

  async function deleteMarkupRule(id: string): Promise<string | null> {
    const res = await fetch(`/api/v1/markup-rules/${id}`, { method: "DELETE" });
    if (res.ok) {
      setMarkupRules((prev) => prev.filter((r) => r.id !== id));
      return null;
    }
    const d = await res.json().catch(() => null);
    return typeof d?.detail === "string" ? d.detail : "Could not delete rule.";
  }

  // ---- save --------------------------------------------------------------- //
  async function resolveProjectId(v: IntakeValue): Promise<string> {
    // Continuing an existing project — no new project needed.
    if (v.project.kind === "existing") return v.project.id;

    // A new project: link an existing client, save a new one inline, or (fallback)
    // carry a bare client name.
    const projectBody: Record<string, unknown> = { code: v.project.code };
    if (v.client.kind === "existing") projectBody.client_id = v.client.id;
    else projectBody.client = v.client.data;

    const res = await fetch("/api/v1/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(projectBody),
    });
    if (!res.ok) {
      const d = await res.json().catch(() => null);
      throw new Error(
        typeof d?.detail === "string" ? d.detail : `Project create failed (${res.status}).`,
      );
    }
    return (await res.json()).id as string;
  }

  async function saveItinerary() {
    if (!intake) return;
    setSave({ busy: true, error: null, okId: null, okProjectId: null });
    try {
      const projectId = await resolveProjectId(intake);
      const itRes = await fetch(`/api/v1/projects/${projectId}/itineraries`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload.itinerary),
      });
      if (!itRes.ok) {
        const d = await itRes.json().catch(() => null);
        throw new Error(
          typeof d?.detail === "string" ? d.detail : `Itinerary create failed (${itRes.status}).`,
        );
      }
      const it = await itRes.json();
      setSave({ busy: false, error: null, okId: it.id, okProjectId: projectId });
    } catch (e) {
      setSave({ busy: false, error: e instanceof Error ? e.message : "Save failed.", okId: null, okProjectId: null });
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
      <div className="space-y-6">
        <ClientIntake onChange={handleIntake} />
        <SegmentSection
          segments={segments}
          markupRules={markupRules}
          onAdd={addSegment}
          onUpdate={updateSegment}
          onRemove={removeSegment}
          onCreateRule={createMarkupRule}
          onUpdateRule={updateMarkupRule}
          onDeleteRule={deleteMarkupRule}
        />
        <DaysSection
          days={days}
          segments={segments}
          destinations={destinations}
          onAddDay={addDay}
          onUpdateDay={updateDay}
          onRemoveDay={removeDay}
          onTogglePresence={togglePresence}
          onAddComponent={addComponent}
          onUpdateComponent={updateComponent}
          onRemoveComponent={removeComponent}
        />
      </div>

      <Sidebar
        preview={preview}
        loading={loading}
        error={previewError}
        ready={ready}
        buyerStateCode={buyerStateCode}
        setBuyerStateCode={setBuyerStateCode}
        fxCurrency={fxCurrency}
        setFxCurrency={setFxCurrency}
        fxRate={fxRate}
        setFxRate={setFxRate}
        marginFloor={marginFloor}
        setMarginFloor={setMarginFloor}
        onSave={saveItinerary}
        canSave={!!intake?.ready}
        save={save}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------- //
// sections
// ---------------------------------------------------------------------------- //

const SEGMENT_INFO = (
  <>
    Split the party into groups that share a room type and a pricing rule.
    <br />• <b>Label</b> — a name like “Foreign Double”.
    <br />• <b>Class</b> — foreign / indian / saarc; drives tax &amp; cost splits.
    <br />• <b>Occupancy</b> — single / double / triple (the room-share divisor).
    <br />• <b>Pax</b> — how many people in the group.
    <br />• <b>Markup</b> — which margin rule applies (manage rules with “Rules”).
  </>
);

function SegmentSection({
  segments,
  markupRules,
  onAdd,
  onUpdate,
  onRemove,
  onCreateRule,
  onUpdateRule,
  onDeleteRule,
}: {
  segments: SegmentDraft[];
  markupRules: MarkupRule[];
  onAdd: () => void;
  onUpdate: (key: string, patch: Partial<SegmentDraft>) => void;
  onRemove: (key: string) => void;
  onCreateRule: (label: string, basis: string, rate: string) => void;
  onUpdateRule: (id: string, patch: { label?: string; rate?: string; basis?: string }) => void;
  onDeleteRule: (id: string) => Promise<string | null>;
}) {
  const [showRules, setShowRules] = useState(false);
  return (
    <Card
      title="Traveller groups"
      info={SEGMENT_INFO}
      action={
        <div className="flex gap-2">
          <button onClick={() => setShowRules((s) => !s)} className={btnLight}>
            {showRules ? "Hide rules" : "Markup rules"}
          </button>
          <button onClick={onAdd} className={btnDark}>
            + Add group
          </button>
        </div>
      }
    >
      {(showRules || markupRules.length === 0) && (
        <MarkupRuleManager
          rules={markupRules}
          onCreate={onCreateRule}
          onUpdate={onUpdateRule}
          onDelete={onDeleteRule}
        />
      )}
      {segments.length === 0 ? (
        <Empty>Add a traveller group to begin — e.g. “Foreign Double”, 6 pax.</Empty>
      ) : (
        <>
          <div className="mb-1 grid grid-cols-12 gap-2 px-0.5 text-[10px] uppercase tracking-wide text-neutral-400">
            <span className="col-span-3">Label<Req /></span>
            <span className="col-span-2">Class<Req /></span>
            <span className="col-span-2">Occupancy<Req /></span>
            <span className="col-span-1">Pax<Req /></span>
            <span className="col-span-3">Markup<Req /></span>
            <span className="col-span-1" />
          </div>
          <div className="space-y-2">
            {segments.map((s) => (
              <div key={s.key} className="grid grid-cols-12 items-center gap-2">
                <input
                  className={`${inputCls} col-span-3`}
                  placeholder="Label"
                  value={s.label}
                  onChange={(e) => onUpdate(s.key, { label: e.target.value })}
                />
                <select className={`${inputCls} col-span-2`} value={s.pax_class} onChange={(e) => onUpdate(s.key, { pax_class: e.target.value as PaxClass })}>
                  {PAX_CLASSES.map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
                <select className={`${inputCls} col-span-2`} value={s.occupancy} onChange={(e) => onUpdate(s.key, { occupancy: e.target.value as Occupancy })}>
                  {OCCUPANCIES.map((o) => (
                    <option key={o} value={o}>{o}</option>
                  ))}
                </select>
                <input
                  type="number"
                  min={1}
                  className={`${inputCls} col-span-1`}
                  value={s.pax_count}
                  onChange={(e) => onUpdate(s.key, { pax_count: Math.max(1, Number(e.target.value)) })}
                />
                <select
                  className={`${inputCls} col-span-3 ${s.markup_rule_id ? "" : "border-red-300"}`}
                  value={s.markup_rule_id}
                  onChange={(e) => onUpdate(s.key, { markup_rule_id: e.target.value })}
                >
                  <option value="">— markup —</option>
                  {markupRules.map((r) => (
                    <option key={r.id} value={r.id}>{r.label}</option>
                  ))}
                </select>
                <button onClick={() => onRemove(s.key)} className="col-span-1 text-neutral-400 hover:text-red-600" aria-label="Remove group">
                  ✕
                </button>
              </div>
            ))}
          </div>
        </>
      )}
    </Card>
  );
}

function MarkupRuleManager({
  rules,
  onCreate,
  onUpdate,
  onDelete,
}: {
  rules: MarkupRule[];
  onCreate: (label: string, basis: string, rate: string) => void;
  onUpdate: (id: string, patch: { label?: string; rate?: string; basis?: string }) => void;
  onDelete: (id: string) => Promise<string | null>;
}) {
  const [label, setLabel] = useState("Foreign 15%");
  const [rate, setRate] = useState("0.15");
  const [basis, setBasis] = useState("markup_on_cost");
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="mb-3 rounded-md border border-neutral-200 bg-neutral-50 p-3">
      <p className="mb-2 text-xs font-medium text-neutral-600">
        Markup rules — your reusable margin policy. Rate is a fraction (0.15 = 15%).
      </p>
      {rules.length > 0 && (
        <div className="mb-2 space-y-1.5">
          {rules.map((r) => (
            <div key={r.id} className="grid grid-cols-12 items-center gap-2">
              <input
                className={`${inputCls} col-span-5`}
                value={r.label}
                onChange={(e) => onUpdate(r.id, { label: e.target.value })}
              />
              <select
                className={`${inputCls} col-span-4`}
                value={r.basis}
                onChange={(e) => onUpdate(r.id, { basis: e.target.value })}
              >
                <option value="markup_on_cost">markup on cost</option>
                <option value="margin_on_sell">margin on sell</option>
              </select>
              <input
                className={`${inputCls} col-span-2`}
                value={r.rate}
                onChange={(e) => onUpdate(r.id, { rate: e.target.value })}
              />
              <button
                onClick={async () => setError(await onDelete(r.id))}
                className="col-span-1 text-neutral-400 hover:text-red-600"
                aria-label="Delete rule"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}
      {error && <p className="mb-2 text-xs text-red-600">{error}</p>}
      <div className="flex flex-wrap items-end gap-2 border-t border-neutral-200 pt-2">
        <input className={`${inputCls} flex-1`} value={label} onChange={(e) => setLabel(e.target.value)} placeholder="New rule label" />
        <select className={inputCls} value={basis} onChange={(e) => setBasis(e.target.value)}>
          <option value="markup_on_cost">markup on cost</option>
          <option value="margin_on_sell">margin on sell</option>
        </select>
        <input className={`${inputCls} w-20`} value={rate} onChange={(e) => setRate(e.target.value)} placeholder="0.15" />
        <button className={btnDark} onClick={() => { onCreate(label, basis, rate); setError(null); }}>
          + Add rule
        </button>
      </div>
    </div>
  );
}

const DAYS_INFO = (
  <>
    One row per day of the trip.
    <br />• <b>Present</b> — tap a group to mark it away that day; a group that’s
    away doesn’t pay for that day’s hotel.
    <br />• <b>Add cost</b> — a stay (room rate), transport, guide, tickets, etc.
    <br />• <b>Allocation</b> — “all travellers” splits across everyone; “by pax
    class” within one class; “specific groups” across the ones you pick; “per-pax”
    is a per-person amount.
    <br />A <b>stay</b> must apply to groups sharing one occupancy (single room →
    single group; double room → the double groups).
  </>
);

function DaysSection({
  days,
  segments,
  destinations,
  onAddDay,
  onUpdateDay,
  onRemoveDay,
  onTogglePresence,
  onAddComponent,
  onUpdateComponent,
  onRemoveComponent,
}: {
  days: DayDraft[];
  segments: SegmentDraft[];
  destinations: DestinationFacet[];
  onAddDay: () => void;
  onUpdateDay: (idx: number, patch: Partial<DayDraft>) => void;
  onRemoveDay: (idx: number) => void;
  onTogglePresence: (idx: number, key: string) => void;
  onAddComponent: (idx: number) => void;
  onUpdateComponent: (dayIdx: number, compIdx: number, patch: Partial<ComponentDraft>) => void;
  onRemoveComponent: (dayIdx: number, compIdx: number) => void;
}) {
  return (
    <Card
      title="Days"
      info={DAYS_INFO}
      action={
        <button onClick={onAddDay} className={btnDark}>
          + Add day
        </button>
      }
    >
      {days.length === 0 ? (
        <Empty>Add days, mark who’s present, then add costs to each day.</Empty>
      ) : (
        <div className="space-y-4">
          {days.map((d, idx) => (
            <div key={idx} className="rounded-md border border-neutral-200 p-3">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <span className="rounded bg-neutral-900 px-2 py-1 text-xs font-medium text-white">
                  Day {d.day_number}
                </span>
                <input
                  type="date"
                  className={`${inputCls} w-40`}
                  value={d.date}
                  onChange={(e) => onUpdateDay(idx, { date: e.target.value })}
                />
                <select
                  className={`${inputCls} w-44`}
                  value={d.destination_id ?? ""}
                  onChange={(e) => onUpdateDay(idx, { destination_id: e.target.value || null })}
                >
                  <option value="">— destination —</option>
                  {destinations.map((dest) => (
                    <option key={dest.id} value={dest.id}>{dest.name}</option>
                  ))}
                </select>
                <button onClick={() => onRemoveDay(idx)} className="ml-auto text-neutral-400 hover:text-red-600" aria-label="Remove day">
                  ✕
                </button>
              </div>

              {segments.length > 0 && (
                <div className="mb-2 flex flex-wrap gap-2">
                  <span className="text-xs text-neutral-500">Present:</span>
                  {segments.map((s) => {
                    const on = d.present_segment_keys.includes(s.key);
                    return (
                      <button
                        key={s.key}
                        onClick={() => onTogglePresence(idx, s.key)}
                        className={`rounded-full px-2 py-0.5 text-xs ${
                          on
                            ? "bg-emerald-100 text-emerald-800"
                            : "bg-neutral-100 text-neutral-400 line-through"
                        }`}
                      >
                        {s.label.trim() || s.key}
                      </button>
                    );
                  })}
                </div>
              )}

              <div className="space-y-2">
                {d.components.map((c, cIdx) => (
                  <ComponentRow
                    key={cIdx}
                    comp={c}
                    segments={segments}
                    onUpdate={(patch) => onUpdateComponent(idx, cIdx, patch)}
                    onRemove={() => onRemoveComponent(idx, cIdx)}
                  />
                ))}
              </div>
              <button onClick={() => onAddComponent(idx)} className="mt-2 text-xs font-medium text-neutral-600 hover:text-neutral-900">
                + Add cost
              </button>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function ComponentRow({
  comp,
  segments,
  onUpdate,
  onRemove,
}: {
  comp: ComponentDraft;
  segments: SegmentDraft[];
  onUpdate: (patch: Partial<ComponentDraft>) => void;
  onRemove: () => void;
}) {
  const isStay = comp.kind === "stay";
  const needsSegments =
    isStay || comp.allocation === "per_segment" || comp.allocation === "per_pax_direct";
  const selected = comp.applies_to_segment_keys ?? [];

  return (
    <div className="rounded border border-neutral-200 bg-neutral-50 p-2">
      <div className="flex flex-wrap items-center gap-2">
        <select
          className={`${inputCls} w-28`}
          value={comp.kind}
          onChange={(e) => onUpdate({ kind: e.target.value as ComponentKind })}
        >
          {KINDS.map((k) => (
            <option key={k} value={k}>{k}</option>
          ))}
        </select>
        <input
          className={`${inputCls} flex-1`}
          placeholder="Description"
          value={comp.description}
          onChange={(e) => onUpdate({ description: e.target.value })}
        />
        <input
          type="number"
          min={0}
          className={`${inputCls} w-28`}
          placeholder="Amount ₹"
          value={comp.override_amount}
          onChange={(e) => onUpdate({ override_amount: e.target.value })}
        />
        {!isStay && (
          <select
            className={`${inputCls} w-48`}
            value={comp.allocation}
            onChange={(e) => onUpdate({ allocation: e.target.value as AllocationBasis })}
          >
            {ALLOCATIONS.map((a) => (
              <option key={a.value} value={a.value}>{a.label}</option>
            ))}
          </select>
        )}
        <button onClick={onRemove} className="text-neutral-400 hover:text-red-600" aria-label="Remove cost">
          ✕
        </button>
      </div>

      {isStay && (
        <p className="mt-1 text-xs text-neutral-500">
          Room rate for the selected group(s). Pick groups that share one occupancy.
        </p>
      )}

      {!isStay && comp.allocation === "by_pax_class" && (
        <div className="mt-2">
          <select
            className={`${inputCls} w-40`}
            value={comp.applies_to_pax_class ?? ""}
            onChange={(e) => onUpdate({ applies_to_pax_class: (e.target.value || null) as PaxClass | null })}
          >
            <option value="">— pax class —</option>
            {PAX_CLASSES.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>
      )}

      {needsSegments && segments.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {segments.map((s) => {
            const on = selected.includes(s.key);
            return (
              <button
                key={s.key}
                onClick={() =>
                  onUpdate({
                    applies_to_segment_keys: on
                      ? selected.filter((k) => k !== s.key)
                      : [...selected, s.key],
                  })
                }
                className={`rounded-full px-2 py-0.5 text-xs ${
                  on ? "bg-neutral-800 text-white" : "bg-neutral-200 text-neutral-500"
                }`}
              >
                {s.label.trim() || s.key}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------- //
// live cost sidebar
// ---------------------------------------------------------------------------- //

function Sidebar({
  preview,
  loading,
  error,
  ready,
  buyerStateCode,
  setBuyerStateCode,
  fxCurrency,
  setFxCurrency,
  fxRate,
  setFxRate,
  marginFloor,
  setMarginFloor,
  onSave,
  canSave,
  save,
}: {
  preview: PreviewOut | null;
  loading: boolean;
  error: string | null;
  ready: boolean;
  buyerStateCode: string;
  setBuyerStateCode: (v: string) => void;
  fxCurrency: string;
  setFxCurrency: (v: string) => void;
  fxRate: string;
  setFxRate: (v: string) => void;
  marginFloor: string;
  setMarginFloor: (v: string) => void;
  onSave: () => void;
  canSave: boolean;
  save: { busy: boolean; error: string | null; okId: string | null; okProjectId: string | null };
}) {
  return (
    <aside className="lg:sticky lg:top-6 h-fit space-y-3">
      <div className="rounded-lg border border-neutral-200 bg-white p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-neutral-800">Live pricing</h2>
          {loading && <span className="text-xs text-neutral-400">pricing…</span>}
        </div>

        <div className="mb-3 space-y-2">
          <Field label="Buyer’s state (sets GST)">
            <select className={inputCls} value={buyerStateCode} onChange={(e) => setBuyerStateCode(e.target.value)}>
              {GST_STATES.map((s) => (
                <option key={s.code} value={s.code}>
                  {s.code} — {s.name}
                  {s.code === "05" ? " (same as seller)" : ""}
                </option>
              ))}
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-2">
            <Field label="Quote currency">
              <select className={inputCls} value={fxCurrency} onChange={(e) => setFxCurrency(e.target.value)}>
                {CURRENCIES.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </Field>
            <Field label={`₹ per 1 ${fxCurrency}`}>
              <input className={inputCls} value={fxRate} onChange={(e) => setFxRate(e.target.value)} placeholder="95" />
            </Field>
          </div>
          <Field label="Minimum margin (fraction, e.g. 0.10)">
            <input className={inputCls} value={marginFloor} onChange={(e) => setMarginFloor(e.target.value)} placeholder="0.10" />
          </Field>
        </div>

        {!ready ? (
          <Empty>Add at least one traveller group (with a markup rule) to see pricing.</Empty>
        ) : error ? (
          <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{error}</p>
        ) : preview ? (
          <>
            <dl className="space-y-1.5 text-sm">
              {preview.segments.map((s) => (
                <div key={s.label} className="flex items-baseline justify-between">
                  <dt className="text-neutral-600">
                    {s.label} <span className="text-neutral-400">×{s.pax}</span>
                  </dt>
                  <dd className="font-medium text-neutral-900">{inr(s.sell_per_pax)}</dd>
                </div>
              ))}
            </dl>
            <hr className="my-3 border-neutral-100" />
            <dl className="space-y-1.5 text-sm">
              <Row label="Group total" value={inr(preview.group_total)} strong />
              <Row label="Total cost" value={inr(preview.total_cost)} />
              <Row label="Profit" value={inr(preview.profit)} />
              <Row
                label="Margin"
                value={`${preview.margin_pct}%`}
                tone={preview.below_floor ? "warn" : undefined}
              />
              <Row label={`GST (${preview.gst_treatment})`} value={`${preview.gst_rate}%`} />
              {preview.fx &&
                Object.entries(preview.fx).map(([cur, v]) => (
                  <Row key={cur} label={`≈ in ${cur}`} value={`${cur} ${Number(v).toLocaleString()}`} strong />
                ))}
            </dl>
            {preview.below_floor && (
              <p className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-2 py-1.5 text-xs text-amber-800">
                Margin is below the {preview.margin_floor}% floor — a quote would be blocked
                until an owner overrides it.
              </p>
            )}
          </>
        ) : (
          <Empty>Pricing…</Empty>
        )}
      </div>

      <div className="rounded-lg border border-neutral-200 bg-white p-4">
        <button onClick={onSave} disabled={!ready || !canSave || save.busy} className={`${btnDark} w-full justify-center disabled:opacity-50`}>
          {save.busy ? "Saving…" : "Save itinerary"}
        </button>
        {!canSave && (
          <p className="mt-2 text-xs text-neutral-400">
            Fill the required client &amp; project fields (marked <span className="text-red-500">*</span>) to save.
          </p>
        )}
        {save.error && <p className="mt-2 text-xs text-red-700">{save.error}</p>}
        {save.okId && save.okProjectId && (
          <div className="mt-2 rounded-md border border-emerald-200 bg-emerald-50 px-2 py-2 text-xs text-emerald-800">
            <p>Saved and stored under its project.</p>
            <Link href={`/projects/${save.okProjectId}`} className="mt-1 inline-block font-medium underline hover:text-emerald-900">
              Open project &amp; create a quote →
            </Link>
          </div>
        )}
      </div>
    </aside>
  );
}

function Row({ label, value, strong, tone }: { label: string; value: string; strong?: boolean; tone?: "warn" }) {
  return (
    <div className="flex items-baseline justify-between">
      <dt className={strong ? "font-medium text-neutral-800" : "text-neutral-600"}>{label}</dt>
      <dd
        className={`${strong ? "text-base font-semibold" : "font-medium"} ${
          tone === "warn" ? "text-amber-700" : "text-neutral-900"
        }`}
      >
        {value}
      </dd>
    </div>
  );
}
