"""Phase 5 — GIS: strata geometry (SQL Server union / area), sampling-point generation inside farms and the project,
configured counts (no area rule), spacing, duplicates, relocation, GPS validation."""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import SamplingPoint
from app.repositories import gis
from app.repositories import projects as project_repo
from app.rules.sampling_points import distance_m
from tests.phase5 import MRV, SIZE, MrvCtx, approved_design, approved_plan, approved_stratum, collecting_period, locked_project, photo


@pytest.fixture()
def c(db: Session, client: TestClient) -> MrvCtx:
    ctx = locked_project(db, client, 76.50, 23.50, "8300 2000 3000", n_farms=3)
    approved_plan(client, ctx)
    return ctx


def _inside_square(farm_index: int, lat: float, lon: float) -> bool:
    lon0 = 76.50 + farm_index * SIZE * 1.5
    return lon0 <= lon <= lon0 + SIZE and 23.50 <= lat <= 23.50 + SIZE


def test_strata_geometry_versioning_and_farm_rules(client: TestClient, db: Session, c: MrvCtx) -> None:
    pid = c.project["id"]
    s1 = approved_stratum(client, c, "S1", [c.farms[0]["id"]])
    r = client.post(f"{MRV}/projects/{pid}/strata", headers=c.mrv.headers,
                    json={"code": "S2", "name": "Two farms", "farm_ids": [c.farms[1]["id"], c.farms[2]["id"]],
                          "characteristics": [{"characteristic": "CROP", "value": "Wheat"}]})
    assert r.status_code == 201, r.text
    s2 = r.json()
    # SQL Server union geometry: two disjoint farms → MultiPolygon with twice the area of one farm
    assert s1["geojson"]["type"] == "Polygon" and s2["geojson"]["type"] == "MultiPolygon"
    assert abs(float(s2["area_hectares"]) - 2 * float(s1["area_hectares"])) < 0.02 * float(s1["area_hectares"])
    assert 2.0 < float(s1["area_hectares"]) < 3.5
    # a farm belongs to one current stratum; farms must participate in the project
    r = client.post(f"{MRV}/projects/{pid}/strata", headers=c.mrv.headers, json={"code": "S3", "name": "Dup", "farm_ids": [c.farms[0]["id"]]})
    assert r.json()["error_code"] == "FARM_ALREADY_STRATIFIED"
    r = client.post(f"{MRV}/projects/{pid}/strata", headers=c.mrv.headers, json={"code": "S4", "name": "Stranger", "farm_ids": [str(uuid.uuid4())]})
    assert r.json()["error_code"] == "FARM_NOT_IN_PROJECT"
    # an approved stratum is never silently modified: a revision is a new DRAFT version that needs a reason
    assert client.patch(f"{MRV}/strata/{s1['id']}", headers=c.mrv.headers, json={"name": "Renamed"}).json()["error_code"] == "REASON_REQUIRED"
    r = client.patch(f"{MRV}/strata/{s1['id']}", headers=c.mrv.headers, json={"name": "Renamed stratum", "reason": "soil survey update"})
    v2 = r.json()
    assert v2["version"] == 2 and v2["record_id"] == s1["record_id"] and v2["status"] == "DRAFT" and not v2["is_current"]
    assert client.patch(f"{MRV}/strata/{s1['id']}", headers=c.mrv.headers, json={"name": "Again", "reason": "another one"}
                        ).json()["error_code"] == "REVISION_EXISTS"
    current = {s["code"]: s for s in client.get(f"{MRV}/projects/{pid}/strata", headers=c.mrv.headers).json() if s["is_current"]}
    assert current["S1"]["name"] == "Stratum S1" and current["S1"]["status"] == "APPROVED"
    assert client.post(f"{MRV}/strata/{v2['id']}/approve", headers=c.mrv.headers, json={"reason": "own"}).status_code == 403
    r = client.post(f"{MRV}/strata/{v2['id']}/approve", headers=c.t.gis.headers, json={"reason": "survey ok"})
    assert r.json()["status"] == "APPROVED" and r.json()["is_current"]
    allv = [s for s in client.get(f"{MRV}/projects/{pid}/strata", headers=c.mrv.headers, params={"include_history": True}).json()
            if s["code"] == "S1"]
    assert sorted((s["version"], s["status"]) for s in allv) == [(1, "SUPERSEDED"), (2, "APPROVED")]


def test_points_inside_farms_and_project_with_configured_counts(client: TestClient, db: Session, c: MrvCtx) -> None:
    mp = collecting_period(client, c)
    s1 = approved_stratum(client, c, "S1", [c.farms[0]["id"]])
    s2 = approved_stratum(client, c, "S2", [c.farms[1]["id"], c.farms[2]["id"]])
    d = approved_design(client, c, mp["id"], [{"stratum_id": s1["id"], "sample_count": 3}, {"stratum_id": s2["id"], "sample_count": 5}],
                        min_distance_m="20")
    assert client.post(f"{MRV}/sampling-designs/{d['id']}/generate-points", headers=c.collector.headers).status_code == 403
    r = client.post(f"{MRV}/sampling-designs/{d['id']}/generate-points", headers=c.mrv.headers)
    assert r.status_code == 201, r.text
    out = r.json()
    # the count is exactly what the design configured — no per-area rule
    assert out["created"] == 8 and out["per_stratum"] == {"S1": 3, "S2": 5}
    pts = out["points"]
    assert all(x["point_code"].startswith("SP-") and x["status"] == "PLANNED" for x in pts)
    farm_index = {f["id"]: i for i, f in enumerate(c.farms)}
    pb = project_repo.current_boundary(db, uuid.UUID(c.project["id"]))
    assert pb is not None
    for x in pts:
        row = db.get(SamplingPoint, uuid.UUID(x["id"]))
        assert row is not None
        lat, lon = float(x["latitude"]), float(x["longitude"])
        assert gis.point_inside_boundary(db, row.farm_boundary_id, lat, lon)  # SQL Server containment
        assert gis.point_inside_project(db, pb.id, lat, lon)
        assert _inside_square(farm_index[x["farm_id"]], lat, lon)
        if x["stratum_id"] == s1["id"]:
            assert x["farm_id"] == c.farms[0]["id"]
    coords = [(float(x["latitude"]), float(x["longitude"])) for x in pts]
    assert min(distance_m(a, b) for i, a in enumerate(coords) for b in coords[i + 1:]) >= 20
    # generating twice is refused (no duplicates)
    assert client.post(f"{MRV}/sampling-designs/{d['id']}/generate-points", headers=c.mrv.headers).json()["error_code"] == "POINTS_ALREADY_GENERATED"
    listed = client.get(f"{MRV}/sampling-points", headers=c.mrv.headers, params={"monitoring_period_id": mp["id"]}).json()
    assert len(listed) == 8


def test_systematic_grid_and_insufficient_area(client: TestClient, db: Session, c: MrvCtx) -> None:
    mp = collecting_period(client, c)
    s1 = approved_stratum(client, c, "S1", [c.farms[0]["id"]])
    d = approved_design(client, c, mp["id"], [{"stratum_id": s1["id"], "sample_count": 4}], statistical_design="SYSTEMATIC_GRID",
                        min_distance_m="30")
    pts = client.post(f"{MRV}/sampling-designs/{d['id']}/generate-points", headers=c.mrv.headers).json()["points"]
    assert len(pts) == 4 and all(_inside_square(0, float(x["latitude"]), float(x["longitude"])) for x in pts)
    lats = sorted({round(float(x["latitude"]), 6) for x in pts})
    assert len(lats) <= 3  # grid rows, not scattered random points
    # 10 points 200 m apart cannot fit in a ~2.6 ha stratum → refused, nothing written
    d2 = approved_design(client, c, mp["id"], [{"stratum_id": s1["id"], "sample_count": 10}], code="D2", min_distance_m="200")
    r = client.post(f"{MRV}/sampling-designs/{d2['id']}/generate-points", headers=c.mrv.headers)
    assert r.status_code == 409 and r.json()["error_code"] == "INSUFFICIENT_AREA"
    assert len(client.get(f"{MRV}/sampling-points", headers=c.mrv.headers, params={"monitoring_period_id": mp["id"]}).json()) == 4


def test_relocation_validation_and_approval(client: TestClient, db: Session, c: MrvCtx) -> None:
    mp = collecting_period(client, c)
    s1 = approved_stratum(client, c, "S1", [c.farms[0]["id"]])
    d = approved_design(client, c, mp["id"], [{"stratum_id": s1["id"], "sample_count": 2}])
    a, b = client.post(f"{MRV}/sampling-designs/{d['id']}/generate-points", headers=c.mrv.headers).json()["points"]
    client.post(f"{MRV}/sampling-points/{a['id']}/assign", headers=c.supervisor.headers, json={"collector_id": str(c.collector.user.id)})
    url = f"{MRV}/sampling-points/{a['id']}/relocations"
    # invalid point: outside the farm, or on top of another point, or impossible coordinates
    r = client.post(url, headers=c.collector.headers, json={"latitude": 23.4, "longitude": 76.4, "reason": "flooded corner"})
    assert r.status_code == 422 and r.json()["error_code"] == "OUTSIDE_FARM"
    r = client.post(url, headers=c.collector.headers, json={"latitude": float(b["latitude"]), "longitude": float(b["longitude"]),
                                                            "reason": "flooded"})
    assert r.json()["error_code"] == "DUPLICATE_POINT"
    assert client.post(url, headers=c.collector.headers, json={"latitude": 123.0, "longitude": 76.5, "reason": "bad gps"}).status_code == 422
    # another collector (not assigned) cannot move this point
    assert client.post(url, headers=c.collector2.headers, json={"latitude": 23.5007, "longitude": 76.5007, "reason": "x x x"}).status_code == 403
    new = (23.50 + SIZE / 2, 76.50 + SIZE / 2)
    if distance_m(new, (float(b["latitude"]), float(b["longitude"]))) < 5:
        new = (23.50 + SIZE / 3, 76.50 + SIZE / 3)
    r = client.post(url, headers=c.collector.headers, json={"latitude": new[0], "longitude": new[1], "reason": "standing water at the point"})
    assert r.status_code == 201, r.text
    rel = r.json()
    assert rel["status"] == "PENDING" and float(rel["old_latitude"]) == pytest.approx(float(a["latitude"])) and float(rel["distance_m"]) > 0
    assert client.post(url, headers=c.collector.headers, json={"latitude": new[0], "longitude": new[1], "reason": "again"}
                       ).json()["error_code"] == "RELOCATION_PENDING"
    # the point does not move until someone with sampling.review approves
    assert client.get(f"{MRV}/sampling-points/{a['id']}", headers=c.mrv.headers).json()["latitude"] == a["latitude"]
    assert client.post(f"{MRV}/relocations/{rel['id']}/decision", headers=c.collector.headers,
                       json={"decision": "APPROVED", "notes": "self"}).status_code == 403
    r = client.post(f"{MRV}/relocations/{rel['id']}/decision", headers=c.supervisor.headers, json={"decision": "APPROVED", "notes": "verified"})
    assert r.json()["status"] == "APPROVED" and r.json()["reviewed_by"] == str(c.supervisor.user.id)
    moved = client.get(f"{MRV}/sampling-points/{a['id']}", headers=c.mrv.headers).json()
    assert float(moved["latitude"]) == pytest.approx(new[0], abs=1e-6) and float(moved["longitude"]) == pytest.approx(new[1], abs=1e-6)
    # a rejected request leaves the point where it is
    r = client.post(url, headers=c.collector.headers, json={"latitude": a["latitude"], "longitude": a["longitude"], "reason": "move back"})
    client.post(f"{MRV}/relocations/{r.json()['id']}/decision", headers=c.supervisor.headers, json={"decision": "REJECTED", "notes": "keep it"})
    assert float(client.get(f"{MRV}/sampling-points/{a['id']}", headers=c.mrv.headers).json()["latitude"]) == pytest.approx(new[0], abs=1e-6)
    hist = client.get(url, headers=c.mrv.headers).json()
    assert sorted(h["status"] for h in hist) == ["APPROVED", "REJECTED"]


def test_gps_outside_farm_flagged_and_justified(client: TestClient, db: Session, c: MrvCtx) -> None:
    mp = collecting_period(client, c)
    s1 = approved_stratum(client, c, "S1", [c.farms[0]["id"]])
    d = approved_design(client, c, mp["id"], [{"stratum_id": s1["id"], "sample_count": 1}])
    (pt,) = client.post(f"{MRV}/sampling-designs/{d['id']}/generate-points", headers=c.mrv.headers).json()["points"]
    client.post(f"{MRV}/sampling-points/{pt['id']}/assign", headers=c.supervisor.headers, json={"collector_id": str(c.collector.user.id)})
    fc = client.post(f"{MRV}/field-collections", headers=c.collector.headers, json={"sampling_point_id": pt["id"]}).json()
    r = client.patch(f"{MRV}/field-collections/{fc['id']}", headers=c.collector.headers, json={
        "collected_at": "2026-07-01T09:00:00Z", "gps_latitude": 23.4990, "gps_longitude": 76.4990, "actual_depth_top_cm": "0",
        "actual_depth_bottom_cm": "30", "checklist": dict.fromkeys(fc["required_checklist"], True)})
    got = r.json()
    assert got["gps_inside_farm"] is False and float(got["distance_from_point_m"]) > 30
    photo(client, c, c.collector, "FIELD_COLLECTION", fc["id"])
    r = client.post(f"{MRV}/field-collections/{fc['id']}/submit", headers=c.collector.headers)
    assert r.json()["error_code"] == "REQUIREMENTS_NOT_MET" and "outside the farm" in r.json()["message"]
    # a future date is refused
    client.patch(f"{MRV}/field-collections/{fc['id']}", headers=c.collector.headers, json={"deviation_note": "Gate locked; sampled at the edge",
                                                                                        "collected_at": "2027-09-01T09:00:00Z"})
    assert client.post(f"{MRV}/field-collections/{fc['id']}/submit", headers=c.collector.headers).status_code in (409, 422)
    client.patch(f"{MRV}/field-collections/{fc['id']}", headers=c.collector.headers, json={"collected_at": "2026-07-01T09:00:00Z"})
    assert client.post(f"{MRV}/field-collections/{fc['id']}/submit", headers=c.collector.headers).json()["status"] == "SUBMITTED"
