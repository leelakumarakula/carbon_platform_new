"""Phase 8B cross-organization access (C8, C10, C12) — the laboratory pattern, applied to VVBs.

VVB users hold `verification.vvb_*` / `verification.decide` only in their VVB organization. They reach project data exclusively through
an assignment of that organization: VVB org (type VVB, ACTIVE, same environment) + assignment + project + period (+ the submission).
Everything else is 404 (existence is never revealed). Project users act through `verification.read / manage / respond` in the project's
organization. Cross-organization actions are audited in both organizations (as for laboratories); the VVB never reads audit logs.
"""
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.audit.service import record
from app.core.context import RequestContext
from app.core.errors import NotFound, PermissionDenied
from app.models import Organization, Project, VerificationAssignment, VerificationSubmission, WorkflowEvent
from app.repositories import projects as project_repo
from app.security.permissions import P
from app.security.principal import Principal

PROJECT_VISIBLE = (P.VERIFICATION_READ, P.VERIFICATION_MANAGE, P.VERIFICATION_RESPOND)
VVB_CODES = (P.VERIFICATION_VVB_READ, P.VERIFICATION_VVB_REVIEW, P.VERIFICATION_DECIDE)
VVB_VISIBLE_STATES = ("PROPOSED", "ACCEPTED", "COMPLETED")
VVB_PACKAGE_STATES = ("ACCEPTED", "COMPLETED")


def assignment_nf() -> NotFound:
    return NotFound("Verification assignment not found.", error_code="ASSIGNMENT_NOT_FOUND")


def submission_nf() -> NotFound:
    return NotFound("Verification submission not found.", error_code="SUBMISSION_NOT_FOUND")


# ---------------------------------------------------------------- project side
def project_for(db: Session, principal: Principal, project_id: uuid.UUID, *codes: str) -> Project:
    p = project_repo.get(db, project_id)
    if p is None:
        raise NotFound("Project not found.", error_code="PROJECT_NOT_FOUND")
    needed = codes or (P.VERIFICATION_READ,)
    if any(principal.can_in_org(c, p.organization_id) for c in needed):
        return p
    if any(principal.can_in_org(c, p.organization_id) for c in PROJECT_VISIBLE):
        raise PermissionDenied(details={"required_permission": " or ".join(needed)})
    raise NotFound("Project not found.", error_code="PROJECT_NOT_FOUND")


def project_assignment(db: Session, principal: Principal, assignment_id: uuid.UUID, *codes: str) -> tuple[VerificationAssignment, Project]:
    a = db.get(VerificationAssignment, assignment_id)
    if a is None:
        raise assignment_nf()
    try:
        return a, project_for(db, principal, a.project_id, *codes)
    except NotFound:
        raise assignment_nf() from None


def project_submission(db: Session, principal: Principal, submission_id: uuid.UUID, *codes: str
                       ) -> tuple[VerificationSubmission, VerificationAssignment, Project]:
    s = db.get(VerificationSubmission, submission_id)
    if s is None:
        raise submission_nf()
    try:
        a, p = project_assignment(db, principal, s.assignment_id, *codes)
    except NotFound:
        raise submission_nf() from None
    return s, a, p


# ---------------------------------------------------------------- VVB side
def vvb_org_ok(db: Session, org_id: uuid.UUID, environment: str) -> Organization | None:
    org = db.get(Organization, org_id)
    if org is None or org.org_type != "VVB" or org.status != "ACTIVE" or org.environment != environment:
        return None
    return org


def vvb_assignment(db: Session, principal: Principal, assignment_id: uuid.UUID, code: str,
                   states: tuple[str, ...] = VVB_VISIBLE_STATES) -> tuple[VerificationAssignment, Project, Organization]:
    """The assignment if the caller holds `code` in its (active, same-environment) VVB organization and the state allows; else 404/403."""
    a = db.get(VerificationAssignment, assignment_id)
    if a is None:
        raise assignment_nf()
    p = db.get(Project, a.project_id)
    org = vvb_org_ok(db, a.vvb_organization_id, a.environment)
    if p is None or org is None or p.environment != a.environment:
        raise assignment_nf()
    if not principal.can_in_org(code, org.id):
        if any(principal.can_in_org(c, org.id) for c in VVB_CODES) and a.status in states:
            raise PermissionDenied(details={"required_permission": code})
        raise assignment_nf()
    if a.status not in states:
        raise assignment_nf()
    return a, p, org


def vvb_submission(db: Session, principal: Principal, submission_id: uuid.UUID, code: str
                   ) -> tuple[VerificationSubmission, VerificationAssignment, Project, Organization]:
    s = db.get(VerificationSubmission, submission_id)
    if s is None:
        raise submission_nf()
    try:
        a, p, org = vvb_assignment(db, principal, s.assignment_id, code, VVB_PACKAGE_STATES)
    except NotFound:
        raise submission_nf() from None
    return s, a, p, org


# ---------------------------------------------------------------- audit (both organizations, laboratory precedent)
def audit(db: Session, ctx: RequestContext, principal: Principal | None, action: str, entity_type: str, entity_id: Any, a: VerificationAssignment,
          p: Project, payload: dict[str, Any], reason: str | None = None, side: str = "PROJECT", old: dict[str, Any] | None = None) -> None:
    actor_org = a.vvb_organization_id if side == "VVB" else p.organization_id
    full = {**payload, "actor_side": side, "actor_org_id": actor_org, "project_id": p.id, "monitoring_period_id": a.monitoring_period_id,
            "vvb_organization_id": a.vvb_organization_id, "assignment_id": a.id, "assignment_code": a.assignment_code}
    for org in (p.organization_id, a.vvb_organization_id):
        record(db, ctx, action, entity_type, entity_id, old, full, reason, organization_id=org)


def workflow(db: Session, ctx: RequestContext, entity_type: str, entity_id: Any, frm: str | None, to: str, reason: str | None) -> None:
    db.add(WorkflowEvent(entity_type=entity_type, entity_id=str(entity_id), from_status=frm, to_status=to, user_id=ctx.user_id, reason=reason,
                         request_id=ctx.request_id))


def document_resolver(db: Session, principal: Principal, submission_id: uuid.UUID, kind: str) -> None:
    """Documents attached to a verification submission (VVB report, project evidence): readable by the project organization
    (verification.*) or the assigned VVB organization (assignment ACCEPTED / COMPLETED). They are never changed after upload (no new
    versions through the generic documents API): new evidence is a new document, and the decision keeps its report hash."""
    nf = NotFound("Document not found.", error_code="DOCUMENT_NOT_FOUND")
    if kind == "manage":
        raise PermissionDenied("Verification documents are immutable; upload a new document instead.", error_code="DOCUMENT_IMMUTABLE")
    s = db.get(VerificationSubmission, submission_id)
    a = db.get(VerificationAssignment, s.assignment_id) if s else None
    p = db.get(Project, a.project_id) if a else None
    if s is None or a is None or p is None:
        raise nf
    if any(principal.can_in_org(c, p.organization_id) for c in PROJECT_VISIBLE):
        return
    org = vvb_org_ok(db, a.vvb_organization_id, a.environment)
    if org is not None and a.status in VVB_PACKAGE_STATES and any(principal.can_in_org(c, org.id) for c in VVB_CODES):
        return
    raise nf
