# Troubleshooting

## No Docker / no local Postgres on this machine

The Phase-1 scaffold was created on a machine with Python, Node and Git but
**no Docker and no local Postgres**. Milestones that need a live database
(ingestion runs, review approvals, dedup) require one of the following. Pick one:

### Option A — Docker Desktop (recommended, matches the spec)
Install Docker Desktop, then:
```bash
docker compose up -d      # starts Postgres 16 (pgvector) + MinIO
make migrate
```
`DATABASE_URL` in `.env` already points at `localhost:5432`.

### Option B — Native PostgreSQL 16
Install PostgreSQL 16 (with contrib: `pg_trgm`, `btree_gist`, `citext`).
`pgvector` is optional in Phase 1 — keep `RV_ENABLE_PGVECTOR=0` if unavailable.
Create the database and set `DATABASE_URL` accordingly:
```bash
createdb rootsvida_tms
# edit .env: DATABASE_URL=postgresql+psycopg://<user>:<pass>@localhost:5432/rootsvida_tms
make migrate
```

### Option C — Managed Postgres (e.g. Neon / Supabase, ap-south-1)
Create a Postgres 16 instance, copy its connection string into `DATABASE_URL`
(add `+psycopg` after `postgresql`), then `make migrate`. `pgvector` is available
on Neon/Supabase — you may set `RV_ENABLE_PGVECTOR=1`.

> Until a database is reachable, `/health` still returns `ok` (liveness), but
> `/ready` reports `degraded` (it probes the DB), and DB-backed tests are skipped.

## `make` not found on Windows
Git Bash may not ship GNU `make`. Either install it (`choco install make`) or run
the underlying commands from the Makefile directly (they are plain shell).

## Alembic can't import `app`
`db/env.py` adds `services/domain-svc` to `sys.path`. Run Alembic from the `db/`
directory (the Makefile targets already `cd db`).

## Unicode / rupee symbol errors in the console (Windows)
Set `PYTHONUTF8=1` (and `PYTHONIOENCODING=utf-8`) before running ingestion so
`₹` and emoji in source cells don't crash the terminal encoder.
