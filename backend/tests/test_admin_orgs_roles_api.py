"""Organizations, members and roles administration."""
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, UserRole, WorkflowEvent
from tests.conftest import Actor, login, make_org, make_user

ORGS = "/api/v1/admin/organizations"
ROLES = "/api/v1/admin/roles"


def test_create_update_and_status_of_organization(client: TestClient, db: Session, admin: Actor) -> None:
    r = client.post(ORGS, headers=admin.headers, json={"code": "lab-x", "name": "Soil Lab X", "org_type": "LABORATORY",
                                                       "country": "in", "contact_email": "Lab@X.example"})
    assert r.status_code == 201, r.text
    org = r.json()
    assert org["code"] == "LAB-X" and org["country"] == "IN" and org["contact_email"] == "lab@x.example"
    assert org["status"] == "ACTIVE" and org["environment"] == "LIVE"
    dup = client.post(ORGS, headers=admin.headers, json={"code": "LAB-X", "name": "Again", "org_type": "LABORATORY"})
    assert dup.status_code == 409 and dup.json()["error_code"] == "ORGANIZATION_CODE_EXISTS"
    reserved = client.post(ORGS, headers=admin.headers, json={"code": "PLAT2", "name": "Platform two", "org_type": "PLATFORM"})
    assert reserved.json()["error_code"] == "PLATFORM_ORG_RESERVED"
    up = client.patch(f"{ORGS}/{org['id']}", headers=admin.headers, json={"name": "Soil Laboratory X"})
    assert up.json()["name"] == "Soil Laboratory X"
    s = client.post(f"{ORGS}/{org['id']}/status", headers=admin.headers, json={"status": "ARCHIVED", "reason": "closed down"})
    assert s.json()["status"] == "ARCHIVED"
    again = client.post(f"{ORGS}/{org['id']}/status", headers=admin.headers, json={"status": "ACTIVE", "reason": "reopen"})
    assert again.status_code == 409 and again.json()["error_code"] == "INVALID_STATUS_TRANSITION"
    assert db.scalars(select(WorkflowEvent).where(WorkflowEvent.entity_id == org["id"])).first()
    actions = set(db.scalars(select(AuditLog.action).where(AuditLog.entity_id == org["id"])).all())
    assert {"ORGANIZATION_CREATED", "ORGANIZATION_UPDATED", "ORGANIZATION_STATUS_CHANGED"} <= actions


def test_org_list_filters(client: TestClient, db: Session, admin: Actor) -> None:
    make_org(db, "FLT-LAB", org_type="LABORATORY")
    make_org(db, "FLT-BUY", org_type="BUYER")
    r = client.get(ORGS, headers=admin.headers, params={"search": "FLT-", "org_type": "BUYER"}).json()
    assert [o["code"] for o in r["items"]] == ["FLT-BUY"]


def test_members_add_list_and_remove_revokes_org_roles(client: TestClient, db: Session, admin: Actor) -> None:
    org = make_org(db)
    u = make_user(db)
    add = client.post(f"{ORGS}/{org.id}/members", headers=admin.headers, json={"user_id": str(u.id), "title": "Analyst"})
    assert add.status_code == 201
    again = client.post(f"{ORGS}/{org.id}/members", headers=admin.headers, json={"user_id": str(u.id)})
    assert again.json()["error_code"] == "ALREADY_MEMBER"
    grant = client.post(f"/api/v1/admin/users/{u.id}/roles", headers=admin.headers,
                        json={"role_code": "CALCULATION_ANALYST", "organization_id": str(org.id)})
    assert grant.status_code == 201
    members = client.get(f"{ORGS}/{org.id}/members", headers=admin.headers).json()
    assert [m["title"] for m in members] == ["Analyst"]
    rm = client.post(f"{ORGS}/{org.id}/members/{u.id}/remove", headers=admin.headers, json={"reason": "moved team"})
    assert rm.status_code == 200
    assert db.scalars(select(UserRole).where(UserRole.user_id == u.id)).all() == []
    assert client.get(f"{ORGS}/{org.id}/members", headers=admin.headers).json() == []


def test_cannot_add_member_to_suspended_org(client: TestClient, db: Session, admin: Actor) -> None:
    org = make_org(db)
    org.status = "SUSPENDED"
    db.flush()
    r = client.post(f"{ORGS}/{org.id}/members", headers=admin.headers, json={"user_id": str(make_user(db).id)})
    assert r.json()["error_code"] == "ORGANIZATION_INACTIVE"


def test_roles_catalog_and_system_roles_read_only(client: TestClient, admin: Actor) -> None:
    roles = client.get(ROLES, headers=admin.headers).json()
    system = [r for r in roles if r["is_system"]]
    assert len(system) == 21  # 19 spec roles + PLATFORM_GIS_SPECIALIST (D5) + MARKETPLACE_COMPLIANCE (Phase 10 D28)
    pa = next(r for r in roles if r["code"] == "PLATFORM_ADMIN")
    assert "users.manage" in pa["permissions"] and pa["assignment_count"] >= 1
    r = client.put(f"{ROLES}/{pa['id']}/permissions", headers=admin.headers, json={"permissions": []})
    assert r.status_code == 409 and r.json()["error_code"] == "SYSTEM_ROLE_READONLY"
    perms = client.get("/api/v1/admin/permissions", headers=admin.headers).json()
    assert {p["code"] for p in perms} >= {"users.read", "security.manage"}


def test_custom_role_lifecycle_and_escalation(client: TestClient, db: Session, admin: Actor) -> None:
    r = client.post(ROLES, headers=admin.headers, json={"code": "auditor_lite", "name": "Auditor lite",
                                                        "scope": "ORGANIZATION", "permissions": ["audit.read"]})
    assert r.status_code == 201, r.text
    role = r.json()
    assert role["code"] == "AUDITOR_LITE" and role["permissions"] == ["audit.read"] and not role["is_system"]
    esc = client.put(f"{ROLES}/{role['id']}/permissions", headers=admin.headers, json={"permissions": ["security.manage"]})
    assert esc.status_code == 403 and esc.json()["error_code"] == "ROLE_ESCALATION_BLOCKED"
    unk = client.put(f"{ROLES}/{role['id']}/permissions", headers=admin.headers, json={"permissions": ["nope.nope"]})
    assert unk.json()["error_code"] == "UNKNOWN_PERMISSION"
    ok = client.put(f"{ROLES}/{role['id']}/permissions", headers=admin.headers,
                    json={"permissions": ["audit.read", "users.read"]})
    assert ok.json()["permissions"] == ["audit.read", "users.read"]
    dup = client.post(ROLES, headers=admin.headers, json={"code": "FARMER", "name": "Farmer copy", "scope": "ORGANIZATION"})
    assert dup.json()["error_code"] == "ROLE_EXISTS"
    row = db.scalars(select(AuditLog).where(AuditLog.action == "ROLE_PERMISSIONS_CHANGED",
                                            AuditLog.entity_id == role["id"])).one()
    assert "audit.read" in row.old_value and "users.read" in row.new_value


def test_security_admin_cannot_manage_roles(client: TestClient, db: Session) -> None:
    sec = make_user(db, roles=[("SECURITY_ADMIN", None)])
    r = client.post(ROLES, headers=login(client, sec), json={"code": "X_ROLE", "name": "X", "scope": "PLATFORM"})
    assert r.status_code == 403
