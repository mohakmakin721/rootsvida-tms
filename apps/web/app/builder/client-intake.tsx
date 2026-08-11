"use client";

import { useEffect, useRef, useState } from "react";

import type { ClientDetail, ClientSummary, ClientType, ItineraryBrief } from "@/lib/types";

import { Card, Field, inputCls } from "./ui";

const CLIENT_TYPES: ClientType[] = ["individual", "family", "group", "corporate"];

export interface EditIntakeInitial {
  projectId: string;
  projectCode: string;
  clientName: string;
  title: string;
  start_date: string;
  end_date: string;
  destination?: string;
  origin?: string;
  notes?: string;
}

export interface NewClient {
  name: string;
  client_type: ClientType;
  corporate_name: string;
  country: string;
  email: string;
  phone: string;
  referral: string;
  notes: string;
}

export interface IntakeValue {
  title: string;
  start_date: string;
  end_date: string;
  destination: string;
  origin: string;
  notes: string;
  ready: boolean;
  client:
    | { kind: "existing"; id: string; name: string }
    | { kind: "new"; data: NewClient };
  project: { kind: "existing"; id: string; code: string } | { kind: "new"; code: string };
}

const TODAY = new Date().toISOString().slice(0, 10);
function addDays(iso: string, n: number): string {
  const d = new Date(iso + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

const emptyNew: NewClient = {
  name: "", client_type: "individual", corporate_name: "", country: "", email: "",
  phone: "", referral: "", notes: "",
};

export function ClientIntake({
  onChange,
  initial = null,
}: {
  onChange: (v: IntakeValue) => void;
  initial?: EditIntakeInitial | null;
}) {
  if (initial) return <EditIntake initial={initial} onChange={onChange} />;
  return <NewOrExistingIntake onChange={onChange} />;
}

/** Compact intake shown when editing an existing itinerary: the project & client
 *  are fixed; only the title and travel dates are editable. */
function EditIntake({
  initial,
  onChange,
}: {
  initial: EditIntakeInitial;
  onChange: (v: IntakeValue) => void;
}) {
  const [title, setTitle] = useState(initial.title);
  const [startDate, setStartDate] = useState(initial.start_date);
  const [endDate, setEndDate] = useState(initial.end_date);
  const [destination, setDestination] = useState(initial.destination ?? "");
  const [origin, setOrigin] = useState(initial.origin ?? "");
  const [notes, setNotes] = useState(initial.notes ?? "");

  useEffect(() => {
    const ready =
      title.trim().length > 0 && !!startDate && !!endDate && endDate >= startDate;
    onChange({
      title: title.trim(), start_date: startDate, end_date: endDate,
      destination: destination.trim(), origin: origin.trim(), notes,
      ready,
      client: { kind: "existing", id: "", name: initial.clientName },
      project: { kind: "existing", id: initial.projectId, code: initial.projectCode },
    });
  }, [title, startDate, endDate, destination, origin, notes, initial, onChange]);

  return (
    <Card title="Client & project">
      <div className="mb-3 rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-800">
        Editing an itinerary under project <b>{initial.projectCode}</b> · {initial.clientName}.
        Changing the dates below will re-align the day rows.
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="Itinerary title" required>
          <input className={inputCls} value={title} onChange={(e) => setTitle(e.target.value)} />
        </Field>
        <Field label="Start date" required>
          <input type="date" className={inputCls} value={startDate} onChange={(e) => setStartDate(e.target.value)} />
        </Field>
        <Field label="End date" required>
          <input type="date" className={inputCls} value={endDate} onChange={(e) => setEndDate(e.target.value)} />
        </Field>
        <Field label="Destination">
          <input className={inputCls} value={destination} onChange={(e) => setDestination(e.target.value)} placeholder="e.g. Rishikesh" />
        </Field>
        <Field label="Start point (origin)">
          <input className={inputCls} value={origin} onChange={(e) => setOrigin(e.target.value)} placeholder="e.g. Delhi" />
        </Field>
      </div>
      <div className="mt-3">
        <Field label="Planning notes / constraints (used by AI, saved with the itinerary)">
          <textarea className={inputCls} rows={2} value={notes} onChange={(e) => setNotes(e.target.value)}
            placeholder="e.g. include a farewell dinner; avoid long drives; one flex day" />
        </Field>
      </div>
    </Card>
  );
}

function NewOrExistingIntake({ onChange }: { onChange: (v: IntakeValue) => void }) {
  const [mode, setMode] = useState<"search" | "new">("search");

  // existing-client search
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ClientSummary[]>([]);
  const [showResults, setShowResults] = useState(false);
  const [selected, setSelected] = useState<ClientDetail | null>(null);

  // new-client form
  const [newClient, setNewClient] = useState<NewClient>(emptyNew);

  // project
  const [projectMode, setProjectMode] = useState<"new" | "existing">("new");
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [projectItineraries, setProjectItineraries] = useState<ItineraryBrief[]>([]);
  const [showPast, setShowPast] = useState(false);
  const [code, setCode] = useState("");
  const [codeStatus, setCodeStatus] = useState<"" | "checking" | "available" | "taken">("");

  // itinerary meta
  const [title, setTitle] = useState("");
  const [startDate, setStartDate] = useState(TODAY);
  const [endDate, setEndDate] = useState(addDays(TODAY, 3));
  const [destination, setDestination] = useState("");
  const [origin, setOrigin] = useState("");
  const [notes, setNotes] = useState("");

  // ---- client search (debounced typeahead) ----
  useEffect(() => {
    if (mode !== "search" || selected) return;
    const q = query.trim();
    const t = setTimeout(async () => {
      try {
        const res = await fetch(`/api/v1/clients?q=${encodeURIComponent(q)}&limit=8`, {
          cache: "no-store",
        });
        if (res.ok) setResults((await res.json()) as ClientSummary[]);
      } catch {
        /* ignore — search is best-effort */
      }
    }, 220);
    return () => clearTimeout(t);
  }, [query, mode, selected]);

  async function pickClient(c: ClientSummary) {
    setShowResults(false);
    setQuery(c.name);
    try {
      const res = await fetch(`/api/v1/clients/${c.id}`, { cache: "no-store" });
      if (res.ok) {
        const detail = (await res.json()) as ClientDetail;
        setSelected(detail);
        setProjectMode(detail.projects.length > 0 ? "existing" : "new");
        setSelectedProjectId(detail.projects[0]?.id ?? "");
      }
    } catch {
      /* ignore */
    }
  }

  function clearClient() {
    setSelected(null);
    setQuery("");
    setResults([]);
    setProjectMode("new");
    setSelectedProjectId("");
  }

  // ---- existing project's itineraries (offer edit vs new) ----
  useEffect(() => {
    setShowPast(false); // collapse the list whenever the selected project changes
    if (projectMode !== "existing" || !selectedProjectId) {
      setProjectItineraries([]);
      return;
    }
    fetch(`/api/v1/projects/${selectedProjectId}/itineraries`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : []))
      .then((rows) => setProjectItineraries(rows as ItineraryBrief[]))
      .catch(() => setProjectItineraries([]));
  }, [projectMode, selectedProjectId]);

  // ---- project code availability (debounced) ----
  useEffect(() => {
    if (projectMode !== "new" || !code.trim()) {
      setCodeStatus("");
      return;
    }
    setCodeStatus("checking");
    const t = setTimeout(async () => {
      try {
        const res = await fetch(`/api/v1/projects?code=${encodeURIComponent(code.trim())}`, {
          cache: "no-store",
        });
        const rows = res.ok ? ((await res.json()) as unknown[]) : [];
        setCodeStatus(rows.length > 0 ? "taken" : "available");
      } catch {
        setCodeStatus("");
      }
    }, 300);
    return () => clearTimeout(t);
  }, [code, projectMode]);

  // ---- report the resolved value up ----
  useEffect(() => {
    const corporateOk =
      newClient.client_type !== "corporate" || newClient.corporate_name.trim().length > 0;
    const clientOk =
      mode === "search" ? !!selected : newClient.name.trim().length > 0 && corporateOk;
    const projectOk =
      projectMode === "existing" ? !!selectedProjectId : code.trim().length > 0 && codeStatus !== "taken";
    const ready =
      clientOk && projectOk && title.trim().length > 0 && !!startDate && !!endDate && endDate >= startDate;

    const client: IntakeValue["client"] =
      mode === "search" && selected
        ? { kind: "existing", id: selected.id, name: selected.name }
        : { kind: "new", data: newClient };
    const project: IntakeValue["project"] =
      projectMode === "existing" && selectedProjectId
        ? {
            kind: "existing",
            id: selectedProjectId,
            code: selected?.projects.find((p) => p.id === selectedProjectId)?.code ?? "",
          }
        : { kind: "new", code: code.trim() };

    onChange({
      title: title.trim(), start_date: startDate, end_date: endDate,
      destination: destination.trim(), origin: origin.trim(), notes,
      ready, client, project,
    });
  }, [mode, selected, newClient, projectMode, selectedProjectId, code, codeStatus,
      title, startDate, endDate, destination, origin, notes, onChange]);

  const info = (
    <>
      <b>Client</b> — search to autofill an existing client, or switch to “Add new
      client” to save a new one. <b>Project</b> — start a fresh project with a unique
      code, or continue one of this client’s existing projects. Fields marked{" "}
      <span className="text-red-500">*</span> are required.
    </>
  );

  return (
    <Card title="Client & project" info={info}>
      {/* CLIENT */}
      <div className="mb-4">
        <div className="mb-2 flex items-center gap-3 text-xs">
          <button
            onClick={() => { setMode("search"); setNewClient(emptyNew); }}
            className={tab(mode === "search")}
          >
            Existing client
          </button>
          <button
            onClick={() => { setMode("new"); clearClient(); }}
            className={tab(mode === "new")}
          >
            + Add new client
          </button>
        </div>

        {mode === "search" ? (
          selected ? (
            <div className="flex items-start justify-between rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2">
              <div>
                <div className="text-sm font-medium text-neutral-900">
                  {selected.corporate_name ? `${selected.corporate_name} — ${selected.name}` : selected.name}
                  <span className="ml-2 rounded bg-white px-1.5 py-0.5 text-xs capitalize text-neutral-500">
                    {selected.client_type}
                  </span>
                </div>
                <div className="text-xs text-neutral-600">
                  {[selected.country, selected.email, selected.phone].filter(Boolean).join(" · ") ||
                    "no contact details on file"}
                  {" · "}
                  {selected.project_count} existing project{selected.project_count === 1 ? "" : "s"}
                </div>
              </div>
              <button onClick={clearClient} className="text-xs text-neutral-500 underline hover:text-neutral-800">
                change
              </button>
            </div>
          ) : (
            <div className="relative">
              <Field label="Client name" required>
                <input
                  className={inputCls}
                  placeholder="Start typing a name…"
                  value={query}
                  onChange={(e) => { setQuery(e.target.value); setShowResults(true); }}
                  onFocus={() => setShowResults(true)}
                />
              </Field>
              {showResults && results.length > 0 && (
                <ul className="absolute z-20 mt-1 w-full overflow-hidden rounded-md border border-neutral-200 bg-white shadow-lg">
                  {results.map((c) => (
                    <li key={c.id}>
                      <button
                        onClick={() => pickClient(c)}
                        className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-neutral-50"
                      >
                        <span className="font-medium text-neutral-800">{c.name}</span>
                        <span className="text-xs capitalize text-neutral-400">
                          {c.client_type} · {c.project_count} proj.
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              {showResults && query.trim() && results.length === 0 && (
                <p className="mt-1 text-xs text-neutral-400">
                  No match — switch to “+ Add new client” to save “{query.trim()}”.
                </p>
              )}
            </div>
          )
        ) : (
          <NewClientForm value={newClient} onChange={setNewClient} />
        )}
      </div>

      {/* PROJECT */}
      <div className="mb-4 border-t border-neutral-100 pt-4">
        {selected && selected.projects.length > 0 && (
          <div className="mb-2 flex items-center gap-3 text-xs">
            <button onClick={() => setProjectMode("existing")} className={tab(projectMode === "existing")}>
              Continue a project
            </button>
            <button onClick={() => setProjectMode("new")} className={tab(projectMode === "new")}>
              + New project
            </button>
          </div>
        )}

        {projectMode === "existing" && selected && selected.projects.length > 0 ? (
          <>
            <Field label="Project" required>
              <select className={inputCls} value={selectedProjectId} onChange={(e) => setSelectedProjectId(e.target.value)}>
                {selected.projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.code} — {p.status}
                  </option>
                ))}
              </select>
            </Field>
            {projectItineraries.length > 0 && (
              <div className="mt-2">
                <button
                  type="button"
                  onClick={() => setShowPast((s) => !s)}
                  className="text-xs font-medium text-blue-600 underline hover:text-blue-800"
                >
                  {showPast
                    ? "Hide past itineraries"
                    : `Edit a past itinerary (${projectItineraries.length})`}
                </button>
                {showPast && (
                  <div className="mt-1 max-h-48 overflow-y-auto rounded-md border border-neutral-200 bg-neutral-50 p-2 text-xs">
                    <p className="mb-1 text-neutral-500">
                      Pick one to edit, or build a new itinerary under this project below.
                    </p>
                    <ul className="space-y-1">
                      {projectItineraries.map((it) => (
                        <li key={it.id} className="flex items-center justify-between gap-2">
                          <span className="text-neutral-700">
                            {it.title}{" "}
                            <span className="text-neutral-400">
                              ({it.start_date} → {it.end_date} · created{" "}
                              {new Date(it.created_at).toLocaleDateString()})
                            </span>
                          </span>
                          <a href={`/builder?itinerary=${it.id}`} className="shrink-0 font-medium text-blue-600 underline hover:text-blue-800">
                            Edit
                          </a>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </>
        ) : (
          <Field label="New project code" required>
            <input
              className={inputCls}
              placeholder="e.g. TP-JP-01"
              value={code}
              onChange={(e) => setCode(e.target.value)}
            />
            {codeStatus === "available" && <span className="mt-1 text-xs text-emerald-600">Code is available.</span>}
            {codeStatus === "taken" && <span className="mt-1 text-xs text-red-600">That code is already used — pick another.</span>}
            {codeStatus === "checking" && <span className="mt-1 text-xs text-neutral-400">Checking…</span>}
          </Field>
        )}
      </div>

      {/* ITINERARY META */}
      <div className="grid gap-3 border-t border-neutral-100 pt-4 sm:grid-cols-3">
        <Field label="Itinerary title" required>
          <input className={inputCls} placeholder="Jaipur / Golden Triangle" value={title} onChange={(e) => setTitle(e.target.value)} />
        </Field>
        <Field label="Start date" required>
          <input type="date" className={inputCls} value={startDate} onChange={(e) => setStartDate(e.target.value)} />
        </Field>
        <Field label="End date" required>
          <input type="date" className={inputCls} value={endDate} onChange={(e) => setEndDate(e.target.value)} />
        </Field>
        <Field label="Destination">
          <input className={inputCls} placeholder="e.g. Rishikesh" value={destination} onChange={(e) => setDestination(e.target.value)} />
        </Field>
        <Field label="Start point (origin)">
          <input className={inputCls} placeholder="e.g. Delhi" value={origin} onChange={(e) => setOrigin(e.target.value)} />
        </Field>
      </div>
      <div className="mt-3">
        <Field label="Planning notes / constraints (used by AI, saved with the itinerary)">
          <textarea className={inputCls} rows={2} value={notes} onChange={(e) => setNotes(e.target.value)}
            placeholder="e.g. include a farewell dinner; avoid long drives; one flex day" />
        </Field>
      </div>
    </Card>
  );
}

function NewClientForm({ value, onChange }: { value: NewClient; onChange: (v: NewClient) => void }) {
  const set = (patch: Partial<NewClient>) => onChange({ ...value, ...patch });
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <Field label="Client name" required>
        <input className={inputCls} value={value.name} onChange={(e) => set({ name: e.target.value })} />
      </Field>
      <Field label="Client type" required>
        <select className={inputCls} value={value.client_type} onChange={(e) => set({ client_type: e.target.value as ClientType })}>
          {CLIENT_TYPES.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </Field>
      {value.client_type === "corporate" && (
        <label className="flex flex-col gap-1 sm:col-span-2">
          <span className="text-xs text-neutral-500">
            Company name<span className="text-red-500"> *</span>
            <span className="ml-1 text-neutral-400">(the “Client name” above is the contact person)</span>
          </span>
          <input
            className={`${inputCls} ${value.corporate_name.trim() ? "" : "border-red-300"}`}
            placeholder="e.g. Acme Travel Pvt Ltd"
            value={value.corporate_name}
            onChange={(e) => set({ corporate_name: e.target.value })}
          />
        </label>
      )}
      <Field label="Home country (ISO-2)">
        <input className={inputCls} placeholder="IN, US, CL…" value={value.country} onChange={(e) => set({ country: e.target.value })} />
      </Field>
      <Field label="Email">
        <input className={inputCls} value={value.email} onChange={(e) => set({ email: e.target.value })} />
      </Field>
      <Field label="Phone">
        <input className={inputCls} value={value.phone} onChange={(e) => set({ phone: e.target.value })} />
      </Field>
      <Field label="Referring agent / company">
        <input className={inputCls} value={value.referral} onChange={(e) => set({ referral: e.target.value })} />
      </Field>
      <label className="flex flex-col gap-1 sm:col-span-2">
        <span className="text-xs text-neutral-500">Notes &amp; preferences</span>
        <textarea
          className={`${inputCls} h-20 resize-y`}
          placeholder="Interests, budget band, pace, must-sees — the details a planner would want."
          value={value.notes}
          onChange={(e) => set({ notes: e.target.value })}
        />
      </label>
    </div>
  );
}

function tab(active: boolean): string {
  return active
    ? "rounded-full bg-neutral-900 px-3 py-1 font-medium text-white"
    : "rounded-full bg-neutral-100 px-3 py-1 text-neutral-500 hover:text-neutral-800";
}
