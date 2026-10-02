"""FastAPI dependencies: DB session, current principal, permission checks, request context."""
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Query, Request, UploadFile
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.context import RequestContext
from app.core.database import get_db
from app.core.errors import AuthenticationFailed, PermissionDenied
from app.core.middleware import client_ip
from app.models import User, UserSession, UserStatus
from app.models.base import utcnow
from app.schemas.common import PageParams
from app.security.principal import Principal, load_principal
from app.security.tokens import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{get_settings().API_PREFIX}/auth/token", auto_error=False)

DB = Annotated[Session, Depends(get_db)]


def get_principal(request: Request, db: DB, token: Annotated[str | None, Depends(oauth2_scheme)]) -> Principal:
    if not token:
        raise AuthenticationFailed()
    claims = decode_access_token(token)
    session = db.get(UserSession, claims.session_id)
    if session is None or session.user_id != claims.user_id or not session.is_active(utcnow()):
        raise AuthenticationFailed("Your session has ended. Please sign in again.", error_code="SESSION_REVOKED")
    user = db.get(User, claims.user_id)
    if user is None or user.status != UserStatus.ACTIVE.value or user.is_locked():
        raise AuthenticationFailed("This account is not active.", error_code="ACCOUNT_INACTIVE")
    request.state.user_id = user.id
    return load_principal(db, user, session.id)


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]


def require(*codes: str) -> Callable[..., Principal]:
    """Route dependency: caller must hold every listed permission (in at least one scope)."""
    def _check(principal: CurrentPrincipal) -> Principal:
        if principal.user.must_change_password:
            raise PermissionDenied("You must change your temporary password before continuing.",
                                   error_code="PASSWORD_CHANGE_REQUIRED")
        missing = [c for c in codes if not principal.has(c)]
        if missing:
            raise PermissionDenied(details={"missing_permissions": missing})
        return principal
    return _check


def require_any(*codes: str) -> Callable[..., Principal]:
    """Route dependency: caller must hold at least one of the listed permissions. Record-level checks follow in services."""
    def _check(principal: CurrentPrincipal) -> Principal:
        if principal.user.must_change_password:
            raise PermissionDenied("You must change your temporary password before continuing.",
                                   error_code="PASSWORD_CHANGE_REQUIRED")
        if not any(principal.has(c) for c in codes):
            raise PermissionDenied(details={"required_any_of": list(codes)})
        return principal
    return _check


def read_upload(file: UploadFile) -> bytes:
    """Read an uploaded file (sync routes run in the threadpool), never buffering more than MAX_UPLOAD_BYTES + 1."""
    limit = get_settings().MAX_UPLOAD_BYTES
    data = file.file.read(limit + 1)
    if len(data) > limit:
        from app.core.errors import ValidationFailed
        raise ValidationFailed(f"The file is larger than {limit // (1024 * 1024)} MB.", error_code="FILE_TOO_LARGE",
                               details={"max_bytes": limit})
    return data


def active_principal(principal: CurrentPrincipal) -> Principal:
    """Signed in and not blocked by a temporary password. Record-level access is checked in services."""
    if principal.user.must_change_password:
        raise PermissionDenied("You must change your temporary password before continuing.", error_code="PASSWORD_CHANGE_REQUIRED")
    return principal


ActivePrincipal = Annotated[Principal, Depends(active_principal)]


def get_ctx(request: Request, principal: CurrentPrincipal) -> RequestContext:
    return RequestContext(request_id=getattr(request.state, "request_id", None), user_id=principal.user_id,
                          ip_address=client_ip(request), user_agent=(request.headers.get("user-agent") or "")[:400])


def get_anonymous_ctx(request: Request) -> RequestContext:
    return RequestContext(request_id=getattr(request.state, "request_id", None), ip_address=client_ip(request),
                          user_agent=(request.headers.get("user-agent") or "")[:400])


Ctx = Annotated[RequestContext, Depends(get_ctx)]
AnonCtx = Annotated[RequestContext, Depends(get_anonymous_ctx)]


def page_params(page: Annotated[int, Query(ge=1)] = 1,
                page_size: Annotated[int, Query(ge=1, le=100)] = 25,
                sort: Annotated[str | None, Query(max_length=40, pattern=r"^-?[a-z_]+$")] = None) -> PageParams:
    return PageParams(page=page, page_size=page_size, sort=sort)


Paging = Annotated[PageParams, Depends(page_params)]
