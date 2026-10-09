# VM0047 ARR v1.1 (14 May 2025): extract for the AREA-BASED approach

**Primary source:** Verra VM0047 *Afforestation, Reforestation, and Revegetation*, v1.1, 14 May 2025 (81 pp.). Text used: `methodology-docs/_text/VM0047_ARR_v1.1.md`, which was converted from the PDF, so the equation glyphs are garbled. The v1.1 PDF itself is not on disk. A download attempt from verra.org was blocked by Cloudflare.
**Cross-check source:** VM0047 v1.0, 28 Sep 2023 (68 pp.), `VM0047-ARR/VM0047_ARR_v1.0.pdf`. Pages 16–18, 20–23, 25–29 and 58–61 were rendered to PNG and read visually.

**Page references.** "p.N" means the printed page number of **v1.1**. "v1.0 p.N" means the printed page of v1.0. The v1.1 page numbers come from the page markers in the converted text.

**How each equation was verified.** Every equation below carries one of these tags:
- **[v1.0-CONFIRMED]**: the garbled v1.1 glyphs read as the same symbols and operators as the equation rendered from the v1.0 PDF. The form is taken from v1.0, and v1.1 shows it is unchanged apart from renumbering and changes in subscript or wording, which are noted.
- **[v1.1-RECONSTRUCTED]**: the equation is new or changed in v1.1, so there is no v1.0 image to check against. The form was rebuilt token by token from the garbled v1.1 text, which arrives in a mostly reversed, right-to-left glyph order. Verify these against the official v1.1 PDF before production use.
- **[UNREADABLE]**: none. Every in-scope equation could be read, though some readings are reconstructed as described above.

---

## 1. Structure and decision points (what an area-based project must do, in order)

1. **Choose the approach at the start date (§4, §4.1(3), p.8).** The area-based and census-based approaches are mutually exclusive for each instance. The choice is fixed for the whole crediting period. If both are used, they must sit in non-overlapping areas separated by a buffer of at least 10 m (§4, p.8).
2. **Check general applicability (§4.1, p.8).**
   - Project activities increase vegetative cover.
   - The start date is the **earliest** of (a) the date site preparation began and (b) the land use change date.
   - On organic soils or wetlands, the project must use a multiple-project-activity design: VM0047 covers aboveground biomass, and a Wetland Restoration and Conservation (WRC) methodology such as VM0036 covers the other pools.
3. **Check area-based applicability (§4.2, pp.9–10).**
   - Activities may be direct planting, seeding, assisted natural regeneration (ANR), or a combination.
   - **A t = 0 carbon stock estimate is required for every significant pool**, using one of two paths:
     - **(a) Start date triggered by site preparation:** measure t = 0 *before* site preparation, and no more than **2 years before** the start date. If no plots were established before site preparation, a **remote-sensing estimate is allowed only for pre-existing woody biomass** (§8.2.1.2). If any other significant pool was disturbed without a t = 0 measurement (for example, ploughing deeper than 25 cm or removing dead wood offsite), the project is **ineligible**.
     - **(b) Start date is a land use change date, or site preparation caused no significant stock decrease:** t = 0 plots may be established up to **2 years after** the start date. Plot sampling must cover all significant pools, and the project must provide evidence that site preparation involved no clearing, burning or mechanical disturbance (photos, field data, imagery, attestations).
   - Leakage must be quantified with **VMD0054** and must not be assumed de minimis.
4. **Check exclusions (§4.4.1, p.12).** The area-based approach is not applicable if any of the following holds:
   - The land met the definition of managed forest at any point in the **10 years** before the start date.
   - Clearing of pre-existing woody biomass involved timber harvesting or degraded native ecosystems.
   - The project plants **fewer than 50 planting units/ha and could use the census-based approach**.
   - Note also VCS Standard v4.7 §3.19.29(2) on land degraded within 10 years of the start date (footnote 8, p.12).
5. **Delineate the project area A with GIS and set the pools (§5.1 Table 1, pp.13–14) and GHG sources (§5.3 Table 3, p.15).** Run the **Appendix 2** significance test (Eq. A9, A10) to decide which optional pools and sources may be treated as de minimis.
6. **Demonstrate additionality (§7.1, §7.3, pp.16–17):**
   - Regulatory surplus.
   - Performance benchmark: Appendix 1 Z test, Eq. A7. An ex-ante version is required at validation, and the test is re-run at **every verification**.
   - Investment analysis per VT0008 Step 3. This is not required where the project has no revenue or incentives other than carbon credits (footnote 10).
7. **Set up the performance benchmark (Appendix 1, pp.66–76) for each project area, or for each annual cohort of a grouped project:**
   - Step 1: select project plots (n ≥ 30).
   - Step 2: delineate the donor pool and match control plots (k-NN on stocking index (SI) covariates; Eq. A1).
   - Step 3: check match quality (SDM ≤ 0.25; Eq. A2).
   - Steps 4–6 at every monitoring event: monitor SI, compute weighted slopes (Eq. A3–A6), run the Z test (Eq. A7), and compute PB_t (Eq. A8).
8. **Ex-ante estimate at validation (§8.7, pp.36–37).** Use a growth-and-yield model plus Eq. (1), apply a minimum 10% uncertainty deduction, and forecast the performance benchmark.
9. **Monitor and measure field plots at t = 0, then at least every 5 years (§9.2).** Compute the pool stock changes with Eq. (3)–(11) and total them with Eq. (2) and (1).
10. **Compute project emissions** from biomass burning (Eq. 13–14) and N fertiliser (Eq. 15–21), totalled with Eq. (12).
11. **Compute leakage LK_t** with VMD0054 (§8.4, p.32).
12. **Compute uncertainty UNC_t** with Eq. (28), or with Appendix 3 (Eq. A11–A16) if the sampling design changed. If the half-width of the 90% confidence interval exceeds 100% of the removal estimate, then **CR_t = 0** (p.34).
13. **Compute CR_t** with Eq. (32) and annualise with Eq. (34). If the project harvests, the long-term average (LTA) cap from the VCS Standard applies (p.35).
14. **Buffer and VCUs are set outside VM0047**, by the VCS Standard and the AFOLU Non-Permanence Risk Tool. See §5 below.

---

## 2. Equations in scope

General index: t = 1, 2, 3, …, t years elapsed since the project start date. x is the length of the monitoring period or interval in years.

### Eq. (1): project carbon stock change (§8.2.1, p.19) [v1.0-CONFIRMED, v1.0 Eq. 1, p.16]
Plain text: `ΔC_WP,t = (ΔC_WP-biomass,t + ΔC_WP-SOC,t) × 44/12`
LaTeX: `\Delta C_{WP,t} = (\Delta C_{WP\text{-}biomass,t} + \Delta C_{WP\text{-}SOC,t}) \times \frac{44}{12}`

| Symbol | Definition (as printed in v1.1) | Unit |
|---|---|---|
| ΔC_WP,t | Project carbon stock change through year t | t CO2e |
| ΔC_WP-biomass,t | Change in carbon stock in biomass carbon pools in the project scenario through year t | t C |
| ΔC_WP-SOC,t | Change in soil organic carbon stock in the project scenario through year t | t C |
| 44/12 | Ratio of molecular weight of carbon dioxide to carbon | unitless |

The v1.1 wording is "through year t". v1.0 said "in year t".

### Eq. (2): biomass pools (§8.2.1, p.20) [v1.0-CONFIRMED, v1.0 Eq. 2, p.17]
`ΔC_WP-biomass,t = ΔC_WP-woody,t + ΔC_WP-herb,t + ΔC_WP-DW,t + ΔC_WP-LI,t`
`\Delta C_{WP\text{-}biomass,t} = \Delta C_{WP\text{-}woody,t} + \Delta C_{WP\text{-}herb,t} + \Delta C_{WP\text{-}DW,t} + \Delta C_{WP\text{-}LI,t}`

| Symbol | Definition | Unit |
|---|---|---|
| ΔC_WP-woody,t | Change in carbon stock in woody biomass in the project scenario through year t | t C |
| ΔC_WP-herb,t | Change in carbon stock in non-woody biomass in the project scenario through year t | t C |
| ΔC_WP-DW,t | Change in carbon stock in dead wood in the project scenario through year t | t C |
| ΔC_WP-LI,t | Change in carbon stock in litter in the project scenario through year t | t C |

### Eq. (3): woody biomass stock change (§8.2.1.1, p.20) [v1.0-CONFIRMED, v1.0 Eq. 3, p.17]
`ΔC_WP-woody,t = A × (C_WP-woody,t − C_WP-woody,t=0)`
`\Delta C_{WP\text{-}woody,t} = A \times (C_{WP\text{-}woody,t} - C_{WP\text{-}woody,t=0})`

| Symbol | Definition | Unit |
|---|---|---|
| ΔC_WP-woody,t | Change in carbon stock in woody biomass in the project scenario through year t | t C |
| A | Project area | ha |
| C_WP-woody,t | Average carbon stock in woody biomass in the project scenario in year t | t C/ha |

This is the stock-difference method (Bird et al. 2010).

### Eq. (4): root expansion (§8.2.1.1, pp.20–21) [v1.0-CONFIRMED, v1.0 Eq. 4, p.18]
`C_WP-woody,t = C_WP-woody-AB,t × (1 + R)`
`C_{WP\text{-}woody,t} = C_{WP\text{-}woody\text{-}AB,t} \times (1 + R)`

| Symbol | Definition | Unit |
|---|---|---|
| C_WP-woody,t | Average carbon stock in woody biomass in the project scenario in year t | t C/ha |
| C_WP-woody-AB,t | Average carbon stock in aboveground woody biomass in the project scenario in year t | t C/ha |
| R | Root to shoot ratio | t root d.m./t shoot d.m. (the §9.1 table says "dimensionless") |

The methodology contains **no equation** that converts per-tree allometric biomass into C_WP-woody-AB,t. The §9.2 parameter table (pp.45–47) says only that it is "Calculated as the average of sample measurements", with per-plant aboveground biomass from published allometry. Applying CF to get carbon is implied but is not written as an equation for the area-based approach. See §6 (Ambiguities).

### Eq. (5) and (6): non-woody biomass (§8.2.1.3, p.22) [v1.0-CONFIRMED, v1.0 Eq. 8 and 9, p.20]
`ΔC_WP-herb,t = A × (C_WP-herb,t − C_WP-herb,t=0)` (5)
`C_WP-herb,t = DM_WP-herb,t × CF` (6)
`\Delta C_{WP\text{-}herb,t} = A \times (C_{WP\text{-}herb,t} - C_{WP\text{-}herb,t=0})`;  `C_{WP\text{-}herb,t} = DM_{WP\text{-}herb,t} \times CF`

| Symbol | Definition | Unit |
|---|---|---|
| ΔC_WP-herb,t | Change in carbon stock in non-woody biomass in the project scenario through year t | t C |
| A | Area | ha |
| C_WP-herb,t | Average carbon stock in non-woody biomass in the project scenario in year t | t C/ha |
| DM_WP-herb,t | Average non-woody biomass in the project scenario in year t | t d.m./ha |
| CF | Carbon fraction of dry biomass | t C/t d.m. |

### Eq. (7) and (8): dead wood (§8.2.1.4, p.23) [v1.0-CONFIRMED, v1.0 Eq. 10 and 11, pp.20–21]
`ΔC_WP-DW,t = A × (C_WP-DW,t − C_WP-DW,t=0)` (7)
`C_WP-DW,t = (B_SDW,t + B_LDW,t) × CF` (8)
`\Delta C_{WP\text{-}DW,t} = A \times (C_{WP\text{-}DW,t} - C_{WP\text{-}DW,t=0})`;  `C_{WP\text{-}DW,t} = (B_{SDW,t} + B_{LDW,t}) \times CF`

| Symbol | Definition | Unit |
|---|---|---|
| ΔC_WP-DW,t | Change in carbon stock in dead wood in the project scenario through year t | t C |
| C_WP-DW,t | Average carbon stock in dead wood in the project scenario in year t | t C/ha |
| B_SDW,t | Average biomass of standing dead wood in year t | t d.m./ha |
| B_LDW,t | Average biomass of lying dead wood in year t | t d.m./ha |
| CF | Carbon fraction of dry biomass | t C/t d.m. |

Standing dead wood means "fully dead (i.e., absence of green leaves and green cambium)". The dead-wood t = 0 measurement must be made **before any disturbance and no more than 2 years before the start date** (p.22).

### Eq. (9) and (10): litter (§8.2.1.5, pp.23–24) [v1.0-CONFIRMED, v1.0 Eq. 12 and 13, p.21]
`ΔC_WP-LI,t = A × (C_WP-LI,t − C_WP-LI,t=0)` (9)
`C_WP-LI,t = DM_WP-LI,t × CF` (10)

| Symbol | Definition | Unit |
|---|---|---|
| ΔC_WP-LI,t | Change in carbon stock in litter in the project scenario through year t | t C |
| C_WP-LI,t | Average carbon stock in litter in the project scenario in year t | t C/ha |
| DM_WP-LI,t | Average litter dry mass per hectare in the project scenario in year t | t d.m./ha |
| CF | Carbon fraction of dry biomass | t C/t d.m. |

### Eq. (11): SOC (§8.2.1.6, p.24) [v1.0-CONFIRMED, v1.0 Eq. 14, p.22]
`ΔC_WP-SOC,t = A × (C_WP-SOC,t − C_WP-SOC,t=0)`

| Symbol | Definition | Unit |
|---|---|---|
| ΔC_WP-SOC,t | Change in carbon SOC stock in the project scenario through year t | t C |
| C_WP-SOC,t | Average SOC stock in the project scenario in year t | t C/ha |

### Eq. (12): total project emissions (§8.2.2, p.24) [v1.0-CONFIRMED, v1.0 Eq. 15, p.22]
`PE_t = PE_bburn,t + PE_fert,t`

| Symbol | Definition | Unit |
|---|---|---|
| PE_t | Project emission from biomass burning and fertilizer use in the monitoring interval ending in year t | tCO2e |
| PE_bburn,t | Project emissions due to biomass burning in the monitoring interval ending in year t | t CO2e |
| PE_fert,t | Project emissions from nitrogen fertilizer in the monitoring interval ending in year t | t CO2e |

v1.1 changed "in year t" to "in the monitoring interval ending in year t".

### Eq. (13): biomass burning (§8.2.2.1, p.25) [v1.0-CONFIRMED, v1.0 Eq. 16, p.22]
`PE_bburn,t = A_burn,t × Σ_{g=1..G} (GWP_g × EF_g × B_WP,t × COMF × 10^-3)`
`PE_{bburn,t} = A_{burn,t} \times \sum_{g=1}^{G} \left( GWP_g \times EF_g \times B_{WP,t} \times COMF \times 10^{-3} \right)`

| Symbol | Definition | Unit |
|---|---|---|
| A_burn,t | Area burned in the monitoring interval ending in year t | ha |
| GWP_g | Global warming potential for gas g | dimensionless |
| EF_g | Emission factor for gas g | kg gas/t d.m. burned |
| B_WP,t | Average aboveground biomass stock subject to burning in the project scenario in the monitoring interval ending in year t | t d.m./ha |
| COMF | Combustion factor | dimensionless |
| g | 1, …, G greenhouse gases (methane and nitrous oxide) | dimensionless |
| 10^-3 | Conversion of kilograms to tonnes | – |

v1.0 described 10^-3 as "Conversion of kg CO2e to tCO2e".

### Eq. (14): biomass subject to burning (§8.2.2.1, p.25) [v1.0-CONFIRMED, v1.0 Eq. 17, p.23]
`B_WP,t = (C_WP-woody-AB,t−x + C_WP-herb,t−x + C_WP-DW,t−x + C_WP-LI,t−x) × (1/CF)`
`B_{WP,t} = (C_{WP\text{-}woody\text{-}AB,t-x} + C_{WP\text{-}herb,t-x} + C_{WP\text{-}DW,t-x} + C_{WP\text{-}LI,t-x}) \times (1/CF)`

| Symbol | Definition | Unit |
|---|---|---|
| C_WP-woody-AB,t−x | Average carbon stock in aboveground woody biomass in the project scenario in year t − x | t C/ha |
| C_WP-herb,t−x | Average carbon stock in non-woody biomass in year t − x | t C/ha |
| C_WP-DW,t−x | Average carbon stock in dead wood in year t − x | t C/ha |
| C_WP-LI,t−x | Average carbon stock in litter in year t − x | t C/ha |
| CF | Carbon fraction of dry biomass | t C/t d.m. |
| x | Length of monitoring period | years |

The only difference from v1.0 is that v1.0 wrote Δt where v1.1 writes x.

### Eq. (15): fertiliser total (§8.2.2.2, p.25) [v1.0-CONFIRMED, v1.0 Eq. 20, p.24]
`PE_fert,t = PE_Ndirect,t + PE_Nindirect,t`

| Symbol | Definition | Unit |
|---|---|---|
| PE_Ndirect,t | Direct nitrous oxide emissions due to fertilizer use in the project scenario in the monitoring interval ending in year t | t CO2e |
| PE_Nindirect,t | Indirect nitrous oxide emissions due to fertilizer use … in the monitoring interval ending in year t | t CO2e |

### Eq. (16): direct N2O (p.26) [v1.0-CONFIRMED, v1.0 Eq. 21, p.25]
`PE_Ndirect,t = (F_wp,SN,t + F_wp,ON,t) × EF_Ndirect × 44/28 × GWP_g`
`PE_{Ndirect,t} = (F_{wp,SN,t} + F_{wp,ON,t}) \times EF_{Ndirect} \times \frac{44}{28} \times GWP_g`

| Symbol | Definition | Unit |
|---|---|---|
| F_wp,SN,t | Synthetic nitrogen fertilizer applied in the project scenario in the monitoring interval ending in year t | t N |
| F_wp,ON,t | Organic nitrogen fertilizer applied … | t N |
| EF_Ndirect | Emission factor for direct N2O emissions from N additions due to synthetic fertilizers, organic amendments, and crop residues | t N2O-N/t N applied |
| GWP_g | GWP for gas g (here N2O) | dimensionless |
| 44/28 | Ratio of molecular weight of nitrous oxide to nitrogen | unitless |

### Eq. (17) and (18): N applied (p.26) [v1.0-CONFIRMED, v1.0 Eq. 22 and 23, p.25]
`F_wp,SN,t = M_wp,SF,t × NC_wp,SF,t` (17)
`F_wp,ON,t = M_wp,OF,t × NC_wp,OF,t` (18)

| Symbol | Definition | Unit |
|---|---|---|
| M_wp,SF,t / M_wp,OF,t | Mass of N-containing synthetic / organic fertilizer applied in the project scenario in the monitoring interval ending in year t | t (tonnes) |
| NC_wp,SF,t / NC_wp,OF,t | Nitrogen content of synthetic / organic fertilizer applied | t N/t fertilizer |

### Eq. (19): indirect N2O (p.27) [v1.0-CONFIRMED, v1.0 Eq. 24, p.25]
`PE_Nindirect,t = Nfert_wp,volat,t + Nfert_wp,leach,t`

### Eq. (20): volatilisation (p.27) [v1.0-CONFIRMED, v1.0 Eq. 25, p.26]
`Nfert_wp,volat,t = [(F_wp,SN,t × Frac_GASF) + (F_wp,ON,t × Frac_GASM)] × EF_Nvolat × 44/28 × GWP_g`
`Nfert_{wp,volat,t} = \left[ (F_{wp,SN,t} \times Frac_{GASF}) + (F_{wp,ON,t} \times Frac_{GASM}) \right] \times EF_{Nvolat} \times \frac{44}{28} \times GWP_g`

| Symbol | Definition | Unit |
|---|---|---|
| Nfert_wp,volat,t | Indirect N2O from atmospheric deposition of N volatilized due to N fertilizer use … in the monitoring interval ending in year t | t CO2e |
| Frac_GASF | Fraction of all synthetic N added to soils that volatilizes as NH3 and NOx | dimensionless |
| Frac_GASM | Fraction of all organic N added to soils that volatilizes as NH3 and NOx | dimensionless |
| EF_Nvolat | EF for N2O from atmospheric deposition of N on soils and water surfaces | t N2O-N/(t NH3-N + NOx-N volatilized) |

### Eq. (21): leaching (p.28) [v1.0-CONFIRMED, v1.0 Eq. 26, p.26]
`Nfert_wp,leach,t = (F_wp,SN,t + F_wp,ON,t) × Frac_LEACH × EF_Nleach × 44/28 × GWP_g`

| Symbol | Definition | Unit |
|---|---|---|
| Nfert_wp,leach,t | Indirect N2O from leaching and runoff of N, in regions where leaching and runoff occurs … | t CO2e |
| Frac_LEACH | Fraction of synthetic or organic N added to soils that is lost through leaching and runoff, in regions where leaching and runoff occurs | dimensionless |
| EF_Nleach | EF for N2O from leaching and runoff | t N2O-N/t N leached and runoff |

**Eq. (22)–(27), (29)–(31) and (33) are census-based and out of scope.**

### Eq. (28): area-based uncertainty (§8.5.1, p.33) [v1.1-RECONSTRUCTED; CHANGED from v1.0 Eq. 27]
Plain text:
`UNC_t = MIN(100%, MAX(0, (T × √(SE²_p,t=0 + SE²_p,t − (2 × ρ × SE_p,t=0 × SE_p,t)) / ΔC) − 0.10) × 100)`
LaTeX:
`UNC_t = \min\left(100\%,\ \max\left(0,\ \frac{T \times \sqrt{SE_{p,t=0}^2 + SE_{p,t}^2 - 2\rho\, SE_{p,t=0}\, SE_{p,t}}}{\Delta C} - 0.10\right) \times 100\right)`

| Symbol | Definition (v1.1) | Unit |
|---|---|---|
| UNC_t | Uncertainty in cumulative removals through year t | % |
| T | Critical value of a student's two-tailed t-distribution for significance level α = 0.1 | – |
| SE_p,t=0 | Standard error of the mean carbon stock estimate at time t = 0 | t CO2e |
| SE_p,t | Standard error of the mean carbon stock estimate at time t | t CO2e |
| ρ | Correlation coefficient (rho) between carbon stocks at t = 0 and t. Used only for permanent plots; the term is set to zero for independent measurements between t = 0 and t | – |
| ΔC | Mean change in carbon stocks between t = 0 and t | t CO2e |

How the reading was established: the parenthesis structure follows the garbled glyph order and matches the cleaner Appendix 3 Eq. (A16), `MIN(100%, MAX(0, (T×SE_ΔC/ΔC) − 0.10) × 100)`. ΔC sits in the denominator because it appears on a separate line below the radical.

**Difference from v1.0, which is substantial.** v1.0 Eq. (27), p.27, read `UNC_t = MIN(100%, MAX(0, (Σ_p(U_p,t=0 × C_p,t=0)² + Σ_p(U_p,t × C_p,t)²)^½ × (1/(ΔC_WP-biomass,t + ΔC_WP-SOC,t)) − 10%))`. It used per-pool percentage uncertainties U_p with an explicit sum over pools. v1.1 replaced this with an SE-based form that has a correlation term and **no explicit sum over pools p**.

### Eq. (32): area-based CR_t (§8.6.1, p.35) [v1.1-RECONSTRUCTED; CHANGED from v1.0 Eq. 30]
Plain text:
`CR_t = (MIN(ΔC_WP,t, ΔC_WP,t × (1 − PB_t)) × (1 − UNC_t)) − PE_t − LK_t − ((MIN(ΔC_WP,t−x, ΔC_WP,t−x × (1 − PB_t−x)) × (1 − UNC_t−x)) − PE_t−x − LK_t−x)`
LaTeX:
`CR_t = \left[\min\left(\Delta C_{WP,t},\ \Delta C_{WP,t}(1-PB_t)\right)(1-UNC_t) - PE_t - LK_t\right] - \left[\min\left(\Delta C_{WP,t-x},\ \Delta C_{WP,t-x}(1-PB_{t-x})\right)(1-UNC_{t-x}) - PE_{t-x} - LK_{t-x}\right]`

| Symbol | Definition (v1.1) | Unit |
|---|---|---|
| CR_t | Carbon dioxide removals from the project activity in the monitoring interval ending in year t | t CO2e |
| ΔC_WP,t | Project carbon stock change through year t | t CO2e |
| PB_t | Performance benchmark for the monitoring interval ending in year t | % (Eq. A8 calls it dimensionless) |
| LK_t | Leakage through year t | t CO2e |
| PE_t | Project emissions from biomass burning and fertilizer use in year t | t CO2e |
| UNC_t | Uncertainty in cumulative removals through year t | % |

**Difference from v1.0.** v1.0 Eq. (30), p.29, was `CR_t = ((ΔC_WP,t × (1−PB_t) × (1−UNC_t)) − LK_t) − PE_t − ((ΔC_WP,t−1 × (1−PB_t−1) × (1−UNC_t−1)) − PE_t−1 − LK_t−1)`. v1.1 makes two changes:
- It adds the **MIN(ΔC, ΔC × (1−PB))** wrapper. The effect is that when ΔC_WP,t < 0, the benchmark discount is not applied to the loss.
- It replaces t−1 with **t−x**, the length of the monitoring interval.

### Eq. (34): annualised removals (§8.6.3, p.36) [v1.1-RECONSTRUCTED; new equation, though v1.0 p.29–30 described the same rule in prose]
`CR_annualized = CR_t / x`

| Symbol | Definition | Unit |
|---|---|---|
| CR_annualized | Annualized carbon dioxide removals | t CO2e/year |
| CR_t | Carbon dioxide removals from the project activity over monitoring interval t | t CO2e |
| x | Length of the monitoring period | years |

### Appendix 1: performance method

#### Eq. (A1): control-plot weights (Step 2(3), p.69) [v1.0-CONFIRMED, v1.0 A1, p.58]
`W_control,i,j = e^(−MD_i,j) / Σ_{j=1..n_i,j} e^(−MD_i,j)`
`W_{control,i,j} = \frac{e^{-MD_{i,j}}}{\sum_{j=1}^{n_{i,j}} e^{-MD_{i,j}}}`

| Symbol | Definition | Unit |
|---|---|---|
| W_control,i,j | Weight of control plot j matched to project plot i | 0–1, dimensionless |
| MD_i,j | Multivariate distance of control plot j relative to project plot i | dimensionless |
| n_i,j | Number of control plots matched to project plot i (equal to k at project start date) | – |

#### Eq. (A2): standardized difference of means (Step 3, p.70) [v1.0-CONFIRMED in form, v1.0 A2, p.59; definitions changed]
`SDM = |v̄_wp,u − v̄_bsl,u| / √((σ²_wp,v + σ²_bsl,v) / 2)`
`SDM = \frac{\left|\bar{v}_{wp,u} - \bar{v}_{bsl,u}\right|}{\sqrt{(\sigma_{wp,v}^2 + \sigma_{bsl,v}^2)/2}}`

| Symbol | Definition (v1.1) | Unit |
|---|---|---|
| SDM | Standardized difference of means | – |
| v̄_wp,u | Mean value of covariate u in the population of project plots | SI units |
| v̄_bsl,u | Mean value of weighted sums of covariate u in the population of matched sets of control plots | SI units |
| σ²_wp,v | Sample variance of covariate v in the population of project plots | – |
| σ²_bsl,v | **Weighted** sample variance of covariate v in the population of control plots | – |

Changes from v1.0: v1.0 used x as the covariate symbol and ABS(); v1.1 uses u and v. v1.0 defined σ² as "Standard deviation", while v1.1 says "Sample variance" and "Weighted sample variance".
Threshold: the match is valid if **SDM ≤ 0.25 for every covariate**.

#### Eq. (A3) and (A4): time-series weights (Step 5, p.71) [v1.0-CONFIRMED, v1.0 A3 and A4, p.60]
`W_control,i,j,t = W_control,i,j × 1 / Σ_{t=0..t} n_rs_t` (A3)
`W_wp,i,t = 1 / Σ_{t=0..t} n_rs_t` (A4)
`W_{control,i,j,t} = W_{control,i,j} \times \frac{1}{\sum_{t=0}^{t} n\_rs_t}`;  `W_{wp,i,t} = \frac{1}{\sum_{t=0}^{t} n\_rs_t}`

| Symbol | Definition (v1.1) | Unit |
|---|---|---|
| W_control,i,j,t | Weight of control plot j matched to project plot i at time t | dimensionless |
| W_wp,i,t | Weight of project plot i at time t | dimensionless |
| n_rs_t | (A3) Number of project plots with (k) matched control plots with values assessed at time t. (A4) Number of project plots with matched control plots (i,j) with values assessed at time t | count |

v1.0 defined n_rs_t as "Number of project plots and matched control plots (i,j) with values assessed at time t".

#### Eq. (A5): control slope by weighted least squares regression (WLSR) (p.72) [v1.1-RECONSTRUCTED; NEW in v1.1]
`ΔSI_control,t = [Σ_{i,j}(W_control,i,j,t × t × SI_control,i,j,t) − (Σ_{i,j}(W_control,i,j,t × t) × Σ_{i,j}(W_control,i,j,t × SI_control,i,j,t)) / Σ_{i,j} W_control,i,j,t] / [Σ_{i,j}(W_control,i,j,t × t²) − (Σ_{i,j}(W_control,i,j,t × t))² / Σ_{i,j} W_control,i,j,t]`
`\Delta SI_{control,t} = \frac{\sum W t\, SI - \frac{(\sum W t)(\sum W\, SI)}{\sum W}}{\sum W t^2 - \frac{(\sum W t)^2}{\sum W}}` (with W = W_control,i,j,t, SI = SI_control,i,j,t, and sums over i,j)

| Symbol | Definition | Unit |
|---|---|---|
| ΔSI_control,t | Slope of stocking index of control plots over time | SI units/yr |
| W_control,i,j,t | Weight of control plot j matched to project plot i, at time t | – |
| SI_control,i,j,t | Stocking index of control plot j matched to project plot i, at time t | SI units |

v1.1 notes that these weights are *not* derived from residual error variance (p.72). v1.0 only said "slope of the weighted linear regression", with a worked example on v1.0 p.62.

#### Eq. (A6): project slope by WLSR (p.72) [v1.1-RECONSTRUCTED; NEW]
This is Eq. (A5) with W_wp,i,t and SI_wp,i,t, summed over i.

| Symbol | Definition | Unit |
|---|---|---|
| ΔSI_wp,t | Slope of stocking index of project plots over time | SI units/yr |
| W_wp,i,t | Weight of project plot i at time t | – |
| SI_wp,i,t | Stocking index of project plot i at time t | SI units |

#### Eq. (A7): Z test (p.73) [v1.0-CONFIRMED, v1.0 A5, p.60]
`Z = (ΔSI_wp,t − ΔSI_control,t) / √(SE²_ΔSI_wp,t + SE²_ΔSI_control,t)`
`Z = \frac{\Delta SI_{wp,t} - \Delta SI_{control,t}}{\sqrt{SE_{\Delta SI\_wp,t}^2 + SE_{\Delta SI\_control,t}^2}}`

| Symbol | Definition | Unit |
|---|---|---|
| Z | Z value | unitless |
| ΔSI_control,t / ΔSI_wp,t | Weighted average annual increase (slope) in SI in control / project plots through time t | – |
| SE²_ΔSI_wp,t / SE²_ΔSI_control,t | Squared standard error of the average annual increase (slope) in SI in project / control plots through time t | – |

Threshold: if **|Z| ≥ 1.96**, the two slopes are significantly different and the project is additional for the performance benchmark.

#### Eq. (A8): performance benchmark (Step 6, p.73) [v1.0-CONFIRMED, v1.0 A6, p.61]
`PB_t = ΔSI_control,t × 1/ΔSI_wp,t`
`PB_t = \Delta SI_{control,t} \times \frac{1}{\Delta SI_{wp,t}}`

Rules:
- (a) If |Z| < 1.96, **PB_t = 1** and Eq. (A8) is not applied.
- (b) If |Z| ≥ 1.96, apply Eq. (A8).
- If ΔSI_control,t is insignificant (**P > 0.05**) or **< 0**, set ΔSI_control,t = 0.

PB_t is "dimensionless" here.

### Appendix 2: significance of pools and sources (pp.77–78)

#### Eq. (A9) [v1.1-RECONSTRUCTED; NEW]
`CSR = Σ Es / CR`
`CSR = \frac{\sum_s E_s}{CR}`

#### Eq. (A10) [v1.0-CONFIRMED in form as v1.0 A7, p.67; scope changed]
`RC_Es = Es / Σ_{s=1..S} Es`

| Symbol | Definition (v1.1) | Unit |
|---|---|---|
| CSR | Combined significance ratio | – |
| CR | Total carbon dioxide removals expected from the project | tCO2e |
| Es | Project emissions and decreases in optional carbon pools | tCO2e |
| RC_Es | Relative contribution of each source s | – |
| s | 1 … S sources of project GHG emissions (excluding leakage) and decreases in carbon pools | – |

Procedure:
- If CSR < 0.05, all optional sources are de minimis.
- If CSR ≥ 0.05, rank the sources largest first and add them until the cumulative total is **≥ 95%**. Include all of those. The remainder may be excluded only if their combined impact is also **< 5% of CR**; otherwise keep adding sources.

Leakage is excluded from this test. v1.0 included leakage in Es and had no CSR step.

### Appendix 3: switching sampling approach (pp.79–80) [all v1.1-RECONSTRUCTED; NEW]
- (A11) `SE_ΔC,t0→t1 = √(SE²_t=0 + SE²_t1)`. This covers the independent or temporary-plot period.
- (A12) `SE_ΔC,t1→t = √(SE²_t1 + SE²_t − (2 × ρ × SE_t1 × SE_t))`. This covers the permanent-plot period, where ρ is the correlation between measurements at t1 and t.
- (A13) `SE_ΔC,t0→t = √(SE²_ΔC,t0→t1 + SE²_ΔC,t1→t)`
- (A14) `ΔC_t0→t = C_t − C_t0`
- (A15) `ΔC_t0→t = ΔC_t0→t1 + ΔC_t1→t`
- (A16) `UNC_t = MIN(100%, MAX(0, (T × SE_ΔC,t0→t / ΔC_t0→t) − 0.10) × 100)`

All SE and ΔC terms are in t CO2e.

---

## 3. Data a platform must capture

### 3a. Project / boundary (validation)
- **Project area A in ha** (p.38). Use GIS polygons for each discrete parcel, each with a unique geographic ID. Imagery must be geo-registered.
- Start date and its trigger: site preparation date vs land use change date. Keep evidence: photos, imagery, attestations.
- Management history covering 10 years, to show the land was not managed forest.
- A record of whether site preparation occurred, its type, any soil inversion and its depth, and whether dead wood was removed offsite.
- Selected approach and instance boundaries, with a ≥ 10 m separation from any census-based instances.
- Ecoregion (WWF/Olson biome) or Holdridge life zone. This drives the choice of allometry and R.
- Annual cohort per instance for grouped projects, since each cohort gets its own PB.

### 3b. Field plots (t = 0, then "every five years or more frequently")
The methodology does **not** prescribe plot size, shape or count. It requires:
- A sample design that is "unbiased and derived from representative sampling".
- Stratification, which is optional for biomass pools and **mandatory for SOC**.
- An SOP that documents the design.

The sample design may change between events for biomass pools. For SOC it should be held constant, and any change must be documented and justified.

Per **live woody plant** in a plot (pp.45–47):
- species, or forest type;
- the measured allometric inputs, for example **DBH, diameter at root collar, total height**;
- **fixed size thresholds** for those variables, held for the whole crediting period;
- for each variable used in allometry, a parameter table in the project description.

Allometry hierarchy:
- For ANR or stands with more than 2 species: (i) forest-type equation from the same ecoregion or life zone, then (ii) a global forest-type equation.
- Otherwise, for example monocultures: (iii) a species, genus or family equation from the same ecoregion or life zone, then (iv) a global species, genus or family equation.
- A global equation must have been developed or validated with destructive-sample data from the same ecoregion or life zone.
- VT0005 does not apply.

Double or two-phase sampling (3P, ratio) is allowed. It needs a complete census of an auxiliary variable, such as SI, plus a field subsample to fit the relationship.

Per **plot-level record**: plot ID, coordinates, plot area, stratum, measurement date, and permanent vs temporary status. Permanent vs temporary is needed to decide whether the ρ term in Eq. (28) applies.

**Non-woody biomass**, if included (pp.47–48):
- Clip all live and dead non-woody mass above the soil inside a frame.
- Record frame area, wet mass, and either a dry mass or a subsample dry-to-wet ratio.
- Take **at least two samples, at minimum and maximum standing stock**, or one conservative sample at minimum stock.
- If subsampling is used, treat it as a double sample for uncertainty.

**Standing dead wood** (pp.48–50):
- Per stem: species, DBH, height, and visible **break height**. Only the bole counts.
- Stem volume comes from allometry, using the same hierarchy as live trees.
- Record decay class. Apply a density reduction factor (e.g., Harmon et al. 2011) and a published wood density, chosen in order of preference: species > genus > family > forest type.

**Lying dead wood** (pp.50–51):
- Use line intersect sampling (Van Wagner 1968; Warren & Olsen 1964), perpendicular distance sampling, or another unbiased method.
- Record transect geometry, piece diameter, length if used, and decay class.
- Apply a wood density and a density reduction factor.
- Fixed size thresholds apply.

**Litter** (pp.51–52):
- Collect dead surface material < 10 cm diameter from fixed-area frames.
- Record green weight of the total sample and of a subsample. Dry the subsample at 70 °C to constant weight.
- Measure at t = 0 and then at least every 5 years.

**SOC** (pp.52–54):
- Clear surface organic material first.
- Sample to a **minimum depth of 30 cm**.
- Measure SOC % and **bulk density at the same time**.
- Use stratified sampling.
- Re-measurements after t = 0 must use the **equivalent soil mass** method (Wendt & Hauser 2013).
- Use lab methods such as Nelson & Sommers 1996 or Schumacher 2002.
- Frequency: at t = 0 and at every verification. SOC may be measured as rarely as **every 10 years at most**, and reported as zero in between, if site-preparation disturbance happened no more than once **or** involved no inversion deeper than 25 cm.

**Burning** (p.54): burned-area polygons (A_burn,t) from imagery or GPS survey, plus the fire date. Monitor at least every 5 years.

**Fertiliser** (pp.55–56):
- Mass of synthetic fertiliser (M_SF) and organic fertiliser (M_OF) applied, in tonnes, from land management records.
- A written attestation from the land manager, plus documents such as logs, receipts or invoices.
- NC_SF from the manufacturer's specification.
- NC_OF from published or peer-reviewed data, preferably recent and from the same country.
- Collect at least every 5 years or before each verification.

**SE_p,t** (pp.60–61): the standard deviation of plot values divided by √n. Under double sampling, use the regression or ratio RMSE scaled to sample size, following Cochran (1977). Include QA/QC with error checking and outlier detection.

### 3c. Remote sensing: performance benchmark database (§9.3.1, pp.62–63; Appendix 1)
- **Description of the stocking index (SI) and the process used to derive it.** A reference to a database is not sufficient (§9.3(11)).
- The SI must correlate significantly with aboveground biomass, shown by published or peer-reviewed studies **or** by validation with direct measurements from the project ecoregion (p.74). Examples given: NDFI from Landsat (Souza et al. 2005), LiDAR mean canopy height, and % canopy cover from aerial imagery.
- **Project plots:**
  - Equal-size contiguous units of **0.01 ha (10 × 10 m) to 10 ha**, with **≥ 75%** of each unit inside the boundary. A plot may be a pixel or an aggregate of pixels.
  - Random sample of **n ≥ 30** per annual cohort. Strata may each have fewer than 30 if the total is ≥ 30 and each stratum gets its own PB.
  - Store ID, location, size and configuration, and the SI time series from t = 0 to t.
- **Donor pool layers (Table A1, p.68),** each current to t = 0 ± 5 years:
  - jurisdictional boundary: national, or subnational if JNR/FREL applies, no lower than admin level 2;
  - same ecoregion (biome);
  - same tree-planting incentive policy environment;
  - optional exclusion of registered AFOLU projects, using registry KML files;
  - same land tenure classes, at minimum public vs private;
  - **≤ 100 km from the project plot centroid**.

  Any extra categorical layer must have resolution **no coarser than 30 × 30 m** and no coarser than the project plots.
- **Control plots:**
  - Non-overlapping units within **± 20%** of the mean project-plot size.
  - Covariates: **SI at three or more historic time points**, minimally one between t = −10 and −8, one between t = −8 and −1, and one at t = 0 (Table A2, p.69).
  - The multivariate distance (Euclidean, Mahalanobis or similar) is chosen by the project proponent.
  - k-NN optimal matching **without replacement**. k is chosen by the project proponent and held constant for the project lifetime.
  - Store weights (Eq. A1), the matched project-plot ID, UTM coordinates fixed after a valid match, and the SI time series.
- **Monitoring frequency for SI: at least annually** (p.74).
  - Use a fixed seasonal target window with minimal phenological variation and, for passive sensors, the lowest cloud cover.
  - PB must be updated at **each verification or every 5 years, whichever is first** (A1.1(3)).
  - Each monitoring interval must include **at least two annual time steps, t and t = 0**, plus all observations from earlier verifications. v1.0 required three time steps.
  - If any member of a matched set has no SI at time t, drop that whole matched set for that t. The project must still keep **n ≥ 30** project plots.
- Control plots become invalid if a new subsidised tree-planting programme starts there, or if they enter a registered offset project (optional). Invalid plots must be replaced from the donor pool and the weights re-normalised.
- A change of SI sensor or metric is allowed only if accuracy is equal or better, a peer-reviewed harmonisation method is used, and the old and new metrics overlap by **≥ 2 years** (pp.75–76).
- Archive the remote sensing datasets and time stamps (§9.3.1(4)). All data must be kept for **≥ 2 years after the end of the last crediting period** (§9.3(8)).

---

## 4. Defaults, constants, thresholds and tables

| Item | Value | Source as cited in VM0047 v1.1 | Page |
|---|---|---|---|
| CF | **0.47** t C/t d.m. | 2006 IPCC Guidelines | p.40 |
| R (root:shoot) | Project-specific, from a hierarchy. ANR or >2 spp.: ecoregion/Holdridge forest-type value, then global forest-type value (e.g., **Table 4.4, Ch.4, Vol.4, 2019 Refinement**). Monoculture: species/genus/family value from the ecoregion, then a global one. A global value must be validated with destructive samples from the same ecoregion or life zone | – | pp.38–39 |
| COMF | Selected by vegetation type: default means in **Table 2.6, Ch.2, Vol.4, 2019 Refinement** (1.0 for census-based only) | – | p.40 |
| EF_g (CH4, N2O) | Project-specific, from **Table 2.2 (and Annex 2), Ch.2, Vol.2 [sic], 2006 IPCC** | – | pp.40–41 |
| GWP_g | "Most recent IPCC assessment report". **No number is given** in VM0047 | – | p.41 |
| EF_Ndirect | **0.01** t N2O-N/t N | Table 11.1, Ch.11, Vol.4, 2019 Refinement | p.42 |
| Frac_GASF | **0.11** | Table 11.3, 2019 Refinement | p.42 |
| Frac_GASM | **0.21** | Table 11.3 | p.43 |
| EF_Nvolat | **0.01** t N2O-N/(t NH3-N + NOx-N) | Table 11.3 | p.43 |
| Frac_LEACH | **0.24** | Table 11.3 | p.44 |
| EF_Nleach | **0.011** t N2O-N/t N leached | Table 11.3 | p.44 |
| 44/12, 44/28, 10^-3 | Molecular-weight ratios and the kg→t conversion | – | pp.19, 25–28 |
| T | Two-tailed Student's t at α = 0.1 (90% CI). Degrees of freedom are not specified | – | p.33 |
| Uncertainty allowance | 10% (the "− 0.10" term) | Eq. 28 / A16 | p.33 |
| Not eligible for crediting | 90% CI half-width > 100% of the CR estimate, which gives CR_t = 0 | – | p.34 |
| Ex-ante minimum uncertainty | ≥ 10% | §8.7(3) | p.36 |
| Z threshold | \|Z\| ≥ 1.96 | A7 | p.73 |
| Control slope significance | P > 0.05 or slope < 0, which sets the slope to 0 | A8 | p.73 |
| SDM threshold | ≤ 0.25 per covariate. If not met, widen the donor radius by **100 km** steps and/or reduce k | A2 | p.70 |
| Project plot size | 0.01–10 ha; ≥ 75% inside the boundary; n ≥ 30 | Step 1 | p.67 |
| Donor pool | ≤ 100 km radius; layers ≤ 30 m resolution; t = 0 ± 5 yr | Table A1 | pp.67–68 |
| Control plot size | Within ± 20% of the mean project plot size | Step 2(2) | p.69 |
| Historic SI window | t = −10 to 0; points in [−10, −8], [−8, −1] and at 0 | Table A2 | p.69 |
| Significance (de minimis) | CSR < 5%; 95% cumulative rule | App. 2 | p.77 |
| t = 0 timing | ≤ 2 yr before the start (site-preparation case); ≤ 2 yr after (land use change / no-disturbance case) | §4.2 | pp.9–10 |
| Remote sensing t = 0 for pre-existing woody biomass | Upper **90%** bound of the SI-regression prediction interval | §8.2.1.2(3)(b) | p.21 |
| Soil disturbance | > 25 cm inversion makes SOC mandatory and, without a t = 0, the project ineligible | §4.2, Table 1 | pp.9, 14 |
| Monitoring frequency | Field pools every ≤ 5 yr; SOC every ≤ 10 yr where allowed; SI ≥ annually; PB at each verification or ≤ 5 yr | §9.2, A1.1 | pp.45–76 |
| Lab drying (litter) | 70 °C to constant weight | – | p.51 |
| Common practice 15% | Census-based only (not applicable here) | §7.3.4 | p.18 |

**CDM tools.** VM0047 v1.1 does **not** reference AR-Tool14 or any other CDM A/R calculation tool for the area-based calculations. Its only CDM references are in §2 "Sources" (p.6):
- AR-ACM0003, the methodology it is based on;
- the "CDM Tool for Testing Significance of GHG Emissions in A/R CDM Project Activities", which is the basis of Appendix 2.

Neither supplies values. Other tools referenced:
- **VT0008** Step 3, for investment analysis (p.17).
- **VMD0054**, for leakage (pp.10, 32).
- **VT0005**, stated *not* to apply (p.47).
- VT0001 appears in "Sources" only.

---

## 5. Uncertainty, buffer, VCUs

**Uncertainty (§8.5, pp.32–34):**
- Only sampling error is quantified. Measurement error is handled through QA/QC.
- Uncertainty is set to **zero** for A (GIS), for the performance benchmark, and for burning and fertiliser emissions.
- UNC_t is computed with Eq. (28) for the cumulative change from t = 0 to t. Use ρ only for permanent plots; for independent re-measurement, ρ = 0.
- If the inventory method changed partway (for example, temporary plots and then permanent plots), use Appendix 3 (Eq. A11–A16).
- The result is a % between 0 and 100. The first 10 percentage points of the 90% CI half-width are forgiven.
- In Eq. (32), UNC_t is applied to ΔC_WP,t after the PB discount, and is **not** applied to PE or LK.
- If the 90% CI half-width exceeds 100% of the estimate, CR_t = 0.

**Removals (Eq. 32, p.35):**
- Removals are computed for each monitoring interval as the difference of cumulative net quantities at t and at t − x.
- Then annualise: CR_annualized = CR_t / x (Eq. 34). Each year in the interval gets the same CR.
- If the project uses both approaches, total CR is the sum of the two.
- If the project harvests, CR is capped by the VCS Standard long-term average (p.35; A1 Step 5, p.73).
- Removing pre-existing biomass under the §8.2.1.2 conditions is *not* treated as harvesting (p.22).

**Buffer / non-permanence: not defined in VM0047.** The governing rules are outside the methodology:
- VCS Standard v5.0 §3.14.15 (`_text/VCS_Standard_v5.0.txt`, line ~1995): "The number of VCUs issued to projects is determined by subtracting out the buffer credits from the reductions and/or removals (including leakage) … The buffer credits are calculated by multiplying the non-permanence risk rating (as determined by the AFOLU Non-Permanence Risk Tool) by the change in carbon stocks only."
- AFOLU Non-Permanence Risk Procedure v5.0 §2.5.1–2.5.3:
  - overall risk = internal + external + natural, **rounded up to the nearest whole percent**;
  - **minimum risk rating 12**;
  - a rating **> 60** fails the analysis.

A typical implementation is therefore `Buffer = NPR% × (change in carbon stocks)` and `VCU = CR − Buffer`. The CR here is net of leakage, per the VCS Standard. Which quantity counts as the "change in carbon stocks" for an area-based VM0047 project is ambiguous: ΔC_WP after the PB and uncertainty deductions, or before them? It is not stated in VM0047. Confirm against the VCS Standard and Registration & Issuance rules.

**VCU rounding.** VM0047 gives **no rounding rule** for CR or VCUs. The local VCS documents searched (Standard v5.0, Program Guide v5.0, RIP v4.4) gave no explicit rule beyond rounding up the risk rating. VCUs are issued in whole units of 1 t CO2e, but the convention for rounding fractional values is **not stated in the sources reviewed**.

---

## 6. Ambiguities, dependencies and v1.0→v1.1 differences

1. **Eq. (28) does not say how to combine pools** (p.33). The text says to apply it "to each carbon pool p", yet it produces a single UNC_t and contains no Σ_p. v1.0 summed squared absolute errors across pools. The reading "sum SE² across pools, assuming independence" is an *interpretation* and is not in the text. ΔC is "Mean change" in t CO2e; whether that is per ha or a project total is unspecified. The ratio is scale-free only if SE and ΔC are on the same basis.
2. **Eq. (28) and (32) and Appendix 3 are reconstructed** from garbled v1.1 glyphs, and have no v1.0 image to check against. The placement of "× 100" and of the 0.10 offset follows A16. Verify against the official v1.1 PDF.
3. **PE_t and LK_t in Eq. (32).**
   - PE_t is defined as "in the monitoring interval ending in year t" (Eq. 12, p.24), but Eq. (32) also subtracts PE_t−x, which only makes sense if PE is cumulative. LK_t is "through year t" (cumulative), so it is consistent.
   - The Eq. (32) table defines PE_t as "in year t".
   - This affects whether emissions are double-handled. v1.0 had the same issue.
4. **Units of PB_t.** Eq. (32) lists "%" and Eq. (A8) says "dimensionless". Both UNC_t and PB_t must be used as fractions in (1 − ·).
5. **PB_t = 1 when |Z| < 1.96** gives CR_t = MIN(ΔC, 0) × … ≤ 0. In other words, a non-additional result produces zero or negative credit. The MIN() term also means losses are not reduced by the PB.
6. **Eq. (A1) vs its text.** The prose says the weights are "proportional to the inverse of the multivariate distance", but the equation uses e^(−MD). This is the same in v1.0 (p.58). Implement the equation, but flag it.
7. **Eq. (A2) symbols.** The mean uses subscript u and the variance uses v, which looks like a typo. v1.0 defined σ² as "standard deviation". The method for the weighted variance of the control plots is not given.
8. **Eq. (A5) and (A6).** The sums are written over i,j (or i) only, but the regression is over the accumulated time series, so the sums implicitly include all time points t. The method for SE of the slope in A7 is not specified (WLS standard error assumed), and neither is the P-value test for the control slope.
9. **Ex-ante PB with ΔSI_wp derived from growth-and-yield** needs an external biomass→SI regression (§8.7(6)(a), p.37). The model source is the project proponent's choice.
10. **No plot→hectare equation for woody biomass.** The step from per-tree allometric biomass (t d.m.) to C_WP-woody-AB,t (t C/ha) is not written out. The implied steps are Σ tree AGB ÷ plot area × CF, then the mean over plots. Expansion factors for variable-radius or nested plots are left to the SOP.
11. **Meaning of t = 0 when plots are measured up to 2 years after the start date** (§4.2(2)(b)). v1.0 (p.17) said the "year of initial measurement is substituted for t = 0". v1.1 dropped that sentence, so it is unclear whether the measurement date or the start date is used as t = 0 in the stock-change and PB time series.
12. **Parameter-table cross-references in v1.1 are stale**, still using v1.0 numbering:
    - CF lists Eq. (13), but should be (14).
    - COMF and EF_g list (12), but should be (13).
    - The census-based Eq. (29) table says "C_total,t, calculated using Equation (29)", but should be (30).
    - The EF_g source is cited as "Volume 2", but the IPCC AFOLU tables are in Volume 4.
13. **Changes from v1.0 that affect implementation:**
    - Minimum project-plot size: 0.09 ha → 0.01 ha.
    - Project-plot sampling: "random or systematic, stratified or unstratified" → "random sampling".
    - Minimum SI time steps per interval: 3 → 2.
    - New explicit WLSR equations (A5, A6).
    - Uncertainty formula rewritten (Eq. 28 replaces v1.0 Eq. 27).
    - CR equation gains MIN() and uses t−x.
    - Ex-ante horizon: v1.0 used a rolling 10-year window; v1.1 uses the whole crediting period.
    - Appendix 2: CSR step added and leakage excluded.
    - Appendix 3 is new.
    - The v1.0 rule that a significant negative pre-start SI slope signals clearing requiring justification (v1.0 p.18) has been removed. In its place, v1.1 allows a remote-sensing t = 0 estimate for pre-existing woody biomass (§8.2.1.2).
14. **External dependencies:**
    - VMD0054 v1.1, for LK_t; mandatory, never de minimis.
    - AFOLU Non-Permanence Risk Tool, for the buffer.
    - VCS Standard: LTA for harvesting, buffer, §3.19 degradation rule.
    - VT0008, for investment analysis.
    - VCS Methodology Requirements, for regulatory surplus.
    - IPCC 2006 / 2019 Refinement tables, for R, COMF, EF_g and the N factors.
    - Most recent IPCC AR, for GWP.
    - WWF/Olson ecoregions or Holdridge life zones.
    - Published allometry, wood densities, and Harmon et al. density reduction factors.
15. **Figure 1 (p.19)**, the area-based calculation flowchart, is an image and is missing from the v1.1 text. The v1.0 figure uses v1.0 equation numbers.
16. **Wetlands and organic soils:** VM0047 covers only aboveground biomass, and a WRC methodology is required for the other pools (§4.1(5)).
