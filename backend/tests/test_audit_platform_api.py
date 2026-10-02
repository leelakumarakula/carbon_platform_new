"""Audit trail, security views, platform behaviour (headers, envelope, limits, access log), seeds."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.models import AuditLog, Organization, User
from app.seed.accounts import DEMO_USERS, seed_demo
from app.seed.reference import sync_reference
from tests.conftest import Actor, login, make_org, make_user


# ---------- audit ----------
def test_audit_log_listing_and_filters(client: TestClient, db: Session, admin: Actor) -> None:
    u = make_user(db)
    client.patch(f"/api/v1/admin/users/{u.id}", headers=admin.headers, json={"full_name": "Audited Name"})
    r = client.get("/api/v1/admin/audit-logs", headers=admin.headers,
                   params={"entity_type": "user", "entity_id": str(u.id)}).json()
    assert r["total"] == 1
    row = r["items"][0]
    assert row["action"] == "USER_UPDATED" and row["user_email"] == admin.user.email
    assert row["old_value"] == {"full_name": "Test User"} and row["new_value"] == {"full_name": "Audited Name"}
    assert row["request_id"]


@pytest.mark.parametrize("stmt", ["UPDATE audit_logs SET reason = 'tampered'", "DELETE FROM audit_logs",
                                  "UPDATE login_audit SET success = 1", "DELETE FROM security_events",
                                  "DELETE FROM workflow_events"])
def test_audit_tables_are_append_only_in_the_database(stmt: str) -> None:
    """THROW inside the trigger aborts the whole transaction, so use a dedicated connection."""
    from app.core.database import get_engine
    with get_engine().connect() as conn:
        trans = conn.begin()
        conn.execute(text("INSERT INTO audit_logs (action, entity_type) VALUES ('TEST', 'test')"))
        conn.execute(text("INSERT INTO login_audit (email_attempted, success) VALUES ('t@test.example', 0)"))
        conn.execute(text("INSERT INTO security_events (event_type, severity) VALUES ('TEST', 'INFO')"))
        conn.execute(text("INSERT INTO workflow_events (entity_type, entity_id, to_status) VALUES ('t', '1', 'X')"))
        with pytest.raises(DBAPIError) as e:
            conn.execute(text(stmt))
        assert "append-only" in str(e.value)
        if trans.is_active:
            trans.rollback()


def test_security_views_require_security_read(client: TestClient, db: Session, admin: Actor) -> None:
    support = make_user(db, roles=[("SUPPORT", None)])
    h = login(client, support)
    assert client.get("/api/v1/admin/security/events", headers=h).status_code == 403
    assert client.get("/api/v1/admin/audit-logs", headers=h).status_code == 403
    client.post("/api/v1/auth/login", json={"email": "ghost@test.example", "password": "Whatever-123"})
    la = client.get("/api/v1/admin/security/login-audit", headers=admin.headers, params={"success": False}).json()
    assert any(r["email_attempted"] == "ghost@test.example" and r["failure_reason"] == "UNKNOWN_EMAIL" for r in la["items"])


def test_sessions_list_and_admin_revoke(client: TestClient, db: Session) -> None:
    sec = make_user(db, roles=[("SECURITY_ADMIN", None)])
    hs = login(client, sec)
    victim = make_user(db)
    hv = login(client, victim)
    sessions = client.get("/api/v1/admin/security/sessions", headers=hs, params={"user_id": str(victim.id)}).json()
    assert sessions["total"] == 1 and sessions["items"][0]["is_active"]
    sid = sessions["items"][0]["id"]
    r = client.post(f"/api/v1/admin/security/sessions/{sid}/revoke", headers=hs, json={"reason": "suspicious device"})
    assert r.status_code == 200
    assert client.get("/api/v1/auth/me", headers=hv).status_code == 401
    assert db.scalars(select(AuditLog).where(AuditLog.action == "SESSION_REVOKED", AuditLog.entity_id == sid)).first()


def test_workflow_events_endpoint(client: TestClient, db: Session, admin: Actor) -> None:
    org = make_org(db)
    client.post(f"/api/v1/admin/organizations/{org.id}/status", headers=admin.headers,
                json={"status": "SUSPENDED", "reason": "payment overdue"})
    r = client.get("/api/v1/admin/workflow-events", headers=admin.headers,
                   params={"entity_type": "organization", "entity_id": str(org.id)}).json()
    assert r["items"][0]["to_status"] == "SUSPENDED" and r["items"][0]["reason"] == "payment overdue"


# ---------- platform behaviour ----------
def test_health(client: TestClient) -> None:
    r = client.get("/api/v1/health")
    assert r.status_code == 200 and r.json()["database"] == "ok"


def test_secure_headers_and_request_id(client: TestClient) -> None:
    r = client.get("/api/v1/health", headers={"X-Request-ID": "abc12345-req"})
    assert r.headers["x-request-id"] == "abc12345-req"
    for h in ("x-content-type-options", "x-frame-options", "referrer-policy", "content-security-policy", "cache-control"):
        assert h in r.headers
    assert r.headers["cache-control"] == "no-store"
    bad = client.get("/api/v1/health", headers={"X-Request-ID": "<script>"})
    assert bad.headers["x-request-id"] != "<script>"


def test_error_envelope_for_unknown_route(client: TestClient) -> None:
    r = client.get("/api/v1/does-not-exist")
    body = r.json()
    assert r.status_code == 404 and body == {"success": False, "error_code": "NOT_FOUND", "message": body["message"],
                                             "details": {}, "request_id": r.headers["x-request-id"]}


def test_payload_too_large(client: TestClient, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "MAX_REQUEST_BYTES", 100)
    r = client.post("/api/v1/auth/login", content=b"x" * 500, headers={"Content-Type": "application/json"})
    assert r.status_code == 413 and r.json()["error_code"] == "PAYLOAD_TOO_LARGE"


def test_cors_preflight_allows_configured_origin_only(client: TestClient) -> None:
    ok = client.options("/api/v1/auth/login", headers={"Origin": "http://localhost:4200",
                                                       "Access-Control-Request-Method": "POST"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:4200"
    assert ok.headers.get("access-control-allow-credentials") == "true"
    evil = client.options("/api/v1/auth/login", headers={"Origin": "https://evil.example",
                                                         "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in evil.headers


def test_api_access_log_records_user(client: TestClient, db: Session, admin: Actor, access_log: list[dict]) -> None:
    access_log.clear()
    client.get("/api/v1/auth/me", headers=admin.headers)
    entry = access_log[-1]
    assert entry["path"] == "/api/v1/auth/me" and entry["status_code"] == 200
    assert entry["user_id"] == admin.user.id and entry["request_id"] and entry["duration_ms"] >= 0


def test_openapi_lists_versioned_routes(client: TestClient) -> None:
    paths = client.get("/api/v1/openapi.json").json()["paths"]
    assert "/api/v1/auth/login" in paths and "/api/v1/admin/users" in paths


# ---------- seeds ----------
def test_reference_sync_is_idempotent(db: Session) -> None:
    assert sync_reference(db) == {"permissions_added": 0, "roles_added": 0, "role_permission_changes": 0, "consent_definitions_added": 0}
    assert db.scalars(select(Organization).where(Organization.code == "PLATFORM")).one().org_type == "PLATFORM"


def test_demo_seed_marks_everything_demo_and_is_idempotent(db: Session) -> None:
    seed_demo(db, "Demo-Password-123")
    again = seed_demo(db, "Demo-Password-123")
    assert again == {"organizations": 0, "users": 0}
    demo_users = db.scalars(select(User).where(User.email.like("%@demo.carbon.example"))).all()
    assert len(demo_users) == len(DEMO_USERS) and {u.environment for u in demo_users} == {"DEMO"}
    assert {o.environment for o in db.scalars(select(Organization).where(Organization.code.like("DEMO-%"))).all()} == {"DEMO"}


def test_demo_seed_refuses_to_mix_with_live(db: Session) -> None:
    from app.core.errors import AppError
    make_org(db, "DEMO-DEV-A")  # LIVE org squatting a demo code
    with pytest.raises(AppError) as e:
        seed_demo(db, "Demo-Password-123")
    assert e.value.error_code == "DEMO_CONFLICT"


def test_timestamps_are_utc_iso_with_z(client: TestClient, admin: Actor) -> None:
    me = client.get("/api/v1/auth/me", headers=admin.headers).json()
    assert me["user"]["created_at"].endswith("Z") and me["user"]["last_login_at"].endswith("Z")


def test_role_revoke_reason_is_audited(client: TestClient, db: Session, admin: Actor) -> None:
    u = make_user(db, roles=[("SUPPORT", None)])
    grant = client.get(f"/api/v1/admin/users/{u.id}", headers=admin.headers).json()["roles"][0]["id"]
    r = client.delete(f"/api/v1/admin/users/{u.id}/roles/{grant}", headers=admin.headers, params={"reason": "role no longer needed"})
    assert r.status_code == 200
    row = db.scalars(select(AuditLog).where(AuditLog.action == "ROLE_REVOKED", AuditLog.entity_id == str(u.id))).one()
    assert row.reason == "role no longer needed"


def test_demo_farmers_and_farms_seed(db: Session) -> None:
    from app.models import Farm, Farmer, FarmOverlapCheck
    from app.seed.demo_farms import seed_demo_farms
    seed_demo(db, "Demo-Password-123")
    assert seed_demo_farms(db) == {"farmers": 5, "farms": 10}
    assert seed_demo_farms(db) == {"farmers": 0, "farms": 0}  # idempotent
    farmers = db.scalars(select(Farmer).where(Farmer.environment == "DEMO")).all()
    farms = db.scalars(select(Farm).where(Farm.environment == "DEMO")).all()
    assert len(farmers) == 5 and {f.status for f in farmers} == {"ACTIVE"} and all(f.kyc_id_last4 for f in farmers)
    assert len(farms) == 10 and sorted(f.status for f in farms).count("VERIFIED") == 6
    assert all(f.area_hectares and f.area_hectares > 0 for f in farms)
    assert db.scalars(select(FarmOverlapCheck).where(FarmOverlapCheck.status == "OPEN")).first()
    assert any(f.user_id for f in farmers)  # demo farmer login linked for self-service


def test_demo_projects_seed(db: Session) -> None:
    from app.models import Project, ProjectCarbonRight, ProjectFarm, Standard
    from app.seed.demo_farms import seed_demo_farms
    from app.seed.demo_projects import seed_demo_projects
    seed_demo(db, "Demo-Password-123")
    seed_demo_farms(db)
    assert seed_demo_projects(db) == {"projects": 2, "standards": 2, "activities": 3}
    assert seed_demo_projects(db) == {"projects": 0, "standards": 0, "activities": 0}  # idempotent
    projects = db.scalars(select(Project).where(Project.environment == "DEMO")).all()
    assert sorted(p.status for p in projects) == ["ACTIVITY_SELECTED", "DATA_COLLECTION"]
    assert all(p.methodology_status == "NOT_SELECTED" and p.standard_id and p.activity_id and p.current_boundary_id for p in projects)
    farms = db.scalars(select(ProjectFarm).where(ProjectFarm.project_id.in_([p.id for p in projects]))).all()
    assert len(farms) == 6 and {f.status for f in farms} == {"ACTIVE"}
    rights = db.scalars(select(ProjectCarbonRight).where(ProjectCarbonRight.project_id.in_([p.id for p in projects]))).all()
    assert len(rights) == 6 and all(r.agreement_id for r in rights)
    assert {s.environment for s in db.scalars(select(Standard).where(Standard.code.like("DEMO-%"))).all()} == {"DEMO"}


def test_demo_methodologies_seed(db: Session) -> None:
    from app.models import Methodology, MethodologyVersion, Project, ProjectMethodology
    from app.seed.demo_farms import seed_demo_farms
    from app.seed.demo_methodologies import seed_demo_methodologies
    from app.seed.demo_projects import seed_demo_projects
    seed_demo(db, "Demo-Password-123")
    seed_demo_farms(db)
    seed_demo_projects(db)
    assert seed_demo_methodologies(db) == {"methodologies": 2, "locked_projects": 1}
    assert seed_demo_methodologies(db) == {"methodologies": 0, "locked_projects": 0}  # idempotent
    ms = db.scalars(select(Methodology).where(Methodology.code.like("DEMO-%"))).all()
    assert {m.environment for m in ms} == {"DEMO"}
    versions = db.scalars(select(MethodologyVersion).where(MethodologyVersion.methodology_id.in_([m.id for m in ms]))).all()
    assert sorted(v.status for v in versions) == ["APPROVED", "APPROVED", "APPROVED", "DRAFT"]
    assert all(v.is_demo_illustrative and v.calculation_readiness == "NOT_PRODUCTION_READY" for v in versions)
    locked = db.scalars(select(ProjectMethodology).where(ProjectMethodology.status == "LOCKED")).all()
    b = db.get(Project, locked[0].project_id)
    assert b is not None and b.status == "METHODOLOGY_CONFIRMED" and b.methodology_status == "CONFIRMED"
