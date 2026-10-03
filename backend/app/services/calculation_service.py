"""Phase 7 calculation workflow (decisions A1–A22, C1–C7).

DRAFT → INPUTS_FROZEN → CALCULATED → QA_REVIEW → APPROVED (→ SUPERSEDED); DRAFT / INPUTS_FROZEN → BLOCKED or CANCELLED;
QA_REVIEW → REJECTED. A run is never edited after its lifecycle points; a correction is a new run (recalculation).

- readiness blocks the input freeze (C3): the run becomes BLOCKED with the first blocker's code and every blocker in details;
  no module → CONFIGURATION_REQUIRED, reason NO_CALCULATION_MODULE (C4). The project moves MONITORING → CALCULATION_READY only
  after a successful freeze, and CALCULATION_READY → CALCULATED only when its first run is approved (A17)
- execution is synchronous and reads only the frozen snapshot (A5, A18); currency of the frozen sources is re-checked first
  (INPUTS_OUT_OF_DATE) and the module must be the same module and version that was frozen
- QA / approval mirror MRV (A15, C7): reviewer and approver are never the run's creator, freezer, executor or submitter
- no request carries a calculated value: every value comes from the registered module (A1)
"""
import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import record
from app.calculation import framework as fw
from app.calculation.registry import Resolver
from app.calculation.registry import resolve as registry_resolve
from app.core.config import get_settings
from app.core.context import RequestContext
from app.core.errors import Conflict, NotFound, PermissionDenied
from app.models import (
    CalculationInput,
    CalculationOutput,
    CalculationQaReview,
    CalculationRun,
    LabResult,
    MethodologyCalculationRule,
    MonitoringPeriod,
    MrvDataset,
    Project,
    ProjectCreditingPeriod,
    WorkflowEvent,
)
from app.models.base import utcnow
from app.models.calculation import OPEN_RUN_STATUSES
from app.repositories import projects as project_repo
from app.repositories.sequences import next_code
from app.schemas.calculation import RunIn
from app.security.permissions import P
from app.security.principal import Principal
from app.services import calculation_inputs as ci
from app.services import project_service as psvc
from app.services.workflows import CALCULATION_RUN_MACHINE

ENTITY = "calculation_run"
VISIBLE = (P.CALCULATION_READ, P.CALCULATION_MANAGE, P.CALCULATION_REVIEW, P.CALCULATION_APPROVE)
RECALCULABLE = ("APPROVED", "SUPERSEDED", "REJECTED", "BLOCKED", "CANCELLED")


# ---------------------------------------------------------------- access
def _project_nf() -> NotFound:
    return NotFound("Project not found.", error_code="PROJECT_NOT_FOUND")


def _run_nf() -> NotFound:
    return NotFound("Calculation run not found.", error_code="CALCULATION_RUN_NOT_FOUND")


def project_for(db: Session, principal: Principal, project_id: uuid.UUID, *codes: str) -> Project:
    """Organization-scoped: 403 when the project is visible but the action is not allowed, 404 otherwise."""
    p = project_repo.get(db, project_id)
    if p is None:
        raise _project_nf()
    needed = codes or (P.CALCULATION_READ,)
    if any(principal.can_in_org(c, p.organization_id) for c in needed):
        return p
    if any(principal.can_in_org(c, p.organization_id) for c in VISIBLE):
        raise PermissionDenied(details={"required_permission": " or ".join(needed)})
    raise _project_nf()


def get_run(db: Session, principal: Principal, run_id: uuid.UUID, *codes: str) -> tuple[CalculationRun, Project]:
    run = db.get(CalculationRun, run_id)
    if run is None:
        raise _run_nf()
    try:
        return run, project_for(db, principal, run.project_id, *codes)
    except NotFound:
        raise _run_nf() from None


def projects(db: Session, principal: Principal) -> list[tuple[Project, list[MonitoringPeriod]]]:
    """Projects in monitoring or later that the caller may read calculations of (organization-scoped; needs only calculation.read)."""
    stmt = select(Project).where(Project.status.in_(ci.CALC_PROJECT_STATES))
    scope = principal.scope_for(P.CALCULATION_READ)
    if scope is not None:
        stmt = stmt.where(Project.organization_id.in_(scope))
    out = []
    for p in db.scalars(stmt.order_by(Project.project_code)).all():
        periods = list(db.scalars(select(MonitoringPeriod).where(MonitoringPeriod.project_id == p.id).order_by(MonitoringPeriod.period_number)).all())
        out.append((p, periods))
    return out


def runs(db: Session, principal: Principal, project_id: uuid.UUID, period_id: uuid.UUID | None = None) -> list[CalculationRun]:
    project_for(db, principal, project_id)
    stmt = select(CalculationRun).where(CalculationRun.project_id == project_id)
    if period_id:
        stmt = stmt.where(CalculationRun.monitoring_period_id == period_id)
    return list(db.scalars(stmt.order_by(CalculationRun.created_at.desc())).all())


def _period(db: Session, p: Project, period_id: uuid.UUID) -> MonitoringPeriod:
    mp = db.get(MonitoringPeriod, period_id)
    if mp is None or mp.project_id != p.id:
        raise NotFound("Monitoring period not found.", error_code="PERIOD_NOT_FOUND")
    return mp


def _crediting(db: Session, p: Project, crediting_id: uuid.UUID | None) -> ProjectCreditingPeriod | None:
    if crediting_id is None:
        return None
    cp = db.get(ProjectCreditingPeriod, crediting_id)
    if cp is None or cp.project_id != p.id:
        raise NotFound("Crediting period not found.", error_code="CREDITING_PERIOD_NOT_FOUND")
    return cp


# ---------------------------------------------------------------- audit / transitions
def _payload(run: CalculationRun, **extra: Any) -> dict[str, Any]:
    return {"run_code": run.run_code, "status": run.status, "methodology_version_id": run.methodology_version_id,
            "calculation_rules_version": run.calculation_rules_version, "module_code": run.module_code, "module_version": run.module_version,
            "engine_version": run.engine_version, "input_sha256": run.input_sha256, "output_sha256": run.output_sha256,
            "net_result": run.net_result, "net_unit": run.net_unit, **extra}


def _transition(db: Session, ctx: RequestContext, p: Project, run: CalculationRun, to: str, action: str, reason: str | None,
                **extra: Any) -> None:
    frm = run.status
    CALCULATION_RUN_MACHINE.assert_transition(frm, to)
    db.add(WorkflowEvent(entity_type=ENTITY, entity_id=str(run.id), from_status=frm, to_status=to, user_id=ctx.user_id, reason=reason,
                         request_id=ctx.request_id))
    run.status = to
    record(db, ctx, action, ENTITY, run.id, {"status": frm}, _payload(run, **extra), reason, organization_id=p.organization_id)


def _close(db: Session, ctx: RequestContext, p: Project, run: CalculationRun, to: str, action: str, reason: str,
           blockers: list[dict[str, Any]] | None = None) -> None:
    run.closed_by, run.closed_at, run.status_reason = ctx.user_id, utcnow(), reason[:1000]
    if blockers is not None:
        run.blockers = json.dumps(blockers)
    _transition(db, ctx, p, run, to, action, reason, blockers=blockers)


def _block(db: Session, ctx: RequestContext, p: Project, run: CalculationRun, blockers: list[ci.Blocker]) -> Conflict:
    """Record BLOCKED (committed) and return the error to raise (first blocker's code; all blockers in details)."""
    first = blockers[0]
    _close(db, ctx, p, run, "BLOCKED", "CALCULATION_BLOCKED", f"{first.code}: {first.message}", [b.as_dict() for b in blockers])
    db.commit()
    return Conflict(first.message, error_code=first.code,
                    details={"reason": first.reason, "run_code": run.run_code, "blockers": [b.as_dict() for b in blockers]})


# ---------------------------------------------------------------- readiness / create
def readiness(db: Session, principal: Principal, project_id: uuid.UUID, period_id: uuid.UUID, crediting_id: uuid.UUID | None = None,
              resolver: Resolver | None = None) -> ci.Evaluation:
    p = project_for(db, principal, project_id)
    return ci.evaluate(db, p, _period(db, p, period_id), _crediting(db, p, crediting_id), resolver)


def create_run(db: Session, ctx: RequestContext, principal: Principal, data: RunIn,
               recalculation_of: CalculationRun | None = None, recalculation_reason: str | None = None) -> CalculationRun:
    p = project_for(db, principal, data.project_id, P.CALCULATION_MANAGE)
    mp = _period(db, p, data.monitoring_period_id)
    cp = _crediting(db, p, data.crediting_period_id)
    if cp is not None and not (cp.start_date <= mp.start_date and mp.end_date <= cp.end_date):
        raise Conflict("The reporting period is not inside the selected crediting period.", error_code="OUTSIDE_CREDITING_PERIOD")
    pm = ci.locked(db, p)
    if pm is None or p.methodology_status != "CONFIRMED":
        raise Conflict("The project's methodology and version must be locked before a calculation.", error_code="METHODOLOGY_NOT_LOCKED")
    if p.status not in ci.CALC_PROJECT_STATES:
        raise Conflict(f"Calculation needs a project in monitoring (it is {p.status}).", error_code="PROJECT_NOT_IN_MRV")
    if db.scalars(select(CalculationRun).where(CalculationRun.monitoring_period_id == mp.id,
                                               CalculationRun.status.in_(OPEN_RUN_STATUSES))).first():
        raise Conflict("This reporting period already has an open calculation run.", error_code="OPEN_RUN_EXISTS")
    from app.models import MethodologyVersion
    v = db.get(MethodologyVersion, pm.methodology_version_id)
    assert v is not None
    run = CalculationRun(run_code=next_code(db, "calculation_run", utcnow().year), project_id=p.id, monitoring_period_id=mp.id,
                         crediting_period_id=cp.id if cp else None, methodology_id=pm.methodology_id, methodology_version_id=v.id,
                         project_methodology_id=pm.id, calculation_rules_version=pm.calculation_rules_version,
                         monitoring_rules_version=pm.monitoring_rules_version, engine_version=fw.ENGINE_VERSION, notes=data.notes,
                         environment=p.environment, created_by=principal.user_id, status="DRAFT",
                         recalculation_of_run_id=recalculation_of.id if recalculation_of else None, recalculation_reason=recalculation_reason)
    db.add(run)
    db.flush()
    db.add(WorkflowEvent(entity_type=ENTITY, entity_id=str(run.id), from_status=None, to_status="DRAFT", user_id=ctx.user_id,
                         reason=recalculation_reason, request_id=ctx.request_id))
    record(db, ctx, "CALCULATION_RUN_CREATED", ENTITY, run.id, None,
           _payload(run, project_id=p.id, monitoring_period_id=mp.id, recalculation_of_run_id=run.recalculation_of_run_id),
           recalculation_reason, organization_id=p.organization_id)
    db.commit()
    return run


def recalculate(db: Session, ctx: RequestContext, principal: Principal, run_id: uuid.UUID, reason: str) -> CalculationRun:
    """A14: a new run (own snapshot, hashes, outputs, QA, approval) linked to the previous one; nothing is overwritten."""
    prev, p = get_run(db, principal, run_id, P.CALCULATION_MANAGE)
    if prev.status not in RECALCULABLE:
        raise Conflict(f"Run {prev.run_code} is still open ({prev.status}); finish or cancel it first.", error_code="OPEN_RUN_EXISTS")
    return create_run(db, ctx, principal, RunIn(project_id=p.id, monitoring_period_id=prev.monitoring_period_id,
                                                crediting_period_id=prev.crediting_period_id), prev, reason)


# ---------------------------------------------------------------- freeze / execute
def freeze(db: Session, ctx: RequestContext, principal: Principal, run_id: uuid.UUID, resolver: Resolver | None = None) -> CalculationRun:
    run, p = get_run(db, principal, run_id, P.CALCULATION_MANAGE)
    if run.status != "DRAFT":
        raise Conflict(f"Only a DRAFT run can be frozen (it is {run.status}).", error_code="RUN_NOT_EDITABLE")
    mp = db.get(MonitoringPeriod, run.monitoring_period_id)
    assert mp is not None
    ev = ci.evaluate(db, p, mp, _crediting(db, p, run.crediting_period_id), resolver)
    if not ev.ready or ev.module is None or ev.snapshot is None:
        raise _block(db, ctx, p, run, ev.blockers or [ci.Blocker("CONFIGURATION_REQUIRED", "Readiness failed.")])
    m = ev.module
    assert ev.dataset is not None
    run.mrv_dataset_id = ev.dataset.id
    run.module_code, run.module_version, run.module_readiness = m.code, m.version, m.readiness
    run.input_snapshot = fw.canonical_json(ev.snapshot)
    run.input_sha256 = ev.snapshot_sha256
    run.frozen_by, run.frozen_at = principal.user_id, utcnow()
    for r in ev.inputs:
        db.add(CalculationInput(run_id=run.id, seq=r["seq"], variable_code=r["variable"], source_type=r["source_type"],
                                source_id=_uuid(r["source_id"]), source_version=r["source_version"], source_code=r["source_code"],
                                value=r["value"], value_kind=r["value_kind"], unit=r["unit"], level=r["level"],
                                stratum_id=_uuid(r["stratum_id"]), farm_id=_uuid(r["farm_id"]), sampling_point_id=_uuid(r["sampling_point_id"]),
                                field_collection_id=_uuid(r["field_collection_id"]), sample_id=_uuid(r["sample_id"]),
                                root_sample_id=_uuid(r["root_sample_id"]), monitoring_rule_id=_uuid(r["monitoring_rule_id"]),
                                plan_measurement_id=_uuid(r["plan_measurement_id"]), requirement_source=r["requirement_source"],
                                source_reference=r["source_reference"], source_sha256=r["source_sha256"]))
    _transition(db, ctx, p, run, "INPUTS_FROZEN", "CALCULATION_INPUTS_FROZEN", None, dataset_id=ev.dataset.id, input_rows=len(ev.inputs),
                warnings=ev.warnings)
    if p.status == "MONITORING":   # A17: only after a successful readiness check and input freeze
        psvc.transition_to(db, ctx, p, "CALCULATION_READY", "PROJECT_STATUS_CHANGED", "CALCULATION_READY",
                           f"Calculation inputs frozen ({run.run_code})")
    db.commit()
    return run


def current_problems(db: Session, run: CalculationRun, snapshot: dict[str, Any]) -> list[str]:
    """Frozen sources that are no longer current (decision A6: an outdated input blocks; nothing is substituted)."""
    out = []
    ds = db.get(MrvDataset, uuid.UUID(snapshot["dataset"]["id"]))
    if ds is None or ds.status != "APPROVED" or ds.snapshot_sha256 != snapshot["dataset"]["snapshot_sha256"]:
        out.append(f"MRV dataset {snapshot['dataset']['code']} is no longer the APPROVED dataset ({ds.status if ds else 'missing'}).")
    for row in snapshot["inputs"]:
        if row["source_type"] == "LAB_RESULT":
            res = db.get(LabResult, uuid.UUID(row["source_id"]))
            if res is None or res.status != "APPROVED" or res.version != row["source_version"]:
                out.append(f"Laboratory result for {row['source_code']} is no longer APPROVED ({res.status if res else 'missing'}).")
    p = db.get(Project, run.project_id)
    pm = ci.locked(db, p) if p else None
    meth = snapshot["methodology"]
    if (pm is None or str(pm.id) != meth["project_methodology_id"] or pm.calculation_rules_version != meth["calculation_rules_version"]
            or pm.monitoring_rules_version != meth["monitoring_rules_version"]):
        out.append("The project's methodology lock or its rule revisions changed since the inputs were frozen.")
    return out


def execute(db: Session, ctx: RequestContext, principal: Principal, run_id: uuid.UUID, resolver: Resolver | None = None) -> CalculationRun:
    run, p = get_run(db, principal, run_id, P.CALCULATION_MANAGE)
    if run.status != "INPUTS_FROZEN":
        raise Conflict(f"Only a run with frozen inputs can be executed (it is {run.status}).", error_code="RUN_NOT_EDITABLE")
    snapshot = json.loads(run.input_snapshot or "{}")
    if fw.sha256(snapshot) != run.input_sha256:
        raise _block(db, ctx, p, run, [ci.Blocker("INPUT_SNAPSHOT_MISMATCH", "The frozen input snapshot does not match its SHA-256.")])
    stale = current_problems(db, run, snapshot)
    if stale:
        raise _block(db, ctx, p, run, [ci.Blocker("INPUTS_OUT_OF_DATE", "Frozen inputs are out of date; create a new run.", None,
                                                  {"problems": stale})])
    module = (resolver or registry_resolve)(snapshot["methodology"]["code"], snapshot["methodology"]["version_label"])
    if module is None:
        raise _block(db, ctx, p, run, [ci.Blocker("CONFIGURATION_REQUIRED", "No calculation module is registered for this methodology version.",
                                                  "NO_CALCULATION_MODULE")])
    if module.code != run.module_code or module.version != run.module_version or module.declaration() != snapshot["module"]:
        raise _block(db, ctx, p, run, [ci.Blocker("INPUTS_OUT_OF_DATE", "The calculation module changed since the inputs were frozen.",
                                                  "MODULE_CHANGED")])
    if module.readiness != fw.PRODUCTION_READY and get_settings().is_production:
        raise _block(db, ctx, p, run, [ci.Blocker("NOT_PRODUCTION_READY", f"Module {module.code} is NOT_PRODUCTION_READY (blocked in production).")])
    try:
        result = fw.execute(module, snapshot)
    except fw.CalculationBlocked as e:
        raise _block(db, ctx, p, run, [ci.Blocker(e.code, e.message, e.details.get("reason"), e.details)]) from None
    rule_ids = {r["rule_code"]: (r["id"], r["equation_reference"]) for r in snapshot["methodology"]["calculation_rules"]}
    for o in result.outputs:
        rid, eq = rule_ids[o["rule_code"]]
        db.add(CalculationOutput(run_id=run.id, seq=o["seq"], step=o["step"], output_code=o["output_code"], calculation_rule_id=uuid.UUID(rid),
                                 rule_code=o["rule_code"], equation_reference=eq, value=o["value"], unit=o["unit"], level=o["level"],
                                 entity_id=_uuid(o["entity_id"]), input_refs=json.dumps({"inputs": o["inputs"], "outputs": o["outputs"]}),
                                 is_final=o["is_final"]))
    run.output_sha256, run.net_result, run.net_unit = result.output_sha256, result.net_value, result.net_unit
    run.executed_by, run.executed_at = principal.user_id, utcnow()
    _transition(db, ctx, p, run, "CALCULATED", "CALCULATION_EXECUTED", None, outputs=len(result.outputs))
    db.commit()
    return run


def stored_output_records(db: Session, run_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = outputs(db, run_id)
    return [{"seq": o.seq, "step": o.step, "output_code": o.output_code, "rule_code": o.rule_code, "value": o.value, "unit": o.unit,
             "level": o.level, "entity_id": str(o.entity_id) if o.entity_id else None, "inputs": json.loads(o.input_refs)["inputs"],
             "outputs": json.loads(o.input_refs)["outputs"], "is_final": o.is_final} for o in rows]


def inputs(db: Session, run_id: uuid.UUID) -> list[CalculationInput]:
    return list(db.scalars(select(CalculationInput).where(CalculationInput.run_id == run_id).order_by(CalculationInput.seq)).all())


def outputs(db: Session, run_id: uuid.UUID) -> list[CalculationOutput]:
    return list(db.scalars(select(CalculationOutput).where(CalculationOutput.run_id == run_id).order_by(CalculationOutput.seq)).all())


# ---------------------------------------------------------------- submit / cancel
def submit(db: Session, ctx: RequestContext, principal: Principal, run_id: uuid.UUID) -> CalculationRun:
    run, p = get_run(db, principal, run_id, P.CALCULATION_MANAGE)
    if run.status != "CALCULATED":
        raise Conflict(f"Only a CALCULATED run can be submitted for QA (it is {run.status}).", error_code="RUN_NOT_EDITABLE")
    run.submitted_by, run.submitted_at = principal.user_id, utcnow()
    _transition(db, ctx, p, run, "QA_REVIEW", "CALCULATION_SUBMITTED", None)
    db.commit()
    return run


def cancel(db: Session, ctx: RequestContext, principal: Principal, run_id: uuid.UUID, reason: str) -> CalculationRun:
    run, p = get_run(db, principal, run_id, P.CALCULATION_MANAGE)
    if run.status not in ("DRAFT", "INPUTS_FROZEN"):
        raise Conflict(f"Only DRAFT or INPUTS_FROZEN runs can be cancelled (it is {run.status}).", error_code="RUN_NOT_EDITABLE")
    _close(db, ctx, p, run, "CANCELLED", "CALCULATION_RUN_CANCELLED", reason)
    db.commit()
    return run


# ---------------------------------------------------------------- QA / approval
def sod_reasons(run: CalculationRun, user_id: uuid.UUID) -> list[str]:
    out = []
    for attr, what in (("created_by", "created"), ("frozen_by", "froze the inputs of"), ("executed_by", "executed"),
                       ("submitted_by", "submitted")):
        if getattr(run, attr) == user_id:
            out.append(f"you {what} this run")
    return out


def _require_sod(run: CalculationRun, principal: Principal) -> None:
    reasons = sod_reasons(run, principal.user_id)
    if reasons:
        raise PermissionDenied("Calculation QA and approval must be done by someone else: " + "; ".join(reasons) + ".",
                               error_code="SEPARATION_OF_DUTIES", details={"reasons": reasons})


def qa_reviews(db: Session, run_id: uuid.UUID) -> list[CalculationQaReview]:
    return list(db.scalars(select(CalculationQaReview).where(CalculationQaReview.run_id == run_id)
                           .order_by(CalculationQaReview.started_at)).all())


def qa_checks(db: Session, run: CalculationRun, reviewer_id: uuid.UUID | None, resolver: Resolver | None = None) -> list[dict[str, Any]]:
    from app.services import calculation_qa
    return calculation_qa.checks(db, run, reviewer_id, resolver or registry_resolve)


def start_qa(db: Session, ctx: RequestContext, principal: Principal, run_id: uuid.UUID) -> CalculationQaReview:
    run, p = get_run(db, principal, run_id, P.CALCULATION_REVIEW)
    if run.status != "QA_REVIEW":
        raise Conflict(f"QA starts after submission (the run is {run.status}).", error_code="RUN_NOT_IN_QA")
    _require_sod(run, principal)
    if any(r.completed_at is None for r in qa_reviews(db, run.id)):
        raise Conflict("A QA review is already open.", error_code="QA_IN_PROGRESS")
    rv = CalculationQaReview(run_id=run.id, started_by=principal.user_id)
    db.add(rv)
    db.flush()
    record(db, ctx, "CALCULATION_QA_STARTED", ENTITY, run.id, None, _payload(run, qa_review_id=rv.id), None, organization_id=p.organization_id)
    db.commit()
    return rv


def complete_qa(db: Session, ctx: RequestContext, principal: Principal, run_id: uuid.UUID, result: str, notes: str,
                resolver: Resolver | None = None) -> CalculationQaReview:
    run, p = get_run(db, principal, run_id, P.CALCULATION_REVIEW)
    if run.status != "QA_REVIEW":
        raise Conflict(f"QA is only possible while the run is in QA_REVIEW (it is {run.status}).", error_code="RUN_NOT_IN_QA")
    _require_sod(run, principal)
    rv = next((r for r in reversed(qa_reviews(db, run.id)) if r.completed_at is None), None)
    if rv is None:
        raise Conflict("Start QA first.", error_code="QA_NOT_STARTED")
    checks = qa_checks(db, run, principal.user_id, resolver)
    failed = [c["key"] for c in checks if c["result"] == "FAIL"]
    if result == "PASS" and failed:
        raise Conflict("QA cannot pass while checks fail: " + ", ".join(failed) + ".", error_code="QA_CHECKS_FAILED", details={"failed": failed})
    rv.checks, rv.result, rv.notes, rv.completed_by, rv.completed_at = json.dumps(checks), result, notes, principal.user_id, utcnow()
    record(db, ctx, "CALCULATION_QA_COMPLETED", ENTITY, run.id, None,
           _payload(run, qa_review_id=rv.id, result=result, checks={c["key"]: c["result"] for c in checks}), notes,
           organization_id=p.organization_id)
    db.commit()
    return rv


def approve(db: Session, ctx: RequestContext, principal: Principal, run_id: uuid.UUID, reason: str) -> CalculationRun:
    run, p = get_run(db, principal, run_id, P.CALCULATION_APPROVE)
    if run.status != "QA_REVIEW":
        raise Conflict(f"Only a run in QA_REVIEW can be approved (it is {run.status}).", error_code="RUN_NOT_IN_QA")
    _require_sod(run, principal)
    last = next((r for r in reversed(qa_reviews(db, run.id)) if r.completed_at is not None), None)
    if last is None or last.result != "PASS":
        raise Conflict("Approval needs a completed calculation QA with result PASS.", error_code="QA_NOT_PASSED")
    snapshot = json.loads(run.input_snapshot or "{}")
    if fw.sha256(snapshot) != run.input_sha256:
        raise Conflict("The frozen input snapshot does not match its SHA-256.", error_code="INPUT_SNAPSHOT_MISMATCH")
    if fw.output_hash(stored_output_records(db, run.id), run.module_code or "", run.module_version or "", run.engine_version) != run.output_sha256:
        raise Conflict("The stored outputs do not match their SHA-256.", error_code="SNAPSHOT_MISMATCH")
    stale = current_problems(db, run, snapshot)
    if stale:
        raise Conflict("Frozen inputs are out of date; create a new run.", error_code="INPUTS_OUT_OF_DATE", details={"problems": stale})
    now = utcnow()
    for old in db.scalars(select(CalculationRun).where(CalculationRun.monitoring_period_id == run.monitoring_period_id,
                                                       CalculationRun.status == "APPROVED", CalculationRun.id != run.id)).all():
        old.superseded_by_run_id, old.superseded_at = run.id, now
        _transition(db, ctx, p, old, "SUPERSEDED", "CALCULATION_SUPERSEDED", f"Superseded by {run.run_code}", superseded_by=run.run_code)
    db.flush()
    run.approved_by, run.approved_at, run.status_reason = principal.user_id, now, reason
    _transition(db, ctx, p, run, "APPROVED", "CALCULATION_APPROVED", reason, qa_review_id=last.id)
    if p.status == "CALCULATION_READY":   # A17: the first approved calculation run
        psvc.transition_to(db, ctx, p, "CALCULATED", "PROJECT_STATUS_CHANGED", "CALCULATED", f"Calculation {run.run_code} approved")
    db.commit()
    return run


def reject(db: Session, ctx: RequestContext, principal: Principal, run_id: uuid.UUID, reason: str) -> CalculationRun:
    run, p = get_run(db, principal, run_id, P.CALCULATION_APPROVE)
    if run.status != "QA_REVIEW":
        raise Conflict(f"Only a run in QA_REVIEW can be rejected (it is {run.status}).", error_code="RUN_NOT_IN_QA")
    _require_sod(run, principal)
    _close(db, ctx, p, run, "REJECTED", "CALCULATION_REJECTED", reason)
    db.commit()
    return run


def history(db: Session, run_id: uuid.UUID) -> list[WorkflowEvent]:
    return list(db.scalars(select(WorkflowEvent).where(WorkflowEvent.entity_type == ENTITY, WorkflowEvent.entity_id == str(run_id))
                           .order_by(WorkflowEvent.occurred_at, WorkflowEvent.id)).all())


def calc_rule(db: Session, rule_id: uuid.UUID) -> MethodologyCalculationRule | None:
    return db.get(MethodologyCalculationRule, rule_id)


def _uuid(v: Any) -> uuid.UUID | None:
    return uuid.UUID(str(v)) if v else None
