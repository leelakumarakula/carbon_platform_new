"""Read side of audit, workflow events, login audit, security events and sessions."""
import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.audit.service import AuditAction, record
from app.core.context import RequestContext
from app.core.errors import NotFound, PermissionDenied
from app.models import AuditLog, LoginAudit, SecurityEvent, User, UserSession, WorkflowEvent
from app.models.base import utcnow
from app.repositories.common import paginate
from app.schemas.audit import AuditLogOut, LoginAuditOut, SecurityEventOut, SessionOut, WorkflowEventOut
from app.schemas.common import PageParams
from app.security.permissions import P
from app.security.principal import Principal
from app.services.auth_service import _revoke_session


def _j(v: str | None) -> dict | None:
    return json.loads(v) if v else None


def _between(stmt: Select[Any], col: Any, start: datetime | None, end: datetime | None) -> Select[Any]:
    if start:
        stmt = stmt.where(col >= start)
    if end:
        stmt = stmt.where(col <= end)
    return stmt


def list_audit(db: Session, principal: Principal, params: PageParams, *, entity_type: str | None,
               entity_id: str | None, action: str | None, user_id: uuid.UUID | None,
               organization_id: uuid.UUID | None, start: datetime | None, end: datetime | None
               ) -> tuple[list[AuditLogOut], int]:
    scope = principal.scope_for(P.AUDIT_READ)
    stmt = select(AuditLog)
    if scope is not None:
        stmt = stmt.where(AuditLog.organization_id.in_(list(scope)))
    for col, val in ((AuditLog.entity_type, entity_type), (AuditLog.entity_id, entity_id), (AuditLog.action, action),
                     (AuditLog.user_id, user_id), (AuditLog.organization_id, organization_id)):
        if val:
            stmt = stmt.where(col == val)
    stmt = _between(stmt, AuditLog.occurred_at, start, end)
    rows, total = paginate(db, stmt, params, {"occurred_at": AuditLog.occurred_at, "action": AuditLog.action},
                           "-occurred_at", AuditLog.id.desc())
    return audit_rows_out(db, rows), total


def audit_rows_out(db: Session, rows: Any) -> list[AuditLogOut]:
    emails = dict(db.execute(select(User.id, User.email).where(User.id.in_({r.user_id for r in rows if r.user_id})))
                  .tuples().all()) if rows else {}
    return [AuditLogOut(id=r.id, occurred_at=r.occurred_at, user_id=r.user_id, user_email=emails.get(r.user_id),
                        organization_id=r.organization_id, action=r.action, entity_type=r.entity_type,
                        entity_id=r.entity_id, old_value=_j(r.old_value), new_value=_j(r.new_value), reason=r.reason,
                        request_id=r.request_id, ip_address=r.ip_address) for r in rows]


def list_workflow_events(db: Session, principal: Principal, params: PageParams, *, entity_type: str | None,
                         entity_id: str | None) -> tuple[list[WorkflowEventOut], int]:
    if not principal.has_platform(P.AUDIT_READ):
        raise PermissionDenied(details={"required_permission": P.AUDIT_READ})
    stmt = select(WorkflowEvent)
    if entity_type:
        stmt = stmt.where(WorkflowEvent.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(WorkflowEvent.entity_id == entity_id)
    rows, total = paginate(db, stmt, params, {"occurred_at": WorkflowEvent.occurred_at}, "-occurred_at",
                           WorkflowEvent.id.desc())
    return [WorkflowEventOut.model_validate(r, from_attributes=True) for r in rows], total


def _require_security_read(principal: Principal) -> None:
    if not principal.has_platform(P.SECURITY_READ):
        raise PermissionDenied(details={"required_permission": P.SECURITY_READ})


def list_login_audit(db: Session, principal: Principal, params: PageParams, *, user_id: uuid.UUID | None,
                     success: bool | None, start: datetime | None, end: datetime | None) -> tuple[list[LoginAuditOut], int]:
    _require_security_read(principal)
    stmt = select(LoginAudit)
    if user_id:
        stmt = stmt.where(LoginAudit.user_id == user_id)
    if success is not None:
        stmt = stmt.where(LoginAudit.success == success)
    stmt = _between(stmt, LoginAudit.occurred_at, start, end)
    rows, total = paginate(db, stmt, params, {"occurred_at": LoginAudit.occurred_at}, "-occurred_at", LoginAudit.id.desc())
    return [LoginAuditOut.model_validate(r, from_attributes=True) for r in rows], total


def list_security_events(db: Session, principal: Principal, params: PageParams, *, event_type: str | None,
                         severity: str | None) -> tuple[list[SecurityEventOut], int]:
    _require_security_read(principal)
    stmt = select(SecurityEvent)
    if event_type:
        stmt = stmt.where(SecurityEvent.event_type == event_type)
    if severity:
        stmt = stmt.where(SecurityEvent.severity == severity)
    rows, total = paginate(db, stmt, params, {"occurred_at": SecurityEvent.occurred_at}, "-occurred_at",
                           SecurityEvent.id.desc())
    return [SecurityEventOut(id=r.id, occurred_at=r.occurred_at, event_type=r.event_type, severity=r.severity,
                             user_id=r.user_id, ip_address=r.ip_address, details=_j(r.details),
                             request_id=r.request_id) for r in rows], total


def list_sessions(db: Session, principal: Principal, params: PageParams, *, user_id: uuid.UUID | None,
                  active_only: bool) -> tuple[list[SessionOut], int]:
    _require_security_read(principal)
    now = utcnow()
    stmt = select(UserSession)
    if user_id:
        stmt = stmt.where(UserSession.user_id == user_id)
    if active_only:
        stmt = stmt.where(UserSession.revoked_at.is_(None), UserSession.expires_at > now)
    rows, total = paginate(db, stmt, params, {"created_at": UserSession.created_at, "last_seen_at": UserSession.last_seen_at},
                           "-last_seen_at", UserSession.id)
    emails = (dict(db.execute(select(User.id, User.email).where(User.id.in_({r.user_id for r in rows}))).tuples().all())
              if rows else {})
    return [SessionOut(id=r.id, user_id=r.user_id, user_email=emails.get(r.user_id, ""), created_at=r.created_at,
                       last_seen_at=r.last_seen_at, expires_at=r.expires_at, revoked_at=r.revoked_at,
                       revoked_reason=r.revoked_reason, ip_address=r.ip_address, user_agent=r.user_agent,
                       is_active=r.is_active(now)) for r in rows], total


def revoke_session(db: Session, ctx: RequestContext, principal: Principal, session_id: uuid.UUID, reason: str) -> None:
    if not principal.has_platform(P.SECURITY_MANAGE):
        raise PermissionDenied(details={"required_permission": P.SECURITY_MANAGE})
    s = db.get(UserSession, session_id)
    if s is None:
        raise NotFound("Session not found.", error_code="SESSION_NOT_FOUND")
    _revoke_session(db, s, "ADMIN_REVOKED", utcnow())
    record(db, ctx, AuditAction.SESSION_REVOKED, "session", s.id, None, {"user_id": s.user_id}, reason)
    db.commit()
