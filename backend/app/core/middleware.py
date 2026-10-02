"""HTTP middleware: request id, secure headers, body-size limit, global rate limit, API access log."""
import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.core.context import set_request_id
from app.core.errors import envelope
from app.core.rate_limit import limiter

log = logging.getLogger("app.http")
Call = Callable[[Request], Awaitable[Response]]


def client_ip(request: Request) -> str | None:
    # Behind a trusted reverse proxy configure uvicorn --proxy-headers so request.client is correct.
    return request.client.host if request.client else None


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Call) -> Response:
        incoming = request.headers.get("X-Request-ID", "")
        rid = incoming if 8 <= len(incoming) <= 64 and incoming.replace("-", "").isalnum() else str(uuid.uuid4())
        request.state.request_id = rid
        set_request_id(rid)
        request.state.user_id = None
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        duration_ms = int((time.perf_counter() - started) * 1000)
        writer = getattr(request.app.state, "access_log_writer", None)
        if writer and get_settings().API_ACCESS_LOG_ENABLED and request.url.path.startswith(get_settings().API_PREFIX):
            try:
                await run_in_threadpool(writer, {
                    "request_id": rid, "method": request.method, "path": request.url.path[:400],
                    "status_code": response.status_code, "duration_ms": duration_ms,
                    "user_id": getattr(request.state, "user_id", None), "ip_address": client_ip(request),
                    "user_agent": (request.headers.get("user-agent") or "")[:400],
                })
            except Exception:  # access logging must never break a request
                log.exception("Failed to write api access log")
        return response


class SecureHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Call) -> Response:
        response = await call_next(request)
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "no-referrer")
        h.setdefault("Permissions-Policy", "geolocation=(), camera=(), microphone=()")
        if request.url.path.startswith(get_settings().API_PREFIX):
            h.setdefault("Cache-Control", "no-store")
            h.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        if get_settings().is_production:
            h.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
        return response


class LimitsMiddleware(BaseHTTPMiddleware):
    """Rejects oversized bodies (by Content-Length) and applies a coarse per-IP rate limit."""

    async def dispatch(self, request: Request, call_next: Call) -> Response:
        s = get_settings()
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > s.MAX_REQUEST_BYTES:
            return envelope(request, 413, "PAYLOAD_TOO_LARGE", "The request body is too large.")
        ip = client_ip(request) or "unknown"
        if request.url.path.startswith(s.API_PREFIX) and not limiter.hit(f"global:{ip}", s.GLOBAL_RATE_LIMIT_PER_MINUTE, 60):
            return envelope(request, 429, "RATE_LIMITED", "Too many requests. Please try again later.",
                            headers={"Retry-After": "60"})
        return await call_next(request)


def install_middleware(app: FastAPI) -> None:
    # Starlette runs the last-added middleware first: RequestContext must wrap everything.
    app.add_middleware(LimitsMiddleware)
    app.add_middleware(SecureHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)
