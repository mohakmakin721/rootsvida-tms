# Architecture Decision Log — RootsVida TMS

One row per decision. Newest first. A new developer should be able to read this
and understand *why* the code looks the way it does without asking.

Format: **ID · Date · Status** — Decision, Context, Consequence.

---

## D-0007 · 2026-07-29 · Accepted
**No live LLM calls in Phase 1.**
- **Context:** The plan (Part 1 §1.2 Tier B) designs an LLM-assisted price-parsing
  stage. Phase 1's job is the data-governance foundation, not AI.
- **Decision:** The Tier-B pipeline is *wired but dormant*. `RV_ENABLE_LLM=0`.
  No Anthropic API calls are made during Phase 1. Price strings are preserved as
  `raw_price_text` and classified mechanically; structured extraction is deferred.
- **Consequence:** Zero LLM spend and zero external-API dependency in Phase 1.
  The dormant interface is documented in `docs/INGESTION.md`.

## D-0006 · 2026-07-29 · Accepted
**Monorepo root is the existing `E:\Rootsvida` folder; source workbooks are git-ignored.**
- **Context:** Source files already live at the repo root. They contain
  commercially sensitive commission notes (see D-0002).
- **Decision:** `git init` at the existing folder. `*.xlsx`, `*.xls` and
  `Sample_invoice.pdf` are git-ignored. Ingestion reads them from
  `SOURCE_DATA_DIR` (default: repo root) at runtime; they are treated as
  immutable inputs and never modified or committed.
- **Consequence:** No sensitive business data enters version control. A teammate
  cloning the repo must obtain the workbooks out-of-band and set `SOURCE_DATA_DIR`.

## D-0005 · 2026-07-29 · Accepted
**Local DB engine is a deferred environment choice; Docker Compose is the documented path.**
- **Context:** The scaffold machine has Node, Git and Python but **no Docker and
  no local Postgres**. The stack needs Postgres 16 with `pg_trgm`, `btree_gist`,
  `citext` (all contrib) and optionally `pgvector`.
- **Decision:** Ship `docker-compose.yml` (image `pgvector/pgvector:pg16`) as the
  canonical local environment. Running the DB requires one of: (a) Docker Desktop,
  (b) a native Postgres 16, or (c) a managed Postgres connection string in
  `DATABASE_URL`. `pgvector` is optional in Phase 1 (`RV_ENABLE_PGVECTOR`), since
  semantic search is a later feature.
- **Consequence:** Phase-1 milestones that need a live DB (5–11) are gated on this
  one-time setup. Docker-independent work (schema authoring, ingestion logic,
  offline SQL rendering) proceeds regardless.

## D-0004 · 2026-07-29 · Accepted
**`Jaipur_Dynamic_Costing_Workbook_Revised.xlsx` is a Phase-2 input, present but not used in Phase 1.**
- **Context:** The plan treats this workbook as the pricing-engine product spec and
  the source of the golden fixtures (₹65,597 / ₹47,303 / ₹26,956 / ₹4,03,327 /
  profit ₹67,277). It was supplied on 2026-07-29.
- **Decision:** Left untouched in Phase 1. It is not ingested into the canonical
  DB; it becomes the golden-fixture source when the deterministic pricing engine
  is built in Phase 2.
- **Consequence:** No pricing logic is implemented now (Part 1 §36 forbids it).

## D-0003 · 2026-07-29 · Accepted
**Filename drift recorded: `Hotels Database.xlsx` (space), not `Hotels_Database.xlsx`.**
- **Context:** The specs reference underscored filenames; the on-disk file uses a
  space.
- **Decision:** Ingestion config keys off the real on-disk names and records a
  SHA-256 per source document so a later rename/edit is detectable.
- **Consequence:** No ambiguity about which physical file was ingested.

## D-0002 · 2026-07-29 · Accepted
**Auth deferred to Phase 3; commercial data isolated structurally now (Option A).**
- **Context:** Part 2 §8.3 requires commission/margin data to be invisible below
  Ops Manager. Two options: (a) Postgres RLS keyed on a real login, or (b) a
  separate `supplier_commercials` table. Phase 1 is a single-operator internal
  curation tool; standing up Clerk + MFA + RLS now is setup cost for a door only
  the owner walks through this month.
- **Decision (user-approved 2026-07-29):** Use the **stronger structural option
  (b)** now — commission/margin live in a separate `supplier_commercials` table
  that ordinary code and (future) agent tools never read. Role-awareness is a
  server-side setting (`RV_CURRENT_ROLE`). Real auth (Clerk/Better-Auth), MFA and
  Postgres RLS land in Phase 3. Every table carries `org_id` so RLS is additive,
  not a rewrite.
- **Consequence:** Sensitive data is genuinely isolated from day one, not merely
  hidden in the UI. Phase 3 adds login on top without schema changes.

## D-0001 · 2026-07-29 · Accepted
**AI does not own money (foundational).**
- **Context:** Part 1 §0, Part 2 §1. The Jaipur workbook is a correct deterministic
  pricing algebra; the failure mode of AI quoting systems is letting a model do
  arithmetic or invent a rate.
- **Decision:** Determinism owns all money math. LLMs may only *select inputs* and
  write prose. Every quotable rate must trace to a source document + verifier +
  validity window. No rate is auto-published; the review queue is the only path to
  `verified`.
- **Consequence:** The schema makes provenance and lifecycle state (`raw → candidate
  → reviewed → verified → stale → expired → rejected`) first-class, not a boolean.
