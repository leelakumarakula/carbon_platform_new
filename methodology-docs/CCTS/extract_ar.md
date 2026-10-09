# CCTS (India) A/R methodologies and tools: implementation extract

Sources (all in `D:\Desktop\CC\methodology-docs\CCTS\`):

| Short | File | Title | Version / date |
|---|---|---|---|
| FR05.002 | BM_FR05.002_AR_lands_except_wetlands.pdf | Afforestation and reforestation of lands except wetlands (adopted from CDM AR-ACM0003) | v1.0, published 8 Sep 2025, effective 08/09/2025 |
| FR05.001 | BM_FR05.001_AR_degraded_mangroves.pdf | Afforestation and reforestation of degraded mangrove habitats (adopted from CDM AR-AM0014) | v1.0, 27 Mar 2025 |
| AR-0004 | BM-T-AR-0004_trees_shrubs.pdf | Estimation of carbon stocks and change in carbon stocks of trees and shrubs in A/R ICM project activities | v1.0, 27 Mar 2025 |
| AR-0003 | BM-T-AR-0003_deadwood_litter.pdf | Estimation of carbon stocks and change in carbon stocks in dead wood and litter in A/R ICM project activities | v1.0, 27 Mar 2025 |
| AR-0002 | BM-T-AR-0002_biomass_burning.pdf | Estimation of non-CO2 GHG emissions resulting from burning of biomass attributable to an A/R ICM project activity | v1.0, 27 Mar 2025 |
| AR-0005 | BM-T-AR-0005_displacement_leakage.pdf | Estimation of the increase in GHG emissions attributable to displacement of pre-project agricultural activities in A/R ICM project activity | v1.0, 27 Mar 2025 |
| AR-0006 | BM-T-AR-0006_SOC.pdf | Tool for estimation of change in soil organic carbon stocks due to the implementation of A/R ICM project activities | v1.0, 27 Mar 2025 |

All equations were read from page renders (PDF p = physical page number of the PDF). Where the PDF itself has
lost superscripts/subscripts (e.g. AR-0003), the printed form is transcribed literally and the evident
intended form is given separately, flagged in section 4. Nothing is paraphrased inside "Exact (as printed)" lines.

Conventions: t CO2e = tonnes CO2 equivalent; t d.m. = tonnes dry matter; "44/12" converts C to CO2.

---

## 1. Methodologies

### 1.1 FR05.002 - A/R of lands except wetlands

**Applicability (para 6-8, p3-4)**
- Land subject to the project activity does not fall in the wetland category.
- Soil disturbance attributable to the project activity does not cover more than 10 per cent of area in each of the following types of land, when included in the boundary: (i) land containing organic soils; (ii) "Land which, in the baseline, is subjected to land-use and management practices" (sentence truncated in the source - see Ambiguity A1).
  - Footnote 3: pits 0.50 m x 0.50 m at 3 m x 3 m spacing = 2.78 per cent coverage; continuous ploughing = 100 per cent.
- Must also comply with applicability conditions of the tools applied.
- Land does not have to be degraded (footnote 1). Dead wood, litter and SOC may each be included or excluded (para 3).

**Carbon pools (Table 1, p5)**

| Pool | Selected | Note |
|---|---|---|
| Above-ground biomass | Yes | major pool |
| Below-ground biomass | Yes | |
| Dead wood, Litter, Soil organic carbon | Optional | |

**Emission sources / gases (Table 2, p5)**: Burning of woody biomass - CO2: No (counted as stock change); CH4: Yes; N2O: Yes (burning for site preparation or forest management is allowed).

**Insignificant (accounted as zero) (para 15, p6)**: removal of herbaceous vegetation, fossil fuel combustion, fertilizer application, use of wood, decomposition of litter and fine roots of N-fixing trees, construction of access roads within boundary, transportation.

**Baseline & additionality**: BM-T-AR-001 (combined tool; not among the supplied PDFs). Stratification (para 13): baseline by major vegetation type/crown cover/land use; ex-ante project by planting plan; ex-post by actual implementation, revised after disturbances.

**Equation chain (p6-8)**

Eq (1) Baseline net GHG removals by sinks
- Exact: `∆C_BSL,t = ∆C_TREE_BSL,t + ∆C_SHRUB_BSL,t + ∆C_DW_BSL,t + ∆C_LI_BSL,t`
- LaTeX: `\Delta C_{BSL,t} = \Delta C_{TREE\_BSL,t} + \Delta C_{SHRUB\_BSL,t} + \Delta C_{DW\_BSL,t} + \Delta C_{LI\_BSL,t}`

| Var | Meaning | Unit | Source |
|---|---|---|---|
| ∆C_BSL,t | Baseline net GHG removals by sinks in year t | t CO2-e | |
| ∆C_TREE_BSL,t | Change in carbon stock in baseline tree biomass in year t | t CO2-e | AR-0004 |
| ∆C_SHRUB_BSL,t | Change in carbon stock in baseline shrub biomass in year t | t CO2-e | AR-0004 |
| ∆C_DW_BSL,t | Change in carbon stock in baseline dead wood in year t | t CO2-e | AR-0003 |
| ∆C_LI_BSL,t | Change in carbon stock in baseline litter in year t | t CO2-e | AR-0003 |

Eq (2) Actual net GHG removals by sinks
- Exact: `∆C_ACTUAL,t = ∆C_P,t − GHG_E,t`
- LaTeX: `\Delta C_{ACTUAL,t} = \Delta C_{P,t} - GHG_{E,t}`
- GHG_E,t = increase in non-CO2 GHG emissions within boundary from the project in year t, from AR-0002; t CO2-e.

Eq (3) Change in project carbon stocks
- Exact: `∆C_P,t = ∆C_TREE_PROJ,t + ∆C_SHRUB_PROJ,t + ∆C_DW_PROJ,t + ∆C_LI_PROJ,t + ∆SOC_AL,t`
- LaTeX: `\Delta C_{P,t} = \Delta C_{TREE\_PROJ,t} + \Delta C_{SHRUB\_PROJ,t} + \Delta C_{DW\_PROJ,t} + \Delta C_{LI\_PROJ,t} + \Delta SOC_{AL,t}`
- Tree/shrub terms from AR-0004; DW/LI from AR-0003; ∆SOC_AL,t = change in SOC in areas of land meeting the applicability conditions of AR-0006 (from AR-0006). All t CO2-e.

Eq (4) Leakage
- Exact: `LK_t = LK_AGRIC,t`  LaTeX: `LK_t = LK_{AGRIC,t}`  (LK_AGRIC,t from AR-0005; t CO2-e)

Eq (5) Net anthropogenic GHG removals by sinks
- Exact: `∆C_AR,t = ∆C_ACTUAL,t − ∆C_BSL,t − LK_t`
- LaTeX: `\Delta C_{AR,t} = \Delta C_{ACTUAL,t} - \Delta C_{BSL,t} - LK_t`

Eq (6) tCCC and Eq (7) lCCC, for verification period T = t2 − t1
- Exact: `tCCC_t2 = Σ_{t=1}^{t2} ∆C_AR,t` ; `lCCC_t2 = Σ_{t=t1+1}^{t2} ∆C_AR,t`
- LaTeX: `tCCC_{t_2} = \sum_{t=1}^{t_2} \Delta C_{AR,t}` ; `lCCC_{t_2} = \sum_{t=t_1+1}^{t_2} \Delta C_{AR,t}`
- (Printed lower limit is "1", with no "t=": see A2.)
- Para 21: if lCCC_t2 < 0, lCCC_t2 is the number of lCCCs that shall be replaced because of a reversal since the previous certification.

**Tools called and purpose**
| Tool | Purpose in FR05.002 |
|---|---|
| BM-T-AR-001 | baseline scenario + additionality (not supplied) |
| AR-0002 | GHG_E,t (non-CO2 from burning) |
| AR-0003 | ∆C_DW / ∆C_LI baseline and project (optional pools) |
| AR-0004 | tree and shrub stocks/changes baseline and project; precision requirements |
| AR-0005 | LK_AGRIC,t |
| AR-0006 | ∆SOC_AL,t (optional pool) |

**Monitoring (sec 5, p8-9)**: monitoring plan must cover applicability conditions, carbon stock changes in selected pools, project and leakage emissions. Data archived at least two years after end of last crediting period. Forest inventory SOPs + QA/QC (host-country practice, or IPCC GPG-LULUCF 2003). Precision requirements = those in AR-0004 (para 25). Parameters: "found in the tools" (para 26-27) - see each tool's monitored-parameter list below.

**Crediting / vintage / permanence**: temporary credit approach (tCCC for cumulative removals since start; lCCC for removals in each verification period; negative lCCC -> replacement). No buffer pool, non-permanence risk tool, crediting-period length, or vintage rule is stated in the methodology. FR05.002 has no expiry footnote (FR05.001 does - see 1.2).

**Uncertainty / discount**: none in the methodology itself; delegated to AR-0004 (90 % CI, discount when uncertainty > 10 %, Appendix 2).

**GWPs**: none stated in the methodology. The only GWPs in the package are in AR-0002: GWP_CH4 = 21, GWP_N2O = 310 (see A15).

### 1.2 FR05.001 - A/R of degraded mangrove habitats

**Definitions (para 5)**: Degraded mangrove habitat = wetlands where, in their natural state, mangrove vegetation can grow, with soil/sediment usually water-logged with saline or brackish water, subjected to impacts resulting in decrease of forest cover below that reported by the host Party.

**Applicability (para 7, p4)**
- (a) Land is degraded mangrove habitat;
- (b) More than 90 per cent of the project area under the project scenario is planted with mangrove species. If more than 10 per cent of the project area is planted with non-mangrove species then the project activity does not lead to alteration of hydrology of the project area and of connected up-gradient and down-gradient wetland area;
- (c) Soil disturbance attributable to the project does not cover more than 10 per cent of area (same footnote example: 2.78 % / 100 %).
- Must comply with tool applicability conditions.

**Pools (Table 1, p5)**: AGB Yes; BGB Yes; **Litter No** (high turnover and tidal displacement; conservative); Dead wood and SOC Optional.
**Gases (Table 2)**: identical to FR05.002 (CH4, N2O from burning woody biomass; CO2 not counted).
**Insignificant sources (para 16)**: identical list to FR05.002.
**Baseline & additionality**: BM-T-AR-0001. Stratification text identical to FR05.002.

**Equation chain (p6-8)**

Eq (1): `∆C_BSL,t = ∆C_TREE_BSL,t + ∆C_SHRUB_BSL,t + ∆C_DW_BSL,t`  (no litter term)
LaTeX: `\Delta C_{BSL,t} = \Delta C_{TREE\_BSL,t} + \Delta C_{SHRUB\_BSL,t} + \Delta C_{DW\_BSL,t}`

Eq (2): `∆C_ACTUAL,t = ∆C_P,t ― GHG_E,t` (same as FR05.002; GHG_E,t from AR-0002)

Eq (3): `∆C_P,t = ∆C_TREE_PROJ,t + ∆C_SHRUB_PROJ,t + ∆C_DW_PROJ,t + ∆SOC_PROJ,t`
LaTeX: `\Delta C_{P,t} = \Delta C_{TREE\_PROJ,t} + \Delta C_{SHRUB\_PROJ,t} + \Delta C_{DW\_PROJ,t} + \Delta SOC_{PROJ,t}`

Eq (4) SOC (methodology-internal default, AR-0006 NOT used)
- Exact: `∆SOC_PROJ,t = 44/12 × Σ_{t=1}^{t} A_PLANT,t × dSOC_t × 1 year`
- LaTeX: `\Delta SOC_{PROJ,t} = \frac{44}{12} \times \sum_{t=1}^{t} A_{PLANT,t} \times dSOC_t \times 1\,year`

| Var | Meaning | Unit |
|---|---|---|
| ∆SOC_PROJ,t | Change in SOC stock within the project boundary in year t | t CO2-e |
| A_PLANT,t | Area planted in year t | ha |
| dSOC_t | Rate of change in SOC stocks within boundary in year t. Default: (i) 0.50 t C ha-1 yr-1 for t = t_PLANT to t = t_PLANT + 20 years (t_PLANT = year of planting); (ii) 0 t C ha-1 yr-1 for t > t_PLANT + 20 - unless transparent and verifiable information justifies a different value | t C ha-1 yr-1 |

(Summation index reuses t - see A3.)

Eq (5): `LK_t = LK_AGRIC,t` (AR-0005)
Eq (6): `∆C_AR,t = ∆C_ACTUAL,t ― ∆C_BSL,t ― LK_t`
Eq (7): `tCCC_t2 = Σ_{1}^{t2} ∆C_AR,t` ; Eq (8): `lCCC_t2 = Σ_{t1+1}^{t2} ∆C_AR,t`
Para 23: negative lCCC -> replacement (same as FR05.002 para 21).
Footnote 3 (p8): "Temporary CCCs or tCCCs expire at the end of the commitment period following the one during which these were issued. Long-term CCCs or lCCCs expire at the end of its crediting period. tCCCs are issued for the net anthropogenic greenhouse gas removals by sinks achieved by the project activity since the project start date; lCCCs are issued for the net anthropogenic greenhouse gas removals by sinks achieved by the project activity during each verification period."

**Tools called**: BM-T-AR-0001 (baseline/additionality), AR-0002 (GHG_E,t), AR-0003 (dead wood only), AR-0004 (trees, shrubs, precision), AR-0005 (leakage). AR-0006 is not listed.

**Monitoring, precision, uncertainty, GWP, permanence**: identical wording to FR05.002 (sec 5, p9; precision from BM-T-AR-0004). No buffer, no GWP, no crediting-period length.

### 1.3 Differences FR05.001 vs FR05.002

| Item | FR05.002 (non-wetland) | FR05.001 (mangrove) |
|---|---|---|
| Land eligibility | not wetland | degraded mangrove habitat (wetland) |
| Species condition | none | >90 % mangrove species; if >10 % non-mangrove, no hydrology alteration |
| Soil disturbance cap | ≤10 % only on organic soils / certain baseline-managed land | ≤10 % on all project area |
| Litter pool | optional (baseline Eq 1 and project Eq 3) | excluded |
| SOC | via AR-0006 (∆SOC_AL,t, applicability-limited, stratified factors, 0.8 cap) | internal Eq 4: default 0.50 t C/ha/yr for 20 yr per planted cohort |
| Equation numbering | Eq 1-7 | Eq 1-8 (extra SOC eq) |
| tCCC/lCCC expiry footnote | absent | present |
| Everything else (trees/shrubs/DW/fire/leakage/CCC formulas, insignificant sources, monitoring) | same | same |

---

## 2. Tools

### 2.1 BM-T-AR-0004 - Trees and shrubs (core biomass tool)

**Scope / applicability**: baseline stocks/changes; ex-ante projection; ex-post monitoring. "No internal applicability conditions" (para 9).

**Definitions (para 4-7)**
- Uncertainty = standard error of the mean expanded at 90 % confidence level divided by the mean, as percentage. Worked example (p4): mean 45.328 t d.m./ha, n = 34, s = 12.776 -> SEM = 12.776/√34 = 2.191; × t(0.1,33) = 1.692 -> 3.707; U = 3.707/45.328 × 100 = 8.18 %.
- Only sampling uncertainty is assessed/controlled; measurement and model (allometric) uncertainty are not quantified (handled by QA/QC).
- Plot biomass = tree biomass per hectare in a plot. Tree biomass = above- plus below-ground living biomass.
- Notation in methodologies: baseline C_TREE_BSL,t, C_SHRUB_BSL,t, ∆C_TREE_BSL,t, ∆C_SHRUB_BSL,t; project C_TREE_PROJ,t, C_SHRUB_PROJ,t, ∆C_TREE_PROJ,t, ∆C_SHRUB_PROJ,t (para 12).

**Zero conditions (sec 4.1)**
- Para 13 - baseline tree carbon stock may be zero if ALL: (a) pre-project trees neither harvested, cleared nor removed during the crediting period; (b) no mortality from competition with planted trees or damage from project implementation; (c) pre-project trees not inventoried with project trees, but their continued existence is monitored throughout the crediting period.
- Para 14 - baseline changes in trees and shrubs may be zero where documentary evidence or PRA shows one or more of: (a) reduced topsoil depth; (b) gully/sheet/rill erosion, landslides, mass-movement; (c) indicator species of infertile land; (d) bare sand dunes or other bare land; (e) contaminated soils, mine spoils, highly alkaline/saline soils; (f) periodic cycles (slash-and-burn, clearing-regrowing) with oscillating biomass; (g) conditions (a), (b), (c) "under paragraph 11" apply (see A6).
- Para 15 - ex-ante, project shrub change may be zero.

**Methods for change in tree carbon stock between two times (para 16)**: (a) difference of two independent stock estimations; (b) direct re-measurement of plots (ex-post only); (c) proportionate crown cover (ex-ante baseline only, CC < 20 % of national forest crown-cover threshold); (d) "no-decrease" demonstration (ex-post only).

#### Eq (1)-(2): Difference of two independent stock estimations (p7-8)
- Eq (1) Exact: `∆C_TREE = C_TREE,t2 − C_TREE,t1`; LaTeX: `\Delta C_{TREE} = C_{TREE,t_2} - C_{TREE,t_1}`
- Eq (2) Exact: `u_∆C = √((u1 × C_TREE,t1)² + (u2 × C_TREE,t2)²) / |∆C_TREE|`
  LaTeX: `u_{\Delta C} = \frac{\sqrt{(u_1 \times C_{TREE,t_1})^2 + (u_2 \times C_{TREE,t_2})^2}}{|\Delta C_{TREE}|}`

| Var | Meaning | Unit |
|---|---|---|
| ∆C_TREE | Change in carbon stock in trees between t1 and t2 | t CO2e |
| C_TREE,t1 | Carbon stock at t1. Note 1: at first verification set equal to pre-project tree stock (C_TREE,t1 = C_TREE_BSL); may be zero if conditions "under paragraph 10" are met (A6). Note 2: use the undiscounted estimate even if discounted at the previous verification | t CO2e |
| C_TREE,t2 | Carbon stock at t2 | t CO2e |
| u_∆C | Uncertainty in ∆C_TREE | fraction/% |
| u1, u2 | Uncertainties in C_TREE,t1 and C_TREE,t2 | fraction/% |

Para 20: if u_∆C > 10 %, ∆C_TREE is made conservative by Appendix 2 discount.

#### Eq (3)-(8): Direct estimation of change by re-measurement of plots (ex-post only) (p8-10)
- Eq (3) Exact: `∆C_TREE = 44/12 × CF_TREE × ∆B_TREE` (the "44" is on p8, rest on p9; A7)
  LaTeX: `\Delta C_{TREE} = \frac{44}{12} \times CF_{TREE} \times \Delta B_{TREE}`
- Eq (4) Exact: `∆B_TREE = A × ∆b_TREE`; LaTeX: `\Delta B_{TREE} = A \times \Delta b_{TREE}`
- [Eq (5), unlabelled in source] Exact: `∆b_TREE = Σ_{i=1}^{M} w_i × ∆b_TREE,i`; LaTeX: `\Delta b_{TREE} = \sum_{i=1}^{M} w_i \times \Delta b_{TREE,i}`
- Eq (6) Exact: `u_∆C = t_VAL × √(Σ_{i=1}^{M} w_i² × s²_∆,i / n_i) / |∆b_TREE|`
  LaTeX: `u_{\Delta C} = \frac{t_{VAL} \times \sqrt{\sum_{i=1}^{M} w_i^2 \times \frac{s_{\Delta,i}^2}{n_i}}}{|\Delta b_{TREE}|}`
- Eq (7) Exact: `∆b_TREE,i = Σ_{p=1}^{n_i} ∆b_TREE,p,i / n_i`; LaTeX: `\Delta b_{TREE,i} = \frac{\sum_{p=1}^{n_i} \Delta b_{TREE,p,i}}{n_i}`
- Eq (8) Exact: `s²_∆,i = (n_i × Σ_{p=1}^{n_i} ∆b²_TREE,p,i − (Σ_{p=1}^{n_i} ∆b_TREE,p,i)²) / (n_i × (n_i − 1))`
  LaTeX: `s_{\Delta,i}^2 = \frac{n_i \times \sum_{p=1}^{n_i} \Delta b_{TREE,p,i}^2 - \left(\sum_{p=1}^{n_i} \Delta b_{TREE,p,i}\right)^2}{n_i \times (n_i - 1)}`

| Var | Meaning | Unit |
|---|---|---|
| ∆C_TREE | Change in carbon stock in trees between two successive measurements | t CO2e |
| CF_TREE | Carbon fraction of tree biomass; default 0.47 unless justified | t C (t d.m.)-1 |
| ∆B_TREE | Change in tree biomass within the biomass estimation strata | t d.m. |
| A | Sum of areas of the biomass estimation strata | ha |
| ∆b_TREE | Mean change in tree biomass per hectare within the strata (printed as "BTREE") | t d.m. ha-1 |
| w_i | A_i / A | dimensionless |
| ∆b_TREE,i | Mean change in tree biomass per hectare in stratum i (printed "carbon stock" but unit t d.m. ha-1) | t d.m. ha-1 |
| ∆b_TREE,p,i | Change in tree biomass per hectare in plot p of stratum i | t d.m. ha-1 |
| t_VAL | Two-sided Student's t for 90 % confidence, df = n − M (n = total plots in the strata, M = number of strata) | - |
| s²_∆,i | Variance of (mean) change in tree biomass per ha in stratum i (A8) | (t d.m. ha-1)² |
| n_i | Number of plots re-measured in stratum i | - |

Para 24: if u_∆C > 10 %, discount ∆C_TREE per Appendix 2. Plot biomass via Appendix 1.

#### Eq (9)-(10): Proportionate crown cover - baseline change (ex-ante only) (p10-11)
Applicability: mean pre-project tree crown cover < 20 % of the threshold crown cover reported by India under para 8 of annex to decision 5/CMP.1. Tool example: India threshold 30 % -> applicable only if < 6 % (A9).
- Eq (9) Exact: `∆C_TREE_BSL = Σ_{i=1} ∆C_TREE_BSL,i`; LaTeX: `\Delta C_{TREE\_BSL} = \sum_{i=1}^{M} \Delta C_{TREE\_BSL,i}` (upper limit not printed)
- Eq (10) Exact: `∆C_TREE_BSL,i = 44/12 × CF_TREE × ∆b_FOREST × (1 + R_TREE) × CC_TREE_BSL,i × A_i`
  LaTeX: `\Delta C_{TREE\_BSL,i} = \frac{44}{12} \times CF_{TREE} \times \Delta b_{FOREST} \times (1 + R_{TREE}) \times CC_{TREE\_BSL,i} \times A_i`

| Var | Meaning | Unit |
|---|---|---|
| ∆C_TREE_BSL | Mean annual change in carbon stock in trees in the baseline | t CO2e yr-1 |
| ∆C_TREE_BSL,i | Same, stratum i | t CO2e yr-1 |
| CF_TREE | default 0.47 | t C (t d.m.)-1 |
| ∆b_FOREST | Default mean annual increment of above-ground biomass in forest in the region/country; values of MAI_FOR from Table 3A.1.5 of IPCC GPG-LULUCF (latest) unless justified | t d.m. ha-1 yr-1 |
| R_TREE | Root-shoot ratio for baseline trees; default 0.25 | dimensionless |
| CC_TREE_BSL,i | Baseline tree crown cover in stratum i at project start, as fraction | dimensionless |
| A_i | Area of baseline stratum i delineated by crown cover at start | ha |

Result is already annual, so Eq (11) does not apply.

#### "No-decrease" method (para 28-29, ex-post only)
Change in stratum may be conservatively estimated as zero if all of: (a) no harvest since previous verification; (b) no disturbance (pest, fire) reducing tree carbon; (c) remote sensing or inventory data (incl. participatory) show crown cover not decreased.

#### Eq (11): Annual change (p12)
- Exact: `∆C_TREE,t = (C_TREE,t2 − C_TREE,t1) / T × 1 year`
- LaTeX: `\Delta C_{TREE,t} = \frac{C_{TREE,t_2} - C_{TREE,t_1}}{T} \times 1\,year`
- T = t2 − t1 in years, may be fractional (4 yr 5 mo -> 4.417). Linear change assumed between verifications. Where different methods are used in different strata, C_TREE is the sum over strata.

#### Stock at a point in time (sec 4.8)
Methods: (a) sample-plot measurement; (b) modelling of growth (ex-ante, no uncertainty control, para 53); (c) proportionate crown cover (pre-project baseline stock only); (d) updating previous stock by independent measurement of change. Date of estimation = date of last plot measurement / crown-cover estimate.

#### Eq (12)-(17): Stratified random sampling (p14-15)
Plots installed randomly (e.g. systematic with random start). Number/allocation of plots may use the A/R tool "Calculation of the number of sample plots..." (not supplied).
- Eq (12) Exact: `C_TREE = 44/12 × CF_TREE × B_TREE`; LaTeX: `C_{TREE} = \frac{44}{12} \times CF_{TREE} \times B_{TREE}`
- Eq (13) Exact: `B_TREE = A × b_TREE`; LaTeX: `B_{TREE} = A \times b_{TREE}`
- Eq (14) Exact: `b_TREE = Σ_{i=1}^{M} w_i × b_TREE,i`; LaTeX: `b_{TREE} = \sum_{i=1}^{M} w_i \times b_{TREE,i}`
- Eq (15) Exact: `u_C = t_VAL × √(Σ_{i=1}^{M} w_i² × s_i²/n_i) / b_TREE`
  LaTeX: `u_C = \frac{t_{VAL} \times \sqrt{\sum_{i=1}^{M} w_i^2 \times \frac{s_i^2}{n_i}}}{b_{TREE}}`
- Eq (16) Exact: `b_TREE,i = Σ_{p=1}^{n_i} b_TREE,p,i / n_i`; LaTeX: `b_{TREE,i} = \frac{\sum_{p=1}^{n_i} b_{TREE,p,i}}{n_i}`
- Eq (17) Exact: `s_i² = (n_i × Σ_{p=1}^{n_i} b²_TREE,p,i − (Σ_{p=1}^{n_i} b_TREE,p,i)²) / (n_i × (n_i − 1))`
  LaTeX: `s_i^2 = \frac{n_i \times \sum_{p=1}^{n_i} b_{TREE,p,i}^2 - \left(\sum_{p=1}^{n_i} b_{TREE,p,i}\right)^2}{n_i \times (n_i - 1)}`

| Var | Meaning | Unit |
|---|---|---|
| C_TREE | Carbon stock in trees in the tree biomass estimation strata | t CO2e |
| CF_TREE | default 0.47 | t C (t d.m.)-1 |
| B_TREE | Tree biomass in the strata | t d.m. |
| A | Sum of stratum areas | ha |
| b_TREE | Mean tree biomass per ha in the strata | t d.m. ha-1 |
| w_i | A_i / A | dimensionless |
| b_TREE,i | Mean tree biomass per ha in stratum i | t d.m. ha-1 |
| b_TREE,p,i | Tree biomass per ha in plot p of stratum i | t d.m. ha-1 |
| u_C | Uncertainty in C_TREE | fraction/% |
| t_VAL | Two-sided Student's t, 90 % confidence, df = n − M | - |
| s_i² | Variance of tree biomass per ha across plots in stratum i (Eq 15 list); "variance of mean" (Eq 17 list) (A8) | (t d.m. ha-1)² |
| n_i | Number of plots in stratum i | - |

Para 38: if u_C > 10 %, C_TREE is made conservative by Appendix 2.

#### Eq (18)-(19): Double sampling (p15-17)
Secondary variable (e.g. basal area, NDVI) measured on all plots; biomass on a sub-sample; requires linear relationship. Eq (12)-(15) still aggregate across strata; Eq (18)-(19) replace (16)-(17) in double-sampled strata.
- Eq (18) Exact: `b_TREE,i = Σ_{p=1}^{n_i} b_TREE,p,i / n_i + β × (x̄′ − x̄)`
  LaTeX: `b_{TREE,i} = \frac{\sum_{p=1}^{n_i} b_{TREE,p,i}}{n_i} + \beta \times (\bar{x}' - \bar{x})`
- Eq (19) Exact: `s_i² = (n_i × Σ_{p=1}^{n_i} b²_TREE,p,i − (Σ_{p=1}^{n_i} b_TREE,p,i)²) / (n_i × (n_i − 1)) × (1 − (1 − α) × ρ²)`
  LaTeX: `s_i^2 = \frac{n_i \sum_{p=1}^{n_i} b_{TREE,p,i}^2 - \left(\sum_{p=1}^{n_i} b_{TREE,p,i}\right)^2}{n_i (n_i - 1)} \times \left(1 - (1-\alpha)\rho^2\right)`

| Var | Meaning (corrected per A10) | Unit |
|---|---|---|
| n_i | Number of sample plots in the sub-sample (where biomass measured) | - |
| b_TREE,p,i | Tree biomass per ha in plot p | t d.m. ha-1 |
| β | Slope of regression of plot biomass on secondary variable (Appendix 3) | - |
| x̄′ | Mean of secondary variable across all sample plots | var. unit |
| x̄ | Mean of secondary variable across the sub-sample | var. unit |
| α | Ratio of number of sub-sample plots to number of sample plots (α < 1) | - |
| ρ | Correlation coefficient between secondary variable and plot biomass, over the sub-sample | - |

Para 48: discount if u_C (Eq 15) > 10 %.

#### Eq (20)-(21): Pre-project baseline tree stock by proportionate crown cover (p18)
Same applicability (< 20 % of threshold crown cover; area stratified by pre-project crown cover).
- Eq (20) Exact: `C_TREE_BSL = Σ_{i=1}^{M} C_TREE_BSL,i`; LaTeX: `C_{TREE\_BSL} = \sum_{i=1}^{M} C_{TREE\_BSL,i}`
- Eq (21) Exact: `C_TREE_BSL,i = 44/12 × CF_TREE × b_FOREST × (1 + R_TREE) × CC_TREE_BSL,i × A_i`
  LaTeX: `C_{TREE\_BSL,i} = \frac{44}{12} \times CF_{TREE} \times b_{FOREST} \times (1 + R_{TREE}) \times CC_{TREE\_BSL,i} \times A_i`

| Var | Meaning | Unit |
|---|---|---|
| C_TREE_BSL(,i) | Carbon stock in pre-project tree biomass (stratum i) | t CO2e |
| CF_TREE | default 0.47 | t C (t d.m.)-1 |
| b_FOREST | Mean above-ground biomass in forest in region/country; latest IPCC GPG-LULUCF unless justified | t d.m. ha-1 |
| R_TREE | default 0.25 | - |
| CC_TREE_BSL,i | Crown cover fraction at project start (measured once; for slash-and-burn/cyclic land use half the maximum crown cover of the cycle) | - |
| A_i | Area of baseline stratum i | ha |

#### Eq (22)-(23): Updating previous stock by measured change (p18-19)
New stock = previous stock + change by re-measurement (Eq 3-8). Note in source: efficient because tCCCs are based on total carbon stock.
- Eq (22) Exact: `C_TREE,t2 = C_TREE,t1 + ∆C_TREE`; LaTeX: `C_{TREE,t_2} = C_{TREE,t_1} + \Delta C_{TREE}`
- Eq (23) Exact: `u2 = √((u1 × C_TREE,t1)² + (u_∆C × ∆C_TREE)²) / C_TREE,t2`
  LaTeX: `u_2 = \frac{\sqrt{(u_1 \times C_{TREE,t_1})^2 + (u_{\Delta C} \times \Delta C_{TREE})^2}}{C_{TREE,t_2}}`
- C_TREE,t1 undiscounted. Para 61: if u2 > 10 %, discount C_TREE,t2 (Appendix 2).

#### Eq (24)-(27): Shrubs (p19-21)
- Eq (24) Exact: `∆C_SHRUB = C_SHRUB,t2 − C_SHRUB,t1`; LaTeX: `\Delta C_{SHRUB} = C_{SHRUB,t_2} - C_{SHRUB,t_1}`
  ("No decrease" mutatis mutandis -> ∆C_SHRUB = 0 for those strata, para 64.)
- Eq (25) Exact: `∆C_SHRUB,t = (C_SHRUB,t2 − C_SHRUB,t1) / T × 1 year`; LaTeX: `\Delta C_{SHRUB,t} = \frac{C_{SHRUB,t_2} - C_{SHRUB,t_1}}{T} \times 1\,year`
- Stratify by shrub crown cover; areas with shrub crown cover < 5 % -> single stratum with zero shrub biomass (para 67). For strata > 5 %:
- Eq (26) Exact: `C_SHRUB,t = 44/12 × CF_s × (1 + R_s) × Σ_i A_SHRUB,i × b_SHRUB,i`
  LaTeX: `C_{SHRUB,t} = \frac{44}{12} \times CF_s \times (1 + R_s) \times \sum_i A_{SHRUB,i} \times b_{SHRUB,i}`
- Eq (27) Exact: `b_SHRUB,i = BDR_SF × b_FOREST × CC_SHRUB,i`; LaTeX: `b_{SHRUB,i} = BDR_{SF} \times b_{FOREST} \times CC_{SHRUB,i}`

| Var | Meaning | Unit / default |
|---|---|---|
| C_SHRUB,t | Carbon stock in shrubs at a point of time in year t | t CO2-e |
| CF_s | Carbon fraction of shrub biomass | 0.47 default, t C (t d.m.)-1 |
| R_s | Root-shoot ratio for shrubs | 0.40 default |
| A_SHRUB,i | Area of shrub stratum i | ha |
| b_SHRUB,i | Shrub biomass per ha in stratum i | t d.m. ha-1 |
| BDR_SF | Ratio of shrub biomass per ha at 100 % shrub crown cover to default forest AGB per ha | 0.10 default |
| b_FOREST | Default AGB in forest in region/country (latest IPCC GPG-LULUCF) | t d.m. ha-1 |
| CC_SHRUB,i | Shrub crown cover fraction at time of estimation (ocular, line transect, relascope; every verification; cyclic land: average 0.5 unless justified) | - |

#### Appendix 1: Plot biomass (p24-29)
Fixed-area plots: measure individual tree dimensions (DBH, root-collar diameter, height); variable-area (angle-count) plots: basal area per ha. Conversion: allometric equations, BEF, or both. Fixed plot example size 1/10 or 1/20 ha; minimum measured diameter e.g. 2 cm or 10 cm depending on model range. Saplings below the allometric range: harvest saplings near the mid-way diameter outside the plot, mean biomass × count.

- App1 Eq (1) Exact: `b_TREE,p,i = B_TREE,p,i / A_PLOT,i`; LaTeX: `b_{TREE,p,i} = \frac{B_{TREE,p,i}}{A_{PLOT,i}}`
- App1 Eq (2) Exact: `B_TREE,p,i = Σ_j B_TREE,j,p,i`; LaTeX: `B_{TREE,p,i} = \sum_j B_{TREE,j,p,i}`
- App1 Eq (3) Exact: `B_TREE,j,p,i = Σ_l B_TREE,l,j,p,i`; LaTeX: `B_{TREE,j,p,i} = \sum_l B_{TREE,l,j,p,i}`
- App1 Eq (4) Exact: `B_TREE,l,j,p,i = f_j(x1,l, x2,l, x3,l, …) × (1 + R_j)`; LaTeX: `B_{TREE,l,j,p,i} = f_j(x_{1,l}, x_{2,l}, x_{3,l}, \ldots) \times (1 + R_j)`
- App1 Eq (5) Exact: `B_TREE,l,j,p,i = V_TREE,j(x1,l, x2,l, x3,l, …) × D_j × BEF_2,j × (1 + R_j)`; LaTeX: `B_{TREE,l,j,p,i} = V_{TREE,j}(x_{1,l}, x_{2,l}, x_{3,l}, \ldots) \times D_j \times BEF_{2,j} \times (1 + R_j)`
- App1 Eq (6) (variable plots) Exact: `b_TREE,p,i = Σ_j b_TREE,j,p,i`
- App1 Eq (7) Exact: `b_TREE,j,p,i = f_j(BA_p,i) × (1 + R_j)`
- App1 Eq (8) Exact: `b_TREE,j,p,i = v_TREE,j(BA_p,i) × D_j × BEF_2,j × (1 + R_j)`

| Var | Meaning | Unit / default |
|---|---|---|
| b_TREE,p,i | Tree biomass per ha in plot p of stratum i | t d.m. ha-1 |
| B_TREE,p,i | Tree biomass in plot p | t d.m. |
| A_PLOT,i | Size of sample plot in stratum i | ha |
| B_TREE,j,p,i | Biomass of trees of species j in plot | t d.m. |
| B_TREE,l,j,p,i | Biomass of tree l of species j | t d.m. |
| f_j(x…) | AGB of tree from species-j allometric equation (apply in the equation's native units, convert result to t) | t d.m. |
| R_j | Root-shoot ratio species j; `R_j = e^(−1.085 + 0.9256 × ln b) / b` (LaTeX `R_j = \frac{e^{(-1.085 + 0.9256 \times \ln b)}}{b}`) where b = above-ground tree biomass per hectare (t d.m. ha-1), unless justified. Coppice after harvest: multiply R_j by max(v_HARVEST / v_TREE, 1) (v_HARVEST = harvested volume/ha, v_TREE = standing volume/ha) | - |
| V_TREE,j(x…) | Stem volume of tree l from volume table/equation (correct under-bark to over-bark) | m³ |
| D_j | Density (over-bark) of species j; IPCC GPG-LULUCF latest unless justified; correct conservatively for bark density | t d.m. m-3 |
| BEF_2,j | BEF stem biomass -> AGB; ex-ante selected per para 7 procedure (mutatis mutandis); ex-post conservative default 1.15 unless justified | - |
| f_j(BA_p,i) | AGB per ha from basal-area allometry | t d.m. ha-1 |
| v_TREE,j(BA_p,i) | Stem volume per ha from basal area | m³ ha-1 |

Model source hierarchy, ex-ante (para 6): (a) local existing data; (b) national (NFI / GHG inventory); (c) neighbouring countries; (d) global. Ex-post (para 7): allometric equations must pass the tool "Demonstrating appropriateness of allometric equations for estimation of aboveground tree biomass in A/R ICM project activities"; volume equations the tool "Demonstrating appropriateness of volume equations ..." (neither supplied).

#### Appendix 2: Uncertainty discount (p29)
When uncertainty U of an estimated mean > 10 %, the mean is increased (baseline) or decreased (project) by a percentage of the uncertainty (of the half-width):

| Uncertainty U | Discount (% of U) |
|---|---|
| U ≤ 10 % | 0 % |
| 10 < U ≤ 15 | 25 % |
| 15 < U ≤ 20 | 50 % |
| 20 < U ≤ 30 | 75 % |
| U > 30 | 100 % |

Example: mean 60 ± 9 t d.m./ha, U = 9/60 × 100 = 15 % -> discount = 25 % × 9 = 2.25; baseline 62.25, project 57.75.
Implementable form (derived, not printed): conservative_project = mean − DF × U × mean; conservative_baseline = mean + DF × U × mean, with U as fraction and DF from table.

#### Appendix 3: Correlation and slope (p30)
- App3 Eq (1) Exact: `β = ρ × s_y / s_x`; LaTeX: `\beta = \rho \times \frac{s_y}{s_x}`
- App3 Eq (2) Exact: `ρ = Σ_{i=1}^{n}{(x_i − x̄)(y_i − ȳ)} / √(Σ_{i=1}^{n}(x_i − x̄)² × Σ_{i=1}^{n}(y_i − ȳ)²)`
  LaTeX: `\rho = \frac{\sum_{i=1}^{n} (x_i - \bar{x})(y_i - \bar{y})}{\sqrt{\sum_{i=1}^{n}(x_i - \bar{x})^2 \times \sum_{i=1}^{n}(y_i - \bar{y})^2}}`
- s_y, s_x sample standard deviations; y = dependent (plot biomass), x = independent (secondary variable).

#### Monitored parameters (sec 6.2)
| Parameter | Unit | Source | Frequency |
|---|---|---|---|
| A_PLOT,i, A_SHRUB,i, A_i | ha | field measurement (NFI SOPs / handbooks / IPCC GPG-LULUCF) | every verification |
| CC_SHRUB,i | - | field (ocular, line transect, relascope) | every verification |
| CC_TREE_BSL,i | - | field (simplified methods allowed) | once, at project start |
Non-monitored defaults are those in the equation tables above.

**AR-0004 default values summary**: CF_TREE 0.47; CF_s 0.47; R_TREE (baseline) 0.25; R_s 0.40; R_j formula (Mokany-type) with b in t d.m./ha; BEF_2,j ex-post 1.15; BDR_SF 0.10; b_FOREST and ∆b_FOREST (MAI_FOR) from IPCC GPG-LULUCF (Table 3A.1.5 for MAI); D_j from IPCC GPG-LULUCF. No wood-density, BEF or b_FOREST tables are reproduced in the tool - values must be taken from IPCC GPG-LULUCF.
**Thresholds**: uncertainty discount above 10 % (90 % CI); crown-cover method only if pre-project crown cover < 20 % of national threshold; shrub stratum < 5 % crown cover = zero.

### 2.2 BM-T-AR-0003 - Dead wood and litter

Scope: dead wood and/or litter stocks and changes, baseline and project. No internal applicability conditions. Assumptions: linear change between estimations; living-tree root-shoot ratios valid for dead trees. Same strata and plots as living tree biomass unless justified. Notation: C_DW,BSL,t / C_LI,BSL,t / ∆C_DW,BSL,t / ∆C_LI,BSL,t (baseline), C_DW,PROJ,t etc. (project). No sampling-uncertainty procedure in this tool (A13).

**Standing dead wood categories (para 12, numbering garbled - A11)**: dead trees that have lost only leaves and twigs -> biomass reduction factor 0.975; dead trees that have lost leaves, twigs and small branches (diameter < 10 cm) -> factor 0.80 (source: IPCC GPG-LULUCF Dead Organic Matter). Other dead trees and stumps -> stump method (para 20-24). Measured in sample plots (or all dead trees where few and scattered).

- Eq (1) BEF method. Exact (as printed): `B_DWS_TREE,j,p,i,t = D_j × BEF2,j × (1+D_j) × Σ_{k=1}^{n} (V_TREE,j × (DBH_k, H_k) × α_k)`
  Intended: `B_DWS_TREE,j,p,i,t = D_j × BEF_2,j × (1 + R_j) × Σ_{k=1}^{n} (V_TREE,j(DBH_k, H_k) × α_k)` (A12)
  LaTeX (intended): `B_{DWS\_TREE,j,p,i,t} = D_j \times BEF_{2,j} \times (1 + R_j) \times \sum_{k=1}^{n} \left( V_{TREE,j}(DBH_k, H_k) \times \alpha_k \right)`
- Eq (2) Allometric. Exact: `B_DW_TREE,j,p,i,t = (1+R_j) × Σ_{k=1}^{n} (f_j(DBH_k, H_k) × α_k)`
  LaTeX: `B_{DW\_TREE,j,p,i,t} = (1 + R_j) \times \sum_{k=1}^{n} \left( f_j(DBH_k, H_k) \times \alpha_k \right)`
- Eq (3) Exact: `C_DWS_TREE,j,p,i,t = 44/12 × CF_TREE × B_DWS_TREE,j,p,i,t`; LaTeX: `C_{DWS\_TREE,j,p,i,t} = \frac{44}{12} \times CF_{TREE} \times B_{DWS\_TREE,j,p,i,t}`

| Var | Meaning | Unit |
|---|---|---|
| B_DWS_TREE,j,p,i,t | Dead wood biomass in standing dead trees, species j, plot p, stratum i, year t | t d.m. |
| V_TREE,j(DBH_k,H_k) | Stem volume of k-th dead tree from volume function | m³ |
| DBH_k, H_k | Diameter / height of k-th dead tree (unit of the volume function) | m or other |
| α_k | Biomass reduction factor (0.975 or 0.80 by category) | - |
| D_j | Basic wood density species j | t d.m. m-3 |
| BEF_2,j | Stem -> AGB expansion factor | - |
| R_j | Root-shoot ratio species j | - |
| f_j(DBH_k,H_k) | AGB of k-th dead tree from allometric function | t d.m. |
| CF_TREE | Carbon fraction of tree biomass; **0.5** in this tool's parameter table (A14) | t C (t d.m.)-1 |

Volume/allometric equations must pass the appropriateness tools.

**Stumps (para 20-24)**: decay class by machete test: Sound (density reduction factor 1.00), Intermediate (0.80), Rotten (0.45) (Harmon and Sexton 1996). Stumps < 4 m: mid-height diameter measured; ≥ 4 m: DBH measured and mid-height diameter estimated:
- Eq (4) Exact (as printed): `D_MID_STUMP = 0.57×DBH_k × (H_STUMP /H_STUMP − H_DBH)0.80 for H_STUMP ≥ 4m`
  Intended (Ormerod 1973): `D_MID_STUMP = 0.57 × DBH_k × (H_STUMP / (H_STUMP − H_DBH))^0.80` (A12)
  LaTeX (intended): `D_{MID\_STUMP} = 0.57 \times DBH_k \times \left(\frac{H_{STUMP}}{H_{STUMP} - H_{DBH}}\right)^{0.80}`
  Units: all m.
- Eq (5) Exact (as printed): `C_DW_STUMP,j,p,i,t = 44/12×CF_TREE× D_j×(1+R_j)×π/4 Σ_k(D_MIDSTIUMP,k2×H_k×β_k)`
  Intended: `C_DW_STUMP,j,p,i,t = 44/12 × CF_TREE × D_j × (1 + R_j) × π/4 × Σ_k (D_MID_STUMP,k² × H_k × β_k)`
  LaTeX: `C_{DW\_STUMP,j,p,i,t} = \frac{44}{12} \times CF_{TREE} \times D_j \times (1 + R_j) \times \frac{\pi}{4} \sum_k \left( D_{MID\_STUMP,k}^2 \times H_k \times \beta_k \right)`
  D_MID_STUMP,k in m; H_k in m; β_k density reduction factor.

**Lying dead wood (para 25-27)**: line-intersect method; two transects of total length ≥ 100 m roughly orthogonally bisecting at plot centre (more lines allowed if parcel too small; parallel lines ≥ 20 m apart); measure pieces with diameter ≥ 10 cm; decay classes as above.
- Eq (6) Exact (as printed): `C_DWL,j,p,i,t = a_plot × 44/12 × CF_TREE × D_j × π2/8L × Σ_{n=1}^{N}(D_n2 × β_n)`
  Intended: `C_DWL,j,p,i,t = a_plot × 44/12 × CF_TREE × D_j × π²/(8L) × Σ_{n=1}^{N} (D_n² × β_n)`
  LaTeX: `C_{DWL,j,p,i,t} = a_{plot} \times \frac{44}{12} \times CF_{TREE} \times D_j \times \frac{\pi^2}{8L} \times \sum_{n=1}^{N} \left( D_n^2 \times \beta_n \right)`
  a_plot plot area (ha); L total transect length (m); D_n diameter (cm); β_n density reduction factor. (π²ΣD²/(8L) with D in cm and L in m yields m³/ha.)
- Eq (7) Exact: `C_DW,i,t = A_i / A_plot,i Σ_p Σ_j (C_DWS_TREE,j,p,i,t + C_DWSTUMP,j,p,i,t + C_DWL,j,p,i,t)`
  LaTeX: `C_{DW,i,t} = \frac{A_i}{A_{plot,i}} \sum_p \sum_j \left( C_{DWS\_TREE,j,p,i,t} + C_{DW\_STUMP,j,p,i,t} + C_{DWL,j,p,i,t} \right)`
  A_i stratum area (ha); A_plot,i total area of sample plots in stratum (ha).
- Eq (8) Exact: `C_DW,t = Σ_i C_DW,i,t`
- Eq (9) Default factor. Exact: `C_DW,i,t = C_TREE,i,t × DF_DW`; LaTeX: `C_{DW,i,t} = C_{TREE,i,t} \times DF_{DW}`
  Only if dead wood remains in situ (not removed by anthropogenic activity). C_TREE,i,t from AR-0004 (t CO2e). DF_DW in per cent (apply /100).
- Eq (10) Exact: `dC_DW,(t1,t2) = C_DW,t2 − C_DW,t1 / T` (intended `(C_DW,t2 − C_DW,t1)/T`); unit t CO2e yr-1
- Eq (11) Exact: `∆C_DW,t = dC_DW,(t1,t2) × 1 year for t1 ≤ t ≤ t2`
- Litter measurement (para 37): four samples per plot with a sampling frame at random positions, composited, wet weight; oven-dried sub-sample gives dry-to-wet ratio.
- Eq (12) Exact: `C_L,p,i,t = 44/12 × CF_LI × 2.5 × A_p,i / a_p,i × B_LI,wet,p,i × DWR_LI,p,i`
  LaTeX: `C_{L,p,i,t} = \frac{44}{12} \times CF_{LI} \times 2.5 \times \frac{A_{p,i}}{a_{p,i}} \times B_{LI,wet,p,i} \times DWR_{LI,p,i}`
  CF_LI 0.37 (IPCC default); B_LI,wet in kg; DWR dimensionless; A_p,i plot area (ha); a_p,i frame area (m², often 0.50 m²). (2.5 = 10 (kg/m² -> t/ha) / 4 frames - inferred, not stated.)
- Eq (13) Exact: `C_L,i,t = A_i / A_plot,i Σ_p C_LI,p,i,t`
- Eq (14) Exact: `C_LI,t = Σ_i C_LI,i,t`
- Eq (15) Default factor. Exact: `C_LI,i,t = C_TREE,i,t × DF_LI` (only if litter remains in situ)
- Eq (16) Exact: `dC_LI,(t1,t2) = C_LI,t2 − C_LI,t1 / T` (intended `(C_LI,t2 − C_LI,t1)/T`)
- Eq (17) Exact: `∆C_LI,t = dC_LI,(t1,t2) × 1 year for t1 ≤ t ≤ t2`

**DF tables (p16-17)** (Delaney 1997, Smith 2006, Glenday 2008, Keller 2004, Eaton & Lawrence 2006, Krankina & Harmon 1995, Clark 2002):

| Biome | Elevation | Precipitation | DF_DW | DF_LI |
|---|---|---|---|---|
| Tropical | < 2000 m | < 1000 mm yr-1 | 2 % | 4 % |
| Tropical | < 2000 m | 1000-1600 mm yr-1 | 1 % | 1 % |
| Tropical | < 2000 m | > 1600 mm yr-1 | 6 % | 1 % |
| Tropical | > 2000 m | All | 7 % | 1 % |
| Temperate/boreal | All | All | 8 % | 4 % |

**Other AR-0003 parameters**: BEF_2,j from IPCC GPG-LULUCF; if applied to open-grown trees, increase BEF by 30 %. D_j from IPCC GPG-LULUCF. R_j = exp[−1.085 + 0.9256 × ln(A)]/A, A = AGB (t d.m./ha). Monitored (every five years since initial verification): A_i, A_PLOT,i, a_p,i, B_LI_WET,p,i, DBH, D_n (cm), H; T recorded (fractional allowed).

### 2.3 BM-T-AR-0002 - Non-CO2 emissions from biomass burning

Applicability: all fire occurrences in the boundary. Emissions accounted for each fire incidence affecting an area greater than the host Party's minimum forest area threshold, provided the accumulated area affected by such fires in a year is ≥ 5 % of the project area. Assumptions: living-tree AGB not significantly emitting if fire stays in understory or singes trees with leaf regeneration within six months; 60 % of dead organic matter is entirely burnt in all fires.

- Eq (1) Exact: `GHG_E,t = GHG_SPF,t + GHG_FMF,t + GHG_FF,t`; LaTeX: `GHG_{E,t} = GHG_{SPF,t} + GHG_{FMF,t} + GHG_{FF,t}` (site-preparation fire; harvest-residue/forest-management fire; forest fire; all t CO2-e)
- Eq (2): `GHG_SPF,t = 0` where (i) slash-and-burn is common in the baseline AND (ii) fire used at least once in the ten years before project start.
- Eq (3) Exact (as printed): `GHG_SPF,t=i= 0.07 * Σ_{i=1}^{M}(A_SPF,t,i * 44/12 * (CF_TREE * b_TREE,i,t + BDR_SF * CF_SHRUB * CC_SHRUB,i,t * B_FOREST)`
  Intended: `GHG_SPF,t = 0.07 × Σ_{i=1}^{M} [A_SPF,t,i × 44/12 × (CF_TREE × b_TREE,i,t + BDR_SF × CF_SHRUB × CC_SHRUB,i,t × B_FOREST)]`
  LaTeX: `GHG_{SPF,t} = 0.07 \times \sum_{i=1}^{M} A_{SPF,t,i} \times \frac{44}{12} \times \left( CF_{TREE} \times b_{TREE,i,t} + BDR_{SF} \times CF_{SHRUB} \times CC_{SHRUB,i,t} \times B_{FOREST} \right)`

| Var | Meaning | Unit / default |
|---|---|---|
| 0.07 | Ratio of non-CO2 (CH4 + N2O) to CO2 emissions from burning (adapted IPCC 2006 Table 2.5) | - |
| A_SPF,t,i | Area where fire used in site preparation, stratum i, year t | ha |
| CF_TREE / CF_SHRUB | Carbon fraction | 0.50 (IPCC default) |
| b_TREE,i,t | Mean tree biomass per ha in stratum at project start (AR-0004); zero if pre-project trees not burned | t d.m. ha-1 |
| BDR_SF | 0.10 default | - |
| CC_SHRUB,i,t | Shrub crown cover at project start where fire used | - |
| B_FOREST | Default AGB in forest of region/country (NFI > neighbouring > global (FAO) > IPCC GPG-LULUCF) | t d.m. ha-1 |

- Eq (4) Exact: `GHG_FMF,t = 0.07*44/12 * B_HARVEST,t * f_BL * CF_TREE`; LaTeX: `GHG_{FMF,t} = 0.07 \times \frac{44}{12} \times B_{HARVEST,t} \times f_{BL} \times CF_{TREE}`
  B_HARVEST,t biomass harvested from area burned for residue clearing (t d.m.); f_BL fraction of AGB left on site: 0.10 temperate, 0.25 tropical (IPCC GPG-LULUCF Table 3A.1.11); CF_TREE 0.50.
- Eq (5) Exact: `B_HARVEST,t = B_FOREST / BEF2 * A_FMF,t`; LaTeX: `B_{HARVEST,t} = \frac{B_{FOREST}}{BEF_2} \times A_{FMF,t}` (BEF_2 = 1.25; A_FMF,t ha) - used when harvest data unavailable.
- Eq (6) Exact: `GHG_FF,t = GHG_FF_TREE,t + GHG_FF_DOM,t`
- Eq (7) Exact: `GHG_FF_TREE,t = 0.001 * Σ A_BURN,i,t * b_TREE,i,tL * COMF_i * (EF_CH4,i * GWP_CH4 + EF_N2O,i * GWP_N2O)`
  LaTeX: `GHG_{FF\_TREE,t} = 0.001 \times \sum_{i=1}^{M} A_{BURN,i,t} \times b_{TREE,i,t_L} \times COMF_i \times \left( EF_{CH4,i} \times GWP_{CH4} + EF_{N2O,i} \times GWP_{N2O} \right)`
  Zero at first verification. b_TREE,i,tL = mean AGB per ha at last verification before the fire (t d.m. ha-1); may be zero if living AGB not burnt.
- Eq (8) Exact: `GHG_FF_DOM,t = 0.07 * Σ_{i=1}^{M} A_BURN,i,t * (C_DW,i,tL + C_LI,i,tL)`
  LaTeX: `GHG_{FF\_DOM,t} = 0.07 \times \sum_{i=1}^{M} A_{BURN,i,t} \times \left( C_{DW,i,t_L} + C_{LI,i,t_L} \right)`
  Zero if DOM pools not accounted, and zero for the first verification period. C_DW,i,tL, C_LI,i,tL from AR-0003 (t CO2-e) (unit issue A16).

**Defaults**: GWP_CH4 = 21; GWP_N2O = 310. EF_CH4: tropical forest 6.8, other forest 4.7 g kg-1 d.m. burnt. EF_N2O: tropical 0.20, other 0.26 g kg-1. COMF (combustion factor) defaults: tropical forest by mean age 3-5 yr 0.46, 6-10 yr 0.67, 11-17 yr 0.50, ≥18 yr 0.32 (table layout garbled - A17); boreal 0.40; temperate 0.45. EF/COMF source hierarchy: project-specific/national > neighbouring > global > default. Monitored: A_SPF,t and CC_SHRUB,t (whenever fire used in site prep), A_FMF,t (whenever residue burning), A_BURN,i,t (whenever forest fire; GPS or georeferenced RS).

### 2.4 BM-T-AR-0005 - Leakage from displacement of agricultural activities

Not applicable if displacement causes, directly or indirectly, drainage of wetlands or peat lands. Leakage = decrease in carbon stocks in land receiving the displaced activity; market/secondary effects = zero. Grazing displacement leakage = zero if animals go to: (a) existing grazing land within carrying capacity; (b) existing non-grazing grassland within carrying capacity; (c) cropland abandoned within last five years; (d) forested land with no tree clearance or crown-cover decrease; (e) zero-grazing system.

- Eq (1) Exact: `LK_AGRIC,t = 44/12 × (∆C_BIOMASS,t + ∆SOC_LUC,t)`; LaTeX: `LK_{AGRIC,t} = \frac{44}{12} \times (\Delta C_{BIOMASS,t} + \Delta SOC_{LUC,t})`
- Eq (2) Exact: `∆C_BIOMASS,t = [1.1 × b_TREE × (1 + R_TREE) + b_SHRUB × (1 + R_S)] × CF × A_DISP,t`
  LaTeX: `\Delta C_{BIOMASS,t} = \left[ 1.1 \times b_{TREE} \times (1 + R_{TREE}) + b_{SHRUB} \times (1 + R_S) \right] \times CF \times A_{DISP,t}`
- Eq (3) Exact: `∆SOC_LUC,t = SOC_REF × (f_LUP × f_MGP × f_INP − f_LUD × f_MGD × f_IND) × A_DISP,t`
  LaTeX: `\Delta SOC_{LUC,t} = SOC_{REF} \times (f_{LUP} f_{MGP} f_{INP} - f_{LUD} f_{MGD} f_{IND}) \times A_{DISP,t}`

| Var | Meaning | Unit / default |
|---|---|---|
| LK_AGRIC,t | Leakage emission in year t | t CO2e |
| ∆C_BIOMASS,t | Decrease in carbon stock in receiving land (printed unit t d.m.; A18) | |
| 1.1 | factor for dead wood and litter as fixed % of living trees | - |
| CF | Carbon fraction woody biomass | 0.47 |
| A_DISP,t | Area from which agricultural activity is displaced in year t (monitored every verification) | ha |
| b_TREE | Mean AGB of trees in receiving land (AR-0004); if receiving land unidentified, mean AGB of forest in region/country (IPCC GPG-LULUCF) | t d.m. ha-1 |
| R_TREE | 0.25 | - |
| b_SHRUB | Mean AGB of shrubs in receiving land (AR-0004) | t d.m. ha-1 |
| R_S | 0.40 | - |
| ∆SOC_LUC,t | SOC change in receiving land (printed unit tC ha-1); set zero if only grazing received or if Eq 3 negative | |
| SOC_REF | Reference SOC (AR-0006 "Table 3", actually Table 4) | t C ha-1 |
| f_LUP, f_MGP, f_INP | factors before receiving (AR-0006 "Tables 4, 5, 6") | - |
| f_LUD, f_MGD, f_IND | factors after receiving | - |

Multiple receiving land types: apply Eq 1-3 to each and sum.

### 2.5 BM-T-AR-0006 - SOC

Applicability: land (i) not wetland; or (ii) no organic soils; (iii) not under the baseline management/input practices in the non-applicability tables (A19 on "or"); project: litter stays on site; soil disturbance per soil-conservation practice (e.g. contours) and limited to site preparation, not repeated in less than twenty years. Assumptions: site prep and planting within a year; SOC rises to native steady-state; constant rate over 20 years from planting. Stratify by climate/soil (SOC_REF table), cropland management, grassland management.

- Eq (1) Exact: `SOC_INITIAL,i = SOC_REF,i * f_LU,i * f_MG,i * f_IN,i`; LaTeX: `SOC_{INITIAL,i} = SOC_{REF,i} \times f_{LU,i} \times f_{MG,i} \times f_{IN,i}` (t C ha-1)
- Eq (2): `SOC_LOSS,i = SOC_INITIAL,i * 0.1` - for strata where total project soil disturbance (over and above baseline) > 10 % of stratum area (0.1 = approx. proportion of SOC lost within first five years after site preparation)
- Eq (3): `SOC_LOSS,i = 0` - all other strata
- Eq (4): `dSOC_t,i = 0 for t < t_PREP,i`
- Eq (5) Exact: `dSOC_t,i = − SOC_LOSS,i / 1 year for t = t_PREP,i`; LaTeX: `dSOC_{t,i} = -\frac{SOC_{LOSS,i}}{1\,year}`
- Eq (6) Exact: `dSOC_t,i = (SOC_REF,i − (SOC_INITIAL,i − SOC_LOSS,i)) / 20 years for t_PREP,i < t ≤ t_PREP,i + 20`
  LaTeX: `dSOC_{t,i} = \frac{SOC_{REF,i} - (SOC_{INITIAL,i} - SOC_{LOSS,i})}{20\,years}`
- Eq (7): If dSOC_t,i > 0.8 t C ha-1 yr-1 then dSOC_t,i = 0.8 t C ha-1 yr-1
- Eq (8) Exact: `∆SOC_AL,t = 44/12 * Σ_i A_i * dSOC_t,i * 1 year`; LaTeX: `\Delta SOC_{AL,t} = \frac{44}{12} \times \sum_i A_i \times dSOC_{t,i} \times 1\,year` (t CO2e)
- t_PREP,i = year of first soil disturbance in stratum i. (After t_PREP + 20, dSOC not defined; implied 0 - A19.)

**Table 4 SOC_REF, mineral soils, t C ha-1, 0-30 cm (IPCC 2006)**

| Climate | HAC | LAC | Sandy | Spodic | Volcanic |
|---|---|---|---|---|---|
| Boreal | 68 | NA | 10 | 117 | 20 |
| Cold temperate, dry | 50 | 33 | 34 | NA | 20 |
| Cold temperate, moist | 95 | 85 | 71 | 115 | 130 |
| Warm temperate, dry | 38 | 24 | 19 | NA | 70 |
| Warm temperate (moist) | 88 | 63 | 34 | NA | 80 |
| Tropical, dry | 38 | 35 | 31 | NA | 50 |
| Tropical, moist | 65 | 47 | 39 | NA | 70 |
| Tropical, wet | 44 | 60 | 66 | NA | 130 |
| Tropical montane | 88 | 63 | 34 | NA | 80 |

**Table 5 cropland factors (20 yr)**: f_LU long-term cultivated (> 20 yr): Temperate/Boreal dry 0.80, moist 0.69; Tropical dry 0.58, moist/wet 0.48; Tropical montane 0.64. f_LU short-term (< 20 yr) or set-aside (< 5 yr): Temperate/Boreal and Tropical dry 0.93, moist/wet 0.82; Tropical montane 0.88. f_MG full tillage: all 1.00. f_MG reduced tillage: Temperate/Boreal dry 1.02, moist 1.08; Tropical dry 1.09, moist/wet 1.15; Tropical montane 1.09.
**Table 6 cropland input factors**: Low: Temperate/Boreal dry 0.95, moist 0.92; Tropical dry 0.95, moist/wet 0.92; Tropical montane 0.94. Medium: all 1.00. High without manure: Temperate/Boreal and Tropical dry 1.04, moist/wet 1.11; Tropical montane 1.08. (No "high with manure" factor - such lands are in the non-applicability table.)
**Table 7 grassland**: f_LU all 1.00; f_MG non-degraded 1.00; moderately degraded Temperate/Boreal 0.95, Tropical 0.97, Tropical montane 0.96; severely degraded 0.70; f_IN low/medium 1.00, high 1.11.
**Table 2 (non-applicable cropland practices)** and **Table 3 (non-applicable grassland practices)**: reproduced on p7-8 of the PDF (mostly "High with manure"/"High without manure" input regimes, no-till combinations, improved/non-degraded grassland). Implement as a lookup from the PDF pages; too long to restate here without risk.

---

## 3. Minimal implementable chain (FR05.002, plot-based trees, ex-post)

Assumptions: trees only plus (optionally) shrubs; DW/LI/SOC excluded or default; no fire; leakage per AR-0005. Ordered computation per verification at time t2 (previous verification t1):

| # | Step | Equation | Inputs and where they come from |
|---|---|---|---|
| 1 | Stratify project area; record A_i, A = ΣA_i, w_i = A_i/A | AR-0004 Eq 14 def. | GIS/field boundaries (monitored each verification) |
| 2 | Per tree AGB | f_j(DBH, H) (allometric) or V_TREE,j(DBH,H) × D_j × BEF_2,j | Field DBH/H per tree; species allometric equation (validated by appropriateness tool); or volume eq + D_j (IPCC GPG-LULUCF) + BEF_2,j (ex-post default 1.15) |
| 3 | Root-shoot R_j | R_j = e^(−1.085+0.9256 ln b)/b | b = plot AGB per ha (sum of step 2 / A_PLOT,i) - two-pass calc (A20) |
| 4 | Per tree total biomass | App1 Eq 4 or Eq 5 | steps 2-3 |
| 5 | Per plot biomass, per ha | App1 Eq 3 -> Eq 2 -> Eq 1 | A_PLOT,i (monitored) |
| 6 | Stratum mean and variance | AR-0004 Eq 16, 17 | plot values |
| 7 | Project mean, total biomass, carbon stock | Eq 14 -> Eq 13 -> Eq 12 | CF_TREE = 0.47 |
| 8 | Uncertainty | Eq 15 | t_VAL two-sided 90 %, df = n − M |
| 9 | Discount if u_C > 10 % (project: reduce) | Appendix 2 | stores both undiscounted (for next period, Note 2) and discounted |
| 10 | Stock at t1 | first verification: C_TREE,t1 = C_TREE_BSL (Eq 20-21 crown-cover, or 0 if para 13 conditions); later: previous undiscounted estimate | baseline crown cover CC_TREE_BSL,i (measured once), b_FOREST (IPCC), R_TREE 0.25 |
| 11 | Change in tree stock | Eq 1 and Eq 2 (independent estimates) or Eq 3-8 (re-measured plots, with Eq 22-23 to update stock); discount if u > 10 % | step 7/9 values |
| 12 | Annual change ∆C_TREE_PROJ,t for each year t in (t1, t2] | Eq 11 | T fractional years |
| 13 | Shrubs (optional; may be zero ex-ante) | Eq 27 -> Eq 26 -> Eq 24 -> Eq 25 | CC_SHRUB,i (monitored), BDR_SF 0.10, b_FOREST, CF_s 0.47, R_s 0.40; < 5 % cover = 0 |
| 14 | Baseline ∆C_TREE_BSL,t, ∆C_SHRUB_BSL,t | 0 if AR-0004 para 13/14 conditions; else Eq 9-10 (annual, crown-cover) | baseline CC, ∆b_FOREST (IPCC Table 3A.1.5) |
| 15 | Optional DW/LI (project and baseline) | AR-0003 Eq 9/15 (default factors × C_TREE,i,t) -> Eq 8/14 -> Eq 10-11/16-17; or measurement Eq 1-8, 12-14 | DF_DW / DF_LI table by biome, elevation, precipitation |
| 16 | Optional SOC | AR-0006 Eq 1-8 | climate/soil class, baseline management, A_i, t_PREP |
| 17 | GHG_E,t | AR-0002 Eq 1-8 (often 0 if no fire / below 5 % threshold) | fire areas, b_TREE at last verification |
| 18 | LK_t | AR-0005 Eq 1-3 (0 if grazing exemptions apply) | A_DISP,t, receiving-land biomass |
| 19 | ∆C_P,t | FR05.002 Eq 3 | steps 12, 13, 15, 16 |
| 20 | ∆C_ACTUAL,t | Eq 2 | steps 19, 17 |
| 21 | ∆C_BSL,t | Eq 1 | steps 14, 15 |
| 22 | LK_t | Eq 4 | step 18 |
| 23 | ∆C_AR,t | Eq 5 | |
| 24 | tCCC_t2 and lCCC_t2 | Eq 6, Eq 7; negative lCCC -> replacement obligation | annual ∆C_AR,t series |

For FR05.001 the same chain applies, with: no litter (drop LI terms), SOC by FR05.001 Eq 4 (0.50 t C/ha/yr per planted area for 20 years) instead of AR-0006, and the extra applicability checks (mangrove share, hydrology, 10 % disturbance on all land).

---

## 4. Ambiguities and errors (with page refs; PDF page numbers)

- **A1** FR05.002 p4 para 7(b)(ii): "Land which, in the baseline, is subjected to land-use and management practices" ends abruptly. In source AR-ACM0003 the clause continues "...and receives inputs listed in appendices 1 and 2" (external knowledge; not in this PDF). Implement as: disturbance cap applies to organic soils and to land under baseline practices that make AR-0006 inapplicable - confirm with BEE.
- **A2** FR05.002 p8 Eq 6 / FR05.001 p8 Eq 7: sum lower limit printed as "1" without index; interpreted as t = 1 (first project year). Crediting-period length, vintage-year assignment and tCCC expiry under CCTS are not defined in FR05.002 (FR05.001 footnote 3 uses Kyoto "commitment period" language, which has no CCTS equivalent).
- **A3** FR05.001 p7 Eq 4: summation index t reused with upper limit t. Intended: sum over planting cohorts τ = 1..t of A_PLANT,τ × dSOC applicable to that cohort's age (0.50 if t − τ ≤ 20, else 0). Also "following default value of is used" - symbol missing; also unclear whether dSOC applies in planting year itself ("t = t_PLANT to t_PLANT + 20" = 21 years inclusive?).
- **A4** FR05.002: baseline Eq 1 has no SOC term, project Eq 3 uses ∆SOC_AL,t only for land meeting AR-0006 applicability. FR05.002 Table 1 lists "Dead wood Litter and Soil organic carbon" in one row (optional).
- **A5** Tool numbering: methodologies cite "BM-T-AR-001..006" (FR05.002) vs "BM-T-AR-0001..0006" (FR05.001, tool covers). Same tools.
- **A6** AR-0004 cross-references are legacy CDM numbering: p7 para 14(g) "paragraph 11" and p8 "paragraph 10" (should be para 13); p8 "section 8"; p12 "section 6.3"; p18 "section 6.2"; p20 "section 10", "section 6.4"; p5 "section 12"; Appendix 1 para 12 "paragraphs 7 and 8" (should be 6 and 7); BEF para "paragraph 7 below" (likely para 6).
- **A7** AR-0004 p8-9 Eq 3: "44" printed at the bottom of p8, rest ("/12 × CF_TREE × ∆B_TREE") on p9; the summation for ∆b_TREE carries no equation number (Eq 5 missing). ∆b_TREE is mislabelled "BTREE" and ∆b_TREE,i described as "Mean change in carbon stock" with unit t d.m. ha-1.
- **A8** AR-0004 Eq 8/17 compute the plot-level sample variance (divide by n(n−1) of the sum form), but the where-lists call it "variance of mean". Eq 6/15 then divide by n_i. Implement as sample variance of plot values; SE² = s²/n_i (consistent with the p4 worked example).
- **A9** AR-0004 p10, p18: tool states India's threshold crown cover is 30 % (so crown-cover method applies below 6 %). India's CDM forest definition is commonly cited as 15 % crown cover (external knowledge) - confirm value with BEE before hard-coding; make it a parameter.
- **A10** AR-0004 p16-17 double-sampling where-list: β described as "Number of sample plots in the sub-sample" and n_i as "Tree biomass per hectare in plot p" (shifted labels); x̄′ and x̄ both render with overline. Corrected meanings given in 2.1 from Appendix 3 and standard double-sampling.
- **A11** AR-0003 p5 para 12: items (a)-(d) merge category and factor (category a -> factor 0.975 in item b; category c -> factor 0.80 in item d); footnote markers "1"/"2" are fused to the numbers ("0.975;1", "0.80.2"). Para 13/14/26 refer to "paragraph 14", "23-27", "23 and 24" (should be 12, 20-24, 20-21).
- **A12** AR-0003 p5 Eq 1 prints "(1+D_j)" - evidently (1+R_j) (R_j is listed in the where-table, and parameter table 7 says R_j used in Eq 1). "V_TREE,j×(DBH_k,H_k)" has a stray ×. Eq 4/5/6 lost superscripts in the PDF ("0.80", "k2", "π2", "Dn2"); Eq 4 bracket placement (H_STUMP / H_STUMP − H_DBH) read as H/(H − H_DBH). "D_MIDSTIUMP" typo. Eq 10/16 missing parentheses around the numerator.
- **A13** AR-0003 has no uncertainty/discount procedure for dead wood or litter, though plot sampling is used; whether AR-0004 Appendix 2 should be applied is not stated.
- **A14** Carbon fraction inconsistency: AR-0004 CF_TREE 0.47; AR-0005 CF 0.47; AR-0003 CF_TREE 0.5 (p14); AR-0002 CF_TREE/CF_SHRUB 0.50. Litter CF_LI 0.37 (AR-0003).
- **A15** GWPs: only AR-0002 gives GWP_CH4 = 21, GWP_N2O = 310 (IPCC SAR). Neither methodology states GWPs; CCTS may require AR5/AR6 values - confirm. AR-0002 Eq 3, 4, 8 use the 0.07 ratio (embeds SAR-era GWPs implicitly) rather than explicit GWPs.
- **A16** AR-0002 p8 Eq 8 multiplies A_BURN,i,t (ha) by C_DW,i,tL + C_LI,i,tL which AR-0002 defines as stratum stocks in t CO2-e (not per ha) - dimensionally inconsistent; per-ha stocks (t CO2-e ha-1) intended. The "60 % of DOM entirely burnt" assumption (p3) is not visible in Eq 8. Eq 7 has no CF or 44/12 (correct, since EF is per kg d.m.). Eq 3 has a stray "=i=" and an unclosed bracket. p3 para 1 wrongly says the tool determines the baseline scenario. Section numbering p9 ("5.", para "14" repeated). A_BURN description (p12) copies A_FMF text.
- **A17** AR-0002 p10 COMF table layout garbled: read as tropical 3-5 yr 0.46; 6-10 yr 0.67; 11-17 yr 0.50; 18+ yr 0.32. Matches CDM AR-Tool08; verify visually.
- **A18** AR-0005 p5: ∆C_BIOMASS,t unit printed "t d.m." but formula includes CF and area -> t C; ∆SOC_LUC,t unit printed "tC ha-1" but multiplied by A_DISP,t -> t C. 44/12 then gives t CO2e. AR-0005 cites "Table 3" and "Tables 4, 5, 6" of AR-0006, whose actual numbering is Table 4 (SOC_REF), Tables 5-6 (cropland), Table 7 (grassland).
- **A19** AR-0006 p3 applicability (a)(i)-(iii) joined by "or" after (i) - CDM original requires all; p5 para 10 cites "Tables 3 - 6" and para 4 "Tables 1 and 2" (actual: Tables 4-7 and 2-3). Eq 6 defines dSOC only up to t_PREP + 20; afterwards presumably 0. SOC_LOSS in Eq 5 is negative for one year only. Para 11 "over and above the area disturbed in the baseline" requires baseline disturbance data.
- **A20** AR-0004 p26: R_j depends on b = AGB per ha, but is applied per tree inside the plot sum; b is not specified as plot-level vs stratum-level. Implement as plot AGB per ha (two-pass). Same formula in AR-0003 (with "A" for AGB).
- **A21** AR-0004 p17 sec "Estimation by modelling" and "Estimation by proportionate crown cover" (paras 49-59) lost their section headings; paras 59-61 (stock update Eq 22-23) sit under the crown-cover heading but belong to method (d) "Updating the previous stock by independent measurement of change".
- **A22** AR-0004 Appendix 2 does not specify how to discount a change estimate (∆C_TREE) or how discounted stocks feed tCCC; FR05.00x do not state whether the discount applies to C_TREE or ∆C. Precision "requirements" in AR-0004 are only the discount scheme (no mandatory target precision).
- **A23** AR-0004 p9 Eq 10 symbol ∆b_FOREST is described with "MAI_FOR" (LaTeX artefact); Table 3A.1.5 reference is to IPCC GPG-LULUCF 2003. b_FOREST (stock) vs ∆b_FOREST (increment) must not be confused.
- **A24** AR-0003 monitoring frequency "every five years since the year of the initial verification" vs AR-0004 "at every verification"; the methodologies set no verification frequency.
- **A25** Not supplied but referenced: BM-T-AR-001 (baseline/additionality), "Calculation of the number of sample plots", "Demonstrating appropriateness of allometric equations", "Demonstrating appropriateness of volume equations", Glossary of ICM terms, Detailed Procedure for Offset Mechanism under CCTS.
