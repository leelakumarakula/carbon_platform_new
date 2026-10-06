# End-to-end test guide — every role, every field

One project, taken from an empty catalog to a farmer payout through the UI. For every step this guide names the **role** (and test login),
the **screen**, **every field** on the form with its rule, the **value to enter**, the **button**, and the **expected result**.

- Calculation path: Gold Standard SOC Framework **GS402**, module **GS402-IT-A3** (Improved Tillage, Approach 3 — IPCC stock-change
  factors). It needs no soil sampling and no laboratory work. Field sampling and the laboratory are tested in [Appendix A](#appendix-a--field-sampling-and-laboratory-separate-project).
- Values are **test values** shaped like IPCC factors, not a real project's. With a ~100 ha farm they give about **170 credits**, enough
  to test issuance, the ledger, the marketplace and the payout.
- Verified through the UI up to the calculation run; Stages 10–14 follow the code (`backend/app/services/*`, `frontend/src/app/*`).
  Report mismatches to the team lead with the error code.
- 🔎 marks a **negative test**: the action must be refused. The refusal proves the separation-of-duties rule.

Contents: [0 Setup](#0--setup) · [Role matrix](#role-matrix--who-fills-what) · [1 Catalog](#stage-1--catalog) ·
[2 Methodology](#stage-2--methodology-with-the-calculation-module) · [3 Farmer](#stage-3--farmer) · [4 Farm](#stage-4--farm-about-100-ha) ·
[5 Project](#stage-5--project-and-eligibility) · [6 Lock](#stage-6--lock-the-methodology) · [7 MRV](#stage-7--mrv-plan-monitoring-period-stratum) ·
[8 Data](#stage-8--factor-data-and-the-mrv-dataset) · [9 Calculation](#stage-9--calculation-and-calculation-qa) ·
[10 Verification](#stage-10--internal-readiness-and-vvb-verification) · [11 Registry](#stage-11--registry-submission-and-issuance) ·
[12 Ledger](#stage-12--credit-ledger) · [13 Marketplace](#stage-13--marketplace) · [14 Payout](#stage-14--revenue-sharing-settlement-and-farmer-payout) ·
[Appendix A](#appendix-a--field-sampling-and-laboratory-separate-project) · [Troubleshooting](#troubleshooting)

---

## 0 — Setup

### 0.1 Servers
- Backend on port 8000, `npx ng serve` in `frontend`, open http://localhost:4200.
- Start the backend with `LOGIN_RATE_LIMIT_PER_MINUTE=100` in `backend/.env` — the test signs in many times.

### 0.2 House rules (apply to every stage)

| Rule | Detail |
|---|---|
| Reason dialog | Almost every action button opens **"Reason (recorded in the audit log)"**: required, 3–1000 characters. Type e.g. `ok test`. The confirm button repeats the action name. |
| Dates | Date boxes read **month/day/year**. `06/01/2026` = 1 June 2026; `01/06/2026` = 6 January. |
| Uploads | Checked by content, not by extension. PDF, PNG, JPEG, WebP; max 15 MB; empty files refused. Evidence for registry, ledger, payments and payouts is **PDF only**. Keep 3–4 small PDFs and one JPG ready. |
| Separation of duties | The person who submits something can never approve it. Each step names the second login. |
| Browser windows | Keep 2–3 windows (normal, Incognito, a second browser) so you switch users without signing out. |
| First sign-in | A user with a temporary password lands on **Set your password**: Current password, New password (12+ characters, letters **and** digits, max 72 bytes, no leading/trailing spaces, different from the old one), Confirm new password → **Change password**. |
| Several testers on one database | Each tester has a number (`01`, `02`, …). Put it in ID numbers, serials and references where the step says *+ tester no.*, and shift the farm corners (Stage 4). Codes such as `GS`, `GS402` exist only once — the first tester creates them, the others reuse them. |

### 0.3 Organizations — role: **Platform Admin** (`leelak@vayublue.com`)
Screen: **Administration → Organizations → New organization**

| Field | Required | Rule | Enter |
|---|---|---|---|
| Code | Yes | 2–40 letters, digits, `-`, `_`; starts with a letter; stored upper case; unique | see table below |
| Name | Yes | 2–200 characters | see table below |
| Type | Yes | Project developer · Field partner · Farmer group · Laboratory · VVB / ACVA · Registry · Buyer | see table below |
| Country (ISO code) | No | 2 letters | `IN` |
| Registration number | No | max 100 | empty |
| Contact email | No | valid email | empty |

Button **Create**. New organizations are **Active** at once (no activation step).

| Organization | Code | Type | Needed for |
|---|---|---|---|
| Carbon Platform Operator | — | Platform operator | exists (created by the seed) |
| varsapradaya_developer | — | Project developer | exists: owns farmers, farms, project, credits |
| soiltestlab | — | Laboratory | exists: Appendix A |
| verify_co | — | VVB / ACVA | exists: Stage 10 |
| **Test Registry** | `TESTREG` | **Registry** | **create** — Stage 11 (a registry has no users) |
| **Test Buyer** | `TESTBUYER` | **Buyer** | **create** — Stages 12–13 |

### 0.4 Users — role: **Platform Admin**
Screen: **Administration → Users → New user**

| Card | Field | Required | Rule |
|---|---|---|---|
| Account | Email | Yes | valid, unique, max 320 |
| | Full name | Yes | 2–200 |
| | Phone | No | digits, spaces, `+ ( ) -` |
| | Temporary password | Yes | pre-filled random value (refresh icon makes a new one); share it with the tester |
| Organization | Organization | for organization roles | "None (platform staff)" for platform roles; otherwise the organization (membership is created automatically) |
| | Job title | No | max 120 |
| Roles | **Add role** → Role | Yes | Organization roles apply in the chosen organization; platform roles apply everywhere |

Button **Create user**. The role must sit in the right organization type: a lab role in a Laboratory, VVB reviewer in a VVB, Buyer in a
Buyer organization. A mismatched role is granted without error but never works.

| Login | Organization | Role | Scope |
|---|---|---|---|
| leelak@vayublue.com | none | Platform Admin | platform |
| ms1@yopmail.com | none | Methodology Specialist | platform |
| ms2@yopmail.com | none | Methodology Specialist | platform |
| pm@yopmail.com | varsapradaya_developer | Project Manager / Project Developer | organization |
| qa@yopmail.com | varsapradaya_developer | Data Quality / QA Officer | organization |
| gis@yopmail.com | varsapradaya_developer | GIS / Remote Sensing Specialist | organization |
| mrv@yopmail.com | varsapradaya_developer | MRV Manager | organization |
| sup@yopmail.com | varsapradaya_developer | Field Supervisor | organization |
| col@yopmail.com | varsapradaya_developer | Field Collector / Field Agent | organization |
| analyst@yopmail.com | varsapradaya_developer | Carbon Calculation Analyst | organization |
| labmgr@yopmail.com | soiltestlab | Lab Manager / Lab QA | organization |
| labtec@yopmail.com | soiltestlab | Lab Technician | organization |
| vvb@yopmail.com | verify_co | VVB / ACVA Reviewer | organization |
| **credits@yopmail.com** | varsapradaya_developer | Credit Manager | organization — **create** |
| **fin1@yopmail.com** | varsapradaya_developer | Finance / Payout Manager | organization — **create** |
| **fin2@yopmail.com** | varsapradaya_developer | Finance / Payout Manager | organization — **create** |
| **fin3@yopmail.com** | varsapradaya_developer | Finance / Payout Manager | organization — **create** |
| **buyer@yopmail.com** | Test Buyer | Buyer | organization — **create** |
| **compliance@yopmail.com** | none | Marketplace Compliance Officer | platform — **create** |
| vvb2@yopmail.com *(optional)* | verify_co | VVB / ACVA Reviewer | organization — only for the optional VVB findings test |
| farmer@yopmail.com *(optional)* | varsapradaya_developer | Farmer | organization — only for the optional "My payouts" check |

A payout needs **three different Finance Managers**: fin1 calculates, fin2 approves and reconciles, fin3 executes.

---

## Role matrix — who fills what

| Role (login) | Fills in / creates | Approves / confirms (as the second person) |
|---|---|---|
| Platform Admin (leelak) | Organizations, users, standard, activity | — |
| Methodology Specialist (ms1) | Methodology, version details, calculation module, applicability rules; project candidate evaluation and recommendation | — |
| Methodology Specialist (ms2) | — | Methodology version |
| Project Manager (pm) | Farmer, KYC submission, consent, agreement, farm, boundary, ownership, project, farms, standard/activity, crediting period, baseline; methodology lock; VVB assignment and READY package; registry account, registration, submission, issuance; revenue-share version, farm allocation, farmer bank account | — |
| QA Officer (qa) | Internal calculation findings | KYC, carbon rights, eligibility, MRV plan, MRV dataset, calculation QA and approval, verification readiness, issuance, ledger opening / transfers / retirements, marketplace delivery |
| GIS Specialist (gis) | Stratum | Ownership record, farm (GIS review), project boundary |
| MRV Manager (mrv) | MRV plan, monitoring period, factor values, dataset | — |
| Field Supervisor (sup) | — | Stratum (Appendix A: also design, field records, shipment) |
| Calculation Analyst (analyst) | Calculation run, finding responses, calculation report, verification readiness | — |
| VVB Reviewer (vvb) | Conflict-of-interest declaration, VVB decision with report | — |
| Credit Manager (credits) | Ledger opening request, retirement and transfer requests, marketplace listing | — |
| Finance Manager fin1 | Settlement run, payouts | Listing price, buyer payment, revenue-share version, farm allocation, bank account |
| Finance Manager fin2 | Reconciliation | Settlement run, payouts |
| Finance Manager fin3 | Payout execution and "paid" record | — |
| Buyer (buyer) | Buyer profile, KYC documents, order, payment record, retirement of own credits | — |
| Compliance Officer (compliance) | — | Buyer KYC |

---

## Stage 1 — Catalog
**Role: Platform Admin (leelak).** Screen: **Projects → Standards & activities**. If `GS` and `AGR-SOC` already exist, check them and go to Stage 2.

**1.1 Standard** (card "Standards / crediting routes")

| Field | Required | Rule | Enter |
|---|---|---|---|
| Code | Yes | 2–40, letters/digits/`-`/`_`, starts with a letter; unique | `GS` |
| Name | Yes | 2+ characters | `Gold Standard for the Global Goals` |
| Programme owner | No | free text | `Gold Standard Foundation` |
| Type | Yes | Voluntary · Compliance · Other | Voluntary |
| Official source URL | No | starts with http(s):// | empty |

Button **Add standard** → "Standard added."

**1.2 Activity** (card "Activities")

| Field | Required | Rule | Enter |
|---|---|---|---|
| Code | Yes | as above | `AGR-SOC` |
| Name | Yes | 2+ characters | `Agriculture - soil organic carbon` |
| Offered under | No in the form, needed in practice | multi-select of standards | tick **Gold Standard for the Global Goals** |

Button **Add activity** → the row shows "Offered under: Gold Standard for the Global Goals". Without that link the activity never appears on a project.

---

## Stage 2 — Methodology with the calculation module
**Roles: Methodology Specialist ms1 (author), ms2 (approver).** Screen: **Methodologies**.

> **The one step that cannot be undone.** The calculation module is chosen on the version's **Calculation tab while it is a draft**.
> An approved version can never change its module. Check that the chosen module code ends in **`-A3`**.

**2.1 Methodology** — ms1, card "Add a methodology" (skip if `GS402` exists)

| Field | Required | Rule | Enter |
|---|---|---|---|
| Code | Yes | 2–40, letters/digits/`.`/`-`/`_`; must be **exactly `GS402`** for the GS modules | `GS402` |
| Name | Yes | 2+ | `Gold Standard SOC Framework` |
| Standard / route | Yes | select | Gold Standard for the Global Goals |
| Activities | Yes | at least one; only activities offered under the standard | Agriculture - soil organic carbon |
| Official source URL | No | http(s) | empty |

Button **Add methodology**.

**2.2 Draft version** — ms1, same page

| Field | Required | Rule | Enter |
|---|---|---|---|
| New version label | Yes | 1–30; unique per methodology; must be `1.0` or `1.0` + `-`/space/`_`/`/` + suffix for the GS modules | `1.0` — or, if `1.0` already exists, `1.0-IT-A3-` + tester no. (e.g. `1.0-IT-A3-02`) |

Button **New draft version** (copies the rules of the latest version) → **Open**. Version page: status **Draft**.

**2.3 Version details** — ms1

| Field | Required | Rule | Enter |
|---|---|---|---|
| Effective from | Yes to submit | date; must be on or before the project start (Stage 5) | `01/01/2020` |
| Effective to | No | ≥ Effective from | empty |
| Source (publisher, title) | Yes to submit (source, URL or document) | max 300 | `Gold Standard SOC Framework Methodology v1.0` |
| Source URL | No | http(s) | empty |

Button **Save details**.

**2.4 Calculation module** — ms1, tab **calculation**

| Field | Required | Rule | Enter |
|---|---|---|---|
| Calculation module | Yes for a calculation | only modules for GS402 / 1.0 are enabled | **GS 402 + 402.1 Improved Tillage - Approach 3 (IPCC stock change factors, Eqs. 4 and 6) · v1.0.0** |

Button **Use this module** → dialog **Use module** (reason). Expected:
- header badge **Module: GS402-IT-A3**; the module card title ends in `GS402-IT-A3 · v1.0.0`;
- "Calculation steps": 8 rules `GS-BSL` … `GS-NET`;
- "Data the module needs": `GS_SOC_REF`, `GS_F_LU`, `GS_F_MG_BL`, `GS_F_I_BL`, `GS_F_MG_PR`, `GS_F_I_PR`, `GS_T_BL`, `GS_T_PR` (per stratum),
  `GS_U_…` uncertainties, fertiliser/fuel/yield (per farm), `GS_PAA` (project);
- no "Sampling settings" line (only `-A1` modules have one).

The five GS402 options look alike: `-A1` modules need soil sampling, two campaigns and lab results.

**2.5 Applicability rules** — ms1, tab **applicability**, one **Add rule** per row

| Field | Rule A1 | Rule A2 | Rule |
|---|---|---|---|
| Code | `A1` | `A2` | `[A-Z][A-Z0-9_.-]`, unique in the version |
| Title | `Standard is GS` | `Activity is AGR-SOC` | 2–300 |
| Category | Standard | Activity | select |
| Fact key | `standard_code` | `activity_code` | lower-case `[a-z][a-z0-9_]` |
| Operator | EQUALS | EQUALS | select |
| Expected value (JSON) | `"GS"` | `"AGR-SOC"` | valid JSON — **keep the quotes** |
| If it fails | Not applicable | Not applicable | Not applicable · Evidence required · Needs information |
| Evidence requirement | empty | empty | optional |
| Source reference | empty | empty | optional |

**2.6 Submit and approve**

| # | Role | Action | Expected |
|---|---|---|---|
| 2.6a | ms1 | Check the badge still says **Module: GS402-IT-A3** → **Submit for approval** (reason) | **In review** |
| 2.6b 🔎 | ms1 | Try **Approve** | Refused — submitter cannot approve |
| 2.6c | ms2 | Open the version → **Approve** (reason) | **Approved**; rules read-only; "Calculation: Not production ready" is expected |

---

## Stage 3 — Farmer
**Roles: Project Manager (pm) registers; QA Officer (qa) verifies KYC.** Screen: **Farmers**.

**3.1 Register farmer** — pm, **Farmers → Register farmer**

| Field | Required | Rule | Enter |
|---|---|---|---|
| Managing organization | Yes | active Project developer / Field partner / Farmer group | varsapradaya_developer |
| Full name | Yes | 2–200 | `Ramesh Patil` |
| Gender | No | Not recorded · FEMALE · MALE · OTHER · UNDISCLOSED | MALE |
| Preferred language (ISO code) | No | e.g. `mr`, `hi`, `en-IN` | `mr` |
| Primary phone | Needed to register | `+` and 6–30 digits/spaces/`()-` | `+91 98765 43210` |
| Village / Sub-district / District / State | Village **or** District needed to register | max 120 each | `Ozar` / empty / `Nashik` / `Maharashtra` |
| Country (ISO code) | Yes | 2 letters | `IN` |

Button **Create farmer** → `FRM-2026-…`, **Draft**. Then header **Register** (reason) → **Registered**.

**3.2 KYC** — pm, tab **KYC**

| Field | Required | Rule | Enter |
|---|---|---|---|
| ID type | Yes | National ID · Voter ID · Tax ID · Passport · Driving licence · Other | National ID |
| ID number | Yes | 4–40 characters; only last 4 + fingerprint stored | `1234 5678 90` + tester no. (e.g. `1234 5678 9002`) |
| Attach ID document | Yes | PDF/PNG/JPG/WebP | any PDF |

Button **Submit for review** → **KYC pending**, number shown as `••••` + last 4.

| # | Role | Screen / field | Enter | Expected |
|---|---|---|---|---|
| 3.3 🔎 | pm | KYC tab | — | "You submitted this KYC, so another reviewer must decide" |
| 3.4 | qa | KYC tab → Review notes (required, 3–1000) · "different person" checkbox (only if a duplicate is flagged) | `ID checked` → **Verify KYC** | **KYC verified** |

**3.5 Consent** — pm, tab **Consents**

| Field | Required | Rule | Enter |
|---|---|---|---|
| Consent | Yes | active consent types | Personal data processing (v1) · required (pre-selected) |
| Consent text version | Yes | 1–40 | `DATA_PROCESSING-v1` (pre-filled) |
| Captured by | Yes | Paper signed · Digital signature · Verbal recorded · OTP · Online checkbox | Paper signed |
| Language | No | ISO code | `mr` |

Button **Record consent** → Consents (1). Then header **Activate** (reason) → **Active**.

**3.6 Agreement** — pm, tab **Agreements**

| Field | Required | Rule | Enter |
|---|---|---|---|
| Agreement type | Yes | `[A-Za-z][A-Za-z0-9_]{2,39}` | `PROGRAM_PARTICIPATION` |
| Template version | Yes | 1–40 | `v1` |
| Effective from | No | date | `06/01/2026` |
| Terms summary | No | max 4000 | `Participation and carbon rights` |

Button **Create agreement** → **Draft**; then **Upload signed copy** (PDF/JPG) → **Signed** (`AGR-2026-…`). Note the agreement code for Stage 14.

The bank account is added in Stage 14.

---

## Stage 4 — Farm (about 100 ha)
**Roles: Project Manager (pm) records; GIS Specialist (gis) verifies.** A 1 km × 1 km plot — a 2.2 ha plot earns under one credit, rounded down to 0.

**4.1 Create farm** — pm, farmer page → **Farms** tab → **Add farm**

| Field | Required | Rule | Enter |
|---|---|---|---|
| Farmer | Yes | registered, not suspended | Ramesh Patil |
| Farm name | Yes | 2–200 | `North block` |
| Land tenure | Yes | Owned · Leased · Sharecropped · Community · Government allotted · Customary · Other | Owned |
| Declared area (ha) | No | > 0; only a warning if > 25 % off the measured area | `100` |
| Village / District / State | No | pre-filled from the farmer | keep |
| Country | Yes | 2 letters | `IN` |

Button **Create farm and draw boundary** → `FARM-2026-…`, **Draft**, Boundary tab open.

**4.2 Boundary** — pm, tab **Boundary**

| Field | Rule | Enter |
|---|---|---|
| Paste several corners | one `latitude, longitude` per line; at least 3 corners; closed automatically | the four lines below |

```
20.1000, 73.7000
20.1000, 73.7096
20.1090, 73.7096
20.1090, 73.7000
```
Tester 2 adds `0.02` to every latitude, tester 3 adds `0.04`, … so farms do not overlap.

Buttons **Add these corners** → **Check boundary** (SQL Server measures ≈ 100 ha) → **Save as new boundary version**.

**4.3 Ownership evidence document** — pm, tab **Documents**

| Field | Required | Rule | Enter |
|---|---|---|---|
| Category | Yes | farm document categories | Land record |
| Title | Yes | free text | `7/12 extract Survey 45/2` |
| Choose file | Yes | PDF/PNG/JPG/WebP | any PDF |

Button **Upload**.

**4.4 Ownership** — pm, tab **Ownership** (editable only while the farm is Draft)

| Field | Required | Rule | Enter |
|---|---|---|---|
| Owner type | Yes | Farmer · Individual · Organization · Government · Community | Farmer |
| Owner name | Only if not Farmer | 2–200 | (hidden) |
| Farmer's relationship | Yes | Owner · Co-owner · Tenant · Lessee · Sharecropper · Custodian · Other | Owner |
| Share % | No | > 0 and ≤ 100 | `100` |
| Title / survey reference | No | max 120 | `Survey 45/2` |
| Valid from | No | date | `01/01/2020` |
| Evidence document | No | land record / title / lease / other from the Documents tab; newest is pre-selected | `7/12 extract Survey 45/2` |

Button **Record ownership** → one record, **Unverified**, "Evidence: 7/12 extract Survey 45/2".

**4.5 Review**

| # | Role | Action | Expected |
|---|---|---|---|
| 4.5a | pm | Header **Submit for review** (reason) | **Submitted** (overlap check runs) |
| 4.5b 🔎 | pm | Look for **Verify farm** | Not available to the submitter |
| 4.5c | gis | Tab **Ownership** → **Verify** → reason `Land record checked` | Ownership **Verified** |
| 4.5d | gis | Header **Start GIS review** (reason) | **GIS review** |
| 4.5e | gis | Tab **Overlaps** → **Clear** anything listed (only if corners collide) | No open overlaps |
| 4.5f | gis | Header **Verify farm** (reason) | **Verified** |

---

## Stage 5 — Project and eligibility
**Roles: pm builds the project; gis accepts the boundary; qa verifies rights and approves eligibility.**

**5.1 Create project** — pm, **Projects → New project**

| Field | Required | Rule | Enter |
|---|---|---|---|
| Organization | Yes | Project developer / Field partner / Farmer group where you manage projects | varsapradaya_developer |
| Project name | Yes | 2–200 | `Nashik tillage pilot` (+ tester no. if several testers) |
| Project type | Yes | Agricultural land management · Agroforestry · Rice cultivation · Grassland management · Other | Agricultural land management |
| Country (ISO code) | Yes | 2 letters | `IN` |
| Region | No | max 200 | `Nashik` |
| Planned start date | Strongly advised | must be ≥ methodology Effective from | `06/01/2026` |
| Description | No | max 4000 | empty |

Button **Create project** → `PRJ-2026-…`, **Draft**; pm is on the **Team** tab as Project Manager. Then header **Start data collection** (reason).

**5.2 Add farm** — pm, tab **Farms** → "Add a verified farm"

| Field | Required | Rule | Enter |
|---|---|---|---|
| Farm | Yes | verified farm of an **active** farmer, same organization | North block |
| Participation from | Yes | date | `06/01/2026` |
| Participation to | No | ≥ from | empty |
| Rights holder | Yes | Farmer · Landowner · Organization · Farmer group · Other | Farmer |
| Agreement / evidence reference | Yes | max 200 | `Carbon rights clause of AGR-2026-…` |
| Share % | No | > 0 and ≤ 100, total per farm ≤ 100 | `100` |
| I acknowledge these conflicts + Why the farm can still join | Only if conflicts are shown | both needed | (not shown for a new farm) |

Button **Add farm** → farm listed with a Rights chip.

**5.3 Standard & activity** — pm, tab **Standard & activity**: Standard `Gold Standard for the Global Goals` → **Select**; Activity
`Agriculture - soil organic carbon` → **Select**. Both show "(current)".

**5.4 Crediting & baseline** — pm, tab **Crediting & baseline**

| Form | Field | Required | Rule | Enter |
|---|---|---|---|---|
| Crediting period | Start | Yes | date | `06/01/2026` |
| | End | Yes | after start; no overlap with another proposed period | `05/31/2036` |
| | Notes | No | max 2000 | empty |
| Baseline | From | Yes | date | `06/01/2021` |
| | To | Yes | ≥ From | `05/31/2026` |
| | Baseline practices | No | max 4000 | `Conventional tillage, residue burning` |
| | Data sources | No | max 2000 | `Farmer interview` |

Buttons **Record period** and **Record baseline**.

**5.5 Eligibility**

| # | Role | Screen | Action | Expected |
|---|---|---|---|---|
| 5.5a | pm | Header | **Submit for eligibility review** (reason). Needs: farm, verified farm + active farmer, carbon rights, valid boundary, standard, activity, crediting period, baseline, a PM on the team | **Eligibility review** |
| 5.5b | gis | Tab **Boundary** | **Accept boundary** (reason) — do it after the last farm change | Review: Accepted |
| 5.5c | qa | Tab **Carbon rights** | **Verify** → reason `Agreement checked` | Verified |
| 5.5d 🔎 | pm | Header | Look for **Approve eligibility** | Not shown to the submitter |
| 5.5e | qa | Header | **Approve eligibility** (reason) | **Standard selected** |
| 5.5f | pm | Header | **Confirm activity** (reason) | **Activity selected** |

---

## Stage 6 — Lock the methodology
**Roles: ms1 recommends; pm confirms.** Screen: project → tab **Methodology**.

| # | Role | Field / action | Enter | Expected |
|---|---|---|---|---|
| 6.1 | ms1 | Declared facts (Fact key + Value, optional) → **Evaluate candidates** | leave empty | Candidate **GS402 1.0** (your label): **Applicable**, A1 ✔ A2 ✔; status **Methodology review** |
| 6.2 | ms1 | Expand the candidate → **Recommend** (reason = notes, 3–1000) | `Applicable; module GS402-IT-A3` | "Recommended by" ms1's name |
| 6.3 🔎 | ms1 | Try **Confirm & lock** | — | Not allowed |
| 6.4 | pm | Expand → **Confirm & lock** (reason) | `Confirmed` | Lock card with the version; status **Methodology confirmed**; **MRV workspace** button |

Do not click **Unlock**. Do not re-evaluate after 6.2 (`EVALUATION_OUTDATED`).

---

## Stage 7 — MRV plan, monitoring period, stratum
**Roles: mrv plans; qa approves the plan; gis creates the stratum; sup approves it.** Screen: **MRV** → choose the project in the selector at the top.

**7.1 MRV plan** — mrv, tab **MRV plans** → **Create MRV plan**

| Field | Required | Rule | Enter |
|---|---|---|---|
| Monitoring frequency | Yes to submit | free text, max 200 | `Annual` |
| Quantification approach | No | leave **empty** (a different value from the methodology's is refused) | empty |
| Monitoring start / end | Yes to submit | end after start | `06/01/2026` / `05/31/2036` |
| Required evidence | Advised | max 2000 | `Factor sources (IPCC tables)` |
| Notes | No | max 2000 | empty |
| Project measurements | No | the methodology's `GS_…` measurements are copied in automatically | add none |

Button **Create plan (draft)** → plan page lists the `GS_…` measurements → **Submit for approval** (reason) → **Submitted**.

| # | Role | Action | Expected |
|---|---|---|---|
| 7.2 🔎 | mrv | Look for **Approve** | Not shown to the submitter |
| 7.3 | qa | Open the plan → **Approve** (reason; the dialog notes CONFIGURATION_REQUIRED gaps — expected outside production) | **Approved**; project **MRV planned** |

**7.4 Monitoring period** — mrv, tab **Monitoring periods**

| Field | Required | Rule | Enter |
|---|---|---|---|
| Name | Yes | 2–200 | `Period 1` |
| Purpose | Yes | Monitoring · Baseline · Verification · Other | Monitoring |
| Start / End | Yes | end after start; inside the plan window | `06/01/2026` / `05/31/2027` |

Button **Create period**; then on its row **Mark planned** → **Start period** → **Open data collection** (reason each) → period **Data
collection**, project **Monitoring**.

**7.5 Stratum** — gis, tab **Stratification** → New, keep **Project stratum**

| Field | Required | Rule | Enter |
|---|---|---|---|
| Code | Yes | `[A-Z][A-Z0-9_.-]`, unique | `S1` |
| Name | Yes | 2–200 | `Tillage plots` |
| Farms | Yes | active project farms with a boundary, not already in a stratum | North block |
| Characteristic + Value | No | Soil type, Crop, Land use, …; click **+** to add each | Soil type = `Black soil` → **+** |

Button **Create stratum** → S1 **Draft**, area ≈ 100 ha.

| # | Role | Action | Expected |
|---|---|---|---|
| 7.6 🔎 | gis | Look for **Approve** on S1 | Not available to the creator |
| 7.7 | sup | **Approve** on S1 (reason) | S1 **Approved** |

No sampling design or points are needed for Approach 3.

---

## Stage 8 — Factor data and the MRV dataset
**Roles: mrv records and submits; qa reviews and approves.**

**8.1 Factor values** — mrv, tab **Monitoring data**. One record per row.

| Field | Rule | Enter for every row |
|---|---|---|
| Measurement | the plan's measurements | see table |
| Stratum | appears for per-stratum measurements | `S1 · Tillage plots` |
| Value | number for measurements with a unit | see table |
| Observed on | inside the period, not in the future | `10/05/2026` (or today) |
| Phase | Monitoring · Project · Baseline | Project |
| Source | Field observation · Farmer claim · Document · Instrument · Other | Document |

Button **Record value** after each row.

| Measurement | Unit | Required | Value |
|---|---|---|---|
| GS_SOC_REF | t C/ha | Yes | `47` |
| GS_F_LU | factor | Yes | `0.83` |
| GS_F_MG_BL | factor | Yes | `1.00` |
| GS_F_I_BL | factor | Yes | `0.92` |
| GS_F_MG_PR | factor | Yes | `1.10` |
| GS_F_I_PR | factor | Yes | `1.11` |
| GS_T_BL | yr | Yes | `20` |
| GS_T_PR | yr | Yes | `1` |
| GS_U_SOC_REF | % | No — keeps the uncertainty deduction at 0 | `2` |
| GS_U_F_LU | % | No | `2` |
| GS_U_F_MG_BL | % | No | `1` |
| GS_U_F_I_BL | % | No | `1` |
| GS_U_F_MG_PR | % | No | `1` |
| GS_U_F_I_PR | % | No | `1` |

**8.2 Paris alignment** — mrv, same tab, project level (no stratum or farm box): Measurement **GS_PAA** · Value `YES` · same date,
phase, source. Without it every 2026 credit is blocked (`PAA_BLOCKED_SHARE` = 1).

Record each measurement **once**; fix a typo with **Correct** on its row (a second record blocks the run with `DUPLICATE_INPUT`).
Leave fertiliser, diesel, gasoline, electricity and yield empty. If you enter diesel you must also enter project-level `GS_FEF_DIESEL`
(e.g. `0.00268`).

**8.3 Dataset**

| # | Role | Screen / action | Expected |
|---|---|---|---|
| 8.3a | mrv | Tab **Datasets & QA** → Monitoring period `Period 1` → **Create dataset version** → **Open / QA** → **Submit for QA** (reason) | **Submitted**, frozen snapshot with SHA-256 |
| 8.3b 🔎 | mrv | Look for **Record QA result** | Not available to the submitter |
| 8.3c | qa | **Start QA review** | All checks PASS or WARN, no FAIL |
| 8.3d | qa | QA result `PASS` → **Record QA result** (reason) → **Approve dataset** (reason) | Dataset and period **Approved** |

After 8.3a never press **Open data collection** on that period again. To correct data, create a new dataset version.

---

## Stage 9 — Calculation and calculation QA
**Roles: analyst runs; qa reviews and approves.** Screen: **Calculations** → Project `Nashik tillage pilot` · Monitoring period `Period 1`.

| # | Role | Action | Expected |
|---|---|---|---|
| 9.1 | analyst | Read the readiness panel | No red blocker; only "NOT_PRODUCTION_READY: non-production use only" |
| 9.2 | analyst | **New calculation run** (no fields) → click the run code | Run page **Draft** |
| 9.3 | analyst | **Check readiness & freeze inputs** | **Inputs frozen**; Inputs tab lists the factors, GS_PAA and the S1 area |
| 9.4 | analyst | **Execute** | **Calculated**; Results tab filled |
| 9.5 | analyst | **Submit for QA** | Submitted for QA |
| 9.6 🔎 | analyst | Look for **Approve** | Not available to the run's creator |
| 9.7 | qa | Tab **QA** → **Start calculation QA** → Result `PASS` · Notes (3+) `Inputs and outputs checked` → **Record QA** | QA PASS |
| 9.8 | qa | Header **Approve** (reason) | Run **Approved**; project **Calculated** |

Expected outputs (approximate, they scale with the measured area):

| Output | Meaning | Approx. |
|---|---|---|
| SOC_0_… / SOC_T_… | SOC stock at start / end of the period | t C/ha |
| DSOC_C | SOC stock change | ≈ 59 t C |
| UNC / UD | uncertainty / deduction above 20 % | ≈ 0.15 / 0 |
| BUFFER | 20 % Gold Standard buffer | ≈ 43 t CO2e |
| GS_VER_TOTAL | net reductions, whole tonnes rounded down | **≈ 170** — note the exact number for Stages 10–11 |

---

## Stage 10 — Internal readiness and VVB verification
**Roles: qa raises and resolves findings; analyst responds, generates the report and prepares readiness; qa approves readiness;
pm proposes the VVB and submits the package; vvb accepts and decides.**

Settle internal findings **before** generating the report — any later finding change makes it stale (`REPORT_STALE`). The pm cannot do
10.1–10.8 (only the analyst holds `calculation.manage`).

**10.1 Internal finding** — qa, run page → tab **Findings**

| Field | Required | Rule | Enter |
|---|---|---|---|
| Category | Yes | Observation · Non-conformity · Clarification · Missing evidence · Calculation issue · Methodology issue | Clarification |
| Blocking (gates internal readiness) | — | ticked by default | ticked |
| Title | Yes | 3–200 | `Source of factors` |
| Description | Yes | 3–4000 | `Cite the IPCC table used for F_MG and F_I` |
| Input # / Output # | No | must exist in this run | empty |

Button **Raise finding** → **Open**.

| # | Role | Field / action | Enter | Expected |
|---|---|---|---|---|
| 10.2 | analyst | Response (3+) → **Respond** | `IPCC 2019 Vol. 4 Ch. 5 Table 5.5 (test values)` | **Responded** |
| 10.3 🔎 | analyst | Look for **Resolve** | — | Not shown to the responder |
| 10.4 | qa | **Resolve** (reason) | `Source accepted` | **Resolved** |
| 10.5 | analyst | Run page → Calculation report → **Generate report** → **Verify** | — | Report v1 CURRENT, "Hashes verify" |
| 10.6 | analyst | Calculations → project + Period 1 → **Verification readiness** → **Prepare readiness** → **Submit** | — | Readiness **Submitted** |
| 10.7 🔎 | analyst | Look for **Approve (READY)** | — | Hidden: submitter and run creator cannot approve |
| 10.8 | qa | **Approve (READY)** (reason) | `Internal checks complete` | **READY**; **Package manifest** button |

**10.9 Propose the VVB** — pm, **MRV → project → tab Verification** → "Propose a VVB assignment"

| Field | Required | Rule | Enter |
|---|---|---|---|
| VVB / ACVA organization | Yes | active VVB organizations | verify_co |
| Notes | No | max 2000 | `Verification of Period 1` |

Button **Propose** → assignment **Proposed**.

**10.10 Accept** — vvb, **VVB workspace** → the assignment

| Field | Required | Rule | Enter |
|---|---|---|---|
| Conflict-of-interest declaration | Yes | 10–4000 characters | `No financial or personal interest in the project or its developer` |

Button **Accept** → **Accepted**; project **Verification**.

**10.11 Submit package** — pm, Verification tab → assignment card → **Submit READY package** → submission `SUB-…` **Submitted**.

**10.12 Review** — vvb, assignment tabs **Package** and **Documents**: farms, factors, outputs and the calculation report are listed.

**10.13 Decision** — vvb, assignment tab **Decision**

| Field | Required | Rule | Enter |
|---|---|---|---|
| Outcome | Yes | Verified · Not verified | Verified |
| VVB-stated verified quantity | Needed for issuance | decimal ≥ 0; must be ≥ 1 to issue anything | the `GS_VER_TOTAL` from 9 (e.g. `170`) |
| Unit | Yes when a quantity is entered | text; must match the registry account in 11.1 exactly | `tCO2e` |
| Rationale | Yes | 3–4000 | `Factors and calculation checked against the package` |
| Verification report | Yes | PDF only | any PDF |

Button **Record decision** → decision CURRENT; assignment **Completed**; project **Verified**.

*Optional — VVB findings* (needs `vvb2`; the VVB user who raises a finding on a submission cannot decide it). Between 10.12 and 10.13:
vvb2 → tab **Findings**: Category Missing evidence · Blocking ticked · Title `Factor source document` · Description `Attach the factor table` ·
Target SUBMISSION · Target reference empty → **Raise finding**. pm → Verification tab → Response `Table attached` + optional PDF →
**Respond**. vvb2 → **Close** (reason). Every finding must be Closed before the Decision form appears.

---

## Stage 11 — Registry submission and issuance
**Roles: pm (or a Registry Manager) records everything the registry states; qa confirms the issuance.** Screen: **Registry** → Project +
Period 1 (or MRV workspace → tab **Registry**). The registry is an outside party with no users.

> Units are compared as exact, case-sensitive text: the account's **= 1 verified unit** must equal the VVB unit (`tCO2e`), and the
> issuance **Unit** must equal the account's **Registry credit unit** (`VER`). An account's units cannot be changed in the UI afterwards.

**11.1 Registry account** — pm, "Record a registry account / registration"

| Field | Required | Rule | Enter |
|---|---|---|---|
| Registry | Yes | active Registry organizations | Test Registry |
| Registry account ID | Yes | 1–120; unique per registry | `ACC-` + tester no. (e.g. `ACC-01`) |
| Label | Yes | 2+ | `Main GS account` |
| Registry credit unit | For issuance | max 40 | `VER` |
| = 1 verified unit (explicit) | For issuance | max 40; fill both units or neither | `tCO2e` |
| Document checklist (JSON) | No (warning only outside production) | JSON array of `{code,title,source}` | empty |

Button **Record account** → **Active**, "1 VER = 1 tCO2e".

**11.2 Registration** — pm

| Step | Field | Required | Enter |
|---|---|---|---|
| Start | Account for registration | Yes | Main GS account → **Start registration record** → **Pending** |
| Record | Registry project ID | Yes, 1–120, unique per registry | `GS-PRJ-` + tester no. |
| | Registered on | No | `10/05/2026` |
| | Registry evidence (PDF) | Yes | any PDF → **Record registered** → **Registered** |

**11.3 Submission** — pm, "Registry submissions"

| Step | Field | Required | Enter | Expected |
|---|---|---|---|---|
| Prepare | Registry account | Yes | Main GS account → **Prepare registry submission** | `RSUB-…` **Draft** (warning CHECKLIST_NOT_CONFIGURED only) |
| Freeze | — | — | **Freeze snapshot** | **Frozen** |
| Submitted | Registry submission reference | Yes, 1–120 | `GS-SUB-` + tester no. | |
| | Registry receipt (PDF) | Yes | any PDF → **Record submitted** | **Submitted** ("Send via registry API" fails with MANUAL_ACTION_REQUIRED — expected) |
| Response | Outcome | Yes | Accepted | |
| | Registry reason / note | Only for Rejected | empty | |
| | Registry response (PDF) | Yes | any PDF → **Record response** | **Accepted** |

**11.4 Issuance** — pm, "Record issuance" (shown when Accepted)

| Field | Required | Rule | Enter |
|---|---|---|---|
| Registry issuance ID | Yes | 1–120, unique per registry | `GS-ISS-` + tester no. |
| Issuance date (registry) | Yes | date | `10/05/2026` |
| Unit (registry) | Yes | exactly the account credit unit | `VER` |
| Issuance statement (PDF) | Yes | PDF | any PDF |
| Batch → Vintage (registry) | Yes | 1–60, as the registry states | `2026` |
| Batch → Whole credits | Yes | integer ≥ 1; total ≤ VVB quantity | the VVB quantity (e.g. `170`) |
| Batch → Serial start / end | Both or neither; unique per registry | as supplied | `GS-T01-2026-000001` / `GS-T01-2026-000170` (your tester no.) |

Button **Record issuance** → issuance **Recorded**, "Total 170".

| # | Role | Action | Expected |
|---|---|---|---|
| 11.5 🔎 | pm | Look for **Confirm** | Not shown to the recorder |
| 11.6 | qa | **Confirm (second person)** → note `Matches registry statement` | Issuance **Confirmed**, batch **Issued**; project **Issued**; batch listed under **Issued credits** |

---

## Stage 12 — Credit ledger
**Roles: credits requests every movement; qa confirms it; buyer retires its own credits.** Screen: **Credit ledger** → the batch → **Details**.
Of 170 credits: 10 retired by the developer, 10 moved to the buyer (who retires 5), 150 kept for the marketplace.

| # | Role | Form / field | Enter | Expected |
|---|---|---|---|---|
| 12.1 | credits | **Open in ledger** → reason → **Request opening** | `Open issued batch` | Opening **Requested** |
| 12.2 🔎 | credits | Look for **Confirm opening** | — | Not available to the requester |
| 12.3 | qa | **Confirm opening** | — | **Confirmed**; Available 170 owned by varsapradaya_developer |

**12.4 Request retirement** — credits, Details → action forms

| Field | Required | Rule | Enter |
|---|---|---|---|
| Owner | Yes | an owner in the balances table — only the developer (the buyer is refused) | varsapradaya_developer |
| From reservation | No | — | empty |
| Quantity | Yes | whole credits ≤ available | `10` |
| Beneficiary | Yes | 2–300 | `Varsapradaya Developer` |
| Retirement reason | Yes | 3–2000 | `Test retirement by the developer` |

Button **Request retirement** → 10 **Retirement pending**.

**12.5 Record retirement** — qa, Details → Retirements row

| Field | Required | Rule | Enter |
|---|---|---|---|
| Registry retirement reference | Yes | 1–120, unique | `GS-RET-` + tester no. + `-A` |
| Date | Yes | date | `10/05/2026` |
| Serial start / end (as stated) | No, both or neither | as stated | empty |
| Certificate | Yes | PDF | any PDF |

Button **Record retirement** → 10 **Retired** (final).

**12.6 Request transfer** — credits

| Field | Required | Rule | Enter |
|---|---|---|---|
| Kind | Yes | Internal (platform ownership) · Registry | Internal |
| Sender | Yes | an owner | varsapradaya_developer |
| Recipient | Yes | active Buyer or Project developer organization, not the sender | Test Buyer |
| From reservation | No | — | empty |
| Quantity | Yes (without reservation) | ≤ available | `10` |
| Registry range | No | — | empty |
| Purpose | No | — | `Test transfer` |

Button **Request transfer** → 10 **Transfer pending**.

| # | Role | Field / action | Enter | Expected |
|---|---|---|---|---|
| 12.7 | qa | Transfers table → **Complete** (no evidence for Internal) | — | **Completed**; Test Buyer owns 10 |
| 12.8 | buyer | **My credits** → AVAILABLE row → **Request retirement**: Quantity ≤ own available · Beneficiary 2+ · Retirement reason 3+ | `5` · `Test Buyer Ltd` · `Offsetting 2026 travel` | Request listed |
| 12.9 | qa | Credit ledger → batch → Details → Retirements → as 12.5 with reference `GS-RET-` + tester no. + `-B` | — | 5 **Retired**; buyer sees 5 left |

*Optional:* **Reserve** (Owner developer · Quantity `5` · Purpose `Hold for client` · Expires at a future date) → **Release** (reason).

---

## Stage 13 — Marketplace
**Roles: buyer builds its profile and buys; compliance verifies KYC; credits lists; fin1 approves the listing and confirms payment;
qa completes delivery on the Credit ledger (the QA officer has no access to Orders).** Order: 20 credits × ₹500 = ₹10,000.

**13.1 Buyer profile** — buyer, **Buyer profile**

| Field | Required | Rule | Enter |
|---|---|---|---|
| Legal name | Yes | 2–300 | `Test Buyer Ltd` |
| Registration number | No | max 100 | `U12345MH2026PTC0000` + tester no. |
| Country (ISO code) | No | 2 letters | `IN` |
| Contact name | No | — | `Asha Rao` |
| Contact email | No | valid email | `buyer@yopmail.com` |
| KYC documents (PDF) | At least one to submit | PDF | any PDF → **Upload** |

Buttons **Save** (→ Draft), then **Submit for KYC review** → **KYC submitted**.

**13.2 KYC** — compliance, **KYC review** → row Test Buyer Ltd → **Verify** → reason `Registration documents checked` → **KYC verified**.
(Return → buyer edits and resubmits; Suspend / Reinstate exist for verified buyers.)

**13.3 Listing** — credits, **Listings → New listing**

| Field | Required | Rule | Enter |
|---|---|---|---|
| Credits (batch · owner · available) | Yes | batches with a confirmed opening and available > 0 | your batch |
| Registry range | No | — | Any range of the batch |
| Title | Yes | max 200 | `GS402 Nashik tillage 2026` |
| Listed quantity (credits) | Yes | whole number ≤ seller's available | `100` |
| Price per credit | Yes | decimal, currency's decimals | `500.00` |
| Currency (ISO 4217) | Yes | INR, USD, EUR, … | `INR` |
| Min order / Max order | No | max ≥ min; min ≤ quantity | `1` / `50` |
| Payment window (hours) | Yes | 1–720 | `48` |
| Valid until | No | future date-time | empty |
| Co-benefits | No | max 2000 | `Soil health, farmer income` |

Buttons **Create draft** → row **Submit** → **Pending approval**.

| # | Role | Field / action | Enter | Expected |
|---|---|---|---|---|
| 13.4 🔎 | credits | Look for **Approve** | — | Hidden for the creator |
| 13.5 | fin1 | **Listings** → **Approve** (reason) | `Price approved` | **Active** (price frozen) |
| 13.6 | buyer | **Marketplace** → listing **Details** → Quantity (whole credits) → **Add to order** · Delivery: Ledger transfer (default) → **Place order** | `20` | Order `ORD-…` **Placed**, total INR 10,000.00 |
| 13.7 | buyer | **Orders** → Open → Payment reference (optional, max 120) + PDF evidence (required) → **Record payment** | `UTR-` + tester no. + `-0001` | Payment **Pending confirmation** |
| 13.8 🔎 | buyer | Look for **Confirm receipt** | — | Not available to the payer |
| 13.9 | fin1 | **Payments** → **Confirm receipt** (reason) | `Funds received` | Payment **Confirmed**; order **Transfer pending** |
| 13.10 | qa | **Credit ledger** → batch → Details → Transfers row "marketplace order ORD-…" → **Complete** | — | Order **Completed**; buyer's **My credits** +20; revenue INR 10,000 recognized |

---

## Stage 14 — Revenue sharing, settlement and farmer payout
**Roles: pm authors the sharing and adds the bank account; fin1 approves configuration, verifies the bank and calculates; fin2 approves
and reconciles; fin3 pays.** Every Finance page has a **Project** picker — choose `Nashik tillage pilot`. Farmer share 60 % of ₹10,000 = **₹6,000**.

**14.1 Revenue** — pm, **Revenue & costs** → Revenue records: one RECOGNITION of INR 10,000 for Period 1 (automatic, nothing to enter).

**14.2 Revenue-share version** — pm, **Revenue sharing**

| Field | Required | Rule | Enter |
|---|---|---|---|
| Farmer share % (0–100] | Yes | > 0 and ≤ 100, up to 6 decimals | `60` |
| Rounding mode | Yes | HALF_UP · HALF_EVEN · DOWN | HALF_UP |
| Deduct approved project costs | — | checkbox | unticked |
| Effective from | Yes | must cover the whole period | `06/01/2026` |
| Effective to | No | ≥ from | empty |
| Source (agreement / clause) | Yes | 3–500 | `Farmer agreement AGR-2026-… clause 7` |

Buttons **Create draft version** → **Submit** → **In review**. Then **fin1 → Approve** (reason) → **Approved** (🔎 pm cannot approve it).

**14.3 Farm allocation** — pm, same page

| Field | Required | Rule | Enter |
|---|---|---|---|
| Monitoring period | Yes | — | Period 1 |
| Basis (document / decision) | Yes | 3+ | `Single participating farm` |
| Share % per farm | Total must be exactly 100 | empty = excluded | North block `100` (Total: 100 %) |

Buttons **Create draft allocation** → **Submit**. Then **fin1 → Approve** (reason).

**14.4 Bank account** — pm, **Farmers** → Ramesh Patil → tab **Bank**

| Field | Required | Rule | Enter |
|---|---|---|---|
| Account holder | Yes | 2+ | `Ramesh Patil` |
| Bank | Yes | 2+ | `State Bank of India` |
| Branch | No | — | `Nashik Main` |
| Routing code (IFSC / SWIFT) | Yes | 4–30 letters/digits | `SBIN0001234` |
| Account number | Yes | 6–40 letters/digits/space/hyphen; stored encrypted | `1234567890` + tester no. |

Button **Add bank account** → **Pending verification**. Then **fin1 → Verify** (reason `Cancelled cheque checked`) → **Verified**
(🔎 the person who added it cannot verify).

**14.5 Settlement** — Settlements page

| # | Role | Field / action | Enter | Expected |
|---|---|---|---|---|
| 14.5a | fin1 | Monitoring period · Currency · Approved revenue-share version · Approved farm allocation → **Create run** → **Calculate** → **Verify (recompute from snapshot)** → **Submit** | Period 1 · `INR` · the approved version · the approved allocation | Entitlement INR 6,000.00 for Ramesh Patil; "Reproducible"; **Pending approval** |
| 14.5b 🔎 | fin1 | Look for **Approve** | — | Hidden for the calculator |
| 14.5c | fin2 | **Approve** (reason) | `Entitlements checked` | Run **Approved** |

**14.6 Payout** — Payouts page

| # | Role | Field / action | Enter | Expected |
|---|---|---|---|---|
| 14.6a | fin1 | Settlements → run → **Create payouts**; Payouts → **Submit** | — | Payout **Pending approval** |
| 14.6b | fin2 | **Approve** (reason) | `Approved for payment` | **Approved**; bank ••••last 4 captured |
| 14.6c 🔎 | fin2 | Look for **Execute** | — | Not available to the approver |
| 14.6d | fin3 | **Execute** | — | **Payment pending** |
| 14.6e | fin3 | **Record paid** → Bank / remittance reference (required) + PDF → **Upload evidence and record PAID** | `NEFT-` + tester no. + `-0001` | **Paid** |
| 14.6f | fin2 | **Reconcile** → Statement reference · Statement amount (≥ 0) · Currency · Statement date · PDF → **Upload statement and reconcile** | the same `NEFT-…` · `6000.00` · `INR` · `10/05/2026` | **Reconciled**; settlement run **Completed** |

*Optional — farmer view.* `farmer@yopmail.com` (Farmer role in varsapradaya_developer). There is no UI to link a login to a farmer: pm
calls `POST /api/v1/farmers/{farmer_id}/link-user` with body `{"user_id": "<farmer user id>"}` in Swagger (http://localhost:8000/docs,
**Authorize** as pm). The farmer then opens **My payouts**: INR 6,000.00, Reconciled, bank ••••last 4.

---

## Appendix A — Field sampling and laboratory (separate project)
The main flow never touches field work or the laboratory. Test them on a second project locked to a lab-only methodology. Its calculation
ends at `NO_CALCULATION_MODULE` — the expected end.

**A.1 Methodology** — ms1 → ms2 (as Stage 2, without a module)

| Item | Enter |
|---|---|
| Methodology | Code `TESTLAB` · Name `Lab test methodology` · Standard Gold Standard · Activity AGR-SOC |
| Version | label `1.0` · Effective from `01/01/2020` · Source `Internal lab test` · Calculation tab: **None** |
| Applicability | `A1` as in 2.5 |
| Monitoring rule (the only one) | Code `SOC1` · Title `Soil organic carbon` · Parameter `soil_organic_carbon` · Unit `g/kg` · Frequency `Per period` · Measurement source **Laboratory** |

ms1 submits, ms2 approves.

**A.2 Project** — Stages 5–6 again with name `Nashik lab test`; add North block with **I acknowledge these conflicts** + `Separate lab test project`.
At 6.1 two candidates appear: ms1 recommends **TESTLAB 1.0**.

**A.3 MRV** — mrv: plan and Period 1 as 7.1–7.4 (qa approves the plan). gis: stratum `S1` as 7.5; sup approves.

**A.4 Lab engagement** — mrv, tab **Samples & laboratory**: Laboratory `soiltestlab` · LABORATORY rules in scope `SOC1` → **Propose
engagement**. labmgr → **Laboratory → Engagements** → **Accept**.

**A.5 Sampling design** — gis, tab **Sampling design**

| Field | Required | Rule | Enter |
|---|---|---|---|
| Code | Yes | code format, unique per period | `SOIL-1` |
| Name | Yes | 2–200 | `Soil sampling` |
| Sample count for S1 | Yes | 1–10000 | `2` |
| Statistical design | Yes | Stratified random · Simple random · Systematic grid · Other | Stratified random |
| Sampling method | No | max 1000 | `Soil auger` |
| Depth top / bottom (cm) | Yes | 0–1000, bottom > top | `0` / `30` |
| Target precision / Confidence level (%) | No | (0,100] / (0,100) | empty |
| Min. distance between points (m) | No | 0–10000 | `10` |
| Random seed | No | integer | empty |

Button **Create design (2 samples)**; sup → **Approve design**; gis → **Generate sampling points** (2 points).

**A.6 Assign** — sup, tab **Points & assignments** → **Select unassigned** → Field collector `colfield_test` · Planned date today →
**Assign 2 point(s)**.

**A.7 Field collection** — col, **Field work** (phone-size window) → **Start collection**, each point

| Field | Required | Rule | Enter |
|---|---|---|---|
| Latitude / Longitude | Yes | within 30 m of the point and inside the farm, else a deviation note | the point's own coordinates |
| GPS accuracy (m) | No | 0–10000, 1 decimal | empty |
| Collected at | Yes | inside the period, not in the future | now |
| Depth top / bottom (cm) | Yes | pre-filled | `0` / `30` |
| Sample quantity / Unit | No | ≥ 0 | `0.5` / `kg` |
| Field observations | No | max 2000 | empty |
| Deviation note | Only if GPS is off | max 1000 | empty |
| Field checklist | All 4 required | location, depth, container labelled, photo | tick all |
| Take / add photo | At least 1 | JPG/PNG/WebP | one photo |

Button **Save & submit**. sup → Points & assignments → Submitted field records → **Accept** each (🔎 col cannot accept own records).

**A.8 Sample** — col, on the accepted field record → **Register & seal sample**

| Field | Required | Enter (point 1 / point 2) |
|---|---|---|
| Description | Yes, 2–500 | `Topsoil core 0–30 cm` |
| Quantity / Unit | No | `500` / `g` |
| Container label | No | `BAG-01` / `BAG-02` |
| Seal number (after **Register sample**) | Yes, 1–100 | `SEAL-0001` / `SEAL-0002` → **Seal sample** |

**A.9 Shipment** — sup, tab **Samples & laboratory** → Shipments: Ship to laboratory `soiltestlab` · Carrier `Courier` → **Create shipment** →
Add sealed samples (both) → **Add** → **Dispatch**.

**A.10 Laboratory** — labtec, **Laboratory**

| Tab | Field | Rule | Enter |
|---|---|---|---|
| Incoming | Accept | ticked | ticked |
| | Seal observed | must equal the field seal | `SEAL-0001` / `SEAL-0002` |
| | Condition | max 500 | `Good` → **Record receipt** |
| Samples | Accession no. | 1–100 | `LAB-0001` / `LAB-0002` → **Register** |
| Worklist → test | Method used | max 500 | `Walkley-Black` → **Start test** |
| | Result type | Numeric · Text as reported | Numeric |
| | Value | number | `12.5` / `13.1` |
| | Unit | must equal the rule unit exactly | `g/kg` |
| | Analysed at | after receipt, not in the future | now → **Save result** |
| | PDF report | PDF | any PDF → **Submit for QA** |

🔎 labtec cannot approve own result. labmgr → **Laboratory → QA** → **Review** → **Start QA review** → Decision `APPROVED` · Notes (3+)
`Checked` → **Record decision** → result **Approved**, sample **Analysed**.

**A.11 Dataset and calculation** — mrv/qa: dataset as 8.3 → **Approved**. analyst: **Calculations** → this project → **New calculation
run** → **Check readiness & freeze inputs** → **Blocked — NO_CALCULATION_MODULE** (expected). As labtec, `/mrv` shows "You don't
have access to this page".

---

## Troubleshooting

| Code / symptom | Stage | Fix |
|---|---|---|
| A button is missing | any | Wrong login for the step, or it is your own submission |
| `SEPARATION_OF_DUTIES` | any | Use the second login named in the step |
| `REQUIREMENTS_NOT_MET` | 3–5 | Read the "still needed" checklist on the page |
| "The farmer is KYC_VERIFIED, not ACTIVE" | 5.2 | Record the consent and **Activate** (3.5) |
| `DUPLICATE_REVIEW_REQUIRED` | 3.4 | Same ID number as another tester: tick the "different person" box or use your own number |
| Open overlap blocks **Verify farm** | 4.5f | Clear it on **Overlaps**; shift the corners by your tester offset |
| Version label already exists | 2.2 | Use `1.0-IT-A3-` + tester no. |
| Module options greyed out | 2.4 | Methodology code is not `GS402` or the label does not start with `1.0` |
| No methodology candidate | 6.1 | Version not Approved, Effective from after the project start, or activity is not AGR-SOC |
| `EVALUATION_OUTDATED` | 6.4 | Someone re-evaluated after the recommendation; ms1 recommends again |
| `METHODOLOGY_REQUIREMENT` | 7.1 | Leave Quantification approach empty |
| `OUTSIDE_PLAN_WINDOW` / `OUTSIDE_PERIOD` | 7.4 / 8.1 | Date outside the window or period — check month/day order |
| No Stratum box on Monitoring data | 8.1 | Stratum not approved (7.7) |
| QA FAIL "Required measurements are recorded" | 8.3c | A required measurement has no value: reject, create a new dataset version, record it |
| `MODULE_NOT_SELECTED` / `RULE_MODULE_MISMATCH` | 9 | Version approved without the module (2.4) — set up a new version and a new project |
| `PREVIOUS_PERIOD_REQUIRED`, missing `OC_T` / `MASS_T` | 9 | An `-A1` module was chosen instead of `-A3` |
| `MISSING_REQUIRED_INPUT` (a factor) | 9 | Factor missing or recorded without the stratum |
| `DUPLICATE_INPUT` | 9 | A factor recorded twice — use **Correct** |
| `REPORT_STALE` | 10 | A finding changed after the report: regenerate (10.5) and prepare readiness again |
| Decision form hidden | 10.13 | A finding is not Closed, or this VVB user raised findings on the submission |
| `UNIT_EQUIVALENCE_NOT_CONFIGURED` | 11.4 | Account units missing, or the issuance unit is not exactly `VER` |
| `QUANTITY_EXCEEDS_VERIFIED` | 11.4 | More credits than the VVB quantity |
| `DUPLICATE_SERIAL` / `DUPLICATE_EXTERNAL_…` | 11 | Another tester used the same serial or reference: add your tester number |
| `INSUFFICIENT_AVAILABLE` | 12–13 | Fewer available credits than requested |
| `BUYER_KYC_REQUIRED` | 13 | Buyer KYC not verified (13.2) |
| `PAYMENT_AMOUNT_MISMATCH` | 13.7 | The payment must equal the order total |
| `SHARING_RULE_NOT_EFFECTIVE` | 14.5 | The share version does not cover the whole period: Effective from ≤ 06/01/2026, Effective to empty |
| `ALLOCATION_NOT_CONSERVED` | 14.3 | Farm shares must total exactly 100 |
| `BANK_ACCOUNT_NOT_VERIFIED` | 14.6b | Verify the bank account (14.4) with a different Finance Manager |
| "Too many sign-in attempts" | any | `LOGIN_RATE_LIMIT_PER_MINUTE=100` in `backend/.env`, restart the backend |
