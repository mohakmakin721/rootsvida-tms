"use client";

import { useState } from "react";

import { CURRENCIES, GST_STATES, inr } from "@/lib/constants";
import type { Invoice, ItineraryBrief, Milestone, Project, Quote } from "@/lib/types";

import { btnDark, btnLight, Field, inputCls } from "@/app/builder/ui";

import { ProjectTimeline } from "./project-timeline";

const QUOTE_TONE: Record<string, string> = {
  draft: "bg-neutral-100 text-neutral-600",
  issued: "bg-blue-100 text-blue-700",
  accepted: "bg-emerald-100 text-emerald-700",
  expired: "bg-amber-100 text-amber-700",
  superseded: "bg-neutral-200 text-neutral-400 line-through",
};

interface Assumptions {
  buyer_state_code: string;
  fx_currency: string;
  fx_rate: string;
  rounding: string;
  margin_floor: string;
}

const DEFAULT_ASSUMPTIONS: Assumptions = {
  buyer_state_code: "05",
  fx_currency: "USD",
  fx_rate: "",
  rounding: "nearest_1",
  margin_floor: "",
};

function assumptionsBody(a: Assumptions): Record<string, unknown> {
  return {
    buyer_state_code: a.buyer_state_code || null,
    buyer_country: "IN",
    rounding: a.rounding,
    fx_currency: a.fx_currency,
    fx_rate: a.fx_rate ? a.fx_rate : null,
    // Field is a percentage (e.g. 12); the engine wants a fraction (0.12).
    margin_floor:
      a.margin_floor && Number(a.margin_floor) > 0 ? String(Number(a.margin_floor) / 100) : null,
  };
}

export function ProjectWorkspace({
  project,
  initialItineraries,
  initialQuotes,
  initialMilestones,
  initialInvoices,
}: {
  project: Project;
  initialItineraries: ItineraryBrief[];
  initialQuotes: Quote[];
  initialMilestones: Milestone[];
  initialInvoices: Invoice[];
}) {
  const [quotes, setQuotes] = useState<Quote[]>(initialQuotes);
  const [invoices, setInvoices] = useState<Invoice[]>(initialInvoices);
  const [openForm, setOpenForm] = useState<string | null>(null); // "create:<itId>" | "revise:<qId>"
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // A quote is already invoiced if it has a live (issued) invoice.
  const invoicedQuoteIds = new Set(
    invoices.filter((i) => i.kind === "invoice" && i.status === "issued").map((i) => i.quote_id),
  );

  async function refreshQuotes() {
    const res = await fetch(`/api/v1/projects/${project.id}/quotes`, { cache: "no-store" });
    if (res.ok) setQuotes((await res.json()) as Quote[]);
  }

  async function refreshInvoices() {
    const res = await fetch(`/api/v1/projects/${project.id}/invoices`, { cache: "no-store" });
    if (res.ok) setInvoices((await res.json()) as Invoice[]);
  }

  async function generateInvoice(quoteId: string) {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/v1/quotes/${quoteId}/invoice`, { method: "POST" });
      if (!res.ok) {
        const d = await res.json().catch(() => null);
        setError(typeof d?.detail === "string" ? d.detail : `Could not generate invoice (${res.status}).`);
      } else {
        await refreshInvoices();
      }
    } catch {
      setError("Could not reach the domain service.");
    } finally {
      setBusy(false);
    }
  }

  async function creditNote(invoiceId: string) {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/v1/invoices/${invoiceId}/credit-note`, { method: "POST" });
      if (!res.ok) {
        const d = await res.json().catch(() => null);
        setError(typeof d?.detail === "string" ? d.detail : `Could not raise credit note (${res.status}).`);
      } else {
        await refreshInvoices();
      }
    } finally {
      setBusy(false);
    }
  }

  async function post(url: string, body: unknown): Promise<boolean> {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => null);
        setError(typeof d?.detail === "string" ? d.detail : `Request failed (${res.status}).`);
        return false;
      }
      await refreshQuotes();
      return true;
    } catch {
      setError("Could not reach the domain service.");
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function createQuote(itineraryId: string, a: Assumptions) {
    if (await post(`/api/v1/itineraries/${itineraryId}/quotes`, assumptionsBody(a))) {
      setOpenForm(null);
    }
  }

  async function reviseQuote(quoteId: string, a: Assumptions) {
    if (await post(`/api/v1/quotes/${quoteId}/revise`, assumptionsBody(a))) {
      setOpenForm(null);
    }
  }

  async function issueQuote(quoteId: string, validUntil: string) {
    await post(`/api/v1/quotes/${quoteId}/issue`, { valid_until: validUntil || null });
  }

  return (
    <div className="mt-3">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold">{project.code}</h1>
        <p className="mt-1 text-sm text-neutral-600">
          {project.client_name}
          {project.client_country ? ` · ${project.client_country}` : ""}
        </p>
        <p className="mt-0.5 text-xs text-neutral-400">
          Project created {new Date(project.created_at).toLocaleString()}
        </p>
      </header>

      {error && (
        <p className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      <ProjectTimeline project={project} initialMilestones={initialMilestones} />

      {/* Itineraries — each can be priced into a new quote. */}
      <section className="mb-8">
        <h2 className="mb-2 text-sm font-semibold text-neutral-800">Itineraries</h2>
        {initialItineraries.length === 0 ? (
          <p className="rounded-md border border-dashed border-neutral-200 px-3 py-3 text-xs text-neutral-400">
            No itineraries. Build one to price a quote.
          </p>
        ) : (
          <div className="space-y-2">
            {initialItineraries.map((it) => (
              <div key={it.id} className="rounded-lg border border-neutral-200 bg-white p-3">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-medium text-neutral-900">{it.title}</div>
                    <div className="text-xs text-neutral-500">
                      {it.start_date} → {it.end_date} · v{it.version} · {it.status}
                    </div>
                    <div className="text-[11px] text-neutral-400">
                      created {new Date(it.created_at).toLocaleDateString()}
                    </div>
                  </div>
                  <button
                    className={btnDark}
                    onClick={() => setOpenForm(openForm === `create:${it.id}` ? null : `create:${it.id}`)}
                  >
                    {openForm === `create:${it.id}` ? "Cancel" : "Create quote"}
                  </button>
                </div>
                {openForm === `create:${it.id}` && (
                  <AssumptionsForm busy={busy} onSubmit={(a) => createQuote(it.id, a)} submitLabel="Price quote" />
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Quotes */}
      <section>
        <h2 className="mb-2 text-sm font-semibold text-neutral-800">Quotes</h2>
        {quotes.length === 0 ? (
          <p className="rounded-md border border-dashed border-neutral-200 px-3 py-3 text-xs text-neutral-400">
            No quotes yet. Price an itinerary above to create version 1.
          </p>
        ) : (
          <div className="space-y-3">
            {quotes
              .slice()
              .sort((a, b) => b.version - a.version)
              .map((q) => (
                <QuoteCard
                  key={q.id}
                  quote={q}
                  busy={busy}
                  invoiced={invoicedQuoteIds.has(q.id)}
                  reviseOpen={openForm === `revise:${q.id}`}
                  onToggleRevise={() =>
                    setOpenForm(openForm === `revise:${q.id}` ? null : `revise:${q.id}`)
                  }
                  onRevise={(a) => reviseQuote(q.id, a)}
                  onIssue={(d) => issueQuote(q.id, d)}
                  onGenerateInvoice={() => generateInvoice(q.id)}
                />
              ))}
          </div>
        )}
      </section>

      {/* Invoices */}
      <section className="mt-8">
        <h2 className="mb-2 text-sm font-semibold text-neutral-800">Invoices</h2>
        {invoices.length === 0 ? (
          <p className="rounded-md border border-dashed border-neutral-200 px-3 py-3 text-xs text-neutral-400">
            No invoices yet. Generate one from an issued quote above.
          </p>
        ) : (
          <div className="space-y-2">
            {invoices.map((inv) => (
              <InvoiceRow
                key={inv.id}
                invoice={inv}
                busy={busy}
                onCreditNote={() => creditNote(inv.id)}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

const INVOICE_TONE: Record<string, string> = {
  issued: "bg-blue-100 text-blue-700",
  cancelled: "bg-neutral-200 text-neutral-400 line-through",
};

function InvoiceRow({
  invoice,
  busy,
  onCreditNote,
}: {
  invoice: Invoice;
  busy: boolean;
  onCreditNote: () => void;
}) {
  const isCredit = invoice.kind === "credit_note";
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-neutral-200 bg-white p-3">
      <span className="font-mono text-sm font-medium text-neutral-900">{invoice.number}</span>
      {isCredit && (
        <span className="rounded-full bg-purple-100 px-2 py-0.5 text-xs font-medium text-purple-700">
          credit note
        </span>
      )}
      <span className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${INVOICE_TONE[invoice.status] ?? "bg-neutral-100"}`}>
        {invoice.status}
      </span>
      <span className="text-sm text-neutral-700">{inr(invoice.total)}</span>
      <span className="text-xs text-neutral-400">{invoice.invoice_date}</span>
      <div className="ml-auto flex items-center gap-2">
        <a
          href={`/api/v1/invoices/${invoice.id}/pdf`}
          target="_blank"
          rel="noopener noreferrer"
          className={btnDark}
        >
          Download PDF
        </a>
        {!isCredit && invoice.status === "issued" && (
          <button className={btnLight} disabled={busy} onClick={onCreditNote}>
            Credit note
          </button>
        )}
      </div>
    </div>
  );
}

function AssumptionsForm({
  busy,
  onSubmit,
  submitLabel,
}: {
  busy: boolean;
  onSubmit: (a: Assumptions) => void;
  submitLabel: string;
}) {
  const [a, setA] = useState<Assumptions>(DEFAULT_ASSUMPTIONS);
  const set = (patch: Partial<Assumptions>) => setA({ ...a, ...patch });
  return (
    <div className="mt-3 grid gap-3 rounded-md border border-neutral-200 bg-neutral-50 p-3 sm:grid-cols-2">
      <Field label="Buyer’s state (sets GST)">
        <select className={inputCls} value={a.buyer_state_code} onChange={(e) => set({ buyer_state_code: e.target.value })}>
          {GST_STATES.map((s) => (
            <option key={s.code} value={s.code}>
              {s.code} — {s.name}{s.code === "05" ? " (same as seller)" : ""}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Rounding">
        <select className={inputCls} value={a.rounding} onChange={(e) => set({ rounding: e.target.value })}>
          <option value="nearest_1">Per-pax to the rupee</option>
          <option value="gross_nearest_100">Round gross to ₹100 (invoice)</option>
        </select>
      </Field>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Quote currency">
          <select className={inputCls} value={a.fx_currency} onChange={(e) => set({ fx_currency: e.target.value })}>
            {CURRENCIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </Field>
        <Field label={`₹ per 1 ${a.fx_currency}`}>
          <input className={inputCls} value={a.fx_rate} onChange={(e) => set({ fx_rate: e.target.value })} placeholder="95" />
        </Field>
      </div>
      <Field label="Minimum margin % (optional)">
        <input className={inputCls} value={a.margin_floor} onChange={(e) => set({ margin_floor: e.target.value })} placeholder="e.g. 12" />
        <span className="mt-1 text-[11px] leading-snug text-neutral-400">
          Safety floor — a quote below this margin is blocked at issue (owner can override).
        </span>
      </Field>
      <div className="flex items-end sm:col-span-2">
        <button className={`${btnDark} disabled:opacity-50`} disabled={busy} onClick={() => onSubmit(a)}>
          {busy ? "Working…" : submitLabel}
        </button>
      </div>
    </div>
  );
}

function QuoteCard({
  quote,
  busy,
  invoiced,
  reviseOpen,
  onToggleRevise,
  onRevise,
  onIssue,
  onGenerateInvoice,
}: {
  quote: Quote;
  busy: boolean;
  invoiced: boolean;
  reviseOpen: boolean;
  onToggleRevise: () => void;
  onRevise: (a: Assumptions) => void;
  onIssue: (validUntil: string) => void;
  onGenerateInvoice: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [validUntil, setValidUntil] = useState("");
  const [issuing, setIssuing] = useState(false);

  const converted =
    quote.fx_currency && quote.fx_rate_inr_usd && quote.total_gross
      ? Number(quote.total_gross) / Number(quote.fx_rate_inr_usd)
      : null;

  return (
    <div className="rounded-lg border border-neutral-200 bg-white">
      <div className="flex items-center justify-between gap-3 p-3">
        <button className="flex items-center gap-3 text-left" onClick={() => setOpen((o) => !o)}>
          <span className="text-sm font-semibold text-neutral-900">v{quote.version}</span>
          <span className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${QUOTE_TONE[quote.status] ?? "bg-neutral-100"}`}>
            {quote.status}
          </span>
          <span className="text-sm text-neutral-700">
            {quote.total_gross != null ? inr(quote.total_gross) : "—"}
            {converted != null && (
              <span className="text-neutral-400">
                {" "}
                ≈ {quote.fx_currency} {converted.toLocaleString(undefined, { maximumFractionDigits: 2 })}
              </span>
            )}
          </span>
          <span className="text-xs text-neutral-400">
            margin {quote.margin_pct != null ? `${quote.margin_pct}%` : "—"}
          </span>
        </button>
        <div className="flex items-center gap-2">
          {quote.status === "draft" && (
            <>
              <input
                type="date"
                className={`${inputCls} w-36`}
                value={validUntil}
                onChange={(e) => setValidUntil(e.target.value)}
                title="Valid until (optional)"
              />
              <button
                className={`${btnDark} disabled:opacity-50`}
                disabled={busy}
                onClick={async () => { setIssuing(true); await onIssue(validUntil); setIssuing(false); }}
              >
                {issuing ? "Issuing…" : "Issue"}
              </button>
            </>
          )}
          {(quote.status === "issued" || quote.status === "accepted") && (
            invoiced ? (
              <span className="rounded-full bg-emerald-100 px-2 py-1 text-xs font-medium text-emerald-700">
                ✓ invoiced
              </span>
            ) : (
              <button className={`${btnDark} disabled:opacity-50`} disabled={busy} onClick={onGenerateInvoice}>
                Generate invoice
              </button>
            )
          )}
          {(quote.status === "issued" || quote.status === "accepted" || quote.status === "expired") && (
            <button className={btnLight} onClick={onToggleRevise}>
              {reviseOpen ? "Cancel" : "Revise"}
            </button>
          )}
          <a
            href={`/api/v1/quotes/${quote.id}/proposal.pdf`}
            target="_blank"
            rel="noopener noreferrer"
            className={btnLight}
            title="Client-facing proposal PDF"
          >
            Proposal
          </a>
          <a
            href={`/api/v1/quotes/${quote.id}/costing.xlsx`}
            className={btnLight}
            title="Internal costing workbook (confidential — shows margin)"
          >
            Costing
          </a>
          <button className="text-neutral-400" onClick={() => setOpen((o) => !o)} aria-label="Toggle detail">
            {open ? "▲" : "▼"}
          </button>
        </div>
      </div>

      {reviseOpen && (
        <div className="border-t border-neutral-100 p-3">
          <p className="mb-1 text-xs text-neutral-500">
            Revising supersedes v{quote.version} and creates a new draft version.
          </p>
          <AssumptionsForm busy={busy} onSubmit={onRevise} submitLabel="Create revision" />
        </div>
      )}

      {open && (
        <div className="border-t border-neutral-100 p-3">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-neutral-500">
                <tr>
                  <th className="py-1 pr-3 font-medium">Group</th>
                  <th className="py-1 pr-3 font-medium text-right">Cost / pax</th>
                  <th className="py-1 pr-3 font-medium text-right">Sell / pax</th>
                  <th className="py-1 pr-3 font-medium text-right">Pax</th>
                  <th className="py-1 font-medium text-right">Line total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {quote.lines.map((ln, i) => (
                  <tr key={i}>
                    <td className="py-1.5 pr-3 text-neutral-700">{ln.description}</td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">{ln.cost_per_pax != null ? inr(ln.cost_per_pax) : "—"}</td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">{ln.sell_per_pax != null ? inr(ln.sell_per_pax) : "—"}</td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">{ln.pax_count ?? "—"}</td>
                    <td className="py-1.5 text-right font-medium tabular-nums">{ln.line_total != null ? inr(ln.line_total) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1 text-xs sm:grid-cols-3">
            <Stat label="Total cost" value={quote.total_cost != null ? inr(quote.total_cost) : "—"} />
            <Stat label="Taxable" value={quote.total_taxable != null ? inr(quote.total_taxable) : "—"} />
            <Stat label="GST" value={`${quote.gst_rate}% (${quote.gst_treatment})`} />
            <Stat label="Tax" value={quote.total_tax != null ? inr(quote.total_tax) : "—"} />
            <Stat label="Gross total" value={quote.total_gross != null ? inr(quote.total_gross) : "—"} strong />
            <Stat label="Margin" value={quote.margin_pct != null ? `${quote.margin_pct}%` : "—"} />
            {converted != null && (
              <Stat
                label={`≈ in ${quote.fx_currency}`}
                value={`${quote.fx_currency} ${converted.toLocaleString(undefined, { maximumFractionDigits: 2 })} @ ₹${quote.fx_rate_inr_usd}`}
              />
            )}
            <Stat label="Rounding" value={quote.rounding_policy} />
            <Stat label="Created" value={new Date(quote.created_at).toLocaleString()} />
            {quote.issued_at && <Stat label="Issued" value={new Date(quote.issued_at).toLocaleDateString()} />}
            {quote.valid_until && <Stat label="Valid until" value={quote.valid_until} />}
            {quote.engine_version && <Stat label="Engine" value={quote.engine_version} />}
          </dl>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="flex flex-col">
      <dt className="text-[10px] uppercase tracking-wide text-neutral-400">{label}</dt>
      <dd className={`${strong ? "font-semibold text-neutral-900" : "text-neutral-700"}`}>{value}</dd>
    </div>
  );
}
