# Marketplace: buyers, listings, orders, payments and refunds (Phase 10)

Phase 10 is the commercial layer around credits the registry has already issued. The Phase 9B credit ledger stays the **only** record of
who owns which credits and how many are available ([credit-ledger-workflow.md](credit-ledger-workflow.md)).

The marketplace stores commercial facts only: listings, orders, payments and refunds. Every credit movement goes through 9B:
- placing an order creates a 9B reservation;
- confirming the payment turns it into a 9B transfer request;
- delivery is the 9B transfer completion, done by the custodian.

**What Phase 10 does not include:**
- fees, commissions, taxes or invoices (D9, D10);
- revenue, farmer share or payouts (Phase 11);
- workers, scheduled jobs or webhook queues (Phase 12);
- resale by buyers, buyer-to-third-party transfers, offers, bidding or discounts;
- a public catalogue (D25);
- a real payment gateway or registry API (no contract exists).

## Flow

```
ACTIVE listing (fixed price; nothing reserved)                                       [seller: listings.manage → listings.approve, ≠ creator]
  → T1 order PLACED: listings locked, items created, one 9B RESERVATION per item     [KYC-verified buyer: orders.place]
  → T2 payment PENDING_CONFIRMATION (manual, PDF evidence, exact total)              [buyer: payments.record]
  → T3 payment CONFIRMED, order PAID → TRANSFER_PENDING: reservations consumed into 9B TRANSFER requests   [seller finance: payments.confirm, ≠ recorder]
  → T4 9B transfer COMPLETED (custodian, ≠ requester), item DELIVERED, order COMPLETED   [credits.confirm]
  → the buyer holds AVAILABLE ledger positions (My credits) → optional 9B retirement with the registry's certificate
```

## Locked decisions and how they are implemented

| | Implementation |
|---|---|
| D1 KYC gate | The buyer organization must be KYC_VERIFIED to place an order, record a payment, have it confirmed, and receive a marketplace delivery. Enforced in the marketplace layer only; the general 9B recipient rule is unchanged (X2). |
| D2 Buyer onboarding | Organization-level `buyer_profiles`: DRAFT → KYC_SUBMITTED → KYC_VERIFIED, or KYC_RETURNED → resubmission. KYC_VERIFIED ⇄ SUSPENDED. A suspended buyer cannot order; holdings are never removed. No self-registration (the Platform Admin onboards organizations). |
| D3 Sellers | Only an ACTIVE PROJECT_DEVELOPER organization holding AVAILABLE 9B credits in the batch may list. No buyer resale. |
| D4 Quantity | `listed_quantity` is an immutable commercial cap. *Remaining* is derived: listed minus the quantity of committed order items (RESERVED, TRANSFER_PENDING, DELIVERED, FAILED), computed under the listing lock. *Available* shown to buyers is min(remaining, the seller's derived 9B AVAILABLE). No balance is stored anywhere. |
| D5 Expiry | `valid_until` with lazy expiry on reads and before relevant writes. No worker. |
| D6 Reservation | Reserved when the order is placed, never when listing. |
| D7, D8 Price | Fixed per registry-issued credit, `Numeric(19,4)`, one ISO-4217 currency. Decimals are limited to the currency's minor unit (known currencies only, never guessed). Frozen once approved; changing the price means close and re-list. No offers, discounts or tCO2e pricing. |
| D9, D10 | No fee of any kind and no tax. The deterministic ORDER_CONFIRMATION PDF says it is **not a tax invoice**. The invoice table and the INV sequence are deferred: tax and invoice rules are not defined. |
| D11 Order states | PLACED → PAID → TRANSFER_PENDING → COMPLETED. Also: PLACED → CANCELLED / EXPIRED; PAID / TRANSFER_PENDING → ATTENTION_REQUIRED → TRANSFER_PENDING or REFUND_PENDING; PAID → REFUND_PENDING → REFUNDED. COMPLETED, CANCELLED, EXPIRED and REFUNDED are final (trigger). |
| D12, D13 Items | Several items per order, all from one seller in one currency. Each item references one listing, one 9B batch and optionally one serial range. Each item has its own 9B reservation and later its own 9B transfer. Positions are never merged. |
| D14 Atomicity | 9B was refactored into composable functions: `reserve_in_tx`, `request_transfer_in_tx`, `complete_transfer_in_tx`, `close_transfer_in_tx`, `release_in_tx` and `expire_reservation_in_tx`. They use the same locking, guarded consumption, posting checks and triggers. The public 9B endpoints behave exactly as before. |
| D15, D16, D33 Payment | A `PaymentAdapter` Protocol defines `create_payment`, `get_status`, `refund` and `parse_event`. The only runtime adapter is MANUAL, which raises `ManualActionRequired`. The TEST adapter exists only in `tests/payment_fixture.py`. The seller is the payee, and its finance team confirms; the confirmer is never the recorder. `PAYMENT_PROVIDER=manual` (no mock provider exists). |
| D17 Events | Append-only `payment_events`, unique on (provider, external event id). A duplicate is a recorded no-op (`PAYMENT_EVENT_DUPLICATE`). There is no public webhook route; provider events reach the service only through an adapter. |
| D18 Failure | A failed or rejected payment leaves the order PLACED and the buyer may pay again before the deadline. An unpaid order past its deadline expires together with its 9B reservations. |
| D19 Refunds | Money only, with dual control (requester ≠ approver). See *Refunds* below. |
| D20 Transfer trigger | Confirming the payment *requests* the 9B transfer; it never completes it. The 9B second-person rule applies. |
| D21 | No per-order seller approval: listing approval plus custodian completion. |
| D22 Delivery kind | INTERNAL by default: beneficial ownership changes and the credits stay in the seller's registry account. REGISTRY is chosen at ordering with the buyer's registry account (`RECIPIENT_ACCOUNT_REQUIRED` otherwise); completion needs the registry reference and a PDF. |
| D23 | A rejected delivery returns the credits to the seller (9B) and the order needs attention, with no silent retry. Resolution is either "re-reserve and request the transfer again" (`POST /orders/{id}/retry-transfer`, seller) or a refund. |
| D24 | No owned, available or sold quantity column exists in any marketplace table (tested). |
| D25 | Authenticated catalogue only. Buyers see an allow-listed disclosure snapshot (SHA-256) and the seller's published PDFs, nothing else. |
| D26 | See *Concurrency*. |

## Interpretations (details the decisions did not fix)

- **A payment awaiting confirmation holds its order.** A PLACED order with a PENDING_CONFIRMATION payment is not expired automatically, so the seller's finance team can decide. Its 9B reservations still expire on their own (D18). If finance then confirms money that arrived after the reservation expired, the payment is CONFIRMED, the order goes PAID → ATTENTION_REQUIRED (`RESERVATION_EXPIRED`), and no transfer is created and no credit fabricated (T3). For the same reason, an order with a PENDING_CONFIRMATION or CONFIRMED payment cannot be cancelled (`PAYMENT_IN_PROGRESS`). An abandoned provider payment (PENDING) does not block cancellation; if it later reports success, it becomes UNMATCHED and a refund is required.
- **A rejected refund returns the order to attention** (REFUND_PENDING → ATTENTION_REQUIRED). Otherwise the order would be stuck.
- **A reviewer may reinstate a suspended buyer** (SUSPENDED → KYC_VERIFIED, recorded as REINSTATED in the KYC history).
- **Paused listings resume** through `POST /marketplace/listings/{id}/resume`. Withdrawing a draft or submitted listing gives CANCELLED; an approver may also decline one this way.
- **Refunds cover the whole payment.** Partial or item-level refunds are not implemented.
- **KYC documents are document-driven.** No legal document list is invented: submission needs at least one BUYER_KYC_DOCUMENT (PDF, restricted), and the reviewer decides.
- **LISTING_DOCUMENT** is an extra PDF category for documents a seller publishes on a listing.
- **Provider "succeeded" still needs the payee's confirmation.** It puts the payment in PENDING_CONFIRMATION; T3 always has a human confirmer (who is also the 9B transfer requester).

## Transaction boundaries and concurrency (D26)

Lock order everywhere: listing(s) by id → order → payment → reservation(s) → 9B positions, using UPDLOCK, HOLDLOCK and ROWLOCK. Each step
runs in the 9B transaction runner (`ledger_service.run`), which provides one transaction, deadlock retry, and a CREDIT_DOUBLE_SPEND_CONFLICT
audit for the losing request.

- **T1 place:**
  1. KYC gate; lazy expiry of due orders and reservations on the listings.
  2. Lock the listings; check status, expiry, environment, minimum and maximum, and remaining quantity (under the lock).
  3. Create the order and its items, plus one `reserve_in_tx` per item.
  4. Commit. Any failure rolls everything back: no partial order and no partial reservation.
- **T2 record:** lock the order; one open payment per order (also a filtered unique index).
- **T3 confirm:**
  1. Lock the order, the payment and each reservation.
  2. If every reservation is ACTIVE and not due, consume each into a `request_transfer_in_tx`: payment CONFIRMED, order PAID → TRANSFER_PENDING.
  3. Otherwise: payment CONFIRMED, order PAID → ATTENTION_REQUIRED, no transfer.
- **T4 complete / reject:** `POST /orders/transfers/{id}/complete|reject`.
  1. Lock the order and the transfer.
  2. Run `complete_transfer_in_tx` or `close_transfer_in_tx`.
  3. Update the item and the order.

  The public 9B release, transfer and retirement actions refuse order-linked reservations and transfers with 409 `ORDER_LINKED`
  (registered link guard). The 9B outputs show the order code, so the ledger UI routes these actions through the order.

**Real concurrency tests** (`tests/test_marketplace_concurrency.py`) run on separate connections against a committed world restored from a
database snapshot. Every scenario asserts no double spend, no negative inventory, conservation, no orphan reservation or transfer, no
duplicate payment, transfer or refund effect, and no over-committed listing.

| Scenario | Outcome |
|---|---|
| A. Two buyers order 100 each from a 100-credit listing | One succeeds; the other gets 409. |
| B. 60 + 60 against 100 | One succeeds; the other gets 409. |
| C. Two orders that both fit | Both succeed and nothing is lost (remaining is exact). |
| D. Payment confirmation races reservation expiry | Exactly one RESERVATION_EXPIRE entry; the order goes to ATTENTION_REQUIRED and no transfer is created. |
| E. The same provider event delivered twice | One APPLIED, one DUPLICATE; a single event row. |
| F. Payment event racing a cancellation | Either CANCELLED + UNMATCHED, or PLACED + PENDING_CONFIRMATION with the cancel refused. |
| G. Two cancellations | One succeeds; the other gets ORDER_NOT_CANCELLABLE. Exactly one release. |
| H. Refund racing delivery | The delivery always completes. The refund is either refused (in flight) or an after-delivery money-only refund. |
| I. Delivery failure racing resolution | Either a fresh REQUESTED transfer, or ORDER_NOT_IN_ATTENTION then ATTENTION_REQUIRED. |

## Payments

| Adapter | Lifecycle |
|---|---|
| MANUAL (runtime) | PENDING_CONFIRMATION → CONFIRMED / REJECTED. CONFIRMED → REFUNDED. |
| Provider (TEST only) | CREATED is committed with its key **before** the provider is called (outbox). → PENDING → PENDING_CONFIRMATION (event SUCCEEDED) / FAILED. A timeout gives UNCONFIRMED, which is resolved by `POST /payments/{id}/reconcile` (one status query on request; no job, no automatic retry). Success for a CANCELLED or EXPIRED order gives UNMATCHED → refund. |

The amount must equal the order total in the order currency (`PAYMENT_AMOUNT_MISMATCH`). Partial payment is not supported. Reconciling a
MANUAL payment answers `MANUAL_ACTION_REQUIRED`: people reconcile it by confirming or rejecting it with evidence.

## Refunds

Lifecycle: REQUESTED → APPROVED → COMPLETED / REJECTED. Requester ≠ approver.

| Case | Behaviour |
|---|---|
| Before delivery | Order PAID or ATTENTION_REQUIRED with nothing delivered or in delivery → REFUND_PENDING. On completion, the reservations are released, the items RELEASED and the order REFUNDED. The credits never left the seller. |
| UNMATCHED payment | Refunded; the order is untouched. |
| After delivery | Order COMPLETED. Money-only remediation (`after_transfer = true`): the credits stay with the buyer. Returning credits is a separate, manual 9B reversal, and only for an INTERNAL transfer whose outputs are untouched. **A REGISTRY transfer is never reversed.** |
| Other states | Refused with `REFUND_NOT_ALLOWED`: resolve the deliveries first. |

Completion needs the refund's payment reference plus a REFUND_EVIDENCE PDF (manual), or the provider's refund reference (TEST adapter).

## RBAC (D27, D28)

| Role | Phase 10 permissions |
|---|---|
| Buyer | marketplace.read, orders.place, orders.read, payments.record, buyers.kyc_submit (+ the 9B holder permissions) |
| Credit Manager | marketplace.read, listings.manage, orders.read, orders.manage |
| Project Manager | marketplace.read, orders.read |
| Finance / Payout Manager | marketplace.read, listings.approve, orders.read, payments.confirm, refunds.request, refunds.approve |
| Marketplace Compliance Officer (new, platform) | buyers.kyc_verify |
| QA Officer | none new (completes deliveries with the existing credits.confirm in the custodian organization) |
| VVB, laboratory, farmer and methodology roles | none |

Separation of duties:
- KYC submitter ≠ verifier;
- listing creator ≠ approver (also a database check);
- payment recorder ≠ confirmer (database check);
- refund requester ≠ approver (database check);
- transfer requester ≠ completer (the 9B database check).

Scoping is the usual 404 when out of scope and 403 when visible but forbidden.

## Documents (D29)

| Category | Attached to | Visible to | Format |
|---|---|---|---|
| BUYER_KYC_DOCUMENT | buyer profile | the buyer organization and the platform reviewer (RESTRICTED) | PDF |
| PAYMENT_EVIDENCE | order | buyer and seller | PDF |
| REFUND_EVIDENCE | refund | buyer and seller | PDF |
| ORDER_CONFIRMATION | order (generated, deterministic — same data, same bytes) | buyer and seller | PDF |
| LISTING_DOCUMENT | listing | anyone who can see the listing | PDF |

All marketplace documents are malware-scanned, immutable and resolver-checked.

## Audit and lineage

**Audit events:**
- **Buyer:** BUYER_PROFILE_CREATED / UPDATED, BUYER_KYC_SUBMITTED / VERIFIED / RETURNED, BUYER_SUSPENDED.
- **Listing:** MARKETPLACE_LISTING_CREATED / SUBMITTED / APPROVED / PAUSED / RESUMED / CLOSED / EXPIRED / CANCELLED.
- **Order:** ORDER_PLACED / CANCELLED / EXPIRED / PAID / ATTENTION_REQUIRED / RESOLVED / REFUND_PENDING / REFUNDED / COMPLETED, ORDER_DOCUMENT_ADDED, ORDER_CONFIRMATION_GENERATED.
- **Payment:** PAYMENT_RECORDED / CONFIRMED / REJECTED / EVENT_RECEIVED / EVENT_DUPLICATE / UNCONFIRMED / RECONCILED / UNMATCHED.
- **Refund:** REFUND_REQUESTED / APPROVED / COMPLETED / REJECTED.
- **9B (unchanged):** CREDIT_RESERVATION_*, CREDIT_TRANSFER_*, CREDIT_DOUBLE_SPEND_CONFLICT.
- Cross-organization events are recorded in both the buyer's and the seller's organization.

**Lineage:** `GET /orders/{id}/lineage` follows order → item → listing (disclosure SHA-256) → 9B reservation → 9B transfer → TRANSFER_COMPLETE
ledger entry → batch. For `credits.read` holders it links on to the existing 9A batch lineage (issuance → registry submission → VVB
decision → calculation → MRV → laboratory → farms). Buyers stop at the batch.

## DEMO, TEST and LIVE

| Environment | Behaviour |
|---|---|
| DEMO | No listing, order, payment or credit is seeded or possible. Marketplace, orders and listings show "DEMO — no registry-issued credits; nothing is listed", and ordering fails (`LISTING_NOT_FOUND`). The KYC workflow (no external claim) is demonstrated on DEMO-BUYER-D with `compliance@demo.carbon.example`. |
| TEST | The complete synthetic path: TEST registry issuance → 9B opening → listing → KYC → order → 9B reservation → manual and TEST-adapter payments → confirmation → 9B transfer → custodian completion → buyer holding → retirement. Also concurrency A–I and the triggers. |
| LIVE | Manual payments with evidence and seller-finance confirmation; manual registry transfers with evidence. No mock provider, fake registry, fake credits or fake payment success. |
