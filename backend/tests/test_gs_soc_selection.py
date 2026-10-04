"""Calculation-tab selection of the Gold Standard SOC (GS 402 v1.0) modules: several modules implement GS402 / 1.0, the version
chooses one (rules copied, Approach 3 factors recorded per stratum) and may switch to another while it is a draft."""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.phase3 import catalog
from tests.phase4 import M, methodology, specialists


def test_gs402_modules_selectable_and_switchable_on_a_draft(client: TestClient, db: Session) -> None:
    cat = catalog(db)
    author, _ = specialists(db, client)
    m = methodology(client, author, str(cat["s1"].id), [str(cat["a1"].id)], "GS402")
    vid = client.post(f"{M}/{m['id']}/versions", headers=author.headers,
                      json={"version_label": "1.0", "effective_from": "2020-01-01", "source_name": "Gold Standard SOC Framework v1.0"}).json()["id"]
    opts = client.get(f"{M}/versions/{vid}/calculation-modules", headers=author.headers).json()
    assert [o["code"] for o in opts if o["compatible"]] == ["GS402-ZT-A1", "GS402-IT-A1", "GS402-IT-A3", "GS402-CC-A1", "GS402-CC-A3"]
    r = client.post(f"{M}/versions/{vid}/calculation-module", headers=author.headers, json={"module_code": "GS402-IT-A3", "reason": "tillage"})
    assert r.status_code == 200, r.text
    v = r.json()
    mon = {x["rule_code"]: x["data"] for x in v["rules"] if x["kind"] == "monitoring"}
    assert mon["GS_SOC_REF"]["data_level"] == "STRATUM" and mon["GS_SOC_REF"]["unit"] == "t C/ha"
    assert mon["GS_FERT_N"]["data_level"] == "FARM" and mon["GS_LK_EF"]["data_level"] == "PROJECT"
    assert "GS_OC" not in mon
    calc = {x["rule_code"]: x["data"] for x in v["rules"] if x["kind"] == "calculation"}
    assert calc["GS-LK"]["equation_reference"] == "GS 402 v1.0 Eq. 19"
    assert not any(x["rule_code"] == "MODULE-SAMPLING" for x in v["rules"])            # Approach 3 has no sampling settings
    # switch to cover crops Approach 1: lab rules added, shared rules kept without conflict, calculation rules replaced
    r = client.post(f"{M}/versions/{vid}/calculation-module", headers=author.headers, json={"module_code": "GS402-CC-A1", "reason": "cover crops"})
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["calculation_module_code"] == "GS402-CC-A1"
    mon = {x["rule_code"]: x["data"] for x in v["rules"] if x["kind"] == "monitoring"}
    assert mon["GS_OC"]["measurement_source"] == "LABORATORY" and "GS_CC_SEED" in mon
    calc = {x["rule_code"]: x["data"] for x in v["rules"] if x["kind"] == "calculation"}
    assert calc["GS-LK"]["equation_reference"] == "402.6 v1.0 Eq. 10"
    sampling = next(x for x in v["rules"] if x["rule_code"] == "MODULE-SAMPLING")
    assert sampling["data"]["parameters"]["reference_depth_cm"] == 30
