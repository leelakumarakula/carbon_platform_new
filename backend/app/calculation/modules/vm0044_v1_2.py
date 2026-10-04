"""Verra VM0044 Biochar Utilization in Soil and Non-Soil Applications v1.2 (equations unchanged from v1.1).

Calculation specification: `methodology-docs/VM0044-Biochar/VM0044_v1.2_calculation_spec.md` (equations transcribed and checked
against the v1.1 PDF in `extract_vm0044.md`). One project = one biochar production facility p; per monitoring period:

- persistent carbon CC = M_used x F_Cp x PR_de (Eqs. 2/6): F_Cp from laboratory analysis (mandatory for high technology) or
  Table 4 by feedstock and process; PR_de from Table 3 by production temperature (0.56 when unknown);
- production-stage emissions PE_PS = (P_ED + P_EP + P_EC) x M_used / M_produced (Eqs. 3/7); P_EP = 0 for high technology,
  F_e x GWP_CH4 x M_used for low technology (Eq. 9, default F_e 0.049 t CH4/t);
- application-stage emissions (Eqs. 11/12), leakage from transport (Eq. 13; activity shifting / diversion = 0);
- ER = CC x 44/12 − PE_PS − PE_AS − LE (Eqs. 1, 14, 15). No uncertainty deduction and no buffer (VM0044 has none; permanence is
  the 100-year decay factor PR_de).

Grid electricity, fossil fuel and freight emissions are calculated with CDM TOOL05 / TOOL03 / TOOL12 and recorded in t CO2e.
NOT_PRODUCTION_READY until the production-readiness approval is recorded.
"""
from decimal import ROUND_FLOOR, Decimal, localcontext
from typing import Any, ClassVar

from app.calculation import framework as fw
from app.calculation.framework import CalculationBlocked, CalculationContext, CalculationModule, Constant, Output, Step, Variable

D0, D1 = Decimal(0), Decimal(1)
T = "t CO2e"

R_BSL, R_PRJ, R_PE, R_REM, R_LK, R_UNC, R_ADJ, R_NET = ("V44-BSL", "V44-PRJ", "V44-PE", "V44-REM", "V44-LK", "V44-UNC", "V44-ADJ", "V44-NET")
CALC_RULES: tuple[dict[str, Any], ...] = (
    {"rule_code": R_BSL, "step": "BASELINE", "title": "Baseline and sourcing reductions (zero)", "equation_reference": "VM0044 v1.2 §8.1, Eq. 14"},
    {"rule_code": R_PRJ, "step": "PROJECT", "title": "Persistent organic carbon of the biochar used (CC)",
     "equation_reference": "VM0044 v1.2 Eqs. 2, 6; Tables 3, 4"},
    {"rule_code": R_PE, "step": "EMISSIONS", "title": "Production-stage and application-stage project emissions",
     "equation_reference": "VM0044 v1.2 Eqs. 3-5, 7-12"},
    {"rule_code": R_REM, "step": "REMOVALS", "title": "Removals at the production stage", "equation_reference": "VM0044 v1.2 Eq. 1"},
    {"rule_code": R_LK, "step": "LEAKAGE", "title": "Leakage (transport of feedstock and biochar)", "equation_reference": "VM0044 v1.2 Eq. 13"},
    {"rule_code": R_UNC, "step": "UNCERTAINTY", "title": "Uncertainty (none in VM0044: conservative defaults)",
     "equation_reference": "VM0044 v1.2 §8"},
    {"rule_code": R_ADJ, "step": "ADJUSTMENT", "title": "Buffer (none: permanence is the decay factor PR_de)",
     "equation_reference": "VM0044 v1.2 §8.4"},
    {"rule_code": R_NET, "step": "NET", "title": "Net reductions and removals; VCUs (whole tonnes, rounded down)",
     "equation_reference": "VM0044 v1.2 Eq. 15"},
)


def _rule(code: str, title: str, parameter: str, unit: str | None, ref: str, frequency: str, source: str = "FIELD_ACTIVITY") -> dict[str, Any]:
    return {"rule_code": code, "title": title, "parameter": parameter, "unit": unit, "measurement_source": source, "data_level": "PROJECT",
            "frequency": frequency, "source_reference": ref}


_BATCH = "Per batch / application (summed for the period)"
MONITORING_RULES: tuple[dict[str, Any], ...] = (
    _rule("V44_PRODUCED", "Biochar produced, dry mass (all uses, including unsold stock)", "biochar_produced_dry", "t",
          "VM0044 Eqs. 3/7 M_p,y", _BATCH),
    _rule("V44_USED_SOIL", "Biochar applied to soil, dry mass (H:C_org <= 0.7, within 1 year of production)", "biochar_soil_dry", "t",
          "VM0044 Eq. 2 M_t,k,p,y (k = soil)", _BATCH),
    _rule("V44_USED_NONSOIL", "Biochar used in non-soil applications, dry mass (concrete, asphalt, ...)", "biochar_nonsoil_dry", "t",
          "VM0044 Eq. 2 M_t,k,p,y (k = non-soil)", _BATCH),
    _rule("V44_FCP", "Organic carbon content of the biochar (laboratory, dry basis, as a fraction)", "organic_carbon_fraction", "fraction",
          "VM0044 Eqs. 2/6 F_Cp (lab analysis at least annually)", "At least annually and after a material change"),
    _rule("V44_HC_RATIO", "H:C_org molar ratio of the batch (laboratory)", "h_corg_ratio", "ratio", "VM0044 §4 condition 10 (<= 0.7 for soil)",
          "Each batch"),
    _rule("V44_TEMP", "Production (pyrolysis) temperature, period average", "production_temperature", "degC", "VM0044 Table 3 T_prod",
          "Continuous, averaged for the period"),
    _rule("V44_TECH", "Production technology: HIGH or LOW", "technology_class", None, "VM0044 §3 high / low technology; Options P.1 / P.2",
          "Validation"),
    _rule("V44_FEEDSTOCK", "Feedstock class: WOOD, HERBACEOUS, RICE, NUTSHELL, MANURE or BIOSOLIDS", "feedstock_class", None,
          "VM0044 Table 4 (mixed feedstock: the class with the lowest value)", "Validation and when it changes"),
    _rule("V44_PROCESS", "Conversion process: PYROLYSIS or GASIFICATION", "conversion_process", None, "VM0044 Table 4", "Validation"),
    _rule("V44_FE", "CH4 emitted per tonne of biochar (low technology; kiln-specific, Cornelissen et al. 2016)", "kiln_ch4_factor",
          "t CH4/t", "VM0044 Eq. 9 F_e (default 0.049)", "Validation"),
    _rule("V44_PE_PRETREAT", "Pre-treatment emissions (grid electricity TOOL05 + fossil fuel TOOL03; 0 if renewable)", "pretreatment_emissions",
          T, "VM0044 Eqs. 4/8 P_ED", "Per period"),
    _rule("V44_PE_AUX", "Auxiliary energy emissions of the reactor (TOOL05 + TOOL03; 0 if renewable)", "auxiliary_energy_emissions", T,
          "VM0044 Eqs. 5/10 P_EC", "Per period"),
    _rule("V44_PE_PROCESSING", "Biochar processing emissions before application (TOOL05 + TOOL03)", "processing_emissions", T,
          "VM0044 Eqs. 11/12 E_P", "Per period"),
    _rule("V44_LE_TRANSPORT", "Transport emissions of feedstock and biochar (TOOL12; only legs with a round trip of 200 km or more)",
          "transport_emissions", T, "VM0044 Eq. 13 LE_ts + LE_tap", "Per period"),
)

# Table 4 (IPCC 2019 Table 4AP.1): organic carbon fraction of biochar by feedstock, (pyrolysis, gasification)
FCP_DEFAULTS = {"MANURE": ("0.38", "0.09"), "WOOD": ("0.77", "0.52"), "HERBACEOUS": ("0.65", "0.28"), "RICE": ("0.49", "0.13"),
                "NUTSHELL": ("0.74", "0.40"), "BIOSOLIDS": ("0.35", "0.07")}
CONSTANTS = (
    Constant("C_TO_CO2", "3.666666666666666666666666666666667", "t CO2/t C", "44/12 (VM0044 v1.2 Eq. 1)"),
    Constant("GWP_CH4", "28", "t CO2e/t CH4", "VM0044 v1.2 §9.1 GWP_CH4; VCS Standard v5.0 Table 9 (IPCC AR5)"),
    Constant("FE_DEFAULT", "0.049", "t CH4/t", "VM0044 v1.2 Eq. 9 F_e default (traditional kilns)"),
    Constant("PR_HIGH", "0.89", "fraction", "VM0044 v1.2 Table 3 (> 600 degC)"),
    Constant("PR_MEDIUM", "0.80", "fraction", "VM0044 v1.2 Table 3 (450-600 degC)"),
    Constant("PR_LOW", "0.65", "fraction", "VM0044 v1.2 Table 3 (350-450 degC)"),
    Constant("PR_UNKNOWN", "0.56", "fraction", "VM0044 v1.2 §8.2.2 (temperature unknown; IPCC 2019 Fig. 4Ap.1(b))"),
    Constant("HC_MAX", "0.7", "ratio", "VM0044 v1.2 §4 condition 10 (soil use)"),
    *(Constant(f"FCP_{k}_{p}", v, "fraction", f"VM0044 v1.2 Table 4 ({k.lower()}, {p.lower()})")
      for k, (pyro, gas) in FCP_DEFAULTS.items() for p, v in (("PYROLYSIS", pyro), ("GASIFICATION", gas))),
)

ASSUMPTIONS = (
    "One project = one production facility; quantities are the period totals of the batch and application records.",
    "Table 3 boundaries: > 600 degC -> 0.89; > 450 to 600 -> 0.80; 350 to 450 (450 itself, where the table overlaps) -> 0.65; below 350 "
    "or not measured -> 0.56 (the table does not cover < 350 degC; the unknown-temperature value is the conservative choice).",
    "High technology requires laboratory F_Cp and a measured temperature; low technology uses laboratory F_Cp when recorded, otherwise "
    "Table 4 (mixed feedstock: record the class with the lowest value).",
    "Non-soil applications use the Table 3 soil value (VM0044 §8.2.1) unless a lower literature value is configured.",
    "Soil biochar with any batch H:C_org above 0.7 is refused (condition 10).",
    "Eq. 1: production emissions are subtracted once per facility (the t index of PE_PS is not repeated per biochar type).",
    "Eq. 9 uses the biochar used (M_used), as printed; production emissions are allocated by M_used / M_produced (Eqs. 3/7).",
    "Electricity, fossil fuel and freight are calculated with CDM TOOL05 / TOOL03 / TOOL12 outside the platform and recorded in t CO2e; "
    "transport legs with a round trip under 200 km are not recorded (zero).",
    "No uncertainty deduction and no buffer (VM0044 has neither); VCUs are whole tonnes rounded down; a negative balance gives no VCUs.",
)


def _var(code: str, rule: str, unit: str, required: bool = False, kind: str = "NUMBER") -> Variable:
    return Variable(code, "MONITORING_RECORD", unit, "PROJECT", rule_code=rule, required=required, kind=kind)


class Vm0044V12(CalculationModule):
    code = "VM0044-V1.2"
    version = "1.0.0"
    methodology_code = "VM0044"
    version_label = "1.2"
    calculation_rules_version = 0
    readiness = fw.NOT_PRODUCTION_READY
    label = "VM0044 v1.2 - biochar in soil and non-soil applications"
    rules: ClassVar[dict[str, str]] = {r["rule_code"]: r["step"] for r in CALC_RULES}
    calculation_rule_definitions = CALC_RULES
    monitoring_rule_definitions = MONITORING_RULES
    sampling_parameters: ClassVar[dict[str, Any]] = {}
    assumptions = ASSUMPTIONS
    variables = (
        _var("PRODUCED", "V44_PRODUCED", "t", required=True),
        _var("USED_SOIL", "V44_USED_SOIL", "t"),
        _var("USED_NONSOIL", "V44_USED_NONSOIL", "t"),
        _var("FCP", "V44_FCP", "fraction"),
        _var("HC_RATIO", "V44_HC_RATIO", "ratio"),
        _var("TEMP", "V44_TEMP", "degC"),
        _var("TECH", "V44_TECH", "", required=True, kind="TEXT"),
        _var("FEEDSTOCK", "V44_FEEDSTOCK", "", kind="TEXT"),
        _var("PROCESS", "V44_PROCESS", "", kind="TEXT"),
        _var("FE", "V44_FE", "t CH4/t"),
        _var("PE_PRETREAT", "V44_PE_PRETREAT", T),
        _var("PE_AUX", "V44_PE_AUX", T),
        _var("PE_PROCESSING", "V44_PE_PROCESSING", T),
        _var("LE_TRANSPORT", "V44_LE_TRANSPORT", T),
    )
    constants = CONSTANTS
    steps = tuple(Step(r["step"], fw.IMPLEMENTED, r["rule_code"]) for r in CALC_RULES)

    @staticmethod
    def _k(ctx: CalculationContext, code: str) -> Decimal:
        v = ctx.constant(code).value
        assert isinstance(v, Decimal)
        return v

    @staticmethod
    def _sum(ctx: CalculationContext, var: str) -> tuple[Decimal, tuple[int, ...]]:
        vals = ctx.values(var)
        return sum((Decimal(v.value) for v in vals), D0), tuple(v.seq for v in vals)

    @staticmethod
    def _mean(ctx: CalculationContext, var: str) -> tuple[Decimal | None, tuple[int, ...]]:
        vals = ctx.values(var)
        if not vals:
            return None, ()
        return sum((Decimal(v.value) for v in vals), D0) / Decimal(len(vals)), tuple(v.seq for v in vals)

    @staticmethod
    def _text(ctx: CalculationContext, var: str) -> tuple[str | None, tuple[int, ...]]:
        vals = ctx.values(var)
        if not vals:
            return None, ()
        texts = {str(v.value).strip().upper() for v in vals}
        if len(texts) > 1:
            raise CalculationBlocked("INCONSISTENT_INPUT", f"{var} has different values in the period: {', '.join(sorted(texts))}.",
                                     {"variable": var})
        return texts.pop(), tuple(v.seq for v in vals)

    def validate_inputs(self, ctx: CalculationContext) -> None:
        tech, _ = self._text(ctx, "TECH")
        if tech not in ("HIGH", "LOW"):
            raise CalculationBlocked("INVALID_INPUT", "V44_TECH must be HIGH or LOW.", {"variable": "TECH"})
        produced, _ = self._sum(ctx, "PRODUCED")
        used = self._sum(ctx, "USED_SOIL")[0] + self._sum(ctx, "USED_NONSOIL")[0]
        if produced <= 0:
            raise CalculationBlocked("MISSING_REQUIRED_INPUT", "No biochar produced in the period (V44_PRODUCED).", {"variable": "PRODUCED"})
        if used > produced:
            raise CalculationBlocked("INVALID_INPUT", f"Biochar used ({used} t) exceeds biochar produced ({produced} t).", {"variable": "PRODUCED"})
        if self._sum(ctx, "USED_SOIL")[0] > 0:
            too_high = [v for v in ctx.values("HC_RATIO") if Decimal(v.value) > self._k(ctx, "HC_MAX")]
            if too_high:
                raise CalculationBlocked("INELIGIBLE_BIOCHAR", "A batch has H:C_org above 0.7: it may not be credited for soil application "
                                         "(VM0044 §4 condition 10).", {"variable": "HC_RATIO"})
        if tech == "HIGH":
            if not ctx.values("FCP"):
                raise CalculationBlocked("MISSING_REQUIRED_INPUT", "High technology needs the laboratory organic carbon content (V44_FCP).",
                                         {"variable": "FCP"})
            if not ctx.values("TEMP"):
                raise CalculationBlocked("MISSING_REQUIRED_INPUT", "High technology needs the measured production temperature (V44_TEMP).",
                                         {"variable": "TEMP"})

    def _fcp(self, ctx: CalculationContext) -> tuple[Decimal, tuple[int, ...]]:
        lab, seqs = self._mean(ctx, "FCP")
        if lab is not None:
            return lab, seqs
        feed, fs = self._text(ctx, "FEEDSTOCK")
        proc, ps = self._text(ctx, "PROCESS")
        if feed not in FCP_DEFAULTS or proc not in ("PYROLYSIS", "GASIFICATION"):
            raise CalculationBlocked("MISSING_REQUIRED_INPUT", "Without a laboratory F_Cp, the feedstock class (V44_FEEDSTOCK) and process "
                                     "(V44_PROCESS) select the Table 4 default.", {"variable": "FEEDSTOCK"})
        c = ctx.constant(f"FCP_{feed}_{proc}")
        return Decimal(c.value), (*fs, *ps, c.seq)

    def _pr(self, ctx: CalculationContext) -> tuple[Decimal, tuple[int, ...]]:
        temp, seqs = self._mean(ctx, "TEMP")
        if temp is None or temp < 350:
            code = "PR_UNKNOWN"
        elif temp > 600:
            code = "PR_HIGH"
        elif temp > 450:
            code = "PR_MEDIUM"
        else:
            code = "PR_LOW"
        return self._k(ctx, code), (*seqs, ctx.constant(code).seq)

    def calculate_baseline(self, ctx: CalculationContext) -> list[Output]:
        return [Output("ER_SS", "BASELINE", R_BSL, D0, T, inputs=(ctx.constant("C_TO_CO2").seq,))]

    def calculate_project(self, ctx: CalculationContext) -> list[Output]:
        soil, s_seqs = self._sum(ctx, "USED_SOIL")
        nonsoil, n_seqs = self._sum(ctx, "USED_NONSOIL")
        fcp, f_seqs = self._fcp(ctx)
        pr, p_seqs = self._pr(ctx)
        return [Output("M_USED", "PROJECT", R_PRJ, soil + nonsoil, "t", inputs=(*s_seqs, *n_seqs) or (ctx.constant("C_TO_CO2").seq,)),
                Output("F_CP", "PROJECT", R_PRJ, fcp, "fraction", inputs=f_seqs),
                Output("PR_DE", "PROJECT", R_PRJ, pr, "fraction", inputs=p_seqs),
                Output("CC", "PROJECT", R_PRJ, (soil + nonsoil) * fcp * pr, "t C", outputs=("M_USED", "F_CP", "PR_DE"))]      # Eqs. 2/6

    def calculate_emissions(self, ctx: CalculationContext) -> list[Output]:
        tech, t_seqs = self._text(ctx, "TECH")
        produced, pr_seqs = self._sum(ctx, "PRODUCED")
        used = ctx.output("M_USED").value
        pre, pre_seqs = self._sum(ctx, "PE_PRETREAT")
        aux, aux_seqs = self._sum(ctx, "PE_AUX")
        if tech == "HIGH":
            p_ep, ep_in = D0, t_seqs
        else:
            fe, fe_seqs = self._mean(ctx, "FE")
            fe_seqs = fe_seqs or (ctx.constant("FE_DEFAULT").seq,)
            p_ep = (fe if fe is not None else self._k(ctx, "FE_DEFAULT")) * self._k(ctx, "GWP_CH4") * used                           # Eq. 9
            ep_in = (*t_seqs, *fe_seqs, ctx.constant("GWP_CH4").seq)
        pe_ps = (pre + p_ep + aux) * used / produced                                                                                # Eqs. 3/7
        processing, proc_seqs = self._sum(ctx, "PE_PROCESSING")
        return [Output("P_EP", "EMISSIONS", R_PE, p_ep, T, inputs=ep_in, outputs=("M_USED",)),
                Output("PE_PS", "EMISSIONS", R_PE, pe_ps, T, inputs=(*pr_seqs, *pre_seqs, *aux_seqs), outputs=("P_EP", "M_USED")),
                Output("PE_AS", "EMISSIONS", R_PE, processing, T, inputs=proc_seqs or (ctx.constant("C_TO_CO2").seq,))]        # Eqs. 11/12

    def calculate_removals(self, ctx: CalculationContext) -> list[Output]:
        cc = ctx.output("CC").value * self._k(ctx, "C_TO_CO2")
        return [Output("CC_CO2", "REMOVALS", R_REM, cc, T, inputs=(ctx.constant("C_TO_CO2").seq,), outputs=("CC",)),
                Output("ER_PS", "REMOVALS", R_REM, cc - ctx.output("PE_PS").value, T, outputs=("CC_CO2", "PE_PS"))]                # Eq. 1

    def calculate_leakage(self, ctx: CalculationContext) -> list[Output]:
        le, seqs = self._sum(ctx, "LE_TRANSPORT")
        return [Output("LE", "LEAKAGE", R_LK, le, T, inputs=seqs or (ctx.constant("C_TO_CO2").seq,))]                                 # Eq. 13

    def calculate_uncertainty(self, ctx: CalculationContext) -> list[Output]:
        return [Output("UNC", "UNCERTAINTY", R_UNC, D0, "fraction", outputs=("ER_PS",))]

    def apply_methodology_adjustments(self, ctx: CalculationContext) -> list[Output]:
        return [Output("BUFFER", "ADJUSTMENT", R_ADJ, D0, T, outputs=("ER_PS",))]

    def calculate_net_result(self, ctx: CalculationContext) -> list[Output]:
        o = ctx.output
        er = o("ER_SS").value + o("ER_PS").value - o("PE_AS").value - o("LE").value - o("BUFFER").value                              # Eq. 15
        with localcontext(fw.DECIMAL_CONTEXT):
            vcus = max(D0, er).to_integral_value(rounding=ROUND_FLOOR)
        return [Output("ER_NET", "NET", R_NET, er, T, outputs=("ER_SS", "ER_PS", "PE_AS", "LE", "BUFFER")),
                Output("VCU_TOTAL", "NET", R_NET, vcus, "VCU (t CO2e)", outputs=("ER_NET",), is_final=True)]
