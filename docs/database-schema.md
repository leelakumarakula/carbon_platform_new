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

## Phase 2 decisions (D3)

| Table | Notes |
|---|---|
| `consent_definitions` | `consent_type` + `version` unique; title, `text_version`, `required_for_activation`, ACTIVE/RETIRED (one ACTIVE per type, filtered unique index). `farmer_consents.consent_definition_id` references the version granted; grants of an older version become SUPERSEDED |

## Phase 3 tables (§7.4 projects, §7.5 standards/activities)

| Table | Notes |
|---|---|
| `standards` | `code` unique; programme owner, VOLUNTARY/COMPLIANCE/OTHER, official `source_url`, ACTIVE/INACTIVE, `environment` |
| `activities` | `code` unique; category, ACTIVE/INACTIVE, `environment` |
| `standard_activities` | PK (standard, activity): which activities a standard offers (catalog link, not a rule) |
| `projects` | `project_code` (sequence `seq_project_code`, PRJ-YYYY-nnnnnn); organization; type; country/region; start date; status CHECK with all 20 lifecycle states; current `standard_id` / `activity_id`; `methodology_status` CHECK = NOT_SELECTED (Phase 4 widens); `current_boundary_id`; submission and eligibility-review stamps; `environment` |
| `project_farms` | participation: project, farm, farmer, ACTIVE/REMOVED (filtered unique ACTIVE per project+farm), period (CHECK end ≥ start), `farm_boundary_id` + area at add time, conflict acknowledgement + JSON snapshot, added/removed by/at/reason |
| `project_participants` | team: user + project role (CHECK list of system role codes), ACTIVE/REMOVED (filtered unique), dates, notes |
| `project_standards`, `project_activities` | selection history; filtered unique `is_current = 1` per project |
| `project_crediting_periods` | period number (unique per project), start/end (CHECK end > start), PROPOSED/SUPERSEDED/CANCELLED (+ CONFIRMED/ACTIVE/ENDED reserved), `replaces_id` |
| `project_baselines` | versioned baseline metadata (period, description, data sources); filtered unique current |
| `project_carbon_rights` | per participation: holder type/farmer/organization/name, share % (0–100], agreement (→ `farmer_agreements`), document, reference (CHECK at least one), validity, ACTIVE/ENDED/VOID, UNVERIFIED/VERIFIED/REJECTED + reviewer |
| `project_documents` | link to `documents` (categories PROJECT_DESIGN, CARBON_RIGHTS, BASELINE_DATA added) |
| `project_boundaries` | `geography` union of farm boundaries, versioned CURRENT/SUPERSEDED (filtered unique), union area, sum of farm areas, internal overlap, farm boundary IDs used (JSON), validity, other-project overlaps (JSON), GIS review. **Spatial index** `six_project_boundaries_boundary` |
| `project_status_history` | **append-only (trigger)**: from/to status, action, reason, user, time, request ID |

## Phase 4 tables (§7.5 methodologies, §9 selection)

| Table | Notes |
|---|---|
| `methodologies` | `code` unique; one `standard_id`; owner; source URL; ACTIVE/INACTIVE; `environment` |
| `methodology_activities` | PK (methodology, activity): activities covered (each must be offered under the standard) |
| `methodology_versions` | unique (methodology, version number) and (methodology, label); DRAFT/IN_REVIEW/APPROVED/SUPERSEDED/RETIRED/WITHDRAWN; effective dates (CHECK); source name/URL/document; rule-set revision counters; `calculation_readiness` NOT_PRODUCTION_READY/PRODUCTION_READY; `is_demo_illustrative`; based-on / superseded-by self references; submitted/approved stamps |
| `methodology_applicability_rules` | per version, unique rule code; category, fact key, operator (CHECK lists), `expected_value` JSON (`{"value": …}`, ISJSON), on_fail, evidence requirement, mandatory |
| `methodology_monitoring_rules` | parameter, unit, frequency, method, evidence; `measurement_source` NOT NULL, CHECK FIELD / FIELD_ACTIVITY / LABORATORY / UNCLASSIFIED (0008, decision V2-A) |
| `methodology_calculation_rules` | step CHECK, equation reference, parameter names, `implementation_status` NOT_IMPLEMENTED/NOT_PRODUCTION_READY/VERIFIED (documentation only) |
| `methodology_rules` | rule type CHECK (crediting period, baseline, additionality, leakage, uncertainty, sampling, permanence, general), `parameters` JSON |
| `methodology_documents` | link to `documents` (category METHODOLOGY_DOCUMENT), optional version |
| `methodology_change_history` | **append-only (trigger)** |
| `methodology_evaluations` | **append-only (trigger)**: project, standard, activity, engine version, facts JSON snapshot, evaluator, request ID |
| `methodology_evaluation_results` | **append-only (trigger)**: one row per candidate version; outcome CHECK; rule results JSON; rules revision |
| `project_methodology_reviews` | specialist recommendation per candidate result |
| `project_methodologies` | LOCKED/UNLOCKED (filtered unique: one LOCKED per project); version, evaluation result, review, rule revisions, confirmation and unlock stamps |
| `projects` (changed) | `methodology_id`, `methodology_version_id`; `methodology_status` CHECK widened to NOT_SELECTED/UNDER_REVIEW/CONFIRMED |

## Phase 5 tables (§7.6 MRV, §11 sampling)

| Table | Notes |
|---|---|
| `mrv_plans` | unique (project, plan_version); DRAFT/SUBMITTED/APPROVED/SUPERSEDED/WITHDRAWN (filtered unique: one APPROVED per project); `project_methodology_id`, methodology + version; frequency, window (CHECK); `quantification_approach` CHECK (MEASURE_AND_REMEASURE / MEASURE_AND_MODEL / OTHER / CONFIGURATION_REQUIRED); `configuration_status`, `configuration_gaps` JSON, `gaps_acknowledged_by`; `supersedes_id`; submitted/approved stamps |
| `mrv_plan_measurements` | configurable measurement definitions: code (unique per plan), category / value type / level CHECK lists, unit, `allowed_values` JSON, required, source METHODOLOGY / PROJECT_CONFIGURED, `monitoring_rule_id` |
| `monitoring_periods` | unique (project, period_number); plan, methodology version; purpose; dates (CHECK); 9 statuses |
| `project_strata` | versioned (`record_id`, `version`, filtered unique `is_current`); code, criteria JSON, `geometry` geography (spatial index `six_project_strata_geometry`), `area_hectares` (SQL Server), DRAFT/APPROVED/SUPERSEDED/RETIRED |
| `stratum_farms` | PK (stratum, farm) + the farm boundary used |
| `stratum_characteristics` | characteristic CHECK list, value, source |
| `sampling_designs` | per period, unique (period, code); methodology version |
| `sampling_design_versions` | DRAFT/APPROVED/SUPERSEDED (one APPROVED per design); statistical design CHECK; precision, confidence, CV, MDD, method, depth (CHECK), min distance, repeat sampling, **random seed**, requirement source, configuration status/gaps, `points_generated_at` |
| `sampling_design_versions` (0007) | `field_rules` JSON: GPS tolerance, duplicate threshold, checklist version + items, minimum photos, each with source PLATFORM_DEFAULT / METHODOLOGY (frozen at creation) |
| `field_collection_records` (0007) | `field_rules` JSON (copied from the design version at start), `checklist_version`, `gps_tolerance_m` |
| `sampling_design_strata` | per version and stratum: `sample_count` (configured), allocation basis |
| `sampling_points` | `point_code` (`seq_sampling_point_code`, SP-), `location` geography (spatial index `six_sampling_points_location`), lat/lon, planned depth, PLANNED/ASSIGNED/COLLECTED/SKIPPED/CANCELLED, farm + farm boundary, collector, planned date |
| `sampling_point_relocations` | old/new coordinates, SQL Server distance, reason, PENDING/APPROVED/REJECTED, requester / reviewer stamps |
| `sampling_assignments` | ACTIVE/REASSIGNED/COMPLETED/CANCELLED (filtered unique: one ACTIVE per point) |
| `field_collection_records` | `collection_code` (`seq_field_collection_code`, FIELD-), version + `supersedes_id`; IN_PROGRESS/SUBMITTED/ACCEPTED/RETURNED/SUPERSEDED; GPS geography (spatial index `six_field_collection_records_gps`), accuracy, SQL Server `distance_from_point_m`, `gps_inside_farm`, deviation note; actual depth; quantity; checklist JSON; review stamps |
| `monitoring_records` | versioned (`record_id`, `version`, `is_current`); measurement, level entity, phase, typed value columns, unit, source, RECORDED/SUPERSEDED/RETRACTED, change reason |
| `mrv_evidence` | entity type/id, evidence type CHECK, `document_id`, `checksum_sha256`, lat/lon, source, status |
| `mrv_datasets` | `dataset_code` unique, version + `supersedes_id`; 7 statuses (filtered unique: one open per period); `snapshot` JSON + `snapshot_sha256`; configuration gaps; `environment` |
| `mrv_qa_reviews` | checks JSON, result PASS/FAIL/REQUIRES_CORRECTION, start/complete stamps |

## Phase 6 tables (§7.7 samples / laboratory) — migration 0009

| Table | Key columns / rules |
|---|---|
| `project_laboratory_engagements` | project, laboratory organization, locked methodology version; PROPOSED/ACTIVE/ENDED; `replaces_engagement_id`; proposed / accepted / ended stamps, `ended_side` PROJECT/LABORATORY, `end_reason` (required when ENDED); CHECK proposer ≠ accepter; filtered unique: one ACTIVE and one PROPOSED per project + laboratory; `environment` |
| `project_laboratory_engagement_rules` | engagement × methodology monitoring rule (composite PK) — the engagement scope (LABORATORY rules only) |
| `lab_samples` | `sample_code` unique (`seq_sample_code`, SMP-); `root_sample_id` (NOT NULL, self-FK) and `parent_sample_id` (splits); `field_collection_id` (never re-pointed), point, period, farm, project, methodology version, engagement, laboratory; 12 custody states; description, depth top/bottom, quantity + unit, container label, seal, accession number; registered / sealed stamps; `environment` |
| `sample_custody_events` | append-only (`trg_sample_custody_events_append_only`); unique (sample, `sequence_no`); event type, from/to state, actor user / organization / role / side, occurred / recorded at, location, lat/lon, seal, shipment, exception type (required for EXCEPTION_RECORDED), reason (required for REJECTED / EXCEPTION / VOIDED), document |
| `lab_shipments` | `shipment_code` unique (`seq_shipment_code`, SHP-); DRAFT/DISPATCHED/RECEIVED/CANCELLED; carrier, tracking; created / dispatched / received stamps; cancel reason |
| `lab_shipment_items` | unique (shipment, sample); filtered unique: one open (IN_SHIPMENT) item per sample; receipt condition, observed seal, reason, received by / at |
| `lab_tests` | `test_code` unique (`seq_lab_test_code`, LT-); sample, root sample, project, laboratory, engagement, methodology version, rule, MRV plan measurement; REQUESTED/IN_PROGRESS/RESULT_SUBMITTED/CLOSED/CANCELLED; `retest_of_test_id`, retest reason / requester; filtered unique (sample, rule) for non-retest, non-cancelled tests |
| `lab_results` | test + `version`, supersedes / superseded-by; sample, root sample, project, laboratory, methodology version, rule, plan measurement; `result_type` NUMERIC/TEXT with CHECK exactly one of `value_number` / `value_text`; unit (verbatim); analysed at, analyst, method, `report_document_id`; `source` MANUAL/LIMS_IMPORT (+ `external_result_id`, unique per laboratory); 8 statuses; filtered unique: one APPROVED per root sample + rule; trigger `trg_lab_results_approved_immutable` (an APPROVED row changes only to SUPERSEDED, and is never deleted) |
| `lab_result_qa_reviews` | append-only (`trg_lab_result_qa_reviews_append_only`); reviewer, decision, checks JSON (`ISJSON`), notes, configuration acknowledgement |

0009 also widens `documents.category` with `LAB_REPORT` and `CUSTODY_DOCUMENT` (PDF only, enforced by the document service);
its downgrade refuses to run while documents of those categories exist. No Phase 5 table changes.

## Phase 7 tables (§7.10 calculations) — migration 0010

| Table | Key columns / rules |
|---|---|
| `calculation_runs` | `run_code` unique (`seq_calculation_run_code`, CALC-); project, reporting `monitoring_period_id`, optional `crediting_period_id`, `mrv_dataset_id` (bound at freeze); methodology, version, `project_methodology_id`, frozen `calculation_rules_version` / `monitoring_rules_version`; `module_code`, `module_version`, `module_readiness`, `engine_version`; `input_snapshot` (canonical JSON) + `input_sha256`; `output_sha256`; `net_result` (exact decimal text) + `net_unit`; `blockers` JSON; 9 statuses; `recalculation_of_run_id` + reason; `superseded_by_run_id` / `superseded_at`; created / frozen / executed / submitted / approved / closed by and at; `environment`. Filtered unique: one open run (DRAFT … QA_REVIEW) and one APPROVED run per reporting period. Trigger `trg_calculation_runs_immutable` |
| `calculation_inputs` | append-only; unique (run, seq); variable; `source_type` (LAB_RESULT / MONITORING_RECORD / STRATUM_AREA / SAMPLING_DESIGN_PARAMETER / MODULE_CONSTANT); `source_id` + `source_version` (indexed for reverse lineage); exact value + kind; unit; level; stratum / farm / point / field collection / sample / root sample / monitoring rule / plan measurement; `requirement_source`; `source_reference`; `source_sha256` |
| `calculation_outputs` | append-only; unique (run, seq); step; output code; `calculation_rule_id` (FK to the locked version's rule) + rule code + equation reference; exact value; unit; level + entity; `input_refs` JSON (input and output seq numbers); filtered unique: one `is_final` per run |
| `calculation_qa_reviews` | started / completed by and at, checks JSON (`ISJSON`), result PASS / FAIL, notes; a completed review is immutable (trigger) |

No earlier table changes (the project statuses CALCULATION_READY / CALCULATED already existed in the status check).

## Phase 8A tables (internal pre-verification) — migration 0011

| Table | Key columns / rules |
|---|---|
| `calculation_findings` | `finding_code` (CFND-); project, period, run; category (6 specification values); `blocking`; title, description; optional targets (input seq, output seq, calculation rule, source type + id, evidence document); status OPEN / RESPONDED / RESOLVED / WITHDRAWN; raised / responded / resolved / withdrawn stamps, response, resolution note, `resolved_by_run_id`, withdraw reason; environment. Trigger: identity, target and original text immutable; WITHDRAWN final; no delete |
| `calculation_finding_events` | append-only; unique (finding, seq); action, from / to status, actor, time, note, document, run |
| `calculation_reports` | `report_code` (CRPT-); run, project, period; version (unique per run); `generator_version`; canonical JSON `content` + `content_sha256`; `document_id` (CALCULATION_REPORT PDF) + `pdf_sha256`; CURRENT / SUPERSEDED (filtered unique: one CURRENT per run); superseded by / at. Trigger: immutable except CURRENT → SUPERSEDED |
| `calculation_readiness_reviews` | `readiness_code` (RDY-); project, period, run, report; DRAFT / SUBMITTED / READY / REJECTED / WITHDRAWN / INVALIDATED (filtered unique: one open and one READY per period); checks JSON; `manifest` + `manifest_sha256` (required when READY); created / submitted / decided / withdrawn / invalidated stamps. Trigger: identity fixed, decided reviews frozen, READY → INVALIDATED only |

0011 also adds the documents category `CALCULATION_REPORT` (PDF only); its downgrade refuses to run while any Phase 8A row or report
document exists.

## Phase 8B tables (VVB / ACVA verification) — migration 0012

| Table | Key columns / rules |
|---|---|
| `verification_assignments` | `assignment_code` (VAS-); project, monitoring period, VVB organization; PROPOSED / ACCEPTED / COMPLETED / DECLINED / WITHDRAWN / TERMINATED (filtered unique: one PROPOSED/ACCEPTED per period); `previous_assignment_id` (replacement lineage); proposed / accepted stamps; COI declaration + declared by / at (required once ACCEPTED); completed at; closed by / at / side / reason (required when declined, withdrawn or terminated). Trigger: identity and COI fixed; closed assignments final; no delete |
| `verification_submissions` | `submission_code` (VSUB-); assignment + seq (unique); project, period; Phase 8A readiness review, calculation run, calculation report, `manifest_sha256`; SUBMITTED / SUPERSEDED / INVALIDATED (filtered unique: one SUBMITTED per assignment); closed at / reason, superseded by. Trigger: the package references never change; closed submissions final |
| `verification_findings` | `finding_code` (VFND-); assignment, submission; category (6 specification values); `blocking`; title, description; `target_type` (SUBMISSION, MONITORING_PERIOD, CALCULATION_RUN, INPUT, OUTPUT, LAB_RESULT, MRV_EVIDENCE, DATASET, CALCULATION_REPORT, METHODOLOGY, DOCUMENT) + `target_ref`; OPEN / RESPONDED / CLOSED; raised / responded / closed stamps, response (+ document), closure note. Trigger: identity, category, target and original text immutable; no delete |
| `verification_finding_events` | append-only; unique (finding, seq); action, from / to status, actor, actor organization, actor side, time, note, document |
| `corrective_actions` | `action_code` (CAR-); finding, submission, assignment; description, `due_date` (overdue derived); REQUESTED / RESPONDED / ACCEPTED / CANCELLED; requested / responded / reviewed stamps, response (+ document), review note. Trigger: request immutable; ACCEPTED / CANCELLED final |
| `corrective_action_events` | append-only; same shape as finding events |
| `verification_decisions` | `decision_code` (VDEC-); assignment, submission (unique), project, period, VVB organization; outcome VERIFIED / NOT_VERIFIED; `verified_quantity` + `verified_quantity_unit` ("VVB-stated verified quantity", both or neither — never a credit); rationale; `report_document_id` (VERIFICATION_REPORT PDF) + `report_sha256`; `manifest_sha256`; decided by / at; CURRENT / SUPERSEDED (filtered unique: one CURRENT per period) + superseded at / reason. Trigger: immutable except CURRENT → SUPERSEDED |

0012 also adds the documents categories `VERIFICATION_REPORT` and `VERIFICATION_EVIDENCE` (PDF only) and the sequences VAS / VSUB / VFND /
CAR / VDEC; its downgrade refuses to run while any Phase 8B row or verification document exists. No earlier table changes (the project
statuses VERIFICATION / VERIFIED already existed in the status check).

## Phase 9A tables (registry submission & credit issuance) — migration 0013

| Table | Key columns / rules |
|---|---|
| `registry_accounts` | owner organization (project developer); registry organization (org_type REGISTRY, counterparty); `external_account_id` (unique per registry); label; `adapter_code` (MANUAL); explicit unit equivalence `credit_unit` + `verified_unit_equivalent` (both or neither, D5); `document_checklist` JSON (D16); ACTIVE / CLOSED. Trigger: identity fixed; CLOSED final |
| `registry_project_registrations` | `registration_code` (RREG-); project, account, registry; PENDING / REGISTERED / REJECTED; `external_project_id` (unique per registry), registry-stated `registered_on`, evidence document (required when REGISTERED / REJECTED), recorded by / at; filtered unique: one PENDING / REGISTERED per project and registry. Trigger: identity fixed; recorded answers final |
| `registry_submissions` | `submission_code` (RSUB-); project, period, registration, account, registry, VVB decision, verification submission, previous submission; DRAFT / FROZEN / SUBMITTING / SUBMISSION_UNCONFIRMED / SUBMITTED / ACCEPTED / REJECTED / WITHDRAWN / CANCELLED / INVALIDATED (filtered unique: one open / accepted per monitoring period across registries); `snapshot` (registry-submission-v1 JSON) + `snapshot_sha256` + `idempotency_key` (required once frozen); `external_submission_id` (unique per registry); response document or payload hash; reasons. Trigger: identity, snapshot, hash, key and external reference fixed once set; final states frozen |
| `registry_events` | append-only: account, registration / submission / issuance; event type (SUBMIT_ATTEMPT, SUBMIT_CONFIRMED, TIMEOUT, STATUS_QUERIED, QUERY_RECEIVED, RESPONSE_RECORDED, ERROR, RECONCILED, MISMATCH, SOURCE_SUPERSEDED, DOCUMENT_ATTACHED, EXTERNAL_REFERENCE_RECORDED); actor; adapter; idempotency key; external reference; payload SHA-256 (no raw payload); outcome; checklist item; note; document |
| `credit_issuances` | `issuance_code` (ISS-); registry submission, project, period, account, registry, VVB decision; registry-stated `external_issuance_id` (unique per registry among CONFIRMED), date, whole `quantity` (Numeric(28,0) > 0), unit; source MANUAL / API; ISSUANCE_STATEMENT document or API response hash; RECORDED / CONFIRMED / VOIDED / CORRECTED / CANCELLED; recorded / confirmed (check: confirmer ≠ recorder) / voided / cancelled stamps; `corrects_issuance_id` / `corrected_by_issuance_id`. Trigger: recorded data immutable; CONFIRMED → CORRECTED / CANCELLED only; final states frozen |
| `credit_batches` | `batch_code` (CB-); issuance; project, period, registry, account, VVB decision, methodology version, standard; registry-stated `vintage`; whole quantity; unit; RECORDED / ISSUED / VOIDED / SUPERSEDED / CANCELLED. Trigger: only status changes, along the lifecycle |
| `credit_serial_ranges` | batch; registry; `serial_start` / `serial_end` verbatim (both or neither); quantity; optional parsed series / bounds (registry-specific parser only); `is_current` (ISSUED / CANCELLED batches); filtered unique: registry + serial start and registry + serial end among current ranges. Trigger: serials never change |

0013 also adds the documents categories `REGISTRY_SUBMISSION`, `REGISTRY_RESPONSE`, `ISSUANCE_STATEMENT` (PDF only) and the sequences RREG /
RSUB / ISS / CB; its downgrade refuses to run while any Phase 9A row or registry document exists. No earlier table changes (the project
status ISSUED already existed in the status check).

## Phase 9B tables (credit ledger) — migration 0014

Workflow details: [credit-ledger-workflow.md](credit-ledger-workflow.md).

| Table | Key columns / rules |
|---|---|
| `credit_ledger_entries` | `entry_code` (LEDG-); `entry_type` (OPEN_INVENTORY, RESERVE, RESERVATION_RELEASE, RESERVATION_EXPIRE, TRANSFER_REQUEST, TRANSFER_COMPLETE, TRANSFER_CANCEL, RETIREMENT_REQUEST, RETIRE, RETIREMENT_CANCEL, REVERSAL, ISSUANCE_ADJUSTMENT); batch; organization and counterparty organization; links to the opening / reservation / transfer / retirement / reversal / issuance; whole quantity; actor; `confirmed_by` (check ≠ actor); reason; `request_key` (filtered unique); `posted`. Trigger `trg_credit_ledger_entries_guard`: append-only, posted once, and on posting conservation per type (OPEN_INVENTORY outputs = issued quantity of an ISSUED batch; ISSUANCE_ADJUSTMENT leaves no open quantity; otherwise inputs = outputs > 0 and open = issued) plus no overlap of parsed sub-ranges |
| `credit_positions` | immutable UTXO: batch; 9A `serial_range_id`; owner organization; holding registry account (or registry-stated external account id); state AVAILABLE / RESERVED / TRANSFER_PENDING / RETIREMENT_PENDING / RETIRED; status OPEN / CONSUMED; whole quantity; optional registry-stated / parsed sub-range (`parsed_bounds` check: end − start + 1 = quantity); reservation / transfer / retirement links; `created_by_entry_id`, `consumed_by_entry_id` (check: consumed ⇔ link). Trigger `trg_credit_positions_guard`: insert only into an unposted entry, consume once, never update otherwise, never delete; RETIRED never consumed |
| `credit_openings` | `opening_code` (OPN-); batch; owner (holding account organization); REQUESTED / CONFIRMED / CANCELLED (filtered unique: one REQUESTED / CONFIRMED per batch); requester / confirmer (check ≠); entry. Final states immutable |
| `credit_reservations` | `reservation_code` (RSV-); batch; owner; optional recipient; purpose + generic `purpose_reference`; whole quantity; `expires_at`; ACTIVE / CONSUMED / RELEASED / EXPIRED. Final states immutable |
| `credit_transfers` | `transfer_code` (TRF-); kind INTERNAL / REGISTRY; batch; sender / recipient (check distinct); recipient registry account id (REGISTRY); quantity; optional reservation; REQUESTED / COMPLETED / CANCELLED / REJECTED; requester / completer (check ≠); `registry_transfer_reference` (filtered unique per registry) + REGISTRY_TRANSFER_EVIDENCE document (check: required for a COMPLETED REGISTRY transfer). No price, payment or order column. Final states immutable |
| `credit_retirements` | `retirement_code` (RET-); batch; owner; quantity; beneficiary; reason; REQUESTED / RETIRED / REJECTED / CANCELLED; requester / retirer (check ≠); `registry_retirement_reference` (filtered unique per registry), registry-stated `retirement_date`, RETIREMENT_CERTIFICATE document (check: all required when RETIRED); `retired_serials` JSON (registry-stated). Final states immutable |
| `credit_reversals` | `reversal_code` (REV-); reversed entry (filtered unique: one open per entry); reason; REQUESTED / APPLIED / REJECTED; requester / decider (check ≠); compensating entry. Final states immutable |

0014 also adds the sequences LEDG / OPN / RSV / TRF / RET / REV and the documents categories `RETIREMENT_CERTIFICATE` and
`REGISTRY_TRANSFER_EVIDENCE` (PDF only). The five entry → workflow foreign keys are created after the tables (cyclic references). Its
downgrade refuses to run while any Phase 9B row or ledger document exists. No earlier table changes.

## Phase 10 tables (marketplace) — migration 0015

Workflow details: [marketplace.md](marketplace.md). No table stores a credit quantity that could act as a balance: order items reference the
Phase 9B batch / serial range / reservation / transfer only (D24). Money is `Numeric(19,4)` with an ISO-4217 currency; carbon is whole credits.

| Table | Key columns / rules |
|---|---|
| `buyer_profiles` | one per BUYER organization; DRAFT / KYC_SUBMITTED / KYC_VERIFIED / KYC_RETURNED / SUSPENDED; legal name, registration number, country, contact; optional identifier stored as type + last 4 + keyed fingerprint (never in clear); submitted / verified by and at (check verifier ≠ submitter); return / suspension reasons. Trigger: organization, creator, environment fixed; never deleted |
| `buyer_kyc_reviews` | append-only (trigger): SUBMITTED / VERIFIED / RETURNED / SUSPENDED / REINSTATED, actor, note, the reviewed document ids |
| `marketplace_listings` | `listing_code` (LST-); seller organization; ONE 9B batch (+ optional serial range); title; immutable cap `listed_quantity`; `unit_price` + `currency`; min / max order; `payment_window_hours`; `valid_until`; seller co-benefit text; allow-listed `disclosure` JSON + SHA-256; DRAFT / PENDING_APPROVAL / ACTIVE / PAUSED / CLOSED / EXPIRED / CANCELLED; approver ≠ creator (check); filtered unique: one ACTIVE / PAUSED listing per seller + batch + range. Trigger: identity fixed; price, quantity, terms and disclosure frozen once approved; final states frozen; never deleted |
| `listing_documents` | append-only links of seller-published LISTING_DOCUMENT PDFs |
| `orders` | `order_code` (ORD-); buyer and seller organizations (check distinct); currency; subtotal = total (no fee, no tax); transfer kind INTERNAL / REGISTRY (+ the buyer's registry account); `expires_at` (payment deadline = the item reservations' expiry); status (D11); attention / close reasons. Trigger: parties, currency, amounts, kind and deadline fixed; COMPLETED / CANCELLED / EXPIRED / REFUNDED final |
| `order_items` | `item_code`; order; listing; batch; optional serial range; quantity; `unit_price`; `line_total` (check = price × quantity); the current 9B `reservation_id` and `transfer_id` (filtered unique); RESERVED / TRANSFER_PENDING / DELIVERED / FAILED / RELEASED / EXPIRED. Trigger: price and quantity immutable; DELIVERED / RELEASED / EXPIRED final |
| `payments` | `payment_code` (PAY-); order; payee (seller) / payer organizations; adapter (MANUAL at runtime); amount + currency; status; external reference (unique per adapter); PAYMENT_EVIDENCE document; recorded / confirmed (check ≠) / rejected; filtered unique: one open payment per order. Trigger: order, parties, adapter and amount fixed; REJECTED / FAILED / REFUNDED final |
| `payment_events` | append-only (trigger); provider; external event id (unique per provider); event type; payload SHA-256 only; outcome APPLIED / UNMATCHED / IGNORED |
| `refunds` | `refund_code` (RFD-); payment; order; amount (the whole payment); `after_transfer`; reason; REQUESTED / APPROVED / COMPLETED / REJECTED; requested / approved (check ≠) / completed (reference + evidence required); filtered unique: one open / completed refund per payment. Trigger: payment and amount fixed; COMPLETED / REJECTED final |

Every Phase 10 table carries a filtered unique `request_key` and an `action_key` (the Idempotency-Key of the last state change, for
replays). 0015 adds the sequences LST / ORD / PAY / RFD and the documents categories BUYER_KYC_DOCUMENT (restricted), PAYMENT_EVIDENCE,
REFUND_EVIDENCE, ORDER_CONFIRMATION, LISTING_DOCUMENT (PDF only). No invoice table and no INV sequence (tax / invoice rules undefined — D10).
Its downgrade refuses to run while any Phase 10 row or marketplace document exists. No earlier table changes.

## Phase 11 tables (revenue, sharing, settlement, payouts) — migration 0016

Money is `Numeric(19,4)` with an ISO-4217 currency; percentages are `Numeric(9,6)`. No table stores a default percentage, fee or tax.

| Table | Key columns / rules |
|---|---|
| `revenue_records` | `revenue_code` (RVN-).<br>Kind RECOGNITION (> 0) / REVERSAL (< 0, with `reverses_revenue_id` and `refund_id`).<br>Lineage: order item, order, payment, 9B transfer, batch, project, monitoring period, seller organization.<br>Filtered unique: one recognition per order item; one reversal per recognition.<br>Append-only (trigger). |
| `revenue_share_versions` | `version_code` (RSH-), project, `version_no`.<br>`farmer_share_pct` (0 < x ≤ 100), `deduct_approved_costs`, `rounding_mode` (HALF_UP / HALF_EVEN / DOWN), effective from / to, `source_reference`.<br>DRAFT / IN_REVIEW / APPROVED / SUPERSEDED; approver ≠ creator (check).<br>Trigger: identity fixed; values frozen once submitted; APPROVED only becomes SUPERSEDED; never deleted. |
| `farm_allocation_versions` / `farm_allocation_lines` | Version (FAL-) per project and monitoring period, with `basis_reference` and the same workflow and triggers.<br>Lines: append-only; one per project farm (unique), with farm, farmer and `share_pct` (Σ = 100 enforced on submit). |
| `project_costs` | `cost_code` (PCS-); project; optional period; category; description; amount ≠ 0 (a negative amount corrects an approved cost via `corrects_cost_id`); currency; incurred on; reference.<br>PENDING_APPROVAL / APPROVED / REJECTED; approver ≠ creator.<br>Trigger: fixed; APPROVED / REJECTED final. |
| `settlement_runs` | `run_code` (SET-); project, organization, period, currency, revenue-share version, allocation version; `calculation_version`.<br>Figures: gross, deducted costs, distributable, farmer total, developer residual.<br>`input_snapshot` (canonical JSON) + `input_sha256`.<br>DRAFT / CALCULATED / PENDING_APPROVAL / APPROVED / COMPLETED / REJECTED / CANCELLED; approver ≠ calculator (check).<br>Trigger: figures and snapshot frozen once calculated; APPROVED only becomes COMPLETED; final states frozen. |
| `settlement_revenue_items` / `settlement_cost_items` | The run's claims on revenue records / costs, with amount and `active`.<br>Filtered unique on `active = 1`: a record is settled at most once.<br>Trigger: only `active` 1 → 0 (on reject / cancel). |
| `farmer_entitlements` | Append-only: one row per run and allocation line, with project farm, farm, farmer, share %, rounded amount. |
| `payouts` | `payout_code` (PYT-); run; payer organization; farmer; amount > 0 (Σ the farmer's entitlements); status (D20); adapter (MANUAL); `bank_account_id` (FK to the Phase 2 VERIFIED account) + `bank_last4` only; external reference (unique per adapter); evidence; `replaces_payout_id`.<br>Checks: approver ≠ calculator; executor ≠ approver; bank account required from APPROVED; reference + executor when PAID.<br>Filtered unique: one open payout per run and farmer.<br>Trigger: identity and amount fixed; execution frozen once PAID (then only RECONCILED); final states frozen. |
| `payout_transactions` | Append-only: INITIATED / PAID / FAILED / UNCONFIRMED / STATUS_QUERIED, with adapter, reference, amount, evidence, actor. |
| `payout_reconciliations` | Append-only: MATCHED / EXCEPTION, statement reference / amount / currency / date, RECONCILIATION_EVIDENCE, note, reconciler. |
| `payout_adjustments` | Recovery case (ADJ-): reversal (unique), original run, amount, OPEN / CLOSED with resolution.<br>Trigger: fixed; CLOSED final. |

Every configuration, cost, run and payout row carries a filtered unique `request_key` and an `action_key`. 0016 adds the RVN / RSH /
FAL / PCS / SET / PYT / ADJ sequences and the COST_EVIDENCE, PAYOUT_EVIDENCE and RECONCILIATION_EVIDENCE document categories (PDF
only). Its downgrade refuses to run while any Phase 11 row or financial document exists. No earlier table changes.

## Migrations

`backend/alembic/versions/20261002_0001_phase1_identity_access_audit.py` and
`20261002_0002_phase2_farmer_farm.py` (tables, sequences, spatial index, `document_versions` trigger),
`20261002_0003_phase2_decisions_consent_definitions.py` (D3, with data backfill) and `20261002_0004_phase3_projects.py`
(project tables, `seq_project_code`, project spatial index, `project_status_history` trigger, document categories) and
`20261002_0005_phase4_methodologies.py` (methodology tables, three append-only triggers, project columns and checks) and
`20261002_0006_phase5_mrv_sampling.py` (17 MRV/sampling tables, three spatial indexes, the SP- and FIELD- sequences) and
`20261003_0007_phase5_field_rules_governance.py` (decisions S1/S2: `field_rules` JSON on design versions and field records,
`checklist_version` and `gps_tolerance_m` on field records; existing rows backfilled with the defaults in force then) and
`20261003_0008_methodology_measurement_source.py` (decision V2-A: `methodology_monitoring_rules.measurement_source`; DEMO rule DM1 →
LABORATORY, other existing rows → UNCLASSIFIED; one methodology change-history entry per backfilled row) and
`20261003_0009_phase6_laboratory.py` (9 laboratory tables, the SMP- / SHP- / LT- sequences, three triggers, document categories) and
`20261003_0010_phase7_carbon_calculation.py` (4 calculation tables, the CALC- sequence, four triggers; downgrade refused while runs exist) and
`20261003_0011_phase8a_internal_pre_verification.py` (findings, finding events, reports, readiness reviews, CFND / CRPT / RDY sequences,
CALCULATION_REPORT category, four triggers; downgrade refused while Phase 8A rows exist) and
`20261003_0012_phase8b_vvb_verification.py` (7 verification tables, VAS / VSUB / VFND / CAR / VDEC sequences, VERIFICATION_REPORT /
VERIFICATION_EVIDENCE categories, seven triggers; downgrade refused while Phase 8B rows exist) and
`20261003_0013_phase9a_registry_credit_issuance.py` (7 registry / credit tables, RREG / RSUB / ISS / CB sequences, three registry document
categories, seven triggers; downgrade refused while Phase 9A rows exist) and
`20261003_0014_phase9b_credit_ledger.py` (7 ledger tables, LEDG / OPN / RSV / TRF / RET / REV sequences, two ledger document categories,
seven triggers; downgrade refused while Phase 9B rows exist) and
`20261003_0015_phase10_marketplace.py` (9 marketplace tables, LST / ORD / PAY / RFD sequences, five marketplace document categories, nine
triggers; downgrade refused while Phase 10 rows exist) and
`20261003_0016_phase11_financials.py` (13 finance tables, RVN / RSH / FAL / PCS / SET / PYT / ADJ sequences, three financial document
categories, thirteen triggers; downgrade refused while Phase 11 rows exist). Spatial
indexes (`six_*`) are hand-written SQL and excluded from autogenerate by `include_object` in `alembic/env.py`. Generate new revisions with
`alembic revision --autogenerate`, review them, and add raw SQL (triggers, spatial indexes) by hand.
`alembic check` must report no drift before a phase is closed.
