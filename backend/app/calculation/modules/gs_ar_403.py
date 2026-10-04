"""Gold Standard for the Global Goals — A/R GHG Emissions Reduction & Sequestration Methodology (GS 403) v2.1.

Calculation specification: `methodology-docs/GS-AR/GS403_calculation_spec.md` (equations in `extract_gs403.md`). GS 403 does not
use the CDM A/R tools: removals per Modelling Unit (MU = project stratum) come from stem volume (forest inventory, BioCarbon Fund
Sourcebook) × wood density × BEF × (1 + R:S) × CF × 44/12 (§3.9-3.10), with the inventory precision rule (±20 % at 90 %, excess
deducted, §3.11.5), capped by the growth model's long-term value (§3.6.6-3.6.12). Baseline, leakage and burning emissions are
deducted once (t = 1, Eqs. 1, 3, 5-7), fertiliser N in the year of use (§3.8). Issuable units are cumulative net removals minus
units already issued (§3.3.3); 20 % go to the GS Compliance Buffer (GHG ER&S Product Requirements v3.2 §11.1.1).

Paris Agreement alignment (GS 119 v1.2): GSVERs of vintages from 1 January 2026 need a PA-aligned methodology; the part of the
period from 2026 is not credited unless the project records its PAA status. NOT_PRODUCTION_READY until the production-readiness
approval is recorded.
"""
from collections import defaultdict
from datetime import date
from decimal import ROUND_FLOOR, Decimal, localcontext
from typing import Any, ClassVar

from app.calculation import framework as fw
from app.calculation.framework import CalculationBlocked, CalculationContext, CalculationModule, Constant, InputValue, Output, Step, Variable
from app.calculation.library import stats

D0, D1 = Decimal(0), Decimal(1)
T = "t CO2e"
PAA_DATE = date(2026, 1, 1)
R_BSL, R_PRJ, R_PE, R_REM, R_LK, R_UNC, R_ADJ, R_NET = ("GA-BSL", "GA-PRJ", "GA-PE", "GA-REM", "GA-LK", "GA-UNC", "GA-ADJ", "GA-NET")

CALC_RULES: tuple[dict[str, Any], ...] = (
    {"rule_code": R_BSL, "step": "BASELINE", "title": "Baseline stock at planting start (deducted once)", "equation_reference": "GS 403 v2.1 Eq. 3"},
    {"rule_code": R_PRJ, "step": "PROJECT", "title": "Tree CO2 stock per MU from the inventory (precision deduction, long-term cap)",
     "equation_reference": "GS 403 v2.1 §3.9-3.11, Eq. 4"},
    {"rule_code": R_PE, "step": "EMISSIONS", "title": "Other emissions: burning for site preparation (10 % of baseline), fertiliser N",
     "equation_reference": "GS 403 v2.1 §3.8"},
    {"rule_code": R_REM, "step": "REMOVALS", "title": "Cumulative CO2 removal of the project area", "equation_reference": "GS 403 v2.1 Eqs. 1, 2"},
    {"rule_code": R_LK, "step": "LEAKAGE", "title": "Leakage (deducted once)", "equation_reference": "GS 403 v2.1 Eqs. 5-7"},
    {"rule_code": R_UNC, "step": "UNCERTAINTY", "title": "Inventory precision (90 % confidence; error above 20 % deducted)",
     "equation_reference": "GS 403 v2.1 §3.11.5"},
    {"rule_code": R_ADJ, "step": "ADJUSTMENT", "title": "Issuable units, Paris alignment of vintages, GS Compliance Buffer (20 %)",
     "equation_reference": "GS 403 v2.1 §3.3.3; GHG ER&S PR v3.2 §11.1; GS 119 v1.2"},
    {"rule_code": R_NET, "step": "NET", "title": "GSVERs to the project account (whole units, rounded down)",
     "equation_reference": "GS 403 v2.1 Eq. 1"},
)


def _rule(code: str, title: str, parameter: str, unit: str | None, ref: str, level: str, frequency: str,
          source: str = "FIELD_ACTIVITY") -> dict[str, Any]:
    return {"rule_code": code, "title": title, "parameter": parameter, "unit": unit, "measurement_source": source, "data_level": level,
            "frequency": frequency, "source_reference": ref}


_INV = "Each forest inventory (before every Performance Certification)"
MONITORING_RULES: tuple[dict[str, Any], ...] = (
    _rule("GA_PLOT_VOL", "Stem volume in the inventory plot (sum of the trees' over-bark stem volume)", "plot_stem_volume", "m3",
          "GS 403 §3.11; BioCarbon Fund Sourcebook", "SAMPLING_POINT", _INV, "FIELD"),
    _rule("GA_PLOT_AREA", "Inventory plot size (slope-corrected)", "plot_area", "ha", "GS 403 §3.11; Sourcebook", "PROJECT", _INV, "FIELD"),
    _rule("GA_WD", "Wood density of the MU", "wood_density", "t d.m./m3", "GS 403 §3.10.2 (default 0.3)", "STRATUM", "Design certification"),
    _rule("GA_BEF", "Biomass expansion factor of the MU", "bef", "factor", "GS 403 §3.10.2 (default 1.1)", "STRATUM", "Design certification"),
    _rule("GA_RS", "Root-to-shoot ratio of the MU (relative, e.g. 0.2)", "root_shoot", "ratio", "GS 403 §3.10.2 (default 0.2)", "STRATUM",
          "Design certification"),
    _rule("GA_CR_LT", "Long-term CO2 removal of the MU (growth model: equilibrium, Option 1, or Eq. 4 average, Option 2)", "long_term_removal",
          "t CO2/ha", "GS 403 §3.6.6-3.6.12, Eq. 4", "STRATUM", "Design certification"),
    _rule("GA_CR_MODEL", "Growth-model CO2 stock of the MU at this inventory date", "modelled_stock", "t CO2/ha", "GS 403 §3.6.1-3.6.5, §3.11.1",
          "STRATUM", _INV),
    _rule("GA_MANGROVE_PLANTED", "Mangrove MU: year planting started (adds 1.8 t CO2/ha/yr for 20 years)", "mangrove_planting_year", "year",
          "GS 403 §2.1 (AR-AM0014 default)", "STRATUM", "Design certification"),
    _rule("GA_BSL", "Baseline stock of the eligible planting area (tree and non-tree, conservative factors)", "baseline_stock", T,
          "GS 403 Eq. 3; §3.4-3.5; §3.10.2 (WD 0.7, BEF 3.5, R:S 0.8 / 4.0)", "PROJECT", "Design certification"),
    _rule("GA_BURNING", "Baseline biomass burned for site preparation: YES or NO", "site_preparation_burning", None, "GS 403 §3.8", "PROJECT",
          "Design certification"),
    _rule("GA_LK", "Leakage of the project area for the whole crediting period", "leakage", T, "GS 403 Eqs. 6-7", "PROJECT", "Design certification"),
    _rule("GA_FERT_N", "Fertiliser N applied (synthetic and organic)", "fertilizer_n", "kg N", "GS 403 §3.8 (0.005 t CO2/kg N)", "FARM",
          "Year of use"),
    _rule("GA_FERT_N_PRIOR", "Fertiliser N applied in earlier monitoring periods (cumulative)", "fertilizer_n_prior", "kg N", "GS 403 §3.8",
          "PROJECT", "Each verification"),
    _rule("GA_ISSUED_PRIOR", "Units already issued for the project (GSVERs and converted PERs, before buffer)", "issued_prior", T,
          "GS 403 §3.3.3; PR §11.2", "PROJECT", "Each verification"),
    _rule("GA_PAA", "Paris Agreement alignment status for 2026+ vintages: YES when approved by Gold Standard", "paa_status", None,
          "GS 119 PAA P&R v1.2", "PROJECT", "When approved"),
)

CONSTANTS = (
    Constant("C_TO_CO2", "3.666666666666666666666666666666667", "t CO2/t C", "44/12 (GS 403 v2.1 §3.10.1)"),
    Constant("CF_TREE", "0.47", "t C/t d.m.", "GS 403 v2.1 §3.10.1a (printed 0.47 with the 5 struck through)"),
    Constant("WD_DEFAULT", "0.3", "t d.m./m3", "GS 403 v2.1 §3.10.2 (CO2 removal)"),
    Constant("BEF_DEFAULT", "1.1", "factor", "GS 403 v2.1 §3.10.2 (CO2 removal)"),
    Constant("RS_DEFAULT", "0.2", "ratio", "GS 403 v2.1 §3.10.2 (CO2 removal)"),
    Constant("PRECISION", "0.20", "fraction", "GS 403 v2.1 §3.11.5 (±20 % at 90 % confidence)"),
    Constant("BURN_FRACTION", "0.10", "fraction", "GS 403 v2.1 §3.8 (10 % of the baseline)"),
    Constant("FERT_EF", "0.005", "t CO2/kg N", "GS 403 v2.1 §3.8"),
    Constant("MANGROVE_SOC", "1.8", "t CO2/ha/yr", "GS 403 v2.1 §2.1 (20 years)"),
    Constant("BUFFER", "0.20", "fraction", "GS GHG ER&S Product Requirements v3.2 §11.1.1"),
)

ASSUMPTIONS = (
    "MU = project stratum (its area = eligible planting area); inventory plots are the sampling points and record stem volume (m3).",
    "Precision per MU: E = t(two-sided 90 %, n - 1) x SE / mean (the AR-TOOL14 definition; GS 403 does not define it); the accountable "
    "mean volume = mean x (1 - max(0, E - 0.20)) (§3.11.5 example).",
    "Creditable stock per MU = min(inventory stock, growth-model stock at the date, long-term value) when those are recorded (§3.6, §3.11.1).",
    "CF 0.47 (the printed '0.475' has the 5 struck through); GS default factors WD 0.3, BEF 1.1, R:S 0.2 unless MU factors are recorded.",
    "Baseline and leakage are recorded as project-area totals from the GS template (conservative factors WD 0.7, BEF 3.5, R:S 0.8 / 4.0) "
    "and deducted once; burning = 10 % of the baseline.",
    "Issuable = max(0, cumulative net removal) - units already issued (§3.3.3); cumulative fertiliser N = prior + this period.",
    "GS 119 v1.2: the share of the issuable amount falling in vintages from 1 January 2026 (by days of the period) is not credited unless "
    "GA_PAA = YES.",
    "20 % of the issuable units go to the GS Compliance Buffer; GSVERs to the project account are whole units rounded down. PERs (forward "
    "issuance) are not calculated here.",
)


def _rec(code: str, rule: str, unit: str, level: str, kind: str = "NUMBER") -> Variable:
    return Variable(code, "MONITORING_RECORD", unit, level, rule_code=rule, required=False, kind=kind)


class Gs403V21(CalculationModule):
    code = "GS403-V2.1"
    version = "1.0.0"
    methodology_code = "GS403"
    version_label = "2.1"
    calculation_rules_version = 0
    readiness = fw.NOT_PRODUCTION_READY
    label = "GS 403 v2.1 - afforestation / reforestation (inventory stem volume, GS conversion factors)"
    rules: ClassVar[dict[str, str]] = {r["rule_code"]: r["step"] for r in CALC_RULES}
    calculation_rule_definitions = CALC_RULES
    monitoring_rule_definitions = MONITORING_RULES
    sampling_parameters: ClassVar[dict[str, Any]] = {"quantification_approach": "FOREST_INVENTORY", "min_samples_per_stratum": 2,
                                                     "target_precision_pct": 20, "confidence_level_pct": 90}
    assumptions = ASSUMPTIONS
    variables = (
        Variable("PLOT_VOL", "MONITORING_RECORD", "m3", "SAMPLING_POINT", rule_code="GA_PLOT_VOL"),
        Variable("PLOT_AREA", "MONITORING_RECORD", "ha", "PROJECT", rule_code="GA_PLOT_AREA"),
        Variable("AREA", "STRATUM_AREA", "ha", "STRATUM"),
        _rec("WD", "GA_WD", "t d.m./m3", "STRATUM"),
        _rec("BEF", "GA_BEF", "factor", "STRATUM"),
        _rec("RS", "GA_RS", "ratio", "STRATUM"),
        _rec("CR_LT", "GA_CR_LT", "t CO2/ha", "STRATUM"),
        _rec("CR_MODEL", "GA_CR_MODEL", "t CO2/ha", "STRATUM"),
        _rec("MANGROVE_PLANTED", "GA_MANGROVE_PLANTED", "year", "STRATUM"),
        _rec("BSL", "GA_BSL", T, "PROJECT"),
        _rec("BURNING", "GA_BURNING", "", "PROJECT", "TEXT"),
        _rec("LK", "GA_LK", T, "PROJECT"),
        _rec("FERT_N", "GA_FERT_N", "kg N", "FARM"),
        _rec("FERT_N_PRIOR", "GA_FERT_N_PRIOR", "kg N", "PROJECT"),
        _rec("ISSUED_PRIOR", "GA_ISSUED_PRIOR", T, "PROJECT"),
        _rec("PAA", "GA_PAA", "", "PROJECT", "TEXT"),
    )
    constants = CONSTANTS
    steps = tuple(Step(r["step"], fw.IMPLEMENTED, r["rule_code"]) for r in CALC_RULES)

    @staticmethod
    def _k(ctx: CalculationContext, code: str) -> Decimal:
        v = ctx.constant(code).value
        assert isinstance(v, Decimal)
        return v

    @staticmethod
    def _rec_id(v: InputValue) -> str:
        return str(v.context.get("stratum_record_id") or v.stratum_id or "")

    @staticmethod
    def _total(ctx: CalculationContext, var: str) -> tuple[Decimal, tuple[int, ...]]:
        vals = ctx.values(var)
        return sum((Decimal(v.value) for v in vals), D0), tuple(v.seq for v in vals)

    def _by_stratum(self, ctx: CalculationContext, var: str) -> dict[str, InputValue]:
        out: dict[str, InputValue] = {}
        for v in ctx.values(var):
            out[self._rec_id(v)] = v
        return out

    def _mus(self, ctx: CalculationContext) -> list[dict[str, Any]]:
        cached = getattr(ctx, "_gs403", None)
        if cached is not None:
            return cached  # type: ignore[no-any-return]
        sizes = ctx.values("PLOT_AREA")
        if not sizes or Decimal(sizes[0].value) <= 0:
            raise CalculationBlocked("MISSING_REQUIRED_INPUT", "The inventory plot size (GA_PLOT_AREA) is needed.", {"variable": "PLOT_AREA"})
        plot_ha = Decimal(sizes[0].value)
        areas = {self._rec_id(a): a for a in ctx.values("AREA") if a.context.get("stratum_role", "PROJECT") == "PROJECT"}
        plots: dict[str, list[InputValue]] = defaultdict(list)
        for p in ctx.values("PLOT_VOL"):
            plots[self._rec_id(p)].append(p)
        factors = {f: self._by_stratum(ctx, f) for f in ("WD", "BEF", "RS", "CR_LT", "CR_MODEL", "MANGROVE_PLANTED")}
        mus = []
        for rec, ps in sorted(plots.items()):
            if rec not in areas:
                raise CalculationBlocked("MISSING_REQUIRED_INPUT", f"Inventory plots in MU {rec} without an area.", {"variable": "AREA"})
            if len(ps) < 2:
                raise CalculationBlocked("INSUFFICIENT_SAMPLES", f"MU {rec} has {len(ps)} inventory plot; at least 2 are needed.",
                                         {"reason": "TOO_FEW_PLOTS"})
            vols = [Decimal(p.value) / plot_ha for p in ps]                                                 # m3/ha per plot
            mean = stats.mean(vols)
            t = stats.t_quantile(0.95, Decimal(len(vols) - 1))
            err = t * (stats.sample_variance(vols) / Decimal(len(vols))).sqrt() / mean if mean > 0 else D1
            v_adj = mean * (D1 - max(D0, err - self._k(ctx, "PRECISION")))                                   # §3.11.5
            fv = {f: (Decimal(factors[f][rec].value) if rec in factors[f] else None) for f in factors}
            wd = fv["WD"] if fv["WD"] is not None else self._k(ctx, "WD_DEFAULT")
            bef = fv["BEF"] if fv["BEF"] is not None else self._k(ctx, "BEF_DEFAULT")
            rs = fv["RS"] if fv["RS"] is not None else self._k(ctx, "RS_DEFAULT")
            stock = v_adj * bef * wd * (D1 + rs) * self._k(ctx, "CF_TREE") * self._k(ctx, "C_TO_CO2")         # §3.9 conversion
            creditable = min([stock] + [x for x in (fv["CR_MODEL"], fv["CR_LT"]) if x is not None])
            seqs = sorted({p.seq for p in ps} | {sizes[0].seq, areas[rec].seq} | {factors[f][rec].seq for f in factors if rec in factors[f]})
            mus.append({"rec": rec, "area": Decimal(areas[rec].value), "mean": mean, "err": err, "stock": stock, "creditable": creditable,
                        "planted": fv["MANGROVE_PLANTED"], "seqs": tuple(seqs)})
        if not mus:
            raise CalculationBlocked("MISSING_REQUIRED_INPUT", "No inventory plot stem volume (GA_PLOT_VOL) in the period.", {"variable": "PLOT_VOL"})
        ctx._gs403 = mus  # type: ignore[attr-defined]
        return mus

    def validate_inputs(self, ctx: CalculationContext) -> None:
        self._mus(ctx)

    def calculate_baseline(self, ctx: CalculationContext) -> list[Output]:
        bsl, seqs = self._total(ctx, "BSL")
        return [Output("BASELINE", "BASELINE", R_BSL, bsl, T, inputs=seqs or (ctx.constant("C_TO_CO2").seq,))]

    def calculate_project(self, ctx: CalculationContext) -> list[Output]:
        outs = []
        for mu in self._mus(ctx):
            r = mu["rec"][:8]
            outs += [Output(f"V_MEAN_{r}", "PROJECT", R_PRJ, mu["mean"], "m3/ha", "STRATUM", mu["rec"], inputs=mu["seqs"]),
                     Output(f"STOCK_{r}", "PROJECT", R_PRJ, mu["stock"], "t CO2/ha", "STRATUM", mu["rec"],
                            inputs=(ctx.constant("CF_TREE").seq, ctx.constant("PRECISION").seq), outputs=(f"V_MEAN_{r}",)),
                     Output(f"CREDITABLE_{r}", "PROJECT", R_PRJ, mu["creditable"], "t CO2/ha", "STRATUM", mu["rec"], inputs=mu["seqs"],
                            outputs=(f"STOCK_{r}",))]
        return outs

    def calculate_emissions(self, ctx: CalculationContext) -> list[Output]:
        burning = any(str(v.value).strip().upper() == "YES" for v in ctx.values("BURNING"))
        b_seqs = tuple(v.seq for v in ctx.values("BURNING"))
        burn = ctx.output("BASELINE").value * self._k(ctx, "BURN_FRACTION") if burning else D0
        fert, f_seqs = self._total(ctx, "FERT_N")
        prior, p_seqs = self._total(ctx, "FERT_N_PRIOR")
        return [Output("OE_BURN", "EMISSIONS", R_PE, burn, T, inputs=(*b_seqs, ctx.constant("BURN_FRACTION").seq), outputs=("BASELINE",)),
                Output("OE_FERT", "EMISSIONS", R_PE, (fert + prior) * self._k(ctx, "FERT_EF"), T,
                       inputs=(*f_seqs, *p_seqs, ctx.constant("FERT_EF").seq))]

    def calculate_removals(self, ctx: CalculationContext) -> list[Output]:
        rp_end = date.fromisoformat(ctx.snapshot["reporting_period"]["end"])
        total, soc = D0, D0
        for mu in self._mus(ctx):
            total += mu["creditable"] * mu["area"]
            if mu["planted"] is not None:
                years = min(Decimal(20), max(D0, Decimal(rp_end.year) - mu["planted"]))
                soc += self._k(ctx, "MANGROVE_SOC") * years * mu["area"]
        creditable = tuple(o for o in ctx.outputs if o.startswith("CREDITABLE_"))
        return [Output("CR_STOCK", "REMOVALS", R_REM, total, T, outputs=creditable),
                Output("CR_MANGROVE_SOC", "REMOVALS", R_REM, soc, T, inputs=(ctx.constant("MANGROVE_SOC").seq,))]

    def calculate_leakage(self, ctx: CalculationContext) -> list[Output]:
        lk, seqs = self._total(ctx, "LK")
        return [Output("LEAKAGE", "LEAKAGE", R_LK, lk, T, inputs=seqs or (ctx.constant("C_TO_CO2").seq,))]

    def calculate_uncertainty(self, ctx: CalculationContext) -> list[Output]:
        worst = max(mu["err"] for mu in self._mus(ctx))
        return [Output("INVENTORY_ERROR_MAX", "UNCERTAINTY", R_UNC, worst, "fraction",
                       outputs=tuple(o for o in ctx.outputs if o.startswith("V_MEAN_")))]

    def apply_methodology_adjustments(self, ctx: CalculationContext) -> list[Output]:
        o = ctx.output
        net_cum = (o("CR_STOCK").value + o("CR_MANGROVE_SOC").value - o("BASELINE").value - o("LEAKAGE").value
                   - o("OE_BURN").value - o("OE_FERT").value)                                                       # Eqs. 1-2, cumulative
        prior, p_seqs = self._total(ctx, "ISSUED_PRIOR")
        issuable = max(D0, max(D0, net_cum) - prior)                                                                 # §3.3.3
        rp = ctx.snapshot["reporting_period"]
        start, end = date.fromisoformat(rp["start"]), date.fromisoformat(rp["end"])
        paa = any(str(v.value).strip().upper() == "YES" for v in ctx.values("PAA"))
        days = (end - start).days + 1
        late = max(0, (end - max(start, PAA_DATE)).days + 1) if end >= PAA_DATE else 0
        share_blocked = D0 if paa else Decimal(late) / Decimal(days)
        eligible = issuable * (D1 - share_blocked)
        buffer = eligible * self._k(ctx, "BUFFER")
        paa_seqs = tuple(v.seq for v in ctx.values("PAA"))
        return [Output("NET_CUMULATIVE", "ADJUSTMENT", R_ADJ, net_cum, T,
                       outputs=("CR_STOCK", "CR_MANGROVE_SOC", "BASELINE", "LEAKAGE", "OE_BURN", "OE_FERT", "INVENTORY_ERROR_MAX")),
                Output("ISSUABLE", "ADJUSTMENT", R_ADJ, issuable, T, inputs=p_seqs, outputs=("NET_CUMULATIVE",)),
                Output("PAA_BLOCKED_SHARE", "ADJUSTMENT", R_ADJ, share_blocked, "fraction", inputs=paa_seqs, outputs=("ISSUABLE",)),
                Output("BUFFER", "ADJUSTMENT", R_ADJ, buffer, T, inputs=(ctx.constant("BUFFER").seq,), outputs=("ISSUABLE", "PAA_BLOCKED_SHARE"))]

    def calculate_net_result(self, ctx: CalculationContext) -> list[Output]:
        o = ctx.output
        eligible = o("ISSUABLE").value * (D1 - o("PAA_BLOCKED_SHARE").value)
        with localcontext(fw.DECIMAL_CONTEXT):
            vers = max(D0, eligible - o("BUFFER").value).to_integral_value(rounding=ROUND_FLOOR)
        return [Output("GSVER_ELIGIBLE", "NET", R_NET, eligible, T, outputs=("ISSUABLE", "PAA_BLOCKED_SHARE")),
                Output("GSVER_PROJECT", "NET", R_NET, vers, "GS VER (t CO2e)", outputs=("GSVER_ELIGIBLE", "BUFFER"), is_final=True)]
