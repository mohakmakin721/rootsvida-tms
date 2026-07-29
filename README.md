# RootsVida TMS

Travel Management System for **Rootsvida Experiences & Tours** — a canonical data
foundation, migration/ingestion pipeline, and human review interface, on top of
which the later deterministic pricing engine, web app, documents, and (eventually)
AI-agentic layer are built.

> **Phase 1 only.** This repository currently implements the data-governance
> foundation. The pricing engine, itinerary builder, invoicing, WhatsApp, payments
> and AI agents are **deliberately not built yet** (see the plan §36). The system
> is designed to be fully usable with every AI agent switched **off**.

## Guiding principle

**The AI does not own money.** Determinism owns all arithmetic, pricing, tax,
rounding and invoice numbering. LLMs may only *select inputs* and write prose.
Every quotable rate must trace to a source document + verifier + validity window.
Nothing auto-publishes — the human review queue is the only path to a verified rate.

See [`docs/DECISIONS.md`](docs/DECISIONS.md) for the decision log.

## Architecture

Monorepo, two deployables + one database (boring on purpose):

| Path | What |
|---|---|
| `apps/web/` | Next.js (App Router, TS, Tailwind, shadcn/ui) — the internal **Review Queue** UI |
| `services/domain-svc/` | Python 3.12+ / FastAPI / Pydantic v2 — canonical data, review API, provenance |
| `db/` | Alembic migrations — the single migration source of truth |
| `ingestion/` | Tiered workbook loaders (mechanical / assisted / bespoke / manual) |
| `docs/` | Decisions, ERD, data dictionary, ingestion + migration + troubleshooting guides |
| `infra/`, `scripts/` | Ops glue |

Stack: **PostgreSQL 16** (`numeric(14,2)` money, `timestamptz`, UUID PKs,
`pg_trgm` / `btree_gist` / `citext`, optional `pgvector`), FastAPI, Alembic,
Next.js, Docker Compose for local dev.

## Quick start

Prerequisites: **Python 3.12+**, **Node 20+**, and a **PostgreSQL 16** reachable
via `DATABASE_URL` — locally the easiest is Docker Desktop (`docker compose up -d`).
This scaffold machine had no Docker/Postgres; see
[`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) for the options.

```bash
cp .env.example .env          # then edit secrets
docker compose up -d          # Postgres + MinIO   (needs Docker)
make install                  # python venv + domain-svc deps
make migrate                  # apply Alembic migrations
make api                      # FastAPI on :8000   (/health, /ready, /docs)
make web-install && make web  # Next.js review UI on :3000
```

`make help` lists every target.

## Phase 1 milestones

1. Repository + local environment ✅
2. PostgreSQL + Alembic baseline ✅
3. Canonical schema ✅
4. Source-document / provenance system ✅
5. Raw ingestion / staging framework ✅
6. Rajasthan migration (117 rows) end-to-end ✅
7. Validation + data-quality reporting ✅
8. Review queue backend ✅
9. Review queue UI ✅
10. Deduplication candidates ← **next**
11. Repeatable reingestion (`make reingest`)
12. Tests + documentation

## Data & privacy

Source workbooks contain **commercially sensitive** commission notes and are
**git-ignored** — they are immutable inputs read from `SOURCE_DATA_DIR`, never
committed or modified. Commission/margin data is isolated in a separate table
visible only to `owner`/`ops_manager` (see `DECISIONS.md` D-0002).
