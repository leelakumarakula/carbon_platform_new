# GS 403 – A/R GHG Emissions Reduction & Sequestration Methodology v2.1: implementation extract

Prepared 2026-10-05. Primary source: `GS_403_AR_Methodology_v2.1.pdf`. It is 17 PDF pages and the PDF page number equals the printed page number. It was published 16.05.2024 (next planned update 24.10.2025). Its MD5 matches the copy currently on globalgoals.goldstandard.org.
Page references: **[GS p.N]** = GS 403 v2.1; **[T14 p.N]** = CDM AR-TOOL14 v04.2 (printed "N of 31"); **[PR §x]** = GS GHG ER&S Product Requirements v3.2 (12.12.2025); **[LUF §x]** = GS LUF Activity Requirements v1.2.1; **[SB p.N]** = Winrock/BioCarbon Fund Sourcebook (printed page).
Equations were checked against page renders at 2x/5x, not just pdftotext, because the text layer garbles operators (`÷` and `×` come out as `�`).

---

## 0. Headline findings (read first)

1. **GS 403 v2.1 does not reference AR-TOOL14, AR-TOOL12, AR-TOOL15 or any other CDM A/R quantification tool.** The only CDM documents it cites are:
   - the additionality tools: CDM Tool 01, Tool 19 and Tool 21 [GS p.6–7];
   - AR-AM0014 v3.0, as the source of the mangrove soil carbon default [GS p.5].

   GS 403 quantifies removals with its own approach:
   - a **growth model per Modelling Unit (MU)**;
   - a **stem volume → biomass → CO2 conversion chain** (wood density × BEF × (1+R:S) × CF × 44/12) [GS p.9, 12–14];
   - the model is **confirmed or adjusted by MU-level forest inventories** run according to the **BioCarbon Fund Sourcebook** (Winrock) [GS p.15];
   - a precision rule of **±20 % at 90 % confidence, with the excess deducted** [GS p.15].

   I still transcribed AR-TOOL14 in full (§2.3) as you asked. It is useful as the statistical and per-tree engine, and it is what CCTS BM-T-AR-0004 copies. But under GS 403 it is **optional or informative, not mandatory**.
2. The GS documents listed in the brief ("A/R GHG calculation tool", 403.01–403.06) map onto files that do exist:
   - **403.01 Integrated (Consolidated) template**;
   - **403 0.1–0.6** section templates (Applicability, Baseline, Leakage, Other emissions, Carbon Performance, CO2-Fixation);
   - **0.7 Soil Carbon Tool** (xlsm);
   - **0.8 Rotation Forestry Projects Tool** (xlsx).

   None of the templates contains formulas beyond what is in the methodology. The only file with formulas is the Rotation Forestry tool, transcribed in §2.2.
3. **Carbon fraction for tree biomass is ambiguous in v2.1.** The text layer reads "0.475", but the rendered page shows **"0.47" followed by a struck-through "5"** [GS p.14, §3.10.1a]. v2.0 used **0.5**. The most likely intended value is **0.47**, which matches the IPCC default and AR-TOOL14. Confirm with GS before production.
4. **Paris Agreement Alignment (PAA) – regulatory risk.** GS document 119 (PAA P&R100-01 v1.2, published 02/10/2026) sets these rules:
   - GSVERs with vintages from **1 Jan 2026** must be quantified with a **PA-aligned** methodology.
   - New projects submitted after the **30 June 2026 sunset date** must use a PA-aligned methodology.
   - Projects certified under a non-PA methodology get **no 2026+ vintages** unless they complete a PAA design change.
   - LUF buffer and vintage guidance is "under development".

   As of today **no PA-aligned A/R methodology is listed** on the GS PAA documents page. GS 403 v2.1 is therefore usable as-is only for **pre-2026 vintages**, or for projects already in the pipeline that later go through PAA transition.

---

## 1. GS 403 structure

### 1.1 Definitions [GS p.3–4]
- **Tree**: a perennial woody plant with secondary growth. The definition includes shrubs, palms and bamboo. In any project, trees **shall reach a minimum height of 2 m**.
- **Forest**: as defined by the host-country DNA. If there is none, use the FAO or the national definition.
- **Wetland** (Cowardin 1979) and **organic soil** are defined by thresholds:
  - organic carbon >20 % by weight if never saturated;
  - if subject to saturation: >12 % with no clay, or >18 % with >60 % clay, with a proportional limit in between.
- **Modelling Unit (MU)**: a distinct part of the planting area where carbon stocks are quantified by applying a forest growth model. An MU normally has homogeneous growth pattern, silvicultural treatment and planting date. **The MU is the unit of stratification, accounting and precision.**

### 1.2 Applicability [GS p.4–5, §2.1]
- **Eligible land**: tree planting on land that does not meet the forest definition. The spatial forest/non-forest assessment follows LUF Annex C.
- **Silvicultural systems**: all are allowed – conservation forest, selective harvesting, rotation forestry. Agroforestry and silvopasture are allowed.
- **Land exclusions**:
  - project areas shall not be on wetlands (except mangrove projects, §2.1.3e);
  - organic soils shall not be drained or irrigated, except irrigation for planting;
  - soil disturbance on organic soils must be **< 10 %** of the area submitted for certification.
- **Baseline condition**: the baseline scenario shall show no *significant* increase in baseline biomass (tree and non-tree). **"Significant" means > 5 % of the long-term CO2 removal** (footnote 2, p.5; footnote 3, p.8).
- **Mangrove projects** (§2.1.3):
  - at least 90 % of the planting area must be planted with mangrove species;
  - **+1.8 tCO2/ha/yr SOC** may be accounted for in the **first 20 years after an MU is planted**. This is 0.5 tC/ha/yr from AR-AM0014 v3.0 converted to CO2, and applies unless other verifiable data exist;
  - **SOC is excluded from PERs**;
  - the wetland exclusion does not apply;
  - §2.1.3 lapses once a GS mangrove methodology exists.
- **Entry into force**: v2.1 is effective from publication. The previous version stays valid for 30 days, and projects already listed may keep using it [GS p.5].

### 1.3 Pools and sources – Table 1 [GS p.6]

| Pool | Includes | CO2-removal | Baseline | Leakage |
|---|---|---|---|---|
| Tree biomass – aboveground | stem, branches, bark | Yes | Yes | Yes |
| Tree biomass – belowground | tree roots | Yes | Yes | Yes |
| Non-tree biomass – aboveground | grass, herbs, etc. | **No** | Yes | No |
| Non-tree biomass – belowground | roots of grass, herbs | **No** | Yes | No |
| Soil | organic material | Optional | Optional | No |
| Harvested wood (timber & energy wood) | furniture, construction | No | No | No |
| Litter & lying dead wood | leaves, small branches, lying dead wood | No | No | No |

Further rules on pools:
- **Standing dead wood is part of tree biomass** (§3.1.2).
- Positive leakage and market leakage are **not** accounted (§3.1.3).
- Soil carbon may be accounted only via the **A/R Soil Carbon Tool**, and only on planting areas. The resulting GS-VERs can be issued only after a successful Performance Certification. **No PERs from soil** (§3.1.5) [GS p.6].

### 1.4 Additionality [GS p.6–7, §3.2]
- Regulatory surplus is required for all projects.
- Additionality is then demonstrated by one of:
  - the GS4GG Activity Requirements;
  - CDM Tool 01;
  - CDM Tool 19 (microscale – not applicable to GS microscale projects);
  - CDM Tool 21 (small-scale only);
  - an approved GS VER additionality tool.

### 1.5 Baseline [GS p.8–9, §3.4–3.5]
- **Definition**: the tree and non-tree biomass present in the eligible planting area **just prior to planting start**. It is a stock, not a trajectory.
- **Stratification**: by vegetation type.
- **Data sources**, in order of preference:
  1. project-specific values (from an inventory), regional values or national values;
  2. IPCC defaults, only if nothing else exists.
- **Accounting at MU level**: Eq. 3 converts the baseline to tCO2/ha, and it is **deducted only in year t=1** (§3.3.4c).
- **Baseline trees** are those identified within the project area. Losses of baseline trees must be accounted, preferably by census with numbered trees. If baseline trees were sampled, the need for that is assessed at design review.
- **Reporting and monitoring**:
  - baseline stock change is reported for the whole crediting period;
  - if design certification establishes that the baseline will not increase, monitoring is limited to confirming losses of baseline trees;
  - the baseline is **not reassessed at crediting period renewal** (§3.5.7).

  **Conflict:** LUF §3.1.12(c) [LUF p.16] says A/R projects shall update the baseline at renewal according to the methodology (see §5).

### 1.6 How removals are quantified [GS p.7–10, 12–15]
- **Yearly CO2 removal per MU** comes from a **growth model plus conversion factors**: wood density, BEF and R:S, all set per MU (§3.6.1–3.6.3, §3.9.2).
- Conversion factors are **not subject to monitoring** (§3.6.3).
- The growth model must reflect:
  - surviving baseline tree biomass (§3.6.4);
  - a realistic survival rate (§3.6.5).
- **Long-term CO2 removal** caps or averages the creditable stock (§3.6.6–3.6.12):
  - **Option 1 – selective harvesting or conservation forest**: tree biomass at MU equilibrium. If biomass is still increasing at the end of the crediting period, use the biomass in the year the crediting period ends.
  - **Option 2 – rotation forestry**: the average tree biomass between planting start and end of crediting period (Eq. 4). The RC 2020 rules apply in addition (see below).
- **Forest inventory** (§3.11) [GS p.15]:
  - MU-specific inventories confirm or adjust the growth model;
  - inventories follow the **BioCarbon Fund Sourcebook**, are documented so they can be replicated, and are repeated at least **before every Performance Certification**;
  - precision must be **≤ ±20 % at 90 % confidence**, otherwise the excess is deducted.
- **Submission**: all figures go in the GS templates (§3.3.5).
- **RC 2020 Rotation Forestry clarification** (02/04/2020):
  - the crediting period covers whole rotations (e.g. a 15-yr rotation gives a 30–45 yr crediting period);
  - the stand must remain standing at the end of the crediting period;
  - CO2 performance is assessed against the original growth model, not the long-term-average model;
  - performance verification must take place in the year before each felling.

### 1.7 Leakage [GS p.10–12, §3.7]
- **Categories**: (a) wood collection, (b) timber harvesting, (c) agriculture (crops, shrimp, etc.), (d) livestock. Only tree biomass affected outside the project area is counted.
- **Formulas**:
  - Eq. 6 for categories a, b and c (area × % activity shift × CO2 stock);
  - Eq. 7 for livestock (displaced heads × grazing capacity × CO2 stock).
- **Default CO2 stock**: if the displacement destination is unknown, use the average tree-biomass stock of **natural forest in the host country**.
- **Timing**: all leakage for the whole crediting period is deducted **in year 1**, so leakage is **not monitored** (§3.7.3–3.7.4).

### 1.8 Other emissions [GS p.12, §3.8]
- **Burning for site preparation**: deduct an additional **10 % of the Baseline**, at t=1. A lower value is allowed if justified.
- **Fertiliser**: **0.005 tCO2 per kg N**, synthetic or organic. It is deducted over time, in the year of use. A lower value is allowed if justified.
- **Fossil fuel**: insignificant, so neglected.
- **N-fixing species**: zero.

### 1.9 Uncertainty and conservativeness
- **Sampling precision**: ±20 % at 90 % confidence, with the excess deducted from the mean stem volume [GS p.15].
- **Conservative factor selection** (§3.9.9) [GS p.14]:
  - CO2 removal shall not be overestimated;
  - Baseline and Leakage shall not be underestimated.

  Hence the asymmetric default factors (§2.1.6 below).
- **Not specified in GS 403**: no allometric or model uncertainty, no ex-ante uncertainty deduction, no discount table.

### 1.10 Buffer, PERs vs GSVERs, crediting [PR §11, Annex C; LUF §3.1.9–3.1.12]
- **Buffer**:
  - **20 % of issued PERs and GSVERs** go to the GS Compliance Buffer, pro rata by vintage (PR §11.1.1–11.1.2);
  - where a project mixes sequestration with permanent reductions, the 20 % applies to the sequestration component only;
  - the buffer may be substituted with GSVERs from other GS projects, but only at an issuance event (PR Annex C §3).
- **PERs** (Planned Emission Reductions) (PR §11.2):
  - **Timing**: may be issued after Design Certification or any Performance Certification, for at most **5 years forward**. They are issued pro rata per year: **80 % to the project account and 20 % to the buffer**.
  - **Eligibility**: only from areas that have scientifically robust carbon modelling and where the VVB confirms planting.
  - **Exclusions**: none for SOC, none for permanent-reduction projects, and none for smallholder projects that use default values for baseline, leakage and CO2 fixation.
  - **Trading**: PERs can be transferred and assigned but **not retired**.
  - **Conversion**: at Performance Certification, PERs convert into **GSVERs** (ex-post verified). 20 % of the conversions take place in the buffer.
- **Carbon Performance** (PR §11.4):
  - at all times, PERs ≤ the project's expected (ex-ante) carbon stock, and GSVERs ≥ that stock;
  - **[UNCLEAR]** that is what the text says (§11.4.1a), but the GSVER clause looks inverted. The intent is presumably that issued GSVERs never exceed actual stocks;
  - a shortfall triggers the Performance Shortfall Guidelines: the project must recover within 5 years, and buffer units are put on hold.
- **Crediting period** (A/R) (LUF §3.1.9–3.1.12):
  - **30 to 50 years**, chosen by the developer;
  - starts at the later of the project start date and 3 years before Design Certification (also PR §10.2.1);
  - verification at least every 5 years;
  - crediting period renewal every 5th year (the 5-year certification cycle).
- **Issuance logic** (GS p.7, §3.3.3): removal units are cumulative. While net cumulative removal is ≤ 0 (because Baseline, Leakage and Other Emissions are front-loaded at t=1), no GSVERs are issued.

### 1.11 Monitoring and documentation [GS p.9, 15–16]
- **Monitored**:
  - forest inventories per MU (stem volume) before every Performance Certification;
  - survival and stand condition through the growth-model check;
  - losses of baseline trees;
  - fertiliser N.
- **Not monitored**: conversion factors, leakage, and the Baseline (beyond baseline-tree losses).
- **Documentation**:
  - **Design Certification**: the Consolidated A/R template, sections Applicability, Baseline, Leakage, Other Emissions, Carbon Performance and CO2 fixation.
  - **Performance Certification**: only CO2 fixation and Carbon Performance need updating.
  - **New Area Certification**: update the template, with new areas clearly distinguishable.
  - **PoA**: one template per real-case and regular VPA, or grouped per real case.
- **CO2-Fixation template** fields per growth model: MU list; option; time to equilibrium; long-term value in m³/ha or tdm/ha; source; BEF, WD and R:S values with source class (Project-specific, Regional, National, International, Gold Standard); long-term CO2-Fixation in tCO2/ha.
- **CO2-Fixation template** fields per inventory: MU; size; date; plot shape and size; number of plots; precision %; slopes >10 %; result in **m³ stem volume/ha**; confirmation or adaptation of the growth model; present CO2-fixation in tCO2/ha.

---

## 2. Equations

### 2.1 GS 403 v2.1 – all equations, verbatim

#### Eq. 1 – CO2 removal units per MU per year [GS p.7]
Verbatim:
`CO2 removal units MU,t = (CO2-removal MU,t − Baseline MU,t − Leakage MU,t − Other Emissions MU,t) × Eligible planting area MU`

$$\text{CO2RU}_{MU,t} = \left(\text{CR}_{MU,t} - \text{BSL}_{MU,t} - \text{LK}_{MU,t} - \text{OE}_{MU,t}\right)\times A_{MU}$$

| Symbol | Meaning | Unit (as implied) |
|---|---|---|
| CO2 removal units MU,t | CO2-removal units of MU in year t | tCO2 |
| CO2-removal MU,t | CO2 removal of MU in year t | tCO2/ha (Eq. 4 gives "[tCO2/ha]"; §3.3.2 says tCO2 – see Ambiguity A3) |
| Baseline MU,t | from Eq. 3; non-zero only at t=1 | tCO2/ha |
| Leakage MU,t | from Eq. 5; non-zero only at t=1 | tCO2/ha |
| Other Emissions MU,t | 10 % of Baseline at t=1 if burning; fertiliser in year of use | tCO2/ha |
| Eligible planting area MU | eligible planting area of MU | ha |

#### Eq. 2 – Project total [GS p.7]
Verbatim, from the render:

$$\text{CO2}_{removal}\,\text{Project area},t = \sum_{MU=1}^{MUs}\ \sum_{t=1}^{CP}\ \text{CO2\_removal MU},t$$

| Symbol | Meaning | Unit |
|---|---|---|
| CO2removal Project area,t | CO2-removal units of a project area in year t | tCO2 |
| CO2 removal MU,t | CO2-removal of a MU in year t | tCO2 |
| MUs | MUs of a project area (1, 2, 3, …) | – |
| t | years of the crediting period (1, 2, 3, …) | – |
| CP | year the crediting period ends (1, 2, 3, …) | – |

The inner sum over t up to CP conflicts with the label "in year t" (Ambiguity A2). Implement the inner sum as a cumulative sum to the current year.

#### Eq. 3 – Baseline per MU [GS p.8]
Verbatim: `Baseline MU,t [tCO2/ha] = Baseline Eligible planting area [tCO2] ÷ Eligible planting area [ha]`

$$\text{BSL}_{MU,t} = \frac{\text{BSL}_{EPA}}{A_{EPA}}\quad(\text{applied at } t=1 \text{ only})$$

#### Eq. 4 – Long-term CO2 removal, rotation forestry [GS p.10]
Verbatim; the source prints "= =", a typo:

$$\text{CR}_{MU,long\_term} = \frac{\sum_{t=1}^{T}\text{CR}_{MU,t}}{T}$$

| Symbol | Meaning | Unit |
|---|---|---|
| CR MU,long_term | long-term CO2-removal of a MU | tCO2/ha |
| CR MU,t | CO2 removal of a MU in year t (the standing-stock trajectory from the growth model) | tCO2/ha |
| T | number of years between the planting start and the end of the crediting period | [ ] (years) |
| t | years [1, 2, 3, …] | – |

#### Eq. 5 – Leakage per MU [GS p.11]
Verbatim: `Leakage MU,t [tCO2/ha] = Leakage Project area [tCO2] ÷ Eligible planting area [ha]`. Leakage is deducted in the first year (t=1).

$$\text{LK}_{MU,t} = \frac{\text{LK}_{PA}}{A_{EPA}}\quad(t=1)$$

#### Eq. 6 – Leakage, categories a/b/c [GS p.11]
Verbatim: `Leakage Project area [tCO2] = Area [ha] × % of activity-shift [%] × CO2-stock [tCO2/ha]`

$$\text{LK}_{PA} = A_{act}\times f_{shift}\times \text{CS}_{dest}$$

| Symbol | Meaning | Unit |
|---|---|---|
| Area | land within the project area where the activity is taking place | ha |
| % of activity-shift | share of the activity that will be displaced during the crediting period AND will affect tree biomass outside the project area; from credible estimates or a representative survey | % |
| CO2-stock | average tree-biomass stock on the destination area; if unknown, the average tree-biomass stock of natural forest in the host country | tCO2/ha |

#### Eq. 7 – Leakage, category d (livestock) [GS p.11–12]
Verbatim: `Leakage Project area [tCO2] = Displaced heads [head] × Grazing capacity [ha/head] × CO2-stock [tCO2/ha]`

$$\text{LK}_{PA} = H_{disp}\times GC_{dest}\times \text{CS}_{dest}$$

| Symbol | Meaning | Unit |
|---|---|---|
| Displaced heads | heads displaced during the crediting period AND affecting tree biomass outside; from credible estimates or a survey | head |
| Grazing capacity | grazing capacity of the destination area | ha/head |
| CO2-stock | as Eq. 6 | tCO2/ha |

#### Other emissions [GS p.12] – rules stated as text, not numbered equations

$$\text{OE}^{burn}_{MU,1} = 0.10\times \text{BSL}_{MU,1}\ \ (\text{only if baseline biomass is burned; lower value if justified})$$

$$\text{OE}^{fert}_{MU,t} = 0.005\ [\text{tCO}_2/\text{kg N}]\times N_{MU,t}\,[\text{kg N}] / A_{MU}\ \ (\text{deducted over time})$$

Normalising fertiliser emissions to per hectare (÷ A_MU) is needed for consistency with Eq. 1. That is an implementation inference.

#### Mangrove SOC add-on [GS p.5]

$$\Delta\text{SOC}_{MU,t} = 1.8\ \text{tCO}_2\,\text{ha}^{-1}\text{yr}^{-1}\ \text{for } 1\le (t - t_{plant,MU}) \le 20$$

This is 0.5 tC/ha/yr × 44/12 = 1.833, which GS rounds to 1.8. The add-on is excluded from PERs.

#### Conversion procedure – the core biomass chain [GS p.12–14, §3.9]
From the diagram on p.13 (text verbatim):
- "Aboveground tree biomass = Stem volume * Biomass Expansion Factor * Wood density * Carbon fraction * C to CO2 factor"
- "Belowground tree biomass = Aboveground tree biomass * Root-to-Shoot ratio"
- Diagram flow: BEF [ ] + Stem volume [m³] → Tree volume [m³]; + Wood density [tdm/m³] → Tree biomass [tdm]; + Carbon fraction [tC/tdm] + C to CO2 [tCO2/tC] → Aboveground tree biomass [tCO2]; + R:S [ ] → Belowground [tCO2]; AG + BG → Tree biomass.

$$\text{AGB}_{CO2} = V_{stem}\times BEF\times WD\times CF\times\tfrac{44}{12}$$

$$\text{BGB}_{CO2} = \text{AGB}_{CO2}\times R$$

$$\text{TB}_{CO2} = V_{stem}\times BEF\times WD\times(1+R)\times CF\times\tfrac{44}{12}$$

| Symbol | Meaning | Unit | Default for CO2 removal [GS p.14] | Default for Baseline/Leakage [GS p.14–15] |
|---|---|---|---|---|
| V_stem | stem volume (from inventory or growth model) | m³ (m³/ha) | – | – |
| BEF | biomass expansion factor = AG tree biomass / stem biomass (the example is in volumes: 1.3 m³/1 m³ = 1.3) | – | **1.1** | **3.5** |
| WD | wood density = dry mass / volume (example 0.6 t/m³) | tdm/m³ | **0.3** | **0.7** |
| R | root-to-shoot = BG tree biomass / AG tree biomass (example 0.3/1.3 = 0.23) | – | **0.2** (tree) | **0.8** (tree); **4.0** (non-tree) |
| CF (tree) | carbon fraction of tree biomass | tC/tdm | **0.47 [see Ambiguity A1: printed "0.47~~5~~"; v2.0 = 0.5]** | same |
| CF (non-tree) | carbon fraction of non-tree biomass | tC/tdm | 0.4 | 0.4 |
| 44/12 | C → CO2 | tCO2/tC | 44/12 | 44/12 |

Rules on the factors:
- **When the defaults apply**: the factors in §3.10.2 apply "when no rigorous scientific information is available". The CF and 44/12 values in §3.10.1 apply to all conversions.
- **IPCC alternatives**: IPCC 2019 Refinement Ch.4 (Forest Land) and Ch.6 (Grassland) defaults may replace the GS defaults without justification (§3.10.3–3.10.5).
- **Choosing factors** – attributes to consider (§3.9.8):
  - (a) some BEFs already include R:S;
  - (b) stem volume refers to a stump diameter, and the BEF should match it;
  - (c) most R:S ratios are based on tree volume, some on stem volume;
  - (d) a BCEF integrates BEF and WD;
  - (e) BEF can depend on age;
  - (f) dead wood has a different WD, BEF and R:S;
  - (g) sources may give a relative figure (0.4) or a "calculative" figure (1.4).

  Implementation consequence: support **BCEF mode** (TB = V × BCEF × (1+R) × CF × 44/12), an **age-dependent BEF**, an R:S that is either "relative" (0.4) or already "+1" (1.4), and separate dead-wood factors.

#### Inventory precision deduction [GS p.15, §3.11.5] – worked rule, verbatim example
"A forest inventory determined the mean 'Stem volume' of a MU at 100 m3/ha with an error of 23%. The error is 3% higher than required: 3% * 100 m3/ha = 3 m3/ha. The mean 'Stem volume' which can be accounted for is: 100 - 3 = 97 m3/ha"

$$\bar V_{adj} = \bar V\times\left(1-\max(0,\ E_{\%}-20\%)\right)$$

$$E_{\%} = \frac{t_{0.90}\cdot SE(\bar V)}{\bar V}$$

The error formula is **not given in GS 403**. The form above follows the AR-TOOL14 definition [T14 p.4–5] and is an interpretation (Ambiguity A6).

### 2.2 GS Rotation Forestry Projects Tool (403 0.8 xlsx, sheet "Example 1") – cell logic
Inputs:
- E3 = gross CO2 reduction per year (tCO2/ha), example 5;
- E4 = applicable area (ha), example 400;
- E5 = crediting years = `COUNT(A10:A45)`, i.e. 36;
- E6 = rotation period (yr), example 12.

Per year row r (year t = A_r):

| Column | Formula | Meaning |
|---|---|---|
| B (linear ex-ante estimation, tCO2e/ha) | `=$E$3` | annual increment |
| C (cumulative ER, tCO2e/ha) | `=C(r-1)+B(r)` | standing stock |
| D (baseline emissions) | entered value, 7.48 in year 1 only | |
| E (net reduction, tCO2e/ha/yr) | `=B−D` | |
| F (cumulative net reduction) | `=F(r-1)+E(r)` | |
| L (long-term average) | `=$F$48` | |
| M (cumulative, tCO2e/ha) | `=M(r-1)+L(r)` | |
| N (cumulative tCO2e) | `=M*$E$4` | |

In harvest years (12 and 24), B, C and F are set to 0, i.e. the stock is reset.

Summary cells:
- F47 = `AVERAGE(F10:F45)`, the long-term average stock (Eq. 4 applied to the net cumulative curve);
- **F48 "CFMU, long-term" = F47 / E5**.

The creditable trajectory is therefore a **linear ramp reaching the long-term average stock at the end of the crediting period**. Note that the tool averages the *net* curve (after baseline), not the gross CR_MU,t that Eq. 4 refers to (Ambiguity A5).

### 2.3 CDM AR-TOOL14 v04.2 (EB 85, 24 July 2015) – all equations
Not mandatory under GS 403. Provided as the reference statistical and tree engine, and because it is mathematically identical to CCTS **BM-T-AR-0004 v1.0** (27 Mar 2025).

Conventions [T14 p.5]: lower-case = per-ha quantities, upper-case = totals; t d.m. = tonne dry matter. In a methodology, the scenario suffixes _BSL and _PROJ are added (e.g. C_TREE_BSL,t, C_TREE_PROJ,t) [T14 p.6].

**Definition of uncertainty** [T14 p.4–5]: the standard error of the mean, expanded at 90 % confidence, divided by the mean, in %. Worked example:
- mean 45.328 t d.m./ha, n = 34, s = 12.776;
- SEM = 12.776/√34 = 2.191;
- × t(0.1,33) = 1.692 → 3.707;
- U = 8.18 %.

Only sampling uncertainty is controlled. Measurement and allometric error are handled by QA/QC.

**Zero conditions** [T14 p.6–7]:
- **Baseline tree stock = 0** if pre-project trees are (a) not harvested, cleared or removed, (b) not killed by competition or damage, and (c) not inventoried with project trees but monitored for continued existence (para 11).
- **Baseline tree/shrub change = 0** if one or more degradation indicators apply (para 12 (a)–(g)).
- **Ex-ante shrub change in the project = 0** is allowed (para 13).

#### Section 6.1 – Difference of two independent stock estimates [T14 p.7–8]
Eq. (1):

$$\Delta C_{TREE} = C_{TREE,t_2} - C_{TREE,t_1}$$

Eq. (2):

$$u_{\Delta C} = \frac{\sqrt{(u_1\times C_{TREE,t_1})^2 + (u_2\times C_{TREE,t_2})^2}}{\left|\Delta C_{TREE}\right|}$$

| Symbol | Meaning | Unit |
|---|---|---|
| ΔC_TREE | change in carbon stock in trees between t1 and t2 | t CO2e |
| C_TREE,t1 | stock at t1. At the first verification it equals the pre-project stock (C_TREE,t1 = C_TREE_BSL), or 0 if the zero conditions hold. Use the **undiscounted** previous value | t CO2e |
| C_TREE,t2 | stock at t2 | t CO2e |
| u_ΔC | uncertainty in ΔC_TREE | fraction |
| u1, u2 | uncertainties in C_TREE,t1 and C_TREE,t2 | fraction |

If u_ΔC > 10 %, apply the Appendix 2 discount to ΔC_TREE (para 18).

#### Section 6.2 – Direct estimation of change by re-measuring the same plots (ex-post only) [T14 p.8–10]
Eq. (3):

$$\Delta C_{TREE} = \frac{44}{12}\times CF_{TREE}\times\Delta B_{TREE}$$

Eq. (4):

$$\Delta B_{TREE} = A\times\Delta b_{TREE}$$

Eq. (5):

$$\Delta b_{TREE} = \sum_{i=1}^{M} w_i\times\Delta b_{TREE,i}$$

Eq. (6):

$$u_{\Delta C} = \frac{t_{VAL}\times\sqrt{\sum_{i=1}^{M} w_i^2\times\frac{s_{\Delta,i}^2}{n_i}}}{\left|\Delta b_{TREE}\right|}$$

Eq. (7):

$$\Delta b_{TREE,i} = \frac{\sum_{p=1}^{n_i}\Delta b_{TREE,p,i}}{n_i}$$

Eq. (8):

$$s_{\Delta,i}^2 = \frac{n_i\times\sum_{p=1}^{n_i}\Delta b_{TREE,p,i}^2 - \left(\sum_{p=1}^{n_i}\Delta b_{TREE,p,i}\right)^2}{n_i\times(n_i-1)}$$

| Symbol | Meaning | Unit |
|---|---|---|
| CF_TREE | carbon fraction of tree biomass; **default 0.47** | t C (t d.m.)⁻¹ |
| ΔB_TREE | change in tree biomass within the estimation strata | t d.m. |
| A | sum of areas of the biomass estimation strata | ha |
| Δb_TREE | mean change in tree biomass per ha | t d.m. ha⁻¹ |
| w_i | A_i / A | – |
| Δb_TREE,i | mean change per ha in stratum i (the source mislabels it "carbon stock … t d.m. ha⁻¹") | t d.m. ha⁻¹ |
| Δb_TREE,p,i | change in tree biomass per ha in plot p of stratum i | t d.m. ha⁻¹ |
| t_VAL | two-sided Student's t at 90 % confidence, df = n − M (n = total plots, M = number of strata) | – |
| s²_Δ,i | labelled "variance of mean change…"; Eq. (8) is actually the **sample variance** (see A9) | (t d.m. ha⁻¹)² |
| n_i | number of plots re-measured in stratum i | – |

If u_ΔC > 10 %, apply Appendix 2 (para 22).

#### Section 6.3 – Proportionate crown cover, baseline change (ex-ante; pre-project crown cover < 20 % of the forest threshold) [T14 p.10–11]
Eq. (9):

$$\Delta C_{TREE\_BSL} = \sum_{i=1}^{M}\Delta C_{TREE\_BSL,i}$$

Eq. (10):

$$\Delta C_{TREE\_BSL,i} = \frac{44}{12}\times CF_{TREE}\times\Delta b_{FOREST}\times(1+R_{TREE})\times CC_{TREE\_BSL,i}\times A_i$$

| Symbol | Meaning | Unit / default |
|---|---|---|
| ΔC_TREE_BSL(,i) | mean annual change in baseline tree carbon (in stratum i) | t CO2e yr⁻¹ |
| Δb_FOREST | default mean annual increment of AGB in forest in the region; IPCC GPG-LULUCF 2003 Table 3A.1.5. **Set to 0 after the steady-state year**, by default the 20th year from project start | t d.m. ha⁻¹ yr⁻¹ |
| R_TREE | root-shoot ratio of baseline trees; **default 0.25** | – |
| CC_TREE_BSL,i | baseline tree crown cover at project start, as a fraction | – |
| A_i | area of baseline stratum i | ha |

#### Section 6.4 – "No-decrease" (ex-post) [T14 p.11–12]
ΔC = 0 for a stratum if all of the following hold:
- (a) no harvest;
- (b) no disturbance;
- (c) remote sensing or inventory shows crown cover has not decreased.

#### Section 7 – Annual change [T14 p.12]
Eq. (11):

$$\Delta C_{TREE,t} = \frac{C_{TREE,t_2} - C_{TREE,t_1}}{T}\times 1\ \text{year}$$

- T = t2 − t1 in years; it may be fractional (4 yr 5 mo → 4.417).
- Not used with section 6.3.

#### Section 8.1.1 – Stock by stratified random sampling [T14 p.13–15]
Eq. (12):

$$C_{TREE} = \frac{44}{12}\times CF_{TREE}\times B_{TREE}$$

Eq. (13):

$$B_{TREE} = A\times b_{TREE}$$

Eq. (14):

$$b_{TREE} = \sum_{i=1}^{M} w_i\times b_{TREE,i}$$

Eq. (15):

$$u_C = \frac{t_{VAL}\times\sqrt{\sum_{i=1}^{M} w_i^2\times\frac{s_i^2}{n_i}}}{b_{TREE}}$$

Eq. (16):

$$b_{TREE,i} = \frac{\sum_{p=1}^{n_i} b_{TREE,p,i}}{n_i}$$

Eq. (17):

$$s_i^2 = \frac{n_i\times\sum_{p=1}^{n_i} b_{TREE,p,i}^2 - \left(\sum_{p=1}^{n_i} b_{TREE,p,i}\right)^2}{n_i\times(n_i-1)}$$

| Symbol | Meaning | Unit |
|---|---|---|
| C_TREE | carbon stock in trees in the estimation strata | t CO2e |
| CF_TREE | default 0.47 | t C (t d.m.)⁻¹ |
| B_TREE | tree biomass in the strata | t d.m. |
| A | sum of stratum areas | ha |
| b_TREE | mean tree biomass per ha | t d.m. ha⁻¹ |
| w_i | A_i/A | – |
| b_TREE,i | mean tree biomass per ha in stratum i | t d.m. ha⁻¹ |
| b_TREE,p,i | tree biomass per ha in plot p of stratum i (from Appendix 1) | t d.m. ha⁻¹ |
| u_C | uncertainty in C_TREE | fraction |
| t_VAL | two-sided t at 90 %, df = n − M | – |
| s_i² | variance of tree biomass per ha across plots in stratum i (Eq. 17 = sample variance) | (t d.m. ha⁻¹)² |
| n_i | number of plots in stratum i | – |

If u_C > 10 %, apply Appendix 2 (para 37).

#### Section 8.1.2 – Double sampling (linear relation with a secondary variable) [T14 p.15–17]
Eqs. (12)–(15) still apply. For a double-sampled stratum, these replace Eqs. (16) and (17):

Eq. (18):

$$b_{TREE,i} = \frac{\sum_{p=1}^{n_i} b_{TREE,p,i}}{n_i} + \beta\times(\bar{x}' - \bar{x})$$

Eq. (19):

$$s_i^2 = \frac{n_i\times\sum_{p=1}^{n_i} b_{TREE,p,i}^2 - \left(\sum_{p=1}^{n_i} b_{TREE,p,i}\right)^2}{n_i\times(n_i-1)}\times\left(1-(1-\alpha)\times\rho^2\right)$$

| Symbol | Meaning |
|---|---|
| n_i | number of plots in the **sub-sample** (those with biomass measured) |
| β | slope of the regression of plot biomass per ha on the secondary variable (Appendix 3) |
| x̄′ | mean of the secondary variable over **all** sample plots |
| x̄ | mean of the secondary variable over the sub-sample |
| α | (plots in sub-sample)/(plots in sample), α < 1 |
| ρ | correlation coefficient between the secondary variable and plot biomass, over the sub-sample (Appendix 3) |

If u_C > 10 %, apply Appendix 2 (para 44).

#### Section 8.2 – Growth modelling (ex-ante) [T14 p.17]
- No equation.
- Stand parameters (stocking, age classes, species, planting density, survival, thinning, pruning) are simulated from the planting/management plan, with local growth data and site factors.
- **Ex-ante projections are not subject to uncertainty control.**

#### Section 8.3 – Proportionate crown cover, pre-project baseline stock [T14 p.17–18]
Eq. (20):

$$C_{TREE\_BSL} = \sum_{i=1}^{M} C_{TREE\_BSL,i}$$

Eq. (21):

$$C_{TREE\_BSL,i} = \frac{44}{12}\times CF_{TREE}\times b_{FOREST}\times(1+R_{TREE})\times CC_{TREE\_BSL,i}\times A_i$$

| Symbol | Meaning / default |
|---|---|
| CF_TREE | 0.47 t C (t d.m.)⁻¹ |
| b_FOREST | mean AGB in forest in the region or country, IPCC GPG-LULUCF 2003 Table 3A.1.4 (t d.m. ha⁻¹) |
| R_TREE | 0.25 |
| CC_TREE_BSL,i | crown cover at start (fraction) |
| A_i | stratum area (ha) |

#### Section 8.4 – Update the previous stock with directly estimated change [T14 p.18–19]
Eq. (22):

$$C_{TREE,t_2} = C_{TREE,t_1} + \Delta C_{TREE}$$

Eq. (23):

$$u_2 = \frac{\sqrt{(u_1\times C_{TREE,t_1})^2 + (u_{\Delta C}\times\Delta C_{TREE})^2}}{C_{TREE,t_2}}$$

- C_TREE,t1 is the **undiscounted** previous estimate.
- If u2 > 10 %, apply Appendix 2 to C_TREE,t2.

#### Sections 9–11 – Shrubs [T14 p.19–21]
Eq. (24):

$$\Delta C_{SHRUB} = C_{SHRUB,t_2} - C_{SHRUB,t_1}$$

Eq. (25):

$$\Delta C_{SHRUB,t} = \frac{C_{SHRUB,t_2} - C_{SHRUB,t_1}}{T}\times 1\ \text{year}$$

Eq. (26):

$$C_{SHRUB,t} = \frac{44}{12}\times CF_S\times(1+R_S)\times\sum_i A_{SHRUB,i}\times b_{SHRUB,i}$$

Eq. (27):

$$b_{SHRUB,i} = BDR_{SF}\times b_{FOREST}\times CC_{SHRUB,i}$$

| Symbol | Meaning / default |
|---|---|
| CF_S | 0.47 |
| R_S | 0.40 |
| A_SHRUB,i | stratum area (ha) |
| b_SHRUB,i | shrub biomass per ha (t d.m. ha⁻¹) |
| BDR_SF | ratio of shrub biomass per ha at 100 % shrub cover to the forest default AGB; **default 0.10** |
| b_FOREST | IPCC GPG-LULUCF Table 3A.1.4 |
| CC_SHRUB,i | shrub crown cover (fraction). Strata with < 5 % cover count as zero. Under periodic cycles use a default of 0.5 (Data table 2) |

"No decrease" may be applied to shrubs (para 57).

#### Appendix 1 – Plot biomass [T14 p.23–27]
**Fixed-area plots** (e.g. 1/10 or 1/20 ha; minimum dbh e.g. 2 cm or 10 cm):

Eq. (A1.1):

$$b_{TREE,p,i} = \frac{B_{TREE,p,i}}{A_{PLOT,i}}$$

Eq. (A1.2):

$$B_{TREE,p,i} = \sum_j B_{TREE,j,p,i}$$

Eq. (A1.3):

$$B_{TREE,j,p,i} = \sum_l B_{TREE,l,j,p,i}$$

Eq. (A1.4) – allometric route:

$$B_{TREE,l,j,p,i} = f_j(x_{1,l},x_{2,l},x_{3,l},\ldots)\times(1+R_j)$$

Eq. (A1.5) – volume/BEF route:

$$B_{TREE,l,j,p,i} = V_{TREE,j}(x_{1,l},x_{2,l},x_{3,l},\ldots)\times D_j\times BEF_{2,j}\times(1+R_j)$$

Default root-shoot function (p.25):

$$R_j = \frac{e^{(-1.085+0.9256\times\ln b)}}{b}$$

Here b = above-ground tree biomass **per hectare** (t d.m. ha⁻¹), "unless transparent and verifiable information can be provided to justify a different value".

Coppice note: multiply R_j by max(v_HARVEST / v_TREE, 1), where v_HARVEST = volume per ha harvested and v_TREE = volume per ha standing.

| Symbol | Meaning | Unit / default |
|---|---|---|
| b_TREE,p,i | tree biomass per ha in plot p of stratum i | t d.m. ha⁻¹ |
| B_TREE,p,i | tree biomass in the plot | t d.m. |
| A_PLOT,i | plot size in stratum i | ha |
| B_TREE,j,p,i | biomass of species j in the plot | t d.m. |
| B_TREE,l,j,p,i | biomass of tree l of species j | t d.m. |
| f_j(·) | AGB from the species-j allometric equation (apply units consistently, e.g. in→cm, lb→t) | t d.m. |
| V_TREE,j(·) | stem volume from a volume table or equation. **Over-bark**: correct if the equation gives under-bark volume | m³ |
| D_j | over-bark basic density; IPCC GPG-LULUCF 2003 Table 3A.1.9; bark correction if needed | t d.m. m⁻³ |
| BEF_2,j | stem-biomass → AGB expansion factor. **Ex-post default 1.15**; ex-ante chosen by the source hierarchy | – |
| R_j | root-shoot ratio of species j | – |

Further rules:
- **Saplings below the allometric range** (p.23):
  1. take the diameter midway between the smallest sapling and the minimum diameter of the equation;
  2. harvest a few saplings outside the plot near that diameter to get the mean biomass per sapling;
  3. multiply the sapling count in the plot by that mean.
- **Model source hierarchy, ex-ante** (para 6): (a) local data, then (b) national, then (c) neighbouring countries, then (d) global.
- **Ex-post** (para 7): the allometric equation must pass the CDM tool "Demonstrating appropriateness of allometric equations…" (AR-TOOL17), and the volume equation must pass the corresponding tool for volume equations (AR-TOOL18).

**Variable-area (angle-count) plots** [T14 p.26–27]:

Eq. (A1.6):

$$b_{TREE,p,i} = \sum_j b_{TREE,j,p,i}$$

Eq. (A1.7):

$$b_{TREE,j,p,i} = f_j(BA_{p,i})\times(1+R_j)$$

Eq. (A1.8):

$$b_{TREE,j,p,i} = v_{TREE,j}(BA_{p,i})\times D_j\times BEF_{2,j}\times(1+R_j)$$

- f_j(BA) = AGB per ha from a basal-area allometry (t d.m. ha⁻¹).
- v_TREE,j(BA) = stem volume per ha (m³ ha⁻¹).
- Other symbols as in Eqs. (A1.4) and (A1.5).

#### Appendix 2 – Uncertainty discount [T14 p.28] (Table 1, exact)

| Uncertainty U | Discount (% of U) |
|---|---|
| U ≤ 10 % | 0 % |
| 10 < U ≤ 15 | 25 % |
| 15 < U ≤ 20 | 50 % |
| 20 < U ≤ 30 | 75 % |
| U > 30 | 100 % |

Worked example (verbatim): "Estimated mean = 60±9 t d.m ha⁻¹; i.e. U=9/60x100 = 15%; Discount = 25% x 9 = 2.25 t d.m ha⁻¹; Discounted conservative mean: In baseline = 60+2.25 = 62.25; In project = 60−2.25 = 57.75 t d.m ha⁻¹".

The discount is a percentage of the **absolute 90 % CI half-width**, not of the mean:

$$\hat X_{cons} = \hat X \mp d(U)\times U\times\hat X$$

Use − for project removals and + for baseline.

#### Appendix 3 – Regression slope and correlation [T14 p.29]
Eq. (A3.1):

$$\beta = \rho\times\frac{s_y}{s_x}$$

Eq. (A3.2):

$$\rho = \frac{\sum_{i=1}^{n}(x_i-\bar x)(y_i-\bar y)}{\sqrt{\sum_{i=1}^{n}(x_i-\bar x)^2\times\sum_{i=1}^{n}(y_i-\bar y)^2}}$$

- s_y, s_x are sample standard deviations.
- y = plot biomass per ha; x = the secondary variable.

#### Monitored parameters [T14 p.21–22]
- **Areas** (plot and stratum): field measurement under national forest inventory SOPs, otherwise IPCC GPG-LULUCF 2003 SOPs; at every verification.
- **Shrub crown cover**: at every verification; ocular estimate, line transect or relascope allowed; 0.5 under periodic cycles.
- **Baseline tree crown cover**: measured once at project start; under periodic cycles use half the maximum cover.

### 2.4 BioCarbon Fund Sourcebook (mandated by GS 403 §3.11.2 for inventories) – quantitative content
Source: Pearson, Walker & Brown, *Sourcebook for LULUCF Projects*, Winrock/BioCarbon Fund (64 pp).

**Plot sizes** for nested or single plots [SB p.14]:

| Stem diameter | Circular plot radius | Square plot |
|---|---|---|
| < 5 cm dbh | 1 m | 2 × 2 m |
| 5–20 cm | 4 m | 7 × 7 m |
| 20–50 cm | 14 m | 25 × 25 m |
| > 50 cm | 20 m | 35 × 35 m |

- **Single plot**: it must hold at least 8–10 trees at the end of the project.
- **Nested-circle expansion factors**: for 4/14/20 m radii, 198.9, 16.2 and 8.0.
- **Rectangular nests**: 5×10, 17×35 and 20×50 m.

**Number of plots** [SB p.15–16]. GS overrides the confidence level with 90 % (see A8). The Sourcebook's own settings:
- t for 95 % confidence, usually set to 2;
- E = mean × precision (0.1 or 0.2).

$$n = \frac{\left(\sum_{h=1}^{L} N_h\, s_h\right)^2}{\dfrac{N^2 E^2}{t^2} + \sum_{h=1}^{L} N_h\, s_h^2}$$

- Single stratum: n = (N·s)² / (N²E²/t² + N·s²).
- N_h = number of sampling units in stratum h (stratum area ÷ plot area). The source garbles this as "= area of stratum in hectares or area of the plot in hectares".
- N = Σ N_h. The source prints "n = … (n = Σ N_h)".
- s_h = SD of stratum h.

**Slope correction** [SB p.24]:

$$L = L_s\cos S$$

- Circular plot area = π × L_s × L (example: 20 m on 25° → 3.142 × 20 × 18.1 = 0.11 ha).
- Rectangular plot area = width × L.
- Required where slope > 10 % [SB p.15].

**Expansion factor** [SB p.24]:

$$EF = \frac{10\,000\ \text{m}^2}{\text{slope-corrected plot area (m}^2)}$$

**Carbon**: the Sourcebook says Carbon = Biomass / 2 [SB p.24]. **GS 403 §3.10.1 overrides this** (CF 0.47 or 0.475).

**Belowground** [SB p.27] (Cairns et al. 1997 form), with BBD and ABD in t/ha:

$$\text{BBD} = \exp(-1.0587 + 0.8836\ln \text{ABD} + c)$$

with c = 0.1874 (boreal), 0.2840 (temperate), 0 (tropical). Under GS 403 the **R:S ratio of §3.10 is the default**; this regression is an alternative "scientific source".

---

## 3. Minimal implementable chain – typical GS A/R project with plot-based per-tree measurements

Scope: one or more MUs, ex-post inventory before each Performance Certification, conservation or selective-harvest forest (Option 1), no burning. Interpretive steps are marked **[interp]**.

**Static, at design certification**
1. **MU registry.** For each MU, record:
   - MU id, eligible planting area A_MU (ha), planting date, species group, option (1 or 2);
   - growth model: a per-ha stem-volume or biomass trajectory by age;
   - factor set WD, BEF (optionally by age), R (relative), CF_tree = 0.47 **[A1]**. Store each factor's source class (project, regional, national, international, GS default or IPCC 2019).
2. **Baseline** (stock at planting start), per baseline stratum s (vegetation type) with area a_s:
   - Tree part, if expressed as volume:

     $$\text{BSL}_{tree,s} = a_s\cdot V_s\cdot WD_{bsl}\cdot BEF_{bsl}\cdot(1+R_{bsl})\cdot CF_{tree}\cdot\tfrac{44}{12}$$

     with GS defaults WD = 0.7, BEF = 3.5, R = 0.8. If expressed as tdm: a_s · AGB_s · (1+R) · CF · 44/12.
   - Non-tree part:

     $$\text{BSL}_{nt,s} = a_s\cdot AGB_{nt,s}\cdot(1+4.0)\cdot 0.4\cdot\tfrac{44}{12}$$

     (R non-tree default 4.0; CF 0.4.)
   - Totals: BSL_EPA = Σ_s (tree + non-tree), then Eq. 3: BSL_MU = BSL_EPA / A_EPA, deducted at t=1. **[interp]** All MUs share the project-wide per-ha baseline, as Eq. 3 literally says. Allow an MU-specific override where baseline strata map to MUs.
3. **Leakage**:
   - categories a–c: LK = Σ (Area × %shift × CS_dest), Eq. 6;
   - livestock: LK += heads × ha/head × CS_dest, Eq. 7;
   - LK_MU = LK / A_EPA (Eq. 5), at t=1.
4. **Other emissions**: OE_MU,1 = 0.10 × BSL_MU if burning. Fertiliser in year t: 0.005 × kgN_MU,t / A_MU.
5. **Ex-ante trajectory**: CR_MU,t = growth-model volume_t × WD × BEF × (1+R) × CF × 44/12 (tCO2/ha, standing stock).
   - Include surviving baseline trees and survival rate.
   - Mangroves: add the 1.8 tCO2/ha/yr SOC term for 20 years.
6. **Long-term cap** **[interp]**:
   - Option 1: CR_LT = CR at equilibrium, or CR_MU,CP if the stock is still growing. The creditable stock is CR*_t = min(CR_MU,t, CR_LT).
   - Option 2: CR_LT = mean_t CR_MU,t (Eq. 4) over T years. The creditable stock ramps linearly, CR*_t = CR_LT × t / T, as in GS tool 0.8.
7. **PERs** (optional): forward issuance for ≤ 5 years from the ex-ante net trajectory, never more than the ex-ante stock. Excluded components: SOC, and smallholder projects on default values. 80 % to the project account, 20 % to the buffer.

**Per inventory (before each Performance Certification), per MU**

8. **Tree level** for each measured tree l (species j) in plot p:
   - volume route: V_l = V_j(dbh, h) (over-bark m³);
   - allometric route: AGB_l from f_j(dbh, h, …) in tdm, which may be expressed as volume-equivalent ÷ (WD·BEF) for GS reporting **[interp – A4]**.
   - Saplings below the model range: use the Sourcebook or AR-TOOL14 sapling method.
9. **Plot level**: v_p = Σ_l V_l / A_plot,p (m³/ha). A_plot is slope-corrected when slope > 10 % (L = L_s cos S). For nested plots, apply a per-nest expansion factor.
10. **MU statistics** (one stratum = one MU):
    - mean V̄ and sample variance s² = [n Σ v² − (Σ v)²] / [n(n−1)];
    - SE = s/√n;
    - E% = t(0.90, n−1) × SE / V̄ **[interp – A6]**. If the MU is post-stratified, use the AR-TOOL14 Eqs. (14)–(15) with df = n − M.
11. **Precision deduction** (GS §3.11.5): V̄_adj = V̄ × (1 − max(0, E% − 20 %)).
12. **Convert**: CR_inv,MU = V̄_adj × WD × BEF × (1+R) × CF × 44/12 (tCO2/ha).
13. **Growth-model check**: confirm or adjust the model with CR_inv. Re-derive CR_MU,t for the remaining years, and CR_LT if needed.
    - **[interp]** Credit at the monitoring date the lower of CR_inv (adjusted) and the modelled CR_MU,t, then apply the long-term cap from step 6.
    - Rotation forestry: performance is checked against the original growth model (RC 2020).
14. **Net per MU, cumulative to year t**:

    $$\text{NET}_{MU}(t) = \left[\text{CR}^{*}_{MU,t} - \text{BSL}_{MU} - \text{LK}_{MU} - \text{OE}_{MU,1} - \textstyle\sum_{\tau\le t}\text{OE}^{fert}_{MU,\tau} (+\ \Delta\text{SOC})\right]\times A_{MU}$$

    This is Eq. 1 with the t=1 deductions carried cumulatively.
15. **Project**: NET(t) = Σ_MU NET_MU(t) (Eq. 2).
    - Issuable for the monitoring period (t1, t2] = max(0, NET(t2)) − (units already issued as GSVERs).
    - Convert outstanding PERs first.
    - If NET ≤ 0, issue nothing (§3.3.3).
16. **Buffer**: 20 % of issued GSVERs and PERs go to the GS buffer, pro rata by vintage. Check Carbon Performance: issued ≤ verified stock, otherwise the shortfall procedure applies.
17. **Vintage gate (PAA)**: block 2026+ vintages unless the project has PAA status (GS 119 v1.2).

---

## 4. Can GS 403 and CCTS BM FR05.002 share one biomass engine?

**Yes, at the "biomass engine" layer. No, at the accounting layer.**

CCTS FR05.002 v1.0 (8 Sep 2025) adopts CDM AR-ACM0003 and delegates tree and shrub biomass to **BM-T-AR-0004 v1.0**. That tool is a transposition of AR-TOOL14 v04.2: the same equations (1)–(27), Appendices 1–3, defaults CF 0.47, R_TREE 0.25, R_S 0.40, BEF₂ 1.15, the Rj function, the 10 % threshold and the identical discount table. The only change is that "IPCC GPG-LULUCF 2003 Table 3A.x" becomes "latest version of IPCC GPG-LULUCF". GS 403's conversion chain is a special case of AR-TOOL14 Appendix 1, Eq. (A1.5), aggregated per ha.

### 4.1 Shareable core (same math, parameterised)

| Engine component | GS 403 use | CCTS FR05.002 / BM-T-AR-0004 use |
|---|---|---|
| Tree-level AGB: allometry f_j(·) **or** V_j(·)·D_j·BEF_j (or BCEF) | volume route is primary; tdm allowed (§3.9.1) | both routes (A1.4/A1.5) |
| Belowground: AGB·R | R = fixed ratio (default 0.2 project, 0.8 baseline) | R_j = e^(−1.085+0.9256 ln b)/b per ha by default, or a justified value |
| Plot aggregation Σ trees / A_plot (slope-corrected), nested EFs, sapling rule | yes (Sourcebook) | yes (A1.1–A1.3) |
| Stratum mean, sample variance (Eq. 16–17), weighted mean (Eq. 14), t-based relative half-width (Eq. 15) | needed for the ±20 % test | needed for the 10 % test |
| Double sampling, regression (Eq. 18–19, App. 3) | allowed under the Sourcebook in principle | yes |
| Stock → CO2: × CF × 44/12 | CF 0.47 (or 0.475) tree; 0.4 non-tree | CF 0.47 |
| Change between occasions (Eq. 1–8, 22–23) and annualisation (Eq. 11) | not used by GS (GS works with stock vs growth model) | core of ex-post ΔC |

### 4.2 What must be parameterised or kept methodology-specific

| Aspect | GS 403 v2.1 | CCTS FR05.002 (AR-ACM0003 + BM-T-AR-0004) |
|---|---|---|
| Accounting unit | MU (growth-model unit), tCO2/ha × area | stratum totals, t CO2e |
| Primary quantity | **standing stock per year from the growth model**, confirmed or adjusted by inventory | **ΔC between verifications** from measurement; growth models only ex-ante |
| Long-term cap | Option 1 equilibrium or CP-end stock; Option 2 average (Eq. 4) with linear ramp | none; temporary or long-term CCCs (tCCC = Σ₁^t2 ΔC_AR; lCCC = Σ_{t1+1}^{t2}), negative lCCC → replacement |
| Precision rule | ±20 % @90 %, **deduct the excess percentage points × mean** (on stem volume) | if U > 10 % @90 %, **stepped discount** 25/50/75/100 % of the CI half-width; baseline +, project − |
| t-value df | not specified | n − M |
| CF tree | 0.47 (printed 0.47~~5~~; v2.0 = 0.5) | 0.47 |
| Defaults WD / BEF / R | project 0.3 / 1.1 / 0.2; baseline and leakage 0.7 / 3.5 / 0.8 (non-tree R 4.0); IPCC 2019 alternatives without justification | D from IPCC table; BEF₂ 1.15 ex-post; R by Mokany/Cairns-type function; baseline R 0.25 |
| Pools | trees (AG+BG, standing dead wood included); non-tree in baseline only; SOC optional (GS soil tool; mangrove 1.8 tCO2/ha/yr) | trees, shrubs; dead wood and litter optional (BM-T-AR-003); SOC optional (BM-T-AR-006) |
| Baseline | stock just before planting, tree + non-tree, deducted once at t=1 | ΔC_BSL,t trees, shrubs, DW, LI per year (crown-cover methods, or 0 under the conditions) |
| Leakage | activity shift × destination tree stock (4 categories), all at t=1, not monitored | BM-T-AR-005 (agricultural displacement), per year |
| Non-CO2 / other | +10 % of baseline if burnt; fertiliser 0.005 tCO2/kg N; fossil fuel and N-fixers zero | BM-T-AR-002 biomass burning CH4/N2O; fertiliser, fossil fuel etc. insignificant |
| Permanence | 20 % buffer; PER → GSVER conversion; Carbon Performance shortfall | temporary/long-term CCCs; no buffer in FR05.002 |
| Crediting | 30–50 yr; verification ≤ 5 yr; renewal every 5 yr; PAA gate for 2026+ | per CCTS detailed procedure (not in FR05.002) |

### 4.3 Recommended design
- **Shared engine `tree_biomass`.**
  - Tree → plot → stratum statistics → stock (t d.m. and tCO2), with pluggable `AGBModel` (allometric | volume×D×BEF | BCEF) and `RootModel` (fixed ratio | AR-TOOL14 function | Cairns-by-zone).
  - Plot geometry: fixed, nested or variable-area; slope correction.
  - Statistics: SRS, stratified, double-sampling; configurable confidence level (default 90 %) and df rule.
- **Methodology adapters** (`gs403`, `ccts_fr05_002`):
  - choose the factor defaults;
  - choose the precision policy: `excess_deduction(20 %)` vs `stepped_discount(10 %)`;
  - turn engine outputs into credits: GS = MU stock vs growth model + long-term cap + t=1 deductions + buffer/PER; CCTS = ΔC_ACTUAL − ΔC_BSL − LK → tCCC/lCCC.
- **Units**: keep **undiscounted** estimates in storage. Both AR-TOOL14 (Notes to Eq. 1 and 23) and GS's cumulative logic need undiscounted previous stocks. Apply conservativeness only at the reporting and adapter layer.

---

## 5. Ambiguities and issues (with page refs)

| # | Where | Issue | Suggested handling |
|---|---|---|---|
| A1 | GS p.14 §3.10.1a | CF for tree biomass is printed "0.47" with a **struck-through "5"**; the text layer reads 0.475. v2.0 (p.14 equivalent) = **0.5**. | Use **0.47** (IPCC/AR-TOOL14) as default; make it configurable; ask GS to confirm. |
| A2 | GS p.7 Eq. 2 | Labelled "in year t" but sums t=1…CP; the sum over CP double-counts if CR_MU,t is a stock. | Interpret as a cumulative sum to the current year, applied to Eq. 1 results; CR_MU,t is a stock and the deductions are one-off. |
| A3 | GS p.7 §3.3.2 vs Eq. 1 / p.10 | CO2 removal MU,t is "tCO2" in §3.3.2 but must be tCO2/ha for Eq. 1 (× area) and per Eq. 4's legend "[tCO2/ha]". | Treat as tCO2/ha. |
| A4 | GS p.9 §3.6.3, p.12 §3.9.1, p.15 template | The chain assumes **stem volume**; allometric biomass (tdm) is mentioned only in §3.9.1, and the inventory template reports "m³ stem volume per ha". No rule for allometry-based inventories or for applying the 20 % rule to biomass instead of volume. | Allow the tdm route (skip WD·BEF) and apply the 20 % rule to whichever per-ha quantity was inventoried; document it in the PDD. |
| A5 | GS p.9–10 §3.6.6–3.6.12; tool 0.8 | The long-term CO2 removal is defined, but **Eq. 1 never references it**. How it caps or spreads issuance is unspecified in the methodology. The tool spreads it linearly (F48 = average/years) and averages the **net** (post-baseline) curve, whereas Eq. 4 averages gross CR_MU,t. | Option 1: cap at CR_LT. Option 2: linear ramp to CR_LT per the GS tool. Flag the net/gross choice. |
| A6 | GS p.15 §3.11.5 | "Error" is not defined: relative half-width or SE, which t/df, per MU or pooled? Also "the additional difference" applies to the % points of the mean. | Use AR-TOOL14's definition: t₀.₉₀,df × SE / mean, df = n − 1 per MU (or n − M if post-stratified). |
| A7 | GS p.8 Eq. 3 vs p.9 §3.5.4 | Eq. 3 spreads one project-wide baseline per ha equally over MUs; §3.5.4 introduces a "baseline modelling unit" with baseline trees tracked by census. The two are not reconciled. | Support both: a project-wide per-ha baseline, plus a separate baseline-tree MU whose losses are deducted when they occur. |
| A8 | GS p.15 §3.11.2 vs SB p.15–16 | The Sourcebook uses **95 %** confidence and ±10 % (or 20 %) precision; GS requires **90 %** confidence and ±20 %. The Sourcebook plot-count formula has typos: N_h definition, "n = Σ N_h" should be N, and the two-strata denominator is missing a square on s₁. | Use the GS thresholds; implement the corrected Neyman-type formula. |
| A9 | T14 p.9–10 Eq. (8), p.15 Eq. (17), p.16 Eq. (19) | s² is labelled "variance of **mean**…", but the formula is the sample variance (÷ n(n−1) of the raw sums). Eq. (6) and (15) then divide by n_i again. | Implement exactly as written; it is consistent if read as sample variance. Do not divide twice. |
| A10 | T14 p.8 Note 1 | Refers to the zero conditions under "paragraph 10"; they are in **paragraph 11**. | Editorial. |
| A11 | T14 p.9 | Δb_TREE,i is defined as "mean change in carbon stock per hectare … t d.m. ha⁻¹" – it is biomass, not carbon. | Treat as biomass. |
| A12 | T14 p.25 vs SB p.27 | Two different root regressions: AR-TOOL14 R_j = e^(−1.085+0.9256 ln b)/b vs the Sourcebook BBD = exp(−1.0587 + 0.8836 ln ABD [+0.1874/+0.2840]). GS 403 uses neither by default (it uses fixed R:S). | Offer both as alternative "scientific sources" for GS; AR-TOOL14 is the default for CCTS. |
| A13 | GS p.9 §3.5.7 vs LUF p.16 §3.1.12(c) | GS 403: the baseline is not reassessed at renewal. LUF v1.2.1: A/R projects shall update the baseline at renewal "following the applied … Methodology". | The methodology governs: the baseline is fixed. Note the conflict. |
| A14 | PR §11.4.1a | "the quantity of GSVERs is equal or higher (not less) to the project's expected carbon stocks" looks inverted. | Implement as issued GSVERs ≤ verified stock (shortfall check). |
| A15 | GS p.12 §3.8.3 | Fertiliser deduction is per kg N with no per-ha normalisation for Eq. 1 or rule for MU allocation. | Allocate to the MU where it is applied; divide by A_MU. |
| A16 | GS p.5 §2.1.3b | 0.5 tC/ha/yr × 44/12 = 1.833, and GS states 1.8. | Use 1.8 as printed. |
| A17 | GS p.10 Eq. 4 | Printed "= =" (typo). The definition of T (planting start to CP end) differs from the crediting period when planting precedes the CP start. | Use T as defined. |
| A18 | GS 119 PAA v1.2 §1.4, §4.1.3 | LUF vintage-allocation and buffer guidance is "to be published separately"; no PA-aligned A/R methodology is listed yet. | Gate 2026+ vintages; revisit when GS publishes. |
| A19 | Brief | It assumed GS 403 is 8 pages and references AR-TOOL14/12/15 and "403.01–403.06". `file` reports 8 pages, but the PDF has 17 pages (an incremental-update artefact), and it references none of those CDM A/R tools. | Noted in §0. |

**[UNREADABLE]** items: none. Every equation was legible in the renders. The PDF text layer garbles operators (`÷`, `×` → `�`) and the struck digit (A1); this was resolved visually.

---

## 6. Files downloaded to `D:\Desktop\CC\methodology-docs\GS-AR\`

**Gold Standard** (base URL `https://globalgoals.goldstandard.org/standards/`)

| File | URL suffix | Notes |
|---|---|---|
| 403.01_V1.0_LUF_AR-Methodology_Integrated-TEMPLATE.docx | same as file name | Consolidated A/R template ("403.01") |
| 403_V1.0_0.1_LUF_AR-Methodology_Applicability-TEMPLATE.docx | same | |
| 403_V1.0_0.2_LUF_AR-Methodology_Baseline-TEMPLATE.docx | same | |
| 403_V1.0_0.3_LUF_AR-Methodology_Leakage-TEMPLATE.docx | same | |
| 403_V1.0_0.4_LUF_AR-Methodology_Other-emissions-TEMPLATE.docx | same | |
| 403_V1.0_0.5_LUF_AR-Methodology_Carbon-Performance-TEMPLATE.docx | same | |
| 403_V1.0_0.6_LUF_AR-Methodology_CO2-Fixation-TEMPLATE.docx | same | |
| 403_V1.0_0.7_LUF_AR-Methodology_Soil-Carbon-Tool.xlsm.zip | same | A/R Soil Carbon Tool (zip of an xlsm; not unpacked) |
| 403_V1.0_0.8_LUF_AR-Methodology_Rotation-Forestry-Projects-Tool.xlsx | same | transcribed in §2.2 |
| 403_V2.0_LUF_AR-Methodology-GHGs-emission-reduction-and-Sequestration-Methodology.pdf | same | previous version (CF 0.5) |
| RC_2020-Clarification-on-the-rules-for-Rotation-Forestry-Projects-under-the-AfforestationReforestation-methodology.pdf | same | |
| 203_V1.2.1_AR_LUF-Activity-Requirements.pdf | same | LUF Activity Requirements (crediting period 30–50 yr, Annex B/C) |
| 203_V1.0_AR_LUF_Activity-requirements_AR_Additionality-Template.docx | same | |
| RC_2025_LUFAR_Positive-List.pdf | same | |
| RC_2020-Applicability-of-Land-Use-and-Forests-Activity-Requirements-Annex-B-Requirements-for-AR-Smallholder-and-Microscale-Projects.pdf | same | |
| 119_V1.2_PAA-PR100-01_Requirements-for-Paris-Agreement-Alignment.pdf | same | PAA rules (published 02/10/2026) |

(The existing `GS_403_AR_Methodology_v2.1.pdf` is byte-identical to `…/standards/403_V2.1_LUF_AR-Methodology-GHGs-emission-reduction-and-Sequestration-Methodology.pdf`. The Product Requirements v3.2 used here was already in `..\GS-SOC\501_V3.2_PR_GHG-ERS.pdf`.)

**CDM.** cdm.unfccc.int blocks curl with an Incapsula JS challenge, so these files were fetched as raw originals from the Internet Archive: `http://web.archive.org/web/<timestamp>id_/http://cdm.unfccc.int/<path>`. The canonical URL is `https://cdm.unfccc.int/<path>`.

| File | Canonical path | Wayback timestamp | Status |
|---|---|---|---|
| ar-am-tool-14-v4.2.pdf | methodologies/ARmethodologies/tools/ar-am-tool-14-v4.2.pdf | 20151112065804 | AR-TOOL14 v04.2 (current; EB 85) – transcribed |
| ar-am-tool-12-v3.1.pdf | …/ar-am-tool-12-v3.1.pdf | 20151022024235 | dead wood & litter (not referenced by GS 403) |
| ar-am-tool-15-v2.0.pdf | …/ar-am-tool-15-v2.0.pdf | 20151022025909 | displacement of agricultural activities (not referenced by GS 403) |
| ar-am-tool-16-v1.1.0.pdf | …/ar-am-tool-16-v1.1.0.pdf | 20110928112817 | SOC (not referenced by GS 403) |
| ar-am-tool-03-v2.1.0.pdf | …/ar-am-tool-03-v2.1.0.pdf | 20110928134920 | number of sample plots (referenced by AR-TOOL14 para 34) |
| ar-am-tool-17-v1.pdf | …/ar-am-tool-17-v1.pdf | 20120609233349 | appropriateness of allometric equations (AR-TOOL14 App.1 para 7) |
| ar-am-tool-18-v1.0.1.pdf | …/ar-am-tool-18-v1.0.1.pdf | 20130421013956 | appropriateness of volume equations (AR-TOOL14 App.1 para 7) |
| am-tool-01-v7.0.0.pdf | methodologies/PAmethodologies/tools/am-tool-01-v7.0.0.pdf | 20140123203802 | CDM Tool 01 additionality (GS 403 §3.2.3b) |
| am-tool-19-v10.0.pdf | methodologies/PAmethodologies/tools/am-tool-19-v10.0.pdf | 20221007092959 | CDM Tool 19 microscale additionality (latest found in archive) |
| am-tool-21-v13.1.pdf | methodologies/PAmethodologies/tools/am-tool-21-v13.1.pdf | 20210607225628 | CDM Tool 21 small-scale additionality (latest found in archive) |

Version caveat: the Tool 19 and Tool 21 versions are the newest found in the archive index. Newer versions may exist on the live CDM site, which could not be reached.

**Other**

| File | URL |
|---|---|
| Winrock-BioCarbon_Fund_Sourcebook-compressed.pdf | https://winrock.org/wp-content/uploads/2016/03/Winrock-BioCarbon_Fund_Sourcebook-compressed.pdf (the URL in GS 403 footnote 7) |

**Not downloaded**:
- AR-AM0014 v3.0. It is cited only for the 1.8 tCO2/ha/yr mangrove default, and no stable URL was found because the CDM DB is behind Incapsula.
- IPCC 2019 Refinement Vol.4 Ch.4 and Ch.6 (linked from GS 403). These were not re-downloaded; see `..\IPCC\`.

Text copies created in `..\_text\`: `ar-am-tool-14-v4.2.txt`, `203_V1.2.1_AR_LUF-Activity-Requirements.txt`, `403_V2.0_…txt`, `RC_2020-Clarification-…Rotation…txt`, `119_V1.2_PAA.txt`, `Winrock_BioCarbon_Sourcebook.txt`.
