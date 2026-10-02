# Implementation status

| Phase | Scope (spec §47) | Status |
|---|---|---|
| 1 | Foundation: Angular, FastAPI, SQL Server, SQLAlchemy, Alembic, auth, RBAC, organizations, audit, dev setup | **Done** |
| 2 | Farmer & farm (KYC, polygons, history, evidence) | Next |
| 3 | Project | — |
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

## Known limitations and open items

- The rate limiter is in-memory (single API process). Redis is required before scaling out (Phase 12).
- `docker-compose.yml` has not been run on the development machine (Docker not installed).
- Status values for later entities (orders, payouts, lab results, …) are still to be confirmed. See the
  architecture document's open questions.
- The browser logs one expected 401 at start-up: the silent session-restore attempt when nobody is signed in.
