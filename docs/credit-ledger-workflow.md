# Credit ledger: ownership, reservation, transfer and retirement (Phase 9B)

Phase 9B tracks **who holds which registry-issued credits** and how they move. The only quantity that enters the ledger is a Phase 9A
**ISSUED** batch: the registry-stated quantity, vintage and serial ranges, confirmed by a second person. Calculated (Phase 7) and
VVB-stated (Phase 8B) quantities never enter the ledger and are not ledger states.

The ledger is **not a marketplace**. It has no price, order, checkout, payment or settlement (Phase 10), and no farmer payout (Phase 11).
Registries are external. The platform never transfers or retires a credit at a registry by itself: a REGISTRY transfer or a retirement is
recorded only with the registry's reference and the registry's evidence PDF.

## Locked decisions

| | Decision |
|---|---|
| X1 | RETIRED only with registry evidence: the registry retirement reference, a `RETIREMENT_CERTIFICATE` PDF, and the registry-stated serials where the registry supplies them. |
| X2 | BUYER organizations may receive, hold and request retirement of their own credits. Buyer KYC is Phase 10 (an open compliance risk, see below). |
| X3 | 9A serial ranges are never modified. Sub-ranges exist only when registry-stated or parser-derived; otherwise positions hold a *quantity within the range*. Serials are never fabricated. Positions never merge across batches or ranges. |
| X4 | A 9A correction or cancellation is refused with `LEDGER_ACTIVITY_EXISTS` unless every position of the batch is untouched (only the OPEN_INVENTORY entry; AVAILABLE; original owner). The untouched case closes the ledger with an explicit `ISSUANCE_ADJUSTMENT` entry. |
| X5 | Position states: AVAILABLE, RESERVED, TRANSFER_PENDING, RETIREMENT_PENDING, RETIRED. |
| D1 | Granularity: batch + registry serial range + whole quantity. |
| D2 | Initial owner: the organization that owns the batch's holding registry account. Opening is an explicit "Open in ledger" step under dual control. |
| D3 | Available is derived from open positions. It is never stored, and no request may set it (request schemas forbid extra fields). |
| D4 | Reservations: ACTIVE → CONSUMED / RELEASED / EXPIRED. Expiry is applied lazily on reads and writes, plus `POST /credits/reservations/expire-due`. There is no background worker. |
| D5–D7, D10 | Concurrency: locked reads, a guarded update, and a single transaction per movement (see below). |
| D6 | Transfers: INTERNAL (platform ownership) or REGISTRY (recorded at the registry). REQUESTED → COMPLETED / CANCELLED / REJECTED. A second person completes. REGISTRY completion needs the registry transfer reference and a `REGISTRY_TRANSFER_EVIDENCE` PDF. |
| D9 | Retirement: REQUESTED → RETIRED / REJECTED / CANCELLED. RETIRED is terminal: no un-retirement and no reversal. |
| D12, D20 | The registry adapter declares `transfer_credits`, `retire_credits` and `get_credit_inventory`. The MANUAL adapter raises `ManualActionRequired` for all three. Synchronisation is manual only. Reconciliation records a MISMATCH and never auto-fixes. |
| D13 | UTXO model: immutable positions plus append-only ledger entries. |
| D14 | A completed INTERNAL transfer can be undone only by a compensating REVERSAL entry under dual control, and only while its outputs are untouched. |
| D15 | Positions never merge across periods or batches. |
| D19 | DEMO has no credits ("DEMO — no registry-issued credits"). TEST uses fixtures only. LIVE opens only ISSUED 9A batches. |

## Model

```
credit_batches (9A, ISSUED) ──open (dual control)──▶ credit_ledger_entries (append-only, one per movement)
                                                        │ consumes (inputs)      │ creates (outputs)
                                                        ▼                        ▼
                                                  credit_positions (immutable UTXOs: batch · range · owner · state · quantity)
credit_openings · credit_reservations · credit_transfers · credit_retirements · credit_reversals  (workflow records; linked from entries)
```

- **Entry** (`LEDG-YYYY-NNNNNN`): `entry_type` is one of OPEN_INVENTORY, RESERVE, RESERVATION_RELEASE, RESERVATION_EXPIRE,
  TRANSFER_REQUEST, TRANSFER_COMPLETE, TRANSFER_CANCEL, RETIREMENT_REQUEST, RETIRE, RETIREMENT_CANCEL, REVERSAL or
  ISSUANCE_ADJUSTMENT. Each entry records the actor, the confirmer (database check: confirmer ≠ actor), the reason, and an optional
  idempotency `request_key` (filtered unique).
- **Position**: owner organization, holding registry account, state, status OPEN/CONSUMED, whole quantity, and the 9A serial range.
  An optional registry-stated or parser-derived sub-range is kept; when parsed, `end − start + 1 = quantity` is enforced by a database
  check. A position is never updated except to be consumed once, by exactly one entry.
- **Balances** per batch and owner are computed from OPEN positions by state, plus CONSUMED history for *Transferred out* and *Retired*.

## Posting protocol and database guards

Every movement runs in **one transaction**:

1. Insert the entry, unposted.
2. Lock the candidate OPEN positions with `WITH (UPDLOCK, HOLDLOCK, ROWLOCK)`, in deterministic order (range, created time, id).
3. Consume each input with a guarded `UPDATE … WHERE status='OPEN' AND consumed_by_entry_id IS NULL`, which must affect exactly one
   row. A shortfall raises `INSUFFICIENT_AVAILABLE` (409).
4. Create the outputs (the moved part plus the change), splitting parsed sub-ranges exactly.
5. Mark the entry posted. The `trg_credit_ledger_entries_guard` trigger then validates:
   - OPEN_INVENTORY: no inputs; outputs equal the batch's issued quantity; the batch is ISSUED.
   - ISSUANCE_ADJUSTMENT: consumes the inventory; no outputs; no open quantity remains.
   - Every other type: inputs = outputs > 0, and the batch's open quantity still equals its issued quantity.
   - Parsed sub-ranges never overlap.

Further triggers:

- Entries are append-only and are posted once.
- Positions may be inserted only into an unposted entry, are consumed once, are never deleted, and a RETIRED position stays terminal.
- Openings, reservations, transfers, retirements and reversals are immutable once in a final state.

The loser of a race gets 409 `INSUFFICIENT_AVAILABLE`. A `CREDIT_DOUBLE_SPEND_CONFLICT` audit is committed after the rollback.
Deadlocks (SQL Server error 1205) are retried up to three times.

Real concurrency was tested on separate database connections (threads behind a barrier, each with its own session, against a
committed world restored from a SQL Server database snapshot):

| Test | Contention | Outcome |
|---|---|---|
| A | Reservations of 600 + 600 against 1000 available | One succeeds, the other gets 409. Available 400, reserved 600. |
| B | Transfers of 600 + 600 against 1000 | One succeeds. Conservation holds. |
| C | Retirements of 80 + 80 against 100 | One succeeds. |
| D | A reservation racing a retirement for the same credits | Exactly one wins. |
| E | Fault injected after the positions moved, before posting | Full rollback: no entry, position or workflow row is left behind. |

## Workflows

| Step | Who | Effect |
|---|---|---|
| Open in ledger | `credits.manage` requests; `credits.confirm` (another person, custodian organization) confirms | OPEN_INVENTORY: one AVAILABLE position per serial range, owned by the holding account's organization |
| Reserve | `credits.manage` | AVAILABLE → RESERVED (purpose, optional `purpose_reference` and recipient, expiry) |
| Release / expire | `credits.manage` / lazy or `expire-due` | RESERVED → AVAILABLE |
| Request transfer | `credits.manage` | AVAILABLE (or a reservation) → TRANSFER_PENDING |
| Complete transfer | `credits.confirm`, not the requester; REGISTRY needs the reference + evidence PDF | Recipient receives AVAILABLE positions; the reservation, if any, becomes CONSUMED |
| Cancel / reject transfer | `credits.manage` / `credits.confirm` | TRANSFER_PENDING → AVAILABLE (sender) |
| Request retirement | `credits.manage`, or the holder with `credits.holder_retire` (own credits only) | AVAILABLE (or a reservation) → RETIREMENT_PENDING |
| Retire | `credits.confirm`, not the requester; registry reference + date + `RETIREMENT_CERTIFICATE` PDF (+ registry-stated serials) | RETIREMENT_PENDING → RETIRED (terminal) |
| Cancel / reject retirement | the requester's side / `credits.confirm` | RETIREMENT_PENDING → AVAILABLE |
| Reversal | `credits.manage` requests; `credits.confirm` applies or rejects | INTERNAL TRANSFER_COMPLETE only, while the recipient's outputs are untouched |
| Reconcile | `credits.manage` uploads a registry statement to the registry account, then states the registry's per-batch quantities | `registry_events` RECONCILED or MISMATCH. Nothing is auto-corrected. |

**Custodian organization.** This is the organization that owns the holding registry account; if there is none, the position owner is
used. A confirmer must hold `credits.confirm` in that organization and must not be the requester.

**Idempotency.** Every POST accepts `Idempotency-Key`. A repeated key with the same body replays the original result. A repeated key with
a different body gets 409 `IDEMPOTENCY_KEY_REUSED`. The UI sends one key per submission and keeps it across retries.

**Error codes:**
- `INSUFFICIENT_AVAILABLE`, `BATCH_NOT_ISSUED`, `OPENING_EXISTS`, `OPENING_NOT_REQUESTED`;
- `RESERVATION_NOT_ACTIVE`, `EXPIRY_IN_PAST`, `QUANTITY_REQUIRED`, `SERIAL_RANGE_NOT_FOUND`;
- `INVALID_RECIPIENT`, `SAME_PARTY`, `RECIPIENT_ACCOUNT_REQUIRED`;
- `TRANSFER_NOT_REQUESTED`, `RETIREMENT_NOT_REQUESTED`, `REGISTRY_EVIDENCE_REQUIRED`, `DUPLICATE_REGISTRY_REFERENCE`, `RETIRED_SERIALS_MISMATCH`;
- `REVERSAL_NOT_ALLOWED`, `REVERSAL_NOT_POSSIBLE`, `REVERSAL_EXISTS`, `REVERSAL_NOT_REQUESTED`;
- `SEPARATION_OF_DUTIES`, `LEDGER_ACTIVITY_EXISTS`, `IDEMPOTENCY_KEY_REUSED`.

## Holder view

`GET /credits/holdings` (`credits.holder_read`) returns only the caller organization's own positions. Each position is an allow-listed
projection:
- batch, issuance and registry identifiers;
- project code and name, period, vintage, methodology and standard;
- registry range or sub-range, state and quantity.

It never contains farmer, farm, location or GPS, KYC, bank, agreement, audit or other-holder data. A holder sees retirements of its own
organization, and the lineage of a retirement is cut at the batch for holders.

## Retirement lineage

`GET /credits/retirements/{id}/lineage` walks:

```
retirement → its ledger entries → the consumed positions → … → OPEN_INVENTORY → batch → (credits.read only) 9A batch lineage
```

The 9A batch lineage continues to the issuance, registry submission, VVB decision, calculation, farms and farmer codes.

## Audit events

| Area | Events |
|---|---|
| Opening | `CREDIT_INVENTORY_OPENED`, `CREDIT_INVENTORY_CONFIRMED`, `CREDIT_INVENTORY_OPENING_CANCELLED` |
| Reservation | `CREDIT_RESERVATION_CREATED`, `CREDIT_RESERVATION_RELEASED`, `CREDIT_RESERVATION_EXPIRED`, `CREDIT_RESERVATION_CONSUMED` |
| Transfer | `CREDIT_TRANSFER_REQUESTED`, `CREDIT_TRANSFER_COMPLETED`, `CREDIT_TRANSFER_CANCELLED`, `CREDIT_TRANSFER_REJECTED` |
| Retirement | `CREDIT_RETIREMENT_REQUESTED`, `CREDIT_RETIREMENT_RETIRED`, `CREDIT_RETIREMENT_CANCELLED`, `CREDIT_RETIREMENT_REJECTED` |
| Reversal | `CREDIT_LEDGER_REVERSAL_REQUESTED`, `CREDIT_LEDGER_REVERSAL`, `CREDIT_LEDGER_REVERSAL_REJECTED` |
| Other | `CREDIT_ISSUANCE_ADJUSTMENT`, `CREDIT_EVIDENCE_UPLOADED`, `CREDIT_DOUBLE_SPEND_CONFLICT`, `CREDIT_RECONCILIATION_PERFORMED`, `CREDIT_RECONCILIATION_MISMATCH` |

A cross-organization transfer is audited in both the sender's and the recipient's organization.

## UI

- **Credit ledger** (`/ledger`, `credits.read`):
  - an inventory table showing Issued (registry) / Available / Reserved / Pending transfer / Pending retirement / Transferred out / Retired;
  - Open in ledger and confirm/cancel opening;
  - batch detail with per-owner balances, positions and their entries;
  - reserve, transfer and retirement-request forms;
  - reservation, transfer, retirement and reversal lists with second-person actions (complete with a registry reference and evidence
    upload; retire with the certificate, reference, date and optional registry-stated serials);
  - entry and retirement-lineage views.
- **My credits** (`/holdings`, `credits.holder_read`): the holder's own positions and retirement requests.
- DEMO shows "DEMO — no registry-issued credits".
- There is no marketplace UI.

## Phase 10 integration

The Phase 10 marketplace drives the ledger without a second balance ([marketplace.md](marketplace.md)):
- placing an order calls `reserve_in_tx` per item inside the order's transaction;
- confirming a payment consumes those reservations through `request_transfer_in_tx`;
- delivery is `complete_transfer_in_tx` / `close_transfer_in_tx` behind `POST /orders/transfers/{id}/complete|reject` — the same locks,
  posting checks, triggers and second-person rule.

Reservations and transfers owned by an order are refused by the public release / transfer / retirement actions with 409 `ORDER_LINKED`, and
the ledger outputs show the order code. The public `/credits` endpoints behave exactly as before for everything else.

## Deferred

- Phase 10: buyer KYC and onboarding, marketplace, orders, pricing, payment and settlement.
- Phase 11: revenue and farmer payouts.
- A registry API integration and registry-specific serial parsers: none exists for any real registry.
- Scheduled reconciliation (synchronisation is manual).
- Fractional units (whole credits only).
