"""Celery task adapters (Phase 12A). Each task only passes a job id to `job_service.execute`; no business rule lives in a task."""
import os
import socket
import uuid
from typing import Any

from app.core.database import get_session_factory
from app.workers import job_service, joblog


def run_job(task: Any, job_id: str) -> str:
    """Load the job from SQL Server (authoritative), verify and execute it. The Redis message is never trusted beyond the job id."""
    try:
        jid = uuid.UUID(str(job_id))
    except ValueError:
        joblog.event("job_delivery_ignored", outcome="INVALID_JOB_ID", task_name=getattr(task, "name", None))
        return "INVALID_JOB_ID"
    worker = f"{getattr(task.request, 'hostname', None) or socket.gethostname()}:{os.getpid()}"[:200]
    with get_session_factory()() as db:
        return job_service.execute(db, jid, worker, expected_task_name=task.name)
