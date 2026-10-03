"""Unit tests: state machine, password policy, tokens, permission scoping."""
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
import pytest

from app.core.config import get_settings
from app.core.errors import AuthenticationFailed, InvalidTransition, PermissionDenied, ValidationFailed
from app.core.state_machine import StateMachine
from app.security.passwords import hash_password, validate_password_policy, verify_password
from app.security.permissions import ALL_PERMISSION_CODES, SYSTEM_ROLES, P
from app.security.principal import Grant, Principal
from app.security.tokens import create_access_token, decode_access_token, hash_refresh_token, new_refresh_token
from app.services.workflows import ORGANIZATION_MACHINE, USER_MACHINE


# ---------- state machine ----------
def test_state_machine_allows_declared_transitions_only() -> None:
    m = StateMachine.build("thing", "A", {"A": {"B"}, "B": {"C"}}, terminal={"C"})
    m.assert_transition("A", "B")
    with pytest.raises(InvalidTransition) as e:
        m.assert_transition("A", "C")
    assert e.value.details["allowed"] == ["B"]
    with pytest.raises(InvalidTransition):
        m.assert_transition("C", "A")
    with pytest.raises(InvalidTransition):
        m.assert_transition("A", "NOPE")


def test_state_machine_rejects_terminal_with_outgoing() -> None:
    with pytest.raises(ValueError):
        StateMachine.build("bad", "A", {"A": {"B"}, "B": {"A"}}, terminal={"B"})


@pytest.mark.parametrize("frm,to,ok", [("ACTIVE", "SUSPENDED", True), ("SUSPENDED", "ACTIVE", True),
                                      ("ACTIVE", "DEACTIVATED", True), ("DEACTIVATED", "ACTIVE", False),
                                      ("ACTIVE", "ACTIVE", False)])
def test_user_machine(frm: str, to: str, ok: bool) -> None:
    assert USER_MACHINE.can(frm, to) is ok


def test_organization_machine_archived_is_terminal() -> None:
    assert ORGANIZATION_MACHINE.allowed_from("ARCHIVED") == frozenset()


# ---------- passwords ----------
@pytest.mark.parametrize("pw", ["short1", "allletterslongenough", "123456789012345", " LeadingSpace123", "x" * 70 + "1é"])
def test_password_policy_rejects(pw: str) -> None:
    with pytest.raises(ValidationFailed):
        validate_password_policy(pw)


def test_password_hash_roundtrip() -> None:
    h = hash_password("Valid-Password-123")
    assert h.startswith("$2b$") and verify_password("Valid-Password-123", h)
    assert not verify_password("wrong-Password-123", h)
    assert not verify_password("x", "not-a-hash")


# ---------- tokens ----------
def test_access_token_roundtrip() -> None:
    uid, sid = uuid.uuid4(), uuid.uuid4()
    token, ttl = create_access_token(uid, sid)
    claims = decode_access_token(token)
    assert (claims.user_id, claims.session_id) == (uid, sid) and ttl == get_settings().ACCESS_TOKEN_MINUTES * 60


def test_expired_token_rejected() -> None:
    token, _ = create_access_token(uuid.uuid4(), uuid.uuid4(), now=datetime.now(timezone.utc) - timedelta(hours=2))
    with pytest.raises(AuthenticationFailed) as e:
        decode_access_token(token)
    assert e.value.error_code == "TOKEN_EXPIRED"


def test_tampered_and_foreign_tokens_rejected() -> None:
    token, _ = create_access_token(uuid.uuid4(), uuid.uuid4())
    with pytest.raises(AuthenticationFailed):
        decode_access_token(token[:-3] + ("AAA" if not token.endswith("AAA") else "BBB"))
    s = get_settings()
    now = int(datetime.now(timezone.utc).timestamp())
    forged = jwt.encode({"sub": str(uuid.uuid4()), "sid": str(uuid.uuid4()), "typ": "access", "iss": s.JWT_ISSUER,
                         "iat": now, "exp": now + 60}, "another-secret-another-secret-another-secret", algorithm="HS256")
    with pytest.raises(AuthenticationFailed):
        decode_access_token(forged)
    wrong_type = jwt.encode({"sub": str(uuid.uuid4()), "sid": str(uuid.uuid4()), "typ": "refresh", "iss": s.JWT_ISSUER,
                             "iat": now, "exp": now + 60}, s.JWT_SECRET, algorithm="HS256")
    with pytest.raises(AuthenticationFailed):
        decode_access_token(wrong_type)


def test_refresh_token_only_hash_stored() -> None:
    raw, digest = new_refresh_token()
    assert len(raw) >= 60 and digest == hash_refresh_token(raw) and raw not in digest


# ---------- permissions / principal ----------
def test_catalog_consistency() -> None:
    assert len(SYSTEM_ROLES) == 21  # 19 spec roles + PLATFORM_GIS_SPECIALIST (D5) + MARKETPLACE_COMPLIANCE (Phase 10 D28)
    assert {r.code for r in SYSTEM_ROLES} >= {"FARMER", "VVB_REVIEWER", "BUYER", "PLATFORM_ADMIN", "SECURITY_ADMIN"}
    for r in SYSTEM_ROLES:
        assert r.permissions <= ALL_PERMISSION_CODES


def _principal(*grants: tuple[str | None, set[str]]) -> Principal:
    gs = tuple(Grant(uuid.uuid4(), "R", "X", uuid.UUID(o) if o else None, frozenset(p)) for o, p in grants)
    return Principal(user=SimpleNamespace(id=uuid.uuid4()), session_id=None, grants=gs)  # type: ignore[arg-type]


def test_principal_scope_platform_vs_org() -> None:
    org_a, org_b = str(uuid.uuid4()), str(uuid.uuid4())
    platform = _principal((None, {P.USERS_READ}))
    assert platform.scope_for(P.USERS_READ) is None
    scoped = _principal((org_a, {P.USERS_READ}), (org_b, {P.USERS_MANAGE}))
    assert scoped.scope_for(P.USERS_READ) == frozenset({uuid.UUID(org_a)})
    assert scoped.can_in_org(P.USERS_MANAGE, uuid.UUID(org_b)) and not scoped.can_in_org(P.USERS_MANAGE, uuid.UUID(org_a))
    assert not scoped.can_in_org(P.USERS_READ, None)
    with pytest.raises(PermissionDenied):
        scoped.scope_for(P.AUDIT_READ)
