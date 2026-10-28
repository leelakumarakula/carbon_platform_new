# End-to-end test — VM0047 tree planting (dmrv_db1 · Verra VCS · VM0047 v1.1 census-based · farm to farmer payout)

This is the complete test of the platform for **Verra VM0047 v1.1 — Afforestation, Reforestation and Revegetation (ARR), census-based
approach**: trees planted on farmland, all planted trees counted (census), a sample of trees measured, credits for the woody carbon.

The flow and every value below were **run once end to end on the test database** before this document was written (stages 2–13); the
expected result is the one the platform produced.

| | |
|---|---|
| Database | `dmrv_db1` (VCS, users and organizations already exist; the Palthope VM0042 project is separate and unaffected) |
| Code | branch `fixes_14/10` (backend and frontend) |
| Password for every user | **`Test@12345678`** |
| Scenario | 🧪 a farmer plants **1,800 Melia dubia** seedlings on a **≈ 39 ha** farm near Hunsur on 01-06-2025 (≤ 50 trees per hectare) |
| Expected credits | **63 VCUs** |
| Farmer payout | **₹3,000.00** (60 % of ₹5,000 sales) |

**Markers:** 🔎 negative check (a refusal is a pass) · ⚠ known trap · 🧪 test value · ✍ your own real value.

---

## Part A — How VM0047 differs from the VM0042 test
| | VM0042 (soil) | **VM0047 (trees)** |
|---|---|---|
| What is measured | soil carbon by a laboratory | **trees**: how many were planted, and alive / dead + biomass of sampled trees |
| Laboratory | yes | **no** (Stage 9 is skipped) |
| Control farms | 3 | **none** (the baseline is zero) |
| Sampling | soil cores, 2 depth layers | **12 sampled trees**, each with a field visit (GPS, date, photo) |
| Data entry | lab results | **Monitoring data** records at stratum, sampling-point, farm and project level |
| Periods | baseline + monitoring | **Period 0 = planting census**, **Period 1 = first tree measurement** |
| Key rule | — | **at most 50 trees per hectare** (`DENSITY_EXCEEDED`) |

## Part B — Users
| Login | Role |
|---|---|
| leelak@vayublue.com | Platform Admin |
| ms1@ / ms2@ | Methodology Specialist (author / approver) |
| pm@ · qatester1@ · gis@ · mrv@ · sup@ · col@ · analyst@ | Project Manager · QA · GIS · MRV Manager · Supervisor · Collector · Analyst (varsapradaya_developer) |
| credits@ · fin1@ · fin2@ · fin3@ | Credit Manager · Finance ×3 |
| vvb@ · buyer@ · compliance@ | VVB · Buyer · Marketplace Compliance |

## Part C — The flow at a glance
| Stage | Logins | Result |
|---|---|---|
| 1 Catalog | leelak | activity `ARR` under VCS |
| 2 Methodology | ms1 → ms2 | VM0047 1.1 with module `VM0047-V1.1-CENSUS`, approved |
| 3 Farmer | pm → qatester1 → pm | farmer active |
| 4 Farm | pm → gis | Hunsur Melia block (≈ 39 ha) verified |
| 5 Project | pm → gis → qatester1 → pm | eligible, activity selected |
| 6 Lock | ms1 → pm | VM0047 1.1 locked |
| 7 MRV setup | mrv → qatester1 → mrv → gis → sup | plan, 2 periods, stratum S1 |
| 8 Period 0 census | mrv → qatester1 | 1,800 trees recorded, dataset approved |
| 9 Period 1 sample | gis → sup → gis → sup → col → sup → mrv → qatester1 | 12 trees measured, dataset approved |
| 10 Calculation | analyst → qatester1 | **63 VCUs** |
| 11–15 | same as the VM0042 test | verified → issued → ledger → sold → farmer paid |

---

## Stage 1 — Catalog · LOGIN `leelak`
**Projects → Standards & activities** → card **Activities**:

| Field | Enter |
|---|---|
| Code | `ARR` |
| Name | `Afforestation, reforestation and revegetation` |
| Offered under | tick **Verified Carbon Standard** (already exists) |

**Add activity** → ✔ "Offered under: Verified Carbon Standard".

## Stage 2 — Methodology VM0047 1.1
### 2.1 · LOGIN `ms1` · Methodologies
| Where | Field | Enter |
|---|---|---|
| Add a methodology | Code | **`VM0047`** (exactly) |
| | Name | `Afforestation, Reforestation and Revegetation` |
| | Standard / Activities | Verified Carbon Standard / Afforestation, reforestation and revegetation |
| New version | label | **`1.1`** (exactly) → **New draft version** → **Open** |
| Version details | Effective from | `14-05-2025` (VM0047 v1.1 date) |
| | Source | `Verra VM0047 v1.1` → **Save details** |
| Tab **calculation** | module | **VM0047 v1.1 - census-based approach (planting units on farmland, <= 50 …) · v1.0.0** → **Use this module** |
| Tab **applicability** | Rule 1 | `A1` · Standard is VCS · Standard · `standard_code` · EQUALS · `"VCS"` · Not applicable |
| | Rule 2 | `A2` · Activity is ARR · Activity · `activity_code` · EQUALS · `"ARR"` · Not applicable |

**Submit for approval.** ✔ badge **Module: VM0047-V1.1-CENSUS**; 8 calculation rules `V47-BSL` … `V47-NET`; **8 monitoring rules**:
`V47_N` (units, stratum) · `V47_ALIVE` (flag, sampling point) · `V47_AGB` (kg d.m., sampling point) · `V47_BURNED` (flag, sampling point) ·
`V47_FSN` · `V47_FON` (kg N, farm) · `V47_ROOT_SHOOT` (ratio, project) · `V47_NPR` (%, project).

🔎 **2.2** ms1 clicks **Approve** → refused.
### 2.3 · LOGIN `ms2` → **Approve**. ✔ Approved; "Not production ready" (normal).

## Stage 3 — Farmer
| Step | LOGIN | Enter |
|---|---|---|
| 3.1 | pm | Farmers → **Register farmer**: org `varsapradaya_developer` · Name ✍ (🧪 `Ramesh Gowda`) · Gender · Language `kn` · Phone ✍ · Village `Hunsur` · District `Mysuru` · State `Karnataka` · `IN` → **Create farmer** → **Register** → KYC: National ID 🧪 `1234 5678 9021` + PDF → **Submit for review** |
| 3.2 🔎 | pm | KYC tab → "another reviewer must decide" |
| 3.3 | qatester1 | KYC → `ID checked` → **Verify KYC** |
| 3.4 | pm | Consent (defaults) → **Record consent** → **Activate** → Agreement `PROGRAM_PARTICIPATION` · `v1` · Effective from **`01-06-2025`** → **Create** → **Upload signed copy** (PDF). Note the code `AGR-2026-…` |

## Stage 4 — Farm (one farm, no control farms)
### 4.1 · LOGIN `pm` → farmer → **Farms → Add farm**
| Field | Enter |
|---|---|
| Farm name | `Hunsur Melia block` |
| Land tenure / Declared area | Owned / `39` |
| Boundary (paste, one per line) | 🧪 `12.3100, 76.2900` / `12.3100, 76.2957` / `12.3157, 76.2957` / `12.3157, 76.2900` (≈ 39 ha) — or ✍ the real farm via **FarmFuture** |
| Documents / Ownership | Land record PDF `RTC Hunsur Melia block` · Farmer · Owner · 100 % · `Sy No 88/1` · `01-01-2020` |

→ **Check boundary** → **Save as new boundary version** → **Submit for review**.

⚠ **The farm must be at least 36 ha** for 1,800 trees (VM0047 allows at most 50 trees per hectare). With a smaller real farm, record
fewer trees in Stages 8 and 9: **trees ≤ 50 × hectares**.

### 4.2 · LOGIN `gis` → Ownership **Verify** → **Start GIS review** → Overlaps empty → **Verify farm**.

## Stage 5 — Project · LOGIN `pm` (then gis, qatester1)
| Field | Enter |
|---|---|
| Name / Type | `Hunsur Melia dubia ARR pilot` / **Agroforestry** |
| Country / Region / **Planned start** | `IN` / `Hunsur` / **`01-06-2025`** (on or after the methodology's 14-05-2025) |
| Farms | **Hunsur Melia block** · from `01-06-2025` · Farmer · `Carbon rights clause of AGR-2026-…` · `100` |
| Standard / Activity | Verified Carbon Standard / Afforestation, reforestation and revegetation |
| Crediting period | `01-06-2025` – `31-05-2045` |
| Baseline | `01-06-2022` – `31-05-2025` · Practices `Annual crops, no trees` · Data sources `Farmer records` |

**Submit for eligibility review** → **gis**: Boundary → **Accept boundary** → **qatester1**: Carbon rights **Verify** → **Approve eligibility**
→ **pm**: **Confirm activity**. 🔎 pm cannot approve eligibility.

## Stage 6 — Lock
**ms1**: project → **Methodology** → **Evaluate candidates** → **VM0047 1.1 Applicable** (A1 ✔ A2 ✔) → **Recommend**.
🔎 ms1 cannot **Confirm & lock**. **pm** → **Confirm & lock** → ✔ Methodology confirmed.

## Stage 7 — MRV setup (MRV → Hunsur Melia dubia ARR pilot)
| Step | LOGIN | Enter | ✔ |
|---|---|---|---|
| 7.1 | mrv | **MRV plans → Create**: frequency `Annual` · Quantification approach **empty** · start `01-06-2025` · end `31-05-2045` · evidence `Field photos, GPS, tree measurements` → **Create** → **Submit** | 8 `V47_…` measurements; approach becomes **OTHER** |
| 7.2 | qatester1 | open the plan → **Approve** (the dialog lists the sampling-depth gap — acknowledge it) | Approved |
| 7.3 | mrv | **Monitoring periods** → `Period 0 planting census` · Baseline · `01-06-2025` – `31-08-2025`; `Period 1` · Monitoring · `01-09-2025` – `20-10-2026` → on both **Mark planned → Start period → Open data collection** | both Data collection |
| 7.4 | gis | **Stratification → New**: Project stratum · `S1` / `Melia dubia block` · farm Hunsur Melia block · characteristic LAND_USE `Cropland with tree rows` → **Create** | Draft |
| 7.5 | sup | **Approve** S1 | Approved |

No control sites and **no laboratory engagement** for VM0047.

## Stage 8 — Period 0: planting census (picker **Period 0 planting census**)
### 8.1 · LOGIN `mrv` · tab **Monitoring data** — 3 records
| # | Measurement | Level / where | Value | Observed on | Phase | Source |
|---|---|---|---|---|---|---|
| 1 | V47_N · planting units in the census | Stratum **S1** | 🧪 `1800` | `15-07-2025` | Monitoring | Document |
| 2 | V47_ROOT_SHOOT · root-to-shoot ratio | project | 🧪 `0.25` | `15-07-2025` | Monitoring | Document |
| 3 | V47_NPR · risk rating (%) | project | 🧪 `15` | `15-07-2025` | Monitoring | Document |

⚠ Rows 2 and 3 are required in **every** period — without them the dataset QA fails ("V47_NPR / V47_ROOT_SHOOT missing for the project").

### 8.2 · mrv → **Datasets & QA** → Period 0 → **Create dataset version** → **Open / QA** → **Submit for QA**.
### 8.3 · qatester1 → **Start QA review** (PASS; one WARN for sampling depth is normal) → PASS → **Record QA result** → **Approve dataset**.

## Stage 9 — Period 1: tree sample (picker **Period 1**)
### 9.1 · LOGIN `gis` · Sampling design
| Field | Enter |
|---|---|
| Code / Name | `TREES-P1` / `Planting-unit sample` |
| Sample count — S1 | **`12`** |
| Statistical design | **Systematic grid** (required by VM0047) |
| Sampling method | `Measure DBH and height of the sampled planting units` |
| Depth top / bottom | `0` / `30` (required by the form; not used for trees) |
| Min. distance (m) | `10` |

→ **Create design** → 9.2 **sup Approve design** → 9.3 **gis Generate sampling points** (✔ 12 points) → 9.4 **sup** assign all 12 to
`colfield_test`, planned date `01-10-2026`.

### 9.5 · Give each sampled tree its key
In **Points & assignments** sort the 12 point codes; the lowest is **T1**, the next **T2** … the highest **T12**.

### 9.6 · LOGIN `col` · field visit on each of the 12 trees
**Field work** → point → **Start collection**: Latitude / Longitude = the planned point (don't click Use my GPS) · **Collected at
`01-10-2026 10:00`** · depth pre-filled · checklist all ticked · photo of the tree → **Save** → **Save & submit**.
### 9.7 · LOGIN `sup` → **Submitted field records** → **Accept** all 12.

⚠ Every sampled tree needs an **accepted** field visit, otherwise dataset QA fails ("SP-… has no accepted collection").

### 9.8 · LOGIN `mrv` · tab **Monitoring data** — 41 records (12 trees × 3 + 5) (Source Document, Observed on `01-10-2026` unless stated)

**Per sampled tree** (Measurement level *sampling point* → choose the point in the **Sampling point** box):

| Tree | V47_ALIVE (1 alive / 0 dead) | V47_AGB (kg dry matter) | V47_BURNED (1 / 0) |
|---|---|---|---|
| T1 | `1` | `24.5` | `0` |
| T2 | `1` | `31.0` | `0` |
| T3 | `0` | `0` (dead) | `0` |
| T4 | `1` | `27.8` | `0` |
| T5 | `1` | `22.6` | `0` |
| T6 | `1` | `35.4` | `0` |
| T7 | `1` | `29.1` | `0` |
| T8 | `0` | `0` (dead) | `0` |
| T9 | `1` | `26.3` | `0` |
| T10 | `1` | `33.7` | `0` |
| T11 | `1` | `21.9` | `0` |
| T12 | `1` | `28.4` | `0` |

**Other records:**
| Measurement | Level | Value | Observed on | Phase |
|---|---|---|---|---|
| V47_N | Stratum S1 | `1800` | `01-10-2026` | Monitoring |
| V47_FSN · synthetic fertiliser N (kg N) | Farm Hunsur Melia block | 🧪 `120` | `01-10-2025` | Project |
| V47_FON · organic fertiliser N (kg N) | Farm Hunsur Melia block | 🧪 `40` | `01-10-2025` | Project |
| V47_ROOT_SHOOT | project | `0.25` | `01-10-2026` | Monitoring |
| V47_NPR | project | `15` | `01-10-2026` | Monitoring |

⚠ A dead tree still needs **V47_AGB = `0`** (QA fails otherwise: "V47_AGB missing for SP-…"). The calculation averages live trees only.
Biomass in real use comes from the species' allometric equation (DBH, height) — here 🧪 test values for 16-month Melia dubia.

### 9.9 · mrv → **Datasets & QA** → Period 1 → create → **Submit for QA** · 9.10 · qatester1 → QA PASS → **Approve dataset**.

## Stage 10 — Calculation · LOGIN `analyst`
**Calculations** → project · **Period 1** → **New calculation run** → **Check readiness & freeze inputs** → **Execute**.

| Output | Meaning | Expected |
|---|---|---|
| MORTALITY_… | dead share of the sample (2 of 12) | **0.1667** |
| C_PU_AVG_… | carbon per live tree: mean biomass 28.07 kg × (1 + 0.25) × 0.47 | **0.0165 t C** |
| C_WOODY_… | 1,800 × (1 − 0.1667) × 0.0165 | **24.74 t C** |
| DC_WP_T | woody carbon as CO₂ (× 44/12) | **90.70 t CO₂e** |
| DC_WP_T_X | stock at the census (no earlier biomass) | **0** |
| PE_FERT / PE_BURN | fertiliser N₂O / burning | **0.93** / 0 |
| UNC_T | sampling + mortality uncertainty (90 %) | **15.91 %** |
| STOCK_CHANGE_ADJ | 90.70 × (1 − 0.159) | **76.27** |
| CR_T | removals (− fertiliser) | **75.34** |
| BUFFER | 15 % of the stock change (minimum 12 %) | **11.44** |
| NET_REMOVALS | | **63.90** |
| **VCU_TOTAL** | whole tonnes, rounded down | **63** |

🔎 analyst cannot **Approve**. **qatester1**: run → **QA** → **Start calculation QA** → PASS → **Record QA** → **Approve**.
✔ run **Approved**, project **Calculated**.

## Stages 11–15 — Verification, registry, ledger, marketplace, payout
Exactly as in the VM0042 test document (`docs/e2e-test-palthope-vm0042.md`, Stages 14–18), with these numbers:

| Stage | Change |
|---|---|
| 11 Verification | finding text `Allometric equation and tree count`; VVB quantity **`63`** · unit `tCO2e`; the Verification tab picker on **Period 1** |
| 12 Registry | issuance **63** VCU · vintage `2026` · serials `VCS-2026-000001` – `VCS-2026-000063` (use the next free numbers if Palthope's batch already used them, e.g. `VCS-2026-000062` – `VCS-2026-000124`); 🔎 **64** → `QUANTITY_EXCEEDS_VERIFIED` |
| 13 Ledger | retire 5 · transfer 5 to the buyer · buyer retires 2 → **53** available |
| 14 Marketplace | listing 40 credits · ₹500 · max order 20 · buyer orders **10** = **₹5,000** |
| 15 Payout | 60 % → **₹3,000** to the farmer · allocation farm **Hunsur Melia block 100 %** · bank details 🧪 · settlement period dropdown "Period 2" = Period 1 |

⚠ Registry serial numbers must be unique per registry: if Palthope's batch already holds `VCS-2026-000001`–`000061`, start this one after it.

---

## Part D — Where every value comes from
| Value | Source | Why |
|---|---|---|
| Methodology code, version 1.1, date 14-05-2025, ≤ 50 trees/ha, CF 0.47, buffer ≥ 12 % | ⚙ Verra VM0047 v1.1 | the methodology |
| Tree count 1,800, planting 01-06-2025 | 🧪 | census of planted units |
| 12 sampled trees: alive/dead, biomass | 🧪 (real: tree measurements + allometric equation) | stock of the live trees and mortality |
| Root-to-shoot 0.25 | 🧪 (real: IPCC 2019 Table 4.4 for the species / ecozone) | below-ground biomass |
| Fertiliser 120 / 40 kg N | 🧪 (real: farm records) | project emissions |
| Risk rating 15 % | 🧪 (real: Verra AFOLU risk tool, minimum 12) | buffer |
| Farm boundary, farmer | ✍ / 🧪 | project area |

## Part E — Errors you may see
| Code / message | Fix |
|---|---|
| "V47_NPR / V47_ROOT_SHOOT missing for the project" | record both in **every** period (8.1, 9.8) |
| "SP-… has no accepted collection" | each sampled tree needs a field visit accepted by sup (9.6–9.7) |
| "V47_AGB missing for SP-…" | dead tree → AGB `0` |
| `DENSITY_EXCEEDED` | more than 50 trees per hectare: bigger farm or fewer trees |
| `INSUFFICIENT_SAMPLES` | too few live sampled trees |
| "depth_bottom_cm must be greater than depth_top_cm" | design depth `0` / `30` |
| `CONFIGURATION_REQUIRED` on plan approval | acknowledge the gaps in the approval dialog |
