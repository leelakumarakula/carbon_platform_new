# Phase 11 — Decision lock (for human review)

> **No implementation.** This document prepares the Phase 11 decisions for sign-off. No application code, migration, schema, API, UI or
> database was changed. Source: [phase-11-discovery.md](phase-11-discovery.md) (D1–D42, C1–C14) and the master specification.
> Baseline commit `1a8b9b3`; latest migration `0015`.

## How to read this document

Every decision carries **exactly one** classification:

| Classification | Meaning | Count |
|---|---|---|
| **BUSINESS DECISION REQUIRED** | The specification does not define the rule (money, entitlement, legal, policy). Only the business can lock it. | 29 |
| **RECOMMENDATION — REQUIRES SIGN-OFF** | The discovery report already recommends an answer that affects business behaviour; a human must accept or replace it. | 8 |
| **TECHNICAL DECISION** | An engineering choice that follows from the existing platform architecture (Phases 1–10); recorded for review, no business rule involved. | 5 |

Rules applied:

- No percentage, amount, threshold, frequency, formula, FX rule, rounding rule, tax rule or recovery rule is proposed — none is defined
  by the source.
- `revenue × share_pct`, `revenue − costs = distributable revenue` and `farmer share = share_pct` are **not** assumed anywhere.
- Where the discovery report gave a recommendation it is reproduced (not changed) and labelled **RECOMMENDATION — REQUIRES SIGN-OFF**.
  Where the discovery report deferred to the business, the field says so.
- "Proposed locked wording" uses `⟨BUSINESS TO SELECT …⟩` placeholders wherever the business must choose.

---

## The 30 most important business decisions (index)

| # | Topic | Decision(s) | Classification |
|---|---|---|---|
| 1 | Revenue recognition trigger | D8 | RECOMMENDATION — REQUIRES SIGN-OFF |
| 2 | Farmer revenue-sharing model | D1, D2, D3 | BUSINESS DECISION REQUIRED |
| 3 | Can carbon-rights `share_pct` be used for revenue sharing? | D13 (with D1, C3) | BUSINESS DECISION REQUIRED |
| 4 | Allocation key: credit batch / order revenue → farms | D12, D14 | BUSINESS DECISION REQUIRED |
| 5 | Allocation key: farm → farmers / holders | D13 | BUSINESS DECISION REQUIRED |
| 6 | Project developer share | D3, D38 | BUSINESS DECISION REQUIRED |
| 7 | Fees and commissions | D4, D5 | BUSINESS DECISION REQUIRED |
| 8 | Project costs | D6, D7 | BUSINESS DECISION REQUIRED |
| 9 | Are costs deducted before the farmer share? | D3, D6 | BUSINESS DECISION REQUIRED |
| 10 | Settlement period | D19 | BUSINESS DECISION REQUIRED |
| 11 | Payout trigger | D18 | BUSINESS DECISION REQUIRED |
| 12 | Payout lifecycle | D20 | BUSINESS DECISION REQUIRED (OPEN DECISION — D20) |
| 13 | Refund after payout | D29, D30 | BUSINESS DECISION REQUIRED |
| 14 | Chargeback after payout | D11, D29 | BUSINESS DECISION REQUIRED |
| 15 | Bank-account change during payout processing | D23 | BUSINESS DECISION REQUIRED |
| 16 | Payout currency | D26 | RECOMMENDATION — REQUIRES SIGN-OFF |
| 17 | FX treatment | D26 | RECOMMENDATION — REQUIRES SIGN-OFF |
| 18 | Rounding | D27 | BUSINESS DECISION REQUIRED |
| 19 | Tax / withholding boundary | D31, D32 | BUSINESS DECISION REQUIRED |
| 20 | Payout provider | D24 (provider choice OPEN) | RECOMMENDATION — REQUIRES SIGN-OFF |
| 21 | Manual vs automated payout | D24 | RECOMMENDATION — REQUIRES SIGN-OFF |
| 22 | Payout reconciliation | D21, D24 | BUSINESS DECISION REQUIRED (D21) |
| 23 | Payout adjustments | D29, D37 | BUSINESS DECISION REQUIRED (D29) |
| 24 | Multiple farmers on one farm | D13 | BUSINESS DECISION REQUIRED |
| 25 | Multiple farms in one credit batch | D12, D14 | BUSINESS DECISION REQUIRED |
| 26 | Multiple projects / participants / organizations | D16, D22, D38 | BUSINESS DECISION REQUIRED |
| 27 | Agreement termination | D15 | BUSINESS DECISION REQUIRED |
| 28 | Historical entitlement immutability | D37 | TECHNICAL DECISION |
| 29 | Revenue reversal | D10 | BUSINESS DECISION REQUIRED |
| 30 | Farmer visibility | D33, D40 | RECOMMENDATION — REQUIRES SIGN-OFF |

---

## D1–D42

### D1

Title: Source of farmer economic entitlement

Current requirement:
- §4.16 "calculate farmer share according to agreement"; §26 "Use project agreement / configured revenue-share rules"; §46 #38 "Farmer
  payout is calculated according to configured agreement"; §7.14 lists `farmer_revenue_shares`.
- Repo: `farmer_agreements.terms_summary` is free text (plus a signed PDF); `project_carbon_rights.share_pct` is a share of carbon rights
  for a farm's participation; no structured revenue entitlement exists.

Problem:
- Nothing in the platform can compute what a farmer is owed without inventing terms.

Options:
- Option A — a new, versioned, approval-controlled revenue-share configuration per project whose versions reference the signed farmer
  agreements / carbon-rights records they implement.
- Option B — structured economic terms added to each `farmer_agreements` record (agreement-level entitlement).
- Option C — `project_carbon_rights.share_pct` declared by the business to be the economic share (see D13 / C3).

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: "a new versioned, second-person-approved revenue-share configuration per project, whose versions
  reference the signed farmer agreements and carbon-rights records it implements … Keep `share_pct` as carbon-rights evidence only, unless
  the business confirms it is the economic share."

Impact:
- Farmer entitlement, project economics, payout: defines who is owed what. Database: `revenue_share_rules` / versions (Option A) or new
  agreement columns (Option B). API: sharing-rule endpoints. UI: sharing-rule screens. Audit: SHARING_RULE_* events.

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "Farmer economic entitlement is sourced exclusively from ⟨BUSINESS TO SELECT: A / B / C⟩. No payout is calculated from any other
  source or from a value typed at payout time."

### D2

Title: Revenue-share rule configuration model

Current requirement:
- §26 "configured revenue-share rules"; "Do not calculate farmer payout directly from a UI-entered number." Repo: versioned,
  second-person-approved configuration exists for methodologies (Phase 4) — a reusable pattern.

Problem:
- Any configured rule is entered by someone; it must be controlled (C4). Scope (project / agreement / farm) is undefined.

Options:
- Option A — per project, versioned, second-person approval, immutable once approved.
- Option B — per agreement.
- Option C — per farm participation.

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: "per project, versioned, second-person approval."

Impact:
- Farmer entitlement; Database (rule + version tables); API (sharing-rules, submit / approve); UI; Audit (rule lifecycle).

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "Revenue-share rules are configured per ⟨BUSINESS TO SELECT: project / agreement / farm participation⟩, versioned, approved by a person
  other than the author, and immutable once approved; a change is a new version."

### D3

Title: Calculation base for the farmer share (and the project developer share)

Current requirement:
- §26 ordering: Revenue → Project Costs / Fees → Farmer Share. No rule states a deduction. Four interpretations documented (I1 net of
  fees and costs; I2 share of gross; I3 per-credit fixed amount; I4 carbon-rights share of a farm's portion).

Problem:
- The base determines every amount; it also defines the project developer's residual share.

Options:
- Option A — gross revenue (I2).
- Option B — revenue net of approved fees and costs (I1).
- Option C — per-credit fixed amount (I3), or the share_pct-based interpretation (I4) if D13 confirms it.

Discovery recommendation:
- None — the discovery report states "business chooses gross or net".

Impact:
- Revenue, farmer entitlement, project economics (developer share), payout; Database (settlement inputs); tests (calculation).

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "The farmer share is calculated on ⟨BUSINESS TO SELECT: gross revenue / net revenue as defined in D6 / per-credit amount / other⟩. The
  project developer receives ⟨BUSINESS TO SELECT⟩."

### D4

Title: Platform / seller / buyer fee and commission

Current requirement:
- Spec: none defined. Phase 10 D9 locked: no marketplace, buyer or seller fee and no platform commission; D16: the seller is the payee
  and the platform collects no marketplace revenue.

Problem:
- Any fee would change either the order total (locked in Phase 10) or require an invoice / deduction mechanism (C6).

Options:
- Option A — no fee and no commission in Phase 11.
- Option B — a fee recorded as a deduction owed (payer, receiver, base, timing to be defined by the business).
- Option C — a fee charged outside the platform (out of scope).

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: "none unless supplied" / "No fee and no commission in the first Phase 11 cut unless the business
  supplies them."

Impact:
- Revenue, project economics, payout; Database (fee records only if B); API; UI; Audit.

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "Phase 11 applies ⟨BUSINESS TO SELECT: no fee or commission / the fee schedule supplied in document ___⟩. No fee value is defaulted by
  the platform."

### D5

Title: Third-party fees (registry, VVB, payment processing)

Current requirement:
- Spec: none. These are paid to external parties; no provider exists for payment processing.

Problem:
- Whether and how such amounts influence distributions is undefined.

Options:
- Option A — treat them as project costs under D6.
- Option B — ignore them in Phase 11 (outside the platform).

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: "treat as project costs if D6".

Impact:
- Project economics, farmer entitlement (only if costs are deducted); Database (`project_costs`).

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "Registry, VVB and payment-processing fees are ⟨BUSINESS TO SELECT: recorded as project costs under D6 / not recorded in Phase 11⟩."

### D6

Title: Project costs — tracked, and deducted before the farmer share?

Current requirement:
- §7.14 `project_costs`; §4.16 "record fees/costs"; §26 places costs before the farmer share. No categories, evidence rule or deduction
  rule are defined (C5).

Problem:
- Deducting costs changes the farmer share; tracking costs without a rule is data with no effect.

Options:
- Option A — costs not tracked in Phase 11.
- Option B — costs tracked with evidence, informational only (not deducted).
- Option C — costs tracked and deducted according to a business-defined rule and categories.

Discovery recommendation:
- None — "business defines categories + deduction rule".

Impact:
- Project economics, farmer entitlement, payout; Database (`project_costs`); API (costs); UI; Audit (PROJECT_COST_*).

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "Project costs are ⟨BUSINESS TO SELECT: not tracked / tracked for information only / tracked and deducted as follows: ___⟩. Cost
  categories: ⟨BUSINESS TO SELECT⟩."

### D7

Title: Cost granularity

Current requirement:
- Only project and monitoring period are reachable from a credit batch; no farm- or credit-level cost key exists.

Problem:
- If costs are deducted (D6 C), the level at which they apply must be fixed.

Options:
- Option A — project + monitoring period.
- Option B — project only.
- Option C — another level defined by the business.

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: "project + monitoring period" (only reachable keys).

Impact:
- Project economics; Database (`project_costs` keys); settlement calculation.

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "Costs, if recorded, are recorded per ⟨BUSINESS TO SELECT: project and monitoring period / project / other⟩."

### D8

Title: Revenue recognition trigger

Current requirement:
- Spec: undefined. Repo facts available: payment CONFIRMED (`payments.confirmed_at`), order item DELIVERED / 9B transfer COMPLETED
  (`credit_transfers.completed_at`), order COMPLETED.

Problem:
- Determines when money becomes distributable and how refunds interact.

Options:
- Option A — when the order item's 9B delivery completes (payment already confirmed).
- Option B — when the payment is confirmed.
- Option C — when the whole order is COMPLETED.

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: "order-item delivery completion (T4)" — "money received + credits transferred", recorded in the T4
  transaction; INTERNAL and REGISTRY treated the same.

Impact:
- Revenue, payout timing; Database (`revenue_records`); API (revenue); concurrency (race 5); Audit (REVENUE_RECOGNIZED).

Decision classification:
- RECOMMENDATION — REQUIRES SIGN-OFF

Proposed locked wording:
- "Revenue is recognized per order item when ⟨SIGN-OFF: its 9B delivery completes⟩, from the immutable Phase 10 records; it is never
  entered manually."

### D9

Title: Recognition granularity

Current requirement:
- An order holds items of possibly several batches (one seller, one currency); each item is one batch → one project / period.

Problem:
- Recognition must keep batch lineage.

Options:
- Option A — per order item.
- Option B — per order.

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: "per order item" (keeps batch lineage).

Impact:
- Database (`revenue_records.order_item_id`); lineage.

Decision classification:
- TECHNICAL DECISION

Proposed locked wording:
- "Revenue records are created per order item and reference the order item, order, payment, 9B transfer and credit batch."

### D10

Title: Revenue reversal after refund

Current requirement:
- Phase 10 refunds are whole-payment, money only (`after_transfer` flag); credits never move with a refund.

Problem:
- Recognized revenue may later be refunded, before or after delivery.

Options:
- Option A — a reversal record against the revenue record (never an edit); farmer entitlements of unpaid runs follow the reversal.
- Option B — refunds after delivery do not reverse farmer-relevant revenue.
- Option C — case-by-case manual remediation.

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: "reversal record" (immutability); the entitlement policy remains open.

Impact:
- Revenue, farmer entitlement, payout; Database (`revenue_records` reversal rows); Audit (REVENUE_REVERSED).

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "A completed refund of a recognized order item ⟨BUSINESS TO SELECT: creates a reversal revenue record that is carried into the next
  settlement run / does not affect farmer revenue / is remediated manually⟩. Revenue records are never edited."

### D11

Title: Chargebacks

Current requirement:
- Not modelled (no payment provider; Phase 10 is manual payment only).

Problem:
- A chargeback after delivery / payout has no handling.

Options:
- Option A — not supported until a provider exists; handled as manual remediation.
- Option B — treated like a refund (D10 / D29).

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: "not supported until a provider exists".

Impact:
- Revenue, payout; Database (none or reversal rows).

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "Chargebacks are ⟨BUSINESS TO SELECT: out of scope until a payment provider is contracted / handled as refunds under D10 and D29⟩."

### D12

Title: Allocation key — credit batch / order revenue → farms

Current requirement:
- No authoritative key: issuance is per monitoring period / batch; farm-level calculation allocation was deferred in Phase 7; farm-level
  calculation outputs are calculated tCO2e, not credits (§1.11, rule 12; C9). Acreage, equal split or quantity split are not required
  anywhere.

Problem:
- A batch's revenue cannot be split across farms without an approved key.

Options:
- Option A — an agreement-defined fixed share per farm / farmer.
- Option B — an approved, versioned per-period allocation table recorded by the project (second-person approved).
- Option C — a methodology-provided, VVB-accepted farm-level contribution (requires a methodology module).

Discovery recommendation:
- None — "business supplies (agreement share / approved allocation table)".

Impact:
- Farmer entitlement, payout; Database (rules / entitlements); settlement calculation; tests (allocation).

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "Revenue of a credit batch is allocated to farms by ⟨BUSINESS TO SELECT: A / B / C⟩. Equal, acreage-based or credit-quantity-based
  allocation is not used unless selected here."

### D13

Title: Multiple holders per farm — economic meaning of carbon-rights `share_pct`

Current requirement:
- `project_carbon_rights` allows several holders (FARMER, LANDOWNER, ORGANIZATION, FARMER_GROUP, OTHER) with `share_pct` (0 < x ≤ 100),
  evidenced by an agreement / document / reference, verified by a second person. Its stated meaning is a share of carbon rights.

Problem:
- Whether `share_pct` may be used as an economic (revenue) share, and whether shares per farm must sum to 100, is undefined (C3).

Options:
- Option A — `share_pct` is declared an economic share for allocation within a farm.
- Option B — `share_pct` remains carbon-rights evidence only; within-farm economic shares come from the D1 configuration.
- Option C — another within-farm rule supplied by the business.

Discovery recommendation:
- None beyond D1 ("keep `share_pct` as carbon-rights evidence only, unless the business confirms it is the economic share").

Impact:
- Farmer entitlement (multi-holder farms), payout; Database (rights / rules); validation (sum rule).

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "`project_carbon_rights.share_pct` ⟨BUSINESS TO SELECT: is / is not⟩ an economic share. Within a farm, revenue is split among holders
  by ⟨BUSINESS TO SELECT⟩; shares ⟨must / need not⟩ sum to 100."

### D14

Title: Time eligibility — which farms share a batch's revenue

Current requirement:
- Available dates: `project_farms.participation_start/end`; carbon-rights `effective_from/to` and status; the batch's monitoring period.

Problem:
- Farms join / leave projects; the eligible set per batch must be fixed.

Options:
- Option A — farms with ACTIVE participation and ACTIVE, VERIFIED carbon-rights records during the batch's monitoring period.
- Option B — farms eligible at the time of sale.
- Option C — another rule.

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: "ACTIVE participation + VERIFIED rights during the batch's monitoring period" (the only dates
  available).

Impact:
- Farmer entitlement; settlement calculation; tests (date edge cases).

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "A farm participates in a batch's revenue if ⟨BUSINESS TO SELECT: A / B / C⟩."

### D15

Title: Agreement termination / carbon-rights transfer

Current requirement:
- Agreements DRAFT / SIGNED / TERMINATED / EXPIRED / VOID; carbon-rights records ACTIVE / ENDED / VOID with effective dates. No economic
  consequence defined.

Problem:
- Entitlements accrued before termination vs revenue from later sales of earlier credits.

Options:
- Option A — entitlement follows eligibility for the credits' monitoring period (D14), regardless of later termination.
- Option B — termination ends all future entitlement, including from earlier periods' credits.
- Option C — per agreement terms (manual).

Discovery recommendation:
- None — "accrued vs future entitlement rule" left to the business.

Impact:
- Farmer entitlement, payout; settlement calculation.

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "After agreement termination or rights transfer, entitlement to revenue from credits of earlier periods ⟨BUSINESS TO SELECT⟩."

### D16

Title: Secondary sales

Current requirement:
- Phase 10 lets any PROJECT_DEVELOPER holding AVAILABLE credits (including credits received by a 9B INTERNAL transfer) sell them; the
  seller may differ from the project organization (C7).

Problem:
- Whether the original project's farmers share in such sales is undefined.

Options:
- Option A — only sales by the project's own organization create farmer-relevant revenue.
- Option B — every sale of the project's credits creates farmer-relevant revenue.
- Option C — secondary sales excluded and to be prevented by policy.

Discovery recommendation:
- None — "business decides farmer participation".

Impact:
- Revenue, farmer entitlement, organization ownership (D38).

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "Revenue from sales by an organization other than the project organization ⟨BUSINESS TO SELECT⟩."

### D17

Title: Entitlement creation

Current requirement:
- Undefined.

Problem:
- Entitlements must be reproducible and immutable.

Options:
- Option A — entitlements are created only inside an approved settlement run.
- Option B — entitlements created continuously as revenue is recognized.

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: "in an approved settlement run".

Impact:
- Farmer entitlement, payout; Database (`farmer_entitlements` per run).

Decision classification:
- RECOMMENDATION — REQUIRES SIGN-OFF

Proposed locked wording:
- "Farmer entitlements are created only by a settlement run and become binding when the run is approved."

### D18

Title: Payout trigger and aggregation

Current requirement:
- Undefined; no scheduler in Phase 11 (Phase 12 boundary).

Problem:
- Defines when money becomes payable and how many payouts a farmer receives.

Options:
- Option A — manually triggered settlement run; one payout per payee per run.
- Option B — one payout per revenue record.
- Option C — another aggregation (e.g. per project per payee).

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: "manual run; one payout per payee per run".

Impact:
- Payout; Database (`payouts`); concurrency (races 1, 6).

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "A payout becomes payable when ⟨BUSINESS TO SELECT⟩; payouts are aggregated ⟨BUSINESS TO SELECT⟩."

### D19

Title: Settlement period / cycle

Current requirement:
- Undefined; no accounting or settlement period exists; monitoring / crediting periods are carbon concepts.

Problem:
- Frequency cannot be assumed (no monthly / quarterly rule).

Options:
- Option A — no fixed cycle in Phase 11; runs are started manually; cycle defined later.
- Option B — a business-defined cycle (frequency supplied by the business).

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: "none in Phase 11 (manual); cycle = business".

Impact:
- Payout timing; Phase 12 scheduling.

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "Settlement cycle: ⟨BUSINESS TO SELECT: none (manual runs) / ___⟩. Scheduled runs are Phase 12."

### D20

Title: Payout lifecycle

Current requirement:
- §35 lists PAYOUT_APPROVED; §33 notifies "Payout completed". No states are defined.

Problem:
- Every workflow needs explicit states (§1.20).

Options:
- Option A — the candidate lifecycle (see "Proposed payout lifecycle").
- Option B — a reduced lifecycle (e.g. without PENDING_APPROVAL or ON_HOLD).
- Option C — a business-supplied lifecycle.

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: the candidate lifecycle in discovery §10.

Impact:
- Payout; Database (`payouts` status, triggers); API; UI (queue); Audit.

Decision classification:
- BUSINESS DECISION REQUIRED — **OPEN DECISION — D20**

Proposed locked wording:
- "The payout lifecycle is ⟨BUSINESS TO SELECT: the candidate lifecycle, with / without ON_HOLD / other⟩."

### D21

Title: Separation of duties — calculator / approver / executor / reconciler

Current requirement:
- §4.16 gives calculate, approve, track bank status and reconcile to one role (C2); the platform enforces SoD per person.

Problem:
- Who may do which step, and whether the reconciler must differ from the executor.

Options:
- Option A — calculator ≠ approver ≠ executor; reconciler ≠ executor.
- Option B — calculator ≠ approver ≠ executor; reconciler unrestricted.
- Option C — calculator ≠ approver only.

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: "per-person: calculator ≠ approver ≠ executor; reconciler TBD".

Impact:
- Payout; Database (CHECK constraints); API; tests (SoD).

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "Calculator ≠ approver ≠ executor (per person). Reconciler ⟨BUSINESS TO SELECT: must / need not⟩ differ from the executor."

### D22

Title: Payee types

Current requirement:
- Carbon-rights holders may be farmers, landowners, organizations, farmer groups or others; bank accounts exist only for farmers (C10).

Problem:
- Non-farmer holders cannot be paid without a destination model.

Options:
- Option A — farmers only in Phase 11.
- Option B — farmers and organizations / groups / landowners (requires a new bank-destination model).

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: "farmers only in first cut".

Impact:
- Payout; Database (destination model if B); multi-participant handling.

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "Phase 11 pays ⟨BUSINESS TO SELECT: farmers only / farmers and ___⟩. Entitlements of other holder types are ⟨recorded but not paid /
  not created⟩."

### D23

Title: Bank-account requirement and change during payout processing

Current requirement:
- Phase 2: accounts PENDING_VERIFICATION → VERIFIED (second person) / REJECTED → INACTIVE; encrypted number; last4 + keyed hash.

Problem:
- Paying unverified or freshly changed accounts is a fraud risk.

Options:
- Option A — VERIFIED account required; an account change after approval puts the payout ON_HOLD and requires re-approval.
- Option B — VERIFIED required; the account is snapshotted at approval and changes do not affect that payout.
- Option C — another rule.

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: "VERIFIED required; change → hold + re-approval".

Impact:
- Payout; Database (account snapshot, hold); concurrency (race 8); UI (queue).

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "Payouts are made only to a VERIFIED farmer bank account ⟨SIGN-OFF⟩. A bank-account change during processing ⟨BUSINESS TO SELECT⟩."

### D24

Title: Payout adapter, provider and manual vs automated payout

Current requirement:
- §42 lists PaymentProvider but no payout provider; §26 "Bank / Payment Provider"; §49 only `PAYMENT_PROVIDER` (C8); §1.13 requires a
  controlled manual workflow when no API exists. No provider contract exists.

Problem:
- Execution must not fake success.

Options:
- Option A — ManualPayoutAdapter only (evidence-backed) + TEST-only adapter; no webhook.
- Option B — a contracted provider (none exists — not available).

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: "ManualPayoutAdapter + TEST adapter; no webhook". Provider choice: **OPEN** (none specified).

Impact:
- Payout execution and reconciliation; Database (`payout_transactions`, `payout_events`); API (execute, reconcile).

Decision classification:
- RECOMMENDATION — REQUIRES SIGN-OFF

Proposed locked wording:
- "LIVE payouts are executed manually through ManualPayoutAdapter with evidence and second-person reconciliation; a TEST-only adapter is
  used in tests; no provider is integrated and no public webhook exists until a provider is contracted."

### D25

Title: Documents

Current requirement:
- None defined for payouts; existing pattern: PDF, malware scan, immutable versions, resolver, SHA-256.

Problem:
- Which documents are needed (and legally meaningful) is undefined.

Options:
- Option A — remittance proof (executor), bank / settlement statement (reconciliation), farmer payout statement ("not a tax document").
- Option B — remittance proof only.
- Option C — a business-supplied list.

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: "remittance proof, statement, farmer statement (not a tax doc)".

Impact:
- Database (document categories); API (documents); UI; Audit.

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "Phase 11 documents: ⟨BUSINESS TO SELECT⟩. None is presented as a tax document unless D31 / D32 define it."

### D26

Title: Payout currency and FX

Current requirement:
- Phase 10: one ISO-4217 currency per order, minor-unit validation, no FX.

Problem:
- Revenue may be in several currencies across orders.

Options:
- Option A — one currency per settlement run = the revenue currency; no FX.
- Option B — conversion with exchange-rate snapshots (rule to be supplied).

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: "one currency per run = revenue currency; no FX".

Impact:
- Payout; Database (run currency); settlement calculation.

Decision classification:
- RECOMMENDATION — REQUIRES SIGN-OFF

Proposed locked wording:
- "Each settlement run and its payouts use one currency equal to the currency of the revenue records it includes; no FX conversion is
  performed ⟨SIGN-OFF⟩."

### D27

Title: Rounding and remainder

Current requirement:
- Minor-unit validation exists (`CURRENCY_EXPONENTS`); no rounding rule.

Problem:
- Splits produce fractions; remainders must not leak or appear.

Options:
- Option A — round each line to the currency's minor unit with a business-defined remainder rule.
- Option B — another rounding method supplied by the business.

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: "round per line to minor unit; remainder rule to decide".

Impact:
- Farmer entitlement, payout; settlement calculation; tests (rounding).

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "Amounts are rounded ⟨BUSINESS TO SELECT: method⟩ to the currency's minor unit at ⟨BUSINESS TO SELECT: line / payout⟩ level; the
  remainder goes to ⟨BUSINESS TO SELECT⟩."

### D28

Title: Minimum payout threshold

Current requirement:
- Undefined.

Problem:
- Very small payouts may be undesirable; carrying amounts forward needs a rule.

Options:
- Option A — no threshold.
- Option B — a business-defined threshold with carry-forward.

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: "none unless defined".

Impact:
- Payout; settlement calculation.

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "Minimum payout: ⟨BUSINESS TO SELECT: none / ___ with carry-forward⟩."

### D29

Title: Refund (or chargeback) after payout — recovery and adjustments

Current requirement:
- No recovery policy anywhere; Phase 10 refunds after delivery are money only.

Problem:
- Money already paid to farmers may relate to refunded revenue.

Options:
- Option A — negative adjustment carried into the payee's next settlement run.
- Option B — manual remediation outside the platform; record only.
- Option C — no effect on paid farmers (developer bears the loss).

Discovery recommendation:
- None — "business: carry-forward negative adjustment vs manual remediation".

Impact:
- Farmer entitlement, payout, project economics; Database (`payout_adjustments`); concurrency (race 4); Audit.

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "When revenue already paid out is reversed, ⟨BUSINESS TO SELECT: A / B / C⟩. Paid payouts are never edited."

### D30

Title: Holdback / reserve

Current requirement:
- Undefined.

Problem:
- A reserve would protect against refunds after payout but delays farmer money.

Options:
- Option A — no holdback.
- Option B — a business-defined holdback (amount / duration supplied by the business).

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: "none unless defined".

Impact:
- Payout timing, farmer entitlement; settlement calculation.

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "Holdback: ⟨BUSINESS TO SELECT: none / ___⟩."

### D31

Title: Tax / withholding boundary

Current requirement:
- Not specified (GST, TDS, withholding, income tax); Phase 10 deferred tax.

Problem:
- Withholding may be legally required in some jurisdictions; no rule exists in the platform.

Options:
- Option A — external boundary: no tax computed; payout statements state they are not tax documents.
- Option B — business / legal supplies jurisdiction rules for implementation.

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: "external boundary; no rates encoded".

Impact:
- Payout amounts (if withholding), documents, compliance.

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "Tax and withholding are ⟨BUSINESS TO SELECT: outside the platform in Phase 11 / implemented per rules in document ___⟩."

### D32

Title: Invoices / tax documents

Current requirement:
- §7.13 names `invoices` without rules; Phase 10 deferred invoices.

Problem:
- Issuing an invoice without tax rules would misrepresent a legal document.

Options:
- Option A — deferred.
- Option B — implemented once D31 supplies rules.

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: "deferred".

Impact:
- Documents; Database (no invoice table in Phase 11 unless B).

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "Invoices and tax documents are ⟨BUSINESS TO SELECT: deferred / required per D31⟩."

### D33

Title: Visibility / data minimization

Current requirement:
- `farmers.self` (own record only); organization scoping 404 / 403; rule 13 (no private farmer data to buyers); §31.

Problem:
- Payout data is personal and financial.

Options:
- Option A — farmer: own entitlements / payouts only; project organization: its own farmers; platform: none by default.
- Option B — wider internal visibility.

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: "farmer: own only; project org: own farmers; platform: none".

Impact:
- API scoping; UI; tests (isolation).

Decision classification:
- RECOMMENDATION — REQUIRES SIGN-OFF

Proposed locked wording:
- "A farmer sees only their own entitlements and payouts; a project organization sees only its own farmers' records; no other
  organization or the platform sees them by default; bank numbers are shown as last 4 only."

### D34

Title: RBAC (permissions and role grants)

Current requirement:
- §4.16 Finance / Payout Manager duties; FINANCE_MANAGER role exists; who approves sharing rules is undefined.

Problem:
- Least privilege and SoD need explicit grants.

Options:
- Option A — the minimum set in "Proposed permissions", granted to FINANCE_MANAGER (several persons for SoD).
- Option B — sharing-rule approval granted to PROJECT_MANAGER + FINANCE_MANAGER.
- Option C — a new payout-specific role.

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: "minimum set in §19"; role for sharing-rule approval left open.

Impact:
- Permissions catalog, roles, API dependencies, navigation, tests (RBAC).

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "Phase 11 adds ⟨SIGN-OFF: the permissions listed under 'Proposed permissions'⟩, granted to ⟨BUSINESS TO SELECT⟩."

### D35

Title: DEMO behaviour

Current requirement:
- Established honest-DEMO rule (no registry-issued credits, no orders) vs §43 "1 payout" (C1) and §46 #39 / §54 (C12).

Problem:
- A DEMO payout cannot be produced honestly.

Options:
- Option A — no financial records in DEMO; honest DEMO note.
- Option B — seed illustrative DEMO payouts (would contradict §1.13 / §1.19 and the Phase 9–10 decisions).

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: "no financial records in DEMO".

Impact:
- Seed, UI (DEMO note), E2E.

Decision classification:
- RECOMMENDATION — REQUIRES SIGN-OFF

Proposed locked wording:
- "DEMO contains no revenue, entitlement, payout, bank transfer or earnings; Phase 11 screens show an honest DEMO note."

### D36

Title: TEST behaviour

Current requirement:
- TEST-only fixtures exist for issuance (9A), ledger (9B) and payments (Phase 10).

Problem:
- The financial chain must be testable end to end without fake LIVE data.

Options:
- Option A — full synthetic chain (completed orders → revenue → run with a TEST-only approved rule → payouts → TEST adapter →
  reconciliation) + real concurrency races.

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: "full synthetic path + races".

Impact:
- Tests only.

Decision classification:
- TECHNICAL DECISION

Proposed locked wording:
- "TEST covers the full synthetic financial chain and the races of 'Concurrency' using TEST-only fixtures injected into the service layer."

### D37

Title: Immutability and corrections (historical entitlement immutability)

Current requirement:
- Platform patterns: append-only events, immutable approved versions, superseding runs (Phases 4, 7, 9B, 10).

Problem:
- Financial history must never be rewritten.

Options:
- Option A — revenue records, entitlements, approved rule versions, payout transactions / events / reconciliations immutable; settlement
  runs superseded, never edited; corrections by adjustment / reversal records.

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: "runs immutable, supersede; adjustments not edits".

Impact:
- Database (triggers); API (no edit endpoints); Audit.

Decision classification:
- TECHNICAL DECISION

Proposed locked wording:
- "Phase 11 financial records are immutable once created or approved; corrections are new adjustment, reversal or superseding records."

### D38

Title: Organization ownership of revenue, entitlements and payouts

Current requirement:
- Phase 10: the seller organization is the payee of buyer payments; farmer agreements have a counterparty organization; projects have an
  owner organization — they may differ (C11).

Problem:
- Who owes the farmer and who sees the records.

Options:
- Option A — revenue owned by the seller organization; entitlements / payouts owned by the project organization.
- Option B — all owned by the agreement counterparty organization.
- Option C — another rule.

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: "revenue: seller org; payouts: project org — confirm when they differ".

Impact:
- Organization scoping, API, UI, tests (isolation).

Decision classification:
- BUSINESS DECISION REQUIRED

Proposed locked wording:
- "Revenue records belong to ⟨BUSINESS TO SELECT⟩; entitlements and payouts belong to ⟨BUSINESS TO SELECT⟩. Where these organizations
  differ, ⟨BUSINESS TO SELECT⟩."

### D39

Title: INTERNAL vs REGISTRY transfer — financial treatment

Current requirement:
- Both complete through the same 9B transfer workflow; no financial difference is defined.

Problem:
- Recognition and entitlement must not depend on an undefined distinction.

Options:
- Option A — treated the same.
- Option B — different treatment (rule to be supplied).

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: "treat the same".

Impact:
- Revenue recognition.

Decision classification:
- RECOMMENDATION — REQUIRES SIGN-OFF

Proposed locked wording:
- "INTERNAL and REGISTRY deliveries are treated identically for revenue recognition and entitlement."

### D40

Title: Farmer statement content

Current requirement:
- §36 farmer report includes payout; §27 farmer UI "Payouts"; §4.1 "view credit/payout information permitted by project".

Problem:
- What a farmer may see about the sale and its lineage.

Options:
- Option A — own entitlements / payouts with lineage to the credit batch (no buyer identity, prices of other items or other farmers).
- Option B — a reduced statement (amounts only).

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: "own entitlements / payouts, lineage to batch".

Impact:
- API (`/payouts/me`), UI (farmer earnings), documents (statement).

Decision classification:
- RECOMMENDATION — REQUIRES SIGN-OFF

Proposed locked wording:
- "The farmer statement shows the farmer's own entitlements and payouts and their lineage to the credit batch, and nothing about other
  farmers, buyers or project finances."

### D41

Title: Migration

Current requirement:
- Latest revision `0015` (`20261003_0015_phase10_marketplace.py`).

Problem:
- Naming / ordering of the Phase 11 schema change.

Options:
- Option A — `0016_phase11_financials`.

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: `0016_phase11_financials`.

Impact:
- Database; Alembic up / down / up gate; downgrade guard.

Decision classification:
- TECHNICAL DECISION

Proposed locked wording:
- "Phase 11 schema is delivered as migration `0016_phase11_financials`, with a downgrade guard refusing while any Phase 11 row exists."

### D42

Title: Phase 12 boundary

Current requirement:
- §34 background jobs (Redis + Celery); Phase 10 deferred workers.

Problem:
- Keep Phase 11 free of scheduling and workers.

Options:
- Option A — as listed under "Phase 12 boundary".

Discovery recommendation:
- RECOMMENDATION — REQUIRES SIGN-OFF: as discovery §29.

Impact:
- Scope only.

Decision classification:
- TECHNICAL DECISION

Proposed locked wording:
- "Phase 11 contains no worker, scheduler, notification worker, webhook queue or automated recurring settlement."

---

## Contradictions C1–C14

| C | Contradiction | Source A | Source B | Why it matters | Discovery recommendation | Business approval? | Proposed resolution wording |
|---|---|---|---|---|---|---|---|
| C1 | DEMO payout seed | §43 seeds "1 payout" | honest-DEMO rule (Phases 9A–10), §1.13, §1.19 | a seeded payout would fake money movement | no financial records in DEMO (D35) | **Yes** | "§43's DEMO payout is not seeded; DEMO shows an honest note." |
| C2 | One role calculates and approves | §4.16 (Finance / Payout Manager does both) | platform SoD (creator ≠ approver) | approval by the calculator defeats control | SoD per person (D21) | **Yes** | "The same role may hold both permissions; the same person may never calculate and approve the same run." |
| C3 | Revenue-share source | §26 "project agreement / configured revenue-share rules" | repo: agreements = free text; `share_pct` = carbon-rights share | no computable entitlement exists | new versioned configuration; `share_pct` evidence only unless confirmed (D1, D13) | **Yes** | "Entitlement source per D1; `share_pct` meaning per D13." |
| C4 | Configured rules vs no UI-entered numbers | §26 "configured revenue-share rules" | §26 "Do not calculate farmer payout directly from a UI-entered number" | rules must be entered by someone | approval-controlled, versioned configuration (D2) | **Yes** | "Rules are entered once, approved by a second person, versioned; payouts are never typed." |
| C5 | Costs before farmer share | §26 ordering (costs / fees → farmer share) | no stated deduction rule | changes the base of every share | business defines (D3, D6) | **Yes** | "Deduction per D3 / D6 only." |
| C6 | Platform fee vs seller as payee | any platform-fee model | Phase 10 D16 (seller is payee; platform collects nothing), D9 (no fee) | a fee could not be collected in-flow | none unless supplied (D4) | **Yes** | "No platform fee unless D4 supplies one and its collection mechanism." |
| C7 | Secondary sales | Phase 10 D3 (any PD holding credits may list) | spec silent on farmers' share of secondary sales | obligations without an agreement | business decides (D16) | **Yes** | "Secondary-sale revenue per D16." |
| C8 | Payout provider | §42 PaymentProvider; §26 "Bank / Payment Provider" | §49 only PAYMENT_PROVIDER; no payout provider listed | adapter scope unclear | ManualPayoutAdapter + TEST adapter (D24) | **Yes** | "Payout execution is manual until a payout provider is contracted." |
| C9 | Calculated vs issued for allocation | farm-level calculation outputs exist | §1.11, rule 12 (calculated ≠ issued); Phase 7 deferred farm allocation | allocating issued revenue by calculated values blurs the distinction | business supplies a key (D12) | **Yes** | "Calculated farm-level values are not an allocation key unless D12 explicitly selects a VVB-accepted contribution." |
| C10 | Holders vs bank model | carbon-rights holders include organizations / groups / landowners | bank accounts exist only for farmers | some holders cannot be paid | farmers only first (D22) | **Yes** | "Payees per D22." |
| C11 | Who owes the farmer | agreement counterparty organization | project organization; seller organization (payee) | scoping and liability | revenue: seller; payouts: project org — confirm (D38) | **Yes** | "Ownership per D38." |
| C12 | DEMO completion of payout | §46 #39, §54 ("payout can be approved", "farmer payout completed") | honest-DEMO rule | DEMO acceptance cannot be met honestly | no DEMO financial records (D35) | **Yes** | "§46 #37–39 are demonstrated in TEST, not DEMO." |
| C13 | Refund after delivery | Phase 10: refunds after delivery are money only; credits stay with the buyer | farmer revenue impact undefined | revenue / entitlement mismatch | reversal record; policy open (D10, D29) | **Yes** | "Refund effects per D10 and D29." |
| C14 | Documentation / API naming | §52 requires `docs/payout-workflow.md` | §29 lists only `/api/v1/payouts`; revenue / cost endpoints unnamed | API surface placement | revenue under `/revenue`, others under `/payouts` (discovery §26) | No (technical) | "Phase 11 delivers `docs/payout-workflow.md`; endpoints per the approved API proposal." |

---

## Proposed Phase 11 model (candidate — not approved)

| Table | Status | Why (from the discovery report) |
|---|---|---|
| `revenue_records` (§7.14 `project_revenue`) | **REQUIRED** | §46 #37 "Revenue is recorded"; recognition per order item from immutable Phase 10 facts, with reversal rows (D8–D10) |
| `revenue_share_rules` | **OPTIONAL IF DECISION CONFIRMED** (D1 A, D2) | needed only if the entitlement source is a new configuration |
| `revenue_share_rule_versions` | **OPTIONAL IF DECISION CONFIRMED** (D1 A, D2) | versioned, approved, immutable rule content |
| `project_costs` (§7.14) | **OPTIONAL IF DECISION CONFIRMED** (D6 B / C) | only if costs are tracked |
| `fee_records` | **OPTIONAL IF DECISION CONFIRMED** (D4 B) | only if a fee is defined; discovery "fee records (if any)" |
| `settlement_runs` | **REQUIRED** | immutable, input-hashed calculation version (D17, D37); payouts need a reproducible basis |
| `farmer_entitlements` (§7.14 `farmer_revenue_shares` lines) | **REQUIRED** | §46 #38 "Farmer payout is calculated"; per payee per revenue record per run |
| `revenue_allocations` (separate table) | **REJECTED** | the allocation is the entitlement line itself; a separate table would duplicate the allocation source of truth |
| `payouts` (§7.14 `farmer_payouts`) | **REQUIRED** | §46 #39 "Payout can be approved"; payout lifecycle (D20) |
| `payout_transactions` (§7.14) | **REQUIRED** | each execution attempt with bank reference and evidence |
| `payout_events` | **OPTIONAL IF DECISION CONFIRMED** (D24) | provider / TEST-adapter events only; the manual runtime adapter produces none |
| `payout_reconciliations` (§7.14) | **REQUIRED** | §47 Phase 11 "reconciliation"; §4.16 "track bank / payment status" |
| `payout_adjustments` | **OPTIONAL IF DECISION CONFIRMED** (D29 A) | only if a carry-forward recovery policy is chosen |
| `invoices` (§7.13) | **DEFERRED** (D32) | no tax / invoice rules |

No table stores a credit quantity or ownership (the Phase 9B ledger remains the only credit source of truth). Money columns follow
Phase 10 (`Numeric(19,4)` + ISO-4217 currency).

## Proposed financial lineage

**Money flow (candidate):**

```
Completed Order → Order Item → Payment (CONFIRMED) → Revenue Record → [Revenue Allocation = entitlement line] → Farmer Entitlement
→ Settlement Run (the entitlement is created by, and belongs to, the run) → Payout → Payout Transaction → Reconciliation
```

**Back to carbon lineage:**

```
Payout → Entitlement → Revenue Record → Order Item → Order → 9B Transfer (TRANSFER_COMPLETE entry) → Credit Ledger positions
→ Credit Batch → Issuance → Registry submission → VVB Decision → Calculation Run → MRV Dataset → Monitoring period → Project
→ Project Farm → Farm → Farmer (+ carbon-rights record, agreement)
```

| Source of truth | Records |
|---|---|
| **MONEY SOURCE OF TRUTH** | Phase 10 `orders`, `order_items`, `payments`, `refunds` (what was charged and received) → Phase 11 `revenue_records`, `farmer_entitlements`, `payouts`, `payout_transactions`, `payout_reconciliations`, adjustments (what is owed and paid). Money never changes a carbon quantity |
| **CREDIT SOURCE OF TRUTH** | Phase 9B credit ledger (positions, entries, reservations, transfers, retirements) over 9A batches / issuances. Phase 11 only references it |

Below the credit batch, the existing 9A / 9B / Phase 10 lineage endpoints are reused — not duplicated.

## Proposed payout lifecycle — OPEN DECISION — D20

```
CALCULATED → PENDING_APPROVAL → APPROVED → PAYMENT_PENDING → PAID → RECONCILED
Failure / exit states: REJECTED, CANCELLED, FAILED, UNCONFIRMED
Optional: ON_HOLD (bank-account change, KYC / agreement problem — D23)
```

Not locked. Requires human confirmation (D20), together with D21 (who performs each step) and D23 (ON_HOLD).

## Proposed permissions

| Permission | Status | Justification |
|---|---|---|
| `payouts.read` | **definitely required** | read runs / payouts of the organization |
| `payouts.calculate` | **definitely required** | create a settlement run (§4.16 "calculate farmer share") |
| `payouts.approve` | **definitely required** | §4.16 "approve payouts"; §35 PAYOUT_APPROVED; approver ≠ calculator |
| `payouts.execute` | **definitely required** | record execution with evidence; executor ≠ approver |
| `payouts.reconcile` | **conditional** (D21) | separate only if reconciler must differ from executor; otherwise could be part of `payouts.execute` — potentially unnecessary |
| `revenue.read` | **potentially unnecessary** | could be covered by `payouts.read`; keep separate only if revenue must be visible to roles that must not see payouts |
| `sharing.manage`, `sharing.approve` | **conditional** (D1 A, D2) | only with a new sharing configuration |
| `costs.manage` | **conditional** (D6) | only if costs are tracked |
| `farmers.self` (existing) | **reused** | farmer sees own entitlements / payouts (D33, D40) |

Not proposed: `revenue.manage` (revenue is never entered manually — §26), `allocation.manage` (allocation belongs to the settlement run).

## Payout adapter (proposed architecture)

- `PayoutAdapter` Protocol — candidate methods: `create_payout`, `get_status`, `cancel_payout`, `parse_event`; `reconcile` = a single
  status query on request.
- Runtime: **ManualPayoutAdapter** — raises `ManualActionRequired`; execution is recorded by a person with the bank reference and a PDF
  proof; reconciliation by matching a bank statement.
- TEST: a **TEST-only adapter** injected into the service layer, never registered; outbox (row + idempotency key committed before the
  call), timeout → UNCONFIRMED, no automatic retry, deduplicated append-only events.
- LIVE: **no fake success**, no public webhook.
- Provider choice: **OPEN** — the specification defines no payout provider (no bank API, UPI, NEFT, RTGS or IMPS).

## Phase 12 boundary

Phase 11 does **not** implement: Celery; Redis workers; scheduled payout jobs; scheduled reconciliation; notification workers; webhook
queues; automated recurring settlement. These remain Phase 12.

---

## DECISION SUMMARY

| ID | Decision | Classification | Recommendation | Human sign-off required |
|----|----------|----------------|----------------|-------------------------|
| D1 | Source of farmer entitlement | BUSINESS DECISION REQUIRED | new versioned approved configuration; share_pct evidence only unless confirmed | Yes |
| D2 | Rule configuration model | BUSINESS DECISION REQUIRED | per project, versioned, second-person approval | Yes |
| D3 | Calculation base (incl. developer share) | BUSINESS DECISION REQUIRED | none — business chooses | Yes |
| D4 | Fees / commission | BUSINESS DECISION REQUIRED | none unless supplied | Yes |
| D5 | Third-party fees | BUSINESS DECISION REQUIRED | treat as project costs if D6 | Yes |
| D6 | Project costs tracked / deducted | BUSINESS DECISION REQUIRED | none — business defines | Yes |
| D7 | Cost granularity | BUSINESS DECISION REQUIRED | project + monitoring period | Yes |
| D8 | Revenue recognition trigger | RECOMMENDATION — REQUIRES SIGN-OFF | order-item delivery completion | Yes |
| D9 | Recognition granularity | TECHNICAL DECISION | per order item | No (technical review) |
| D10 | Revenue reversal after refund | BUSINESS DECISION REQUIRED | reversal record; policy open | Yes |
| D11 | Chargebacks | BUSINESS DECISION REQUIRED | not supported until a provider exists | Yes |
| D12 | Allocation key batch → farms | BUSINESS DECISION REQUIRED | none — business supplies | Yes |
| D13 | Multiple holders / share_pct meaning | BUSINESS DECISION REQUIRED | none beyond D1 | Yes |
| D14 | Time eligibility | BUSINESS DECISION REQUIRED | ACTIVE participation + VERIFIED rights in the period | Yes |
| D15 | Agreement termination / rights transfer | BUSINESS DECISION REQUIRED | none — business decides | Yes |
| D16 | Secondary sales | BUSINESS DECISION REQUIRED | none — business decides | Yes |
| D17 | Entitlement creation | RECOMMENDATION — REQUIRES SIGN-OFF | in an approved settlement run | Yes |
| D18 | Payout trigger / aggregation | BUSINESS DECISION REQUIRED | manual run; one payout per payee per run | Yes |
| D19 | Settlement cycle | BUSINESS DECISION REQUIRED | none in Phase 11 (manual) | Yes |
| D20 | Payout lifecycle | BUSINESS DECISION REQUIRED (OPEN — D20) | candidate lifecycle | Yes |
| D21 | Separation of duties | BUSINESS DECISION REQUIRED | calculator ≠ approver ≠ executor; reconciler TBD | Yes |
| D22 | Payee types | BUSINESS DECISION REQUIRED | farmers only first | Yes |
| D23 | Bank requirement / change hold | BUSINESS DECISION REQUIRED | VERIFIED; change → hold + re-approval | Yes |
| D24 | Payout adapter / provider / manual | RECOMMENDATION — REQUIRES SIGN-OFF | ManualPayoutAdapter + TEST adapter; provider OPEN | Yes |
| D25 | Documents | BUSINESS DECISION REQUIRED | remittance proof, statement, farmer statement | Yes |
| D26 | Currency / FX | RECOMMENDATION — REQUIRES SIGN-OFF | one currency per run; no FX | Yes |
| D27 | Rounding / remainder | BUSINESS DECISION REQUIRED | per line to minor unit; remainder rule open | Yes |
| D28 | Minimum payout | BUSINESS DECISION REQUIRED | none unless defined | Yes |
| D29 | Refund after payout | BUSINESS DECISION REQUIRED | none — business decides | Yes |
| D30 | Holdback | BUSINESS DECISION REQUIRED | none unless defined | Yes |
| D31 | Tax / withholding | BUSINESS DECISION REQUIRED | external boundary | Yes |
| D32 | Invoices / tax documents | BUSINESS DECISION REQUIRED | deferred | Yes |
| D33 | Visibility | RECOMMENDATION — REQUIRES SIGN-OFF | farmer own; project org own farmers; platform none | Yes |
| D34 | RBAC | BUSINESS DECISION REQUIRED | minimum set; role grants open | Yes |
| D35 | DEMO | RECOMMENDATION — REQUIRES SIGN-OFF | no financial records in DEMO | Yes |
| D36 | TEST | TECHNICAL DECISION | full synthetic chain + races | No (technical review) |
| D37 | Immutability / corrections | TECHNICAL DECISION | immutable; supersede; adjustments | No (technical review) |
| D38 | Organization ownership | BUSINESS DECISION REQUIRED | revenue: seller; payouts: project org (confirm) | Yes |
| D39 | INTERNAL vs REGISTRY | RECOMMENDATION — REQUIRES SIGN-OFF | treat the same | Yes |
| D40 | Farmer statement content | RECOMMENDATION — REQUIRES SIGN-OFF | own records, lineage to batch | Yes |
| D41 | Migration | TECHNICAL DECISION | `0016_phase11_financials` | No (technical review) |
| D42 | Phase 12 boundary | TECHNICAL DECISION | no workers / schedulers | No (technical review) |

Totals: 42 decisions — 29 BUSINESS DECISION REQUIRED, 8 RECOMMENDATION — REQUIRES SIGN-OFF, 5 TECHNICAL DECISION; 37 require human
sign-off; 14 contradictions (C1–C14, 13 requiring business approval).

## IMPLEMENTATION BLOCKERS

These must be resolved before Phase 11 coding can safely begin (they determine schema, amounts or legal exposure):

- **D1, D2, D13** — entitlement source, rule model, meaning of `share_pct`.
- **D3** — calculation base (and the developer share).
- **D4, D5, D6, D7** — fees, third-party fees, costs and their deduction / granularity.
- **D8, D10** — revenue recognition and reversal.
- **D12, D14, D15, D16** — allocation keys, eligibility, termination, secondary sales.
- **D18, D19, D20, D21** — payout trigger, cycle, lifecycle, separation of duties.
- **D22, D23** — payee types, bank requirement and change handling.
- **D27** — rounding / remainder.
- **D29** — refund after payout (determines whether `payout_adjustments` exists).
- **D31** — tax / withholding boundary (legal exposure).
- **D38** — organization ownership.

## SAFE TO IMPLEMENT AFTER LOCK

Technical decisions that can proceed once the business decisions above are locked:

- **D9** — per-order-item revenue records.
- **D36** — TEST-only fixtures and real concurrency tests (separate connections, snapshot harness).
- **D37** — immutability triggers, superseding runs, adjustment / reversal records.
- **D41** — migration `0016_phase11_financials` with a downgrade guard.
- **D42** — no workers or schedulers.
- Plus, once signed off: D24 adapter skeleton (ManualPayoutAdapter + TEST adapter), D26 single-currency runs, D33 / D40 visibility,
  D35 honest DEMO, D39 identical INTERNAL / REGISTRY treatment, D17 entitlement-in-run.

## PHASE 11 IMPLEMENTATION ORDER (proposed sequence only — not started)

1. Migration / schema (`0016_phase11_financials`; only the tables confirmed above)
2. Revenue recognition
3. Share configuration (if D1 A / D2)
4. Allocation
5. Settlement calculation
6. Entitlements
7. Payout workflow
8. Payout adapter (ManualPayoutAdapter + TEST adapter)
9. Reconciliation
10. Documents
11. RBAC
12. UI
13. Tests (functional, RBAC / SoD, isolation, real concurrency, triggers, DEMO honesty)
14. E2E (Phases 1–11)

None of these steps is implemented by this document.
