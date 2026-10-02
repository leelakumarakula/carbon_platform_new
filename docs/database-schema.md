# Database schema

SQL Server. Conventions (spec §7): `uniqueidentifier` public IDs, `bigint IDENTITY` for high-volume logs,
`datetime2` timestamps in UTC (`SYSUTCDATETIME()` defaults), `nvarchar` text, CHECK constraints for status
enums, `ISJSON` checks on JSON columns. Constraint names follow the naming convention in `app/models/base.py`.
The database has READ_COMMITTED_SNAPSHOT on.

## Phase 1 tables

### Identity and access (§7.1)

| Table | Notes |
|---|---|
| `organizations` | `code` unique; `org_type` ∈ PLATFORM, PROJECT_DEVELOPER, FIELD_PARTNER, FARMER_GROUP, LABORATORY, VVB, REGISTRY, BUYER; `status` ACTIVE/SUSPENDED/ARCHIVED; `environment` LIVE/DEMO |
| `users` | `email` unique (lower-case); bcrypt `password_hash`; `status` ACTIVE/SUSPENDED/DEACTIVATED; lockout (`failed_login_count`, `locked_until`); `must_change_password`; MFA-ready (`mfa_enabled`, `mfa_secret_ref`); `environment` |
| `permissions` | catalog synced from code |
| `roles` | `scope` PLATFORM/ORGANIZATION; `is_system` for the 19 spec roles |
| `role_permissions` | PK (role_id, permission_id) |
| `user_roles` | grant; `organization_id` NULL = platform-wide; unique (user, role, organization) |
| `organization_users` | membership; unique (organization, user) |
| `sessions` | one per sign-in; `expires_at`, `revoked_at`, `revoked_reason` |
| `refresh_tokens` | SHA-256 hash only; `used_at` + `replaced_by_id` (rotation chain); `revoked_at` |

### Audit (§7.15, §35)

| Table | Append-only | Notes |
|---|---|---|
| `audit_logs` | yes (trigger) | user, organization, action, entity type/id, old/new JSON, reason, request id, IP, user agent |
| `workflow_events` | yes (trigger) | every status transition |
| `login_audit` | yes (trigger) | every sign-in attempt with failure reason |
| `security_events` | yes (trigger) | lockouts, rate limiting, refresh-token reuse, … |
| `api_access_logs` | no (retention purge allowed) | method, path, status, duration, user |

`INSTEAD OF UPDATE, DELETE` triggers raise error 51000 for every database user. Legal erasure or retention
must be done by a DBA who explicitly disables the trigger, and that action is itself an operational record.

## Migrations

`backend/alembic/versions/20261002_0001_phase1_identity_access_audit.py`. Generate new revisions with
`alembic revision --autogenerate`, review them, and add raw SQL (triggers, spatial indexes) by hand.
`alembic check` must report no drift before a phase is closed.
