# Phase 11 — Revenue, costs, farmer share and payouts: discovery and design

> **Discovery only.** No application code, migration, schema, API or UI was created or changed. This document is the only file added.
> Baseline: commit `1a8b9b3` (`phase-10-marketplace`), working tree clean, development database at migration `0015`.

Tags used throughout:

- **[EXISTING REQUIREMENT]** — stated in the master specification (`§n`) or already built and locked in the repository ("repo").
- **[ASSUMPTION]** — inferred because it is technically necessary; needs no business decision but can be challenged.
- **[OPEN DECISION]** — not defined anywhere; must be decided by the business before implementation.

---

## 1. Executive summary

1. **The specification requires Phase 11 but defines almost no rules.** It names the flow (§26: buyer payment → order → revenue →
   project costs / fees → farmer share → payout → bank / payment provider → reconciliation), the tables (§7.14), the Finance / Payout
   Manager's duties (§4.16), and three acceptance steps (§46 #37–39: revenue is recorded; farmer payout is calculated *according to
   configured agreement*; payout can be approved). It defines **no** percentage, fee, commission, cost treatment, calculation base,
   allocation key, settlement cycle, payout provider, rounding rule, tax treatment or refund recovery policy.
2. **No authoritative source of farmer economic entitlement exists in the repository.** `farmer_agreements` holds only free-text
   `terms_summary` (no share, amount or formula). `project_carbon_rights.share_pct` records a share of the *carbon rights* of one farm's
   participation, evidenced by an agreement / document / reference — the specification never says it is a revenue share. §26 says
   "use project agreement / configured revenue-share rules" and "do not calculate farmer payout directly from a UI-entered number", so a
   **versioned, approval-controlled revenue-share configuration does not exist yet** and must be decided (D1, D2).
3. **No authoritative allocation key exists for issued credits.** Registry issuance (9A) is per monitoring period / batch; farm-level
   calculation allocation was explicitly deferred in Phase 7; calculated farm-level values are *calculated tCO2e*, never credits (§1.11,
   rule 12). Allocating revenue across the farms of a project therefore needs an explicit decision (D12–D14). Equal, acreage-based or
   quantity-based allocation must **not** be assumed.
4. **Where Phase 11 attaches (repo):** the Phase 10 money facts — `orders` / `order_items` (gross line totals, one currency),
   `payments` (CONFIRMED, payee = the seller organization), `refunds` (`after_transfer`) — and the 9B delivery (`credit_transfers`
   COMPLETED) per order item; the item's batch gives project, monitoring period, vintage and the 9A / 8B / 7 lineage down to farms and
   farmer codes. Phase 11 should *read* these records; it must not duplicate amounts or ownership.
5. **Recommended shape (all marked OPEN until confirmed):** recognize revenue per order item from immutable Phase 10 facts; compute farmer
   entitlements in **immutable, versioned settlement runs** that snapshot their inputs (revenue records, approved revenue-share rule
   version, carbon-rights records, cost records if any) with a SHA-256; payouts per payee per run with dual control (calculator ≠ approver
   ≠ executor), a **ManualPayoutAdapter** (evidence-backed, no fake success) and a TEST-only adapter; corrections only by adjustment /
   reversal records; DEMO stays honest (no revenue, no payout).
6. Counts: **42 open decisions**, **14 contradictions / ambiguities**, proposed migration **`0016_phase11_financials`** (the repository's
   latest revision is `0015`).

## 2. Current repository baseline

| Item | State (repo) |
|---|---|
| Commit | `1a8b9b3` phase-10-marketplace; Phases 1–10 complete |
| Latest migration | `20261003_0015_phase10_marketplace.py` (revision `0015`) |
| Payout code | none — no `/payouts` route, no payout model, no payout adapter; `FINANCE_MANAGER` role description already says "calculates farmer share per agreement, approves payouts" |
| Revenue / fee / cost code | none — Phase 10 records gross order amounts only (D9: no fee of any kind; D34: no revenue, commission, payout) |
| Boundary tests | `/payouts` is asserted absent in several tests (test_registry, test_verification, test_ledger, test_marketplace, frontend specs) — Phase 11 must narrow these deliberately |
| Docs | spec §52 requires `docs/payout-workflow.md` (not yet written) |

### End-to-end lineage that exists today (repo)

```
farmers (KYC, bank accounts — encrypted, last4 + keyed hash, VERIFIED by a 2nd person)
  └ farmer_agreements (DRAFT/SIGNED/TERMINATED/EXPIRED/VOID; counterparty_organization_id; terms_summary = free text; signed PDF)
farms (farm_ownership, boundaries)
projects (organization_id = project developer)
  └ project_farms (farm, farmer, participation_start/end, boundary version, area snapshot)
       └ project_carbon_rights (holder_type FARMER/LANDOWNER/ORGANIZATION/FARMER_GROUP/OTHER, holder, share_pct, agreement /
                                document / reference, effective_from/to, ACTIVE/ENDED/VOID, verified by a 2nd person)
  └ monitoring periods → MRV datasets → calculation runs (outputs incl. optional FARM-level calculated values) → readiness →
    8B VVB decision (VVB-stated quantity) → 9A registry submission → credit_issuances → credit_batches (+ serial ranges)
       └ 9B credit ledger: positions / entries / reservations / transfers / retirements (owner organization = custodian / holder)
            └ Phase 10: marketplace_listings → orders → order_items (batch, serial range, qty, unit_price, line_total,
                         reservation_id, transfer_id) → payments (payee = seller org, CONFIRMED by seller finance) → refunds
                         → 9B transfer COMPLETED → buyer AVAILABLE positions
```

**Attachment point for Phase 11 [ASSUMPTION]:** the order item (`order_items`) is the smallest unit that carries both money (line total,
currency, payment) and carbon lineage (batch → issuance → period → project → farms). Phase 11 records should reference `order_item_id`
(and through it `order_id`, `payment_id`, `transfer_id`, `batch_id`) rather than copy amounts or ownership.

## 3. Existing financial / economic data model

| Concept | Where it exists | Notes |
|---|---|---|
| Unit price, line total, subtotal / total | `order_items.unit_price`, `line_total`; `orders.subtotal`, `total` (= subtotal) | `Numeric(19,4)`, one ISO-4217 currency per order, minor-unit validation (`CURRENCY_EXPONENTS`) [EXISTING REQUIREMENT] |
| Payment amount | `payments.amount` (must equal order total; no partial payment) | payee = seller organization (D16); MANUAL adapter only [EXISTING REQUIREMENT] |
| Refund amount | `refunds.amount` (whole payment only), `after_transfer` flag | money only; never moves credits [EXISTING REQUIREMENT] |
| Fees, commissions, taxes | **none** (Phase 10 D9 / D10) | |
| Seller proceeds / platform revenue / project revenue | **none** | the seller receives the gross payment directly (D16) |
| Farmer share / payout amount | **none** | |
| Exchange rate | **none** (no FX) | |
| Carbon-rights share | `project_carbon_rights.share_pct` `Numeric(6,3)`, 0 < x ≤ 100 | share of carbon rights, not stated as revenue share |
| Farmer agreement terms | `farmer_agreements.terms_summary` (free text), signed PDF | no structured economics |
| Bank destination | `farmer_bank_accounts` (VERIFIED by a second person; encrypted number; last4 + hash; `is_primary`) | farmers only — no organization / landowner bank model |

**Missing business rules (all OPEN):** revenue recognition point; calculation base (gross / net); fee types and rates; commission; cost
categories and whether they reduce the farmer share; farmer share source and formula; allocation key across farms and holders;
settlement cycle; minimum payout; rounding and remainder; payout currency; FX; tax / withholding; invoice / statement; refund-after-payout
recovery; secondary-sale entitlement.

## 4. Farmer economic rights

| Question | Finding |
|---|---|
| 1. Is a farmer entitled to sale proceeds? | **Implied, not defined.** §5 purpose "revenue distribution, and farmer payout"; §4.16 "calculate farmer share according to agreement"; §26 "Farmer Share"; §46 #38 "farmer payout is calculated according to configured agreement". No entitlement rule is defined [EXISTING REQUIREMENT for the *existence* of a share; OPEN DECISION for its content] |
| 2. Where is it represented? | Nowhere structurally. Candidates: (a) `farmer_agreements` (only free text + PDF); (b) `project_carbon_rights.share_pct` (share of carbon rights per farm participation, linked to an agreement); (c) a new versioned revenue-share configuration (§7.14 `farmer_revenue_shares`). [OPEN DECISION D1] |
| 3. Percentage / fixed / formula / agreement / project / farm-specific? | **Unknown.** §26 "project agreement / configured revenue-share rules" allows project-level or agreement-level rules; nothing more [OPEN DECISION D2] |
| 4. Many farmers per project? | Yes — `project_farms` per farm with its farmer [EXISTING REQUIREMENT] |
| 5. One farmer in many projects? | Yes, with conflicts acknowledged (overlapping participation is flagged, not refused) [EXISTING REQUIREMENT] |
| 6. One farm in several economic arrangements? | Possible: several `project_carbon_rights` records per participation (different holders, `share_pct`), and a farm can participate in another project with acknowledged overlap. Whether a farm's revenue can be claimed twice is a double-counting question (§41) [OPEN DECISION D13] |
| 7. Agreement terminated? | Agreement → TERMINATED / EXPIRED; carbon-rights records can be ENDED with `effective_to`; no economic consequence defined (accrued vs future entitlement) [OPEN DECISION D15] |
| 8. Carbon rights transferred? | Modelled as ending one rights record and creating another with new dates / holder; economic effect on already-issued / already-sold credits undefined [OPEN DECISION D15] |
| 9. Multiple participating organizations? | `project_participants` are *users* with project roles; the project has one owner organization; carbon-rights holders may be organizations (`holder_organization_id`). No inter-organization revenue split exists [OPEN DECISION D22] |

## 5. Revenue recognition

Source records (repo): `order_items` (line total), `orders` (status, `completed_at`), `payments` (`status`, `confirmed_at`,
`amount`, `currency`), `credit_transfers` (`status`, `completed_at`, `kind`), `refunds` (`status`, `completed_at`, `after_transfer`).

| Question | Finding |
|---|---|
| Recognition event | **Undefined.** Candidates: payment CONFIRMED (money received — §26 starts at "Buyer Payment"); order item DELIVERED / order COMPLETED (credits transferred — §25 "Transfer → Ownership update"); both [OPEN DECISION D8] |
| Granularity | Per order item is the only granularity that keeps batch / project / period lineage (an order may hold items of several batches; one seller) [ASSUMPTION; OPEN DECISION D9] |
| Refunds | Phase 10 refunds are whole-payment, money only. Recognized revenue would need a **reversal record** (never an edit) [ASSUMPTION; policy OPEN D10] |
| Chargebacks | Not modelled anywhere (no provider) [OPEN DECISION D11] |
| Cancelled / rejected transfers | A rejected delivery returns credits to the seller (ATTENTION_REQUIRED); if recognition is at delivery, nothing is recognized until COMPLETED [ASSUMPTION] |
| INTERNAL vs REGISTRY | Both complete the same way in 9B; the specification defines no financial difference [OPEN DECISION — recommend none, D8] |
| Secondary sales | A PROJECT_DEVELOPER that received credits by a 9B INTERNAL transfer may list and sell them (Phase 10 D3). Whether the original project's farmers share in a secondary sale is undefined [OPEN DECISION D16] |

## 6. Fees and commissions

**The specification defines no fee and no commission.** §4.16 "record fees/costs" and §26 "Project Costs / Fees" are the only
mentions. Phase 10 D9 locked "no marketplace / buyer / seller fee, no platform commission" for the marketplace transaction; D16 makes the
seller the payee and "the platform does not collect marketplace revenue".

| Fee candidate | Payer / receiver / base / timing / currency / rounding / tax / in order total / deducted before share / separately payable |
|---|---|
| Platform fee | all [OPEN DECISION D4]. Note contradiction C6: with D16 the platform never receives the money, so a platform fee could only be invoiced or recorded as a deduction owed — not collected through the marketplace flow |
| Seller fee / buyer fee | all OPEN (D4) — a buyer fee would change the Phase 10 order total (locked as subtotal = total) |
| Project fee / project-developer share | all OPEN (D3, D22) |
| Registry fee, VVB fee | all OPEN (D5) — these are *costs* paid to third parties, see §7 |
| Payment processing fee | all OPEN (D5) — no provider exists |
| Fixed / percentage / tiered / per-credit | all OPEN (D4) — **no percentage is proposed here** |

## 7. Project costs

§7.14 lists `project_costs`; §4.16 "record fees/costs"; §26 places "Project Costs / Fees" between revenue and farmer share. Nothing
defines cost categories, evidence, approval, accrual vs actual, granularity or whether costs reduce the farmer share.

| Question | Finding |
|---|---|
| Categories (MRV, laboratory, VVB, registry, marketplace, payment processing, administration, onboarding, verification, other) | none defined [OPEN DECISION D6] |
| Actual / estimated / accrued / paid | undefined [OPEN DECISION D6] |
| Granularity (project / farm / credit / period) | undefined; only project and monitoring period are reachable from a batch [OPEN DECISION D7] |
| Effect on farmer share, project share, net revenue, payout | undefined; §26 ordering *suggests* deduction before farmer share but does not state it (ambiguity C5) [OPEN DECISION D3, D6] |

## 8. Farmer share / benefit sharing

| Question | Finding |
|---|---|
| Farmer share | named, not defined (§4.16, §26, §46 #38) |
| Carbon revenue sharing vs benefit sharing | the specification uses "revenue distribution" (§ purpose), "revenue-share rules" (§26) and "co-benefits" (listing disclosure §25 — environmental, not monetary). **Benefit sharing is not defined separately** from revenue sharing |
| Project-developer / landowner / tenant / community / other shares | not defined; carbon-rights holder types include LANDOWNER, ORGANIZATION, FARMER_GROUP, OTHER (repo) — they could be payees, but no economics are attached |
| Model | **not selected here.** Interpretations, each with its source: |

| # | Interpretation | Source / ambiguity |
|---|---|---|
| I1 | gross revenue → minus fees → minus project costs → net revenue → farmer % of net | §26 ordering (Revenue → Project Costs / Fees → Farmer Share); the deduction is not stated (C5) |
| I2 | gross revenue → farmer % of gross; fees / costs borne by the developer's share | §4.16 "calculate farmer share according to agreement" — the agreement may define a gross share |
| I3 | per-credit fixed amount to the farmer, independent of price | possible agreement term; §26 "configured revenue-share rules" does not exclude it |
| I4 | carbon-rights share_pct applied to the holder's portion of a farm's revenue | repo `share_pct` — only if the business confirms it is an economic share (C3) |

All four are **[OPEN DECISION D3 / D1 / D2]**.

## 9. Allocation model

No authoritative key exists to split a batch's revenue across the farms of a project [repo]:

- Issuance is per monitoring period and batch (9A); serial ranges are registry-stated, not per farm.
- Phase 7 farm-level allocation was deferred; any FARM-level calculation outputs are *calculated tCO2e* (§1.11, rule 12) — using them
  would treat calculated values as issued credits (C9).
- `project_farms.farm_area_hectares` is a boundary snapshot; acreage allocation is **not** required anywhere.

Candidate keys (none to be assumed): (a) an agreement-defined fixed share per farm / farmer; (b) an approved per-period allocation table
recorded by the project (versioned, second-person approved); (c) a methodology-provided farm-level verified contribution (would need the
methodology module and VVB acceptance); (d) carbon-rights `share_pct` within a farm. [OPEN DECISION D12, D13, D14]

Eligibility in time: which farms share a batch's revenue? Candidates: farms with ACTIVE participation and ACTIVE, VERIFIED carbon-rights
records during the batch's monitoring period [ASSUMPTION — the only dates available]; the rule itself is [OPEN DECISION D14].

## 10. Payout lifecycle (candidate — OPEN DECISION D20)

```
CALCULATED (settlement run)  → PENDING_APPROVAL → APPROVED → PAYMENT_PENDING → PAID → RECONCILED
                       ↘ REJECTED (by approver) / CANCELLED (before execution)
PAYMENT_PENDING → FAILED (bank / provider rejection; funds not sent) → a new payout or re-issue (never an edit)
PAYMENT_PENDING → UNCONFIRMED (provider timeout, adapter only) → reconciliation
ON_HOLD (bank-account change, KYC / agreement problem) — candidate, OPEN
```

| Role | Candidate actor | SoD |
|---|---|---|
| create / calculate | Finance / Payout Manager (§4.16 "calculate farmer share") | — |
| review / approve | Finance / Payout Manager (§4.16 "approve payouts"), **a different person** | approver ≠ calculator [EXISTING pattern] |
| execute (record the bank transfer with evidence) | finance user ≠ approver | executor ≠ approver [requested by Phase 11 brief] |
| reconcile (match the bank statement) | finance user; whether ≠ executor is OPEN | [OPEN DECISION D21] |

§35 lists `PAYOUT_APPROVED`; §33 notifies "Payout completed" [EXISTING REQUIREMENT].

## 11. Bank / payout destination

| Question | Finding |
|---|---|
| Verified bank account usable? | Yes — `farmer_bank_accounts` VERIFIED by someone other than the adder (Phase 2) [EXISTING REQUIREMENT] |
| Payout requires VERIFIED? | not stated; strongly recommended [OPEN DECISION D23] |
| Account belongs to farmer | yes (farmer-level); **no bank model for organizations, farmer groups or landowners** that may hold carbon rights (C10) [OPEN DECISION D22] |
| Project organization receives money? | yes — it is the payee of buyer payments (Phase 10 D16) |
| Destination change / hold / re-verification | a change creates a new PENDING_VERIFICATION account; the effect on a pending payout (hold, re-approval) is [OPEN DECISION D23] |
| last4 / hash | available (`account_last4`, keyed `account_number_hash`); the full number is decrypted only server-side [EXISTING REQUIREMENT] |
| Data minimization | payouts should store `bank_account_id` + last4 snapshot only; never return the clear number to the UI [ASSUMPTION] |

## 12. Payout adapter

The specification lists `PaymentProvider` (§42) and "Bank / Payment Provider" (§26) but **no payout provider, bank API, UPI / NEFT /
RTGS / IMPS or settlement system**; §49 has only `PAYMENT_PROVIDER` (C8).

Recommended pattern (mirrors 9A registry / Phase 10 payment) [ASSUMPTION; D24]:

- `PayoutAdapter` Protocol: `create_payout`, `get_status`, `cancel_payout`, `parse_event` (`reconcile` = status query on request).
- `ManualPayoutAdapter` — the only runtime adapter: raises `ManualActionRequired`; a finance user records the bank reference and a PDF
  remittance proof; another person reconciles against a bank statement.
- TEST-only fake adapter injected in tests, never registered; outbox (payout row + idempotency key committed before any call), timeout →
  UNCONFIRMED, no automatic retry, append-only deduplicated `payout_events`.
- Never a fake LIVE success; no public webhook until a provider contract exists.

## 13. Refund / chargeback interaction

| Case | Current behaviour (repo) | Phase 11 question |
|---|---|---|
| Refund before transfer | order REFUNDED; no credits moved | if revenue was recognized at payment, a reversal record is needed; no payout should exist yet [OPEN D10] |
| Refund after INTERNAL transfer | money-only refund; credits stay with the buyer; a manual 9B reversal is possible only for untouched outputs | revenue reversal? entitlement reversal? [OPEN D10, D29] |
| Refund after REGISTRY transfer | money only; never reversed | same [OPEN D10, D29] |
| Payout not yet made | — | recompute in the next settlement run via reversal records [ASSUMPTION] |
| Payout already made / completed | — | recovery from future payouts (negative carry-forward), direct recovery, write-off, or holdback reserve — **no policy is defined** [OPEN D29, D30] |
| Revenue already recognized | — | reversal record, never edit [ASSUMPTION] |
| Chargeback | not modelled | [OPEN D11] |

## 14. Multi-farmer allocation

| Situation | Finding |
|---|---|
| Project with many farms | needs the allocation key (D12) |
| One farm, several holders | carbon-rights records with `share_pct` per holder — whether shares must sum to 100 % and whether they are economic shares is [OPEN D13] |
| Farmer agreements with different dates | entitlement by effective dates within the monitoring period is a candidate [ASSUMPTION], rule [OPEN D14, D15] |
| Different crediting periods / methodologies | each batch is one project + one period (+ one methodology version); allocation per batch keeps them separate [EXISTING REQUIREMENT for batch granularity] |
| Credits from several batches / projects in one order | each order item is one batch → allocate per item [ASSUMPTION] |

## 15. Financial lineage (required links)

```
payout → payout line(s) → farmer entitlement (settlement run version, rule version) → revenue record → order item → order → payment
       → 9B transfer (completion entry) → 9B positions → credit batch → issuance → registry submission → VVB decision → calculation run
       → MRV dataset → monitoring period → project → project_farm → farm → farmer (+ carbon-rights record, agreement)
```

Required stored references [ASSUMPTION]: `payout_lines.entitlement_id`; `entitlements.revenue_record_id`, `project_farm_id`,
`carbon_right_id` (if used), `agreement_id`, `rule_version_id`; `revenue_records.order_item_id`, `payment_id`, `transfer_id`,
`batch_id`; everything below the batch reuses the existing 9A / 9B / Phase 10 lineage endpoints — **not duplicated**.

## 16. Immutability / corrections

| Record | Proposed treatment |
|---|---|
| Revenue records | immutable once created; reversal rows for refunds / chargebacks [ASSUMPTION] |
| Revenue-share rule versions | draft editable; approved versions immutable; changes = new version (methodology-version pattern, Phase 4) [ASSUMPTION; D2] |
| Settlement runs / entitlements | immutable with an input snapshot + SHA-256 (calculation-run pattern, Phase 7); recalculation = a new run that supersedes, never edits [ASSUMPTION; D37] |
| Payout approval / execution / reconciliation | append-only events; final states frozen by triggers [ASSUMPTION] |
| Adjustments / reversals | separate records referencing the original; never edits [ASSUMPTION] |

## 17. Accounting / settlement periods

Nothing defines an accounting period, settlement period, payout cycle, monthly / quarterly payouts or project close. The crediting period
and monitoring period exist (Phase 3 / 5) but are carbon concepts. [OPEN DECISION D19] — **no monthly / quarterly behaviour is
assumed.** A manually triggered settlement run over a selected set of recognized revenue records is the minimal mechanism
[ASSUMPTION]; scheduling is Phase 12.

## 18. Tax boundaries

GST, TDS / withholding, income tax, invoices and tax documents are **not specified**. Phase 10 D10 deferred tax and invoices. Phase 11
should treat tax as an **external accounting / legal configuration boundary**: no rate, threshold or jurisdiction rule is encoded until
provided [OPEN DECISION D31, D32]. A payout statement that is explicitly "not a tax document" is possible without tax rules.

## 19. RBAC (proposal — minimum set)

| Permission | Purpose | Candidate roles |
|---|---|---|
| `revenue.read` | read recognized revenue of the organization | FINANCE_MANAGER, PROJECT_MANAGER |
| `sharing.manage` / `sharing.approve` | draft / approve revenue-share rule versions (only if D2 = new configuration) | FINANCE_MANAGER (two people) or PROJECT_MANAGER + FINANCE_MANAGER [OPEN D34] |
| `costs.manage` | record project costs with evidence (only if D6 = costs tracked) | FINANCE_MANAGER |
| `payouts.read` | read settlement runs / payouts of the organization | FINANCE_MANAGER, PROJECT_MANAGER |
| `payouts.calculate` | create a settlement run | FINANCE_MANAGER |
| `payouts.approve` | approve / reject a run or payout — never the calculator | FINANCE_MANAGER (another person) |
| `payouts.execute` | record execution (bank reference + proof) — never the approver | FINANCE_MANAGER (a third person) |
| `payouts.reconcile` | match against bank statements | FINANCE_MANAGER [OPEN whether ≠ executor] |
| farmer self-service | own entitlements and payouts only, via existing `farmers.self` | FARMER |

`revenue.manage` and `allocation.manage` are **not** proposed separately: revenue is recognized from immutable Phase 10 facts (no manual
revenue entry, §26 "do not calculate farmer payout directly from a UI-entered number"), and allocation belongs to the settlement run.
Buyer, VVB, laboratory, QA, registry, credit-manager and methodology roles get nothing. Note ambiguity C2: §4.16 gives "calculate" and
"approve" to the same role — SoD is enforced per person, as everywhere in the platform.

## 20. Organization isolation

| Record | Owner [ASSUMPTION unless noted] |
|---|---|
| Revenue | the seller organization (the payee of the payment — Phase 10 D16) |
| Farmer entitlement / payout | the paying organization = the project developer (owner of the project and of the farmer agreements' counterparty) — but the seller may differ from the project organization after a 9B internal transfer (C7, D16) |
| Fees / costs | the organization that incurs / records them [OPEN] |

Farmers see only their own entitlements / payouts (`farmers.self`, linked farmer). The seller / project organization sees its own
farmers' payouts only; another project developer never sees them. The platform organization sees nothing by default [OPEN D33].

## 21. Documents

Candidates (none invented as legal documents): payout remittance proof (PDF, by the executor), bank / settlement statement for
reconciliation (PDF), payout statement for the farmer (deterministic PDF, "not a tax document"), cost evidence (PDF, if D6). All would
follow the existing pattern: PDF only, malware scan, immutable versions, resolver-based access, SHA-256. Existing `BANK_PROOF` stays a
restricted Phase 2 category. [OPEN D25]

## 22. Audit (candidate events)

`REVENUE_RECOGNIZED`, `REVENUE_REVERSED`, `SHARING_RULE_CREATED` / `_SUBMITTED` / `_APPROVED` / `_SUPERSEDED` (if D2), `PROJECT_COST_RECORDED`
/ `_VOIDED` (if D6), `SETTLEMENT_RUN_CALCULATED` / `_SUPERSEDED`, `PAYOUT_CALCULATED`, `PAYOUT_APPROVED` (§35), `PAYOUT_REJECTED`,
`PAYOUT_CANCELLED`, `PAYOUT_EXECUTION_RECORDED`, `PAYOUT_FAILED`, `PAYOUT_UNCONFIRMED`, `PAYOUT_COMPLETED` (§33 notification),
`PAYOUT_RECONCILED`, `PAYOUT_RECONCILIATION_MISMATCH`, `PAYOUT_ADJUSTMENT_CREATED`, `PAYOUT_HELD` / `_RELEASED` (if D23), `PAYOUT_EVENT_RECEIVED`
/ `_DUPLICATE`. Two-organization pattern where a farmer group / other organization is the payee. Audit logs are append-only already.

## 23. Concurrency

| Race | Proposed protection [ASSUMPTION] |
|---|---|
| 1. Two settlement runs over the same revenue | lock revenue records (UPDLOCK, HOLDLOCK, ROWLOCK) in id order; filtered unique index: one ACTIVE entitlement per (revenue record, payee, run lineage) |
| 2. Approval racing recalculation | lock the run; approval requires the run CURRENT and its input hash unchanged |
| 3. Execution racing cancellation | lock the payout; guarded status update |
| 4. Refund racing payout | lock order → payment → revenue record → entitlement → payout (extends the Phase 10 order); a refund creates a reversal, never edits |
| 5. Order completion racing recognition | recognition in the T4 transaction (if D8 = delivery) or a guarded unique (order_item_id, event) recognition row |
| 6. Duplicate payout request | Idempotency-Key + unique request keys |
| 7. Duplicate provider event | unique (provider, external event id), append-only |
| 8. Bank-account change racing payout | the payout snapshots `bank_account_id` + last4 at approval; execution re-checks VERIFIED / ACTIVE under lock |
| 9. Reconciliation racing execution | lock the payout; reconcile only PAID |

Real concurrency tests on separate connections (snapshot harness of 9B / Phase 10) [ASSUMPTION].

## 24. Proposed data model (candidates — final set depends on decisions)

| Candidate table (spec §7.14 name) | Why | Authoritative source | Mutability / state | Owner | Lineage | Duplicates? |
|---|---|---|---|---|---|---|
| `revenue_records` (`project_revenue`) | recognized revenue per order item (+ reversal rows) | Phase 10 order item / payment / transfer | immutable; RECOGNIZED / REVERSED via separate rows | seller org | order_item → … | references amounts by id; stores the recognized amount snapshot only (needed for reversals) |
| `revenue_share_rules` + `revenue_share_rule_versions` (`farmer_revenue_shares`) | approved configuration of farmer / holder shares | agreements / business decision | versioned; DRAFT → PENDING_APPROVAL → APPROVED → SUPERSEDED | project org | project, agreement(s) | only if D1 / D2 choose a new configuration; otherwise reference agreements / carbon rights |
| `project_costs` | recorded costs with evidence | invoices / business | immutable rows; VOIDED by reversal | project org | project / period | only if D6 |
| `settlement_runs` (part of `farmer_payouts`) | one versioned calculation over selected revenue | revenue records + rule version + rights + costs | immutable + input snapshot SHA-256; CURRENT / SUPERSEDED | project org | revenue records | no |
| `farmer_entitlements` (`farmer_revenue_shares` lines) | per payee per revenue record amount | settlement run | immutable | project org | run, revenue record, project_farm, rights, agreement | no |
| `payouts` (`farmer_payouts`) | money owed to one payee in one run | entitlements | state machine (D20) | project org | entitlements, bank account snapshot | no |
| `payout_transactions` | each execution attempt (bank reference, proof) | executor / adapter | append-only | project org | payout | no |
| `payout_events` | provider events | adapter | append-only, unique (provider, event id) | — | payout | no |
| `payout_reconciliations` | statement matching results | reconciler | append-only | project org | payout transactions | no |
| `payout_adjustments` | recoveries / corrections | finance | immutable | project org | original payout / revenue reversal | only if D29 |

No table stores a credit quantity or ownership (Phase 9B remains the only ownership source). Money: `Numeric(19,4)` + currency (Phase 10
pattern).

## 25. Proposed migration

`0016_phase11_financials` (the repository's latest revision is `0015`). Content depends on the decisions: the confirmed subset of §24
tables; sequences (e.g. `REV-` revenue, `SET-` settlement run, `PAYO-` payout — names to be confirmed; note `REV` is already used by 9B
reversals, so revenue needs another prefix, e.g. `RVN`); filtered unique indexes (one recognition per order item event, one ACTIVE
entitlement per revenue record + payee + run lineage, one open payout per payee + run, request keys); CHECK constraints (amount > 0 or
explicit negative adjustment rows, approver ≠ calculator, executor ≠ approver, currency code length); append-only triggers (events,
transactions, reconciliations, revenue, entitlements); final-state triggers (payouts, runs); documents categories (D25); downgrade guard
refusing while any Phase 11 row exists.

## 26. Proposed API (areas only)

| Endpoint | Actor / permission | Scope | Precondition | Idempotency | Audit |
|---|---|---|---|---|---|
| GET `/revenue?project_id&period` | revenue.read | seller / project org | — | — | — |
| POST `/revenue/recognize` (only if recognition is not automatic) | payouts.calculate | org | item delivered / paid (D8) | key | REVENUE_RECOGNIZED |
| GET/POST `/payouts/sharing-rules` (+ `/{id}/submit`, `/approve`) | sharing.manage / sharing.approve | project org | D2 | key | SHARING_RULE_* |
| GET/POST `/payouts/costs` | costs.manage | project org | D6 | key | PROJECT_COST_* |
| POST `/payouts/settlement-runs` | payouts.calculate | project org | approved rule; recognized revenue | key | SETTLEMENT_RUN_CALCULATED |
| GET `/payouts/settlement-runs/{id}` (+ `/lineage`) | payouts.read | project org | — | — | — |
| POST `/payouts/{id}/approve` · `/reject` | payouts.approve (≠ calculator) | project org | CALCULATED / PENDING_APPROVAL | key | PAYOUT_APPROVED / REJECTED |
| POST `/payouts/{id}/documents` · `/execute` (bank ref + proof) · `/fail` | payouts.execute (≠ approver) | project org | APPROVED / PAYMENT_PENDING | key | PAYOUT_EXECUTION_RECORDED / FAILED |
| POST `/payouts/{id}/reconcile` | payouts.reconcile | project org | PAID | key | PAYOUT_RECONCILED |
| GET `/payouts/me` | farmers.self | own farmer | — | — | — |

No public webhook (no provider contract). `/payouts` routes must then be allowed by deliberately narrowing the existing boundary tests.

## 27. Proposed UI

- **Farmer** (`farmers.self`): Earnings / entitlements (per project and period, own only), payout status and history, payout statements.
  Never other farmers, bank numbers (last4 only), audit or project financials.
- **Project / finance:** Revenue (recognized per order item, reversals), Sharing rules (if D2), Costs (if D6), Settlement runs (inputs,
  snapshot hash, lines), Payout queue (approve / execute / fail), Reconciliation.
- **Admin / compliance:** none new by default; bank verification stays in the Phase 2 farmer screens.

## 28. DEMO / TEST / LIVE

| Environment | Behaviour |
|---|---|
| DEMO | no revenue, entitlement, payout, bank transfer or earnings is fabricated — there are no registry-issued credits and no orders (Phase 10). Screens show an honest DEMO note. Contradiction C1: §43 seeds "1 payout" |
| TEST | synthetic issued credits → completed orders → payments → revenue → settlement run (with a TEST-only approved sharing rule) → payouts → TEST adapter → reconciliation; concurrency races |
| LIVE | ManualPayoutAdapter only; manual evidence + second-person confirmation / reconciliation; no fake payout success |

## 29. Phase 12 boundary

Deferred to Phase 12: Celery / Redis workers, scheduled settlement runs, scheduled reconciliation, notification workers ("Payout
completed" email / SMS), webhook queues, automatic recurring settlement, bulk bank-file generation jobs.

## 30. Contradictions / ambiguities (14)

| # | Contradiction / ambiguity |
|---|---|
| C1 | §43 seeds "1 payout" in DEMO vs the established honest-DEMO rule (no issued credits → no revenue → no payout) and §1.13 |
| C2 | §4.16 gives "calculate farmer share" and "approve payouts" to one role vs creator ≠ approver (resolved per person) |
| C3 | §26 "project agreement / configured revenue-share rules" vs repo: agreements hold only free text; `share_pct` is a carbon-rights share, not stated as revenue share |
| C4 | §26 "do not calculate farmer payout directly from a UI-entered number" vs any configured rule must be entered by someone — needs an approval-controlled, versioned configuration |
| C5 | §26 ordering (costs / fees before farmer share) suggests deduction; no rule states that costs reduce the farmer share |
| C6 | a platform fee is unclear when Phase 10 D16 makes the seller the payee and the platform collects no money |
| C7 | Phase 10 lets any project developer holding credits (including credits received by 9B internal transfer) sell them; the spec is silent on whether original farmers share in secondary sales; the seller may differ from the project organization |
| C8 | §42 lists `PaymentProvider` but no payout provider; §26 "Bank / Payment Provider"; §49 has only `PAYMENT_PROVIDER` |
| C9 | farm-level calculation outputs are calculated tCO2e; using them to allocate issued-credit revenue would blur calculated vs issued (§1.11, rule 12) |
| C10 | carbon-rights holders may be organizations / farmer groups / landowners, but only farmers have bank accounts |
| C11 | farmer agreement counterparty organization, project organization and seller organization may differ — who owes the farmer is undefined |
| C12 | §46 #39 / §54 ("payout can be approved", "farmer payout completed") vs the DEMO honesty rule — a DEMO payout cannot be completed honestly |
| C13 | Phase 10 refunds after delivery are money only (credits stay with the buyer) — whether such revenue is reversed for farmers is undefined |
| C14 | spec §52 requires `docs/payout-workflow.md` while the API section (§29) lists `/api/v1/payouts` only — revenue / cost endpoints are not named |

## 31. Open decisions

See the decision table (§ "Decision table") — **42 open decisions** (D1–D42).

## 32. Recommended locked decisions (to propose to the business — not locked here)

1. Entitlement source: a **new versioned, second-person-approved revenue-share configuration per project**, whose versions reference the
   signed farmer agreements and carbon-rights records it implements (D1, D2). Keep `share_pct` as carbon-rights evidence only, unless the
   business confirms it is the economic share.
2. Revenue recognized **per order item when its 9B delivery completes** (payment already confirmed by then; credits actually transferred),
   recorded in the T4 transaction; INTERNAL and REGISTRY treated the same (D8, D9).
3. No fee and no commission in the first Phase 11 cut unless the business supplies them; costs only if the business defines categories
   and the deduction rule (D4–D7).
4. Settlement runs are manually triggered, immutable, input-hashed, superseded never edited; payouts per payee per run (D18–D20, D37).
5. Payees limited to farmers with a VERIFIED bank account in the first cut; organizations / groups / landowners as payees need a bank
   model (D22, D23).
6. ManualPayoutAdapter + TEST-only adapter; no webhook (D24).
7. One currency per run = the revenue currency; no FX; rounding to the currency's minor unit with a defined remainder rule (D26, D27).
8. Refund after payout: no automatic recovery; record a negative adjustment carried into the next run, or manual remediation — business
   decides (D29, D30).
9. Tax: an external boundary; payout statement "not a tax document" (D31, D32).
10. DEMO: no financial records (D35).

## 33. Proposed implementation sequence (after decisions)

1. Confirm D1–D42 (at least the "must confirm" ones).
2. Migration 0016 + models + triggers; narrow boundary tests for `/payouts` (and revenue routes) deliberately.
3. Revenue recognition hook in the Phase 10 T4 delivery transaction (composable), reversal on refund.
4. Sharing-rule configuration with approval (if confirmed); cost records (if confirmed).
5. Settlement run (snapshot + hash), entitlements, payouts; lineage endpoint.
6. Payout lifecycle with ManualPayoutAdapter, documents, reconciliation; TEST adapter.
7. Farmer self-service views; finance UI.
8. Tests: functional, RBAC / SoD, isolation, real concurrency races (§23), DEMO honesty; E2E; docs (`payout-workflow.md`).

## 34. Risks

- Implementing any share, fee or allocation without a confirmed rule would invent business / legal terms.
- Paying farmers without a legally reviewed entitlement source (agreement terms) exposes the project developer.
- Secondary sales and seller ≠ project organization (C7, C11) can create obligations the platform cannot trace to an agreement.
- Refunds after payout without a recovery policy create unrecoverable amounts.
- Bank-detail changes near payout time are a fraud vector — needs a hold / re-approval rule.
- Tax withholding (e.g. TDS) may be legally required in some jurisdictions; the platform has no tax configuration.
- Manual payouts depend on human evidence and reconciliation; mistakes are only detectable at reconciliation.

---

## Critical questions — answers

| # | Question | Answer |
|---|---|---|
| 1 | Source of farmer economic entitlement | **Not defined.** Implied by §4.16 / §26 / §46 #38 ("according to configured agreement"); candidates: agreements (free text only), `project_carbon_rights.share_pct` (rights share), new configuration (§7.14). OPEN D1 |
| 2 | Is the farmer share defined anywhere? | No (no percentage, amount or formula) |
| 3 | Benefit sharing separate from revenue sharing? | No separate definition; "co-benefits" are environmental listing disclosures |
| 4 | Calculation base | Undefined (gross vs net — interpretations I1–I4). OPEN D3 |
| 5 | Fees defined? | No (Phase 10 D9: none in the marketplace) |
| 6 | Commissions defined? | No |
| 7 | Project costs defined? | Named only (§7.14 `project_costs`, §4.16, §26); no categories or treatment |
| 8 | Do costs reduce farmer share? | Undefined; §26 ordering suggests it (C5). OPEN D6 |
| 9 | When is revenue recognized? | Undefined; recommended: order-item delivery completion. OPEN D8 |
| 10 | When is farmer entitlement created? | Undefined; recommended: in an approved settlement run over recognized revenue. OPEN D17 |
| 11 | When is payout payable? | Undefined; recommended: after run approval. OPEN D18 |
| 12 | What triggers payout? | Undefined; manual settlement run (no schedule in Phase 11). OPEN D18, D19 |
| 13 | Who approves? | Finance / Payout Manager (§4.16), a person other than the calculator |
| 14 | Who executes? | Undefined; proposed a finance user ≠ approver, recording the bank reference + proof. OPEN D21 |
| 15 | Who reconciles? | Finance (§4.16 "track bank/payment status"); SoD vs executor OPEN D21 |
| 16 | Which bank account? | The farmer's VERIFIED (primary) `farmer_bank_accounts` row — requirement OPEN D23; non-farmer payees have no bank model (C10) |
| 17 | Bank details change? | New account starts PENDING_VERIFICATION; effect on pending payouts OPEN D23 |
| 18 | After refund? | Revenue reversal record; entitlement impact OPEN D10 |
| 19 | After chargeback? | Not modelled; OPEN D11 |
| 20 | After payout already happened? | No recovery policy; OPEN D29, D30 |
| 21 | Sale with credits of multiple farms | No authoritative allocation key; OPEN D12, D14 |
| 22 | Multiple farmers on one farm | Carbon-rights records with `share_pct` exist; economic meaning OPEN D13 |
| 23 | Allocation rules change | New approved rule version; runs reference the version used. OPEN D2, D37 |
| 24 | Historical allocation immutable? | Recommended yes (runs immutable, superseded only). OPEN D37 |
| 25 | FX required? | Not specified; recommended none. OPEN D26 |
| 26 | Tax required? | Not specified; external boundary. OPEN D31 |
| 27 | Invoice required? | §7.13 lists `invoices` but no rules; Phase 10 deferred; OPEN D32 |
| 28 | Payout provider specified? | No |
| 29 | Manual payout required? | Implied by §1.13 (controlled manual workflow when no API); recommended ManualPayoutAdapter. OPEN D24 |
| 30 | Records needing immutable history | revenue records, rule versions, settlement runs, entitlements, payout transactions / events / reconciliations, adjustments, approvals |
| 31 | Phase 11 migration | `0016_phase11_financials` |
| 32 | Deferred to Phase 12 | workers, scheduled settlement / reconciliation, notifications, webhook queues, recurring settlement, bulk bank files |

---

## Decision table

Legend for "Confirm?": **Yes** = must be confirmed before implementation; Rec = a recommendation exists but needs sign-off.

| D | Topic | Current requirement | Proposed decision | Reason | Tables | APIs | UI | Tests | Confirm? |
|---|---|---|---|---|---|---|---|---|---|
| D1 | Entitlement source | implied (§4.16, §26, §46 #38); none in repo | new versioned revenue-share configuration referencing agreements / rights | agreements are free text; share_pct is rights | revenue_share_rules(+versions) | sharing-rules | sharing rules | rule approval | **Yes** |
| D2 | Rule configuration model | §26 "configured revenue-share rules" | per project, versioned, second-person approval | §26 forbids UI-entered payout numbers | revenue_share_rule_versions | sharing-rules | sharing rules | versioning, SoD | **Yes** |
| D3 | Calculation base | undefined (I1–I4) | business chooses gross or net | no rule | settlement_runs | runs | runs | calc tests | **Yes** |
| D4 | Platform / seller / buyer fee, commission | none (Phase 10 D9) | none unless supplied | not defined | fee records (if any) | — | — | — | **Yes** |
| D5 | Third-party fees (registry, VVB, processing) | undefined | treat as project costs if D6 | no rule | project_costs | costs | costs | — | **Yes** |
| D6 | Project costs tracked & deducted? | named only | business defines categories + deduction rule | §26 ambiguity | project_costs | costs | costs | deduction tests | **Yes** |
| D7 | Cost granularity | undefined | project + monitoring period | only reachable keys | project_costs | costs | costs | — | **Yes** |
| D8 | Revenue recognition event | undefined | order-item delivery completion (T4) | money received + credits transferred | revenue_records | revenue | revenue | race 5 | Rec |
| D9 | Recognition granularity | — | per order item | keeps batch lineage | revenue_records | revenue | revenue | — | Rec |
| D10 | Refund → recognized revenue | undefined | reversal record | immutability | revenue_records | revenue | revenue | refund tests | **Yes** |
| D11 | Chargebacks | not modelled | not supported until a provider exists | no provider | — | — | — | — | **Yes** |
| D12 | Allocation key across farms | none | business supplies (agreement share / approved allocation table) | no authoritative key | entitlements / rules | runs | runs | allocation tests | **Yes** |
| D13 | Multiple holders per farm | share_pct exists (rights) | confirm whether share_pct is economic; sum rule | ambiguity C3 | rights / rules | — | — | — | **Yes** |
| D14 | Time eligibility (which farms share a batch) | dates exist | ACTIVE participation + VERIFIED rights during the batch's monitoring period | only available dates | entitlements | runs | runs | date tests | **Yes** |
| D15 | Agreement termination / rights transfer | statuses exist | accrued vs future entitlement rule | undefined | entitlements | runs | — | — | **Yes** |
| D16 | Secondary sales | Phase 10 allows PD resale of held credits | business decides farmer participation | C7 | revenue_records | revenue | — | — | **Yes** |
| D17 | Entitlement creation | undefined | in an approved settlement run | immutability | farmer_entitlements | runs | runs | — | Rec |
| D18 | Payout trigger / aggregation | undefined | manual run; one payout per payee per run | no schedule | payouts | payouts | queue | race 1, 6 | **Yes** |
| D19 | Settlement period / cycle | undefined | none in Phase 11 (manual); cycle = business | no rule | settlement_runs | runs | runs | — | **Yes** |
| D20 | Payout lifecycle | §35 PAYOUT_APPROVED, §33 Payout completed | candidate in §10 | needs explicit states | payouts | payouts | queue | lifecycle | **Yes** |
| D21 | SoD: calculator / approver / executor / reconciler | §4.16 one role | per-person: calculator ≠ approver ≠ executor; reconciler TBD | platform SoD pattern | payouts | payouts | queue | SoD tests | **Yes** |
| D22 | Payee types | rights holders incl. orgs; banks only for farmers | farmers only in first cut | C10 | payouts | payouts | — | — | **Yes** |
| D23 | Bank requirement / change hold | VERIFIED workflow exists | VERIFIED required; change → hold + re-approval | fraud risk | payouts | payouts | queue | race 8 | **Yes** |
| D24 | Payout adapter | none; §1.13 manual workflow | ManualPayoutAdapter + TEST adapter; no webhook | no contract | payout_transactions/events | execute, reconcile | queue | adapter tests | Rec |
| D25 | Documents | none | remittance proof, statement, farmer statement (not a tax doc) | evidence pattern | documents | documents | — | doc tests | **Yes** |
| D26 | Currency / FX | Phase 10 one currency, no FX | one currency per run = revenue currency; no FX | no FX rule | runs | runs | — | — | Rec |
| D27 | Rounding & remainder | minor-unit validation exists | round per line to minor unit; remainder rule to decide | must not leak money | entitlements | runs | — | rounding tests | **Yes** |
| D28 | Minimum payout threshold | undefined | none unless defined | no rule | payouts | — | — | — | **Yes** |
| D29 | Refund after payout | undefined | business: carry-forward negative adjustment vs manual remediation | no policy | payout_adjustments | adjustments | queue | race 4 | **Yes** |
| D30 | Holdback / reserve | undefined | none unless defined | no rule | runs | — | — | — | **Yes** |
| D31 | Tax / withholding | undefined; Phase 10 deferred | external boundary; no rates encoded | no rule | — | — | — | — | **Yes** |
| D32 | Invoices / tax documents | §7.13 `invoices` named only | deferred | no rule | — | — | — | — | **Yes** |
| D33 | Visibility / data minimization | farmers.self exists | farmer: own only; project org: own farmers; platform: none | §31, rule 13 | all | all | all | isolation | Rec |
| D34 | RBAC | §4.16 finance duties | minimum set in §19 | least privilege | permissions | all | nav | RBAC | **Yes** |
| D35 | DEMO | honest-DEMO rule vs §43 "1 payout" | no financial records in DEMO | C1, C12 | — | — | DEMO note | E2E | Rec |
| D36 | TEST | synthetic chain | full synthetic path + races | quality | — | — | — | all | Rec |
| D37 | Immutability / corrections | append-only patterns | runs immutable, supersede; adjustments not edits | audit | all | all | — | trigger tests | Rec |
| D38 | Organization ownership of revenue / payouts | payee = seller (Phase 10) | revenue: seller org; payouts: project org — confirm when they differ | C11 | revenue / payouts | all | — | isolation | **Yes** |
| D39 | Recognition of INTERNAL vs REGISTRY | no difference defined | treat the same | no rule | revenue_records | — | — | — | Rec |
| D40 | Farmer statement content | §36 farmer report incl. payout | own entitlements / payouts, lineage to batch | data minimization | — | payouts/me | farmer earnings | — | Rec |
| D41 | Migration | latest 0015 | `0016_phase11_financials` | sequence | all | — | — | alembic cycle | Rec |
| D42 | Phase 12 boundary | spec §34 background jobs | as §29 | phase plan | — | — | — | — | Rec |

**Totals:** 42 open decisions (D1–D42; 29 marked "must confirm", 13 with a recommendation needing sign-off), 14 contradictions /
ambiguities (C1–C14).
