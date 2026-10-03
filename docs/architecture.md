# Architecture

The full target architecture, lifecycle and domain model are in
`DMRV_Carbon_Platform_Architecture.pdf` (in the project's specification folder). This file describes the
code as it exists.

## Shape

```
Angular SPA ──HTTPS/JSON, Bearer JWT──▶ FastAPI /api/v1 ──SQLAlchemy──▶ SQL Server
   │                                       │
   │ httpOnly refresh cookie (path /api/v1/auth)
   │                                       ├─ middleware: request id → limits → secure headers → CORS
   │                                       ├─ routers (thin) → services (rules, state machines, audit) → repositories
   │                                       └─ (later) Celery workers, object storage, external adapters
```

One deployable (modular monolith). Each domain module owns its router, schemas, service, repository and
models; no module reaches into another's tables except through its service.

## Backend layout (`backend/app`)

| Package | Responsibility |
|---|---|
| `core/` | settings, DB engine/session, error envelope, middleware, rate limiter, request context, `StateMachine` |
| `models/` | SQLAlchemy models; `base.py` sets the conventions (UUID PK, `datetime2` UTC, naming convention, `Environment`) |
| `schemas/` | Pydantic request/response models; `common.py` holds pagination, `Email`, `Reason`, `UtcDatetime` |
| `repositories/` | Query building, pagination, whitelisted sorting |
| `services/` | Business rules, permission scoping, status transitions, audit recording, `commit()` |
| `security/` | Permission catalog + system roles, password policy, tokens, `Principal` |
| `audit/` | Audit/workflow/security-event writers, API access-log writer |
| `api/` | `deps.py` (principal, `require()`, context, paging) and versioned routers |
| `rules/` | Pure functions: geometry parsing (GeoJSON/KML to WKT), file-type sniffing, the deterministic methodology applicability engine, seeded sampling-point candidate generation (SQL Server decides containment) |
| `integrations/` | Adapters: `ObjectStorage` (local; S3 pending), `MalwareScanner` (signature; real AV pending), `LimsAdapter` (interface only; `NoLimsAdapter`) |
| `seed/` | Reference data sync, bootstrap admin, DEMO data (accounts, farmers, farms) |

Rules followed: routes contain no DB logic; services take an explicit `RequestContext` so every audit row
records who, from where, which request and why; material changes and their audit rows commit in one
transaction.

## Frontend layout (`frontend/src/app`)

| Folder | Responsibility |
|---|---|
| `core/` | `ApiService`, `ApiError`, auth service/guards/interceptors, permissions, navigation registry, notifications |
| `shared/` | Status badge, page header, state view, reason dialog, form helpers, `PagedList` |
| `layout/` | Shell: side navigation filtered by permissions, user menu, DEMO indicator |
| `auth/`, `dashboard/`, `admin/`, `farmer/`, `farms/`, `projects/`, `methodologies/`, `mrv/` (MRV workspace + mobile field screens), `lab/` (laboratory workspace, test / QA pages, sample detail, result lineage) | Feature pages; each feature has its own models and API service |

`shared/geo-map.ts` wraps Leaflet. The browser only draws and previews shapes; validation and area are
always computed by SQL Server.

The app is zoneless and uses signals; every component is standalone and uses `OnPush`. Business rules stay
on the server. The client only mirrors them (state machines, password policy) for instant feedback.

## Cross-cutting decisions

- **Status machines**: `StateMachine.build(...)` per entity; `record_transition()` validates, writes
  `workflow_events` and `audit_logs`.
- **Multi-tenancy**: role grants are platform-wide or per organization; `Principal.scope_for(permission)`
  returns `None` (all) or the set of organizations to filter by. Out-of-scope records return 404, not 403,
  so their existence doesn't leak.
- **DEMO isolation**: `environment` column (`LIVE`/`DEMO`) on organizations and users; mixing is rejected.
- **GIS**: `geography` (SRID 4326) columns through a custom SQLAlchemy type (`models/gis.py`). Spatial SQL lives in
  `repositories/gis.py`.
- **Versioned history**: land, crop and practice history and boundaries are never updated in place. A new
  version is written, and a filtered unique index guarantees one current row.
- **Documents**: one document service for every module. Each owning module registers a resolver that decides
  access, so documents inherit their parent record's scope.
- **Projects**: `project_service` (project, team, references, periods, workflow) and `project_farm_service`
  (participation, carbon rights, derived boundary). The project boundary is a SQL Server `UnionAggregate` of the
  participating farms' current boundaries, versioned like farm boundaries. Status history is a dedicated
  append-only table in addition to `workflow_events`.
- **Methodologies**: catalog/versioning in `methodology_service`; project selection in `project_methodology_service`, which
  builds facts from project data and runs `rules/methodology_engine.py` (pure, deterministic, versioned engine). The
  engine output is stored as an append-only evaluation; people review, confirm and lock.
- **Laboratory**: `lab_service` (project side: engagements, samples, custody, shipments, read model) and `laboratory_service` (laboratory side: receipt, tests, results, QA, retests). Two routers: `/lab` (project) and `/laboratory` (allow-list `*LabView` schemas built in `lab_mappers`). Custody, QA reviews and approved results are protected by DB triggers.
- **Time**: stored as naive UTC `datetime2`, emitted as ISO-8601 with `Z`.
