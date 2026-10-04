"""Gold Standard SOC Framework (402) v1.0 modules on synthetic frozen snapshots, checked against independent hand calculations in
plain float arithmetic: Approach 1 (equivalent soil mass, Eqs. 2/3/5, uncertainty Eqs. 7-11 with the Table 6 t-values),
Approach 3 (Eqs. 4/6 with IPCC Table 4 factors, bound combinations), project emissions (Eqs. 12-18; 402.6 seed Eqs. 6/7),
yield leakage (Eq. 19 / 402.4 Eq. 8), the 20 % buffer and whole GS VERs."""
import math
from decimal import Decimal
from itertools import product

import pytest

from app.calculation import framework as fw
from app.calculation import registry
from app.calculation.modules.gs_soc_402 import FACTORS, Gs402CoverCropsA1, Gs402ImprovedTillageA3, Gs402ZeroTillageA1

D_MM, CORES, AREA = 21.5, 4, 50.0
# campaign -> profiles [(top, bottom, fine mass g, OC g/kg), ...]; 3 samples per campaign (GS Table 6 minimum)
PROFILES = {
    "PREVIOUS": [[(0, 30, 280.0, 11.0), (30, 50, 200.0, 6.0)], [(0, 30, 290.0, 10.5), (30, 50, 205.0, 6.2)],
                 [(0, 30, 285.0, 11.4), (30, 50, 198.0, 5.9)]],
    "CURRENT": [[(0, 30, 282.0, 12.4), (30, 50, 201.0, 6.6)], [(0, 30, 288.0, 12.1), (30, 50, 206.0, 6.5)],
                [(0, 30, 284.0, 12.9), (30, 50, 199.0, 6.4)]],
}
T90 = {3: 2.92}                     # GS 402 Table 6 (n = 3)


class _Snap:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def add(self, var: str, value: str, unit: str, level: str, farm: str | None = None, ctx: dict | None = None, kind: str = "NUMBER") -> None:
        self.rows.append({"seq": len(self.rows) + 1, "variable": var, "value": value, "value_kind": kind, "unit": unit, "level": level,
                          "stratum_id": None, "farm_id": farm, "sampling_point_id": None, "context": ctx or {}})

    def done(self, module: fw.CalculationModule) -> dict:
        for c in module.constants:
            self.add(c.code, fw.decimal_text(Decimal(c.value)), c.unit, "PROJECT")
        return {"reporting_period": {"start": "2026-06-01", "end": "2027-05-31"},
                "previous_period": {"start": "2025-06-01", "end": "2026-05-31"}, "inputs": self.rows}


STRATUM = {"stratum_role": "PROJECT", "stratum_record_id": "S1", "farm_ids": ["f1"]}


def _soil(s: _Snap, profiles: dict = PROFILES) -> None:
    n = 0
    for period, profs in profiles.items():
        sfx = "_T" if period == "CURRENT" else "_T0"
        for i, prof in enumerate(profs):
            for top, bottom, mass, oc in prof:
                n += 1
                ctx = {"period": period, "depth_top_cm": str(top), "depth_bottom_cm": str(bottom), "probe_diameter_mm": str(D_MM),
                       "cores_count": CORES, "root_sample_id": f"s{n}", "field_collection_id": f"{period}-{i}", **STRATUM}
                s.add("OC" + sfx, str(oc), "g/kg", "SAMPLING_POINT", ctx=ctx)
                s.add("MASS" + sfx, str(mass), "g", "SAMPLING_POINT", ctx=ctx)


def _activities(s: _Snap, yields: tuple[float, float] = (4000.0, 4000.0)) -> None:
    s.add("AREA", str(AREA), "ha", "STRATUM", ctx=STRATUM)
    for var, unit, bsl, prj in (("FERT_N", "kg N", (100, 120), 150), ("DIESEL", "L", (900, 1100), 1200), ("AGROCHEM", "t CO2e", (1, 1), 0.5)):
        for year, value in zip(("2023-06-01", "2024-06-01"), bsl, strict=True):
            s.add(var, str(value), unit, "FARM", farm="f1", ctx={"phase": "BASELINE", "observed_on": year})
        s.add(var, str(prj), unit, "FARM", farm="f1", ctx={"phase": "PROJECT", "observed_on": "2026-09-01"})
    s.add("FEF_DIESEL", "0.00268", "t CO2e/L", "PROJECT", ctx={"phase": "MONITORING"})
    s.add("PAA", "YES", "", "PROJECT", ctx={"phase": "MONITORING"}, kind="TEXT")   # 2026+ vintages: Paris-aligned (GS 119)
    for year in ("2023-06-01", "2024-06-01"):
        s.add("YIELD", str(yields[0]), "kg/ha", "FARM", farm="f1", ctx={"phase": "BASELINE", "observed_on": year})
    s.add("YIELD", str(yields[1]), "kg/ha", "FARM", farm="f1", ctx={"phase": "PROJECT", "observed_on": "2026-10-01"})


def _out(res: fw.ExecutionResult, code: str) -> float:
    return float(next(r["value"] for r in res.outputs if r["output_code"] == code))


# ---------------------------------------------------------------- independent hand calculation (floats)
def _cum(prof: list[tuple]) -> tuple[list[float], list[float], list[float]]:
    area_mm2 = math.pi * (D_MM / 2) ** 2 * CORES
    mass, oc, depth = [0.0], [0.0], [0.0]
    for _, bottom, m, c in prof:
        fine = m / area_mm2 * 10_000            # Mg/ha
        mass.append(mass[-1] + fine)
        oc.append(oc[-1] + fine * c / 1000)
        depth.append(bottom)
    return mass, oc, depth


def _lin(x: list[float], y: list[float], t: float) -> float:
    i = max(k for k in range(len(x) - 1) if x[k] <= t) if t < x[-1] else len(x) - 2
    return y[i] + (y[i + 1] - y[i]) * (t - x[i]) / (x[i + 1] - x[i])


def _measured(depth_cm: float) -> dict[str, float]:
    ref = sum(_lin(_cum(p)[2], _cum(p)[0], depth_cm) for p in PROFILES["PREVIOUS"]) / 3
    soc = {k: [_lin(_cum(p)[0], _cum(p)[1], ref) for p in v] for k, v in PROFILES.items()}
    m = {k: sum(v) / len(v) for k, v in soc.items()}
    se = {k: math.sqrt(sum((x - m[k]) ** 2 for x in v) / (len(v) - 1)) / math.sqrt(len(v)) for k, v in soc.items()}
    dsoc = (m["CURRENT"] - m["PREVIOUS"]) * AREA
    lower = ((m["CURRENT"] - T90[3] * se["CURRENT"]) - (m["PREVIOUS"] + T90[3] * se["PREVIOUS"])) * AREA
    upper = ((m["CURRENT"] + T90[3] * se["CURRENT"]) - (m["PREVIOUS"] - T90[3] * se["PREVIOUS"])) * AREA
    unc = min(1.0, abs(upper - lower) / (2 * dsoc))
    ud = min(1.0, max(0.0, unc - 0.20))
    return {"ref": ref, "soc0": m["PREVIOUS"], "soct": m["CURRENT"], "dsoc": dsoc, "unc": unc, "ud": ud}


def _pe(years: float = 1.0) -> dict[str, float]:
    fert = max(0.0, 150 - 110 * years) * 0.01                    # Eq. 13, EF_FE as printed
    fuel = max(0.0, 1200 - 1000 * years) * 0.00268                # Eqs. 14/15
    agro = max(0.0, 0.5 - 1 * years)                              # Eq. 17 (decrease -> 0)
    return {"fert": fert, "fuel": fuel, "agro": agro, "total": fert + fuel + agro}


def _credits(dsoc_c: float, ud: float, pe: float, lk: float) -> dict[str, float]:
    gross = dsoc_c * (1 - ud) * 44 / 12 - pe - lk                 # Eqs. 1/2
    buffer = max(0.0, gross) * 0.20
    net = gross - buffer
    return {"gross": gross, "buffer": buffer, "net": net, "vers": math.floor(max(0.0, net))}


# ---------------------------------------------------------------- tests
def test_zero_tillage_approach1_matches_hand_calculation() -> None:
    s = _Snap()
    _soil(s)
    _activities(s)
    res = fw.execute(Gs402ZeroTillageA1(), s.done(Gs402ZeroTillageA1()))
    e = _measured(50.0)                                           # 402.4: reference depth 50 cm
    years = 365 / 365
    pe = _pe(years)
    c = _credits(e["dsoc"], e["ud"], pe["total"], 0.0)
    assert _out(res, "REF_MASS_S1") == pytest.approx(e["ref"], rel=1e-9)
    assert _out(res, "SOC_0_S1") == pytest.approx(e["soc0"], rel=1e-9)
    assert _out(res, "SOC_T_S1") == pytest.approx(e["soct"], rel=1e-9)
    assert _out(res, "DSOC_C") == pytest.approx(e["dsoc"], rel=1e-9)
    assert _out(res, "UNC") == pytest.approx(e["unc"], rel=1e-4)          # t from the quantile vs Table 6 (4 decimals)
    assert _out(res, "PE_FERT") == pytest.approx(pe["fert"]) and _out(res, "PE_AGRO") == 0
    assert _out(res, "PE_TOTAL") == pytest.approx(pe["total"], rel=1e-9)
    assert _out(res, "LK_TOTAL") == 0
    assert _out(res, "BUFFER") == pytest.approx(c["buffer"], rel=1e-4)
    assert _out(res, "GS_VER_TOTAL") == c["vers"] and res.net_value == str(c["vers"]) and c["vers"] > 0
    assert {r["rule_code"] for r in res.outputs} == set(Gs402ZeroTillageA1.rules)
    assert fw.execute(Gs402ZeroTillageA1(), s.done(Gs402ZeroTillageA1())).output_sha256 != ""


def test_improved_tillage_approach3_matches_hand_calculation() -> None:
    # IPCC 2019 Table 5.5 (GS 402 Table 4): tropical moist, full -> reduced tillage, medium input; SOC_REF 47 t C/ha
    f = {"SOC_REF": 47.0, "F_LU": 0.83, "F_MG_BL": 1.00, "F_I_BL": 1.00, "F_MG_PR": 1.04, "F_I_PR": 1.00}
    u = {"F_LU": 11.0, "F_MG_PR": 7.0}                             # ± % (2 SD) from the table; others without -> SE 50 %, t = 3
    t_bl, t_pr = 20.0, 3.0
    s = _Snap()
    strat = {**STRATUM}
    for k, v in f.items():
        s.add(k, str(v), "t C/ha" if k == "SOC_REF" else "factor", "STRATUM", ctx=strat)
    for k, v in u.items():
        s.add(f"U_{k}", str(v), "%", "STRATUM", ctx=strat)
    s.add("T_BL", str(t_bl), "yr", "STRATUM", ctx=strat)
    s.add("T_PR", str(t_pr), "yr", "STRATUM", ctx=strat)
    _activities(s)
    mod = Gs402ImprovedTillageA3()
    res = fw.execute(mod, s.done(mod))

    def dsoc(x: dict) -> float:                                    # Eq. 6 at the end minus at the start of the period
        return x["SOC_REF"] * x["F_LU"] * (x["F_MG_PR"] * x["F_I_PR"] - x["F_MG_BL"] * x["F_I_BL"]) * (min(t_pr, 20) - min(t_pr - 1, 20)) / 20
    soc_bl = 47.0 * (1 + (0.83 * 1.0 * 1.0 - 1) * 20 / 20)        # Eq. 4
    ranges = []
    for k in FACTORS:
        half = f[k] * u[k] / 200 * 1.675 if k in u else f[k] * 0.5 * 3
        ranges.append((max(0.0, f[k] - half), f[k] + half))
    vals = [dsoc(dict(zip(FACTORS, c, strict=True))) for c in product(*ranges)]
    d = dsoc(f) * AREA
    unc = min(1.0, (max(vals) - min(vals)) * AREA / (2 * d))
    ud = min(1.0, max(0.0, unc - 0.2))
    c = _credits(d, ud, _pe()["total"], 0.0)
    assert _out(res, "SOC_BL_S1") == pytest.approx(soc_bl, rel=1e-12)
    assert _out(res, "SOC_0_S1") == pytest.approx(soc_bl + 47.0 * 0.83 * 0.04 * 2 / 20, rel=1e-12)
    assert _out(res, "DSOC_C") == pytest.approx(d, rel=1e-12)
    assert _out(res, "UNC") == pytest.approx(unc, rel=1e-12) and _out(res, "UD") == pytest.approx(ud, rel=1e-12)
    assert _out(res, "GS_VER_TOTAL") == c["vers"]
    assert ud > 0.5                                                # default SE 50 % / t = 3 makes the deduction large


def test_cover_crops_seed_emissions_and_yield_leakage() -> None:
    s = _Snap()
    _soil(s)
    _activities(s, yields=(4000.0, 3600.0))                        # 10 % yield reduction -> leakage
    s.add("SEED", "1500", "kg", "FARM", farm="f1", ctx={"phase": "PROJECT", "observed_on": "2026-11-01"})
    s.add("EF_SP", "0.0008", "t CO2e/kg", "PROJECT", ctx={"phase": "MONITORING"})
    s.add("EF_ST", "0.0000001", "t CO2e/(kg km)", "PROJECT", ctx={"phase": "MONITORING"})
    s.add("DIST", "300", "km", "PROJECT", ctx={"phase": "MONITORING"})
    mod = Gs402CoverCropsA1()
    snap = s.done(mod)
    with pytest.raises(fw.CalculationBlocked) as blocked:          # yield fell: the leakage-area factor is required
        fw.execute(mod, snap)
    assert blocked.value.code == "MISSING_REQUIRED_INPUT" and blocked.value.details["variable"] == "LK_EF"
    s.rows = [r for r in s.rows if r["variable"] not in {c.code for c in mod.constants}]
    s.add("LK_EF", "2.5", "t CO2e/ha", "PROJECT", ctx={"phase": "MONITORING"})
    res = fw.execute(mod, s.done(mod))
    e = _measured(30.0)                                            # 402.6: no depth stated -> 30 cm (IPCC)
    seed = 1500 * (0.0008 + 0.0000001 * 300)                       # 402.6 Eq. 7
    lk = (4000 - 3600) / 4000 * AREA * 2.5                         # 402.6 Eq. 10 with CY_min = CY_BL
    pe = _pe()["total"] + seed
    c = _credits(e["dsoc"], e["ud"], pe, lk)
    assert _out(res, "PE_SEED") == pytest.approx(seed, rel=1e-12)
    assert _out(res, "LK_DISPLACED_HA") == pytest.approx(5.0) and _out(res, "LK_TOTAL") == pytest.approx(lk)
    assert _out(res, "ER_GROSS") == pytest.approx(c["gross"], rel=1e-4)
    assert _out(res, "GS_VER_TOTAL") == c["vers"]


def test_guards_and_reversal() -> None:
    mod = Gs402ZeroTillageA1()
    # fewer than 3 samples in a campaign
    s = _Snap()
    _soil(s, {"PREVIOUS": PROFILES["PREVIOUS"][:2], "CURRENT": PROFILES["CURRENT"]})
    _activities(s)
    with pytest.raises(fw.CalculationBlocked) as e:
        fw.execute(mod, s.done(mod))
    assert e.value.code == "INSUFFICIENT_SAMPLES"
    # 402.4 needs samples to 50 cm
    s = _Snap()
    _soil(s, {k: [[layer for layer in p if layer[1] <= 30] + [(30, 40, 150.0, 6.0)] for p in v] for k, v in PROFILES.items()})
    _activities(s)
    with pytest.raises(fw.CalculationBlocked) as e:
        fw.execute(mod, s.done(mod))
    assert e.value.code == "SAMPLING_DEPTH_INSUFFICIENT"
    # SOC loss -> no credits, reversal reported, no buffer
    s = _Snap()
    _soil(s, {"PREVIOUS": PROFILES["CURRENT"], "CURRENT": PROFILES["PREVIOUS"]})
    _activities(s)
    res = fw.execute(mod, s.done(mod))
    assert _out(res, "GS_VER_TOTAL") == 0 and _out(res, "REVERSAL") > 0 and _out(res, "BUFFER") == 0
    assert _out(res, "DC_SOC_ADJ") == _out(res, "DSOC_C") < 0           # the full loss, not reduced by the uncertainty deduction
    assert _out(res, "REVERSAL") == pytest.approx(-_out(res, "DSOC_C") * 44 / 12 + _out(res, "PE_TOTAL"), rel=1e-9)


def test_registry_resolves_the_selected_gs_module() -> None:
    codes = [m.code for m in registry.modules() if m.methodology_code == "GS402"]
    assert codes == ["GS402-ZT-A1", "GS402-IT-A1", "GS402-IT-A3", "GS402-CC-A1", "GS402-CC-A3"]
    assert registry.resolve("GS402", "1.0", "GS402-CC-A3").code == "GS402-CC-A3"   # type: ignore[union-attr]
    assert registry.resolve("GS402", "1.0", "VM0042-V2.2-QA2-QA3").code == "GS402-ZT-A1"   # type: ignore[union-attr]
    bound = registry.bind(registry.by_code("GS402-IT-A3"), 3, "PRODUCTION_READY")
    assert bound is not None and bound.calculation_rules_version == 3 and bound.readiness == "PRODUCTION_READY"
    assert bound.declaration() == {**Gs402ImprovedTillageA3().declaration(), "calculation_rules_version": 3, "readiness": "PRODUCTION_READY"}


def test_paris_alignment_gate_for_2026_vintages() -> None:
    s = _Snap()
    _soil(s)
    _activities(s)
    s.rows = [r for r in s.rows if r["variable"] != "PAA"]
    res = fw.execute(Gs402ZeroTillageA1(), s.done(Gs402ZeroTillageA1()))
    assert _out(res, "PAA_BLOCKED_SHARE") == 1 and _out(res, "GS_VER_TOTAL") == 0 and _out(res, "BUFFER") == 0
