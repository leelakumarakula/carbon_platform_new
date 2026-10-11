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
| `calculation/` | Calculation framework (Decimal, deterministic, spec §18 methods) and the methodology-module registry (no module in Phase 7) |
| `reports/` | Deterministic, dependency-free text-only PDF writer (Phase 8A) |
| `seed/` | Reference data sync, bootstrap admin, DEMO data (accounts, farmers, farms) |

Rules followed: routes contain no DB logic; services take an explicit `RequestContext` so every audit row
records who, from where, which request and why; material changes and their audit rows commit in one
transaction.

## Frontend layout (`src/app` in the `carbon_project_frontend` repository)

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
- **Calculation**: `calculation_inputs` (readiness + frozen snapshot), `calculation_service` (workflow), `calculation_qa` (checks) and `calculation_mappers`; the engine reads only the frozen snapshot. Services accept an explicit module resolver (tests pass a TEST-only fixture); the API always uses the application registry.
- **Internal pre-verification (8A)**: `calculation_findings`, `calculation_report`, `calculation_readiness`, `preverification_mappers`; router `calculation_preverification` under `/calculations`. Readiness is re-checked when read and invalidated automatically.
- **VVB / ACVA verification (8B)**: `verification_access` (cross-organization scoping, two-organization audit, document resolver), `verification_service` (assignments, submissions with lazy invalidation, decisions, aggregate project status, lineage), `verification_findings` (findings, corrective actions, evidence), `verification_package` (the VVB allow-list view and manifest-scoped downloads), `verification_mappers`. Routers: `/verification` (project side) and `/vvb` (VVB workspace, allow-list), as for laboratories.
- **Registry & issuance (9A)**: `app/integrations/registry.py` (RegistryAdapter Protocol, canonical dataclasses, ManualRegistryAdapter; adapters selected per registry account, test adapters injected), `registry_access` (scoping, audit, events, immutable document resolvers), `registry_service` (accounts, registrations, eligibility, snapshot, submissions with outbox-style idempotency, reconciliation, period view), `credit_issuance` (issuances, dual confirmation, batches, serial ranges, D5 invariant, corrections), `registry_mappers` (three separated quantities, lineage). Routers: `/registry` and read-only `/credits`.
- **Credit ledger (9B)**: `models/ledger.py` (entries, positions, openings, reservations, transfers, retirements, reversals), `ledger_service` (the engine: `run()` transaction with deadlock retry and double-spend audit, `lock_positions` with UPDLOCK/HOLDLOCK/ROWLOCK, guarded `consume`, `create` with exact sub-range splits, `post`, idempotent replay; openings, reservations with lazy expiry, transfers, retirements, reversals, the 9A `ledger_guard` / `issuance_adjustment`, manual reconciliation), `ledger_mappers` (derived balances, allow-listed holder view, retirement lineage). The adapter declares `transfer_credits` / `retire_credits` / `get_credit_inventory` (MANUAL raises `ManualActionRequired`). Router: the ledger endpoints under `/credits`. Frontend: `/ledger` and `/holdings`. Phase 10 refactored the engine into composable
  `*_in_tx` functions (reserve, release, expire, request / complete / close transfer) that run inside a caller's transaction, plus a link guard
  through which a later phase marks reservations / transfers it owns (the public 9B actions then answer ORDER_LINKED).
- **Marketplace (10)**: `models/marketplace.py` (buyer profiles + append-only KYC reviews, listings, listing documents, orders, order items,
  payments, append-only payment events, refunds), `integrations/payment.py` (PaymentAdapter Protocol, ManualPaymentAdapter, ISO-4217 minor
  units), `marketplace_service` (access helpers, KYC, listings with derived remaining / available), `order_service` (T1 placement, lazy
  expiry, cancellation, T4 delivery wrapper, resolution, confirmation PDF, lineage), `payment_service` (T2 manual recording, provider outbox
  and events, T3 confirmation, reconciliation, refunds), `marketplace_mappers` (allow-listed outputs). Routers: `/marketplace`, `/orders`,
  `/payments` + `/refunds`. Frontend: `/marketplace` (+ `/listings`, `/profile`, `/kyc-review`), `/orders`, `/payments`.
- **Revenue & payouts (11)**:
  - `models/finance.py`: revenue records, revenue-share versions, farm allocation versions / lines, project costs, settlement runs +
    claims, farmer entitlements, payouts, payout transactions, reconciliations, recovery cases.
  - `integrations/payout.py`: PayoutAdapter Protocol, ManualPayoutAdapter.
  - `finance_service`: access helpers, `recognize_in_tx` / `reverse_for_refund_in_tx` (called inside the Phase 10 delivery and refund
    transactions), configuration, costs.
  - `settlement_service`: the pure `calculate_figures` (fin-calc-1), snapshot + hash, claims, verify, approval, recovery cases.
  - `payout_service`: lifecycle, bank re-check under lock, adapter, reconciliation, lineage, summary, self-service.
  - `finance_mappers`.
  - Routers: `/revenue`, `/revenue-share`, `/allocations`, `/costs`, `/settlements` (`api/v1/finance.py`) and `/payouts` (`api/v1/payouts.py`).
  - Frontend: `/finance/revenue`, `/finance/sharing`, `/finance/settlements`, `/finance/payouts`, `/me/payouts`.
- **Background jobs (12A)**:
  - `models/jobs.py`: jobs, append-only attempts, worker heartbeats, SYSTEM actor ids.
  - `workers/registry.py`: allow-list.
  - `workers/job_service.py`: outbox enqueue / publish, SQL claim + lease, execute, retry classification, recovery, operator actions.
  - `workers/handlers.py`: thin adapters to the 9B / 10 expiry functions, orphan scan, retention infrastructure.
  - `workers/celery_app.py`: JSON, late ack, beat schedule.
  - `workers/tasks/*`: one-line task adapters.
  - `workers/operations.py`: read side and status.
  - `workers/heartbeat.py`, `workers/joblog.py`: structured JSON logs.
  - Router: `/jobs`. Frontend: `/admin/jobs`.
  - Processes: API, `celery worker`, exactly one `celery beat`. SQL Server is the record; Redis is transport.
- **Time**: stored as naive UTC `datetime2`, emitted as ISO-8601 with `Z`.
