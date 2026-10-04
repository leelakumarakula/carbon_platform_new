"""Phase 12B-III — operations: restore verification (D27), backup safety (D26), retention (D48), disk-space safeguards.

Real SQL Server backups / restores run against the TEST database only (COPY_ONLY: no backup chain is affected) into scratch databases
named `*_restoretest`, which are always dropped; the drill's backup file is deleted. Production backup infrastructure (encrypted,
off-host, immutable) is not available locally: its rules are tested as refusals, never as fake successes.
"""
import json
import os
import time
import uuid
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.context import RequestContext
from app.integrations.storage import get_storage
from app.models import ApiAccessLog, AuditLog, BackgroundJob, BackgroundWorkerHeartbeat, Notification
from app.models.base import utcnow
from app.models.jobs import SYSTEM_ACTOR_IDS
from app.ops import disk
from app.ops import sqlserver as sq
from app.ops.drill import restore_drill
from app.ops.verify_restore import MANIFEST, build_manifest, code_head, verify_restore
from app.workers import handlers, job_service
from tests.conftest import make_user
from tests.phase2 import PDF, create_farmer, dev_org, staff, upload

TEST_DB = get_settings().SQL_SERVER_DATABASE


@pytest.fixture(autouse=True)
def _no_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "REDIS_URL", None)


# ---------------------------------------------------------------- target safety (never the live / application database)
@pytest.mark.parametrize("name", [TEST_DB, "master", "msdb", "tempdb", "model", "carbon_platform", "x]; DROP DATABASE y; --",
                                  "carbon_platform_test_restore", ""])
def test_scratch_targets_are_restricted(name: str) -> None:
    with pytest.raises(sq.UnsafeTarget):
        sq.check_scratch(name)


def test_scratch_operations_refused_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "APP_ENV", "production")
    with pytest.raises(sq.UnsafeTarget, match="production"):
        sq.check_scratch("anything_restoretest")
    with pytest.raises(sq.UnsafeTarget):
        restore_drill(TEST_DB)


def test_production_backups_must_be_encrypted_and_off_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "APP_ENV", "production")
    with pytest.raises(sq.UnsafeTarget, match="encrypted"):
        sq.backup(TEST_DB, "log")                                         # no certificate, local disk: refused before anything runs
    monkeypatch.setattr(get_settings(), "BACKUP_ENCRYPTION_CERT", "carbon_backup_cert")
    with pytest.raises(sq.UnsafeTarget, match="off-host"):
        sq.backup(TEST_DB, "log", destination=r"C:\backups\x.bak")


def test_backup_statements() -> None:
    full = sq.backup_sql("db1", "full", "s3://store/carbon/db1_full.bak", copy_only=False, certificate="carbon_backup_cert")
    assert full.startswith("BACKUP DATABASE [db1] TO URL = N's3://store/carbon/db1_full.bak'")
    assert "CHECKSUM" in full and "COMPRESSION" in full and "ENCRYPTION (ALGORITHM = AES_256, SERVER CERTIFICATE = [carbon_backup_cert])" in full
    assert "DIFFERENTIAL" in sq.backup_sql("db1", "diff", r"C:\b\d.bak", copy_only=False, certificate=None)
    assert sq.backup_sql("db1", "log", r"C:\b\l.bak", copy_only=True, certificate=None).startswith("BACKUP LOG [db1] TO DISK")
    for bad in ("db1; DROP", "[db1]"):
        with pytest.raises(sq.UnsafeTarget):
            sq.backup_sql(bad, "full", r"C:\b\x.bak", copy_only=False, certificate=None)
    with pytest.raises(sq.UnsafeTarget):
        sq.backup_sql("db1", "full", "C:\\b\\x'.bak", copy_only=False, certificate=None)
    with pytest.raises(sq.UnsafeTarget):
        sq.delete_backup_file(sq.master_engine(), r"C:\Windows\system32\config\SAM")


def test_backup_and_retention_configuration_guards(tmp_path: Any) -> None:
    from pydantic import ValidationError

    from app.core.config import Settings
    base = get_settings().model_dump()
    for over in ({"BACKUP_URL": "https://store/x"}, {"BACKUP_ENCRYPTION_CERT": "cert; DROP"}, {"OPERATIONAL_RETENTION_DAYS": 0},
                 {"DISK_CRITICAL_FREE_MB": 4096, "DISK_WARN_FREE_MB": 2048}):
        with pytest.raises(ValidationError):
            Settings(**{**base, **over})
    from tests.test_runtime_hardening import _prod
    with pytest.raises(ValidationError, match="at least 60 days"):
        Settings(**_prod(tmp_path, OPERATIONAL_RETENTION_DAYS=30))
    assert Settings(**_prod(tmp_path, OPERATIONAL_RETENTION_DAYS=90)).OPERATIONAL_RETENTION_DAYS == 90


# ---------------------------------------------------------------- verify-restore and the real local drill
def test_schema_manifest_matches_the_migrated_test_database() -> None:
    """The committed manifest is what verify-restore checks against: regenerate it (manage.py schema-manifest) with every migration."""
    want = json.loads(MANIFEST.read_text(encoding="utf-8"))
    eng = sq.database_engine(TEST_DB)
    try:
        with eng.connect() as c:
            have = {"head": c.execute(text("SELECT version_num FROM dbo.alembic_version")).scalar(), **build_manifest(c)}
    finally:
        eng.dispose()
    assert want == have and want["head"] == code_head()


def test_verify_restore_on_the_test_database_and_a_missing_one() -> None:
    rep = verify_restore(TEST_DB)
    assert rep.ok, [c for c in rep.checks if not c["ok"]]
    names = [c["name"] for c in rep.checks]
    for n in ("connectivity", "migration_head", "tables", "columns", "indexes", "constraints", "triggers", "triggers_enabled",
              "append_only_probe", "ledger_conservation", "settlement_reproducibility", "calculation_report_hashes", "organization_scoping"):
        assert n in names
    assert rep.row_counts and all(isinstance(v, int) for v in rep.row_counts.values())
    missing = verify_restore("carbon_does_not_exist_restoretest")
    assert not missing.ok and missing.checks[0]["name"] == "connectivity"


def test_real_restore_drill_backup_restore_verify_drop(record_property: Any) -> None:
    out = restore_drill(TEST_DB)
    assert out["ok"], [c for c in out["verification"]["checks"] if not c["ok"]]
    assert out["scratch_dropped"] and out["backup_file_deleted"] and out["backup"]["verified"] and out["backup"]["copy_only"]
    assert not out["backup"]["encrypted"] and any("UNENCRYPTED" in n for n in out["backup"]["notes"])   # local drill: honest
    assert {c["name"] for c in out["verification"]["checks"]} >= {"row_counts_match_source"}
    eng = sq.master_engine()
    try:
        assert not sq.exists(eng, out["scratch"])
        assert not eng.connect().execute(text("SELECT file_exists FROM sys.dm_os_file_exists(:p)"),
                                         {"p": out["backup"]["destination"]}).scalar()
    finally:
        eng.dispose()
    for k, v in out["timings_seconds"].items():
        record_property(f"drill_{k}_seconds", v)


def test_drill_refuses_without_disk_headroom(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sq, "server_free_mb", lambda eng, path: 100)
    with pytest.raises(disk.DiskSpaceLow):
        restore_drill(TEST_DB)
    eng = sq.master_engine()
    try:
        assert not sq.exists(eng, f"{TEST_DB}{sq.SCRATCH_SUFFIX}")
    finally:
        eng.dispose()


def test_manage_verify_restore_exit_codes(tmp_path: Any) -> None:
    import subprocess
    import sys
    env = {**os.environ, "SQL_SERVER_DATABASE": TEST_DB}   # conftest already points DATABASE_URL (if any) at TEST_DB
    report = tmp_path / "r.json"
    ok = subprocess.run([sys.executable, "manage.py", "verify-restore", "--database", TEST_DB, "--report", str(report)],  # noqa: S603
                        cwd=os.path.dirname(os.path.dirname(__file__)), env=env, capture_output=True, text=True, timeout=300)
    assert ok.returncode == 0, ok.stderr[-500:] and json.loads(report.read_text())["ok"] is True
    bad = subprocess.run([sys.executable, "manage.py", "verify-restore", "--database", "carbon_missing_restoretest"],  # noqa: S603
                         cwd=os.path.dirname(os.path.dirname(__file__)), env=env, capture_output=True, text=True, timeout=300)
    assert bad.returncode == 1
    none = subprocess.run([sys.executable, "manage.py", "verify-restore"],  # noqa: S603 - fixed argv, test only
                          cwd=os.path.dirname(os.path.dirname(__file__)), env=env, capture_output=True, text=True, timeout=300)
    assert none.returncode != 0 and "needs --database" in none.stderr


# ---------------------------------------------------------------- retention (D48)
def _old(days: int) -> Any:
    return utcnow() - timedelta(days=days)


def test_retention_purges_only_operational_records_per_environment(db: Session) -> None:
    live_user = make_user(db)
    demo_user = make_user(db, environment="DEMO")
    stamp = uuid.uuid4().hex[:8]
    for uid, tag in ((live_user.id, "live"), (demo_user.id, "demo"), (None, "anon")):
        db.add(ApiAccessLog(occurred_at=_old(61), request_id=f"old-{tag}-{stamp}", method="GET", path="/x", status_code=200,
                            duration_ms=1, user_id=uid))
        db.add(ApiAccessLog(occurred_at=_old(10), request_id=f"new-{tag}-{stamp}", method="GET", path="/x", status_code=200,
                            duration_ms=1, user_id=uid))
    for uid in (live_user.id, demo_user.id):
        db.add(Notification(recipient_user_id=uid, event_type="T", title="old read", status="SENT", read_at=_old(61)))
        db.add(Notification(recipient_user_id=uid, event_type="T", title="old unread", status="SENT", read_at=None,
                            created_at=_old(200)))
        db.add(Notification(recipient_user_id=uid, event_type="T", title="recent read", status="SENT", read_at=_old(5)))
    hb = BackgroundWorkerHeartbeat(worker_identity=f"old-worker-{stamp}", hostname="h", pid=1, queues="maintenance",
                                   started_at=_old(90), last_heartbeat_at=_old(89), stopped_at=_old(89))
    db.add(hb)
    db.flush()
    st: Any = get_storage()
    part = st.root / "live" / f"stale-{stamp}.part"
    part.parent.mkdir(parents=True, exist_ok=True)
    part.write_bytes(b"partial")
    aged = time.time() - 3 * 86400
    os.utime(part, (aged, aged))
    audit_before = db.scalar(select(func.count()).select_from(AuditLog))

    def logs(prefix: str) -> set[str]:
        return {r for (r,) in db.execute(select(ApiAccessLog.request_id).where(ApiAccessLog.request_id.like(f"{prefix}-%-{stamp}")))}

    def run(env: str) -> dict:
        ctx = RequestContext(request_id="t", user_id=SYSTEM_ACTOR_IDS[env])
        job, _ = job_service.enqueue(db, ctx, "RETENTION_PURGE", environment=env, trigger_type="SERVICE", created_by=SYSTEM_ACTOR_IDS[env])
        db.commit()
        assert job_service.execute(db, job.id, "w:1", expected_task_name=job.task_name) == "SUCCEEDED"
        return json.loads(db.get(BackgroundJob, job.id).result or "{}")  # type: ignore[union-attr]

    live = run("LIVE")
    assert live["retention_days"] == 60 and live["complete"] and "audit_logs" in live["never_purged"]
    assert logs("old") == {f"old-demo-{stamp}"}                                       # LIVE + anonymous old rows purged, DEMO kept
    assert logs("new") == {f"new-{t}-{stamp}" for t in ("live", "demo", "anon")}      # recent rows kept
    titles = {(n.recipient_user_id, n.title) for n in db.scalars(select(Notification).where(
        Notification.recipient_user_id.in_([live_user.id, demo_user.id])))}
    assert (live_user.id, "old read") not in titles and (demo_user.id, "old read") in titles
    assert (live_user.id, "old unread") in titles and (live_user.id, "recent read") in titles   # unread / recent never purged
    assert db.scalars(select(BackgroundWorkerHeartbeat).where(BackgroundWorkerHeartbeat.worker_identity == f"old-worker-{stamp}")).first() is None
    assert not part.exists() and live["by_policy"]["TEMP_UPLOAD_FILES"] >= 1
    demo = run("DEMO")
    assert logs("old") == set() and "WORKER_HEARTBEATS" not in demo["by_policy"]      # DEMO job: its own users' rows only
    again = run("LIVE")
    assert again["by_policy"]["API_ACCESS_LOGS"] == 0 and again["by_policy"]["READ_NOTIFICATIONS"] == 0   # idempotent
    purged = db.scalars(select(AuditLog).where(AuditLog.action == "RETENTION_PURGED")).all()
    assert {a.entity_id for a in purged} >= {"API_ACCESS_LOGS", "READ_NOTIFICATIONS", "WORKER_HEARTBEATS", "TEMP_UPLOAD_FILES"}
    assert db.scalar(select(func.count()).select_from(AuditLog)) > audit_before        # audit rows only ever added


def test_retention_never_touches_append_only_records(db: Session) -> None:
    """Old audit rows exist; the purge leaves every append-only / financial table exactly as it was."""
    db.add(AuditLog(occurred_at=_old(400), action="TEST_OLD", entity_type="t", entity_id="1"))
    db.commit()
    guarded = ("audit_logs", "workflow_events", "security_events", "login_audit", "background_job_attempts", "document_scans",
               "document_versions", "credit_ledger_entries", "revenue_records")
    before = {t: db.scalar(text(f"SELECT COUNT(*) FROM dbo.{t}")) for t in guarded}
    ctx = RequestContext(request_id="t", user_id=SYSTEM_ACTOR_IDS["LIVE"])
    job, _ = job_service.enqueue(db, ctx, "RETENTION_PURGE", environment="LIVE", trigger_type="SERVICE", created_by=SYSTEM_ACTOR_IDS["LIVE"])
    db.commit()
    assert job_service.execute(db, job.id, "w:1", expected_task_name=job.task_name) == "SUCCEEDED"
    after = {t: db.scalar(text(f"SELECT COUNT(*) FROM dbo.{t}")) for t in guarded}
    for t in guarded:
        assert after[t] >= before[t], t                                               # nothing removed (only job audit rows added)
    assert db.scalars(select(AuditLog).where(AuditLog.action == "TEST_OLD")).first() is not None
    assert set(handlers.RETENTION_POLICIES) == {"API_ACCESS_LOGS", "READ_NOTIFICATIONS", "WORKER_HEARTBEATS", "TEMP_UPLOAD_FILES"}


# ---------------------------------------------------------------- disk-space safeguards
def test_disk_thresholds_drive_readiness_and_metrics(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    s = get_settings()
    monkeypatch.setattr(disk, "free_mb", lambda path: s.DISK_WARN_FREE_MB + 500)
    assert client.get("/api/v1/health/ready").json()["checks"]["disk"] == "ok"
    monkeypatch.setattr(disk, "free_mb", lambda path: s.DISK_WARN_FREE_MB - 1)
    r = client.get("/api/v1/health/ready")
    assert r.status_code == 200 and r.json()["checks"]["disk"] == "degraded"
    monkeypatch.setattr(disk, "free_mb", lambda path: s.DISK_CRITICAL_FREE_MB - 1)
    r = client.get("/api/v1/health/ready")
    assert r.status_code == 503 and r.json()["checks"]["disk"] == "failed" and r.json()["status"] == "not_ready"
    monkeypatch.setattr(s, "METRICS_TOKEN", "t" * 40)
    body = client.get("/metrics", headers={"Authorization": f"Bearer {'t' * 40}"}).text
    for g in ("disk_free_mb_app", "disk_free_mb_temp", "db_last_full_backup_age_seconds", "db_last_log_backup_age_seconds"):
        assert g in body, g


def test_uploads_refused_before_the_disk_is_exhausted(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    org = dev_org(db)
    pm = staff(db, client, org, "PROJECT_MANAGER")
    farmer = create_farmer(client, pm.headers, org)
    url = f"/api/v1/farmers/{farmer['id']}/documents"
    assert upload(client, pm.headers, url, "LAND_RECORD", PDF).status_code == 201
    monkeypatch.setattr(disk, "free_mb", lambda path: get_settings().DISK_CRITICAL_FREE_MB)   # at the reserve: nothing may be written
    r = upload(client, pm.headers, url, "LAND_RECORD", PDF)
    assert r.status_code == 503 and r.json()["details"]["reason"] == "DISK_SPACE_LOW"


def test_ensure_headroom_reserves_the_critical_threshold() -> None:
    reserve = get_settings().DISK_CRITICAL_FREE_MB
    assert disk.ensure_headroom(".", 0, free=reserve + 10) == reserve + 10
    with pytest.raises(disk.DiskSpaceLow) as e:
        disk.ensure_headroom(".", 20, free=reserve + 10)
    assert "DISK_CRITICAL_FREE_MB" in str(e.value)
