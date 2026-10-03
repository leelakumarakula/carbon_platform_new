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
| 8B | VVB / ACVA | Next (awaiting approval) |
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
- The browser logs one expected 401 at start-up: the silent session-restore attempt when nobody is signed in.
