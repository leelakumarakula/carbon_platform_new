"""Worker heartbeat into SQL Server (operational visibility only — never used for job correctness, which is the SQL lease)."""
import logging
import os
import socket
import threading

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.models import BackgroundWorkerHeartbeat
from app.models.base import utcnow
from app.workers import registry

log = logging.getLogger("app.jobs")
_stop = threading.Event()
_thread: threading.Thread | None = None
_identity: str | None = None


def identity(hostname: str | None = None) -> str:
    return f"{hostname or socket.gethostname()}:{os.getpid()}"[:200]


def beat_once(worker: str, stopped: bool = False) -> None:
    with get_session_factory()() as db:
        row = db.scalars(select(BackgroundWorkerHeartbeat).where(BackgroundWorkerHeartbeat.worker_identity == worker)).first()
        now = utcnow()
        if row is None:
            row = BackgroundWorkerHeartbeat(worker_identity=worker, hostname=socket.gethostname()[:200], pid=os.getpid(),
                                            queues=",".join(registry.QUEUES), started_at=now)
            db.add(row)
        row.last_heartbeat_at = now
        row.stopped_at = now if stopped else None
        db.commit()


def _loop(worker: str) -> None:
    while not _stop.wait(get_settings().JOB_HEARTBEAT_SECONDS):
        try:
            beat_once(worker)
        except Exception:                                           # a missed heartbeat must never stop the worker
            log.warning("worker heartbeat failed", exc_info=True)


def start(hostname: str | None = None) -> None:
    global _thread, _identity
    _identity = identity(hostname)
    beat_once(_identity)
    _stop.clear()
    _thread = threading.Thread(target=_loop, args=(_identity,), name="job-heartbeat", daemon=True)
    _thread.start()


def stop() -> None:
    _stop.set()
    if _identity:
        try:
            beat_once(_identity, stopped=True)
        except Exception:
            log.warning("final worker heartbeat failed", exc_info=True)
