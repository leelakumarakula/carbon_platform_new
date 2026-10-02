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
| `seed/` | Reference data sync, bootstrap admin, DEMO data |

Rules followed: routes contain no DB logic; services take an explicit `RequestContext` so every audit row
records who, from where, which request and why; material changes and their audit rows commit in one
transaction.

## Frontend layout (`frontend/src/app`)

| Folder | Responsibility |
|---|---|
| `core/` | `ApiService`, `ApiError`, auth service/guards/interceptors, permissions, navigation registry, notifications |
| `shared/` | Status badge, page header, state view, reason dialog, form helpers, `PagedList` |
| `layout/` | Shell: side navigation filtered by permissions, user menu, DEMO indicator |
| `auth/`, `dashboard/`, `admin/` | Feature pages; each feature has its own models and API service |

The app is zoneless and uses signals; every component is standalone and uses `OnPush`. Business rules stay
on the server. The client only mirrors them (state machines, password policy) for instant feedback.

## Cross-cutting decisions

- **Status machines**: `StateMachine.build(...)` per entity; `record_transition()` validates, writes
  `workflow_events` and `audit_logs`.
- **Multi-tenancy**: role grants are platform-wide or per organization; `Principal.scope_for(permission)`
  returns `None` (all) or the set of organizations to filter by. Out-of-scope records return 404, not 403,
  so their existence doesn't leak.
- **DEMO isolation**: `environment` column (`LIVE`/`DEMO`) on organizations and users; mixing is rejected.
- **Time**: stored as naive UTC `datetime2`, emitted as ISO-8601 with `Z`.
