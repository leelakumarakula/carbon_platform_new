"""Retention purge task (infrastructure only: no retention policy is configured, so nothing is purged)."""
from typing import Any

from app.workers.celery_app import celery_app
from app.workers.tasks import run_job


@celery_app.task(name="maintenance.retention_purge", bind=True)
def retention_purge(self: Any, job_id: str) -> str:
    return run_job(self, job_id)
