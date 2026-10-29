"""Fixes 29/10 (calculation engine, reports): module exceptions never leak their text, the report carries the module's assumptions,
and the PDF writer spells out symbols that Windows-1252 cannot encode. Pure tests (no database)."""
import logging
from decimal import Decimal
from typing import Any

import pytest

from app.calculation import framework as fw
from app.calculation.modules.vm0042_v2_2 import Vm0042V22
from app.reports import pdf
from tests.calc_fixture import FixtureModule

ROWS = [{"seq": 1, "variable": "TEST_LAB", "value": "1.5", "value_kind": "NUMBER", "unit": "t C/ha", "level": "SAMPLING_POINT"},
        {"seq": 2, "variable": "TEST_AREA", "value": "2", "value_kind": "NUMBER", "unit": "ha", "level": "STRATUM"},
        {"seq": 3, "variable": "TEST_K", "value": "2", "value_kind": "NUMBER", "unit": "TEST", "level": "PROJECT"}]


def _leaky(self: Any, ctx: fw.CalculationContext) -> list[fw.Output]:
    raise KeyError("secret-internal-key C:/srv/app/settings.py")


def test_module_exception_message_is_generic_and_the_details_are_logged(caplog: pytest.LogCaptureFixture) -> None:
    module = type("Leaky", (FixtureModule,), {"calculate_removals": _leaky})()
    with caplog.at_level(logging.ERROR, logger="app.calculation.framework"), pytest.raises(fw.CalculationBlocked) as e:
        fw.execute(module, {"inputs": ROWS})
    assert e.value.code == "CALCULATION_ERROR" and e.value.details == {"reason": "MODULE_EXCEPTION", "exception": "KeyError"}
    assert "secret-internal-key" not in e.value.message and "settings.py" not in e.value.message and "KeyError" in e.value.message
    assert "secret-internal-key" in caplog.text                         # the full error is in the server log


def test_report_content_and_text_include_the_module_assumptions() -> None:
    from app.services import calculation_report as cr
    decl = Vm0042V22().declaration()
    content = {"calculation_run": {"run_code": "CR-1", "status_at_generation": "APPROVED", "approved_at": None, "approved_by": None,
                                   "input_sha256": "i", "output_sha256": "o", "net_result": "1", "net_unit": "VCU"},
               "labels": [], "methodology": {}, "dataset": {}, "engine_version": fw.ENGINE_VERSION, "inputs": [], "outputs": [],
               "qa_reviews": [], "findings": [], "generator_version": cr.GENERATOR_VERSION,
               "module": {**{k: decl[k] for k in ("code", "version", "readiness", "label", "steps", "constants", "variables")},
                          "assumptions": decl["assumptions"]}}
    text = cr.lines(content)
    i = text.index("ASSUMPTIONS (documented interpretations of the methodology)")
    assert text[i + 1].startswith("  1. Q2:") and any("PREVIOUS_PERIOD_NOT_ADJACENT" in t for t in text[i:])
    assert cr.GENERATOR_VERSION.startswith("calc-report-1.1+text-pdf-1.1")


def test_pdf_spells_out_symbols_instead_of_question_marks() -> None:
    data = pdf.render(["ΔSOC = 2.5 t CO₂e/ha · CH₄ ≤ 3 m² at 25 °C, 5 µg, 3 × 4 − 1 ± 0.2, σ² Σ"])
    assert b"?" not in data.split(b"stream", 1)[1].split(b"endstream", 1)[0]
    for text in (b"Delta SOC", b"CO2e", b"CH4 <= 3 m^2 at 25  degC", b"5 ug", b"3 x 4 - 1 +/- 0.2", b"sigma^2 Sum"):
        assert text in data, text


def test_decimal_values_stay_decimal() -> None:          # guard against float creeping into the shared input helpers
    from app.calculation.library.inputs import stratum_labels
    v = fw.InputValue(1, "AREA", Decimal("1"), "ha", "STRATUM", None, None, None, {"stratum_record_id": "r1", "stratum_code": "S1"})
    assert stratum_labels([v], ["r1"]) == {"r1": "S1"}
