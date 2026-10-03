"""Celery application (Phase 12A). Redis (REDIS_URL) is the broker — transport only. SQL Server holds every job, attempt and result;
the Celery result backend is disabled. JSON only (no pickle). Late acknowledgement + reject-on-worker-lost give at-least-once delivery;
the SQL claim makes the business effect effectively-once.

Run (see docs/background-jobs.md):
    celery -A app.workers.celery_app:celery_app worker -Q default,maintenance -l info [-P solo on Windows development]
    celery -A app.workers.celery_app:celery_app beat -l info --schedule <writable path>/celerybeat-schedule
"""
from typing import Any

from celery import Celery
from celery.signals import worker_process_init, worker_ready, worker_shutdown

from app.core.config import get_settings
from app.workers import registry


def _beat_schedule() -> dict[str, dict[str, Any]]:
    s = get_settings()
    beat: dict[str, dict[str, Any]] = {
        "jobs-recover": {"task": "jobs.recover", "schedule": float(s.JOB_RECOVERY_INTERVAL), "options": {"queue": registry.QUEUE_DEFAULT}},
    }
    for spec in registry.TASKS.values():
        if spec.interval_setting:
            beat[f"schedule-{spec.job_type.lower()}"] = {"task": "jobs.schedule", "schedule": float(getattr(s, spec.interval_setting)),
                                                          "args": [spec.job_type], "options": {"queue": registry.QUEUE_DEFAULT}}
    return beat


def _broker_ssl(url: str | None, ca_cert: str | None) -> dict[str, object] | None:
    if not (url or "").startswith("rediss://"):
        return None
    import ssl
    opts: dict[str, object] = {"ssl_cert_reqs": ssl.CERT_REQUIRED}
    if ca_cert:
        opts["ssl_ca_certs"] = ca_cert
    return opts


def create_celery() -> Celery:
    s = get_settings()
    app = Celery("carbon_platform", include=["app.workers.tasks.expiry", "app.workers.tasks.storage", "app.workers.tasks.retention",
                                             "app.workers.tasks.infra"])
    app.conf.update(
        broker_url=s.REDIS_URL,
        broker_connection_timeout=3,
        broker_connection_retry_on_startup=True,
        # The visibility timeout must exceed the longest task; the SQL lease (JOB_STALE_AFTER_SECONDS) is the authority anyway.
        broker_transport_options={"visibility_timeout": s.JOB_STALE_AFTER_SECONDS + 300, "socket_connect_timeout": 3, "socket_timeout": 10},
        # Phase 12B D23: rediss:// verifies the broker certificate (REDIS_CA_CERT for a private CA)
        broker_use_ssl=_broker_ssl(s.REDIS_URL, s.REDIS_CA_CERT),
        result_backend=None,
        task_ignore_result=True,
        task_serializer="json",
        accept_content=["json"],
        result_accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        task_default_queue=registry.QUEUE_DEFAULT,
        task_routes={"maintenance.*": {"queue": registry.QUEUE_MAINTENANCE}, "jobs.*": {"queue": registry.QUEUE_DEFAULT}},
        task_soft_time_limit=270,
        task_time_limit=300,
        worker_hijack_root_logger=False,
        worker_send_task_events=False,
        beat_schedule=_beat_schedule(),
    )
    return app


celery_app = create_celery()


@worker_process_init.connect
def _dispose_engine(**_: Any) -> None:
    """SQLAlchemy pools are not fork-safe: each worker process opens its own connections."""
    from app.core.database import get_engine
    get_engine().dispose()


@worker_ready.connect
def _start_heartbeat(sender: Any = None, **_: Any) -> None:
    if not get_settings().REDIS_URL:
        raise RuntimeError("REDIS_URL is not configured: a Celery worker needs the Redis broker.")
    from app.workers import heartbeat
    heartbeat.start(getattr(sender, "hostname", None))


@worker_shutdown.connect
def _stop_heartbeat(**_: Any) -> None:
    from app.workers import heartbeat
    heartbeat.stop()
