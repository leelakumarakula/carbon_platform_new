"""Phase 3 GIS: the project boundary is derived by SQL Server from participating farm boundaries (UnionAggregate),
its area is authoritative (STArea, overlaps counted once), validity is checked, and overlaps with other projects are
flagged for review — never auto-rejected."""
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.phase2 import add_owner, create_farm, set_boundary, square
from tests.phase3 import PR, Team, active_farmer, add_farm, create_project, team, verified_farm

SIZE = 0.001


def _area_ha(db: Session, geo: dict) -> float:
    from app.rules.geometry_io import parse_geojson
    wkt = parse_geojson(geo).to_wkt()
    return float(db.execute(text("SELECT geography::STGeomFromText(:w, 4326).STArea()"), {"w": wkt}).scalar_one()) / 10_000


def _verified_overlapping(client: TestClient, t: Team, farmer_id: str, geo: dict) -> dict:
    """A farm that overlaps an existing one: the GIS reviewer clears the flag (same organization) before verifying."""
    farm = create_farm(client, t.agent.headers, farmer_id)
    set_boundary(client, t.agent.headers, farm["id"], geo)
    own = add_owner(client, t.agent.headers, farm["id"])
    fid = farm["id"]
    client.post(f"/api/v1/farms/{fid}/submit", headers=t.agent.headers, json={"reason": "ready"})
    client.post(f"/api/v1/farms/{fid}/start-review", headers=t.gis.headers, json={"reason": "start"})
    for o in client.get(f"/api/v1/farms/{fid}/overlaps", headers=t.gis.headers).json():
        r = client.post(f"/api/v1/farms/{fid}/overlaps/{o['id']}/resolve", headers=t.gis.headers,
                        json={"resolution": "CLEARED", "notes": "shared field bund, surveyed"})
        assert r.status_code == 200, r.text
    client.post(f"/api/v1/farms/{fid}/ownership/{own['id']}/review", headers=t.gis.headers, json={"status": "VERIFIED", "notes": "ok seen"})
    r = client.post(f"/api/v1/farms/{fid}/verify", headers=t.gis.headers, json={"reason": "verified with cleared overlap"})
    assert r.status_code == 200, r.text
    return r.json()


def test_boundary_derived_from_farms_and_area_is_authoritative(client: TestClient, db: Session) -> None:
    t = team(db, client)
    farmer = active_farmer(client, t, "6100 2000 3000")
    a_geo, b_geo = square(75.10, 22.10, SIZE), square(75.10 + SIZE, 22.10, SIZE)  # adjacent: share one edge
    a = verified_farm(client, t, farmer["id"], a_geo)
    b = verified_farm(client, t, farmer["id"], b_geo)
    p = create_project(client, t)
    assert client.get(f"{PR}/{p['id']}/boundary", headers=t.pm.headers).json()["current"] is None
    add_farm(client, t, p["id"], a["id"])
    add_farm(client, t, p["id"], b["id"])
    view = client.get(f"{PR}/{p['id']}/boundary", headers=t.gis.headers).json()
    cur = view["current"]
    expected = _area_ha(db, a_geo) + _area_ha(db, b_geo)
    assert cur["farm_count"] == 2 and cur["is_valid"] is True and cur["status"] == "CURRENT"
    assert abs(float(cur["area_hectares"]) - expected) < 0.0005          # touching farms: union == sum
    assert float(cur["internal_overlap_hectares"]) < 0.0005
    assert cur["geojson"]["type"] in ("Polygon", "MultiPolygon")
    assert {f["farm_code"] for f in view["farms"]} == {a["farm_code"], b["farm_code"]}
    assert all(f["geojson"]["type"] == "Polygon" for f in view["farms"])
    summary = client.get(f"{PR}/{p['id']}", headers=t.pm.headers).json()
    assert abs(float(summary["area_hectares"]) - expected) < 0.0005 and summary["farm_count"] == 2


def test_overlapping_farms_count_once_and_other_projects_are_flagged(client: TestClient, db: Session) -> None:
    t = team(db, client)
    farmer = active_farmer(client, t, "6200 2000 3000")
    a_geo, b_geo = square(75.20, 22.20, SIZE), square(75.20 + SIZE / 2, 22.20, SIZE)  # B covers half of A
    a = verified_farm(client, t, farmer["id"], a_geo)
    b = _verified_overlapping(client, t, farmer["id"], b_geo)
    p = create_project(client, t, name="Overlap project")
    add_farm(client, t, p["id"], a["id"])
    r = add_farm(client, t, p["id"], b["id"])
    assert r.status_code == 201, r.text  # a reviewed (cleared) overlap is not a conflict
    cur = client.get(f"{PR}/{p['id']}/boundary", headers=t.pm.headers).json()["current"]
    one = _area_ha(db, a_geo)
    assert abs(float(cur["sum_farm_area_hectares"]) - 2 * one) < 0.0005
    assert abs(float(cur["area_hectares"]) - 1.5 * one) < 0.001          # overlap counted once
    assert abs(float(cur["internal_overlap_hectares"]) - 0.5 * one) < 0.001
    assert "overlap each other" in (cur["validation_notes"] or "")
    # A second project containing farm B: its boundary intersects the first project → flagged, not rejected.
    q = create_project(client, t, name="Neighbour project")
    r = add_farm(client, t, q["id"], b["id"])
    assert r.status_code == 409 and r.json()["error_code"] == "CONFLICTS_REQUIRE_ACKNOWLEDGEMENT"
    r = add_farm(client, t, q["id"], b["id"], acknowledge_conflicts=True, conflict_notes="Separate carbon pools; reviewer to confirm")
    assert r.status_code == 201
    qv = client.get(f"{PR}/{q['id']}/boundary", headers=t.pm.headers).json()
    assert [(o["other_project_code"], o["same_organization"]) for o in qv["project_overlaps"]] == [(p["project_code"], True)]
    assert float(qv["project_overlaps"][0]["overlap_area_m2"]) > 0


def test_stale_boundary_recompute_and_review(client: TestClient, db: Session) -> None:
    t = team(db, client)
    farmer = active_farmer(client, t, "6300 2000 3000")
    farm = verified_farm(client, t, farmer["id"], square(75.30, 22.30, SIZE))
    p = create_project(client, t)
    add_farm(client, t, p["id"], farm["id"])
    url = f"{PR}/{p['id']}/boundary"
    # Phase 2 correction of the farm boundary makes the project boundary stale.
    client.post(f"/api/v1/farms/{farm['id']}/reopen", headers=t.agent.headers, json={"reason": "resurvey"})
    set_boundary(client, t.agent.headers, farm["id"], square(75.30, 22.30, SIZE * 2))
    view = client.get(url, headers=t.gis.headers).json()
    assert view["stale"] is True
    r = client.post(f"{url}/review", headers=t.gis.headers, json={"decision": "ACCEPTED", "notes": "looks fine"})
    assert r.status_code == 409 and r.json()["error_code"] == "BOUNDARY_STALE"
    assert client.post(f"{url}/recompute", headers=t.gis.headers).status_code == 403  # GIS reviews, PM recomputes
    view = client.post(f"{url}/recompute", headers=t.pm.headers).json()
    assert view["stale"] is False and view["current"]["version"] == 2 and [v["status"] for v in view["versions"]] == ["CURRENT", "SUPERSEDED"]
    assert float(view["current"]["area_hectares"]) > float(view["versions"][1]["area_hectares"]) * 3.5  # 2x side → ~4x area
    r = client.post(f"{url}/review", headers=t.gis.headers, json={"decision": "ISSUES", "notes": "farm still under correction"})
    assert r.json()["current"]["review_status"] == "ISSUES"


def test_cross_org_project_overlap_details_hidden(client: TestClient, db: Session) -> None:
    """Other organizations' projects intersecting this one are visible as a flag but not identified (spec section 41).
    The cross-organization farm overlap itself is cleared by the Platform GIS Specialist (decision D5)."""
    from tests.conftest import login, make_user
    t = team(db, client)
    o = team(db, client)
    fa = active_farmer(client, t, "6400 2000 3000")
    fb = active_farmer(client, o, "6500 2000 3000")
    a = verified_farm(client, t, fa["id"], square(75.40, 22.40, SIZE))
    pa = create_project(client, t)
    add_farm(client, t, pa["id"], a["id"])
    farm = create_farm(client, o.agent.headers, fb["id"])
    set_boundary(client, o.agent.headers, farm["id"], square(75.40 + SIZE * 0.99, 22.40, SIZE))  # thin sliver over A
    own = add_owner(client, o.agent.headers, farm["id"])
    fid = farm["id"]
    client.post(f"/api/v1/farms/{fid}/submit", headers=o.agent.headers, json={"reason": "ready"})
    client.post(f"/api/v1/farms/{fid}/start-review", headers=o.gis.headers, json={"reason": "start"})
    pgis = login(client, make_user(db, roles=[("PLATFORM_GIS_SPECIALIST", None)]))
    for ov in client.get(f"/api/v1/farms/{fid}/overlaps", headers=pgis).json():
        r = client.post(f"/api/v1/farms/{fid}/overlaps/{ov['id']}/resolve", headers=pgis,
                        json={"resolution": "CLEARED", "notes": "digitising sliver along the shared boundary"})
        assert r.status_code == 200, r.text
    client.post(f"/api/v1/farms/{fid}/ownership/{own['id']}/review", headers=o.gis.headers, json={"status": "VERIFIED", "notes": "ok seen"})
    assert client.post(f"/api/v1/farms/{fid}/verify", headers=o.gis.headers, json={"reason": "verified"}).status_code == 200
    pb = create_project(client, o)
    assert add_farm(client, o, pb["id"], fid).status_code == 201
    ov = client.get(f"{PR}/{pb['id']}/boundary", headers=o.pm.headers).json()["project_overlaps"]
    assert ov and ov[0]["other_project_visible"] is False and ov[0]["other_project_code"] is None and ov[0]["same_organization"] is False
