"""Phase 8B mappers. `vvb=True` renders the VVB-side view: project-side people appear as "Project team" (no internal user list, C10)."""
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CalculationReadinessReview,
    CalculationReport,
    CalculationRun,
    CorrectiveAction,
    MonitoringPeriod,
    Organization,
    Project,
    User,
    VerificationAssignment,
    VerificationDecision,
    VerificationFinding,
    VerificationSubmission,
)
from app.schemas.verification import (
    CATEGORY_LABELS,
    AssignmentOut,
    CorrectiveActionOut,
    DecisionOut,
    EventOut,
    SubmissionOut,
    VFindingOut,
)
from app.security.permissions import P
from app.security.principal import Principal
from app.services import verification_findings as vf
from app.services import verification_service as vs

PROJECT_TEAM = "Project team"


def _names(db: Session, ids: set[Any]) -> dict[Any, str]:
    ids_ = {i for i in ids if i}
    return {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_(ids_))).all()} if ids_ else {}


def _name(names: dict[Any, str], user_id: uuid.UUID | None, project_side: bool, vvb: bool) -> str | None:
    if user_id is None:
        return None
    return PROJECT_TEAM if (vvb and project_side) else names.get(user_id)


def submission_out(db: Session, s: VerificationSubmission, vvb: bool = False) -> SubmissionOut:
    r = db.get(CalculationReadinessReview, s.readiness_review_id)
    run = db.get(CalculationRun, s.calculation_run_id)
    rep = db.get(CalculationReport, s.calculation_report_id)
    names = _names(db, {s.submitted_by})
    return SubmissionOut(id=s.id, submission_code=s.submission_code, seq=s.seq, status=s.status, readiness_review_id=s.readiness_review_id,
                         readiness_code=r.readiness_code if r else None, calculation_run_id=s.calculation_run_id,
                         run_code=run.run_code if run else None, calculation_report_id=s.calculation_report_id,
                         report_code=rep.report_code if rep else None, report_version=rep.version if rep else None,
                         manifest_sha256=s.manifest_sha256, calculated_value=run.net_result if run else None,
                         calculated_unit=run.net_unit if run else None, submitted_by_name=_name(names, s.submitted_by, True, vvb),
                         submitted_at=s.submitted_at, closed_at=s.closed_at, closed_reason=s.closed_reason,
                         superseded_by_submission_id=s.superseded_by_submission_id)


def decision_out(db: Session, d: VerificationDecision) -> DecisionOut:
    s = db.get(VerificationSubmission, d.submission_id)
    org = db.get(Organization, d.vvb_organization_id)
    names = _names(db, {d.decided_by})
    return DecisionOut(id=d.id, decision_code=d.decision_code, assignment_id=d.assignment_id, submission_id=d.submission_id,
                       submission_code=s.submission_code if s else None, monitoring_period_id=d.monitoring_period_id,
                       vvb_organization_id=d.vvb_organization_id, vvb_organization_name=org.name if org else None, outcome=d.outcome,
                       verified_quantity=format(d.verified_quantity.normalize(), "f") if d.verified_quantity is not None else None,
                       verified_quantity_unit=d.verified_quantity_unit, rationale=d.rationale, report_document_id=d.report_document_id,
                       report_sha256=d.report_sha256, manifest_sha256=d.manifest_sha256, decided_by_name=names.get(d.decided_by),
                       decided_at=d.decided_at, status=d.status, superseded_at=d.superseded_at, superseded_reason=d.superseded_reason)


def decision_blockers(db: Session, principal: Principal, a: VerificationAssignment) -> list[str]:
    out = []
    cur = vs.current_submission(db, a.id)
    if a.status != "ACCEPTED":
        out.append(f"The assignment is {a.status}.")
    if cur is None:
        out.append("No current submission (the project has not submitted a valid READY package).")
        return out
    fs = vf.findings_of(db, cur.id)
    if any(f.raised_by == principal.user_id for f in fs):
        out.append("You raised findings on this submission; another VVB user must record the decision (separation of duties).")
    open_f = [f.finding_code for f in fs if f.status != "CLOSED"]
    if open_f:
        out.append("Open findings: " + ", ".join(open_f))
    open_ca = [c.action_code for c in db.scalars(select(CorrectiveAction).where(CorrectiveAction.submission_id == cur.id)).all()
               if c.status in ("REQUESTED", "RESPONDED")]
    if open_ca:
        out.append("Open corrective actions: " + ", ".join(open_ca))
    return out


def assignment_out(db: Session, principal: Principal, a: VerificationAssignment, vvb: bool = False) -> AssignmentOut:
    p = db.get(Project, a.project_id)
    mp = db.get(MonitoringPeriod, a.monitoring_period_id)
    org = db.get(Organization, a.vvb_organization_id)
    names = _names(db, {a.proposed_by, a.accepted_by, a.coi_declared_by, a.closed_by})
    subs = vs.submissions(db, a.id)
    if vvb and a.status == "PROPOSED":
        subs = []                            # nothing of the package is visible before acceptance
    cur = next((s for s in subs if s.status == "SUBMITTED"), None)
    actions: list[str] = []
    blockers: list[str] = []
    if vvb:
        if principal.can_in_org(P.VERIFICATION_VVB_REVIEW, a.vvb_organization_id):
            actions += {"PROPOSED": ["accept", "decline"], "ACCEPTED": ["terminate", "raise_finding"]}.get(a.status, [])
        if principal.can_in_org(P.VERIFICATION_DECIDE, a.vvb_organization_id) and a.status == "ACCEPTED":
            blockers = decision_blockers(db, principal, a)
            if not blockers:
                actions.append("decide")
    elif p is not None:
        if principal.can_in_org(P.VERIFICATION_MANAGE, p.organization_id):
            actions += {"PROPOSED": ["withdraw"], "ACCEPTED": ["submit", "terminate"]}.get(a.status, [])
        if principal.can_in_org(P.VERIFICATION_RESPOND, p.organization_id) and a.status == "ACCEPTED":
            actions.append("respond")
    return AssignmentOut(
        id=a.id, assignment_code=a.assignment_code, project_id=a.project_id, project_code=p.project_code if p else None,
        project_name=p.name if p else None, monitoring_period_id=a.monitoring_period_id, period_number=mp.period_number if mp else None,
        period_start=mp.start_date if mp else None, period_end=mp.end_date if mp else None, vvb_organization_id=a.vvb_organization_id,
        vvb_organization_name=org.name if org else None, status=a.status, previous_assignment_id=a.previous_assignment_id,
        notes=a.notes, proposed_by_name=_name(names, a.proposed_by, True, vvb), proposed_at=a.proposed_at,
        accepted_by_name=_name(names, a.accepted_by, False, vvb), accepted_at=a.accepted_at, coi_declaration=a.coi_declaration,
        coi_declared_by_name=_name(names, a.coi_declared_by, False, vvb), coi_declared_at=a.coi_declared_at, completed_at=a.completed_at,
        closed_side=a.closed_side, closed_reason=a.closed_reason, closed_at=a.closed_at, environment=a.environment,
        current_submission=submission_out(db, cur, vvb) if cur else None, submissions=[submission_out(db, s, vvb) for s in subs],
        decisions=[decision_out(db, d) for d in vs.decisions(db, a.id)], actions=actions, decision_blockers=blockers,
    )


def _events(db: Session, evs: list[Any], vvb: bool) -> list[EventOut]:
    names = _names(db, {e.actor_id for e in evs})
    return [EventOut(seq=e.seq, action=e.action, from_status=e.from_status, to_status=e.to_status,
                     actor_name=_name(names, e.actor_id, e.actor_side == "PROJECT", vvb), actor_side=e.actor_side, occurred_at=e.occurred_at,
                     note=e.note, document_id=e.document_id) for e in evs]


def ca_out(db: Session, c: CorrectiveAction, vvb: bool = False) -> CorrectiveActionOut:
    names = _names(db, {c.requested_by, c.responded_by, c.reviewed_by})
    return CorrectiveActionOut(id=c.id, action_code=c.action_code, finding_id=c.finding_id, description=c.description, due_date=c.due_date,
                               overdue=vf.is_overdue(c), status=c.status, requested_by_name=_name(names, c.requested_by, False, vvb),
                               requested_at=c.requested_at, response_text=c.response_text, response_document_id=c.response_document_id,
                               responded_by_name=_name(names, c.responded_by, True, vvb), responded_at=c.responded_at,
                               reviewed_by_name=_name(names, c.reviewed_by, False, vvb), reviewed_at=c.reviewed_at, review_note=c.review_note,
                               events=_events(db, vf.ca_events(db, c.id), vvb))


def finding_out(db: Session, f: VerificationFinding, vvb: bool = False) -> VFindingOut:
    names = _names(db, {f.raised_by, f.responded_by, f.closed_by})
    return VFindingOut(id=f.id, finding_code=f.finding_code, assignment_id=f.assignment_id, submission_id=f.submission_id, category=f.category,
                       category_label=CATEGORY_LABELS[f.category], blocking=f.blocking, title=f.title, description=f.description,
                       target_type=f.target_type, target_ref=f.target_ref, status=f.status,
                       raised_by_name=_name(names, f.raised_by, False, vvb), raised_at=f.raised_at, response_text=f.response_text,
                       response_document_id=f.response_document_id, responded_by_name=_name(names, f.responded_by, True, vvb),
                       responded_at=f.responded_at, closure_note=f.closure_note, closed_by_name=_name(names, f.closed_by, False, vvb),
                       closed_at=f.closed_at, events=_events(db, vf.finding_events(db, f.id), vvb),
                       corrective_actions=[ca_out(db, c, vvb) for c in vf.cas_of(db, f.id)])
