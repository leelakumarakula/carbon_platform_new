"""Phase 12A — background job lifecycle. SQL Server is the system of record; Redis only carries the job id to a worker.

Enqueue (outbox): `enqueue` adds the job row (+ JOB_CREATED audit) to the CALLER's transaction; only after that transaction commits
does `publish` hand the job id to the broker. A rolled-back business transaction therefore leaves no job, and a committed job whose
publication failed stays QUEUED with `last_publish_error` until the recovery tick (or `manage.py jobs-recover`) republishes it.
SQL Server and Redis are NOT atomic together — this pattern plus recovery is what makes the pair reliable.

Execution: delivery is at-least-once. `execute` claims the row under UPDLOCK / HOLDLOCK / ROWLOCK (QUEUED → CLAIMED), opens an
append-only attempt (CLAIMED → RUNNING), validates environment / registry / system actor, runs the allow-listed handler (which calls
existing domain services with their own locks and re-checks) and records SUCCEEDED / RETRY_WAITING / FAILED. A duplicate delivery of
a claimed, running, succeeded, failed or cancelled job is a logged no-op.

Retries: only transient infrastructure failures (database connectivity, deadlock after the service's own retries, broker / network
errors, time budget) are retried, with deterministic exponential backoff, bounded by `max_retries`. Business refusals, validation,
permission, configuration and environment errors fail at once. A stale lease (worker lost) is recovered: a CLAIMED job returns to
QUEUED; a RUNNING job's attempt becomes ABANDONED and the job is retried (or FAILED when retries are exhausted).
"""
import hashlib
import json
import re
import time
import uuid
from datetime import datetime, timedelta
from typing import Any

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError, IntegrityError, InterfaceError, OperationalError
from sqlalchemy.orm import Session

from app.audit.service import record
from app.core.config import get_settings
from app.core.context import RequestContext
from app.core.errors import AppError, Conflict, NotFound, ValidationFailed
from app.models import BackgroundJob, BackgroundJobAttempt, User
from app.models.base import Environment, utcnow
from app.models.jobs import SYSTEM_ACTOR_IDS
from app.repositories.sequences import next_code
from app.security.principal import Principal
from app.services import ledger_service as ls
from app.services import marketplace_service as ms
from app.services.workflows import BACKGROUND_JOB_MACHINE
from app.workers import joblog, registry
from app.workers.registry import TaskSpec

ENTITY = "background_job"
FINAL = ("SUCCEEDED", "CANCELLED")
MAX_PAYLOAD_BYTES = 2000
FORBIDDEN_PAYLOAD_WORDS = ("password", "token", "secret", "credential", "account", "bank", "iban", "kyc", "otp", "signed_url", "file")
_KEY = re.compile(r"^[a-z][a-z0-9_]{0,39}$")


class JobConfigurationError(AppError):
    status_code, error_code, message = 409, "JOB_CONFIGURATION_ERROR", "The job cannot run with the current configuration."


class EnvironmentMismatch(AppError):
    status_code, error_code, message = 409, "ENVIRONMENT_MISMATCH", "The job's environment does not match."


# ---------------------------------------------------------------- helpers
def spec_of(job: BackgroundJob) -> TaskSpec | None:
    s = registry.TASKS.get(job.job_type)
    return s if s is not None and s.task_name == job.task_name else None


def system_actor_id(environment: str) -> uuid.UUID:
    return SYSTEM_ACTOR_IDS[environment]


def system_ctx(environment: str, request_id: str) -> RequestContext:
    return RequestContext(request_id=request_id, user_id=SYSTEM_ACTOR_IDS.get(environment))


def canonical_payload(payload: dict[str, Any] | None, spec: TaskSpec) -> tuple[str, str]:
    """Identifiers only: small, flat, allow-listed keys, scalar values; never secrets, PII, documents or files."""
    payload = payload or {}
    if not isinstance(payload, dict):
        raise ValidationFailed("A job payload is an object of identifiers.", error_code="INVALID_PAYLOAD")
    for k, v in payload.items():
        if not isinstance(k, str) or not _KEY.match(k) or any(w in k for w in FORBIDDEN_PAYLOAD_WORDS) or k not in spec.payload_keys:
            raise ValidationFailed(f"Payload key {k!r} is not accepted by {spec.job_type}.", error_code="INVALID_PAYLOAD")
        if not (v is None or isinstance(v, (bool, int)) or (isinstance(v, str) and len(v) <= 200)):
            raise ValidationFailed("Payload values are short identifiers.", error_code="INVALID_PAYLOAD")
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    if len(text.encode("utf-8")) > MAX_PAYLOAD_BYTES:
        raise ValidationFailed("The job payload is too large; pass identifiers only.", error_code="INVALID_PAYLOAD")
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


def _move(db: Session, ctx: RequestContext, job: BackgroundJob, to: str, action: str, reason: str | None = None,
          extra: dict[str, Any] | None = None) -> None:
    frm = job.status
    BACKGROUND_JOB_MACHINE.assert_transition(frm, to)
    job.status = to
    if to == "QUEUED":
        job.published_at = None                                     # republished on the next recovery tick, not after the stale window
    ls.workflow(db, ctx, ENTITY, job.id, frm, to, reason)
    record(db, ctx, action, ENTITY, job.id, {"status": frm}, {"job_code": job.job_code, "job_type": job.job_type, "status": to,
                                                                 "environment": job.environment, **(extra or {})}, reason,
           organization_id=job.organization_id)


def _sanitize(e: BaseException) -> str:
    if isinstance(e, AppError):
        return e.message[:500]
    if isinstance(e, DBAPIError):                                   # never the SQL text or its parameters
        return f"database error ({type(e.orig).__name__})"
    return type(e).__name__


def classify(e: BaseException) -> tuple[bool, str, str]:
    """(retryable, error_code, sanitized message)."""
    if isinstance(e, AppError):
        return False, e.error_code, _sanitize(e)
    if isinstance(e, SoftTimeLimitExceeded):
        return True, "TIME_LIMIT", "The task reached its time limit; committed progress is kept."
    if isinstance(e, (OperationalError, InterfaceError)) or (isinstance(e, DBAPIError) and (e.connection_invalidated or ls._is_deadlock(e))):
        return True, "DATABASE_UNAVAILABLE", _sanitize(e)
    if isinstance(e, IntegrityError):
        return False, "INTEGRITY_ERROR", _sanitize(e)
    try:
        from kombu.exceptions import OperationalError as BrokerError
        from redis.exceptions import ConnectionError as RedisConnectionError
        from redis.exceptions import TimeoutError as RedisTimeout
        transient: tuple[type[BaseException], ...] = (BrokerError, RedisConnectionError, RedisTimeout, ConnectionError, TimeoutError)
    except ImportError:                                             # pragma: no cover
        transient = (ConnectionError, TimeoutError)
    if isinstance(e, transient):
        return True, "TRANSIENT_NETWORK", type(e).__name__
    return False, "UNEXPECTED_ERROR", type(e).__name__


def backoff_seconds(retry_number: int) -> int:
    return int(min(get_settings().JOB_RETRY_BACKOFF_SECONDS * (2 ** max(retry_number - 1, 0)), 3600))


# ---------------------------------------------------------------- enqueue (in the caller's transaction) and publish (after commit)
def enqueue(db: Session, ctx: RequestContext, job_type: str, *, environment: str, trigger_type: str, created_by: uuid.UUID,
            organization_id: uuid.UUID | None = None, entity_type: str | None = None, entity_id: Any = None,
            payload: dict[str, Any] | None = None, idempotency_key: str | None = None,
            scheduled_at: datetime | None = None) -> tuple[BackgroundJob, bool]:
    spec = registry.TASKS.get(job_type)
    if spec is None:
        raise ValidationFailed(f"Unknown job type {job_type!r}.", error_code="UNKNOWN_JOB_TYPE")
    if environment not in {e.value for e in Environment} or environment not in spec.environments:
        raise ValidationFailed(f"{job_type} does not run in environment {environment!r}.", error_code="INVALID_ENVIRONMENT")
    text, digest = canonical_payload(payload, spec)
    if idempotency_key:
        prior = db.scalars(select(BackgroundJob).where(BackgroundJob.idempotency_key == idempotency_key)).first()
        if prior is not None:
            if (prior.job_type, prior.environment, prior.payload_hash) != (job_type, environment, digest):
                raise Conflict("This idempotency key was already used for a different job.", error_code="IDEMPOTENCY_KEY_REUSED")
            return prior, False
    now = utcnow()
    job = BackgroundJob(job_code=next_code(db, "job", now.year), job_type=job_type, task_name=spec.task_name, queue_name=spec.queue,
                        status="QUEUED", environment=environment, trigger_type=trigger_type, organization_id=organization_id,
                        entity_type=entity_type, entity_id=str(entity_id) if entity_id is not None else None,
                        idempotency_key=idempotency_key, payload=text, payload_hash=digest, scheduled_at=scheduled_at, available_at=now,
                        max_retries=get_settings().JOB_MAX_RETRIES if spec.max_retries is None else spec.max_retries,
                        created_by=created_by)
    try:
        with db.begin_nested():
            db.add(job)
            db.flush()
    except IntegrityError:                                          # a concurrent enqueue with the same idempotency key won
        prior = db.scalars(select(BackgroundJob).where(BackgroundJob.idempotency_key == idempotency_key)).first()
        if prior is None:
            raise
        return prior, False
    ls.workflow(db, ctx, ENTITY, job.id, None, "QUEUED", None)
    record(db, ctx, "JOB_CREATED", ENTITY, job.id, None, {"job_code": job.job_code, "job_type": job_type, "task_name": spec.task_name,
                                                           "queue": spec.queue, "environment": environment, "trigger": trigger_type},
           organization_id=organization_id)
    joblog.event("job_created", job_id=job.id, job_code=job.job_code, task_name=spec.task_name, queue=spec.queue, environment=environment,
                 entity_type=entity_type, entity_id=job.entity_id, status="QUEUED", request_id=ctx.request_id)
    return job, True


def _send(job: BackgroundJob, spec: TaskSpec) -> None:
    from app.workers.celery_app import celery_app
    celery_app.send_task(spec.task_name, args=[str(job.id)], queue=spec.queue, task_id=f"{job.job_code}-p{job.publish_attempts + 1}",
                         soft_time_limit=spec.soft_time_limit, time_limit=spec.time_limit, retry=False)


def publish(db: Session, job_id: uuid.UUID) -> bool:
    """Hand a committed QUEUED job to the broker (never inside the business transaction). Never raises: a failure is recorded on the
    row and the job stays QUEUED for the recovery tick. Duplicate publication is harmless (the SQL claim decides)."""
    job = db.get(BackgroundJob, job_id, populate_existing=True)
    if job is None or job.status != "QUEUED":
        return False
    spec = spec_of(job)
    error: str | None = None
    if spec is None:
        error = "UNKNOWN_TASK"
    elif not get_settings().REDIS_URL:
        error = "BROKER_NOT_CONFIGURED"
    else:
        try:
            _send(job, spec)
        except Exception as e:                                      # broker down / unreachable: SQL keeps the job
            error = f"BROKER_UNAVAILABLE ({type(e).__name__})"
    now = utcnow()
    values: dict[str, Any] = {"publish_attempts": BackgroundJob.publish_attempts + 1, "last_publish_error": error, "updated_at": now}
    if error is None:
        values["published_at"] = now
    db.execute(update(BackgroundJob).where(BackgroundJob.id == job.id, BackgroundJob.status == "QUEUED").values(**values))
    db.commit()
    joblog.event("job_published" if error is None else "job_publish_failed", job_id=job.id, job_code=job.job_code,
                 task_name=job.task_name, queue=job.queue_name, environment=job.environment, published=error is None, error_code=error)
    return error is None


# ---------------------------------------------------------------- execution (worker side)
def _claim(db: Session, job_id: uuid.UUID, worker: str) -> bool:
    x = ms.lock(db, BackgroundJob, job_id)
    now = utcnow()
    if x is None or x.status != "QUEUED" or x.available_at > now:
        db.rollback()
        return False
    ctx = system_ctx(x.environment, f"job:{x.job_code}")
    _move(db, ctx, x, "CLAIMED", "JOB_CLAIMED", extra={"worker": worker})
    x.claimed_at, x.claimed_by = now, worker
    x.lease_expires_at = now + timedelta(seconds=get_settings().JOB_STALE_AFTER_SECONDS)
    db.commit()
    return True


def _start(db: Session, job_id: uuid.UUID, worker: str) -> BackgroundJobAttempt | None:
    x = ms.lock(db, BackgroundJob, job_id)
    if x is None or x.status != "CLAIMED" or x.claimed_by != worker:
        db.rollback()
        return None
    n = int(db.scalar(select(func.coalesce(func.max(BackgroundJobAttempt.attempt_number), 0))
                      .where(BackgroundJobAttempt.background_job_id == x.id)) or 0) + 1
    now = utcnow()
    a = BackgroundJobAttempt(background_job_id=x.id, attempt_number=n, worker_identity=worker, task_name=x.task_name,
                             system_actor_id=SYSTEM_ACTOR_IDS.get(x.environment), status="RUNNING", started_at=now)
    db.add(a)
    ctx = system_ctx(x.environment, f"job:{x.job_code}:{n}")
    _move(db, ctx, x, "RUNNING", "JOB_STARTED", extra={"attempt_number": n, "worker": worker})
    x.started_at, x.lease_expires_at = now, now + timedelta(seconds=get_settings().JOB_STALE_AFTER_SECONDS)
    db.commit()
    return a


def _validate_runtime(db: Session, job: BackgroundJob, spec: TaskSpec | None) -> uuid.UUID:
    if spec is None:
        raise JobConfigurationError(f"Task {job.task_name!r} is not in the registry.", error_code="UNKNOWN_TASK")
    if job.environment not in spec.environments:
        raise EnvironmentMismatch(f"{job.job_type} does not run in {job.environment}.")
    if job.environment not in get_settings().JOB_ENVIRONMENTS:
        raise EnvironmentMismatch(f"Environment {job.environment} is not enabled for background jobs on this deployment.")
    actor = db.get(User, SYSTEM_ACTOR_IDS[job.environment])
    if actor is None or actor.status != "SYSTEM" or actor.environment != job.environment:
        raise JobConfigurationError(f"The {job.environment} SYSTEM actor is missing (run the migrations).", error_code="SYSTEM_ACTOR_MISSING")
    return actor.id


def _complete_attempt(db: Session, attempt_id: uuid.UUID, status: str, started: float, code: str | None = None,
                      message: str | None = None) -> None:
    db.execute(update(BackgroundJobAttempt).where(BackgroundJobAttempt.id == attempt_id, BackgroundJobAttempt.status == "RUNNING")
               .values(status=status, finished_at=utcnow(), duration_ms=int((time.monotonic() - started) * 1000), error_code=code,
                       error_message=message))


def execute(db: Session, job_id: uuid.UUID, worker: str, expected_task_name: str | None = None) -> str:
    """Run one delivered job id. Returns the outcome (for logs / tests); never raises for an ineligible or duplicate delivery."""
    job = db.get(BackgroundJob, job_id, populate_existing=True)
    db.commit()
    if job is None:
        joblog.event("job_delivery_ignored", job_id=job_id, outcome="MISSING", worker=worker)
        return "MISSING"
    if expected_task_name is not None and job.task_name != expected_task_name:
        joblog.event("job_delivery_ignored", job_id=job.id, job_code=job.job_code, task_name=expected_task_name, outcome="TASK_MISMATCH")
        return "TASK_MISMATCH"
    if job.status != "QUEUED":
        joblog.event("job_duplicate_delivery", job_id=job.id, job_code=job.job_code, task_name=job.task_name, status=job.status,
                     environment=job.environment, worker=worker, outcome="NOT_ELIGIBLE")
        return f"NOT_ELIGIBLE:{job.status}"
    if not _claim(db, job.id, worker):
        joblog.event("job_duplicate_delivery", job_id=job.id, job_code=job.job_code, worker=worker, outcome="NOT_CLAIMED")
        return "NOT_CLAIMED"
    attempt = _start(db, job.id, worker)
    if attempt is None:
        return "LOST_CLAIM"
    started = time.monotonic()
    spec = spec_of(job)
    base: dict[str, Any] = {"job_id": job.id, "job_code": job.job_code, "attempt_id": attempt.id, "attempt_number": attempt.attempt_number,
            "task_name": job.task_name, "queue": job.queue_name, "environment": job.environment, "entity_type": job.entity_type,
            "entity_id": job.entity_id, "worker": worker}
    joblog.event("job_started", status="RUNNING", **base)
    try:
        actor = _validate_runtime(db, job, spec)
        assert spec is not None
        ctx = RequestContext(request_id=f"job:{job.job_code}:{attempt.attempt_number}", user_id=actor)
        deadline = time.monotonic() + max(spec.soft_time_limit - 30, 10)
        result = spec.handler(db, ctx, job, deadline)
    except Exception as e:
        db.rollback()
        retryable, code, message = classify(e)
        if code == "UNEXPECTED_ERROR":
            joblog.log.exception("job %s raised an unexpected error", job.job_code)   # server log only; users see the code
        outcome = _fail(db, job.id, attempt.id, worker, started, retryable, code, message,
                        e.details if isinstance(e, AppError) else None)
        joblog.event("job_finished", status=outcome, error_code=code, duration_ms=int((time.monotonic() - started) * 1000), **base)
        return outcome
    outcome = _succeed(db, job.id, attempt.id, worker, started, result)
    joblog.event("job_finished", status=outcome, duration_ms=int((time.monotonic() - started) * 1000),
                 counts={k: v for k, v in result.items() if isinstance(v, (int, bool))}, **base)
    return outcome


def _succeed(db: Session, job_id: uuid.UUID, attempt_id: uuid.UUID, worker: str, started: float, result: dict[str, Any]) -> str:
    x = ms.lock(db, BackgroundJob, job_id)
    if x is None or x.status != "RUNNING" or x.claimed_by != worker:
        db.rollback()                                               # the lease was recovered meanwhile; the effect is idempotent
        return "LEASE_LOST"
    _complete_attempt(db, attempt_id, "SUCCEEDED", started)
    x.completed_at, x.result = utcnow(), json.dumps(result, default=str, sort_keys=True)
    x.error_code, x.error_message = None, None
    _move(db, system_ctx(x.environment, f"job:{x.job_code}"), x, "SUCCEEDED", "JOB_SUCCEEDED")
    db.commit()
    return "SUCCEEDED"


def _fail(db: Session, job_id: uuid.UUID, attempt_id: uuid.UUID, worker: str, started: float, retryable: bool, code: str, message: str,
          details: dict[str, Any] | None) -> str:
    x = ms.lock(db, BackgroundJob, job_id)
    if x is None or x.status != "RUNNING" or x.claimed_by != worker:
        db.rollback()
        return "LEASE_LOST"
    now = utcnow()
    _complete_attempt(db, attempt_id, "RETRYABLE_ERROR" if retryable else "FAILED", started, code, message)
    x.error_code, x.error_message = code, message
    if details is not None:
        x.result = json.dumps(details, default=str, sort_keys=True)
    ctx = system_ctx(x.environment, f"job:{x.job_code}")
    if retryable and x.retry_count < x.max_retries:
        x.retry_count += 1
        x.available_at = now + timedelta(seconds=backoff_seconds(x.retry_count))
        x.claimed_by, x.lease_expires_at = None, None
        _move(db, ctx, x, "RETRY_WAITING", "JOB_RETRY_SCHEDULED", message, {"error_code": code, "retry_count": x.retry_count,
                                                                            "available_at": x.available_at})
        status = "RETRY_WAITING"
    else:
        x.failed_at = now
        x.claimed_by, x.lease_expires_at = None, None
        _move(db, ctx, x, "FAILED", "JOB_FAILED", message, {"error_code": code, "retries_exhausted": retryable})
        status = "FAILED"
    db.commit()
    return status


# ---------------------------------------------------------------- recovery tick (beat → worker; also `manage.py jobs-recover`)
def recover(db: Session, limit: int | None = None) -> dict[str, int]:
    s = get_settings()
    limit = limit or s.JOB_BATCH_SIZE
    now = utcnow()
    out = {"stale_claims_requeued": 0, "stale_runs_recovered": 0, "retries_requeued": 0, "republished": 0}
    for jid in db.scalars(select(BackgroundJob.id).where(BackgroundJob.status.in_(("CLAIMED", "RUNNING")),
                                                         BackgroundJob.lease_expires_at < now).limit(limit)).all():
        x = ms.lock(db, BackgroundJob, jid)
        if x is None or x.status not in ("CLAIMED", "RUNNING") or x.lease_expires_at is None or x.lease_expires_at >= utcnow():
            db.rollback()
            continue
        ctx = system_ctx(x.environment, f"job:{x.job_code}:recovery")
        if x.status == "CLAIMED":                                   # the worker died before starting: nothing ran
            x.claimed_by, x.claimed_at, x.lease_expires_at = None, None, None
            _move(db, ctx, x, "QUEUED", "JOB_REQUEUED", "stale claim: worker lost before start")
            out["stale_claims_requeued"] += 1
        else:                                                       # the worker died while running: its attempt is abandoned
            db.execute(update(BackgroundJobAttempt).where(BackgroundJobAttempt.background_job_id == x.id,
                                                          BackgroundJobAttempt.status == "RUNNING")
                       .values(status="ABANDONED", finished_at=utcnow(), error_code="WORKER_LOST",
                               error_message="The worker stopped responding before finishing (lease expired)."))
            x.claimed_by, x.lease_expires_at, x.error_code = None, None, "WORKER_LOST"
            x.error_message = "The worker stopped responding before finishing (lease expired)."
            if x.retry_count < x.max_retries:
                x.retry_count += 1
                x.available_at = utcnow()
                _move(db, ctx, x, "RETRY_WAITING", "JOB_RETRY_SCHEDULED", "stale run: worker lost", {"retry_count": x.retry_count})
            else:
                x.failed_at = utcnow()
                _move(db, ctx, x, "FAILED", "JOB_FAILED", "stale run: worker lost; retries exhausted", {"error_code": "WORKER_LOST"})
            out["stale_runs_recovered"] += 1
        db.commit()
    for jid in db.scalars(select(BackgroundJob.id).where(BackgroundJob.status == "RETRY_WAITING", BackgroundJob.available_at <= now)
                          .limit(limit)).all():
        x = ms.lock(db, BackgroundJob, jid)
        if x is None or x.status != "RETRY_WAITING" or x.available_at > utcnow():
            db.rollback()
            continue
        _move(db, system_ctx(x.environment, f"job:{x.job_code}:recovery"), x, "QUEUED", "JOB_REQUEUED", "retry due")
        db.commit()
        out["retries_requeued"] += 1
    stale_publish = now - timedelta(seconds=s.JOB_STALE_AFTER_SECONDS)
    for jid in db.scalars(select(BackgroundJob.id).where(
            BackgroundJob.status == "QUEUED", BackgroundJob.available_at <= utcnow(),
            (BackgroundJob.published_at.is_(None)) | (BackgroundJob.last_publish_error.is_not(None))
            | (BackgroundJob.published_at < stale_publish)).order_by(BackgroundJob.available_at).limit(limit)).all():
        db.commit()
        if publish(db, jid):
            out["republished"] += 1
    db.commit()
    if any(out.values()):
        joblog.event("job_recovery", counts=out)
    return out


def schedule(db: Session, job_type: str, now: datetime | None = None) -> list[uuid.UUID]:
    """Beat → worker: create (idempotently, one per environment and schedule slot) and publish the scheduled job."""
    spec = registry.TASKS[job_type]
    assert spec.interval_setting is not None
    interval = int(getattr(get_settings(), spec.interval_setting))
    now = now or utcnow()
    epoch = datetime(1970, 1, 1)                                     # naive UTC arithmetic (utcnow is naive UTC)
    slot = epoch + timedelta(seconds=(int((now - epoch).total_seconds()) // interval) * interval)
    created: list[uuid.UUID] = []
    for env in [e for e in get_settings().JOB_ENVIRONMENTS if e in spec.environments]:
        ctx = system_ctx(env, f"schedule:{job_type}:{env}")
        job, new = enqueue(db, ctx, job_type, environment=env, trigger_type="SCHEDULE", created_by=system_actor_id(env),
                           idempotency_key=f"schedule:{job_type}:{env}:{slot.isoformat()}", scheduled_at=slot)
        db.commit()
        if new:
            created.append(job.id)
    for jid in created:
        publish(db, jid)
    return created


# ---------------------------------------------------------------- operator actions (API; jobs.manage)
def visible_job(db: Session, principal: Principal, job_id: uuid.UUID) -> BackgroundJob:
    job = db.get(BackgroundJob, job_id)
    if job is None or job.environment != principal.user.environment:     # environment isolation: DEMO sees DEMO, LIVE sees LIVE
        raise NotFound("Background job not found.", error_code="JOB_NOT_FOUND")
    return job


def cancel(db: Session, ctx: RequestContext, principal: Principal, job_id: uuid.UUID, reason: str) -> BackgroundJob:
    job = visible_job(db, principal, job_id)
    if job.status == "CANCELLED":
        return job
    x = ms.lock(db, BackgroundJob, job.id)
    if x.status != "QUEUED":
        db.rollback()
        raise Conflict(f"Only a QUEUED job can be cancelled (this job is {x.status}).", error_code="JOB_NOT_CANCELLABLE")
    x.cancelled_at, x.reason = utcnow(), reason
    _move(db, ctx, x, "CANCELLED", "JOB_CANCELLED", reason)
    db.commit()
    joblog.event("job_cancelled", job_id=x.id, job_code=x.job_code, status="CANCELLED", request_id=ctx.request_id)
    return x


def retry(db: Session, ctx: RequestContext, principal: Principal, job_id: uuid.UUID, reason: str) -> BackgroundJob:
    job = visible_job(db, principal, job_id)
    spec = spec_of(job)
    x = ms.lock(db, BackgroundJob, job.id)
    if x.status != "FAILED":
        db.rollback()
        raise Conflict(f"Only a FAILED job can be requeued (this job is {x.status}).", error_code="JOB_NOT_RETRYABLE")
    if spec is None or not spec.manual_retry_safe:
        db.rollback()
        raise Conflict("This job type cannot be requeued manually.", error_code="JOB_NOT_RETRYABLE")
    x.available_at, x.reason, x.failed_at = utcnow(), reason, None
    _move(db, ctx, x, "QUEUED", "JOB_REQUEUED", reason, {"manual": True})
    db.commit()
    publish(db, x.id)
    return x


def trigger(db: Session, ctx: RequestContext, principal: Principal, job_type: str, key: str | None) -> BackgroundJob:
    spec = registry.TASKS.get(job_type)
    if spec is None or not spec.manually_triggerable:
        raise ValidationFailed(f"{job_type!r} is not an allow-listed task that can be run on request.", error_code="TASK_NOT_TRIGGERABLE")
    job, new = enqueue(db, ctx, job_type, environment=principal.user.environment, trigger_type="MANUAL", created_by=principal.user_id,
                       idempotency_key=f"manual:{principal.user_id}:{key}" if key else None)
    db.commit()
    if new:
        publish(db, job.id)
    return job
