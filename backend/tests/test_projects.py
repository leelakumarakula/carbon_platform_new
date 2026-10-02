"""Phase 3 — projects: creation, RBAC & isolation, farms (eligibility, conflicts, removal), team, standard/activity
references, crediting period, baseline metadata, carbon rights, documents, workflow, status history and audit."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import AuditLog, Project, ProjectStatusHistory, WorkflowEvent
from app.services.workflows import PROJECT_MACHINE
from tests.conftest import Actor, login, make_org, make_user
from tests.phase2 import create_farm, set_boundary, square, staff, upload
from tests.phase3 import (
    PR,
    Team,
    active_farmer,
    add_farm,
    catalog,
    create_project,
    rights,
    team,
    upload_project_doc,
    verified_farm,
)


@pytest.fixture()
def t(db: Session, client: TestClient) -> Team:
    return team(db, client)


@pytest.fixture()
def farmer(client: TestClient, t: Team) -> dict:
    return active_farmer(client, t, "4100 2000 3000")


def _actions(db: Session, project_id: str) -> set[str]:
    return set(db.scalars(select(AuditLog.action).where(AuditLog.entity_type == "project", AuditLog.entity_id == project_id)).all())


def _start(client: TestClient, t: Team, p: dict) -> dict:
    r = client.post(f"{PR}/{p['id']}/start-data-collection", headers=t.pm.headers, json={"reason": "collecting farm data"})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------- create / update / RBAC
def test_create_and_update_project(client: TestClient, db: Session, t: Team) -> None:
    p = create_project(client, t)
    assert p["project_code"].startswith("PRJ-") and p["status"] == "DRAFT" and p["methodology_status"] == "NOT_SELECTED"
    assert p["environment"] == "LIVE" and p["can_manage"] is True and p["farm_count"] == 0
    team_rows = client.get(f"{PR}/{p['id']}/participants", headers=t.pm.headers).json()
    assert [(x["project_role"], x["user_id"]) for x in team_rows] == [("PROJECT_MANAGER", str(t.pm.user.id))]  # creator joins the team
    r = client.patch(f"{PR}/{p['id']}", headers=t.pm.headers, json={"name": "Nashik regenerative pilot", "region": "Niphad"})
    assert r.status_code == 200 and r.json()["name"] == "Nashik regenerative pilot"
    assert {"PROJECT_CREATED", "PROJECT_UPDATED", "PROJECT_PARTICIPANT_ADDED"} <= _actions(db, p["id"])
    hist = client.get(f"{PR}/{p['id']}/status-history", headers=t.pm.headers).json()
    assert [(h["from_status"], h["to_status"], h["action"]) for h in hist] == [(None, "DRAFT", "PROJECT_CREATED")]
    bad = client.post(PR, headers=t.pm.headers, json={"organization_id": str(t.org.id), "name": "x", "project_type": "MAGIC", "country": "IN"})
    assert bad.status_code == 422


def test_rbac_and_organization_isolation(client: TestClient, db: Session, t: Team) -> None:
    p = create_project(client, t)
    pid = p["id"]
    # Field agent, GIS, QA, MRV, finance and field supervisor can read; only the PM manages.
    for role in ("FIELD_AGENT", "GIS_SPECIALIST", "QA_OFFICER", "MRV_MANAGER", "FINANCE_MANAGER", "FIELD_SUPERVISOR"):
        a = staff(db, client, t.org, role)
        assert client.get(f"{PR}/{pid}", headers=a.headers).status_code == 200, role
        r = client.patch(f"{PR}/{pid}", headers=a.headers, json={"name": "Hijacked"})
        assert r.status_code == 403, role
        assert client.post(f"{PR}/{pid}/start-data-collection", headers=a.headers, json={"reason": "go go"}).status_code == 403, role
    assert client.post(PR, headers=t.agent.headers, json={"organization_id": str(t.org.id), "name": "Agent project",
                                                           "project_type": "OTHER", "country": "IN"}).status_code == 403
    # Another developer's PM cannot see or touch it, and cannot create in this organization.
    other = team(db, client)
    assert client.get(f"{PR}/{pid}", headers=other.pm.headers).status_code == 404
    assert client.patch(f"{PR}/{pid}", headers=other.pm.headers, json={"name": "Renamed"}).status_code == 404
    assert pid not in {x["id"] for x in client.get(PR, headers=other.pm.headers, params={"page_size": 100}).json()["items"]}
    r = client.post(PR, headers=other.pm.headers, json={"organization_id": str(t.org.id), "name": "Intruder", "project_type": "OTHER",
                                                       "country": "IN"})
    assert r.status_code == 403
    # Platform roles: Methodology Specialist and Platform Admin can view (Phase 3), not manage.
    for role in ("METHODOLOGY_SPECIALIST", "PLATFORM_ADMIN", "SUPPORT"):
        u = make_user(db, roles=[(role, None)])
        h = login(client, u)
        assert client.get(f"{PR}/{pid}", headers=h).status_code == 200, role
        assert client.patch(f"{PR}/{pid}", headers=h, json={"name": "Renamed"}).status_code == 403, role
    # Buyers and farmers have no project access.
    buyer = make_user(db, roles=[("BUYER", make_org(db, org_type="BUYER"))])
    bh = login(client, buyer)
    assert client.get(PR, headers=bh).status_code == 403 and client.get(f"{PR}/{pid}", headers=bh).status_code == 403
    assert client.get(f"{PR}/{pid}/farms", headers=bh).status_code == 403
    farmer_user = make_user(db, roles=[("FARMER", make_org(db, org_type="FARMER_GROUP"))])
    fh = login(client, farmer_user)
    assert client.get(PR, headers=fh).status_code == 403
    assert client.post(PR, headers=fh, json={"organization_id": str(t.org.id), "name": "Mine", "project_type": "OTHER",
                                             "country": "IN"}).status_code == 403


# ---------------------------------------------------------------- farms
def test_add_farm_rules(client: TestClient, db: Session, t: Team, farmer: dict) -> None:
    p = create_project(client, t)
    pid = p["id"]
    unverified = verified_farm(client, t, farmer["id"], square(74.10, 21.10), verify=False)
    r = add_farm(client, t, pid, unverified["id"])
    assert r.status_code == 409 and r.json()["error_code"] == "FARM_NOT_VERIFIED"
    # A verified farm whose farmer is not ACTIVE (KYC verified only).
    from tests.phase2 import kyc_verified_farmer
    kyc_only = kyc_verified_farmer(client, t.agent, t.qa, t.org, id_number="4100 2000 3999")
    f2 = verified_farm(client, t, kyc_only["id"], square(74.12, 21.10))
    r = add_farm(client, t, pid, f2["id"])
    assert r.status_code == 409 and r.json()["error_code"] == "FARMER_NOT_ACTIVE"
    # Another organization's farm is invisible.
    other = team(db, client)
    of = verified_farm(client, other, active_farmer(client, other, "5100 2000 3000")["id"], square(74.14, 21.10))
    assert add_farm(client, t, pid, of["id"]).json()["error_code"] == "FARM_NOT_FOUND"
    # Carbon-rights evidence and valid dates are required.
    good = verified_farm(client, t, farmer["id"], square(74.16, 21.10))
    r = add_farm(client, t, pid, good["id"], carbon_rights={"holder_type": "FARMER", "effective_from": "2026-06-01"})
    assert r.status_code == 422
    r = add_farm(client, t, pid, good["id"], participation_start="2026-06-01", participation_end="2026-01-01")
    assert r.status_code == 422
    ok = add_farm(client, t, pid, good["id"])
    assert ok.status_code == 201, ok.text
    body = ok.json()
    assert body["status"] == "ACTIVE" and body["farm_boundary_id"] == good["current_boundary"]["id"]
    assert body["carbon_rights"][0]["holder_name"] == farmer["full_name"] and body["carbon_rights"][0]["verification_status"] == "UNVERIFIED"
    assert add_farm(client, t, pid, good["id"]).json()["error_code"] == "FARM_ALREADY_IN_PROJECT"
    eligible = {x["farm_id"]: x for x in client.get(f"{PR}/{pid}/farms/eligible", headers=t.pm.headers).json()}
    assert eligible[unverified["id"]]["eligible"] is False and good["id"] not in eligible
    assert {"PROJECT_FARM_ADDED", "PROJECT_CARBON_RIGHT_CREATED", "PROJECT_BOUNDARY_COMPUTED"} <= _actions(db, pid)


def test_conflicts_are_shown_and_acknowledged_not_auto_rejected(client: TestClient, db: Session, t: Team, farmer: dict) -> None:
    farm = verified_farm(client, t, farmer["id"], square(74.20, 21.20))
    a = create_project(client, t, name="Project A")
    b = create_project(client, t, name="Project B")
    assert add_farm(client, t, a["id"], farm["id"]).status_code == 201
    r = add_farm(client, t, b["id"], farm["id"])
    assert r.status_code == 409 and r.json()["error_code"] == "CONFLICTS_REQUIRE_ACKNOWLEDGEMENT"
    conflict = r.json()["details"]["conflicts"][0]
    assert conflict["kind"] == "OTHER_PROJECT_PARTICIPATION" and conflict["other_project_code"] == a["project_code"]
    r = add_farm(client, t, b["id"], farm["id"], acknowledge_conflicts=True,
                 conflict_notes="Different practice changes; double counting to be assessed in eligibility review")
    assert r.status_code == 201 and r.json()["conflicts_acknowledged"] is True and r.json()["conflicts"]
    # A participation that does not overlap in time is not a conflict.
    c = create_project(client, t, name="Project C")
    later = {"participation_start": "2040-01-01", "carbon_rights": rights(effective_from="2040-01-01")}
    a_farm = client.get(f"{PR}/{a['id']}/farms", headers=t.pm.headers).json()[0]
    assert a_farm["participation_end"] is None
    r = add_farm(client, t, c["id"], farm["id"], **later)
    assert r.status_code == 409  # A's participation is open-ended, so 2040 still overlaps


def test_remove_farm_keeps_history(client: TestClient, db: Session, t: Team, farmer: dict) -> None:
    p = create_project(client, t)
    f1 = verified_farm(client, t, farmer["id"], square(74.30,21.30))
    f2 = verified_farm(client, t, farmer["id"], square(74.31, 21.30))
    add_farm(client, t, p["id"], f1["id"])
    add_farm(client, t, p["id"], f2["id"])
    assert client.get(f"{PR}/{p['id']}/boundary", headers=t.pm.headers).json()["current"]["farm_count"] == 2
    r = client.request("DELETE", f"{PR}/{p['id']}/farms/{f1['id']}", headers=t.pm.headers, json={"reason": "farmer withdrew"})
    assert r.status_code == 200 and r.json()["status"] == "REMOVED" and r.json()["removal_reason"] == "farmer withdrew"
    assert [c["status"] for c in r.json()["carbon_rights"]] == ["ENDED"]
    assert client.request("DELETE", f"{PR}/{p['id']}/farms/{f1['id']}", headers=t.pm.headers, json={"reason": "again"}).status_code == 404
    active = client.get(f"{PR}/{p['id']}/farms", headers=t.pm.headers).json()
    everything = client.get(f"{PR}/{p['id']}/farms", headers=t.pm.headers, params={"include_removed": True}).json()
    assert len(active) == 1 and len(everything) == 2
    view = client.get(f"{PR}/{p['id']}/boundary", headers=t.pm.headers).json()
    assert view["current"]["farm_count"] == 1 and len(view["versions"]) == 3 and view["stale"] is False
    assert "PROJECT_FARM_REMOVED" in _actions(db, p["id"])


# ---------------------------------------------------------------- team
def test_participants(client: TestClient, db: Session, t: Team) -> None:
    p = create_project(client, t)
    url = f"{PR}/{p['id']}/participants"
    r = client.post(url, headers=t.pm.headers, json={"user_id": str(t.qa.user.id), "project_role": "QA_OFFICER"})
    assert r.status_code == 201, r.text
    qa_part = r.json()
    assert client.post(url, headers=t.pm.headers, json={"user_id": str(t.qa.user.id), "project_role": "QA_OFFICER"}).json()["error_code"] \
        == "PARTICIPANT_EXISTS"
    # Project roles never grant permissions: the user must already hold the role.
    r = client.post(url, headers=t.pm.headers, json={"user_id": str(t.qa.user.id), "project_role": "MRV_MANAGER"})
    assert r.status_code == 422 and r.json()["error_code"] == "ROLE_NOT_HELD"
    outsider = team(db, client)
    assert client.post(url, headers=t.pm.headers, json={"user_id": str(outsider.qa.user.id), "project_role": "QA_OFFICER"}).status_code == 404
    meth = make_user(db, roles=[("METHODOLOGY_SPECIALIST", None)])
    assert client.post(url, headers=t.pm.headers, json={"user_id": str(meth.id), "project_role": "METHODOLOGY_SPECIALIST"}).status_code == 201
    cands = {c["user_id"]: c["roles"] for c in client.get(f"{url}/candidates", headers=t.pm.headers).json()}
    assert cands[str(t.gis.user.id)] == ["GIS_SPECIALIST"] and str(meth.id) in cands
    r = client.patch(f"{url}/{qa_part['id']}", headers=t.pm.headers, json={"notes": "Leads dataset QA", "end_date": "2027-12-31"})
    assert r.status_code == 200 and r.json()["notes"] == "Leads dataset QA"
    assert client.patch(f"{url}/{qa_part['id']}", headers=t.pm.headers, json={"status": "REMOVED"}).json()["error_code"] == "REASON_REQUIRED"
    r = client.patch(f"{url}/{qa_part['id']}", headers=t.pm.headers, json={"status": "REMOVED", "reason": "moved to another project"})
    assert r.json()["status"] == "REMOVED"
    assert client.patch(f"{url}/{qa_part['id']}", headers=t.agent.headers, json={"notes": "x"}).status_code == 403
    assert {"PROJECT_PARTICIPANT_ADDED", "PROJECT_PARTICIPANT_UPDATED", "PROJECT_PARTICIPANT_REMOVED"} <= _actions(db, p["id"])


# ---------------------------------------------------------------- standard / activity
def test_standard_and_activity_linkage(client: TestClient, db: Session, t: Team) -> None:
    cat = catalog(db)
    demo = catalog(db, environment="DEMO")
    p = create_project(client, t)
    pid = p["id"]
    r = client.post(f"{PR}/{pid}/activity", headers=t.pm.headers, json={"activity_id": str(cat["a1"].id)})
    assert r.json()["error_code"] == "STANDARD_REQUIRED"
    assert client.post(f"{PR}/{pid}/standard", headers=t.pm.headers, json={"standard_id": str(demo["s1"].id)}).json()["error_code"] \
        == "ENVIRONMENT_MISMATCH"
    assert client.post(f"{PR}/{pid}/standard", headers=t.agent.headers, json={"standard_id": str(cat["s1"].id)}).status_code == 403
    r = client.post(f"{PR}/{pid}/standard", headers=t.pm.headers, json={"standard_id": str(cat["s1"].id)})
    assert r.status_code == 200 and r.json()["standard_id"] == str(cat["s1"].id)
    avail = client.get(f"{PR}/{pid}/activities", headers=t.pm.headers).json()
    assert {a["id"] for a in avail["available"]} == {str(cat["a1"].id), str(cat["a2"].id)} and avail["methodology_status"] == "NOT_SELECTED"
    assert client.post(f"{PR}/{pid}/activity", headers=t.pm.headers, json={"activity_id": str(cat["a1"].id)}).json()["activity_id"] \
        == str(cat["a1"].id)
    # Switching to a standard that does not offer the activity clears it (history kept).
    r = client.post(f"{PR}/{pid}/standard", headers=t.pm.headers, json={"standard_id": str(cat["s2"].id), "reason": "compliance route"})
    assert r.json()["activity_id"] is None
    r = client.post(f"{PR}/{pid}/activity", headers=t.pm.headers, json={"activity_id": str(cat["a1"].id)})
    assert r.status_code == 422 and r.json()["error_code"] == "ACTIVITY_NOT_IN_STANDARD"
    assert client.post(f"{PR}/{pid}/activity", headers=t.pm.headers, json={"activity_id": str(cat["a2"].id)}).status_code == 200
    stds = client.get(f"{PR}/{pid}/standards", headers=t.pm.headers).json()
    assert stds["current"]["id"] == str(cat["s2"].id) and [h["is_current"] for h in stds["history"]] == [True, False]
    acts = client.get(f"{PR}/{pid}/activities", headers=t.pm.headers).json()
    assert len(acts["history"]) == 2 and acts["current"]["id"] == str(cat["a2"].id)
    assert {"PROJECT_STANDARD_SELECTED", "PROJECT_ACTIVITY_SELECTED", "PROJECT_ACTIVITY_CLEARED"} <= _actions(db, pid)


def test_catalog_management(client: TestClient, db: Session, admin: Actor, t: Team) -> None:
    r = client.post("/api/v1/standards", headers=t.pm.headers, json={"code": "X-STD", "name": "X std", "program_type": "OTHER"})
    assert r.status_code == 403
    s = client.post("/api/v1/standards", headers=admin.headers, json={"code": "test-std", "name": "Test standard", "program_type": "VOLUNTARY",
                                                                      "source_url": "https://example.org/standard"})
    assert s.status_code == 201 and s.json()["code"] == "TEST-STD"
    a = client.post("/api/v1/activities", headers=admin.headers, json={"code": "test-act", "name": "Test activity",
                                                                       "standard_ids": [s.json()["id"]]})
    assert a.status_code == 201 and a.json()["standard_ids"] == [s.json()["id"]]
    assert client.post(f"/api/v1/activities/{a.json()['id']}/standards", headers=admin.headers,
                       json={"standard_id": s.json()["id"]}).json()["error_code"] == "ALREADY_LINKED"
    listed = client.get("/api/v1/activities", headers=t.pm.headers, params={"standard_id": s.json()["id"]}).json()
    assert [x["code"] for x in listed] == ["TEST-ACT"]
    off = client.patch(f"/api/v1/standards/{s.json()['id']}", headers=admin.headers, json={"status": "INACTIVE"})
    assert off.json()["status"] == "INACTIVE"
    p = create_project(client, t)
    assert client.post(f"{PR}/{p['id']}/standard", headers=t.pm.headers, json={"standard_id": s.json()["id"]}).json()["error_code"] \
        == "STANDARD_INACTIVE"


# ---------------------------------------------------------------- crediting period / baseline
def test_crediting_period_and_baseline(client: TestClient, db: Session, t: Team) -> None:
    p = create_project(client, t)
    url = f"{PR}/{p['id']}/crediting-period"
    assert client.post(url, headers=t.pm.headers, json={"start_date": "2026-06-01", "end_date": "2026-06-01"}).status_code == 422
    c1 = client.post(url, headers=t.pm.headers, json={"start_date": "2026-06-01", "end_date": "2036-05-31"})
    assert c1.status_code == 201 and c1.json()["period_number"] == 1 and c1.json()["status"] == "PROPOSED"
    clash = client.post(url, headers=t.pm.headers, json={"start_date": "2030-01-01", "end_date": "2040-01-01"})
    assert clash.status_code == 409 and clash.json()["error_code"] == "CREDITING_PERIOD_OVERLAP"
    assert client.post(url, headers=t.pm.headers, json={"start_date": "2026-07-01", "end_date": "2036-06-30",
                                                        "replaces_id": c1.json()["id"]}).json()["error_code"] == "REASON_REQUIRED"
    c2 = client.post(url, headers=t.pm.headers, json={"start_date": "2026-07-01", "end_date": "2036-06-30", "replaces_id": c1.json()["id"],
                                                      "reason": "start aligned to kharif sowing"})
    assert c2.status_code == 201 and c2.json()["replaces_id"] == c1.json()["id"]
    assert [(x["period_number"], x["status"]) for x in client.get(url, headers=t.pm.headers).json()] == [(1, "SUPERSEDED"), (2, "PROPOSED")]
    b = f"{PR}/{p['id']}/baseline"
    assert client.get(b, headers=t.pm.headers).json()["current"] is None
    r = client.patch(b, headers=t.pm.headers, json={"period_start": "2021-06-01", "period_end": "2026-05-31",
                                                    "description": "Conventional tillage, residue burning", "data_sources": "Farmer survey"})
    assert r.status_code == 200 and r.json()["current"]["version"] == 1
    assert "No baseline emissions or removals are calculated" in r.json()["note"]
    assert client.patch(b, headers=t.pm.headers, json={"period_start": "2020-06-01", "period_end": "2026-05-31"}).json()["error_code"] \
        == "REASON_REQUIRED"
    r = client.patch(b, headers=t.pm.headers, json={"period_start": "2020-06-01", "period_end": "2026-05-31", "reason": "five full seasons"})
    assert [v["version"] for v in r.json()["versions"]] == [2, 1] and r.json()["current"]["period_start"] == "2020-06-01"
    assert {"PROJECT_CREDITING_PERIOD_CREATED", "PROJECT_CREDITING_PERIOD_SUPERSEDED", "PROJECT_BASELINE_UPDATED"} <= _actions(db, p["id"])


# ---------------------------------------------------------------- carbon rights & documents
def test_carbon_rights_records(client: TestClient, db: Session, t: Team, farmer: dict) -> None:
    p = create_project(client, t)
    farm = verified_farm(client, t, farmer["id"], square(74.40, 21.40))
    pf = add_farm(client, t, p["id"], farm["id"], carbon_rights=rights(share_pct="60")).json()
    url = f"{PR}/{p['id']}/carbon-rights"
    # An unsigned agreement cannot evidence rights.
    ag = client.post(f"/api/v1/farmers/{farmer['id']}/agreements", headers=t.agent.headers,
                     json={"agreement_type": "CARBON_PARTICIPATION", "template_version": "CPA-1"}).json()["agreements"][0]
    r = client.post(url, headers=t.pm.headers, json={"project_farm_id": pf["id"], "holder_type": "LANDOWNER", "holder_name": "Ramesh Patil",
                                                     "agreement_id": ag["id"], "effective_from": "2026-06-01"})
    assert r.json()["error_code"] == "AGREEMENT_NOT_SIGNED"
    doc = upload_project_doc(client, t, p["id"], "CARBON_RIGHTS")
    too_much = {"project_farm_id": pf["id"], "holder_type": "LANDOWNER", "holder_name": "Ramesh Patil", "document_id": doc,
                "share_pct": "50", "effective_from": "2026-06-01"}
    assert client.post(url, headers=t.pm.headers, json=too_much).json()["error_code"] == "SHARE_EXCEEDS_100"
    r = client.post(url, headers=t.pm.headers, json=too_much | {"share_pct": "40"})
    assert r.status_code == 201 and r.json()["holder_type"] == "LANDOWNER"
    landowner = r.json()
    # Review: the recorder cannot review; QA can.
    pm_qa = staff(db, client, t.org, "PROJECT_MANAGER", "QA_OFFICER")
    mine = client.post(url, headers=pm_qa.headers, json={"project_farm_id": pf["id"], "holder_type": "OTHER", "holder_name": "Village trust",
                                                         "reference": "Panchayat letter 12/2026", "effective_from": "2026-06-01"}).json()
    r = client.post(f"{url}/{mine['id']}/review", headers=pm_qa.headers, json={"status": "VERIFIED", "notes": "letter seen"})
    assert r.status_code == 403 and r.json()["error_code"] == "SEPARATION_OF_DUTIES"
    assert client.post(f"{url}/{landowner['id']}/review", headers=t.pm.headers, json={"status": "VERIFIED", "notes": "x seen"}).status_code == 403
    r = client.post(f"{url}/{landowner['id']}/review", headers=t.qa.headers, json={"status": "VERIFIED", "notes": "lease and assignment seen"})
    assert r.json()["verification_status"] == "VERIFIED"
    r = client.post(f"{url}/{mine['id']}/end", headers=t.pm.headers, json={"status": "VOID", "reason": "recorded in error"})
    assert r.json()["status"] == "VOID"
    listed = client.get(url, headers=t.agent.headers).json()
    assert len(listed) == 3 and all(x["farm_code"] == farm["farm_code"] for x in listed)
    assert {"PROJECT_CARBON_RIGHT_CREATED", "PROJECT_CARBON_RIGHT_REVIEWED", "PROJECT_CARBON_RIGHT_ENDED"} <= _actions(db, p["id"])


def test_project_documents(client: TestClient, db: Session, t: Team) -> None:
    p = create_project(client, t)
    doc = upload_project_doc(client, t, p["id"])
    r = upload(client, t.pm.headers, f"{PR}/{p['id']}/documents", "KYC_ID")
    assert r.status_code == 422 and r.json()["error_code"] == "INVALID_CATEGORY"
    listed = client.get(f"{PR}/{p['id']}/documents", headers=t.agent.headers).json()
    assert [d["id"] for d in listed["documents"]] == [doc] and "PROJECT_DESIGN" in listed["categories"]
    assert client.get(f"/api/v1/evidence/documents/{doc}/download", headers=t.agent.headers).status_code == 200
    other = team(db, client)
    assert client.get(f"/api/v1/evidence/documents/{doc}", headers=other.pm.headers).status_code == 404
    assert "PROJECT_DOCUMENT_ADDED" in _actions(db, p["id"])


# ---------------------------------------------------------------- workflow
def test_workflow_transitions_status_history_and_audit(client: TestClient, db: Session, t: Team, farmer: dict) -> None:
    cat = catalog(db)
    p = create_project(client, t)
    pid = p["id"]
    _start(client, t, p)
    r = client.post(f"{PR}/{pid}/submit", headers=t.pm.headers, json={"reason": "ready for review"})
    assert r.status_code == 409 and r.json()["error_code"] == "REQUIREMENTS_NOT_MET"
    assert "At least one participating farm" in r.json()["details"]["missing"]
    f1 = verified_farm(client, t, farmer["id"], square(74.50,21.50))
    assert add_farm(client, t, pid, f1["id"]).status_code == 201
    client.post(f"{PR}/{pid}/standard", headers=t.pm.headers, json={"standard_id": str(cat["s1"].id)})
    client.post(f"{PR}/{pid}/activity", headers=t.pm.headers, json={"activity_id": str(cat["a1"].id)})
    client.post(f"{PR}/{pid}/crediting-period", headers=t.pm.headers, json={"start_date": "2026-06-01", "end_date": "2036-05-31"})
    client.patch(f"{PR}/{pid}/baseline", headers=t.pm.headers, json={"period_start": "2021-06-01", "period_end": "2026-05-31"})
    ready = client.get(f"{PR}/{pid}", headers=t.pm.headers).json()["readiness"]
    sub = next(x for x in ready if x["target"] == "ELIGIBILITY_REVIEW")
    assert sub["ready"] is True and [i["key"] for i in sub["items"] if not i["done"]] == ["design_doc"]  # recommended only
    r = client.post(f"{PR}/{pid}/submit", headers=t.pm.headers, json={"reason": "all project data recorded"})
    assert r.status_code == 200 and r.json()["status"] == "ELIGIBILITY_REVIEW"
    # Locked while under review.
    assert client.patch(f"{PR}/{pid}/baseline", headers=t.pm.headers,
                        json={"period_start": "2021-06-01", "period_end": "2026-05-31", "reason": "x y"}).json()["error_code"] == "PROJECT_NOT_EDITABLE"
    assert client.post(f"{PR}/{pid}/approve-eligibility", headers=t.pm.headers, json={"reason": "fine fine"}).status_code == 403
    r = client.post(f"{PR}/{pid}/approve-eligibility", headers=t.qa.headers, json={"reason": "eligible"})
    assert r.status_code == 409 and set(r.json()["details"]["missing"]) == {"GIS review accepted the current project boundary",
                                                                            "All active carbon-rights records are verified"}
    assert client.post(f"{PR}/{pid}/boundary/review", headers=t.qa.headers, json={"decision": "ACCEPTED", "notes": "ok ok"}).status_code == 403
    assert client.post(f"{PR}/{pid}/boundary/review", headers=t.gis.headers,
                       json={"decision": "ACCEPTED", "notes": "union matches farm polygons"}).status_code == 200
    cr = client.get(f"{PR}/{pid}/carbon-rights", headers=t.qa.headers).json()[0]
    client.post(f"{PR}/{pid}/carbon-rights/{cr['id']}/review", headers=t.qa.headers, json={"status": "VERIFIED", "notes": "agreement clause seen"})
    r = client.post(f"{PR}/{pid}/approve-eligibility", headers=t.qa.headers, json={"reason": "eligible for the selected route"})
    assert r.status_code == 200 and r.json()["status"] == "STANDARD_SELECTED" and r.json()["eligibility_reviewed_by"] == str(t.qa.user.id)
    r = client.post(f"{PR}/{pid}/confirm-activity", headers=t.pm.headers, json={"reason": "activity confirmed"})
    assert r.json()["status"] == "ACTIVITY_SELECTED" and r.json()["methodology_status"] == "NOT_SELECTED"
    assert r.json()["allowed_transitions"] == ["CLOSED", "DATA_COLLECTION", "METHODOLOGY_REVIEW"]  # Phase 4 adds methodology review
    r = client.post(f"{PR}/{pid}/reopen", headers=t.pm.headers, json={"reason": "add another farm"})
    assert r.json()["status"] == "DATA_COLLECTION" and r.json()["eligibility_reviewed_by"] is None
    hist = client.get(f"{PR}/{pid}/status-history", headers=t.agent.headers).json()
    assert [h["to_status"] for h in hist] == ["DRAFT", "DATA_COLLECTION", "ELIGIBILITY_REVIEW", "STANDARD_SELECTED", "ACTIVITY_SELECTED",
                                              "DATA_COLLECTION"]
    assert hist[2]["action"] == "SUBMITTED_FOR_ELIGIBILITY_REVIEW" and hist[2]["reason"] == "all project data recorded"
    assert all(h["request_id"] for h in hist) and hist[3]["changed_by_name"]
    events = db.scalars(select(WorkflowEvent).where(WorkflowEvent.entity_type == "project", WorkflowEvent.entity_id == pid)).all()
    assert len(events) == 5 and all(e.user_id and e.request_id for e in events)  # five transitions after creation
    assert {"PROJECT_CREATED", "PROJECT_SUBMITTED", "PROJECT_STATUS_CHANGED", "PROJECT_FARM_ADDED", "PROJECT_STANDARD_SELECTED",
            "PROJECT_ACTIVITY_SELECTED", "PROJECT_CREDITING_PERIOD_CREATED", "PROJECT_BASELINE_UPDATED", "PROJECT_CARBON_RIGHT_CREATED",
            "PROJECT_BOUNDARY_REVIEWED"} <= _actions(db, pid)


def test_submitter_cannot_approve_and_return_path(client: TestClient, db: Session, t: Team, farmer: dict) -> None:
    cat = catalog(db)
    both = staff(db, client, t.org, "PROJECT_MANAGER", "QA_OFFICER")
    bt = Team(t.org, both, t.qa, t.gis, t.agent)
    p = create_project(client, bt)
    pid = p["id"]
    _start(client, bt, p)
    f1 = verified_farm(client, t, farmer["id"], square(74.60, 21.60))
    add_farm(client, bt, pid, f1["id"])
    client.post(f"{PR}/{pid}/standard", headers=both.headers, json={"standard_id": str(cat["s1"].id)})
    client.post(f"{PR}/{pid}/activity", headers=both.headers, json={"activity_id": str(cat["a1"].id)})
    client.post(f"{PR}/{pid}/crediting-period", headers=both.headers, json={"start_date": "2026-06-01", "end_date": "2036-05-31"})
    client.patch(f"{PR}/{pid}/baseline", headers=both.headers, json={"period_start": "2021-06-01", "period_end": "2026-05-31"})
    assert client.post(f"{PR}/{pid}/submit", headers=both.headers, json={"reason": "ready now"}).status_code == 200
    r = client.post(f"{PR}/{pid}/approve-eligibility", headers=both.headers, json={"reason": "self approval"})
    assert r.status_code == 403 and r.json()["error_code"] == "SEPARATION_OF_DUTIES"
    r = client.post(f"{PR}/{pid}/return", headers=t.qa.headers, json={"reason": "carbon-rights evidence missing"})
    assert r.json()["status"] == "DATA_COLLECTION" and r.json()["review_notes"] == "carbon-rights evidence missing"
    r = client.post(f"{PR}/{pid}/close", headers=both.headers, json={"reason": "programme cancelled"})
    assert r.json()["status"] == "CLOSED" and r.json()["allowed_transitions"] == []


def test_no_transitions_into_later_phase_states() -> None:
    reachable, frontier = {"DRAFT"}, ["DRAFT"]
    while frontier:
        s = frontier.pop()
        for n in PROJECT_MACHINE.allowed_from(s):
            if n not in reachable:
                reachable.add(n)
                frontier.append(n)
    assert reachable == {"DRAFT", "DATA_COLLECTION", "ELIGIBILITY_REVIEW", "STANDARD_SELECTED", "ACTIVITY_SELECTED", "CLOSED",
                         "METHODOLOGY_REVIEW", "METHODOLOGY_CONFIRMED"}  # Phase 4 boundary
    assert not reachable & {"MRV_PLANNED", "CALCULATED", "VERIFIED", "ISSUED", "ACTIVE"}


def test_status_history_is_append_only() -> None:
    """THROW inside the trigger aborts the whole transaction, so use a dedicated connection (rolled back)."""
    from sqlalchemy.exc import DBAPIError

    from app.core.database import get_engine
    from app.models import Organization
    with get_engine().connect() as conn:
        trans = conn.begin()
        s = Session(bind=conn)
        org = Organization(code="APPEND-ONLY-T", name="Append only test", org_type="PROJECT_DEVELOPER")
        s.add(org)
        s.flush()
        prj = Project(project_code="PRJ-TEST-APPEND", name="Append only", project_type="OTHER", organization_id=org.id, country="IN")
        s.add(prj)
        s.flush()
        s.add(ProjectStatusHistory(project_id=prj.id, from_status=None, to_status="DRAFT", action="PROJECT_CREATED"))
        s.flush()
        for stmt in ("UPDATE dbo.project_status_history SET reason = N'x'", "DELETE FROM dbo.project_status_history"):
            with pytest.raises(DBAPIError) as e:
                conn.execute(text(stmt))
            assert "append-only" in str(e.value)
            break  # the THROW aborts the transaction; one statement proves it
        if trans.is_active:
            trans.rollback()


# ---------------------------------------------------------------- farmer self-service / buyer
def test_farmer_sees_only_own_participation(client: TestClient, db: Session, t: Team, farmer: dict) -> None:
    group = make_org(db, org_type="FARMER_GROUP")
    user = make_user(db, roles=[("FARMER", group)])
    assert client.post(f"/api/v1/farmers/{farmer['id']}/link-user", headers=t.agent.headers, json={"user_id": str(user.id)}).status_code == 200
    other_farmer = active_farmer(client, t, "4100 2000 3555", full_name="Someone Else")
    p = create_project(client, t)
    mine = verified_farm(client, t, farmer["id"], square(74.70, 21.70))
    theirs = verified_farm(client, t, other_farmer["id"], square(74.72, 21.70))
    add_farm(client, t, p["id"], mine["id"])
    add_farm(client, t, p["id"], theirs["id"])
    fh = login(client, user)
    rows = client.get(f"{PR}/my-participation", headers=fh).json()
    assert [(r["farm_code"], r["project_code"]) for r in rows] == [(mine["farm_code"], p["project_code"])]
    assert rows[0]["carbon_rights"][0]["holder_type"] == "FARMER"
    assert client.get(f"{PR}/{p['id']}", headers=fh).status_code == 403  # no project-wide view for farmers
    assert client.get(f"{PR}/{p['id']}/farms", headers=fh).status_code == 403
    buyer = make_user(db, roles=[("BUYER", make_org(db, org_type="BUYER"))])
    assert client.get(f"{PR}/my-participation", headers=login(client, buyer)).status_code == 403


def test_demo_project_isolation(client: TestClient, db: Session) -> None:
    demo_org = make_org(db, org_type="PROJECT_DEVELOPER", environment="DEMO")
    pm = make_user(db, roles=[("PROJECT_MANAGER", demo_org)], environment="DEMO")
    h = login(client, pm)
    r = client.post(PR, headers=h, json={"organization_id": str(demo_org.id), "name": "Demo project", "project_type": "OTHER", "country": "IN"})
    assert r.status_code == 201 and r.json()["environment"] == "DEMO"
    live = catalog(db)
    r2 = client.post(f"{PR}/{r.json()['id']}/standard", headers=h, json={"standard_id": str(live["s1"].id)})
    assert r2.json()["error_code"] == "ENVIRONMENT_MISMATCH"
    assert db.get(Project, r.json()["id"]) is not None


def test_unverified_farm_after_reopen_blocks_submit(client: TestClient, db: Session, t: Team, farmer: dict) -> None:
    """A farm re-opened for correction (Phase 2) after joining is flagged; the project cannot be submitted."""
    cat = catalog(db)
    p = create_project(client, t)
    _start(client, t, p)
    f = verified_farm(client, t, farmer["id"], square(74.80, 21.80))
    add_farm(client, t, p["id"], f["id"])
    client.post(f"/api/v1/farms/{f['id']}/reopen", headers=t.agent.headers, json={"reason": "correct the boundary"})
    set_boundary(client, t.agent.headers, f["id"], square(74.80, 21.80, 0.0012))
    farms = client.get(f"{PR}/{p['id']}/farms", headers=t.pm.headers).json()
    assert farms[0]["farm_status"] == "DRAFT" and farms[0]["boundary_changed"] is True
    assert client.get(f"{PR}/{p['id']}/boundary", headers=t.pm.headers).json()["stale"] is True
    for path, body in (("standard", {"standard_id": str(cat["s1"].id)}), ("activity", {"activity_id": str(cat["a1"].id)})):
        client.post(f"{PR}/{p['id']}/{path}", headers=t.pm.headers, json=body)
    client.post(f"{PR}/{p['id']}/crediting-period", headers=t.pm.headers, json={"start_date": "2026-06-01", "end_date": "2036-05-31"})
    client.patch(f"{PR}/{p['id']}/baseline", headers=t.pm.headers, json={"period_start": "2021-06-01", "period_end": "2026-05-31"})
    r = client.post(f"{PR}/{p['id']}/submit", headers=t.pm.headers, json={"reason": "try anyway"})
    assert r.status_code == 409 and "All participating farms are verified and their farmers active" in r.json()["details"]["missing"]
    _ = create_farm  # keep import used
