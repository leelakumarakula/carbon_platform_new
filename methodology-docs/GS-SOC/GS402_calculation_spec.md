# Gold Standard SOC Framework (GS 402) v1.0: calculation specification for the platform

**Implemented in:** `backend/app/calculation/modules/gs_soc_402.py`

**Tests:**
- `tests/test_gs_soc_402.py`: hand calculations for Approach 1 and Approach 3, seed emissions, leakage, guards and reversal.
- `tests/test_gs_soc_selection.py`: selecting and switching modules on the Calculation tab.

**Equations:** transcribed in `extract_framework.md` (framework, 19 equations) and `extract_modules.md` (402.1, 402.4 and 402.6).

## 1. Calculation modules

The methodology version must be **code `GS402`, label `1.0`**. Its Calculation tab offers five modules:

| Module code | Activity module | Approach | SOC data |
|---|---|---|---|
| `GS402-ZT-A1` | 402.4 Zero Tillage v1.0 | 1: on-site measurement | Lab OC (g/kg) and soil mass (g) per depth increment, sampled to **50 cm** (402.4 §5.2.1c), on an equivalent soil mass basis |
| `GS402-IT-A1` | 402.1 Improved Tillage v1.0 | 1 | As above, with a reference depth of 30 cm |
| `GS402-IT-A3` | 402.1 | 3: IPCC factors | Per stratum: SOC_REF, F_LU, F_MG/F_I (baseline and project), T_BL, T_PR, and optionally the ± % of each |
| `GS402-CC-A1` | 402.6 Cover Crops v1.0 | 1 | Lab, 30 cm, plus cover crop seed emissions |
| `GS402-CC-A3` | 402.6 | 3.1: national or regional Tier 2 factors | Per-stratum factors, plus seed emissions |

**Not included:**
- Approach 2 (models and literature).
- 402.6 Approach 3.2 (the IPCC Tier 2 steady-state method).
- 402.4 with Approach 3, which the module itself forbids (402.4 §5.1.1).
- 402.2 organic soil improvers.

## 2. Chain (all modules)

1. **SOC_0 and SOC_t per stratum (t C/ha).**
   - **Approach 1:**
     - Each sample's OC mass is read at the stratum's reference soil mass.
     - The reference mass is the mean cumulative fine-earth mass down to the reference depth in the earlier campaign.
     - With 2 depth increments the value is linearly interpolated; with 3 or more, a cubic spline is used.
     - SOC_0 is the mean over the earlier campaign; SOC_t is the mean over the current campaign.
   - **Approach 3:**
     - SOC_BL comes from Eq. 4.
     - SOC_0 = SOC_BL + ΔSOC up to the period start.
     - SOC_t = SOC_0 + ΔSOC over the period.
     - The Eq. 6 increment over the period is `SOC_REF·F_LU·(F_MG,PR·F_I,PR − F_MG,BL·F_I,BL)·(min(T_PR,D) − min(T_PR−years,D))/D`, with D = 20.
2. **ΔSOC (t C)** = Σ_y (SOC_t,y − SOC_0,y) × A_y (Eqs. 3 and 5).
3. **Uncertainty (Eqs. 7–11).**
   - **Approach 1, per stratum and campaign:**
     - SE = SD/√n.
     - t = two-sided 90 % Student-t with df = n − 1, which equals Table 6.
     - Lower = Σ(SOC_t lower − SOC_0 upper)·A; Upper = Σ(SOC_t upper − SOC_0 lower)·A.
   - **Approach 3, per factor:**
     - If a ± % (two SD) is given: half-width = value × % / 200 × 1.675.
     - If not: half-width = value × 0.5 × 3 (402.4/402.6 §9.1.2).
     - Lower and Upper are the minimum and maximum ΔSOC over all combinations of the factor bounds.
   - UNC = |Upper − Lower| / (2·ΔSOC), with UNC = 1 when ΔSOC ≤ 0.
   - UD = max(0, UNC − 0.20), capped at 1.
4. **ΔC_SOC** = ΔSOC × (1 − UD) when ΔSOC > 0. A loss is taken in full (Eq. 2).
5. **PE (t CO₂e)** is summed per farm and source as `max(0, project total in the period − baseline annual mean × years)`.
   - Fertiliser: × EF_FE.
   - Diesel and gasoline: × FEF.
   - Electricity: × EEF.
   - Agrochemicals: recorded directly in t CO₂e as Σ AQ × AEF.
   - Cover crops also add seed emissions: S × (EF_SP + EF_ST × Dist).
6. **LK (t CO₂e)** = Σ_strata max[(CY_BL − CY_t)/CY_BL; 0] × A_y × leakage-area emissions per ha (FM Eq. 19; 402.4 Eq. 8; 402.6 Eq. 10).
7. **Eq. 1 and credits.**
   - ER_gross = ΔC_SOC × 44/12 − PE − LK.
   - Buffer = 20 % × max(0, ER_gross).
   - ER = ER_gross − buffer.
   - **GS VERs** = floor(max(0, ER)).
   - A negative ER is reported as **REVERSAL**.

## 3. Questions resolved, with sources

| # | Question | Answer used | Source |
|---|---|---|---|
| G1 | Buffer % (BUF) | **20 %** of GS VERs from sequestration; none for permanent reductions. Distributed pro rata by vintage. | GS GHG Emissions Reductions & Sequestration Product Requirements **v3.2 (12.12.2025) §11.1.1–11.1.2** (`501_V3.2_PR_GHG-ERS.pdf`) |
| G2 | GWPs | IPCC **AR5**: CH₄ 28, N₂O 265, for all monitoring from 1 Jan 2021 | GS Rule Update **RU-2020-P&R v1.2** "Applicability of GWP" (03/06/2021), Table 1 and §2.1.3 (`RU-2020-PR-V1.2-GWP-values.pdf`) |
| G3 | EF_FE = 0.01 "t CO₂e/kg N": IPCC's 0.01 is kg N₂O-N/kg N | **Used as printed**, i.e. 0.01 t CO₂e/kg N. This is 2.4× the IPCC conversion (0.01 × 44/28 × 265 / 1000 = 0.00416), so the more conservative reading. All three documents print the same value and unit. | GS 402 Eq. 13 and p.38; 402.4 Eq. 2 and p.19; 402.6 Eq. 2 and p.26 |
| G4 | "t = 1.675 (n = 3)" vs Table 6 (n = 3 → 2.92) | Measured samples use the Table 6 value for their n (n ≥ 3 is required). 1.675 is used only for a factor whose n is unknown; with no SE at all, SE = 50 % and t = 3. | GS 402 p.27; 402.4 / 402.6 §9.1.2 |
| G5 | Eq. 14: is the electricity term inside the year sum? | Yes, summed over the years | Dimensional consistency: the EU term carries the index *a* |
| G6 | "t CO₂e ha⁻¹" on Eqs. 15, 16 and 18 | t CO₂e per farm. Litres × t/L, kWh × t/kWh and kg × t/kg give t CO₂e, and Eqs. 14 and 17 sum t CO₂e. | GS 402 Eqs. 14–18 |
| G7 | Undocumented baseline | Baseline = 50 % of the project value (the maximum the methodology allows) | GS 402 §10.1–10.3; 402.4 / 402.6 Eqs. 2–7 |
| G8 | CY_min | CY_min = CY_BL. CY_min ≤ CY_BL by definition, so this gives at least as much leakage (conservative). The 402.4 ">5 %" text and its 3-year exemption are not applied, because Eq. 8 has neither. | GS 402 Eq. 19 note; 402.4 Eq. 8 footnote ** |
| G9 | 402.6 Eq. 10 has no max[…;0] | max[…;0] is applied: positive leakage is never allowed | GS 402 §11; 402.4 §11.1.1 |
| G10 | Sampling depth and ESM | 402.4: 50 cm (§5.2.1c). 402.1 and 402.6 state no depth, so 30 cm is used (the IPCC depth that the Approach 3 factors refer to). Equivalent soil mass is used in all cases, as 402.4 and 402.6 require. | 402.4 §5.2.1(c),(e); 402.6 §6.2.1 |
| G11 | Reference soil mass | The mean mass down to the reference depth in the earlier campaign, so that a denser soil later is "reduced in depth proportionally" | 402.4 §5.2.1(e) |
| G12 | UD applied to a loss | Not applied: the full loss counts (conservative) | GS 402 Eq. 2; LUF conservativeness |
| G13 | Rounding | Whole GS VERs, rounded down | GS registry issues whole units; conservative |
| G15 | Paris alignment (vintages from 1 Jan 2026) | The share of a positive result falling in 2026+ vintages is not credited unless `GS_PAA` = YES. The buffer applies to the credited share. | GS 119 PAA P&R v1.2 §3.1 (applies to all GS4GG methodologies) |
| G14 | Eq. 6 across several calculation periods | ΔSOC of a period = Eq. 6 at the period end minus Eq. 6 at its start | GS 402 Eq. 2 note: SOC_0 is the previous SOC_t |

## 4. Data the platform captures

- **Lab, Approach 1:** `GS_OC` (g/kg) and `GS_SOIL_MASS` (g) per depth increment. At least 2 increments, down to the reference depth.
- **Field record:** probe diameter (mm) and number of cores.
- **Two campaigns:** the project-start sampling (the earlier approved period) and the re-measurement.
- **Per stratum, Approach 3** (Monitoring data → measurement with level *Stratum*):
  - `GS_SOC_REF` (t C/ha);
  - `GS_F_LU`, `GS_F_MG_BL`, `GS_F_I_BL`, `GS_F_MG_PR`, `GS_F_I_PR` (unit `factor`);
  - `GS_T_BL` and `GS_T_PR` (yr);
  - optionally `GS_U_<factor>` (%).
- **Per farm**, phase BASELINE (one record per year, 5 baseline years) and PROJECT (in the period):
  - `GS_FERT_N` (kg N);
  - `GS_DIESEL` and `GS_GASOLINE` (L);
  - `GS_ELECTRICITY` (kWh);
  - `GS_AGROCHEM` (t CO₂e);
  - `GS_YIELD` (kg/ha);
  - cover crops only: `GS_CC_SEED` (kg).
- **Per project:**
  - `GS_FEF_DIESEL` and `GS_FEF_GASOLINE` (t CO₂e/L);
  - `GS_EEF` (t CO₂e/kWh);
  - `GS_LK_EF` (t CO₂e/ha);
  - cover crops only: `GS_CC_EF_SP`, `GS_CC_EF_ST` and `GS_CC_DIST`.

## 5. Typical IPCC 2019 values for Approach 3 (GS 402 Table 4, cropland)

| Factor | Value |
|---|---|
| F_LU, long-term cultivated, tropical moist/wet | 0.83 ±11 % |
| F_LU, long-term cultivated, tropical dry | 0.92 ±13 % |
| F_MG, full tillage | 1.00 |
| F_MG, reduced tillage, tropical moist/wet | 1.04 ±7 % |
| F_MG, reduced tillage, tropical dry | 0.99 ±7 % |
| F_I, medium | 1.00 |
| F_I, high without manure, tropical moist/wet | 1.11 ±10 % |
| F_I, high with manure, tropical moist/wet | 1.44 ±13 % |

For no-till, take the factor from IPCC 2019 Table 5.5 directly, because GS Table 4 has no no-till row. 402.1 excludes no-till anyway.
