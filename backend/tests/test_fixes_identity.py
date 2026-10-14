"""Identity security fixes: account takeover through membership (B1), environment isolation of platform-wide grants (B2),
suspended organizations (B3), the atomic sign-in lockout (B4) and the refresh-token row lock (B5)."""
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_engine
from app.models import Organization, OrganizationUser, Permission, Role, RolePermission, SecurityEvent, User
from app.models.base import utcnow
from app.security.permissions import P
from app.security.principal import Grant, Principal
from app.services import access
from tests.conftest import PASSWORD, Actor, login, make_org, make_user
from tests.phase2 import BASE_LAT, BASE_LON, create_farm, create_farmer, register, set_boundary, staff

USERS = "/api/v1/admin/users"
ORGS = "/api/v1/admin/organizations"
LOGIN = "/api/v1/auth/login"


@pytest.fixture()
def org_admin_role(db: Session) -> Role:
    """A custom organization-scoped role: user and member administration inside one organization."""
    perms = db.scalars(select(Permission).where(Permission.code.in_(
        ["users.read", "users.manage", "users.assign_roles", "organizations.read", "organizations.manage_members"]))).all()
    r = Role(code="FIX_ORG_ADMIN", name="Org user admin", scope="ORGANIZATION", is_system=False)
    r.permissions = [RolePermission(permission=p) for p in perms]
    db.add(r)
    db.flush()
    return r


def _reset(client: TestClient, h: dict, user_id: uuid.UUID) -> object:
    return client.post(f"{USERS}/{user_id}/reset-password", headers=h,
                       json={"temporary_password": "Reset-Password-99", "reason": "takeover attempt"})


def _suspend(client: TestClient, h: dict, user_id: uuid.UUID) -> object:
    return client.post(f"{USERS}/{user_id}/status", headers=h, json={"status": "SUSPENDED", "reason": "takeover attempt"})


def _enrol(client: TestClient, h: dict, org: Organization, user: User) -> object:
    return client.post(f"{ORGS}/{org.id}/members", headers=h, json={"user_id": str(user.id)})


def _signs_in(client: TestClient, user: User) -> bool:
    return client.post(LOGIN, json={"email": user.email, "password": PASSWORD}).status_code == 200


# ---------------------------------------------------------------- B1: account takeover
def test_org_admin_cannot_take_over_a_platform_admin(client: TestClient, db: Session, org_admin_role: Role) -> None:
    x, platform = make_org(db), make_org(db)
    h = login(client, make_user(db, roles=[("FIX_ORG_ADMIN", x)]))
    unaffiliated = make_user(db, roles=[("PLATFORM_ADMIN", None)])                  # like admin@demo: no organization
    member = make_user(db, roles=[("PLATFORM_ADMIN", None)], orgs=[platform])        # like the bootstrap admin
    for pa in (unaffiliated, member):
        r = _enrol(client, h, x, pa)
        assert r.status_code == 404 and r.json()["error_code"] == "USER_NOT_FOUND"   # step 1 of the chain is refused
    assert not db.scalars(select(OrganizationUser).where(OrganizationUser.organization_id == x.id,
                                                         OrganizationUser.user_id.in_([unaffiliated.id, member.id]))).all()
    # Step 2, even if such a membership exists: a Platform Admin is never reset, suspended or edited by an organization admin.
    db.add(OrganizationUser(organization_id=x.id, user_id=member.id))
    in_x_only = make_user(db, roles=[("PLATFORM_ADMIN", None)], orgs=[x])
    db.flush()
    assert _reset(client, h, member.id).status_code == 403                             # not all of its organizations are in scope
    r = _reset(client, h, in_x_only.id)
    assert r.status_code == 403 and r.json()["error_code"] == "ROLE_ESCALATION_BLOCKED"
    assert {"users.manage", "security.read", "audit.read"} <= set(r.json()["details"]["missing_permissions"])
    assert _suspend(client, h, in_x_only.id).status_code == 403
    assert client.patch(f"{USERS}/{in_x_only.id}", headers=h, json={"full_name": "Owned"}).status_code == 403
    assert _signs_in(client, member) and _signs_in(client, in_x_only)                  # passwords untouched


def test_org_admin_manages_only_accounts_entirely_in_its_scope(client: TestClient, db: Session, org_admin_role: Role) -> None:
    x, y = make_org(db), make_org(db)
    h = login(client, make_user(db, roles=[("FIX_ORG_ADMIN", x)]))
    only_x = make_user(db, orgs=[x])
    x_and_y = make_user(db, orgs=[x, y])
    platform_gis = make_user(db, roles=[("PLATFORM_GIS_SPECIALIST", None)], orgs=[x])   # platform-wide grant, no privileged code
    assert _reset(client, h, only_x.id).status_code == 200                               # control
    assert client.get(f"{USERS}/{x_and_y.id}", headers=h).status_code == 200            # visible ...
    assert _reset(client, h, x_and_y.id).status_code == 403                              # ... but not manageable
    assert _suspend(client, h, x_and_y.id).status_code == 403
    r = _reset(client, h, platform_gis.id)
    assert r.status_code == 403 and r.json()["details"]["missing_permissions"] == ["users.manage"]
    assert _signs_in(client, x_and_y) and _signs_in(client, platform_gis)


def test_member_enrolment_needs_users_manage_over_the_account(client: TestClient, db: Session, org_admin_role: Role) -> None:
    x, y, z = make_org(db), make_org(db), make_org(db)
    h = login(client, make_user(db, roles=[("FIX_ORG_ADMIN", x), ("FIX_ORG_ADMIN", y)]))
    assert _enrol(client, h, x, make_user(db, orgs=[y])).status_code == 201               # all of its organizations are in scope
    for outsider in (make_user(db, orgs=[z]), make_user(db, orgs=[y, z]), make_user(db)):
        r = _enrol(client, h, x, outsider)
        assert r.status_code == 404 and r.json()["error_code"] == "USER_NOT_FOUND"


def test_platform_admin_cannot_take_over_a_security_admin(client: TestClient, db: Session, admin: Actor) -> None:
    sec = make_user(db, roles=[("SECURITY_ADMIN", None)])
    r = _reset(client, admin.headers, sec.id)
    assert r.status_code == 403 and r.json()["error_code"] == "ROLE_ESCALATION_BLOCKED"
    assert r.json()["details"]["missing_permissions"] == ["security.manage"]
    assert _suspend(client, admin.headers, sec.id).status_code == 403
    assert client.patch(f"{USERS}/{sec.id}", headers=admin.headers, json={"full_name": "Owned"}).status_code == 403
    assert _signs_in(client, sec)
    # Platform Admins still manage ordinary accounts and each other (D4: a Platform Admin may grant Platform Admin).
    assert _reset(client, admin.headers, make_user(db, roles=[("PLATFORM_ADMIN", None)]).id).status_code == 200
    assert _reset(client, admin.headers, make_user(db, roles=[("SUPPORT", None)]).id).status_code == 200


# ---------------------------------------------------------------- B2: DEMO and LIVE platform grants
def test_principal_platform_grant_reaches_only_its_environment() -> None:
    mine, other = uuid.uuid4(), uuid.uuid4()
    grant = Grant(uuid.uuid4(), "R", "PLATFORM", None, frozenset({P.FARMERS_READ}))
    p = Principal(user=SimpleNamespace(id=uuid.uuid4()), session_id=None, grants=(grant,),  # type: ignore[arg-type]
                  environment_organization_ids=frozenset({mine}))
    assert p.can_in_org(P.FARMERS_READ, mine) and p.can_in_org(P.FARMERS_READ, None)
    assert not p.can_in_org(P.FARMERS_READ, other)
    assert p.scope_for(P.FARMERS_READ) == frozenset({mine}) and access.read_scope(p, P.FARMERS_READ) == (frozenset({mine}), False)
    empty = Principal(user=SimpleNamespace(id=uuid.uuid4()), session_id=None, grants=(grant,),  # type: ignore[arg-type]
                      environment_organization_ids=frozenset())
    assert access.read_scope(empty, P.FARMERS_READ) == (access.NO_ORGANIZATION, False)   # matches nothing, never "everything"


def test_demo_platform_accounts_cannot_read_live_records(client: TestClient, db: Session) -> None:
    live = make_org(db, org_type="PROJECT_DEVELOPER")
    pm = staff(db, client, live, "PROJECT_MANAGER")
    farmer = create_farmer(client, pm.headers, live)
    register(client, pm.headers, farmer["id"])
    farm = create_farm(client, pm.headers, farmer["id"])
    set_boundary(client, pm.headers, farm["id"])
    live_user = make_user(db, orgs=[live])
    near = {"lat": BASE_LAT + 0.0005, "lon": BASE_LON + 0.0005, "radius_m": 1000, "environment": "LIVE"}

    def reads(h: dict) -> dict[str, object]:
        return {
            "farmer": client.get(f"/api/v1/farmers/{farmer['id']}", headers=h).status_code,
            "farm": client.get(f"/api/v1/farms/{farm['id']}", headers=h).status_code,
            "farmers": farmer["id"] in {f["id"] for f in client.get("/api/v1/farmers", headers=h, params={"page_size": 100}).json()["items"]},
            "farms": farm["id"] in {f["id"] for f in client.get("/api/v1/farms", headers=h, params={"page_size": 100}).json()["items"]},
            "near": farm["id"] in {f["farm_id"] for f in client.get("/api/v1/farms/spatial/near", headers=h, params=near).json()},
        }

    assert reads(login(client, make_user(db, roles=[("SUPPORT", None)]))) == {  # control: a LIVE platform account sees them
        "farmer": 200, "farm": 200, "farmers": True, "farms": True, "near": True}
    for role in ("PLATFORM_ADMIN", "SUPPORT", "PLATFORM_GIS_SPECIALIST"):
        h = login(client, make_user(db, roles=[(role, None)], environment="DEMO"))
        assert reads(h) == {"farmer": 404, "farm": 404, "farmers": False, "farms": False, "near": False}, role
        if role != "PLATFORM_GIS_SPECIALIST":
            assert client.get(f"{USERS}/{live_user.id}", headers=h).status_code == 404
            assert live_user.email not in {u["email"] for u in client.get(USERS, headers=h, params={"page_size": 100}).json()["items"]}
            assert client.get(USERS, headers=h, params={"environment": "LIVE"}).json()["total"] == 0
            assert client.get(f"{ORGS}/{live.id}", headers=h).status_code == 404
            assert live.code not in {o["code"] for o in client.get(ORGS, headers=h, params={"page_size": 100}).json()["items"]}


def test_demo_platform_admin_cannot_create_live_accounts(client: TestClient, db: Session) -> None:
    h = login(client, make_user(db, roles=[("PLATFORM_ADMIN", None)], environment="DEMO"))
    r = client.post(USERS, headers=h, json={"email": "new.pa@test.example", "full_name": "New Admin",
                                            "temporary_password": "Temp-Password-123", "roles": [{"role_code": "PLATFORM_ADMIN"}]})
    assert r.status_code == 201 and r.json()["environment"] == "DEMO"   # never a LIVE Platform Admin


# ---------------------------------------------------------------- B3: suspended organizations
def test_suspended_organization_gives_its_members_no_access(client: TestClient, db: Session, admin: Actor) -> None:
    org = make_org(db, org_type="PROJECT_DEVELOPER")
    pm = staff(db, client, org, "PROJECT_MANAGER")
    farmer = create_farmer(client, pm.headers, org)
    assert client.get(f"/api/v1/farmers/{farmer['id']}", headers=pm.headers).status_code == 200
    status = f"{ORGS}/{org.id}/status"
    assert client.post(status, headers=admin.headers, json={"status": "SUSPENDED", "reason": "contract paused"}).status_code == 200
    assert client.get(f"/api/v1/farmers/{farmer['id']}", headers=pm.headers).status_code in (403, 404)
    assert client.get("/api/v1/farmers", headers=pm.headers).status_code == 403
    r = client.post("/api/v1/farmers", headers=pm.headers, json={"organization_id": str(org.id), "full_name": "Asha Patil",
                                                                 "village": "Pimpalgaon", "district": "Nashik", "state": "Maharashtra",
                                                                 "country": "IN"})
    assert r.status_code == 403
    # The platform admin still sees the organization, reactivates it, and access comes back.
    assert client.get(f"{ORGS}/{org.id}", headers=admin.headers).json()["status"] == "SUSPENDED"
    r = client.post(status, headers=admin.headers, json={"status": "ACTIVE", "reason": "contract resumed"})
    assert r.status_code == 200 and r.json()["status"] == "ACTIVE"
    assert client.get(f"/api/v1/farmers/{farmer['id']}", headers=pm.headers).status_code == 200


# ---------------------------------------------------------------- B4: lockout
def test_failed_sign_ins_are_counted_atomically(client: TestClient, db: Session) -> None:
    u = make_user(db)
    limit = get_settings().MAX_FAILED_LOGINS
    # Failures written by parallel requests that this session's copy of the user has not seen (a read-modify-write lost them).
    db.execute(update(User).where(User.id == u.id).values(failed_login_count=limit - 1), execution_options={"synchronize_session": False})
    assert u.failed_login_count == 0
    assert client.post(LOGIN, json={"email": u.email, "password": "Wrong-Password-1"}).status_code == 401
    db.refresh(u)
    assert u.locked_until is not None and u.locked_until > utcnow() and u.failed_login_count == 0
    assert db.scalars(select(SecurityEvent).where(SecurityEvent.user_id == u.id, SecurityEvent.event_type == "ACCOUNT_LOCKED")).first()


def test_wrong_current_password_counts_towards_the_lockout(client: TestClient, db: Session) -> None:
    u = make_user(db)
    h = login(client, u)
    for _ in range(get_settings().MAX_FAILED_LOGINS):
        r = client.post("/api/v1/auth/change-password", headers=h,
                        json={"current_password": "Guess-Password-1", "new_password": "Brand-New-Secret-7"})
        assert r.status_code == 422 and r.json()["error_code"] == "CURRENT_PASSWORD_INCORRECT"
    db.refresh(u)
    assert u.locked_until is not None and u.locked_until > utcnow()
    r = client.get("/api/v1/auth/me", headers=h)
    assert r.status_code == 401 and r.json()["error_code"] == "ACCOUNT_INACTIVE"
    assert db.scalars(select(SecurityEvent).where(SecurityEvent.user_id == u.id, SecurityEvent.event_type == "ACCOUNT_LOCKED")).first()


# ---------------------------------------------------------------- B5: refresh rotation lock
def test_refresh_token_is_read_with_a_sql_server_row_lock(client: TestClient, db: Session) -> None:
    u = make_user(db)
    assert client.post(LOGIN, json={"email": u.email, "password": PASSWORD}).status_code == 200
    seen: list[str] = []

    def capture(conn: object, cursor: object, statement: str, *args: object) -> None:
        seen.append(statement)

    event.listen(get_engine(), "before_cursor_execute", capture)
    try:
        r = client.post("/api/v1/auth/refresh")
    finally:
        event.remove(get_engine(), "before_cursor_execute", capture)
    assert r.status_code == 200
    reads = [s for s in seen if s.lstrip().upper().startswith("SELECT") and "FROM refresh_tokens" in s]
    assert reads and "UPDLOCK" in reads[0] and "HOLDLOCK" in reads[0]
