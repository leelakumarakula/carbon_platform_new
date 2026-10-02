"""Audit trail writer (spec section 35, rule 8).

Audit rows are added to the caller's session so they commit atomically with the
business change they describe. Never put secrets (password hashes, tokens) in values.
"""
import json
import uuid
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session

from app.core.context import RequestContext
from app.core.state_machine import StateMachine
from app.models import AuditLog, SecurityEvent, WorkflowEvent

SENSITIVE_FIELDS = frozenset({"password", "password_hash", "token", "token_hash", "mfa_secret_ref", "refresh_token"})


class AuditAction:
    LOGIN_SUCCEEDED = "LOGIN_SUCCEEDED"
    LOGOUT = "LOGOUT"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"  # noqa: S105 (audit action name, not a secret)
    PASSWORD_RESET = "PASSWORD_RESET"  # noqa: S105
    USER_CREATED = "USER_CREATED"
    USER_UPDATED = "USER_UPDATED"
    USER_STATUS_CHANGED = "USER_STATUS_CHANGED"
    USER_UNLOCKED = "USER_UNLOCKED"
    ROLE_ASSIGNED = "ROLE_ASSIGNED"
    ROLE_REVOKED = "ROLE_REVOKED"
    ROLE_CREATED = "ROLE_CREATED"
    ROLE_UPDATED = "ROLE_UPDATED"
    ROLE_PERMISSIONS_CHANGED = "ROLE_PERMISSIONS_CHANGED"
    ORGANIZATION_CREATED = "ORGANIZATION_CREATED"
    ORGANIZATION_UPDATED = "ORGANIZATION_UPDATED"
    ORGANIZATION_STATUS_CHANGED = "ORGANIZATION_STATUS_CHANGED"
    MEMBER_ADDED = "ORGANIZATION_MEMBER_ADDED"
    MEMBER_REMOVED = "ORGANIZATION_MEMBER_REMOVED"
    SESSION_REVOKED = "SESSION_REVOKED"


def _default(o: Any) -> Any:
    if isinstance(o, (uuid.UUID, Decimal)):
        return str(o)
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if isinstance(o, Enum):
        return o.value
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    raise TypeError(f"not JSON serialisable: {type(o).__name__}")


def to_json(data: dict[str, Any] | None) -> str | None:
    if data is None:
        return None
    clean = {k: v for k, v in data.items() if k not in SENSITIVE_FIELDS}
    return json.dumps(clean, default=_default, sort_keys=True, ensure_ascii=False)


def snapshot(obj: Any, fields: Iterable[str]) -> dict[str, Any]:
    return {f: getattr(obj, f) for f in fields if f not in SENSITIVE_FIELDS}


def record(db: Session, ctx: RequestContext, action: str, entity_type: str, entity_id: Any,
           old: dict[str, Any] | None = None, new: dict[str, Any] | None = None,
           reason: str | None = None, organization_id: uuid.UUID | None = None) -> AuditLog:
    row = AuditLog(user_id=ctx.user_id, organization_id=organization_id or ctx.organization_id, action=action,
                   entity_type=entity_type, entity_id=str(entity_id) if entity_id is not None else None,
                   old_value=to_json(old), new_value=to_json(new), reason=reason, request_id=ctx.request_id,
                   ip_address=ctx.ip_address, user_agent=ctx.user_agent)
    db.add(row)
    return row


def record_transition(db: Session, ctx: RequestContext, machine: StateMachine, entity_id: Any,
                      from_status: str | None, to_status: str, action: str, reason: str | None = None,
                      organization_id: uuid.UUID | None = None) -> None:
    """Validate a status change against the machine and log it as workflow event + audit row."""
    if from_status is not None:
        machine.assert_transition(from_status, to_status)
    db.add(WorkflowEvent(entity_type=machine.entity_type, entity_id=str(entity_id), from_status=from_status,
                         to_status=to_status, user_id=ctx.user_id, reason=reason, request_id=ctx.request_id))
    record(db, ctx, action, machine.entity_type, entity_id, {"status": from_status}, {"status": to_status},
           reason, organization_id)


def security_event(db: Session, ctx: RequestContext, event_type: str, severity: str = "WARNING",
                   user_id: uuid.UUID | None = None, details: dict[str, Any] | None = None) -> None:
    db.add(SecurityEvent(event_type=event_type, severity=severity, user_id=user_id or ctx.user_id,
                         ip_address=ctx.ip_address, details=to_json(details), request_id=ctx.request_id))
