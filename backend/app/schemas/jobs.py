"""Phase 12A schemas — background jobs. Request bodies forbid unknown fields. There is no field through which a client can name an
arbitrary task, an import path or a payload: the trigger body names an allow-listed job type only."""
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.schemas.common import Reason, UtcDatetime


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class JobReasonIn(_Strict):
    reason: Reason


class JobTriggerIn(_Strict):
    job_type: str


class JobOut(BaseModel):
    id: uuid.UUID
    job_code: str
    job_type: str
    task_name: str
    queue_name: str
    status: str
    environment: str
    trigger_type: str
    organization_id: uuid.UUID | None
    entity_type: str | None
    entity_id: str | None
    scheduled_at: UtcDatetime | None
    available_at: UtcDatetime
    claimed_at: UtcDatetime | None
    claimed_by: str | None
    started_at: UtcDatetime | None
    completed_at: UtcDatetime | None
    failed_at: UtcDatetime | None
    cancelled_at: UtcDatetime | None
    retry_count: int
    max_retries: int
    error_code: str | None
    error_message: str | None
    result: dict[str, Any] | None
    published_at: UtcDatetime | None
    publish_attempts: int
    last_publish_error: str | None
    reason: str | None
    created_by_name: str | None
    created_at: UtcDatetime
    can_cancel: bool
    can_retry: bool


class JobAttemptOut(BaseModel):
    id: uuid.UUID
    attempt_number: int
    worker_identity: str
    task_name: str
    status: str
    started_at: UtcDatetime
    finished_at: UtcDatetime | None
    duration_ms: int | None
    error_code: str | None
    error_message: str | None
    system_actor_name: str | None


class TaskSpecOut(BaseModel):
    job_type: str
    task_name: str
    queue: str
    description: str
    environments: list[str]
    scheduled_every_seconds: int | None
    manually_triggerable: bool
    max_retries: int
    soft_time_limit: int
    time_limit: int
    idempotency: str


class WorkerOut(BaseModel):
    worker_identity: str
    hostname: str
    queues: str
    started_at: UtcDatetime
    last_heartbeat_at: UtcDatetime
    stopped_at: UtcDatetime | None
    alive: bool


class JobsStatusOut(BaseModel):
    environment: str
    database: str
    broker: str                      # NOT_CONFIGURED / REACHABLE / UNREACHABLE — reachability says nothing about workers
    workers: list[WorkerOut]
    worker_alive: bool               # a heartbeat within 3 × JOB_HEARTBEAT_SECONDS
    counts: dict[str, int]
    last_scheduled_at: UtcDatetime | None
    note: str
