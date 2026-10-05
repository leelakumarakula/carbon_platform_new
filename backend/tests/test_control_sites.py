"""VM0042 Quantification Approach 2 — baseline control sites (strata with role CONTROL): farm eligibility (not a project
participant), links to the project strata they represent, Table 7 similarity checks at approval (categorical criteria,
precipitation tolerance, distance ≤ 250 km) and the reverse guard (a control farm cannot join the project)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.project_farm_service import _is_control_farm
from tests.phase2 import square
from tests.phase3 import verified_farm
from tests.phase5 import MRV, SIZE, MrvCtx, approved_design, approved_plan, approved_stratum, collecting_period, locked_project

LON, LAT = 77.10, 21.40


@pytest.fixture()
def c(db: Session, client: TestClient) -> MrvCtx:
    ctx = locked_project(db, client, LON, LAT, "8350 2000 3000", n_farms=2)
    approved_plan(client, ctx)
    return ctx


def _control_farm(client: TestClient, c: MrvCtx, lon: float, lat: float) -> dict:
    """A verified farm of the same organization that does NOT join the project."""
    return verified_farm(client, c.t, c.farms[0]["farmer_id"], square(lon, lat, SIZE))


def _create(client: TestClient, c: MrvCtx, code: str, farm_ids: list[str], links: list[str], chars: list[dict] | None = None,
            role: str = "CONTROL") -> dict:
    return client.post(f"{MRV}/projects/{c.project['id']}/strata", headers=c.mrv.headers,
                       json={"code": code, "name": f"Control {code}", "farm_ids": farm_ids, "role": role, "linked_stratum_ids": links,
                             "characteristics": chars if chars is not None else [{"characteristic": "SOIL_TYPE", "value": "Vertisol"}]}).json()


def test_control_site_farm_rules_links_and_candidates(client: TestClient, db: Session, c: MrvCtx) -> None:
    pid = c.project["id"]
    s1 = approved_stratum(client, c, "S1", [c.farms[0]["id"], c.farms[1]["id"]])
    near = _control_farm(client, c, LON + 0.02, LAT)
    # candidates: eligible farms of the organization that are not project participants
    cands = {x["farm_id"] for x in client.get(f"{MRV}/projects/{pid}/control-site-candidates", headers=c.mrv.headers).json()}
    assert near["id"] in cands and c.farms[0]["id"] not in cands
    # a project participant cannot be a control site; a control site needs links; a project stratum takes none
    assert _create(client, c, "C0", [c.farms[0]["id"]], [s1["id"]])["error_code"] == "CONTROL_FARM_IN_PROJECT"
    assert _create(client, c, "C0", [near["id"]], [])["error_code"] == "CONTROL_LINKS_REQUIRED"
    assert _create(client, c, "P9", [near["id"]], [s1["id"]], role="PROJECT")["error_code"] == "LINKS_NOT_ALLOWED"
    cs = _create(client, c, "C1", [near["id"]], [s1["id"]])
    assert cs["role"] == "CONTROL" and [x["code"] for x in cs["linked_strata"]] == ["S1"] and float(cs["area_hectares"]) > 2
    # the stratum list shows the role; a farm stays in only one current stratum
    roles = {s["code"]: s["role"] for s in client.get(f"{MRV}/projects/{pid}/strata", headers=c.mrv.headers).json()}
    assert roles == {"S1": "PROJECT", "C1": "CONTROL"}
    assert _create(client, c, "C2", [near["id"]], [s1["id"]])["error_code"] == "FARM_ALREADY_STRATIFIED"
    # the reverse guard: a control farm cannot join the project as a participant
    assert _is_control_farm(db, c.project["id"], near["id"]) and not _is_control_farm(db, c.project["id"], c.farms[0]["id"])


def test_control_site_similarity_and_distance_checked_at_approval(client: TestClient, db: Session, c: MrvCtx) -> None:
    chars = [{"characteristic": "SOIL_TYPE", "value": "Vertisol"}, {"characteristic": "SOIL_TEXTURE", "value": "Clay"},
             {"characteristic": "SOIL_GROUP", "value": "Vertisols"}, {"characteristic": "PRECIPITATION_MM", "value": "750"}]
    s1 = approved_stratum(client, c, "S1", [c.farms[0]["id"], c.farms[1]["id"]], characteristics=chars)
    near, far = _control_farm(client, c, LON + 0.02, LAT), _control_farm(client, c, LON + 3.0, LAT)   # ~0 km vs ~310 km
    gis = c.t.gis.headers
    # different texture and too much rain difference -> refused with each problem listed
    bad = _create(client, c, "C1", [near["id"]], [s1["id"]],
                  [{"characteristic": "SOIL_TEXTURE", "value": "Sandy loam"}, {"characteristic": "SOIL_GROUP", "value": "vertisols"},
                   {"characteristic": "PRECIPITATION_MM", "value": "900"}])
    r = client.post(f"{MRV}/strata/{bad['id']}/approve", headers=gis, json={"reason": "check it"}).json()
    assert r["error_code"] == "CONTROL_SITE_NOT_SIMILAR"
    problems = " ".join(r["details"]["problems"])
    assert "SOIL_TEXTURE differs" in problems and "precipitation differs by 150" in problems and "SOIL_GROUP" not in problems
    # too far from the stratum it represents
    away = _create(client, c, "C2", [far["id"]], [s1["id"]], chars)
    r = client.post(f"{MRV}/strata/{away['id']}/approve", headers=gis, json={"reason": "check it"}).json()
    assert r["error_code"] == "CONTROL_SITE_NOT_SIMILAR" and "km away (limit 250 km)" in " ".join(r["details"]["problems"])
    # fix the near one (a DRAFT is edited in place) -> approved by someone other than its creator
    fixed = client.patch(f"{MRV}/strata/{bad['id']}", headers=c.mrv.headers, json={"characteristics": chars}).json()
    assert client.post(f"{MRV}/strata/{fixed['id']}/approve", headers=c.mrv.headers, json={"reason": "own"}).status_code == 403
    ok = client.post(f"{MRV}/strata/{fixed['id']}/approve", headers=gis, json={"reason": "similar enough"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "APPROVED" and ok.json()["role"] == "CONTROL"
    # a revision keeps the role and the links
    v2 = client.patch(f"{MRV}/strata/{fixed['id']}", headers=c.mrv.headers, json={"name": "Control renamed", "reason": "rename"}).json()
    assert v2["role"] == "CONTROL" and [x["code"] for x in v2["linked_strata"]] == ["S1"]


def test_sampling_points_are_generated_inside_control_sites(client: TestClient, db: Session, c: MrvCtx) -> None:
    """A control site lies outside the project boundary by definition: its points stay inside its own farm (regression: they were
    clipped to the project boundary, so no point could be placed and VM0042 sampling was impossible)."""
    s1 = approved_stratum(client, c, "S1", [c.farms[0]["id"]])
    near = _control_farm(client, c, LON + 0.02, LAT)
    cs = _create(client, c, "C1", [near["id"]], [s1["id"]])
    assert client.post(f"{MRV}/strata/{cs['id']}/approve", headers=c.t.gis.headers, json={"reason": "control ok"}).status_code == 200
    mp = collecting_period(client, c)
    d = approved_design(client, c, mp["id"], [{"stratum_id": s1["id"], "sample_count": 2}, {"stratum_id": cs["id"], "sample_count": 3}])
    r = client.post(f"{MRV}/sampling-designs/{d['id']}/generate-points", headers=c.mrv.headers)
    assert r.status_code == 201, r.text
    pts = r.json()["points"]
    assert sum(1 for p in pts if p["stratum_id"] == cs["id"]) == 3 and all(p["farm_id"] == near["id"] for p in pts if p["stratum_id"] == cs["id"])
    assert all(p["farm_id"] == c.farms[0]["id"] for p in pts if p["stratum_id"] == s1["id"])
