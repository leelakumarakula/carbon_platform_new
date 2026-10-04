"""Verra VM0047 Afforestation, Reforestation and Revegetation v1.1 (14 May 2025) — census-based approach.

Calculation specification: `methodology-docs/VM0047-ARR/VM0047_v1.1_calculation_spec.md` (equations transcribed in
`extract_census_leakage.md`). Scope: planting units on land whose pre-project use continues (≤ 50 units/ha, direct planting):

- woody carbon stock (Eqs. 22-25): complete census N per stratum, mortality M_t and aboveground woody biomass from a sample of
  planting units (one sampling point per sampled unit; biomass from the documented allometric equation), R and CF = 0.47;
- project emissions (Eq. 12): biomass burning CH4/N2O (Eqs. 26/27, COMF = 1.0) and N fertiliser N2O (Eqs. 15-21);
- uncertainty (Eqs. 29-31) and the 100 % half-width eligibility rule (§8.5.2); removals (Eq. 33) and annualised removals (Eq. 34);
- leakage is zero for the census-based approach (§8.4); baseline is zero (§8.1.2);
- buffer = AFOLU non-permanence risk rating x the stock change only (VCS Standard v5.0 §3.14.15; minimum rating 12, NPRT §2.5.2).

Not included: the area-based approach (it needs the remote-sensing dynamic performance benchmark, §8.2) and VMD0054 leakage.
NOT_PRODUCTION_READY until the production-readiness approval is recorded.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_FLOOR, Decimal, localcontext
from typing import Any, ClassVar

from app.calculation import framework as fw
from app.calculation.framework import CalculationBlocked, CalculationContext, CalculationModule, Constant, Output, Step, Variable
from app.calculation.library import stats

D0, D1 = Decimal(0), Decimal(1)
T = "t CO2e"
MAX_DENSITY = Decimal(50)                 # §4.3(3): planting units per hectare
TWO_SIDED_90 = 0.95                       # T: two-tailed Student-t, alpha = 0.1, df = n - 1

R_BSL, R_PRJ, R_PE, R_REM, R_LK, R_UNC, R_ADJ, R_NET = ("V47-BSL", "V47-PRJ", "V47-PE", "V47-REM", "V47-LK", "V47-UNC", "V47-ADJ", "V47-NET")

CALC_RULES: tuple[dict[str, Any], ...] = (
    {"rule_code": R_BSL, "step": "BASELINE", "title": "Baseline (zero: no planting units without the project)",
     "equation_reference": "VM0047 v1.1 §6.2, §8.1.2"},
    {"rule_code": R_PRJ, "step": "PROJECT", "title": "Woody carbon stock of the planting units (census x survival x mean carbon)",
     "equation_reference": "VM0047 v1.1 Eqs. 22-25"},
    {"rule_code": R_PE, "step": "EMISSIONS", "title": "Project emissions: biomass burning and N fertiliser",
     "equation_reference": "VM0047 v1.1 Eqs. 12, 15-21, 26, 27"},
    {"rule_code": R_REM, "step": "REMOVALS", "title": "Carbon stock change through year t and t - x (t CO2e)",
     "equation_reference": "VM0047 v1.1 Eqs. 22, 23"},
    {"rule_code": R_LK, "step": "LEAKAGE", "title": "Leakage (zero for the census-based approach)", "equation_reference": "VM0047 v1.1 §8.4"},
    {"rule_code": R_UNC, "step": "UNCERTAINTY", "title": "Sampling uncertainty of biomass and mortality (deduction above 10 %)",
     "equation_reference": "VM0047 v1.1 Eqs. 29-31, §8.5.2"},
    {"rule_code": R_ADJ, "step": "ADJUSTMENT", "title": "Removals in the interval; AFOLU non-permanence buffer",
     "equation_reference": "VM0047 v1.1 Eqs. 33, 34; VCS Standard v5.0 §3.14.15; AFOLU NPRT §2.5"},
    {"rule_code": R_NET, "step": "NET", "title": "VCUs (whole tonnes, rounded down)", "equation_reference": "VCS Standard v5.0 §3.14.15"},
)


def _rule(code: str, title: str, parameter: str, unit: str, ref: str, level: str, frequency: str, source: str = "FIELD") -> dict[str, Any]:
    return {"rule_code": code, "title": title, "parameter": parameter, "unit": unit, "measurement_source": source, "data_level": level,
            "frequency": frequency, "source_reference": ref}


_EVENT = "Each monitoring event (at most every 5 years)"
MONITORING_RULES: tuple[dict[str, Any], ...] = (
    _rule("V47_N", "Planting units in the complete census (initial population N)", "census_population", "units", "VM0047 v1.1 Eq. 24 N; "
          "§4.3(4)", "STRATUM", "Census at t = 0 (repeat the value each period)", "FIELD_ACTIVITY"),
    _rule("V47_ALIVE", "Sampled planting unit alive (1) or dead / not relocated (0)", "unit_alive", "flag", "VM0047 v1.1 Eqs. 24/31 M_t; "
          "§4.3(7)", "SAMPLING_POINT", _EVENT),
    _rule("V47_AGB", "Aboveground woody biomass of the sampled unit (published allometric equation; 0 below the size threshold)",
          "aboveground_woody_biomass", "kg d.m.", "VM0047 v1.1 Eq. 25 B_WP-woody-AB,pu,t; §9.2", "SAMPLING_POINT", _EVENT),
    _rule("V47_BURNED", "Sampled planting unit visibly burned in the interval (1) or not (0)", "unit_burned", "flag",
          "VM0047 v1.1 Eq. 27 n_burn,t", "SAMPLING_POINT", _EVENT),
    _rule("V47_FSN", "Synthetic fertiliser N applied to planting units (mass x N content)", "synthetic_fertilizer_n", "kg N",
          "VM0047 v1.1 Eqs. 16/17 F_wp,SN,t", "FARM", "Per application, summed for the interval", "FIELD_ACTIVITY"),
    _rule("V47_FON", "Organic fertiliser N applied to planting units (mass x N content)", "organic_fertilizer_n", "kg N",
          "VM0047 v1.1 Eqs. 16/18 F_wp,ON,t", "FARM", "Per application, summed for the interval", "FIELD_ACTIVITY"),
    _rule("V47_ROOT_SHOOT", "Root-to-shoot ratio R (species / genus / family, same ecoregion; IPCC 2019 Table 4.4)", "root_shoot_ratio",
          "ratio", "VM0047 v1.1 Eq. 25 R; §9.1", "PROJECT", "Validation", "FIELD_ACTIVITY"),
    _rule("V47_NPR", "AFOLU non-permanence risk rating", "non_permanence_risk_rating", "%", "VCS Standard v5.0 §3.14.15; AFOLU NPRT v5.0",
          "PROJECT", "Each verification", "FIELD_ACTIVITY"),
)

CONSTANTS = (
    Constant("C_TO_CO2", "3.666666666666666666666666666666667", "t CO2/t C", "44/12 (VM0047 v1.1 Eq. 22)"),
    Constant("N2ON_TO_N2O", "1.571428571428571428571428571428571", "t N2O/t N2O-N", "44/28 (VM0047 v1.1 Eqs. 16, 20, 21)"),
    Constant("CF", "0.47", "t C/t d.m.", "VM0047 v1.1 §9.1 CF (2006 IPCC Guidelines)"),
    Constant("GWP_CH4", "28", "t CO2e/t CH4", "VCS Standard v5.0 §3.14.4 Table 9 (IPCC AR5)"),
    Constant("GWP_N2O", "265", "t CO2e/t N2O", "VCS Standard v5.0 §3.14.4 Table 9 (IPCC AR5)"),
    Constant("COMF", "1.0", "fraction", "VM0047 v1.1 §9.1 COMF (census-based: 1.0)"),
    Constant("EF_BB_CH4", "6.8", "kg CH4/t d.m.", "IPCC 2006 Vol. 4 Ch. 2 Table 2.5 (tropical forest, highest forest CH4 factor)"),
    Constant("EF_BB_N2O", "0.26", "kg N2O/t d.m.", "IPCC 2006 Vol. 4 Ch. 2 Table 2.5 (extra-tropical forest, highest forest N2O factor)"),
    Constant("EF_NDIRECT", "0.01", "t N2O-N/t N", "VM0047 v1.1 §9.1 (IPCC 2019 Table 11.1)"),
    Constant("FRAC_GASF", "0.11", "fraction", "VM0047 v1.1 §9.1 (IPCC 2019 Table 11.3)"),
    Constant("FRAC_GASM", "0.21", "fraction", "VM0047 v1.1 §9.1 (IPCC 2019 Table 11.3)"),
    Constant("EF_NVOLAT", "0.01", "t N2O-N/t N volatilised", "VM0047 v1.1 §9.1 (IPCC 2019 Table 11.3)"),
    Constant("FRAC_LEACH", "0.24", "fraction", "VM0047 v1.1 §9.1 (IPCC 2019 Table 11.3)"),
    Constant("EF_NLEACH", "0.011", "t N2O-N/t N leached", "VM0047 v1.1 §9.1 (IPCC 2019 Table 11.3)"),
    Constant("UNC_ALLOWANCE", "0.10", "fraction", "VM0047 v1.1 Eq. 29 (- 0.10)"),
    Constant("NPR_MIN", "12", "%", "AFOLU Non-Permanence Risk Tool v5.0 §2.5.2 (minimum overall rating)"),
)

ASSUMPTIONS = (
    "Sampled planting units are sampling points (one per unit); M_t = dead / sampled; Eq. 25 averages the live sampled units only "
    "(dead units enter through 1 - M_t, so mortality is not counted twice).",
    "Biomass per sampled unit is entered in kg d.m. from the documented allometric equation (species > genus > family, same "
    "ecoregion); live units below the fixed size threshold are entered as 0.",
    "Eq. 29 read dimensionally: per stratum, relative half-width = sqrt((T x SE / mean carbon per unit)^2 + U_M^2) with U_M from Eq. 31 "
    "as a fraction; strata are combined by adding half-widths in quadrature; UNC = min(1, max(0, relative half-width - 0.10)). T is "
    "the two-tailed 90 % Student-t with n - 1 degrees of freedom.",
    "§8.5.2: no removals are credited when the 90 % half-width exceeds 100 % of the stock (CR_t = 0).",
    "Eq. 33: dC(t - x) and UNC(t - x) come from the previous approved period; when it has no biomass sample (the census at t = 0), "
    "dC(t - x) = 0.",
    "Eq. 27: biomass subject to burning uses the previous period's mean biomass of the stratum (the current mean when there is none).",
    "Burning factors: the highest IPCC 2006 Table 2.5 forest factors (CH4 6.8, N2O 0.26 kg/t d.m.); VM0047 §9.1 cites a "
    "stationary-combustion table by mistake.",
    "Fertiliser: Frac_LEACH always applied (conservative); fertiliser N is recorded as mass x N content (Eqs. 17/18).",
    "Leakage is zero (§8.4). Buffer = max(rating, 12) % x the uncertainty-adjusted stock change of the interval (stock change only, "
    "never negative); VCUs = removals - buffer, whole tonnes rounded down; a negative result is a REVERSAL.",
    "GWPs: IPCC AR5 (VCS Standard v5.0 §3.14.4).",
)


@dataclass
class _Campaign:
    n_sampled: int = 0
    dead: int = 0
    burned: int = 0
    agb_live: list[Decimal] = field(default_factory=list)      # kg d.m. per live sampled unit
    seqs: list[int] = field(default_factory=list)


@dataclass
class _Stratum:
    record: str
    population: Decimal = D0
    population_seq: int | None = None
    area: Decimal | None = None
    camp: dict[str, _Campaign] = field(default_factory=lambda: {"CURRENT": _Campaign(), "PREVIOUS": _Campaign()})


@dataclass
class _State:
    strata: dict[str, _Stratum] = field(default_factory=dict)
    years: Decimal = D1
    root_shoot: Decimal = D0
    rs_seqs: tuple[int, ...] = ()


class Vm0047V11Census(CalculationModule):
    code = "VM0047-V1.1-CENSUS"
    version = "1.0.0"
    methodology_code = "VM0047"
    version_label = "1.1"
    calculation_rules_version = 0
    readiness = fw.NOT_PRODUCTION_READY
    label = "VM0047 v1.1 - census-based approach (planting units on farmland, <= 50 per ha)"
    rules: ClassVar[dict[str, str]] = {r["rule_code"]: r["step"] for r in CALC_RULES}
    calculation_rule_definitions = CALC_RULES
    monitoring_rule_definitions = MONITORING_RULES
    sampling_parameters: ClassVar[dict[str, Any]] = {"quantification_approach": "CENSUS_BASED", "min_samples_per_stratum": 2,
                                                     "statistical_design": "STRATIFIED_SYSTEMATIC"}
    assumptions = ASSUMPTIONS
    variables = (
        Variable("N", "MONITORING_RECORD", "units", "STRATUM", rule_code="V47_N"),
        Variable("ALIVE", "MONITORING_RECORD", "flag", "SAMPLING_POINT", rule_code="V47_ALIVE"),
        Variable("AGB", "MONITORING_RECORD", "kg d.m.", "SAMPLING_POINT", rule_code="V47_AGB"),
        Variable("BURNED", "MONITORING_RECORD", "flag", "SAMPLING_POINT", rule_code="V47_BURNED", required=False),
        Variable("ALIVE_T0", "MONITORING_RECORD", "flag", "SAMPLING_POINT", rule_code="V47_ALIVE", required=False, period="PREVIOUS"),
        Variable("AGB_T0", "MONITORING_RECORD", "kg d.m.", "SAMPLING_POINT", rule_code="V47_AGB", required=False, period="PREVIOUS"),
        Variable("N_T0", "MONITORING_RECORD", "units", "STRATUM", rule_code="V47_N", required=False, period="PREVIOUS"),
        Variable("AREA", "STRATUM_AREA", "ha", "STRATUM", required=False),
        Variable("FSN", "MONITORING_RECORD", "kg N", "FARM", rule_code="V47_FSN", required=False),
        Variable("FON", "MONITORING_RECORD", "kg N", "FARM", rule_code="V47_FON", required=False),
        Variable("ROOT_SHOOT", "MONITORING_RECORD", "ratio", "PROJECT", rule_code="V47_ROOT_SHOOT"),
        Variable("NPR", "MONITORING_RECORD", "%", "PROJECT", rule_code="V47_NPR"),
    )
    constants = CONSTANTS
    steps = tuple(Step(r["step"], fw.IMPLEMENTED, r["rule_code"]) for r in CALC_RULES)

    @staticmethod
    def _state(ctx: CalculationContext) -> _State:
        st = getattr(ctx, "_vm0047", None)
        if st is None:
            st = _State()
            ctx._vm0047 = st  # type: ignore[attr-defined]
        return st

    @staticmethod
    def _k(ctx: CalculationContext, code: str) -> Decimal:
        v = ctx.constant(code).value
        assert isinstance(v, Decimal)
        return v

    @staticmethod
    def _rec(v: Any) -> str:
        return str(v.context.get("stratum_record_id") or v.stratum_id or "")

    # ------------------------------------------------------------------ validation
    def validate_inputs(self, ctx: CalculationContext) -> None:
        st = self._state(ctx)
        rp = ctx.snapshot["reporting_period"]
        st.years = Decimal((date.fromisoformat(rp["end"]) - date.fromisoformat(rp["start"])).days + 1) / Decimal(365)
        for v in ctx.values("N"):
            s = st.strata.setdefault(self._rec(v), _Stratum(self._rec(v)))
            if s.population_seq is not None:
                raise CalculationBlocked("DUPLICATE_INPUT", f"Stratum {s.record} has more than one census population (V47_N).", {"variable": "N"})
            s.population, s.population_seq = Decimal(v.value), v.seq
        for a in ctx.values("AREA"):
            if self._rec(a) in st.strata:
                st.strata[self._rec(a)].area = Decimal(a.value)
        for s in st.strata.values():
            if s.area is not None and s.area > 0 and s.population > MAX_DENSITY * s.area:
                raise CalculationBlocked("DENSITY_EXCEEDED", f"Stratum {s.record}: {s.population} planting units on {s.area} ha exceeds "
                                         "50 per hectare (VM0047 §4.3(3)); use the area-based approach.", {"reason": "CENSUS_DENSITY"})
        for period, alive_var, agb_var in (("CURRENT", "ALIVE", "AGB"), ("PREVIOUS", "ALIVE_T0", "AGB_T0")):
            agb = {v.sampling_point_id: v for v in ctx.values(agb_var)}
            burned = {v.sampling_point_id: v for v in ctx.values("BURNED")} if period == "CURRENT" else {}
            for a in ctx.values(alive_var):
                rec = self._rec(a)
                if rec not in st.strata:
                    raise CalculationBlocked("MISSING_REQUIRED_INPUT", f"Sampled unit in stratum {rec} but the stratum has no census "
                                             "population (V47_N).", {"variable": "N"})
                c = st.strata[rec].camp[period]
                c.n_sampled += 1
                c.seqs.append(a.seq)
                if Decimal(a.value) == 0:
                    c.dead += 1
                else:
                    b = agb.get(a.sampling_point_id)
                    if b is None:
                        raise CalculationBlocked("MISSING_REQUIRED_INPUT", f"A live sampled unit in stratum {rec} has no biomass (V47_AGB).",
                                                 {"variable": agb_var})
                    c.agb_live.append(Decimal(b.value))
                    c.seqs.append(b.seq)
                bu = burned.get(a.sampling_point_id)
                if bu is not None:
                    c.seqs.append(bu.seq)
                    if Decimal(bu.value) != 0:
                        c.burned += 1
        for s in st.strata.values():
            c = s.camp["CURRENT"]
            if c.n_sampled < 2 or len(c.agb_live) < 2:
                raise CalculationBlocked("INSUFFICIENT_SAMPLES", f"Stratum {s.record}: {c.n_sampled} sampled units ({len(c.agb_live)} alive); "
                                         "the uncertainty needs at least 2 live sampled units.", {"reason": "TOO_FEW_SAMPLES"})
        rs = ctx.values("ROOT_SHOOT")
        st.root_shoot, st.rs_seqs = Decimal(rs[0].value), tuple(v.seq for v in rs)

    # ------------------------------------------------------------------ helpers
    def _carbon_per_unit(self, ctx: CalculationContext, agb_kg: list[Decimal]) -> list[Decimal]:
        """t CO2e per live sampled unit: B x (1 + R) x CF x 44/12 (Eq. 25, expressed in CO2e as Eq. 30's C_pu)."""
        st = self._state(ctx)
        f = (D1 + st.root_shoot) * self._k(ctx, "CF") * self._k(ctx, "C_TO_CO2") / 1000
        return [b * f for b in agb_kg]

    def _stock(self, ctx: CalculationContext, s: _Stratum, period: str) -> tuple[Decimal, Decimal]:
        """(stock t CO2e = N (1 - M) C_pu, absolute 90 % half-width t CO2e) for a stratum and campaign; (0, 0) without a sample."""
        c = s.camp[period]
        population = s.population
        if period == "PREVIOUS":
            prev = [v for v in ctx.values("N_T0") if self._rec(v) == s.record]
            population = Decimal(prev[0].value) if prev else s.population
        if c.n_sampled == 0 or not c.agb_live:
            return D0, D0
        m = Decimal(c.dead) / Decimal(c.n_sampled)
        cpu = self._carbon_per_unit(ctx, c.agb_live)
        mean = stats.mean(cpu)
        stock = population * (D1 - m) * mean                                                                # Eqs. 24, 30
        if mean == 0 or len(cpu) < 2:
            return stock, stock
        t = stats.t_quantile(TWO_SIDED_90, Decimal(len(cpu) - 1))
        rel_b = t * (stats.sample_variance(cpu) / Decimal(len(cpu))).sqrt() / mean
        if m >= 1:
            return stock, stock
        t_m = stats.t_quantile(TWO_SIDED_90, Decimal(max(1, c.n_sampled - 1)))
        u_m = t_m * (m * (D1 - m) / Decimal(max(1, c.n_sampled - 1))).sqrt() / (D1 - m)                     # Eq. 31 (fraction)
        return stock, stock * (rel_b * rel_b + u_m * u_m).sqrt()

    def _campaign_totals(self, ctx: CalculationContext, period: str) -> tuple[Decimal, Decimal]:
        st = self._state(ctx)
        total, hw2 = D0, D0
        for s in st.strata.values():
            stock, hw = self._stock(ctx, s, period)
            total += stock
            hw2 += hw * hw
        return total, hw2.sqrt()

    def _seqs(self, ctx: CalculationContext, period: str) -> tuple[int, ...]:
        st = self._state(ctx)
        out = {q for s in st.strata.values() for q in s.camp[period].seqs}
        out |= {s.population_seq for s in st.strata.values() if s.population_seq is not None}
        return tuple(sorted(out | set(st.rs_seqs)))

    # ------------------------------------------------------------------ steps
    def calculate_baseline(self, ctx: CalculationContext) -> list[Output]:
        return [Output("BASELINE_STOCK_CHANGE", "BASELINE", R_BSL, D0, T, inputs=(ctx.constant("C_TO_CO2").seq,))]

    def calculate_project(self, ctx: CalculationContext) -> list[Output]:
        st, outs = self._state(ctx), []
        for rec, s in sorted(st.strata.items()):
            c = s.camp["CURRENT"]
            m = Decimal(c.dead) / Decimal(c.n_sampled)
            cpu = stats.mean([x / self._k(ctx, "C_TO_CO2") for x in self._carbon_per_unit(ctx, c.agb_live)])     # t C per unit (Eq. 25)
            seqs = tuple(sorted(set(c.seqs) | set(st.rs_seqs)))
            outs += [Output(f"MORTALITY_{rec[:8]}", "PROJECT", R_PRJ, m, "fraction", "STRATUM", rec, inputs=tuple(sorted(set(c.seqs)))),
                     Output(f"C_PU_AVG_{rec[:8]}", "PROJECT", R_PRJ, cpu, "t C/planting unit", "STRATUM", rec,
                            inputs=(*seqs, ctx.constant("CF").seq)),
                     Output(f"C_WOODY_{rec[:8]}", "PROJECT", R_PRJ, s.population * (D1 - m) * cpu, "t C", "STRATUM", rec,     # Eq. 24
                            inputs=(s.population_seq,) if s.population_seq else (), outputs=(f"MORTALITY_{rec[:8]}", f"C_PU_AVG_{rec[:8]}"))]
        return outs

    def calculate_emissions(self, ctx: CalculationContext) -> list[Output]:
        st, k = self._state(ctx), self._k
        burn_dm = D0                                                                                       # t d.m. subject to burning
        for s in st.strata.values():
            cur, prev = s.camp["CURRENT"], s.camp["PREVIOUS"]
            if cur.burned and cur.n_sampled:
                base = prev.agb_live or cur.agb_live
                burn_dm += s.population * Decimal(cur.burned) / Decimal(cur.n_sampled) * stats.mean(base) / 1000   # Eq. 27
        pe_burn = (k(ctx, "GWP_CH4") * k(ctx, "EF_BB_CH4") + k(ctx, "GWP_N2O") * k(ctx, "EF_BB_N2O")) * burn_dm * k(ctx, "COMF") / 1000  # Eq. 26
        rp = ctx.snapshot["reporting_period"]
        p_start, p_end = date.fromisoformat(rp["start"]), date.fromisoformat(rp["end"])
        n: dict[str, Decimal] = defaultdict(Decimal)
        fert_seqs = []
        for var in ("FSN", "FON"):
            for v in ctx.values(var):
                observed = v.context.get("observed_on")
                if observed is None or p_start <= date.fromisoformat(observed) <= p_end:
                    n[var] += Decimal(v.value) / 1000                                                      # t N
                    fert_seqs.append(v.seq)
        conv = k(ctx, "N2ON_TO_N2O") * k(ctx, "GWP_N2O")
        direct = (n["FSN"] + n["FON"]) * k(ctx, "EF_NDIRECT") * conv                                        # Eq. 16
        volat = (n["FSN"] * k(ctx, "FRAC_GASF") + n["FON"] * k(ctx, "FRAC_GASM")) * k(ctx, "EF_NVOLAT") * conv   # Eq. 20
        leach = (n["FSN"] + n["FON"]) * k(ctx, "FRAC_LEACH") * k(ctx, "EF_NLEACH") * conv                    # Eq. 21
        burn_in = self._seqs(ctx, "CURRENT") + self._seqs(ctx, "PREVIOUS")
        fert_in = tuple(fert_seqs) or (ctx.constant("EF_NDIRECT").seq,)
        return [Output("PE_BURN", "EMISSIONS", R_PE, pe_burn, T, inputs=tuple(sorted(set(burn_in) | {ctx.constant("COMF").seq}))),
                Output("PE_FERT", "EMISSIONS", R_PE, direct + volat + leach, T, inputs=fert_in),             # Eq. 15
                Output("PE_TOTAL", "EMISSIONS", R_PE, pe_burn + direct + volat + leach, T, outputs=("PE_BURN", "PE_FERT"))]   # Eq. 12

    def calculate_removals(self, ctx: CalculationContext) -> list[Output]:
        cur, _ = self._campaign_totals(ctx, "CURRENT")
        prev, _ = self._campaign_totals(ctx, "PREVIOUS")
        prev_in = self._seqs(ctx, "PREVIOUS")
        return [Output("DC_WP_T", "REMOVALS", R_REM, cur, T, inputs=self._seqs(ctx, "CURRENT"), outputs=tuple(
                    o for o in ctx.outputs if o.startswith("C_WOODY_"))),                                   # Eqs. 22-24
                Output("DC_WP_T_X", "REMOVALS", R_REM, prev, T, inputs=prev_in or (ctx.constant("C_TO_CO2").seq,))]

    def calculate_leakage(self, ctx: CalculationContext) -> list[Output]:
        return [Output("LK_TOTAL", "LEAKAGE", R_LK, D0, T, outputs=("DC_WP_T",))]

    def calculate_uncertainty(self, ctx: CalculationContext) -> list[Output]:
        allowance = self._k(ctx, "UNC_ALLOWANCE")
        outs = []
        for period, code, stock in (("CURRENT", "UNC_T", "DC_WP_T"), ("PREVIOUS", "UNC_T_X", "DC_WP_T_X")):
            total, hw = self._campaign_totals(ctx, period)
            rel = hw / total if total > 0 else (D0 if period == "PREVIOUS" else D1)
            outs.append(Output(f"HALF_WIDTH_{code}", "UNCERTAINTY", R_UNC, rel, "fraction", outputs=(stock,)))
            outs.append(Output(code, "UNCERTAINTY", R_UNC, min(D1, max(D0, rel - allowance)), "fraction",                  # Eq. 29
                               inputs=(ctx.constant("UNC_ALLOWANCE").seq,), outputs=(f"HALF_WIDTH_{code}",)))
        return outs

    def apply_methodology_adjustments(self, ctx: CalculationContext) -> list[Output]:
        o, st = ctx.output, self._state(ctx)
        eligible = o("HALF_WIDTH_UNC_T").value <= D1                                                          # §8.5.2
        stock_change = o("DC_WP_T").value * (D1 - o("UNC_T").value) - o("DC_WP_T_X").value * (D1 - o("UNC_T_X").value)
        if not eligible:
            stock_change = min(D0, stock_change)
        cr = stock_change - o("PE_TOTAL").value - o("LK_TOTAL").value                                         # Eq. 33
        npr_vals = ctx.values("NPR")
        npr = max(self._k(ctx, "NPR_MIN"), sum((Decimal(v.value) for v in npr_vals), D0) / Decimal(len(npr_vals)))
        buffer = max(D0, stock_change) * npr / 100
        years = st.years if st.years > 0 else D1
        lin = ("DC_WP_T", "DC_WP_T_X", "UNC_T", "UNC_T_X", "HALF_WIDTH_UNC_T")
        return [Output("STOCK_CHANGE_ADJ", "ADJUSTMENT", R_ADJ, stock_change, T, outputs=lin),
                Output("CR_T", "ADJUSTMENT", R_ADJ, cr, T, outputs=("STOCK_CHANGE_ADJ", "PE_TOTAL", "LK_TOTAL")),
                Output("CR_ANNUALIZED", "ADJUSTMENT", R_ADJ, cr / years, "t CO2e/yr", outputs=("CR_T",)),            # Eq. 34
                Output("NPR_PCT", "ADJUSTMENT", R_ADJ, npr, "%", inputs=(*(v.seq for v in npr_vals), ctx.constant("NPR_MIN").seq)),
                Output("BUFFER", "ADJUSTMENT", R_ADJ, buffer, T, outputs=("STOCK_CHANGE_ADJ", "NPR_PCT"))]

    def calculate_net_result(self, ctx: CalculationContext) -> list[Output]:
        o = ctx.output
        net = o("CR_T").value - o("BUFFER").value
        reversal = -net if net < 0 else D0
        with localcontext(fw.DECIMAL_CONTEXT):
            vcus = max(D0, net).to_integral_value(rounding=ROUND_FLOOR)
        return [Output("NET_REMOVALS", "NET", R_NET, net, T, outputs=("CR_T", "BUFFER")),
                Output("REVERSAL", "NET", R_NET, reversal, T, outputs=("NET_REMOVALS",)),
                Output("VCU_TOTAL", "NET", R_NET, vcus, "VCU (t CO2e)", outputs=("NET_REMOVALS",), is_final=True)]
