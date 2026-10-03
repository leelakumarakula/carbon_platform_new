"""Authentication: login with lockout, rotating refresh tokens with reuse detection, logout, password change."""
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.audit.service import AuditAction, record, security_event
from app.core.config import get_settings
from app.core.context import RequestContext
from app.core.errors import AuthenticationFailed, RateLimited, ValidationFailed
from app.core.rate_limit import limiter
from app.models import LoginAudit, RefreshToken, User, UserSession, UserStatus
from app.models.base import utcnow
from app.repositories import identity as repo
from app.security.passwords import DUMMY_HASH, hash_password, validate_password_policy, verify_password
from app.security.tokens import create_access_token, hash_refresh_token, new_refresh_token, refresh_expiry

INVALID_CREDENTIALS = "Invalid email or password, or the account is temporarily locked."


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    expires_in: int
    refresh_token: str
    refresh_expires_at: object
    user: User
    session_id: uuid.UUID
    refresh_token_id: uuid.UUID


def _issue(db: Session, user: User, session: UserSession) -> IssuedTokens:
    now = utcnow()
    raw, digest = new_refresh_token()
    rt = RefreshToken(session_id=session.id, user_id=user.id, token_hash=digest, issued_at=now,
                      expires_at=min(refresh_expiry(now), session.expires_at))
    db.add(rt)
    db.flush()
    access, ttl = create_access_token(user.id, session.id)
    return IssuedTokens(access, ttl, raw, rt.expires_at, user, session.id, rt.id)


def _login_audit(db: Session, ctx: RequestContext, email: str, user: User | None, ok: bool, reason: str | None) -> None:
    db.add(LoginAudit(user_id=user.id if user else None, email_attempted=email[:320], success=ok,
                      failure_reason=reason, ip_address=ctx.ip_address, user_agent=ctx.user_agent,
                      request_id=ctx.request_id))


def login(db: Session, ctx: RequestContext, email: str, password: str) -> IssuedTokens:
    s = get_settings()
    email = email.lower()
    ip = ctx.ip_address or "unknown"
    if not limiter.hit(f"login:{ip}", s.LOGIN_RATE_LIMIT_PER_MINUTE, 60) or \
            not limiter.hit(f"login:{ip}:{email}", s.LOGIN_RATE_LIMIT_PER_MINUTE, 60):
        security_event(db, ctx, "LOGIN_RATE_LIMITED", "WARNING", details={"email": email})
        _login_audit(db, ctx, email, None, False, "RATE_LIMITED")
        db.commit()
        raise RateLimited("Too many sign-in attempts. Please wait a minute and try again.")

    user = repo.get_user_by_email(db, email)
    now = utcnow()

    def fail(reason: str) -> AuthenticationFailed:
        _login_audit(db, ctx, email, user, False, reason)
        db.commit()
        return AuthenticationFailed(INVALID_CREDENTIALS, error_code="INVALID_CREDENTIALS")

    if user is None:
        verify_password(password, DUMMY_HASH)  # keep timing similar to a real check
        raise fail("UNKNOWN_EMAIL")
    password_ok = verify_password(password, user.password_hash)
    if user.is_locked(now):
        raise fail("ACCOUNT_LOCKED")
    if user.status != UserStatus.ACTIVE.value:
        raise fail(f"ACCOUNT_{user.status}")
    if not password_ok:
        user.failed_login_count += 1
        if user.failed_login_count >= s.MAX_FAILED_LOGINS:
            user.locked_until = now + timedelta(minutes=s.LOCKOUT_MINUTES)
            user.failed_login_count = 0
            security_event(db, ctx, "ACCOUNT_LOCKED", "WARNING", user.id,
                           {"reason": "too many failed sign-in attempts", "locked_minutes": s.LOCKOUT_MINUTES})
        raise fail("BAD_PASSWORD")

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    session = UserSession(user_id=user.id, created_at=now, last_seen_at=now,
                          expires_at=now + timedelta(days=s.REFRESH_TOKEN_DAYS),
                          ip_address=ctx.ip_address, user_agent=ctx.user_agent)
    db.add(session)
    db.flush()
    tokens = _issue(db, user, session)
    _login_audit(db, ctx, email, user, True, None)
    record(db, RequestContext(ctx.request_id, user.id, None, ctx.ip_address, ctx.user_agent),
           AuditAction.LOGIN_SUCCEEDED, "session", session.id)
    db.commit()
    return tokens


def refresh(db: Session, ctx: RequestContext, raw_token: str | None) -> IssuedTokens:
    # F5 / D19: dedicated per-IP refresh limit (reuse detection and rotation below are unchanged)
    if not limiter.hit(f"refresh:{ctx.ip_address or 'unknown'}", get_settings().REFRESH_RATE_LIMIT_PER_MINUTE, 60):
        raise RateLimited("Too many session refreshes. Please wait a minute and try again.")
    if not raw_token:
        raise AuthenticationFailed("No refresh token was provided.", error_code="REFRESH_MISSING")
    now = utcnow()
    rt = db.scalars(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token))
                    .with_for_update()).first()
    if rt is None:
        raise AuthenticationFailed("The refresh token is invalid.", error_code="REFRESH_INVALID")
    session = db.get(UserSession, rt.session_id)
    assert session is not None
    if rt.used_at is not None or rt.revoked_at is not None:
        # A rotated token was presented again: assume theft and kill the whole session.
        _revoke_session(db, session, "REFRESH_TOKEN_REUSE", now)
        security_event(db, ctx, "REFRESH_TOKEN_REUSE", "CRITICAL", rt.user_id, {"session_id": str(session.id)})
        db.commit()
        raise AuthenticationFailed("This session has been revoked for your security. Please sign in again.",
                                   error_code="REFRESH_REUSED")
    if rt.expires_at <= now or not session.is_active(now):
        raise AuthenticationFailed("Your session has expired. Please sign in again.", error_code="REFRESH_EXPIRED")
    user = db.get(User, rt.user_id)
    if user is None or user.status != UserStatus.ACTIVE.value or user.is_locked(now):
        raise AuthenticationFailed("This account is not active.", error_code="ACCOUNT_INACTIVE")
    rt.used_at = now
    session.last_seen_at = now
    tokens = _issue(db, user, session)
    rt.replaced_by_id = tokens.refresh_token_id
    db.commit()
    return tokens


def _revoke_session(db: Session, session: UserSession, reason: str, now: object) -> None:
    if session.revoked_at is None:
        session.revoked_at = now  # type: ignore[assignment]
        session.revoked_reason = reason
    db.execute(update(RefreshToken).where(RefreshToken.session_id == session.id, RefreshToken.revoked_at.is_(None))
               .values(revoked_at=now))


def revoke_user_sessions(db: Session, user_id: uuid.UUID, reason: str, except_session: uuid.UUID | None = None) -> int:
    now = utcnow()
    sessions = db.scalars(select(UserSession).where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))).all()
    count = 0
    for s in sessions:
        if s.id != except_session:
            _revoke_session(db, s, reason, now)
            count += 1
    return count


def logout(db: Session, ctx: RequestContext, session_id: uuid.UUID | None) -> None:
    if session_id is None:
        return
    session = db.get(UserSession, session_id)
    if session is None:
        return
    _revoke_session(db, session, "LOGOUT", utcnow())
    record(db, ctx, AuditAction.LOGOUT, "session", session.id)
    db.commit()


def logout_by_refresh(db: Session, ctx: RequestContext, raw_token: str | None) -> None:
    if not raw_token:
        return
    rt = db.scalars(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token))).first()
    if rt is not None:
        logout(db, RequestContext(ctx.request_id, rt.user_id, None, ctx.ip_address, ctx.user_agent), rt.session_id)


def change_password(db: Session, ctx: RequestContext, user: User, session_id: uuid.UUID | None,
                    current: str, new: str) -> None:
    if not verify_password(current, user.password_hash):
        security_event(db, ctx, "PASSWORD_CHANGE_FAILED", "INFO", user.id)
        db.commit()
        raise ValidationFailed("The current password is incorrect.", error_code="CURRENT_PASSWORD_INCORRECT")
    validate_password_policy(new)
    if verify_password(new, user.password_hash):
        raise ValidationFailed("The new password must be different from the current one.", error_code="PASSWORD_REUSED")
    user.password_hash = hash_password(new)
    user.must_change_password = False
    user.password_changed_at = utcnow()
    revoked = revoke_user_sessions(db, user.id, "PASSWORD_CHANGED", except_session=session_id)
    record(db, ctx, AuditAction.PASSWORD_CHANGED, "user", user.id, new={"other_sessions_revoked": revoked})
    db.commit()
