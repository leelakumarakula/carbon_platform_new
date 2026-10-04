"""GS 403 v2.1 A/R module against a hand calculation: stem volume per plot -> MU mean, inventory precision deduction above 20 %
(§3.11.5), GS conversion (§3.9-3.10), long-term cap, one-off baseline / leakage / burning, fertiliser, cumulative issuance, the
20 % buffer and the Paris-alignment gate for 2026+ vintages."""
import math
from decimal import Decimal

import pytest

from app.calculation import framework as fw
from app.calculation.library import stats
from app.calculation.modules.gs_ar_403 import Gs403V21

PLOT_HA = 0.04
MU = {"M1": (40.0, [4.4, 3.9, 4.8, 4.1, 3.6]), "M2": (25.0, [2.0, 3.1, 1.4, 2.6])}     # (area ha, plot stem volume m3)


def _snap(start: str = "2021-01-01", end: str = "2025-12-31", extra: list[tuple] | None = None) -> dict:
    rows: list[dict] = []

    def add(var: str, value: object, unit: str, level: str, ctx: dict | None = None, kind: str = "NUMBER", farm: str | None = None) -> None:
        rows.append({"seq": len(rows) + 1, "variable": var, "value": str(value), "value_kind": kind, "unit": unit, "level": level,
                     "stratum_id": None, "farm_id": farm, "sampling_point_id": None, "context": ctx or {}})

    add("PLOT_AREA", PLOT_HA, "ha", "PROJECT")
    for rec, (area, vols) in MU.items():
        add("AREA", area, "ha", "STRATUM", {"stratum_role": "PROJECT", "stratum_record_id": rec})
        for v in vols:
            add("PLOT_VOL", v, "m3", "SAMPLING_POINT", {"stratum_record_id": rec})
    add("WD", 0.55, "t d.m./m3", "STRATUM", {"stratum_record_id": "M1"})
    add("CR_LT", 150, "t CO2/ha", "STRATUM", {"stratum_record_id": "M1"})
    add("BSL", 300, "t CO2e", "PROJECT")
    add("BURNING", "YES", "", "PROJECT", kind="TEXT")
    add("LK", 120, "t CO2e", "PROJECT")
    add("FERT_N", 2000, "kg N", "FARM", farm="f1", ctx={"phase": "PROJECT", "observed_on": "2024-03-01"})
    add("ISSUED_PRIOR", 500, "t CO2e", "PROJECT")
    for var, value, unit, kind in extra or []:
        add(var, value, unit, "PROJECT", kind=kind)
    for c in Gs403V21.constants:
        add(c.code, fw.decimal_text(Decimal(c.value)), c.unit, "PROJECT")
    return {"reporting_period": {"start": start, "end": end}, "inputs": rows}


def _out(res: fw.ExecutionResult, code: str) -> float:
    return float(next(r["value"] for r in res.outputs if r["output_code"] == code))


def _mu_stock(vols: list[float], wd: float) -> tuple[float, float]:
    v = [x / PLOT_HA for x in vols]
    n = len(v)
    m = sum(v) / n
    se = math.sqrt(sum((x - m) ** 2 for x in v) / (n - 1) / n)
    err = float(stats.t_quantile(0.95, Decimal(n - 1))) * se / m
    adj = m * (1 - max(0.0, err - 0.20))
    return adj * 1.1 * wd * 1.2 * 0.47 * 44 / 12, err


def test_gs403_matches_hand_calculation() -> None:
    res = fw.execute(Gs403V21(), _snap())
    s1, _ = _mu_stock(MU["M1"][1], 0.55)
    s2, e2 = _mu_stock(MU["M2"][1], 0.3)
    stock = min(s1, 150) * 40 + s2 * 25
    net = stock - 300 - 120 - 30 - 2000 * 0.005
    issuable = max(0.0, net - 500)
    vers = math.floor(issuable * 0.8)
    assert e2 > 0.20                                                     # M2 is imprecise: the excess error is deducted
    assert _out(res, "CREDITABLE_M2") == pytest.approx(s2, rel=1e-9)
    assert _out(res, "NET_CUMULATIVE") == pytest.approx(net, rel=1e-9)
    assert _out(res, "PAA_BLOCKED_SHARE") == 0
    assert _out(res, "GSVER_PROJECT") == vers and res.net_value == str(vers)
    assert {r["rule_code"] for r in res.outputs} == set(Gs403V21.rules)


def test_paris_alignment_gate() -> None:
    res = fw.execute(Gs403V21(), _snap("2025-07-01", "2026-06-30"))
    assert _out(res, "PAA_BLOCKED_SHARE") == pytest.approx(181 / 365, rel=1e-9)
    ok = fw.execute(Gs403V21(), _snap("2025-07-01", "2026-06-30", [("PAA", "YES", "", "TEXT")]))
    assert _out(ok, "PAA_BLOCKED_SHARE") == 0 and _out(ok, "GSVER_PROJECT") >= _out(res, "GSVER_PROJECT")
