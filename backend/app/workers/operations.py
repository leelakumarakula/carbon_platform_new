"""Read side of the job system for the operations API: listing, mapping and status (broker reachability, worker heartbeats, counts).
Broker reachability is reported separately from worker liveness — a reachable Redis never means a worker is running."""
import json
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import BackgroundJob, BackgroundJobAttempt, BackgroundWorkerHeartbeat, User
from app.models.base import utcnow
from app.schemas.jobs import JobAttemptOut, JobOut, JobsStatusOut, TaskSpecOut, WorkerOut
from app.security.permissions import P
from app.security.principal import Principal
from app.workers import job_service, registry

DEMO_NOTE = ("DEMO — background jobs here act only on DEMO records. DEMO has no registry-issued credits, so there are no reservations, "
             "orders or listings to expire; nothing financial is ever processed by a worker.")


def _name(db: Session, user_id: uuid.UUID | None) -> str | None:
    u = db.get(User, user_id) if user_id else None
    return u.full_name if u else None


def jobs(db: Session, principal: Principal, status: str | None, job_type: str | None, limit: int) -> list[BackgroundJob]:
    stmt = select(BackgroundJob).where(BackgroundJob.environment == principal.user.environment)
    if status:
        stmt = stmt.where(BackgroundJob.status == status)
    if job_type:
        stmt = stmt.where(BackgroundJob.job_type == job_type)
    return list(db.scalars(stmt.order_by(BackgroundJob.created_at.desc(), BackgroundJob.job_code.desc()).limit(limit)).all())


def job_out(db: Session, principal: Principal, j: BackgroundJob) -> JobOut:
    manage = principal.has(P.JOBS_MANAGE)
    spec = job_service.spec_of(j)
    return JobOut(
        id=j.id, job_code=j.job_code, job_type=j.job_type, task_name=j.task_name, queue_name=j.queue_name, status=j.status,
        environment=j.environment, trigger_type=j.trigger_type, organization_id=j.organization_id, entity_type=j.entity_type,
        entity_id=j.entity_id, scheduled_at=j.scheduled_at, available_at=j.available_at, claimed_at=j.claimed_at, claimed_by=j.claimed_by,
        started_at=j.started_at, completed_at=j.completed_at, failed_at=j.failed_at, cancelled_at=j.cancelled_at,
        retry_count=j.retry_count, max_retries=j.max_retries, error_code=j.error_code, error_message=j.error_message,
        result=json.loads(j.result) if j.result else None, published_at=j.published_at, publish_attempts=j.publish_attempts,
        last_publish_error=j.last_publish_error, reason=j.reason, created_by_name=_name(db, j.created_by), created_at=j.created_at,
        can_cancel=manage and j.status == "QUEUED",
        can_retry=manage and j.status == "FAILED" and spec is not None and spec.manual_retry_safe)


def attempts(db: Session, job_id: uuid.UUID) -> list[JobAttemptOut]:
    rows = db.scalars(select(BackgroundJobAttempt).where(BackgroundJobAttempt.background_job_id == job_id)
                      .order_by(BackgroundJobAttempt.attempt_number)).all()
    return [JobAttemptOut(id=a.id, attempt_number=a.attempt_number, worker_identity=a.worker_identity, task_name=a.task_name, status=a.status,
                          started_at=a.started_at, finished_at=a.finished_at, duration_ms=a.duration_ms, error_code=a.error_code,
                          error_message=a.error_message, system_actor_name=_name(db, a.system_actor_id)) for a in rows]


def task_specs() -> list[TaskSpecOut]:
    s = get_settings()
    return [TaskSpecOut(job_type=t.job_type, task_name=t.task_name, queue=t.queue, description=t.description,
                        environments=sorted(t.environments),
                        scheduled_every_seconds=int(getattr(s, t.interval_setting)) if t.interval_setting else None,
                        manually_triggerable=t.manually_triggerable, max_retries=s.JOB_MAX_RETRIES if t.max_retries is None else t.max_retries,
                        soft_time_limit=t.soft_time_limit, time_limit=t.time_limit, idempotency=t.idempotency) for t in registry.TASKS.values()]


def broker_status() -> str:
    url = get_settings().REDIS_URL
    if not url:
        return "NOT_CONFIGURED"
    try:
        import redis
        client: Any = redis.Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
        client.ping()
        client.close()
        return "REACHABLE"
    except Exception:
        return "UNREACHABLE"


def status(db: Session, principal: Principal) -> JobsStatusOut:
    env = principal.user.environment
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        database = "unavailable"
    window = timedelta(seconds=3 * get_settings().JOB_HEARTBEAT_SECONDS)
    now = utcnow()
    workers = [WorkerOut(worker_identity=w.worker_identity, hostname=w.hostname, queues=w.queues, started_at=w.started_at,
                         last_heartbeat_at=w.last_heartbeat_at, stopped_at=w.stopped_at,
                         alive=w.stopped_at is None and now - w.last_heartbeat_at <= window)
               for w in db.scalars(select(BackgroundWorkerHeartbeat).order_by(BackgroundWorkerHeartbeat.last_heartbeat_at.desc()).limit(20))]
    counts = {s: int(n) for s, n in db.execute(select(BackgroundJob.status, func.count()).where(BackgroundJob.environment == env)
                                               .group_by(BackgroundJob.status)).all()}
    last = db.scalar(select(func.max(BackgroundJob.created_at)).where(BackgroundJob.environment == env,
                                                                      BackgroundJob.trigger_type == "SCHEDULE"))
    alive = any(w.alive for w in workers)
    note = DEMO_NOTE if env == "DEMO" else ("No worker heartbeat: queued jobs wait in SQL Server; lazy expiry keeps every workflow correct."
                                            if not alive else "Workers are running.")
    return JobsStatusOut(environment=env, database=database, broker=broker_status(), workers=workers, worker_alive=alive,
                         counts=counts, last_scheduled_at=last, note=note)
