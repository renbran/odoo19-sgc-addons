# Docker local test environment

Spin up Odoo 19 + PostgreSQL 15 in Docker, with this module auto-installed, so you can validate install/upgrade behaviour before touching the VPS.

## Prerequisites

- Docker Desktop 4.x+ (Windows/macOS) or Docker Engine + Compose v2 (Linux)
- Docker daemon running (`docker info` should succeed)
- 4 GB RAM free, 5 GB disk free
- Ports 8069 and 8072 free on the host

## Files in this setup

| File | Purpose |
|------|---------|
| `../docker-compose.yml` (module root) | Service definitions for `db` (postgres:15-alpine) and `odoo` (odoo:19.0), volume mounts, port mappings. Auto-installs `sgc_construction_management` on first run. |
| `../odoo.conf` (module root) | Odoo 19 configuration: db connection, addons path, ports, workers, logging. |
| `../.dockerignore` (module root) | Excludes dev artifacts (`__pycache__`, `.git`, `.omc/`, etc.) from the bind mount. |
| `docker/README.md` (this file) | Usage instructions. |

## One-time setup (from the module root)

```powershell
cd D:\01_WORK_PROJECTS\SGC-CONSTRUCTION-MANAGEMENT

# Start in detached mode (db + odoo)
docker compose up -d

# Watch Odoo's first-run install log (Ctrl+C to exit, container keeps running)
docker compose logs -f odoo
```

Watch for the line:

```text
INFO sgc_construction_management: registering assets
...
INFO odoo.modules.loading: Modules loaded.
INFO odoo: HTTP service (werkzeug) running on 0.0.0.0:8069
```

Then open **http://localhost:8069** in your browser and log in with:

- Email: `admin`
- Password: `admin`

The Construction menu should appear with all submenus (Dashboard, Projects, BOQ, WBS Phases, Work Orders, Material Requisitions, Subcontracts, RA Billing, Progress Billing, Quality Checks, Expenses, Site Diaries, Documents, etc.).

## Common operations

| Task | Command |
|------|---------|
| Tail Odoo logs | `docker compose logs -f odoo` |
| Tail Postgres logs | `docker compose logs -f db` |
| Open a shell in the Odoo container | `docker compose exec odoo bash` |
| Open psql in the DB container | `docker compose exec db psql -U odoo -d sgc_test` |
| Re-run the install (after editing manifest, etc.) | `docker compose exec odoo odoo -d sgc_test -i sgc_construction_management --stop-after-init` |
| Upgrade the module after code changes | `docker compose exec odoo odoo -d sgc_test -u sgc_construction_management --stop-after-init` |
| Restart Odoo (after editing odoo.conf) | `docker compose restart odoo` |
| Stop everything, keep data | `docker compose down` |
| Stop everything, wipe all data | `docker compose down -v` |
| Force-recreate from scratch | `docker compose down -v && docker compose up -d` |

## Verifying the install worked

After `docker compose up -d` finishes (and you see "Modules loaded."), check:

1. **App is installed.** Log in, go to **Settings -> Apps**, search "Construction". The "SGC Construction Management" app should show as **Installed**.
2. **Menu shows up.** The left sidebar should have a **Construction** root menu with submenus (Dashboard, Projects, BOQ, Planning, Site, Documents, Procurement, Billing, Quality & HSE, Expenses, Configuration).
3. **Demo data loaded.** With the demo dataset you should see 2 projects (Al Noor Tower, Highway Bridge Expansion) already created.
4. **Dashboard renders.** Click **Construction -> Dashboard**; the OWL dashboard with KPI cards, revenue/cost chart, and UAE map should appear. (Leaflet library loads from `static/lib/leaflet`.)
5. **No tracebacks in logs.** `docker compose logs --tail=200 odoo | Select-String -Pattern "ERROR|Traceback"` should return nothing.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `failed to connect to docker API` | Docker daemon not running | Start Docker Desktop |
| Port 8069 already in use | Another Odoo / app bound to it | Edit `docker-compose.yml` ports mapping `8069:8069` to `8169:8069` (host:container) |
| Module not found at install | Mount path wrong | Confirm you're running `docker compose up -d` from the module directory; the module mounts at `/mnt/extra-addons/sgc_construction_management` inside the container |
| `ModuleNotFoundError: No module named 'xlsxwriter'` | Odoo 19 base image lacks the XLSX dep | The `report_xlsx` dependency module needs xlsxwriter. Either install it in the image (custom Dockerfile) or drop the XLSX report dependency |
| `psycopg2` errors on first install | Healthcheck hasn't passed yet | Wait — `depends_on: db: condition: service_healthy` should prevent this |
| Login fails with "Wrong login/password" | DB exists but admin user wasn't created | `docker compose exec db psql -U odoo -d sgc_test -c "SELECT login, password FROM res_users;"` — if empty, drop the DB and re-install: `docker compose down -v && docker compose up -d` |

## Updating the Odoo image

To pull the latest `odoo:19.0` image:

```powershell
docker compose pull odoo
docker compose up -d
```

To pin to a specific patch version (e.g. `odoo:19.0.20260601`):

```yaml
# docker-compose.yml
services:
  odoo:
    image: odoo:19.0.20260601
```

## What is NOT shipped to the marketplace

The marketplace release zip (created via `release/sgc_construction_management/package/sgc_construction_management_release.zip`) excludes these Docker files. They are dev-only. The staging copy filters them out via the standard runbook patterns plus the `.dockerignore` patterns.

## When you're ready for VPS

Once you've validated:

- Install passes on clean DB
- Upgrade passes after every code change
- No traceback in logs
- All menus open
- All views render
- E2E screenshots captured
- App store description render captured

... tell Claude the VPS subdomain (`test.sgctech.ai`) is ready and Claude will write the nginx vhost, certbot SSL config, and deploy Odoo 19 on the VPS.