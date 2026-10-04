"""Rice methane (VM0051 v1.1 QA3 and CCTS AG04.002 v1.0) on synthetic snapshots against hand calculations with IPCC 2019 Tables
5.11-5.14: EF = EFc x SFw x SFp x SFo, SFo = (1 + sum ROA x CFOA)^0.59, the 5 t/ha baseline straw, the drying-period N2O (0.00314),
the conservative look-back regime and the two uncertainty profiles."""
import math
from decimal import Decimal

import pytest

from app.calculation import framework as fw
from app.calculation.modules.rice import CctsAg04002, Vm0051V11

UNITS = {"AREA": "ha", "DAYS": "days", "STRAW": "t/ha", "COMPOST": "t/ha", "FYM": "t/ha", "GREEN": "t/ha", "N": "kg N/ha", "DIESEL": "L",
         "BURN": "kg d.m.", "EFC": "kg CH4/ha/day", "UNC": "%", "PE_AB": "t CO2e", "LE": "t CO2e", "PE_FUEL": "t CO2e"}


def _snap(module: type[fw.CalculationModule], project: dict, baseline: list[dict], extra: dict | None = None) -> dict:
    rows: list[dict] = []

    def add(var: str, value: object, level: str, farm: str | None, ctx: dict) -> None:
        text = var in ("WATER", "PRESEASON", "STRAW_TIMING", "REGION")
        rows.append({"seq": len(rows) + 1, "variable": var, "value": str(value), "value_kind": "TEXT" if text else "NUMBER",
                     "unit": UNITS.get(var, ""), "level": level, "stratum_id": None, "farm_id": farm, "sampling_point_id": None, "context": ctx})

    for season, values in project.items():
        for var, value in values.items():
            add(var, value, "FARM", "f1", {"phase": "PROJECT", "observed_on": season})
    for i, values in enumerate(baseline):
        for var, value in values.items():
            add(var, value, "FARM", "f1", {"phase": "BASELINE", "observed_on": f"202{i}-10-15"})
    for var, value in (extra or {"REGION": "SOUTH_ASIA"}).items():
        add(var, value, "PROJECT", None, {"phase": "MONITORING"})
    for c in module.constants:
        rows.append({"seq": len(rows) + 1, "variable": c.code, "value": fw.decimal_text(Decimal(c.value)), "value_kind": "NUMBER", "unit": c.unit,
                     "level": "PROJECT", "stratum_id": None, "farm_id": None, "sampling_point_id": None, "context": {}})
    return {"reporting_period": {"start": "2026-06-01", "end": "2027-05-31"}, "inputs": rows}


def _out(res: fw.ExecutionResult, code: str) -> float:
    return float(next(r["value"] for r in res.outputs if r["output_code"] == code))


PROJECT = {"2026-10-20": {"AREA": 2.0, "DAYS": 110, "WATER": "MULTIPLE", "PRESEASON": "SHORT", "STRAW": 3.0, "STRAW_TIMING": "LONG", "FYM": 2.0,
                          "N": 120, "DIESEL": 40},
           "2027-04-10": {"AREA": 2.0, "DAYS": 100, "WATER": "SINGLE", "PRESEASON": "SHORT", "N": 100}}
BASELINE = [{"WATER": "CONTINUOUS", "PRESEASON": "SHORT", "DAYS": 115, "N": 120, "DIESEL": 50, "FYM": 2.0},
            {"WATER": "CONTINUOUS", "PRESEASON": "SHORT", "DAYS": 118, "N": 120, "DIESEL": 50, "FYM": 2.0}]


def _sfo(straw: float, cfoa: float, fym: float) -> float:
    return (1 + straw * cfoa + fym * 0.21) ** 0.59


def _expected(gwp_ch4: float, gwp_n2o: float) -> dict[str, float]:
    efc = 0.85                                                   # South Asia, Table 5.11
    sfo_b = _sfo(5, 0.19, 2.0)                                   # baseline: 5 t/ha straw (LONG), mean FYM 2 t/ha
    b_days = 116.5
    ch4_b = sum(efc * 1.0 * 1.0 * sfo_b * min(d, b_days) * 2.0 / 1000 * gwp_ch4 for d in (110, 100))
    ch4_p = (efc * 0.55 * 1.0 * _sfo(3, 0.19, 2.0) * 110 + efc * 0.71 * 1.0 * _sfo(0, 0.19, 0) * 100) * 2.0 / 1000 * gwp_ch4
    n2o = 44 / 28 * gwp_n2o
    d_n2o = ((120 - 120) + (120 - 100)) * 2.0 / 1000 * 0.003 * n2o           # N rate change at the flooded factor
    drying = (120 + 100) * 2.0 / 1000 * 0.002 * n2o                          # Eq. 25, CF_N2O 0.00314
    return {"ch4_b": ch4_b, "ch4_p": ch4_p, "d_n2o": d_n2o, "drying": drying}


def test_vm0051_matches_hand_calculation() -> None:
    res = fw.execute(Vm0051V11(), _snap(Vm0051V11, PROJECT, BASELINE))
    e = _expected(28, 265)
    fuel = (50 - 40) * 0.002886                                  # second season has no diesel record: baseline 50 - 0
    fuel += (50 - 0) * 0.002886
    er = fuel + (e["ch4_b"] - e["ch4_p"]) * 0.85 + e["d_n2o"] * 0.85 - e["drying"]
    assert _out(res, "CH4_BSL") == pytest.approx(e["ch4_b"], rel=1e-9)
    assert _out(res, "CH4_WP") == pytest.approx(e["ch4_p"], rel=1e-9)
    assert _out(res, "PE_DRYING") == pytest.approx(e["drying"], rel=1e-9)
    assert _out(res, "ER_NET") == pytest.approx(er, rel=1e-9)
    assert _out(res, "CREDITS") == math.floor(er) and res.net_value == str(math.floor(er))
    assert {r["rule_code"] for r in res.outputs} == set(Vm0051V11.rules)


def test_ag04002_profile_and_conservative_baseline() -> None:
    res = fw.execute(CctsAg04002(), _snap(CctsAg04002, PROJECT, BASELINE))
    e = _expected(29.8, 273)
    er = ((e["ch4_b"] - e["ch4_p"]) + 0 - e["drying"]) * 0.85    # N2O decrease not credited; 15 % once on the whole reduction
    assert _out(res, "D_N2O_SOIL") == 0
    assert _out(res, "ER_NET") == pytest.approx(er, rel=1e-9)
    # single drainage in any look-back year -> baseline single drainage; no drying N2O for a field already draining
    bsl = [{**BASELINE[0], "WATER": "SINGLE"}, BASELINE[1]]
    res2 = fw.execute(Vm0051V11(), _snap(Vm0051V11, PROJECT, bsl))
    assert _out(res2, "PE_DRYING") == 0 and _out(res2, "CH4_BSL") == pytest.approx(_expected(28, 265)["ch4_b"] * 0.71, rel=1e-9)


def test_country_ef_and_guards() -> None:
    res = fw.execute(Vm0051V11(), _snap(Vm0051V11, PROJECT, BASELINE, {"EFC": "1.40", "UNC": "8"}))
    assert _out(res, "EFC") == 1.40 and _out(res, "UNC") == pytest.approx(0.08)
    with pytest.raises(fw.CalculationBlocked) as blocked:
        fw.execute(Vm0051V11(), _snap(Vm0051V11, PROJECT, []))
    assert blocked.value.details.get("reason") == "BASELINE_LOOKBACK"
    bad = {"2026-10-20": {**PROJECT["2026-10-20"], "WATER": "AWD"}}
    with pytest.raises(fw.CalculationBlocked) as blocked:
        fw.execute(Vm0051V11(), _snap(Vm0051V11, bad, BASELINE))
    assert blocked.value.code == "INVALID_INPUT"
