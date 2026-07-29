# Ingestion guide

How legacy workbooks become curated canonical data in RootsVida TMS. Phase 1
covers the **data-governance foundation**: capture, normalise, and human-review.
No pricing, no invoicing, and **no LLM calls** (D-0007).

## Principles

- **The AI does not own money** (D-0001). Determinism owns all arithmetic; this
  phase does not compute or assert any price.
- **Nothing auto-publishes.** Candidates flow into the `review_queue`; only a
  human decision promotes or merges data.
- **Provenance always.** Every canonical row traces back to the exact source
  cells it came from.
- **Idempotent.** Every step upserts on a natural key, so re-running never
  duplicates. `make reingest` rebuilds the whole thing from source.

## The pipeline

```
source workbook
   │  stage      (ingestion/staging.py)      — verbatim capture
   ▼
source_documents ──< raw_import_rows          (JSONB, one row per source row)
   │  migrate    (ingestion/migrate.py)       — mechanical normalisation, no LLM
   ▼
suppliers ──< supplier_contacts               (unverified "prospects", D-0009)
destinations                                   (fetch-or-create reference data)
   │  dedup      (ingestion/dedup.py)         — fuzzy name+destination match
   │  report     (ingestion/quality.py)       — data-quality summary
   ▼
review_queue                                   (merge_candidate + supplier items)
   │  approve / edit / reject  (app/services/review.py, /api/v1/review-queue)
   ▼
canonical truth (merge applied by app/services/merge.py on approval)
```

### 1. Stage — verbatim capture
`stage_sheet` fingerprints the workbook (SHA-256) into a **`source_documents`**
row (idempotent on `(org, sha256)`), then reads the target sheet and upserts each
data row into **`raw_import_rows`** as `{column: raw_value}` JSONB, keyed on
`(source_document, sheet, row_number)`. Cell values are preserved faithfully;
only dates/times are coerced to ISO strings so they fit JSONB. A stable
`row_hash` lets a re-run detect unchanged rows.

### 2. Migrate — mechanical normalisation
`migrate_sheet` runs a **per-sheet normaliser** (`ingestion/normalize.py`) over
the staged rows and upserts canonical **`suppliers`** + **`supplier_contacts`**,
resolving **`destinations`** as it goes. The staging→canonical link
(`raw_import_rows.normalized_supplier_id`) makes it idempotent. Each row's
`parse_status` records the outcome:

| status | meaning |
|---|---|
| `parsed` | mapped, with a destination |
| `partial` | mapped, but no destination resolved |
| `needs_review` | no usable identity — **not** written to canonical |

Suppliers are created as **prospects** (`status='prospect'`), never verified rates
(D-0009). The rough "Price Range" text stays in staging as raw provenance.

### 3. Dedup — merge candidates
`enqueue_merge_candidates` compares `normalise(name)` within each destination
(difflib similarity, threshold default 0.84) and enqueues each likely pair as a
`merge_candidate` review item. **Never auto-merges** (D-0011).

### 4. Review — the human gate
The `review_queue` holds candidates. A reviewer approves / edits / rejects via the
UI (`apps/web`, `/review`) or the API (`/api/v1/review-queue`). Approving a
`merge_candidate` executes the merge (`app/services/merge.py`): the older supplier
survives, the duplicate's references are repointed, and the duplicate is
**soft-deleted** (reversible).

## Parser tiers (plan §1.2)

| tier | `ParserStrategy` | how |
|---|---|---|
| A | `mechanical` | shared header vocabulary + column mapping (Rajasthan) |
| B | `assisted` | LLM price-string parsing — **DORMANT in Phase 1** (D-0007) |
| C | `bespoke` / `manual` | one-off parser, or re-keyed by hand |

## Commands

```bash
make ingest sheet=Rajasthan   # stage + migrate one sheet
make dedup                    # queue duplicate suppliers as merge candidates
make reingest                 # rebuild EVERYTHING from source (idempotent)
make dq                       # data-quality report
```

All are thin wrappers over `python -m ingestion.cli <cmd>`. `stage` (capture only)
and `--file` / `--threshold` options are available on the CLI directly.

## Adding a new sheet

1. Add a `SheetSpec` to `ingestion/mappings/registry.py` (workbook, header row,
   parser tier).
2. Write a normaliser `normalize_<sheet>(raw) -> NormalizedSupplier | None` in
   `ingestion/normalize.py` and register it in `NORMALIZERS`.
3. `make ingest sheet=<Name>` — or just `make reingest`, which picks up any sheet
   that has both a registry workbook and a normaliser.

## Provenance chain

`source_documents.sha256` → `raw_import_rows` (verbatim) →
`raw_import_rows.normalized_supplier_id` → `suppliers`. Given any canonical
supplier you can find the exact staged row, sheet, row number, and source file it
came from. See [DATA_DICTIONARY.md](DATA_DICTIONARY.md) for the full schema.
