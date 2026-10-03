"""Phase 6 — project-side laboratory workflow: engagements, sample registration & sealing, custody, shipments, and the
read models (approved results with full lineage). Laboratory-side actions and QA are in laboratory_service.py.

Access model (decisions 1, 14, 16):
- project-side permissions are evaluated in the project's organization;
- laboratory-side permissions are evaluated in the laboratory organization AND require an engagement for the project;
- the engagement (project_laboratory_engagements) is the only cross-organization link.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit.service import record, record_transition
from app.core.context import RequestContext
from app.core.errors import Conflict, NotFound, PermissionDenied, ValidationFailed
from app.models import (
    FieldCollectionRecord,
    LabResult,
    LabSample,
    LabShipment,
    LabShipmentItem,
    LabTest,
    MethodologyMonitoringRule,
    MonitoringPeriod,
    MrvPlanMeasurement,
    Organization,
    Project,
    ProjectLaboratoryEngagement,
    ProjectLaboratoryEngagementRule,
    SampleCustodyEvent,
    User,
)
from app.models.base import utcnow
from app.repositories import projects as project_repo
from app.repositories.sequences import next_code
from app.schemas.lab import CustodyEventIn, EngagementIn, SampleIn, SampleUpdate, SealIn, ShipmentIn
from app.security.permissions import P
from app.security.principal import Principal
from app.services import mrv_access
from app.services.workflows import LAB_ENGAGEMENT_MACHINE, LAB_SAMPLE_MACHINE, LAB_SHIPMENT_MACHINE, LAB_TEST_MACHINE

ENTITY = "lab"
PROJECT_SIDE_STATES = {"REGISTERED", "SEALED", "IN_SHIPMENT", "DISPATCHED", "IN_TRANSIT"}
LAB_SIDE_STATES = {"LAB_RECEIVED", "LAB_REGISTERED", "IN_ANALYSIS", "ANALYSED"}
REGISTRABLE_COLLECTION_STATES = ("SUBMITTED", "ACCEPTED")          # decision 13


# ---------------------------------------------------------------- helpers
def not_found(what: str = "Record") -> NotFound:
    return NotFound(f"{what} not found.", error_code="LAB_NOT_FOUND")


def audit(db: Session, ctx: RequestContext, action: str, entity_id: Any, new: dict[str, Any], org: uuid.UUID,
          reason: str | None = None, entity_type: str = ENTITY) -> None:
    """Project-side actions are audited in the project organization, laboratory actions in the laboratory organization.
    Laboratory-organization rows never carry farm / farmer / GPS / field-collection data."""
    record(db, ctx, action, entity_type, entity_id, None, new, reason, organization_id=org)


def names(db: Session, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    ids_ = {i for i in ids if i}
    if not ids_:
        return {}
    return {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_(ids_))).all()}


def org_name(db: Session, org_id: uuid.UUID | None) -> str:
    o = db.get(Organization, org_id) if org_id else None
    return o.name if o else ""


def actor_role(principal: Principal, org_id: uuid.UUID | None, code: str) -> str | None:
    for g in principal.grants:
        if code in g.permissions and (g.organization_id == org_id or g.organization_id is None):
            return g.role_code
    return None


def project_for(db: Session, principal: Principal, project_id: uuid.UUID, *codes: str) -> Project:
    """Project if the caller holds one of `codes` in the project organization; 403 if visible otherwise; else 404."""
    p = project_repo.get(db, project_id)
    if p is None:
        raise not_found("Project")
    if any(principal.can_in_org(c, p.organization_id) for c in codes):
        return p
    if principal.can_in_org(P.PROJECTS_READ, p.organization_id) or principal.can_in_org(P.LAB_READ, p.organization_id):
        raise PermissionDenied(details={"required_permission": " or ".join(codes)})
    raise not_found("Project")


def active_engagement(db: Session, project_id: uuid.UUID, lab_org_id: uuid.UUID) -> ProjectLaboratoryEngagement | None:
    return db.scalars(select(ProjectLaboratoryEngagement).where(
        ProjectLaboratoryEngagement.project_id == project_id, ProjectLaboratoryEngagement.laboratory_org_id == lab_org_id,
        ProjectLaboratoryEngagement.status == "ACTIVE")).first()


def scope_rule_ids(db: Session, engagement_id: uuid.UUID) -> list[uuid.UUID]:
    return list(db.scalars(select(ProjectLaboratoryEngagementRule.methodology_monitoring_rule_id).where(
        ProjectLaboratoryEngagementRule.engagement_id == engagement_id)).all())


def require_active_for_rule(db: Session, project_id: uuid.UUID, lab_org_id: uuid.UUID, rule_id: uuid.UUID) -> ProjectLaboratoryEngagement:
    """New work (shipments, dispatch, starting tests, retests) needs an ACTIVE engagement covering the rule (wind-down rule)."""
    e = active_engagement(db, project_id, lab_org_id)
    if e is None or rule_id not in scope_rule_ids(db, e.id):
        raise Conflict("No active laboratory engagement covers this work.", error_code="ENGAGEMENT_NOT_ACTIVE")
    return e


def require_active(db: Session, project_id: uuid.UUID, lab_org_id: uuid.UUID) -> ProjectLaboratoryEngagement:
    e = active_engagement(db, project_id, lab_org_id)
    if e is None:
        raise Conflict("No active laboratory engagement for this project and laboratory.", error_code="ENGAGEMENT_NOT_ACTIVE")
    return e


def custody(db: Session, ctx: RequestContext, principal: Principal, s: LabSample, event_type: str, to_state: str, *, side: str,
            org_id: uuid.UUID | None, perm: str, occurred_at: datetime | None = None, reason: str | None = None,
            seal_number: str | None = None, shipment_id: uuid.UUID | None = None, exception_type: str | None = None,
            location_text: str | None = None, check_machine: bool = True) -> SampleCustodyEvent:
    """Append one custody event; the previous state is the sample's current state (ordering + integrity)."""
    from_state = s.status
    if check_machine:
        LAB_SAMPLE_MACHINE.assert_transition(from_state, to_state)
    last = db.scalar(select(func.max(SampleCustodyEvent.sequence_no)).where(SampleCustodyEvent.sample_id == s.id)) or 0
    when = occurred_at or utcnow()
    prev_at = db.scalar(select(func.max(SampleCustodyEvent.occurred_at)).where(SampleCustodyEvent.sample_id == s.id))
    if prev_at is not None and when.replace(tzinfo=None) < prev_at.replace(tzinfo=None):
        raise ValidationFailed("A custody event cannot be dated before the previous one.", error_code="CUSTODY_OUT_OF_ORDER")
    ev = SampleCustodyEvent(sample_id=s.id, sequence_no=last + 1, event_type=event_type, from_state=from_state if last else None,
                            to_state=to_state, actor_user_id=principal.user_id, actor_org_id=org_id, actor_role=actor_role(principal, org_id, perm),
                            actor_side=side, occurred_at=when.replace(tzinfo=None), location_text=location_text, seal_number=seal_number,
                            shipment_id=shipment_id, exception_type=exception_type, reason=reason, request_id=ctx.request_id)
    db.add(ev)
    s.status = to_state
    db.flush()
    audit(db, ctx, f"LAB_CUSTODY_{event_type}", s.id, {"sample_code": s.sample_code, "event": event_type, "from": from_state,
                                                       "to": to_state, "sequence_no": ev.sequence_no},
          org_id or s.laboratory_org_id, reason, entity_type="lab_sample")
    return ev


# ---------------------------------------------------------------- engagements
def laboratories(db: Session, principal: Principal, project_id: uuid.UUID) -> list[Organization]:
    p = project_for(db, principal, project_id, P.LAB_ENGAGE, P.LAB_READ)
    return list(db.scalars(select(Organization).where(Organization.org_type == "LABORATORY", Organization.status == "ACTIVE",
                                                      Organization.environment == p.environment).order_by(Organization.name)).all())


def laboratory_rules(db: Session, principal: Principal, project_id: uuid.UUID) -> list[MethodologyMonitoringRule]:
    """The locked version's monitoring rules declared LABORATORY (the only rules an engagement may cover)."""
    p = project_for(db, principal, project_id, P.LAB_ENGAGE, P.LAB_READ)
    _, v = mrv_access.locked_methodology(db, p)
    return list(db.scalars(select(MethodologyMonitoringRule).where(MethodologyMonitoringRule.methodology_version_id == v.id,
                                                                   MethodologyMonitoringRule.measurement_source == "LABORATORY")
                           .order_by(MethodologyMonitoringRule.rule_code)).all())


def engagements(db: Session, project_id: uuid.UUID) -> list[ProjectLaboratoryEngagement]:
    return list(db.scalars(select(ProjectLaboratoryEngagement).where(ProjectLaboratoryEngagement.project_id == project_id)
                           .order_by(ProjectLaboratoryEngagement.proposed_at.desc())).all())


def get_engagement(db: Session, engagement_id: uuid.UUID) -> ProjectLaboratoryEngagement:
    e = db.get(ProjectLaboratoryEngagement, engagement_id)
    if e is None:
        raise not_found("Engagement")
    return e


def propose_engagement(db: Session, ctx: RequestContext, principal: Principal, data: EngagementIn) -> ProjectLaboratoryEngagement:
    p = project_for(db, principal, data.project_id, P.LAB_ENGAGE)
    _, v = mrv_access.locked_methodology(db, p)
    lab = db.get(Organization, data.laboratory_org_id)
    if lab is None or lab.org_type != "LABORATORY" or lab.status != "ACTIVE":
        raise ValidationFailed("Choose an active laboratory organization.", error_code="NOT_A_LABORATORY")
    if lab.environment != p.environment:
        raise ValidationFailed("DEMO and live records are never mixed.", error_code="ENVIRONMENT_MISMATCH")
    rules = {r.id: r for r in db.scalars(select(MethodologyMonitoringRule).where(MethodologyMonitoringRule.id.in_(data.rule_ids))).all()}
    bad = [str(i) for i in data.rule_ids if i not in rules or rules[i].methodology_version_id != v.id
           or rules[i].measurement_source != "LABORATORY"]
    if bad:
        raise ValidationFailed("Every rule in scope must be a LABORATORY monitoring rule of the project's locked methodology version.",
                               error_code="RULE_NOT_LABORATORY", details={"rule_ids": bad})
    if db.scalars(select(ProjectLaboratoryEngagement).where(
            ProjectLaboratoryEngagement.project_id == p.id, ProjectLaboratoryEngagement.laboratory_org_id == lab.id,
            ProjectLaboratoryEngagement.status == "PROPOSED")).first():
        raise Conflict("A proposal to this laboratory is already waiting for acceptance.", error_code="ENGAGEMENT_PENDING")
    current = active_engagement(db, p.id, lab.id)
    e = ProjectLaboratoryEngagement(project_id=p.id, laboratory_org_id=lab.id, methodology_version_id=v.id, status="PROPOSED",
                                    replaces_engagement_id=current.id if current else None, notes=data.notes,
                                    proposed_by=principal.user_id, environment=p.environment)
    db.add(e)
    db.flush()
    for rid in dict.fromkeys(data.rule_ids):
        db.add(ProjectLaboratoryEngagementRule(engagement_id=e.id, methodology_monitoring_rule_id=rid))
    record_transition(db, ctx, LAB_ENGAGEMENT_MACHINE, e.id, None, "PROPOSED", "LAB_ENGAGEMENT_PROPOSED", data.notes, p.organization_id)
    payload = {"engagement_id": e.id, "project_code": p.project_code, "laboratory": lab.name,
               "rules": [rules[i].rule_code for i in dict.fromkeys(data.rule_ids)], "replaces": current.id if current else None}
    audit(db, ctx, "LAB_ENGAGEMENT_PROPOSED", e.id, payload, p.organization_id, entity_type="lab_engagement")
    audit(db, ctx, "LAB_ENGAGEMENT_PROPOSED", e.id, payload, lab.id, entity_type="lab_engagement")
    db.commit()
    return e


def accept_engagement(db: Session, ctx: RequestContext, principal: Principal, engagement_id: uuid.UUID) -> ProjectLaboratoryEngagement:
    e = get_engagement(db, engagement_id)
    if not principal.can_in_org(P.LAB_ENGAGEMENT_ACCEPT, e.laboratory_org_id):
        raise not_found("Engagement")
    if e.status != "PROPOSED":
        raise Conflict(f"Only a PROPOSED engagement can be accepted (it is {e.status}).", error_code="ENGAGEMENT_NOT_PROPOSED")
    if e.proposed_by == principal.user_id:
        raise PermissionDenied("You proposed this engagement, so someone else must accept it.", error_code="SEPARATION_OF_DUTIES")
    p = db.get(Project, e.project_id)
    assert p is not None
    if e.replaces_engagement_id:                       # scope change: end the old one in the same transaction
        old = db.get(ProjectLaboratoryEngagement, e.replaces_engagement_id)
        if old is not None and old.status == "ACTIVE":
            record_transition(db, ctx, LAB_ENGAGEMENT_MACHINE, old.id, "ACTIVE", "ENDED", "LAB_ENGAGEMENT_ENDED",
                              "Replaced by a new engagement (scope change)", p.organization_id)
            old.status, old.ended_by, old.ended_at, old.ended_side = "ENDED", principal.user_id, utcnow(), "LABORATORY"
            old.end_reason = f"Replaced by engagement {e.id} (scope change)"
            db.flush()
    record_transition(db, ctx, LAB_ENGAGEMENT_MACHINE, e.id, "PROPOSED", "ACTIVE", "LAB_ENGAGEMENT_ACCEPTED", None, e.laboratory_org_id)
    e.status, e.accepted_by, e.accepted_at = "ACTIVE", principal.user_id, utcnow()
    db.flush()
    payload = {"engagement_id": e.id, "project_code": p.project_code, "replaced": e.replaces_engagement_id}
    audit(db, ctx, "LAB_ENGAGEMENT_ACCEPTED", e.id, payload, e.laboratory_org_id, entity_type="lab_engagement")
    audit(db, ctx, "LAB_ENGAGEMENT_ACCEPTED", e.id, payload, p.organization_id, entity_type="lab_engagement")
    db.commit()
    return e


def end_engagement(db: Session, ctx: RequestContext, principal: Principal, engagement_id: uuid.UUID, reason: str, side: str
                   ) -> ProjectLaboratoryEngagement:
    """Either side may end (with a reason). Never reactivated: collaboration resumes through a new engagement."""
    e = get_engagement(db, engagement_id)
    p = db.get(Project, e.project_id)
    assert p is not None
    allowed = (principal.can_in_org(P.LAB_ENGAGE, p.organization_id) if side == "PROJECT"
               else principal.can_in_org(P.LAB_ENGAGEMENT_ACCEPT, e.laboratory_org_id))
    if not allowed:
        raise not_found("Engagement")
    if e.status == "ENDED":
        raise Conflict("This engagement has already ended.", error_code="ENGAGEMENT_ENDED")
    record_transition(db, ctx, LAB_ENGAGEMENT_MACHINE, e.id, e.status, "ENDED", "LAB_ENGAGEMENT_ENDED", reason,
                      p.organization_id if side == "PROJECT" else e.laboratory_org_id)
    e.status, e.ended_by, e.ended_at, e.ended_side, e.end_reason = "ENDED", principal.user_id, utcnow(), side, reason
    db.flush()
    payload = {"engagement_id": e.id, "project_code": p.project_code, "side": side}
    audit(db, ctx, "LAB_ENGAGEMENT_ENDED", e.id, payload, p.organization_id, reason, entity_type="lab_engagement")
    audit(db, ctx, "LAB_ENGAGEMENT_ENDED", e.id, payload, e.laboratory_org_id, reason, entity_type="lab_engagement")
    db.commit()
    return e


# ---------------------------------------------------------------- samples (project side)
def get_sample(db: Session, principal: Principal, sample_id: uuid.UUID, *codes: str) -> tuple[LabSample, Project]:
    s = db.get(LabSample, sample_id)
    if s is None:
        raise not_found("Sample")
    p = db.get(Project, s.project_id)
    assert p is not None
    if any(principal.can_in_org(c, p.organization_id) for c in codes):
        if not principal.can_in_org(P.LAB_READ, p.organization_id) and not principal.can_in_org(P.LAB_SAMPLE_MANAGE, p.organization_id):
            _own_or_404(db, principal, s)      # field agents: samples of their own collections only
        return s, p
    if principal.can_in_org(P.LAB_READ, p.organization_id):
        raise PermissionDenied(details={"required_permission": " or ".join(codes)})
    raise not_found("Sample")


def _own_or_404(db: Session, principal: Principal, s: LabSample) -> None:
    fc = db.get(FieldCollectionRecord, s.field_collection_id)
    if fc is None or fc.collector_id != principal.user_id:
        raise not_found("Sample")


def samples(db: Session, principal: Principal, *, project_id: uuid.UUID | None = None, monitoring_period_id: uuid.UUID | None = None,
            field_collection_id: uuid.UUID | None = None) -> list[LabSample]:
    stmt = select(LabSample)
    if project_id:
        stmt = stmt.where(LabSample.project_id == project_id)
    if monitoring_period_id:
        stmt = stmt.where(LabSample.monitoring_period_id == monitoring_period_id)
    if field_collection_id:
        stmt = stmt.where(LabSample.field_collection_id == field_collection_id)
    out = []
    for s in db.scalars(stmt.order_by(LabSample.registered_at.desc())).all():
        p = db.get(Project, s.project_id)
        if p is None:
            continue
        if principal.can_in_org(P.LAB_READ, p.organization_id) or principal.can_in_org(P.LAB_SAMPLE_MANAGE, p.organization_id):
            out.append(s)
        elif principal.can_in_org(P.LAB_SAMPLE_REGISTER, p.organization_id):
            fc = db.get(FieldCollectionRecord, s.field_collection_id)
            if fc is not None and fc.collector_id == principal.user_id:
                out.append(s)
    return out


def register_sample(db: Session, ctx: RequestContext, principal: Principal, data: SampleIn) -> LabSample:
    fc = db.get(FieldCollectionRecord, data.field_collection_id)
    if fc is None:
        raise not_found("Field collection")
    p = project_for(db, principal, fc.project_id, P.LAB_SAMPLE_REGISTER)
    manager = principal.can_in_org(P.LAB_SAMPLE_MANAGE, p.organization_id)
    if not manager and fc.collector_id != principal.user_id:
        raise PermissionDenied("Field collectors register samples of their own field collections only.", error_code="NOT_COLLECTOR")
    if fc.status not in REGISTRABLE_COLLECTION_STATES:
        raise Conflict(f"Samples are registered from SUBMITTED or ACCEPTED field collections (this one is {fc.status}).",
                       error_code="FIELD_COLLECTION_NOT_READY")
    _, v = mrv_access.locked_methodology(db, p)
    parent = None
    if data.parent_sample_id:
        parent = db.get(LabSample, data.parent_sample_id)
        if parent is None or parent.field_collection_id != fc.id:
            raise ValidationFailed("A split must come from a sample of the same field collection.", error_code="INVALID_PARENT")
        if parent.status in ("VOIDED", "REJECTED_AT_RECEIPT"):
            raise Conflict(f"Cannot split a {parent.status} sample.", error_code="INVALID_PARENT")
        engagement = require_active(db, p.id, parent.laboratory_org_id)
    elif data.laboratory_org_id:
        engagement = require_active(db, p.id, data.laboratory_org_id)
    else:
        active = db.scalars(select(ProjectLaboratoryEngagement).where(ProjectLaboratoryEngagement.project_id == p.id,
                                                                      ProjectLaboratoryEngagement.status == "ACTIVE")).all()
        if not active:
            raise Conflict("Engage a laboratory for this project before registering samples.", error_code="ENGAGEMENT_NOT_ACTIVE")
        if len(active) > 1:
            raise ValidationFailed("Several laboratories are engaged; choose one.", error_code="LABORATORY_REQUIRED")
        engagement = active[0]
    top = data.depth_top_cm if data.depth_top_cm is not None else fc.actual_depth_top_cm
    bottom = data.depth_bottom_cm if data.depth_bottom_cm is not None else fc.actual_depth_bottom_cm
    if top is None or bottom is None:
        raise ValidationFailed("Give the sample depth (the field collection has no actual depth recorded).", error_code="DEPTH_REQUIRED")
    if bottom <= top:
        raise ValidationFailed("depth_bottom_cm must be greater than depth_top_cm.", error_code="INVALID_DEPTH")
    if fc.actual_depth_top_cm is not None and fc.actual_depth_bottom_cm is not None and \
            not (fc.actual_depth_top_cm <= top and bottom <= fc.actual_depth_bottom_cm):
        raise ValidationFailed("The sample depth must lie within the field collection's actual depth.", error_code="INVALID_DEPTH")
    mp = db.get(MonitoringPeriod, fc.monitoring_period_id)
    assert mp is not None
    rules = scope_rule_ids(db, engagement.id)
    measures = {m.monitoring_rule_id: m for m in db.scalars(select(MrvPlanMeasurement).where(
        MrvPlanMeasurement.mrv_plan_id == mp.mrv_plan_id, MrvPlanMeasurement.monitoring_rule_id.in_(rules or [uuid.uuid4()]))).all()}
    if parent is None:
        missing = [str(r) for r in rules if r not in measures]
        if missing:
            raise Conflict("The period's MRV plan has no measurement for a rule in the engagement scope.", error_code="PLAN_MEASUREMENT_MISSING",
                           details={"rule_ids": missing})
    sid = uuid.uuid4()
    s = LabSample(id=sid, sample_code=next_code(db, "lab_sample", mp.start_date.year), root_sample_id=parent.root_sample_id if parent else sid,
                  parent_sample_id=parent.id if parent else None, field_collection_id=fc.id, sampling_point_id=fc.sampling_point_id,
                  monitoring_period_id=mp.id, farm_id=fc.farm_id, project_id=p.id, methodology_version_id=v.id, engagement_id=engagement.id,
                  laboratory_org_id=engagement.laboratory_org_id, status="REGISTERED", description=data.description,
                  depth_top_cm=Decimal(top), depth_bottom_cm=Decimal(bottom), quantity=data.quantity, quantity_unit=data.quantity_unit,
                  container_label=data.container_label, registered_by=principal.user_id, environment=p.environment)
    db.add(s)
    db.flush()
    custody(db, ctx, principal, s, "REGISTERED", "REGISTERED", side="PROJECT", org_id=p.organization_id, perm=P.LAB_SAMPLE_REGISTER,
            check_machine=False)
    tests: list[LabTest] = []
    if parent is None:                          # decision: one test per in-scope LABORATORY rule, created automatically
        for rid in rules:
            t = LabTest(test_code=next_code(db, "lab_test", mp.start_date.year), sample_id=s.id, root_sample_id=s.root_sample_id,
                        project_id=p.id, laboratory_org_id=s.laboratory_org_id, engagement_id=engagement.id, methodology_version_id=v.id,
                        methodology_monitoring_rule_id=rid, mrv_plan_measurement_id=measures[rid].id, status="REQUESTED",
                        created_by=principal.user_id, environment=p.environment)
            db.add(t)
            db.flush()
            record_transition(db, ctx, LAB_TEST_MACHINE, t.id, None, "REQUESTED", "LAB_TEST_CREATED", None, p.organization_id)
            tests.append(t)
    audit(db, ctx, "LAB_SAMPLE_REGISTERED", s.id, {"sample_code": s.sample_code, "field_collection": fc.collection_code,
                                                   "field_collection_version": fc.version, "parent": parent.sample_code if parent else None,
                                                   "engagement_id": engagement.id, "tests": [t.test_code for t in tests]},
          p.organization_id, entity_type="lab_sample")
    db.commit()
    return s


def update_sample(db: Session, ctx: RequestContext, principal: Principal, sample_id: uuid.UUID, data: SampleUpdate) -> LabSample:
    s, p = get_sample(db, principal, sample_id, P.LAB_SAMPLE_MANAGE, P.LAB_SAMPLE_REGISTER)
    if not principal.can_in_org(P.LAB_SAMPLE_MANAGE, p.organization_id) and s.registered_by != principal.user_id:
        raise PermissionDenied("Only the registrant or a sample manager can correct a sample.", error_code="NOT_REGISTRANT")
    if s.status != "REGISTERED":
        raise Conflict("Physical details can only be corrected before the sample is sealed.", error_code="SAMPLE_SEALED")
    changes = data.model_dump(exclude_unset=True)
    for k, val in changes.items():
        setattr(s, k, val)
    audit(db, ctx, "LAB_SAMPLE_UPDATED", s.id, {"sample_code": s.sample_code, **{k: str(v) for k, v in changes.items()}},
          p.organization_id, entity_type="lab_sample")
    db.commit()
    return s


def seal_sample(db: Session, ctx: RequestContext, principal: Principal, sample_id: uuid.UUID, data: SealIn) -> LabSample:
    s, p = get_sample(db, principal, sample_id, P.LAB_SAMPLE_REGISTER, P.LAB_SAMPLE_MANAGE)
    if not principal.can_in_org(P.LAB_SAMPLE_MANAGE, p.organization_id):
        _own_or_404(db, principal, s)
    if s.status != "REGISTERED":
        raise Conflict(f"Only a REGISTERED sample can be sealed (it is {s.status}).", error_code="SAMPLE_NOT_REGISTERED")
    custody(db, ctx, principal, s, "SEALED", "SEALED", side="PROJECT", org_id=p.organization_id, perm=P.LAB_SAMPLE_REGISTER,
            occurred_at=data.occurred_at, seal_number=data.seal_number, location_text=data.location_text)
    s.seal_number, s.sealed_by, s.sealed_at = data.seal_number, principal.user_id, utcnow()
    db.commit()
    return s


def void_sample(db: Session, ctx: RequestContext, principal: Principal, sample_id: uuid.UUID, reason: str) -> LabSample:
    s, p = get_sample(db, principal, sample_id, P.LAB_SAMPLE_MANAGE)
    if s.status not in ("REGISTERED", "SEALED"):
        raise Conflict("Only samples not yet in a shipment can be voided.", error_code="SAMPLE_NOT_VOIDABLE")
    custody(db, ctx, principal, s, "VOIDED", "VOIDED", side="PROJECT", org_id=p.organization_id, perm=P.LAB_SAMPLE_MANAGE, reason=reason)
    cancel_tests(db, ctx, s, reason, p.organization_id)
    db.commit()
    return s


def cancel_tests(db: Session, ctx: RequestContext, s: LabSample, reason: str, org: uuid.UUID) -> None:
    for t in db.scalars(select(LabTest).where(LabTest.sample_id == s.id, LabTest.status.in_(["REQUESTED", "IN_PROGRESS"]))).all():
        record_transition(db, ctx, LAB_TEST_MACHINE, t.id, t.status, "CANCELLED", "LAB_TEST_CANCELLED", reason, org)
        t.status = "CANCELLED"


def exception_origin(db: Session, s: LabSample) -> str | None:
    """The state an open EXCEPTION interrupted (from the custody history — nothing is rewritten)."""
    ev = db.scalars(select(SampleCustodyEvent).where(SampleCustodyEvent.sample_id == s.id, SampleCustodyEvent.event_type == "EXCEPTION_RECORDED")
                    .order_by(SampleCustodyEvent.sequence_no.desc())).first()
    return ev.from_state if ev else None


def custody_action(db: Session, ctx: RequestContext, principal: Principal, s: LabSample, data: CustodyEventIn, *, side: str,
                   org_id: uuid.UUID, perm: str) -> SampleCustodyEvent:
    """Transfers, exceptions and their resolution, by the side that holds the sample."""
    holder_states = PROJECT_SIDE_STATES if side == "PROJECT" else LAB_SIDE_STATES
    current = exception_origin(db, s) if s.status == "EXCEPTION" else s.status
    if current not in holder_states:
        raise Conflict("The sample is not in your custody.", error_code="NOT_CUSTODIAN")
    if data.event_type == "TRANSFERRED":
        if side != "PROJECT" or s.status not in ("DISPATCHED", "IN_TRANSIT"):
            raise Conflict("Transfers are recorded while a dispatched sample is in transit.", error_code="INVALID_CUSTODY_EVENT")
        ev = custody(db, ctx, principal, s, "TRANSFERRED", "IN_TRANSIT", side=side, org_id=org_id, perm=perm, occurred_at=data.occurred_at,
                     reason=data.reason, location_text=data.location_text)
    elif data.event_type == "EXCEPTION_RECORDED":
        if s.status == "EXCEPTION":
            raise Conflict("An exception is already open for this sample.", error_code="EXCEPTION_OPEN")
        ev = custody(db, ctx, principal, s, "EXCEPTION_RECORDED", "EXCEPTION", side=side, org_id=org_id, perm=perm,
                     occurred_at=data.occurred_at, reason=data.reason, exception_type=data.exception_type, location_text=data.location_text)
    else:
        if s.status != "EXCEPTION":
            raise Conflict("No open exception to resolve.", error_code="NO_EXCEPTION")
        target = data.resolve_to or current
        if data.resolve_to == "VOIDED" and side != "PROJECT":
            raise Conflict("Only the project side voids a sample.", error_code="INVALID_CUSTODY_EVENT")
        if data.resolve_to == "REJECTED_AT_RECEIPT" and side != "LABORATORY":
            raise Conflict("Only the laboratory rejects a sample.", error_code="INVALID_CUSTODY_EVENT")
        assert target is not None
        ev = custody(db, ctx, principal, s, "EXCEPTION_RESOLVED", target, side=side, org_id=org_id, perm=perm, occurred_at=data.occurred_at,
                     reason=data.reason, location_text=data.location_text)
        if target in ("VOIDED", "REJECTED_AT_RECEIPT"):
            cancel_tests(db, ctx, s, data.reason or target, org_id)
    db.commit()
    return ev


def project_custody(db: Session, ctx: RequestContext, principal: Principal, sample_id: uuid.UUID, data: CustodyEventIn) -> SampleCustodyEvent:
    s, p = get_sample(db, principal, sample_id, P.LAB_SAMPLE_MANAGE)
    return custody_action(db, ctx, principal, s, data, side="PROJECT", org_id=p.organization_id, perm=P.LAB_SAMPLE_MANAGE)


# ---------------------------------------------------------------- shipments (project side)
def get_shipment(db: Session, principal: Principal, shipment_id: uuid.UUID, *codes: str) -> tuple[LabShipment, Project]:
    sh = db.get(LabShipment, shipment_id)
    if sh is None:
        raise not_found("Shipment")
    p = db.get(Project, sh.project_id)
    assert p is not None
    if any(principal.can_in_org(c, p.organization_id) for c in codes):
        return sh, p
    if principal.can_in_org(P.LAB_READ, p.organization_id):
        raise PermissionDenied(details={"required_permission": " or ".join(codes)})
    raise not_found("Shipment")


def shipments(db: Session, project_id: uuid.UUID) -> list[LabShipment]:
    return list(db.scalars(select(LabShipment).where(LabShipment.project_id == project_id).order_by(LabShipment.created_at.desc())).all())


def shipment_items(db: Session, shipment_id: uuid.UUID) -> list[LabShipmentItem]:
    return list(db.scalars(select(LabShipmentItem).where(LabShipmentItem.shipment_id == shipment_id).order_by(LabShipmentItem.added_at)).all())


def create_shipment(db: Session, ctx: RequestContext, principal: Principal, data: ShipmentIn) -> LabShipment:
    p = project_for(db, principal, data.project_id, P.LAB_SHIPMENT_MANAGE)
    e = require_active(db, p.id, data.laboratory_org_id)
    mp_year = utcnow().year
    sh = LabShipment(shipment_code=next_code(db, "lab_shipment", mp_year), project_id=p.id, engagement_id=e.id,
                     laboratory_org_id=data.laboratory_org_id, status="DRAFT", carrier=data.carrier, tracking_number=data.tracking_number,
                     notes=data.notes, created_by=principal.user_id, environment=p.environment)
    db.add(sh)
    db.flush()
    record_transition(db, ctx, LAB_SHIPMENT_MACHINE, sh.id, None, "DRAFT", "LAB_SHIPMENT_CREATED", None, p.organization_id)
    audit(db, ctx, "LAB_SHIPMENT_CREATED", sh.id, {"shipment_code": sh.shipment_code, "laboratory": org_name(db, sh.laboratory_org_id)},
          p.organization_id, entity_type="lab_shipment")
    db.commit()
    return sh


def add_items(db: Session, ctx: RequestContext, principal: Principal, shipment_id: uuid.UUID, sample_ids: list[uuid.UUID]) -> LabShipment:
    sh, p = get_shipment(db, principal, shipment_id, P.LAB_SHIPMENT_MANAGE)
    if sh.status != "DRAFT":
        raise Conflict("Samples can only be added to a DRAFT shipment.", error_code="SHIPMENT_NOT_DRAFT")
    require_active(db, p.id, sh.laboratory_org_id)
    for sid in dict.fromkeys(sample_ids):
        s = db.get(LabSample, sid)
        if s is None or s.project_id != p.id:
            raise ValidationFailed("Sample not found in this project.", error_code="SAMPLE_NOT_IN_PROJECT", details={"sample_id": str(sid)})
        if s.laboratory_org_id != sh.laboratory_org_id:
            raise ValidationFailed(f"{s.sample_code} is registered for another laboratory.", error_code="WRONG_LABORATORY")
        if s.status != "SEALED":
            raise Conflict(f"{s.sample_code} must be SEALED to be shipped (it is {s.status}).", error_code="SAMPLE_NOT_SEALED")
        db.add(LabShipmentItem(shipment_id=sh.id, sample_id=s.id, status="IN_SHIPMENT", added_by=principal.user_id))
        custody(db, ctx, principal, s, "ADDED_TO_SHIPMENT", "IN_SHIPMENT", side="PROJECT", org_id=p.organization_id,
                perm=P.LAB_SHIPMENT_MANAGE, shipment_id=sh.id, seal_number=s.seal_number)
    db.commit()
    return sh


def remove_item(db: Session, ctx: RequestContext, principal: Principal, shipment_id: uuid.UUID, sample_id: uuid.UUID) -> LabShipment:
    sh, p = get_shipment(db, principal, shipment_id, P.LAB_SHIPMENT_MANAGE)
    if sh.status != "DRAFT":
        raise Conflict("Samples can only be removed from a DRAFT shipment.", error_code="SHIPMENT_NOT_DRAFT")
    it = next((i for i in shipment_items(db, sh.id) if i.sample_id == sample_id and i.status == "IN_SHIPMENT"), None)
    if it is None:
        raise not_found("Shipment item")
    s = db.get(LabSample, sample_id)
    assert s is not None
    it.status = "REMOVED"
    custody(db, ctx, principal, s, "REMOVED_FROM_SHIPMENT", "SEALED", side="PROJECT", org_id=p.organization_id, perm=P.LAB_SHIPMENT_MANAGE,
            shipment_id=sh.id)
    db.commit()
    return sh


def dispatch_shipment(db: Session, ctx: RequestContext, principal: Principal, shipment_id: uuid.UUID, occurred_at: datetime | None) -> LabShipment:
    sh, p = get_shipment(db, principal, shipment_id, P.LAB_SHIPMENT_MANAGE)
    e = require_active(db, p.id, sh.laboratory_org_id)
    items = [i for i in shipment_items(db, sh.id) if i.status == "IN_SHIPMENT"]
    if not items:
        raise Conflict("Add at least one sealed sample before dispatching.", error_code="SHIPMENT_EMPTY")
    record_transition(db, ctx, LAB_SHIPMENT_MACHINE, sh.id, sh.status, "DISPATCHED", "LAB_SHIPMENT_DISPATCHED", None, p.organization_id)
    for it in items:
        s = db.get(LabSample, it.sample_id)
        assert s is not None
        custody(db, ctx, principal, s, "DISPATCHED", "DISPATCHED", side="PROJECT", org_id=p.organization_id, perm=P.LAB_SHIPMENT_MANAGE,
                shipment_id=sh.id, seal_number=s.seal_number, occurred_at=occurred_at)
    sh.status, sh.dispatched_by, sh.dispatched_at, sh.engagement_id = "DISPATCHED", principal.user_id, utcnow(), e.id
    audit(db, ctx, "LAB_SHIPMENT_DISPATCHED", sh.id, {"shipment_code": sh.shipment_code, "samples": len(items)}, p.organization_id,
          entity_type="lab_shipment")
    audit(db, ctx, "LAB_SHIPMENT_DISPATCHED", sh.id, {"shipment_code": sh.shipment_code, "samples": len(items)}, sh.laboratory_org_id,
          entity_type="lab_shipment")
    db.commit()
    return sh


def cancel_shipment(db: Session, ctx: RequestContext, principal: Principal, shipment_id: uuid.UUID, reason: str) -> LabShipment:
    sh, p = get_shipment(db, principal, shipment_id, P.LAB_SHIPMENT_MANAGE)
    record_transition(db, ctx, LAB_SHIPMENT_MACHINE, sh.id, sh.status, "CANCELLED", "LAB_SHIPMENT_CANCELLED", reason, p.organization_id)
    for it in shipment_items(db, sh.id):
        if it.status == "IN_SHIPMENT":
            it.status = "REMOVED"
            s = db.get(LabSample, it.sample_id)
            assert s is not None
            custody(db, ctx, principal, s, "REMOVED_FROM_SHIPMENT", "SEALED", side="PROJECT", org_id=p.organization_id,
                    perm=P.LAB_SHIPMENT_MANAGE, shipment_id=sh.id, reason=reason)
    sh.status, sh.cancel_reason = "CANCELLED", reason
    audit(db, ctx, "LAB_SHIPMENT_CANCELLED", sh.id, {"shipment_code": sh.shipment_code}, p.organization_id, reason, entity_type="lab_shipment")
    db.commit()
    return sh


# ---------------------------------------------------------------- read models
def tests_of_sample(db: Session, sample_id: uuid.UUID) -> list[LabTest]:
    return list(db.scalars(select(LabTest).where(LabTest.sample_id == sample_id).order_by(LabTest.created_at)).all())


def results_of_test(db: Session, test_id: uuid.UUID) -> list[LabResult]:
    return list(db.scalars(select(LabResult).where(LabResult.test_id == test_id).order_by(LabResult.version)).all())


def custody_events(db: Session, sample_id: uuid.UUID) -> list[SampleCustodyEvent]:
    return list(db.scalars(select(SampleCustodyEvent).where(SampleCustodyEvent.sample_id == sample_id)
                           .order_by(SampleCustodyEvent.sequence_no)).all())


def project_results(db: Session, principal: Principal, project_id: uuid.UUID, status: str | None = "APPROVED") -> list[LabResult]:
    p = project_for(db, principal, project_id, P.LAB_READ)
    stmt = select(LabResult).where(LabResult.project_id == p.id, LabResult.status != "DRAFT")   # drafts never reach project users
    if status:
        stmt = stmt.where(LabResult.status == status)
    return list(db.scalars(stmt.order_by(LabResult.created_at.desc())).all())


def get_project_result(db: Session, principal: Principal, result_id: uuid.UUID) -> LabResult:
    r = db.get(LabResult, result_id)
    if r is None or r.status == "DRAFT":
        raise not_found("Result")
    project_for(db, principal, r.project_id, P.LAB_READ)
    return r


def approved_for(db: Session, root_sample_ids: set[uuid.UUID], rule_id: uuid.UUID) -> LabResult | None:
    if not root_sample_ids:
        return None
    return db.scalars(select(LabResult).where(LabResult.root_sample_id.in_(root_sample_ids), LabResult.methodology_monitoring_rule_id == rule_id,
                                              LabResult.status == "APPROVED")).first()


def collection_analysis_status(db: Session, fc: FieldCollectionRecord, lab_rule_ids: list[uuid.UUID]) -> str:
    """Phase 5 display (decision 19): ANALYSED once every methodology LABORATORY parameter of the plan has an APPROVED result
    for a sample from this collection."""
    roots = set(db.scalars(select(LabSample.root_sample_id).where(LabSample.field_collection_id == fc.id)).all())
    if lab_rule_ids and roots and all(approved_for(db, roots, rid) is not None for rid in lab_rule_ids):
        return "ANALYSED"
    return "AWAITING_ANALYSIS"
