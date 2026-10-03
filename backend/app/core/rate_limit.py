"""Fixed-window rate limiting behind one abstraction (Phase 12B D18–D21).

- `InMemoryRateLimiter`: single API process (local development and tests).
- `RedisRateLimiter`: shared counters for several API processes (`INCR` + `EXPIRE` on `<prefix>:<sha256(key)>:<window>`). Keys are
  hashed, so no email address or identifier is stored in Redis (D18); counters are the only data written.
- **Redis unavailable -> FAIL OPEN (locked D20).** The request is allowed; the condition is never silent: a WARNING log (throttled),
  the `rate_limiter_degraded_total` / `redis_errors_total` metrics, and `degraded()` for readiness and metrics. Database-backed
  protections (account lockout after failed sign-ins, refresh-token reuse detection, sessions) do not depend on Redis and stay active.
  After a failure Redis is not retried for `RATE_LIMIT_REDIS_RETRY_SECONDS`, so an outage adds no latency to requests.

`limiter` is the process-wide facade every caller uses (`limiter.hit(...)`); the backend is chosen from configuration on first use
(`RATE_LIMIT_BACKEND`), and tests can install one with `limiter.use(...)`.
"""
import hashlib
import logging
import threading
import time
from typing import Any, Protocol

from app.core import metrics
from app.core.config import get_settings

log = logging.getLogger("app.ratelimit")


class RateLimitBackend(Protocol):
    def hit(self, key: str, limit: int, window_seconds: int) -> bool: ...
    def reset(self) -> None: ...


class InMemoryRateLimiter:
    name = "memory"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buckets: dict[str, tuple[int, float]] = {}

    def hit(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        """Register a hit; returns False when the caller has exceeded `limit` within the window."""
        now = time.monotonic()
        with self._lock:
            count, started = self._buckets.get(key, (0, now))
            if now - started >= window_seconds:
                count, started = 0, now
            count += 1
            self._buckets[key] = (count, started)
            if len(self._buckets) > 50_000:  # crude memory guard
                self._buckets = {k: v for k, v in self._buckets.items() if now - v[1] < window_seconds}
            return count <= limit

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()

    def degraded(self) -> bool:
        return False


class RedisRateLimiter:
    """Shared fixed-window counters. `client` is a redis-py client (or any object with `.pipeline()`)."""
    name = "redis"

    def __init__(self, client: Any, prefix: str = "rl", retry_seconds: float = 5.0) -> None:
        self.client, self.prefix, self.retry_seconds = client, prefix, retry_seconds
        self._down_until = 0.0
        self._last_log = 0.0
        self._lock = threading.Lock()
        self.fail_open_count = 0

    def _key(self, key: str, window_seconds: int, now: float) -> str:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:40]
        return f"{self.prefix}:{digest}:{int(now // window_seconds)}"

    def hit(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        now = time.time()
        if now < self._down_until:
            return self._fail_open(None)
        try:
            pipe = self.client.pipeline(transaction=True)
            k = self._key(key, window_seconds, now)
            pipe.incr(k)
            pipe.expire(k, window_seconds * 2)
            count = int(pipe.execute()[0])
        except Exception as e:                                       # connection refused, timeout, auth / ACL failure, …
            self._down_until = now + self.retry_seconds
            metrics.inc("redis_errors_total", {"component": "rate_limiter"})
            return self._fail_open(e)
        if self._down_until:
            with self._lock:
                self._down_until = 0.0
            log.warning("rate limiter: Redis is reachable again; shared rate limits are enforced again")
        return count <= limit

    def _fail_open(self, error: Exception | None) -> bool:
        """Locked D20: allow the request, but never silently."""
        self.fail_open_count += 1
        metrics.inc("rate_limiter_degraded_total", {"backend": "redis"})
        now = time.monotonic()
        with self._lock:
            should_log = now - self._last_log >= 30
            if should_log:
                self._last_log = now
        if should_log:
            log.warning("rate limiter DEGRADED (fail-open, D20): Redis unavailable (%s); requests are not rate limited by Redis. "
                        "Database lockout and refresh-token reuse detection remain active.",
                        type(error).__name__ if error else "retry pause")
        return True

    def degraded(self) -> bool:
        return time.time() < self._down_until

    def reset(self) -> None:
        self._down_until = 0.0
        try:
            for k in self.client.scan_iter(match=f"{self.prefix}:*", count=500):
                self.client.delete(k)
        except Exception as e:                                       # reset is a test / operator convenience
            log.warning("rate limiter reset skipped: Redis unavailable (%s)", type(e).__name__)


def redis_client(url: str, *, ca_cert: str | None = None, timeout: float = 0.5) -> Any:
    """redis-py client with short timeouts (a slow / absent Redis must not slow requests). TLS (`rediss://`) verifies the server
    certificate, with `ca_cert` for a private CA."""
    import redis
    kwargs: dict[str, Any] = {"socket_connect_timeout": timeout, "socket_timeout": timeout, "retry_on_timeout": False,
                              "health_check_interval": 0}
    if url.startswith("rediss://"):
        kwargs["ssl_cert_reqs"] = "required"
        if ca_cert:
            kwargs["ssl_ca_certs"] = ca_cert
    return redis.Redis.from_url(url, **kwargs)


def build_backend() -> RateLimitBackend:
    s = get_settings()
    if s.RATE_LIMIT_BACKEND == "redis":
        url = s.RATE_LIMIT_REDIS_URL or s.REDIS_URL
        assert url, "RATE_LIMIT_BACKEND=redis needs RATE_LIMIT_REDIS_URL or REDIS_URL (validated at start-up)"
        return RedisRateLimiter(redis_client(url, ca_cert=s.REDIS_CA_CERT, timeout=s.RATE_LIMIT_REDIS_TIMEOUT_SECONDS),
                                prefix=f"{s.RATE_LIMIT_KEY_PREFIX}:{s.APP_ENV.lower()}", retry_seconds=s.RATE_LIMIT_REDIS_RETRY_SECONDS)
    return InMemoryRateLimiter()


class Limiter:
    """Process-wide facade: callers keep `limiter.hit(...)`; the backend is resolved lazily from configuration."""

    def __init__(self) -> None:
        self._backend: RateLimitBackend | None = None
        self._lock = threading.Lock()

    @property
    def backend(self) -> RateLimitBackend:
        if self._backend is None:
            with self._lock:
                if self._backend is None:
                    self._backend = build_backend()
        return self._backend

    def use(self, backend: RateLimitBackend | None) -> None:
        """Install a backend (tests) or None to re-resolve from configuration."""
        self._backend = backend

    def hit(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        return self.backend.hit(key, limit, window_seconds)

    def reset(self) -> None:
        self.backend.reset()

    def degraded(self) -> bool:
        return bool(getattr(self.backend, "degraded", lambda: False)())

    @property
    def name(self) -> str:
        return str(getattr(self.backend, "name", type(self.backend).__name__))


limiter = Limiter()
