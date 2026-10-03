"""Health endpoints (Phase 12B D46 / F9).

- `GET /health`      — kept for compatibility: status + database. The environment name is included only outside production.
- `GET /health/live` — liveness: the process answers. No dependency is touched, so a database / Redis outage never restarts the pod.
- `GET /health/ready` — readiness for the load balancer. HTTP 503 (`not_ready`) when the node cannot serve correctly:
    * the database is unreachable, or the schema is not at the migration head;
    * production security misconfiguration: public bucket policy / versioning off, Redis without `noeviction` or persistence,
      no real antivirus scanner.
  Outages of components the platform degrades around are reported as `degraded` with HTTP 200, because removing every API node would
  turn a partial outage into a full one: Redis (rate limiting fails open per D20, jobs stay QUEUED in SQL Server per D24), object
  storage and the antivirus engine (uploads / downloads answer 503 individually; LIVE uploads are never accepted unscanned).
  Production responses carry check names and states only — no hosts, versions, environment or error text (details are logged).
"""
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Response
from pydantic import BaseModel
from sqlalchemy import text

from app.api.deps import DB
from app.core import metrics
from app.core.config import get_settings
from app.core.rate_limit import limiter, redis_client

router = APIRouter(tags=["health"])
log = logging.getLogger("app.health")
OK, DEGRADED, FAILED, NOT_CONFIGURED = "ok", "degraded", "failed", "not_configured"


class Health(BaseModel):
    status: str
    database: str
    environment: str | None = None


class Live(BaseModel):
    status: str


class Ready(BaseModel):
    status: str                              # ready | degraded | not_ready
    checks: dict[str, str]
    details: dict[str, str] | None = None    # outside production only


@router.get("/health", response_model=Health, response_model_exclude_none=True)
def health(db: DB) -> Health:
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        database = "unavailable"
    s = get_settings()
    return Health(status="ok" if database == "ok" else "degraded", database=database,
                  environment=None if s.is_production else s.APP_ENV)


@router.get("/health/live", response_model=Live)
def live() -> Live:
    return Live(status="alive")


@lru_cache
def _migration_head() -> str | None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    backend = Path(__file__).resolve().parents[3]
    cfg = Config(str(backend / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend / "alembic"))
    return ScriptDirectory.from_config(cfg).get_current_head()


def _database(db: Any) -> tuple[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        return FAILED, f"database unreachable ({type(e).__name__})"
    try:
        current = db.execute(text("SELECT version_num FROM dbo.alembic_version")).scalar()
    except Exception as e:
        return FAILED, f"migration state unreadable ({type(e).__name__})"
    head = _migration_head()
    if current != head:
        return FAILED, f"schema at {current}, code expects {head}"
    return OK, f"schema at {current}"


def _storage() -> tuple[str, str]:
    from app.integrations.storage import get_storage
    try:
        problems = get_storage().health()
    except Exception as e:                                   # misconfiguration (e.g. local storage in production)
        return FAILED, f"storage not configured ({type(e).__name__})"
    if not problems:
        return OK, "object storage ready"
    outage = all("unreachable" in p for p in problems)
    return (DEGRADED if outage else FAILED), "; ".join(problems)


def _scanner() -> tuple[str, str]:
    from app.integrations.malware import get_scanner
    try:
        scanner = get_scanner()
    except Exception as e:                                   # unregistered adapter / test double in production
        return FAILED, f"antivirus scanner not configured ({type(e).__name__})"
    try:
        problems = scanner.health()
    except Exception as e:
        problems = [f"health check failed ({type(e).__name__})"]
    if problems:
        return DEGRADED, "; ".join(problems)
    note = " (test-signature check only: not an antivirus engine)" if scanner.is_test_double else ""
    return OK, f"scanner {scanner.name}{note}"


def redis_status(url: str | None, *, production: bool) -> tuple[str, str]:
    """Ping; in production also verify `maxmemory-policy noeviction` and AOF persistence (D23) through INFO."""
    if not url:
        return NOT_CONFIGURED, "not configured"
    s = get_settings()
    try:
        client = redis_client(url, ca_cert=s.REDIS_CA_CERT, timeout=0.5)
        client.ping()
    except Exception as e:
        return DEGRADED, f"unreachable ({type(e).__name__})"
    if not production:
        return OK, "reachable"
    try:
        memory, persistence = client.info("memory"), client.info("persistence")
    except Exception as e:
        return DEGRADED, f"INFO not permitted for this ACL user ({type(e).__name__}); grant +info to verify noeviction / AOF"
    problems = []
    if memory.get("maxmemory_policy") != "noeviction":
        problems.append(f"maxmemory-policy is {memory.get('maxmemory_policy')} (noeviction required)")
    if str(persistence.get("aof_enabled")) != "1":
        problems.append("AOF persistence is off (appendonly yes required)")
    return (FAILED, "; ".join(problems)) if problems else (OK, "reachable, noeviction, AOF on")


def _disk() -> tuple[str, str]:
    """Phase 12B-III: below DISK_WARN_FREE_MB degraded, below DISK_CRITICAL_FREE_MB failed (writes would risk corruption)."""
    from app.ops.disk import status
    try:
        state, free = status()
    except Exception as e:
        return DEGRADED, f"disk usage unreadable ({type(e).__name__})"
    detail = ", ".join(f"{k} {v} MB free" for k, v in free.items())
    return {"ok": OK, "warn": DEGRADED, "critical": FAILED}[state], detail


def _rate_limiter() -> tuple[str, str]:
    s = get_settings()
    if s.RATE_LIMIT_BACKEND == "memory":
        return OK, "in-process limiter (single API process only)"
    state, detail = redis_status(s.RATE_LIMIT_REDIS_URL or s.REDIS_URL, production=s.is_production)
    if limiter.degraded() and state == OK:
        state, detail = DEGRADED, "recovering from a Redis outage (fail-open, D20)"
    return state, detail


@router.get("/health/ready", response_model=Ready, response_model_exclude_none=True,
            responses={503: {"model": Ready, "description": "Not ready"}})
def ready(db: DB, response: Response) -> Ready:
    s = get_settings()
    results = {
        "database": _database(db),
        "storage": _storage(),
        "antivirus": _scanner(),
        "broker": redis_status(s.REDIS_URL, production=s.is_production),
        "rate_limiter": _rate_limiter(),
        "disk": _disk(),
    }
    checks = {k: v[0] for k, v in results.items()}
    if s.is_production and checks["broker"] == NOT_CONFIGURED:
        checks["broker"] = DEGRADED                         # production jobs stay QUEUED without a broker (D24)
    failed = [k for k, v in checks.items() if v == FAILED]
    status = "not_ready" if failed else "degraded" if DEGRADED in checks.values() else "ready"
    for k, (state, detail) in results.items():
        if state in (FAILED, DEGRADED):
            metrics.inc("readiness_failures_total", {"check": k, "state": state})
            log.warning("readiness check %s %s: %s", k, state, detail)
    if failed:
        response.status_code = 503
    return Ready(status=status, checks=checks, details=None if s.is_production else {k: v[1] for k, v in results.items()})
