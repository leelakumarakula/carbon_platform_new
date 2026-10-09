# Gold Standard SOC Framework (402) Activity Modules: Transcription Extract

Sources (page numbers below are the printed page numbers; in all three PDFs these match the PDF page index):
- **402.1** Soil Organic Carbon Activity Module: *Increasing Soil Carbon Through Improved Tillage Practices*, Version 1.0, published January 2020 (19 pp). Developed by TREES Consulting.
- **402.4** *Soil Organic Carbon Activity Module for Zero Tillage*, Version 1.0, publication date 20.02.2024, next planned update 19.02.2027 (26 pp). Developed by TREES Consulting and Agoro Carbon Alliance US Inc.
- **402.6** *Soil Organic Carbon Activity Module for Cover Crops*, Version 1.0, publication date 02.10.2024, next planned update 1.10.2027 (31 pp). Developed by TREES Consulting on behalf of Agoro Carbon Alliance US, Inc.

How this was done: text came from `_text/*.txt`. Every equation and every parameter table that was garbled in the text copy was checked against page renders (402.4 pp. 13-20, 402.6 pp. 16-25 and 27, 402.1 pp. 9-10 and 12-13). Equations are written in plain-text/LaTeX-like notation that matches the printed symbols. "SOC FM" means the GS 402 SOC Framework Methodology v1.0. FM equation numbers are given only where a module itself cites them. This file does not transcribe the FM.

Nothing in the three modules was physically unreadable. No item is marked [UNREADABLE]. Printed typos are kept as printed and flagged in each module's ambiguities section.

---

## Module 402.1: Improved Tillage (v1.0, Jan 2020)

### 1.1 Applicability, eligible practices, baseline

**Applicability (Section 3, pp. 5-6), exact text:**
> A project applying this Activity Module shall comply with the applicability conditions specified below and within the SOC Framework Methodology. In addition, the project shall comply with applicable Land Use & Forests Activity Requirements (hereafter LUF Activity Requirements) and the Gold Standard for the Global Goals Principles & Requirements.
>
> a. Soil type:
> - Proposed projects on sites with organic soils (Histosols), as defined by the World Reference Base for Soil Resources (FAO 2015), are ineligible. Only mineral soil types are eligible.
>
> b. Cropping system:
> - Managed cropping systems (e.g. single crop or crop rotation) must have been in place for at least 5 years prior to project implementation, i.e. the project does not lead to land use change.
>
> c. Tillage practice:
> - Under this Activity Module, conservation tillage methods are applied, meaning forms of minimum or reduced tillage, where residue, mulch, or sod is left on the soil surface to protect soil and conserve moisture. After planting, at least 30 percent of the soil surface remains covered by residue to reduce soil erosion by water.
> - Due to the uncertainties on the actual carbon benefits of no-till techniques, this activity module is not applicable to no-till techniques, including strip tillage and direct drill practices.

**Definitions (Section 2.1, p. 4):**
- *Conservation tillage*: "Includes any form of minimum or reduced tillage, where residue, mulch, or sod is left on the soil surface to protect soil and conserve moisture. After planting, at least 30 percent of the soil surface remains covered by residue to reduce soil erosion by water."
- *Conventional tillage*: "Seedbed preparation using cultivation instruments such as harrows, mouldboard ploughs, offset harrows, subsoilers, and rippers. Conventional tillage methods, involving extensive seedbed preparation, cause the greatest soil disturbance and leave little plant residues on the surface."
- *No tillage*: "A way of growing crops or pasture without tillage (no turning of topsoil), minimizing soil disturbance. Also called no-till farming or zero tillage."

**Eligible practice:** conservation tillage (minimum/reduced tillage with at least 30% residue cover after planting). No-till, strip tillage and direct drill are **excluded** (p. 6).

**Baseline (Section 6, p. 7):** "the relevant baseline scenario is the continuation of the historical cropping practices where, in the absence of the project activity, conventional tillage is done in a business as usual (BAU) manner."

**Stratification into modelling units (MU):**
- Baseline (p. 7): Mineral soil type; Climate zone; Land management / cropping system; Input levels (e.g. fertilization); Tillage practices.
- Project (pp. 7-8): Mineral soil type; Climate zone; Cropping systems; Input levels (e.g. fertilization); Tillage practices.
- "For each stratum (MU), SOC measurements have to be performed (Approach 1) and/or model parameters identified and verified (Approach 2 or 3)."

**Boundaries (Section 4, p. 6):**
- Spatial: SOC FM rules apply.
- Temporal: "The project crediting period shall be fixed ten years and cannot be renewed." (Footnote 7 justification: Mangalassery et al. 2014; West and Post 2002.)
- Pools: soil carbon pool only, in line with SOC FM.

### 1.2 Quantification approaches

Section 5 (p. 6): "Calculations for overall benefits follow the equations set out in Section: Emissions Reduction Quantification Approaches of the SOC Framework Methodology."

Section 5.1 (pp. 6-7): **all three approaches are allowed.** "If a different approach is used for baseline and project scenarios in a stratum, conservativeness and comparability have to be ensured."
- **Approach 1:** "Requires on-site measurements to directly document pre-project and project SOC stocks."
- **Approach 2:** "Uses peer-reviewed publications to quantify pre-project SOC stocks and project impact. Project owners shall prove that the research results are conservative and applicable to the project site and management practice."
- **Approach 3:** "Applies default factors to quantify SOC changes from improved tillage, relating to the general methodology described in the IPCC 2019 Guidelines for National Greenhouse Gas Inventories (IPCC 2006a). However, instead of IPCC default SOC reference values (SOCREF), a project-oriented SOCREF value shall be used in connection with IPCC impact factors."
- "Generally, project owners shall apply the most specific approach possible with the data available, giving preference to local data sources and models. A decision tree to determine an eligible approach is provided in the SOC Framework Methodology."

Baseline SOC (SOC_BL,y), Section 6.1: follows SOC FM "Baseline Scenario". Project SOC (SOC_t,y), Section 7.1: follows SOC FM "Project scenario".

**Module-specific equations: none.** 402.1 has no numbered equations of its own. The only module-specific quantities are the tillage factors F_MG,BL,y and F_MG,PR,y (Section 14), which feed the SOC FM Approach 3 equations.

### 1.3 Default factors / tables

- **No IPCC tillage factor values (F_MG, F_I, F_LU) or SOC_REF values are printed in 402.1.** The F_MG parameter tables (pp. 9-10) give the source as "IPCC defaults or national / local studies (preferred)" and leave "Value(s) applied" **blank**. The implementer has to take the values from the SOC FM or IPCC 2019 Vol. 4 Ch. 5. Those sources were not transcribed here.
- **Annex A, Table A-01 (pp. 12-13): Soil carbon (SOC) accumulation for improved tillage approaches for climate and soil combinations.** This annex is explicitly labelled "an extract of the original non-binding Annex of the 2016 approved Gold Standard methodology" (p. 11). The module says "these values are rough indications only". Unit: tCO2e ha-1 yr-1.

| IPCC Climate Zone | IPCC Soil Type | Country | SOC accumulation range (tCO2e ha-1 yr-1) | Crop - Biomass productivity | Reference |
|---|---|---|---|---|---|
| Tropical Dry | HAC | India | 0.83 | No change | Kurothe et al., 2014 |
| Tropical Dry | LAC | India | 1.94 to 2.24 | No change | Bhattacharyya et al., 2009 |
| Tropical Dry | LAC | India | 0.89 to 1.38 | No change | Das et al., 2013 |
| Tropical Dry | LAC | India | 1.36 | Higher | Bhattacharyya et al., 2012 |
| Tropical Dry | Sandy | Zimbabwe | 2.57 | N/A | Thierfelder et al., 2012 |
| Tropical Moist | LAC | Brazil | 0.44 to 1.03 | N/A | Costa Junior et al., 2013 |
| Tropical Moist | LAC | Brazil | 1.28 | N/A | Metay et al., 2007 |
| Tropical Montane | HAC | Zimbabwe | 5.32 | Higher | Thierfelder and Wall, 2012 |
| Tropical Montane | LAC | Zambia | 5.35 to 6.53 | Higher | Thierfelder et al., 2013 |
| Tropical Montane | Sandy | Zimbabwe | 5.79 | No change | Thierfelder et al., 2012 |
| Tropical Montane | Sandy | Zimbabwe | 2.93 to 5.87 | No change | Thierfelder and Wall, 2012 |
| Tropical Wet | LAC | Nigeria | 2.25 | N/A | Lal, 1997 |
| Warm Temperate Dry | HAC | Morocco | 1.14 | N/A | Mrabet et al., 2001 |
| Warm Temperate Dry | HAC | Spain | 1.32 | N/A | Lopes and Fando Pardo, 2011 |
| Warm Temperate Dry | HAC | Tunisia | 1.47 to 2.79 | N/A | Jemai et al., 2012 |
| Warm Temperate Dry | HAC | Argentina | 3.30 | Higher | Bono et al., 2008 |
| Warm Temperate Dry | HAC | Slovakia | 0.69 | N/A | Macák et al., 2010 |
| Warm Temperate Moist | HAC | Madagascar | 2.78 to 4.92 | N/A | Sá et al., 2006 |
| Warm Temperate Moist | LAC | Madagascar | 2.53 | N/A | Razafimbelo et al., 2008 |

Usage condition (p. 11): "in order to apply such parameters, projects must match the sources conditions, i.e. climate, soil, cropping system and any other parameters in the reference (e.g. soil clay content). It is the project owners' responsibility to provide evidence that this requirement is met."

### 1.4 Monitoring parameters (Section 14, pp. 9-10)

These are in addition to the SOC FM monitoring parameters.

| Parameter | Unit | Description | Source | Frequency | Section |
|---|---|---|---|---|---|
| F_MG,BL,y | [dimensionless] | tillage factor before project start in stratum y | IPCC defaults or national / local studies (preferred) | Project start | 14.1 (fixed: baseline, when areas are added, at renewal if required) |
| F_MG,PR,y | [dimensionless] | tillage factor after project start in stratum y | IPCC defaults or national / local studies (preferred) | Annually | 14.2 (monitored) |

Evidence that applicability conditions are met "at all times", especially (p. 10):
- Measures are taken to prevent soil erosion
- Adequate input of organic crop residue, mulch, sod or other organic C source is applied to the project area fields

### 1.5 Uncertainty, other emissions, leakage, buffer/permanence

- **Uncertainty (Section 8, p. 8):** follows SOC FM rules and equations. No module-specific rule.
- **Other emissions (Section 9, p. 8):** "Significant additional greenhouse gas emissions (>5% total) due to the project activity need to be accounted for. For this SOC Activity Module, this explicitly includes emissions from increased fertilizer input, fossil fuel combustion, and other agrochemical emissions." Calculated with SOC FM equations, area-wide. 402.1 has no stratum-level replacement.
- **Leakage (Section 10, p. 8):** follows SOC FM. Module-specific text: "leakage from C runoff is considered 0 as projects are not allowed on wetlands ... Thus for initial project calculations, LKt-0 is considered equal 0." "If a reduction in yield is detected in a performance certification, it is assumed that the lost production capacity will have to be made up for on land outside the project area. Emissions caused by such a shift shall be accounted for as leakage according to the equation listed in the SOC Framework Methodology."
- **Project buffer (Section 11, p. 8):** "Allocation to Gold Standard Compliance Buffer shall follow requirements defined in GHG Emissions Reduction & Sequestration Product Requirements and in the SOC Framework Methodology." No module-specific buffer percentage.
- **Additionality (Section 12, p. 9):** LUF Activity Requirements and the AGR Additionality (AGR projects) Template.

### 1.6 Ambiguities (402.1)

1. p. 7: Approach 3 refers to "IPCC 2019 Guidelines for National Greenhouse Gas Inventories (IPCC 2006a)". This mixes the 2019 Refinement and the 2006 Guidelines. Which edition's F_MG values apply is unclear.
2. pp. 9-10: F_MG "Value(s) applied" is blank. No numeric tillage factors appear anywhere in the module. F_I (input factor) and F_LU are not mentioned at all, so the module does not say whether they are held constant between baseline and project.
3. p. 7: Approach 3 requires "a project-oriented SOCREF value" but gives no procedure for deriving it. Batjes (2010/2011) is cited in the references (p. 4), possibly as the intended source. This is not stated.
4. p. 3: "conservation tillage methods are introduced to project areas previously under more conservative management". This reads like a drafting error, since the baseline is conventional tillage (p. 7).
5. p. 6: No-till is excluded here, while 402.4 now covers zero tillage. The 30% residue threshold is the same in both, so the line between "reduced tillage with at least 30% residue cover" (402.1) and "zero tillage with more than 30% cover" (402.4) depends only on whether there is any soil disturbance.
6. p. 6: The crediting period is "fixed ten years ... cannot be renewed". 402.4 instead requires renewal at year 5 (p. 8). This 2020 module may be out of step with later GS Principles & Requirements.
7. Section 14 heading (p. 9): "at renewable of crediting period" (typo for "renewal"). This conflicts with the non-renewable crediting period stated on p. 6.
8. p. 8: LK is set to 0 "for initial project calculations", but the module does not say at what point the yield check is made, or against which CY threshold.
9. Table A-01 (pp. 12-13): this is a non-binding annex. Whether its values may be used as Approach 2 "peer-reviewed" inputs is not stated. Unit: tCO2e ha-1 yr-1.

---

## Module 402.4: Zero Tillage (v1.0, 20.02.2024)

### 2.1 Applicability, eligible practices, baseline

**Definitions (Section 1, p. 5):**
- *Zero Tillage/No-Till*: "Zero tillage/no-till is an agricultural technique for growing crops or pasture without mechanically disturbing the soil through tillage (including disturbance from non-turning tillage such as rippers and disc harrows). Crop is sown directly into soil that has not been tilled since the harvest of the previous crop. This technique has more than 30% coverage of the soil surface with residues."
- *Conventional Tillage*: "Seedbed preparation using cultivation instruments such as harrows, mouldboard ploughs, offset harrows, subsoilers, and rippers. Conventional tillage methods, involving extensive seedbed preparation, cause the greatest soil disturbance and leave little plant residue on the surface."
- *Conservation Tillage*: "Conservation tillage includes any form of minimum or reduced tillage in which residue, mulch, or sod is left on the soil surface to protect soil and conserve moisture. After planting, at least 30% of the soil surface remains covered by residue to reduce soil erosion by water."

**Scope (2.1.1, p. 5):** "applicable to project activities that introduces zero tillage/no-till practice, an agricultural technique for growing crops or pasture without mechanically disturbing the soil through tillage."

**Applicability (2.2, pp. 5-7), exact text:**
> 2.2.1 | Projects applying this SOC Activity Module shall comply with the applicability conditions that are specified below and are within the SOC Framework Methodology. In addition, projects shall comply with applicable Land Use & Forests Activity Requirements (hereafter LUF Activity Requirements) and the Gold Standard for the Global Goals Principles & Requirements (hereafter Principles & Requirements).
>
> 2.2.2 | Applicability conditions specific to this SOC Activity Module:
> a. Geographic location – The activity module is applicable globally.
> b. Project area –
>   i. Generally, entire farms or selected fields/areas of a farm are eligible (see Section 4.1: Spatial Boundary).
>   ii. The methodology shall not be applicable to farms which have been applying zero tillage techniques in more than one full rotation cycle in the baseline period prior to project start, even if such application was on fields not included in the project. For single crop systems, baseline practices shall not include more than two subsequent years of zero tillage practices. In the baseline period, at least one tillage event (soil disturbance) shall be no less than two years prior to project start.
> c. Zero tillage refers to practices on arable land for which no tillage is applied between harvest and sowing. Crop is sown directly into soil that has not been tilled since the harvest of the previous crop. At least 30% of the soil surface remains covered by residue to reduce soil erosion by water.
> d. Soil type –
>   i. Proposed projects on sites with organic soils (Histosols), as defined by the World Reference Base for Soil Resources (FAO 2015), are ineligible. While no-till practices can reduce C losses from organic soils, they shall not commonly lead to an increase in soil carbon as targeted by this SOC Activity Module. Thus, only mineral soil types are eligible.
> e. In line with the SOC Framework Methodology, any reduction in crop yield which can be attributed to the project activity shall be avoided. To date, the majority of studies report little or no difference in yield between the zero and conventional tillage managements (Shakoor et al. 2021, Huang et al. 2018). However, it has been reported that yields in the first one to two years following zero tillage implementation can decline (Pittelkow et al. 2015b). This SOC Activity Module thus requires monitoring whether the project activity impacts crop yields, calculated as the five-year average. Reductions of more than 5% in five-year average yield during the crediting period shall be accounted for as leakage (see Section 11). An exception to this may be allowed for reductions in the first three years after project start to allow refinement of practices, subject to review at verification.
> f. In line with the SOC Framework Methodology, this SOC Activity Module only accounts for benefits in the SOC pool. No other pools or emission reductions (e.g. in N2O due to reduced fertilizer need) can be accounted for as benefits.
> g. No reversal to conventional or reduced tillage practices is allowed on the project area fields. This explicitly prohibits tillage rotation approaches applying periodic tillage runs between or after several years of zero tillage during the crediting period.
> h. Organic carbon inputs to the field (other than on-field crop residue) shall not be changed as part of the project activity by more than 5% from baseline period average.
>    Exception: If this activity module is stacked with an additional Gold Standard methodology or activity module which uses the same quantification approach in the project (measurement or compatible SOC model allowing distinction of impacts between zero tillage and organic inputs) and considers respective leakage effects, this applicability condition may be omitted.
> i. If project activity includes change of other agricultural practices impacting SOC (e.g. cover crops, organic inputs), the same quantification approach (measurements and/or models) shall be used for all activities and shall be fully aligned to ensure that overall benefits are quantified correctly and not double-counted.
> j. Application of herbicides to prepare fields and/or terminate crops shall be minimized, and negative environmental impacts shall be prevented, in accordance with Gold Standard Principle 9.6. Use of herbicides related to project activities, specifically for crop termination and weed control, shall not be increased by more than 5% from baseline period average.

**Entry into force (2.3.1, p. 7):** "dd/02/2024" (day placeholder left in the published text).

**Baseline (Summary, p. 2):** "In the baseline situation, a farmer applies conventional or conservation tillage practices in which soil disturbance is caused by applying instruments such as harrows, mouldboard ploughs, offset harrows, subsoilers, and rippers for extensive seedbed preparation in a conventional tillage approach or less soil disturbance following a reduced tillage approach applying chisels, sweeps, and/or discs. The project introduces the zero tillage/no-till practice, which applies direct seeding of crops in a field without mechanical disturbance of the soil."

**Additionality (Section 3, p. 7):** regulatory surplus is required for all projects, irrespective of scale. If a legal requirement is identified, crediting is allowed only until the date it takes effect. Otherwise see the Additionality section of the SOC FM.

**Boundaries (Section 4, pp. 7-9):**
- 4.1.2a: The same fields "shall remain in the project during the entire crediting period (i.e. no change of participating fields within a farm during the crediting period is allowed)."
- 4.1.2b / Figure 4-01: the SSR boundary includes on-field crop residue management, machine use, organic inputs, tillage, fertilizer application and pesticide application. Excluded (marked *): fertilizer production, farm equipment manufacture and transportation, farm facilities construction, operations and decommissioning, post-harvest processing, crop processing and crop transport.
- 4.2.1 Temporal: "The maximum crediting period allowed under this Activity Module is 10 years The crediting period renewal at the end of 5th year is required as per Principles and requirements."
- 4.3 Pools: benefits come from the SOC pool only. Biomass and litter may be used to calculate SOC change but are not credited. No ERs from fuel or fertilizer.
- 4.4.2 GHGs: "any significant increases in CO, CH4, and NO emissions from project activities" (as printed; probably CO2 and N2O with subscripts lost).

### 2.2 Quantification approaches and equations

**5.1.1 (p. 9):** "This SOC Activity Module allows application of quantification Approaches 1 and 2, as described in the SOC Framework Methodology. It does not allow application of Approach 3 (default equations and parameters). Project developers shall select the most specific approach possible with the data available, as outlined in the decision tree in Figure 2 of the SOC Framework Methodology."

**Approach 1 additional requirements (5.2.1, pp. 9-10):**
- a. Sample at a suitable time of year (e.g. beginning of the main-crop season) and repeat at the same time of year. The project documentation must specify sampling timing (season and crop rotation phase) for all farms.
- b. Measure "before any significant carbon inputs, such as organic or partially organic fertilizers, including compost and manure, as well as other carbon sources (e.g. in lime or other soil inputs)."
- c. "In line with the SOC Framework Methodology, soil samples shall be collected to a depth of 50 cm."
- d. Avoid repeated sampling at the same position (e.g. mark sites, record exact GPS coordinates and set a minimum distance for the next round).
- e. "bulk density must be considered in all quantification approaches. Quantification is to be done on an equivalent mass basis ... if increased bulk density is measured in the project scenario, respective layer depth shall be reduced proportionally when calculating SOC change."
- f. Exclude superficial litter (crop residue) from SOC quantification.

**5.2.2 (p. 10):** Alternative SOC quantification (proximal sensing in situ, lab spectroscopy) is allowed only if approved by GS at Activity Requirement level, with scientific proof of no significant difference from lab results to 50 cm. If the technology is untested under comparable conditions, a project-specific dataset is needed: repeated SOC stock measurements at at least two points in time, with parallel lab analysis, and separate calibration and validation datasets. A design change approved by GS is then required. Uncertainty follows the GS Uncertainty Requirements and the SOC FM Uncertainty Assessment.

**Approach 2 additional requirements (5.3.1, p. 11):**
- a. Evidence that approaches, datasets, parameters and models from peer-reviewed publications are conservative and applicable (footnote 7: all stratification criteria of 7.1.4 must be assessed).
- b. "Models and datasets applied must be calibrated locally, i.e. using project-specific data. Global models without such local parametrization and validation shall not be applied. Application of global defaults for soil respiration, e.g. Q10 values to quantify temperature effects on respiration, is not allowed."
- c. Evidence of applicability to main crops, yield levels (production intensity) and management (including tillage). Datasets and models need sufficient temporal resolution (multiple data points per year).
- d. "Parameters for process-based models shall be calibrated and verified following best practice, using at least five years of data for calibration and three years of independent data for verification." Gaps must be reported at validation.
- e. "SOC measurements for a representative sample in each stratum of the project area shall be made at project start and at least once every five years, applying proven methodology (see Section 5.2.2) and used to statistically assess model results or research data used for quantification. If significant differences from modelled results or research data are found, the models shall be refined."

**Baseline (6.1, p. 12):** SOC_BL,y follows the SOC FM Baseline Scenario. Five years of baseline data are required (6.1.2). If a field lacks them, evidence must show that the stratum averages apply. The baseline period may be extended to cover full rotations (6.1.3; e.g. a 3-year rotation gives a 6-year baseline). Stratification (6.1.4) uses SOC FM Section 6 criteria plus: Mineral soil type; Tillage practices (e.g. tillage depth, frequency, tillage equipment); Specific crops (or crop rotations) and production periods. 6.1.5: no "black box" models.

**Project (7.1, pp. 12-13):** SOC_t,y follows the SOC FM Project Scenario. All practice changes must be considered (crop management, fertilization, other agrochemicals). Other activities (cover crops, organic inputs) must use the same approach, and models must cover all activities (7.1.3). Stratification (7.1.4) uses SOC FM Section 7 criteria plus: Mineral soil type; Tillage practices (zero tillage); Specific crops (or crop rotations) and production periods. 7.1.5: no "black box" models.

**Approach change (8.1.1, p. 13):** must comply with SOC FM Section 8 "Procedure for approach change".

**Module-specific equations (Section 10, pp. 13-17; Section 11, p. 17).** 10.1.2: "calculation for this SOC Activity Module shall follow the rules and Equations 1 through 7 that are described below, which replace the area-wide calculation set out in Equations 12 through 18 of the SOC Framework Methodology." Eq. 8 replaces SOC FM Eq. 19 (11.1.2).

**Eq. (1), p. 13: project emissions**
```
PE_{t-0} = ΔFE_{t-0} + ΔFU_{t-0} + ΔAE_{t-0}
```
| Symbol | Definition | Unit |
|---|---|---|
| PE_t-0 | emissions from project activities in the calculation period | tCO2e |
| ΔFE_t-0 | emissions from increased fertilizer use in the calculation period | tCO2e |
| ΔFU_t-0 | emissions from increased fuel and electricity use in the calculation period | tCO2e |
| ΔAE_t-0 | other agrochemical emissions in the calculation period | tCO2e |

**Eq. (2), p. 14: increased N fertilizer**
```
ΔFE_{t-0} = Σ_y [ EF_{FE,y} × Σ_{a=1}^{T} ( FE_{PR,y,a} − FE_{BL,y} ) ]
```
| Symbol | Definition | Unit |
|---|---|---|
| ΔFE_t-0 | emissions from increased fertilizer use in the calculation period. "Must be ≥ 0 in this methodology (i.e. no accounting of reductions)." | tCO2e |
| FE_PR,y,a | N fertilizer input in stratum y under the project scenario in year a of the calculation period | kgN |
| FE_BL,y | mean annual N fertilizer input in stratum y under the baseline scenario | kgN |
| T | number of years in the calculation period | yr |
| EF_FE,y | Conversion factor for emissions from N fertilizer in stratum y. IPCC 2019 aggregated default value for EF_FE is 0.01. Disaggregated default values in IPCC 2019 Table 11.1 may be used if fertilizer inputs are known per fertilizer type. | tCO2e kgN-1 |

Rules: no distinction is made between synthetic and organic N. If N input is reduced, ΔFE_t-0 = 0. FE_BL is the mean of the 5 years before project start. "If no adequate documentation can be provided, FE_BL shall be no more than 50% of FE_PR."

**Eq. (3), p. 15: increased fuel and electricity** (bracketing exactly as printed)
```
ΔFU_{t-0} = Σ_y [ Σ_{a=1}^{T} ( FU_{PR,y,a} − FU_{BL,y} ) + ( EU_{PR,y,a} − EU_{BL,y} ) ]
```
| Symbol | Definition | Unit |
|---|---|---|
| ΔFU_t-0 | emissions from increased fossil fuel and electricity use in the calculation period | tCO2e |
| FU_PR,y,a | emissions from use of fossil fuels in stratum y under the project scenario in year a of the calculation period | tCO2e |
| FU_BL,y | mean annual emissions from use of fossil fuels in stratum y under the baseline scenario | tCO2e |
| EU_PR,y,a | emissions from use of electricity in stratum y under the project scenario in year a of the calculation period | tCO2e |
| EU_BL,y | mean annual emissions from use of electricity in stratum y under the baseline scenario | tCO2e |
| T | number of years in the calculation period | yr |

ΔFU_t-0 = 0 if the developer shows that project fuel and electricity use is less than, or not significantly different from, the baseline.

**Eq. (4), p. 15: fuel emissions**
```
FU_{i,y,a} = Σ_MT FUL_{i,y,MT,a} × FEF_{i,y,MT}
```
| Symbol | Definition | Unit |
|---|---|---|
| FU_i,y,a | emissions from use of fossil fuels in stratum y in year a | tCO2e ha-1 (as printed) |
| FUL_i,y,MT,a | fuel consumption in stratum y by the machinery type MT used in year a | litres |
| FEF_i,y,MT | emissions factor for the fuel used in stratum y in machinery MT | tCO2e litres-1 |
| MT | machinery type (gasoline two-stroke, gasoline four-stroke, diesel) | – |
| i | formula used for baseline (i=BL) as well as project scenario (i=PR) | – |

FU_BL is the mean of the 5 years before project start. If records are missing, fuel may be estimated from fuel efficiency (l/100 km, l/tonne-km, l/hour) times use. "If no adequate documentation can be provided, FU_BL shall be no more than 50% of FU_PR." Non-CO2 from fossil fuel is insignificant and may be neglected.

**Eq. (5), p. 16: electricity emissions**
```
EU_{i,y,a} = Σ_SE EUW_{i,y,SE,a} × EEF_{i,y,SE}
```
| Symbol | Definition | Unit |
|---|---|---|
| EU_i,y,a | emissions from electricity consumption in stratum y in year a | tCO2e ha-1 (as printed) |
| EUW_i,y,SE,a | electricity consumption in stratum y from source SE in year a | kWh |
| EEF_i,y,SE | emissions factor for the electricity used in stratum y in source SE | tCO2e kWh-1 |
| SE | electricity source type (grid, fossil fuel generator, etc) | – |
| i | BL or PR | – |

On-site fossil generation is calculated as fuel (Eq. 4) instead. EU_BL is the mean of the 5 years before project start. "If no adequate documentation can be provided, EU_BL shall be no more than 50% of EU_PR."

**Eq. (6), p. 16: other agrochemical emissions**
```
ΔAE_{t-0} = Σ_y [ Σ_{a=1}^{T} ( AE_{PR,y,a} − AE_{BL,y} ) ]
```
| Symbol | Definition | Unit |
|---|---|---|
| ΔAE_t-0 | additional emissions from project activity in the calculation period | tCO2e |
| AE_PR,y,a | other emissions in stratum y under the project scenario in year a of the calculation period | tCO2e |
| AE_BL,y | other emissions (annual mean) in stratum y under the baseline scenario | tCO2e |
| T | number of years in the calculation period | yr |

ΔAE_t-0 = 0 if project agrochemical use is less than, or not significantly different from, the baseline. Emission factors come from manufacturer information or scientific sources.

**Eq. (7), p. 17: agrochemical emissions by emitter type**
```
AE_{i,y,a} = Σ_ET AQ_{i,y,ET,a} × AEF_{i,y,ET}
```
| Symbol | Definition | Unit |
|---|---|---|
| AE_i,y,a | emissions from use of other agrochemicals in stratum y in year a | tCO2e ha-1 (as printed) |
| AQ_i,y,ET,a | quantity of agrochemicals in stratum y for emitter type ET applied in year a | kg |
| AEF_i,y,ET | emissions factor of the agrochemical used in stratum y (for emitter type ET) | tCO2e kg-1 |
| ET | emitter type (specific pesticide, fertilizer, or other agrochemical) | – |
| i | BL or PR | – |

AE_BL is the mean of the 5 years before project start. "If no adequate documentation can be provided, AE_BL shall be no more than 50% of AE_PR."

**Eq. (8), p. 17: stratum-level leakage (replaces SOC FM Eq. 19)**
```
LK_{t-0} = Σ_y [ max[ (CY_{min,y} − CY_{t,y}) / CY_{BL,y} ; 0 ] × Ā_{y,t} ] × ( ΔBC_LA + ΔSOC_{LA,t-0} + ΔFE_{LA,t-0} + ΔFU_{LA,t-0} )
```
| Symbol | Definition | Unit |
|---|---|---|
| LK_t-0 | emissions due to shift of production to non-project lands (leakage area) | tCO2e |
| CY_t,y | crop yield in stratum y at time t (five-year average*) | kg ha-1 |
| CY_min,y | lowest crop yield (five-year average**) in stratum y in any calculation period since project start | kg ha-1 |
| CY_BL,y | crop yield in stratum y under the baseline scenario (five-year average*) | kg ha-1 |
| Ā_y,t | eligible project area in stratum y (five-year average*) | ha |
| ΔBC_LA | emissions from change in biomass carbon stocks in leakage area | tCO2e ha-1 |
| ΔSOC_LA,t-0 | emissions from change in SOC stocks in leakage area | tCO2e ha-1 |
| ΔFE_LA,t-0 | change in emissions from use of fertilizer in leakage area | tCO2e ha-1 |
| ΔFU_LA,t-0 | change in emissions from fuel use in leakage area | tCO2e ha-1 |

\* "If the baseline period is extended to cover full rotation cycles, crop yield and stratum area shall be calculated as the average across an equal length period. In the project scenario, the five-year average shall be calculated as a running average from year t-4 to year t (for longer baseline periods, averaging period shall be increased accordingly)."
\** "Baseline years shall be in included in CY_min for the project period (i.e. in project year 1, CY_min = CY_BL)."

### 2.3 Default factors / tables

- **No SOC stock change factors, tillage factors (F_MG/F_I), SOC_REF or climate/soil tables.** Approach 3 is not allowed (p. 9). The summary (p. 2) says "This SOC Activity Module does not allow Approach 3 (IPCC defaults)".
- **EF_FE = 0.01 tCO2e kgN-1**: "IPCC 2019 aggregated default value". Footnote 8: "IPCC 2019, Vol 4 AFOLU, Table 11.1 (Aggregated default value)" (p. 14; also p. 19 parameter table).
- **Uncertainty defaults (9.1.2, p. 13):** SE = 50% of the parameter value if no SD/SE is known. t-value = 3 for upper/lower confidence intervals. Exceptions are accepted constants (physical conversion rates, GWPs).
- **Missing-baseline-record caps:** FE_BL, FU_BL, EU_BL, AE_BL are each "no more than 50%" of the corresponding PR value (pp. 14-17).
- **Thresholds:** 5% significance for other emissions (10.1.1). Yield reduction above 5% in the 5-yr average counts as leakage (2.2.2e). Organic C inputs may change by no more than 5% (2.2.2h). Herbicide use may increase by no more than 5% (2.2.2j). Soil sampling depth is 50 cm (5.2.1c).
- **EEF sources (p. 23):** (a) regional/national grid: latest TOOL05; (b) mini grid: latest "AMS-I.F."; (c) renewable captive plant: 0 tCO2/MWh; (d) fossil captive: national GHG inventory sources (USA EPA EF for GHG Inventories; EU EMEP/EEA guidebook 2019 and 2023), otherwise IPCC 2006 Vol 2, Ch 3, Table 3.3.1.
- **FEF sources (p. 24):** national GHG inventory sources (USA EPA; Canada Emission_Factors.pdf (ec.gc.ca); EU EMEP/EEA 2019 and 2023), otherwise IPCC 2006 Vol 2, Ch 3, Table 3.3.1.

### 2.4 Monitoring parameters (Section 12, pp. 18-24)

12.1.1: Evidence that applicability conditions are met at all times and "specifically that no tillage events have occurred. Acceptable evidence are detailed field reports listing key interventions, dates and machinery used, remote sensing analysis of vegetation, and crop residue cover or time-stamped photographs of fields before, during, and after the cropping season, including fallow periods as applicable."
12.1.2: Where these overlap with SOC FM parameters, the module definitions apply.

**a. Fixed (collected for baseline, when areas are added, and at renewal):**

| Parameter | Unit | Description | Source | Frequency | Used in / notes |
|---|---|---|---|---|---|
| CY_BL,y | kg ha-1 | Average annual crop yield per hectare (ha) in stratum y in the project area during the baseline period (five-year average*) | Farm records, e.g. field records, sales receipts | Project start | Eq. 8. Replaces CY_BL of SOC FM Eq. 19. Recorded per crop season, summed annually across crop types. |
| EF_FE,y | tCO2e kgN-1 | Conversion factor for emissions from N fertilizer in stratum y | IPCC 2019 | Project start | Eq. 2. Value 0.01 (aggregated). Table 11.1 disaggregated values allowed. |
| FE_BL,y | kgN | Mean annual N fertilizer input in stratum y under the baseline scenario | Farm records (field level) | Project start | Eq. 2. Average over the 5-year baseline. |

**b. Monitored:**

| Parameter | Unit | Description | Source | Frequency | Used in / notes |
|---|---|---|---|---|---|
| Ā_y,t | ha | Eligible project area in stratum y at time t (five-year average*) | Farm records (GPS data, GIS files) | Annually (for 5-yr average) | Eq. 8 |
| AQ_i,y,ET,a | km (as printed; Eq. 7 says kg) | Quantity of agrochemicals in stratum y for emitter type (ET) applied in year a | Farm records | Annually | Eq. 7. Quantity and type of non-N fertilizer agrochemicals used for zero tillage (e.g. crop termination, weed control). |
| AEF_i,y,ET | tCO2e kg-1 | Emissions factor of the agrochemical used in stratum y (for emitter type [ET]) | Supplier information | Annually | Eq. 7. Supplier LCA (production + transport), otherwise national/international defaults. |
| CY_t,y | kg ha-1 | Average annual crop yield per ha in stratum y in the project area (five-year average*) | Farm records | Annually (for 5-yr average) | Eq. 8. Replaces CY_t of SOC FM Eq. 19. |
| CY_min,y | kg ha-1 | Minimum annual crop yield per ha in stratum y since project start | Farm records | At verification | Eq. 8. Replaces CY_min of SOC FM Eq. 19. In project year 1 it equals CY_BL. |
| ΔBC_LA | tCO2e ha-1 | Emissions from change in biomass carbon stocks in leakage area | Remote sensing analysis or public data on leakage area | At verification | Eq. 8. No increase in biomass may be credited (no positive leakage). |
| ΔSOC_LA,t-0 | tCO2e ha-1 | Emissions from change in SOC stocks in leakage area | Remote sensing analysis or public data on leakage area | At verification | Eq. 8. No increase in SOC may be credited. |
| EEF_i,y,SE | tCO2e kWh-1 | Emissions factor for the electricity used in stratum y in electricity source type | See 2.3 above | Project start, annual review for national updates | Eq. 5 |
| EUW_i,y,SE,a | kWh | Electricity consumption in stratum y from source SE in year a | Farm records | Annually (use-based, summed per year) | Eq. 5. From direct records, or hours times kW per equipment type. |
| FE_PR,y,a | kgN | N fertilizer input in stratum y under the project scenario in year a | Farm records (field level) | Use-based, aggregated annually | Eq. 2 |
| FEF_i,y,MT | tCO2e liter-1 | Emissions factor for the fuel used in stratum y in machinery type (MT) | See 2.3 above | Project start, annual review for national updates | Eq. 4 |
| FUL_i,y,MT,a | Liter | Fuel consumption in stratum y by the machinery type (MT) used in year a | Farm records | Baseline: project start. Project: use-based, summed per year. | Eq. 4. From direct fuel records, or hours/distance times l/h or l/km. |

Also required through the module (Approach 1): SOC stock sampling to 50 cm with bulk density on an equivalent-mass basis. Approach 2: verification SOC sampling at project start and at least every 5 years per stratum. SOC FM monitoring parameters also apply.

### 2.5 Uncertainty, leakage, permanence

- **Uncertainty (9.1, p. 13):** SOC FM rules, plus the default SE of 50% and t = 3 (see 2.3).
- **Leakage (11, p. 17):** SOC FM rules. Leakage is calculated per stratum with Eq. 8 instead of FM Eq. 19. "accounting of positive leakage is not allowed according to the SOC Framework Methodology." Yield reductions of more than 5% (5-yr average) count as leakage. Reductions in the first 3 years may be exempted, subject to review at verification (2.2.2e).
- **Permanence-related rules:** no reversal to conventional or reduced tillage, and no tillage rotation (2.2.2g). Fields are fixed for the whole crediting period (4.1.2a). Crediting period is at most 10 years with renewal at year 5 (4.2.1). The module has no buffer section, so the SOC FM / GS product requirements apply by default.

### 2.6 Ambiguities (402.4)

1. p. 15, Eq. 3: As printed, Σ_{a=1}^{T} closes before the electricity term (EU_PR,y,a − EU_BL,y), which leaves index *a* unbound in the EU term. The intended form is most likely Σ_y[Σ_a((FU_PR − FU_BL) + (EU_PR − EU_BL))]. Transcribed as printed. Same in 402.6 Eq. 3.
2. pp. 15-17, Eqs. 4, 5, 7: FU_i,y,a, EU_i,y,a and AE_i,y,a are given in **tCO2e ha-1**, but the inputs (litres, kWh, kg per stratum) give **tCO2e** per stratum, and Eqs. 3 and 6 treat them as tCO2e. This is a unit inconsistency, and it is unclear whether area scaling is intended.
3. p. 20: The AQ_i,y,ET,a unit is printed as "km". Eq. 7's definition (p. 17) gives [kg]. Probably a typo for kg.
4. p. 5 vs p. 6: 2.2.2(c) requires "At least 30%" residue cover, while the definition (p. 5) says "more than 30%". The boundary case of exactly 30% is ambiguous.
5. p. 6, 2.2.2(b)(ii): "at least one tillage event ... shall be no less than two years prior to project start". It is unclear whether this means a tillage event within the last 2 years is required, or one at least 2 years ago.
6. p. 6, 2.2.2(e) vs Eq. 8: the text says reductions **> 5%** of the 5-yr average count as leakage, but Eq. 8 has no 5% threshold. It applies max[(CY_min − CY_t)/CY_BL; 0] from the first kg of reduction. The 3-year exemption is also not shown in Eq. 8.
7. p. 17-18: CY_min,y is defined as "lowest crop yield ... since project start" and used as min − current. If CY_t equals the running minimum, the term is 0. This makes the leakage term depend on the current yield falling below a *previous* minimum, rather than below baseline. The definitions do not resolve this. Also, CY_min is described as "Minimum annual crop yield" in the parameter table (p. 21) but as a "five-year average" in Eq. 8 (p. 18).
8. p. 7: entry into force "dd/02/2024" (placeholder).
9. p. 8 / p. 9: "CO, CH4, and NO" are probably CO2 and N2O with lost subscripts (printed as shown).
10. p. 8: crediting period is "maximum ... 10 years" with "renewal at the end of 5th year". Whether this means two 5-year periods within a 10-year cap is not stated.
11. 12.1.3 (p. 18): "at renewable of crediting period" (typo for "renewal").
12. pp. 9-10 vs SOC FM: the 50 cm depth is stated "in line with the SOC Framework Methodology". This should be checked against the FM text, which was not transcribed here.
13. p. 9, 10.1.2: Eqs. 1-7 replace FM Eqs. 12-18. The mapping of individual FM equations is not given.

---

## Module 402.6: Cover Crops (v1.0, 02.10.2024)

### 3.1 Applicability, eligible practices, baseline

**Definitions (2.1.1, p. 4):**
- *Farm*: "A farm is an area of land that is devoted primarily to agricultural processes with the primary objective of rearing livestock or producing food and other crops. Under this Activity Module, 'farm' encompasses all such lands legally registered as part of the farm's holdings as well as associated leased lands with a valid contract."
- *Cover crop*: "A cover crop is a close-growing, dense canopy crop that provides soil protection, seedling protection, and soil improvement between periods of normal crop production (Soil Science Society of America, 2008). A cover crop is not harvested, and biomass is not removed from a field (this is particularly relevant to SOC)."
- *Full tillage (full-till)*: "Full tillage refers to field practices leading to substantial soil disturbance with full inversion and/or frequent, within-year tillage operations, while leaving <30% of the surface covered by residues at the time of planting (IPCC 2019, Volume 4, Chapter 5, Section 5.2.3.3)."
- *Reduced tillage (reduced-till)*: "Reduced tillage refers to field practices with primary and/or secondary tillage but with reduced soil disturbance that is usually shallow and without full soil inversion; this normally leaves surface with >30% coverage by residues at planting (IPCC 2019, Volume 4, Chapter 4, Section 5.2.3.3)."
- *Zero tillage (no-till)*: "Zero tillage is an agricultural technique for growing crops or pasture without mechanically disturbing the soil through tillage (including disturbance from non-turning tillage such as rippers and disc harrows). Crop is sown directly into soil that has not been tilled since the harvest of the previous crop. Zero tillage has more than 30% cover of the soil surface with residues."

**Applicability (Section 3, pp. 5-6), exact text:**
> 3.1.1 | A project applying this Activity Module shall comply with the applicability conditions specified below and with those in the Soil Organic Carbon Framework Methodology. In addition, the project shall comply with applicable Land Use & Forests Activity Requirements (hereafter referred to as "LUF Activity Requirements" or Agriculture Activity Requirements when published and in force) and the Gold Standard for the Global Goals Principles & Requirements (hereafter referred to as "Principles & Requirements").
>
> 3.1.2 | Applicability conditions:
> - Projects are eligible in all countries.
> - Generally, entire farms or selected fields/areas of a farm are eligible (see Section 5.1: Spatial Boundary).
> - The Activity Module shall not be applicable to farms which have been using cover crops for more than one season within five years prior to project start, even if such application was on fields not included in the project.
> - In line with the Soil Organic Carbon Framework Methodology, this Activity Module accounts for only those benefits in the SOC pool. No other pools or emission reductions (e.g., in nitrous oxide [N2O] due to reduced fertiliser need) can be accounted for as benefits.
> - Cover cropping can comprise a single species or a mixture of species and can use annual, biennial, or perennial vegetation.
>
> 3.1.3 | Other than cover crops, organic carbon inputs to the field shall not be changed as part of the project by more than 5% from baseline period average. If this Activity Module is stacked with an additional Gold Standard methodology or activity module which uses the same quantification approach in the project (measurement or compatible SOC model allowing distinction of impacts between cover crops and organic inputs from other practice changes) and considers respective leakage effects, this applicability condition may be omitted.
> - If the project includes change of tillage practices, the same quantification approach (measurements, models, or defaults) shall be used for both activities and shall be fully aligned to ensure that overall benefits are quantified correctly and not double-counted. Changes in tillage practices shall be documented and shall follow quantification approaches according to a respective Gold Standard–approved methodology or activity module.
>
> 3.1.4 | Application of herbicides to terminate cover crops shall be minimised, and negative environmental impacts shall be prevented in accordance with Gold Standard Safeguarding Principle 9.6 (Pesticides & Fertilisers). Use of herbicides related to the project, specifically for crop termination and weed control, shall not be increased by more than 5% from baseline period average.

**Eligible practices (Summary p. 3; 8.1.2 p. 14):** cover crops planted during the fallow period. Categories: legumes, non-legumes, grasses and brassicas. Single species or mixtures. Annual, biennial or perennial. Combined with reduced till or no-till. Termination at the end of the fallow period, including by grazing. In no-till, cover crops are left on the surface.

**Baseline (Summary, p. 3):** "In a typical baseline situation, crop fields are left bare (i.e., without plant growth) from the time of harvest until the next crop is planted (fallow period)." 10.4.1 (p. 19): "applicability conditions for this Activity Module do not allow cover crops in the baseline scenario".

**Additionality (4.1.1, p. 6):** LUF Activity Requirements Additionality section and the Additionality Requirements for Agriculture Projects Template.

**Boundaries (Section 5, pp. 7-9):**
- 5.1.2: Selected fields must meet all conditions, "(including maintaining yield)", and stay in the project for the whole crediting period with no change of participating fields. The boundary includes main crop practices, cover crop growth and residue management, other organic inputs (monitored), and **cover crop seed production and transport**.
- Figure 5-01: project-controlled or project-related SSRs are crop biomass growth and residues, machine use, organic inputs, tillage, fertiliser application, pesticide application, cover crop seed production and seed transport. Excluded (*): fertiliser production, farm equipment manufacture and transportation, farm facilities, post-harvest/crop processing and crop transport.
- 5.2.1 Temporal: "This Activity Module requires a crediting period of 10 years to account for the slow SOC buildup and to ensure long-term SOC impacts. The crediting period can be renewed once."
- 5.3 Pools: SOC only. Biomass and litter may be used in calculation but not credited. No ERs from fuel or fertiliser.
- 5.4.2 GHGs: "any significant increases in carbon dioxide (CO), methane (CH4), and NO emissions from the project" (as printed).

### 3.2 Quantification approaches and equations

Section 6 (p. 9): "Calculations for overall benefits follow the equations in the Emissions Reduction Quantification Approaches section of the Soil Organic Carbon Framework Methodology."

**6.1.1 (p. 9):** "This Activity Module allows application of all three quantification approaches as described in the Soil Organic Carbon Framework Methodology. Project proponents shall select the most specific approach possible with the data available, giving preference to local data sources and models as outlined in the decision tree in Figure 2 of the Soil Organic Carbon Framework Methodology."

**Approach 1 additional requirements (6.2, pp. 9-10):**
- Sample at a suitable, repeated time of year "to avoid bias due to short-term variation in soil carbon pools (e.g., after harvest of main crops and tilling of crop residue into the soil)". Timing (season and rotation phase) must be specified for all sampled farms.
- Measure before significant C inputs (organic/partially organic fertilisers, compost, manure, lime or other soil inputs) "and soil disturbance events (tillage)".
- "Bulk density shall be considered in all quantification approaches. Quantification shall be done on an 'equivalent mass basis' ... if increased bulk density is measured in the project scenario, respective layer depth shall be reduced proportionally when calculating SOC change."
- 6.2.2: Exclude surface litter (crop residue) from SOC quantification.
- (No sampling depth is stated in 402.6. See ambiguities.)

**Approach 2 additional requirements (6.3, pp. 10-11):**
- Conservative and applicable peer-reviewed sources. "In accordance with the LUF Activity Requirements, 'conservativeness' shall mean that from a range of available data, the value resulting in lower GHG benefits shall be applied."
- Local calibration with project-specific data. Global models without local parametrisation/validation are not allowed. Global soil-respiration defaults (Q10) are not allowed.
- Applicability evidence for main crops, yield levels, management (tillage; footnote 2: "Changes in tillage due to cover crops shall be represented in the model parameters at the level required by the specific model applied"), and cover crop species and practices (e.g. duration of growth). Temporal resolution must be multiple data points per year. "If the model used does not allow seasonal crop and practice variations, data shall be aggregated to a representative annual value with and without cover crops."
- Process-based models need at least 5 years of calibration data and 3 years of independent verification data.
- "SOC measurements for a representative sample in each stratum of the project area shall be made at project start and at least once every five years, applying proven methodology (see Section 6.2 above)". Models are refined if significant differences are found.

**Approach 3 additional requirements (6.4, pp. 11-13).** 6.4.1: "this Activity Module provides two alternative calculations in addition to the IPCC Tier 1/2 approach as listed in the Soil Organic Carbon Framework Methodology":
- **Approach 3.1** (6.4.2): "applies default equations to estimate SOC changes as described for Approach 3 in the Soil Organic Carbon Framework Methodology, based on a Tier 2 approach according to IPCC 2019. Cover crop residue shall be considered as 'organic inputs' only. However, as no specific stock change factors for cover crops are available in the IPCC guidelines, national or regional Tier 2 parameters for organic input stock change factors specific to cover crops must be used, in line with the Soil Organic Carbon Framework Methodology. This Activity Module thus requires that national or regional Tier 2 SOC reference values (SOCREF) and stock change factors shall be applied in **Equations 4 and 6 of the Soil Organic Carbon Framework Methodology**. If tillage practices are changed due to the introduction of cover crops, stock change factors for tillage practices (see Section 2.1.1 for definitions) shall also be applied in accordance with the Tier 2 data source."
- **Approach 3.2** (6.4.3): "applies the IPCC Tier 2 'Steady State Approach' according to IPCC 2019, Volume 4, Chapter 5". The following interpretations apply:
  - "The IPCC 2019 term 'grid cell or region' shall be interpreted as field strata or individual fields, as appropriate to achieve conservative results at the field level within Gold Standard uncertainty requirements."
  - All inputs at field or stratum level: harvested crops for baseline, harvested crops plus cover crops for project, plus green manure, compost and animal manure.
  - Tillage changes from cover crop management are handled per IPCC 2019 and the Tier 2 source.
  - Project-specific data are used if available, with evidence of applicability.
  - Otherwise IPCC 2019 Tier 2 parameters (Table 6-01) may be used, considering their uncertainties. A min/max sensitivity analysis is recommended. "Crop volumes, soil, and weather data used in the quantification shall always be based on local information."
  - All input parameters must be monitored and reported with source and rationale (Section 12).
  - "If the project includes tillage changes, Approach 3.2 shall be applied only if no separate calculation of tillage impacts on SOC is performed".
  - The IPCC 2019 spreadsheet may be consulted for reference.

**Baseline (7.1, pp. 13-14):** SOC_BL,y follows the SOC FM Baseline Scenario. 5 years of baseline data are required. Fields lacking them need evidence that stratum averages apply. Extension to full rotations is allowed (e.g. a 3-yr rotation gives a 6-yr baseline). Stratification (7.1.4) uses SOC FM Section 6 plus: Mineral soil type (footnote 4: "e.g. World Reference Base for Soil Resources (WRB) Reference Soil Groups (RSG)"); Tillage practices; Specific crops (and crop rotations) and production period; Productivity (e.g., net primary productivity or crop yield); Fallow (bare) period. 7.1.5: no "black box" models (Approach 2).

**Project (8.1, pp. 14-15):** SOC_t,y follows the SOC FM Project Scenario. Quantification must reflect specific cover crops and practices (termination, residue cover). Other activities (e.g. tillage change) must use the same approach (1, 2 or 3), and models must cover all activities (8.1.3). Stratification (8.1.4) uses SOC FM Section 7 plus: Mineral soil type; Tillage practices; Specific crops (or crop rotations) and production period; Productivity; Fallow (bare) period (only if part of the area remains uncovered); Cover crop period; Cover crop type. "Baseline strata with bare land shall be subdivided based on cover crop type and practices." 8.1.5: no "black box" models.

**Module-specific equations (Section 10, pp. 16-21; Section 11, p. 22).** 10.1.2: "Equations 1 through 8, which replace the area-wide calculation in Equations 12 through 18 of the Soil Organic Carbon Framework Methodology. They follow the same approach but expand calculation to include cover crop seed production and transport". Eq. 10 replaces SOC FM Eq. 19.

**Eq. 1, p. 16**
```
PE_{t-0} = ΔFE_{t-0} + ΔFU_{t-0} + ΔSPT_{t-0} + ΔAE_{t-0}
```
| Symbol | Definition | Unit |
|---|---|---|
| PE_t-0 | emissions from project activities in the calculation period | tCO2e |
| ΔFE_t-0 | emissions from increased fertiliser use in the calculation period | tCO2e |
| ΔFU_t-0 | emissions from increased fuel and electricity use in the calculation period | tCO2e |
| ΔSPT_t-0 | emissions from cover crop seed production and transport in the calculation period | tCO2e |
| ΔAE_t-0 | other agrochemical emissions in the calculation period | tCO2e |

**Eq. 2, p. 16:** identical form to 402.4 Eq. 2
```
ΔFE_{t-0} = Σ_y [ EF_{FE,y} × Σ_{a=1}^{T} ( FE_{PR,y,a} − FE_{BL,y} ) ]
```
Variables, units and rules are as in 402.4 Eq. 2: ΔFE ≥ 0. FE_PR,y,a and FE_BL,y in kgN. T in yr. EF_FE,y in tCO2e kgN-1, with IPCC 2019 aggregated default 0.01 (footnote 5: "IPCC 2019, Vol. 4 AFOLU, Table 11.1 (aggregated default value)"). FE_BL is the 5-yr mean, capped at 50% of FE_PR if undocumented.

**Eq. 3, p. 17:** identical form to 402.4 Eq. 3, bracketing as printed
```
ΔFU_{t-0} = Σ_y [ Σ_{a=1}^{T} ( FU_{PR,y,a} − FU_{BL,y} ) + ( EU_{PR,y,a} − EU_{BL,y} ) ]
```
Variables (all tCO2e except T [yr]) are as in 402.4 Eq. 3. ΔFU = 0 if use is not significantly different.

**Eq. 4, p. 18**
```
FU_{i,y,a} = Σ_MT FUL_{i,y,MT,a} × FEF_{i,y,MT}
```
FU_i,y,a [tCO2e ha-1 as printed]. FUL [litres]. FEF [tCO2e litres-1]. MT = gasoline two-stroke, gasoline four-stroke, diesel. i = BL/PR. The 5-yr baseline mean, the fuel-efficiency fallback, the 50% cap and the note that non-CO2 is negligible are the same as in 402.4.

**Eq. 5, p. 18**
```
EU_{i,y,a} = Σ_SE EUW_{i,y,SE,a} × EEF_{i,y,SE}
```
EU_i,y,a [tCO2e ha-1 as printed]. EUW [kWh]. EEF [tCO2e kWh-1]. SE = grid, fossil fuel generator, etc. On-site fossil generation "should be calculated" as fuel. EU_BL is capped at 50% of EU_PR if undocumented.

**Eq. 6, p. 19: seed production and transport (new in 402.6)**
```
ΔSPT_{t-o} = Σ_y [ Σ_{a=1}^{T} ( SPT_{PR,y,a} ) ]
```
(Subscript printed as "t-o".) 10.4.1: baseline SPT = 0 because cover crops are not allowed in the baseline, "Change in emissions SPT_t-0 thus equals emissions from seed production and transport in the project scenario SBT_PR".

**Eq. 7, p. 19**
```
SPT_{PR,y,a} = Σ_c [ ( S_{PR,y,a,c} × A_{PR,y} ) × ( EF_{SP,y,c} + EF_{ST,y,c} × DistST_{PR,y,a,c} ) ]
```
| Symbol | Definition | Unit |
|---|---|---|
| SPT_PR,y,a | Emissions from seed production and transport in stratum y in year a of the project scenario | tCO2e |
| S_PR,y,a,c | Amount of seed for crop c applied in stratum y in year a of the project scenario | kg ha-1 |
| A_PR,y | Area in stratum y in the project scenario | ha |
| EF_SP,y,c | Emission factor for production of seed for crop c applied in stratum y in year a of the project scenario | tCO2e kg-1 |
| EF_ST,y,c | Emission factor for transport of seed for crop c applied in stratum y in year a of the project scenario | tCO2e km-1 kg-1 |
| DistST_PR,y,a,c | Transport distance for seed for crop c applied in stratum y in year a of the project scenario | km |

Rules (pp. 19-20):
- S: monitored per stratum. For pre-mixed seeds, conservative documented expert opinion may be used per species.
- EF_SP: documented. If unavailable, conservative defaults (EFs or LCA for related crops).
- EF_ST: documented if not already in the EF_SP LCA. National values specific to the transport means are used. Otherwise conservative defaults, e.g. from the GHG Protocol (footnote 6: "Emission Factors from Cross-Sector Tools" or "GHG Emissions from Transport or Mobile Sources", ghgprotocol.org, accessed June 2021).
- Dist: GIS/map distance from production to field. Use the stratum average weighted by field size. If EF_SP includes transport to distribution centres, only the remaining distance is counted. Air, sea and ground legs are calculated separately with their respective EFs.

**Eq. 8, p. 20:** identical form to 402.4 Eq. 6
```
ΔAE_{t-0} = Σ_y [ Σ_{a=1}^{T} ( AE_{PR,y,a} − AE_{BL,y} ) ]
```
ΔAE_t-0, AE_PR,y,a and AE_BL,y in tCO2e. T in yr. ΔAE = 0 if not significantly different.

**Eq. 9, p. 21:** identical form to 402.4 Eq. 7
```
AE_{i,y,a} = Σ_ET AQ_{i,y,ET,a} × AEF_{i,y,ET}
```
AE_i,y,a [tCO2e ha-1 as printed]. AQ [kg]. AEF [tCO2e kg-1]. ET = specific pesticide, fertiliser, or other agrochemical. AE_BL is capped at 50% of AE_PR if undocumented.

**Eq. 10, p. 22: stratum-level leakage (replaces SOC FM Eq. 19)**
```
LK_{t-0} = Σ_y [ (CY_{min,y} − CY_{t,y}) / CY_{BL,y} × Ā_{y,t} ] × ( ΔBC_LA + ΔSOC_{LA,t-0} + ΔFE_{LA,t-0} + ΔFU_{LA,t-0} )
```
**No max[...; 0] operator is printed** here, unlike 402.4 Eq. 8.
| Symbol | Definition | Unit |
|---|---|---|
| LK_t-0 | emissions due to shift of production to non-project lands (leakage area) | tCO2e |
| CY_t,y | crop yield in stratum y at time t (5 year average*) | kg ha-1 |
| CY_min,y | lowest crop yield in stratum y in any calculation period since project start (5 year average*) | kg ha-1 |
| CY_BL,y | crop yield in stratum y under the baseline scenario (5 year average*) | kg ha-1 |
| Ā_y,t | eligible project area in stratum y (5-year average*) | ha |
| ΔBC_LA | change in biomass carbon stocks in leakage area | tCO2e ha-1 |
| ΔSOC_LA,t-0 | change in soil organic carbon stocks in leakage area | tCO2e ha-1 |
| ΔFE_LA,t-0 | change in emissions from use of fertiliser in leakage area | tCO2e ha-1 |
| ΔFU_LA,t-0 | change in emissions from fuel use in leakage area | tCO2e ha-1 |

\* "If the baseline period is extended to cover full rotation cycles, crop yield and stratum area shall be calculated as the average across an equal length period."

### 3.3 Default factors / tables

- **No numeric SOC stock change factors, tillage factors, input factors, SOC_REF or climate/soil tables are printed.** Approach 3.1 *requires* national/regional Tier 2 SOC_REF and stock change factors (IPCC global defaults are not sufficient because IPCC has no cover-crop factor) (p. 11).
- **Table 6-01: Key References to IPCC 2019 Steady State Method (p. 13):**

| Topic | Reference IPCC 2019, Vol. 4, Chapter 5 |
|---|---|
| Description of Steady State Method | Pages 5.15 to 5.18 |
| Step-by-step procedure | Pages 5.23 to 5.26 |
| Equations for Steady State Method | Pages 5.18 to 5.23 |
| Default value table for model parameters | Table 5.5A, page 5.31 |
| Default value table for nitrogen and lignin contents in crops | Table 5.5B, page 5.32 |
| Default value table for carbon to nitrogen ratios and lignin contents in livestock manure | Table 5.5C, page 5.33 |
| Tier 2 Steady State Method spreadsheet (MS Excel) | Separate tool (footnote 3: https://www.ipcc-nggip.iges.or.jp/public/2019rf/pdf/4_Volume4/Vol4_Ch5_Tier2_Steady_State_Method-Spreadsheet.xlsx) |

  (The PDF layout places "Separate tool3" on the line after the Table 5.5C row. Pairing it with the spreadsheet row is inferred from layout and footnote 3.)
- **EF_FE = 0.01 tCO2e kgN-1** (IPCC 2019 Vol. 4 Table 11.1 aggregated), pp. 17 and 26.
- **Uncertainty defaults (9.1.2, p. 15):** SE = 50% if unknown. t = 3. Constants are exempt. EF_ST: uncertainty from the parameter source, otherwise "conservatively assumed to be 50%" (p. 27).
- **50% caps** for undocumented FE_BL, FU_BL, EU_BL, AE_BL (pp. 17-21).
- **Thresholds:** 5% significance for other emissions. Non-cover-crop organic C inputs may change by no more than 5% (3.1.3). Herbicide use may increase by no more than 5% (3.1.4). Prior cover cropping of no more than one season in the 5 years before start (3.1.2).
- **EEF sources (pp. 27-28):** national GHG inventories (U.S. EPA; EU EMEP/EEA 2023), otherwise IPCC 2006 Vol 2 Ch 3 Table 3.3.1. (Unlike 402.4, there is no TOOL05, AMS-I.F. or renewable = 0 rule.)
- **FEF sources (p. 30):** national GHG inventories (U.S. EPA; Canada; EU EMEP/EEA 2023), otherwise IPCC 2006 Vol 2 Ch 3 Table 3.3.1.

### 3.4 Monitoring parameters (Section 12, pp. 22-31)

12.1.1: SOC FM monitoring, plus evidence that applicability conditions are met at all times. 12.1.2: module definitions override overlapping FM parameters. Approach 3.2 also requires that all steady-state input parameters be monitored and reported with source and rationale (6.4.3).

| Parameter | Unit | Description | Source | Frequency | Used in / notes |
|---|---|---|---|---|---|
| A_PR,y | ha | Area in stratum y in the project scenario | Farm records (GPS data, GIS files) | At project start; reviewed annually | Eq. 7 |
| Ā_y,t | ha | Area in stratum y at time t (five-year average*) | Farm records (GPS data, GIS files) | Annually (for 5-yr average) | Eq. 10 |
| AQ_i,y,ET,a | Km (as printed; Eq. 9 says kg) | Quantity of agrochemicals in stratum y for emitter type ET applied in year a | Farm records | Annually | Eq. 9. Non-N-fertiliser agrochemicals used for cover crops (e.g. termination). |
| AEF_i,y,ET | tCO2e kg-1 | Emissions factor of the agrochemical used in stratum y (for emitter type ET) | Supplier information | Annually | Eq. 9. Supplier LCA, otherwise national/international defaults or third-party EFs. |
| CY_BL,c,y | kg ha-1 | Average annual crop yield for crop type c per ha in stratum y in the project area during the baseline period (five-year average) | Farm records, e.g. field records, sales receipts | Project start | Replaces CY_BL of SOC FM Eq. 19 |
| CY_t,y | kg ha-1 | Average annual crop yield per ha in stratum y in the project area (five-year average*) | Farm records | Annually | Eq. 10. Replaces CY_t of FM Eq. 19. "If cover crops are partially grazed or harvested (e.g., as feed or biomass crop), this yield may be included in CY_t,y and, as relevant in quantification Approach 2 or 3, may be deducted from organic inputs to the soil (i.e., the respective model parameter)." |
| CY_min,y | kg ha-1 | Minimum annual crop yield per ha in stratum y since project start | Farm records | Annually | "Used in Equation 8" (as printed; should be Eq. 10). Replaces CY_min of FM Eq. 19. |
| DistST_PR,y,a,c | km | Transport distance for seed for crop c applied in stratum y in year a of the project scenario | GIS/map distances | Annually | Eq. 7. Stratum average weighted by field size. Separate legs by transport mode. |
| EF_FE,y | tCO2e kgN-1 | Conversion factor for emissions from N fertiliser in stratum y | IPCC 2019 | Project start | Eq. 2. Value 0.01. |
| EF_SP,y,c | tCO2e kg-1 | Emission factor for production of seed for crop c applied in stratum y in year a of the project scenario | Seed producer information/product information | Project start; updated annually | Eq. 7. QA/QC: "The seed production emission factors shall be assessed by an expert who shall be part of the VVB team at project validation." |
| EF_ST,y,c | tCO2e km-1 kg-1 | Emission factor for transport of seed for crop c applied in stratum y in year a of the project scenario | National transport emission factors | Project start; reviewed annually | Eq. 7. Uncertainty from source, otherwise 50%. |
| EEF_i,y,SE | tCO2e kWh-1 | Emissions factor for the electricity used in stratum y in source SE | National GHG inventories, otherwise IPCC 2006 Vol 2 Ch 3 Table 3.3.1 | Project start; reviewed annually for national updates | Eq. 5 |
| EUW_i,y,SE,a | kWh | Electricity consumption in stratum y from source SE in year a | Farm records | Use-based, aggregated (sum) per year | Eq. 5. Electricity used for cover cropping (direct records, or hours times kW). |
| FE_BL,y | kgN | Mean annual N fertiliser input in stratum y under the baseline scenario | Farm records (field level) | Project start | Eq. 2 |
| FE_PR,y,a | kgN | N fertiliser input in stratum y under the project scenario in year a | Farm records (field level) | Use-based; aggregated annually | Eq. 2 |
| FEF_i,y,MT | tCO2e liters-1 | Emissions factor for the fuel used in stratum y in machinery MT | National GHG inventories, otherwise IPCC 2006 Table 3.3.1 | Project start; reviewed annually for national updates | Eq. 4 |
| FUL_i,y,MT,a | Liter | Fuel consumption in stratum y by the machinery type MT used in year a | Farm records | Baseline: project start. Project: use-based, summed per year. | Eq. 4. Fuel for cover cropping (direct records, or hours/distance times l/h or l/km). |
| S_PR,y,a,c | kg ha-1 | Amount of seed for crop c applied in stratum y in year a of the project scenario | Farm records | Use-based, aggregated (sum) per year | Eq. 7. Per cover crop type. Expert opinion allowed for pre-mixes. |

Approach-dependent SOC data: Approach 1 needs SOC stock sampling with bulk density on an equivalent-mass basis. Approach 2 needs verification sampling at project start and at least every 5 years per stratum. Approach 3.1/3.2 needs activity data (crop yields/volumes, residues, cover crop biomass inputs, manure/compost, tillage) plus Tier 2 parameters.

Note: unlike 402.4, the 402.6 monitoring list has **no** ΔBC_LA or ΔSOC_LA,t-0 tables, although both are used in Eq. 10.

### 3.5 Uncertainty, leakage, permanence

- **Uncertainty (9.1, p. 15):** SOC FM rules, plus SE = 50% default and t = 3. Approach 3.2 recommends a min/max sensitivity analysis (p. 12).
- **Leakage (11.1, pp. 21-22):** SOC FM rules, calculated per stratum with Eq. 10 instead of FM Eq. 19. Yield reduction detected in a performance certification means the lost production is assumed to be displaced. 402.6 has no explicit 5% yield threshold and no 3-year exemption (both are in 402.4).
- **Permanence-related rules:** 10-year crediting period, renewable once (5.2.1). Participating fields are fixed (5.1.2). There is no explicit "no reversal" clause (unlike 402.4 2.2.2g) and no buffer section, so the SOC FM / GS product requirements apply.

### 3.6 Ambiguities (402.6)

1. p. 22, Eq. 10: no max[...; 0] operator, so a yield *increase* would give negative leakage. This conflicts with the SOC FM ban on positive leakage (stated in 402.4 11.1.1). 402.4 Eq. 8 includes max[...; 0]. Transcribed as printed.
2. p. 17, Eq. 3: same bracketing issue as 402.4 Eq. 3 (the EU term is outside Σ_a).
3. pp. 18-21, Eqs. 4, 5, 9: FU/EU/AE are in tCO2e ha-1 while the inputs give tCO2e. Same unit inconsistency as 402.4.
4. p. 23: AQ_i,y,ET,a unit printed "Km". Eq. 9 says kg.
5. p. 25: CY_min,y table says "Used in Equation 8". It is used in Eq. 10 (Eq. 8 is ΔAE).
6. p. 24 vs p. 22: the monitoring table defines **CY_BL,c,y** (per crop type c), but Eq. 10 uses **CY_BL,y** with no crop index. How crop-specific baseline yields are aggregated is not stated.
7. p. 19: ΔSPT subscript printed "t-o". 10.4.1 refers to "SBT_PR" (should be SPT_PR). p. 20 uses "Dist_PR,y,a,c" and "EF_ST,t,0", which are inconsistent with DistST_PR,y,a,c and EF_ST,y,c. EF_SP and EF_ST are defined "in year a" but carry no *a* subscript.
8. p. 4: the reduced-tillage definition cites "IPCC 2019, Volume 4, Chapter 4, Section 5.2.3.3". The full-tillage definition cites Chapter 5. Chapter 4 is probably a typo for Chapter 5.
9. pp. 9-10: no SOC sampling depth is stated for Approach 1 (402.4 states 50 cm "in line with the SOC Framework Methodology"). The FM default presumably applies, but this is not verified here.
10. p. 11, 6.4.1: Approach 3 offers "two alternative calculations in addition to the IPCC Tier 1/2 approach as listed in the SOC FM". But 6.4.2 then requires Tier 2 national/regional factors, so whether a plain FM Tier 1 calculation is still allowed for cover crops is unclear.
11. p. 11, 6.4.2: the reference to "Equations 4 and 6 of the Soil Organic Carbon Framework Methodology" needs to be checked against FM numbering (FM not transcribed here).
12. p. 13, Table 6-01: the row alignment of "Separate tool" vs the spreadsheet row is inferred from layout.
13. p. 6, 3.1.2: "more than one season within five years" does not define "season" (cropping season vs calendar season).
14. p. 25, CY_t,y: harvested or grazed cover crop yield "may be included" in CY_t,y. This contradicts the definition (p. 4) that "A cover crop is not harvested, and biomass is not removed from a field".
15. pp. 27-28, EEF: 402.6 drops the TOOL05/AMS-I.F./renewable = 0 provisions present in 402.4, with no rationale given.
16. 8.1 and 9.1 vs 5.4.2: "CO" and "NO" are probably CO2 and N2O (subscripts lost in print).

---

## Comparison table: soil sampling vs activity data and defaults

| Item | 402.1 Improved Tillage | 402.4 Zero Tillage | 402.6 Cover Crops |
|---|---|---|---|
| Approach 1 (on-site SOC measurement) | Allowed | Allowed (main focus) | Allowed |
| Approach 2 (models / research data) | Allowed (peer-reviewed, conservative, applicable) | Allowed, with local calibration (5 yr calib + 3 yr verif.) and **mandatory verification SOC sampling at start and at least every 5 yrs** | Allowed, with local calibration (5 + 3 yr) and **mandatory verification SOC sampling at start and at least every 5 yrs** |
| Approach 3 (defaults / IPCC) | Allowed: IPCC impact factors (F_MG) with project-oriented SOC_REF | **Not allowed** | Allowed as 3.1 (FM Approach 3 with **Tier 2 national/regional SOC_REF and factors only**) or 3.2 (IPCC 2019 Tier 2 Steady State Method) |
| Can a project avoid soil sampling entirely? | **Yes**, via Approach 3 (activity data + F_MG + project SOC_REF) or Approach 2 | **No**. Approach 1 is sampling. Approach 2 requires periodic verification sampling. | **Yes**, via Approach 3.1/3.2 (activity data + Tier 2 parameters). Approach 2 requires sampling. |
| Sampling depth stated | Not stated (FM applies) | 50 cm | Not stated (FM applies) |
| Equivalent-mass / bulk density rule | Not stated | Yes (5.2.1e) | Yes (6.2.1) |
| Module-printed numeric SOC factors | None (F_MG values blank). Only non-binding Table A-01 accumulation rates (tCO2e ha-1 yr-1). | None | None (only IPCC 2019 page/table references, Table 6-01) |
| Module-specific activity-data parameters | F_MG,BL,y (project start), F_MG,PR,y (annual) | CY, Ā, FE, FUL/FEF, EUW/EEF, AQ/AEF, ΔBC_LA, ΔSOC_LA | CY, Ā, A_PR, FE, FUL/FEF, EUW/EEF, AQ/AEF, S/EF_SP/EF_ST/DistST (seed) |
| Module-specific project-emission equations | None (FM Eqs. 12-18 area-wide) | Eqs. 1-7 (stratum-level, replace FM 12-18) | Eqs. 1-9 (stratum-level incl. seed SPT, replace FM 12-18) |
| Leakage | FM. LK = 0 initially, yield-based if reduced. | Eq. 8 (stratum, with max[...;0]). >5% yield-reduction trigger. 3-yr exemption. | Eq. 10 (stratum, no max printed) |
| Crediting period | 10 yr fixed, not renewable | max 10 yr, renewal at year 5 | 10 yr, renewable once |
| Uncertainty defaults | FM only | SE 50%, t = 3 | SE 50%, t = 3. EF_ST uncertainty 50% fallback. |
