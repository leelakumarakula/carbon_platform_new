"""Per-request context used for audit logging and the error envelope."""
import uuid
from contextvars import ContextVar
from dataclasses import dataclass

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def current_request_id() -> str | None:
    return _request_id.get()


def set_request_id(value: str) -> None:
    _request_id.set(value)


@dataclass(frozen=True)
class RequestContext:
    """Who is acting, from where. Passed explicitly into services so audit rows are complete."""
    request_id: str | None = None
    user_id: uuid.UUID | None = None
    organization_id: uuid.UUID | None = None
    ip_address: str | None = None
    user_agent: str | None = None

    @classmethod
    def system(cls, request_id: str | None = None) -> "RequestContext":
        return cls(request_id=request_id or f"system-{uuid.uuid4()}")
