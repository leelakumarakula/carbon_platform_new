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
    res = fw.execute(Vm0044V12(), _snap(TECH="LOW", FCP=None, TEMP=None, FEEDSTOCK="RICE", PROCESS="PYROLYSIS", PE_AUX=None))
    used = 110.0
    cc = used * 0.49 * 0.56                                   # Table 4 rice / pyrolysis; temperature unknown
    p_ep = 0.049 * 28 * used                                  # Eq. 9, default F_e
    pe_ps = (4.5 + p_ep) * used / 120
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
