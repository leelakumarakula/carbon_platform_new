# CCTS BM FR05.002 v1.0 and FR05.001 v1.0 (A/R): calculation specification for the platform

**Implemented in:**
- `backend/app/calculation/modules/ccts_ar.py`, modules `CCTS-FR05.002` (methodology code **`BM-FR05.002`**, label **`1.0`**) and `CCTS-FR05.001` (**`BM-FR05.001`**, **`1.0`**);
- `library/ar_cdm.py`, which implements BM-T-AR-0004 (a near-verbatim copy of CDM AR-TOOL14).

**Tests:** `tests/test_ccts_ar.py`.

**Equations:** in `extract_ar.md`.

## Chain (per verification)
1. **Plots.** Each sample plot is a sampling point. It records its above-ground tree biomass `AR_PLOT_AGB` (t d.m., from the per-tree allometric equation), with plot size `AR_PLOT_AREA` (ha).
   - Per plot, b = AGB / plot size.
   - The total includes roots: b × (1 + R), with R = e^(−1.085 + 0.9256 ln b)/b (Appendix 1).
2. **Stratified stock (Eqs. 12–17).**
   - C = 44/12 × 0.47 × A × Σ w_i·mean_i.
   - Uncertainty: u = t(90 %, df = n − M) × √(Σ w_i² s_i²/n_i) / mean.
   - **Shrubs** (Eqs. 26–27), optional: 44/12 × 0.47 × 1.40 × Σ A·0.10·b_FOREST·cover. Crown cover below 5 % counts as 0.
3. **Change (Eqs. 1–2).**
   - ΔC = C_t2 − C_t1. C_t1 is the previous approved campaign, or the pre-project stock `AR_BSL_STOCK` (default 0) at the first verification.
   - Uncertainty of the change: u_ΔC = √((u1·C1)² + (u2·C2)²)/|ΔC|.
   - **Appendix 2 discount:** up to 10 % → 0; ≤ 15 % → 25 % of U; ≤ 20 % → 50 %; ≤ 30 % → 75 %; above 30 % → 100 %.
4. **FR05.001 only:** SOC = 44/12 × Σ area × 0.50 t C/ha/yr for each year of the period within 20 years of planting (Eq. 4; `AR_PLANT_YEAR`).
5. **Net removals:** ΔC_AR = ΔC_P − GHG_E (`AR_GHG_E`, from BM-T-AR-0002) − ΔC_BSL (`AR_BSL_CHANGE`) − LK (`AR_LK`, from BM-T-AR-0005).
   - **lCCC** = floor(ΔC_AR).
   - A negative result is reported as REPLACEMENT_DUE (para 21).
   - tCCC is the running sum kept by the registry.

## Questions resolved
- **Discount:** applied to the stock change. The previous estimate is used undiscounted (Eq. 1 note 2).
- **Dead wood and litter:** excluded. They are optional pools, so leaving them out is conservative.
- **SOC for FR05.002:** BM-T-AR-0006 is not included (SOC is an optional pool).
- **Burning GWPs (21/310 in BM-T-AR-0002):** they stay inside that tool. Its result is recorded in t CO2e.
- **Crediting:** temporary credits (tCCC / lCCC) per the methodologies. There is no buffer pool.
