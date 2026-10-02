# Implementation status

| Phase | Scope (spec §47) | Status |
|---|---|---|
| 1 | Foundation: Angular, FastAPI, SQL Server, SQLAlchemy, Alembic, auth, RBAC, organizations, audit, dev setup | **Done** |
| 2 | Farmer & farm (KYC, polygons, history, evidence) | **Done** |
| 3 | Project | Next (awaiting approval) |
| 4 | Methodology | — |
| 5 | MRV / GIS | — |
| 6 | Sample / lab | — |
| 7 | Calculation | — |
| 8 | VVB / ACVA | — |
| 9 | Registry / credits | — |
| 10 | Marketplace | — |
| 11 | Revenue / payout | — |
| 12 | Production hardening | — |

## Phase 1 — delivered

**Login, roles, users, organizations, navigation.** Acceptance criterion 40 (critical actions audited) is in
place for every Phase 1 action.

Backend
- SQL Server schema for spec §7.1 (identity and access) and §7.15 (audit) via Alembic migration `0001`. Status
  columns have CHECK constraints, JSON columns are validated with `ISJSON`, and the audit tables are made
  append-only by `INSTEAD OF UPDATE, DELETE` triggers.
- Auth: bcrypt password policy; login with account lockout and per-IP and per-email rate limiting; a JWT
  access token; and a refresh token stored only as a SHA-256 hash, delivered as an httpOnly SameSite=Strict
  cookie, rotated on every use, with reuse detection that revokes the whole session. Also: logout,
  change-password (revokes other sessions), forced change of temporary passwords, and MFA-ready columns.
- RBAC: permission catalog and 19 system roles in code, synced by `seed-reference`. Grants are platform-wide or
  organization-scoped. `Principal.scope_for()` filters every query by organization. Escalation guards: nobody
  can grant permissions they don't hold, change their own roles or status, or remove the last Platform Admin.
- Admin APIs for users, roles and permissions (custom roles), organizations and members, audit logs, workflow
  events, security events, login audit and sessions (with revoke).
- Status machines for user and organization; transitions are recorded in `workflow_events` and `audit_logs`.
- Platform: request IDs, the standard error envelope, secure headers, CORS, body-size limit, global rate limit,
  the API access log, server-side pagination with whitelisted sorting, and UTC ISO-8601 (`Z`) timestamps.
- `manage.py`: create-db, migrate, seed-reference, bootstrap-admin, seed-demo (DEMO-marked).

Frontend
- Login, change password and profile pages; app shell with permission-filtered navigation and a DEMO
  indicator; dashboard.
- Admin screens: users (list, create, detail with status, roles, password reset, unlock), organizations
  (list, create, detail, members), roles and permissions (system read-only, custom editable), audit log
  (filters, before/after values), and the security center (events, sign-in history, sessions).
- Core: central `ApiService`; auth and error interceptors (silent refresh and retry); route guards (auth,
  guest, permission, forced password change); reusable status badge, page header, loading/error/empty state
  and reason dialog; and a server-paged list helper.

Verification
- Backend: 81 pytest tests against real SQL Server (unit, API, security, multi-tenancy, append-only, seeds);
  ruff and mypy clean; `alembic check` reports no drift.
- Frontend: 28 Vitest tests; the production build succeeds.
- Driven in headless Chrome: admin sign-in, every admin page, reload keeps the session, and the farmer sees
  only the dashboard and is refused admin pages.

## Phase 2 — delivered

**Farmer onboarding and farm data.** Workflow details are in [farmer-workflow.md](farmer-workflow.md).

Backend
- Migration `0002`:
  - 15 Phase 2 tables plus `documents`, `document_versions` and `notifications`; 32 tables in total.
  - CHECK constraints on every status column.
  - Sequences for farmer, farm and agreement codes.
  - The `geography` spatial index.
  - An append-only trigger on `document_versions`.
- State machines:
  - farmer: DRAFT → REGISTERED → KYC_PENDING → KYC_VERIFIED → ACTIVE ⇄ SUSPENDED;
  - farm: DRAFT → SUBMITTED → GIS_REVIEW → VERIFIED / REJECTED → INACTIVE;
  - agreement, bank account and overlap flag.

  Each has readiness checklists and separation of duties.
- KYC with a hashed ID and a duplicate check. Versioned consents and agreements. Fernet-encrypted bank
  accounts with second-person verification. Contacts. Farmer self-service (`/farmers/me`).
- GIS on SQL Server:
  - Draw, GeoJSON or KML input, validated with `IsValidDetailed` and auto-reorientation.
  - The authoritative area comes from `STArea`.
  - Boundaries are versioned.
  - Overlaps are detected with `STIntersects` / `STIntersection` and flagged for review, never rejected
    automatically.
  - Point and radius queries use `STContains` / `STDistance`.
- Ownership and tenure separate from the farmer. Land, crop and practice history with amend and retract
  versioning. Evidence with review.
- Shared document service:
  - checks: content sniffing, size limit, malware hook, SHA-256;
  - versioning, with an append-only trigger;
  - local storage adapter;
  - RESTRICTED handling.
- In-app notifications for review hand-offs.
- DEMO seed: 5 farmers and 10 farms (6 VERIFIED, 1 deliberate OPEN overlap), all `environment=DEMO`, created
  through the real services.

Frontend
- Farmers: list, create, and detail with tabs (profile, KYC, consents, agreements, bank, farms, documents).
  Farmer self-service is a "My farm" area.
- Farms:
  - list and create;
  - detail tabs: overview map, boundary editor, ownership, history, evidence, overlaps, documents.
  - The boundary editor offers click-to-draw, GeoJSON paste and file upload, with a server-side validation
    preview.
  - History offers amend, retract and a versions view.
- Shared: Leaflet map component, readiness panel, documents panel, notification bell.

Verification (exit gate, 2 Oct 2026)
- Backend: **132 pytest tests passed** against SQL Server 2022. ruff clean. mypy clean (85 files).
  `alembic check`: no drift.
- Frontend: **35 Vitest tests passed** (6 files). Production build OK (initial bundle 732 kB, 172 kB
  transferred).
- E2E smoke test (`frontend/e2e/smoke.cjs`, headless Chrome) passed:
  - admin pages;
  - project manager: the farm polygon renders and the overlap flag is visible;
  - a boundary drawn in the UI measured 5.0443 ha by SQL Server;
  - farmer: sees only their 2 farms and 3 navigation items;
  - no unexpected console errors.
- Audit review (DEMO run): every Phase 2 action wrote audit rows (FARMER_*, FARM_*, DOCUMENT_UPLOADED), plus
  42 farmer and farm workflow events.

## Known limitations and open items

- The rate limiter is in-memory (single API process). Redis is required before scaling out (Phase 12).
- `docker-compose.yml` has not been run on the development machine (Docker not installed).
- Status values for later entities (orders, payouts, lab results, …) are still to be confirmed. See the
  architecture document's open questions.
- Phase 2:
  - The S3/MinIO storage adapter and a real antivirus engine are not built. `local` storage and the
    signature-only scanner are for development.
  - Offline capture and sync are not built.
  - Notifications are in-app only.
  - Satellite evidence is recorded manually only (adapter in Phase 5).
  - OpenStreetMap public tiles are for development only.
  - The workflow assumptions A1–A7 in farmer-workflow.md need business confirmation.
  - No system role holds a platform-level `farms.review`, so cross-organization overlap flags can be cleared
    only by a custom platform role.
- The browser logs one expected 401 at start-up: the silent session-restore attempt when nobody is signed in.
