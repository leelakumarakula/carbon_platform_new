# VM0042 v2.2 (with June 2026 C&C tracked changes): Part 2, Sections 8.2.2 to 8.4.4

Source: `VM0042_v2.2_with_CC_tracked.pdf`, PDF pages 42 to 57 (the printed page numbers match the PDF page numbers). The tail of 8.4.4 is on p.58 and was included.
Method: I rendered each page to an image and transcribed it by eye. Where a tracked change replaces text, only the corrected (new) text is used. Most C&C edits on these pages only refresh cross-reference fields ("Table 3", "(10)"); they do not change any maths. The exceptions are noted where they occur.

Notation conventions used here:
- `overline{X}` is the "areal mean" symbol, printed with a bar over it (per-hectare value).
- Subscripts are written exactly as printed, typos included. Typos are noted rather than silently fixed.
- Several equations print a dotless "ı" in subscripts (e.g. `bsl,ı,t`). This is a math-font rendering of `i`, not a different index. It is written as `i` below.

---

## 1. Equations

### Eq. (5), Section 8.2.1 (end of the SOC section; it sits on p.42 so it is included here)

```
SOC_{bsl,i,t} = f(SOC_{bsl,i,t})
```
(Printed with a script-f, meaning "modeled value of".) Used under Quantification Approach 1, following VMD0053.

| Variable | Definition | Unit |
|---|---|---|
| SOC_{bsl,i,t} | Estimated carbon stocks in the SOC pool in the baseline scenario for quantification unit i at the end of year t | t CO2e/ha |
| f(SOC_{bsl,i,t}) | Modeled SOC stocks in the baseline scenario for quantification unit i in year t, calculated by modeling SOC stock changes over the course of the preceding year | t CO2e/ha |
| i | Quantification unit | n/a |

### 8.2.2 Change in carbon stocks in aboveground and belowground woody biomass (p.42): no equation
- This section applies where woody biomass is in the project boundary per Table 3.
- ΔC_{TREE,bsl,i,t} (trees) and ΔC_{SHRUB,bsl,i,t} (shrubs) are calculated with these CDM A/R tools:
  - *Estimation of carbon stocks and change in carbon stocks of trees and shrubs in A/R CDM project activities*
  - *Simplified baseline and monitoring methodology for small scale CDM afforestation and reforestation project activities implemented on lands other than wetlands*
- The ARR requirements of the latest *VCS Methodology Requirements* apply. Footnote 39 recommends VM0047 for projects where woody biomass is the primary activity.
- If woody biomass is harvested, the long-term average GHG benefit must be calculated per VCS Methodology Requirements Section 3.6 and VCS Standard Section 3.2.

### Eq. (6), Section 8.2.3 Fossil fuel CO2 (p.42). Quantification Approach 3.

```
overline{CO2_ff}_{bsl,i,t} = ( Σ_{j=1}^{J} EFF_{bsl,j,i,t} ) / A_i
```

| Variable | Definition | Unit |
|---|---|---|
| overline{CO2_ff}_{bsl,i,t} | Areal mean carbon dioxide emissions from fossil fuel combustion in the baseline scenario for quantification unit i in year t | t CO2e/ha |
| EFF_{bsl,j,i,t} | Carbon dioxide emissions from fossil fuel combustion in the baseline scenario in vehicle/equipment type j for quantification unit i in year t | t CO2e |
| A_i | Area of quantification unit i | ha |
| j | Type of fossil fuel (gasoline, diesel or other) | n/a |

Note: the printed symbol is `CO_2_ff` (subscript 2 on CO) with a bar over it.

### Eq. (7), Section 8.2.3 (p.43)

```
EFF_{bsl,j,i,t} = FFC_{bsl,j,i,t} × EF_{CO2,j}
```

| Variable | Definition | Unit |
|---|---|---|
| FFC_{bsl,j,i,t} | Consumption of fossil fuel type j for quantification unit i in year t | liters |
| EF_{CO2,j} | Emission factor for combustion of fossil fuel type j | t CO2e/liter |

### Eq. (8), Section 8.2.4 Liming CO2 (p.43). Quantification Approach 3; applies only when liming is not de minimis.

```
overline{CO2_lime}_{bsl,i,t} = EL_{bsl,i,t} / A_i
```

| Variable | Definition | Unit |
|---|---|---|
| overline{CO2_lime}_{bsl,i,t} | Areal mean carbon dioxide emissions from liming in the baseline scenario for quantification unit i in year t | t CO2e/ha |
| EL_{bsl,i,t} | Carbon dioxide emissions from liming in the baseline scenario for quantification unit i in year t | t CO2e |

### Eq. (9), Section 8.2.4 (p.43 to 44)

```
EL_{bsl,i,t} = ( (M_{Limestone,bsl,i} × EF_{Limestone}) + (M_{Dolomite,,bsl,i} × EF_{Dolomite}) ) × 44/12
```
(The double comma in `Dolomite,,bsl,i` is printed that way and is a typo.)

| Variable | Definition | Unit |
|---|---|---|
| M_{Limestone,bsl,i} | Amount of calcitic limestone (CaCO3) applied to quantification unit i in year t | tonnes |
| EF_{Limestone} | Emission factor for calcitic limestone (0.12) | t C/t of limestone |
| M_{Dolomite,bsl,i} | Amount of dolomite (CaMg(CO3)2) applied to quantification unit i in year t | tonnes |
| EF_{Dolomite} | Emission factor for dolomite (0.13) | t C/t of dolomite |
| 44/12 | Molar mass ratio of CO2 to C, applied to convert CO2-C emissions to CO2 emissions | n/a |

### Eq. (10), Section 8.2.5 CH4 from the SOC pool (p.44). Quantification Approach 1 (model).

```
overline{CH4_soil}_{bsl,i,t} = GWP_{CH4} × f(CH4_soil_{bsl,i,t})
```

| Variable | Definition | Unit |
|---|---|---|
| overline{CH4_soil}_{bsl,i,t} | Areal mean methane emissions from SOC pool in the baseline scenario for quantification unit i in year t | t CO2e/ha |
| f(CH4_soil_{bsl,i,t}) | Modeled methane emissions from soil in the baseline scenario for quantification unit i in year t, calculated by modeling soil methane fluxes over the course of the preceding year | t CO2e/ha (as printed; see ambiguity A1) |
| GWP_{CH4} | Global warming potential for CH4 | t CO2e/t CH4 |

### Eq. (11), Section 8.2.6 Enteric fermentation CH4 (p.44). Quantification Approach 3.
Per the IPCC 2019 Refinement, results must be differentiated by livestock type, manure management system and productivity system.

```
overline{CH4_ent}_{bsl,i,t} = ( GWP_{CH4} × Σ_{l=1}^{L} Pop_{bsl,l,i,t,P} × EF_{ent,l,P} / 1000 ) / A_i
```
LaTeX: `\overline{CH4\_ent}_{bsl,i,t} = \left(\frac{GWP_{CH4}\times\sum_{l=1}^{L} Pop_{bsl,l,i,t,P}\times EF_{ent,l,P}}{1000}\right)/A_i`

| Variable | Definition | Unit |
|---|---|---|
| overline{CH4_ent}_{bsl,i,t} | Areal mean methane emissions from livestock enteric fermentation in the baseline scenario for quantification unit i in year t | t CO2e/ha |
| Pop_{bsl,l,i,t,P} | Population of grazing livestock of type l in quantification unit i for productivity system P in year t in the baseline scenario | head numbers |
| EF_{ent,l,P} | Enteric fermentation emission factor for livestock type l in productivity system P | kg CH4/(head × year) |
| l | Type of livestock | n/a |
| P | Productivity system | n/a |
| 1000 | Conversion factor from kg to t | n/a |

### Eq. (12), Section 8.2.7 Manure deposition CH4 (p.45). Quantification Approach 3.

```
overline{CH4_md}_{bsl,i,t} = GWP_{CH4} × Σ_{l=1}^{L} ( Pop_{bsl,l,i,t,P} × VS_{l,i,t,P} × AWMS_{l,i,t,P,S} × EF_{CH4,md,l,P,S} ) / (10^6 × A_i)
```
LaTeX: `\overline{CH4\_md}_{bsl,i,t} = \frac{GWP_{CH4}\times\sum_{l=1}^{L}(Pop_{bsl,l,i,t,P}\times VS_{l,i,t,P}\times AWMS_{l,i,t,P,S}\times EF_{CH4,md,l,P,S})}{10^6\times A_i}`

| Variable | Definition | Unit |
|---|---|---|
| overline{CH4_md}_{bsl,i,t} | Baseline areal mean CH4 emissions from manure deposition in the baseline scenario for quantification unit i in year t | t CO2e/ha |
| VS_{l,i,t,P} | Average volatile solids excretion per head for livestock type l in quantification unit i for productivity system P in year t | kg volatile solids/head (C&C correction: the old unit "kg volatile solids/(head × day)" is struck out) |
| AWMS_{l,i,t,P,S} | Fraction of total annual volatile solids for each livestock type l in quantification unit i that is managed in manure management system S in the project area, for productivity system P | dimensionless |
| EF_{CH4,md,l,P,S} | Emission factor for methane emissions from manure deposition for livestock type l for productivity system P in manure management system S | g CH4/kg volatile solids |
| S | Manure management system | n/a |
| 10^6 | Conversion factor from grams to tonnes | n/a |

### Eq. (13), Section 8.2.7 (p.45)

```
VS_{l,i,t,P} = ( VS_{rate,l,P} × W_{bsl,l,i,t,P} / 1000 ) × 365
```

| Variable | Definition | Unit |
|---|---|---|
| VS_{rate,l,P} | Default volatile solids excretion rate for livestock type l for productivity system P | kg volatile solids/(1000 kg animal mass × day) |
| W_{bsl,l,i,t,P} | Average weight in the baseline scenario of livestock type l for quantification unit i in productivity system P in year t | kg animal mass/head |
| 1000 | Conversion factor kg per tonne | n/a |
| 365 | Days per year | n/a |

### Eq. (14), Section 8.2.8 Biomass burning CH4 (p.46). Quantification Approach 3.

```
overline{CH4_bb}_{sl,i,t} = ( GWP_{CH4} × Σ_{c=1}^{C} MB_{bsl,c,i,t} × CF_c × EF_{c,CH4} / 10^6 ) / A_i
```
The left-hand side is printed with subscript `sl,ı,t`, which drops the "b". This is a typo for `bsl,i,t`; the Where list uses `bsl,i,t`. I checked this on a 4x zoom.
LaTeX: `\overline{CH4\_bb}_{bsl,i,t} = \left(\frac{GWP_{CH4}\times\sum_{c=1}^{C} MB_{bsl,c,i,t}\times CF_c\times EF_{c,CH4}}{10^6}\right)/A_i`

| Variable | Definition | Unit |
|---|---|---|
| overline{CH4_bb}_{bsl,i,t} | Methane emissions in the baseline scenario from biomass burning for quantification unit i in year t | t CO2e/ha |
| MB_{bsl,c,i,t} | Mass of agricultural residues of type c burned in the baseline scenario for quantification unit i in year t | kg |
| CF_c | Combustion factor for agricultural residue type c | proportion of pre-fire fuel biomass consumed |
| EF_{c,CH4} | Methane emission factor for the burning of agricultural residue type c | g CH4/kg dry matter burned |
| c | Type of agricultural residue | n/a |
| 10^6 | Conversion factor from grams to tonnes | n/a |

### Section 8.2.9 N2O from N fertilizers and N-fixing species (p.46 to 49)
- Quantification Approach 1 uses Eq. (15).
- Quantification Approach 3 uses Eqs. (16) to (25). The C&C edit only refreshed the "(25)" cross-reference field.
- The text says quantification "must be differentiated by livestock type, manure management system, and productivity system", which reads oddly for fertilizer (see A5).

#### Eq. (15), Quantification Approach 1 (p.46)

```
overline{N2O_soil}_{bsl,i,t} = GWP_{N2O} × f(N2O_soil_{bsl,i,t})
```

| Variable | Definition | Unit |
|---|---|---|
| overline{N2O_soil}_{bsl,i,t} | Areal mean direct and indirect nitrous oxide emissions due to nitrogen inputs to soils in the baseline scenario for quantification unit i in year t | t CO2e/ha |
| f(N2O_soil_{bsl,i,t}) | Modeled nitrous oxide emissions from soil in the baseline scenario for quantification unit i in year t, calculated by modeling soil fluxes of nitrogen forms over the course of the preceding year | t N2O/ha |
| GWP_{N2O} | Global warming potential for N2O | t CO2e/t N2O |

Under Quantification Approach 1, the modeled N2O covers fertilizers, manure deposition and N-fixing species together (p.46 text).

#### Eq. (16), Quantification Approach 3 (p.47)

```
N2O_soil_{bsl,i,t} = N2O_fert_{bsl,i.t} + N2O_md_{bsl,i,t} + N2O_Nfix_{bsl,i,t}
```
The term `i.t` (a period instead of a comma) is printed that way and is a typo. This equation's terms are printed without the overbar.

| Variable | Definition | Unit |
|---|---|---|
| N2O_soil_{bsl,i,t} | Nitrous oxide emissions due to nitrogen inputs to soils in the baseline scenario for quantification unit i in year t | t CO2e/ha |
| N2O_fert_{bsl,i,t} | Nitrous oxide emissions due to fertilizer use in the baseline scenario for quantification unit i in year t | t CO2e/ha |
| N2O_md_{bsl,i,t} | Nitrous oxide emissions due to manure deposition in the baseline scenario for quantification unit i in year t | t CO2e/ha |
| N2O_Nfix_{bsl,i,t} | Nitrous oxide emissions from crop residues due to the use of N-fixing species in the baseline scenario for quantification unit i in year t | t CO2e/ha |

#### Eq. (17) (p.47). Fertilizer N2O, used with Eqs. (17) to (23).

```
N2O_fert_{bsl,i,t} = N2O_fert_{bsl,direct,i,t} + N2O_fert_{bsl,indirect,i,t}
```

| Variable | Definition | Unit |
|---|---|---|
| N2O_fert_{bsl,direct,i,t} | Direct nitrous oxide emissions due to fertilizer use in the baseline scenario for quantification unit i in year t | t CO2e/ha |
| N2O_fert_{bsl,indirect,i,t} | Indirect nitrous oxide emissions due to fertilizer use in the baseline scenario for quantification unit i in year t | t CO2e/ha |

#### Eq. (18), direct (p.47)

```
overline{N2O_fert}_{bsl,direct,i,t} = ( (FSN_{bsl,i,t} + FON_{bsl,i,t}) × EF_{Ndirect} × 44/28 × GWP_{N2O} ) / A_i
```

#### Eq. (19) (p.47)

```
FSN_{bsl,i,t} = Σ_{SF} M_{bsl,SF,i,t} × NC_{SF}
```

#### Eq. (20) (p.48)

```
FON_{bsl,i,t} = Σ_{OF} M_{bsl,OF,i,t} × NC_{OF}
```

Where list for Eqs. (18) to (20) (p.48):

| Variable | Definition | Unit |
|---|---|---|
| overline{N2O_fert}_{bsl,direct,i,t} | Areal mean direct nitrous oxide emissions due to fertilizer use in the baseline scenario for quantification unit i in year t | t CO2e/ha |
| FSN_{bsl,i,t} | Synthetic N fertilizer applied to quantification unit i in year t in the baseline scenario | t N |
| FON_{bsl,i,t} | Organic N fertilizer applied to quantification unit i in year t in the baseline scenario | t N |
| EF_{Ndirect} | Emission factor for nitrous oxide emissions from N additions from synthetic fertilizers, organic amendments, and crop residues | t N2O-N/t N applied |
| M_{bsl,SF,i,t} | Mass of N-containing synthetic fertilizer type SF applied to quantification unit i in year t in the baseline scenario | t fertilizer |
| NC_{SF} | N content of synthetic fertilizer type SF | t N/t fertilizer |
| M_{bsl,OF,i,t} | Mass of N-containing organic fertilizer type OF applied to quantification unit i in year t in the baseline scenario | t fertilizer |
| NC_{OF} | N content of organic fertilizer type OF | t N/t fertilizer |
| SF | Synthetic N fertilizer type | n/a |
| OF | Organic N fertilizer type | n/a |
| 44/28 | Molar mass ratio of N2O to N, applied to convert N2O-N emissions to N2O emissions | n/a |

#### Eq. (21), indirect (p.48)

```
overline{N2O_fert}_{bsl,indirect,i,t} = ( N2O_fert_{bsl,volat,i,t} + N2O_fert_{bsl,leach,i,t} ) / A_i
```

#### Eq. (22) (p.48)

```
N2O_fert_{bsl,volat,i,t} = [ (FSN_{bsl,i,t} × Frac_{GASF,l,S}) + (FON_{bsl,i,t} × Frac_{GASM,l,S}) ] × EF_{Nvolat} × 44/28 × GWP_{N2O}
```

#### Eq. (23) (p.48)

```
N2O_fert_{bsl,leach,i,t} = (FSN_{bsl,i,t} + FON_{bsl,i,t}) × Frac_{LEACH,l,S} × EF_{Nleach} × 44/28 × GWP_{N2O}
```
In Eqs. (22) and (23), the Frac terms carry subscripts `l,S` in the equation, but the Where list defines them without subscripts. I checked this on a zoom. See A6.

Where list for Eqs. (21) to (23) (p.48 to 49):

| Variable | Definition | Unit |
|---|---|---|
| overline{N2O_fert}_{bsl,indirect,i,t} | Areal mean indirect nitrous oxide emissions due to fertilizer use in the baseline scenario for quantification unit i in year t | t CO2e/ha |
| N2O_fert_{bsl,volat,i,t} | Indirect nitrous oxide emissions produced from atmospheric deposition of N volatilized due to fertilizer use in the baseline scenario in quantification unit i in year t | t CO2e |
| N2O_fert_{bsl,leach,i,t} | Indirect nitrous oxide emissions produced from leaching and runoff of N, in regions where leaching and runoff occurs, due to fertilizer use in the baseline scenario in quantification unit i in year t | t CO2e |
| Frac_{GASF} | Fraction of all synthetic N added to soils that volatilizes as NH3 and NOx | dimensionless |
| Frac_{GASM} | Fraction of all organic N added to soils and N in manure and urine deposited on soils that volatilizes as NH3 and NOx | dimensionless |
| EF_{Nvolat} | Emission factor for nitrous oxide emissions from atmospheric deposition of N on soils and water surfaces | t N2O-N/(t NH3-N + NOx-N volatilized) |
| Frac_{LEACH} | Fraction of N (synthetic or organic) added to soils and in manure and urine deposited on soils that is lost through leaching and runoff, in regions where leaching and runoff occurs | dimensionless |
| EF_{Nleach} | Emission factor for nitrous oxide emissions from leaching and runoff | t N2O-N/t N leached and runoff |

#### Eq. (24), N-fixing species (p.49)

```
overline{N2O_Nfix}_{bsl,i,t} = ( F_{CR,bsl,i,t} × EF_{Ndirect} × 44/28 × GWP_{N2O} ) / A_i
```

| Variable | Definition | Unit |
|---|---|---|
| overline{N2O_Nfix}_{bsl,i,t} | Areal mean nitrous oxide emissions from crop residues due to the use of N-fixing species in the baseline scenario for quantification unit i in year t | t CO2e/ha |
| F_{CR,bsl,i,t} | Amount of N in N-fixing species (above- and belowground) returned to soils in the baseline scenario for quantification unit i in year t | t N |

#### Eq. (25) (p.49)

```
F_{CR,bsl,i,t} = Σ_{g=1}^{G} MB_{g,bsl,i,t} × N_{content,g}
```

| Variable | Definition | Unit |
|---|---|---|
| MB_{g,bsl,i,t} | Annual dry matter (above- and belowground) of N-fixing species g returned to soils for quantification unit i in year t | t d.m. |
| N_{content,g} | Fraction of N in dry matter for N-fixing species g | t N/t d.m. |
| g | Type of N-fixing species | n/a |

### Section 8.2.10 N2O from manure deposition (p.50 to 51). Quantification Approach 3, Eqs. (26) to (31).

#### Eq. (26) (p.50)

```
overline{N2O_md}_{bsl,i,t} = N2O_md_{bsl,direct,i,t} + N2O_md_{bsl,indirect,i,t}
```

| Variable | Definition | Unit |
|---|---|---|
| overline{N2O_md}_{bsl,i,t} | Areal mean nitrous oxide emissions due to manure deposition in the baseline scenario for quantification unit i in year t | t CO2e/ha |
| N2O_md_{bsl,direct,i,t} | Direct nitrous oxide emissions due to manure deposition in the baseline scenario for quantification unit i in year t | t CO2e/ha |
| N2O_md_{bsl,indirect,i,t} | Indirect nitrous oxide emissions due to manure deposition in the baseline scenario for quantification unit i in year t | t CO2e/ha |

#### Eq. (27), direct (p.50)

```
overline{N2O_md}_{bsl,direct,i,t,P,S} = ( Σ_{l=1}^{L} F_{bsl,manure,l,i,t,P} × EF_{N2O,md,l,S} × 44/28 × GWP_{N2O} ) / (1000 × A_i)
```

#### Eq. (28) (p.50)

```
F_{bsl,manure,l,i,t,P} = (Pop_{bsl,l,i,t} × Nex_{l,P}) × AWMS_{l,i,t,P,S} × MS_{bsl,l,i,t}
```
(Printed exactly as shown: `Pop` carries no `P` subscript here, unlike Eqs. (11) and (12).)

| Variable | Definition | Unit |
|---|---|---|
| overline{N2O_md}_{bsl,direct,i,t,P,S} | Areal mean direct nitrous oxide emissions due to manure deposition in the baseline scenario for quantification unit i for productivity system P and manure management system S in year t | t CO2e/ha |
| F_{bsl,manure,l,i,t,P} | Amount of nitrogen in manure and urine deposited on soils by livestock type l for productivity system P in quantification unit i in year t | t N (as printed; see A3) |
| Nex_{l,P} | Average annual nitrogen excretion per head of livestock type l for productivity system P | kg N deposited/(head × year) |
| EF_{N2O,md,l,S} | Emission factor for nitrous oxide from manure and urine deposited on soils by livestock type l for manure management system S | kg N2O-N/kg N input |
| MS_{bsl,l,i,t} | Baseline fraction of total annual N excretion for each livestock type l for quantification unit i in year t that is deposited on the project area | % (as printed; see A4) |
| 1000 | Conversion factor from kg to t | n/a |

#### Eq. (29), indirect (p.51)

```
overline{N2O_md}_{bsl,indirect,i,t} = ( N2O_md_{bsl,volat,i,t} + N2O_md_{bsl,leach,i,t} ) / A_i
```

#### Eq. (30) (p.51)

```
N2O_md_{bsl,volat,i,t} = F_{bsl,manure,l,i,t,P} × Frac_{GASM,l,S} × EF_{Nvolat} × 44/28 × GWP_{N2O}
```

#### Eq. (31) (p.51)

```
N2O_md_{bsl,leach,i,t} = F_{bsl,manure,l,i,t,P} × Frac_{LEACH,l,S} × EF_{Nleach} × 44/28 × GWP_{N2O}
```

| Variable | Definition | Unit |
|---|---|---|
| overline{N2O_md}_{bsl,indirect,i,t} | Areal mean indirect nitrous oxide emissions due to manure deposition in the baseline scenario for quantification unit i in year t | t CO2e/ha |
| N2O_md_{bsl,volat,i,t} | Indirect nitrous oxide emissions produced from atmospheric deposition of N volatilized due to manure deposition for quantification unit i in year t | t CO2e |
| N2O_md_{bsl,leach,i,t} | Indirect nitrous oxide emissions produced from leaching and runoff of N, in regions where leaching and runoff occurs, as a result of manure deposition for quantification unit i in year t. Equal to zero where annual precipitation is less than potential evapotranspiration, unless irrigation is employed | t CO2e |

### Eq. (32), Section 8.2.11 N2O from biomass burning (p.51 to 52). Quantification Approach 3.

```
overline{N2O_bb}_{bsl,i,t} = ( GWP_{N2O} × Σ_{c=1}^{C} MB_{bsl,c,i,t} × CF_c × EF_{c,N2O} / 10^6 ) / A_i
```

| Variable | Definition | Unit |
|---|---|---|
| overline{N2O_bb}_{bsl,i,t} | Areal mean nitrous oxide emissions in the baseline scenario from biomass burning for quantification unit i in year t | t CO2e/ha |
| EF_{c,N2O} | Nitrous oxide emission factor for the burning of agricultural residue type c | g N2O/kg dry matter burnt |
| 10^6 (p.52) | Conversion factor from grams to tonnes | n/a |

MB and CF_c are defined as in Eq. (14).

### Eq. (33), Section 8.4.1 Leakage from organic amendments (p.56)

```
LE_{OA,t} = Σ_{l} ( M_OA_{wp,l,t} × CC_{wp,oa,t} × 0.12 × 44/12 )
```

| Variable | Definition | Unit |
|---|---|---|
| LE_{OA,t} | Leakage from organic amendments in year t | t CO2e |
| M_OA_{wp,l,t} | Mass of organic amendment applied as fertilizer in the project area in year t, disaggregated by livestock type l for manure | tonnes |
| CC_{wp,oa,t} | Carbon content of organic amendment applied as fertilizer in the project area in year t, disaggregated by livestock type l for manure | t C/t organic amendment |
| 0.12 | Fraction of manure (i.e., organic amendment) carbon expected to remain in project area soils | unitless |
| 44/12 | Ratio of molecular weight of carbon dioxide to carbon | n/a |

### Eq. (34), Section 8.4.3, replacing VMD0054 v1.0 Eq. (5) (p.57)

```
l_{j,t} = FP_{j,t} − LM_{j,t}
```
VM0042 gives no Where list for this equation. The symbols l, FP and LM are defined in VMD0054. VM0042 changes l to mean "production change" instead of "foregone production", and removes "minimum value is zero" from its definition.

### Eq. (35), Section 8.4.3, replacing VMD0054 v1.0 Eq. (7) (p.57)

```
AL_t = MAX( Σ_{j=1}^{T} INL_{j,t} , 0 )
```
VM0042 gives no Where list here either; AL and INL are defined in VMD0054. The sum runs over j = 1..T as printed. The purpose is to count only area with net land conversion (AL > 0), so that net land sparing never produces positive leakage.

### Eq. (36), Section 8.4.3, step 4 (p.57). Uses the outcome of VMD0054 v1.0 Eq. (10).

```
LK_{disp,t} = MAX(0, LK_t − LK_{prior}) / years
```

| Variable | Definition | Unit |
|---|---|---|
| LK_{disp,t} | Leakage emissions from displaced production in year t. C&C correction: the old wording "livestock displacement" is struck out | t CO2e |
| LK_t | Cumulative leakage up to year t calculated using VMD0054 | t CO2e |
| LK_{prior} | Cumulative leakage between y = 0 and the previous verification event, calculated using VMD0054 | t CO2e |
| years | Duration of the verification period | years |

Total: 32 numbered equations on these pages, Eqs. (5) through (36). Eq. (5) technically belongs to 8.2.1. No equation was unreadable.

---

## 2. Default values, emission factors, GWPs and constants

The values in the first table are printed on pp.42 to 57. Sources marked "param table" come from the Section 9 parameter tables, which are outside my page range. I verified pp.93, 94, 107, 108, 109 and 126 visually; the rest come from the text copy.

| Item | Value | Source as cited | Page |
|---|---|---|---|
| EF_{Limestone} | 0.12 t C/t limestone | In-line in Eq. (9) Where list. Param table: "Section 11.3, Chapter 11, Volume 4 in IPCC (2019)" | 43; 109 |
| EF_{Dolomite} | 0.13 t C/t dolomite | Same as above | 44; 109 |
| 44/12 | CO2:C molar ratio | Constant | 44, 56 |
| 44/28 | N2O:N molar ratio | Constant | 48 |
| 1000 | kg to t (Eqs. 11, 27); kg per tonne (Eq. 13) | Constant | 45, 50 |
| 10^6 | g to t (Eqs. 12, 14, 32) | Constant | 45, 46, 52 |
| 365 | days/year (Eq. 13) | Constant | 45 |
| 0.12 (manure C retention) | Fraction of applied organic-amendment C remaining in soil | "global manure C retention coefficient from Maillard and Angers (2014)". Also applied "conservatively" to compost and biosolids | 55 to 56 |
| De minimis threshold | < 5% of total net anthropogenic reductions and removals (leakage sources). Section 5 (p.~14, text copy) gives < 5% of total GHG benefit for pools and sources | CDM *Tool for testing significance of GHG emissions in A/R CDM project activities* | 54 to 55 |
| GWP_{CH4} | 28 t CO2e/t CH4 | param table: "IPCC Fifth Assessment Report (IPCC, 2013)". GWPs "must be applied as described in the most recent version of the VCS Standard" | 93 (verified) |
| GWP_{N2O} | 265 t CO2e/t N2O | param table: IPCC AR5 (IPCC, 2013), same VCS Standard caveat | ~95 (text copy) |
| EF_{CO2,j} gasoline | 0.002810 t CO2e/liter | param table. Source: Table 3.3.1, Ch 3, Vol 2, IPCC (2019). Assumes a four-stroke engine and energy content of 47.1 GJ/t (IEA 2004) | 108 (verified) |
| EF_{CO2,j} diesel | 0.002886 t CO2e/liter | Same as above; 45.66 GJ/t | 108 (verified) |
| EF_{ent,l,P} | no number given | Derive per IPCC 2019 Vol 4 Ch 10 Sec 10.3.2, or Tier 1 from Tables 10.10/10.11 (with Annex 10A.1) | ~110 |
| VS_{rate,l,P} | no number given | IPCC 2019 Vol 4 Ch 10 Eq 10.24, or Tier 1/1a Table 10.13a | ~115 |
| W_{bsl,l,i,t,P} | no number given | Box 1, or Tier 1 Table 10A.5, Ch 10, Vol 4 | 94 (verified) |
| AWMS | no number given | Tier 1 Tables 10A.6 to 10A.9, Ch 10, Vol 4 | ~113 |
| EF_{CH4,md,l,P,S} | no number given | Tier 1/1a Tables 10.14 and 10.15, Ch 10, Vol 4 | ~114 |
| S (manure management system) | n/a | Table 10.18, Ch 10, Vol 4. Also footnote 45, p.55 | ~114 |
| CF_c | no number given | Table 2.6, Ch 2, Vol 4, IPCC (2019) | ~116 |
| EF_{c,CH4} | no number given | Table 2.5, Ch 2, Vol 4 | ~117 |
| EF_{c,N2O} | no number given | Table 2.5, Ch 2, Vol 4 | ~132 |
| EF_{Ndirect} | no number given | Derive per Ch 11 Sec 11.2.1.1 and Ch 2 Sec 2.2.4, or "appropriate disaggregated Tier 1 value from Table 11.1, Chapter 11, Volume 4" | ~120 |
| Frac_{GASF}, Frac_{GASM}, EF_{Nvolat}, EF_{Nleach} | no number given | Table 11.3, Ch 11, Vol 4 | ~125 to 131 |
| Frac_{LEACH} | 0.24 for wet climates and for dry climates with irrigation (other than drip); 0 for all other dry climates | Table 11.3, Ch 11, Vol 4. Wet/dry definition: precip/PET > 1 (temperate/boreal), or > 1000 mm/yr (tropical) | 126 to 127 |
| N_{content,g} | no number given | Table 11.2, Ch 11, Vol 4 | ~128 |
| EF_{N2O,md,l,S} | no number given | Tier 1/1a Table 10.21, Ch 10, Vol 4 | ~130 |
| Nex_{l,P} | no number given | IPCC 2019 Ch 10 Eqs 10.31/10.31a, or Tier 1/1a Table 10.19 | ~130 |
| MS_{bsl,l,i,t} | 1 may be applied with no further support (conservatively assumes 100% deposition on the project area) | param table comment | ~97 |
| P (productivity system) | n/a | IPCC 2019 Vol 4 Ch 10 Sec 10.2 "Definitions of High and Low Productivity Systems" | ~112 |

Emission-factor hierarchy for Quantification Approach 3 (8.3, p.53 to 54), in descending preference:
1. A project-specific EF from a peer-reviewed publication. Footnote 41: the journal must be indexed in Web of Science Science Citation Index, per VCS Methodology Requirements Section 2.5.
2. Alternative sources (government databases, industry publications), with evidence of robustness such as an independent expert attestation.
3. Tier 2 EFs derived from project activity data per the IPCC 2019 Refinement.
4. Tier 1 or Tier 1a IPCC 2019 Refinement EFs, only where the proponent justifies a lack of data.

Parameter tables also require the EF data source to be re-checked every five years.

---

## 3. Project emissions (8.3, p.52 to 54) and how they relate to the baseline equations

- **Same equations, project data.** Project CO2, CH4 and N2O are quantified using the approaches in Table 5 and the equations of Section 8.2. In every equation, the subscript `bsl` is replaced by `wp` (with-project). No separate project-emission equations are printed. For example, Eq. (7) becomes `EFF_{wp,j,i,t} = FFC_{wp,j,i,t} × EF_{CO2,j}`.
- **Livestock floor.** Per 8.4.2, where livestock are in the baseline, the project must use at least the average livestock value from the historical look-back period.
- **Quantification Approach 1 (model).** Model inputs follow Table 8 (p.52 to 53):

  | Input | Timing | Requirement |
  |---|---|---|
  | SOC content | t=0, by direct measurement or (back-)modeled from measurements within ±5 yr; remeasure at least every 5 yr | Lab or proximal sensing (INS, LIBS, MIR, Vis-NIR) with known uncertainty, per Appendix 4 and VMD0053 |
  | Bulk density (initial) | Before intervention, at t=0 or within ±5 yr | See Section 8.2.1.5 |
  | Other soil properties | Ex ante | Measured, or from published soil maps with known uncertainty; must be representative/unbiased and follow best practice |
  | Climate | Continuously monitored ex post at the model's temporal resolution | Nearest weather station within 50 km, or a synthetic station such as PRISM |
  | ALM activities | Monitored ex post for each year t | Farmer/landowner signed attestation plus documentary evidence |

- **Quantification Approach 2 (measured).** Used for SOC stocks only.
  - C&C addition: baseline control sites and the project area must be remeasured at least every five years, or before each verification where verification is more frequent.
  - SOC_{wp,i,t} is calculated on an equivalent soil mass (ESM) basis using SOC content at t−1 measured in each sample field. Mass corrections are allowed where bulk density was measured at fixed depth.
  - References: Wendt & Hauser (2013) and von Haden et al. (2020). SOC changes use Eqs. (3) to (5).
- **Quantification Approach 3 (default factors).** Calculated for each sample field, using the EF hierarchy in section 2 above.
- **Woody biomass (project).** This rule differs from the baseline. Aboveground woody biomass **must** be included where project activities may significantly reduce this pool compared with the baseline; otherwise it is optional. It is calculated with the same two CDM A/R tools as 8.2.2. If harvested, the VCS MR 3.6 and VCS Standard 3.2 long-term average rules apply.
- **Downstream use (p.58, outside my range).** Baseline and project values are differenced into the Δ terms of Eq. (37), e.g. ΔCO2_ff_t and ΔCH4_ent_t.

---

## 4. Leakage rules (8.4, p.54 to 58)

**Overview.** There are four leakage types:
1. New organic amendments from outside the project area.
2. Livestock displacement.
3. Productivity / production declines.
4. Diversion of biomass residues from bioenergy.

**De minimis.** Per Section 5, if the sum of increases in GHG emissions from any leakage source is less than 5% of the project's total net anthropogenic reductions and removals, it may be deemed de minimis and ignored. This must be demonstrated with the CDM *Tool for testing significance of GHG emissions in A/R CDM project activities*.

### 8.4.1 New application of organic amendments from outside the project area: Eq. (33)
- **Applies when** new or additional manure, compost or biosolids are applied that were not applied in the historical look-back period. Footnotes 42 to 44:
  - "new" means the field had no organic amendment in the look-back period;
  - "additional" means the field had some, but the amount increases in the project scenario;
  - biosolids means treated sewage sludge.
- **A deduction is required unless any one of these applies:**
  1. The manure or compost is newly produced on-site from farms within the project area.
  2. The manure is documented to have been diverted from an uncontrolled anaerobic lagoon, pond, tank or pit with no methane recovery for heat or electricity. Footnote 45: temporary storage before field application should be aerobic, in stocks or piles.
  3. The manure, compost or biosolids are documented not to have been used as a soil amendment.
- **What the deduction represents:** amendment C that remains in project soils (12%, Maillard & Angers 2014) and would otherwise have gone to agricultural land outside the project area.

### 8.4.2 Livestock displacement
- **Trigger:** a decline in livestock population in the project scenario. CH4 and N2O from 8.2.6, 8.2.7 and 8.2.10 depend on population.
- **The proponent must do either (a) or (b):**
  - (a) Use the **baseline** livestock population to calculate with-project emissions, and quantify leakage with *VMD0054 Module for Estimating Leakage from ARR Activities*, per Eq. (36).
  - (b) Show that project commodity production (meat, dairy, fibre) did not decrease, and that livestock were slaughtered rather than displaced. Then project-scenario populations are used and LK_{disp,t} = 0 in Eq. (36).
- **If livestock production declines** relative to the baseline, the foregone production is handled under 8.4.3.

### 8.4.3 Production declines: Eqs. (34) to (36)
- **Applies to:** production declines in the initial project years (footnote 46: the producer adjusting to new practices), and to changes in overall crop or livestock products produced.
- **Method:** the most recent VMD0054, with these modifications:
  1. Read "ALM" / "Agricultural Land Management" for "ARR" / "Afforestation, Reforestation, and Revegetation", and "VM0042 Improved Agricultural Management" for "VM0047 Afforestation, Reforestation, and Revegetation".
  2. Replace VMD0054 v1.0 Eq. (5) with Eq. (34). This captures the land-sparing effect of new commodities: read "production change" for "foregone production" and drop "minimum value is zero". Footnote 47: or the equivalent equation in a newer VMD0054.
  3. Replace VMD0054 v1.0 Eq. (7) with Eq. (35), limited to net land conversion (AL > 0).
  4. Annualise VMD0054 v1.0 Eq. (10) output with Eq. (36): MAX(0, LK_t − LK_prior)/years.

### 8.4.4 Diversion of biomass residues used for energy in the baseline (p.57 to 58): no VM0042 equation
- **Applies where:** manure or crop residue management is part of the project activity, and the manure or residues are diverted from energy applications in the baseline (e.g. cookstove fuel, biomass power).
- **Method:** LE_{BR,Div,t} is determined by CDM **TOOL16: Project and leakage emissions from biomass**, Section "6,2" (printed with a comma) "Leakage due to diversion of biomass residues from other applications in year y".
  - Footnote 48: see the section "Leakage due to diversion of biomass residues from other applications" in the latest TOOL16.
  - Footnote 49: subscript t is used instead of y.

### How leakage is aggregated (outside my range, from the text copy only)
- Eq. (38) on p.59 is ER_NET,t = ER_t − LK_ER,t.
- Eq. (39) on p.59 allocates leakage (LK_ER,t) between reductions and removals using LE_BR,t, LK_disp,t and a third term. That term is garbled in the text copy and is probably LE_OA,t; the p.59 image needs to be checked.

---

## 5. Ambiguities, possible errata and external dependencies

| # | Issue | Page(s) |
|---|---|---|
| A1 | **Unit conflict in Eq. (10).** The Where list gives f(CH4_soil_{bsl,i,t}) in t CO2e/ha, but the parameter table (verified) gives **t CH4/ha**. Multiplying by GWP_CH4 is only correct if the model output is in t CH4/ha. Recommend implementing it as t CH4/ha. The N2O analogue, Eq. (15), is consistently t N2O/ha. | 44, 109 |
| A2 | **Eq. (14) subscript typo.** The left-hand side prints `sl,ı,t` where `bsl,i,t` is meant. | 46 |
| A3 | **Unit inconsistency for F_{bsl,manure} in Eqs. (27) to (31).** In Eq. (28), Pop (head) × Nex (kg N/head/yr) gives **kg N**, but the Where list says t N. Eq. (27) divides by 1000, which is consistent with kg. Eqs. (30) and (31) use the same F with no /1000 and claim t CO2e, so either Eq. (27) or Eqs. (30)/(31) is off by a factor of 1000 depending on F's true unit. Eq. (30) also uses Frac_GASM, defined per kg N, so the issue is not resolved there. | 50, 51 |
| A4 | **MS_{bsl,l,i,t} unit.** The Where list says "(%)", but the parameter table says "Fraction", with a default of 1 meaning 100%. Use a fraction from 0 to 1. | 50, ~97 |
| A5 | **Index handling.** P and S appear as subscripts but are never explicitly summed: Eq. (11) sums only over l, yet Pop and EF carry P; Eq. (12) carries P and S; Eq. (27)'s left-hand side has P,S while Eq. (26) uses a P,S-free direct term; Eq. (28)'s F omits S even though AWMS carries S. Implementers must decide to sum over P and S (implied by "differentiated by livestock type, manure management system, and productivity system"). The same sentence appears in 8.2.9 (fertilizer), where it reads like a copy-over. | 44, 45, 46, 50 |
| A6 | **Frac subscripts.** In Eqs. (22), (23), (30) and (31), Frac_{GASF}, Frac_{GASM} and Frac_{LEACH} carry `l,S` subscripts, but the Where lists and parameter tables define them without subscripts. Eqs. (30) and (31) also have F indexed by l and P, but their left-hand sides are indexed only by i,t, so the sum over l is implicit. | 48, 51 |
| A7 | **Eq. (9) time index.** M_{Limestone,bsl,i} and M_{Dolomite,,bsl,i} have no t subscript, but are defined "in year t". The double comma is a typo. | 43 |
| A8 | **Eq. (16).** `N2O_fert_{bsl,i.t}` is a period typo. Eq. (16)'s terms have no overbar, while Eqs. (18), (21) and (24) give the components as areal means with an overbar. All are t CO2e/ha. | 47 |
| A9 | **Frac_{LEACH} = 0 condition.** The Eq. (31) Where list says leaching is zero when precip < PET "unless irrigation is employed". The parameter table says 0.24 for dry climates with irrigation "other than drip", which implies drip-irrigated dry climates get 0. The two statements are slightly inconsistent. | 51, 126 |
| A10 | **Eq. (33) indexing and area basis.** CC_{wp,oa,t} has no l subscript, although it is defined as disaggregated by l. The equation is a project-total (t CO2e), with no A_i and no i index. | 56 |
| A11 | **Eqs. (34) and (35) depend on VMD0054 v1.0.** l, FP, LM, INL, AL and the T limit on the sum are defined only in VMD0054. Eq. (35) sums over j=1..T, so the index meaning comes from VMD0054. LK_t and LK_prior also come from VMD0054 Eq. (10). VMD0054 must be obtained to implement 8.4.3. | 57 |
| A12 | **Eq. (36) naming.** It is used for both livestock displacement (8.4.2) and production declines (8.4.3); the C&C renamed it to "displaced production". "years" means the verification-period length, so leakage is spread evenly across the years of the period. | 56 to 57 |
| A13 | **8.4.4 depends on CDM TOOL16.** It cites Section "6,2", probably 6.2, which may differ by TOOL16 version; footnote 48 says to use the latest TOOL16. The symbol is LE_{BR,Div,t} in 8.4.4 but LE_{BR,t} in Eq. (39). Footnote 49 refers to "Equation (38)" for the t subscript, but leakage appears in Eq. (39), so the reference may be stale. | 57 to 59 |
| A14 | **Woody biomass depends on two CDM A/R tools, VCS MR 3.6 and VCS Standard 3.2.** No equations are given in VM0042, and the ARR requirements of the VCS Methodology Requirements apply. | 42, 54 |
| A15 | **Quantification Approach 1 models depend on VMD0053**, plus Appendix 4 for the SOC measurement criteria. | 42, 52 |
| A16 | **GWP values.** The parameter tables state AR5 values (28, 265) but also say to apply them "as described in the most recent version of the VCS Standard", which could require different values. Confirm against the current VCS Standard. | 93 to 95 |
| A17 | **Fossil fuel j.** Eq. (6)'s Where list describes EFF as "in vehicle/equipment type j", but defines j as "Type of fossil fuel". The index is fuel type. | 42 to 43 |
| A18 | **Applicability conditions** come from Table 3 (boundary), Table 5 (allowed quantification approaches per source) and Section 5 (de minimis). These are outside pp.42 to 57. | 54 |
