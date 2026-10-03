# Internal pre-verification (Phase 8A)

Phase 8A adds the internal layer between an approved calculation and any later verification: **findings**, the official
**calculation report**, and **internal verification readiness** per monitoring period with a frozen **package manifest**.

> **Internal readiness — not verification.** READY means "internally approved for submission to verification". It is not a VVB/ACVA
> decision, not validation, not verification. CALCULATED ≠ VERIFIED ≠ ISSUED. The project status stays CALCULATED (no new project
> state). Phase 8B (VVB/ACVA) is not implemented.

## Findings (decisions B2–B6)

- Raised by the **QA Officer** (`calculation.review`) on any **non-DRAFT** calculation run (blocked, calculated, in QA, approved,
  superseded). A DRAFT run takes no finding (`FINDING_RUN_DRAFT`).
- Categories — exactly the six of the specification: Observation, Non-conformity, Clarification, Missing Evidence, Calculation Issue,
  Methodology Issue. No severity scale: only `blocking` true / false.
- Optional targets, all validated to belong to **the same run** (`INVALID_FINDING_TARGET` otherwise): frozen input `#seq`, output `#seq`,
  a calculation rule of the run's methodology version, a frozen source (`source_type` + `source_id` of one of the run's inputs), and an
  evidence document attached to the run (or the laboratory report of one of its laboratory-result inputs).
- Lifecycle: `OPEN → RESPONDED → RESOLVED`; `RESPONDED → OPEN` (response returned); `RESOLVED → OPEN` (reopened, with a reason);
  `OPEN / RESPONDED → WITHDRAWN` (only by the raiser, with a reason).
- The **Calculation Analyst** (`calculation.manage`) responds (text + optional evidence uploaded to the run). The QA Officer resolves,
  returns or reopens; **the resolver is never the responder** (`SEPARATION_OF_DUTIES`).
- The finding row keeps the current state; identity, target and original text never change, and every change is an append-only event
  (`calculation_finding_events`). Findings belong to their run and survive recalculation (a resolution may cite the run that fixes it).
- Findings never change Phase 7 approval. **Blocking** findings that are open (OPEN / RESPONDED) in the reporting period gate internal
  readiness, and opening or reopening one invalidates a READY readiness immediately.

## Calculation report (B7, B8, B11)

- Generated only for an **APPROVED** run (`RUN_NOT_APPROVED` otherwise — never for a BLOCKED run), by `calculation.manage`.
- Content is built only from frozen / immutable records: the run's input snapshot (methodology lock and rule revisions, module
  declaration, inputs with sources and laboratory report checksums), its append-only outputs, its completed QA reviews, its findings and
  the APPROVED dataset's frozen snapshot (MRV evidence checksums, point / collection / stratum codes). No live source table is read.
- Stored as canonical JSON + `content_sha256`, and a **deterministic text-only PDF** (in-house writer `text-pdf-1.0`: PDF 1.4, standard
  Helvetica, WinAnsi, no images, no `/Info`, no creation date, no ID) stored as a `CALCULATION_REPORT` document with `pdf_sha256`, plus
  `generator_version`. Re-rendering the stored content reproduces the PDF byte for byte.
- Labels: "Calculated tCO2e — not verified, not issued" (+ DEMO / TEST labels where applicable); "not a verification report".
- `GET /reports/{id}/verify`: content hash, stored PDF hash, document checksum, re-render, and freshness (`stale` when findings / QA or the
  generator changed). Tampering with the stored file is reported, and the download refuses it (`DOCUMENT_INTEGRITY_FAILURE`).
- Reports are immutable (trigger). A new version supersedes the CURRENT one only when the deterministic content or the generator version
  differs (`REPORT_UNCHANGED` otherwise). Synchronous with a size guard (`CALCULATION_REPORT_MAX_ROWS`, `REPORT_TOO_LARGE`).

## Internal verification readiness (B9, B12)

Per monitoring period: `DRAFT → SUBMITTED → READY → INVALIDATED`; `SUBMITTED → REJECTED / WITHDRAWN`; `DRAFT → WITHDRAWN`.
One open (DRAFT / SUBMITTED) and one READY review per period.

Prerequisites (deterministic, re-checked at creation, submission, approval and whenever readiness is read):

| Check | Blocker |
|---|---|
| The period's current APPROVED run (not superseded) | `NO_APPROVED_CALCULATION` |
| Input and output hashes valid | `INPUT_SNAPSHOT_MISMATCH` |
| Inputs current: dataset APPROVED with the same hash, laboratory results APPROVED at the same version, methodology lock and rule revisions unchanged | `INPUTS_OUT_OF_DATE` |
| The run's CURRENT report exists, verifies and is not stale | `REPORT_MISSING` / `REPORT_INTEGRITY_FAILED` / `REPORT_STALE` |
| No open blocking finding in the period | `OPEN_BLOCKING_FINDINGS` |
| Production-ready module in production | `NOT_PRODUCTION_READY` |

The analyst creates and submits; the QA Officer approves or rejects. The approver is never the submitter nor the run's creator, freezer,
executor or submitter (`SEPARATION_OF_DUTIES`). On approval a canonical **package manifest** is frozen with its SHA-256: project,
reporting and crediting period, methodology / version / rule revisions, dataset and snapshot hash, MRV evidence checksums, approved
laboratory results with report checksums, the run with input / output hashes, the report hashes, the period's findings and the QA
reviews — references and hashes of what already exists (no new evidence store).

Automatic invalidation (READY → INVALIDATED, audited): when the run is superseded, inputs become stale, the report changes or stops
verifying, or a blocking finding is opened or reopened. The readiness view also shows the period's Phase 7 calculation blockers (e.g.
CONFIGURATION_REQUIRED — NO_CALCULATION_MODULE).

## Permissions (B10)

No new permission or role. `calculation.read` (Analyst, QA Officer, MRV Manager, Project Manager) reads everything;
`calculation.manage` (Analyst) responds, uploads evidence, generates reports, creates / submits / withdraws readiness;
`calculation.review` (QA Officer) raises / returns / resolves / reopens / withdraws findings; `calculation.approve` (QA Officer) approves
or rejects readiness. VVB/ACVA, farmers, buyers, laboratory roles and finance have no access.

## DEMO

No DEMO methodology or seed data changed. Niphad stays blocked: readiness shows `NO_APPROVED_CALCULATION` and the calculation blocker
CONFIGURATION_REQUIRED — NO_CALCULATION_MODULE; no report exists for a blocked run. The E2E raises, answers and resolves a finding on the
E2E project's BLOCKED run. Successful report / readiness paths are exercised only in automated tests with the TEST-only fixture module.
