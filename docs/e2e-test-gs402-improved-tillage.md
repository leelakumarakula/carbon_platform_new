# End-to-end test — GS 402.1 Improved Tillage (dmrv_db1 · Gold Standard · SOC Framework v1.0, Approach 3 IPCC factors · farm to farmer payout)

This is the complete test of the platform for **Gold Standard SOC Framework Methodology v1.0 (GS 402) with Activity Module 402.1 Improved
Tillage**, quantified with **Approach 3**: the soil-carbon change is **modelled from IPCC stock change factors** (no soil sampling, no
laboratory). A farmer moves from full tillage with residues burnt/removed to **reduced tillage with residues kept**.

The flow and every value below were **run once end to end on the test database** before this document was written (stages 1–10);
the expected results are the ones the platform produced. Stages 11–15 work exactly as in the VM0042 test.

| | |
|---|---|
| Database | `dmrv_db1` (users and organizations already exist; the Palthope VM0042 project is separate and unaffected) |
| Code | branch `fixes_14/10` (backend and frontend) |
| Password for every user | **`Test@12345678`** |
| Scenario | 🧪 a **≈ 97.5 ha** maize farm near Gonikoppal (Kodagu) switches to reduced tillage + residue retention on 01-06-2025; first monitoring year 01-06-2025 – 31-05-2026 |
| Expected credits | **17 GS VERs** (10 if the PAA record is left out — negative check) |
| Farmer payout | **₹1,500.00** (60 % of ₹2,500 sales) |

**Markers:** 🔎 negative check (a refusal is a pass) · ⚠ known trap · 🧪 test value · ✍ your own real value.

---

## Part A — How GS 402.1 (Approach 3) differs from the VM0042 test
| | VM0042 (soil, Verra) | **GS 402.1 Approach 3 (Gold Standard)** |
|---|---|---|
| Standard / unit | Verra VCS / VCU | **Gold Standard for the Global Goals / GS VER** |
| How SOC change is found | soil samples + laboratory | **IPCC model**: SOC_REF × factors for land use, tillage and inputs (GS 402 Eqs. 4 and 6) |
| Laboratory / sampling design / field visits | yes | **none** (no Stage for lab, design or field work) |
| Control farms | 3 | **none** |
| Periods | baseline + monitoring | **one monitoring period** (no earlier period needed) |
| Data entry | lab results | **Monitoring data** records: 14 per stratum, fertiliser/diesel per farm, 2 per project |
| Uncertainty | sample statistics | each IPCC factor ± its published uncertainty; deduction = uncertainty above 20 % |
| Buffer | Verra AFOLU risk tool | fixed **20 %** (GS GHG ER&S Product Requirements) |
| 2026+ vintages | — | need **Paris Agreement alignment (PAA = YES)**, otherwise the 2026 share is not credited |

## Part B — Users
| Login | Role |
|---|---|
| leelak@vayublue.com | Platform Admin |
| ms1@ / ms2@ | Methodology Specialist (author / approver) |
| pm@ · qatester1@ · gis@ · mrv@ · analyst@ | Project Manager · QA · GIS · MRV Manager · Analyst (varsapradaya_developer) |
| credits@ · fin1@ · fin2@ · fin3@ | Credit Manager · Finance ×3 |
| vvb@ · buyer@ · compliance@ | VVB · Buyer · Marketplace Compliance |

`sup@` and `col@` are **not needed** (no field work in Approach 3).

## Part C — The flow at a glance
| Stage | Logins | Result |
|---|---|---|
| 1 Catalog | leelak | standard `GS`, activity `AGR-SOC`, organization **Gold Standard Registry** |
| 2 Methodology | ms1 → ms2 | GS402 `1.0-IT-A3` with module `GS402-IT-A3`, approved |
| 3 Farmer | pm → qatester1 → pm | farmer active |
| 4 Farm | pm → gis | Gonikoppal maize block (≈ 97.5 ha) verified |
| 5 Project | pm → gis → qatester1 → pm | eligible, activity confirmed |
| 6 Lock | ms1 → pm | GS402 1.0-IT-A3 locked |
| 7 MRV setup | mrv → qatester1 → mrv → gis | plan, Period 1, stratum S1 |
| 8 Data | mrv → qatester1 | 28 records, dataset approved |
| 9 Calculation | analyst → qatester1 | **17 GS VERs** |
| 10–14 | same as the VM0042 test | verified → issued → ledger → sold → farmer paid |

---

## Stage 1 — Catalog · LOGIN `leelak`
### 1.1 · **Projects → Standards & activities** → card **Standards / crediting routes** (skip if `GS` already exists)
| Field | Enter |
|---|---|
| Code | **`GS`** (exactly — the applicability rule checks it) |
| Name | `Gold Standard for the Global Goals` |
| Programme owner | `Gold Standard Foundation` |
| Type | Voluntary |
| Official source URL | `https://globalgoals.goldstandard.org` |

**Add standard** → ✔ listed, Active.

### 1.2 · card **Activities**
| Field | Enter |
|---|---|
| Code | **`AGR-SOC`** (exactly) |
| Name | `Agriculture - soil organic carbon` |
| Offered under | tick **Gold Standard for the Global Goals** |

**Add activity** → ✔ "Offered under: Gold Standard for the Global Goals".

### 1.3 · **Administration → Organizations → New** (skip if it already exists)
| Field | Enter |
|---|---|
| Code / Name | `GSREG` / `Gold Standard Registry` |
| Type | **Registry** |

✔ Active. (Needed only at Stage 11 — Gold Standard credits are issued at the Gold Standard Impact Registry, not at Verra.)

## Stage 2 — Methodology GS402 1.0-IT-A3
### 2.1 · LOGIN `ms1` · Methodologies
| Where | Field | Enter |
|---|---|---|
| Add a methodology | Code | **`GS402`** (exactly) |
| | Name | `Soil Organic Carbon Framework Methodology` |
| | Standard / Activities | Gold Standard for the Global Goals / Agriculture - soil organic carbon |
| New version | label | **`1.0-IT-A3`** (exactly) → **New draft version** → **Open** |
| Version details | Effective from | `01-01-2020` (GS 402 v1.0 publication) |
| | Source | `Gold Standard SOC Framework Methodology v1.0 + Activity Module 402.1 Improved Tillage` → **Save details** |
| Tab **calculation** | module | **GS 402 + 402.1 Improved Tillage - Approach 3 (IPCC stock change factors, Eqs. 4 and 6) · v1.0.0** → **Use this module** |
| Tab **applicability** | Rule 1 | `A1` · Standard is GS · Standard · `standard_code` · EQUALS · `"GS"` · Not applicable |
| | Rule 2 | `A2` · Activity is AGR-SOC · Activity · `activity_code` · EQUALS · `"AGR-SOC"` · Not applicable |

The module list also offers ZT-A1, IT-A1, CC-A1 and CC-A3 — pick **IT-A3** only.

**Submit for approval.** ✔ badge **Module: GS402-IT-A3**; 8 calculation rules `GS-BSL` … `GS-NET`; **25 monitoring rules**:

| Level | Codes |
|---|---|
| Stratum (required) | `GS_SOC_REF` (t C/ha) · `GS_F_LU` · `GS_F_MG_BL` · `GS_F_I_BL` · `GS_F_MG_PR` · `GS_F_I_PR` (factors) · `GS_T_BL` · `GS_T_PR` (yr) |
| Stratum (uncertainty, %) | `GS_U_SOC_REF` · `GS_U_F_LU` · `GS_U_F_MG_BL` · `GS_U_F_I_BL` · `GS_U_F_MG_PR` · `GS_U_F_I_PR` |
| Farm | `GS_FERT_N` (kg N) · `GS_DIESEL` · `GS_GASOLINE` (L) · `GS_ELECTRICITY` (kWh) · `GS_AGROCHEM` (t CO2e) · `GS_YIELD` (kg/ha) |
| Project | `GS_FEF_DIESEL` · `GS_FEF_GASOLINE` (t CO2e/L) · `GS_EEF` (t CO2e/kWh) · `GS_LK_EF` (t CO2e/ha) · `GS_PAA` (YES/NO) |

🔎 **2.2** ms1 clicks **Approve** → refused (author cannot approve).
### 2.3 · LOGIN `ms2` → **Approve**. ✔ Approved; "Not production ready" (normal).

## Stage 3 — Farmer
| Step | LOGIN | Enter |
|---|---|---|
| 3.1 | pm | Farmers → **Register farmer**: org `varsapradaya_developer` · Name ✍ (🧪 `Tillage Farmer`) · Gender · Language `kn` · Phone ✍ · Village `Gonikoppal` · District `Kodagu` · State `Karnataka` · `IN` → **Create farmer** → **Register** → KYC: National ID 🧪 `4321 3333 2109` + PDF → **Submit for review** |
| 3.2 🔎 | pm | KYC tab → "another reviewer must decide" |
| 3.3 | qatester1 | KYC → `ID checked` → **Verify KYC** |
| 3.4 | pm | Consent (defaults) → **Record consent** → **Activate** → Agreement `PROGRAM_PARTICIPATION` · `v1` · Effective from **`01-06-2025`** → **Create** → **Upload signed copy** (PDF). Note the code `AGR-2026-…` |

## Stage 4 — Farm (one farm, no control farms)
### 4.1 · LOGIN `pm` → farmer → **Farms → Add farm**
| Field | Enter |
|---|---|
| Farm name | `Gonikoppal maize block` |
| Land tenure / Declared area | Owned / `98` |
| Boundary (paste, one per line) | 🧪 `12.1800, 75.9100` / `12.1800, 75.9190` / `12.1890, 75.9190` / `12.1890, 75.9100` (≈ 97.5 ha) — or ✍ the real farm via **FarmFuture** |
| Documents / Ownership | Land record PDF `RTC Sy No 70/3` · Farmer · Owner · 100 % · `RTC Sy. No. 70/3` · `01-01-2020` |

→ **Check boundary** → **Save as new boundary version** → **Submit for review**.

### 4.2 · LOGIN `gis` → Ownership **Verify** (`RTC matches`) → **Start GIS review** → Overlaps empty → **Verify farm**.

The square is ≈ 20 km from Palthope, so it does not overlap any dmrv_db1 farm. With a real farm of another size the credits scale with
the area (≈ 0.17 VER per hectare in year 1 with these factors).

## Stage 5 — Project · LOGIN `pm` (then gis, qatester1)
| Field | Enter |
|---|---|
| Name / Type | `Gonikoppal reduced tillage pilot` / **Agricultural land management** |
| Country / Region / **Planned start** | `IN` / `Karnataka` / **`01-06-2025`** (after the methodology's 01-01-2020) |
| Farms | **Gonikoppal maize block** · from `01-06-2025` · Farmer · `Carbon rights clause of AGR-2026-…` · `100` |
| Standard / Activity | Gold Standard for the Global Goals / Agriculture - soil organic carbon |
| Crediting period | `01-06-2025` – `31-05-2035` |
| Baseline | `01-06-2020` – `31-05-2025` · Practices `Full inversion tillage, crop residues burnt` · Data sources `Farmer records, fuel and fertiliser bills` |

**Submit for eligibility review** → **gis**: Boundary → **Accept boundary** (`ok test`) → **qatester1**: Carbon rights **Verify** →
**Approve eligibility** → **pm**: **Confirm activity**. 🔎 pm cannot approve eligibility.

## Stage 6 — Lock
**ms1**: project → **Methodology** → **Evaluate candidates** → **GS402 1.0-IT-A3 Applicable** (A1 ✔ A2 ✔) → **Recommend**
(tick evidence acknowledged). 🔎 ms1 cannot **Confirm & lock**. **pm** → **Confirm & lock** → ✔ Methodology confirmed.

## Stage 7 — MRV setup (MRV → Gonikoppal reduced tillage pilot)
| Step | LOGIN | Enter | ✔ |
|---|---|---|---|
| 7.1 | mrv | **MRV plans → Create**: frequency `Annual` · Quantification approach **empty** · start `01-06-2025` · end `31-05-2035` · evidence `Records` → **Create** → **Submit** | 25 `GS_…` measurements; approach shows **Configuration required** (Approach 3 has no sampling — normal) |
| 7.2 | qatester1 | open the plan → **Approve** — the dialog lists the gaps (approach, depth, samples per stratum, statistical design): **acknowledge** them | Approved |
| 7.3 | mrv | **Monitoring periods** → `Period 1` · Monitoring · `01-06-2025` – `31-05-2026` → **Mark planned → Start period → Open data collection** | Data collection |
| 7.4 | mrv | **Stratification → New**: Project stratum · `S1` / `Maize block` · farm Gonikoppal maize block · characteristics CLIMATE `Tropical moist`, SOIL_TYPE `Red sandy clay loam` → **Create** | Draft |
| 7.5 | gis | **Approve** S1 | Approved |

No control sites, no sampling design, no laboratory engagement.

## Stage 8 — Monitoring data (picker **Period 1**)
### 8.1 · LOGIN `mrv` · tab **Monitoring data** — 14 stratum records
Measurement level **Stratum** → **S1** · Observed on **`15-05-2026`** · Phase **Monitoring** · Source **Document**.

| # | Measurement | Value | Meaning |
|---|---|---|---|
| 1 | GS_SOC_REF | 🧪 `47` | reference SOC 0–30 cm, tropical moist, low-activity clay soil (IPCC Table 2.3) |
| 2 | GS_F_LU | 🧪 `0.83` | land use factor, long-term cultivated, tropical moist |
| 3 | GS_F_MG_BL | 🧪 `1.00` | tillage factor, baseline = full tillage |
| 4 | GS_F_I_BL | 🧪 `1.00` | input factor, baseline = medium input |
| 5 | GS_F_MG_PR | 🧪 `1.04` | tillage factor, project = reduced tillage, tropical moist |
| 6 | GS_F_I_PR | 🧪 `1.11` | input factor, project = high input (residues kept) |
| 7 | GS_T_BL | `20` | years under the baseline practice (at most 20) |
| 8 | GS_T_PR | **`1`** | years since project start at the end of this period |
| 9 | GS_U_SOC_REF | 🧪 `10` | ± % |
| 10 | GS_U_F_LU | 🧪 `11` | ± % |
| 11 | GS_U_F_MG_BL | `0` | baseline reference factor, no uncertainty |
| 12 | GS_U_F_I_BL | `0` | baseline reference factor, no uncertainty |
| 13 | GS_U_F_MG_PR | 🧪 `7` | ± % |
| 14 | GS_U_F_I_PR | 🧪 `10` | ± % |

⚠ Rows 1–8 are required — a missing one fails dataset QA (missing records). ⚠ Enter **all six** `GS_U_…` rows: a missing uncertainty
is replaced by the conservative default (± 50 %, t = 3), which wipes out most of the credits.

### 8.2 · Farm records (Measurement level **Farm** → Gonikoppal maize block, Source Document)
Five baseline years and the project year, so the platform can compare project use with the baseline average.

| Measurement | Phase | Observed on | Value |
|---|---|---|---|
| GS_FERT_N (kg N) | **Baseline** | `01-03-2021` / `01-03-2022` / `01-03-2023` / `01-03-2024` / `01-03-2025` | 🧪 `4000` / `4100` / `4000` / `4200` / `4100` (5 records) |
| GS_FERT_N (kg N) | **Project** | `01-03-2026` | 🧪 `4000` |
| GS_DIESEL (L) | **Baseline** | same 5 dates | 🧪 `2500` each (5 records) |
| GS_DIESEL (L) | **Project** | `01-03-2026` | 🧪 `1800` |

### 8.3 · Project records (Measurement level **Project**, Observed on `15-05-2026`, Phase Monitoring)
| Measurement | Value | Why |
|---|---|---|
| GS_FEF_DIESEL | `0.00268` | 2.68 kg CO2e per litre of diesel (needed only if project diesel exceeds the baseline, recorded anyway) |
| GS_PAA | **`YES`** | the period runs into 2026; without PAA = YES the 2026 share (151 of 365 days) is not credited |

Total **28 records** (14 + 12 + 2).

### 8.4 · mrv → **Datasets & QA** → Period 1 → **Create dataset version** → **Open / QA** → **Submit for QA**.
### 8.5 · qatester1 → **Start QA review** → all PASS except **one WARN "configuration"** (approach, depth, samples, design — normal for
Approach 3) → PASS → **Record QA result** → **Approve dataset**.

## Stage 9 — Calculation · LOGIN `analyst`
**Calculations** → project · **Period 1** → **New calculation run** → **Check readiness & freeze inputs** (✔ Inputs frozen) → **Execute**
(✔ Calculated).

| Output | Meaning | Expected |
|---|---|---|
| SOC_BL_… | baseline SOC = 47 × (1 + (0.83 × 1.00 × 1.00 − 1) × 20/20) (Eq. 4) | **39.0100 t C/ha** |
| SOC_0_… | SOC at the start of the period (T_PR − 1 = 0 → equals SOC_BL) | **39.0100 t C/ha** |
| SOC_T_… | 39.01 + 47 × 0.83 × (1.04 × 1.11 − 1.00 × 1.00) × (1 − 0)/20 (Eq. 6) | **39.3112 t C/ha** |
| PE_FERT / PE_FUEL / PE_ELEC / PE_AGRO | only an **increase** over the baseline average counts: fertiliser 4,000 < 4,080, diesel 1,800 < 2,500 | **0 / 0 / 0 / 0** |
| PE_TOTAL | | **0** |
| DSOC_C | 0.3012 t C/ha × 97.5156 ha | **29.3675 t C** |
| DSOC_CO2 | × 44/12 | **107.6809 t CO2e** |
| LK_DISPLACED_HA / LK_TOTAL | no yield recorded → no displaced production | **0 / 0** |
| UNC_LOWER_C / UNC_UPPER_C | every factor at mean ± (U/2 × 1.675), all combinations | **−0.9657 / 73.0359 t C** |
| UNC | (73.04 + 0.97) / (2 × 29.37) = 1.26 → capped at 100 % | **1.0000** |
| UD | uncertainty deduction = UNC − 20 % | **0.8000** |
| DC_SOC_ADJ | 29.3675 × (1 − 0.80) | **5.8735 t C** |
| ER_GROSS | 5.8735 × 44/12 − PE − LK | **21.5362 t CO2e** |
| PAA_BLOCKED_SHARE | PAA = YES | **0** |
| BUFFER | 20 % | **4.3072** |
| ER_NET | | **17.2289** |
| REVERSAL | | **0** |
| **GS_VER_TOTAL** | whole tonnes, rounded down | **17** |

**Why only 17 of 107 t CO2e?** In year 1 the modelled change is small (0.30 t C/ha) while the IPCC factors carry ± 7 – 11 % uncertainty;
the low end of the range gives no gain at all (slightly negative), so the uncertainty is above 100 % and GS 402 deducts 80 %. This is the methodology
working as written, not an error. The measured option (module **GS402-IT-A1**, soil sampling like the VM0042 test) usually gives a
much smaller deduction.

🔎 **9.1** analyst cannot **Approve**. **qatester1**: run → **QA** → **Start calculation QA** → PASS → **Record QA** → **Approve**.
✔ run **Approved**, project **Calculated**.

🔎 **9.2 (optional, on a copy of the period)** Without the `GS_PAA = YES` record: PAA_BLOCKED_SHARE **0.4137** (151/365 days after
01-01-2026), BUFFER 2.5253, ER_NET 10.1014 → **10 GS VERs**.

## Stages 10–14 — Verification, registry, ledger, marketplace, payout
Exactly as in the VM0042 test document (`docs/e2e-test-palthope-vm0042.md`, Stages 14–18), with these changes:

| Stage | Change |
|---|---|
| 10 Verification | finding text `IPCC factors and tillage records`; VVB quantity **`17`** · unit `tCO2e`; Verification tab picker on **Period 1** |
| 11 Registry | account: Registry **Gold Standard Registry** · Account ID `GS-ACC-001` · Label `Gold Standard account` · credit unit **`VER`** = **`tCO2e`**; registration `GS-PRJ-001`; submission `GS-SUB-001`; issuance `GS-ISS-001` · Unit **`VER`** · vintage `2026` · **17** credits · serials `GS-2026-000001` – `GS-2026-000017`; 🔎 **18** → `QUANTITY_EXCEEDS_VERIFIED` |
| 12 Ledger | retire 2 · transfer 2 to the buyer · buyer retires 1 → **13** available |
| 13 Marketplace | listing 10 credits · ₹500 · max order 5 · buyer orders **5** = **₹2,500** |
| 14 Payout | 60 % → **₹1,500** to the farmer · allocation farm **Gonikoppal maize block 100 %** · bank details 🧪 |

---

## Part D — Where every value comes from
| Value | Source | Why |
|---|---|---|
| Code GS402, version 1.0, date 01-01-2020, Eqs. 4/6, D = 20 years, 20 % uncertainty threshold, 20 % buffer | ⚙ Gold Standard SOC Framework v1.0 + 402.1 | the methodology |
| SOC_REF 47 t C/ha | 🧪 IPCC 2019 Refinement Vol. 4 Table 2.3 (tropical moist, LAC soil) — ✍ real: GS 402 Table 4 / national data for the farm's soil | reference stock |
| F_LU 0.83 ± 11 %, F_MG 1.04 ± 7 % (reduced till), F_I 1.11 ± 10 % (high input) | 🧪 IPCC 2019 Refinement Vol. 4 Table 5.5 (tropical moist) — ✍ confirm for the farm's climate zone | stock change factors and uncertainties |
| T_BL 20, T_PR 1 | farm history / period | years under each practice |
| Fertiliser and diesel, 5 baseline years + project year | 🧪 — ✍ real: farmer bills and logbook | project emissions only if above baseline |
| FEF diesel 0.00268 t CO2e/L | IPCC 2006 Vol. 2 (diesel, ≈ 2.68 kg CO2/L) | fuel emission factor |
| PAA = YES | 🧪 — ✍ real: only after Gold Standard approves the project's PAA status | 2026+ vintages |
| Farm boundary, farmer | ✍ / 🧪 | project area |

## Part E — Errors you may see
| Code / message | Fix |
|---|---|
| `CONFIGURATION_REQUIRED` on plan approval | acknowledge the gaps in the approval dialog (Approach 3 has no sampling) |
| Dataset QA missing records for `GS_SOC_REF` / `GS_F_…` / `GS_T_…` | all 8 required stratum records for S1 in the period (8.1) |
| Very few credits, UNC = 1.0 | check all six `GS_U_…` were entered; year 1 with IPCC factors is expected to be heavily deducted |
| `MISSING_REQUIRED_INPUT` "FEF_DIESEL is needed because the project uses more than the baseline" | record `GS_FEF_DIESEL` (same for gasoline / `GS_EEF` for electricity) |
| `MISSING_REQUIRED_INPUT` "Crop yield fell below the baseline … GS_LK_EF" | record `GS_LK_EF` when `GS_YIELD` drops below the baseline |
| `INVALID_INPUT` "factors and years must not be negative" | correct the stratum record |
| Credits ≈ 40 % lower than expected | `GS_PAA = YES` missing (2026 share blocked) |
| Module list does not show IT-A3 | methodology code must be **`GS402`** and version label **`1.0-IT-A3`** (or `1.0`) |
