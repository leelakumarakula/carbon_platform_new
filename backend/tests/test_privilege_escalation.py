"""Decision D4: the permission-grant matrix (docs/roles-permissions.md) and privilege-escalation guards.

Operational roles can be assigned by authorized administrators; administrative/security permissions stay
restricted to holders; nobody changes their own roles; platform roles need a platform-wide grant; the last
Platform Admin is protected (covered in test_admin_users_api).
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Organization, Permission, Role, RolePermission
from app.security.permissions import PRIVILEGED_CODES, SYSTEM_ROLES
from tests.conftest import Actor, login, make_org, make_user

USERS = "/api/v1/admin/users"
OPERATIONAL_ORG_ROLES = ["FIELD_AGENT", "FIELD_SUPERVISOR", "GIS_SPECIALIST", "MRV_MANAGER", "QA_OFFICER", "PROJECT_MANAGER",
                         "FINANCE_MANAGER"]


def _grant(client: TestClient, h: dict, user_id: object, role: str, org: Organization | None = None):  # type: ignore[no-untyped-def]
    body: dict = {"role_code": role}
    if org is not None:
        body["organization_id"] = str(org.id)
    return client.post(f"{USERS}/{user_id}/roles", headers=h, json=body)


@pytest.fixture()
def dev(db: Session) -> Organization:
    return make_org(db, org_type="PROJECT_DEVELOPER")


@pytest.fixture()
def org_user_admin(db: Session, client: TestClient, dev: Organization) -> Actor:
    """Custom org-scoped role: user administration inside one organization only (no admin/security beyond that)."""
    perms = db.scalars(select(Permission).where(Permission.code.in_(["users.read", "users.manage", "users.assign_roles"]))).all()
    r = Role(code="DEV_USER_ADMIN", name="Developer user admin", scope="ORGANIZATION", is_system=False)
    r.permissions = [RolePermission(permission=p) for p in perms]
    db.add(r)
    db.flush()
    u = make_user(db, roles=[("DEV_USER_ADMIN", dev)])
    return Actor(u, login(client, u))


def test_privileged_codes_are_admin_audit_security_only() -> None:
    assert {c.split(".")[0] for c in PRIVILEGED_CODES} == {"users", "roles", "organizations", "audit", "security", "consents"}
    operational = {r.code: r for r in SYSTEM_ROLES if r.code in [*OPERATIONAL_ORG_ROLES, "SUPPORT", "PLATFORM_GIS_SPECIALIST"]}
    for code, r in operational.items():
        if code != "SUPPORT":
            assert not (r.permissions & PRIVILEGED_CODES), f"{code} must not carry privileged permissions"


def test_platform_admin_assigns_every_operational_role(client: TestClient, db: Session, admin: Actor, dev: Organization) -> None:
    for role in OPERATIONAL_ORG_ROLES:
        u = make_user(db, orgs=[dev])
        r = _grant(client, admin.headers, u.id, role, dev)
        assert r.status_code == 201, (role, r.text)
    for role in ("SUPPORT", "PLATFORM_GIS_SPECIALIST"):
        u = make_user(db)
        assert _grant(client, admin.headers, u.id, role).status_code == 201, role


def test_admin_and_security_permissions_stay_restricted(client: TestClient, db: Session, admin: Actor) -> None:
    u = make_user(db)
    r = _grant(client, admin.headers, u.id, "SECURITY_ADMIN")
    assert r.status_code == 403 and r.json()["error_code"] == "ROLE_ESCALATION_BLOCKED"
    # A custom role cannot be used to smuggle in a privileged permission the creator does not hold.
    r = client.post("/api/v1/admin/roles", headers=admin.headers,
                    json={"code": "SNEAKY", "name": "Sneaky role", "scope": "PLATFORM", "permissions": ["security.manage", "farms.read"]})
    assert r.status_code == 403 and r.json()["error_code"] == "ROLE_ESCALATION_BLOCKED"


def test_nobody_grants_themselves(client: TestClient, admin: Actor) -> None:
    r = _grant(client, admin.headers, admin.user.id, "SUPPORT")
    assert r.status_code == 403 and r.json()["error_code"] == "SELF_ROLE_CHANGE"


def test_org_admin_assigns_operational_roles_only_in_own_org(client: TestClient, db: Session, org_user_admin: Actor,
                                                             dev: Organization) -> None:
    h = org_user_admin.headers
    member = make_user(db, orgs=[dev])
    assert _grant(client, h, member.id, "FIELD_AGENT", dev).status_code == 201
    # Not a platform role, not another organization, not a role with admin permissions it lacks.
    assert _grant(client, h, member.id, "PLATFORM_GIS_SPECIALIST").status_code == 403
    assert _grant(client, h, member.id, "PLATFORM_ADMIN").status_code == 403
    other = make_org(db)
    outsider = make_user(db, orgs=[other])
    assert _grant(client, h, outsider.id, "FIELD_AGENT", other).status_code == 404  # invisible user
    both = make_user(db, orgs=[dev, other])
    assert _grant(client, h, both.id, "FIELD_AGENT", other).status_code == 403
    admin_role = Role(code="DEV_ROLE_ADMIN", name="Role admin", scope="ORGANIZATION", is_system=False)
    admin_role.permissions = [RolePermission(permission=db.scalars(select(Permission).where(Permission.code == "roles.manage")).one())]
    db.add(admin_role)
    db.flush()
    r = _grant(client, h, member.id, "DEV_ROLE_ADMIN", dev)
    assert r.status_code == 403 and r.json()["details"]["missing_permissions"] == ["roles.manage"]
    # It cannot escalate itself either.
    assert _grant(client, h, org_user_admin.user.id, "PROJECT_MANAGER", dev).json()["error_code"] == "SELF_ROLE_CHANGE"


@pytest.mark.parametrize("role", ["PROJECT_MANAGER", "FIELD_AGENT", "GIS_SPECIALIST", "QA_OFFICER", "FARMER", "BUYER"])
def test_business_roles_cannot_grant_roles(client: TestClient, db: Session, dev: Organization, role: str) -> None:
    actor = make_user(db, roles=[(role, dev)])
    target = make_user(db, orgs=[dev])
    r = _grant(client, login(client, actor), target.id, "FIELD_AGENT", dev)
    assert r.status_code == 403
