"""Phase 6 response builders.

Project-side builders may include internal lineage. Laboratory-facing builders (`*_lab_view`) assemble their response from
an explicit allow-list only — they never read or pass on farm, farmer, GPS, sampling-point, field-collection, stratum,
project-name or project-side location data (decision 16).
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    FarmBoundary,
    FieldCollectionRecord,
    LabResult,
    LabResultQaReview,
    LabSample,
    LabShipment,
    LabTest,
    Methodology,
    MethodologyMonitoringRule,
    MethodologyVersion,
    MrvPlan,
    MrvPlanMeasurement,
    Project,
    ProjectLaboratoryEngagement,
    ProjectStratum,
    SampleCustodyEvent,
    SamplingPoint,
)
from app.models.farms import Farm
from app.schemas.lab import (
    CustodyEventLabView,
    CustodyEventOut,
    DocumentRef,
    EngagementLabView,
    EngagementOut,
    LabQaCheck,
    LineageOut,
    QaReviewOut,
    ResultLabView,
    ResultOut,
    RuleRef,
    SampleDetailOut,
    SampleLabView,
    SampleOut,
    ShipmentItemLabView,
    ShipmentItemOut,
    ShipmentLabView,
    ShipmentOut,
    TestLabView,
    TestOut,
)
from app.security.permissions import P
from app.security.principal import Principal
from app.services import lab_service as ls
from app.services import laboratory_service as lab


def _methodology_label(db: Session, version_id: uuid.UUID) -> str:
    v = db.get(MethodologyVersion, version_id)
    m = db.get(Methodology, v.methodology_id) if v else None
    return f"{m.code} v{v.version_label}" if (m and v) else ""


def rule_ref(db: Session, rule_id: uuid.UUID) -> RuleRef:
    r = db.get(MethodologyMonitoringRule, rule_id)
    assert r is not None
    return RuleRef(rule_id=r.id, rule_code=r.rule_code, parameter=r.parameter, unit=r.unit, method=r.method, measurement_source=r.measurement_source)


def _doc(db: Session, doc_id: uuid.UUID | None) -> DocumentRef | None:
    d = lab.doc_ref(db, doc_id)
    return DocumentRef(**d) if d else None


def _sample(db: Session, sample_id: uuid.UUID) -> LabSample:
    s = db.get(LabSample, sample_id)
    assert s is not None
    return s


def _shipment_docs(db: Session, shipment_id: uuid.UUID) -> list[DocumentRef]:
    return [d for d in (_doc(db, x.id) for x in lab.document_ids_for_shipment(db, shipment_id)) if d is not None]


def _project_code(db: Session, project_id: uuid.UUID) -> str:
    p = db.get(Project, project_id)
    return p.project_code if p else ""


# ---------------------------------------------------------------- engagements
def engagement_out(db: Session, principal: Principal, e: ProjectLaboratoryEngagement) -> EngagementOut:
    p = db.get(Project, e.project_id)
    assert p is not None
    n = ls.names(db, {e.proposed_by, e.accepted_by, e.ended_by})
    return EngagementOut(id=e.id, project_id=p.id, project_code=p.project_code, project_name=p.name,
                         project_org_name=ls.org_name(db, p.organization_id), laboratory_org_id=e.laboratory_org_id,
                         laboratory_org_name=ls.org_name(db, e.laboratory_org_id), methodology_version_id=e.methodology_version_id,
                         methodology_label=_methodology_label(db, e.methodology_version_id), status=e.status,
                         replaces_engagement_id=e.replaces_engagement_id, notes=e.notes,
                         rules=[rule_ref(db, r) for r in ls.scope_rule_ids(db, e.id)], proposed_by_name=n.get(e.proposed_by),
                         proposed_at=e.proposed_at, accepted_by_name=n.get(e.accepted_by) if e.accepted_by else None, accepted_at=e.accepted_at,
                         ended_by_name=n.get(e.ended_by) if e.ended_by else None, ended_at=e.ended_at, ended_side=e.ended_side,
                         end_reason=e.end_reason, environment=e.environment,
                         can_end=e.status != "ENDED" and principal.can_in_org(P.LAB_ENGAGE, p.organization_id))


def engagement_lab_view(db: Session, principal: Principal, e: ProjectLaboratoryEngagement) -> EngagementLabView:
    p = db.get(Project, e.project_id)
    assert p is not None
    can_accept = (e.status == "PROPOSED" and principal.can_in_org(P.LAB_ENGAGEMENT_ACCEPT, e.laboratory_org_id)
                  and e.proposed_by != principal.user_id)
    return EngagementLabView(id=e.id, project_code=p.project_code, project_org_name=ls.org_name(db, p.organization_id),
                             laboratory_org_name=ls.org_name(db, e.laboratory_org_id),
                             methodology_label=_methodology_label(db, e.methodology_version_id), status=e.status,
                             rules=[rule_ref(db, r) for r in ls.scope_rule_ids(db, e.id)], proposed_at=e.proposed_at, accepted_at=e.accepted_at,
                             ended_at=e.ended_at, ended_side=e.ended_side, end_reason=e.end_reason, environment=e.environment,
                             can_accept=can_accept,
                             can_end=e.status != "ENDED" and principal.can_in_org(P.LAB_ENGAGEMENT_ACCEPT, e.laboratory_org_id))


# ---------------------------------------------------------------- results / tests / samples (project side)
def result_out(db: Session, r: LabResult) -> ResultOut:
    t = db.get(LabTest, r.test_id)
    rule = db.get(MethodologyMonitoringRule, r.methodology_monitoring_rule_id)
    n = ls.names(db, {r.analyst_id, r.approved_by})
    return ResultOut(id=r.id, test_id=r.test_id, test_code=t.test_code if t else "", version=r.version, status=r.status, result_type=r.result_type,
                     value_number=r.value_number, value_text=r.value_text, unit=r.unit, analysed_at=r.analysed_at,
                     analyst_name=n.get(r.analyst_id), method_reported=r.method_reported, report=_doc(db, r.report_document_id),
                     source=r.source, supersedes_result_id=r.supersedes_result_id, superseded_by_result_id=r.superseded_by_result_id,
                     status_reason=r.status_reason, submitted_at=r.submitted_at, approved_at=r.approved_at,
                     approved_by_name=n.get(r.approved_by) if r.approved_by else None, rule_code=rule.rule_code if rule else "",
                     parameter=rule.parameter if rule else "", authoritative=r.status == "APPROVED")


def test_out(db: Session, t: LabTest, include_drafts: bool = False) -> TestOut:
    s = db.get(LabSample, t.sample_id)
    m = db.get(MrvPlanMeasurement, t.mrv_plan_measurement_id)
    orig = db.get(LabTest, t.retest_of_test_id) if t.retest_of_test_id else None
    results = [r for r in ls.results_of_test(db, t.id) if include_drafts or r.status != "DRAFT"]
    return TestOut(id=t.id, test_code=t.test_code, status=t.status, sample_code=s.sample_code if s else "", rule=rule_ref(db,
                                                                                                                          t.methodology_monitoring_rule_id),
                   plan_measurement_code=m.code if m else "", plan_measurement_type=m.value_type if m else "",
                   retest_of_test_code=orig.test_code if orig else None, retest_reason=t.retest_reason,
                   laboratory_org_name=ls.org_name(db, t.laboratory_org_id), results=[result_out(db, r) for r in results])


def custody_out(db: Session, events: list[SampleCustodyEvent]) -> list[CustodyEventOut]:
    n = ls.names(db, {e.actor_user_id for e in events})
    out = []
    for e in events:
        sh = db.get(LabShipment, e.shipment_id) if e.shipment_id else None
        out.append(CustodyEventOut(sequence_no=e.sequence_no, event_type=e.event_type, from_state=e.from_state, to_state=e.to_state,
                                   actor_name=n.get(e.actor_user_id), actor_org_name=ls.org_name(db, e.actor_org_id), actor_role=e.actor_role,
                                   actor_side=e.actor_side, occurred_at=e.occurred_at, recorded_at=e.recorded_at, location_text=e.location_text,
                                   latitude=e.latitude, longitude=e.longitude, seal_number=e.seal_number,
                                   shipment_code=sh.shipment_code if sh else None, exception_type=e.exception_type, reason=e.reason))
    return out


def sample_out(db: Session, principal: Principal, s: LabSample) -> SampleOut:
    fc = db.get(FieldCollectionRecord, s.field_collection_id)
    sp = db.get(SamplingPoint, s.sampling_point_id)
    farm = db.get(Farm, s.farm_id)
    root = db.get(LabSample, s.root_sample_id)
    parent = db.get(LabSample, s.parent_sample_id) if s.parent_sample_id else None
    p = db.get(Project, s.project_id)
    assert fc is not None and p is not None
    tests = ls.tests_of_sample(db, s.id)
    approved = sum(1 for t in tests if any(r.status == "APPROVED" for r in ls.results_of_test(db, t.id)))
    org = p.organization_id
    manager = principal.can_in_org(P.LAB_SAMPLE_MANAGE, org)
    own = fc.collector_id == principal.user_id
    can_register = principal.can_in_org(P.LAB_SAMPLE_REGISTER, org) and (manager or own)
    n = ls.names(db, {s.registered_by})
    return SampleOut(id=s.id, sample_code=s.sample_code, root_sample_code=root.sample_code if root else s.sample_code,
                     parent_sample_code=parent.sample_code if parent else None, status=s.status, description=s.description,
                     depth_top_cm=s.depth_top_cm, depth_bottom_cm=s.depth_bottom_cm, quantity=s.quantity, quantity_unit=s.quantity_unit,
                     container_label=s.container_label, seal_number=s.seal_number, accession_number=s.accession_number,
                     field_collection_id=fc.id, field_collection_code=fc.collection_code, field_collection_version=fc.version,
                     field_collection_status=fc.status, sampling_point_code=sp.point_code if sp else "", farm_code=farm.farm_code if farm else None,
                     project_id=p.id, project_code=p.project_code, monitoring_period_id=s.monitoring_period_id, laboratory_org_id=s.laboratory_org_id,
                     laboratory_org_name=ls.org_name(db, s.laboratory_org_id), engagement_id=s.engagement_id,
                     registered_by_name=n.get(s.registered_by), registered_at=s.registered_at, sealed_at=s.sealed_at, environment=s.environment,
                     test_count=len(tests), approved_count=approved, can_seal=s.status == "REGISTERED" and can_register,
                     can_edit=s.status == "REGISTERED" and (manager or s.registered_by == principal.user_id))


def sample_detail(db: Session, principal: Principal, s: LabSample) -> SampleDetailOut:
    base = sample_out(db, principal, s)
    events = ls.custody_events(db, s.id)
    codes = {sh.shipment_code for sh in (db.get(LabShipment, e.shipment_id) for e in events if e.shipment_id) if sh is not None}
    shipments = sorted(codes)
    return SampleDetailOut(**base.model_dump(), custody=custody_out(db, ls.custody_events(db, s.id)),
                           tests=[test_out(db, t) for t in ls.tests_of_sample(db, s.id)], shipments=shipments)


def shipment_out(db: Session, sh: LabShipment) -> ShipmentOut:
    items = ls.shipment_items(db, sh.id)
    return ShipmentOut(id=sh.id, shipment_code=sh.shipment_code, project_id=sh.project_id, project_code=_project_code(db, sh.project_id),
                       laboratory_org_id=sh.laboratory_org_id, laboratory_org_name=ls.org_name(db, sh.laboratory_org_id), status=sh.status,
                       carrier=sh.carrier, tracking_number=sh.tracking_number, notes=sh.notes, created_at=sh.created_at,
                       dispatched_at=sh.dispatched_at, received_at=sh.received_at, cancel_reason=sh.cancel_reason,
                       items=[ShipmentItemOut(sample_id=i.sample_id, sample_code=_sample(db, i.sample_id).sample_code, status=i.status,
                                              receipt_condition=i.receipt_condition, receipt_reason=i.receipt_reason,
                                              received_at=i.received_at) for i in items],
                       documents=_shipment_docs(db, sh.id))


def qa_review_out(db: Session, rv: LabResultQaReview) -> QaReviewOut:
    import json
    n = ls.names(db, {rv.reviewer_id})
    return QaReviewOut(id=rv.id, decision=rv.decision, notes=rv.notes, reviewer_name=n.get(rv.reviewer_id), reviewed_at=rv.reviewed_at,
                       configuration_acknowledged=rv.configuration_acknowledged,
                       checks=[LabQaCheck(**c) for c in json.loads(rv.checks or "[]")])


def lineage(db: Session, r: LabResult) -> LineageOut:
    t = db.get(LabTest, r.test_id)
    s = db.get(LabSample, r.sample_id)
    root = db.get(LabSample, r.root_sample_id)
    assert t is not None and s is not None and root is not None
    fc = db.get(FieldCollectionRecord, s.field_collection_id)
    sp = db.get(SamplingPoint, s.sampling_point_id)
    st = db.get(ProjectStratum, sp.stratum_id) if sp else None
    farm = db.get(Farm, s.farm_id)
    fb = db.get(FarmBoundary, sp.farm_boundary_id) if sp else None
    p = db.get(Project, r.project_id)
    v = db.get(MethodologyVersion, r.methodology_version_id)
    m = db.get(Methodology, v.methodology_id) if v else None
    pm = db.get(MrvPlanMeasurement, r.mrv_plan_measurement_id)
    plan = db.get(MrvPlan, pm.mrv_plan_id) if pm else None
    assert fc is not None and sp is not None and farm is not None and p is not None and v is not None and m is not None and pm is not None
    versions = ls.results_of_test(db, t.id)
    chain = lab._test_chain(db, t)
    shipments = []
    for sh_id in {e.shipment_id for e in ls.custody_events(db, s.id) if e.shipment_id}:
        sh = db.get(LabShipment, sh_id)
        if sh:
            it = next((i for i in ls.shipment_items(db, sh.id) if i.sample_id == s.id), None)
            shipments.append({"shipment_code": sh.shipment_code, "status": sh.status, "dispatched_at": sh.dispatched_at,
                              "received_at": it.received_at if it else None, "receipt_status": it.status if it else None,
                              "receipt_condition": it.receipt_condition if it else None})
    reviews = db.scalars(select(LabResultQaReview).where(LabResultQaReview.result_id.in_([x.id for x in versions]))
                         .order_by(LabResultQaReview.reviewed_at)).all()
    return LineageOut(
        result=result_out(db, r), versions=[result_out(db, x) for x in versions if x.status != "DRAFT"],
        test={"id": t.id, "test_code": t.test_code, "status": t.status, "retest_chain": [x.test_code for x in chain],
              "engagement_id": t.engagement_id, "laboratory": ls.org_name(db, t.laboratory_org_id), "method_reported": t.method_reported},
        sample={"id": s.id, "sample_code": s.sample_code, "parent_sample_id": s.parent_sample_id, "depth_top_cm": s.depth_top_cm,
                "depth_bottom_cm": s.depth_bottom_cm, "seal_number": s.seal_number, "accession_number": s.accession_number, "status": s.status},
        root_sample={"id": root.id, "sample_code": root.sample_code},
        field_collection={"id": fc.id, "collection_code": fc.collection_code, "version": fc.version, "status": fc.status,
                          "collected_at": fc.collected_at, "supersedes_id": fc.supersedes_id},
        sampling_point={"id": sp.id, "point_code": sp.point_code, "latitude": sp.latitude, "longitude": sp.longitude,
                        "design_version_id": sp.design_version_id},
        stratum={"id": st.id, "code": st.code, "version": st.version} if st else None,
        farm={"id": farm.id, "farm_code": farm.farm_code, "name": farm.name, "boundary_version": fb.version if fb else None},
        project={"id": p.id, "project_code": p.project_code, "name": p.name, "status": p.status},
        methodology={"methodology_code": m.code, "version_id": v.id, "version_label": v.version_label, "locked": p.methodology_version_id == v.id},
        methodology_rule=rule_ref(db, r.methodology_monitoring_rule_id),
        plan_measurement={"id": pm.id, "code": pm.code, "value_type": pm.value_type, "unit": pm.unit,
                          "plan_version": plan.plan_version if plan else None},
        custody=custody_out(db, ls.custody_events(db, s.id)), shipments=shipments, qa_reviews=[qa_review_out(db, x) for x in reviews])


# ---------------------------------------------------------------- laboratory-facing (allow-lists)
def custody_lab_view(db: Session, events: list[SampleCustodyEvent]) -> list[CustodyEventLabView]:
    n = ls.names(db, {e.actor_user_id for e in events if e.actor_side == "LABORATORY"})
    out = []
    for e in events:
        lab_event = e.actor_side == "LABORATORY"
        out.append(CustodyEventLabView(sequence_no=e.sequence_no, event_type=e.event_type, from_state=e.from_state, to_state=e.to_state,
                                       occurred_at=e.occurred_at, actor_org_name=ls.org_name(db, e.actor_org_id), actor_role=e.actor_role,
                                       actor_side=e.actor_side, actor_name=n.get(e.actor_user_id) if lab_event else None,
                                       location_text=e.location_text if lab_event else None, reason=e.reason if lab_event else None,
                                       seal_number=e.seal_number, exception_type=e.exception_type))
    return out


def result_lab_view(db: Session, principal: Principal, r: LabResult) -> ResultLabView:
    n = ls.names(db, {r.analyst_id})
    own = r.created_by == principal.user_id
    return ResultLabView(id=r.id, version=r.version, status=r.status, result_type=r.result_type, value_number=r.value_number,
                         value_text=r.value_text, unit=r.unit, analysed_at=r.analysed_at, analyst_name=n.get(r.analyst_id),
                         method_reported=r.method_reported, report=_doc(db, r.report_document_id), source=r.source,
                         supersedes_result_id=r.supersedes_result_id, status_reason=r.status_reason, submitted_at=r.submitted_at,
                         approved_at=r.approved_at, can_edit=own and r.status == "DRAFT",
                         can_submit=own and r.status == "DRAFT" and r.report_document_id is not None)


def test_lab_view(db: Session, principal: Principal, t: LabTest) -> TestLabView:
    s = db.get(LabSample, t.sample_id)
    m = db.get(MrvPlanMeasurement, t.mrv_plan_measurement_id)
    rule = rule_ref(db, t.methodology_monitoring_rule_id)
    orig = db.get(LabTest, t.retest_of_test_id) if t.retest_of_test_id else None
    results = ls.results_of_test(db, t.id)
    can_test = principal.can_in_org(P.LAB_TEST, t.laboratory_org_id)
    return TestLabView(id=t.id, test_code=t.test_code, status=t.status, sample_id=t.sample_id, sample_code=s.sample_code if s else "",
                       project_code=_project_code(db, t.project_id), rule=rule, required_unit=(rule.unit or "").strip() or None,
                       value_type=m.value_type if m else "",
                       unit_configuration="CONFIGURED" if (rule.unit or "").strip() else "CONFIGURATION_REQUIRED",
                       method_reported=t.method_reported, retest_of_test_code=orig.test_code if orig else None, retest_reason=t.retest_reason,
                       results=[result_lab_view(db, principal, r) for r in results],
                       can_start=can_test and t.status == "REQUESTED",
                       can_enter_result=can_test and t.status == "IN_PROGRESS" and not any(r.status in lab.OPEN_RESULT for r in results))


def sample_lab_view(db: Session, principal: Principal, s: LabSample, with_detail: bool = True) -> SampleLabView:
    p = db.get(Project, s.project_id)
    parent = db.get(LabSample, s.parent_sample_id) if s.parent_sample_id else None
    assert p is not None
    return SampleLabView(id=s.id, sample_code=s.sample_code, parent_sample_code=parent.sample_code if parent else None, status=s.status,
                         description=s.description, depth_top_cm=s.depth_top_cm, depth_bottom_cm=s.depth_bottom_cm, quantity=s.quantity,
                         quantity_unit=s.quantity_unit, container_label=s.container_label, seal_number=s.seal_number,
                         accession_number=s.accession_number, project_code=p.project_code, project_org_name=ls.org_name(db, p.organization_id),
                         laboratory_org_name=ls.org_name(db, s.laboratory_org_id), methodology_label=_methodology_label(db, s.methodology_version_id),
                         tests=[test_lab_view(db, principal, t) for t in ls.tests_of_sample(db, s.id)] if with_detail else [],
                         custody=custody_lab_view(db, ls.custody_events(db, s.id)) if with_detail else [])


def shipment_lab_view(db: Session, principal: Principal, sh: LabShipment) -> ShipmentLabView:
    p = db.get(Project, sh.project_id)
    assert p is not None
    items = [i for i in ls.shipment_items(db, sh.id) if i.status != "REMOVED"]
    return ShipmentLabView(id=sh.id, shipment_code=sh.shipment_code, project_code=p.project_code, project_org_name=ls.org_name(db, p.organization_id),
                           laboratory_org_name=ls.org_name(db, sh.laboratory_org_id), status=sh.status, carrier=sh.carrier,
                           tracking_number=sh.tracking_number, dispatched_at=sh.dispatched_at, received_at=sh.received_at,
                           items=[ShipmentItemLabView(sample_id=i.sample_id, sample_code=_sample(db, i.sample_id).sample_code, status=i.status,
                                                      seal_number=_sample(db, i.sample_id).seal_number,
                                                      receipt_condition=i.receipt_condition, receipt_reason=i.receipt_reason,
                                                      received_at=i.received_at) for i in items],
                           documents=_shipment_docs(db, sh.id),
                           can_receive=sh.status == "DISPATCHED" and principal.can_in_org(P.LAB_RECEIVE, sh.laboratory_org_id))


def analysis_rule_ids(db: Session, plan_id: uuid.UUID) -> list[uuid.UUID]:
    """Methodology LABORATORY rules of a plan (for the Phase 5 ANALYSED display)."""
    rows = db.scalars(select(MrvPlanMeasurement).where(MrvPlanMeasurement.mrv_plan_id == plan_id, MrvPlanMeasurement.source == "METHODOLOGY")).all()
    out = []
    for m in rows:
        rule = db.get(MethodologyMonitoringRule, m.monitoring_rule_id) if m.monitoring_rule_id else None
        if rule is not None and rule.measurement_source == "LABORATORY":
            out.append(rule.id)
    return out

