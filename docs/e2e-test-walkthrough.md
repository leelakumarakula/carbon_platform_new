# End-to-end test walkthrough (clean database, VM0042, your users)

Follow it top to bottom. Each step gives **who** signs in, **where** to click (exact screen labels), **what to enter**, and **✅ what you
should see**. 🔎 marks a test that must be **refused**; a refusal is a pass.

Database state at the start (reset 5 Oct 2026): only users, organizations, roles and the consent type "Personal data processing" exist.
Everything else is empty and numbering starts at `…-000001`.

**General tips**
- Use 2–3 browser windows (normal, private, second browser) to be several people at once.
- Every action asks for a reason: type 3 or more characters.
- Dates are entered as month/day/year.
- A red message shows a rule code (e.g. `SEPARATION_OF_DUTIES`) and the field at fault; detail pages have a "still needed" checklist.

---

## Stage 0: users you still need to create (as admin, `charana@vayublue.com`)

You have pm@, qa@, gis@, mrv@, sup@, col@, analyst@, meth1@, meth2@, labmgr@, labtech@, labqa@, vvb@. The later stages also need these.
Create them now or when you reach the stage: **Administration → Users → New user** (temporary password; each changes it at first sign-in).

| Email | Organization | Role | Needed from |
|---|---|---|---|
| registry@cc.example.com | Green Farms Developer (DEV) | Registry Manager | Stage 13 |
| credit@cc.example.com | DEV | Credit Manager | Stage 14 |
| fin1@cc.example.com | DEV | Finance Manager | Stage 15 (approves listing, payment, costs, sharing; reconciles) |
| fin2@cc.example.com | DEV | Finance Manager | Stage 16 (calculates the settlement) |
| fin3@cc.example.com | DEV | Finance Manager | Stage 16 (approves settlement and payout) |
| fin4@cc.example.com | DEV | Finance Manager | Stage 16 (executes the payout) |
| buyer@cc.example.com | Buyer Co (BUY) | Buyer | Stage 15 |
| comp@cc.example.com | none (platform staff) | Marketplace Compliance | Stage 15 |

And one organization: **Administration → Organizations**: Code `REG`, Name `Verra Registry (test)`, Type **Registry**, Country `IN`.

🔎 **0.1** Sign in as **labtech@** and open `http://localhost:4200/mrv` → "You don't have access to this page".
✅ **0.2** analyst@ and vvb@ still have temporary passwords: at their first sign-in they're forced to set a new one.

---

## Stage 1: Catalog (admin)

**Projects → Standards & activities**
1. Left card: Code `VCS` · Name `Verified Carbon Standard` · Programme owner `Verra` · Type `Voluntary` → **Add standard**.
2. Right card: Code `IALM` · Name `Improved agricultural land management` · Offered under ✔ `Verified Carbon Standard` → **Add activity**.

✅ The activity shows "Offered under: Verified Carbon Standard".

---

## Stage 2: Methodology VM0042 with its calculation module (meth1@ → meth2@)

**meth1@ · Projects → Methodologies → Add a methodology**
1. Code **`VM0042`** (exactly) · Name `Improved Agricultural Land Management` · Standard `Verified Carbon Standard` · Activities `Improved agricultural land management` → **Add methodology**.
2. New version label **`2.2`** (exactly) → **New draft version** → **Open**.
3. Version details: Effective from `10/21/2025` · Source `Verra VM0042 v2.2` → **Save details**.
4. **Calculation tab → Calculation module**: choose **VM0042 v2.2 - SOC measure & remeasure (QA2) + default-factor emissions (QA3)** → **Use this module**.
   ✅ The draft now has 8 calculation rules (`V42-BSL` … `V42-NET`), 13 monitoring rules (`V42_OC`, `V42_SOIL_MASS`, `V42_FSN`, `V42_DIESEL`, … `V42_NPR`) and a sampling rule.
5. **Applicability tab**, add 2 rules (click **Add rule** after each):

| Field | Rule 1 | Rule 2 |
|---|---|---|
| Code | `A1` | `A2` |
| Title | `Standard is VCS` | `Activity is IALM` |
| Category | Standard | Activity |
| Fact key | `standard_code` | `activity_code` |
| Operator | `EQUALS` | `EQUALS` |
| Expected value (JSON) | `"VCS"` (with quotes) | `"IALM"` (with quotes) |
| If it fails | Not applicable | Not applicable |

6. **Submit for approval** → status **In review**.

🔎 **2.1** meth1@ clicks **Approve** → refused (the author can't approve).

**meth2@** → open the version → **Approve**. ✅ **Approved**; rules read-only; "Calculation: Not production ready" (expected).

---

## Stage 3: Farmer (pm@ → qa@)

**pm@ · Field operations → Farmers → Register farmer**
1. Managing org `Green Farms Developer` · Full name `Ramesh Patil` · Primary phone `9876543210` · Village `Pimpalgaon` · District `Nashik` · State `Maharashtra` · Country `IN` → save. ✅ `FRM-2026-000001`, **Draft**.
2. Header → **Registered**.
   🔎 **3.1** Try **Activate** now → refused (KYC and consent missing).
3. **KYC** tab: upload any PDF/JPG · ID type · ID number `1234 5678 9012` → submit. ✅ **KYC pending**, number shown as `••••9012`.
   🔎 **3.2** pm@ tries to approve the KYC → refused / no button.
4. **qa@** → same farmer → **KYC** → approve. ✅ **KYC verified**.
5. **pm@ · Consents** tab: `Personal data processing` · version `v1` · Captured by `Paper signed` → **Record consent**.
6. Header → **Activate**. ✅ **Active**.

---

## Stage 4: Four farms: the project farm + 3 control farms (pm@ → gis@)

VM0042 needs **3 control sites**: farms with the same soil and rainfall that keep the **old** practice and do **not** join the project.
Create 4 farms for Ramesh Patil (in a real project the control farms belong to other farmers; for the test one farmer is fine).

| Farm name | Corners (lat, long), paste into **Boundary → Paste several corners** |
|---|---|
| `Pimpalgaon plot 1` (project) | `20.0063, 73.7910` · `20.0063, 73.7925` · `20.0050, 73.7925` · `20.0050, 73.7910` |
| `Control field 1` | `20.0063, 73.7940` · `20.0063, 73.7955` · `20.0050, 73.7955` · `20.0050, 73.7940` |
| `Control field 2` | `20.0063, 73.7970` · `20.0063, 73.7985` · `20.0050, 73.7985` · `20.0050, 73.7970` |
| `Control field 3` | `20.0063, 73.8000` · `20.0063, 73.8015` · `20.0050, 73.8015` · `20.0050, 73.8000` |

For **each** farm:
1. **pm@ · Farms → New farm**: Farmer `Ramesh Patil` · the farm name · Land tenure `Owned` · Declared area `2.2` · Village/District/State · Country `IN` → **Create farm and draw boundary**.
2. **Boundary** tab: paste the corners → **Add these corners** → **Check boundary** → **Save as new boundary version**. ✅ "Measured by SQL Server ≈ 2.27 ha".
3. **Documents** tab: upload a PDF, category `LAND_RECORD` (e.g. "7/12 extract").
4. **Ownership** tab: Owner type `Farmer` · Relationship `Owner` · Share % `100` · Title / survey reference `Survey 12/3` · Valid from `01/01/2020` · **Evidence document** = the land record (preselected) → save.
5. **History** tab (needed for a realistic record): Land use 2021–2025 `CROPLAND`; Practice 2025 `HISTORICAL` `Conventional tillage`; plot 1 only: 2026 `PROPOSED` `Reduced tillage`.
6. Header → **Submit**. 🔎 **4.1** (first farm only) pm@ looks for **Verify** → not available.
7. **gis@** → farm → **Ownership** → **Verify** the record → header **Start review** → **Overlaps** tab (should be empty) → header **Verify**. ✅ **Verified**; the land-records card shows "Verified".

---

## Stage 5: Project and eligibility (pm@ → gis@ → qa@)

1. **pm@ · Projects → New project**: Org `Green Farms Developer` · Name `Nashik soil carbon pilot` · Country `IN` · Region `Maharashtra` · Planned start **`11/01/2025`** → **Create project**. ✅ `PRJ-2026-000001`, **Draft**.
   (The start must be on or after the version's effective date 10/21/2025, otherwise VM0042 is not offered.)
2. Header → **Start data collection**.
3. **Farms** tab: Farm `Pimpalgaon plot 1` · Agreement / evidence reference `Participation agreement clause 4` → **Add farm**. Add **only plot 1**; the control farms must stay out of the project.
4. **Team** tab: add `qa@` as QA officer.
5. **Standard & activity**: Select `Verified Carbon Standard`, Select `Improved agricultural land management`.
6. **Crediting & baseline**: crediting period `11/01/2025`–`10/31/2035` → **Record period**; baseline `11/01/2020`–`10/31/2025`, `Conventional tillage, residue burning` → **Record baseline**.
7. Header → **Submit for eligibility review**.
8. **gis@ · Boundary** tab → **Accept boundary**.
9. **qa@ · Carbon rights** tab → **Verify**.
   🔎 **5.1** pm@ looks for **Approve eligibility** → not shown.
10. **qa@** header → **Approve eligibility** → **pm@** header → **Confirm activity**. ✅ **Activity selected**.

---

## Stage 6: Lock the methodology (pm@ → meth1@ → pm@)

1. **pm@ · Methodology** tab → **Evaluate candidates**. ✅ "VM0042 2.2: Applicable" (A1 ✔, A2 ✔); status **Methodology review**.
2. **meth1@** → project → **Methodology** → expand → **Recommend**.
   🔎 **6.1** meth1@ tries **Confirm & lock** → not allowed.
3. **pm@** → expand → **Confirm & lock**. ✅ Lock card "VM0042 2.2"; status **Methodology confirmed**.

---

## Stage 7: MRV plan, strata and control sites (mrv@ → qa@ → gis@)

Everything below is in **Projects → MRV → Nashik soil carbon pilot** (the MRV workspace).

1. **mrv@ · MRV plans → Create MRV plan**: frequency `Annual` · approach `MEASURE_AND_REMEASURE` · `11/01/2025`–`10/31/2035` · Required evidence `Field photos, GPS, lab report` → **Create plan (draft)** → **Submit for approval**.
   ✅ The 13 VM0042 measurements are added automatically (this is the module at work).
2. **qa@ · MRV plans** → open → **Approve**. ✅ project **MRV planned**.
3. **mrv@ · Stratification**, **Project stratum**: Code `S1` · Name `Black soil plot` · Farms ✔ `Pimpalgaon plot 1` · characteristics `SOIL_TEXTURE` = `Clay`, `SOIL_GROUP` = `Vertisol`, `PRECIPITATION_MM` = `750` → **Create stratum**.
4. Switch to **Control site**: `C1` · `Control site 1` · Farms ✔ `Control field 1` · **Represents (project strata)** ✔ `S1` · the same three characteristics → **Create control site**. Repeat for `C2` (Control field 2) and `C3` (Control field 3).
   🔎 **7.1** mrv@ tries **Approve** on S1 → refused.
5. **gis@ · Stratification** → **Approve** S1, C1, C2, C3. ✅ Checklist: "3 of at least 3" control sites; "Every stratum has a control site".

Why: S1's area (≈ 2.27 ha, measured by SQL Server) multiplies the result later; the control sites tell VM0042 what would have happened without the project; `PRECIPITATION_MM` decides wet or dry IPCC factors (750 mm = dry).

---

## Stage 8: Lab engagement (once) (mrv@ → labmgr@)

1. **mrv@ · Samples & laboratory** → **Laboratory engagements**: Laboratory `Soil Test Lab` · **LABORATORY rules in scope** ✔ `V42_OC` and ✔ `V42_SOIL_MASS` → **Propose engagement**.
2. **labmgr@ · Laboratory → Engagements** → **Accept**. ✅ **Active**.

---

## Stage 9: Period 0, the baseline sampling (soil at the project start)

### 9a. Period (mrv@)
**Monitoring periods**: Name `Period 0` · purpose `BASELINE` · `11/01/2025`–`05/31/2026` → **Create period** → **Mark planned** → **Start period** → **Open data collection**.
✅ Period **Data collection**; project **Monitoring**.

### 9b. Sampling design (mrv@ → gis@)
**Sampling design → New sampling design**: Code `SOIL-0` · Name `Baseline soil sampling` · **S1 = 3, C1 = 3, C2 = 3, C3 = 3** · Statistical design `Stratified random` · Sampling method `Soil auger` · Depth top `0` · Depth bottom `50` · Target precision `10` · Confidence level `90` · Min. distance `10` → **Create design (12 samples)**.
VM0042 refuses fewer than 3 per stratum or a design other than stratified random.
**gis@** → **Approve design**. **mrv@** → **Generate sampling points**. ✅ "Points generated (SQL Server validated)": 12 points, 3 inside each farm.

### 9c. Assign (sup@)
**Points & assignments** → **Select unassigned** → collector `col@` → **Assign 12 point(s)**.

### 9d. Field collection (col@, phone view: F12 → Ctrl+Shift+M)
**Field operations → Field work** → each point → **Start collection**:

| Field | Value |
|---|---|
| Latitude / Longitude | the planned point's coordinates (shown on the point) |
| GPS accuracy (m) | leave empty |
| Collected at | `05/20/2026` 10:00 (must be inside Period 0 and not in the future) |
| Depth top / bottom (cm) | `0` / `50` |
| Probe inside diameter (mm) * | `21.5` |
| Number of cores * | `4` |
| Checklist | tick every item |
| Photos | add one photo |

→ **Save & submit**.
🔎 **9.1** (first point) col@ tries to accept their own record → not allowed.
**sup@ · Points & assignments** → **Accept** each record.

### 9e. Two depth samples per field record (col@)
On each **accepted** record (**Field work → the point → View**) → **Laboratory samples** → **Register & seal sample**, twice:

| Sample | Description | Depth top (cm) | Depth bottom (cm) | Then |
|---|---|---|---|---|
| 1 | `Soil core 0-30 cm` | `0` | `30` | Seal number e.g. `S0-01` → **Seal sample** |
| 2 | `Soil core 30-50 cm` | `30` | `50` | Seal number e.g. `S0-02` → **Seal sample** |

✅ Each sample shows "0–30 cm" / "30–50 cm" and **2 test(s)** (organic carbon and soil mass, created automatically). 24 samples in total.
VM0042 needs ≥ 2 depth layers per point (equivalent-soil-mass comparison); one layer gives the blocker `DEPTH_INCREMENTS_REQUIRED`.

### 9f. Ship and receive (sup@ → labtech@)
1. **sup@ · Samples & laboratory → Shipments**: Ship to laboratory `Soil Test Lab` · Carrier `Courier` → **Create shipment** → **Add sealed samples** → **Add** → **Dispatch**.
2. **labtech@ · Laboratory → Incoming**: for each sample ✔ Accept · **Seal observed** = that sample's seal · Condition `Good` → **Record receipt**.
3. **Samples** tab: Accession no. `L0-01`, `L0-02`, … → **Register**.

### 9g. Lab results (labtech@ → labqa@)
**Laboratory → Worklist** → each test → Method used `Dry combustion` → **Start test** → Result type `Numeric` · Value · **Unit exactly `g/kg` (organic carbon) or `g` (soil mass)** · Analysed at = now → **Save result** → upload a **PDF report** → **Submit for QA**.

Values for Period 0 (enter them point by point; "point 1/2/3" = the 1st/2nd/3rd point of that farm, any order):

| Farm | Point | 0–30 cm: OC (g/kg) | 0–30 cm: mass (g) | 30–50 cm: OC (g/kg) | 30–50 cm: mass (g) |
|---|---|---|---|---|---|
| Plot 1 (S1) | 1 | 11.0 | 280 | 6.0 | 200 |
| Plot 1 (S1) | 2 | 10.5 | 290 | 6.2 | 205 |
| Plot 1 (S1) | 3 | 11.4 | 285 | 5.9 | 198 |
| Each control field (C1, C2, C3) | 1 | 11.2 | 284 | 6.1 | 202 |
| Each control field | 2 | 11.0 | 287 | 6.0 | 204 |
| Each control field | 3 | 11.5 | 283 | 6.2 | 200 |

🔎 **9.2** labtech@ tries to approve their own result → refused.
🔎 **9.3** (optional) submit one result without the PDF → refused `REPORT_REQUIRED`.
**labqa@ · Laboratory → QA** → **Review** → **Start QA review** (12 checks) → Decision `APPROVED` · Notes → **Record decision**. ✅ samples **Analysed**.
✅ **mrv@ · Samples & laboratory → Lineage** on a result: result → test → sample → field record → point → stratum → farm → project.

### 9h. Monitoring data and dataset (mrv@ → qa@)
1. **Monitoring data**: Measurement `V42_NPR` (project level, no farm) · Value `12` · Observed on `05/31/2026` · Phase `Monitoring` · Source `Document` → **Record value**.
2. **Datasets & QA**: Period 0 → **Create dataset version** → **Open / QA** → **Submit for QA**.
   🔎 **9.4** mrv@ tries **Approve dataset** → refused.
3. **qa@** → **Start QA review** (15 checks; a WARN `configuration` is OK) → QA result `PASS` → **Record QA result** → **Approve dataset**. ✅ Period 0 **Approved**.

⚠️ After the dataset is submitted, don't press **Open data collection** on Period 0 again (known issue).

---

## Stage 10: Period 1, the re-measurement (one year of the new practice)

Repeat Stage 9 with these differences:

| Step | Period 1 value |
|---|---|
| 9a | `Period 1` · purpose `MONITORING` · `06/01/2026`–`05/31/2027` |
| 9b | Code `SOIL-1`; again 3 / 3 / 3 / 3, depth 0–50 |
| 9d | Collected at = **today** (inside Period 1, not in the future) |
| 9e | Seals `S1-01`, `S1-02`, … |
| 9g | the values below |

| Farm | Point | 0–30 cm: OC | 0–30 cm: mass | 30–50 cm: OC | 30–50 cm: mass |
|---|---|---|---|---|---|
| Plot 1 (S1) | 1 | 12.6 | 282 | 6.6 | 201 |
| Plot 1 (S1) | 2 | 12.2 | 288 | 6.5 | 206 |
| Plot 1 (S1) | 3 | 12.9 | 284 | 6.4 | 199 |
| Each control field | 1 | 11.3 | 285 | 6.1 | 203 |
| Each control field | 2 | 11.0 | 286 | 6.0 | 204 |
| Each control field | 3 | 11.4 | 284 | 6.1 | 199 |

**Monitoring data for Period 1** (mrv@; farm-level items ask for the **Farm** = `Pimpalgaon plot 1`):

| Measurement | Farm | Value | Observed on | Phase | Meaning |
|---|---|---|---|---|---|
| `V42_FSN` | plot 1 | 120 | 07/01/2023 | Baseline | old practice, history year 1 (kg N) |
| `V42_FSN` | plot 1 | 110 | 07/01/2024 | Baseline | history year 2 |
| `V42_FSN` | plot 1 | 130 | 01/15/2025 | Baseline | history year 3 |
| `V42_FSN` | plot 1 | 90 | today | Project | new practice |
| `V42_DIESEL` | plot 1 | 60 | 07/01/2023 | Baseline | litres |
| `V42_DIESEL` | plot 1 | 60 | 07/01/2024 | Baseline | |
| `V42_DIESEL` | plot 1 | 35 | today | Project | |
| `V42_NPR` | (project) | 12 | today | Monitoring | Verra non-permanence risk rating, % |

Then create, submit and approve the **Period 1 dataset** (qa@).

---

## Stage 11: Calculation (analyst@ → qa@)

1. **analyst@ · Calculations**: Project `Nashik soil carbon pilot` · Monitoring period `Period 1`.
   ✅ Readiness: no blockers, only the warning "NOT_PRODUCTION_READY: non-production use only".
2. **New calculation run** → open the run → **Check readiness & freeze inputs** → **Execute**.
   ✅ **Results** tab: about 41 outputs, each with its VM0042 equation: `REF_MASS_…`, `SOC_BAS_PREV/CURR`, `SOC_PRO_PREV/CURR`, `E_BAS_*`, `E_PRO_*`, `ER_*`, `DCO2_SOIL_WP`, `DCO2_SOIL_BSL`, `UNC_PCT`, `BUFFER_CR`, … **`VCU_TOTAL`**.
   Expected: SOC project ≈ 21.44 → 24.62 t C/ha, control ≈ 21.99 → 22.01, uncertainty ≈ 9.8 %, **VCU_TOTAL ≈ 21** (the exact value depends on the area SQL Server measures; with 2.6153 ha it was 24).
3. **Submit for QA**.
4. **qa@ · QA** tab → **Start calculation QA** → **Findings** tab → Raise a finding: Category `Clarification` · ✔ Blocking · Title `Soil mass basis` · Description `Confirm the soil mass is oven-dry fine earth.` → **Raise finding**.
5. **analyst@** → Findings → Response `Confirmed: oven-dry fine earth < 2 mm.` → **Respond**.
   🔎 **11.1** analyst@ tries **Resolve** → refused.
6. **qa@** → **Resolve** → **QA** tab: Result `PASS` · Notes → **Record QA**.
   🔎 **11.2** analyst@ tries **Approve** → refused.
7. **qa@** → **Approve**. ✅ Run **Approved**.
8. **analyst@** → **Calculation report** → **Generate report** → **Verify** ✅ valid.
9. **analyst@ · Calculations** (Period 1) → **Verification readiness** → **Prepare readiness** → **Submit**. **qa@** → **Approve (READY)**.

👉 Send me a message at this point: I'll read your run and explain every number with your data.

---

## Stage 12: Verification by the VVB (pm@ → vvb@)

1. **pm@ · MRV workspace → Verification** tab (period `Period 1`): VVB / ACVA organization `Verify Co` → **Propose**.
2. **vvb@ · VVB workspace** → the assignment → Conflict-of-interest declaration `No conflict of interest with the project, developer or farmers.` → **Accept**. ✅ project **Verification**.
3. **pm@** → **Submit READY package**.
4. **vvb@** → **Package** and **Documents** tabs (no farmer names or GPS visible) → **Decision** tab: Outcome `Verified` · VVB-stated verified quantity = the `VCU_TOTAL` value · Unit `tCO2e` · Rationale · Verification report PDF → **Record decision**. ✅ project **Verified**.

(If vvb@ raises findings in the **Findings** tab, a **second** VVB reviewer must record the decision.)

---

## Stage 13: Registry (registry@ → qa@)

**registry@ · Registry** → Project `Nashik soil carbon pilot` · Monitoring period `Period 1`
1. **Record a registry account / registration**: Registry `REG` · Registry account ID `VCS-ACC-001` · Label `Verra account` · Registry credit unit `VCU` · = 1 verified unit `tCO2e` → **Record account**.
2. Account for registration → **Start registration record** → Registry project ID `VCS-1234` · Registered on (today) · Registry evidence PDF → **Record registered**.
3. **Registry submissions**: Registry account → **Prepare registry submission** → open it → attach a PDF ("Document sent to the registry") → **Attach** → **Freeze snapshot**.
4. Registry submission reference `SUB-001` · Registry receipt PDF → **Record submitted**.
5. Outcome `Accepted` · Registry response PDF → **Record response**.
6. **Record a registry issuance**: Registry issuance ID `ISS-001` · Issuance date (today) · Unit `VCU` · Issuance statement PDF · Vintage `2026` · Whole credits = VCU_TOTAL · Serial start `VCU-0001` · Serial end (e.g. `VCU-0021`) → **Record issuance**.
   🔎 **13.1** Try first with VCU_TOTAL + 1 → refused `QUANTITY_EXCEEDS_VERIFIED`.
   🔎 **13.2** registry@ clicks **Confirm (second person)** → refused.
7. **qa@** → **Confirm (second person)**. ✅ Issuance **Confirmed**; project **Issued**.

## Stage 14: Credit ledger (credit@ → qa@)
**credit@ · Credit ledger** → **Open in ledger** → **Request opening**. 🔎 credit@ tries **Confirm opening** → refused.
**qa@** → **Confirm opening**. ✅ All credits **Available**.

## Stage 15: Marketplace (buyer@, comp@, credit@, fin1@, qa@)
1. **buyer@ · Buyer profile**: Legal name `Buyer Co Pvt Ltd` · Country `IN` · contact → **Save** → KYC documents PDF → **Upload** → **Submit for KYC review**.
2. **comp@ · KYC review** → **Verify**.
3. **credit@ · Listings → New listing**: the batch · Title `Nashik VCUs 2026` · Listed quantity `20` (or less than your total) · Price per credit `850` · Currency `INR` · Payment window `24` → **Create draft** → **Submit**.
   🔎 credit@ tries **Approve** → refused. **fin1@** → **Approve**.
4. **buyer@ · Marketplace** → **Details** → Quantity `10` → **Add to order** → **Place order**. ✅ total INR 8,500.
5. **buyer@ · Orders** → **Open** → Payment reference `NEFT-001` + PDF → **Record payment**.
   🔎 buyer@ can't confirm it. **fin1@ · Payments** → **Confirm receipt**.
6. **qa@ · Orders** → **Complete delivery** (or **Credit ledger** → transfers → **Complete**). ✅ order **Completed**; buyer's **My credits** shows 10.
7. **buyer@ · My credits** → **Request retirement**: Quantity `4` · Beneficiary `Buyer Co Pvt Ltd` · reason `Voluntary claim FY2026`.
8. **qa@ · Credit ledger** → Retirements → Registry retirement reference `RET-001` · date · certificate PDF → **Record retirement**. ✅ buyer holds 6 available, 4 retired.

## Stage 16: Revenue sharing and farmer payout (pm@, fin1–fin4)
1. **pm@ · Revenue sharing**: Farmer share `60` · Rounding `HALF_UP` · ✔ Deduct approved project costs · Effective from `01/01/2026` · Source `Benefit-sharing agreement clause 4` → **Create draft version** → **Submit**; **fin1@** → **Approve**.
2. **pm@** → Farm allocation: Period 1 · Basis `Allocation by area` · plot 1 `100` % → **Create draft allocation** → **Submit**; **fin1@** → **Approve**.
3. **pm@ · Revenue & costs**: Category `FIELD_OPERATIONS` · `Soil sampling and laboratory analysis` · `1500` · `INR` · today → **Record cost** → attach invoice PDF; **fin1@** → **Approve**.
4. **fin2@ · Settlements → New settlement run**: Period 1 · INR · the approved sharing version and allocation → **Create run** → **Calculate** → **Verify (recompute from snapshot)** → **Submit**.
   ✅ 8,500 − 1,500 = **7,000** distributable; farmers 60 % = **4,200**; developer 2,800.
   🔎 fin2@ tries **Approve** → refused. **fin3@** → **Approve**.
5. **fin2@** → **Create payouts** → **Payouts** → **Submit**.
   🔎 **fin3@** → **Approve** → refused `BANK_ACCOUNT_NOT_VERIFIED`.
6. **pm@ · Farmers → Ramesh Patil → Bank** tab: Account holder · Bank `State Bank of India` · Routing code `SBIN0001234` · Account number → **Add bank account**; **fin1@** → **Verify**.
7. **fin3@** → **Approve** the payout. 🔎 fin3@ tries **Execute** → refused.
8. **fin4@** → **Execute** → **Record paid**: reference `NEFT-002` + PDF → **Upload evidence and record PAID**.
9. **fin1@** → **Reconcile**: Statement reference `NEFT-002` · amount `4200` · `INR` · date · statement PDF → **Upload statement and reconcile**. ✅ **Matched**; payout **Reconciled**; settlement **Completed**.

## Stage 17: Farmer self-service
⚠️ There is currently **no screen to link a farmer login to the farmer profile** (the server supports it, the UI doesn't). Until that
is added, "My payouts" can't be tested from the UI.

## Final checks
1. **Project → Status history**: Draft → Data collection → Eligibility review → Standard selected → Activity selected → Methodology review → Methodology confirmed → MRV planned → Monitoring → Calculation ready → Calculated → Verification → Verified → Issued.
2. **Administration → Audit log**: every action with who, when and the reason.
3. All 🔎 tests were refused.
