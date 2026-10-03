# Laboratory & sample analysis workflow (Phase 6)

Phase 6 turns a field sample into an **approved laboratory result with full lineage**. It ends there: no calculation, no
tCO2e, no credits, no verification, no issuance, no retirement. Nothing is converted, inferred or invented — values, units
and text are stored exactly as the laboratory reported them, and every rule below comes from the locked decision table.

```
engagement (project proposes → laboratory accepts)
  → sample registered from a SUBMITTED / ACCEPTED field record  → tests created automatically (one per in-scope rule)
  → sealed → added to a shipment → dispatched → received by the laboratory (per item) → laboratory registration (accession)
  → test started → result entered (+ PDF report) → submitted → laboratory QA (another LAB_MANAGER) → APPROVED
  → approved result + lineage visible to project users; the Phase 5 field record shows ANALYSED (display only)
```

## Engagements

- `PROPOSED → ACTIVE → ENDED`. Proposed by PROJECT_MANAGER / MRV_MANAGER (`lab.engage`), accepted by a LAB_MANAGER of the
  laboratory (`lab.engagement_accept`). The proposer can never accept (`SEPARATION_OF_DUTIES`), even holding both roles.
- Scope = LABORATORY rules (`measurement_source = LABORATORY`) of the project's **locked** methodology version
  (`project_laboratory_engagement_rules`). Any other rule is refused (`RULE_NOT_LABORATORY`). DEMO and live never mix
  (`ENVIRONMENT_MISMATCH`).
- One ACTIVE (and one PROPOSED) engagement per project + laboratory. A scope change is a new engagement; when it is accepted the
  old one ends in the same transaction.
- Either side may end it — project side (`lab.engage`) or laboratory side (`lab.engagement_accept`) — with a reason; user, side
  and time are stored and audited. An ENDED engagement is never reactivated (`ENGAGEMENT_ENDED`).
- **Wind-down after END**: receipt of shipments already dispatched, IN_PROGRESS tests, result entry / submit / QA / correction stay
  allowed; a new shipment, dispatch, a new test start and a retest are refused with `ENGAGEMENT_NOT_ACTIVE`.

## Samples (`SMP-YYYY-NNNNNN`)

- Registered by the collector of the record (FIELD_AGENT, own records only) or by a supervisor / MRV manager, only from a
  **SUBMITTED or ACCEPTED** field collection. The sample keeps that `field_collection_id` forever, even when the record is later
  corrected (QA warns when the version is SUPERSEDED, fails when it is not ACCEPTED).
- Depth defaults to the field record's actual depth; quantity / unit, description, container label, seal and environment are
  stored. Splits (`parent_sample_id`, same `root_sample_id`) carry no automatic tests; they can be used for a retest.
- **Automatic tests**: on registration of a root sample, one `lab_test` (`LT-YYYY-NNNNNN`) per in-scope rule, each linked to the
  engagement, methodology version, rule and the approved plan's measurement (`PLAN_MEASUREMENT_MISSING` otherwise). No manual
  ordinary tests; no duplicate per sample + rule except explicit retests (filtered unique index).
- The field checklist (PLATFORM-DEFAULT-2) contains `sample_labelled_with_sample_code` — "Sample container labelled with its
  sample code (SMP-…)". The mobile collection screen has a "Register & seal sample" section.

## Chain of custody

Append-only `sample_custody_events` (DB trigger), ordered by `sequence_no`, each with actor, organization, role, side, time,
location, seal and shipment. States:

`REGISTERED → SEALED → IN_SHIPMENT → DISPATCHED → (IN_TRANSIT) → LAB_RECEIVED → LAB_REGISTERED → IN_ANALYSIS → ANALYSED`

plus `REJECTED_AT_RECEIPT`, `VOIDED` and `EXCEPTION` (DAMAGED, SEAL_BROKEN, LOST, OTHER — reason required; resolved back to the
interrupted state). Retention / return / disposal are out of scope: custody ends at ANALYSED.

## Shipments (`SHP-YYYY-NNNNNN`)

`DRAFT → DISPATCHED → RECEIVED` (or `CANCELLED`). Managed by FIELD_SUPERVISOR / MRV_MANAGER (`lab.shipment_manage`), never by a
FIELD_AGENT. Only SEALED samples for the same laboratory; a sample is in at most one open shipment. Receipt is per item
(accepted with condition and observed seal, or rejected with a reason — rejection cancels the sample's tests). PDF custody
documents can be attached by both sides.

## Results

- Versioned per test (`version`, `supersedes_result_id`). Each result references the test, sample, root sample, rule, plan
  measurement, methodology version, laboratory, PDF report document, analyst and source (`MANUAL` or `LIMS_IMPORT`; there is no
  DEMO_MOCK source).
- Exactly one value: `NUMERIC` (`value_number`) or `TEXT` (`value_text`, verbatim). The plan measurement type decides which can be
  approved; "ND", "<0.05", "<LOQ" are never parsed and there is no qualifier column. No unit conversion.
- `DRAFT → SUBMITTED → QA_REVIEW → APPROVED`, plus `REJECTED`, `RETEST_REQUIRED`, `WITHDRAWN`, `SUPERSEDED`. Exactly one APPROVED
  result per root sample + rule (filtered unique index); an APPROVED row is immutable except APPROVED → SUPERSEDED (DB trigger).
- Corrections of an approved result create a new version; the old one stays APPROVED until the new one is approved, then both
  change in one transaction.

## Laboratory QA (LAB_MANAGER, `lab.qa`)

Deterministic checks: lineage, field collection version ACCEPTED, unbroken custody, engagement covering the rule, rule declared
LABORATORY, **unit** (exact text after trimming, case-sensitive; missing rule unit = CONFIGURATION_REQUIRED — blocked in
production, acknowledgeable with audit outside production; mismatch = UNIT_MISMATCH → FAIL), result type, PDF report present,
report SHA-256 re-verified from storage, analysis after receipt (compared at whole seconds, the precision of the entered time) and
not in the future, separation of duties, environment/source.

**Separation of duties**: the approving manager cannot be the analyst or submitter, nor the sample registrant or sealer, the
shipment creator or dispatcher, or the retest requester (`SEPARATION_OF_DUTIES`, 403).

## Retests

LAB_MANAGER only (`lab.retest_request`), with a reason, on an APPROVED result (or via a RETEST_REQUIRED QA decision), on the same
sample or a split of the same root, while the engagement is ACTIVE. The approver must differ from the requester, analyst and
submitter. The previous approved result stays authoritative until the retest result is approved.

## Laboratory-facing API and isolation

`/api/v1/laboratory/*` returns explicit allow-list schemas (`*LabView`): sample code, description, depth, quantity, container,
seal, accession, project code, project organization name, methodology label, rule, required unit. **Never** farmer, farm, GPS,
sampling point, stratum, field collection or MRV data; project-side custody events show only state, time and organization.
Laboratory users can see only samples shipped to their laboratory. Documents are PDF only. Enforced in the backend.

## Project read model

`/api/v1/lab/results` (default APPROVED; drafts never reach project users) and `/api/v1/lab/results/{id}/lineage`: result →
versions → test (retest chain) → sample / root → field collection version → sampling point → stratum → farm → project →
locked methodology rule → plan measurement, plus shipments, receipts, QA reviews and custody.

## LIMS

`app/integrations/lims.py` defines the `LimsAdapter` interface (submit manifest, fetch results, acknowledge) and a
`NoLimsAdapter` that raises `LimsNotConfigured`. No LIMS is connected; imported results would use source `LIMS_IMPORT` with an
external result ID unique per laboratory.

## DEMO

`seed-demo` runs the manual flow on the Niphad DEMO project with DEMO-LAB-B: mrv@ proposes, labmanager@ accepts, collector@
registers and seals, supervisor@ ships, labtech@ receives, registers, analyses (DEMO placeholder value and PDF) and submits, and
labqa@ — a second LAB_MANAGER independent of every earlier step — approves. All DEMO-marked; it is not a real analysis.
