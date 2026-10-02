"""Audit tables (spec sections 7.15 and 35). Append-only: enforced by DB triggers (see migration 0001)."""
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Index, Integer, Unicode, UnicodeText, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow

APPEND_ONLY_TABLES = ("audit_logs", "workflow_events", "login_audit", "security_events")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        CheckConstraint("old_value IS NULL OR ISJSON(old_value) = 1", name="old_value_json"),
        CheckConstraint("new_value IS NULL OR ISJSON(new_value) = 1", name="new_value_json"),
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
        Index("ix_audit_logs_occurred_at", "occurred_at"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    user_id: Mapped[uuid.UUID | None]
    organization_id: Mapped[uuid.UUID | None]
    action: Mapped[str] = mapped_column(Unicode(80), index=True)
    entity_type: Mapped[str] = mapped_column(Unicode(60))
    entity_id: Mapped[str | None] = mapped_column(Unicode(64))
    old_value: Mapped[str | None] = mapped_column(UnicodeText)
    new_value: Mapped[str | None] = mapped_column(UnicodeText)
    reason: Mapped[str | None] = mapped_column(Unicode(1000))
    request_id: Mapped[str | None] = mapped_column(Unicode(64))
    ip_address: Mapped[str | None] = mapped_column(Unicode(64))
    user_agent: Mapped[str | None] = mapped_column(Unicode(400))


class WorkflowEvent(Base):
    __tablename__ = "workflow_events"
    __table_args__ = (Index("ix_workflow_events_entity", "entity_type", "entity_id"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"))
    entity_type: Mapped[str] = mapped_column(Unicode(60))
    entity_id: Mapped[str] = mapped_column(Unicode(64))
    from_status: Mapped[str | None] = mapped_column(Unicode(40))
    to_status: Mapped[str] = mapped_column(Unicode(40))
    user_id: Mapped[uuid.UUID | None]
    reason: Mapped[str | None] = mapped_column(Unicode(1000))
    request_id: Mapped[str | None] = mapped_column(Unicode(64))


class LoginAudit(Base):
    __tablename__ = "login_audit"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    email_attempted: Mapped[str] = mapped_column(Unicode(320))
    success: Mapped[bool] = mapped_column(Boolean)
    failure_reason: Mapped[str | None] = mapped_column(Unicode(60))
    ip_address: Mapped[str | None] = mapped_column(Unicode(64))
    user_agent: Mapped[str | None] = mapped_column(Unicode(400))
    request_id: Mapped[str | None] = mapped_column(Unicode(64))


class SecurityEvent(Base):
    __tablename__ = "security_events"
    __table_args__ = (
        CheckConstraint("severity IN ('INFO', 'WARNING', 'CRITICAL')", name="severity"),
        CheckConstraint("details IS NULL OR ISJSON(details) = 1", name="details_json"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"), index=True)
    event_type: Mapped[str] = mapped_column(Unicode(60), index=True)
    severity: Mapped[str] = mapped_column(Unicode(10))
    user_id: Mapped[uuid.UUID | None]
    ip_address: Mapped[str | None] = mapped_column(Unicode(64))
    details: Mapped[str | None] = mapped_column(UnicodeText)
    request_id: Mapped[str | None] = mapped_column(Unicode(64))


class ApiAccessLog(Base):
    """High-volume operational log; not append-only-enforced so retention jobs can purge it."""
    __tablename__ = "api_access_logs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=text("SYSUTCDATETIME()"), index=True)
    request_id: Mapped[str] = mapped_column(Unicode(64))
    method: Mapped[str] = mapped_column(Unicode(10))
    path: Mapped[str] = mapped_column(Unicode(400))
    status_code: Mapped[int] = mapped_column(Integer)
    duration_ms: Mapped[int] = mapped_column(Integer)
    user_id: Mapped[uuid.UUID | None]
    ip_address: Mapped[str | None] = mapped_column(Unicode(64))
    user_agent: Mapped[str | None] = mapped_column(Unicode(400))
