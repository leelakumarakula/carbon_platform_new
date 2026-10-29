"""Verra VM0042 Improved Agricultural Land Management, v2.2 (with the Corrections & Clarifications of 11 June 2026).

Scope (calculation specification `methodology-docs/VM0042-IALM/VM0042_v2.2_calculation_spec.md`, §1 and Q1):
- SOC stock change — Quantification Approach 2 (measure and remeasure), baseline at linked control sites, on an equivalent
  (mineral) soil mass basis (Eq. 3, §8.2.1.6, Eqs. 46/47; Verra draft Soil Sampling and Analysis Handbook v1.0 §6);
- emissions — Quantification Approach 3 (IPCC 2019 default factors): fossil fuel (Eqs. 6/7, 52), liming (Eqs. 8/9, 53),
  synthetic and organic fertiliser N2O, direct and indirect (Eqs. 16–23, 58), biomass burning CH4 and N2O (Eqs. 14, 32, 57, 59);
- uncertainty — Approach 2 sampling uncertainty (Eqs. 70, 71, 74) applied through Eqs. 44/45;
- net reductions/removals, buffer and VCUs (Eqs. 37–43, 75–79).
- leakage from imported organic amendments (§8.4.1, Eq. 33), on versions that carry the V42_OA_* rules.
Not included (they must be not applicable or de minimis for the project — Q1): Approach 1 (models), enteric fermentation and manure
(Eqs. 11–13, 26–31), N-fixing species (Eqs. 24/25), woody biomass (Eqs. 48–51), leakage 8.4.2–8.4.4 (reported as zero). Woody
biomass may only be left out while it does not decrease: on versions that carry V42_WOODY every project farm declares each period
that no shade tree was cut and no perennial crop (e.g. coffee) uprooted, and a removal blocks the run.

Inputs per sampling point and depth increment (laboratory): organic carbon (g/kg) and dry fine-earth soil mass (g, coarse
fraction > 2 mm excluded), for the reporting period (t) and the previous approved period (t − x). Field record: depth increment,
probe inside diameter (mm), number of cores. Per farm and year (monitoring records, phase BASELINE = historical schedule t = −1…−3,
PROJECT/MONITORING = reporting period): fertiliser N, fuel, lime, residues burned, irrigation type. A source with baseline records
needs a record for the reporting period too (0 when none was used). Per project: the AFOLU non-permanence risk rating (%; buffer at
least 12, more than 60 fails). Per stratum: area (SQL Server) and mean annual precipitation (mm, required) for the IPCC climate class.

NOT_PRODUCTION_READY until the production-readiness approval (methodology expert + QA sign-off) is recorded.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_FLOOR, Decimal, localcontext
from typing import Any, ClassVar

from app.calculation import framework as fw
from app.calculation.framework import CalculationBlocked, CalculationContext, CalculationModule, Constant, InputValue, Output, Step, Variable
from app.calculation.library import esm, stats
from app.calculation.library.inputs import pair_lab_samples, previous_period_gap, stratum_labels

D0, D1 = Decimal(0), Decimal(1)
REFERENCE_DEPTH_CM = Decimal(30)          # VM0042 §8.2.1.3 (7b): SOC reported to a minimum of 30 cm on an ESM basis
MIN_CONTROL_SITES = 3                     # VM0042 §8.2 QA2
T = "t CO2e"

R_BSL, R_PRJ, R_ER, R_CR, R_LK, R_UNC, R_ADJ, R_NET = ("V42-BSL", "V42-PRJ", "V42-ER", "V42-CR", "V42-LK", "V42-UNC", "V42-ADJ", "V42-NET")

CALC_RULES: tuple[dict[str, Any], ...] = (
    {"rule_code": R_BSL, "step": "BASELINE", "title": "Baseline: control-site SOC stocks (ESM) and baseline emissions",
     "equation_reference": "VM0042 v2.2 Eq. 3, §8.2.1.6, Eq. 46; Eqs. 6-9, 14, 16-23, 32"},
    {"rule_code": R_PRJ, "step": "PROJECT", "title": "Project: project-strata SOC stocks (ESM) and project emissions",
     "equation_reference": "VM0042 v2.2 Eq. 3, §8.2.1.6, Eq. 47; §8.3"},
    {"rule_code": R_ER, "step": "EMISSIONS", "title": "Emission reductions per source (fuel, liming, N2O, biomass burning)",
     "equation_reference": "VM0042 v2.2 Eqs. 52, 53, 57, 58, 59"},
    {"rule_code": R_CR, "step": "REMOVALS", "title": "SOC stock change, project and baseline (t CO2e)",
     "equation_reference": "VM0042 v2.2 Eqs. 46, 47 (x 44/12)"},
    {"rule_code": R_LK, "step": "LEAKAGE", "title": "Leakage: imported organic amendments (8.4.1); 8.4.2-8.4.4 not applicable",
     "equation_reference": "VM0042 v2.2 §8.4, Eqs. 33, 39, 42"},
    {"rule_code": R_UNC, "step": "UNCERTAINTY", "title": "Approach 2 sampling uncertainty deduction",
     "equation_reference": "VM0042 v2.2 Eqs. 70, 71, 74"},
    {"rule_code": R_ADJ, "step": "ADJUSTMENT", "title": "Uncertainty applied to stock changes; non-permanence buffer",
     "equation_reference": "VM0042 v2.2 Eqs. 44, 45, 75, 76"},
    {"rule_code": R_NET, "step": "NET", "title": "Net reductions and removals; VCUs (whole tonnes, rounded down)",
     "equation_reference": "VM0042 v2.2 Eqs. 37-43, 77-79"},
)


def _activity(code: str, title: str, parameter: str, unit: str, ref: str, level: str = "FARM") -> dict[str, Any]:
    return {"rule_code": code, "title": title, "parameter": parameter, "unit": unit, "measurement_source": "FIELD_ACTIVITY",
            "data_level": level, "frequency": "Per year (baseline t=-1..-3 and each project year)", "source_reference": ref}


MONITORING_RULES: tuple[dict[str, Any], ...] = (
    {"rule_code": "V42_OC", "title": "Soil organic carbon content (per depth increment)", "parameter": "soil_organic_carbon",
     "unit": "g/kg", "measurement_source": "LABORATORY", "data_level": "SAMPLING_POINT", "frequency": "Each sampling campaign",
     "method": "Dry combustion (Dumas) preferred; Walkley-Black / LOI not recommended", "source_reference": "VM0042 v2.2 §8.2.1.4, Eq. 3 OC"},
    {"rule_code": "V42_SOIL_MASS", "title": "Dry fine-earth soil mass of the sample (per depth increment, > 2 mm excluded)",
     "parameter": "fine_soil_mass", "unit": "g", "measurement_source": "LABORATORY", "data_level": "SAMPLING_POINT",
     "frequency": "Each sampling campaign", "source_reference": "VM0042 v2.2 §8.2.1.3 (4), §8.2.1.6 Eq. 3 M_sample"},
    _activity("V42_FSN", "Synthetic fertiliser N applied", "synthetic_fertilizer_n", "kg N", "VM0042 v2.2 Eq. 19 FSN"),
    _activity("V42_FON", "Organic fertiliser N applied", "organic_fertilizer_n", "kg N", "VM0042 v2.2 Eq. 20 FON"),
    _activity("V42_DIESEL", "Diesel consumed", "diesel", "L", "VM0042 v2.2 Eq. 7 FFC (diesel)"),
    _activity("V42_GASOLINE", "Gasoline consumed", "gasoline", "L", "VM0042 v2.2 Eq. 7 FFC (gasoline)"),
    _activity("V42_LIMESTONE", "Calcitic limestone applied", "limestone", "t", "VM0042 v2.2 Eq. 9 M_Limestone"),
    _activity("V42_DOLOMITE", "Dolomite applied", "dolomite", "t", "VM0042 v2.2 Eq. 9 M_Dolomite"),
    _activity("V42_BURN_RICE", "Rice residues burned (dry matter)", "residue_burned_rice", "kg d.m.", "VM0042 v2.2 Eqs. 14/32 MB (rice)"),
    _activity("V42_BURN_WHEAT", "Wheat residues burned (dry matter)", "residue_burned_wheat", "kg d.m.", "VM0042 v2.2 Eqs. 14/32 MB (wheat)"),
    _activity("V42_BURN_OTHER", "Other crop residues burned (dry matter)", "residue_burned_other", "kg d.m.",
              "VM0042 v2.2 Eqs. 14/32 MB (maize, sugarcane, other)"),
    {"rule_code": "V42_IRRIGATION", "title": "Irrigation type (NONE / DRIP / OTHER)", "parameter": "irrigation_type", "unit": None,
     "measurement_source": "FIELD_ACTIVITY", "data_level": "FARM", "frequency": "Per year",
     "source_reference": "VM0042 v2.2 Eq. 23 FracLEACH; IPCC 2019 Vol. 4 Ch. 11 Tier 1 note"},
    _activity("V42_NPR", "AFOLU non-permanence risk rating", "non_permanence_risk_rating", "%",
              "VM0042 v2.2 §8.7 NPR%; VCS AFOLU Non-Permanence Risk Tool", level="PROJECT"),
    {**_activity("V42_OA_IMPORTED", "Manure, compost or biosolids brought in from outside the project area and applied (not exempt)",
                 "organic_amendment_imported", "t", "VM0042 v2.2 §8.4.1, Eq. 33 M_OA"),
     "frequency": "Per project year",
     "method": "Record only amendments that are subject to §8.4.1: not made on farms in the project area (compost an estate makes "
               "from its own coffee pulp is exempt), not diverted from an uncontrolled anaerobic lagoon, pond, tank or pit, and "
               "previously used as a soil amendment elsewhere. Enter 0 when none was brought in."},
    {**_activity("V42_OA_CARBON", "Carbon content of the imported organic amendment (mass-weighted, as received)",
                 "organic_amendment_carbon_content", "t C/t", "VM0042 v2.2 §8.4.1, Eq. 33 CC_OA"),
     "frequency": "Per project year, when an amendment is brought in",
     "method": "One value per farm and period: laboratory analysis or supplier certificate (e.g. 0.15 for 15 % carbon)."},
    {"rule_code": "V42_WOODY", "title": "Woody biomass removed in the period (NO / NONE / YES)", "parameter": "woody_biomass_removed",
     "unit": None, "measurement_source": "FIELD_ACTIVITY", "data_level": "FARM", "frequency": "Each reporting period",
     "method": "NO = no shade tree cut and no perennial crop (e.g. coffee) uprooted; NONE = no woody plants on the farm (annual crops); "
               "YES = woody biomass was removed (the calculation is then blocked: Eqs. 48-51 are not implemented).",
     "source_reference": "VM0042 v2.2 §8.2 woody biomass (Eqs. 48-51), Q1 condition"},
)

_IPCC = "IPCC 2019 Refinement Vol. 4"
CONSTANTS = (
    Constant("C_TO_CO2", "3.666666666666666666666666666666667", "t CO2/t C", "44/12 (VM0042 v2.2 §8.5.1)"),
    Constant("N2ON_TO_N2O", "1.571428571428571428571428571428571", "t N2O/t N2O-N", "44/28 (VM0042 v2.2 Eqs. 18, 22, 23)"),
    Constant("GWP_CH4", "28", "t CO2e/t CH4", "VCS Standard v5.0 §3.14.4 Table 9 (IPCC AR5)"),
    Constant("GWP_N2O", "265", "t CO2e/t N2O", "VCS Standard v5.0 §3.14.4 Table 9 (IPCC AR5)"),
    Constant("EF_DIESEL", "0.002886", "t CO2e/L", "VM0042 v2.2 parameter EF_CO2,j (diesel)"),
    Constant("EF_GASOLINE", "0.002810", "t CO2e/L", "VM0042 v2.2 parameter EF_CO2,j (gasoline)"),
    Constant("EF_LIMESTONE", "0.12", "t C/t", "VM0042 v2.2 Eq. 9"),
    Constant("EF_DOLOMITE", "0.13", "t C/t", "VM0042 v2.2 Eq. 9"),
    Constant("EF1_WET_SYN", "0.016", "kg N2O-N/kg N", f"{_IPCC} Ch. 11 Table 11.1 (wet climate, synthetic)"),
    Constant("EF1_WET_OTHER", "0.006", "kg N2O-N/kg N", f"{_IPCC} Ch. 11 Table 11.1 (wet climate, other N inputs)"),
    Constant("EF1_DRY", "0.005", "kg N2O-N/kg N", f"{_IPCC} Ch. 11 Table 11.1 (dry climate, all N inputs)"),
    Constant("EF4_WET", "0.014", "kg N2O-N/kg N volatilised", f"{_IPCC} Ch. 11 Table 11.3 (wet climate)"),
    Constant("EF4_DRY", "0.005", "kg N2O-N/kg N volatilised", f"{_IPCC} Ch. 11 Table 11.3 (dry climate)"),
    Constant("EF5", "0.011", "kg N2O-N/kg N leached", f"{_IPCC} Ch. 11 Table 11.3"),
    Constant("FRAC_GASF", "0.11", "fraction", f"{_IPCC} Ch. 11 Table 11.3 (aggregated synthetic)"),
    Constant("FRAC_GASM", "0.21", "fraction", f"{_IPCC} Ch. 11 Table 11.3"),
    Constant("FRAC_LEACH", "0.24", "fraction", f"{_IPCC} Ch. 11 Table 11.3 FracLEACH-(H); 0 in dry climates without non-drip irrigation"),
    Constant("WET_PRECIP_MM", "1000", "mm", f"{_IPCC} Ch. 11 Table 11.1 note 4 (tropical: wet if annual precipitation > 1000 mm)"),
    Constant("EF_BB_CH4", "2.7", "g CH4/kg d.m. burnt", f"{_IPCC} Ch. 2 Table 2.5 (agricultural residues)"),
    Constant("EF_BB_N2O", "0.07", "g N2O/kg d.m. burnt", f"{_IPCC} Ch. 2 Table 2.5 (agricultural residues)"),
    Constant("CF_RICE", "0.80", "fraction", f"{_IPCC} Ch. 2 Table 2.6 (rice residues)"),
    Constant("CF_WHEAT", "0.90", "fraction", f"{_IPCC} Ch. 2 Table 2.6 (wheat residues)"),
    Constant("CF_OTHER", "0.80", "fraction", f"{_IPCC} Ch. 2 Table 2.6 (maize/sugarcane 0.80; conservative for other crops)"),
    Constant("NPR_MIN", "12", "%", "VCS AFOLU Non-Permanence Risk Procedure v5.0 §2.5.2 (minimum risk rating)"),
    Constant("NPR_MAX", "60", "%", "VCS AFOLU Non-Permanence Risk Procedure v5.0 §2.5.3 (above 60 the project fails the risk analysis)"),
    Constant("OA_C_RETENTION", "0.12", "fraction", "VM0042 v2.2 Eq. 33 (manure carbon retained in soil; Maillard and Angers 2014)"),
)

ASSUMPTIONS = (
    "Q2: the Eq. 74 uncertainty (%) is divided by 100 before Eqs. 37/44/45 (dimensional consistency; VCS MR v5.0 §2.4).",
    "Q3: buffer deposits are never negative; a negative net carbon-stock benefit is a reversal (VCS Standard v5.0 §3.2.21-3.2.23) "
    "reported as REVERSAL with zero VCUs.",
    "Q5: t = one-sided Student-t at 66.67 % with Welch-Satterthwaite degrees of freedom (Verra SSA Handbook draft v1.0).",
    "Q6: UNC uses the absolute mean change and is capped at 100 %.",
    "Q7/Q8: stratified estimator; independent sampling - variance of a change = sum of the two snapshot variances; control sites use "
    "the same estimator.",
    "Q11/Q13: IPCC 2019 Tier 1 factors by climate (tropical wet if precipitation > 1000 mm); FracLEACH 0 in dry climates unless "
    "irrigation other than drip. Precipitation is required for every project stratum and for every farm with activity records; "
    "a missing value blocks the run (dry factors are not assumed).",
    "Q12: equivalent mineral soil mass (SOM = SOC/0.58); linear interpolation with 2 depth increments, cubic spline with 3 or more; "
    "reference mass = mean cumulative mineral mass to 30 cm at the linked control sites in the earlier campaign of the comparison.",
    "Q14: AR5 GWPs (CH4 28, N2O 265).",
    "Q16: VCUs are whole tonnes rounded down.",
    "Cumulative project stock change for the I(dCO2_wp) switch is taken as the change since the earlier campaign of this "
    "comparison (equal to the change since the project start at the first verification).",
    "Baseline emissions per farm = mean annual activity of the BASELINE-phase records (t=-1..-3) x years in the reporting period; "
    "project emissions = PROJECT/MONITORING-phase records observed in the reporting period. A farm and source with baseline records "
    "but no record in the reporting period blocks the run (a missing record is never read as zero, which would credit a cut that "
    "was not monitored); record 0 when the source was not used.",
    "Buffer: the AFOLU non-permanence risk rating is applied as max(rating, 12) (NPR Procedure v5.0 §2.5.2); a rating above 60 "
    "blocks the run (§2.5.3), as does a rating below 0 or above 100.",
    "Leakage 8.4.1 (Eq. 33): LE_OA = sum over farms of imported mass (t) x carbon content (t C/t) x 0.12 x 44/12, from the "
    "V42_OA_IMPORTED records of the reporting period. The whole imported mass is counted, also when only part of it is additional "
    "to the look-back (conservative). Exempt amendments (8.4.1 cases 1-3) are not recorded under V42_OA_IMPORTED. A farm with "
    "imported mass needs exactly one carbon content for the period. A farm whose organic fertiliser N (V42_FON) in the reporting period "
    "is above its look-back annual mean x years needs a V42_OA_IMPORTED record for the period (0 when the amendment was made on the farm), "
    "else the run is blocked. Versions set up before these rules existed report zero leakage.",
    "Woody biomass (Eqs. 48-51) is not quantified, so it may be left out only while it does not decrease: when the version carries "
    "V42_WOODY, every project farm needs a NO or NONE declaration for the period, and YES (shade trees cut or perennial crops "
    "uprooted) blocks the run.",
    "Out of scope and treated as not applicable / zero (Q1 condition): enteric, manure, N-fixing species, woody biomass, leakage "
    "8.4.2-8.4.4.",
    "Eqs. 46/47 (x 1/x): the SOC change between the two campaigns is credited whole to this reporting period (the annual rate x 1/x "
    "times the x years between the campaigns), while emissions are annual baseline means x the years of this period. The two only "
    "describe the same span when the earlier campaign closes the immediately preceding period: an earlier approved period that ends "
    "more than one day before this period starts (a gap, e.g. an intervening period without an approved dataset) blocks the run "
    "(PREVIOUS_PERIOD_NOT_ADJACENT), so a multi-period SOC change is never credited against one period's emissions.",
    "Vintages (Q16): the result of the reporting period is quantified and rounded down once for the whole period; the split by "
    "calendar-year vintage is not made by the module (the registry states the vintages of what it issues).",
    "Eqs. 44/45: one sign indicator I(dCO2_soil) is taken from the net SOC change (project minus baseline) and the same factor "
    "(1 - UNC x I) is applied to the project and the baseline stock change.",
    "Control sites linked to more than one project stratum enter the baseline of each of those strata; the covariance this creates "
    "between strata is ignored in the Eq. 70/71 variance (strata are treated as independent).",
    "Activity records need an observed-on date: BASELINE records are grouped by calendar year for the look-back mean, project records "
    "count only when dated inside the reporting period; an undated record blocks the run (MISSING_OBSERVED_ON). Irrigation type is "
    "read per phase: the baseline uses the look-back (BASELINE) records - leaching applies only when all of them are OTHER - and the "
    "project uses the reporting period's records (any OTHER applies leaching); a farm with look-back irrigation records needs one for "
    "the period.",
    "Each sample has exactly one approved organic carbon and one soil mass result, and each field collection one sample per depth "
    "increment; duplicates or a result without its partner block the run (DUPLICATE_LAB_RESULT / MASS_RESULT_MISSING).",
    "Per-stratum outputs are named by the stratum code (e.g. REF_MASS_S1), or by a collision-free prefix of the stratum record id "
    "when the code is not available.",
)


def _activity_var(code: str, rule: str, unit: str) -> Variable:
    return Variable(code, "MONITORING_RECORD", unit, "FARM", rule_code=rule, required=False)


def _observed(v: InputValue, variable: str) -> date:
    """The record's observed-on date; an undated activity record can be placed neither in a look-back year nor in the period."""
    observed = v.context.get("observed_on")
    if not observed:
        raise CalculationBlocked("MISSING_OBSERVED_ON", f"A {variable} record (input #{v.seq}) has no observed-on date, so it can be placed "
                                 "neither in a look-back year nor in the reporting period. Record the date.",
                                 {"variable": variable, "input_seq": v.seq, "farm_id": v.farm_id, "phase": v.context.get("phase")})
    return date.fromisoformat(str(observed)[:10])


@dataclass
class _Profile:
    key: str                 # field collection id
    period: str
    stratum_record: str
    role: str
    linked: list[str]
    profile: esm.Profile
    increments: int
    seqs: list[int]


@dataclass
class _Group:
    """SOC stocks (Mg C/ha at the stratum's reference mass) of one stratum and campaign."""
    values: list[Decimal] = field(default_factory=list)
    seqs: list[int] = field(default_factory=list)


@dataclass
class _State:
    method: str = esm.LINEAR
    ref: dict[str, Decimal] = field(default_factory=dict)            # project stratum record -> reference mineral mass
    area: dict[str, Decimal] = field(default_factory=dict)           # project stratum record -> ha
    area_seqs: dict[str, int] = field(default_factory=dict)
    groups: dict[tuple[str, str, str], _Group] = field(default_factory=dict)  # (stratum record, PROJECT|BASELINE, CURRENT|PREVIOUS)
    labels: dict[str, str] = field(default_factory=dict)             # project stratum record -> output-code label
    years: Decimal = D1
    emissions: dict[str, dict[str, Decimal]] = field(default_factory=dict)    # scenario -> source -> t CO2e
    emission_seqs: list[int] = field(default_factory=list)
    leakage_oa: Decimal | None = None                                # Eq. 33 (t CO2e); None = the version has no V42_OA_* rules
    leakage_seqs: list[int] = field(default_factory=list)
    # organic fertiliser N per farm: (look-back annual mean, reporting-period total), kg N
    fon: tuple[dict[str, Decimal], dict[str, Decimal]] = field(default_factory=lambda: ({}, {}))


class Vm0042V22(CalculationModule):
    code = "VM0042-V2.2-QA2-QA3"
    # 1.1.0: data safeguards (period records, rainfall, risk rating), Eq. 33 leakage, woody biomass
    # 1.2.0: an organic-N increase needs a V42_OA_IMPORTED declaration for the period (forgotten compost entry)
    # 1.3.0: profiles must reach 30 cm and the reference soil mass (never extrapolated)
    # 1.4.0: duplicate / unpaired lab results, dated records, irrigation per phase, adjacent previous campaign, stratum-code output names
    version = "1.4.0"
    methodology_code = "VM0042"
    version_label = "2.2"
    calculation_rules_version = 0           # bound to the selecting methodology version (registry.bind)
    readiness = fw.NOT_PRODUCTION_READY
    label = "VM0042 v2.2 - SOC measure & remeasure (QA2) + default-factor emissions (QA3)"
    rules: ClassVar[dict[str, str]] = {r["rule_code"]: r["step"] for r in CALC_RULES}
    calculation_rule_definitions = CALC_RULES
    monitoring_rule_definitions = MONITORING_RULES
    sampling_parameters: ClassVar[dict[str, Any]] = {"quantification_approach": "MEASURE_AND_REMEASURE", "min_samples_per_stratum": 3,
                                                     "core_details_required": True, "statistical_design": "STRATIFIED_RANDOM"}
    assumptions = ASSUMPTIONS
    variables = (
        Variable("OC_T", "LAB_RESULT", "g/kg", "SAMPLING_POINT", rule_code="V42_OC"),
        Variable("MASS_T", "LAB_RESULT", "g", "SAMPLING_POINT", rule_code="V42_SOIL_MASS"),
        Variable("OC_T0", "LAB_RESULT", "g/kg", "SAMPLING_POINT", rule_code="V42_OC", period="PREVIOUS"),
        Variable("MASS_T0", "LAB_RESULT", "g", "SAMPLING_POINT", rule_code="V42_SOIL_MASS", period="PREVIOUS"),
        Variable("AREA", "STRATUM_AREA", "ha", "STRATUM"),
        Variable("PRECIP", "STRATUM_CHARACTERISTIC", "mm", "STRATUM", parameter="PRECIPITATION_MM"),
        _activity_var("FSN", "V42_FSN", "kg N"),
        _activity_var("FON", "V42_FON", "kg N"),
        _activity_var("DIESEL", "V42_DIESEL", "L"),
        _activity_var("GASOLINE", "V42_GASOLINE", "L"),
        _activity_var("LIMESTONE", "V42_LIMESTONE", "t"),
        _activity_var("DOLOMITE", "V42_DOLOMITE", "t"),
        _activity_var("BURN_RICE", "V42_BURN_RICE", "kg d.m."),
        _activity_var("BURN_WHEAT", "V42_BURN_WHEAT", "kg d.m."),
        _activity_var("BURN_OTHER", "V42_BURN_OTHER", "kg d.m."),
        Variable("IRRIGATION", "MONITORING_RECORD", "", "FARM", rule_code="V42_IRRIGATION", kind="TEXT", required=False),
        Variable("NPR", "MONITORING_RECORD", "%", "PROJECT", rule_code="V42_NPR"),
        Variable("OA_MASS", "MONITORING_RECORD", "t", "FARM", rule_code="V42_OA_IMPORTED", required=False, optional_rule=True),
        Variable("OA_CC", "MONITORING_RECORD", "t C/t", "FARM", rule_code="V42_OA_CARBON", required=False, optional_rule=True),
        Variable("WOODY", "MONITORING_RECORD", "", "FARM", rule_code="V42_WOODY", kind="TEXT", required=False, optional_rule=True),
    )
    constants = CONSTANTS
    steps = tuple(Step(r["step"], fw.IMPLEMENTED, r["rule_code"]) for r in CALC_RULES)

    # ------------------------------------------------------------------ shared state
    @staticmethod
    def _state(ctx: CalculationContext) -> _State:
        st = getattr(ctx, "_vm0042", None)
        if st is None:
            st = _State()
            ctx._vm0042 = st  # type: ignore[attr-defined]
        return st

    @staticmethod
    def _k(ctx: CalculationContext, code: str) -> Decimal:
        v = ctx.constant(code).value
        assert isinstance(v, Decimal)
        return v

    def validate_inputs(self, ctx: CalculationContext) -> None:
        st = self._state(ctx)
        gap = previous_period_gap(ctx.snapshot)
        if gap is not None:
            raise CalculationBlocked("PREVIOUS_PERIOD_NOT_ADJACENT", "The earlier approved sampling campaign does not close the period "
                                     "immediately before this reporting period. The SOC change between the campaigns would be credited "
                                     "against this period's emissions only (VM0042 Eqs. 46/47); calculate each period against the campaign "
                                     "that precedes it.", gap)
        profiles = self._profiles(ctx)
        st.method = esm.method_for(min(p.increments for p in profiles))
        project_records = sorted({p.stratum_record for p in profiles if p.role == "PROJECT"})
        controls = {p.stratum_record for p in profiles if p.role == "CONTROL"}
        if len(controls) < MIN_CONTROL_SITES:
            raise CalculationBlocked("CONTROL_SITES_REQUIRED", f"VM0042 Quantification Approach 2 needs at least {MIN_CONTROL_SITES} baseline "
                                     f"control sites with samples (found {len(controls)}).", {"reason": "TOO_FEW_CONTROL_SITES"})
        for a in ctx.values("AREA"):
            if a.context.get("stratum_role") == "PROJECT":
                st.area[a.context["stratum_record_id"]] = Decimal(a.value)
                st.area_seqs[a.context["stratum_record_id"]] = a.seq
        # reference mineral soil mass per project stratum = mean mass to 30 cm at its linked control sites, earlier campaign (Q12)
        for rec in project_records:
            linked = [p for p in profiles if p.role == "CONTROL" and p.period == "PREVIOUS" and rec in p.linked]
            if not linked:
                raise CalculationBlocked("CONTROL_SITE_REQUIRED", f"Project stratum {rec} has no linked control site sampled in the earlier "
                                         "campaign (VM0042: at least one control site per stratum).", {"reason": "STRATUM_WITHOUT_CONTROL"})
            masses = [esm.mass_at_depth(p.profile, REFERENCE_DEPTH_CM, st.method) for p in linked]
            st.ref[rec] = stats.mean(masses)
            if rec not in st.area:
                raise CalculationBlocked("MISSING_REQUIRED_INPUT", f"No area for project stratum {rec}.", {"variable": "AREA"})
        for p in profiles:
            targets = [p.stratum_record] if p.role == "PROJECT" else [r for r in p.linked if r in st.ref]
            scenario = "PROJECT" if p.role == "PROJECT" else "BASELINE"
            for rec in targets:
                if p.profile.cumulative_soil_mass_mg_ha[-1] < st.ref[rec]:
                    # the reference soil mass lies below this core's deepest sample: its SOC there would be extrapolated, not measured
                    raise CalculationBlocked("SAMPLING_DEPTH_INSUFFICIENT", f"Field collection {p.key} holds less soil "
                                             f"({p.profile.cumulative_soil_mass_mg_ha[-1]:.1f} Mg/ha) than stratum {rec}'s reference soil mass "
                                             f"({st.ref[rec]:.1f} Mg/ha); sample deeper so the equivalent soil mass is reached "
                                             "(Verra SSA Handbook §6).", {"reason": "REFERENCE_MASS_NOT_REACHED", "field_collection": p.key})
                g = st.groups.setdefault((rec, scenario, p.period), _Group())
                g.values.append(esm.oc_at_mass(p.profile, st.ref[rec], st.method))
                g.seqs.extend(p.seqs)
        for rec in project_records:
            for scenario in ("PROJECT", "BASELINE"):
                for period in ("CURRENT", "PREVIOUS"):
                    grp = st.groups.get((rec, scenario, period))
                    if grp is None or len(grp.values) < 2:
                        raise CalculationBlocked("INSUFFICIENT_SAMPLES", f"Stratum {rec}: {scenario.lower()} samples in the {period.lower()} "
                                                 "campaign are fewer than 2 (a variance needs at least two).", {"reason": "TOO_FEW_SAMPLES"})
        st.labels = stratum_labels([*ctx.values("AREA"), *ctx.values("OC_T"), *ctx.values("OC_T0")], project_records)
        self._npr(ctx)                       # refuse an unusable risk rating before any result is produced
        rp = ctx.snapshot["reporting_period"]
        start, end = date.fromisoformat(rp["start"]), date.fromisoformat(rp["end"])
        st.years = Decimal((end - start).days + 1) / Decimal(365)
        st.emissions = self._emissions(ctx, st)
        project_farms = sorted({f for a in ctx.values("AREA") if a.context.get("stratum_role") == "PROJECT"
                                for f in a.context.get("farm_ids", [])})
        if self._configured(ctx, "V42_WOODY"):
            self._woody(ctx, project_farms)
        if self._configured(ctx, "V42_OA_IMPORTED"):
            self._leakage_oa(ctx, st, start, end)

    @staticmethod
    def _configured(ctx: CalculationContext, rule_code: str) -> bool:
        """Whether the locked version carries a monitoring rule (older snapshots do not list them: not configured)."""
        return rule_code in (ctx.snapshot.get("methodology") or {}).get("monitoring_rules", [])

    @staticmethod
    def _woody(ctx: CalculationContext, project_farms: list[str]) -> None:
        """Woody biomass may be left out only while it does not decrease (Eqs. 48-51 are not implemented)."""
        answers: dict[str, set[str]] = defaultdict(set)
        for v in ctx.values("WOODY"):
            if v.farm_id:
                answers[v.farm_id].add(str(v.value).strip().upper())
        bad = sorted(f for f, a in answers.items() if not a <= {"NO", "NONE", "YES"})
        if bad:
            raise CalculationBlocked("INVALID_INPUT", f"V42_WOODY must be NO, NONE or YES (farm {', '.join(bad[:5])}).",
                                     {"variable": "WOODY", "reason": "WOODY_VALUE_INVALID", "farms": bad})
        removed = sorted(f for f, a in answers.items() if "YES" in a)
        if removed:
            raise CalculationBlocked("WOODY_BIOMASS_REMOVED", f"Woody biomass was removed on farm {', '.join(removed[:5])} (shade trees cut or "
                                     "perennial crops uprooted). This module does not quantify woody biomass (VM0042 Eqs. 48-51), so the "
                                     "loss cannot be left out and the period cannot be credited here.", {"variable": "WOODY", "farms": removed})
        missing = [f for f in project_farms if f not in answers]
        if missing:
            raise CalculationBlocked("MISSING_REQUIRED_INPUT", f"No woody biomass declaration (V42_WOODY) for the reporting period on farm "
                                     f"{', '.join(missing[:5])}. Record NO (no shade tree cut, no coffee uprooted) or NONE (no woody plants).",
                                     {"variable": "WOODY", "reason": "WOODY_DECLARATION_MISSING", "farms": missing})

    def _leakage_oa(self, ctx: CalculationContext, st: _State, start: date, end: date) -> None:
        """VM0042 Eq. 33: LE_OA = sum of M_OA x CC_OA x 0.12 x 44/12 over the farms' imported amendments in the reporting period."""
        mass: dict[str, Decimal] = defaultdict(Decimal)
        for v in ctx.values("OA_MASS"):
            if not v.farm_id or v.context.get("phase") == "BASELINE" or not start <= _observed(v, "OA_MASS") <= end:
                continue
            if Decimal(v.value) < 0:
                raise CalculationBlocked("INVALID_INPUT", "V42_OA_IMPORTED cannot be negative.", {"variable": "OA_MASS"})
            mass[v.farm_id] += Decimal(v.value)
            st.leakage_seqs.append(v.seq)
        # more organic N than in the look-back means more manure / compost was applied: where it came from must be declared, so a
        # forgotten V42_OA_IMPORTED entry is never read as "nothing imported" (0 is accepted: estate-made compost is exempt)
        look_back, period_n = st.fon
        undeclared = sorted(f for f, n in period_n.items() if n > look_back.get(f, D0) * st.years and f not in mass)
        if undeclared:
            raise CalculationBlocked("MISSING_REQUIRED_INPUT", f"Organic fertiliser N on farm {', '.join(undeclared[:5])} is above its look-back "
                                     "level, but no imported organic amendment (V42_OA_IMPORTED) is recorded for the reporting period. Record "
                                     "the tonnes brought in from outside the project area, or 0 when the compost was made on the farm "
                                     "(exempt) (VM0042 §8.4.1).", {"variable": "OA_MASS", "reason": "OA_DECLARATION_MISSING", "farms": undeclared})
        carbon: dict[str, list[InputValue]] = defaultdict(list)
        for v in ctx.values("OA_CC"):
            if v.farm_id:
                carbon[v.farm_id].append(v)
        total = D0
        for f, m in sorted(mass.items()):
            if m == 0:
                continue
            cc = carbon.get(f, [])
            if not cc:
                raise CalculationBlocked("MISSING_REQUIRED_INPUT", f"Farm {f} brought in {fw.decimal_text(m)} t of organic amendment but has no "
                                         "carbon content (V42_OA_CARBON) for the period (VM0042 Eq. 33).",
                                         {"variable": "OA_CC", "reason": "OA_CARBON_MISSING", "farm_id": f})
            if len(cc) > 1:
                raise CalculationBlocked("INVALID_INPUT", f"Farm {f} has {len(cc)} carbon contents (V42_OA_CARBON) for the period; record one "
                                         "mass-weighted value.", {"variable": "OA_CC", "reason": "OA_CARBON_DUPLICATE", "farm_id": f})
            content = Decimal(cc[0].value)
            if not D0 < content <= D1:
                raise CalculationBlocked("INVALID_INPUT", f"Farm {f}: the carbon content must be a fraction above 0 and at most 1 t C/t "
                                         f"(got {fw.decimal_text(content)}).", {"variable": "OA_CC", "reason": "OA_CARBON_OUT_OF_RANGE"})
            total += m * content * self._k(ctx, "OA_C_RETENTION") * self._k(ctx, "C_TO_CO2")              # Eq. 33
            st.leakage_seqs.append(cc[0].seq)
        st.leakage_oa = total
        st.leakage_seqs += [ctx.constant("OA_C_RETENTION").seq, ctx.constant("C_TO_CO2").seq]

    def _npr(self, ctx: CalculationContext) -> tuple[Decimal, Decimal]:
        """(recorded risk rating, rating applied to the buffer) — NPR Procedure v5.0 §2.5.2 / §2.5.3."""
        values = ctx.values("NPR")
        if not values:
            raise CalculationBlocked("MISSING_REQUIRED_INPUT", "No AFOLU non-permanence risk rating (V42_NPR) for the reporting period.",
                                     {"variable": "NPR"})
        ratings = [Decimal(v.value) for v in values]
        if any(r < 0 or r > 100 for r in ratings):
            raise CalculationBlocked("INVALID_INPUT", "The non-permanence risk rating (V42_NPR) must be between 0 and 100 %.",
                                     {"variable": "NPR", "reason": "NPR_OUT_OF_RANGE"})
        rated = sum(ratings, D0) / Decimal(len(ratings))
        if rated > self._k(ctx, "NPR_MAX"):
            raise CalculationBlocked("NPR_UNACCEPTABLE", f"The non-permanence risk rating is {fw.decimal_text(rated)} %: above 60 the project "
                                     "fails the risk analysis and cannot be credited until its risk is lowered (NPR Procedure v5.0 §2.5.3).",
                                     {"variable": "NPR", "rating": fw.decimal_text(rated)})
        return rated, max(rated, self._k(ctx, "NPR_MIN"))

    def _profiles(self, ctx: CalculationContext) -> list[_Profile]:
        """One soil profile per field collection and campaign: depth increments paired by sample (OC + soil mass)."""
        out: list[_Profile] = []
        for period, oc_var, mass_var in (("CURRENT", "OC_T", "MASS_T"), ("PREVIOUS", "OC_T0", "MASS_T0")):
            by_fc = pair_lab_samples(ctx, oc_var, mass_var)
            for fc, pairs in sorted(by_fc.items()):
                c = pairs[0][1].context
                if c.get("probe_diameter_mm") is None or c.get("cores_count") is None:
                    raise CalculationBlocked("MISSING_REQUIRED_INPUT", f"Field collection {fc} has no probe diameter / number of cores "
                                             "(VM0042 Eq. 3).", {"reason": "CORE_DETAILS_MISSING"})
                layers = []
                for o, m in pairs:
                    if o.context.get("depth_top_cm") is None or o.context.get("depth_bottom_cm") is None:
                        raise CalculationBlocked("MISSING_REQUIRED_INPUT", "A sample has no depth increment.", {"reason": "DEPTH_MISSING"})
                    layers.append(esm.Layer(Decimal(o.context["depth_top_cm"]), Decimal(o.context["depth_bottom_cm"]),
                                            Decimal(m.value), Decimal(o.value)))
                if len(layers) < 2:
                    raise CalculationBlocked("DEPTH_INCREMENTS_REQUIRED", f"Field collection {fc} has {len(layers)} depth increment; ESM needs "
                                             "at least two (VM0042 §8.2.1.3 (7c)).", {"reason": "ONE_INCREMENT"})
                if max(layer.depth_bottom_cm for layer in layers) < REFERENCE_DEPTH_CM:
                    # never extrapolated: a shallower profile would be extended on its last segment (esm), not measured
                    raise CalculationBlocked("SAMPLING_DEPTH_INSUFFICIENT", f"Field collection {fc} is sampled to "
                                             f"{max(layer.depth_bottom_cm for layer in layers)} cm; VM0042 reports SOC to at least "
                                             f"{REFERENCE_DEPTH_CM} cm (§8.2.1.3 (7b)).", {"reason": "TOO_SHALLOW", "field_collection": fc})
                try:
                    prof = esm.profile(layers, Decimal(c["probe_diameter_mm"]), int(c["cores_count"]), mineral=True)
                except esm.EsmError as e:
                    raise CalculationBlocked("INVALID_SOIL_PROFILE", f"Field collection {fc}: {e}", {"reason": "ESM"}) from None
                out.append(_Profile(fc, period, c.get("stratum_record_id") or "", c.get("stratum_role") or "PROJECT",
                                    list(c.get("linked_stratum_record_ids") or []), prof, len(layers),
                                    sorted({x.seq for pair in pairs for x in pair})))
        if not out:
            raise CalculationBlocked("MISSING_REQUIRED_INPUT", "No soil profiles.", {"variable": "OC_T"})
        return out

    # ------------------------------------------------------------------ emissions (Approach 3)
    def _emissions(self, ctx: CalculationContext, st: _State) -> dict[str, dict[str, Decimal]]:
        k = self._k
        farm_wet: dict[str, bool] = {}
        rain_strata: set[str] = set()
        for p in ctx.values("PRECIP"):
            for f in p.context.get("farm_ids", []):
                farm_wet[f] = Decimal(p.value) > k(ctx, "WET_PRECIP_MM")
            rain_strata.add(p.context.get("stratum_record_id") or "")
            st.emission_seqs.append(p.seq)
        no_rain = sorted({a.context.get("stratum_code") or a.context["stratum_record_id"] for a in ctx.values("AREA")
                          if a.context.get("stratum_role") == "PROJECT" and a.context.get("stratum_record_id") not in rain_strata})
        if no_rain:
            raise CalculationBlocked("MISSING_REQUIRED_INPUT", f"No mean annual precipitation (PRECIPITATION_MM) on project stratum "
                                     f"{', '.join(no_rain)}: it decides the IPCC wet or dry factors, so it is required.",
                                     {"variable": "PRECIP", "reason": "PRECIPITATION_MISSING", "strata": no_rain})
        rp = ctx.snapshot["reporting_period"]
        p_start, p_end = date.fromisoformat(rp["start"]), date.fromisoformat(rp["end"])
        irrigation = self._irrigation(ctx, p_start, p_end, rp)

        def totals(var: str) -> tuple[dict[str, Decimal], dict[str, Decimal]]:
            """(baseline annual mean per farm, project total per farm in the reporting period)."""
            hist: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
            proj: dict[str, Decimal] = defaultdict(Decimal)
            for v in ctx.values(var):
                if not v.farm_id:
                    continue
                st.emission_seqs.append(v.seq)
                phase, observed = v.context.get("phase"), _observed(v, var)
                if phase == "BASELINE":
                    hist[v.farm_id][str(observed.year)] += Decimal(v.value)
                elif p_start <= observed <= p_end:
                    proj[v.farm_id] += Decimal(v.value)
            bsl = {f: sum(years.values(), D0) / Decimal(len(years)) for f, years in hist.items()}
            return bsl, dict(proj)

        out: dict[str, dict[str, Decimal]] = {"BASELINE": defaultdict(Decimal), "PROJECT": defaultdict(Decimal)}  # type: ignore[dict-item]
        gwp_n2o, gwp_ch4, n2o = k(ctx, "GWP_N2O"), k(ctx, "GWP_CH4"), k(ctx, "N2ON_TO_N2O")
        series = {v: totals(v) for v in ("FSN", "FON", "DIESEL", "GASOLINE", "LIMESTONE", "DOLOMITE", "BURN_RICE", "BURN_WHEAT", "BURN_OTHER")}
        st.fon = series["FON"]
        missing = sorted((f, var) for var, (bsl, prj) in series.items() for f in bsl if f not in prj)
        if missing:
            listed = "; ".join(f"V42_{var} on farm {f}" for f, var in missing[:5]) + (" …" if len(missing) > 5 else "")
            raise CalculationBlocked("MISSING_REQUIRED_INPUT", f"Baseline records exist but the reporting period {rp['start']} to {rp['end']} "
                                     f"has none: {listed}. Record the period's value (0 if the source was not used).",
                                     {"reason": "PERIOD_RECORD_MISSING", "missing": [{"farm_id": f, "variable": var} for f, var in missing]})
        farms = sorted({f for b, p in series.values() for f in (*b, *p)})
        no_rain_farms = [f for f in farms if f not in farm_wet]
        if no_rain_farms:
            raise CalculationBlocked("MISSING_REQUIRED_INPUT", f"Farm {', '.join(no_rain_farms[:5])} has activity records but lies in no "
                                     "stratum with a mean annual precipitation (PRECIPITATION_MM), so its climate is unknown.",
                                     {"variable": "PRECIP", "reason": "PRECIPITATION_MISSING", "farms": no_rain_farms})
        for scenario in ("BASELINE", "PROJECT"):
            idx, scale = (0, st.years) if scenario == "BASELINE" else (1, D1)

            def amount(var: str, farm: str, idx: int = idx, scale: Decimal = scale) -> Decimal:
                return series[var][idx].get(farm, D0) * scale
            for f in farms:
                wet = farm_wet[f]                     # every farm has a climate class (checked above)
                fsn, fon = amount("FSN", f), amount("FON", f)
                ef1_syn = k(ctx, "EF1_WET_SYN") if wet else k(ctx, "EF1_DRY")
                ef1_org = k(ctx, "EF1_WET_OTHER") if wet else k(ctx, "EF1_DRY")
                ef4 = k(ctx, "EF4_WET") if wet else k(ctx, "EF4_DRY")
                leach = k(ctx, "FRAC_LEACH") if (wet or irrigation[scenario].get(f, False)) else D0
                # Eqs. 18, 22, 23 with N in kg (kg N2O-N -> t N2O via / 1000)
                direct = (fsn * ef1_syn + fon * ef1_org) * n2o * gwp_n2o / 1000
                volat = (fsn * k(ctx, "FRAC_GASF") + fon * k(ctx, "FRAC_GASM")) * ef4 * n2o * gwp_n2o / 1000
                leached = (fsn + fon) * leach * k(ctx, "EF5") * n2o * gwp_n2o / 1000
                out[scenario]["N2O_FERT"] += direct + volat + leached
                out[scenario]["FUEL"] += amount("DIESEL", f) * k(ctx, "EF_DIESEL") + amount("GASOLINE", f) * k(ctx, "EF_GASOLINE")  # Eqs. 6/7
                out[scenario]["LIME"] += (amount("LIMESTONE", f) * k(ctx, "EF_LIMESTONE")
                                          + amount("DOLOMITE", f) * k(ctx, "EF_DOLOMITE")) * k(ctx, "C_TO_CO2")              # Eq. 9
                burnt = (amount("BURN_RICE", f) * k(ctx, "CF_RICE") + amount("BURN_WHEAT", f) * k(ctx, "CF_WHEAT")
                         + amount("BURN_OTHER", f) * k(ctx, "CF_OTHER"))                                                    # kg d.m.
                out[scenario]["CH4_BB"] += burnt * k(ctx, "EF_BB_CH4") / Decimal(10) ** 6 * gwp_ch4                         # Eq. 14
                out[scenario]["N2O_BB"] += burnt * k(ctx, "EF_BB_N2O") / Decimal(10) ** 6 * gwp_n2o                         # Eq. 32
        st.emission_seqs = sorted(set(st.emission_seqs)) or [ctx.constant("GWP_N2O").seq]
        return {s: dict(v) for s, v in out.items()}

    @staticmethod
    def _irrigation(ctx: CalculationContext, p_start: date, p_end: date, rp: dict[str, Any]) -> dict[str, dict[str, bool]]:
        """Scenario -> farm -> irrigation other than drip (FracLEACH in dry climates), each read from its own phase's records."""
        look_back: dict[str, set[str]] = defaultdict(set)
        period: dict[str, set[str]] = defaultdict(set)
        for v in ctx.values("IRRIGATION"):
            if not v.farm_id:
                continue
            value, observed = str(v.value).strip().upper(), _observed(v, "IRRIGATION")
            if v.context.get("phase") == "BASELINE":
                look_back[v.farm_id].add(value)
            elif p_start <= observed <= p_end:
                period[v.farm_id].add(value)
        missing = sorted(f for f in look_back if f not in period)
        if missing:
            raise CalculationBlocked("MISSING_REQUIRED_INPUT", f"Baseline irrigation records exist but the reporting period {rp['start']} to "
                                     f"{rp['end']} has none: V42_IRRIGATION on farm {', '.join(missing[:5])}. Record the period's "
                                     "irrigation type.", {"reason": "PERIOD_RECORD_MISSING", "variable": "IRRIGATION",
                                                          "missing": [{"farm_id": f, "variable": "IRRIGATION"} for f in missing]})
        # conservative: the baseline leaches only when every look-back record is OTHER, the project when any period record is
        return {"BASELINE": {f: vals == {"OTHER"} for f, vals in look_back.items()},
                "PROJECT": {f: "OTHER" in vals for f, vals in period.items()}}

    # ------------------------------------------------------------------ steps
    def _soc_outputs(self, ctx: CalculationContext, scenario: str, rule: str, step: str) -> list[Output]:
        st = self._state(ctx)
        outs = []
        for rec in sorted(st.ref):
            for period in ("PREVIOUS", "CURRENT"):
                g = st.groups[(rec, scenario, period)]
                outs.append(Output(f"SOC_{scenario[:3]}_{period[:4]}_{st.labels[rec]}", step, rule, stats.mean(g.values), "Mg C/ha", "STRATUM",
                                   rec, inputs=tuple(sorted(set(g.seqs)))))
        return outs

    def _emission_outputs(self, ctx: CalculationContext, scenario: str, rule: str, step: str) -> list[Output]:
        st = self._state(ctx)
        seqs = tuple(st.emission_seqs)
        return [Output(f"E_{scenario[:3]}_{src}", step, rule, st.emissions[scenario].get(src, D0), T, inputs=seqs)
                for src in ("FUEL", "LIME", "N2O_FERT", "CH4_BB", "N2O_BB")]

    def calculate_baseline(self, ctx: CalculationContext) -> list[Output]:
        st = self._state(ctx)
        refs = [Output(f"REF_MASS_{st.labels[rec]}", "BASELINE", R_BSL, st.ref[rec], "Mg/ha", "STRATUM", rec,
                       inputs=tuple(sorted({s for (r, sc, pe), g in st.groups.items() if r == rec and sc == "BASELINE" and pe == "PREVIOUS"
                                            for s in g.seqs}))) for rec in sorted(st.ref)]
        return refs + self._soc_outputs(ctx, "BASELINE", R_BSL, "BASELINE") + self._emission_outputs(ctx, "BASELINE", R_BSL, "BASELINE")

    def calculate_project(self, ctx: CalculationContext) -> list[Output]:
        return self._soc_outputs(ctx, "PROJECT", R_PRJ, "PROJECT") + self._emission_outputs(ctx, "PROJECT", R_PRJ, "PROJECT")

    def calculate_emissions(self, ctx: CalculationContext) -> list[Output]:
        outs = []
        for src in ("FUEL", "LIME", "N2O_FERT", "CH4_BB", "N2O_BB"):
            b, p = ctx.output(f"E_BAS_{src}"), ctx.output(f"E_PRO_{src}")
            outs.append(Output(f"ER_{src}", "EMISSIONS", R_ER, b.value - p.value, T, outputs=(b.code, p.code)))   # bsl - wp
        total = sum((o.value for o in outs), D0)
        outs.append(Output("ER_SOURCES", "EMISSIONS", R_ER, total, T, outputs=tuple(o.code for o in outs)))
        return outs

    def calculate_removals(self, ctx: CalculationContext) -> list[Output]:
        st = self._state(ctx)
        c2 = self._k(ctx, "C_TO_CO2")
        outs = []
        for scenario, code in (("PROJECT", "DCO2_SOIL_WP"), ("BASELINE", "DCO2_SOIL_BSL")):
            total, used = D0, []
            for rec in sorted(st.ref):
                lbl = st.labels[rec]
                prev, cur = ctx.output(f"SOC_{scenario[:3]}_PREV_{lbl}"), ctx.output(f"SOC_{scenario[:3]}_CURR_{lbl}")
                total += (cur.value - prev.value) * st.area[rec] * c2                                   # Eqs. 46/47 (x 44/12)
                used += [prev.code, cur.code]
            outs.append(Output(code, "REMOVALS", R_CR, total, T, inputs=(*sorted(st.area_seqs.values()), ctx.constant("C_TO_CO2").seq),
                               outputs=tuple(used)))
        return outs

    def calculate_leakage(self, ctx: CalculationContext) -> list[Output]:
        st = self._state(ctx)
        if st.leakage_oa is None:            # the version has no V42_OA_* rules: 8.4.1 not applicable, as before
            return [Output("LK_TOTAL", "LEAKAGE", R_LK, D0, T, outputs=("ER_SOURCES", "DCO2_SOIL_WP"))]
        return [Output("LK_OA", "LEAKAGE", R_LK, st.leakage_oa, T, inputs=tuple(sorted(set(st.leakage_seqs)))),
                Output("LK_TOTAL", "LEAKAGE", R_LK, st.leakage_oa, T, outputs=("LK_OA",))]

    def calculate_uncertainty(self, ctx: CalculationContext) -> list[Output]:
        st = self._state(ctx)
        c2 = self._k(ctx, "C_TO_CO2")
        area = sum(st.area.values(), D0)
        components: list[tuple[Decimal, int]] = []
        for rec in sorted(st.ref):
            w = (st.area[rec] / area) * c2
            for scenario in ("PROJECT", "BASELINE"):
                for period in ("CURRENT", "PREVIOUS"):
                    g = st.groups[(rec, scenario, period)]
                    components.append((w * w * stats.sample_variance(g.values) / Decimal(len(g.values)), len(g.values)))   # Eqs. 70/71
        variance = sum((c for c, _ in components), D0)
        mean_change = (ctx.output("DCO2_SOIL_WP").value - ctx.output("DCO2_SOIL_BSL").value) / area                       # t CO2e/ha
        df = stats.welch_satterthwaite(components)
        t = stats.t_quantile(stats.T_PROBABILITY, df)
        if mean_change == 0:
            unc = Decimal(100)
        else:
            unc = min(Decimal(100), t * variance.sqrt() / abs(mean_change) * 100)                                            # Eq. 74
        lineage = ("DCO2_SOIL_WP", "DCO2_SOIL_BSL")
        return [Output("UNC_VARIANCE", "UNCERTAINTY", R_UNC, variance, "(t CO2e/ha)^2", outputs=lineage),
                Output("UNC_DF", "UNCERTAINTY", R_UNC, df, "degrees of freedom", outputs=lineage),
                Output("UNC_T", "UNCERTAINTY", R_UNC, t, "t-value (one-sided 66.67 %)", outputs=("UNC_DF",)),
                Output("UNC_PCT", "UNCERTAINTY", R_UNC, unc, "%", outputs=("UNC_VARIANCE", "UNC_T", *lineage))]

    def apply_methodology_adjustments(self, ctx: CalculationContext) -> list[Output]:
        unc = ctx.output("UNC_PCT").value / 100                                                   # Q2: % -> fraction
        wp, bsl = ctx.output("DCO2_SOIL_WP").value, ctx.output("DCO2_SOIL_BSL").value
        sign = D1 if wp - bsl >= 0 else -D1                                                       # I(dCO2_soil), Eqs. 44/45
        adj_wp, adj_bsl = wp * (D1 - unc * sign), bsl * (D1 - unc * sign)
        rated, npr = self._npr(ctx)                                                               # applied = max(rating, 12)
        npr_seqs = (*(v.seq for v in ctx.values("NPR")), ctx.constant("NPR_MIN").seq)
        i_wp = D1 if adj_wp > 0 else D0
        frac = npr / 100
        mn = min(D0, adj_wp) - min(D0, adj_bsl)
        mx = max(D0, adj_wp) - max(D0, adj_bsl)
        bu_er = max(D0, (i_wp * mn + (D1 - i_wp) * (mn + mx)) * frac)                             # Eq. 75 (never negative, Q3)
        bu_cr = max(D0, i_wp * mx * frac)                                                         # Eq. 76
        lin = ("UNC_PCT", "DCO2_SOIL_WP", "DCO2_SOIL_BSL")
        return [Output("DCO2_WP_ADJ", "ADJUSTMENT", R_ADJ, adj_wp, T, outputs=lin),
                Output("DCO2_BSL_ADJ", "ADJUSTMENT", R_ADJ, adj_bsl, T, outputs=lin),
                Output("NPR_RATED", "ADJUSTMENT", R_ADJ, rated, "%", inputs=npr_seqs[:-1]),
                Output("NPR_PCT", "ADJUSTMENT", R_ADJ, npr, "%", inputs=npr_seqs),
                Output("BUFFER_ER", "ADJUSTMENT", R_ADJ, bu_er, T, inputs=npr_seqs, outputs=("DCO2_WP_ADJ", "DCO2_BSL_ADJ")),
                Output("BUFFER_CR", "ADJUSTMENT", R_ADJ, bu_cr, T, inputs=npr_seqs, outputs=("DCO2_WP_ADJ", "DCO2_BSL_ADJ"))]

    def calculate_net_result(self, ctx: CalculationContext) -> list[Output]:
        o = ctx.output
        wp, bsl = o("DCO2_WP_ADJ").value, o("DCO2_BSL_ADJ").value
        i_wp = D1 if wp > 0 else D0
        mn = min(D0, wp) - min(D0, bsl)
        mx = max(D0, wp) - max(D0, bsl)
        er = o("ER_SOURCES").value + mn + (D1 - i_wp) * mx                                        # Eq. 37 (QA1 soil CH4/N2O not used)
        cr = i_wp * mx                                                                            # Eq. 40
        lk = o("LK_TOTAL").value
        lk_er = lk * er / (er + cr) if er + cr != 0 else D0                                       # Eqs. 39/42
        er_net, cr_net = er - lk_er, cr - (lk - lk_er)                                            # Eqs. 38/41
        vcu_er, vcu_cr = er_net - o("BUFFER_ER").value, cr_net - o("BUFFER_CR").value             # Eqs. 77/78
        total = vcu_er + vcu_cr                                                                   # Eq. 79
        reversal = -total if total < 0 else D0                                                    # Q3: negative benefit = reversal
        with localcontext(fw.DECIMAL_CONTEXT):
            vcus = max(D0, total).to_integral_value(rounding=ROUND_FLOOR)                         # Q16: whole tonnes, rounded down
        base = ("ER_SOURCES", "DCO2_WP_ADJ", "DCO2_BSL_ADJ", "LK_TOTAL")
        return [Output("ER_T", "NET", R_NET, er, T, outputs=base),
                Output("CR_T", "NET", R_NET, cr, T, outputs=base),
                Output("ER_NET", "NET", R_NET, er_net, T, outputs=("ER_T", "LK_TOTAL")),
                Output("CR_NET", "NET", R_NET, cr_net, T, outputs=("CR_T", "LK_TOTAL")),
                Output("VCU_ER", "NET", R_NET, vcu_er, T, outputs=("ER_NET", "BUFFER_ER")),
                Output("VCU_CR", "NET", R_NET, vcu_cr, T, outputs=("CR_NET", "BUFFER_CR")),
                Output("REVERSAL", "NET", R_NET, reversal, T, outputs=("VCU_ER", "VCU_CR")),
                Output("VCU_TOTAL", "NET", R_NET, vcus, "VCU (t CO2e)", outputs=("VCU_ER", "VCU_CR"), is_final=True)]
