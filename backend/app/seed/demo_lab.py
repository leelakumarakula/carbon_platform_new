"""DEMO laboratory flow on the DEMO Niphad project (Phase 6), through the real services — no mock result generator.

mrv@demo proposes an engagement with the DEMO laboratory (scope: the locked DEMO methodology's LABORATORY rule), labmanager@demo
accepts it, collector@demo registers and seals a sample from their own accepted field collection (tests are created
automatically), supervisor@demo ships it, labtech@demo receives it, registers it, analyses it and submits a result with a DEMO
placeholder PDF report, and labqa@demo — independent of every earlier step — performs laboratory QA and approves it.

The value and the report are DEMO placeholders, labelled as such; they are not real laboratory measurements. Nothing is
calculated and no credit exists.
"""
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FieldCollectionRecord, LabTest, MethodologyMonitoringRule, Project, ProjectLaboratoryEngagement
from app.models.base import utcnow
from app.models.identity import Organization
from app.schemas.lab import EngagementIn, QaDecisionIn, ReceiptIn, ReceiptItemIn, ResultIn, SampleIn, SealIn, ShipmentIn
from app.seed.demo_farms import _actor
from app.services import lab_service, laboratory_service, mrv_access

DEMO_REPORT = (b"%PDF-1.4\n% DEMO placeholder laboratory report - not a real analysis\n1 0 obj << /Type /Catalog >> endobj\n"
               b"trailer << /Root 1 0 R >>\n%%EOF\n")


def seed_demo_lab(db: Session) -> dict[str, int]:
    p = db.scalars(select(Project).where(Project.environment == "DEMO", Project.methodology_status == "CONFIRMED",
                                         Project.name.like("Niphad%"))).first()
    lab_org = db.scalars(select(Organization).where(Organization.code == "DEMO-LAB-B")).first()
    if p is None or lab_org is None:
        return {"engagements": 0, "samples": 0, "approved_results": 0}
    if db.scalars(select(ProjectLaboratoryEngagement).where(ProjectLaboratoryEngagement.project_id == p.id)).first():
        return {"engagements": 0, "samples": 0, "approved_results": 0}
    fc = db.scalars(select(FieldCollectionRecord).where(FieldCollectionRecord.project_id == p.id, FieldCollectionRecord.status == "ACCEPTED")
                    .order_by(FieldCollectionRecord.collection_code)).first()
    if fc is None:          # the DEMO MRV seed has not run
        return {"engagements": 0, "samples": 0, "approved_results": 0}
    mrv, mrv_ctx = _actor(db, "mrv")
    labmanager, lm_ctx = _actor(db, "labmanager")
    collector, col_ctx = _actor(db, "collector")
    supervisor, sup_ctx = _actor(db, "supervisor")
    labtech, lt_ctx = _actor(db, "labtech")
    labqa, qa_ctx = _actor(db, "labqa")

    _, v = mrv_access.locked_methodology(db, p)
    rules = db.scalars(select(MethodologyMonitoringRule).where(MethodologyMonitoringRule.methodology_version_id == v.id,
                                                               MethodologyMonitoringRule.measurement_source == "LABORATORY")).all()
    e = lab_service.propose_engagement(db, mrv_ctx, mrv, EngagementIn(project_id=p.id, laboratory_org_id=lab_org.id, rule_ids=[r.id for r in rules],
                                                                      notes="DEMO engagement with the DEMO soil laboratory"))
    lab_service.accept_engagement(db, lm_ctx, labmanager, e.id)

    s = lab_service.register_sample(db, col_ctx, collector, SampleIn(
        field_collection_id=fc.id, laboratory_org_id=lab_org.id, description="DEMO composite soil sample, air-dried bag",
        quantity=Decimal("0.5"), quantity_unit="kg", container_label="DEMO bag 1"))
    lab_service.seal_sample(db, col_ctx, collector, s.id, SealIn(seal_number="DEMO-SEAL-0001", location_text="DEMO field edge"))
    sh = lab_service.create_shipment(db, sup_ctx, supervisor, ShipmentIn(project_id=p.id, laboratory_org_id=lab_org.id, carrier="DEMO courier",
                                                                         tracking_number="DEMO-TRACK-001"))
    lab_service.add_items(db, sup_ctx, supervisor, sh.id, [s.id])
    lab_service.dispatch_shipment(db, sup_ctx, supervisor, sh.id, None)

    laboratory_service.receive(db, lt_ctx, labtech, sh.id, ReceiptIn(items=[ReceiptItemIn(
        sample_id=s.id, accepted=True, condition="DEMO: intact, seal unbroken", seal_number_observed="DEMO-SEAL-0001")]))
    laboratory_service.accession(db, lt_ctx, labtech, s.id, "DEMO-ACC-0001")
    approved = 0
    for t in db.scalars(select(LabTest).where(LabTest.sample_id == s.id)).all():
        rule = db.get(MethodologyMonitoringRule, t.methodology_monitoring_rule_id)
        assert rule is not None
        laboratory_service.start_test(db, lt_ctx, labtech, t.id, "DEMO placeholder method (not a real analysis)")
        r = laboratory_service.create_result(db, lt_ctx, labtech, t.id, ResultIn(
            result_type="NUMERIC", value_number=Decimal("1.230000"), unit=rule.unit, analysed_at=utcnow() + timedelta(seconds=1),
            method_reported="DEMO placeholder method (not a real analysis)"))
        laboratory_service.attach_report(db, lt_ctx, labtech, r.id, "demo-lab-report.pdf", DEMO_REPORT, "DEMO laboratory report (placeholder)")
        laboratory_service.submit_result(db, lt_ctx, labtech, r.id)
        laboratory_service.start_qa(db, qa_ctx, labqa, r.id)
        laboratory_service.decide(db, qa_ctx, labqa, r.id, QaDecisionIn(
            decision="APPROVED", notes="DEMO: laboratory QA by an independent lab manager (DEMO value, not a real measurement)"))
        approved += 1
    return {"engagements": 1, "samples": 1, "approved_results": approved}
