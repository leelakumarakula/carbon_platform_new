"""Expiry sweep tasks (9B reservations; Phase 10 orders and listings) — thin adapters over `job_service.execute`."""
from typing import Any

from app.workers.celery_app import celery_app
from app.workers.tasks import run_job


@celery_app.task(name="maintenance.expire_credit_reservations", bind=True)
def expire_credit_reservations(self: Any, job_id: str) -> str:
    return run_job(self, job_id)


@celery_app.task(name="maintenance.expire_marketplace_objects", bind=True)
def expire_marketplace_objects(self: Any, job_id: str) -> str:
    return run_job(self, job_id)
