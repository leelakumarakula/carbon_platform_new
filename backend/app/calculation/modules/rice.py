"""Rice methane: Verra VM0051 Improved Management in Rice Production Systems v1.1 (QA3, IPCC 2019 emission-factor approach) and
India CCTS BM AG04.002 v1.0 (IPCC default-value approach) on one emission-factor engine.

Calculation specification: `methodology-docs/VM0051-Rice/Rice_calculation_spec.md` (equations in `extract_rice.md`). Per farm (field)
and season of the reporting period:

- EF = EFc × SFw × SFp × SFo, SFo = (1 + Σ ROA × CFOA)^0.59 (VM0051 Eqs. 6-7; AG04.002 / IPCC 2019 Eqs. 5.2-5.3), Tables 5.11-5.14;
- CH4 = EF × L × area × 10^-3 × GWP (VM0051 Eq. 8 per season; GWP applied once);
- baseline from the farm's BASELINE look-back records (conservative drainage rule, 5 t/ha straw);
- N2O for drying periods (VM0051 Eq. 25 / AG04.002 PE_n: (0.005 − 0.003) × 44/28 × N) and for a change in N rate (VM0051 Eq. 19);
- VM0051: fuel, burning, straw end use and leakage; uncertainty 15 % on ΔCH4 and ΔN2O (Eq. 29). AG04.002: 15 % on the whole
  reduction, decreases in N2O not credited.

Not included: QA1 (models) and QA2 (chamber measurement) — mandatory under VM0051 for methanotrophs, biochar, low-emission cultivars
and AWD shallower than 10 cm. NOT_PRODUCTION_READY until the production-readiness approval is recorded.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_FLOOR, Decimal, localcontext
from typing import Any, ClassVar

from app.calculation import framework as fw
from app.calculation.framework import CalculationBlocked, CalculationContext, CalculationModule, Constant, InputValue, Output, Step, Variable

D0, D1 = Decimal(0), Decimal(1)
T = "t CO2e"
EXP = Decimal("0.59")
WATER = {"CONTINUOUS": "SFW_CONTINUOUS", "SINGLE": "SFW_SINGLE", "MULTIPLE": "SFW_MULTIPLE"}
WATER_RANK = {"CONTINUOUS": 0, "SINGLE": 1, "MULTIPLE": 2}                 # higher = lower emissions
PRESEASON = {"SHORT": "SFP_SHORT", "LONG": "SFP_LONG", "FLOODED": "SFP_FLOODED", "VERY_LONG": "SFP_VERY_LONG"}
REGIONS = {"WORLD": "1.19", "AFRICA": "1.19", "EAST_ASIA": "1.32", "SOUTHEAST_ASIA": "1.22", "SOUTH_ASIA": "0.85", "EUROPE": "1.56",
           "NORTH_AMERICA": "0.65", "SOUTH_AMERICA": "1.27"}
AMENDMENTS = ("COMPOST", "FYM", "GREEN")                                    # besides straw
R_BSL, R_PRJ, R_PE, R_REM, R_LK, R_UNC, R_ADJ, R_NET = ("RI-BSL", "RI-PRJ", "RI-PE", "RI-REM", "RI-LK", "RI-UNC", "RI-ADJ", "RI-NET")

_IPCC = "IPCC 2019 Refinement Vol. 4 Ch. 5"
FACTOR_CONSTANTS = (
    *(Constant(f"EFC_{r}", v, "kg CH4/ha/day", f"{_IPCC} Table 5.11 ({r.lower().replace('_', ' ')})") for r, v in REGIONS.items()),
    Constant("SFW_CONTINUOUS", "1", "factor", f"{_IPCC} Table 5.12 (continuously flooded)"),
    Constant("SFW_SINGLE", "0.71", "factor", f"{_IPCC} Table 5.12 (single drainage period)"),
    Constant("SFW_MULTIPLE", "0.55", "factor", f"{_IPCC} Table 5.12 (multiple drainage periods incl. AWD)"),
    Constant("SFP_SHORT", "1.00", "factor", f"{_IPCC} Table 5.13 (non-flooded pre-season < 180 days)"),
    Constant("SFP_LONG", "0.89", "factor", f"{_IPCC} Table 5.13 (non-flooded pre-season > 180 days)"),
    Constant("SFP_FLOODED", "2.41", "factor", f"{_IPCC} Table 5.13 (flooded pre-season > 30 days)"),
    Constant("SFP_VERY_LONG", "0.59", "factor", f"{_IPCC} Table 5.13 (non-flooded pre-season > 365 days)"),
    Constant("CFOA_STRAW_SHORT", "1.00", "factor", f"{_IPCC} Table 5.14 (straw incorporated < 30 days before cultivation)"),
    Constant("CFOA_STRAW_LONG", "0.19", "factor", f"{_IPCC} Table 5.14 (straw incorporated > 30 days before cultivation)"),
    Constant("CFOA_COMPOST", "0.17", "factor", f"{_IPCC} Table 5.14 (compost)"),
    Constant("CFOA_FYM", "0.21", "factor", f"{_IPCC} Table 5.14 (farmyard manure)"),
    Constant("CFOA_GREEN", "0.45", "factor", f"{_IPCC} Table 5.14 (green manure)"),
    Constant("STRAW_BASELINE", "5", "t/ha", "VM0051 v1.1 fn 16 / AG04.002: 5 t/ha straw assumed in the baseline"),
    Constant("EF_N_FLOODED", "0.003", "t N2O-N/t N", "IPCC 2019 Table 11.1 EF1FR (continuous flooding)"),
    Constant("EF_N_DRAINED", "0.005", "t N2O-N/t N", "IPCC 2019 Table 11.1 EF1FR (single and multiple drainage)"),
    Constant("N2ON_TO_N2O", "1.571428571428571428571428571428571", "t N2O/t N2O-N", "44/28"),
    Constant("UNC_TIER1", "0.15", "fraction", "VM0051 v1.1 §8.5 / AG04.002: 15 % uncertainty deduction for IPCC default values"),
)


def _rule(code: str, title: str, parameter: str, unit: str | None, ref: str, level: str = "FARM",
          frequency: str = "Each season (record all values of a season with the same observed-on date)") -> dict[str, Any]:
    return {"rule_code": code, "title": title, "parameter": parameter, "unit": unit, "measurement_source": "FIELD_ACTIVITY",
            "data_level": level, "frequency": frequency, "source_reference": ref}


SEASON_RULES: tuple[dict[str, Any], ...] = (
    _rule("RI_AREA", "Rice area of the field in the season", "rice_area", "ha", "VM0051 A_i / AG04.002 A_g,s"),
    _rule("RI_DAYS", "Cultivation period (land preparation to the later of harvest or post-season drainage)", "cultivation_days", "days",
          "VM0051 Eq. 8 L_t; IPCC 2019 Eq. 5.1"),
    _rule("RI_WATER", "On-season water regime: CONTINUOUS, SINGLE or MULTIPLE (drainage periods; AWD = MULTIPLE)", "water_regime", None,
          "IPCC 2019 Table 5.12 SFw"),
    _rule("RI_PRESEASON", "Pre-season water status: SHORT (< 180 days dry), LONG (> 180), VERY_LONG (> 365) or FLOODED (> 30 days)",
          "preseason_status", None, "IPCC 2019 Table 5.13 SFp"),
    _rule("RI_STRAW", "Rice straw incorporated (dry matter)", "straw_incorporated", "t/ha", "IPCC 2019 Eq. 5.3 ROA (straw)"),
    _rule("RI_STRAW_TIMING", "Straw incorporated SHORT (< 30 days) or LONG (> 30 days) before cultivation", "straw_timing", None,
          "IPCC 2019 Table 5.14 CFOA"),
    _rule("RI_COMPOST", "Compost applied (fresh weight)", "compost", "t/ha", "IPCC 2019 Eq. 5.3 ROA"),
    _rule("RI_FYM", "Farmyard manure applied (fresh weight)", "farmyard_manure", "t/ha", "IPCC 2019 Eq. 5.3 ROA"),
    _rule("RI_GREEN", "Green manure applied (fresh weight)", "green_manure", "t/ha", "IPCC 2019 Eq. 5.3 ROA"),
    _rule("RI_N", "Nitrogen applied (synthetic + organic + residue)", "n_rate", "kg N/ha", "VM0051 Eqs. 19, 25 Q_N"),
)
PROJECT_RULES: tuple[dict[str, Any], ...] = (
    _rule("RI_REGION", "IPCC region of the baseline emission factor (WORLD, SOUTH_ASIA, SOUTHEAST_ASIA, EAST_ASIA, EUROPE, ...)", "ipcc_region",
          None, "IPCC 2019 Table 5.11", "PROJECT", "Validation"),
    _rule("RI_EFC", "Country-specific / measured baseline emission factor (continuously flooded, no amendments; replaces the region value)",
          "efc", "kg CH4/ha/day", "VM0051 §8.2.3 EF_bsl,c hierarchy; AG04.002 paras 27-28 (reference fields)", "PROJECT", "Validation"),
    _rule("RI_UNC", "Uncertainty deduction of a country-specific emission factor (%)", "efc_uncertainty", "%", "VM0051 §8.6", "PROJECT",
          "Validation"),
)
VM0051_EXTRA = (
    _rule("RI_DIESEL", "Diesel used on the field", "diesel", "L", "VM0051 Eqs. 1-2 FFC"),
    _rule("RI_BURN", "Rice residue burned (dry matter)", "residue_burned", "kg d.m.", "VM0051 Eqs. 17, 23 MB"),
    _rule("RI_PE_AB", "Emissions of straw diverted to other end uses (Eq. 24)", "straw_end_use_emissions", T, "VM0051 Eq. 24", "PROJECT",
          "Each verification"),
    _rule("RI_LE", "Leakage: imported organic amendments (Eq. 26) and diverted bioenergy residues (TOOL16)", "leakage", T,
          "VM0051 Eq. 26, §8.4", "PROJECT", "Each verification"),
)
AG04_EXTRA = (
    _rule("RI_PE_FUEL", "Land preparation fuel emissions (BM-T-002; year 1, when above 5 % of reductions)", "land_prep_fuel_emissions", T,
          "AG04.002 PE_l", "PROJECT", "Year 1"),
)


@dataclass
class _Season:
    farm: str
    key: str
    values: dict[str, InputValue] = field(default_factory=dict)


@dataclass
class _State:
    seasons: list[_Season] = field(default_factory=list)
    baseline: dict[str, dict[str, list[InputValue]]] = field(default_factory=dict)       # farm -> variable -> look-back records
    efc: Decimal = D0
    efc_seqs: tuple[int, ...] = ()
    region_default: bool = True
    results: dict[str, Decimal] = field(default_factory=dict)
    seqs: list[int] = field(default_factory=list)


class _Rice(CalculationModule):
    version = "1.0.0"
    calculation_rules_version = 0
    readiness = fw.NOT_PRODUCTION_READY
    sampling_parameters: ClassVar[dict[str, Any]] = {}
    gwp: ClassVar[tuple[str, str]] = ("28", "265")
    gwp_ref: ClassVar[str] = ""
    vcs: ClassVar[bool] = True                     # True: VM0051 profile; False: AG04.002 profile
    ref: ClassVar[str] = ""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not getattr(cls, "code", ""):
            return
        r = cls.ref
        cls.calculation_rule_definitions = (
            {"rule_code": R_BSL, "step": "BASELINE", "title": "Baseline CH4 (and N2O) per field and season",
             "equation_reference": f"{r}; IPCC 2019 Eqs. 5.1-5.3"},
            {"rule_code": R_PRJ, "step": "PROJECT", "title": "Project CH4 (and N2O) per field and season", "equation_reference": f"{r}"},
            {"rule_code": R_PE, "step": "EMISSIONS", "title": "Other emission sources and the N2O of drying periods",
             "equation_reference": "VM0051 v1.1 Eqs. 1-2, 17, 23-25" if cls.vcs else "AG04.002 PE_n, PE_l"},
            {"rule_code": R_REM, "step": "REMOVALS", "title": "Removals (none: SOC is not credited)", "equation_reference": r},
            {"rule_code": R_LK, "step": "LEAKAGE", "title": "Leakage", "equation_reference": "VM0051 v1.1 §8.4" if cls.vcs else "AG04.002 (none)"},
            {"rule_code": R_UNC, "step": "UNCERTAINTY", "title": "Uncertainty deduction (15 % for IPCC default values)",
             "equation_reference": "VM0051 v1.1 §8.5, §8.6" if cls.vcs else "AG04.002 Table 6"},
            {"rule_code": R_ADJ, "step": "ADJUSTMENT", "title": "Uncertainty applied",
             "equation_reference": "VM0051 v1.1 Eq. 29" if cls.vcs else "AG04.002"},
            {"rule_code": R_NET, "step": "NET", "title": "Net emission reductions; credits (whole tonnes, rounded down)",
             "equation_reference": "VM0051 v1.1 Eqs. 29-34" if cls.vcs else "AG04.002 ER_y"},
        )
        cls.rules = {x["rule_code"]: x["step"] for x in cls.calculation_rule_definitions}
        cls.steps = tuple(Step(x["step"], fw.IMPLEMENTED, x["rule_code"]) for x in cls.calculation_rule_definitions)
        cls.monitoring_rule_definitions = (*SEASON_RULES, *PROJECT_RULES, *(VM0051_EXTRA if cls.vcs else AG04_EXTRA))
        cls.constants = (*FACTOR_CONSTANTS,
                         Constant("GWP_CH4", cls.gwp[0], "t CO2e/t CH4", cls.gwp_ref), Constant("GWP_N2O", cls.gwp[1], "t CO2e/t N2O", cls.gwp_ref),
                         *((Constant("EF_DIESEL", "0.002886", "t CO2e/L", "VM0051 v1.1 parameter EF_CO2 (diesel)"),
                            Constant("EF_BB_CH4", "2.7", "g CH4/kg d.m.", "IPCC 2019 Vol. 4 Ch. 2 Table 2.5"),
                            Constant("EF_BB_N2O", "0.07", "g N2O/kg d.m.", "IPCC 2019 Vol. 4 Ch. 2 Table 2.5"),
                            Constant("CF_RICE", "0.80", "fraction", "IPCC 2019 Vol. 4 Ch. 2 Table 2.6"),
                            Constant("TIER1_CAP", "60000", T, "VM0051 v1.1 §8.2: Tier 1 factors only up to 60 000 t CO2e per year"))
                           if cls.vcs else ()))
        season_vars = [Variable(d["rule_code"][3:], "MONITORING_RECORD", d["unit"] or "", "FARM", rule_code=d["rule_code"],
                                required=d["rule_code"] in ("RI_AREA", "RI_DAYS", "RI_WATER"), kind="NUMBER" if d["unit"] else "TEXT")
                       for d in SEASON_RULES]
        extra = VM0051_EXTRA if cls.vcs else AG04_EXTRA
        cls.variables = (*season_vars,
                         *(Variable(d["rule_code"][3:], "MONITORING_RECORD", d["unit"] or "", "PROJECT", rule_code=d["rule_code"], required=False,
                                    kind="NUMBER" if d["unit"] else "TEXT") for d in PROJECT_RULES),
                         *(Variable(d["rule_code"][3:], "MONITORING_RECORD", d["unit"] or "", d["data_level"], rule_code=d["rule_code"],
                                    required=False) for d in extra))

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _k(ctx: CalculationContext, code: str) -> Decimal:
        v = ctx.constant(code).value
        assert isinstance(v, Decimal)
        return v

    @staticmethod
    def _state(ctx: CalculationContext) -> _State:
        st = getattr(ctx, "_rice", None)
        if st is None:
            st = _State()
            ctx._rice = st  # type: ignore[attr-defined]
        return st

    def _seasonal_vars(self) -> list[str]:
        return [d["rule_code"][3:] for d in SEASON_RULES] + (["DIESEL", "BURN"] if self.vcs else [])

    def validate_inputs(self, ctx: CalculationContext) -> None:
        st = self._state(ctx)
        rp = ctx.snapshot["reporting_period"]
        start, end = date.fromisoformat(rp["start"]), date.fromisoformat(rp["end"])
        seasons: dict[tuple[str, str], _Season] = {}
        for var in self._seasonal_vars():
            for v in ctx.values(var):
                if not v.farm_id:
                    continue
                observed = v.context.get("observed_on") or ""
                if v.context.get("phase") == "BASELINE":
                    st.baseline.setdefault(v.farm_id, defaultdict(list))[var].append(v)
                elif observed and start <= date.fromisoformat(observed) <= end:
                    s = seasons.setdefault((v.farm_id, observed), _Season(v.farm_id, observed))
                    if var in s.values:
                        raise CalculationBlocked("DUPLICATE_INPUT", f"Farm {v.farm_id} has two {var} records for the season {observed}.",
                                                 {"variable": var})
                    s.values[var] = v
        st.seasons = [s for _, s in sorted(seasons.items()) if "AREA" in s.values]
        if not st.seasons:
            raise CalculationBlocked("MISSING_REQUIRED_INPUT", "No rice season (RI_AREA) in the reporting period.", {"variable": "AREA"})
        for s in st.seasons:
            for need in ("DAYS", "WATER"):
                if need not in s.values:
                    raise CalculationBlocked("MISSING_REQUIRED_INPUT", f"Season {s.key} of farm {s.farm} has no RI_{need}.", {"variable": need})
            allowed_values: dict[str, tuple[str, ...]] = {"WATER": tuple(WATER), "PRESEASON": tuple(PRESEASON), "STRAW_TIMING": ("SHORT", "LONG")}
            for var, allowed in allowed_values.items():
                rec = s.values.get(var)
                if rec is not None and str(rec.value).strip().upper() not in allowed:
                    raise CalculationBlocked("INVALID_INPUT", f"RI_{var} '{rec.value}' is not one of {', '.join(allowed)}.", {"variable": var})
            if s.farm not in st.baseline or "WATER" not in st.baseline[s.farm]:
                raise CalculationBlocked("MISSING_REQUIRED_INPUT", f"Farm {s.farm} has no BASELINE look-back water regime (RI_WATER, phase "
                                         "BASELINE).", {"variable": "WATER", "reason": "BASELINE_LOOKBACK"})
        efc = ctx.values("EFC")
        if efc:
            st.efc, st.efc_seqs, st.region_default = Decimal(efc[0].value), (efc[0].seq,), False
        else:
            region = ctx.values("REGION")
            code = f"EFC_{str(region[0].value).strip().upper()}" if region else "EFC_WORLD"
            if region and str(region[0].value).strip().upper() not in REGIONS:
                raise CalculationBlocked("INVALID_INPUT", f"RI_REGION '{region[0].value}' is not an IPCC Table 5.11 region.", {"variable": "REGION"})
            st.efc, st.efc_seqs = self._k(ctx, code), (*(r.seq for r in region), ctx.constant(code).seq)

    # ------------------------------------------------------------------ engine
    def _text(self, v: InputValue | None, default: str) -> str:
        return str(v.value).strip().upper() if v is not None else default

    def _num(self, v: InputValue | None) -> Decimal:
        return Decimal(v.value) if v is not None else D0

    def _sfo(self, ctx: CalculationContext, straw: Decimal, timing: str, others: dict[str, Decimal]) -> Decimal:
        total = straw * self._k(ctx, f"CFOA_STRAW_{timing}") + sum((others[a] * self._k(ctx, f"CFOA_{a}") for a in AMENDMENTS), D0)
        with localcontext(fw.DECIMAL_CONTEXT):
            return ((D1 + total).ln() * EXP).exp()                                                     # Eq. 7

    def _baseline_text(self, recs: list[InputValue], default: str, rank: dict[str, int] | None = None) -> str:
        vals = [str(r.value).strip().upper() for r in recs]
        if not vals:
            return default
        if rank:                                     # conservative: the lowest-emission regime seen in the look-back (VM0051 p. 14)
            return max(vals, key=lambda x: rank.get(x, 0))
        return max(set(vals), key=vals.count)

    @staticmethod
    def _mean(recs: list[InputValue]) -> Decimal | None:
        return sum((Decimal(r.value) for r in recs), D0) / Decimal(len(recs)) if recs else None

    def _compute(self, ctx: CalculationContext) -> None:
        st, k = self._state(ctx), self._k
        if st.results:
            return
        gwp_ch4, gwp_n2o, n2o = k(ctx, "GWP_CH4"), k(ctx, "GWP_N2O"), k(ctx, "N2ON_TO_N2O")
        res: dict[str, Decimal] = defaultdict(Decimal)
        for s in st.seasons:
            v, b = s.values, st.baseline[s.farm]
            area, days = self._num(v.get("AREA")), self._num(v.get("DAYS"))
            st.seqs += [x.seq for x in v.values()] + [x.seq for recs in b.values() for x in recs]
            # project
            sfo_p = self._sfo(ctx, self._num(v.get("STRAW")), self._text(v.get("STRAW_TIMING"), "LONG"),
                              {a: self._num(v.get(a)) for a in AMENDMENTS})
            sfw_p = k(ctx, WATER[self._text(v.get("WATER"), "CONTINUOUS")])
            ef_p = st.efc * sfw_p * k(ctx, PRESEASON[self._text(v.get("PRESEASON"), "SHORT")]) * sfo_p
            # baseline (look-back): conservative water regime, 5 t/ha straw, mean other amendments, same or shorter cultivation period
            b_water = self._baseline_text(b.get("WATER", []), "CONTINUOUS", WATER_RANK)
            b_pre = self._baseline_text(b.get("PRESEASON", []), self._text(v.get("PRESEASON"), "SHORT"))
            b_timing = self._baseline_text(b.get("STRAW_TIMING", []), "LONG")
            b_others = {a: self._mean(b.get(a, [])) or D0 for a in AMENDMENTS}
            sfo_b = self._sfo(ctx, k(ctx, "STRAW_BASELINE"), b_timing, b_others)
            b_days = min(days, self._mean(b.get("DAYS", [])) or days)
            ef_b = st.efc * k(ctx, WATER[b_water]) * k(ctx, PRESEASON[b_pre]) * sfo_b
            res["CH4_BSL"] += ef_b * b_days * area / 1000 * gwp_ch4                                     # Eq. 8
            res["CH4_WP"] += ef_p * days * area / 1000 * gwp_ch4
            # N2O: change in N rate at the flooded factor (Eq. 19) + drying-period increment (Eq. 25 / AG04 PE_n)
            n_p = self._num(v.get("N"))
            n_b = self._mean(b.get("N", []))
            n_b = n_p if n_b is None else n_b
            res["N2O_SOIL"] += (n_b - n_p) * area / 1000 * k(ctx, "EF_N_FLOODED") * n2o * gwp_n2o
            if b_water == "CONTINUOUS" and self._text(v.get("WATER"), "CONTINUOUS") != "CONTINUOUS":     # field starts draining
                res["PE_DRYING"] += n_p * area / 1000 * (k(ctx, "EF_N_DRAINED") - k(ctx, "EF_N_FLOODED")) * n2o * gwp_n2o
            if self.vcs:
                b_diesel = self._mean(b.get("DIESEL", [])) or D0
                res["FUEL"] += (b_diesel - self._num(v.get("DIESEL"))) * k(ctx, "EF_DIESEL")                      # Eqs. 1-2, 30
                burn_b, burn_p = self._mean(b.get("BURN", [])) or D0, self._num(v.get("BURN"))
                f = k(ctx, "CF_RICE") / Decimal(10) ** 6
                res["BB"] += (burn_b - burn_p) * f * (k(ctx, "EF_BB_CH4") * gwp_ch4 + k(ctx, "EF_BB_N2O") * gwp_n2o)    # Eqs. 17, 23
        if not self.vcs:
            res["N2O_SOIL"] = min(D0, res["N2O_SOIL"])                    # AG04.002: decreases in N2O are not credited
        st.results = dict(res)
        st.seqs = sorted(set(st.seqs))

    def _total(self, ctx: CalculationContext, var: str) -> tuple[Decimal, tuple[int, ...]]:
        vals = ctx.values(var)
        return sum((Decimal(v.value) for v in vals), D0), tuple(v.seq for v in vals)

    # ------------------------------------------------------------------ steps
    def calculate_baseline(self, ctx: CalculationContext) -> list[Output]:
        self._compute(ctx)
        st = self._state(ctx)
        return [Output("EFC", "BASELINE", R_BSL, st.efc, "kg CH4/ha/day", inputs=st.efc_seqs),
                Output("CH4_BSL", "BASELINE", R_BSL, st.results["CH4_BSL"], T, inputs=tuple(st.seqs), outputs=("EFC",))]

    def calculate_project(self, ctx: CalculationContext) -> list[Output]:
        st = self._state(ctx)
        return [Output("CH4_WP", "PROJECT", R_PRJ, st.results["CH4_WP"], T, inputs=tuple(st.seqs), outputs=("EFC",))]

    def calculate_emissions(self, ctx: CalculationContext) -> list[Output]:
        st, r = self._state(ctx), self._state(ctx).results
        lin = tuple(st.seqs)
        outs = [Output("D_CH4_SOIL", "EMISSIONS", R_PE, r["CH4_BSL"] - r["CH4_WP"], T, outputs=("CH4_BSL", "CH4_WP")),       # Eq. 31
                Output("D_N2O_SOIL", "EMISSIONS", R_PE, r.get("N2O_SOIL", D0), T, inputs=lin),                                   # Eq. 33
                Output("PE_DRYING", "EMISSIONS", R_PE, r.get("PE_DRYING", D0), T, inputs=lin)]                                   # Eq. 25
        if self.vcs:
            ab, ab_seqs = self._total(ctx, "PE_AB")
            outs += [Output("D_FUEL", "EMISSIONS", R_PE, r.get("FUEL", D0), T, inputs=lin),
                     Output("D_BURN", "EMISSIONS", R_PE, r.get("BB", D0), T, inputs=lin),
                     Output("PE_AB", "EMISSIONS", R_PE, ab, T, inputs=ab_seqs or lin)]
        else:
            fuel, f_seqs = self._total(ctx, "PE_FUEL")
            outs.append(Output("PE_FUEL", "EMISSIONS", R_PE, fuel, T, inputs=f_seqs or lin))
        return outs

    def calculate_removals(self, ctx: CalculationContext) -> list[Output]:
        return [Output("REMOVALS", "REMOVALS", R_REM, D0, T, outputs=("CH4_WP",))]

    def calculate_leakage(self, ctx: CalculationContext) -> list[Output]:
        le, seqs = self._total(ctx, "LE") if self.vcs else (D0, ())
        return [Output("LE", "LEAKAGE", R_LK, le, T, inputs=seqs or tuple(self._state(ctx).seqs))]

    def calculate_uncertainty(self, ctx: CalculationContext) -> list[Output]:
        st = self._state(ctx)
        unc_rec = ctx.values("UNC")
        if not st.region_default and unc_rec:
            unc, seqs = Decimal(unc_rec[0].value) / 100, (unc_rec[0].seq,)
        else:
            unc, seqs = self._k(ctx, "UNC_TIER1"), (ctx.constant("UNC_TIER1").seq,)
        return [Output("UNC", "UNCERTAINTY", R_UNC, min(D1, max(D0, unc)), "fraction", inputs=seqs, outputs=("D_CH4_SOIL",))]

    def apply_methodology_adjustments(self, ctx: CalculationContext) -> list[Output]:
        o = ctx.output
        u = o("UNC").value
        if self.vcs:                                                     # Eq. 29: (1 - UNC) on ΔCH4_soil and ΔN2O_soil only
            return [Output("D_CH4_SOIL_ADJ", "ADJUSTMENT", R_ADJ, o("D_CH4_SOIL").value * (D1 - u), T, outputs=("D_CH4_SOIL", "UNC")),
                    Output("D_N2O_SOIL_ADJ", "ADJUSTMENT", R_ADJ, o("D_N2O_SOIL").value * (D1 - u), T, outputs=("D_N2O_SOIL", "UNC"))]
        return [Output("D_CH4_SOIL_ADJ", "ADJUSTMENT", R_ADJ, o("D_CH4_SOIL").value, T, outputs=("D_CH4_SOIL",)),
                Output("D_N2O_SOIL_ADJ", "ADJUSTMENT", R_ADJ, o("D_N2O_SOIL").value, T, outputs=("D_N2O_SOIL",))]

    def calculate_net_result(self, ctx: CalculationContext) -> list[Output]:
        o, st = ctx.output, self._state(ctx)
        if self.vcs:
            er = (o("D_FUEL").value + o("D_BURN").value + o("D_CH4_SOIL_ADJ").value + o("D_N2O_SOIL_ADJ").value
                  - o("LE").value - o("PE_AB").value - o("PE_DRYING").value)                                                    # Eq. 29
            lin: tuple[str, ...] = ("D_FUEL", "D_BURN", "D_CH4_SOIL_ADJ", "D_N2O_SOIL_ADJ", "LE", "PE_AB", "PE_DRYING")
            if st.region_default and er > self._k(ctx, "TIER1_CAP") * max(D1, Decimal(len({s.key[:4] for s in st.seasons}))):
                raise CalculationBlocked("TIER1_CAP_EXCEEDED", "Reductions exceed 60 000 t CO2e per year: VM0051 requires a country-specific "
                                         "emission factor (RI_EFC) instead of the IPCC Tier 1 regional value.", {"variable": "EFC"})
        else:
            gross = o("D_CH4_SOIL_ADJ").value + o("D_N2O_SOIL_ADJ").value - o("PE_DRYING").value - o("PE_FUEL").value
            er = gross * (D1 - o("UNC").value)                                                                                 # 15 % once
            lin = ("D_CH4_SOIL_ADJ", "D_N2O_SOIL_ADJ", "PE_DRYING", "PE_FUEL", "UNC")
        with localcontext(fw.DECIMAL_CONTEXT):
            credits = max(D0, er).to_integral_value(rounding=ROUND_FLOOR)
        return [Output("ER_NET", "NET", R_NET, er, T, outputs=lin),
                Output("CREDITS", "NET", R_NET, credits, "credits (t CO2e)", outputs=("ER_NET",), is_final=True)]


class Vm0051V11(_Rice):
    code = "VM0051-V1.1-QA3"
    methodology_code = "VM0051"
    version_label = "1.1"
    ref = "VM0051 v1.1 Eqs. 6-8"
    gwp_ref = "VM0051 v1.1 §9.1 -> VCS Standard v5.0 Table 9 (IPCC AR5)"
    label = "VM0051 v1.1 - improved rice management, IPCC emission factors (QA3)"
    assumptions = (
        "QA3 only (IPCC 2019 Tables 5.11-5.14 or a country-specific EF); QA2 is mandatory for methanotrophs, biochar, low-emission "
        "cultivars and AWD shallower than 10 cm and is not included.",
        "Eq. 5 / Eq. 8: GWP is applied once (BE_CH4 from Eq. 8 is used as the areal mean); Eq. 8 is summed over the seasons of the period.",
        "Season = the farm's records with the same observed-on date in the reporting period; baseline = the farm's BASELINE look-back records.",
        "Baseline water regime: the lowest-emission regime recorded in the look-back (single drainage in any year -> single drainage, p. 14); "
        "baseline straw 5 t/ha with the look-back incorporation timing (LONG = 0.19 when not recorded); baseline cultivation period = "
        "the look-back mean, at most the project season's length.",
        "Pre-season factors from IPCC Table 5.13 including FLOODED 2.41 and VERY_LONG 0.59 (Eq. 6 refers to the full table).",
        "N2O: change in N rate at EF1FR continuous flooding 0.003 (Eq. 19) plus, on fields that start draining, Eq. 25 with "
        "CF_N2O = (0.005 - 0.003) x 44/28 = 0.00314 kg N2O/kg N (the drying increment is deducted after the uncertainty, Eq. 29).",
        "Uncertainty 15 % on dCH4 and dN2O for IPCC default factors (<= 60 000 t CO2e/yr, otherwise blocked); a country-specific EF uses "
        "its recorded uncertainty (RI_UNC).",
        "dCO2_lime and LE_yield are not calculated (no defining equation); liming and yield-related leakage must be shown de minimis.",
        "GWPs IPCC AR5 (CH4 28, N2O 265); VCUs are whole tonnes rounded down.",
    )


class CctsAg04002(_Rice):
    code = "CCTS-AG04.002"
    methodology_code = "BM-AG04.002"
    version_label = "1.0"
    vcs = False
    gwp = ("29.8", "273")
    ref = "AG04.002 v1.0 paras 26-35"
    gwp_ref = "AG04.002 v1.0 (IPCC AR6)"
    label = "CCTS BM AG04.002 v1.0 - improved rice management, IPCC default-value approach"
    assumptions = (
        "IPCC default-value approach (paras 26-35); EFc measured on reference fields (RI_EFC) or the IPCC Table 5.11 region value.",
        "Season = the farm's records with the same observed-on date; baseline = continuation of current practice from the farm's "
        "BASELINE records (same conservative rules as VM0051 where AG04.002 is silent).",
        "Pre-season factor and straw CFOA from the recorded pre-season status and incorporation timing (equivalent to the regional "
        "double / single cropping defaults 1.0 / 0.89 and 1.0 / 0.19).",
        "PE_n corrected: N x (0.005 - 0.003) x 44/28 x GWP, positive (the printed sign and the missing 44/28 are errors).",
        "Decreases in N2O are not credited; land-preparation fuel (BM-T-002) is recorded in t CO2e.",
        "The 15 % deduction is applied once to the whole reduction (Eq. 7 applies it twice; Table 6 does not).",
        "GWPs IPCC AR6 (CH4 29.8, N2O 273); credits are whole tonnes rounded down.",
    )
