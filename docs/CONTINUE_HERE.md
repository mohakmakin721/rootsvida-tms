# RootsVida TMS — development handoff & session log

**Purpose:** bootstrap a new chat/session to continue building RootsVida TMS.
This is a faithful development log (what was built, every commit, the commands, the
decisions, the state) — not a verbatim message transcript. Read this top-to-bottom
and you have everything to resume.

**As of:** git HEAD `14bcad5` · 60 commits · **221 tests passing** · migrations
through `0012` · Phase 1 ✅ · Phase 2 ✅ · Phase 3 ✅ · Phase 4 ✅ · **Security
hardening ✅** (whole API behind auth + role gates; web login flow; users admin).
Next: Phase 5 (agentic itinerary drafter).

---

## 1. What this project is

**RootsVida TMS** — a Travel Management System for Rootsvida Experiences & Tours.
Built in strict phases. **North-star product (owner):** for **any destination**,
create a **project-based itinerary**, generate its **related invoices**, and
**track the project timeline**. Flow: *Project → Itinerary (AI-drafted, structured,
DB-first) → priced Quote (deterministic) → Invoice (GST) → project timeline.*

**Founding rules (never violate):**
- **AI never owns money (D-0001).** Determinism owns all arithmetic/pricing/tax/
  rounding. LLMs only *select inputs* and write prose. No number field is ever
  populated by an LLM.
- **Nothing auto-publishes.** Candidates flow into a human **review queue**; only a
  human approval promotes/merges data.
- **Provenance + idempotency everywhere.** Every rate traces to a source; every
  pipeline step upserts (safe to re-run).
- **Cost-conscious / FOSS-first (D-0012, revised).** Prefer free, open-source,
  self-hostable tools; a paid service is OK only when genuinely needed for reliable
  operation — and **always ask the owner before adopting any paid service / spend.**
  Anthropic LLM is pre-approved for itinerary drafting but stays dormant/opt-in.

## 2. Environment & connection

- Repo root: `E:\Rootsvida` (Windows; Git Bash + PowerShell). Monorepo.
- **Postgres 16** in Docker: container `rootsvida-db`, **host port 5433** (a native
  Postgres owns 5432 — always use 5433). MinIO on 9000/9001. Migrations through `0008`.
- DB: host `localhost`, port **5433**, db `rootsvida_tms`, user `rootsvida`,
  password `change_me_in_local_env`. `DATABASE_URL` is in `.env`.
- Git identity: Mohak Makin. Work on `master` (solo local repo; all work committed
  there).
- Python 3.13 present; deps installed (fastapi, sqlalchemy, alembic, psycopg,
  openpyxl, hypothesis, pytest, ruff, mypy). Node 20 for `apps/web`.
- Source workbooks (git-ignored, D-0006) live in repo root: `Hotels Database.xlsx`,
  `Vendors.xlsx`, `Jaipur_Dynamic_Costing_Workbook_Revised.xlsx`.

## 3. Command reference (how to run everything)

```bash
# --- database (once; container may already be up) ---
docker compose up -d                          # Postgres + MinIO
cd db && python -m alembic upgrade head        # apply migrations (through 0007)
cd .. && python scripts/seed_org.py            # org + GST identity + 3 tax rules (idempotent)

# --- ingestion pipeline (Phase 1) ---
python -m ingestion.cli reingest               # rebuild everything from source (idempotent)
python -m ingestion.cli ingest --sheet Rajasthan
python -m ingestion.cli dedup                  # queue duplicate suppliers
python -m ingestion.cli report                 # data-quality report

# --- quality gates (run before every commit) ---
python -m pytest -q                            # 154 tests (from repo ROOT)
cd services/domain-svc && python -m ruff check . && python -m mypy app pricing

# --- run the app ---
cd services/domain-svc && python -m uvicorn app.main:app --reload --port 8000   # API :8000 (/docs)
cd apps/web && npm run dev                     # web UI :3000  (/review works today)

# --- auth (self-hosted; seeded owner user) ---
curl -s localhost:8000/api/v1/auth/login -H 'content-type: application/json' \
  -d '{"email":"owner@rootsvida.local","password":"change_me_owner"}'   # -> {token,...}
# then send: Authorization: Bearer <token>  (rotate RV_OWNER_PASSWORD in .env)

# --- inspect the DB ---
docker exec -e PGPASSWORD=change_me_in_local_env rootsvida-db \
  psql -U rootsvida -d rootsvida_tms -c "\dt"
# native client (PG18): "/c/Program Files/PostgreSQL/18/bin/psql.exe" -h localhost -p 5433 -U rootsvida -d rootsvida_tms
```

Migrations run from `db/`; tests run from repo root; `ruff`/`mypy` from
`services/domain-svc`. On Windows set `PYTHONUTF8=1` if the console chokes on `₹`.

## 4. Full commit history (the authoritative build log)

```
Phase 1 — data-governance foundation (canonical DB + ingestion + review):
 f0ef61c M1 repository + local environment
 327a146 M2 PostgreSQL + Alembic baseline
 0de73df M3 canonical schema
 28b8f9f M4 provenance + staging layer
 4a01eaf M5 raw ingestion / staging framework
 bd10920 M6 Rajasthan migration (staged rows -> canonical suppliers)
 44b6659 M7 data-quality validation + reporting
 a23080f M8 review queue backend (model + service + REST API)
 42871d8 M9 review queue UI (Next.js)
 d497109 M10 deduplication candidates + human-gated merge
 c9b7611 M11 repeatable reingestion (make reingest)
 4af6585 M12 tests + documentation (Phase 1 complete)
 9554364 docs: Phase 1 handoff
Phase 2 — deterministic pricing engine (pure lib, no I/O):
 143a922 M1 money primitives (Decimal, ROUND_HALF_UP)
 26229cf M2 domain model (typed inputs + outputs)
 eade9b9 M3 cost pass (accommodation + shared + direct)
 5379cb6 M4 sell pass (markup, tax, round once, roll up)
 28a3441 M5 GOLDEN Jaipur reproduces to the rupee
 cf90ebc M6 gross_nearest_100 + GOLDEN invoice TP10
 f95bbdb M7 GST place-of-supply resolver + tax rules in DB
 7411bf4 M8 minimum-margin guardrail
 c41692c M9 property + snapshot tests + docs (Phase 2 complete)
 6021d36 docs: Phase 2 handoff
 94bab07 / 586acbf docs: D-0012 (cost policy, revised)
 3fac9d2 chore: gitignore local instruction/brief docs
Phase 3 — web app: itineraries & quotes (IN PROGRESS):
 56da5a0 M1 itinerary/quote data model + migration 0007 (+ quote immutability trigger)
 f184588 M2 pricing bridge (DB itinerary -> engine; reproduces Jaipur through the DB)
 2361435 docs: itinerary-drafting spec + LLM prompt (dormant/opt-in)
 5c8a0fd M3 quote issuance + frozen snapshot
 31fc8c9 M4 REST API for projects, itineraries, quotes
 6ca34aa docs: add CONTINUE_HERE handoff/session log
 b866cda M5 self-hosted auth + roles (FOSS) + migration 0008 (users.password_hash)
 eddacb8 docs: update CONTINUE_HERE through Phase 3 M5 (auth)
 4e7f9ca M6 supplier & rate browser UI (search/filter + freshness badges)
 aac2603 docs: update CONTINUE_HERE through Phase 3 M6 (supplier browser)
 6ff1c95 M7 itinerary builder UI + live pricing preview (savepoint, persists nothing)
 a2c9be8 docs: update CONTINUE_HERE through Phase 3 M7 (itinerary builder)
 ca03ae0 M8 backend — clients + project continuity + markup CRUD + any-currency FX (migration 0009)
 a70ba56 M8 frontend — client intake, markup manager, state/currency pickers, tooltips
 1b1f4d6 perf(builder): scope live preview to itinerary fields; docs through M8
 138db5b M9 backend — multi-currency quotes (migration 0010) + list-itineraries endpoint
 35fbbec M9 frontend — projects & quotes workspace (create/issue/revise, breakdown)
 ca1d182 docs: update CONTINUE_HERE through Phase 3 M9
 3fd9884 M10 backend — first-class project timeline (migration 0011, milestones)
 c78172c M10 frontend — timeline UI (status stepper, travel window, milestones); Phase 3 exit test green
Phase 4 — documents (IN PROGRESS):
 4602504 P4-M1 GST invoice record — gapless numbering + immutable + credit notes (migration 0012)
 5857160 P4-M2 invoice PDF (ReportLab) + GET /invoices/{id}/pdf
 c405b95 P4-M2 frontend — invoices in the project workspace (generate / PDF / credit note)
 28d9b8f docs: CONTINUE_HERE through Phase 4 GST invoice
 6e8d8dd P4-M3 client proposal PDF (build_proposal + proposal_pdf; no internal figures)
 1b1da83 docs: CONTINUE_HERE through Phase 4 client proposal
 97375d6 P4-M4 internal costing XLSX (openpyxl; build-up + margin; Phase 4 complete)
 8f9bfda docs: Phase 4 complete
Security hardening:
 a51bc04 auth required across API (current_org_id ← current_user) + role gates + test_authz
 a9054f8 web login flow (login page, httpOnly cookie, middleware Bearer injection + page gate)   <-- HEAD
```

## 5. Repo layout (where things are)

| Path | What |
|---|---|
| `services/domain-svc/app/models/` | SQLAlchemy models (canonical, provenance, review, tax, itinerary, quote, client, project_milestone, **invoice / document_counter**) |
| `services/domain-svc/app/services/` | `review`, `merge`, `tax` (place-of-supply), `pricing_bridge`, `quote`, `auth`, `suppliers` (browse, D-0002-safe), `freshness` (pure badge classifier), `itinerary` (build graph from a draft), `preview` (price a draft, savepoint-rollback, persists nothing) |
| `services/domain-svc/app/security/` | Self-hosted auth primitives: `passwords` (PBKDF2), `tokens` (HMAC) |
| `services/domain-svc/app/api/v1/` | FastAPI routers: `auth`, `review`, `suppliers`, `markup_rules` (CRUD), `clients`, `projects`, `itineraries`, `quotes`, `invoices` (+ PDF), `pricing` (live preview) |
| `services/domain-svc/pricing/` | **Pure** deterministic pricing engine (`money`, `model`, `engine`, `tax`) |
| `ingestion/` | Ingestion CLI + pipeline (`staging`, `normalize`, `migrate`, `dedup`, `quality`, `reingest`) |
| `db/migrations/versions/` | Alembic migrations `0001`–`0007` |
| `apps/web/` | Next.js UI (`/review` queue; `/suppliers` browser; `/builder` client intake + itinerary builder + live sidebar; `/projects` + `/projects/[id]` quote workspace **with timeline**: status stepper, travel window, milestones) |
| `tests/` | 210 tests (pytest, from repo root) |
| `docs/` | DECISIONS, DATA_DICTIONARY, INGESTION, PRICING, ITINERARY_DRAFTING, TROUBLESHOOTING, PHASE{1,2}_HANDOFF |

## 6. Golden facts (must always reproduce)

- **Jaipur quote** (Jaipur_Dynamic_Costing_Workbook): Foreign Single **65,597** ·
  Foreign Double **47,303** · Indian Double **26,956** · group **4,03,327** · profit
  **67,277** · USD@95 **4,245.55** · base costs 54,324.60 / 39,174.60 / 23,338.89 ·
  **true margin 12.52%** (on ex-tax revenue). Tests: `test_golden_jaipur.py`,
  `test_pricing_bridge.py`, `test_api_itinerary_quote.py`.
- **Invoice REPL/2627/TP10** (gross_nearest_100): taxable **1,61,619.05** · CGST
  **4,040.48** · SGST **4,040.48** · rounding **−0.01** · total **1,69,700.00**.
  Test: `test_golden_invoice_tp10.py`.
- **GST place-of-supply (D-0013):** seller Uttarakhand (state 05, GSTIN
  05AANCR1978G1Z1), HSN 998555 @5%. intra→CGST+SGST · inter→IGST · international→
  CGST+SGST (owner choice, CA-confirmable, overridable). Rules stored in `tax_rules`.

## 7. Architecture decisions (see docs/DECISIONS.md for full text)

D-0001 AI never owns money · D-0002 commission isolated in `supplier_commercials`,
auth deferred · D-0006 source workbooks git-ignored · D-0007 no live LLM in Phase
1/2 · D-0008 NULL room_type exempt from no-overlap · D-0009 property sheets →
unverified *prospects*, not rates · D-0010 review queue is a decision ledger ·
D-0011 dedup is fuzzy + human-gated soft merge · **D-0012 cost-conscious, ask
before any paid service** · **D-0013 GST place-of-supply rule set** · **D-0014
self-hosted, dependency-free auth (PBKDF2 + HMAC; no paid auth service)**.

## 8. Roadmap — what's next (depth-first, owner's choice)

**Phase 3 done so far:** M1 data model · M2 pricing bridge · M3 quote issuance +
frozen snapshot · M4 REST API · M5 auth + roles (FOSS) · M6 supplier/rate browser
UI (D-0002-safe) · **M7 itinerary builder UI** (`/builder`: traveller groups, day
strip with presence toggles, stay/shared/direct cost components, live cost sidebar
via `POST /pricing/preview` which prices a draft in a rolled-back savepoint and
persists nothing; reproduces Jaipur golden numbers live) · **M8 client intake +
builder overhaul** (migration 0009 `clients` table with type/contact/notes +
`projects.client_id`; `/clients` autopicker & project-code continuity; markup-rule
CRUD + in-builder manager; preview generalised to any currency (₹ authoritative +
converted figure, D-0001); builder gains client/project intake, named GST-state
picker, currency selector, red required-asterisks + ℹ tooltips) · **M9 quote view /
projects workspace** (migration 0010 `quotes.fx_currency`; `/projects` index +
`/projects/[id]` workspace: price an itinerary into a draft quote with assumptions,
view the full breakdown, **issue** (freeze + valid-until) and **revise** into a new
version; builder save links straight to the project) · **M10 project timeline**
(migration 0011: `projects.status_changed_at`/`travel_start`/`travel_end` +
`project_milestones`; `PATCH /projects/{id}` advances status + travel window;
milestone CRUD; workspace timeline = lifecycle stepper + travel window + milestones
with overdue flags) ✅. **Phase 3 EXIT TEST GREEN**: golden Jaipur rebuilt through
the full app reproduces ₹4,03,327 / 12.52% / USD 4,245.55.
**Phase 3 ✅ COMPLETE (all 10 milestones).**
**Phase 4 — documents (IN PROGRESS):** **GST invoice ✅** — migration 0012
(`document_counters` gapless per-org/kind/FY, `invoices` with a reconcile CHECK +
immutability trigger, `invoice_lines`); `app/services/invoice.py` generates from an
issued quote (tax via the pure `split_tax`, reproduces golden REPL/2627/TP10),
credit notes negate + cancel; `app/services/invoice_pdf.py` (ReportLab) renders the
TAX INVOICE / CREDIT NOTE PDF (number `RV/2026-27/0001`, project code as Ref,
Rs. + Indian grouping, amount-in-words); `/quotes/{id}/invoice`, `/invoices/{id}`,
`/invoices/{id}/pdf`, `/invoices/{id}/credit-note`; UI in the project workspace
(generate / download PDF / credit note). Invoice number format + Ref were owner
choices. **Client proposal PDF ✅** — `app/services/proposal.py` (`build_proposal`:
client-facing view from a quote + itinerary — day-by-day, per-person prices in ₹ +
chosen currency, inclusions from component KINDS so internal cost lines never leak)
+ `app/services/proposal_pdf.py` (ReportLab, branded); `GET /quotes/{id}/proposal.pdf`
(any status); "Proposal" button on each quote card. **Internal costing XLSX ✅** —
`app/services/costing_xlsx.py` reads the quote's frozen snapshot into a 3-sheet
openpyxl workbook (Costing build-up + totals + true margin; Cost inputs; Build-up
trace); `GET /quotes/{id}/costing.xlsx`; "Costing" button on each quote card.
CONFIDENTIAL (shows margin + internal fee lines) — now role-gated (below).
**Phase 4 ✅ COMPLETE.**

**Security hardening ✅** — the whole API is behind auth: `current_org_id` now
derives the tenant from `current_user` (a valid Bearer token), so every org-scoped
endpoint requires login; only `/auth/login` and `/ping` are public. Role gates
(`require_role`): markup-rule CRUD + quote issue + costing.xlsx → owner/ops_manager;
invoice + credit-note → owner/ops_manager/accounts. Web: `/login` page,
Next route handlers `/api/auth/login|logout` set/clear an **httpOnly `rv_token`
cookie**, `middleware.ts` injects the Bearer header on `/api/v1/*` and redirects
unauthenticated pages to `/login`; server components forward the cookie token
(`lib/api.getJSON`). Seeded login: `owner@rootsvida.local` / `RV_OWNER_PASSWORD`.
Tests: `test_authz.py` (real stack: 401 unauth/bad-token, 403 readonly-on-commercial,
login flow). Verified end-to-end through the web app.

**Users admin ✅** — `GET /auth/users` + `PATCH /auth/users/{id}` (owner-only;
can't self-demote/deactivate); web `/users` screen (list + inline role change +
activate/deactivate + add-user form), "Users" link on home for owners. Login route
now distinguishes "API down (:8000)" from "bad credentials".
**Reminder: run BOTH servers** — the API (`uvicorn ... :8000`) AND the web
(`npm run dev` from apps/web :3000). If login says "Invalid email or password",
first check the API on :8000 is up. Seeded login `owner@rootsvida.local` /
`RV_OWNER_PASSWORD` (default `change_me_owner`).
**What's next (owner's choice):** Phase 5 agentic itinerary drafter (dormant; spec
in docs/ITINERARY_DRAFTING.md; outputs in the builder's input format; needs the
pre-approved Anthropic API). Possible follow-ups: token-refresh / longer sessions.
(status enquiry→quoted→confirmed→operating→closed + travel/quote-validity/payment/
invoice dates) + exit test (rebuild Jaipur in the UI → golden numbers). As the UI
lands, tighten `require_role(...)` onto sensitive endpoints (commercial data,
issuing quotes).
**Phase 4:** documents — internal costing XLSX, client proposal PDF, **GST invoice
PDF** (gapless numbering via a Postgres sequence, immutable, credit-note corrections).
**Later:** Phase 5 agent layer (itinerary-draft LLM — spec already in
docs/ITINERARY_DRAFTING.md, dormant/opt-in), Phase 6 WhatsApp, Phase 7 payments,
Phase 8 hardening.

## 9. Working agreements (how the owner likes it)

- **Milestone by milestone**, each ending with: build → tests green → `ruff`+`mypy`
  clean → commit → a **plain-English progress update** (% of phase, what's done in
  non-technical terms, what's next). Owner tracks at a high level.
- Reproduce the golden numbers on any pricing/quote change.
- Commit messages end with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Ask before any paid service. Prefer dedicated tools; keep tests + types green.

## 10. To resume in a new session, say:

> "Continue RootsVida TMS. Read docs/CONTINUE_HERE.md, docs/DECISIONS.md, and the
> PHASE1/PHASE2 handoffs. Phases 1–4 COMPLETE + security hardening done (whole API
> behind auth + role gates + web login; HEAD a9054f8, 220 tests, migrations through
> 0012). Start Phase 5 (agentic itinerary drafter)." — then follow §9.

(In a **Claude Code** session on this machine, per-project memory under
`~/.claude/.../memory/` also persists: product-vision, rootsvida-tms-phase1,
foss-only-constraint, progress-update-style. A plain claude.ai chat won't have
those or the repo — paste this file.)
