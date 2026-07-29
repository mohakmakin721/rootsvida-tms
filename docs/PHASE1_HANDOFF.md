# Phase 1 — handoff summary

**Status: complete** (12/12 milestones). This is the data-governance foundation:
canonical schema, provenance, the ingestion pipeline, human review, dedup, and a
repeatable rebuild. No pricing, invoicing, WhatsApp, payments, or AI agents yet —
those are Phase 2+ (plan §36). No LLM runs in Phase 1 (D-0007).

## What it does

Turns the legacy workbooks into curated, traceable canonical data behind a human
review gate:

1. **Capture** — a source workbook is fingerprinted (SHA-256) and every row is
   staged verbatim as JSONB (`source_documents` → `raw_import_rows`).
2. **Normalise** — a mechanical, per-sheet mapping upserts canonical `suppliers`
   + `supplier_contacts` + `destinations` (no LLM). Suppliers are unverified
   *prospects*; rough price text stays in staging, never turned into a rate
   (D-0009).
3. **Flag** — a data-quality report and a fuzzy dedup pass surface what needs a
   human (name-less rows, duplicate pairs).
4. **Review** — the review queue (API + Next.js UI) lets a person approve / edit /
   reject candidates and merge duplicates; nothing auto-publishes.
5. **Rebuild** — `make reingest` re-derives everything from source, idempotently.

## Current state (dev DB)

Rajasthan sheet ingested end-to-end: **117 rows staged → 112 supplier prospects,
23 destinations, 68 contacts**. Review queue holds **5 supplier candidates**
(name-less rows) + **4 merge candidates** (28 Kothi, Utsav Camp, Taj Hari Mahal,
Samode House), all pending. **74 tests pass**; ruff + mypy + web build green.
Migrations `0001`–`0005` applied.

## Run it

Prereqs: Python 3.12+, Node 20+, Postgres 16 (Docker easiest). Local Postgres is
published on **host port 5433** (a native PG owns 5432) — see
[TROUBLESHOOTING.md](TROUBLESHOOTING.md).

```bash
docker compose up -d          # Postgres + MinIO
make install && make migrate  # deps + schema
make seed                     # the initial org (idempotent)
make ingest sheet=Rajasthan   # stage + normalise
make dedup                    # queue duplicate suppliers
make dq                       # data-quality report
make api                      # domain service on :8000
make web-install && make web  # review UI on :3000  ->  /review
```

`make reingest` runs the whole pipeline in one idempotent step.

## Layout & entry points

| area | where |
|---|---|
| Canonical/provenance/review models | `services/domain-svc/app/models/` |
| Review API + service | `app/api/v1/review.py`, `app/services/{review,merge}.py` |
| Ingestion pipeline | `ingestion/` (`staging`, `normalize`, `migrate`, `dedup`, `quality`, `reingest`, `cli`) |
| Migrations | `db/migrations/versions/` (`0001`–`0005`) |
| Review UI | `apps/web/app/review/` |
| Tests | `tests/` (74) |

## Load-bearing decisions (see [DECISIONS.md](DECISIONS.md))

- **D-0001** AI never owns money; determinism owns arithmetic.
- **D-0002** Commission/margin isolated in `supplier_commercials` (owner/ops only).
- **D-0007** LLM dormant in Phase 1; price strings preserved, not parsed.
- **D-0009** Property sheets migrate to unverified *prospects*, not rates.
- **D-0010** Review queue is a decision/audit ledger; producers apply decisions.
- **D-0011** Dedup is human-gated; merges are soft (reversible) and never automatic.

## Guarantees worth trusting

- **Provenance:** any canonical supplier → its staged row → sheet, row number, and
  source file (via `raw_import_rows.normalized_supplier_id`).
- **Idempotent everywhere:** re-running any step (or `make reingest`) converges
  with no duplicates.
- **Nothing auto-publishes:** the review queue is the only path to trusted data.

## Next (Phase 2, not started)

Deterministic pricing engine — the Jaipur costing workbook
(`Jaipur_Dynamic_Costing_Workbook_Revised.xlsx`, held out per D-0004) becomes the
golden-fixture spec. Then itineraries/quotes, documents/invoices, and the agent
layer — all built on this foundation, every agent switch-off-able.

## Reference

[INGESTION.md](INGESTION.md) · [DATA_DICTIONARY.md](DATA_DICTIONARY.md) ·
[DECISIONS.md](DECISIONS.md) · [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
