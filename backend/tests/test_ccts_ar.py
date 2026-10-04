"""CCTS BM FR05.002 / FR05.001 v1.0 (BM-T-AR-0004) on synthetic snapshots against hand calculations: per-plot root-shoot ratio,
stratified stock and its 90 % uncertainty (Eqs. 12-17), change of two independent estimates (Eqs. 1-2), Appendix 2 discount,
shrubs (Eqs. 26-27), the FR05.001 SOC default (Eq. 4) and the lCCC."""
import math
from decimal import Decimal

import pytest

from app.calculation import framework as fw
from app.calculation.library import ar_cdm, stats
from app.calculation.modules.ccts_ar import CctsFr05001, CctsFr05002

PLOT_HA = 0.05
STRATA = {"S1": 30.0, "S2": 20.0}
CUR = {"S1": [4.1, 3.6, 4.8, 4.0], "S2": [2.9, 3.3, 2.6]}          # t d.m. above ground per plot
PREV = {"S1": [1.9, 1.6, 2.2, 1.8], "S2": [1.2, 1.5, 1.1]}


def _snap(prev: dict | None = PREV, extra: list[tuple] | None = None) -> dict:
    rows: list[dict] = []

    def add(var: str, value: object, unit: str, level: str, ctx: dict | None = None, point: str | None = None) -> None:
        rows.append({"seq": len(rows) + 1, "variable": var, "value": str(value), "value_kind": "NUMBER", "unit": unit, "level": level,
                     "stratum_id": None, "farm_id": None, "sampling_point_id": point, "context": ctx or {}})

    for period, plots, sfx in (("CURRENT", CUR, ""), ("PREVIOUS", prev, "_T0")):
        if plots is None:
            continue
        add("PLOT_AREA" + sfx, PLOT_HA, "ha", "PROJECT")
        for s, values in plots.items():
            add("AREA" + sfx, STRATA[s], "ha", "STRATUM", {"stratum_role": "PROJECT", "stratum_record_id": s})
            for i, v in enumerate(values):
                add("PLOT_AGB" + sfx, v, "t d.m.", "SAMPLING_POINT", {"stratum_record_id": s}, f"{period}{s}{i}")
    for var, value, unit, level, ctx in extra or []:
        add(var, value, unit, level, ctx)
    for c in CctsFr05001.constants:
        add(c.code, fw.decimal_text(Decimal(c.value)), c.unit, "PROJECT")
    return {"reporting_period": {"start": "2027-01-01", "end": "2029-12-31"}, "inputs": rows}


def _out(res: fw.ExecutionResult, code: str) -> float:
    return float(next(r["value"] for r in res.outputs if r["output_code"] == code))


def _stock(plots: dict) -> tuple[float, float]:
    area = sum(STRATA.values())
    mean, var, n = 0.0, 0.0, 0
    for s, values in plots.items():
        b = [v / PLOT_HA for v in values]
        tot = [x * (1 + math.exp(-1.085 + 0.9256 * math.log(x)) / x) for x in b]     # Mokany root-shoot per plot
        w = STRATA[s] / area
        m = sum(tot) / len(tot)
        mean += w * m
        var += w * w * (sum((x - m) ** 2 for x in tot) / (len(tot) - 1)) / len(tot)
        n += len(tot)
    t = float(stats.t_quantile(0.95, Decimal(n - len(plots))))
    return 44 / 12 * 0.47 * area * mean, t * math.sqrt(var) / mean


def _discounted(c1: float, u1: float, c2: float, u2: float) -> float:
    d = c2 - c1
    u = math.sqrt((u1 * c1) ** 2 + (u2 * c2) ** 2) / abs(d)
    df = 0 if u <= 0.10 else 0.25 if u <= 0.15 else 0.5 if u <= 0.20 else 0.75 if u <= 0.30 else 1.0
    return d - df * u * abs(d)


def test_fr05002_matches_hand_calculation() -> None:
    extra: list[tuple] = [("GHG_E", 3.5, "t CO2e", "PROJECT", {}), ("LK", 2.0, "t CO2e", "PROJECT", {})]
    res = fw.execute(CctsFr05002(), _snap(extra=extra))
    c2, u2 = _stock(CUR)
    c1, u1 = _stock(PREV)
    net = _discounted(c1, u1, c2, u2) - 3.5 - 0 - 2.0
    assert _out(res, "C_T2") == pytest.approx(c2, rel=1e-9) and _out(res, "U_T2") == pytest.approx(u2, rel=1e-6)
    assert _out(res, "C_T1") == pytest.approx(c1, rel=1e-9)
    assert _out(res, "DC_AR") == pytest.approx(net, rel=1e-6)
    assert _out(res, "LCCC") == math.floor(net) and res.net_value == str(math.floor(net))
    assert {r["rule_code"] for r in res.outputs} == set(CctsFr05002.rules)


def test_first_verification_shrubs_and_mangrove_soc() -> None:
    plant = [("PLANT_YEAR", 2026, "year", "STRATUM", {"stratum_record_id": "S1"}),
             ("SHRUB_CC", 0.30, "fraction", "STRATUM", {"stratum_record_id": "S2"}), ("SHRUB_CC", 0.03, "fraction", "STRATUM", {"stratum_record_id": "S1"}),
             ("B_FOREST", 120, "t d.m./ha", "PROJECT", {}), ("BSL_STOCK", 40, "t CO2e", "PROJECT", {})]
    res = fw.execute(CctsFr05001(), _snap(prev=None, extra=plant))
    c2, u2 = _stock(CUR)
    shrubs = 44 / 12 * 0.47 * 1.40 * (20 * 0.10 * 120 * 0.30)          # S1 below 5 % cover counts as 0
    soc = 44 / 12 * 30 * 0.50 * 3                                       # 2027-2029, planted 2026
    total2 = c2 + shrubs
    net = _discounted(40, 0, total2, u2 * c2 / total2) + soc
    assert _out(res, "C_SHRUB_T2") == pytest.approx(shrubs, rel=1e-12) and _out(res, "C_T1") == 40
    assert _out(res, "DSOC") == pytest.approx(soc, rel=1e-12)
    # stratified uncertainty is relative to trees; the change uses the absolute tree uncertainty (u2 x C_TREE)
    assert _out(res, "LCCC") == math.floor(_out(res, "DC_AR")) and _out(res, "DC_AR") > 0
    assert abs(_out(res, "DC_AR") - net) / net < 0.05


def test_discount_bands_and_guards() -> None:
    assert ar_cdm.discount_fraction(Decimal("0.10")) == 0 and ar_cdm.discount_fraction(Decimal("0.15")) == Decimal("0.25")
    assert ar_cdm.discount_fraction(Decimal("0.31")) == 1
    assert ar_cdm.conservative(Decimal(60), Decimal("0.15")) == Decimal("57.75")             # Appendix 2 worked example
    with pytest.raises(fw.CalculationBlocked) as e:
        fw.execute(CctsFr05002(), _snap(prev=None) | {"inputs": [r for r in _snap(prev=None)["inputs"] if r["variable"] != "PLOT_AREA"]})
    assert e.value.code == "MISSING_REQUIRED_INPUT"
