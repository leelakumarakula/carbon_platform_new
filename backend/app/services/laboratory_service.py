"""Phase 6 — laboratory-side workflow: inbox and receipt, accession, tests, versioned results, PDF reports, laboratory QA
and retests. Every action is evaluated in the laboratory organization and needs an engagement for the project.

Decisions applied here: automatic tests only (no out-of-methodology tests), units compared as exact text (no conversion),
verbatim text results never approvable for numeric parameters, one APPROVED result per root sample + rule (replaced only
through its own correction or retest chain), and laboratory QA separation of duties (decision 15).
"""
import hashlib
import json
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit.service import record_transition
from app.core.context import RequestContext
from app.core.errors import Conflict, NotFound, PermissionDenied, ValidationFailed
from app.integrations.storage import get_storage
from app.models import (
    Document,
    DocumentVersion,
    FieldCollectionRecord,
    LabResult,
    LabResultQaReview,
    LabSample,
    LabShipment,
    LabShipmentItem,
    LabTest,
    MethodologyMonitoringRule,
    MrvPlanMeasurement,
    Organization,
    Project,
    ProjectLaboratoryEngagement,
    SampleCustodyEvent,
)
from app.models.base import utcnow
from app.schemas.lab import CustodyEventIn, LabQaCheck, QaDecisionIn, ReceiptIn, ResultIn, ResultUpdate, RetestIn
from app.security.permissions import P
from app.security.principal import Principal
from app.services import document_service, mrv_service
from app.services import lab_service as ls
from app.services.workflows import LAB_RESULT_MACHINE, LAB_SHIPMENT_MACHINE, LAB_TEST_MACHINE

OPEN_RESULT = ("DRAFT", "SUBMITTED", "QA_REVIEW")


# ---------------------------------------------------------------- scoping
def lab_orgs(principal: Principal, code: str) -> set[uuid.UUID] | None:
    """Laboratory organizations where the caller holds `code` (None = platform-wide)."""
    if principal.has_platform(code):
        return None
    return {g.organization_id for g in principal.grants if code in g.permissions and g.organization_id}


def _in_lab(principal: Principal, lab_org_id: uuid.UUID, code: str) -> bool:
    return principal.can_in_org(code, lab_org_id)


def visible_sample_ids(db: Session, principal: Principal) -> set[uuid.UUID] | None:
    """Samples a laboratory user may see: those in a non-draft shipment addressed to their laboratory."""
    orgs = lab_orgs(principal, P.LAB_LAB_READ)
    stmt = select(LabShipmentItem.sample_id).join(LabShipment, LabShipment.id == LabShipmentItem.shipment_id).where(
        LabShipment.status.in_(["DISPATCHED", "RECEIVED"]), LabShipmentItem.status != "REMOVED")
    if orgs is not None:
        if not orgs:
            return set()
        stmt = stmt.where(LabShipment.laboratory_org_id.in_(orgs))
    roots = set(db.scalars(stmt).all())
    # splits made from a visible sample stay visible to the same laboratory
    if roots:
        roots |= set(db.scalars(select(LabSample.id).where(LabSample.root_sample_id.in_(
            select(LabSample.root_sample_id).where(LabSample.id.in_(roots))))).all())
    return roots


def lab_sample(db: Session, principal: Principal, sample_id: uuid.UUID, code: str = P.LAB_LAB_READ) -> LabSample:
    s = db.get(LabSample, sample_id)
    if s is None or not _in_lab(principal, s.laboratory_org_id, P.LAB_LAB_READ):
        raise ls.not_found("Sample")
    vis = visible_sample_ids(db, principal)
    if vis is not None and s.id not in vis:
        raise ls.not_found("Sample")
    if not _in_lab(principal, s.laboratory_org_id, code):
        raise PermissionDenied(details={"required_permission": code})
    return s


def lab_test(db: Session, principal: Principal, test_id: uuid.UUID, code: str = P.LAB_LAB_READ) -> LabTest:
    t = db.get(LabTest, test_id)
    if t is None:
        raise ls.not_found("Test")
    lab_sample(db, principal, t.sample_id)
    if not _in_lab(principal, t.laboratory_org_id, code):
        raise PermissionDenied(details={"required_permission": code})
    return t


def lab_result(db: Session, principal: Principal, result_id: uuid.UUID, code: str = P.LAB_LAB_READ) -> LabResult:
    r = db.get(LabResult, result_id)
    if r is None:
        raise ls.not_found("Result")
    lab_test(db, principal, r.test_id)
    if not _in_lab(principal, r.laboratory_org_id, code):
        raise PermissionDenied(details={"required_permission": code})
    return r


def lab_shipment(db: Session, principal: Principal, shipment_id: uuid.UUID, code: str = P.LAB_LAB_READ) -> LabShipment:
    sh = db.get(LabShipment, shipment_id)
    if sh is None or sh.status not in ("DISPATCHED", "RECEIVED") or not _in_lab(principal, sh.laboratory_org_id, P.LAB_LAB_READ):
        raise ls.not_found("Shipment")
    if not _in_lab(principal, sh.laboratory_org_id, code):
        raise PermissionDenied(details={"required_permission": code})
    return sh


def engagements(db: Session, principal: Principal) -> list[ProjectLaboratoryEngagement]:
    orgs = lab_orgs(principal, P.LAB_LAB_READ) if principal.has(P.LAB_LAB_READ) else lab_orgs(principal, P.LAB_ENGAGEMENT_ACCEPT)
    stmt = select(ProjectLaboratoryEngagement)
    if orgs is not None:
        stmt = stmt.where(ProjectLaboratoryEngagement.laboratory_org_id.in_(orgs or {uuid.uuid4()}))
    return list(db.scalars(stmt.order_by(ProjectLaboratoryEngagement.proposed_at.desc())).all())


def inbox(db: Session, principal: Principal) -> list[LabShipment]:
    orgs = lab_orgs(principal, P.LAB_LAB_READ)
    stmt = select(LabShipment).where(LabShipment.status.in_(["DISPATCHED", "RECEIVED"]))
    if orgs is not None:
        stmt = stmt.where(LabShipment.laboratory_org_id.in_(orgs or {uuid.uuid4()}))
    return list(db.scalars(stmt.order_by(LabShipment.dispatched_at.desc())).all())


def worklist(db: Session, principal: Principal, status: str | None = None) -> list[LabTest]:
    vis = visible_sample_ids(db, principal)
    stmt = select(LabTest)
    if vis is not None:
        stmt = stmt.where(LabTest.sample_id.in_(vis or {uuid.uuid4()}))
    if status:
        stmt = stmt.where(LabTest.status == status)
    return list(db.scalars(stmt.order_by(LabTest.created_at.desc())).all())


def lab_samples(db: Session, principal: Principal) -> list[LabSample]:
    vis = visible_sample_ids(db, principal)
    stmt = select(LabSample)
    if vis is not None:
        stmt = stmt.where(LabSample.id.in_(vis or {uuid.uuid4()}))
    return list(db.scalars(stmt.order_by(LabSample.registered_at.desc())).all())


# ---------------------------------------------------------------- receipt & accession
def receive(db: Session, ctx: RequestContext, principal: Principal, shipment_id: uuid.UUID, data: ReceiptIn) -> LabShipment:
    """Item-level receipt. Allowed for any shipment dispatched while the engagement was ACTIVE (wind-down rule)."""
    sh = lab_shipment(db, principal, shipment_id, P.LAB_RECEIVE)
    if sh.status != "DISPATCHED":
        raise Conflict("This shipment has already been received.", error_code="SHIPMENT_NOT_DISPATCHED")
    items = {i.sample_id: i for i in ls.shipment_items(db, sh.id) if i.status == "IN_SHIPMENT"}
    for it_in in data.items:
        it = items.get(it_in.sample_id)
        if it is None:
            raise ValidationFailed("Sample is not waiting in this shipment.", error_code="NOT_IN_SHIPMENT",
                                   details={"sample_id": str(it_in.sample_id)})
        s = db.get(LabSample, it.sample_id)
        assert s is not None
        it.received_by, it.received_at = principal.user_id, utcnow()
        it.receipt_condition, it.receipt_seal_number = it_in.condition, it_in.seal_number_observed
        if it_in.accepted:
            it.status = "RECEIVED"
            ls.custody(db, ctx, principal, s, "RECEIVED", "LAB_RECEIVED", side="LABORATORY", org_id=sh.laboratory_org_id, perm=P.LAB_RECEIVE,
                       occurred_at=data.occurred_at, seal_number=it_in.seal_number_observed, shipment_id=sh.id, location_text=data.location_text)
        else:
            it.status, it.receipt_reason = "REJECTED", it_in.reason
            ls.custody(db, ctx, principal, s, "REJECTED", "REJECTED_AT_RECEIPT", side="LABORATORY", org_id=sh.laboratory_org_id,
                       perm=P.LAB_RECEIVE, occurred_at=data.occurred_at, reason=it_in.reason, seal_number=it_in.seal_number_observed,
                       shipment_id=sh.id, location_text=data.location_text)
            ls.cancel_tests(db, ctx, s, it_in.reason or "Rejected at receipt", sh.laboratory_org_id)
    db.flush()
    if not any(i.status == "IN_SHIPMENT" for i in ls.shipment_items(db, sh.id)):
        record_transition(db, ctx, LAB_SHIPMENT_MACHINE, sh.id, "DISPATCHED", "RECEIVED", "LAB_SHIPMENT_RECEIVED", None, sh.laboratory_org_id)
        sh.status, sh.received_at = "RECEIVED", utcnow()
    ls.audit(db, ctx, "LAB_SHIPMENT_RECEIPT_RECORDED", sh.id, {"shipment_code": sh.shipment_code, "items": [
        {"sample_id": str(i.sample_id), "accepted": i.accepted} for i in data.items]}, sh.laboratory_org_id, entity_type="lab_shipment")
    db.commit()
    return sh


def accession(db: Session, ctx: RequestContext, principal: Principal, sample_id: uuid.UUID, number: str) -> LabSample:
    s = lab_sample(db, principal, sample_id, P.LAB_RECEIVE)
    if s.status != "LAB_RECEIVED":
        raise Conflict(f"Only a received sample can be registered at the laboratory (it is {s.status}).", error_code="SAMPLE_NOT_RECEIVED")
    s.accession_number = number
    ls.custody(db, ctx, principal, s, "LAB_REGISTERED", "LAB_REGISTERED", side="LABORATORY", org_id=s.laboratory_org_id, perm=P.LAB_RECEIVE)
    db.commit()
    return s


def lab_custody(db: Session, ctx: RequestContext, principal: Principal, sample_id: uuid.UUID, data: CustodyEventIn) -> SampleCustodyEvent:
    s = lab_sample(db, principal, sample_id, P.LAB_RECEIVE)
    return ls.custody_action(db, ctx, principal, s, data, side="LABORATORY", org_id=s.laboratory_org_id, perm=P.LAB_RECEIVE)


# ---------------------------------------------------------------- tests
def start_test(db: Session, ctx: RequestContext, principal: Principal, test_id: uuid.UUID, method: str | None) -> LabTest:
    t = lab_test(db, principal, test_id, P.LAB_TEST)
    if t.status != "REQUESTED":
        raise Conflict(f"Only a REQUESTED test can be started (it is {t.status}).", error_code="TEST_NOT_REQUESTED")
    ls.require_active_for_rule(db, t.project_id, t.laboratory_org_id, t.methodology_monitoring_rule_id)   # wind-down: no new tests
    s = db.get(LabSample, t.sample_id)
    assert s is not None
    if s.status not in ("LAB_REGISTERED", "IN_ANALYSIS", "ANALYSED"):
        raise Conflict(f"The sample must be registered at the laboratory first (it is {s.status}).", error_code="SAMPLE_NOT_LAB_REGISTERED")
    record_transition(db, ctx, LAB_TEST_MACHINE, t.id, t.status, "IN_PROGRESS", "LAB_TEST_STARTED", None, t.laboratory_org_id)
    t.status, t.started_by, t.started_at, t.method_reported = "IN_PROGRESS", principal.user_id, utcnow(), method
    if s.status != "IN_ANALYSIS":
        ls.custody(db, ctx, principal, s, "ANALYSIS_STARTED", "IN_ANALYSIS", side="LABORATORY", org_id=t.laboratory_org_id, perm=P.LAB_TEST)
    ls.audit(db, ctx, "LAB_TEST_STARTED", t.id, {"test_code": t.test_code, "sample_code": s.sample_code}, t.laboratory_org_id, entity_type="lab_test")
    db.commit()
    return t


def _measurement(db: Session, t: LabTest) -> MrvPlanMeasurement:
    m = db.get(MrvPlanMeasurement, t.mrv_plan_measurement_id)
    assert m is not None
    return m


def create_result(db: Session, ctx: RequestContext, principal: Principal, test_id: uuid.UUID, data: ResultIn,
                  supersedes: LabResult | None = None) -> LabResult:
    t = lab_test(db, principal, test_id, P.LAB_TEST)
    if t.status != "IN_PROGRESS":
        raise Conflict(f"Results are entered for a test IN_PROGRESS (it is {t.status}).", error_code="TEST_NOT_IN_PROGRESS")
    versions = ls.results_of_test(db, t.id)
    if any(r.status in OPEN_RESULT for r in versions):
        raise Conflict("This test already has a result in progress.", error_code="RESULT_IN_PROGRESS")
    s = db.get(LabSample, t.sample_id)
    assert s is not None
    r = LabResult(test_id=t.id, version=(max((x.version for x in versions), default=0) + 1),
                  supersedes_result_id=supersedes.id if supersedes else None, sample_id=s.id, root_sample_id=s.root_sample_id,
                  project_id=t.project_id, laboratory_org_id=t.laboratory_org_id, methodology_version_id=t.methodology_version_id,
                  methodology_monitoring_rule_id=t.methodology_monitoring_rule_id, mrv_plan_measurement_id=t.mrv_plan_measurement_id,
                  result_type=data.result_type, value_number=data.value_number, value_text=data.value_text, unit=data.unit,
                  analysed_at=data.analysed_at.replace(tzinfo=None), analyst_id=principal.user_id,
                  method_reported=data.method_reported or t.method_reported, source="MANUAL", status="DRAFT",
                  created_by=principal.user_id, environment=t.environment)
    db.add(r)
    db.flush()
    record_transition(db, ctx, LAB_RESULT_MACHINE, r.id, None, "DRAFT", "LAB_RESULT_CREATED", None, t.laboratory_org_id)
    ls.audit(db, ctx, "LAB_RESULT_CREATED", r.id, {"test_code": t.test_code, "version": r.version, "supersedes": r.supersedes_result_id},
             t.laboratory_org_id, entity_type="lab_result")
    db.commit()
    return r


def update_result(db: Session, ctx: RequestContext, principal: Principal, result_id: uuid.UUID, data: ResultUpdate) -> LabResult:
    r = lab_result(db, principal, result_id, P.LAB_TEST)
    if r.status != "DRAFT" or r.created_by != principal.user_id:
        raise Conflict("Only your own DRAFT result can be edited.", error_code="RESULT_NOT_EDITABLE")
    changes = data.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(r, k, v.replace(tzinfo=None) if k == "analysed_at" and v else v)
    if (r.result_type == "NUMERIC") != (r.value_number is not None and r.value_text is None) or \
            (r.result_type == "TEXT") != (r.value_text is not None and r.value_number is None):
        raise ValidationFailed("A result holds exactly one value: a number (NUMERIC) or verbatim text (TEXT).", error_code="ONE_VALUE_REQUIRED")
    ls.audit(db, ctx, "LAB_RESULT_UPDATED", r.id, {k: str(v) for k, v in changes.items()}, r.laboratory_org_id, entity_type="lab_result")
    db.commit()
    return r


def attach_report(db: Session, ctx: RequestContext, principal: Principal, result_id: uuid.UUID, filename: str | None, data: bytes,
                  title: str | None) -> LabResult:
    r = lab_result(db, principal, result_id, P.LAB_TEST)
    if r.status not in ("DRAFT", "SUBMITTED"):
        raise Conflict("A report is attached before QA starts.", error_code="RESULT_NOT_EDITABLE")
    doc = document_service.create_document(db, ctx, entity_type="lab_result", entity_id=r.id, organization_id=r.laboratory_org_id,
                                           environment=r.environment, category="LAB_REPORT", title=title or "Laboratory report",
                                           filename=filename, data=data)
    r.report_document_id = doc.id
    ls.audit(db, ctx, "LAB_REPORT_ATTACHED", r.id, {"document_id": doc.id}, r.laboratory_org_id, entity_type="lab_result")
    db.commit()
    return r


def submit_result(db: Session, ctx: RequestContext, principal: Principal, result_id: uuid.UUID) -> LabResult:
    r = lab_result(db, principal, result_id, P.LAB_TEST)
    if r.created_by != principal.user_id:
        raise PermissionDenied("The analyst who entered the result submits it.", error_code="NOT_ANALYST")
    t = db.get(LabTest, r.test_id)
    assert t is not None
    record_transition(db, ctx, LAB_RESULT_MACHINE, r.id, r.status, "SUBMITTED", "LAB_RESULT_SUBMITTED", None, r.laboratory_org_id)
    r.status, r.submitted_by, r.submitted_at = "SUBMITTED", principal.user_id, utcnow()
    record_transition(db, ctx, LAB_TEST_MACHINE, t.id, t.status, "RESULT_SUBMITTED", "LAB_TEST_RESULT_SUBMITTED", None, t.laboratory_org_id)
    t.status = "RESULT_SUBMITTED"
    ls.audit(db, ctx, "LAB_RESULT_SUBMITTED", r.id, {"test_code": t.test_code, "version": r.version}, r.laboratory_org_id,
             entity_type="lab_result")
    db.commit()
    return r


def withdraw_result(db: Session, ctx: RequestContext, principal: Principal, result_id: uuid.UUID, reason: str) -> LabResult:
    r = lab_result(db, principal, result_id, P.LAB_TEST)
    if r.created_by != principal.user_id:
        raise PermissionDenied("Only the analyst who entered the result can withdraw it.", error_code="NOT_ANALYST")
    t = db.get(LabTest, r.test_id)
    assert t is not None
    record_transition(db, ctx, LAB_RESULT_MACHINE, r.id, r.status, "WITHDRAWN", "LAB_RESULT_WITHDRAWN", reason, r.laboratory_org_id)
    if t.status == "RESULT_SUBMITTED":
        record_transition(db, ctx, LAB_TEST_MACHINE, t.id, t.status, "IN_PROGRESS", "LAB_TEST_REOPENED", reason, t.laboratory_org_id)
        t.status = "IN_PROGRESS"
    r.status, r.status_reason = "WITHDRAWN", reason
    db.commit()
    return r


def correct_result(db: Session, ctx: RequestContext, principal: Principal, result_id: uuid.UUID, reason: str, data: ResultIn) -> LabResult:
    """An APPROVED result is never edited: a correction is a new version of the same test (allowed during wind-down)."""
    r = lab_result(db, principal, result_id, P.LAB_TEST)
    if r.status != "APPROVED":
        raise Conflict("Only an APPROVED result is corrected by a new version; edit or resubmit the others.", error_code="RESULT_NOT_APPROVED")
    t = db.get(LabTest, r.test_id)
    assert t is not None
    if t.status == "CLOSED":
        record_transition(db, ctx, LAB_TEST_MACHINE, t.id, "CLOSED", "IN_PROGRESS", "LAB_TEST_REOPENED", reason, t.laboratory_org_id)
        t.status = "IN_PROGRESS"
        db.flush()
    new = create_result(db, ctx, principal, t.id, data, supersedes=r)
    ls.audit(db, ctx, "LAB_RESULT_CORRECTION_STARTED", new.id, {"supersedes": r.id, "test_code": t.test_code}, r.laboratory_org_id, reason,
             entity_type="lab_result")
    db.commit()
    return new


# ---------------------------------------------------------------- QA
def _qa(key: str, label: str, problems: list[str], *, config: list[str] | None = None, warn: list[str] | None = None,
        acknowledgeable: bool = False) -> LabQaCheck:
    if problems:
        return LabQaCheck(key=key, label=label, result="FAIL", details=problems)
    if config:
        return LabQaCheck(key=key, label=label, result="CONFIGURATION_REQUIRED", details=config, acknowledgeable=acknowledgeable)
    if warn:
        return LabQaCheck(key=key, label=label, result="WARN", details=warn)
    return LabQaCheck(key=key, label=label, result="PASS")


def sod_violations(db: Session, r: LabResult, reviewer_id: uuid.UUID, approving: bool) -> list[str]:
    """Decision 15: the approver must differ from everyone who handled the sample or the result."""
    t = db.get(LabTest, r.test_id)
    s = db.get(LabSample, r.sample_id)
    assert t is not None and s is not None
    out = []
    if r.analyst_id == reviewer_id:
        out.append("you are the analyst")
    if r.submitted_by == reviewer_id:
        out.append("you submitted the result")
    if approving:
        if s.registered_by == reviewer_id:
            out.append("you registered the sample")
        if s.sealed_by == reviewer_id:
            out.append("you sealed the sample")
        chain = _test_chain(db, t)
        if any(x.retest_requested_by == reviewer_id for x in chain):
            out.append("you requested the retest")
        for sh_id in set(db.scalars(select(LabShipmentItem.shipment_id).where(LabShipmentItem.sample_id.in_(
                [s.id, s.root_sample_id]))).all()):
            sh = db.get(LabShipment, sh_id)
            if sh and sh.created_by == reviewer_id:
                out.append("you created the shipment")
            if sh and sh.dispatched_by == reviewer_id:
                out.append("you dispatched the shipment")
    return sorted(set(out))


def _test_chain(db: Session, t: LabTest) -> list[LabTest]:
    chain, cur = [t], t
    while cur.retest_of_test_id:
        nxt = db.get(LabTest, cur.retest_of_test_id)
        if nxt is None:
            break
        chain.append(nxt)
        cur = nxt
    return chain


def _report_integrity(db: Session, r: LabResult) -> tuple[list[str], list[str]]:
    if r.report_document_id is None:
        return ["no laboratory report is attached"], []
    doc = db.get(Document, r.report_document_id)
    if doc is None or doc.category != "LAB_REPORT" or doc.status != "ACTIVE":
        return ["the attached document is not an active LAB_REPORT"], []
    v = db.scalars(select(DocumentVersion).where(DocumentVersion.document_id == doc.id, DocumentVersion.version == doc.current_version)).first()
    if v is None or v.mime_type != "application/pdf":
        return ["the laboratory report is not a PDF"], []
    try:
        actual = hashlib.sha256(get_storage().get(v.storage_key)).hexdigest()
    except Exception:
        return [], ["the report file could not be read back from storage"]
    problems = [] if actual == v.checksum_sha256 else ["the report file does not match its recorded SHA-256 checksum"]
    if v.scan_status == "INFECTED":
        problems.append("the report failed the malware scan")
    return [], problems


def qa_checks(db: Session, r: LabResult, reviewer_id: uuid.UUID | None = None) -> list[LabQaCheck]:
    """Deterministic laboratory QA checks (Phase 6 decisions 5, 10–13, 15, 20)."""
    out: list[LabQaCheck] = []
    t = db.get(LabTest, r.test_id)
    s = db.get(LabSample, r.sample_id)
    assert t is not None and s is not None
    p = db.get(Project, r.project_id)
    fc = db.get(FieldCollectionRecord, s.field_collection_id)
    rule = db.get(MethodologyMonitoringRule, r.methodology_monitoring_rule_id)
    m = db.get(MrvPlanMeasurement, r.mrv_plan_measurement_id)
    root = db.get(LabSample, s.root_sample_id)
    lin = []
    if p is None or p.methodology_version_id != r.methodology_version_id:
        lin.append("the project's locked methodology version differs from the result's")
    if fc is None or fc.project_id != s.project_id or fc.sampling_point_id != s.sampling_point_id:
        lin.append("the sample's field collection does not match its sampling point / project")
    if rule is None or rule.methodology_version_id != r.methodology_version_id:
        lin.append("the methodology rule is not part of the locked version")
    if m is None or m.monitoring_rule_id != r.methodology_monitoring_rule_id:
        lin.append("the plan measurement does not correspond to the methodology rule")
    if root is None or root.root_sample_id != root.id or s.root_sample_id != r.root_sample_id:
        lin.append("the root sample is inconsistent")
    out.append(_qa("lineage", "Traceable lineage: sample → field collection → point → project → locked methodology rule", lin))
    # decision 13: the sample's OWN collection version (never re-pointed)
    if fc is not None and fc.status == "ACCEPTED":
        out.append(_qa("field_collection", "The sample's own field-collection version is ACCEPTED", []))
    elif fc is not None and fc.status == "SUPERSEDED":
        successors = db.scalars(select(FieldCollectionRecord.collection_code).where(FieldCollectionRecord.supersedes_id == fc.id)).all()
        out.append(_qa("field_collection", "The sample's own field-collection version is ACCEPTED", [],
                       warn=[f"{fc.collection_code} was corrected after sampling (successor {', '.join(successors) or '—'}); the sample stays "
                             "linked to the version it was taken from"]))
    else:
        out.append(_qa("field_collection", "The sample's own field-collection version is ACCEPTED",
                       [f"field collection is {fc.status if fc else 'missing'}"]))
    events = ls.custody_events(db, s.id)
    cust = []
    for i, ev in enumerate(events):
        if ev.sequence_no != i + 1:
            cust.append("custody sequence has a gap")
        if i and ev.from_state != events[i - 1].to_state:
            cust.append(f"custody event {ev.sequence_no} does not continue from the previous state")
    if s.status in ("EXCEPTION", "REJECTED_AT_RECEIPT", "VOIDED"):
        cust.append(f"sample custody is {s.status}")
    received = [e for e in events if e.event_type == "RECEIVED"]
    if not received:
        cust.append("the sample was never received by the laboratory")
    elif received[-1].seal_number and s.seal_number and received[-1].seal_number != s.seal_number:
        cust.append("seal number observed at receipt differs from the seal applied in the field")
    out.append(_qa("custody", "Unbroken chain of custody, received by the laboratory, no open exception", sorted(set(cust))))
    eng = db.get(ProjectLaboratoryEngagement, t.engagement_id)
    eng_problems = []
    if eng is None or eng.accepted_at is None:
        eng_problems.append("the test's engagement was never accepted")
    elif r.methodology_monitoring_rule_id not in ls.scope_rule_ids(db, eng.id):
        eng_problems.append("the rule is outside the engagement scope")
    out.append(_qa("engagement", "Performed under an accepted engagement covering the rule", eng_problems))
    out.append(_qa("methodology_rule_source", "The methodology rule is declared LABORATORY",
                   [] if rule is not None and rule.measurement_source == "LABORATORY" else ["the rule is not a LABORATORY rule"]))
    # decision 10: exact text, no conversion
    required = (rule.unit or "").strip() if rule else ""
    if not required:
        out.append(_qa("unit", "Reported unit equals the methodology rule unit", [],
                       config=["CONFIGURATION_REQUIRED: the methodology rule declares no unit"],
                       acknowledgeable=p is not None and mrv_service.gap_approval_allowed(p)))
    elif (r.unit or "").strip() != required:
        out.append(_qa("unit", "Reported unit equals the methodology rule unit",
                       [f"UNIT_MISMATCH: reported '{(r.unit or '').strip()}', required '{required}' (no conversion is performed)"]))
    else:
        out.append(_qa("unit", "Reported unit equals the methodology rule unit", []))
    # decision 12: verbatim text never approvable for numeric parameters
    if m is not None and m.value_type == "NUMBER" and r.result_type == "TEXT":
        out.append(_qa("result_type", "Result type matches the plan measurement",
                       ["CONFIGURATION_REQUIRED: detection-limit handling is not configured — a verbatim text result cannot be approved "
                        "for a numeric parameter (it is stored as reported, never converted)"]))
    elif m is not None and m.value_type != "NUMBER" and r.result_type == "NUMERIC":
        out.append(_qa("result_type", "Result type matches the plan measurement", ["a numeric value was reported for a text parameter"]))
    else:
        out.append(_qa("result_type", "Result type matches the plan measurement", []))
    rep_missing, rep_integrity = _report_integrity(db, r)
    out.append(_qa("report", "A PDF laboratory report is attached", rep_missing))
    out.append(_qa("report_checksum", "The report file matches its SHA-256 checksum", rep_integrity if not rep_missing else ["no report"]))
    timing = []
    if r.analysed_at is None:
        timing.append("no analysis date")
    else:
        # analysis times are entered to the second: compare at that precision (same second as receipt is not "before")
        if received and r.analysed_at < received[-1].occurred_at.replace(microsecond=0):
            timing.append("analysed before the laboratory received the sample")
        if r.analysed_at > utcnow().replace(tzinfo=None) + timedelta(minutes=5):
            timing.append("analysis date is in the future")
    out.append(_qa("analysis_timing", "Analysed after laboratory receipt and not in the future", timing))
    sod = sod_violations(db, r, reviewer_id, approving=True) if reviewer_id else []
    out.append(_qa("separation_of_duties", "Reviewer is independent of the analysis and of sample handling", sod))
    env = []
    lab = db.get(Organization, r.laboratory_org_id)
    envs = {r.environment, s.environment, p.environment if p else None, lab.environment if lab else None}
    if len(envs) != 1:
        env.append("DEMO and live records are mixed")
    if r.source not in ("MANUAL", "LIMS_IMPORT") or (r.source == "LIMS_IMPORT" and not r.external_result_id):
        env.append("unsupported result source")
    out.append(_qa("environment_source", "Environment consistent; source MANUAL / LIMS_IMPORT", env))
    return out


def qa_view_data(db: Session, principal: Principal, result_id: uuid.UUID) -> tuple[LabResult, list[LabQaCheck], list[LabResultQaReview]]:
    r = lab_result(db, principal, result_id)
    reviews = list(db.scalars(select(LabResultQaReview).where(LabResultQaReview.result_id == r.id).order_by(LabResultQaReview.reviewed_at)).all())
    return r, qa_checks(db, r, principal.user_id), reviews


def start_qa(db: Session, ctx: RequestContext, principal: Principal, result_id: uuid.UUID) -> LabResult:
    r = lab_result(db, principal, result_id, P.LAB_QA)
    if r.analyst_id == principal.user_id or r.submitted_by == principal.user_id:
        raise PermissionDenied("You cannot review your own analysis.", error_code="SEPARATION_OF_DUTIES")
    record_transition(db, ctx, LAB_RESULT_MACHINE, r.id, r.status, "QA_REVIEW", "LAB_QA_STARTED", None, r.laboratory_org_id)
    r.status = "QA_REVIEW"
    ls.audit(db, ctx, "LAB_QA_STARTED", r.id, {"result_id": r.id}, r.laboratory_org_id, entity_type="lab_result")
    db.commit()
    return r


def _in_replacement_chain(db: Session, new: LabResult, old: LabResult) -> bool:
    cur: LabResult | None = new
    while cur is not None and cur.supersedes_result_id:
        if cur.supersedes_result_id == old.id:
            return True
        cur = db.get(LabResult, cur.supersedes_result_id)
    t = db.get(LabTest, new.test_id)
    return t is not None and old.test_id in {x.id for x in _test_chain(db, t)[1:]}


def decide(db: Session, ctx: RequestContext, principal: Principal, result_id: uuid.UUID, data: QaDecisionIn) -> LabResult:
    r = lab_result(db, principal, result_id, P.LAB_QA)
    if r.status != "QA_REVIEW":
        raise Conflict("Start the QA review first.", error_code="RESULT_NOT_IN_QA")
    approving = data.decision == "APPROVED"
    sod = sod_violations(db, r, principal.user_id, approving)
    if sod:
        raise PermissionDenied("Separation of duties: " + "; ".join(sod) + ".", error_code="SEPARATION_OF_DUTIES", details={"reasons": sod})
    t = db.get(LabTest, r.test_id)
    s = db.get(LabSample, r.sample_id)
    p = db.get(Project, r.project_id)
    assert t is not None and s is not None and p is not None
    checks = qa_checks(db, r, principal.user_id)
    acknowledged = False
    if approving:
        failing = [c.key for c in checks if c.result == "FAIL"]
        if failing:
            raise Conflict("The result cannot be approved while QA checks fail: " + ", ".join(failing) + ".", error_code="QA_CHECKS_FAILED",
                           details={"failing": failing})
        config = [c for c in checks if c.result == "CONFIGURATION_REQUIRED"]
        if config:
            if not all(c.acknowledgeable for c in config):
                raise Conflict("Approval is blocked until the methodology configures: " + "; ".join(d for c in config for d in c.details),
                               error_code="CONFIGURATION_REQUIRED", details={"policy": "PRODUCTION_BLOCK"})
            if not data.acknowledge_configuration:
                raise Conflict("Acknowledge the CONFIGURATION_REQUIRED items explicitly to approve (DEMO / non-production only).",
                               error_code="CONFIGURATION_REQUIRED")
            acknowledged = True
        current = ls.approved_for(db, {r.root_sample_id}, r.methodology_monitoring_rule_id)
        if current is not None and not _in_replacement_chain(db, r, current):
            raise Conflict("An approved result already exists for this sample and parameter; replace it through a correction or a retest.",
                           error_code="AUTHORITATIVE_RESULT_EXISTS", details={"approved_result_id": str(current.id)})
        if current is not None:                         # replacement: supersede atomically
            record_transition(db, ctx, LAB_RESULT_MACHINE, current.id, "APPROVED", "SUPERSEDED", "LAB_RESULT_SUPERSEDED",
                              f"Superseded by result {r.id}", r.laboratory_org_id)
            current.status, current.superseded_by_result_id, current.superseded_at = "SUPERSEDED", r.id, utcnow()
            db.flush()
            ls.audit(db, ctx, "LAB_RESULT_SUPERSEDED", current.id, {"superseded_by": r.id}, r.laboratory_org_id, entity_type="lab_result")
    elif data.decision == "RETEST_REQUIRED":
        if not _in_lab(principal, r.laboratory_org_id, P.LAB_RETEST_REQUEST):
            raise PermissionDenied(details={"required_permission": P.LAB_RETEST_REQUEST})
        ls.require_active_for_rule(db, r.project_id, r.laboratory_org_id, r.methodology_monitoring_rule_id)
    db.add(LabResultQaReview(result_id=r.id, reviewer_id=principal.user_id, decision=data.decision, notes=data.notes,
                             checks=json.dumps([c.model_dump() for c in checks]), configuration_acknowledged=acknowledged))
    record_transition(db, ctx, LAB_RESULT_MACHINE, r.id, "QA_REVIEW", data.decision, f"LAB_RESULT_{data.decision}", data.notes,
                      r.laboratory_org_id)
    r.status, r.status_reason = data.decision, data.notes
    if approving:
        r.approved_by, r.approved_at = principal.user_id, utcnow()
        record_transition(db, ctx, LAB_TEST_MACHINE, t.id, t.status, "CLOSED", "LAB_TEST_CLOSED", None, t.laboratory_org_id)
        t.status = "CLOSED"
        db.flush()
        _maybe_analysed(db, ctx, principal, s)
    elif data.decision == "REJECTED":
        record_transition(db, ctx, LAB_TEST_MACHINE, t.id, t.status, "IN_PROGRESS", "LAB_TEST_REOPENED", data.notes, t.laboratory_org_id)
        t.status = "IN_PROGRESS"
    else:
        record_transition(db, ctx, LAB_TEST_MACHINE, t.id, t.status, "CLOSED", "LAB_TEST_CLOSED", data.notes, t.laboratory_org_id)
        t.status = "CLOSED"
        db.flush()
        _new_retest(db, ctx, principal, t, s, data.notes)
    ls.audit(db, ctx, f"LAB_RESULT_{data.decision}", r.id, {"test_code": t.test_code, "version": r.version, "acknowledged": acknowledged},
             r.laboratory_org_id, data.notes, entity_type="lab_result")
    ls.audit(db, ctx, f"LAB_RESULT_{data.decision}", r.id, {"sample_code": s.sample_code, "test_code": t.test_code, "version": r.version},
             p.organization_id, data.notes, entity_type="lab_result")
    db.commit()
    return r


def _maybe_analysed(db: Session, ctx: RequestContext, principal: Principal, s: LabSample) -> None:
    tests = ls.tests_of_sample(db, s.id)
    if tests and all(t.status in ("CLOSED", "CANCELLED") for t in tests) and s.status == "IN_ANALYSIS":
        ls.custody(db, ctx, principal, s, "ANALYSIS_COMPLETED", "ANALYSED", side="LABORATORY", org_id=s.laboratory_org_id, perm=P.LAB_QA)


def _new_retest(db: Session, ctx: RequestContext, principal: Principal, original: LabTest, sample: LabSample, reason: str) -> LabTest:
    from app.repositories.sequences import next_code
    nt = LabTest(test_code=next_code(db, "lab_test", utcnow().year), sample_id=sample.id, root_sample_id=sample.root_sample_id,
                 project_id=original.project_id, laboratory_org_id=original.laboratory_org_id,
                 engagement_id=ls.require_active_for_rule(db, original.project_id, original.laboratory_org_id,
                                                          original.methodology_monitoring_rule_id).id,
                 methodology_version_id=original.methodology_version_id, methodology_monitoring_rule_id=original.methodology_monitoring_rule_id,
                 mrv_plan_measurement_id=original.mrv_plan_measurement_id, status="REQUESTED", retest_of_test_id=original.id,
                 retest_reason=reason, retest_requested_by=principal.user_id, created_by=principal.user_id, environment=original.environment)
    db.add(nt)
    db.flush()
    record_transition(db, ctx, LAB_TEST_MACHINE, nt.id, None, "REQUESTED", "LAB_RETEST_REQUESTED", reason, original.laboratory_org_id)
    ls.audit(db, ctx, "LAB_RETEST_REQUESTED", nt.id, {"test_code": nt.test_code, "retest_of": original.test_code, "sample_code": sample.sample_code},
             original.laboratory_org_id, reason, entity_type="lab_test")
    return nt


def request_retest(db: Session, ctx: RequestContext, principal: Principal, result_id: uuid.UUID, data: RetestIn) -> LabTest:
    """Explicit retest of an APPROVED (or rejected) result; the original result is kept until a retest result is approved."""
    r = lab_result(db, principal, result_id, P.LAB_RETEST_REQUEST)
    if r.status not in ("APPROVED", "REJECTED"):
        raise Conflict("Retests are requested for APPROVED or REJECTED results (use the QA decision during review).",
                       error_code="RESULT_NOT_RETESTABLE")
    t = db.get(LabTest, r.test_id)
    assert t is not None
    sample = db.get(LabSample, data.sample_id or t.sample_id)
    if sample is None or sample.root_sample_id != t.root_sample_id or sample.laboratory_org_id != t.laboratory_org_id:
        raise ValidationFailed("A retest uses the same sample or a split of the same root sample.", error_code="INVALID_RETEST_SAMPLE")
    open_retest = db.scalars(select(LabTest).where(LabTest.retest_of_test_id == t.id, LabTest.status.notin_(["CLOSED", "CANCELLED"]))).first()
    if open_retest is not None:
        raise Conflict(f"Retest {open_retest.test_code} is already open.", error_code="RETEST_OPEN")
    if sample.status == "ANALYSED":
        ls.custody(db, ctx, principal, sample, "ANALYSIS_STARTED", "IN_ANALYSIS", side="LABORATORY", org_id=sample.laboratory_org_id,
                   perm=P.LAB_RETEST_REQUEST, reason=data.reason)
    nt = _new_retest(db, ctx, principal, t, sample, data.reason)
    db.commit()
    return nt


def results_awaiting_qa(db: Session, principal: Principal) -> list[LabResult]:
    vis = visible_sample_ids(db, principal)
    stmt = select(LabResult).where(LabResult.status.in_(["SUBMITTED", "QA_REVIEW"]))
    if vis is not None:
        stmt = stmt.where(LabResult.sample_id.in_(vis or {uuid.uuid4()}))
    return list(db.scalars(stmt.order_by(LabResult.submitted_at)).all())


def counts(db: Session, principal: Principal) -> dict[str, int]:
    eng = [e for e in engagements(db, principal) if e.status == "PROPOSED"]
    ships = [s for s in inbox(db, principal) if s.status == "DISPATCHED"]
    to_register = [s for s in lab_samples(db, principal) if s.status == "LAB_RECEIVED"]
    tests = [t for t in worklist(db, principal) if t.status in ("REQUESTED", "IN_PROGRESS")]
    return {"engagements_pending": len(eng), "shipments_incoming": len(ships), "samples_to_register": len(to_register),
            "tests_open": len(tests), "results_awaiting_qa": len(results_awaiting_qa(db, principal))}


def document_ids_for_shipment(db: Session, shipment_id: uuid.UUID) -> list[Document]:
    return list(db.scalars(select(Document).where(Document.entity_type == "lab_shipment", Document.entity_id == shipment_id,
                                                  Document.category == "CUSTODY_DOCUMENT", Document.status == "ACTIVE")).all())


def upload_custody_document(db: Session, ctx: RequestContext, principal: Principal, shipment_id: uuid.UUID, filename: str | None,
                            data: bytes, title: str | None, side: str) -> Document:
    sh = db.get(LabShipment, shipment_id)
    if sh is None:
        raise ls.not_found("Shipment")
    if side == "PROJECT":
        ls.get_shipment(db, principal, shipment_id, P.LAB_SHIPMENT_MANAGE)
        org = db.get(Project, sh.project_id).organization_id  # type: ignore[union-attr]
    else:
        lab_shipment(db, principal, shipment_id, P.LAB_RECEIVE)
        org = sh.laboratory_org_id
    doc = document_service.create_document(db, ctx, entity_type="lab_shipment", entity_id=sh.id, organization_id=org,
                                           environment=sh.environment, category="CUSTODY_DOCUMENT", title=title or "Custody document",
                                           filename=filename, data=data)
    ls.audit(db, ctx, "LAB_CUSTODY_DOCUMENT_ATTACHED", sh.id, {"shipment_code": sh.shipment_code, "document_id": doc.id}, org,
             entity_type="lab_shipment")
    db.commit()
    return doc


# ---------------------------------------------------------------- document access (decision 16)
def _result_doc_resolver(db: Session, principal: Principal, result_id: uuid.UUID, kind: str) -> None:
    r = db.get(LabResult, result_id)
    nf = NotFound("Document not found.", error_code="DOCUMENT_NOT_FOUND")
    if r is None:
        raise nf
    p = db.get(Project, r.project_id)
    if kind == "manage":
        if not principal.can_in_org(P.LAB_TEST, r.laboratory_org_id):
            raise nf
        return
    if principal.can_in_org(P.LAB_LAB_READ, r.laboratory_org_id):
        vis = visible_sample_ids(db, principal)
        if vis is None or r.sample_id in vis:
            return
    if p is not None and principal.can_in_org(P.LAB_READ, p.organization_id) and r.status != "DRAFT":
        return
    raise nf


def _shipment_doc_resolver(db: Session, principal: Principal, shipment_id: uuid.UUID, kind: str) -> None:
    sh = db.get(LabShipment, shipment_id)
    nf = NotFound("Document not found.", error_code="DOCUMENT_NOT_FOUND")
    if sh is None:
        raise nf
    p = db.get(Project, sh.project_id)
    if kind == "manage":
        if (p is not None and principal.can_in_org(P.LAB_SHIPMENT_MANAGE, p.organization_id)) or principal.can_in_org(P.LAB_RECEIVE,
                                                                                                                      sh.laboratory_org_id):
            return
        raise nf
    if p is not None and principal.can_in_org(P.LAB_READ, p.organization_id):
        return
    if principal.can_in_org(P.LAB_LAB_READ, sh.laboratory_org_id) and sh.status in ("DISPATCHED", "RECEIVED"):
        return
    raise nf


document_service.register_resolver("lab_result", _result_doc_resolver)
document_service.register_resolver("lab_shipment", _shipment_doc_resolver)


def doc_ref(db: Session, doc_id: uuid.UUID | None) -> dict[str, Any] | None:
    if doc_id is None:
        return None
    doc = db.get(Document, doc_id)
    if doc is None:
        return None
    v = db.scalars(select(DocumentVersion).where(DocumentVersion.document_id == doc.id, DocumentVersion.version == doc.current_version)).first()
    return {"document_id": doc.id, "category": doc.category, "title": doc.title, "file_name": v.file_name if v else None,
            "sha256": v.checksum_sha256 if v else None, "uploaded_at": v.uploaded_at if v else None}


def latest_version_no(db: Session, test_id: uuid.UUID) -> int:
    return db.scalar(select(func.max(LabResult.version)).where(LabResult.test_id == test_id)) or 0
