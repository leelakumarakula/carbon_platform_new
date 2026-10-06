# Test walkthrough — who logs in, what they fill, who verifies next

A step-by-step script for the test team. Follow the steps **in order**. Every step says:

- **LOGIN** — which test user signs in (switch browser window or sign out and in),
- **TYPE** — what kind of step it is:
  - **FILL**: enter data and submit;
  - **VERIFY**: a second person checks someone else's work;
  - **APPROVE**: a second person approves it;
  - **NEGATIVE CHECK**: try something that must be **refused**;
- **GO TO** — the menu and tab,
- **ENTER** — the values to type,
- **CLICK** — the buttons,
- **YOU SHOULD SEE** — the expected result,
- **NEXT** — who logs in for the next step.

Field rules and allowed values for every form are in [e2e-test-guide.md](e2e-test-guide.md). This walkthrough only gives the order and the values.

**Every action button asks for a reason** — type `ok test` (3+ characters). **Date boxes are month/day/year** (`06/01/2026` = 1 June 2026).

Keep 2–3 browser windows open (normal, Incognito, another browser) so you can switch users quickly.

---

## The whole flow at a glance

| Stage | Logins in order | What happens |
|---|---|---|
| 0 Setup | leelak | Create organizations and users |
| 1 Catalog | leelak | Standard and activity |
| 2 Methodology | ms1 → ms2 | ms1 writes the methodology and picks the module; ms2 approves |
| 3 Farmer | pm → qa → pm | pm registers and submits KYC; qa verifies KYC; pm activates |
| 4 Farm | pm → gis | pm records farm, boundary, ownership; gis verifies |
| 5 Project | pm → gis → qa → pm | pm builds and submits; gis accepts boundary; qa verifies rights and approves; pm confirms activity |
| 6 Methodology lock | ms1 → pm | ms1 recommends; pm locks |
| 7 MRV | mrv → qa → mrv → gis → sup | plan, approval, period, stratum, approval |
| 8 Data | mrv → qa | factor values and dataset; qa approves |
| 9 Calculation | analyst → qa | run; qa approves |
| 10 Verification | qa → analyst → qa → analyst → qa → pm → vvb → pm → vvb | internal finding, report, readiness; VVB accepts and decides |
| 11 Registry | pm → qa | account, registration, submission, issuance; qa confirms |
| 12 Ledger | credits → qa → credits → qa → credits → qa → buyer → qa | open, retire, transfer, buyer retires |
| 13 Marketplace | buyer → compliance → credits → fin1 → buyer → fin1 → qa → buyer | KYC, listing, order, payment, delivery |
| 14 Payout | pm → fin1 → pm → fin1 → pm → fin1 → fin2 → fin1 → fin2 → fin3 → fin2 | sharing, allocation, bank, settlement, payout |

Test users (create the **bold** ones in Stage 0):

| Login | Role | Organization |
|---|---|---|
| leelak@vayublue.com | Platform Admin | platform |
| ms1@yopmail.com, ms2@yopmail.com | Methodology Specialist | platform |
| pm@yopmail.com | Project Manager | varsapradaya_developer |
| qa@yopmail.com | QA Officer | varsapradaya_developer |
| gis@yopmail.com | GIS Specialist | varsapradaya_developer |
| mrv@yopmail.com | MRV Manager | varsapradaya_developer |
| sup@yopmail.com | Field Supervisor | varsapradaya_developer |
| analyst@yopmail.com | Calculation Analyst | varsapradaya_developer |
| vvb@yopmail.com | VVB / ACVA Reviewer | verify_co |
| **credits@yopmail.com** | Credit Manager | varsapradaya_developer |
| **fin1@yopmail.com**, **fin2@yopmail.com**, **fin3@yopmail.com** | Finance / Payout Manager | varsapradaya_developer |
| **buyer@yopmail.com** | Buyer | Test Buyer |
| **compliance@yopmail.com** | Marketplace Compliance Officer | platform |

Several testers on one database: use your tester number (`01`, `02`, …) wherever a step says *+ tester no.*

---

## Stage 0 — Setup

### 0.1 · LOGIN `leelak` · FILL — Create the organizations
**GO TO:** Administration → Organizations → **New organization**

| Organization | Code | Type |
|---|---|---|
| Test Registry | `TESTREG` | Registry |
| Test Buyer | `TESTBUYER` | Buyer |

Country `IN`; other fields empty. **CLICK:** Create (once per organization).

**YOU SHOULD SEE:** both organizations listed as Active.

**NEXT:** stay as `leelak`.

### 0.2 · LOGIN `leelak` · FILL — Create the new users
**GO TO:** Administration → Users → **New user**

| Email | Full name | Organization | Add role |
|---|---|---|---|
| `credits@yopmail.com` | `credit_test` | varsapradaya_developer | Credit Manager |
| `fin1@yopmail.com` | `finance_one` | varsapradaya_developer | Finance / Payout Manager |
| `fin2@yopmail.com` | `finance_two` | varsapradaya_developer | Finance / Payout Manager |
| `fin3@yopmail.com` | `finance_three` | varsapradaya_developer | Finance / Payout Manager |
| `buyer@yopmail.com` | `buyer_test` | Test Buyer | Buyer |
| `compliance@yopmail.com` | `compliance_test` | None (platform staff) | Marketplace Compliance Officer |

Copy each temporary password. **CLICK:** Create user.

**YOU SHOULD SEE:** the users listed with "Must change password".

**NEXT:** stay as `leelak` → Stage 1.

---

## Stage 1 — Catalog
*Flow: leelak FILL.* Skip if `GS` and `AGR-SOC` already exist.

### 1.1 · LOGIN `leelak` · FILL — Standard and activity
**GO TO:** Projects → **Standards & activities**

| Card | Field | Enter |
|---|---|---|
| Standard | Code | `GS` |
| | Name | `Gold Standard for the Global Goals` |
| | Programme owner | `Gold Standard Foundation` |
| | Type | Voluntary |
| Activity | Code | `AGR-SOC` |
| | Name | `Agriculture - soil organic carbon` |
| | Offered under | tick Gold Standard for the Global Goals |

**CLICK:** Add standard, then Add activity.

**YOU SHOULD SEE:** the activity row says "Offered under: Gold Standard for the Global Goals".

**NEXT:** log in as `ms1`.

---

## Stage 2 — Methodology
*Flow: ms1 FILL → ms1 NEGATIVE CHECK → ms2 APPROVE.*

### 2.1 · LOGIN `ms1` · FILL — Methodology, version and module
**GO TO:** Methodologies

| Where | Field | Enter |
|---|---|---|
| Add a methodology (skip if GS402 exists) | Code | `GS402` |
| | Name | `Gold Standard SOC Framework` |
| | Standard / route | Gold Standard for the Global Goals |
| | Activities | Agriculture - soil organic carbon |
| New version | New version label | `1.0` — or `1.0-IT-A3-` + tester no. if `1.0` exists |
| Version page → details | Effective from | `01/01/2020` |
| | Source | `Gold Standard SOC Framework Methodology v1.0` |
| Tab **calculation** | Calculation module | **GS 402 + 402.1 Improved Tillage - Approach 3 (IPCC stock change factors, Eqs. 4 and 6) · v1.0.0** |
| Tab **applicability** — rule 1 | Code / Title / Category | `A1` / `Standard is GS` / Standard |
| | Fact key / Operator / Expected value / If it fails | `standard_code` / EQUALS / `"GS"` / Not applicable |
| Tab **applicability** — rule 2 | Code / Title / Category | `A2` / `Activity is AGR-SOC` / Activity |
| | Fact key / Operator / Expected value / If it fails | `activity_code` / EQUALS / `"AGR-SOC"` / Not applicable |

**CLICK:** Add methodology → New draft version → Open → Save details → **Use this module** → Use module → Add rule (×2) → **Submit for approval**.

**YOU SHOULD SEE:** badge **Module: GS402-IT-A3** (must end in **-A3**), status **In review**.

**NEXT:** stay as `ms1`.

> Choose the module **before** submitting. After approval it can never be changed.

### 2.2 · LOGIN `ms1` · NEGATIVE CHECK
**CLICK:** Approve. **YOU SHOULD SEE:** refused — the submitter cannot approve.

**NEXT:** log in as `ms2`.

### 2.3 · LOGIN `ms2` · APPROVE
**GO TO:** Methodologies → GS402 → the version. **CLICK:** Approve (reason).

**YOU SHOULD SEE:** **Approved**; "Calculation: Not production ready" is normal.

**NEXT:** log in as `pm`.

---

## Stage 3 — Farmer
*Flow: pm FILL → pm NEGATIVE CHECK → qa VERIFY → pm FILL.*

### 3.1 · LOGIN `pm` · FILL — Register the farmer and submit KYC
**GO TO:** Farmers → **Register farmer**

| Field | Enter |
|---|---|
| Managing organization | varsapradaya_developer |
| Full name | `Ramesh Patil` |
| Gender | MALE |
| Preferred language | `mr` |
| Primary phone | `+91 98765 43210` |
| Village / District / State | `Ozar` / `Nashik` / `Maharashtra` |
| Country | `IN` |

**CLICK:** Create farmer → header **Register** (reason).

Then tab **KYC**: ID type National ID · ID number `1234 5678 90` + tester no. · Attach ID document (any PDF) → **Submit for review**.

**YOU SHOULD SEE:** status **KYC pending**.

**NEXT:** stay as `pm`.

### 3.2 · LOGIN `pm` · NEGATIVE CHECK
On the KYC tab look for Verify. **YOU SHOULD SEE:** "You submitted this KYC, so another reviewer must decide".

**NEXT:** log in as `qa`.

### 3.3 · LOGIN `qa` · VERIFY — KYC
**GO TO:** Farmers → Ramesh Patil → tab KYC. **ENTER:** Review notes `ID checked`. **CLICK:** **Verify KYC**.

**YOU SHOULD SEE:** **KYC verified**.

**NEXT:** log in as `pm`.

### 3.4 · LOGIN `pm` · FILL — Consent, activation, agreement
**GO TO:** Farmers → Ramesh Patil

| Tab | Enter | Click |
|---|---|---|
| Consents | keep defaults: Personal data processing (v1) · `DATA_PROCESSING-v1` · Paper signed | Record consent |
| Header | — | **Activate** (reason) |
| Agreements | Type `PROGRAM_PARTICIPATION` · Template version `v1` · Effective from `06/01/2026` | Create agreement → Upload signed copy (PDF) |

**YOU SHOULD SEE:** farmer **Active**; agreement **Signed** — note its code `AGR-2026-…`.

**NEXT:** stay as `pm` → Stage 4.

---

## Stage 4 — Farm
*Flow: pm FILL → pm NEGATIVE CHECK → gis VERIFY.*

### 4.1 · LOGIN `pm` · FILL — Farm, boundary, document, ownership
**GO TO:** Farmers → Ramesh Patil → tab Farms → **Add farm**

| Tab / form | Field | Enter |
|---|---|---|
| Add farm | Farm name / Land tenure / Declared area / Country | `North block` / Owned / `100` / `IN` |
| Boundary | Paste several corners | the 4 lines below |
| Documents | Category / Title / file | Land record / `7/12 extract Survey 45/2` / any PDF |
| Ownership | Owner type / Relationship / Share % | Farmer / Owner / `100` |
| | Title reference / Valid from | `Survey 45/2` / `01/01/2020` |
| | Evidence document | `7/12 extract Survey 45/2` (pre-selected) |

```
20.1000, 73.7000
20.1000, 73.7096
20.1090, 73.7096
20.1090, 73.7000
```
Tester 2 adds `0.02` to each latitude, tester 3 adds `0.04`, …

**CLICK:** Create farm and draw boundary → Add these corners → Check boundary → Save as new boundary version → Upload → Record ownership → header **Submit for review**.

**YOU SHOULD SEE:** area ≈ 100 ha; farm **Submitted**.

**NEXT:** stay as `pm`.

### 4.2 · LOGIN `pm` · NEGATIVE CHECK
Look for **Verify farm**. **YOU SHOULD SEE:** not available to the submitter.

**NEXT:** log in as `gis`.

### 4.3 · LOGIN `gis` · VERIFY — Ownership and farm
**GO TO:** Farms → North block

| Order | Where | Click |
|---|---|---|
| 1 | Tab Ownership | **Verify** → reason `Land record checked` |
| 2 | Header | **Start GIS review** |
| 3 | Tab Overlaps | **Clear** anything listed (only if another tester overlaps) |
| 4 | Header | **Verify farm** |

**YOU SHOULD SEE:** ownership Verified; farm **Verified**.

**NEXT:** log in as `pm`.

---

## Stage 5 — Project and eligibility
*Flow: pm FILL → gis VERIFY → qa VERIFY → pm NEGATIVE CHECK → qa APPROVE → pm FILL.*

### 5.1 · LOGIN `pm` · FILL — Build and submit the project
**GO TO:** Projects → **New project**

| Tab / form | Field | Enter |
|---|---|---|
| New project | Organization / Name / Type | varsapradaya_developer / `Nashik tillage pilot` (+ tester no.) / Agricultural land management |
| | Country / Region / Planned start | `IN` / `Nashik` / `06/01/2026` |
| Header | Start data collection | reason |
| Farms | Farm / Participation from / Rights holder | North block / `06/01/2026` / Farmer |
| | Agreement / evidence reference / Share % | `Carbon rights clause of AGR-2026-…` / `100` |
| Standard & activity | Standard / Activity | Gold Standard → Select / Agriculture - soil organic carbon → Select |
| Crediting & baseline | Crediting period | `06/01/2026` – `05/31/2036` → Record period |
| | Baseline From / To / Practices / Data sources | `06/01/2021` / `05/31/2026` / `Conventional tillage, residue burning` / `Farmer interview` → Record baseline |

**CLICK:** Create project → Start data collection → Add farm → Select ×2 → Record period → Record baseline → header **Submit for eligibility review**.

**YOU SHOULD SEE:** status **Eligibility review**.

**NEXT:** log in as `gis`.

### 5.2 · LOGIN `gis` · VERIFY — Project boundary
**GO TO:** Projects → the project → tab **Boundary**. **CLICK:** **Accept boundary** (reason).

**YOU SHOULD SEE:** Review: Accepted.

**NEXT:** log in as `qa`.

### 5.3 · LOGIN `qa` · VERIFY — Carbon rights
**GO TO:** the project → tab **Carbon rights**. **CLICK:** **Verify** → reason `Agreement checked`.

**YOU SHOULD SEE:** rights Verified.

**NEXT:** log in as `pm` for a quick check.

### 5.4 · LOGIN `pm` · NEGATIVE CHECK
Look for **Approve eligibility**. **YOU SHOULD SEE:** not shown to the submitter.

**NEXT:** log in as `qa`.

### 5.5 · LOGIN `qa` · APPROVE — Eligibility
**GO TO:** the project header. **CLICK:** **Approve eligibility** (reason).

**YOU SHOULD SEE:** **Standard selected**.

**NEXT:** log in as `pm`.

### 5.6 · LOGIN `pm` · FILL — Confirm activity
**CLICK:** header **Confirm activity** (reason). **YOU SHOULD SEE:** **Activity selected**.

**NEXT:** log in as `ms1`.

---

## Stage 6 — Lock the methodology
*Flow: ms1 FILL → ms1 NEGATIVE CHECK → pm APPROVE.*

### 6.1 · LOGIN `ms1` · FILL — Evaluate and recommend
**GO TO:** Projects → the project → tab **Methodology**. Leave Declared facts empty.

**CLICK:** **Evaluate candidates** → expand GS402 → **Recommend** → reason `Applicable; module GS402-IT-A3`.

**YOU SHOULD SEE:** candidate **Applicable** (A1 ✔ A2 ✔); "Recommended by" your name; status **Methodology review**.

**NEXT:** stay as `ms1`.

### 6.2 · LOGIN `ms1` · NEGATIVE CHECK
Try **Confirm & lock**. **YOU SHOULD SEE:** not allowed.

**NEXT:** log in as `pm`.

### 6.3 · LOGIN `pm` · APPROVE — Confirm and lock
**GO TO:** tab Methodology → expand the candidate. **CLICK:** **Confirm & lock** (reason). Do **not** re-evaluate or unlock.

**YOU SHOULD SEE:** lock card; status **Methodology confirmed**; **MRV workspace** button.

**NEXT:** log in as `mrv`.

---

## Stage 7 — MRV plan, period, stratum
*Flow: mrv FILL → mrv NEGATIVE CHECK → qa APPROVE → mrv FILL → gis FILL → gis NEGATIVE CHECK → sup APPROVE.*

### 7.1 · LOGIN `mrv` · FILL — MRV plan
**GO TO:** MRV → choose the project at the top → tab **MRV plans** → **Create MRV plan**

| Field | Enter |
|---|---|
| Monitoring frequency | `Annual` |
| Quantification approach | **leave empty** |
| Monitoring start / end | `06/01/2026` / `05/31/2036` |
| Required evidence | `Factor sources (IPCC tables)` |
| Project measurements | add none |

**CLICK:** Create plan (draft) → **Submit for approval**.

**YOU SHOULD SEE:** the `GS_…` measurements listed; plan **Submitted**.

**NEXT:** stay as `mrv`.

### 7.2 · LOGIN `mrv` · NEGATIVE CHECK
Look for **Approve** on the plan. **YOU SHOULD SEE:** not shown.

**NEXT:** log in as `qa`.

### 7.3 · LOGIN `qa` · APPROVE — MRV plan
**GO TO:** MRV → project → MRV plans → open the plan. **CLICK:** **Approve** (reason; the gaps notice is expected).

**YOU SHOULD SEE:** plan **Approved**; project **MRV planned**.

**NEXT:** log in as `mrv`.

### 7.4 · LOGIN `mrv` · FILL — Monitoring period
**GO TO:** tab **Monitoring periods**. **ENTER:** Name `Period 1` · Purpose Monitoring · Start `06/01/2026` · End `05/31/2027`.

**CLICK:** Create period → **Mark planned** → **Start period** → **Open data collection**.

**YOU SHOULD SEE:** period **Data collection**; project **Monitoring**.

**NEXT:** log in as `gis`.

### 7.5 · LOGIN `gis` · FILL — Stratum
**GO TO:** tab **Stratification** → New, keep **Project stratum**. **ENTER:** Code `S1` · Name `Tillage plots` · Farms North block · Characteristic Soil type · Value `Black soil` → click **+**.

**CLICK:** **Create stratum**.

**YOU SHOULD SEE:** S1 Draft, area ≈ 100 ha.

**NEXT:** stay as `gis`.

### 7.6 · LOGIN `gis` · NEGATIVE CHECK
Look for **Approve** on S1. **YOU SHOULD SEE:** not available to the creator.

**NEXT:** log in as `sup`.

### 7.7 · LOGIN `sup` · APPROVE — Stratum
**GO TO:** MRV → project → Stratification. **CLICK:** **Approve** on S1 (reason).

**YOU SHOULD SEE:** S1 **Approved**.

**NEXT:** log in as `mrv`.

---

## Stage 8 — Factor data and dataset
*Flow: mrv FILL → mrv NEGATIVE CHECK → qa VERIFY + APPROVE.*

### 8.1 · LOGIN `mrv` · FILL — Factor values
**GO TO:** MRV → project → tab **Monitoring data**. For **every** row: Stratum `S1 · Tillage plots` · Observed on `10/05/2026` · Phase Project · Source Document → **Record value**.

| Measurement | Value |
|---|---|
| GS_SOC_REF | `47` |
| GS_F_LU | `0.83` |
| GS_F_MG_BL | `1.00` |
| GS_F_I_BL | `0.92` |
| GS_F_MG_PR | `1.10` |
| GS_F_I_PR | `1.11` |
| GS_T_BL | `20` |
| GS_T_PR | `1` |
| GS_U_SOC_REF | `2` |
| GS_U_F_LU | `2` |
| GS_U_F_MG_BL | `1` |
| GS_U_F_I_BL | `1` |
| GS_U_F_MG_PR | `1` |
| GS_U_F_I_PR | `1` |
| GS_PAA (project level — no stratum box) | `YES` |

Record each measurement **once**; fix a mistake with **Correct** on its row.

**YOU SHOULD SEE:** 15 records in the table.

**NEXT:** stay as `mrv`.

### 8.2 · LOGIN `mrv` · FILL — Submit the dataset
**GO TO:** tab **Datasets & QA** → Monitoring period `Period 1`. **CLICK:** **Create dataset version** → **Open / QA** → **Submit for QA**.

**YOU SHOULD SEE:** dataset **Submitted**.

**NEXT:** stay as `mrv`.

### 8.3 · LOGIN `mrv` · NEGATIVE CHECK
Look for **Record QA result**. **YOU SHOULD SEE:** not available to the submitter.

**NEXT:** log in as `qa`.

### 8.4 · LOGIN `qa` · VERIFY + APPROVE — Dataset
**GO TO:** MRV → project → Datasets & QA → Open / QA.

**CLICK:** **Start QA review** → QA result `PASS` → **Record QA result** → **Approve dataset**.

**YOU SHOULD SEE:** every check PASS or WARN; dataset and period **Approved**.

**NEXT:** log in as `analyst`.

---

## Stage 9 — Calculation
*Flow: analyst FILL → analyst NEGATIVE CHECK → qa VERIFY + APPROVE.*

### 9.1 · LOGIN `analyst` · FILL — Calculation run
**GO TO:** **Calculations** → Project `Nashik tillage pilot` · Period `Period 1`.

**CLICK:** **New calculation run** → open the run → **Check readiness & freeze inputs** → **Execute** → **Submit for QA**.

**YOU SHOULD SEE:** no red blocker (only "NOT_PRODUCTION_READY"); outputs incl. **GS_VER_TOTAL ≈ 170** — write the exact number down.

**NEXT:** stay as `analyst`.

### 9.2 · LOGIN `analyst` · NEGATIVE CHECK
Look for **Approve** on the run. **YOU SHOULD SEE:** not available to the creator.

**NEXT:** log in as `qa`.

### 9.3 · LOGIN `qa` · VERIFY + APPROVE — Calculation
**GO TO:** Calculations → the run → tab **QA**. **CLICK:** **Start calculation QA** → Result `PASS` · Notes `Inputs and outputs checked` → **Record QA** → header **Approve**.

**YOU SHOULD SEE:** run **Approved**.

**NEXT:** stay as `qa` → Stage 10.

---

## Stage 10 — Internal readiness and VVB verification
*Flow: qa FILL → analyst FILL → analyst NEGATIVE CHECK → qa VERIFY → analyst FILL → analyst NEGATIVE CHECK → qa APPROVE → pm FILL → vvb FILL → pm FILL → vvb VERIFY + APPROVE.*

### 10.1 · LOGIN `qa` · FILL — Internal finding
**GO TO:** the run → tab **Findings**. **ENTER:** Category Clarification · Blocking ticked · Title `Source of factors` · Description `Cite the IPCC table used for F_MG and F_I`.

**CLICK:** **Raise finding**. **YOU SHOULD SEE:** finding **Open**.

**NEXT:** log in as `analyst`.

### 10.2 · LOGIN `analyst` · FILL — Respond
**GO TO:** the run → tab Findings. **ENTER:** Response `IPCC 2019 Vol. 4 Ch. 5 Table 5.5 (test values)`. **CLICK:** **Respond**.

**YOU SHOULD SEE:** **Responded**. Look for **Resolve** — it must **not** be shown to you (NEGATIVE CHECK).

**NEXT:** log in as `qa`.

### 10.3 · LOGIN `qa` · VERIFY — Resolve the finding
**CLICK:** **Resolve** → reason `Source accepted`. **YOU SHOULD SEE:** **Resolved**.

**NEXT:** log in as `analyst`.

### 10.4 · LOGIN `analyst` · FILL — Report and readiness
**CLICK:** run page → **Generate report** → **Verify** (shows "Hashes verify"). Then **Calculations** → project + Period 1 → **Verification readiness** → **Prepare readiness** → **Submit**.

**YOU SHOULD SEE:** readiness **Submitted**; **Approve (READY)** is hidden for you (NEGATIVE CHECK).

**NEXT:** log in as `qa`.

### 10.5 · LOGIN `qa` · APPROVE — Readiness
**GO TO:** Calculations → project + Period 1 → Verification readiness. **CLICK:** **Approve (READY)** → reason `Internal checks complete`.

**YOU SHOULD SEE:** **READY**.

**NEXT:** log in as `pm`.

### 10.6 · LOGIN `pm` · FILL — Propose the VVB
**GO TO:** MRV → project → tab **Verification**. **ENTER:** VVB / ACVA organization `verify_co` · Notes `Verification of Period 1`. **CLICK:** **Propose**.

**YOU SHOULD SEE:** assignment **Proposed**.

**NEXT:** log in as `vvb`.

### 10.7 · LOGIN `vvb` · FILL — Accept the assignment
**GO TO:** **VVB workspace** → the assignment. **ENTER:** Conflict-of-interest declaration `No financial or personal interest in the project or its developer`. **CLICK:** **Accept**.

**YOU SHOULD SEE:** **Accepted**; project **Verification**.

**NEXT:** log in as `pm`.

### 10.8 · LOGIN `pm` · FILL — Submit the package
**GO TO:** MRV → project → Verification. **CLICK:** **Submit READY package**.

**YOU SHOULD SEE:** submission `SUB-…` **Submitted**.

**NEXT:** log in as `vvb`.

### 10.9 · LOGIN `vvb` · VERIFY + APPROVE — Review and decide
**GO TO:** VVB workspace → the assignment → tabs **Package** and **Documents** (review), then tab **Decision**.

| Field | Enter |
|---|---|
| Outcome | Verified |
| VVB-stated verified quantity | the GS_VER_TOTAL from 9.1 (e.g. `170`) |
| Unit | `tCO2e` |
| Rationale | `Factors and calculation checked against the package` |
| Verification report | any PDF |

**CLICK:** **Record decision**.

**YOU SHOULD SEE:** assignment **Completed**; project **Verified**.

**NEXT:** log in as `pm`.

---

## Stage 11 — Registry and issuance
*Flow: pm FILL → pm NEGATIVE CHECK → qa APPROVE.*

### 11.1 · LOGIN `pm` · FILL — Account, registration, submission, issuance
**GO TO:** **Registry** → project + Period 1. Work top to bottom:

| Form | Field | Enter | Click |
|---|---|---|---|
| Registry account | Registry / Account ID / Label | Test Registry / `ACC-` + tester no. / `Main GS account` | |
| | Registry credit unit / = 1 verified unit | `VER` / `tCO2e` | Record account |
| Registration | Account for registration | Main GS account | Start registration record |
| | Registry project ID / Registered on / PDF | `GS-PRJ-` + tester no. / `10/05/2026` / any PDF | Record registered |
| Submission | Registry account | Main GS account | Prepare registry submission → Freeze snapshot |
| | Submission reference / receipt PDF | `GS-SUB-` + tester no. / any PDF | Record submitted |
| | Outcome / response PDF | Accepted / any PDF | Record response |
| Issuance | Issuance ID / date / Unit / statement PDF | `GS-ISS-` + tester no. / `10/05/2026` / `VER` / any PDF | |
| | Batch: Vintage / Whole credits | `2026` / the VVB quantity (e.g. `170`) | |
| | Batch: Serial start / end | `GS-T01-2026-000001` / `GS-T01-2026-000170` (your tester no.) | Record issuance |

**YOU SHOULD SEE:** account "1 VER = 1 tCO2e"; registration Registered; submission Accepted; issuance **Recorded**. The **Confirm** button is not shown to you (NEGATIVE CHECK).

**NEXT:** log in as `qa`.

### 11.2 · LOGIN `qa` · APPROVE — Confirm the issuance
**GO TO:** Registry → project + Period 1. **CLICK:** **Confirm (second person)** → note `Matches registry statement`.

**YOU SHOULD SEE:** issuance **Confirmed**; batch **Issued**; project **Issued**.

**NEXT:** log in as `credits`.

---

## Stage 12 — Credit ledger
*Flow: credits FILL → qa APPROVE → credits FILL → qa APPROVE → credits FILL → qa APPROVE → buyer FILL → qa APPROVE.*

### 12.1 · LOGIN `credits` · FILL — Request opening
**GO TO:** **Credit ledger** → the batch. **CLICK:** **Open in ledger** → reason → **Request opening**.

**YOU SHOULD SEE:** opening **Requested**; **Confirm opening** not available to you (NEGATIVE CHECK).

**NEXT:** log in as `qa`.

### 12.2 · LOGIN `qa` · APPROVE — Confirm opening
**CLICK:** **Confirm opening**. **YOU SHOULD SEE:** Available 170 owned by varsapradaya_developer.

**NEXT:** log in as `credits`.

### 12.3 · LOGIN `credits` · FILL — Request a retirement
**GO TO:** Credit ledger → batch → **Details** → Request retirement. **ENTER:** Owner varsapradaya_developer · Quantity `10` · Beneficiary `Varsapradaya Developer` · Retirement reason `Test retirement by the developer`.

**CLICK:** **Request retirement**. **YOU SHOULD SEE:** 10 Retirement pending.

**NEXT:** log in as `qa`.

### 12.4 · LOGIN `qa` · APPROVE — Record the retirement
**GO TO:** batch → Details → Retirements. **ENTER:** Registry retirement reference `GS-RET-` + tester no. + `-A` · date `10/05/2026` · certificate PDF.

**CLICK:** **Record retirement**. **YOU SHOULD SEE:** 10 **Retired**.

**NEXT:** log in as `credits`.

### 12.5 · LOGIN `credits` · FILL — Request a transfer to the buyer
**GO TO:** batch → Details → Request transfer. **ENTER:** Kind Internal · Sender varsapradaya_developer · Recipient Test Buyer · Quantity `10` · Purpose `Test transfer`.

**CLICK:** **Request transfer**. **YOU SHOULD SEE:** 10 Transfer pending.

**NEXT:** log in as `qa`.

### 12.6 · LOGIN `qa` · APPROVE — Complete the transfer
**GO TO:** batch → Details → Transfers. **CLICK:** **Complete**. **YOU SHOULD SEE:** Test Buyer owns 10.

**NEXT:** log in as `buyer`.

### 12.7 · LOGIN `buyer` · FILL — Retire own credits
**GO TO:** **My credits** → AVAILABLE row → **Request retirement**. **ENTER:** Quantity `5` · Beneficiary `Test Buyer Ltd` · Retirement reason `Offsetting 2026 travel`.

**YOU SHOULD SEE:** request listed under Retirement requests.

**NEXT:** log in as `qa`.

### 12.8 · LOGIN `qa` · APPROVE — Record the buyer's retirement
**GO TO:** Credit ledger → batch → Details → Retirements. **ENTER:** reference `GS-RET-` + tester no. + `-B` · date · certificate PDF. **CLICK:** **Record retirement**.

**YOU SHOULD SEE:** 5 **Retired**; 150 still available to the developer.

**NEXT:** log in as `buyer`.

---

## Stage 13 — Marketplace
*Flow: buyer FILL → compliance VERIFY → credits FILL → fin1 APPROVE → buyer FILL → fin1 VERIFY → qa APPROVE → buyer CHECK.*

### 13.1 · LOGIN `buyer` · FILL — Buyer profile and KYC
**GO TO:** **Buyer profile**. **ENTER:** Legal name `Test Buyer Ltd` · Registration number `U12345MH2026PTC0000` + tester no. · Country `IN` · Contact name `Asha Rao` · Contact email `buyer@yopmail.com`.

**CLICK:** **Save** → KYC documents: choose a PDF → **Upload** → **Submit for KYC review**.

**YOU SHOULD SEE:** **KYC submitted**.

**NEXT:** log in as `compliance`.

### 13.2 · LOGIN `compliance` · VERIFY — Buyer KYC
**GO TO:** **KYC review** → Test Buyer Ltd. **CLICK:** **Verify** → reason `Registration documents checked`.

**YOU SHOULD SEE:** **KYC verified**.

**NEXT:** log in as `credits`.

### 13.3 · LOGIN `credits` · FILL — Listing
**GO TO:** **Listings** → **New listing**

| Field | Enter |
|---|---|
| Credits | your batch |
| Title | `GS402 Nashik tillage 2026` |
| Listed quantity | `100` |
| Price per credit / Currency | `500.00` / `INR` |
| Min order / Max order | `1` / `50` |
| Payment window (hours) | `48` |
| Co-benefits | `Soil health, farmer income` |

**CLICK:** **Create draft** → row **Submit**.

**YOU SHOULD SEE:** **Pending approval**; **Approve** hidden for you (NEGATIVE CHECK).

**NEXT:** log in as `fin1`.

### 13.4 · LOGIN `fin1` · APPROVE — Listing
**GO TO:** **Listings**. **CLICK:** **Approve** → reason `Price approved`. **YOU SHOULD SEE:** listing **Active**.

**NEXT:** log in as `buyer`.

### 13.5 · LOGIN `buyer` · FILL — Order and payment
**GO TO:** **Marketplace** → the listing → **Details**. **ENTER:** Quantity `20` → **Add to order** · Delivery Ledger transfer → **Place order**.

Then **Orders** → Open → Payment reference `UTR-` + tester no. + `-0001` · PDF evidence → **Record payment**.

**YOU SHOULD SEE:** order **Placed**, total INR 10,000.00; payment **Pending confirmation**; no Confirm button for you (NEGATIVE CHECK).

**NEXT:** log in as `fin1`.

### 13.6 · LOGIN `fin1` · VERIFY — Payment
**GO TO:** **Payments**. **CLICK:** **Confirm receipt** → reason `Funds received`.

**YOU SHOULD SEE:** payment **Confirmed**; order **Transfer pending**.

**NEXT:** log in as `qa`.

### 13.7 · LOGIN `qa` · APPROVE — Delivery
**GO TO:** **Credit ledger** → batch → Details → Transfers (row "marketplace order ORD-…"). **CLICK:** **Complete**.

**YOU SHOULD SEE:** order **Completed**.

**NEXT:** log in as `buyer`.

### 13.8 · LOGIN `buyer` · CHECK — Holdings
**GO TO:** **My credits**. **YOU SHOULD SEE:** 25 credits (5 left from Stage 12 + 20 bought).

**NEXT:** log in as `pm`.

---

## Stage 14 — Revenue sharing, settlement, payout
*Flow: pm FILL → fin1 APPROVE → pm FILL → fin1 APPROVE → pm FILL → fin1 VERIFY → fin1 FILL → fin2 APPROVE → fin1 FILL → fin2 APPROVE → fin3 FILL → fin2 VERIFY.*

Every Finance page has a **Project** picker — choose `Nashik tillage pilot`.

### 14.1 · LOGIN `pm` · FILL — Revenue-share version
**GO TO:** **Revenue & costs** — check one revenue record of INR 10,000. Then **Revenue sharing**:

| Field | Enter |
|---|---|
| Farmer share % | `60` |
| Rounding mode | HALF_UP |
| Deduct approved project costs | unticked |
| Effective from / to | `06/01/2026` / empty |
| Source (agreement / clause) | `Farmer agreement AGR-2026-… clause 7` |

**CLICK:** **Create draft version** → **Submit**. **YOU SHOULD SEE:** version **In review**.

**NEXT:** log in as `fin1`.

### 14.2 · LOGIN `fin1` · APPROVE — Revenue-share version
**GO TO:** Revenue sharing. **CLICK:** **Approve** (reason). **YOU SHOULD SEE:** **Approved**.

**NEXT:** log in as `pm`.

### 14.3 · LOGIN `pm` · FILL — Farm allocation
**GO TO:** Revenue sharing → farm allocation. **ENTER:** Monitoring period `Period 1` · Basis `Single participating farm` · North block `100` (Total: 100 %).

**CLICK:** **Create draft allocation** → **Submit**.

**NEXT:** log in as `fin1`.

### 14.4 · LOGIN `fin1` · APPROVE — Farm allocation
**CLICK:** **Approve** (reason). **YOU SHOULD SEE:** allocation **Approved**.

**NEXT:** log in as `pm`.

### 14.5 · LOGIN `pm` · FILL — Farmer bank account
**GO TO:** Farmers → Ramesh Patil → tab **Bank**. **ENTER:** Account holder `Ramesh Patil` · Bank `State Bank of India` · Branch `Nashik Main` · Routing code `SBIN0001234` · Account number `1234567890` + tester no.

**CLICK:** **Add bank account**. **YOU SHOULD SEE:** **Pending verification**.

**NEXT:** log in as `fin1`.

### 14.6 · LOGIN `fin1` · VERIFY — Bank account
**GO TO:** Farmers → Ramesh Patil → Bank. **CLICK:** **Verify** → reason `Cancelled cheque checked`. **YOU SHOULD SEE:** **Verified**.

**NEXT:** stay as `fin1`.

### 14.7 · LOGIN `fin1` · FILL — Settlement run
**GO TO:** **Settlements**. **ENTER:** Monitoring period `Period 1` · Currency `INR` · the approved revenue-share version · the approved farm allocation.

**CLICK:** **Create run** → **Calculate** → **Verify (recompute from snapshot)** → **Submit**.

**YOU SHOULD SEE:** entitlement **INR 6,000.00** for Ramesh Patil; "Reproducible"; **Pending approval**; Approve hidden for you (NEGATIVE CHECK).

**NEXT:** log in as `fin2`.

### 14.8 · LOGIN `fin2` · APPROVE — Settlement
**GO TO:** Settlements → the run. **CLICK:** **Approve** → reason `Entitlements checked`. **YOU SHOULD SEE:** run **Approved**.

**NEXT:** log in as `fin1`.

### 14.9 · LOGIN `fin1` · FILL — Create the payout
**GO TO:** Settlements → the run → **Create payouts**; then **Payouts** → **Submit**.

**YOU SHOULD SEE:** payout **Pending approval**.

**NEXT:** log in as `fin2`.

### 14.10 · LOGIN `fin2` · APPROVE — Payout
**GO TO:** **Payouts**. **CLICK:** **Approve** → reason `Approved for payment`.

**YOU SHOULD SEE:** **Approved**; **Execute** not available to you (NEGATIVE CHECK).

**NEXT:** log in as `fin3`.

### 14.11 · LOGIN `fin3` · FILL — Pay
**GO TO:** **Payouts**. **CLICK:** **Execute** → **Record paid** → Bank / remittance reference `NEFT-` + tester no. + `-0001` · PDF → **Upload evidence and record PAID**.

**YOU SHOULD SEE:** payout **Paid**.

**NEXT:** log in as `fin2`.

### 14.12 · LOGIN `fin2` · VERIFY — Reconcile
**GO TO:** **Payouts** → **Reconcile**. **ENTER:** Statement reference = the same `NEFT-…` · Statement amount `6000.00` · Currency `INR` · Statement date `10/05/2026` · PDF.

**CLICK:** **Upload statement and reconcile**.

**YOU SHOULD SEE:** payout **Reconciled**; settlement run **Completed**. **End of the main flow.**

---

## If a step fails
- **A button is missing:** you are logged in as the wrong user, or it is your own submission. Check the step's LOGIN.
- **A red message with a code** (`SEPARATION_OF_DUTIES`, `REQUIREMENTS_NOT_MET`, …): look the code up in the Troubleshooting table of [e2e-test-guide.md](e2e-test-guide.md).
- Report every failure with: step number, login, screen, the values entered, and the error code.
