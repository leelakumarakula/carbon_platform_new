# Implementation status

| Phase | Scope (spec §47) | Status |
|---|---|---|
| 1 | Foundation: Angular, FastAPI, SQL Server, SQLAlchemy, Alembic, auth, RBAC, organizations, audit, dev setup | **Done** |
| 2 | Farmer & farm (KYC, polygons, history, evidence) | **Done** |
| 3 | Project | **Done** |
| 4 | Standard / activity / methodology | **Done** |
| 5 | MRV / GIS / sampling | **Done** |
| 6 | Sample / lab | **Done** |
| 7 | Calculation | **Done** |
| 8A | Internal pre-verification (findings, calculation report, internal readiness) | **Done** |
| 8B | VVB / ACVA verification (assignments, submission, findings, corrective actions, recorded decision) | **Done** |
| 9A | Registry submission & credit issuance (no inventory, ownership, reservation, transfer or retirement) | **Done** |
| 9B | Credit ledger: ownership, reservation, transfer, retirement (no marketplace, price or payment) | **Done** |
| 10 | Marketplace: buyer KYC, listings, orders, manual payments, refunds (no fee, tax, commission or payout) | **Done** |
| 11 | Revenue, farmer entitlement, payouts & reconciliation (configurable sharing; no tax, fee or payout provider) | **Done** |
| 12A | Background job infrastructure (Celery + Redis transport, SQL Server job record, scheduled expiry sweeps, orphan scan, retention infrastructure) | **Done** |
| 12B | Remaining production hardening (S3, antivirus, monitoring stack, Redis rate limiter, backup / restore, performance) | — |

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

## Phase 2 decisions (D1–D6) — applied

- **D1, D2:** transitions and agreement/bank statuses confirmed; documented as internal workflow states.
- **D3:** versioned `consent_definitions` with `required_for_activation`. A new version supersedes older grants
  without overwriting them. Admin API and page. DATA_PROCESSING v1 is the only definition; no others were invented.
- **D4:** permission-grant matrix (roles-permissions.md) and a privilege-escalation test suite.
- **D5:** Platform GIS Specialist role (`farms.review_cross_org`). Only that role can clear cross-organization
  overlaps; the decision is audited in both organizations.
- **D6:** basemap tile source from `MAP_TILE_*` settings, via `GET /api/v1/config/client`.

## Phase 3 — delivered

**Project domain connecting verified farms to a carbon project.** Details are in [project-workflow.md](project-workflow.md).

Backend
- Migration `0004`:
  - 14 tables: `projects`, `project_farms`, `project_participants`, `project_standards`, `project_activities`,
    `project_crediting_periods`, `project_baselines`, `project_carbon_rights`, `project_documents`,
    `project_boundaries`, `project_status_history`, `standards`, `activities`, `standard_activities`.
  - The project code sequence and the `geography` spatial index.
  - An append-only trigger on the status history.
  - The new document categories.
- Project state machine with all 20 lifecycle states allowed by the database. Only the early transitions are
  implemented (DRAFT → DATA_COLLECTION → ELIGIBILITY_REVIEW → STANDARD_SELECTED → ACTIVITY_SELECTED, plus return,
  re-open and close), each with readiness checklists and separation of duties.
- Farm participation:
  - Only verified farms of active farmers, in the project's organization and environment, can join.
  - Conflicts (farm overlaps, other participations) are shown and acknowledged, never auto-rejected.
  - Removal ends the participation and keeps the record.
- Carbon-rights references (agreement, document or reference) with independent review. Team membership tied to
  RBAC roles the user already holds.
- Standard and activity catalog with selection history. Crediting periods with replacement. Versioned baseline
  metadata, with no calculation. Project documents.
- Project boundary derived by SQL Server (`UnionAggregate`):
  - authoritative area with overlaps counted once;
  - validity check;
  - stale detection;
  - overlaps with other projects;
  - versioned, with GIS review.
- Farmer self-service participation view (`/projects/my-participation`).
- DEMO seed: 2 standards and 3 activities (illustrative), signed DEMO agreements, and 2 projects (one in
  DATA_COLLECTION, one taken through the real eligibility review to ACTIVITY_SELECTED).

Frontend
- Projects list, create, and detail with tabs:
  - overview with readiness and map;
  - farms (eligible-farm selection, conflict acknowledgement, carbon rights);
  - team;
  - boundary map with GIS review;
  - standard & activity;
  - crediting period & baseline;
  - carbon rights with review;
  - documents;
  - status history.
- Admin "Standards & activities" catalog page and the farmer's "My projects" page.

Verification (exit gate, 2 Oct 2026)
- Backend: **168 pytest tests passed**:
  - Phase 1 and 2: 132;
  - decisions D1–D6: 13;
  - Phase 3: 23 (18 project, 4 GIS, 1 DEMO seed).

  ruff clean. mypy clean (99 files). `alembic check`: no drift. Migration 0004 tested up/down/up.
- Frontend: **47 Vitest tests passed** (8 files). Production build OK (initial bundle 734 kB, 173 kB transferred).
- E2E (`npm run e2e:smoke`) passed:
  - Phases 1–2;
  - the Project Manager runs the whole Phase 3 flow in the UI: create, start data collection, add a verified farm
    (conflict acknowledged), boundary of 1.5014 ha computed by SQL Server, add team member, standard and activity,
    crediting period, baseline, carbon rights, submit, then ELIGIBILITY_REVIEW and status history;
  - all required audit events present;
  - the farmer sees only their own participation;
  - the buyer is blocked;
  - map tiles load from server configuration;
  - no console errors.

## Phase 4 — delivered

**Standard → activity → methodology → version, with candidate rules, specialist review and a locked version.**
Details are in [methodology-engine.md](methodology-engine.md).

Backend
- Migration `0005`:
  - 13 tables: `methodologies`, `methodology_activities`, `methodology_versions`, the applicability, monitoring,
    calculation and general rule tables, `methodology_documents`, `methodology_change_history`,
    `methodology_evaluations`, `methodology_evaluation_results`, `project_methodology_reviews`,
    `project_methodologies`.
  - Three append-only triggers.
  - New project columns and checks.
- Versioning: DRAFT → IN_REVIEW → APPROVED → SUPERSEDED / RETIRED, or WITHDRAWN.
  - The approver must not be the submitter.
  - Rules are editable only in DRAFT; a change means a new version, optionally copied, with rule-set revision
    counters.
  - Several versions can be approved at once, with effective dates.
- Deterministic rules engine (`rules/methodology_engine.py`, engine 1.0.0):
  - 15 operators;
  - outcomes APPLICABLE / NOT_APPLICABLE / NEEDS_INFORMATION / EVIDENCE_REQUIRED, with an explanation per rule;
  - facts derived from project data, plus labelled DECLARED facts that cannot override them.
- Project selection:
  - evaluate (append-only, facts snapshot);
  - specialist recommendation;
  - confirmation by the project developer (separation of duties, latest evaluation only, eligible outcomes only,
    approved version, configured crediting-period rules);
  - LOCK of methodology + version + rule revisions;
  - explicit audited unlock.
- Project workflow: ACTIVITY_SELECTED → METHODOLOGY_REVIEW → METHODOLOGY_CONFIRMED (with unlock and re-open).
  MRV_PLANNED and later states remain unreachable.
- Decision P3 is held in one policy function (`PROJECT_FARM_ORG_POLICY = SAME_ORGANIZATION`).
- DEMO: 2 illustrative methodologies (versions 1.0, 2.0, a 2.1 draft, and 1.0), a second demo methodology
  specialist (approver), and the Niphad project locked to DEMO-CCTS-SOIL 1.0.

Frontend
- Methodologies catalog page (methodologies, versions, new draft version, add methodology).
- Version page: metadata, rules by kind with add/remove in DRAFT, submit/approve/return/retire/withdraw, change history.
- Project "Methodology" tab:
  - declared facts;
  - evaluate candidates;
  - per-rule explanation table and the facts used;
  - specialist recommend / not recommend;
  - confirm & lock;
  - lock card with a newer-version notice;
  - unlock.

Verification (exit gate, 2 Oct 2026)
- Backend: **207 pytest tests passed**:
  - Phases 1–3 and the decisions: 168;
  - Phase 4: 39 (28 engine unit, 10 methodology API, 1 DEMO seed).

  ruff clean. mypy clean (107 files). `alembic check`: no drift. Migration 0005 tested up/down/up.
- Frontend: **54 Vitest tests passed** (9 files). Production build OK (initial bundle 735 kB, 172 kB transferred).
- E2E passed (Phases 1–4).
  - The E2E project was taken through eligibility.
  - The PM declared a fact and evaluated candidates (2 candidates).
  - The specialist opened the catalog (an approved version is read-only) and recommended a candidate.
  - The PM confirmed and locked DEMO-ALM-SOC 1.0.
  - The DEMO project shows its DEMO-CCTS-SOIL 1.0 lock.
  - All methodology audit events were present and there were no console errors.

## Phase 5 — delivered

**MRV plan → monitoring period → stratification → sampling design → points → field collection → dataset → QA → APPROVED.**
Details are in [mrv-workflow.md](mrv-workflow.md) and [sampling-workflow.md](sampling-workflow.md).

Backend
- Migrations `0006` + `0007` (field rules frozen per design version / field record): 17 tables (plans, measurements, periods, strata + characteristics + farms, designs + versions + allocations,
  points, relocations, assignments, field collections, monitoring records, evidence, datasets, QA reviews), three spatial indexes,
  the `SP-` and `FIELD-` sequences.
- MRV only on a LOCKED, valid methodology version. Requirements come from the version's monitoring and SAMPLING rules; anything
  not configured is **CONFIGURATION_REQUIRED** (listed, acknowledged at approval, reported by QA). No sampling rule is invented.
- Versioned plans (never overwritten), monitoring periods (9 states), versioned strata (SQL Server union geometry and area),
  versioned sampling designs with configured per-stratum counts (no per-area rule) and a stored random seed.
- Point generation: seeded candidates, SQL Server containment in the farm boundaries, spacing, duplicate check against existing
  points, project-boundary check, all-or-nothing. Relocation with old/new location, reason, requester, approval.
- Assignment to collectors; mobile field collection (`FIELD-YYYY-NNNNNN`) with SQL Server GPS distance / inside-farm checks,
  checklist, photo evidence (SHA-256), deviation notes, review, correction versions.
- Configurable monitoring (activity) data with typed values and versioned corrections; evidence linked to project / farm /
  period / point / collection / record.
- Versioned datasets with a frozen snapshot + SHA-256 (re-verified on approval), 15 deterministic QA checks, PASS / FAIL /
  REQUIRES_CORRECTION, approval by QA (not the submitter). The workflow ends at APPROVED; project status MRV_PLANNED → MONITORING;
  nothing moves to calculation.
- RBAC: `mrv.read/manage/collect/review/approve`, `sampling.manage/assign/collect/review`; separation of duties on every approval.
- DEMO: on the locked Niphad project — approved plan (gaps acknowledged), period in DATA_COLLECTION, 2 strata, approved design,
  6 points assigned to collector@demo, 2 accepted + 1 submitted collections with DEMO placeholder photos, practice records and a
  COLLECTING dataset. No lab results, calculations or credits.

Frontend
- MRV dashboard (`/mrv`); project MRV workspace with tabs: plans, monitoring periods, stratification (map), sampling design,
  points map + assignments + relocations + field-record review, monitoring data entry, evidence, datasets & QA, MRV history.
- Plan create and plan detail (submit / approve with gap acknowledgement / return / withdraw); dataset + QA review page.
- Mobile field collector dashboard (`/field`) and collection screen (`/field/collections/:id`: device GPS or manual entry,
  depth, checklist, camera photo, relocation request, submit). Nav: "MRV" (`mrv.read`), "Field work" (`sampling.collect`).

Verification (exit gate, 3 Oct 2026)
- Backend: **226 pytest tests passed** (Phases 1–4: 207; Phase 5: 19 — 8 MRV API, 5 GIS/sampling, 5 review decisions
  V1/S1/S2/SOC, 1 DEMO seed). ruff clean. mypy clean (118 files). `alembic check`: no drift. Migrations 0006 + 0007 tested
  upgrade → downgrade (to 0005) → upgrade on the test database.
- Frontend: **62 Vitest tests passed** (10 files). Production build OK (initial bundle 741 kB, 173 kB transferred).
- E2E passed (Phases 1–5): MRV manager created and submitted a plan in the UI, QA approved it (gaps acknowledged), period
  created and opened, design created and points generated, supervisor assigned points, collector collected on a 390 px phone
  viewport (GPS, checklist, photo), supervisor accepted, dataset submitted, QA ran checks (0 FAIL), recorded PASS and approved;
  period APPROVED, project MONITORING; buyer and farmer blocked from MRV; all required MRV audit events present; no console
  errors.

## Phase 6 — delivered

**Engagement → sample → custody → shipment → receipt → test → result → laboratory QA → APPROVED result with lineage.**
Details are in [laboratory-workflow.md](laboratory-workflow.md). Phase 6 produces no calculation, tCO2e, credit, verification,
issuance or retirement.

Backend
- Migration `0009`: 9 tables (engagements + rules, samples, custody events, shipments + items, tests, results, QA reviews), the
  `SMP-` / `SHP-` / `LT-` sequences, append-only triggers on custody events and QA reviews, the approved-result immutability
  trigger, filtered unique indexes (one ACTIVE engagement per project + laboratory, one open shipment item per sample, one ordinary
  test per sample + rule, one APPROVED result per root sample + rule), and the `LAB_REPORT` / `CUSTODY_DOCUMENT` document categories.
  No Phase 5 schema change.
- Two-sided engagements scoped to LABORATORY rules of the locked methodology version (proposer ≠ accepter; either side ends with a
  reason; never reactivated; wind-down rules after END).
- Samples only from SUBMITTED / ACCEPTED field records (field collection version kept forever), splits, depth / quantity / seal;
  automatic tests (one per in-scope rule with full lineage, no manual ordinary tests, no duplicates except explicit retests).
- Append-only custody with ordering, exceptions with reasons; shipments managed by supervisors / MRV managers; item-level receipt.
- Versioned results (exactly one value, NUMERIC or verbatim TEXT, no qualifier, no unit conversion, MANUAL / LIMS_IMPORT source,
  PDF report); 12 deterministic laboratory QA checks (exact unit match, CONFIGURATION_REQUIRED production block, report checksum,
  analysis timing, separation of duties); corrections and retests with a single authoritative result.
- Laboratory-facing API `/laboratory` with explicit allow-list schemas; project read model `/lab/results` + lineage (no drafts).
- `LimsAdapter` interface only. 11 `lab.*` permissions. All material actions audited (project-org and laboratory-org rows; laboratory
  rows carry no field data). Field checklist `PLATFORM-DEFAULT-2` (`sample_labelled_with_sample_code`); the Phase 5 field record shows
  AWAITING_ANALYSIS / ANALYSED (display only).
- DEMO: the full manual flow on the Niphad project with a second laboratory manager (`labqa@`) doing laboratory QA.

Frontend
- Laboratory workspace (`/laboratory`: engagements, incoming shipments with per-item receipt, sample registration, worklist, QA
  queue), test page (`/laboratory/tests/:id`: start, result entry with the rule unit pre-filled and an exact-match preview, PDF
  report, submit, withdraw, retest) and QA page (`/laboratory/qa/:id`: checks, separation-of-duties explanation, decision,
  configuration acknowledgement). Nav: "Laboratory" (`lab.lab_read`).
- MRV workspace tab "Samples & laboratory" (engagements, samples per field record, sealing, shipments, approved results), sample
  detail (`/mrv/samples/:id`, custody timeline) and result lineage (`/mrv/lab-results/:id`); "Register & seal sample" on the mobile
  field collection screen.

Verification (exit gate, 3 Oct 2026)
- Backend: **252 pytest tests passed** (Phase 6: 18 laboratory tests + the DEMO laboratory seed test). ruff clean. mypy clean
  (127 files). `alembic check`: no drift. Migration 0009 tested upgrade → downgrade (to 0008) → upgrade (twice) on the test database; its downgrade is refused while LAB_REPORT / CUSTODY_DOCUMENT documents exist (verified).
- Frontend: **74 Vitest tests passed** (11 files). Production build OK (initial bundle 742 kB, 174 kB transferred).
- E2E passed (Phases 1–6): MRV manager proposed an engagement and the lab manager accepted it (UI); the collector registered and
  sealed a sample from an accepted record on a phone viewport, one test was created automatically; the supervisor created and
  dispatched a shipment; the technician received it, registered it, analysed it with the exact rule unit, attached a PDF report and
  submitted; a different lab manager ran QA (0 FAIL) and approved; the MRV manager opened the full lineage and the record shows
  ANALYSED; laboratory users saw no farmer / farm / GPS / MRV data and were refused MRV pages; buyer and farmer were refused;
  the retest requester's approval returned SEPARATION_OF_DUTIES, the retest result was approved and superseded the first; after the
  engagement ended, receipt of an in-transit shipment was allowed and new shipments, retests and test starts returned
  ENGAGEMENT_NOT_ACTIVE; all required laboratory audit events present; no console errors.

## Phase 7 — delivered

**Readiness → frozen inputs → methodology-module execution (Decimal) → calculation QA → approval → recalculation / supersession,
with full lineage.** Details are in [calculation-workflow.md](calculation-workflow.md). Calculated tCO2e is labelled
"Calculated tCO2e — not verified, not issued"; no credit, serial, registry, verification, issuance, transfer, retirement, marketplace
or payout exists.

Backend
- Migration `0010`: `calculation_runs`, `calculation_inputs`, `calculation_outputs`, `calculation_qa_reviews`, sequence `CALC-`,
  filtered unique indexes (one open and one APPROVED run per reporting period, one final output per run), append-only inputs / outputs,
  completed-QA immutability and the run immutability trigger (no deletes; APPROVED → SUPERSEDED only). No earlier table changed.
- `app/calculation/`: framework (engine `calc-framework-1.0`, spec §18 methods, no default formula), application registry —
  **no module is registered** (no real methodology, no approved DEMO equations), so every project, including the DEMO Niphad project,
  is blocked with CONFIGURATION_REQUIRED — NO_CALCULATION_MODULE.
- Deterministic readiness (blocker list), input freeze into a canonical snapshot + SHA-256 + normalized input rows (APPROVED dataset and
  APPROVED laboratory results only; no substitution; exact units; text refused for numeric variables; input-size guard), currency
  re-check before execution (INPUTS_OUT_OF_DATE), synchronous Decimal execution with output SHA-256, 14 calculation QA checks
  (including reproducibility), approval with separation of duties, recalculation as a new run, comparison and lineage.
- Project status MONITORING → CALCULATION_READY (first successful freeze) → CALCULATED (first approved run); MRV stays possible in both.
- 4 permissions (`calculation.read/manage/review/approve`) on existing roles; all actions audited with hashes, versions and the result.

Frontend
- **Calculations** page (`/calculations`, `calculation.read`): project + period, readiness with the actual blockers, runs. The same panel
  is a "Calculations" tab in the MRV workspace. Run page (`/calculations/runs/:id`): actions, Inputs, Results (by step), QA, Lineage,
  History / Compare; labels "Calculated tCO2e — not verified, not issued" and, for DEMO, "DEMO — not carbon accounting".

Verification (exit gate, 3 Oct 2026)
- Backend: **262 pytest tests passed** (Phase 7: 10 calculation tests, using a TEST-only non-carbon fixture module that is never
  registered). ruff clean. mypy clean (137 files). `alembic check`: no drift. Migration 0010 tested upgrade → downgrade (to 0009) →
  upgrade (twice) on the test database; its downgrade is refused while calculation runs exist (verified).
- Frontend: **81 Vitest tests passed** (12 files). Production build OK (initial bundle 742 kB, 174 kB transferred).
- E2E passed (Phases 1–7): the analyst opened Calculations for the E2E project (approved dataset and laboratory results, DEMO methodology)
  and saw CONFIGURATION_REQUIRED — NO_CALCULATION_MODULE with the labels; the created run was BLOCKED on freeze with no value; the project
  stayed MONITORING; no module is registered; the QA officer can read; a request carrying a value is refused (422); buyer, farmer and
  laboratory users are refused; CALCULATION_RUN_CREATED and CALCULATION_BLOCKED were audited; no unexpected console errors.

## Phase 8A — delivered

**Internal pre-verification — not VVB/ACVA, not verification.** Details are in [pre-verification-workflow.md](pre-verification-workflow.md).
Phase 8 was split (decision B1): 8A internal pre-verification (this), 8B VVB/ACVA (not started).

Backend
- Migration `0011`: `calculation_findings` + append-only `calculation_finding_events`, `calculation_reports`, `calculation_readiness_reviews`,
  sequences CFND / CRPT / RDY, filtered unique indexes (one CURRENT report per run; one open and one READY readiness per period), documents
  category `CALCULATION_REPORT`, immutability triggers; downgrade refused while Phase 8A rows or report documents exist. No Phase 1–7
  data changed, no backfill.
- Findings: the six specification categories, `blocking` flag only, targets validated within the run, OPEN / RESPONDED / RESOLVED /
  WITHDRAWN with return and reopen, QA raises / resolves, analyst responds, resolver ≠ responder, withdraw by the raiser with a reason,
  append-only history, evidence attached to the run. Findings never change Phase 7 approval.
- Calculation report for APPROVED runs only: canonical JSON from frozen records + SHA-256, deterministic in-house text-only PDF (no new
  dependency) + SHA-256, generator version, tamper detection, immutability, supersession when the content changes, synchronous with a
  size guard.
- Internal verification readiness per monitoring period (no new project state; the project stays CALCULATED): deterministic
  prerequisites, analyst submits, independent QA officer approves or rejects, frozen package manifest + SHA-256, automatic invalidation.
- Lineage extended with findings, reports and readiness. No new permission or role; no VVB access.

Frontend
- Run page: **Calculation report** section (generate, download, verify) and **Findings** tab (raise, respond, return, resolve, reopen,
  withdraw, history); Lineage tab lists findings, reports and readiness. Calculations page / MRV tab: **Verification readiness** panel per
  period with "Internal readiness — not verification", blockers, reviews, approval and the package manifest view.

Verification (exit gate, 3 Oct 2026)
- Backend: **270 pytest tests passed** (Phase 8A: 8 tests — PDF writer, findings, reports, readiness, RBAC / isolation, DEMO, two trigger
  tests). ruff clean. mypy clean (146 files). `alembic check`: no drift. Migration 0011 upgrade → downgrade (to 0010) → upgrade (twice) on
  the test database; its downgrade is refused while Phase 8A rows exist (verified on the development database).
- Frontend: **86 Vitest tests passed** (13 files). Production build OK.
- E2E passed (Phases 1–8A): the QA officer raised a Methodology Issue finding on the E2E project's BLOCKED run in the UI, the analyst
  responded and QA resolved it; no report for the blocked run (RUN_NOT_APPROVED); the readiness panel showed "Internal readiness — not
  verification" and NO_APPROVED_CALCULATION; creating readiness was refused; Niphad: NO_APPROVED_CALCULATION with CONFIGURATION_REQUIRED —
  NO_CALCULATION_MODULE; VVB, buyer, farmer and laboratory users refused; the project stayed MONITORING; finding audit events present; no
  unexpected console errors.

## Phase 8B — delivered

**VVB / ACVA verification only — no validation, registry, issuance or credits.** The platform records an external VVB's decision; it
never verifies. Details: [verification-workflow.md](verification-workflow.md) (decisions C1–C20, interpretations I1–I6).

Backend
- Migration `0012`: `verification_assignments`, `verification_submissions`, `verification_findings` + append-only events, `corrective_actions`
  + append-only events, `verification_decisions`; sequences VAS / VSUB / VFND / CAR / VDEC; filtered unique indexes (one open assignment per
  period, one SUBMITTED submission per assignment, one CURRENT decision per period); documents categories `VERIFICATION_REPORT` /
  `VERIFICATION_EVIDENCE` (PDF only); seven triggers; downgrade refused while Phase 8B rows exist. No earlier data changed.
- Permissions `verification.read / manage / respond` (project roles) and `verification.vvb_read / vvb_review / decide` (VVB / ACVA Reviewer
  only — no other grant).
- Two APIs as for laboratories: `/verification` (project side) and `/vvb` (allow-list workspace, scoped per assignment of the caller's
  ACTIVE, same-environment VVB organization). Every action audited in both organizations.
- Assignment lifecycle with COI on acceptance and replacement lineage; submission only of the period's currently valid Phase 8A READY
  package (re-checked; lazily INVALIDATED / SUPERSEDED, never mutated); findings and corrective actions (VVB raises / closes, project
  responds); decision with the VVB report PDF, separation of duties against finding raisers, optional "VVB-stated verified quantity" kept
  apart from the calculated quantity; recalculation supersedes a recorded decision; aggregate project status CALCULATED → VERIFICATION →
  VERIFIED; decision lineage down to farms.

Frontend
- MRV workspace **Verification** tab (per period): calculated label, VVB assignments (propose, withdraw, terminate, submit), submissions,
  findings with responses and evidence, decisions with the VVB-stated quantity, report download and lineage.
- **VVB workspace** (`/vvb`, `verification.vvb_read`): assignment list; assignment page with COI acceptance / decline, package (farms with
  farmer codes, points, laboratory results, calculation), manifest documents, findings / corrective actions and the decision form.

Verification (exit gate, 3 Oct 2026)
- Backend: **283 pytest tests passed** (Phase 8B: 13 tests). ruff clean. mypy clean (155 files). `alembic check`: no drift. Test database:
  upgrade base → 0012, downgrade 0012 → base, upgrade base → 0012 again. Development database: the 0012 downgrade is refused while Phase 8B
  rows exist.
- Frontend: **94 Vitest tests passed** (14 files). Production build OK.
- E2E passed (Phases 1–8B): the PM proposed DEMO-VVB-C in the Verification tab, the VVB reviewer accepted it with a COI declaration in the
  VVB workspace, submission was refused (409 NO_READY_PACKAGE) for the E2E project and for Niphad, no submission or decision exists, the
  project stayed MONITORING, the VVB user was refused project / calculation / project-side verification / farmer / audit endpoints and saw
  only the VVB workspace, non-VVB users were refused `/vvb`, assignment audit events present, no unexpected console errors.

## Phase 9A — delivered

**Registry submission and credit issuance — no inventory, ownership, reservation, transfer or retirement.** Registries are external
counterparties; the platform records what a registry states, with evidence. Details: [registry-workflow.md](registry-workflow.md)
(decisions D1–D18).

Backend
- Migration `0013`: `registry_accounts`, `registry_project_registrations`, `registry_submissions`, append-only `registry_events`,
  `credit_issuances`, `credit_batches`, `credit_serial_ranges`; sequences RREG / RSUB / ISS / CB; filtered unique indexes (one open / accepted
  submission per period across registries; registry + external submission / issuance / project ID; registry + serial start / end of current
  ranges; idempotency keys); documents categories REGISTRY_SUBMISSION / REGISTRY_RESPONSE / ISSUANCE_STATEMENT (PDF only); seven triggers;
  downgrade refused while Phase 9A rows exist. No earlier data changed.
- `app/integrations/registry.py`: RegistryAdapter Protocol + ManualRegistryAdapter (never simulates); selected per registry account. A
  TEST-only API adapter (`tests/registry_fixture.py`) is injected in tests and never registered.
- Permissions `registry.read / manage / confirm` and `credits.read` (D18). APIs `/registry` (project side) and read-only `/credits`.
- Eligibility (CURRENT VERIFIED VVB decision with a stated quantity, REGISTERED registration, active account / registry, environment, one
  submission per period, configured checklist), frozen registry-submission-v1 snapshot + SHA-256, manual evidence-backed workflow,
  outbox-style idempotency with SUBMISSION_UNCONFIRMED and reconciliation (no automatic retry), registry rejection / acceptance, issuance
  with dual confirmation, tranches, issued ≤ VVB-stated only with explicit unit equivalence, whole units, registry serials verbatim
  (duplicates refused; parser-based length / overlap), correction and cancellation history, SOURCE_SUPERSEDED on recalculation, aggregate
  project status VERIFIED → ISSUED, batch lineage down to farmer codes.

Frontend
- MRV workspace **Registry** tab and `/registry` page (registry.read): three separate quantity cards (calculated / VVB-stated / registry-issued),
  eligibility blockers, accounts and registrations, submission lifecycle with evidence uploads, snapshot, events, documents, issuance
  recording and second-person confirmation, batches and serial ranges. `/credits` (credits.read): read-only issued batches with lineage.
  DEMO shows "DEMO — no registry issuance".

Verification (exit gate, 3 Oct 2026)
- Backend: **293 pytest tests passed** (Phase 9A: 10 test functions covering the 49 listed scenarios). ruff clean. mypy clean (164 files).
  `alembic check`: no drift (development and test databases). Test database: upgrade base → 0013, downgrade 0013 → base, upgrade base → 0013
  again. Downgrade guard: refused while Phase 9A rows exist (dedicated test inserting a registry account in a rolled-back transaction); the
  development database holds no Phase 9A rows and was not downgraded.
- Frontend: **101 Vitest tests passed** (15 files). Production build OK.
- E2E passed (Phases 1–9A) after the final code changes: the Registry tab showed "DEMO — no registry issuance", the three labelled
  quantity cards and NO_VERIFIED_DECISION; creating a registry submission was refused (409 NO_VERIFIED_DECISION) for the E2E project and for
  Niphad; the Registry Manager saw Registry and Issued credits (no batches); no DEMO credit exists; the only DEMO registry is "Carbon Registry
  R (DEMO)"; VVB, buyer, farmer and laboratory users were refused the registry and credits APIs; the project stayed MONITORING; no unexpected
  console errors.

## Phase 9B — delivered

**Credit ledger — ownership, reservation, transfer and retirement of registry-issued credits; no marketplace, price, order or payment.**
Details: [credit-ledger-workflow.md](credit-ledger-workflow.md) (decisions X1–X5, D1–D21).

Backend
- Migration `0014`: `credit_ledger_entries` (append-only), `credit_positions` (immutable UTXOs), `credit_openings`, `credit_reservations`,
  `credit_transfers`, `credit_retirements`, `credit_reversals`; sequences LEDG / OPN / RSV / TRF / RET / REV; documents categories
  RETIREMENT_CERTIFICATE / REGISTRY_TRANSFER_EVIDENCE (PDF only); seven triggers (conservation on posting, consume-once, RETIRED terminal,
  no delete, final workflow states immutable); downgrade refused while Phase 9B rows exist. No earlier data changed.
- `ledger_service`: one transaction per movement; UPDLOCK / HOLDLOCK / ROWLOCK locked reads in deterministic order; guarded single-row
  consumption (loser → 409 INSUFFICIENT_AVAILABLE + CREDIT_DOUBLE_SPEND_CONFLICT audit); deadlock retry; Idempotency-Key replay on every POST;
  dual-control opening (initial owner = holding registry account's organization), reservations with lazy expiry + sweep, INTERNAL / REGISTRY
  transfers (REGISTRY completion needs the registry reference + evidence PDF), retirements (RETIRED only with the registry reference, date
  and RETIREMENT_CERTIFICATE; registry-stated serials checked against the quantity), compensating REVERSAL of INTERNAL transfers under dual
  control, manual reconciliation (MISMATCH recorded, never auto-fixed), retirement lineage. 9A correction / cancellation guarded
  (LEDGER_ACTIVITY_EXISTS; untouched batches closed by an explicit ISSUANCE_ADJUSTMENT).
- Adapter: `transfer_credits`, `retire_credits`, `get_credit_inventory` (MANUAL raises `ManualActionRequired`; the TEST adapter implements them).
- Permissions `credits.manage`, `credits.confirm`, `credits.holder_read`, `credits.holder_retire` (D16). Holder view allow-listed.

Frontend
- `/ledger` (credits.read): inventory with Issued (registry) / Available / Reserved / Pending transfer / Pending retirement / Transferred out /
  Retired; open / confirm opening; batch detail with per-owner balances, positions and entries; reservation, transfer and retirement forms;
  second-person completion (evidence upload), retirement recording (certificate, reference, date, serials), reversals, retirement lineage.
  `/holdings` (credits.holder_read): own positions and retirement requests. Idempotency-Key per submission. DEMO note; no marketplace UI.

Verification (exit gate, 3 Oct 2026)
- Backend: **306 pytest tests passed** (Phase 9B: 7 functional test functions covering the listed scenarios + 6 concurrency / trigger
  tests). Concurrency tests A–E run on separate database connections (threads, own sessions, barrier) against a committed world restored
  from a SQL Server database snapshot afterwards: A reservations 600 + 600 / 1000, B transfers 600 + 600 / 1000, C retirements 80 + 80 / 100,
  D reservation vs retirement — exactly one winner each, the loser 409 INSUFFICIENT_AVAILABLE, the owner's total unchanged (A also asserts
  the loser's CREDIT_DOUBLE_SPEND_CONFLICT audit); E fault
  injection before posting — full rollback. ruff clean. mypy clean (168 files). `alembic check`: no drift (development and test databases).
  Test database: downgrade 0014 → base, upgrade base → 0014, downgrade → base, upgrade → 0014. The development database (no Phase 9B rows)
  is at 0014 and was not downgraded.
- Frontend: **111 Vitest tests passed** (16 files). Production build OK.
- E2E passed (Phases 1–9B) after the final code changes: the Credit Manager saw "Credit ledger" with "DEMO — no registry-issued credits",
  the seven labelled columns and no batch; the inventory API returned no DEMO batch; opening, reserving, transferring and retiring a
  non-existent batch returned 404 CREDIT_BATCH_NOT_FOUND; a request carrying a balance was rejected (422); the buyer saw only "My credits"
  with the DEMO note and no holdings and was refused the ledger (UI and API); VVB, farmer, laboratory and buyer users were refused the
  inventory and non-holders the holdings API; no unexpected console errors.

## Phase 10 — delivered

**Marketplace — buyer KYC, listings, orders, manual payments, refunds; the Phase 9B ledger stays the only ownership / availability record; no
fee, tax, commission, revenue or payout.** Details: [marketplace.md](marketplace.md) (locked decisions D1–D36).

Backend
- Migration `0015`: buyer_profiles, buyer_kyc_reviews (append-only), marketplace_listings, listing_documents (append-only), orders,
  order_items, payments, payment_events (append-only, unique per provider event), refunds; sequences LST / ORD / PAY / RFD; documents
  categories BUYER_KYC_DOCUMENT (restricted), PAYMENT_EVIDENCE, REFUND_EVIDENCE, ORDER_CONFIRMATION, LISTING_DOCUMENT (PDF only); nine
  triggers; downgrade refused while Phase 10 rows exist. No invoice table / INV sequence (tax and invoice rules undefined — D10).
- Phase 9B refactored into composable `*_in_tx` functions (reserve, release, expire, request / complete / close transfer) with the same
  locks, guarded consumption, posting checks and triggers; public 9B behaviour unchanged; a link guard makes the public 9B actions refuse
  order-owned reservations / transfers (ORDER_LINKED).
- T1 placement (KYC gate → listings locked → derived remaining under the lock → order + items + one 9B reservation per item, all or nothing),
  T2 manual payment recording, T3 confirmation (reservations consumed into 9B transfer requests, or ATTENTION_REQUIRED when a reservation
  was lost), T4 order-linked delivery (9B completion / rejection + item + order in one transaction), seller resolution (re-reserve +
  re-request), lazy listing / order expiry, whole-payment refunds with dual control (before delivery: order REFUNDED; after delivery: money
  only), deterministic ORDER_CONFIRMATION PDF (not a tax invoice), order lineage into the 9B / 9A chains.
- `PaymentAdapter` Protocol + `ManualPaymentAdapter` (the only runtime adapter; `PAYMENT_PROVIDER=manual`); provider outbox, events
  (deduplicated), reconciliation and provider refunds exercised with the TEST-only adapter (`tests/payment_fixture.py`, never registered).
  No public webhook route.
- 12 permissions + the platform Marketplace Compliance Officer role (D27, D28); demo account `compliance@demo.carbon.example`.

Frontend
- Marketplace (authenticated catalogue, allow-listed disclosure, order builder — one seller / one currency), Buyer profile & KYC documents,
  Orders (buyer: pay with evidence, cancel, confirmation, lineage; seller: cancel, resolve, confirm / reject payments, refunds, delivery
  completion for credits.confirm holders), Listings (create from the ledger inventory, submit, approve, pause / resume, close, publish PDFs),
  Payments (finance queue), KYC review (platform). The ledger page routes order-linked transfers through the order. DEMO shows
  "DEMO — no registry-issued credits; nothing is listed"; navigation is permission-driven (new any-of support).

Verification (exit gate, 3 Oct 2026)
- Backend: **326 pytest tests passed** — Phase 10: 10 functional test functions (the 44 listed areas) + 10 real-concurrency / trigger
  tests. Concurrency scenarios A–I run on separate database connections against a committed world restored from a SQL Server database
  snapshot: A 100 + 100 / 100 and B 60 + 60 / 100 — exactly one order, the other 409; C two fitting orders — both, nothing lost; D
  confirmation vs expiry — one RESERVATION_EXPIRE entry, ATTENTION_REQUIRED, no transfer; E duplicate event — one APPLIED, one DUPLICATE;
  F event vs cancellation — consistent either way; G double cancellation — one; H refund vs delivery — delivery always completes, no credit
  reversed; I delivery failure vs resolution — consistent either way; every scenario checks no double spend, no negative inventory,
  conservation, no orphan reservation / transfer and no duplicate payment / transfer / refund effect. The 8B / 9A / 9B boundary tests were
  narrowed deliberately (marketplace / orders / payments only under their own prefixes; payouts, checkout, invoices, offers, pricing still
  forbidden). ruff clean. mypy clean (178 files). `alembic check`: no drift (development and test databases). Test database: 0015 → base →
  0015 → base → 0015. Downgrade guard tested. The development database is at 0015 (not downgraded).
- Frontend: **118 Vitest tests passed** (17 files). Production build OK.
- E2E passed (Phases 1–10) after the final code changes: the buyer saw Marketplace / Orders / Buyer profile / My credits (no Payments /
  Listings) and "DEMO — no registry-issued credits; nothing is listed" with no listing; the DEMO buyer's KYC was submitted in the UI (profile,
  PDF, submission) and verified by the compliance officer in the KYC review queue (later runs find it verified); ordering was refused (404
  LISTING_NOT_FOUND) and a request carrying a total rejected (422); no DEMO order, payment or listing exists; finance saw Payments and
  Listings; a DEMO listing of a non-existent batch was refused (404 CREDIT_BATCH_NOT_FOUND); VVB, farmer and laboratory users were refused
  the marketplace, orders, payments and KYC APIs; no unexpected console errors or 5xx responses.

## Phase 11 — delivered

**Revenue, farmer entitlement, payouts and reconciliation — a money ledger beside the 9B credit ledger; every economic value is approved,
versioned configuration (no hard-coded percentage, fee or tax).** Details: [payout-workflow.md](payout-workflow.md) (decision lock
[phase-11-decision-lock.md](phase-11-decision-lock.md); D9 per order item, D10 reversals, D11 chargebacks out of scope, D12 approved
per-period farm allocation).

Backend
- Migration `0016`:
  - tables: revenue_records (append-only), revenue_share_versions, farm_allocation_versions, farm_allocation_lines (append-only),
    project_costs, settlement_runs, settlement_revenue_items / settlement_cost_items (one ACTIVE claim per record),
    farmer_entitlements (append-only), payouts, payout_transactions (append-only), payout_reconciliations (append-only),
    payout_adjustments;
  - sequences RVN / RSH / FAL / PCS / SET / PYT / ADJ;
  - documents categories COST_EVIDENCE, PAYOUT_EVIDENCE (restricted) and RECONCILIATION_EVIDENCE (restricted), all PDF only;
  - 13 triggers;
  - downgrade refused while Phase 11 rows exist.
- Revenue:
  - recognized per order item inside the Phase 10 delivery-completion transaction (payment CONFIRMED + 9B transfer COMPLETED);
  - reversed by a completed refund in the refund transaction;
  - idempotent, with re-run endpoints.
  The two hooks are the only Phase 10 change.
- Configuration:
  - revenue-share versions and per-period farm allocations, with author ≠ approver, immutable once approved, superseded by new versions;
  - project costs with PDF evidence, recorder ≠ approver, and corrections as negative costs.
- Settlement engine (`fin-calc-1`):
  - Decimal only;
  - per-line quantization to the currency minor unit with the version's rounding mode;
  - frozen canonical snapshot + SHA-256;
  - verify / recompute;
  - concurrency-safe claims;
  - recovery cases for reversals of paid-out revenue.
- Payouts:
  - lifecycle D20;
  - calculator ≠ approver ≠ executor, executor ≠ reconciler;
  - VERIFIED bank account referenced (last 4) and re-checked under lock at execution (ON_HOLD on change);
  - MANUAL adapter (PAID with reference + PDF);
  - reissue of failed payouts.
- Reconciliation: MATCHED / EXCEPTION against statements, then run completion.
- Lineage, financial summary and farmer self-service.
- 14 permissions (`revenue.*`, `settlement.*`, `payouts.*`, `sharing.*`, `costs.*`); no new role.

Frontend
- Finance section: **Revenue & costs**, **Revenue sharing**, **Settlements** and **Payouts** (with reconciliation and recovery cases).
- Farmer **My payouts**.
- DEMO note and configuration-required states. No form sends a payout amount.

Tests
- `tests/test_finance.py`: RBAC, client-amount refusal, recognition / reversal, configuration, the full settlement → payout →
  reconciliation lifecycle, recovery cases, netting, the TEST adapter, rounding, DEMO and the downgrade guard.
- `tests/test_finance_concurrency.py`: database snapshot; eight races (recognition × delivery, calculation × 2, settlement approval × 2,
  payout creation × 2, execution × 2, bank change × execution, reconciliation × 2, refund × settlement) and the direct-SQL trigger tests.
- `finance.spec.ts`.
- E2E: Phase 11 DEMO-honest block.

## Phase 12A — delivered

**Background job infrastructure and safe scheduled operational work. SQL Server is the system of record and Redis only transports job
ids; no business semantics changed.** Details: [background-jobs.md](background-jobs.md). Design and decisions:
[phase-12-discovery.md](phase-12-discovery.md), [phase-12-decision-lock.md](phase-12-decision-lock.md) (lock record).

Backend
- Migration `0017`:
  - `background_jobs`, `background_job_attempts` (append-only), `background_worker_heartbeats`;
  - JOB- sequence;
  - user status `SYSTEM` plus two non-login SYSTEM actors (LIVE, DEMO);
  - two triggers;
  - downgrade guard.
- Celery application (`app/workers`):
  - JSON only, no result backend, late acknowledgement, reject on worker lost, prefetch 1;
  - queues `default` / `maintenance`;
  - beat schedule: expiry sweeps, orphan scan, retention, recovery tick;
  - worker heartbeat.
- Job service:
  - transactional enqueue (outbox) and publication after commit;
  - SQL claim under row locks, with a lease;
  - append-only attempts;
  - retry classification and deterministic exponential backoff;
  - stale-lease recovery and republication;
  - environment validation;
  - audit (`JOB_*`) and workflow events;
  - structured JSON logs;
  - `manage.py jobs-recover`.
- Allow-listed registry:
  - reservation expiry and order + listing expiry, through the existing 9B / 10 functions; lazy expiry is unchanged;
  - orphan-file scan (detection only);
  - retention purge (no policy, so it purges nothing).
- `/api/v1/jobs`: list / get / attempts / registry / status / cancel / retry / allow-listed trigger. Permissions `jobs.read` /
  `jobs.manage` (Platform Administrator).

Frontend
- Administration → **Background jobs**: status panel (database, broker, worker heartbeat, counts), job list, detail with attempts,
  audited cancel / retry, read-only registry, DEMO note.

Tests
- `tests/test_jobs.py`:
  - registry allow-list and financial boundary;
  - SYSTEM actor;
  - enqueue / idempotency / outbox;
  - lifecycle; retries and exhaustion; non-retryable errors;
  - stale-lease recovery; environment isolation;
  - API RBAC;
  - reservation, marketplace and pending-payment sweeps;
  - orphan scan; retention; schedule slots.
- `tests/test_jobs_concurrency.py`:
  - database snapshot; duplicate delivery; two sweeps on the same rows;
  - worker crash after partial progress; rollback after claim;
  - a real Celery worker over the Redis protocol: publication, duplicate message, sweep, Redis outage → cleared broker → republish.
- `jobs.spec.ts`.
- E2E: Phase 12A block.

## Phase 12B-I — delivered

**Storage and document safety: MinIO object storage through the S3 API, antivirus scanning with append-only history, quarantine and
security release, safe orphan deletion, local → MinIO migration.** Details: [storage-and-scanning.md](storage-and-scanning.md). Design
and decisions: [phase-12b-discovery.md](phase-12b-discovery.md), [phase-12b-decision-lock.md](phase-12b-decision-lock.md) (D1–D51;
12B-I implements D2–D17).

Backend
- Migration `0018`: `document_scans` (append-only trigger; downgrade refused while scan history exists). No Phase 1–12A table changes.
- `app/integrations/s3.py`: standard-library SigV4 client (no boto3 / MinIO SDK); refuses XML with a DTD.
- `S3ObjectStorage`: one private, versioned bucket per environment; SSE-S3 required and confirmed; SHA-256 as the signed payload hash and
  object metadata; server-generated keys only; no delete on the application identity. Separate deletion identity for orphan cleanup.
  `local` storage refused in production.
- Upload order: scan → write object → verify (size, SHA-256, SSE) → database rows → commit. A storage outage leaves no database row.
- Antivirus boundary `AntivirusScanner` + registry. No vendor selected (D13): production refuses to start without a registered real
  scanner and its endpoint / key. The `signature` scanner records NOT_SCANNED (never CLEAN). LIVE production refuses uploads while the
  scanner is unavailable; elsewhere the document is quarantined and a rescan queued.
- Quarantine / background rescan / release-after-clean-rescan; `scan_state` on `DocumentOut`; security endpoints under
  `/api/v1/evidence/documents` (`security.read` / `security.manage`).
- Jobs: `ORPHAN_FILE_SCAN` now deletes aged, unreferenced, server-generated objects after a locked re-check (audited
  `STORAGE_ORPHAN_DELETED`); new `DOCUMENT_RESCAN` (`maintenance.rescan_documents`, `JOB_RESCAN_INTERVAL`).
- `manage.py storage-migrate [--dry-run]`: copy + verify, idempotent, never deletes local originals.
- `app/core/metrics.py`: in-process counters / timings (AV, storage, orphan deletions) — exposition arrives with 12B-II.
- `docker-compose.yml` + `docker/minio-init.sh`: MinIO with SSE-S3 (development KMS key), buckets, versioning, two identities (not run
  here: Docker is not installed).

Frontend
- Documents show the scan state; quarantined documents cannot be downloaded from the UI.
- Security → **Document quarantine**: quarantined documents, scan history, rescan, release (reason; server decides).

Tests
- `tests/test_storage_av.py`: AWS SigV4 known-answer tests; S3 protocol against the TEST-only stub server `tests/s3_stub.py` (SigV4
  verification, payload hash, SSE, versioning, policies, two identities, pagination); keys; production guards; documents end to end on
  S3; antivirus clean / infected / unavailable with the TEST-only double `tests/av_fixture.py`; append-only history; quarantine / rescan /
  release / RBAC / environment isolation; orphan deletion (local and S3); migration.
- `tests/test_storage_concurrency.py`: real two-connection race between an uncommitted upload and orphan deletion (commit → kept;
  rollback → deleted).
- `quarantine.spec.ts`; E2E: Phase 12B-I block.

## Phase 12B-II — delivered

**Runtime hardening.** Details and runbooks: [runtime-hardening.md](runtime-hardening.md). Decisions D18–D24, D30–D33, D38–D47 of
[phase-12b-decision-lock.md](phase-12b-decision-lock.md). No migration.

Backend
- Rate limiting behind the existing abstraction: Redis backend (hashed keys, counters only) or in-process; production requires Redis.
  Locked D19 limits as settings: refresh 100 / IP, uploads 100 / user, 1,000 / user, 5,000 / organization, 10,000 deployment-wide burst;
  login / global / lockout unchanged. Redis outage → fail open (D20), logged, counted, visible in readiness.
- Trusted proxies (`TRUSTED_PROXIES`); uvicorn `--no-proxy-headers`.
- Streamed request-body limit (chunked bodies included).
- `/health/live`, `/health/ready` (database + schema head, storage, antivirus, broker, limiter; 503 only for failures / production
  misconfiguration); `/health` without the environment in production. Swagger / OpenAPI off in production.
- Production guards: TLS + ACL-user Redis, shared limiter, secret-store mount (`SECRETS_DIR`, no `.env`, no secrets in environment
  variables), no simulated providers, JSON logs, metrics token length. Celery broker TLS verification.
- MultiFernet data-key rotation + `manage.py rotate-data-key`; JWT `kid` signing-key rotation.
- Structured JSON logging with redaction and request / job correlation; `GET /metrics` (OpenMetrics / JSON, bearer token).
- External-notification boundary: SMTP configuration only, delivery deferred, opt-in / opt-out / language / quiet-hours gate.
- SQL-side scoping, optional limit / offset and preloading for orders, listings, refunds, finance projects; lazy expiry kept.

Tests
- `tests/test_runtime_hardening.py`, `tests/test_performance.py` (synthetic harness, no SLA assertions); E2E: Phase 12B-II block.

## Phase 12B-III — delivered

**Operations.** Runbooks: [operations-runbook.md](operations-runbook.md), [object-storage-recovery.md](object-storage-recovery.md),
[production-readiness.md](production-readiness.md). Decisions D25–D29, D31, D43–D45, D48, D50, D51. No migration.

- `manage.py backup` (CHECKSUM, COMPRESSION, VERIFYONLY; production: encrypted + off-host or refused), `restore-drill` (COPY_ONLY backup →
  verify → restore into `*_restoretest` → verify-restore → drop), `verify-restore` (schema manifest, triggers, append-only probe, ledger
  conservation, settlement reproducibility, report hashes, scoping, objects, row counts, CHECKDB), `schema-manifest`.
- Deployment templates: SQL Agent backup jobs (LOG 5 min, DIFF 6 h, FULL weekly, 60-day history), MinIO object-locked backup bucket,
  replication and version lifecycle.
- `RETENTION_PURGE` now applies 60-day operational policies (access logs, read notifications, worker heartbeats, temporary files);
  append-only / financial / credit / audit / verification records are never purged.
- Disk safety: readiness `disk` check, gauges, upload / drill / backup headroom checks, test-suite guard. Backup-age and disk gauges on
  `/metrics`. Alert catalogue and 16 runbooks for Platform / DevOps.
- Tests: `tests/test_operations.py`; finance-world verify-restore + tamper detection; operational-volume performance baselines.

## Known limitations and open items

- Rate limiting uses Redis in production (Phase 12B-II); a Redis outage fails open (D20). Real Redis, secret store, monitoring and
  SMTP integrations are pending the deployment environment.
- `docker-compose.yml` has not been run on the development machine (Docker not installed).
- Status values for later entities (orders, payouts, lab results, …) are still to be confirmed. See the
  architecture document's open questions.
- Phase 2:
  - Phase 12B-I built the MinIO adapter and the antivirus boundary. No antivirus vendor is selected (D13): the vendor adapter is a
    deployment prerequisite, and production refuses to start without it. The MinIO adapter is verified against a TEST-only S3 stub;
    real MinIO integration is pending the deployment environment.
  - Offline capture and sync are not built.
  - Notifications are in-app only.
  - Satellite evidence is recorded manually only (no satellite adapter yet; Phase 5 adds field evidence only).
  - OpenStreetMap public tiles are the development default; production sets `MAP_TILE_*` (D6).
  - A1–A5 were approved (D1–D3); the GIS thresholds (A6) and the farm verification gates (A7) are still to be confirmed.
- Phase 3:
  - Access is organization-scoped. Project-team membership is not yet used to narrow access.
  - Only farms of the project's own organization can join (P3).
  - Cross-organization overlapping project boundaries are flagged, not adjudicated.
  - Each E2E run creates a DEMO-environment project in the development database.
  - The project assumptions P1–P9 in project-workflow.md need confirmation.
- Phase 4:
  - No real methodology (VM0042, CCTS, …) is configured. Its rules must be entered from the authoritative source
    by a specialist and approved by a second person.
  - Calculation readiness is NOT_PRODUCTION_READY everywhere.
  - Assumptions M1–M5 in methodology-engine.md need confirmation.
- Phase 5:
  - Offline field capture and sync are not built; the field screens need a connection.
  - Decision V2 (locked 3 Oct 2026, after the Phase 5 commit): sample-based parameters (SOC, bulk density, …) are
    authoritative only as approved Phase 6 laboratory results. Phase 5 refuses them as monitoring data
    (`LABORATORY_RESULT_REQUIRED`) and keeps only field/sample traceability; QA reports them as AWAITING_ANALYSIS.
  - Decision V2-A (uncommitted at the time of writing): measurement provenance is declared explicitly on each methodology
    monitoring rule (`measurement_source` FIELD / FIELD_ACTIVITY / LABORATORY; migration 0008) and the V2 guard reads it —
    never the unit, name, type or level.
  - Decision V2-B (uncommitted at the time of writing): user-created measurements are SUPPLEMENTARY_OBSERVATION — kept, marked
    non-authoritative in the API and in dataset snapshots, never a laboratory result or calculation input. No schema change.
  - Decision V2-C (uncommitted at the time of writing): field-kit measurements are FIELD or LABORATORY exactly as the
    methodology rule declares `measurement_source`; no name/unit/type/level inference and no parameter-specific logic.
  - Decisions V1, S1, S2 were applied after review (production block of gap approval; GPS / duplicate / checklist / photo values
    are versioned, configurable PLATFORM DEFAULTS frozen per design version and field record — migration 0007). Assumptions
    V3–V4 and S3–S4 still need confirmation. No production exception to V1 exists.
  - Each E2E run adds an MRV plan, period, points and dataset to its DEMO-environment project in the development database.
- Phase 6:
  - No LIMS is connected (interface only); results are entered manually.
  - Sample retention, return and disposal are out of scope (custody ends at ANALYSED).
  - Analysis times are entered to the second; laboratory QA compares them with the receipt time at whole-second precision.
  - Each E2E run adds an engagement, two samples, two shipments and laboratory results to its DEMO project in the development
    database.
- Phase 7:
  - No calculation module is registered: a real methodology must be entered from its authoritative source and its module implemented
    and verified with reference tests; illustrative DEMO equations need explicit approval. Until then every calculation is blocked
    (CONFIGURATION_REQUIRED — NO_CALCULATION_MODULE).
  - Modules are NOT_PRODUCTION_READY (blocked in production); the production-readiness workflow is deferred.
  - Execution is synchronous with an input-size guard; background execution (Celery / Redis) is deferred to Phase 12.
  - Reference / baseline periods for multi-period (remeasurement) modules and `calculation_run_datasets` come with the first module that
    needs them. Calculation report PDF, findings and farm-level allocation are deferred.
  - Each E2E run adds a BLOCKED calculation run to its DEMO project in the development database.
- Phase 8A:
  - Internal only: VVB/ACVA organizations, assignment, VVB findings, corrective actions, validation / verification decisions and states
    are Phase 8B (not started). READY is "internally approved for submission to verification", not verification.
  - Without a registered calculation module no run reaches APPROVED outside tests, so reports and READY readiness are exercised only with
    the TEST-only fixture; DEMO shows the blocked path.
  - Report generation is synchronous (size-guarded); background generation is deferred to Phase 12. The PDF is text-only.
  - Cross-module automated checks (duplicate farm, overlaps, double counting) are not part of readiness.
- Phase 8B:
  - Verification only: validation, registry submission, issuance, credits, serials, buffer and allocation are not implemented; a
    recorded VERIFIED decision is not an issuance. No accreditation is modelled (C4).
  - Without a registered calculation module no period reaches READY outside tests, so submission, findings and decisions are exercised
    only with the TEST-only fixture; DEMO shows assignment and COI only.
  - Findings belong to one submission; a superseded package's findings remain as history (I5).
  - Each E2E run adds a VVB assignment to its DEMO project (and reuses Niphad's open assignment) in the development database.
- Phase 9A:
  - No real registry API is integrated (no contract): every registry interaction is manual and evidence-backed. API-mode paths are
    exercised only with the TEST-only adapter.
  - No registry-specific serial parser exists in the application, so serial ranges are checked for exact duplicates only (length / overlap
    checks need a registry parser).
  - The registry document checklist and the unit equivalence are configuration per registry account; none is invented.
  - The UI records one serial range per batch (the API accepts several); issuance correction is available through the API only.
  - Inventory, ownership, reservation, transfer and retirement are Phase 9B; marketplace Phase 10; payouts Phase 11.
- Phase 9B:
  - Buyer KYC / onboarding is Phase 10: buyers can already receive, hold and request retirement of credits (X2) — a compliance dependency.
  - No registry API and no registry-specific serial parser exist in the application: REGISTRY transfers and retirements are recorded
    manually with evidence; sub-ranges exist only when registry-stated or parser-derived (TEST fixture), otherwise positions hold a
    quantity within the 9A range.
  - A confirmer must hold credits.confirm in the custodian organization (the holding registry account's organization); a credit-holding
    organization without such a user cannot complete transfers or retirements of its credits.
  - Reservation expiry is lazy (on reads and writes) plus a manual sweep endpoint; there is no background worker (Phase 12).
  - Reconciliation is manual (registry statement + stated quantities); scheduled sync needs a registry API.
  - Multi-period isolation is enforced and tested at batch level (each batch belongs to one period; positions never merge across batches).
  - The UI has no reconciliation screen (API only) and records at most one registry-stated retired serial range per retirement (the API
    accepts several).
  - DEMO has no registry-issued batch, so every ledger workflow is exercised only in the rolled-back TEST database.
- Phase 10:
  - No payment provider is contracted: LIVE payments are manual (evidence + seller-finance confirmation); provider paths (outbox, events,
    reconciliation, provider refunds) are exercised only with the TEST adapter. There is no public webhook route.
  - Buyer KYC is document-driven: no legal document list is configured or invented; the platform reviewer decides.
  - Tax / invoice rules are undefined: only a deterministic ORDER_CONFIRMATION (not a tax invoice) exists; no invoice table, no INV sequence.
  - Refunds are whole-payment only (no partial / item-level refunds); a refund after delivery is money only — returning credits is a manual
    9B reversal (INTERNAL, untouched outputs only); a REGISTRY transfer is never reversed.
  - Listing and order expiry are lazy (on read / before writes); scheduled expiry and payment reconciliation jobs are Phase 12.
  - Every DEMO run leaves DEMO-BUYER-D's buyer profile KYC_VERIFIED in the development database (KYC demonstration); no listing, order or
    payment is created.
- Phase 11:
  - Payee organization (D16 / D38): a settlement includes only revenue whose seller is the project organization; revenue sold by
    another holder is not distributed until an inter-organization policy is decided.
  - Payees (D22): only farmers are payees.
  - Recovery (D29): recovery cases are resolved manually; there is no automatic netting or clawback.
  - Tax / withholding (D31): none is calculated.
  - Rounding (D27): chosen per approved version, with no platform default.
  - No payout provider is contracted: payouts are manual with evidence, and provider paths are exercised only with the TEST adapter.
    Chargebacks are out of scope (D11).
  - A revenue-share version must cover the whole monitoring period; mid-period agreement changes need a business decision.
  - DEMO has no revenue, so every financial workflow is exercised only in the rolled-back TEST database. DEMO shows the DEMO note and
    empty / configuration-required states.
  - No scheduled reconciliation or payout job exists (Phase 12).
- Phase 12A:
  - This development machine has no Docker / WSL / Redis. The API, unit tests and E2E run without a broker (jobs stay QUEUED). The
    real-worker test uses the test-only `fakeredis` TCP server unless `REDIS_TEST_URL` points at a real Redis.
  - Windows workers use the solo pool, which does not enforce Celery hard time limits (cooperative budgets and SQL leases still bound
    jobs). Production workers are Linux.
  - Orphan files are detected and reported, never deleted (the storage abstraction has no delete).
  - No retention period exists, so the purge job purges nothing and job history is kept.
  - Calculation / report execution, provider polling, notification delivery, the Redis rate limiter, alerting and monitoring are not
    in 12A.
- The browser logs one expected 401 at start-up: the silent session-restore attempt when nobody is signed in.
