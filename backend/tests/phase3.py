"""Helpers for Phase 3 (project) tests: a developer organization with its team, ACTIVE farmers and VERIFIED farms
created through the real Phase 2 workflow, and a small standard/activity catalog."""
from dataclasses import dataclass, field
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Activity, Organization, Standard, StandardActivity
from tests.conftest import Actor
from tests.phase2 import PDF, add_owner, create_farm, dev_org, kyc_verified_farmer, set_boundary, square, staff, upload

PR = "/api/v1/projects"


@dataclass
class Team:
    org: Organization
    pm: Actor
    qa: Actor
    gis: Actor
    agent: Actor
    extra: dict[str, Any] = field(default_factory=dict)


def team(db: Session, client: TestClient) -> Team:
    org = dev_org(db)
    return Team(org, staff(db, client, org, "PROJECT_MANAGER"), staff(db, client, org, "QA_OFFICER"), staff(db, client, org, "GIS_SPECIALIST"),
                staff(db, client, org, "FIELD_AGENT"))


def active_farmer(client: TestClient, t: Team, id_number: str, **kw: Any) -> dict:
    f = kyc_verified_farmer(client, t.agent, t.qa, t.org, id_number=id_number, **kw)
    r = client.post(f"/api/v1/farmers/{f['id']}/consents", headers=t.agent.headers,
                    json={"consent_type": "DATA_PROCESSING", "consent_text_version": "DPC-1", "capture_method": "PAPER_SIGNED"})
    assert r.status_code == 201, r.text
    r = client.post(f"/api/v1/farmers/{f['id']}/status", headers=t.agent.headers, json={"status": "ACTIVE", "reason": "onboarded"})
    assert r.status_code == 200, r.text
    return r.json()


def verified_farm(client: TestClient, t: Team, farmer_id: str, geo: dict | None = None, verify: bool = True) -> dict:
    farm = create_farm(client, t.agent.headers, farmer_id, declared_area_hectares="1.2")
    set_boundary(client, t.agent.headers, farm["id"], geo)
    own = add_owner(client, t.agent.headers, farm["id"])
    if not verify:
        return farm
    h, fid = t.gis.headers, farm["id"]
    for url, actor, body in ((f"/api/v1/farms/{fid}/submit", t.agent, {"reason": "ready for review"}),
                             (f"/api/v1/farms/{fid}/start-review", t.gis, {"reason": "start review"}),
                             (f"/api/v1/farms/{fid}/ownership/{own['id']}/review", t.gis, {"status": "VERIFIED", "notes": "title matches"}),
                             (f"/api/v1/farms/{fid}/verify", t.gis, {"reason": "boundary and tenure confirmed"})):
        r = client.post(url, headers=actor.headers, json=body)
        assert r.status_code in (200, 201), (url, r.text)
    r = client.get(f"/api/v1/farms/{fid}", headers=h)
    assert r.json()["status"] == "VERIFIED", r.text
    return r.json()


def catalog(db: Session, environment: str = "LIVE") -> dict[str, Any]:
    import uuid
    tag = uuid.uuid4().hex[:6].upper()
    s1 = Standard(code=f"STD-A-{tag}", name=f"Standard A {tag}", program_type="VOLUNTARY", environment=environment)
    s2 = Standard(code=f"STD-B-{tag}", name=f"Standard B {tag}", program_type="COMPLIANCE", environment=environment)
    a1 = Activity(code=f"ACT-1-{tag}", name=f"Activity one {tag}", environment=environment)
    a2 = Activity(code=f"ACT-2-{tag}", name=f"Activity two {tag}", environment=environment)
    db.add_all([s1, s2, a1, a2])
    db.flush()
    db.add_all([StandardActivity(standard_id=s1.id, activity_id=a1.id), StandardActivity(standard_id=s1.id, activity_id=a2.id),
                StandardActivity(standard_id=s2.id, activity_id=a2.id)])
    db.flush()
    return {"s1": s1, "s2": s2, "a1": a1, "a2": a2}


def create_project(client: TestClient, t: Team, **kw: Any) -> dict:
    body = {"organization_id": str(t.org.id), "name": "Nashik soil carbon pilot", "project_type": "AGRICULTURAL_LAND_MANAGEMENT",
            "country": "IN", "region": "Nashik, Maharashtra", "start_date": "2026-06-01", **kw}
    r = client.post(PR, headers=t.pm.headers, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def rights(reference: str = "Carbon rights clause, farmer agreement 2026", **kw: Any) -> dict:
    return {"holder_type": "FARMER", "reference": reference, "effective_from": "2026-06-01", **kw}


def add_farm(client: TestClient, t: Team, project_id: str, farm_id: str, **kw: Any) -> Any:
    body = {"farm_id": farm_id, "participation_start": "2026-06-01", "carbon_rights": rights(), **kw}
    return client.post(f"{PR}/{project_id}/farms", headers=t.pm.headers, json=body)


def upload_project_doc(client: TestClient, t: Team, project_id: str, category: str = "PROJECT_DESIGN") -> str:
    r = upload(client, t.pm.headers, f"{PR}/{project_id}/documents", category, PDF, "pdd.pdf", "Project design")
    assert r.status_code == 201, r.text
    return r.json()["id"]


__all__ = ["PR", "Team", "active_farmer", "add_farm", "catalog", "create_project", "rights", "square", "team", "upload_project_doc",
           "verified_farm"]
