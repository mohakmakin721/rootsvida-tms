"use client";

import { useEffect, useState } from "react";

import { ACCOMMODATION_TIERS } from "@/lib/constants";
import type { AiItineraryDraft, IntakeParse, SuggestResult } from "@/lib/types";

const THEME_OPTIONS = [
  "Leisure & Sightseeing", "Family-friendly", "Wellness & De-stress", "Adventure",
  "Honeymoon / Romantic", "Leadership Workshop", "Annual Offsite Meeting",
  "Yoga and Wellness", "Festival", "Work from Holiday Destination",
  "Trekking and Hiking", "Training Program", "Team Building",
];
const TIER_OPTIONS = ACCOMMODATION_TIERS;
const AGE_OPTIONS = ["18-24", "25-40", "40 and above"];
const TRANSPORT_OPTIONS = ["Flights", "Trains", "Car", "Tempo Traveler"];

const WEIGHT_LABELS: Record<string, string> = {
  experience_match: "Experience match", comfort: "Comfort / tier",
  budget_fit: "Budget fit", pace: "Pace", proximity: "Proximity",
  seasonality: "Seasonality", authenticity: "Authenticity", logistics: "Logistics",
};

function toggle(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

export function AiSuggestions({
  defaultDays,
  defaultGroupSize,
  defaultDestination = "",
  defaultOrigin = "",
  notes = "",
  onNotesChange,
  segments = [],
  onApply,
}: {
  defaultDays?: number;
  defaultGroupSize?: number;
  defaultDestination?: string;
  defaultOrigin?: string;
  notes?: string;
  onNotesChange?: (v: string) => void;
  segments?: { pax_class: string; occupancy: string; pax_count: number }[];
  onApply: (draft: AiItineraryDraft) => void;
}) {
  const [open, setOpen] = useState(false);
  const [destination, setDestination] = useState(defaultDestination);
  const [origin, setOrigin] = useState(defaultOrigin);

  // Prefill destination/origin from the intake above when it provides them (without
  // wiping a value the user typed here directly).
  useEffect(() => {
    if (defaultDestination) setDestination(defaultDestination);
  }, [defaultDestination]);
  useEffect(() => {
    if (defaultOrigin) setOrigin(defaultOrigin);
  }, [defaultOrigin]);
  const [days, setDays] = useState(defaultDays && defaultDays > 0 ? String(defaultDays) : "");
  // Keep Days in step with the travel window set above (end − start): when the dates
  // change, the day count follows, same as destination/start-point prefill.
  useEffect(() => {
    if (defaultDays && defaultDays > 0) setDays(String(defaultDays));
  }, [defaultDays]);
  const [groupSize, setGroupSize] = useState(defaultGroupSize ? String(defaultGroupSize) : "");
  const [themes, setThemes] = useState<string[]>([]);
  const [tier, setTier] = useState("");
  const [budget, setBudget] = useState("");
  const [ageBand, setAgeBand] = useState("");
  const [transport, setTransport] = useState<string[]>([]);

  const [paste, setPaste] = useState("");
  const [result, setResult] = useState<SuggestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [applied, setApplied] = useState(false);

  async function getSuggestions() {
    setLoading(true);
    setError(null);
    setApplied(false);
    try {
      const res = await fetch("/api/v1/planning/suggest", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          destination: destination || null,
          origin: origin || null,
          duration_days: days ? Number(days) : null,
          group_size: groupSize ? Number(groupSize) : null,
          themes, tier: tier || null, budget_inr: budget || null,
          age_band: ageBand || null, transport,
          segments, notes: notes || null,
        }),
      });
      if (!res.ok) throw new Error(`Suggest failed (${res.status})`);
      setResult((await res.json()) as SuggestResult);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not get suggestions.");
    } finally {
      setLoading(false);
    }
  }

  async function parsePaste() {
    setError(null);
    try {
      const res = await fetch("/api/v1/planning/parse", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ text: paste }),
      });
      if (!res.ok) throw new Error(`Parse failed (${res.status})`);
      const p = (await res.json()) as IntakeParse;
      if (p.destination) setDestination(p.destination);
      if (p.origin) setOrigin(p.origin);
      if (p.duration_days) setDays(String(p.duration_days));
      if (p.group_size) setGroupSize(String(p.group_size));
      if (p.themes.length) setThemes(p.themes);
      if (p.tier) setTier(p.tier);
      if (p.budget_inr) setBudget(p.budget_inr);
      if (p.age_band) setAgeBand(p.age_band);
      if (p.transport.length) setTransport(p.transport);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not parse.");
    }
  }

  const weights = result
    ? Object.entries(result.weights).sort((a, b) => b[1] - a[1])
    : [];

  return (
    <section className="mb-6 rounded-lg border border-indigo-200 bg-indigo-50/40">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-5 py-3 text-left"
      >
        <span className="font-medium text-indigo-900">✨ AI suggestions</span>
        <span className="text-sm text-indigo-600">{open ? "Hide" : "Plan with AI"}</span>
      </button>

      {open && (
        <div className="space-y-4 border-t border-indigo-200 px-5 py-4">
          {/* paste-parse */}
          <div>
            <label className="text-xs font-medium text-neutral-600">
              Paste the client&apos;s form answers (optional) — the AI fills the fields below
            </label>
            <textarea
              value={paste}
              onChange={(e) => setPaste(e.target.value)}
              rows={3}
              className="mt-1 w-full rounded-md border border-neutral-300 bg-white p-2 text-sm text-neutral-900 placeholder:text-neutral-400"
              placeholder="Paste the intake response here…"
            />
            <button
              onClick={parsePaste}
              disabled={!paste.trim()}
              className="mt-1 rounded-md border border-neutral-300 px-3 py-1 text-xs font-medium text-neutral-700 hover:bg-white disabled:opacity-40"
            >
              Parse into fields
            </button>
          </div>

          {/* structured inputs */}
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Destination">
              <input value={destination} onChange={(e) => setDestination(e.target.value)}
                className="input" placeholder="e.g. Rishikesh" />
            </Field>
            <Field label="Start point (for transport)">
              <input value={origin} onChange={(e) => setOrigin(e.target.value)}
                className="input" placeholder="e.g. Delhi" />
            </Field>
            <Field label="Days">
              <input value={days} onChange={(e) => setDays(e.target.value)}
                inputMode="numeric" className="input" placeholder="5" />
            </Field>
            <Field label="Participants">
              <input value={groupSize} onChange={(e) => setGroupSize(e.target.value)}
                inputMode="numeric" className="input" placeholder="5" />
            </Field>
            <Field label="Accommodation">
              <select value={tier} onChange={(e) => setTier(e.target.value)} className="input">
                <option value="">—</option>
                {TIER_OPTIONS.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </Field>
            <Field label="Budget (₹)">
              <input value={budget} onChange={(e) => setBudget(e.target.value)}
                inputMode="numeric" className="input" placeholder="300000" />
            </Field>
            <Field label="Age group">
              <select value={ageBand} onChange={(e) => setAgeBand(e.target.value)} className="input">
                <option value="">—</option>
                {AGE_OPTIONS.map((a) => <option key={a} value={a}>{a}</option>)}
              </select>
            </Field>
          </div>

          <Field label="Experiences">
            <div className="flex flex-wrap gap-1.5">
              {THEME_OPTIONS.map((t) => (
                <Chip key={t} on={themes.includes(t)} onClick={() => setThemes(toggle(themes, t))}>
                  {t}
                </Chip>
              ))}
            </div>
          </Field>
          <Field label="Transport">
            <div className="flex flex-wrap gap-1.5">
              {TRANSPORT_OPTIONS.map((t) => (
                <Chip key={t} on={transport.includes(t)} onClick={() => setTransport(toggle(transport, t))}>
                  {t}
                </Chip>
              ))}
            </div>
          </Field>

          <Field label="Notes / constraints for the AI (saved with the itinerary)">
            <textarea
              value={notes}
              onChange={(e) => onNotesChange?.(e.target.value)}
              rows={2}
              className="w-full rounded-md border border-neutral-300 bg-white p-2 text-sm text-neutral-900 placeholder:text-neutral-400"
              placeholder="Must-include / exclude / constraints — e.g. include a farewell dinner; avoid early mornings; no shopping stops"
            />
          </Field>

          {segments.length > 0 && (
            <p className="text-xs text-neutral-500">
              Using {segments.reduce((n, s) => n + s.pax_count, 0)} travellers from your
              groups
              {segments.some((s) => s.pax_class === "foreign")
                ? " — includes foreign travellers, so guide/monument costs are treated per class."
                : "."}
            </p>
          )}

          <div className="flex items-center gap-3">
            <button
              onClick={getSuggestions}
              disabled={loading}
              className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {loading ? "Thinking…" : "Get AI suggestions"}
            </button>
            {error && <span className="text-sm text-red-600">{error}</span>}
          </div>

          {result && (
            <div className="space-y-4 rounded-md border border-neutral-200 bg-white p-4">
              {/* category-check warnings — what the deterministic net auto-added/flagged */}
              {result.warnings.length > 0 && (
                <div className="rounded-md border border-amber-300 bg-amber-50 p-3">
                  <p className="text-xs font-semibold text-amber-900">
                    ⚠ Auto-filled to complete every day — please review &amp; confirm rates
                  </p>
                  <ul className="mt-1.5 list-disc space-y-0.5 pl-5 text-xs text-amber-800">
                    {result.warnings.map((w, i) => <li key={i}>{w}</li>)}
                  </ul>
                </div>
              )}

              {/* weights */}
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-neutral-500">
                  Priority weights for this client
                </p>
                <div className="mt-2 space-y-1">
                  {weights.map(([k, v]) => (
                    <div key={k} className="flex items-center gap-2 text-xs">
                      <span className="w-32 shrink-0 text-neutral-600">{WEIGHT_LABELS[k] ?? k}</span>
                      <span className="h-2 rounded bg-indigo-400" style={{ width: `${v * 2}px` }} />
                      <span className="text-neutral-500">{v}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* draft */}
              <div>
                <p className="font-medium text-neutral-900">{result.draft.title}</p>
                <p className="text-sm text-neutral-500">{result.draft.overview}</p>
                <div className="mt-3 space-y-3">
                  {result.draft.days.map((d) => (
                    <div key={d.day_number} className="rounded-md border border-neutral-100 bg-neutral-50 p-3">
                      <p className="text-sm font-medium">Day {d.day_number}: {d.title}</p>
                      <p className="text-xs text-neutral-500">{d.narrative}</p>
                      <ul className="mt-2 space-y-1">
                        {d.components.map((c, i) => (
                          <li key={i} className="flex flex-wrap items-center gap-2 text-xs">
                            <span className="rounded bg-neutral-200 px-1.5 py-0.5 font-medium text-neutral-700">
                              {c.kind}
                            </span>
                            <span className="text-neutral-800">{c.title}</span>
                            {c.estimate_amount != null ? (
                              <span className="rounded bg-amber-100 px-1.5 py-0.5 text-amber-800">
                                estimate ₹{c.estimate_amount}
                              </span>
                            ) : (
                              <span className="text-neutral-400">rate to confirm</span>
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
                {result.draft.ops_notes.length > 0 && (
                  <ul className="mt-3 list-disc pl-5 text-xs text-neutral-500">
                    {result.draft.ops_notes.map((n, i) => <li key={i}>{n}</li>)}
                  </ul>
                )}
                {result.draft.sources.length > 0 && (
                  <div className="mt-3 border-t border-neutral-100 pt-2">
                    <p className="text-xs font-medium text-neutral-500">
                      🔎 Live web sources (estimates only — verify before quoting)
                    </p>
                    <ul className="mt-1 space-y-0.5 text-xs">
                      {result.draft.sources.map((s, i) => {
                        const href = /^https?:\/\//i.test(s) ? s : null;
                        let host = s;
                        if (href) {
                          try { host = new URL(s).hostname.replace(/^www\./, ""); }
                          catch { host = s; }
                        }
                        return (
                          <li key={i} className="truncate">
                            {href ? (
                              <a href={href} target="_blank" rel="noopener noreferrer"
                                className="text-indigo-600 hover:underline">{host}</a>
                            ) : (
                              <span className="text-neutral-500">{s}</span>
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                )}
              </div>

              <button
                onClick={() => { onApply(result.draft); setApplied(true); }}
                className="rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800"
              >
                Apply all to the days below
              </button>
              {applied && <span className="ml-3 text-sm text-green-700">Applied ✓ — review + confirm rates below.</span>}
            </div>
          )}
        </div>
      )}
      <style jsx>{`
        .input {
          width: 100%;
          border-radius: 0.375rem;
          border: 1px solid rgb(212 212 212);
          padding: 0.375rem 0.5rem;
          font-size: 0.875rem;
          background: #ffffff;
          color: #171717;
        }
        .input::placeholder {
          color: rgb(163 163 163);
        }
      `}</style>
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-neutral-600">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  );
}

function Chip({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border px-2.5 py-1 text-xs ${
        on
          ? "border-indigo-400 bg-indigo-100 text-indigo-800"
          : "border-neutral-300 bg-white text-neutral-600 hover:border-neutral-400"
      }`}
    >
      {children}
    </button>
  );
}
