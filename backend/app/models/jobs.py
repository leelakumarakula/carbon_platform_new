"""Phase 12A — background jobs. SQL Server is the system of record; Redis (Celery broker) only transports job ids.

- `background_jobs`: one row per unit of background work (allow-listed task, environment, optional organization / entity, small JSON
  payload of identifiers, idempotency key). Lifecycle QUEUED → CLAIMED → RUNNING → SUCCEEDED, with RETRY_WAITING → QUEUED for bounded
  retries of transient failures, FAILED (permanent / retries exhausted; a person may requeue it) and CANCELLED (from QUEUED).
- `background_job_attempts`: append-only — one row per execution; written once RUNNING and completed once (trigger), never changed after.
- `background_worker_heartbeats`: the last heartbeat of each Celery worker process (operational visibility only).
Delivery is at-least-once; the business effect is made effectively-once by the SQL claim, the attempt history and the locked re-checks
of the existing domain services. Nothing in Redis is authoritative.
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Unicode, UnicodeText, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Environment, UUIDPrimaryKey, in_check, utcnow

JOB_STATUSES = ["QUEUED", "CLAIMED", "RUNNING", "SUCCEEDED", "RETRY_WAITING", "FAILED", "CANCELLED"]
JOB_TRIGGERS = ["SCHEDULE", "MANUAL", "SERVICE"]
ATTEMPT_STATUSES = ["RUNNING", "SUCCEEDED", "RETRYABLE_ERROR", "FAILED", "ABANDONED"]

# The non-login SYSTEM actors seeded by migration 0017 (one per data environment). They hold no role and no permission; they only
# attribute the system-owned transitions a job performs (deadline expiry) in audit, workflow and ledger records.
SYSTEM_ACTOR_IDS: dict[str, uuid.UUID] = {
    "LIVE": uuid.UUID("00000000-0000-4000-8000-00000000a001"),
    "DEMO": uuid.UUID("00000000-0000-4000-8000-00000000a002"),
}


class BackgroundJob(UUIDPrimaryKey, Base):
    __tablename__ = "background_jobs"
    __table_args__ = (
        CheckConstraint(in_check("status", JOB_STATUSES), name="status"),
        CheckConstraint(in_check("environment", Environment), name="environment"),
        CheckConstraint(in_check("trigger_type", JOB_TRIGGERS), name="trigger_type"),
        CheckConstraint("retry_count >= 0 AND max_retries >= 0", name="retries"),
        CheckConstraint("ISJSON(payload) = 1", name="payload_json"),
        CheckConstraint("result IS NULL OR ISJSON(result) = 1", name="result_json"),
        CheckConstraint("status <> 'SUCCEEDED' OR completed_at IS NOT NULL", name="succeeded"),
        CheckConstraint("status <> 'FAILED' OR (failed_at IS NOT NULL AND error_code IS NOT NULL)", name="failed"),
        CheckConstraint("status NOT IN ('CLAIMED', 'RUNNING') OR (claimed_by IS NOT NULL AND lease_expires_at IS NOT NULL)", name="claimed"),
        Index("uq_background_jobs_idempotency", "idempotency_key", unique=True, mssql_where=text("idempotency_key IS NOT NULL")),
        Index("ix_background_jobs_due", "status", "available_at"),
        Index("ix_background_jobs_task", "environment", "task_name", "created_at"),
    )
    job_code: Mapped[str] = mapped_column(Unicode(20), unique=True)                # JOB-YYYY-NNNNNN
    job_type: Mapped[str] = mapped_column(Unicode(60))                             # registry key, e.g. EXPIRY_CREDIT_RESERVATIONS
    task_name: Mapped[str] = mapped_column(Unicode(120))                           # allow-listed Celery task name
    queue_name: Mapped[str] = mapped_column(Unicode(40))
    status: Mapped[str] = mapped_column(Unicode(20), default="QUEUED")
    environment: Mapped[str] = mapped_column(Unicode(10))
    trigger_type: Mapped[str] = mapped_column(Unicode(10))
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"))
    entity_type: Mapped[str | None] = mapped_column(Unicode(40))
    entity_id: Mapped[str | None] = mapped_column(Unicode(64))
    idempotency_key: Mapped[str | None] = mapped_column(Unicode(160))
    payload: Mapped[str] = mapped_column(UnicodeText, default="{}")                # identifiers only — never secrets, PII or files
    payload_hash: Mapped[str] = mapped_column(Unicode(64))
    result: Mapped[str | None] = mapped_column(UnicodeText)                        # small JSON summary (counts)
    scheduled_at: Mapped[datetime | None]                                          # schedule slot of a SCHEDULE job
    available_at: Mapped[datetime] = mapped_column(default=utcnow)                 # not executed before this time (retry backoff)
    claimed_at: Mapped[datetime | None]
    claimed_by: Mapped[str | None] = mapped_column(Unicode(200))                   # worker identity holding the lease
    lease_expires_at: Mapped[datetime | None]
    started_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]
    failed_at: Mapped[datetime | None]
    cancelled_at: Mapped[datetime | None]
    retry_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    max_retries: Mapped[int] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(Unicode(60))
    error_message: Mapped[str | None] = mapped_column(Unicode(1000))               # sanitized; never a traceback
    published_at: Mapped[datetime | None]                                          # last successful hand-over to the broker
    publish_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    last_publish_error: Mapped[str | None] = mapped_column(Unicode(500))
    reason: Mapped[str | None] = mapped_column(Unicode(1000))                      # cancel / manual requeue reason
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))          # requester or the SYSTEM actor
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"), onupdate=utcnow)


class BackgroundJobAttempt(UUIDPrimaryKey, Base):
    __tablename__ = "background_job_attempts"
    __table_args__ = (
        CheckConstraint(in_check("status", ATTEMPT_STATUSES), name="status"),
        CheckConstraint("status = 'RUNNING' OR finished_at IS NOT NULL", name="finished"),
        Index("uq_background_job_attempts_number", "background_job_id", "attempt_number", unique=True),
    )
    background_job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("background_jobs.id"), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer)
    worker_identity: Mapped[str] = mapped_column(Unicode(200))
    task_name: Mapped[str] = mapped_column(Unicode(120))
    system_actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(Unicode(20), default="RUNNING")
    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    finished_at: Mapped[datetime | None]
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(Unicode(60))
    error_message: Mapped[str | None] = mapped_column(Unicode(1000))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))


class BackgroundWorkerHeartbeat(UUIDPrimaryKey, Base):
    __tablename__ = "background_worker_heartbeats"
    worker_identity: Mapped[str] = mapped_column(Unicode(200), unique=True)
    hostname: Mapped[str] = mapped_column(Unicode(200))
    pid: Mapped[int] = mapped_column(Integer)
    queues: Mapped[str] = mapped_column(Unicode(200))
    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_heartbeat_at: Mapped[datetime] = mapped_column(default=utcnow)
    stopped_at: Mapped[datetime | None]
