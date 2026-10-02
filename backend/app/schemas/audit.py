"""Schemas for audit, security events, login audit and sessions."""
import uuid
from typing import Any

from pydantic import BaseModel

from app.schemas.common import UtcDatetime


class AuditLogOut(BaseModel):
    id: int
    occurred_at: UtcDatetime
    user_id: uuid.UUID | None
    user_email: str | None
    organization_id: uuid.UUID | None
    action: str
    entity_type: str
    entity_id: str | None
    old_value: dict[str, Any] | None
    new_value: dict[str, Any] | None
    reason: str | None
    request_id: str | None
    ip_address: str | None


class WorkflowEventOut(BaseModel):
    id: int
    occurred_at: UtcDatetime
    entity_type: str
    entity_id: str
    from_status: str | None
    to_status: str
    user_id: uuid.UUID | None
    reason: str | None
    request_id: str | None


class LoginAuditOut(BaseModel):
    id: int
    occurred_at: UtcDatetime
    user_id: uuid.UUID | None
    email_attempted: str
    success: bool
    failure_reason: str | None
    ip_address: str | None


class SecurityEventOut(BaseModel):
    id: int
    occurred_at: UtcDatetime
    event_type: str
    severity: str
    user_id: uuid.UUID | None
    ip_address: str | None
    details: dict[str, Any] | None
    request_id: str | None


class SessionOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    user_email: str
    created_at: UtcDatetime
    last_seen_at: UtcDatetime
    expires_at: UtcDatetime
    revoked_at: UtcDatetime | None
    revoked_reason: str | None
    ip_address: str | None
    user_agent: str | None
    is_active: bool
