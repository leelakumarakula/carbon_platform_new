"""User administration: CRUD, status machine, role grants, escalation guards, audit."""
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, WorkflowEvent
from tests.conftest import PASSWORD, Actor, login, make_org, make_user

USERS = "/api/v1/admin/users"


def _create(client: TestClient, h: dict, **kw: object) -> dict:
    body = {"email": "new.user@test.example", "full_name": "New User", "temporary_password": "Temp-Password-123", **kw}
    return client.post(USERS, headers=h, json=body).json()


def test_create_user_with_org_and_role_is_audited(client: TestClient, db: Session, admin: Actor) -> None:
    org = make_org(db)
    r = client.post(USERS, headers=admin.headers, json={
        "email": "Field.Agent@Test.Example", "full_name": "Field Agent", "temporary_password": "Temp-Password-123",
        "organization_id": str(org.id), "title": "Collector", "roles": [{"role_code": "field_agent", "organization_id": str(org.id)}]})
    assert r.status_code == 201, r.text
    u = r.json()
    assert u["email"] == "field.agent@test.example" and u["must_change_password"] is True
    assert u["organizations"][0]["organization_id"] == str(org.id)
    assert [g["role_code"] for g in u["roles"]] == ["FIELD_AGENT"]
    actions = set(db.scalars(select(AuditLog.action).where(AuditLog.entity_id == u["id"])).all())
    assert {"USER_CREATED", "ROLE_ASSIGNED"} <= actions
    created = db.scalars(select(AuditLog).where(AuditLog.action == "USER_CREATED", AuditLog.entity_id == u["id"])).one()
    assert "password" not in (created.new_value or "") and created.user_id == admin.user.id and created.request_id


def test_new_user_must_change_temporary_password(client: TestClient, admin: Actor) -> None:
    u = _create(client, admin.headers)
    r = client.post("/api/v1/auth/login", json={"email": u["email"], "password": "Temp-Password-123"})
    assert r.json()["must_change_password"] is True


def test_duplicate_email_and_weak_password(client: TestClient, admin: Actor) -> None:
    _create(client, admin.headers)
    dup = client.post(USERS, headers=admin.headers, json={"email": "NEW.user@test.example", "full_name": "X Y",
                                                         "temporary_password": "Temp-Password-123"})
    assert dup.status_code == 409 and dup.json()["error_code"] == "EMAIL_EXISTS"
    weak = client.post(USERS, headers=admin.headers, json={"email": "w@test.example", "full_name": "X Y",
                                                          "temporary_password": "weak"})
    assert weak.status_code == 422 and weak.json()["error_code"] == "PASSWORD_POLICY"


def test_list_search_filter_sort_paginate(client: TestClient, db: Session, admin: Actor) -> None:
    org = make_org(db)
    for i in range(3):
        make_user(db, email=f"zeta{i}@test.example", orgs=[org])
    r = client.get(USERS, headers=admin.headers, params={"search": "zeta", "page_size": 2, "sort": "-email"})
    body = r.json()
    assert body["total"] == 3 and len(body["items"]) == 2 and body["items"][0]["email"] == "zeta2@test.example"
    page2 = client.get(USERS, headers=admin.headers, params={"search": "zeta", "page_size": 2, "page": 2, "sort": "-email"})
    assert [i["email"] for i in page2.json()["items"]] == ["zeta0@test.example"]
    by_org = client.get(USERS, headers=admin.headers, params={"organization_id": str(org.id)}).json()
    assert by_org["total"] == 3
    bad = client.get(USERS, headers=admin.headers, params={"sort": "password_hash"})
    assert bad.status_code == 422 and bad.json()["error_code"] in ("INVALID_SORT", "VALIDATION_FAILED")


def test_update_profile_records_diff(client: TestClient, db: Session, admin: Actor) -> None:
    u = make_user(db)
    r = client.patch(f"{USERS}/{u.id}", headers=admin.headers, json={"full_name": "Renamed Person"})
    assert r.status_code == 200 and r.json()["full_name"] == "Renamed Person"
    row = db.scalars(select(AuditLog).where(AuditLog.action == "USER_UPDATED", AuditLog.entity_id == str(u.id))).one()
    assert "Test User" in row.old_value and "Renamed Person" in row.new_value


def test_status_machine_and_workflow_events(client: TestClient, db: Session, admin: Actor) -> None:
    u = make_user(db)
    h = login(client, u)
    s = client.post(f"{USERS}/{u.id}/status", headers=admin.headers, json={"status": "SUSPENDED", "reason": "investigation"})
    assert s.status_code == 200 and s.json()["status"] == "SUSPENDED"
    assert client.get("/api/v1/auth/me", headers=h).status_code == 401  # sessions revoked
    d = client.post(f"{USERS}/{u.id}/status", headers=admin.headers, json={"status": "DEACTIVATED", "reason": "left company"})
    assert d.status_code == 200
    back = client.post(f"{USERS}/{u.id}/status", headers=admin.headers, json={"status": "ACTIVE", "reason": "oops"})
    assert back.status_code == 409 and back.json()["error_code"] == "INVALID_STATUS_TRANSITION"
    assert back.json()["details"]["from"] == "DEACTIVATED"
    events = db.scalars(select(WorkflowEvent).where(WorkflowEvent.entity_id == str(u.id))
                        .order_by(WorkflowEvent.id)).all()
    assert [(e.from_status, e.to_status) for e in events] == [("ACTIVE", "SUSPENDED"), ("SUSPENDED", "DEACTIVATED")]
    assert all(e.reason for e in events)


def test_reason_required_for_status_change(client: TestClient, db: Session, admin: Actor) -> None:
    u = make_user(db)
    r = client.post(f"{USERS}/{u.id}/status", headers=admin.headers, json={"status": "SUSPENDED", "reason": ""})
    assert r.status_code == 422


def test_cannot_change_own_status_or_roles(client: TestClient, admin: Actor) -> None:
    r = client.post(f"{USERS}/{admin.user.id}/status", headers=admin.headers, json={"status": "SUSPENDED", "reason": "test it"})
    assert r.json()["error_code"] == "SELF_STATUS_CHANGE"
    r = client.post(f"{USERS}/{admin.user.id}/roles", headers=admin.headers, json={"role_code": "SUPPORT"})
    assert r.status_code == 403 and r.json()["error_code"] == "SELF_ROLE_CHANGE"


def test_last_platform_admin_is_protected(client: TestClient, db: Session, admin: Actor) -> None:
    from sqlalchemy import update

    from app.models import Role, RolePermission, User, UserRole
    pa = db.scalars(select(Role).where(Role.code == "PLATFORM_ADMIN")).one()
    # Within this rolled-back transaction, make `admin` the only active Platform Admin.
    others = db.scalars(select(UserRole.user_id).where(UserRole.role_id == pa.id, UserRole.user_id != admin.user.id)).all()
    if others:
        db.execute(update(User).where(User.id.in_(others)).values(status="SUSPENDED"))
    # An operator with an equivalent custom role (same permissions, so no escalation block).
    ops = Role(code="OPS_EQUIV", name="Ops", scope="PLATFORM", is_system=False)
    ops.permissions = [RolePermission(permission_id=rp.permission_id) for rp in pa.permissions]
    db.add(ops)
    db.flush()
    operator = make_user(db, roles=[("OPS_EQUIV", None)])
    h = login(client, operator)
    r = client.post(f"{USERS}/{admin.user.id}/status", headers=h, json={"status": "SUSPENDED", "reason": "rotation"})
    assert r.status_code == 409 and r.json()["error_code"] == "LAST_PLATFORM_ADMIN"
    grant = next(g for g in client.get(f"{USERS}/{admin.user.id}", headers=h).json()["roles"]
                 if g["role_code"] == "PLATFORM_ADMIN")
    r = client.delete(f"{USERS}/{admin.user.id}/roles/{grant['id']}", headers=h)
    assert r.status_code == 409 and r.json()["error_code"] == "LAST_PLATFORM_ADMIN"
    # With a second active Platform Admin the suspension is allowed.
    make_user(db, roles=[("PLATFORM_ADMIN", None)])
    r = client.post(f"{USERS}/{admin.user.id}/status", headers=h, json={"status": "SUSPENDED", "reason": "rotation"})
    assert r.status_code == 200


def test_role_assignment_rules(client: TestClient, db: Session, admin: Actor) -> None:
    org = make_org(db)
    u = make_user(db)
    not_member = client.post(f"{USERS}/{u.id}/roles", headers=admin.headers,
                             json={"role_code": "MRV_MANAGER", "organization_id": str(org.id)})
    assert not_member.status_code == 409 and not_member.json()["error_code"] == "USER_NOT_MEMBER"
    no_org = client.post(f"{USERS}/{u.id}/roles", headers=admin.headers, json={"role_code": "MRV_MANAGER"})
    assert no_org.json()["error_code"] == "ROLE_SCOPE_MISMATCH"
    platform_scoped = client.post(f"{USERS}/{u.id}/roles", headers=admin.headers,
                                  json={"role_code": "SUPPORT", "organization_id": str(org.id)})
    assert platform_scoped.json()["error_code"] == "ROLE_SCOPE_MISMATCH"
    ok = client.post(f"{USERS}/{u.id}/roles", headers=admin.headers, json={"role_code": "SUPPORT"})
    assert ok.status_code == 201
    dup = client.post(f"{USERS}/{u.id}/roles", headers=admin.headers, json={"role_code": "SUPPORT"})
    assert dup.json()["error_code"] == "ROLE_ALREADY_ASSIGNED"
    grant_id = ok.json()["roles"][0]["id"]
    rv = client.delete(f"{USERS}/{u.id}/roles/{grant_id}", headers=admin.headers)
    assert rv.status_code == 200 and rv.json()["roles"] == []
    assert db.scalars(select(AuditLog).where(AuditLog.action == "ROLE_REVOKED", AuditLog.entity_id == str(u.id))).first()


def test_platform_admin_cannot_grant_security_admin(client: TestClient, db: Session, admin: Actor) -> None:
    """PLATFORM_ADMIN lacks security.manage, so cannot hand out SECURITY_ADMIN (escalation guard)."""
    u = make_user(db)
    r = client.post(f"{USERS}/{u.id}/roles", headers=admin.headers, json={"role_code": "SECURITY_ADMIN"})
    assert r.status_code == 403 and r.json()["error_code"] == "ROLE_ESCALATION_BLOCKED"
    assert "security.manage" in r.json()["details"]["missing_permissions"]


def test_support_is_read_only(client: TestClient, db: Session) -> None:
    s = make_user(db, roles=[("SUPPORT", None)])
    h = login(client, s)
    target = make_user(db)
    assert client.get(f"{USERS}/{target.id}", headers=h).status_code == 200
    r = client.patch(f"{USERS}/{target.id}", headers=h, json={"full_name": "Hacked Name"})
    assert r.status_code == 403 and r.json()["details"]["missing_permissions"] == ["users.manage"]
    assert client.post(f"{USERS}/{target.id}/roles", headers=h, json={"role_code": "SUPPORT"}).status_code == 403


def test_reset_password_and_unlock(client: TestClient, db: Session, admin: Actor) -> None:
    u = make_user(db)
    r = client.post(f"{USERS}/{u.id}/reset-password", headers=admin.headers,
                    json={"temporary_password": "Reset-Password-99", "reason": "forgot password"})
    assert r.status_code == 200 and r.json()["must_change_password"] is True
    assert client.post("/api/v1/auth/login", json={"email": u.email, "password": PASSWORD}).status_code == 401
    # Only security.manage may unlock
    assert client.post(f"{USERS}/{u.id}/unlock", headers=admin.headers, json={"reason": "verified"}).status_code == 403
    sec = make_user(db, roles=[("SECURITY_ADMIN", None)])
    from datetime import timedelta

    from app.models.base import utcnow
    u.locked_until = utcnow() + timedelta(minutes=10)
    db.flush()
    ok = client.post(f"{USERS}/{u.id}/unlock", headers=login(client, sec), json={"reason": "identity verified"})
    assert ok.status_code == 200 and ok.json()["is_locked"] is False


def test_unknown_user_404(client: TestClient, admin: Actor) -> None:
    r = client.get(f"{USERS}/00000000-0000-0000-0000-000000000000", headers=admin.headers)
    assert r.status_code == 404 and r.json()["error_code"] == "USER_NOT_FOUND"
