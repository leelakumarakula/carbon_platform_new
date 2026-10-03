"""Helpers for Phase 5 (MRV) tests: a project with several verified farms taken through the real Phase 2–4 workflow to a
LOCKED methodology version, plus the MRV team. The methodology rules here are TEST fixtures, not real requirements."""
from dataclasses import dataclass
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import Actor
from tests.phase2 import square, staff
from tests.phase3 import PR, Team, active_farmer, add_farm, catalog, create_project, team, verified_farm
from tests.phase4 import ALM_RULES, M, add_history, methodology, specialists

MRV = "/api/v1/mrv"
SIZE = 0.0015  # ≈ 167 m × 158 m ≈ 2.6 ha per farm


@dataclass
class MrvCtx:
    t: Team
    mrv: Actor          # MRV manager
    supervisor: Actor   # field supervisor (assign / review collections)
    collector: Actor    # field agent
    collector2: Actor
    project: dict
    farms: list[dict]
    version_id: str


def locked_project(db: Session, client: TestClient, lon: float, lat: float, id_number: str, n_farms: int = 2,
                   sampling: dict[str, Any] | None = None, monitoring: bool = True,
                   monitoring_rules: list[dict[str, Any]] | None = None) -> MrvCtx:
    t = team(db, client)
    cat = catalog(db)
    author, approver = specialists(db, client)
    m = methodology(client, author, str(cat["s1"].id), [str(cat["a1"].id)], f"TMRV-{cat['s1'].code[-6:]}")
    v = client.post(f"{M}/{m['id']}/versions", headers=author.headers,
                    json={"version_label": "1.0", "effective_from": "2020-01-01", "source_name": "TEST source"}).json()
    vid = v["id"]
    for rule in ALM_RULES:
        assert client.post(f"{M}/versions/{vid}/rules/applicability", headers=author.headers, json=rule).status_code == 201
    if monitoring:
        for rule in monitoring_rules or [{"rule_code": "SOC", "title": "Soil organic carbon", "parameter": "Soil organic carbon stock",
                                          "unit": "t C/ha", "frequency": "each monitoring period", "measurement_source": "LABORATORY"}]:
            assert client.post(f"{M}/versions/{vid}/rules/monitoring", headers=author.headers, json=rule).status_code == 201
    if sampling is not None:
        client.post(f"{M}/versions/{vid}/rules/general", headers=author.headers,
                    json={"rule_code": "SMP", "title": "Sampling (TEST values)", "rule_type": "SAMPLING", "parameters": sampling})
    client.post(f"{M}/versions/{vid}/submit", headers=author.headers, json={"reason": "ready for approval"})
    assert client.post(f"{M}/versions/{vid}/approve", headers=approver.headers, json={"reason": "checked"}).status_code == 200
    # farms and the Phase 3 project workflow
    farmer = active_farmer(client, t, id_number)
    farms = []
    for i in range(n_farms):
        f = verified_farm(client, t, farmer["id"], square(lon + i * SIZE * 1.5, lat, SIZE))
        add_history(client, t, f["id"])
        farms.append(f)
    p = create_project(client, t)
    pid, h = p["id"], t.pm.headers
    assert client.post(f"{PR}/{pid}/start-data-collection", headers=h, json={"reason": "collect"}).status_code == 200
    for f in farms:
        assert add_farm(client, t, pid, f["id"]).status_code == 201
    for path, body in (("standard", {"standard_id": str(cat["s1"].id)}), ("activity", {"activity_id": str(cat["a1"].id)}),
                       ("crediting-period", {"start_date": "2026-06-01", "end_date": "2036-05-31"})):
        assert client.post(f"{PR}/{pid}/{path}", headers=h, json=body).status_code in (200, 201)
    client.patch(f"{PR}/{pid}/baseline", headers=h, json={"period_start": "2021-06-01", "period_end": "2026-05-31"})
    assert client.post(f"{PR}/{pid}/submit", headers=h, json={"reason": "complete"}).status_code == 200
    client.post(f"{PR}/{pid}/boundary/review", headers=t.gis.headers, json={"decision": "ACCEPTED", "notes": "ok ok"})
    for cr in client.get(f"{PR}/{pid}/carbon-rights", headers=t.qa.headers).json():
        client.post(f"{PR}/{pid}/carbon-rights/{cr['id']}/review", headers=t.qa.headers, json={"status": "VERIFIED", "notes": "seen it"})
    assert client.post(f"{PR}/{pid}/approve-eligibility", headers=t.qa.headers, json={"reason": "eligible"}).status_code == 200
    assert client.post(f"{PR}/{pid}/confirm-activity", headers=h, json={"reason": "confirmed"}).status_code == 200
    ev = client.post(f"{PR}/{pid}/methodology/candidates", headers=h, json={"declared_facts": {"additionality_assessment": "COMPLETED"}}).json()
    cand = next(c for c in ev["candidates"] if c["methodology_version_id"] == vid)
    client.post(f"{PR}/{pid}/methodology/reviews", headers=author.headers,
                json={"evaluation_result_id": cand["id"], "recommendation": "RECOMMENDED", "notes": "fits", "evidence_acknowledged": True})
    r = client.post(f"{PR}/{pid}/methodology/confirm", headers=h, json={"evaluation_result_id": cand["id"], "notes": "confirmed and locked"})
    assert r.status_code == 200, r.text
    org = t.org
    return MrvCtx(t, staff(db, client, org, "MRV_MANAGER"), staff(db, client, org, "FIELD_SUPERVISOR"), staff(db, client, org, "FIELD_AGENT"),
                  staff(db, client, org, "FIELD_AGENT"), client.get(f"{PR}/{pid}", headers=h).json(), farms, vid)


def approved_plan(client: TestClient, c: MrvCtx, **kw: Any) -> dict:
    body = {"project_id": c.project["id"], "monitoring_frequency": "Once per monitoring period", "monitoring_start": "2026-06-01",
            "monitoring_end": "2036-05-31", "quantification_approach": "MEASURE_AND_REMEASURE",
            "measurements": [{"code": "TILL", "name": "Tillage operations", "category": "TILLAGE", "value_type": "CHOICE",
                              "allowed_values": ["CONVENTIONAL", "REDUCED", "NO_TILL"], "level": "FARM"}], **kw}
    r = client.post(f"{MRV}/plans", headers=c.mrv.headers, json=body)
    assert r.status_code == 201, r.text
    plan = r.json()
    assert client.post(f"{MRV}/plans/{plan['id']}/submit", headers=c.mrv.headers, json={"reason": "ready"}).status_code == 200
    r = client.post(f"{MRV}/plans/{plan['id']}/approve", headers=c.t.qa.headers, json={"reason": "plan ok", "acknowledge_configuration_gaps": True})
    assert r.status_code == 200, r.text
    return r.json()


def collecting_period(client: TestClient, c: MrvCtx, start: str = "2026-06-01", end: str = "2027-05-31") -> dict:
    r = client.post(f"{MRV}/monitoring-periods", headers=c.mrv.headers,
                    json={"project_id": c.project["id"], "name": "Monitoring 1", "purpose": "MONITORING", "start_date": start, "end_date": end})
    assert r.status_code == 201, r.text
    mp = r.json()
    for action in ("plan", "start", "open-collection"):
        r = client.post(f"{MRV}/monitoring-periods/{mp['id']}/{action}", headers=c.mrv.headers, json={"reason": f"{action} now"})
        assert r.status_code == 200, r.text
    return r.json()


def approved_stratum(client: TestClient, c: MrvCtx, code: str, farm_ids: list[str], **kw: Any) -> dict:
    r = client.post(f"{MRV}/projects/{c.project['id']}/strata", headers=c.mrv.headers,
                    json={"code": code, "name": f"Stratum {code}", "farm_ids": farm_ids,
                          "characteristics": [{"characteristic": "SOIL_TYPE", "value": "Vertisol"}], **kw})
    assert r.status_code == 201, r.text
    r = client.post(f"{MRV}/strata/{r.json()['id']}/approve", headers=c.t.gis.headers, json={"reason": "stratum ok"})
    assert r.status_code == 200, r.text
    return r.json()


def approved_design(client: TestClient, c: MrvCtx, period_id: str, allocations: list[dict], **kw: Any) -> dict:
    body = {"monitoring_period_id": period_id, "code": "D1", "name": "Soil sampling design", "statistical_design": "STRATIFIED_RANDOM",
            "depth_top_cm": "0", "depth_bottom_cm": "30", "min_distance_m": "10", "random_seed": 42, "allocations": allocations, **kw}
    r = client.post(f"{MRV}/sampling-designs", headers=c.mrv.headers, json=body)
    assert r.status_code == 201, r.text
    d = r.json()
    r = client.post(f"{MRV}/sampling-designs/{d['id']}/versions/{d['current']['id']}/approve", headers=c.t.gis.headers, json={"reason": "design ok"})
    assert r.status_code == 200, r.text
    return client.get(f"{MRV}/sampling-designs/{d['id']}", headers=c.mrv.headers).json()


def collect(client: TestClient, c: MrvCtx, point: dict, collector: Actor, when: str = "2026-07-01T09:30:00Z", accept: bool = True) -> dict:
    """Start → fill → photo → submit → (accept) a field collection exactly at the point's location."""
    r = client.post(f"{MRV}/field-collections", headers=collector.headers, json={"sampling_point_id": point["id"]})
    assert r.status_code == 201, r.text
    fc = r.json()
    r = client.patch(f"{MRV}/field-collections/{fc['id']}", headers=collector.headers, json={
        "collected_at": when, "gps_latitude": float(point["latitude"]), "gps_longitude": float(point["longitude"]), "gps_accuracy_m": "4",
        "actual_depth_top_cm": point["planned_depth_top_cm"], "actual_depth_bottom_cm": point["planned_depth_bottom_cm"],
        "sample_quantity": "0.5", "sample_unit": "kg", "observations": "Dry, crop residue present",
        "checklist": dict.fromkeys(fc["required_checklist"], True)})   # the checklist frozen on the record (S2 / decision 18)
    assert r.status_code == 200, r.text
    photo(client, c, collector, "FIELD_COLLECTION", fc["id"])
    r = client.post(f"{MRV}/field-collections/{fc['id']}/submit", headers=collector.headers)
    assert r.status_code == 200, r.text
    if accept:
        r = client.post(f"{MRV}/field-collections/{fc['id']}/review", headers=c.supervisor.headers, json={"decision": "ACCEPTED",
                                                                                                          "notes": "good sample"})
        assert r.status_code == 200, r.text
    return r.json()


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def photo(client: TestClient, c: MrvCtx, actor: Actor, entity_type: str, entity_id: str) -> dict:
    r = client.post(f"{MRV}/evidence", headers=actor.headers, files={"file": ("photo.png", PNG, "image/png")},
                    data={"project_id": c.project["id"], "entity_type": entity_type, "entity_id": entity_id, "evidence_type": "FIELD_PHOTO",
                          "latitude": "20.0", "longitude": "73.8", "description": "field photo"})
    assert r.status_code == 201, r.text
    return r.json()
