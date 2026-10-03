"""Structured job logging on the `app.jobs` logger: the event name is the message and the allow-listed fields are structured fields
of the platform's JSON log line (Phase 12B D44, `app/core/logs.py`). Job failures and broker publication failures also feed the
`job_failures_total` / `redis_errors_total` metrics.

Only identifiers, codes, statuses and timings are logged — never payload values, secrets, tokens, KYC, bank or document content.
"""
import logging
from typing import Any

from app.core import metrics

log = logging.getLogger("app.jobs")
ALLOWED = frozenset({"event", "job_id", "job_code", "attempt_id", "attempt_number", "task_name", "queue", "environment", "entity_type",
                     "entity_id", "status", "outcome", "duration_ms", "request_id", "worker", "error_code", "retry_count", "counts",
                     "job_type", "published", "reason"})


def event(name: str, level: int = logging.INFO, **fields: Any) -> None:
    record = {"event": name, **{k: v for k, v in fields.items() if k in ALLOWED and v is not None}}
    if name == "job_finished" and record.get("status") in ("FAILED", "RETRY_WAITING"):
        metrics.inc("job_failures_total", {"task": str(record.get("task_name", "")), "status": str(record["status"])})
    elif name == "job_publish_failed":
        metrics.inc("redis_errors_total", {"component": "broker"})
    log.log(level, name, extra={"fields": record})
