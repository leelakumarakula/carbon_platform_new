# Methodologies and methodology rules in the platform

Every methodology the platform can calculate, with **all of its rules exactly as built into the code** (`backend/app/calculation/modules/`). Generated from the registered calculation modules — when a module changes, regenerate this document.

> **Status of every module: NOT PRODUCTION READY.** Each module runs in development and testing; in production it is blocked until a methodology expert has checked it against the official methodology text and the readiness is approved on the version's Calculation tab (ms1 *Request production readiness* → ms2 *Approve*). Interpretations the code makes are listed under each module for that review.
>
> **Readiness is approved for one module code version** (since 29 Oct 2026, migration 0024): the approval records the module's
> version (e.g. VM0042 `1.2.0`) in `methodology_versions.calculation_readiness_module_version`, and the version counts as
> production-ready only while the registered module has exactly that version. A module code change (1.2.0 → 1.3.0) makes it
> NOT_PRODUCTION_READY until readiness is requested and approved again. Approvals made before 0024 recorded no module version: the
> migration reset them to NOT_PRODUCTION_READY. Approval also needs the version to be still APPROVED (`READINESS_NOT_APPLICABLE`).

## Contents
1. [How methodologies work in the platform](#1-how-methodologies-work-in-the-platform)
2. [Overview of all methodologies](#2-overview-of-all-methodologies)
3. [Which methodology for which project](#3-which-methodology-for-which-project)
4. [VM0042 2.2 — VM0042-V2.2-QA2-QA3](#4-vm0042-22--vm0042-v22-qa2-qa3)
5. [GS402 1.0 — GS402-ZT-A1](#5-gs402-10--gs402-zt-a1)
6. [GS402 1.0 — GS402-IT-A1](#6-gs402-10--gs402-it-a1)
7. [GS402 1.0 — GS402-IT-A3](#7-gs402-10--gs402-it-a3)
8. [GS402 1.0 — GS402-CC-A1](#8-gs402-10--gs402-cc-a1)
9. [GS402 1.0 — GS402-CC-A3](#9-gs402-10--gs402-cc-a3)
10. [VM0047 1.1 — VM0047-V1.1-CENSUS](#10-vm0047-11--vm0047-v11-census)
11. [VM0044 1.2 — VM0044-V1.2](#11-vm0044-12--vm0044-v12)
12. [BM-FR05.002 1.0 — CCTS-FR05.002](#12-bm-fr05002-10--ccts-fr05002)
13. [BM-FR05.001 1.0 — CCTS-FR05.001](#13-bm-fr05001-10--ccts-fr05001)
14. [VM0051 1.1 — VM0051-V1.1-QA3](#14-vm0051-11--vm0051-v11-qa3)
15. [BM-AG04.002 1.0 — CCTS-AG04.002](#15-bm-ag04002-10--ccts-ag04002)
16. [GS403 2.1 — GS403-V2.1](#16-gs403-21--gs403-v21)

---

## 1. How methodologies work in the platform

### 1.1 Methodology, version, module
| Item | What it is | Where |
|---|---|---|
| **Methodology** | Code (e.g. `VM0042`), name, one standard, the activities it covers | Methodologies → Add a methodology |
| **Version** | Label (e.g. `2.2`), effective dates, source; status Draft → In review → Approved (→ Superseded / Retired). A version locked by a non-closed project cannot be retired (`VERSION_IN_USE`); supersede it instead | Methodology → New draft version |
| **Calculation module** | The code that implements the version's equations; one per version, chosen while the version is a Draft | Version → Calculation tab |
| **Project lock** | A project is evaluated, recommended and confirmed on exactly one approved version; that version is locked | Project → Methodology tab |

**Who manages the catalog:** creating, editing, submitting, approving, retiring versions and deciding readiness need a
**platform-wide** grant of `methodologies.manage` / `methodologies.approve` (the Methodology Specialist role); an
organization-scoped grant of the same permission is refused, and a DEMO account never changes a LIVE entry (or the reverse;
`ENVIRONMENT_MISMATCH`).

**Matching rule:** a module is offered only when the methodology **code is exactly** the module's code and the **version label is the module's label or that label plus a suffix** (`1.0`, `1.0-IT-A3`, `2.2-02`). This lets one official version (e.g. GS402 1.0) be set up once per module.

### 1.2 The four kinds of methodology rules
| Rule kind | Who writes it | What it does | Shipped with the module? |
|---|---|---|---|
| **Applicability rules** | Methodology specialist, from the official text | Decide whether a project is eligible: each rule tests a project or farm *fact* (e.g. `standard_code`, `activity_code`, `proposed_practice_categories`, `land_use_current`, `project_start_date`) with an operator (EQUALS, IN, ANY_IN, GTE, DATE_ON_OR_AFTER, EXISTS …). Result: Applicable / Evidence required / Needs information / Not applicable | **No** — never invented by the platform |
| **Monitoring rules** | Added by the module (or the specialist) | The data the project must collect: code, unit, level (sampling point / farm / stratum / project), measurement source (LABORATORY / FIELD / FIELD_ACTIVITY), frequency, source reference. They become the MRV plan's measurements | **Yes** |
| **Calculation rules** | Added by the module | The calculation steps BASELINE → PROJECT → EMISSIONS → REMOVALS → LEAKAGE → UNCERTAINTY → ADJUSTMENT → NET, each with its equation reference | **Yes** (replace the draft's) |
| **General rules** | Module (`MODULE-SAMPLING`) or specialist | Sampling requirements (quantification approach, minimum samples per stratum, statistical design, core details, reference depth), crediting period limits, etc. | **Yes** for sampling, where the module needs it |

### 1.3 From rules to credits
1. The **module's monitoring rules** become the **MRV plan measurements** — the Monitoring data screen and the laboratory offer exactly these.
2. The **sampling rule** is enforced on strata, sampling designs and field records.
3. At **Check readiness & freeze inputs**, the module reads its **inputs** (below) from the approved dataset(s); required inputs that are missing block the run; optional ones count as zero.
4. **Execute** runs the calculation rules in order and writes every **output** with its rule, equation reference and lineage.
5. The final output is a **calculated quantity**, not a credit: it still goes through calculation QA, VVB verification and registry issuance.

### 1.4 Input sources
| Source | Meaning |
|---|---|
| Laboratory result | An **approved** laboratory result for the rule, per sample (CURRENT = the period calculated, PREVIOUS = the earlier approved period) |
| Monitoring data | A record on the Monitoring data tab, at the rule's level |
| Stratum area | The stratum's area measured by SQL Server from the farm boundaries |
| Stratum characteristic | A characteristic recorded on the stratum (e.g. `PRECIPITATION_MM`) |
| Sampling design | A parameter of the approved sampling design |

---

## 2. Overview of all methodologies
| # | Standard | Methodology code | Version label | Module code | Name | Soil sampling + lab | Final output |
|---|---|---|---|---|---|---|---|
| 1 | Verra (VCS) | `VM0042` | `2.2` | `VM0042-V2.2-QA2-QA3` | Improved Agricultural Land Management | Yes | `VCU_TOTAL` |
| 2 | Gold Standard | `GS402` | `1.0` | `GS402-ZT-A1` | Soil Organic Carbon Framework + 402.4 Zero Tillage, Approach 1 | Yes | `GS_VER_TOTAL` |
| 3 | Gold Standard | `GS402` | `1.0` | `GS402-IT-A1` | Soil Organic Carbon Framework + 402.1 Improved Tillage, Approach 1 | Yes | `GS_VER_TOTAL` |
| 4 | Gold Standard | `GS402` | `1.0` | `GS402-IT-A3` | Soil Organic Carbon Framework + 402.1 Improved Tillage, Approach 3 | No | `GS_VER_TOTAL` |
| 5 | Gold Standard | `GS402` | `1.0` | `GS402-CC-A1` | Soil Organic Carbon Framework + 402.6 Cover Crops, Approach 1 | Yes | `GS_VER_TOTAL` |
| 6 | Gold Standard | `GS402` | `1.0` | `GS402-CC-A3` | Soil Organic Carbon Framework + 402.6 Cover Crops, Approach 3.1 | No | `GS_VER_TOTAL` |
| 7 | Verra (VCS) | `VM0047` | `1.1` | `VM0047-V1.1-CENSUS` | Afforestation, Reforestation and Revegetation — census-based approach | No soil sampling | `VCU_TOTAL` |
| 8 | Verra (VCS) | `VM0044` | `1.2` | `VM0044-V1.2` | Biochar Utilization in Soil and Non-Soil Applications | Laboratory results of the biochar (carbon content, H:C ratio) entered as values | `VCU_TOTAL` |
| 9 | India CCTS | `BM-FR05.002` | `1.0` | `CCTS-FR05.002` | BM FR05.002 — Afforestation / reforestation of lands except wetlands | No soil sampling | `LCCC` |
| 10 | India CCTS | `BM-FR05.001` | `1.0` | `CCTS-FR05.001` | BM FR05.001 — Afforestation / reforestation of degraded mangrove habitats | No soil sampling | `LCCC` |
| 11 | Verra (VCS) | `VM0051` | `1.1` | `VM0051-V1.1-QA3` | Improved Management in Rice Production Systems — Quantification Approach 3 | No | `CREDITS` |
| 12 | India CCTS | `BM-AG04.002` | `1.0` | `CCTS-AG04.002` | BM AG04.002 — Improved rice management, IPCC default-value approach | No | `CREDITS` |
| 13 | Gold Standard | `GS403` | `2.1` | `GS403-V2.1` | GS 403 Afforestation / Reforestation v2.1 | No soil sampling | `GSVER_PROJECT` |

## 3. Which methodology for which project
| Your project | Methodology / module |
|---|---|
| Cropland practice change, soil sampling possible, control farms available | **VM0042 2.2** |
| Cropland practice change, soil sampling possible, no control farms | **GS402 1.0 — ZT-A1 / IT-A1 / CC-A1** |
| Cropland practice change, no soil sampling (smallholders, pilot) | **GS402 1.0 — IT-A3 / CC-A3** |
| Paddy rice — water saving, straw management (voluntary market) | **VM0051 1.1** |
| Paddy rice — India compliance market (CCTS) | **BM-AG04.002 1.0** |
| Trees on farmland, at most 50 per hectare | **VM0047 1.1** |
| Plantation / reforestation — Gold Standard | **GS403 2.1** |
| Plantation / reforestation — India CCTS | **BM-FR05.002 1.0** |
| Mangrove restoration — India CCTS | **BM-FR05.001 1.0** |
| Biochar from crop residue / biomass | **VM0044 1.2** |

One project uses **one** methodology version for its whole life. Different activities (e.g. rice and dry cropland) are separate projects.

---

## 4. VM0042 2.2 — VM0042-V2.2-QA2-QA3

| | |
|---|---|
| Standard | Verra (VCS) |
| Methodology | Improved Agricultural Land Management |
| Methodology code / version label to create | `VM0042` / `2.2` (or `2.2-<suffix>`) |
| Calculation module | `VM0042-V2.2-QA2-QA3` · module version 1.4.0 |
| Option text on the Calculation tab | VM0042 v2.2 - SOC measure & remeasure (QA2) + default-factor emissions (QA3) |
| Suitable for | Cropland practice change — reduced / zero tillage, stopping residue burning, cover crops, nutrient management — with soil carbon measured twice and compared with control sites. |
| Field / laboratory work | Yes — two sampling rounds, two depth layers, laboratory OC and soil mass; at least 3 control sites |
| Readiness | Not Production Ready |

### 4.1 Sampling rule (`MODULE-SAMPLING`)
| Parameter | Value | Effect in the platform |
|---|---|---|
| `quantification_approach` | `MEASURE_AND_REMEASURE` | The MRV plan's approach is set to this value; any other choice is refused |
| `min_samples_per_stratum` | `3` | Every stratum in a sampling design needs at least this many points |
| `core_details_required` | `True` | Probe diameter and number of cores are mandatory on every field record |
| `statistical_design` | `STRATIFIED_RANDOM` | The sampling design must use this design |

### 4.2 Monitoring rules — the data the project collects (16)
The last three rules (`V42_OA_IMPORTED`, `V42_OA_CARBON`, `V42_WOODY`) were added in module 1.1.0. A version gets them when the module is
chosen on its Calculation tab; a version approved earlier (for example the first VM0042 2.2 set-up) keeps 13 rules and calculates as
before (zero leakage, no woody-biomass check). To use them, create a new draft version (e.g. `2.2-02`), choose the module, and approve it.

| Code | What to record | Unit | Level | Source | Frequency | Methodology reference |
|---|---|---|---|---|---|---|
| `V42_OC` | Soil organic carbon content (per depth increment) | g/kg | Sampling point | Laboratory | Each sampling campaign | VM0042 v2.2 §8.2.1.4, Eq. 3 OC |
| `V42_SOIL_MASS` | Dry fine-earth soil mass of the sample (per depth increment, > 2 mm excluded) | g | Sampling point | Laboratory | Each sampling campaign | VM0042 v2.2 §8.2.1.3 (4), §8.2.1.6 Eq. 3 M_sample |
| `V42_FSN` | Synthetic fertiliser N applied | kg N | Farm | Field activity | Per year (baseline t=-1..-3 and each project year) | VM0042 v2.2 Eq. 19 FSN |
| `V42_FON` | Organic fertiliser N applied | kg N | Farm | Field activity | Per year (baseline t=-1..-3 and each project year) | VM0042 v2.2 Eq. 20 FON |
| `V42_DIESEL` | Diesel consumed | L | Farm | Field activity | Per year (baseline t=-1..-3 and each project year) | VM0042 v2.2 Eq. 7 FFC (diesel) |
| `V42_GASOLINE` | Gasoline consumed | L | Farm | Field activity | Per year (baseline t=-1..-3 and each project year) | VM0042 v2.2 Eq. 7 FFC (gasoline) |
| `V42_LIMESTONE` | Calcitic limestone applied | t | Farm | Field activity | Per year (baseline t=-1..-3 and each project year) | VM0042 v2.2 Eq. 9 M_Limestone |
| `V42_DOLOMITE` | Dolomite applied | t | Farm | Field activity | Per year (baseline t=-1..-3 and each project year) | VM0042 v2.2 Eq. 9 M_Dolomite |
| `V42_BURN_RICE` | Rice residues burned (dry matter) | kg d.m. | Farm | Field activity | Per year (baseline t=-1..-3 and each project year) | VM0042 v2.2 Eqs. 14/32 MB (rice) |
| `V42_BURN_WHEAT` | Wheat residues burned (dry matter) | kg d.m. | Farm | Field activity | Per year (baseline t=-1..-3 and each project year) | VM0042 v2.2 Eqs. 14/32 MB (wheat) |
| `V42_BURN_OTHER` | Other crop residues burned (dry matter) | kg d.m. | Farm | Field activity | Per year (baseline t=-1..-3 and each project year) | VM0042 v2.2 Eqs. 14/32 MB (maize, sugarcane, other) |
| `V42_IRRIGATION` | Irrigation type (NONE / DRIP / OTHER) | — | Farm | Field activity | Per year | VM0042 v2.2 Eq. 23 FracLEACH; IPCC 2019 Vol. 4 Ch. 11 Tier 1 note |
| `V42_NPR` | AFOLU non-permanence risk rating | % | Project | Field activity | Per year (baseline t=-1..-3 and each project year) | VM0042 v2.2 §8.7 NPR%; VCS AFOLU Non-Permanence Risk Tool |
| `V42_OA_IMPORTED` | Manure, compost or biosolids brought in from outside the project area and applied (not exempt; 0 when none) | t | Farm | Field activity | Per project year | VM0042 v2.2 §8.4.1, Eq. 33 M_OA |
| `V42_OA_CARBON` | Carbon content of the imported amendment (one mass-weighted value per farm and period, e.g. 0.15) | t C/t | Farm | Field activity | Per project year, when an amendment is brought in | VM0042 v2.2 §8.4.1, Eq. 33 CC_OA |
| `V42_WOODY` | Woody biomass removed in the period: NO (no shade tree cut, no coffee uprooted) · NONE (no woody plants) · YES | — | Farm | Field activity | Each reporting period | VM0042 v2.2 Eqs. 48-51, Q1 condition |

Exempt from `V42_OA_IMPORTED` (§8.4.1 cases 1–3): amendments made on farms in the project area (e.g. compost an estate makes from its own
coffee pulp), manure diverted from an uncontrolled anaerobic lagoon, pond, tank or pit, and amendments not previously used as a soil amendment.

### 4.3 Calculation rules — the steps (8)
| # | Code | Step | What it calculates | Equation reference |
|---|---|---|---|---|
| 1 | `V42-BSL` | BASELINE | Baseline: control-site SOC stocks (ESM) and baseline emissions | VM0042 v2.2 Eq. 3, §8.2.1.6, Eq. 46; Eqs. 6-9, 14, 16-23, 32 |
| 2 | `V42-PRJ` | PROJECT | Project: project-strata SOC stocks (ESM) and project emissions | VM0042 v2.2 Eq. 3, §8.2.1.6, Eq. 47; §8.3 |
| 3 | `V42-ER` | EMISSIONS | Emission reductions per source (fuel, liming, N2O, biomass burning) | VM0042 v2.2 Eqs. 52, 53, 57, 58, 59 |
| 4 | `V42-CR` | REMOVALS | SOC stock change, project and baseline (t CO2e) | VM0042 v2.2 Eqs. 46, 47 (x 44/12) |
| 5 | `V42-LK` | LEAKAGE | Leakage: imported organic amendments (8.4.1); 8.4.2-8.4.4 not applicable | VM0042 v2.2 §8.4, Eqs. 33, 39, 42 |
| 6 | `V42-UNC` | UNCERTAINTY | Approach 2 sampling uncertainty deduction | VM0042 v2.2 Eqs. 70, 71, 74 |
| 7 | `V42-ADJ` | ADJUSTMENT | Uncertainty applied to stock changes; non-permanence buffer | VM0042 v2.2 Eqs. 44, 45, 75, 76 |
| 8 | `V42-NET` | NET | Net reductions and removals; VCUs (whole tonnes, rounded down) | VM0042 v2.2 Eqs. 37-43, 77-79 |

### 4.4 Calculation inputs (20)
| Input | Comes from | Rule / parameter | Unit | Level | Round | Required |
|---|---|---|---|---|---|---|
| `OC_T` | Laboratory result | V42_OC | g/kg | Sampling point | period calculated | **Yes** |
| `MASS_T` | Laboratory result | V42_SOIL_MASS | g | Sampling point | period calculated | **Yes** |
| `OC_T0` | Laboratory result | V42_OC | g/kg | Sampling point | previous round | **Yes** |
| `MASS_T0` | Laboratory result | V42_SOIL_MASS | g | Sampling point | previous round | **Yes** |
| `AREA` | Stratum area (SQL Server) | — | ha | Stratum | period calculated | **Yes** |
| `PRECIP` | Stratum characteristic | PRECIPITATION_MM | mm | Stratum | period calculated | **Yes** — every project stratum and every farm with activity records |
| `FSN` | Monitoring data | V42_FSN | kg N | Farm | period calculated | No (0 if missing) |
| `FON` | Monitoring data | V42_FON | kg N | Farm | period calculated | No (0 if missing) |
| `DIESEL` | Monitoring data | V42_DIESEL | L | Farm | period calculated | No (0 if missing) |
| `GASOLINE` | Monitoring data | V42_GASOLINE | L | Farm | period calculated | No (0 if missing) |
| `LIMESTONE` | Monitoring data | V42_LIMESTONE | t | Farm | period calculated | No (0 if missing) |
| `DOLOMITE` | Monitoring data | V42_DOLOMITE | t | Farm | period calculated | No (0 if missing) |
| `BURN_RICE` | Monitoring data | V42_BURN_RICE | kg d.m. | Farm | period calculated | No (0 if missing) |
| `BURN_WHEAT` | Monitoring data | V42_BURN_WHEAT | kg d.m. | Farm | period calculated | No (0 if missing) |
| `BURN_OTHER` | Monitoring data | V42_BURN_OTHER | kg d.m. | Farm | period calculated | No (0 if missing) |
| `IRRIGATION` | Monitoring data | V42_IRRIGATION | — | Farm | period calculated | No (0 if missing) |
| `NPR` | Monitoring data | V42_NPR | % | Project | period calculated | **Yes** — 0 to 100; buffer uses at least 12; above 60 blocks |
| `OA_MASS` | Monitoring data | V42_OA_IMPORTED | t | Farm | period calculated | No — only on versions with the rule |
| `OA_CC` | Monitoring data | V42_OA_CARBON | t C/t | Farm | period calculated | **Yes** for a farm with imported mass above 0 (exactly one, above 0 and at most 1) |
| `WOODY` | Monitoring data | V42_WOODY | — | Farm | period calculated | **Yes** for every project farm, on versions with the rule (NO / NONE; YES blocks) |

The farm activity inputs (`FSN` … `BURN_OTHER`) are optional per source, but a farm with **baseline** records for a source must also have a
record in the reporting period (enter `0` when the source was not used); otherwise the run is blocked (`PERIOD_RECORD_MISSING`).

### 4.5 Constants built into the module (26)
| Constant | Value | Unit | Source |
|---|---|---|---|
| `C_TO_CO2` | 3.66667 | t CO2/t C | 44/12 (VM0042 v2.2 §8.5.1) |
| `N2ON_TO_N2O` | 1.57143 | t N2O/t N2O-N | 44/28 (VM0042 v2.2 Eqs. 18, 22, 23) |
| `GWP_CH4` | 28 | t CO2e/t CH4 | VCS Standard v5.0 §3.14.4 Table 9 (IPCC AR5) |
| `GWP_N2O` | 265 | t CO2e/t N2O | VCS Standard v5.0 §3.14.4 Table 9 (IPCC AR5) |
| `EF_DIESEL` | 0.002886 | t CO2e/L | VM0042 v2.2 parameter EF_CO2,j (diesel) |
| `EF_GASOLINE` | 0.002810 | t CO2e/L | VM0042 v2.2 parameter EF_CO2,j (gasoline) |
| `EF_LIMESTONE` | 0.12 | t C/t | VM0042 v2.2 Eq. 9 |
| `EF_DOLOMITE` | 0.13 | t C/t | VM0042 v2.2 Eq. 9 |
| `EF1_WET_SYN` | 0.016 | kg N2O-N/kg N | IPCC 2019 Refinement Vol. 4 Ch. 11 Table 11.1 (wet climate, synthetic) |
| `EF1_WET_OTHER` | 0.006 | kg N2O-N/kg N | IPCC 2019 Refinement Vol. 4 Ch. 11 Table 11.1 (wet climate, other N inputs) |
| `EF1_DRY` | 0.005 | kg N2O-N/kg N | IPCC 2019 Refinement Vol. 4 Ch. 11 Table 11.1 (dry climate, all N inputs) |
| `EF4_WET` | 0.014 | kg N2O-N/kg N volatilised | IPCC 2019 Refinement Vol. 4 Ch. 11 Table 11.3 (wet climate) |
| `EF4_DRY` | 0.005 | kg N2O-N/kg N volatilised | IPCC 2019 Refinement Vol. 4 Ch. 11 Table 11.3 (dry climate) |
| `EF5` | 0.011 | kg N2O-N/kg N leached | IPCC 2019 Refinement Vol. 4 Ch. 11 Table 11.3 |
| `FRAC_GASF` | 0.11 | fraction | IPCC 2019 Refinement Vol. 4 Ch. 11 Table 11.3 (aggregated synthetic) |
| `FRAC_GASM` | 0.21 | fraction | IPCC 2019 Refinement Vol. 4 Ch. 11 Table 11.3 |
| `FRAC_LEACH` | 0.24 | fraction | IPCC 2019 Refinement Vol. 4 Ch. 11 Table 11.3 FracLEACH-(H); 0 in dry climates without non-drip irrigation |
| `WET_PRECIP_MM` | 1000 | mm | IPCC 2019 Refinement Vol. 4 Ch. 11 Table 11.1 note 4 (tropical: wet if annual precipitation > 1000 mm) |
| `EF_BB_CH4` | 2.7 | g CH4/kg d.m. burnt | IPCC 2019 Refinement Vol. 4 Ch. 2 Table 2.5 (agricultural residues) |
| `EF_BB_N2O` | 0.07 | g N2O/kg d.m. burnt | IPCC 2019 Refinement Vol. 4 Ch. 2 Table 2.5 (agricultural residues) |
| `CF_RICE` | 0.80 | fraction | IPCC 2019 Refinement Vol. 4 Ch. 2 Table 2.6 (rice residues) |
| `CF_WHEAT` | 0.90 | fraction | IPCC 2019 Refinement Vol. 4 Ch. 2 Table 2.6 (wheat residues) |
| `CF_OTHER` | 0.80 | fraction | IPCC 2019 Refinement Vol. 4 Ch. 2 Table 2.6 (maize/sugarcane 0.80; conservative for other crops) |
| `NPR_MIN` | 12 | % | VCS AFOLU Non-Permanence Risk Procedure v5.0 §2.5.2 (minimum risk rating) |
| `NPR_MAX` | 60 | % | VCS AFOLU Non-Permanence Risk Procedure v5.0 §2.5.3 (above 60 the project fails the risk analysis) |
| `OA_C_RETENTION` | 0.12 | fraction | VM0042 v2.2 Eq. 33 (manure carbon retained in soil; Maillard and Angers 2014) |

### 4.6 Outputs
Outputs written by this module's code (some appear only for the approach or activity module in use; `<stratum>` = one output per stratum).

| Output | Step |
|---|---|
| `REF_MASS_<stratum>` | BASELINE |
| `ER_<stratum>` | EMISSIONS |
| `ER_SOURCES` | EMISSIONS |
| `LK_OA` | LEAKAGE (Eq. 33; only on versions with the V42_OA_* rules) |
| `LK_TOTAL` | LEAKAGE |
| `UNC_VARIANCE` | UNCERTAINTY |
| `UNC_DF` | UNCERTAINTY |
| `UNC_T` | UNCERTAINTY |
| `UNC_PCT` | UNCERTAINTY |
| `DCO2_WP_ADJ` | ADJUSTMENT |
| `DCO2_BSL_ADJ` | ADJUSTMENT |
| `NPR_RATED` | ADJUSTMENT (rating as recorded) |
| `NPR_PCT` | ADJUSTMENT (rating applied to the buffer, at least 12) |
| `BUFFER_ER` | ADJUSTMENT |
| `BUFFER_CR` | ADJUSTMENT |
| `ER_T` | NET |
| `CR_T` | NET |
| `ER_NET` | NET |
| `CR_NET` | NET |
| `VCU_ER` | NET |
| `VCU_CR` | NET |
| `REVERSAL` | NET |
| `VCU_TOTAL` | NET |

### 4.7 Interpretations made by the code (for the expert review)
- Q2: the Eq. 74 uncertainty (%) is divided by 100 before Eqs. 37/44/45 (dimensional consistency; VCS MR v5.0 §2.4).
- Q3: buffer deposits are never negative; a negative net carbon-stock benefit is a reversal (VCS Standard v5.0 §3.2.21-3.2.23) reported as REVERSAL with zero VCUs.
- Q5: t = one-sided Student-t at 66.67 % with Welch-Satterthwaite degrees of freedom (Verra SSA Handbook draft v1.0).
- Q6: UNC uses the absolute mean change and is capped at 100 %.
- Q7/Q8: stratified estimator; independent sampling - variance of a change = sum of the two snapshot variances; control sites use the same estimator.
- Q11/Q13: IPCC 2019 Tier 1 factors by climate (tropical wet if precipitation > 1000 mm); FracLEACH 0 in dry climates unless irrigation other than drip. Precipitation is required for every project stratum and for every farm with activity records; a missing value blocks the run (dry factors are not assumed).
- Q12: equivalent mineral soil mass (SOM = SOC/0.58); linear interpolation with 2 depth increments, cubic spline with 3 or more; reference mass = mean cumulative mineral mass to 30 cm at the linked control sites in the earlier campaign of the comparison.
- Q14: AR5 GWPs (CH4 28, N2O 265).
- Q16: VCUs are whole tonnes rounded down.
- Cumulative project stock change for the I(dCO2_wp) switch is taken as the change since the earlier campaign of this comparison (equal to the change since the project start at the first verification).
- Baseline emissions per farm = mean annual activity of the BASELINE-phase records (t=-1..-3) x years in the reporting period; project emissions = PROJECT/MONITORING-phase records observed in the reporting period. A farm and source with baseline records but no record in the reporting period blocks the run (a missing record is never read as zero, which would credit a cut that was not monitored); record 0 when the source was not used.
- Buffer: the AFOLU non-permanence risk rating is applied as max(rating, 12) (NPR Procedure v5.0 §2.5.2); a rating above 60 blocks the run (§2.5.3), as does a rating below 0 or above 100.
- Leakage 8.4.1 (Eq. 33): LE_OA = sum over farms of imported mass (t) x carbon content (t C/t) x 0.12 x 44/12, from the V42_OA_IMPORTED records of the reporting period. The whole imported mass is counted, also when only part of it is additional to the look-back (conservative). Exempt amendments (8.4.1 cases 1-3) are not recorded under V42_OA_IMPORTED. A farm with imported mass needs exactly one carbon content for the period. A farm whose organic fertiliser N (V42_FON) in the reporting period is above its look-back annual mean x years needs a V42_OA_IMPORTED record for the period (0 when the amendment was made on the farm), else the run is blocked. Versions set up before these rules existed report zero leakage.
- Woody biomass (Eqs. 48-51) is not quantified, so it may be left out only while it does not decrease: when the version carries V42_WOODY, every project farm needs a NO or NONE declaration for the period, and YES (shade trees cut or perennial crops uprooted) blocks the run.
- Out of scope and treated as not applicable / zero (Q1 condition): enteric, manure, N-fixing species, woody biomass, leakage 8.4.2-8.4.4.
- Eqs. 46/47 (x 1/x): the SOC change between the two campaigns is credited whole to this reporting period (the annual rate x 1/x times the x years between the campaigns), while emissions are annual baseline means x the years of this period. The two only describe the same span when the earlier campaign closes the immediately preceding period: an earlier approved period that ends more than one day before this period starts (a gap, e.g. an intervening period without an approved dataset) blocks the run (PREVIOUS_PERIOD_NOT_ADJACENT), so a multi-period SOC change is never credited against one period's emissions.
- Vintages (Q16): the result of the reporting period is quantified and rounded down once for the whole period; the split by calendar-year vintage is not made by the module (the registry states the vintages of what it issues).
- Eqs. 44/45: one sign indicator I(dCO2_soil) is taken from the net SOC change (project minus baseline) and the same factor (1 - UNC x I) is applied to the project and the baseline stock change.
- Control sites linked to more than one project stratum enter the baseline of each of those strata; the covariance this creates between strata is ignored in the Eq. 70/71 variance (strata are treated as independent).
- Activity records need an observed-on date: BASELINE records are grouped by calendar year for the look-back mean, project records count only when dated inside the reporting period; an undated record blocks the run (MISSING_OBSERVED_ON). Irrigation type is read per phase: the baseline uses the look-back (BASELINE) records - leaching applies only when all of them are OTHER - and the project uses the reporting period's records (any OTHER applies leaching); a farm with look-back irrigation records needs one for the period.
- Each sample has exactly one approved organic carbon and one soil mass result, and each field collection one sample per depth increment; duplicates or a result without its partner block the run (DUPLICATE_LAB_RESULT / MASS_RESULT_MISSING).
- Per-stratum outputs are named by the stratum code (e.g. REF_MASS_S1), or by a collision-free prefix of the stratum record id when the code is not available.

### 4.8 Reasons the calculation can be blocked
`CONTROL_SITES_REQUIRED`, `CONTROL_SITE_REQUIRED`, `DEPTH_INCREMENTS_REQUIRED`, `INSUFFICIENT_SAMPLES`, `INVALID_INPUT` (risk rating outside 0–100; carbon content not one value between 0 and 1; woody answer not NO / NONE / YES), `INVALID_SOIL_PROFILE`, `MISSING_REQUIRED_INPUT` (including `PERIOD_RECORD_MISSING`, `PRECIPITATION_MISSING`, `OA_CARBON_MISSING` and `WOODY_DECLARATION_MISSING`), `NPR_UNACCEPTABLE` (risk rating above 60), `SAMPLING_DEPTH_INSUFFICIENT` (a core sampled to less than 30 cm, or holding less soil than the stratum's reference soil mass: never extrapolated), `WOODY_BIOMASS_REMOVED` (shade trees cut or perennial crops uprooted). Added 29/10: `DUPLICATE_LAB_RESULT` (two approved results of one kind for a sample, or two samples for one depth increment), `MASS_RESULT_MISSING` (an organic carbon result without its soil mass), `MISSING_OBSERVED_ON` (an undated activity record), `PREVIOUS_PERIOD_NOT_ADJACENT` (the earlier campaign's period does not end the day before this period starts).

---

## 5. GS402 1.0 — GS402-ZT-A1

| | |
|---|---|
| Standard | Gold Standard |
| Methodology | Soil Organic Carbon Framework + 402.4 Zero Tillage, Approach 1 |
| Methodology code / version label to create | `GS402` / `1.0` (or `1.0-<suffix>`) |
| Calculation module | `GS402-ZT-A1` · module version 1.1.0 |
| Option text on the Calculation tab | GS 402 + 402.4 Zero Tillage - Approach 1 (SOC measured to 50 cm, equivalent soil mass) |
| Suitable for | Switch to zero tillage; soil carbon measured to 50 cm (equivalent soil mass); no control sites. |
| Field / laboratory work | Yes — two sampling rounds, laboratory OC and soil mass |
| Readiness | Not Production Ready |

### 5.1 Sampling rule (`MODULE-SAMPLING`)
| Parameter | Value | Effect in the platform |
|---|---|---|
| `quantification_approach` | `MEASURE_AND_REMEASURE` | The MRV plan's approach is set to this value; any other choice is refused |
| `min_samples_per_stratum` | `3` | Every stratum in a sampling design needs at least this many points |
| `core_details_required` | `True` | Probe diameter and number of cores are mandatory on every field record |
| `reference_depth_cm` | `50` | Soil carbon compared on an equivalent soil mass to this depth |
| `statistical_design` | `STRATIFIED_RANDOM` | The sampling design must use this design |

### 5.2 Monitoring rules — the data the project collects (13)
| Code | What to record | Unit | Level | Source | Frequency | Methodology reference |
|---|---|---|---|---|---|---|
| `GS_OC` | Soil organic carbon content (per depth increment) | g/kg | Sampling point | Laboratory | Project start and each performance certification | GS 402 v1.0 §5.1 Approach 1, Annex 1 |
| `GS_SOIL_MASS` | Dry fine-earth soil mass of the sample (per depth increment, > 2 mm excluded) | g | Sampling point | Laboratory | Project start and each performance certification | 402.4 / 402.6 §5.2.1(e) / §6.2: equivalent mass basis |
| `GS_FERT_N` | Nitrogen fertiliser applied (synthetic and organic) | kg N | Farm | Field activity | Per year (5 baseline years before the project start and each project year) | GS 402 Eq. 13 FE; 402.4/402.6 Eq. 2 |
| `GS_DIESEL` | Diesel used by machinery | L | Farm | Field activity | Per year (5 baseline years before the project start and each project year) | GS 402 Eq. 15 FUL; 402.4/402.6 Eq. 4 |
| `GS_GASOLINE` | Gasoline used by machinery | L | Farm | Field activity | Per year (5 baseline years before the project start and each project year) | GS 402 Eq. 15 FUL; 402.4/402.6 Eq. 4 |
| `GS_ELECTRICITY` | Electricity used (grid or captive; on-site fossil generation is fuel) | kWh | Farm | Field activity | Per year (5 baseline years before the project start and each project year) | GS 402 Eq. 16 EUW; 402.4/402.6 Eq. 5 |
| `GS_AGROCHEM` | Other agrochemical emissions (sum of quantity x supplier emission factor per product) | t CO2e | Farm | Field activity | Per year (5 baseline years before the project start and each project year) | GS 402 Eqs. 17/18; 402.4/402.6 Eqs. 6/7 (AQ x AEF) |
| `GS_FEF_DIESEL` | Emission factor of diesel | t CO2e/L | Project | Field activity | Project start; reviewed annually | GS 402 Eq. 15 FEF; national GHG inventory, otherwise IPCC 2006 Vol. 2 Ch. 3 Table 3.3.1 |
| `GS_FEF_GASOLINE` | Emission factor of gasoline | t CO2e/L | Project | Field activity | Project start; reviewed annually | GS 402 Eq. 15 FEF; national GHG inventory, otherwise IPCC 2006 Vol. 2 Ch. 3 Table 3.3.1 |
| `GS_EEF` | Emission factor of the electricity used | t CO2e/kWh | Project | Field activity | Project start; reviewed annually | GS 402 Eq. 16 EEF; 402.4: grid - CDM TOOL05 |
| `GS_YIELD` | Crop yield | kg/ha | Farm | Field activity | Per year (5 baseline years before the project start and each project year) | GS 402 Eq. 19 CY; 402.4 Eq. 8; 402.6 Eq. 10 |
| `GS_LK_EF` | Leakage-area emissions per hectare displaced (dBC_LA + dSOC_LA + dFE_LA + dFU_LA) | t CO2e/ha | Project | Field activity | At verification, when the yield fell | GS 402 Eq. 19; 402.4 Eq. 8; 402.6 Eq. 10 |
| `GS_PAA` | Paris Agreement alignment status for 2026+ vintages: YES when approved by Gold Standard | — | Project | Field activity | When approved | GS 119 PAA P&R v1.2 §3.1 |

### 5.3 Calculation rules — the steps (8)
| # | Code | Step | What it calculates | Equation reference |
|---|---|---|---|---|
| 1 | `GS-BSL` | BASELINE | SOC stock at the start of the calculation period (SOC_0) per stratum | GS 402 v1.0 Eqs. 2, 3; Approach 1 on-site measurement (equivalent soil mass) |
| 2 | `GS-PRJ` | PROJECT | SOC stock at the end of the calculation period (SOC_t) per stratum | GS 402 v1.0 Eq. 5; Approach 1 on-site measurement (equivalent soil mass) |
| 3 | `GS-PE` | EMISSIONS | Project emissions: fertiliser N, fuel and electricity, agrochemicals | 402.4 v1.0 Eqs. 1-7 (replace GS 402 Eqs. 12-18) |
| 4 | `GS-DSOC` | REMOVALS | SOC stock change in the calculation period (t C and t CO2e) | GS 402 v1.0 Eqs. 2, 3, 5 (x 44/12, Eq. 1) |
| 5 | `GS-LK` | LEAKAGE | Leakage from a yield reduction (shift of production) | 402.4 v1.0 Eq. 8 |
| 6 | `GS-UNC` | UNCERTAINTY | Uncertainty at 90 % confidence and uncertainty deduction | GS 402 v1.0 Eqs. 7-11, Table 6 |
| 7 | `GS-ADJ` | ADJUSTMENT | Uncertainty deduction applied; Gold Standard compliance buffer | GS 402 v1.0 Eqs. 1, 2; GS GHG ER&S Product Requirements v3.2 §11.1.1 |
| 8 | `GS-NET` | NET | Emission reductions for issuance (GS VERs, whole tonnes rounded down) | GS 402 v1.0 Eq. 1 |

### 5.4 Calculation inputs (16)
| Input | Comes from | Rule / parameter | Unit | Level | Round | Required |
|---|---|---|---|---|---|---|
| `OC_T` | Laboratory result | GS_OC | g/kg | Sampling point | period calculated | **Yes** |
| `MASS_T` | Laboratory result | GS_SOIL_MASS | g | Sampling point | period calculated | **Yes** |
| `OC_T0` | Laboratory result | GS_OC | g/kg | Sampling point | previous round | **Yes** |
| `MASS_T0` | Laboratory result | GS_SOIL_MASS | g | Sampling point | previous round | **Yes** |
| `AREA` | Stratum area (SQL Server) | — | ha | Stratum | period calculated | **Yes** |
| `FERT_N` | Monitoring data | GS_FERT_N | kg N | Farm | period calculated | No (0 if missing) |
| `DIESEL` | Monitoring data | GS_DIESEL | L | Farm | period calculated | No (0 if missing) |
| `GASOLINE` | Monitoring data | GS_GASOLINE | L | Farm | period calculated | No (0 if missing) |
| `ELECTRICITY` | Monitoring data | GS_ELECTRICITY | kWh | Farm | period calculated | No (0 if missing) |
| `AGROCHEM` | Monitoring data | GS_AGROCHEM | t CO2e | Farm | period calculated | No (0 if missing) |
| `FEF_DIESEL` | Monitoring data | GS_FEF_DIESEL | t CO2e/L | Project | period calculated | No (0 if missing) |
| `FEF_GASOLINE` | Monitoring data | GS_FEF_GASOLINE | t CO2e/L | Project | period calculated | No (0 if missing) |
| `EEF` | Monitoring data | GS_EEF | t CO2e/kWh | Project | period calculated | No (0 if missing) |
| `YIELD` | Monitoring data | GS_YIELD | kg/ha | Farm | period calculated | No (0 if missing) |
| `LK_EF` | Monitoring data | GS_LK_EF | t CO2e/ha | Project | period calculated | No (0 if missing) |
| `PAA` | Monitoring data | GS_PAA | — | Project | period calculated | No (0 if missing) |

### 5.5 Constants built into the module (5)
| Constant | Value | Unit | Source |
|---|---|---|---|
| `C_TO_CO2` | 3.66667 | t CO2/t C | 44/12 (GS 402 v1.0 Eq. 1) |
| `EF_FE` | 0.01 | t CO2e/kg N | GS 402 v1.0 Eq. 13 / 402.4 and 402.6 Eq. 2 EF_FE (IPCC 2019 Table 11.1 aggregated), as printed |
| `BUFFER` | 0.20 | fraction | GS GHG ER&S Product Requirements v3.2 §11.1.1 (20 % of sequestration GSVERs) |
| `UNC_THRESHOLD` | 0.20 | fraction | GS 402 v1.0 Eq. 11 (20 % of the mean at 90 % confidence) |
| `BASELINE_CAP` | 0.5 | fraction | GS 402 v1.0 §10: undocumented FE_BL / FU_BL / EU_BL / AE_BL at most 50 % of the project value |

### 5.6 Outputs
Outputs written by this module's code (some appear only for the approach or activity module in use; `<stratum>` = one output per stratum).

| Output | Step |
|---|---|
| `REF_MASS_<stratum>` | BASELINE |
| `SOC_0_<stratum>` | BASELINE |
| `SOC_BL_<stratum>` | BASELINE |
| `SOC_T_<stratum>` | PROJECT |
| `PE_<stratum>` | EMISSIONS |
| `PE_TOTAL` | EMISSIONS |
| `DSOC_C` | REMOVALS |
| `DSOC_CO2` | REMOVALS |
| `LK_DISPLACED_HA` | LEAKAGE |
| `LK_TOTAL` | LEAKAGE |
| `UNC_LOWER_C` | UNCERTAINTY |
| `UNC_UPPER_C` | UNCERTAINTY |
| `UNC` | UNCERTAINTY |
| `UD` | UNCERTAINTY |
| `DC_SOC_ADJ` | ADJUSTMENT |
| `ER_GROSS` | ADJUSTMENT |
| `PAA_BLOCKED_SHARE` | ADJUSTMENT |
| `BUFFER` | ADJUSTMENT |
| `ER_NET` | NET |
| `REVERSAL` | NET |
| `GS_VER_TOTAL` | NET |

### 5.7 Interpretations made by the code (for the expert review)
- Approach 1: SOC_0 = mean stock of the stratum's samples in the earlier approved campaign (the project-start sampling at the first period), SOC_t = in this period's campaign; at least 3 samples per stratum and campaign (Table 6 starts at n = 3).
- Equivalent soil mass: cumulative fine-earth soil mass; reference mass per stratum = mean mass to the reference depth in the earlier campaign; linear interpolation with 2 depth increments, cubic spline with 3 or more (as for VM0042).
- Uncertainty (Eqs. 7-9): per stratum and campaign SE = SD / sqrt(n), t = two-sided 90 % Student-t with n - 1 degrees of freedom (equal to Table 6); Lower = sum of (SOC_t lower - SOC_0 upper) x A, Upper = sum of (SOC_t upper - SOC_0 lower) x A.
- Buffer: 20 % of the GS VERs from SOC sequestration go to the GS Compliance Buffer (GS GHG ER&S Product Requirements v3.2 §11.1.1); the whole net amount is sequestration for these activity modules, so (1 - BUF) applies to all of Eq. 1.
- GWPs: IPCC AR5 (Gold Standard rule update RU-2020-P&R v1.2, from 1 January 2021); EF_FE is used as printed (0.01 t CO2e per kg N), which is more conservative than 0.01 kg N2O-N/kg N x 44/28 x 265.
- Eq. 2: SOC_0 is the stock at the start of the calculation period (the baseline at the first period, the previous SOC_t later).
- Eqs. 10/11: UNC = |Upper - Lower| / (2 x dSOC) as a fraction; UD = UNC - 0.20 when UNC > 0.20 (capped at 1); no deduction otherwise. UNC is 1 when dSOC <= 0, and a SOC loss is used in full (the deduction never reduces a loss).
- Eq. 14: the electricity term is summed over the years like the fuel term (the printed bracket closes early).
- Eqs. 15/16/18: emissions are t CO2e per farm (litres, kWh and kg give t CO2e; the printed 'per ha' is not applied).
- Project emissions per farm and source: project records in the period minus the baseline annual mean (5 baseline years) x years in the period, floored at zero (decreases are never credited). Without baseline records the baseline is 50 % of the project value.
- Leakage: per stratum, max[(CY_BL - CY_t) / CY_BL; 0] x area x leakage-area emissions per ha. CY_min is taken as CY_BL (CY_min can never exceed CY_BL, so this is conservative); yields are the means of the farms' records (baseline years / this period). Yield records are required (no exemption is applied, G8): a stratum without a farm that has both baseline and period yields, or a farm with yields in only one of the two, blocks the run (YIELD_RECORDS_REQUIRED) instead of reading leakage as zero.
- Per-stratum outputs are named by the stratum code, or by a collision-free prefix of the stratum record id when it is not available; each sample has exactly one organic carbon and one soil mass result (duplicates or unpaired results block the run).
- GS VERs are whole tonnes rounded down; a negative result is reported as REVERSAL with zero credits.
- GS 119 v1.2 §3.1: the share of a positive result falling in vintages from 1 January 2026 (by days of the period) is not credited unless GS_PAA = YES (Gold Standard approved the Paris-aligned transition); the buffer applies to the credited share.

### 5.8 Reasons the calculation can be blocked
`DEPTH_INCREMENTS_REQUIRED`, `DUPLICATE_INPUT`, `INSUFFICIENT_SAMPLES`, `INVALID_INPUT`, `INVALID_SOIL_PROFILE`, `MISSING_REQUIRED_INPUT`, `SAMPLING_DEPTH_INSUFFICIENT`. Added 29/10: `DUPLICATE_LAB_RESULT` / `MASS_RESULT_MISSING` (Approach 1), `YIELD_RECORDS_REQUIRED` (a stratum without baseline and period crop yields, or a farm with yields of one phase only).

---

## 6. GS402 1.0 — GS402-IT-A1

| | |
|---|---|
| Standard | Gold Standard |
| Methodology | Soil Organic Carbon Framework + 402.1 Improved Tillage, Approach 1 |
| Methodology code / version label to create | `GS402` / `1.0` (or `1.0-<suffix>`) |
| Calculation module | `GS402-IT-A1` · module version 1.1.0 |
| Option text on the Calculation tab | GS 402 + 402.1 Improved Tillage - Approach 1 (SOC measured, equivalent soil mass to 30 cm) |
| Suitable for | Switch to reduced tillage; soil carbon measured to 30 cm; no control sites. |
| Field / laboratory work | Yes — two sampling rounds, laboratory OC and soil mass |
| Readiness | Not Production Ready |

### 6.1 Sampling rule (`MODULE-SAMPLING`)
| Parameter | Value | Effect in the platform |
|---|---|---|
| `quantification_approach` | `MEASURE_AND_REMEASURE` | The MRV plan's approach is set to this value; any other choice is refused |
| `min_samples_per_stratum` | `3` | Every stratum in a sampling design needs at least this many points |
| `core_details_required` | `True` | Probe diameter and number of cores are mandatory on every field record |
| `reference_depth_cm` | `30` | Soil carbon compared on an equivalent soil mass to this depth |
| `statistical_design` | `STRATIFIED_RANDOM` | The sampling design must use this design |

### 6.2 Monitoring rules — the data the project collects (13)
| Code | What to record | Unit | Level | Source | Frequency | Methodology reference |
|---|---|---|---|---|---|---|
| `GS_OC` | Soil organic carbon content (per depth increment) | g/kg | Sampling point | Laboratory | Project start and each performance certification | GS 402 v1.0 §5.1 Approach 1, Annex 1 |
| `GS_SOIL_MASS` | Dry fine-earth soil mass of the sample (per depth increment, > 2 mm excluded) | g | Sampling point | Laboratory | Project start and each performance certification | 402.4 / 402.6 §5.2.1(e) / §6.2: equivalent mass basis |
| `GS_FERT_N` | Nitrogen fertiliser applied (synthetic and organic) | kg N | Farm | Field activity | Per year (5 baseline years before the project start and each project year) | GS 402 Eq. 13 FE; 402.4/402.6 Eq. 2 |
| `GS_DIESEL` | Diesel used by machinery | L | Farm | Field activity | Per year (5 baseline years before the project start and each project year) | GS 402 Eq. 15 FUL; 402.4/402.6 Eq. 4 |
| `GS_GASOLINE` | Gasoline used by machinery | L | Farm | Field activity | Per year (5 baseline years before the project start and each project year) | GS 402 Eq. 15 FUL; 402.4/402.6 Eq. 4 |
| `GS_ELECTRICITY` | Electricity used (grid or captive; on-site fossil generation is fuel) | kWh | Farm | Field activity | Per year (5 baseline years before the project start and each project year) | GS 402 Eq. 16 EUW; 402.4/402.6 Eq. 5 |
| `GS_AGROCHEM` | Other agrochemical emissions (sum of quantity x supplier emission factor per product) | t CO2e | Farm | Field activity | Per year (5 baseline years before the project start and each project year) | GS 402 Eqs. 17/18; 402.4/402.6 Eqs. 6/7 (AQ x AEF) |
| `GS_FEF_DIESEL` | Emission factor of diesel | t CO2e/L | Project | Field activity | Project start; reviewed annually | GS 402 Eq. 15 FEF; national GHG inventory, otherwise IPCC 2006 Vol. 2 Ch. 3 Table 3.3.1 |
| `GS_FEF_GASOLINE` | Emission factor of gasoline | t CO2e/L | Project | Field activity | Project start; reviewed annually | GS 402 Eq. 15 FEF; national GHG inventory, otherwise IPCC 2006 Vol. 2 Ch. 3 Table 3.3.1 |
| `GS_EEF` | Emission factor of the electricity used | t CO2e/kWh | Project | Field activity | Project start; reviewed annually | GS 402 Eq. 16 EEF; 402.4: grid - CDM TOOL05 |
| `GS_YIELD` | Crop yield | kg/ha | Farm | Field activity | Per year (5 baseline years before the project start and each project year) | GS 402 Eq. 19 CY; 402.4 Eq. 8; 402.6 Eq. 10 |
| `GS_LK_EF` | Leakage-area emissions per hectare displaced (dBC_LA + dSOC_LA + dFE_LA + dFU_LA) | t CO2e/ha | Project | Field activity | At verification, when the yield fell | GS 402 Eq. 19; 402.4 Eq. 8; 402.6 Eq. 10 |
| `GS_PAA` | Paris Agreement alignment status for 2026+ vintages: YES when approved by Gold Standard | — | Project | Field activity | When approved | GS 119 PAA P&R v1.2 §3.1 |

### 6.3 Calculation rules — the steps (8)
| # | Code | Step | What it calculates | Equation reference |
|---|---|---|---|---|
| 1 | `GS-BSL` | BASELINE | SOC stock at the start of the calculation period (SOC_0) per stratum | GS 402 v1.0 Eqs. 2, 3; Approach 1 on-site measurement (equivalent soil mass) |
| 2 | `GS-PRJ` | PROJECT | SOC stock at the end of the calculation period (SOC_t) per stratum | GS 402 v1.0 Eq. 5; Approach 1 on-site measurement (equivalent soil mass) |
| 3 | `GS-PE` | EMISSIONS | Project emissions: fertiliser N, fuel and electricity, agrochemicals | GS 402 v1.0 Eqs. 12-18 |
| 4 | `GS-DSOC` | REMOVALS | SOC stock change in the calculation period (t C and t CO2e) | GS 402 v1.0 Eqs. 2, 3, 5 (x 44/12, Eq. 1) |
| 5 | `GS-LK` | LEAKAGE | Leakage from a yield reduction (shift of production) | GS 402 v1.0 Eq. 19 |
| 6 | `GS-UNC` | UNCERTAINTY | Uncertainty at 90 % confidence and uncertainty deduction | GS 402 v1.0 Eqs. 7-11, Table 6 |
| 7 | `GS-ADJ` | ADJUSTMENT | Uncertainty deduction applied; Gold Standard compliance buffer | GS 402 v1.0 Eqs. 1, 2; GS GHG ER&S Product Requirements v3.2 §11.1.1 |
| 8 | `GS-NET` | NET | Emission reductions for issuance (GS VERs, whole tonnes rounded down) | GS 402 v1.0 Eq. 1 |

### 6.4 Calculation inputs (16)
| Input | Comes from | Rule / parameter | Unit | Level | Round | Required |
|---|---|---|---|---|---|---|
| `OC_T` | Laboratory result | GS_OC | g/kg | Sampling point | period calculated | **Yes** |
| `MASS_T` | Laboratory result | GS_SOIL_MASS | g | Sampling point | period calculated | **Yes** |
| `OC_T0` | Laboratory result | GS_OC | g/kg | Sampling point | previous round | **Yes** |
| `MASS_T0` | Laboratory result | GS_SOIL_MASS | g | Sampling point | previous round | **Yes** |
| `AREA` | Stratum area (SQL Server) | — | ha | Stratum | period calculated | **Yes** |
| `FERT_N` | Monitoring data | GS_FERT_N | kg N | Farm | period calculated | No (0 if missing) |
| `DIESEL` | Monitoring data | GS_DIESEL | L | Farm | period calculated | No (0 if missing) |
| `GASOLINE` | Monitoring data | GS_GASOLINE | L | Farm | period calculated | No (0 if missing) |
| `ELECTRICITY` | Monitoring data | GS_ELECTRICITY | kWh | Farm | period calculated | No (0 if missing) |
| `AGROCHEM` | Monitoring data | GS_AGROCHEM | t CO2e | Farm | period calculated | No (0 if missing) |
| `FEF_DIESEL` | Monitoring data | GS_FEF_DIESEL | t CO2e/L | Project | period calculated | No (0 if missing) |
| `FEF_GASOLINE` | Monitoring data | GS_FEF_GASOLINE | t CO2e/L | Project | period calculated | No (0 if missing) |
| `EEF` | Monitoring data | GS_EEF | t CO2e/kWh | Project | period calculated | No (0 if missing) |
| `YIELD` | Monitoring data | GS_YIELD | kg/ha | Farm | period calculated | No (0 if missing) |
| `LK_EF` | Monitoring data | GS_LK_EF | t CO2e/ha | Project | period calculated | No (0 if missing) |
| `PAA` | Monitoring data | GS_PAA | — | Project | period calculated | No (0 if missing) |

### 6.5 Constants built into the module (5)
| Constant | Value | Unit | Source |
|---|---|---|---|
| `C_TO_CO2` | 3.66667 | t CO2/t C | 44/12 (GS 402 v1.0 Eq. 1) |
| `EF_FE` | 0.01 | t CO2e/kg N | GS 402 v1.0 Eq. 13 / 402.4 and 402.6 Eq. 2 EF_FE (IPCC 2019 Table 11.1 aggregated), as printed |
| `BUFFER` | 0.20 | fraction | GS GHG ER&S Product Requirements v3.2 §11.1.1 (20 % of sequestration GSVERs) |
| `UNC_THRESHOLD` | 0.20 | fraction | GS 402 v1.0 Eq. 11 (20 % of the mean at 90 % confidence) |
| `BASELINE_CAP` | 0.5 | fraction | GS 402 v1.0 §10: undocumented FE_BL / FU_BL / EU_BL / AE_BL at most 50 % of the project value |

### 6.6 Outputs
Outputs written by this module's code (some appear only for the approach or activity module in use; `<stratum>` = one output per stratum).

| Output | Step |
|---|---|
| `REF_MASS_<stratum>` | BASELINE |
| `SOC_0_<stratum>` | BASELINE |
| `SOC_BL_<stratum>` | BASELINE |
| `SOC_T_<stratum>` | PROJECT |
| `PE_<stratum>` | EMISSIONS |
| `PE_TOTAL` | EMISSIONS |
| `DSOC_C` | REMOVALS |
| `DSOC_CO2` | REMOVALS |
| `LK_DISPLACED_HA` | LEAKAGE |
| `LK_TOTAL` | LEAKAGE |
| `UNC_LOWER_C` | UNCERTAINTY |
| `UNC_UPPER_C` | UNCERTAINTY |
| `UNC` | UNCERTAINTY |
| `UD` | UNCERTAINTY |
| `DC_SOC_ADJ` | ADJUSTMENT |
| `ER_GROSS` | ADJUSTMENT |
| `PAA_BLOCKED_SHARE` | ADJUSTMENT |
| `BUFFER` | ADJUSTMENT |
| `ER_NET` | NET |
| `REVERSAL` | NET |
| `GS_VER_TOTAL` | NET |

### 6.7 Interpretations made by the code (for the expert review)
- Approach 1: SOC_0 = mean stock of the stratum's samples in the earlier approved campaign (the project-start sampling at the first period), SOC_t = in this period's campaign; at least 3 samples per stratum and campaign (Table 6 starts at n = 3).
- Equivalent soil mass: cumulative fine-earth soil mass; reference mass per stratum = mean mass to the reference depth in the earlier campaign; linear interpolation with 2 depth increments, cubic spline with 3 or more (as for VM0042).
- Uncertainty (Eqs. 7-9): per stratum and campaign SE = SD / sqrt(n), t = two-sided 90 % Student-t with n - 1 degrees of freedom (equal to Table 6); Lower = sum of (SOC_t lower - SOC_0 upper) x A, Upper = sum of (SOC_t upper - SOC_0 lower) x A.
- Buffer: 20 % of the GS VERs from SOC sequestration go to the GS Compliance Buffer (GS GHG ER&S Product Requirements v3.2 §11.1.1); the whole net amount is sequestration for these activity modules, so (1 - BUF) applies to all of Eq. 1.
- GWPs: IPCC AR5 (Gold Standard rule update RU-2020-P&R v1.2, from 1 January 2021); EF_FE is used as printed (0.01 t CO2e per kg N), which is more conservative than 0.01 kg N2O-N/kg N x 44/28 x 265.
- Eq. 2: SOC_0 is the stock at the start of the calculation period (the baseline at the first period, the previous SOC_t later).
- Eqs. 10/11: UNC = |Upper - Lower| / (2 x dSOC) as a fraction; UD = UNC - 0.20 when UNC > 0.20 (capped at 1); no deduction otherwise. UNC is 1 when dSOC <= 0, and a SOC loss is used in full (the deduction never reduces a loss).
- Eq. 14: the electricity term is summed over the years like the fuel term (the printed bracket closes early).
- Eqs. 15/16/18: emissions are t CO2e per farm (litres, kWh and kg give t CO2e; the printed 'per ha' is not applied).
- Project emissions per farm and source: project records in the period minus the baseline annual mean (5 baseline years) x years in the period, floored at zero (decreases are never credited). Without baseline records the baseline is 50 % of the project value.
- Leakage: per stratum, max[(CY_BL - CY_t) / CY_BL; 0] x area x leakage-area emissions per ha. CY_min is taken as CY_BL (CY_min can never exceed CY_BL, so this is conservative); yields are the means of the farms' records (baseline years / this period). Yield records are required (no exemption is applied, G8): a stratum without a farm that has both baseline and period yields, or a farm with yields in only one of the two, blocks the run (YIELD_RECORDS_REQUIRED) instead of reading leakage as zero.
- Per-stratum outputs are named by the stratum code, or by a collision-free prefix of the stratum record id when it is not available; each sample has exactly one organic carbon and one soil mass result (duplicates or unpaired results block the run).
- GS VERs are whole tonnes rounded down; a negative result is reported as REVERSAL with zero credits.
- GS 119 v1.2 §3.1: the share of a positive result falling in vintages from 1 January 2026 (by days of the period) is not credited unless GS_PAA = YES (Gold Standard approved the Paris-aligned transition); the buffer applies to the credited share.

### 6.8 Reasons the calculation can be blocked
`DEPTH_INCREMENTS_REQUIRED`, `DUPLICATE_INPUT`, `INSUFFICIENT_SAMPLES`, `INVALID_INPUT`, `INVALID_SOIL_PROFILE`, `MISSING_REQUIRED_INPUT`, `SAMPLING_DEPTH_INSUFFICIENT`. Added 29/10: `DUPLICATE_LAB_RESULT` / `MASS_RESULT_MISSING` (Approach 1), `YIELD_RECORDS_REQUIRED` (a stratum without baseline and period crop yields, or a farm with yields of one phase only).

---

## 7. GS402 1.0 — GS402-IT-A3

| | |
|---|---|
| Standard | Gold Standard |
| Methodology | Soil Organic Carbon Framework + 402.1 Improved Tillage, Approach 3 |
| Methodology code / version label to create | `GS402` / `1.0` (or `1.0-<suffix>`) |
| Calculation module | `GS402-IT-A3` · module version 1.1.0 |
| Option text on the Calculation tab | GS 402 + 402.1 Improved Tillage - Approach 3 (IPCC stock change factors, Eqs. 4 and 6) |
| Suitable for | Reduced tillage without soil sampling — soil carbon change from IPCC stock-change factors (smallholders, pilots). |
| Field / laboratory work | No — factor values per stratum |
| Readiness | Not Production Ready |

### 7.1 Sampling rule (`MODULE-SAMPLING`)
None — this module needs no sampling design rule (no soil sampling).

### 7.2 Monitoring rules — the data the project collects (25)
| Code | What to record | Unit | Level | Source | Frequency | Methodology reference |
|---|---|---|---|---|---|---|
| `GS_SOC_REF` | Reference SOC stock under natural vegetation (project-oriented, 0-30 cm) | t C/ha | Stratum | Field activity | Project start | GS 402 Eqs. 4/6 SOC_REF |
| `GS_F_LU` | Land use factor | factor | Stratum | Field activity | Project start | GS 402 Eqs. 4/6 F_LU; Table 4 |
| `GS_F_MG_BL` | Tillage (management) factor, baseline | factor | Stratum | Field activity | Project start | GS 402 Eq. 4 F_MG,BL; Table 4 |
| `GS_F_I_BL` | Input factor, baseline | factor | Stratum | Field activity | Project start | GS 402 Eq. 4 F_I,BL; Table 4 |
| `GS_F_MG_PR` | Tillage (management) factor, project | factor | Stratum | Field activity | Annually | GS 402 Eq. 6 F_MG,PR; Table 4 |
| `GS_F_I_PR` | Input factor, project | factor | Stratum | Field activity | Annually | GS 402 Eq. 6 F_I,PR; Table 4 |
| `GS_T_BL` | Years since the baseline practice was introduced (at most D = 20) | yr | Stratum | Field activity | Project start | GS 402 Eq. 4 T_BL |
| `GS_T_PR` | Years since the project start at the end of the calculation period | yr | Stratum | Field activity | Each calculation period | GS 402 Eq. 6 T_PR |
| `GS_U_SOC_REF` | Uncertainty of SOC_REF (± % of the mean, two standard deviations, as in the IPCC tables) | % | Stratum | Field activity | Project start | GS 402 §9 Step 1; Tables 3/4 (± two standard deviations as % of mean) |
| `GS_U_F_LU` | Uncertainty of F_LU (± % of the mean, two standard deviations, as in the IPCC tables) | % | Stratum | Field activity | Project start | GS 402 §9 Step 1; Tables 3/4 (± two standard deviations as % of mean) |
| `GS_U_F_MG_BL` | Uncertainty of F_MG_BL (± % of the mean, two standard deviations, as in the IPCC tables) | % | Stratum | Field activity | Project start | GS 402 §9 Step 1; Tables 3/4 (± two standard deviations as % of mean) |
| `GS_U_F_I_BL` | Uncertainty of F_I_BL (± % of the mean, two standard deviations, as in the IPCC tables) | % | Stratum | Field activity | Project start | GS 402 §9 Step 1; Tables 3/4 (± two standard deviations as % of mean) |
| `GS_U_F_MG_PR` | Uncertainty of F_MG_PR (± % of the mean, two standard deviations, as in the IPCC tables) | % | Stratum | Field activity | Project start | GS 402 §9 Step 1; Tables 3/4 (± two standard deviations as % of mean) |
| `GS_U_F_I_PR` | Uncertainty of F_I_PR (± % of the mean, two standard deviations, as in the IPCC tables) | % | Stratum | Field activity | Project start | GS 402 §9 Step 1; Tables 3/4 (± two standard deviations as % of mean) |
| `GS_FERT_N` | Nitrogen fertiliser applied (synthetic and organic) | kg N | Farm | Field activity | Per year (5 baseline years before the project start and each project year) | GS 402 Eq. 13 FE; 402.4/402.6 Eq. 2 |
| `GS_DIESEL` | Diesel used by machinery | L | Farm | Field activity | Per year (5 baseline years before the project start and each project year) | GS 402 Eq. 15 FUL; 402.4/402.6 Eq. 4 |
| `GS_GASOLINE` | Gasoline used by machinery | L | Farm | Field activity | Per year (5 baseline years before the project start and each project year) | GS 402 Eq. 15 FUL; 402.4/402.6 Eq. 4 |
| `GS_ELECTRICITY` | Electricity used (grid or captive; on-site fossil generation is fuel) | kWh | Farm | Field activity | Per year (5 baseline years before the project start and each project year) | GS 402 Eq. 16 EUW; 402.4/402.6 Eq. 5 |
| `GS_AGROCHEM` | Other agrochemical emissions (sum of quantity x supplier emission factor per product) | t CO2e | Farm | Field activity | Per year (5 baseline years before the project start and each project year) | GS 402 Eqs. 17/18; 402.4/402.6 Eqs. 6/7 (AQ x AEF) |
| `GS_FEF_DIESEL` | Emission factor of diesel | t CO2e/L | Project | Field activity | Project start; reviewed annually | GS 402 Eq. 15 FEF; national GHG inventory, otherwise IPCC 2006 Vol. 2 Ch. 3 Table 3.3.1 |
| `GS_FEF_GASOLINE` | Emission factor of gasoline | t CO2e/L | Project | Field activity | Project start; reviewed annually | GS 402 Eq. 15 FEF; national GHG inventory, otherwise IPCC 2006 Vol. 2 Ch. 3 Table 3.3.1 |
| `GS_EEF` | Emission factor of the electricity used | t CO2e/kWh | Project | Field activity | Project start; reviewed annually | GS 402 Eq. 16 EEF; 402.4: grid - CDM TOOL05 |
| `GS_YIELD` | Crop yield | kg/ha | Farm | Field activity | Per year (5 baseline years before the project start and each project year) | GS 402 Eq. 19 CY; 402.4 Eq. 8; 402.6 Eq. 10 |
| `GS_LK_EF` | Leakage-area emissions per hectare displaced (dBC_LA + dSOC_LA + dFE_LA + dFU_LA) | t CO2e/ha | Project | Field activity | At verification, when the yield fell | GS 402 Eq. 19; 402.4 Eq. 8; 402.6 Eq. 10 |
| `GS_PAA` | Paris Agreement alignment status for 2026+ vintages: YES when approved by Gold Standard | — | Project | Field activity | When approved | GS 119 PAA P&R v1.2 §3.1 |

### 7.3 Calculation rules — the steps (8)
| # | Code | Step | What it calculates | Equation reference |
|---|---|---|---|---|
| 1 | `GS-BSL` | BASELINE | SOC stock at the start of the calculation period (SOC_0) per stratum | GS 402 v1.0 Eqs. 2, 3; Approach 3 Eqs. 4, 6 |
| 2 | `GS-PRJ` | PROJECT | SOC stock at the end of the calculation period (SOC_t) per stratum | GS 402 v1.0 Eq. 5; Approach 3 Eqs. 4, 6 |
| 3 | `GS-PE` | EMISSIONS | Project emissions: fertiliser N, fuel and electricity, agrochemicals | GS 402 v1.0 Eqs. 12-18 |
| 4 | `GS-DSOC` | REMOVALS | SOC stock change in the calculation period (t C and t CO2e) | GS 402 v1.0 Eqs. 2, 3, 5 (x 44/12, Eq. 1) |
| 5 | `GS-LK` | LEAKAGE | Leakage from a yield reduction (shift of production) | GS 402 v1.0 Eq. 19 |
| 6 | `GS-UNC` | UNCERTAINTY | Uncertainty at 90 % confidence and uncertainty deduction | GS 402 v1.0 Eqs. 7-11, Table 6 |
| 7 | `GS-ADJ` | ADJUSTMENT | Uncertainty deduction applied; Gold Standard compliance buffer | GS 402 v1.0 Eqs. 1, 2; GS GHG ER&S Product Requirements v3.2 §11.1.1 |
| 8 | `GS-NET` | NET | Emission reductions for issuance (GS VERs, whole tonnes rounded down) | GS 402 v1.0 Eq. 1 |

### 7.4 Calculation inputs (26)
| Input | Comes from | Rule / parameter | Unit | Level | Round | Required |
|---|---|---|---|---|---|---|
| `SOC_REF` | Monitoring data | GS_SOC_REF | t C/ha | Stratum | period calculated | **Yes** |
| `F_LU` | Monitoring data | GS_F_LU | factor | Stratum | period calculated | **Yes** |
| `F_MG_BL` | Monitoring data | GS_F_MG_BL | factor | Stratum | period calculated | **Yes** |
| `F_I_BL` | Monitoring data | GS_F_I_BL | factor | Stratum | period calculated | **Yes** |
| `F_MG_PR` | Monitoring data | GS_F_MG_PR | factor | Stratum | period calculated | **Yes** |
| `F_I_PR` | Monitoring data | GS_F_I_PR | factor | Stratum | period calculated | **Yes** |
| `T_BL` | Monitoring data | GS_T_BL | yr | Stratum | period calculated | **Yes** |
| `T_PR` | Monitoring data | GS_T_PR | yr | Stratum | period calculated | **Yes** |
| `U_SOC_REF` | Monitoring data | GS_U_SOC_REF | % | Stratum | period calculated | No (0 if missing) |
| `U_F_LU` | Monitoring data | GS_U_F_LU | % | Stratum | period calculated | No (0 if missing) |
| `U_F_MG_BL` | Monitoring data | GS_U_F_MG_BL | % | Stratum | period calculated | No (0 if missing) |
| `U_F_I_BL` | Monitoring data | GS_U_F_I_BL | % | Stratum | period calculated | No (0 if missing) |
| `U_F_MG_PR` | Monitoring data | GS_U_F_MG_PR | % | Stratum | period calculated | No (0 if missing) |
| `U_F_I_PR` | Monitoring data | GS_U_F_I_PR | % | Stratum | period calculated | No (0 if missing) |
| `AREA` | Stratum area (SQL Server) | — | ha | Stratum | period calculated | **Yes** |
| `FERT_N` | Monitoring data | GS_FERT_N | kg N | Farm | period calculated | No (0 if missing) |
| `DIESEL` | Monitoring data | GS_DIESEL | L | Farm | period calculated | No (0 if missing) |
| `GASOLINE` | Monitoring data | GS_GASOLINE | L | Farm | period calculated | No (0 if missing) |
| `ELECTRICITY` | Monitoring data | GS_ELECTRICITY | kWh | Farm | period calculated | No (0 if missing) |
| `AGROCHEM` | Monitoring data | GS_AGROCHEM | t CO2e | Farm | period calculated | No (0 if missing) |
| `FEF_DIESEL` | Monitoring data | GS_FEF_DIESEL | t CO2e/L | Project | period calculated | No (0 if missing) |
| `FEF_GASOLINE` | Monitoring data | GS_FEF_GASOLINE | t CO2e/L | Project | period calculated | No (0 if missing) |
| `EEF` | Monitoring data | GS_EEF | t CO2e/kWh | Project | period calculated | No (0 if missing) |
| `YIELD` | Monitoring data | GS_YIELD | kg/ha | Farm | period calculated | No (0 if missing) |
| `LK_EF` | Monitoring data | GS_LK_EF | t CO2e/ha | Project | period calculated | No (0 if missing) |
| `PAA` | Monitoring data | GS_PAA | — | Project | period calculated | No (0 if missing) |

### 7.5 Constants built into the module (9)
| Constant | Value | Unit | Source |
|---|---|---|---|
| `C_TO_CO2` | 3.66667 | t CO2/t C | 44/12 (GS 402 v1.0 Eq. 1) |
| `EF_FE` | 0.01 | t CO2e/kg N | GS 402 v1.0 Eq. 13 / 402.4 and 402.6 Eq. 2 EF_FE (IPCC 2019 Table 11.1 aggregated), as printed |
| `BUFFER` | 0.20 | fraction | GS GHG ER&S Product Requirements v3.2 §11.1.1 (20 % of sequestration GSVERs) |
| `UNC_THRESHOLD` | 0.20 | fraction | GS 402 v1.0 Eq. 11 (20 % of the mean at 90 % confidence) |
| `BASELINE_CAP` | 0.5 | fraction | GS 402 v1.0 §10: undocumented FE_BL / FU_BL / EU_BL / AE_BL at most 50 % of the project value |
| `D_YEARS` | 20 | yr | GS 402 v1.0 Eqs. 4/6, footnotes 7 and 14 (IPCC default time dependency D = 20 years) |
| `T_UNKNOWN_N` | 1.675 | t-value | GS 402 v1.0 Eq. 8: n_p unknown -> 1.675 |
| `T_DEFAULT` | 3 | t-value | 402.4 / 402.6 §9.1.2: no SD / SE known -> SE = 50 % and t = 3 |
| `SE_DEFAULT` | 0.5 | fraction | 402.4 / 402.6 §9.1.2: SE = 50 % of the parameter value when unknown |

### 7.6 Outputs
Outputs written by this module's code (some appear only for the approach or activity module in use; `<stratum>` = one output per stratum).

| Output | Step |
|---|---|
| `REF_MASS_<stratum>` | BASELINE |
| `SOC_0_<stratum>` | BASELINE |
| `SOC_BL_<stratum>` | BASELINE |
| `SOC_T_<stratum>` | PROJECT |
| `PE_<stratum>` | EMISSIONS |
| `PE_TOTAL` | EMISSIONS |
| `DSOC_C` | REMOVALS |
| `DSOC_CO2` | REMOVALS |
| `LK_DISPLACED_HA` | LEAKAGE |
| `LK_TOTAL` | LEAKAGE |
| `UNC_LOWER_C` | UNCERTAINTY |
| `UNC_UPPER_C` | UNCERTAINTY |
| `UNC` | UNCERTAINTY |
| `UD` | UNCERTAINTY |
| `DC_SOC_ADJ` | ADJUSTMENT |
| `ER_GROSS` | ADJUSTMENT |
| `PAA_BLOCKED_SHARE` | ADJUSTMENT |
| `BUFFER` | ADJUSTMENT |
| `ER_NET` | NET |
| `REVERSAL` | NET |
| `GS_VER_TOTAL` | NET |

### 7.7 Interpretations made by the code (for the expert review)
- Approach 3: dSOC in the period = SOC_REF x F_LU x (F_MG,PR x F_I,PR - F_MG,BL x F_I,BL) x (min(T_PR, D) - min(T_PR - years, D)) / D, i.e. Eq. 6 at the end minus Eq. 6 at the start of the period (D = 20); the reported SOC_0 / SOC_T are Eq. 6 at the start / end of the period (the time dependency stops D years after the project start).
- Uncertainty (Eqs. 7-9): for a factor with a ± % (two standard deviations, IPCC tables) SE = value x % / 200 and t = 1.675 (n unknown); without a ± %, SE = 50 % and t = 3 (402.4/402.6 §9.1.2). Lower / Upper = the smallest / largest dSOC over all combinations of the factors' bounds.
- Buffer: 20 % of the GS VERs from SOC sequestration go to the GS Compliance Buffer (GS GHG ER&S Product Requirements v3.2 §11.1.1); the whole net amount is sequestration for these activity modules, so (1 - BUF) applies to all of Eq. 1.
- GWPs: IPCC AR5 (Gold Standard rule update RU-2020-P&R v1.2, from 1 January 2021); EF_FE is used as printed (0.01 t CO2e per kg N), which is more conservative than 0.01 kg N2O-N/kg N x 44/28 x 265.
- Eq. 2: SOC_0 is the stock at the start of the calculation period (the baseline at the first period, the previous SOC_t later).
- Eqs. 10/11: UNC = |Upper - Lower| / (2 x dSOC) as a fraction; UD = UNC - 0.20 when UNC > 0.20 (capped at 1); no deduction otherwise. UNC is 1 when dSOC <= 0, and a SOC loss is used in full (the deduction never reduces a loss).
- Eq. 14: the electricity term is summed over the years like the fuel term (the printed bracket closes early).
- Eqs. 15/16/18: emissions are t CO2e per farm (litres, kWh and kg give t CO2e; the printed 'per ha' is not applied).
- Project emissions per farm and source: project records in the period minus the baseline annual mean (5 baseline years) x years in the period, floored at zero (decreases are never credited). Without baseline records the baseline is 50 % of the project value.
- Leakage: per stratum, max[(CY_BL - CY_t) / CY_BL; 0] x area x leakage-area emissions per ha. CY_min is taken as CY_BL (CY_min can never exceed CY_BL, so this is conservative); yields are the means of the farms' records (baseline years / this period). Yield records are required (no exemption is applied, G8): a stratum without a farm that has both baseline and period yields, or a farm with yields in only one of the two, blocks the run (YIELD_RECORDS_REQUIRED) instead of reading leakage as zero.
- Per-stratum outputs are named by the stratum code, or by a collision-free prefix of the stratum record id when it is not available; each sample has exactly one organic carbon and one soil mass result (duplicates or unpaired results block the run).
- GS VERs are whole tonnes rounded down; a negative result is reported as REVERSAL with zero credits.
- GS 119 v1.2 §3.1: the share of a positive result falling in vintages from 1 January 2026 (by days of the period) is not credited unless GS_PAA = YES (Gold Standard approved the Paris-aligned transition); the buffer applies to the credited share.

### 7.8 Reasons the calculation can be blocked
`DEPTH_INCREMENTS_REQUIRED`, `DUPLICATE_INPUT`, `INSUFFICIENT_SAMPLES`, `INVALID_INPUT`, `INVALID_SOIL_PROFILE`, `MISSING_REQUIRED_INPUT`, `SAMPLING_DEPTH_INSUFFICIENT`. Added 29/10: `DUPLICATE_LAB_RESULT` / `MASS_RESULT_MISSING` (Approach 1), `YIELD_RECORDS_REQUIRED` (a stratum without baseline and period crop yields, or a farm with yields of one phase only).

---

## 8. GS402 1.0 — GS402-CC-A1

| | |
|---|---|
| Standard | Gold Standard |
| Methodology | Soil Organic Carbon Framework + 402.6 Cover Crops, Approach 1 |
| Methodology code / version label to create | `GS402` / `1.0` (or `1.0-<suffix>`) |
| Calculation module | `GS402-CC-A1` · module version 1.1.0 |
| Option text on the Calculation tab | GS 402 + 402.6 Cover Crops - Approach 1 (SOC measured, equivalent soil mass to 30 cm) + seed emissions |
| Suitable for | Cover crops; soil carbon measured; cover-crop seed production and transport emissions included. |
| Field / laboratory work | Yes — two sampling rounds, laboratory OC and soil mass |
| Readiness | Not Production Ready |

### 8.1 Sampling rule (`MODULE-SAMPLING`)
| Parameter | Value | Effect in the platform |
|---|---|---|
| `quantification_approach` | `MEASURE_AND_REMEASURE` | The MRV plan's approach is set to this value; any other choice is refused |
| `min_samples_per_stratum` | `3` | Every stratum in a sampling design needs at least this many points |
| `core_details_required` | `True` | Probe diameter and number of cores are mandatory on every field record |
| `reference_depth_cm` | `30` | Soil carbon compared on an equivalent soil mass to this depth |
| `statistical_design` | `STRATIFIED_RANDOM` | The sampling design must use this design |

### 8.2 Monitoring rules — the data the project collects (17)
| Code | What to record | Unit | Level | Source | Frequency | Methodology reference |
|---|---|---|---|---|---|---|
| `GS_OC` | Soil organic carbon content (per depth increment) | g/kg | Sampling point | Laboratory | Project start and each performance certification | GS 402 v1.0 §5.1 Approach 1, Annex 1 |
| `GS_SOIL_MASS` | Dry fine-earth soil mass of the sample (per depth increment, > 2 mm excluded) | g | Sampling point | Laboratory | Project start and each performance certification | 402.4 / 402.6 §5.2.1(e) / §6.2: equivalent mass basis |
| `GS_FERT_N` | Nitrogen fertiliser applied (synthetic and organic) | kg N | Farm | Field activity | Per year (5 baseline years before the project start and each project year) | GS 402 Eq. 13 FE; 402.4/402.6 Eq. 2 |
| `GS_DIESEL` | Diesel used by machinery | L | Farm | Field activity | Per year (5 baseline years before the project start and each project year) | GS 402 Eq. 15 FUL; 402.4/402.6 Eq. 4 |
| `GS_GASOLINE` | Gasoline used by machinery | L | Farm | Field activity | Per year (5 baseline years before the project start and each project year) | GS 402 Eq. 15 FUL; 402.4/402.6 Eq. 4 |
| `GS_ELECTRICITY` | Electricity used (grid or captive; on-site fossil generation is fuel) | kWh | Farm | Field activity | Per year (5 baseline years before the project start and each project year) | GS 402 Eq. 16 EUW; 402.4/402.6 Eq. 5 |
| `GS_AGROCHEM` | Other agrochemical emissions (sum of quantity x supplier emission factor per product) | t CO2e | Farm | Field activity | Per year (5 baseline years before the project start and each project year) | GS 402 Eqs. 17/18; 402.4/402.6 Eqs. 6/7 (AQ x AEF) |
| `GS_FEF_DIESEL` | Emission factor of diesel | t CO2e/L | Project | Field activity | Project start; reviewed annually | GS 402 Eq. 15 FEF; national GHG inventory, otherwise IPCC 2006 Vol. 2 Ch. 3 Table 3.3.1 |
| `GS_FEF_GASOLINE` | Emission factor of gasoline | t CO2e/L | Project | Field activity | Project start; reviewed annually | GS 402 Eq. 15 FEF; national GHG inventory, otherwise IPCC 2006 Vol. 2 Ch. 3 Table 3.3.1 |
| `GS_EEF` | Emission factor of the electricity used | t CO2e/kWh | Project | Field activity | Project start; reviewed annually | GS 402 Eq. 16 EEF; 402.4: grid - CDM TOOL05 |
| `GS_CC_SEED` | Cover crop seed applied | kg | Farm | Field activity | Per year | 402.6 Eq. 7 S x A |
| `GS_CC_EF_SP` | Emission factor of cover crop seed production | t CO2e/kg | Project | Field activity | Project start; updated annually | 402.6 Eq. 7 EF_SP |
| `GS_CC_EF_ST` | Emission factor of seed transport | t CO2e/(kg km) | Project | Field activity | Project start; reviewed annually | 402.6 Eq. 7 EF_ST |
| `GS_CC_DIST` | Seed transport distance (field-size weighted) | km | Project | Field activity | Per year | 402.6 Eq. 7 DistST |
| `GS_YIELD` | Crop yield | kg/ha | Farm | Field activity | Per year (5 baseline years before the project start and each project year) | GS 402 Eq. 19 CY; 402.4 Eq. 8; 402.6 Eq. 10 |
| `GS_LK_EF` | Leakage-area emissions per hectare displaced (dBC_LA + dSOC_LA + dFE_LA + dFU_LA) | t CO2e/ha | Project | Field activity | At verification, when the yield fell | GS 402 Eq. 19; 402.4 Eq. 8; 402.6 Eq. 10 |
| `GS_PAA` | Paris Agreement alignment status for 2026+ vintages: YES when approved by Gold Standard | — | Project | Field activity | When approved | GS 119 PAA P&R v1.2 §3.1 |

### 8.3 Calculation rules — the steps (8)
| # | Code | Step | What it calculates | Equation reference |
|---|---|---|---|---|
| 1 | `GS-BSL` | BASELINE | SOC stock at the start of the calculation period (SOC_0) per stratum | GS 402 v1.0 Eqs. 2, 3; Approach 1 on-site measurement (equivalent soil mass) |
| 2 | `GS-PRJ` | PROJECT | SOC stock at the end of the calculation period (SOC_t) per stratum | GS 402 v1.0 Eq. 5; Approach 1 on-site measurement (equivalent soil mass) |
| 3 | `GS-PE` | EMISSIONS | Project emissions: fertiliser N, fuel and electricity, agrochemicals | 402.6 v1.0 Eqs. 1-9 (replace GS 402 Eqs. 12-18) |
| 4 | `GS-DSOC` | REMOVALS | SOC stock change in the calculation period (t C and t CO2e) | GS 402 v1.0 Eqs. 2, 3, 5 (x 44/12, Eq. 1) |
| 5 | `GS-LK` | LEAKAGE | Leakage from a yield reduction (shift of production) | 402.6 v1.0 Eq. 10 |
| 6 | `GS-UNC` | UNCERTAINTY | Uncertainty at 90 % confidence and uncertainty deduction | GS 402 v1.0 Eqs. 7-11, Table 6 |
| 7 | `GS-ADJ` | ADJUSTMENT | Uncertainty deduction applied; Gold Standard compliance buffer | GS 402 v1.0 Eqs. 1, 2; GS GHG ER&S Product Requirements v3.2 §11.1.1 |
| 8 | `GS-NET` | NET | Emission reductions for issuance (GS VERs, whole tonnes rounded down) | GS 402 v1.0 Eq. 1 |

### 8.4 Calculation inputs (20)
| Input | Comes from | Rule / parameter | Unit | Level | Round | Required |
|---|---|---|---|---|---|---|
| `OC_T` | Laboratory result | GS_OC | g/kg | Sampling point | period calculated | **Yes** |
| `MASS_T` | Laboratory result | GS_SOIL_MASS | g | Sampling point | period calculated | **Yes** |
| `OC_T0` | Laboratory result | GS_OC | g/kg | Sampling point | previous round | **Yes** |
| `MASS_T0` | Laboratory result | GS_SOIL_MASS | g | Sampling point | previous round | **Yes** |
| `AREA` | Stratum area (SQL Server) | — | ha | Stratum | period calculated | **Yes** |
| `FERT_N` | Monitoring data | GS_FERT_N | kg N | Farm | period calculated | No (0 if missing) |
| `DIESEL` | Monitoring data | GS_DIESEL | L | Farm | period calculated | No (0 if missing) |
| `GASOLINE` | Monitoring data | GS_GASOLINE | L | Farm | period calculated | No (0 if missing) |
| `ELECTRICITY` | Monitoring data | GS_ELECTRICITY | kWh | Farm | period calculated | No (0 if missing) |
| `AGROCHEM` | Monitoring data | GS_AGROCHEM | t CO2e | Farm | period calculated | No (0 if missing) |
| `FEF_DIESEL` | Monitoring data | GS_FEF_DIESEL | t CO2e/L | Project | period calculated | No (0 if missing) |
| `FEF_GASOLINE` | Monitoring data | GS_FEF_GASOLINE | t CO2e/L | Project | period calculated | No (0 if missing) |
| `EEF` | Monitoring data | GS_EEF | t CO2e/kWh | Project | period calculated | No (0 if missing) |
| `SEED` | Monitoring data | GS_CC_SEED | kg | Farm | period calculated | No (0 if missing) |
| `EF_SP` | Monitoring data | GS_CC_EF_SP | t CO2e/kg | Project | period calculated | No (0 if missing) |
| `EF_ST` | Monitoring data | GS_CC_EF_ST | t CO2e/(kg km) | Project | period calculated | No (0 if missing) |
| `DIST` | Monitoring data | GS_CC_DIST | km | Project | period calculated | No (0 if missing) |
| `YIELD` | Monitoring data | GS_YIELD | kg/ha | Farm | period calculated | No (0 if missing) |
| `LK_EF` | Monitoring data | GS_LK_EF | t CO2e/ha | Project | period calculated | No (0 if missing) |
| `PAA` | Monitoring data | GS_PAA | — | Project | period calculated | No (0 if missing) |

### 8.5 Constants built into the module (5)
| Constant | Value | Unit | Source |
|---|---|---|---|
| `C_TO_CO2` | 3.66667 | t CO2/t C | 44/12 (GS 402 v1.0 Eq. 1) |
| `EF_FE` | 0.01 | t CO2e/kg N | GS 402 v1.0 Eq. 13 / 402.4 and 402.6 Eq. 2 EF_FE (IPCC 2019 Table 11.1 aggregated), as printed |
| `BUFFER` | 0.20 | fraction | GS GHG ER&S Product Requirements v3.2 §11.1.1 (20 % of sequestration GSVERs) |
| `UNC_THRESHOLD` | 0.20 | fraction | GS 402 v1.0 Eq. 11 (20 % of the mean at 90 % confidence) |
| `BASELINE_CAP` | 0.5 | fraction | GS 402 v1.0 §10: undocumented FE_BL / FU_BL / EU_BL / AE_BL at most 50 % of the project value |

### 8.6 Outputs
Outputs written by this module's code (some appear only for the approach or activity module in use; `<stratum>` = one output per stratum).

| Output | Step |
|---|---|
| `REF_MASS_<stratum>` | BASELINE |
| `SOC_0_<stratum>` | BASELINE |
| `SOC_BL_<stratum>` | BASELINE |
| `SOC_T_<stratum>` | PROJECT |
| `PE_<stratum>` | EMISSIONS |
| `PE_TOTAL` | EMISSIONS |
| `DSOC_C` | REMOVALS |
| `DSOC_CO2` | REMOVALS |
| `LK_DISPLACED_HA` | LEAKAGE |
| `LK_TOTAL` | LEAKAGE |
| `UNC_LOWER_C` | UNCERTAINTY |
| `UNC_UPPER_C` | UNCERTAINTY |
| `UNC` | UNCERTAINTY |
| `UD` | UNCERTAINTY |
| `DC_SOC_ADJ` | ADJUSTMENT |
| `ER_GROSS` | ADJUSTMENT |
| `PAA_BLOCKED_SHARE` | ADJUSTMENT |
| `BUFFER` | ADJUSTMENT |
| `ER_NET` | NET |
| `REVERSAL` | NET |
| `GS_VER_TOTAL` | NET |

### 8.7 Interpretations made by the code (for the expert review)
- Approach 1: SOC_0 = mean stock of the stratum's samples in the earlier approved campaign (the project-start sampling at the first period), SOC_t = in this period's campaign; at least 3 samples per stratum and campaign (Table 6 starts at n = 3).
- Equivalent soil mass: cumulative fine-earth soil mass; reference mass per stratum = mean mass to the reference depth in the earlier campaign; linear interpolation with 2 depth increments, cubic spline with 3 or more (as for VM0042).
- Uncertainty (Eqs. 7-9): per stratum and campaign SE = SD / sqrt(n), t = two-sided 90 % Student-t with n - 1 degrees of freedom (equal to Table 6); Lower = sum of (SOC_t lower - SOC_0 upper) x A, Upper = sum of (SOC_t upper - SOC_0 lower) x A.
- Buffer: 20 % of the GS VERs from SOC sequestration go to the GS Compliance Buffer (GS GHG ER&S Product Requirements v3.2 §11.1.1); the whole net amount is sequestration for these activity modules, so (1 - BUF) applies to all of Eq. 1.
- GWPs: IPCC AR5 (Gold Standard rule update RU-2020-P&R v1.2, from 1 January 2021); EF_FE is used as printed (0.01 t CO2e per kg N), which is more conservative than 0.01 kg N2O-N/kg N x 44/28 x 265.
- Eq. 2: SOC_0 is the stock at the start of the calculation period (the baseline at the first period, the previous SOC_t later).
- Eqs. 10/11: UNC = |Upper - Lower| / (2 x dSOC) as a fraction; UD = UNC - 0.20 when UNC > 0.20 (capped at 1); no deduction otherwise. UNC is 1 when dSOC <= 0, and a SOC loss is used in full (the deduction never reduces a loss).
- Eq. 14: the electricity term is summed over the years like the fuel term (the printed bracket closes early).
- Eqs. 15/16/18: emissions are t CO2e per farm (litres, kWh and kg give t CO2e; the printed 'per ha' is not applied).
- Project emissions per farm and source: project records in the period minus the baseline annual mean (5 baseline years) x years in the period, floored at zero (decreases are never credited). Without baseline records the baseline is 50 % of the project value.
- Leakage: per stratum, max[(CY_BL - CY_t) / CY_BL; 0] x area x leakage-area emissions per ha. CY_min is taken as CY_BL (CY_min can never exceed CY_BL, so this is conservative); yields are the means of the farms' records (baseline years / this period). Yield records are required (no exemption is applied, G8): a stratum without a farm that has both baseline and period yields, or a farm with yields in only one of the two, blocks the run (YIELD_RECORDS_REQUIRED) instead of reading leakage as zero.
- Per-stratum outputs are named by the stratum code, or by a collision-free prefix of the stratum record id when it is not available; each sample has exactly one organic carbon and one soil mass result (duplicates or unpaired results block the run).
- GS VERs are whole tonnes rounded down; a negative result is reported as REVERSAL with zero credits.
- GS 119 v1.2 §3.1: the share of a positive result falling in vintages from 1 January 2026 (by days of the period) is not credited unless GS_PAA = YES (Gold Standard approved the Paris-aligned transition); the buffer applies to the credited share.

### 8.8 Reasons the calculation can be blocked
`DEPTH_INCREMENTS_REQUIRED`, `DUPLICATE_INPUT`, `INSUFFICIENT_SAMPLES`, `INVALID_INPUT`, `INVALID_SOIL_PROFILE`, `MISSING_REQUIRED_INPUT`, `SAMPLING_DEPTH_INSUFFICIENT`. Added 29/10: `DUPLICATE_LAB_RESULT` / `MASS_RESULT_MISSING` (Approach 1), `YIELD_RECORDS_REQUIRED` (a stratum without baseline and period crop yields, or a farm with yields of one phase only).

---

## 9. GS402 1.0 — GS402-CC-A3

| | |
|---|---|
| Standard | Gold Standard |
| Methodology | Soil Organic Carbon Framework + 402.6 Cover Crops, Approach 3.1 |
| Methodology code / version label to create | `GS402` / `1.0` (or `1.0-<suffix>`) |
| Calculation module | `GS402-CC-A3` · module version 1.1.0 |
| Option text on the Calculation tab | GS 402 + 402.6 Cover Crops - Approach 3.1 (national / regional Tier 2 factors, Eqs. 4 and 6) + seed emissions |
| Suitable for | Cover crops without soil sampling — national / regional Tier 2 stock-change factors; seed emissions included. |
| Field / laboratory work | No — factor values per stratum |
| Readiness | Not Production Ready |

### 9.1 Sampling rule (`MODULE-SAMPLING`)
None — this module needs no sampling design rule (no soil sampling).

### 9.2 Monitoring rules — the data the project collects (29)
| Code | What to record | Unit | Level | Source | Frequency | Methodology reference |
|---|---|---|---|---|---|---|
| `GS_SOC_REF` | Reference SOC stock under natural vegetation (project-oriented, 0-30 cm) | t C/ha | Stratum | Field activity | Project start | GS 402 Eqs. 4/6 SOC_REF |
| `GS_F_LU` | Land use factor | factor | Stratum | Field activity | Project start | GS 402 Eqs. 4/6 F_LU; Table 4 |
| `GS_F_MG_BL` | Tillage (management) factor, baseline | factor | Stratum | Field activity | Project start | GS 402 Eq. 4 F_MG,BL; Table 4 |
| `GS_F_I_BL` | Input factor, baseline | factor | Stratum | Field activity | Project start | GS 402 Eq. 4 F_I,BL; Table 4 |
| `GS_F_MG_PR` | Tillage (management) factor, project | factor | Stratum | Field activity | Annually | GS 402 Eq. 6 F_MG,PR; Table 4 |
| `GS_F_I_PR` | Input factor, project | factor | Stratum | Field activity | Annually | GS 402 Eq. 6 F_I,PR; Table 4 |
| `GS_T_BL` | Years since the baseline practice was introduced (at most D = 20) | yr | Stratum | Field activity | Project start | GS 402 Eq. 4 T_BL |
| `GS_T_PR` | Years since the project start at the end of the calculation period | yr | Stratum | Field activity | Each calculation period | GS 402 Eq. 6 T_PR |
| `GS_U_SOC_REF` | Uncertainty of SOC_REF (± % of the mean, two standard deviations, as in the IPCC tables) | % | Stratum | Field activity | Project start | GS 402 §9 Step 1; Tables 3/4 (± two standard deviations as % of mean) |
| `GS_U_F_LU` | Uncertainty of F_LU (± % of the mean, two standard deviations, as in the IPCC tables) | % | Stratum | Field activity | Project start | GS 402 §9 Step 1; Tables 3/4 (± two standard deviations as % of mean) |
| `GS_U_F_MG_BL` | Uncertainty of F_MG_BL (± % of the mean, two standard deviations, as in the IPCC tables) | % | Stratum | Field activity | Project start | GS 402 §9 Step 1; Tables 3/4 (± two standard deviations as % of mean) |
| `GS_U_F_I_BL` | Uncertainty of F_I_BL (± % of the mean, two standard deviations, as in the IPCC tables) | % | Stratum | Field activity | Project start | GS 402 §9 Step 1; Tables 3/4 (± two standard deviations as % of mean) |
| `GS_U_F_MG_PR` | Uncertainty of F_MG_PR (± % of the mean, two standard deviations, as in the IPCC tables) | % | Stratum | Field activity | Project start | GS 402 §9 Step 1; Tables 3/4 (± two standard deviations as % of mean) |
| `GS_U_F_I_PR` | Uncertainty of F_I_PR (± % of the mean, two standard deviations, as in the IPCC tables) | % | Stratum | Field activity | Project start | GS 402 §9 Step 1; Tables 3/4 (± two standard deviations as % of mean) |
| `GS_FERT_N` | Nitrogen fertiliser applied (synthetic and organic) | kg N | Farm | Field activity | Per year (5 baseline years before the project start and each project year) | GS 402 Eq. 13 FE; 402.4/402.6 Eq. 2 |
| `GS_DIESEL` | Diesel used by machinery | L | Farm | Field activity | Per year (5 baseline years before the project start and each project year) | GS 402 Eq. 15 FUL; 402.4/402.6 Eq. 4 |
| `GS_GASOLINE` | Gasoline used by machinery | L | Farm | Field activity | Per year (5 baseline years before the project start and each project year) | GS 402 Eq. 15 FUL; 402.4/402.6 Eq. 4 |
| `GS_ELECTRICITY` | Electricity used (grid or captive; on-site fossil generation is fuel) | kWh | Farm | Field activity | Per year (5 baseline years before the project start and each project year) | GS 402 Eq. 16 EUW; 402.4/402.6 Eq. 5 |
| `GS_AGROCHEM` | Other agrochemical emissions (sum of quantity x supplier emission factor per product) | t CO2e | Farm | Field activity | Per year (5 baseline years before the project start and each project year) | GS 402 Eqs. 17/18; 402.4/402.6 Eqs. 6/7 (AQ x AEF) |
| `GS_FEF_DIESEL` | Emission factor of diesel | t CO2e/L | Project | Field activity | Project start; reviewed annually | GS 402 Eq. 15 FEF; national GHG inventory, otherwise IPCC 2006 Vol. 2 Ch. 3 Table 3.3.1 |
| `GS_FEF_GASOLINE` | Emission factor of gasoline | t CO2e/L | Project | Field activity | Project start; reviewed annually | GS 402 Eq. 15 FEF; national GHG inventory, otherwise IPCC 2006 Vol. 2 Ch. 3 Table 3.3.1 |
| `GS_EEF` | Emission factor of the electricity used | t CO2e/kWh | Project | Field activity | Project start; reviewed annually | GS 402 Eq. 16 EEF; 402.4: grid - CDM TOOL05 |
| `GS_CC_SEED` | Cover crop seed applied | kg | Farm | Field activity | Per year | 402.6 Eq. 7 S x A |
| `GS_CC_EF_SP` | Emission factor of cover crop seed production | t CO2e/kg | Project | Field activity | Project start; updated annually | 402.6 Eq. 7 EF_SP |
| `GS_CC_EF_ST` | Emission factor of seed transport | t CO2e/(kg km) | Project | Field activity | Project start; reviewed annually | 402.6 Eq. 7 EF_ST |
| `GS_CC_DIST` | Seed transport distance (field-size weighted) | km | Project | Field activity | Per year | 402.6 Eq. 7 DistST |
| `GS_YIELD` | Crop yield | kg/ha | Farm | Field activity | Per year (5 baseline years before the project start and each project year) | GS 402 Eq. 19 CY; 402.4 Eq. 8; 402.6 Eq. 10 |
| `GS_LK_EF` | Leakage-area emissions per hectare displaced (dBC_LA + dSOC_LA + dFE_LA + dFU_LA) | t CO2e/ha | Project | Field activity | At verification, when the yield fell | GS 402 Eq. 19; 402.4 Eq. 8; 402.6 Eq. 10 |
| `GS_PAA` | Paris Agreement alignment status for 2026+ vintages: YES when approved by Gold Standard | — | Project | Field activity | When approved | GS 119 PAA P&R v1.2 §3.1 |

### 9.3 Calculation rules — the steps (8)
| # | Code | Step | What it calculates | Equation reference |
|---|---|---|---|---|
| 1 | `GS-BSL` | BASELINE | SOC stock at the start of the calculation period (SOC_0) per stratum | GS 402 v1.0 Eqs. 2, 3; Approach 3 Eqs. 4, 6 |
| 2 | `GS-PRJ` | PROJECT | SOC stock at the end of the calculation period (SOC_t) per stratum | GS 402 v1.0 Eq. 5; Approach 3 Eqs. 4, 6 |
| 3 | `GS-PE` | EMISSIONS | Project emissions: fertiliser N, fuel and electricity, agrochemicals | 402.6 v1.0 Eqs. 1-9 (replace GS 402 Eqs. 12-18) |
| 4 | `GS-DSOC` | REMOVALS | SOC stock change in the calculation period (t C and t CO2e) | GS 402 v1.0 Eqs. 2, 3, 5 (x 44/12, Eq. 1) |
| 5 | `GS-LK` | LEAKAGE | Leakage from a yield reduction (shift of production) | 402.6 v1.0 Eq. 10 |
| 6 | `GS-UNC` | UNCERTAINTY | Uncertainty at 90 % confidence and uncertainty deduction | GS 402 v1.0 Eqs. 7-11, Table 6 |
| 7 | `GS-ADJ` | ADJUSTMENT | Uncertainty deduction applied; Gold Standard compliance buffer | GS 402 v1.0 Eqs. 1, 2; GS GHG ER&S Product Requirements v3.2 §11.1.1 |
| 8 | `GS-NET` | NET | Emission reductions for issuance (GS VERs, whole tonnes rounded down) | GS 402 v1.0 Eq. 1 |

### 9.4 Calculation inputs (30)
| Input | Comes from | Rule / parameter | Unit | Level | Round | Required |
|---|---|---|---|---|---|---|
| `SOC_REF` | Monitoring data | GS_SOC_REF | t C/ha | Stratum | period calculated | **Yes** |
| `F_LU` | Monitoring data | GS_F_LU | factor | Stratum | period calculated | **Yes** |
| `F_MG_BL` | Monitoring data | GS_F_MG_BL | factor | Stratum | period calculated | **Yes** |
| `F_I_BL` | Monitoring data | GS_F_I_BL | factor | Stratum | period calculated | **Yes** |
| `F_MG_PR` | Monitoring data | GS_F_MG_PR | factor | Stratum | period calculated | **Yes** |
| `F_I_PR` | Monitoring data | GS_F_I_PR | factor | Stratum | period calculated | **Yes** |
| `T_BL` | Monitoring data | GS_T_BL | yr | Stratum | period calculated | **Yes** |
| `T_PR` | Monitoring data | GS_T_PR | yr | Stratum | period calculated | **Yes** |
| `U_SOC_REF` | Monitoring data | GS_U_SOC_REF | % | Stratum | period calculated | No (0 if missing) |
| `U_F_LU` | Monitoring data | GS_U_F_LU | % | Stratum | period calculated | No (0 if missing) |
| `U_F_MG_BL` | Monitoring data | GS_U_F_MG_BL | % | Stratum | period calculated | No (0 if missing) |
| `U_F_I_BL` | Monitoring data | GS_U_F_I_BL | % | Stratum | period calculated | No (0 if missing) |
| `U_F_MG_PR` | Monitoring data | GS_U_F_MG_PR | % | Stratum | period calculated | No (0 if missing) |
| `U_F_I_PR` | Monitoring data | GS_U_F_I_PR | % | Stratum | period calculated | No (0 if missing) |
| `AREA` | Stratum area (SQL Server) | — | ha | Stratum | period calculated | **Yes** |
| `FERT_N` | Monitoring data | GS_FERT_N | kg N | Farm | period calculated | No (0 if missing) |
| `DIESEL` | Monitoring data | GS_DIESEL | L | Farm | period calculated | No (0 if missing) |
| `GASOLINE` | Monitoring data | GS_GASOLINE | L | Farm | period calculated | No (0 if missing) |
| `ELECTRICITY` | Monitoring data | GS_ELECTRICITY | kWh | Farm | period calculated | No (0 if missing) |
| `AGROCHEM` | Monitoring data | GS_AGROCHEM | t CO2e | Farm | period calculated | No (0 if missing) |
| `FEF_DIESEL` | Monitoring data | GS_FEF_DIESEL | t CO2e/L | Project | period calculated | No (0 if missing) |
| `FEF_GASOLINE` | Monitoring data | GS_FEF_GASOLINE | t CO2e/L | Project | period calculated | No (0 if missing) |
| `EEF` | Monitoring data | GS_EEF | t CO2e/kWh | Project | period calculated | No (0 if missing) |
| `SEED` | Monitoring data | GS_CC_SEED | kg | Farm | period calculated | No (0 if missing) |
| `EF_SP` | Monitoring data | GS_CC_EF_SP | t CO2e/kg | Project | period calculated | No (0 if missing) |
| `EF_ST` | Monitoring data | GS_CC_EF_ST | t CO2e/(kg km) | Project | period calculated | No (0 if missing) |
| `DIST` | Monitoring data | GS_CC_DIST | km | Project | period calculated | No (0 if missing) |
| `YIELD` | Monitoring data | GS_YIELD | kg/ha | Farm | period calculated | No (0 if missing) |
| `LK_EF` | Monitoring data | GS_LK_EF | t CO2e/ha | Project | period calculated | No (0 if missing) |
| `PAA` | Monitoring data | GS_PAA | — | Project | period calculated | No (0 if missing) |

### 9.5 Constants built into the module (9)
| Constant | Value | Unit | Source |
|---|---|---|---|
| `C_TO_CO2` | 3.66667 | t CO2/t C | 44/12 (GS 402 v1.0 Eq. 1) |
| `EF_FE` | 0.01 | t CO2e/kg N | GS 402 v1.0 Eq. 13 / 402.4 and 402.6 Eq. 2 EF_FE (IPCC 2019 Table 11.1 aggregated), as printed |
| `BUFFER` | 0.20 | fraction | GS GHG ER&S Product Requirements v3.2 §11.1.1 (20 % of sequestration GSVERs) |
| `UNC_THRESHOLD` | 0.20 | fraction | GS 402 v1.0 Eq. 11 (20 % of the mean at 90 % confidence) |
| `BASELINE_CAP` | 0.5 | fraction | GS 402 v1.0 §10: undocumented FE_BL / FU_BL / EU_BL / AE_BL at most 50 % of the project value |
| `D_YEARS` | 20 | yr | GS 402 v1.0 Eqs. 4/6, footnotes 7 and 14 (IPCC default time dependency D = 20 years) |
| `T_UNKNOWN_N` | 1.675 | t-value | GS 402 v1.0 Eq. 8: n_p unknown -> 1.675 |
| `T_DEFAULT` | 3 | t-value | 402.4 / 402.6 §9.1.2: no SD / SE known -> SE = 50 % and t = 3 |
| `SE_DEFAULT` | 0.5 | fraction | 402.4 / 402.6 §9.1.2: SE = 50 % of the parameter value when unknown |

### 9.6 Outputs
Outputs written by this module's code (some appear only for the approach or activity module in use; `<stratum>` = one output per stratum).

| Output | Step |
|---|---|
| `REF_MASS_<stratum>` | BASELINE |
| `SOC_0_<stratum>` | BASELINE |
| `SOC_BL_<stratum>` | BASELINE |
| `SOC_T_<stratum>` | PROJECT |
| `PE_<stratum>` | EMISSIONS |
| `PE_TOTAL` | EMISSIONS |
| `DSOC_C` | REMOVALS |
| `DSOC_CO2` | REMOVALS |
| `LK_DISPLACED_HA` | LEAKAGE |
| `LK_TOTAL` | LEAKAGE |
| `UNC_LOWER_C` | UNCERTAINTY |
| `UNC_UPPER_C` | UNCERTAINTY |
| `UNC` | UNCERTAINTY |
| `UD` | UNCERTAINTY |
| `DC_SOC_ADJ` | ADJUSTMENT |
| `ER_GROSS` | ADJUSTMENT |
| `PAA_BLOCKED_SHARE` | ADJUSTMENT |
| `BUFFER` | ADJUSTMENT |
| `ER_NET` | NET |
| `REVERSAL` | NET |
| `GS_VER_TOTAL` | NET |

### 9.7 Interpretations made by the code (for the expert review)
- Approach 3: dSOC in the period = SOC_REF x F_LU x (F_MG,PR x F_I,PR - F_MG,BL x F_I,BL) x (min(T_PR, D) - min(T_PR - years, D)) / D, i.e. Eq. 6 at the end minus Eq. 6 at the start of the period (D = 20); the reported SOC_0 / SOC_T are Eq. 6 at the start / end of the period (the time dependency stops D years after the project start).
- Uncertainty (Eqs. 7-9): for a factor with a ± % (two standard deviations, IPCC tables) SE = value x % / 200 and t = 1.675 (n unknown); without a ± %, SE = 50 % and t = 3 (402.4/402.6 §9.1.2). Lower / Upper = the smallest / largest dSOC over all combinations of the factors' bounds.
- Buffer: 20 % of the GS VERs from SOC sequestration go to the GS Compliance Buffer (GS GHG ER&S Product Requirements v3.2 §11.1.1); the whole net amount is sequestration for these activity modules, so (1 - BUF) applies to all of Eq. 1.
- GWPs: IPCC AR5 (Gold Standard rule update RU-2020-P&R v1.2, from 1 January 2021); EF_FE is used as printed (0.01 t CO2e per kg N), which is more conservative than 0.01 kg N2O-N/kg N x 44/28 x 265.
- Eq. 2: SOC_0 is the stock at the start of the calculation period (the baseline at the first period, the previous SOC_t later).
- Eqs. 10/11: UNC = |Upper - Lower| / (2 x dSOC) as a fraction; UD = UNC - 0.20 when UNC > 0.20 (capped at 1); no deduction otherwise. UNC is 1 when dSOC <= 0, and a SOC loss is used in full (the deduction never reduces a loss).
- Eq. 14: the electricity term is summed over the years like the fuel term (the printed bracket closes early).
- Eqs. 15/16/18: emissions are t CO2e per farm (litres, kWh and kg give t CO2e; the printed 'per ha' is not applied).
- Project emissions per farm and source: project records in the period minus the baseline annual mean (5 baseline years) x years in the period, floored at zero (decreases are never credited). Without baseline records the baseline is 50 % of the project value.
- Leakage: per stratum, max[(CY_BL - CY_t) / CY_BL; 0] x area x leakage-area emissions per ha. CY_min is taken as CY_BL (CY_min can never exceed CY_BL, so this is conservative); yields are the means of the farms' records (baseline years / this period). Yield records are required (no exemption is applied, G8): a stratum without a farm that has both baseline and period yields, or a farm with yields in only one of the two, blocks the run (YIELD_RECORDS_REQUIRED) instead of reading leakage as zero.
- Per-stratum outputs are named by the stratum code, or by a collision-free prefix of the stratum record id when it is not available; each sample has exactly one organic carbon and one soil mass result (duplicates or unpaired results block the run).
- GS VERs are whole tonnes rounded down; a negative result is reported as REVERSAL with zero credits.
- GS 119 v1.2 §3.1: the share of a positive result falling in vintages from 1 January 2026 (by days of the period) is not credited unless GS_PAA = YES (Gold Standard approved the Paris-aligned transition); the buffer applies to the credited share.

### 9.8 Reasons the calculation can be blocked
`DEPTH_INCREMENTS_REQUIRED`, `DUPLICATE_INPUT`, `INSUFFICIENT_SAMPLES`, `INVALID_INPUT`, `INVALID_SOIL_PROFILE`, `MISSING_REQUIRED_INPUT`, `SAMPLING_DEPTH_INSUFFICIENT`. Added 29/10: `DUPLICATE_LAB_RESULT` / `MASS_RESULT_MISSING` (Approach 1), `YIELD_RECORDS_REQUIRED` (a stratum without baseline and period crop yields, or a farm with yields of one phase only).

---

## 10. VM0047 1.1 — VM0047-V1.1-CENSUS

| | |
|---|---|
| Standard | Verra (VCS) |
| Methodology | Afforestation, Reforestation and Revegetation — census-based approach |
| Methodology code / version label to create | `VM0047` / `1.1` (or `1.1-<suffix>`) |
| Calculation module | `VM0047-V1.1-CENSUS` · module version 1.1.0 |
| Option text on the Calculation tab | VM0047 v1.1 - census-based approach (planting units on farmland, <= 50 per ha) |
| Suitable for | Trees planted on farmland where farming continues, at most 50 planting units per hectare; every unit counted at t = 0. |
| Field / laboratory work | No soil sampling — tree census and sampled-tree measurements |
| Readiness | Not Production Ready |

### 10.1 Sampling rule (`MODULE-SAMPLING`)
| Parameter | Value | Effect in the platform |
|---|---|---|
| `quantification_approach` | `OTHER` | The MRV plan's approach is set to this value; any other choice is refused |
| `sampling_method` | `CENSUS_BASED` | Recorded on the sampling design |
| `min_samples_per_stratum` | `2` | Every stratum in a sampling design needs at least this many points |
| `statistical_design` | `SYSTEMATIC_GRID` | The sampling design must use this design |

### 10.2 Monitoring rules — the data the project collects (8)
| Code | What to record | Unit | Level | Source | Frequency | Methodology reference |
|---|---|---|---|---|---|---|
| `V47_N` | Planting units in the complete census (initial population N) | units | Stratum | Field activity | Census at t = 0 (repeat the value each period) | VM0047 v1.1 Eq. 24 N; §4.3(4) |
| `V47_ALIVE` | Sampled planting unit alive (1) or dead / not relocated (0) | flag | Sampling point | Field | Each monitoring event (at most every 5 years) | VM0047 v1.1 Eqs. 24/31 M_t; §4.3(7) |
| `V47_AGB` | Aboveground woody biomass of the sampled unit (published allometric equation; 0 below the size threshold) | kg d.m. | Sampling point | Field | Each monitoring event (at most every 5 years) | VM0047 v1.1 Eq. 25 B_WP-woody-AB,pu,t; §9.2 |
| `V47_BURNED` | Sampled planting unit visibly burned in the interval (1) or not (0) | flag | Sampling point | Field | Each monitoring event (at most every 5 years) | VM0047 v1.1 Eq. 27 n_burn,t |
| `V47_FSN` | Synthetic fertiliser N applied to planting units (mass x N content) | kg N | Farm | Field activity | Per application, summed for the interval | VM0047 v1.1 Eqs. 16/17 F_wp,SN,t |
| `V47_FON` | Organic fertiliser N applied to planting units (mass x N content) | kg N | Farm | Field activity | Per application, summed for the interval | VM0047 v1.1 Eqs. 16/18 F_wp,ON,t |
| `V47_ROOT_SHOOT` | Root-to-shoot ratio R (species / genus / family, same ecoregion; IPCC 2019 Table 4.4) | ratio | Project | Field activity | Validation | VM0047 v1.1 Eq. 25 R; §9.1 |
| `V47_NPR` | AFOLU non-permanence risk rating | % | Project | Field activity | Each verification | VCS Standard v5.0 §3.14.15; AFOLU NPRT v5.0 |

### 10.3 Calculation rules — the steps (8)
| # | Code | Step | What it calculates | Equation reference |
|---|---|---|---|---|
| 1 | `V47-BSL` | BASELINE | Baseline (zero: no planting units without the project) | VM0047 v1.1 §6.2, §8.1.2 |
| 2 | `V47-PRJ` | PROJECT | Woody carbon stock of the planting units (census x survival x mean carbon) | VM0047 v1.1 Eqs. 22-25 |
| 3 | `V47-PE` | EMISSIONS | Project emissions: biomass burning and N fertiliser | VM0047 v1.1 Eqs. 12, 15-21, 26, 27 |
| 4 | `V47-REM` | REMOVALS | Carbon stock change through year t and t - x (t CO2e) | VM0047 v1.1 Eqs. 22, 23 |
| 5 | `V47-LK` | LEAKAGE | Leakage (zero for the census-based approach) | VM0047 v1.1 §8.4 |
| 6 | `V47-UNC` | UNCERTAINTY | Sampling uncertainty of biomass and mortality (deduction above 10 %) | VM0047 v1.1 Eqs. 29-31, §8.5.2 |
| 7 | `V47-ADJ` | ADJUSTMENT | Removals in the interval; AFOLU non-permanence buffer | VM0047 v1.1 Eqs. 33, 34; VCS Standard v5.0 §3.14.15; AFOLU NPRT §2.5 |
| 8 | `V47-NET` | NET | VCUs (whole tonnes, rounded down) | VCS Standard v5.0 §3.14.15 |

### 10.4 Calculation inputs (12)
| Input | Comes from | Rule / parameter | Unit | Level | Round | Required |
|---|---|---|---|---|---|---|
| `N` | Monitoring data | V47_N | units | Stratum | period calculated | **Yes** |
| `ALIVE` | Monitoring data | V47_ALIVE | flag | Sampling point | period calculated | **Yes** |
| `AGB` | Monitoring data | V47_AGB | kg d.m. | Sampling point | period calculated | **Yes** |
| `BURNED` | Monitoring data | V47_BURNED | flag | Sampling point | period calculated | No (0 if missing) |
| `ALIVE_T0` | Monitoring data | V47_ALIVE | flag | Sampling point | previous round | No (0 if missing) |
| `AGB_T0` | Monitoring data | V47_AGB | kg d.m. | Sampling point | previous round | No (0 if missing) |
| `N_T0` | Monitoring data | V47_N | units | Stratum | previous round | No (0 if missing) |
| `AREA` | Stratum area (SQL Server) | — | ha | Stratum | period calculated | No (0 if missing) |
| `FSN` | Monitoring data | V47_FSN | kg N | Farm | period calculated | No (0 if missing) |
| `FON` | Monitoring data | V47_FON | kg N | Farm | period calculated | No (0 if missing) |
| `ROOT_SHOOT` | Monitoring data | V47_ROOT_SHOOT | ratio | Project | period calculated | **Yes** |
| `NPR` | Monitoring data | V47_NPR | % | Project | period calculated | **Yes** |

### 10.5 Constants built into the module (16)
| Constant | Value | Unit | Source |
|---|---|---|---|
| `C_TO_CO2` | 3.66667 | t CO2/t C | 44/12 (VM0047 v1.1 Eq. 22) |
| `N2ON_TO_N2O` | 1.57143 | t N2O/t N2O-N | 44/28 (VM0047 v1.1 Eqs. 16, 20, 21) |
| `CF` | 0.47 | t C/t d.m. | VM0047 v1.1 §9.1 CF (2006 IPCC Guidelines) |
| `GWP_CH4` | 28 | t CO2e/t CH4 | VCS Standard v5.0 §3.14.4 Table 9 (IPCC AR5) |
| `GWP_N2O` | 265 | t CO2e/t N2O | VCS Standard v5.0 §3.14.4 Table 9 (IPCC AR5) |
| `COMF` | 1.0 | fraction | VM0047 v1.1 §9.1 COMF (census-based: 1.0) |
| `EF_BB_CH4` | 6.8 | kg CH4/t d.m. | IPCC 2006 Vol. 4 Ch. 2 Table 2.5 (tropical forest, highest forest CH4 factor) |
| `EF_BB_N2O` | 0.26 | kg N2O/t d.m. | IPCC 2006 Vol. 4 Ch. 2 Table 2.5 (extra-tropical forest, highest forest N2O factor) |
| `EF_NDIRECT` | 0.01 | t N2O-N/t N | VM0047 v1.1 §9.1 (IPCC 2019 Table 11.1) |
| `FRAC_GASF` | 0.11 | fraction | VM0047 v1.1 §9.1 (IPCC 2019 Table 11.3) |
| `FRAC_GASM` | 0.21 | fraction | VM0047 v1.1 §9.1 (IPCC 2019 Table 11.3) |
| `EF_NVOLAT` | 0.01 | t N2O-N/t N volatilised | VM0047 v1.1 §9.1 (IPCC 2019 Table 11.3) |
| `FRAC_LEACH` | 0.24 | fraction | VM0047 v1.1 §9.1 (IPCC 2019 Table 11.3) |
| `EF_NLEACH` | 0.011 | t N2O-N/t N leached | VM0047 v1.1 §9.1 (IPCC 2019 Table 11.3) |
| `UNC_ALLOWANCE` | 0.10 | fraction | VM0047 v1.1 Eq. 29 (- 0.10) |
| `NPR_MIN` | 12 | % | AFOLU Non-Permanence Risk Tool v5.0 §2.5.2 (minimum overall rating) |
| `NPR_MAX` | 60 | % | AFOLU Non-Permanence Risk Tool v5.0 §2.5.3 (above 60 the project fails the risk analysis) |

### 10.6 Outputs
Outputs written by this module's code (some appear only for the approach or activity module in use; `<stratum>` = one output per stratum).

| Output | Step |
|---|---|
| `BASELINE_STOCK_CHANGE` | BASELINE |
| `MORTALITY_<stratum>` | PROJECT |
| `C_PU_AVG_<stratum>` | PROJECT |
| `C_WOODY_<stratum>` | PROJECT |
| `PE_BURN` | EMISSIONS |
| `PE_FERT` | EMISSIONS |
| `PE_TOTAL` | EMISSIONS |
| `DC_WP_T` | REMOVALS |
| `DC_WP_T_X` | REMOVALS |
| `LK_TOTAL` | LEAKAGE |
| `HALF_WIDTH_<stratum>` | UNCERTAINTY |
| `STOCK_CHANGE_ADJ` | ADJUSTMENT |
| `CR_T` | ADJUSTMENT |
| `CR_ANNUALIZED` | ADJUSTMENT |
| `NPR_PCT` | ADJUSTMENT |
| `BUFFER` | ADJUSTMENT |
| `NET_REMOVALS` | NET |
| `REVERSAL` | NET |
| `VCU_TOTAL` | NET |

### 10.7 Interpretations made by the code (for the expert review)
- Sampled planting units are sampling points (one per unit); M_t = dead / sampled; Eq. 25 averages the live sampled units only (dead units enter through 1 - M_t, so mortality is not counted twice).
- Biomass per sampled unit is entered in kg d.m. from the documented allometric equation (species > genus > family, same ecoregion); live units below the fixed size threshold are entered as 0.
- Eq. 29 read dimensionally: per stratum, relative half-width = sqrt((T x SE / mean carbon per unit)^2 + U_M^2) with U_M from Eq. 31 as a fraction; strata are combined by adding half-widths in quadrature; UNC = min(1, max(0, relative half-width - 0.10)). T is the two-tailed 90 % Student-t with n - 1 degrees of freedom.
- §8.5.2: no removals are credited when the 90 % half-width exceeds 100 % of the stock (CR_t = 0).
- Eq. 33: dC(t - x) and UNC(t - x) come from the previous approved period. dC(t - x) = 0 only at the first verification: the previous approved period is the project's first monitoring period (the census at t = 0) and has no biomass sample in any stratum. Otherwise a stratum without previous biomass samples blocks the run (PREVIOUS_STOCK_MISSING), so a stock already credited is never credited again.
- Eq. 27: biomass subject to burning uses the previous period's mean biomass of the stratum (the current mean when there is none).
- Burning factors: the highest IPCC 2006 Table 2.5 forest factors (CH4 6.8, N2O 0.26 kg/t d.m.); VM0047 §9.1 cites a stationary-combustion table by mistake.
- Fertiliser: Frac_LEACH always applied (conservative); fertiliser N is recorded as mass x N content (Eqs. 17/18).
- Leakage is zero (§8.4). Buffer = max(rating, 12) % x the uncertainty-adjusted stock change of the interval (stock change only, never negative); VCUs = removals - buffer, whole tonnes rounded down; a negative result is a REVERSAL. A rating outside 0-100 % or above 60 % (the project fails the risk analysis, NPRT §2.5.3) blocks the run.
- Every stratum with a census population needs its area (the 50 units/ha census density limit, §4.3(3), is always checked); conflicting root-to-shoot ratios (V47_ROOT_SHOOT) block the run (one value is used for all units).
- Per-stratum outputs are named by the stratum code, or by a collision-free prefix of the stratum record id when it is not available.
- GWPs: IPCC AR5 (VCS Standard v5.0 §3.14.4).

### 10.8 Reasons the calculation can be blocked
`DENSITY_EXCEEDED`, `DUPLICATE_INPUT`, `INSUFFICIENT_SAMPLES`, `MISSING_REQUIRED_INPUT`. Added 29/10: `PREVIOUS_STOCK_MISSING` (no sampled unit in the previous approved period after the first verification), `NPR_UNACCEPTABLE` (rating above 60), `INVALID_INPUT` (rating outside 0-100, negative R), `INCONSISTENT_INPUT` (conflicting root-to-shoot ratios), `MISSING_REQUIRED_INPUT` `STRATUM_AREA_MISSING`.

---

## 11. VM0044 1.2 — VM0044-V1.2

| | |
|---|---|
| Standard | Verra (VCS) |
| Methodology | Biochar Utilization in Soil and Non-Soil Applications |
| Methodology code / version label to create | `VM0044` / `1.2` (or `1.2-<suffix>`) |
| Calculation module | `VM0044-V1.2` · module version 1.1.0 |
| Option text on the Calculation tab | VM0044 v1.2 - biochar in soil and non-soil applications |
| Suitable for | Biochar produced from biomass (e.g. crop residue) and applied to soil or used in non-soil applications. |
| Field / laboratory work | Laboratory results of the biochar (carbon content, H:C ratio) entered as values |
| Readiness | Not Production Ready |

### 11.1 Sampling rule (`MODULE-SAMPLING`)
None — this module needs no sampling design rule (no soil sampling).

### 11.2 Monitoring rules — the data the project collects (14)
| Code | What to record | Unit | Level | Source | Frequency | Methodology reference |
|---|---|---|---|---|---|---|
| `V44_PRODUCED` | Biochar produced, dry mass (all uses, including unsold stock) | t | Project | Field activity | Per batch / application (summed for the period) | VM0044 Eqs. 3/7 M_p,y |
| `V44_USED_SOIL` | Biochar applied to soil, dry mass (H:C_org <= 0.7, within 1 year of production) | t | Project | Field activity | Per batch / application (summed for the period) | VM0044 Eq. 2 M_t,k,p,y (k = soil) |
| `V44_USED_NONSOIL` | Biochar used in non-soil applications, dry mass (concrete, asphalt, ...) | t | Project | Field activity | Per batch / application (summed for the period) | VM0044 Eq. 2 M_t,k,p,y (k = non-soil) |
| `V44_FCP` | Organic carbon content of the biochar (laboratory, dry basis, as a fraction) | fraction | Project | Field activity | At least annually and after a material change | VM0044 Eqs. 2/6 F_Cp (lab analysis at least annually) |
| `V44_HC_RATIO` | H:C_org molar ratio of the batch (laboratory) | ratio | Project | Field activity | Each batch | VM0044 §4 condition 10 (<= 0.7 for soil) |
| `V44_TEMP` | Production (pyrolysis) temperature, period average | degC | Project | Field activity | Continuous, averaged for the period | VM0044 Table 3 T_prod |
| `V44_TECH` | Production technology: HIGH or LOW | — | Project | Field activity | Validation | VM0044 §3 high / low technology; Options P.1 / P.2 |
| `V44_FEEDSTOCK` | Feedstock class: WOOD, HERBACEOUS, RICE, NUTSHELL, MANURE or BIOSOLIDS | — | Project | Field activity | Validation and when it changes | VM0044 Table 4 (mixed feedstock: the class with the lowest value) |
| `V44_PROCESS` | Conversion process: PYROLYSIS or GASIFICATION | — | Project | Field activity | Validation | VM0044 Table 4 |
| `V44_FE` | CH4 emitted per tonne of biochar (low technology; kiln-specific, Cornelissen et al. 2016) | t CH4/t | Project | Field activity | Validation | VM0044 Eq. 9 F_e (default 0.049) |
| `V44_PE_PRETREAT` | Pre-treatment emissions (grid electricity TOOL05 + fossil fuel TOOL03; 0 if renewable) | t CO2e | Project | Field activity | Per period | VM0044 Eqs. 4/8 P_ED |
| `V44_PE_AUX` | Auxiliary energy emissions of the reactor (TOOL05 + TOOL03; 0 if renewable) | t CO2e | Project | Field activity | Per period | VM0044 Eqs. 5/10 P_EC |
| `V44_PE_PROCESSING` | Biochar processing emissions before application (TOOL05 + TOOL03) | t CO2e | Project | Field activity | Per period | VM0044 Eqs. 11/12 E_P |
| `V44_LE_TRANSPORT` | Transport emissions of feedstock and biochar (TOOL12; only legs with a round trip of 200 km or more) | t CO2e | Project | Field activity | Per period | VM0044 Eq. 13 LE_ts + LE_tap |

### 11.3 Calculation rules — the steps (8)
| # | Code | Step | What it calculates | Equation reference |
|---|---|---|---|---|
| 1 | `V44-BSL` | BASELINE | Baseline and sourcing reductions (zero) | VM0044 v1.2 §8.1, Eq. 14 |
| 2 | `V44-PRJ` | PROJECT | Persistent organic carbon of the biochar used (CC) | VM0044 v1.2 Eqs. 2, 6; Tables 3, 4 |
| 3 | `V44-PE` | EMISSIONS | Production-stage and application-stage project emissions | VM0044 v1.2 Eqs. 3-5, 7-12 |
| 4 | `V44-REM` | REMOVALS | Removals at the production stage | VM0044 v1.2 Eq. 1 |
| 5 | `V44-LK` | LEAKAGE | Leakage (transport of feedstock and biochar) | VM0044 v1.2 Eq. 13 |
| 6 | `V44-UNC` | UNCERTAINTY | Uncertainty (none in VM0044: conservative defaults) | VM0044 v1.2 §8 |
| 7 | `V44-ADJ` | ADJUSTMENT | Buffer (none: permanence is the decay factor PR_de) | VM0044 v1.2 §8.4 |
| 8 | `V44-NET` | NET | Net reductions and removals; VCUs (whole tonnes, rounded down) | VM0044 v1.2 Eq. 15 |

### 11.4 Calculation inputs (14)
| Input | Comes from | Rule / parameter | Unit | Level | Round | Required |
|---|---|---|---|---|---|---|
| `PRODUCED` | Monitoring data | V44_PRODUCED | t | Project | period calculated | **Yes** |
| `USED_SOIL` | Monitoring data | V44_USED_SOIL | t | Project | period calculated | No (0 if missing) |
| `USED_NONSOIL` | Monitoring data | V44_USED_NONSOIL | t | Project | period calculated | No (0 if missing) |
| `FCP` | Monitoring data | V44_FCP | fraction | Project | period calculated | No (0 if missing) |
| `HC_RATIO` | Monitoring data | V44_HC_RATIO | ratio | Project | period calculated | No (0 if missing) |
| `TEMP` | Monitoring data | V44_TEMP | degC | Project | period calculated | No (0 if missing) |
| `TECH` | Monitoring data | V44_TECH | — | Project | period calculated | **Yes** |
| `FEEDSTOCK` | Monitoring data | V44_FEEDSTOCK | — | Project | period calculated | No (0 if missing) |
| `PROCESS` | Monitoring data | V44_PROCESS | — | Project | period calculated | No (0 if missing) |
| `FE` | Monitoring data | V44_FE | t CH4/t | Project | period calculated | No (0 if missing) |
| `PE_PRETREAT` | Monitoring data | V44_PE_PRETREAT | t CO2e | Project | period calculated | No (0 if missing) |
| `PE_AUX` | Monitoring data | V44_PE_AUX | t CO2e | Project | period calculated | No (0 if missing) |
| `PE_PROCESSING` | Monitoring data | V44_PE_PROCESSING | t CO2e | Project | period calculated | No (0 if missing) |
| `LE_TRANSPORT` | Monitoring data | V44_LE_TRANSPORT | t CO2e | Project | period calculated | No (0 if missing) |

### 11.5 Constants built into the module (20)
| Constant | Value | Unit | Source |
|---|---|---|---|
| `C_TO_CO2` | 3.66667 | t CO2/t C | 44/12 (VM0044 v1.2 Eq. 1) |
| `GWP_CH4` | 28 | t CO2e/t CH4 | VM0044 v1.2 §9.1 GWP_CH4; VCS Standard v5.0 Table 9 (IPCC AR5) |
| `FE_DEFAULT` | 0.049 | t CH4/t | VM0044 v1.2 Eq. 9 F_e default (traditional kilns) |
| `PR_HIGH` | 0.89 | fraction | VM0044 v1.2 Table 3 (> 600 degC) |
| `PR_MEDIUM` | 0.80 | fraction | VM0044 v1.2 Table 3 (450-600 degC) |
| `PR_LOW` | 0.65 | fraction | VM0044 v1.2 Table 3 (350-450 degC) |
| `PR_UNKNOWN` | 0.56 | fraction | VM0044 v1.2 §8.2.2 (temperature unknown; IPCC 2019 Fig. 4Ap.1(b)) |
| `HC_MAX` | 0.7 | ratio | VM0044 v1.2 §4 condition 10 (soil use) |
| `FCP_MANURE_PYROLYSIS` | 0.38 | fraction | VM0044 v1.2 Table 4 (manure, pyrolysis) |
| `FCP_MANURE_GASIFICATION` | 0.09 | fraction | VM0044 v1.2 Table 4 (manure, gasification) |
| `FCP_WOOD_PYROLYSIS` | 0.77 | fraction | VM0044 v1.2 Table 4 (wood, pyrolysis) |
| `FCP_WOOD_GASIFICATION` | 0.52 | fraction | VM0044 v1.2 Table 4 (wood, gasification) |
| `FCP_HERBACEOUS_PYROLYSIS` | 0.65 | fraction | VM0044 v1.2 Table 4 (herbaceous, pyrolysis) |
| `FCP_HERBACEOUS_GASIFICATION` | 0.28 | fraction | VM0044 v1.2 Table 4 (herbaceous, gasification) |
| `FCP_RICE_PYROLYSIS` | 0.49 | fraction | VM0044 v1.2 Table 4 (rice, pyrolysis) |
| `FCP_RICE_GASIFICATION` | 0.13 | fraction | VM0044 v1.2 Table 4 (rice, gasification) |
| `FCP_NUTSHELL_PYROLYSIS` | 0.74 | fraction | VM0044 v1.2 Table 4 (nutshell, pyrolysis) |
| `FCP_NUTSHELL_GASIFICATION` | 0.40 | fraction | VM0044 v1.2 Table 4 (nutshell, gasification) |
| `FCP_BIOSOLIDS_PYROLYSIS` | 0.35 | fraction | VM0044 v1.2 Table 4 (biosolids, pyrolysis) |
| `FCP_BIOSOLIDS_GASIFICATION` | 0.07 | fraction | VM0044 v1.2 Table 4 (biosolids, gasification) |

### 11.6 Outputs
Outputs written by this module's code (some appear only for the approach or activity module in use; `<stratum>` = one output per stratum).

| Output | Step |
|---|---|
| `ER_SS` | BASELINE |
| `M_USED` | PROJECT |
| `F_CP` | PROJECT |
| `PR_DE` | PROJECT |
| `CC` | PROJECT |
| `P_EP` | EMISSIONS |
| `PE_PS` | EMISSIONS |
| `PE_AS` | EMISSIONS |
| `CC_CO2` | REMOVALS |
| `ER_PS` | REMOVALS |
| `LE` | LEAKAGE |
| `UNC` | UNCERTAINTY |
| `BUFFER` | ADJUSTMENT |
| `ER_NET` | NET |
| `VCU_TOTAL` | NET |

### 11.7 Interpretations made by the code (for the expert review)
- One project = one production facility; quantities are the period totals of the batch and application records.
- Table 3 boundaries: > 600 degC -> 0.89; > 450 to 600 -> 0.80; 350 to 450 (450 itself, where the table overlaps) -> 0.65; below 350 or not measured -> 0.56 (the table does not cover < 350 degC; the unknown-temperature value is the conservative choice).
- High technology requires laboratory F_Cp and a measured temperature; low technology uses laboratory F_Cp when recorded, otherwise Table 4 (mixed feedstock: record the class with the lowest value).
- Non-soil applications use the Table 3 soil value (VM0044 §8.2.1: the soil value unless robust permanence evidence gives a lower one; no alternative value is configured). Non-soil use of low-technology biochar is refused (condition 11: non-soil applications only for high-technology facilities).
- Soil biochar needs H:C_org results (condition 10); soil biochar with no H:C_org record or with any batch above 0.7 is refused.
- F_Cp and the production temperature are mass-weighted over the period: one recorded value applies to the whole period; several values are weighted by the biochar produced (V44_PRODUCED) on the same observed-on date, and values that cannot be matched to exactly one production date block the run (a simple mean is never taken).
- Eq. 1: production emissions are subtracted once per facility (the t index of PE_PS is not repeated per biochar type).
- Eq. 9 / A8: the kiln methane is computed on the biochar produced (F_e x GWP_CH4 x M_produced) and then allocated by M_used / M_produced with the other production emissions (Eqs. 3/7), so the methane of the used biochar is counted once in full (the literal reading, Eq. 9 on M_used, would scale it down twice).
- Electricity, fossil fuel and freight are calculated with CDM TOOL05 / TOOL03 / TOOL12 outside the platform and recorded in t CO2e; transport legs with a round trip under 200 km are not recorded (zero).
- No uncertainty deduction and no buffer (VM0044 has neither); VCUs are whole tonnes rounded down; a negative balance gives no VCUs.

### 11.8 Reasons the calculation can be blocked
`INCONSISTENT_INPUT`, `INELIGIBLE_BIOCHAR`, `INVALID_INPUT`, `MISSING_REQUIRED_INPUT`. Added 29/10: `MISSING_REQUIRED_INPUT` `HC_RATIO_MISSING` (soil use without H:C_org), `INELIGIBLE_BIOCHAR` `NONSOIL_LOW_TECH`, `INVALID_INPUT` `NOT_MASS_WEIGHTABLE` (several F_Cp / temperature values not dated like one production batch each).

---

## 12. BM-FR05.002 1.0 — CCTS-FR05.002

| | |
|---|---|
| Standard | India CCTS |
| Methodology | BM FR05.002 — Afforestation / reforestation of lands except wetlands |
| Methodology code / version label to create | `BM-FR05.002` / `1.0` (or `1.0-<suffix>`) |
| Calculation module | `CCTS-FR05.002` · module version 1.1.0 |
| Option text on the Calculation tab | CCTS BM FR05.002 v1.0 - afforestation / reforestation of lands except wetlands |
| Suitable for | Tree plantations on degraded or non-forest land in India, credited under the Carbon Credit Trading Scheme. |
| Field / laboratory work | No soil sampling — plot inventory (tree biomass) |
| Readiness | Not Production Ready |

### 12.1 Sampling rule (`MODULE-SAMPLING`)
| Parameter | Value | Effect in the platform |
|---|---|---|
| `quantification_approach` | `OTHER` | The MRV plan's approach is set to this value; any other choice is refused |
| `sampling_method` | `PLOT_SAMPLING` | Recorded on the sampling design |
| `min_samples_per_stratum` | `2` | Every stratum in a sampling design needs at least this many points |
| `statistical_design` | `STRATIFIED_RANDOM` | The sampling design must use this design |

### 12.2 Monitoring rules — the data the project collects (8)
| Code | What to record | Unit | Level | Source | Frequency | Methodology reference |
|---|---|---|---|---|---|---|
| `AR_PLOT_AGB` | Above-ground tree biomass in the sample plot (sum of the trees' allometric / volume x density x BEF biomass) | t d.m. | Sampling point | Field | Each verification | BM-T-AR-0004 Appendix 1 Eqs. 2-5 (B_TREE,p,i without roots) |
| `AR_PLOT_AREA` | Size of the sample plots | ha | Project | Field | Each verification | BM-T-AR-0004 Appendix 1 Eq. 1 A_PLOT,i |
| `AR_BSL_STOCK` | Pre-project carbon stock of trees and shrubs (crown-cover method, or 0) | t CO2e | Project | Field activity | Project start | BM-T-AR-0004 Eqs. 20-21; Eq. 1 note 1 (C_TREE,t1 at the first verification) |
| `AR_BSL_CHANGE` | Baseline removals in the period (trees and shrubs; 0 when the tool's conditions are met) | t CO2e | Project | Field activity | Each verification | FR05.002 Eq. 1; BM-T-AR-0004 Eqs. 9-10 |
| `AR_SHRUB_CC` | Shrub crown cover of the stratum (fraction) | fraction | Stratum | Field | Each verification | BM-T-AR-0004 Eq. 27 CC_SHRUB,i |
| `AR_B_FOREST` | Default above-ground forest biomass of the region (IPCC GPG-LULUCF) | t d.m./ha | Project | Field activity | Validation | BM-T-AR-0004 Eq. 27 b_FOREST |
| `AR_GHG_E` | Non-CO2 emissions from burning woody biomass (BM-T-AR-0002) | t CO2e | Project | Field activity | Each verification | FR05.002 Eq. 2 GHG_E,t |
| `AR_LK` | Leakage from displacement of agricultural activities (BM-T-AR-0005) | t CO2e | Project | Field activity | Each verification | FR05.002 Eq. 4 LK_AGRIC,t |

### 12.3 Calculation rules — the steps (8)
| # | Code | Step | What it calculates | Equation reference |
|---|---|---|---|---|
| 1 | `AR-BSL` | BASELINE | Carbon stock at the previous verification (or pre-project) and baseline removals | FR05.002 Eq. 1; BM-T-AR-0004 Eqs. 1, 9-10, 20-21 |
| 2 | `AR-PRJ` | PROJECT | Tree and shrub carbon stock at this verification (plot sampling) | BM-T-AR-0004 Eqs. 12-17, 26-27; Appendix 1 |
| 3 | `AR-PE` | EMISSIONS | Non-CO2 emissions from burning woody biomass | FR05.002 Eq. 2; BM-T-AR-0002 |
| 4 | `AR-REM` | REMOVALS | Change in project carbon stocks | FR05.002 Eq. 3; BM-T-AR-0004 Eq. 1 |
| 5 | `AR-LK` | LEAKAGE | Leakage (displacement of agricultural activities) | FR05.002 Eq. 4; BM-T-AR-0005 |
| 6 | `AR-UNC` | UNCERTAINTY | Uncertainty of the stock change (90 %) | BM-T-AR-0004 Eqs. 2, 15 |
| 7 | `AR-ADJ` | ADJUSTMENT | Uncertainty discount above 10 % | BM-T-AR-0004 Appendix 2 |
| 8 | `AR-NET` | NET | Net anthropogenic removals; lCCC for the verification period | FR05.002 Eqs. 5-7 |

### 12.4 Calculation inputs (13)
| Input | Comes from | Rule / parameter | Unit | Level | Round | Required |
|---|---|---|---|---|---|---|
| `PLOT_AGB` | Monitoring data | AR_PLOT_AGB | t d.m. | Sampling point | period calculated | **Yes** |
| `PLOT_AREA` | Monitoring data | AR_PLOT_AREA | ha | Project | period calculated | **Yes** |
| `PLOT_AGB_T0` | Monitoring data | AR_PLOT_AGB | t d.m. | Sampling point | previous round | No (0 if missing) |
| `PLOT_AREA_T0` | Monitoring data | AR_PLOT_AREA | ha | Project | previous round | No (0 if missing) |
| `AREA` | Stratum area (SQL Server) | — | ha | Stratum | period calculated | **Yes** |
| `AREA_T0` | Stratum area (SQL Server) | — | ha | Stratum | previous round | No (0 if missing) |
| `BSL_STOCK` | Monitoring data | AR_BSL_STOCK | t CO2e | Project | period calculated | No (0 if missing) |
| `BSL_CHANGE` | Monitoring data | AR_BSL_CHANGE | t CO2e | Project | period calculated | No (0 if missing) |
| `SHRUB_CC` | Monitoring data | AR_SHRUB_CC | fraction | Stratum | period calculated | No (0 if missing) |
| `SHRUB_CC_T0` | Monitoring data | AR_SHRUB_CC | fraction | Stratum | previous round | No (0 if missing) |
| `B_FOREST` | Monitoring data | AR_B_FOREST | t d.m./ha | Project | period calculated | No (0 if missing) |
| `GHG_E` | Monitoring data | AR_GHG_E | t CO2e | Project | period calculated | No (0 if missing) |
| `LK` | Monitoring data | AR_LK | t CO2e | Project | period calculated | No (0 if missing) |

### 12.5 Constants built into the module (5)
| Constant | Value | Unit | Source |
|---|---|---|---|
| `C_TO_CO2` | 3.66667 | t CO2/t C | 44/12 (BM-T-AR-0004 Eq. 12) |
| `CF_TREE` | 0.47 | t C/t d.m. | BM-T-AR-0004 Eq. 12 CF_TREE default |
| `CF_SHRUB` | 0.47 | t C/t d.m. | BM-T-AR-0004 Eq. 26 CF_s default |
| `R_SHRUB` | 0.40 | ratio | BM-T-AR-0004 Eq. 26 R_s default |
| `BDR_SF` | 0.10 | ratio | BM-T-AR-0004 Eq. 27 BDR_SF default |

### 12.6 Outputs
Outputs written by this module's code (some appear only for the approach or activity module in use; `<stratum>` = one output per stratum).

| Output | Step |
|---|---|
| `C_T1` | BASELINE |
| `U_T1` | BASELINE |
| `DC_BSL` | BASELINE |
| `B_TREE_MEAN` | PROJECT |
| `C_TREE_T2` | PROJECT |
| `C_SHRUB_T2` | PROJECT |
| `U_T2` | PROJECT |
| `C_T2` | PROJECT |
| `GHG_E` | EMISSIONS |
| `DC_TREES_SHRUBS` | REMOVALS |
| `DSOC` | REMOVALS |
| `LK` | LEAKAGE |
| `U_DC` | UNCERTAINTY |
| `DISCOUNT` | UNCERTAINTY |
| `DC_TREES_SHRUBS_ADJ` | ADJUSTMENT |
| `DC_P` | NET |
| `DC_AR` | NET |
| `REPLACEMENT_DUE` | NET |
| `LCCC` | NET |

### 12.7 Interpretations made by the code (for the expert review)
- Sample plots are the sampling points of the period's design; each records the plot's above-ground tree biomass (t d.m.) from the species allometric equation (or volume x density x BEF 1.15); the per-tree sheets are attached as evidence.
- Below-ground biomass per plot: R = e^(-1.085 + 0.9256 ln b) / b with b = the plot's above-ground biomass per ha (Appendix 1).
- Stock change = difference of two independent estimates (Eqs. 1-2): the current campaign minus the previous approved campaign, or minus the pre-project stock (AR_BSL_STOCK, 0 when not recorded) at the first verification; the previous estimate is used undiscounted (Eq. 1 note 2). The pre-project stock replaces the previous campaign only when the previous approved period is the project's first monitoring period (#1); otherwise a previous period without sample plots, or a stratum with plots now but none in the previous campaign, blocks the run (PREVIOUS_STOCK_MISSING) so a stock already credited is never credited again.
- Appendix 2 discount is applied to the stock change (a project estimate: decreased by discount x U x |dC|).
- Shrubs (optional): crown cover per stratum x BDR_SF 0.10 x b_FOREST; < 5 % crown cover = 0.
- Dead wood and litter (optional pools) are excluded (conservative); FR05.002 SOC (BM-T-AR-0006) is not included.
- Burning emissions and leakage are recorded in t CO2e from BM-T-AR-0002 / BM-T-AR-0005; baseline removals from BM-T-AR-0004 Eqs. 9-10 (0 when its conditions are met).
- Credits: lCCC = net removals of the verification period (Eq. 7), whole units rounded down; a negative lCCC is reported as REPLACEMENT_DUE (para 21). tCCC (Eq. 6) is the running sum of the lCCC of all verifications, kept by the registry.

### 12.8 Reasons the calculation can be blocked
`INSUFFICIENT_SAMPLES`, `MISSING_REQUIRED_INPUT`. Added 29/10: `PREVIOUS_STOCK_MISSING` (no plots in the previous approved period after the first verification, or a stratum with plots now but none in the previous campaign).

---

## 13. BM-FR05.001 1.0 — CCTS-FR05.001

| | |
|---|---|
| Standard | India CCTS |
| Methodology | BM FR05.001 — Afforestation / reforestation of degraded mangrove habitats |
| Methodology code / version label to create | `BM-FR05.001` / `1.0` (or `1.0-<suffix>`) |
| Calculation module | `CCTS-FR05.001` · module version 1.1.0 |
| Option text on the Calculation tab | CCTS BM FR05.001 v1.0 - afforestation / reforestation of degraded mangrove habitats |
| Suitable for | Mangrove restoration in India under the Carbon Credit Trading Scheme. |
| Field / laboratory work | No soil sampling — plot inventory (tree biomass) |
| Readiness | Not Production Ready |

### 13.1 Sampling rule (`MODULE-SAMPLING`)
| Parameter | Value | Effect in the platform |
|---|---|---|
| `quantification_approach` | `OTHER` | The MRV plan's approach is set to this value; any other choice is refused |
| `sampling_method` | `PLOT_SAMPLING` | Recorded on the sampling design |
| `min_samples_per_stratum` | `2` | Every stratum in a sampling design needs at least this many points |
| `statistical_design` | `STRATIFIED_RANDOM` | The sampling design must use this design |

### 13.2 Monitoring rules — the data the project collects (9)
| Code | What to record | Unit | Level | Source | Frequency | Methodology reference |
|---|---|---|---|---|---|---|
| `AR_PLOT_AGB` | Above-ground tree biomass in the sample plot (sum of the trees' allometric / volume x density x BEF biomass) | t d.m. | Sampling point | Field | Each verification | BM-T-AR-0004 Appendix 1 Eqs. 2-5 (B_TREE,p,i without roots) |
| `AR_PLOT_AREA` | Size of the sample plots | ha | Project | Field | Each verification | BM-T-AR-0004 Appendix 1 Eq. 1 A_PLOT,i |
| `AR_BSL_STOCK` | Pre-project carbon stock of trees and shrubs (crown-cover method, or 0) | t CO2e | Project | Field activity | Project start | BM-T-AR-0004 Eqs. 20-21; Eq. 1 note 1 (C_TREE,t1 at the first verification) |
| `AR_BSL_CHANGE` | Baseline removals in the period (trees and shrubs; 0 when the tool's conditions are met) | t CO2e | Project | Field activity | Each verification | FR05.002 Eq. 1; BM-T-AR-0004 Eqs. 9-10 |
| `AR_SHRUB_CC` | Shrub crown cover of the stratum (fraction) | fraction | Stratum | Field | Each verification | BM-T-AR-0004 Eq. 27 CC_SHRUB,i |
| `AR_B_FOREST` | Default above-ground forest biomass of the region (IPCC GPG-LULUCF) | t d.m./ha | Project | Field activity | Validation | BM-T-AR-0004 Eq. 27 b_FOREST |
| `AR_GHG_E` | Non-CO2 emissions from burning woody biomass (BM-T-AR-0002) | t CO2e | Project | Field activity | Each verification | FR05.002 Eq. 2 GHG_E,t |
| `AR_LK` | Leakage from displacement of agricultural activities (BM-T-AR-0005) | t CO2e | Project | Field activity | Each verification | FR05.002 Eq. 4 LK_AGRIC,t |
| `AR_PLANT_YEAR` | Year the stratum was planted | year | Stratum | Field activity | Project start | FR05.001 Eq. 4 t_PLANT |

### 13.3 Calculation rules — the steps (8)
| # | Code | Step | What it calculates | Equation reference |
|---|---|---|---|---|
| 1 | `AR-BSL` | BASELINE | Carbon stock at the previous verification (or pre-project) and baseline removals | FR05.001 Eq. 1; BM-T-AR-0004 Eqs. 1, 9-10, 20-21 |
| 2 | `AR-PRJ` | PROJECT | Tree and shrub carbon stock at this verification (plot sampling) | BM-T-AR-0004 Eqs. 12-17, 26-27; Appendix 1 |
| 3 | `AR-PE` | EMISSIONS | Non-CO2 emissions from burning woody biomass | FR05.001 Eq. 2; BM-T-AR-0002 |
| 4 | `AR-REM` | REMOVALS | Change in project carbon stocks incl. SOC of planted areas | FR05.001 Eq. 3, Eq. 4; BM-T-AR-0004 Eq. 1 |
| 5 | `AR-LK` | LEAKAGE | Leakage (displacement of agricultural activities) | FR05.001 Eq. 5; BM-T-AR-0005 |
| 6 | `AR-UNC` | UNCERTAINTY | Uncertainty of the stock change (90 %) | BM-T-AR-0004 Eqs. 2, 15 |
| 7 | `AR-ADJ` | ADJUSTMENT | Uncertainty discount above 10 % | BM-T-AR-0004 Appendix 2 |
| 8 | `AR-NET` | NET | Net anthropogenic removals; lCCC for the verification period | FR05.001 Eqs. 6-8 |

### 13.4 Calculation inputs (14)
| Input | Comes from | Rule / parameter | Unit | Level | Round | Required |
|---|---|---|---|---|---|---|
| `PLOT_AGB` | Monitoring data | AR_PLOT_AGB | t d.m. | Sampling point | period calculated | **Yes** |
| `PLOT_AREA` | Monitoring data | AR_PLOT_AREA | ha | Project | period calculated | **Yes** |
| `PLOT_AGB_T0` | Monitoring data | AR_PLOT_AGB | t d.m. | Sampling point | previous round | No (0 if missing) |
| `PLOT_AREA_T0` | Monitoring data | AR_PLOT_AREA | ha | Project | previous round | No (0 if missing) |
| `AREA` | Stratum area (SQL Server) | — | ha | Stratum | period calculated | **Yes** |
| `AREA_T0` | Stratum area (SQL Server) | — | ha | Stratum | previous round | No (0 if missing) |
| `BSL_STOCK` | Monitoring data | AR_BSL_STOCK | t CO2e | Project | period calculated | No (0 if missing) |
| `BSL_CHANGE` | Monitoring data | AR_BSL_CHANGE | t CO2e | Project | period calculated | No (0 if missing) |
| `SHRUB_CC` | Monitoring data | AR_SHRUB_CC | fraction | Stratum | period calculated | No (0 if missing) |
| `SHRUB_CC_T0` | Monitoring data | AR_SHRUB_CC | fraction | Stratum | previous round | No (0 if missing) |
| `B_FOREST` | Monitoring data | AR_B_FOREST | t d.m./ha | Project | period calculated | No (0 if missing) |
| `GHG_E` | Monitoring data | AR_GHG_E | t CO2e | Project | period calculated | No (0 if missing) |
| `LK` | Monitoring data | AR_LK | t CO2e | Project | period calculated | No (0 if missing) |
| `PLANT_YEAR` | Monitoring data | AR_PLANT_YEAR | year | Stratum | period calculated | No (0 if missing) |

### 13.5 Constants built into the module (7)
| Constant | Value | Unit | Source |
|---|---|---|---|
| `C_TO_CO2` | 3.66667 | t CO2/t C | 44/12 (BM-T-AR-0004 Eq. 12) |
| `CF_TREE` | 0.47 | t C/t d.m. | BM-T-AR-0004 Eq. 12 CF_TREE default |
| `CF_SHRUB` | 0.47 | t C/t d.m. | BM-T-AR-0004 Eq. 26 CF_s default |
| `R_SHRUB` | 0.40 | ratio | BM-T-AR-0004 Eq. 26 R_s default |
| `BDR_SF` | 0.10 | ratio | BM-T-AR-0004 Eq. 27 BDR_SF default |
| `DSOC_RATE` | 0.50 | t C/ha/yr | FR05.001 Eq. 4 dSOC default (t_PLANT to t_PLANT + 20) |
| `DSOC_YEARS` | 20 | yr | FR05.001 Eq. 4 (20 years after planting) |

### 13.6 Outputs
Outputs written by this module's code (some appear only for the approach or activity module in use; `<stratum>` = one output per stratum).

| Output | Step |
|---|---|
| `C_T1` | BASELINE |
| `U_T1` | BASELINE |
| `DC_BSL` | BASELINE |
| `B_TREE_MEAN` | PROJECT |
| `C_TREE_T2` | PROJECT |
| `C_SHRUB_T2` | PROJECT |
| `U_T2` | PROJECT |
| `C_T2` | PROJECT |
| `GHG_E` | EMISSIONS |
| `DC_TREES_SHRUBS` | REMOVALS |
| `DSOC` | REMOVALS |
| `LK` | LEAKAGE |
| `U_DC` | UNCERTAINTY |
| `DISCOUNT` | UNCERTAINTY |
| `DC_TREES_SHRUBS_ADJ` | ADJUSTMENT |
| `DC_P` | NET |
| `DC_AR` | NET |
| `REPLACEMENT_DUE` | NET |
| `LCCC` | NET |

### 13.7 Interpretations made by the code (for the expert review)
- Sample plots are the sampling points of the period's design; each records the plot's above-ground tree biomass (t d.m.) from the species allometric equation (or volume x density x BEF 1.15); the per-tree sheets are attached as evidence.
- Below-ground biomass per plot: R = e^(-1.085 + 0.9256 ln b) / b with b = the plot's above-ground biomass per ha (Appendix 1).
- Stock change = difference of two independent estimates (Eqs. 1-2): the current campaign minus the previous approved campaign, or minus the pre-project stock (AR_BSL_STOCK, 0 when not recorded) at the first verification; the previous estimate is used undiscounted (Eq. 1 note 2). The pre-project stock replaces the previous campaign only when the previous approved period is the project's first monitoring period (#1); otherwise a previous period without sample plots, or a stratum with plots now but none in the previous campaign, blocks the run (PREVIOUS_STOCK_MISSING) so a stock already credited is never credited again.
- Appendix 2 discount is applied to the stock change (a project estimate: decreased by discount x U x |dC|).
- Shrubs (optional): crown cover per stratum x BDR_SF 0.10 x b_FOREST; < 5 % crown cover = 0.
- Dead wood and litter (optional pools) are excluded (conservative); FR05.002 SOC (BM-T-AR-0006) is not included.
- Burning emissions and leakage are recorded in t CO2e from BM-T-AR-0002 / BM-T-AR-0005; baseline removals from BM-T-AR-0004 Eqs. 9-10 (0 when its conditions are met).
- Credits: lCCC = net removals of the verification period (Eq. 7), whole units rounded down; a negative lCCC is reported as REPLACEMENT_DUE (para 21). tCCC (Eq. 6) is the running sum of the lCCC of all verifications, kept by the registry.

### 13.8 Reasons the calculation can be blocked
`INSUFFICIENT_SAMPLES`, `MISSING_REQUIRED_INPUT`. Added 29/10: `PREVIOUS_STOCK_MISSING` (no plots in the previous approved period after the first verification, or a stratum with plots now but none in the previous campaign).

---

## 14. VM0051 1.1 — VM0051-V1.1-QA3

| | |
|---|---|
| Standard | Verra (VCS) |
| Methodology | Improved Management in Rice Production Systems — Quantification Approach 3 |
| Methodology code / version label to create | `VM0051` / `1.1` (or `1.1-<suffix>`) |
| Calculation module | `VM0051-V1.1-QA3` · module version 1.1.0 |
| Option text on the Calculation tab | VM0051 v1.1 - improved rice management, IPCC emission factors (QA3) |
| Suitable for | Paddy rice methane reduction — water regime (e.g. alternate wetting and drying), pre-season water status, straw and organic amendment management — with IPCC emission factors. |
| Field / laboratory work | No — seasonal field records per farm |
| Readiness | Not Production Ready |

### 14.1 Sampling rule (`MODULE-SAMPLING`)
None — this module needs no sampling design rule (no soil sampling).

### 14.2 Monitoring rules — the data the project collects (17)
| Code | What to record | Unit | Level | Source | Frequency | Methodology reference |
|---|---|---|---|---|---|---|
| `RI_AREA` | Rice area of the field in the season | ha | Farm | Field activity | Each season (record all values of a season with the same observed-on date) | VM0051 A_i / AG04.002 A_g,s |
| `RI_DAYS` | Cultivation period (land preparation to the later of harvest or post-season drainage) | days | Farm | Field activity | Each season (record all values of a season with the same observed-on date) | VM0051 Eq. 8 L_t; IPCC 2019 Eq. 5.1 |
| `RI_WATER` | On-season water regime: CONTINUOUS, SINGLE or MULTIPLE (drainage periods; AWD = MULTIPLE) | — | Farm | Field activity | Each season (record all values of a season with the same observed-on date) | IPCC 2019 Table 5.12 SFw |
| `RI_PRESEASON` | Pre-season water status: SHORT (< 180 days dry), LONG (> 180), VERY_LONG (> 365) or FLOODED (> 30 days) | — | Farm | Field activity | Each season (record all values of a season with the same observed-on date) | IPCC 2019 Table 5.13 SFp |
| `RI_STRAW` | Rice straw incorporated (dry matter) | t/ha | Farm | Field activity | Each season (record all values of a season with the same observed-on date) | IPCC 2019 Eq. 5.3 ROA (straw) |
| `RI_STRAW_TIMING` | Straw incorporated SHORT (< 30 days) or LONG (> 30 days) before cultivation | — | Farm | Field activity | Each season (record all values of a season with the same observed-on date) | IPCC 2019 Table 5.14 CFOA |
| `RI_COMPOST` | Compost applied (fresh weight) | t/ha | Farm | Field activity | Each season (record all values of a season with the same observed-on date) | IPCC 2019 Eq. 5.3 ROA |
| `RI_FYM` | Farmyard manure applied (fresh weight) | t/ha | Farm | Field activity | Each season (record all values of a season with the same observed-on date) | IPCC 2019 Eq. 5.3 ROA |
| `RI_GREEN` | Green manure applied (fresh weight) | t/ha | Farm | Field activity | Each season (record all values of a season with the same observed-on date) | IPCC 2019 Eq. 5.3 ROA |
| `RI_N` | Nitrogen applied (synthetic + organic + residue) | kg N/ha | Farm | Field activity | Each season (record all values of a season with the same observed-on date) | VM0051 Eqs. 19, 25 Q_N |
| `RI_REGION` | IPCC region of the baseline emission factor (WORLD, SOUTH_ASIA, SOUTHEAST_ASIA, EAST_ASIA, EUROPE, ...) | — | Project | Field activity | Validation | IPCC 2019 Table 5.11 |
| `RI_EFC` | Country-specific / measured baseline emission factor (continuously flooded, no amendments; replaces the region value) | kg CH4/ha/day | Project | Field activity | Validation | VM0051 §8.2.3 EF_bsl,c hierarchy; AG04.002 paras 27-28 (reference fields) |
| `RI_UNC` | Uncertainty deduction of a country-specific emission factor (%) | % | Project | Field activity | Validation | VM0051 §8.6 |
| `RI_DIESEL` | Diesel used on the field | L | Farm | Field activity | Each season (record all values of a season with the same observed-on date) | VM0051 Eqs. 1-2 FFC |
| `RI_BURN` | Rice residue burned (dry matter) | kg d.m. | Farm | Field activity | Each season (record all values of a season with the same observed-on date) | VM0051 Eqs. 17, 23 MB |
| `RI_PE_AB` | Emissions of straw diverted to other end uses (Eq. 24) | t CO2e | Project | Field activity | Each verification | VM0051 Eq. 24 |
| `RI_LE` | Leakage: imported organic amendments (Eq. 26) and diverted bioenergy residues (TOOL16) | t CO2e | Project | Field activity | Each verification | VM0051 Eq. 26, §8.4 |

### 14.3 Calculation rules — the steps (8)
| # | Code | Step | What it calculates | Equation reference |
|---|---|---|---|---|
| 1 | `RI-BSL` | BASELINE | Baseline CH4 (and N2O) per field and season | VM0051 v1.1 Eqs. 6-8; IPCC 2019 Eqs. 5.1-5.3 |
| 2 | `RI-PRJ` | PROJECT | Project CH4 (and N2O) per field and season | VM0051 v1.1 Eqs. 6-8 |
| 3 | `RI-PE` | EMISSIONS | Other emission sources and the N2O of drying periods | VM0051 v1.1 Eqs. 1-2, 17, 23-25 |
| 4 | `RI-REM` | REMOVALS | Removals (none: SOC is not credited) | VM0051 v1.1 Eqs. 6-8 |
| 5 | `RI-LK` | LEAKAGE | Leakage | VM0051 v1.1 §8.4 |
| 6 | `RI-UNC` | UNCERTAINTY | Uncertainty deduction (15 % for IPCC default values) | VM0051 v1.1 §8.5, §8.6 |
| 7 | `RI-ADJ` | ADJUSTMENT | Uncertainty applied | VM0051 v1.1 Eq. 29 |
| 8 | `RI-NET` | NET | Net emission reductions; credits (whole tonnes, rounded down) | VM0051 v1.1 Eqs. 29-34 |

### 14.4 Calculation inputs (17)
| Input | Comes from | Rule / parameter | Unit | Level | Round | Required |
|---|---|---|---|---|---|---|
| `AREA` | Monitoring data | RI_AREA | ha | Farm | period calculated | **Yes** |
| `DAYS` | Monitoring data | RI_DAYS | days | Farm | period calculated | **Yes** |
| `WATER` | Monitoring data | RI_WATER | — | Farm | period calculated | **Yes** |
| `PRESEASON` | Monitoring data | RI_PRESEASON | — | Farm | period calculated | No (0 if missing) |
| `STRAW` | Monitoring data | RI_STRAW | t/ha | Farm | period calculated | No (0 if missing) |
| `STRAW_TIMING` | Monitoring data | RI_STRAW_TIMING | — | Farm | period calculated | No (0 if missing) |
| `COMPOST` | Monitoring data | RI_COMPOST | t/ha | Farm | period calculated | No (0 if missing) |
| `FYM` | Monitoring data | RI_FYM | t/ha | Farm | period calculated | No (0 if missing) |
| `GREEN` | Monitoring data | RI_GREEN | t/ha | Farm | period calculated | No (0 if missing) |
| `N` | Monitoring data | RI_N | kg N/ha | Farm | period calculated | No (0 if missing) |
| `REGION` | Monitoring data | RI_REGION | — | Project | period calculated | No (0 if missing) |
| `EFC` | Monitoring data | RI_EFC | kg CH4/ha/day | Project | period calculated | No (0 if missing) |
| `UNC` | Monitoring data | RI_UNC | % | Project | period calculated | No (0 if missing) |
| `DIESEL` | Monitoring data | RI_DIESEL | L | Farm | period calculated | No (0 if missing) |
| `BURN` | Monitoring data | RI_BURN | kg d.m. | Farm | period calculated | No (0 if missing) |
| `PE_AB` | Monitoring data | RI_PE_AB | t CO2e | Project | period calculated | No (0 if missing) |
| `LE` | Monitoring data | RI_LE | t CO2e | Project | period calculated | No (0 if missing) |

### 14.5 Constants built into the module (32)
| Constant | Value | Unit | Source |
|---|---|---|---|
| `EFC_WORLD` | 1.19 | kg CH4/ha/day | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.11 (world) |
| `EFC_AFRICA` | 1.19 | kg CH4/ha/day | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.11 (africa) |
| `EFC_EAST_ASIA` | 1.32 | kg CH4/ha/day | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.11 (east asia) |
| `EFC_SOUTHEAST_ASIA` | 1.22 | kg CH4/ha/day | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.11 (southeast asia) |
| `EFC_SOUTH_ASIA` | 0.85 | kg CH4/ha/day | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.11 (south asia) |
| `EFC_EUROPE` | 1.56 | kg CH4/ha/day | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.11 (europe) |
| `EFC_NORTH_AMERICA` | 0.65 | kg CH4/ha/day | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.11 (north america) |
| `EFC_SOUTH_AMERICA` | 1.27 | kg CH4/ha/day | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.11 (south america) |
| `SFW_CONTINUOUS` | 1 | factor | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.12 (continuously flooded) |
| `SFW_SINGLE` | 0.71 | factor | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.12 (single drainage period) |
| `SFW_MULTIPLE` | 0.55 | factor | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.12 (multiple drainage periods incl. AWD) |
| `SFP_SHORT` | 1.00 | factor | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.13 (non-flooded pre-season < 180 days) |
| `SFP_LONG` | 0.89 | factor | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.13 (non-flooded pre-season > 180 days) |
| `SFP_FLOODED` | 2.41 | factor | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.13 (flooded pre-season > 30 days) |
| `SFP_VERY_LONG` | 0.59 | factor | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.13 (non-flooded pre-season > 365 days) |
| `CFOA_STRAW_SHORT` | 1.00 | factor | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.14 (straw incorporated < 30 days before cultivation) |
| `CFOA_STRAW_LONG` | 0.19 | factor | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.14 (straw incorporated > 30 days before cultivation) |
| `CFOA_COMPOST` | 0.17 | factor | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.14 (compost) |
| `CFOA_FYM` | 0.21 | factor | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.14 (farmyard manure) |
| `CFOA_GREEN` | 0.45 | factor | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.14 (green manure) |
| `STRAW_BASELINE` | 5 | t/ha | VM0051 v1.1 fn 16 / AG04.002: 5 t/ha straw assumed in the baseline |
| `EF_N_FLOODED` | 0.003 | t N2O-N/t N | IPCC 2019 Table 11.1 EF1FR (continuous flooding) |
| `EF_N_DRAINED` | 0.005 | t N2O-N/t N | IPCC 2019 Table 11.1 EF1FR (single and multiple drainage) |
| `N2ON_TO_N2O` | 1.57143 | t N2O/t N2O-N | 44/28 |
| `UNC_TIER1` | 0.15 | fraction | VM0051 v1.1 §8.5 / AG04.002: 15 % uncertainty deduction for IPCC default values |
| `GWP_CH4` | 28 | t CO2e/t CH4 | VM0051 v1.1 §9.1 -> VCS Standard v5.0 Table 9 (IPCC AR5) |
| `GWP_N2O` | 265 | t CO2e/t N2O | VM0051 v1.1 §9.1 -> VCS Standard v5.0 Table 9 (IPCC AR5) |
| `EF_DIESEL` | 0.002886 | t CO2e/L | VM0051 v1.1 parameter EF_CO2 (diesel) |
| `EF_BB_CH4` | 2.7 | g CH4/kg d.m. | IPCC 2019 Vol. 4 Ch. 2 Table 2.5 |
| `EF_BB_N2O` | 0.07 | g N2O/kg d.m. | IPCC 2019 Vol. 4 Ch. 2 Table 2.5 |
| `CF_RICE` | 0.80 | fraction | IPCC 2019 Vol. 4 Ch. 2 Table 2.6 |
| `TIER1_CAP` | 60000 | t CO2e | VM0051 v1.1 §8.2: Tier 1 factors only up to 60 000 t CO2e per year |

### 14.6 Outputs
Outputs written by this module's code (some appear only for the approach or activity module in use; `<stratum>` = one output per stratum).

| Output | Step |
|---|---|
| `EFC` | BASELINE |
| `CH4_BSL` | BASELINE |
| `CH4_WP` | PROJECT |
| `D_CH4_SOIL` | EMISSIONS |
| `D_N2O_SOIL` | EMISSIONS |
| `PE_DRYING` | EMISSIONS |
| `D_FUEL` | EMISSIONS |
| `D_BURN` | EMISSIONS |
| `PE_AB` | EMISSIONS |
| `PE_FUEL` | EMISSIONS |
| `REMOVALS` | REMOVALS |
| `LE` | LEAKAGE |
| `UNC` | UNCERTAINTY |
| `D_CH4_SOIL_ADJ` | ADJUSTMENT |
| `D_N2O_SOIL_ADJ` | ADJUSTMENT |
| `ER_NET` | NET |
| `CREDITS` | NET |

### 14.7 Interpretations made by the code (for the expert review)
- QA3 only (IPCC 2019 Tables 5.11-5.14 or a country-specific EF); QA2 is mandatory for methanotrophs, biochar, low-emission cultivars and AWD shallower than 10 cm and is not included.
- Eq. 5 / Eq. 8: GWP is applied once (BE_CH4 from Eq. 8 is used as the areal mean); Eq. 8 is summed over the seasons of the period.
- Season = the farm's records with the same observed-on date in the reporting period; baseline = the farm's BASELINE look-back records. A project record that matches no season (no RI_AREA on its date, dated outside the period, or undated) blocks the run (UNMATCHED_SEASON_RECORD / MISSING_OBSERVED_ON); it is never dropped.
- Baseline water regime: the lowest-emission regime recorded in the look-back (single drainage in any year -> single drainage, p. 14); baseline straw 5 t/ha with the look-back incorporation timing (LONG = 0.19 when not recorded); baseline cultivation period = the look-back mean, at most the project season's length.
- Pre-season factors from IPCC Table 5.13 including FLOODED 2.41 and VERY_LONG 0.59 (Eq. 6 refers to the full table).
- N2O: change in N rate at EF1FR continuous flooding 0.003 (Eq. 19) plus, on fields that start draining, Eq. 25 with CF_N2O = (0.005 - 0.003) x 44/28 = 0.00314 kg N2O/kg N (the drying increment is deducted after the uncertainty, Eq. 29).
- Uncertainty 15 % on dCH4 and dN2O for IPCC default factors (<= 60 000 t CO2e/yr, otherwise blocked); a country-specific EF uses its recorded uncertainty (RI_UNC).
- dCO2_lime and LE_yield are not calculated (no defining equation); liming and yield-related leakage must be shown de minimis.
- GWPs IPCC AR5 (CH4 28, N2O 265); VCUs are whole tonnes rounded down.

### 14.8 Reasons the calculation can be blocked
`DUPLICATE_INPUT`, `INVALID_INPUT`, `MISSING_REQUIRED_INPUT`. Added 29/10: `UNMATCHED_SEASON_RECORD` (a project record dated on no season's RI_AREA date or outside the period), `MISSING_OBSERVED_ON`.

---

## 15. BM-AG04.002 1.0 — CCTS-AG04.002

| | |
|---|---|
| Standard | India CCTS |
| Methodology | BM AG04.002 — Improved rice management, IPCC default-value approach |
| Methodology code / version label to create | `BM-AG04.002` / `1.0` (or `1.0-<suffix>`) |
| Calculation module | `CCTS-AG04.002` · module version 1.1.0 |
| Option text on the Calculation tab | CCTS BM AG04.002 v1.0 - improved rice management, IPCC default-value approach |
| Suitable for | Paddy rice methane reduction under India's Carbon Credit Trading Scheme. |
| Field / laboratory work | No — seasonal field records per farm |
| Readiness | Not Production Ready |

### 15.1 Sampling rule (`MODULE-SAMPLING`)
None — this module needs no sampling design rule (no soil sampling).

### 15.2 Monitoring rules — the data the project collects (14)
| Code | What to record | Unit | Level | Source | Frequency | Methodology reference |
|---|---|---|---|---|---|---|
| `RI_AREA` | Rice area of the field in the season | ha | Farm | Field activity | Each season (record all values of a season with the same observed-on date) | VM0051 A_i / AG04.002 A_g,s |
| `RI_DAYS` | Cultivation period (land preparation to the later of harvest or post-season drainage) | days | Farm | Field activity | Each season (record all values of a season with the same observed-on date) | VM0051 Eq. 8 L_t; IPCC 2019 Eq. 5.1 |
| `RI_WATER` | On-season water regime: CONTINUOUS, SINGLE or MULTIPLE (drainage periods; AWD = MULTIPLE) | — | Farm | Field activity | Each season (record all values of a season with the same observed-on date) | IPCC 2019 Table 5.12 SFw |
| `RI_PRESEASON` | Pre-season water status: SHORT (< 180 days dry), LONG (> 180), VERY_LONG (> 365) or FLOODED (> 30 days) | — | Farm | Field activity | Each season (record all values of a season with the same observed-on date) | IPCC 2019 Table 5.13 SFp |
| `RI_STRAW` | Rice straw incorporated (dry matter) | t/ha | Farm | Field activity | Each season (record all values of a season with the same observed-on date) | IPCC 2019 Eq. 5.3 ROA (straw) |
| `RI_STRAW_TIMING` | Straw incorporated SHORT (< 30 days) or LONG (> 30 days) before cultivation | — | Farm | Field activity | Each season (record all values of a season with the same observed-on date) | IPCC 2019 Table 5.14 CFOA |
| `RI_COMPOST` | Compost applied (fresh weight) | t/ha | Farm | Field activity | Each season (record all values of a season with the same observed-on date) | IPCC 2019 Eq. 5.3 ROA |
| `RI_FYM` | Farmyard manure applied (fresh weight) | t/ha | Farm | Field activity | Each season (record all values of a season with the same observed-on date) | IPCC 2019 Eq. 5.3 ROA |
| `RI_GREEN` | Green manure applied (fresh weight) | t/ha | Farm | Field activity | Each season (record all values of a season with the same observed-on date) | IPCC 2019 Eq. 5.3 ROA |
| `RI_N` | Nitrogen applied (synthetic + organic + residue) | kg N/ha | Farm | Field activity | Each season (record all values of a season with the same observed-on date) | VM0051 Eqs. 19, 25 Q_N |
| `RI_REGION` | IPCC region of the baseline emission factor (WORLD, SOUTH_ASIA, SOUTHEAST_ASIA, EAST_ASIA, EUROPE, ...) | — | Project | Field activity | Validation | IPCC 2019 Table 5.11 |
| `RI_EFC` | Country-specific / measured baseline emission factor (continuously flooded, no amendments; replaces the region value) | kg CH4/ha/day | Project | Field activity | Validation | VM0051 §8.2.3 EF_bsl,c hierarchy; AG04.002 paras 27-28 (reference fields) |
| `RI_UNC` | Uncertainty deduction of a country-specific emission factor (%) | % | Project | Field activity | Validation | VM0051 §8.6 |
| `RI_PE_FUEL` | Land preparation fuel emissions (BM-T-002; year 1, when above 5 % of reductions) | t CO2e | Project | Field activity | Year 1 | AG04.002 PE_l |

### 15.3 Calculation rules — the steps (8)
| # | Code | Step | What it calculates | Equation reference |
|---|---|---|---|---|
| 1 | `RI-BSL` | BASELINE | Baseline CH4 (and N2O) per field and season | AG04.002 v1.0 paras 26-35; IPCC 2019 Eqs. 5.1-5.3 |
| 2 | `RI-PRJ` | PROJECT | Project CH4 (and N2O) per field and season | AG04.002 v1.0 paras 26-35 |
| 3 | `RI-PE` | EMISSIONS | Other emission sources and the N2O of drying periods | AG04.002 PE_n, PE_l |
| 4 | `RI-REM` | REMOVALS | Removals (none: SOC is not credited) | AG04.002 v1.0 paras 26-35 |
| 5 | `RI-LK` | LEAKAGE | Leakage | AG04.002 (none) |
| 6 | `RI-UNC` | UNCERTAINTY | Uncertainty deduction (15 % for IPCC default values) | AG04.002 Table 6 |
| 7 | `RI-ADJ` | ADJUSTMENT | Uncertainty applied | AG04.002 |
| 8 | `RI-NET` | NET | Net emission reductions; credits (whole tonnes, rounded down) | AG04.002 ER_y |

### 15.4 Calculation inputs (14)
| Input | Comes from | Rule / parameter | Unit | Level | Round | Required |
|---|---|---|---|---|---|---|
| `AREA` | Monitoring data | RI_AREA | ha | Farm | period calculated | **Yes** |
| `DAYS` | Monitoring data | RI_DAYS | days | Farm | period calculated | **Yes** |
| `WATER` | Monitoring data | RI_WATER | — | Farm | period calculated | **Yes** |
| `PRESEASON` | Monitoring data | RI_PRESEASON | — | Farm | period calculated | No (0 if missing) |
| `STRAW` | Monitoring data | RI_STRAW | t/ha | Farm | period calculated | No (0 if missing) |
| `STRAW_TIMING` | Monitoring data | RI_STRAW_TIMING | — | Farm | period calculated | No (0 if missing) |
| `COMPOST` | Monitoring data | RI_COMPOST | t/ha | Farm | period calculated | No (0 if missing) |
| `FYM` | Monitoring data | RI_FYM | t/ha | Farm | period calculated | No (0 if missing) |
| `GREEN` | Monitoring data | RI_GREEN | t/ha | Farm | period calculated | No (0 if missing) |
| `N` | Monitoring data | RI_N | kg N/ha | Farm | period calculated | No (0 if missing) |
| `REGION` | Monitoring data | RI_REGION | — | Project | period calculated | No (0 if missing) |
| `EFC` | Monitoring data | RI_EFC | kg CH4/ha/day | Project | period calculated | No (0 if missing) |
| `UNC` | Monitoring data | RI_UNC | % | Project | period calculated | No (0 if missing) |
| `PE_FUEL` | Monitoring data | RI_PE_FUEL | t CO2e | Project | period calculated | No (0 if missing) |

### 15.5 Constants built into the module (27)
| Constant | Value | Unit | Source |
|---|---|---|---|
| `EFC_WORLD` | 1.19 | kg CH4/ha/day | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.11 (world) |
| `EFC_AFRICA` | 1.19 | kg CH4/ha/day | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.11 (africa) |
| `EFC_EAST_ASIA` | 1.32 | kg CH4/ha/day | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.11 (east asia) |
| `EFC_SOUTHEAST_ASIA` | 1.22 | kg CH4/ha/day | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.11 (southeast asia) |
| `EFC_SOUTH_ASIA` | 0.85 | kg CH4/ha/day | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.11 (south asia) |
| `EFC_EUROPE` | 1.56 | kg CH4/ha/day | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.11 (europe) |
| `EFC_NORTH_AMERICA` | 0.65 | kg CH4/ha/day | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.11 (north america) |
| `EFC_SOUTH_AMERICA` | 1.27 | kg CH4/ha/day | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.11 (south america) |
| `SFW_CONTINUOUS` | 1 | factor | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.12 (continuously flooded) |
| `SFW_SINGLE` | 0.71 | factor | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.12 (single drainage period) |
| `SFW_MULTIPLE` | 0.55 | factor | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.12 (multiple drainage periods incl. AWD) |
| `SFP_SHORT` | 1.00 | factor | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.13 (non-flooded pre-season < 180 days) |
| `SFP_LONG` | 0.89 | factor | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.13 (non-flooded pre-season > 180 days) |
| `SFP_FLOODED` | 2.41 | factor | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.13 (flooded pre-season > 30 days) |
| `SFP_VERY_LONG` | 0.59 | factor | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.13 (non-flooded pre-season > 365 days) |
| `CFOA_STRAW_SHORT` | 1.00 | factor | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.14 (straw incorporated < 30 days before cultivation) |
| `CFOA_STRAW_LONG` | 0.19 | factor | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.14 (straw incorporated > 30 days before cultivation) |
| `CFOA_COMPOST` | 0.17 | factor | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.14 (compost) |
| `CFOA_FYM` | 0.21 | factor | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.14 (farmyard manure) |
| `CFOA_GREEN` | 0.45 | factor | IPCC 2019 Refinement Vol. 4 Ch. 5 Table 5.14 (green manure) |
| `STRAW_BASELINE` | 5 | t/ha | VM0051 v1.1 fn 16 / AG04.002: 5 t/ha straw assumed in the baseline |
| `EF_N_FLOODED` | 0.003 | t N2O-N/t N | IPCC 2019 Table 11.1 EF1FR (continuous flooding) |
| `EF_N_DRAINED` | 0.005 | t N2O-N/t N | IPCC 2019 Table 11.1 EF1FR (single and multiple drainage) |
| `N2ON_TO_N2O` | 1.57143 | t N2O/t N2O-N | 44/28 |
| `UNC_TIER1` | 0.15 | fraction | VM0051 v1.1 §8.5 / AG04.002: 15 % uncertainty deduction for IPCC default values |
| `GWP_CH4` | 29.8 | t CO2e/t CH4 | AG04.002 v1.0 (IPCC AR6) |
| `GWP_N2O` | 273 | t CO2e/t N2O | AG04.002 v1.0 (IPCC AR6) |

### 15.6 Outputs
Outputs written by this module's code (some appear only for the approach or activity module in use; `<stratum>` = one output per stratum).

| Output | Step |
|---|---|
| `EFC` | BASELINE |
| `CH4_BSL` | BASELINE |
| `CH4_WP` | PROJECT |
| `D_CH4_SOIL` | EMISSIONS |
| `D_N2O_SOIL` | EMISSIONS |
| `PE_DRYING` | EMISSIONS |
| `D_FUEL` | EMISSIONS |
| `D_BURN` | EMISSIONS |
| `PE_AB` | EMISSIONS |
| `PE_FUEL` | EMISSIONS |
| `REMOVALS` | REMOVALS |
| `LE` | LEAKAGE |
| `UNC` | UNCERTAINTY |
| `D_CH4_SOIL_ADJ` | ADJUSTMENT |
| `D_N2O_SOIL_ADJ` | ADJUSTMENT |
| `ER_NET` | NET |
| `CREDITS` | NET |

### 15.7 Interpretations made by the code (for the expert review)
- IPCC default-value approach (paras 26-35); EFc measured on reference fields (RI_EFC) or the IPCC Table 5.11 region value.
- Season = the farm's records with the same observed-on date; baseline = continuation of current practice from the farm's BASELINE records (same conservative rules as VM0051 where AG04.002 is silent). A project record that matches no season blocks the run (UNMATCHED_SEASON_RECORD / MISSING_OBSERVED_ON); it is never dropped.
- Pre-season factor and straw CFOA from the recorded pre-season status and incorporation timing (equivalent to the regional double / single cropping defaults 1.0 / 0.89 and 1.0 / 0.19).
- PE_n corrected: N x (0.005 - 0.003) x 44/28 x GWP, positive (the printed sign and the missing 44/28 are errors).
- Decreases in N2O are not credited; land-preparation fuel (BM-T-002) is recorded in t CO2e.
- The 15 % deduction is applied once to the whole reduction (Eq. 7 applies it twice; Table 6 does not).
- GWPs IPCC AR6 (CH4 29.8, N2O 273); credits are whole tonnes rounded down.

### 15.8 Reasons the calculation can be blocked
`DUPLICATE_INPUT`, `INVALID_INPUT`, `MISSING_REQUIRED_INPUT`. Added 29/10: `UNMATCHED_SEASON_RECORD` (a project record dated on no season's RI_AREA date or outside the period), `MISSING_OBSERVED_ON`.

---

## 16. GS403 2.1 — GS403-V2.1

| | |
|---|---|
| Standard | Gold Standard |
| Methodology | GS 403 Afforestation / Reforestation v2.1 |
| Methodology code / version label to create | `GS403` / `2.1` (or `2.1-<suffix>`) |
| Calculation module | `GS403-V2.1` · module version 1.1.0 |
| Option text on the Calculation tab | GS 403 v2.1 - afforestation / reforestation (inventory stem volume, GS conversion factors) |
| Suitable for | Tree plantations and forests — stem-volume inventory plots converted with Gold Standard factors. |
| Field / laboratory work | No soil sampling — forest inventory plots |
| Readiness | Not Production Ready |

### 16.1 Sampling rule (`MODULE-SAMPLING`)
| Parameter | Value | Effect in the platform |
|---|---|---|
| `quantification_approach` | `OTHER` | The MRV plan's approach is set to this value; any other choice is refused |
| `sampling_method` | `FOREST_INVENTORY` | Recorded on the sampling design |
| `min_samples_per_stratum` | `2` | Every stratum in a sampling design needs at least this many points |
| `target_precision_pct` | `20` | Design precision must be at or below this |
| `confidence_level_pct` | `90` | Design confidence must be at or above this |

### 16.2 Monitoring rules — the data the project collects (15)
| Code | What to record | Unit | Level | Source | Frequency | Methodology reference |
|---|---|---|---|---|---|---|
| `GA_PLOT_VOL` | Stem volume in the inventory plot (sum of the trees' over-bark stem volume) | m3 | Sampling point | Field | Each forest inventory (before every Performance Certification) | GS 403 §3.11; BioCarbon Fund Sourcebook |
| `GA_PLOT_AREA` | Inventory plot size (slope-corrected) | ha | Project | Field | Each forest inventory (before every Performance Certification) | GS 403 §3.11; Sourcebook |
| `GA_WD` | Wood density of the MU | t d.m./m3 | Stratum | Field activity | Design certification | GS 403 §3.10.2 (default 0.3) |
| `GA_BEF` | Biomass expansion factor of the MU | factor | Stratum | Field activity | Design certification | GS 403 §3.10.2 (default 1.1) |
| `GA_RS` | Root-to-shoot ratio of the MU (relative, e.g. 0.2) | ratio | Stratum | Field activity | Design certification | GS 403 §3.10.2 (default 0.2) |
| `GA_CR_LT` | Long-term CO2 removal of the MU (growth model: equilibrium, Option 1, or Eq. 4 average, Option 2) | t CO2/ha | Stratum | Field activity | Design certification | GS 403 §3.6.6-3.6.12, Eq. 4 |
| `GA_CR_MODEL` | Growth-model CO2 stock of the MU at this inventory date | t CO2/ha | Stratum | Field activity | Each forest inventory (before every Performance Certification) | GS 403 §3.6.1-3.6.5, §3.11.1 |
| `GA_MANGROVE_PLANTED` | Mangrove MU: year planting started (adds 1.8 t CO2/ha/yr for 20 years) | year | Stratum | Field activity | Design certification | GS 403 §2.1 (AR-AM0014 default) |
| `GA_BSL` | Baseline stock of the eligible planting area (tree and non-tree, conservative factors) | t CO2e | Project | Field activity | Design certification | GS 403 Eq. 3; §3.4-3.5; §3.10.2 (WD 0.7, BEF 3.5, R:S 0.8 / 4.0) |
| `GA_BURNING` | Baseline biomass burned for site preparation: YES or NO | — | Project | Field activity | Design certification | GS 403 §3.8 |
| `GA_LK` | Leakage of the project area for the whole crediting period | t CO2e | Project | Field activity | Design certification | GS 403 Eqs. 6-7 |
| `GA_FERT_N` | Fertiliser N applied (synthetic and organic) | kg N | Farm | Field activity | Year of use | GS 403 §3.8 (0.005 t CO2/kg N) |
| `GA_FERT_N_PRIOR` | Fertiliser N applied in earlier monitoring periods (cumulative) | kg N | Project | Field activity | Each verification | GS 403 §3.8 |
| `GA_ISSUED_PRIOR` | Units already issued for the project (GSVERs and converted PERs, before buffer) | t CO2e | Project | Field activity | Each verification | GS 403 §3.3.3; PR §11.2 |
| `GA_PAA` | Paris Agreement alignment status for 2026+ vintages: YES when approved by Gold Standard | — | Project | Field activity | When approved | GS 119 PAA P&R v1.2 |

### 16.3 Calculation rules — the steps (8)
| # | Code | Step | What it calculates | Equation reference |
|---|---|---|---|---|
| 1 | `GA-BSL` | BASELINE | Baseline stock at planting start (deducted once) | GS 403 v2.1 Eq. 3 |
| 2 | `GA-PRJ` | PROJECT | Tree CO2 stock per MU from the inventory (precision deduction, long-term cap) | GS 403 v2.1 §3.9-3.11, Eq. 4 |
| 3 | `GA-PE` | EMISSIONS | Other emissions: burning for site preparation (10 % of baseline), fertiliser N | GS 403 v2.1 §3.8 |
| 4 | `GA-REM` | REMOVALS | Cumulative CO2 removal of the project area | GS 403 v2.1 Eqs. 1, 2 |
| 5 | `GA-LK` | LEAKAGE | Leakage (deducted once) | GS 403 v2.1 Eqs. 5-7 |
| 6 | `GA-UNC` | UNCERTAINTY | Inventory precision (90 % confidence; error above 20 % deducted) | GS 403 v2.1 §3.11.5 |
| 7 | `GA-ADJ` | ADJUSTMENT | Issuable units, Paris alignment of vintages, GS Compliance Buffer (20 %) | GS 403 v2.1 §3.3.3; GHG ER&S PR v3.2 §11.1; GS 119 v1.2 |
| 8 | `GA-NET` | NET | GSVERs to the project account (whole units, rounded down) | GS 403 v2.1 Eq. 1 |

### 16.4 Calculation inputs (16)
| Input | Comes from | Rule / parameter | Unit | Level | Round | Required |
|---|---|---|---|---|---|---|
| `PLOT_VOL` | Monitoring data | GA_PLOT_VOL | m3 | Sampling point | period calculated | **Yes** |
| `PLOT_AREA` | Monitoring data | GA_PLOT_AREA | ha | Project | period calculated | **Yes** |
| `AREA` | Stratum area (SQL Server) | — | ha | Stratum | period calculated | **Yes** |
| `WD` | Monitoring data | GA_WD | t d.m./m3 | Stratum | period calculated | No (0 if missing) |
| `BEF` | Monitoring data | GA_BEF | factor | Stratum | period calculated | No (0 if missing) |
| `RS` | Monitoring data | GA_RS | ratio | Stratum | period calculated | No (0 if missing) |
| `CR_LT` | Monitoring data | GA_CR_LT | t CO2/ha | Stratum | period calculated | No (0 if missing) |
| `CR_MODEL` | Monitoring data | GA_CR_MODEL | t CO2/ha | Stratum | period calculated | No (0 if missing) |
| `MANGROVE_PLANTED` | Monitoring data | GA_MANGROVE_PLANTED | year | Stratum | period calculated | No (0 if missing) |
| `BSL` | Monitoring data | GA_BSL | t CO2e | Project | period calculated | No (0 if missing) |
| `BURNING` | Monitoring data | GA_BURNING | — | Project | period calculated | No (0 if missing) |
| `LK` | Monitoring data | GA_LK | t CO2e | Project | period calculated | No (0 if missing) |
| `FERT_N` | Monitoring data | GA_FERT_N | kg N | Farm | period calculated | No (0 if missing) |
| `FERT_N_PRIOR` | Monitoring data | GA_FERT_N_PRIOR | kg N | Project | period calculated | No (0 if missing) |
| `ISSUED_PRIOR` | Monitoring data | GA_ISSUED_PRIOR | t CO2e | Project | period calculated | No (0 if missing) |
| `PAA` | Monitoring data | GA_PAA | — | Project | period calculated | No (0 if missing) |

### 16.5 Constants built into the module (10)
| Constant | Value | Unit | Source |
|---|---|---|---|
| `C_TO_CO2` | 3.66667 | t CO2/t C | 44/12 (GS 403 v2.1 §3.10.1) |
| `CF_TREE` | 0.47 | t C/t d.m. | GS 403 v2.1 §3.10.1a (printed 0.47 with the 5 struck through) |
| `WD_DEFAULT` | 0.3 | t d.m./m3 | GS 403 v2.1 §3.10.2 (CO2 removal) |
| `BEF_DEFAULT` | 1.1 | factor | GS 403 v2.1 §3.10.2 (CO2 removal) |
| `RS_DEFAULT` | 0.2 | ratio | GS 403 v2.1 §3.10.2 (CO2 removal) |
| `PRECISION` | 0.20 | fraction | GS 403 v2.1 §3.11.5 (±20 % at 90 % confidence) |
| `BURN_FRACTION` | 0.10 | fraction | GS 403 v2.1 §3.8 (10 % of the baseline) |
| `FERT_EF` | 0.005 | t CO2/kg N | GS 403 v2.1 §3.8 |
| `MANGROVE_SOC` | 1.8 | t CO2/ha/yr | GS 403 v2.1 §2.1 (20 years) |
| `BUFFER` | 0.20 | fraction | GS GHG ER&S Product Requirements v3.2 §11.1.1 |

### 16.6 Outputs
Outputs written by this module's code (some appear only for the approach or activity module in use; `<stratum>` = one output per stratum).

| Output | Step |
|---|---|
| `BASELINE` | BASELINE |
| `V_MEAN_<stratum>` | PROJECT |
| `STOCK_<stratum>` | PROJECT |
| `CREDITABLE_<stratum>` | PROJECT |
| `OE_BURN` | EMISSIONS |
| `OE_FERT` | EMISSIONS |
| `CR_STOCK` | REMOVALS |
| `CR_MANGROVE_SOC` | REMOVALS |
| `LEAKAGE` | LEAKAGE |
| `INVENTORY_ERROR_MAX` | UNCERTAINTY |
| `NET_CUMULATIVE` | ADJUSTMENT |
| `ISSUABLE` | ADJUSTMENT |
| `PAA_BLOCKED_SHARE` | ADJUSTMENT |
| `BUFFER` | ADJUSTMENT |
| `GSVER_ELIGIBLE` | NET |
| `GSVER_PROJECT` | NET |

### 16.7 Interpretations made by the code (for the expert review)
- MU = project stratum (its area = eligible planting area); inventory plots are the sampling points and record stem volume (m3).
- Precision per MU: E = t(two-sided 90 %, n - 1) x SE / mean (the AR-TOOL14 definition; GS 403 does not define it); the accountable mean volume = mean x (1 - max(0, E - 0.20)) (§3.11.5 example).
- Creditable stock per MU = min(inventory stock, growth-model stock at the date, long-term value) when those are recorded (§3.6, §3.11.1).
- CF 0.47 (the printed '0.475' has the 5 struck through); GS default factors WD 0.3, BEF 1.1, R:S 0.2 unless MU factors are recorded.
- Baseline and leakage are recorded as project-area totals from the GS template (conservative factors WD 0.7, BEF 3.5, R:S 0.8 / 4.0) and deducted once; burning = 10 % of the baseline.
- Issuable = max(0, cumulative net removal) - units already issued (§3.3.3); cumulative fertiliser N = prior + this period. The units already issued are a recorded value (GA_ISSUED_PRIOR, 0 when none): it is required for every reporting period after the project's first (period number above 1), so a missing entry is never read as nothing issued.
- GS 119 v1.2: the share of the issuable amount falling in vintages from 1 January 2026 (by days of the reporting period) is not credited unless GA_PAA = YES. The issuable amount is the increment since the units already issued, so the day share of this period is at least the day share of any longer accrual span (conservative under even accrual).
- Per-MU outputs are named by the stratum code, or by a collision-free prefix of the stratum record id when it is not available.
- 20 % of the issuable units go to the GS Compliance Buffer; GSVERs to the project account are whole units rounded down. PERs (forward issuance) are not calculated here.

### 16.8 Reasons the calculation can be blocked
`INSUFFICIENT_SAMPLES`, `MISSING_REQUIRED_INPUT`. Added 29/10: `ISSUED_PRIOR_REQUIRED` (GA_ISSUED_PRIOR missing in a reporting period after the first).

---

## Applicability rules to write for a real project
No applicability rules ship with the modules — they must come from the official methodology text. Every version needs at least the two identity rules below; add the methodology's eligibility conditions (land use, practices, location, dates) as further rules.

| Code | Fact key | Operator | Expected value (JSON) | Purpose |
|---|---|---|---|---|
| A1 | `standard_code` | EQUALS | `"VCS"` / `"GS"` / your CCTS code | The project is under this standard |
| A2 | `activity_code` | EQUALS | your activity code (e.g. `"IALM"`) | The project's activity is covered |
| A3 (example) | `proposed_practice_categories` | ANY_IN | e.g. `["TILLAGE","RESIDUE","COVER_CROP"]` | The new practice is one the methodology covers |
| A4 (example) | `land_use_current` | EQUALS | e.g. `"CROPLAND"` | Land-use condition |
| A5 (example) | `project_start_date` | DATE_ON_OR_AFTER | e.g. `"2025-10-21"` | Start-date condition |

A3–A5 are **examples of the format only**; the expected values must be taken from the methodology's applicability conditions by the methodology expert.