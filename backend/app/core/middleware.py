"""HTTP middleware: request id, secure headers, body-size limit, rate limits, API access log.

Client IP (Phase 12B D21): the TCP peer address, unless the peer is one of TRUSTED_PROXIES — then the right-most X-Forwarded-For
address that is not itself a trusted proxy. X-Forwarded-For from any other source is ignored, so a client cannot choose its own IP for
rate limiting or audit. Uvicorn's own proxy-header handling is switched off (`--no-proxy-headers`) so this is the only interpretation.

Body size (F6): `BodySizeLimitMiddleware` refuses a declared Content-Length above MAX_REQUEST_BYTES before reading, and counts the
bytes actually received, so a chunked / undeclared body is cut off at the same limit (HTTP 413).
"""
import functools
import ipaddress
import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request, Response
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core import metrics
from app.core.config import get_settings
from app.core.context import set_request_id
from app.core.errors import envelope
from app.core.rate_limit import limiter

log = logging.getLogger("app.http")
Call = Callable[[Request], Awaitable[Response]]


@functools.lru_cache(maxsize=8)
def _trusted_networks(cidrs: tuple[str, ...]) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    return tuple(ipaddress.ip_network(c, strict=False) for c in cidrs)


def _is_trusted(addr: str, nets: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]) -> bool:
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return any(ip in n for n in nets)


def client_ip(request: Request) -> str | None:
    peer = request.client.host if request.client else None
    nets = _trusted_networks(tuple(get_settings().TRUSTED_PROXIES))
    if peer is None or not nets or not _is_trusted(peer, nets):
        return peer                                                  # X-Forwarded-For from an untrusted peer is ignored
    hops = [h.strip() for h in ",".join(request.headers.getlist("x-forwarded-for")).split(",") if h.strip()]
    for hop in reversed(hops):                                       # right-most first: appended by our own proxies
        try:
            ipaddress.ip_address(hop)
        except ValueError:
            return peer                                              # malformed chain: fall back to the proxy address
        if not _is_trusted(hop, nets):
            return hop
    return hops[0] if hops else peer


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Call) -> Response:
        incoming = request.headers.get("X-Request-ID", "")
        rid = incoming if 8 <= len(incoming) <= 64 and incoming.replace("-", "").isalnum() else str(uuid.uuid4())
        request.state.request_id = rid
        set_request_id(rid)
        request.state.user_id = None
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            _observe(request, 500, time.perf_counter() - started)
            raise
        response.headers["X-Request-ID"] = rid
        elapsed = time.perf_counter() - started
        duration_ms = int(elapsed * 1000)
        _observe(request, response.status_code, elapsed)
        writer = getattr(request.app.state, "access_log_writer", None)
        if writer and get_settings().API_ACCESS_LOG_ENABLED and request.url.path.startswith(get_settings().API_PREFIX) \
                and not _is_probe(request.url.path):
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


def _is_probe(path: str) -> bool:
    """Load-balancer probes: not rate limited and not written to api_access_logs (they would dominate both)."""
    return path.endswith(("/health/live", "/health/ready"))


def _route(request: Request) -> str:
    route = request.scope.get("route")
    return str(getattr(route, "path", None) or "unmatched")      # the template ("/farmers/{farmer_id}"), never raw ids


def _observe(request: Request, status: int, elapsed: float) -> None:
    """D43 / D44: API latency / error metrics and one structured log line per request (no query string, body or headers)."""
    route = _route(request)
    labels = {"method": request.method, "route": route, "status": f"{status // 100}xx"}
    metrics.inc("api_requests_total", labels)
    metrics.observe("api_request_duration_seconds", elapsed, {"method": request.method, "route": route})
    if status >= 500:
        metrics.inc("api_errors_total", {"method": request.method, "route": route, "status": str(status)})
    if _is_probe(request.url.path):
        return
    level = logging.ERROR if status >= 500 else logging.WARNING if status in (401, 403, 413, 429) else logging.INFO
    uid = getattr(request.state, "user_id", None)
    log.log(level, "request", extra={"fields": {"method": request.method, "route": route, "status": status,
                                                "duration_ms": int(elapsed * 1000), "user_id": str(uid) if uid else None}})


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
    """Coarse per-IP limit plus the deployment-wide API burst ceiling (D19). Per-user, per-organization and upload limits need the
    authenticated principal and are applied in `api.deps.get_principal`; refresh in `auth_service.refresh`."""

    async def dispatch(self, request: Request, call_next: Call) -> Response:
        s = get_settings()
        if request.url.path.startswith(s.API_PREFIX) and not _is_probe(request.url.path):
            ip = client_ip(request) or "unknown"
            if not limiter.hit(f"global:{ip}", s.GLOBAL_RATE_LIMIT_PER_MINUTE, 60) or \
                    not limiter.hit("burst:api", s.API_BURST_RATE_LIMIT_PER_MINUTE, 60):
                return envelope(request, 429, "RATE_LIMITED", "Too many requests. Please try again later.",
                                headers={"Retry-After": "60"})
        return await call_next(request)


class BodySizeLimitMiddleware:
    """F6: pure ASGI, so it sees the raw body stream (chunked transfer included)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = get_settings().MAX_REQUEST_BYTES
        declared = dict(scope.get("headers") or []).get(b"content-length")
        if declared is not None and (not declared.isdigit() or int(declared) > limit):
            await _too_large(scope, send)
            return
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:                     # surfaced by FastAPI as HTTP 413 -> PAYLOAD_TOO_LARGE envelope
                    raise StarletteHTTPException(413, "The request body is too large.")
            return message

        await self.app(scope, limited_receive, send)


async def _too_large(scope: Scope, send: Send) -> None:
    rid: Any = (scope.get("state") or {}).get("request_id")
    body = json.dumps({"success": False, "error_code": "PAYLOAD_TOO_LARGE", "message": "The request body is too large.",
                       "details": {}, "request_id": rid}).encode()
    await send({"type": "http.response.start", "status": 413,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()),
                            (b"connection", b"close")]})
    await send({"type": "http.response.body", "body": body})


def install_middleware(app: FastAPI) -> None:
    # Starlette runs the last-added middleware first: RequestContext must wrap everything.
    app.add_middleware(BodySizeLimitMiddleware)
    app.add_middleware(LimitsMiddleware)
    app.add_middleware(SecureHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)
