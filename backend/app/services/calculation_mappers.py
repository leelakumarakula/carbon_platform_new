"""Response builders for the calculation API (read-only)."""
import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calculation import framework as fw
from app.calculation.registry import Resolver
from app.models import (
    CalculationRun,
    Farm,
    Farmer,
    FieldCollectionRecord,
    LabResult,
    LabSample,
    Methodology,
    MethodologyVersion,
    MonitoringPeriod,
    MonitoringRecord,
    MrvDataset,
    MrvPlanMeasurement,
    Project,
    ProjectStratum,
    SamplingDesignVersion,
    SamplingPoint,
    User,
)
from app.schemas.calculation import (
    DEMO_LABEL,
    Blocker,
    CalcCheck,
    CalcQaView,
    CompareOut,
    InputOut,
    InputsOut,
    LineageOut,
    LineageOutput,
    LineageSource,
    ModuleOut,
    OutputOut,
    OutputsOut,
    QaReviewOut,
    ReadinessOut,
    RunOut,
    StepStatus,
)
from app.security.permissions import P
from app.security.principal import Principal
from app.services import calculation_inputs as ci
from app.services import calculation_service as cs


def _names(db: Session, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    ids_ = {i for i in ids if i}
    return {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_(ids_))).all()} if ids_ else {}


def _steps(snapshot: dict[str, Any] | None) -> list[StepStatus]:
    decl = (snapshot or {}).get("module") or {}
    by = {s["step"]: s for s in decl.get("steps", [])}
    return [StepStatus(step=s, status=by.get(s, {}).get("status", "NOT_CONFIGURED"), rule_code=by.get(s, {}).get("rule_code"),
                       label=ci.STEP_LABELS.get(by.get(s, {}).get("status", "NOT_CONFIGURED"), "")) for s in fw.STEPS]


def _label(db: Session, run: CalculationRun) -> tuple[str, bool]:
    m, v = db.get(Methodology, run.methodology_id), db.get(MethodologyVersion, run.methodology_version_id)
    return (f"{m.code if m else '?'} v{v.version_label if v else '?'}", bool(v and v.is_demo_illustrative))


def module_out(m: fw.CalculationModule) -> ModuleOut:
    d = m.declaration()
    return ModuleOut(code=d["code"], version=d["version"], methodology_code=d["methodology_code"], version_label=d["version_label"],
                     calculation_rules_version=d["calculation_rules_version"], readiness=d["readiness"], label=d["label"], rules=d["rules"],
                     variables=d["variables"], constants=d["constants"], steps=d["steps"])


def run_out(db: Session, principal: Principal, run: CalculationRun) -> RunOut:
    p = db.get(Project, run.project_id)
    mp = db.get(MonitoringPeriod, run.monitoring_period_id)
    assert p is not None and mp is not None
    ds = db.get(MrvDataset, run.mrv_dataset_id) if run.mrv_dataset_id else None
    names = _names(db, {run.created_by, run.frozen_by, run.executed_by, run.submitted_by, run.approved_by, run.closed_by})
    label, demo = _label(db, run)
    prev = db.get(CalculationRun, run.recalculation_of_run_id) if run.recalculation_of_run_id else None
    nxt = db.get(CalculationRun, run.superseded_by_run_id) if run.superseded_by_run_id else None
    snapshot = json.loads(run.input_snapshot) if run.input_snapshot else None
    can = lambda code: principal.can_in_org(code, p.organization_id)  # noqa: E731
    independent = not cs.sod_reasons(run, principal.user_id)
    return RunOut(
        id=run.id, run_code=run.run_code, project_id=p.id, project_code=p.project_code, monitoring_period_id=mp.id,
        monitoring_period=f"{mp.name} (#{mp.period_number})", period_start=mp.start_date, period_end=mp.end_date,
        crediting_period_id=run.crediting_period_id, mrv_dataset_id=run.mrv_dataset_id, dataset_code=ds.dataset_code if ds else None,
        methodology_label=label, methodology_version_id=run.methodology_version_id, is_demo_illustrative=demo,
        calculation_rules_version=run.calculation_rules_version, module_code=run.module_code, module_version=run.module_version,
        module_readiness=run.module_readiness, engine_version=run.engine_version, input_sha256=run.input_sha256, output_sha256=run.output_sha256,
        net_result=run.net_result, net_unit=run.net_unit, status=run.status, status_reason=run.status_reason,
        blockers=[Blocker(**b) for b in json.loads(run.blockers or "[]")], notes=run.notes, recalculation_of_run_id=run.recalculation_of_run_id,
        recalculation_of_code=prev.run_code if prev else None, recalculation_reason=run.recalculation_reason,
        superseded_by_run_id=run.superseded_by_run_id, superseded_by_code=nxt.run_code if nxt else None, superseded_at=run.superseded_at,
        environment=run.environment, created_by_name=names.get(run.created_by), created_at=run.created_at,
        frozen_by_name=names.get(run.frozen_by) if run.frozen_by else None, frozen_at=run.frozen_at,
        executed_by_name=names.get(run.executed_by) if run.executed_by else None, executed_at=run.executed_at,
        submitted_by_name=names.get(run.submitted_by) if run.submitted_by else None, submitted_at=run.submitted_at,
        approved_by_name=names.get(run.approved_by) if run.approved_by else None, approved_at=run.approved_at,
        closed_by_name=names.get(run.closed_by) if run.closed_by else None, closed_at=run.closed_at,
        demo_label=DEMO_LABEL if run.environment == "DEMO" or demo else None, steps=_steps(snapshot),
        can_freeze=run.status == "DRAFT" and can(P.CALCULATION_MANAGE),
        can_execute=run.status == "INPUTS_FROZEN" and can(P.CALCULATION_MANAGE),
        can_submit=run.status == "CALCULATED" and can(P.CALCULATION_MANAGE),
        can_cancel=run.status in ("DRAFT", "INPUTS_FROZEN") and can(P.CALCULATION_MANAGE),
        can_review=run.status == "QA_REVIEW" and can(P.CALCULATION_REVIEW) and independent,
        can_approve=run.status == "QA_REVIEW" and can(P.CALCULATION_APPROVE) and independent,
        can_recalculate=run.status in cs.RECALCULABLE and can(P.CALCULATION_MANAGE))


def readiness_out(db: Session, ev: ci.Evaluation) -> ReadinessOut:
    p, mp = ev.project, ev.period
    m, v, ds = ev.methodology, ev.version, ev.dataset or (ci.latest_dataset(db, mp.id))
    return ReadinessOut(
        project_id=p.id, project_code=p.project_code, project_status=p.status, environment=p.environment, monitoring_period_id=mp.id,
        monitoring_period=f"{mp.name} (#{mp.period_number})", methodology_label=f"{m.code} v{v.version_label}" if m and v else None,
        is_demo_illustrative=bool(v and v.is_demo_illustrative), module_code=ev.module.code if ev.module else None,
        module_version=ev.module.version if ev.module else None, module_readiness=ev.module.readiness if ev.module else None,
        dataset_id=ds.id if ds else None, dataset_code=ds.dataset_code if ds else None, dataset_status=ds.status if ds else None,
        ready=ev.ready, blockers=[Blocker(**b.as_dict()) for b in ev.blockers], warnings=ev.warnings,
        steps=[StepStatus(**s) for s in (ev.steps or ci.step_statuses(None))], input_rows=len(ev.inputs),
        calculation_rules=[{"rule_code": r.rule_code, "step": r.step, "title": r.title, "equation_reference": r.equation_reference,
                            "implementation_status": r.implementation_status} for r in ev.calc_rules])


def inputs_out(db: Session, run: CalculationRun) -> InputsOut:
    rows = cs.inputs(db, run.id)
    return InputsOut(run_id=run.id, input_sha256=run.input_sha256, snapshot=json.loads(run.input_snapshot) if run.input_snapshot else None,
                     inputs=[InputOut(seq=r.seq, variable_code=r.variable_code, source_type=r.source_type, source_id=r.source_id,
                                      source_version=r.source_version, source_code=r.source_code, value=r.value, value_kind=r.value_kind,
                                      unit=r.unit, level=r.level, stratum_id=r.stratum_id, farm_id=r.farm_id,
                                      sampling_point_id=r.sampling_point_id, field_collection_id=r.field_collection_id, sample_id=r.sample_id,
                                      root_sample_id=r.root_sample_id, requirement_source=r.requirement_source,
                                      source_reference=r.source_reference, source_sha256=r.source_sha256) for r in rows])


def outputs_out(db: Session, run: CalculationRun) -> OutputsOut:
    _, demo = _label(db, run)
    snapshot = json.loads(run.input_snapshot) if run.input_snapshot else None
    return OutputsOut(run_id=run.id, output_sha256=run.output_sha256, net_result=run.net_result, net_unit=run.net_unit,
                      demo_label=DEMO_LABEL if run.environment == "DEMO" or demo else None, steps=_steps(snapshot),
                      outputs=[_output(o) for o in cs.outputs(db, run.id)])


def _output(o: Any) -> OutputOut:
    refs = json.loads(o.input_refs)
    return OutputOut(seq=o.seq, step=o.step, output_code=o.output_code, rule_code=o.rule_code, calculation_rule_id=o.calculation_rule_id,
                     equation_reference=o.equation_reference, value=o.value, unit=o.unit, level=o.level, entity_id=o.entity_id,
                     input_seqs=refs["inputs"], output_seqs=refs["outputs"], is_final=o.is_final)


def review_outs(db: Session, run: CalculationRun) -> list[QaReviewOut]:
    rvs = cs.qa_reviews(db, run.id)
    names = _names(db, {x for r in rvs for x in (r.started_by, r.completed_by)})
    return [QaReviewOut(id=r.id, started_by_name=names.get(r.started_by), started_at=r.started_at,
                        completed_by_name=names.get(r.completed_by) if r.completed_by else None, completed_at=r.completed_at, result=r.result,
                        notes=r.notes, checks=[CalcCheck(**c) for c in json.loads(r.checks or "[]")]) for r in rvs]


def qa_view(db: Session, principal: Principal, run: CalculationRun, resolver: Resolver | None = None) -> CalcQaView:
    out = run_out(db, principal, run)
    reviewer = principal.user_id
    checks = [CalcCheck(**c) for c in cs.qa_checks(db, run, reviewer, resolver)] if run.input_snapshot else []
    rvs = cs.qa_reviews(db, run.id)
    open_rv = any(r.completed_at is None for r in rvs)
    last = next((r for r in reversed(rvs) if r.completed_at is not None), None)
    blocked = cs.sod_reasons(run, reviewer)
    return CalcQaView(run=out, checks=checks, reviews=review_outs(db, run), can_start=out.can_review and not open_rv,
                      can_complete=out.can_review and open_rv,
                      can_approve=out.can_approve and bool(last and last.result == "PASS"), blocked_reasons=blocked)


def _chain(db: Session, row: Any) -> dict[str, Any]:
    """Source lineage of one frozen input: → result / record → sample → field collection → point → stratum → farm → farmer."""
    c: dict[str, Any] = {"source_type": row.source_type, "source_id": str(row.source_id) if row.source_id else None,
                         "source_version": row.source_version}
    if row.source_type == "LAB_RESULT" and row.source_id:
        res = db.get(LabResult, row.source_id)
        if res:
            c["lab_result"] = {"id": str(res.id), "version": res.version, "status": res.status, "approved_at": res.approved_at.isoformat()
                               if res.approved_at else None, "report_sha256": row.source_sha256}
        s, root = db.get(LabSample, row.sample_id) if row.sample_id else None, db.get(LabSample, row.root_sample_id) if row.root_sample_id else None
        c["sample"] = s.sample_code if s else None
        c["root_sample"] = root.sample_code if root else None
    if row.source_type == "MONITORING_RECORD" and row.source_id:
        rec = db.get(MonitoringRecord, row.source_id)
        meas = db.get(MrvPlanMeasurement, row.plan_measurement_id) if row.plan_measurement_id else None
        c["monitoring_record"] = {"record_id": str(rec.record_id) if rec else None, "version": rec.version if rec else None,
                                  "measurement": meas.code if meas else None}
    if row.source_type == "SAMPLING_DESIGN_PARAMETER" and row.source_id:
        dv = db.get(SamplingDesignVersion, row.source_id)
        c["sampling_design_version"] = {"version": dv.version if dv else None, "requirement_source": row.requirement_source}
    if row.source_type == "MODULE_CONSTANT":
        c["constant"] = {"code": row.source_code, "source_reference": row.source_reference}
    if row.field_collection_id:
        fc = db.get(FieldCollectionRecord, row.field_collection_id)
        c["field_collection"] = {"code": fc.collection_code, "version": fc.version} if fc else None
    if row.sampling_point_id:
        pt = db.get(SamplingPoint, row.sampling_point_id)
        c["sampling_point"] = pt.point_code if pt else None
    if row.stratum_id:
        st = db.get(ProjectStratum, row.stratum_id)
        c["stratum"] = {"code": st.code, "version": st.version} if st else None
    if row.farm_id:
        farm = db.get(Farm, row.farm_id)
        farmer = db.get(Farmer, farm.farmer_id) if farm else None
        c["farm"] = farm.farm_code if farm else None
        c["farmer"] = farmer.farmer_code if farmer else None
    return c


def lineage(db: Session, principal: Principal, run: CalculationRun) -> LineageOut:
    snapshot = json.loads(run.input_snapshot) if run.input_snapshot else {}
    rules = {r["rule_code"]: r for r in snapshot.get("methodology", {}).get("calculation_rules", [])}
    outs = []
    for o in cs.outputs(db, run.id):
        refs = json.loads(o.input_refs)
        rule = {**rules.get(o.rule_code, {}), "calculation_rule_id": str(o.calculation_rule_id)}
        outs.append(LineageOutput(seq=o.seq, step=o.step, output_code=o.output_code, value=o.value, unit=o.unit, rule=rule,
                                  input_seqs=refs["inputs"], output_seqs=refs["outputs"], is_final=o.is_final))
    p = db.get(Project, run.project_id)
    inputs = [LineageSource(seq=r.seq, variable_code=r.variable_code, source_type=r.source_type, value=r.value, unit=r.unit,
                            chain={**_chain(db, r), "project": p.project_code if p else None}) for r in cs.inputs(db, run.id)]
    names = _names(db, {e.user_id for e in cs.history(db, run.id)})
    hist = [{"from_status": e.from_status, "to_status": e.to_status, "user_name": names.get(e.user_id) if e.user_id else None,
             "at": e.occurred_at.isoformat() + "Z", "reason": e.reason} for e in cs.history(db, run.id)]
    meth = snapshot.get("methodology") or {}
    label, demo = _label(db, run)
    from app.services import preverification_mappers as pvm
    return LineageOut(**pvm.lineage_extras(db, run), run=run_out(db, principal, run),
                      methodology={"label": label, "is_demo_illustrative": demo, "version_id": str(run.methodology_version_id),
                                   "calculation_rules_version": run.calculation_rules_version, "rules": meth.get("calculation_rules", [])},
                      dataset=snapshot.get("dataset"), final=next((o for o in outs if o.is_final), None), outputs=outs, inputs=inputs,
                      qa_reviews=review_outs(db, run), history=hist)


def compare(db: Session, principal: Principal, a: CalculationRun, b: CalculationRun) -> CompareOut:
    def key(r: Any) -> tuple[str, str, str]:
        return (r.variable_code, r.source_type, str(r.source_id or r.source_code))
    ia, ib = {key(r): r for r in cs.inputs(db, a.id)}, {key(r): r for r in cs.inputs(db, b.id)}
    oa = {(o.output_code, str(o.entity_id)): o for o in cs.outputs(db, a.id)}
    ob = {(o.output_code, str(o.entity_id)): o for o in cs.outputs(db, b.id)}
    fields = ("methodology_version_id", "calculation_rules_version", "module_code", "module_version", "engine_version", "mrv_dataset_id",
              "input_sha256", "output_sha256", "net_result", "net_unit")
    changed = {f: [str(getattr(a, f)) if getattr(a, f) is not None else None, str(getattr(b, f)) if getattr(b, f) is not None else None]
               for f in fields if getattr(a, f) != getattr(b, f)}
    ref = lambda r: {"variable": r.variable_code, "source_type": r.source_type, "source_code": r.source_code, "value": r.value,  # noqa: E731
                     "unit": r.unit, "source_version": r.source_version}
    return CompareOut(
        run_a=run_out(db, principal, a), run_b=run_out(db, principal, b), same_inputs=a.input_sha256 == b.input_sha256,
        same_outputs=a.output_sha256 == b.output_sha256, changed_fields=changed,
        inputs_added=[ref(ib[k]) for k in sorted(set(ib) - set(ia))], inputs_removed=[ref(ia[k]) for k in sorted(set(ia) - set(ib))],
        inputs_changed=[{"before": ref(ia[k]), "after": ref(ib[k])} for k in sorted(set(ia) & set(ib))
                        if (ia[k].value, ia[k].unit, ia[k].source_version) != (ib[k].value, ib[k].unit, ib[k].source_version)],
        outputs_changed=[{"output_code": k[0], "entity_id": None if k[1] == "None" else k[1], "before": oa[k].value if k in oa else None,
                          "after": ob[k].value if k in ob else None, "unit": (ob.get(k) or oa[k]).unit}
                         for k in sorted(set(oa) | set(ob)) if (oa[k].value if k in oa else None) != (ob[k].value if k in ob else None)])
