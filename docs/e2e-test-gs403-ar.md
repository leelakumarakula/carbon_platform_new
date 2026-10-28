# End-to-end test — GS 403 Afforestation / Reforestation (dmrv_db1 · Gold Standard · A/R methodology v2.1 · farm to farmer payout)

This is the complete test of the platform for **Gold Standard Afforestation/Reforestation GHG Emissions Reduction & Sequestration
Methodology v2.1 (GS 403)**: trees planted on degraded land, a **forest inventory** of circular plots measures the stem volume, and
the platform converts it to CO₂ with the Gold Standard factors, minus the baseline stock, leakage and project emissions.

The flow and every value below were **run once end to end on the test database** before this document was written (stages 1–10);
the expected results are the ones the platform produced. Stages 11–15 work exactly as in the VM0042 test.

| | |
|---|---|
| Database | `dmrv_db1` (users and organizations already exist; the Palthope VM0042 project is separate and unaffected) |
| Code | branch `fixes_14/10` (backend and frontend) |
| Password for every user | **`Test@12345678`** |
| Scenario | 🧪 silver oak and teak planted on 01-06-2024 on **≈ 39 ha** of degraded grassland near Siddapura (Kodagu); first inventory 01-10-2026 with **6 plots of 0.04 ha** |
| Expected credits | **625 GS VERs** (415 if the PAA record is left out — negative check) |
| Farmer payout | **₹3,000.00** (60 % of ₹5,000 sales) |

**Markers:** 🔎 negative check (a refusal is a pass) · ⚠ known trap · 🧪 test value · ✍ your own real value.

If you already ran the GS 402.1 test, **Stage 1.1 and 1.3 are done** — only the activity in 1.2 is new.

---

## Part A — How GS 403 differs from the VM0042 / VM0047 tests
| | VM0047 (trees, Verra) | **GS 403 (trees, Gold Standard)** |
|---|---|---|
| Standard / unit | Verra VCS / VCU | **Gold Standard for the Global Goals / GS VER** |
| What is measured | each sampled tree's biomass + a census of all trees | **stem volume per inventory plot** (sum of the trees in a 0.04 ha circle) |
| Conversion | allometric biomass × root-shoot × 0.47 | volume × **BEF** × **wood density** × (1 + **root-shoot**) × **0.47** × 44/12 |
| Laboratory / control farms | none | none |
| Periods | Period 0 census + Period 1 | **one monitoring period** (credits are cumulative; earlier issuance is subtracted) |
| Precision rule | uncertainty deduction | inventory error must be **≤ 20 % at 90 %**; above that the mean volume is reduced |
| Caps | — | creditable stock ≤ growth-model stock and ≤ long-term removal |
| Buffer | Verra risk tool | fixed **20 %** |
| 2026+ vintages | — | need **PAA = YES**, otherwise the 2026 share is not credited |

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
| 1 Catalog | leelak | standard `GS`, activity `AR-GS`, organization **Gold Standard Registry** |
| 2 Methodology | ms1 → ms2 | GS403 `2.1` with module `GS403-V2.1`, approved |
| 3 Farmer | pm → qatester1 → pm | farmer active |
| 4 Farm | pm → gis | Siddapura silver oak plantation (≈ 39 ha) verified |
| 5 Project | pm → gis → qatester1 → pm | eligible, activity confirmed |
| 6 Lock | ms1 → pm | GS403 2.1 locked |
| 7 MRV setup | mrv → qatester1 → mrv → gis | plan, Period 1, management unit MU1 |
| 8 Inventory | gis → sup → gis → sup → col → sup | 6 plots visited and accepted |
| 9 Data | mrv → qatester1 | 19 records, dataset approved |
| 10 Calculation | analyst → qatester1 | **625 GS VERs** |
| 11–15 | same as the VM0042 test | verified → issued → ledger → sold → farmer paid |

---

## Stage 1 — Catalog · LOGIN `leelak`
### 1.1 · **Projects → Standards & activities** → card **Standards / crediting routes** (skip if `GS` already exists)
| Field | Enter |
|---|---|
| Code | **`GS`** (exactly) |
| Name | `Gold Standard for the Global Goals` |
| Programme owner / Type | `Gold Standard Foundation` / Voluntary |
| Official source URL | `https://globalgoals.goldstandard.org` |

**Add standard** → ✔ listed, Active.

### 1.2 · card **Activities**
| Field | Enter |
|---|---|
| Code | **`AR-GS`** (exactly) |
| Name | `Afforestation / reforestation (Gold Standard)` |
| Offered under | tick **Gold Standard for the Global Goals** |

**Add activity** → ✔ "Offered under: Gold Standard for the Global Goals".

### 1.3 · **Administration → Organizations → New** (skip if it already exists)
Code `GSREG` · Name `Gold Standard Registry` · Type **Registry** → ✔ Active (used at Stage 12).

## Stage 2 — Methodology GS403 2.1
### 2.1 · LOGIN `ms1` · Methodologies
| Where | Field | Enter |
|---|---|---|
| Add a methodology | Code | **`GS403`** (exactly) |
| | Name | `Afforestation/Reforestation GHG Emissions Reduction & Sequestration Methodology` |
| | Standard / Activities | Gold Standard for the Global Goals / Afforestation / reforestation (Gold Standard) |
| New version | label | **`2.1`** (exactly) → **New draft version** → **Open** |
| Version details | Effective from | `16-05-2024` (GS 403 v2.1 publication) |
| | Source | `Gold Standard A/R GHG Emissions Reduction & Sequestration Methodology v2.1` → **Save details** |
| Tab **calculation** | module | **GS 403 v2.1 - afforestation / reforestation (inventory stem volume, GS conversion factors) · v1.0.0** → **Use this module** |
| Tab **applicability** | Rule 1 | `A1` · Standard is GS · Standard · `standard_code` · EQUALS · `"GS"` · Not applicable |
| | Rule 2 | `A2` · Activity is AR-GS · Activity · `activity_code` · EQUALS · `"AR-GS"` · Not applicable |

**Submit for approval.** ✔ badge **Module: GS403-V2.1**; 8 calculation rules `GA-BSL` … `GA-NET`; **15 monitoring rules**:

| Level | Codes |
|---|---|
| Sampling point (required) | `GA_PLOT_VOL` — stem volume in the plot (m3) |
| Project (required) | `GA_PLOT_AREA` — plot size (ha) |
| Stratum / management unit | `GA_WD` (t d.m./m3) · `GA_BEF` · `GA_RS` · `GA_CR_LT` (t CO2/ha) · `GA_CR_MODEL` (t CO2/ha) · `GA_MANGROVE_PLANTED` (year) |
| Project | `GA_BSL` (t CO2e) · `GA_BURNING` (YES/NO) · `GA_LK` (t CO2e) · `GA_FERT_N_PRIOR` (kg N) · `GA_ISSUED_PRIOR` (t CO2e) · `GA_PAA` (YES/NO) |
| Farm | `GA_FERT_N` (kg N) |

🔎 **2.2** ms1 clicks **Approve** → refused.
### 2.3 · LOGIN `ms2` → **Approve**. ✔ Approved; "Not production ready" (normal).

## Stage 3 — Farmer
| Step | LOGIN | Enter |
|---|---|---|
| 3.1 | pm | Farmers → **Register farmer**: org `varsapradaya_developer` · Name ✍ (🧪 `Plantation Owner`) · Gender · Language `kn` · Phone ✍ · Village `Siddapura` · District `Kodagu` · State `Karnataka` · `IN` → **Create farmer** → **Register** → KYC: National ID 🧪 `4321 4444 2109` + PDF → **Submit for review** |
| 3.2 🔎 | pm | KYC tab → "another reviewer must decide" |
| 3.3 | qatester1 | KYC → `ID checked` → **Verify KYC** |
| 3.4 | pm | Consent (defaults) → **Record consent** → **Activate** → Agreement `PROGRAM_PARTICIPATION` · `v1` · Effective from **`01-06-2024`** → **Create** → **Upload signed copy** (PDF). Note the code `AGR-2026-…` |

## Stage 4 — Farm (one farm, no control farms)
### 4.1 · LOGIN `pm` → farmer → **Farms → Add farm**
| Field | Enter |
|---|---|
| Farm name | `Siddapura silver oak plantation` |
| Land tenure / Declared area | Owned / `39` |
| Boundary (paste, one per line) | 🧪 `12.3500, 75.8800` / `12.3500, 75.8857` / `12.3557, 75.8857` / `12.3557, 75.8800` (≈ 39.1 ha) — or ✍ the real farm via **FarmFuture** |
| Documents / Ownership | Land record PDF `RTC Sy No 61/4` · Farmer · Owner · 100 % · `RTC Sy. No. 61/4` · `01-01-2020` |

→ **Check boundary** → **Save as new boundary version** → **Submit for review**.

### 4.2 · LOGIN `gis` → Ownership **Verify** → **Start GIS review** → Overlaps empty → **Verify farm**.

The square does not overlap Palthope, the GS 402 farm or the VM0047 farm. The credits scale with the area (≈ 16 VER per hectare here).

## Stage 5 — Project · LOGIN `pm` (then gis, qatester1)
| Field | Enter |
|---|---|
| Name / Type | `Siddapura A/R pilot` / **Other** |
| Country / Region / **Planned start** | `IN` / `Karnataka` / **`01-06-2024`** (on or after the methodology's 16-05-2024) |
| Farms | **Siddapura silver oak plantation** · from `01-06-2024` · Farmer · `Carbon rights clause of AGR-2026-…` · `100` |
| Standard / Activity | Gold Standard for the Global Goals / Afforestation / reforestation (Gold Standard) |
| Crediting period | `01-06-2024` – `31-05-2054` (30 years) |
| Baseline | `01-06-2021` – `31-05-2024` · Practices `Degraded grassland, occasional grazing` · Data sources `Site survey, satellite images` |

**Submit for eligibility review** → **gis**: Boundary → **Accept boundary** → **qatester1**: Carbon rights **Verify** → **Approve eligibility**
→ **pm**: **Confirm activity**. 🔎 pm cannot approve eligibility.

## Stage 6 — Lock
**ms1**: project → **Methodology** → **Evaluate candidates** → **GS403 2.1 Applicable** (A1 ✔ A2 ✔) → **Recommend**.
🔎 ms1 cannot **Confirm & lock**. **pm** → **Confirm & lock** → ✔ Methodology confirmed.

## Stage 7 — MRV setup (MRV → Siddapura A/R pilot)
| Step | LOGIN | Enter | ✔ |
|---|---|---|---|
| 7.1 | mrv | **MRV plans → Create**: frequency `Annual` · Quantification approach **empty** · start `01-06-2024` · end `31-05-2054` · evidence `Inventory sheets, plot photos, GPS` → **Create** → **Submit** | 15 `GA_…` measurements; approach becomes **OTHER** |
| 7.2 | qatester1 | open the plan → **Approve** — acknowledge the gaps (sampling depth, statistical design) | Approved |
| 7.3 | mrv | **Monitoring periods** → `Period 1` · Monitoring · `01-06-2024` – `20-10-2026` → **Mark planned → Start period → Open data collection** | Data collection |
| 7.4 | mrv | **Stratification → New**: Project stratum · `MU1` / `Silver oak and teak` · farm Siddapura silver oak plantation · characteristic LAND_USE `Degraded grassland planted 2024` → **Create** | Draft |
| 7.5 | gis | **Approve** MU1 | Approved |

## Stage 8 — Forest inventory (picker **Period 1**)
### 8.1 · LOGIN `gis` · Sampling design
| Field | Enter |
|---|---|
| Code / Name | `INV-P1` / `Forest inventory` |
| Sample count — MU1 | **`6`** (GS 403 needs at least 2 plots per management unit) |
| Statistical design | **Stratified random** |
| Sampling method | `Circular plots 0.04 ha, DBH and height of every tree` |
| Target precision (%) / Confidence level (%) | **`20`** / **`90`** (the GS 403 rule: ± 20 % at 90 %) |
| Depth top / bottom | `0` / `30` (required by the form; not used for trees) |
| Min. distance (m) | `10` |

→ **Create design** → 8.2 **sup Approve design** → 8.3 **gis Generate sampling points** (✔ 6 points) → 8.4 **sup** assign all 6 to
`colfield_test`, planned date `01-10-2026`.

### 8.5 · Give each plot its key
In **Points & assignments** sort the 6 point codes; the lowest is **P1**, the next **P2** … the highest **P6**.

### 8.6 · LOGIN `col` · field visit on each of the 6 plots
**Field work** → point → **Start collection**: Latitude / Longitude = the planned point (don't click Use my GPS) · **Collected at
`01-10-2026 10:00`** · depth pre-filled · checklist all ticked · photo of the plot → **Save** → **Save & submit**.
### 8.7 · LOGIN `sup` → **Submitted field records** → **Accept** all 6.

⚠ Every plot needs an **accepted** field visit, otherwise dataset QA fails ("SP-… has no accepted collection").

## Stage 9 — Monitoring data · LOGIN `mrv` · tab **Monitoring data** — 19 records
Source **Document**, Observed on **`01-10-2026`**, Phase **Monitoring** unless stated.

### 9.1 · Per plot (Measurement level **Sampling point** → choose the point)
| Plot | GA_PLOT_VOL (m3 in the plot) | = m3/ha (÷ 0.04) |
|---|---|---|
| P1 | 🧪 `0.82` | 20.50 |
| P2 | 🧪 `0.76` | 19.00 |
| P3 | 🧪 `0.91` | 22.75 |
| P4 | 🧪 `0.70` | 17.50 |
| P5 | 🧪 `0.85` | 21.25 |
| P6 | 🧪 `0.79` | 19.75 |

Plot volume in real use = sum of the stem volumes of every tree in the plot (from DBH and height with the species' volume equation).

### 9.2 · Management unit (Measurement level **Stratum** → **MU1**)
| Measurement | Value | Meaning |
|---|---|---|
| GA_WD | 🧪 `0.55` | wood density, t dry matter per m3 (default 0.3 if not recorded) |
| GA_BEF | `1.1` | biomass expansion factor (GS default) |
| GA_RS | `0.2` | root-to-shoot ratio (GS default) |
| GA_CR_LT | 🧪 `300` | long-term CO2 removal from the growth model, t CO2/ha (cap) |
| GA_CR_MODEL | 🧪 `30` | growth-model CO2 stock at this inventory date, t CO2/ha (cap) |

### 9.3 · Project (Measurement level **Project**)
| Measurement | Value | Meaning |
|---|---|---|
| GA_PLOT_AREA | `0.04` | plot size in ha (required) |
| GA_BSL | 🧪 `150` | baseline stock of the planting area (grass, shrubs), t CO2e |
| GA_BURNING | `NO` | no burning for site preparation (YES would deduct 10 % of the baseline) |
| GA_LK | 🧪 `50` | leakage for the crediting period, t CO2e |
| GA_FERT_N_PRIOR | `0` | fertiliser N in earlier periods (first period) |
| GA_ISSUED_PRIOR | `0` | units already issued (first issuance) |
| GA_PAA | **`YES`** | the period runs into 2026; without it the 2026 share is not credited |

### 9.4 · Farm (Measurement level **Farm** → Siddapura silver oak plantation)
| Measurement | Phase | Observed on | Value |
|---|---|---|---|
| GA_FERT_N (kg N) | **Project** | `01-07-2025` | 🧪 `400` |

Total **19 records** (6 + 5 + 7 + 1).

### 9.5 · mrv → **Datasets & QA** → Period 1 → **Create dataset version** → **Open / QA** → **Submit for QA**.
### 9.6 · qatester1 → **Start QA review** → all PASS except **one WARN "configuration"** (sampling depth, statistical design — normal for
trees) → PASS → **Record QA result** → **Approve dataset**.

## Stage 10 — Calculation · LOGIN `analyst`
**Calculations** → project · **Period 1** → **New calculation run** → **Check readiness & freeze inputs** (✔ Inputs frozen) → **Execute**
(✔ Calculated).

| Output | Meaning | Expected |
|---|---|---|
| BASELINE | GA_BSL | **150.0000 t CO2e** |
| V_MEAN_… | mean plot volume per hectare (6 plots) | **20.1250 m3/ha** |
| INVENTORY_ERROR_MAX | t(90 %) × standard error / mean | **0.0745** (7.45 % ≤ 20 % → no reduction) |
| STOCK_… | 20.125 × BEF 1.1 × WD 0.55 × (1 + 0.2) × 0.47 × 44/12 | **25.1792 t CO2/ha** |
| CREDITABLE_… | lowest of stock 25.18, model 30, long-term 300 | **25.1792 t CO2/ha** |
| CR_STOCK | 25.1792 × 39.0903 ha | **984.2622 t CO2e** |
| CR_MANGROVE_SOC | not a mangrove | **0** |
| OE_BURN | GA_BURNING = NO | **0** |
| OE_FERT | 400 kg N × 0.005 t CO2/kg N | **2.0000** |
| LEAKAGE | GA_LK | **50.0000** |
| NET_CUMULATIVE | 984.26 − 150 − 50 − 0 − 2 | **782.2622** |
| ISSUABLE | − units issued before (0) | **782.2622** |
| PAA_BLOCKED_SHARE | PAA = YES | **0** |
| BUFFER | 20 % | **156.4524** |
| GSVER_ELIGIBLE | | **782.2622** |
| **GSVER_PROJECT** | 782.26 − 156.45, whole tonnes, rounded down | **625** |

🔎 **10.1** analyst cannot **Approve**. **qatester1**: run → **QA** → **Start calculation QA** → PASS → **Record QA** → **Approve**.
✔ run **Approved**, project **Calculated**.

🔎 **10.2 (optional)** Without the `GA_PAA = YES` record: PAA_BLOCKED_SHARE **0.3360** (293 of 872 days fall in 2026), GSVER_ELIGIBLE
519.4149, BUFFER 103.8830 → **415 GS VERs**.

**Next period:** GS 403 credits are cumulative. In the next period record the new inventory and **`GA_ISSUED_PRIOR` = the units issued so
far before buffer** (here `782`) and **`GA_FERT_N_PRIOR` = `400`**, so only the growth since the last issuance is credited.

## Stages 11–15 — Verification, registry, ledger, marketplace, payout
Exactly as in the VM0042 test document (`docs/e2e-test-palthope-vm0042.md`, Stages 14–18), with these changes:

| Stage | Change |
|---|---|
| 11 Verification | finding text `Inventory plots and volume equations`; VVB quantity **`625`** · unit `tCO2e`; Verification tab picker on **Period 1** |
| 12 Registry | account: Registry **Gold Standard Registry** · Account ID `GS-ACC-002` (or reuse `GS-ACC-001` from the GS 402 test) · credit unit **`VER`** = **`tCO2e`**; registration `GS-PRJ-002`; submission `GS-SUB-002`; issuance `GS-ISS-002` · Unit **`VER`** · vintage `2026` · **625** credits · serials `GS-2026-000018` – `GS-2026-000642` (after the GS 402 batch; `GS-2026-000001` – `000625` if that test was not done); 🔎 **626** → `QUANTITY_EXCEEDS_VERIFIED` |
| 13 Ledger | retire 5 · transfer 5 to the buyer · buyer retires 2 → **615** available |
| 14 Marketplace | listing 100 credits · ₹500 · max order 20 · buyer orders **10** = **₹5,000** |
| 15 Payout | 60 % → **₹3,000** to the farmer · allocation farm **Siddapura silver oak plantation 100 %** · bank details 🧪 |

⚠ Registry serial numbers must be unique per registry: start after the last serial already used at the Gold Standard Registry.

---

## Part D — Where every value comes from
| Value | Source | Why |
|---|---|---|
| Code GS403, version 2.1, date 16-05-2024, CF 0.47, defaults WD 0.3 / BEF 1.1 / RS 0.2, ± 20 % at 90 %, fertiliser 0.005 t CO2/kg N, burning 10 %, buffer 20 % | ⚙ Gold Standard A/R methodology v2.1 + GHG ER&S Product Requirements | the methodology |
| Plot size 0.04 ha, 6 plots | 🧪 — ✍ real: the project's inventory design (at least 2 plots per MU, enough for ± 20 %) | sample |
| Plot stem volumes | 🧪 — ✍ real: DBH and height of every tree × species volume equation | carbon stock |
| Wood density 0.55 | 🧪 — ✍ real: species value from literature / the Global Wood Density Database | conversion |
| Long-term removal 300, model stock 30 | 🧪 — ✍ real: the growth model in the certified project design | caps |
| Baseline stock 150, leakage 50 | 🧪 — ✍ real: baseline survey and leakage assessment in the project design | deductions |
| Fertiliser 400 kg N | 🧪 — ✍ real: nursery and planting records | project emissions |
| PAA = YES | 🧪 — ✍ real: only after Gold Standard approves the PAA status | 2026+ vintages |
| Farm boundary, farmer | ✍ / 🧪 | project area |

## Part E — Errors you may see
| Code / message | Fix |
|---|---|
| `CONFIGURATION_REQUIRED` on plan approval | acknowledge the gaps in the approval dialog |
| "depth_bottom_cm must be greater than depth_top_cm" | design depth `0` / `30` |
| "SP-… has no accepted collection" | each plot needs a field visit accepted by sup (8.6–8.7) |
| Dataset QA missing records for `GA_PLOT_VOL` | one volume record per generated plot |
| `INSUFFICIENT_SAMPLES` "MU … has 1 inventory plot; at least 2 are needed" | more plots in the design |
| `MISSING_REQUIRED_INPUT` "The inventory plot size (GA_PLOT_AREA) is needed" | record `GA_PLOT_AREA` at project level |
| Credits lower than expected, INVENTORY_ERROR_MAX > 0.20 | plots vary too much — the mean volume is reduced by the excess error; add plots |
| CREDITABLE_… lower than STOCK_… | the growth-model cap `GA_CR_MODEL` or `GA_CR_LT` is limiting (by design) |
| Credits ≈ 34 % lower than expected | `GA_PAA = YES` missing (2026 share blocked) |
| Module list does not show GS403-V2.1 | methodology code must be **`GS403`** and version label **`2.1`** |
