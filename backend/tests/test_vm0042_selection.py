"""Calculation-tab module selection and production readiness (VM0042 v2.2): choosing the registered module on a DRAFT version
copies its rule set (calculation rules, monitoring rules with data levels, SAMPLING parameters); a module for another methodology or
a conflicting monitoring rule is refused; production readiness is requested on the APPROVED version and decided by someone else."""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.phase3 import catalog
from tests.phase4 import ALM_RULES, M, methodology, specialists

MODULE = "VM0042-V2.2-QA2-QA3"


def _draft(client: TestClient, author, code: str, label: str = "2.2") -> tuple[dict, str]:
    cat = catalog_holder["cat"]
    m = methodology(client, author, str(cat["s1"].id), [str(cat["a1"].id)], code)
    v = client.post(f"{M}/{m['id']}/versions", headers=author.headers,
                    json={"version_label": label, "effective_from": "2025-10-21", "source_name": "Verra VM0042 v2.2 (C&C 11 Jun 2026)"}).json()
    return m, v["id"]


catalog_holder: dict = {}


def test_select_module_copies_rule_set_and_readiness_workflow(client: TestClient, db: Session) -> None:
    catalog_holder["cat"] = catalog(db)
    author, approver = specialists(db, client)
    _, vid = _draft(client, author, "VM0042")
    opts = client.get(f"{M}/versions/{vid}/calculation-modules", headers=author.headers).json()
    assert [(o["code"], o["selected"]) for o in opts if o["compatible"]] == [(MODULE, False)]
    assert any("Q12" in a for a in opts[0]["assumptions"])
    assert {o["code"] for o in opts if not o["compatible"]} >= {"GS402-ZT-A1", "GS402-CC-A3"}   # other methodologies' modules
    # readiness cannot be requested on a draft
    r = client.post(f"{M}/versions/{vid}/calculation-readiness/request", headers=author.headers, json={"reason": "expert checked"})
    assert r.json()["error_code"] == "READINESS_NOT_APPLICABLE"
    # select -> rule set copied
    r = client.post(f"{M}/versions/{vid}/calculation-module", headers=author.headers, json={"module_code": MODULE, "reason": "VM0042 module"})
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["calculation_module_code"] == MODULE
    by_kind: dict[str, dict[str, dict]] = {}
    for rule in v["rules"]:
        by_kind.setdefault(rule["kind"], {})[rule["rule_code"]] = rule
    assert sorted(by_kind["calculation"]) == sorted(["V42-BSL", "V42-PRJ", "V42-ER", "V42-CR", "V42-LK", "V42-UNC", "V42-ADJ", "V42-NET"])
    assert by_kind["calculation"]["V42-UNC"]["data"]["step"] == "UNCERTAINTY"
    mon = by_kind["monitoring"]
    assert mon["V42_OC"]["data"]["unit"] == "g/kg" and mon["V42_OC"]["data"]["measurement_source"] == "LABORATORY"
    assert mon["V42_FSN"]["data"]["data_level"] == "FARM" and mon["V42_NPR"]["data"]["data_level"] == "PROJECT"
    assert by_kind["general"]["MODULE-SAMPLING"]["data"]["parameters"]["core_details_required"] is True
    # selecting again is idempotent for monitoring rules (no duplicates)
    r = client.post(f"{M}/versions/{vid}/calculation-module", headers=author.headers, json={"module_code": MODULE, "reason": "again"})
    assert r.status_code == 200 and sum(1 for x in r.json()["rules"] if x["kind"] == "monitoring") == len(mon)
    # approve the version (an applicability rule is required), then production readiness
    assert client.post(f"{M}/versions/{vid}/rules/applicability", headers=author.headers, json=ALM_RULES[0]).status_code == 201
    assert client.post(f"{M}/versions/{vid}/submit", headers=author.headers, json={"reason": "ready"}).status_code == 200
    r = client.post(f"{M}/versions/{vid}/approve", headers=approver.headers, json={"reason": "checked"})
    assert r.status_code == 200, r.text
    assert r.json()["calculation_readiness"] == "NOT_PRODUCTION_READY"
    r = client.post(f"{M}/versions/{vid}/calculation-readiness/request", headers=author.headers,
                    json={"reason": "Equations checked against VM0042 v2.2 by the expert; worked-example tests pass"})
    assert r.status_code == 200 and r.json()["readiness_request"]["evidence"].startswith("Equations checked")
    assert client.post(f"{M}/versions/{vid}/calculation-readiness/request", headers=author.headers,
                       json={"reason": "twice"}).json()["error_code"] == "READINESS_REQUEST_OPEN"
    r = client.post(f"{M}/versions/{vid}/calculation-readiness/decide", headers=author.headers, json={"approve": True, "reason": "own"})
    assert r.status_code == 403
    r = client.post(f"{M}/versions/{vid}/calculation-readiness/decide", headers=approver.headers, json={"approve": True, "reason": "verified"})
    assert r.status_code == 200 and r.json()["calculation_readiness"] == "PRODUCTION_READY" and r.json()["readiness_request"] is None
    r = client.post(f"{M}/versions/{vid}/calculation-readiness/revoke", headers=approver.headers, json={"reason": "new evidence needed"})
    assert r.json()["calculation_readiness"] == "NOT_PRODUCTION_READY"
    # an approved version cannot change its module
    r = client.post(f"{M}/versions/{vid}/calculation-module", headers=author.headers, json={"module_code": None, "reason": "clear"})
    assert r.json()["error_code"] == "VERSION_NOT_EDITABLE"


def test_module_refused_for_other_methodology_or_conflicting_rule(client: TestClient, db: Session) -> None:
    catalog_holder["cat"] = catalog(db)
    author, _ = specialists(db, client)
    _, other = _draft(client, author, "OTHER-SOC")
    r = client.post(f"{M}/versions/{other}/calculation-module", headers=author.headers, json={"module_code": MODULE, "reason": "try"})
    assert r.json()["error_code"] == "MODULE_NOT_FOR_VERSION"
    assert not any(o["compatible"] for o in client.get(f"{M}/versions/{other}/calculation-modules", headers=author.headers).json())
    _, vid = _draft(client, author, "VM0042")
    client.post(f"{M}/versions/{vid}/rules/monitoring", headers=author.headers,
                json={"rule_code": "V42_OC", "title": "SOC", "parameter": "soc", "unit": "%", "measurement_source": "LABORATORY"})
    r = client.post(f"{M}/versions/{vid}/calculation-module", headers=author.headers, json={"module_code": MODULE, "reason": "try"})
    assert r.json()["error_code"] == "MONITORING_RULE_CONFLICT" and r.json()["details"]["rule_codes"] == ["V42_OC"]
    assert client.post(f"{M}/versions/{vid}/calculation-module", headers=author.headers,
                       json={"module_code": "NOPE", "reason": "try"}).json()["error_code"] == "MODULE_NOT_FOUND"
