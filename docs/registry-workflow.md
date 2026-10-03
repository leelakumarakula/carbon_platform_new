# Registry submission and credit issuance (Phase 9A)

Phase 9A records a period's registry submission and the credits a registry issues for it. Registries are **external counterparties**:
the platform never registers a project, never issues a credit and never generates a serial number. It records what the registry
states, with evidence, and a second person confirms each issuance.

> **Three separate quantities, never converted into each other:**
>
> | | Source | Label |
> |---|---|---|
> | Calculated | Phase 7 approved calculation run | "Calculated tCO2e — not verified, not issued" |
> | Verified | Phase 8B VVB decision | "VVB-stated verified quantity" |
> | Issued | The registry (issuance statement or API response) | "Registry-issued credits" |
>
> No endpoint accepts a calculated or verified value as an issuance quantity. The only quantity a user types is the registry-stated
> issued quantity, in whole units, backed by the registry's evidence.

Phase 9A does **not** include:

- available inventory, credit ownership, reservations, transfers or retirements (Phase 9B — see
  [credit-ledger-workflow.md](credit-ledger-workflow.md); an ISSUED batch enters the ledger only through a dual-control opening, and a 9A
  correction or cancellation is refused with `LEDGER_ACTIVITY_EXISTS` once the batch has ledger activity);
- marketplace, buyers or payment (Phase 10);
- revenue or farmer payouts (Phase 11);
- validation, accreditation, or any real registry API (no contract exists).

## Locked decisions (D1–D18)

| | Decision |
|---|---|
| D1 | Scope: registry submission and credit issuance only. The adapter has no `transfer_credits`, `retire_credits` or `get_credit_inventory`. |
| D2 | No registry portal and no registry users. Every 9A record belongs to the project's organization. |
| D3 | A project needs a **REGISTERED** registration at the target registry before a submission can be created or frozen. The registration is a recorded external fact: external project ID, registry, account, evidence, recording user and time, and the registry-stated date. |
| D4 | The adapter is chosen per registry account (`adapter_code`). The only application adapter is `MANUAL`, which never simulates anything: it raises `ManualActionRequired`, and the operator records the reference and evidence instead. |
| D5 | Issued ≤ verified applies only when the account **explicitly** declares `1 <credit unit> = 1 <verified unit>`. Without that, issuance is blocked with `UNIT_EQUIVALENCE_NOT_CONFIGURED`. With it, a cumulative CONFIRMED total above the VVB-stated quantity is blocked with `QUANTITY_EXCEEDS_VERIFIED`. There is no unit conversion. |
| D6 | Several issuances (tranches) per accepted submission, each separately traceable. |
| D7 | Whole units: positive integers, stored as `Numeric(28,0)`. |
| D8 | Vintage is registry-stated per batch, never computed or split by the platform. |
| D9 | Serials belong to the registry and are stored exactly as supplied. Duplicates are refused. Length and overlap checks run only through a registry-specific parser (none exists in the application; the TEST adapter has one). |
| D10 | Dual control: the recorder never confirms (`registry.confirm`, QA Officer). Corrections and cancellations keep history. |
| D11 | Submission requires a CURRENT VERIFIED VVB decision with a VVB-stated quantity (`VERIFIED_QUANTITY_REQUIRED`). The calculated quantity is never used. |
| D12 | Recalculation stays allowed. Submissions, issuances and batches are never silently changed. A superseded source invalidates an unsent submission and only flags a sent one (`SOURCE_SUPERSEDED`). Corrections are new issuances with `corrects_issuance_id`. |
| D13 | Project aggregate: VERIFIED → **ISSUED** at the first CONFIRMED issuance. REGISTRY_SUBMISSION, REGISTERED, ISSUANCE_PENDING and ACTIVE stay unreachable. Period records are authoritative. |
| D14 | PDF only. New categories: REGISTRY_SUBMISSION, REGISTRY_RESPONSE, ISSUANCE_STATEMENT. Registry documents are immutable after upload. |
| D15 | DEMO has one fictitious counterparty, "Carbon Registry R (DEMO)", and nothing else: no account, registration, submission, issuance or serial number. |
| D16 | The registry document checklist is configuration on the account. If none is configured: a warning outside production, a blocker in production (the NOT_PRODUCTION_READY policy). |
| D17 | No status-history table: status history lives in `workflow_events` and the audit log. `registry_events` keeps every external interaction. |
| D18 | Permissions are listed below. |

Interpretations made while implementing:

- **D5 configuration** sits on `registry_accounts.credit_unit` / `verified_unit_equivalent`. It is set explicitly and audited, and it
  cannot change once an issuance on the account has been confirmed.
- **D16 checklist** is a JSON list `[{code, title, source}]`, where `source` is REGISTRY_SUBMISSION, VERIFICATION_REPORT or
  CALCULATION_REPORT. Lineage documents are always included. REGISTRY_SUBMISSION items are satisfied by a document attached for that
  item.
- A cancelled issuance no longer counts toward the cumulative total, because the registry cancelled it. Its serial numbers stay allocated.
- The Registry Manager holds only registry and credits permissions, so a `/registry` page (`registry.read`) gives access to the per-period
  registry panel. Project Managers also see it as a tab in the MRV workspace.

## Lifecycles

```
registry account        ACTIVE → CLOSED
project registration    PENDING → REGISTERED | REJECTED                     (registry answer + REGISTRY_RESPONSE evidence)
registry submission     DRAFT → FROZEN → SUBMITTING → SUBMITTED | SUBMISSION_UNCONFIRMED   (API)
                        FROZEN → SUBMITTED                                   (manual: external reference + receipt)
                        SUBMITTING → FROZEN               only if the registry was certainly not reached
                        SUBMISSION_UNCONFIRMED → SUBMITTED | FROZEN (only after the registry confirms it has nothing)
                        SUBMITTED → ACCEPTED | REJECTED | WITHDRAWN;  DRAFT/FROZEN → CANCELLED | INVALIDATED
issuance                RECORDED → CONFIRMED (second person) | VOIDED;  CONFIRMED → CORRECTED | CANCELLED
credit batch            RECORDED → ISSUED | VOIDED;  ISSUED → SUPERSEDED | CANCELLED
```

Final states are frozen by triggers. A rejected submission is never edited into a successful one: a new submission links to it through
`previous_submission_id`.

## Eligibility

These are checked when a submission is created, frozen and submitted:

1. The period has a CURRENT VVB decision. The 8B lazy re-check runs first, so a recalculation supersedes the decision before this check.
2. The outcome is VERIFIED.
3. The decision is not superseded.
4. The verification submission and manifest hashes match.
5. A VVB-stated quantity exists.
6. The project has a REGISTERED registration at the target registry.
7. The account is ACTIVE.
8. The registry organization is an ACTIVE REGISTRY.
9. The environment matches.
10. No other open or accepted submission exists for the period at **any** registry.
11. The configured checklist is satisfied (at freeze).
12. DEMO projects never use an API adapter.

Error codes are the first blocker's code: NO_VERIFIED_DECISION, DECISION_NOT_VERIFIED, VERIFICATION_PACKAGE_MISMATCH,
VERIFIED_QUANTITY_REQUIRED, REGISTRATION_REQUIRED, REGISTRY_ACCOUNT_INACTIVE, REGISTRY_INACTIVE, ENVIRONMENT_MISMATCH,
OPEN_REGISTRY_SUBMISSION_EXISTS, CHECKLIST_NOT_CONFIGURED, CHECKLIST_INCOMPLETE and DEMO_API_NOT_ALLOWED.

## Frozen snapshot (registry-submission-v1)

The snapshot is canonical JSON plus SHA-256, fixed by a trigger once FROZEN. It is deterministic: no generation time and no user.

**Contents:**
- the registry, account (with its unit configuration) and registration (external project ID and registry date);
- the project, period, crediting period, standard and methodology code / version;
- the VVB decision: ID, code, outcome, stated quantity and unit, report and manifest SHA-256, decision time;
- the verification submission, Phase 8A readiness, calculation report (content and PDF SHA-256) and calculation run (input and output
  SHA-256);
- the dataset reference;
- the documents with their SHA-256 values (VVB report, calculation report and attached REGISTRY_SUBMISSION documents);
- the checklist with its satisfaction.

## Idempotency, timeouts and reconciliation

- At freeze, a unique `idempotency_key` is generated. In API mode, SUBMITTING and the key are **committed before** the adapter is called.
- **Registry unavailable** (request certainly not sent): back to FROZEN with an ERROR event, error `REGISTRY_UNAVAILABLE`.
- **Timeout or unknown outcome:** `SUBMISSION_UNCONFIRMED`. There is never an automatic retry: `submit` refuses because the submission is
  no longer FROZEN.
- **Reconciliation:**
  - an unconfirmed submission is resolved by looking it up with the same idempotency key (FOUND → SUBMITTED; NOT_FOUND → FROZEN);
  - a SUBMITTED submission has its status queried (ACCEPTED / REJECTED, with the registry payload hash as evidence);
  - an ACCEPTED submission has its issuances compared with the registry (MISMATCH events, never auto-fixed);
  - manual reconciliation needs registry evidence.
- **Unique indexes:**
  - registry + external submission ID;
  - registry + external issuance ID (CONFIRMED);
  - registry + external project ID;
  - registry + serial start / serial end (current ranges);
  - one open or accepted submission per period;
  - idempotency keys.
- **Optional `Idempotency-Key` header:** creating a submission or recording an issuance with the same key returns the original record.

## Issuance, batches and serial ranges

- **Recording requires:**
  - an ACCEPTED submission;
  - the registry issuance ID, date, whole quantity and unit;
  - batches (vintage + quantity) whose quantities add up to the issued quantity;
  - per batch, serial ranges whose quantities add up (start and end verbatim, both or neither);
  - an ISSUANCE_STATEMENT PDF, or in API mode the registry response, which must match exactly (`ISSUANCE_MISMATCH` otherwise).
- **Confirmation:**
  - is done by a `registry.confirm` holder other than the recorder;
  - re-checks D5 under a row lock;
  - marks the batches ISSUED and their ranges current (the unique indexes apply);
  - moves the project aggregate VERIFIED → ISSUED.
- **Correction:** a new issuance referencing the original. On confirmation the original becomes CORRECTED and its batches SUPERSEDED.
- **Cancellation:** records the registry's cancellation with evidence; the batches become CANCELLED.
- **No one row per credit:** a batch and its serial ranges represent the registry's blocks.

## Recalculation after verification or issuance (D12)

| When | Effect |
|---|---|
| Before freeze or submission | The DRAFT / FROZEN submission becomes INVALIDATED, with the reason. |
| After the registry has the submission | One `SOURCE_SUPERSEDED` registry event plus audit. The submission is unchanged; correcting it needs a controlled registry action. |
| After issuance | Issuances and batches are unchanged; batches show "source superseded". A registry correction is recorded as a correcting issuance. |

## Permissions (D18)

| Permission | Roles |
|---|---|
| registry.read | Project Manager, Registry Manager, QA Officer, MRV Manager, Calculation Analyst |
| registry.manage | Project Manager, Registry Manager (accounts, registrations, submissions, responses, recording issuances) |
| registry.confirm | QA Officer (independent confirmation, never the recorder) |
| credits.read | Project Manager, Registry Manager, Credit Manager, Finance Manager (Phase 9B adds QA Officer, and the ledger permissions credits.manage / confirm / holder_read / holder_retire) |

The VVB Reviewer, farmers, buyers and laboratory roles have no registry or credits permission. All records are organization-scoped:
404 out of scope, 403 when visible but forbidden.

## API

The endpoint list is in [api.md](api.md): `/api/v1/registry/...` (project side) and `/api/v1/credits/...` (read-only).

## Lineage

`GET /credits/batches/{id}/lineage` follows this chain:

> batch (vintage, serial ranges) → issuance (registry ID, evidence or API hash) → registry submission (snapshot SHA-256) → registration
> (registry project ID) → registry → VVB decision → verification submission → readiness → calculation report → calculation run →
> methodology version → MRV dataset → monitoring period → project → farms / farmer **codes**

The 8B verification lineage and the Phase 7 calculation lineage (samples, field collections, points, strata) are embedded for callers
who hold those permissions.

## Database (migration 0013)

- **Tables:** `registry_accounts`, `registry_project_registrations`, `registry_submissions`, `registry_events` (append-only),
  `credit_issuances`, `credit_batches`, `credit_serial_ranges`.
- **Sequences:** RREG, RSUB, ISS, CB.
- **Document categories:** the three registry categories.
- **Triggers:**
  - recorded registry facts, snapshots, idempotency keys and external references are fixed once set;
  - final states are frozen;
  - batches change only along their lifecycle;
  - serials never change;
  - nothing is deleted.
- **Downgrade:** refused while any Phase 9A row or registry document exists.

## DEMO and tests

- **DEMO:**
  - the Niphad and E2E projects have no VERIFIED period;
  - the Registry tab shows "DEMO — no registry issuance" with NO_VERIFIED_DECISION;
  - creating a submission is refused;
  - no DEMO credit exists.
- **TEST:** `backend/tests/registry_fixture.py` is a test-only API adapter, injected into the service layer and never registered. It
  covers:
  - receipt;
  - acceptance and rejection through status queries;
  - timeouts before and after receipt, and unavailability;
  - issuances with serials, and a made-up `TSER-` serial format with a parser.

  The full manual workflow (registration → submission → response → issuance → confirmation → correction / cancellation) runs over HTTP in
  `backend/tests/test_registry.py`, inside the rolled-back test database.
