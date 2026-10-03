"""Platform-neutral application metrics (Phase 12B D43 / D44).

A small in-process registry of counters and timing summaries, exported both as JSON and in the OpenMetrics text format (an open
exposition standard many self-hosted monitoring platforms scrape). No vendor client library is used. Values are per process: each API /
worker process exposes its own; the monitoring platform aggregates. Labels must never carry personal data, secrets or identifiers of
business records — only route templates, methods, status classes, component and result names.
"""
import math
import threading
from collections import defaultdict
from typing import Any

_lock = threading.Lock()
_counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
_timings: dict[tuple[str, tuple[tuple[str, str], ...]], list[float]] = {}   # [count, sum, max]
HELP = {
    "api_requests_total": "API requests by method, route template and status class",
    "api_request_duration_seconds": "API request duration",
    "api_errors_total": "API responses with status >= 500",
    "rate_limiter_degraded_total": "Rate-limiter backend failures (fail-open, D20)",
    "redis_errors_total": "Redis errors by component",
    "job_failures_total": "Background job attempts ending FAILED or RETRY_WAITING",
    "av_scans_total": "Antivirus scans by trigger and result",
    "av_scan_duration_seconds": "Antivirus scan duration",
    "av_scan_failures_total": "Antivirus scans that could not complete (ERROR)",
    "storage_failures_total": "Object-storage failures by operation",
    "db_failures_total": "Database failures observed by probes",
    "readiness_failures_total": "Readiness probe failures by component",
    "orphan_objects_deleted_total": "Orphan storage objects deleted by the cleanup job",
}


def _key(name: str, labels: dict[str, str] | None) -> tuple[str, tuple[tuple[str, str], ...]]:
    return name, tuple(sorted((labels or {}).items()))


def inc(name: str, labels: dict[str, str] | None = None, value: float = 1.0) -> None:
    with _lock:
        _counters[_key(name, labels)] += value


def observe(name: str, seconds: float, labels: dict[str, str] | None = None) -> None:
    k = _key(name, labels)
    with _lock:
        t = _timings.setdefault(k, [0.0, 0.0, 0.0])
        t[0] += 1
        t[1] += seconds
        t[2] = max(t[2], seconds)


def snapshot() -> dict[str, Any]:
    with _lock:
        counters = [{"name": n, "labels": dict(lb), "value": v} for (n, lb), v in sorted(_counters.items())]
        timings = [{"name": n, "labels": dict(lb), "count": int(t[0]), "sum": round(t[1], 6), "max": round(t[2], 6)}
                   for (n, lb), t in sorted(_timings.items())]
    return {"counters": counters, "timings": timings}


def _labels(lb: tuple[tuple[str, str], ...], extra: dict[str, str] | None = None) -> str:
    items = list(lb) + list((extra or {}).items())
    if not items:
        return ""
    return "{" + ",".join(f'{k}="{_esc(v)}"' for k, v in items) + "}"


def _esc(v: object) -> str:
    return str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def openmetrics(gauges: dict[str, float] | None = None) -> str:
    """OpenMetrics text exposition (counters, summaries as _count / _sum, optional gauges computed at scrape time)."""
    lines: list[str] = []
    snap_c, snap_t = {}, {}
    with _lock:
        snap_c, snap_t = dict(_counters), {k: list(v) for k, v in _timings.items()}
    for name in sorted({n for n, _ in snap_c}):
        lines += [f"# HELP {name.removesuffix('_total')} {HELP.get(name, name)}", f"# TYPE {name.removesuffix('_total')} counter"]
        lines += [f"{name}{_labels(lb)} {v}" for (n, lb), v in sorted(snap_c.items()) if n == name]
    for name in sorted({n for n, _ in snap_t}):
        lines += [f"# HELP {name} {HELP.get(name, name)}", f"# TYPE {name} summary"]
        for (n, lb), t in sorted(snap_t.items()):
            if n == name:
                lines += [f"{name}_count{_labels(lb)} {int(t[0])}", f"{name}_sum{_labels(lb)} {t[1]}"]
    for name, value in sorted((gauges or {}).items()):
        lines += [f"# TYPE {name} gauge", f"{name} {value if math.isfinite(value) else 0}"]
    lines.append("# EOF")
    return "\n".join(lines) + "\n"


def reset() -> None:
    """Tests only."""
    with _lock:
        _counters.clear()
        _timings.clear()
