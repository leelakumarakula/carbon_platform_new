# Palthope VM0042 test — where every value comes from

**Project:** PRJ-2026-000001 · Palthope VM0042 pilot · database `dmrv_db1` · branch `fixes_14/10` · Verra VCS, methodology VM0042 v2.2
**Status at the time of writing:** Stages 1–13 complete; calculation CALC-2026-000001 approved with **61 VCUs**.

This page lists every value entered in the platform for this test and says whether it came from the **soil reports**, from **real
project data**, or was **entered manually as a test value** — and why.

| Mark | Meaning |
|---|---|
| 🟢 **Report** | Taken from the Ganesh Consultancy soil reports |
| 🔵 **Real** | Real project data that is not in the reports (FarmFuture map, farmer phone) |
| 🟡 **Derived** | Chosen from the reports (e.g. period dates set around the report dates) |
| 🧪 **Manual (test)** | Not in the reports; entered so the platform can run the full flow |
| ⚙ **Methodology / setup** | Fixed by Verra, VM0042 or the test setup |

---

## 1. The two soil reports

Lab: **Ganesh Consultancy & Analytical Services, Mysore** (ISO 17025). Customer: Varsapradaya Private Limited. Samples drawn by the customer.

| Round | Report | Collected | Samples and organic carbon (OC) |
|---|---|---|---|
| **Baseline (Period 0)** | C-11169 … C-11172 | 16-09-2026 | 3 Soil **1.40 %** · 2/Weather **2.39 %** · Palthope Hub **2.01 %** · Palthope Probe **1.74 %** |
| **Monitoring (Period 1)** | C-11543 … C-11546 | 25-09-2026 | P1 **1.83 %** · P2 **1.78 %** · H1 **1.14 %** · H2 **2.77 %** |

The reports also give pH, EC, available N, P and K. **VM0042 does not use these**, so they are not entered. Only organic carbon is used.

---

## 2. Values from the reports (🟢 / 🟡)

| Where in the platform | Value entered | From the report |
|---|---|---|
| Period 0 lab result LT-2026-000001 (P0 S1-1 0-30, V42_OC) | **20.1 g/kg** | 🟢 Palthope Hub 2.01 % × 10 |
| Period 0 lab result LT-2026-000005 (P0 S1-2 0-30, V42_OC) | **17.4 g/kg** | 🟢 Palthope Probe 1.74 % × 10 |
| Period 0 lab result LT-2026-000009 (P0 S1-3 0-30, V42_OC) | **23.9 g/kg** | 🟢 2/Weather 2.39 % × 10 |
| Period 0 lab result LT-2026-000013 (P0 S1-4 0-30, V42_OC) | **14.0 g/kg** | 🟢 3 Soil 1.40 % × 10 |
| Period 1 lab result (P1 S1-1 0-30, V42_OC) | **11.4 g/kg** | 🟢 H1 1.14 % × 10 |
| Period 1 lab result (P1 S1-2 0-30, V42_OC) | **18.3 g/kg** | 🟢 P1 1.83 % × 10 |
| Period 1 lab result (P1 S1-3 0-30, V42_OC) | **27.7 g/kg** | 🟢 H2 2.77 % × 10 |
| Period 1 lab result (P1 S1-4 0-30, V42_OC) | **17.8 g/kg** | 🟢 P2 1.78 % × 10 |
| Field records Period 0 — "Collected at" | **16-09-2026 10:00** | 🟢 baseline collection date |
| Field records Period 1 — "Collected at" | **25-09-2026 10:00** | 🟢 monitoring collection date |
| PDF report on all 52 Period 0 lab results | Ganesh Consultancy - Soil Test-16-09-2026.pdf | 🟢 the baseline report |
| PDF report on all 52 Period 1 lab results | Varsapradaya Pvt ltd - Soil - 25-09-2026.pdf | 🟢 the monitoring report |
| Sample quantity per field record | **1 kg** | 🟢 "Polythene cover / 1 kg" |
| Laboratory method text (V42_OC) | Dry combustion | 🟢 report method GCAS/SOP/7.2/TOC (organic carbon) |
| Monitoring period **Period 0 baseline** | **01-09-2026 – 20-09-2026** | 🟡 chosen to contain the 16-09-2026 sampling |
| Monitoring period **period 1** | **21-09-2026 – 20-09-2027** | 🟡 chosen to contain the 25-09-2026 sampling |
| Project start, crediting start, MRV plan start, participation, agreement | **01-09-2026** | 🟡 chosen to start before the first sampling |

---

## 3. Values entered manually, stage by stage

### Stage 1–3 · Setup, catalog, methodology
| Value | Entered | Source | Why |
|---|---|---|---|
| Organizations (DEV, LAB, VVB, BUY, VREG) and 19 users, password `Test@12345678` | — | ⚙ setup | test accounts |
| Standard `VCS`, activity `IALM` | — | ⚙ Verra | the crediting programme |
| Methodology `VM0042` version `2.2`, effective `21-10-2025` | — | ⚙ Verra VM0042 v2.2 | the methodology document |
| Calculation module `VM0042-V2.2-QA2-QA3` v1.2.0 (16 monitoring rules) | — | ⚙ platform | implements VM0042 |
| Applicability rules A1 (`"VCS"`), A2 (`"IALM"`) | — | ⚙ methodology | eligibility check |

### Stage 4 · Farmer
| Value | Entered | Source | Why |
|---|---|---|---|
| Farmer name | `srikanth dodla` | 🔵 real | owner of the FarmFuture account |
| Phone | `7799661222` | 🔵 real | finds the estate boundaries in FarmFuture |
| Village / district / state | `Palthope` / `sub-karnataka` / `karnataka` | 🔵 / 🧪 | location (district typed as a placeholder) |
| Language / gender | `mr` / MALE | 🧪 | required fields |
| KYC National ID | ends `3456` | 🧪 | KYC is required to activate the farmer |
| Consent | Personal data processing v1, paper signed | 🧪 | required before activation |
| Agreement | AGR-2026-000001 · PROGRAM_PARTICIPATION · v1 · from 01-09-2026 | 🧪 / 🟡 | carbon rights need a signed agreement |

### Stage 5 · Farms
| Farm | Boundary | Area | Source | Why |
|---|---|---|---|---|
| **Palthope Estate** (FARM-…001, project) | FarmFuture "Palthope estate", whole farm (2 zones merged) | **7.63 ha** | 🔵 real | the project farm |
| Palthope Control C1 (FARM-…003) | drawn square, 300 m west of the estate | 2.89 ha | 🧪 | VM0042 needs **3 control farms**; the reports have none |
| Palthope Control C2 (FARM-…004) | drawn square, 300 m east | 2.89 ha | 🧪 | same |
| Palthope Control C3 (FARM-…005) | drawn square, 300 m south | 2.89 ha | 🧪 | same |
| Survey references, valid from, ownership 100 % | Sy No 45/2, 46/1–46/3 · 01-01-2020 | — | 🧪 | ownership must be recorded and verified |

The FarmFuture field "Palthope Bison Field" was first tried as control C1, but FarmFuture maps it as a 0.18 ha triangle in central
Bengaluru (196 km away). That farm (FARM-…002) was made inactive and replaced by the drawn square.

### Stage 6 · Project
| Value | Entered | Source | Why |
|---|---|---|---|
| Name / type / region | Palthope VM0042 pilot · Agricultural land management · Palthope | 🧪 | project record |
| Crediting period | 01-09-2026 – 31-08-2036 | 🧪 / 🟡 | 10 years from the project start |
| Baseline period | 01-09-2023 – 31-08-2026 | 🧪 | the 3 years before the project |
| Baseline practices | High synthetic N, diesel machinery, burning of coffee prunings | 🧪 | describes the old practice |
| Carbon rights | farmer 100 %, from 01-09-2026 | 🧪 | the farmer owns the carbon rights |

### Stage 8 · MRV plan, periods, strata
| Value | Entered | Source | Why |
|---|---|---|---|
| MRV plan | Annual sampling · 01-09-2026 – 31-08-2036 | 🧪 / 🟡 | monitoring window |
| Periods | see section 2 | 🟡 | contain the report dates |
| Strata | S1 = Palthope Estate; C1–C3 = control farms, each linked to S1 | 🧪 | project area vs control sites |
| Soil texture · soil group · climate | sandy clay loam · Red lateritic · Tropical wet | 🧪 | control farms must match the project (VM0042 Table 7); the reports give no texture |
| Annual rainfall | S1 2200 · C1 2150 · C2 2200 · C3 2250 mm | 🧪 | **required**; above 1,000 mm the wet-climate N₂O factors apply |

### Stages 10 and 12 · Sampling and laboratory (both periods)
| Value | Entered | Source | Why |
|---|---|---|---|
| Sampling design | 4 points on the estate (one per report sample), 3 per control farm; stratified random; 0–50 cm; 10 m apart | 🟡 / 🧪 | 4 report samples per round; VM0042 needs at least 3 per stratum |
| GPS of each field record | the planned point's coordinates | ⚙ platform | generated by the platform |
| Probe diameter / cores | 21.5 mm / 4 | 🧪 | needed to turn soil mass into tonnes per hectare (VM0042 Eq. 3) |
| Depth layers | 0–30 cm and 30–50 cm | 🧪 | VM0042 needs **two layers**; the reports have one sample and no depth |
| **OC of the 30–50 cm layer** (estate) | 0.6 × the top layer (P0: 12.1, 10.4, 14.3, 8.4 · P1: 6.8, 11.0, 16.6, 10.7 g/kg) | 🧪 | second layer not in the reports |
| **Soil mass** of every sample | 285 g (0–30) · 205 g (30–50) | 🧪 | the reports give no soil mass or bulk density |
| **OC of the control farms** | P0 ≈ 18.8–19.3 g/kg (top), 11.3–11.6 (bottom); P1 ≈ 18.3–18.8 (top), 11.0–11.3 (bottom) | 🧪 | the reports cover no control farms |
| Sample labels, seals, accession numbers | P0-/P1-<key>-A/B · SEAL-… · LAB-<number> | 🧪 | chain of custody |
| Analysed at | the date of entry | ⚙ platform | must be after the lab receipt (the report's own analysis dates are earlier) |
| Soil-mass method text | Oven-dried at 105 C, sieved < 2 mm | 🧪 | method of the (test) soil mass |

### Stages 11 and 12.14 · Monitoring data
| Value | Entered | Source | Why |
|---|---|---|---|
| Risk rating (V42_NPR), both periods | 12 % | ⚙ Verra minimum | sets the buffer |
| Synthetic fertiliser N | 9000 / 9200 / 9400 kg (2023–25) → 4500 kg (project year) | 🧪 | credits come from the cut in emissions |
| Organic fertiliser N | 2000 ×3 → 3000 kg | 🧪 | more compost under the new practice |
| Diesel | 15000 ×3 → 7000 L | 🧪 | less machinery |
| Coffee prunings burned | 60000 / 62000 / 64000 → 0 kg dry matter | 🧪 | prunings mulched instead of burned |
| Compost bought from outside | 20 t at 0.15 t C/t | 🧪 | tests the leakage deduction (VM0042 Eq. 33) |
| Shade trees removed | NO | 🧪 | VM0042 may ignore trees only if none are cut |

---

## 4. Result (CALC-2026-000001, approved)

| Output | Value | Driven by |
|---|---|---|
| Estate soil carbon, Period 0 → 1 | 36.99 → 36.92 t C/ha | 🟢 the real report values |
| Control soil carbon, Period 0 → 1 | 37.35 → 36.34 t C/ha | 🧪 |
| Sampling uncertainty | 100 % → soil change counted as 0 | 🟢 real values: rounds 9 days apart, spots 1.14–2.77 % OC |
| Emission reductions | 62.43 t CO₂e (diesel 23.09 · fertiliser N₂O 34.67 · burning CH₄ 3.75 + N₂O 0.92) | 🧪 farm-activity values |
| Compost leakage | − 1.32 t CO₂e | 🧪 |
| **VCU_TOTAL** | **61** | 62.43 − 1.32 = 61.11, rounded down |

**What this means:** the run proves the full platform flow with the real laboratory numbers. Because the two report rounds are only
9 days apart, the estate's soil carbon does not change measurably and the platform correctly gives **no soil credit**; the 61 credits
come from the farm-activity test values. This is therefore **not a carbon estimate for Palthope**. A real estimate needs a second
sampling about a year later, real control farms, soil mass (or bulk density) per depth layer, and the estate's real records.

## 5. Deviations noticed during the run
| Item | Effect |
|---|---|
| Field record SP-2026-000004 (Period 0, S1-1) saved with **2 cores** instead of 4 | estate Period 0 soil carbon 36.99 instead of 36.98; credits unchanged (61) |
| Field record SP-2026-000010 (Period 0, C1-3) has no sample quantity | none (not used by the calculation) |
| Carbon-rights reference saved as "Carbon rights clause of AGR-2026" (number cut off) | none (free text) |
| A second agreement AGR-2026-000002 left in Draft | none (AGR-2026-000001 is the signed one) |
| FarmFuture "Palthope Bison Field" mapped in Bengaluru | replaced by a drawn control farm; FarmFuture mapping should be corrected |
| Period 1 named "period 1" (lower case) | none; shows as "Period 2 · period 1" on finance pages |
