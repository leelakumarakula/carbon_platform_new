"""Gold Standard for the Global Goals — Soil Organic Carbon Framework Methodology (GS 402) v1.0 with its activity modules.

Calculation specification: `methodology-docs/GS-SOC/GS402_calculation_spec.md` (equations transcribed in `extract_framework.md`
and `extract_modules.md`). One registered module per activity module and quantification approach; a methodology version
`GS402` / `1.0` chooses one of them on its Calculation tab:

- `GS402-ZT-A1`  — 402.4 Zero Tillage v1.0, Approach 1 (on-site SOC measurement, 50 cm, equivalent soil mass)
- `GS402-IT-A1`  — 402.1 Improved Tillage v1.0, Approach 1
- `GS402-IT-A3`  — 402.1 Improved Tillage v1.0, Approach 3 (IPCC stock change factors, FM Eqs. 4 and 6)
- `GS402-CC-A1`  — 402.6 Cover Crops v1.0, Approach 1 (+ cover crop seed production and transport, Eqs. 6/7)
- `GS402-CC-A3`  — 402.6 Cover Crops v1.0, Approach 3.1 (national / regional Tier 2 factors in FM Eqs. 4 and 6)

Chain (FM Eqs. 1-19): SOC_0 and SOC_t per stratum (Approach 1: the earlier and the current sampling campaign; Approach 3: Eqs. 4/6)
→ ΔSOC (Eqs. 3/5) → uncertainty deduction UD (Eqs. 7-11, 90 % confidence, 20 % threshold) → ΔC_SOC = ΔSOC × (1 − UD) (Eq. 2)
→ project emissions PE (FM Eqs. 12-18; 402.4 / 402.6 Eqs. 1-9) → leakage LK (FM Eq. 19; 402.4 Eq. 8; 402.6 Eq. 10)
→ ER = [ΔC_SOC × 44/12 − PE − LK] × (1 − BUF), BUF = 20 % for sequestration (GS GHG ER&S Product Requirements v3.2 §11.1.1).

Not included: Approach 2 (models / literature) and 402.6 Approach 3.2 (IPCC Tier 2 steady-state method); 402.2 organic soil
improvers. NOT_PRODUCTION_READY until the production-readiness approval is recorded.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_FLOOR, Decimal, localcontext
from itertools import product
from typing import Any, ClassVar

from app.calculation import framework as fw
from app.calculation.framework import CalculationBlocked, CalculationContext, CalculationModule, Constant, InputValue, Output, Step, Variable
from app.calculation.library import esm, stats

D0, D1 = Decimal(0), Decimal(1)
T = "t CO2e"
MIN_SAMPLES = 3                       # FM Table 6 starts at n = 3
TWO_SIDED_90 = 0.95                   # FM Eq. 8: 90 % confidence interval (two-sided) -> 0.95 quantile, df = n - 1
UNC_THRESHOLD = Decimal("0.20")       # FM Eq. 11

R_BSL, R_PRJ, R_PE, R_SOC, R_LK, R_UNC, R_ADJ, R_NET = ("GS-BSL", "GS-PRJ", "GS-PE", "GS-DSOC", "GS-LK", "GS-UNC", "GS-ADJ", "GS-NET")


def _calc_rules(soc_ref: str, pe_ref: str, lk_ref: str) -> tuple[dict[str, Any], ...]:
    return (
        {"rule_code": R_BSL, "step": "BASELINE", "title": "SOC stock at the start of the calculation period (SOC_0) per stratum",
         "equation_reference": f"GS 402 v1.0 Eqs. 2, 3{soc_ref}"},
        {"rule_code": R_PRJ, "step": "PROJECT", "title": "SOC stock at the end of the calculation period (SOC_t) per stratum",
         "equation_reference": f"GS 402 v1.0 Eq. 5{soc_ref}"},
        {"rule_code": R_PE, "step": "EMISSIONS", "title": "Project emissions: fertiliser N, fuel and electricity, agrochemicals",
         "equation_reference": pe_ref},
        {"rule_code": R_SOC, "step": "REMOVALS", "title": "SOC stock change in the calculation period (t C and t CO2e)",
         "equation_reference": "GS 402 v1.0 Eqs. 2, 3, 5 (x 44/12, Eq. 1)"},
        {"rule_code": R_LK, "step": "LEAKAGE", "title": "Leakage from a yield reduction (shift of production)", "equation_reference": lk_ref},
        {"rule_code": R_UNC, "step": "UNCERTAINTY", "title": "Uncertainty at 90 % confidence and uncertainty deduction",
         "equation_reference": "GS 402 v1.0 Eqs. 7-11, Table 6"},
        {"rule_code": R_ADJ, "step": "ADJUSTMENT", "title": "Uncertainty deduction applied; Gold Standard compliance buffer",
         "equation_reference": "GS 402 v1.0 Eqs. 1, 2; GS GHG ER&S Product Requirements v3.2 §11.1.1"},
        {"rule_code": R_NET, "step": "NET", "title": "Emission reductions for issuance (GS VERs, whole tonnes rounded down)",
         "equation_reference": "GS 402 v1.0 Eq. 1"},
    )


def _rule(code: str, title: str, parameter: str, unit: str | None, ref: str, level: str = "FARM", source: str = "FIELD_ACTIVITY",
          frequency: str = "Per year (5 baseline years before the project start and each project year)") -> dict[str, Any]:
    return {"rule_code": code, "title": title, "parameter": parameter, "unit": unit, "measurement_source": source, "data_level": level,
            "frequency": frequency, "source_reference": ref}


LAB_RULES = (
    {"rule_code": "GS_OC", "title": "Soil organic carbon content (per depth increment)", "parameter": "soil_organic_carbon", "unit": "g/kg",
     "measurement_source": "LABORATORY", "data_level": "SAMPLING_POINT", "frequency": "Project start and each performance certification",
     "method": "Dry combustion preferred (ICRAF protocol / VCS VMD0021)", "source_reference": "GS 402 v1.0 §5.1 Approach 1, Annex 1"},
    {"rule_code": "GS_SOIL_MASS", "title": "Dry fine-earth soil mass of the sample (per depth increment, > 2 mm excluded)",
     "parameter": "fine_soil_mass", "unit": "g", "measurement_source": "LABORATORY", "data_level": "SAMPLING_POINT",
     "frequency": "Project start and each performance certification", "source_reference": "402.4 / 402.6 §5.2.1(e) / §6.2: equivalent mass basis"},
)
PE_RULES = (
    _rule("GS_FERT_N", "Nitrogen fertiliser applied (synthetic and organic)", "fertilizer_n", "kg N", "GS 402 Eq. 13 FE; 402.4/402.6 Eq. 2"),
    _rule("GS_DIESEL", "Diesel used by machinery", "diesel", "L", "GS 402 Eq. 15 FUL; 402.4/402.6 Eq. 4"),
    _rule("GS_GASOLINE", "Gasoline used by machinery", "gasoline", "L", "GS 402 Eq. 15 FUL; 402.4/402.6 Eq. 4"),
    _rule("GS_ELECTRICITY", "Electricity used (grid or captive; on-site fossil generation is fuel)", "electricity", "kWh",
          "GS 402 Eq. 16 EUW; 402.4/402.6 Eq. 5"),
    _rule("GS_AGROCHEM", "Other agrochemical emissions (sum of quantity x supplier emission factor per product)", "agrochemical_emissions",
          T, "GS 402 Eqs. 17/18; 402.4/402.6 Eqs. 6/7 (AQ x AEF)"),
    _rule("GS_FEF_DIESEL", "Emission factor of diesel", "fef_diesel", "t CO2e/L",
          "GS 402 Eq. 15 FEF; national GHG inventory, otherwise IPCC 2006 Vol. 2 Ch. 3 Table 3.3.1", level="PROJECT",
          frequency="Project start; reviewed annually"),
    _rule("GS_FEF_GASOLINE", "Emission factor of gasoline", "fef_gasoline", "t CO2e/L",
          "GS 402 Eq. 15 FEF; national GHG inventory, otherwise IPCC 2006 Vol. 2 Ch. 3 Table 3.3.1", level="PROJECT",
          frequency="Project start; reviewed annually"),
    _rule("GS_EEF", "Emission factor of the electricity used", "eef_electricity", "t CO2e/kWh",
          "GS 402 Eq. 16 EEF; 402.4: grid - CDM TOOL05", level="PROJECT", frequency="Project start; reviewed annually"),
)
LK_RULES = (
    _rule("GS_YIELD", "Crop yield", "crop_yield", "kg/ha", "GS 402 Eq. 19 CY; 402.4 Eq. 8; 402.6 Eq. 10"),
    _rule("GS_LK_EF", "Leakage-area emissions per hectare displaced (dBC_LA + dSOC_LA + dFE_LA + dFU_LA)", "leakage_area_emissions",
          "t CO2e/ha", "GS 402 Eq. 19; 402.4 Eq. 8; 402.6 Eq. 10", level="PROJECT", frequency="At verification, when the yield fell"),
)
PAA_RULES = (
    _rule("GS_PAA", "Paris Agreement alignment status for 2026+ vintages: YES when approved by Gold Standard", "paa_status", None,
          "GS 119 PAA P&R v1.2 §3.1", level="PROJECT", frequency="When approved"),
)
PAA_DATE = date(2026, 1, 1)
SEED_RULES = (
    _rule("GS_CC_SEED", "Cover crop seed applied", "cover_crop_seed", "kg", "402.6 Eq. 7 S x A", frequency="Per year"),
    _rule("GS_CC_EF_SP", "Emission factor of cover crop seed production", "seed_production_ef", "t CO2e/kg", "402.6 Eq. 7 EF_SP",
          level="PROJECT", frequency="Project start; updated annually"),
    _rule("GS_CC_EF_ST", "Emission factor of seed transport", "seed_transport_ef", "t CO2e/(kg km)", "402.6 Eq. 7 EF_ST",
          level="PROJECT", frequency="Project start; reviewed annually"),
    _rule("GS_CC_DIST", "Seed transport distance (field-size weighted)", "seed_transport_distance", "km", "402.6 Eq. 7 DistST",
          level="PROJECT", frequency="Per year"),
)
FACTORS = ("SOC_REF", "F_LU", "F_MG_BL", "F_I_BL", "F_MG_PR", "F_I_PR")
A3_RULES = (
    _rule("GS_SOC_REF", "Reference SOC stock under natural vegetation (project-oriented, 0-30 cm)", "soc_ref", "t C/ha",
          "GS 402 Eqs. 4/6 SOC_REF", level="STRATUM", frequency="Project start"),
    _rule("GS_F_LU", "Land use factor", "f_lu", "factor", "GS 402 Eqs. 4/6 F_LU; Table 4", level="STRATUM", frequency="Project start"),
    _rule("GS_F_MG_BL", "Tillage (management) factor, baseline", "f_mg_bl", "factor", "GS 402 Eq. 4 F_MG,BL; Table 4", level="STRATUM",
          frequency="Project start"),
    _rule("GS_F_I_BL", "Input factor, baseline", "f_i_bl", "factor", "GS 402 Eq. 4 F_I,BL; Table 4", level="STRATUM", frequency="Project start"),
    _rule("GS_F_MG_PR", "Tillage (management) factor, project", "f_mg_pr", "factor", "GS 402 Eq. 6 F_MG,PR; Table 4", level="STRATUM",
          frequency="Annually"),
    _rule("GS_F_I_PR", "Input factor, project", "f_i_pr", "factor", "GS 402 Eq. 6 F_I,PR; Table 4", level="STRATUM", frequency="Annually"),
    _rule("GS_T_BL", "Years since the baseline practice was introduced (at most D = 20)", "t_bl", "yr", "GS 402 Eq. 4 T_BL", level="STRATUM",
          frequency="Project start"),
    _rule("GS_T_PR", "Years since the project start at the end of the calculation period", "t_pr", "yr", "GS 402 Eq. 6 T_PR",
          level="STRATUM", frequency="Each calculation period"),
    *(_rule(f"GS_U_{f}", f"Uncertainty of {f} (± % of the mean, two standard deviations, as in the IPCC tables)", f"u_{f.lower()}", "%",
            "GS 402 §9 Step 1; Tables 3/4 (± two standard deviations as % of mean)", level="STRATUM", frequency="Project start")
      for f in FACTORS),
)

CONSTANTS = (
    Constant("C_TO_CO2", "3.666666666666666666666666666666667", "t CO2/t C", "44/12 (GS 402 v1.0 Eq. 1)"),
    Constant("EF_FE", "0.01", "t CO2e/kg N", "GS 402 v1.0 Eq. 13 / 402.4 and 402.6 Eq. 2 EF_FE (IPCC 2019 Table 11.1 aggregated), as printed"),
    Constant("BUFFER", "0.20", "fraction", "GS GHG ER&S Product Requirements v3.2 §11.1.1 (20 % of sequestration GSVERs)"),
    Constant("UNC_THRESHOLD", "0.20", "fraction", "GS 402 v1.0 Eq. 11 (20 % of the mean at 90 % confidence)"),
    Constant("BASELINE_CAP", "0.5", "fraction", "GS 402 v1.0 §10: undocumented FE_BL / FU_BL / EU_BL / AE_BL at most 50 % of the project value"),
)
A3_CONSTANTS = (
    Constant("D_YEARS", "20", "yr", "GS 402 v1.0 Eqs. 4/6, footnotes 7 and 14 (IPCC default time dependency D = 20 years)"),
    Constant("T_UNKNOWN_N", "1.675", "t-value", "GS 402 v1.0 Eq. 8: n_p unknown -> 1.675"),
    Constant("T_DEFAULT", "3", "t-value", "402.4 / 402.6 §9.1.2: no SD / SE known -> SE = 50 % and t = 3"),
    Constant("SE_DEFAULT", "0.5", "fraction", "402.4 / 402.6 §9.1.2: SE = 50 % of the parameter value when unknown"),
)

COMMON_ASSUMPTIONS = (
    "Buffer: 20 % of the GS VERs from SOC sequestration go to the GS Compliance Buffer (GS GHG ER&S Product Requirements v3.2 "
    "§11.1.1); the whole net amount is sequestration for these activity modules, so (1 - BUF) applies to all of Eq. 1.",
    "GWPs: IPCC AR5 (Gold Standard rule update RU-2020-P&R v1.2, from 1 January 2021); EF_FE is used as printed (0.01 t CO2e per kg N), "
    "which is more conservative than 0.01 kg N2O-N/kg N x 44/28 x 265.",
    "Eq. 2: SOC_0 is the stock at the start of the calculation period (the baseline at the first period, the previous SOC_t later).",
    "Eqs. 10/11: UNC = |Upper - Lower| / (2 x dSOC) as a fraction; UD = UNC - 0.20 when UNC > 0.20 (capped at 1); no deduction otherwise. "
    "UNC is 1 when dSOC <= 0, and a SOC loss is used in full (the deduction never reduces a loss).",
    "Eq. 14: the electricity term is summed over the years like the fuel term (the printed bracket closes early).",
    "Eqs. 15/16/18: emissions are t CO2e per farm (litres, kWh and kg give t CO2e; the printed 'per ha' is not applied).",
    "Project emissions per farm and source: project records in the period minus the baseline annual mean (5 baseline years) x years in "
    "the period, floored at zero (decreases are never credited). Without baseline records the baseline is 50 % of the project value.",
    "Leakage: per stratum, max[(CY_BL - CY_t) / CY_BL; 0] x area x leakage-area emissions per ha. CY_min is taken as CY_BL (CY_min "
    "can never exceed CY_BL, so this is conservative); yields are the means of the farms' records (baseline years / this period).",
    "GS VERs are whole tonnes rounded down; a negative result is reported as REVERSAL with zero credits.",
    "GS 119 v1.2 §3.1: the share of a positive result falling in vintages from 1 January 2026 (by days of the period) is not credited "
    "unless GS_PAA = YES (Gold Standard approved the Paris-aligned transition); the buffer applies to the credited share.",
)
A1_ASSUMPTIONS = (
    "Approach 1: SOC_0 = mean stock of the stratum's samples in the earlier approved campaign (the project-start sampling at the first "
    "period), SOC_t = in this period's campaign; at least 3 samples per stratum and campaign (Table 6 starts at n = 3).",
    "Equivalent soil mass: cumulative fine-earth soil mass; reference mass per stratum = mean mass to the reference depth in the earlier "
    "campaign; linear interpolation with 2 depth increments, cubic spline with 3 or more (as for VM0042).",
    "Uncertainty (Eqs. 7-9): per stratum and campaign SE = SD / sqrt(n), t = two-sided 90 % Student-t with n - 1 degrees of freedom "
    "(equal to Table 6); Lower = sum of (SOC_t lower - SOC_0 upper) x A, Upper = sum of (SOC_t upper - SOC_0 lower) x A.",
)
A3_ASSUMPTIONS = (
    "Approach 3: dSOC in the period = SOC_REF x F_LU x (F_MG,PR x F_I,PR - F_MG,BL x F_I,BL) x (min(T_PR, D) - min(T_PR - years, D)) / D, "
    "i.e. Eq. 6 at the end minus Eq. 6 at the start of the period (D = 20).",
    "Uncertainty (Eqs. 7-9): for a factor with a ± % (two standard deviations, IPCC tables) SE = value x % / 200 and t = 1.675 (n unknown); "
    "without a ± %, SE = 50 % and t = 3 (402.4/402.6 §9.1.2). Lower / Upper = the smallest / largest dSOC over all combinations of "
    "the factors' bounds.",
)


def _record_var(code: str, rule: str, unit: str, level: str = "FARM", required: bool = False, kind: str = "NUMBER") -> Variable:
    return Variable(code, "MONITORING_RECORD", unit, level, rule_code=rule, required=required, kind=kind)


@dataclass
class _Stratum:
    record: str
    area: Decimal = D0
    area_seq: int | None = None
    farms: list[str] = field(default_factory=list)
    soc: dict[str, list[Decimal]] = field(default_factory=dict)        # Approach 1: CURRENT | PREVIOUS -> stocks (t C/ha)
    seqs: dict[str, list[int]] = field(default_factory=dict)
    ref_mass: Decimal = D0
    factors: dict[str, Decimal] = field(default_factory=dict)          # Approach 3
    factor_unc: dict[str, Decimal | None] = field(default_factory=dict)
    factor_seqs: list[int] = field(default_factory=list)


@dataclass
class _State:
    strata: dict[str, _Stratum] = field(default_factory=dict)
    years: Decimal = D1
    pe: dict[str, Decimal] = field(default_factory=dict)
    pe_seqs: list[int] = field(default_factory=list)


class _GsSoc402(CalculationModule):
    """Shared GS 402 chain; subclasses choose the activity module and the quantification approach."""
    version = "1.0.0"
    methodology_code = "GS402"
    version_label = "1.0"
    calculation_rules_version = 0           # bound to the selecting methodology version (registry.bind)
    readiness = fw.NOT_PRODUCTION_READY
    approach: ClassVar[str] = "A1"
    activity: ClassVar[str] = ""
    reference_depth_cm: ClassVar[Decimal] = Decimal(30)
    seed: ClassVar[bool] = False
    constants = CONSTANTS

    # ------------------------------------------------------------------ declarations built per subclass
    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not cls.activity:
            return
        a1 = cls.approach == "A1"
        soc_ref = "; Approach 1 on-site measurement (equivalent soil mass)" if a1 else "; Approach 3 Eqs. 4, 6"
        pe_ref = ("GS 402 v1.0 Eqs. 12-18" if cls.activity == "402.1"
                  else f"{cls.activity} v1.0 Eqs. 1-{9 if cls.seed else 7} (replace GS 402 Eqs. 12-18)")
        lk_ref = {"402.1": "GS 402 v1.0 Eq. 19", "402.4": "402.4 v1.0 Eq. 8", "402.6": "402.6 v1.0 Eq. 10"}[cls.activity]
        cls.calculation_rule_definitions = _calc_rules(soc_ref, pe_ref, lk_ref)
        cls.rules = {r["rule_code"]: r["step"] for r in cls.calculation_rule_definitions}
        cls.steps = tuple(Step(r["step"], fw.IMPLEMENTED, r["rule_code"]) for r in cls.calculation_rule_definitions)
        cls.monitoring_rule_definitions = (*(LAB_RULES if a1 else A3_RULES), *PE_RULES, *(SEED_RULES if cls.seed else ()), *LK_RULES, *PAA_RULES)
        cls.sampling_parameters = ({"quantification_approach": "MEASURE_AND_REMEASURE", "min_samples_per_stratum": MIN_SAMPLES,
                                    "core_details_required": True, "reference_depth_cm": int(cls.reference_depth_cm),
                                    "statistical_design": "STRATIFIED_RANDOM"} if a1 else {})
        cls.constants = (*CONSTANTS, *(() if a1 else A3_CONSTANTS))
        cls.assumptions = (*(A1_ASSUMPTIONS if a1 else A3_ASSUMPTIONS), *COMMON_ASSUMPTIONS)
        soc_vars: tuple[Variable, ...]
        if a1:
            soc_vars = (Variable("OC_T", "LAB_RESULT", "g/kg", "SAMPLING_POINT", rule_code="GS_OC"),
                        Variable("MASS_T", "LAB_RESULT", "g", "SAMPLING_POINT", rule_code="GS_SOIL_MASS"),
                        Variable("OC_T0", "LAB_RESULT", "g/kg", "SAMPLING_POINT", rule_code="GS_OC", period="PREVIOUS"),
                        Variable("MASS_T0", "LAB_RESULT", "g", "SAMPLING_POINT", rule_code="GS_SOIL_MASS", period="PREVIOUS"))
        else:
            soc_vars = (*(_record_var(f, f"GS_{f}", "t C/ha" if f == "SOC_REF" else "factor", "STRATUM", required=True) for f in FACTORS),
                        _record_var("T_BL", "GS_T_BL", "yr", "STRATUM", required=True),
                        _record_var("T_PR", "GS_T_PR", "yr", "STRATUM", required=True),
                        *(_record_var(f"U_{f}", f"GS_U_{f}", "%", "STRATUM") for f in FACTORS))
        cls.variables = (
            *soc_vars,
            Variable("AREA", "STRATUM_AREA", "ha", "STRATUM"),
            _record_var("FERT_N", "GS_FERT_N", "kg N"),
            _record_var("DIESEL", "GS_DIESEL", "L"),
            _record_var("GASOLINE", "GS_GASOLINE", "L"),
            _record_var("ELECTRICITY", "GS_ELECTRICITY", "kWh"),
            _record_var("AGROCHEM", "GS_AGROCHEM", T),
            _record_var("FEF_DIESEL", "GS_FEF_DIESEL", "t CO2e/L", "PROJECT"),
            _record_var("FEF_GASOLINE", "GS_FEF_GASOLINE", "t CO2e/L", "PROJECT"),
            _record_var("EEF", "GS_EEF", "t CO2e/kWh", "PROJECT"),
            *((_record_var("SEED", "GS_CC_SEED", "kg"),
               _record_var("EF_SP", "GS_CC_EF_SP", "t CO2e/kg", "PROJECT"),
               _record_var("EF_ST", "GS_CC_EF_ST", "t CO2e/(kg km)", "PROJECT"),
               _record_var("DIST", "GS_CC_DIST", "km", "PROJECT")) if cls.seed else ()),
            _record_var("YIELD", "GS_YIELD", "kg/ha"),
            _record_var("LK_EF", "GS_LK_EF", "t CO2e/ha", "PROJECT"),
            _record_var("PAA", "GS_PAA", "", "PROJECT", kind="TEXT"),
        )

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _state(ctx: CalculationContext) -> _State:
        st = getattr(ctx, "_gs402", None)
        if st is None:
            st = _State()
            ctx._gs402 = st  # type: ignore[attr-defined]
        return st

    @staticmethod
    def _k(ctx: CalculationContext, code: str) -> Decimal:
        v = ctx.constant(code).value
        assert isinstance(v, Decimal)
        return v

    @staticmethod
    def _project_value(ctx: CalculationContext, var: str) -> tuple[Decimal | None, tuple[int, ...]]:
        vals = ctx.values(var)
        if not vals:
            return None, ()
        return sum((Decimal(v.value) for v in vals), D0) / Decimal(len(vals)), tuple(v.seq for v in vals)

    # ------------------------------------------------------------------ validation
    def validate_inputs(self, ctx: CalculationContext) -> None:
        st = self._state(ctx)
        rp = ctx.snapshot["reporting_period"]
        st.years = Decimal((date.fromisoformat(rp["end"]) - date.fromisoformat(rp["start"])).days + 1) / Decimal(365)
        for a in ctx.values("AREA"):
            if a.context.get("stratum_role", "PROJECT") != "PROJECT":
                continue
            rec = a.context.get("stratum_record_id") or a.stratum_id or ""
            s = st.strata.setdefault(rec, _Stratum(rec))
            s.area, s.area_seq, s.farms = Decimal(a.value), a.seq, list(a.context.get("farm_ids") or [])
        if not st.strata:
            raise CalculationBlocked("MISSING_REQUIRED_INPUT", "No project stratum with an area.", {"variable": "AREA"})
        if self.approach == "A1":
            self._measured(ctx, st)
        else:
            self._factors(ctx, st)
        st.pe = self._project_emissions(ctx, st)

    def _measured(self, ctx: CalculationContext, st: _State) -> None:
        profiles: list[tuple[str, str, esm.Profile, int, list[int]]] = []     # (period, stratum record, profile, increments, seqs)
        for period, oc_var, mass_var in (("CURRENT", "OC_T", "MASS_T"), ("PREVIOUS", "OC_T0", "MASS_T0")):
            oc = {v.context.get("root_sample_id"): v for v in ctx.values(oc_var)}
            by_fc: dict[str, list[tuple[InputValue, InputValue]]] = defaultdict(list)
            for m in ctx.values(mass_var):
                o = oc.get(m.context.get("root_sample_id"))
                if o is None:
                    raise CalculationBlocked("MISSING_REQUIRED_INPUT", f"Sample {m.context.get('root_sample_id')} has a soil mass but no organic "
                                             "carbon result.", {"variable": oc_var})
                by_fc[m.context["field_collection_id"]].append((o, m))
            for fc, pairs in sorted(by_fc.items()):
                c = pairs[0][1].context
                if c.get("stratum_role", "PROJECT") != "PROJECT":
                    continue
                if c.get("probe_diameter_mm") is None or c.get("cores_count") is None:
                    raise CalculationBlocked("MISSING_REQUIRED_INPUT", f"Field collection {fc} has no probe diameter / number of cores.",
                                             {"reason": "CORE_DETAILS_MISSING"})
                layers = []
                for o, m in pairs:
                    if o.context.get("depth_top_cm") is None or o.context.get("depth_bottom_cm") is None:
                        raise CalculationBlocked("MISSING_REQUIRED_INPUT", "A sample has no depth increment.", {"reason": "DEPTH_MISSING"})
                    layers.append(esm.Layer(Decimal(o.context["depth_top_cm"]), Decimal(o.context["depth_bottom_cm"]),
                                            Decimal(m.value), Decimal(o.value)))
                if len(layers) < 2:
                    raise CalculationBlocked("DEPTH_INCREMENTS_REQUIRED", f"Field collection {fc} has {len(layers)} depth increment; the "
                                             "equivalent soil mass needs at least two.", {"reason": "ONE_INCREMENT"})
                if max(layer.depth_bottom_cm for layer in layers) < self.reference_depth_cm:
                    raise CalculationBlocked("SAMPLING_DEPTH_INSUFFICIENT", f"Field collection {fc} is sampled to less than "
                                             f"{self.reference_depth_cm} cm ({self.activity} reference depth).", {"reason": "TOO_SHALLOW"})
                try:
                    prof = esm.profile(layers, Decimal(c["probe_diameter_mm"]), int(c["cores_count"]))
                except esm.EsmError as e:
                    raise CalculationBlocked("INVALID_SOIL_PROFILE", f"Field collection {fc}: {e}", {"reason": "ESM"}) from None
                profiles.append((period, c.get("stratum_record_id") or "", prof, len(layers),
                                 sorted({x.seq for pair in pairs for x in pair})))
        if not profiles:
            raise CalculationBlocked("MISSING_REQUIRED_INPUT", "No soil profiles.", {"variable": "OC_T"})
        method = esm.method_for(min(p[3] for p in profiles))
        for rec, s in st.strata.items():
            earlier = [p for p in profiles if p[0] == "PREVIOUS" and p[1] == rec]
            for period in ("PREVIOUS", "CURRENT"):
                n = sum(1 for p in profiles if p[0] == period and p[1] == rec)
                if n < MIN_SAMPLES:
                    raise CalculationBlocked("INSUFFICIENT_SAMPLES", f"Stratum {rec}: {n} samples in the {period.lower()} campaign; GS 402 "
                                             f"Table 6 needs at least {MIN_SAMPLES}.", {"reason": "TOO_FEW_SAMPLES"})
            s.ref_mass = stats.mean([esm.mass_at_depth(p[2], self.reference_depth_cm, method) for p in earlier])
            for period, rec_p, prof, _, seqs in profiles:
                if rec_p == rec:
                    s.soc.setdefault(period, []).append(esm.oc_at_mass(prof, s.ref_mass, method))
                    s.seqs.setdefault(period, []).extend(seqs)

    def _factors(self, ctx: CalculationContext, st: _State) -> None:
        by_stratum: dict[str, dict[str, InputValue]] = defaultdict(dict)
        for var in (*FACTORS, "T_BL", "T_PR", *(f"U_{f}" for f in FACTORS)):
            for v in ctx.values(var):
                rec = v.context.get("stratum_record_id") or v.stratum_id or ""
                if var in by_stratum[rec]:
                    raise CalculationBlocked("DUPLICATE_INPUT", f"Stratum {rec} has more than one {var} record in the period.",
                                             {"variable": var})
                by_stratum[rec][var] = v
        for rec, s in st.strata.items():
            got = by_stratum.get(rec, {})
            missing = [v for v in (*FACTORS, "T_BL", "T_PR") if v not in got]
            if missing:
                raise CalculationBlocked("MISSING_REQUIRED_INPUT", f"Stratum {rec} has no {', '.join(missing)} record (Approach 3).",
                                         {"variable": missing[0], "stratum": rec})
            for f in FACTORS:
                s.factors[f] = Decimal(got[f].value)
                u = got.get(f"U_{f}")
                s.factor_unc[f] = Decimal(u.value) if u is not None else None
            s.factors["T_BL"], s.factors["T_PR"] = Decimal(got["T_BL"].value), Decimal(got["T_PR"].value)
            if any(v < 0 for v in s.factors.values()):
                raise CalculationBlocked("INVALID_INPUT", f"Stratum {rec}: factors and years must not be negative.", {"stratum": rec})
            s.factor_seqs = sorted(v.seq for v in got.values())

    # ------------------------------------------------------------------ project emissions
    def _project_emissions(self, ctx: CalculationContext, st: _State) -> dict[str, Decimal]:
        rp = ctx.snapshot["reporting_period"]
        p_start, p_end = date.fromisoformat(rp["start"]), date.fromisoformat(rp["end"])
        cap = self._k(ctx, "BASELINE_CAP")

        def increase(var: str) -> dict[str, Decimal]:
            """Per farm: Σ_a (PR_a − BL) = project total − baseline annual mean × years, floored at zero."""
            hist: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
            proj: dict[str, Decimal] = defaultdict(Decimal)
            for v in ctx.values(var):
                if not v.farm_id:
                    continue
                st.pe_seqs.append(v.seq)
                phase, observed = v.context.get("phase"), v.context.get("observed_on")
                if phase == "BASELINE":
                    hist[v.farm_id][observed[:4] if observed else "unknown"] += Decimal(v.value)
                elif observed is None or p_start <= date.fromisoformat(observed) <= p_end:
                    proj[v.farm_id] += Decimal(v.value)
            out = {}
            for farm in sorted({*hist, *proj}):
                pr = proj.get(farm, D0)
                if farm in hist:
                    bl_total = sum(hist[farm].values(), D0) / Decimal(len(hist[farm])) * st.years
                else:
                    bl_total = pr * cap                       # undocumented baseline: at most 50 % of the project value
                out[farm] = max(D0, pr - bl_total)
            return out

        def factor(var: str, needed: bool) -> Decimal:
            value, seqs = self._project_value(ctx, var)
            if value is None:
                if needed:
                    raise CalculationBlocked("MISSING_REQUIRED_INPUT", f"{var} is needed because the project uses more than the baseline.",
                                             {"variable": var})
                return D0
            st.pe_seqs.extend(seqs)
            return value

        fert = sum(increase("FERT_N").values(), D0)
        diesel, gasoline = sum(increase("DIESEL").values(), D0), sum(increase("GASOLINE").values(), D0)
        elec = sum(increase("ELECTRICITY").values(), D0)
        out = {
            "FERT": fert * self._k(ctx, "EF_FE"),                                                          # Eq. 13 / Eq. 2
            "FUEL": diesel * factor("FEF_DIESEL", diesel > 0) + gasoline * factor("FEF_GASOLINE", gasoline > 0),   # Eqs. 14/15
            "ELEC": elec * factor("EEF", elec > 0),                                                        # Eqs. 14/16
            "AGRO": sum(increase("AGROCHEM").values(), D0),                                                # Eqs. 17/18
        }
        if self.seed:                                                                                      # 402.6 Eqs. 6/7
            seed = D0
            for v in ctx.values("SEED"):
                observed = v.context.get("observed_on")
                if v.context.get("phase") != "BASELINE" and (observed is None or p_start <= date.fromisoformat(observed) <= p_end):
                    seed += Decimal(v.value)
                    st.pe_seqs.append(v.seq)
            ef_sp, ef_st, dist = factor("EF_SP", seed > 0), factor("EF_ST", seed > 0), factor("DIST", seed > 0)
            out["SEED"] = seed * (ef_sp + ef_st * dist)
        st.pe_seqs = sorted(set(st.pe_seqs)) or [ctx.constant("EF_FE").seq]
        return out

    # ------------------------------------------------------------------ Approach 3 model (Eq. 6 over the period)
    def _dsoc_a3(self, ctx: CalculationContext, s: _Stratum, f: dict[str, Decimal], years: Decimal) -> Decimal:
        d = self._k(ctx, "D_YEARS")
        t_end = min(s.factors["T_PR"], d)
        t_start = min(max(D0, s.factors["T_PR"] - years), d)
        return f["SOC_REF"] * f["F_LU"] * (f["F_MG_PR"] * f["F_I_PR"] - f["F_MG_BL"] * f["F_I_BL"]) * (t_end - t_start) / d

    def _soc_bl_a3(self, ctx: CalculationContext, s: _Stratum) -> Decimal:
        f, d = s.factors, self._k(ctx, "D_YEARS")
        return f["SOC_REF"] * (D1 + (f["F_LU"] * f["F_MG_BL"] * f["F_I_BL"] - D1) * min(f["T_BL"], d) / d)          # Eq. 4

    # ------------------------------------------------------------------ steps
    def calculate_baseline(self, ctx: CalculationContext) -> list[Output]:
        st, outs = self._state(ctx), []
        for rec, s in sorted(st.strata.items()):
            if self.approach == "A1":
                outs.append(Output(f"REF_MASS_{rec[:8]}", "BASELINE", R_BSL, s.ref_mass, "Mg/ha", "STRATUM", rec,
                                   inputs=tuple(sorted(set(s.seqs["PREVIOUS"])))))
                outs.append(Output(f"SOC_0_{rec[:8]}", "BASELINE", R_BSL, stats.mean(s.soc["PREVIOUS"]), "t C/ha", "STRATUM", rec,
                                   inputs=tuple(sorted(set(s.seqs["PREVIOUS"])))))
            else:
                soc_bl = self._soc_bl_a3(ctx, s)
                t_start = max(D0, s.factors["T_PR"] - st.years)
                outs.append(Output(f"SOC_BL_{rec[:8]}", "BASELINE", R_BSL, soc_bl, "t C/ha", "STRATUM", rec,
                                   inputs=(*s.factor_seqs, ctx.constant("D_YEARS").seq)))
                start = soc_bl + self._dsoc_a3(ctx, s, s.factors, t_start) if t_start > 0 else soc_bl
                outs.append(Output(f"SOC_0_{rec[:8]}", "BASELINE", R_BSL, start, "t C/ha", "STRATUM", rec, outputs=(f"SOC_BL_{rec[:8]}",)))
        return outs

    def calculate_project(self, ctx: CalculationContext) -> list[Output]:
        st, outs = self._state(ctx), []
        for rec, s in sorted(st.strata.items()):
            if self.approach == "A1":
                outs.append(Output(f"SOC_T_{rec[:8]}", "PROJECT", R_PRJ, stats.mean(s.soc["CURRENT"]), "t C/ha", "STRATUM", rec,
                                   inputs=tuple(sorted(set(s.seqs["CURRENT"])))))
            else:
                value = ctx.output(f"SOC_0_{rec[:8]}").value + self._dsoc_a3(ctx, s, s.factors, st.years)             # Eq. 6
                outs.append(Output(f"SOC_T_{rec[:8]}", "PROJECT", R_PRJ, value, "t C/ha", "STRATUM", rec,
                                   inputs=tuple(s.factor_seqs), outputs=(f"SOC_0_{rec[:8]}",)))
        return outs

    def calculate_emissions(self, ctx: CalculationContext) -> list[Output]:
        st = self._state(ctx)
        seqs = tuple(st.pe_seqs)
        outs = [Output(f"PE_{src}", "EMISSIONS", R_PE, value, T, inputs=seqs) for src, value in st.pe.items()]
        outs.append(Output("PE_TOTAL", "EMISSIONS", R_PE, sum(st.pe.values(), D0), T, outputs=tuple(o.code for o in outs)))   # Eq. 12
        return outs

    def calculate_removals(self, ctx: CalculationContext) -> list[Output]:
        st = self._state(ctx)
        total, used, areas = D0, [], []
        for rec, s in sorted(st.strata.items()):
            total += (ctx.output(f"SOC_T_{rec[:8]}").value - ctx.output(f"SOC_0_{rec[:8]}").value) * s.area                    # Eqs. 3/5
            used += [f"SOC_0_{rec[:8]}", f"SOC_T_{rec[:8]}"]
            if s.area_seq is not None:
                areas.append(s.area_seq)
        return [Output("DSOC_C", "REMOVALS", R_SOC, total, "t C", inputs=tuple(areas), outputs=tuple(used)),
                Output("DSOC_CO2", "REMOVALS", R_SOC, total * self._k(ctx, "C_TO_CO2"), T, inputs=(ctx.constant("C_TO_CO2").seq,),
                       outputs=("DSOC_C",))]

    def calculate_leakage(self, ctx: CalculationContext) -> list[Output]:
        st = self._state(ctx)
        rp = ctx.snapshot["reporting_period"]
        p_start, p_end = date.fromisoformat(rp["start"]), date.fromisoformat(rp["end"])
        base: dict[str, list[Decimal]] = defaultdict(list)
        current: dict[str, list[Decimal]] = defaultdict(list)
        seqs: list[int] = []
        for v in ctx.values("YIELD"):
            if not v.farm_id:
                continue
            observed = v.context.get("observed_on")
            if v.context.get("phase") == "BASELINE":
                base[v.farm_id].append(Decimal(v.value))
            elif observed is None or p_start <= date.fromisoformat(observed) <= p_end:
                current[v.farm_id].append(Decimal(v.value))
            seqs.append(v.seq)
        displaced = D0                                                       # ha-equivalents of lost production
        for _, s in sorted(st.strata.items()):
            b = [stats.mean(base[f]) for f in s.farms if base.get(f)]
            c = [stats.mean(current[f]) for f in s.farms if current.get(f)]
            if b and c and stats.mean(b) > 0:
                displaced += max(D0, (stats.mean(b) - stats.mean(c)) / stats.mean(b)) * s.area
        lk_ef, ef_seqs = self._project_value(ctx, "LK_EF")
        if displaced > 0 and lk_ef is None:
            raise CalculationBlocked("MISSING_REQUIRED_INPUT", "Crop yield fell below the baseline: the leakage-area emissions per hectare "
                                     "(GS_LK_EF) are needed.", {"variable": "LK_EF"})
        lk = displaced * (lk_ef or D0)
        lineage = tuple(sorted({*seqs, *ef_seqs})) or (ctx.constant("C_TO_CO2").seq,)
        return [Output("LK_DISPLACED_HA", "LEAKAGE", R_LK, displaced, "ha", inputs=lineage, outputs=("DSOC_CO2",)),
                Output("LK_TOTAL", "LEAKAGE", R_LK, lk, T, inputs=lineage, outputs=("LK_DISPLACED_HA",))]

    def calculate_uncertainty(self, ctx: CalculationContext) -> list[Output]:
        st = self._state(ctx)
        lower = upper = D0
        if self.approach == "A1":
            for _, s in sorted(st.strata.items()):
                bounds = {}
                for period in ("PREVIOUS", "CURRENT"):
                    v = s.soc[period]
                    se = stats.sample_variance(v).sqrt() / Decimal(len(v)).sqrt()                               # Eq. 7
                    t = stats.t_quantile(TWO_SIDED_90, Decimal(len(v) - 1))
                    m = stats.mean(v)
                    bounds[period] = (m - t * se, m + t * se)                                                    # Eq. 8
                lower += (bounds["CURRENT"][0] - bounds["PREVIOUS"][1]) * s.area                                 # Eq. 9
                upper += (bounds["CURRENT"][1] - bounds["PREVIOUS"][0]) * s.area
        else:
            t_known, t_default, se_default = self._k(ctx, "T_UNKNOWN_N"), self._k(ctx, "T_DEFAULT"), self._k(ctx, "SE_DEFAULT")
            for _, s in sorted(st.strata.items()):
                ranges = []
                for f in FACTORS:
                    x, u = s.factors[f], s.factor_unc[f]
                    half = x * u / Decimal(200) * t_known if u is not None else x * se_default * t_default
                    ranges.append((max(D0, x - half), x + half))                                                  # Eq. 8
                results = [self._dsoc_a3(ctx, s, dict(zip(FACTORS, combo, strict=True)), st.years) for combo in product(*ranges)]
                lower += min(results) * s.area                                                                    # Eq. 9
                upper += max(results) * s.area
        dsoc = ctx.output("DSOC_C").value
        unc = min(D1, abs(upper - lower) / (2 * dsoc)) if dsoc > 0 else D1                                         # Eq. 10
        ud = min(D1, max(D0, unc - self._k(ctx, "UNC_THRESHOLD")))                                                  # Eq. 11
        lin = ("DSOC_C",)
        return [Output("UNC_LOWER_C", "UNCERTAINTY", R_UNC, lower, "t C", outputs=lin),
                Output("UNC_UPPER_C", "UNCERTAINTY", R_UNC, upper, "t C", outputs=lin),
                Output("UNC", "UNCERTAINTY", R_UNC, unc, "fraction", outputs=("UNC_LOWER_C", "UNC_UPPER_C", "DSOC_C")),
                Output("UD", "UNCERTAINTY", R_UNC, ud, "fraction", inputs=(ctx.constant("UNC_THRESHOLD").seq,), outputs=("UNC",))]

    def apply_methodology_adjustments(self, ctx: CalculationContext) -> list[Output]:
        o = ctx.output
        dsoc = o("DSOC_C").value
        dc = dsoc * (D1 - o("UD").value) if dsoc > 0 else dsoc                     # Eq. 2; a loss is never reduced by the deduction
        gross = dc * self._k(ctx, "C_TO_CO2") - o("PE_TOTAL").value - o("LK_TOTAL").value                           # Eq. 1 bracket
        rp = ctx.snapshot["reporting_period"]
        start, end = date.fromisoformat(rp["start"]), date.fromisoformat(rp["end"])
        paa_vals = ctx.values("PAA")
        late = (end - max(start, PAA_DATE)).days + 1 if end >= PAA_DATE else 0
        blocked = D0 if any(str(v.value).strip().upper() == "YES" for v in paa_vals) else Decimal(late) / Decimal((end - start).days + 1)
        buffer = max(D0, gross) * (D1 - blocked) * self._k(ctx, "BUFFER")
        return [Output("DC_SOC_ADJ", "ADJUSTMENT", R_ADJ, dc, "t C", outputs=("DSOC_C", "UD")),
                Output("ER_GROSS", "ADJUSTMENT", R_ADJ, gross, T, inputs=(ctx.constant("C_TO_CO2").seq,),
                       outputs=("DC_SOC_ADJ", "PE_TOTAL", "LK_TOTAL")),
                Output("PAA_BLOCKED_SHARE", "ADJUSTMENT", R_ADJ, blocked, "fraction", inputs=tuple(v.seq for v in paa_vals),
                       outputs=("ER_GROSS",)),
                Output("BUFFER", "ADJUSTMENT", R_ADJ, buffer, T, inputs=(ctx.constant("BUFFER").seq,), outputs=("ER_GROSS", "PAA_BLOCKED_SHARE"))]

    def calculate_net_result(self, ctx: CalculationContext) -> list[Output]:
        o = ctx.output
        gross = o("ER_GROSS").value
        er = gross * (D1 - o("PAA_BLOCKED_SHARE").value) - o("BUFFER").value if gross > 0 else gross                  # Eq. 1, GS 119
        reversal = -er if er < 0 else D0
        with localcontext(fw.DECIMAL_CONTEXT):
            vers = max(D0, er).to_integral_value(rounding=ROUND_FLOOR)
        return [Output("ER_NET", "NET", R_NET, er, T, outputs=("ER_GROSS", "PAA_BLOCKED_SHARE", "BUFFER")),
                Output("REVERSAL", "NET", R_NET, reversal, T, outputs=("ER_NET",)),
                Output("GS_VER_TOTAL", "NET", R_NET, vers, "GS VER (t CO2e)", outputs=("ER_NET",), is_final=True)]


class Gs402ZeroTillageA1(_GsSoc402):
    code = "GS402-ZT-A1"
    activity = "402.4"
    reference_depth_cm = Decimal(50)                 # 402.4 §5.2.1(c)
    label = "GS 402 + 402.4 Zero Tillage - Approach 1 (SOC measured to 50 cm, equivalent soil mass)"


class Gs402ImprovedTillageA1(_GsSoc402):
    code = "GS402-IT-A1"
    activity = "402.1"
    label = "GS 402 + 402.1 Improved Tillage - Approach 1 (SOC measured, equivalent soil mass to 30 cm)"


class Gs402ImprovedTillageA3(_GsSoc402):
    code = "GS402-IT-A3"
    activity = "402.1"
    approach = "A3"
    label = "GS 402 + 402.1 Improved Tillage - Approach 3 (IPCC stock change factors, Eqs. 4 and 6)"


class Gs402CoverCropsA1(_GsSoc402):
    code = "GS402-CC-A1"
    activity = "402.6"
    seed = True
    label = "GS 402 + 402.6 Cover Crops - Approach 1 (SOC measured, equivalent soil mass to 30 cm) + seed emissions"


class Gs402CoverCropsA3(_GsSoc402):
    code = "GS402-CC-A3"
    activity = "402.6"
    approach = "A3"
    seed = True
    label = "GS 402 + 402.6 Cover Crops - Approach 3.1 (national / regional Tier 2 factors, Eqs. 4 and 6) + seed emissions"


MODULES: tuple[CalculationModule, ...] = (Gs402ZeroTillageA1(), Gs402ImprovedTillageA1(), Gs402ImprovedTillageA3(), Gs402CoverCropsA1(),
                                          Gs402CoverCropsA3())
