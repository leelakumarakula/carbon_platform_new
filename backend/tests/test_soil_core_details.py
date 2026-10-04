"""Soil-core details on field records (VM0042 v2.2 Equation 3): probe/auger inside diameter and number of cores. Optional by
default; mandatory at submission when the locked methodology's SAMPLING rule sets `core_details_required` (frozen in the
record's field rules); kept on correction."""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.phase5 import MRV, MrvCtx, approved_design, approved_plan, approved_stratum, collecting_period, locked_project, photo


def _point(client: TestClient, c: MrvCtx, sampling: dict | None) -> dict:
    mp = collecting_period(client, c)
    s1 = approved_stratum(client, c, "S1", [c.farms[0]["id"]])
    d = approved_design(client, c, mp["id"], [{"stratum_id": s1["id"], "sample_count": 1}])
    (pt,) = client.post(f"{MRV}/sampling-designs/{d['id']}/generate-points", headers=c.mrv.headers).json()["points"]
    r = client.post(f"{MRV}/sampling-points/{pt['id']}/assign", headers=c.supervisor.headers, json={"collector_id": str(c.collector.user.id)})
    assert r.status_code == 200, r.text
    return pt


def _filled(client: TestClient, c: MrvCtx, pt: dict) -> dict:
    fc = client.post(f"{MRV}/field-collections", headers=c.collector.headers, json={"sampling_point_id": pt["id"]}).json()
    r = client.patch(f"{MRV}/field-collections/{fc['id']}", headers=c.collector.headers, json={
        "collected_at": "2026-07-01T09:30:00Z", "gps_latitude": float(pt["latitude"]), "gps_longitude": float(pt["longitude"]),
        "actual_depth_top_cm": "0", "actual_depth_bottom_cm": "50", "checklist": dict.fromkeys(fc["required_checklist"], True)})
    assert r.status_code == 200, r.text
    photo(client, c, c.collector, "FIELD_COLLECTION", fc["id"])
    return r.json()


def test_core_details_required_by_methodology(client: TestClient, db: Session) -> None:
    c = locked_project(db, client, 77.30, 21.60, "8360 2000 3000", n_farms=1, sampling={"core_details_required": True})
    approved_plan(client, c)
    fc = _filled(client, c, _point(client, c, {"core_details_required": True}))
    assert fc["core_details_required"] is True and fc["field_rules"]["core_details_source"] == "METHODOLOGY"
    r = client.post(f"{MRV}/field-collections/{fc['id']}/submit", headers=c.collector.headers).json()
    assert r["error_code"] == "REQUIREMENTS_NOT_MET" and any("number of cores" in m for m in r["details"]["missing"])
    # out-of-range values are refused; valid ones are stored and the record can be submitted
    bad = client.patch(f"{MRV}/field-collections/{fc['id']}", headers=c.collector.headers, json={"cores_count": 0})
    assert bad.status_code == 422
    r = client.patch(f"{MRV}/field-collections/{fc['id']}", headers=c.collector.headers, json={"probe_diameter_mm": "21.5", "cores_count": 4})
    assert r.status_code == 200 and float(r.json()["probe_diameter_mm"]) == 21.5 and r.json()["cores_count"] == 4
    r = client.post(f"{MRV}/field-collections/{fc['id']}/submit", headers=c.collector.headers)
    assert r.status_code == 200, r.text
    r = client.post(f"{MRV}/field-collections/{fc['id']}/review", headers=c.supervisor.headers, json={"decision": "ACCEPTED", "notes": "good core"})
    assert r.status_code == 200, r.text
    # a correction starts from the accepted values, core details included
    r = client.post(f"{MRV}/field-collections/{fc['id']}/correct", headers=c.collector.headers, json={"reason": "fix the depth note"})
    assert r.status_code in (200, 201), r.text
    assert float(r.json()["probe_diameter_mm"]) == 21.5 and r.json()["cores_count"] == 4


def test_core_details_optional_by_default(client: TestClient, db: Session) -> None:
    c = locked_project(db, client, 77.40, 21.70, "8370 2000 3000", n_farms=1)
    approved_plan(client, c)
    fc = _filled(client, c, _point(client, c, None))
    assert fc["core_details_required"] is False and fc["field_rules"]["core_details_source"] == "PLATFORM_DEFAULT"
    r = client.post(f"{MRV}/field-collections/{fc['id']}/submit", headers=c.collector.headers)
    assert r.status_code == 200, r.text
