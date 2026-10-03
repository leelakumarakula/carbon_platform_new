"""Background jobs API (`/api/v1/jobs`, Phase 12A) — operations only, Platform Administrator permissions (`jobs.read`, `jobs.manage`).

Every view is limited to the caller's environment (DEMO sees DEMO jobs, LIVE sees LIVE jobs). There is NO endpoint that runs an arbitrary
task: `POST /jobs/trigger` accepts only an allow-listed, manually-triggerable job type from the registry; retry requeues a FAILED job and
cancel cancels a QUEUED one — each audited with a reason. Payloads, stack traces, credentials and personal data are never returned."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, status

from app.api.deps import DB, Ctx, require_any
from app.schemas.jobs import JobAttemptOut, JobOut, JobReasonIn, JobsStatusOut, JobTriggerIn, TaskSpecOut
from app.security.permissions import P
from app.security.principal import Principal
from app.workers import job_service, operations

router = APIRouter(prefix="/jobs", tags=["operations — background jobs"])

Reader = Annotated[Principal, Depends(require_any(P.JOBS_READ))]
Manager = Annotated[Principal, Depends(require_any(P.JOBS_MANAGE))]
IdemKey = Annotated[str | None, Header(alias="Idempotency-Key", max_length=80)]


@router.get("", response_model=list[JobOut], summary="Background jobs of your environment (newest first)")
def list_jobs(principal: Reader, db: DB, status_filter: Annotated[str | None, Query(alias="status", max_length=20)] = None,
              job_type: Annotated[str | None, Query(max_length=60)] = None, limit: Annotated[int, Query(ge=1, le=200)] = 100) -> list[JobOut]:
    return [operations.job_out(db, principal, j) for j in operations.jobs(db, principal, status_filter, job_type, limit)]


@router.get("/registry", response_model=list[TaskSpecOut], summary="The allow-listed background tasks (read-only)")
def task_registry(principal: Reader) -> list[TaskSpecOut]:
    return operations.task_specs()


@router.get("/status", response_model=JobsStatusOut,
            summary="Database / broker reachability, worker heartbeats and job counts (broker reachable ≠ worker running)")
def jobs_status(principal: Reader, db: DB) -> JobsStatusOut:
    return operations.status(db, principal)


@router.post("/trigger", response_model=JobOut, status_code=status.HTTP_201_CREATED,
             summary="Queue an allow-listed maintenance task now (never an arbitrary task)")
def trigger(body: JobTriggerIn, principal: Manager, db: DB, ctx: Ctx, key: IdemKey = None) -> JobOut:
    return operations.job_out(db, principal, job_service.trigger(db, ctx, principal, body.job_type, key))


@router.get("/{job_id}", response_model=JobOut, summary="A background job")
def get_job(job_id: uuid.UUID, principal: Reader, db: DB) -> JobOut:
    return operations.job_out(db, principal, job_service.visible_job(db, principal, job_id))


@router.get("/{job_id}/attempts", response_model=list[JobAttemptOut], summary="The append-only attempt history of a job")
def job_attempts(job_id: uuid.UUID, principal: Reader, db: DB) -> list[JobAttemptOut]:
    return operations.attempts(db, job_service.visible_job(db, principal, job_id).id)


@router.post("/{job_id}/cancel", response_model=JobOut, summary="Cancel a QUEUED job (with a reason; audited)")
def cancel(job_id: uuid.UUID, body: JobReasonIn, principal: Manager, db: DB, ctx: Ctx) -> JobOut:
    return operations.job_out(db, principal, job_service.cancel(db, ctx, principal, job_id, body.reason))


@router.post("/{job_id}/retry", response_model=JobOut, summary="Requeue a FAILED job (with a reason; audited; preconditions re-checked)")
def retry(job_id: uuid.UUID, body: JobReasonIn, principal: Manager, db: DB, ctx: Ctx) -> JobOut:
    return operations.job_out(db, principal, job_service.retry(db, ctx, principal, job_id, body.reason))
