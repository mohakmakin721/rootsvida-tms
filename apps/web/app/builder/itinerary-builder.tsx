"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

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

function inr(v: string | number): string {
  const n = typeof v === "string" ? Number(v) : v;
  return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
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
  const [meta, setMeta] = useState({
    client_name: "",
    client_country: "",
    code: "",
    title: "",
    start_date: TODAY,
    end_date: addDays(TODAY, 3),
  });
  const [segments, setSegments] = useState<SegmentDraft[]>([]);
  const [days, setDays] = useState<DayDraft[]>([]);
  const [buyerStateCode, setBuyerStateCode] = useState("05");
  const [fx, setFx] = useState("");
  const [marginFloor, setMarginFloor] = useState("");

  const [preview, setPreview] = useState<PreviewOut | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [save, setSave] = useState<{ busy: boolean; error: string | null; okId: string | null }>(
    { busy: false, error: null, okId: null },
  );

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
      const date = prev.length ? addDays(prev[prev.length - 1].date, 1) : meta.start_date;
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
        title: meta.title.trim() || "Untitled itinerary",
        start_date: meta.start_date,
        end_date: meta.end_date,
        generated_by: "human",
        segments: seg,
        days: dayList,
      },
      buyer_state_code: buyerStateCode || null,
      buyer_country: "IN",
      rounding: "nearest_1",
      fx_inr_per_usd: fx ? fx : null,
      margin_floor: marginFloor ? marginFloor : null,
    };
  }, [segments, days, meta, buyerStateCode, fx, marginFloor]);

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

  // ---- save --------------------------------------------------------------- //
  async function saveItinerary() {
    setSave({ busy: true, error: null, okId: null });
    try {
      const projRes = await fetch("/api/v1/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: meta.code.trim() || `TP-${Date.now().toString().slice(-6)}`,
          client_name: meta.client_name.trim() || "(unnamed client)",
          client_country: meta.client_country.trim() || null,
        }),
      });
      if (!projRes.ok) {
        const d = await projRes.json().catch(() => null);
        throw new Error(d?.detail ?? `Project create failed (${projRes.status}).`);
      }
      const project = await projRes.json();
      const itRes = await fetch(`/api/v1/projects/${project.id}/itineraries`, {
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
      setSave({ busy: false, error: null, okId: it.id });
    } catch (e) {
      setSave({ busy: false, error: e instanceof Error ? e.message : "Save failed.", okId: null });
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
      <div className="space-y-6">
        <ProjectMeta meta={meta} setMeta={setMeta} />
        <SegmentSection
          segments={segments}
          markupRules={markupRules}
          onAdd={addSegment}
          onUpdate={updateSegment}
          onRemove={removeSegment}
          onCreateRule={createMarkupRule}
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
        fx={fx}
        setFx={setFx}
        marginFloor={marginFloor}
        setMarginFloor={setMarginFloor}
        onSave={saveItinerary}
        save={save}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------- //
// sections
// ---------------------------------------------------------------------------- //

function Card({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-neutral-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-neutral-800">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function ProjectMeta({
  meta,
  setMeta,
}: {
  meta: { client_name: string; client_country: string; code: string; title: string; start_date: string; end_date: string };
  setMeta: (m: typeof meta) => void;
}) {
  const set = (patch: Partial<typeof meta>) => setMeta({ ...meta, ...patch });
  return (
    <Card title="Project">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Client name">
          <input className={inputCls} value={meta.client_name} onChange={(e) => set({ client_name: e.target.value })} />
        </Field>
        <Field label="Project code">
          <input className={inputCls} placeholder="TP-…" value={meta.code} onChange={(e) => set({ code: e.target.value })} />
        </Field>
        <Field label="Itinerary title">
          <input className={inputCls} value={meta.title} onChange={(e) => set({ title: e.target.value })} />
        </Field>
        <Field label="Client country (ISO-2)">
          <input className={inputCls} placeholder="IN, US, CL…" value={meta.client_country} onChange={(e) => set({ client_country: e.target.value })} />
        </Field>
        <Field label="Start date">
          <input type="date" className={inputCls} value={meta.start_date} onChange={(e) => set({ start_date: e.target.value })} />
        </Field>
        <Field label="End date">
          <input type="date" className={inputCls} value={meta.end_date} onChange={(e) => set({ end_date: e.target.value })} />
        </Field>
      </div>
    </Card>
  );
}

function SegmentSection({
  segments,
  markupRules,
  onAdd,
  onUpdate,
  onRemove,
  onCreateRule,
}: {
  segments: SegmentDraft[];
  markupRules: MarkupRule[];
  onAdd: () => void;
  onUpdate: (key: string, patch: Partial<SegmentDraft>) => void;
  onRemove: (key: string) => void;
  onCreateRule: (label: string, basis: string, rate: string) => void;
}) {
  return (
    <Card
      title="Traveller groups"
      action={
        <button onClick={onAdd} className={btnDark}>
          + Add group
        </button>
      }
    >
      {markupRules.length === 0 && <MarkupRuleCreator onCreate={onCreateRule} />}
      {segments.length === 0 ? (
        <Empty>Add a traveller group to begin — e.g. “Foreign Double”, 6 pax.</Empty>
      ) : (
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
                className={`${inputCls} col-span-3`}
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
      )}
    </Card>
  );
}

function MarkupRuleCreator({ onCreate }: { onCreate: (label: string, basis: string, rate: string) => void }) {
  const [label, setLabel] = useState("Foreign 15%");
  const [rate, setRate] = useState("0.15");
  const [basis, setBasis] = useState("markup_on_cost");
  return (
    <div className="mb-3 rounded-md border border-amber-200 bg-amber-50 p-3">
      <p className="mb-2 text-xs text-amber-800">
        No markup rules yet — create one so groups can be priced.
      </p>
      <div className="flex flex-wrap items-end gap-2">
        <input className={inputCls} value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Label" />
        <select className={inputCls} value={basis} onChange={(e) => setBasis(e.target.value)}>
          <option value="markup_on_cost">markup on cost</option>
          <option value="margin_on_sell">margin on sell</option>
        </select>
        <input className={`${inputCls} w-24`} value={rate} onChange={(e) => setRate(e.target.value)} placeholder="0.15" />
        <button className={btnDark} onClick={() => onCreate(label, basis, rate)}>
          Create rule
        </button>
      </div>
    </div>
  );
}

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
  fx,
  setFx,
  marginFloor,
  setMarginFloor,
  onSave,
  save,
}: {
  preview: PreviewOut | null;
  loading: boolean;
  error: string | null;
  ready: boolean;
  buyerStateCode: string;
  setBuyerStateCode: (v: string) => void;
  fx: string;
  setFx: (v: string) => void;
  marginFloor: string;
  setMarginFloor: (v: string) => void;
  onSave: () => void;
  save: { busy: boolean; error: string | null; okId: string | null };
}) {
  return (
    <aside className="lg:sticky lg:top-6 h-fit space-y-3">
      <div className="rounded-lg border border-neutral-200 bg-white p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-neutral-800">Live pricing</h2>
          {loading && <span className="text-xs text-neutral-400">pricing…</span>}
        </div>

        <div className="mb-3 grid grid-cols-3 gap-2">
          <Field label="Buyer state">
            <input className={inputCls} value={buyerStateCode} onChange={(e) => setBuyerStateCode(e.target.value)} placeholder="05" />
          </Field>
          <Field label="FX ₹/USD">
            <input className={inputCls} value={fx} onChange={(e) => setFx(e.target.value)} placeholder="95" />
          </Field>
          <Field label="Floor %">
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
                  <Row key={cur} label={`≈ ${cur}`} value={`${cur} ${Number(v).toLocaleString()}`} />
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
        <button onClick={onSave} disabled={!ready || save.busy} className={`${btnDark} w-full justify-center disabled:opacity-50`}>
          {save.busy ? "Saving…" : "Save itinerary"}
        </button>
        {save.error && <p className="mt-2 text-xs text-red-700">{save.error}</p>}
        {save.okId && (
          <p className="mt-2 rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1.5 text-xs text-emerald-800">
            Saved. Itinerary <code>{save.okId.slice(0, 8)}</code> created — quote it from
            the API (<code>POST /itineraries/{save.okId.slice(0, 8)}…/quotes</code>).
          </p>
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

// ---------------------------------------------------------------------------- //
// tiny shared bits
// ---------------------------------------------------------------------------- //

const inputCls =
  "rounded-md border border-neutral-300 bg-white px-2 py-1.5 text-sm focus:border-neutral-500 focus:outline-none";
const btnDark =
  "inline-flex rounded-md bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-neutral-800";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs text-neutral-500">{label}</span>
      {children}
    </label>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-md border border-dashed border-neutral-200 px-3 py-3 text-xs text-neutral-400">
      {children}
    </p>
  );
}
