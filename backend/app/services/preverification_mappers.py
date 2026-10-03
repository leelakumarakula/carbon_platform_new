"""Response builders for Phase 8A (findings, reports, readiness)."""
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CalculationFinding,
    CalculationReadinessReview,
    CalculationReport,
    CalculationRun,
    MethodologyCalculationRule,
    User,
)
from app.schemas.calculation import CALCULATED_LABEL, Blocker
from app.schemas.preverification import (
    CATEGORY_LABELS,
    FindingEventOut,
    FindingOut,
    ManifestOut,
    ReadinessCheckOut,
    ReadinessOut,
    ReadinessView,
    ReportDetailOut,
    ReportOut,
)
from app.security.permissions import P
from app.security.principal import Principal
from app.services import calculation_findings as cf
from app.services import calculation_readiness as cr


def _names(db: Session, ids: set[Any]) -> dict[Any, str]:
    ids_ = {i for i in ids if i}
    return {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_(ids_))).all()} if ids_ else {}


def finding_out(db: Session, principal: Principal, f: CalculationFinding) -> FindingOut:
    run = db.get(CalculationRun, f.run_id)
    assert run is not None
    evs = cf.events(db, f.id)
    names = _names(db, {f.raised_by, f.responded_by, f.resolved_by, *(e.actor_id for e in evs)})
    rule = db.get(MethodologyCalculationRule, f.target_calculation_rule_id) if f.target_calculation_rule_id else None
    from app.models import Project
    p = db.get(Project, f.project_id)
    org = p.organization_id if p else None
    can = lambda c: org is not None and principal.can_in_org(c, org)  # noqa: E731
    return FindingOut(
        id=f.id, finding_code=f.finding_code, project_id=f.project_id, monitoring_period_id=f.monitoring_period_id, run_id=f.run_id,
        run_code=run.run_code, category=f.category, category_label=CATEGORY_LABELS[f.category], blocking=f.blocking, title=f.title,
        description=f.description, target_input_seq=f.target_input_seq, target_output_seq=f.target_output_seq,
        target_calculation_rule_id=f.target_calculation_rule_id, target_rule_code=rule.rule_code if rule else None,
        target_source_type=f.target_source_type, target_source_id=f.target_source_id, evidence_document_id=f.evidence_document_id,
        status=f.status, raised_by_name=names.get(f.raised_by), raised_at=f.raised_at, response_text=f.response_text,
        response_document_id=f.response_document_id, responded_by_name=names.get(f.responded_by) if f.responded_by else None,
        responded_at=f.responded_at, resolution_note=f.resolution_note, resolved_by_name=names.get(f.resolved_by) if f.resolved_by else None,
        resolved_at=f.resolved_at, resolved_by_run_id=f.resolved_by_run_id, withdraw_reason=f.withdraw_reason, environment=f.environment,
        events=[FindingEventOut(seq=e.seq, action=e.action, from_status=e.from_status, to_status=e.to_status, actor_name=names.get(e.actor_id),
                                occurred_at=e.occurred_at, note=e.note, document_id=e.document_id, run_id=e.run_id) for e in evs],
        can_respond=f.status == "OPEN" and can(P.CALCULATION_MANAGE),
        can_resolve=f.status == "RESPONDED" and can(P.CALCULATION_REVIEW) and f.responded_by != principal.user_id,
        can_return=f.status == "RESPONDED" and can(P.CALCULATION_REVIEW),
        can_reopen=f.status == "RESOLVED" and can(P.CALCULATION_REVIEW),
        can_withdraw=f.status in ("OPEN", "RESPONDED") and can(P.CALCULATION_REVIEW) and f.raised_by == principal.user_id)


def report_out(db: Session, rep: CalculationReport, detail: bool = False) -> ReportOut:
    run = db.get(CalculationRun, rep.run_id)
    assert run is not None
    names = _names(db, {rep.generated_by})
    out = ReportOut(id=rep.id, report_code=rep.report_code, run_id=rep.run_id, run_code=run.run_code, version=rep.version,
                    generator_version=rep.generator_version, content_sha256=rep.content_sha256, pdf_sha256=rep.pdf_sha256,
                    document_id=rep.document_id, status=rep.status, superseded_by_report_id=rep.superseded_by_report_id,
                    superseded_at=rep.superseded_at, generated_by_name=names.get(rep.generated_by), generated_at=rep.generated_at,
                    environment=rep.environment, label=CALCULATED_LABEL)
    return ReportDetailOut(**out.model_dump(), content=json.loads(rep.content)) if detail else out


def readiness_out(db: Session, principal: Principal, r: CalculationReadinessReview) -> ReadinessOut:
    run = db.get(CalculationRun, r.run_id)
    rep = db.get(CalculationReport, r.report_id) if r.report_id else None
    names = _names(db, {r.created_by, r.submitted_by, r.decided_by})
    from app.models import Project
    p = db.get(Project, r.project_id)
    org = p.organization_id if p else None
    can = lambda c: org is not None and principal.can_in_org(c, org)  # noqa: E731
    independent = not cr.sod_reasons(db, r, principal.user_id)
    return ReadinessOut(
        id=r.id, readiness_code=r.readiness_code, project_id=r.project_id, monitoring_period_id=r.monitoring_period_id, run_id=r.run_id,
        run_code=run.run_code if run else "", report_id=r.report_id, report_code=rep.report_code if rep else None, status=r.status,
        checks=[ReadinessCheckOut(**c) for c in json.loads(r.checks or "[]")], manifest_sha256=r.manifest_sha256,
        created_by_name=names.get(r.created_by), created_at=r.created_at, submitted_by_name=names.get(r.submitted_by) if r.submitted_by else None,
        submitted_at=r.submitted_at, decided_by_name=names.get(r.decided_by) if r.decided_by else None, decided_at=r.decided_at,
        decision_notes=r.decision_notes, withdraw_reason=r.withdraw_reason, invalidated_at=r.invalidated_at,
        invalidation_reason=r.invalidation_reason, environment=r.environment,
        can_submit=r.status == "DRAFT" and can(P.CALCULATION_MANAGE),
        can_approve=r.status == "SUBMITTED" and can(P.CALCULATION_APPROVE) and independent,
        can_reject=r.status == "SUBMITTED" and can(P.CALCULATION_APPROVE) and independent,
        can_withdraw=r.status in ("DRAFT", "SUBMITTED") and can(P.CALCULATION_MANAGE))


def view_out(db: Session, principal: Principal, v: dict[str, Any]) -> ReadinessView:
    p, mp, run, rep = v["project"], v["period"], v["run"], v["report"]
    open_or_ready = any(r.status in ("DRAFT", "SUBMITTED", "READY") for r in v["reviews"])
    return ReadinessView(
        project_id=p.id, project_code=p.project_code, project_status=p.status, monitoring_period_id=mp.id, environment=p.environment,
        current_run_id=run.id if run else None, current_run_code=run.run_code if run else None, current_report_id=rep.id if rep else None,
        ready_to_submit=not v["blockers"], blockers=[Blocker(**b.as_dict()) for b in v["blockers"]],
        checks=[ReadinessCheckOut(**c) for c in v["checks"]], calculation_blockers=[Blocker(**b.as_dict()) for b in v["calculation_blockers"]],
        open_blocking_findings=v["open_blocking"], reviews=[readiness_out(db, principal, r) for r in v["reviews"]],
        can_create=run is not None and not open_or_ready and principal.can_in_org(P.CALCULATION_MANAGE, p.organization_id))


def manifest_out(r: CalculationReadinessReview) -> ManifestOut:
    return ManifestOut(readiness_id=r.id, readiness_code=r.readiness_code, status=r.status, manifest_sha256=r.manifest_sha256,
                       manifest=json.loads(r.manifest) if r.manifest else None)


def lineage_extras(db: Session, run: CalculationRun) -> dict[str, list[dict[str, Any]]]:
    """Phase 8A records of a run for the lineage view."""
    from app.services import calculation_report as crep
    finds = db.scalars(select(CalculationFinding).where(CalculationFinding.run_id == run.id).order_by(CalculationFinding.finding_code)).all()
    revs = db.scalars(select(CalculationReadinessReview).where(CalculationReadinessReview.run_id == run.id)
                      .order_by(CalculationReadinessReview.created_at)).all()
    return {
        "findings": [{**cf.summary(f), "id": str(f.id), "category_label": CATEGORY_LABELS[f.category]} for f in finds],
        "reports": [{"id": str(r.id), "report_code": r.report_code, "version": r.version, "status": r.status, "content_sha256": r.content_sha256,
                     "pdf_sha256": r.pdf_sha256, "generator_version": r.generator_version} for r in crep.reports_of(db, run.id)],
        "readiness": [{"id": str(r.id), "readiness_code": r.readiness_code, "status": r.status, "manifest_sha256": r.manifest_sha256,
                       "report_id": str(r.report_id) if r.report_id else None} for r in revs],
    }
