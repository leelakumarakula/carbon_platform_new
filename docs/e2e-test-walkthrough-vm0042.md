# Test walkthrough — Verra VCS · Improved agricultural land management · VM0042 v2.2

A step-by-step test script for a soil-carbon project credited under **Verra's Verified Carbon Standard (VCS)** with the methodology
**VM0042 v2.2** and the platform module **`VM0042-V2.2-QA2-QA3`** (soil carbon measured and remeasured from soil samples, plus
default-factor emissions). Unlike the GS402 walkthrough, this path uses **soil sampling, the laboratory and control sites** — the path a
real sampling project takes.

Every step says **LOGIN** (who signs in), the step **TYPE** (FILL · VERIFY · APPROVE · NEGATIVE CHECK = must be refused),
**GO TO**, **ENTER**, **CLICK**, **YOU SHOULD SEE** and **NEXT** (who logs in after). Field rules for each form are in
[e2e-test-guide.md](e2e-test-guide.md).

All values are **test values** chosen to produce a known result (about **950 VCUs** on a 100 ha project farm). They are not real
project data.

---

## Read this first

### How VM0042 credits soil carbon
| Concept | What it means in this test |
|---|---|
| **Two sampling rounds** | **Period 0** (baseline, before the practice change takes effect) and **Period 1** (remeasurement). Credits = change between them. |
| **Control sites** | **3 farms that keep the old practice.** Their change shows what would have happened anyway, and is subtracted. |
| **Equivalent soil mass** | Carbon is compared in the same mass of soil, so each sample is split into **2 depth layers** (0–30 cm and 30–50 cm) and the lab reports **organic carbon (g/kg)** and **dry soil mass (g)** for each layer. |
| **Core details** | Every field record must state the **probe diameter** and **number of cores**, used to convert the sample mass to tonnes per hectare. |
| **Emission reductions** | Fertiliser, diesel and residue burning before vs. after the practice change. |
| **Buffer** | `V42_NPR` (non-permanence risk %) sets aside part of the removals. |

### Workload
Each period has **4 strata × 3 points = 12 field records → 24 samples → 48 lab results** (organic carbon + soil mass per sample),
so the whole test has **96 lab results**, each with a PDF and lab QA. Split the lab work between testers if possible and use one small
PDF for every result.

### Depth layers — two samples per field record
VM0042 needs each core split into **two depth layers** (0–30 cm and 30–50 cm). The **Register & seal sample** form on the field
record has **Depth top (cm)** and **Depth bottom (cm)** fields for this (step 8.7). After the first layer is registered, the form
proposes the next one (30–50 cm) automatically.

### Dates
Date boxes follow **your browser's format** — on many Indian machines it is **day-month-year**. This guide writes dates as `1 Nov 2025`;
type them in your box's format and check the saved value.

### Users
| Login | Role | Organization |
|---|---|---|
| leelak@vayublue.com | Platform Admin | platform |
| ms1@yopmail.com / ms2@yopmail.com | Methodology Specialist | platform |
| pm@yopmail.com | Project Manager | varsapradaya_developer |
| qa@yopmail.com | QA Officer | varsapradaya_developer |
| gis@yopmail.com | GIS Specialist | varsapradaya_developer |
| mrv@yopmail.com | MRV Manager | varsapradaya_developer |
| sup@yopmail.com | Field Supervisor | varsapradaya_developer |
| col@yopmail.com | Field Collector / Field Agent | varsapradaya_developer |
| analyst@yopmail.com | Calculation Analyst | varsapradaya_developer |
| labtec@yopmail.com | Lab Technician | soiltestlab |
| labmgr@yopmail.com | Lab Manager / Lab QA | soiltestlab |
| vvb@yopmail.com | VVB / ACVA Reviewer | verify_co |
| credits, fin1, fin2, fin3, buyer, compliance | as in [e2e-test-walkthrough.md](e2e-test-walkthrough.md) Stage 0 | for Stages 11–14 |

Every action button asks for a reason — type `ok test`. Several testers on one database: add your tester number where marked.

---

## The flow at a glance

| Stage | Logins in order | What happens |
|---|---|---|
| 1 Catalog | leelak | Verra standard `VCS`, activity `IALM` |
| 2 Methodology | ms1 → ms2 | VM0042 2.2 with the module; approval |
| 3 Farms | pm → gis | 1 project farm (reuse North block) + 3 control farms |
| 4 Project | pm → gis → qa → pm | project, eligibility |
| 5 Lock | ms1 → pm | methodology locked on VM0042 2.2 |
| 6 MRV setup | mrv → qa → mrv → gis → sup | plan, 2 periods, project stratum + 3 control sites |
| 7 Lab engagement | mrv → labmgr | lab scope V42_OC + V42_SOIL_MASS |
| 8 Period 0 sampling | gis → sup → gis → sup → col → sup → col → sup → labtec → labmgr | design, points, field work, 2 depth samples per point, lab |
| 9 Period 0 dataset | mrv → qa | NPR record, dataset approved |
| 10 Period 1 sampling + data | same as 8, then mrv | remeasurement, farm activity, NPR |
| 11 Period 1 dataset + calculation | mrv → qa → analyst → qa | dataset, run, ≈ 950 VCUs |
| 12 Verification → payout | as the GS402 walkthrough | VVB, registry, ledger, marketplace, payout |

---

## Stage 1 — Catalog

### 1.1 · LOGIN `leelak` · FILL — Verra standard and activity
**GO TO:** Projects → **Standards & activities**. Skip what already exists.

| Card | Field | Enter |
|---|---|---|
| Standard | Code | `VCS` |
| | Name | `Verified Carbon Standard` |
| | Programme owner | `Verra` |
| | Type | Voluntary |
| | Official source URL | `https://verra.org/programs/verified-carbon-standard/` |
| Activity | Code | `IALM` |
| | Name | `Improved agricultural land management` |
| | Offered under | tick **Verified Carbon Standard** |

**CLICK:** Add standard → Add activity.

**YOU SHOULD SEE:** "Offered under: Verified Carbon Standard" on the IALM row.

**NEXT:** log in as `ms1`.

---

## Stage 2 — Methodology VM0042 2.2 with the module

### 2.1 · LOGIN `ms1` · FILL — Methodology, version, module, rules
**GO TO:** Methodologies

| Where | Field | Enter |
|---|---|---|
| Add a methodology (skip if VM0042 exists) | Code | `VM0042` (exactly) |
| | Name | `Improved Agricultural Land Management` |
| | Standard / route | Verified Carbon Standard |
| | Activities | Improved agricultural land management |
| New version | New version label | `2.2` — or `2.2-` + tester no. (e.g. `2.2-02`) if `2.2` exists |
| Version details | Effective from | `21 Oct 2025` |
| | Source | `Verra VM0042 v2.2` |
| | Source URL | `https://verra.org/methodologies/vm0042-improved-agricultural-land-management-v2-2/` |
| Tab **calculation** | Calculation module | **VM0042 v2.2 - SOC measure & remeasure (QA2) + default-factor emissions (QA3) · v1.0.0** |
| Tab **applicability** — rule 1 | Code / Title / Category | `A1` / `Standard is VCS` / Standard |
| | Fact key / Operator / Expected value / If it fails | `standard_code` / EQUALS / `"VCS"` / Not applicable |
| Tab **applicability** — rule 2 | Code / Title / Category | `A2` / `Activity is IALM` / Activity |
| | Fact key / Operator / Expected value / If it fails | `activity_code` / EQUALS / `"IALM"` / Not applicable |

**CLICK:** Add methodology → New draft version → Open → Save details → **Use this module** → Use module → Add rule (×2) → **Submit for approval**.

**YOU SHOULD SEE:** badge **Module: VM0042-V2.2-QA2-QA3**; the module card lists 8 rules `V42-BSL` … `V42-NET`, data `V42_OC` (g/kg),
`V42_SOIL_MASS` (g), fertiliser / fuel / lime / burning per farm, `V42_NPR` per project, and sampling settings (measure and remeasure,
≥ 3 samples per stratum, core details required, stratified random); status **In review**.

**NEXT:** stay as `ms1`.

### 2.2 · LOGIN `ms1` · NEGATIVE CHECK
Try **Approve**. **YOU SHOULD SEE:** refused. **NEXT:** log in as `ms2`.

### 2.3 · LOGIN `ms2` · APPROVE
**CLICK:** Approve (reason). **YOU SHOULD SEE:** **Approved**; "Calculation: Not production ready" (normal in testing).

**NEXT:** log in as `pm`.

---

## Stage 3 — Farms: 1 project farm + 3 control farms

The project farm is **North block** (≈ 100 ha, verified, farmer Ramesh Patil active) from the GS402 test. If you don't have it, create it
as in [e2e-test-walkthrough.md](e2e-test-walkthrough.md) Stages 3–4.

Control farms must be **verified farms of the same organization that do NOT join this project**, within 250 km. They keep the old practice.

### 3.1 · LOGIN `pm` · FILL — Three control farms
**GO TO:** Farmers → Ramesh Patil → tab Farms → **Add farm** (once per farm). For each: Land tenure Owned · Declared area `4` · Country `IN`,
then **Boundary** (paste corners) → **Documents** (Land record PDF) → **Ownership** (Farmer · Owner · `100` % · evidence document) →
**Submit for review**.

| Farm name | Corners (lat, lon — one per line). Tester 2 adds `0.02` to every latitude, tester 3 `0.04` |
|---|---|
| `Control C1` | `20.1000, 73.7200` · `20.1000, 73.7219` · `20.1018, 73.7219` · `20.1018, 73.7200` |
| `Control C2` | `20.1000, 73.7300` · `20.1000, 73.7319` · `20.1018, 73.7319` · `20.1018, 73.7300` |
| `Control C3` | `20.1000, 73.7400` · `20.1000, 73.7419` · `20.1018, 73.7419` · `20.1018, 73.7400` |

**YOU SHOULD SEE:** each ≈ 4 ha, **Submitted**.

**NEXT:** log in as `gis`.

### 3.2 · LOGIN `gis` · VERIFY — Control farms
For each control farm: tab Ownership → **Verify** → header **Start GIS review** → **Verify farm**.

**YOU SHOULD SEE:** all three **Verified**.

**NEXT:** log in as `pm`.

---

## Stage 4 — Project and eligibility

### 4.1 · LOGIN `pm` · FILL — Build and submit
**GO TO:** Projects → **New project**

| Tab / form | Field | Enter |
|---|---|---|
| New project | Organization / Name / Type | varsapradaya_developer / `Nashik VM0042 pilot` (+ tester no.) / Agricultural land management |
| | Country / Region / **Planned start** | `IN` / `Nashik` / **`1 Nov 2025`** (must be on or after the version's 21 Oct 2025) |
| Header | Start data collection | reason |
| Farms | Farm / Participation from / Rights holder | **North block only** / `1 Nov 2025` / Farmer |
| | Reference / Share % | `Carbon rights clause of AGR-2026-…` / `100` |
| | Conflicts box (North block is in the GS402 projects) | tick **I acknowledge these conflicts** · `Separate VM0042 test project` |
| Standard & activity | Standard / Activity | Verified Carbon Standard → Select / Improved agricultural land management → Select |
| Crediting & baseline | Crediting period | `1 Nov 2025` – `31 Oct 2035` → Record period |
| | Baseline From / To / Practices / Data sources | `1 Nov 2020` / `31 Oct 2025` / `Full tillage, residue burning, high N` / `Farmer interview` → Record baseline |

**Do not add the control farms to the project.**

**CLICK:** Create project → Start data collection → Add farm → Select ×2 → Record period → Record baseline → **Submit for eligibility review**.

**YOU SHOULD SEE:** **Eligibility review**.

**NEXT:** log in as `gis`.

### 4.2 · LOGIN `gis` · VERIFY — **Boundary** tab → **Accept boundary**. **NEXT:** `qa`.
### 4.3 · LOGIN `qa` · VERIFY + APPROVE — **Carbon rights** → **Verify**; header **Approve eligibility** → **Standard selected**. **NEXT:** `pm`.
### 4.4 · LOGIN `pm` · FILL — header **Confirm activity** → **Activity selected**. **NEXT:** `ms1`.

---

## Stage 5 — Lock the methodology

### 5.1 · LOGIN `ms1` · FILL — Project → tab **Methodology** → **Evaluate candidates** → expand **VM0042 2.2** (Applicable, A1 ✔ A2 ✔) → **Recommend** → reason `Applicable; module VM0042-V2.2-QA2-QA3`.
If VM0042 is missing: the planned start is before 21 Oct 2025, or the activity is not IALM.

**NEXT:** `pm`.

### 5.2 · LOGIN `pm` · APPROVE — **Confirm & lock** → **Methodology confirmed**. **NEXT:** `mrv`.

---

## Stage 6 — MRV plan, two periods, strata and control sites

### 6.1 · LOGIN `mrv` · FILL — MRV plan
**GO TO:** MRV → choose the project → tab **MRV plans** → **Create MRV plan**

| Field | Enter |
|---|---|
| Monitoring frequency | `Annual sampling` |
| Quantification approach | leave empty (saved as MEASURE_AND_REMEASURE from the module) — any other choice is refused |
| Monitoring start / end | **`1 Nov 2025`** / `31 Oct 2035` — the start must cover Period 0 |
| Required evidence | `Field photos, GPS, lab reports` |

**CLICK:** Create plan (draft) → **Submit for approval**.

**YOU SHOULD SEE:** the `V42_…` measurements listed; **Submitted**.

**NEXT:** log in as `qa`.

### 6.2 · LOGIN `qa` · APPROVE — open the plan → **Approve** (the dialog acknowledges the sampling-depth gap; expected in testing). **NEXT:** `mrv`.

### 6.3 · LOGIN `mrv` · FILL — Two monitoring periods
**GO TO:** tab **Monitoring periods** → Create period, twice:

| Name | Purpose | Start | End |
|---|---|---|---|
| `Period 0 baseline` | Baseline | `1 Nov 2025` | `31 May 2026` |
| `Period 1` | Monitoring | `1 Jun 2026` | `31 May 2027` |

On **Period 0 only**: **Mark planned** → **Start period** → **Open data collection**.

**YOU SHOULD SEE:** Period 0 **Data collection**; Period 1 Draft; project **Monitoring**.

**NEXT:** log in as `gis`.

### 6.4 · LOGIN `gis` · FILL — Project stratum and 3 control sites
**GO TO:** tab **Stratification** → New. For each characteristic choose it, type the value, click **+**.

| Toggle | Code / Name | Farms | Represents | Characteristics |
|---|---|---|---|---|
| Project stratum | `S1` / `North block` | North block | — | SOIL_TEXTURE `Clay` · SOIL_GROUP `Vertisol` · CLIMATE `Tropical dry` · PRECIPITATION_MM `750` |
| Control site | `C1` / `Control C1` | Control C1 | S1 | SOIL_TEXTURE `Clay` · SOIL_GROUP `Vertisol` · CLIMATE `Tropical dry` · PRECIPITATION_MM `720` |
| Control site | `C2` / `Control C2` | Control C2 | S1 | same, PRECIPITATION_MM `760` |
| Control site | `C3` / `Control C3` | Control C3 | S1 | same, PRECIPITATION_MM `780` |

**CLICK:** Create stratum / Create control site.

**YOU SHOULD SEE:** the checklist "Baseline control sites": **3 of at least 3** and **Every stratum has a control site**.

Look for **Approve** — not available to you (NEGATIVE CHECK).

**NEXT:** log in as `sup`.

### 6.5 · LOGIN `sup` · APPROVE — **Approve** S1, C1, C2, C3 (reason each).
Control sites are checked against S1: same texture, soil group and climate; rainfall within 100 mm; within 250 km. A mismatch gives
`CONTROL_SITE_NOT_SIMILAR` with the reason.

**YOU SHOULD SEE:** all four **Approved**.

**NEXT:** log in as `mrv`.

---

## Stage 7 — Lab engagement (once for both periods)

### 7.1 · LOGIN `mrv` · FILL — tab **Samples & laboratory** → Laboratory `soiltestlab` · LABORATORY rules in scope: tick **both** `V42_OC · soil_organic_carbon (g/kg)` and `V42_SOIL_MASS · fine_soil_mass (g)` → **Propose engagement**. **NEXT:** `labmgr`.
### 7.2 · LOGIN `labmgr` · APPROVE — **Laboratory → Engagements** → **Accept**. **NEXT:** `gis`.

---

## Stage 8 — Period 0: baseline sampling and lab

In the MRV workspace, set the **Monitoring period** picker at the top to **Period 0 baseline** for this whole stage.

### 8.1 · LOGIN `gis` · FILL — One sampling design for all four strata
**GO TO:** tab **Sampling design**. Create **one** design only — a second design's points would cancel the first's.

| Field | Enter |
|---|---|
| Code / Name | `SOIL-P0` / `Baseline soil sampling` |
| Sample count | S1 `3` · C1 `3` · C2 `3` · C3 `3` (at least 3 each) |
| Statistical design | Stratified random (required) |
| Sampling method | `Soil auger, 4-core composite` |
| Depth top / bottom (cm) | `0` / `50` |
| Min. distance (m) | `10` |

**CLICK:** **Create design (12 samples)**. **NEXT:** `sup`.

### 8.2 · LOGIN `sup` · APPROVE — **Approve design**. **NEXT:** `gis`.
### 8.3 · LOGIN `gis` · FILL — **Generate sampling points** → 12 points (3 in North block, 3 in each control farm). **NEXT:** `sup`.
### 8.4 · LOGIN `sup` · FILL — tab **Points & assignments** → **Select unassigned** → Field collector `colfield_test` · Planned date `20 May 2026` → **Assign 12 point(s)**. **NEXT:** `col`.

### 8.5 · LOGIN `col` · FILL — Field collection (12 points)
**GO TO:** **Field work** → **Start collection** on each point:

| Field | Enter |
|---|---|
| Latitude / Longitude | the point's own coordinates |
| Collected at | **`20 May 2026, 10:00`** (inside Period 0, a past date is fine) |
| Depth top / bottom (cm) | `0` / `50` |
| **Probe inside diameter (mm)** | `21.5` |
| **Number of cores** | `4` |
| Sample quantity / Unit | `2` / `kg` |
| Field checklist | tick all 4 |
| Photo | one JPG |

**CLICK:** **Save & submit** on each. Note each point's code (e.g. `SP-2025-000001`) — it goes on the container labels and seals in 8.7.

**NEXT:** log in as `sup`.

### 8.6 · LOGIN `sup` · VERIFY — Points & assignments → Submitted field records → **Accept** all 12. **NEXT:** `col`.

### 8.7 · LOGIN `col` · FILL — Two depth samples per field record (24 samples)
**GO TO:** **Field work** → open each **accepted** field record → section **Laboratory samples** → **Register & seal sample**.

| Field | First sample (layer A) | Second sample (layer B) |
|---|---|---|
| Description | `Soil 0-30 cm` | `Soil 30-50 cm` |
| Quantity / Unit | `1` / `kg` | `1` / `kg` |
| Container label | `<point code>-A` | `<point code>-B` |
| **Depth top (cm)** | `0` | `30` (pre-filled after the first sample) |
| **Depth bottom (cm)** | `30` | `50` (pre-filled after the first sample) |

**CLICK:** **Register sample** (once per layer).

**YOU SHOULD SEE:** two samples listed, e.g. `SMP-… · 0–30 cm · 2 test(s)` and `SMP-… · 30–50 cm · 2 test(s)`. A depth outside the
field record (e.g. bottom 60) is refused before sending: "The sample depth must lie within the field record depth".

Then, on each sample: Seal number `SEAL-<point code>-A` / `-B` → **Seal sample**.

If a record already has a **0–50 cm** sample from before this change, **sup** voids it first: **Samples & laboratory** → the sample →
**Void** → reason `Wrong depth, replaced by 0-30 and 30-50 samples`. A 0–50 sample next to the two layers blocks the calculation
(`INVALID_SOIL_PROFILE`).

**NEXT:** log in as `sup`.

### 8.8 · LOGIN `sup` · FILL — tab **Samples & laboratory** → Shipments: Ship to `soiltestlab` · Carrier `Courier` → **Create shipment** → add all 24 sealed samples → **Dispatch**. **NEXT:** `labtec`.

### 8.9 · LOGIN `labtec` · FILL — Receive, register, analyse (48 results)
**GO TO:** **Laboratory**
1. **Incoming:** keep Accept ticked, Seal observed = the sample's seal, Condition `Good` → **Record receipt**.
2. **Samples:** Accession no. `LAB-` + sample code → **Register**.
3. **Worklist:** each sample has a `V42_OC` test and a `V42_SOIL_MASS` test. For each: Method `Dry combustion` / `Oven-dry, sieved < 2 mm`
   → **Start test** → Result type Numeric · Value from the table · Unit exactly `g/kg` (OC) or `g` (mass) · Analysed at now →
   **Save result** → PDF report → **Submit for QA**.

**Period 0 values** — points numbered 1–3 by point code within each stratum:

| Stratum | Point | 0–30 cm OC (g/kg) | 0–30 cm mass (g) | 30–50 cm OC (g/kg) | 30–50 cm mass (g) |
|---|---|---|---|---|---|
| S1 | 1 | `12.0` | `280` | `7.0` | `200` |
| S1 | 2 | `11.0` | `290` | `6.5` | `210` |
| S1 | 3 | `11.5` | `285` | `6.8` | `205` |
| C1, C2, C3 (each) | 1 | `11.5` | `285` | `6.8` | `205` |
| C1, C2, C3 (each) | 2 | `11.7` | `286` | `6.6` | `204` |
| C1, C2, C3 (each) | 3 | `11.6` | `284` | `6.7` | `206` |

**NEXT:** log in as `labmgr`.

### 8.10 · LOGIN `labmgr` · APPROVE — **Laboratory → QA** → each result → **Review** → **Start QA review** → Decision `APPROVED` · Notes `Checked` → **Record decision** (48 times). labtec cannot approve own results (NEGATIVE CHECK).
**NEXT:** log in as `mrv`.

---

## Stage 9 — Period 0 dataset

### 9.1 · LOGIN `mrv` · FILL — tab **Monitoring data** (period picker: Period 0): Measurement `V42_NPR` (project level) · Value `12` · Observed on `20 May 2026` · Phase Monitoring · Source Document → **Record value**. Then tab **Datasets & QA** → Period 0 → **Create dataset version** → **Open / QA** → **Submit for QA**.
**NEXT:** `qa`.

### 9.2 · LOGIN `qa` · VERIFY + APPROVE — **Start QA review** → all PASS / WARN → QA result `PASS` → **Record QA result** → **Approve dataset**.
**YOU SHOULD SEE:** Period 0 **Approved**. **NEXT:** `mrv`.

---

## Stage 10 — Period 1: remeasurement and farm activity

### 10.1 · LOGIN `mrv` · FILL — Open Period 1: **Mark planned** → **Start period** → **Open data collection**. Set the period picker to **Period 1**.

### 10.2 — Repeat Stage 8 for Period 1 with these changes:
| Step | Change |
|---|---|
| 8.1 design | Code `SOIL-P1`, Name `Remeasurement` |
| 8.4 assign | Planned date today |
| 8.5 field work | **Collected at = today** (inside Period 1) |
| 8.7 seals | `SEAL-<point code>-A2` / `-B2` |
| 8.9 lab values | the table below |

**Period 1 values:**

| Stratum | Point | 0–30 cm OC (g/kg) | 0–30 cm mass (g) | 30–50 cm OC (g/kg) | 30–50 cm mass (g) |
|---|---|---|---|---|---|
| S1 | 1 | `13.5` | `282` | `7.4` | `201` |
| S1 | 2 | `12.6` | `288` | `6.9` | `209` |
| S1 | 3 | `13.0` | `284` | `7.2` | `204` |
| C1, C2, C3 (each) | 1 | `11.4` | `285` | `6.8` | `205` |
| C1, C2, C3 (each) | 2 | `11.6` | `287` | `6.5` | `203` |
| C1, C2, C3 (each) | 3 | `11.5` | `285` | `6.7` | `205` |

The project farm gains carbon; the control sites stay about the same.

### 10.3 · LOGIN `mrv` · FILL — Farm activity and risk (period picker: **Period 1**)
**GO TO:** tab **Monitoring data**. All farm records: Farm **North block** · Source Document. The baseline years go in **Period 1** too —
the calculation reads only the period being calculated.

| Measurement | Phase | Observed on | Value |
|---|---|---|---|
| V42_FSN (kg N) | Baseline | `1 Jun 2023` / `1 Jun 2024` / `1 Jun 2025` | `1000` / `1100` / `1200` |
| V42_FSN | Project | today | `800` |
| V42_DIESEL (L) | Baseline | `1 Jun 2023` / `1 Jun 2024` / `1 Jun 2025` | `6000` / `6000` / `6000` |
| V42_DIESEL | Project | today | `3500` |
| V42_BURN_RICE (kg d.m.) | Baseline | `1 Jun 2023` / `1 Jun 2024` / `1 Jun 2025` | `20000` / `21000` / `22000` |
| V42_BURN_RICE | Project | today | `0` |
| V42_NPR (%) — project level | Monitoring | today | `12` |

Project-phase records must be dated **inside Period 1**, or they are ignored. Leave lime, gasoline, other burning and irrigation empty
(irrigation `OTHER` would switch on nitrogen leaching).

**YOU SHOULD SEE:** 13 records.

---

## Stage 11 — Period 1 dataset and calculation

### 11.1 · LOGIN `mrv` · FILL — Datasets & QA → Period 1 → **Create dataset version** → **Open / QA** → **Submit for QA**. **NEXT:** `qa`.
### 11.2 · LOGIN `qa` · VERIFY + APPROVE — **Start QA review** → `PASS` → **Record QA result** → **Approve dataset**. **NEXT:** `analyst`.

### 11.3 · LOGIN `analyst` · FILL — Calculation
**GO TO:** **Calculations** → Project `Nashik VM0042 pilot` · Period `Period 1`.

**CLICK:** **New calculation run** → open it → **Check readiness & freeze inputs** → **Execute** → **Submit for QA**.

**YOU SHOULD SEE** (for a 100 ha project stratum; results scale with the measured area):

| Output | Meaning | Expected |
|---|---|---|
| REF_MASS_S1 | Reference mineral soil mass to 30 cm (control sites, Period 0) | ≈ 1923 Mg/ha |
| SOC_PRO_PREV_S1 → SOC_PRO_CURR_S1 | Project soil carbon, Period 0 → Period 1 | ≈ 22.51 → 25.56 Mg C/ha |
| SOC_BAS_PREV_S1 → SOC_BAS_CURR_S1 | Control-site soil carbon, Period 0 → Period 1 | ≈ 22.75 → 22.57 Mg C/ha |
| DCO2_SOIL_WP / DCO2_SOIL_BSL | Soil CO2 change, project / baseline | ≈ 1122 / −69 t CO2e |
| ER_FUEL / ER_N2O_FERT / ER_CH4_BB / ER_N2O_BB | Emission reductions by source | ≈ 7.22 / 0.69 / 1.27 / 0.31 t CO2e |
| ER_SOURCES | Total emission reductions | ≈ 9.49 t CO2e |
| UNC_PCT | Sampling uncertainty deduction | ≈ 10.19 % |
| BUFFER_CR / BUFFER_ER | Non-permanence buffer (12 %) | ≈ 121 / 7.5 t CO2e |
| VCU_CR / VCU_ER | Removal / reduction VCUs | ≈ 886 / 64 |
| **VCU_TOTAL** | **Credits, whole tonnes rounded down** | **≈ 950** |

These numbers come from running the platform's VM0042 module on exactly these inputs. A large difference means a typo in a lab value or a
missing record — check the Inputs tab.

**NEXT:** stay as `analyst` (NEGATIVE CHECK: **Approve** is not available to you), then log in as `qa`.

### 11.4 · LOGIN `qa` · VERIFY + APPROVE — tab **QA** → **Start calculation QA** → `PASS` · Notes `Inputs and outputs checked` → **Record QA** → header **Approve**.
**YOU SHOULD SEE:** run **Approved**.

---

## Stage 12 — Verification, registry, ledger, marketplace, payout

Follow [e2e-test-walkthrough.md](e2e-test-walkthrough.md) **Stages 10–14** on this project with these substitutions:

| Item | GS402 walkthrough | VM0042 test |
|---|---|---|
| Project / period | Nashik tillage pilot · Period 1 | **Nashik VM0042 pilot · Period 1** |
| Internal finding text | "Source of factors" | `Lab method` · `Confirm the OC method and sieving for all 48 results` |
| VVB verified quantity | ≈ 170 | **the VCU_TOTAL from 11.3 (≈ 950)**, unit `tCO2e` |
| Registry account units | `VER` = 1 `tCO2e` | **`VCU`** = 1 `tCO2e` (a new account, e.g. `ACC-V42-` + tester no.) |
| Registry IDs | `GS-PRJ-` / `GS-SUB-` / `GS-ISS-` | `VCS-PRJ-` / `VCS-SUB-` / `VCS-ISS-` + tester no. |
| Issuance unit / vintage / credits | `VER` / 2026 / 170 | **`VCU`** / `2026` / ≈ 950 |
| Serials | `GS-T01-2026-000001` … | `VCS-T01-2026-000001` … `VCS-T01-2026-000950` |
| Ledger, marketplace, payout values | as written | unchanged (retire 10, transfer 10, sell 20 × ₹500, 60 % farmer share) |

---

## If a step fails
| Code | Fix |
|---|---|
| VM0042 not a candidate (5.1) | Planned start before 21 Oct 2025, or activity not IALM, or version not Approved |
| `METHODOLOGY_REQUIREMENT` (6.1 / 8.1) | Leave the approach empty; design must be Stratified random with ≥ 3 per stratum |
| `OUTSIDE_PLAN_WINDOW` (6.3) | Plan monitoring start must be on or before 1 Nov 2025 |
| `CONTROL_FARM_IN_PROJECT` / `FARM_IS_CONTROL_SITE` | A control farm was added to the project, or the other way round |
| `CONTROL_SITE_NOT_SIMILAR` (6.5) | Texture, soil group or climate differ, or rainfall differs by more than 100 mm |
| Points of the first design disappeared | A second design was generated in the same period — use one design per period |
| `REQUIREMENTS_NOT_MET` on field submit | Probe diameter / number of cores missing, or Collected at outside the period or in the future |
| `INVALID_DEPTH` (8.7) | Sample depths must lie inside the field record's 0–50 cm |
| `UNIT_MISMATCH` (lab QA) | Unit must be exactly `g/kg` or `g` |
| `MISSING_APPROVED_LAB_RESULT` | A field record lacks an approved OC or mass result |
| `PREVIOUS_PERIOD_REQUIRED` | Period 0 dataset not approved |
| `CONTROL_SITES_REQUIRED` / `CONTROL_SITE_REQUIRED` | Fewer than 3 sampled control sites, or none linked to S1 |
| `DEPTH_INCREMENTS_REQUIRED` | Only one sample per field record — register both layers with Depth top / bottom (8.7) |
| `MISSING_REQUIRED_INPUT` · `CORE_DETAILS_MISSING` | A field record has no probe diameter or cores |
| `INVALID_SOIL_PROFILE` | Layers don't start at 0 cm or aren't contiguous (0–30, 30–50) |
| `INSUFFICIENT_SAMPLES` | Fewer than 2 analysed profiles in a stratum and period |
| `MISSING_REQUIRED_INPUT` (NPR) | V42_NPR not recorded in Period 1 |
| ER values are 0 | Farm records in Period 0 instead of Period 1, or project records dated outside Period 1 |
