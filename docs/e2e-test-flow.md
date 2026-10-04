# End-to-end test flow (manual, from a clean database)

Work through the stages in order, top to bottom. Each step says **who** does it, **where**, **what to enter**, and **what you should see**. 🔎 marks a negative test: it must be *refused*. That refusal proves the approval rules work.

## 0. Before you start

**Starting point.** On a brand-new database, first do [fresh-setup.md](fresh-setup.md): migrations, the first admin, then the organizations and users. On an existing one that was reset, the database holds only the accounts, organizations, roles and permissions. All farmers, farms, projects, methodologies, standards and activities, MRV, lab and calculation data were removed, and document numbering restarts at `…-000001`. The one reference item kept is the consent type **Personal data processing**, which is required to activate a farmer.

**Servers.**
- Backend on port 8000.
- `npx ng serve` in `frontend`.
- Open http://localhost:4200.

**Tips.**
- Keep 2–3 browser windows open: normal, Incognito, and a second browser. Each holds its own sign-in, so you don't have to keep signing out.
- Almost every action asks for a **reason**. Type 3 or more characters.
- A red message shows a business-rule code (`SEPARATION_OF_DUTIES`, `REQUIREMENTS_NOT_MET`, …) and names the field at fault. Detail pages have a **"still needed"** checklist that says what's missing.
- Dates use the month/day/year format in the date boxes.

**Users** (organizations: DEV = Green Farms Developer, LAB = Soil Test Lab, VVB = Verify Co, PLATFORM = platform staff):

| User | Org | Role | Main job in this test |
|---|---|---|---|
| your admin | PLATFORM | Platform Admin | catalog, audit log |
| meth1@ | PLATFORM | Methodology Specialist | writes the methodology, recommends it |
| meth2@ | PLATFORM | Methodology Specialist | approves the methodology |
| pm@ | DEV | Project Manager | farmer, farm, project |
| qa@ | DEV | QA Officer | approves KYC, eligibility, plan, dataset |
| gis@ | DEV | GIS Specialist | farm verification, boundary, strata, design |
| mrv@ | DEV | MRV Manager | MRV plan, periods, design, dataset, lab engagement |
| sup@ | DEV | Field Supervisor | assigns points, accepts field work, ships samples |
| col@ | DEV | Field Collector | field collection, samples |
| analyst@ | DEV | Calculation Analyst | calculation run |
| labmgr@ | LAB | Lab Manager | accepts the engagement |
| labtech@ | LAB | Lab Technician | receives and analyses samples |
| labqa@ | LAB | Lab Manager | independent lab QA |
| vvb@ | VVB | VVB Reviewer | external verification |

> `analyst@` and `vvb@` still have their **temporary** password. On first sign-in they're forced to set a new one, which is part of the test.

---

## Stage A: Catalog (as admin)

**A1. Check the consent type.** **Administration → Consent types**. **Personal data processing** (`DATA_PROCESSING`, v1) is listed as **Active**.

**A2. Standard.** **Projects → Standards & activities** → left card:

| Field | Value |
|---|---|
| Code | `VCS` |
| Name | `Verified Carbon Standard` |
| Programme owner | `Verra` |
| Type | `Voluntary` |

Click **Add standard**.

**A3. Activity.** Right card:

| Field | Value |
|---|---|
| Code | `IALM` |
| Name | `Improved agricultural land management` |
| Offered under | ✅ `Verified Carbon Standard` |

Click **Add activity**.

✅ The activity shows "Offered under: Verified Carbon Standard". Without that link, the activity never appears later.

---

## Stage B: Methodology

**B1 (`meth1@`).** **Methodologies → Add a methodology**:

| Field | Value |
|---|---|
| Code | `VM0042` |
| Name | `Improved Agricultural Land Management` |
| Standard / route | `Verified Carbon Standard` |
| Activities | `Improved agricultural land management` |

Click **Add methodology**.

**B2 (`meth1@`).** **New version label** `2.2` → **New draft version** → **Open** the version.

**B3 (`meth1@`). Version details:**

| Field | Value |
|---|---|
| Effective from | `10/21/2025` |
| Effective to | leave empty |
| Source | `Verra – VM0042 v2.2 (TEST copy, not official rules)` |

Click **Save details**.

**B4 (`meth1@`). Applicability tab.** Add two rules, clicking **Add rule** after each:

| Field | A1 | A2 |
|---|---|---|
| Code | `A1` | `A2` |
| Title | `Standard is VCS` | `Activity is IALM` |
| Category | `Standard` | `Activity` |
| Fact key | `standard_code` | `activity_code` |
| Operator | `EQUALS` | `EQUALS` |
| Expected value (JSON) | `"VCS"` (with the quotes) | `"IALM"` (with the quotes) |
| If it fails | `Not applicable` | `Not applicable` |

**B5 (`meth1@`). Monitoring tab.** Add two rules:

| Field | M1 | M2 |
|---|---|---|
| Code | `M1` | `M2` |
| Title | `Soil organic carbon` | `Tillage practice` |
| Parameter | `soil_organic_carbon` | `tillage_practice` |
| Unit | `%` | **leave empty** |
| Frequency | `Per period` | `Per season` |
| Measurement source | `Laboratory` | `Field activity` |

**B6 (`meth1@`).** **Submit for approval**. Status: **In review**.

🔎 **B7 (`meth1@`).** Try **Approve**. It's refused: the submitter can't approve.

**B8 (`meth2@`).** Open the version → **Approve**. ✅ Status: **Approved**, and the rules are now read-only. "Calculation: Not production ready" is expected (see Stage I).

---

## Stage C: Farmer (`pm@`, then `qa@`)

| # | Who | Where | Action | You should see |
|---|---|---|---|---|
| C1 | pm@ | **Farmers → Register farmer** | Managing org `Green Farms Developer` · Full name `Ramesh Patil` · Primary phone `9876543210` · Village `Pimpalgaon` · District `Nashik` · State `Maharashtra` · Country `IN` → save | Farmer page, code `FRM-2026-000001`, **Draft** |
| C2 | pm@ | Header | Move to **Registered** | **Registered** |
| C3 | pm@ | **KYC** tab | Upload any PDF/PNG/JPG · ID type · ID number `1234 5678 9012` → submit | **KYC pending**; the number shows as `••••9012` |
| C4 🔎 | pm@ | KYC tab | Try to approve your own KYC | Refused, or no button |
| C5 | qa@ | Same farmer → **KYC** | Approve | **KYC verified** |
| C6 | pm@ | **Consents** tab | Consent `Personal data processing` · Consent text version `v1` · Captured by `Paper signed` → **Record consent** | Consents (1); the checklist item is ticked |
| C7 | pm@ | Header | **Activate** | ✅ **Active** |

## Stage D: Farm (`pm@`, then `gis@`)

| # | Who | Where | Action | You should see |
|---|---|---|---|---|
| D1 | pm@ | **Farms → New farm**, or the farmer's **Farms** tab → **Add farm** | Farmer `Ramesh Patil` · Farm name `Pimpalgaon plot 1` · Land tenure `Owned` · Declared area `2` · Village / District / State · Country `IN` → **Create farm and draw boundary** | `FARM-2026-000001`, **Draft** |
| D2 | pm@ | **Boundary** tab | Paste the corners below into **Paste several corners** → **Add these corners**. Or click 4+ points on the map. Then **Check boundary** → **Save as new boundary version**. | "Measured by SQL Server ≈ 2.2 ha" |
| D3 | pm@ | **Ownership** tab | Owner type `Farmer` · Owner name `Ramesh Patil` · Relationship `Owner` · Share % `100` · Title / survey reference `Survey 12/3` · Valid from `01/01/2020` → save | One record |
| D4 | pm@ | Header | **Submit** | **Submitted** (overlap check runs) |
| D5 🔎 | pm@ | Header | Look for **Verify** | Not available: the submitter can't verify |
| D6 | gis@ | Farm → **Ownership** | **Verify** the record | Verified |
| D7 | gis@ | Header | **Start review** | **GIS review** |
| D8 | gis@ | **Overlaps** tab | **Clear** anything listed | No open overlaps |
| D9 | gis@ | Header | **Verify** | ✅ **Verified** |

Corners for D2 (an approximately 2.2 ha plot near Pimpalgaon). Enter them in order around the field:
```
20.0063, 73.7910
20.0063, 73.7925
20.0050, 73.7925
20.0050, 73.7910
```

**Optional (makes the record complete):**
- **History** tab, as pm@:
  - Land use 2023/2024/2025 `CROPLAND` (source Farmer claim);
  - Crop 2025 Kharif `Soybean`;
  - Practice 2025 `HISTORICAL` `Conventional tillage` and 2026 `PROPOSED` `Reduced tillage`.
- **Documents** tab: a PDF as `LAND_TITLE`.
- **3D:** use the **2D / 3D** switch on the map to see the farm in 3D.

---

## Stage E: Project and eligibility

| # | Who | Where | Action | You should see |
|---|---|---|---|---|
| E1 | pm@ | **Projects → New project** | Org `Green Farms Developer` · Name `Nashik soil carbon pilot` · Type (any) · Country `IN` · Region `Maharashtra` · Planned start `06/01/2026` → **Create project** | `PRJ-2026-000001`, **Draft** |
| E2 | pm@ | Header | **Start data collection** | **Data collection** |
| E3 | pm@ | **Farms** tab | Farm `Pimpalgaon plot 1` · Agreement / evidence reference `Participation agreement clause 4` → **Add farm** | Farm listed with a "Rights" chip |
| E4 | pm@ | **Boundary** tab | Just look | **Project area** computed by SQL Server |
| E5 | pm@ | **Team** tab | Person `qa@` · role → **Add to team** | Listed |
| E6 | pm@ | **Standard & activity** tab | `Verified Carbon Standard` → **Select**; `Improved agricultural land management` → **Select** | Both "(current)" |
| E7 | pm@ | **Crediting & baseline** tab | Period `06/01/2026`–`05/31/2036` → **Record period**; Baseline `06/01/2021`–`05/31/2026`, `Conventional tillage, residue burning` → **Record baseline** | Both recorded |
| E8 | pm@ | Header | **Submit for eligibility review** | **Eligibility review** |
| E9 | gis@ | **Boundary** tab | **Accept boundary** | Review: Accepted |
| E10 | qa@ | **Carbon rights** tab | **Verify** the record | Verified |
| E11 🔎 | pm@ | Header | Look for **Approve eligibility** | Not shown: the submitter can't approve |
| E12 | qa@ | Header | **Approve eligibility** | **Standard selected** |
| E13 | pm@ | Header | **Confirm activity** | ✅ **Activity selected** |

## Stage F: Methodology selection

| # | Who | Action | You should see |
|---|---|---|---|
| F1 | pm@ | Project → **Methodology** tab → **Evaluate candidates**. Skip "Declared facts". | Candidate **VM0042 2.2: Applicable**; expand it to see A1 ✔ and A2 ✔; status **Methodology review** |
| F2 | meth1@ | **Projects** → project → **Methodology** → expand → **Recommend** | "Recommended by meth1" |
| F3 🔎 | meth1@ | Try **Confirm & lock** | Not allowed |
| F4 | pm@ | Expand → **Confirm & lock** | 🔒 Lock card "VM0042 2.2"; status **Methodology confirmed**. **Don't click Unlock.** |

✅ The **Status history** tab shows: Draft → Data collection → Eligibility review → Standard selected → Activity selected → Methodology review → Methodology confirmed.

---

## Stage G: Monitoring (MRV)

Everything happens in **MRV → Nashik soil carbon pilot**. The yellow **CONFIGURATION_REQUIRED** note is expected: the test methodology defines no sampling rules.

| # | Who | Tab / action | You should see |
|---|---|---|---|
| G1 | mrv@ | **Create MRV plan**: frequency `Annual` · approach `MEASURE_AND_REMEASURE` · `06/01/2026`–`05/31/2036` · **Required evidence** `Field photos, GPS, lab report` (must not be empty) → **Create plan (draft)** → **Submit for approval** | M1 and M2 added automatically; **Submitted** |
| G2 | qa@ | **MRV plans** → open → **Approve** (this acknowledges the configuration gaps) | Approved; project **MRV planned** |
| G3 | mrv@ | **Monitoring periods**: `Period 1` · purpose `MONITORING` · `06/01/2026`–`05/31/2027` → **Create period** → **Mark planned** → **Start period** → **Open data collection** | Period **Data collection**; project **Monitoring** |
| G4 | mrv@ | **Stratification**: Code `S1` · Name `Black soil plots` · tick the farm · characteristic `SOIL_TYPE` = `Vertisol` → **Create stratum** | Draft |
| G5 | gis@ | **Stratification** → **Approve** | Approved |
| G6 | mrv@ | **Sampling design**: Code `SOIL-1` · Name `Baseline soil sampling` · `STRATIFIED_RANDOM` · method `Soil auger` · depth `0`/`30` · precision `10` · confidence `90` · count for S1 `2` → **Create design (2 samples)** | Draft design |
| G7 | gis@ | **Sampling design** → **Approve design** | Approved |
| G8 | mrv@ | **Generate sampling points** | "Points generated (SQL Server validated)", 2 points in the farm |
| G9 | sup@ | **Points & assignments** → **Select unassigned** → collector `col@` → **Assign 2 point(s)** | Assigned |
| G10 | col@ | **Field work** (phone view: F12 → Ctrl+Shift+M) → **Start collection** on each point. Enter: lat/long = the **planned point** coordinates; collected at = now; depth `0`/`30`; **GPS accuracy empty**; tick every checklist item; add one photo. Then **Save & submit**. | Both **Submitted** |
| G11 🔎 | col@ | Try to accept your own record | Not allowed |
| G12 | sup@ | **Points & assignments** → **Accept** each record | Both **Accepted** |
| G13 | mrv@ | **Monitoring data**: `tillage_practice` · farm · `REDUCED` · observed today · phase `PROJECT` → **Record value** | Recorded |
| G14 | mrv@ | **Datasets & QA**: Period 1 → **Create dataset version** → **Open / QA** → **Submit for QA** | Submitted (frozen, hashed snapshot) |
| G15 | qa@ | Dataset → **Start QA review** (15 checks; the WARN "analysis pending" is OK) → QA result `PASS` → **Record QA result** → **Approve dataset** | ✅ Dataset and period **Approved** |

⚠️ **Avoid:** once the dataset is submitted (G14), never press **Open data collection** on that period again. It's a known bug that leaves the period stuck.

---

## Stage H: Laboratory (do it for **both** samples)

| # | Who | Action | You should see |
|---|---|---|---|
| H1 | mrv@ | **Samples & laboratory**: Laboratory `Soil Test Lab` · tick `M1 · soil_organic_carbon` → **Propose engagement** | Proposed |
| H2 | labmgr@ | **Laboratory → Engagements** → **Accept** | **Active** |
| H3 | col@ | **Field work** → point 1 → **View** (accepted record) → Laboratory samples: `Topsoil core 0–30 cm` · `500` `g` · label `BAG-01` → **Register sample** → seal `SEAL-0001` → **Seal sample**. Repeat for point 2 with `BAG-02` / `SEAL-0002`. | `SMP-2026-000001` and `…02` **Sealed**; one lab test each, created automatically |
| H4 | sup@ | **Samples & laboratory**: ship to `Soil Test Lab` · carrier `Courier` → **Create shipment** → add both samples → **Dispatch** | Dispatched |
| H5 | labtech@ | **Laboratory → Incoming**: seal observed = each sample's own seal (`SEAL-0001` / `SEAL-0002`) · condition `Good` → **Record receipt** | Received |
| H6 | labtech@ | **Samples**: accession `LAB-0001` / `LAB-0002` → **Register** | Registered |
| H7 | labtech@ | **Worklist** → each test → **Start test** → method `Walkley-Black` · `NUMERIC` · value `1.24` (then `1.31`) · unit exactly `%` · analysed now → **Save result** → **upload a PDF report** → **Submit for QA** | Submitted |
| H8 🔎 | labtech@ | Try to approve your own result | Refused |
| H9 | labqa@ | **Laboratory → QA** → **Review** each → **Start QA review** (12 checks) → decision `APPROVED` + notes → **Record decision** | ✅ Both **Approved**; samples **Analysed** |
| H10 | mrv@ | **Samples & laboratory** → **Lineage** on a result | Result → test → sample → field record → point → farm → project |
| H11 🔎 | labtech@ | Open `http://localhost:4200/mrv` | "You don't have access to this page" |

If lab QA refuses approval with a **report** check failure, the PDF wasn't attached. Have **labqa@** reject the result. **labtech@** then enters a new version with the PDF attached and submits again.

---

## Stage I: Calculation, internal QA, VVB (with the simple test methodology from Stage B)

With the Stage B test methodology (no calculation module selected), Stage I still stops at the calculation:

| # | Who | Action | You should see |
|---|---|---|---|
| I1 | analyst@ | (First sign-in → set a new password.) **Calculations** → project + Period 1 | Blocker **CONFIGURATION_REQUIRED** (no module selected for this version) |
| I2 | qa@ | Open a blocked run → **Findings** → **Raise finding**; analyst@ responds; qa@ **Resolves** | Resolved |
| I3 | pm@ / vvb@ | **Verification** tab → propose `Verify Co`; vvb@ accepts with a conflict-of-interest declaration | Accepted; "no package" until a calculation is approved |

To get real numbers, run **Stage J**.

---

## Stage J: VM0042 calculation, end to end (measure & remeasure + default-factor emissions)

This uses the built-in **VM0042 v2.2 calculation module**. It needs **two sampling campaigns** (the baseline sampling at t0 and a
re-measurement), **at least 3 control sites**, and **2 depth layers per sample**. It is "Not production ready" (development only)
until Stage J8.

### J1. Methodology with the module (meth1@ → meth2@)
1. **Methodologies → Add a methodology**: Code exactly `VM0042`, Standard `Verified Carbon Standard`, Activity `IALM`.
2. New draft version, label exactly `2.2`; Effective from `10/21/2025`; Source `Verra VM0042 v2.2 (C&C 11 Jun 2026)`.
3. **Calculation tab → Calculation module** → choose **VM0042 v2.2 - SOC measure & remeasure (QA2) + default-factor emissions (QA3)** →
   **Use this module**. The draft now has 8 calculation rules (`V42-…`), 13 monitoring rules (`V42_OC` g/kg and `V42_SOIL_MASS` g from
   the laboratory; fertiliser, fuel, lime, residue burning and irrigation per farm; `V42_NPR` risk rating per project) and a sampling rule
   (`min_samples_per_stratum = 3`, `core_details_required = true`).
4. Add the applicability rules A1 (`standard_code EQUALS "VCS"`) and A2 (`activity_code EQUALS "IALM"`) as in Stage B; **Submit**;
   meth2@ **Approves**.

### J2. Farms, project, control sites
- Stages C–F as before, but lock the project on **VM0042 2.2**.
- Create **3 more verified farms** of the same organization that do **not** join the project — they become control sites.
- **MRV → Stratification**:
  - project stratum `S1` (your project farm), characteristics `SOIL_TEXTURE`, `SOIL_GROUP`, `PRECIPITATION_MM` (e.g. `750`);
  - switch to **Control site** and create `C1`, `C2`, `C3` (one control farm each), **Represents `S1`**, with the **same** texture and
    soil group and rainfall within 100 mm. gis@ approves each. The checklist at the top must show "3 of at least 3" and "Every stratum has a
    control site".

### J3. Two monitoring periods
1. **Period 0** — purpose **BASELINE**, e.g. `2025-06-01`–`2026-05-31`: the sampling at t0.
2. **Period 1** — purpose **MONITORING**, e.g. `2026-06-01`–`2027-05-31`: the re-measurement (the calculation is run for this one).
For **each** period: a sampling design that allocates **3 samples to S1 and to each control site**, depth `0`–`50` cm; generate points;
assign them to col@.

### J4. Field collection (col@) — every point, both periods
Depth top `0`, bottom `50`; **Probe inside diameter (mm)** e.g. `21.5`; **Number of cores** e.g. `4`; checklist; photo; submit. sup@ accepts.

### J5. Laboratory — two depth layers per field record
1. mrv@ proposes the engagement with rules **`V42_OC` and `V42_SOIL_MASS`**; labmgr@ accepts.
2. On each accepted field record col@ registers **two samples**: depth `0`–`30` and `30`–`50` (each gets a `V42_OC` and a
   `V42_SOIL_MASS` test automatically), seals them; sup@ ships; labtech@ receives and registers.
3. labtech@ enters for every sample: organic carbon in **g/kg** (e.g. `12.5`; 1.25 % = 12.5 g/kg) and dry fine-earth soil mass in **g**
   (e.g. `280` for 0–30 cm, `200` for 30–50 cm), attaches the PDF report, submits; labqa@ approves.

### J6. Farm activity and project risk (Monitoring data tab)
- Per farm, phase **BASELINE**, one record per historical year (observed on a date in 2023, 2024, 2025): `V42_FSN` kg N, `V42_DIESEL` L,
  `V42_BURN_RICE` kg dry matter, …
- Per farm, phase **PROJECT**, observed inside Period 1: the same activities under the new practice.
- Optional `V42_IRRIGATION`: `NONE`, `DRIP` or `OTHER`.
- Project level: `V42_NPR` = the AFOLU non-permanence risk rating, e.g. `12` (%).
Then create, submit and approve the **dataset** of each period (qa@).

### J7. Calculate (analyst@)
**Calculations** → project → **Period 1** → readiness shows no blocker (only the warning "NOT_PRODUCTION_READY: non-production use only")
→ **New calculation run** → **Check readiness & freeze inputs** → **Execute**. The outputs list every step with its VM0042 equation:
reference soil mass, SOC stocks per stratum and campaign, emission reductions per source, SOC change (project and baseline),
uncertainty (%), buffer, and **VCU_TOTAL** (whole tonnes, rounded down). Then qa@ runs calculation QA and approves.

Typical blockers and what they mean: `PREVIOUS_PERIOD_REQUIRED` (Period 0 dataset not approved) · `CONTROL_SITES_REQUIRED` (fewer than 3
sampled control sites) · `INSUFFICIENT_SAMPLES` (fewer than 2 samples in a stratum and campaign) · `DEPTH_INCREMENTS_REQUIRED` (only one
depth layer) · `MISSING_REQUIRED_INPUT` with `CORE_DETAILS_MISSING` (probe diameter / cores not recorded) · `MODULE_NOT_SELECTED`.

### J8. Production readiness (after the expert review)
On the approved version's Calculation tab: meth1@ **Request production readiness** with the expert's evidence summary; meth2@
**Approve**. From then on the calculation is allowed in production; until then it is blocked there.

---

## Final checks

1. **Project → Status history**: Draft → Data collection → Eligibility review → Standard selected → Activity selected → Methodology review → Methodology confirmed → MRV planned → Monitoring.
2. **Admin → Audit log**: every action above, with who, when and the reason.
3. **MRV → project → MRV history**: every monitoring event.
4. **Dashboard** (as pm@): the counts show 1 farmer, 1 active farmer, 1 farm, 1 verified farm and 1 project.
5. All 🔎 negative tests were refused.

## Troubleshooting

| What you see | Fix |
|---|---|
| "Too many sign-in attempts" | Set `LOGIN_RATE_LIMIT_PER_MINUTE=100` in `backend/.env` and restart the backend |
| A button is missing | Wrong user for that step (check the table at the top), or it's your own submission |
| `REQUIREMENTS_NOT_MET` | Read the "still needed" checklist on the page |
| No methodology candidate (F1) | The version isn't Approved, effective-from is after the project start, or the activity isn't IALM |
| `EVALUATION_OUTDATED` (F4) | You re-evaluated after the recommendation; meth1@ must recommend again |
| 422 "invalid data" on field collection | The message names the field. Usually GPS accuracy (leave it empty), depth (whole numbers) or a future date. |
| `INSUFFICIENT_AREA` on point generation | Use count `1`, or draw a larger boundary |
| Seal mismatch at receipt | Seal observed must equal the seal number from H3 |

## Restoring the previous data

A full backup was taken just before the reset: `CC_before_reset_20261004.bak` in the SQL Server backup folder (`C:\Program Files\Microsoft SQL Server\MSSQL16.SQL_LOCAL\MSSQL\Backup`). The uploaded files were copied to the session scratchpad. To restore, ask for it; it's a `RESTORE DATABASE` from that file.
