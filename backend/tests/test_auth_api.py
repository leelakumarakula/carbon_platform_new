"""Authentication API: login, lockout, refresh rotation + reuse detection, logout, password change."""
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import false, select, true
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AuditLog, LoginAudit, RefreshToken, SecurityEvent, User, UserSession
from app.models.base import utcnow
from tests.conftest import PASSWORD, login, make_user

LOGIN = "/api/v1/auth/login"


def test_login_success_sets_httponly_refresh_cookie_and_audits(client: TestClient, db: Session) -> None:
    u = make_user(db)
    r = client.post(LOGIN, json={"email": u.email.upper(), "password": PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and body["expires_in"] > 0 and body["must_change_password"] is False
    cookie = r.headers["set-cookie"]
    assert "cp_refresh=" in cookie and "HttpOnly" in cookie and "samesite=strict" in cookie.lower()
    assert "Path=/api/v1/auth" in cookie
    assert db.scalars(select(LoginAudit).where(LoginAudit.user_id == u.id, LoginAudit.success == true())).first()
    assert db.scalars(select(AuditLog).where(AuditLog.user_id == u.id, AuditLog.action == "LOGIN_SUCCEEDED")).first()
    assert db.get(User, u.id).last_login_at is not None


def test_login_failure_is_generic_for_unknown_email_and_bad_password(client: TestClient, db: Session) -> None:
    u = make_user(db)
    a = client.post(LOGIN, json={"email": "nobody@test.example", "password": PASSWORD})
    b = client.post(LOGIN, json={"email": u.email, "password": "Wrong-Password-1"})
    assert a.status_code == b.status_code == 401
    assert a.json()["error_code"] == b.json()["error_code"] == "INVALID_CREDENTIALS"
    assert a.json()["message"] == b.json()["message"]
    reasons = {r.failure_reason for r in db.scalars(select(LoginAudit).where(LoginAudit.success == false())).all()}
    assert {"UNKNOWN_EMAIL", "BAD_PASSWORD"} <= reasons


def test_lockout_after_max_failures_blocks_even_correct_password(client: TestClient, db: Session) -> None:
    u = make_user(db)
    for _ in range(get_settings().MAX_FAILED_LOGINS):
        assert client.post(LOGIN, json={"email": u.email, "password": "Wrong-Password-1"}).status_code == 401
    db.refresh(u)
    assert u.locked_until is not None and u.locked_until > utcnow()
    assert client.post(LOGIN, json={"email": u.email, "password": PASSWORD}).status_code == 401
    assert db.scalars(select(SecurityEvent).where(SecurityEvent.user_id == u.id,
                                                  SecurityEvent.event_type == "ACCOUNT_LOCKED")).first()
    assert db.scalars(select(LoginAudit).where(LoginAudit.failure_reason == "ACCOUNT_LOCKED")).first()


def test_suspended_user_cannot_login(client: TestClient, db: Session) -> None:
    u = make_user(db, status="SUSPENDED")
    assert client.post(LOGIN, json={"email": u.email, "password": PASSWORD}).status_code == 401


def test_validation_error_envelope(client: TestClient) -> None:
    r = client.post(LOGIN, json={"email": "not-an-email", "password": ""})
    assert r.status_code == 422
    body = r.json()
    assert body["success"] is False and body["error_code"] == "VALIDATION_FAILED" and body["request_id"]
    assert {e["field"] for e in body["details"]["errors"]} >= {"email", "password"}


def test_me_requires_auth_and_returns_permissions(client: TestClient, db: Session) -> None:
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401 and r.json()["error_code"] == "AUTHENTICATION_FAILED"
    assert r.headers.get("www-authenticate") == "Bearer"
    u = make_user(db, roles=[("SUPPORT", None)])
    me = client.get("/api/v1/auth/me", headers=login(client, u)).json()
    assert me["user"]["email"] == u.email
    assert set(me["permissions"]) == {"users.read", "organizations.read", "farmers.read", "farms.read"}
    assert me["user"]["roles"][0]["role_code"] == "SUPPORT"


def test_refresh_rotates_and_reuse_revokes_session(client: TestClient, db: Session) -> None:
    u = make_user(db)
    client.post(LOGIN, json={"email": u.email, "password": PASSWORD})
    first = client.cookies.get("cp_refresh")
    r1 = client.post("/api/v1/auth/refresh")
    assert r1.status_code == 200
    second = client.cookies.get("cp_refresh")
    assert second and second != first
    # Present the already-used first token again (as an attacker would).
    client.cookies.clear()
    r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": first})
    assert r2.status_code == 401 and r2.json()["error_code"] == "REFRESH_REUSED"
    session = db.scalars(select(UserSession).where(UserSession.user_id == u.id)).one()
    assert session.revoked_reason == "REFRESH_TOKEN_REUSE"
    # The legitimate (second) token no longer works either, nor does the access token.
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": second}).status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {r1.json()['access_token']}"}).status_code == 401
    assert db.scalars(select(SecurityEvent).where(SecurityEvent.event_type == "REFRESH_TOKEN_REUSE")).first()


def test_expired_refresh_token_rejected(client: TestClient, db: Session) -> None:
    u = make_user(db)
    client.post(LOGIN, json={"email": u.email, "password": PASSWORD})
    rt = db.scalars(select(RefreshToken).where(RefreshToken.user_id == u.id)).one()
    rt.expires_at = utcnow() - timedelta(seconds=1)
    db.flush()
    r = client.post("/api/v1/auth/refresh")
    assert r.status_code == 401 and r.json()["error_code"] == "REFRESH_EXPIRED"


def test_logout_revokes_session_and_access_token(client: TestClient, db: Session) -> None:
    u = make_user(db)
    h = login(client, u)
    assert client.post("/api/v1/auth/logout").status_code == 200
    r = client.get("/api/v1/auth/me", headers=h)
    assert r.status_code == 401 and r.json()["error_code"] == "SESSION_REVOKED"
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_must_change_password_gates_everything_until_changed(client: TestClient, db: Session) -> None:
    u = make_user(db, roles=[("PLATFORM_ADMIN", None)], must_change=True)
    h = login(client, u)
    r = client.get("/api/v1/admin/users", headers=h)
    assert r.status_code == 403 and r.json()["error_code"] == "PASSWORD_CHANGE_REQUIRED"
    assert client.get("/api/v1/auth/me", headers=h).status_code == 200
    bad = client.post("/api/v1/auth/change-password", headers=h,
                      json={"current_password": PASSWORD, "new_password": "short"})
    assert bad.status_code == 422 and bad.json()["error_code"] == "PASSWORD_POLICY"
    same = client.post("/api/v1/auth/change-password", headers=h,
                       json={"current_password": PASSWORD, "new_password": PASSWORD})
    assert same.json()["error_code"] == "PASSWORD_REUSED"
    ok = client.post("/api/v1/auth/change-password", headers=h,
                     json={"current_password": PASSWORD, "new_password": "Brand-New-Secret-7"})
    assert ok.status_code == 200
    assert client.get("/api/v1/admin/users", headers=h).status_code == 200
    assert client.post(LOGIN, json={"email": u.email, "password": "Brand-New-Secret-7"}).status_code == 200


def test_change_password_revokes_other_sessions(client: TestClient, db: Session) -> None:
    u = make_user(db)
    h1 = login(client, u)
    h2 = login(client, u)
    client.post("/api/v1/auth/change-password", headers=h2,
                json={"current_password": PASSWORD, "new_password": "Brand-New-Secret-7"})
    assert client.get("/api/v1/auth/me", headers=h1).status_code == 401
    assert client.get("/api/v1/auth/me", headers=h2).status_code == 200


def test_wrong_current_password(client: TestClient, db: Session) -> None:
    u = make_user(db)
    r = client.post("/api/v1/auth/change-password", headers=login(client, u),
                    json={"current_password": "Nope-nope-123", "new_password": "Brand-New-Secret-7"})
    assert r.status_code == 422 and r.json()["error_code"] == "CURRENT_PASSWORD_INCORRECT"


def test_login_rate_limit(client: TestClient, db: Session, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(get_settings(), "LOGIN_RATE_LIMIT_PER_MINUTE", 3)
    codes = [client.post(LOGIN, json={"email": "x@test.example", "password": "whatever-123"}).status_code
             for _ in range(5)]
    assert codes[:3] == [401, 401, 401] and codes[3:] == [429, 429]
    assert db.scalars(select(SecurityEvent).where(SecurityEvent.event_type == "LOGIN_RATE_LIMITED")).first()


def test_oauth2_token_endpoint_for_swagger(client: TestClient, db: Session) -> None:
    u = make_user(db)
    r = client.post("/api/v1/auth/token", data={"username": u.email, "password": PASSWORD})
    assert r.status_code == 200 and r.json()["access_token"]


def test_deactivated_user_token_stops_working(client: TestClient, db: Session) -> None:
    u = make_user(db)
    h = login(client, u)
    u.status = "DEACTIVATED"
    db.flush()
    r = client.get("/api/v1/auth/me", headers=h)
    assert r.status_code == 401 and r.json()["error_code"] == "ACCOUNT_INACTIVE"
