# Rice methane methodologies: transcription extract for platform implementation

Prepared 2026-10-05. Two parts: (A) Verra VM0051 v1.1, (B) India CCTS BM AG04.002 v1.0, followed by (C) a comparison.

## Sources and how they were checked

| Doc | File | Verification |
|---|---|---|
| VM0051 v1.1 (14 Jul 2026, 90 pp) | `VM0051-Rice/VM0051_v1.1.pdf` (downloaded from `https://verra.org/wp-content/uploads/2026/07/VM0051-Improved-Management-in-Rice-Production-Systems-v1.1.pdf`); text copy `_text/VM0051_v1.1.md` | Eqs (1)-(9), (13)-(16), (19)-(22), (24), (25), (29), (30), (35), (36), (38) were checked against page renders (pp. 24-29, 31, 33, 38, 42, 44). The rest come from the text copy, which reads cleanly for them. |
| VM0051 v1.0 (27 Feb 2025) | **Not obtained.** The only file at `wp-content/uploads/2025/03/VM0051-Improved-Management-in-Rice-Production-Systems-v1.0.pdf` is the 11 Mar 2025 webinar slide deck. It is saved as `VM0051-Rice/VM0051_v1.0_webinar_slides_11MAR2025.pdf`. Other guessed URLs returned 404 or 429. | v1.1 is the version in force (minor revision), so v1.0 is not needed. |
| BM AG04.002 v1.0 (30 Jun 2026, 24 pp) | `CCTS/BM_AG04.002_Rice_cultivation.pdf` | Every equation and table was checked against page renders (pp. 7-14, 22-23). The text dump garbles stacked formulas and fuses footnote markers into values: "29.85" is really 29.8 plus footnote 5, and "273.06" is really 273.0 plus footnote 6. |
| IPCC 2019 Refinement Vol 4 Ch 5 (Cropland, rice section 5.5) | Downloaded to `IPCC/IPCC_2019R_V4_Ch05_Cropland.pdf`; text in `_text/IPCC_2019R_V4_Ch05_Cropland.txt` | Both methodologies point here for EFc and SFw/SFp/CFOA. Tables 5.11-5.14 below are transcribed from it (pp. 5.53-5.56). |
| ICVCM Board observations on VM0051 v1.1 (Aug 2026) | `VM0051-Rice/ICVCM_Board_Observations_VM0051_v1.1.pdf` | Context only. It is non-binding. |
| VCS Standard v5.0 | `VERRA-common/VCS_Standard_v5.0.pdf` | Source for the GWPs that VM0051 defers to (s. 3.14.4). |

Conventions used in this file: "p." means the page number printed on the document. **[RECONSTRUCTED]** marks a reading I inferred, with the reasoning given. **[AMBIGUITY]** marks unclear or inconsistent source text. No values are invented. Where a value comes from a document the methodology cites rather than the methodology itself, the cited source is named.

---

# PART A: VM0051 v1.1 Improved Management in Rice Production Systems

## A1. Applicability, boundary, baseline

### A1.1 Summary (p. 5-6)
- Category: ALM / Improved cropland management. Additionality and crediting baseline both use the project method. Mitigation outcome is **Reductions** only. SOC removals are not credited; those go to VM0042.
- There are three quantification approaches (QAs): **QA1** biogeochemical model, **QA2** direct chamber measurement of CH4, **QA3** default equations and emission factors.
- Simplified QA3 procedures (IPCC Tier 1 factors and a flat 15% uncertainty deduction) apply only to projects with a **capacity limit of 60 000 t CO2e/yr** (p. 6, 21, 25, 38, 43).
- Any quantitative adjustment in an optional practice must exceed **5% of the pre-existing value** (look-back average) to count as a practice change (p. 6, 10).

### A1.2 Definitions relevant to water regimes (p. 7-9)
- **Continuous flooding**: standing water throughout the season. Fields are drained only shortly before maturity and for harvest (end-of-season drainage).
- **Single drainage**: a single drainage event and period during the cropping season, at any growth stage, in addition to end-of-season drainage.
- **AWD**: controlled intermittent irrigation with multiple (more than one) drainage events during the cultivation period, plus end-of-season drainage.
- **DSR**: seeds (pre-germinated or dry) are broadcast or sown directly, with no transplanting. The field must be dry before seeding and stay dry during sowing until germination (plantlets at the 2-4 leaf stage can withstand shallow flooding).
- **Cultivation period**: starts with pre-planting preparation and ends at harvest. Footnote 17 (p. 27) and the L_t parameter table (p. 54) say it "commences at land preparation and continues until whichever comes later, harvest or post-season drainage."
- **Historical look-back period**: at least 3 years of rice cultivation before the project start, including a complete crop rotation where there is one.
- **Controlled irrigation**: the farmer controls flow rate, flooding duration and similar variables.

### A1.3 Applicability conditions (Section 4, p. 9-11)
Applicable when all of the following hold:
1. Main project activities reduce CH4 from methanogenesis through improved irrigation, using at least one of:
   - (a) single drainage and/or a shortened flooded period
   - (b) AWD
   - (c) DSR

   Optional activities are methanotrophs; short-duration or low-emission cultivars (with no material change in root C inputs); avoided residue burning; reduced fossil fuel use; improved N management (less total N, nitrification inhibitors, slow-release N); and biochar.
2. Quantitative adjustments exceed 5% of the pre-existing value (average over the look-back period).
3. Fields have controlled irrigation **and** drainage facilities.
4. Activities face no local regulatory restrictions.
5. No clearing of native ecosystems in the 10 years before the project start.
6. The number of rice cultivation periods per year stays the same as in the look-back period.

Not applicable when:
7. Practices materially reduce SOC through lower C inputs (more straw removal, less manure or compost, cultivars with materially smaller roots).
8. Rice is upland, rainfed, deep-water, or non-irrigated lowland.
9. Off-season management changes (fertilizer, tillage, rotations, crop types, livestock). **Exceptions**: (a) avoided residue burning after harvest; (b) **reducing the flooding period before the cultivation period, only on fields with no crop rotation** (fields used exclusively for flooded rice).
10. The project seeks credits for biochar CO2 removals (use VM0044 instead).

### A1.4 Boundary (Section 5, Table 1, p. 11-12)
Spatial boundary: all lands on which the rice activities are implemented.

| Source | GHG | Included? |
|---|---|---|
| Soil methanogenesis | CH4 | **Yes** (dominant source) |
| Fossil fuels | CO2 | S* |
| Liming | CO2 | S* |
| Enteric fermentation | CH4 | No |
| Manure deposition | N2O, CH4 | No |
| N fertilizer + N from incorporated rice straw | N2O | **Yes** for N2O attributable to irrigation change (all projects). S* where N rate or residue N exceeds baseline. |
| Biomass burning | CH4, N2O | S* |

S* = **must** be included where the project raises total GHG emissions by more than 5% versus baseline (not de minimis). **May** be included where the project lowers them by more than 5%.

### A1.5 Baseline determination (Section 6, p. 12-15)
- **Per field**, build an annual **schedule of activities** from a look-back of x years. x is at least 3 and must cover at least one full rotation. Collect data for t = -1 to t = -x on all Table 2 parameters plus machinery and liming.
- From t = 1 the schedule is applied by repeating the x-year cycle (starting at year t = -x) until the end of the baseline period. Rice production is then re-evaluated against regional data from the last 5 years.
- The document history (p. 90) says v1.1 requires baseline reassessment "every five years or at project crediting renewal". Section 6 text (p. 12) says at the end of each crediting period. See A6.
- **Table 2 minimum baseline data (p. 13)**:

  | Area | Qualitative | Quantitative |
  |---|---|---|
  | Water | Irrigation Y/N; on-season flooding (Continuous/Single/Multiple); pre-season flooding (Flooded / Short or Long drainage) | Irrigation rate or volume; flooding duration (days); water level below surface |
  | Planting and harvest | Crop types; variety; DSR or transplanting | Seeding and harvest dates; yield |
  | Tillage and residue | Tillage, residue removal, incorporation, burning (each Y/N); end use of residue | Tillage depth, frequency, area; residue rate left; incorporation timing; burned area |
  | Nutrients | Organic amendment Y/N and type; synthetic N Y/N and type | Application rates |
  | Other amendments | Biochar, methanotrophs (Y/N) | Rates |
  | Liming | Limestone or dolomite (Y/N) | Amount and date |
  | Machinery | Fossil fuel Y/N and type | Fuel rate |

- **Conservative single-drainage rule (p. 14)**: if single drainage occurred in **any** year of the look-back, the baseline on-season regime for that field is single drainage in **every** year. Such fields must then implement a shortened pre-season flooding period, multiple drainage, and/or DSR.
  - Footnote 15 (p. 26): "Projects with dynamic baseline activities must use the most conservative baseline assumption from a three-year historical look-back period … This may mean that a project must set EF_bsl,c using the emission factor for single drainage."
- **Dynamic cultivation-period exception (p. 14, p. 54)**: if weather makes a monitoring-period season longer than the baseline season, the baseline L may be set equal to the project L for affected fields in that season. Evidence must show the duration matches non-project reference fields in the region, or follow Box 1.
- **Box 1 data hierarchy (p. 14-15)**. Qualitative data come from the farmer or landowner. Quantitative data, in descending preference:
  1. Records with documentary evidence, or remote sensing.
  2. Management plans with evidence. Where a range is given, take the value giving the **lowest** baseline emissions.
  3. Signed farmer attestation, which may be digital, consistent with other evidence.
  4. Regional census averages from within 20 years or the last 10 iterations, backed by an attestation.

  The hierarchy applies to QA1, QA2 and QA3 inputs.
- **Additionality (Section 7, p. 16-17)**: regulatory surplus, then VT0008 barrier and/or investment analysis, then common practice. Adoption of each activity must be 20% or less per state/province (second-order jurisdiction), excluding VCS-registered activities.

## A2. Quantification approaches and all numbered equations

**Table 3: allowed approaches by source (p. 19)**

| GHG / source | QA1 Model | QA2 Measure | QA3 Defaults |
|---|---|---|---|
| CH4 soil methanogenesis | X | X | X |
| CH4, N2O biomass burning | | | X |
| N2O N fertilizers incl. straw N | X | | X |
| CO2 fossil fuels | | | X |
| CO2 liming | | | X |
| CO2 SOC | X* (must be modeled under QA1 but not credited) | | |

- QA1 and QA2 projects must use QA3 (or QA1 where it applies) for sources outside their domain (p. 19-20).
- The same QA must be used for baseline and project for a given source within a monitoring period (p. 18).
- **QA2 is mandatory** for methanotrophs, biochar, low-emission varieties, and AWD drained to a depth of less than 10 cm below the soil surface (p. 20, 23, 71).

**QA3 emission-factor hierarchy (p. 20-21)**:
1. A project-specific EF from peer-reviewed literature (Web of Science SCI journal).
2. Alternative credible sources. **Not allowed for soil CH4 or N2O.**
3. Tier 2 factors derived from literature following IPCC 2019.
4. Projects at or below 60 000 t CO2e/yr may use IPCC 2019 Tier 1 global or regional soil-CH4 factors. **All other projects must use country-specific soil-CH4 EFs.**

Convention: **all baseline equations apply to the project scenario by replacing subscript `bsl` with `wp`** (p. 32). Index i = quantification unit (QU), t = year. An overbar marks an areal mean (t CO2e/ha).

### 8.2.1 Fossil fuel CO2 (QA3) (p. 24)

**Eq (1)**
Plain: `CO2_ff_bsl,i,t = ( Σ_{j=1..J} EFF_bsl,i,j,t ) / A_i`
LaTeX: `\overline{CO2\_ff}_{bsl,i,t} = \left(\sum_{j=1}^{J} EFF_{bsl,i,j,t}\right) / A_i`

**Eq (2)**
Plain: `EFF_bsl,i,j,t = FFC_bsl,i,j,t × EF_CO2,j`
LaTeX: `EFF_{bsl,i,j,t} = FFC_{bsl,i,j,t} \times EF_{CO2,j}`

| Symbol | Meaning | Unit |
|---|---|---|
| CO2_ff_bsl,i,t (overbar) | Areal mean fossil-fuel CO2, QU i, year t, baseline | t CO2e/ha |
| EFF_bsl,i,j,t | CO2 from combustion of fuel j | t CO2e |
| A_i | Area of QU i | ha |
| j | Fuel type (gasoline, diesel, other) | - |
| FFC_bsl,i,j,t | Fuel consumption | L |
| EF_CO2,j | Combustion EF | t CO2e/L |

### 8.2.2 Liming CO2 (QA3 or QA1) (p. 24-25)

**Eq (3)**
Plain: `CO2_lime_bsl,i,t = EL_bsl,i,t / A_i`
LaTeX: `\overline{CO2\_lime}_{bsl,i,t} = EL_{bsl,i,t} / A_i`

**Eq (4)**
Plain: `EL_bsl,i,t = ((M_limestone,bsl,i,t × EF_limestone) + (M_dolomite,bsl,i,t × EF_dolomite)) × 44/12`
LaTeX: `EL_{bsl,i,t} = \left( (M_{limestone,bsl,i,t} \times EF_{limestone}) + (M_{dolomite,bsl,i,t} \times EF_{dolomite}) \right) \times \frac{44}{12}`

| Symbol | Meaning | Unit |
|---|---|---|
| CO2_lime_bsl,i,t (overbar) | Areal mean liming CO2 | t CO2e/ha |
| EL_bsl,i,t | Liming CO2 | t CO2e |
| M_limestone / M_dolomite | Amount of CaCO3 / CaMg(CO3)2 applied | t |
| EF_limestone | 0.12 | t C/t limestone |
| EF_dolomite | 0.13 | t C/t dolomite |
| 44/12 | CO2:C molar mass ratio | - |

### 8.2.3 Soil methanogenesis CH4 (p. 25-27)

**Eq (5)** (QA1. QA2 and QA3 supply f(·) as described below.)
Plain: `CH4_soil_bsl,i,t = GWP_CH4 × f(CH4_soil_bsl,i,t)`
LaTeX: `\overline{CH4\_soil}_{bsl,i,t} = GWP_{CH4} \times f(CH4\_soil_{bsl,i,t})`

| Symbol | Meaning | Unit |
|---|---|---|
| CH4_soil_bsl,i,t (overbar) | Areal mean soil CH4 | t CO2e/ha |
| GWP_CH4 | GWP of CH4 | t CO2e/t CH4 |
| f(CH4_soil_bsl,i,t) | Modeled CH4 over the preceding year | t CH4/ha |

The text says QA2 sets f(·) via 8.2.4 and QA3 calculates it via Eqs (6)-(8). Eq (8) and Eq (16) already contain GWP, so see A6 item 1.

**Eq (6)** (QA3)
Plain: `EF_bsl,i,t = EF_bsl,c × SC_bsl,w × SC_bsl,p × SC_bsl,o`
LaTeX: `EF_{bsl,i,t} = EF_{bsl,c} \times SC_{bsl,w} \times SC_{bsl,p} \times SC_{bsl,o}`

**Eq (7)**
Plain: `SC_bsl,o = (1 + Σ_a ROA_a × CFOA_a)^0.59`
LaTeX: `SC_{bsl,o} = \left(1 + \sum_{a} ROA_a \times CFOA_a\right)^{0.59}`

**Eq (8)**
Plain: `BE_CH4,i,t = EF_bsl,i,t × L_t × 10^-3 × GWP_CH4`
LaTeX: `BE_{CH4,i,t} = EF_{bsl,i,t} \times L_t \times 10^{-3} \times GWP_{CH4}`

| Symbol | Meaning (verbatim where possible) | Unit |
|---|---|---|
| EF_bsl,i,t | "Adjusted baseline methane emission factor for continuously flooded fields without organic amendments for quantification unit i in year t". The label is a misnomer: this is the adjusted EF. | kg CH4/ha/day |
| EF_bsl,c | Baseline CH4 EF for continuously flooded fields without organic amendments (IPCC Table 5.11). See footnote 15. | kg CH4/ha/day |
| SC_bsl,w | Water-regime scaling factor during cultivation (IPCC 2019 Table 5.12 Updated) | - |
| SC_bsl,p | Pre-season water-regime scaling factor (IPCC 2019 Table 5.13 Updated) | - |
| SC_bsl,o | Organic amendment scaling factor, from Eq (7) | - |
| ROA_a | Application rate of amendment type a. Dry weight for straw, fresh weight for others. Footnote 16: "For the baseline, 5 t/ha of straw is assumed." | t/ha |
| CFOA_a | Conversion factor for amendment type a (IPCC 2019 Table 5.14 Updated) | - |
| BE_CH4,i,t | Baseline soil CH4 for QU i, year t | t CO2e/ha |
| L_t | Cultivation period of rice in year t (land preparation to the later of harvest or post-season drainage) | days |

Notes:
- VM0051 writes **SC** where IPCC and AG04.002 write **SF**. The quantities are the same.
- p. 26: "Where root biomass changes significantly relative to baseline conditions, the project proponent must account for the changes in biomass to soil using Equation (7), unless … de minimis."
- p. 49: a new cultivar with a materially larger root system must be accounted for through CFOA.

### 8.2.4 Direct measurement CH4 (QA2) (p. 27-29)

**Eq (9)**
Plain: `m_CH4,pt = Conc_CH4,pt × Vol_ch × M_CH4 × 1 atm / (R × T_pt × 1000)`
LaTeX: `m_{CH4,pt} = Conc_{CH4,pt} \times Vol_{ch} \times M_{CH4} \times \frac{1\,atm}{R \times T_{pt} \times 1000}`

**Eq (10)**
Plain: `sl = Δm_CH4,pt / Δpt`
LaTeX: `sl = \frac{\Delta m_{CH4,pt}}{\Delta pt}`
(This is the slope of the line of best fit of m against pt.)

**Eq (11)**
Plain: `F_ch = sl × 60 min / A_ch`
LaTeX: `F_{ch} = \frac{sl \times 60\,min}{A_{ch}}`

**Eq (12)**
Plain: `F_f = ( Σ_{ch=1..Nch} F_ch ) / Nch`
LaTeX: `F_f = \frac{\sum_{ch=1}^{N_{ch}} F_{ch}}{N_{ch}}`

**Eq (13)**
Plain: `E_f,z = (F_f,z + F_f,z+1) × 24h × D_z / 2`
LaTeX: `E_{f,z} = \frac{(F_{f,z} + F_{f,z+1}) \times 24h \times D_z}{2}`

**Eq (14)**
Plain: `E_f,s = Σ_{z=1..N} E_f,z`
LaTeX: `E_{f,s} = \sum_{z=1}^{N} E_{f,z}`

**Eq (15)**
Plain: `EF_bsl,i,s = ( Σ_{f=1..NF} E_f,s × 10^-5 ) / NF`
LaTeX: `EF_{bsl,i,s} = \frac{\sum_{f=1}^{NF} E_{f,s} \times 10^{-5}}{NF}`

**Eq (16)**
Plain: `BE_CH4,i,t = Σ_s^S EF_bsl,i,s × GWP_CH4`
LaTeX: `BE_{CH4,i,t} = \sum_{s}^{S} EF_{bsl,i,s} \times GWP_{CH4}`

| Symbol | Meaning | Unit |
|---|---|---|
| m_CH4,pt | CH4 mass in chamber at time pt | mg |
| pt | Sampling time point (e.g., 0, 15, 30) | min |
| Conc_CH4,pt | CH4 concentration | ppm |
| Vol_ch | Chamber volume | L |
| M_CH4 | 16 | g/mol |
| 1 atm | Constant pressure unless measured | atm |
| R | 0.08206 | L atm/K/mol |
| T_pt | Temperature | K |
| sl | Slope | mg/min |
| F_ch | Flux of chamber ch | mg/m2/h |
| A_ch | Chamber basal area | m2 |
| F_f | Mean hourly flux of sample unit f | mg/m2/h |
| Nch | Number of replicate chambers per sample unit | - |
| E_f,z | Emissions in interval z | mg/m2 |
| z | Weekly measurement interval index | - |
| F_z, F_z+1 | Hourly flux at start and end of interval | mg/m2/h |
| D_z | Days in interval | d |
| E_f,s | Season total for sample unit f | mg/m2 |
| N | Number of intervals in season s | - |
| EF_bsl,i,s | Seasonal CH4 EF of QU i | t CH4/ha |
| NF | Number of sample units in QU i | - |
| BE_CH4,i,t | Baseline soil CH4 | t CO2e/ha |

Notes:
- 10^-5 converts mg/m2 to t/ha.
- Flux on planting and harvest days may be assumed zero where not measured (p. 29).
- Minimums: 3 baseline control sites and 3 project sample units per stratum; 3 samples per chamber per event; weekly sampling; samples taken 09:00-12:00 (Appendix 2, p. 79-81).

### 8.2.5 Biomass burning CH4 (QA3) (p. 30)

**Eq (17)**
Plain: `CH4_bb_bsl,i,t = (GWP_CH4 × MB_bsl,i,t × CF_r × EF_CH4 / 10^6) / A_i`
LaTeX: `\overline{CH4\_bb}_{bsl,i,t} = \left( \frac{GWP_{CH4} \times MB_{bsl,i,t} \times CF_r \times EF_{CH4}}{10^6} \right) / A_i`

| Symbol | Meaning | Unit |
|---|---|---|
| MB_bsl,i,t | Mass of rice straw burned. p. 49: assume 100% of aboveground biomass is burned in the baseline. | kg |
| CF_r | Combustion factor, 0.80 (IPCC 2019 Vol 4 Table 2.6) | fraction |
| EF_CH4 | 2.7 (IPCC Table 2.5) | g CH4/kg dm burned |
| 10^6 | g to t | - |

[AMBIGUITY] MB is in kg and EF in g/kg, so MB × EF / 10^6 gives t CH4. The units are consistent.

### 8.2.6 N2O from N inputs (p. 30-32)

**Eq (18)** (QA1)
Plain: `N2O_soil_bsl,i,t = GWP_N2O × f(N2O_soil_bsl,i,t)`
LaTeX: `\overline{N2O\_soil}_{bsl,i,t} = GWP_{N2O} \times f(N2O\_soil_{bsl,i,t})`
f(·) is in t N2O/ha.

**Eq (19)** (QA3)
Plain: `N2O_soil_bsl,i,t = [(FSN_bsl,i,t + FON_bsl,i,t + FCR_bsl,i,t) × EF_N] × 44/28 × GWP_N2O / A_i`
LaTeX: `\overline{N2O\_soil}_{bsl,i,t} = \left[ (FSN_{bsl,i,t} + FON_{bsl,i,t} + FCR_{bsl,i,t}) \times EF_N \right] \times \frac{44}{28} \times GWP_{N2O} / A_i`

**Eq (20)**
Plain: `FSN_bsl,i,t = Σ_SF M_bsl,SF,i,t × NC_SF`
LaTeX: `FSN_{bsl,i,t} = \sum_{SF} M_{bsl,SF,i,t} \times NC_{SF}`

**Eq (21)**
Plain: `FON_bsl,i,t = Σ_OF M_bsl,OF,i,t × NC_OF`
LaTeX: `FON_{bsl,i,t} = \sum_{OF} M_{bsl,OF,i,t} \times NC_{OF}`

**Eq (22)**
Plain: `FCR_bsl,i,t = Σ_CR M_bsl,CR,i,t × NC_CR`
LaTeX: `FCR_{bsl,i,t} = \sum_{CR} M_{bsl,CR,i,t} \times NC_{CR}`

| Symbol | Meaning | Unit |
|---|---|---|
| FSN / FON / FCR | Total N applied as synthetic fertilizer / organic fertilizer / crop residue (above and below ground). Footnote 19: FCR includes residue left over the off-season. | t N |
| EF_N | N2O EF for N additions in flooded rice | t N2O-N/t N |
| M_bsl,SF,i,t / M_bsl,OF,i,t | Mass of fertilizer product | t |
| M_bsl,CR,i,t | Dry mass of rice straw returned to soil | t dm |
| NC_SF / NC_OF | N content | t N/t fertilizer |
| NC_CR | N content of residue dry mass | t N/t dm |
| 44/28 | N2O:N | - |

EF_N source (p. 59):
- Use the Section 8.2.6 / QA3 hierarchy, or derive per IPCC 2019 Ch 11 s. 11.2.1.1 and Ch 2 s. 2.2.2.
- Where activity data are justified as lacking, "an appropriate disaggregated Tier 1 value from Table 11.1" may be used. From Table 8 (p. 83), EF1FR is: continuous flooding 0.003; single and multiple drainage 0.005; aggregated 0.004.

### 8.2.7 Biomass burning N2O (QA3) (p. 32)

**Eq (23)**
Plain: `N2O_bb_bsl,i,t = (GWP_N2O × MB_bsl,i,t × CF_r × EF_N2O / 10^6) / A_i`
LaTeX: `\overline{N2O\_bb}_{bsl,i,t} = \left( \frac{GWP_{N2O} \times MB_{bsl,i,t} \times CF_r \times EF_{N2O}}{10^6} \right) / A_i`

EF_N2O = 0.07 g N2O/kg dm burned (IPCC Table 2.5, p. 65).

### 8.3 Project-only emissions (p. 32-34)

**Eq (24)** Straw diverted to alternative end uses (required where burning is materially reduced)
Plain: `PE_AB,t = (RS_removed,r × EF_eu,r × 0.001)`
LaTeX: `PE_{AB,t} = (RS_{removed,r} \times EF_{eu,r} \times 0.001)`

| Symbol | Meaning | Unit |
|---|---|---|
| PE_AB,t | Project emissions from off-farm straw end uses, year t | t CO2e |
| RS_removed,r | Straw removed to end-use category r | t dm |
| EF_eu,r | EF of end use r (project-derived from literature or LCA) | kg CO2e/t dry straw |

[AMBIGUITY] There is no Σ over r, although r is a category index. Implement as Σ_r.

**Eq (25)** N2O correction for irrigation change. This is mandatory for every field moving from continuous flooding to single or multiple drainage, whether or not N rates change.
Plain: `PE_Red-Irri,t = Σ_{i=1..n} (Q_N,i × A_i) × CF_N2O × 10^-3 × GWP_N2O`
LaTeX: `PE_{Red\text{-}Irri,t} = \sum_{i=1}^{n} (Q_{N,i} \times A_i) \times CF_{N2O} \times 10^{-3} \times GWP_{N2O}`

| Symbol | Meaning | Unit |
|---|---|---|
| PE_Red-Irri,t | Deduction for N2O flux due to drying periods | t CO2e |
| Q_N,i | N input application rate in the project scenario | kg N/ha |
| CF_N2O | **0.00314** (fixed: "value of 0.00314 must be used") | kg N2O/kg N input |
| 10^-3 | kg to t | - |

Derivation (Appendix 3, p. 83): (0.005 - 0.003) kg N2O-N/kg N × 44/28 = 0.003143.

Footnote 20: if N rates change in either direction, also compute N2O with the Section 8.2.6 equations.

### 8.4 Leakage (p. 34-37)
Leakage sources summing to less than 5% of total reductions are de minimis. This must be shown with the CDM A/R significance tool.

**Eq (26)** New or additional imported manure, compost or biosolids. Exempt if the material is produced on-site within the project, diverted from an uncontrolled anaerobic lagoon/pond/tank/pit, or documented as not otherwise used as a soil amendment.
Plain: `LE_OA,t = Σ_l (M_OA_wp,l,t × CC_wp,l,t × 0.12 × 44/12)`
LaTeX: `LE_{OA,t} = \sum_{l} \left( M\_OA_{wp,l,t} \times CC_{wp,l,t} \times 0.12 \times \frac{44}{12} \right)`

| Symbol | Meaning | Unit |
|---|---|---|
| LE_OA,t | Leakage from organic amendments | t CO2e |
| M_OA_wp,l,t | Mass of amendment from livestock type l applied | t |
| CC_wp,l,t | C content | t C/t |
| 0.12 | Fraction of manure C remaining (Maillard & Angers 2014), also applied to compost and biosolids | - |

[AMBIGUITY] The equation applies to the whole M_OA, not only the "new or additional" increment. The definitions (footnotes 22-23) imply the increment.

**Eq (27)** Yield check, Step 1 option 1
Plain: `ΔP = ((P_wp − P_bsl) / P_bsl) × 100`
LaTeX: `\Delta P = \left( \frac{P_{wp} - P_{bsl}}{P_{bsl}} \right) \times 100`

**Eq (28)** Yield check, Step 1 option 2
Plain: `ΔPR = (P_wp / RP_wp − P_bsl / RP_bsl) × 100`
LaTeX: `\Delta PR = \left( \frac{P_{wp}}{RP_{wp}} - \frac{P_{bsl}}{RP_{bsl}} \right) \times 100`

| Symbol | Meaning | Unit |
|---|---|---|
| ΔP / ΔPR | Change in productivity / in yield ratio | % |
| P_wp, P_bsl | Average yield in the monitoring period / the look-back | output/ha |
| RP_wp, RP_bsl | Average regional yield in the same periods | output/ha |

Yield procedure:
- Step 1: show yield fell by no more than 5%. Exclude extreme-weather years. Use only data from the last 10 years. For techniques that are new to the project (DSR, inhibitors, less burning), set P_bsl = RP_bsl.
- If the drop exceeds 5%, Step 2: drop the first 3 project years and recompute.
- If it still exceeds 5%, Step 3: stratify by practice, practice combination, soil and climate.
  - A combination found to cause the decline becomes ineligible until remedied.
  - If the decline is not isolated to a combination, LE_yield = the decline above 5%.
  - If the cause cannot be isolated at all, the whole project becomes ineligible.
- Run in the first monitoring period. Repeat each season while leakage is detected, otherwise again at the next crediting period.

[AMBIGUITY] The text never says how LE_yield "portion of the observed yield decline above 5%" converts to t CO2e. LE_yield also does not appear in Eq (29).

**LE_BR,t** Diversion of baseline bioenergy residues. Determine with CDM TOOL16. No equation in VM0051.

### 8.5 Net reductions (p. 38-39)

**Eq (29)**
Plain: `ER_t = ΔCO2_ff_t + ΔCO2_lime_t + ΔCH4_bb_t + (ΔCH4_soil_t × (1 − UNC_CH4_soil,t)) + (ΔN2O_soil_t × (1 − UNC_N2O_soil,t)) + ΔN2O_bb_t − LE_OA,t − LE_BR,t − PE_AB,t − PE_Red-Irri,t`
LaTeX: `ER_t = \Delta CO2\_ff_t + \Delta CO2\_lime_t + \Delta CH4\_bb_t + \left(\Delta CH4\_soil_t \times (1 - UNC_{CH4\_soil,t})\right) + \left(\Delta N2O\_soil_t \times (1 - UNC_{N2O\_soil,t})\right) + \Delta N2O\_bb_t - LE_{OA,t} - LE_{BR,t} - PE_{AB,t} - PE_{Red\text{-}Irri,t}`

**Eq (30)**
Plain: `ΔCO2_ff_t = Σ_{i=1..n} (CO2_ff_bsl,i,t − CO2_ff_wp,i,t) × A_i`
LaTeX: `\Delta CO2\_ff_t = \sum_{i=1}^{n} \left( \overline{CO2\_ff}_{bsl,i,t} - \overline{CO2\_ff}_{wp,i,t} \right) \times A_i`

**Eq (31)**
Plain: `ΔCH4_soil_t = Σ_{i=1..n} (CH4_soil_bsl,i,t − CH4_soil_wp,i,t) × A_i`
LaTeX: `\Delta CH4\_soil_t = \sum_{i=1}^{n} \left( \overline{CH4\_soil}_{bsl,i,t} - \overline{CH4\_soil}_{wp,i,t} \right) \times A_i`

**Eq (32)**
Plain: `ΔCH4_bb_t = Σ_{i=1..n} (CH4_bb_bsl,i,t − CH4_bb_wp,i,t) × A_i`
LaTeX: `\Delta CH4\_bb_t = \sum_{i=1}^{n} \left( \overline{CH4\_bb}_{bsl,i,t} - \overline{CH4\_bb}_{wp,i,t} \right) \times A_i`

**Eq (33)**
Plain: `ΔN2O_soil_t = Σ_{i=1..n} (N2O_soil_bsl,i,t − N2O_soil_wp,i,t) × A_i`
LaTeX: `\Delta N2O\_soil_t = \sum_{i=1}^{n} \left( \overline{N2O\_soil}_{bsl,i,t} - \overline{N2O\_soil}_{wp,i,t} \right) \times A_i`

**Eq (34)**
Plain: `ΔN2O_bb_t = Σ_{i=1..n} (N2O_bb_bsl,i,t − N2O_bb_wp,i,t) × A_i`
LaTeX: `\Delta N2O\_bb_t = \sum_{i=1}^{n} \left( \overline{N2O\_bb}_{bsl,i,t} - \overline{N2O\_bb}_{wp,i,t} \right) \times A_i`

All Δ terms are in t CO2e. UNC values are fractions between 0 and 1 in Eq (29). QA3 projects at or below 60 000 t/yr use UNC = 0.15.

[AMBIGUITY] There is no equation for ΔCO2_lime_t. By analogy: `Σ_i (CO2_lime_bsl,i,t − CO2_lime_wp,i,t) × A_i` [RECONSTRUCTED, following the pattern of Eqs 30-34].

### 8.6 Uncertainty (p. 39-45)

**Eq (35)**
Plain: `S²_sampling,Δ•,t = Σ_{h=1..H} S²_sampling,Δ•,h,t`
LaTeX: `S^2_{sampling,\Delta\bullet,t} = \sum_{h=1}^{H} S^2_{sampling,\Delta\bullet,h,t}`

**Eq (36)**
Plain: `S²_sampling,Δ•,h,t = A_h² / (n_h (n_h − 1)) × Σ_{ip=1..n_h} (Δ•_h,ip,t − Δ•_h,t(mean))²`
LaTeX: `S^2_{sampling,\Delta\bullet,h,t} = \frac{A_h^2}{n_h(n_h-1)} \sum_{ip=1}^{n_h} \left( \Delta\bullet_{h,ip,t} - \overline{\Delta\bullet}_{h,t} \right)^2`

**Eq (37)**
Plain: `S²_Δ•(mean),t = S²_sampling,Δ•,t / A²`
LaTeX: `S^2_{\overline{\Delta\bullet},t} = \frac{S^2_{sampling,\Delta\bullet,t}}{A^2}`

**Eq (38)**
Plain: `UNC_Δ•,t = ( sqrt(s²_Δ•,t) / Δ•_t(mean) × 100 ) × t_0.667`
LaTeX: `UNC_{\overline{\Delta\bullet},t} = \left( \frac{\sqrt{s^2_{\overline{\Delta\bullet},t}}}{\overline{\Delta\bullet}_t} \times 100 \right) \times t_{0.667}`

| Symbol | Meaning | Unit |
|---|---|---|
| • | Gas placeholder (CH4 or N2O) | - |
| h, H | Stratum, number of strata | - |
| ip, n_h | Sample point, number of points in stratum h | - |
| A_h, A | Stratum area, total project area | ha |
| Δ•_h,ip,t | Reduction at point ip | t CO2e/ha |
| Δ•_h,t (mean) | Stratum mean reduction | t CO2e/ha |
| S²_sampling | Variance | (t CO2e)² |
| S²_Δ•(mean),t | Variance of the mean | (t CO2e/ha)² |
| UNC | Deduction | **%** (Eq 38). Eq (29) needs a fraction, so divide by 100. |
| t_0.667 | One-sided Student's t at 66.7%, about 0.4307 for large n | - |

Rules:
- Random uncertainty may be excluded if the 90% CI half-width is unlikely to exceed 10% of the estimate.
- If the half-width exceeds 100%, the project is **not eligible**.
- QA1 uncertainty follows VMD0053 and VM0042 s. 8.6.1 (error propagation or Monte Carlo).
- QA3 above 60 000 t: uncertainty comes from the EF source literature or from error propagation or Monte Carlo. EF prediction error is presumed zero, and the most conservative available EF must be used.
- Fossil fuel, liming and burning EF uncertainty are excluded (p. 43-44).

## A3. Default values and tables

| Parameter | Value(s) | VM0051 page | Underlying source |
|---|---|---|---|
| EF_bsl,c | "Value depends on the country … See Table 5.11." Preference: country, then regional, then global. Tier 1 only if 60 000 t/yr or less. | p. 47 | IPCC 2019 Table 5.11 (Updated), p. 5.53 (below) |
| SC_w | Continuously flooded **1**; single drainage period **0.71**; multiple drainage periods **0.55** | p. 48 | IPCC 2019 Table 5.12 (Updated) |
| SC_p | Non-flooded pre-season <180 d (double cropping) **1.00**; >180 d (single cropping) **0.89** | p. 48 | IPCC 2019 Table 5.13 (Updated). VM0051 lists only these two rows. |
| CFOA_a | "Value depends on organic amendment type" (no numbers in VM0051) | p. 48-49 | IPCC 2019 Table 5.14 (Updated) (below) |
| ROA straw, baseline | 5 t/ha (dry) assumed | p. 26 fn 16; p. 54 | - |
| Eq (7) exponent | 0.59 | p. 26 | IPCC Eq 5.3. IPCC gives an uncertainty range of 0.54-0.64 for the exponent. |
| CF_N2O | 0.00314 kg N2O/kg N | p. 34, 50, 83 | Derived from IPCC 2019 Table 11.1 |
| EF1FR (Table 8) | Aggregated 0.004 (0.000-0.029); continuous flooding 0.003 (0.000-0.010); single and multiple drainage 0.005 (0.000-0.016) kg N2O-N/kg N | p. 83 | IPCC 2019 Table 11.1 (Updated) |
| EF1 (Table 8) | Aggregated 0.01; synthetic N in wet climates 0.016; other N in wet climates 0.006; all N in dry climates 0.005 | p. 83 | IPCC 2019 Table 11.1. Not for flooded rice. |
| EF_CO2 | Gasoline 0.002810; diesel 0.002886 t CO2e/L | p. 52 | IPCC Vol 2 Table 3.3.1 |
| EF_limestone / EF_dolomite | 0.12 / 0.13 t C/t | p. 25, 52-53 | IPCC Vol 4 s. 11.3 |
| CF_r | 0.80 | p. 57 | IPCC Vol 4 Table 2.6 |
| EF_CH4 (burning) | 2.7 g/kg dm | p. 58 | IPCC Table 2.5 |
| EF_N2O (burning) | 0.07 g/kg dm | p. 65 | IPCC Table 2.5 |
| Manure C retention | 0.12 | p. 35 | Maillard & Angers 2014 |
| M_CH4, R | 16 g/mol; 0.08206 L atm/K/mol | p. 27 | - |
| GWP_CH4, GWP_N2O | "See the most recent version of the VCS Standard" | p. 47, 49-50 | VCS Standard v5.0 s. 3.14.4 Table 9 (AR5): **CH4 = 28, N2O = 265** for reductions on or after 1 Jan 2021 |
| Uncertainty, QA3 at or below 60 000 t | 15% | p. 38, 43 | - |
| t_0.667 | about 0.4307 | p. 44 | - |

**IPCC 2019 Table 5.11 (Updated)**: EFc, kg CH4/ha/day (IPCC p. 5.53)

| Scope | EFc | Error range |
|---|---|---|
| World | 1.19 | 0.80-1.76 |
| Africa (global used) | 1.19 | 0.80-1.76 |
| East Asia | 1.32 | 0.89-1.96 |
| Southeast Asia | 1.22 | 0.83-1.81 |
| **South Asia** | **0.85** | 0.58-1.26 |
| Europe | 1.56 | 1.06-2.31 |
| North America | 0.65 | 0.44-0.96 |
| South America | 1.27 | 0.86-1.88 |

IPCC Table 5.11A gives the default cultivation period, which can stand in when L is unknown: World 113 d; South Asia 112; Southeast Asia 102; East Asia 112; Europe 123; North America 139; South America 124. Neither methodology cites Table 5.11A. Both require monitored L.

**IPCC 2019 Table 5.12 (Updated)**: SFw (p. 5.54)

| Regime | Aggregated | Disaggregated |
|---|---|---|
| Upland | 0 | 0 |
| Irrigated | 0.60 | Continuously flooded 1.00 (0.73-1.27); single drainage 0.71 (0.53-0.94); multiple drainage incl. AWD 0.55 (0.41-0.72) |
| Rainfed / deep water | 0.45 | Regular rainfed 0.54; drought prone 0.16; deep water 0.06 |

**IPCC 2019 Table 5.13 (Updated)**: SFp (p. 5.55)

| Pre-season regime | Aggregated | Disaggregated |
|---|---|---|
| Any (aggregated case) | 1.22 (1.08-1.37) | - |
| Non-flooded <180 d | - | 1.00 (0.88-1.12) |
| Non-flooded >180 d | - | 0.89 (0.80-0.99) |
| Flooded pre-season (>30 d) | - | **2.41** (2.13-2.73) |
| Non-flooded >365 d (upland crop-paddy rotation) | - | 0.59 (0.41-0.84) |

Pre-season flooding of less than 30 d is ignored when selecting SFp.

**IPCC 2019 Table 5.14 (Updated)**: CFOA (p. 5.56)

| Amendment | CFOA | Error range |
|---|---|---|
| Straw incorporated shortly (<30 d) before cultivation | 1.00 | 0.85-1.17 |
| Straw incorporated long (>30 d) before cultivation | 0.19 | 0.11-0.28 |
| Compost | 0.17 | 0.09-0.29 |
| Farmyard manure | 0.21 | 0.15-0.28 |
| Green manure | 0.45 | 0.36-0.57 |

Straw application means incorporation. It excludes surface-placed straw and straw burnt on the field.

## A4. Data to capture per field and season (VM0051)

Static or validation data (per field, then aggregated to the QU):
- Field polygon (geo-registered GIS or RS) and area in ha, re-measured each season (A_i, p. 51).
- QU and stratum assignment.
  - Mandatory strata keys: on-season and pre-season water regime, amendment type and rate, biochar, methanotrophs.
  - Under QA3, any parameter for which a scaling factor or EF is used is also a key.
  - Soil pH, texture and SOC and the agro-ecological zone are recorded once.
  - (Appendix 1 Table 4, p. 75-78.)
- Look-back schedule of activities for t = -1 to -x (x at least 3) with every Table 2 field (A1.5). Store the evidence tier for each item (Box 1 level 1-4) plus documents and attestations.
- Whether the field had single drainage in any look-back year (triggers the conservative baseline).
- Whether the field has a crop rotation (determines eligibility for the pre-season flooding change).
- Controlled irrigation and drainage evidence.
- Baseline yield P_bsl and regional yield RP_bsl.
- Expert recommendations per stratum: drainage depth, timing, duration; fertilization plan; residue; amendments; variety; tillage (p. 71).

Per season (monitored):
- Land preparation date, sowing or transplanting date, harvest date, post-season drainage date. Derive L (days) as land preparation to the later of harvest or post-season drainage.
- Establishment method (DSR or transplanting) and variety. Flag low-emission cultivars (these force QA2).
- On-season water regime: classify continuous / single / multiple. Keep evidence (farmer logbook, RS or radar dry-event detection, water tube readings) and dry-period dates, durations and depths. Note depth <10 cm (forces QA2). First AWD drainage at least 21 days after the initial flood is recommended (p. 72).
- Pre-season water status: non-flooded days before cultivation (<180, >180, >365) or flooded for more than 30 d. Record the pre-season flooding duration.
- Organic amendments: type (straw on-season or off-season with incorporation timing relative to cultivation, green manure, FYM, compost), rate in t/ha (dry for straw, fresh for others), and origin (on-site or imported, livestock type, C content) for leakage.
- Residue: burned (Y/N, area, MB in kg), removed (RS_removed,r in t dm by end-use r), retained (M_CR, t dm).
- Synthetic fertilizer: product, mass (t), NC (manufacturer). Organic fertilizer: mass, NC. Q_N,i in kg N/ha. Purchase receipts for QA/QC.
- Biochar and methanotroph application (forces QA2).
- Liming: limestone and dolomite tonnage and dates.
- Fossil fuel: type and litres (or efficiency × use).
- Yield (output/ha) measured by scale or tickets each season, and regional yield RP_wp.
- QA2 only: chamber dimensions (volume, basal area), concentrations, temperatures, times, number of chambers, interval days.
- DMRV metadata (Appendix 4): data source, resolution, cloud masking, ML accuracy, out-of-range flags, and an audit trail.

## A5. Uncertainty, leakage, permanence, crediting

- **Uncertainty**: applied per source (CH4 soil and N2O soil only, in Eq 29) as (1 - UNC). QA3 Tier 1 projects at or below 60 000 t/yr use 15% (p. 38, 43). Otherwise use Eq (38).
- **Leakage**: LE_OA (Eq 26), LE_BR (TOOL16), and LE_yield (not in Eq 29, see A6). Sources below 5% of reductions are de minimis.
- **Project-emission deductions**: PE_AB (Eq 24) and PE_Red-Irri (Eq 25, always applies with AWD or single drainage).
- **Permanence**: VM0051 has no non-permanence or buffer provision. The mitigation outcome is "Reductions" (p. 5) and SOC is explicitly not credited (Table 3 footnote, p. 19). Under the VCS Standard (s. 2.4), buffer contributions attach to carbon-stock changes. I infer that no AFOLU buffer applies to VM0051 avoidance credits. Confirm with the VCS AFOLU NPRT if SOC were ever credited.
- **Vintage**: when a verification period spans calendar years, compute by year t (p. 18).
- **Rounding**: VM0051 gives no rounding rule. VCS Methodology Requirements v5.0 (example near s. 3.9) rounds VCU volumes **down** to the nearest whole number. Apply rounding only at the issuance step.
- The monitoring plan must re-evaluate the baseline (10-year plan, p. 70). Data must be archived for at least 2 years after the last crediting period ends.

## A6. VM0051 ambiguities (with page references)

1. **Eq (5) vs Eqs (6)-(8)/(16) GWP double count (p. 25-29).** The text says the QA2 and QA3 values "in Equation (5) for f(CH4_soil)" come from Eq (16) or Eqs (6)-(8). However, Eq (8) and Eq (16) already multiply by GWP_CH4 and output t CO2e/ha, while f(·) is defined in t CH4/ha.
   [RECONSTRUCTED] Use BE_CH4,i,t from Eq (8) or (16) directly as the areal mean CH4_soil_bsl,i,t (t CO2e/ha). Equivalently, set f(·) = EF × L × 10^-3 and apply GWP once.
2. **Seasons per year in Eq (8) (p. 27).** L_t is "cultivation period in year t", and Eq (8) has no season sum. Eq (16) for QA2 does sum over seasons. Double- and triple-cropped fields need Σ_s EF_s × L_s.
   [RECONSTRUCTED] Compute per season with that season's SC_p and SC_o, then sum. This matches IPCC guidance (one calculation per cropping season).
3. **EF_bsl,c and footnote 15 (p. 26).** Footnote 15 says a project may have to "set EF_bsl,c using the emission factor for single drainage". That mixes EF_c with SC_w. The section reference "Section 6, above Table 3" is also wrong: Table 3 is in Section 8.
   Implementation: for a conservative-baseline field, set SC_bsl,w = 0.71 and keep EF_bsl,c as the IPCC EFc.
4. **EF_bsl,i,t label (p. 26).** It is described as the EF "for continuously flooded fields without organic amendments", but it is the adjusted EF.
5. **Pre-season factors (p. 48 vs IPCC Table 5.13).** VM0051's parameter table lists only 1.00 and 0.89, but Eq (6) says SC_p "must be sourced from Table 5.13 (Updated)". That table also has flooded pre-season (>30 d) = 2.41 and non-flooded >365 d = 0.59. Appendix 1 Table 4 categories are Flooded / Short drainage (<180 d) / Long drainage (>180 d).
   A project that reduces pre-season flooding (allowed by condition 9(b)) needs the 2.41 baseline value. Confirm with the VVB.
6. **CFOA for straw (p. 26, 48-49, 54).** The baseline straw assumption is 5 t/ha, but VM0051 does not say which CFOA applies (1.00 for <30 d or 0.19 for >30 d). That choice drives SC_o (2.88 vs 1.48). It must be chosen per field from the straw incorporation timing.
   Footnote 16 and p. 54 say the 5 t/ha assumption "should be adjusted" where biomass management changes materially.
7. **Applying the 5 t/ha straw assumption in the project.** If project ROA equals baseline ROA, SC_o cancels in the ratio. The methodology does not say whether the project scenario also assumes 5 t/ha by default.
8. **Appendix 3 text vs table (p. 83).** The text says the difference is between continuously flooded "(0.004 kg N2O/kg N)" and drained "(0.005 kg N2O/kg N)". However, 0.004 is the aggregated EF1FR. Table 8 gives continuous flooding = 0.003, and only (0.005 - 0.003) × 44/28 = 0.00314 reproduces CF_N2O. The units in the text should be kg N2O-N/kg N.
9. **Eq (25) Q_N,i (p. 33, 66).** Q_N,i is the total N input rate. It is unclear whether organic and residue N count. "Nitrogen input" suggests all N (the IPCC EF1FR covers all inputs).
10. **ΔCO2_lime_t has no defining equation (p. 38).** See the reconstruction in Section 8.5.
11. **LE_yield is missing from Eq (29) (p. 36-38).** There is also no conversion from % yield loss to t CO2e.
12. **UNC units (p. 38 vs p. 44).** Eq (38) returns %. Eq (29) expects a fraction.
13. **Eq (24) has no Σ_r and no area normalisation (p. 33).**
14. **Baseline reassessment timing.** The document history (p. 90) says "every five years or at project crediting renewal". Sections 1 and 6 (p. 5, 12) say at crediting-period renewal. Section 9.3.1 (p. 70) says a "ten-year baseline re-evaluation plan".
15. **Capacity limit wording.** "Capacity limit of 60 000 t CO2e per year" (p. 6, 25, 38) versus "estimated reductions above 60 000" (p. 43). Use the VCS Standard s. 3.5.12-13 definition (footnote 13).
16. **Parameter tables give wrong equation references.** EF_N is linked to Eq (20) instead of (19) (p. 59). CR is linked to Eq (21) instead of (22) (p. 63). These are cosmetic.

---

# PART B: India CCTS BM AG04.002 v1.0, "Emission reduction through improved management practices in rice cultivation"

Adopted 30 June 2026. It refers to and adopts CDM AMS-III.AU (p. 3, para 1). It applies under Sectoral Scope 04 Agriculture (p. 7, para 10). Proponents are "non-obligated entities" and verifiers are ACVAs. Additionality uses BM-T-001.

## B1. Applicability, boundary, baseline

**Typical projects (Table 1, p. 3; scope para 7, p. 6):**
- (a) Change from continuous to intermittent flooding and/or a shortened flooded period.
- (b) AWD and aerobic rice.
- (c) Change from transplanted rice to DSR.
- (d) Optional activities: methanotrophs, low-emission cultivars (no material change in root C), avoided residue burning, less fossil fuel, improved N management, biochar. Optional quantitative changes must exceed 5%.
- (e) "Emissions from organic matter are not under the purview of the methodology."

The mitigation type is GHG **emission avoidance**.

**Definitions (p. 3-4):**
- AWD ("safe-AWD") means re-irrigating when water falls to **15 cm below the soil surface** in a field water tube, or soil water potential reaches **-10 kPa at 15 cm**. VM0051 instead uses about 10 cm as general best practice and requires QA2 below 10 cm.
- Continuous flooding is defined as in VM0051.
- DSR is defined as in VM0051, but without the dry-seedbed condition.
- Water regime = ecosystem type plus flooding pattern.

**Applicability (para 8, p. 6-7):**
- (a) Irrigated, flooded fields for an extended period. Upland, rainfed and deep-water are excluded. Footnote 3: a "pilot flexibility" for upland and rainfed is at the administrator's discretion.
  - Show this with a representative regional survey or national data, covering pre-season water regime and organic amendments (all dynamic Table 2 parameters).
- (b) Controlled irrigation and drainage in both dry and wet season. Footnote 4: projects without controlled irrigation may petition the administrator with a transition roadmap.
- (c) No switch to a never-grown cultivar unless it is low-emission without yield loss.
- (d) Training and technical support, documented. The farmer must be able to determine supplemental N need (leaf colour chart, photo sensor, test strips, or an equivalent backed by literature).
- (e) No regulatory restriction.
- (f) Access to closed-chamber and laboratory infrastructure, **except** when the default-value approach is chosen. The text cites "section 5.1.2"; the actual section is 4.7.2.

**Cultivation pattern classification (para 5, Table 2, p. 4-5).** Every project field is classified, and fields with the same pattern form group g (para 6).

| # | Parameter | Type | Categories | Source |
|---|---|---|---|---|
| 1 | Water regime, on-season | Dynamic | w1 continuously flooded; w2 single drainage; w3 multiple drainage | Baseline: farmer information. Project: monitoring. |
| 2 | Water regime, pre-season | Dynamic | p1 flooded; p2 short drainage (<180 d); p3 long drainage (>180 d) | Same |
| 3 | Organic amendment | Dynamic | o1 straw on-season (applied or incorporated just before the season); o2 straw off-season (applied in the previous season); o3 green manure; o4 FYM; o5 compost; o6 none (low stubble or straw burnt) | Same |
| 4 | Soil pH | Static | s1 <7; s2 7-8; s3 >8 | ISRIC-WISE or national data |
| 5 | Soil organic carbon | Static | c1 <1%; c2 1-3%; c3 >3% | ISRIC-WISE or national data |
| 6 | Climate | Static | AEZ | Rice Almanac (3rd ed. 2002) or HarvestChoice |
| 7 | Crop duration (variety) | Dynamic | t1 long; t2 medium; t3 short | Farmer information / monitoring |

**Boundary (para 12, p. 7):** the rice fields where the cultivation method and water regime change. The methodology has no GHG source table. From the equations, the sources are CH4 (soil) and N2O (AWD increment, and N-rate increases). CO2 from land-preparation machinery is counted if it exceeds 5% of ER (para 22).

**Baseline (para 13, p. 7):** "continuation of the current practice e.g. transplanted and continuously flooded rice cultivation in the project fields." There is no look-back period length and no field-level schedule of activities, unlike VM0051. Baseline characterisation comes from a survey or national data (para 8(a)) and farmer information (Table 2).

## B2. Quantification approaches and all numbered equations

AG04.002 offers four routes:
1. **Reference-field (measurement) approach**, the default (paras 14-20). Measure seasonally integrated EF_BL and EF_P on at least 3 baseline and at least 3 project reference fields per group.
2. **IPCC Tier 1 / default-value approach** (paras 26-35, Eqs 6-10).
3. **Tier 2** (para 36): country-specific EF and/or scaling factors from peer-reviewed literature for similar agro-climatic conditions. The heading reads "Using India default values derived from IPCC tier 2 approach", but **no India values are given in the document**.
4. **(Optional) Tier 3 modelling** (paras 37-38). Uses a validated model. "Neither initial nor periodic measurements of CH4 and N2O fluxes are required." CO2 from liming, fossil fuel and burning use defaults.

### Reference-field approach (p. 7-10)

**Eq (1)**
Plain: `BE_y = Σ_s BE_s`
LaTeX: `BE_y = \sum_{s} BE_s`

**Eq (2)**
Plain: `BE_s = Σ_{g=1..G} EF_BL,s,g × A_s,g × 10^-3 × GWP_CH4`
LaTeX: `BE_s = \sum_{g=1}^{G} EF_{BL,s,g} \times A_{s,g} \times 10^{-3} \times GWP_{CH4}`

**Eq (3)**
Plain: `PE_y = Σ_s PE_s + PE_n + PE_l`
LaTeX: `PE_y = \sum_{s} PE_s + PE_n + PE_l`

**Eq (4)**
Plain: `PE_s = Σ_{g=1..G} EF_P,s,g × A_s,g × 10^-3 × GWP_CH4`
LaTeX: `PE_s = \sum_{g=1}^{G} EF_{P,s,g} \times A_{s,g} \times 10^{-3} \times GWP_{CH4}`

**Unnumbered equation (para 21, p. 9)**, the N2O increment from AWD:
Plain: `PE_n = Σ_{g=1..G} (Q_n,P,g × A_s,g) × (EF_N2O,B,g − EF_N2O,P,g) × 10^-3 × GWP_N2O`
LaTeX: `PE_n = \sum_{g=1}^{G} (Q_{n,P,g} \times A_{s,g}) \times (EF_{N2O,B,g} - EF_{N2O,P,g}) \times 10^{-3} \times GWP_{N2O}`

**Eq (5)**
Plain: `ER_y = (BE_y − PE_y) × (1 − U_d)`
LaTeX: `ER_y = (BE_y - PE_y) \times (1 - U_d)`

| Symbol | Meaning (verbatim) | Unit / value |
|---|---|---|
| BE_y | Baseline emissions in year y | t CO2e |
| BE_s | Baseline emissions from project fields in season s | t CO2e |
| EF_BL,s,g | Baseline EF of group g in season s. The seasonally integrated average of 3 reference-field measurements (para 15). | kg CH4/ha per season |
| A_s,g | Area of project fields of group g in season s. Only compliant farms count (p. 17, para 42). | ha |
| GWP_CH4 | 29.8 (footnote 5: "IPCC Global Warming Potential Values 07082024", which corresponds to AR6) | t CO2e/t CH4 |
| g, G | Group with the same cultivation pattern (Table 2); number of groups | - |
| PE_y | Project emissions in year y | t CO2e |
| PE_s | Project CH4 emissions in season s | t CO2e |
| PE_n | Project N2O emissions from N inputs. The where-list also restates it as "Project emissions from project fields in season s". | t CO2e |
| PE_l | Project CO2 from field preparation | t CO2e |
| EF_P,s,g | Project EF of group g in season s, from at least 3 project reference fields located near the baseline fields and starting at the same time (para 20) | kg CH4/ha per season |
| Q_n,P,g | "Application rate of N-input in the project scenario where the application rate doesn't exceed that of baseline". Data table 10 (p. 19) says "**where it exceeds** the baseline application rate". | kg N/ha |
| EF_N2O,P,g | EF for single and multiple drainage: **0.005** | kg N2O-N/kg N input |
| EF_N2O,B,g | EF for continuously flooded: **0.003** | kg N2O-N/kg N input |
| GWP_N2O | **273.0** (footnote 6, AR6) | t CO2e/t N2O |
| ER_y | Emission reductions in year y | t CO2e |
| U_d | Uncertainty deduction. Fixed at 15% (para 45, p. 20). | % |

Further rules:
- **PE_l** (para 22, p. 10): CO2 from machinery for land preparation. Count it only if it exceeds 5% of ER_y, then calculate with BM-T-002. The fuel parameter Q_F,i (litres) is monitored **only in year 1** (p. 18-19).
- **N2O from N-rate changes** (para 17, p. 8): fertilizer increases must be counted as project emissions. The methodology gives **no equation** for this (BM-T or IPCC is implied).
- **Para 23**: N2O reductions from lower fertilizer use **cannot be claimed**.
- **Leakage** (para 16, p. 8): deemed negligible, so it is not considered.

### IPCC Tier 1 / default-value approach (paras 26-35, p. 10-14)

Para 27: "Using the IPCC tier 1 approach but undertaking measurements to determine baseline emission factors for continuously flooded fields, as per the following formula:"

**Eq (6)**
Plain: `ER_y = EF_ER × A_y × L_y × 10^-3 × GWP_CH4 × (1 − U_d)`
LaTeX: `ER_y = EF_{ER} \times A_y \times L_y \times 10^{-3} \times GWP_{CH4} \times (1 - U_d)`

**Eq (7)** (transcribed exactly as printed)
Plain: `EF_ER = EF_BL − EF_P × (1 − U_d)`
LaTeX: `EF_{ER} = EF_{BL} - EF_P \times (1 - U_d)`
See B6 item 1.

**Eq (8)**
Plain: `EF_BL = EF_BL,c × SF_BL,w × SF_BL,p × SF_BL,o`
LaTeX: `EF_{BL} = EF_{BL,c} \times SF_{BL,w} \times SF_{BL,p} \times SF_{BL,o}`

**Eq (9)**
Plain: `EF_P = EF_BL,c × SF_P,w × SF_P,p × SF_P,o`
LaTeX: `EF_P = EF_{BL,c} \times SF_{P,w} \times SF_{P,p} \times SF_{P,o}`

**Eq (10)**
Plain: `SF_o = (1 + Σ_i ROA_i × CFOA_i)^0.59`
LaTeX: `SF_o = \left(1 + \sum_{i} ROA_i \times CFOA_i\right)^{0.59}`

| Symbol | Meaning (verbatim) | Unit / value |
|---|---|---|
| ER_y | Emission reductions in year y | t CO2e |
| EF_ER | "Adjusted daily emission factor (kgCH4/ha/day). Alternatively, seasonal emission factor (kgCH4/ha/season) may be determined". Footnote 7: a "season" runs from land preparation until harvest or post-season drainage; a seasonal EF must cover the whole flooding period including the drainage CH4 pulse. | kg CH4/ha/day or kg CH4/ha/season |
| A_y | Area of project fields in year y (compliant farms only, p. 17) | ha |
| L_y | Cultivation period in year y. Not applicable when a seasonal EF is used. | days/year |
| GWP_CH4 | 29.8 | t CO2e/t CH4 |
| EF_BL / EF_P | Baseline / project EF | kg CH4/ha/day or /season |
| EF_BL,c | Baseline EF for continuously flooded fields without organic amendments. Determined ex ante before the start (and then used for the crediting period) or monitored annually (ex post), on at least 3 reference fields with closed chambers (para 28). | kg CH4/ha/day or /season |
| SF_BL,w / SF_P,w | Water-regime scaling factor during cultivation | - |
| SF_BL,p / SF_P,p | Pre-season water-regime scaling factor | - |
| SF_BL,o / SF_P,o | Organic amendment scaling factor | - |
| ROA_i | Rate of amendment i, dry weight for straw and fresh weight for others. **5 t/ha straw assumed as baseline** (range 3 t/ha manual harvest to 7 t/ha mechanical). | t/ha |
| CFOA_i | Conversion factor relative to straw applied shortly before cultivation: "0.19 is used for a single crop and 1.0 for a double crop" | - |
| U_d | "Apply default value of 15% for IPCC default values (global, regional or country specific)" | % |

Para 29: alternatively, EF_BL,c may be determined **for continuously flooded fields with organic amendments**. In that case SF_o is not applied in Eqs (8) and (9).

Para 25 (ex ante, p. 10): PDD estimates may use the proponent's own experiments, national data, or IPCC Tier 1 defaults.

## B3. Default values and tables (AG04.002)

**Table 3 (p. 12): SF_w** (source cited: IPCC 2019 Vol 4 Ch 5.5 Table 5.12)

| Regime | SF_BL,w or SF_P,w |
|---|---|
| Irrigated, continuously flooded | 1 |
| Intermittently flooded, single aeration | 0.71 |
| Intermittently flooded, multiple aeration | 0.55 |

Notes to Table 3:
- Intermittently flooded means at least one aeration period of **more than 3 days**, excluding end-season drainage.
- Single aeration = one such period. Multiple aeration = more than one.

**Table 4 (p. 12): SF_p** (source cited: IPCC **2006** Vol 4 Ch 5.5 Table 5.13)

| Pre-season regime | SF_BL,p or SF_P,p |
|---|---|
| Non-flooded pre-season <180 d (double cropping) | 1 |
| Non-flooded pre-season >180 d (single cropping) | 0.89 |

Para 31: use 1.0 where official government data or peer-reviewed literature shows double cropping in the region or country, otherwise 0.89.

**Eq (10) defaults / Table 5 (p. 13)**, for rice straw only:

| Pre-season regime | SF_o | Computation as printed |
|---|---|---|
| Non-flooded <180 d (double cropping) | 2.88 | (1 + 5 × 1)^0.59 = 2.88 |
| Non-flooded >180 d (single cropping) | 1.48 | (1 + 5 × 0.19)^0.59 = 1.48 |

The source cited is IPCC 2019 Table 5.14. Arithmetic check: 6^0.59 = 2.878 and 1.95^0.59 = 1.483. Both are correct.

**Para 34 (p. 13): other amendments**
- Compost: SF_o = (1 + C × 0.17)^0.59
- FYM: SF_o = (1 + YM × 0.21)^0.59
- Green manure: SF_o = (1 + GM × 0.45)^0.59
- C, YM, GM are application rates in t/ha.

Each formula is written alone. A combination of straw plus manure would need the summed form of Eq (10).

**Table 6 (p. 14): pre-computed EFs, as multiples of EF_BL,c** (kg CH4/ha/day or /season)

| Context | Baseline SF_w / SF_p / SF_o | EF_BL | Project scenario | Project SF_w / SF_p / SF_o | EF_P | EF_ER |
|---|---|---|---|---|---|---|
| Double cropping | 1.00 / 1.00 / 2.88 | EF_BL,c × 2.88 | S1 single aeration | 0.71 / 1.00 / 2.88 | × 2.04 | × 0.84 |
| Double cropping | 1.00 / 1.00 / 2.88 | EF_BL,c × 2.88 | S2 multiple aeration | 0.55 / 1.00 / 2.88 | × 1.58 | × 1.30 |
| Single cropping | 1.00 / 0.89 / 1.48 | EF_BL,c × 1.32 | S1 single aeration | 0.71 / 0.89 / 1.48 | × 0.94 | × 0.38 |
| Single cropping | 1.00 / 0.89 / 1.48 | EF_BL,c × 1.32 | S2 multiple aeration | 0.55 / 0.89 / 1.48 | × 0.72 | × 0.60 |

Arithmetic check:
- 0.71 × 2.88 = 2.045
- 0.55 × 2.88 = 1.584
- 0.89 × 1.48 = 1.317
- 0.71 × 0.89 × 1.48 = 0.935
- 0.55 × 0.89 × 1.48 = 0.724

**In every row, EF_ER = EF_BL - EF_P with no (1 - U_d) factor.** For example, 2.88 - 2.04 = 0.84 and 1.32 - 0.72 = 0.60.

**Other constants in AG04.002:**

| Constant | Value | Page |
|---|---|---|
| GWP_CH4 | 29.8 | p. 8, 9, 11 |
| GWP_N2O | 273.0 | p. 10 |
| EF_N2O continuous flooding | 0.003 kg N2O-N/kg N | p. 10 |
| EF_N2O single and multiple drainage | 0.005 kg N2O-N/kg N | p. 10 |
| U_d | 15% | p. 11, 20 |
| M_CH4 | 16 g/mol | p. 23 |
| R | 0.08206 L atm K^-1 mol^-1 (printed "0,08206") | p. 23 |
| mg/m2 to kg/ha | × 0.01 | p. 23 |
| AWD trigger | 15 cm / -10 kPa | p. 3 |

**EF_BL,c has no numeric default in AG04.002.** IPCC 2019 Table 5.11 gives South Asia = 0.85 kg CH4/ha/day (see A3). Using it requires reading the methodology as allowing IPCC defaults for EF_BL,c (see B6 item 3).

### Annexure 1: chamber equations (p. 21-23)

**Annex Eq (1)**
Plain: `m_CH4,t = c_CH4,t × V_Chamber × M_CH4 × 1 atm / (R × T_t × 1000)`
LaTeX: `m_{CH4,t} = c_{CH4,t} \times V_{Chamber} \times M_{CH4} \times \frac{1\,atm}{R \times T_t \times 1000}`

**Annex Eq (2)**
Plain: `s = Δm_CH4 / Δt`
LaTeX: `s = \frac{\Delta m_{CH4}}{\Delta t}`

**Annex Eq (3)**
Plain: `RE_ch = s × 60 min / A_Chamber`
LaTeX: `RE_{ch} = s \times 60\,min / A_{Chamber}`

**Annex Eq (4)**
Plain: `RE_plot = ( Σ_{ch=1..Ch} RE_ch ) / Ch`
LaTeX: `RE_{plot} = \frac{\sum_{ch=1}^{Ch} RE_{ch}}{Ch}`

| Symbol | Meaning | Unit |
|---|---|---|
| m_CH4,t | CH4 mass in chamber at time t | mg |
| t | Sample time (0, 15, 30) | min |
| c_CH4,t | Concentration | ppm |
| V_Chamber | Volume | L |
| T_t | Temperature | K |
| s | Slope | mg/min |
| RE_ch, RE_plot | Emission rate per chamber / plot mean | mg/(h·m2) |
| A_Chamber | Chamber area | m2 |
| Ch | Number of replicate chambers per plot (at least 3) | - |

Seasonal integration is described in words only: sum rate × interval hours and convert mg/m2 to kg/ha with × 0.01. **No trapezoid equation is given**, unlike VM0051 Eq 13.

Minimums: 3 replicate chambers per plot; 3 samples per 30-min exposure; morning sampling; weekly sampling plus extra samples 2, 3 and 5 days after fertilizer.

## B4. Data to capture per field and season (AG04.002)

From the monitoring tables (p. 15-19) and paras 40-44:
- **Farm database**: farmer name and address, field size (GPS or satellite; otherwise conservative), unambiguous field ID, group g (Table 2 pattern).
- **Static**: soil pH class, SOC class, AEZ.
- **Per season**: A_s,g (compliant fields only); sowing date; land-preparation operations; fertilizer, organic amendment and crop-protection applications (date and amount); water status ("dry / moist / flooded") with the date of each change; yield; farmer statement on following the fertilization recommendations (para 41).
- **Per year**: A_y and L_y (Tier 1 and 2 only); organic amendment by category in kg (annual); synthetic fertilizer in kg (annual); Q_N,P,g in kg N/ha (annual).
- **Q_F,i**: litres of fossil fuel used in land preparation, first year only.
- **Reference fields** (measurement routes): EF_BL,s,g, EF_P,s,g and EF_BL,c from closed chambers, with the full seasonal measurement plan (Annexure para 2).
- **Remote sensing**: SAR or NDVI with GIS is **optional** for water-regime and crop-growth monitoring (para 15). DMRV is encouraged (footnote 10) with the same QA/QC best practices as VM0051 Appendix 4: value ranges, an SOP, audit trail and accuracy thresholds.
- **Baseline data**: from regional studies, official data, farmer interviews or records. Sampling is allowed (p. 18).
- **Verification**: based on samples of logbooks per the CCTS "Detailed Procedure for Offset Mechanism" (para 43).

## B5. Uncertainty, leakage, permanence, crediting

- **Uncertainty**: a flat **15%** U_d on emission reductions (para 45, p. 20; Eq 5; Eq 6). There is no statistical uncertainty procedure.
- **Leakage**: none; deemed negligible (para 16).
- **Permanence**: not addressed. This is an avoidance methodology ("emission avoidance", p. 3), so no buffer applies.
- **Rounding and crediting**: not specified in AG04.002. It falls under the CCTS "Detailed Procedure for Offset Mechanism", which is not reviewed here.
- **Deductions**: PE_n (always with AWD) and PE_l (only if more than 5% of ER, year 1 only). N2O savings from fertilizer cuts are not creditable.
- **Compliance filter**: fields that deviate from the project practice are excluded from A_s,g (para 42).

## B6. AG04.002 ambiguities (with page references)

1. **Eq (7) double-applies U_d and has a precedence problem (p. 11).** As printed, `EF_ER = EF_BL − EF_P × (1 − U_d)`, and Eq (6) applies `× (1 − U_d)` again. Read literally, U_d scales only EF_P, which *raises* ER, and is then applied a second time.
   - Table 6 (p. 14) computes EF_ER = EF_BL - EF_P with no U_d.
   - Para 45 says a single 15% deduction applies.
   - [RECONSTRUCTED] Implement `EF_ER = EF_BL − EF_P` and apply (1 - U_d) once, in Eq (6). Flag this for the administrator or ACVA.
2. **Sign and unit error in the PE_n equation (p. 9-10).** (EF_N2O,B - EF_N2O,P) = 0.003 - 0.005 = **-0.002**, so PE_n comes out negative (it would add to ER). The EFs are in kg N2O-**N**, but there is no 44/28 conversion before GWP_N2O.
   - [RECONSTRUCTED] `PE_n = Σ_g (Q_n,P,g × A_s,g) × (EF_N2O,P,g − EF_N2O,B,g) × 44/28 × 10^-3 × GWP_N2O`. This equals VM0051's CF_N2O = 0.00314 approach. The source text needs confirmation.
   - The literal formula without 44/28 understates the deduction by a factor of 1.571.
3. **Is EF_BL,c measured or defaulted? (p. 7, 10-12)**
   - Para 27 says Tier 1 is used "but undertaking measurements to determine baseline emission factors for continuously flooded fields". Para 28 requires at least 3 reference fields with chambers.
   - Against that: para 8(f) exempts the default-value approach from the chamber-infrastructure requirement; the U_d definition refers to "IPCC default values (global, regional or country specific)"; and para 25 allows IPCC Tier 1 defaults ex ante.
   - The text therefore conflicts on whether EF_BL,c may be the IPCC Table 5.11 value (South Asia 0.85).
4. **Q_n,P,g definition conflict.** The equation's where-list (p. 9) says the rate "doesn't exceed" the baseline. Data table 10 (p. 19) says "where it exceeds the baseline". Para 21 says the increment assumes no increase in N input.
   [RECONSTRUCTED] Q_n,P,g = the project N rate (kg N/ha). Increases above baseline are handled separately under para 17, which has no equation.
5. **CFOA footnote 9 (p. 13)** says "therefore, 0.29 is used" for single crop, but the body (p. 13) and Table 5 use **0.19**. IPCC 2019 Table 5.14 gives 0.19 (>30 d before cultivation). Use 0.19.
6. **CFOA keyed to cropping system rather than incorporation timing.** IPCC keys CFOA on incorporation <30 d (1.00) vs >30 d (0.19). AG04.002 maps these to double vs single cropping, and SF_p is likewise defaulted by regional cropping intensity (para 31), not by field-level pre-season data.
7. **SF_p source year.** Table 4 cites IPCC **2006** Table 5.13, but 0.89 is the **2019 Refinement** value (confirmed in the local IPCC 2019 PDF, p. 5.55). Footnote 8 says "average values in 2006 IPCC Guidelines are chosen" for all scaling factors. [Not verified locally: the 2006 Table 5.13 value for >180 d differs from 0.89; the 2006 chapter is not in the repo.]
8. **SF_p has no flooded pre-season or >365 d rows.** Table 2 has category p1 "Flooded" but Table 4 offers no factor for it (IPCC 2019: 2.41). Pre-season flooding reduction is a listed project type (para 7(a) "shortened period of flooded conditions"), but it cannot be quantified with the defaults given.
9. **DSR has no scaling factor.** DSR (para 7(c)) appears in no SF table. Under Tier 1 it must be expressed through SF_w (reduced flooding) or a shorter L. The method is unspecified.
10. **Units of L_y** (p. 11) are "days/year", and A_y is annual area. With multiple seasons per year, Eq (6) is underspecified: should A_y be summed harvested area or physical area? IPCC uses harvested area (the sum over croppings) with season-specific factors.
    [RECONSTRUCTED] Compute Σ_s EF_ER,s × A_s × L_s.
11. **Tier 1 route drops PE_n and PE_l.** Eq (6) contains CH4 only. Para 36 (Tier 2) says project emissions follow s. 4.6 and ER follows s. 4.7, which implies PE_n and PE_l should also be deducted under Tier 1/2.
    [RECONSTRUCTED] `ER_y = [Σ CH4 (EF_BL − EF_P) × A × L × 10^-3 × GWP_CH4 − PE_n − PE_l] × (1 − U_d)`, consistent with Eq (5).
12. **Wrong cross-references.** "Section 5.1.2" in para 8(f) should be 4.7.2. "Paragraph 3(d)" in para 17 should be 8(d). "The appendix" refers to Annexure 1.
13. **"India default values derived from IPCC tier 2 approach" (p. 15)** is a heading with no values under it.
14. **Text-extraction traps.** "29.85" and "273.06" in the text dump are 29.8 and 273.0 plus footnote markers 5 and 6 (confirmed on renders of p. 8 and p. 10).
15. **GWP basis.** AR6 values (29.8, 273) are cited from a 07-Aug-2024 IPCC GWP list. This differs from VCS v5.0 (AR5: 28 and 265).

---

# PART C: Can one platform module implement the Tier 1/2 emission-factor approach of both?

**Yes, with a shared core and methodology-specific profiles.** The algebra is identical at its core: IPCC 2019 Eq 5.2 / 5.3, `EF = EFc × SFw × SFp × SFo`, `SFo = (1 + Σ ROA × CFOA)^0.59`, and `E = EF × days × area × 10^-3 × GWP`. The SFw values (1 / 0.71 / 0.55), SFp values (1.00 / 0.89), CFOA values (1.00 / 0.19 / 0.17 / 0.21 / 0.45), the 5 t/ha baseline straw assumption, and the 15% Tier 1 uncertainty deduction are the same in both.

### Shared input schema (per field × season)
- field_id, polygon, area_ha, season_id, crop_year
- land_prep_date, sow/transplant_date, harvest_date, post_season_drainage_date, giving cultivation_days (L)
- establishment (DSR / TPR), variety, duration class
- water_regime_on_season (continuous / single / multiple) plus evidence (logbook, RS events, dry-period dates and depth)
- pre_season_status (non-flooded <180 / >180 / >365 / flooded >30 d) plus days
- organic_amendments[] {type, timing relative to cultivation (<30 / >30 d), rate_t_ha, dry/fresh basis, origin, C content}
- residue {burned Y/N, mass, removed t dm and end use, retained t dm}
- synthetic_N[] {product, mass, N content}, organic_N[], giving N rate in kg N/ha
- fuel {type, litres}, lime {limestone t, dolomite t}
- yield (output/ha)
- compliance flag (AG04 para 42) and baseline (look-back or survey) record with evidence tier
- static soil pH, SOC, texture, AEZ, and group/stratum key

### Shared calculation core
1. `sf_o(amendments, cfoa_table)` → (1 + Σ ROA·CFOA)^0.59
2. `ef_adj(ef_c, sf_w, sf_p, sf_o)`
3. `season_ch4_tco2e(ef_adj, L, area, gwp)` = ef_adj × L × area × 10^-3 × gwp
4. `n2o_awd_increment(N_kg_ha, area, gwp_n2o)` = N × area × (0.005 − 0.003) × 44/28 × 10^-3 × gwp. This is VM0051 Eq 25 and the corrected AG04.002 PE_n.
5. A deduction wrapper `× (1 − U)`.

### Profile differences that must be parameterised

| Aspect | VM0051 v1.1 | BM AG04.002 v1.0 |
|---|---|---|
| GWP_CH4 / GWP_N2O | Per VCS Standard. v5.0 = AR5: **28 / 265** | **29.8 / 273.0** (AR6) |
| EF_c source | IPCC Table 5.11, country, then regional, then global. Tier 1 only if 60 000 t/yr or less, otherwise country-specific Tier 2 EF required. | Measured on at least 3 reference fields (para 27-28), ex ante or annually; IPCC default arguably allowed (ambiguity B6-3). May be measured *with* amendments, in which case SF_o is dropped (para 29). |
| EF unit | Daily only (kg/ha/day) × L | Daily × L **or** seasonal (kg/ha/season), with L not used |
| SF_p choice | Field-level from pre-season water status; IPCC Table 5.13 (Updated), including 2.41 for flooded pre-season (implied) | Regional default: 1.0 if double cropping is documented for the region, else 0.89. No flooded row. |
| CFOA for straw | From IPCC Table 5.14 by incorporation timing (field-level) | 1.0 double crop / 0.19 single crop (cropping-system proxy) |
| Baseline setting | Per-field look-back (3 years or more) schedule of activities, Box 1 evidence hierarchy, conservative single-drainage rule, dynamic L exception, baseline re-evaluation | "Continuation of current practice" from a regional survey or national data plus farmer information. No look-back length. |
| Unit of calculation | Quantification unit i (stratum) per year t. Areal means × A_i. Vintage by calendar year. | Group g per season s, summed to year y |
| Uncertainty | (1 − UNC) applied **only to ΔCH4_soil and ΔN2O_soil** (15% for Tier 1 at or below 60 000 t; statistical above that) | (1 − U_d) = 0.85 on the **whole** net ER |
| N2O | AWD correction (Eq 25) always, deducted **after** uncertainty. Full Eq 19-22 when N rate changes (increase or decrease, so reductions are creditable). | AWD increment PE_n (with sign and unit errors to correct). Increases counted with no equation; **decreases not creditable**. |
| Other sources | Fossil fuel (Eq 1-2), liming (Eq 3-4), burning CH4/N2O (Eq 17, 23), straw end use (Eq 24), all in S* boundary logic | Land-prep fuel CO2 only, if more than 5% of ER, year 1 only, via BM-T-002 |
| Leakage | LE_OA (Eq 26), LE_yield (5% test), LE_BR (TOOL16) | None |
| Activity gates | QA2 mandatory for methanotrophs, biochar, low-emission cultivars, AWD <10 cm; same number of seasons per year; no off-season changes | AWD trigger 15 cm / -10 kPa; N-need tool required; no new cultivar unless low-emission |
| Scale limit | 60 000 t CO2e/yr for Tier 1 + 15% | None |
| Rounding | VCS: round VCUs down to a whole number (VCS Methodology Requirements v5.0) | Not stated in methodology (CCTS procedure) |
| Equation defects to patch | Eq 5 vs 8 GWP double count; season sum in Eq 8; ΔCO2_lime missing | Eq 7 U_d double count; PE_n sign and 44/28; Tier 1 path omits PE_n and PE_l |

### Recommended module design
- **One `RiceIPCCEmissionFactorEngine`** computes per field × season: SF_w, SF_p, SF_o, EF_adj (baseline and project), CH4 in t, and the AWD N2O increment in t N2O. It outputs **gas-mass results (t CH4, t N2O)**, not CO2e.
- **Methodology profiles** (`VM0051_v1_1`, `CCTS_AG04_002_v1_0`) supply:
  - GWP set
  - factor-lookup rules (field-level vs regional SF_p and CFOA; EF_c source and the daily vs seasonal flag)
  - aggregation key (QU × calendar year vs group × season → year)
  - where the uncertainty factor is applied (per source vs whole ER)
  - extra sources and leakage modules (VM0051 only)
  - eligibility gates and the compliance filter
  - a "literal vs corrected" switch for each documented defect, so the VVB/ACVA-agreed interpretation is explicit and auditable
- **Shared data capture works for both** if the platform records field-level detail: pre-season days, straw incorporation timing, and season-level water regime evidence. AG04.002's coarser defaults can be derived from those fields, but not the other way round.
- **Not shareable**: VM0051's look-back schedule, Box 1 evidence tiers and statistical uncertainty (QA1/QA2). AG04.002's reference-field paired-measurement route can reuse the VM0051 QA2 chamber code (Eqs 9-15 ≈ Annex Eqs 1-4 plus integration). The conversion factors differ: VM0051 uses 10^-5 to t/ha; AG04 uses 0.01 to kg/ha.
