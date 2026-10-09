# GS 403 v2.1 (Gold Standard A/R): calculation specification for the platform

**Implemented in:** `backend/app/calculation/modules/gs_ar_403.py`, module `GS403-V2.1`. The methodology version must be **code `GS403`, label `2.1`**.

**Tests:** `tests/test_gs_ar_403.py`.

**Equations:** in `extract_gs403.md`. GS 403 does **not** use the CDM A/R tools.

## Chain (per inventory / Performance Certification)
1. **Inventory.** Each plot is a sampling point. It records stem volume `GA_PLOT_VOL` (m³), with plot size `GA_PLOT_AREA` (ha). Each MU is a project stratum.
2. **Precision, per MU.**
   - Error E = t(two-sided 90 %, n − 1) × SE / mean.
   - Accountable mean volume = mean × (1 − max(0, E − 0.20)) (§3.11.5).
3. **Stock (t CO2/ha)** = V × BEF × WD × (1 + R:S) × CF 0.47 × 44/12.
   - Defaults: WD 0.3, BEF 1.1, R:S 0.2. Recorded MU values (`GA_WD`, `GA_BEF`, `GA_RS`) replace them.
   - The stock is capped by the growth model's stock at the date (`GA_CR_MODEL`) and its long-term value (`GA_CR_LT`).
4. **Cumulative net removal** = Σ stock × area + mangrove SOC (1.8 t CO2/ha/yr for up to 20 years), minus:
   - the baseline (`GA_BSL`, from the GS template with the conservative factors);
   - leakage (`GA_LK`);
   - burning: 10 % of the baseline, when `GA_BURNING` = YES;
   - fertiliser: 0.005 × cumulative kg N.
5. **Issuance.**
   - Issuable = max(0, net) − units already issued (`GA_ISSUED_PRIOR`).
   - **Paris alignment (GS 119 v1.2):** the share of the period from 1 Jan 2026 is not credited unless `GA_PAA` = YES.
   - Buffer: 20 %.
   - GSVERs to the project account = floor(eligible − buffer).

## Questions resolved
- **Carbon fraction:** 0.47. The printed "0.475" has the 5 struck through.
- **Error formula:** GS 403 does not define it, so the AR-TOOL14 definition is used, with t at 90 % (two-sided) and df = n − 1.
- **Baseline, leakage and burning:** deducted once, so net removals are cumulative.
- **PERs (forward issuance):** not calculated.
