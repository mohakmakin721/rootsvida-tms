# RootsVida TMS — deploy to the web (free tier)

Goal: run the app on the internet with **no desktop running** and **no paid
service**. Three free hosts, no credit card on any:

| Piece | Host | Sleeps? | Notes |
|---|---|---|---|
| **Postgres** | **Neon** | no | Persistent serverless PG; has `pgvector`/`pg_trgm`/`citext`. |
| **FastAPI backend** | **Render** (free web service, Docker) | yes (~50s cold start) | Built from `Dockerfile` + `render.yaml`. |
| **Next.js frontend** | **Vercel** (Hobby) | no | Root directory `apps/web`. |

**Why there's no CORS/cookie setup:** the browser only ever talks to the Vercel
domain. `next.config.mjs` rewrites `/api/v1/*` to the backend **server-side**, so
requests are same-origin and the `rv_token` cookie stays on the Vercel domain.

> Nothing is public. The GitHub repo is **private**; the deployed app sits behind
> the login screen. Only the login page is reachable without a session.

> **Vercel free-tier caveat:** Vercel's "Hobby" plan is, per their ToS, for
> **non-commercial** use. It's commonly used for small internal/business tools and
> works fine technically, but if you want a free host that explicitly permits
> commercial use, **Cloudflare Pages** is the alternative (free, commercial OK).
> It needs a Next.js adapter (`@cloudflare/next-on-pages`) and some edge-runtime
> tweaks to middleware — more setup than Vercel. Ask and I'll write that path
> instead. The backend (Render) and DB (Neon) are unaffected either way.

---

## 0. One-time: the secret + owner login

Set these when the guide tells you to (Render dashboard). Keep them out of git.

- **`RV_AUTH_SECRET`** (signs login tokens — a leaked/default value lets anyone
  forge a session). Freshly generated for you:

  ```
  rCR_jGvxHZbZhUWYdbtT52xzF9QlJA6X20_G3ycaTLOWmODuiKhGOpCgt9VRbtvm
  ```

  (To make your own instead: `python -c "import secrets; print(secrets.token_urlsafe(48))"`)

- **`RV_OWNER_EMAIL`** — your real login email (e.g. your address).
- **`RV_OWNER_PASSWORD`** — a strong password (NOT the `change_me_owner` default).

The backend seeds/updates this owner user on every boot, so setting these is how
you create your online login.

---

## 1. Push the repo to a private GitHub repo

You have a GitHub account. Create an **empty private** repo (no README) named e.g.
`rootsvida-tms`, then from the repo root:

```bash
git remote add origin https://github.com/<you>/rootsvida-tms.git
git branch -M main
git push -u origin main
```

> If your work is on `master` and you want to keep that name, push `master`
> instead and pick it as the deploy branch in Render/Vercel. `.gitignore` already
> excludes `.env` and the source `*.xlsx` workbooks, so no secrets/data ship.

---

## 2. Database — Neon

1. Sign up at neon.tech (GitHub login is fine), create a project (region near you).
2. Copy the **connection string**. It looks like:
   `postgresql://user:pass@ep-xxx.region.aws.neon.tech/neondb?sslmode=require`
3. **Convert the scheme** for our psycopg driver — change `postgresql://` to
   `postgresql+psycopg://` and keep `?sslmode=require`:
   ```
   postgresql+psycopg://user:pass@ep-xxx.region.aws.neon.tech/neondb?sslmode=require
   ```
   That converted string is your **`DATABASE_URL`** for Render.

Schema + seed are created automatically on the backend's first boot (it runs
`alembic upgrade head` then `scripts/seed_org.py`). See §5 to also bring your
existing local data across.

---

## 3. Backend — Render

1. Sign up at render.com. **New → Blueprint**, connect the GitHub repo. Render
   reads `render.yaml` and proposes the `rootsvida-api` web service (free, Docker).
   - (Or **New → Web Service** manually: runtime Docker, Dockerfile `./Dockerfile`,
     health check `/health`, plan Free.)
2. Set the **environment variables** (dashboard → Environment):

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | your converted Neon URL from §2 |
   | `RV_AUTH_SECRET` | the secret from §0 |
   | `RV_OWNER_EMAIL` | your login email |
   | `RV_OWNER_PASSWORD` | your strong password |
   | `APP_ENV` | `production` |
   | `RV_ENABLE_PGVECTOR` | `false` |

3. Deploy. Watch the logs: you should see migrations apply, the seed run, then
   `Uvicorn running`. Note the service URL, e.g.
   `https://rootsvida-api.onrender.com`.
4. Verify: open `https://rootsvida-api.onrender.com/health` → should return OK.

---

## 4. Frontend — Vercel

1. Sign up at vercel.com. **Add New → Project**, import the GitHub repo.
2. **Root Directory: `apps/web`** (important — it's a monorepo). Framework
   auto-detects as Next.js.
3. Set **environment variables** (both point at your Render backend, with the
   `/api/v1` suffix):

   | Key | Value |
   |---|---|
   | `NEXT_PUBLIC_API_BASE_URL` | `https://rootsvida-api.onrender.com/api/v1` |
   | `API_BASE_URL` | `https://rootsvida-api.onrender.com/api/v1` |

4. Deploy. Open the Vercel URL → you should land on `/login`. Sign in with the
   `RV_OWNER_EMAIL` / `RV_OWNER_PASSWORD` you set on Render.

> First request after the backend has been idle takes ~50s (Render waking). After
> that it's snappy. See §6 to keep it warm.

---

## 5. (Optional) Bring your existing local data online

The steps above start with an **empty** database (just org + GST rules + owner).
To move the suppliers/projects/quotes you already built locally into Neon:

```bash
# 1. Dump the local Docker Postgres (custom format, includes alembic_version):
docker exec -e PGPASSWORD=change_me_in_local_env rootsvida-db \
  pg_dump -U rootsvida -d rootsvida_tms -Fc -f /tmp/rv.dump
docker cp rootsvida-db:/tmp/rv.dump ./rv.dump

# 2. Restore into Neon (run BEFORE the backend's first boot, or it's fine either
#    way since the dump carries alembic_version=head so upgrade is a no-op).
#    Use the plain postgresql:// form of the Neon URL here (not +psycopg):
pg_restore --no-owner --no-privileges --clean --if-exists \
  -d "postgresql://user:pass@ep-xxx.region.aws.neon.tech/neondb?sslmode=require" rv.dump

# 3. Delete the local dump when done:
rm rv.dump
```

If `pg_restore` isn't on your PATH, use the one shipped with PostgreSQL 18:
`"/c/Program Files/PostgreSQL/18/bin/pg_restore.exe"`.

> Do this once. Afterwards the online DB is the source of truth; the local Docker
> DB stays your dev copy.

---

## 6. (Optional, free) Keep the backend warm

Render's free service sleeps after 15 min idle. A free uptime pinger avoids the
cold start: create a monitor at **uptimerobot.com** or **cron-job.org** (both
free) hitting `https://rootsvida-api.onrender.com/health` every 10 minutes.

---

## 7. Post-deploy checklist

- [ ] `RV_AUTH_SECRET` is the long random value (NOT the code default).
- [ ] `RV_OWNER_PASSWORD` is strong (NOT `change_me_owner`).
- [ ] You can log in on the Vercel URL and see your projects.
- [ ] `/health` on the Render URL returns OK.
- [ ] GitHub repo is **private**.
- [ ] (If you migrated data) suppliers/projects show up online.

## 8. Redeploying after code changes

Push to the deploy branch — **both** Render and Vercel auto-rebuild from GitHub.
Migrations run automatically on the backend's next boot.

## What this does NOT include

- The Phase 5 itinerary drafter (LLM) is still dormant — no LLM key is set, so no
  spend. When you want it, a **free** hosted model (Google Gemini free tier or
  Groq) can slot in; that's a separate, owner-gated step.
- Free tiers aren't backed up robustly. Neon keeps recent history, but for real
  business data take an occasional `pg_dump` of Neon as your own backup.
