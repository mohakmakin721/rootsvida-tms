# Architecture Decision Log — RootsVida TMS

One row per decision. Newest first. A new developer should be able to read this
and understand *why* the code looks the way it does without asking.

Format: **ID · Date · Status** — Decision, Context, Consequence.

---

## D-0013 · 2026-07-30 · Accepted
**GST place-of-supply rule set (seller Uttarakhand); rules stored as data.**
- **Context:** RootsVida is registered in **Uttarakhand** (state code 05, GSTIN
  05AANCR1978G1Z1). Invoices must apply the correct GST treatment by place of
  supply; the plan (§1.4) flagged this needs a resolver + per-invoice override +
  CA sign-off. The sample invoice REPL/2627/TP10 charged CGST+SGST to a foreign
  (Chilean) buyer.
- **Decision (user-approved 2026-07-30):** three scenarios —
  - **intra-state** (buyer in Uttarakhand) → CGST 2.5% + SGST 2.5%
  - **inter-state** (another Indian state) → IGST 5%
  - **international** (buyer outside India) → CGST 2.5% + SGST 2.5%, the owner's
    chosen default matching current practice / the sample invoice.
  The rules live in the **`tax_rules`** table (one row per scenario, HSN 998555 @
  5%, `gross_nearest_100` rounding), so a treatment/rate can change without a code
  deploy. `classify_place_of_supply` is a pure function; `resolve_tax_rule` reads
  the DB row; an explicit override with a logged reason wins. The pure pricing
  engine consumes whichever `TaxRule` the resolver selects.
- **Consequence:** place-of-supply is resolved consistently, auditable, and
  editable as data. **Not tax advice** — the international / export-vs-LUT
  position in particular must be confirmed with a CA; it is overridable per
  booking precisely so a corrected position needs no code change.

## D-0012 · 2026-07-30 · Accepted
**Free & open-source, self-hostable only until the project is proven.**
- **Context:** The owner wants zero recurring service spend during build-out;
  paid/managed services are considered only *after* the project succeeds.
- **Decision:** Every component must be FOSS and self-hostable on the local
  machine (or a free tier). This is already true of the whole core stack —
  **PostgreSQL 16, MinIO (S3-compatible object store), FastAPI, SQLAlchemy,
  Alembic, Next.js, Playwright** — all open-source, all runnable via
  `docker compose` with no account or bill. The pricing engine (Phase 2) is pure
  Python with zero external services. The **only** paid dependency anywhere in
  the plan is the Anthropic LLM API, which is already **dormant and optional**
  (D-0007): the system is designed to run fully with every agent switched off, so
  no feature is gated behind paid AI. When extraction/agents are eventually built,
  prefer a free/local option (e.g. Ollama with an open model) or keep the paid
  path opt-in behind `RV_ENABLE_LLM`.
- **Consequence:** No managed Postgres, no cloud object store, no SaaS, no paid
  APIs are required to run or develop RootsVida TMS. Migrating any piece to a paid
  managed service (managed Postgres, hosted LLM, a payment gateway's live keys) is
  a deliberate, success-gated choice recorded as its own future decision — never a
  silent dependency. CI stays on free GitHub Actions minutes; deployment, when it
  comes, targets self-hosting or free tiers first.

## D-0011 · 2026-07-30 · Accepted
**Dedup is fuzzy name+destination detection; merge is soft, reversible, human-gated.**
- **Context:** Plan §1.3 wants duplicate suppliers surfaced as merge candidates,
  never auto-merged. `pg_trgm` is available, but the detection logic benefits from
  being pure and unit-testable without a live DB.
- **Decision:** Detection (`ingestion/dedup.py`) compares `normalise(name)` with
  `difflib.SequenceMatcher` **within the same destination** (threshold default
  0.84); it is a pure function over (id, name, destination) tuples. Each pair is
  enqueued as a `merge_candidate` review item (idempotent per pair). Executing a
  merge (`app/services/merge.py`) happens **only when a human approves** (wired
  into the approve endpoint per D-0010): the older supplier survives, the
  duplicate's references (contacts, room types, rates, staged-row links, and
  commercials when the primary has none) are repointed, and the duplicate is
  **soft-deleted** — nothing is destroyed, so a merge is reversible by clearing
  `deleted_at`. Re-applying is a no-op.
- **Consequence:** `make dedup` surfaced the 4 real Rajasthan duplicate pairs (28
  Kothi, Utsav Camp, Taj Hari Mahal, Samode House) the M7 report flagged, each at
  1.0 confidence, idempotent on re-run. pg_trgm can replace difflib at scale
  without changing the interface.

## D-0010 · 2026-07-30 · Accepted
**The review queue is a decision + audit ledger; producers apply the decision.**
- **Context:** Part 2 §4.6 makes `review_queue` the single human gate. But the
  concrete producers (dedup merges, rate extraction) land in later milestones,
  so wiring type-specific "apply approved candidate to canonical" now would be
  speculative and couple M8 to code that doesn't exist yet.
- **Decision:** M8 builds the review-queue *mechanism* — table, model, service
  (`enqueue` / `list` / `get` / `approve` / `reject` / `edit`), and REST API at
  `/api/v1/review-queue`. Decisions are valid only on a **pending** item (a second
  decision returns HTTP 409) and record who/when/notes. `enqueue` is idempotent
  via a nullable `dedupe_key` (unique per org). Applying an approved candidate to
  canonical is the **producer's** job, implemented alongside each producer (M10
  merges; future rate extraction). `agent_run_id` exists as a plain nullable
  column — its FK to `agent_runs` is deferred to the agent layer (Phase 5).
- **Consequence:** The UI (M9) has a stable, typed API and real content now — the
  bulk `POST /review-queue/import-staging` enqueues the 5 Rajasthan needs-review
  rows as supplier candidates. Nothing auto-writes to canonical from the queue.

## D-0009 · 2026-07-30 · Accepted
**Property sheets migrate to unverified supplier *prospects*, not rates.**
- **Context:** The Rajasthan sheet (M6's target) is a property shortlist —
  name / place / category / type / contact / a rough "Price Range" text /
  remarks — not a rate card. D-0007 keeps price strings unparsed; the governance
  rule makes the review queue the only path to a *verified rate*.
- **Decision:** M6 normalises staged rows **mechanically** (no LLM) into
  `suppliers` + `supplier_contacts` + `destinations` with `status='prospect'`.
  **No `rates` rows are created** and no price is asserted — the "Price Range"
  stays verbatim in `raw_import_rows` as provenance. A row with no usable name is
  marked `parse_status='needs_review'` and is **not** written to canonical.
  Idempotency + forward provenance come from a new
  `raw_import_rows.normalized_supplier_id` link (migration 0004): a re-run updates
  the same supplier instead of duplicating it.
- **Consequence:** Canonical suppliers exist before the review-queue backend
  (M8), while nothing that constitutes a rate/price is auto-published. Verified on
  the real sheet: 117 rows → 112 prospects (3 partial, 5 needs-review), and
  `make ingest sheet=Rajasthan` is idempotent on re-run.

## D-0008 · 2026-07-29 · Accepted
**Rates with NULL room_type_id are exempt from the no-overlap exclusion.**
- **Context:** `rates_no_overlap` (Part 2 §4.1) keys on `room_type_id WITH =`.
  GiST equality treats NULL as distinct, so two rates with NULL `room_type_id`
  for the same supplier/meal_plan/occupancy on overlapping dates do NOT conflict.
  Migrated legacy data often has no room type.
- **Decision:** Keep the spec's constraint exactly as written (do not coalesce
  NULLs to a sentinel — that would change semantics). The exclusion protects
  fully-specified rates; overlaps among room_type-less rates are caught instead by
  data-quality checks and human review, not the DB constraint.
- **Consequence:** The constraint is verified to reject overlaps when a room type
  is set (test_db_canonical). Reviewers must resolve room_type before a rate is
  marked `verified`; documented in the data dictionary.

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
