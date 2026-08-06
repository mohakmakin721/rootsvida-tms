# RootsVida TMS — local manual testing guide

How to start everything and manually test, on this Windows machine. Three moving
parts: **Postgres/MinIO (Docker)**, the **API** (`:8000`), and the **web app**
(`:3000`). Start them in that order.

Commands are shown for **PowerShell** (the primary shell). Each long-running server
wants **its own terminal window** — don't background them if you want to watch logs.

---

## 0. One-time / prerequisites

- Docker Desktop running.
- Python 3.13 with deps installed; Node 20 with `apps/web` deps installed
  (`cd apps/web; npm install` — only if `node_modules` is missing).
- `.env` at the repo root (already present). Default owner password is
  `change_me_owner` unless you changed `RV_OWNER_PASSWORD`.

---

## 1. Database + object store (Docker)

```powershell
cd E:\Rootsvida
docker compose up -d
```

Postgres → host port **5433** (a native Postgres owns 5432, so always 5433).
MinIO → 9000/9001. Check they're healthy:

```powershell
docker ps --filter name=rootsvida
```

---

## 2. Apply migrations (schema up to date)

```powershell
cd E:\Rootsvida\db
python -m alembic upgrade head
python -m alembic current   # should print 0018_milestone_kinds (head)
```

## 3. Seed the org, tax rules, roles and owner user (idempotent — safe to re-run)

```powershell
cd E:\Rootsvida
python scripts\seed_org.py
```

This guarantees the org, the 3 GST place-of-supply rules, the **5 built-in roles**
(owner / ops_manager / sales / accounts / readonly) and the **owner login** exist.

---

## 4. Start the API — Terminal A

```powershell
cd E:\Rootsvida\services\domain-svc
$env:PYTHONUTF8=1
python -m uvicorn app.main:app --reload --port 8000
```

- Interactive API docs: **http://localhost:8000/docs**
- Health check: **http://localhost:8000/api/v1/ping** → `{"status":"ok","api":"v1"}`
- `$env:PYTHONUTF8=1` avoids console errors on the `₹` symbol.
- `--reload` restarts the API when you edit backend code.

## 5. Start the web app — Terminal B

```powershell
cd E:\Rootsvida\apps\web
npm run dev
```

- App: **http://localhost:3000** (redirects to `/login` until you sign in).
- If you had previously run `npm run build`, delete the prod bundle first, or the
  dev server misbehaves: `Remove-Item -Recurse -Force .next` then `npm run dev`.

---

## 6. Log in

Open **http://localhost:3000** → you'll land on `/login`.

| Field | Value |
|---|---|
| Email | `owner@rootsvida.local` |
| Password | `change_me_owner` (or your `RV_OWNER_PASSWORD`) |

The owner has every permission, so you can reach every screen. To test what a
narrower role sees, create a user with that role (see §7.3) and log in as them
(use a private/incognito window so both sessions coexist).

> If login says "Invalid email or password", first confirm the **API on :8000** is
> up (§4) — the web app talks to it. The login screen distinguishes "API down"
> from "bad credentials".

---

## 7. What to test (this session's changes)

### 7.1 SAARC removed (traveller class)
- Go to **Builder** (`/builder`) → **Traveller groups** → add a group → open the
  **Class** dropdown. It should list only **foreign** and **indian** (no saarc).

### 7.2 Delete users
- **Home → Users & roles** (`/users`). Each user row has a **Delete** action
  (with a confirm click). You **cannot** delete yourself (shows `—`) or the last
  remaining admin (the API blocks it with a message).

### 7.3 Dynamic roles & permissions
On **`/users`**, below the users table:
- **Roles & permissions matrix** — tick/untick a permission for any role; it saves
  immediately. The **Owner** row is locked to all-on (can't be reduced).
- **+ New role** — create a custom role (e.g. "Reservations"), choose its
  permissions, Create. It appears in the matrix and in the user role dropdowns.
- **Delete** a custom role — allowed only if no user holds it (built-ins can't be
  deleted).
- **Add a user** with a role, then log in as them (incognito) to confirm the gate:
  e.g. a role **without** `suppliers.manage` can't add/edit suppliers; without
  `costing.view` the `costing.xlsx` download is forbidden; without `users.manage`
  the "Users & roles" link is hidden.

### 7.4 Builder — pick a supplier, auto-fill the rate
- **Builder** → add a traveller group + a markup rule + a day → **+ Add cost**.
- On the cost line, use **"Find supplier / hotel…"** → pick a supplier → choose one
  of its rates → the amount auto-fills and the live pricing (right sidebar) updates.
- If the hotel/rate isn't there: **"+ New supplier"** (name, kind, meal plan,
  occupancy, amount) or **"+ Rate"** on an existing supplier → it's saved and used,
  and shows up in the supplier book afterwards.
- (Adding a supplier needs the `suppliers.manage` permission — the owner has it.)
- Manual amount entry still works as a fallback ("or … manually").

### 7.5 Dynamic costing workbook (Inputs / Cost build-up / Rates applied / Hotels)
1. In the Builder, build an itinerary (link some hotel/meal/activity rates via 7.4)
   and **Save itinerary** → open the project.
2. In the project workspace, **price it into a quote**, then click **Costing** on
   the quote card to download `costing-<code>-vN.xlsx`.
3. Open it in Excel. Sheets: **Inputs**, **Cost build-up**, **Rates applied**,
   **Hotels & meal plans**. The **yellow** cells are editable — change pax, a
   markup %, GST %, the FX rate, or a room rate and every total recalculates. The
   "Engine (authoritative)" block shows the frozen figures to cross-check against.

### 7.6 Builder — vendor suggestions are filtered by cost kind
- Builder → **+ Add cost**. Change the cost **kind** and use "Find vendor…": a
  **guide** cost only suggests guide vendors, a **stay** only hotels/homestays, a
  **transport** only transport vendors, a **meal** only meal vendors, etc. "+ New
  vendor" defaults to the matching kind.

### 7.7 "Vendor" wording
- The old "Supplier & rate browser" is now **Vendor & rate browser** everywhere —
  home card & nav ("Browse vendors"), the browser title, "+ Add vendor" / "Edit
  vendor", the search placeholder, and the builder's "Find vendor…" picker. (The
  URL stays `/suppliers` and the API is unchanged — internal only.)

### 7.8 Type-aware vendors (add/edit adapts to the kind)
On **Vendor & rate browser** (`/suppliers`), open or add a vendor:
- **Kind = hotel / homestay** → Room types + meal-plan/occupancy rates; a
  "Property type" field. (As before.)
- **Kind = transport** → a **Transport rates** section: vehicle class/model/seats,
  pricing **basis** (per-day-8hr-80km, per-km, …), amount. No room types/meal plan.
- **Kind = guide** → a **Guide rates** section: languages, per-day / per-half-day,
  specialisation.
- **Kind = activity** → an **Activity rates** section: per-pax price **by
  nationality** (Indian vs foreign) + optional child price.
- **Kind = meal / misc / permit / …** → a simple amount rate.
Add a rate in each and confirm it lists; the freshness badge + rate count on the
list row roll up across whatever rate type the vendor uses.

---

## 8. Quick API smoke test (optional, without the browser)

```powershell
# login -> capture the token
$body = '{"email":"owner@rootsvida.local","password":"change_me_owner"}'
$tok = (Invoke-RestMethod -Uri http://localhost:8000/api/v1/auth/login -Method Post -ContentType application/json -Body $body).token
$h = @{ Authorization = "Bearer $tok" }

Invoke-RestMethod -Uri http://localhost:8000/api/v1/roles -Headers $h            # roles + permissions
Invoke-RestMethod -Uri http://localhost:8000/api/v1/roles/permissions -Headers $h # the catalog
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/suppliers?kind=hotel&limit=5" -Headers $h
```

Or just use **http://localhost:8000/docs** — click **Authorize**, paste the token,
and try any endpoint.

---

## 9. Stopping / restarting

- Stop a server: **Ctrl+C** in its terminal (Terminal A / B). Prefer Ctrl+C over
  force-killing the PID — with `--reload`, killing only the parent can orphan the
  worker that still holds port 8000. If `:8000` seems stuck after a hard kill, find
  the orphan: `Get-CimInstance Win32_Process -Filter "Name='python.exe'"` → stop the
  `multiprocessing.spawn` child, then restart.
- Stop the database: `docker compose stop` (keeps data) or `docker compose down`
  (removes containers; data persists in the named volume).
- After pulling new backend code that adds a migration: re-run §2 (and §3 if seed
  logic changed), then restart the API.

## 10. Troubleshooting

| Symptom | Fix |
|---|---|
| Login "Invalid email or password" | Is the API (:8000) up? (§4) |
| Web pages 500 / stale | `Remove-Item -Recurse -Force apps\web\.next`, restart `npm run dev` |
| `₹` breaks the API console | Set `$env:PYTHONUTF8=1` before uvicorn (§4) |
| Port 5432 vs 5433 confusion | The app uses **5433**; a native Postgres owns 5432 |
| Migration not applied | `cd db; python -m alembic upgrade head` |
| Forgot the owner password | Rotate `RV_OWNER_PASSWORD` in `.env`, re-run `seed_org.py` (only sets it on first create) — or reset via another owner on `/users` |
