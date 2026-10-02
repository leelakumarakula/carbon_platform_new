# API

Base path `/api/v1`. Interactive docs at `/docs` (OpenAPI at `/api/v1/openapi.json`).

## Conventions

- **Auth**: `Authorization: Bearer <access token>`. Browsers get the refresh token as an httpOnly cookie
  scoped to `/api/v1/auth`.
- **Errors**: `{ "success": false, "error_code": "...", "message": "...", "details": {}, "request_id": "..." }`.
  Validation errors put `details.errors[] = {field, message, type}`.
- **Pagination**: `page` (from 1), `page_size` (1–100), `sort` (`field` or `-field`; whitelisted per endpoint).
  Response shape: `{ items, total, page, page_size }`.
- **Timestamps**: ISO-8601 UTC with `Z`.
- **Request ID**: send `X-Request-ID` (8–64 alphanumeric/hyphen) or one is generated; it is echoed back and
  stored in audit rows.
- **Reasons**: status changes, password resets, unlocks, member removal and session revocation need a
  `reason` (3–1000 characters), stored in the audit log.

## Endpoints (Phase 1)

| Method | Path | Permission |
|---|---|---|
| GET | `/health` | — |
| POST | `/auth/login` · `/auth/token` (OAuth2 form) | — |
| POST | `/auth/refresh` · `/auth/logout` | refresh cookie |
| GET | `/auth/me` | signed in |
| POST | `/auth/change-password` | signed in |
| GET/POST | `/admin/users` | users.read / users.manage |
| GET/PATCH | `/admin/users/{id}` | users.read / users.manage |
| POST | `/admin/users/{id}/status` · `/reset-password` | users.manage |
| POST | `/admin/users/{id}/unlock` | security.manage (platform) |
| POST/DELETE | `/admin/users/{id}/roles[/{user_role_id}]` | users.assign_roles |
| GET | `/admin/permissions` · `/admin/roles[/{id}]` | roles.read |
| POST/PATCH/PUT | `/admin/roles` · `/admin/roles/{id}` · `/admin/roles/{id}/permissions` | roles.manage (custom roles only) |
| GET/POST | `/admin/organizations` | organizations.read / organizations.manage (platform) |
| GET/PATCH | `/admin/organizations/{id}` | organizations.read / organizations.manage |
| POST | `/admin/organizations/{id}/status` | organizations.manage (platform) |
| GET/POST | `/admin/organizations/{id}/members` | organizations.read / organizations.manage_members |
| POST | `/admin/organizations/{id}/members/{user_id}/remove` | organizations.manage_members |
| GET | `/admin/audit-logs` · `/admin/workflow-events` | audit.read |
| GET | `/admin/security/events` · `/login-audit` · `/sessions` | security.read (platform) |
| POST | `/admin/security/sessions/{id}/revoke` | security.manage (platform) |

## Endpoints (Phase 2)

Permissions marked "or self" also let a farmer act on their own linked record (`farmers.self`).
Records outside the caller's scope return 404. Uploads are `multipart/form-data` (`file`, plus `category` and `title`).

| Method | Path | Permission |
|---|---|---|
| GET/POST | `/farmers` | farmers.read / farmers.manage |
| GET | `/farmers/me` | farmers.self |
| GET/PATCH | `/farmers/{id}` | farmers.read / farmers.manage, or self |
| POST | `/farmers/{id}/status` | farmers.manage or self (suspend / reinstate: organization only) |
| POST | `/farmers/{id}/kyc` · `/kyc/decision` | farmers.manage or self · farmers.kyc_verify |
| POST | `/farmers/{id}/contacts[/{cid}/deactivate]` | farmers.manage or self |
| POST | `/farmers/{id}/consents[/{cid}/withdraw]` | farmers.manage or self |
| POST | `/farmers/{id}/agreements` · `/{aid}/sign` · `/{aid}/status` | farmers.manage |
| POST | `/farmers/{id}/bank-accounts` · `/{bid}/decision` · `/{bid}/deactivate` | farmers.bank_manage or self · farmers.bank_verify · farmers.bank_manage or self |
| POST | `/farmers/{id}/documents` · `/link-user` | farmers.manage or self · farmers.manage (organization only) |
| GET/POST | `/farms` | farms.read / farms.manage, or self (own farmer) |
| POST | `/farms/geometry/validate` | farms.read (dry run, nothing saved) |
| GET | `/farms/spatial/at-point` · `/spatial/near` | farms.read |
| GET/PATCH | `/farms/{id}` | farms.read / farms.manage |
| POST | `/farms/{id}/boundary` · `/boundary/upload` (GeoJSON/KML) | farms.manage |
| GET | `/farms/{id}/boundaries` · `/overlaps` | farms.read |
| POST | `/farms/{id}/overlaps/{oid}/resolve` | farms.review |
| GET/POST | `/farms/{id}/ownership` · `/{oid}/end` · `/{oid}/review` | farms.read / farms.manage / farms.review |
| GET/POST | `/farms/{id}/history/{land\|crop\|practice}` | farms.read / farms.manage |
| GET/POST | `…/history/{kind}/{rid}/versions` · `/amend` · `/retract` · `/review` | farms.read / farms.manage / farms.review |
| GET/POST | `/farms/{id}/evidence` · `/{eid}/review` · `/documents` | farms.read / farms.manage / farms.review |
| POST | `/farms/{id}/submit` · `/withdraw` · `/reopen` · `/inactivate` | farms.manage |
| POST | `/farms/{id}/start-review` · `/verify` · `/reject` | farms.review |
| GET/POST | `/evidence/documents/{id}` · `/versions` · `/download` | access of the owning farmer or farm (RESTRICTED: see roles doc) |
| GET/POST | `/notifications` · `/unread-count` · `/{id}/read` · `/read-all` | signed in (own inbox) |

Workflow endpoints take `{ "reason": "..." }`. Farm responses include `allowed_transitions`, `readiness`
checklists and `can_manage` / `can_review` flags, so the UI never has to guess the rules.

## Endpoints (Phase 2 decisions)

| Method | Path | Permission |
|---|---|---|
| GET | `/config/client` | signed in — basemap tile settings (`MAP_TILE_*`, decision D6) |
| GET | `/consent-definitions` | farmers.read, farmers.self or consents.configure |
| GET/POST | `/admin/consent-definitions` · `/{id}/retire` | consents.configure |

## Endpoints (Phase 3)

All project endpoints are organization-scoped; out-of-scope projects return 404. Workflow endpoints take `{ "reason": "..." }`.

| Method | Path | Permission |
|---|---|---|
| GET/POST | `/projects` | projects.read / projects.manage |
| GET | `/projects/my-participation` | farmers.self (own farms only) |
| GET/PATCH | `/projects/{id}` | projects.read / projects.manage |
| GET | `/projects/{id}/farms` (`include_removed`, `geometry`) · `/farms/eligible` | projects.read · projects.manage |
| POST | `/projects/{id}/farms` | projects.manage (farm + participation period + carbon_rights; conflicts need `acknowledge_conflicts` + note) |
| DELETE | `/projects/{id}/farms/{farm_id}` (body `{reason}`) | projects.manage — ends the participation, keeps the record |
| GET/POST | `/projects/{id}/participants` · `/participants/candidates` | projects.read / projects.manage |
| PATCH | `/projects/{id}/participants/{participant_id}` | projects.manage (`status: REMOVED` + reason removes) |
| GET | `/projects/{id}/boundary` | projects.read |
| POST | `/projects/{id}/boundary/recompute` · `/boundary/review` | projects.manage · farms.review |
| GET/POST | `/projects/{id}/standards` · `/standard` | projects.read / projects.manage |
| GET/POST | `/projects/{id}/activities` · `/activity` | projects.read / projects.manage |
| GET/POST | `/projects/{id}/crediting-period` | projects.read / projects.manage |
| GET/PATCH | `/projects/{id}/baseline` | projects.read / projects.manage (new version; reason required after the first) |
| GET/POST | `/projects/{id}/carbon-rights` | projects.read / projects.manage |
| POST | `/projects/{id}/carbon-rights/{rid}/review` · `/end` | projects.review (not the recorder) · projects.manage |
| GET/POST | `/projects/{id}/documents` | projects.read / projects.manage |
| POST | `/projects/{id}/start-data-collection` · `/submit` · `/confirm-activity` · `/reopen` · `/close` | projects.manage |
| POST | `/projects/{id}/approve-eligibility` · `/return` | projects.review (approval: not the submitter) |
| GET | `/projects/{id}/status-history` | projects.read |
| GET/POST/PATCH | `/standards`, `/activities`, `/activities/{id}/standards` | read: projects.read or standards.manage · write: standards.manage |

Project responses include `allowed_transitions` (already filtered by the caller's permissions), `readiness`
checklists, `can_manage` / `can_review` / `can_review_boundary` and `is_editable`.

## Endpoints (Phase 4)

| Method | Path | Permission |
|---|---|---|
| GET/POST | `/methodologies` (`environment`, `standard_id`) | methodologies.read / methodologies.manage |
| GET/PATCH | `/methodologies/{id}` | methodologies.read / methodologies.manage |
| POST | `/methodologies/{id}/versions` (`based_on_version_id` copies rules) | methodologies.manage |
| GET | `/methodologies/{id}/history` | methodologies.read |
| POST | `/methodologies/{id}/documents` (multipart; `version_id`, `as_source`) | methodologies.manage |
| GET/PATCH | `/methodologies/versions/{vid}` | methodologies.read / methodologies.manage (DRAFT only) |
| POST/DELETE | `/methodologies/versions/{vid}/rules/{applicability\|monitoring\|calculation\|general}[/{rule_id}]` | methodologies.manage (DRAFT only) |
| POST | `/methodologies/versions/{vid}/submit` · `/retire` · `/withdraw` | methodologies.manage |
| POST | `/methodologies/versions/{vid}/approve` (`supersedes_version_id`) · `/return` | methodologies.approve (not the submitter) |
| GET | `/projects/{id}/methodology` | projects.read |
| POST | `/projects/{id}/methodology/candidates` (`declared_facts`) | projects.manage or methodologies.review_project |
| GET | `/projects/{id}/methodology/evaluations` | projects.read |
| POST | `/projects/{id}/methodology/reviews` | methodologies.review_project |
| POST | `/projects/{id}/methodology/confirm` · `/unlock` | projects.manage (confirm: not the recommender) |

## Endpoints (Phase 5) — prefix `/mrv`

| Method | Path | Permission |
|---|---|---|
| GET | `/mrv/projects` · `/mrv/projects/{id}/requirements` · `/mrv/projects/{id}/history` | mrv.read |
| GET | `/mrv/projects/{id}/collectors` | sampling.assign |
| GET/POST | `/mrv/plans` (`project_id`) | mrv.read / mrv.manage |
| GET/PATCH | `/mrv/plans/{id}` · POST `/mrv/plans/{id}/measurements` | mrv.read / mrv.manage (DRAFT only) |
| POST | `/mrv/plans/{id}/submit` · `/withdraw` | mrv.manage |
| POST | `/mrv/plans/{id}/approve` (`acknowledge_configuration_gaps`) · `/return` | mrv.approve (not the submitter) |
| GET/POST | `/mrv/monitoring-periods` · GET `/mrv/monitoring-periods/{id}` | mrv.read / mrv.manage |
| POST | `/mrv/monitoring-periods/{id}/{plan\|start\|open-collection\|submit\|close}` | mrv.manage |
| GET/POST | `/mrv/projects/{id}/strata` (`include_history`) · PATCH `/mrv/strata/{id}` | mrv.read or sampling.collect / sampling.manage |
| POST | `/mrv/strata/{id}/approve` | sampling.review (not the creator) |
| GET/POST | `/mrv/sampling-designs` · GET `/mrv/sampling-designs/{id}` · POST `/{id}/versions` | mrv.read / sampling.manage |
| POST | `/mrv/sampling-designs/{id}/versions/{vid}/approve` | sampling.review (not the creator) |
| POST | `/mrv/sampling-designs/{id}/generate-points` | sampling.manage |
| GET | `/mrv/sampling-points` (`project_id`, `monitoring_period_id`, `mine`) · `/mrv/sampling-points/{id}` | mrv.read or sampling.collect (collectors: own points) |
| POST | `/mrv/sampling-points/assign` (bulk) · `/mrv/sampling-points/{id}/assign` | sampling.assign |
| POST | `/mrv/sampling-points/{id}/skip` | sampling.review |
| GET/POST | `/mrv/sampling-points/{id}/relocations` | read / sampling.collect (assigned) or sampling.manage |
| POST | `/mrv/relocations/{id}/decision` | sampling.review (not the requester) |
| GET/POST | `/mrv/field-collections` · GET/PATCH `/mrv/field-collections/{id}` · POST `/{id}/submit` | sampling.collect (assigned collector) |
| POST | `/mrv/field-collections/{id}/review` | sampling.review (not the collector) |
| POST | `/mrv/field-collections/{id}/correct` | sampling.collect or sampling.review |
| GET/POST | `/mrv/monitoring-records` · POST `/mrv/monitoring-records/{record_id}/amend` | mrv.read / mrv.collect or mrv.manage |
| GET/POST | `/mrv/evidence` (multipart, file optional for GPS / notes) | mrv.read or own collection / mrv.collect, mrv.manage or sampling.collect |
| GET/POST | `/mrv/datasets` · GET `/mrv/datasets/{id}` · `/mrv/datasets/{id}/snapshot` | mrv.read / mrv.manage |
| POST | `/mrv/datasets/{id}/submit` | mrv.manage |
| POST | `/mrv/datasets/{id}/approve` · `/reject` | mrv.approve (not the submitter; approve needs QA PASS) |
| GET | `/mrv/qa/{dataset_id}` (checks + reviews) | mrv.read |
| POST | `/mrv/qa/{dataset_id}/start` · `/complete` | mrv.review (complete: not the submitter) |

## Notable error codes

`INVALID_CREDENTIALS`, `TOKEN_EXPIRED`, `SESSION_REVOKED`, `REFRESH_REUSED`, `ACCOUNT_INACTIVE`,
`PASSWORD_CHANGE_REQUIRED`, `PASSWORD_POLICY`, `PERMISSION_DENIED`, `ROLE_ESCALATION_BLOCKED`,
`SELF_ROLE_CHANGE`, `LAST_PLATFORM_ADMIN`, `INVALID_STATUS_TRANSITION`, `USER_NOT_MEMBER`,
`ROLE_SCOPE_MISMATCH`, `ENVIRONMENT_MISMATCH`, `SYSTEM_ROLE_READONLY`, `RATE_LIMITED`, `PAYLOAD_TOO_LARGE`.

Phase 2: `REQUIREMENTS_NOT_MET` (details list the missing items), `SEPARATION_OF_DUTIES`,
`DUPLICATE_REVIEW_REQUIRED`, `IDENTITY_LOCKED`, `FARMER_NOT_READY`, `FARM_NOT_EDITABLE`, `INVALID_POLYGON`,
`INVALID_GEOJSON`, `INVALID_KML`, `UNSAFE_KML`, `UNSUPPORTED_GEOMETRY`, `TOO_MANY_VERTICES`, `CROSS_ORG_OVERLAP`,
`RESTRICTED_DOCUMENT`, `UNSUPPORTED_FILE_TYPE`, `FILE_TOO_LARGE`, `MALWARE_DETECTED`, `CONSENT_ALREADY_GRANTED`,
`BANK_ACCOUNT_EXISTS`, `USER_ALREADY_LINKED`, `UNKNOWN_CONSENT_TYPE`, `CROSS_ORG_OVERLAP`.

Phase 3: `PROJECT_NOT_EDITABLE`, `FARM_NOT_VERIFIED`, `FARMER_NOT_ACTIVE`, `FARM_NOT_IN_PROJECT_ORGANIZATION`,
`FARM_ALREADY_IN_PROJECT`, `CONFLICTS_REQUIRE_ACKNOWLEDGEMENT` (details list the conflicts), `ROLE_NOT_HELD`,
`PARTICIPANT_EXISTS`, `STANDARD_REQUIRED`, `ACTIVITY_NOT_IN_STANDARD`, `STANDARD_INACTIVE`, `CREDITING_PERIOD_OVERLAP`,
`REASON_REQUIRED`, `AGREEMENT_NOT_SIGNED`, `SHARE_EXCEEDS_100`, `BOUNDARY_STALE`, `NO_PROJECT_BOUNDARY`, `SEPARATION_OF_DUTIES`.

Phase 4: `VERSION_NOT_EDITABLE`, `VERSION_EXISTS`, `INVALID_RULE`, `RULE_EXISTS`, `INVALID_BASE_VERSION`, `INVALID_SUPERSEDE`,
`DECLARED_FACT_CONFLICT`, `CANDIDATE_NOT_FOUND`, `CANDIDATE_NOT_ELIGIBLE`, `EVIDENCE_NOT_ACKNOWLEDGED`, `SPECIALIST_REVIEW_REQUIRED`,
`EVALUATION_OUTDATED`, `VERSION_NOT_APPROVED`, `CREDITING_PERIOD_NOT_COMPLIANT`, `NOT_LOCKED`.

Phase 5: `METHODOLOGY_NOT_LOCKED`, `METHODOLOGY_VERSION_INVALID`, `PROJECT_NOT_IN_MRV`, `METHODOLOGY_REQUIREMENT`, `CONFIGURATION_REQUIRED`,
`PLAN_IN_PROGRESS`, `PLAN_NOT_EDITABLE`, `MRV_PLAN_NOT_APPROVED`, `OUTSIDE_PLAN_WINDOW`, `PERIOD_OVERLAP`, `PERIOD_NOT_OPEN`, `PERIOD_NOT_COLLECTING`,
`FARM_ALREADY_STRATIFIED`, `REVISION_EXISTS`, `CHARACTERISTICS_REQUIRED`, `STRATUM_NOT_APPROVED`, `DESIGN_EXISTS`, `DRAFT_EXISTS`, `DESIGN_NOT_APPROVED`,
`POINTS_ALREADY_GENERATED`, `INSUFFICIENT_AREA`, `NOT_A_COLLECTOR`, `NOT_ASSIGNED`, `OUTSIDE_FARM`, `DUPLICATE_POINT`, `RELOCATION_PENDING`,
`COLLECTION_EXISTS`, `CORRECTION_EXISTS`, `MEASUREMENT_NOT_IN_PLAN`, `LEVEL_REQUIRED`, `UNIT_MISMATCH`, `INVALID_VALUE`, `DUPLICATE_RECORD`,
`DATASET_EMPTY`, `QA_CHECKS_FAILED`, `QA_NOT_PASSED`, `SNAPSHOT_MISMATCH`, `LABORATORY_RESULT_REQUIRED` (decisions V2/V2-A: parameters
the methodology rule declares LABORATORY cannot be entered as monitoring data), `MEASUREMENT_SOURCE_UNCLASSIFIED` (the methodology rule
declares no measurement source). Phase 4 monitoring rules require `measurement_source` = FIELD / FIELD_ACTIVITY / LABORATORY (422 otherwise).
Plan measurements and monitoring records expose `data_role` (METHODOLOGY_PARAMETER / LABORATORY_PARAMETER / UNCLASSIFIED_PARAMETER /
SUPPLEMENTARY_OBSERVATION) and `authoritative` (decision V2-B: user-created measurements are supplementary, never authoritative).
