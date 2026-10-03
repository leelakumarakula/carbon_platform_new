"""Structured job logging: one JSON object per line on the `app.jobs` logger (compatible with the platform's standard logging).

Only identifiers, codes, statuses and timings are logged — never payload values, secrets, tokens, KYC, bank or document content.
"""
import json
import logging
from typing import Any

log = logging.getLogger("app.jobs")
ALLOWED = frozenset({"event", "job_id", "job_code", "attempt_id", "attempt_number", "task_name", "queue", "environment", "entity_type",
                     "entity_id", "status", "outcome", "duration_ms", "request_id", "worker", "error_code", "retry_count", "counts",
                     "job_type", "published", "reason"})


def event(name: str, level: int = logging.INFO, **fields: Any) -> None:
    record = {"event": name, **{k: v for k, v in fields.items() if k in ALLOWED and v is not None}}
    log.log(level, json.dumps(record, default=str, sort_keys=True))
