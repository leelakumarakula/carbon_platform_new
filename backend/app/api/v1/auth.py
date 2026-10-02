from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request, Response
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import DB, AnonCtx, Ctx, CurrentPrincipal
from app.core.config import get_settings
from app.repositories import identity as repo
from app.schemas.common import Message
from app.schemas.identity import ChangePasswordRequest, LoginRequest, MeOut, RefreshRequest, TokenResponse
from app.services import auth_service
from app.services.auth_service import IssuedTokens
from app.services.mappers import user_out

router = APIRouter(prefix="/auth", tags=["auth"])


def _cookie_path() -> str:
    return f"{get_settings().API_PREFIX}/auth"


def _respond(response: Response, t: IssuedTokens) -> TokenResponse:
    s = get_settings()
    response.set_cookie(s.REFRESH_COOKIE_NAME, t.refresh_token, httponly=True, secure=s.REFRESH_COOKIE_SECURE,
                        samesite="strict", path=_cookie_path(), max_age=s.REFRESH_TOKEN_DAYS * 86400)
    return TokenResponse(access_token=t.access_token, expires_in=t.expires_in,
                         must_change_password=t.user.must_change_password)


@router.post("/login", response_model=TokenResponse, summary="Sign in with email + password")
def login(body: LoginRequest, response: Response, db: DB, ctx: AnonCtx) -> TokenResponse:
    return _respond(response, auth_service.login(db, ctx, body.email, body.password))


@router.post("/token", response_model=TokenResponse, include_in_schema=True,
             summary="OAuth2 password flow (used by the Swagger 'Authorize' button)")
def token(form: Annotated[OAuth2PasswordRequestForm, Depends()], response: Response, db: DB, ctx: AnonCtx) -> TokenResponse:
    body = LoginRequest(email=form.username, password=form.password)
    return _respond(response, auth_service.login(db, ctx, body.email, body.password))


@router.post("/refresh", response_model=TokenResponse, summary="Rotate the refresh token and get a new access token")
def refresh(request: Request, response: Response, db: DB, ctx: AnonCtx,
            body: Annotated[RefreshRequest | None, Body()] = None) -> TokenResponse:
    raw = request.cookies.get(get_settings().REFRESH_COOKIE_NAME) or (body.refresh_token if body else None)
    return _respond(response, auth_service.refresh(db, ctx, raw))


@router.post("/logout", response_model=Message, summary="End the current session")
def logout(request: Request, response: Response, db: DB, ctx: AnonCtx,
           body: Annotated[RefreshRequest | None, Body()] = None) -> Message:
    raw = request.cookies.get(get_settings().REFRESH_COOKIE_NAME) or (body.refresh_token if body else None)
    auth_service.logout_by_refresh(db, ctx, raw)
    response.delete_cookie(get_settings().REFRESH_COOKIE_NAME, path=_cookie_path())
    return Message(message="Signed out.")


@router.get("/me", response_model=MeOut, summary="Current user, role grants and effective permissions")
def me(principal: CurrentPrincipal, db: DB) -> MeOut:
    user = repo.get_user(db, principal.user_id)
    assert user is not None
    platform = sorted({p for g in principal.grants if g.organization_id is None for p in g.permissions})
    return MeOut(user=user_out(user), permissions=sorted(principal.permissions), platform_permissions=platform)


@router.post("/change-password", response_model=Message, summary="Change own password (revokes other sessions)")
def change_password(body: ChangePasswordRequest, principal: CurrentPrincipal, db: DB, ctx: Ctx) -> Message:
    auth_service.change_password(db, ctx, principal.user, principal.session_id, body.current_password, body.new_password)
    return Message(message="Password changed. Other sessions were signed out.")
