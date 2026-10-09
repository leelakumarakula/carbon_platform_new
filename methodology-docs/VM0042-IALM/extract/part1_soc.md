# VM0042 v2.2 (with June 2026 C&C tracked changes): Part 1, Section 8.1 to 8.2.1.6 (PDF pages 23 to 41)

Source: `VM0042_v2.2_with_CC_tracked.pdf`, read from rendered page images. Where tracked changes appear, the corrected (new, underlined green) text is used. Page numbers are the printed page numbers, which match the PDF page index here.

The tracked changes on these pages are mostly cross-reference renumbering ("Table 5", "Table 6", "Table 7", "Table 8", "Equations (48) and (49)"). They do not change any equation. The changes that matter are:
- p.23: "When dividing the project area into multiple quantification units, estimates of ERRs ... are then aggregated". In the same paragraph, "project description document" becomes "project description".
- p.23: New paragraph on grouped projects and eligibility areas (see §1).
- p.38: New text on method changes / conversion factors (see §3).

---

## 1. Structure of the quantification

**§8.1 Summary (p.23)**
- Baseline and project emissions are defined as flux of CH4, N2O and CO2 in **t CO2e per unit area per verification period**. Footnote 14: "for reporting purposes, hectares should be used as the unit area".
- Within each quantification unit, stock and emission changes in each included pool or flux are handled **per unit area**.
- Section 8.5 turns total stock and emission changes into net reductions and removals. Where a verification period spans more than one calendar year, reductions and removals are quantified **by year** to set vintages.
- The project area is divided into **quantification units** that must be shown to be more homogeneous than the whole project area (similar management, soil type, climate). The whole project area may be a single quantification unit. When there are several units, the per-unit ERR estimates are **aggregated** to the project area.
- A staged (hierarchical or nested) design may use primary, secondary, tertiary and further units (Appendix 6 has an example). Units must be defined in the sampling design description in the project description.
- New C&C text: "In grouped projects, the determination of different eligibility areas [15a: Geographic area per VCS Standard, v4.7 and previous versions] may be treated independently from potential division into quantification units. Thus, quantification units may span across multiple eligibility areas or represent subdivisions of one eligibility area."
- More than one approach may be used for a given gas and source, **provided the same approach is used for a given quantification unit in both the project and baseline scenarios**.

**Table 5: Summary of allowable quantification approaches (p.24)**

| GHG/Pool | Source | QA1: Measure and Model* | QA2: Measure and Remeasure | QA3: Default Factors |
|---|---|---|---|---|
| CO2 | SOC | X | X | |
| CO2 | Fossil fuel | | | X |
| CO2 | Liming | | | X |
| CO2 | Woody biomass** | | | |
| CH4 | Soil methanogenesis*** | X | | |
| CH4 | Enteric fermentation | | | X |
| CH4 | Manure deposition | | | X |
| CH4 | Biomass burning | | | X |
| N2O | Use of nitrogen fertilizers*** | X | | X |
| N2O | Use of nitrogen-fixing species*** | X | | X |
| N2O | Manure deposition*** | X | | X |
| N2O | Biomass burning | | | X |

- \* "Approach 1 may only be used where a valid model is available (see model requirements in VMD0053)."
- \*\* Woody biomass, where included in the project boundary, is calculated using the CDM A/R tools *Estimation of carbon stocks and change in carbon stocks of trees and shrubs in A/R CDM project activities* and *Simplified baseline and monitoring methodology for small scale CDM afforestation and reforestation project activities implemented on lands other than wetlands*. If woody biomass is harvested, the long-term average GHG benefit must be calculated following the VCS Methodology Requirements (fn16: Section 3.6.6, v4.4) and the VCS Standard (fn17: Sections 3.2.28 to 3.2.30, v4.7). p.28 adds that woody biomass is reported using **Equations (48) and (49)**, citing VCS Methodology Requirements Section 3.6 and VCS Standard Section 3.2.
- \*\*\* "Measured data on CH4 and N2O fluxes as described in VMD0053, v2.0 are required for model calibration and validation when following Quantification Approach 1. Periodic measurements of CH4 and N2O fluxes as part of project monitoring is not required."

**Rules for applying the approaches (p.24)**
- Parts of the project area that use different approaches for a pool or source must be **stratified and accounted separately**.
- A project **may switch** between allowable approaches for a source during the project lifetime, provided the same approach is used for both project and baseline.

**Approach descriptions (pp.24 to 26)**
- **QA1, Measure and Model.** A model estimates GHG flux from soil characteristics, implemented ALM practices, measured initial SOC stocks and climate in each quantification unit. SOC stocks are measured **every five years or more frequently** (Table 8). These remeasurements are used to re-estimate model prediction error and recalibrate the model ("true-up", §8.6.1.3). CH4 and N2O fluxes need no initial or periodic measurement in monitoring. High-quality observed experimental data from controlled trials or approved sources (VMD0053) are needed for model calibration (VMD0053 §5.1) and validation (VMD0053 §5.2.3). These data must come from peer-reviewed published datasets, ideally with control plots. They may instead come from a third-party benchmark database, or from measurements inside the project boundary where the independent modeling expert (IME) approves (VMD0053 Appendix 1).
- **QA2, Measure and Remeasure.** SOC stock change is quantified by direct measurement. It is used where models are unavailable, not validated or not parameterized, or where the proponent prefers it. The baseline is measured and remeasured directly at **baseline control sites** linked to one or more quantification units. **QA2 applies only to SOC.**
- **QA3, Default Factors.** GHG flux is calculated following the 2019 Refinement to the 2006 IPCC Guidelines, using the equations in this methodology. If an activity is not practised in the baseline or project, so that an equation element is zero, that element is not required. Baseline and project emissions are calculated **for each sample field**. Emission factors are chosen in this descending order of preference:
  1. A project-specific EF from a peer-reviewed publication. Fn18 requires a journal indexed in the Web of Science Science Citation Index, per VCS Methodology Requirements §2.5.2.
  2. Alternative sources such as government databases or industry publications, with evidence that the source is robust and credible (e.g. independent expert attestation).
  3. Tier 2 EFs derived from project activity data, following the 2019 Refinement guidance.
  4. Where the project justifies a lack of activity data and project-specific sources, Tier 1 and Tier 1a EFs from the 2019 Refinement.
- Project proponents must use the VM0042 webpage templates: the ERR quantification spreadsheet, the model validation report and the IME assessment report (p.26).

**Figure 1: Equation map (p.27)**
- QA1: CO2-SOC uses Eqs. 3-5 and 46-47. CH4 soil methanogenesis uses Eqs. 10 and 54. N2O from N fertilizers, manure deposition and N-fixing species uses Eqs. 15 and 58.
- QA2: CO2-SOC uses Eqs. 3 and 46-47.
- QA3:
  - CO2: fossil fuel Eqs. 6-7 and 52; liming Eqs. 8-9 and 53.
  - CH4: enteric fermentation Eqs. 11 and 55; manure deposition Eqs. 12-13 and 56; biomass burning Eqs. 14 and 57.
  - N2O: N fertilizers Eqs. 16-23 and 58; manure deposition Eqs. 16, 26-31 and 58; N-fixing species Eqs. 16, 24-25 and 58; biomass burning Eqs. 32 and 59.

**§8.2 Baseline Emissions: baseline versus project logic (pp.28 to 31)**
- **QA1:** The baseline is **modeled** for each quantification unit, using the baseline schedule of ALM activities from Section 6. Table 6 gives guidance on model inputs.
- **QA2:** Baseline SOC is **measured and remeasured at control sites** managed under the baseline schedule (Section 6). Control sites must meet the Table 7 similarity criteria.
- **QA3:** The baseline is **calculated per sample field** with default EFs. Data are determined per sample field at validation.
- **§8.2.1 (p.31):** Under QA1, SOC stocks are measured directly as model inputs for the baseline and then at least every five years for true-up. Under QA2, they are measured at the project start date and at each verification event, for both baseline and project. Under QA1, the initial SOC stock (t = 0, measured directly or (back-)modeled to t = 0 from measurements within ±5 years) is **the same in baseline and project**: SOC_wp,i,0 = SOC_bsl,i,0.

**Table 6: Biophysical model inputs for the baseline (QA1) (pp.28 to 29)**

| Model input | Timing | Approach |
|---|---|---|
| SOC content to calculate SOC stocks (initial) | Determined before project intervention by direct measurement at t = 0, or (back-)modeled to t = 0 from measurements collected within ±5 years of t = 0 | Measured directly by conventional laboratory methods (e.g. dry combustion) or proximal sensing (e.g. INS, LIBS, MIR, Vis-NIR) with known uncertainty, following the Appendix 4 criteria, at t = 0. Alternatively (back-)modeled to t = 0 following VMD0053. See the parameter table for SOC̄_bsl,i,t (printed with an overbar). |
| Bulk density to calculate SOC stocks (initial) | Determined before project intervention by direct measurement at t = 0, or from measurements collected within ±5 years of t = 0 | See Section 8.2.1.5 |
| Soil properties (other than bulk density and SOC) | Determined before project intervention | Measured directly or taken from published soil maps with known uncertainty. Estimates from direct measurement must be derived from representative (unbiased) sampling and must be accurate through adherence to best practice. |
| Climate variables (e.g. precipitation, temperature) | Continuously monitored ex post | Measured for each model-specific meteorological input at its required temporal frequency (e.g. daily) for the model prediction interval. Taken at the closest continuously monitored weather station not more than 50 km from the sample field, or from a synthetic weather station (e.g. PRISM). |

---

## 2. Equations (4 equations on pages 23 to 41)

### Equation (1): §8.2.1.3, item 11 (p.37). Minimum detectable difference (power analysis, FAO 2019)

Printed:

$$MDD \geq \frac{S}{\sqrt{n}} \times \left(t_{\alpha,\upsilon} + t_{\beta,\upsilon}\right)$$

Plain text: `MDD >= S / sqrt(n) * (t_{alpha,v} + t_{beta,v})`

The second subscript is printed as an italic glyph that looks like "υ" or "v". It is most likely ν (degrees of freedom), but it is **not defined** in the Where list.

### Equation (2): §8.2.1.3, item 11 (p.38). Required number of samples

$$n \geq \left(\frac{S \times (t_{\alpha} + t_{\beta})}{MDD}\right)^{2}$$

Plain text: `n >= ( S * (t_alpha + t_beta) / MDD )^2`

The Where list below is shared by Eqs. (1) and (2):

| Variable | Definition (as printed) | Unit |
|---|---|---|
| MDD | Minimum detectable difference | not stated |
| S | Standard deviation of the difference in SOC stocks between t0 and t1 | not stated |
| n | Number of samples | not stated (count) |
| tα | Two-sided critical value of the t-distribution at a given significance level (α) frequently taken as 0.05 (5%) | dimensionless |
| tβ | One-sided quartile of the t-distribution corresponding to a probability of type II error β (e.g., 90%) | dimensionless |

Use of Eqs. (1) and (2) is **optional**: "A power analysis may be conducted ... However, projects are not required to take this number of samples."

### Equation (3): §8.2.1.6 (p.40). SOC mass per sample and depth layer (Wendt & Hauser, 2013)

$$M_{n,dl,SOC} = \left(\frac{M_{n,dl,sample}}{\pi\left(\frac{D}{2}\right)^{2} \times N} \times 10\,000\right) \times OC_{n,dl}$$

Plain text: `M_n,dl,SOC = ( M_n,dl,sample / ( pi * (D/2)^2 * N ) * 10000 ) * OC_n,dl`

| Variable | Definition (as printed) | Unit |
|---|---|---|
| M_n,dl,SOC | SOC mass in soil sample n in depth layer dl | kg/ha |
| M_n,dl,sample | Soil mass of sample n in depth layer dl | g |
| D | Inside diameter of probe or auger | mm |
| N | Number of cores sampled | unitless |
| OC_n,dl | Organic carbon content in sample n in depth layer dl | g/kg |
| 10 000 | Conversion factor from g/mm² to kg/ha | (constant) |

Unit check, worked against Figure 3, VM42point1-1:
- 283.2 g / (π × 10.75² × 4 = 1452.2 mm²) = 0.19501 g/mm².
- × 10 000 = 1950. This matches cell F15 "1950 Mg/ha", so the bracketed term is in **Mg/ha**.
- × 24.29 g/kg = 47 368 kg/ha ≈ 47.36 Mg/ha. This matches cell H15.

The equation is therefore internally consistent and gives kg/ha with OC in g/kg. However, 1 g/mm² is actually 10^7 kg/ha. The "10 000" is a combined factor: g/mm² to Mg/ha, or equivalently g/mm² to kg/ha together with g/kg to a fraction. **Do not use the bracketed term as soil mass in kg/ha.** See §5.

After Eq. (3), the cumulative SOC mass per unit area is the sum over all sampled depth increments (Figure 3, column H). The ESM adjustment then follows Wendt & Hauser or von Haden (see §4).

### Equation (4): §8.2.1.6 (p.41). SOC stock as a model input (QA1 only, optional)

$$SOC_{model} = 100 \times BD_{corr} \times d \times OC_{n,dl}$$

Plain text: `SOC_model = 100 * BD_corr * d * OC_n,dl`

| Variable | Definition (as printed) | Unit |
|---|---|---|
| SOC_model | SOC stock as model input data | t/ha |
| BD_corr | Corrected bulk density of the fine soil fraction, after subtracting the mass proportion of the coarse fragments | g/cm³ |
| d | Soil depth | cm |
| 100 | Conversion factor from g/cm² to t/ha | (constant) |
| OC_n,dl | **Not defined in Eq. 4's Where list.** It appears to reuse the Eq. 3 definition (g/kg), but see §5 on units. | (see §5) |

Context: "under Quantification Approach 1, SOC stocks for model initialization may be calculated using Equation (4) where models use SOC stocks as an input rather than ingesting SOC content and bulk density values separately." Where models need bulk density inputs, bulk density is measured per §8.2.1.5.

---

## 3. Defaults, constants, thresholds and rules affecting calculation

| Rule / value | Section | Page |
|---|---|---|
| Reporting unit area is the hectare (fn14) | 8.1 | 23 |
| Results are reported per verification period and split by calendar year (vintage) | 8.1 | 23 |
| Same approach must be used in baseline and project for a given quantification unit and source | 8.1, Table 5 text | 23-24 |
| Areas using different approaches must be stratified and accounted separately | 8.1 | 24 |
| QA1: SOC remeasured every **5 years** or more often (true-up, §8.6.1.3, Table 8) | 8.1, 8.2.1 | 24, 31 |
| QA1: initial SOC/BD measured at t = 0 or within **±5 years** of t = 0 (back-modeled); SOC_wp,i,0 = SOC_bsl,i,0 | Table 6, 8.2.1 | 28, 31 |
| QA1: weather station no more than **50 km** from the sample field, or a synthetic station (PRISM) | Table 6 | 29 |
| QA2: control sites within **250 km** of linked quantification units | 8.2 QA2 | 29 |
| QA2: **at least 3 control sites** across the project area (more decreases uncertainty, especially if fewer than 10) | 8.2 QA2 | 29 |
| QA2: **at least 1 control site per stratum**, or the control site is divided into the same strata as the quantification unit | 8.2 QA2 | 29 |
| QA2: one control site may link to more than one quantification unit if it meets the criteria for each | 8.2 QA2 | 29 |
| QA2: control site **location fixed** for the project lifetime (management may change); edge effects eliminated | 8.2 QA2 | 29 |
| Baseline SOC stocks reported for the control sites **and** for each stratum in the project area | 8.2 QA2 | 29 |
| Table 7 topography: same most frequent slope class (Appendix 5, Table 10); for hilly, steep or very steep land, aspect within **30°** of the cardinal direction | Table 7 | 30 |
| Table 7 texture: same FAO textural class, to project boundary depth (**min 30 cm**); determine separately by horizon if texture differs within 0-30 cm | Table 7 | 30 |
| Table 7 soil group: same WRB reference soil group | Table 7 | 30 |
| Table 7 SOC %: not significantly different from the unit mean at **90% confidence**, to project boundary depth (**min 30 cm**) | Table 7 | 30 |
| Table 7 historical ALM: same for **at least 5 years** before project start (tillage Y/N and type, residue removal, crop planting and harvesting/crop type, manure, compost, irrigation) | Table 7 | 30 |
| Table 7 historical land cover: for lands converted up to **50 years** before start, same major land cover type within **±10 years** | Table 7 | 31 |
| Table 7: same terrestrial ecoregion (WWF) and same IPCC climate zone | Table 7 | 31 |
| Table 7 precipitation: mean annual within **±100 mm**; station no more than **50 km** away, or synthetic | Table 7 | 31 |
| Table 7 fn e: if the crop type cannot be matched, a crop from the same crop functional group (VMD0053 definition) may be used | Table 7 | 31 |
| Sampling design: **stratified random sampling required**; in multi-stage designs it must be used in the stage directly before the sample point stage; alternatives only via methodology deviation | 8.2.1.2 | 33 |
| Strata generated at the **lowest level** quantification unit | 8.2.1.2 | 33 |
| Grid or linear sampling is not recommended | 8.2.1.2 | 33 |
| Strata, their areas and sampling points reported in a spreadsheet annex at every verification | 8.2.1.2 | 33 |
| **At least 3-5 composite samples per stratum** for model true-up (QA1) or under QA2 | 8.2.1.2 | 34 |
| Resampling in the **same season**; locations georeferenced | 8.2.1.1 | 32 |
| Composited cores from the same depth, fully homogenized | 8.2.1.3 (2) | 36 |
| Particles **> 2 mm** excluded (2 mm sieve) from soil mass and bulk density | 8.2.1.3 (4), 8.2.1.5 | 36, 39 |
| Samples shipped within **5 days** of campaign end; refrigerated storage **no more than 3 months**; not frozen | 8.2.1.3 (5) | 36 |
| SOC stock changes from measurements (QA1 and QA2) reported on an **ESM basis** | 8.2.1.3 (7), 8.2.1.6 | 36, 39 |
| SOC reported to a **minimum depth of 30 cm**, or to bedrock/hardpan if shallower; sample deeper than 30 cm to avoid extrapolation | 8.2.1.3 (7b) | 36-37 |
| At resampling, **at least two depth increments** | 8.2.1.3 (7c) | 37 |
| Recommended **0-30 cm and 30-50 cm** (to 50 cm) | 8.2.1.3 (7e) | 37 |
| Soil mass is needed for each increment separately; SOC analysis may use one mixed sample | 8.2.1.3 (7e) | 37 |
| Soils shallower than 30 cm: sample to the impeding layer and report SOC only to the sampled depth (this affects ESM layers, fn32) | 8.2.1.3 (8) | 37 |
| Record both intended and actual sampling point locations | 8.2.1.3 (9) | 37 |
| Pre-sampling of **5 to 10 samples per stratum** to estimate variance (optional) | 8.2.1.3 (10) | 37 |
| α frequently 0.05; β e.g. 90% (Eqs. 1-2) | 8.2.1.3 (11) | 38 |
| SOC by dry combustion (Dumas). Allowed proximal sensing: NIR, Vis-NIR, MIR, LIBS, INS (Appendix 4) | 8.2.1.4 | 38 |
| Walkley-Black and LOI not recommended; allowed only where no other method is available | 8.2.1.4 | 39 |
| Same laboratory for the whole project where possible (ISO/IEC 17025 preferred). A change of lab needs justification and consistent methods | 8.2.1.4 | 38 |
| **C&C (new):** "Where the project adopts a new eligible method when adopting a new version of the methodology (e.g., a proximal sensing method per Appendix 4), project proponents or their technical service providers must demonstrate the comparability of previous measurements with new remeasurements, and, where necessary, justify the use of conversion factors." | 8.2.1.4 | 38 |
| Remote sensing / digital soil mapping allowed (QA1 initialization/true-up, QA2 mapped predictions) under **VT0014** | 8.2.1.4 | 39 |
| Bulk density by core, excavation or clod methods (ISO 11272:2017); coarse fraction may be estimated by sieving and weighing × average coarse density | 8.2.1.5 | 39 |
| BD, dry soil mass and SOC samples taken at the same time, within a few meters of the previous point | 8.2.1.5 | 39 |
| ESM reference mass must cover the **highest measured soil mass** (densest sample) | 8.2.1.6 | 40-41 |
| ESM worked example: reference layers 0-1950 Mg/ha and 1950-3253 Mg/ha. 0-1950 Mg/ha is the ≥30 cm reporting layer; the SOC values for the three points are 47.36, 49.9 and 36.8 Mg/ha. Probe diameter 21.5 mm, 4 cores per sample | 8.2.1.6, Fig. 3 | 40-41 |
| Fn36: calibration and validation datasets for QA1 modeling do **not** need to meet the ESM requirement | 8.2.1.6 | 39 |
| ESM layer values are averaged to an SOC mass for the whole quantification unit area | 8.2.1.6 | 40 |

---

## 4. Choices the project proponent must make

1. **Quantification approach** for each pool or source and quantification unit (QA1, QA2 or QA3, per Table 5). The same choice applies to baseline and project. Switching later is allowed if both scenarios still match.
2. **How quantification units are defined** (single unit or staged hierarchy), and the **strata** within the lowest-level unit. Stratification factors must be reported.
3. **ESM procedure** (§8.2.1.6, pp.39-40): Ellert & Bettany (1995), Wendt & Hauser (2013), or von Haden et al. (2020).
   - Tools: the Wendt & Hauser spreadsheet (fn37, cubic spline: https://verra.org/wp-content/uploads/2025/01/ESM-sample-spreadsheets-Wendt-and-Hauser-2013.xlsx) or the von Haden et al. (2020) R script (fn38).
   - If a template is used, a copy showing the calculation must be submitted to the VVB.
   - The **reference cumulative soil masses** (column I) must be chosen to cover the maximum measured soil mass.
4. **Depth increments** sampled (at least 2; chosen for expected loosening or compaction; 0-30 and 30-50 cm recommended).
5. **SOC analytical method**: dry combustion or an Appendix 4 proximal sensing method. A method change under a new methodology version needs a comparability demonstration and possibly conversion factors (C&C).
6. **Bulk density method**: core, excavation or clod.
7. **Number of samples per stratum**: at least 3-5 composites. The power analysis (Eqs. 1-2) is optional.
8. QA1 only: whether to feed the model SOC stock (Eq. 4) or SOC content and BD separately. Also the weather data source (station within 50 km, or synthetic).
9. QA2 only: control site selection (at least 3, within 250 km, Table 7 criteria, per stratum) and who manages them.
10. QA3 only: emission factor source, following the 4-level preference hierarchy.
11. QA/QC procedures, documented in the monitoring plan.

---

## 5. Ambiguities and external dependencies

**Ambiguities**
- **Eq. (1) subscript (p.37):** The printed subscript is "t_{α,υ}" / "t_{β,υ}" (it could be υ or v; it is probably ν, degrees of freedom). It is not defined, and Eq. (2) drops it. [Glyph identity uncertain; meaning not stated.]
- **Eqs. (1)-(2) (p.38):** No units are given for MDD or S. tβ is called a "quartile", which probably means "quantile". The example "β (e.g., 90%)" reads as statistical power (1−β) rather than the type II error probability.
- **Eq. (3) (p.40):** The factor 10 000 is labeled "g/mm² to kg/ha", but 1 g/mm² = 10^7 kg/ha. The equation only gives kg/ha because the factor also absorbs g/kg → kg/kg (10^-3). This is verified numerically against Figure 3. Implement it exactly as printed, with OC in g/kg and the output in kg/ha. Do not reuse the bracket as kg/ha soil mass (it is Mg/ha).
- **Eq. (4) (p.41):** OC_n,dl is not defined in its Where list. With the factor 100 (g/cm² → t/ha) and an output in t/ha, OC must be a **mass fraction (g/g)**. If it is entered in g/kg as defined for Eq. 3, the result is 1000× too high. The equation also uses a single depth d (not per layer), and it is not on an ESM basis (fn36 may exempt it only for calibration and validation data).
- **Figure 1 (p.27):** It maps QA1 SOC to "Eqs. 3-5" but QA2 SOC to "Eq. 3" only. Eq. 5 is outside these pages. Its relationship to the ESM procedure should be confirmed in part 2.
- **ESM computation itself:** No equation is given for the cubic-spline ESM interpolation (columns I-M in Figure 3). The procedure lives entirely in external sources (Wendt & Hauser 2013 spreadsheet, von Haden 2020 R script, Ellert & Bettany 1995). A software implementation must reproduce one of these.
- **Table 7 "not significantly different ... at a 90% confidence level" (p.30):** The statistical test is not specified.
- **"At least 3-5 composite samples" (p.34):** The binding minimum (3 or 5) is ambiguous. It is presumably 3, with 5 recommended.
- **Table 5 (p.24):** It footnotes "VMD0053, v2.0" while other text cites VMD0053 without a version.
- **QA2 SOC reporting depth:** Table 7 says "depth of project boundary (minimum 30 cm)". The project boundary depth itself is defined elsewhere (Section 5).

**External dependencies**
- **VMD0053:** model requirements, calibration (§5.1), validation (§5.2.3), IME (Appendix 1), back-modeling to t = 0, crop functional group definition (pp.24-25, 28, 31).
- **Appendix 4:** proximal sensing criteria. **Appendix 5:** slope classes (Table 10) and GIS workflow. **Appendix 6:** staged design example.
- **Table 8:** remeasurement frequency. **§8.6.1.3:** true-up. **§8.6.2:** number of samples. **§8.5:** net ERR equations. **Section 6:** baseline schedules. **§9.3:** monitoring plan.
- **Eqs. (48)-(49):** woody biomass. **CDM A/R tools:** trees and shrubs carbon; the small-scale A/R methodology.
- **IPCC 2019 Refinement to the 2006 Guidelines:** Tier 1/1a/2 EFs and IPCC climate zones.
- **VCS Standard v4.7:** §3.2.28-3.2.30, §3.20, and eligibility areas (fn15a). **VCS Methodology Requirements v4.4:** §3.6.6, §2.5.2.
- **VT0014:** digital soil mapping.
- **FAO WRB 2014:** soil groups and texture (Annex 4, Table 2). **USDA texture calculator. WWF Terrestrial Ecoregions. PRISM.**
- **ESM sources:** Wendt & Hauser (2013) spreadsheet, von Haden et al. (2020) R script, Ellert & Bettany (1995).
- **Sampling guidance:** FAO (2019, 2020), World Bank (2021) Soil Organic Carbon MRV Sourcebook (Box 3.5, Module B), ISO 18400-104, ISO 11272:2017, IPCC GPG LULUCF 2003, Beem-Miller et al. (2016).
- **VM0042 webpage templates:** ERR spreadsheet, model validation report, IME report (p.26).
