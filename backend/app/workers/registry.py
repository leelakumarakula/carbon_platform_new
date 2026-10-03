"""The allow-list of background tasks (Phase 12A). Nothing outside this registry can be enqueued, triggered or executed: task names are
never taken from a client or a database payload as an import path. Financial, approval, issuance, transfer and retirement work has NO
entry and must never get one (revenue recognition / reversal stay inside their Phase 10 transactions)."""
from dataclasses import dataclass, field

from app.workers import handlers
from app.workers.handlers import Handler

QUEUE_DEFAULT = "default"           # infrastructure ticks (scheduling, recovery)
QUEUE_MAINTENANCE = "maintenance"   # allow-listed maintenance jobs
QUEUES = (QUEUE_DEFAULT, QUEUE_MAINTENANCE)


@dataclass(frozen=True)
class TaskSpec:
    job_type: str
    task_name: str
    queue: str
    description: str
    handler: Handler
    idempotency: str
    environments: frozenset[str] = frozenset({"LIVE", "DEMO"})
    soft_time_limit: int = 270          # seconds; the handler's cooperative budget stops new work well before it
    time_limit: int = 300               # hard limit (enforced by the prefork pool; JOB_STALE_AFTER_SECONDS is larger)
    interval_setting: str | None = None  # Settings attribute holding the schedule interval (None = not scheduled)
    manually_triggerable: bool = False
    manual_retry_safe: bool = True
    payload_keys: frozenset[str] = field(default_factory=frozenset)   # accepted payload identifiers (none for 12A tasks)
    max_retries: int | None = None      # None = JOB_MAX_RETRIES


TASKS: dict[str, TaskSpec] = {s.job_type: s for s in (
    TaskSpec("EXPIRY_CREDIT_RESERVATIONS", "maintenance.expire_credit_reservations", QUEUE_MAINTENANCE,
             "Expire ACTIVE 9B credit reservations whose deadline has passed (proactive sweep; lazy expiry stays).",
             handlers.expire_credit_reservations,
             "each reservation is locked and re-checked (ACTIVE and due) in its own transaction; a second run finds nothing to expire",
             interval_setting="JOB_EXPIRY_INTERVAL", manually_triggerable=True),
    TaskSpec("EXPIRY_MARKETPLACE_OBJECTS", "maintenance.expire_marketplace_objects", QUEUE_MAINTENANCE,
             "Expire unpaid PLACED orders past their payment deadline (with their reservations), then listings past valid_until.",
             handlers.expire_marketplace_objects,
             "each order / listing is locked and re-checked (state, deadline, held payment) in its own transaction",
             interval_setting="JOB_EXPIRY_INTERVAL", manually_triggerable=True),
    TaskSpec("ORPHAN_FILE_SCAN", "maintenance.scan_orphan_files", QUEUE_MAINTENANCE,
             "Delete stored objects no document version references and older than the grace period (Phase 12B D10; separate deletion "
             "identity; each deletion audited).",
             handlers.scan_orphan_files,
             "each candidate is re-checked under a key-range lock in its own transaction; a referenced or recent object is never deleted",
             interval_setting="JOB_ORPHAN_SCAN_INTERVAL", manually_triggerable=True),
    TaskSpec("DOCUMENT_RESCAN", "maintenance.rescan_documents", QUEUE_MAINTENANCE,
             "Rescan one document (security request / scanner-unavailable upload) or every document without a CLEAN scan; INFECTED "
             "quarantines. Never releases (Phase 12B D12 / D15 / D16).",
             handlers.rescan_documents, "append-only scan rows; quarantine is idempotent; release is a separate security action",
             interval_setting="JOB_RESCAN_INTERVAL", manually_triggerable=True),
    TaskSpec("RETENTION_PURGE", "maintenance.retention_purge", QUEUE_MAINTENANCE,
             "Operational retention (D48, OPERATIONAL_RETENTION_DAYS): access logs, read notifications, stopped worker heartbeats, "
             "stale temporary upload files. Append-only, financial, credit, audit and verification records are never purged.",
             handlers.retention_purge, "age-based deletes in bounded batches; a second run finds nothing older than the cutoff",
             interval_setting="JOB_RETENTION_INTERVAL",
             manually_triggerable=True),
)}

BY_TASK_NAME: dict[str, TaskSpec] = {s.task_name: s for s in TASKS.values()}
INFRA_TASKS = ("jobs.schedule", "jobs.recover")   # Celery-only ticks; they create / recover job rows and perform no business work
