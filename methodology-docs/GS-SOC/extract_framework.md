# Extraction: Gold Standard Soil Organic Carbon Framework Methodology v1.0 (GS 402)

Source: `GS-SOC/GS_402_SOC_Framework_Methodology_v1.0.pdf`, 46 pages, published January 2020. Developed by TREES Consulting. SDG 13.
The page numbers ("p.") below are the printed page numbers, which match the PDF page index.
Every equation was checked against a rendered image of its page. Variable definitions and units are copied exactly as printed, including any errors in the original; those errors are flagged in Section 8.

---

## 1. Structure

### 1.1 Architecture (p.3-6, Table 1)
- The **Framework Methodology** (this document) sets the core equations, the three quantification approaches, the GHG and pool list, uncertainty, leakage guidelines, buffer, and monitoring rules.
- **Activity Modules** (separate documents, "to be developed on an ongoing basis") set:
  - activity-specific applicability;
  - which of Approaches 1/2/3 are allowed;
  - detailed equations and models with their parameters;
  - which GHGs are monitored, with a justification for each inclusion or exclusion;
  - crediting period length (within 5-20 yr);
  - stratification criteria (a subset of, or additions to, the framework list);
  - leakage calculations;
  - any specific buffer or non-permanence requirements;
  - extra monitoring parameters;
  - default SDGs.
- "A project cannot apply the Framework Methodology without an applicable Activity Module." (p.8)
- A project may apply one or more modules if activities are clearly delineated and the SOC benefits do not overlap (p.4). Overlap rules are in Section 12 (p.33-34; see 1.6 below).
- It replaces the "GS Agriculture Methodology for Increasing Soil Carbon Through Improved Tillage Practices V0.9" (p.8).

### 1.2 Applicability (Section 3, p.8-9)
a. **Geography:** all countries. Modules may restrict this.

b. **Project area:**
- The project must be on the same parcel of land as the baseline.
- Not on wetlands. Wetland is defined per the IPCC 2019 Refinement glossary as land covered or saturated by water for all or part of the year, e.g. peatland (fn 1).
- Not on forest as defined in the LUF Activity Requirements.

c. **Site preparation:**
- No biomass burning for site preparation in the project scenario.
- No changes in surface and shallow (<1 m) soil water regimes through flood irrigation, drainage or other significant anthropogenic changes in the ground water table.

d. **Land use:**
- Managed cropping systems (e.g. single crop or crop rotation) must have been in place for **at least 5 years** before project implementation.
- The project shall not lead to land use change.
- Fn 2: if a module considers a crop change, it must show no negative SOC impact in the medium term (e.g. 5 years), or must quantify the change. The parameters to consider are listed in fn 2:
  - agrochemical inputs;
  - hydrology;
  - crop inputs, residue and N-fixation;
  - machinery;
  - seasonal management;
  - market leakage (revenue, and yield in tons and in calorific value).
- Fn 3: for grassland-to-cropland conversion or the reverse, contact the GS Secretariat.

e. **Food security:**
- No reduction in crop yield attributable to the project is allowed.
- Yield must be at least the baseline yield, defined as the five-year average before project start.
- If regional productivity changes (e.g. due to climate), project-area yield shall not decrease significantly (5%) more than yield in the project region.

### 1.3 Project boundary (Section 4, p.9-11)
- **Spatial (4.1):** the impacts of activities under the project owner's control.
  - Areas leaving the project (no longer monitored) are treated conservatively as **full reversals**, i.e. loss of all carbon sequestered.
  - Under the LUF Activity Requirements, the owner must maintain the carbon, or compensate losses up to the level of credits already issued, per the GHG Emissions Reductions & Sequestration Product Requirements.
  - New areas follow the "new area certification" procedure in the LUF Activity Requirements.
- **Temporal (4.2):** crediting period **5-20 years**. The module sets the exact length based on peer-reviewed science. Retroactive projects follow the "Retroactive Issuance" chapter of the LUF Activity Requirements.
- **Carbon pools (4.3, Table 2, p.10):**

| Pool | Includes | Project | Baseline | Leakage |
|---|---|---|---|---|
| Above ground | Stem, branches, bark, grass, herbs, etc. | No | No | Yes* |
| Below ground | Roots of grass, trees, herbs | No | No | Yes* |
| Deadwood | Standing and lying deadwood | No | No | No |
| Litter | Leaves, small fallen branches | No | No | No |
| Soil organic carbon | Organic material | Yes | Yes | Yes |
| Wood products | Furniture, construction material, etc. | No | No | No |

\* Change in biomass carbon stocks in the leakage area is accounted for in case of activity shift (Section 11).

- **GHGs (4.4, p.10-11):**
  - **CO2 is the primary gas.** CH4 and N2O "may be required" by Activity Modules (e.g. leakage risk, change in fertilization).
  - In principle all affected sinks and sources are monitored. Exclusions are allowed for impacts with limited measurability if the omission is conservative.
  - Emissions that are **insignificant (<5% of total emission reduction and sequestration)** may be omitted.

### 1.4 Quantification approaches (Section 5.1, p.12-13; Figure 2)

| Approach | Basis | Accuracy / deductions per Figure 2 |
|---|---|---|
| **Approach 1** | On-site measurements directly document baseline and project SOC stocks | High accuracy; no deductions |
| **Approach 2** | Calculation approaches, datasets, parameters and/or models from peer-reviewed publications. The owner must prove they are conservative and applicable to the site and practice. | Medium accuracy; deductions possible |
| **Approach 3** | Default factors following the IPCC 2019 Tier 1/2 model. Tier 2 should be used if possible. Applicability of SOCREF must be shown transparently. | Low accuracy; deductions likely |

- Bold note, p.12:
  - Not all approaches may be applicable to every activity.
  - Locally derived datasets and models may only be applied if validated by direct measurements in the project area (Approach 1).
  - **Modules must define which approaches are applicable.** The GS Secretariat assesses this at module review.
- Owners shall select the most specific approach possible with the data available, preferring local data and models.
- **Decision tree (Figure 2, p.13):**
  1. Identify project activity and boundaries.
  2. Are on-site SOC measurements (before and after the change) ongoing or planned? Yes → Approach 1. No → next question.
  3. Is applicable peer-reviewed research data or a model (before and after the change) available? Yes → Approach 2. No → next question.
  4. Are an applicable SOCREF value and impact factors available? Yes → Approach 3. No → "Perform SOC measurements", which loops back to step 2.
- **Strata can use different approaches** (p.14).
- **Ex-ante project estimates must use Approach 2**, i.e. literature or an accepted soil carbon model such as RothC or Century (p.21).
- **Approach 3 scope limit (p.15):** IPCC only provides stock change factors for tillage change and generic inputs (fertilizing) on cropland and grassland. Approach 3 therefore does not apply to activities that increase SOC in other ways (e.g. biological soil agents), unless additional factors exist for the area (e.g. Tier 2 factors from the national inventory).

### 1.5 Baseline determination (Section 6, p.13-20)
- The baseline is the continuation of the historical land management practices followed in the **last 5 years** before the project start date (BAU).
- Stratify into **Modelling Units (MU)** by:
  - soil type;
  - climate zone;
  - land management / cropping system;
  - input levels (e.g. fertilization);
  - where a module requires it: tillage practices, soil properties (e.g. nutrient status or soil health), hydrology, and risk of carbon loss (e.g. fire risk).
- The same stratification applies to the project scenario (Section 7, p.20).
- For each MU, SOC is either measured (Approach 1) or model parameters are identified and verified (Approach 2/3).
- Baseline SOC comes from Eq. 3. Under Approach 3, SOCBL,y comes from Eq. 4.
- **Approach 2 literature rules (p.14, p.21-22):**
  - Applicability must be shown for climate factors (e.g. precipitation levels and seasonal distribution), soil and vegetation types, and current and historic management systems (land use category, crops, tillage, fertilization).
  - Values may only be used within the spatial and temporal dimensions of the source (e.g. SOC depth, timespan).
  - If the source gives a range, or data aggregated across factor levels, **the most conservative value** shall be applied.
  - Literature values may be verified against measurements at sample sites. Such measurements are **required** if the VVB deems the applicability evidence insufficient.
- **Approach 3:**
  - SOCREF must come from a scientific source or measurements (fn 8: ISRIC, Hengl et al. 2014, European Soil Portal). Applicability must be documented.
  - "IPCC default SOC reference values (SOCREF) may only be applied if within Gold Standard Uncertainty Requirements" (fn 8, p.15).
  - FLU, FMG and FI may use IPCC 2019 defaults (Tables 3 and 4). National or regional Tier 2/3 factors "should be used instead" when available (p.16).

### 1.6 Project scenario and approach-change rules
- **Project scenario (Section 7, p.20-23):**
  - Eq. 5 gives SOCt. Under Approach 3, SOCt,y comes from Eq. 6.
  - SOCREF,y and FLU,y are identical to the baseline values, since there is no land use change.
  - The same climate zone and soil type as the baseline must be used.
  - If Tier 2/3 factors are used, D must match their source.
- **Approach change (Section 8, p.23-25):**
  1. Changing from Approach 1 or 2 to Approach 3 is **not allowed**.
  2. At project start, compare the results of both approaches:
     - **(a) Neutral change:** the new result differs by no more than 5% from the verified baseline value of the previous approach. The new result is used. Exception: if the baseline was measured under Approach 1 and is higher than the new Approach 2 result, the measured value is kept.
     - **(b) Modelled change:** a new Approach 2 result differs by more than 5%. The VVB reviews the applicability of the dataset or model and its parametrization at validation. If accepted, the baseline is corrected. The same Approach 1 exception applies.
     - **(c) Measured change:** a new Approach 1 result differs by more than 5%. The baseline is corrected; measurements take precedence.
  - Table 5 (p.25) gives seven worked examples.
- **Benefits overlap (Section 12, p.33-34):**
  - Strata measured with Approach 1 capture all activities; no extra model increments are added.
  - Under Approach 2/3 without measurement, impacts may only be summed if the SOC pools can be separated chemically, physically or geographically, or if a cumulative impact is proven. Otherwise only one activity is credited. Direct measurement is recommended.

---

## 2. Equations (19 numbered equations)

### Eq. 1. Emission reductions for issuance (Section 5, p.11)
Plain text: `ER_(t-0) = [ ( ΔC_(SOC,t-0) × 44/12 ) − PE_(t-0) − LK_(t-0) ] × (1 − BUF)`

LaTeX: `ER_{t-0} = \left[\left(\Delta C_{SOC,t-0} \times \frac{44}{12}\right) - PE_{t-0} - LK_{t-0}\right] \times (1 - BUF)`

| Symbol | Definition (as printed) | Unit |
|---|---|---|
| ER_t-0 | emissions reductions to be issued for the calculation period | tCO2e |
| ΔC_SOC,t-0 | change in carbon stocks in mineral soils in the calculation period | tC |
| 44/12 | CO2 to C molecular mass ratio | tCO2e tC-1 |
| PE_t-0 | additional emissions due to project activity in the calculation period | tCO2e |
| LK_t-0 | leakage of emissions due to project activity in the calculation period | tCO2e |
| BUF | compliance buffer fraction (fn 5: per the GHG ER&S Product Requirements) | dimensionless |

Text note: BUF = 0% for SOC emission-reduction activities. A buffer applies only to sequestration.

### Eq. 2. SOC stock change with uncertainty deduction (Section 5, p.11-12)
Plain text: `ΔC_(SOC,t-0) = (SOC_t − SOC_0) × (1 − UD)`

LaTeX: `\Delta C_{SOC,t-0} = (SOC_t - SOC_0) \times (1 - UD)`

| Symbol | Definition | Unit |
|---|---|---|
| ΔC_SOC,t-0 | change in soil organic carbon stocks in the calculation period | tC |
| SOC_0 | soil organic carbon stock at the beginning of the calculation period | tC |
| SOC_t | soil organic carbon stock at the end of the calculation period | tC |
| UD | uncertainty deduction | dimensionless |

Note (p.12): for the first calculation period SOC_0 = SOC_BL (Section 6.1). For later periods, SOC_0 is the previous period's SOC_t.

### Eq. 3. Baseline SOC stock (Section 6.1, p.14)
Plain text: `SOC_BL = Σ_(y=1..n) ( SOC_(BL,y) × A_y )`

LaTeX: `SOC_{BL} = \sum_{y=1}^{n}\left(SOC_{BL,y} \times A_y\right)`

| Symbol | Definition | Unit |
|---|---|---|
| SOC_BL | soil organic carbon in the eligible project area before project start | tC |
| SOC_BL,y | soil organic carbon in stratum y before project start | tC ha-1 |
| A_y | area of stratum y before project start | ha |
| n, y | number of strata / stratum index (not defined in the table; implied) | - |

### Eq. 4. Approach 3 baseline SOC per stratum (Section 6.1, p.15)
Plain text: `SOC_(BL,y) = SOC_(REF,y) × ( 1 + ( F_(LU,y) × F_(MG,BL,y) × F_(I,BL,y) − 1 ) × T_BL / D_BL )`

LaTeX: `SOC_{BL,y} = SOC_{REF,y} \times \left(1 + \left(F_{LU,y} \times F_{MG,BL,y} \times F_{I,BL,y} - 1\right) \times \frac{T_{BL}}{D_{BL}}\right)`

| Symbol | Definition | Unit |
|---|---|---|
| SOC_BL,y | soil organic carbon before project start in stratum y | tCha-1 |
| SOC_REF,y | reference soil organic carbon stock under natural vegetation in stratum y | tC ha-1 |
| F_LU,y | land use factor in stratum y | dimensionless |
| F_MG,BL,y | tillage factor before project start in stratum y | dimensionless |
| F_I,BL,y | input factor before project start in stratum y | dimensionless |
| D_BL | time dependency of F_MG,BL and F_I,BL factors (fn 7: for IPCC 2019 and IPCC 2006 default factors, D equals 20 years) | yr |
| T_BL | number of years since introduction of baseline practice; maximum T_BL = D | yr |

### Eq. 5. Project SOC stock at time t (Section 7.1, p.20)
Plain text: `SOC_t = Σ_(y=1..n) ( SOC_(t,y) × A_y )`

LaTeX: `SOC_t = \sum_{y=1}^{n}\left(SOC_{t,y} \times A_y\right)`

| Symbol | Definition | Unit |
|---|---|---|
| SOC_t | soil organic carbon in the eligible project area at time t | tC |
| SOC_t,y | soil organic carbon in stratum y at time t | tC ha-1 |
| A_y | area of stratum y at time t | ha |

### Eq. 6. Approach 3 project SOC per stratum (Section 7.1, p.22-23). Two lines under one number.
Plain text:
```
SOC_(t,y)  = SOC_(BL,y) + ΔSOC_(t,y)
ΔSOC_(t,y) = SOC_(REF,y) × F_(LU,y) × ( F_(MG,PR,y) × F_(I,PR,y) − F_(MG,BL,y) × F_(I,BL,y) ) × T_PR / D_PR
```
LaTeX:
```
SOC_{t,y} = SOC_{BL,y} + \Delta SOC_{t,y}
\Delta SOC_{t,y} = SOC_{REF,y} \times F_{LU,y} \times \left(F_{MG,PR,y} \times F_{I,PR,y} - F_{MG,BL,y} \times F_{I,BL,y}\right) \times \frac{T_{PR}}{D_{PR}}
```

| Symbol | Definition | Unit |
|---|---|---|
| SOC_t,y | soil organic carbon in stratum y at time t | tC ha-1 |
| SOC_BL,y | soil organic carbon in stratum y before project start (see equation 9) [sic; should be Eq. 4] | tC ha-1 |
| ΔSOC_t,y | change in soil organic carbon since project start in stratum y at time t | tC ha-1 |
| SOC_REF,y | reference soil organic carbon stock under natural vegetation in stratum y | tC ha-1 |
| F_LU,y | land use factor in stratum y | dimensionless |
| F_MG,BL,y | tillage factor before project start in stratum y | dimensionless |
| F_I,BL,y | input factor before project start in stratum y | dimensionless |
| F_MG,PR,y | tillage factor under the project scenario in stratum y | dimensionless |
| F_I,PR,y | input factor under the project scenario in stratum y | dimensionless |
| D_PR | time dependency of F_MG,PR and F_I,PR factors (fn 14: for IPCC 2019 and IPCC 2006 default factors, D equals 20 years) | yr |
| T_PR | number of years since project start at time t; maximum T_PR = D | yr |

### Eq. 7. Standard error of parameter mean (Section 9, Step 1, p.26)
Plain text: `SE_p = σ_p / √(n_p)`

LaTeX: `SE_p = \frac{\sigma_p}{\sqrt{n_p}}`

| Symbol | Definition | Unit |
|---|---|---|
| SE_p | Standard error in the mean of parameter p | (unit of p) |
| σ_p | Standard deviation of the parameter p | (unit of p) |
| n_p | Number of samples used to calculate the mean and standard deviation of parameter p | - |

If SE_p is available directly from the source (literature, metadata), it may be used without Eq. 7.

### Eq. 8. Confidence limits per parameter (Section 9, Step 1, p.26-27)
Plain text:
```
Lower_p = X̄_p − t_np × SE_p
Upper_p = X̄_p + t_np × SE_p
```
LaTeX: `\text{Lower}_p = \bar{X}_p - t_{np} \times SE_p \quad;\quad \text{Upper}_p = \bar{X}_p + t_{np} \times SE_p`

| Symbol | Definition | Unit |
|---|---|---|
| Lower_p | Value at the lower end of the 90% confidence interval for parameter p | (unit of p) |
| Upper_p | Value at the upper end of the 90% confidence interval for parameter p | (unit of p) |
| X̄_p | Mean value for parameter p | (unit of p) |
| SE_p | Standard error in the mean of parameter p | (unit of p) |
| t_np | t-value for the cumulative normal distribution at 90% confidence interval for the number of samples n_p for parameter p (apply Table 6). If no information is available on n_p, a conservative value of 1.675 (n=3) shall be used. | - |

The method assumes the parameter values are normally distributed about the mean.

### Eq. 9. Model run at lower and upper parameter bounds (Section 9, Step 2, p.27-28)
Plain text:
```
Lower_ΔCSOC = Model_SOC{Lower_p}
Upper_ΔCSOC = Model_SOC{Upper_p}
```
LaTeX: `\text{Lower}_{\Delta CSOC} = \text{Model}_{SOC}\{\text{Lower}_p\} \quad;\quad \text{Upper}_{\Delta CSOC} = \text{Model}_{SOC}\{\text{Upper}_p\}`

| Symbol | Definition | Unit |
|---|---|---|
| Lower_ΔCSOC | lower value of SOC change at a 90% confidence interval | (tC per Eq. 10) |
| Upper_ΔCSOC | upper value of SOC change at a 90% confidence interval | (tC per Eq. 10) |
| Model_SOC | calculation models for SOC_t, SOC_0, SOC_BL | - |
| Lower_p | values at the lower end of the 90% confidence interval for all parameters p | - |
| Upper_p | values at the upper end of the 90% confidence interval for all parameters p | - |

### Eq. 10. Model output uncertainty (Section 9, Step 3, p.28)
Plain text: `UNC = | Upper_ΔCSOC − Lower_ΔCSOC | / ( 2 × ΔC_SOC )`

LaTeX: `UNC = \frac{\left|\text{Upper}_{\Delta CSOC} - \text{Lower}_{\Delta CSOC}\right|}{2 \times \Delta C_{SOC}}`

| Symbol | Definition | Unit |
|---|---|---|
| UNC | model output uncertainty | % |
| Lower_ΔCSOC | lower value of SOC change at a 90% confidence interval | tC |
| Upper_ΔCSOC | upper value of SOC change at a 90% confidence interval | tC |
| ΔC_SOC | change in soil organic carbon stocks | tC |

### Eq. 11. Uncertainty deduction (Section 9, Step 4, p.28)
Plain text: `UD = UNC − 20%`

LaTeX: `UD = UNC - 20\%`

| Symbol | Definition | Unit |
|---|---|---|
| UD | uncertainty deduction | % |
| UNC | model output uncertainty (>20%) | % |

Rule: if UNC ≤ 20% of the mean SOC change, then UD = 0 in Eq. 2. If UNC > 20%, apply Eq. 11.

### Eq. 12. Project emissions (Section 10, p.28-29)
Plain text: `PE_(t-0) = ΔFE_(t-0) + ΔFU_(t-0) + ΔAE_(t-0)`

LaTeX: `PE_{t-0} = \Delta FE_{t-0} + \Delta FU_{t-0} + \Delta AE_{t-0}`

| Symbol | Definition | Unit |
|---|---|---|
| PE_t-0 | emissions from project activities in the calculation period | tCO2e |
| ΔFE_t-0 | emissions from increased fertilizer use in the calculation period | tCO2e |
| ΔFU_t-0 | emissions from increased fuel and electricity use in the calculation period | tCO2e |
| ΔAE_t-0 | other agrochemical emissions in the calculation period | tCO2e |

### Eq. 13. Increased N fertilizer emissions (Section 10.1, p.29)
Plain text: `ΔFE_(t-0) = EF_FE × Σ_(a=1..T) ( FE_(PR,a) − FE_BL )`

LaTeX: `\Delta FE_{t-0} = EF_{FE} \times \sum_{a=1}^{T}\left(FE_{PR,a} - FE_{BL}\right)`

| Symbol | Definition | Unit |
|---|---|---|
| ΔFE_t-0 | emissions from increased fertilizer use in the calculation period. Must be ≥ 0 in this methodology (i.e. no accounting of reductions). | tCO2e |
| FE_PR,a | N fertilizer input under the project scenario in year a of the calculation period | kgN |
| FE_BL | mean annual N fertilizer input under the baseline scenario | kgN |
| T | number of years in the calculation period | yr |
| EF_FE | Conversion factor for emissions from N fertilizer. IPCC 2019 aggregated default value (fn 17: IPCC 2019 Vol 4 Table 11.1) for EF_FE is 0.01. Disaggregated defaults in IPCC 2019 Table 11.1 may be used if inputs are known per fertilizer type. | tCO2e kgN-1 |

Rules:
- No distinction is made between synthetic and organic N.
- If N input decreases, ΔFE is 0. Reductions require a separate GS methodology.
- FE_BL is the 5-year pre-project mean from management records. If documentation is inadequate, **FE_BL ≤ 50% of FE_PR**.

### Eq. 14. Increased fossil fuel and electricity emissions (Section 10.2, p.29-30)
Plain text, as printed: `ΔFU_(t-0) = Σ_(a=1..T) ( FU_(PR,a) − FU_BL ) + ( EU_(PR,a) − EU_BL )`

LaTeX, as printed: `\Delta FU_{t-0} = \sum_{a=1}^{T}\left(FU_{PR,a} - FU_{BL}\right) + \left(EU_{PR,a} - EU_{BL}\right)`

(See Section 8: the summation scope is ambiguous.)

| Symbol | Definition | Unit |
|---|---|---|
| ΔFU_t-0 | emissions from increased fossil fuel and electricity use in the calculation period | tCO2e |
| FU_PR,a | emissions from use of fossil fuels under the project scenario in year a of the calculation period | tCO2e |
| FU_BL | mean annual emissions from use of fossil fuels under the baseline scenario | tCO2e |
| EU_PR,a | emissions from use of electricity under the project scenario in year a of the calculation period | tCO2e |
| EU_BL | mean annual emissions from use of electricity under the baseline scenario | tCO2e |
| T | number of years in the calculation period | yr |

Rules:
- ΔFU = 0 if the owner shows project use is less than, or does not differ significantly from, the baseline.
- FU_BL is the 5-year pre-project mean. Otherwise it is estimated from fuel efficiency (e.g. l/100 km, l/t-km, l/hour) × unit of use. If documentation is inadequate, **FU_BL ≤ 50% of FU_PR**.
- Non-CO2 GHGs from fossil fuel use are insignificant and may be neglected.

### Eq. 15. Fossil fuel emissions (Section 10.2, p.30)
Plain text: `FU_(i,a) = Σ_MT FUL_(i,MT,a) × FEF_(i,MT)`

LaTeX: `FU_{i,a} = \sum_{MT} FUL_{i,MT,a} \times FEF_{i,MT}`

| Symbol | Definition | Unit |
|---|---|---|
| FU_i,a | emissions from use of fossil fuels in year a | tCO2e ha-1 |
| FUL_i,MT,a | fuel consumption by the machinery type MT used in year a | litres |
| FEF_i,MT | emissions factor for the fuel used in machinery MT | tCO2e litres-1 |
| MT | machinery type (gasoline two-stroke, gasoline four-stroke, diesel) | - |
| i | formula used for baseline (i=BL) as well as project scenario (i=PR) | - |

### Eq. 16. Electricity emissions (Section 10.2, p.30-31)
Plain text: `EU_(i,a) = Σ_SE EUW_(i,SE,a) × EEF_(i,SE)`

LaTeX: `EU_{i,a} = \sum_{SE} EUW_{i,SE,a} \times EEF_{i,SE}`

| Symbol | Definition (as printed) | Unit |
|---|---|---|
| EU_i,a | emissions from use of fossil fuels in year a [sic; context = electricity] | tCO2e ha-1 |
| EUW_i,SE,a | electricity consumption from source SE in year a | kWh |
| EEF_i,SE | emissions factor for the electricity used in source SE | tCO2e kWh-1 |
| SE | electricity source type (grid, fossil fuel generator, etc) | - |
| i | formula used for baseline (i=BL) as well as project scenario (i=PR) | - |

Rules:
- If electricity is generated on-site from fossil fuel (e.g. diesel generators for irrigation pumps), calculate fuel combustion with Eq. 15 instead.
- If documentation is inadequate, **EU_BL ≤ 50% of EU_PR**.

### Eq. 17. Other agrochemical emissions (Section 10.3, p.31)
Plain text: `ΔAE_(t-0) = Σ_(a=1..T) ( AE_(PR,a) − AE_BL )`

LaTeX: `\Delta AE_{t-0} = \sum_{a=1}^{T}\left(AE_{PR,a} - AE_{BL}\right)`

| Symbol | Definition | Unit |
|---|---|---|
| ΔAE_t-0 | additional emissions from project activity in the calculation period | tCO2e |
| AE_PR,a | other emissions under the project scenario in year a of the calculation period | tCO2e |
| AE_BL | other emissions (annual mean) under the baseline scenario | tCO2e |
| T | number of years in the calculation period | yr |

Rules:
- ΔAE = 0 if the owner shows agrochemical use is less than, or does not differ significantly from, the baseline.
- Emission factors come from manufacturer information or scientific sources.

### Eq. 18. Agrochemical emissions by emitter type (Section 10.3, p.31-32)
Plain text: `AE_(i,a) = Σ_ET AQ_(i,ET,a) × AEF_(i,ET)`

LaTeX: `AE_{i,a} = \sum_{ET} AQ_{i,ET,a} \times AEF_{i,ET}`

| Symbol | Definition | Unit |
|---|---|---|
| AE_i,a | emissions from use of other agrochemicals in year a | tCO2e ha-1 |
| AQ_i,ET,a | quantity of agrochemicals for emitter type ET applied in year a | kg |
| AEF_i,ET | emissions factor of the agrochemical used (for emitter type ET) | tCO2e kg-1 |
| ET | emitter type (specific pesticide, fertilizer, or other agrochemical) | - |
| i | formula used for baseline (i=BL) as well as project scenario (i=PR) | - |

AE_BL is the 5-year pre-project mean. If documentation is inadequate, **AE_BL ≤ 50% of AE_PR**.

### Eq. 19. Yield-shift leakage (Section 11, p.33)
Plain text: `LK_(t-0) = ( CY_min − CY_t ) / CY_BL × A × ( ΔBC_LA + ΔSOC_(LA,t-0) + ΔFE_(LA,t-0) + ΔFU_(LA,t-0) )`

LaTeX: `LK_{t-0} = \frac{CY_{min} - CY_t}{CY_{BL}} \times A \times \left(\Delta BC_{LA} + \Delta SOC_{LA,t-0} + \Delta FE_{LA,t-0} + \Delta FU_{LA,t-0}\right)`

| Symbol | Definition | Unit |
|---|---|---|
| LK_t-0 | emissions due to shift of production to non-project lands (leakage area) | tCO2e |
| CY_t | crop yield in the project area at time t (5-year average) | kg ha-1 |
| CY_min | lowest crop yield in the project area in any calculation period since project start (5-year average) | kg ha-1 |
| CY_BL | crop yield in the project area under the baseline scenario (5-year average) | kg ha-1 |
| A | total eligible project area | ha |
| ΔBC_LA | change in biomass carbon stocks in leakage area | tCO2e ha-1 |
| ΔSOC_LA,t-0 | change in soil organic carbon stocks in leakage area | tCO2e ha-1 |
| ΔFE_LA,t-0 | change in emissions from use of fertilizer in leakage area | tCO2e ha-1 |
| ΔFU_LA,t-0 | change in emissions from fuel use in leakage area | tCO2e ha-1 |

Rules:
- Apply only if CY_t < CY_min. Positive leakage is not allowed.
- For the first calculation period, CY_min = CY_BL. Each yield value is the previous five years' average.
- Leakage-area deltas are the difference between stocks on the land the activity would most likely shift to (pre-shift vegetation and land use) and the long-term biomass carbon stock under the baseline cropping system.
- ΔBC_LA uses IPCC 2019 biomass stocks or local literature. Fn 18 cites IPCC 2019 Vol 4: Table 4.7 (forests), Table 4.8 (plantations), Ch. 5.2.1 (cropland), Ch. 6.2.1 (grassland).

### Calculation chain (for implementation)
1. Per stratum y, compute SOC_BL,y (Approach 1 measured, Approach 2 literature/model, or Approach 3 Eq. 4). Eq. 3 gives SOC_BL.
2. Per stratum y at time t, compute SOC_t,y (Approach 1/2, or Approach 3 Eq. 6). Eq. 5 gives SOC_t.
3. Run the uncertainty steps: Eq. 7 → 8 → 9 → 10 → 11, giving UD.
4. Eq. 2 gives ΔC_SOC,t-0. SOC_0 = SOC_BL in the first period, else the previous SOC_t.
5. Compute PE with Eq. 12, from Eq. 13 + (14 with 15/16) + (17 with 18).
6. Compute LK: 0 initially; Eq. 19 if yield falls below CY_min.
7. Eq. 1, applying BUF from the GHG ER&S Product Requirements, gives ER_t-0.

---

## 3. SOC measurement requirements

- **Protocols (Approach 1):** measurement shall follow accepted protocols (p.14, p.21; Annex 1 Table [6] p.44):
  - **ICRAF protocol**: Aynekulu, Vagen, Shephard, Winowiecki 2011, "A protocol for modeling, measurement and monitoring soil carbon stocks in agricultural landscapes", v1.1, World Agroforestry Centre, Nairobi.
  - **VCS Module VMD0021** "Estimation of Stocks in the Soil Carbon Pool" v1.0.
  - Alternate protocols may be proposed in modules or at project level. Deviations are subject to GS review and decision. Other protocols may be submitted for addition to the list.
- **Number of samples:** "an adequate number of soil profiles to meet GS uncertainty requirements in each stratum" (p.14, p.21). The target precision is **20% of the mean at 90% confidence** for the total SOC change calculation (p.26), per Annex A "Uncertainty of LUF Parameters" in the LUF Activity Requirements. The framework gives no sample-size formula.
- **Sampling depth:** **not specified** in the framework; it is deferred to the protocols and modules. Literature values may only be applied within the SOC depth analysed in the source (p.14).
- **Equivalent soil mass vs fixed depth:** **not addressed** in the framework. Fn on p.36 mentions "density corrections" only for rocky soils when adapting literature data.
- **Lab methods:** **not specified**; deferred to ICRAF/VMD0021. Measuring equipment must be certified to national or international standards and calibrated and recalibrated per manufacturer specifications (p.35).
- **Re-measurement frequency:** SOC_t,y is determined "at each performance certification" (monitoring table, p.41). Monitoring reports are due at each verification/performance review, plus an annual report (p.35).
- **Control / baseline plots:** no paired control plots are required.
  - The baseline is measured at project start (SOC_BL,y, "Project start", p.38) or estimated with Approach 2/3.
  - Approach 2 values may be checked against measurements at sample sites in each stratum. These are mandatory if the VVB deems the applicability evidence insufficient (p.15, p.22).
- **Applicability field assessment for Approach 2/3 (Section 16.2, p.35-36):**
  - Per stratum, dig a representative number of temporary soil pits, **50 × 50 cm, to 50 cm depth**.
  - Assess four criteria:
    1. soil type and depth;
    2. inorganic content (rock, sand, clay);
    3. pre-project organic matter (e.g. large root residues);
    4. evidence of management history (structure, compaction, disturbance depth).
  - In heterogeneous areas, enough pits are needed to represent variation and confirm the stratification.
  - **Pits remain open until after the initial certification audit.** The VVB revisits a series of pits. SOC measurement of a sub-sample is recommended if applicability is in doubt.
  - This is also required for retrospective crediting.
- **Approach change at project start:** a 5% comparison threshold applies (Section 8).

---

## 4. Emissions (non-SOC GHG sources)

| Source | Equation | Default factor / tier | Gas |
|---|---|---|---|
| Increased N fertilizer (synthetic + organic, no differentiation) | Eq. 13 | EF_FE = **0.01** "tCO2e kgN-1". IPCC 2019 aggregated default, Vol 4 Table 11.1. Disaggregated Table 11.1 values allowed by fertilizer type. | N2O implied, not stated |
| Increased fossil fuel (machinery) | Eq. 14 + 15 | FEF_i,MT per machinery/fuel type. No default given. | CO2 only; non-CO2 from fuel neglected (p.30) |
| Increased electricity | Eq. 14 + 16 | EEF_i,SE per source. No default given. | CO2 |
| Other agrochemicals (pesticides, herbicides, non-N fertilizers) | Eq. 17 + 18 | AEF_i,ET from manufacturer or scientific sources. No default. | unspecified |
| Leakage-area fertilizer / fuel | Eq. 19 terms | "calculated according to the approaches described in this methodology" | - |

- **Significance:** emissions >5% of total must be accounted for. Those <5% may be omitted (p.11, p.28).
- **Baseline for each source:** the 5-year pre-project mean from records. If undocumented, the baseline is capped at 50% of the project value.
- Decreases are not credited; ΔFE is floored at 0 explicitly. ΔFU and ΔAE are 0 when project use is not higher.
- **GWPs: none stated anywhere in the document.** The source of GWPs is not referenced (presumably GS Principles & Requirements / the GHG ER&S Product Requirements).
- **IPCC tiers:** SOC Approach 3 uses IPCC 2019 Tier 1 defaults (Tables 3/4). Tier 2/3 national or regional factors are preferred where available. The fertilizer EF is the IPCC 2019 aggregated (Tier 1) default.
- Biomass burning is prohibited for site preparation, so no burning emission source is included.

---

## 5. Uncertainty and conservativeness

- **Criterion (p.26):** precision of **20% of the mean at the 90% confidence level** for the total SOC change calculation. It applies to all three approaches.
- **Procedure:** adapted from VCS VM0017 and the GS Improved Tillage methodology (fn 16).
  - **Step 1:** for every parameter and coefficient, compute the mean and SD. Eq. 7 gives SE_p (or use SE_p from the source). Eq. 8 gives Lower_p/Upper_p, using t_np from Table 6. If n_p is unknown, use t = **1.675 (n=3)**.
  - **Step 2:** Eq. 9 runs the SOC models (SOC_t, SOC_0, SOC_BL) with all Lower_p values and with all Upper_p values.
  - **Step 3:** Eq. 10 gives UNC = |Upper − Lower| / (2 × ΔC_SOC).
  - **Step 4:** if UNC ≤ 20%, UD = 0. Otherwise UD = UNC − 20% (Eq. 11), applied in Eq. 2 as the factor (1 − UD).
- **Table 6 t-values (p.27).** n_p = number of samples. Two-sided 90%, df = n_p − 1.

| n_p | t | n_p | t | n_p | t | n_p | t |
|---|---|---|---|---|---|---|---|
| 3 | 2.9200 | 4 | 2.3534 | 5 | 2.1319 | 6 | 2.0150 |
| 7 | 1.9432 | 8 | 1.8946 | 9 | 1.8595 | 10 | 1.8331 |
| 11 | 1.8124 | 12 | 1.7959 | 13 | 1.7823 | 14 | 1.7709 |
| 15 | 1.7613 | 16 | 1.7530 | 17 | 1.7459 | 18 | 1.7396 |
| 19 | 1.7341 | 20 | 1.7291 | 21 | 1.7247 | 22 | 1.7207 |
| 23 | 1.7172 | 24 | 1.7139 | 25 | 1.7109 | 26 | 1.7081 |
| 27 | 1.7056 | 28 | 1.7033 | 29 | 1.7011 | 30 | 1.6991 |
| 31 | 1.6973 | 32 | 1.6955 | 33 | 1.6939 | 34 | 1.6924 |
| 35 | 1.6909 | 36 | 1.6896 | 37 | 1.6883 | 38 | 1.6871 |
| 39 | 1.6859 | 40 | 1.6849 | 41 | 1.6839 | 42 | 1.6829 |
| 43 | 1.6820 | 44 | 1.6811 | 45 | 1.6802 | 46 | 1.6794 |
| 47 | 1.6787 | 48 | 1.6779 | 49 | 1.6772 | 50 | 1.6766 |
| 51 | 1.6759 | 52 | 1.6753 | 53 | 1.6747 | 54 | 1.6741 |
| 55 | 1.6736 | 56 | 1.6730 | 57 | 1.6725 | 58 | 1.6720 |
| 59 | 1.6715 | 60 | 1.6711 | 61 | 1.6706 | 62 | 1.6702 |
| 63 | 1.6698 | 64 | 1.6694 | 65 | 1.6690 | 66 | 1.6686 |
| 67 | 1.6683 | 68 | 1.6679 | 69 | 1.6676 | 70 | 1.6673 |
| 71 | 1.6669 | 72 | 1.6666 | 73 | 1.6663 | 74 | 1.6660 |
| 75 | 1.6657 | 76 | 1.6654 | 77 | 1.6652 | 78 | 1.6649 |
| 79 | 1.6646 | 80 | 1.6644 | 81 | 1.6641 | 82 | 1.6639 |
| 83 | 1.6636 | 84 | 1.6634 | 85 | 1.6632 | 86 | 1.6630 |
| 87 | 1.6628 | 88 | 1.6626 | 89 | 1.6623 | 90 | 1.6622 |
| 91 | 1.6620 | 92 | 1.6618 | 93 | 1.6616 | 94 | 1.6614 |
| 95 | 1.6612 | 96 | 1.6610 | 97 | 1.6609 | 98 | 1.6607 |
| 99 | 1.6606 | 100 | 1.6604 | 101 | 1.6602 | 102 | 1.6601 |
| 103 | 1.6599 | 104 | 1.6598 | 105 | 1.6596 | 106 | 1.6595 |
| 107 | 1.6593 | 108 | 1.6592 | 109 | 1.6591 | 110 | 1.6589 |
| 111 | 1.6588 | 112 | 1.6587 | 113 | 1.6586 | 114 | 1.6585 |
| 115 | 1.6583 | 116 | 1.6582 | 117 | 1.6581 | 118 | 1.6580 |
| 119 | 1.6579 | 120 | 1.6578 | 121 | 1.6577 | 122 | 1.6575 |
| 123 | 1.6574 | 124 | 1.6573 | 125 | 1.6572 | 126 | 1.6571 |
| 127 | 1.6570 | 128 | 1.6570 | 129 | 1.6568 | 130 | 1.6568 |
| 131 | 1.6567 | 132 | 1.6566 | 133 | 1.6565 | 134 | 1.6564 |
| 135 | 1.6563 | 136 | 1.6562 | 137 | 1.6561 | 138 | 1.6561 |
| 139 | 1.6560 | 140 | 1.6559 | 141 | 1.6558 | 142 | 1.6557 |
| 143 | 1.6557 | 144 | 1.6556 | 145 | 1.6555 | 146 | 1.6554 |
| 147 | 1.6554 | 148 | 1.6553 | 149 | 1.6552 | 150 | 1.6551 |
| 151 | 1.6551 | 152 | 1.6550 | 153 | 1.6549 | 154 | 1.6549 |
| 155 | 1.6548 | 156 | 1.6547 | 157 | 1.6547 | 158 | 1.6546 |
| 159 | 1.6546 | 160 | 1.6545 | 161 | 1.6544 | 162 | 1.6544 |
| 163 | 1.6543 | 164 | 1.6543 | 165 | 1.6542 | 166 | 1.6542 |
| 167 | 1.6541 | 168 | 1.6540 | 169 | 1.6540 | 170 | 1.6539 |
| 171 | 1.6539 | 172 | 1.6538 | 173 | 1.6537 | 174 | 1.6537 |
| 175 | 1.6537 | 176 | 1.6536 | 177 | 1.6536 | 178 | 1.6535 |
| 179 | 1.6535 | 180 | 1.6534 | 181 | 1.6534 | 182 | 1.6533 |
| 183 | 1.6533 | 184 | 1.6532 | 185 | 1.6532 | 186 | 1.6531 |
| 187 | 1.6531 | 188 | 1.6531 | 189 | 1.6530 | 190 | 1.6529 |
| 191 | 1.6529 | 192 | 1.6529 | 193 | 1.6528 | 194 | 1.6528 |
| 195 | 1.6528 | 196 | 1.6527 | 197 | 1.6527 | 198 | 1.6526 |
| 199 | 1.6526 | ≥200 | 1.6525 | | | | |

(Rows for n_p = 1 and 2 are blank in the printed table.)

- **Other conservativeness rules:**
  - Use the most conservative value when the literature gives a range or aggregated data (p.14, p.22).
  - Approach change: a higher measured Approach 1 baseline is retained over a lower Approach 2 result (p.23).
  - Undocumented baselines for fertilizer, fuel, electricity and agrochemicals are capped at 50% of the project value.
  - Areas leaving the project are full reversals (p.9).
  - Reductions in emissions are not credited.
  - IPCC default SOCREF may only be used if within GS uncertainty requirements (fn 8).
  - Figure 2 labels: Approach 1 "No deductions", Approach 2 "Deductions possible", Approach 3 "Deductions likely".
  - Table 5 fn 15: a high-uncertainty parameter likely triggers an uncertainty deduction but does not affect the approach-change assessment.
- **No discount table** (e.g. a stepwise % deduction) is provided beyond Eq. 11.

---

## 6. Leakage, non-permanence, crediting

- **Leakage (Section 11, p.32-33):**
  - C runoff leakage is 0, because wetlands are excluded.
  - Yield-related leakage: **LK_t-0 = 0 for initial calculations**, since applicability forbids yield reduction.
  - If a yield reduction is detected at a performance certification, Eq. 19 applies, unless the owner shows the cause is unrelated to the project (e.g. regional yield reduction due to weather). It applies only if CY_t < CY_min; positive leakage is not allowed.
  - Modules "shall provide leakage calculations if applicable".
- **Non-permanence / buffer (Section 5 p.11, Section 13 p.34-35):**
  - A **fixed percentage** of validated and verified GS VERs attributable to SOC **sequestration** goes to the **Gold Standard Compliance Buffer**, per the GHG Emissions Reductions & Sequestration Product Requirements.
  - **The buffer percentage is not stated in this document.**
  - No buffer applies to SOC emission-reduction activities (BUF = 0%).
  - The buffer is **non-refundable**. The owner may transfer GS VERs from other GS-certified projects into the buffer in lieu of project VERs.
  - Modules may add specific buffer or non-permanence requirements (Table 1).
  - Reversal liability: areas leaving the project count as full reversal. The owner must maintain or compensate carbon loss up to the credits issued (p.9-10).
- **Credits:**
  - Eq. 1 gives ER_t-0 in tCO2e = "emissions reductions to be issued for the calculation period". Throughout the text these are called "GS VERs".
  - The buffer is deducted inside Eq. 1 via (1 − BUF).
  - Uncertainty is deducted inside Eq. 2 via (1 − UD), and applies only to the SOC term, not to PE or LK.
- **Rounding / vintage:** **not specified** in this document.
  - "Calculation period" = time between two points (e.g. between performance certifications).
  - "Monitoring period" has an analogous definition (p.7).
  - Retroactive issuance follows the LUF Activity Requirements.
- **Additionality (Section 14):** per the LUF Activity Requirements and the "AGR Additionality (AGR projects) Template".
- **SDGs:** SDG 13 primary; others are set at project level per Principles & Requirements.
- **Double counting:** GHG ER&S Product Requirements Annex A "Double Counting Requirements" (p.34).

---

## 7. Default values, constants and thresholds

| Item | Value | Page |
|---|---|---|
| CO2:C molecular mass ratio | 44/12 tCO2e tC-1 | 11 |
| BUF for SOC emission reductions | 0% | 11, 34 |
| BUF for sequestration | "fixed percentage" per GHG ER&S Product Requirements (value not given) | 11, 34 |
| Crediting period | 5-20 years (module defines) | 10 |
| Min. years of managed cropping system pre-project | 5 years | 9 |
| Baseline historical reference period | last 5 years before project start | 13 |
| Baseline yield reference | 5-year average prior to project start | 9 |
| Yield decrease tolerance vs project region | not significantly (5%) more than regional decrease | 9 |
| Shallow soil water regime limit | <1 m | 8 |
| GHG de minimis | <5% of total ER and sequestration may be omitted; >5% must be accounted for | 11, 28 |
| IPCC time dependency D (D_BL, D_PR) | 20 years (IPCC 2019 / 2006 defaults); max T = D | 15, 22-23 |
| Uncertainty target | 20% of mean at 90% confidence | 26 |
| UD threshold | UNC ≤ 20% → UD = 0; else UD = UNC − 20% | 28 |
| Default t-value if n_p unknown | 1.675 (n=3) | 27 |
| t-value table | Table 6 (n=3 to ≥200; ≥200 → 1.6525) | 27 |
| Approach change neutrality threshold | 5% | 23-24 |
| EF_FE (N fertilizer) | 0.01 tCO2e kgN-1 (IPCC 2019 Vol 4 Table 11.1 aggregated) | 29, 38 |
| Baseline record period for FE_BL, FU_BL, EU_BL, AE_BL | 5 years prior to project start | 29-32 |
| Undocumented baseline cap (FE, FU, EU, AE) | ≤ 50% of project-scenario value | 29-32 |
| Non-CO2 from fossil fuel | insignificant, may be neglected | 30 |
| Leakage initial value | LK = 0 | 32 |
| First-period CY_min | = CY_BL | 33 |
| Applicability soil pits | 50 cm × 50 cm area, 50 cm depth; open until initial certification audit | 36 |
| Data archiving | up to 2 years after end of crediting period | 35 |
| **Table 3 grassland (IPCC 2019 Table 6.2 updated), p.16-17** | | |
| FLU: All / All | 1.0 (N/A) | 16 |
| FMG: Nominally managed (non-degraded) / All | 1.0 (N/A) | 16 |
| FMG: High intensity grazing / All | 0.90 (±8%) | 16 |
| FMG: Severely degraded / All | 0.7 (±40%) | 16 |
| FMG: Improved grassland, Temperate/Boreal | 1.14 (±11%) | 17 |
| FMG: Improved grassland, Tropical | 1.17 (±9%) | 17 |
| FMG: Improved grassland, Tropical Montane | 1.16 (±40%) | 17 |
| FI (improved grassland only): Medium / All | 1.0 (NA) | 17 |
| FI (improved grassland only): High / All | 1.11 (±7%) | 17 |
| **Table 4 cropland (IPCC 2019 Table 5.5 updated), p.18-19** | | |
| FLU Long-term cultivated: Cool Temperate/Boreal Dry / Moist | 0.77 (±14%) / 0.70 (±12%) | 18 |
| FLU Long-term cultivated: Warm Temperate Dry / Moist | 0.76 (±12%) / 0.69 (±16%) | 18 |
| FLU Long-term cultivated: Tropical Dry / Moist-Wet | 0.92 (±13%) / 0.83 (±11%) | 18 |
| FLU Paddy rice: All, Dry and Moist/Wet | 1.35 (±4%); tillage and input factors not used | 18 |
| FLU Perennial/Tree crop: Temperate/Boreal Dry and Moist | 0.72 (±22%) | 18 |
| FLU Perennial/Tree crop: Tropical Dry and Moist/Wet | 1.01 (±25%) | 18 |
| FLU Set aside (<20 yrs): Temperate/Boreal and Tropical Dry / Moist-Wet | 0.93 (±11%) / 0.82 (±17%) | 18 |
| FLU Set aside: Tropical montane, n/a | 0.88 (±50%) | 18 |
| FMG Tillage Full: All | 1.00 (n/a) | 18 |
| FMG Tillage Reduced: Cool Temperate/Boreal Dry / Moist | 0.98 (±5%) / 1.04 (±4%) | 18-19 |
| FMG Tillage Reduced: Warm Temperate Dry / Moist | 0.99 (±3%) / 1.05 (±4%) | 19 |
| FMG Tillage Reduced: Tropical Dry / Moist-Wet | 0.99 (±7%) / 1.04 (±7%) | 19 |
| FMG Tillage Reduced: n/a | n/a | 19 |
| FI Low: Temperate/Boreal Dry / Moist | 0.95 (±13%) / 0.92 (±14%) | 19 |
| FI Low: Tropical Dry / Moist-Wet | 0.95 (±13%) / 0.92 (±14%) | 19 |
| FI Low: Tropical montane | 0.94 (±50%) | 19 |
| FI Medium: All | 1.00 (n/a) | 19 |
| FI High without manure: Temperate/Boreal and Tropical Dry / Moist-Wet | 1.04 (±13%) / 1.11 (±10%) | 19 |
| FI High without manure: Tropical montane | 1.08 (±50%) | 19 |
| FI High with manure: Temperate/Boreal and Tropical Dry / Moist-Wet | 1.37 (±12%) / 1.44 (±13%) | 19 |
| FI High with manure: Tropical montane | 1.41 (±50%) | 19 |
| Table error convention | ± two standard deviations as % of mean. Defaults where studies were insufficient: grassland +40%, cropland +50% (expert). | 17, 20 |

---

## 8. Ambiguities, errors and external dependencies

### 8.1 Equation and variable issues
1. **Eq. 6 cross-reference (p.22):** SOC_BL,y says "(see equation 9)". It should be Eq. 4; Eq. 9 is the uncertainty model run.
2. **UD unit inconsistency:** UD is "dimensionless" in Eq. 2 (p.12) but "%" in Eq. 11 (p.28). The platform must convert % to a fraction in (1 − UD).
3. **Eq. 10 denominator (p.28):** ΔC_SOC is not specified as central-estimate SOC_t − SOC_0 versus SOC_t − SOC_BL. Step 2 mentions both SOC_0 and SOC_BL models.
   - It is also unclear whether UNC is computed per stratum, per period, or project-wide.
   - Running all parameters simultaneously at their lower (or upper) bound does not guarantee that the resulting ΔC is the min (or max). Example: a lower SOC_BL increases ΔC. The direction convention is unstated.
4. **t-value inconsistency (p.27):** the text says to use "a conservative value of 1.675 (n=3)" when n_p is unknown, but Table 6 gives t = 2.9200 for n=3. 1.675 is not conservative relative to the table. The t-values are also described as for the "cumulative normal distribution", but they are Student-t two-sided 90% values with df = n−1. The table has no entries for n = 1 or 2.
5. **Eq. 13 EF_FE units (p.29, p.38):** EF_FE = 0.01 is labelled "tCO2e kgN-1".
   - The IPCC 2019 Table 11.1 aggregated EF1 = 0.010 is in kg N2O-N per kg N.
   - Turning it into tCO2e requires × 44/28 × GWP_N2O / 1000. The methodology states none of these conversions.
   - Applying 0.01 tCO2e/kgN literally gives a very different value.
   - The text also does not say whether indirect N2O (volatilisation and leaching) is included.
   - **Requires clarification before implementation.**
   - The data table names the parameter "EFLE" (p.38), a typo for EF_FE.
6. **Eq. 14 summation scope (p.29):** the printed parentheses put (EU_PR,a − EU_BL) outside Σ_a. It is presumably meant to be summed over years a = 1..T as well.
7. **Eq. 15/16/18 units:** outputs are labelled "tCO2e ha-1", but the inputs (litres × tCO2e/litre; kWh × tCO2e/kWh; kg × tCO2e/kg) give tCO2e. Eqs. 14 and 17 use tCO2e (not per ha). No area multiplication step is given.
8. **Eq. 16 definition copy error:** EU_i,a is defined as "emissions from use of fossil fuels". It should be electricity.
9. **Eq. 19:**
   - ΔBC_LA lacks the t-0 subscript.
   - CY_min is "lowest ... 5-year average" in the equation table (p.33), but "the lowest annual yield is considered CYmin" in the monitoring table (p.41).
   - The sign convention for the leakage-area deltas is described only verbally (p.33).
   - ΔSOC_LA is in tCO2e ha-1, whereas the project-side SOC is in tC.
10. **Eq. 1 with mixed activities:** BUF multiplies the whole net amount. For projects that combine emission reductions (BUF = 0) and sequestration, no split procedure is given. "Change in carbon stocks in mineral soils" implicitly limits the method to mineral soils.
11. **Eq. 4 / text naming:** the text refers to "F_LU,BL,y" (p.16), while the equation uses F_LU,y. The SOC_BL,y and SOC_t,y data tables say "density at equilibrium" (p.38, p.41), which contradicts the non-equilibrium T/D formulation.
12. **Eq. 3/5 index n** (number of strata) is not defined.
13. **ΔFE_t-0,y** appears in the text (p.29) with a stratum subscript, but Eq. 13 has none. Whether fertilizer is tracked per stratum is unclear.

### 8.2 Table and text issues
14. **Table 4 (p.18-19):**
   - **No "No-till" row** is reproduced, although IPCC 2019 Table 5.5 includes one. Projects needing no-till factors must take them directly from IPCC.
   - Footnotes 5, 6 and 7 (cited on "Land use5", "Land use6", "Tillage7") are not printed; Table 4 notes list only 1-4.
   - The Reduced-tillage row has an "n/a n/a n/a n/a" line, presumably tropical montane.
15. **Table 3** cites footnote "3" for the bibliography and has no printed footnote 3 in the notes list. This is minor.
16. **Table 5 example row 3 (p.25):** baseline 37 → project 39 is classed "Rule 2a: Difference is less than 5%". (39 − 37)/37 = 5.4%, which exceeds 5% (unless the denominator is 39 → 5.1%). The base for the 5% comparison is not defined.
17. **Monitoring tables (Section 16.3/16.4, p.36-43):**
   - F_I,PR,y is described as "input factor before project start" (copy error) and is monitored "Annually".
   - **F_MG,BL,y and F_MG,PR,y have no data tables.**
   - CY_min, FEF, EEF, AEF, D, T_BL and T_PR have no data tables either.
   - Several tables have their fields shifted, so values land in the wrong rows (e.g. "Unit" holds the description).
18. **Numbering duplicates:**
   - "Table 6" is used both for the t-values (p.27) and for the eligible protocols (Annex 1, p.44).
   - Protocols are said to be listed in "Appendix 1" (p.14), but the section is Annex 1.
   - VMD0021 is dated 2012 on p.21 and 2011 in Annex 1.
   - Annex 2 contains "Error! Reference source not found." (p.45).
19. **Sampling specifics are absent:** depth, equivalent soil mass vs fixed depth, lab method (dry combustion vs Walkley-Black), bulk density and coarse-fragment correction, and sample-size calculation. All are deferred to ICRAF/VMD0021 and the modules.
20. **"Calculation period" vs "monitoring period"** are defined almost identically (p.6-7).

### 8.3 External dependencies (required to implement)
- **GS4GG GHG Emissions Reductions & Sequestration Product Requirements:** buffer %, reversal compensation, Annex A double counting (p.9-11, 34).
- **GS4GG Land-use & Forests (LUF) Activity Requirements:**
  - forest definition;
  - new area certification;
  - retroactive issuance;
  - Annex A "Uncertainty of LUF Parameters";
  - additionality;
  - yield / productivity requirement (p.8-10, 26, 32, 35).
- **GS4GG Principles & Requirements:** monitoring report and annual report content, SDG contributions (p.35). Also the **Annual Report Template**.
- **Glossary of GS for Global Goals** (p.6).
- **AGR Additionality (AGR projects) Template** (p.35).
- **SOC Activity Modules:** mandatory. They supply applicable approaches, crediting period, GHGs, leakage, stratification and extra parameters.
- **IPCC 2019 Refinement Vol 4:**
  - Ch. 5 Table 5.5 (cropland factors);
  - Ch. 6 Table 6.2 (grassland factors);
  - Table 11.1 (N2O EF);
  - Tables 4.7/4.8, Ch. 5.2.1, Ch. 6.2.1 (biomass stocks for leakage);
  - Annex 5A1/6A1;
  - Chapter 3 climate zones;
  - Glossary (wetland definition).
- **ICRAF protocol** (Aynekulu et al. 2011) and **VCS VMD0021 v1.0** for SOC sampling and analysis.
- **VCS VM0017 v1.0** and the GS Improved Tillage methodology: source of the uncertainty procedure.
- **SOC reference data sources:** ISRIC/SoilGrids (Hengl et al. 2014), the European Soil Data Centre, and soil models RothC and Century (p.15, 21).
- **GWP values:** not given. They must come from the current GS rules.
