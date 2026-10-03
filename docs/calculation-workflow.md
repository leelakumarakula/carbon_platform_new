# Carbon calculation workflow (Phase 7)

Phase 7 turns approved MRV data and approved laboratory results into a **calculated** quantity, using a methodology-specific
calculation module. It ends there:

> **Calculated tCO2e — not verified, not issued.** CALCULATED ≠ VERIFIED ≠ ISSUED. No credit, serial, registry ID, buffer,
> transfer, retirement or payout exists in Phase 7.

```
readiness (deterministic blockers)
  → run DRAFT (CALC-YYYY-NNNNNN)
  → freeze: re-check and copy every input into a canonical JSON snapshot + SHA-256 + normalized input rows  → INPUTS_FROZEN
  → execute the registered module on the frozen snapshot only (Decimal, synchronous)                        → CALCULATED
  → submit → calculation QA (start / complete PASS) → approve                                             → APPROVED
  (DRAFT / INPUTS_FROZEN → BLOCKED or CANCELLED; QA_REVIEW → REJECTED; APPROVED → SUPERSEDED by a newer approved run)
```

Project status: MONITORING → **CALCULATION_READY** after the first successful input freeze; → **CALCULATED** when the first run is
approved. An attempted (blocked) run never moves the project. Monitoring-period states are not changed, and MRV continues in
CALCULATION_READY / CALCULATED (later periods and data corrections, which lead to a recalculation).

## Calculation engine (decisions A1, A2)

- `app/calculation/framework.py` — methodology-independent framework (engine version `calc-framework-1.0`). The spec section 18
  methods: `validate_inputs`, `calculate_baseline`, `calculate_project`, `calculate_emissions`, `calculate_removals`,
  `calculate_leakage`, `calculate_uncertainty`, `apply_methodology_adjustments`, `calculate_net_result`, `validate_output`.
  The framework supplies **no formula**: a step method that a module does not implement blocks the calculation
  (CONFIGURATION_REQUIRED, reason STEP_NOT_IMPLEMENTED).
- A module declares, explicitly: methodology code, supported version label, expected `calculation_rules_version`, the exact
  calculation rule codes (code → step), variables (source, monitoring-rule code, **exact expected unit**, level, kind), constants
  (value, unit, source reference), one declaration per step (IMPLEMENTED with its rule, or NOT_INCLUDED_DEMO), module version and
  readiness. Any difference from the locked version's calculation rules blocks with CALCULATION_RULE_NOT_CONFIGURED.
- Execution: Python `Decimal` in a fixed context (34 digits, ROUND_HALF_EVEN only where Decimal must round, traps on invalid
  operations / division by zero / overflow); no float, randomness, I/O, clock or database. Every output must cite a calculation rule
  of its step and reference existing inputs or earlier outputs; exactly one final NET output. Values are stored as exact decimal text
  (no storage rounding); the UI only formats them for display.
- `app/calculation/registry.py` — the application registry. **Phase 7 registers no module**: no real methodology is configured and no
  illustrative DEMO equations were approved. Every project is therefore blocked with **CONFIGURATION_REQUIRED, reason
  NO_CALCULATION_MODULE** — including the DEMO Niphad project.
- Every module is NOT_PRODUCTION_READY until a future production-readiness workflow exists; NOT_PRODUCTION_READY modules are blocked in
  production (`NOT_PRODUCTION_READY`) and shown as a QA warning elsewhere.
- No endpoint accepts a calculated or final value (request bodies forbid unknown fields).

## Readiness and the frozen input snapshot (A5–A11, A18, A20, A22; C3, C4)

Blockers, in order: METHODOLOGY_NOT_LOCKED · PROJECT_NOT_IN_MRV · CONFIGURATION_REQUIRED (NO_CALCULATION_MODULE, STEP_NOT_CONFIGURED,
STEP_NOT_INCLUDED) · NOT_PRODUCTION_READY · CALCULATION_RULE_NOT_CONFIGURED · DATASET_NOT_APPROVED · SNAPSHOT_MISMATCH ·
OUTSIDE_CREDITING_PERIOD · MISSING_APPROVED_LAB_RESULT · MISSING_REQUIRED_INPUT · INPUT_NOT_NUMERIC · UNIT_MISMATCH · INPUT_TOO_LARGE.
A freeze that fails readiness turns the run BLOCKED (final) with every blocker recorded; the error code is the first blocker's.

Eligibility — nothing is ever substituted (no zero, average, previous, estimated or interpolated value):
- MRV: only the reporting period's **APPROVED** dataset, its snapshot hash re-verified; only records the snapshot marks as
  authoritative methodology records (supplementary observations never).
- Laboratory: only **APPROVED** results of the same project, the locked methodology version, a LABORATORY rule of that version and the
  dataset plan's measurement, whose root sample belongs to the reporting period and to a field-collection version in the dataset
  snapshot. DRAFT / SUBMITTED / REJECTED / WITHDRAWN / SUPERSEDED results are never used; one result per root sample and rule.
- Text results ("ND", "<0.05", "<LOQ") for a numeric variable → INPUT_NOT_NUMERIC (never parsed, never zero).
- Units: exact text after trimming, case-sensitive; no conversion library. A conversion constant (e.g. 44/12) may exist only inside a
  methodology module, with value, unit and source reference, frozen as an input.
- Sampling-design parameters (target precision, confidence) are inputs only when a module declares them; PROJECT_CONFIGURED values are
  frozen as such and give a QA warning.
- Crediting period (optional on a run): the reporting period must lie inside it.
- Synchronous execution with an input-size guard (`CALCULATION_MAX_INPUT_ROWS`, default 20 000).

The snapshot (`calculation-input-v1`) holds the project, reporting period, crediting period, dataset (id, code, version, snapshot
SHA-256), methodology lock (version, rule revisions, calculation rules), the module declaration and every input with its source ID and
version. It has no timestamp or user, so the same data always gives the same `input_sha256`.

Before execution the frozen sources are re-checked: dataset still APPROVED with the same hash, every laboratory result still APPROVED
at the same version, the methodology lock and rule revisions unchanged, the same module version → otherwise **INPUTS_OUT_OF_DATE**
(the run is BLOCKED; a new run is needed).

## Baseline, leakage, uncertainty, adjustments (A9, A10)

Methodology-specific only. If the module (from the methodology) does not configure a step, the calculation is blocked with
CONFIGURATION_REQUIRED. A DEMO calculation outside production may declare a step NOT_INCLUDED_DEMO; the UI shows
"Not included — DEMO". Nothing is fabricated: no baseline value, leakage deduction, uncertainty method, bounds or rounding.

## QA and approval (A15, C7)

Deterministic checks: input snapshot hash · inputs current · required inputs · units · input types · no duplicate authoritative inputs ·
module matches the frozen module and rules · **reproducible** (re-running the frozen snapshot gives the same `output_sha256`; stored
outputs match it) · steps complete (one final NET) · lineage complete · project-configured parameters (WARN) · module readiness (WARN /
FAIL in production) · environment · separation of duties. PASS is refused while a check fails; approval needs the latest QA PASS and
re-verifies both hashes and input currency.

Separation of duties: the reviewer and the approver are never the run's creator, freezer, executor or submitter
(`SEPARATION_OF_DUTIES`). The same QA officer may review and approve (as in MRV).

## Recalculation (A14)

`POST /calculations/runs/{id}/recalculate` creates a **new** run (own snapshot, hashes, module version, outputs, QA, approval) with
`recalculation_of_run_id` and a reason. The previous approved run stays authoritative until the new one is approved; then it becomes
SUPERSEDED in the same transaction. `GET /runs/{a}/compare/{b}` lists changed fields, inputs and outputs.

## Lineage

`GET /calculations/runs/{id}/lineage`: calculated value → run → methodology version and calculation rules → outputs (rule, inputs,
earlier outputs) → frozen inputs → approved laboratory result / monitoring record / stratum version / constant → sample and root
sample → field-collection version → sampling point → stratum → farm → farmer code → project; plus dataset, QA reviews and history.

## Permissions (A16)

| Permission | Roles |
|---|---|
| calculation.read | Calculation Analyst, QA Officer, MRV Manager, Project Manager |
| calculation.manage | Calculation Analyst (create, freeze, execute, submit, cancel, recalculate) |
| calculation.review | QA Officer |
| calculation.approve | QA Officer |

No access for farmers, buyers, laboratory roles, finance or VVB/ACVA in Phase 7. Everything is organization-scoped (404 when out of
scope). Calculation readers use the **Calculations** page (`/calculations`), which needs only `calculation.read`.

## Database (migration 0010)

`calculation_runs`, `calculation_inputs`, `calculation_outputs`, `calculation_qa_reviews`, sequence `seq_calculation_run_code`.
Triggers: inputs and outputs append-only; a completed QA review is immutable; a run's identity never changes, its frozen columns only
while DRAFT, its outputs only while INPUTS_FROZEN, final states never change, APPROVED → SUPERSEDED only, and runs are never deleted.
Filtered unique indexes: one open run and one APPROVED run per reporting period; one final output per run.

Phase 8A builds on approved runs: findings, the official report and internal verification readiness — see
[pre-verification-workflow.md](pre-verification-workflow.md).

## DEMO and tests

The DEMO methodologies have one placeholder calculation rule (`DC1`, NOT_IMPLEMENTED) and no approved equations, and the Niphad DEMO
dataset is still COLLECTING, so the DEMO calculation stays blocked: **CONFIGURATION_REQUIRED — NO_CALCULATION_MODULE**. No DEMO
equation, approved dataset or laboratory result was added for Phase 7.

The engine is proven by a **test-only** fixture (`backend/tests/calc_fixture.py`): deliberately non-carbon arithmetic with output unit
`TEST`, never registered in the application registry and unreachable through the API (tests pass it to the service layer). It drives
DRAFT → INPUTS_FROZEN → CALCULATED → QA_REVIEW → APPROVED, then a recalculation that supersedes the first run, and the project's
CALCULATION_READY → CALCULATED transitions, inside the rolled-back test database.
