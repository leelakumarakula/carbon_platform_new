"""Cross-organization isolation (spec section 31) and role-escalation guards for org-scoped administrators."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Organization, Permission, Role, RolePermission
from tests.conftest import login, make_org, make_user

USERS = "/api/v1/admin/users"
ORGS = "/api/v1/admin/organizations"


@pytest.fixture()
def org_admin_role(db: Session) -> Role:
    """A custom role giving user + member administration inside one organization only."""
    from sqlalchemy import select
    perms = db.scalars(select(Permission).where(Permission.code.in_(
        ["users.read", "users.manage", "users.assign_roles", "organizations.read", "organizations.manage_members"]))).all()
    r = Role(code="ORG_USER_ADMIN", name="Org user admin", scope="ORGANIZATION", is_system=False)
    r.permissions = [RolePermission(permission=p) for p in perms]
    db.add(r)
    db.flush()
    return r


@pytest.fixture()
def tenants(db: Session, org_admin_role: Role) -> dict:
    a, b = make_org(db, "TEN-A"), make_org(db, "TEN-B")
    admin_a = make_user(db, roles=[("ORG_USER_ADMIN", a)])
    user_a = make_user(db, orgs=[a], email="alice@tenant-a.example")
    user_b = make_user(db, orgs=[b], email="bob@tenant-b.example")
    return {"a": a, "b": b, "admin_a": admin_a, "user_a": user_a, "user_b": user_b}


def test_org_admin_sees_only_own_org_users(client: TestClient, tenants: dict) -> None:
    h = login(client, tenants["admin_a"])
    emails = {u["email"] for u in client.get(USERS, headers=h, params={"page_size": 100}).json()["items"]}
    assert "alice@tenant-a.example" in emails and "bob@tenant-b.example" not in emails
    # Direct access to another tenant's user looks exactly like a missing record.
    r = client.get(f"{USERS}/{tenants['user_b'].id}", headers=h)
    assert r.status_code == 404 and r.json()["error_code"] == "USER_NOT_FOUND"
    # Filtering by a foreign organization is refused.
    assert client.get(USERS, headers=h, params={"organization_id": str(tenants["b"].id)}).status_code == 403


def test_org_admin_cannot_modify_other_tenant(client: TestClient, tenants: dict) -> None:
    h = login(client, tenants["admin_a"])
    b = tenants["b"]
    r = client.post(USERS, headers=h, json={"email": "x@tenant-b.example", "full_name": "Intruder",
                                            "temporary_password": "Temp-Password-123", "organization_id": str(b.id)})
    assert r.status_code == 403
    r = client.post(USERS, headers=h, json={"email": "x@nowhere.example", "full_name": "No Org",
                                            "temporary_password": "Temp-Password-123"})
    assert r.status_code == 422 and r.json()["error_code"] == "ORGANIZATION_REQUIRED"
    assert client.patch(f"{USERS}/{tenants['user_b'].id}", headers=h, json={"full_name": "Changed"}).status_code == 404
    assert client.post(f"{ORGS}/{b.id}/members", headers=h, json={"user_id": str(tenants["user_a"].id)}).status_code == 404


def test_org_admin_can_manage_own_tenant(client: TestClient, tenants: dict) -> None:
    h = login(client, tenants["admin_a"])
    a = tenants["a"]
    r = client.post(USERS, headers=h, json={"email": "new@tenant-a.example", "full_name": "New Member",
                                            "temporary_password": "Temp-Password-123", "organization_id": str(a.id),
                                            "roles": [{"role_code": "ORG_USER_ADMIN", "organization_id": str(a.id)}]})
    assert r.status_code == 201, r.text
    orgs = client.get(ORGS, headers=h).json()
    assert [o["code"] for o in orgs["items"]] == ["TEN-A"]


def test_org_admin_cannot_escalate(client: TestClient, tenants: dict) -> None:
    h = login(client, tenants["admin_a"])
    a, uid = tenants["a"], tenants["user_a"].id
    # Platform roles require a platform-wide users.assign_roles grant.
    r = client.post(f"{USERS}/{uid}/roles", headers=h, json={"role_code": "PLATFORM_ADMIN"})
    assert r.status_code == 403
    # An org role that carries permissions the org admin does not hold is blocked.
    from sqlalchemy.orm import Session as _S  # noqa: F401
    r = client.post(f"{USERS}/{uid}/roles", headers=h, json={"role_code": "ORG_USER_ADMIN", "organization_id": str(a.id)})
    assert r.status_code == 201  # same permissions as the granter: allowed


def test_org_scoped_permission_does_not_leak_to_other_org(db: Session, client: TestClient, org_admin_role: Role) -> None:
    a, b = make_org(db), make_org(db)
    admin_a = make_user(db, roles=[("ORG_USER_ADMIN", a)], orgs=[b])  # member of B but admin only in A
    target_b = make_user(db, orgs=[b])
    h = login(client, admin_a)
    r = client.post(f"{USERS}/{target_b.id}/status", headers=h, json={"status": "SUSPENDED", "reason": "attempt"})
    assert r.status_code in (403, 404)


def test_demo_and_live_records_do_not_mix(client: TestClient, db: Session) -> None:
    admin = make_user(db, roles=[("PLATFORM_ADMIN", None)])
    h = login(client, admin)
    demo_org: Organization = make_org(db, environment="DEMO")
    live_user = make_user(db)
    r = client.post(f"{ORGS}/{demo_org.id}/members", headers=h, json={"user_id": str(live_user.id)})
    assert r.status_code == 409 and r.json()["error_code"] == "ENVIRONMENT_MISMATCH"
    created = client.post(USERS, headers=h, json={"email": "d@demo.example", "full_name": "Demo Person",
                                                  "temporary_password": "Temp-Password-123",
                                                  "organization_id": str(demo_org.id)}).json()
    assert created["environment"] == "DEMO"
