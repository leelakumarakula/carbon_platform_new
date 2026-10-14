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
NPR = 12.0                                   # the minimum rating (NPR Procedure v5.0 §2.5.2)
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


def _blocked(snap: dict) -> fw.CalculationBlocked:
    with pytest.raises(fw.CalculationBlocked) as e:
        fw.execute(Vm0042V22(), snap)
    return e.value


def test_missing_period_record_blocks_instead_of_counting_zero() -> None:
    # baseline fertiliser records exist but this period's record is missing: read as 0 it would credit an unmonitored cut
    snap = _snapshot()
    snap["inputs"] = [r for r in snap["inputs"] if not (r["variable"] == "FSN" and r["context"].get("phase") == "PROJECT")]
    e = _blocked(snap)
    assert e.code == "MISSING_REQUIRED_INPUT" and e.details["reason"] == "PERIOD_RECORD_MISSING"
    assert e.details["missing"] == [{"farm_id": "f1", "variable": "FSN"}] and "V42_FSN" in e.message
    # a record dated outside the reporting period does not count for it
    snap = _snapshot()
    for r in snap["inputs"]:
        if r["variable"] == "DIESEL" and r["context"].get("phase") == "PROJECT":
            r["context"]["observed_on"] = "2025-09-01"
    assert _blocked(snap).details["reason"] == "PERIOD_RECORD_MISSING"
    # an explicit 0 for the period is accepted (the fixture already records rice burning as 0)
    assert _out(fw.execute(Vm0042V22(), _snapshot()), "VCU_TOTAL") == _expected()["vcus"]


def test_precipitation_is_required_and_drives_the_climate_factors() -> None:
    snap = _snapshot()
    snap["inputs"] = [r for r in snap["inputs"] if r["variable"] != "PRECIP"]
    e = _blocked(snap)
    assert e.code == "MISSING_REQUIRED_INPUT" and e.details["reason"] == "PRECIPITATION_MISSING" and e.details["strata"] == ["P1"]
    # a farm with activity records outside any stratum that has rainfall is refused too
    snap = _snapshot()
    for r in snap["inputs"]:
        if r["variable"] == "PRECIP":
            r["context"]["farm_ids"] = ["other-farm"]
    e = _blocked(snap)
    assert e.details["reason"] == "PRECIPITATION_MISSING" and e.details["farms"] == ["f1"]
    # Western Ghats rainfall (> 1000 mm): wet factors, including leaching (IPCC 2019 Tables 11.1 / 11.3)
    snap = _snapshot()
    for r in snap["inputs"]:
        if r["variable"] == "PRECIP":
            r["value"] = "2500"
    n2o = 44 / 28 * 265 / 1000
    wet = lambda n: n * (0.016 + 0.11 * 0.014 + 0.24 * 0.011) * n2o     # noqa: E731 - direct + volatilisation + leaching
    assert _out(fw.execute(Vm0042V22(), snap), "ER_N2O_FERT") == pytest.approx(wet(1100) - wet(800), rel=1e-9)


def test_risk_rating_minimum_12_and_failure_above_60() -> None:
    def with_npr(value: str) -> dict:
        snap = _snapshot()
        for r in snap["inputs"]:
            if r["variable"] == "NPR":
                r["value"] = value
        return snap
    low = fw.execute(Vm0042V22(), with_npr("8"))                 # a lower rating is raised to 12 (§2.5.2)
    assert _out(low, "NPR_RATED") == 8 and _out(low, "NPR_PCT") == 12
    assert _out(low, "VCU_TOTAL") == _expected()["vcus"]          # same buffer as the fixture's 12
    assert _out(fw.execute(Vm0042V22(), with_npr("60")), "NPR_PCT") == 60   # 60 is still acceptable
    e = _blocked(with_npr("61"))                                   # above 60 the project fails (§2.5.3)
    assert e.code == "NPR_UNACCEPTABLE"
    assert _blocked(with_npr("-1")).code == "INVALID_INPUT"
    snap = _snapshot()
    snap["inputs"] = [r for r in snap["inputs"] if r["variable"] != "NPR"]
    assert _blocked(snap).code == "MISSING_REQUIRED_INPUT"


def _with_new_rules(*records: tuple[str, str, str, str]) -> dict:
    """A snapshot of a version that carries the V42_OA_* and V42_WOODY rules, plus (variable, value, unit, kind) farm records for f1."""
    from app.calculation.modules.vm0042_v2_2 import MONITORING_RULES
    snap = _snapshot()
    snap["methodology"] = {"monitoring_rules": sorted(r["rule_code"] for r in MONITORING_RULES)}
    for var, value, unit, kind in records:
        snap["inputs"].append({"seq": len(snap["inputs"]) + 1, "variable": var, "value": value, "value_kind": kind, "unit": unit,
                               "level": "FARM", "stratum_id": None, "farm_id": "f1", "sampling_point_id": None,
                               "context": {"phase": "PROJECT", "observed_on": "2026-09-01"}})
    return snap


WOODY_NO = ("WOODY", "NO", "", "TEXT")


def test_older_versions_without_the_new_rules_behave_as_before() -> None:
    res = fw.execute(Vm0042V22(), _snapshot())               # no "monitoring_rules" in the snapshot, as for Nashik's approved version
    assert _out(res, "LK_TOTAL") == 0 and not any(r["output_code"] == "LK_OA" for r in res.outputs)
    assert _out(res, "VCU_TOTAL") == _expected()["vcus"]
    with pytest.raises(ValueError):                            # optional_rule is only for optional monitoring-record variables
        fw.Variable("X", "MONITORING_RECORD", "t", "FARM", rule_code="R", optional_rule=True)


def test_imported_compost_leakage_eq_33() -> None:
    # 50 t of bought compost at 15 % carbon: 50 x 0.15 x 0.12 x 44/12 = 3.3 t CO2e, deducted from the credits
    res = fw.execute(Vm0042V22(), _with_new_rules(WOODY_NO, ("OA_MASS", "50", "t", "NUMBER"), ("OA_CC", "0.15", "t C/t", "NUMBER")))
    assert _out(res, "LK_OA") == pytest.approx(3.3, rel=1e-12) and _out(res, "LK_TOTAL") == pytest.approx(3.3, rel=1e-12)
    assert _out(res, "VCU_TOTAL") == math.floor(_expected()["total"] - 3.3)
    # estate-made compost (exempt) is not recorded as imported: 0 t gives no leakage and needs no carbon content
    res = fw.execute(Vm0042V22(), _with_new_rules(WOODY_NO, ("OA_MASS", "0", "t", "NUMBER")))
    assert _out(res, "LK_OA") == 0 and _out(res, "VCU_TOTAL") == _expected()["vcus"]
    # baseline-phase (look-back) amendments are not project imports
    snap = _with_new_rules(WOODY_NO, ("OA_MASS", "50", "t", "NUMBER"))
    snap["inputs"][-1]["context"]["phase"] = "BASELINE"
    assert _out(fw.execute(Vm0042V22(), snap), "LK_OA") == 0
    e = _blocked(_with_new_rules(WOODY_NO, ("OA_MASS", "50", "t", "NUMBER")))
    assert e.code == "MISSING_REQUIRED_INPUT" and e.details["reason"] == "OA_CARBON_MISSING"
    e = _blocked(_with_new_rules(WOODY_NO, ("OA_MASS", "50", "t", "NUMBER"), ("OA_CC", "0.15", "t C/t", "NUMBER"),
                                 ("OA_CC", "0.2", "t C/t", "NUMBER")))
    assert e.details["reason"] == "OA_CARBON_DUPLICATE"
    e = _blocked(_with_new_rules(WOODY_NO, ("OA_MASS", "50", "t", "NUMBER"), ("OA_CC", "15", "t C/t", "NUMBER")))   # 15 % typed as 15
    assert e.code == "INVALID_INPUT" and e.details["reason"] == "OA_CARBON_OUT_OF_RANGE"


def _with_fon(snap: dict, look_back: str, period: str) -> dict:
    """Organic fertiliser N on farm f1: one look-back year and the reporting period (one year: 2026-06-01..2027-05-31)."""
    for phase, observed, value in (("BASELINE", "2022-06-01", look_back), ("PROJECT", "2026-09-01", period)):
        snap["inputs"].append({"seq": len(snap["inputs"]) + 1, "variable": "FON", "value": value, "value_kind": "NUMBER", "unit": "kg N",
                               "level": "FARM", "stratum_id": None, "farm_id": "f1", "sampling_point_id": None,
                               "context": {"phase": phase, "observed_on": observed}})
    return snap


def test_organic_n_increase_needs_an_imported_amendment_declaration() -> None:
    # more organic N than in the look-back (900 vs 500 kg N/yr) and no V42_OA_IMPORTED record: a forgotten compost entry is refused
    e = _blocked(_with_fon(_with_new_rules(WOODY_NO), "500", "900"))
    assert e.code == "MISSING_REQUIRED_INPUT" and e.details["reason"] == "OA_DECLARATION_MISSING" and e.details["farms"] == ["f1"]
    assert e.details["variable"] == "OA_MASS" and "V42_OA_IMPORTED" in e.message
    # 0 t imported: estate-made compost (exempt) — accepted, no leakage
    res = fw.execute(Vm0042V22(), _with_fon(_with_new_rules(WOODY_NO, ("OA_MASS", "0", "t", "NUMBER")), "500", "900"))
    assert _out(res, "LK_OA") == 0
    # bought compost declared: Eq. 33 leakage as usual
    res = fw.execute(Vm0042V22(), _with_fon(_with_new_rules(WOODY_NO, ("OA_MASS", "50", "t", "NUMBER"), ("OA_CC", "0.15", "t C/t", "NUMBER")),
                                            "500", "900"))
    assert _out(res, "LK_OA") == pytest.approx(3.3, rel=1e-12)
    # no increase (same N as the look-back): no declaration needed
    assert _out(fw.execute(Vm0042V22(), _with_fon(_with_new_rules(WOODY_NO), "500", "500")), "LK_OA") == 0
    # a declaration dated outside the reporting period does not count for it
    snap = _with_fon(_with_new_rules(WOODY_NO, ("OA_MASS", "0", "t", "NUMBER")), "500", "900")
    next(r for r in snap["inputs"] if r["variable"] == "OA_MASS")["context"]["observed_on"] = "2025-09-01"
    assert _blocked(snap).details["reason"] == "OA_DECLARATION_MISSING"
    # versions without the V42_OA_* rules are unchanged (8.4.1 not applicable there)
    assert _out(fw.execute(Vm0042V22(), _with_fon(_snapshot(), "500", "900")), "LK_TOTAL") == 0


def test_woody_biomass_declaration_protects_shade_trees() -> None:
    assert _out(fw.execute(Vm0042V22(), _with_new_rules(("WOODY", "NONE", "", "TEXT"))), "VCU_TOTAL") == _expected()["vcus"]
    e = _blocked(_with_new_rules())                                            # no declaration for the project farm
    assert e.code == "MISSING_REQUIRED_INPUT" and e.details["reason"] == "WOODY_DECLARATION_MISSING" and e.details["farms"] == ["f1"]
    e = _blocked(_with_new_rules(("WOODY", "yes", "", "TEXT")))               # shade trees cut / coffee uprooted
    assert e.code == "WOODY_BIOMASS_REMOVED" and e.details["farms"] == ["f1"]
    assert _blocked(_with_new_rules(("WOODY", "maybe", "", "TEXT"))).code == "INVALID_INPUT"


def test_three_increments_use_cubic_spline() -> None:
    from app.calculation.library import esm
    assert esm.method_for(2) == esm.LINEAR and esm.method_for(3) == esm.SPLINE
