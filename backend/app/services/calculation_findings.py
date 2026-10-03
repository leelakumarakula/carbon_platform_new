"""Internal calculation findings (Phase 8A decisions B2–B6). Not VVB findings; no corrective-action workflow.

OPEN → RESPONDED → RESOLVED; RESPONDED → OPEN (response returned); RESOLVED → OPEN (reopened); OPEN / RESPONDED → WITHDRAWN.
- QA Officer (calculation.review) raises, returns, resolves, reopens and — only the raiser, with a reason — withdraws
- Calculation Analyst (calculation.manage) responds; the resolver is never the responder (SEPARATION_OF_DUTIES)
- findings are raised on a non-DRAFT run and every target must belong to that run (no cross-run targets)
- blocking findings gate internal verification readiness only (Phase 7 approval is unchanged); opening or reopening a blocking
  finding immediately invalidates a READY readiness of the period (B12)
- the finding row keeps the current state; identity, target and original text never change; every change is an append-only event
"""
import uuid
from typing import Any

from sqlalchemy import func, select, true
from sqlalchemy.orm import Session

from app.audit.service import record
from app.core.context import RequestContext
from app.core.errors import Conflict, NotFound, PermissionDenied
from app.models import (
    CalculationFinding,
    CalculationFindingEvent,
    CalculationInput,
    CalculationOutput,
    CalculationRun,
    Document,
    LabResult,
    MethodologyCalculationRule,
    WorkflowEvent,
)
from app.models.base import utcnow
from app.models.preverification import OPEN_FINDING_STATUSES
from app.repositories.sequences import next_code
from app.schemas.preverification import FindingIn
from app.security.permissions import P
from app.security.principal import Principal
from app.services import calculation_service as cs
from app.services.workflows import CALCULATION_FINDING_MACHINE

ENTITY = "calculation_finding"


def _nf() -> NotFound:
    return NotFound("Finding not found.", error_code="FINDING_NOT_FOUND")


def get_finding(db: Session, principal: Principal, finding_id: uuid.UUID, *codes: str) -> tuple[CalculationFinding, CalculationRun]:
    f = db.get(CalculationFinding, finding_id)
    if f is None:
        raise _nf()
    try:
        run, _ = cs.get_run(db, principal, f.run_id, *codes)
    except NotFound:
        raise _nf() from None
    return f, run


def findings(db: Session, principal: Principal, project_id: uuid.UUID, period_id: uuid.UUID | None = None, run_id: uuid.UUID | None = None,
             status: str | None = None) -> list[CalculationFinding]:
    cs.project_for(db, principal, project_id)
    stmt = select(CalculationFinding).where(CalculationFinding.project_id == project_id)
    if period_id:
        stmt = stmt.where(CalculationFinding.monitoring_period_id == period_id)
    if run_id:
        stmt = stmt.where(CalculationFinding.run_id == run_id)
    if status:
        stmt = stmt.where(CalculationFinding.status == status)
    return list(db.scalars(stmt.order_by(CalculationFinding.finding_code)).all())


def findings_of_period(db: Session, period_id: uuid.UUID) -> list[CalculationFinding]:
    return list(db.scalars(select(CalculationFinding).where(CalculationFinding.monitoring_period_id == period_id)
                           .order_by(CalculationFinding.finding_code)).all())


def events(db: Session, finding_id: uuid.UUID) -> list[CalculationFindingEvent]:
    return list(db.scalars(select(CalculationFindingEvent).where(CalculationFindingEvent.finding_id == finding_id)
                           .order_by(CalculationFindingEvent.seq)).all())


def open_blocking(db: Session, period_id: uuid.UUID) -> list[CalculationFinding]:
    """Open (OPEN / RESPONDED) blocking findings of any run of the period — findings survive recalculation."""
    return list(db.scalars(select(CalculationFinding).where(CalculationFinding.monitoring_period_id == period_id,
                                                           CalculationFinding.blocking == true(),
                                                           CalculationFinding.status.in_(OPEN_FINDING_STATUSES))
                           .order_by(CalculationFinding.finding_code)).all())


def _event(db: Session, ctx: RequestContext, f: CalculationFinding, action: str, frm: str | None, to: str, note: str | None,
           document_id: uuid.UUID | None = None, run_id: uuid.UUID | None = None, org: uuid.UUID | None = None) -> None:
    if frm is not None:
        CALCULATION_FINDING_MACHINE.assert_transition(frm, to)
    seq = (db.scalar(select(func.max(CalculationFindingEvent.seq)).where(CalculationFindingEvent.finding_id == f.id)) or 0) + 1
    assert ctx.user_id is not None
    db.add(CalculationFindingEvent(finding_id=f.id, seq=seq, action=action, from_status=frm, to_status=to, actor_id=ctx.user_id, note=note,
                                   document_id=document_id, run_id=run_id))
    db.add(WorkflowEvent(entity_type=ENTITY, entity_id=str(f.id), from_status=frm, to_status=to, user_id=ctx.user_id, reason=note,
                         request_id=ctx.request_id))
    record(db, ctx, f"CALCULATION_FINDING_{action}", ENTITY, f.id, {"status": frm} if frm else None,
           {"status": to, "finding_code": f.finding_code, "run_id": f.run_id, "category": f.category, "blocking": f.blocking,
            "document_id": document_id, "run_ref": run_id}, note, organization_id=org)
    f.status = to


def _check_document(db: Session, run: CalculationRun, document_id: uuid.UUID | None) -> None:
    """Evidence must belong to this run: a document attached to the run, or the report of one of its laboratory-result inputs."""
    if document_id is None:
        return
    doc = db.get(Document, document_id)
    ok = doc is not None and doc.status == "ACTIVE" and doc.entity_type == "calculation_run" and doc.entity_id == run.id
    if not ok and doc is not None:
        lab_ids = [i.source_id for i in cs.inputs(db, run.id) if i.source_type == "LAB_RESULT" and i.source_id]
        ok = bool(lab_ids) and db.scalar(select(func.count()).select_from(LabResult).where(
            LabResult.id.in_(lab_ids), LabResult.report_document_id == document_id)) == 1
    if not ok:
        raise Conflict("The evidence document does not belong to this calculation run.", error_code="INVALID_FINDING_TARGET",
                       details={"target": "evidence_document_id"})


def _check_targets(db: Session, run: CalculationRun, data: FindingIn) -> None:
    bad = []
    if data.target_input_seq is not None and not db.scalar(select(func.count()).select_from(CalculationInput).where(
            CalculationInput.run_id == run.id, CalculationInput.seq == data.target_input_seq)):
        bad.append("target_input_seq")
    if data.target_output_seq is not None and not db.scalar(select(func.count()).select_from(CalculationOutput).where(
            CalculationOutput.run_id == run.id, CalculationOutput.seq == data.target_output_seq)):
        bad.append("target_output_seq")
    if data.target_calculation_rule_id is not None:
        rule = db.get(MethodologyCalculationRule, data.target_calculation_rule_id)
        if rule is None or rule.methodology_version_id != run.methodology_version_id:
            bad.append("target_calculation_rule_id")
    source_in_run = data.target_source_type is None or bool(db.scalar(select(func.count()).select_from(CalculationInput).where(
        CalculationInput.run_id == run.id, CalculationInput.source_type == data.target_source_type,
        CalculationInput.source_id == data.target_source_id)))
    if (data.target_source_type is None) != (data.target_source_id is None) or not source_in_run:
        bad.append("target_source")
    if bad:
        raise Conflict("Finding targets must belong to the same calculation run.", error_code="INVALID_FINDING_TARGET", details={"targets": bad})
    _check_document(db, run, data.evidence_document_id)


def raise_finding(db: Session, ctx: RequestContext, principal: Principal, run_id: uuid.UUID, data: FindingIn) -> CalculationFinding:
    run, p = cs.get_run(db, principal, run_id, P.CALCULATION_REVIEW)
    if run.status == "DRAFT":     # B5
        raise Conflict("Findings cannot be raised on a DRAFT run.", error_code="FINDING_RUN_DRAFT")
    _check_targets(db, run, data)
    f = CalculationFinding(finding_code=next_code(db, "calculation_finding", utcnow().year), project_id=p.id,
                           monitoring_period_id=run.monitoring_period_id, run_id=run.id, category=data.category, blocking=data.blocking,
                           title=data.title, description=data.description, target_input_seq=data.target_input_seq,
                           target_output_seq=data.target_output_seq, target_calculation_rule_id=data.target_calculation_rule_id,
                           target_source_type=data.target_source_type, target_source_id=data.target_source_id,
                           evidence_document_id=data.evidence_document_id, status="OPEN", raised_by=principal.user_id, environment=run.environment)
    db.add(f)
    db.flush()
    _event(db, ctx, f, "RAISED", None, "OPEN", data.description, data.evidence_document_id, org=p.organization_id)
    if f.blocking:
        _invalidate(db, ctx, run.monitoring_period_id, f"Blocking finding {f.finding_code} opened")
    db.commit()
    return f


def respond(db: Session, ctx: RequestContext, principal: Principal, finding_id: uuid.UUID, response: str,
            document_id: uuid.UUID | None = None) -> CalculationFinding:
    f, run = get_finding(db, principal, finding_id, P.CALCULATION_MANAGE)
    if f.status != "OPEN":
        raise Conflict(f"Only an OPEN finding can be responded to (it is {f.status}).", error_code="FINDING_NOT_OPEN")
    _check_document(db, run, document_id)
    f.response_text, f.response_document_id, f.responded_by, f.responded_at = response, document_id, principal.user_id, utcnow()
    _event(db, ctx, f, "RESPONDED", "OPEN", "RESPONDED", response, document_id, org=_org(db, run))
    db.commit()
    return f


def resolve(db: Session, ctx: RequestContext, principal: Principal, finding_id: uuid.UUID, note: str,
            resolved_by_run_id: uuid.UUID | None = None) -> CalculationFinding:
    f, run = get_finding(db, principal, finding_id, P.CALCULATION_REVIEW)
    if f.status != "RESPONDED":
        raise Conflict(f"Only a RESPONDED finding can be resolved (it is {f.status}).", error_code="FINDING_NOT_RESPONDED")
    if f.responded_by == principal.user_id:
        raise PermissionDenied("You responded to this finding, so someone else must resolve it.", error_code="SEPARATION_OF_DUTIES",
                               details={"reasons": ["you responded to this finding"]})
    if resolved_by_run_id is not None:
        other = db.get(CalculationRun, resolved_by_run_id)
        if other is None or other.project_id != f.project_id or other.monitoring_period_id != f.monitoring_period_id:
            raise Conflict("The resolving run must belong to the same project and reporting period.", error_code="INVALID_FINDING_TARGET",
                           details={"target": "resolved_by_run_id"})
    f.resolution_note, f.resolved_by, f.resolved_at, f.resolved_by_run_id = note, principal.user_id, utcnow(), resolved_by_run_id
    _event(db, ctx, f, "RESOLVED", "RESPONDED", "RESOLVED", note, run_id=resolved_by_run_id, org=_org(db, run))
    db.commit()
    return f


def return_response(db: Session, ctx: RequestContext, principal: Principal, finding_id: uuid.UUID, reason: str) -> CalculationFinding:
    f, run = get_finding(db, principal, finding_id, P.CALCULATION_REVIEW)
    if f.status != "RESPONDED":
        raise Conflict(f"Only a RESPONDED finding can be returned (it is {f.status}).", error_code="FINDING_NOT_RESPONDED")
    _event(db, ctx, f, "RESPONSE_RETURNED", "RESPONDED", "OPEN", reason, org=_org(db, run))
    db.commit()
    return f


def reopen(db: Session, ctx: RequestContext, principal: Principal, finding_id: uuid.UUID, reason: str) -> CalculationFinding:
    f, run = get_finding(db, principal, finding_id, P.CALCULATION_REVIEW)
    if f.status != "RESOLVED":
        raise Conflict(f"Only a RESOLVED finding can be reopened (it is {f.status}).", error_code="FINDING_NOT_RESOLVED")
    f.resolution_note = f.resolved_by = f.resolved_at = f.resolved_by_run_id = None
    _event(db, ctx, f, "REOPENED", "RESOLVED", "OPEN", reason, org=_org(db, run))
    if f.blocking:
        _invalidate(db, ctx, f.monitoring_period_id, f"Blocking finding {f.finding_code} reopened")
    db.commit()
    return f


def withdraw(db: Session, ctx: RequestContext, principal: Principal, finding_id: uuid.UUID, reason: str) -> CalculationFinding:
    f, run = get_finding(db, principal, finding_id, P.CALCULATION_REVIEW)
    if f.status not in OPEN_FINDING_STATUSES:
        raise Conflict(f"Only an OPEN or RESPONDED finding can be withdrawn (it is {f.status}).", error_code="FINDING_NOT_OPEN")
    if f.raised_by != principal.user_id:
        raise PermissionDenied("Only the person who raised this finding can withdraw it.", error_code="NOT_RAISER")
    f.withdrawn_by, f.withdrawn_at, f.withdraw_reason = principal.user_id, utcnow(), reason
    _event(db, ctx, f, "WITHDRAWN", f.status, "WITHDRAWN", reason, org=_org(db, run))
    db.commit()
    return f


def upload_evidence(db: Session, ctx: RequestContext, principal: Principal, run_id: uuid.UUID, filename: str | None, data: bytes,
                    title: str | None) -> Document:
    """Evidence for a finding or a response, attached to the run itself (so it can never be a cross-run target)."""
    run, p = cs.get_run(db, principal, run_id, P.CALCULATION_MANAGE, P.CALCULATION_REVIEW)
    if run.status == "DRAFT":
        raise Conflict("Evidence is attached to non-DRAFT runs only.", error_code="FINDING_RUN_DRAFT")
    from app.services import (
        calculation_report,  # noqa: F401  (registers the calculation_run document resolver)
        document_service,
    )
    doc = document_service.create_document(db, ctx, entity_type="calculation_run", entity_id=run.id, organization_id=p.organization_id,
                                           environment=run.environment, category="OTHER", title=title or "Calculation evidence",
                                           filename=filename, data=data)
    db.commit()
    return doc


def _org(db: Session, run: CalculationRun) -> uuid.UUID | None:
    from app.models import Project
    p = db.get(Project, run.project_id)
    return p.organization_id if p else None


def _invalidate(db: Session, ctx: RequestContext, period_id: uuid.UUID, reason: str) -> None:
    from app.services import calculation_readiness as cr
    cr.invalidate_period(db, ctx, period_id, reason)


def summary(f: CalculationFinding) -> dict[str, Any]:
    return {"code": f.finding_code, "category": f.category, "blocking": f.blocking, "status": f.status, "title": f.title}
