# Methodology engine (Phase 4)

Code:
- `backend/app/rules/methodology_engine.py`: the pure, deterministic rules engine.
- `backend/app/services/methodology_service.py`: catalog, versions and rules.
- `backend/app/services/project_methodology_service.py`: facts, evaluation, review, confirm and unlock.
- Models: `backend/app/models/methodologies.py`.

```
PROJECT ─▶ STANDARD ─▶ ACTIVITY ─▶ METHODOLOGY ─▶ METHODOLOGY VERSION
                                     (candidates)    (confirmed = locked)
```

**The rules engine proposes; people decide.** No candidate is ever selected automatically. A methodology specialist
records a recommendation, and the project developer confirms it, which locks the methodology and its version.

## Catalog and versioning

| Entity | Notes |
|---|---|
| `methodologies` | code (e.g. VM0042), name, **one standard**, activities covered (`methodology_activities`, each must be offered under the standard), owner, source URL, `environment` |
| `methodology_versions` | version label as published, internal number, status, effective dates, source (name / URL / document), **rule-set revision counters** (`rules_version`, `monitoring_rules_version`, `calculation_rules_version`), `calculation_readiness` (always starts NOT_PRODUCTION_READY), `based_on_version_id`, submitted/approved/superseded stamps |
| `methodology_applicability_rules` | deterministic `fact_key OPERATOR expected_value`, category, `on_fail`, evidence requirement, mandatory flag, source reference |
| `methodology_monitoring_rules` | parameter, unit, frequency, method, evidence, **`measurement_source`** (FIELD / FIELD_ACTIVITY / LABORATORY, required — decision V2-A); used to configure MRV in Phase 5 |
| `methodology_calculation_rules` | step (baseline, project, emissions, removals, leakage, uncertainty, adjustment, net), **equation reference in the source**, parameter names; `implementation_status` NOT_IMPLEMENTED. These rows document; they never execute |
| `methodology_rules` | other requirements: crediting period, baseline, additionality, leakage, uncertainty, sampling, permanence. JSON `parameters` apply only when configured, e.g. `{"min_years": 20}` |
| `methodology_documents` | source documents (category METHODOLOGY_DOCUMENT) in the document store |
| `methodology_change_history` | **append-only**: every change to a methodology, version or rule |

Version lifecycle (`METHODOLOGY_VERSION_MACHINE`):

```
DRAFT ─▶ IN_REVIEW ─▶ APPROVED ─▶ SUPERSEDED / RETIRED
  │          └─(returned)─▶ DRAFT
  └─▶ WITHDRAWN
```

- **Submit** requires at least one applicability rule, an authoritative source (name, URL or document) and an
  effective date.
- **Approve** needs `methodologies.approve`, and the approver must not be the submitter. Drafts never become
  active by themselves.
- Several versions can be APPROVED at once. For example, two active versions of one methodology can co-exist.
  Approving a version can optionally supersede an older APPROVED version.
- **Rules are editable only in DRAFT.** Changing rules means a new draft version, optionally copied from an
  existing one. Changing a copied rule set bumps its revision counter, so every distinct rule set has its own
  number.

## Rules engine

Each applicability rule is checked against a **fact**, giving PASS, FAIL, MISSING or SKIPPED. The candidate's
outcome is then:

| Outcome | When |
|---|---|
| NOT_APPLICABLE | a mandatory rule with `on_fail = NOT_APPLICABLE` failed |
| NEEDS_INFORMATION | a mandatory rule's fact is missing (or the value cannot be evaluated), or the version has no applicability rules |
| EVIDENCE_REQUIRED | a rule with `on_fail = EVIDENCE_REQUIRED` failed, **or** a rule with an evidence requirement passed only on a *declared* fact |
| APPLICABLE | everything else |

Precedence: NOT_APPLICABLE > NEEDS_INFORMATION > EVIDENCE_REQUIRED > APPLICABLE.

Each rule result stores:
- the rule code and title;
- the category and source reference;
- the fact key, the expected value and the actual value;
- the fact source (PROJECT, FARM_DATA or DECLARED);
- the check, its effect and a plain-language reason;
- the evidence requirement.

Engine version: `1.0.0`. It is stored with every evaluation.

Operators: EQUALS, NOT_EQUALS, IN, NOT_IN, ANY_IN, ALL_IN, NONE_IN, GTE, LTE, BETWEEN, DATE_ON_OR_AFTER,
DATE_ON_OR_BEFORE, IS_TRUE, IS_FALSE, EXISTS. Strings compare case-insensitively.

### Facts derived from project data

| Key | Source |
|---|---|
| `standard_code`, `activity_code`, `country`, `project_type`, `project_start_date`, `farm_count`, `project_area_ha` | project / SQL Server boundary |
| `farm_countries`, `farm_states`, `farm_districts`, `farms_all_verified` | participating farms |
| `land_use_current`, `land_use_all_years`, `land_use_history_years_min` | current land-use history records (only set when records exist) |
| `crop_history_years_min`, `crops` | crop history (only set when records exist) |
| `historical_/current_/proposed_practice_categories`, `…_practice_types` | practice history by phase (only set when records exist) |
| `baseline_recorded`, `baseline_period_years`, `crediting_period_years`, `carbon_rights_all_verified`, `verified_evidence_count` | project records |

**"No records" is missing information, not a negative fact.** For example, a project with no practice records
gets NEEDS_INFORMATION, not NOT_APPLICABLE.

**Declared facts.** Users may declare other facts, such as `additionality_assessment = COMPLETED`.
- They are labelled DECLARED and stored in the evaluation snapshot.
- They cannot override derived facts (`DECLARED_FACT_CONFLICT`).
- A rule with an evidence requirement that passes on a declared fact gives EVIDENCE_REQUIRED.

## Project selection workflow

1. The project reaches ACTIVITY_SELECTED (Phase 3).
2. **Evaluate candidates.** Holders of `projects.manage` (the PM) or `methodologies.review_project` (the
   specialist) can run an evaluation.
   - Candidates are APPROVED, effective versions (at the project start date) of ACTIVE methodologies of the
     project's standard that cover its activity.
   - Drafts, versions under review, and retired, superseded or expired versions are never candidates.
   - The first evaluation moves the project to METHODOLOGY_REVIEW (`methodology_status = UNDER_REVIEW`).
   - Every evaluation is kept, append-only, with its facts snapshot.
3. **Specialist review.** A user with `methodologies.review_project` records RECOMMENDED or NOT_RECOMMENDED
   with notes.
   - NOT_APPLICABLE and NEEDS_INFORMATION candidates cannot be recommended.
   - Recommending an EVIDENCE_REQUIRED candidate requires acknowledging the evidence.
4. **Confirm.** A user with `projects.manage` confirms a candidate, which must:
   - come from the **latest** evaluation;
   - be APPLICABLE or EVIDENCE_REQUIRED;
   - have the specialist's RECOMMENDED review as its most recent review;
   - be recommended by someone other than the confirmer;
   - still be an APPROVED version;
   - satisfy any crediting-period parameters configured on the version.

   Confirmation creates `project_methodologies` (LOCKED). It records the version and its three rule-set revisions,
   then moves the project to METHODOLOGY_CONFIRMED (`methodology_status = CONFIRMED`).
5. **Locked.**
   - Approving a newer version does not change the project; the screen shows "newer version available".
   - Further evaluation and re-opening are refused until an explicit **unlock**. Unlock needs `projects.manage`
     and a reason, is audited, keeps the row as UNLOCKED, and returns the project to METHODOLOGY_REVIEW.

Audit events:
- Project: `PROJECT_METHODOLOGY_CANDIDATES_EVALUATED`, `PROJECT_METHODOLOGY_REVIEWED`,
  `PROJECT_METHODOLOGY_CONFIRMED`, `PROJECT_METHODOLOGY_UNLOCKED`, plus `PROJECT_STATUS_CHANGED` and the status
  history.
- Catalog: `METHODOLOGY_CREATED/UPDATED`, `METHODOLOGY_VERSION_CREATED/UPDATED/SUBMITTED/APPROVED/RETURNED/SUPERSEDED/RETIRED/WITHDRAWN`,
  `METHODOLOGY_RULE_ADDED/REMOVED`, `METHODOLOGY_DOCUMENT_ADDED`.

## Measurement provenance of monitoring rules (decision V2-A)

Measurement provenance is explicitly defined by the methodology monitoring rule. The platform does not infer laboratory provenance from units, names, numeric types or sampling frequency.

| `measurement_source` | Meaning | Phase 5 MRV |
|---|---|---|
| `LABORATORY` | Analysed in a laboratory on a collected sample (e.g. SOC, bulk density, when the methodology says so) | Value entry refused (`LABORATORY_RESULT_REQUIRED`); authoritative only as an APPROVED Phase 6 lab result. Attached to sampling points |
| `FIELD` | Measured or observed in the field | Captured as monitoring data |
| `FIELD_ACTIVITY` | Activity / management data (inputs, operations) | Captured as monitoring data |
| `UNCLASSIFIED` | Only for rules that existed before the field (migration 0008) and could not be classified safely | Not capturable (`MEASUREMENT_SOURCE_UNCLASSIFIED`); a CONFIGURATION_REQUIRED gap for MRV plans |

- **Field-kit measurements (decision V2-C)** are not automatically laboratory measurements: the same parameter (pH, SOC,
  bulk density, nutrients, …) is FIELD or LABORATORY exactly as the methodology rule declares. There is no parameter-specific
  logic.
- The value is **required** when a monitoring rule is created (API and the version page); there is no default and
  `UNCLASSIFIED` is not accepted for new rules.
- A version that still contains an `UNCLASSIFIED` monitoring rule cannot be submitted or approved (`MEASUREMENT_SOURCE_UNCLASSIFIED`;
  the approval check also covers versions that were already IN_REVIEW when migration 0008 ran). Approved versions are
  immutable, so an unclassified rule is classified by creating a new version (copied rules keep their classification).
- Migration 0008 backfilled existing rows deterministically: the DEMO soil-sampling rule `DM1` of `DEMO-ALM-SOC` and
  `DEMO-CCTS-SOIL` → `LABORATORY` (known DEMO semantics); every other existing row → `UNCLASSIFIED`. Each backfilled row has
  a `METHODOLOGY_RULE_SOURCE_BACKFILLED` entry in the methodology change history. Rule-set revision counters were not
  changed.
- Not defined by the platform: test methods, depths, procedures, acceptance limits, replicates, accreditation or retest
  rules — those belong to the authoritative methodology and the Phase 6 laboratory design.

## Methodology safety (spec §48)

- No methodology rules or equations are shipped with the platform. Real rules must be entered by a methodology
  specialist from the authoritative, versioned source, then approved by a second person.
- The DEMO methodologies (`DEMO-ALM-SOC`, `DEMO-CCTS-SOIL`) are **illustrative**. Their rules were invented to
  demonstrate the engine; they are flagged `is_demo_illustrative` and labelled in the UI.
- Calculation readiness stays NOT_PRODUCTION_READY until Phase 7 implements and verifies a methodology module
  against the authoritative equations, with reference tests.

## Assumptions (to confirm)

| # | Assumption |
|---|---|
| M1 | The specialist recommends and the project developer (`projects.manage`) confirms; the recommender cannot also confirm |
| M2 | EVIDENCE_REQUIRED candidates may be confirmed once the specialist acknowledges the evidence; NOT_APPLICABLE and NEEDS_INFORMATION cannot |
| M3 | Candidate effectiveness is judged at the project start date (today if none) |
| M4 | Version approval: same role (methodology specialist), different person |
| M5 | Unlocking is allowed for `projects.manage` with a reason; the earlier lock is kept as history |
