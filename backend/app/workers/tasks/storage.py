"""Orphan stored-file scan task (detection / reporting only)."""
from typing import Any

from app.workers.celery_app import celery_app
from app.workers.tasks import run_job


@celery_app.task(name="maintenance.scan_orphan_files", bind=True)
def scan_orphan_files(self: Any, job_id: str) -> str:
    return run_job(self, job_id)
