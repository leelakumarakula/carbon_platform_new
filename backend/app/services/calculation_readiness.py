"""Internal verification readiness per monitoring period (Phase 8A decisions B9, B12). READY means "internally approved for submission
to verification" — it is NOT verification, and the project status is not changed (it stays CALCULATED).

DRAFT → SUBMITTED → READY → INVALIDATED; SUBMITTED → REJECTED / WITHDRAWN; DRAFT → WITHDRAWN.

Deterministic prerequisites (re-checked when created, submitted, approved and whenever readiness is read):
the period's current APPROVED run (not superseded) · input and output hashes valid · inputs current (dataset still APPROVED with the
same hash, laboratory results still APPROVED at the same version, methodology lock and rule revisions unchanged) · the run's CURRENT
report exists, its hashes verify and it is not stale · no open blocking finding in the period · a production-ready module in production.
A READY review whose prerequisites no longer hold is INVALIDATED automatically.
"""
import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import record
from app.calculation import framework as fw
from app.core.config import get_settings
from app.core.context import RequestContext
from app.core.errors import Conflict, NotFound, PermissionDenied
from app.models import CalculationReadinessReview, CalculationReport, CalculationRun, MonitoringPeriod, MrvDataset, Project, WorkflowEvent
from app.models.base import utcnow
from app.models.preverification import OPEN_READINESS_STATUSES
from app.repositories.sequences import next_code
from app.schemas.preverification import READINESS_LABEL, READY_MEANING
from app.security.permissions import P
from app.security.principal import Principal
from app.services import calculation_findings as cf
from app.services import calculation_report as crep
from app.services import calculation_service as cs
from app.services.calculation_inputs import Blocker
from app.services.workflows import CALCULATION_READINESS_MACHINE

ENTITY = "calculation_readiness"


def _nf() -> NotFound:
    return NotFound("Readiness review not found.", error_code="READINESS_NOT_FOUND")


def current_run(db: Session, period_id: uuid.UUID) -> CalculationRun | None:
    return db.scalars(select(CalculationRun).where(CalculationRun.monitoring_period_id == period_id, CalculationRun.status == "APPROVED")).first()


def reviews(db: Session, period_id: uuid.UUID) -> list[CalculationReadinessReview]:
    return list(db.scalars(select(CalculationReadinessReview).where(CalculationReadinessReview.monitoring_period_id == period_id)
                           .order_by(CalculationReadinessReview.created_at.desc())).all())


def get_review(db: Session, principal: Principal, review_id: uuid.UUID, *codes: str) -> tuple[CalculationReadinessReview, Project]:
    r = db.get(CalculationReadinessReview, review_id)
    if r is None:
        raise _nf()
    try:
        return r, cs.project_for(db, principal, r.project_id, *codes)
    except NotFound:
        raise _nf() from None


def _check(key: str, label: str, problems: list[str]) -> dict[str, Any]:
    return {"key": key, "label": label, "result": "FAIL" if problems else "PASS", "details": problems}


def evaluate(db: Session, period_id: uuid.UUID, run: CalculationRun | None) -> tuple[list[Blocker], list[dict[str, Any]], CalculationReport | None]:
    """All deterministic prerequisites for `run` (expected to be the period's current APPROVED run)."""
    blockers: list[Blocker] = []
    checks: list[dict[str, Any]] = []
    approved = current_run(db, period_id)
    if run is None or approved is None or approved.id != run.id:
        msg = ("The reporting period has no APPROVED calculation run." if approved is None
               else "The run is no longer the period's current APPROVED run (superseded).")
        blockers.append(Blocker("NO_APPROVED_CALCULATION", msg, None, {"current_run": approved.run_code if approved else None}))
        checks.append(_check("approved_run", "Current APPROVED calculation run (not superseded)", [msg]))
        return blockers, checks, None
    checks.append(_check("approved_run", "Current APPROVED calculation run (not superseded)", []))
    snap = json.loads(run.input_snapshot or "{}")
    hash_problems = []
    if fw.sha256(snap) != run.input_sha256:
        hash_problems.append("input snapshot SHA-256 mismatch")
    records = cs.stored_output_records(db, run.id)
    if fw.output_hash(records, run.module_code or "", run.module_version or "", run.engine_version) != run.output_sha256:
        hash_problems.append("output SHA-256 mismatch")
    checks.append(_check("run_hashes", "Input and output hashes valid", hash_problems))
    if hash_problems:
        blockers.append(Blocker("INPUT_SNAPSHOT_MISMATCH", "The run's hashes do not verify.", None, {"problems": hash_problems}))
    stale = cs.current_problems(db, run, snap) if snap else ["no snapshot"]
    checks.append(_check("inputs_current", "Dataset approved, laboratory results approved, methodology lock unchanged", stale))
    if stale:
        blockers.append(Blocker("INPUTS_OUT_OF_DATE", "Frozen inputs are no longer current.", None, {"problems": stale}))
    rep = crep.current_report(db, run.id)
    rep_problems: list[str] = []
    if rep is None:
        rep_problems.append("no CURRENT calculation report for the run")
        blockers.append(Blocker("REPORT_MISSING", "Generate the calculation report of the approved run first."))
    else:
        v = crep.verify(db, rep)
        if not v["valid"]:
            rep_problems += v["problems"]
            blockers.append(Blocker("REPORT_INTEGRITY_FAILED", "The calculation report does not verify.", None, {"problems": v["problems"]}))
        elif v["stale"]:
            rep_problems.append("the report content is out of date (findings or QA changed since it was generated)")
            blockers.append(Blocker("REPORT_STALE", "Regenerate the calculation report: its content is out of date."))
    checks.append(_check("report", "Calculation report of this run exists, verifies and is current", rep_problems))
    open_f = cf.open_blocking(db, period_id)
    checks.append(_check("findings", "No open blocking finding in the reporting period", [f"{f.finding_code} {f.status}" for f in open_f]))
    if open_f:
        blockers.append(Blocker("OPEN_BLOCKING_FINDINGS", "Open blocking findings must be resolved or withdrawn.", None,
                                {"findings": [f.finding_code for f in open_f]}))
    prod = []
    if get_settings().is_production and run.module_readiness != fw.PRODUCTION_READY:
        prod.append(f"module {run.module_code} is {run.module_readiness}")
        blockers.append(Blocker("NOT_PRODUCTION_READY", "A NOT_PRODUCTION_READY module is blocked in production."))
    checks.append(_check("module_readiness", "Production-ready module in production", prod))
    return blockers, checks, rep


def build_manifest(db: Session, run: CalculationRun, rep: CalculationReport) -> dict[str, Any]:
    """Canonical package manifest: references and hashes of what already exists (no new evidence store)."""
    snap = json.loads(run.input_snapshot or "{}")
    ds = db.get(MrvDataset, run.mrv_dataset_id) if run.mrv_dataset_id else None
    ds_snap = json.loads(ds.snapshot) if ds and ds.snapshot else {}
    meth = snap.get("methodology", {})
    return {
        "schema": "pre-verification-manifest-v1",
        "label": READINESS_LABEL,
        "meaning": READY_MEANING,
        "project": snap.get("project"),
        "reporting_period": snap.get("reporting_period"),
        "crediting_period": snap.get("crediting_period"),
        "methodology": {k: meth.get(k) for k in ("methodology_id", "code", "version_id", "version_label", "is_demo_illustrative",
                                                 "project_methodology_id", "calculation_rules_version", "monitoring_rules_version")},
        "dataset": snap.get("dataset"),
        "mrv_evidence": [{"id": e["id"], "type": e["type"], "checksum_sha256": e["checksum_sha256"]} for e in ds_snap.get("evidence", [])],
        "laboratory_results": [{"result_id": r["source_id"], "version": r["source_version"], "sample": r["source_code"],
                                "report_sha256": r["source_sha256"]} for r in snap.get("inputs", []) if r["source_type"] == "LAB_RESULT"],
        "calculation_run": {"id": str(run.id), "run_code": run.run_code, "input_sha256": run.input_sha256, "output_sha256": run.output_sha256,
                            "net_result": run.net_result, "net_unit": run.net_unit, "module": run.module_code, "module_version": run.module_version,
                            "module_readiness": run.module_readiness, "engine_version": run.engine_version},
        "calculation_report": {"id": str(rep.id), "report_code": rep.report_code, "version": rep.version, "content_sha256": rep.content_sha256,
                               "pdf_sha256": rep.pdf_sha256, "generator_version": rep.generator_version},
        "findings": [cf.summary(f) for f in cf.findings_of_period(db, run.monitoring_period_id)],
        "qa_reviews": [{"id": str(r.id), "result": r.result, "completed_at": r.completed_at.isoformat() + "Z"}
                       for r in cs.qa_reviews(db, run.id) if r.completed_at is not None],
    }


# ---------------------------------------------------------------- transitions
def _transition(db: Session, ctx: RequestContext, r: CalculationReadinessReview, to: str, action: str, reason: str | None,
                org: uuid.UUID | None, **extra: Any) -> None:
    frm = r.status
    CALCULATION_READINESS_MACHINE.assert_transition(frm, to)
    db.add(WorkflowEvent(entity_type=ENTITY, entity_id=str(r.id), from_status=frm, to_status=to, user_id=ctx.user_id, reason=reason,
                         request_id=ctx.request_id))
    r.status = to
    record(db, ctx, action, ENTITY, r.id, {"status": frm},
           {"status": to, "readiness_code": r.readiness_code, "run_id": r.run_id, "report_id": r.report_id, "manifest_sha256": r.manifest_sha256,
            **extra}, reason, organization_id=org)


def invalidate_period(db: Session, ctx: RequestContext, period_id: uuid.UUID, reason: str) -> None:
    """B12: a READY review of the period becomes INVALIDATED (caller commits)."""
    for r in db.scalars(select(CalculationReadinessReview).where(CalculationReadinessReview.monitoring_period_id == period_id,
                                                                 CalculationReadinessReview.status == "READY")).all():
        p = db.get(Project, r.project_id)
        r.invalidated_at, r.invalidation_reason = utcnow(), reason[:2000]
        _transition(db, ctx, r, "INVALIDATED", "CALCULATION_READINESS_INVALIDATED", reason, p.organization_id if p else None)


def refresh(db: Session, ctx: RequestContext, period_id: uuid.UUID) -> None:
    """Re-check a READY review on read / before use; invalidate it when a prerequisite no longer holds."""
    ready = db.scalars(select(CalculationReadinessReview).where(CalculationReadinessReview.monitoring_period_id == period_id,
                                                                CalculationReadinessReview.status == "READY")).first()
    if ready is None:
        return
    run = db.get(CalculationRun, ready.run_id)
    blockers, _, rep = evaluate(db, period_id, run)
    if not blockers and rep is not None and rep.id != ready.report_id:
        blockers.append(Blocker("REPORT_STALE", "The run's current report is not the one this readiness was approved with."))
    if blockers:
        invalidate_period(db, ctx, period_id, "; ".join(f"{b.code}: {b.message}" for b in blockers))
        db.commit()


def view(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID, period_id: uuid.UUID) -> dict[str, Any]:
    p = cs.project_for(db, principal, project_id)
    mp = db.get(MonitoringPeriod, period_id)
    if mp is None or mp.project_id != p.id:
        raise NotFound("Monitoring period not found.", error_code="PERIOD_NOT_FOUND")
    refresh(db, ctx, period_id)
    run = current_run(db, period_id)
    blockers, checks, rep = evaluate(db, period_id, run)
    from app.services import calculation_inputs as ci
    calc = ci.evaluate(db, p, mp)    # Phase 7 readiness with the application registry (e.g. NO_CALCULATION_MODULE)
    return {"project": p, "period": mp, "run": run, "report": rep, "blockers": blockers, "checks": checks,
            "calculation_blockers": calc.blockers, "open_blocking": [f.finding_code for f in cf.open_blocking(db, period_id)],
            "reviews": reviews(db, period_id)}


def create(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID, period_id: uuid.UUID) -> CalculationReadinessReview:
    p = cs.project_for(db, principal, project_id, P.CALCULATION_MANAGE)
    mp = db.get(MonitoringPeriod, period_id)
    if mp is None or mp.project_id != p.id:
        raise NotFound("Monitoring period not found.", error_code="PERIOD_NOT_FOUND")
    refresh(db, ctx, period_id)
    run = current_run(db, period_id)
    if run is None:
        raise Conflict("Readiness needs the period's current APPROVED calculation run.", error_code="NO_APPROVED_CALCULATION")
    existing = next((r for r in reviews(db, period_id) if r.status in (*OPEN_READINESS_STATUSES, "READY")), None)
    if existing is not None:
        raise Conflict(f"Readiness {existing.readiness_code} is already {existing.status} for this period.", error_code="READINESS_EXISTS")
    r = CalculationReadinessReview(readiness_code=next_code(db, "calculation_readiness", utcnow().year), project_id=p.id,
                                   monitoring_period_id=period_id, run_id=run.id, status="DRAFT", created_by=principal.user_id,
                                   environment=run.environment)
    db.add(r)
    db.flush()
    db.add(WorkflowEvent(entity_type=ENTITY, entity_id=str(r.id), from_status=None, to_status="DRAFT", user_id=ctx.user_id, reason=None,
                         request_id=ctx.request_id))
    record(db, ctx, "CALCULATION_READINESS_CREATED", ENTITY, r.id, None,
           {"status": "DRAFT", "readiness_code": r.readiness_code, "run_id": run.id, "run_code": run.run_code}, None,
           organization_id=p.organization_id)
    db.commit()
    return r


def _blocked(blockers: list[Blocker]) -> Conflict:
    return Conflict(blockers[0].message, error_code=blockers[0].code, details={"blockers": [b.as_dict() for b in blockers]})


def submit(db: Session, ctx: RequestContext, principal: Principal, review_id: uuid.UUID) -> CalculationReadinessReview:
    r, p = get_review(db, principal, review_id, P.CALCULATION_MANAGE)
    if r.status != "DRAFT":
        raise Conflict(f"Only a DRAFT readiness can be submitted (it is {r.status}).", error_code="READINESS_NOT_DRAFT")
    blockers, checks, rep = evaluate(db, r.monitoring_period_id, db.get(CalculationRun, r.run_id))
    if blockers:
        raise _blocked(blockers)
    assert rep is not None
    r.checks, r.report_id, r.submitted_by, r.submitted_at = json.dumps(checks), rep.id, principal.user_id, utcnow()
    _transition(db, ctx, r, "SUBMITTED", "CALCULATION_READINESS_SUBMITTED", None, p.organization_id)
    db.commit()
    return r


def sod_reasons(db: Session, r: CalculationReadinessReview, user_id: uuid.UUID) -> list[str]:
    run = db.get(CalculationRun, r.run_id)
    out = ["you submitted this readiness"] if r.submitted_by == user_id else []
    return out + (cs.sod_reasons(run, user_id) if run else [])


def _require_sod(db: Session, r: CalculationReadinessReview, principal: Principal) -> None:
    reasons = sod_reasons(db, r, principal.user_id)
    if reasons:
        raise PermissionDenied("Readiness must be decided by someone else: " + "; ".join(reasons) + ".", error_code="SEPARATION_OF_DUTIES",
                               details={"reasons": reasons})


def approve(db: Session, ctx: RequestContext, principal: Principal, review_id: uuid.UUID, notes: str) -> CalculationReadinessReview:
    r, p = get_review(db, principal, review_id, P.CALCULATION_APPROVE)
    if r.status != "SUBMITTED":
        raise Conflict(f"Only a SUBMITTED readiness can be approved (it is {r.status}).", error_code="READINESS_NOT_SUBMITTED")
    _require_sod(db, r, principal)
    run = db.get(CalculationRun, r.run_id)
    blockers, checks, rep = evaluate(db, r.monitoring_period_id, run)
    if not blockers and rep is not None and rep.id != r.report_id:
        blockers.append(Blocker("REPORT_STALE", "The run's report changed after submission; withdraw and submit again."))
    if blockers:
        raise _blocked(blockers)
    assert run is not None and rep is not None
    manifest = build_manifest(db, run, rep)
    r.checks, r.manifest, r.manifest_sha256 = json.dumps(checks), fw.canonical_json(manifest), fw.sha256(manifest)
    r.decided_by, r.decided_at, r.decision_notes = principal.user_id, utcnow(), notes
    _transition(db, ctx, r, "READY", "CALCULATION_READINESS_READY", notes, p.organization_id, meaning=READY_MEANING)
    db.commit()
    return r


def reject(db: Session, ctx: RequestContext, principal: Principal, review_id: uuid.UUID, notes: str) -> CalculationReadinessReview:
    r, p = get_review(db, principal, review_id, P.CALCULATION_APPROVE)
    if r.status != "SUBMITTED":
        raise Conflict(f"Only a SUBMITTED readiness can be rejected (it is {r.status}).", error_code="READINESS_NOT_SUBMITTED")
    _require_sod(db, r, principal)
    r.decided_by, r.decided_at, r.decision_notes = principal.user_id, utcnow(), notes
    _transition(db, ctx, r, "REJECTED", "CALCULATION_READINESS_REJECTED", notes, p.organization_id)
    db.commit()
    return r


def withdraw(db: Session, ctx: RequestContext, principal: Principal, review_id: uuid.UUID, reason: str) -> CalculationReadinessReview:
    r, p = get_review(db, principal, review_id, P.CALCULATION_MANAGE)
    if r.status not in OPEN_READINESS_STATUSES:
        raise Conflict(f"Only a DRAFT or SUBMITTED readiness can be withdrawn (it is {r.status}).", error_code="READINESS_NOT_OPEN")
    r.withdrawn_by, r.withdrawn_at, r.withdraw_reason = principal.user_id, utcnow(), reason
    _transition(db, ctx, r, "WITHDRAWN", "CALCULATION_READINESS_WITHDRAWN", reason, p.organization_id)
    db.commit()
    return r
