"""ORM → response mapping for MRV (permissions decided here, never in the client)."""
import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    Farm,
    FieldCollectionRecord,
    Methodology,
    MethodologyVersion,
    MonitoringPeriod,
    MonitoringRecord,
    MrvDataset,
    MrvEvidence,
    MrvPlan,
    MrvPlanMeasurement,
    MrvQaReview,
    Organization,
    Project,
    ProjectStratum,
    SamplingDesign,
    SamplingDesignVersion,
    SamplingPoint,
    SamplingPointRelocation,
    User,
)
from app.rules.geometry_io import wkt_to_geojson
from app.schemas.mrv import (
    AllocationOut,
    CharacteristicIn,
    CollectionOut,
    DatasetOut,
    DesignOut,
    DesignVersionOut,
    EvidenceOut,
    MeasurementOut,
    MonitoringRecordOut,
    PeriodOut,
    PlanOut,
    PointOut,
    ProjectMrvSummary,
    QaCheck,
    QaReviewOut,
    RelocationOut,
    StratumOut,
)
from app.security.permissions import P
from app.security.principal import Principal
from app.services import field_rules
from app.services import mrv_service as msvc
from app.services import sampling_service as ssvc
from app.services.workflows import MONITORING_PERIOD_MACHINE


def _methodology_label(db: Session, version_id: uuid.UUID) -> str:
    v = db.get(MethodologyVersion, version_id)
    m = db.get(Methodology, v.methodology_id) if v else None
    return f"{m.code} v{v.version_label}" if v and m else ""


def _project_code(db: Session, project_id: uuid.UUID) -> str:
    p = db.get(Project, project_id)
    return p.project_code if p else ""


def measurement_out(m: MrvPlanMeasurement) -> MeasurementOut:
    return MeasurementOut(id=m.id, code=m.code, name=m.name, category=m.category, value_type=m.value_type, unit=m.unit,
                          allowed_values=json.loads(m.allowed_values) if m.allowed_values else None, level=m.level, frequency=m.frequency,
                          required=m.required, source=m.source, monitoring_rule_id=m.monitoring_rule_id)


def plan_out(db: Session, principal: Principal, plan: MrvPlan, p: Project) -> PlanOut:
    org = p.organization_id
    blockers = msvc.approval_blockers(plan, p) if plan.status == "SUBMITTED" else []
    return PlanOut(id=plan.id, project_id=p.id, project_code=p.project_code, plan_version=plan.plan_version, status=plan.status,
                   methodology_id=plan.methodology_id, methodology_version_id=plan.methodology_version_id,
                   methodology_label=_methodology_label(db, plan.methodology_version_id), monitoring_frequency=plan.monitoring_frequency,
                   monitoring_start=plan.monitoring_start, monitoring_end=plan.monitoring_end, quantification_approach=plan.quantification_approach,
                   sampling_requirements_ref=plan.sampling_requirements_ref, required_evidence=plan.required_evidence,
                   configuration_status=plan.configuration_status, configuration_gaps=json.loads(plan.configuration_gaps or "[]"), notes=plan.notes,
                   supersedes_id=plan.supersedes_id, created_by=plan.created_by, created_at=plan.created_at, submitted_by=plan.submitted_by,
                   submitted_at=plan.submitted_at, approved_by=plan.approved_by, approved_at=plan.approved_at, status_reason=plan.status_reason,
                   measurements=[measurement_out(m) for m in msvc.measurements(db, plan.id)],
                   can_edit=plan.status == "DRAFT" and principal.can_in_org(P.MRV_MANAGE, org),
                   can_submit=plan.status == "DRAFT" and principal.can_in_org(P.MRV_MANAGE, org),
                   can_approve=plan.status == "SUBMITTED" and principal.can_in_org(P.MRV_APPROVE, org) and plan.submitted_by != principal.user_id
                   and not blockers,
                   gap_approval_policy="ACKNOWLEDGE_ALLOWED" if msvc.gap_approval_allowed(p) else "PRODUCTION_BLOCK",
                   approval_blockers=blockers, gaps_acknowledged_by=plan.gaps_acknowledged_by)


def period_out(db: Session, mp: MonitoringPeriod) -> PeriodOut:
    plan = db.get(MrvPlan, mp.mrv_plan_id)
    pts = ssvc.points_of_period(db, mp.id)
    cols = ssvc.collections_of_period(db, mp.id)
    return PeriodOut(id=mp.id, project_id=mp.project_id, project_code=_project_code(db, mp.project_id), mrv_plan_id=mp.mrv_plan_id,
                     plan_version=plan.plan_version if plan else 0, methodology_version_id=mp.methodology_version_id, period_number=mp.period_number,
                     name=mp.name, purpose=mp.purpose, start_date=mp.start_date, end_date=mp.end_date, status=mp.status,
                     status_reason=mp.status_reason, created_at=mp.created_at,
                     counts={"points": sum(1 for x in pts if x.status != "CANCELLED"), "assigned": sum(1 for x in pts if x.status == "ASSIGNED"),
                             "collected": sum(1 for x in pts if x.status == "COLLECTED"),
                             "accepted": sum(1 for c in cols if c.status == "ACCEPTED"),
                             "records": len(msvc.monitoring_records(db, mp.id)), "datasets": len(msvc.datasets(db, mp.id))},
                     allowed_transitions=sorted(MONITORING_PERIOD_MACHINE.allowed_from(mp.status)))


def stratum_out(db: Session, s: ProjectStratum, required: list[str]) -> StratumOut:
    farms = ssvc.stratum_farms(db, s.id)
    codes = [f.farm_code for f in (db.get(Farm, x.farm_id) for x in farms) if f]
    chars = ssvc.characteristics(db, s.id)
    have = {c.characteristic for c in chars}
    chars_out = [CharacteristicIn.model_validate({"characteristic": c.characteristic, "value": c.value, "source": c.source}) for c in chars]
    return StratumOut(id=s.id, record_id=s.record_id, project_id=s.project_id, version=s.version, is_current=s.is_current, code=s.code, name=s.name,
                      description=s.description, criteria=json.loads(s.criteria) if s.criteria else None,
                      geojson=wkt_to_geojson(s.geometry) if s.geometry else None, area_hectares=s.area_hectares, farm_ids=[x.farm_id for x in farms],
                      farm_codes=codes, characteristics=chars_out,
                      missing_required_characteristics=[c for c in required if c not in have], source=s.source, status=s.status,
                      change_reason=s.change_reason, created_by=s.created_by, created_at=s.created_at, approved_by=s.approved_by,
                      approved_at=s.approved_at)


def design_version_out(db: Session, dv: SamplingDesignVersion) -> DesignVersionOut:
    allocs = []
    for a in ssvc.allocations(db, dv.id):
        st = db.get(ProjectStratum, a.stratum_id)
        allocs.append(AllocationOut(stratum_id=a.stratum_id, stratum_code=st.code if st else "",
                                    stratum_area_hectares=st.area_hectares if st else None,
                                    sample_count=a.sample_count, allocation_basis=a.allocation_basis))
    skip = ("allocations", "configuration_gaps", "field_rules")
    return DesignVersionOut.model_validate({**{k: getattr(dv, k) for k in DesignVersionOut.model_fields if k not in skip},
                                            "allocations": allocs, "configuration_gaps": json.loads(dv.configuration_gaps or "[]"),
                                            "field_rules": field_rules.of_design(dv)})


def design_out(db: Session, d: SamplingDesign) -> DesignOut:
    mp = db.get(MonitoringPeriod, d.monitoring_period_id)
    vs = ssvc.design_versions(db, d.id)
    cur = next((v for v in vs if v.status == "APPROVED"), None) or (vs[0] if vs else None)
    return DesignOut(id=d.id, project_id=d.project_id, project_code=_project_code(db, d.project_id), mrv_plan_id=d.mrv_plan_id,
                     monitoring_period_id=d.monitoring_period_id, monitoring_period_name=mp.name if mp else "",
                     methodology_version_id=d.methodology_version_id, code=d.code, name=d.name,
                     current=design_version_out(db, cur) if cur else None, versions=[design_version_out(db, v) for v in vs],
                     point_count=sum(1 for x in ssvc.points_of_period(db, d.monitoring_period_id) if x.design_version_id in {v.id for v in vs}))


def _user_names(db: Session, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    return {i: u.full_name for i in ids if i for u in [db.get(User, i)] if u}


def points_out(db: Session, pts: list[SamplingPoint]) -> list[PointOut]:
    names = _user_names(db, {x.assigned_collector_id for x in pts})
    farms = {f.id: f for f in (db.get(Farm, fid) for fid in {x.farm_id for x in pts}) if f}
    strata = {s.id: s for s in (db.get(ProjectStratum, sid) for sid in {x.stratum_id for x in pts}) if s}
    out = []
    for x in pts:
        cols = [c for c in ssvc.collections_of_period(db, x.monitoring_period_id) if c.sampling_point_id == x.id and c.status != "SUPERSEDED"]
        col = cols[-1] if cols else None
        pending = any(r.status == "PENDING" for r in ssvc.relocations(db, x.id))
        f = farms.get(x.farm_id)
        st = strata.get(x.stratum_id)
        out.append(PointOut(id=x.id, point_code=x.point_code, project_id=x.project_id, monitoring_period_id=x.monitoring_period_id,
                            design_version_id=x.design_version_id, stratum_id=x.stratum_id, stratum_code=st.code if st else None, farm_id=x.farm_id,
                            farm_code=f.farm_code if f else None, farm_name=f.name if f else None, sequence=x.sequence, latitude=x.latitude,
                            longitude=x.longitude, planned_depth_top_cm=x.planned_depth_top_cm, planned_depth_bottom_cm=x.planned_depth_bottom_cm,
                            status=x.status, assigned_collector_id=x.assigned_collector_id,
                            assigned_collector_name=names.get(x.assigned_collector_id) if x.assigned_collector_id else None,
                            planned_date=x.planned_date, status_reason=x.status_reason, pending_relocation=pending,
                            collection_id=col.id if col else None, collection_status=col.status if col else None))
    return out


def relocation_out(r: SamplingPointRelocation) -> RelocationOut:
    return RelocationOut.model_validate(r, from_attributes=True)


def collection_out(db: Session, principal: Principal, fc: FieldCollectionRecord) -> CollectionOut:
    sp = db.get(SamplingPoint, fc.sampling_point_id)
    p = db.get(Project, fc.project_id)
    names = _user_names(db, {fc.collector_id})
    base = {k: getattr(fc, k) for k in CollectionOut.model_fields if hasattr(fc, k) and k not in ("checklist", "field_rules")}
    fr = field_rules.of_collection(fc)
    return CollectionOut.model_validate({
        **base, "checklist": ssvc.checklist_of(fc) or None, "required_checklist": field_rules.checklist_keys(fr),
        "checklist_version": fr["checklist_version"], "checklist_items": fr["checklist_items"], "gps_tolerance_m": fr["gps_tolerance_m"],
        "min_photos": fr["min_photos"], "field_rules": fr,
        "analysis_status": "AWAITING_ANALYSIS" if fc.status in ("SUBMITTED", "ACCEPTED") else None,
        "point_code": sp.point_code if sp else None, "collector_name": names.get(fc.collector_id),
        "planned_depth_top_cm": sp.planned_depth_top_cm if sp else None, "planned_depth_bottom_cm": sp.planned_depth_bottom_cm if sp else None,
        "evidence_count": ssvc.evidence_count(db, fc.id),
        "can_edit": fc.collector_id == principal.user_id and fc.status in ("IN_PROGRESS", "RETURNED"),
        "can_review": bool(p) and fc.status == "SUBMITTED" and fc.collector_id != principal.user_id
                      and principal.can_in_org(P.SAMPLING_REVIEW, p.organization_id)})  # type: ignore[union-attr]


def record_out(db: Session, r: MonitoringRecord) -> MonitoringRecordOut:
    m = db.get(MrvPlanMeasurement, r.measurement_id)
    return MonitoringRecordOut(id=r.id, record_id=r.record_id, version=r.version, is_current=r.is_current,
                               monitoring_period_id=r.monitoring_period_id,
                               measurement_id=r.measurement_id, measurement_code=m.code if m else "", measurement_name=m.name if m else "",
                               farm_id=r.farm_id, stratum_id=r.stratum_id, sampling_point_id=r.sampling_point_id,
                               field_collection_id=r.field_collection_id, measurement_phase=r.measurement_phase, value=msvc.record_value(r),
                               unit=r.unit, observed_on=r.observed_on, source=r.source, status=r.status, notes=r.notes,
                               change_reason=r.change_reason, recorded_by=r.recorded_by, recorded_at=r.recorded_at)


def evidence_out(e: MrvEvidence) -> EvidenceOut:
    return EvidenceOut.model_validate(e, from_attributes=True)


def dataset_out(db: Session, principal: Principal, ds: MrvDataset) -> DatasetOut:
    mp = db.get(MonitoringPeriod, ds.monitoring_period_id)
    plan = db.get(MrvPlan, ds.mrv_plan_id)
    p = db.get(Project, ds.project_id)
    snap = json.loads(ds.snapshot) if ds.snapshot else None
    actions: list[str] = []
    if p is not None:
        org = p.organization_id
        if ds.status == "COLLECTING" and principal.can_in_org(P.MRV_MANAGE, org):
            actions.append("submit")
        if ds.status == "SUBMITTED" and principal.can_in_org(P.MRV_REVIEW, org):
            actions.append("start-qa")
        if ds.status == "QA_REVIEW" and principal.can_in_org(P.MRV_REVIEW, org) and ds.submitted_by != principal.user_id:
            actions.append("complete-qa")
        if ds.status == "QA_REVIEW" and principal.can_in_org(P.MRV_APPROVE, org) and ds.submitted_by != principal.user_id:
            actions += ["approve", "reject"]
    return DatasetOut(id=ds.id, dataset_code=ds.dataset_code, project_id=ds.project_id, project_code=p.project_code if p else "",
                      monitoring_period_id=ds.monitoring_period_id, monitoring_period_name=mp.name if mp else "", mrv_plan_id=ds.mrv_plan_id,
                      plan_version=plan.plan_version if plan else 0, methodology_version_id=ds.methodology_version_id,
                      methodology_label=_methodology_label(db, ds.methodology_version_id), version=ds.version, supersedes_id=ds.supersedes_id,
                      status=ds.status, snapshot_summary={k: len(v) for k, v in snap.items() if isinstance(v, list)} if snap else None,
                      snapshot_sha256=ds.snapshot_sha256, configuration_gaps=json.loads(ds.configuration_gaps or "[]"), notes=ds.notes,
                      status_reason=ds.status_reason, environment=ds.environment, created_at=ds.created_at, submitted_by=ds.submitted_by,
                      submitted_at=ds.submitted_at, approved_by=ds.approved_by, approved_at=ds.approved_at, allowed_actions=actions)


def qa_review_out(r: MrvQaReview) -> QaReviewOut:
    return QaReviewOut(id=r.id, dataset_id=r.dataset_id, started_by=r.started_by, started_at=r.started_at,
                       checks=[QaCheck.model_validate(c) for c in json.loads(r.checks)] if r.checks else None, result=r.result, notes=r.notes,
                       completed_by=r.completed_by, completed_at=r.completed_at)


def project_summary(db: Session, p: Project) -> ProjectMrvSummary:
    plans = msvc.plans(db, p.id)
    approved = next((x for x in plans if x.status == "APPROVED"), None)
    pers = msvc.periods(db, p.id)
    open_p = next((x for x in reversed(pers) if x.status not in ("APPROVED", "CLOSED")), None)
    pts = [x for mp in pers for x in ssvc.points_of_period(db, mp.id) if x.status != "CANCELLED"]
    last_ds = next((d for mp in reversed(pers) for d in msvc.datasets(db, mp.id)), None)
    org = db.get(Organization, p.organization_id)
    label: Any = _methodology_label(db, p.methodology_version_id) if p.methodology_version_id else None
    return ProjectMrvSummary(project_id=p.id, project_code=p.project_code, project_name=p.name, project_status=p.status,
                             organization_name=org.name if org else None, methodology_label=label, environment=p.environment,
                             approved_plan_version=approved.plan_version if approved else None, plan_count=len(plans), period_count=len(pers),
                             open_period=f"#{open_p.period_number} {open_p.name} ({open_p.status})" if open_p else None, point_count=len(pts),
                             collected_count=sum(1 for x in pts if x.status == "COLLECTED"),
                             dataset_status=f"{last_ds.dataset_code} {last_ds.status}" if last_ds else None)
