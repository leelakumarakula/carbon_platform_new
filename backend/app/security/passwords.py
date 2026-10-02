"""Password hashing (bcrypt) and password policy."""
import re

import bcrypt

from app.core.errors import ValidationFailed

MIN_LENGTH = 12
MAX_BYTES = 72  # bcrypt limit


def validate_password_policy(password: str) -> None:
    problems: list[str] = []
    if len(password) < MIN_LENGTH:
        problems.append(f"at least {MIN_LENGTH} characters")
    if len(password.encode("utf-8")) > MAX_BYTES:
        problems.append(f"at most {MAX_BYTES} bytes")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        problems.append("at least one letter and one digit")
    if password.strip() != password:
        problems.append("no leading or trailing spaces")
    if problems:
        raise ValidationFailed("Password does not meet the policy: " + "; ".join(problems) + ".",
                               error_code="PASSWORD_POLICY", details={"requirements": problems})


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:MAX_BYTES], password_hash.encode("ascii"))
    except ValueError:
        return False


# Used to keep login timing similar when the email does not exist.
DUMMY_HASH = hash_password("timing-equaliser-not-a-real-password-1")
