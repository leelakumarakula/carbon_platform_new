"""GET /metrics — platform-neutral metrics for the self-hosted monitoring platform (Phase 12B D43; no vendor selected).

- OpenMetrics text (an open exposition standard) by default, or JSON with `?format=json`.
- Protected by a bearer token (METRICS_TOKEN, compared in constant time). Without METRICS_TOKEN the endpoint does not exist (404), so
  nothing is exposed by default. It lives outside the API prefix: no rate limiting, no api_access_logs rows per scrape.
- Contents: per-process counters / timings (API requests, latency, 5xx, rate-limiter fail-open, Redis errors, job failures, antivirus,
  storage, readiness, orphan deletions) plus gauges computed at scrape time from SQL Server (job queue depth, oldest queued job,
  quarantined documents) and the rate-limiter state. No personal data, identifiers of business records or secrets.
"""
import hmac
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from sqlalchemy import func, select

from app.core import metrics
from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.rate_limit import limiter
from app.models import BackgroundJob, Document
from app.models.base import utcnow

router = APIRouter(include_in_schema=False)
OPENMETRICS = "application/openmetrics-text; version=1.0.0; charset=utf-8"


def _gauges() -> dict[str, float]:
    g: dict[str, float] = {"rate_limiter_degraded": 1.0 if limiter.degraded() else 0.0}
    try:
        with get_session_factory()() as db:
            counts: dict[str, int] = {str(st): int(n) for st, n in db.execute(
                select(BackgroundJob.status, func.count()).group_by(BackgroundJob.status)).all()}
            oldest = db.scalar(select(func.min(BackgroundJob.available_at)).where(BackgroundJob.status == "QUEUED"))
            quarantined = db.scalar(select(func.count()).select_from(Document).where(Document.status == "QUARANTINED"))
        for status in ("QUEUED", "RETRY_WAITING", "CLAIMED", "RUNNING", "FAILED"):
            g[f"jobs_{status.lower()}"] = float(counts.get(status, 0))
        g["jobs_oldest_queued_age_seconds"] = max(0.0, (utcnow() - oldest).total_seconds()) if oldest else 0.0
        g["documents_quarantined"] = float(quarantined or 0)
        g["database_up"] = 1.0
    except Exception:
        metrics.inc("db_failures_total", {"probe": "metrics"})
        g["database_up"] = 0.0
    try:
        from app.ops.disk import status as disk_status
        for name, mb in disk_status()[1].items():
            g[f"disk_free_mb_{name}"] = float(mb)
    except Exception:
        metrics.inc("disk_probe_failures_total")
    g.update(_backup_ages())
    return g


def _backup_ages() -> dict[str, float]:
    """Seconds since the last FULL / DIFF / LOG backup of the application database (msdb). -1 = none recorded / not visible to this
    login. The LOG age is the measurable signal for the 15-minute RPO (D25)."""
    from urllib.parse import urlsplit

    from app.ops.sqlserver import backup_freshness, master_engine
    s = get_settings()
    name = (urlsplit(s.DATABASE_URL).path.lstrip("/") if s.DATABASE_URL else "") or s.SQL_SERVER_DATABASE
    try:
        eng = master_engine()
        try:
            ages = backup_freshness(eng, name)
        finally:
            eng.dispose()
    except Exception:
        ages = {}
    return {f"db_last_{k}_backup_age_seconds": (v if v is not None else -1.0) for k, v in
            {**{"full": None, "diff": None, "log": None}, **ages}.items()}


@router.get("/metrics")
def scrape(request: Request, format: str = "openmetrics") -> Response:
    token = get_settings().METRICS_TOKEN
    if not token:
        return JSONResponse(status_code=404, content={"success": False, "error_code": "NOT_FOUND", "message": "Not found.",
                                                      "details": {}, "request_id": getattr(request.state, "request_id", None)})
    supplied = request.headers.get("authorization", "")
    if not hmac.compare_digest(supplied.encode(), f"Bearer {token}".encode()):
        return JSONResponse(status_code=401, headers={"WWW-Authenticate": "Bearer"},
                            content={"success": False, "error_code": "AUTHENTICATION_FAILED", "message": "Authentication required.",
                                     "details": {}, "request_id": getattr(request.state, "request_id", None)})
    gauges = _gauges()
    if format == "json":
        body: dict[str, Any] = {**metrics.snapshot(), "gauges": gauges}
        return JSONResponse(body, headers={"Cache-Control": "no-store"})
    return PlainTextResponse(metrics.openmetrics(gauges), media_type=OPENMETRICS, headers={"Cache-Control": "no-store"})
