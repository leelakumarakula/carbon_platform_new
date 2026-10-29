"""Identity / HTTP fixes of 29/10: the sign-in lockout no longer ends live sessions, rate-limited sign-ins are audited once per
window, CORS allows Idempotency-Key, unhandled errors keep the request id / CORS headers / access log, X-Request-ID is adopted
only from trusted proxies, NULL-user security rows stay out of DEMO, platform listings avoid IN lists of every organization,
seed-demo refuses production, member removal takes the account-management checks, and restore SQL escapes its literals."""
import json
import uuid
from typing import Any

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db, get_engine
from app.core.rate_limit import limiter
from app.main import create_app
from app.models import LoginAudit, OrganizationUser, Permission, Role, RolePermission, SecurityEvent, UserRole
from app.models.base import Environment
from app.ops import sqlserver as sq
from app.security.principal import EnvironmentOrganizations, load_principal
from tests.conftest import PASSWORD, Actor, login, make_org, make_user

API = "/api/v1"
LOGIN = f"{API}/auth/login"
ORGS = f"{API}/admin/organizations"


def _custom_role(db: Session, code: str, perms: list[str]) -> Role:
    r = Role(code=code, name=code, scope="ORGANIZATION", is_system=False)
    r.permissions = [RolePermission(permission=p) for p in db.scalars(select(Permission).where(Permission.code.in_(perms))).all()]
    db.add(r)
    db.flush()
    return r


# ---------------------------------------------------------------- 1: lockout blocks new sign-ins only
def test_lockout_does_not_end_the_victims_live_session(client: TestClient, db: Session) -> None:
    u = make_user(db)
    h = login(client, u)
    for _ in range(get_settings().MAX_FAILED_LOGINS):       # a stranger types wrong passwords for the victim's email
        assert client.post(LOGIN, json={"email": u.email, "password": "Wrong-Password-1"}).status_code == 401
    db.refresh(u)
    assert u.is_locked()
    assert client.get(f"{API}/auth/me", headers=h).status_code == 200            # the live session continues
    assert client.post(f"{API}/auth/refresh").status_code == 200                 # ... and can be refreshed
    assert client.post(LOGIN, json={"email": u.email, "password": PASSWORD}).status_code == 401   # new sign-ins still blocked
    u.status = "SUSPENDED"                                                       # suspension still ends everything
    db.flush()
    r = client.get(f"{API}/auth/me", headers=h)
    assert r.status_code == 401 and r.json()["error_code"] == "ACCOUNT_INACTIVE"


# ---------------------------------------------------------------- 2: one audit row per rate-limit window
def test_rate_limited_sign_ins_are_audited_once_per_window(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "LOGIN_RATE_LIMIT_PER_MINUTE", 2)
    email = f"flood{uuid.uuid4().hex[:8]}@test.example"
    codes = [client.post(LOGIN, json={"email": email, "password": "whatever-123"}).status_code for _ in range(8)]
    assert codes[:2] == [401, 401] and set(codes[2:]) == {429}
    events = [e for e in db.scalars(select(SecurityEvent).where(SecurityEvent.event_type == "LOGIN_RATE_LIMITED")).all()
              if e.details and json.loads(e.details).get("email") == email]
    assert len(events) == 1                                                      # 6 refusals, one security event
    assert db.scalar(select(func.count()).select_from(LoginAudit).where(LoginAudit.email_attempted == email,
                                                                        LoginAudit.failure_reason == "RATE_LIMITED")) == 1


# ---------------------------------------------------------------- 3: CORS preflight allows Idempotency-Key
def test_cors_preflight_allows_idempotency_key(client: TestClient) -> None:
    origin = get_settings().CORS_ORIGINS[0]
    r = client.options(f"{API}/auth/login", headers={"Origin": origin, "Access-Control-Request-Method": "POST",
                                                      "Access-Control-Request-Headers": "idempotency-key, content-type"})
    assert r.status_code == 200 and "idempotency-key" in r.headers["access-control-allow-headers"].lower()


# ---------------------------------------------------------------- 4 + 5: 500 envelope inside the middleware, request id rule
@pytest.fixture()
def boom_client(db: Session, access_log: list[dict]) -> TestClient:
    app = create_app()
    extra = APIRouter()

    @extra.get(f"{API}/__boom_test")
    def boom() -> None:
        raise RuntimeError("unexpected failure")

    app.include_router(extra)
    app.dependency_overrides[get_db] = lambda: db
    app.state.access_log_writer = access_log.append
    limiter.reset()
    return TestClient(app, base_url="http://testserver", raise_server_exceptions=False)


def test_unhandled_error_keeps_request_id_cors_and_access_log(boom_client: TestClient, access_log: list[dict]) -> None:
    origin = get_settings().CORS_ORIGINS[0]
    r = boom_client.get(f"{API}/__boom_test", headers={"Origin": origin})
    body = r.json()
    assert r.status_code == 500 and body["success"] is False and body["error_code"] == "INTERNAL_ERROR"
    assert body["request_id"] and r.headers["x-request-id"] == body["request_id"]
    assert r.headers["access-control-allow-origin"] == origin
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["cache-control"] == "no-store"
    assert [(e["status_code"], e["request_id"]) for e in access_log if e["path"] == f"{API}/__boom_test"] == [(500, body["request_id"])]


def test_request_id_is_adopted_only_from_trusted_proxies(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    app.state.access_log_writer = None
    planted = "client-chosen-id-1234"
    with TestClient(app, base_url="http://testserver", client=("203.0.113.9", 5000)) as direct:
        r = direct.get(f"{API}/health/live", headers={"X-Request-ID": planted})
        assert r.headers["x-request-id"] != planted
        uuid.UUID(r.headers["x-request-id"])                                     # a generated one
    monkeypatch.setattr(get_settings(), "TRUSTED_PROXIES", ["10.0.0.0/8"])
    with TestClient(app, base_url="http://testserver", client=("10.1.2.3", 5000)) as proxied:
        assert proxied.get(f"{API}/health/live", headers={"X-Request-ID": planted}).headers["x-request-id"] == planted
        bad = proxied.get(f"{API}/health/live", headers={"X-Request-ID": "bad id; drop"}).headers["x-request-id"]
        assert bad != "bad id; drop"


# ---------------------------------------------------------------- 6: NULL-user security rows are LIVE-only
def test_null_user_login_attempts_are_hidden_from_demo(client: TestClient, db: Session) -> None:
    email = f"live-person{uuid.uuid4().hex[:6]}@test.example"
    client.post(LOGIN, json={"email": email, "password": "whatever-123"})        # unknown email: user_id NULL
    demo = make_user(db, roles=[("SECURITY_ADMIN", None)], environment=Environment.DEMO.value)
    live = make_user(db, roles=[("SECURITY_ADMIN", None)])

    def emails(u: Any) -> set[str]:
        h = login(client, u)
        rows = client.get(f"{API}/admin/security/login-audit", headers=h, params={"page_size": 100}).json()["items"]
        return {r["email_attempted"] for r in rows}

    assert email in emails(live)
    assert email not in emails(demo)


# ---------------------------------------------------------------- 7: no IN list of every organization
def _max_params(client: TestClient, url: str, h: dict) -> int:
    counts: list[int] = []

    def capture(conn: object, cursor: object, statement: str, params: object, *args: object) -> None:
        counts.append(len(params) if isinstance(params, (tuple, list)) else 0)

    event.listen(get_engine(), "before_cursor_execute", capture)
    try:
        assert client.get(url, headers=h).status_code == 200
    finally:
        event.remove(get_engine(), "before_cursor_execute", capture)
    return max(counts)


def test_platform_listings_do_not_bind_every_organization(client: TestClient, db: Session, admin: Actor) -> None:
    for _ in range(40):
        make_org(db)
    assert _max_params(client, f"{ORGS}?page_size=5", admin.headers) < 20
    assert _max_params(client, f"{API}/admin/audit-logs?page_size=5", admin.headers) < 20


def test_environment_organizations_are_read_on_demand(db: Session) -> None:
    live_org, demo_org = make_org(db), make_org(db, environment=Environment.DEMO.value)
    p = load_principal(db, make_user(db), None)
    env = p.environment_organization_ids
    assert isinstance(env, EnvironmentOrganizations) and env._ids is None       # nothing loaded per request
    assert p.in_environment(live_org.id) and not p.in_environment(demo_org.id)
    assert env._ids is None                                                      # point lookups only
    ids = set(env)
    assert live_org.id in ids and demo_org.id not in ids and len(env) == len(ids)


# ---------------------------------------------------------------- 8: seed-demo refuses production
def test_seed_demo_refuses_production(monkeypatch: pytest.MonkeyPatch) -> None:
    import manage
    monkeypatch.setattr(get_settings(), "APP_ENV", "production")
    with pytest.raises(SystemExit, match="production"):
        manage.seed_demo()


# ---------------------------------------------------------------- 9: member removal takes the account-management checks
def test_member_removal_needs_users_manage_and_no_escalation(client: TestClient, db: Session) -> None:
    x, y = make_org(db), make_org(db)
    _custom_role(db, "FIX29_ORG_ADMIN", ["users.read", "users.manage", "users.assign_roles", "organizations.read",
                                         "organizations.manage_members"])
    auditor = _custom_role(db, "FIX29_ORG_AUDITOR", ["audit.read"])                  # a privileged permission the admin lacks
    h = login(client, make_user(db, roles=[("FIX29_ORG_ADMIN", x)]))
    plain = make_user(db, roles=[("FIELD_AGENT", x)])
    privileged = make_user(db, orgs=[x])
    db.add(UserRole(user_id=privileged.id, role_id=auditor.id, organization_id=x.id))
    shared = make_user(db, roles=[("FIELD_AGENT", x)], orgs=[y])                       # also in an organization out of scope
    db.flush()

    def remove(u: Any) -> Any:
        return client.post(f"{ORGS}/{x.id}/members/{u.id}/remove", headers=h, json={"reason": "cleanup"})

    r = remove(privileged)
    assert r.status_code == 403 and r.json()["error_code"] == "ROLE_ESCALATION_BLOCKED"
    assert remove(shared).status_code == 403
    for u in (privileged, shared):                                                   # memberships and grants untouched
        assert db.scalar(select(OrganizationUser).where(OrganizationUser.organization_id == x.id, OrganizationUser.user_id == u.id))
        assert db.scalars(select(UserRole).where(UserRole.user_id == u.id, UserRole.organization_id == x.id)).first()
    assert remove(plain).status_code == 200                                          # control
    assert not db.scalars(select(UserRole).where(UserRole.user_id == plain.id, UserRole.organization_id == x.id)).first()


def test_member_removal_with_roles_needs_assign_roles(client: TestClient, db: Session) -> None:
    x = make_org(db)
    _custom_role(db, "FIX29_MEMBER_ADMIN", ["users.read", "users.manage", "organizations.read", "organizations.manage_members"])
    h = login(client, make_user(db, roles=[("FIX29_MEMBER_ADMIN", x)]))
    with_role, without_role = make_user(db, roles=[("FIELD_AGENT", x)]), make_user(db, orgs=[x])
    r = client.post(f"{ORGS}/{x.id}/members/{with_role.id}/remove", headers=h, json={"reason": "cleanup"})
    assert r.status_code == 403 and r.json()["details"]["required_permission"] == "users.assign_roles"
    assert client.post(f"{ORGS}/{x.id}/members/{without_role.id}/remove", headers=h, json={"reason": "cleanup"}).status_code == 200


# ---------------------------------------------------------------- 10: restore statements escape their literals
def test_restore_sql_escapes_paths_and_logical_names(monkeypatch: pytest.MonkeyPatch) -> None:
    assert sq.sql_string("a'b") == "N'a''b'"
    assert sq.backup_source("C:\\b\\o'brien.bak") == "DISK = N'C:\\b\\o''brien.bak'"
    assert sq.backup_source("s3://x/y.bak").startswith("URL = N'")
    with pytest.raises(sq.UnsafeTarget):
        sq.sql_string("x.bak'\n; DROP DATABASE prod --")
    sql = sq.restore_sql("carbon_restoretest", sq.backup_source("C:\\b\\x'; SHUTDOWN --.bak"),
                         [("data']; DROP DATABASE [carbon", "D"), ("log", "L")], "C:\\data", replace=True)
    assert "MOVE N'data'']; DROP DATABASE [carbon' TO N'C:\\data\\carbon_restoretest_0.mdf'" in sql
    assert "DISK = N'C:\\b\\x''; SHUTDOWN --.bak'" in sql and sql.endswith("RECOVERY, REPLACE")
    with pytest.raises(sq.UnsafeTarget):
        sq.restore_sql("carbon", "DISK = N'x'", [], "C:\\data", replace=False)          # never a non-scratch database
