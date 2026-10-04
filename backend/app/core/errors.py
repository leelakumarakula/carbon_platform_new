"""Domain errors and the standard error envelope (spec section 44).

{ "success": false, "error_code": "...", "message": "...", "details": {}, "request_id": "..." }
"""
import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("app.errors")


class AppError(Exception):
    status_code = 400
    error_code = "BAD_REQUEST"
    message = "The request could not be processed."

    def __init__(self, message: str | None = None, *, error_code: str | None = None,
                 details: dict[str, Any] | None = None, status_code: int | None = None) -> None:
        self.message = message or self.message
        self.error_code = error_code or self.error_code
        self.status_code = status_code or self.status_code
        self.details = details or {}
        super().__init__(self.message)


class AuthenticationFailed(AppError):
    status_code, error_code, message = 401, "AUTHENTICATION_FAILED", "Authentication is required."


class PermissionDenied(AppError):
    status_code, error_code, message = 403, "PERMISSION_DENIED", "You do not have permission to perform this action."


class NotFound(AppError):
    status_code, error_code, message = 404, "NOT_FOUND", "The requested record was not found."


class Conflict(AppError):
    status_code, error_code, message = 409, "CONFLICT", "The request conflicts with the current state."


class InvalidTransition(AppError):
    status_code, error_code, message = 409, "INVALID_STATUS_TRANSITION", "This status change is not permitted."


class ValidationFailed(AppError):
    status_code, error_code, message = 422, "VALIDATION_FAILED", "The submitted data is invalid."


class ServiceUnavailable(AppError):
    status_code, error_code, message = 503, "SERVICE_UNAVAILABLE", "A required service is temporarily unavailable. Please try again later."


class RateLimited(AppError):
    status_code, error_code, message = 429, "RATE_LIMITED", "Too many requests. Please try again later."


def envelope(request: Request, status: int, code: str, message: str,
             details: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"success": False, "error_code": code, "message": message, "details": details or {},
                 "request_id": getattr(request.state, "request_id", None)},
        headers=headers,
    )


_HTTP_CODES = {400: "BAD_REQUEST", 401: "AUTHENTICATION_FAILED", 403: "PERMISSION_DENIED", 404: "NOT_FOUND",
               405: "METHOD_NOT_ALLOWED", 409: "CONFLICT", 413: "PAYLOAD_TOO_LARGE", 429: "RATE_LIMITED"}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else \
            {"Retry-After": "60"} if exc.status_code == 429 else None
        return envelope(request, exc.status_code, exc.error_code, exc.message, exc.details, headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"field": ".".join(str(p) for p in e.get("loc", []) if p != "body"),
                   "message": e.get("msg"), "type": e.get("type")} for e in exc.errors()]
        return envelope(request, 422, "VALIDATION_FAILED", "The submitted data is invalid.", {"errors": errors})

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODES.get(exc.status_code, "HTTP_ERROR")
        msg = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return envelope(request, exc.status_code, code, msg)

    @app.exception_handler(IntegrityError)
    async def _integrity(request: Request, exc: IntegrityError) -> JSONResponse:
        # Services check state first; a unique / foreign-key / check violation reaching here is a concurrent change (409, not 500).
        # The SQL text and parameters are never returned.
        log.warning("Integrity conflict (request_id=%s): %s", getattr(request.state, "request_id", None), type(exc.orig).__name__)
        return envelope(request, 409, "CONCURRENT_CONFLICT",
                        "The record was changed by another request at the same time. Reload and try again.")

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("Unhandled error (request_id=%s)", getattr(request.state, "request_id", None))
        return envelope(request, 500, "INTERNAL_ERROR",
                        "An unexpected error occurred. Please contact support with the request ID.")
