# End-to-end test — Demo_db (Verra VCS · VM0042 v2.2 · farm to farmer payout)

This document is the complete test of the platform, from an empty catalog to a farmer payout, on the **Demo_db** database. It follows
one soil-carbon project credited under **Verra's Verified Carbon Standard (VCS)** with the methodology **VM0042 v2.2** — soil sampled
twice, analysed by a laboratory, compared with control sites, verified, issued, sold, and shared with the farmer.

Every step names **who logs in**, **where to click**, **what to enter**, and **what you should see**. Everything that went wrong in our first run
is already corrected here — follow the values exactly and every step passes the first time.

| | |
|---|---|
| Database | `Demo_db` (users, organizations and roles only; everything else empty) |
| Password for every user | **`Test@12345678`** |
| Expected credits | **≈ 950 VCUs** (on a ≈ 100 ha project farm) |
| Farmer payout | **₹6,000.00** (60 % of ₹10,000 sales) |
| Time | about one working day (most of it is the 96 laboratory results) |

**Markers:** 🔎 = negative check: the action must be **refused** (a refusal is a pass) · ⚠ = a mistake we made in the first run; do it as written.

---

## Contents
- [Part A — Before you start](#part-a--before-you-start)
- [Part B — The flow at a glance](#part-b--the-flow-at-a-glance)
- Stages: [1 Setup](#stage-1--setup-users-and-organizations) · [2 Catalog](#stage-2--catalog) · [3 Methodology](#stage-3--methodology-vm0042-22-with-its-calculation-module) ·
  [4 Farmer](#stage-4--farmer) · [5 Farms](#stage-5--farms-1-project-farm--3-control-farms) · [6 Project](#stage-6--project-and-eligibility) ·
  [7 Lock](#stage-7--lock-the-methodology) · [8 MRV setup](#stage-8--mrv-plan-periods-strata-and-control-sites) · [9 Lab engagement](#stage-9--laboratory-engagement) ·
  [10 Period 0](#stage-10--period-0-baseline-sampling-and-laboratory) · [11 Period 0 dataset](#stage-11--period-0-dataset) ·
  [12 Period 1](#stage-12--period-1-remeasurement-and-laboratory) · [13 Calculation](#stage-13--period-1-dataset-and-calculation) ·
  [14 Verification](#stage-14--internal-readiness-and-vvb-verification) · [15 Registry](#stage-15--registry-and-credit-issuance) ·
  [16 Ledger](#stage-16--credit-ledger) · [17 Marketplace](#stage-17--marketplace) · [18 Payout](#stage-18--revenue-sharing-settlement-and-farmer-payout)
- [Part C — How the credits are calculated](#part-c--how-the-credits-are-calculated) · [Part D — Lessons from the first run](#part-d--lessons-from-the-first-run) ·
  [Part E — Error codes](#part-e--error-codes)

---

## Part A — Before you start

### A.1 Switch the application to Demo_db
1. In `backend/.env` change `DATABASE_URL=…/dmrv_db?…` to `…/Demo_db?…` and restart the backend (uvicorn).
2. Run the frontend: `npx ng serve` in `frontend` → open http://localhost:4200.
3. After the demo, change it back to `dmrv_db` and restart.

### A.2 Check the computer
| Check | Why |
|---|---|
| **C: drive has at least 3 GB free** | ⚠ The platform refuses every upload (photos, PDFs) when less than 1 GB would remain: "The document store is unavailable or refused the file". |
| Browser shows the **new sample form** (Depth top / Depth bottom on "Register & seal sample") | Press Ctrl+F5 once. VM0042 needs two depth layers per sample. |
| Have ready: **one JPG** (field photo) and **a few small PDFs** (lab reports, evidence) | Every result, evidence and registry step needs one. |

### A.3 House rules
- **Every action button asks for a reason** — type `ok test` (3+ characters).
- ⚠ **Dates are typed day-month-year** (`20-05-2026` = 20 May 2026). Look at the saved value after typing.
- Keep 2–3 browser windows (normal, Incognito, a second browser) to switch users without signing out.
- Almost every approval must be done by a **different person** from the one who submitted it — follow the LOGIN of each step.

### A.4 Users (all with password `Test@12345678`)
| Login | Role | Organization |
|---|---|---|
| leelak@vayublue.com | Platform Admin | platform-wide |
| ms1@yopmail.com | Methodology Specialist (author) | platform-wide |
| ms2@yopmail.com | Methodology Specialist (approver) | platform-wide |
| pm@yopmail.com | Project Manager | varsapradaya_developer |
| **qatester1@yopmail.com** | QA Officer | varsapradaya_developer |
| gis@yopmail.com | GIS Specialist | varsapradaya_developer |
| mrv@yopmail.com | MRV Manager | varsapradaya_developer |
| sup@yopmail.com | Field Supervisor | varsapradaya_developer |
| col@yopmail.com | Field Collector | varsapradaya_developer |
| analyst@yopmail.com | Calculation Analyst | varsapradaya_developer |
| labmgr@yopmail.com | Lab Manager / Lab QA | soiltestlab |
| labtec@yopmail.com | Lab Technician | soiltestlab |
| vvb@yopmail.com | VVB / ACVA Reviewer | verify_co |
| credits@ · fin1@ · fin2@ · fin3@ | Credit Manager · Finance / Payout Manager ×3 | varsapradaya_developer |
| buyer@yopmail.com | Buyer | buyer |
| compliance@yopmail.com | Marketplace Compliance Officer | platform-wide |

`qa@yopmail.com` is deactivated — **qatester1 is the QA officer** in this test.

---

## Part B — The flow at a glance

| Stage | Logins in order | Result |
|---|---|---|
| 1 Setup | leelak | Check the registry organization and 6 extra users (already created) |
| 2 Catalog | leelak | Standard `VCS`, activity `IALM` |
| 3 Methodology | ms1 → ms2 | VM0042 2.2 with its calculation module, approved |
| 4 Farmer | pm → qatester1 → pm | Ramesh Patil, KYC verified, active |
| 5 Farms | pm → gis | North block (≈ 100 ha, project) + 3 control farms (≈ 4 ha) verified |
| 6 Project | pm → gis → qatester1 → pm | Project eligible, activity selected |
| 7 Lock | ms1 → pm | VM0042 2.2 locked on the project |
| 8 MRV setup | mrv → qatester1 → mrv → gis → sup | Plan, 2 periods, stratum S1 + control sites C1–C3 |
| 9 Lab engagement | mrv → labmgr | Lab scope: organic carbon + soil mass |
| 10 Period 0 | gis → sup → col → sup → col → sup → labtec → labmgr | 12 points, 24 samples, 48 approved lab results |
| 11 Period 0 dataset | mrv → qatester1 | Baseline dataset approved |
| 12 Period 1 | gis → sup → col → sup → col → sup → labtec → labmgr → mrv | Remeasurement, 48 lab results, farm activity |
| 13 Calculation | mrv → qatester1 → analyst → qatester1 | **≈ 950 VCUs**, run approved |
| 14 Verification | qatester1 → analyst → qatester1 → pm → vvb | Project **Verified** |
| 15 Registry | pm → qatester1 | 950 VCUs **issued** |
| 16 Ledger | credits → qatester1 → buyer | Credits opened, retired, transferred |
| 17 Marketplace | buyer → compliance → credits → fin1 → buyer → fin1 → qatester1 | 20 credits sold for ₹10,000 |
| 18 Payout | pm → fin1 → fin2 → fin3 | ₹6,000 paid to the farmer and reconciled |

---

## Stage 1 — Setup: users and organizations
**Already done in Demo_db** — the registry organization and the six users below exist, password **`Test@12345678`**, no forced change.

**LOGIN `leelak`** and just check them: Administration → Organizations / Users.

| Organization | Code | Type |
|---|---|---|
| Verra Registry (test) | `VREG` | Registry |
| buyer | `BUY` | Buyer |

| Email | Organization | Role |
|---|---|---|
| `credits@yopmail.com` | varsapradaya_developer | Credit Manager |
| `fin1@yopmail.com` | varsapradaya_developer | Finance / Payout Manager |
| `fin2@yopmail.com` | varsapradaya_developer | Finance / Payout Manager |
| `fin3@yopmail.com` | varsapradaya_developer | Finance / Payout Manager |
| `buyer@yopmail.com` | buyer | Buyer |
| `compliance@yopmail.com` | none (platform-wide) | Marketplace Compliance Officer |

They cannot all sit in one organization: a Buyer must belong to a Buyer organization, the compliance officer is platform-wide, and the
credit and finance users must belong to the project's organization to sell its credits and pay its farmers.

🔎 **1.3** Log in as `labtec` and open http://localhost:4200/mrv → "You don't have access to this page".

---

## Stage 2 — Catalog
**LOGIN `leelak`** · **GO TO:** Projects → **Standards & activities**

| Card | Field | Enter |
|---|---|---|
| Standard | Code / Name | `VCS` / `Verified Carbon Standard` |
| | Programme owner / Type | `Verra` / Voluntary |
| Activity | Code / Name | `IALM` / `Improved agricultural land management` |
| | Offered under | tick **Verified Carbon Standard** |

**CLICK:** Add standard → Add activity. **YOU SHOULD SEE:** "Offered under: Verified Carbon Standard" on IALM.

---

## Stage 3 — Methodology VM0042 2.2 with its calculation module

### 3.1 · LOGIN `ms1` · FILL
**GO TO:** Methodologies

| Where | Field | Enter |
|---|---|---|
| Add a methodology | Code | **`VM0042`** (exactly) |
| | Name | `Improved Agricultural Land Management` |
| | Standard / Activities | Verified Carbon Standard / Improved agricultural land management |
| New version | New version label | **`2.2`** (exactly) → **New draft version** → **Open** |
| Version details | Effective from | `21-10-2025` |
| | Source | `Verra VM0042 v2.2` → **Save details** |
| Tab **calculation** | Calculation module | **VM0042 v2.2 - SOC measure & remeasure (QA2) + default-factor emissions (QA3) · v1.0.0** → **Use this module** → **Use module** |
| Tab **applicability** | Rule 1 | Code `A1` · Title `Standard is VCS` · Category Standard · Fact key `standard_code` · Operator EQUALS · Expected value `"VCS"` (with quotes) · If it fails Not applicable → **Add rule** |
| | Rule 2 | Code `A2` · Title `Activity is IALM` · Category Activity · Fact key `activity_code` · EQUALS · `"IALM"` · Not applicable → **Add rule** |

**CLICK:** **Submit for approval**.

**YOU SHOULD SEE:** header badge **Module: VM0042-V2.2-QA2-QA3**; 8 calculation rules `V42-BSL` … `V42-NET`; 13 monitoring rules (`V42_OC` g/kg,
`V42_SOIL_MASS` g, fertiliser, fuel, lime, burning, irrigation, `V42_NPR`); status **In review**.

⚠ **Choose the module before submitting.** An approved version can never change its module (our first run had to be repaired in the database).

🔎 **3.2** ms1 clicks **Approve** → refused (the author cannot approve).

### 3.3 · LOGIN `ms2` · APPROVE
Open the version → **Approve**. **YOU SHOULD SEE:** **Approved**; "Calculation: Not production ready" (normal outside production).

---

## Stage 4 — Farmer

### 4.1 · LOGIN `pm` · FILL — register and submit KYC
**GO TO:** Farmers → **Register farmer**: Managing organization `varsapradaya_developer` · Full name `Ramesh Patil` · Gender MALE · Preferred
language `mr` · Primary phone `+91 98765 43210` · Village `Ozar` · District `Nashik` · State `Maharashtra` · Country `IN` → **Create farmer** → header **Register**.

Tab **KYC**: ID type National ID · ID number `1234 5678 9012` · Attach ID document (any PDF) → **Submit for review**.

**YOU SHOULD SEE:** **KYC pending**, ID shown as `••••9012`.

🔎 **4.2** pm on the KYC tab → "You submitted this KYC, so another reviewer must decide".

### 4.3 · LOGIN `qatester1` · VERIFY
Farmers → Ramesh Patil → KYC → Review notes `ID checked` → **Verify KYC**. **YOU SHOULD SEE:** **KYC verified**.

### 4.4 · LOGIN `pm` · FILL — consent, activation, agreement
| Tab | Enter | Click |
|---|---|---|
| Consents | keep defaults (Personal data processing v1 · `DATA_PROCESSING-v1` · Paper signed) | **Record consent** |
| Header | — | **Activate** |
| Agreements | Type `PROGRAM_PARTICIPATION` · Template version `v1` · Effective from `01-11-2025` | **Create agreement** → **Upload signed copy** (PDF) |

**YOU SHOULD SEE:** farmer **Active**; agreement **Signed** — note its code `AGR-2026-…` (used in Stage 18).

⚠ The farmer must be **Active**, not just KYC verified, or the farm cannot be added to the project.

---

## Stage 5 — Farms: 1 project farm + 3 control farms

VM0042 compares the project farm with **3 control sites**: farms with the same soil and rainfall that **keep the old practice** and are

**not** part of the project. For the test all four farms belong to Ramesh Patil.

### 5.1 · LOGIN `pm` · FILL — four farms
**GO TO:** Farmers → Ramesh Patil → tab **Farms** → **Add farm**, once per farm. For each:
1. Farm name (table) · Land tenure Owned · Declared area (table) · Country `IN` → **Create farm and draw boundary**.
2. **Boundary** tab → paste the 4 corners into **Paste several corners** (**one corner per line**) → **Add these corners** → **Check boundary** → **Save as new boundary version**.
3. **Documents** tab → Category Land record · Title `7/12 extract <farm name>` · any PDF → **Upload**.
4. **Ownership** tab → Owner type Farmer · Relationship Owner · Share % `100` · Title / survey reference `Survey 45/2` · Valid from `01-01-2020` · Evidence document (pre-selected) → **Record ownership**.
5. Header → **Submit for review**.

| Farm name | Declared area | Corners (latitude, longitude) — one per line | Measured |
|---|---|---|---|
| `North block` (project) | `100` | `20.1000, 73.7000` / `20.1000, 73.7096` / `20.1090, 73.7096` / `20.1090, 73.7000` | ≈ 100 ha |
| `Control C1` | `4` | `20.1000, 73.7200` / `20.1000, 73.7219` / `20.1018, 73.7219` / `20.1018, 73.7200` | ≈ 4 ha |
| `Control C2` | `4` | `20.1000, 73.7300` / `20.1000, 73.7319` / `20.1018, 73.7319` / `20.1018, 73.7300` | ≈ 4 ha |
| `Control C3` | `4` | `20.1000, 73.7400` / `20.1000, 73.7419` / `20.1018, 73.7419` / `20.1018, 73.7400` | ≈ 4 ha |

🔎 **5.2** pm looks for **Verify farm** on North block → not available to the submitter.

### 5.3 · LOGIN `gis` · VERIFY — all four farms
For each farm: tab **Ownership** → **Verify** (reason `Land record checked`) → header **Start GIS review** → **Verify farm**.

**YOU SHOULD SEE:** four farms **Verified**.

---

## Stage 6 — Project and eligibility

### 6.1 · LOGIN `pm` · FILL
**GO TO:** Projects → **New project**

| Tab / form | Field | Enter |
|---|---|---|
| New project | Organization / Name / Type | varsapradaya_developer / `Nashik VM0042 pilot` / Agricultural land management |
| | Country / Region / **Planned start** | `IN` / `Nashik` / **`01-11-2025`** |
| Header | Start data collection | reason |
| Farms | Farm / Participation from / Rights holder | **North block only** / `01-11-2025` / Farmer |
| | Agreement / evidence reference / Share % | `Carbon rights clause of AGR-2026-…` / `100` |
| Standard & activity | Standard / Activity | Verified Carbon Standard → Select / Improved agricultural land management → Select |
| Crediting & baseline | Crediting period | `01-11-2025` – `31-10-2035` → **Record period** |
| | Baseline From / To / Practices / Data sources | `01-11-2020` / `31-10-2025` / `Full tillage, residue burning, high N` / `Farmer interview` → **Record baseline** |

**CLICK:** header **Submit for eligibility review**. **YOU SHOULD SEE:** **Eligibility review**.

⚠ **Planned start 01-11-2025** must be on or after the methodology's effective date (21-10-2025), or VM0042 is not offered in Stage 7.

⚠ **Never add the control farms to the project.**

### 6.2 · LOGIN `gis` · VERIFY — tab **Boundary** → **Accept boundary**.
### 6.3 · LOGIN `qatester1` · VERIFY + APPROVE — tab **Carbon rights** → **Verify** (`Agreement checked`); header **Approve eligibility** → **Standard selected**.
🔎 **6.4** pm looks for **Approve eligibility** → not shown to the submitter.
### 6.5 · LOGIN `pm` · FILL — header **Confirm activity** → **Activity selected**.

---

## Stage 7 — Lock the methodology

### 7.1 · LOGIN `ms1` · FILL
Projects → Nashik VM0042 pilot → tab **Methodology** → **Evaluate candidates** → expand **VM0042 2.2** (Applicable, A1 ✔ A2 ✔) → **Recommend** → reason `Applicable; module VM0042-V2.2-QA2-QA3`.

🔎 **7.2** ms1 tries **Confirm & lock** → not allowed.

### 7.3 · LOGIN `pm` · APPROVE
Expand → **Confirm & lock**. **YOU SHOULD SEE:** status **Methodology confirmed**; **MRV workspace** button.

---

## Stage 8 — MRV plan, periods, strata and control sites
All steps in **MRV → Nashik VM0042 pilot**. A yellow **CONFIGURATION_REQUIRED** banner about sampling depth is normal (VM0042's module
doesn't fix the depth; the project sets 0–50 cm).

### 8.1 · LOGIN `mrv` · FILL — MRV plan
Tab **MRV plans** → **Create MRV plan**: Monitoring frequency `Annual sampling` · Quantification approach **empty** · Monitoring start

**`01-11-2025`** · end `31-10-2035` · Required evidence `Field photos, GPS, lab reports` → **Create plan (draft)** → **Submit for approval**.

**YOU SHOULD SEE:** 13 `V42_…` measurements listed; **Submitted**.

⚠ The plan window must **start on 01-11-2025**, otherwise Period 0 is refused (`OUTSIDE_PLAN_WINDOW`).

### 8.2 · LOGIN `qatester1` · APPROVE — open the plan → **Approve** (the dialog notes the depth gap — expected).

### 8.3 · LOGIN `mrv` · FILL — two monitoring periods
Tab **Monitoring periods** → **Create period** twice:

| Name | Purpose | Start | End |
|---|---|---|---|
| `Period 0 baseline` | Baseline | `01-11-2025` | `31-05-2026` |
| `Period 1` | Monitoring | `01-06-2026` | `31-05-2027` |

On **both** rows: **Mark planned** → **Start period** → **Open data collection**.

**YOU SHOULD SEE:** both periods **Data collection**; project **Monitoring**.

### 8.4 · LOGIN `gis` · FILL — project stratum and 3 control sites
Tab **Stratification** → New. For **each** characteristic: choose it, type the value, click **+**. Add **all four** before creating.

| Toggle | Code / Name | Farms | Represents | Characteristics (all four) |
|---|---|---|---|---|
| Project stratum | `S1` / `North block` | North block | — | SOIL_TEXTURE `clay` · SOIL_GROUP `Vertisol` · CLIMATE `Tropical dry` · PRECIPITATION_MM `750` |
| Control site | `C1` / `Control C1` | Control C1 | S1 | same three + PRECIPITATION_MM `720` |
| Control site | `C2` / `Control C2` | Control C2 | S1 | same three + PRECIPITATION_MM `760` |
| Control site | `C3` / `Control C3` | Control C3 | S1 | same three + PRECIPITATION_MM `780` |

**YOU SHOULD SEE:** "Baseline control sites: **3 of at least 3** · Every stratum has a control site".

⚠ **Enter every characteristic before creating the stratum** — a draft stratum cannot be edited on screen. In our first run S1 had only
"Soil type" and had to be fixed through the API. "Soil type" is not used for the control-site check; texture, soil group, climate and rainfall are.

🔎 **8.5** gis looks for **Approve** on S1 → not available to the creator.

### 8.6 · LOGIN `sup` · APPROVE — **Approve** S1, C1, C2, C3.
The control sites are checked against S1 (same texture, soil group, climate; rainfall within 100 mm; within 250 km). **YOU SHOULD SEE:** all four **Approved**.

---

## Stage 9 — Laboratory engagement
### 9.1 · LOGIN `mrv` · FILL — tab **Samples & laboratory** → Laboratory `soiltestlab` · LABORATORY rules in scope: tick **both** `V42_OC` and `V42_SOIL_MASS` → **Propose engagement**.
### 9.2 · LOGIN `labmgr` · APPROVE — **Laboratory → Engagements** → **Accept**. **YOU SHOULD SEE:** engagement **Active**.

---

## Stage 10 — Period 0: baseline sampling and laboratory
The first sampling round, at the project start. Soil is sampled on the project farm and the 3 control farms and analysed by the lab.

⚠ In the MRV workspace set the **Monitoring period** picker (top right) to **Period 0 baseline** for every step of this stage.

### 10.1 · LOGIN `gis` · FILL — sampling design (one per period)
**GO TO:** MRV → Nashik VM0042 pilot → tab **Sampling design**

| Field | Enter |
|---|---|
| Code | `SOIL-P0` |
| Name | `Baseline soil sampling` |
| Sample count — S1 · C1 · C2 · C3 | `3` · `3` · `3` · `3` |
| Statistical design | Stratified random |
| Sampling method | `Soil auger, 4-core composite` |
| Depth top (cm) / Depth bottom (cm) | `0` / `50` |
| Target precision / Confidence level | empty |
| Min. distance between points (m) | `10` |
| Random seed | empty |

**CLICK:** **Create design (12 samples)**. **YOU SHOULD SEE:** the design in **Draft**.

⚠ One design per period: generating points for a second design in the same period cancels the first design's points.

### 10.2 · LOGIN `sup` · APPROVE — design
Tab **Sampling design** → **Approve design** → reason `Design checked`. **YOU SHOULD SEE:** design **Approved**. (🔎 gis cannot approve it.)

### 10.3 · LOGIN `gis` · FILL — sampling points
Tab **Sampling design** → **Generate sampling points**. **YOU SHOULD SEE:** 12 points — 3 inside North block, 3 inside each control farm.

### 10.4 · LOGIN `sup` · FILL — assign the points
Tab **Points & assignments** → **Select unassigned** → Field collector `colfield_test` · Planned date `20-05-2026` → **Assign 12 point(s)**.

### 10.5 · Give each point its key (write it down)
In **Points & assignments** look at the 12 point codes (SP-…) and the **Stratum** column. Within each stratum the **lowest** code is point 1, the next 2, the highest 3. Fill this worksheet — the key goes on the bags and tells the lab which values to enter:

| Key | Stratum | Point code (write it) |
|---|---|---|
| **S1-1** | S1 | SP-… |
| **S1-2** | S1 | SP-… |
| **S1-3** | S1 | SP-… |
| **C1-1** | C1 | SP-… |
| **C1-2** | C1 | SP-… |
| **C1-3** | C1 | SP-… |
| **C2-1** | C2 | SP-… |
| **C2-2** | C2 | SP-… |
| **C2-3** | C2 | SP-… |
| **C3-1** | C3 | SP-… |
| **C3-2** | C3 | SP-… |
| **C3-3** | C3 | SP-… |

### 10.6 · LOGIN `col` · FILL — field collection on all 12 points
**GO TO:** **Field work** → each point → **Start collection**. On every point:

| Field | Enter |
|---|---|
| Latitude / Longitude | the point's own coordinates ("Planned point …" at the top of the page) |
| GPS accuracy (m) | empty |
| **Collected at** | `20-05-2026 10:00` — must lie inside Period 0 baseline (01-11-2025 – 31-05-2026) and not in the future |
| Depth top (cm) / Depth bottom (cm) | `0` / `50` (pre-filled) |
| **Probe inside diameter (mm)** | **`21.5`** — same on every point |
| **Number of cores** | **`4`** — same on every point |
| Sample quantity / Unit | `2` / `kg` |
| Field observations / Deviation note | empty |
| Field checklist | tick all 4 boxes |
| Photo | **Take / add photo** → the JPG |

**CLICK:** **Save & submit**. **YOU SHOULD SEE:** "Submitted for review".

⚠ Today's date is outside Period 0 → "Cannot submit yet: a collection date within the monitoring period". Use 20-05-2026.

🔎 **10.6a** col tries to accept their own record → not allowed.

### 10.7 · LOGIN `sup` · VERIFY — accept the field records
Tab **Points & assignments** → section **Submitted field records** → **Accept** on each of the 12 (reason `Field record checked`). **YOU SHOULD SEE:** all 12 **Accepted**.

### 10.8 · LOGIN `col` · FILL — two depth samples per field record (24 samples)
**GO TO:** **Field work** → open each accepted record → section **Laboratory samples** → **Register & seal sample**. For each point register sample **A** (top layer) then sample **B** (bottom layer), then seal both. Quantity `1`, Unit `kg` on all.

| Key | Layer | Description | Container label | Depth top | Depth bottom | Seal number |
|---|---|---|---|---|---|---|
| S1-1 | A | `P0 S1-1 0-30` | `P0-S1-1-A` | `0` | `30` | `SEAL-P0-S1-1-A` |
| S1-1 | B | `P0 S1-1 30-50` | `P0-S1-1-B` | `30` | `50` | `SEAL-P0-S1-1-B` |
| S1-2 | A | `P0 S1-2 0-30` | `P0-S1-2-A` | `0` | `30` | `SEAL-P0-S1-2-A` |
| S1-2 | B | `P0 S1-2 30-50` | `P0-S1-2-B` | `30` | `50` | `SEAL-P0-S1-2-B` |
| S1-3 | A | `P0 S1-3 0-30` | `P0-S1-3-A` | `0` | `30` | `SEAL-P0-S1-3-A` |
| S1-3 | B | `P0 S1-3 30-50` | `P0-S1-3-B` | `30` | `50` | `SEAL-P0-S1-3-B` |
| C1-1 | A | `P0 C1-1 0-30` | `P0-C1-1-A` | `0` | `30` | `SEAL-P0-C1-1-A` |
| C1-1 | B | `P0 C1-1 30-50` | `P0-C1-1-B` | `30` | `50` | `SEAL-P0-C1-1-B` |
| C1-2 | A | `P0 C1-2 0-30` | `P0-C1-2-A` | `0` | `30` | `SEAL-P0-C1-2-A` |
| C1-2 | B | `P0 C1-2 30-50` | `P0-C1-2-B` | `30` | `50` | `SEAL-P0-C1-2-B` |
| C1-3 | A | `P0 C1-3 0-30` | `P0-C1-3-A` | `0` | `30` | `SEAL-P0-C1-3-A` |
| C1-3 | B | `P0 C1-3 30-50` | `P0-C1-3-B` | `30` | `50` | `SEAL-P0-C1-3-B` |
| C2-1 | A | `P0 C2-1 0-30` | `P0-C2-1-A` | `0` | `30` | `SEAL-P0-C2-1-A` |
| C2-1 | B | `P0 C2-1 30-50` | `P0-C2-1-B` | `30` | `50` | `SEAL-P0-C2-1-B` |
| C2-2 | A | `P0 C2-2 0-30` | `P0-C2-2-A` | `0` | `30` | `SEAL-P0-C2-2-A` |
| C2-2 | B | `P0 C2-2 30-50` | `P0-C2-2-B` | `30` | `50` | `SEAL-P0-C2-2-B` |
| C2-3 | A | `P0 C2-3 0-30` | `P0-C2-3-A` | `0` | `30` | `SEAL-P0-C2-3-A` |
| C2-3 | B | `P0 C2-3 30-50` | `P0-C2-3-B` | `30` | `50` | `SEAL-P0-C2-3-B` |
| C3-1 | A | `P0 C3-1 0-30` | `P0-C3-1-A` | `0` | `30` | `SEAL-P0-C3-1-A` |
| C3-1 | B | `P0 C3-1 30-50` | `P0-C3-1-B` | `30` | `50` | `SEAL-P0-C3-1-B` |
| C3-2 | A | `P0 C3-2 0-30` | `P0-C3-2-A` | `0` | `30` | `SEAL-P0-C3-2-A` |
| C3-2 | B | `P0 C3-2 30-50` | `P0-C3-2-B` | `30` | `50` | `SEAL-P0-C3-2-B` |
| C3-3 | A | `P0 C3-3 0-30` | `P0-C3-3-A` | `0` | `30` | `SEAL-P0-C3-3-A` |
| C3-3 | B | `P0 C3-3 30-50` | `P0-C3-3-B` | `30` | `50` | `SEAL-P0-C3-3-B` |

**CLICK:** **Register sample** (once per layer) → type the Seal number next to the sample → **Seal sample**.

**YOU SHOULD SEE:** on each record "Laboratory samples (2)": `0–30 cm · 2 test(s)` and `30–50 cm · 2 test(s)`, both **Sealed**.

⚠ Check the depth reads **30** (not 29.8). ⚠ After the second sample the form still shows 30 / 50 — **don't click Register a third time**. If a wrong sample was registered: **sup** → Samples & laboratory → the sample → **Void**, then register it again.

### 10.9 · LOGIN `sup` · FILL — ship to the laboratory
Tab **Samples & laboratory** → **Shipments**: Ship to laboratory `soiltestlab` · Carrier `Courier` → **Create shipment** → **Add sealed samples** (tick all 24) → **Add** → **Dispatch**. **YOU SHOULD SEE:** shipment **Dispatched**.

### 10.10 · LOGIN `labtec` · FILL — receive the shipment
**GO TO:** **Laboratory** → tab **Incoming** → the shipment card. On every row:

| Field | Enter |
|---|---|
| Accept | ticked |
| Seal observed | leave the pre-filled seal (it must equal the seal on the bag) |
| Condition | `intact` |

**CLICK:** **Record receipt**. **YOU SHOULD SEE:** samples **Lab received**.

### 10.11 · LOGIN `labtec` · FILL — accession numbers and lookup sheet
Tab **Samples**: each row shows SAMPLE, DESCRIPTION, DEPTH. In **Accession no.** type **`LAB-` + the sample's number** (SMP-2026-000031 → `LAB-000031`) → **Register**. Accession is one-way — check before clicking.

While doing it, copy each sample's code next to its description in the worksheet below; the Worklist shows only sample codes.

### 10.12 · LOGIN `labtec` · FILL — enter the 48 results
**GO TO:** tab **Worklist**. Each sample has two tests: **V42_OC** (organic carbon, unit **g/kg**) and **V42_SOIL_MASS** (soil mass, unit **g**). For each test click the test code (LT-…):

| Field on the test page | Enter |
|---|---|
| Method used (as performed) | `Dry combustion` (V42_OC) · `Oven-dried at 105 C, sieved < 2 mm` (V42_SOIL_MASS) → **Start test** |
| Result type | Numeric |
| Value | from the worksheet below |
| Unit | leave the pre-filled unit (`g/kg` or `g`) |
| Analysed at | leave the pre-filled date and time (today, after the receipt) |

**CLICK:** **Save result** → **PDF report: Choose File** (the upload starts when you pick the file) → **Submit for QA**. **YOU SHOULD SEE:** the result **Submitted**.

**Worksheet — Period 0 baseline laboratory values** (find the row by the sample's Description):

| Description | Sample code (write it) | V42_OC value (g/kg) | V42_SOIL_MASS value (g) |
|---|---|---|---|
| `P0 S1-1 0-30` | SMP-… | **12.0** | **280** |
| `P0 S1-1 30-50` | SMP-… | **7.0** | **200** |
| `P0 S1-2 0-30` | SMP-… | **11.0** | **290** |
| `P0 S1-2 30-50` | SMP-… | **6.5** | **210** |
| `P0 S1-3 0-30` | SMP-… | **11.5** | **285** |
| `P0 S1-3 30-50` | SMP-… | **6.8** | **205** |
| `P0 C1-1 0-30` | SMP-… | **11.5** | **285** |
| `P0 C1-1 30-50` | SMP-… | **6.8** | **205** |
| `P0 C1-2 0-30` | SMP-… | **11.7** | **286** |
| `P0 C1-2 30-50` | SMP-… | **6.6** | **204** |
| `P0 C1-3 0-30` | SMP-… | **11.6** | **284** |
| `P0 C1-3 30-50` | SMP-… | **6.7** | **206** |
| `P0 C2-1 0-30` | SMP-… | **11.5** | **285** |
| `P0 C2-1 30-50` | SMP-… | **6.8** | **205** |
| `P0 C2-2 0-30` | SMP-… | **11.7** | **286** |
| `P0 C2-2 30-50` | SMP-… | **6.6** | **204** |
| `P0 C2-3 0-30` | SMP-… | **11.6** | **284** |
| `P0 C2-3 30-50` | SMP-… | **6.7** | **206** |
| `P0 C3-1 0-30` | SMP-… | **11.5** | **285** |
| `P0 C3-1 30-50` | SMP-… | **6.8** | **205** |
| `P0 C3-2 0-30` | SMP-… | **11.7** | **286** |
| `P0 C3-2 30-50` | SMP-… | **6.6** | **204** |
| `P0 C3-3 0-30` | SMP-… | **11.6** | **284** |
| `P0 C3-3 30-50` | SMP-… | **6.7** | **206** |

⚠ Analysed at must be after the receipt time: a date before it makes lab QA fail. ⚠ Check every value against the worksheet before **Save result**.

🔎 **10.12a** labtec tries to approve their own result → refused.

### 10.13 · LOGIN `labmgr` · APPROVE — lab QA of the 48 results
**GO TO:** **Laboratory** → tab **QA** → each result → **Review**:

| Field on the QA page | Enter |
|---|---|
| — | **Start QA review** → 12 checks, all **PASS** |
| Decision | APPROVED |
| Notes | `Checked` |

**CLICK:** **Record decision**. **YOU SHOULD SEE:** result **Approved**; after all 48, the 24 samples show **Analysed**.

If a check shows FAIL (wrong date, unit or value): Decision **REJECTED** with the reason → labtec opens the test again and enters a corrected result (v2) → submit → labmgr approves v2.

---

## Stage 11 — Period 0 dataset

### 11.1 · LOGIN `mrv` · FILL — risk value and dataset (picker: **Period 0 baseline**)
Tab **Monitoring data** — one record:

| Field | Enter |
|---|---|
| Measurement | **V42_NPR · non_permanence_risk_rating (%)** (project level — the Farm box disappears) |
| Value | `12` |
| Observed on | **`20-05-2026`** (inside Period 0) |
| Phase | Monitoring |
| Source | Document |

**CLICK:** **Record value**. **YOU SHOULD SEE:** one row V42_NPR · 12 % · 20-05-2026.

Then tab **Datasets & QA** → Monitoring period **Period 0 baseline** → **Create dataset version** → **Open / QA** → **Submit for QA** (reason `Period 0 complete`).

⚠ An Observed on date outside Period 0 makes dataset QA fail on dates.

🔎 **11.2** mrv looks for **Record QA result** → not available to the submitter.

### 11.3 · LOGIN `qatester1` · VERIFY + APPROVE — Period 0 dataset
MRV → project → tab **Datasets & QA** → **Open / QA** on the Period 0 dataset → **Start QA review** → all checks PASS or WARN (WARN for the depth
configuration and "awaiting laboratory analysis" is normal) → QA result **PASS** → **Record QA result** → **Approve dataset**.

**YOU SHOULD SEE:** dataset and **Period 0 baseline Approved**.

⚠ After submitting a dataset, never press **Open data collection** on that period again.

---

## Stage 12 — Period 1: remeasurement and laboratory
The second sampling round, one year into the new practice — exactly the same steps as Stage 10, with Period 1 dates, keys and values.

⚠ In the MRV workspace set the **Monitoring period** picker (top right) to **Period 1** for every step of this stage.

### 12.1 · LOGIN `gis` · FILL — sampling design (one per period)
**GO TO:** MRV → Nashik VM0042 pilot → tab **Sampling design**

| Field | Enter |
|---|---|
| Code | `SOIL-P1` |
| Name | `Remeasurement` |
| Sample count — S1 · C1 · C2 · C3 | `3` · `3` · `3` · `3` |
| Statistical design | Stratified random |
| Sampling method | `Soil auger, 4-core composite` |
| Depth top (cm) / Depth bottom (cm) | `0` / `50` |
| Target precision / Confidence level | empty |
| Min. distance between points (m) | `10` |
| Random seed | empty |

**CLICK:** **Create design (12 samples)**. **YOU SHOULD SEE:** the design in **Draft**.

⚠ One design per period: generating points for a second design in the same period cancels the first design's points.

### 12.2 · LOGIN `sup` · APPROVE — design
Tab **Sampling design** → **Approve design** → reason `Design checked`. **YOU SHOULD SEE:** design **Approved**. (🔎 gis cannot approve it.)

### 12.3 · LOGIN `gis` · FILL — sampling points
Tab **Sampling design** → **Generate sampling points**. **YOU SHOULD SEE:** 12 points — 3 inside North block, 3 inside each control farm.

### 12.4 · LOGIN `sup` · FILL — assign the points
Tab **Points & assignments** → **Select unassigned** → Field collector `colfield_test` · Planned date today → **Assign 12 point(s)**.

### 12.5 · Give each point its key (write it down)
In **Points & assignments** look at the 12 point codes (SP-…) and the **Stratum** column. Within each stratum the **lowest** code is point 1, the next 2, the highest 3. Fill this worksheet — the key goes on the bags and tells the lab which values to enter:

| Key | Stratum | Point code (write it) |
|---|---|---|
| **S1-1** | S1 | SP-… |
| **S1-2** | S1 | SP-… |
| **S1-3** | S1 | SP-… |
| **C1-1** | C1 | SP-… |
| **C1-2** | C1 | SP-… |
| **C1-3** | C1 | SP-… |
| **C2-1** | C2 | SP-… |
| **C2-2** | C2 | SP-… |
| **C2-3** | C2 | SP-… |
| **C3-1** | C3 | SP-… |
| **C3-2** | C3 | SP-… |
| **C3-3** | C3 | SP-… |

### 12.6 · LOGIN `col` · FILL — field collection on all 12 points
**GO TO:** **Field work** → each point → **Start collection**. On every point:

| Field | Enter |
|---|---|
| Latitude / Longitude | the point's own coordinates ("Planned point …" at the top of the page) |
| GPS accuracy (m) | empty |
| **Collected at** | **today**, with a time that has already passed (e.g. `06-10-2026 10:00`) — must lie inside Period 1 (01-06-2026 – 31-05-2027) and not in the future |
| Depth top (cm) / Depth bottom (cm) | `0` / `50` (pre-filled) |
| **Probe inside diameter (mm)** | **`21.5`** — same on every point |
| **Number of cores** | **`4`** — same on every point |
| Sample quantity / Unit | `2` / `kg` |
| Field observations / Deviation note | empty |
| Field checklist | tick all 4 boxes |
| Photo | **Take / add photo** → the JPG |

**CLICK:** **Save & submit**. **YOU SHOULD SEE:** "Submitted for review".

### 12.7 · LOGIN `sup` · VERIFY — accept the field records
Tab **Points & assignments** → section **Submitted field records** → **Accept** on each of the 12 (reason `Field record checked`). **YOU SHOULD SEE:** all 12 **Accepted**.

### 12.8 · LOGIN `col` · FILL — two depth samples per field record (24 samples)
**GO TO:** **Field work** → open each accepted record → section **Laboratory samples** → **Register & seal sample**. For each point register sample **A** (top layer) then sample **B** (bottom layer), then seal both. Quantity `1`, Unit `kg` on all.

| Key | Layer | Description | Container label | Depth top | Depth bottom | Seal number |
|---|---|---|---|---|---|---|
| S1-1 | A | `P1 S1-1 0-30` | `P1-S1-1-A` | `0` | `30` | `SEAL-P1-S1-1-A` |
| S1-1 | B | `P1 S1-1 30-50` | `P1-S1-1-B` | `30` | `50` | `SEAL-P1-S1-1-B` |
| S1-2 | A | `P1 S1-2 0-30` | `P1-S1-2-A` | `0` | `30` | `SEAL-P1-S1-2-A` |
| S1-2 | B | `P1 S1-2 30-50` | `P1-S1-2-B` | `30` | `50` | `SEAL-P1-S1-2-B` |
| S1-3 | A | `P1 S1-3 0-30` | `P1-S1-3-A` | `0` | `30` | `SEAL-P1-S1-3-A` |
| S1-3 | B | `P1 S1-3 30-50` | `P1-S1-3-B` | `30` | `50` | `SEAL-P1-S1-3-B` |
| C1-1 | A | `P1 C1-1 0-30` | `P1-C1-1-A` | `0` | `30` | `SEAL-P1-C1-1-A` |
| C1-1 | B | `P1 C1-1 30-50` | `P1-C1-1-B` | `30` | `50` | `SEAL-P1-C1-1-B` |
| C1-2 | A | `P1 C1-2 0-30` | `P1-C1-2-A` | `0` | `30` | `SEAL-P1-C1-2-A` |
| C1-2 | B | `P1 C1-2 30-50` | `P1-C1-2-B` | `30` | `50` | `SEAL-P1-C1-2-B` |
| C1-3 | A | `P1 C1-3 0-30` | `P1-C1-3-A` | `0` | `30` | `SEAL-P1-C1-3-A` |
| C1-3 | B | `P1 C1-3 30-50` | `P1-C1-3-B` | `30` | `50` | `SEAL-P1-C1-3-B` |
| C2-1 | A | `P1 C2-1 0-30` | `P1-C2-1-A` | `0` | `30` | `SEAL-P1-C2-1-A` |
| C2-1 | B | `P1 C2-1 30-50` | `P1-C2-1-B` | `30` | `50` | `SEAL-P1-C2-1-B` |
| C2-2 | A | `P1 C2-2 0-30` | `P1-C2-2-A` | `0` | `30` | `SEAL-P1-C2-2-A` |
| C2-2 | B | `P1 C2-2 30-50` | `P1-C2-2-B` | `30` | `50` | `SEAL-P1-C2-2-B` |
| C2-3 | A | `P1 C2-3 0-30` | `P1-C2-3-A` | `0` | `30` | `SEAL-P1-C2-3-A` |
| C2-3 | B | `P1 C2-3 30-50` | `P1-C2-3-B` | `30` | `50` | `SEAL-P1-C2-3-B` |
| C3-1 | A | `P1 C3-1 0-30` | `P1-C3-1-A` | `0` | `30` | `SEAL-P1-C3-1-A` |
| C3-1 | B | `P1 C3-1 30-50` | `P1-C3-1-B` | `30` | `50` | `SEAL-P1-C3-1-B` |
| C3-2 | A | `P1 C3-2 0-30` | `P1-C3-2-A` | `0` | `30` | `SEAL-P1-C3-2-A` |
| C3-2 | B | `P1 C3-2 30-50` | `P1-C3-2-B` | `30` | `50` | `SEAL-P1-C3-2-B` |
| C3-3 | A | `P1 C3-3 0-30` | `P1-C3-3-A` | `0` | `30` | `SEAL-P1-C3-3-A` |
| C3-3 | B | `P1 C3-3 30-50` | `P1-C3-3-B` | `30` | `50` | `SEAL-P1-C3-3-B` |

**CLICK:** **Register sample** (once per layer) → type the Seal number next to the sample → **Seal sample**.

**YOU SHOULD SEE:** on each record "Laboratory samples (2)": `0–30 cm · 2 test(s)` and `30–50 cm · 2 test(s)`, both **Sealed**.

⚠ Check the depth reads **30** (not 29.8). ⚠ After the second sample the form still shows 30 / 50 — **don't click Register a third time**. If a wrong sample was registered: **sup** → Samples & laboratory → the sample → **Void**, then register it again.

### 12.9 · LOGIN `sup` · FILL — ship to the laboratory
Tab **Samples & laboratory** → **Shipments**: Ship to laboratory `soiltestlab` · Carrier `Courier` → **Create shipment** → **Add sealed samples** (tick all 24) → **Add** → **Dispatch**. **YOU SHOULD SEE:** shipment **Dispatched**.

### 12.10 · LOGIN `labtec` · FILL — receive the shipment
**GO TO:** **Laboratory** → tab **Incoming** → the shipment card. On every row:

| Field | Enter |
|---|---|
| Accept | ticked |
| Seal observed | leave the pre-filled seal (it must equal the seal on the bag) |
| Condition | `intact` |

**CLICK:** **Record receipt**. **YOU SHOULD SEE:** samples **Lab received**.

### 12.11 · LOGIN `labtec` · FILL — accession numbers and lookup sheet
Tab **Samples**: each row shows SAMPLE, DESCRIPTION, DEPTH. In **Accession no.** type **`LAB-` + the sample's number** (SMP-2026-000031 → `LAB-000031`) → **Register**. Accession is one-way — check before clicking.

While doing it, copy each sample's code next to its description in the worksheet below; the Worklist shows only sample codes.

### 12.12 · LOGIN `labtec` · FILL — enter the 48 results
**GO TO:** tab **Worklist**. Each sample has two tests: **V42_OC** (organic carbon, unit **g/kg**) and **V42_SOIL_MASS** (soil mass, unit **g**). For each test click the test code (LT-…):

| Field on the test page | Enter |
|---|---|
| Method used (as performed) | `Dry combustion` (V42_OC) · `Oven-dried at 105 C, sieved < 2 mm` (V42_SOIL_MASS) → **Start test** |
| Result type | Numeric |
| Value | from the worksheet below |
| Unit | leave the pre-filled unit (`g/kg` or `g`) |
| Analysed at | leave the pre-filled date and time (today, after the receipt) |

**CLICK:** **Save result** → **PDF report: Choose File** (the upload starts when you pick the file) → **Submit for QA**. **YOU SHOULD SEE:** the result **Submitted**.

**Worksheet — Period 1 laboratory values** (find the row by the sample's Description):

| Description | Sample code (write it) | V42_OC value (g/kg) | V42_SOIL_MASS value (g) |
|---|---|---|---|
| `P1 S1-1 0-30` | SMP-… | **13.5** | **282** |
| `P1 S1-1 30-50` | SMP-… | **7.4** | **201** |
| `P1 S1-2 0-30` | SMP-… | **12.6** | **288** |
| `P1 S1-2 30-50` | SMP-… | **6.9** | **209** |
| `P1 S1-3 0-30` | SMP-… | **13.0** | **284** |
| `P1 S1-3 30-50` | SMP-… | **7.2** | **204** |
| `P1 C1-1 0-30` | SMP-… | **11.4** | **285** |
| `P1 C1-1 30-50` | SMP-… | **6.8** | **205** |
| `P1 C1-2 0-30` | SMP-… | **11.6** | **287** |
| `P1 C1-2 30-50` | SMP-… | **6.5** | **203** |
| `P1 C1-3 0-30` | SMP-… | **11.5** | **285** |
| `P1 C1-3 30-50` | SMP-… | **6.7** | **205** |
| `P1 C2-1 0-30` | SMP-… | **11.4** | **285** |
| `P1 C2-1 30-50` | SMP-… | **6.8** | **205** |
| `P1 C2-2 0-30` | SMP-… | **11.6** | **287** |
| `P1 C2-2 30-50` | SMP-… | **6.5** | **203** |
| `P1 C2-3 0-30` | SMP-… | **11.5** | **285** |
| `P1 C2-3 30-50` | SMP-… | **6.7** | **205** |
| `P1 C3-1 0-30` | SMP-… | **11.4** | **285** |
| `P1 C3-1 30-50` | SMP-… | **6.8** | **205** |
| `P1 C3-2 0-30` | SMP-… | **11.6** | **287** |
| `P1 C3-2 30-50` | SMP-… | **6.5** | **203** |
| `P1 C3-3 0-30` | SMP-… | **11.5** | **285** |
| `P1 C3-3 30-50` | SMP-… | **6.7** | **205** |

⚠ Analysed at must be after the receipt time: a date before it makes lab QA fail. ⚠ Check every value against the worksheet before **Save result**.

### 12.13 · LOGIN `labmgr` · APPROVE — lab QA of the 48 results
**GO TO:** **Laboratory** → tab **QA** → each result → **Review**:

| Field on the QA page | Enter |
|---|---|
| — | **Start QA review** → 12 checks, all **PASS** |
| Decision | APPROVED |
| Notes | `Checked` |

**CLICK:** **Record decision**. **YOU SHOULD SEE:** result **Approved**; after all 48, the 24 samples show **Analysed**.

If a check shows FAIL (wrong date, unit or value): Decision **REJECTED** with the reason → labtec opens the test again and enters a corrected result (v2) → submit → labmgr approves v2.

### 12.14 · LOGIN `mrv` · FILL — farm activity and risk (picker: **Period 1**)
Tab **Monitoring data**. Record these **13 rows**, one **Record value** each. Source **Document** on every row; Farm **North block** on every row
except V42_NPR (project level — no Farm box).

| # | Measurement | Farm | Phase | Observed on | Value |
|---|---|---|---|---|---|
| 1 | V42_FSN · synthetic_fertilizer_n (kg N) | North block | Baseline | `01-06-2023` | `1000` |
| 2 | V42_FSN | North block | Baseline | `01-06-2024` | `1100` |
| 3 | V42_FSN | North block | Baseline | `01-06-2025` | `1200` |
| 4 | V42_FSN | North block | Project | today | `800` |
| 5 | V42_DIESEL · diesel (L) | North block | Baseline | `01-06-2023` | `6000` |
| 6 | V42_DIESEL | North block | Baseline | `01-06-2024` | `6000` |
| 7 | V42_DIESEL | North block | Baseline | `01-06-2025` | `6000` |
| 8 | V42_DIESEL | North block | Project | today | `3500` |
| 9 | V42_BURN_RICE · residue_burned_rice (kg d.m.) | North block | Baseline | `01-06-2023` | `20000` |
| 10 | V42_BURN_RICE | North block | Baseline | `01-06-2024` | `21000` |
| 11 | V42_BURN_RICE | North block | Baseline | `01-06-2025` | `22000` |
| 12 | V42_BURN_RICE | North block | Project | today | `0` |
| 13 | V42_NPR · non_permanence_risk_rating (%) | — (project) | Monitoring | today | `12` |

**YOU SHOULD SEE:** 13 rows in the table under the form.

Baseline rows = the old practice in the 3 years before the project (old dates are allowed). Project rows = the new practice, dated inside
Period 1. Leave V42_FON, V42_GASOLINE, V42_LIMESTONE, V42_DOLOMITE, V42_BURN_WHEAT, V42_BURN_OTHER and V42_IRRIGATION empty.

⚠ These rows go in **Period 1** — the calculation reads farm activity only from the period being calculated.

---

## Stage 13 — Period 1 dataset and calculation

### 13.1 · LOGIN `mrv` · FILL — Period 1 dataset
**GO TO:** MRV → Nashik VM0042 pilot (picker **Period 1**) → tab **Datasets & QA** → Monitoring period **Period 1** → **Create dataset version** →

**Open / QA** → **Submit for QA** (reason `Period 1 complete`). **YOU SHOULD SEE:** dataset **Submitted**.

### 13.2 · LOGIN `qatester1` · VERIFY + APPROVE — Period 1 dataset
Tab **Datasets & QA** → **Open / QA** on the Period 1 dataset → **Start QA review** → all checks PASS or WARN → QA result **PASS** →

**Record QA result** (reason `Checks passed`) → **Approve dataset** (reason `Approved`). **YOU SHOULD SEE:** **Period 1 Approved**.

### 13.3 · LOGIN `analyst` · FILL — calculation
**GO TO:** **Calculations** → Project `Nashik VM0042 pilot` · Monitoring period **Period 1**.

**YOU SHOULD SEE:** readiness with no red blocker, only "NOT_PRODUCTION_READY: non-production use only".

**CLICK:** **New calculation run** → open the run → **Check readiness & freeze inputs** → **Execute** → **Submit for QA**.

You select only Period 1 — the platform takes **Period 0** automatically as the earlier sampling round (see Part C).

**Expected results** (Results tab, ≈ 100 ha project farm):

| Output | Meaning | Expected |
|---|---|---|
| REF_MASS_S1 | Reference soil mass to 30 cm (control sites, Period 0) | ≈ 1,923 t/ha |
| SOC_PRO_PREV_S1 → SOC_PRO_CURR_S1 | Project soil carbon, Period 0 → 1 | ≈ 22.51 → 25.56 t C/ha |
| SOC_BAS_PREV_S1 → SOC_BAS_CURR_S1 | Control-site soil carbon, Period 0 → 1 | ≈ 22.75 → 22.57 t C/ha |
| DCO2_SOIL_WP / DCO2_SOIL_BSL | Soil CO₂ change, project / controls | ≈ +1,122 / −69 t CO₂e |
| ER_FUEL · ER_N2O_FERT · ER_CH4_BB · ER_N2O_BB | Emission reductions | ≈ 7.22 · 0.69 · 1.27 · 0.31 t CO₂e |
| UNC_PCT | Sampling uncertainty deduction | ≈ 10.19 % |
| BUFFER_CR / BUFFER_ER | Non-permanence buffer (12 %) | ≈ 121 / 7.5 t CO₂e |
| **VCU_TOTAL** | **Credits (whole tonnes, rounded down)** | **≈ 950** — write it down |

🔎 **13.4** analyst looks for **Approve** → not available to the run's creator.

### 13.5 · LOGIN `qatester1` · VERIFY + APPROVE
Run page → tab **QA** → **Start calculation QA** → Result `PASS` · Notes `Inputs and outputs checked` → **Record QA** → header **Approve**.

**YOU SHOULD SEE:** run **Approved**; project **Calculated**.

---

## Stage 14 — Internal readiness and VVB verification

### 14.1 · LOGIN `qatester1` · FILL — run page → tab **Findings** → Category Clarification · Blocking ticked · Title `Lab method` · Description `Confirm the OC method and sieving for all results` → **Raise finding**.
### 14.2 · LOGIN `analyst` · FILL — Response `Dry combustion; fine earth < 2 mm, oven-dried at 105 C` → **Respond**. 🔎 **Resolve** is not shown to you.
### 14.3 · LOGIN `qatester1` · VERIFY — **Resolve** → reason `Accepted`.
### 14.4 · LOGIN `analyst` · FILL — run page → **Generate report** → **Verify** ("Hashes verify"); then **Calculations** → Period 1 → **Verification readiness** → **Prepare readiness** → **Submit**.
⚠ Resolve findings **before** generating the report; any later finding change makes it stale (`REPORT_STALE`).
### 14.5 · LOGIN `qatester1` · APPROVE — **Approve (READY)** → reason `Internal checks complete`.
### 14.6 · LOGIN `pm` · FILL — MRV → project → tab **Verification** (Period 1) → VVB / ACVA organization `verify_co` · Notes `Verification of Period 1` → **Propose**.
### 14.7 · LOGIN `vvb` · FILL — **VVB workspace** → the assignment → Conflict-of-interest declaration `No financial or personal interest in the project or its developer` → **Accept**.
### 14.8 · LOGIN `pm` · FILL — Verification tab → **Submit READY package**.
### 14.9 · LOGIN `vvb` · VERIFY + APPROVE — tabs **Package** / **Documents** (review) → tab **Decision**:

| Field | Enter |
|---|---|
| Outcome | Verified |
| VVB-stated verified quantity | the **VCU_TOTAL** from 13.3 (e.g. `950`) |
| Unit | `tCO2e` |
| Rationale | `Sampling, laboratory results and calculation checked against the package` |
| Verification report | any PDF |

**CLICK:** **Record decision**. **YOU SHOULD SEE:** assignment **Completed**; project **Verified**.

---

## Stage 15 — Registry and credit issuance
### 15.1 · LOGIN `pm` · FILL
**GO TO:** **Registry** → Project `Nashik VM0042 pilot` · Period `Period 1`. Work top to bottom:

| Form | Field | Enter | Click |
|---|---|---|---|
| Registry account | Registry / Account ID / Label | Verra Registry (test) / `VCS-ACC-001` / `Verra account` | |
| | Registry credit unit / = 1 verified unit | **`VCU`** / **`tCO2e`** | **Record account** |
| Registration | Account for registration | Verra account | **Start registration record** |
| | Registry project ID / Registered on / PDF | `VCS-PRJ-001` / today / any PDF | **Record registered** |
| Submission | Registry account | Verra account | **Prepare registry submission** → **Freeze snapshot** |
| | Submission reference / receipt PDF | `VCS-SUB-001` / any PDF | **Record submitted** |
| | Outcome / response PDF | Accepted / any PDF | **Record response** |
| Issuance | Issuance ID / date / Unit / statement PDF | `VCS-ISS-001` / today / **`VCU`** / any PDF | |
| | Batch: Vintage / Whole credits | `2026` / the VCU_TOTAL (e.g. `950`) | |
| | Batch: Serial start / end | `VCS-2026-000001` / `VCS-2026-000950` | **Record issuance** |

⚠ Units are exact text: `tCO2e` must match the VVB unit, `VCU` must match the account's credit unit.

🔎 **15.2** Record issuance with VCU_TOTAL + 1 credits → refused `QUANTITY_EXCEEDS_VERIFIED`.

🔎 **15.3** pm looks for **Confirm** → not shown to the recorder.

### 15.4 · LOGIN `qatester1` · APPROVE — **Confirm (second person)** → `Matches registry statement`.
**YOU SHOULD SEE:** issuance **Confirmed**; batch **Issued**; project **Issued**; batch listed under **Issued credits**.

---

## Stage 16 — Credit ledger
Of 950 credits: 10 retired by the developer, 10 moved to the buyer (who retires 5), 930 kept for sale.

| # | LOGIN | GO TO / fields | Click | YOU SHOULD SEE |
|---|---|---|---|---|
| 16.1 | credits | **Credit ledger** → the batch | **Open in ledger** → **Request opening** | Opening Requested (🔎 Confirm not shown) |
| 16.2 | qatester1 | same batch | **Confirm opening** | 950 Available, owner varsapradaya_developer |
| 16.3 | credits | batch → **Details** → Request retirement: Owner varsapradaya_developer · Quantity `10` · Beneficiary `Varsapradaya Developer` · Reason `Test retirement` | **Request retirement** | 10 Retirement pending |
| 16.4 | qatester1 | Details → Retirements: reference `VCS-RET-001` · date today · certificate PDF | **Record retirement** | 10 **Retired** |
| 16.5 | credits | Details → Request transfer: Kind Internal · Sender varsapradaya_developer · Recipient **buyer** · Quantity `10` · Purpose `Test transfer` | **Request transfer** | 10 Transfer pending |
| 16.6 | qatester1 | Details → Transfers | **Complete** | buyer owns 10 |
| 16.7 | buyer | **My credits** → AVAILABLE row → Request retirement: Quantity `5` · Beneficiary `Buyer Co` · Reason `Offsetting 2026 travel` | submit | request listed |
| 16.8 | qatester1 | Credit ledger → batch → Details → Retirements: reference `VCS-RET-002` · date · certificate PDF | **Record retirement** | 5 **Retired**; buyer keeps 5 |

---

## Stage 17 — Marketplace
Sale: **20 credits × ₹500 = ₹10,000**.

| # | LOGIN | GO TO / fields | Click | YOU SHOULD SEE |
|---|---|---|---|---|
| 17.1 | buyer | **Buyer profile**: Legal name `Buyer Co Pvt Ltd` · Country `IN` · Contact name `Asha Rao` · Contact email `buyer@yopmail.com` | **Save** → KYC PDF → **Upload** → **Submit for KYC review** | KYC submitted |
| 17.2 | compliance | **KYC review** → Buyer Co Pvt Ltd | **Verify** (`Documents checked`) | KYC verified |
| 17.3 | credits | **Listings → New listing**: the batch · Title `Nashik VM0042 VCUs 2026` · Listed quantity `100` · Price per credit `500.00` · Currency `INR` · Min / Max order `1` / `50` · Payment window `48` | **Create draft** → **Submit** | Pending approval (🔎 Approve hidden for you) |
| 17.4 | fin1 | **Listings** | **Approve** (`Price approved`) | listing **Active** |
| 17.5 | buyer | **Marketplace** → listing **Details** → Quantity `20` → **Add to order** · Delivery Ledger transfer | **Place order** | order Placed, INR 10,000.00 |
| 17.6 | buyer | **Orders** → Open → Payment reference `UTR-0001` · PDF | **Record payment** | Pending confirmation (🔎 no Confirm for you) |
| 17.7 | fin1 | **Payments** | **Confirm receipt** (`Funds received`) | order Transfer pending |
| 17.8 | qatester1 | **Credit ledger** → batch → Details → Transfers row "marketplace order ORD-…" | **Complete** | order **Completed**; buyer's My credits +20 |

⚠ The QA officer has no Orders page — delivery is completed on the **Credit ledger**.

---

## Stage 18 — Revenue sharing, settlement and farmer payout
Farmer share 60 % of ₹10,000 = **₹6,000**. Three finance users: fin1 calculates, fin2 approves and reconciles, fin3 pays.
Every Finance page has a **Project** picker → `Nashik VM0042 pilot`.

| # | LOGIN | GO TO / fields | Click | YOU SHOULD SEE |
|---|---|---|---|---|
| 18.1 | pm | **Revenue & costs** | — | one revenue record INR 10,000 (automatic) |
| 18.2 | pm | **Revenue sharing** → Farmer share `60` · Rounding HALF_UP · Deduct costs unticked · Effective from `01-06-2026` · Source `Farmer agreement AGR-2026-… clause 7` | **Create draft version** → **Submit** | In review |
| 18.3 | fin1 | Revenue sharing | **Approve** | Approved (🔎 pm cannot approve) |
| 18.4 | pm | Revenue sharing → farm allocation: Period `Period 1` · Basis `Single participating farm` · North block `100` (Total 100 %) | **Create draft allocation** → **Submit** | In review |
| 18.5 | fin1 | same | **Approve** | Approved |
| 18.6 | pm | **Farmers** → Ramesh Patil → **Bank**: Holder `Ramesh Patil` · Bank `State Bank of India` · Branch `Nashik Main` · Routing `SBIN0001234` · Account `123456789012` | **Add bank account** | Pending verification |
| 18.7 | fin1 | same tab | **Verify** (`Cancelled cheque checked`) | Verified |
| 18.8 | fin1 | **Settlements**: Period 1 · `INR` · the approved version · the approved allocation | **Create run** → **Calculate** → **Verify (recompute from snapshot)** → **Submit** | Ramesh Patil **INR 6,000.00**; "Reproducible" |
| 18.9 | fin2 | Settlements → the run | **Approve** | run Approved (🔎 fin1 can't approve) |
| 18.10 | fin1 | Settlements → **Create payouts**; **Payouts** → **Submit** | | Pending approval |
| 18.11 | fin2 | **Payouts** | **Approve** | Approved, bank ••••9012 |
| 18.12 | fin3 | Payouts | **Execute** → **Record paid**: reference `NEFT-0001` · PDF → **Upload evidence and record PAID** | **Paid** (🔎 fin2 can't execute) |
| 18.13 | fin2 | Payouts → **Reconcile**: Statement reference `NEFT-0001` · amount `6000.00` · `INR` · date today · PDF | **Upload statement and reconcile** | **Reconciled**; settlement **Completed** |

**End of the test.** Final checks:
1. Project → **Status history**: Draft → Data collection → Eligibility review → Standard selected → Activity selected → Methodology review →
   Methodology confirmed → MRV planned → Monitoring → Calculated → Verification → Verified → Issued.
2. Administration → **Audit log**: every action with who, when and the reason.
3. Every 🔎 check was refused.

---

## Part C — How the credits are calculated
You choose **Period 1**; the platform automatically adds **Period 0** (the latest earlier period with an approved dataset). Three kinds of
"baseline" feed the result:

| Baseline | Source | Used for |
|---|---|---|
| Baseline sampling round | Period 0 lab results | Soil carbon at the start |
| Baseline scenario | Control sites C1–C3 (both periods) | What happens without the project |
| Baseline emissions | Baseline-phase records (2023–2025) in Period 1 | Emissions of the old practice |

1. **Reference soil mass** — control sites, Period 0: ≈ 1,923 t/ha to 30 cm. Carbon is always compared in this same mass of soil.
2. **Soil carbon** — each point = 2 layers × (OC × soil mass), converted to t/ha with probe diameter and cores; mean of 3 points:
   project 22.51 → 25.56 (**+3.06**), controls 22.75 → 22.57 (**−0.19**) t C/ha.
3. **CO₂ change** — change × 100 ha × 44/12: project **+1,122**, controls **−69** t CO₂e.
4. **Emission reductions** — old practice (mean of 2023–25) minus new practice: diesel 7.22 + fertiliser 0.69 + residue burning 1.58 = **9.49** t CO₂e
   (750 mm rainfall → dry-climate factors).
5. **Uncertainty** — spread of the 3 points per group → **10.19 %** deducted: project +1,007, controls −62.
6. **Removals** = project gain **1,007**; **reductions** = 9.49 + 62 avoided soil loss = **71.7** t CO₂e.
7. **Buffer** 12 % (V42_NPR): removals 1,007 − 121 = 886; reductions 71.7 − 7.5 = 64.
8. **VCU_TOTAL** = 886 + 64 = 950.7 → rounded down → **950**.

---

## Part D — Lessons from the first run
These problems happened in the first run on dmrv_db. This document's steps already avoid them.

| What happened | Effect | Built into this document |
|---|---|---|
| Methodology approved without choosing the module | Calculation blocked forever (`MODULE_NOT_SELECTED`) | 3.1: choose the module before submitting |
| GS402 Approach 1 module picked instead of Approach 3 | Calculation asked for lab data that didn't exist | VM0042 with real sampling, one module only |
| Dates typed month/day on a day-month browser | 06/01/2026 saved as 6 January | A.3: day-month-year everywhere |
| Stratum S1 created with only "Soil type" | Control-site check skipped; no screen to edit a draft | 8.4: all characteristics before creating |
| Collected at = today on a Period 0 point | "Collection date within the monitoring period" | 10.6: 20-05-2026 for Period 0 |
| One field record saved with 1 core | Soil mass per hectare four times too high for that point | 10.6: 4 cores on every point |
| Sample form had no depth fields | Only 0–50 cm samples → `DEPTH_INCREMENTS_REQUIRED` | **Fixed in the app**: Depth top / bottom on the form |
| Depth typed 29.8, extra 30–50 sample registered | Gap / overlap in the soil profile | 10.8: check 30, don't register a third sample |
| Accession numbers changed after registering | One-way step; needed a custody exception to reset | 10.11: decide the rule first |
| C: drive almost full | Every upload refused | A.2: 3 GB free |
| Analysed at 5 Apr 2026 (before receipt) | Lab QA fail; result rejected and re-entered | 10.12: analysed today, after receipt |
| Four lab value typos | Wrong soil carbon; rejected and re-entered | 10.12: check against the table |
| Farm activity recorded in the wrong period | Emission reductions would be 0 | 12.14: farm activity in Period 1 |

---

## Part E — Error codes
| Code / message | Stage | Fix |
|---|---|---|
| A button is missing | any | Wrong login for the step, or it's your own submission |
| `SEPARATION_OF_DUTIES` | any | Use the second login named in the step |
| `REQUIREMENTS_NOT_MET` | 4–6 | Read the "still needed" checklist on the page |
| VM0042 not a candidate | 7 | Planned start before 21-10-2025, activity not IALM, or version not approved |
| `METHODOLOGY_REQUIREMENT` | 8, 10 | Leave the plan's approach empty; design Stratified random, ≥ 3 per stratum |
| `OUTSIDE_PLAN_WINDOW` | 8.3 | Plan start must be 01-11-2025 or earlier |
| `CONTROL_FARM_IN_PROJECT` / `FARM_IS_CONTROL_SITE` | 6, 8 | Control farms must not be in the project |
| `CONTROL_SITE_NOT_SIMILAR` | 8.6 | Texture / soil group / climate differ, or rainfall more than 100 mm apart |
| "a collection date within the monitoring period" | 10.6 | Collected at outside the period, or in the future |
| `INVALID_DEPTH` | 10.8 | Sample depth outside the field record's 0–50 cm |
| "The document store is unavailable or refused the file" | any upload | Free disk space on C: (A.2) |
| `SAMPLE_NOT_LAB_REGISTERED` | 10.12 | Register the accession number first |
| "analysed before the laboratory received the sample" | 10.13 | Reject; labtec re-enters with today's date |
| `UNIT_MISMATCH` | 10.13 | Unit must be exactly `g/kg` or `g` |
| `PREVIOUS_PERIOD_REQUIRED` | 13 | Period 0 dataset not approved |
| `CONTROL_SITES_REQUIRED` / `CONTROL_SITE_REQUIRED` | 13 | Fewer than 3 sampled control sites, or none linked to S1 |
| `DEPTH_INCREMENTS_REQUIRED` | 13 | A field record has only one sample layer |
| `INVALID_SOIL_PROFILE` | 13 | Layers don't start at 0 or don't touch (0–30, 30–50) |
| `MISSING_REQUIRED_INPUT` · `CORE_DETAILS_MISSING` | 13 | Probe diameter / cores missing on a field record |
| `MISSING_REQUIRED_INPUT` (NPR) | 13 | V42_NPR not recorded in Period 1 |
| Emission reductions are 0 | 13 | Farm records in Period 0, or project rows dated outside Period 1 |
| `REPORT_STALE` | 14 | A finding changed after the report; regenerate it |
| `UNIT_EQUIVALENCE_NOT_CONFIGURED` / `QUANTITY_EXCEEDS_VERIFIED` | 15 | Units not exactly VCU / tCO2e, or more credits than verified |
| `BUYER_KYC_REQUIRED` | 17 | Buyer KYC not verified |
| `SHARING_RULE_NOT_EFFECTIVE` | 18 | Share version must start on or before 01-06-2026 |
| `BANK_ACCOUNT_NOT_VERIFIED` | 18 | fin1 verifies the bank account (18.7) |
