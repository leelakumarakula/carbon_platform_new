# VVB / ACVA verification workflow (Phase 8B)

Phase 8B records the work and the decision of an **external** verification body (VVB / ACVA) on a monitoring period's Phase 8A
READY package. The platform records the VVB's decision. It does **not** verify anything itself.

> Phase 9A continues from a VERIFIED decision with a registry submission and registry-stated issuance — see
> [registry-workflow.md](registry-workflow.md).
>
> **Verification only.** Phase 8B adds no validation, registry, issuance, credits, serial numbers, retirement, marketplace, buyer flow,
> payout, buffer, farm allocation or accreditation engine. A recorded VERIFIED decision is not an issuance.
> **Calculated tCO2e — not verified, not issued** stays the label of the calculated quantity. A **VVB-stated verified quantity** is
> shown only as the VVB stated it, with its unit. It is never a credit.

```
project (verification.manage)            VVB organization (org_type VVB, verification.vvb_*)
  propose assignment (VAS-…) ─────────────▶ accept + conflict-of-interest declaration | decline
  withdraw (PROPOSED) / terminate           terminate
  submit the period's valid READY package (VSUB-…) ──▶ allow-list package view, manifest documents
  respond to findings / corrective actions  ◀── raise findings (VFND-…), request corrective actions (CAR-…)
                                             close / return / reopen findings; accept / reject / cancel corrective actions
                                             record the decision (VDEC-…): VERIFIED / NOT_VERIFIED + VVB report PDF
```

## Decisions applied (C1–C20)

| | Decision |
|---|---|
| C1 | Verification only; validation is deferred (not modelled). |
| C2 | Period records are authoritative. The project status is an aggregate: CALCULATED → **VERIFICATION** when a calculated project has its first ACCEPTED assignment; VERIFICATION → **VERIFIED** with the first VERIFIED period. Later periods are tracked separately and never move the project back. MRV and calculation continue in VERIFICATION / VERIFIED. |
| C3 | A VVB is an organization with `org_type = 'VVB'`, ACTIVE, in the project's environment. |
| C4 | No accreditation is modelled. |
| C5 | Assignment = project + monitoring period + VVB organization. One open assignment (PROPOSED / ACCEPTED) per period. No reactivation; a replacement references the previous (closed) assignment. |
| C6 | An assignment may exist before READY; a submission needs the period's currently valid Phase 8A READY package. |
| C7 | Accepting needs a conflict-of-interest declaration (text, user, time), fixed once made. |
| C8 | VVB access only through `/api/v1/vvb/...`, scoped to assignments of the caller's VVB organization; project side `/api/v1/verification/...`. |
| C9–C11 | The VVB reads an allow-list view (below) and only documents referenced by the submitted manifest or attached to the submission. The 8A finding summaries are shared as they are in the manifest; audit history is never shared. |
| C12 | Every action is audited in **both** organizations (the laboratory precedent), with the actor's side and organization. |
| C13 | Findings: exactly the six categories, `blocking` flag, no severity scale. |
| C14 | Finding OPEN → RESPONDED → CLOSED, RESPONDED → OPEN (returned), CLOSED → OPEN (reopened with a reason). The VVB raises / closes; the project responds and never closes. Corrective action REQUESTED → RESPONDED → ACCEPTED; rejected → REQUESTED; cancellable. Overdue is derived (REQUESTED after its due date). |
| C15 | Decision VERIFIED / NOT_VERIFIED with the VVB report PDF; it references assignment, submission, period, VVB organization, user, report hash, manifest hash, time and rationale. |
| C16 | "VVB-stated verified quantity" (value + unit, only with VERIFIED), stored apart from the calculated quantity. |
| C17 | The project responds with `verification.respond` (not `calculation.manage`). |
| C18 | The decider is a VVB user who raised no finding on that submission (`SEPARATION_OF_DUTIES`). |
| C19 | Project: `verification.read / manage / respond`. VVB: `verification.vvb_read / vvb_review / decide`, and nothing else. |
| C20 | DEMO: assignment and COI only; the Niphad submission stays blocked (no READY package). No fake decision, report or quantity. |

Interpretations made while implementing:

- **I1:** accept and decline exist on the VVB side only. The project proposes, withdraws and terminates.
- **I2:** the project status is synchronized on acceptance, submission and decision, only when the state machine allows it.
- **I3:** a decision completes its assignment. A recalculation after a decision invalidates the submission when it is next read, and
  marks the decision SUPERSEDED with a reason. The decision row is kept and never edited. The project's aggregate status stays
  VERIFIED, and a new assignment opens the new verification path.
- **I4:** every OPEN or RESPONDED finding blocks the decision. The `blocking` flag is information for the project.
- **I5:** findings belong to one submission. When that submission is superseded or invalidated, its findings remain as history and
  the new package is reviewed afresh.
- **I6:** the VVB may also read documents attached to the submission (the project's response evidence and the VVB report), in
  addition to documents referenced by the manifest.

## Assignment

`PROPOSED → ACCEPTED → COMPLETED`; `PROPOSED → DECLINED | WITHDRAWN`; `ACCEPTED → TERMINATED`. Closing needs a reason (side recorded).
Terminating an assignment invalidates its current submission. A VVB sees PROPOSED / ACCEPTED / COMPLETED assignments of its own
organization. Before acceptance, no package data is visible.

## Submission (C6)

`POST /verification/assignments/{id}/submit`, with `verification.manage`. These are re-checked when the package is submitted:

- the assignment is ACCEPTED;
- the period has a READY readiness review (after the Phase 8A lazy re-check, so stale readiness is INVALIDATED first);
- it belongs to the same project and period;
- its run is the period's current APPROVED run;
- every Phase 8A prerequisite holds (hashes, currency, report not stale, no open blocking 8A finding, production readiness);
- the review's report is the run's CURRENT report;
- the manifest hash re-verifies.

Errors: `ASSIGNMENT_NOT_ACCEPTED`, `NO_READY_PACKAGE`, `READINESS_NOT_VALID` and `SUBMISSION_EXISTS` (that READY package is already
submitted).

`SUBMITTED → SUPERSEDED` (a newer READY package is submitted) and `SUBMITTED → INVALIDATED` (the package is no longer valid, for
example after a recalculation or termination). Both are checked lazily whenever an assignment or its period view is read. A submitted
package is never mutated. Its readiness, run, report and manifest hash are fixed by a trigger.

## VVB package view (allow-list, C9–C11)

`GET /vvb/submissions/{id}/package` returns:

- project code and name, and the reporting period;
- the submitted manifest **as is** (including the 8A finding summaries) and its hash;
- the methodology reference;
- the calculation run, its frozen inputs and outputs, and the report summary;
- the dataset's strata, sampling points (coordinates) and field collections;
- the sampled farms: farm code, area and boundary (the stratum's frozen boundary version), plus the farmer **code**;
- the approved laboratory results used;
- the allowed documents.

Never included: farmer names, contacts, KYC or government ID, bank or payout data, agreements, consent forms, land titles, other projects
or periods, internal user lists, or audit history. Project-side people appear as "Project team".

Downloads (`GET /vvb/submissions/{id}/documents/{document_id}`) work only for documents in the allow-list:

- the calculation report PDF;
- methodology source documents;
- the laboratory report PDFs of the results in the manifest;
- MRV evidence in the manifest;
- documents attached to the submission.

KYC, bank, agreement, consent, carbon-rights and land documents and RESTRICTED documents are excluded, even if referenced. The stored
bytes are re-hashed before every download, which is audited as `VVB_DOCUMENT_DOWNLOADED` in both organizations. Generic document,
project, calculation, farmer and audit endpoints stay closed to VVB users.

## Findings and corrective actions (C13, C14)

Targets must lie inside the submitted package. Available targets:

- the submission, the period, the run, the report, the dataset or the methodology version (each optionally with its id);
- an input or output, by id or #;
- a laboratory result or MRV evidence from the manifest;
- an allowed document.

INPUT, OUTPUT, LAB_RESULT, MRV_EVIDENCE and DOCUMENT need a reference (`TARGET_NOT_IN_PACKAGE` otherwise).

The project may upload PDF evidence (`POST /verification/submissions/{id}/evidence`, category `VERIFICATION_EVIDENCE`, attached to the
submission) and cite it in a response. A finding cannot be closed while it has an open corrective action. Every change writes an
append-only event (actor, organization, side) and a workflow event. Findings are worked only on the current submission of an ACCEPTED
assignment.

## Decision (C15–C18)

`POST /vvb/submissions/{id}/decision` (multipart) takes:

- `outcome` (VERIFIED / NOT_VERIFIED);
- `rationale`;
- the VVB report PDF (`file`, category `VERIFICATION_REPORT`, owned by the VVB organization);
- optionally `verified_quantity` + `verified_quantity_unit`, accepted only with VERIFIED.

Refused when:

- the submission is not current (it is re-checked first);
- the assignment is not ACCEPTED;
- a finding is OPEN or RESPONDED;
- a corrective action is REQUESTED or RESPONDED;
- the decider raised a finding on the submission;
- the report is missing or not a PDF;
- the quantity is not a non-negative decimal or has no unit.

The decision stores the report and manifest hashes. It completes the assignment and moves the aggregate project status (C2). One
CURRENT decision per period exists (filtered unique index). A decision is immutable, except CURRENT → SUPERSEDED with a time and
reason.

## Lineage

`GET /verification/decisions/{id}/lineage` follows this chain:

> decision → VVB organization → assignment (COI) → submission → Phase 8A readiness review → manifest (hash matches the decision) →
> calculation report → approved calculation run → methodology version → MRV dataset → monitoring period → project

When the caller also holds `calculation.read`, the Phase 7 lineage is embedded: run → frozen inputs → laboratory results / monitoring
records → samples → field collections → sampling points → strata → farms → farmer codes.

## Permissions

| Permission | Roles |
|---|---|
| verification.read | Project Manager, MRV Manager, Calculation Analyst, QA Officer |
| verification.manage | Project Manager (propose, withdraw, terminate, submit) |
| verification.respond | Project Manager, MRV Manager, Calculation Analyst (respond, upload evidence) |
| verification.vvb_read / vvb_review / decide | VVB / ACVA Reviewer (in the VVB organization only) |

Each check covers:

1. the user belongs to the VVB organization;
2. that organization's `org_type` is VVB;
3. it is ACTIVE;
4. its environment matches;
5. the assignment is ACCEPTED (or COMPLETED for reads);
6. the project matches;
7. the period matches;
8. the submission belongs to the assignment;
9. the resource is on the allow-list.

Failing any of these gives 404 (existence is not revealed), or 403 when the record is visible but the permission is missing.

## Database (migration 0012)

- Tables: `verification_assignments`, `verification_submissions`, `verification_findings` + `verification_finding_events`,
  `corrective_actions` + `corrective_action_events`, `verification_decisions`.
- Sequences: VAS / VSUB / VFND / CAR / VDEC.
- Documents categories: `VERIFICATION_REPORT`, `VERIFICATION_EVIDENCE` (PDF only).
- Filtered unique indexes: one open assignment per period; one SUBMITTED submission per assignment; one CURRENT decision per period.
- Checks:
  - a COI declaration on ACCEPTED / COMPLETED / TERMINATED;
  - a reason when declined, withdrawn or terminated;
  - quantity and unit together;
  - the six categories.
- Triggers:
  - event tables are append-only;
  - identities never change and nothing is deleted;
  - the COI declaration is fixed;
  - closed assignments, SUPERSEDED / INVALIDATED submissions, and ACCEPTED / CANCELLED corrective actions are final;
  - a decision changes only CURRENT → SUPERSEDED.
- The downgrade is refused while any Phase 8B row or verification document exists.

## DEMO and tests

The DEMO seed contains no verification data. In DEMO, the project manager may propose DEMO-VVB-C and the DEMO VVB reviewer may accept
with a COI declaration. Submission is refused (`NO_READY_PACKAGE`) because no calculation module exists, so no period is READY. No
decision, report or verified quantity is ever created for DEMO.

The successful path (READY → submit → findings → corrective actions → decision → supersession after a recalculation) is proven only in
backend tests, with the TEST-only Phase 7 fixture inside the rolled-back test database (`backend/tests/test_verification.py`).
