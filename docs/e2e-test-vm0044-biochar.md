# End-to-end test — VM0044 biochar (dmrv_db1 · Verra VCS · VM0044 v1.2 · facility to owner payout)

This is the complete test of the platform for **Verra VM0044 v1.2 — Biochar Utilization in Soil and Non-Soil Applications**: a plant
turns biomass (e.g. coffee and silver-oak prunings) into biochar; the biochar applied to soil or used in other products locks carbon away.

The flow and every value below were **run once end to end on the test database** before this document was written (stages 1–10); the
expected result is the one the platform produced.

| | |
|---|---|
| Database | `dmrv_db1` (VCS, users and organizations already exist) |
| Code | branch `fixes_14/10` |
| Password for every user | **`Test@12345678`** |
| Scenario | 🧪 a **high-technology** pyrolysis plant near Hunsur, **620 °C**, 150 t biochar produced Jan–Sep 2026: 120 t applied to soil, 10 t used in concrete |
| Expected credits | **297 VCUs** |
| Owner payout | **₹6,000.00** (60 % of ₹10,000 sales) |

**Markers:** 🔎 negative check · ⚠ known trap · 🧪 test value · ✍ your own real value.

---

## Part A — How VM0044 differs from the VM0042 test
| | VM0042 (soil) | **VM0044 (biochar)** |
|---|---|---|
| Unit of the project | farms | **one production facility** |
| Sampling / strata / control farms | yes | **none** |
| Laboratory workflow | yes | **no** — the biochar lab values (carbon content, H:C ratio) are entered as monitoring records |
| Periods | baseline + monitoring | **one monitoring period** is enough |
| Data entry | lab results + farm records | **15 project-level records** on the Monitoring data tab |
| Uncertainty / buffer | yes | **none** (VM0044 has neither; permanence is the 100-year factor) |
| Key rules | — | soil biochar must have **H:C ≤ 0.7** (`INELIGIBLE_BIOCHAR`); high technology needs the **lab carbon content** and a **measured temperature** |

## Part B — The flow at a glance
| Stage | Logins | Result |
|---|---|---|
| 1 Catalog | leelak | activity `BIOCHAR` under VCS |
| 2 Methodology | ms1 → ms2 | VM0044 1.2 with module `VM0044-V1.2`, approved |
| 3 Owner | pm → qatester1 → pm | facility owner active (as a "farmer") |
| 4 Site | pm → gis | plant site (≈ 2 ha) verified |
| 5 Project | pm → gis → qatester1 → pm | eligible |
| 6 Lock | ms1 → pm | VM0044 1.2 locked |
| 7 MRV setup | mrv → qatester1 → mrv | plan, one period |
| 8 Production data | mrv → qatester1 | 15 records, dataset approved |
| 9 Calculation | analyst → qatester1 | **297 VCUs** |
| 10–14 | same as the VM0042 test | verified → issued → ledger → sold → owner paid |

---

## Stage 1 — Catalog · LOGIN `leelak`
**Projects → Standards & activities** → **Activities**: Code `BIOCHAR` · Name `Biochar production and use` · Offered under **Verified
Carbon Standard** → **Add activity**.

## Stage 2 — Methodology VM0044 1.2
### 2.1 · LOGIN `ms1` · Methodologies
| Where | Field | Enter |
|---|---|---|
| Add a methodology | Code / Name | **`VM0044`** / `Biochar Utilization in Soil and Non-Soil Applications` |
| | Standard / Activities | Verified Carbon Standard / Biochar production and use |
| New version | label | **`1.2`** → **New draft version** → **Open** |
| Version details | Effective from / Source | `27-06-2025` (VM0044 v1.2 date) / `Verra VM0044 v1.2` → **Save details** |
| Tab **calculation** | module | **VM0044 v1.2 - biochar in soil and non-soil applications · v1.0.0** → **Use this module** |
| Tab **applicability** | A1 / A2 | `"VCS"` on `standard_code` · `"BIOCHAR"` on `activity_code` (EQUALS, Not applicable) |

**Submit for approval.** ✔ module `VM0044-V1.2`; 8 calculation rules `V44-BSL` … `V44-NET`; **14 monitoring rules** (all project level).
🔎 ms1 cannot approve. **2.2 · ms2 → Approve.**

## Stage 3 — Facility owner (entered as a farmer)
The platform pays project revenue to farmers, so the plant owner is registered as one.

| Step | LOGIN | Enter |
|---|---|---|
| 3.1 | pm | **Register farmer**: org `varsapradaya_developer` · Name ✍ (🧪 `Suresh Kumar`) · Phone ✍ · Village `Hunsur` · District `Mysuru` · State `Karnataka` · `IN` → **Create** → **Register** → KYC National ID 🧪 `1234 5678 9032` + PDF → **Submit** |
| 3.2 | qatester1 | **Verify KYC** (🔎 pm cannot) |
| 3.3 | pm | Consent → **Activate** → Agreement `PROGRAM_PARTICIPATION` · `v1` · from **`01-01-2026`** → signed PDF; note `AGR-2026-…` |

## Stage 4 — Plant site (one "farm")
**pm** → owner → **Farms → Add farm**: `Hunsur biochar plant` · Owned · `2` ha · corners 🧪 `12.3100, 76.3200` / `12.3100, 76.3213` /
`12.3113, 76.3213` / `12.3113, 76.3200` (≈ 2 ha; ✍ or the real site) · Land record PDF · ownership Farmer / Owner / 100 % /
`Sy No 90/2` → **Submit for review**. **gis** → verify ownership → **Start GIS review** → **Verify farm**.

## Stage 5 — Project · LOGIN `pm` (then gis, qatester1)
| Field | Enter |
|---|---|
| Name / Type | `Hunsur biochar facility` / **Other** |
| Planned start | **`01-01-2026`** (after 27-06-2025) |
| Farms | **Hunsur biochar plant** · from `01-01-2026` · Farmer · `Carbon rights clause of AGR-2026-…` · `100` |
| Standard / Activity | Verified Carbon Standard / Biochar production and use |
| Crediting period / Baseline | `01-01-2026` – `31-12-2035` / `01-01-2023` – `31-12-2025` · `Prunings burned or left to decompose` |

**Submit for eligibility review** → gis **Accept boundary** → qatester1 **Verify** carbon rights + **Approve eligibility** → pm **Confirm activity**.

## Stage 6 — Lock
**ms1** → **Evaluate candidates** → **VM0044 1.2 Applicable** → **Recommend** · **pm** → **Confirm & lock**.

## Stage 7 — MRV setup (MRV → Hunsur biochar facility)
| Step | LOGIN | Enter | ✔ |
|---|---|---|---|
| 7.1 | mrv | **Create MRV plan**: frequency `Per production period` · approach **empty** · `01-01-2026` – `31-12-2035` · evidence `Production log, lab certificates, delivery notes` → **Create** → **Submit** | 14 `V44_…` measurements |
| 7.2 | qatester1 | **Approve** — acknowledge the gaps in the dialog (approach, depth, design: not used by biochar) | Approved (status "Configuration required" is normal) |
| 7.3 | mrv | **Monitoring periods**: `Period 1` · Monitoring · `01-01-2026` – `30-09-2026` → **Mark planned → Start period → Open data collection** | Data collection |

No strata, sampling design, field visits or laboratory engagement are needed.

## Stage 8 — Production data (picker **Period 1**) · LOGIN `mrv` → tab **Monitoring data**
All records are **project level** (no farm box), Phase **Project**, Source **Document**.

| # | Measurement | Value | Observed on | What it is |
|---|---|---|---|---|
| 1 | V44_PRODUCED (t) | 🧪 `150` | `15-09-2026` | all biochar produced, dry mass |
| 2 | V44_USED_SOIL (t) | 🧪 `90` | `15-06-2026` | applied to soil, first batch |
| 3 | V44_USED_SOIL (t) | 🧪 `30` | `15-09-2026` | applied to soil, second batch (the two add up: 120 t) |
| 4 | V44_USED_NONSOIL (t) | 🧪 `10` | `15-09-2026` | used in concrete |
| 5 | V44_FCP (fraction) | 🧪 `0.72` | `15-09-2026` | lab organic carbon content 72 % — type **0.72** |
| 6 | V44_HC_RATIO (ratio) | 🧪 `0.35` | `15-06-2026` | lab H:C ratio, batch 1 (must be ≤ 0.7) |
| 7 | V44_HC_RATIO (ratio) | 🧪 `0.41` | `15-09-2026` | lab H:C ratio, batch 2 |
| 8 | V44_TEMP (degC) | 🧪 `620` | `15-09-2026` | average pyrolysis temperature |
| 9 | V44_TECH (text) | `HIGH` | `15-09-2026` | high-technology plant (exactly `HIGH` or `LOW`) |
| 10 | V44_FEEDSTOCK (text) | `WOOD` | `15-09-2026` | woody prunings |
| 11 | V44_PROCESS (text) | `PYROLYSIS` | `15-09-2026` | conversion process |
| 12 | V44_PE_PRETREAT (t CO2e) | 🧪 `4.5` | `15-09-2026` | chipping / drying energy |
| 13 | V44_PE_AUX (t CO2e) | 🧪 `1.5` | `15-09-2026` | reactor auxiliary energy |
| 14 | V44_PE_PROCESSING (t CO2e) | 🧪 `0.8` | `15-09-2026` | crushing / bagging before use |
| 15 | V44_LE_TRANSPORT (t CO2e) | 🧪 `2.2` | `15-09-2026` | transport legs over 200 km round trip |

V44_FE (kiln methane) is left empty — it is only for **LOW** technology.

**8.2** mrv → **Datasets & QA** → Period 1 → **Create dataset version** → **Submit for QA**.
**8.3** qatester1 → **Start QA review** (PASS; WARN for configuration is normal) → PASS → **Approve dataset**.

## Stage 9 — Calculation · LOGIN `analyst`
**Calculations** → project · Period 1 → **New calculation run** → **Check readiness & freeze inputs** → **Execute**.

| Output | Meaning | Expected |
|---|---|---|
| M_USED | biochar used: 120 soil + 10 non-soil | **130 t** |
| F_CP | carbon content (lab) | **0.72** |
| PR_DE | 100-year permanence factor (above 600 °C) | **0.89** |
| CC | persistent carbon: 130 × 0.72 × 0.89 | **83.30 t C** |
| CC_CO2 | × 44/12 | **305.45 t CO₂e** |
| P_EP | kiln methane (high technology = 0) | **0** |
| PE_PS | production emissions: (4.5 + 0 + 1.5) × 130 / 150 | **5.20** |
| PE_AS | processing before use | **0.80** |
| ER_PS | 305.45 − 5.20 | **300.25** |
| LE | transport leakage | **2.20** |
| UNC / BUFFER | none in VM0044 | **0 / 0** |
| ER_NET | 300.25 − 0.80 − 2.20 | **297.25** |
| **VCU_TOTAL** | whole tonnes, rounded down | **297** |

🔎 analyst cannot Approve. **qatester1**: **QA** → **Start calculation QA** → PASS → **Record QA** → **Approve**.

## Stages 10–14 — Verification, registry, ledger, marketplace, payout
As in the VM0042 test document (`docs/e2e-test-palthope-vm0042.md`, Stages 14–18), with these numbers:

| Stage | Change |
|---|---|
| 10 Verification | finding `Biochar lab certificates (carbon content, H:C)`; VVB quantity **`297`** · `tCO2e`; Verification tab picker **Period 1** |
| 11 Registry | issuance **297** VCU · vintage `2026` · serials after the last used number (e.g. `VCS-2026-000125` – `VCS-2026-000421` if Palthope and VM0047 used 1–124); 🔎 **298** → `QUANTITY_EXCEEDS_VERIFIED` |
| 12 Ledger | retire 10 · transfer 10 to the buyer · buyer retires 5 → **277** available |
| 13 Marketplace | listing 100 · ₹500 · max order 50 · buyer orders **20** = **₹10,000** |
| 14 Payout | 60 % → **₹6,000** to the owner · allocation **Hunsur biochar plant 100 %** · settlement period "Period 1" (this project has one period) |

---

## Part C — Where every value comes from
| Value | Source (real project) | Why |
|---|---|---|
| Permanence 0.89 (> 600 °C), Table 4 defaults, H:C ≤ 0.7, no buffer | ⚙ Verra VM0044 v1.2 | the methodology |
| Biochar produced / used | 🧪 (real: production log, delivery notes, application records) | the amount that stores carbon |
| Carbon content 0.72, H:C 0.35 / 0.41 | 🧪 (real: **biochar lab certificate per batch**) | carbon locked and stability check |
| Temperature 620 °C, technology HIGH | 🧪 (real: kiln / reactor records) | permanence factor |
| Energy emissions 4.5 / 1.5 / 0.8, transport 2.2 | 🧪 (real: electricity and fuel bills via CDM tools TOOL05 / TOOL03 / TOOL12) | deducted emissions |
| Site, owner | ✍ / 🧪 | project record |

## Part D — Errors you may see
| Code | Fix |
|---|---|
| `INELIGIBLE_BIOCHAR` | an H:C ratio above 0.7 with soil use — check the lab certificate |
| `MISSING_REQUIRED_INPUT` (V44_FCP / V44_TEMP) | high technology needs the lab carbon content and a measured temperature |
| `INVALID_INPUT` | used more than produced, or technology not `HIGH` / `LOW` |
| `CONFIGURATION_REQUIRED` on plan approval | acknowledge the gaps — biochar does not use sampling |
