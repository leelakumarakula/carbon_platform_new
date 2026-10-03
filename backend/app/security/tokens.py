"""JWT access tokens and opaque rotating refresh tokens.

Phase 12B D30 signing-key rotation: every access token carries the header `kid` = JWT_KEY_ID and is signed with JWT_SECRET. During a
rotation window, JWT_PREVIOUS_KEYS ("kid:secret") still verify the tokens they signed (at most ACCESS_TOKEN_MINUTES old). A token with
an unknown `kid` is invalid. The algorithm is fixed by configuration (no algorithm negotiation)."""
import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import get_settings
from app.core.errors import AuthenticationFailed


@dataclass(frozen=True)
class AccessClaims:
    user_id: uuid.UUID
    session_id: uuid.UUID
    expires_at: datetime


def create_access_token(user_id: uuid.UUID, session_id: uuid.UUID, now: datetime | None = None) -> tuple[str, int]:
    s = get_settings()
    now = now or datetime.now(timezone.utc)
    ttl = s.ACCESS_TOKEN_MINUTES * 60
    payload = {"sub": str(user_id), "sid": str(session_id), "typ": "access", "iss": s.JWT_ISSUER,
               "iat": int(now.timestamp()), "exp": int(now.timestamp()) + ttl, "jti": uuid.uuid4().hex}
    return jwt.encode(payload, s.JWT_SECRET, algorithm=s.JWT_ALGORITHM, headers={"kid": s.JWT_KEY_ID}), ttl


def _verification_key(token: str) -> str:
    s = get_settings()
    try:
        kid = jwt.get_unverified_header(token).get("kid")
    except jwt.InvalidTokenError as e:
        raise AuthenticationFailed("The access token is invalid.", error_code="TOKEN_INVALID") from e
    if kid is None or kid == s.JWT_KEY_ID:          # tokens issued before key ids existed verify with the current key only
        return s.JWT_SECRET
    previous = dict(e.split(":", 1) for e in s.JWT_PREVIOUS_KEYS)
    if not isinstance(kid, str) or kid not in previous:
        raise AuthenticationFailed("The access token is invalid.", error_code="TOKEN_INVALID")
    return previous[kid]


def decode_access_token(token: str) -> AccessClaims:
    s = get_settings()
    try:
        data = jwt.decode(token, _verification_key(token), algorithms=[s.JWT_ALGORITHM], issuer=s.JWT_ISSUER,
                          options={"require": ["exp", "iat", "sub", "sid", "iss"]})
    except jwt.ExpiredSignatureError as e:
        raise AuthenticationFailed("Your session has expired. Please sign in again.", error_code="TOKEN_EXPIRED") from e
    except jwt.InvalidTokenError as e:
        raise AuthenticationFailed("The access token is invalid.", error_code="TOKEN_INVALID") from e
    if data.get("typ") != "access":
        raise AuthenticationFailed("The access token is invalid.", error_code="TOKEN_INVALID")
    try:
        return AccessClaims(uuid.UUID(data["sub"]), uuid.UUID(data["sid"]),
                            datetime.fromtimestamp(data["exp"], timezone.utc))
    except ValueError as e:
        raise AuthenticationFailed("The access token is invalid.", error_code="TOKEN_INVALID") from e


def new_refresh_token() -> tuple[str, str]:
    """Returns (raw token for the client, sha256 hash to store)."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def refresh_expiry(now: datetime) -> datetime:
    return now + timedelta(days=get_settings().REFRESH_TOKEN_DAYS)
