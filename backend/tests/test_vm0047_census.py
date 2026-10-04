"""VM0047 v1.1 census-based module on a synthetic frozen snapshot, checked against an independent float hand calculation: Eqs. 24/25
(live sampled units, R, CF), Eq. 31 mortality uncertainty, the dimensional reading of Eq. 29, Eq. 33 with the previous campaign,
burning (Eqs. 26/27) and fertiliser N2O (Eqs. 15-21), the AFOLU buffer (minimum 12 %) and whole VCUs."""
import math
from decimal import Decimal

import pytest

from app.calculation import framework as fw
from app.calculation.library import stats
from app.calculation.modules.vm0047_v1_1 import Vm0047V11Census

N, AREA, R = 400, 10.0, 0.25
# campaign -> sampled units: (alive, agb kg d.m., burned)
UNITS = {
    "CURRENT": [(1, 42.0, 0), (1, 55.0, 1), (0, 0.0, 0), (1, 48.0, 0), (1, 61.0, 0), (1, 39.0, 0), (1, 52.0, 0), (1, 47.0, 0),
                (1, 58.0, 0), (0, 0.0, 0)],
    "PREVIOUS": [(1, 12.0, 0), (1, 15.0, 0), (1, 11.0, 0), (1, 14.0, 0), (0, 0.0, 0), (1, 13.0, 0), (1, 16.0, 0), (1, 12.5, 0)],
}
STR = {"stratum_role": "PROJECT", "stratum_record_id": "S1", "farm_ids": ["f1"]}


def _snapshot(units: dict = UNITS, npr: str = "10", fert: bool = True, population: int = N) -> dict:
    rows: list[dict] = []

    def add(var: str, value: str, unit: str, level: str, farm: str | None = None, point: str | None = None, ctx: dict | None = None) -> None:
        rows.append({"seq": len(rows) + 1, "variable": var, "value": value, "value_kind": "NUMBER", "unit": unit, "level": level,
                     "stratum_id": None, "farm_id": farm, "sampling_point_id": point, "context": ctx or {}})

    for period, sfx in (("CURRENT", ""), ("PREVIOUS", "_T0")):
        add("N" + sfx, str(population), "units", "STRATUM", ctx={**STR, "period": period})
        for i, (alive, agb, burned) in enumerate(units[period]):
            pt = f"{period[:1]}{i}"
            ctx = {**STR, "period": period, "observed_on": "2027-05-01"}
            add("ALIVE" + sfx, str(alive), "flag", "SAMPLING_POINT", point=pt, ctx=ctx)
            if alive:
                add("AGB" + sfx, str(agb), "kg d.m.", "SAMPLING_POINT", point=pt, ctx=ctx)
            if period == "CURRENT":
                add("BURNED", str(burned), "flag", "SAMPLING_POINT", point=pt, ctx=ctx)
    add("AREA", str(AREA), "ha", "STRATUM", ctx=STR)
    if fert:
        add("FSN", "60", "kg N", "FARM", farm="f1", ctx={"phase": "PROJECT", "observed_on": "2026-08-01"})
        add("FON", "20", "kg N", "FARM", farm="f1", ctx={"phase": "PROJECT", "observed_on": "2026-08-01"})
    add("ROOT_SHOOT", str(R), "ratio", "PROJECT")
    add("NPR", npr, "%", "PROJECT")
    for c in Vm0047V11Census.constants:
        add(c.code, fw.decimal_text(Decimal(c.value)), c.unit, "PROJECT")
    return {"reporting_period": {"start": "2022-06-01", "end": "2027-05-31"}, "previous_period": {"start": "2021-06-01", "end": "2022-05-31"},
            "inputs": rows}


def _out(res: fw.ExecutionResult, code: str) -> float:
    return float(next(r["value"] for r in res.outputs if r["output_code"] == code))


def _t(df: int) -> float:
    return float(stats.t_quantile(0.95, Decimal(df)))


def _campaign(units: list[tuple]) -> tuple[float, float]:
    live = [a for alive, a, _ in units if alive]
    n = len(units)
    m = (n - len(live)) / n
    cpu = [a * (1 + R) * 0.47 * 44 / 12 / 1000 for a in live]        # t CO2e per live unit (Eq. 25 x 44/12)
    mean = sum(cpu) / len(cpu)
    stock = N * (1 - m) * mean                                         # Eqs. 24/30
    se = math.sqrt(sum((x - mean) ** 2 for x in cpu) / (len(cpu) - 1) / len(cpu))
    rel_b = _t(len(cpu) - 1) * se / mean
    u_m = _t(n - 1) * math.sqrt(m * (1 - m) / (n - 1)) / (1 - m)       # Eq. 31
    return stock, math.sqrt(rel_b ** 2 + u_m ** 2)


def test_census_module_matches_hand_calculation() -> None:
    res = fw.execute(Vm0047V11Census(), _snapshot())
    cur, rel_c = _campaign(UNITS["CURRENT"])
    prev, rel_p = _campaign(UNITS["PREVIOUS"])
    unc_c, unc_p = min(1, max(0, rel_c - 0.10)), min(1, max(0, rel_p - 0.10))
    stock_change = cur * (1 - unc_c) - prev * (1 - unc_p)
    # burning: 1 of 10 sampled units burned; pre-burn biomass = previous mean of live units (Eq. 27)
    prev_live = [a for alive, a, _ in UNITS["PREVIOUS"] if alive]
    burn_dm = N * 1 / 10 * (sum(prev_live) / len(prev_live)) / 1000
    pe_burn = (28 * 6.8 + 265 * 0.26) * burn_dm * 1.0 / 1000
    n2o = 44 / 28 * 265
    fsn, fon = 0.060, 0.020
    pe_fert = (fsn + fon) * 0.01 * n2o + (fsn * 0.11 + fon * 0.21) * 0.01 * n2o + (fsn + fon) * 0.24 * 0.011 * n2o
    cr = stock_change - pe_burn - pe_fert
    buffer = stock_change * 12 / 100                                   # rating 10 -> minimum 12
    vcus = math.floor(cr - buffer)
    assert _out(res, "MORTALITY_S1") == pytest.approx(0.2)
    assert _out(res, "DC_WP_T") == pytest.approx(cur, rel=1e-9)
    assert _out(res, "DC_WP_T_X") == pytest.approx(prev, rel=1e-9)
    assert _out(res, "UNC_T") == pytest.approx(unc_c, rel=1e-6)
    assert _out(res, "PE_BURN") == pytest.approx(pe_burn, rel=1e-9) and _out(res, "PE_FERT") == pytest.approx(pe_fert, rel=1e-9)
    assert _out(res, "NPR_PCT") == 12
    assert _out(res, "CR_T") == pytest.approx(cr, rel=1e-6)
    assert _out(res, "CR_ANNUALIZED") == pytest.approx(cr / (1826 / 365), rel=1e-6)
    assert _out(res, "VCU_TOTAL") == vcus and vcus > 0
    assert {r["rule_code"] for r in res.outputs} == set(Vm0047V11Census.rules)


def test_census_guards() -> None:
    with pytest.raises(fw.CalculationBlocked) as e:                    # 600 units on 10 ha > 50/ha
        fw.execute(Vm0047V11Census(), _snapshot(population=600))
    assert e.value.code == "DENSITY_EXCEEDED"
    few = {"CURRENT": [(1, 40.0, 0), (0, 0.0, 0)], "PREVIOUS": UNITS["PREVIOUS"]}
    with pytest.raises(fw.CalculationBlocked) as e:
        fw.execute(Vm0047V11Census(), _snapshot(few))
    assert e.value.code == "INSUFFICIENT_SAMPLES"
    # first verification after the census (no previous biomass sample): dC(t - x) = 0
    res = fw.execute(Vm0047V11Census(), _snapshot({"CURRENT": UNITS["CURRENT"], "PREVIOUS": []}, npr="20", fert=False))
    assert _out(res, "DC_WP_T_X") == 0 and _out(res, "NPR_PCT") == 20 and _out(res, "VCU_TOTAL") > 0
