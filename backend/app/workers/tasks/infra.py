"""Infrastructure ticks sent by Celery beat. They create (idempotently, per schedule slot) or recover SQL job rows and publish them;
they perform no business work themselves."""
from typing import Any

from app.core.database import get_session_factory
from app.workers import job_service, registry
from app.workers.celery_app import celery_app


@celery_app.task(name="jobs.schedule")
def schedule(job_type: str) -> int:
    if job_type not in registry.TASKS:                   # only allow-listed job types can ever be scheduled
        return 0
    with get_session_factory()() as db:
        return len(job_service.schedule(db, job_type))


@celery_app.task(name="jobs.recover")
def recover() -> dict[str, Any]:
    with get_session_factory()() as db:
        return job_service.recover(db)
