"""Phase 9A mappers. The three quantities are rendered side by side but never derived from one another."""
import json
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFound, PermissionDenied
from app.integrations.registry import ADAPTERS
from app.models import (
    CreditBatch,
    CreditIssuance,
    MonitoringPeriod,
    MrvDataset,
    Organization,
    Project,
    RegistryAccount,
    RegistryEvent,
    RegistryProjectRegistration,
    RegistrySubmission,
    User,
    VerificationDecision,
)
from app.schemas.registry import (
    CALCULATED_LABEL,
    DEMO_NOTE,
    ISSUED_LABEL,
    ISSUED_NOTE,
    VERIFIED_LABEL,
    AccountOut,
    BatchOut,
    EligibilityOut,
    EventOut,
    IssuanceOut,
    PeriodRegistryView,
    Quantity,
    RegistrationOut,
    SerialRangeOut,
    SubmissionDetail,
    SubmissionOut,
)
from app.security.permissions import P
from app.security.principal import Principal
from app.services import credit_issuance as ci
from app.services import registry_service as rs


def _names(db: Session, ids: set[Any]) -> dict[Any, str]:
    ids_ = {i for i in ids if i}
    return {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_(ids_))).all()} if ids_ else {}


def _org_name(db: Session, org_id: uuid.UUID | None) -> str | None:
    org = db.get(Organization, org_id) if org_id else None
    return org.name if org else None


def _num(v: Decimal | None) -> str | None:
    return format(v.normalize(), "f") if v is not None else None


def account_out(db: Session, a: RegistryAccount) -> AccountOut:
    adapter = ADAPTERS.get(a.adapter_code)
    return AccountOut(id=a.id, organization_id=a.organization_id, registry_organization_id=a.registry_organization_id,
                      registry_name=_org_name(db, a.registry_organization_id), external_account_id=a.external_account_id, label=a.label,
                      adapter_code=a.adapter_code, adapter_mode=adapter.mode if adapter else None, credit_unit=a.credit_unit,
                      verified_unit_equivalent=a.verified_unit_equivalent, document_checklist=rs.parse_checklist(a.document_checklist),
                      status=a.status, created_at=a.created_at, closed_reason=a.closed_reason, environment=a.environment)


def registration_out(db: Session, r: RegistryProjectRegistration) -> RegistrationOut:
    names = _names(db, {r.recorded_by})
    return RegistrationOut(id=r.id, registration_code=r.registration_code, project_id=r.project_id, registry_account_id=r.registry_account_id,
                           registry_organization_id=r.registry_organization_id, registry_name=_org_name(db, r.registry_organization_id),
                           status=r.status, external_project_id=r.external_project_id, registered_on=r.registered_on,
                           evidence_document_id=r.evidence_document_id, response_reason=r.response_reason, notes=r.notes,
                           recorded_by_name=names.get(r.recorded_by), recorded_at=r.recorded_at, created_at=r.created_at)


def event_out(names: dict[Any, str], e: RegistryEvent) -> EventOut:
    return EventOut(id=e.id, event_type=e.event_type, occurred_at=e.occurred_at, actor_name=names.get(e.actor_id) if e.actor_id else "system",
                    adapter_code=e.adapter_code, idempotency_key=e.idempotency_key, external_ref=e.external_ref, payload_sha256=e.payload_sha256,
                    outcome=e.outcome, checklist_item=e.checklist_item, note=e.note, document_id=e.document_id)


def _superseded(db: Session, decision_id: uuid.UUID) -> bool:
    d = db.get(VerificationDecision, decision_id)
    return d is not None and d.status != "CURRENT"


def batch_out(db: Session, b: CreditBatch) -> BatchOut:
    i = db.get(CreditIssuance, b.issuance_id)
    p = db.get(Project, b.project_id)
    mp = db.get(MonitoringPeriod, b.monitoring_period_id)
    ranges = ci.ranges_of(db, b.id)
    return BatchOut(id=b.id, batch_code=b.batch_code, issuance_id=b.issuance_id, issuance_code=i.issuance_code if i else None,
                    external_issuance_id=i.external_issuance_id if i else None, project_id=b.project_id, project_code=p.project_code if p else None,
                    monitoring_period_id=b.monitoring_period_id, period_number=mp.period_number if mp else None,
                    registry_name=_org_name(db, b.registry_organization_id), vintage=b.vintage, quantity=int(b.quantity), unit=b.unit,
                    status=b.status, issuance_date=i.issuance_date if i else None,
                    serial_ranges=[SerialRangeOut(seq=r.seq, serial_start=r.serial_start, serial_end=r.serial_end, quantity=int(r.quantity),
                                                  parsed=r.parsed_series is not None, is_current=r.is_current) for r in ranges],
                    source_superseded=_superseded(db, b.verification_decision_id), environment=b.environment)


def issuance_out(db: Session, principal: Principal, i: CreditIssuance) -> IssuanceOut:
    names = _names(db, {i.recorded_by, i.confirmed_by})
    p = db.get(Project, i.project_id)
    can_confirm = (i.status == "RECORDED" and p is not None and principal.can_in_org(P.REGISTRY_CONFIRM, p.organization_id)
                   and principal.user_id != i.recorded_by)
    return IssuanceOut(id=i.id, issuance_code=i.issuance_code, registry_submission_id=i.registry_submission_id,
                       external_issuance_id=i.external_issuance_id, issuance_date=i.issuance_date, quantity=int(i.quantity), unit=i.unit,
                       source=i.source, evidence_document_id=i.evidence_document_id, api_response_sha256=i.api_response_sha256, status=i.status,
                       corrects_issuance_id=i.corrects_issuance_id, corrected_by_issuance_id=i.corrected_by_issuance_id,
                       correction_reason=i.correction_reason, recorded_by_name=names.get(i.recorded_by), recorded_at=i.recorded_at,
                       confirmed_by_name=names.get(i.confirmed_by) if i.confirmed_by else None, confirmed_at=i.confirmed_at,
                       void_reason=i.void_reason, cancel_reason=i.cancel_reason, batches=[batch_out(db, b) for b in ci.batches_of(db, i.id)],
                       can_confirm=can_confirm)


def submission_out(db: Session, s: RegistrySubmission) -> SubmissionOut:
    reg = db.get(RegistryProjectRegistration, s.registration_id)
    d = db.get(VerificationDecision, s.verification_decision_id)
    return SubmissionOut(id=s.id, submission_code=s.submission_code, project_id=s.project_id, monitoring_period_id=s.monitoring_period_id,
                         registration_id=s.registration_id, registration_code=reg.registration_code if reg else None,
                         external_project_id=reg.external_project_id if reg else None, registry_account_id=s.registry_account_id,
                         registry_name=_org_name(db, s.registry_organization_id), verification_decision_id=s.verification_decision_id,
                         decision_code=d.decision_code if d else None, decision_status=d.status if d else None,
                         previous_submission_id=s.previous_submission_id, status=s.status, snapshot_sha256=s.snapshot_sha256,
                         idempotency_key=s.idempotency_key, external_submission_id=s.external_submission_id,
                         submission_evidence_document_id=s.submission_evidence_document_id, response_document_id=s.response_document_id,
                         response_payload_sha256=s.response_payload_sha256, external_response_ref=s.external_response_ref,
                         response_reason=s.response_reason, created_at=s.created_at, frozen_at=s.frozen_at, submitted_at=s.submitted_at,
                         response_at=s.response_at, closed_reason=s.closed_reason, source_superseded=_superseded(db, s.verification_decision_id),
                         environment=s.environment)


def submission_detail(db: Session, principal: Principal, s: RegistrySubmission) -> SubmissionDetail:
    evs = rs.events_of(db, s)
    names = _names(db, {e.actor_id for e in evs})
    account = db.get(RegistryAccount, s.registry_account_id)
    checklist = rs.checklist_state(db, account, s)[0] if account else None
    docs = [{"document_id": str(doc.id), "category": doc.category, "title": doc.title, "sha256": e.payload_sha256,
             "checklist_item": e.checklist_item, "attached_at": e.occurred_at.isoformat() + "Z"} for doc, e in rs.documents_of(db, s)]
    return SubmissionDetail(**submission_out(db, s).model_dump(), snapshot=json.loads(s.snapshot) if s.snapshot else None,
                            events=[event_out(names, e) for e in evs], issuances=[issuance_out(db, principal, i) for i in ci.issuances_of(db, s.id)],
                            checklist=checklist, documents=docs)


def period_view_out(db: Session, principal: Principal, v: dict[str, Any]) -> PeriodRegistryView:
    p, mp, run, d = v["project"], v["period"], v["run"], v["decision"]
    totals: dict[str, Decimal] = {}
    for i in v["issuances"]:
        if i.status == "CONFIRMED":
            totals[i.unit] = totals.get(i.unit, Decimal(0)) + i.quantity
    issued = [Quantity(label=ISSUED_LABEL, value=_num(q), unit=u, note=ISSUED_NOTE) for u, q in sorted(totals.items())] or \
        [Quantity(label=ISSUED_LABEL, value=None, unit=None, note="No confirmed registry issuance.")]
    remaining = None
    accepted = next((s for s in v["submissions"] if s.status == "ACCEPTED"), None)
    if accepted is not None:
        account = db.get(RegistryAccount, accepted.registry_account_id)
        dd = db.get(VerificationDecision, accepted.verification_decision_id)
        if (account and dd and dd.verified_quantity is not None and account.credit_unit and account.verified_unit_equivalent
                and dd.verified_quantity_unit == account.verified_unit_equivalent):
            remaining = Quantity(label="Remaining against the VVB-stated quantity", value=_num(dd.verified_quantity - ci.confirmed_total(db, dd.id)),
                                 unit=account.credit_unit,
                                 note=f"Only because the registry account declares 1 {account.credit_unit} = 1 {account.verified_unit_equivalent}.")
    return PeriodRegistryView(
        project_id=p.id, organization_id=p.organization_id, project_status=p.status, environment=p.environment,
        demo_note=DEMO_NOTE if p.environment == "DEMO" else None,
        monitoring_period_id=mp.id, period_number=mp.period_number, registry_status=v["registry_status"],
        calculated=Quantity(label=CALCULATED_LABEL, value=run.net_result if run else None, unit=run.net_unit if run else None),
        verified=Quantity(label=VERIFIED_LABEL, value=_num(d.verified_quantity) if d else None, unit=d.verified_quantity_unit if d else None,
                          note=f"{d.decision_code} · {d.outcome}" if d else "No current VVB decision."),
        issued=issued, remaining=remaining, decision_code=d.decision_code if d else None,
        eligibility=[EligibilityOut(registry_account_id=e["account"].id if e["account"] else None,
                                    account_label=e["account"].label if e["account"] else None, blockers=e["blockers"], warnings=e["warnings"])
                     for e in v["eligibility"]],
        registrations=[registration_out(db, r) for r in v["registrations"]], submissions=[submission_out(db, s) for s in v["submissions"]],
        issuances=[issuance_out(db, principal, i) for i in v["issuances"]], can_manage=v["can_manage"], can_confirm=v["can_confirm"])


def lineage(db: Session, principal: Principal, b: CreditBatch) -> dict[str, Any]:
    """batch → serial ranges → issuance → registry submission (frozen snapshot) → registration → registry → VVB decision → verification
    submission → readiness → calculation report → run → methodology → dataset → period → project → farms → farmer codes."""
    i = db.get(CreditIssuance, b.issuance_id)
    assert i is not None
    s = db.get(RegistrySubmission, i.registry_submission_id)
    assert s is not None
    snap = json.loads(s.snapshot or "{}")
    p = db.get(Project, b.project_id)
    assert p is not None
    batch = batch_out(db, b).model_dump(mode="json")
    chain: list[dict[str, Any]] = [
        {"kind": "CREDIT_BATCH", "id": str(b.id), "code": b.batch_code, "status": b.status, "vintage": b.vintage, "quantity": int(b.quantity),
         "unit": b.unit, "label": ISSUED_LABEL},
        {"kind": "CREDIT_ISSUANCE", "id": str(i.id), "code": i.issuance_code, "status": i.status, "external_issuance_id": i.external_issuance_id,
         "issuance_date": i.issuance_date.isoformat(), "source": i.source,
         "evidence_document_id": str(i.evidence_document_id) if i.evidence_document_id else None,
         "api_response_sha256": i.api_response_sha256, "corrects_issuance_id": str(i.corrects_issuance_id) if i.corrects_issuance_id else None},
        {"kind": "REGISTRY_SUBMISSION", "id": str(s.id), "code": s.submission_code, "status": s.status,
         "external_submission_id": s.external_submission_id, "snapshot_sha256": s.snapshot_sha256},
        {"kind": "REGISTRY_REGISTRATION", **(snap.get("registration") or {})},
        {"kind": "REGISTRY", **(snap.get("registry") or {})},
        {"kind": "VERIFICATION_DECISION", **(snap.get("verification_decision") or {}), "current": not _superseded(db, i.verification_decision_id)},
        {"kind": "VERIFICATION_SUBMISSION", **(snap.get("verification_submission") or {})},
        {"kind": "READINESS_REVIEW", **(snap.get("readiness") or {})},
        {"kind": "CALCULATION_REPORT", **(snap.get("calculation_report") or {})},
        {"kind": "CALCULATION_RUN", **(snap.get("calculation_run") or {})},
        {"kind": "METHODOLOGY_VERSION", **(snap.get("methodology") or {})},
        {"kind": "MRV_DATASET", **(snap.get("dataset") or {})},
        {"kind": "MONITORING_PERIOD", **(snap.get("monitoring_period") or {})},
        {"kind": "PROJECT", "id": str(p.id), "code": p.project_code, "status": p.status},
    ]
    from app.services import verification_package as vp
    ds_id = (snap.get("dataset") or {}).get("id")
    ds = db.get(MrvDataset, uuid.UUID(ds_id)) if ds_id else None
    farms = vp._farms(db, json.loads(ds.snapshot)) if ds is not None and ds.snapshot else []
    sources = {"farms": [{"farm_code": f["farm_code"], "farmer_code": f["farmer_code"], "area_hectares": f["area_hectares"]} for f in farms]}
    verification_lineage = calculation_lineage = None
    if any(principal.can_in_org(c, p.organization_id) for c in (P.VERIFICATION_READ, P.VERIFICATION_MANAGE, P.VERIFICATION_RESPOND)):
        from app.services import verification_service as vs
        verification_lineage = vs.lineage(db, principal, i.verification_decision_id)
    run_id = (snap.get("calculation_run") or {}).get("id")
    if run_id and principal.can_in_org(P.CALCULATION_READ, p.organization_id):
        from app.services import calculation_mappers as cm
        from app.services import calculation_service as cs
        try:
            run, _ = cs.get_run(db, principal, uuid.UUID(run_id))
            calculation_lineage = cm.lineage(db, principal, run).model_dump(mode="json")
        except (NotFound, PermissionDenied):
            calculation_lineage = None
    return {"batch": batch, "chain": chain, "sources": sources, "verification_lineage": verification_lineage,
            "calculation_lineage": calculation_lineage}


def batches(db: Session, principal: Principal, project_id: uuid.UUID | None, period_id: uuid.UUID | None) -> list[CreditBatch]:
    orgs = rs.visible_org_ids(principal, P.CREDITS_READ)
    stmt = select(CreditBatch).where(CreditBatch.status.in_(("ISSUED", "SUPERSEDED", "CANCELLED")))
    if orgs is not None:
        stmt = stmt.join(Project, Project.id == CreditBatch.project_id).where(Project.organization_id.in_(orgs or {uuid.uuid4()}))
    if project_id:
        stmt = stmt.where(CreditBatch.project_id == project_id)
    if period_id:
        stmt = stmt.where(CreditBatch.monitoring_period_id == period_id)
    return list(db.scalars(stmt.order_by(CreditBatch.batch_code)).all())

