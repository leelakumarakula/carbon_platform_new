# Carbon Platform

End-to-end agricultural carbon project platform: farmer onboarding → farm & land data → project →
standard / activity / methodology → MRV, sampling and laboratory → carbon calculation → VVB/ACVA
verification → registry issuance → credit ledger → marketplace → retirement → revenue and farmer payout.
Every step is auditable.

The platform orchestrates external parties (laboratories, VVB/ACVA bodies, registries, banks) through
adapters. It is not itself a laboratory, verifier, registry or certification body.

> **Status:** Phases 1 (Foundation), 2 (Farmer & Farm), 3 (Project) and 4 (Standard / Activity / Methodology) are complete. See [docs/implementation-status.md](docs/implementation-status.md).

## Architecture

Modular monolith (spec §5): Angular SPA → FastAPI (`/api/v1`) → SQL Server, with Redis/Celery workers,
S3-compatible object storage, and adapter interfaces for external systems added in later phases.
Details: [docs/architecture.md](docs/architecture.md).

| Layer | Technology |
|---|---|
| Frontend | Angular 21, TypeScript strict, standalone components, signals, Angular Material |
| Backend | FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic |
| Database | Microsoft SQL Server 2022 (`geography`, `datetime2`, `uniqueidentifier`); administered with SSMS |
| Auth | JWT access token (in memory) + rotating refresh token (httpOnly cookie), RBAC with organization scoping |

## Prerequisites

- Python 3.10+ and Node 22+ (verified with Python 3.10.0 and Node 24.12)
- SQL Server 2019+ (verified on 2022 Developer) and **ODBC Driver 17 or 18 for SQL Server**
- Optional: Docker (for `docker-compose.yml`)

## Folder structure

```
backend/    FastAPI app (api, core, models, schemas, services, repositories, security, audit, seed), alembic, tests
frontend/   Angular app (core, shared, layout, auth, dashboard, admin, farmer, farms, projects, methodologies)
storage/    local-dev document storage (git-ignored contents)
database/   seed / reference-data / scripts / documentation
docs/       architecture, schema, API, roles, security, deployment, status
docker/     Dockerfiles + nginx config used by docker-compose.yml
```

## Environment variables

Copy [.env.example](.env.example) to `backend/.env` and fill it in. Generate secrets with
`python -c "import secrets; print(secrets.token_urlsafe(48))"`. Never commit a real `.env`.

`DATA_ENCRYPTION_KEY` (required) encrypts bank account numbers and keys the identity-number fingerprint.
Generate it with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
Documents are stored under `storage/local-dev` (`STORAGE_BACKEND=local`, development only).

For a local default instance with Windows authentication and TCP/IP disabled, leave `SQL_SERVER_PORT=` empty
and set `SQL_SERVER_TRUSTED_CONNECTION=true`; the driver then connects through shared memory.

## Running without Docker (verified)

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements/dev.txt      # Linux/macOS: .venv/bin/pip
.venv/Scripts/python manage.py setup                   # create DB (RCSI on) + migrate + reference data
.venv/Scripts/python manage.py bootstrap-admin         # first Platform Admin (BOOTSTRAP_ADMIN_* in .env)
.venv/Scripts/python manage.py seed-demo               # optional DEMO data (DEMO_USER_PASSWORD in .env)
.venv/Scripts/python -m uvicorn app.main:app --port 8000

cd ../frontend
npm ci
npx ng serve                                           # http://localhost:4200, proxies /api to :8000
```

- API: http://localhost:8000/api/v1 · Swagger: http://localhost:8000/docs (use **Authorize** with an email + password)
- If ports 8000/4200 are taken, start uvicorn with `--port 8100` and run `ng serve --port 4300 --proxy-config <file>`, where the file points `/api` at `http://localhost:8100`.

### Database setup and migrations

| Command | Purpose |
|---|---|
| `python manage.py create-db` | Create the database if missing; enable READ_COMMITTED_SNAPSHOT |
| `python manage.py migrate` | `alembic upgrade head` |
| `alembic revision --autogenerate -m "..."` | New migration (review it before committing) |
| `alembic check` | Fail if models and migrations have drifted |
| `python manage.py seed-reference` | Sync permissions, the 19 system roles and the platform organization (idempotent) |

Schema changes go through Alembic only (agent rules 4–5).

## Demo accounts

`python manage.py seed-demo` creates five DEMO organizations and one user per role, all marked
`environment = DEMO`. Each account's email is `<name>@demo.carbon.example`, and all share the password `DEMO_USER_PASSWORD`:

| Email prefix | Role | Organization |
|---|---|---|
| admin / security / support / methodology / methodologyqa / platformgis | Platform Admin / Security Admin / Support / Methodology Specialist (author) / Methodology Specialist (approver) / Platform GIS Specialist | platform-wide |
| pm, supervisor, collector, gis, mrv, analyst, qa, registry, credits, finance | developer-side roles | Project Developer A (DEMO) |
| farmer | Farmer | Farmer Producer Group E (DEMO) |
| labtech, labmanager | Lab Technician, Lab Manager | Soil Laboratory B (DEMO) |
| vvb | VVB / ACVA Reviewer | Verification Body C (DEMO) |
| buyer | Buyer | Buyer D (DEMO) |

`seed-demo` also creates 5 DEMO farmers (KYC verified, consent granted, bank account pending verification)
and 10 farms near Nashik: 6 VERIFIED, 1 in GIS review, 2 submitted and 1 draft, with one deliberate boundary
overlap. Sign in as `farmer@…` to see the self-service view of the first farmer's two farms.

It also creates a DEMO catalog (2 standards, 3 activities — illustrative reference entries only) and 2 DEMO
projects on the verified farms: *Nashik soil health pilot* (DATA_COLLECTION, standard and activity selected) and
*Niphad residue retention programme* (taken through the real eligibility review to ACTIVITY_SELECTED). No
credit is calculated, verified or issued.

Phase 4 adds 2 DEMO methodologies (`DEMO-ALM-SOC` with versions 1.0, 2.0 and a 2.1 draft; `DEMO-CCTS-SOIL` 1.0). Their rules are
**illustrative, invented for the demo** and labelled as such. The Niphad project is taken through candidate evaluation,
specialist recommendation and confirmation, so its methodology version is locked.

Phase 5 adds DEMO MRV data on the Niphad project: an approved MRV plan (CONFIGURATION_REQUIRED gaps acknowledged — the DEMO
methodology configures no sampling rules), a monitoring period in data collection, two strata, an approved sampling design,
six points assigned to `collector@demo.carbon.example` (sign in on a phone-sized window and open **Field work**), accepted and
submitted field records with DEMO placeholder photos, and a COLLECTING dataset. There are no lab results, calculations or credits.

Demo and live records cannot be mixed; the API rejects it with `ENVIRONMENT_MISMATCH`.

## Tests and checks (exit gate after every phase)

```bash
cd backend
.venv/Scripts/python -m pytest          # runs against <db>_test on the configured SQL Server
.venv/Scripts/ruff check .
.venv/Scripts/mypy app manage.py
.venv/Scripts/alembic check
cd ../frontend
npx ng test --watch=false               # Vitest
npx ng build
npm run e2e:smoke                       # E2E smoke (API + ng serve running, DEMO data seeded; start the API with
                                        # LOGIN_RATE_LIMIT_PER_MINUTE=100 — the run signs in ~15 times; see e2e/smoke.cjs)
```

## Roles

The 19 roles in spec §4 (plus Platform GIS Specialist, decision D5) are defined in `backend/app/security/permissions.py`. See
[docs/roles-permissions.md](docs/roles-permissions.md). Phase 2 added the farmer and farm permissions to the
field, project, GIS, QA, MRV and finance roles, and `farmers.self` to Farmer. Phase 3 added `projects.*` and `standards.manage`; Phase 4 added `methodologies.*`; Phase 5 added `mrv.*` and `sampling.*`. Each later phase adds its module's permissions.

## Workflow

Every workflow entity has an explicit state machine (`app/core/state_machine.py`, `app/services/workflows.py`).
Each transition is validated, then written to `workflow_events` and `audit_logs`. Audit tables are append-only,
enforced by database triggers. The farmer and farm workflows are described in [docs/farmer-workflow.md](docs/farmer-workflow.md), the project
workflow in [docs/project-workflow.md](docs/project-workflow.md), methodology selection in
[docs/methodology-engine.md](docs/methodology-engine.md), MRV in [docs/mrv-workflow.md](docs/mrv-workflow.md) and
[docs/sampling-workflow.md](docs/sampling-workflow.md), lineage in [docs/data-lineage.md](docs/data-lineage.md).

## External integrations

Phase 2 adds the `ObjectStorage` (local) and `MalwareScanner` (signature) adapters; S3 and a real antivirus engine are pending. Adapter interfaces for satellite, lab, VVB, registry, payment, notification and identity providers
are added in their phases, configured by `*_PROVIDER` variables. A mock confirmation is never treated as real.

## Production deployment

See [docs/deployment.md](docs/deployment.md). In short: `APP_ENV=production`, HTTPS with
`REFRESH_COOKIE_SECURE=true`, secrets in a secret store, Redis-backed rate limiting before running more than
one API worker, and a least-privilege SQL login.
