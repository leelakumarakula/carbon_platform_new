# Rice methane: VM0051 v1.1 (QA3) and CCTS BM AG04.002 v1.0, calculation specification for the platform

**Implemented in:** `backend/app/calculation/modules/rice.py`.
- `VM0051-V1.1-QA3`: methodology code **`VM0051`**, label **`1.1`**.
- `CCTS-AG04.002`: methodology code **`BM-AG04.002`**, label **`1.0`**.

**Tests:** `tests/test_rice.py`.

**Equations:** in `extract_rice.md`. The VM0051 v1.1 PDF was downloaded and its key equations were checked against page images.

## Data
- **Per farm (field) and season.** Record all values of a season with the **same observed-on date**.
  - **Season records** (phase PROJECT, inside the period):
    - `RI_AREA` (ha), `RI_DAYS` (days);
    - `RI_WATER`: CONTINUOUS / SINGLE / MULTIPLE;
    - `RI_PRESEASON`: SHORT / LONG / VERY_LONG / FLOODED;
    - `RI_STRAW` (t/ha dry) with `RI_STRAW_TIMING` (SHORT / LONG);
    - `RI_COMPOST`, `RI_FYM`, `RI_GREEN` (t/ha fresh);
    - `RI_N` (kg N/ha);
    - VM0051 only: `RI_DIESEL` (L), `RI_BURN` (kg d.m.).
  - **Look-back:** the same measurements with phase **BASELINE**, one set per historical year (at least 3).
- **Per project:**
  - `RI_REGION` (IPCC Table 5.11 region), or `RI_EFC` (country-specific or measured kg CH4/ha/day) with `RI_UNC` (%).
  - VM0051: `RI_PE_AB` and `RI_LE` (t CO2e).
  - AG04.002: `RI_PE_FUEL` (t CO2e).

## Chain
1. **Emission factor:** EF = EFc × SFw (1 / 0.71 / 0.55) × SFp (1.00 / 0.89 / 0.59 / 2.41) × SFo, where SFo = (1 + Σ ROA·CFOA)^0.59.
   - CFOA values: straw 1.00 (< 30 days before cultivation) or 0.19 (> 30 days); compost 0.17; farmyard manure 0.21; green manure 0.45.
2. **CH4** = EF × L × area / 1000 × GWP, per season (GWP applied once).
3. **Baseline:**
   - Water regime: the lowest-emission regime recorded in the look-back. Single drainage in any year means single drainage for the baseline.
   - Straw: 5 t/ha.
   - Other amendments: the look-back mean.
   - Cultivation period: the look-back mean, at most the season's own length.
4. **N2O:**
   - A change in N rate is valued at EF1FR 0.003 (VM0051 Eq. 19).
   - Fields that start draining add N × (0.005 − 0.003) × 44/28 × GWP (VM0051 Eq. 25 / AG04.002 PE_n, corrected).
5. **VM0051:**
   - ER = Δfuel + Δburning + ΔCH4·(1 − UNC) + ΔN2O·(1 − UNC) − LE − PE_AB − PE_drying (Eq. 29).
   - UNC is 15 % with IPCC defaults. Tier 1 is blocked above 60 000 t CO2e per year.
   - GWPs 28 / 265.
6. **AG04.002:**
   - ER = (ΔCH4 + min(0, ΔN2O) − PE_n − PE_fuel) × 0.85.
   - GWPs 29.8 / 273.
7. **Credits:** whole tonnes, rounded down.

## Not included
- QA1 (models) and QA2 (chambers). VM0051 makes QA2 mandatory for methanotrophs, biochar, low-emission cultivars, and AWD shallower than 10 cm.
- The liming CO2 and yield-related leakage terms of VM0051, which have no defining equation. They must be shown to be de minimis.
