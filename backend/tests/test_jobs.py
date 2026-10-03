"""Phase 12A — background job infrastructure: registry allow-list, SYSTEM actor, enqueue / publish (outbox), lifecycle, retries,
stale-lease recovery, environment isolation, operations API / RBAC, expiry sweeps over Phase 9B / 10 objects and the financial
boundary. Runs inside the rolled-back test database WITHOUT Redis (the Celery task functions are called directly; publication without
a broker is recorded on the job row). Real cross-connection concurrency and the broker integration are in test_jobs_concurrency.py."""
import ast
import dataclasses
import json
import pathlib
import uuid
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.context import RequestContext
from app.core.errors import AppError, Conflict, NotFound, ValidationFailed
from app.models import (
    AuditLog,
    BackgroundJob,
    BackgroundJobAttempt,
    CreditLedgerEntry,
    CreditReservation,
    MarketplaceListing,
    Order,
    OrderItem,
    User,
    UserRole,
    WorkflowEvent,
)
from app.models.base import utcnow
from app.models.jobs import SYSTEM_ACTOR_IDS
from app.security.permissions import P
from app.security.principal import load_principal
from app.services import auth_service
from app.services import ledger_service as ls
from app.services import marketplace_service as ms
from app.services import order_service as os_
from app.services import payment_service as ps
from app.services import payout_service as pys
from app.workers import handlers, job_service, registry
from tests.conftest import Actor, login, make_org, make_user
from tests.phase2 import staff
from tests.test_marketplace import ORD, PAY, M
from tests.test_registry import codes

J = "/api/v1/jobs"
LIVE_ACTOR, DEMO_ACTOR = SYSTEM_ACTOR_IDS["LIVE"], SYSTEM_ACTOR_IDS["DEMO"]
WORKERS = pathlib.Path(__file__).parents[1] / "app" / "workers"


def _later(monkeypatch: pytest.MonkeyPatch, delta: timedelta) -> None:
    t = utcnow() + delta
    for mod in (ls, ms, os_, ps, handlers, job_service):
        monkeypatch.setattr(mod, "utcnow", lambda t=t: t)


def _enqueue(db: Session, job_type: str = "RETENTION_PURGE", env: str = "LIVE", **kw: Any) -> BackgroundJob:
    ctx = RequestContext(request_id="test-enqueue", user_id=SYSTEM_ACTOR_IDS[env])
    job, created = job_service.enqueue(db, ctx, job_type, environment=env, trigger_type="SERVICE", created_by=SYSTEM_ACTOR_IDS[env], **kw)
    db.commit()
    assert created
    return job


def _run(db: Session, job: BackgroundJob, worker: str = "test-worker:1") -> str:
    return job_service.execute(db, job.id, worker, expected_task_name=job.task_name)


def _attempts(db: Session, job: BackgroundJob) -> list[BackgroundJobAttempt]:
    return list(db.scalars(select(BackgroundJobAttempt).where(BackgroundJobAttempt.background_job_id == job.id)
                           .order_by(BackgroundJobAttempt.attempt_number)).all())


def _actions(db: Session, job: BackgroundJob) -> list[str]:
    return [a for (a,) in db.execute(select(AuditLog.action).where(AuditLog.entity_type == "background_job", AuditLog.entity_id == str(job.id))
                                      .order_by(AuditLog.id))]


def _swap(monkeypatch: pytest.MonkeyPatch, job_type: str, handler: Callable[..., dict[str, Any]]) -> None:
    monkeypatch.setitem(registry.TASKS, job_type, dataclasses.replace(registry.TASKS[job_type], handler=handler))


@pytest.fixture(autouse=True)
def _no_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "REDIS_URL", None)          # unit tests never need Redis


# ---------------------------------------------------------------- registry allow-list and the financial boundary
def test_registry_is_an_allow_list_with_no_financial_or_approval_work() -> None:
    assert set(registry.TASKS) == {"EXPIRY_CREDIT_RESERVATIONS", "EXPIRY_MARKETPLACE_OBJECTS", "ORPHAN_FILE_SCAN", "DOCUMENT_RESCAN",
                                   "RETENTION_PURGE"}
    assert {s.queue for s in registry.TASKS.values()} == {"maintenance"} and registry.QUEUES == ("default", "maintenance")
    from app.workers.celery_app import celery_app
    celery_app.loader.import_default_modules()
    tasks = {t for t in celery_app.tasks if not t.startswith("celery.")}
    assert tasks == {s.task_name for s in registry.TASKS.values()} | set(registry.INFRA_TASKS)
    conf = celery_app.conf
    assert conf.task_serializer == "json" and conf.accept_content == ["json"] and conf.task_acks_late and conf.task_reject_on_worker_lost
    assert conf.result_backend is None and conf.task_ignore_result and conf.worker_prefetch_multiplier == 1
    assert {v["task"] for v in conf.beat_schedule.values()} == {"jobs.schedule", "jobs.recover"}
    assert all(v["schedule"] >= 60 for v in conf.beat_schedule.values())
    forbidden_words = ("revenue", "settle", "payout", "payment", "refund", "approve", "reconcil", "issu", "retire", "transfer", "verif")
    for s in registry.TASKS.values():
        assert not any(w in s.task_name.lower() or w in s.job_type.lower() for w in forbidden_words), s.task_name
        assert s.payload_keys == frozenset() and s.time_limit <= 300 < get_settings().JOB_STALE_AFTER_SECONDS
    # no worker module imports a financial, approval, registry, verification or issuance service
    banned = {"finance_service", "settlement_service", "payout_service", "payment_service", "registry_service", "credit_issuance",
              "verification_service", "calculation_service", "calculation_qa", "lab_service", "laboratory_service"}
    for path in WORKERS.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {a.name.split(".")[-1] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom | ast.Import) for a in n.names}
        mods = {(n.module or "").split(".")[-1] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        assert not (names | mods) & banned, (path.name, (names | mods) & banned)


def test_system_actor_cannot_sign_in_holds_nothing_and_is_hidden(client: TestClient, db: Session) -> None:
    for env, uid in SYSTEM_ACTOR_IDS.items():
        u = db.get(User, uid)
        assert u is not None and u.status == "SYSTEM" and u.environment == env and u.password_hash.startswith("!")
        assert db.scalar(select(func.count()).select_from(UserRole).where(UserRole.user_id == uid)) == 0
        r = client.post("/api/v1/auth/login", json={"email": u.email, "password": "!SYSTEM-ACTOR-NO-LOGIN"})
        assert r.status_code in (401, 422)                                        # the .invalid address does not even validate
        with pytest.raises(AppError) as refused:                                  # and the service refuses the SYSTEM status
            auth_service.login(db, RequestContext(ip_address=f"10.9.9.{len(env)}"), u.email, "!SYSTEM-ACTOR-NO-LOGIN")
        assert refused.value.error_code == "INVALID_CREDENTIALS"
        p = load_principal(db, u, None)
        assert not p.grants and not any(p.has(c) for c in (P.PAYOUTS_APPROVE, P.PAYOUTS_EXECUTE, P.PAYOUTS_RECONCILE, P.REVENUE_MANAGE,
                                                           P.SETTLEMENT_APPROVE, P.PAYMENTS_CONFIRM, P.CREDITS_CONFIRM, P.JOBS_MANAGE))
        # a worker principal can never reach a financial action: no permission, no visibility
        with pytest.raises((NotFound, AppError)):
            pys.action(db, RequestContext(user_id=uid), p, uuid.uuid4(), "approve", None, None)
    adm = make_user(db, roles=[("PLATFORM_ADMIN", None)])
    h = login(client, adm)
    listed = client.get("/api/v1/admin/users", headers=h, params={"search": "carbon-platform.invalid"}).json()
    assert listed["total"] == 0
    assert client.get(f"/api/v1/admin/users/{LIVE_ACTOR}", headers=h).status_code == 404
    assert client.post(f"/api/v1/admin/users/{LIVE_ACTOR}/roles", headers=h, json={"role_code": "PLATFORM_ADMIN"}).status_code in (404, 422)


# ---------------------------------------------------------------- enqueue validation, idempotency, outbox publication
def test_enqueue_validation_idempotency_and_publication_without_broker(db: Session) -> None:
    ctx = RequestContext(user_id=LIVE_ACTOR)
    with pytest.raises(ValidationFailed) as e:
        job_service.enqueue(db, ctx, "os.system", environment="LIVE", trigger_type="SERVICE", created_by=LIVE_ACTOR)
    assert e.value.error_code == "UNKNOWN_JOB_TYPE"
    with pytest.raises(ValidationFailed) as e:
        job_service.enqueue(db, ctx, "RETENTION_PURGE", environment="TEST", trigger_type="SERVICE", created_by=LIVE_ACTOR)
    assert e.value.error_code == "INVALID_ENVIRONMENT"
    for bad in ({"password": "x"}, {"order_id": "x"}, {"Bad Key": 1}, ["x"]):
        with pytest.raises(ValidationFailed) as e:
            job_service.enqueue(db, ctx, "RETENTION_PURGE", environment="LIVE", trigger_type="SERVICE", created_by=LIVE_ACTOR,
                                payload=bad)  # type: ignore[arg-type]
        assert e.value.error_code == "INVALID_PAYLOAD"
    key = f"test:{uuid.uuid4()}"
    a = _enqueue(db, idempotency_key=key)
    b, created = job_service.enqueue(db, ctx, "RETENTION_PURGE", environment="LIVE", trigger_type="SERVICE", created_by=LIVE_ACTOR,
                                     idempotency_key=key)
    assert b.id == a.id and not created                                           # idempotent enqueue
    with pytest.raises(Conflict) as c:
        job_service.enqueue(db, ctx, "ORPHAN_FILE_SCAN", environment="LIVE", trigger_type="SERVICE", created_by=LIVE_ACTOR, idempotency_key=key)
    assert c.value.error_code == "IDEMPOTENCY_KEY_REUSED"
    assert a.status == "QUEUED" and a.job_code.startswith("JOB-") and a.payload == "{}" and len(a.payload_hash) == 64
    assert _actions(db, a) == ["JOB_CREATED"]
    # no broker configured: the job stays QUEUED in SQL Server with the publication error (recoverable)
    assert job_service.publish(db, a.id) is False
    db.refresh(a)
    assert a.status == "QUEUED" and a.publish_attempts == 1 and a.last_publish_error == "BROKER_NOT_CONFIGURED" and a.published_at is None


def test_publication_failure_and_rollback_leave_no_phantom(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    from kombu.exceptions import OperationalError as BrokerError
    monkeypatch.setattr(get_settings(), "REDIS_URL", "redis://127.0.0.1:1/0")
    sent: list[str] = []

    def broken(job: BackgroundJob, spec: Any) -> None:
        raise BrokerError("connection refused")
    monkeypatch.setattr(job_service, "_send", broken)
    a = _enqueue(db)
    assert job_service.publish(db, a.id) is False
    db.refresh(a)
    assert a.status == "QUEUED" and a.last_publish_error == "BROKER_UNAVAILABLE (OperationalError)"
    monkeypatch.setattr(job_service, "_send", lambda job, spec: sent.append(job.job_code))
    out = job_service.recover(db)                                                 # broker back: the recovery tick republishes
    db.refresh(a)
    assert out["republished"] >= 1 and a.job_code in sent and a.last_publish_error is None and a.published_at is not None
    # a business transaction that rolls back leaves no job (the row is written in that transaction; publish happens after commit)
    before = db.scalar(select(func.count()).select_from(BackgroundJob))
    nested = db.begin_nested()
    job_service.enqueue(db, RequestContext(user_id=LIVE_ACTOR), "RETENTION_PURGE", environment="LIVE", trigger_type="SERVICE",
                        created_by=LIVE_ACTOR)
    nested.rollback()
    assert db.scalar(select(func.count()).select_from(BackgroundJob)) == before


# ---------------------------------------------------------------- lifecycle, duplicate delivery, retries, permanent failure
def test_lifecycle_success_and_duplicate_delivery_is_a_no_op(db: Session) -> None:
    job = _enqueue(db)
    assert _run(db, job) == "SUCCEEDED"
    db.refresh(job)
    assert job.status == "SUCCEEDED" and job.completed_at and json.loads(job.result or "{}")["purged"] == 0
    att = _attempts(db, job)
    assert len(att) == 1 and att[0].status == "SUCCEEDED" and att[0].system_actor_id == LIVE_ACTOR and att[0].duration_ms is not None
    assert _actions(db, job) == ["JOB_CREATED", "JOB_CLAIMED", "JOB_STARTED", "JOB_SUCCEEDED"]
    statuses = [t for (t,) in db.execute(select(WorkflowEvent.to_status).where(WorkflowEvent.entity_type == "background_job",
                                                                                 WorkflowEvent.entity_id == str(job.id)))]
    assert sorted(statuses) == sorted(["QUEUED", "CLAIMED", "RUNNING", "SUCCEEDED"])
    for _ in range(2):                                                            # duplicate Redis deliveries
        assert _run(db, job, "other-worker:2") == "NOT_ELIGIBLE:SUCCEEDED"
    assert len(_attempts(db, job)) == 1
    assert job_service.execute(db, job.id, "w:3", expected_task_name="maintenance.expire_credit_reservations") == "TASK_MISMATCH"
    assert job_service.execute(db, uuid.uuid4(), "w:3") == "MISSING"


def test_transient_failures_retry_with_backoff_then_succeed_or_exhaust(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def flaky(db: Session, ctx: RequestContext, job: BackgroundJob, deadline: float) -> dict[str, Any]:
        calls["n"] += 1
        if calls["n"] < 3:
            raise OperationalError("SELECT 1", {}, Exception("connection lost"))
        return {"ok": True}
    _swap(monkeypatch, "RETENTION_PURGE", flaky)
    job = _enqueue(db)
    assert _run(db, job) == "RETRY_WAITING"
    db.refresh(job)
    assert job.retry_count == 1 and job.error_code == "DATABASE_UNAVAILABLE" and job.available_at > utcnow()
    assert "SELECT" not in (job.error_message or "")                              # sanitized: no SQL text
    assert _run(db, job) == "NOT_ELIGIBLE:RETRY_WAITING"                          # not due yet: nothing runs
    assert job_service.backoff_seconds(1) == 60 and job_service.backoff_seconds(2) == 120 and job_service.backoff_seconds(10) == 3600
    _later(monkeypatch, timedelta(hours=2))
    assert job_service.recover(db)["retries_requeued"] == 1
    assert _run(db, job) == "RETRY_WAITING"
    _later(monkeypatch, timedelta(hours=4))
    job_service.recover(db)
    assert _run(db, job) == "SUCCEEDED"
    att = _attempts(db, job)
    assert [a.status for a in att] == ["RETRYABLE_ERROR", "RETRYABLE_ERROR", "SUCCEEDED"] and [a.attempt_number for a in att] == [1, 2, 3]
    # exhaustion: bounded retries, then FAILED
    _swap(monkeypatch, "RETENTION_PURGE", lambda *a: (_ for _ in ()).throw(OperationalError("x", {}, Exception("down"))))
    j2 = _enqueue(db)
    hours = 6
    for _ in range(10):
        if _run(db, j2) == "FAILED":
            break
        hours += 2
        _later(monkeypatch, timedelta(hours=hours))
        job_service.recover(db)
    db.refresh(j2)
    assert j2.status == "FAILED" and j2.retry_count == j2.max_retries == get_settings().JOB_MAX_RETRIES and len(_attempts(db, j2)) == 4
    assert "JOB_FAILED" in _actions(db, j2)


@pytest.mark.parametrize("exc, code", [(Conflict("refused", error_code="SOMETHING_FINAL"), "SOMETHING_FINAL"),
                                       (ValueError("bad data"), "UNEXPECTED_ERROR")])
def test_non_retryable_errors_fail_at_once(db: Session, monkeypatch: pytest.MonkeyPatch, exc: Exception, code: str) -> None:
    def boom(*_: Any) -> dict[str, Any]:
        raise exc
    _swap(monkeypatch, "RETENTION_PURGE", boom)
    job = _enqueue(db)
    assert _run(db, job) == "FAILED"
    db.refresh(job)
    assert job.status == "FAILED" and job.retry_count == 0 and job.error_code == code and _attempts(db, job)[0].status == "FAILED"
    assert "bad data" not in (job.error_message or "")


# ---------------------------------------------------------------- stale-lease recovery (worker crash) and environment isolation
def test_stale_claim_and_stale_run_are_recovered_without_double_execution(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    job = _enqueue(db)
    assert job_service._claim(db, job.id, "dead-worker:1")                       # claimed, then the worker died (or rolled back)
    assert _run(db, job) == "NOT_ELIGIBLE:CLAIMED"                               # a live lease is never stolen
    _later(monkeypatch, timedelta(seconds=get_settings().JOB_STALE_AFTER_SECONDS + 60))
    assert job_service.recover(db)["stale_claims_requeued"] == 1
    assert _run(db, job) == "SUCCEEDED" and len(_attempts(db, job)) == 1
    assert "JOB_REQUEUED" in _actions(db, job)
    j2 = _enqueue(db)
    assert job_service._claim(db, j2.id, "dead-worker:2") and job_service._start(db, j2.id, "dead-worker:2") is not None
    _later(monkeypatch, timedelta(seconds=2 * get_settings().JOB_STALE_AFTER_SECONDS + 120))
    out = job_service.recover(db)
    assert out["stale_runs_recovered"] == 1
    db.refresh(j2)
    assert j2.status in ("RETRY_WAITING", "QUEUED") and j2.error_code == "WORKER_LOST"
    job_service.recover(db)
    assert _run(db, j2) == "SUCCEEDED"
    assert [a.status for a in _attempts(db, j2)] == ["ABANDONED", "SUCCEEDED"]
    assert job_service._succeed(db, j2.id, _attempts(db, j2)[0].id, "dead-worker:2", 0.0, {}) == "LEASE_LOST"   # the dead worker returns


def test_environment_mismatch_is_rejected(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "JOB_ENVIRONMENTS", ["LIVE"])
    job = _enqueue(db, env="DEMO")
    assert _run(db, job) == "FAILED"
    db.refresh(job)
    assert job.error_code == "ENVIRONMENT_MISMATCH" and _attempts(db, job)[0].system_actor_id == DEMO_ACTOR


# ---------------------------------------------------------------- operations API: RBAC, environment isolation, no arbitrary task
def test_jobs_api_rbac_trigger_cancel_retry_and_isolation(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    adm = Actor(u := make_user(db, roles=[("PLATFORM_ADMIN", None)]), login(client, u))
    t = client.post(f"{J}/trigger", headers={**adm.headers, "Idempotency-Key": "trig-1"}, json={"job_type": "EXPIRY_MARKETPLACE_OBJECTS"})
    assert t.status_code == 201, t.text
    job = t.json()
    assert job["status"] == "QUEUED" and job["trigger_type"] == "MANUAL" and job["environment"] == "LIVE" and job["can_cancel"]
    assert job["last_publish_error"] == "BROKER_NOT_CONFIGURED"
    again = client.post(f"{J}/trigger", headers={**adm.headers, "Idempotency-Key": "trig-1"}, json={"job_type": "EXPIRY_MARKETPLACE_OBJECTS"})
    assert again.json()["id"] == job["id"]                                         # idempotent trigger
    for bad in ({"job_type": "os.system"}, {"job_type": "maintenance.expire_credit_reservations"}):
        assert codes(client.post(f"{J}/trigger", headers=adm.headers, json=bad)) == "TASK_NOT_TRIGGERABLE"
    assert client.post(f"{J}/trigger", headers=adm.headers, json={"job_type": "RETENTION_PURGE", "task": "x"}).status_code == 422
    assert job["id"] in {j["id"] for j in client.get(J, headers=adm.headers).json()}
    assert client.get(f"{J}/{job['id']}/attempts", headers=adm.headers).json() == []
    reg = client.get(f"{J}/registry", headers=adm.headers).json()
    assert {r["job_type"] for r in reg} == set(registry.TASKS) and all(r["queue"] == "maintenance" for r in reg)
    st = client.get(f"{J}/status", headers=adm.headers).json()
    assert st["broker"] == "NOT_CONFIGURED" and st["worker_alive"] is False and st["counts"].get("QUEUED", 0) >= 1
    assert client.post(f"{J}/{job['id']}/retry", headers=adm.headers, json={"reason": "TEST retry"}).json()["error_code"] == "JOB_NOT_RETRYABLE"
    c = client.post(f"{J}/{job['id']}/cancel", headers=adm.headers, json={"reason": "TEST: not needed"})
    assert c.status_code == 200 and c.json()["status"] == "CANCELLED" and c.json()["reason"] == "TEST: not needed"
    assert client.post(f"{J}/{job['id']}/cancel", headers=adm.headers, json={"reason": "TEST again"}).json()["status"] == "CANCELLED"
    assert "JOB_CANCELLED" in _actions(db, db.get(BackgroundJob, uuid.UUID(job["id"])))  # type: ignore[arg-type]
    # a FAILED job can be requeued (audited), a SUCCEEDED / CANCELLED one never
    _swap(monkeypatch, "RETENTION_PURGE", lambda *a: (_ for _ in ()).throw(Conflict("x", error_code="TEST_FAIL")))
    failed = _enqueue(db)
    _run(db, failed)
    r = client.post(f"{J}/{failed.id}/retry", headers=adm.headers, json={"reason": "TEST: fixed the cause"})
    assert r.status_code == 200 and r.json()["status"] == "QUEUED", r.text
    assert _actions(db, failed)[-1] == "JOB_REQUEUED"
    # only the Platform Administrator (jobs.read / jobs.manage); no organization role has access
    org = make_org(db)
    for role in ("PROJECT_MANAGER", "FINANCE_MANAGER", "QA_OFFICER", "CREDIT_MANAGER"):
        a = staff(db, client, org, role)
        for url in (J, f"{J}/status", f"{J}/registry", f"{J}/{job['id']}"):
            assert client.get(url, headers=a.headers).status_code == 403, (role, url)
        assert client.post(f"{J}/{job['id']}/cancel", headers=a.headers, json={"reason": "TEST x"}).status_code == 403
        assert client.post(f"{J}/trigger", headers=a.headers, json={"job_type": "RETENTION_PURGE"}).status_code == 403
    farmer = make_user(db, roles=[("FARMER", make_org(db, org_type="FARMER_GROUP"))])
    assert client.get(J, headers=login(client, farmer)).status_code == 403
    # DEMO platform admin sees only DEMO jobs; a LIVE job is not found
    demo = make_user(db, roles=[("PLATFORM_ADMIN", None)], environment="DEMO")
    dh = login(client, demo)
    assert client.get(f"{J}/{job['id']}", headers=dh).status_code == 404
    assert all(j["environment"] == "DEMO" for j in client.get(J, headers=dh).json())
    dj = client.post(f"{J}/trigger", headers=dh, json={"job_type": "EXPIRY_CREDIT_RESERVATIONS"}).json()
    assert dj["environment"] == "DEMO" and client.get(f"{J}/{dj['id']}", headers=adm.headers).status_code == 404
    assert client.get(f"{J}/status", headers=dh).json()["note"].startswith("DEMO")


# ---------------------------------------------------------------- expiry sweeps over Phase 9B reservations
def test_reservation_sweep_expires_only_due_active_reservations_once(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    m = M(client, db, 83.41, 28.41, "9810 2000 3000")
    lg = m.lg
    due = [lg.reserve(5).json()["id"] for _ in range(3)]
    later = lg.reserve(5, expires_at=(utcnow() + timedelta(hours=6)).isoformat() + "Z").json()["id"]
    released = lg.reserve(5).json()["id"]
    assert lg.post(f"/reservations/{released}/release", {"reason": "TEST release"}).status_code == 200
    demo_job = _enqueue(db, "EXPIRY_CREDIT_RESERVATIONS", env="DEMO")
    _later(monkeypatch, timedelta(hours=2))
    assert _run(db, demo_job) == "SUCCEEDED"                                       # DEMO job never touches LIVE rows
    assert json.loads(db.get(BackgroundJob, demo_job.id).result or "{}")["expired"] == 0  # type: ignore[union-attr]
    job = _enqueue(db, "EXPIRY_CREDIT_RESERVATIONS")
    assert _run(db, job) == "SUCCEEDED"
    res = json.loads(db.get(BackgroundJob, job.id).result or "{}")  # type: ignore[union-attr]
    assert res["expired"] == 3 and res["complete"] is True and res["item_errors"] == 0
    rows = {str(r.id): r.status for r in db.scalars(select(CreditReservation).where(CreditReservation.id.in_(
        [uuid.UUID(x) for x in [*due, later, released]])))}
    assert [rows[x] for x in due] == ["EXPIRED"] * 3 and rows[later] == "ACTIVE" and rows[released] == "RELEASED"
    entries = db.scalars(select(CreditLedgerEntry).where(CreditLedgerEntry.entry_type == "RESERVATION_EXPIRE",
                                                         CreditLedgerEntry.batch_id == uuid.UUID(lg.batch["id"]))).all()
    assert len(entries) == 3 and {e.actor_id for e in entries} == {LIVE_ACTOR}       # attributed to the SYSTEM actor
    again = _enqueue(db, "EXPIRY_CREDIT_RESERVATIONS")
    assert _run(db, again) == "SUCCEEDED" and json.loads(db.get(BackgroundJob, again.id).result or "{}")["expired"] == 0  # type: ignore[union-attr]
    assert db.scalar(select(func.count()).select_from(CreditLedgerEntry).where(CreditLedgerEntry.entry_type == "RESERVATION_EXPIRE",
                                                                              CreditLedgerEntry.batch_id == uuid.UUID(lg.batch["id"]))) == 3
    assert int(lg.balance(m.seller.id)["reserved"]) == 5                          # only the not-yet-due reservation still holds credits
    # lazy expiry is unchanged: a read still expires due reservations without any worker
    _later(monkeypatch, timedelta(hours=8))
    ls.expire_due(db, RequestContext(user_id=m.cm.user.id), batch_ids=[uuid.UUID(lg.batch["id"])])
    assert db.get(CreditReservation, uuid.UUID(later)).status == "EXPIRED"  # type: ignore[union-attr]


# ---------------------------------------------------------------- expiry sweeps over Phase 10 orders / listings; pending payment
def test_marketplace_sweep_and_pending_payment_behaviour(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    m = M(client, db, 83.42, 28.42, "9820 2000 3000")
    m.verify_buyer()
    soon = (utcnow() + timedelta(hours=10)).isoformat() + "Z"
    lst = m.listing(300, "10.00", rng=m.range600, valid_until=soon)
    unpaid = m.order([(lst["id"], 10)]).json()
    paid = m.order([(lst["id"], 20)]).json()
    assert m.pay(paid).json()["status"] == "PENDING_CONFIRMATION"                 # buyer reported payment, not yet confirmed
    _later(monkeypatch, timedelta(hours=25))                                       # past the 24 h payment window and valid_until
    job = _enqueue(db, "EXPIRY_MARKETPLACE_OBJECTS")
    assert _run(db, job) == "SUCCEEDED"
    res = json.loads(db.get(BackgroundJob, job.id).result or "{}")  # type: ignore[union-attr]
    assert res["orders_expired"] == 1 and res["listings_expired"] == 1
    assert db.get(Order, uuid.UUID(unpaid["id"])).status == "EXPIRED"  # type: ignore[union-attr]
    assert db.get(MarketplaceListing, uuid.UUID(lst["id"])).status == "EXPIRED"  # type: ignore[union-attr]
    held = db.get(Order, uuid.UUID(paid["id"]))
    assert held is not None and held.status == "PLACED"                            # a reported payment holds the order …
    rjob = _enqueue(db, "EXPIRY_CREDIT_RESERVATIONS")
    assert _run(db, rjob) == "SUCCEEDED"
    item = db.scalars(select(OrderItem).where(OrderItem.order_id == held.id)).one()
    assert db.get(CreditReservation, item.reservation_id).status == "EXPIRED"  # type: ignore[arg-type,union-attr]   # … but not its reservation
    # the late confirmation is routed to the existing human workflow: ATTENTION_REQUIRED, no transfer, no recreated reservation
    pay_id = m.get(f"{ORD}/{paid['id']}", m.fin).json()["payments"][0]["id"]
    c = m.post(f"{PAY}/{pay_id}/confirm", {}, m.fin)
    assert c.status_code == 200 and c.json()["status"] == "CONFIRMED", c.text
    od = m.get(f"{ORD}/{paid['id']}", m.fin).json()
    assert od["status"] == "ATTENTION_REQUIRED" and od["items"][0]["transfer_id"] is None
    again = _enqueue(db, "EXPIRY_MARKETPLACE_OBJECTS")
    assert _run(db, again) == "SUCCEEDED" and json.loads(db.get(BackgroundJob, again.id).result or "{}")["orders_expired"] == 0  # type: ignore[union-attr]


def test_orphan_cleanup_deletes_only_aged_unreferenced_objects(db: Session) -> None:
    """Phase 12B D10 changed this job from detection-only to safe deletion (full coverage in test_storage_av.py)."""
    import os
    import time as _time

    from app.integrations.storage import get_storage
    st: Any = get_storage()
    old_key, new_key = f"live/2000/01/{uuid.uuid4().hex}", f"live/2000/01/{uuid.uuid4().hex}"
    st.put(old_key, b"orphan", "application/pdf")
    st.put(new_key, b"in flight", "application/pdf")                               # e.g. an upload whose transaction is not committed
    aged = _time.time() - (get_settings().JOB_ORPHAN_GRACE_HOURS + 2) * 3600
    os.utime(st._path(old_key), (aged, aged))
    job = _enqueue(db, "ORPHAN_FILE_SCAN")
    assert _run(db, job) == "SUCCEEDED"
    res = json.loads(db.get(BackgroundJob, job.id).result or "{}")  # type: ignore[union-attr]
    assert res["deletion"] == "ENABLED" and res["complete"] and res["deleted"] >= 1
    assert old_key in res["sample_candidates"] and new_key not in res["sample_candidates"] and res["recent_unreferenced"] >= 1
    assert not st.exists(old_key) and st.exists(new_key)                              # aged orphan deleted; in-flight upload kept
    assert db.scalars(select(AuditLog).where(AuditLog.action == "STORAGE_ORPHAN_DELETED", AuditLog.entity_id == old_key)).one()
    demo = _enqueue(db, "ORPHAN_FILE_SCAN", env="DEMO")                              # the DEMO scan only looks under demo/
    assert _run(db, demo) == "SUCCEEDED"
    assert old_key not in json.loads(db.get(BackgroundJob, demo.id).result or "{}")["sample_candidates"]  # type: ignore[union-attr]


def test_retention_purge_without_policy_purges_nothing(db: Session) -> None:
    before = db.scalar(select(func.count()).select_from(AuditLog))
    job = _enqueue(db)
    assert _run(db, job) == "SUCCEEDED" and handlers.RETENTION_POLICIES == ()
    assert json.loads(db.get(BackgroundJob, job.id).result or "{}") == {  # type: ignore[union-attr]
        "message": "No retention policy is configured; nothing was purged.", "policies_configured": 0, "purged": 0}
    assert db.scalar(select(func.count()).select_from(AuditLog)) > before             # only new job audit rows; nothing deleted


def test_schedule_creates_one_job_per_environment_and_slot(db: Session) -> None:
    now = utcnow()
    first = job_service.schedule(db, "EXPIRY_CREDIT_RESERVATIONS", now)
    assert len(first) == 2
    assert job_service.schedule(db, "EXPIRY_CREDIT_RESERVATIONS", now) == []          # duplicate beat / redelivery: same slot, no job
    jobs = [db.get(BackgroundJob, j) for j in first]
    assert {j.environment for j in jobs if j} == {"LIVE", "DEMO"} and all(j and j.trigger_type == "SCHEDULE" for j in jobs)
    assert {j.created_by for j in jobs if j} == {LIVE_ACTOR, DEMO_ACTOR}
    with pytest.raises(KeyError):
        job_service.schedule(db, "NOT_A_TASK", now)
