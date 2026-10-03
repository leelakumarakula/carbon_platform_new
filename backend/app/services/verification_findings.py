"""Phase 8B VVB findings and corrective actions (C13, C14). The VVB raises, closes, returns and reopens; the project responds (never closes).

- finding: OPEN → RESPONDED → CLOSED; RESPONDED → OPEN (response returned); CLOSED → OPEN (reopened, reason required).
  Six categories, `blocking` flag; the target must lie inside the submitted package
- corrective action (on a finding): REQUESTED → RESPONDED → ACCEPTED; RESPONDED → REQUESTED (rejected); REQUESTED / RESPONDED →
  CANCELLED. Overdue is derived (REQUESTED past its due date), never stored
- every change writes an append-only event (actor, organization, side) and an audit row in both organizations
- findings belong to one submission: they are worked while that submission is current; a superseded / invalidated submission keeps them
  as history (a new package is reviewed afresh)
"""
import uuid
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.context import RequestContext
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.models import (
    CorrectiveAction,
    CorrectiveActionEvent,
    Organization,
    Project,
    VerificationAssignment,
    VerificationFinding,
    VerificationFindingEvent,
    VerificationSubmission,
)
from app.models.base import utcnow
from app.models.documents import DocumentCategory
from app.models.verification import OPEN_CA_STATUSES, TARGET_TYPES, VFINDING_CATEGORIES
from app.repositories.sequences import next_code
from app.security.permissions import P
from app.security.principal import Principal
from app.services import document_service
from app.services import verification_access as va
from app.services import verification_package as vp
from app.services import verification_service as vs
from app.services.workflows import CORRECTIVE_ACTION_MACHINE, VERIFICATION_FINDING_MACHINE


def _finding_nf() -> NotFound:
    return NotFound("Verification finding not found.", error_code="VERIFICATION_FINDING_NOT_FOUND")


def _ca_nf() -> NotFound:
    return NotFound("Corrective action not found.", error_code="CORRECTIVE_ACTION_NOT_FOUND")


# ---------------------------------------------------------------- lookups
def vvb_finding(db: Session, principal: Principal, finding_id: uuid.UUID, code: str
                ) -> tuple[VerificationFinding, VerificationSubmission, VerificationAssignment, Project, Organization]:
    f = db.get(VerificationFinding, finding_id)
    if f is None:
        raise _finding_nf()
    try:
        s, a, p, org = va.vvb_submission(db, principal, f.submission_id, code)
    except NotFound:
        raise _finding_nf() from None
    return f, s, a, p, org


def project_finding(db: Session, principal: Principal, finding_id: uuid.UUID, *codes: str
                    ) -> tuple[VerificationFinding, VerificationSubmission, VerificationAssignment, Project]:
    f = db.get(VerificationFinding, finding_id)
    if f is None:
        raise _finding_nf()
    try:
        s, a, p = va.project_submission(db, principal, f.submission_id, *codes)
    except NotFound:
        raise _finding_nf() from None
    return f, s, a, p


def vvb_ca(db: Session, principal: Principal, ca_id: uuid.UUID, code: str
           ) -> tuple[CorrectiveAction, VerificationFinding, VerificationSubmission, VerificationAssignment, Project]:
    c = db.get(CorrectiveAction, ca_id)
    if c is None:
        raise _ca_nf()
    try:
        f, s, a, p, _ = vvb_finding(db, principal, c.finding_id, code)
    except NotFound:
        raise _ca_nf() from None
    return c, f, s, a, p


def project_ca(db: Session, principal: Principal, ca_id: uuid.UUID, *codes: str
               ) -> tuple[CorrectiveAction, VerificationFinding, VerificationSubmission, VerificationAssignment, Project]:
    c = db.get(CorrectiveAction, ca_id)
    if c is None:
        raise _ca_nf()
    try:
        f, s, a, p = project_finding(db, principal, c.finding_id, *codes)
    except NotFound:
        raise _ca_nf() from None
    return c, f, s, a, p


def findings_of(db: Session, submission_id: uuid.UUID) -> list[VerificationFinding]:
    return list(db.scalars(select(VerificationFinding).where(VerificationFinding.submission_id == submission_id)
                           .order_by(VerificationFinding.raised_at)).all())


def findings_of_assignment(db: Session, assignment_id: uuid.UUID) -> list[VerificationFinding]:
    return list(db.scalars(select(VerificationFinding).where(VerificationFinding.assignment_id == assignment_id)
                           .order_by(VerificationFinding.raised_at)).all())


def finding_events(db: Session, finding_id: uuid.UUID) -> list[VerificationFindingEvent]:
    return list(db.scalars(select(VerificationFindingEvent).where(VerificationFindingEvent.finding_id == finding_id)
                           .order_by(VerificationFindingEvent.seq)).all())


def cas_of(db: Session, finding_id: uuid.UUID) -> list[CorrectiveAction]:
    return list(db.scalars(select(CorrectiveAction).where(CorrectiveAction.finding_id == finding_id).order_by(CorrectiveAction.requested_at)).all())


def ca_events(db: Session, ca_id: uuid.UUID) -> list[CorrectiveActionEvent]:
    return list(db.scalars(select(CorrectiveActionEvent).where(CorrectiveActionEvent.corrective_action_id == ca_id)
                           .order_by(CorrectiveActionEvent.seq)).all())


def is_overdue(c: CorrectiveAction, today: date | None = None) -> bool:
    return c.status == "REQUESTED" and c.due_date is not None and c.due_date < (today or utcnow().date())


# ---------------------------------------------------------------- guards
def _current(s: VerificationSubmission, a: VerificationAssignment) -> None:
    if a.status != "ACCEPTED":
        raise Conflict(f"The assignment is {a.status}; findings can only be worked on an ACCEPTED assignment.", error_code="ASSIGNMENT_NOT_ACCEPTED")
    if s.status != "SUBMITTED":
        raise Conflict(f"The submission is {s.status}; findings are worked on the current submission only.", error_code="SUBMISSION_NOT_CURRENT")


def _refreshed(db: Session, ctx: RequestContext, s: VerificationSubmission, a: VerificationAssignment) -> None:
    vs.refresh(db, ctx, a)
    db.refresh(s)
    _current(s, a)


def upload_evidence(db: Session, ctx: RequestContext, principal: Principal, submission_id: uuid.UUID, filename: str | None, data: bytes,
                    title: str | None) -> Any:
    """Project evidence for a response (PDF, category VERIFICATION_EVIDENCE), attached to the submission so the VVB may read it."""
    s, a, p = va.project_submission(db, principal, submission_id, P.VERIFICATION_RESPOND)
    _refreshed(db, ctx, s, a)
    doc = document_service.create_document(db, ctx, entity_type=vs.SUBMISSION_ENTITY, entity_id=s.id, organization_id=p.organization_id,
                                           environment=s.environment, category=DocumentCategory.VERIFICATION_EVIDENCE.value,
                                           title=title or f"Verification evidence ({s.submission_code})", filename=filename, data=data)
    va.audit(db, ctx, principal, "VERIFICATION_EVIDENCE_UPLOADED", vs.SUBMISSION_ENTITY, s.id, a, p,
             {"document_id": doc.id, "submission_code": s.submission_code})
    db.commit()
    return doc


def _evidence(db: Session, s: VerificationSubmission, document_id: uuid.UUID | None) -> uuid.UUID | None:
    doc = document_service.require_attached(db, document_id, vs.SUBMISSION_ENTITY, s.id, {DocumentCategory.VERIFICATION_EVIDENCE.value})
    return doc.id if doc else None


def _f_event(db: Session, principal: Principal, f: VerificationFinding, a: VerificationAssignment, p: Project, action: str, frm: str | None,
             to: str, side: str, note: str | None, document_id: uuid.UUID | None = None) -> None:
    seq = (db.scalar(select(func.max(VerificationFindingEvent.seq)).where(VerificationFindingEvent.finding_id == f.id)) or 0) + 1
    db.add(VerificationFindingEvent(finding_id=f.id, seq=seq, action=action, from_status=frm, to_status=to, actor_id=principal.user_id,
                                    actor_org_id=a.vvb_organization_id if side == "VVB" else p.organization_id, actor_side=side,
                                    note=note, document_id=document_id))


def _ca_event(db: Session, principal: Principal, c: CorrectiveAction, a: VerificationAssignment, p: Project, action: str, frm: str | None,
              to: str, side: str, note: str | None, document_id: uuid.UUID | None = None) -> None:
    seq = (db.scalar(select(func.max(CorrectiveActionEvent.seq)).where(CorrectiveActionEvent.corrective_action_id == c.id)) or 0) + 1
    db.add(CorrectiveActionEvent(corrective_action_id=c.id, seq=seq, action=action, from_status=frm, to_status=to, actor_id=principal.user_id,
                                 actor_org_id=a.vvb_organization_id if side == "VVB" else p.organization_id, actor_side=side,
                                 note=note, document_id=document_id))


def _f_move(db: Session, ctx: RequestContext, principal: Principal, f: VerificationFinding, a: VerificationAssignment, p: Project, to: str,
            event: str, audit_action: str, side: str, note: str | None, document_id: uuid.UUID | None = None) -> None:
    frm = f.status
    VERIFICATION_FINDING_MACHINE.assert_transition(frm, to)
    f.status = to
    _f_event(db, principal, f, a, p, event, frm, to, side, note, document_id)
    va.workflow(db, ctx, "verification_finding", f.id, frm, to, note)
    va.audit(db, ctx, principal, audit_action, "verification_finding", f.id, a, p,
             {"finding_code": f.finding_code, "status": to, "submission_id": f.submission_id, "document_id": document_id}, note, side,
             {"status": frm})


def _ca_move(db: Session, ctx: RequestContext, principal: Principal, c: CorrectiveAction, a: VerificationAssignment, p: Project, to: str,
             event: str, audit_action: str, side: str, note: str | None, document_id: uuid.UUID | None = None) -> None:
    frm = c.status
    CORRECTIVE_ACTION_MACHINE.assert_transition(frm, to)
    c.status = to
    _ca_event(db, principal, c, a, p, event, frm, to, side, note, document_id)
    va.workflow(db, ctx, "corrective_action", c.id, frm, to, note)
    va.audit(db, ctx, principal, audit_action, "corrective_action", c.id, a, p,
             {"action_code": c.action_code, "status": to, "finding_id": c.finding_id, "document_id": document_id}, note, side, {"status": frm})


# ---------------------------------------------------------------- findings (VVB raises / closes; project responds)
def raise_finding(db: Session, ctx: RequestContext, principal: Principal, submission_id: uuid.UUID, data: Any) -> VerificationFinding:
    s, a, p, _ = va.vvb_submission(db, principal, submission_id, P.VERIFICATION_VVB_REVIEW)
    _refreshed(db, ctx, s, a)
    if data.category not in VFINDING_CATEGORIES:
        raise ValidationFailed("Unknown finding category.", error_code="INVALID_CATEGORY")
    if data.target_type not in TARGET_TYPES:
        raise ValidationFailed("Unknown finding target type.", error_code="INVALID_TARGET")
    ref = data.target_ref.strip() if data.target_ref else None
    if not vp.target_ok(db, s, data.target_type, ref):
        raise ValidationFailed("The finding target is not part of the submitted package.", error_code="TARGET_NOT_IN_PACKAGE")
    f = VerificationFinding(finding_code=next_code(db, "verification_finding", utcnow().year), assignment_id=a.id, submission_id=s.id,
                            category=data.category, blocking=data.blocking, title=data.title.strip(), description=data.description.strip(),
                            target_type=data.target_type, target_ref=ref, status="OPEN", raised_by=principal.user_id, environment=s.environment)
    db.add(f)
    db.flush()
    _f_event(db, principal, f, a, p, "RAISED", None, "OPEN", "VVB", f.description)
    va.workflow(db, ctx, "verification_finding", f.id, None, "OPEN", None)
    va.audit(db, ctx, principal, "VERIFICATION_FINDING_RAISED", "verification_finding", f.id, a, p,
             {"finding_code": f.finding_code, "category": f.category, "blocking": f.blocking, "target_type": f.target_type,
              "target_ref": f.target_ref, "submission_id": s.id, "status": "OPEN"}, None, "VVB")
    db.commit()
    return f


def respond(db: Session, ctx: RequestContext, principal: Principal, finding_id: uuid.UUID, text: str,
            document_id: uuid.UUID | None = None) -> VerificationFinding:
    f, s, a, p = project_finding(db, principal, finding_id, P.VERIFICATION_RESPOND)
    _refreshed(db, ctx, s, a)
    if f.status != "OPEN":
        raise Conflict(f"Only an OPEN finding can be answered (it is {f.status}).", error_code="FINDING_NOT_OPEN")
    doc_id = _evidence(db, s, document_id)
    f.response_text, f.response_document_id, f.responded_by, f.responded_at = text, doc_id, principal.user_id, utcnow()
    _f_move(db, ctx, principal, f, a, p, "RESPONDED", "RESPONDED", "VERIFICATION_FINDING_RESPONDED", "PROJECT", text, doc_id)
    db.commit()
    return f


def close(db: Session, ctx: RequestContext, principal: Principal, finding_id: uuid.UUID, note: str) -> VerificationFinding:
    f, s, a, p, _ = vvb_finding(db, principal, finding_id, P.VERIFICATION_VVB_REVIEW)
    _refreshed(db, ctx, s, a)
    if f.status != "RESPONDED":
        raise Conflict(f"Only a RESPONDED finding can be closed (it is {f.status}).", error_code="FINDING_NOT_RESPONDED")
    pending = [c.action_code for c in cas_of(db, f.id) if c.status in OPEN_CA_STATUSES]
    if pending:
        raise Conflict("Accept or cancel the finding's corrective actions first.", error_code="OPEN_CORRECTIVE_ACTIONS",
                       details={"corrective_actions": pending})
    f.closure_note, f.closed_by, f.closed_at = note, principal.user_id, utcnow()
    _f_move(db, ctx, principal, f, a, p, "CLOSED", "CLOSED", "VERIFICATION_FINDING_CLOSED", "VVB", note)
    db.commit()
    return f


def return_response(db: Session, ctx: RequestContext, principal: Principal, finding_id: uuid.UUID, reason: str) -> VerificationFinding:
    f, s, a, p, _ = vvb_finding(db, principal, finding_id, P.VERIFICATION_VVB_REVIEW)
    _refreshed(db, ctx, s, a)
    if f.status != "RESPONDED":
        raise Conflict(f"Only a RESPONDED finding can be returned (it is {f.status}).", error_code="FINDING_NOT_RESPONDED")
    _f_move(db, ctx, principal, f, a, p, "OPEN", "RETURNED", "VERIFICATION_FINDING_RETURNED", "VVB", reason)
    db.commit()
    return f


def reopen(db: Session, ctx: RequestContext, principal: Principal, finding_id: uuid.UUID, reason: str) -> VerificationFinding:
    f, s, a, p, _ = vvb_finding(db, principal, finding_id, P.VERIFICATION_VVB_REVIEW)
    _refreshed(db, ctx, s, a)
    if f.status != "CLOSED":
        raise Conflict(f"Only a CLOSED finding can be reopened (it is {f.status}).", error_code="FINDING_NOT_CLOSED")
    _f_move(db, ctx, principal, f, a, p, "OPEN", "REOPENED", "VERIFICATION_FINDING_REOPENED", "VVB", reason)
    db.commit()
    return f


# ---------------------------------------------------------------- corrective actions
def request_ca(db: Session, ctx: RequestContext, principal: Principal, finding_id: uuid.UUID, description: str,
               due_date: date | None) -> CorrectiveAction:
    f, s, a, p, _ = vvb_finding(db, principal, finding_id, P.VERIFICATION_VVB_REVIEW)
    _refreshed(db, ctx, s, a)
    if f.status == "CLOSED":
        raise Conflict("A corrective action needs an open finding (reopen it first).", error_code="FINDING_CLOSED")
    c = CorrectiveAction(action_code=next_code(db, "corrective_action", utcnow().year), finding_id=f.id, submission_id=s.id, assignment_id=a.id,
                         description=description.strip(), due_date=due_date, status="REQUESTED", requested_by=principal.user_id,
                         environment=s.environment)
    db.add(c)
    db.flush()
    _ca_event(db, principal, c, a, p, "REQUESTED", None, "REQUESTED", "VVB", c.description)
    va.workflow(db, ctx, "corrective_action", c.id, None, "REQUESTED", None)
    va.audit(db, ctx, principal, "CORRECTIVE_ACTION_REQUESTED", "corrective_action", c.id, a, p,
             {"action_code": c.action_code, "finding_id": f.id, "finding_code": f.finding_code, "due_date": due_date, "status": "REQUESTED"},
             None, "VVB")
    db.commit()
    return c


def respond_ca(db: Session, ctx: RequestContext, principal: Principal, ca_id: uuid.UUID, text: str,
               document_id: uuid.UUID | None = None) -> CorrectiveAction:
    c, f, s, a, p = project_ca(db, principal, ca_id, P.VERIFICATION_RESPOND)
    _refreshed(db, ctx, s, a)
    if c.status != "REQUESTED":
        raise Conflict(f"Only a REQUESTED corrective action can be answered (it is {c.status}).", error_code="CORRECTIVE_ACTION_NOT_REQUESTED")
    doc_id = _evidence(db, s, document_id)
    c.response_text, c.response_document_id, c.responded_by, c.responded_at = text, doc_id, principal.user_id, utcnow()
    _ca_move(db, ctx, principal, c, a, p, "RESPONDED", "RESPONDED", "CORRECTIVE_ACTION_RESPONDED", "PROJECT", text, doc_id)
    db.commit()
    return c


def review_ca(db: Session, ctx: RequestContext, principal: Principal, ca_id: uuid.UUID, accept: bool, note: str) -> CorrectiveAction:
    c, f, s, a, p = vvb_ca(db, principal, ca_id, P.VERIFICATION_VVB_REVIEW)
    _refreshed(db, ctx, s, a)
    if c.status != "RESPONDED":
        raise Conflict(f"Only a RESPONDED corrective action can be reviewed (it is {c.status}).", error_code="CORRECTIVE_ACTION_NOT_RESPONDED")
    c.reviewed_by, c.reviewed_at, c.review_note = principal.user_id, utcnow(), note
    if accept:
        _ca_move(db, ctx, principal, c, a, p, "ACCEPTED", "ACCEPTED", "CORRECTIVE_ACTION_ACCEPTED", "VVB", note)
    else:
        _ca_move(db, ctx, principal, c, a, p, "REQUESTED", "REJECTED", "CORRECTIVE_ACTION_REJECTED", "VVB", note)
    db.commit()
    return c


def cancel_ca(db: Session, ctx: RequestContext, principal: Principal, ca_id: uuid.UUID, reason: str) -> CorrectiveAction:
    c, f, s, a, p = vvb_ca(db, principal, ca_id, P.VERIFICATION_VVB_REVIEW)
    _refreshed(db, ctx, s, a)
    if c.status not in OPEN_CA_STATUSES:
        raise Conflict(f"The corrective action is already {c.status}.", error_code="CORRECTIVE_ACTION_CLOSED")
    _ca_move(db, ctx, principal, c, a, p, "CANCELLED", "CANCELLED", "CORRECTIVE_ACTION_CANCELLED", "VVB", reason)
    db.commit()
    return c
