import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.deps import DB, Ctx, Paging, require
from app.schemas.audit import AuditLogOut, LoginAuditOut, SecurityEventOut, SessionOut, WorkflowEventOut
from app.schemas.common import Message, Page, Reason
from app.security.permissions import P
from app.security.principal import Principal
from app.services import audit_query_service as svc

router = APIRouter(prefix="/admin", tags=["admin: audit & security"])

CanAudit = Annotated[Principal, Depends(require(P.AUDIT_READ))]
CanSecRead = Annotated[Principal, Depends(require(P.SECURITY_READ))]
CanSecManage = Annotated[Principal, Depends(require(P.SECURITY_MANAGE))]


class ReasonBody(BaseModel):
    reason: Reason


@router.get("/audit-logs", response_model=Page[AuditLogOut])
def audit_logs(principal: CanAudit, db: DB, paging: Paging,
               entity_type: Annotated[str | None, Query(max_length=60)] = None,
               entity_id: Annotated[str | None, Query(max_length=64)] = None,
               action: Annotated[str | None, Query(max_length=80)] = None,
               user_id: uuid.UUID | None = None, organization_id: uuid.UUID | None = None,
               start: datetime | None = Query(default=None, alias="from"),
               end: datetime | None = Query(default=None, alias="to")) -> Page[AuditLogOut]:
    rows, total = svc.list_audit(db, principal, paging, entity_type=entity_type, entity_id=entity_id, action=action,
                                 user_id=user_id, organization_id=organization_id, start=start, end=end)
    return Page(items=rows, total=total, page=paging.page, page_size=paging.page_size)


@router.get("/workflow-events", response_model=Page[WorkflowEventOut])
def workflow_events(principal: CanAudit, db: DB, paging: Paging, entity_type: str | None = None,
                    entity_id: str | None = None) -> Page[WorkflowEventOut]:
    rows, total = svc.list_workflow_events(db, principal, paging, entity_type=entity_type, entity_id=entity_id)
    return Page(items=rows, total=total, page=paging.page, page_size=paging.page_size)


@router.get("/security/login-audit", response_model=Page[LoginAuditOut])
def login_audit(principal: CanSecRead, db: DB, paging: Paging, user_id: uuid.UUID | None = None,
                success: bool | None = None,
                start: datetime | None = Query(default=None, alias="from"),
                end: datetime | None = Query(default=None, alias="to")) -> Page[LoginAuditOut]:
    rows, total = svc.list_login_audit(db, principal, paging, user_id=user_id, success=success, start=start, end=end)
    return Page(items=rows, total=total, page=paging.page, page_size=paging.page_size)


@router.get("/security/events", response_model=Page[SecurityEventOut])
def security_events(principal: CanSecRead, db: DB, paging: Paging, event_type: str | None = None,
                    severity: Literal["INFO", "WARNING", "CRITICAL"] | None = None) -> Page[SecurityEventOut]:
    rows, total = svc.list_security_events(db, principal, paging, event_type=event_type, severity=severity)
    return Page(items=rows, total=total, page=paging.page, page_size=paging.page_size)


@router.get("/security/sessions", response_model=Page[SessionOut])
def sessions(principal: CanSecRead, db: DB, paging: Paging, user_id: uuid.UUID | None = None,
             active_only: bool = True) -> Page[SessionOut]:
    rows, total = svc.list_sessions(db, principal, paging, user_id=user_id, active_only=active_only)
    return Page(items=rows, total=total, page=paging.page, page_size=paging.page_size)


@router.post("/security/sessions/{session_id}/revoke", response_model=Message)
def revoke_session(session_id: uuid.UUID, body: ReasonBody, principal: CanSecManage, db: DB, ctx: Ctx) -> Message:
    svc.revoke_session(db, ctx, principal, session_id, body.reason)
    return Message(message="Session revoked.")
