# VM0047 v1.1 Census-Based Approach and Leakage (VMD0054 v1.1): Extraction for Implementation

**Sources**

- Verra **VM0047 Afforestation, Reforestation, and Revegetation v1.1 (14 May 2025)**. Text: `methodology-docs/_text/VM0047_ARR_v1.1.md`, converted from PDF. "p. N" means the document's printed page number.
- Verra **VM0047 v1.0 (28 Sep 2023)** PDF: `VM0047-ARR/VM0047_ARR_v1.0.pdf`. Pages 19 and 23–28 were rendered to images to check equations.
- Verra **VMD0054 Estimating Leakage from the Displacement of Agricultural Activities v1.1 (13 Jan 2026)**. Text: `_text/VMD0054_v1.1.md`.
- Verra **VMD0054 v1.0** PDF: `VM0042-IALM/VMD0054_v1.0_Leakage_Module.pdf`. Pages 6–11 were rendered to check equations.
- For buffer and VCU rules: VCS Standard v5.0 (`_text/VCS_Standard_v5.0.txt`) and AFOLU Non-Permanence Risk Tool v5.0 (`_text/AFOLU_Non-Permanence_Risk_Procedure_v5.0.txt`).

**Transcription conventions**

- The v1.1 text conversion scrambles the math font (Cambria Math glyphs appear as Syriac/Sinhala/Tamil code points). Each equation therefore has a status:
  - **[TEXT-CLEAN]**: the v1.1 text is legible.
  - **[RECONSTRUCTED]**: the equation was rebuilt token by token from the garbled v1.1 glyph stream.
  - **[V1.0-CONFIRMED]**: the same equation was read on a rendered v1.0 PDF page, and the v1.1 tokens agree with it.
  - **[CHANGED vs v1.0]**: v1.1 differs from v1.0. The difference is stated.
- **No v1.1 PDF is available locally.** An attempt to download it from verra.org was blocked by Cloudflare. Equations that exist only in v1.1 (Eqs. 22, 28, 29, 30, 32, 34 of VM0047; Eqs. 2, 6, 7, 8, 10, 13 of VMD0054) could **not** be checked against a page image. Their reconstructions should be checked against the official v1.1 PDF before production use.
- Nothing is paraphrased inside equations. Items that cannot be read are marked [UNREADABLE]. None were needed: every token could be placed.

---

## 1. Census-based approach: structure

### 1.1 What it is (VM0047 v1.1 §1.2, p. 6)

The census-based approach covers ARR projects that do not occur in forests and do not change land use. Its defining features:

1. Direct planting only.
2. At most **50 planting units per hectare**.
3. A **complete census of all planting units** at t = 0 establishes **N**.
4. Biomass is estimated by **sampling and measuring planting units**, then scaled to the project using N.
5. A **project method** is used for both additionality and the crediting baseline. The baseline is zero.
6. The approach is **exempt from a leakage deduction**, because pre-project land use continues.

A **planting unit** is a "clearly defined individual woody plant (e.g., tree, shrub, discrete bamboo clump) that is identifiable in the field and subject to a complete census" (§3, p. 7).

The **accounting boundary** for census-based projects is limited to the individual planting units. It excludes SOC, litter and non-woody biomass outside those units (§3, p. 6).

### 1.2 Eligibility

**General conditions for all projects (§4 and §4.1, pp. 8–9)**

- Area-based and census-based applicability conditions are mutually exclusive. Each project activity instance must fully meet one set.
- Instances that use different approaches must be separated by a **minimum 10 m buffer**.
- 4.1(1): The project activity increases vegetative cover.
- 4.1(2): When both approaches are used, they apply to non-overlapping areas defined at the project start.
- 4.1(3): The approach is selected at the project start date and used for the whole crediting period.
- 4.1(4): The project start date is the earliest of (a) the start of site preparation or (b) the land use change date.
- 4.1(5): On organic soils or wetlands, a multiple-project-activity design is required. VM0047 covers aboveground biomass, and a WRC methodology (e.g., VM0036) covers the other pools.

**Census-based conditions (§4.3, pp. 10–11)**

| # | Condition (v1.1 wording, condensed only where non-normative) |
|---|---|
| 1 | The project activity only includes direct planting. |
| 2 | Pre-project land use is maintained for the whole project lifetime. For example, on agricultural land, agricultural production continues. |
| 3 | Planting density does not exceed **50 planting units per hectare**. The limit applies proportionally to the size of each instance. (a) Instances under 1 ha, or with part of a hectare, are scaled proportionally: a 0.50 ha instance may have no more than 25 units. (b) Instances over 1 ha must disperse planting to stay within 50/ha across the whole instance. For example, a 10 ha instance may have up to 500 units, but they must not be concentrated in a single hectare or portion. |
| 4 | **Establishing the complete census marks the project start and is t = 0.** The census establishes N. Only units planted by the project proponent are included. Existing vegetation is not in the census and does not count toward the 50/ha limit. |
| 5 | Dead units may be replanted, provided N does not exceed 50 **live** planting units per hectare established by the project activity. |
| 6 | Each planting unit must be clearly defined and identifiable in the field, using **one** of two methods. (a) **GPS points**: spacing between units must be at least the GPS positional accuracy (e.g., 5 m accuracy means at least 5 m spacing). (b) **Physical markers**: a durable in-field identifier bearing a unique ID, clearly visible at verification. |
| 7 | A unit that cannot be located at a monitoring event is conservatively assumed dead. |
| 8 | The activity occurs (a) in an area with **< 10% pre-existing woody biomass cover**; and/or (b) in an area under **continuous cropping**, or in the IPCC "settlements" or "other lands" categories. Footnote 4 defines continuous cropping: "Cultivation of an agricultural crop on the same site year after year, without any periods of fallow exceeding one season, demonstrated over 10 or more years prior to the project start date." Footnote 5 cites the IPCC Guidelines Vol. 4 Ch. 3 for land use categories. |
| 9 | Soil disturbance from project activities: (a) is permitted only at planting, including replanting waves; (b) localized disturbance such as pit planting may exceed 25 cm depth; (c) soil inversion (e.g., plowing) must not exceed 25 cm depth and may occur only once in the crediting period. Footnotes 6–7 say that soil disturbance from the ongoing agricultural land use is not part of the project activity. |

**Census-based exclusions (§4.4.2, p. 12)**

1. Woody biomass serving a similar purpose to the planting units was removed within the last 10 years, as confirmed by pre-project photos and/or attestation.
2. Project soil disturbance involves inversion deeper than 25 cm (e.g., moldboard plow).

Also note §4.4.1(3) (area-based exclusion): a project planting **fewer than 50 units/ha that could use the census-based approach may not use the area-based approach.**

### 1.3 Project boundary and pools (§5, §5.2, §5.3, pp. 12–15)

- Each planting unit has a **10 m radius buffer**. Together the buffers define the accounting boundary of the instance.
- Buffers may overlap within an instance but must not overlap any other census-based or area-based instance.
- Appendix 2 of VM0047 (significance test, §3.5 below) is used to decide whether pools and sources are de minimis.

**Table 2: carbon pools, census-based (p. 14)**

| Pool | Included? | Justification |
|---|---|---|
| Aboveground woody biomass | Yes | Major carbon pool |
| Aboveground non-woody biomass | Excluded | Conservative to exclude |
| Belowground woody biomass | Yes | Major carbon pool |
| Belowground non-woody biomass | Excluded | Conservative to exclude |
| Dead wood | Excluded | Conservative to exclude |
| Litter | Excluded | Conservative to exclude |
| SOC | Excluded | Conservative to exclude |
| Harvested wood products | Excluded | Conservative to exclude |

**Table 3: GHG sources, both approaches (p. 15)**

- **Baseline**: all sources excluded (biomass burning, N fertilizer, fossil fuels; CO2, CH4, N2O), as conservative.
- **Project, biomass burning**: CO2 is No (counted as a stock change); **CH4 Yes**; **N2O Yes**.
- **Project, N fertilizer**: CO2 No; CH4 No; **N2O Yes**.
- **Project, fossil fuels**: No for all gases (de minimis).

### 1.4 Baseline (§6.2, p. 16; §8.1.2, p. 19)

- A project method is used. The activity must (1) be in an area with **< 10%** pre-existing woody biomass cover **and** (2) be on continuously cropped land or in the settlements or other lands categories.
- If both are met, it is assumed that ARR would not happen without the project, and **the crediting baseline is zero**.
- §8.1.2: the baseline is the absence of planting units, so baseline carbon stock changes are **zero**.

**Pre-existing trees:** they are not in the census (§4.3(4)) and are not accounted for. There is no pre-existing woody biomass quantification for census-based projects; §8.2.1.2 applies to area-based projects only. The eligibility gate is < 10% woody cover, and/or the land use type, and no removal of similar woody biomass in the past 10 years.

### 1.5 Additionality (§7.2 and §7.3, pp. 16–18), brief

Census-based projects need three demonstrations:

- **Regulatory surplus**, per the VCS Methodology Requirements.
- **Investment analysis**, per VT0008 Step 3. Footnote 11: "always required for census-based projects".
- **Common practice**, per §7.3.4:
  - Steps 1–6: define the activity, the geographic domain, and the adopter class; identify essential distinctions; survey a representative sample within 5 years of the start date; compute the cumulative adoption rate among non-carbon-finance adopters.
  - **An adoption rate < 15% means not common practice. A rate ≥ 15% means common practice and not additional** (Mathur et al. 2007).
  - Alternatively, use public statistics from within 5 years: agricultural census or government data, peer-reviewed literature, or industry reports.

### 1.6 What is counted and how (allometry)

- **Every planting unit** is censused at t = 0. For each unit, record (9.1 parameter N, p. 45): Unique ID, geo-referenced point, year planted, species.
- **Mortality** (M_t) comes from complete re-enumeration **or** representative sampling of the census list (9.2, pp. 57–58).
  - Suggested design: a stratified systematic sample within annual cohorts, with a random start.
  - A unit is dead if green vascular tissue (cambium) and green leaves are absent, or if it cannot be relocated.
- **Biomass** is measured on a representative sample of n_t units (9.2 parameter B_WP-woody-AB,pu,t, pp. 58–60).
  - Aboveground woody biomass per sampled plant uses **published allometric equations**, chosen in this order of preference:
    - (a) species-, genus- or family-specific equations from the same ecoregion or Holdridge life-zone;
    - (b) global species-, genus- or family-specific equations.
  - Global equations must have been developed from, or validated with, **destructive-sampling data from the same ecoregion or Holdridge life-zone**.
  - Independent variables (DBH, root-collar diameter, height) must be measured in the field following best practice (Kershaw et al. 2016; Avery & Burkhart 2015).
  - **Fixed size thresholds** must be kept for the whole crediting period. A live sampled unit **below the size threshold is assigned zero** and kept in the sample.
  - Double or two-phase sampling (3P, ratio) is allowed. Stratification is optional, and the sample design may change between events.
- **Root-to-shoot ratio R** and **CF = 0.47** convert AGB to total woody carbon (Eq. 25).
- **Wood density:** VM0047 does not specify a wood density source for live census biomass. Wood density appears only for dead wood (area-based), using published densities and Harmon et al. 2011 reduction factors. If the chosen allometric equation needs wood density, VM0047 v1.1 gives no source hierarchy (see §7, Ambiguities).
- Monitoring frequency for all census parameters: **every five years or more frequently.**

### 1.7 Calculation steps in order (census-based)

1. Confirm eligibility under §4.1, §4.3 and §4.4.2 and the baseline criteria in §6.2. Define the planting unit and the 10 m buffer accounting boundary, with no overlap.
2. At t = 0, carry out the complete census to get **N**: ID, GPS point, year planted, species. Check density ≤ 50/ha per instance and spacing ≥ GPS accuracy (or use physical markers).
3. At validation, prepare the ex-ante estimate (§8.7) with a growth and yield model. Apply Eq. 22, a baseline of 0, and an uncertainty deduction of at least 10%.
4. At each monitoring event (≤ 5 years apart):
   - (a) Assess mortality to get **M_t**.
   - (b) Sample n_t units and measure their attributes. Apply allometry to get **B_WP-woody-AB,pu,t**.
   - (c) Eq. 25 gives **C_WP-woody-pu_avg,t**.
   - (d) Eq. 24 gives **C_WP-woody,t**.
   - (e) Eq. 23 gives **ΔC_WP-woody,t**.
   - (f) Eq. 22 gives **ΔC_WP,t** (t CO2e).
5. Calculate project emissions **PE_t**:
   - burning, with Eqs. 26–27 (n_burn,t from the sample, COMF = 1.0);
   - fertilizer, with Eqs. 15–21;
   - then sum them as in Eq. 12.
   - Appendix 2 may allow sources to be deemed de minimis.
6. Calculate uncertainty: Eq. 31 gives U_M,t, Eq. 30 gives C_total,t, Eq. 29 gives UNC_t. If the 90% CI half-width exceeds 100% of the removal estimate, then CR_t = 0.
7. Leakage: **LK_t = 0** (§8.4).
8. Removals: Eq. 33 gives **CR_t**. Eq. 34 annualizes it.
9. If harvesting occurs, cap removals at the long-term average (VCS Standard).
10. Buffer and VCUs: outside VM0047; see §4.3 below.

---

## 2. Equations in scope

Notation: t = 1, 2, 3, … years since the project start date; x = length of the monitoring interval (years).

### 2.1 Census-based carbon stock change (§8.3.1)

#### Eq. (22): §8.3.1, p. 29. [TEXT-CLEAN; NEW in v1.1]

Plain: `ΔC_WP,t = (ΔC_WP-woody,t) × 44/12`

$$\Delta C_{WP,t} = \left(\Delta C_{WP\text{-}woody,t}\right) \times \frac{44}{12}$$

v1.0 had no separate census equation. It used Eq. (1) with SOC, non-woody, dead wood and litter set to zero (v1.0 p. 17). The result is the same.

| Symbol | Meaning | Unit |
|---|---|---|
| ΔC_WP,t | Project carbon stock change through year t | t CO2e |
| ΔC_WP-woody,t | Change in carbon stock in woody biomass in the project scenario through year t | t C |
| 44/12 | Ratio of molecular weight of CO2 to C | unitless |

Text after the equation (pp. 29–30): "Where a project proponent begins measuring carbon stocks after the start date (t > 0), the first year of measurement replaces t = 0 in all stock change calculations. Between t = 0 and t > 0, the project's carbon stock change must be assumed to be zero. The project start date remains t = 0 for all other purposes, including crediting period determination and baseline setting."

#### Eq. (23): §8.3.1.1, p. 30. [TEXT-CLEAN; V1.0-CONFIRMED = v1.0 Eq. (5), p. 19, unchanged]

Plain: `ΔC_WP-woody,t = C_WP-woody,t`

$$\Delta C_{WP\text{-}woody,t} = C_{WP\text{-}woody,t}$$

| Symbol | Meaning | Unit |
|---|---|---|
| ΔC_WP-woody,t | Change in carbon stock in woody biomass in the project scenario through year t | t C |
| C_WP-woody,t | "Average" carbon stock in woody biomass in the project scenario in year t (this is a project total) | t C |

"Note – Monitoring of the complete census of planting units is required." (p. 30)

#### Eq. (24): §8.3.1.1, p. 30. [RECONSTRUCTED; V1.0-CONFIRMED = v1.0 Eq. (6), p. 19, unchanged]

Plain: `C_WP-woody,t = N × (1 − M_t) × C_WP-woody-pu_avg,t`

$$C_{WP\text{-}woody,t} = N \times (1 - M_t) \times C_{WP\text{-}woody\text{-}pu\_avg,t}$$

| Symbol | Meaning | Unit |
|---|---|---|
| C_WP-woody,t | Average carbon stock in woody biomass in the project scenario in year t | t C |
| N | Initial population size (number of planting units) | count |
| M_t | Mortality through year t | % (use as a fraction) |
| C_WP-woody-pu_avg,t | Average carbon stock in woody biomass per planting unit in the project scenario in year t | t C/planting unit |

v1.0 wrote the subscript as C_WP-woody,pu_avg,t in Eq. 6. The difference is cosmetic.

#### Eq. (25): §8.3.1.1, pp. 30–31. [RECONSTRUCTED; V1.0-CONFIRMED = v1.0 Eq. (7), p. 19, unchanged]

Plain: `C_WP-woody-pu_avg,t = (1/n_t) × Σ_{pu=1}^{n_t} ( B_WP-woody-AB,pu,t × (1 + R) × CF )`

$$C_{WP\text{-}woody\text{-}pu\_avg,t} = \frac{1}{n_t} \times \sum_{pu=1}^{n_t}\left(B_{WP\text{-}woody\text{-}AB,pu,t} \times (1+R) \times CF\right)$$

| Symbol | Meaning | Unit |
|---|---|---|
| C_WP-woody-pu_avg,t | Average carbon stock in woody biomass per planting unit pu in year t | t C/planting unit |
| n_t | Number of planting units sampled in year t | integer |
| B_WP-woody-AB,pu,t | Estimated aboveground woody biomass in sampled planting unit pu in year t | t d.m. |
| R | Root-to-shoot ratio | t root d.m./t shoot d.m. (listed as "dimensionless" in 9.1) |
| CF | Carbon fraction of dry biomass | t C/t d.m. (default 0.47) |

§8.3.1.2–8.3.1.5 (p. 31): non-woody biomass, dead wood, litter and SOC are "Not applicable (see Table 2)".

### 2.2 Census-based project emissions (§8.3.2)

§8.3.2 (p. 31) says census-based emissions are estimated with "Equations (26) - (27) and (15) –(21) to respectively". The sentence is garbled in the original. It means Eqs. 26–27 for burning and Eqs. 15–21 for fertilizer.

The total is **Eq. (12)**, from §8.2.2, p. 24. [TEXT-CLEAN; = v1.0 Eq. (15), p. 22]

Plain: `PE_t = PE_bburn,t + PE_fert,t`

$$PE_t = PE_{bburn,t} + PE_{fert,t}$$

| Symbol | Meaning | Unit |
|---|---|---|
| PE_t | Project emissions from biomass burning and fertilizer use in the monitoring interval ending in year t | t CO2e |
| PE_bburn,t | Project emissions due to biomass burning in the monitoring interval ending in year t | t CO2e |
| PE_fert,t | Project emissions from N fertilizer in the monitoring interval ending in year t | t CO2e |

Eq. 12 sits in the area-based section, but §8.3.2 implicitly relies on it. See ambiguity A10.

#### Eq. (26): §8.3.2.1, p. 31. [RECONSTRUCTED; V1.0-CONFIRMED = v1.0 Eq. (18), p. 23, unchanged]

Plain: `PE_bburn,t = Σ_{g=1}^{G} ( GWP_g × EF_g × B_WP,t × COMF × 10^-3 )`

$$PE_{bburn,t} = \sum_{g=1}^{G}\left(GWP_g \times EF_g \times B_{WP,t} \times COMF \times 10^{-3}\right)$$

| Symbol | Meaning | Unit |
|---|---|---|
| PE_bburn,t | Project emissions due to biomass burning in the monitoring interval ending in year t | t CO2e |
| GWP_g | Global warming potential for gas g | dimensionless |
| EF_g | Emission factor for gas g | kg/t d.m. burned |
| B_WP,t | Aboveground biomass stock subject to burning in the monitoring interval ending in year t | t d.m. |
| COMF | Combustion factor (census-based: **1.0**) | dimensionless |
| g | 1, …, G greenhouse gases (CH4 and N2O) | — |

Unlike area-based Eq. 13, there is no area term: B_WP,t is already a project total.

#### Eq. (27): §8.3.2.1, p. 32. [RECONSTRUCTED; V1.0-CONFIRMED = v1.0 Eq. (19), p. 24; Δt renamed x]

Plain: `B_WP,t = (N × n_burn,t / n_t) × (1 / n_{t−x}) × Σ_{pu=1}^{n_t} B_WP-woody-AB,pu,t−x`

$$B_{WP,t} = \left(N \times \frac{n_{burn,t}}{n_t}\right) \times \left(\frac{1}{n_{t-x}}\right) \times \sum_{pu=1}^{n_t} B_{WP\text{-}woody\text{-}AB,pu,t-x}$$

v1.0 Eq. 19 is written as N × (n_burn,t / n_t) × (1/n_{t−Δt}) × Σ_{pu=1}^{n_t} B_{…,pu,t−Δt}. This is mathematically identical. In both versions the summation's upper limit is **n_t**, not n_{t−x}; see ambiguity A6.

| Symbol | Meaning | Unit |
|---|---|---|
| B_WP,t | "Average aboveground biomass stock subject to burning … (t d.m./ha)", as written. Eq. 26's list gives t d.m. | see A6 |
| N | Initial population size | count |
| n_t | Number of planting units sampled in year t | integer |
| n_burn,t | Number of sampled planting units recorded as burned in the monitoring interval ending in year t | integer |
| B_WP-woody-AB,pu,t−x | Aboveground woody biomass in sampled unit pu in year t − x | t d.m. |
| n_{t−x} | Number of planting units sampled in year t − x | integer |
| x | Length of monitoring interval | years |

Text (pp. 31–32): the aboveground stock subject to burning is "estimated from measurements prior to the burn". It is scaled by N "and adjusting for the percentage of sampled planting units observed to be visibly burned at each monitoring event."

#### Fertilizer, Eqs. (15)–(21): §8.2.2.2, pp. 25–28; applied to census-based projects by §8.3.2.2, p. 32

v1.1 Eqs. 15–21 equal v1.0 Eqs. 20–26 (v1.0 pp. 24–26). Pages 24–25 were rendered: Eqs. 20–24 are identical in form. Eqs. 25–26 were checked against the clean v1.0 text layer and are identical in form.

**Eq. (15)** [RECONSTRUCTED; V1.0-CONFIRMED]

Plain: `PE_fert,t = PE_Ndirect,t + PE_Nindirect,t`

$$PE_{fert,t} = PE_{Ndirect,t} + PE_{Nindirect,t}$$

**Eq. (16)** [RECONSTRUCTED; V1.0-CONFIRMED]

Plain: `PE_Ndirect,t = (F_wp,SN,t + F_wp,ON,t) × EF_Ndirect × 44/28 × GWP_g`

$$PE_{Ndirect,t} = \left(F_{wp,SN,t} + F_{wp,ON,t}\right) \times EF_{Ndirect} \times \frac{44}{28} \times GWP_g$$

**Eq. (17)** [RECONSTRUCTED; V1.0-CONFIRMED]

Plain: `F_wp,SN,t = M_wp,SF,t × NC_wp,SF,t`

$$F_{wp,SN,t} = M_{wp,SF,t} \times NC_{wp,SF,t}$$

**Eq. (18)** [RECONSTRUCTED; V1.0-CONFIRMED]

Plain: `F_wp,ON,t = M_wp,OF,t × NC_wp,OF,t`

$$F_{wp,ON,t} = M_{wp,OF,t} \times NC_{wp,OF,t}$$

**Eq. (19)** [RECONSTRUCTED; V1.0-CONFIRMED]

Plain: `PE_Nindirect,t = Nfert_wp,volat,t + Nfert_wp,leach,t`

$$PE_{Nindirect,t} = Nfert_{wp,volat,t} + Nfert_{wp,leach,t}$$

**Eq. (20)** [RECONSTRUCTED; V1.0-CONFIRMED]

Plain: `Nfert_wp,volat,t = [(F_wp,SN,t × Frac_GASF) + (F_wp,ON,t × Frac_GASM)] × EF_Nvolat × 44/28 × GWP_g`

$$Nfert_{wp,volat,t} = \left[\left(F_{wp,SN,t} \times Frac_{GASF}\right) + \left(F_{wp,ON,t} \times Frac_{GASM}\right)\right] \times EF_{Nvolat} \times \frac{44}{28} \times GWP_g$$

**Eq. (21)** [RECONSTRUCTED; V1.0-CONFIRMED]

Plain: `Nfert_wp,leach,t = (F_wp,SN,t + F_wp,ON,t) × Frac_LEACH × EF_Nleach × 44/28 × GWP_g`

$$Nfert_{wp,leach,t} = \left(F_{wp,SN,t} + F_{wp,ON,t}\right) \times Frac_{LEACH} \times EF_{Nleach} \times \frac{44}{28} \times GWP_g$$

| Symbol | Meaning | Unit |
|---|---|---|
| PE_fert,t | Project emissions from N fertilizer in the monitoring interval ending in year t | t CO2e |
| PE_Ndirect,t | Direct N2O emissions due to fertilizer use in the monitoring interval ending in year t. Written "PE_N,direct,t" in the where-list. | t CO2e |
| PE_Nindirect,t | Indirect N2O emissions due to fertilizer use in the monitoring interval ending in year t | t CO2e |
| F_wp,SN,t | Synthetic N fertilizer applied in the monitoring interval ending in year t | t N |
| F_wp,ON,t | Organic N fertilizer applied in the monitoring interval ending in year t | t N |
| M_wp,SF,t | Mass of N-containing synthetic fertilizer applied | t |
| M_wp,OF,t | Mass of N-containing organic fertilizer applied | t |
| NC_wp,SF,t | N content of synthetic fertilizer | t N/t fertilizer |
| NC_wp,OF,t | N content of organic fertilizer | t N/t fertilizer |
| EF_Ndirect | Emission factor for direct N2O from N additions (synthetic fertilizers, organic amendments, crop residues) | t N2O-N/t N applied (default 0.01) |
| Frac_GASF | Fraction of synthetic N that volatilizes as NH3 and NOx | dimensionless (0.11) |
| Frac_GASM | Fraction of organic N that volatilizes as NH3 and NOx | dimensionless (0.21) |
| EF_Nvolat | EF for N2O from atmospheric deposition of N on soils and water surfaces | t N2O-N/(t NH3-N + NOx-N volatilized) (0.01) |
| Frac_LEACH | Fraction of synthetic or organic N lost through leaching and runoff, where these occur | dimensionless (0.24) |
| EF_Nleach | EF for N2O from leaching and runoff | t N2O-N/t N leached and runoff (0.011) |
| Nfert_wp,volat,t | Indirect N2O from atmospheric deposition of volatilized N | t CO2e |
| Nfert_wp,leach,t | Indirect N2O from leaching and runoff | t CO2e |
| GWP_g | GWP of N2O | dimensionless |
| 44/28 | Ratio of molecular weight of N2O to N | unitless |

### 2.3 Uncertainty (§8.5)

General rules (§8.5, p. 32):

- Sample error is quantified. Measurement error is handled through QA/QC.
- "Estimation of emission sources from biomass burning and nitrogen fertilizer apply conservative parameters and associated uncertainty is set at zero."

Census-based rules (§8.5.2, p. 33):

- Uncertainty in N is zero, because the census is complete.
- The zero baseline has zero uncertainty.

#### Eq. (28): §8.5.1, p. 33. AREA-BASED; included for reference only. [RECONSTRUCTED; CHANGED vs v1.0 Eq. (27)]

Plain: `UNC_t = MIN(100%, MAX(0, (T × √(SE²_p,t=0 + SE²_p,t − (2 × ρ × SE_p,t=0 × SE_p,t)) / ΔC − 0.10) × 100))`

$$UNC_t = \mathrm{MIN}\left(100\%,\ \mathrm{MAX}\left(0,\ \left(\frac{T \times \sqrt{SE_{p,t=0}^2 + SE_{p,t}^2 - \left(2 \times \rho \times SE_{p,t=0} \times SE_{p,t}\right)}}{\Delta C} - 0.10\right) \times 100\right)\right)$$

v1.0 Eq. 27 was a different form: (Σ(U_p,t=0 × C_p,t=0)² + Σ(U_p,t × C_p,t)²)^½ × 1/(ΔC_biomass + ΔC_SOC) − 10%.

#### Eq. (29): §8.5.2, p. 33. CENSUS-BASED. [RECONSTRUCTED; CHANGED vs v1.0 Eq. (28)]

Plain: `UNC_t = MIN(100%, MAX(0, (T × √(SE²_p,t + (C_total,t × U_M,t / 100)²) / C_total,t − 0.10) × 100))`

$$UNC_t = \mathrm{MIN}\left(100\%,\ \mathrm{MAX}\left(0,\ \left(\frac{T \times \sqrt{SE_{p,t}^2 + \left(C_{total,t} \times \frac{U_{M,t}}{100}\right)^2}}{C_{total,t}} - 0.10\right) \times 100\right)\right)$$

How the reconstruction was built. The garbled glyph order is: `UNC_t = MIN (100%, MAX (0, T ( × √ SE_p,t 2 C( + total,t U × M,t / 100 )2 / C_total,t )− 0.10 )× 100 )`. The denominators "100" and "C_total,t" appear on separate lines, which is how PDF fraction bars are extracted. The placement of the bracket around the T term is an inference.

v1.0 Eq. 28 (rendered, p. 28) was: `UNC_t = MIN(100%, MAX(0, (U_p,t² + U²_M,t)^½ − 10%))`, where U_p,t is the percentage uncertainty (90% CI as a percentage of the mean) of woody biomass. **v1.1 replaces U_p,t with an SE-based term and rescales U_M,t by C_total,t.** See ambiguity A7.

| Symbol | Meaning | Unit |
|---|---|---|
| UNC_t | Uncertainty in cumulative removals through year t | % |
| U_M,t | Percentage uncertainty in population size adjusted for mortality in year t | % |
| T | Critical value of Student's two-tailed t-distribution for α = 0.1 | — |
| SE_p,t | Standard error of average woody biomass per planting unit in pool p (here woody biomass only) at time t | t CO2e |
| C_total,t | Total carbon stock at time t. The text says "calculated using Equation (29)"; it should be Eq. 30. | t CO2e |

#### Eq. (30): §8.5.2, p. 34. [RECONSTRUCTED; NEW in v1.1]

Plain: `C_total,t = N × (1 − M_t) × C̄_pu,t`

$$C_{total,t} = N \times (1 - M_t) \times \bar{C}_{pu,t}$$

| Symbol | Meaning | Unit |
|---|---|---|
| N | Initial population size | count |
| M_t | Mortality through year t | % |
| C̄_pu,t | Mean carbon per planting unit at time t | t CO2e |

#### Eq. (31): §8.5.2, p. 34. [RECONSTRUCTED; V1.0-CONFIRMED = v1.0 Eq. (29), p. 28, unchanged in form]

Plain: `U_M,t = T × √( M_t × (1 − M_t) / (n_t − 1) ) × 1/(1 − M_t)`

$$U_{M,t} = T \times \sqrt{\frac{M_t \times (1 - M_t)}{n_t - 1}} \times \frac{1}{1 - M_t}$$

v1.0 wrote it as T × ((M_t(1−M_t))/(n_t−1))^½ × (1/(1−M_t)), which is identical. v1.1 adds "two-tailed" to the definition of T.

| Symbol | Meaning | Unit |
|---|---|---|
| U_M,t | Percentage uncertainty in population size adjusted for mortality | % |
| T | Two-tailed Student's t critical value, α = 0.1 | — |
| M_t | Mortality through year t | % |
| n_t | Number of planting units sampled in year t | integer |

**Eligibility rule (p. 34):** "For both census- and area-based quantification approaches, a project is not eligible for crediting (CR_t = 0) where the half-width of the two-sided 90% confidence interval exceeds 100% of the carbon dioxide removal estimate."

Appendix 3 (Eqs. A11–A16, pp. 79–80) covers switching sampling approaches. It is explicitly for the area-based approach and is out of scope.

### 2.4 Removals (§8.6)

General rule (§8.6, pp. 34–35):

- For monitoring intervals longer than one year, compare the stock at t with the stock at t − x.
- Divide the total for the interval by the number of years (Eq. 34), so that each year in the interval gets an equal CR_t.

#### Eq. (32): §8.6.1, p. 34. AREA-BASED; included because it is where VMD0054 LK_t enters. [RECONSTRUCTED; CHANGED vs v1.0 Eq. (30)]

Plain: `CR_t = (MIN(ΔC_WP,t, ΔC_WP,t × (1 − PB_t)) × (1 − UNC_t)) − PE_t − LK_t − ((MIN(ΔC_WP,t−x, ΔC_WP,t−x × (1 − PB_t−x)) × (1 − UNC_t−x)) − PE_t−x − LK_t−x)`

$$CR_t = \left(\mathrm{MIN}\left(\Delta C_{WP,t},\ \Delta C_{WP,t}\times(1-PB_t)\right)\times(1-UNC_t)\right) - PE_t - LK_t - \left(\left(\mathrm{MIN}\left(\Delta C_{WP,t-x},\ \Delta C_{WP,t-x}\times(1-PB_{t-x})\right)\times(1-UNC_{t-x})\right) - PE_{t-x} - LK_{t-x}\right)$$

v1.0 Eq. 30 had no MIN wrapper and used t−1 instead of t−x.

| Symbol | Meaning | Unit |
|---|---|---|
| CR_t | Carbon dioxide removals in the monitoring interval ending in year t | t CO2e |
| ΔC_WP,t | Project carbon stock change through year t | t CO2e |
| PB_t | Performance benchmark for the interval ending in year t | % |
| LK_t | Leakage through year t | t CO2e |
| PE_t | Project emissions from biomass burning and fertilizer use in year t | t CO2e |
| UNC_t | Uncertainty in cumulative removals through year t | % |

#### Eq. (33): §8.6.2, p. 35. CENSUS-BASED. [TEXT-CLEAN; CHANGED vs v1.0 Eq. (31): t−1 becomes t−x, otherwise identical]

Plain: `CR_t = (ΔC_WP,t × (1 − UNC_t)) − (ΔC_WP,t−x × (1 − UNC_t−x)) − PE_t`

$$CR_t = \left(\Delta C_{WP,t} \times (1 - UNC_t)\right) - \left(\Delta C_{WP,t-x} \times (1 - UNC_{t-x})\right) - PE_t$$

| Symbol | Meaning | Unit |
|---|---|---|
| CR_t | CO2 removals over the monitoring interval ending in year t | t CO2e |
| ΔC_WP,t | Project carbon stock change through year t (Eq. 22) | t CO2e |
| UNC_t | Uncertainty through year t (Eq. 29). Not in the where-list for Eq. 33, but defined in Eq. 29. | % |
| PE_t | Project emissions from biomass burning and fertilizer use in year t | t CO2e |

Baseline and leakage are "implicitly set equal to zero".

Further rules on p. 35:

- If area-based and census-based approaches are combined, total removals are the sum of the two, calculated independently on non-overlapping areas.
- If harvesting occurs, apply the VCS Standard long-term average (LTA) as an upper limit.

#### Eq. (34): §8.6.3, p. 36. [RECONSTRUCTED; NEW as an equation in v1.1; v1.0 described it in words on p. 29]

Plain: `CR_annualized = CR_t / x`

$$CR_{annualized} = \frac{CR_t}{x}$$

| Symbol | Meaning | Unit |
|---|---|---|
| CR_annualized | Annualized CO2 removals | t CO2e/year |
| CR_t | CO2 removals over the monitoring interval t | t CO2e |
| x | Length of the monitoring period | years |

### 2.5 Ex-ante estimate (§8.7, pp. 36–37), census part

1. At validation, make ex-ante estimates **for the length of the crediting period**. v1.0 required a 10-year window instead. Use growth and yield models with data and parameters that conservatively represent the project activity.
2. Include any harvest or management regimes in the model.
3. Apply an uncertainty deduction of **at least 10%**. A larger deduction may be chosen.
4. (b) For the census-based approach, use Eq. 22. The growth and yield model output must give ΔC_WP-woody,t in **t C**.
5. The ex-ante baseline is **zero** for census-based projects.
6. (Area-based only; not applicable.)
7. Other pools and sources (e.g., SOC) may be assumed to be zero where that is conservative.

### 2.6 Significance testing (Appendix 2, pp. 77–78), applies to census-based PE sources

Leakage is excluded from this test.

#### Eq. (A9) [TEXT-CLEAN]

Plain: `CSR = Σ E_s / CR`

$$CSR = \frac{\sum E_s}{CR}$$

- If CSR < 0.05, all optional sources are de minimis.
- If CSR ≥ 0.05, go to Step 2.

#### Eq. (A10) [TEXT-CLEAN]

Plain: `RC_Es = E_s / Σ E_s`

$$RC_{E_s} = \frac{E_s}{\sum E_s}$$

Step 2 procedure:

1. Rank the sources from largest to smallest.
2. Add them starting from the largest, stopping when the cumulative total reaches at least 95%.
3. Include all sources up to that point.
4. The remaining sources may be excluded only if their combined impact is also less than 5% of total CR. Otherwise keep adding sources until that holds.

| Symbol | Meaning | Unit |
|---|---|---|
| CSR | Combined significance ratio | — |
| E_s | Project GHG emissions and decreases in optional carbon pools, per source s | t CO2e |
| CR | Total carbon dioxide removals expected from the project | t CO2e |
| RC_Es | Relative contribution of source s. The definition says "to the sum of project and leakage GHG emissions", which conflicts with the leakage-excluded note. | — |

---

## 3. Default values, constants, tables, external references

| Item | Value or source | Where (v1.1) |
|---|---|---|
| CF, carbon fraction | **0.47** t C/t d.m.; source 2006 IPCC Guidelines | 9.1, pp. 39–40 |
| R, root-to-shoot | **No numeric default**; "Project-specific". See the hierarchy below. | 9.1, pp. 38–39 |
| COMF | **1.0 for census-based projects** (conservative). Area-based uses IPCC 2019 Refinement Vol. 4 Ch. 2 **Table 2.6**. | 9.1, p. 40 |
| EF_g (CH4, N2O from burning) | Project-specific. Source as written: "Table 2.2 in Chapter 2, Volume 2 of the 2006 IPCC Guidelines (and in the same document, Appendix 2 …)". See A13. | 9.1, pp. 40–41 |
| GWP_g | "Default factor from the most recent IPCC assessment report" | 9.1, p. 41 |
| EF_Ndirect | **0.01** t N2O-N/t N; IPCC 2019 Refinement Vol. 4 Ch. 11 Table 11.1 | 9.1, pp. 41–42 |
| Frac_GASF | **0.11**; Table 11.3 | 9.1, p. 42 |
| Frac_GASM | **0.21**; Table 11.3 | 9.1, p. 43 |
| EF_Nvolat | **0.01**; Table 11.3 | 9.1, p. 43 |
| Frac_LEACH | **0.24**; Table 11.3 | 9.1, p. 44 |
| EF_Nleach | **0.011**; Table 11.3 | 9.1, pp. 44–45 |
| 44/12; 44/28; 10⁻³ | Molecular weight ratios; kg-to-t conversion | Eqs. 22, 16, 20, 21, 26 |
| T | Two-tailed Student's t, α = 0.1. Degrees of freedom are not stated. | Eqs. 29, 31 |
| Ex-ante minimum uncertainty deduction | **10%** | §8.7(3), p. 36 |
| UNC deduction threshold | 0.10 subtracted inside Eqs. 28 and 29 (only uncertainty above 10% is deducted) | pp. 33 |
| Crediting cut-off | 90% CI half-width > 100% of removals means CR_t = 0 | p. 34 |
| Density cap | 50 planting units/ha, prorated per instance | §4.3(3), p. 10 |
| Buffer per planting unit | 10 m radius; ≥ 10 m separation between instances | §4, p. 8; §5.2, p. 14 |
| Pre-existing woody cover | < 10% | §4.3(8), §6.2 |
| Soil inversion | ≤ 25 cm, once | §4.3(9), §4.4.2 |
| Woody removal look-back | 10 years | §4.4.2(1) |
| Continuous cropping | ≥ 10 years with no fallow longer than one season | fn. 4 |
| Common practice threshold | < 15% adoption | §7.3.4, p. 18 |
| Monitoring frequency | Every 5 years or more often | 9.2 |
| Data archiving | Keep for at least 2 years after the end of the last crediting period | §9.3(8), p. 62 |
| Significance threshold | 5% (CSR) and a 95% cumulative rule | App. 2, pp. 77–78 |

**R selection hierarchy (9.1, pp. 38–39)**

- For facilitated natural regeneration, or more than two species in a single stand:
  1. Forest-type values from the same ecoregion (biome level, Olson et al. 2001) or Holdridge life-zone.
  2. Global forest-type values (e.g., IPCC 2019 Refinement Vol. 4 Ch. 4 **Table 4.4**).
- Otherwise (e.g., monocultures):
  3. Species-, genus- or family-specific values from the same ecoregion or life-zone.
  4. Global species-, genus- or family-specific values (e.g., Table 4.4).
- A global R must have been developed from, or validated with, destructive-sampling data from the same ecoregion or life-zone.
- For census-based projects (direct planting only), branch 1–2 applies only to stands with more than two species. See A4.

**Wood density:** not specified for live census biomass. For area-based dead wood, VM0047 uses published densities (species > genus > family > forest type) with Harmon et al. 2011 decay-class reduction factors (9.2, pp. 50–51).

**CDM tools**

- **VM0047 v1.1 does not reference AR-Tool14 or AR-Tool12 anywhere.** A search of the full text found no "AR-Tool", "AR-TOOL14" or "AR-TOOL12". VM0047 does not use those CDM tools for biomass or dead wood.
- §2 Sources (p. 6) lists:
  - AR-ACM0003 as the base methodology;
  - "CDM Tool for Testing Significance of GHG Emissions in A/R CDM Project Activities". The tool number is not given in the text, and none is inferred here.
  - VT0001.
- Additionality uses **VT0008** Step 3 (investment analysis).
- 9.2 states that VT0005 (remote sensing biomass) does not apply.
- **VMD0054 v1.1** references **AR-TOOL15 v2.0** (displacement of pre-project agricultural activities). It informed the module and is the source of the **1.1 dead wood + litter multiplier** (VMD0054 p. 26, footnote 6).

**Other external data the census-based approach needs:** published allometric equations (literature); R (IPCC 2019 Table 4.4 or ecoregional literature); IPCC EF and GWP; a growth and yield model for ex-ante estimates; the AFOLU Non-Permanence Risk Tool for the buffer.

---

## 4. Uncertainty, buffer, VCU computation

### 4.1 Uncertainty (census-based)

- The only stochastic components are the per-unit biomass sampling error (SE_p,t) and the mortality sampling error (U_M,t). N has zero uncertainty, and so does the baseline.
- Burning and fertilizer emissions have zero uncertainty, because conservative parameters are used.
- UNC_t is the uncertainty above 10% only, capped at 100%: Eq. 29 subtracts 0.10.
- Apply UNC_t as a **fraction** in (1 − UNC_t) in Eq. 33.
- If the 90% CI half-width exceeds 100% of the removal estimate, CR_t = 0.
- If M_t comes from a **complete re-enumeration**, the sampling uncertainty in mortality is arguably zero. VM0047 does not say this explicitly; Eq. 31 assumes sampling. See A8.

### 4.2 Net removals

- Eq. 33 is the cumulative-difference form: credited stock at t, minus credited stock at t − x, minus interval emissions.
- Eq. 34 annualizes it.

### 4.3 Buffer and VCUs (not in VM0047; from the VCS rules)

**VM0047 v1.1 has no buffer or non-permanence equation.** It never mentions the AFOLU Non-Permanence Risk Tool. The buffer comes from the VCS Program:

- **VCS Standard v5.0 §3.14.15:** "The number of VCUs issued to projects is determined by subtracting out the buffer credits from the reductions and/or removals (including leakage) associated with the project. The buffer credits are calculated by multiplying the non-permanence risk rating (as determined by the AFOLU Non-Permanence Risk Tool) by the change in carbon stocks only."
- **AFOLU Non-Permanence Risk Tool v5.0:**
  - §2.5.1: Overall Risk Rating = Internal (Table 5) + External (Table 9) + Natural (Table 11), rounded up to the nearest whole percent.
  - §2.5.2: the **minimum rating is 12**.
  - §2.5.3: a rating above 60 fails. The category thresholds are Internal 35, External 20 and Natural 35.
  - §2.5.4: the rating, converted to a percentage, is multiplied by "the net change in the project's carbon stocks".

Implementation form, derived from the VCS rules quoted above and not from VM0047:

```
Buffer_t = RiskRating% × (net change in carbon stocks for the interval)   -- stock change only; excludes PE
VCU_t    = CR_t − Buffer_t       (census-based: LK_t = 0)
```

Exactly which stock-change quantity is used is a VCS rule, not a VM0047 rule. It could be ΔC_WP,t − ΔC_WP,t−x before or after the uncertainty deduction. See A15. Also check that the locally held Standard (v5.0) and risk tool (v5.0) are the versions in force for the project.

---

## 5. VMD0054 v1.1: leakage

### 5.1 Scope and when leakage is zero

**Census-based VM0047: LK_t = 0.** VM0047 §8.4 (p. 32): "In the census-based quantification approach, LK_t is set equal to zero. The requirement that the ARR project activity maintains pre-project agricultural production levels avoids a change in land use and the planting density threshold avoids any significant displacement of a pre-existing land use due to land use changes such that leakage effects are assumed to be de minimis." See also §1.2(6), p. 6.

**Area-based VM0047:** must use VMD0054. Leakage "must not be assumed to be de minimis" (§4.2(3), p. 10).

**VMD0054's own de minimis rule (§4, p. 6):** leakage may be deemed de minimis only if the project lands **have not been used for agricultural activities or fuelwood production in the 10 years before the project start date**. This must be evidenced by remote sensing of land use **and** landowner or manager attestations.

**Leakage reaches zero within VMD0054 when:**

- **AL_t ≤ 0** (Eq. 10 MAX). This happens when leakage mitigation or cross-commodity land sparing is at least as large as the displaced production. There is no credit for net sparing.
- **CP_j,t ≤ BP − MP**, i.e., no production decline. Note that in v1.1 a negative l_j,t is allowed per commodity (cross-commodity accounting), and the floor is applied only to the aggregate in Eq. 10.

**Duration and scope (§5, p. 6):**

- Leakage is calculated for the **entire project area** and for **at least five years from the project start date**.
- For grouped projects: five years after the most recent instance is added.
- Footnote 1: displacement is a one-time occurrence. Leakage accounted at one verification is not counted again.

### 5.2 Steps and equations

#### Step 1: change in production in the project area (§5.1, pp. 6–8)

**Step 1.1:** the historical reference period is the **longer** of (1) the 3 years immediately before the project or instance start date and (2) one complete crop rotation.

**Step 1.2:** identify every commodity affected, whether displaced or introduced as cross-commodity production. Data sources, in order of priority:

1. Grower records.
2. Remote sensing calibrated and validated in a similar region and for the same commodities.
3. The most recent national or sub-national census averages for a similar ownership type and holding size.
4. For fuelwood, IPCC regional AGB growth rates.

**Eq. (1)**, p. 7. [RECONSTRUCTED; V1.0-CONFIRMED = v1.0 Eq. (1), p. 6, identical]

Plain: `BP_j,t = (Σ_{h=1}^{H} p_j,h / H) × (1 + r_j)^t`

$$BP_{j,t} = \frac{\sum_{h=1}^{H} p_{j,h}}{H} \times (1 + r_j)^t$$

| Symbol | Meaning | Unit |
|---|---|---|
| BP_j,t | Baseline production in the project area of commodity j in year t | units of production |
| p_j,h | Production in the project area of commodity j in year h of the historical reference period | units of production |
| H | Duration of the historical reference period | years |
| r_j | Annual growth rate of yield for commodity j (default 2.5%) | % (use as a fraction) |

"Note – For new cross-commodity production introduced as part of the project activity, baseline production (BP_j,t) is set to zero."

**Eq. (2)**, p. 8. [RECONSTRUCTED; NEW in v1.1. v1.0 defined MP_j,t only in words, as monitored production for up to five years after start.]

Plain: `MP_j,t = Σ_{t=1}^{t} p_j,t / W`

$$MP_{j,t} = \frac{\sum_{t=1}^{t} p_{j,t}}{W}$$

| Symbol | Meaning | Unit |
|---|---|---|
| MP_j,t | Monitored production in the project area of commodity j in year t | units of production |
| p_j,t | Production in the project area of commodity j in year t of the project period | units of production |
| W | Duration of the current monitoring period | years |

The text calls MP_j,t "the average annual production observed in the project area in year t". See A17.

**Step 1.3, Eq. (3)**, p. 8. [TEXT-CLEAN; = v1.0 Eq. (2), p. 6, with FP renamed CP]

Plain: `CP_j,t = BP_j,t − MP_j,t`

$$CP_{j,t} = BP_{j,t} - MP_{j,t}$$

| Symbol | Meaning | Unit |
|---|---|---|
| CP_j,t | Change in production in the project area of commodity j in year t | units of production |

#### Step 2 (optional): leakage mitigation (§5.2, pp. 8–11)

Requirements for leakage mitigation (pp. 8–9):

1. The leakage mitigation area is **outside the project area**.
2. It is in the **same country**.
3. There is an exclusive claim, by agreement with the landowner or manager, to a specified amount of increased production, stated as a percentage or an absolute value.
4. Mitigation is counted only in years when the agreement is in force, and the **agreement term is at least 5 years**.
5. Significant GHG increases are accounted for using **VM0047 Appendix 2**, including supplemental feedstock emissions.
6. Livestock intensification must not exceed maximum carrying capacity, as shown by independent expert reports or attestations.
7. Fuelwood mitigation is only through **new tree plantations**.

The mitigation historical reference period is the longer of the 3 years before the mitigation start or one crop rotation.

**Eq. (4)**, p. 10. [RECONSTRUCTED; V1.0-CONFIRMED = v1.0 Eq. (3), p. 7, with the index changed: v1.0 used h and H, v1.1 uses k and K]

Plain: `OBP_j,t = (Σ_{k=1}^{K} op_j,k / K) × (1 + r_j)^t`

$$OBP_{j,t} = \frac{\sum_{k=1}^{K} op_{j,k}}{K} \times (1 + r_j)^t$$

| Symbol | Meaning | Unit |
|---|---|---|
| OBP_j,t | Baseline production in the leakage mitigation area, commodity j, year t | units of production |
| op_j,k | Baseline production in the mitigation area, commodity j, year k of the mitigation reference period | units of production |
| K | Duration of the leakage mitigation historical reference period | years |
| r_j | Annual growth rate of yield | % |

OBP_fuelwood,t = 0, because only new plantations are eligible.

**Eq. (5)**, p. 10. [RECONSTRUCTED; V1.0-CONFIRMED = v1.0 Eq. (4), p. 8, identical]

Plain: `LM_j,t = OMP_j,t − OBP_j,t`

$$LM_{j,t} = OMP_{j,t} - OBP_{j,t}$$

| Symbol | Meaning | Unit |
|---|---|---|
| LM_j,t | Leakage mitigation for commodity j in year t | units of production |
| OMP_j,t | Monitored production in the leakage mitigation area | units of production |

**Eq. (6)**, p. 10. [RECONSTRUCTED; CHANGED vs v1.0 Eq. (5): v1.0 was l_j,t = MAX(FP_j,t − LM_j,t, 0); **v1.1 drops the MAX**]

Plain: `l_j,t = CP_j,t − LM_j,t`

$$l_{j,t} = CP_{j,t} - LM_{j,t}$$

| Symbol | Meaning | Unit |
|---|---|---|
| l_j,t | Net change in production subject to leakage, commodity j, year t | units of production |

**Step 2.2, Eq. (7)**, p. 11. [RECONSTRUCTED; NEW in v1.1]

Plain: `E_LM,t = Σ_{t=0}^{t} (E_fert,t + E_FF,t)`

$$E_{LM,t} = \sum_{t=0}^{t}\left(E_{fert,t} + E_{FF,t}\right)$$

| Symbol | Meaning | Unit |
|---|---|---|
| E_LM,t | Total leakage mitigation emissions in year t. The text calls it "cumulative … through time t". | t CO2e |
| E_fert,t | Mitigation emissions from the incremental increase in fertilizer use, calculated with **VM0047 Eqs. 15–21** applied to mitigation-area data | t CO2e |
| E_FF,t | Mitigation emissions from the incremental increase in fossil fuel use | t CO2e |

**Eq. (8)**, p. 11. [RECONSTRUCTED; NEW in v1.1]

Plain: `E_FF,t = Σ_{i,j} (F_i,j × EF_i)`

$$E_{FF,t} = \sum_{i,j}\left(F_{i,j} \times EF_i\right)$$

| Symbol | Meaning | Unit |
|---|---|---|
| F_i,j | Quantity of fossil fuel i consumed due to the mitigation activity for commodity j | volume unit |
| EF_i | Emission factor for fossil fuel i. Unit listed as "dimensionless"; see A19. Use the upper bound of IPCC 2019 Vol. 2 Ch. 3 values, or peer-reviewed country-specific values. | — |

Fertilizer assessment and the carrying-capacity demonstration are not required if the mitigation area is in a registered carbon project that assesses GHG and SOC changes (p. 12).

#### Step 3: land impact (§5.3, pp. 12–14)

**Table 1: default IS_j and NL_j (pp. 12–13)**

| | Leakage-only: displaced agricultural | Leakage-only: displaced fuelwood | Cross-commodity: displaced agricultural | Cross-commodity: introduced agricultural |
|---|---|---|---|---|
| Increased supply IS_j (%) | **75** | **100** | **100** | **100** |
| New lands NL_j (%) | **40** | **100** | **100** | **100** |

The column assignment was rebuilt from the flattened table. It matches the IS_j and NL_j parameter tables on pp. 23–24 (75/100 and 40/100).

**Cross-commodity accounting** (used when any CP_j,t < 0) requires:

1. Use the cross-commodity default columns.
2. Show that introduced commodities are produced in-country and that national production is increasing, using the two most recent FAOSTAT time steps.
3. Apply the defaults across the whole project area, all commodities and all instances.

**Leakage-only accounting** may use alternative IS_j or NL_j values for displaced agricultural products. Less conservative values need evidence; more conservative values do not.

**Yield G_j,t:**

- For subsistence commodities, use the project-area yield during the historical reference period. Subsistence commodities must not be introduced as cross-commodity production.
- For fuelwood, IPCC AGB growth rates may be used if regional or national data are unavailable.
- For agricultural commodities, use data no coarser than national scale.

**Eq. (9)**, p. 14. [RECONSTRUCTED; V1.0-CONFIRMED = v1.0 Eq. (6), p. 9; v1.0 used y_j,t and IS without subscript]

Plain: `INL_j,t = (l_j,t × IS_j × NL_j) / G_j,t`

$$INL_{j,t} = \frac{l_{j,t} \times IS_j \times NL_j}{G_{j,t}}$$

| Symbol | Meaning | Unit |
|---|---|---|
| INL_j,t | Area of new land brought into production (+) or spared (−) for commodity j in year t | ha |
| IS_j | Proportion of leakage resulting in a change in supply outside the project area | % (fraction) |
| NL_j | Proportion of increased supply from new land brought into production | % (fraction) |
| G_j,t | Yield on new land brought into production or spared | units of production/ha |

**Eq. (10)**, p. 14. [RECONSTRUCTED; CHANGED vs v1.0 Eq. (7): v1.0 was AL_t = Σ_{j=1}^{T} INL_j,t with no MAX]

Plain: `AL_t = MAX( Σ_{j=1}^{J} INL_j,t , 0 )`

$$AL_t = \mathrm{MAX}\left(\sum_{j=1}^{J} INL_{j,t},\ 0\right)$$

| Symbol | Meaning | Unit |
|---|---|---|
| AL_t | Total area generating leakage emissions in year t | ha |
| J | Total number of commodities produced in the historical reference period | count |

#### Step 4: carbon stock change on new land (§5.4, pp. 14–16)

New land is assumed to be **forest** unless one of these is shown:

1. Forest is less than 10% of national land cover.
2. Forest is effectively protected or unlikely to be converted, with an annual gross deforestation rate **below 0.1% over the past 10 years** according to **Global Forest Watch**.

If either holds:

- (a) Identify the project ecoregion (Olson et al. 2001).
- (b) Assume that the ecoregion's land cover is what gets converted.
- (c) Estimate ΔC_biomass for all significant pools, plus ΔSOC.

If neither holds, assume forest and the complete loss of above- and belowground biomass, dead wood and litter.

**Eq. (11)**, p. 15. [TEXT-CLEAN; V1.0-CONFIRMED = v1.0 Eq. (8), p. 11; v1.0 wrote CS, v1.1 writes ΔCS]

Plain: `ΔCS = ΔC_biomass + ΔSOC`

$$\Delta CS = \Delta C_{biomass} + \Delta SOC$$

| Symbol | Meaning | Unit |
|---|---|---|
| ΔCS | Change in carbon stocks on new lands brought into production | t C/ha |
| ΔC_biomass | Average regional change in carbon stocks of forest or other eligible land cover in the project region | t C/ha |
| ΔSOC | Average regional change in SOC stocks in the project region | t C/ha |

**Eq. (12)**, p. 16. [RECONSTRUCTED; V1.0-CONFIRMED = v1.0 Eq. (9), p. 11]

Plain: `ΔSOC = SOC_REF × (1 − (f_LU × f_MG × f_IN))`

$$\Delta SOC = SOC_{REF} \times \left(1 - \left(f_{LU} \times f_{MG} \times f_{IN}\right)\right)$$

The v1.1 glyph stream shows "SOC_REF × ((1 − (f_LU × f_MG × f_IN))", which has an unbalanced extra "(". v1.0 is `SOC_REF × (1.00 − f_LU × f_MG × f_IN)`, which is the same mathematically.

The change is the difference between the initial reference stock and the steady-state stock after 20 years.

| Symbol | Meaning | Unit |
|---|---|---|
| SOC_REF | Reference SOC stock for the climate region and soil type of the region receiving the displaced activity | t C/ha |
| f_LU, f_MG, f_IN | Relative SOC stock change factors over 20 years for land use, management and inputs applicable to displaced production | dimensionless |

#### Step 5: leakage emissions (§5.5, p. 16)

**Eq. (13)**, p. 16. [RECONSTRUCTED; CHANGED vs v1.0 Eq. (10): v1.0 was LK_t = AL_t × CS × 44/12; **v1.1 adds + E_LM,t**]

Plain: `LK_t = (AL_t × ΔCS × 44/12) + E_LM,t`

$$LK_t = \left(AL_t \times \Delta CS \times \frac{44}{12}\right) + E_{LM,t}$$

| Symbol | Meaning | Unit |
|---|---|---|
| LK_t | Cumulative leakage up to year t | t CO2e |
| AL_t | Total area generating leakage emissions in year t | ha |
| ΔCS | Change in carbon stocks on new lands | t C/ha |
| E_LM,t | Total leakage mitigation emissions | t CO2e |
| 44/12 | Conversion from C to CO2 | — |

LK_t then enters VM0047 Eq. 32 (area-based only).

### 5.3 VMD0054 default values

| Item | Value | Ref |
|---|---|---|
| r_j, yield growth | **2.5%** default. Alternatives: regional data from the smallest administrative unit, disaggregated by ownership class; or FAOSTAT for crops, with r_j = (yield_j,t / yield_j,t−1) − 1. | 6.2, pp. 20–21; App. 1, p. 30 |
| IS_j | **75%** agricultural; **100%** fuelwood; **100%** for all cross-commodity columns | Table 1; pp. 12–13, 23 |
| NL_j | **40%** agricultural; **100%** fuelwood; **100%** for all cross-commodity columns | Table 1; pp. 12–13, 23–24 |
| H, K | 3 years, or one crop rotation, whichever is longer | 6.1, pp. 18–19 |
| Minimum leakage period | 5 years from start (grouped: 5 years after the last instance) | §5, p. 6 |
| Mitigation agreement | at least 5 years | p. 9 |
| Forest assumption exceptions | Forest < 10% of national cover; or gross deforestation < 0.1%/yr over 10 years (GFW) | §5.4, p. 15 |
| SOC horizon | 20 years | p. 16 |
| CF for ΔC_biomass | **0.47** | 6.2, pp. 26–27 |
| Belowground biomass when only AGB is available | IPCC GPG-LULUCF 2003 **Table 4.A.4** allometry | p. 26 |
| Dead wood + litter when only tree biomass is available | (AGB + BGB) × **1.1** (from AR-TOOL15 v2.0) | p. 26, fn. 6 |
| ΔC_biomass fallback | IPCC GPG-LULUCF 2003 **Table 3A.1.4** | p. 25 |
| SOC_REF | IPCC 2019 Refinement Vol. 4 Ch. 2 **Table 2.3** | p. 27 |
| f_LU, f_MG, f_IN | Crops (tree crops for fuelwood): IPCC 2019 Vol. 4 Ch. 5 **Table 5.5**. Grazing: Ch. 6 **Table 6.2**. | p. 28 |
| p_j,h fuelwood fallback | IPCC 2019 Vol. 4 Ch. 4 **Tables 4.9–4.11** (AGB growth) | p. 17 |
| EF_i | IPCC 2019 Vol. 2 Ch. 3, **upper bound** | p. 20 |

Appendix 1 background (pp. 30–31):

- 2.5% comes from IFPRI global growth of 2.08–2.42% "per decade" (as written; see A20) and FAO projections of 1.6% (2007–2030) and 0.9% (2030–2050).
- 75%: production losses lead to a 13–72% supply increase elsewhere.
- 40%: FAO projects 10% of growth globally from new land, up to 40% in Latin America and the Caribbean.

---

## 6. Monitoring parameters

### 6.1 VM0047 v1.1 §9.1: data and parameters available at validation (pp. 38–45)

These are fixed at validation, so no monitoring frequency applies.

| Parameter | Unit | Description | Equations | Source / value | Census-relevant? |
|---|---|---|---|---|---|
| A | ha | Project area | 3, 5, 7, 9, 11 | Calculated from GIS: GIS coverage, GPS survey, imagery, geo-registered. Project-specific. Each discrete area has a unique ID. | No (area-based) |
| R | dimensionless | Root-to-shoot ratio (belowground to aboveground biomass, per unit area or per stem) | 4, 25 | Hierarchy in §3 (ecoregion or life-zone, then global; IPCC 2019 Vol. 4 Ch. 4 Table 4.4). Project-specific. | **Yes** |
| CF | t C/t d.m. | Carbon fraction of dry biomass | 6, 8, 10, 13, 25 | 2006 IPCC Guidelines; **0.47** | **Yes** |
| COMF | dimensionless | Combustion factor | 12, 26 (as listed) | IPCC 2019 Vol. 4 Ch. 2 Table 2.6, by vegetation type; **census-based: 1.0** | **Yes** |
| EF_g | kg/t d.m. burned | Emission factor for gas g | 12, 26 (as listed) | 2006 IPCC, Table 2.2, Ch. 2, Vol. 2 (+ Appendix 2) [as written]. Project-specific. | **Yes** (if burning) |
| GWP_g | dimensionless | Global warming potential for gas g | 13, 16, 20, 21, 26 | Most recent IPCC assessment report | **Yes** |
| EF_Ndirect | t N2O-N/t N applied | EF for direct N2O from N additions | 16 | IPCC 2019 Vol. 4 Ch. 11 Table 11.1; **0.01** | **Yes** (if fertilized) |
| Frac_GASF | dimensionless | Fraction of synthetic N volatilized as NH3 and NOx | 20 | Table 11.3; **0.11** | **Yes** (if fertilized) |
| Frac_GASM | dimensionless | Fraction of organic N volatilized as NH3 and NOx | 20 | Table 11.3; **0.21** | **Yes** (if fertilized) |
| EF_Nvolat | t N2O-N/(t NH3-N + NOx-N volatilized) | EF for N2O from atmospheric deposition | 20 | Table 11.3; **0.01** | **Yes** (if fertilized) |
| Frac_LEACH | dimensionless | Fraction of N lost through leaching and runoff | 21 | Table 11.3; **0.24** | **Yes** (if fertilized) |
| EF_Nleach | t N2O-N/t N leached and runoff | EF for N2O from leaching and runoff | 21 | Table 11.3; **0.011** | **Yes** (if fertilized) |
| N | integer | Initial population size (number of planting units) | 24, 27, 30 | Complete census or enumeration. Record per unit: **(1) unique ID, (2) geo-referenced point, (3) year planted, (4) species**. Units must be clearly defined and identifiable in the field. | **Yes**, core |

### 6.2 VM0047 v1.1 §9.2: data and parameters monitored (pp. 45–61)

| Parameter | Unit | Description | Equations | Source / method | Frequency | Census-relevant? |
|---|---|---|---|---|---|---|
| C_WP-woody-AB,t | t C/ha | Average carbon stock in aboveground woody biomass in year t | 4, 13 | Plot-based field sampling, optionally with double or 3P sampling; published allometry; fixed size thresholds; SOPs | Every 5 years or more often | No (area-based) |
| DM_WP-herb,t | t d.m./ha | Average non-woody biomass in year t | 6 | Clip plots; min and max season samples, or a conservative minimum | Every 5 years or more often | No |
| B_SDW,t | t d.m./ha | Average biomass of standing dead wood in year t | 8 | Plot sampling; allometric volume; wood density + Harmon 2011 | Every 5 years or more often | No |
| B_LDW,t | t d.m./ha | Average biomass of lying dead wood in year t | 8 | Line intersect or perpendicular distance sampling; wood density + reduction factors | Every 5 years or more often | No |
| DM_WP-LI,t | t d.m./ha | Average litter dry mass in year t | 10 | Destructive frames, dried at 70 °C | At t = 0, then every 5 years or more often | No |
| C_WP-SOC,t | t C/ha | Average SOC stock in year t | 11 | Sampled to at least 30 cm with bulk density; ESM re-measurement | At t = 0, then each verification (≤ 5 years); ≤ 10 years under conditions | No |
| A_burn,t | ha | Area burned in the interval ending in year t | 13 | GIS, imagery or GPS | Every 5 years or more often | No |
| M_wp,SF,t; M_wp,OF,t | tonnes | Mass of N-containing synthetic and organic fertilizer applied in the interval | 17, 18 | Land management records; consultation plus written attestation from the land manager; documentary evidence (logs, receipts, invoices) | At least every 5 years, or before each verification | **Yes** (if fertilized) |
| NC_wp,SF,t | t N/t fertilizer | N content of synthetic fertilizer | 17 | Manufacturer's specifications, evidenced by records or invoices | At least every 5 years, or before each verification | **Yes** |
| NC_wp,OF,t | t N/t fertilizer | N content of organic fertilizer | 18 | Published or peer-reviewed data, preferably recent and in-country | At least every 5 years, or before each verification | **Yes** |
| n_t | integer | Number of planting units sampled in year t | 25, 27, 31 | Randomized sampling of the initial census. Record per sampled unit in the monitoring report: **unique ID, geo-referenced point, year planted, species**. | (Not stated; per monitoring event) | **Yes**, core |
| M_t | % | Mortality through year t | 24, 30, 31 | Complete re-enumeration **or** representative sampling from the census list (stratified systematic by annual cohort, random start suggested). Dead = no green cambium and no green leaves, **or** not relocatable. Calculated as a percentage of the sample or census. | Every 5 years or more often; may be combined with biomass sampling | **Yes**, core |
| B_WP-woody-AB,pu,t | t d.m. | Estimated aboveground woody biomass in sampled planting unit pu in year t | 25, 27 | Representative sample of the N units; optional double or 3P sampling and cohort stratification; published allometry (species > genus > family; ecoregion-specific, then global validated by destructive data); field-measured DBH, RCD or height; fixed size thresholds. **A live unit below the threshold counts as 0.** | Every 5 years or more often | **Yes**, core |
| n_burn,t | integer | Number of sampled planting units recorded as burned in the interval ending in year t | 27 | Field sampling; tally each **visibly burned and killed** unit among the representative sample | Every 5 years or more often | **Yes** (if burning) |
| SE_p,t | t CO2e | Standard error of the mean carbon stock estimate for pool p in year t | 28, 29 | SD of sample values ÷ √(number of plots, or **planting units** for census-based). For double sampling, the regression RMSE scaled to the sample size. Use unbiased estimators (Cochran 1977; App. 3). Census-based: **woody biomass only**. | Every 5 years or more often | **Yes** |

The QA/QC fields in 9.2 are "To be determined by the project proponent and outlined in standard operating procedures", or "See description", or (for fertilizer) "documented evidence: logs, receipts, invoices".

§9.3 (pp. 61–62) lists the monitoring plan contents:

- the approach used and the definition of a planting unit;
- the monitoring tasks;
- the accounting boundary and non-overlap;
- parameter tables for every measured allometric attribute (DBH, height and so on);
- sample design and estimators;
- frequency, QA/QC and archiving (at least 2 years after the last crediting period);
- roles and responsibilities;
- items 10–11, remote sensing and stocking index, which are area-based.

### 6.3 VMD0054 v1.1 parameters (for completeness; not used by census-based projects)

| Parameter | Unit | Section | Source / default | Frequency |
|---|---|---|---|---|
| p_j,h | unit of production | 6.1 | (1) grower records or remote sensing; (2) regional census averages; (3) national census averages; (4) fuelwood: IPCC 2019 Tables 4.9–4.11. Must cite the commodity or ownership class and be supported by a signed farmer or landowner attestation. | Every year of the reference period (validation) |
| H | years | 6.1 | 3 years, or one rotation if longer | Validation |
| K | years | 6.1 | 3 years, or one rotation if longer | Validation |
| op_j,k | unit of production | 6.1 | Grower records or remote sensing | Validation |
| EF_i | "dimensionless" | 6.1 | IPCC 2019 Vol. 2 Ch. 3 upper bound, or peer-reviewed country-specific values | Validation |
| r_j | % | 6.2 | Regional statistics or FAOSTAT; default 2.5% | Each monitoring event |
| OMP_j,t | units of production | 6.2 | Grower records or remote sensing | Each monitoring event |
| E_fert,t | t CO2e | 6.2 | VM0047 v1.1 Eqs. 15–21 | At monitoring event |
| IS_j | % | 6.2 | 75% agricultural / 100% fuelwood (Table 1) | Each monitoring event |
| NL_j | % | 6.2 | 40% agricultural / 100% fuelwood (Table 1) | Each monitoring event |
| G_j,t | units/ha | 6.2 | Government statistics or published studies, then FAOSTAT, then project-area historical yield (subsistence: project-area historical yield) | Each monitoring event |
| ΔC_biomass | t C/ha | 6.2 | Regional, then national, then IPCC GPG 2003 Table 3A.1.4; CF 0.47; BGB from Table 4.A.4; ×1.1 for dead wood and litter | Each monitoring event |
| SOC_REF | t C/ha | 6.2 | IPCC 2019 Vol. 4 Ch. 2 Table 2.3 | Each monitoring event |
| f_LU, f_MG, f_IN | dimensionless | 6.2 | IPCC 2019 Table 5.5 (crops) or Table 6.2 (grazing) | Each monitoring event |

Not tabulated in VMD0054 although used in its equations: MP_j,t, p_j,t, W, F_i,j and E_FF,t.

---

## 7. Ambiguities and issues (page references are to v1.1)

- **A1. Project start / t = 0 conflict (pp. 8, 10, 29).** §4.1(4) sets the start date as the earliest of site preparation or the land use change date. §4.3(4) says "the establishment of a complete census … marks the start of the project and is t = 0". §8.3.1 also allows measurement to begin after the start date. Recommended reading: treat the census date as t = 0 for stock accounting and record both dates.
- **A2. Density basis (p. 10).** The 50 units/ha limit applies "proportionally to the size of each instance", but the method of measuring instance area is not defined. It could be the parcel area or the union of the 10 m buffers. A 10 m buffer is about 0.0314 ha, so one isolated unit has a buffer-area density of about 32/ha. §4.3(5) caps N at "50 live planting units per hectare" when replanting, while N is defined as the *initial* census (9.1).
- **A3. Replanting versus N and M_t (pp. 10, 45, 57).** N is fixed at the t = 0 census, and M_t is mortality "through year t" against that N. How replacement plantings enter the calculation is not specified: as new units with new IDs, as reset units, or as a separate cohort. The stratification text ("annual cohorts") suggests cohorts can be added later, which conflicts with a fixed N.
- **A4. R hierarchy for census-based projects (pp. 38–39) versus the allometry hierarchy (p. 59).** The allometry table for B_WP-woody-AB,pu,t allows only species, genus or family equations. The R table still includes the forest-type branch, for facilitated natural regeneration or more than two species per stand. Census-based projects are direct planting only, but mixed plantings could trigger the forest-type R. R is "dimensionless" in 9.1 and "t root d.m./t shoot d.m." in Eq. 25.
- **A5. Dead sampled units in Eq. 25 (pp. 30, 60).** Eq. 25 averages over the n_t *sampled* units, and Eq. 24 then multiplies by (1 − M_t). If dead sampled units enter Eq. 25 as zeros, mortality is counted twice. The 9.2 comment (live units below the threshold count as 0) suggests that Eq. 25 should average **live** sampled units only, but this is never stated explicitly.
- **A6. Eq. 27 summation and units (p. 32).** The sum runs from pu = 1 to **n_t**, but it is divided by n_{t−x} and sums biomass at t − x. The upper limit should logically be n_{t−x}. v1.0 Eq. 19 has the same issue. The unit is given as "t d.m./ha" in Eq. 27's where-list but "t d.m." in Eq. 26's. Dimensionally it is t d.m., a project total. The burned fraction is also applied to the initial N rather than to N × (1 − M).
- **A7. Eq. 29 (p. 33), census uncertainty. This is the highest-risk item; verify against the official PDF.**
  - (a) The reconstruction comes from garbled glyphs. No v1.1 page image was available.
  - (b) C_total,t is said to be "calculated using Equation (29)"; it should be Eq. 30.
  - (c) SE_p,t is defined as the SE of "average woody biomass **per planting unit**", but it is added in quadrature to C_total,t × U_M,t/100, which is a **project total**, and the sum is divided by C_total,t. Without scaling SE by N × (1 − M_t), the biomass error term becomes negligible.
  - (d) T is applied in Eq. 29 and again inside U_M,t in Eq. 31, so it may be applied twice.
  - (e) U_M,t is defined as "%", but Eq. 31 gives a fraction. Eq. 29 divides by 100, which implies U_M,t should be ×100.
  - (f) The degrees of freedom for T are not stated (n_t − 1 is the natural choice).
  - (g) Units are mixed: C_WP-woody (t C) versus SE and C̄_pu (t CO2e).
  - v1.0 Eq. 28, √(U_p,t² + U_M,t²) − 10%, avoided (c)–(e).
- **A8. Complete re-enumeration of mortality (p. 57).** M_t may be found by "complete re-enumeration". Eq. 31 still gives non-zero U_M,t from n_t, and VM0047 does not say whether to set U_M,t = 0 or use n_t = N.
- **A9. UNC_t scaling (pp. 33, 35).** Eqs. 28 and 29 return UNC_t × 100 (percent), but Eqs. 32 and 33 use (1 − UNC_t). Convert to a fraction.
- **A10. PE_t timing (pp. 34–35).** In Eq. 33, PE_t is subtracted once ("in year t" or "in the monitoring interval ending in year t"). In area-based Eq. 32, both PE_t and PE_{t−x} appear, which implies PE is cumulative. This affects how PE should be stored, as interval or cumulative values. Eq. 12 is in the area-based section, but census emissions rely on it.
- **A11. Eq. 22 "first year of measurement replaces t = 0" (p. 29).** Census stock change is ΔC = C_t with no subtraction of t = 0 (Eq. 23). How the substitution works in Eq. 33 is unclear; presumably ΔC_WP,t−x = 0 for the first verification.
- **A12. §6.2 versus §4.3(8) (pp. 11, 16).** §4.3(8) joins its conditions with "and/or". §6.2 requires (1) < 10% cover **and** (2) continuous cropping, settlements or other lands for the zero baseline to apply.
- **A13. EF_g source (p. 41).** It cites "Table 2.2 in Chapter 2, Volume 2 of the 2006 IPCC Guidelines". In the 2006 Guidelines, Vol. 2 Ch. 2 covers stationary combustion; biomass-burning EFs are in **Vol. 4 Ch. 2 (Table 2.5)**. This looks like a referencing error. Confirm before hard-coding.
- **A14. GWP "most recent IPCC assessment report" (p. 41).** VCS program rules may fix a specific AR. This is a policy decision outside the methodology.
- **A15. Buffer base (VCS Standard §3.14.15; NPRT §2.5.4).** It is unclear whether the buffer applies to ΔC before or after the uncertainty deduction. "Change in carbon stocks only" excludes PE. VM0047 is silent on this.
- **A16. Leakage for census-based projects versus VMD0054 §1 and §4.** VMD0054 §1 says VM0047 projects "must use this module", and its §4 allows de minimis only if there was no agriculture in the past 10 years. Census-based projects are often on farmland. VM0047 §8.4 explicitly sets LK_t = 0 for census-based projects. As the governing methodology, VM0047 controls, so **leakage is zero for census-based projects.** Record the conditions (land use maintained, ≤ 50/ha) as evidence.
- **A17. VMD0054 Eq. 2 (p. 8).** The summation index t runs from 1 to t, reusing the outer t, and is divided by W (the current monitoring period). The intended reading is the average annual production over the years of the current monitoring period. The text calls MP_j,t the "average annual production observed in the project area in year t", which is internally inconsistent.
- **A18. VMD0054 Eq. 7 (p. 11).** The sum runs from t = 0 although t is defined as 1, 2, 3, …. E_LM,t is called both "in year t" and "cumulative … through time t". Eq. 13 treats LK_t as cumulative, so E_LM,t should be cumulative.
- **A19. VMD0054 Eq. 8 units (pp. 11–12, 20).** EF_i is listed as "dimensionless" while F_i,j is in volume units. EF_i must in fact be t CO2e per volume unit.
- **A20. VMD0054 r_j (p. 20; App. 1, p. 30).** It is given in percent but used as (1 + r_j)^t, so a fraction is needed. Appendix 1 describes IFPRI growth as "less than 2.5% per decade" and then uses 2.5% as an **annual** default. The wording is inconsistent, but the default is conservative.
- **A21. VMD0054 data-source hierarchies differ (pp. 7 and 17).** §5.1.2 lists (1) grower records, (2) remote sensing, (3) national or sub-national census, (4) IPCC for fuelwood. The p_j,h table merges records and remote sensing as item 1 and splits regional and national averages into separate items.
- **A22. VMD0054 RC_Es / Appendix 2 cross-reference (VM0047 p. 77).** The definition of RC_Es mentions "project and leakage GHG emissions", while the note excludes leakage.
- **A23. Wood density (VM0047, whole document).** There is no source hierarchy for wood density in live-tree allometry (e.g., Chave-type equations that need ρ). Wood density appears only for dead wood (pp. 50–51). Recommendation: apply the same species > genus > family preference by analogy, and document it in the PD.
- **A24. The 9.1 "Equations" field for COMF and EF_g lists (12) and (26).** The equations that actually use them are Eq. 13 (area) and Eq. 26 (census). The list should read (13) and (26). This is a minor editorial point.
- **A25. Version currency.** VMD0054 v1.1 (13 Jan 2026) says E_fert,t uses "Equations (15)–(21) in VM0047, v1.1 or equivalent equations in more recent version". VM0047 v1.1 is the version used here. Check for later VM0047 issues and errata before deployment.
