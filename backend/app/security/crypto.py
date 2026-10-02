"""Field-level protection for personal data.

- encrypt()/decrypt(): Fernet (AES-128-CBC + HMAC-SHA256) for values that must be recoverable
  server-side (bank account numbers for payouts). Never returned in full by the API.
- fingerprint(): keyed HMAC-SHA256 for values that only need equality checks (KYC ID duplicates).
  The raw identity number itself is never stored.
"""
import hashlib
import hmac
import re
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


@lru_cache
def _fernet() -> Fernet:
    return Fernet(get_settings().DATA_ENCRYPTION_KEY.encode("ascii"))


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as e:  # wrong key or tampered value
        raise ValueError("encrypted value cannot be decrypted with the configured key") from e


def normalise_identifier(value: str) -> str:
    """Upper-case and drop spaces/hyphens so '1234 5678-9012' and '123456789012' match."""
    return re.sub(r"[\s\-./]", "", value).upper()


def fingerprint(value: str, purpose: str) -> str:
    key = hashlib.sha256(f"{purpose}:{get_settings().SECRET_KEY}".encode()).digest()
    return hmac.new(key, normalise_identifier(value).encode("utf-8"), hashlib.sha256).hexdigest()


def last4(value: str) -> str:
    v = normalise_identifier(value)
    return v[-4:] if len(v) >= 4 else v
