"""Helpers for Phase 4 (methodology) tests: a small methodology catalog built through the API with separation of
duties, and a project taken through the real Phase 3 workflow to ACTIVITY_SELECTED.

The rules used here are TEST fixtures for the engine — they are not taken from any real methodology."""
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import Actor, login, make_user
from tests.phase2 import square
from tests.phase3 import PR, Team, active_farmer, add_farm, create_project, verified_farm

M = "/api/v1/methodologies"

ALM_RULES: list[dict[str, Any]] = [
    {"rule_code": "A1", "title": "Project in an eligible country", "category": "COUNTRY", "fact_key": "country", "operator": "IN",
     "expected_value": ["IN"], "source_reference": "TEST §1"},
    {"rule_code": "A2", "title": "Land is cropland", "category": "LAND_USE", "fact_key": "land_use_current", "operator": "ALL_IN",
     "expected_value": ["CROPLAND"]},
    {"rule_code": "A3", "title": "Five years of land-use history", "category": "DATA_AVAILABILITY", "fact_key": "land_use_history_years_min",
     "operator": "GTE", "expected_value": 5},
    {"rule_code": "A4", "title": "A practice change is proposed", "category": "PROPOSED_PRACTICE", "fact_key": "proposed_practice_categories",
     "operator": "ANY_IN", "expected_value": ["TILLAGE", "RESIDUE", "FERTILIZER", "COVER_CROP"]},
    {"rule_code": "A5", "title": "Start date not before 2020", "category": "START_DATE", "fact_key": "project_start_date",
     "operator": "DATE_ON_OR_AFTER", "expected_value": "2020-01-01"},
    {"rule_code": "A6", "title": "Additionality assessment completed", "category": "ADDITIONALITY", "fact_key": "additionality_assessment",
     "operator": "EQUALS", "expected_value": "COMPLETED", "evidence_requirement": "Additionality demonstration document"},
]
WETLAND_RULES: list[dict[str, Any]] = [
    {"rule_code": "W1", "title": "Flooded rice land", "category": "LAND_USE", "fact_key": "land_use_current", "operator": "ALL_IN",
     "expected_value": ["WETLAND"]},
]


def specialists(db: Session, client: TestClient) -> tuple[Actor, Actor]:
    a = make_user(db, roles=[("METHODOLOGY_SPECIALIST", None)])
    b = make_user(db, roles=[("METHODOLOGY_SPECIALIST", None)])
    return Actor(a, login(client, a)), Actor(b, login(client, b))


def methodology(client: TestClient, author: Actor, standard_id: str, activity_ids: list[str], code: str, **kw: Any) -> dict:
    r = client.post(M, headers=author.headers, json={"code": code, "name": f"{code} test methodology", "standard_id": standard_id,
                                                     "activity_ids": activity_ids, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def approved_version(client: TestClient, author: Actor, approver: Actor, methodology_id: str, label: str, rules: list[dict],
                     **kw: Any) -> dict:
    body = {"version_label": label, "effective_from": "2020-01-01", "source_name": "TEST source document", **kw}
    v = client.post(f"{M}/{methodology_id}/versions", headers=author.headers, json=body)
    assert v.status_code == 201, v.text
    vid = v.json()["id"]
    if not kw.get("based_on_version_id"):
        for rule in rules:
            r = client.post(f"{M}/versions/{vid}/rules/applicability", headers=author.headers, json=rule)
            assert r.status_code == 201, r.text
    assert client.post(f"{M}/versions/{vid}/submit", headers=author.headers, json={"reason": "ready for approval"}).status_code == 200
    r = client.post(f"{M}/versions/{vid}/approve", headers=approver.headers, json={"reason": "checked against the source"})
    assert r.status_code == 200, r.text
    return r.json()


def add_history(client: TestClient, t: Team, farm_id: str, land_use: str = "CROPLAND", years: int = 5) -> None:
    for y in range(2019, 2019 + years):
        r = client.post(f"/api/v1/farms/{farm_id}/history/land", headers=t.agent.headers, json={"year": y, "land_use": land_use})
        assert r.status_code == 201, r.text
    for body in ({"year": 2022, "practice_phase": "HISTORICAL", "practice_category": "TILLAGE", "practice_type": "Conventional ploughing"},
                 {"year": 2026, "practice_phase": "PROPOSED", "practice_category": "TILLAGE", "practice_type": "Reduced tillage",
                  "implementation_status": "PLANNED"}):
        r = client.post(f"/api/v1/farms/{farm_id}/history/practice", headers=t.agent.headers, json=body)
        assert r.status_code == 201, r.text


def project_at_activity_selected(client: TestClient, t: Team, cat: dict, lon: float, lat: float, id_number: str,
                                 history: bool = True, start_date: str = "2026-06-01") -> dict:
    """Phase 3 workflow end to end: farm, standard, activity, period, baseline, eligibility approval, activity confirmed."""
    farmer = active_farmer(client, t, id_number)
    farm = verified_farm(client, t, farmer["id"], square(lon, lat))
    if history:
        add_history(client, t, farm["id"])
    p = create_project(client, t, start_date=start_date)
    pid = p["id"]
    h = t.pm.headers
    assert client.post(f"{PR}/{pid}/start-data-collection", headers=h, json={"reason": "collect data"}).status_code == 200
    assert add_farm(client, t, pid, farm["id"], participation_start=start_date).status_code == 201
    for path, body in (("standard", {"standard_id": str(cat["s1"].id)}), ("activity", {"activity_id": str(cat["a1"].id)}),
                       ("crediting-period", {"start_date": start_date, "end_date": "2036-05-31"})):
        r = client.post(f"{PR}/{pid}/{path}", headers=h, json=body)
        assert r.status_code in (200, 201), r.text
    assert client.patch(f"{PR}/{pid}/baseline", headers=h, json={"period_start": "2021-06-01", "period_end": "2026-05-31"}).status_code == 200
    assert client.post(f"{PR}/{pid}/submit", headers=h, json={"reason": "complete"}).status_code == 200
    assert client.post(f"{PR}/{pid}/boundary/review", headers=t.gis.headers, json={"decision": "ACCEPTED", "notes": "ok ok"}).status_code == 200
    for cr in client.get(f"{PR}/{pid}/carbon-rights", headers=t.qa.headers).json():
        client.post(f"{PR}/{pid}/carbon-rights/{cr['id']}/review", headers=t.qa.headers, json={"status": "VERIFIED", "notes": "seen it"})
    assert client.post(f"{PR}/{pid}/approve-eligibility", headers=t.qa.headers, json={"reason": "eligible"}).status_code == 200
    r = client.post(f"{PR}/{pid}/confirm-activity", headers=h, json={"reason": "confirmed"})
    assert r.json()["status"] == "ACTIVITY_SELECTED", r.text
    return r.json()

