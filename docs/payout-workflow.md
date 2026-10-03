# Revenue, farmer entitlement, payouts and reconciliation (Phase 11, spec §52)

Phase 11 adds a **money ledger** beside the Phase 9B credit ledger. It records revenue from immutable Phase 10 records, turns it into
farmer entitlements through approved, versioned configuration, and pays those entitlements with full separation of duties and
reconciliation. The credit ledger remains the only record of credit ownership, and a credit quantity is never used as a money amount.

**Nothing economic is hard-coded.** The platform holds no farmer percentage, fee, commission, tax, default rounding mode or allocation
rule. Each of these is a business value, entered as versioned configuration from the project's agreements and approved by a second
person. Until a project has that approved configuration, settlement is refused and the screens say that configuration is required.

## 1. Revenue (locked decisions D8 / D9 / D10)

- **Recognition (per order item).** A RECOGNITION is written inside the Phase 10 delivery-completion transaction. It is written only when
  the order's payment is CONFIRMED and the item's 9B transfer is COMPLETED.
  - Amount: the item's `line_total`, in the order currency.
  - Lineage: order, order item, payment, 9B transfer, credit batch, project, monitoring period, and the seller organization (the payee).
  - It is idempotent: a unique filtered index allows one recognition per order item, and `POST /revenue/recognize` returns the existing
    record.
- **Reversal.** A COMPLETED refund (Phase 10 refunds cover the whole payment) writes one REVERSAL per recognition of the order. The
  reversal has a negative amount and references both the recognition and the refund. It is unique per recognition and is written in the
  same transaction as the refund.
- **Append-only.** `revenue_records` is protected by a trigger. Historical revenue is never edited.
- **No amount from the client.** No endpoint accepts a revenue amount.

## 2. Configuration (business decisions represented as approved, versioned configuration)

| Configuration | Content | Rules |
|---|---|---|
| Revenue-share version (`revenue_share_versions`) | `farmer_share_pct` (0 < x ≤ 100); `deduct_approved_costs`; `rounding_mode` (HALF_UP / HALF_EVEN / DOWN); effective from / to; `source_reference` (the agreement or clause) | DRAFT → IN_REVIEW → APPROVED → SUPERSEDED. Author holds `sharing.manage`; approver holds `sharing.approve` and is never the author. No field has a default. Values freeze once submitted, and an approved version can only become SUPERSEDED (trigger). Approving a new version supersedes the previous one. |
| Farm allocation (`farm_allocation_versions` + append-only `farm_allocation_lines`) | per project and monitoring period: one line per farm participation, with its `share_pct`; `basis_reference` | Every farm appears at most once, and only farms whose participation overlaps the period. The shares must total **exactly 100**, checked on submit. Same approval workflow and immutability as above. Acreage and tCO2e are never used automatically. |
| Project costs (`project_costs`) | category, description, amount actually incurred, currency, date, optional period and reference, COST_EVIDENCE PDF | PENDING_APPROVAL → APPROVED / REJECTED. Approver holds `costs.approve`, is never the recorder, and needs the evidence. A correction is a new negative cost that references an approved cost. Costs are deducted only when the run's revenue-share version says so. |

## 3. Settlement runs (`settlement_runs`, calculation `fin-calc-1`)

A run covers one project, one monitoring period and one currency. It requires an APPROVED revenue-share version that covers the whole
period and an APPROVED allocation for that period. A DEMO project is refused (`DEMO_FINANCE_NOT_ALLOWED`).

**Inputs.** Calculation (`settlement.calculate`) claims the unsettled inputs. Each claim is a link row with an `active` flag; filtered
unique indexes on `active = 1` stop any record from being settled twice, even under concurrency, and the project row is locked during
the calculation.
- **Revenue:** records of the project, period and currency whose seller is the project organization.
- **Costs:** approved costs of that period, or with no period, in the run currency.

**Formula.**

```
gross              = Σ included revenue records (recognitions > 0, reversals < 0)
deducted_costs     = Σ included approved costs            (0 if the version does not deduct costs)
distributable      = gross − deducted_costs               (< 0 → refused: NEGATIVE_DISTRIBUTABLE)
line entitlement   = quantize(distributable × farmer_share_pct / 100 × line share_pct / 100,
                              currency minor unit, the version's rounding_mode)
farmer_total       = Σ line entitlements                  (> distributable → refused: ROUNDING_EXCEEDS_DISTRIBUTABLE)
developer_residual = distributable − farmer_total
```

**Rounding policy.** Arithmetic is Decimal only, never a float. Each line is quantized independently to the ISO-4217 minor unit
(`CURRENCY_EXPONENTS`) with the mode chosen in the approved version. The rounding difference stays in `developer_residual`; it is never
redistributed silently.

**Freezing and verification.**
- All inputs and results are written to a canonical JSON snapshot (`input_snapshot`), whose SHA-256 is stored in `input_sha256`.
- `farmer_entitlements` are append-only, one row per allocation line.
- `GET /settlements/{id}/verify` recomputes the figures from the snapshot and compares the hash, the figures, the entitlement rows and the
  claimed inputs.
- Approval is refused unless the run reproduces.

**Lifecycle.** DRAFT → CALCULATED → PENDING_APPROVAL → APPROVED → COMPLETED, plus REJECTED and CANCELLED.
- The approver holds `settlement.approve` and is never the calculator. This is enforced by the service and by a CHECK constraint.
- Rejecting or cancelling a run deactivates its claims (active 1 → 0 only, enforced by a trigger), so the inputs can go into a new run.
- Changed inputs always mean a new run; a calculated run's figures and snapshot never change (trigger).
- A run becomes COMPLETED when every payout it owes is RECONCILED.

## 4. Refunds after settlement (D10, D29)

When a reversal is calculated:
- **The original revenue was settled but not yet paid out:** the reversal is carried into the next run and netted.
- **A payout of the original run is PAYMENT_PENDING / UNCONFIRMED / PAID / RECONCILED:** the reversal is not netted. Instead a recovery
  case (`payout_adjustments`, ADJ-) is opened, holding the amount, the reversal and the original run.

Recovery cases are closed manually (`payouts.reconcile`) with a written resolution. **There is no automatic clawback and no negative
payout.** The recovery policy is a business decision; see the open items.

## 5. Payouts (`payouts`, D20)

**Calculation.** `POST /payouts/from-settlement/{run}` (`payouts.calculate`) creates one payout per farmer. The amount is Σ of that
farmer's entitlement lines when it is > 0; it is never typed. A filtered unique index allows one open payout per run and farmer, and the
call is idempotent.

| Step | Who | Rule |
|---|---|---|
| CALCULATED → PENDING_APPROVAL | `payouts.calculate` | — |
| → APPROVED / REJECTED | `payouts.approve`, never the calculator | Requires the farmer's **primary VERIFIED Phase 2 bank account**. It is referenced (`bank_account_id`) with the last 4 digits only; the number, routing code and holder are never copied. |
| APPROVED → PAYMENT_PENDING ("Execute") | `payouts.execute`, never the approver or calculator | Re-checks the bank account under lock. If it is no longer the primary VERIFIED account, the payout goes **ON_HOLD** (`BANK_ACCOUNT_CHANGED`, committed and audited), and the request answers 409. |
| PAYMENT_PENDING / UNCONFIRMED → PAID | `payouts.execute` | MANUAL adapter: bank reference + PAYOUT_EVIDENCE PDF. PAID is **not** reconciled. |
| → FAILED | `payouts.execute` | With a reason. A FAILED payout is replaced by a new CALCULATED payout (`reissue`, `replaces_payout_id`); the failed record is never edited. |
| ON_HOLD → PENDING_APPROVAL | `payouts.calculate` | With a reason. The bank snapshot is cleared, and the next approver re-checks the account. |
| CALCULATED / PENDING_APPROVAL / ON_HOLD → CANCELLED | `payouts.calculate` | With a reason. |

**Adapters.**
- **MANUAL** (the only runtime adapter): the provider is never called, and every adapter method raises `ManualActionRequired`.
- **TEST** (`tests/payout_fixture.py`): injected into the service layer by tests only. It exercises timeout → UNCONFIRMED, status queries
  and provider-reported PAID / FAILED. It is never registered, never used in DEMO and never used in LIVE.

There is no public webhook.

`payout_transactions` is append-only and holds INITIATED, PAID, FAILED, UNCONFIRMED and STATUS_QUERIED entries.

## 6. Reconciliation (`payout_reconciliations`, append-only)

`payouts.reconcile` reconciles a PAID payout against a bank statement line with RECONCILIATION_EVIDENCE. The reconciler is never the
executor or the person who confirmed the payment.
- **MATCHED** when the amount and currency are equal **and** the reference is equal. After an earlier EXCEPTION, a reference mismatch (but
  never an amount mismatch) may be matched with a written resolution note.
- **EXCEPTION** otherwise.
- MATCHED → RECONCILED. When all owed payouts are RECONCILED, the run becomes COMPLETED.

## 7. Lineage, reporting and self-service

- `GET /payouts/{id}/lineage` and `GET /settlements/{id}/lineage` trace the chain: payout → the farmer's entitlement lines → run (hash) →
  revenue-share version (source reference) and allocation (basis) → revenue records → order / item / payment / 9B transfer / batch /
  period → costs.
- `GET /revenue/summary` reports recognized, reversed and net revenue per currency, approved costs by category, distributable / farmer /
  residual totals of approved runs, payouts by status, and open recovery cases.
- `GET /payouts/me` (`farmers.self`): the farmer's own payouts only, with amount, status, project, period, dates and bank last 4.

## 8. DEMO / TEST / LIVE

- **LIVE:** manual execution and reconciliation with evidence.
- **TEST:** the full lifecycle, plus the TEST adapter, runs in the rolled-back test database. Real concurrency runs on a database snapshot
  in `tests/test_finance_concurrency.py`.
- **DEMO:** no revenue can exist, because DEMO has no registry-issued credits. Every Phase 11 write on a DEMO project is refused, and the
  pages show the DEMO note, configuration-required or empty states. No fake revenue, cost, entitlement, payout or payment confirmation is
  created.

## 9. Open business items (configurable or reported — not invented)

- **Payee organization (D16 / D38).** Settlement includes only revenue where the seller is the project organization. Revenue sold by
  another credit holder (for example after a 9B transfer) is not settled to the project's farmers until an inter-organization policy is
  decided.
- **Payees (D22).** Only farmers are payees. Farmer groups or other beneficiaries need a decision.
- **Recovery policy (D29).** Recovery cases are resolved manually; there is no netting or clawback policy.
- **Rounding (D27).** The rounding mode is chosen per approved version; there is no platform default.
- **Tax / withholding (D31).** No tax is calculated or withheld. Payouts are gross entitlements.
- **Provider.** No payout provider is contracted; bulk files and provider integration are out of scope. Chargebacks are out of scope
  until a payment provider is contracted (D11).
- **Effective dates.** A revenue-share version must cover the whole monitoring period. A mid-period change of agreement needs a
  business decision on how to split the period.
