"""VM0044 v1.2 biochar module on synthetic frozen snapshots against hand calculations: Eqs. 1-3/6/7/9, Table 3 (temperature) and
Table 4 (feedstock) defaults, H:C_org gate, transport leakage, Eq. 15 and whole VCUs."""
import math
from decimal import Decimal

import pytest

from app.calculation import framework as fw
from app.calculation.modules.vm0044_v1_2 import Vm0044V12


def _snap(**over: object) -> dict:
    data: dict[str, object] = {"PRODUCED": ["120"], "USED_SOIL": ["70", "30"], "USED_NONSOIL": ["10"], "FCP": ["0.72"], "HC_RATIO": ["0.35", "0.41"],
                               "TEMP": ["620"], "TECH": "HIGH", "PE_PRETREAT": ["4.5"], "PE_AUX": ["1.5"], "PE_PROCESSING": ["0.8"],
                               "LE_TRANSPORT": ["2.2"]}
    data.update(over)
    rows: list[dict] = []
    units = {"PRODUCED": "t", "USED_SOIL": "t", "USED_NONSOIL": "t", "FCP": "fraction", "HC_RATIO": "ratio", "TEMP": "degC", "FE": "t CH4/t",
             "PE_PRETREAT": "t CO2e", "PE_AUX": "t CO2e", "PE_PROCESSING": "t CO2e", "LE_TRANSPORT": "t CO2e"}
    for var, val in data.items():
        if val is None:
            continue
        for i, v in enumerate([val] if isinstance(val, str) else list(val)):  # type: ignore[call-overload]
            kind = "TEXT" if var in ("TECH", "FEEDSTOCK", "PROCESS") else "NUMBER"
            rows.append({"seq": len(rows) + 1, "variable": var, "value": v, "value_kind": kind, "unit": units.get(var, ""), "level": "PROJECT",
                         "stratum_id": None, "farm_id": None, "sampling_point_id": None,
                         "context": {"phase": "PROJECT", "observed_on": f"2026-0{i + 1}-15"}})
    for c in Vm0044V12.constants:
        rows.append({"seq": len(rows) + 1, "variable": c.code, "value": fw.decimal_text(Decimal(c.value)), "value_kind": "NUMBER",
                     "unit": c.unit, "level": "PROJECT", "stratum_id": None, "farm_id": None, "sampling_point_id": None, "context": {}})
    return {"reporting_period": {"start": "2026-01-01", "end": "2026-12-31"}, "inputs": rows}


def _out(res: fw.ExecutionResult, code: str) -> float:
    return float(next(r["value"] for r in res.outputs if r["output_code"] == code))


def test_high_technology_matches_hand_calculation() -> None:
    res = fw.execute(Vm0044V12(), _snap())
    used = 110.0
    cc = used * 0.72 * 0.89                                   # Eq. 2, Table 3 > 600 degC
    pe_ps = (4.5 + 0 + 1.5) * used / 120                      # Eq. 3, P_EP = 0 (high tech)
    er = cc * 44 / 12 - pe_ps - 0.8 - 2.2                     # Eqs. 1, 15
    assert _out(res, "CC") == pytest.approx(cc) and _out(res, "PR_DE") == 0.89
    assert _out(res, "PE_PS") == pytest.approx(pe_ps) and _out(res, "P_EP") == 0
    assert _out(res, "ER_NET") == pytest.approx(er)
    assert _out(res, "VCU_TOTAL") == math.floor(er) and res.net_value == str(math.floor(er))
    assert {r["rule_code"] for r in res.outputs} == set(Vm0044V12.rules)


def test_low_technology_uses_table_defaults_and_kiln_methane() -> None:
    res = fw.execute(Vm0044V12(), _snap(TECH="LOW", FCP=None, TEMP=None, FEEDSTOCK="RICE", PROCESS="PYROLYSIS", PE_AUX=None,
                                        USED_NONSOIL=None))   # low technology: soil use only (condition 11)
    used = 100.0
    cc = used * 0.49 * 0.56                                   # Table 4 rice / pyrolysis; temperature unknown
    p_ep = 0.049 * 28 * 120                                   # Eq. 9 on the biochar produced, default F_e (A8)
    pe_ps = (4.5 + p_ep) * used / 120                         # Eq. 7: the used share, CH4 of the used biochar counted once
    er = cc * 44 / 12 - pe_ps - 0.8 - 2.2
    assert _out(res, "F_CP") == 0.49 and _out(res, "PR_DE") == 0.56
    assert _out(res, "P_EP") == pytest.approx(p_ep) and _out(res, "ER_NET") == pytest.approx(er)
    assert _out(res, "VCU_TOTAL") == max(0, math.floor(er))
    # temperature band 450-600 -> 0.80, exactly 450 -> 0.65 (overlap resolved conservatively)
    assert _out(fw.execute(Vm0044V12(), _snap(TEMP=["500"])), "PR_DE") == 0.80
    assert _out(fw.execute(Vm0044V12(), _snap(TEMP=["450"])), "PR_DE") == 0.65


def test_guards() -> None:
    for over, code in (({"HC_RATIO": ["0.35", "0.75"]}, "INELIGIBLE_BIOCHAR"), ({"FCP": None}, "MISSING_REQUIRED_INPUT"),
                       ({"USED_SOIL": ["200"]}, "INVALID_INPUT"), ({"TECH": "MEDIUM"}, "INVALID_INPUT")):
        with pytest.raises(fw.CalculationBlocked) as e:
            fw.execute(Vm0044V12(), _snap(**over))
        assert e.value.code == code
    # non-soil only: the H:C_org gate does not apply
    res = fw.execute(Vm0044V12(), _snap(USED_SOIL=None, HC_RATIO=["0.9"]))
    assert _out(res, "M_USED") == 10


# ---------------------------------------------------------------- fixes 29/10
def test_kiln_methane_of_the_used_biochar_is_counted_once_in_full() -> None:
    res = fw.execute(Vm0044V12(), _snap(TECH="LOW", FCP=["0.70"], USED_NONSOIL=None, PE_PRETREAT=None, PE_AUX=None))
    assert _out(res, "PE_PS") == pytest.approx(0.049 * 28 * 100)          # F_e x GWP x M_used, not x M_used^2 / M_produced


def test_soil_use_needs_hc_ratio_and_non_soil_needs_high_technology() -> None:
    for over, code, reason in (({"HC_RATIO": None}, "MISSING_REQUIRED_INPUT", "HC_RATIO_MISSING"),
                               ({"TECH": "LOW"}, "INELIGIBLE_BIOCHAR", "NONSOIL_LOW_TECH")):
        with pytest.raises(fw.CalculationBlocked) as e:
            fw.execute(Vm0044V12(), _snap(**over))
        assert e.value.code == code and e.value.details["reason"] == reason


def test_fcp_and_temperature_are_mass_weighted() -> None:
    # batches of 100 t (Jan) and 20 t (Feb); F_Cp 0.80 / 0.20 and 620 / 380 degC
    snap = _snap(PRODUCED=["100", "20"], FCP=["0.80", "0.20"], TEMP=["620", "380"])
    res = fw.execute(Vm0044V12(), snap)
    assert _out(res, "F_CP") == pytest.approx((0.80 * 100 + 0.20 * 20) / 120)           # 0.70, not the simple mean 0.50
    assert _out(res, "PR_DE") == 0.80                                               # 580 degC weighted (simple mean 500 -> also 0.80)
    snap = _snap(PRODUCED=["20", "100"], TEMP=["620", "400"], USED_SOIL=["70", "30"])
    assert _out(fw.execute(Vm0044V12(), snap), "PR_DE") == 0.65                      # 436.7 degC weighted; the simple mean 510 gave 0.80
    # values that cannot be matched to one production batch are refused
    with pytest.raises(fw.CalculationBlocked) as e:
        fw.execute(Vm0044V12(), _snap(PRODUCED=["120"], FCP=["0.80", "0.20"]))
    assert e.value.details["reason"] == "NOT_MASS_WEIGHTABLE"
