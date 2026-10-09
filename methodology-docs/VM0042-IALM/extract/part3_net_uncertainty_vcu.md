# VM0042 v2.2 (with June 2026 C&C, tracked): Part 3. Net reductions and removals, uncertainty (QA2/QA3), VCUs

Source: `VM0042_v2.2_with_CC_tracked.pdf`, PDF pages 58–66 and 81–92 (the page numbers printed on the pages match the PDF page numbers).
Equations were transcribed from rendered page images. Where the C&C tracked changes struck text and inserted new text, the **corrected (new)** text is used. Typos in the source are reproduced as printed and flagged with **[SOURCE NOTE]**. Nothing on these pages was unreadable.

Section 8.6.1 (Quantification Approach 1: modelling, Eqs. 60–69, including 8.6.1.3 Remeasurement, Model True-Up and Cumulative Modeling and Figure 4a on p.81) is **out of scope** and is not transcribed here. It is noted only because Eq. 37 (UNC for CH4/N2O soil) and Figure 6 point to it.

Conventions: `_wp` = project (with-project) scenario, `_bsl` = baseline, `t` = year (or verification period in 8.6), `i` = quantification unit, `h` = stratum, `ip` = sample point, `f`/`s` = t_final/t_start, `l` = MC simulation, `pvd` = validation-dataset point. An overbar means an areal or sample mean.

---

## 1. Equations

### 8.5 Net Reductions and Removals (pp. 58–61)

Context (p.58): the methodology lists five ways GHG emission reductions occur:
1. Carbon stocks decrease from t to t+1 in the baseline and, to a lesser extent, in the project. The cumulative project stock change is ≤ 0 (end-of-verification-period project stock ≤ stock at project start date).
2. Carbon stocks decrease in the baseline and increase in the project. "Note that this variation may also generate carbon removals as described in paragraph (2) in introduction of equation 40, below."
3. CO2 from fossil fuel combustion and liming is lower in the project.
4. CH4 from the SOC pool (soil methanogenesis), enteric fermentation, manure deposition and biomass burning is lower in the project.
5. N2O from N fertilizers and N-fixing species, manure deposition and biomass burning is lower in the project.

#### Equation (37): Emission reductions before leakage (pp. 58–59)

"GHG emission reductions before allocation of leakage emissions are quantified as:"

```
ER_t = I(ΔCO2_wp)
         × ( ΔCO2_ff_t + ΔCO2_lime_t + ΔCH4_ent_t + ΔCH4_md_t
             + ΔCH4_bb_t + ( ΔCH4_soil_t × (1 − UNC_t,CH4_soil) )
             + ( ΔN2O_soil_t × (1 − UNC_t,N2O_soil) ) + ΔN2O_bb_t
             + MIN(0, ΔCO2_wp,t) − MIN(0, ΔCO2_bsl,t) )
       + (1 − I(ΔCO2_wp)) ×
         ( ΔCO2_ff_t + ΔCO2_lime_t + ΔCH4_ent_t + ΔCH4_md_t + ΔCH4_bb_t
             + ( ΔCH4_soil_t × (1 − UNC_t,CH4_soil) )
             + ( ΔN2O_soil_t × (1 − UNC_t,N2O_soil) ) + ΔN2O_bb_t
             + MIN(0, ΔCO2_wp,t) − MIN(0, ΔCO2_bsl,t)
             + MAX(0, ΔCO2_wp,t) − MAX(0, ΔCO2_bsl,t) )
```

LaTeX:
```latex
\begin{aligned}
ER_t ={}& I(\Delta CO2_{wp}) \times \Big(\Delta CO2\_ff_t + \Delta CO2\_lime_t + \Delta CH4\_ent_t + \Delta CH4\_md_t + \Delta CH4\_bb_t \\
&+ \big(\Delta CH4\_soil_t \times (1-UNC_{t,CH4\_soil})\big) + \big(\Delta N2O\_soil_t \times (1-UNC_{t,N2O\_soil})\big) + \Delta N2O\_bb_t \\
&+ \mathrm{MIN}(0,\Delta CO2_{wp,t}) - \mathrm{MIN}(0,\Delta CO2_{bsl,t})\Big) \\
&+ \big(1 - I(\Delta CO2_{wp})\big) \times \Big(\Delta CO2\_ff_t + \Delta CO2\_lime_t + \Delta CH4\_ent_t + \Delta CH4\_md_t + \Delta CH4\_bb_t \\
&+ \big(\Delta CH4\_soil_t \times (1-UNC_{t,CH4\_soil})\big) + \big(\Delta N2O\_soil_t \times (1-UNC_{t,N2O\_soil})\big) + \Delta N2O\_bb_t \\
&+ \mathrm{MIN}(0,\Delta CO2_{wp,t}) - \mathrm{MIN}(0,\Delta CO2_{bsl,t}) + \mathrm{MAX}(0,\Delta CO2_{wp,t}) - \mathrm{MAX}(0,\Delta CO2_{bsl,t})\Big)
\end{aligned}
```

Indicator (p.59):
- I(ΔCO2_wp) = 1 if Σ_{1}^{t} ΔCO2_wp,t > 0, and
- I(ΔCO2_wp) = 0 if Σ_{1}^{t} ΔCO2_wp,t ≤ 0

| Variable | Definition (as printed) | Unit |
|---|---|---|
| I(ΔCO2_wp) | Switches on the first part of Equation (37) when the cumulative carbon stock change in the project scenario is positive, and the second part when the carbon stock change is negative | – (0/1) |
| ER_t | Estimated reductions in year t | t CO2e |
| ΔCO2_ff_t | Total GHG emission reductions from fossil fuel combustion in year t | t CO2e |
| ΔCO2_lime_t | Total carbon dioxide emission reductions from liming in year t | t CO2e |
| ΔCH4_ent_t | Total methane emission reductions from livestock enteric fermentation in year t | t CO2e |
| ΔCH4_md_t | Total methane emission reductions from manure deposition in year t | t CO2e |
| ΔCH4_bb_t | Total methane emission reductions from avoided or reduced biomass burning in year t | t CO2e |
| ΔCH4_soil_t | Total methane emission reductions from increasing uptake into the SOC pool in year t | t CO2e |
| UNC_t,CH4_soil | Uncertainty deduction in year t when using Quantification Approach 1 to model methane emission reductions from increasing uptake into the SOC pool | fraction between 0 and 1 |
| ΔN2O_soil_t | Total nitrous oxide emission reductions from nitrification/denitrification in year t | t CO2e |
| UNC_t,N2O_soil | Uncertainty deduction in year t when using Quantification Approach 1 to model nitrous oxide emission reductions from nitrification/denitrification | fraction between 0 and 1 |
| ΔN2O_bb_t | Total nitrous oxide emission reductions from avoided or reduced biomass burning in year t | t CO2e |
| ΔCO2_wp,t | Total carbon stock change in the project scenario in year t | t CO2e |
| ΔCO2_bsl,t | Total carbon stock change in the baseline scenario in year t | t CO2e |

Footnote 50 (p.58): "In this case, the project activity would decelerate the decrease in carbon stocks over time, avoiding emissions in the considered timeframe."

#### Equation (38): Net emission reductions (p.60)

```
ER_NET,t = ER_t − LK_ER,t
```
`ER_{NET,t} = ER_t - LK_{ER,t}`

| Variable | Definition | Unit |
|---|---|---|
| ER_NET,t | Estimated net GHG emission reductions in year t | t CO2e |
| LK_ER,t | Leakage allocated to GHG emission reductions in year t | t CO2e |

#### Equation (39): Leakage allocated to reductions (p.60; the C&C inserts LK_disp,t)

```
LK_ER,t = (LE_OA,t + LK_disp,t + LE_BR,t) × ER_t / (ER_t + CR_t)
```
`LK_{ER,t} = (LE_{OA,t} + LK_{disp,t} + LE_{BR,t}) \times \frac{ER_t}{ER_t + CR_t}`

| Variable | Definition | Unit |
|---|---|---|
| LE_BR,t | Leakage emissions from the diversion of manure or crop residues from baseline energy applications in year t | t CO2e |
| LK_disp,t | (C&C insertion) Leakage emissions from displaced production in year t | t CO2e |
| CR_t | Estimated carbon dioxide removals in year t | t CO2e |
| LE_OA,t | *Not defined in the Where list on p.60.* It is defined in Section 8.4.1, Eq. (33), p.55 as "Leakage from organic amendments in year t" | t CO2e |

#### Equation (40): Carbon dioxide removals (p.60)

Context: "Carbon dioxide removals occur when the cumulative carbon stock change in the project scenario is positive (i.e., the project carbon stock is higher than at the project start date)." Possible annual variations: (1) stocks increase in the baseline and, to a greater extent, in the project (fn 51); (2) stocks decrease in the baseline and increase in the project (fn 52).

```
CR_t = I(ΔCO2_wp) × ( MAX(0, ΔCO2_wp,t) − MAX(0, ΔCO2_bsl,t) )
```
`CR_t = I(\Delta CO2_{wp}) \times (\mathrm{MAX}(0,\Delta CO2_{wp,t}) - \mathrm{MAX}(0,\Delta CO2_{bsl,t}))`

The indicator is the same as in Eq. 37: I = 1 if Σ_{1}^{t} ΔCO2_wp,t > 0, and 0 if Σ_{1}^{t} ΔCO2_wp,t ≤ 0.

| Variable | Definition | Unit |
|---|---|---|
| I(ΔCO2_wp) | Switches Equation (40) on when the cumulative carbon stock change in the project scenario is positive, and off when the change is negative (p.61) | – |

#### Equation (41): Net removals (p.61)

```
CR_NET,t = CR_t − LK_CR,t
```

| Variable | Definition | Unit |
|---|---|---|
| CR_NET,t | Estimated net carbon dioxide removals in year t | t CO2e |
| LK_CR,t | Leakage allocated to carbon dioxide removals in year t | t CO2e |

#### Equation (42): Leakage allocated to removals (p.61; the C&C inserts LK_disp,t)

```
LK_CR,t = (LE_OA,t + LK_disp,t + LE_BR,t) × CR_t / (ER_t + CR_t)
```
`LK_{CR,t} = (LE_{OA,t} + LK_{disp,t} + LE_{BR,t}) \times \frac{CR_t}{ER_t + CR_t}`

The variables are as in Eq. 39. There is no separate Where list.

#### Equation (43): Net reductions and removals (p.61)

```
ERR_NET,t = ER_NET,t + CR_NET,t
```

| Variable | Definition | Unit |
|---|---|---|
| ERR_NET,t | Estimated net reductions and removals in year t | t CO2e |

Sign convention (p.61): "reductions are calculated by subtracting project (subscript wp) from baseline (subscript bsl) emissions ... removals are calculated by subtracting baseline C stocks from project C stocks".

### 8.5.1 Carbon Stock Changes (pp. 61–64)

#### Equation (44): Baseline total carbon stock change (p.61)

```
ΔCO2_bsl,t = ΔCO2_soil_bsl,t × (1 − UNC_t,CO2 × I(ΔCO2_soil_t)) + ΔC_TREE,bsl,t + ΔC_SHRUB,bsl,t
```
`\Delta CO2_{bsl,t} = \Delta CO2\_soil_{bsl,t} \times (1 - UNC_{t,CO2} \times I(\Delta CO2\_soil_t)) + \Delta C_{TREE,bsl,t} + \Delta C_{SHRUB,bsl,t}`

Indicator as printed (p.61):
- I(ΔCO2_soil_t) = +1 if ΔCO2_soil_wp,t − ΔCO2_soil_bsl,t ≥ 0, and
- I(ΔCO2_soil_t) = −1 if ΔCO2_soil_wp,t − ΔCO2_soil_bsl,t < 0

| Variable | Definition | Unit |
|---|---|---|
| ΔCO2_soil_bsl,t | SOC stock change in the baseline scenario in year t | t CO2e |
| UNC_t,CO2 | Uncertainty deduction in year t associated with modeling or measuring SOC stock changes | fraction between 0 and 1 |
| I(ΔCO2_soil_t) | Changes the sign of the Uncertainty UNC_t,CO2 from positive to negative when the SOC stock change between project and baseline scenario is negative (see note below) ensuring a conservative application of uncertainty when SOC losses result in emissions instead of removals. | – (+1/−1) |
| ΔC_TREE,bsl,t | Carbon stock change in tree biomass in the baseline scenario in year t | t CO2e |
| ΔC_SHRUB,bsl,t | Carbon stock change in shrub biomass in the baseline scenario in year t | t CO2e |

Note (p.62, verbatim): "When the SOC stocks in the project scenario decrease more rapidly or increase less rapidly than in the baseline scenario, the application of the I(ΔCO2_soil_t) function ensures that the uncertainty deduction multiplier is a value >1 adding up the SOC losses. In the more usual case where SOC stock increases in the project scenario are higher than in the baseline scenario, the uncertainty deduction multiplier remains a value between 0 and 1 resulting in a deduction."

#### Equation (45): Project total carbon stock change (p.62)

```
ΔCO2_wp,t = ΔCO2_soil_wp,t × (1 − UNC_t,CO2 × I(ΔCO2_soil_t)) + ΔC_TREE,wp,t + ΔC_SHRUB,wp,t
```
Indicator as printed under Eq. 45 (written there as I(ΔCO2_soilt)): = 1 if ΔCO2_soil_wp,t − ΔCO2_soil_bsl,t ≥ 0; = −1 if ΔCO2_soil_wp,t − ΔCO2_soil_bsl,t < 0.

| Variable | Definition | Unit |
|---|---|---|
| ΔCO2_soil_wp,t | SOC stock change in the project scenario in year t | t CO2e |
| ΔC_TREE,wp,t | Carbon stock change in tree biomass in the project scenario in year t | t CO2e |
| ΔC_SHRUB,wp,t | Carbon stock change in shrub biomass in the project scenario in year t | t CO2e |

#### Equation (46): Baseline SOC stock change (p.62)

```
ΔCO2_soil_bsl,t = Σ_{i=1}^{n} ( ( SOC̄_bsl,i,t − SOC̄_bsl,i,t−x ) × 1/x ) × A_i
```
`\Delta CO2\_soil_{bsl,t} = \sum_{i=1}^{n}\left( (\overline{SOC}_{bsl,i,t} - \overline{SOC}_{bsl,i,t-x}) \times \frac{1}{x} \right) \times A_i`

| Variable | Definition | Unit |
|---|---|---|
| SOC̄_bsl,i,t | Areal mean carbon stocks in the SOC pool in the baseline scenario for quantification unit i at the end of year t | t CO2e/ha |
| SOC̄_bsl,i,t−x | Areal mean carbon stocks in the SOC pool in the baseline scenario for quantification unit i at the end of year t − x | t CO2e/ha |
| x | Length of the verification period | years |
| A_i | Area of quantification unit i | ha |

#### Equation (47): Project SOC stock change (p.63)

```
ΔCO2_soil_wp,t = Σ_{i=1}^{n} ( ( SC̄_wp,i,t − SOC̄_wp,i,t−x ) × 1/x ) × A_i
```
**[SOURCE NOTE]** The first term is printed as "SC̄_wp,i,t" (missing "O"). The Where list defines SOC̄_wp,i,t, so it is evidently a typo for `\overline{SOC}_{wp,i,t}`.

| Variable | Definition | Unit |
|---|---|---|
| SOC̄_wp,i,t | Areal mean carbon stocks in the SOC pool in the project scenario for quantification unit i at the end of year t | t CO2e/ha |
| SOC̄_wp,i,t−x | Areal mean carbon stocks in the SOC pool in the project scenario for quantification unit i at the end of year t − x | t CO2e/ha |

Note (p.63): "SOC stock changes must be converted to t CO2e using the factor 44/12 (ratio of molecular weight of carbon dioxide to carbon)."
QA2 text (p.63): "For Quantification Approach 2, SOC stock changes for quantification unit i in year t are compared to the estimated SOC stock change in baseline control sites. The mean SOC stock per hectare of each 'project site–baseline control site' combination should be used. Where measurements are conducted less frequently than every year, results must be divided by the number of years to calculate an annual SOC stock change."

#### Equation (48): Baseline tree biomass carbon stock change (p.63)

```
ΔC_TREE,bsl,t = Σ_{i=1}^{n} ( ΔC̄_TREE,bsl,i,t − ΔC̄_TREE,bsl,i,t−x ) × 1/x × A_i
```

| Variable | Definition | Unit |
|---|---|---|
| ΔC̄_TREE,bsl,i,t | Areal mean baseline carbon stock change in tree biomass for quantification unit i in year t | t CO2e/ha |
| ΔC̄_TREE,bsl,i,t−x | Areal mean baseline carbon stock change in tree biomass for quantification unit i in year t − x | t CO2e/ha |

#### Equation (49): Project tree biomass carbon stock change (pp. 63–64)

```
ΔC_TREE,wp,t = Σ_{i=1}^{n} ( ΔC̄_TREE,wp,i,t − ΔC̄_TREE,wp,i,t−x ) × 1/x × A_i
```

| Variable | Definition | Unit |
|---|---|---|
| ΔC̄_TREE,wp,i,t | Areal mean project scenario carbon stock change in tree biomass for quantification unit i in year t | t CO2e/ha |
| ΔC̄_TREE,wp,i,t−x | Areal mean project scenario carbon stock change in tree biomass for quantification unit i in year t − x | t CO2e/ha |

#### Equation (50): Baseline shrub biomass carbon stock change (p.64)

```
ΔC_SHRUB,bsl,t = Σ_{i=1}^{n} ( ΔC̄_SHRUB,bsl,i,t − ΔC̄_SHRUB,bsl,i,t−x ) × 1/x × A_i
```

| Variable | Definition | Unit |
|---|---|---|
| ΔC̄_SHRUB,bsl,i,t | Areal mean baseline carbon stock change in shrub biomass for quantification unit i in year t | t CO2e/ha |
| ΔC̄_SHRUB,bsl,i,t−x | Areal mean baseline carbon stock change in shrub biomass for quantification unit i in year t − x | t CO2e/ha |

#### Equation (51): Project shrub biomass carbon stock change (p.64)

```
ΔC_SHRUB,wp,t = Σ_{i=1}^{n} ( ΔC̄_SHRUB,wp,i,t − ΔC̄_SHRUB,wp,i,t−x ) × 1/x × A_i
```

| Variable | Definition | Unit |
|---|---|---|
| ΔC̄_SHRUB,wp,i,t | Areal mean project scenario carbon stock change in shrub biomass for quantification unit i in year t | t CO2e/ha |
| ΔC̄_SHRUB,wp,i,t−x | Areal mean project scenario carbon stock change in shrub biomass for quantification unit i in year t − x | t CO2e/ha |

### 8.5.2 Fossil Fuel Combustion Emission Reductions (p.64)

#### Equation (52)

```
ΔCO2_ff_t = Σ_{i=1}^{n} ( CO2_ff̄_bsl,i,t − CO2_ff̄_wp,i,t ) × A_i
```

| Variable | Definition | Unit |
|---|---|---|
| CO2_ff̄_bsl,i,t | Areal mean GHG emissions from fossil fuel combustion in the baseline scenario for quantification unit i in year t | t CO2e/ha |
| CO2_ff̄_wp,i,t | Areal mean GHG emissions from fossil fuel combustion in the project scenario for quantification unit i in year t | t CO2e/ha |

### 8.5.3 Liming Emission Reductions (p.65)

#### Equation (53)

```
ΔCO2_lime_t = Σ_{i=1}^{n} ( CO2_limē_bsl,i,t − CO2_limē_wp,i,t ) × A_i
```

| Variable | Definition | Unit |
|---|---|---|
| CO2_limē_bsl,i,t | Areal mean GHG emissions from liming in the baseline scenario for quantification unit i in year t | t CO2e/ha |
| CO2_limē_wp,i,t | Areal mean GHG emissions from liming in the project scenario for quantification unit i in year t | t CO2e/ha |

### 8.5.4 Methane Emission Reductions (pp. 65–66)

#### Equation (54): CH4 from the SOC pool

```
ΔCH4_soil_t = Σ_{i=1}^{n} ( CH4_soil̄_bsl,i,t − CH4_soil̄_wp,i,t ) × A_i
```

| Variable | Definition | Unit |
|---|---|---|
| CH4_soil̄_bsl,i,t | Areal mean methane emissions from SOC pool in the baseline scenario for quantification unit i in year t | t CO2e/ha |
| CH4_soil̄_wp,i,t | Areal mean methane emissions from SOC pool in the project scenario for quantification unit i in year t | t CO2e/ha |

#### Equation (55): CH4 from enteric fermentation

```
ΔCH4_ent_t = Σ_{i=1}^{n} ( CH4_ent̄_bsl,i,t − CH4_ent̄_p,i,t ) × A_i
```
**[SOURCE NOTE]** The second term's subscript is printed as "p,i,t", but the Where list defines CH4_ent̄_wp,i,t. Treat it as wp.

| Variable | Definition | Unit |
|---|---|---|
| CH4_ent̄_bsl,i,t | Areal mean methane emissions from livestock enteric fermentation in the baseline scenario for quantification unit i in year t | t CO2e/ha |
| CH4_ent̄_wp,i,t | Areal mean methane emissions from livestock enteric fermentation in the project scenario for quantification unit i in year t | t CO2e/ha |

#### Equation (56): CH4 from manure deposition

```
ΔCH4_md_t = Σ_{i=1}^{n} ( CH4_md̄_bsl,i,t − CH4_md̄_wp,i,t ) × A_i
```

| Variable | Definition | Unit |
|---|---|---|
| CH4_md̄_bsl,i,t | Areal mean methane emissions from manure deposition in the baseline scenario for quantification unit i in year t | t CO2e/ha |
| CH4_md̄_wp,i,t | Areal mean methane emissions from manure deposition in the project scenario for quantification unit i in year t | t CO2e/ha |

#### Equation (57): CH4 from biomass burning

```
ΔCH4_bb_t = Σ_{i=1}^{n} ( CH4_bb̄_bsl,i,t − CH4_bb̄_wp,i,t ) × A_i
```

| Variable | Definition | Unit |
|---|---|---|
| CH4_bb̄_bsl,i,t | Areal mean methane emissions from biomass burning in the baseline scenario for quantification unit i in year t | t CO2e/ha |
| CH4_bb̄_wp,i,t | Areal mean methane emissions from biomass burning in the project scenario for quantification unit i in year t | t CO2e/ha |

### 8.5.5 Nitrous Oxide Emission Reductions (p.66)

#### Equation (58): N2O from nitrification/denitrification

```
ΔN2O_soil_t = Σ_{i=1}^{n} ( N2O_soil̄_bsl,i,t − N2O_soil̄_wp,i,t ) × A_i
```

| Variable | Definition | Unit |
|---|---|---|
| N2O_soil̄_bsl,i,t | Areal mean nitrous oxide emissions from nitrogen inputs to soils in the baseline scenario for quantification unit i in year t | t CO2e/ha |
| N2O_soil̄_wp,i,t | Areal mean nitrous oxide emissions from nitrogen inputs to soils in the project scenario for quantification unit i in year t | t CO2e/ha |

#### Equation (59): N2O from biomass burning

```
ΔN2O_bb_t = Σ_{i=1}^{n} ( N2O_bb̄_bsl,i,t − N2O_bb̄_wp,i,t ) × A_i
```

| Variable | Definition | Unit |
|---|---|---|
| N2O_bb̄_bsl,i,t | Nitrous oxide emissions from biomass burning in the baseline scenario for quantification unit i in year t | t CO2e/ha |
| N2O_bb̄_wp,i,t | Nitrous oxide emissions from biomass burning in the project scenario for quantification unit i in year t | t CO2e/ha |

### 8.6 Uncertainty (introduction, pp. 66–67; read from the text copy, no equations)

- "Uncertainty deductions are estimated separately for each GHG source within a project. Deductions are based on an estimate of the total error of the project's calculated reductions and removals for that source over a given verification period."
- All sampling, analysis and modelling is assumed to happen on a point basis. Alternatives (e.g., areal modelling) are a deviation.
- "Per Section 8.2.1, this methodology requires that stratified random sampling is used." Points are allocated randomly within strata, proportionally by area. The example design is stratified random sampling with **simple random sampling with replacement** within strata. Multi-stage examples are in Appendix 6. Alternative designs need a methodology deviation with equivalent uncertainty calculations.

### 8.6.1 Quantification Approach 1: SKIPPED (out of scope)

Eqs. 60–64 (analytical error propagation) and 65–69 (MC simulation), plus 8.6.1.3 (remeasurement/true-up, Figure 4a on p.81), are not transcribed here.

### 8.6.2 Quantification Approach 2 (pp. 81–87)

#### Equation (70): Project-wide variance of mean SOC change (p.82)

```
s²_{ΔSOC̄,t} = (1 / A²) × Σ_{1}^{n} s²_{ΔSOC,h,t}
```
`s^2_{\overline{\Delta SOC},t} = \frac{1}{A^2}\sum_{1}^{n} s^2_{\Delta SOC,h,t}`
(The summation is printed with lower limit "1" and upper limit "n"; no index variable is written.)

with
```
s²_{ΔSOC,h,t} = s²_{ΔSOC,wp,h,t} + s²_{ΔSOC,bsl,h,t}
```

| Variable | Definition | Unit |
|---|---|---|
| s²_{ΔSOC̄,t} | Variance of the estimate of mean SOC stock changes in verification period t across the entire project area, calculated as the difference in net change between the project and baseline scenarios over period t | (t CO2e/ha)² |
| s²_{ΔSOC,h,t} | Variance of the estimate of total SOC stock changes in verification period t in stratum h, calculated as the difference in net change between the project and baseline scenarios over period t | (t CO2e)² |
| s²_{ΔSOC,wp,h,t} | Variance of the estimate of total SOC stock changes in the project plots in verification period t in stratum h, calculated as the difference in SOC stocks at the beginning and end of period t | (t CO2e)² |
| s²_{ΔSOC,bsl,h,t} | Variance of the estimate of total SOC stock changes in baseline (control) plots paired with project stratum h in verification period t, calculated as the difference in SOC stocks at the beginning and end of period t | (t CO2e)² |
| A | *Not defined in the Where list.* From context it is the total project area (the text says weighting is by project strata area) | ha (inferred) |
| n | *Not defined in the Where list.* From context it is the number of strata | – (inferred) |

Text (p.83, C&C corrected the equation cross-reference): "Note that the area-weighting in Equation (70) is based on the area of the project strata, not the baseline control sites with which they are paired."

#### Equation (71): Project-stratum variance of change, conventional lab analysis (p.83)

```
s²_{ΔSOC,wp,h,t} = s²_{SOC,wp,h,f} + s²_{SOC,wp,h,s} − 2·COV(SOC_wp,h,f ; SOC_wp,h,s)
```

Sub-equations (p.83):
```
s²_{SOC,wp,h,f} = A_h² / (n_h (n_h − 1)) × Σ_{ip=1}^{n_h} ( SOC_wp,h,ip,f − SOC̄_wp,h,f )²

s²_{SOC,wp,h,s} = A_h² / (n_h (n_h − 1)) × Σ_{ip=1}^{n_h} ( SOC_wp,h,ip,s − SOC̄_wp,h,s )²

COV(SOC_wp,h,f ; SOC_wp,h,s) = A_h² / (n_h (n_h − 1)) × Σ_{ip=1}^{n_h} ( SOC_wp,h,ip,s − SOC̄_wp,h,s )( SOC_wp,h,ip,f − SOC̄_wp,h,f )
```

LaTeX:
```latex
s^2_{\Delta SOC,wp,h,t} = s^2_{SOC,wp,h,f} + s^2_{SOC,wp,h,s} - 2COV(SOC_{wp,h,f};SOC_{wp,h,s})
s^2_{SOC,wp,h,f} = \frac{A_h^2}{n_h(n_h-1)}\sum_{ip=1}^{n_h}(SOC_{wp,h,ip,f}-\overline{SOC}_{wp,h,f})^2
s^2_{SOC,wp,h,s} = \frac{A_h^2}{n_h(n_h-1)}\sum_{ip=1}^{n_h}(SOC_{wp,h,ip,s}-\overline{SOC}_{wp,h,s})^2
COV(SOC_{wp,h,f};SOC_{wp,h,s}) = \frac{A_h^2}{n_h(n_h-1)}\sum_{ip=1}^{n_h}(SOC_{wp,h,ip,s}-\overline{SOC}_{wp,h,s})(SOC_{wp,h,ip,f}-\overline{SOC}_{wp,h,f})
```

| Variable | Definition | Unit |
|---|---|---|
| s²_{SOC,wp,h,f} | Variance of the estimate of SOC stocks in the project scenario at t_final in stratum h | (t CO2e)² |
| s²_{SOC,wp,h,s} | Variance of the estimate of SOC stocks in the project scenario at t_start in stratum h | (t CO2e)² |
| COV(SOC_wp,h,f ; SOC_wp,h,s) | Covariance of estimates of SOC stocks at t_final and t_start in the project scenario in stratum h | (t CO2e)² |
| SOC̄_wp,h,f | Mean estimate of SOC stocks across all points in the project scenario at t_final in stratum h | t CO2e/ha |
| SOC̄_wp,h,s | Mean estimate of SOC stocks across all points in the project scenario at t_start in stratum h | t CO2e/ha |
| SOC_wp,h,ip,f | Estimated SOC stock on an area basis at point ip in the project scenario at t_final in stratum h | t CO2e/ha |
| SOC_wp,h,ip,s | Estimated SOC stock on an area basis at point ip in the project scenario at t_start in stratum h | t CO2e/ha |
| A_h, n_h | *Not defined in this Where list.* From context they are the area of stratum h and the number of sample points in stratum h | ha, – (inferred) |

#### Equation (72): Project-stratum variance of change with soil spectroscopy, MC approach (pp. 84–85)

```
s²_{ΔSOC,wp,h,t} = s²_{SOC,wp,h,f} + s²_{SOC,wp,h,s} − 2·COV(SOC_wp,h,f ; SOC_wp,h,s)
```
"The variance of an individual stratum is estimated as follows. The same equation form applies to time point s." (p.85)
```
s²_{SOC,wp,h,f} = s²_{SOC,wp,h,f,sample} + s²_{SOC,wp,h,f,model}

s²_{SOC,wp,h,f,sample} = A_h² / (n_h (n_h − 1)) × Σ_{ip=1}^{n_h} ( SOC_wp,h,ip,f − SOC̄_wp,h,f )²

SOC_wp,h,ip,f = (1/L) × Σ_{l=1}^{L} SOC_wp,h,ip,f,l

SOC̄_wp,h,f = (1/A_h) × Σ_{ip=1}^{n_h} SOC_wp,h,ip,f

s²_{SOC,wp,h,f,model} = 1/(L − 1) × Σ_{l=1}^{L} ( SOC_wp,f,l − SOC̄_wp,f )²

SOC_wp,f,l = Σ_{h=1}^{H} SOC_wp,h,f,l

SOC_wp,h,f,l = (A_h / n_h) × Σ_{ip=1}^{n_h} SOC_wp,h,f,ip,l

SOC̄_wp,f = (1/L) × Σ_{l=1}^{L} SOC_wp,f,l

COV(SOC_wp,h,f ; SOC_wp,h,s) = (1/L) × Σ_{l=1}^{L} { A_h² / (n_h (n_h − 1)) × Σ_{ip=1}^{n_h} ( SOC_wp,h,ip,s,l − SOC̄_wp,h,s )( SOC_wp,h,ip,f,l − SOC̄_wp,h,f ) }
```

LaTeX:
```latex
s^2_{SOC,wp,h,f} = s^2_{SOC,wp,h,f,sample} + s^2_{SOC,wp,h,f,model}
s^2_{SOC,wp,h,f,sample} = \frac{A_h^2}{n_h(n_h-1)}\sum_{ip=1}^{n_h}(SOC_{wp,h,ip,f}-\overline{SOC}_{wp,h,f})^2
SOC_{wp,h,ip,f} = \frac{1}{L}\sum_{l=1}^{L} SOC_{wp,h,ip,f,l}
\overline{SOC}_{wp,h,f} = \frac{1}{A_h}\sum_{ip=1}^{n_h} SOC_{wp,h,ip,f}
s^2_{SOC,wp,h,f,model} = \frac{1}{L-1}\sum_{l=1}^{L}(SOC_{wp,f,l}-\overline{SOC}_{wp,f})^2
SOC_{wp,f,l} = \sum_{h=1}^{H} SOC_{wp,h,f,l}
SOC_{wp,h,f,l} = \frac{A_h}{n_h}\sum_{ip=1}^{n_h} SOC_{wp,h,f,ip,l}
\overline{SOC}_{wp,f} = \frac{1}{L}\sum_{l=1}^{L} SOC_{wp,f,l}
COV(SOC_{wp,h,f};SOC_{wp,h,s}) = \frac{1}{L}\sum_{l=1}^{L}\left\{\frac{A_h^2}{n_h(n_h-1)}\sum_{ip=1}^{n_h}(SOC_{wp,h,ip,s,l}-\overline{SOC}_{wp,h,s})(SOC_{wp,h,ip,f,l}-\overline{SOC}_{wp,h,f})\right\}
```

| Variable | Definition | Unit |
|---|---|---|
| s²_{SOC,wp,h,f,sample} | Variance of the estimate of SOC stocks in the project scenario at t_final in stratum h attributable to sampling error | (t CO2e)² |
| s²_{SOC,wp,h,f,model} | Variance of the estimate of SOC stocks in the project scenario at t_final in stratum h attributable to prediction error of the soil spectroscopy model | (t CO2e)² |
| SOC̄_wp,h,f | Mean estimate of SOC stocks across all points in the project scenario at t_final in stratum h in the lth simulation | t CO2e/ha |
| SOC_wp,h,ip,f,l | Estimated SOC stocks on an area basis at point ip in the project scenario at t_final in stratum h in the lth simulation | t CO2e/ha |
| SOC_wp,h,ip,s,l | Estimated SOC stocks on an area basis at point ip in the project scenario at t_start in stratum h in the lth simulation | t CO2e/ha |
| SOC_wp,f,l | Estimate of total SOC stocks on an area basis in the project scenario across the entire project at t_final in the lth simulation | t CO2e |
| SOC̄_wp,f | Mean estimate of total SOC stocks in the project scenario across the entire project at t_final averaged across all L simulations | t CO2e |
| L, H, SOC_wp,h,f,l | *Not defined in the Where list.* From context L is the number of MC iterations, H the number of strata, and SOC_wp,h,f,l the stratum total for simulation l | – |

**[SOURCE NOTES] for Eq. 72:**
- SOC̄_wp,h,f = (1/A_h) Σ SOC_wp,h,ip,f is printed with 1/A_h. A per-point mean would normally be 1/n_h. Reproduced as printed; needs confirmation.
- In SOC_wp,h,f,l = (A_h/n_h) Σ SOC_wp,h,f,ip,l, the subscript order is "h,f,ip,l", while elsewhere it is "h,ip,f,l". These look like the same quantity.
- The Where list defines SOC̄_wp,h,f "in the lth simulation", but the equation has no l index on it.
- In the COV expression the closing "− SOC̄_wp,h,f)" wraps onto a new line inside the braces. The form transcribed above is the reading of the full expression.

#### Equation (73): Model error, simple frequentist alternative to MC (p.86)

"Where a project proponent elects not to use the MC simulation approach and instead estimate model error using a simple frequentist approach, then s²_{SOC,wp,hf,model} in Equation (72) is replaced with an estimate of model prediction error that is the same across all strata and both scenarios, s²_{SOC,model}. This estimate is determined by comparing modeled estimates of SOC to values determined through laboratory analysis (Appendix 4)."

```
s²_{SOC,model} = A² / (tvd − 1) × Σ_{pvd=1}^{tvd} ( error_pvd − mean error )²

error_pvd = SOC_model,pvd − SOC_observed,pvd

mean error = (1/tvd) × Σ_{pvd=1}^{tvd} error_pvd
```
`s^2_{SOC,model} = \frac{A^2}{tvd-1}\sum_{pvd=1}^{tvd}(error_{pvd} - mean\ error)^2`

| Variable | Definition | Unit |
|---|---|---|
| s²_{SOC,model} | Variance of the estimate of SOC stocks attributable to prediction error of the soil spectroscopy model | (t CO2e)² |
| error_pvd | Difference between the predicted estimate of SOC on an area basis and observed SOC at point pvd in the randomly selected statistical validation dataset | t CO2e/ha |
| mean error | Mean of all estimates of error_pvd across all tvd points in the statistical validation dataset | t CO2e/ha |
| SOC_model,pvd | Predicted estimate of SOC on an area basis at point pvd in the randomly selected statistical validation dataset | t CO2e/ha |
| SOC_observed,pvd | Observed SOC on an area basis at point pvd in the randomly selected statistical validation dataset, determined through conventional lab analysis and field sampling | t CO2e/ha |
| pvd | 1, …, tvd sample points within the statistical validation dataset | – |
| A | *Not defined here.* Presumably the project area, as in Eq. 70 | ha (inferred) |

p.87: "Furthermore, s²_{SOC,wp,h,f,sample} should be determined using the same equation as is used to determine s²_{SOC,wp,h,f} in Equation (71), but individual point values are instead the value for that point as predicted by the soil spectroscopy model."

### 8.6.4 Uncertainty Deductions (pp. 88–90)

#### Equation (74): Uncertainty deduction (p.88)

```
UNC_{Δ̄·,t} = ( √(s²_{Δ̄·,t}) / Δ̄·_t × 100 ) × t_0.667
```
`UNC_{\overline{\Delta}\cdot,t} = \left(\frac{\sqrt{s^2_{\overline{\Delta}\cdot,t}}}{\overline{\Delta}\cdot_t} \times 100\right) \times t_{0.667}`
(The square root covers only s²; Δ̄·_t is the denominator. The "·" is a placeholder for the GHG or C pool.)

| Variable | Definition | Unit |
|---|---|---|
| UNC_{Δ̄·,t} | Uncertainty deduction for each GHG or C pool • to be applied in verification period t | % |
| Δ̄·_t | Mean ERR for each GHG or C pool • across the entire project area in year t | t CO2e/ha |
| s²_{Δ̄·,t} | Variance of the mean ERR estimate from each GHG or C pool • at time t. See Figure 5 (C&C: was "Figure 4") to determine how this is estimated based on the methods employed in the project | (t CO2e/ha)² |
| t_0.667 | t-value for a one-sided student's t-distribution at 0.667 (66.7%) confidence interval with degrees of freedom appropriate to the sampling design used. Equal to approximately 0.4307 at large sample sizes | dimensionless |

Text (p.88): deductions are "estimated and applied separately for each reduction and removal source within the project boundary ... using a probability of exceedance method ... (see the most recent version of the VCS Methodology Requirements Section 2.4)". "...one estimates what percentage of the estimates of Δ̄·_t would have a 66.6% probability of exceeding the true value of Δ̄·_t. That percentage is then used as the uncertainty deduction."
Figure 5 caption (p.88): "Probability of exceedance. The value for Δ̄·_t used in calculation of VCUs issued is determined by applying an uncertainty deduction based on the 33.3rd percentile of the estimated probability distribution of Δ̄·_t." Figure p.89 shows a density with the label "66.6% of values exceed".

Figure 6 (p.90; C&C renumbered it from 5 to 6), "Equation map for calculating uncertainty deduction under Quantification Approaches 1 (for SOC, CH4, and N2O) and 2 (for SOC)":
- QA1 (applicable to SOC, and to CH4 and N2O from soil as indicated in Table 5): analytical error propagation, Eqs. 60–64 → s²_{Δ̄·,t} → Eq. 74; or MC simulation, Eqs. 65–69 → s²_{Δ̄·,t} → Eq. 74.
- QA2 (applicable only to SOC): conventional lab analysis, Eqs. 70–71 → s²_{ΔSOC̄,t} → Eq. 74; or proximal sensing methods, Eqs. 70 & 72 or 73 → s²_{ΔSOC̄,t} → Eq. 74.
- Footnote 58: "where a sample design other than the default stratified random sampling approach (see Section 8.2.1) is proposed via a methodology deviation, these equations should not be used but the general workflow is the same."

### 8.7 Calculation of Verified Carbon Units (pp. 90–91)

Text (p.90): "the project proponent must consider the number of buffer credits that must be deposited in the AFOLU pooled buffer account. The number of buffer credits that must be deposited is calculated by multiplying the non-permanence risk rating by the net change in carbon stocks (see most recent version of the VCS Standard [fn 59: For example, this is included in Section 3.2.10 of the VCS Standard, v4.7.])."

#### Equation (75): Buffer credits on reductions (p.90)

```
Bu_ER,t = I(ΔCO2_wp) × ( MIN(0, ΔCO2_wp,t) − MIN(0, ΔCO2_bsl,t) ) × NPR%
        + (1 − I(ΔCO2_wp)) × ( MIN(0, ΔCO2_wp,t) − MIN(0, ΔCO2_bsl,t)
                               + MAX(0, ΔCO2_wp,t) − MAX(0, ΔCO2_bsl,t) ) × NPR%
```
```latex
\begin{aligned}
Bu_{ER,t} ={}& I(\Delta CO2_{wp}) \times (\mathrm{MIN}(0,\Delta CO2_{wp,t}) - \mathrm{MIN}(0,\Delta CO2_{bsl,t})) \times NPR\% \\
&+ (1 - I(\Delta CO2_{wp})) \times (\mathrm{MIN}(0,\Delta CO2_{wp,t}) - \mathrm{MIN}(0,\Delta CO2_{bsl,t}) + \mathrm{MAX}(0,\Delta CO2_{wp,t}) - \mathrm{MAX}(0,\Delta CO2_{bsl,t})) \times NPR\%
\end{aligned}
```
I(ΔCO2_wp) = 1 if Σ_{1}^{t} ΔCO2_wp,t > 0; 0 if Σ_{1}^{t} ΔCO2_wp,t ≤ 0.

| Variable | Definition | Unit |
|---|---|---|
| Bu_ER,t | Buffer credits to be deducted from reductions in year t | t CO2e |

#### Equation (76): Buffer credits on removals (p.91)

```
Bu_CR,t = I(ΔCO2_wp) × ( MAX(0, ΔCO2_wp,t) − MAX(0, ΔCO2_bsl,t) ) × NPR%
```
The indicator is the same as above.

| Variable | Definition | Unit |
|---|---|---|
| Bu_CR,t | Buffer credits to be deducted from removals in year t | t CO2e |
| ΔCO2_wp,t | Total carbon stock change in the project scenario in year t | t CO2e |
| ΔCO2_bsl,i,t | Total carbon stock change in the baseline scenario in year t | t CO2e |
| NPR% | Overall project non-permanence risk rating converted to a percentage | % |

**[SOURCE NOTE]** The Where list prints "ΔCO2_bsl,i,t" with an extra "i", but the equation uses ΔCO2_bsl,t.

#### Equation (77): VCUs from reductions (p.91)

```
VCU_ER,t = ER_NET,t − Bu_ER,t
```

| Variable | Definition | Unit |
|---|---|---|
| VCU_ER,t | Number of Verified Carbon Units resulting from project activities leading to reductions in year t | (none printed) |
| ER_NET,t | Estimated net reductions in year t | t CO2e |

#### Equation (78): VCUs from removals (p.91)

```
VCU_CR,t = CR_NET,t − Bu_CR,t
```

| Variable | Definition | Unit |
|---|---|---|
| VC_CR,t **[SOURCE NOTE: printed "VC_CR,t", means VCU_CR,t]** | Number of Verified Carbon Units resulting from project activities leading to removals in year t | (none printed) |
| CR_NET,t | Estimated net removals in year t | t CO2e |

#### Equation (79): Total VCUs (p.91)

```
VCU_t = VCU_ER,t + VCU_CR,t
```

| Variable | Definition | Unit |
|---|---|---|
| VCU_t | Number of VCUs in year t | t CO2e |

---

## 2. Approach 2 (measure and remeasure) uncertainty: procedure (pp. 63, 81–88, 90)

1. **Scope.** QA2 applies to **SOC stocks only** (p.81). The baseline is represented by control sites linked to one or more project quantification units. The SOC difference and its uncertainty come from comparing control sites with paired project units.
2. **Error sources** (pp. 81–82):
   - Sampling error.
   - Measurement error. If samples are collected with ESM approaches and analysed by dry combustion in a lab with demonstrated proficiency and QC (e.g., NAPT program, fn 57), measurement errors are "assumed to be unbiased and negligible". With alternative methods (e.g., soil spectroscopy), measurement error "must be estimated and propagated".
   - The error sources are estimated separately and then combined into **a single uncertainty deduction for SOC stocks across the entire project**. Either analytical error propagation or MC may be used, but "the MC simulation method is only applicable in cases where measurement error is deemed significant and must be propagated through calculations."
3. **Design assumed in the example** (pp. 82–83): stratified random sampling, with each stratum paired with a control site. Points within each stratum use simple random sampling with replacement, the same estimator applies to project and baseline, and **the same sample points are revisited at t_start and t_final**. Net change is measured by direct sampling and dry combustion at the start and end of period t. Where the project and baseline designs differ (e.g., staged project design and non-staged control), "baseline and project areas should use different uncertainty estimators before estimating the combined uncertainty."
4. **Statistics per stratum h, project side** (Eq. 71):
   - Variance at t_final: A_h²/(n_h(n_h−1)) · Σ(SOC_ip,f − mean_f)².
   - Variance at t_start: the same form.
   - Covariance between t_start and t_final: A_h²/(n_h(n_h−1)) · Σ(SOC_ip,s − mean_s)(SOC_ip,f − mean_f).
   - s²_{ΔSOC,wp,h,t} = s²_f + s²_s − 2·COV.
   - **Baseline side:** s²_{ΔSOC,bsl,h,t} uses "the same" estimator (p.83). No separate baseline equation is printed.
5. **Combine project and baseline per stratum:** s²_{ΔSOC,h,t} = s²_{ΔSOC,wp,h,t} + s²_{ΔSOC,bsl,h,t}. "The covariance of these estimates is conservatively excluded as the baseline control sites and project sites are assumed to be independent" (p.82).
6. **Combine strata** (Eq. 70): s²_{ΔSOC̄,t} = (1/A²) Σ_h s²_{ΔSOC,h,t}. This is an area-weighted estimator based on **project strata areas**, not control site areas (p.83). The result is the variance of the mean change per ha.
7. **Spectroscopy (8.6.2.1)**: each stratum variance at each time point = sampling variance + model variance (Eq. 72, MC with L iterations from a PPD of the spectroscopy model). Alternatively, select **10–15% of samples** for dry combustion and compare them with the model predictions (p.84). With the frequentist option, s²_{SOC,model} from Eq. 73 replaces the MC model variance and is "the same across all strata and both scenarios" (p.86). Details are in Appendix 4.
8. **Other designs (8.6.2.2, p.87)**: if one control plot per stratum or revisiting the same points is not realistic, "the overall process ... should be similar", but the component equations will differ. A multi-stage example is in Appendix 6.
9. **Deduction** (Eq. 74): UNC (%) = (√s²_{ΔSOC̄,t} / Δ̄_t × 100) × t_0.667. Here Δ̄_t is the mean SOC ERR per ha across the project area for period t. The one-sided t is at 66.7% with df "appropriate to the sampling design", ≈ 0.4307 at large n.
10. **Application**: the deduction feeds UNC_t,CO2 (fraction 0–1) in Eqs. 44 and 45. It multiplies both ΔCO2_soil_bsl,t and ΔCO2_soil_wp,t by (1 − UNC_t,CO2 × I(ΔCO2_soil_t)), with I = −1 when the project-minus-baseline SOC change is negative (pp. 61–62).
11. **Annualisation** (p.63): where measurements are less frequent than annual, divide by the number of years. Eqs. 46–47 use 1/x with x = verification period length in years.
12. **Thresholds:** no minimum or maximum uncertainty threshold, no cap on UNC, and no "no deduction below X%" rule appears on these pages.

## 3. VCU calculation in 8.7 (pp. 90–91), with links back to 8.5

- **Order of operations, per year t:**
  1. Compute ΔCO2_wp,t and ΔCO2_bsl,t (Eqs. 44–51). The SOC uncertainty deduction is already applied inside them.
  2. Compute ER_t (Eq. 37). It includes the QA1-only UNC on CH4_soil and N2O_soil, and the carbon-stock terms via MIN/MAX.
  3. Compute CR_t (Eq. 40).
  4. Allocate leakage pro rata by ER_t/(ER_t+CR_t) and CR_t/(ER_t+CR_t) (Eqs. 39 and 42). Leakage = LE_OA,t + LK_disp,t (C&C addition) + LE_BR,t.
  5. ER_NET,t and CR_NET,t (Eqs. 38 and 41).
  6. Buffer Bu_ER,t and Bu_CR,t (Eqs. 75 and 76) = NPR% × the carbon-stock-change component only. Buffer is **not** applied to the non-CO2 or fossil/lime terms, and it is computed on gross stock changes, not net of leakage.
  7. VCU_ER,t = ER_NET,t − Bu_ER,t; VCU_CR,t = CR_NET,t − Bu_CR,t; VCU_t = VCU_ER,t + VCU_CR,t.
- **Switching logic:** I(ΔCO2_wp) is based on the **cumulative** project stock change from year 1 to t (Σ_{1}^{t} ΔCO2_wp,t > 0).
  - If I = 1: positive stock changes are counted as removals (CR) and only the MIN (loss) parts go into ER.
  - If I = 0: all stock-change terms (MIN and MAX) go into ER and CR = 0.
- **Non-permanence / buffer:** NPR% is the "overall project non-permanence risk rating converted to a percentage". The methodology refers to the "most recent version of the VCS Standard" (fn 59: Section 3.2.10 of VCS Standard v4.7) and the "AFOLU pooled buffer account". The AFOLU Non-Permanence Risk Tool is **not named** on these pages; NPR% comes from outside this methodology.
- **Uncertainty:** it is not a separate term in Eqs. 77–79. It is applied upstream: in Eqs. 44/45 (UNC_t,CO2, SOC) and in Eq. 37 (UNC_t,CH4_soil, UNC_t,N2O_soil, QA1 only).
- **Caps / floors / rounding:** none are stated in 8.7. No floor at zero for Bu or VCU and no rounding rule are printed.
- **Vintage:** all equations are indexed by year t. 8.7 contains no explicit vintage-splitting or multi-year verification-period aggregation rule. Eqs. 46–51 annualise period changes with 1/x.

## 4. Defaults, constants, confidence levels and thresholds

| Value | Meaning | Page |
|---|---|---|
| 44/12 | Conversion of SOC (C) stock changes to t CO2e | 63 |
| 1/x | Annualisation; x = length of verification period (years) | 62–64 |
| I(ΔCO2_wp) ∈ {0,1} | 1 if cumulative Σ_{1}^{t} ΔCO2_wp,t > 0, else 0 | 59, 60, 90, 91 |
| I(ΔCO2_soil_t) ∈ {+1,−1} | +1 if ΔCO2_soil_wp,t − ΔCO2_soil_bsl,t ≥ 0, −1 if < 0 | 61, 62 |
| UNC fractions 0–1 | UNC_t,CO2, UNC_t,CH4_soil, UNC_t,N2O_soil | 59, 62 |
| ×100 | Eq. 74 output is a percentage | 88 |
| t_0.667 ≈ 0.4307 | One-sided Student's t at 66.7% "confidence interval", large-sample value | 88 |
| 66.6% / 66.7% / 33.3rd percentile | Probability-of-exceedance level (several wordings) | 88, 89 |
| 10–15% of samples | Share of samples analysed by dry combustion to estimate spectroscopy model error (alternative to MC) | 84 |
| L | Number of MC resamples from the spectroscopy PPD (no value given) | 84–86 |
| COV(bsl, wp) = 0 | Project and control site covariance conservatively excluded | 82 |
| Measurement error negligible | When ESM + dry combustion in a proficiency-tested lab (NAPT) | 81–82 |
| IPCC 2019 EF 0.016 (range 0.013–0.019) | Example N2O EF for synthetic fertilizer, wet climates. Use 0.013 when project emissions decrease relative to baseline and 0.019 when they increase (QA3 conservativeness) | 87 |
| NPR% | From the VCS non-permanence risk rating (external) | 90–91 |

QA3 (8.6.3, pp. 87–88):
- Use the EF giving the **most conservative** result across baseline and project. Use disaggregated values whenever available.
- Sampling error does not factor into the deduction if management data are collected across all quantification units (Box 1 hierarchy).
- Otherwise, the QA1 sampling-error procedures (8.6.1) must be followed, and the sampling design must be described and justified.
- No QA3 equation is numbered.

## 5. Ambiguities and external dependencies

1. **Eq. 47 typo (p.63):** "SC̄_wp,i,t" should be SOC̄_wp,i,t.
2. **Eq. 55 typo (p.65):** "CH4_ent̄_p,i,t" should be the wp subscript defined in the Where list.
3. **Eq. 76 Where list (p.91):** "ΔCO2_bsl,i,t" has a stray i. **Eq. 78 Where list (p.91):** "VC_CR,t" should be VCU_CR,t.
4. **LE_OA,t (Eqs. 39, 42)** is not defined on pp. 60–61. It is defined in 8.4.1, Eq. 33 (p.55). **LK_disp,t** is a C&C insertion (8.4.2/8.4.3, pp. 55–57). **LE_BR,t** comes from 8.4.4 / CDM TOOL16 (p.58).
5. **Percent vs fraction:** Eq. 74 yields UNC in **%**, but Eqs. 37/44/45 use UNC as a **fraction 0–1**. The ÷100 conversion is implied, not stated.
6. **Per-ha vs total mismatch:** Eq. 74 uses Δ̄·_t (t CO2e/ha) with s²_{Δ̄·,t} in (t CO2e/ha)². Eq. 70's output is per-ha (via 1/A²), but its stratum inputs are totals (t CO2e)². This is consistent only if A is the total project area. A, A_h, n, n_h, L and H are not defined in the 8.6.2 Where lists.
7. **Eq. 72 sub-equations (p.85):**
   - SOC̄_wp,h,f is printed as (1/A_h)·Σ over points. 1/n_h may be intended.
   - The Where list says SOC̄_wp,h,f is "in the lth simulation" but carries no l index.
   - Subscript order is inconsistent ("h,f,ip,l" vs "h,ip,f,l").
   - The text on p.86 writes "s²_{SOC,wp,hf,model}" (missing comma).
8. **Eq. 73 (p.86):** it is multiplied by A² (project area squared?), but the result is described as the same across all strata. How it combines with per-stratum A_h²-scaled sampling variances is not stated.
9. **Confidence level wording:**
   - The methodology says 0.667 / 66.7% (Where list), 66.6% (text and figure) and 33.3rd percentile (caption).
   - "≈ 0.4307 at large sample sizes" matches the normal quantile at p = 2/3 (0.4307). At p = 0.667 exactly it is 0.4316.
   - Degrees of freedom are "appropriate to the sampling design" and are not specified.
   - The authoritative reference is VCS Methodology Requirements Section 2.4 (p.88).
10. **Baseline control-site variance (s²_{ΔSOC,bsl,h,t})** has no explicit formula. It "presumes" the same estimator as Eq. 71 (p.83).
11. **Sign of UNC when Δ̄·_t ≤ 0:** Eq. 74 divides by Δ̄·_t. No handling of zero or negative mean ERR is given. The I(ΔCO2_soil_t) sign switch in Eqs. 44/45 is the only conservative-sign rule.
12. **Buffer (Eqs. 75/76):** NPR% depends on the VCS Standard / AFOLU Non-Permanence Risk Tool (not named here; fn 59 cites VCS Standard v4.7 §3.2.10). The methodology states no floor at zero for Bu_ER,t, Bu_CR,t or VCUs. **[Observation, not methodology text:]** MIN(0,wp) − MIN(0,bsl) and MAX(0,wp) − MAX(0,bsl) can be negative (for example, when the project loses more carbon than the baseline), which would give a negative buffer. The implementer must decide how to handle this, or confirm the behaviour with Verra.
13. **No rounding, caps or vintage rules** in 8.7. These presumably follow the VCS Standard / Registration and Issuance Process.
14. **Uncertainty is not applied to tree/shrub biomass, fossil fuel, liming, enteric, manure or biomass-burning terms** in Eqs. 37/44/45. Only the SOC (UNC_t,CO2) and QA1 CH4/N2O soil terms carry UNC. For QA3 the conservativeness is handled by choosing the EF (p.87).
15. **Equation cross-references** (Figure 5 vs 4, Figure 6 vs 5, Eq. "(70)", "(72)") were updated by the C&C. The corrected numbering is used here. Section 8.6.1 (Eqs. 60–69) and Appendix 4 (spectroscopy calibration/PPD) and Appendix 6 (multi-stage example) are required for a complete implementation but are outside these pages.
