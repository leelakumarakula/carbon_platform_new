"""Field-level protection for personal data.

- encrypt()/decrypt(): Fernet (AES-128-CBC + HMAC-SHA256) for values that must be recoverable
  server-side (bank account numbers for payouts). Never returned in full by the API.
  Phase 12B D30 key rotation: MultiFernet over DATA_ENCRYPTION_KEY (encrypts) + DATA_ENCRYPTION_PREVIOUS_KEYS (still decrypt);
  `needs_rotation()` / `rotate()` drive `manage.py rotate-data-key`, which re-encrypts stored values with the current key.
- fingerprint(): keyed HMAC-SHA256 for values that only need equality checks (KYC ID duplicates).
  The raw identity number itself is never stored.
"""
import hashlib
import hmac
import re
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core.config import get_settings


@lru_cache
def _fernet() -> MultiFernet:
    s = get_settings()
    return MultiFernet([Fernet(k.encode("ascii")) for k in [s.DATA_ENCRYPTION_KEY, *s.DATA_ENCRYPTION_PREVIOUS_KEYS]])


@lru_cache
def _primary() -> Fernet:
    return Fernet(get_settings().DATA_ENCRYPTION_KEY.encode("ascii"))


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as e:  # wrong key or tampered value
        raise ValueError("encrypted value cannot be decrypted with the configured key") from e


def needs_rotation(token: str) -> bool:
    """True when the value is not encrypted with the current DATA_ENCRYPTION_KEY (but decrypts with a previous key)."""
    try:
        _primary().decrypt(token.encode("ascii"))
        return False
    except InvalidToken:
        return True


def rotate(token: str) -> str:
    """Re-encrypt with the current key (MultiFernet.rotate). Raises ValueError if no configured key can decrypt it."""
    try:
        return _fernet().rotate(token.encode("ascii")).decode("ascii")
    except InvalidToken as e:
        raise ValueError("encrypted value cannot be decrypted with any configured key") from e


def normalise_identifier(value: str) -> str:
    """Upper-case and drop spaces/hyphens so '1234 5678-9012' and '123456789012' match."""
    return re.sub(r"[\s\-./]", "", value).upper()


def fingerprint(value: str, purpose: str) -> str:
    key = hashlib.sha256(f"{purpose}:{get_settings().SECRET_KEY}".encode()).digest()
    return hmac.new(key, normalise_identifier(value).encode("utf-8"), hashlib.sha256).hexdigest()


def last4(value: str) -> str:
    v = normalise_identifier(value)
    return v[-4:] if len(v) >= 4 else v
