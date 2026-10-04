"""VM0042 v2.2 module (QA2 SOC + QA3 emissions) on a synthetic frozen snapshot, checked against an independent hand calculation
written out below in plain float arithmetic: equivalent mineral soil mass with linear interpolation (2 depth increments), the
control-site reference mass to 30 cm, stratum means, Eqs. 46/47, the Approach 2 uncertainty (Eqs. 70/71/74, Welch–Satterthwaite,
one-sided 66.67 % t), Eqs. 44/45, fertiliser N2O (dry climate), diesel, residue burning, buffer (Eqs. 75/76) and VCUs."""
import math
from decimal import Decimal

import pytest

from app.calculation import framework as fw
from app.calculation.library import stats
from app.calculation.modules.vm0042_v2_2 import Vm0042V22

D_MM, CORES = 21.5, 4
AREA_HA = 100.0
NPR = 10.0
# (stratum record, role) -> campaign -> list of profiles; a profile = [(top, bottom, fine mass g, OC g/kg), ...]
DATA = {
    ("P1", "PROJECT"): {"PREVIOUS": [[(0, 30, 280.0, 12.0), (30, 50, 200.0, 7.0)], [(0, 30, 290.0, 11.0), (30, 50, 210.0, 6.5)]],
                        "CURRENT": [[(0, 30, 282.0, 13.5), (30, 50, 201.0, 7.4)], [(0, 30, 288.0, 12.6), (30, 50, 209.0, 6.9)]]},
    **{(c, "CONTROL"): {"PREVIOUS": [[(0, 30, 285.0, 11.5), (30, 50, 205.0, 6.8)], [(0, 30, 286.0, 11.7), (30, 50, 204.0, 6.6)]],
                        "CURRENT": [[(0, 30, 285.0, 11.4), (30, 50, 205.0, 6.8)], [(0, 30, 287.0, 11.6), (30, 50, 203.0, 6.5)]]}
       for c in ("C1", "C2", "C3")},
}


def _snapshot() -> dict:
    rows: list[dict] = []

    def add(var: str, value: str, unit: str, level: str, kind: str = "NUMBER", farm: str | None = None, ctx: dict | None = None) -> None:
        rows.append({"seq": len(rows) + 1, "variable": var, "value": value, "value_kind": kind, "unit": unit, "level": level, "stratum_id": None,
                     "farm_id": farm, "sampling_point_id": None, "context": ctx or {}})

    sample = 0
    for (rec, role), campaigns in DATA.items():
        for period, profiles in campaigns.items():
            sfx = "_T" if period == "CURRENT" else "_T0"
            for i, prof in enumerate(profiles):
                fc = f"{rec}-{period}-{i}"
                for top, bottom, mass, oc in prof:
                    sample += 1
                    ctx = {"period": period, "depth_top_cm": str(top), "depth_bottom_cm": str(bottom), "probe_diameter_mm": str(D_MM),
                           "cores_count": CORES, "root_sample_id": f"s{sample}", "field_collection_id": fc, "stratum_role": role,
                           "stratum_record_id": rec, "linked_stratum_record_ids": ["P1"] if role == "CONTROL" else []}
                    add("OC" + sfx, str(oc), "g/kg", "SAMPLING_POINT", ctx=ctx)
                    add("MASS" + sfx, str(mass), "g", "SAMPLING_POINT", ctx=ctx)
    add("AREA", str(AREA_HA), "ha", "STRATUM", ctx={"stratum_role": "PROJECT", "stratum_record_id": "P1", "farm_ids": ["f1"]})
    for c in ("C1", "C2", "C3"):
        add("AREA", "40", "ha", "STRATUM", ctx={"stratum_role": "CONTROL", "stratum_record_id": c})
    add("PRECIP", "800", "mm", "STRATUM", ctx={"stratum_role": "PROJECT", "stratum_record_id": "P1", "farm_ids": ["f1"]})
    for var, unit, bsl, prj in (("FSN", "kg N", (1000, 1200), 800), ("DIESEL", "L", (6000, 6000), 3500),
                                ("BURN_RICE", "kg d.m.", (20000, 22000), 0)):
        for year, value in zip(("2021-06-01", "2022-06-01"), bsl, strict=True):
            add(var, str(value), unit, "FARM", farm="f1", ctx={"phase": "BASELINE", "observed_on": year})
        add(var, str(prj), unit, "FARM", farm="f1", ctx={"phase": "PROJECT", "observed_on": "2026-09-01"})
    add("NPR", str(NPR), "%", "PROJECT", ctx={"phase": "MONITORING"})
    for c in Vm0042V22.constants:
        add(c.code, fw.decimal_text(Decimal(c.value)), c.unit, "PROJECT")
    return {"reporting_period": {"start": "2026-06-01", "end": "2027-05-31"},
            "previous_period": {"start": "2025-06-01", "end": "2026-05-31"}, "inputs": rows}


# ---------------------------------------------------------------- independent hand calculation (floats)
def _profile(prof: list[tuple]) -> tuple[list[float], list[float], list[float]]:
    """cumulative mineral mass, cumulative OC (Mg/ha) and depth, starting at the surface."""
    area_mm2 = math.pi * (D_MM / 2) ** 2 * CORES
    mass, oc, depth = [0.0], [0.0], [0.0]
    for _, bottom, m, c in prof:
        fine = m / area_mm2 * 10_000                     # VM0042 Eq. 3 bracket, Mg/ha
        mineral = fine * (1 - c / 1000 / 0.58)           # minus SOM (SOC / 0.58)
        mass.append(mass[-1] + mineral)
        oc.append(oc[-1] + fine * c / 1000)
        depth.append(bottom)
    return mass, oc, depth


def _lin(x: list[float], y: list[float], t: float) -> float:
    i = max(k for k in range(len(x) - 1) if x[k] <= t) if t < x[-1] else len(x) - 2
    return y[i] + (y[i + 1] - y[i]) * (t - x[i]) / (x[i + 1] - x[i])


def _expected() -> dict[str, float]:
    controls = [p for (rec, role), c in DATA.items() if role == "CONTROL" for p in c["PREVIOUS"]]
    ref = sum(_lin(_profile(p)[2], _profile(p)[0], 30.0) for p in controls) / len(controls)   # mean mineral mass to 30 cm
    soc = {}
    for scenario, keys in (("P", [("P1", "PROJECT")]), ("B", [("C1", "CONTROL"), ("C2", "CONTROL"), ("C3", "CONTROL")])):
        for period in ("PREVIOUS", "CURRENT"):
            vals = [_lin(_profile(p)[0], _profile(p)[1], ref) for k in keys for p in DATA[k][period]]
            soc[(scenario, period)] = vals
    mean = {k: sum(v) / len(v) for k, v in soc.items()}
    c2 = 44 / 12
    wp = (mean[("P", "CURRENT")] - mean[("P", "PREVIOUS")]) * AREA_HA * c2
    bsl = (mean[("B", "CURRENT")] - mean[("B", "PREVIOUS")]) * AREA_HA * c2
    comps = []
    for v in soc.values():
        n = len(v)
        m = sum(v) / n
        var = sum((x - m) ** 2 for x in v) / (n - 1)
        comps.append((c2 * c2 * var / n, n))                     # weight (A_h / A)^2 = 1 with one project stratum
    variance = sum(c for c, _ in comps)
    df = sum(c for c, _ in comps) ** 2 / sum(c * c / (n - 1) for c, n in comps)
    t = float(stats.t_quantile(2 / 3, Decimal(str(df))))
    unc = min(100.0, t * math.sqrt(variance) / abs((wp - bsl) / AREA_HA) * 100)
    sign = 1 if wp - bsl >= 0 else -1
    wp_adj, bsl_adj = wp * (1 - unc / 100 * sign), bsl * (1 - unc / 100 * sign)
    # emissions: dry climate (800 mm), no irrigation -> no leaching; 1 year (365 days)
    n2o = 44 / 28 * 265 / 1000
    fert = lambda n: n * 0.005 * n2o + n * 0.11 * 0.005 * n2o     # noqa: E731 - direct + volatilisation
    burn = lambda kg: kg * 0.80 * (2.7 / 1e6 * 28 + 0.07 / 1e6 * 265)  # noqa: E731
    er = (fert(1100) - fert(800)) + (6000 * 0.002886 - 3500 * 0.002886) + (burn(21000) - burn(0))
    i_wp = 1 if wp_adj > 0 else 0
    mx = max(0, wp_adj) - max(0, bsl_adj)
    mn = min(0, wp_adj) - min(0, bsl_adj)
    er_total = er + mn + (1 - i_wp) * mx
    cr = i_wp * mx
    bu_er = max(0.0, (i_wp * mn + (1 - i_wp) * (mn + mx)) * NPR / 100)
    bu_cr = max(0.0, i_wp * mx * NPR / 100)
    total = (er_total - bu_er) + (cr - bu_cr)
    return {"ref": ref, "wp": wp, "bsl": bsl, "unc": unc, "er_sources": er, "cr": cr, "bu_cr": bu_cr, "total": total,
            "vcus": math.floor(max(0.0, total))}


def _out(result: fw.ExecutionResult, code: str) -> float:
    return float(next(r["value"] for r in result.outputs if r["output_code"] == code))


def test_vm0042_module_matches_hand_calculation() -> None:
    result = fw.execute(Vm0042V22(), _snapshot())
    e = _expected()
    assert _out(result, "REF_MASS_P1") == pytest.approx(e["ref"], rel=1e-9)
    assert _out(result, "DCO2_SOIL_WP") == pytest.approx(e["wp"], rel=1e-9)
    assert _out(result, "DCO2_SOIL_BSL") == pytest.approx(e["bsl"], rel=1e-9, abs=1e-9)
    assert _out(result, "UNC_PCT") == pytest.approx(e["unc"], rel=1e-6)
    assert _out(result, "ER_SOURCES") == pytest.approx(e["er_sources"], rel=1e-9)
    assert _out(result, "CR_T") == pytest.approx(e["cr"], rel=1e-6)
    assert _out(result, "BUFFER_CR") == pytest.approx(e["bu_cr"], rel=1e-6)
    assert _out(result, "VCU_TOTAL") == e["vcus"] and result.net_value == str(e["vcus"])
    assert e["wp"] > e["bsl"] and e["vcus"] > 0          # the project gained carbon relative to the control sites
    # every output cites a VM0042 rule and has lineage; the run is reproducible
    assert {r["rule_code"] for r in result.outputs} == set(Vm0042V22.rules)
    assert all(r["inputs"] or r["outputs"] for r in result.outputs)
    assert fw.execute(Vm0042V22(), _snapshot()).output_sha256 == result.output_sha256


def test_reversal_and_guards() -> None:
    snap = _snapshot()
    # project soil loses carbon -> negative benefit: no VCUs and a reported reversal (Q3), buffer never negative
    for r in snap["inputs"]:
        if r["variable"] == "OC_T" and r["context"]["stratum_role"] == "PROJECT":
            r["value"] = str(Decimal(r["value"]) / 2)
    res = fw.execute(Vm0042V22(), snap)
    assert _out(res, "VCU_TOTAL") == 0 and _out(res, "REVERSAL") > 0
    assert _out(res, "BUFFER_ER") >= 0 and _out(res, "BUFFER_CR") >= 0
    # fewer than 3 control sites is refused (VM0042 §8.2 QA2)
    snap = _snapshot()
    snap["inputs"] = [r for r in snap["inputs"] if r["context"].get("stratum_record_id") != "C3"]
    with pytest.raises(fw.CalculationBlocked) as e:
        fw.execute(Vm0042V22(), snap)
    assert e.value.code == "CONTROL_SITES_REQUIRED"
    # missing probe diameter / cores is refused (Eq. 3)
    snap = _snapshot()
    for r in snap["inputs"]:
        if r["variable"].startswith("MASS"):
            r["context"]["cores_count"] = None
    with pytest.raises(fw.CalculationBlocked) as e:
        fw.execute(Vm0042V22(), snap)
    assert e.value.code == "MISSING_REQUIRED_INPUT"


def test_three_increments_use_cubic_spline() -> None:
    from app.calculation.library import esm
    assert esm.method_for(2) == esm.LINEAR and esm.method_for(3) == esm.SPLINE
