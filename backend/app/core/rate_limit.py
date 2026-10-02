"""Fixed-window rate limiter.

The in-memory backend serves a single API process (local development and tests).
A Redis backend is required before running multiple API workers (Phase 12 hardening).
"""
import threading
import time
from typing import Protocol


class RateLimitBackend(Protocol):
    def hit(self, key: str, limit: int, window_seconds: int) -> bool: ...
    def reset(self) -> None: ...


class InMemoryRateLimiter:
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


limiter: RateLimitBackend = InMemoryRateLimiter()
