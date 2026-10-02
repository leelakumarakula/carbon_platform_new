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

## Phase 2 tables (§7.2 farmer, §7.3 farm)

| Table | Notes |
|---|---|
| `farmers` | `farmer_code` (sequence `seq_farmer_code`, FRM-YYYY-nnnnnn) unique; status DRAFT/REGISTERED/KYC_PENDING/KYC_VERIFIED/ACTIVE/SUSPENDED; `organization_id`, optional `group_organization_id`, optional `user_id` (self-service, unique when set); KYC: `kyc_id_type`, `kyc_id_hash` (HMAC fingerprint, indexed), `kyc_id_last4`, `kyc_document_id`, submitter / verifier and times; `environment` |
| `farmer_contacts` | PHONE/EMAIL/ALTERNATE_PHONE/ADDRESS; `is_active` (deactivated, never deleted) |
| `farmer_consents` | GRANTED/WITHDRAWN; consent type, text version, language, capture method, granted/withdrawn time and reason |
| `farmer_agreements` | `agreement_number` (sequence, AGR-YYYY-nnnnnn); DRAFT/SIGNED/TERMINATED/EXPIRED/VOID; effective dates; signed document |
| `farmer_bank_accounts` | `account_number_encrypted` (Fernet), `account_last4`, `account_fingerprint` (duplicate check); PENDING_VERIFICATION/VERIFIED/REJECTED/INACTIVE; proof document |
| `farmer_documents` | link from a farmer to a `documents` row, with review status |
| `farms` | `farm_code` (sequence); status DRAFT/SUBMITTED/GIS_REVIEW/VERIFIED/REJECTED/INACTIVE; `land_tenure`; declared and measured `area_hectares`; `current_boundary_id` (FK added after `farm_boundaries`) |
| `farm_boundaries` | `boundary geography` (SRID 4326); version, CURRENT/SUPERSEDED (filtered unique: one CURRENT per farm); `area_m2`, `area_hectares`, `perimeter_m`, centroid, vertex count, source, validation notes. **Spatial index** `six_farm_boundaries_boundary` (GEOGRAPHY_AUTO_GRID) |
| `farm_ownership` | owner type, owner farmer or name, operator relationship, share %, valid from / to, title reference, verification status |
| `farm_land_history`, `farm_crop_history`, `farm_practice_history` | versioned: `record_id`, `version`, `is_current`, `is_retracted`, `source`, `verification_status`, `change_reason`; filtered unique index on `record_id` WHERE `is_current=1` |
| `farm_evidence` | claim type, source type, document / photo / GPS point, captured by, review status |
| `farm_documents` | link from a farm to a `documents` row |
| `farm_overlap_checks` | boundary pair, relation PARTIAL/CONTAINS/WITHIN/EQUAL, overlap m² and %, OPEN/CLEARED/CONFIRMED_CONFLICT/OBSOLETE, resolution |

Shared services added in Phase 2:

| Table | Notes |
|---|---|
| `documents` | entity type and id, category, status, sensitivity RESTRICTED/INTERNAL, current version, `environment` |
| `document_versions` | **append-only (trigger)**; storage key, SHA-256, size, sniffed MIME, scan status |
| `notifications` | in-app inbox; channel (IN_APP only for now), status, read time |

## Migrations

`backend/alembic/versions/20261002_0001_phase1_identity_access_audit.py` and
`20261002_0002_phase2_farmer_farm.py` (tables, sequences, spatial index, `document_versions` trigger). Spatial
indexes (`six_*`) are hand-written SQL and excluded from autogenerate by `include_object` in `alembic/env.py`. Generate new revisions with
`alembic revision --autogenerate`, review them, and add raw SQL (triggers, spatial indexes) by hand.
`alembic check` must report no drift before a phase is closed.
