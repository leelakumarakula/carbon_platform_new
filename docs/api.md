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

## Endpoints (Phase 6) — project side, prefix `/lab`

| Method | Path | Permission |
|---|---|---|
| GET | `/lab/projects/{id}/laboratories` · `/lab/projects/{id}/laboratory-rules` | lab.engage or lab.read |
| GET/POST | `/lab/engagements` · POST `/lab/engagements/{id}/end` | lab.read / lab.engage |
| GET/POST | `/lab/samples` (filters: project, period, field collection) · GET/PATCH `/lab/samples/{id}` | lab.read, own records with lab.sample_register / lab.sample_register |
| POST | `/lab/samples/{id}/seal` · `/void` · GET/POST `/lab/samples/{id}/custody` | lab.sample_register (seal) / lab.sample_manage |
| GET/POST | `/lab/shipments` · GET `/lab/shipments/{id}` · POST `/{id}/items` · `/{id}/items/{sample_id}/remove` · `/{id}/dispatch` · `/{id}/cancel` · `/{id}/documents` (PDF) | lab.read / lab.shipment_manage |
| GET | `/lab/results?project_id&status=` (default APPROVED; ALL = every non-draft status) · `/lab/results/{id}/lineage` | lab.read |

## Endpoints (Phase 6) — laboratory side, prefix `/laboratory` (allow-list views only)

| Method | Path | Permission |
|---|---|---|
| GET | `/laboratory/dashboard` | lab.lab_read |
| GET | `/laboratory/engagements` · POST `/{id}/accept` · `/{id}/end` | lab.lab_read / lab.engagement_accept |
| GET | `/laboratory/shipments` · `/laboratory/shipments/{id}` · POST `/{id}/receive` (per item) · `/{id}/documents` (PDF) | lab.lab_read / lab.receive |
| GET | `/laboratory/samples` · `/laboratory/samples/{id}` · POST `/{id}/accession` · `/{id}/custody` | lab.lab_read / lab.receive |
| GET | `/laboratory/tests?test_status=` · `/laboratory/tests/{id}` · POST `/{id}/start` · `/{id}/results` | lab.lab_read / lab.test |
| PATCH/POST | `/laboratory/results/{id}` · `/report` (PDF) · `/submit` · `/withdraw` · `/correct` | lab.test |
| POST | `/laboratory/results/{id}/retest` | lab.retest_request |
| GET/POST | `/laboratory/qa` · `/laboratory/qa/{id}` · POST `/{id}/start` · `/{id}/decision` | lab.qa (never on your own work) |

## Endpoints (Phase 7) — prefix `/calculations`

No request body can carry a calculated value (unknown fields are refused with 422); every value comes from the registered module.

| Method | Path | Permission |
|---|---|---|
| GET | `/calculations/modules` (registered modules — none in Phase 7) · `/calculations/projects` (projects in monitoring or later, with periods) | calculation.read |
| GET | `/calculations/projects/{id}/readiness?monitoring_period_id&crediting_period_id` | calculation.read |
| GET/POST | `/calculations/runs?project_id&monitoring_period_id` · GET `/calculations/runs/{id}` | calculation.read / calculation.manage |
| POST | `/runs/{id}/freeze` (BLOCKED with the blockers when not ready) · `/execute` · `/submit` · `/cancel` · `/recalculate` | calculation.manage |
| GET | `/runs/{id}/inputs` · `/outputs` · `/lineage` · `/compare/{other_id}` | calculation.read |
| GET/POST | `/calculations/qa/{run_id}` · POST `/start` · `/complete` | calculation.read / calculation.review (not the run's creator, freezer, executor or submitter) |
| POST | `/runs/{id}/approve` · `/reject` | calculation.approve (same separation of duties; approval needs QA PASS) |

## Endpoints (Phase 11) — revenue, sharing, costs, settlements, payouts

Details: [payout-workflow.md](payout-workflow.md). Every POST accepts an `Idempotency-Key`; extra fields are rejected with 422. No request
carries a revenue, entitlement, settlement figure or payout amount; the server calculates them all. The only typed amounts are a project
cost actually incurred and a bank-statement line. DEMO projects are refused (`DEMO_FINANCE_NOT_ALLOWED`).

| Method | Path | Permission |
|---|---|---|
| GET | `/revenue/projects` · `/revenue?project_id=` · `/revenue/summary` | any finance permission (organization-scoped) |
| POST | `/revenue/recognize` (order item) · `/revenue/reverse-refund` (refund): idempotent re-runs | revenue.manage |
| GET / POST | `/revenue-share` · `/allocations` (create DRAFT) | read: finance · create: sharing.manage |
| POST | `/revenue-share/{id}/submit` · `/allocations/{id}/submit` | sharing.manage |
| POST | `/revenue-share/{id}/approve` / `return` · `/allocations/{id}/approve` / `return` | sharing.approve (never the author) |
| GET / POST | `/costs` · `/costs/{id}/documents` (COST_EVIDENCE) | costs.manage |
| POST | `/costs/{id}/approve` / `reject` | costs.approve (never the recorder) |
| GET | `/settlements` · `/settlements/{id}` · `/settlements/{id}/verify` · `/settlements/{id}/lineage` | settlement.read / calculate / approve, payouts.read, revenue.read |
| POST | `/settlements` · `/{id}/calculate` · `/{id}/submit` · `/{id}/cancel` | settlement.calculate |
| POST | `/settlements/{id}/approve` / `reject` | settlement.approve (never the calculator) |
| GET | `/payouts` · `/payouts/{id}` · `/payouts/{id}/lineage` · `/payouts/adjustments` | payouts.*, settlement.read |
| POST | `/payouts/from-settlement/{run}` · `/{id}/submit` · `/cancel` · `/release-hold` · `/reissue` | payouts.calculate |
| POST | `/payouts/{id}/approve` / `reject` | payouts.approve (never the calculator; needs a VERIFIED bank account) |
| POST | `/payouts/{id}/initiate` · `/documents` (PAYOUT_EVIDENCE) · `/confirm-paid` · `/fail` · `/query-status` | payouts.execute (never the approver or calculator) |
| POST | `/payouts/{id}/documents` (RECONCILIATION_EVIDENCE) · `/payouts/{id}/reconcile` · `/payouts/adjustments/{id}/close` | payouts.reconcile (never the executor) |
| GET | `/payouts/me` | farmers.self (own payouts only) |

## Endpoints (Phase 10) — marketplace

Details: [marketplace.md](marketplace.md). Authenticated only (no public catalogue). Every POST accepts an `Idempotency-Key`. Bodies carry
whole-credit quantities and Decimal money only — never a balance, fee or tax (extra fields → 422). There is no checkout, invoice, offer
or webhook endpoint (payouts are Phase 11, under `/payouts`).

| Method | Path | Permission |
|---|---|---|
| GET / POST | `/marketplace/buyer-profile` · POST `/marketplace/buyer-profile/documents` (PDF, restricted) · `/marketplace/buyer-profile/submit-kyc` | buyers.kyc_submit (own BUYER organization) |
| GET / POST | `/marketplace/buyer-profiles?status` · `/{id}` · `/{id}/verify` (or reinstate) · `/{id}/return` · `/{id}/suspend` | buyers.kyc_verify (platform), never the submitter |
| GET | `/marketplace/listings?mine&status` · `/marketplace/listings/{id}` | marketplace.read (ACTIVE listings) / seller side (own) |
| POST | `/marketplace/listings` · `/{id}/documents` (PDF) · `/{id}/submit` · `/{id}/pause` · `/{id}/resume` · `/{id}/close` | listings.manage (seller) |
| POST | `/marketplace/listings/{id}/approve` | listings.approve, never the creator |
| POST | `/orders` (T1: listings locked, items, one 9B reservation per item) | orders.place, KYC-verified buyer |
| GET | `/orders?status` · `/orders/{id}` · `/orders/{id}/lineage` · POST `/orders/{id}/confirmation` (deterministic PDF, not a tax invoice) | orders.read (buyer or seller side) |
| POST | `/orders/{id}/cancel` (PLACED, no payment awaiting confirmation) | orders.place (buyer) / orders.manage (seller) |
| POST | `/orders/{id}/documents` (PAYMENT_EVIDENCE, PDF) | payments.record / orders.place (buyer) |
| POST | `/orders/{id}/retry-transfer` (ATTENTION_REQUIRED: re-reserve + re-request the 9B transfer) | orders.manage (seller) |
| POST | `/orders/transfers/{transfer_id}/complete` · `/reject` (the Phase 10 wrapper around the composable 9B functions) | credits.confirm in the custodian organization, never the transfer requester |
| POST / GET | `/payments` (manual, exact total, evidence) · `/payments` · `/payments/{id}` | payments.record (buyer) / readers |
| POST | `/payments/{id}/confirm` (T3: requests the 9B transfers) · `/reject` · `/reconcile` | payments.confirm (payee), never the recorder |
| POST | `/payments/{id}/refunds` | refunds.request (payee) |
| GET / POST | `/refunds` · `/refunds/{id}/documents` · `/approve` · `/complete` · `/reject` | refunds.approve (≠ requester) / refunds.request |

## Endpoints (Phase 9B) — credit ledger

Prefix `/credits` (details: [credit-ledger-workflow.md](credit-ledger-workflow.md)). Every POST accepts an optional `Idempotency-Key`
(same key + same body replays; a different body → 409 `IDEMPOTENCY_KEY_REUSED`). Request bodies carry movement quantities only — whole
units — and never a balance (extra fields → 422). No price, order, payment or marketplace endpoint exists.

| Method | Path | Permission |
|---|---|---|
| GET | `/inventory?project_id` (derived balances per batch and owner; DEMO note) · `/batches/{id}/positions?include_consumed` · `/entries/{id}` · `/reversals` · `/reservations?batch_id` | credits.read / manage / confirm |
| GET | `/transfers?batch_id` · `/retirements?batch_id` · `/retirements/{id}/lineage` | the above, or the holder (own organization only) |
| POST | `/batches/{id}/open` | credits.manage |
| POST | `/openings/{id}/confirm` | credits.confirm in the custodian organization, never the requester |
| POST | `/openings/{id}/cancel` | credits.manage / credits.confirm |
| POST | `/reservations` · `/reservations/{id}/release` · `/reservations/expire-due` | credits.manage |
| GET | `/recipients?environment` (ACTIVE BUYER / PROJECT_DEVELOPER organizations) | credits.manage |
| POST | `/transfers` · `/transfers/{id}/cancel` | credits.manage |
| POST | `/transfers/{id}/documents` (PDF, REGISTRY_TRANSFER_EVIDENCE) · `/retirements/{id}/documents` (PDF, RETIREMENT_CERTIFICATE) | credits.manage / credits.confirm |
| POST | `/transfers/{id}/complete` (REGISTRY: `registry_transfer_reference` + `document_id`) · `/transfers/{id}/reject` | credits.confirm, never the requester |
| POST | `/retirements` · `/retirements/{id}/cancel` | credits.manage, or credits.holder_retire for the holder's own credits |
| POST | `/retirements/{id}/retire` (`registry_retirement_reference`, `retirement_date`, `document_id`, optional registry-stated `retired_serials`) · `/retirements/{id}/reject` | credits.confirm, never the requester |
| POST | `/entries/{id}/reverse` | credits.manage (INTERNAL TRANSFER_COMPLETE only) |
| POST | `/reversals/{id}/apply` · `/reversals/{id}/reject` | credits.confirm, never the requester |
| GET | `/holdings` (allow-listed holder view of the caller organization's positions) | credits.holder_read |
| POST | `/accounts/{id}/statements` (PDF registry statement) · `/accounts/{id}/reconcile` (registry-stated per-batch quantities → RECONCILED / MISMATCH; nothing auto-fixed) | credits.manage |

The 9A read-only batch endpoints (`/batches`, `/batches/{id}`, `/batches/{id}/lineage`) are unchanged. `/registry` gained no transfer,
retirement, reservation or inventory endpoint.

## Endpoints (Phase 9A) — registry submission & credit issuance

Prefix `/registry` (project-organization scope; registries are external counterparties — no registry portal):

| Method | Path | Permission |
|---|---|---|
| GET | `/organizations?environment` · `/projects` · `/accounts?organization_id` · `/projects/{id}/registrations` · `/projects/{id}/periods/{period_id}` · `/submissions/{id}` · `/submissions/{id}/snapshot` · `/submissions/{id}/events` | registry.read / manage / confirm |
| POST | `/accounts` · `/accounts/{id}/configure` (unit equivalence, checklist) · `/accounts/{id}/close` | registry.manage |
| POST | `/projects/{id}/registrations` · `/registrations/{id}/documents` (PDF) · `/registrations/{id}/record-registered` · `/record-rejected` | registry.manage |
| POST | `/projects/{id}/submissions` (optional `Idempotency-Key`) · `/submissions/{id}/documents` (PDF; category, checklist item) · `/freeze` · `/submit` (API adapters only) · `/record-submitted` · `/record-query` · `/record-response` · `/withdraw` · `/cancel` · `/reconcile` | registry.manage |
| POST | `/submissions/{id}/issuances` (optional `Idempotency-Key`) · `/issuances/{id}/void` · `/issuances/{id}/cancel` · `/issuances/{id}/correct` | registry.manage |
| POST | `/issuances/{id}/confirm` | registry.confirm (never the recorder) |

Prefix `/credits` — read-only in 9A: GET `/batches?project_id&period_id` · `/batches/{id}` · `/batches/{id}/lineage` (credits.read). The
ledger endpoints were added in Phase 9B (above); no endpoint takes a calculated or VVB-verified value as an issuance or ledger quantity.

## Endpoints (Phase 8B) — VVB / ACVA verification

Project side, prefix `/verification` (organization-scoped; the project never decides or closes a VVB finding):

| Method | Path | Permission |
|---|---|---|
| GET | `/projects/{id}/vvb-organizations` · `/projects/{id}/assignments?period_id` · `/projects/{id}/periods/{period_id}` · `/assignments/{id}` · `/assignments/{id}/submissions` · `/submissions/{id}` · `/submissions/{id}/findings` | verification.read / manage / respond |
| POST | `/projects/{id}/assignments` (propose) · `/assignments/{id}/withdraw` · `/assignments/{id}/terminate` · `/assignments/{id}/submit` | verification.manage |
| POST | `/submissions/{id}/evidence` (PDF) · `/findings/{id}/respond` · `/corrective-actions/{id}/respond` | verification.respond |
| GET | `/decisions/{id}/lineage` · `/decisions/{id}/report` (PDF, audited) | verification.read / manage / respond |

VVB side, prefix `/vvb` (allow-list API; assignments of the caller's own ACTIVE, same-environment VVB organization only):

| Method | Path | Permission |
|---|---|---|
| GET | `/assignments` · `/assignments/{id}` · `/submissions/{id}/package` · `/submissions/{id}/documents` · `/submissions/{id}/documents/{document_id}` (manifest-scoped, integrity-checked, audited) · `/submissions/{id}/findings` · `/decisions/{id}/report` | verification.vvb_read / vvb_review / decide |
| POST | `/assignments/{id}/accept` (COI declaration) · `/decline` · `/terminate` · `/submissions/{id}/findings` · `/findings/{id}/close` · `/return` · `/reopen` · `/findings/{id}/corrective-actions` · `/corrective-actions/{id}/accept` · `/reject` · `/cancel` | verification.vvb_review |
| POST | `/submissions/{id}/decision` (multipart: outcome, rationale, report PDF, optional VVB-stated quantity + unit) | verification.decide (never a finding raiser on the submission) |

No endpoint validates, registers, issues, serializes, retires or prices anything.

## Endpoints (Phase 8A) — internal pre-verification, prefix `/calculations`

| Method | Path | Permission |
|---|---|---|
| GET | `/calculations/findings?project_id&monitoring_period_id&run_id&finding_status` · `/findings/{id}` · `/findings/{id}/history` | calculation.read |
| POST | `/runs/{id}/findings` (non-DRAFT run) | calculation.review |
| POST | `/findings/{id}/respond` | calculation.manage |
| POST | `/findings/{id}/resolve` (not the responder) · `/return` · `/reopen` · `/withdraw` (raiser only) | calculation.review |
| POST | `/runs/{id}/evidence` (PDF / image attached to the run) | calculation.manage or calculation.review |
| GET/POST | `/runs/{id}/reports` (generate: APPROVED runs only) | calculation.read / calculation.manage |
| GET | `/reports/{id}` (content) · `/reports/{id}/pdf` · `/reports/{id}/verify` | calculation.read |
| GET/POST | `/projects/{id}/verification-readiness?monitoring_period_id` (create: body `monitoring_period_id`) | calculation.read / calculation.manage |
| GET | `/readiness/{id}` · `/readiness/{id}/package` | calculation.read |
| POST | `/readiness/{id}/submit` · `/withdraw` | calculation.manage |
| POST | `/readiness/{id}/approve` · `/reject` (not the submitter or the run's handlers) | calculation.approve |

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

Phase 6: `ENGAGEMENT_NOT_ACTIVE`, `ENGAGEMENT_ENDED`, `ENGAGEMENT_PENDING`, `ENGAGEMENT_NOT_PROPOSED`, `NOT_A_LABORATORY`, `RULE_NOT_LABORATORY`,
`LABORATORY_REQUIRED`, `FIELD_COLLECTION_NOT_READY`, `NOT_COLLECTOR`, `INVALID_PARENT`, `DEPTH_REQUIRED`, `INVALID_DEPTH`, `PLAN_MEASUREMENT_MISSING`,
`SAMPLE_SEALED`, `SAMPLE_NOT_REGISTERED`, `SAMPLE_NOT_SEALED`, `SAMPLE_NOT_VOIDABLE`, `SAMPLE_NOT_RECEIVED`, `SAMPLE_NOT_LAB_REGISTERED`,
`WRONG_LABORATORY`, `NOT_IN_SHIPMENT`, `SHIPMENT_NOT_DRAFT`, `SHIPMENT_EMPTY`, `SHIPMENT_NOT_DISPATCHED`, `CUSTODY_OUT_OF_ORDER`, `NOT_CUSTODIAN`,
`EXCEPTION_OPEN`, `NO_EXCEPTION`, `INVALID_CUSTODY_EVENT`, `TEST_NOT_REQUESTED`, `TEST_NOT_IN_PROGRESS`, `RESULT_IN_PROGRESS`, `RESULT_NOT_EDITABLE`,
`NOT_ANALYST`, `ONE_VALUE_REQUIRED`, `RESULT_NOT_IN_QA`, `QA_CHECKS_FAILED`, `CONFIGURATION_REQUIRED` (with `PRODUCTION_BLOCK` when not acknowledgeable),
`SEPARATION_OF_DUTIES` (403; details list the reasons), `AUTHORITATIVE_RESULT_EXISTS`, `RESULT_NOT_APPROVED`, `RESULT_NOT_RETESTABLE`,
`INVALID_RETEST_SAMPLE`, `RETEST_OPEN`, `UNSUPPORTED_FILE_TYPE` (laboratory documents are PDF only), `LAB_NOT_FOUND` (404).

Phase 7: `CONFIGURATION_REQUIRED` (details.reason `NO_CALCULATION_MODULE`, `STEP_NOT_CONFIGURED`, `STEP_NOT_INCLUDED`,
`STEP_NOT_IMPLEMENTED`, `NO_FINAL_NET_OUTPUT`), `CALCULATION_RULE_NOT_CONFIGURED`, `NOT_PRODUCTION_READY`, `DATASET_NOT_APPROVED`,
`SNAPSHOT_MISMATCH`, `OUTSIDE_CREDITING_PERIOD`, `MISSING_APPROVED_LAB_RESULT`, `MISSING_REQUIRED_INPUT`, `INPUT_NOT_NUMERIC`, `UNIT_MISMATCH`,
`INPUT_TOO_LARGE`, `INPUT_SNAPSHOT_MISMATCH`, `INPUTS_OUT_OF_DATE`, `CALCULATION_ERROR` (a module produced an invalid output),
`OPEN_RUN_EXISTS`, `RUN_NOT_EDITABLE`, `RUN_NOT_IN_QA`, `QA_IN_PROGRESS`, `QA_NOT_STARTED`, `QA_CHECKS_FAILED`, `QA_NOT_PASSED`,
`SEPARATION_OF_DUTIES`, `RUNS_NOT_COMPARABLE`, `CALCULATION_RUN_NOT_FOUND` (404).

Phase 8A: `FINDING_RUN_DRAFT`, `INVALID_FINDING_TARGET`, `FINDING_NOT_OPEN`, `FINDING_NOT_RESPONDED`, `FINDING_NOT_RESOLVED`, `NOT_RAISER`,
`SEPARATION_OF_DUTIES`, `RUN_NOT_APPROVED`, `REPORT_UNCHANGED`, `REPORT_TOO_LARGE`, `NO_APPROVED_CALCULATION`, `REPORT_MISSING`,
`REPORT_INTEGRITY_FAILED`, `REPORT_STALE`, `OPEN_BLOCKING_FINDINGS`, `READINESS_EXISTS`, `READINESS_NOT_DRAFT`, `READINESS_NOT_SUBMITTED`,
`READINESS_NOT_OPEN`, `FINDING_NOT_FOUND`, `CALCULATION_REPORT_NOT_FOUND`, `READINESS_NOT_FOUND` (404).

Phase 8B: `NOT_A_VVB`, `OPEN_ASSIGNMENT_EXISTS`, `INVALID_REPLACEMENT`, `ASSIGNMENT_NOT_PROPOSED`, `ASSIGNMENT_NOT_ACCEPTED`, `NO_READY_PACKAGE`,
`READINESS_NOT_VALID`, `SUBMISSION_EXISTS`, `SUBMISSION_NOT_CURRENT`, `TARGET_NOT_IN_PACKAGE`, `FINDING_NOT_OPEN`, `FINDING_NOT_RESPONDED`,
`FINDING_NOT_CLOSED`, `FINDING_CLOSED`, `OPEN_CORRECTIVE_ACTIONS`, `CORRECTIVE_ACTION_NOT_REQUESTED`, `CORRECTIVE_ACTION_NOT_RESPONDED`,
`CORRECTIVE_ACTION_CLOSED`, `OPEN_VERIFICATION_FINDINGS`, `SEPARATION_OF_DUTIES`, `INVALID_OUTCOME`, `INVALID_QUANTITY`,
`QUANTITY_UNIT_REQUIRED`, `QUANTITY_NOT_ALLOWED`, `REPORT_REQUIRED`, `ASSIGNMENT_NOT_FOUND`, `SUBMISSION_NOT_FOUND`,
`VERIFICATION_FINDING_NOT_FOUND`, `CORRECTIVE_ACTION_NOT_FOUND`, `DECISION_NOT_FOUND` (404).

Phase 9A: `NOT_A_REGISTRY`, `UNKNOWN_ADAPTER`, `REGISTRY_ACCOUNT_EXISTS`, `UNIT_EQUIVALENCE_INCOMPLETE`, `UNIT_CONFIGURATION_LOCKED`,
`CHECKLIST_INVALID`, `REGISTRY_ACCOUNT_IN_USE`, `REGISTRATION_EXISTS`, `DUPLICATE_EXTERNAL_PROJECT`, `NO_VERIFIED_DECISION`, `DECISION_NOT_VERIFIED`,
`VERIFICATION_PACKAGE_MISMATCH`, `VERIFIED_QUANTITY_REQUIRED`, `REGISTRATION_REQUIRED`, `REGISTRY_ACCOUNT_INACTIVE`, `REGISTRY_INACTIVE`,
`ENVIRONMENT_MISMATCH`, `OPEN_REGISTRY_SUBMISSION_EXISTS`, `CHECKLIST_NOT_CONFIGURED`, `CHECKLIST_INCOMPLETE`, `CHECKLIST_ITEM_UNKNOWN`,
`DEMO_API_NOT_ALLOWED`, `IDEMPOTENCY_KEY_REUSED`, `INVALID_PREVIOUS_SUBMISSION`, `SUBMISSION_NOT_DRAFT`, `SUBMISSION_FROZEN`, `SUBMISSION_NOT_FROZEN`,
`SUBMISSION_INVALIDATED`, `SNAPSHOT_STALE`, `MANUAL_ACTION_REQUIRED`, `REGISTRY_UNAVAILABLE`, `DUPLICATE_EXTERNAL_SUBMISSION`,
`SUBMISSION_NOT_SUBMITTED`, `SUBMISSION_ALREADY_SENT`, `EVIDENCE_REQUIRED`, `EXTERNAL_REFERENCE_REQUIRED`, `NOTHING_TO_RECONCILE`,
`SUBMISSION_NOT_ACCEPTED`, `UNIT_EQUIVALENCE_NOT_CONFIGURED`, `QUANTITY_EXCEEDS_VERIFIED`, `DUPLICATE_EXTERNAL_ISSUANCE`, `BATCH_TOTAL_MISMATCH`,
`RANGE_TOTAL_MISMATCH`, `SERIAL_RANGE_LENGTH_MISMATCH`, `DUPLICATE_SERIAL`, `SERIAL_OVERLAP`, `ISSUANCE_MISMATCH`, `ISSUANCE_NOT_RECORDED`,
`ISSUANCE_NOT_CONFIRMED`, `CORRECTION_PENDING`, `DUPLICATE_REGISTRY_REFERENCE`, `DOCUMENT_IMMUTABLE` (403), `SEPARATION_OF_DUTIES` (403), and the
404s `REGISTRY_ACCOUNT_NOT_FOUND`, `REGISTRY_REGISTRATION_NOT_FOUND`, `REGISTRY_SUBMISSION_NOT_FOUND`, `CREDIT_ISSUANCE_NOT_FOUND`,
`CREDIT_BATCH_NOT_FOUND`.

Phase 11: `DEMO_FINANCE_NOT_ALLOWED`, `REVENUE_NOT_RECOGNIZABLE`, `REFUND_NOT_COMPLETED`, `INVALID_DATES`, `DUPLICATE_FARM_ALLOCATION`,
`FARM_NOT_IN_PERIOD`, `ALLOCATION_NOT_CONSERVED`, `CORRECTION_TARGET_REQUIRED`, `COST_LOCKED`, `COST_EVIDENCE_REQUIRED`, `SHARING_RULE_NOT_APPROVED`,
`SHARING_RULE_NOT_EFFECTIVE`, `ALLOCATION_NOT_APPROVED`, `CONFIGURATION_SUPERSEDED`, `NOTHING_TO_SETTLE`, `NEGATIVE_DISTRIBUTABLE`,
`ROUNDING_EXCEEDS_DISTRIBUTABLE`, `SETTLEMENT_NOT_CALCULATED`, `SETTLEMENT_NOT_REPRODUCIBLE`, `SETTLEMENT_NOT_APPROVED`, `PAYOUT_NOT_FAILED`,
`PAYOUT_NOT_ON_HOLD`, `BANK_ACCOUNT_NOT_VERIFIED`, `BANK_ACCOUNT_CHANGED` (409; the payout is put ON_HOLD), `MANUAL_ACTION_REQUIRED`,
`UNKNOWN_PAYOUT_ADAPTER`, `PAYOUT_NOT_PENDING`, `PAYOUT_LOCKED`, `PAYOUT_EVIDENCE_REQUIRED`, `PAYOUT_NOT_PAID`, `REASON_REQUIRED`,
`INVALID_STATUS_TRANSITION`, `SEPARATION_OF_DUTIES` (403), `DOCUMENT_IMMUTABLE` (403), and the 404s `PROJECT_NOT_FOUND`,
`MONITORING_PERIOD_NOT_FOUND`, `PROJECT_FARM_NOT_FOUND`, `CONFIG_VERSION_NOT_FOUND`, `PROJECT_COST_NOT_FOUND`, `SETTLEMENT_NOT_FOUND`,
`PAYOUT_NOT_FOUND`, `ADJUSTMENT_NOT_FOUND`, `ORDER_ITEM_NOT_FOUND`, `REFUND_NOT_FOUND`.

Phase 10: `NOT_A_BUYER`, `ORGANIZATION_REQUIRED`, `ORGANIZATION_INACTIVE`, `BUYER_PROFILE_LOCKED`, `IDENTIFIER_TYPE_REQUIRED`,
`KYC_DOCUMENT_REQUIRED`, `REASON_REQUIRED`, `BUYER_KYC_REQUIRED`, `NOT_A_SELLER`, `NO_AVAILABLE_CREDITS`, `LISTED_QUANTITY_EXCEEDS_AVAILABLE`,
`UNSUPPORTED_CURRENCY`, `INVALID_AMOUNT`, `QUANTITY_RANGE_INVALID`, `VALID_UNTIL_IN_PAST`, `LISTING_NOT_PENDING`, `LISTING_EXPIRED`,
`LISTING_EXISTS`, `LISTING_LOCKED`, `LISTING_NOT_ACTIVE`, `DUPLICATE_LISTING`, `SINGLE_SELLER_REQUIRED`, `SINGLE_CURRENCY_REQUIRED`,
`QUANTITY_OUT_OF_RANGE`, `LISTING_QUANTITY_EXCEEDED`, `RECIPIENT_ACCOUNT_REQUIRED`, `ORDER_NOT_CANCELLABLE`, `PAYMENT_IN_PROGRESS`,
`ORDER_NOT_PAYABLE`, `PAYMENT_AMOUNT_MISMATCH`, `PAYMENT_NOT_PENDING`, `ORDER_NOT_DELIVERABLE`, `ORDER_NOT_IN_ATTENTION`, `ORDER_NOT_PAID`,
`NOTHING_TO_RECONCILE`, `MANUAL_ACTION_REQUIRED`, `PAYMENT_PROVIDER_UNAVAILABLE`, `UNKNOWN_PAYMENT_ADAPTER`, `REFUND_NOT_ALLOWED`, `REFUND_EXISTS`,
`REFUND_EVIDENCE_REQUIRED`, `ORDER_LINKED` (409 from the 9B endpoints for order-owned reservations / transfers), `INSUFFICIENT_AVAILABLE`
(9B), `SEPARATION_OF_DUTIES` (403), and the 404s `LISTING_NOT_FOUND`, `ORDER_NOT_FOUND`, `ORDER_TRANSFER_NOT_FOUND`, `PAYMENT_NOT_FOUND`,
`REFUND_NOT_FOUND`, `BUYER_PROFILE_NOT_FOUND`.

Phase 9B: `INSUFFICIENT_AVAILABLE` (409; the loser of a race — a `CREDIT_DOUBLE_SPEND_CONFLICT` audit is recorded), `BATCH_NOT_ISSUED`,
`OPENING_EXISTS`, `OPENING_NOT_REQUESTED`, `RESERVATION_NOT_ACTIVE`, `EXPIRY_IN_PAST`, `QUANTITY_REQUIRED`, `SERIAL_RANGE_NOT_FOUND`,
`INVALID_RECIPIENT`, `SAME_PARTY`, `RECIPIENT_ACCOUNT_REQUIRED`, `TRANSFER_NOT_REQUESTED`, `RETIREMENT_NOT_REQUESTED`, `REGISTRY_EVIDENCE_REQUIRED`,
`DUPLICATE_REGISTRY_REFERENCE`, `RETIRED_SERIALS_MISMATCH`, `REVERSAL_NOT_ALLOWED`, `REVERSAL_NOT_POSSIBLE`, `REVERSAL_EXISTS`,
`REVERSAL_NOT_REQUESTED`, `IDEMPOTENCY_KEY_REUSED`, `LEDGER_ACTIVITY_EXISTS` (9A correction / cancellation after ledger activity),
`SEPARATION_OF_DUTIES` (403), `DOCUMENT_IMMUTABLE` (403), and the 404s `CREDIT_OPENING_NOT_FOUND`, `CREDIT_RESERVATION_NOT_FOUND`,
`CREDIT_TRANSFER_NOT_FOUND`, `CREDIT_RETIREMENT_NOT_FOUND`, `CREDIT_REVERSAL_NOT_FOUND`, `CREDIT_ENTRY_NOT_FOUND`, `ORGANIZATION_NOT_FOUND`.
