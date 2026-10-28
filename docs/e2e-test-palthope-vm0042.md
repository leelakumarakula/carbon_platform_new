# End-to-end test — Palthope Estate (dmrv_db1 · Verra VCS · VM0042 v2.2 · farm to farmer payout)

This is the complete test of the platform on the new database **dmrv_db1**, from an empty catalog to a farmer payout. It uses the
**real soil reports of Ganesh Consultancy & Analytical Services, Mysore** for the project farm:

| Round | Report | Samples (organic carbon) |
|---|---|---|
| **Baseline (Period 0)** | Ganesh Consultancy, collected **16-09-2026** (C-11169 … C-11172) | 3 Soil **1.40 %** · 2/Weather **2.39 %** · Palthope Hub **2.01 %** · Palthope Probe **1.74 %** |
| **Monitoring (Period 1)** | Ganesh Consultancy, collected **25-09-2026** (C-11543 … C-11546) | P1 **1.83 %** · P2 **1.78 %** · H1 **1.14 %** · H2 **2.77 %** |

Everything the reports do not contain is filled with **TEST VALUES**, marked 🧪 in this document. Replace the values marked ✍ with your
own (farmer name, phone, farm boundaries).

| | |
|---|---|
| Database | `dmrv_db1` (organizations and 19 users only; everything else empty) |
| Code | backend and frontend both on branch **`fixes_14/10`** |
| Password for every user | **`Test@12345678`** (no forced change) |
| Expected credits | **61 VCUs** — the same for any farm area (see Part C) |
| Farmer payout | **₹3,000.00** (60 % of ₹5,000 sales) |

**Markers:** 🔎 = negative check: the action must be **refused** (a refusal is a pass) · ⚠ = a known trap · 🧪 = test value (not in the
reports) · ✍ = enter your own real value.

---

## Part A — Before you start

### A.1 Start the application on dmrv_db1
1. `backend/.env` must contain `DATABASE_URL=…/dmrv_db1?…` (already set). **Restart the backend** (uvicorn) so it connects to dmrv_db1.
2. Frontend: `npx ng serve` in `carbon_frontend/carbon_project_frontend` → http://localhost:4200. Press **Ctrl+F5** once.
3. Both repositories must be on branch `fixes_14/10`.

### A.2 Have ready
| Item | Why |
|---|---|
| At least **3 GB free on C:** | Uploads are refused when the disk is almost full |
| **One JPG** (field photo) and **a few small PDFs** | Every evidence, lab result, registry step needs one. Use the two Ganesh report PDFs as the lab PDFs. |
| ✍ Farmer name and phone, ✍ the 4 farm boundaries (GPS corners) | Stages 4 and 5 |

### A.3 House rules
- **Every action button asks for a reason** — type `ok test` (3+ characters).
- ⚠ **Dates are typed day-month-year** (`16-09-2026` = 16 September 2026). Check the saved value.
- Use 2–3 browser windows (normal, Incognito, another browser) to switch users.
- Almost every approval must be done by a **different person** from the one who submitted it — follow the LOGIN of each step.

### A.4 Users (all `Test@12345678`)
| Login | Role | Organization |
|---|---|---|
| leelak@vayublue.com | Platform Admin | platform-wide |
| ms1@yopmail.com · ms2@yopmail.com | Methodology Specialist (author · approver) | platform-wide |
| compliance@yopmail.com | Marketplace Compliance Officer | platform-wide |
| pm@ · qatester1@ · gis@ · mrv@ · sup@ · col@ · analyst@ | Project Manager · QA Officer · GIS · MRV Manager · Field Supervisor · Field Collector · Calculation Analyst | varsapradaya_developer |
| credits@ · fin1@ · fin2@ · fin3@ | Credit Manager · Finance / Payout Manager ×3 | varsapradaya_developer |
| labtec@ · labmgr@ | Lab Technician · Lab Manager | soiltestlab |
| vvb@yopmail.com | VVB / ACVA Reviewer | verify_co |
| buyer@yopmail.com | Buyer | buyer |

The laboratory organization in the platform is **soiltestlab**; its users enter the Ganesh Consultancy values.

### A.5 Where every value comes from (real report vs test value) — read this first
The Ganesh reports measure **pH, EC, organic carbon, N, P and K** of one composite sample per spot. VM0042 (the Verra methodology the
platform calculates) needs more than that, so the missing values are entered as test values. Only **organic carbon** is used by the
calculation; pH, EC, N, P and K are not VM0042 inputs.

**From the reports (real):**

| Value | Report | Entered as | Where |
|---|---|---|---|
| Organic carbon, baseline | 16-09-2026: Palthope Hub 2.01 %, Palthope Probe 1.74 %, 2/Weather 2.39 %, 3 Soil 1.40 % | `20.1`, `17.4`, `23.9`, `14.0` g/kg (% × 10) | 10.12, top layer of S1 |
| Organic carbon, monitoring | 25-09-2026: H1 1.14 %, P1 1.83 %, H2 2.77 %, P2 1.78 % | `11.4`, `18.3`, `27.7`, `17.8` g/kg | 12 worksheet, top layer of S1 |
| Collection dates | 16-09-2026 and 25-09-2026 | "Collected at" | 10.6, 12.6 |
| Lab report PDFs | both Ganesh PDFs | the result's PDF report | 10.12, 12.12 |
| Sample quantity | "Polythene cover / 1 kg" | `1 kg` per field record | 10.6 |

**Entered for testing (🧪 / ✍) and why:**

| Value | Test value | Why it is needed | In a real project it comes from |
|---|---|---|---|
| Farmer name, phone, district | ✍ yours | A farm must belong to a registered, active farmer; the phone finds the FarmFuture boundaries | farmer registration |
| Farm boundaries (estate + 3 controls) | ✍ FarmFuture import or corners | Sampling points are generated inside the boundary; the area is measured from it | FarmFuture / GPS survey |
| **3 control farms** and their organic carbon | ~1.9 % falling to ~1.85 % | VM0042 compares the project with **at least 3 control farms** that keep the old practice; the reports have none | the same lab, on real neighbouring farms |
| **Second depth layer (30–50 cm)** OC | 0.6 × the top layer | VM0042 compares soil carbon on an equal soil mass, which needs **two depth layers** per point; the reports have one sample per spot and no depth | the lab, one result per depth layer |
| **Soil mass per sample** (285 g / 205 g) | fixed values | Needed to turn g/kg into tonnes per hectare (VM0042 Eq. 3); the reports give no bulk density or mass | the lab (oven-dry fine-earth mass) |
| Probe diameter `21.5 mm`, cores `4` | fixed | Needed with the soil mass (Eq. 3) | the field team's equipment |
| Depth 0–30 / 30–50 cm | fixed | VM0042 reports to at least 30 cm | the sampling plan |
| Soil texture, soil group, climate | sandy clay loam · red lateritic · tropical wet | Control farms must match the project farm on these (VM0042 Table 7) | soil survey |
| Annual rainfall `2200` mm | estimate for a coffee area | **Required**; above 1,000 mm the wet-climate N₂O factors apply | IMD / estate rain gauge |
| Fertiliser, diesel, burning (3 baseline years + this year) | 9,200 → 4,500 kg N, 15,000 → 7,000 L, prunings burned → mulched | VM0042 credits the cut in emissions from the practice change; every source needs a value for the period | estate records |
| Bought compost `20 t` at `0.15` carbon, organic N 2,000 → 3,000 | test | Tests the new leakage deduction (VM0042 Eq. 33) | purchase bills, lab analysis |
| Shade trees `NO` | test | VM0042 may ignore trees only if none are cut | yearly estate declaration |
| Risk rating `12 %` | Verra's minimum | Sets the buffer | VCS AFOLU risk tool |
| Registry, VVB, bank, sale values | test references (VCS-…, UTR-…, NEFT-…) | No real registry, payment or bank is connected | Verra, buyer, bank statements |

**What this means for the result:** the two report rounds are 9 days apart, so the estate's soil carbon does not change measurably and
the platform correctly gives **no soil credit** (uncertainty 100 %). The 61 credits come from the farm-activity test values. The run proves
the whole platform works with the real lab numbers; it is **not** a carbon estimate for Palthope — that needs a second sampling
about a year later, real control farms, soil mass per depth and the estate's real records.

---

## Part B — The flow at a glance

| Stage | Logins in order | Result |
|---|---|---|
| 1 Check setup | leelak | 6 organizations, 19 users |
| 2 Catalog | leelak | Standard `VCS`, activity `IALM` |
| 3 Methodology | ms1 → ms2 | VM0042 2.2 with module v1.2.0 (16 monitoring rules), approved |
| 4 Farmer | pm → qatester1 → pm | Farmer active |
| 5 Farms | pm → gis | Palthope Estate (project) + 3 control farms verified |
| 6 Project | pm → gis → qatester1 → pm | Project eligible |
| 7 Lock | ms1 → pm | VM0042 2.2 locked |
| 8 MRV setup | mrv → qatester1 → mrv → gis → sup | Plan, 2 periods, stratum S1 + control sites C1–C3 |
| 9 Lab engagement | mrv → labmgr | Lab scope: organic carbon + soil mass |
| 10 Period 0 | gis → sup → col → sup → col → sup → labtec → labmgr | 13 points, 26 samples, 52 lab results (**16-09-2026 report**) |
| 11 Period 0 dataset | mrv → qatester1 | Baseline dataset approved |
| 12 Period 1 | same as 10, then mrv | 13 points, 52 results (**25-09-2026 report**), farm activity |
| 13 Calculation | mrv → qatester1 → analyst → qatester1 | **61 VCUs**, run approved |
| 14 Verification | qatester1 → analyst → qatester1 → pm → vvb | Project **Verified** |
| 15 Registry | pm → qatester1 | 61 VCUs **issued** |
| 16 Ledger | credits → qatester1 → buyer | Opened, retired, transferred |
| 17 Marketplace | buyer → compliance → credits → fin1 → buyer → fin1 → qatester1 | 10 credits sold for ₹5,000 |
| 18 Payout | pm → fin1 → fin2 → fin3 | ₹3,000 paid to the farmer and reconciled |

---

## Stage 1 — Check the setup
**LOGIN `leelak`** → Administration → **Organizations** and **Users**.

| Code | Organization | Type |
|---|---|---|
| DEV | varsapradaya_developer | Project developer |
| LAB | soiltestlab | Laboratory |
| VVB | verify_co | VVB |
| BUY | buyer | Buyer |
| VREG | Verra Registry | Registry |
| PLATFORM | Carbon Platform Operator | Platform |

**YOU SHOULD SEE:** the 6 organizations and the 19 users of A.4, all Active.

🔎 **1.1** Log in as `labtec` and open http://localhost:4200/mrv → "You don't have access to this page".

---

## Stage 2 — Catalog
**LOGIN `leelak`** · **GO TO:** Projects → **Standards & activities**

| Card | Field | Enter |
|---|---|---|
| Standard | Code / Name | `VCS` / `Verified Carbon Standard` |
| | Programme owner / Type | `Verra` / Voluntary |
| Activity | Code / Name | `IALM` / `Improved agricultural land management` |
| | Offered under | tick **Verified Carbon Standard** |

**CLICK:** Add standard → Add activity. **YOU SHOULD SEE:** "Offered under: Verified Carbon Standard" on IALM.

---

## Stage 3 — Methodology VM0042 2.2 with its calculation module

### 3.1 · LOGIN `ms1` · FILL
**GO TO:** Methodologies

| Where | Field | Enter |
|---|---|---|
| Add a methodology | Code | **`VM0042`** (exactly) |
| | Name | `Improved Agricultural Land Management` |
| | Standard / Activities | Verified Carbon Standard / Improved agricultural land management |
| New version | New version label | **`2.2`** → **New draft version** → **Open** |
| Version details | Effective from | `21-10-2025` |
| | Source | `Verra VM0042 v2.2` → **Save details** |
| Tab **calculation** | Calculation module | **VM0042 v2.2 - SOC measure & remeasure (QA2) + default-factor emissions (QA3) · v1.2.0** → **Use this module** → **Use module** |
| Tab **applicability** | Rule 1 | Code `A1` · Title `Standard is VCS` · Category Standard · Fact key `standard_code` · Operator EQUALS · Expected value `"VCS"` (with quotes) · If it fails Not applicable → **Add rule** |
| | Rule 2 | Code `A2` · Title `Activity is IALM` · Category Activity · Fact key `activity_code` · EQUALS · `"IALM"` · Not applicable → **Add rule** |

**CLICK:** **Submit for approval**.

**YOU SHOULD SEE:** badge **Module: VM0042-V2.2-QA2-QA3**; 8 calculation rules `V42-BSL` … `V42-NET`; **16 monitoring rules** — the 13
known ones plus **`V42_OA_IMPORTED`** (t), **`V42_OA_CARBON`** (t C/t) and **`V42_WOODY`** (text); status **In review**.

⚠ **Choose the module before submitting** — an approved version can never change its module.

🔎 **3.2** ms1 clicks **Approve** → refused (the author cannot approve).

### 3.3 · LOGIN `ms2` · APPROVE
Open the version → **Approve**. **YOU SHOULD SEE:** **Approved**; "Calculation: Not production ready" (normal outside production).

---

## Stage 4 — Farmer

### 4.1 · LOGIN `pm` · FILL — register and submit KYC
**GO TO:** Farmers → **Register farmer**:

| Field | Enter |
|---|---|
| Managing organization | `varsapradaya_developer` |
| Full name | ✍ the estate owner (🧪 example `Palthope Estate Owner`) |
| Gender / Preferred language | ✍ / `kn` (lower case) |
| Primary phone | ✍ the owner's **FarmFuture mobile number** (the number registered in the FarmFuture app), e.g. `+91 9xxxx xxxxx` — Stage 5 finds the farm boundaries with it |
| Village / District / State / Country | `Palthope` / ✍ district / `Karnataka` / `IN` |

**CLICK:** **Create farmer** → header **Register**. Tab **KYC**: ID type National ID · ID number 🧪 `1234 5678 9012` · any PDF → **Submit for review**.

**YOU SHOULD SEE:** **KYC pending**, ID shown as `••••9012`.

🔎 **4.2** pm on the KYC tab → "You submitted this KYC, so another reviewer must decide".

### 4.3 · LOGIN `qatester1` · VERIFY
Farmers → the farmer → KYC → Review notes `ID checked` → **Verify KYC**. **YOU SHOULD SEE:** **KYC verified**.

### 4.4 · LOGIN `pm` · FILL — consent, activation, agreement
| Tab | Enter | Click |
|---|---|---|
| Consents | keep defaults (Personal data processing v1 · `DATA_PROCESSING-v1` · Paper signed) | **Record consent** |
| Header | — | **Activate** |
| Agreements | Type `PROGRAM_PARTICIPATION` · Template version `v1` · Effective from **`01-09-2026`** | **Create agreement** → **Upload signed copy** (PDF) |

**YOU SHOULD SEE:** farmer **Active**; agreement **Signed** — write down its code `AGR-2026-…` (Stages 6 and 18).

---

## Stage 5 — Farms: Palthope Estate + 3 control farms
VM0042 compares the project farm with **3 control farms**: farms with the same soil and rainfall that **keep the old practice** and are
**not** part of the project. For the test all four farms belong to the same farmer.

### 5.1 · LOGIN `pm` · FILL — four farms
**GO TO:** Farmers → the farmer → tab **Farms** → **Add farm**, once per farm:
1. Farm name · Land tenure Owned · Declared area · Country `IN` → **Create farm and draw boundary**.
2. **Boundary** tab → choose **one** way to get the boundary, then **Check boundary** → **Save as new boundary version**:
   - **A. FarmFuture (recommended when the farm is mapped in FarmFuture):** click **FarmFuture** → leave the mobile number empty (it uses
     the farmer's phone from Stage 4) or type another FarmFuture number → **Find farms** → pick the FarmFuture farm → pick the area
     (the **main outline**, one named zone, or **Whole farm — all areas merged**) → **Use this area**.
   - **B. Corners:** paste the corners into **Paste several corners** (**one `latitude, longitude` per line**) → **Add these corners**.
3. **Documents** tab → Category Land record · Title `RTC <farm name>` · any PDF → **Upload**.
4. **Ownership** tab → Owner type Farmer · Relationship Owner · Share % `100` · Title / survey reference ✍ (🧪 `Sy No 45/2`) · Valid from `01-01-2020` · Evidence document (pre-selected) → **Record ownership**.
5. Header → **Submit for review**.

| Farm name | Role | Boundary corners |
|---|---|---|
| `Palthope Estate` | **project** | ✍ the real estate boundary |
| `Palthope Control C1` | control | ✍ a nearby farm that keeps the old practice |
| `Palthope Control C2` | control | ✍ |
| `Palthope Control C3` | control | ✍ |

**Using FarmFuture boundaries — what to pick:**
- **Palthope Estate (project):** the estate's **main outline** or **Whole farm — all areas merged**.
- **Control farms C1–C3:** three **other** mapped farms (another FarmFuture farm of the same owner, or a neighbour's number) that keep
  the old practice. ⚠ Do **not** use a zone that lies inside the estate's outline: the farms would overlap (overlap flag at review, and the
  control points would fall on project land). If the owner has only the one estate in FarmFuture, draw the controls with way **B**.
- The import is only a candidate: the platform still checks the shape (SQL Server), the overlaps and the GIS review, and records the
  boundary with source **IMPORT** in the audit log. It needs internet access to api.farmfuture.io; if FarmFuture is unreachable you see
  "FarmFuture: … Try again later" — use way B.
- 🔎 **5.1a** FarmFuture with a mobile number that has no FarmFuture account → "FarmFuture has no user with this mobile number" (`FARMFUTURE_USER_NOT_FOUND`).

Rules for your boundaries:
- At least 3 corners each; the four farms **must not overlap** each other.
- Control farms within **250 km** of the estate, each at least **~1 ha** (3 sampling points 10 m apart must fit); the estate must fit 4 points.
- The **credits do not depend on the area** in this test (Part C), so any real size works.

🧪 If you do not have the boundaries yet, use these example squares (estate ≈ 100 ha, controls ≈ 4 ha):

| Farm | Corners (one per line) |
|---|---|
| Palthope Estate | `12.3000, 75.9000` / `12.3000, 75.9092` / `12.3090, 75.9092` / `12.3090, 75.9000` |
| Palthope Control C1 | `12.3000, 75.9200` / `12.3000, 75.9218` / `12.3018, 75.9218` / `12.3018, 75.9200` |
| Palthope Control C2 | `12.3000, 75.9300` / `12.3000, 75.9318` / `12.3018, 75.9318` / `12.3018, 75.9300` |
| Palthope Control C3 | `12.3000, 75.9400` / `12.3000, 75.9418` / `12.3018, 75.9418` / `12.3018, 75.9400` |

🔎 **5.2** pm looks for **Verify farm** on Palthope Estate → not available to the submitter.

### 5.3 · LOGIN `gis` · VERIFY — all four farms
For each farm: tab **Ownership** → **Verify** (`Land record checked`) → header **Start GIS review** → **Verify farm**.
**YOU SHOULD SEE:** four farms **Verified**.

---

## Stage 6 — Project and eligibility

### 6.1 · LOGIN `pm` · FILL
**GO TO:** Projects → **New project**

| Tab / form | Field | Enter |
|---|---|---|
| New project | Organization / Name / Type | varsapradaya_developer / `Palthope VM0042 pilot` / Agricultural land management |
| | Country / Region / **Planned start** | `IN` / `Palthope` / **`01-09-2026`** |
| Header | Start data collection | reason |
| Farms | Farm / Participation from / Rights holder | **Palthope Estate only** / `01-09-2026` / Farmer |
| | Agreement / evidence reference / Share % | `Carbon rights clause of AGR-2026-…` / `100` |
| Standard & activity | Standard / Activity | Verified Carbon Standard → Select / Improved agricultural land management → Select |
| Crediting & baseline | Crediting period | `01-09-2026` – `31-08-2036` → **Record period** |
| | Baseline From / To / Practices / Data sources | `01-09-2023` / `31-08-2026` / `High synthetic N, diesel machinery, burning of coffee prunings` / `Estate records` → **Record baseline** |

**CLICK:** header **Submit for eligibility review**. **YOU SHOULD SEE:** **Eligibility review**.

⚠ **Never add the control farms to the project** (the platform now refuses it anyway: `FARM_IS_CONTROL_SITE`).

### 6.2 · LOGIN `gis` · VERIFY — tab **Boundary** → **Accept boundary**.
### 6.3 · LOGIN `qatester1` · VERIFY + APPROVE — tab **Carbon rights** → **Verify** (`Agreement checked`); header **Approve eligibility** → **Standard selected**.
🔎 **6.4** pm looks for **Approve eligibility** → not shown to the submitter.
### 6.5 · LOGIN `pm` · FILL — header **Confirm activity** → **Activity selected**.

---

## Stage 7 — Lock the methodology
### 7.1 · LOGIN `ms1` · FILL
Projects → Palthope VM0042 pilot → tab **Methodology** → **Evaluate candidates** → expand **VM0042 2.2** (Applicable, A1 ✔ A2 ✔) → **Recommend** → reason `Applicable; module VM0042-V2.2-QA2-QA3`.

🔎 **7.2** ms1 tries **Confirm & lock** → not allowed.

### 7.3 · LOGIN `pm` · APPROVE
Expand → **Confirm & lock**. **YOU SHOULD SEE:** **Methodology confirmed**; **MRV workspace** button.

---

## Stage 8 — MRV plan, periods, strata and control sites
All steps in **MRV → Palthope VM0042 pilot**. A yellow **CONFIGURATION_REQUIRED** banner about sampling depth is normal.

### 8.1 · LOGIN `mrv` · FILL — MRV plan
Tab **MRV plans** → **Create MRV plan**: Monitoring frequency `Annual sampling` · Quantification approach **empty** · Monitoring start
**`01-09-2026`** · end `31-08-2036` · Required evidence `Field photos, GPS, lab reports` → **Create plan (draft)** → **Submit for approval**.

**YOU SHOULD SEE:** **16** `V42_…` measurements listed; **Submitted**.

### 8.2 · LOGIN `qatester1` · APPROVE — open the plan → **Approve** (the dialog notes the depth gap — expected).

### 8.3 · LOGIN `mrv` · FILL — two monitoring periods
Tab **Monitoring periods** → **Create period** twice. The dates put each Ganesh report inside its own period:

| Name | Purpose | Start | End | Report inside it |
|---|---|---|---|---|
| `Period 0 baseline` | Baseline | `01-09-2026` | `20-09-2026` | collected 16-09-2026 |
| `Period 1` | Monitoring | `21-09-2026` | `20-09-2027` | collected 25-09-2026 |

On **both** rows: **Mark planned** → **Start period** → **Open data collection**.
**YOU SHOULD SEE:** both periods **Data collection**; project **Monitoring**.

⚠ The settlement page (Stage 18) lists periods by **number**: "Period 1" there = **Period 0 baseline**, "Period 2" = **Period 1**.

### 8.4 · LOGIN `gis` · FILL — project stratum and 3 control sites
Tab **Stratification** → New. For each characteristic: choose it, type the value, click **+**. **Add all four before creating** (a draft
stratum cannot be edited on screen).

| Toggle | Code / Name | Farms | Represents | Characteristics (all four) |
|---|---|---|---|---|
| Project stratum | `S1` / `Palthope Estate` | Palthope Estate | — | SOIL_TEXTURE 🧪 `sandy clay loam` · SOIL_GROUP 🧪 `Red lateritic` · CLIMATE `Tropical wet` · PRECIPITATION_MM 🧪 `2200` |
| Control site | `C1` / `Control C1` | Palthope Control C1 | S1 | same three + PRECIPITATION_MM `2150` |
| Control site | `C2` / `Control C2` | Palthope Control C2 | S1 | same three + PRECIPITATION_MM `2200` |
| Control site | `C3` / `Control C3` | Palthope Control C3 | S1 | same three + PRECIPITATION_MM `2250` |

Rainfall is now **required** (module v1.2.0); above 1,000 mm the wet-climate N₂O factors and leaching apply. ✍ Use the estate's real annual
rainfall if you have it (keep the control sites within 100 mm of it).

**YOU SHOULD SEE:** "Baseline control sites: **3 of at least 3** · Every stratum has a control site".

🔎 **8.5** gis looks for **Approve** on S1 → not available to the creator.

### 8.6 · LOGIN `sup` · APPROVE — **Approve** S1, C1, C2, C3. **YOU SHOULD SEE:** all four **Approved**.

---

## Stage 9 — Laboratory engagement
### 9.1 · LOGIN `mrv` · FILL — tab **Samples & laboratory** → Laboratory `soiltestlab` · tick **both** `V42_OC` and `V42_SOIL_MASS` → **Propose engagement**.
### 9.2 · LOGIN `labmgr` · APPROVE — **Laboratory → Engagements** → **Accept**. **YOU SHOULD SEE:** engagement **Active**.

---

## Stage 10 — Period 0: baseline sampling and laboratory (report of 16-09-2026)
⚠ Set the **Monitoring period** picker (top right of MRV) to **Period 0 baseline** for every step of this stage.

### 10.1 · LOGIN `gis` · FILL — sampling design
Tab **Sampling design**:

| Field | Enter |
|---|---|
| Code / Name | `SOIL-P0` / `Baseline soil sampling` |
| Sample count — **S1 · C1 · C2 · C3** | **`4` · `3` · `3` · `3`** (S1 = the 4 baseline report samples; every stratum needs at least 3) |
| Statistical design | Stratified random |
| Sampling method | `Soil auger, 4-core composite` |
| Depth top / bottom (cm) | `0` / `50` |
| Target precision / Confidence level / Random seed | empty |
| Min. distance between points (m) | `10` |

**CLICK:** **Create design (13 samples)** → design **Draft**.

### 10.2 · LOGIN `sup` · APPROVE — **Approve design** (`Design checked`). (🔎 gis cannot approve it.)
### 10.3 · LOGIN `gis` · FILL — **Generate sampling points** → **13 points**: 4 in Palthope Estate, 3 in each control farm.
### 10.4 · LOGIN `sup` · FILL — tab **Points & assignments** → **Select unassigned** → Field collector `colfield_test` · Planned date `16-09-2026` → **Assign 13 point(s)**.

### 10.5 · Give each point its key (write it down)
Within each stratum the **lowest** point code is point 1, the next 2, and so on.

| Key | Stratum | Point code (write it) | Report sample it stands for |
|---|---|---|---|
| **S1-1** | S1 | SP-… | Palthope Hub |
| **S1-2** | S1 | SP-… | Palthope Probe |
| **S1-3** | S1 | SP-… | 2/Weather |
| **S1-4** | S1 | SP-… | 3 Soil |
| **C1-1 … C1-3** | C1 | SP-… | 🧪 control |
| **C2-1 … C2-3** | C2 | SP-… | 🧪 control |
| **C3-1 … C3-3** | C3 | SP-… | 🧪 control |

### 10.6 · LOGIN `col` · FILL — field collection on all 13 points
**Field work** → each point → **Start collection**:

| Field | Enter |
|---|---|
| Latitude / Longitude | the point's own coordinates ("Planned point …" at the top) |
| **Collected at** | **`16-09-2026 10:00`** (the report's collection date; inside Period 0) |
| Depth top / bottom (cm) | `0` / `50` (pre-filled) |
| **Probe inside diameter (mm)** | 🧪 **`21.5`** on every point |
| **Number of cores** | 🧪 **`4`** on every point |
| Sample quantity / Unit | `1` / `kg` (the reports: 1 kg polythene cover) |
| Field checklist | tick all boxes |
| Photo | the JPG |

**CLICK:** **Save & submit** → "Submitted for review". 🔎 **10.6a** col tries to accept their own record → not allowed.

### 10.7 · LOGIN `sup` · VERIFY — **Submitted field records** → **Accept** all 13 (`Field record checked`).

### 10.8 · LOGIN `col` · FILL — two depth samples per record (26 samples)
Open each accepted record → **Laboratory samples** → **Register & seal sample**: sample **A** = top layer, sample **B** = bottom layer. Quantity `0.5`, Unit `kg`.

| Layer | Description | Container label | Depth top | Depth bottom | Seal number |
|---|---|---|---|---|---|
| A | `P0 <key> 0-30` (e.g. `P0 S1-1 0-30`) | `P0-<key>-A` | `0` | `30` | `SEAL-P0-<key>-A` |
| B | `P0 <key> 30-50` | `P0-<key>-B` | `30` | `50` | `SEAL-P0-<key>-B` |

Do this for all 13 keys (S1-1 … S1-4, C1-1 … C3-3). **Register sample** per layer → type the seal → **Seal sample**.

**YOU SHOULD SEE:** "Laboratory samples (2)": `0–30 cm` and `30–50 cm`, both **Sealed**.
⚠ The depth must read **30** (not 29.8). ⚠ Don't click Register a third time. A wrong sample: **sup** → the sample → **Void**, register again.

### 10.9 · LOGIN `sup` · FILL — **Shipments**: laboratory `soiltestlab` · Carrier `Courier` → **Create shipment** → **Add sealed samples** (all 26) → **Dispatch**.
### 10.10 · LOGIN `labtec` · FILL — **Laboratory → Incoming** → every row: Accept ticked · seal as pre-filled · Condition `intact` → **Record receipt**.
### 10.11 · LOGIN `labtec` · FILL — tab **Samples**: Accession no. **`LAB-` + sample number** (SMP-2026-000031 → `LAB-000031`) → **Register** (one-way — check first). Write each sample code next to its description below.

### 10.12 · LOGIN `labtec` · FILL — enter the 52 results
Tab **Worklist** → each test (LT-…): Method `Dry combustion` (V42_OC) · `Oven-dried at 105 C, sieved < 2 mm` (V42_SOIL_MASS) → **Start test** →
Result type Numeric · Value (table) · Unit pre-filled · **Analysed at** = now (required; it must be after the receipt) → **Save result** →
**PDF report** = the **16-09-2026 Ganesh report** → **Submit for QA**.

**Worksheet — Period 0.** OC in g/kg = the report's % × 10. Top layer (0–30) of S1 = **real report value**; everything else 🧪.

| Description | Report sample | V42_OC (g/kg) | V42_SOIL_MASS (g) |
|---|---|---|---|
| `P0 S1-1 0-30` | Palthope Hub 2.01 % | **20.1** | 🧪 **285** |
| `P0 S1-1 30-50` | 🧪 | **12.1** | 🧪 **205** |
| `P0 S1-2 0-30` | Palthope Probe 1.74 % | **17.4** | 🧪 **285** |
| `P0 S1-2 30-50` | 🧪 | **10.4** | 🧪 **205** |
| `P0 S1-3 0-30` | 2/Weather 2.39 % | **23.9** | 🧪 **285** |
| `P0 S1-3 30-50` | 🧪 | **14.3** | 🧪 **205** |
| `P0 S1-4 0-30` | 3 Soil 1.40 % | **14.0** | 🧪 **285** |
| `P0 S1-4 30-50` | 🧪 | **8.4** | 🧪 **205** |
| `P0 C1-1 0-30` / `30-50` | 🧪 | **19.0** / **11.4** | **285** / **205** |
| `P0 C1-2 0-30` / `30-50` | 🧪 | **19.2** / **11.5** | **285** / **205** |
| `P0 C1-3 0-30` / `30-50` | 🧪 | **18.8** / **11.3** | **285** / **205** |
| `P0 C2-1 0-30` / `30-50` | 🧪 | **19.1** / **11.5** | **285** / **205** |
| `P0 C2-2 0-30` / `30-50` | 🧪 | **18.9** / **11.3** | **285** / **205** |
| `P0 C2-3 0-30` / `30-50` | 🧪 | **19.3** / **11.6** | **285** / **205** |
| `P0 C3-1 0-30` / `30-50` | 🧪 | **18.9** / **11.3** | **285** / **205** |
| `P0 C3-2 0-30` / `30-50` | 🧪 | **19.1** / **11.5** | **285** / **205** |
| `P0 C3-3 0-30` / `30-50` | 🧪 | **19.0** / **11.4** | **285** / **205** |

(The reports give one composite per spot and no depth or bulk density. The 30–50 cm layer is 🧪 0.6 × the top layer; the soil masses are 🧪.)

🔎 **10.12a** labtec tries to approve their own result → refused.

### 10.13 · LOGIN `labmgr` · APPROVE — **Laboratory → QA** → each result → **Start QA review** (all PASS) → Decision APPROVED · Notes `Checked` → **Record decision**.
**YOU SHOULD SEE:** after all 52, the 26 samples **Analysed**. A FAIL: REJECTED with reason → labtec enters v2 → labmgr approves v2.

---

## Stage 11 — Period 0 dataset

### 11.1 · LOGIN `mrv` · FILL (picker **Period 0 baseline**)
Tab **Monitoring data** — one record: Measurement **V42_NPR** (project level) · Value 🧪 `12` · Observed on `16-09-2026` · Phase Monitoring · Source Document → **Record value**.

Tab **Datasets & QA** → Period **Period 0 baseline** → **Create dataset version** → **Open / QA** → **Submit for QA** (`Period 0 complete`).

🔎 **11.2** mrv looks for **Record QA result** → not available to the submitter.

### 11.3 · LOGIN `qatester1` · VERIFY + APPROVE
**Open / QA** → **Start QA review** (PASS or WARN only) → QA result **PASS** → **Record QA result** → **Approve dataset**.
**YOU SHOULD SEE:** dataset and **Period 0 baseline Approved**. ⚠ Never press **Open data collection** on that period again.

---

## Stage 12 — Period 1: remeasurement and laboratory (report of 25-09-2026)
Same steps as Stage 10 with the picker on **Period 1**:

| Step | Difference from Stage 10 |
|---|---|
| 12.1 design | Code `SOIL-P1` · Name `Remeasurement` · counts **`4` · `3` · `3` · `3`** |
| 12.4 assign | Planned date `25-09-2026` |
| 12.5 keys | S1-1 = **H1** · S1-2 = **P1** · S1-3 = **H2** · S1-4 = **P2** · C1-1 … C3-3 controls |
| 12.6 field | **Collected at `25-09-2026 10:00`** (inside Period 1, not in the future) · probe `21.5` · cores `4` |
| 12.8 samples | Descriptions `P1 <key> 0-30` / `P1 <key> 30-50`, labels `P1-<key>-A/B`, seals `SEAL-P1-<key>-A/B` |
| 12.12 results | PDF report = the **25-09-2026 Ganesh report**; values below |

**Worksheet — Period 1.** Top layer of S1 = **real report value**; everything else 🧪 (the control farms lose a little carbon under the old practice).

| Description | Report sample | V42_OC (g/kg) | V42_SOIL_MASS (g) |
|---|---|---|---|
| `P1 S1-1 0-30` | H1 1.14 % | **11.4** | 🧪 **285** |
| `P1 S1-1 30-50` | 🧪 | **6.8** | 🧪 **205** |
| `P1 S1-2 0-30` | P1 1.83 % | **18.3** | 🧪 **285** |
| `P1 S1-2 30-50` | 🧪 | **11.0** | 🧪 **205** |
| `P1 S1-3 0-30` | H2 2.77 % | **27.7** | 🧪 **285** |
| `P1 S1-3 30-50` | 🧪 | **16.6** | 🧪 **205** |
| `P1 S1-4 0-30` | P2 1.78 % | **17.8** | 🧪 **285** |
| `P1 S1-4 30-50` | 🧪 | **10.7** | 🧪 **205** |
| `P1 C1-1 0-30` / `30-50` | 🧪 | **18.5** / **11.1** | **285** / **205** |
| `P1 C1-2 0-30` / `30-50` | 🧪 | **18.7** / **11.2** | **285** / **205** |
| `P1 C1-3 0-30` / `30-50` | 🧪 | **18.3** / **11.0** | **285** / **205** |
| `P1 C2-1 0-30` / `30-50` | 🧪 | **18.6** / **11.2** | **285** / **205** |
| `P1 C2-2 0-30` / `30-50` | 🧪 | **18.4** / **11.0** | **285** / **205** |
| `P1 C2-3 0-30` / `30-50` | 🧪 | **18.8** / **11.3** | **285** / **205** |
| `P1 C3-1 0-30` / `30-50` | 🧪 | **18.4** / **11.0** | **285** / **205** |
| `P1 C3-2 0-30` / `30-50` | 🧪 | **18.6** / **11.2** | **285** / **205** |
| `P1 C3-3 0-30` / `30-50` | 🧪 | **18.5** / **11.1** | **285** / **205** |

### 12.14 · LOGIN `mrv` · FILL — farm activity, compost, shade trees and risk (picker **Period 1**)
Tab **Monitoring data**, one **Record value** per row, Source **Document**. All farm rows: Farm **Palthope Estate**. 🧪 = estate test values.

| # | Measurement | Phase | Observed on | Value |
|---|---|---|---|---|
| 1–3 | V42_FSN · synthetic fertiliser N (kg N) | Baseline | `01-06-2023` · `01-06-2024` · `01-06-2025` | 🧪 `9000` · `9200` · `9400` |
| 4 | V42_FSN | Project | `25-09-2026` | 🧪 `4500` |
| 5–7 | V42_FON · organic fertiliser N (kg N) | Baseline | same three dates | 🧪 `2000` · `2000` · `2000` |
| 8 | V42_FON | Project | `25-09-2026` | 🧪 `3000` (more compost) |
| 9–11 | V42_DIESEL · diesel (L) | Baseline | same three dates | 🧪 `15000` · `15000` · `15000` |
| 12 | V42_DIESEL | Project | `25-09-2026` | 🧪 `7000` |
| 13–15 | V42_BURN_OTHER · other residues burned (kg d.m.) — coffee prunings | Baseline | same three dates | 🧪 `60000` · `62000` · `64000` |
| 16 | V42_BURN_OTHER | Project | `25-09-2026` | 🧪 `0` (prunings mulched) |
| 17 | **V42_OA_IMPORTED** · compost bought from outside the estate (t) | Project | `25-09-2026` | 🧪 `20` |
| 18 | **V42_OA_CARBON** · carbon content of that compost (t C/t) | Project | `25-09-2026` | 🧪 `0.15` (15 % — type **0.15**, not 15) |
| 19 | **V42_WOODY** · woody biomass removed (text) | Project | `25-09-2026` | `NO` (no shade tree cut, no coffee uprooted) |
| 20 | V42_NPR · non-permanence risk rating (%) — project level, no Farm box | Monitoring | `25-09-2026` | 🧪 `12` |

**YOU SHOULD SEE:** 20 rows. Leave V42_GASOLINE, V42_LIMESTONE, V42_DOLOMITE, V42_BURN_RICE, V42_BURN_WHEAT, V42_IRRIGATION empty.

⚠ Every source with Baseline rows **needs a Project row** (enter `0` if not used) — otherwise `PERIOD_RECORD_MISSING`.
⚠ Organic N rose (2000 → 3000), so **row 17 is required** (`OA_DECLARATION_MISSING` without it). Compost made on the estate from its own
coffee pulp is exempt: then row 17 = `0` and row 18 is not needed.
⚠ Row 19 `YES` blocks the calculation (`WOODY_BIOMASS_REMOVED`) — that is a negative test you may try in a copy, not here.

---

## Stage 13 — Period 1 dataset and calculation

### 13.1 · LOGIN `mrv` · FILL — Datasets & QA → Period **Period 1** → **Create dataset version** → **Open / QA** → **Submit for QA** (`Period 1 complete`).
### 13.2 · LOGIN `qatester1` · VERIFY + APPROVE — **Start QA review** → PASS → **Record QA result** → **Approve dataset**. **YOU SHOULD SEE:** **Period 1 Approved**.

### 13.3 · LOGIN `analyst` · FILL — calculation
**GO TO:** **Calculations** → Project `Palthope VM0042 pilot` · Monitoring period **Period 1**.
**YOU SHOULD SEE:** readiness with no red blocker, only "NOT_PRODUCTION_READY: non-production use only".

**CLICK:** **New calculation run** → open the run → **Check readiness & freeze inputs** → **Execute** → **Submit for QA**.
The platform takes **Period 0** automatically as the earlier sampling round.

**Expected results** (Results tab) — computed beforehand with the same module:

| Output | Meaning | Expected |
|---|---|---|
| REF_MASS_… | Reference soil mass to 30 cm (control sites, Period 0) | ≈ 1,898 t/ha |
| SOC_PRO_PREV_… → SOC_PRO_CURR_… | Estate soil carbon, Period 0 → 1 (**real reports**) | ≈ 36.98 → 36.92 t C/ha (no measurable change) |
| SOC_BAS_PREV_… → SOC_BAS_CURR_… | Control farms, Period 0 → 1 | ≈ 37.35 → 36.34 t C/ha |
| UNC_PCT | Sampling uncertainty | **100 %** → the soil part counts as 0 |
| ER_FUEL · ER_N2O_FERT · ER_CH4_BB · ER_N2O_BB | Emission reductions (wet climate) | ≈ 23.09 · 34.67 · 3.75 · 0.92 t CO₂e |
| ER_SOURCES | Total reductions | ≈ 62.43 t CO₂e |
| LK_OA · LK_TOTAL | Leakage of the bought compost (Eq. 33: 20 × 0.15 × 0.12 × 44/12) | **1.32** t CO₂e |
| BUFFER_ER / BUFFER_CR | Buffer (soil part only) | 0 / 0 |
| **VCU_TOTAL** | **Credits (whole tonnes, rounded down)** | **61** — write it down |

The per-stratum outputs end in the first 8 characters of the stratum's internal id, e.g. `REF_MASS_3f2a91c0`.
DCO2_SOIL_WP / DCO2_SOIL_BSL depend on your estate's area (negative values; they do not change the credits).

🔎 **13.4** analyst looks for **Approve** → not available to the run's creator.

### 13.5 · LOGIN `qatester1` · VERIFY + APPROVE
Run page → tab **QA** → **Start calculation QA** → Result `PASS` · Notes `Inputs and outputs checked` → **Record QA** → header **Approve**.
**YOU SHOULD SEE:** run **Approved**; project **Calculated**.

---

## Stage 14 — Internal readiness and VVB verification
| # | LOGIN | Action |
|---|---|---|
| 14.1 | qatester1 | Run page → **Findings** → Category Clarification · Blocking ticked · Title `Lab method` · Description `Confirm the OC method and depth of the Ganesh reports` → **Raise finding** |
| 14.2 | analyst | Response `GCAS/SOP/7.2/TOC; 0-30 cm composite` → **Respond** (🔎 Resolve is not shown to you) |
| 14.3 | qatester1 | **Resolve** → `Accepted` |
| 14.4 | analyst | Run page → **Generate report** → **Verify** ("Hashes verify"); **Calculations** → Period 1 → **Verification readiness** → **Prepare readiness** → **Submit** |
| 14.5 | qatester1 | **Approve (READY)** → `Internal checks complete` |
| 14.6 | pm | MRV → project → tab **Verification** (picker **Period 1**!) → VVB `verify_co` · Notes `Verification of Period 1` → **Propose** |
| 14.7 | vvb | **VVB workspace** → the assignment → declaration `No financial or personal interest in the project or its developer` → **Accept** |
| 14.8 | pm | Verification tab (Period 1) → **Submit READY package** |
| 14.9 | vvb | Tabs Package / Documents → tab **Decision**: Outcome `Verified` · quantity **`61`** (numbers only) · Unit `tCO2e` · Rationale `Sampling, laboratory results and calculation checked against the package` · any PDF → **Record decision** |

⚠ Resolve findings **before** generating the report (else `REPORT_STALE`). ⚠ 14.6 on **Period 1**, not Period 0 (else "no valid READY package").

**YOU SHOULD SEE:** assignment **Completed**; project **Verified**.

---

## Stage 15 — Registry and credit issuance
### 15.1 · LOGIN `pm` · FILL — **Registry** → project · Period `Period 1`:

| Form | Field | Enter | Click |
|---|---|---|---|
| Registry account | Registry / Account ID / Label | **Verra Registry** / `VCS-ACC-001` / `Verra account` | |
| | Registry credit unit / = 1 verified unit | **`VCU`** / **`tCO2e`** | **Record account** |
| Registration | Account | Verra account | **Start registration record** |
| | Registry project ID / Registered on / PDF | `VCS-PRJ-001` / today / any PDF | **Record registered** |
| Submission | Account | Verra account | **Prepare registry submission** → **Freeze snapshot** |
| | Submission reference / receipt PDF | `VCS-SUB-001` / any PDF | **Record submitted** |
| | Outcome / response PDF | Accepted / any PDF | **Record response** |
| Issuance | Issuance ID / date / Unit / statement PDF | `VCS-ISS-001` / today / **`VCU`** / any PDF | |
| | Batch: Vintage / Whole credits | `2026` / **`61`** | |
| | Batch: Serial start / end | `VCS-2026-000001` / **`VCS-2026-000061`** | **Record issuance** |

🔎 **15.2** Record issuance with **62** credits → refused `QUANTITY_EXCEEDS_VERIFIED`.
🔎 **15.3** pm looks for **Confirm** → not shown to the recorder.

### 15.4 · LOGIN `qatester1` · APPROVE — **Confirm (second person)** → `Matches registry statement`.
**YOU SHOULD SEE:** issuance **Confirmed**; batch **Issued**; project **Issued**.

---

## Stage 16 — Credit ledger
Of 61 credits: 5 retired by the developer, 5 moved to the buyer (who retires 2), 51 kept for sale.

| # | LOGIN | GO TO / fields | Click | YOU SHOULD SEE |
|---|---|---|---|---|
| 16.1 | credits | **Credit ledger** → the batch | **Open in ledger** → **Request opening** | Opening Requested (🔎 Confirm not shown) |
| 16.2 | qatester1 | same batch | **Confirm opening** | **61** Available, owner varsapradaya_developer |
| 16.3 | credits | batch → **Details** → Request retirement: Owner varsapradaya_developer · Quantity `5` · Beneficiary `Varsapradaya Developer` · Reason `Test retirement` | **Request retirement** | 5 Retirement pending |
| 16.4 | qatester1 | Details → Retirements: reference `VCS-RET-001` · date today · certificate PDF | **Record retirement** | 5 **Retired** |
| 16.5 | credits | Request transfer: Kind Internal · Sender varsapradaya_developer · Recipient **buyer** · Quantity `5` · Purpose `Test transfer` | **Request transfer** | 5 Transfer pending |
| 16.6 | qatester1 | Details → Transfers | **Complete** | buyer owns 5 |
| 16.7 | buyer | **My credits** → AVAILABLE row → Request retirement: Quantity `2` · Beneficiary `Buyer Co` · Reason `Offsetting 2026 travel` | submit | request listed |
| 16.8 | qatester1 | Credit ledger → batch → Details → Retirements: reference `VCS-RET-002` · date · certificate PDF | **Record retirement** | 2 **Retired**; buyer keeps 3 |

---

## Stage 17 — Marketplace
Sale: **10 credits × ₹500 = ₹5,000**.

| # | LOGIN | GO TO / fields | Click | YOU SHOULD SEE |
|---|---|---|---|---|
| 17.1 | buyer | **Buyer profile**: Legal name `Buyer Co Pvt Ltd` · Country `IN` · Contact name `Asha Rao` · Contact email `buyer@yopmail.com` | **Save** → KYC PDF → **Upload** → **Submit for KYC review** | KYC submitted |
| 17.2 | compliance | **KYC review** → Buyer Co Pvt Ltd | **Verify** (`Documents checked`) | KYC verified |
| 17.3 | credits | **Listings → New listing**: batch (owner varsapradaya_developer · **51**) · Title `Palthope VM0042 VCUs 2026` · Listed quantity `40` · Price `500.00` · Currency `INR` · Min / Max order `1` / `20` · Payment window `48` | **Create draft** → **Submit** | Pending approval (🔎 Approve hidden for you) |
| 17.4 | fin1 | **Listings** | **Approve** (`Price approved`) | listing **Active** |
| 17.5 | buyer | **Marketplace** → listing **Details** → Quantity `10` → **Add to order** · Delivery Ledger transfer | **Place order** | order Placed, **INR 5,000.00** |
| 17.6 | buyer | **Orders** → Open → Payment reference `UTR-0001` · PDF | **Record payment** | Pending confirmation (🔎 no Confirm for you) |
| 17.7 | fin1 | **Payments** | **Confirm receipt** (`Funds received`) | order Transfer pending |
| 17.8 | qatester1 | **Credit ledger** → batch → Details → Transfers row "marketplace order ORD-…" | **Complete** | order **Completed**; buyer's My credits +10 |

---

## Stage 18 — Revenue sharing, settlement and farmer payout
Farmer share 60 % of ₹5,000 = **₹3,000**. fin1 calculates, fin2 approves and reconciles, fin3 pays. Every Finance page: Project `Palthope VM0042 pilot`.

| # | LOGIN | GO TO / fields | Click | YOU SHOULD SEE |
|---|---|---|---|---|
| 18.1 | pm | **Revenue & costs** | — | one revenue record INR 5,000 (automatic) |
| 18.2 | pm | **Revenue sharing** → Farmer share `60` · Rounding HALF_UP · Deduct costs unticked · Effective from **`01-09-2026`** · Source `Farmer agreement AGR-2026-… clause 7` | **Create draft version** → **Submit** (on its row!) | **In review** |
| 18.3 | fin1 | Revenue sharing | **Approve** | Approved (🔎 pm cannot approve) |
| 18.4 | pm | Farm allocation: Monitoring period **"Period 2 · Period 1"** · Basis `Single participating farm` · Palthope Estate `100` (Total 100 %) | **Create draft allocation** → **Submit** | In review |
| 18.5 | fin1 | same | **Approve** | Approved |
| 18.6 | pm | **Farmers** → the farmer → **Bank**: Holder ✍ farmer name · Bank 🧪 `State Bank of India` · Branch 🧪 `Mysore Main` · Routing (IFSC) 🧪 `SBIN0001234` · Account 🧪 `123456789012` | **Add bank account** | Pending verification |
| 18.7 | fin1 | same tab | **Verify** (`Cancelled cheque checked`) | Verified |
| 18.8 | fin1 | **Settlements**: Monitoring period **`Period 2`** (= Period 1) · `INR` · the approved version · the approved allocation | **Create run** → **Calculate** → **Verify (recompute from snapshot)** → **Submit** | the farmer **INR 3,000.00**; "Reproducible" |
| 18.9 | fin2 | Settlements → the run | **Approve** | run Approved (🔎 fin1 can't approve) |
| 18.10 | fin1 | Settlements → **Create payouts**; **Payouts** → **Submit** | | Pending approval |
| 18.11 | fin2 | **Payouts** | **Approve** | Approved, bank ••••9012 |
| 18.12 | fin3 | Payouts | **Execute** → **Record paid**: reference `NEFT-0001` · PDF → **Upload evidence and record PAID** | **Paid** (🔎 fin2 can't execute) |
| 18.13 | fin2 | Payouts → **Reconcile**: Statement reference `NEFT-0001` · amount `3000.00` · `INR` · date today · PDF | **Upload statement and reconcile** | **Reconciled**; settlement **Completed** |

⚠ 18.2 / 18.4: **Create draft** is not enough — click **Submit** on the row, or the approver sees no Approve button.
⚠ 18.8: the Settlements dropdown shows only numbers: pick **Period 2**, then the allocation appears.

**End of the test.** Final checks: Project → **Status history** ends Verified → Issued; Administration → **Audit log** lists every action;
every 🔎 check was refused.

---

## Part C — How the 61 credits come about
1. **Soil (real reports).** Estate soil carbon is ≈ 36.98 t C/ha at the 16-09-2026 sampling and ≈ 36.92 at the 25-09-2026 sampling — the
   two rounds are 9 days apart, so no real change is expected, and the spread between the four spots (1.14 %–2.77 % OC) is large.
2. **Uncertainty 100 %.** Against such a small change the sampling uncertainty is capped at 100 %, so the soil change counts as **zero**
   (no soil credit, no soil buffer). This is why the result is the **same for any estate area**.
3. **Practice change** (estate records 🧪, wet climate because rainfall 2,200 mm > 1,000 mm):
   - synthetic N 9,200 → 4,500 kg N, organic N 2,000 → 3,000 kg N → **N₂O 34.67** t CO₂e saved;
   - diesel 15,000 → 7,000 L → **23.09**;
   - coffee prunings no longer burned (62,000 kg d.m./yr → 0) → **CH₄ 3.75 + N₂O 0.92**;
   - total **62.43** t CO₂e.
4. **Leakage of bought compost** (VM0042 Eq. 33): 20 t × 0.15 t C/t × 0.12 × 44/12 = **1.32** t CO₂e.
5. **VCUs** = 62.43 − 1.32 = 61.11 → rounded down → **61**.

With real second-year samples (12 months later) the soil part would add credits on top, scaled by the estate area.

---

## Part D — Traps (already handled in this document)
| Trap | Effect | Here |
|---|---|---|
| Module chosen after submitting the version | Calculation blocked for ever | 3.1: module first |
| Control farm added to the project | `FARM_IS_CONTROL_SITE` | 6.1: estate only |
| Overlapping farms / another open project on the same land | `DOUBLE_COUNTING_CONFLICT` at plan approval / period start | fresh dmrv_db1, separate boundaries |
| Stratum created with missing characteristics | Control-site check skipped; no screen to fix | 8.4: all four first |
| Rainfall missing | `PRECIPITATION_MISSING` (module v1.2.0) | 8.4 |
| Collection date outside the period | "a collection date within the monitoring period" | 16-09 in P0, 25-09 in P1 |
| Only one depth layer | `DEPTH_INCREMENTS_REQUIRED` | two layers per point |
| Analysed at before the receipt | Lab QA FAIL | analysed now |
| Baseline row without a Project row | `PERIOD_RECORD_MISSING` | 12.14: every source has a Project row |
| Organic N up, no compost declaration | `OA_DECLARATION_MISSING` | 12.14 row 17 |
| Carbon content typed 15 | `OA_CARBON_OUT_OF_RANGE` | 0.15 |
| Verification proposed on Period 0 | "no valid READY package" | 14.6 Period 1 |
| VVB quantity typed with text | refused | `61` only |
| Draft not submitted (finance) | approver sees no Approve | Submit on the row |
| Settlements "Period 1" chosen | allocation dropdown empty | pick "Period 2" |

---

## Part E — Error codes
| Code | Stage | Fix |
|---|---|---|
| A button is missing / `SEPARATION_OF_DUTIES` | any | wrong login, or it is your own submission |
| `FARM_IS_CONTROL_SITE` · `CONTROL_FARM_IN_OTHER_PROJECT` | 6, 8 | control farms stay out of every project |
| `DOUBLE_COUNTING_CONFLICT` | 8 | a farm overlaps a farm of another open project — fix boundaries or close the other project |
| `CONTROL_SITE_NOT_SIMILAR` | 8.6 | texture / soil group / climate differ, or rainfall more than 100 mm apart |
| `PERIOD_OVERLAP` | 8.3 | periods must not overlap (closed ones count too) |
| `PERIOD_NOT_COLLECTING` | 10, 12 | field records change only while the period is in Data collection |
| `INVALID_DEPTH` | 10.8 | sample depth outside 0–50 cm |
| `SAMPLE_NOT_LAB_REGISTERED` | 10.12 | register the accession number first |
| `UNIT_MISMATCH` | 10.12 | unit exactly `g/kg` or `g` |
| `PREVIOUS_PERIOD_REQUIRED` | 13 | Period 0 dataset not approved |
| `CONTROL_SITES_REQUIRED` · `INSUFFICIENT_SAMPLES` | 13 | fewer than 3 sampled control sites / fewer than 2 samples in a group |
| `PERIOD_RECORD_MISSING` | 13 | a Baseline source has no Period 1 row — record it (0 if unused) |
| `PRECIPITATION_MISSING` | 13 | rainfall missing on a stratum |
| `OA_DECLARATION_MISSING` · `OA_CARBON_MISSING` · `OA_CARBON_OUT_OF_RANGE` | 13 | compost rows 17–18 |
| `WOODY_DECLARATION_MISSING` · `WOODY_BIOMASS_REMOVED` | 13 | row 19 must be `NO` or `NONE` |
| `NPR_UNACCEPTABLE` | 13 | risk rating above 60 |
| `REPORT_STALE` | 14 | a finding changed after the report — regenerate |
| `QUANTITY_EXCEEDS_VERIFIED` · `UNIT_EQUIVALENCE_NOT_CONFIGURED` | 15 | more than 61, or units not exactly VCU / tCO2e |
| `BUYER_KYC_REQUIRED` | 17 | buyer KYC not verified |
| `SHARING_RULE_NOT_EFFECTIVE` | 18 | share version must start on or before 21-09-2026 (use 01-09-2026) |
| `BANK_ACCOUNT_NOT_VERIFIED` | 18 | fin1 verifies the bank account (18.7) |
