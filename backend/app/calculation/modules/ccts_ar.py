"""India CCTS offset mechanism — A/R methodologies BM FR05.002 v1.0 (lands except wetlands) and BM FR05.001 v1.0 (degraded mangrove
habitats), with the tool BM-T-AR-0004 v1.0 (trees and shrubs).

Calculation specification: `methodology-docs/CCTS/CCTS_AR_calculation_spec.md` (equations in `extract_ar.md`). Per verification
(the reporting period, compared with the previous approved period or with the pre-project stock at the first verification):

- tree carbon stock by stratified random plot sampling (BM-T-AR-0004 Eqs. 12-17; per-plot root-shoot ratio, Appendix 1),
  shrubs from crown cover (Eqs. 26-27); change between two independent estimates (Eqs. 1-2) with the Appendix 2 discount;
- FR05.001 only: SOC of planted areas at the default 0.50 t C/ha/yr for 20 years (FR05.001 Eq. 4);
- ΔC_AR = ΔC_P − GHG_E − ΔC_BSL − LK (FR05.002 Eqs. 1-5); lCCC for the verification period (Eq. 7), whole units rounded down;
  a negative lCCC is the number of credits to be replaced (para 21).

Dead wood and litter (optional pools, BM-T-AR-0003) are not included (conservative). Burning emissions (BM-T-AR-0002) and leakage
(BM-T-AR-0005) are recorded in t CO2e from those tools. NOT_PRODUCTION_READY until the production-readiness approval is recorded.
"""
from collections import defaultdict
from datetime import date
from decimal import ROUND_FLOOR, Decimal, localcontext
from typing import Any, ClassVar

from app.calculation import framework as fw
from app.calculation.framework import CalculationBlocked, CalculationContext, CalculationModule, Constant, InputValue, Output, Step, Variable
from app.calculation.library import ar_cdm

D0, D1 = Decimal(0), Decimal(1)
T = "t CO2e"
R_BSL, R_PRJ, R_PE, R_REM, R_LK, R_UNC, R_ADJ, R_NET = ("AR-BSL", "AR-PRJ", "AR-PE", "AR-REM", "AR-LK", "AR-UNC", "AR-ADJ", "AR-NET")


def _rule(code: str, title: str, parameter: str, unit: str, ref: str, level: str, frequency: str, source: str = "FIELD") -> dict[str, Any]:
    return {"rule_code": code, "title": title, "parameter": parameter, "unit": unit, "measurement_source": source, "data_level": level,
            "frequency": frequency, "source_reference": ref}


_VER = "Each verification"
BASE_RULES: tuple[dict[str, Any], ...] = (
    _rule("AR_PLOT_AGB", "Above-ground tree biomass in the sample plot (sum of the trees' allometric / volume x density x BEF biomass)",
          "plot_agb", "t d.m.", "BM-T-AR-0004 Appendix 1 Eqs. 2-5 (B_TREE,p,i without roots)", "SAMPLING_POINT", _VER),
    _rule("AR_PLOT_AREA", "Size of the sample plots", "plot_area", "ha", "BM-T-AR-0004 Appendix 1 Eq. 1 A_PLOT,i", "PROJECT", _VER),
    _rule("AR_BSL_STOCK", "Pre-project carbon stock of trees and shrubs (crown-cover method, or 0)", "baseline_stock", T,
          "BM-T-AR-0004 Eqs. 20-21; Eq. 1 note 1 (C_TREE,t1 at the first verification)", "PROJECT", "Project start", "FIELD_ACTIVITY"),
    _rule("AR_BSL_CHANGE", "Baseline removals in the period (trees and shrubs; 0 when the tool's conditions are met)", "baseline_change", T,
          "FR05.002 Eq. 1; BM-T-AR-0004 Eqs. 9-10", "PROJECT", _VER, "FIELD_ACTIVITY"),
    _rule("AR_SHRUB_CC", "Shrub crown cover of the stratum (fraction)", "shrub_crown_cover", "fraction", "BM-T-AR-0004 Eq. 27 CC_SHRUB,i",
          "STRATUM", _VER),
    _rule("AR_B_FOREST", "Default above-ground forest biomass of the region (IPCC GPG-LULUCF)", "forest_biomass_default", "t d.m./ha",
          "BM-T-AR-0004 Eq. 27 b_FOREST", "PROJECT", "Validation", "FIELD_ACTIVITY"),
    _rule("AR_GHG_E", "Non-CO2 emissions from burning woody biomass (BM-T-AR-0002)", "burning_emissions", T, "FR05.002 Eq. 2 GHG_E,t",
          "PROJECT", _VER, "FIELD_ACTIVITY"),
    _rule("AR_LK", "Leakage from displacement of agricultural activities (BM-T-AR-0005)", "leakage", T, "FR05.002 Eq. 4 LK_AGRIC,t",
          "PROJECT", _VER, "FIELD_ACTIVITY"),
)
MANGROVE_RULES: tuple[dict[str, Any], ...] = (
    _rule("AR_PLANT_YEAR", "Year the stratum was planted", "planting_year", "year", "FR05.001 Eq. 4 t_PLANT", "STRATUM", "Project start",
          "FIELD_ACTIVITY"),
)

CONSTANTS = (
    Constant("C_TO_CO2", "3.666666666666666666666666666666667", "t CO2/t C", "44/12 (BM-T-AR-0004 Eq. 12)"),
    Constant("CF_TREE", "0.47", "t C/t d.m.", "BM-T-AR-0004 Eq. 12 CF_TREE default"),
    Constant("CF_SHRUB", "0.47", "t C/t d.m.", "BM-T-AR-0004 Eq. 26 CF_s default"),
    Constant("R_SHRUB", "0.40", "ratio", "BM-T-AR-0004 Eq. 26 R_s default"),
    Constant("BDR_SF", "0.10", "ratio", "BM-T-AR-0004 Eq. 27 BDR_SF default"),
)
MANGROVE_CONSTANTS = (
    Constant("DSOC_RATE", "0.50", "t C/ha/yr", "FR05.001 Eq. 4 dSOC default (t_PLANT to t_PLANT + 20)"),
    Constant("DSOC_YEARS", "20", "yr", "FR05.001 Eq. 4 (20 years after planting)"),
)

ASSUMPTIONS = (
    "Sample plots are the sampling points of the period's design; each records the plot's above-ground tree biomass (t d.m.) from the "
    "species allometric equation (or volume x density x BEF 1.15); the per-tree sheets are attached as evidence.",
    "Below-ground biomass per plot: R = e^(-1.085 + 0.9256 ln b) / b with b = the plot's above-ground biomass per ha (Appendix 1).",
    "Stock change = difference of two independent estimates (Eqs. 1-2): the current campaign minus the previous approved campaign, or "
    "minus the pre-project stock (AR_BSL_STOCK, 0 when not recorded) at the first verification; the previous estimate is used "
    "undiscounted (Eq. 1 note 2).",
    "Appendix 2 discount is applied to the stock change (a project estimate: decreased by discount x U x |dC|).",
    "Shrubs (optional): crown cover per stratum x BDR_SF 0.10 x b_FOREST; < 5 % crown cover = 0.",
    "Dead wood and litter (optional pools) are excluded (conservative); FR05.002 SOC (BM-T-AR-0006) is not included.",
    "Burning emissions and leakage are recorded in t CO2e from BM-T-AR-0002 / BM-T-AR-0005; baseline removals from BM-T-AR-0004 Eqs. 9-10 "
    "(0 when its conditions are met).",
    "Credits: lCCC = net removals of the verification period (Eq. 7), whole units rounded down; a negative lCCC is reported as "
    "REPLACEMENT_DUE (para 21). tCCC (Eq. 6) is the running sum of the lCCC of all verifications, kept by the registry.",
)


class _CctsAr(CalculationModule):
    version = "1.0.0"
    version_label = "1.0"
    calculation_rules_version = 0
    readiness = fw.NOT_PRODUCTION_READY
    mangrove: ClassVar[bool] = False
    sampling_parameters: ClassVar[dict[str, Any]] = {"quantification_approach": "PLOT_SAMPLING", "min_samples_per_stratum": 2,
                                                     "statistical_design": "STRATIFIED_RANDOM"}
    assumptions = ASSUMPTIONS

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not getattr(cls, "code", ""):
            return
        m = cls.methodology_code.replace("BM-", "")
        cls.calculation_rule_definitions = (
            {"rule_code": R_BSL, "step": "BASELINE", "title": "Carbon stock at the previous verification (or pre-project) and baseline removals",
             "equation_reference": f"{m} Eq. 1; BM-T-AR-0004 Eqs. 1, 9-10, 20-21"},
            {"rule_code": R_PRJ, "step": "PROJECT", "title": "Tree and shrub carbon stock at this verification (plot sampling)",
             "equation_reference": "BM-T-AR-0004 Eqs. 12-17, 26-27; Appendix 1"},
            {"rule_code": R_PE, "step": "EMISSIONS", "title": "Non-CO2 emissions from burning woody biomass",
             "equation_reference": f"{m} Eq. 2; BM-T-AR-0002"},
            {"rule_code": R_REM, "step": "REMOVALS",
             "title": "Change in project carbon stocks" + (" incl. SOC of planted areas" if cls.mangrove else ""),
             "equation_reference": f"{m} Eq. 3" + (", Eq. 4" if cls.mangrove else "") + "; BM-T-AR-0004 Eq. 1"},
            {"rule_code": R_LK, "step": "LEAKAGE", "title": "Leakage (displacement of agricultural activities)",
             "equation_reference": f"{m} Eq. {5 if cls.mangrove else 4}; BM-T-AR-0005"},
            {"rule_code": R_UNC, "step": "UNCERTAINTY", "title": "Uncertainty of the stock change (90 %)",
             "equation_reference": "BM-T-AR-0004 Eqs. 2, 15"},
            {"rule_code": R_ADJ, "step": "ADJUSTMENT", "title": "Uncertainty discount above 10 %", "equation_reference": "BM-T-AR-0004 Appendix 2"},
            {"rule_code": R_NET, "step": "NET", "title": "Net anthropogenic removals; lCCC for the verification period",
             "equation_reference": f"{m} Eqs. {'6-8' if cls.mangrove else '5-7'}"},
        )
        cls.rules = {r["rule_code"]: r["step"] for r in cls.calculation_rule_definitions}
        cls.steps = tuple(Step(r["step"], fw.IMPLEMENTED, r["rule_code"]) for r in cls.calculation_rule_definitions)
        cls.monitoring_rule_definitions = (*BASE_RULES, *(MANGROVE_RULES if cls.mangrove else ()))
        cls.constants = (*CONSTANTS, *(MANGROVE_CONSTANTS if cls.mangrove else ()))
        rec = lambda code, rule, unit, level, period="CURRENT": Variable(  # noqa: E731
            code, "MONITORING_RECORD", unit, level, rule_code=rule, required=False, period=period)
        cls.variables = (
            Variable("PLOT_AGB", "MONITORING_RECORD", "t d.m.", "SAMPLING_POINT", rule_code="AR_PLOT_AGB"),
            Variable("PLOT_AREA", "MONITORING_RECORD", "ha", "PROJECT", rule_code="AR_PLOT_AREA"),
            rec("PLOT_AGB_T0", "AR_PLOT_AGB", "t d.m.", "SAMPLING_POINT", "PREVIOUS"),
            rec("PLOT_AREA_T0", "AR_PLOT_AREA", "ha", "PROJECT", "PREVIOUS"),
            Variable("AREA", "STRATUM_AREA", "ha", "STRATUM"),
            Variable("AREA_T0", "STRATUM_AREA", "ha", "STRATUM", required=False, period="PREVIOUS"),
            rec("BSL_STOCK", "AR_BSL_STOCK", T, "PROJECT"),
            rec("BSL_CHANGE", "AR_BSL_CHANGE", T, "PROJECT"),
            rec("SHRUB_CC", "AR_SHRUB_CC", "fraction", "STRATUM"),
            rec("SHRUB_CC_T0", "AR_SHRUB_CC", "fraction", "STRATUM", "PREVIOUS"),
            rec("B_FOREST", "AR_B_FOREST", "t d.m./ha", "PROJECT"),
            rec("GHG_E", "AR_GHG_E", T, "PROJECT"),
            rec("LK", "AR_LK", T, "PROJECT"),
            *((rec("PLANT_YEAR", "AR_PLANT_YEAR", "year", "STRATUM"),) if cls.mangrove else ()),
        )

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _k(ctx: CalculationContext, code: str) -> Decimal:
        v = ctx.constant(code).value
        assert isinstance(v, Decimal)
        return v

    @staticmethod
    def _rec(v: InputValue) -> str:
        return str(v.context.get("stratum_record_id") or v.stratum_id or "")

    @staticmethod
    def _total(ctx: CalculationContext, var: str) -> tuple[Decimal, tuple[int, ...]]:
        vals = ctx.values(var)
        return sum((Decimal(v.value) for v in vals), D0), tuple(v.seq for v in vals)

    def _campaign(self, ctx: CalculationContext, agb_var: str, plot_area_var: str, area_var: str,
                  cc_var: str) -> tuple[ar_cdm.StockEstimate, Decimal, tuple[int, ...]] | None:
        plots = ctx.values(agb_var)
        if not plots:
            return None
        sizes = ctx.values(plot_area_var)
        if not sizes or Decimal(sizes[0].value) <= 0:
            raise CalculationBlocked("MISSING_REQUIRED_INPUT", "The sample plot size (AR_PLOT_AREA) is needed.", {"variable": plot_area_var})
        plot_ha = Decimal(sizes[0].value)
        areas = {self._rec(a): (Decimal(a.value), a.seq) for a in ctx.values(area_var) if a.context.get("stratum_role", "PROJECT") == "PROJECT"}
        if not areas and area_var == "AREA_T0":
            areas = {self._rec(a): (Decimal(a.value), a.seq) for a in ctx.values("AREA")}
        per_stratum: dict[str, list[Decimal]] = defaultdict(list)
        for p in plots:
            agb_ha = Decimal(p.value) / plot_ha
            per_stratum[self._rec(p)].append(agb_ha * (D1 + ar_cdm.mokany_root_shoot(agb_ha)))           # Appendix 1 Eqs. 1, 4
        missing = sorted(set(per_stratum) - set(areas))
        if missing:
            raise CalculationBlocked("MISSING_REQUIRED_INPUT", f"Plots in strata without an area: {', '.join(missing)}.", {"variable": area_var})
        try:
            est = ar_cdm.stratified_stock([(areas[s][0], v) for s, v in per_stratum.items()], self._k(ctx, "CF_TREE"))
        except ValueError as e:
            raise CalculationBlocked("INSUFFICIENT_SAMPLES", str(e), {"reason": "TOO_FEW_PLOTS"}) from None
        shrubs = D0
        cc = ctx.values(cc_var)
        b_forest = ctx.values("B_FOREST")
        if cc:
            if not b_forest:
                raise CalculationBlocked("MISSING_REQUIRED_INPUT", "Shrub crown cover needs the default forest biomass (AR_B_FOREST).",
                                         {"variable": "B_FOREST"})
            strata = [(areas.get(self._rec(v), (D0, 0))[0], Decimal(v.value)) for v in cc]
            shrubs = ar_cdm.shrub_carbon(strata, Decimal(b_forest[0].value), self._k(ctx, "BDR_SF"), self._k(ctx, "CF_SHRUB"),
                                         self._k(ctx, "R_SHRUB"))
        seqs = tuple(sorted({p.seq for p in plots} | {s.seq for s in sizes} | {q for _, q in areas.values()} | {v.seq for v in cc}
                            | ({b_forest[0].seq} if cc and b_forest else set())))
        return est, shrubs, seqs

    def validate_inputs(self, ctx: CalculationContext) -> None:
        if self._campaign(ctx, "PLOT_AGB", "PLOT_AREA", "AREA", "SHRUB_CC") is None:
            raise CalculationBlocked("MISSING_REQUIRED_INPUT", "No sample plot biomass (AR_PLOT_AGB) in the period.", {"variable": "PLOT_AGB"})

    # ------------------------------------------------------------------ steps
    def calculate_baseline(self, ctx: CalculationContext) -> list[Output]:
        prev = self._campaign(ctx, "PLOT_AGB_T0", "PLOT_AREA_T0", "AREA_T0", "SHRUB_CC_T0")
        bsl_change, bc_seqs = self._total(ctx, "BSL_CHANGE")
        lin = bc_seqs or (ctx.constant("C_TO_CO2").seq,)
        if prev is None:
            stock, s_seqs = self._total(ctx, "BSL_STOCK")
            return [Output("C_T1", "BASELINE", R_BSL, stock, T, inputs=s_seqs or (ctx.constant("C_TO_CO2").seq,)),
                    Output("U_T1", "BASELINE", R_BSL, D0, "fraction", outputs=("C_T1",)),
                    Output("DC_BSL", "BASELINE", R_BSL, bsl_change, T, inputs=lin)]
        est, shrubs, seqs = prev
        return [Output("C_T1", "BASELINE", R_BSL, est.carbon_t_co2e + shrubs, T, inputs=(*seqs, ctx.constant("CF_TREE").seq)),
                Output("U_T1", "BASELINE", R_BSL, est.uncertainty, "fraction", inputs=seqs),
                Output("DC_BSL", "BASELINE", R_BSL, bsl_change, T, inputs=lin)]

    def calculate_project(self, ctx: CalculationContext) -> list[Output]:
        cur = self._campaign(ctx, "PLOT_AGB", "PLOT_AREA", "AREA", "SHRUB_CC")
        assert cur is not None
        est, shrubs, seqs = cur
        return [Output("B_TREE_MEAN", "PROJECT", R_PRJ, est.mean_biomass_t_ha, "t d.m./ha", inputs=seqs),
                Output("C_TREE_T2", "PROJECT", R_PRJ, est.carbon_t_co2e, T, inputs=(ctx.constant("CF_TREE").seq,), outputs=("B_TREE_MEAN",)),
                Output("C_SHRUB_T2", "PROJECT", R_PRJ, shrubs, T, inputs=seqs),
                Output("U_T2", "PROJECT", R_PRJ, est.uncertainty, "fraction", inputs=seqs),
                Output("C_T2", "PROJECT", R_PRJ, est.carbon_t_co2e + shrubs, T, outputs=("C_TREE_T2", "C_SHRUB_T2"))]

    def calculate_emissions(self, ctx: CalculationContext) -> list[Output]:
        e, seqs = self._total(ctx, "GHG_E")
        return [Output("GHG_E", "EMISSIONS", R_PE, e, T, inputs=seqs or (ctx.constant("C_TO_CO2").seq,))]

    def _soc(self, ctx: CalculationContext) -> tuple[Decimal, tuple[int, ...]]:
        """FR05.001 Eq. 4 for the years of the reporting period: 44/12 × Σ A_PLANT × 0.50 × years within 20 years of planting."""
        if not self.mangrove:
            return D0, ()
        rp = ctx.snapshot["reporting_period"]
        start, end = date.fromisoformat(rp["start"]), date.fromisoformat(rp["end"])
        areas = {self._rec(a): (Decimal(a.value), a.seq) for a in ctx.values("AREA")}
        total, seqs = D0, []
        for v in ctx.values("PLANT_YEAR"):
            planted = int(Decimal(v.value))
            last = planted + int(self._k(ctx, "DSOC_YEARS"))
            years = sum(1 for y in range(start.year, end.year + 1) if planted <= y < last)
            area, a_seq = areas.get(self._rec(v), (D0, 0))
            total += area * self._k(ctx, "DSOC_RATE") * Decimal(years)
            seqs += [v.seq, a_seq] if a_seq else [v.seq]
        return total * self._k(ctx, "C_TO_CO2"), tuple(seqs)

    def calculate_removals(self, ctx: CalculationContext) -> list[Output]:
        o = ctx.output
        soc, soc_seqs = self._soc(ctx)
        return [Output("DC_TREES_SHRUBS", "REMOVALS", R_REM, o("C_T2").value - o("C_T1").value, T, outputs=("C_T2", "C_T1")),   # Eq. 1
                Output("DSOC", "REMOVALS", R_REM, soc, T, inputs=soc_seqs or (ctx.constant("C_TO_CO2").seq,))]

    def calculate_leakage(self, ctx: CalculationContext) -> list[Output]:
        lk, seqs = self._total(ctx, "LK")
        return [Output("LK", "LEAKAGE", R_LK, lk, T, inputs=seqs or (ctx.constant("C_TO_CO2").seq,))]

    def calculate_uncertainty(self, ctx: CalculationContext) -> list[Output]:
        o = ctx.output
        u = ar_cdm.change_uncertainty(o("C_T1").value, o("U_T1").value, o("C_T2").value, o("U_T2").value)                       # Eq. 2
        return [Output("U_DC", "UNCERTAINTY", R_UNC, u, "fraction", outputs=("C_T1", "U_T1", "C_T2", "U_T2")),
                Output("DISCOUNT", "UNCERTAINTY", R_UNC, ar_cdm.discount_fraction(u), "fraction of U", outputs=("U_DC",))]

    def apply_methodology_adjustments(self, ctx: CalculationContext) -> list[Output]:
        o = ctx.output
        dc = ar_cdm.conservative(o("DC_TREES_SHRUBS").value, o("U_DC").value)                                                    # App. 2
        return [Output("DC_TREES_SHRUBS_ADJ", "ADJUSTMENT", R_ADJ, dc, T, outputs=("DC_TREES_SHRUBS", "U_DC", "DISCOUNT"))]

    def calculate_net_result(self, ctx: CalculationContext) -> list[Output]:
        o = ctx.output
        dcp = o("DC_TREES_SHRUBS_ADJ").value + o("DSOC").value                                                                    # Eq. 3
        net = dcp - o("GHG_E").value - o("DC_BSL").value - o("LK").value                                                          # Eqs. 2, 5
        with localcontext(fw.DECIMAL_CONTEXT):
            credits = max(D0, net).to_integral_value(rounding=ROUND_FLOOR)
        return [Output("DC_P", "NET", R_NET, dcp, T, outputs=("DC_TREES_SHRUBS_ADJ", "DSOC")),
                Output("DC_AR", "NET", R_NET, net, T, outputs=("DC_P", "GHG_E", "DC_BSL", "LK")),
                Output("REPLACEMENT_DUE", "NET", R_NET, -net if net < 0 else D0, T, outputs=("DC_AR",)),
                Output("LCCC", "NET", R_NET, credits, "lCCC (t CO2e)", outputs=("DC_AR",), is_final=True)]


class CctsFr05002(_CctsAr):
    code = "CCTS-FR05.002"
    methodology_code = "BM-FR05.002"
    label = "CCTS BM FR05.002 v1.0 - afforestation / reforestation of lands except wetlands"


class CctsFr05001(_CctsAr):
    code = "CCTS-FR05.001"
    methodology_code = "BM-FR05.001"
    mangrove = True
    label = "CCTS BM FR05.001 v1.0 - afforestation / reforestation of degraded mangrove habitats"
