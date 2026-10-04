"""MRV plans, monitoring periods, monitoring (activity) records, evidence, datasets and QA (spec section 7.6, 17).

Rules enforced here:
- MRV plans are bound to the project's LOCKED methodology version; measurement definitions are copied from that
  version's monitoring rules (source METHODOLOGY) plus project-configured ones (PROJECT_CONFIGURED); unconfigured
  methodology requirements are recorded as CONFIGURATION_REQUIRED and must be explicitly acknowledged on approval
- approved plans are never edited: a new plan version supersedes the old one when approved
- monitoring records are versioned (amend = new version) and typed against their measurement definition
- datasets freeze an exact snapshot (record ids + versions + evidence checksums, SHA-256) on submission; approved
  datasets never change; a correction is a new dataset version
- QA runs deterministic checks; PASS is refused while any check FAILs; approver/QA reviewer ≠ submitter
- nothing is calculated; the project never moves beyond MONITORING in Phase 5
"""
import hashlib
import json
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit.service import record, record_transition
from app.core.config import get_settings
from app.core.context import RequestContext
from app.core.errors import Conflict, NotFound, PermissionDenied, ValidationFailed
from app.models import (
    AuditLog,
    FieldCollectionRecord,
    MethodologyMonitoringRule,
    MonitoringPeriod,
    MonitoringRecord,
    MrvDataset,
    MrvEvidence,
    MrvPlan,
    MrvPlanMeasurement,
    MrvQaReview,
    Project,
    ProjectFarm,
    ProjectStratum,
    SamplingDesign,
    SamplingDesignVersion,
    SamplingPoint,
)
from app.models.base import utcnow
from app.models.documents import DocumentCategory
from app.repositories import gis
from app.schemas.mrv import DatasetIn, MeasurementIn, MonitoringRecordAmend, MonitoringRecordIn, PeriodIn, PlanIn, PlanUpdate, QaCheck
from app.security.permissions import P
from app.security.principal import Principal
from app.services import document_service, mrv_access
from app.services import project_service as psvc
from app.services.mrv_requirements import requirements
from app.services.notification_service import notify
from app.services.workflows import MONITORING_PERIOD_MACHINE, MRV_DATASET_MACHINE, MRV_PLAN_MACHINE

ENTITY = "project"
DOC_ENTITY = "mrv"
EVIDENCE_DOC_CATEGORIES = {DocumentCategory.FIELD_PHOTO.value, DocumentCategory.INPUT_RECORD.value, DocumentCategory.GEOSPATIAL_FILE.value,
                           DocumentCategory.OTHER.value}
EDITABLE_PERIOD = ("ACTIVE", "DATA_COLLECTION")


def _document_resolver(db: Session, principal: Principal, project_id: uuid.UUID, kind: str) -> None:
    nf = NotFound("Document not found.", error_code="DOCUMENT_NOT_FOUND")
    p = db.get(Project, project_id)
    if p is None:
        raise nf
    codes = (P.MRV_COLLECT, P.MRV_MANAGE, P.SAMPLING_COLLECT) if kind == "manage" else (P.MRV_READ, P.MRV_COLLECT, P.SAMPLING_COLLECT)
    if not any(principal.can_in_org(c, p.organization_id) for c in codes):
        raise nf


document_service.register_resolver(DOC_ENTITY, _document_resolver)


def _audit(db: Session, ctx: RequestContext, p: Project, action: str, new: dict[str, Any], old: dict[str, Any] | None = None,
           reason: str | None = None) -> None:
    record(db, ctx, action, ENTITY, p.id, old, new, reason, organization_id=p.organization_id)


# ---------------------------------------------------------------- plans
def plans(db: Session, project_id: uuid.UUID) -> list[MrvPlan]:
    return list(db.scalars(select(MrvPlan).where(MrvPlan.project_id == project_id).order_by(MrvPlan.plan_version.desc())).all())


def approved_plan(db: Session, project_id: uuid.UUID) -> MrvPlan | None:
    return db.scalars(select(MrvPlan).where(MrvPlan.project_id == project_id, MrvPlan.status == "APPROVED")).first()


def measurements(db: Session, plan_id: uuid.UUID) -> list[MrvPlanMeasurement]:
    return list(db.scalars(select(MrvPlanMeasurement).where(MrvPlanMeasurement.mrv_plan_id == plan_id).order_by(MrvPlanMeasurement.code)).all())


def get_plan(db: Session, principal: Principal, plan_id: uuid.UUID, *codes: str) -> tuple[MrvPlan, Project]:
    plan = db.get(MrvPlan, plan_id)
    if plan is None:
        raise NotFound("MRV plan not found.", error_code="MRV_PLAN_NOT_FOUND")
    return plan, mrv_access.project(db, principal, plan.project_id, *codes)


def _add_measurement(db: Session, plan: MrvPlan, m: MeasurementIn) -> MrvPlanMeasurement:
    if any(x.code == m.code for x in measurements(db, plan.id)):
        raise Conflict(f"Measurement {m.code} already exists in this plan.", error_code="MEASUREMENT_EXISTS")
    allowed = json.dumps(m.allowed_values) if m.allowed_values else None
    row = MrvPlanMeasurement(mrv_plan_id=plan.id, source="PROJECT_CONFIGURED", allowed_values=allowed,
                             **m.model_dump(exclude={"allowed_values"}))
    db.add(row)
    db.flush()
    return row


def create_plan(db: Session, ctx: RequestContext, principal: Principal, data: PlanIn) -> MrvPlan:
    p = mrv_access.project(db, principal, data.project_id, P.MRV_MANAGE)
    pm, v = mrv_access.locked_methodology(db, p)
    existing = plans(db, p.id)
    if any(x.status in ("DRAFT", "SUBMITTED") for x in existing):
        raise Conflict("A plan version is already being prepared. Edit or withdraw it first.", error_code="PLAN_IN_PROGRESS")
    req = requirements(db, v)
    method_q = req.value("quantification_approach")
    if method_q and data.quantification_approach and data.quantification_approach != method_q:
        raise ValidationFailed(f"The methodology version sets the quantification approach to {method_q}.", error_code="METHODOLOGY_REQUIREMENT")
    current = approved_plan(db, p.id)
    plan = MrvPlan(project_id=p.id, plan_version=max((x.plan_version for x in existing), default=0) + 1, project_methodology_id=pm.id,
                   methodology_id=pm.methodology_id, methodology_version_id=v.id, monitoring_frequency=data.monitoring_frequency,
                   monitoring_start=data.monitoring_start, monitoring_end=data.monitoring_end,
                   quantification_approach=method_q or data.quantification_approach or "CONFIGURATION_REQUIRED",
                   sampling_requirements_ref=", ".join(sorted({x["rule_code"] for x in req.sampling.values()})) or "CONFIGURATION_REQUIRED",
                   required_evidence=data.required_evidence, configuration_status=req.status,
                   configuration_gaps=json.dumps(req.gaps) if req.gaps else None, notes=data.notes,
                   supersedes_id=current.id if current else None, created_by=principal.user_id)
    db.add(plan)
    db.flush()
    for r in req.monitoring:  # methodology monitoring rules become measurement definitions (not invented)
        # LABORATORY parameters are measured on the samples, so they attach to sampling points (decision V2-A: from the declared
        # provenance, not from the unit); other parameters keep the Phase 5 level mapping
        lab = r["measurement_source"] == "LABORATORY"
        db.add(MrvPlanMeasurement(mrv_plan_id=plan.id, code=r["rule_code"][:40], name=(r["parameter"] or r["title"])[:200], category="OTHER",
                                  value_type="NUMBER" if r["unit"] else "TEXT", unit=r["unit"],
                                  level="SAMPLING_POINT" if (lab or r["unit"]) else "FARM",
                                  frequency=r["frequency"], required=True, source="METHODOLOGY", monitoring_rule_id=uuid.UUID(r["rule_id"])))
    db.flush()
    for m in data.measurements:
        _add_measurement(db, plan, m)
    _audit(db, ctx, p, "MRV_PLAN_CREATED", {"mrv_plan_id": plan.id, "plan_version": plan.plan_version, "methodology_version_id": v.id,
                                           "configuration_status": plan.configuration_status, "gaps": req.gaps,
                                           "measurements": len(req.monitoring) + len(data.measurements)})
    db.commit()
    return plan


def update_plan(db: Session, ctx: RequestContext, principal: Principal, plan_id: uuid.UUID, data: PlanUpdate) -> MrvPlan:
    plan, p = get_plan(db, principal, plan_id, P.MRV_MANAGE)
    if plan.status != "DRAFT":
        raise Conflict(f"Only a DRAFT plan can be edited (this one is {plan.status}). Create a new plan version.", error_code="PLAN_NOT_EDITABLE")
    changes = data.model_dump(exclude_unset=True)
    if "quantification_approach" in changes:
        req = requirements(db, mrv_access.locked_methodology(db, p)[1])
        if req.value("quantification_approach") and changes["quantification_approach"] != req.value("quantification_approach"):
            raise ValidationFailed("The methodology version sets the quantification approach.", error_code="METHODOLOGY_REQUIREMENT")
    start, end = changes.get("monitoring_start", plan.monitoring_start), changes.get("monitoring_end", plan.monitoring_end)
    if start and end and end <= start:
        raise ValidationFailed("monitoring_end must be after monitoring_start.", error_code="INVALID_DATES")
    old = {k: getattr(plan, k) for k in changes}
    for k, val in changes.items():
        setattr(plan, k, val)
    if old != changes:
        _audit(db, ctx, p, "MRV_PLAN_UPDATED", {"mrv_plan_id": plan.id, **changes}, old)
    db.commit()
    return plan


def add_measurement(db: Session, ctx: RequestContext, principal: Principal, plan_id: uuid.UUID, data: MeasurementIn) -> MrvPlanMeasurement:
    plan, p = get_plan(db, principal, plan_id, P.MRV_MANAGE)
    if plan.status != "DRAFT":
        raise Conflict("Measurements can only be added to a DRAFT plan.", error_code="PLAN_NOT_EDITABLE")
    m = _add_measurement(db, plan, data)
    _audit(db, ctx, p, "MRV_PLAN_UPDATED", {"mrv_plan_id": plan.id, "measurement_added": data.code, "source": "PROJECT_CONFIGURED"})
    db.commit()
    return m


def submit_plan(db: Session, ctx: RequestContext, principal: Principal, plan_id: uuid.UUID, reason: str) -> MrvPlan:
    plan, p = get_plan(db, principal, plan_id, P.MRV_MANAGE)
    missing = [label for ok, label in ((bool(measurements(db, plan.id)), "at least one measurement"),
                                       (bool(plan.monitoring_frequency), "a monitoring frequency"),
                                       (bool(plan.monitoring_start and plan.monitoring_end), "monitoring start and end dates")) if not ok]
    if missing:
        raise Conflict("Cannot submit yet: " + "; ".join(missing) + ".", error_code="REQUIREMENTS_NOT_MET", details={"missing": missing})
    record_transition(db, ctx, MRV_PLAN_MACHINE, plan.id, plan.status, "SUBMITTED", "MRV_PLAN_SUBMITTED", reason, p.organization_id)
    plan.status, plan.submitted_by, plan.submitted_at, plan.status_reason = "SUBMITTED", principal.user_id, utcnow(), reason
    db.commit()
    return plan


def gap_approval_allowed(p: Project) -> bool:
    """Decision V1 — a PLATFORM GOVERNANCE rule, not a methodology rule. An MRV plan with CONFIGURATION_REQUIRED gaps may be
    approved (with an explicit, audited acknowledgement) only for DEMO projects or outside production. In production the
    approval is blocked; no exception mechanism exists until the business approves one."""
    return p.environment == "DEMO" or not get_settings().is_production


def approval_blockers(plan: MrvPlan, p: Project) -> list[str]:
    """What blocks a production approval of this plan (empty when nothing does, and always empty for DEMO / non-production)."""
    if gap_approval_allowed(p):
        return []
    out = [f"CONFIGURATION_REQUIRED: {g}" for g in json.loads(plan.configuration_gaps or "[]")]
    if not (plan.required_evidence or "").strip():
        out.append("CONFIGURATION_REQUIRED: required evidence is not configured in the plan")
    return out


def approve_plan(db: Session, ctx: RequestContext, principal: Principal, plan_id: uuid.UUID, reason: str, acknowledge_gaps: bool) -> MrvPlan:
    plan, p = get_plan(db, principal, plan_id, P.MRV_APPROVE)
    if plan.submitted_by == principal.user_id:
        raise PermissionDenied("You submitted this plan, so someone else must approve it.", error_code="SEPARATION_OF_DUTIES")
    mrv_access.locked_methodology(db, p)
    blockers = approval_blockers(plan, p)
    if blockers:
        raise Conflict("Production approval is blocked until the methodology version and the plan configure every required MRV, sampling, "
                       "monitoring and evidence requirement (CONFIGURATION_REQUIRED). This is a platform governance rule.",
                       error_code="CONFIGURATION_REQUIRED", details={"blockers": blockers, "policy": "PRODUCTION_BLOCK"})
    if plan.configuration_status == "CONFIGURATION_REQUIRED" and not acknowledge_gaps:
        raise Conflict("The methodology version does not configure all MRV requirements (CONFIGURATION_REQUIRED). Acknowledge the "
                       "gaps explicitly to approve with project-configured values.", error_code="CONFIGURATION_REQUIRED",
                       details={"gaps": json.loads(plan.configuration_gaps or "[]")})
    previous = approved_plan(db, p.id)
    if previous is not None:
        record_transition(db, ctx, MRV_PLAN_MACHINE, previous.id, "APPROVED", "SUPERSEDED", "MRV_PLAN_SUPERSEDED",
                          f"Superseded by plan version {plan.plan_version}", p.organization_id)
        previous.status = "SUPERSEDED"
        db.flush()
    record_transition(db, ctx, MRV_PLAN_MACHINE, plan.id, plan.status, "APPROVED", "MRV_PLAN_APPROVED", reason, p.organization_id)
    plan.status, plan.approved_by, plan.approved_at, plan.status_reason = "APPROVED", principal.user_id, utcnow(), reason
    if acknowledge_gaps and plan.configuration_status == "CONFIGURATION_REQUIRED":
        plan.gaps_acknowledged_by = principal.user_id
    if p.status == "METHODOLOGY_CONFIRMED":
        psvc.transition_to(db, ctx, p, "MRV_PLANNED", "PROJECT_STATUS_CHANGED", "MRV_PLAN_APPROVED", reason)
    notify(db, [plan.created_by, plan.submitted_by], "MRV_PLAN_APPROVED", f"MRV plan v{plan.plan_version} approved: {p.project_code}", reason,
           ENTITY, p.id, f"/mrv/projects/{p.id}")
    db.commit()
    return plan


def return_plan(db: Session, ctx: RequestContext, principal: Principal, plan_id: uuid.UUID, reason: str) -> MrvPlan:
    plan, p = get_plan(db, principal, plan_id, P.MRV_APPROVE)
    record_transition(db, ctx, MRV_PLAN_MACHINE, plan.id, plan.status, "DRAFT", "MRV_PLAN_RETURNED", reason, p.organization_id)
    plan.status, plan.status_reason = "DRAFT", reason
    db.commit()
    return plan


def withdraw_plan(db: Session, ctx: RequestContext, principal: Principal, plan_id: uuid.UUID, reason: str) -> MrvPlan:
    plan, p = get_plan(db, principal, plan_id, P.MRV_MANAGE)
    record_transition(db, ctx, MRV_PLAN_MACHINE, plan.id, plan.status, "WITHDRAWN", "MRV_PLAN_WITHDRAWN", reason, p.organization_id)
    plan.status, plan.status_reason = "WITHDRAWN", reason
    db.commit()
    return plan


# ---------------------------------------------------------------- monitoring periods
def periods(db: Session, project_id: uuid.UUID) -> list[MonitoringPeriod]:
    return list(db.scalars(select(MonitoringPeriod).where(MonitoringPeriod.project_id == project_id).order_by(MonitoringPeriod.period_number)).all())


def get_period(db: Session, principal: Principal, period_id: uuid.UUID, *codes: str) -> tuple[MonitoringPeriod, Project]:
    mp = db.scalars(select(MonitoringPeriod).where(MonitoringPeriod.id == period_id).execution_options(populate_existing=True)).first()
    if mp is None:
        raise NotFound("Monitoring period not found.", error_code="MONITORING_PERIOD_NOT_FOUND")
    return mp, mrv_access.project(db, principal, mp.project_id, *codes)


def create_period(db: Session, ctx: RequestContext, principal: Principal, data: PeriodIn) -> MonitoringPeriod:
    p = mrv_access.project(db, principal, data.project_id, P.MRV_MANAGE)
    _, v = mrv_access.locked_methodology(db, p)
    plan = approved_plan(db, p.id)
    if plan is None:
        raise Conflict("Approve an MRV plan before planning monitoring periods.", error_code="MRV_PLAN_NOT_APPROVED")
    if (plan.monitoring_start and data.start_date < plan.monitoring_start) or (plan.monitoring_end and data.end_date > plan.monitoring_end):
        raise ValidationFailed("The period must lie within the MRV plan's monitoring window.", error_code="OUTSIDE_PLAN_WINDOW",
                               details={"monitoring_start": str(plan.monitoring_start), "monitoring_end": str(plan.monitoring_end)})
    clash = [x for x in periods(db, p.id) if x.purpose == data.purpose and x.status != "CLOSED"
             and x.start_date < data.end_date and data.start_date < x.end_date]
    if clash:
        raise Conflict("Another open period with the same purpose overlaps these dates.", error_code="PERIOD_OVERLAP")
    n = (db.scalar(select(func.max(MonitoringPeriod.period_number)).where(MonitoringPeriod.project_id == p.id)) or 0) + 1
    mp = MonitoringPeriod(project_id=p.id, mrv_plan_id=plan.id, methodology_version_id=v.id, period_number=n, created_by=principal.user_id,
                          **data.model_dump(exclude={"project_id"}))
    db.add(mp)
    db.flush()
    record_transition(db, ctx, MONITORING_PERIOD_MACHINE, mp.id, None, "DRAFT", "MONITORING_PERIOD_CREATED", None, p.organization_id)
    _audit(db, ctx, p, "MONITORING_PERIOD_CREATED", {"monitoring_period_id": mp.id, "period_number": n, "purpose": mp.purpose,
                                                    "start_date": mp.start_date, "end_date": mp.end_date, "mrv_plan_id": plan.id})
    db.commit()
    return mp


def _period_to(db: Session, ctx: RequestContext, mp: MonitoringPeriod, p: Project, target: str, action: str, reason: str | None) -> None:
    record_transition(db, ctx, MONITORING_PERIOD_MACHINE, mp.id, mp.status, target, action, reason, p.organization_id)
    mp.status, mp.status_reason = target, reason


def period_action(db: Session, ctx: RequestContext, principal: Principal, period_id: uuid.UUID, action: str, reason: str) -> MonitoringPeriod:
    """plan (DRAFT→PLANNED), start (PLANNED→ACTIVE), open-collection (ACTIVE→DATA_COLLECTION), close (APPROVED→CLOSED)."""
    mp, p = get_period(db, principal, period_id, P.MRV_MANAGE)
    mrv_access.locked_methodology(db, p)
    target, audit_action = {"plan": ("PLANNED", "MONITORING_PERIOD_PLANNED"), "start": ("ACTIVE", "MONITORING_PERIOD_STARTED"),
                            "open-collection": ("DATA_COLLECTION", "MONITORING_PERIOD_DATA_COLLECTION_OPENED"),
                            "close": ("CLOSED", "MONITORING_PERIOD_CLOSED")}[action]
    if action == "start" and approved_plan(db, p.id) is None:
        raise Conflict("The MRV plan is no longer approved.", error_code="MRV_PLAN_NOT_APPROVED")
    _period_to(db, ctx, mp, p, target, audit_action, reason)
    if action == "start" and p.status == "MRV_PLANNED":
        psvc.transition_to(db, ctx, p, "MONITORING", "PROJECT_STATUS_CHANGED", "MONITORING_STARTED", reason)
    if action == "open-collection":
        ds = open_dataset(db, mp.id)
        if ds is not None and ds.status in ("DRAFT", "SUBMITTED"):
            # A SUBMITTED dataset is re-opened with its period: the frozen snapshot is dropped and rebuilt at the next submit.
            record_transition(db, ctx, MRV_DATASET_MACHINE, ds.id, ds.status, "COLLECTING", "MRV_DATASET_COLLECTING", reason, p.organization_id)
            ds.status, ds.snapshot, ds.snapshot_sha256, ds.submitted_by, ds.submitted_at = "COLLECTING", None, None, None, None
    _audit(db, ctx, p, audit_action, {"monitoring_period_id": mp.id, "status": target}, None, reason)
    db.commit()
    return mp


# ---------------------------------------------------------------- monitoring records
def _typed_value(m: MrvPlanMeasurement, value: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"value_number": None, "value_text": None, "value_date": None, "value_bool": None}
    if value is None or value == "":
        raise ValidationFailed(f"A value is required for {m.code}.", error_code="VALUE_REQUIRED")
    try:
        if m.value_type == "NUMBER":
            out["value_number"] = Decimal(str(value))
        elif m.value_type == "BOOLEAN":
            if not isinstance(value, bool):
                raise ValueError
            out["value_bool"] = value
        elif m.value_type == "DATE":
            out["value_date"] = date.fromisoformat(str(value))
        elif m.value_type == "CHOICE":
            allowed = json.loads(m.allowed_values or "[]")
            if str(value) not in allowed:
                raise ValidationFailed(f"{m.code} must be one of {', '.join(allowed)}.", error_code="INVALID_VALUE")
            out["value_text"] = str(value)
        else:
            out["value_text"] = str(value)[:1000]
    except (ValueError, InvalidOperation, TypeError) as e:
        raise ValidationFailed(f"{m.code} expects a {m.value_type.lower()} value.", error_code="INVALID_VALUE") from e
    return out


def record_value(r: MonitoringRecord) -> Any:
    for v in (r.value_number, r.value_text, r.value_date, r.value_bool):
        if v is not None:
            return v
    return None


def measurement_source(db: Session, m: MrvPlanMeasurement) -> str | None:
    """Declared provenance (decision V2-A) of a methodology-sourced measurement, read from its methodology monitoring rule:
    FIELD, FIELD_ACTIVITY, LABORATORY or UNCLASSIFIED. None for project-configured measurements. Never inferred from the
    unit, name, numeric type or level of the measurement."""
    if m.source != "METHODOLOGY":
        return None
    rule = db.get(MethodologyMonitoringRule, m.monitoring_rule_id) if m.monitoring_rule_id else None
    return rule.measurement_source if rule is not None else "UNCLASSIFIED"


# Decision V2-B — the role a measurement's values play. Only the origin (METHODOLOGY vs PROJECT_CONFIGURED) and the
# methodology rule's declared provenance decide it; never the code, name, unit, type or level a user gave a measurement.
METHODOLOGY_PARAMETER = "METHODOLOGY_PARAMETER"            # methodology-defined FIELD / FIELD_ACTIVITY: authoritative MRV data
LABORATORY_PARAMETER = "LABORATORY_PARAMETER"              # methodology-defined LABORATORY: no Phase 5 value; approved lab result only
UNCLASSIFIED_PARAMETER = "UNCLASSIFIED_PARAMETER"          # methodology-defined without provenance: not capturable
SUPPLEMENTARY_OBSERVATION = "SUPPLEMENTARY_OBSERVATION"    # user-created: never a lab result, never an authoritative calculation input


def data_role(db: Session, m: MrvPlanMeasurement) -> str:
    """User-created/custom measurements are supplementary observations and are not authoritative laboratory results or
    authoritative calculation inputs. Authoritative analytical parameters originate from methodology-defined monitoring rules
    and their declared measurement provenance (decisions V2, V2-A, V2-B)."""
    src = measurement_source(db, m)
    if src is None:
        return SUPPLEMENTARY_OBSERVATION
    return {"LABORATORY": LABORATORY_PARAMETER, "UNCLASSIFIED": UNCLASSIFIED_PARAMETER}.get(src, METHODOLOGY_PARAMETER)


def is_authoritative(db: Session, m: MrvPlanMeasurement) -> bool:
    """Whether values recorded for this measurement in Phase 5 are authoritative MRV data (methodology FIELD / FIELD_ACTIVITY only)."""
    return data_role(db, m) == METHODOLOGY_PARAMETER


def is_laboratory_parameter(db: Session, m: MrvPlanMeasurement) -> bool:
    """Decision V2: a parameter the methodology declares LABORATORY (whatever its name — SOC, pH, bulk density, …; the same
    parameter declared FIELD is captured in Phase 5, decision V2-C) is authoritative only as an APPROVED Phase 6 laboratory
    result; Phase 5 records only the field collection and its traceability, never the value."""
    return measurement_source(db, m) == "LABORATORY"


def _refuse_sample_analysis_value(db: Session, m: MrvPlanMeasurement) -> None:
    src = measurement_source(db, m)
    if src == "LABORATORY":
        raise ValidationFailed(f"{m.code} ({m.name}) is declared a LABORATORY parameter by the methodology. Its value is authoritative only as "
                               "an approved laboratory result (decision V2) and cannot be entered as MRV monitoring data. Record the field "
                               "collection instead; the value stays AWAITING_ANALYSIS.", error_code="LABORATORY_RESULT_REQUIRED",
                               details={"measurement": m.code, "measurement_source": src, "analysis_status": "AWAITING_ANALYSIS"})
    if src == "UNCLASSIFIED":
        raise ValidationFailed(f"{m.code} ({m.name}) has no declared measurement source in the methodology version (CONFIGURATION_REQUIRED). "
                               "A methodology specialist must classify it as FIELD, FIELD_ACTIVITY or LABORATORY in a new version before "
                               "values can be captured.", error_code="MEASUREMENT_SOURCE_UNCLASSIFIED",
                               details={"measurement": m.code, "measurement_source": src})


def add_monitoring_record(db: Session, ctx: RequestContext, principal: Principal, data: MonitoringRecordIn) -> MonitoringRecord:
    mp, p = get_period(db, principal, data.monitoring_period_id, P.MRV_COLLECT, P.MRV_MANAGE)
    if mp.status not in EDITABLE_PERIOD:
        raise Conflict(f"Monitoring data can be recorded while the period is ACTIVE or DATA_COLLECTION (it is {mp.status}).",
                       error_code="PERIOD_NOT_OPEN")
    m = db.get(MrvPlanMeasurement, data.measurement_id)
    if m is None or m.mrv_plan_id != mp.mrv_plan_id:
        raise ValidationFailed("This measurement is not part of the period's MRV plan.", error_code="MEASUREMENT_NOT_IN_PLAN")
    _refuse_sample_analysis_value(db, m)
    target = {"FARM": data.farm_id, "STRATUM": data.stratum_id, "SAMPLING_POINT": data.sampling_point_id, "PROJECT": p.id}[m.level]
    if target is None:
        raise ValidationFailed(f"{m.code} is recorded per {m.level.lower().replace('_', ' ')}.", error_code="LEVEL_REQUIRED")
    _check_entity(db, p, mp, data)
    if m.unit and data.unit and data.unit != m.unit:
        raise ValidationFailed(f"{m.code} is recorded in {m.unit}.", error_code="UNIT_MISMATCH")
    values = _typed_value(m, data.value)
    dup = db.scalars(select(MonitoringRecord).where(
        MonitoringRecord.monitoring_period_id == mp.id, MonitoringRecord.measurement_id == m.id, MonitoringRecord.is_current == True,  # noqa: E712
        MonitoringRecord.status == "RECORDED", MonitoringRecord.observed_on == data.observed_on,
        MonitoringRecord.measurement_phase == data.measurement_phase, MonitoringRecord.farm_id == data.farm_id,
        MonitoringRecord.stratum_id == data.stratum_id, MonitoringRecord.sampling_point_id == data.sampling_point_id)).first()
    if dup is not None:
        raise Conflict("The same measurement is already recorded for this item and date. Amend it instead.", error_code="DUPLICATE_RECORD",
                       details={"record_id": str(dup.record_id)})
    r = MonitoringRecord(project_id=p.id, monitoring_period_id=mp.id, measurement_id=m.id, record_id=uuid.uuid4(), farm_id=data.farm_id,
                         stratum_id=data.stratum_id, sampling_point_id=data.sampling_point_id, field_collection_id=data.field_collection_id,
                         measurement_phase=data.measurement_phase, unit=data.unit or m.unit, observed_on=data.observed_on, source=data.source,
                         notes=data.notes, recorded_by=principal.user_id, **values)
    db.add(r)
    db.flush()
    _audit(db, ctx, p, "MONITORING_RECORD_ADDED", {"monitoring_record_id": r.id, "measurement": m.code, "data_role": data_role(db, m),
                                                  "authoritative": is_authoritative(db, m), "phase": r.measurement_phase,
                                                  "value": record_value(r), "unit": r.unit, "observed_on": r.observed_on})
    db.commit()
    return r


def _check_entity(db: Session, p: Project, mp: MonitoringPeriod, data: MonitoringRecordIn) -> None:
    if data.farm_id and not db.scalars(select(ProjectFarm).where(ProjectFarm.project_id == p.id, ProjectFarm.farm_id == data.farm_id,
                                                                 ProjectFarm.status == "ACTIVE")).first():
        raise ValidationFailed("The farm does not participate in this project.", error_code="FARM_NOT_IN_PROJECT")
    if data.stratum_id:
        s = db.get(ProjectStratum, data.stratum_id)
        if s is None or s.project_id != p.id:
            raise ValidationFailed("Stratum not found in this project.", error_code="STRATUM_NOT_FOUND")
    if data.sampling_point_id:
        sp = db.get(SamplingPoint, data.sampling_point_id)
        if sp is None or sp.monitoring_period_id != mp.id:
            raise ValidationFailed("Sampling point not found in this period.", error_code="POINT_NOT_FOUND")
    if data.field_collection_id:
        fc = db.get(FieldCollectionRecord, data.field_collection_id)
        if fc is None or fc.monitoring_period_id != mp.id:
            raise ValidationFailed("Field collection not found in this period.", error_code="COLLECTION_NOT_FOUND")


def amend_monitoring_record(db: Session, ctx: RequestContext, principal: Principal, record_id: uuid.UUID, data: MonitoringRecordAmend
                            ) -> MonitoringRecord:
    cur = db.scalars(select(MonitoringRecord).where(MonitoringRecord.record_id == record_id,
                                                    MonitoringRecord.is_current == True)).first()  # noqa: E712
    if cur is None:
        raise NotFound("Monitoring record not found.", error_code="MONITORING_RECORD_NOT_FOUND")
    mp, p = get_period(db, principal, cur.monitoring_period_id, P.MRV_COLLECT, P.MRV_MANAGE)
    if mp.status not in EDITABLE_PERIOD:
        raise Conflict("Records can only be corrected while the period is open; corrections after submission need a new dataset version.",
                       error_code="PERIOD_NOT_OPEN")
    m = db.get(MrvPlanMeasurement, cur.measurement_id)
    assert m is not None
    _refuse_sample_analysis_value(db, m)
    values = _typed_value(m, data.value) if data.value is not None else {k: getattr(cur, k) for k in ("value_number", "value_text", "value_date",
                                                                                                      "value_bool")}
    cur.is_current, cur.status = False, "SUPERSEDED"
    db.flush()
    new = MonitoringRecord(**{c.key: getattr(cur, c.key) for c in MonitoringRecord.__table__.columns
                              if c.key not in ("id", "version", "is_current", "status", "recorded_at", "recorded_by", "change_reason",
                                               "value_number", "value_text", "value_date", "value_bool", "unit", "observed_on", "notes")},
                           version=cur.version + 1, is_current=True, status="RECORDED", recorded_by=principal.user_id, change_reason=data.reason,
                           unit=data.unit or cur.unit, observed_on=data.observed_on or cur.observed_on, notes=data.notes or cur.notes, **values)
    db.add(new)
    db.flush()
    _audit(db, ctx, p, "MONITORING_RECORD_AMENDED", {"record_id": cur.record_id, "version": new.version, "value": record_value(new)},
           {"version": cur.version, "value": record_value(cur)}, data.reason)
    db.commit()
    return new


def monitoring_records(db: Session, period_id: uuid.UUID, include_history: bool = False) -> list[MonitoringRecord]:
    stmt = select(MonitoringRecord).where(MonitoringRecord.monitoring_period_id == period_id)
    if not include_history:
        stmt = stmt.where(MonitoringRecord.is_current == True)  # noqa: E712
    return list(db.scalars(stmt.order_by(MonitoringRecord.observed_on, MonitoringRecord.recorded_at)).all())


# ---------------------------------------------------------------- evidence
ENTITY_MODELS: dict[str, Any] = {"MONITORING_PERIOD": MonitoringPeriod, "SAMPLING_POINT": SamplingPoint, "FIELD_COLLECTION": FieldCollectionRecord,
                                 "MONITORING_RECORD": MonitoringRecord}


def add_evidence(db: Session, ctx: RequestContext, principal: Principal, *, project_id: uuid.UUID, entity_type: str, entity_id: uuid.UUID,
                 evidence_type: str, description: str | None, latitude: float | None, longitude: float | None, captured_at: datetime | None,
                 filename: str | None, data: bytes | None) -> MrvEvidence:
    p = mrv_access.project(db, principal, project_id, P.MRV_COLLECT, P.MRV_MANAGE, P.SAMPLING_COLLECT)
    period_id = _evidence_target(db, principal, p, entity_type, entity_id)
    if evidence_type == "GPS" and (latitude is None or longitude is None):
        raise ValidationFailed("GPS evidence needs latitude and longitude.", error_code="GPS_REQUIRED")
    if evidence_type in ("FIELD_PHOTO", "DOCUMENT") and not data:
        raise ValidationFailed("Attach the file for photo / document evidence.", error_code="FILE_REQUIRED")
    doc_id, checksum = None, None
    if data:
        category = DocumentCategory.FIELD_PHOTO.value if evidence_type == "FIELD_PHOTO" else DocumentCategory.OTHER.value
        doc = document_service.create_document(db, ctx, entity_type=DOC_ENTITY, entity_id=p.id, organization_id=p.organization_id,
                                               environment=p.environment, category=category, title=f"{evidence_type} {entity_type.lower()}",
                                               filename=filename, data=data)
        doc_id, checksum = doc.id, hashlib.sha256(data).hexdigest()
    staff = any(principal.can_in_org(c, p.organization_id) for c in (P.MRV_MANAGE, P.MRV_COLLECT))
    e = MrvEvidence(project_id=p.id, monitoring_period_id=period_id, entity_type=entity_type, entity_id=entity_id, evidence_type=evidence_type,
                    document_id=doc_id, checksum_sha256=checksum, latitude=latitude, longitude=longitude, captured_at=captured_at,
                    description=description, source="FIELD_COLLECTOR" if principal.can_in_org(P.SAMPLING_COLLECT, p.organization_id) and not staff
                    else "STAFF", uploaded_by=principal.user_id)
    db.add(e)
    db.flush()
    _audit(db, ctx, p, "MRV_EVIDENCE_ADDED", {"evidence_id": e.id, "entity_type": entity_type, "entity_id": entity_id,
                                             "evidence_type": evidence_type, "document_id": doc_id, "checksum_sha256": checksum})
    db.commit()
    return e


def _evidence_target(db: Session, principal: Principal, p: Project, entity_type: str, entity_id: uuid.UUID) -> uuid.UUID | None:
    if entity_type == "PROJECT":
        if entity_id != p.id:
            raise ValidationFailed("Evidence entity does not belong to this project.", error_code="EVIDENCE_ENTITY_INVALID")
        return None
    if entity_type == "FARM":
        if not db.scalars(select(ProjectFarm).where(ProjectFarm.project_id == p.id, ProjectFarm.farm_id == entity_id)).first():
            raise ValidationFailed("The farm does not participate in this project.", error_code="EVIDENCE_ENTITY_INVALID")
        return None
    obj = db.get(ENTITY_MODELS[entity_type], entity_id)
    if obj is None or obj.project_id != p.id:
        raise ValidationFailed("Evidence entity does not belong to this project.", error_code="EVIDENCE_ENTITY_INVALID")
    period_id = obj.id if entity_type == "MONITORING_PERIOD" else obj.monitoring_period_id
    # a collector without staff rights may only add evidence to their own work
    if not any(principal.can_in_org(c, p.organization_id) for c in (P.MRV_MANAGE, P.MRV_COLLECT)):
        own = (entity_type == "FIELD_COLLECTION" and obj.collector_id == principal.user_id) or \
              (entity_type == "SAMPLING_POINT" and obj.assigned_collector_id == principal.user_id)
        if not own:
            raise PermissionDenied("Field collectors can add evidence only to their own assignments.", error_code="NOT_ASSIGNED")
    return period_id


def evidence_for(db: Session, project_id: uuid.UUID, period_id: uuid.UUID | None = None, entity_id: uuid.UUID | None = None) -> list[MrvEvidence]:
    stmt = select(MrvEvidence).where(MrvEvidence.project_id == project_id)
    if period_id:
        stmt = stmt.where(MrvEvidence.monitoring_period_id == period_id)
    if entity_id:
        stmt = stmt.where(MrvEvidence.entity_id == entity_id)
    return list(db.scalars(stmt.order_by(MrvEvidence.uploaded_at.desc())).all())


# ---------------------------------------------------------------- datasets
def datasets(db: Session, period_id: uuid.UUID) -> list[MrvDataset]:
    return list(db.scalars(select(MrvDataset).where(MrvDataset.monitoring_period_id == period_id).order_by(MrvDataset.version.desc())).all())


def open_dataset(db: Session, period_id: uuid.UUID) -> MrvDataset | None:
    return db.scalars(select(MrvDataset).where(MrvDataset.monitoring_period_id == period_id,
                                               MrvDataset.status.in_(["DRAFT", "COLLECTING", "SUBMITTED", "QA_REVIEW"]))).first()


def get_dataset(db: Session, principal: Principal, dataset_id: uuid.UUID, *codes: str) -> tuple[MrvDataset, Project]:
    ds = db.scalars(select(MrvDataset).where(MrvDataset.id == dataset_id).execution_options(populate_existing=True)).first()
    if ds is None:
        raise NotFound("MRV dataset not found.", error_code="MRV_DATASET_NOT_FOUND")
    return ds, mrv_access.project(db, principal, ds.project_id, *codes)


def create_dataset(db: Session, ctx: RequestContext, principal: Principal, data: DatasetIn) -> MrvDataset:
    mp, p = get_period(db, principal, data.monitoring_period_id, P.MRV_MANAGE)
    _, v = mrv_access.locked_methodology(db, p)
    if mp.status not in ("ACTIVE", "DATA_COLLECTION", "REJECTED", "APPROVED"):
        raise Conflict(f"A dataset can be opened while the period is ACTIVE, DATA_COLLECTION, REJECTED or APPROVED (it is {mp.status}).",
                       error_code="PERIOD_NOT_OPEN")
    if open_dataset(db, mp.id) is not None:
        raise Conflict("This period already has an open dataset.", error_code="DATASET_OPEN")
    plan = db.get(MrvPlan, mp.mrv_plan_id)
    assert plan is not None
    prev = datasets(db, mp.id)
    version = (prev[0].version if prev else 0) + 1
    num = "".join(ch for ch in p.project_code.split("-")[-1] if ch.isdigit()).lstrip("0") or "0"
    ds = MrvDataset(dataset_code=f"MRV-{mp.start_date.year}-P{int(num):03d}-M{mp.period_number}-V{version}", project_id=p.id,
                    monitoring_period_id=mp.id, mrv_plan_id=plan.id, methodology_version_id=v.id, version=version,
                    supersedes_id=prev[0].id if prev else None, configuration_gaps=plan.configuration_gaps, notes=data.notes,
                    environment=p.environment, created_by=principal.user_id)
    db.add(ds)
    db.flush()
    record_transition(db, ctx, MRV_DATASET_MACHINE, ds.id, None, "DRAFT", "MRV_DATASET_CREATED", None, p.organization_id)
    if mp.status in ("REJECTED", "APPROVED"):  # corrections: a new dataset version reopens collection; approved data stays intact
        _period_to(db, ctx, mp, p, "DATA_COLLECTION", "MONITORING_PERIOD_REOPENED", f"New dataset version {version} (correction)")
    if mp.status == "DATA_COLLECTION":
        record_transition(db, ctx, MRV_DATASET_MACHINE, ds.id, "DRAFT", "COLLECTING", "MRV_DATASET_COLLECTING", None, p.organization_id)
        ds.status = "COLLECTING"
    _audit(db, ctx, p, "MRV_DATASET_CREATED", {"dataset_id": ds.id, "dataset_code": ds.dataset_code, "version": version,
                                              "monitoring_period_id": mp.id, "supersedes_id": ds.supersedes_id})
    db.commit()
    return ds


def build_snapshot(db: Session, ds: MrvDataset) -> dict[str, Any]:
    """The exact record versions the dataset is made of (reproducible lineage)."""
    from app.services import sampling_service as ss
    mp = db.get(MonitoringPeriod, ds.monitoring_period_id)
    plan = db.get(MrvPlan, ds.mrv_plan_id)
    assert mp is not None and plan is not None
    designs = db.scalars(select(SamplingDesign).where(SamplingDesign.monitoring_period_id == mp.id)).all()
    dvs = [dv for d in designs for dv in db.scalars(select(SamplingDesignVersion).where(SamplingDesignVersion.design_id == d.id,
                                                                                         SamplingDesignVersion.status == "APPROVED")).all()]
    pts = ss.points_of_period(db, mp.id)
    cols = [c for c in ss.collections_of_period(db, mp.id) if c.status == "ACCEPTED"]
    recs = monitoring_records(db, mp.id)
    evid = evidence_for(db, ds.project_id, mp.id)
    strata_ids = sorted({str(x.stratum_id) for x in pts})
    strata = {str(s.id): s for s in (db.get(ProjectStratum, uuid.UUID(i)) for i in strata_ids) if s}
    plan_ms = measurements(db, plan.id)
    roles = {m.id: data_role(db, m) for m in plan_ms}
    return {
        "dataset": {"id": str(ds.id), "code": ds.dataset_code, "version": ds.version},
        "project_id": str(ds.project_id), "methodology_version_id": str(ds.methodology_version_id),
        "mrv_plan": {"id": str(plan.id), "version": plan.plan_version, "configuration_status": plan.configuration_status},
        "monitoring_period": {"id": str(mp.id), "number": mp.period_number, "start": mp.start_date.isoformat(), "end": mp.end_date.isoformat(),
                              "purpose": mp.purpose},
        "sampling_design_versions": [{"id": str(dv.id), "design_id": str(dv.design_id), "version": dv.version} for dv in dvs],
        "strata": [{"id": i, "record_id": str(s.record_id), "version": s.version, "code": s.code} for i, s in strata.items()],
        "sampling_points": [{"id": str(x.id), "code": x.point_code, "status": x.status, "farm_id": str(x.farm_id), "stratum_id": str(x.stratum_id),
                             "lat": str(x.latitude), "lon": str(x.longitude)} for x in pts],
        "field_collections": [{"id": str(c.id), "code": c.collection_code, "version": c.version, "point_id": str(c.sampling_point_id)}
                              for c in cols],
        # V2-B: every record carries its origin and role, so a later calculation can tell methodology-defined authoritative data
        # from user-created supplementary observations (which never become laboratory results or calculation inputs)
        "monitoring_records": [_snapshot_record(db, r, roles) for r in recs if r.status == "RECORDED"],
        "data_roles": {
            "authoritative_methodology_records": sum(1 for r in recs if r.status == "RECORDED" and roles[r.measurement_id] == METHODOLOGY_PARAMETER),
            "supplementary_observations": sum(1 for r in recs if r.status == "RECORDED" and roles[r.measurement_id] == SUPPLEMENTARY_OBSERVATION),
            "laboratory_parameters_awaiting_analysis": sorted(m.code for m in plan_ms if roles[m.id] == LABORATORY_PARAMETER),
            "note": "Only authoritative methodology records (and, later, approved laboratory results) may feed a calculation; "
                    "supplementary observations never do.",
        },
        "evidence": [{"id": str(e.id), "type": e.evidence_type, "checksum_sha256": e.checksum_sha256} for e in evid if e.status != "REJECTED"],
    }


def _snapshot_record(db: Session, r: MonitoringRecord, roles: dict[uuid.UUID, str]) -> dict[str, Any]:
    m = db.get(MrvPlanMeasurement, r.measurement_id)
    role = roles.get(r.measurement_id) or (data_role(db, m) if m else SUPPLEMENTARY_OBSERVATION)
    return {"id": str(r.id), "record_id": str(r.record_id), "version": r.version, "measurement_code": m.code if m else None,
            "origin": m.source if m else None, "measurement_source": measurement_source(db, m) if m else None,
            "data_role": role, "authoritative": role == METHODOLOGY_PARAMETER}


def _hash(snapshot: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def submit_dataset(db: Session, ctx: RequestContext, principal: Principal, dataset_id: uuid.UUID, reason: str) -> MrvDataset:
    ds, p = get_dataset(db, principal, dataset_id, P.MRV_MANAGE)
    mp = db.get(MonitoringPeriod, ds.monitoring_period_id)
    assert mp is not None
    if mp.status != "DATA_COLLECTION":
        raise Conflict("Open data collection on the monitoring period first.", error_code="PERIOD_NOT_COLLECTING")
    snap = build_snapshot(db, ds)
    if not (snap["field_collections"] or snap["monitoring_records"]):
        raise Conflict("The dataset is empty: no accepted field collections or monitoring records.", error_code="DATASET_EMPTY")
    record_transition(db, ctx, MRV_DATASET_MACHINE, ds.id, ds.status, "SUBMITTED", "MRV_DATASET_SUBMITTED", reason, p.organization_id)
    ds.status, ds.snapshot, ds.snapshot_sha256 = "SUBMITTED", json.dumps(snap, sort_keys=True), _hash(snap)
    ds.submitted_by, ds.submitted_at, ds.status_reason = principal.user_id, utcnow(), reason
    _period_to(db, ctx, mp, p, "SUBMITTED", "MONITORING_PERIOD_SUBMITTED", reason)
    _audit(db, ctx, p, "MRV_DATASET_SUBMITTED", {"dataset_id": ds.id, "dataset_code": ds.dataset_code, "snapshot_sha256": ds.snapshot_sha256,
                                                "counts": {k: len(v) for k, v in snap.items() if isinstance(v, list)}}, None, reason)
    _audit(db, ctx, p, "MONITORING_PERIOD_SUBMITTED", {"monitoring_period_id": mp.id, "dataset_id": ds.id}, None, reason)
    db.commit()
    return ds


def submit_period(db: Session, ctx: RequestContext, principal: Principal, period_id: uuid.UUID, reason: str) -> MonitoringPeriod:
    mp, _ = get_period(db, principal, period_id, P.MRV_MANAGE)
    ds = open_dataset(db, mp.id)
    if ds is None:
        raise Conflict("Create a dataset for the period first.", error_code="NO_DATASET")
    submit_dataset(db, ctx, principal, ds.id, reason)
    return get_period(db, principal, period_id)[0]


# ---------------------------------------------------------------- QA
def qa_reviews(db: Session, dataset_id: uuid.UUID) -> list[MrvQaReview]:
    return list(db.scalars(select(MrvQaReview).where(MrvQaReview.dataset_id == dataset_id).order_by(MrvQaReview.started_at)).all())


def start_qa(db: Session, ctx: RequestContext, principal: Principal, dataset_id: uuid.UUID) -> MrvQaReview:
    ds, p = get_dataset(db, principal, dataset_id, P.MRV_REVIEW)
    record_transition(db, ctx, MRV_DATASET_MACHINE, ds.id, ds.status, "QA_REVIEW", "MRV_QA_STARTED", None, p.organization_id)
    ds.status = "QA_REVIEW"
    mp = db.get(MonitoringPeriod, ds.monitoring_period_id)
    assert mp is not None
    _period_to(db, ctx, mp, p, "QA_REVIEW", "MONITORING_PERIOD_QA_REVIEW", None)
    rv = MrvQaReview(dataset_id=ds.id, started_by=principal.user_id)
    db.add(rv)
    db.flush()
    _audit(db, ctx, p, "MRV_QA_STARTED", {"dataset_id": ds.id, "qa_review_id": rv.id})
    db.commit()
    return rv


def complete_qa(db: Session, ctx: RequestContext, principal: Principal, dataset_id: uuid.UUID, result: str, notes: str) -> MrvQaReview:
    ds, p = get_dataset(db, principal, dataset_id, P.MRV_REVIEW)
    if ds.status != "QA_REVIEW":
        raise Conflict("Start QA first.", error_code="QA_NOT_STARTED")
    if ds.submitted_by == principal.user_id:
        raise PermissionDenied("You submitted this dataset, so someone else must complete QA.", error_code="SEPARATION_OF_DUTIES")
    rv = next((r for r in reversed(qa_reviews(db, ds.id)) if r.completed_at is None), None)
    if rv is None:
        raise Conflict("No QA review is open.", error_code="QA_NOT_STARTED")
    checks = qa_checks(db, ds)
    failed = [c.key for c in checks if c.result == "FAIL"]
    if result == "PASS" and failed:
        raise Conflict("QA cannot pass while checks fail: " + ", ".join(failed) + ".", error_code="QA_CHECKS_FAILED", details={"failed": failed})
    rv.checks = json.dumps([c.model_dump() for c in checks])
    rv.result, rv.notes, rv.completed_by, rv.completed_at = result, notes, principal.user_id, utcnow()
    _audit(db, ctx, p, "MRV_QA_COMPLETED", {"dataset_id": ds.id, "qa_review_id": rv.id, "result": result,
                                           "checks": {c.key: c.result for c in checks}}, None, notes)
    db.commit()
    return rv


def approve_dataset(db: Session, ctx: RequestContext, principal: Principal, dataset_id: uuid.UUID, reason: str) -> MrvDataset:
    ds, p = get_dataset(db, principal, dataset_id, P.MRV_APPROVE)
    if ds.submitted_by == principal.user_id:
        raise PermissionDenied("You submitted this dataset, so someone else must approve it.", error_code="SEPARATION_OF_DUTIES")
    last = next((r for r in reversed(qa_reviews(db, ds.id)) if r.completed_at is not None), None)
    if last is None or last.result != "PASS":
        raise Conflict("Approval needs a completed QA review with result PASS.", error_code="QA_NOT_PASSED")
    if ds.snapshot is None or _hash(json.loads(ds.snapshot)) != ds.snapshot_sha256:
        raise Conflict("The dataset snapshot does not match its checksum.", error_code="SNAPSHOT_MISMATCH")
    mp = db.get(MonitoringPeriod, ds.monitoring_period_id)
    assert mp is not None
    for old in datasets(db, mp.id):
        if old.status == "APPROVED" and old.id != ds.id:
            record_transition(db, ctx, MRV_DATASET_MACHINE, old.id, "APPROVED", "SUPERSEDED", "MRV_DATASET_SUPERSEDED",
                              f"Superseded by {ds.dataset_code}", p.organization_id)
            old.status = "SUPERSEDED"
    record_transition(db, ctx, MRV_DATASET_MACHINE, ds.id, ds.status, "APPROVED", "MRV_DATASET_APPROVED", reason, p.organization_id)
    ds.status, ds.approved_by, ds.approved_at, ds.status_reason = "APPROVED", principal.user_id, utcnow(), reason
    _period_to(db, ctx, mp, p, "APPROVED", "MONITORING_PERIOD_APPROVED", reason)
    _audit(db, ctx, p, "MRV_DATASET_APPROVED", {"dataset_id": ds.id, "dataset_code": ds.dataset_code, "snapshot_sha256": ds.snapshot_sha256,
                                               "qa_review_id": last.id}, None, reason)
    _audit(db, ctx, p, "MONITORING_PERIOD_APPROVED", {"monitoring_period_id": mp.id, "dataset_id": ds.id}, None, reason)
    notify(db, [ds.submitted_by], "MRV_DATASET_APPROVED", f"MRV dataset approved: {ds.dataset_code}", reason, ENTITY, p.id, f"/mrv/projects/{p.id}")
    db.commit()
    return ds


def reject_dataset(db: Session, ctx: RequestContext, principal: Principal, dataset_id: uuid.UUID, reason: str) -> MrvDataset:
    ds, p = get_dataset(db, principal, dataset_id, P.MRV_APPROVE)
    if ds.status != "QA_REVIEW":
        raise Conflict("Only datasets under QA review can be rejected.", error_code="NOT_IN_QA")
    record_transition(db, ctx, MRV_DATASET_MACHINE, ds.id, ds.status, "REJECTED", "MRV_DATASET_REJECTED", reason, p.organization_id)
    ds.status, ds.status_reason = "REJECTED", reason
    mp = db.get(MonitoringPeriod, ds.monitoring_period_id)
    assert mp is not None
    _period_to(db, ctx, mp, p, "REJECTED", "MONITORING_PERIOD_REJECTED", reason)
    _audit(db, ctx, p, "MRV_DATASET_REJECTED", {"dataset_id": ds.id, "dataset_code": ds.dataset_code}, None, reason)
    notify(db, [ds.submitted_by], "MRV_DATASET_REJECTED", f"MRV dataset needs correction: {ds.dataset_code}", reason, ENTITY, p.id,
           f"/mrv/projects/{p.id}")
    db.commit()
    return ds


def _duplicate_distance(db: Session, x: SamplingPoint) -> float:
    from app.services import field_rules as rules
    dv = db.get(SamplingDesignVersion, x.design_version_id)
    return float(rules.of_design(dv)["duplicate_distance_m"]) if dv is not None else float(rules.legacy_defaults()["duplicate_distance_m"])


def qa_checks(db: Session, ds: MrvDataset) -> list[QaCheck]:
    """Deterministic QA checks over the dataset's snapshot and the records it references."""
    from app.services import field_rules as rules
    from app.services import sampling_service as ss
    out: list[QaCheck] = []
    snap = json.loads(ds.snapshot) if ds.snapshot else build_snapshot(db, ds)
    mp = db.get(MonitoringPeriod, ds.monitoring_period_id)
    plan = db.get(MrvPlan, ds.mrv_plan_id)
    p = db.get(Project, ds.project_id)
    assert mp is not None and plan is not None and p is not None

    def add(key: str, label: str, problems: list[str], warn: bool = False) -> None:
        out.append(QaCheck(key=key, label=label, result="PASS" if not problems else ("WARN" if warn else "FAIL"), details=problems[:50]))

    add("methodology_version", "Dataset uses the project's locked methodology version",
        [] if p.methodology_version_id == ds.methodology_version_id else ["The project's locked version differs from the dataset's."])
    add("mrv_plan_version", "MRV plan version is the approved plan",
        [] if plan.status == "APPROVED" else [f"Plan version {plan.plan_version} is {plan.status}."], warn=plan.status == "SUPERSEDED")
    cols: list[FieldCollectionRecord] = [c for c in (db.get(FieldCollectionRecord, uuid.UUID(i["id"])) for i in snap["field_collections"])
                                         if c is not None]
    pts: list[SamplingPoint] = [x for x in (db.get(SamplingPoint, uuid.UUID(i["id"])) for i in snap["sampling_points"]) if x is not None]
    collected_points = {c.sampling_point_id for c in cols}
    add("sampling_completeness", "Every sampling point is collected (accepted) or skipped with a reason",
        [f"{x.point_code} has no accepted collection" for x in pts if x.status not in ("SKIPPED", "CANCELLED") and x.id not in collected_points]
        + [f"{x.point_code} skipped without a reason" for x in pts if x.status == "SKIPPED" and not x.status_reason])
    pending = [c for c in ss.collections_of_period(db, mp.id) if c.status in ("IN_PROGRESS", "SUBMITTED", "RETURNED")]
    add("field_records", "No field collection is still in progress or awaiting review", [f"{c.collection_code} is {c.status}" for c in pending])
    add("required_fields", "Accepted field records have time, GPS and depth",
        [f"{c.collection_code} lacks "
         + ", ".join(k for k, v in (("time", c.collected_at), ("GPS", c.gps_latitude), ("depth", c.actual_depth_top_cm)) if v is None)
         for c in cols if c.collected_at is None or c.gps_latitude is None or c.actual_depth_top_cm is None])
    tolerances = sorted({rules.of_collection(c)["gps_tolerance_m"] for c in cols})
    add("gps_validity", "GPS within the tolerance recorded on each field record (" + (", ".join(f"{t:g} m" for t in tolerances) or "—")
        + ") and inside the farm (or justified)",
        [f"{c.collection_code}: {c.distance_from_point_m} m from the point (tolerance {rules.of_collection(c)['gps_tolerance_m']:g} m)" for c in cols
         if c.distance_from_point_m is not None and float(c.distance_from_point_m) > rules.of_collection(c)["gps_tolerance_m"]
         and not c.deviation_note]
        + [f"{c.collection_code}: GPS outside the farm boundary" for c in cols if c.gps_inside_farm is False])
    invalid = [x.point_code for x in pts if not gis.point_inside_boundary(db, x.farm_boundary_id, float(x.latitude), float(x.longitude))]
    add("sampling_point_validity", "Sampling points lie inside their farm boundary (SQL Server)", [f"{c} outside its farm" for c in invalid])
    photo_ids = [e.entity_id for e in evidence_for(db, ds.project_id, mp.id) if e.evidence_type == "FIELD_PHOTO" and e.status != "REJECTED"]
    add("evidence", "Every accepted field record has the minimum number of field photos recorded on it",
        [f"{c.collection_code} has {photo_ids.count(c.id)} of {rules.of_collection(c)['min_photos']} photo(s)" for c in cols
         if photo_ids.count(c.id) < rules.of_collection(c)["min_photos"]])
    in_period = [c.collection_code for c in cols if c.collected_at and not (mp.start_date <= c.collected_at.date() <= mp.end_date)]
    recs = [r for r in monitoring_records(db, mp.id) if r.status == "RECORDED"]
    in_period += [f"record {r.record_id} ({r.observed_on})" for r in recs
                  if r.measurement_phase != "BASELINE" and not (mp.start_date <= r.observed_on <= mp.end_date)]
    add("monitoring_period_dates", "Collections and records fall within the monitoring period", in_period)
    farms = [pf.farm_id for pf in db.scalars(select(ProjectFarm).where(ProjectFarm.project_id == p.id, ProjectFarm.status == "ACTIVE")).all()]
    missing: list[str] = []
    analysis: list[str] = []
    unclassified: list[str] = []
    for m in measurements(db, plan.id):
        have = [r for r in recs if r.measurement_id == m.id]
        src = measurement_source(db, m)
        if src == "LABORATORY":
            # decision V2: authoritative only as an approved Phase 6 laboratory result — reported, never filled in here
            analysis.append(f"{m.code} ({m.name}): AWAITING_ANALYSIS for {len(collected_points)} collected sample(s) — no value is entered")
        elif src == "UNCLASSIFIED":
            unclassified.append(f"CONFIGURATION_REQUIRED: measurement source of {m.code} not declared by the methodology version")
        elif m.level == "FARM":
            missing += [f"{m.code} missing for a farm ({f})" for f in farms if not any(r.farm_id == f for r in have)] if m.required else []
        elif m.level == "PROJECT" and m.required and not have:
            missing.append(f"{m.code} missing for the project")
        elif m.level == "SAMPLING_POINT" and m.required:
            missing += [f"{m.code} missing for {x.point_code}" for x in pts
                        if x.id in collected_points and not any(r.sampling_point_id == x.id for r in have)]
    add("missing_records", "Required measurements are recorded", missing)
    add("sample_analysis_pending", "Awaiting laboratory analysis (LABORATORY methodology parameters, Phase 6)", analysis, warn=True)
    dup_cols = [str(pid) for pid in collected_points if len([c for c in cols if c.sampling_point_id == pid]) > 1]
    keys = [(r.measurement_id, r.farm_id, r.stratum_id, r.sampling_point_id, r.observed_on, r.measurement_phase) for r in recs]
    add("duplicate_records", "No duplicate field or monitoring records",
        [f"point {d} has several accepted collections" for d in dup_cols] + (["duplicate monitoring records"] if len(keys) != len(set(keys)) else []))
    near = []
    coords = [(float(x.latitude), float(x.longitude)) for x in pts]
    from app.rules.sampling_points import distance_m
    dup_m = {x.id: _duplicate_distance(db, x) for x in pts}
    for i in range(len(coords)):
        for j in range(i + 1, len(coords)):
            if distance_m(coords[i], coords[j]) < max(dup_m[pts[i].id], dup_m[pts[j].id]):
                near.append(f"{pts[i].point_code} / {pts[j].point_code}")
    add("invalid_locations", "No duplicate point locations", near)
    inconsistent = [f"{c.collection_code}: depth {c.actual_depth_top_cm}-{c.actual_depth_bottom_cm} cm vs planned "
                    f"{x.planned_depth_top_cm}-{x.planned_depth_bottom_cm} cm"
                    for c in cols for x in pts if x.id == c.sampling_point_id and c.actual_depth_top_cm is not None
                    and (c.actual_depth_top_cm != x.planned_depth_top_cm or c.actual_depth_bottom_cm != x.planned_depth_bottom_cm)]
    add("inconsistent_data", "Collected depths match the planned depth", inconsistent, warn=True)
    gaps = json.loads(ds.configuration_gaps or "[]")
    add("configuration", "Methodology MRV requirements fully configured (else CONFIGURATION_REQUIRED)",
        [f"CONFIGURATION_REQUIRED: {g}" for g in gaps] + unclassified, warn=True)
    return out


# ---------------------------------------------------------------- history
def history_rows(db: Session, p: Project, prefixes: tuple[str, ...], limit: int = 500) -> list[AuditLog]:
    """MRV audit rows of one project: rows on the project itself plus workflow rows on its MRV records."""
    ids = {str(p.id)}
    for model in (MrvPlan, MonitoringPeriod, MrvDataset, ProjectStratum, SamplingDesign, SamplingPoint, FieldCollectionRecord):
        ids |= {str(i) for i in db.scalars(select(model.id).where(model.project_id == p.id)).all()}
    rows = db.scalars(select(AuditLog).where(AuditLog.organization_id == p.organization_id).order_by(AuditLog.id.desc())).all()
    return [r for r in rows if r.entity_id in ids and r.action.startswith(prefixes)][:limit]
