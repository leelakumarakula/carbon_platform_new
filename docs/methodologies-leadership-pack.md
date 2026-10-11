# Carbon methodologies — leadership pack

Prepared for the manager and vice president. **Part 1** is a three-page executive brief: what the platform supports, where it stands, the
recommendation, and the decisions needed. **Part 2** explains each methodology in plain language for anyone who wants the detail.
The exact rule-by-rule technical reference for the methodology expert is kept separately (methodologies-reference.md).

## Contents
- Part 1 — Executive brief: Summary · What a methodology is · What the platform supports · Where we stand · Which methodology for our
  projects · Decisions and risks · Next steps
- Part 2 — The methodologies in detail: 1 Basic concepts · 2 The standards · 3 At a glance · 4 How the platform runs any methodology ·
  5 VM0042 · 6 GS 402 · 7 VM0047 · 8 VM0044 · 9 VM0051 · 10 BM AG04.002 · 11 BM FR05.002 / FR05.001 · 12 GS 403 · 13 Comparison ·
  14 Choosing a methodology

## Part 1 — Executive brief

### Summary
The platform can calculate carbon credits under **9 methodologies** from **3 standards** — Verra, Gold Standard and India's Carbon
Credit Trading Scheme (CCTS) — covering **soil carbon on cropland, paddy rice, trees on farms, plantations and mangroves, and biochar**.
All 13 calculation variants are built and pass their automated tests, and the full soil-carbon flow has been run end to end on test data.
**None is approved for live credits yet**: each needs a review by a qualified methodology expert before real projects use it.

**Recommendation:** use **Verra VM0042** for our soil-sampling cropland projects, and start the expert review with VM0042.

---

### What a methodology is, and why it matters
A methodology is the official rulebook of a carbon standard for one type of project. It decides **which projects qualify**, **what is
counted**, **which equations and factors are used** and **what must be monitored**. Credits are only issued if the calculation follows the
methodology exactly, as checked by an independent verifier (VVB). Each project uses **one methodology for its whole life**.

### What the platform supports
| Project type | Methodology | Standard | Credit | How carbon is measured |
|---|---|---|---|---|
| **Cropland practice change** (reduced tillage, residue mulching, cover crops, nutrient management) | **VM0042 v2.2** | Verra | VCU | Soil sampled twice and laboratory-analysed, compared with control farms |
| Cropland practice change — Gold Standard (5 variants) | GS 402 v1.0 | Gold Standard | GS VER | Soil sampled twice, **or** IPCC default factors without sampling |
| **Paddy rice** — water saving, straw management | VM0051 v1.1 | Verra | VCU | Methane from field records and IPCC factors |
| Paddy rice — Indian compliance market | BM AG04.002 v1.0 | India CCTS | CCC | Methane from IPCC default values |
| **Trees on farmland** (≤ 50 per hectare) | VM0047 v1.1 | Verra | VCU | Tree census and sampled tree measurements |
| Plantations / reforestation | GS 403 v2.1 | Gold Standard | GS VER | Forest inventory plots |
| Plantations / reforestation — India | BM FR05.002 v1.0 | India CCTS | CCC | Forest inventory plots |
| Mangrove restoration — India | BM FR05.001 v1.0 | India CCTS | CCC | Forest inventory plots |
| **Biochar** from crop residue | VM0044 v1.2 | Verra | VCU | Biochar quantity and laboratory analysis |

### Where we stand
| Area | Status |
|---|---|
| Calculation modules | **13 built** (9 methodologies; GS 402 has 5 variants), each implementing the official equations with references |
| Automated testing | **34 tests passing** — every module checked against an independent hand calculation |
| End-to-end testing | Soil-carbon flow run in the test environment from farmer registration to calculated credits (VM0042: about **950 credits** on a 100-hectare test farm; GS 402 also run) |
| Approval for live credits | **Not yet — "not production ready" for all 13** |
| Safeguards | One locked methodology per project; land-overlap checks; one registry submission per period; issued credits capped at the verified amount; duplicate-serial checks; every approval by a second person and fully audited |

**What "not production ready" means:** the calculations are built and tested, but a qualified methodology expert must confirm that each
one matches the official methodology text, including the interpretations the code makes where the text is ambiguous. Until that review is
recorded in the platform, the calculation runs in testing only and is **blocked in the live system**. This protects us from issuing credits
that a verifier could later reject.

### Which methodology for our projects
| Our situation | Recommended |
|---|---|
| Farms where we take soil samples and can find comparable control farms | **VM0042** (Verra) — our main choice; tested end to end |
| Farms where we take soil samples but have no control farms | GS 402 measured variant (Gold Standard) |
| Smallholder or pilot projects without soil sampling | GS 402 default-factor variant — simpler and cheaper, but more conservative credits |
| Paddy rice farmers adopting water saving | VM0051 (voluntary market) or BM AG04.002 (Indian compliance market) |
| Tree planting on farm boundaries | VM0047 |

### Decisions and risks
| # | Item | Why it matters | Owner |
|---|---|---|---|
| 1 | **Engage a methodology expert** to review VM0042 first, then the other modules we plan to use | Required before any live credits | Management |
| 2 | **Write the eligibility (applicability) rules** for each methodology from the official text | The platform checks projects against these; they are not supplied with the software | Methodology expert |
| 3 | **Electricity in VM0042** — confirm whether electricity use (e.g. electric irrigation pumps) must be counted | If required, a small addition to the calculation | Methodology expert |
| 4 | **Choose the standard per project** (Verra, Gold Standard or CCTS) before starting | One project = one methodology; prevents double counting | Management |
| 5 | **Field and laboratory capacity** for VM0042 | Each sampling round needs 3+ points per zone, 2 soil layers per point and 2 lab tests per sample; at least 3 control farms per project | Operations |
| 6 | Methodology versions change over time | A new version (e.g. VM0042 v2.3) needs a new calculation module | Product / development |

### Next steps
1. Approve engaging a methodology expert for the VM0042 review.
2. Confirm the standard and methodology for the first live project.
3. Expert writes the eligibility rules and answers the electricity question.
4. Record the production-readiness approval for VM0042 in the platform.
5. Run the first live project; repeat the review for the next methodology we need.

## Part 2 — The methodologies in detail

This guide explains **every methodology the platform can calculate**: who publishes it, what kind of project it credits, what it counts,
how the calculation works, what data it needs, what the platform includes and leaves out, and what the result is. It is general — it is
not about any particular project.

It is written from the platform's calculation modules (`backend/app/calculation/modules/`). Each module records the methodology version,
the sections and equations it implements, the parts it does not implement and the interpretations it makes; this guide explains those in
plain language. For the exact rule codes, units and constants of each module see the technical reference (methodologies-reference.md).

> **Important.** Every module is **Not production ready**. The platform implements each methodology from its official text, but a
> methodology expert must confirm the implementation (in particular the interpretations listed under each methodology) before it is used
> for real credits. Statements here describe **what the platform does**; the official methodology documents remain the authority.

---


### 1. Basic concepts

| Term | Meaning |
|---|---|
| **Methodology** | The official rulebook of a standard for one type of project: who is eligible, what is counted, which equations and default values to use, what to monitor, how uncertainty and permanence are handled. |
| **Baseline** | What would happen without the project (e.g. continued tillage and residue burning, continuous flooding of rice, bare land). |
| **Project scenario** | What happens with the project (e.g. no-till, mulching, alternate wetting and drying, planted trees). |
| **Removals** | CO₂ taken out of the air and stored (soil carbon, trees, biochar). Usually need a permanence buffer. |
| **Emission reductions** | Emissions avoided compared with the baseline (less diesel, less fertiliser N₂O, less methane, no residue burning). |
| **Carbon pools** | Where carbon is stored: soil organic carbon (SOC), above- and below-ground biomass, dead wood, litter, biochar. |
| **Emission sources** | Gases released: CO₂ (fuel, lime), N₂O (fertiliser), CH₄ (rice paddies, burning). |
| **Quantification approach** | How a quantity is obtained: **measured** on site (soil samples, tree inventory), **modelled**, or estimated with **default factors** (IPCC). |
| **Leakage** | Emissions shifted outside the project because of it (e.g. production moving elsewhere after a yield drop). |
| **Uncertainty deduction** | The less precise the estimate, the more is deducted — only the confident part is credited. |
| **Non-permanence / buffer** | Stored carbon can be lost later (fire, ploughing). A share of credits goes to a pooled buffer account to cover such losses. |
| **Reversal** | A net loss of stored carbon in a period — no credits; buffer credits cover it. |
| **GWP** | Global warming potential: CH₄ = 28, N₂O = 265 times CO₂ (IPCC AR5, used by all modules). |
| **44/12** | Converts tonnes of carbon (C) into tonnes of CO₂. |
| **tCO₂e** | Tonnes of CO₂-equivalent — the unit of every result before it becomes a credit. |

**Calculated is not issued.** A methodology calculation gives tCO₂e. Credits exist only after a **VVB verifies** the result and the
**registry issues** them. The platform keeps the three quantities — calculated, verified, issued — separate.

---

### 2. The standards

| Standard | Run by | Credit unit | Methodologies in the platform | Notes |
|---|---|---|---|---|
| **Verified Carbon Standard (VCS)** | Verra | **VCU** — Verified Carbon Unit | VM0042, VM0047, VM0044, VM0051 | Land-based removals use the **AFOLU Non-Permanence Risk Tool** to set the buffer |
| **Gold Standard for the Global Goals** | Gold Standard Foundation | **GS VER** — Verified Emission Reduction | GS 402 (5 variants), GS 403 | **20 % compliance buffer** for sequestration; vintages from 1 January 2026 need **Paris Agreement alignment** (GS 119) |
| **Carbon Credit Trading Scheme (CCTS) — offset mechanism** | Government of India (Bureau of Energy Efficiency) | **CCC** — Carbon Credit Certificate | BM AG04.002, BM FR05.002, BM FR05.001 | India's compliance market; methodologies adapted from IPCC / CDM tools |

---

### 3. The methodologies at a glance

| # | Methodology | Standard | Project type | How carbon is quantified | Field / lab work | Final output |
|---|---|---|---|---|---|---|
| 1 | **VM0042 v2.2** | Verra | Improved agricultural land management (tillage, residue, cover crops, nutrients) | Soil carbon **measured twice** vs. **control sites**; emissions from IPCC factors | Soil sampling (2 rounds, 2 depths), lab | `VCU_TOTAL` |
| 2 | **GS 402 v1.0** (ZT-A1, IT-A1, CC-A1) | Gold Standard | Zero tillage / reduced tillage / cover crops | Soil carbon **measured twice** on the project land | Soil sampling, lab | `GS_VER_TOTAL` |
| 3 | **GS 402 v1.0** (IT-A3, CC-A3) | Gold Standard | Reduced tillage / cover crops | **IPCC or national stock-change factors** (no sampling) | None (factor values) | `GS_VER_TOTAL` |
| 4 | **VM0047 v1.1** | Verra | Trees planted on farmland (≤ 50 per ha) | **Tree census** + sampled tree biomass | Tree measurements | `VCU_TOTAL` |
| 5 | **VM0044 v1.2** | Verra | Biochar production and use | Biochar mass × lab carbon content × permanence factor | Biochar lab analysis | `VCU_TOTAL` |
| 6 | **VM0051 v1.1** | Verra | Paddy rice (water, straw, amendments) | Methane from **IPCC emission factors** and field records | Seasonal field records | `CREDITS` |
| 7 | **BM AG04.002 v1.0** | India CCTS | Paddy rice | Methane from **IPCC default values** | Seasonal field records | `CREDITS` |
| 8 | **BM FR05.002 v1.0** | India CCTS | Afforestation / reforestation (non-wetland) | Tree **plot inventory** | Plot inventory | `LCCC` |
| 9 | **BM FR05.001 v1.0** | India CCTS | Mangrove restoration | Tree **plot inventory** + default mangrove soil carbon | Plot inventory | `LCCC` |
| 10 | **GS 403 v2.1** | Gold Standard | Afforestation / reforestation | **Stem-volume inventory** × Gold Standard factors, capped by a growth model | Inventory plots | `GSVER_PROJECT` |

---

### 4. How the platform runs any methodology

```
Methodology + version  ──(calculation module chosen, version approved)──▶  Project locks the version
        │                                                                          │
        ▼                                                                          ▼
 Monitoring rules  ──▶  MRV plan measurements  ──▶  field / lab / monitoring data  ──▶  approved dataset(s)
                                                                                           │
                         Calculation run: freeze inputs ──▶ execute steps ──▶ outputs ◀────┘
                                                                         │
                         QA approval ──▶ VVB verification ──▶ registry issuance ──▶ ledger / market / payouts
```

Every module follows the same eight calculation steps — **Baseline → Project → Emissions → Removals → Leakage → Uncertainty →
Adjustment (buffer) → Net** — each tied to the methodology's equations. Every output records its inputs and the earlier outputs it used
(lineage), so a VVB can trace any credit back to a lab result, a field record and a farm.

Approaches that use **two campaigns** (VM0042, GS 402 Approach 1, VM0047, CCTS A/R) automatically take the **previous approved period**
as the earlier campaign. Approaches that use **default factors** (GS 402 Approach 3, rice) need one period.

---

### 5. Verra VM0042 v2.2 — Improved Agricultural Land Management
Platform version: v2.2 with the Corrections & Clarifications of 11 June 2026 · module `VM0042-V2.2-QA2-QA3`

#### What it credits
Changes in agricultural land management on cropland that increase soil carbon and/or reduce emissions: reduced or zero tillage, stopping
residue burning (keeping residue as mulch), cover crops, better fertiliser and nutrient management, liming changes, irrigation changes.
Benefits come as **removals** (more soil carbon) and **emission reductions** (less fuel, fertiliser N₂O, burning).

#### What it counts in the platform
| Pool / source | Gas | How |
|---|---|---|
| Soil organic carbon | CO₂ | **Quantification Approach 2 — measure and remeasure**: soil sampled at the start and again later, compared with **baseline control sites** |
| Fossil fuel (diesel, gasoline) | CO₂ | Approach 3 — default emission factors |
| Liming (limestone, dolomite) | CO₂ | Approach 3 — default factors |
| Synthetic and organic fertiliser | N₂O (direct + indirect: volatilisation, leaching) | Approach 3 — IPCC 2019 factors by climate |
| Burning of crop residues | CH₄, N₂O | Approach 3 — IPCC factors and combustion factors per crop |

**Not included** (the project must show they are not applicable or negligible): Approach 1 (process models), livestock (enteric
fermentation, manure), nitrogen-fixing species, woody biomass, and leakage sources 8.4.1–8.4.4 (reported as zero).

#### How the calculation works
1. **Soil profile per sampling point.** For every depth layer (at least two, e.g. 0–30 and 30–50 cm) the lab reports organic carbon (g/kg) and
   dry fine-earth mass (g, stones > 2 mm removed). The core area (probe diameter × number of cores) converts the mass into tonnes per hectare.
2. **Equivalent soil mass (ESM).** Soil carbon is compared in the **same mass of mineral soil**, not the same depth, so tillage and compaction
   cannot create an artificial change. Organic matter is removed as SOC ÷ 0.58; layers are interpolated (linear with 2 layers, cubic spline with 3+).
   The **reference mass** is the mean mineral mass to **30 cm** at the linked **control sites in the earlier campaign**.
3. **SOC stocks** (t C/ha at the reference mass) per stratum: project strata and their control sites, earlier and current campaign.
4. **Removals** = (current − earlier stock) × stratum area × 44/12, for the project (`DCO2_SOIL_WP`) and for the control sites — the
   baseline (`DCO2_SOIL_BSL`).
5. **Emissions**: baseline = average yearly activity of the **three years before the project** × years in the period; project = activity in
   the period. Reduction per source = baseline − project. Climate class: **tropical wet if rainfall > 1,000 mm**, otherwise dry; in dry
   climates nitrogen leaching is counted only with irrigation other than drip.
6. **Uncertainty**: from the spread of the samples (stratified estimator, area-weighted, one-sided 66.67 % Student-t, Welch–Satterthwaite
   degrees of freedom); the percentage is deducted from the soil changes.
7. **Buffer**: the **AFOLU non-permanence risk rating** (%) is applied to the soil-carbon credits.
8. **VCUs** = net removals + net emission reductions after the buffer, in whole tonnes rounded down. A net loss is a **reversal** (no VCUs).

#### Data required
| Data | Level | Required |
|---|---|---|
| Organic carbon (g/kg) and dry fine-earth mass (g) per depth layer, both campaigns | sample | Yes |
| Depth of each layer; probe inside diameter; number of cores | sample / field record | Yes |
| Stratum area; ≥ 3 control sites linked to every project stratum | stratum | Yes |
| Non-permanence risk rating (%) | project | Yes |
| Annual rainfall (mm) | stratum | Optional (dry factors if missing) |
| Fertiliser N (synthetic, organic), diesel, gasoline, limestone, dolomite, residues burned (rice, wheat, other), irrigation type — 3 baseline years + project period | farm | Optional (0 if missing) |

**Sampling rule:** measure and remeasure, stratified random design, at least **3 points per stratum**, core details mandatory.

#### Interpretations for the expert review
Uncertainty % divided by 100 before use · buffer never negative, negative results are reversals · one-sided 66.67 % t with
Welch–Satterthwaite d.f. · uncertainty capped at 100 % · variance of a change = sum of the two campaigns' variances · IPCC 2019 Tier 1 by
climate · ESM reference mass from the earlier campaign's control sites · AR5 GWPs · VCUs rounded down · baseline emissions = mean of the
BASELINE years.

#### Result
`VCU_TOTAL` (with `VCU_CR` from removals and `VCU_ER` from emission reductions).

---

### 6. Gold Standard GS 402 v1.0 — Soil Organic Carbon Framework (5 variants)
Platform modules `GS402-ZT-A1`, `GS402-IT-A1`, `GS402-IT-A3`, `GS402-CC-A1`, `GS402-CC-A3`

#### What it credits
Soil carbon gains from changing cropland management, under Gold Standard. GS 402 is a **framework** used together with **one activity
module**:

| Activity module | Practice | Variants in the platform |
|---|---|---|
| **402.4 Zero Tillage** v1.0 | Switch to no tillage | **ZT-A1** — measured (to 50 cm) |
| **402.1 Improved Tillage** v1.0 | Switch to reduced tillage | **IT-A1** — measured (30 cm) · **IT-A3** — IPCC factors |
| **402.6 Cover Crops** v1.0 | Growing cover crops | **CC-A1** — measured (30 cm) · **CC-A3** — national / regional Tier 2 factors |

**Not included:** Approach 2 (models or literature), 402.6 Approach 3.2 (IPCC Tier 2 steady-state method), 402.2 organic soil improvers.

#### Two quantification approaches
| | **Approach 1 — measured** (ZT-A1, IT-A1, CC-A1) | **Approach 3 — default factors** (IT-A3, CC-A3) |
|---|---|---|
| Soil carbon | Sampled at the start and again later on the **project land itself** (no control sites) | SOC_REF × land-use factor × management factor × input factor, before vs. after |
| Comparison | Equivalent soil mass to the reference depth (50 cm zero tillage, 30 cm others) | Change spread over **20 years** (IPCC default): each year earns 1/20 |
| Samples | ≥ 3 per stratum and campaign | None |
| Uncertainty | From the samples (90 % two-sided t) | From the factors' ± % (IPCC tables); without a ± % the code assumes 50 % error |

#### How the calculation works
1. **SOC at the start (SOC₀) and end (SOCₜ)** of the period per stratum — measured (Approach 1) or from factors (Approach 3).
2. **ΔSOC** = (SOCₜ − SOC₀) × area.
3. **Uncertainty deduction (UD)**: uncertainty at 90 % confidence; only the part **above 20 %** is deducted.
4. **Project emissions** — only **increases** over the baseline count (decreases are never credited): fertiliser N, diesel, gasoline,
   **electricity** (with its emission factor), other agrochemicals; cover crops also **seed production and transport**. Baseline = average
   of up to **5 years** before the project; without baseline records the baseline is taken as 50 % of the project value (conservative).
5. **Leakage**: only if **yields fall** — the share of lost yield × area × the emissions of land used elsewhere.
6. **Emission reductions** ER = [ΔSOC × (1 − UD) × 44/12 − project emissions − leakage].
7. **Buffer**: **20 %** to the Gold Standard Compliance Buffer.
8. **Paris alignment (GS 119)**: the share of the period from **1 January 2026** is credited only if the project records **PAA = YES**
   (Gold Standard approved its Paris-aligned transition).
9. **GS VERs** in whole tonnes rounded down; a negative result is a reversal.

#### Data required
| Data | Variants |
|---|---|
| Organic carbon and soil mass per layer, both campaigns; probe diameter and cores | A1 |
| SOC_REF, land-use factor, tillage and input factors (baseline and project), years of baseline practice, years since project start, ± % of each factor | A3 |
| Fertiliser N, diesel, gasoline, electricity, agrochemical emissions (farm); diesel, gasoline and electricity emission factors (project) | all (optional) |
| Crop yield (farm); leakage-area emissions (project, only after a yield drop) | all |
| Cover-crop seed (kg), seed production and transport factors, transport distance | CC-A1, CC-A3 |
| Paris alignment status (project) | all |

#### Result
`GS_VER_TOTAL` (with `ER_NET`, `BUFFER`, `PAA_BLOCKED_SHARE`).

---

### 7. Verra VM0047 v1.1 — Afforestation, Reforestation and Revegetation (census-based)
Module `VM0047-V1.1-CENSUS` · VM0047 v1.1 (14 May 2025)

#### What it credits
Carbon stored in **trees planted on land whose use continues** (e.g. trees on farm boundaries, agroforestry), with **at most 50 planting units
per hectare**, planted directly. The **census-based approach** counts every planted unit.

**Not included:** the **area-based approach** (it needs a remote-sensing dynamic performance benchmark) and VMD0054 leakage.

#### How the calculation works
1. **Census**: the number of planting units **N** per stratum at the start (t = 0).
2. **Mortality** Mₜ = dead ÷ sampled units in the monitoring event.
3. **Biomass**: above-ground woody biomass of each **sampled live unit** (kg dry matter, from a documented allometric equation — species,
   else genus, else family, same ecoregion); below-ground with the **root-to-shoot ratio**; carbon fraction **0.47**.
4. **Woody carbon stock** = N × (1 − Mₜ) × mean carbon per live unit; change since the previous event.
5. **Baseline** = zero (no planting without the project). **Leakage** = zero for the census approach.
6. **Project emissions**: burning (CH₄, N₂O) and fertiliser N₂O.
7. **Uncertainty** at 90 %: if the half-width exceeds **100 %** of the stock, **no removals** are credited; otherwise the part above 10 % is deducted.
8. **Buffer** = non-permanence risk rating (**minimum 12 %**) × the stock change; VCUs rounded down; a net loss is a reversal.

#### Data required
Census count N per stratum (repeated each period) · per sampled unit: alive / dead, above-ground biomass (kg d.m.), burned yes / no ·
root-to-shoot ratio · fertiliser N (synthetic, organic) · non-permanence risk rating.

#### Result
`VCU_TOTAL` (with `NET_REMOVALS`, annualised removals, `REVERSAL`).

---

### 8. Verra VM0044 v1.2 — Biochar Utilization
Module `VM0044-V1.2` · equations unchanged from v1.1

#### What it credits
Carbon locked in **biochar** — charcoal made by heating biomass (crop residue, wood, husks, manure) with little oxygen — that is **applied
to soil** or used in **non-soil applications** (e.g. concrete, asphalt). One project = **one production facility**.

#### How the calculation works
1. **Persistent carbon** = biochar used × **organic carbon content F_Cp** × **permanence factor PR** (share still stored after 100 years):
   - F_Cp from **laboratory analysis** (mandatory for high technology) or a default by feedstock and process;
   - PR from the **production temperature**: > 600 °C → 0.89; 450–600 °C → 0.80; 350–450 °C → 0.65; lower or unknown → 0.56.
2. **Production emissions**: pre-treatment, auxiliary energy and processing (electricity, fuel — calculated with CDM tools, entered as
   tCO₂e); **low-technology** kilns also emit **methane** (default 0.049 t CH₄ per tonne). Allocated by biochar used ÷ produced.
3. **Application emissions** and **transport leakage** (legs with a round trip under 200 km are not counted).
4. **Emission reductions** = persistent carbon × 44/12 − production − application emissions − leakage.
5. **No uncertainty deduction and no buffer** — VM0044 has neither; permanence is already in the PR factor.

**Eligibility enforced:** soil biochar with any batch **H:C ratio above 0.7** is refused.

#### Data required
Biochar produced; used in soil; used in non-soil applications (t dry) · lab organic carbon content and H:C ratio · production temperature ·
technology (HIGH / LOW) · feedstock class and process · methane per tonne (low technology) · pre-treatment, auxiliary, processing and
transport emissions (tCO₂e).

#### Result
`VCU_TOTAL` (with `ER_NET`).

---

### 9. Verra VM0051 v1.1 — Improved Management in Rice Production Systems
Module `VM0051-V1.1-QA3` — Quantification Approach 3 (IPCC 2019 emission factors)

#### What it credits
Reducing **methane from flooded rice paddies** by changing water management (e.g. **alternate wetting and drying**, mid-season drainage),
pre-season water status, and the management of **straw and organic amendments** (compost, farmyard manure, green manure).

**Not included:** Approach 1 (models) and Approach 2 (chamber measurement) — these are mandatory under VM0051 for methanotrophs, biochar,
low-emission cultivars and AWD shallower than 10 cm, so such projects cannot use this module.

#### How the calculation works
1. **Daily methane emission factor** per field and season: EF = EFc × **SFw** (water regime during the season) × **SFp** (water status before
   the season) × **SFo** (organic amendments: (1 + Σ amount × conversion factor)^0.59).
2. **Methane** = EF × cultivation days × area × GWP, per season.
3. **Baseline** from the farm's look-back years (with a conservative drainage rule and 5 t/ha straw).
4. **N₂O**: drying periods increase N₂O, and changes in the nitrogen rate are counted.
5. **Fuel, residue burning, straw used elsewhere** and **leakage** (imported organic amendments, diverted bioenergy residues).
6. **Uncertainty**: 15 % on the methane and N₂O changes.
7. Credits = baseline − project − leakage − uncertainty.

#### Data required
Per field and season: rice area, cultivation days, water regime (continuous / single / multiple drainage), pre-season water status, straw
incorporated and its timing, compost, farmyard manure, green manure, nitrogen applied, diesel, residue burned · baseline look-back seasons ·
IPCC region (or a country-specific factor and its uncertainty) · straw end-use emissions, leakage, land-preparation fuel.

#### Result
`CREDITS` (with `ER_NET`).

---

### 10. India CCTS BM AG04.002 v1.0 — Improved rice management
Module `CCTS-AG04.002` — IPCC default-value approach; same emission-factor engine as VM0051

#### What it credits
Methane reduction in paddy rice under **India's Carbon Credit Trading Scheme** — the compliance-market counterpart of VM0051.

#### Differences from VM0051 in the platform
| | VM0051 (Verra) | BM AG04.002 (CCTS) |
|---|---|---|
| Market | Voluntary (VCUs) | Indian compliance (CCCs) |
| Uncertainty | 15 % on ΔCH₄ and ΔN₂O | 15 % on the whole reduction |
| N₂O decreases | Counted | **Not credited** |
| Extra sources | Fuel, burning, straw end use, leakage | Fewer (default-value approach) |
| Drying N₂O | (0.005 − 0.003) × 44/28 × N | Same |

#### Data required
As VM0051: rice area, days, water regime, pre-season status, straw, amendments, nitrogen per field and season; baseline seasons; region.

#### Result
`CREDITS`.

---

### 11. India CCTS BM FR05.002 and FR05.001 v1.0 — Afforestation / reforestation
Modules `CCTS-FR05.002` (lands except wetlands) and `CCTS-FR05.001` (degraded mangrove habitats), with tool BM-T-AR-0004 v1.0

#### What they credit
Carbon stored by **planting trees** under India's CCTS — on degraded or non-forest land (**FR05.002**) or in **degraded mangrove habitats**
(**FR05.001**).

#### How the calculation works
1. **Tree carbon stock** by **stratified random sample plots**: above-ground biomass of each plot (species allometric equations); below-ground
   biomass with a per-plot root-to-shoot ratio; scaled to the stratum.
2. **Shrubs** (optional) from crown cover (below 5 % = zero).
3. **Stock change** = current estimate − previous approved estimate (or the pre-project stock at the first verification), reduced by a
   **discount for uncertainty**.
4. **FR05.001 only**: soil carbon of planted mangrove areas at a **default 0.50 t C/ha/year for 20 years**.
5. **Net** ΔC = project change − burning emissions − baseline change − leakage.
6. **Credits for the verification** (`LCCC`), whole units rounded down. A negative value means credits must be **replaced** (`REPLACEMENT_DUE`).

**Not included:** dead wood and litter (optional pools — excluded, conservative); FR05.002 soil carbon.

#### Data required
Per plot: above-ground tree biomass (t d.m.) · plot size · pre-project stock · baseline change · shrub crown cover and regional forest
biomass · burning emissions and leakage (tCO₂e from the CCTS tools) · planting year (mangroves).

#### Result
`LCCC` (credits for this verification; the registry keeps the running total).

---

### 12. Gold Standard GS 403 v2.1 — Afforestation / Reforestation
Module `GS403-V2.1`

#### What it credits
Carbon stored by **tree plantations and forests** under Gold Standard. GS 403 uses its **own conversion factors** (not the CDM A/R tools).

#### How the calculation works
1. **Stem volume** from forest inventory plots per **Modelling Unit** (MU = stratum).
2. **Carbon** = volume × wood density × biomass expansion factor × (1 + root-to-shoot) × 0.47 × 44/12. Defaults: wood density 0.3, BEF 1.1,
   root-to-shoot 0.2 unless the MU's own factors are recorded.
3. **Precision rule**: the inventory must be within **±20 % at 90 %**; the excess is deducted.
4. **Cap**: the creditable stock never exceeds the **growth model's** expected or long-term value.
5. **Baseline, leakage and burning** are deducted once (first year); fertiliser N in the year of use.
6. **Issuable** = cumulative net removals − units already issued.
7. **Buffer**: **20 %** to the Gold Standard Compliance Buffer.
8. **Paris alignment**: vintages from 1 January 2026 need **PAA = YES**.

#### Data required
Stem volume per plot · plot area · MU wood density, BEF, root-to-shoot (optional) · growth-model values · mangrove planting year (adds
1.8 tCO₂/ha/yr for 20 years) · baseline stock · baseline burning yes/no · leakage · fertiliser N (this and earlier periods) · units issued
before · Paris alignment status.

#### Result
`GSVER_PROJECT` (with `GSVER_ELIGIBLE`).

---

### 13. Side-by-side comparison

| | VM0042 | GS 402 A1 | GS 402 A3 | VM0047 | VM0044 | VM0051 | AG04.002 | FR05 | GS 403 |
|---|---|---|---|---|---|---|---|---|---|
| Main pool / source | Soil C + emissions | Soil C | Soil C (factors) | Tree biomass | Biochar C | Rice CH₄ | Rice CH₄ | Tree biomass | Tree biomass |
| Quantification | Measured ×2 + controls | Measured ×2 | IPCC / national factors | Census + sample | Lab + defaults | IPCC factors | IPCC defaults | Plot inventory ×2 | Stem-volume inventory |
| Control sites | **Yes (≥ 3)** | No | No | No | No | No | No | No | No |
| Two campaigns | Yes | Yes | No | Yes | No | No | No | Yes | Cumulative |
| Uncertainty | Sampling, deducted | > 20 % deducted | Factor ± %, > 20 % deducted | > 10 % deducted; > 100 % = none | **None** | 15 % | 15 % | Discount | > 20 % deducted |
| Buffer | NPR % (AFOLU tool) | 20 % | 20 % | NPR % (min 12) | **None** | — | — | Replacement rule | 20 % |
| Paris alignment check | — | Yes (2026+) | Yes (2026+) | — | — | — | — | — | Yes (2026+) |
| Credit unit | VCU | GS VER | GS VER | VCU | VCU | VCU | CCC | CCC | GS VER |

---

### 14. Choosing a methodology

| Your project | Use |
|---|---|
| Cropland practice change, soil sampling possible, control farms available | **VM0042 v2.2** |
| Cropland practice change, soil sampling possible, no control farms | **GS 402 v1.0** — ZT-A1 (zero tillage) / IT-A1 (reduced tillage) / CC-A1 (cover crops) |
| Cropland practice change, no soil sampling (smallholders, pilots) | **GS 402 v1.0** — IT-A3 / CC-A3 |
| Paddy rice — water saving, straw management (voluntary market) | **VM0051 v1.1** |
| Paddy rice — Indian compliance market | **BM AG04.002 v1.0** |
| Trees on farmland, at most 50 per hectare | **VM0047 v1.1** |
| Plantation / reforestation — Gold Standard | **GS 403 v2.1** |
| Plantation / reforestation — Indian compliance market | **BM FR05.002 v1.0** |
| Mangrove restoration — Indian compliance market | **BM FR05.001 v1.0** |
| Biochar from crop residue or other biomass | **VM0044 v1.2** |

**Rules that always apply**
- One project = **one** methodology version for its whole life; different activities are separate projects.
- The project must meet the methodology's **applicability conditions** — written as applicability rules by the methodology specialist from the
  official text; the platform checks them against the farm and project records.
- A methodology version must **choose its calculation module before it is approved**.
- Every module needs the **expert production-readiness review** before it is used for real credits.

