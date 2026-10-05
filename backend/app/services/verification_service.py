"""Phase 8B verification workflow: assignments, submissions, decisions and the aggregate project status (C1–C7, C15, C16, C18, C20).

Verification only — no validation, registry, issuance or credits. The platform records the external VVB's decision; it never decides.
- assignment: PROPOSED → ACCEPTED → COMPLETED; PROPOSED → DECLINED / WITHDRAWN; ACCEPTED → TERMINATED; one open per project + period;
  the VVB accepts with a mandatory conflict-of-interest declaration; never reactivated (a replacement links the previous assignment)
- submission: requires an ACCEPTED assignment and a currently valid Phase 8A READY package of the same project + period (all Phase 8A
  prerequisites re-checked, manifest hash re-verified). SUBMITTED → SUPERSEDED (newer package) / INVALIDATED (package no longer valid,
  e.g. after a recalculation); a decision on an invalidated submission becomes SUPERSEDED — never mutated
- decision: VERIFIED / NOT_VERIFIED with the VVB report PDF; no open finding or corrective action; the decider never raised a finding on
  that submission; an optional "VVB-stated verified quantity" stays separate from the calculated quantity and is never a credit
- project status (aggregate only, C2): CALCULATED → VERIFICATION with the first ACCEPTED assignment (once a calculation is approved);
  VERIFICATION → VERIFIED with the first VERIFIED period. Period records stay authoritative
"""
import hashlib
import json
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calculation import framework as fw
from app.core.context import RequestContext
from app.core.errors import Conflict, NotFound, PermissionDenied, ValidationFailed
from app.models import (
    CalculationReadinessReview,
    CalculationRun,
    CorrectiveAction,
    MonitoringPeriod,
    Organization,
    Project,
    VerificationAssignment,
    VerificationDecision,
    VerificationFinding,
    VerificationSubmission,
)
from app.models.base import utcnow
from app.models.documents import DocumentCategory
from app.models.verification import OPEN_ASSIGNMENT_STATUSES, OPEN_CA_STATUSES
from app.repositories.sequences import next_code
from app.security.permissions import P
from app.security.principal import Principal
from app.services import calculation_readiness as cr
from app.services import calculation_report as crep
from app.services import document_service
from app.services import project_service as psvc
from app.services import verification_access as va
from app.services.workflows import VERIFICATION_ASSIGNMENT_MACHINE, VERIFICATION_SUBMISSION_MACHINE

SUBMISSION_ENTITY = "verification_submission"
document_service.register_resolver(SUBMISSION_ENTITY, va.document_resolver)


def _period(db: Session, p: Project, period_id: uuid.UUID) -> MonitoringPeriod:
    mp = db.get(MonitoringPeriod, period_id)
    if mp is None or mp.project_id != p.id:
        raise NotFound("Monitoring period not found.", error_code="PERIOD_NOT_FOUND")
    return mp


def vvb_organizations(db: Session, principal: Principal, project_id: uuid.UUID) -> list[Organization]:
    p = va.project_for(db, principal, project_id)
    return list(db.scalars(select(Organization).where(Organization.org_type == "VVB", Organization.status == "ACTIVE",
                                                      Organization.environment == p.environment).order_by(Organization.name)).all())


def assignments(db: Session, principal: Principal, project_id: uuid.UUID, period_id: uuid.UUID | None = None) -> list[VerificationAssignment]:
    va.project_for(db, principal, project_id)
    stmt = select(VerificationAssignment).where(VerificationAssignment.project_id == project_id)
    if period_id:
        stmt = stmt.where(VerificationAssignment.monitoring_period_id == period_id)
    return list(db.scalars(stmt.order_by(VerificationAssignment.proposed_at.desc())).all())


def vvb_assignments(db: Session, principal: Principal) -> list[VerificationAssignment]:
    orgs = {g.organization_id for g in principal.grants if P.VERIFICATION_VVB_READ in g.permissions and g.organization_id}
    if not orgs:
        return []
    rows = db.scalars(select(VerificationAssignment).where(VerificationAssignment.vvb_organization_id.in_(orgs),
                                                           VerificationAssignment.status.in_(va.VVB_VISIBLE_STATES))
                      .order_by(VerificationAssignment.proposed_at.desc())).all()
    out = []
    for a in rows:
        p = db.get(Project, a.project_id)
        if p is not None and p.environment == a.environment and va.vvb_org_ok(db, a.vvb_organization_id, a.environment):
            out.append(a)
    return out


def _transition(db: Session, ctx: RequestContext, principal: Principal, a: VerificationAssignment, p: Project, to: str, action: str,
                reason: str | None, side: str, **extra: Any) -> None:
    frm = a.status
    VERIFICATION_ASSIGNMENT_MACHINE.assert_transition(frm, to)
    va.workflow(db, ctx, "verification_assignment", a.id, frm, to, reason)
    a.status = to
    va.audit(db, ctx, principal, action, "verification_assignment", a.id, a, p, {"status": to, **extra}, reason, side, {"status": frm})


# ---------------------------------------------------------------- assignments
def propose(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID, period_id: uuid.UUID, vvb_org_id: uuid.UUID,
            notes: str | None, previous_id: uuid.UUID | None) -> VerificationAssignment:
    p = va.project_for(db, principal, project_id, P.VERIFICATION_MANAGE)
    _period(db, p, period_id)
    if va.vvb_org_ok(db, vvb_org_id, p.environment) is None:
        raise Conflict("The organization is not an active VVB of the project's environment.", error_code="NOT_A_VVB")
    if db.scalars(select(VerificationAssignment).where(VerificationAssignment.monitoring_period_id == period_id,
                                                       VerificationAssignment.status.in_(OPEN_ASSIGNMENT_STATUSES))).first():
        raise Conflict("This monitoring period already has an open VVB assignment.", error_code="OPEN_ASSIGNMENT_EXISTS")
    if previous_id is not None:
        prev = db.get(VerificationAssignment, previous_id)
        if prev is None or prev.project_id != p.id or prev.monitoring_period_id != period_id or prev.status in OPEN_ASSIGNMENT_STATUSES:
            raise Conflict("A replacement must reference a closed assignment of the same project and period.", error_code="INVALID_REPLACEMENT")
    a = VerificationAssignment(assignment_code=next_code(db, "verification_assignment", utcnow().year), project_id=p.id,
                               monitoring_period_id=period_id, vvb_organization_id=vvb_org_id, status="PROPOSED", previous_assignment_id=previous_id,
                               notes=notes, proposed_by=principal.user_id, environment=p.environment)
    db.add(a)
    db.flush()
    va.workflow(db, ctx, "verification_assignment", a.id, None, "PROPOSED", notes)
    va.audit(db, ctx, principal, "VERIFICATION_ASSIGNMENT_PROPOSED", "verification_assignment", a.id, a, p,
             {"status": "PROPOSED", "previous_assignment_id": previous_id}, notes)
    db.commit()
    return a


def withdraw(db: Session, ctx: RequestContext, principal: Principal, assignment_id: uuid.UUID, reason: str) -> VerificationAssignment:
    a, p = va.project_assignment(db, principal, assignment_id, P.VERIFICATION_MANAGE)
    if a.status != "PROPOSED":
        raise Conflict(f"Only a PROPOSED assignment can be withdrawn (it is {a.status}).", error_code="ASSIGNMENT_NOT_PROPOSED")
    a.closed_by, a.closed_at, a.closed_side, a.closed_reason = principal.user_id, utcnow(), "PROJECT", reason
    _transition(db, ctx, principal, a, p, "WITHDRAWN", "VERIFICATION_ASSIGNMENT_WITHDRAWN", reason, "PROJECT")
    db.commit()
    return a


def terminate(db: Session, ctx: RequestContext, principal: Principal, assignment_id: uuid.UUID, reason: str, side: str) -> VerificationAssignment:
    if side == "PROJECT":
        a, p = va.project_assignment(db, principal, assignment_id, P.VERIFICATION_MANAGE)
    else:
        a, p, _ = va.vvb_assignment(db, principal, assignment_id, P.VERIFICATION_VVB_REVIEW)
    if a.status != "ACCEPTED":
        raise Conflict(f"Only an ACCEPTED assignment can be terminated (it is {a.status}).", error_code="ASSIGNMENT_NOT_ACCEPTED")
    a.closed_by, a.closed_at, a.closed_side, a.closed_reason = principal.user_id, utcnow(), side, reason
    _transition(db, ctx, principal, a, p, "TERMINATED", "VERIFICATION_ASSIGNMENT_TERMINATED", reason, side)
    current = current_submission(db, a.id)
    if current is not None:
        _close_submission(db, ctx, principal, current, a, p, "INVALIDATED", f"Assignment terminated: {reason}")
    db.commit()
    return a


def accept(db: Session, ctx: RequestContext, principal: Principal, assignment_id: uuid.UUID, coi: str) -> VerificationAssignment:
    a, p, _ = va.vvb_assignment(db, principal, assignment_id, P.VERIFICATION_VVB_REVIEW)
    if a.status != "PROPOSED":
        raise Conflict(f"Only a PROPOSED assignment can be accepted (it is {a.status}).", error_code="ASSIGNMENT_NOT_PROPOSED")
    now = utcnow()
    a.accepted_by, a.accepted_at = principal.user_id, now
    a.coi_declaration, a.coi_declared_by, a.coi_declared_at = coi, principal.user_id, now
    _transition(db, ctx, principal, a, p, "ACCEPTED", "VERIFICATION_ASSIGNMENT_ACCEPTED", None, "VVB")
    va.audit(db, ctx, principal, "VERIFICATION_COI_DECLARED", "verification_assignment", a.id, a, p, {"coi_declaration": coi}, None, "VVB")
    _sync_project(db, ctx, p, verified=False)
    db.commit()
    return a


def decline(db: Session, ctx: RequestContext, principal: Principal, assignment_id: uuid.UUID, reason: str) -> VerificationAssignment:
    a, p, _ = va.vvb_assignment(db, principal, assignment_id, P.VERIFICATION_VVB_REVIEW)
    if a.status != "PROPOSED":
        raise Conflict(f"Only a PROPOSED assignment can be declined (it is {a.status}).", error_code="ASSIGNMENT_NOT_PROPOSED")
    a.closed_by, a.closed_at, a.closed_side, a.closed_reason = principal.user_id, utcnow(), "VVB", reason
    _transition(db, ctx, principal, a, p, "DECLINED", "VERIFICATION_ASSIGNMENT_DECLINED", reason, "VVB")
    db.commit()
    return a


# ---------------------------------------------------------------- submissions
def submissions(db: Session, assignment_id: uuid.UUID) -> list[VerificationSubmission]:
    return list(db.scalars(select(VerificationSubmission).where(VerificationSubmission.assignment_id == assignment_id)
                           .order_by(VerificationSubmission.seq)).all())


def current_submission(db: Session, assignment_id: uuid.UUID) -> VerificationSubmission | None:
    return db.scalars(select(VerificationSubmission).where(VerificationSubmission.assignment_id == assignment_id,
                                                           VerificationSubmission.status == "SUBMITTED")).first()


def package_problems(db: Session, s: VerificationSubmission) -> list[str]:
    """Is the submitted package still the period's valid Phase 8A READY package?"""
    r = db.get(CalculationReadinessReview, s.readiness_review_id)
    out = []
    if r is None or r.status != "READY":
        out.append(f"the readiness review is {r.status if r else 'missing'}")
    run = cr.current_run(db, s.monitoring_period_id)
    if run is None or run.id != s.calculation_run_id:
        out.append("the submitted calculation run is no longer the period's current APPROVED run")
    rep = crep.current_report(db, s.calculation_run_id)
    if rep is None or rep.id != s.calculation_report_id:
        out.append("the calculation report changed")
    if r is not None and (r.manifest is None or fw.sha256(json.loads(r.manifest)) != s.manifest_sha256):
        out.append("the manifest hash does not match")
    return out


def _close_submission(db: Session, ctx: RequestContext, principal: Principal | None, s: VerificationSubmission, a: VerificationAssignment,
                      p: Project, to: str, reason: str, superseded_by: uuid.UUID | None = None) -> None:
    frm = s.status
    VERIFICATION_SUBMISSION_MACHINE.assert_transition(frm, to)
    s.status, s.closed_at, s.closed_reason, s.superseded_by_submission_id = to, utcnow(), reason[:2000], superseded_by
    va.workflow(db, ctx, "verification_submission", s.id, frm, to, reason)
    action = "VERIFICATION_SUBMISSION_INVALIDATED" if to == "INVALIDATED" else "VERIFICATION_SUBMISSION_SUPERSEDED"
    va.audit(db, ctx, principal, action, "verification_submission", s.id, a, p, {"status": to, "submission_code": s.submission_code}, reason,
             "PROJECT", {"status": frm})
    d = db.scalars(select(VerificationDecision).where(VerificationDecision.submission_id == s.id, VerificationDecision.status == "CURRENT")).first()
    if d is not None:   # the decision no longer represents the current package — it is kept, marked SUPERSEDED (never edited)
        d.status, d.superseded_at, d.superseded_reason = "SUPERSEDED", utcnow(), reason[:2000]
        va.audit(db, ctx, principal, "VERIFICATION_DECISION_SUPERSEDED", "verification_decision", d.id, a, p,
                 {"status": "SUPERSEDED", "decision_code": d.decision_code, "outcome": d.outcome}, reason, "PROJECT", {"status": "CURRENT"})


def refresh(db: Session, ctx: RequestContext, assignment: VerificationAssignment) -> None:
    """Invalidate the assignment's SUBMITTED package when it is no longer the valid READY package (read-time re-check, B12 / C6)."""
    s = current_submission(db, assignment.id)
    if s is None:
        return
    cr.refresh(db, ctx, s.monitoring_period_id)
    problems = package_problems(db, s)
    if problems:
        p = db.get(Project, assignment.project_id)
        assert p is not None
        _close_submission(db, ctx, None, s, assignment, p, "INVALIDATED", "Package no longer valid: " + "; ".join(problems))
        db.commit()


def submit(db: Session, ctx: RequestContext, principal: Principal, assignment_id: uuid.UUID) -> VerificationSubmission:
    a, p = va.project_assignment(db, principal, assignment_id, P.VERIFICATION_MANAGE)
    if a.status != "ACCEPTED":
        raise Conflict(f"Submission needs an ACCEPTED assignment (it is {a.status}).", error_code="ASSIGNMENT_NOT_ACCEPTED")
    refresh(db, ctx, a)
    cr.refresh(db, ctx, a.monitoring_period_id)
    ready = db.scalars(select(CalculationReadinessReview).where(CalculationReadinessReview.monitoring_period_id == a.monitoring_period_id,
                                                                CalculationReadinessReview.status == "READY")).first()
    if ready is None or ready.project_id != a.project_id:
        raise Conflict("The monitoring period has no valid READY package (Phase 8A internal readiness).", error_code="NO_READY_PACKAGE")
    run = db.get(CalculationRun, ready.run_id)
    blockers, _, rep = cr.evaluate(db, a.monitoring_period_id, run)
    if blockers or rep is None or rep.id != ready.report_id or ready.manifest is None \
            or fw.sha256(json.loads(ready.manifest)) != ready.manifest_sha256:
        raise Conflict("The READY package is no longer valid.", error_code="READINESS_NOT_VALID",
                       details={"blockers": [b.as_dict() for b in blockers]})
    assert run is not None and ready.manifest_sha256 is not None
    cur = current_submission(db, a.id)
    if cur is not None and cur.readiness_review_id == ready.id:
        raise Conflict(f"This READY package is already submitted ({cur.submission_code}).", error_code="SUBMISSION_EXISTS")
    seq = len(submissions(db, a.id)) + 1
    s = VerificationSubmission(submission_code=next_code(db, "verification_submission", utcnow().year), assignment_id=a.id, seq=seq,
                               project_id=p.id, monitoring_period_id=a.monitoring_period_id, readiness_review_id=ready.id,
                               calculation_run_id=run.id, calculation_report_id=ready.report_id, manifest_sha256=ready.manifest_sha256,
                               status="SUBMITTED", submitted_by=principal.user_id, environment=a.environment)
    if cur is not None:   # closed first so the "one SUBMITTED per assignment" filtered index holds at every flush
        _close_submission(db, ctx, principal, cur, a, p, "SUPERSEDED", "A newer READY package was submitted")
        db.flush()
    db.add(s)
    db.flush()
    if cur is not None:
        cur.superseded_by_submission_id = s.id
    va.workflow(db, ctx, "verification_submission", s.id, None, "SUBMITTED", None)
    va.audit(db, ctx, principal, "VERIFICATION_SUBMITTED", "verification_submission", s.id, a, p,
             {"status": "SUBMITTED", "submission_code": s.submission_code, "seq": seq, "readiness_review_id": ready.id,
              "calculation_run_id": run.id, "calculation_report_id": ready.report_id, "manifest_sha256": s.manifest_sha256})
    _sync_project(db, ctx, p, verified=False)
    db.commit()
    return s


# ---------------------------------------------------------------- decision
def decide(db: Session, ctx: RequestContext, principal: Principal, submission_id: uuid.UUID, outcome: str, rationale: str,
           quantity: Decimal | None, unit: str | None, filename: str | None, data: bytes) -> VerificationDecision:
    s, a, p, org = va.vvb_submission(db, principal, submission_id, P.VERIFICATION_DECIDE)
    if a.status != "ACCEPTED":
        raise Conflict(f"A decision needs an ACCEPTED assignment (it is {a.status}).", error_code="ASSIGNMENT_NOT_ACCEPTED")
    refresh(db, ctx, a)
    db.refresh(s)
    if s.status != "SUBMITTED":
        raise Conflict(f"Decisions are recorded on the current submission (this one is {s.status}).", error_code="SUBMISSION_NOT_CURRENT")
    if outcome not in ("VERIFIED", "NOT_VERIFIED"):
        raise ValidationFailed("Outcome must be VERIFIED or NOT_VERIFIED.", error_code="INVALID_OUTCOME")
    if (quantity is None) != (unit is None or not unit.strip()):
        raise ValidationFailed("A VVB-stated verified quantity needs both a value and a unit.", error_code="QUANTITY_UNIT_REQUIRED")
    if quantity is not None and outcome != "VERIFIED":
        raise ValidationFailed("A VVB-stated verified quantity is only recorded with a VERIFIED outcome.", error_code="QUANTITY_NOT_ALLOWED")
    raisers = {f.raised_by for f in db.scalars(select(VerificationFinding).where(VerificationFinding.submission_id == s.id)).all()}
    if principal.user_id in raisers:   # C18
        raise PermissionDenied("You raised findings on this submission, so another VVB user must record the decision.",
                               error_code="SEPARATION_OF_DUTIES", details={"reasons": ["you raised verification findings on this submission"]})
    open_f = db.scalars(select(VerificationFinding).where(VerificationFinding.submission_id == s.id,
                                                          VerificationFinding.status.in_(("OPEN", "RESPONDED")))).all()
    if open_f:
        raise Conflict("All verification findings must be closed first.", error_code="OPEN_VERIFICATION_FINDINGS",
                       details={"findings": [f.finding_code for f in open_f]})
    open_ca = db.scalars(select(CorrectiveAction).where(CorrectiveAction.submission_id == s.id, CorrectiveAction.status.in_(OPEN_CA_STATUSES))).all()
    if open_ca:
        raise Conflict("All corrective actions must be accepted or cancelled first.", error_code="OPEN_CORRECTIVE_ACTIONS",
                       details={"corrective_actions": [c.action_code for c in open_ca]})
    if not data:
        raise ValidationFailed("The VVB verification report (PDF) is required.", error_code="REPORT_REQUIRED")
    doc = document_service.create_document(db, ctx, entity_type=SUBMISSION_ENTITY, entity_id=s.id, organization_id=org.id, environment=s.environment,
                                           category=DocumentCategory.VERIFICATION_REPORT.value,
                                           title=f"VVB verification report ({s.submission_code})",
                                           filename=filename, data=data)
    d = VerificationDecision(decision_code=next_code(db, "verification_decision", utcnow().year), assignment_id=a.id, submission_id=s.id,
                             project_id=p.id, monitoring_period_id=s.monitoring_period_id, vvb_organization_id=org.id, outcome=outcome,
                             verified_quantity=quantity, verified_quantity_unit=unit.strip() if unit else None, rationale=rationale,
                             report_document_id=doc.id, report_sha256=hashlib.sha256(data).hexdigest(), manifest_sha256=s.manifest_sha256,
                             decided_by=principal.user_id, status="CURRENT", environment=s.environment)
    old = db.scalars(select(VerificationDecision).where(VerificationDecision.monitoring_period_id == s.monitoring_period_id,
                                                        VerificationDecision.status == "CURRENT")).first()
    if old is not None:
        old.status, old.superseded_at, old.superseded_reason = "SUPERSEDED", utcnow(), f"Superseded by a later decision on {s.submission_code}"
        db.flush()
    db.add(d)
    db.flush()
    va.audit(db, ctx, principal, "VERIFICATION_DECISION_RECORDED", "verification_decision", d.id, a, p,
             {"decision_code": d.decision_code, "outcome": outcome, "submission_id": s.id, "verified_quantity": str(quantity) if quantity else None,
              "verified_quantity_unit": d.verified_quantity_unit, "report_document_id": doc.id, "report_sha256": d.report_sha256,
              "manifest_sha256": d.manifest_sha256, "label": "VVB-stated verified quantity — not issued, not a credit"}, rationale, "VVB")
    a.completed_at = utcnow()
    _transition(db, ctx, principal, a, p, "COMPLETED", "VERIFICATION_ASSIGNMENT_COMPLETED", None, "VVB", decision_code=d.decision_code)
    _sync_project(db, ctx, p, verified=outcome == "VERIFIED")
    db.commit()
    return d


def decisions(db: Session, assignment_id: uuid.UUID) -> list[VerificationDecision]:
    return list(db.scalars(select(VerificationDecision).where(VerificationDecision.assignment_id == assignment_id)
                           .order_by(VerificationDecision.decided_at)).all())


# ---------------------------------------------------------------- aggregate project status (C2)
def _sync_project(db: Session, ctx: RequestContext, p: Project, verified: bool) -> None:
    db.flush()                                      # sessions do not autoflush: the caller's assignment change must be visible
    has_accepted = db.scalars(select(VerificationAssignment).where(VerificationAssignment.project_id == p.id,
                                                                   VerificationAssignment.status.in_(("ACCEPTED", "COMPLETED")))).first()
    if p.status == "CALCULATED" and (has_accepted or verified):
        psvc.transition_to(db, ctx, p, "VERIFICATION", "PROJECT_STATUS_CHANGED", "VERIFICATION_STARTED",
                           "First VVB assignment accepted for a calculated project (aggregate status; periods are authoritative)")
    if verified and p.status == "VERIFICATION":
        psvc.transition_to(db, ctx, p, "VERIFIED", "PROJECT_STATUS_CHANGED", "FIRST_PERIOD_VERIFIED",
                           "First monitoring period verified by a VVB (aggregate status; later periods are tracked separately)")


# ---------------------------------------------------------------- project-side views
def period_view(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID, period_id: uuid.UUID) -> dict[str, Any]:
    p = va.project_for(db, principal, project_id)
    mp = _period(db, p, period_id)
    rows = assignments(db, principal, project_id, period_id)
    for a in rows:
        if a.status in ("ACCEPTED", "COMPLETED"):   # a recalculation also supersedes a recorded decision (it is no longer current)
            refresh(db, ctx, a)
    cr.refresh(db, ctx, period_id)
    ready = db.scalars(select(CalculationReadinessReview).where(CalculationReadinessReview.monitoring_period_id == period_id,
                                                                CalculationReadinessReview.status == "READY")).first()
    run = cr.current_run(db, period_id)
    accepted = next((a for a in rows if a.status == "ACCEPTED"), None)
    blockers = []
    if accepted is None:
        blockers.append("No ACCEPTED VVB assignment for this period.")
    if ready is None:
        blockers.append("No valid READY package (Phase 8A internal readiness) for this period.")
    if accepted is not None and ready is not None:
        cur = current_submission(db, accepted.id)
        if cur is not None and cur.readiness_review_id == ready.id:
            blockers.append(f"The READY package is already submitted ({cur.submission_code}).")
    decision = db.scalars(select(VerificationDecision).where(VerificationDecision.monitoring_period_id == period_id,
                                                             VerificationDecision.status == "CURRENT")).first()
    return {"project": p, "period": mp, "assignments": rows, "ready": ready, "run": run, "decision": decision, "submit_blockers": blockers,
            "can_manage": principal.can_in_org(P.VERIFICATION_MANAGE, p.organization_id),
            "can_respond": principal.can_in_org(P.VERIFICATION_RESPOND, p.organization_id)}


def get_decision(db: Session, principal: Principal, decision_id: uuid.UUID) -> tuple[VerificationDecision, VerificationAssignment, Project]:
    d = db.get(VerificationDecision, decision_id)
    if d is None:
        raise NotFound("Verification decision not found.", error_code="DECISION_NOT_FOUND")
    try:
        a, p = va.project_assignment(db, principal, d.assignment_id)
    except NotFound:
        raise NotFound("Verification decision not found.", error_code="DECISION_NOT_FOUND") from None
    return d, a, p


def lineage(db: Session, principal: Principal, decision_id: uuid.UUID) -> dict[str, Any]:
    """decision → assignment → submission → readiness → manifest → report → run → methodology / dataset → period → project."""
    d, a, p = get_decision(db, principal, decision_id)
    s = db.get(VerificationSubmission, d.submission_id)
    assert s is not None
    r = db.get(CalculationReadinessReview, s.readiness_review_id)
    run = db.get(CalculationRun, s.calculation_run_id)
    rep = crep.current_report(db, s.calculation_run_id)
    rep = rep if rep is not None and rep.id == s.calculation_report_id else None
    org = db.get(Organization, d.vvb_organization_id)
    mp = db.get(MonitoringPeriod, d.monitoring_period_id)
    manifest = json.loads(r.manifest) if r is not None and r.manifest else {}
    chain: list[dict[str, Any]] = [
        {"kind": "VERIFICATION_DECISION", "id": str(d.id), "code": d.decision_code, "status": d.status, "outcome": d.outcome,
         "report_sha256": d.report_sha256,
         "verified_quantity": format(d.verified_quantity.normalize(), "f") if d.verified_quantity is not None else None,
         "verified_quantity_unit": d.verified_quantity_unit, "label": "VVB-stated verified quantity — not issued, not a credit"},
        {"kind": "VVB_ORGANIZATION", "id": str(d.vvb_organization_id), "name": org.name if org else None},
        {"kind": "VERIFICATION_ASSIGNMENT", "id": str(a.id), "code": a.assignment_code, "status": a.status, "coi_declared_at":
         a.coi_declared_at.isoformat() + "Z" if a.coi_declared_at else None},
        {"kind": "VERIFICATION_SUBMISSION", "id": str(s.id), "code": s.submission_code, "status": s.status, "seq": s.seq},
        {"kind": "READINESS_REVIEW", "id": str(s.readiness_review_id), "code": r.readiness_code if r else None, "status": r.status if r else None},
        {"kind": "MANIFEST", "sha256": s.manifest_sha256, "matches_decision": s.manifest_sha256 == d.manifest_sha256},
        {"kind": "CALCULATION_REPORT", "id": str(s.calculation_report_id), "code": (manifest.get("calculation_report") or {}).get("report_code"),
         "current": rep is not None},
        {"kind": "CALCULATION_RUN", "id": str(s.calculation_run_id), "code": run.run_code if run else None, "status": run.status if run else None,
         "net_result": run.net_result if run else None, "net_unit": run.net_unit if run else None,
         "label": "Calculated tCO2e — not verified, not issued", "lineage": f"/api/v1/calculations/runs/{s.calculation_run_id}/lineage"},
        {"kind": "METHODOLOGY_VERSION", **{k: (manifest.get("methodology") or {}).get(k) for k in ("version_id", "code", "version_label")}},
        {"kind": "MRV_DATASET", **(manifest.get("dataset") or {})},
        {"kind": "MONITORING_PERIOD", "id": str(d.monitoring_period_id), "number": mp.period_number if mp else None},
        {"kind": "PROJECT", "id": str(p.id), "code": p.project_code, "status": p.status},
    ]
    return {"decision": chain[0], "chain": chain}
