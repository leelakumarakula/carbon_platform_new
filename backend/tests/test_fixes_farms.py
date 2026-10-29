"""Double-counting fixes on the farm / project side:
D1 an enrolled farm cannot be re-opened or inactivated once its project is past data collection, and an INACTIVE farm still in an
   open project keeps its land in overlap detection;
D2 a farm active in two open projects (or overlapping a farm of another open project) is only acknowledged at enrolment but is a hard
   block for MRV planning;
D3 a baseline control site of any open project cannot join a project."""
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Project, ProjectStratum, StratumFarm
from app.services import project_farm_service as pfs
from tests.phase2 import add_owner, create_farm, set_boundary, square
from tests.phase3 import PR, Team, active_farmer, add_farm, catalog, create_project, rights, team, verified_farm
from tests.phase4 import project_at_activity_selected
from tests.phase5 import MRV, SIZE, MrvCtx, locked_project

FA = "/api/v1/farms"


def _reason(text: str) -> dict:
    return {"reason": text}


def _start(client: TestClient, t: Team, pid: str) -> None:
    assert client.post(f"{PR}/{pid}/start-data-collection", headers=t.pm.headers, json=_reason("collect data")).status_code == 200


def _verified_overlapping(client: TestClient, t: Team, farmer_id: str, geo: dict) -> dict:
    """A farm overlapping an existing one, verified after the GIS reviewer cleared the overlap flag (same organization)."""
    farm = create_farm(client, t.agent.headers, farmer_id)
    set_boundary(client, t.agent.headers, farm["id"], geo)
    own = add_owner(client, t.agent.headers, farm["id"])
    fid = farm["id"]
    client.post(f"{FA}/{fid}/submit", headers=t.agent.headers, json=_reason("ready"))
    client.post(f"{FA}/{fid}/start-review", headers=t.gis.headers, json=_reason("start"))
    for o in client.get(f"{FA}/{fid}/overlaps", headers=t.gis.headers).json():
        r = client.post(f"{FA}/{fid}/overlaps/{o['id']}/resolve", headers=t.gis.headers,
                        json={"resolution": "CLEARED", "notes": "shared field bund, surveyed"})
        assert r.status_code == 200, r.text
    client.post(f"{FA}/{fid}/ownership/{own['id']}/review", headers=t.gis.headers, json={"status": "VERIFIED", "notes": "ok seen"})
    r = client.post(f"{FA}/{fid}/verify", headers=t.gis.headers, json=_reason("verified with cleared overlap"))
    assert r.status_code == 200, r.text
    return r.json()


def _plan(client: TestClient, c: MrvCtx) -> dict:
    """An MRV plan created and submitted (not yet approved)."""
    body = {"project_id": c.project["id"], "monitoring_frequency": "Once per monitoring period", "monitoring_start": "2026-06-01",
            "monitoring_end": "2036-05-31", "quantification_approach": "MEASURE_AND_REMEASURE",
            "measurements": [{"code": "TILL", "name": "Tillage operations", "category": "TILLAGE", "value_type": "CHOICE",
                              "allowed_values": ["CONVENTIONAL", "REDUCED", "NO_TILL"], "level": "FARM"}]}
    r = client.post(f"{MRV}/plans", headers=c.mrv.headers, json=body)
    assert r.status_code == 201, r.text
    assert client.post(f"{MRV}/plans/{r.json()['id']}/submit", headers=c.mrv.headers, json=_reason("ready")).status_code == 200
    return r.json()


def _approve(client: TestClient, c: MrvCtx, plan: dict) -> object:
    return client.post(f"{MRV}/plans/{plan['id']}/approve", headers=c.t.qa.headers,
                       json={"reason": "plan ok", "acknowledge_configuration_gaps": True})


def _mrv_readiness(client: TestClient, c: MrvCtx) -> dict:
    view = client.get(f"{PR}/{c.project['id']}", headers=c.mrv.headers).json()
    target = next(r for r in view["readiness"] if r["target"] == "MRV_PLANNED")
    return next(i for i in target["items"] if i["key"] == "double_counting")


# ---------------------------------------------------------------- D1
def test_enrolled_farm_cannot_be_reopened_or_inactivated_past_data_collection(client: TestClient, db: Session) -> None:
    t = team(db, client)
    p = project_at_activity_selected(client, t, catalog(db), 79.10, 19.10, "7100 2000 3000")
    farm_id = client.get(f"{PR}/{p['id']}/farms", headers=t.pm.headers).json()[0]["farm_id"]
    for action in ("reopen", "inactivate"):
        r = client.post(f"{FA}/{farm_id}/{action}", headers=t.agent.headers, json=_reason("resurvey the plot"))
        assert r.status_code == 409 and r.json()["error_code"] == "FARM_IN_ACTIVE_PROJECT", (action, r.text)
        assert r.json()["details"]["projects"] == [{"project_code": p["project_code"], "status": "ACTIVITY_SELECTED"}]
    assert client.get(f"{FA}/{farm_id}", headers=t.agent.headers).json()["status"] == "VERIFIED"
    # Back in data collection the farm can be corrected again (the project then needs it verified before re-submission).
    assert client.post(f"{PR}/{p['id']}/reopen", headers=t.pm.headers, json=_reason("correct a farm")).json()["status"] == "DATA_COLLECTION"
    r = client.post(f"{FA}/{farm_id}/reopen", headers=t.agent.headers, json=_reason("resurvey the plot"))
    assert r.status_code == 200 and r.json()["status"] == "DRAFT", r.text


def test_closed_project_releases_the_farm(client: TestClient, db: Session) -> None:
    t = team(db, client)
    p = project_at_activity_selected(client, t, catalog(db), 79.20, 19.20, "7200 2000 3000")
    farm_id = client.get(f"{PR}/{p['id']}/farms", headers=t.pm.headers).json()[0]["farm_id"]
    assert client.post(f"{FA}/{farm_id}/inactivate", headers=t.agent.headers, json=_reason("farm sold")).status_code == 409
    assert client.post(f"{PR}/{p['id']}/close", headers=t.pm.headers, json=_reason("project abandoned")).json()["status"] == "CLOSED"
    r = client.post(f"{FA}/{farm_id}/inactivate", headers=t.agent.headers, json=_reason("farm sold"))
    assert r.status_code == 200 and r.json()["status"] == "INACTIVE", r.text


def test_holds_land_sql_matches_the_python_rule() -> None:
    """The GIS queries repeat repositories.projects.holds_land in SQL: their monitored-period states must be the same."""
    import inspect

    from app.repositories import gis
    from app.repositories.projects import MONITORED_PERIOD_STATES
    states = "(" + ", ".join(f"'{x}'" for x in MONITORED_PERIOD_STATES) + ")"
    src = inspect.getsource(gis)
    assert src.count(f"mp.status IN {states}") == 3                       # farm overlaps, project overlaps, cross-project farm overlaps
    assert src.count("status <> 'CLOSED'") == src.count("status <> 'CLOSED' OR EXISTS")     # no query skips the monitored rule


def test_closed_project_that_monitored_keeps_its_credited_dates(client: TestClient, db: Session) -> None:
    """A project that monitored (and may have credited) its land is closed: the land stays taken for its participation dates, which
    end on the closing day; a later project may enrol the farm only from the day after."""
    from datetime import date, timedelta

    from app.models import ProjectFarm
    from tests.phase5 import approved_plan, collecting_period
    c = locked_project(db, client, 79.25, 19.25, "7250 2000 3000", n_farms=1)
    farm = c.farms[0]
    approved_plan(client, c)
    collecting_period(client, c)                                                       # the land was monitored
    assert client.post(f"{PR}/{c.project['id']}/close", headers=c.t.pm.headers, json=_reason("crediting ended")).json()["status"] == "CLOSED"
    pf = db.query(ProjectFarm).filter(ProjectFarm.project_id == uuid.UUID(c.project["id"])).one()
    db.refresh(pf)
    today = date.today()
    assert pf.participation_end == today                                               # open-ended participation ended at closing
    # a new project over the monitored dates: the same farm is double counting (acknowledged at enrolment, blocking MRV planning)
    q = create_project(client, c.t, name="Re-enrolment over credited years")
    _start(client, c.t, q["id"])
    r = add_farm(client, c.t, q["id"], farm["id"])
    assert r.status_code == 409 and r.json()["error_code"] == "CONFLICTS_REQUIRE_ACKNOWLEDGEMENT", r.text
    r = add_farm(client, c.t, q["id"], farm["id"], acknowledge_conflicts=True, conflict_notes="TEST: same years")
    assert r.status_code == 201, r.text
    conflicts = pfs.double_counting_conflicts(db, db.get(Project, uuid.UUID(q["id"])))
    assert [(x["kind"], x["other_project_code"]) for x in conflicts] == [("OTHER_PROJECT_PARTICIPATION", c.project["project_code"])]
    r = client.request("DELETE", f"{PR}/{q['id']}/farms/{farm['id']}", headers=c.t.pm.headers, json=_reason("enrolled over credited years"))
    assert r.status_code == 200, r.text
    # from the day after closing the land is free
    q2 = create_project(client, c.t, name="Enrolment after closing")
    _start(client, c.t, q2["id"])
    r = add_farm(client, c.t, q2["id"], farm["id"], participation_start=(today + timedelta(days=1)).isoformat())
    assert r.status_code == 201, r.text
    assert [x for x in pfs.double_counting_conflicts(db, db.get(Project, uuid.UUID(q2["id"]))) if x["kind"] == "OTHER_PROJECT_PARTICIPATION"
            and x["other_project_code"] == c.project["project_code"]] == []


def test_inactive_farm_still_enrolled_keeps_its_land_in_overlap_detection(client: TestClient, db: Session) -> None:
    t = team(db, client)
    farmer = active_farmer(client, t, "7300 2000 3000")
    enrolled = verified_farm(client, t, farmer["id"], square(79.30, 19.30))
    loose = verified_farm(client, t, farmer["id"], square(79.32, 19.30))
    p = create_project(client, t)
    assert add_farm(client, t, p["id"], enrolled["id"]).status_code == 201
    for f in (enrolled, loose):  # an editable (DRAFT) project does not lock the farm
        r = client.post(f"{FA}/{f['id']}/inactivate", headers=t.agent.headers, json=_reason("duplicate entry"))
        assert r.status_code == 200 and r.json()["status"] == "INACTIVE", r.text
    # The same land drawn again as a new farm: flagged against the still-enrolled inactive farm, not against the loose one.
    redraw = create_farm(client, t.agent.headers, farmer["id"])
    set_boundary(client, t.agent.headers, redraw["id"], square(79.30, 19.30))
    flags = client.get(f"{FA}/{redraw['id']}/overlaps", headers=t.gis.headers).json()
    assert [(o["other_farm_code"], o["status"]) for o in flags] == [(enrolled["farm_code"], "OPEN")]
    redraw2 = create_farm(client, t.agent.headers, farmer["id"])
    set_boundary(client, t.agent.headers, redraw2["id"], square(79.32, 19.30))
    assert client.get(f"{FA}/{redraw2['id']}/overlaps", headers=t.gis.headers).json() == []


# ---------------------------------------------------------------- D2
def test_farm_in_two_projects_blocks_mrv_planning_until_resolved(client: TestClient, db: Session) -> None:
    c = locked_project(db, client, 79.40, 19.40, "7400 2000 3000", n_farms=1)
    farm = c.farms[0]
    q = create_project(client, c.t, name="Second project")
    _start(client, c.t, q["id"])
    r = add_farm(client, c.t, q["id"], farm["id"])
    assert r.status_code == 409 and r.json()["error_code"] == "CONFLICTS_REQUIRE_ACKNOWLEDGEMENT"
    r = add_farm(client, c.t, q["id"], farm["id"], acknowledge_conflicts=True, conflict_notes="Double counting to be assessed later")
    assert r.status_code == 201, r.text  # enrolment is still only acknowledged ...
    conflicts = pfs.double_counting_conflicts(db, db.get(Project, uuid.UUID(c.project["id"])))
    assert [(x["kind"], x["farm_code"], x["other_project_code"]) for x in conflicts] == \
        [("OTHER_PROJECT_PARTICIPATION", farm["farm_code"], q["project_code"])]
    item = _mrv_readiness(client, c)
    assert item["done"] is False and q["project_code"] in item["label"]
    # ... but MRV planning is refused while the conflict is unresolved.
    plan = _plan(client, c)
    r = _approve(client, c, plan)
    assert r.status_code == 409 and r.json()["error_code"] in ("REQUIREMENTS_NOT_MET", "DOUBLE_COUNTING_CONFLICT"), r.text
    assert "double counting" in r.json()["message"].lower()
    db.rollback()  # the test session is shared with the app: drop what the refused request left uncommitted
    assert client.get(f"{PR}/{c.project['id']}", headers=c.mrv.headers).json()["status"] == "METHODOLOGY_CONFIRMED"
    # Resolved by ending the second participation.
    r = client.request("DELETE", f"{PR}/{q['id']}/farms/{farm['id']}", headers=c.t.pm.headers, json=_reason("enrolled in another project"))
    assert r.status_code == 200, r.text
    assert _mrv_readiness(client, c)["done"] is True
    r = _approve(client, c, plan)
    assert r.status_code == 200, r.text
    assert client.get(f"{PR}/{c.project['id']}", headers=c.mrv.headers).json()["status"] == "MRV_PLANNED"


def test_overlapping_farm_in_another_project_blocks_mrv_planning(client: TestClient, db: Session) -> None:
    c = locked_project(db, client, 79.50, 19.50, "7500 2000 3000", n_farms=1)
    mine = c.farms[0]
    # A different farm drawn over half of the project farm; the farm-level flag was cleared for verification.
    other = _verified_overlapping(client, c.t, mine["farmer_id"], square(79.50 + SIZE / 2, 19.50, SIZE))
    q = create_project(client, c.t, name="Neighbour project")
    _start(client, c.t, q["id"])
    assert add_farm(client, c.t, q["id"], other["id"]).status_code == 201  # no conflict shown at enrolment (cleared flag)
    p = db.get(Project, uuid.UUID(c.project["id"]))
    conflicts = pfs.double_counting_conflicts(db, p)
    assert [(x["kind"], x["farm_code"], x["other_farm_code"], x["other_project_code"]) for x in conflicts] == \
        [("PROJECT_BOUNDARY_OVERLAP", mine["farm_code"], other["farm_code"], q["project_code"])]
    assert conflicts[0]["overlap_area_m2"] > 1000
    assert _mrv_readiness(client, c)["done"] is False
    # Participation periods that do not overlap in time are not double counting.
    r = client.request("DELETE", f"{PR}/{q['id']}/farms/{other['id']}", headers=c.t.pm.headers, json=_reason("moved to a past project"))
    assert r.status_code == 200, r.text
    past = create_project(client, c.t, name="Earlier project", start_date="2020-01-01")
    r = add_farm(client, c.t, past["id"], other["id"], participation_start="2020-01-01", participation_end="2025-12-31",
                 carbon_rights=rights(effective_from="2020-01-01"))
    assert r.status_code == 201, r.text
    assert pfs.double_counting_conflicts(db, p) == []
    assert _mrv_readiness(client, c)["done"] is True


# ---------------------------------------------------------------- D3
def test_control_site_of_another_project_cannot_join(client: TestClient, db: Session) -> None:
    t = team(db, client)
    farmer = active_farmer(client, t, "7600 2000 3000")
    farm = verified_farm(client, t, farmer["id"], square(79.60, 19.60))
    a = create_project(client, t, name="Project with the control site")
    b = create_project(client, t, name="Another project")
    stratum = ProjectStratum(project_id=uuid.UUID(a["id"]), record_id=uuid.uuid4(), code="C1", name="Control C1", role="CONTROL",
                             linked_stratum_record_ids="[]", status="APPROVED")
    db.add(stratum)
    db.flush()
    db.add(StratumFarm(stratum_id=stratum.id, farm_id=uuid.UUID(farm["id"]), farm_boundary_id=uuid.UUID(farm["current_boundary"]["id"])))
    db.flush()
    r = add_farm(client, t, b["id"], farm["id"])
    assert r.status_code == 409 and r.json()["error_code"] == "FARM_IS_CONTROL_SITE", r.text
    assert r.json()["details"]["control_site_of"] == [a["project_code"]]
    eligible = {x["farm_id"]: x for x in client.get(f"{PR}/{b['id']}/farms/eligible", headers=t.pm.headers).json()}
    assert eligible[farm["id"]]["eligible"] is False and any("control site" in x for x in eligible[farm["id"]]["reasons"])
    assert add_farm(client, t, a["id"], farm["id"]).json()["error_code"] == "FARM_IS_CONTROL_SITE"  # same project, as before
    # A closed project no longer holds the farm as a control site.
    assert client.post(f"{PR}/{a['id']}/close", headers=t.pm.headers, json=_reason("project abandoned")).json()["status"] == "CLOSED"
    assert add_farm(client, t, b["id"], farm["id"]).status_code == 201
