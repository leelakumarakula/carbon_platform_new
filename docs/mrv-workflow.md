# MRV workflow (Phase 5)

MRV covers the monitoring plan, monitoring periods, monitoring (activity) data, evidence, versioned MRV datasets and
QA. It starts once a project's methodology version is **locked** (Phase 4). It ends at an **APPROVED** dataset.

The following are later phases, and nothing here produces them:
- laboratory results;
- carbon calculations;
- verification;
- credits.

Stratification, sampling design, sampling points and field collection are described in
[sampling-workflow.md](sampling-workflow.md).

## Preconditions (enforced on every MRV write)

`mrv_access.locked_methodology()` refuses MRV work unless all of these hold:

| Condition | Error code |
|---|---|
| The project has a LOCKED `project_methodologies` row and `methodology_status = CONFIRMED`. | `METHODOLOGY_NOT_LOCKED` |
| The locked version is APPROVED or SUPERSEDED. A version that was superseded after locking stays valid for the project. | `METHODOLOGY_VERSION_INVALID` |
| The project is in METHODOLOGY_CONFIRMED, MRV_PLANNED or MONITORING. | `PROJECT_NOT_IN_MRV` |

The methodology cannot be unlocked once the project is MRV_PLANNED or later (Phase 4 unlock requires
METHODOLOGY_CONFIRMED).

## Methodology requirements: CONFIGURATION_REQUIRED

`services/mrv_requirements.py` reads the locked version's rules. Nothing else is used: no sampling rule is ever
invented.

- **Monitoring rules** (Phase 4 `methodology_monitoring_rules`): each becomes a plan measurement with
  source = `METHODOLOGY`.
- **General rules of type `SAMPLING`**: their `parameters` may configure the following keys:
  - `quantification_approach`;
  - `depth_top_cm`, `depth_bottom_cm`;
  - `min_samples_per_stratum`;
  - `target_precision_pct`, `confidence_level_pct`;
  - `statistical_design`;
  - `stratification_variables`;
  - `repeat_sampling`.

When a key is configured, it is **enforced**. A plan or design that contradicts it gets `METHODOLOGY_REQUIREMENT`.

When the core keys are not configured, the requirement status is **CONFIGURATION_REQUIRED**:
- The core keys are the quantification approach, depth, minimum samples and statistical design.
- If the version has no monitoring rule at all, the status is also CONFIGURATION_REQUIRED.
- The gaps are listed on the plan, the design version and the dataset.
- Values entered by the project are recorded as `PROJECT_CONFIGURED`.
- QA reports the gaps as a WARN check.

The DEMO methodologies configure no SAMPLING rule, so DEMO plans show CONFIGURATION_REQUIRED.

## MRV plan (versioned)

`DRAFT → SUBMITTED → APPROVED → SUPERSEDED`, plus `SUBMITTED → DRAFT` (return) and `DRAFT → WITHDRAWN`.

- **Links:** a plan is linked to the project, the locked `project_methodology`, the methodology and the
  methodology version.
- **Contents:** frequency, monitoring window, quantification approach (MEASURE_AND_REMEASURE / MEASURE_AND_MODEL /
  OTHER; no calculation happens), required evidence and measurement definitions.
- **Measurement definitions** (`mrv_plan_measurements`):
  - code, category and value type (NUMBER / TEXT / DATE / BOOLEAN / CHOICE with allowed values);
  - unit;
  - level (PROJECT / FARM / STRATUM / SAMPLING_POINT);
  - required flag;
  - source (METHODOLOGY or PROJECT_CONFIGURED).
- **One draft at a time:** only one DRAFT or SUBMITTED plan may exist (`PLAN_IN_PROGRESS`).
- **Editing:** only DRAFT plans can be edited (`PLAN_NOT_EDITABLE`). An approved plan is never overwritten.
- **Changes:** a new plan version (`supersedes_id`) replaces the approved one only when it is approved.
- **Submitting** needs at least one measurement, a frequency and both window dates.
- **Approval** needs `mrv.approve` (QA officer). The approver must not be the submitter.
  - **Production (decision V1):** a plan with any CONFIGURATION_REQUIRED gap, or without configured required evidence, is
    **blocked** (`CONFIGURATION_REQUIRED`, `details.policy = PRODUCTION_BLOCK`). Acknowledging the gaps does not help. The plan
    shows `gap_approval_policy = PRODUCTION_BLOCK` and its `approval_blockers`.
  - **DEMO projects and non-production environments:** if the plan is CONFIGURATION_REQUIRED, the approver must set
    `acknowledge_configuration_gaps`. That records
    `gaps_acknowledged_by`; without it the error is `CONFIGURATION_REQUIRED`.
  - The first approval moves the project METHODOLOGY_CONFIRMED → **MRV_PLANNED**.

## Monitoring periods

`DRAFT → PLANNED → ACTIVE → DATA_COLLECTION → SUBMITTED → QA_REVIEW → APPROVED | REJECTED → CLOSED`.

Corrections:
- `SUBMITTED → DATA_COLLECTION`;
- `REJECTED → DATA_COLLECTION`;
- `APPROVED → DATA_COLLECTION`, when a correction dataset version is opened.

Rules:
- **Creating** a period requires an APPROVED plan (`MRV_PLAN_NOT_APPROVED`).
  - The dates must lie in the plan window (`OUTSIDE_PLAN_WINDOW`).
  - Periods with the same purpose must not overlap (`PERIOD_OVERLAP`).
- **Period actions** through the API:
  - `plan`;
  - `start` — the first start moves the project MRV_PLANNED → **MONITORING**;
  - `open-collection` — this opens the period's DRAFT dataset (COLLECTING);
  - `close`.
- SUBMITTED, QA_REVIEW, APPROVED and REJECTED are driven by the period's dataset (below).
- No transition leads to calculation. CALCULATION_READY stays unreachable.

## Monitoring data (activity data)

`monitoring_records` is versioned (`record_id`, `version`, `is_current`).

Each record holds:
- the measurement;
- the entity at the measurement's level (farm / stratum / sampling point);
- a typed value;
- the phase (BASELINE / PROJECT / MONITORING);
- the observation date;
- the source (FIELD_OBSERVATION / FARMER_CLAIM / DOCUMENT / INSTRUMENT / OTHER).

Validation:

| Rule | Error code |
|---|---|
| The period must be ACTIVE or DATA_COLLECTION. | `PERIOD_NOT_OPEN` |
| The measurement must belong to the period's plan. | `MEASUREMENT_NOT_IN_PLAN` |
| The level entity must be given. | `LEVEL_REQUIRED` |
| The entity must belong to the project. | — |
| The unit must match the measurement. | `UNIT_MISMATCH` |
| The value must fit the type and the allowed values. | `INVALID_VALUE` |
| The same value must not be recorded twice. | `DUPLICATE_RECORD` |

Corrections (`/monitoring-records/{record_id}/amend`) create a new version with a reason. The old version is kept
as SUPERSEDED.

Sample-based methodology parameters (e.g. soil organic carbon) come from **sample analysis in Phase 6**. They are
not entered as monitoring data, and QA lists them as `sample_analysis_pending` (WARN).

## Evidence

`mrv_evidence` links a file or an observation to one of these entities:
- PROJECT;
- FARM;
- MONITORING_PERIOD;
- SAMPLING_POINT;
- FIELD_COLLECTION;
- MONITORING_RECORD.

Each item has a type:
- FIELD_PHOTO;
- FIELD_NOTE;
- PRACTICE_RECORD;
- DOCUMENT;
- GPS;
- OBSERVATION.

Storage and validation:
- **Files** go through the Phase 2 document pipeline. That covers the type check, scanning and storage (entity
  `mrv`).
- **SHA-256:** a checksum is stored for every file.
- **Type rules:**
  - Photos and documents need a file.
  - GPS evidence needs coordinates.
- **Collectors** may attach evidence only to their own collection or assigned point (`NOT_ASSIGNED`).
- **No satellite data:** no satellite observation is generated. A satellite adapter remains an integration point.

## MRV dataset (versioned) and QA

Dataset states:
- `DRAFT → COLLECTING → SUBMITTED → QA_REVIEW → APPROVED → SUPERSEDED`;
- `QA_REVIEW → REJECTED`;
- `SUBMITTED → COLLECTING` (correction).

Dataset rules:
- **Code:** `MRV-<year>-P<project no.>-M<period no.>-V<version>`.
- **One open dataset** (DRAFT, COLLECTING, SUBMITTED or QA_REVIEW) per period.
- **Submit (MRV manager):**
  - freezes a **snapshot**: plan, period, design versions, strata, points, accepted collections, current records
    and evidence checksums;
  - stores its **SHA-256**;
  - moves the period to SUBMITTED.
  - The dataset must not be empty (`DATASET_EMPTY`).
- **QA start (`mrv.review`):** dataset and period move to QA_REVIEW.
- **QA complete:** the result is PASS, FAIL or REQUIRES_CORRECTION. The reviewer must not be the submitter.
  PASS is refused while any automated check FAILs (`QA_CHECKS_FAILED`).
- **Approve (`mrv.approve`, not the submitter):**
  - requires the latest QA result PASS;
  - **re-verifies the snapshot hash**;
  - moves the period to APPROVED;
  - supersedes the previously approved dataset of the period.
  - Approved datasets are immutable: no endpoint edits a dataset, the snapshot is written once on submit and
    re-hashed on approval, and a correction is a new version.
- **Reject:** the dataset becomes REJECTED and so does the period. A new version re-opens collection.

The automated QA checks are deterministic (`mrv_service.qa_checks`):

| Key | Checks |
|---|---|
| methodology_version | dataset uses the project's locked version |
| mrv_plan_version | dataset uses the approved plan |
| sampling_completeness | every active point ACCEPTED or SKIPPED with a reason |
| field_records | no collection IN_PROGRESS / SUBMITTED / RETURNED |
| required_fields | accepted records have time, GPS and depth |
| gps_validity | GPS within the tolerance recorded on each field record (platform default 30 m) and inside the farm, or justified by a deviation note |
| sampling_point_validity | each point inside its farm boundary (SQL Server) |
| evidence | every accepted collection has the minimum number of field photos recorded on it (platform default 1) |
| monitoring_period_dates | collections and records fall within the period |
| missing_records | required FARM / PROJECT / project-configured measurements recorded |
| duplicate_records | no duplicate accepted collections or monitoring records |
| invalid_locations | no two points closer than 1 m |
| inconsistent_data (WARN) | actual depth equals planned depth |
| sample_analysis_pending (WARN) | "Awaiting laboratory analysis": methodology sampling-point parameters (e.g. SOC) are AWAITING_ANALYSIS; no value is entered |
| configuration (WARN) | CONFIGURATION_REQUIRED gaps |

## Lineage

Approved dataset:
- → snapshot (SHA-256)
- → plan version
- → locked methodology version and its rule revisions
- → design versions, which carry the random seed and allocations
- → stratum versions
- → points and relocation history
- → field collection versions
- → evidence checksums
- → monitoring record versions

Every step is audited. Workflow events are written for each transition. See [data-lineage.md](data-lineage.md).

## Roles

| Permission | Holders |
|---|---|
| `mrv.read` | MRV manager, project manager, field supervisor, GIS, platform GIS, methodology specialist, calculation analyst, QA, platform admin, support |
| `mrv.manage` | MRV manager, project manager |
| `mrv.collect` | MRV manager, field supervisor, field agent |
| `mrv.review` | MRV manager, QA officer |
| `mrv.approve` | QA officer |

Buyers, VVB, lab and finance roles have no MRV access. The farmer has none either: the farmer sees only their
existing self-service pages.

## Platform defaults vs methodology requirements

| Setting | Current value | Kind | Where it comes from | Recorded on |
|---|---|---|---|---|
| GPS tolerance from the planned point (S1) | 30 m | **PLATFORM DEFAULT** | `GPS_MAX_DISTANCE_M`, or the methodology SAMPLING key `gps_max_distance_m` | design version `field_rules`; field record `gps_tolerance_m` + `field_rules` |
| Duplicate sampling-point threshold (S1) | 1 m | **PLATFORM DEFAULT** | `SAMPLING_DUPLICATE_DISTANCE_M`, or `duplicate_point_distance_m` | design version `field_rules` |
| Field checklist (S2) | `PLATFORM-DEFAULT-1`: location confirmed, depth measured, sample labelled, photo taken | **PLATFORM DEFAULT** | `FIELD_CHECKLIST_VERSION` (versioned list in `services/field_rules.py`), or `field_checklist` | design version `field_rules`; field record `checklist_version` + items completed (`checklist`) |
| Minimum photos per sample (S2) | 1 | **PLATFORM DEFAULT** | `FIELD_MIN_PHOTOS_PER_SAMPLE`, or `min_photos_per_sample` | design version / field record `field_rules` |
| Plan approval with CONFIGURATION_REQUIRED gaps (V1) | DEMO / non-production: allowed with audited acknowledgement; production: **blocked** | **PLATFORM GOVERNANCE RULE** | `mrv_service.gap_approval_allowed()` | plan `gaps_acknowledged_by`, `MRV_PLAN_APPROVED` audit |
| Quantification approach, sampling depth, minimum samples per stratum, statistical design, precision, confidence, stratification variables | none | **METHODOLOGY REQUIREMENT** (only when the locked version's SAMPLING rule configures it; otherwise CONFIGURATION_REQUIRED) | methodology version SAMPLING rule | plan / design version (`requirement_source`, gaps) |
| Monitoring parameters (e.g. soil organic carbon) | as configured | **METHODOLOGY REQUIREMENT** | methodology version monitoring rules | plan measurements (source METHODOLOGY) |

The platform defaults are **not** requirements of VM0042, CCTS or any other methodology. A methodology version that
configures one of these keys overrides the default for new design versions; the value used, its source
(`PLATFORM_DEFAULT` / `METHODOLOGY`) and the rule code are frozen on the design version when it is created and copied onto
each field record when it is started. Changing a default later affects only new design versions; historical design
versions and field records keep their rules (migration 0007 backfilled pre-existing rows with the defaults in force then).

## Decisions (Phase 5 review, approved 3 Oct 2026)

- **V1 — MRV plan approval with gaps (platform governance rule, not a methodology rule).**
  - DEMO / development: allowed with an explicit, audited acknowledgement (who, when, reason).
  - Production: a QA officer must not approve a plan with unresolved methodology-required configuration. Approval needs
    the methodology version selected and the applicable MRV, sampling, monitoring and evidence requirements configured;
    otherwise CONFIGURATION_REQUIRED blocks it.
  - No production exception exists. If the business later approves one, it must require an authorized role, explicit
    acknowledgement, a reason, an audit event, the timestamp and the user, and must be recorded as an exception, not as a
    normal approval.
- **Soil carbon.** SOC values are never entered or invented in Phase 5. They come from the Phase 6 laboratory workflow;
  until then accepted samples show `analysis_status = AWAITING_ANALYSIS` and QA warns "Awaiting laboratory analysis".
- **DEMO data** stays as seeded: no laboratory results, SOC values, calculations or credits; Niphad remains marked DEMO.

## Assumptions needing confirmation (OPEN DECISION REQUIRED)

- **V2** — Sample-based methodology parameters (unit-bearing monitoring rules at sampling-point level) are treated as
  Phase 6 analysis outputs, not field entries.
- **V3** — QA approval of the dataset (`mrv.approve`) is held by the QA officer only. The MRV manager reviews but does
  not approve.
- **V4** — A correction after approval re-opens the period. The approved dataset stays APPROVED until a new version is
  approved, which supersedes it.
