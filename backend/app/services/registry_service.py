"""Phase 9A registry workflow: registry accounts, project registrations (external facts), registry submissions with a frozen snapshot,
registry responses, reconciliation and the per-period registry view.

- eligibility (D3, D11; re-checked at create, freeze and submit): CURRENT VVB decision · VERIFIED · not superseded · verification
  submission / manifest hashes match · VVB-stated verified quantity present · REGISTERED project registration at the target registry ·
  ACTIVE account and registry · same environment · no other open / accepted submission for the period at any registry · configured
  document checklist satisfied (D16; an unconfigured checklist is a warning outside production and a blocker in production)
- the snapshot (registry-submission-v1) is canonical JSON + SHA-256, fixed by a trigger once FROZEN
- external calls: SUBMITTING + idempotency key are committed first; a timeout leaves SUBMISSION_UNCONFIRMED (never retried
  automatically); reconciliation decides. The manual adapter never answers: operators record references with evidence
- a superseded VVB decision invalidates a DRAFT / FROZEN submission; once the registry may know the submission it is only flagged
  (SOURCE_SUPERSEDED) — nothing external is changed automatically and no history is rewritten (D12)
"""
import json
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, true
from sqlalchemy.orm import Session

from app.calculation import framework as fw
from app.core.config import get_settings
from app.core.context import RequestContext
from app.core.errors import Conflict, NotFound, PermissionDenied, ValidationFailed
from app.integrations.registry import ADAPTERS, ManualActionRequired, RegistryAdapter, RegistryTimeout, RegistryUnavailable, SubmissionPackage
from app.models import (
    CalculationReadinessReview,
    CalculationReport,
    CalculationRun,
    CreditBatch,
    CreditIssuance,
    Document,
    MonitoringPeriod,
    Organization,
    Project,
    ProjectStandard,
    RegistryAccount,
    RegistryEvent,
    RegistryProjectRegistration,
    RegistrySubmission,
    Standard,
    VerificationAssignment,
    VerificationDecision,
    VerificationSubmission,
)
from app.models.base import utcnow
from app.models.documents import DocumentCategory
from app.models.registry import OPEN_REGISTRATION_STATUSES, OPEN_RSUB_STATUSES
from app.repositories.sequences import next_code
from app.security.permissions import P
from app.security.principal import Principal
from app.services import document_service
from app.services import registry_access as ra
from app.services import verification_service as vs
from app.services.workflows import REGISTRY_ACCOUNT_MACHINE, REGISTRY_REGISTRATION_MACHINE, REGISTRY_SUBMISSION_MACHINE

SNAPSHOT_SCHEMA = "registry-submission-v1"
CHECKLIST_SOURCES = ("REGISTRY_SUBMISSION", "VERIFICATION_REPORT", "CALCULATION_REPORT")
SUBMISSION_DOC_CATEGORIES = {DocumentCategory.REGISTRY_SUBMISSION.value, DocumentCategory.REGISTRY_RESPONSE.value,
                             DocumentCategory.ISSUANCE_STATEMENT.value}


def blocker(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _conflict(blockers: list[dict[str, str]]) -> Conflict:
    first = blockers[0]
    return Conflict(first["message"], error_code=first["code"], details={"blockers": blockers})


def _iso(v: Any) -> str | None:
    return v.isoformat() + ("Z" if hasattr(v, "hour") else "") if v is not None else None


# ---------------------------------------------------------------- registries and accounts
def registries(db: Session, environment: str) -> list[Organization]:
    return list(db.scalars(select(Organization).where(Organization.org_type == "REGISTRY", Organization.status == "ACTIVE",
                                                      Organization.environment == environment).order_by(Organization.name)).all())


def visible_org_ids(principal: Principal, *codes: str) -> set[uuid.UUID] | None:
    """None = platform-wide; otherwise the organizations where the caller holds one of `codes`."""
    out: set[uuid.UUID] = set()
    for g in principal.grants:
        if any(c in g.permissions for c in codes):
            if g.organization_id is None:
                return None
            out.add(g.organization_id)
    return out


def accounts(db: Session, principal: Principal, organization_id: uuid.UUID | None = None) -> list[RegistryAccount]:
    orgs = visible_org_ids(principal, *ra.REGISTRY_VISIBLE)
    stmt = select(RegistryAccount)
    if orgs is not None:
        stmt = stmt.where(RegistryAccount.organization_id.in_(orgs or {uuid.uuid4()}))
    if organization_id:
        stmt = stmt.where(RegistryAccount.organization_id == organization_id)
    return list(db.scalars(stmt.order_by(RegistryAccount.created_at)).all())


def parse_checklist(raw: str | None) -> list[dict[str, str]] | None:
    return json.loads(raw) if raw else None


def _validate_config(credit_unit: str | None, verified_unit: str | None, checklist: list[dict[str, str]] | None) -> None:
    if (credit_unit is None) != (verified_unit is None):
        raise ValidationFailed("Unit equivalence needs both the registry credit unit and the verified unit it equals.",
                               error_code="UNIT_EQUIVALENCE_INCOMPLETE")
    if checklist is not None:
        codes = [i["code"] for i in checklist]
        if len(codes) != len(set(codes)):
            raise ValidationFailed("Checklist item codes must be unique.", error_code="CHECKLIST_INVALID")
        if any(i["source"] not in CHECKLIST_SOURCES for i in checklist):
            raise ValidationFailed(f"Checklist sources: {', '.join(CHECKLIST_SOURCES)}.", error_code="CHECKLIST_INVALID")


def create_account(db: Session, ctx: RequestContext, principal: Principal, data: Any) -> RegistryAccount:
    org = db.get(Organization, data.organization_id)
    if org is None:
        raise NotFound("Organization not found.", error_code="ORGANIZATION_NOT_FOUND")
    if not principal.can_in_org(P.REGISTRY_MANAGE, org.id):
        if any(principal.can_in_org(c, org.id) for c in ra.REGISTRY_VISIBLE):
            raise PermissionDenied(details={"required_permission": P.REGISTRY_MANAGE})
        raise NotFound("Organization not found.", error_code="ORGANIZATION_NOT_FOUND")
    if ra.registry_org_ok(db, data.registry_organization_id, org.environment) is None:
        raise Conflict("The counterparty is not an active registry of this environment.", error_code="NOT_A_REGISTRY")
    if data.adapter_code not in ADAPTERS:
        raise Conflict(f"No registry adapter {data.adapter_code!r} is available (only contracted registry APIs get an adapter).",
                       error_code="UNKNOWN_ADAPTER")
    checklist = [i.model_dump() for i in data.document_checklist] if data.document_checklist is not None else None
    _validate_config(data.credit_unit, data.verified_unit_equivalent, checklist)
    if db.scalars(select(RegistryAccount).where(RegistryAccount.registry_organization_id == data.registry_organization_id,
                                                RegistryAccount.external_account_id == data.external_account_id)).first():
        raise Conflict("This registry account is already recorded.", error_code="REGISTRY_ACCOUNT_EXISTS")
    a = RegistryAccount(organization_id=org.id, registry_organization_id=data.registry_organization_id, external_account_id=data.external_account_id,
                        label=data.label, adapter_code=data.adapter_code, credit_unit=data.credit_unit,
                        verified_unit_equivalent=data.verified_unit_equivalent,
                        document_checklist=json.dumps(checklist) if checklist is not None else None, status="ACTIVE",
                        created_by=principal.user_id, environment=org.environment)
    db.add(a)
    db.flush()
    ra.workflow(db, ctx, "registry_account", a.id, None, "ACTIVE", None)
    ra.audit(db, ctx, "REGISTRY_ACCOUNT_CREATED", "registry_account", a.id, org.id,
             {"registry_organization_id": a.registry_organization_id, "external_account_id": a.external_account_id, "adapter_code": a.adapter_code,
              "credit_unit": a.credit_unit, "verified_unit_equivalent": a.verified_unit_equivalent, "document_checklist": checklist})
    db.commit()
    return a


def _confirmed_issuances_of_account(db: Session, account_id: uuid.UUID) -> int:
    return int(db.scalar(select(func.count()).select_from(CreditIssuance).where(CreditIssuance.registry_account_id == account_id,
                                                                                CreditIssuance.status.in_(("CONFIRMED", "CORRECTED",
                                                                                                           "CANCELLED")))) or 0)


def configure_account(db: Session, ctx: RequestContext, principal: Principal, account_id: uuid.UUID, data: Any) -> RegistryAccount:
    a = ra.account_for(db, principal, account_id, P.REGISTRY_MANAGE)
    if a.status != "ACTIVE":
        raise Conflict("Closed registry accounts cannot be configured.", error_code="REGISTRY_ACCOUNT_INACTIVE")
    checklist = [i.model_dump() for i in data.document_checklist] if data.document_checklist is not None else None
    _validate_config(data.credit_unit, data.verified_unit_equivalent, checklist)
    units_changed = (a.credit_unit, a.verified_unit_equivalent) != (data.credit_unit, data.verified_unit_equivalent)
    if units_changed and _confirmed_issuances_of_account(db, a.id):
        raise Conflict("The unit equivalence cannot change once issuances on this account are confirmed.", error_code="UNIT_CONFIGURATION_LOCKED")
    old = {"credit_unit": a.credit_unit, "verified_unit_equivalent": a.verified_unit_equivalent,
           "document_checklist": parse_checklist(a.document_checklist)}
    a.credit_unit, a.verified_unit_equivalent = data.credit_unit, data.verified_unit_equivalent
    a.document_checklist = json.dumps(checklist) if checklist is not None else None
    ra.audit(db, ctx, "REGISTRY_ACCOUNT_CONFIGURED", "registry_account", a.id, a.organization_id,
             {"credit_unit": a.credit_unit, "verified_unit_equivalent": a.verified_unit_equivalent, "document_checklist": checklist},
             data.reason, old)
    db.commit()
    return a


def close_account(db: Session, ctx: RequestContext, principal: Principal, account_id: uuid.UUID, reason: str) -> RegistryAccount:
    a = ra.account_for(db, principal, account_id, P.REGISTRY_MANAGE)
    REGISTRY_ACCOUNT_MACHINE.assert_transition(a.status, "CLOSED")
    if db.scalars(select(RegistrySubmission).where(RegistrySubmission.registry_account_id == a.id,
                                                   RegistrySubmission.status.in_(OPEN_RSUB_STATUSES[:-1]))).first():
        raise Conflict("The account has open registry submissions.", error_code="REGISTRY_ACCOUNT_IN_USE")
    a.status, a.closed_by, a.closed_at, a.closed_reason = "CLOSED", principal.user_id, utcnow(), reason
    ra.workflow(db, ctx, "registry_account", a.id, "ACTIVE", "CLOSED", reason)
    ra.audit(db, ctx, "REGISTRY_ACCOUNT_CLOSED", "registry_account", a.id, a.organization_id, {"status": "CLOSED"}, reason, {"status": "ACTIVE"})
    db.commit()
    return a


# ---------------------------------------------------------------- project registrations (D3)
def registrations(db: Session, principal: Principal, project_id: uuid.UUID) -> list[RegistryProjectRegistration]:
    ra.project_for(db, principal, project_id)
    return list(db.scalars(select(RegistryProjectRegistration).where(RegistryProjectRegistration.project_id == project_id)
                           .order_by(RegistryProjectRegistration.created_at)).all())


def _project_account(db: Session, principal: Principal, p: Project, account_id: uuid.UUID) -> RegistryAccount:
    a = db.get(RegistryAccount, account_id)
    if a is None or a.organization_id != p.organization_id:
        raise NotFound("Registry account not found.", error_code="REGISTRY_ACCOUNT_NOT_FOUND")
    return a


def create_registration(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID, account_id: uuid.UUID,
                        notes: str | None) -> RegistryProjectRegistration:
    p = ra.project_for(db, principal, project_id, P.REGISTRY_MANAGE)
    a = _project_account(db, principal, p, account_id)
    problems = account_blockers(db, p, a)
    if problems:
        raise _conflict(problems)
    if db.scalars(select(RegistryProjectRegistration).where(RegistryProjectRegistration.project_id == p.id,
                                                            RegistryProjectRegistration.registry_organization_id == a.registry_organization_id,
                                                            RegistryProjectRegistration.status.in_(OPEN_REGISTRATION_STATUSES))).first():
        raise Conflict("The project already has a pending or registered registration at this registry.", error_code="REGISTRATION_EXISTS")
    r = RegistryProjectRegistration(registration_code=next_code(db, "registry_registration", utcnow().year), project_id=p.id,
                                    registry_account_id=a.id, registry_organization_id=a.registry_organization_id, status="PENDING",
                                    notes=notes, created_by=principal.user_id, environment=p.environment)
    db.add(r)
    db.flush()
    ra.workflow(db, ctx, "registry_registration", r.id, None, "PENDING", notes)
    ra.audit(db, ctx, "REGISTRY_REGISTRATION_CREATED", "registry_registration", r.id, p.organization_id,
             {"registration_code": r.registration_code, "registry_account_id": a.id, "registry_organization_id": a.registry_organization_id,
              "project_id": p.id})
    db.commit()
    return r


def upload_document(db: Session, ctx: RequestContext, principal: Principal, entity: str, entity_id: uuid.UUID, category: str,
                    filename: str | None, data: bytes, title: str | None, checklist_item: str | None = None) -> Document:
    if entity == ra.REGISTRATION_ENTITY:
        r, p = ra.registration_for(db, principal, entity_id, P.REGISTRY_MANAGE)
        account = db.get(RegistryAccount, r.registry_account_id)
        if category != DocumentCategory.REGISTRY_RESPONSE.value:
            raise ValidationFailed("Registration evidence is a REGISTRY_RESPONSE document.", error_code="INVALID_CATEGORY")
        link: dict[str, Any] = {"registration_id": r.id}
        code = r.registration_code
    else:
        s, p = ra.submission_for(db, principal, entity_id, P.REGISTRY_MANAGE)
        account = db.get(RegistryAccount, s.registry_account_id)
        if category not in SUBMISSION_DOC_CATEGORIES:
            raise ValidationFailed("Registry documents: REGISTRY_SUBMISSION, REGISTRY_RESPONSE or ISSUANCE_STATEMENT.",
                                   error_code="INVALID_CATEGORY")
        if category == DocumentCategory.REGISTRY_SUBMISSION.value and s.status != "DRAFT":
            raise Conflict("Documents sent with the submission are fixed once it is frozen.", error_code="SUBMISSION_FROZEN")
        if category != DocumentCategory.REGISTRY_SUBMISSION.value and s.status in ("DRAFT", "CANCELLED", "INVALIDATED"):
            raise Conflict("Registry responses and statements belong to a frozen or submitted submission.", error_code="SUBMISSION_NOT_FROZEN")
        if checklist_item is not None:
            items = {i["code"] for i in parse_checklist(account.document_checklist if account else None) or []}
            if category != DocumentCategory.REGISTRY_SUBMISSION.value or checklist_item not in items:
                raise ValidationFailed("Unknown checklist item for this registry account.", error_code="CHECKLIST_ITEM_UNKNOWN")
        link = {"submission_id": s.id}
        code = s.submission_code
    assert account is not None
    doc = document_service.create_document(db, ctx, entity_type=entity, entity_id=entity_id, organization_id=p.organization_id,
                                           environment=p.environment, category=category, title=title or f"{category.title()} ({code})",
                                           filename=filename, data=data)
    db.flush()
    sha = doc.versions[0].checksum_sha256 if doc.versions else None
    ra.event(db, account, "DOCUMENT_ATTACHED", principal.user_id, document_id=doc.id, payload_sha256=sha, checklist_item=checklist_item,
             outcome=category, **link)
    ra.audit(db, ctx, "REGISTRY_DOCUMENT_UPLOADED", entity, entity_id, p.organization_id,
             {"document_id": doc.id, "category": category, "sha256": sha, "checklist_item": checklist_item})
    db.commit()
    return doc


def _evidence(db: Session, entity: str, entity_id: uuid.UUID, document_id: uuid.UUID, categories: set[str]) -> Document:
    doc = document_service.require_attached(db, document_id, entity, entity_id, categories)
    assert doc is not None
    return doc


def record_registered(db: Session, ctx: RequestContext, principal: Principal, registration_id: uuid.UUID, external_project_id: str,
                      registered_on: date | None, document_id: uuid.UUID, note: str | None) -> RegistryProjectRegistration:
    r, p = ra.registration_for(db, principal, registration_id, P.REGISTRY_MANAGE)
    REGISTRY_REGISTRATION_MACHINE.assert_transition(r.status, "REGISTERED")
    _evidence(db, ra.REGISTRATION_ENTITY, r.id, document_id, {DocumentCategory.REGISTRY_RESPONSE.value})
    if db.scalars(select(RegistryProjectRegistration).where(RegistryProjectRegistration.registry_organization_id == r.registry_organization_id,
                                                            RegistryProjectRegistration.external_project_id == external_project_id)).first():
        raise Conflict("This external project ID is already recorded at this registry.", error_code="DUPLICATE_EXTERNAL_PROJECT")
    r.status, r.external_project_id, r.registered_on, r.evidence_document_id = "REGISTERED", external_project_id, registered_on, document_id
    r.recorded_by, r.recorded_at = principal.user_id, utcnow()
    account = db.get(RegistryAccount, r.registry_account_id)
    assert account is not None
    ra.event(db, account, "EXTERNAL_REFERENCE_RECORDED", principal.user_id, registration_id=r.id, external_ref=external_project_id,
             document_id=document_id, outcome="REGISTERED", note=note)
    ra.workflow(db, ctx, "registry_registration", r.id, "PENDING", "REGISTERED", note)
    ra.audit(db, ctx, "REGISTRY_REGISTRATION_REGISTERED", "registry_registration", r.id, p.organization_id,
             {"external_project_id": external_project_id, "registered_on": registered_on, "evidence_document_id": document_id,
              "label": "Recorded external fact — the platform did not register the project"}, note, {"status": "PENDING"})
    db.commit()
    return r


def record_registration_rejected(db: Session, ctx: RequestContext, principal: Principal, registration_id: uuid.UUID, reason: str,
                                 document_id: uuid.UUID) -> RegistryProjectRegistration:
    r, p = ra.registration_for(db, principal, registration_id, P.REGISTRY_MANAGE)
    REGISTRY_REGISTRATION_MACHINE.assert_transition(r.status, "REJECTED")
    _evidence(db, ra.REGISTRATION_ENTITY, r.id, document_id, {DocumentCategory.REGISTRY_RESPONSE.value})
    r.status, r.response_reason, r.evidence_document_id, r.recorded_by, r.recorded_at = "REJECTED", reason, document_id, principal.user_id, utcnow()
    account = db.get(RegistryAccount, r.registry_account_id)
    assert account is not None
    ra.event(db, account, "RESPONSE_RECORDED", principal.user_id, registration_id=r.id, document_id=document_id, outcome="REJECTED", note=reason)
    ra.workflow(db, ctx, "registry_registration", r.id, "PENDING", "REJECTED", reason)
    ra.audit(db, ctx, "REGISTRY_REGISTRATION_REJECTED", "registry_registration", r.id, p.organization_id, {"status": "REJECTED"}, reason,
             {"status": "PENDING"})
    db.commit()
    return r


# ---------------------------------------------------------------- eligibility
def current_decision(db: Session, ctx: RequestContext, period_id: uuid.UUID) -> VerificationDecision | None:
    """The period's CURRENT VVB decision after the Phase 8B lazy re-check (a recalculation supersedes it first)."""
    for a in db.scalars(select(VerificationAssignment).where(VerificationAssignment.monitoring_period_id == period_id,
                                                             VerificationAssignment.status.in_(("ACCEPTED", "COMPLETED")))).all():
        vs.refresh(db, ctx, a)
    return db.scalars(select(VerificationDecision).where(VerificationDecision.monitoring_period_id == period_id,
                                                         VerificationDecision.status == "CURRENT")).first()


def decision_blockers(db: Session, d: VerificationDecision | None) -> list[dict[str, str]]:
    if d is None:
        return [blocker("NO_VERIFIED_DECISION", "The monitoring period has no current VVB decision.")]
    if d.outcome != "VERIFIED":
        return [blocker("DECISION_NOT_VERIFIED", f"The current VVB decision {d.decision_code} is {d.outcome}.")]
    out = []
    vsub = db.get(VerificationSubmission, d.submission_id)
    if vsub is None or vsub.status != "SUBMITTED" or vsub.manifest_sha256 != d.manifest_sha256:
        out.append(blocker("VERIFICATION_PACKAGE_MISMATCH", "The verified package no longer matches the decision's manifest hash."))
    if d.verified_quantity is None or not d.verified_quantity_unit:
        out.append(blocker("VERIFIED_QUANTITY_REQUIRED", "The VVB decision states no verified quantity; the calculated quantity is never used."))
    return out


def account_blockers(db: Session, p: Project, a: RegistryAccount) -> list[dict[str, str]]:
    out = []
    if a.status != "ACTIVE":
        out.append(blocker("REGISTRY_ACCOUNT_INACTIVE", "The registry account is closed."))
    if a.environment != p.environment:
        out.append(blocker("ENVIRONMENT_MISMATCH", "The registry account belongs to another environment."))
    if ra.registry_org_ok(db, a.registry_organization_id, p.environment) is None:
        out.append(blocker("REGISTRY_INACTIVE", "The registry is not an active registry of this environment."))
    return out


def registered(db: Session, p: Project, a: RegistryAccount) -> RegistryProjectRegistration | None:
    return db.scalars(select(RegistryProjectRegistration).where(RegistryProjectRegistration.project_id == p.id,
                                                                RegistryProjectRegistration.registry_organization_id == a.registry_organization_id,
                                                                RegistryProjectRegistration.status == "REGISTERED")).first()


def checklist_state(db: Session, a: RegistryAccount, s: RegistrySubmission | None) -> tuple[list[dict[str, Any]] | None, list[str]]:
    """(items with satisfaction, missing item codes). None = no checklist configured."""
    items = parse_checklist(a.document_checklist)
    if items is None:
        return None, []
    attached = set()
    if s is not None:
        attached = {e.checklist_item for e in db.scalars(select(RegistryEvent).where(RegistryEvent.submission_id == s.id,
                                                                                    RegistryEvent.event_type == "DOCUMENT_ATTACHED",
                                                                                    RegistryEvent.checklist_item.is_not(None))).all()}
    out, missing = [], []
    for i in items:
        ok = i["source"] in ("VERIFICATION_REPORT", "CALCULATION_REPORT") or i["code"] in attached   # lineage documents are always included
        out.append({**i, "satisfied": ok})
        if not ok:
            missing.append(i["code"])
    return out, missing


def eligibility(db: Session, ctx: RequestContext, p: Project, mp: MonitoringPeriod, a: RegistryAccount | None,
                s: RegistrySubmission | None = None, *, for_freeze: bool = False, adapter: RegistryAdapter | None = None
                ) -> tuple[list[dict[str, str]], list[dict[str, str]], VerificationDecision | None]:
    blockers = decision_blockers(db, d := current_decision(db, ctx, mp.id))
    warnings: list[dict[str, str]] = []
    if a is not None:
        blockers += account_blockers(db, p, a)
        if registered(db, p, a) is None:
            blockers.append(blocker("REGISTRATION_REQUIRED", "The project has no REGISTERED registration at this registry."))
        if p.environment == "DEMO" and ra.adapter_for(a, adapter).mode == "API":
            blockers.append(blocker("DEMO_API_NOT_ALLOWED", "DEMO projects never use a registry API."))
        items, missing = checklist_state(db, a, s)
        if items is None:
            b = blocker("CHECKLIST_NOT_CONFIGURED", "No registry document checklist is configured for this account (none is invented).")
            (blockers if get_settings().is_production else warnings).append(b)
        elif for_freeze and missing:
            blockers.append(blocker("CHECKLIST_INCOMPLETE", "Missing registry documents: " + ", ".join(missing)))
    other = select(RegistrySubmission).where(RegistrySubmission.monitoring_period_id == mp.id, RegistrySubmission.status.in_(OPEN_RSUB_STATUSES))
    if s is not None:
        other = other.where(RegistrySubmission.id != s.id)
    if (o := db.scalars(other).first()) is not None:
        blockers.append(blocker("OPEN_REGISTRY_SUBMISSION_EXISTS", f"Registry submission {o.submission_code} is {o.status} for this period."))
    return blockers, warnings, d


# ---------------------------------------------------------------- submissions
def _period(db: Session, p: Project, period_id: uuid.UUID) -> MonitoringPeriod:
    mp = db.get(MonitoringPeriod, period_id)
    if mp is None or mp.project_id != p.id:
        raise NotFound("Monitoring period not found.", error_code="PERIOD_NOT_FOUND")
    return mp


def _transition(db: Session, ctx: RequestContext, s: RegistrySubmission, p: Project, to: str, action: str, reason: str | None,
                **extra: Any) -> None:
    frm = s.status
    REGISTRY_SUBMISSION_MACHINE.assert_transition(frm, to)
    s.status = to
    ra.workflow(db, ctx, "registry_submission", s.id, frm, to, reason)
    ra.audit(db, ctx, action, "registry_submission", s.id, p.organization_id, {"submission_code": s.submission_code, "status": to, **extra},
             reason, {"status": frm})


def check_source(db: Session, ctx: RequestContext, s: RegistrySubmission) -> None:
    """D12: a superseded VVB decision invalidates an unsent submission; a sent one is flagged once, never changed automatically."""
    d = db.get(VerificationDecision, s.verification_decision_id)
    if d is None or s.status in ("REJECTED", "WITHDRAWN", "CANCELLED", "INVALIDATED"):
        return
    assignment = db.get(VerificationAssignment, d.assignment_id)
    if assignment is not None:
        vs.refresh(db, ctx, assignment)
        db.refresh(d)
    if d.status == "CURRENT":
        return
    p = db.get(Project, s.project_id)
    account = db.get(RegistryAccount, s.registry_account_id)
    assert p is not None and account is not None
    reason = f"VVB decision {d.decision_code} is superseded: {d.superseded_reason or 'source changed'}"
    if s.status in ("DRAFT", "FROZEN"):
        s.closed_at, s.closed_reason = utcnow(), reason[:2000]
        _transition(db, ctx, s, p, "INVALIDATED", "REGISTRY_SUBMISSION_INVALIDATED", reason)
        db.commit()
    elif not db.scalars(select(RegistryEvent).where(RegistryEvent.submission_id == s.id, RegistryEvent.event_type == "SOURCE_SUPERSEDED")).first():
        ra.event(db, account, "SOURCE_SUPERSEDED", None, submission_id=s.id, outcome=s.status, note=reason[:2000])
        ra.audit(db, ctx, "REGISTRY_SOURCE_SUPERSEDED", "registry_submission", s.id, p.organization_id,
                 {"submission_code": s.submission_code, "status": s.status, "decision_code": d.decision_code,
                  "note": "Controlled registry action is required for any correction; nothing was changed automatically."}, reason)
        db.commit()


def create_submission(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID, period_id: uuid.UUID,
                      account_id: uuid.UUID, previous_id: uuid.UUID | None, request_key: str | None) -> RegistrySubmission:
    p = ra.project_for(db, principal, project_id, P.REGISTRY_MANAGE)
    if request_key:
        prior = db.scalars(select(RegistrySubmission).where(RegistrySubmission.client_request_key == request_key)).first()
        if prior is not None:
            if prior.project_id != p.id or prior.monitoring_period_id != period_id:
                raise Conflict("This Idempotency-Key was used for another request.", error_code="IDEMPOTENCY_KEY_REUSED")
            return prior
    mp = _period(db, p, period_id)
    first = decision_blockers(db, current_decision(db, ctx, mp.id))    # the most basic prerequisite is reported first (e.g. DEMO)
    if first:
        raise _conflict(first)
    a = _project_account(db, principal, p, account_id)
    blockers, _, d = eligibility(db, ctx, p, mp, a)
    if blockers:
        raise _conflict(blockers)
    assert d is not None
    reg = registered(db, p, a)
    assert reg is not None
    if previous_id is not None:
        prev = db.get(RegistrySubmission, previous_id)
        if prev is None or prev.monitoring_period_id != mp.id or prev.status not in ("REJECTED", "WITHDRAWN", "CANCELLED", "INVALIDATED"):
            raise Conflict("A follow-up must reference a closed submission of the same period.", error_code="INVALID_PREVIOUS_SUBMISSION")
    s = RegistrySubmission(submission_code=next_code(db, "registry_submission", utcnow().year), project_id=p.id, monitoring_period_id=mp.id,
                           registration_id=reg.id, registry_account_id=a.id, registry_organization_id=a.registry_organization_id,
                           verification_decision_id=d.id, verification_submission_id=d.submission_id, previous_submission_id=previous_id,
                           status="DRAFT", client_request_key=request_key, created_by=principal.user_id, environment=p.environment)
    db.add(s)
    db.flush()
    ra.workflow(db, ctx, "registry_submission", s.id, None, "DRAFT", None)
    ra.audit(db, ctx, "REGISTRY_SUBMISSION_CREATED", "registry_submission", s.id, p.organization_id,
             {"submission_code": s.submission_code, "monitoring_period_id": mp.id, "registry_account_id": a.id, "decision_code": d.decision_code,
              "previous_submission_id": previous_id})
    db.commit()
    return s


def documents_of(db: Session, s: RegistrySubmission, category: str | None = None) -> list[tuple[Document, RegistryEvent]]:
    rows = db.scalars(select(RegistryEvent).where(RegistryEvent.submission_id == s.id, RegistryEvent.event_type == "DOCUMENT_ATTACHED")
                      .order_by(RegistryEvent.occurred_at)).all()
    out = []
    for e in rows:
        doc = db.get(Document, e.document_id) if e.document_id else None
        if doc is not None and (category is None or doc.category == category):
            out.append((doc, e))
    return out


def build_snapshot(db: Session, s: RegistrySubmission, p: Project, mp: MonitoringPeriod, a: RegistryAccount, d: VerificationDecision
                   ) -> dict[str, Any]:
    """registry-submission-v1: references and hashes of what already exists (deterministic: no generation time, no user)."""
    vsub = db.get(VerificationSubmission, d.submission_id)
    reg = db.get(RegistryProjectRegistration, s.registration_id)
    org = db.get(Organization, a.registry_organization_id)
    assert vsub is not None and reg is not None and org is not None
    readiness = db.get(CalculationReadinessReview, vsub.readiness_review_id)
    run = db.get(CalculationRun, vsub.calculation_run_id)
    rep = db.get(CalculationReport, vsub.calculation_report_id)
    assert readiness is not None and run is not None and rep is not None
    manifest = json.loads(readiness.manifest or "{}")
    ps = db.scalars(select(ProjectStandard).where(ProjectStandard.project_id == p.id, ProjectStandard.is_current == true())).first()
    std = db.get(Standard, ps.standard_id) if ps else None
    items, _ = checklist_state(db, a, s)
    docs: list[dict[str, Any]] = [{"role": "VERIFICATION_REPORT", "document_id": str(d.report_document_id), "sha256": d.report_sha256},
            {"role": "CALCULATION_REPORT", "document_id": str(rep.document_id), "sha256": rep.pdf_sha256}]
    for doc, e in documents_of(db, s, DocumentCategory.REGISTRY_SUBMISSION.value):
        docs.append({"role": "REGISTRY_SUBMISSION", "document_id": str(doc.id), "sha256": e.payload_sha256, "checklist_item": e.checklist_item,
                     "title": doc.title})
    meth = manifest.get("methodology") or {}
    return {
        "schema": SNAPSHOT_SCHEMA,
        "label": "Registry submission package — requests issuance of the VVB-stated verified quantity; nothing here is an issued credit",
        "registry": {"organization_id": str(org.id), "code": org.code, "name": org.name},
        "account": {"id": str(a.id), "external_account_id": a.external_account_id, "adapter_code": a.adapter_code,
                    "credit_unit": a.credit_unit, "verified_unit_equivalent": a.verified_unit_equivalent},
        "registration": {"id": str(reg.id), "code": reg.registration_code, "external_project_id": reg.external_project_id,
                         "registered_on": _iso(reg.registered_on)},
        "project": {"id": str(p.id), "code": p.project_code, "name": p.name, "environment": p.environment},
        "monitoring_period": {"id": str(mp.id), "number": mp.period_number, "start": _iso(mp.start_date), "end": _iso(mp.end_date)},
        "crediting_period": manifest.get("crediting_period"),
        "standard": {"id": str(std.id), "code": std.code, "name": std.name} if std else None,
        "methodology": {k: meth.get(k) for k in ("methodology_id", "code", "version_id", "version_label")},
        "verification_decision": {"id": str(d.id), "code": d.decision_code, "outcome": d.outcome,
                                  "verified_quantity": format(d.verified_quantity.normalize(), "f") if d.verified_quantity is not None else None,
                                  "verified_quantity_unit": d.verified_quantity_unit, "label": "VVB-stated verified quantity",
                                  "report_sha256": d.report_sha256, "manifest_sha256": d.manifest_sha256, "decided_at": _iso(d.decided_at),
                                  "vvb_organization_id": str(d.vvb_organization_id)},
        "verification_submission": {"id": str(vsub.id), "code": vsub.submission_code, "manifest_sha256": vsub.manifest_sha256,
                                    "submitted_at": _iso(vsub.submitted_at)},
        "readiness": {"id": str(readiness.id), "code": readiness.readiness_code, "manifest_sha256": readiness.manifest_sha256,
                      "decided_at": _iso(readiness.decided_at)},
        "calculation_report": {"id": str(rep.id), "code": rep.report_code, "version": rep.version, "content_sha256": rep.content_sha256,
                               "pdf_sha256": rep.pdf_sha256, "generated_at": _iso(rep.generated_at)},
        "calculation_run": {"id": str(run.id), "code": run.run_code, "input_sha256": run.input_sha256, "output_sha256": run.output_sha256,
                            "approved_at": _iso(run.approved_at), "calculated_label": "Calculated tCO2e — not verified, not issued"},
        "dataset": manifest.get("dataset"),
        "documents": docs,
        "checklist": items,
    }


def freeze(db: Session, ctx: RequestContext, principal: Principal, submission_id: uuid.UUID, adapter: RegistryAdapter | None = None
           ) -> RegistrySubmission:
    s, p = ra.submission_for(db, principal, submission_id, P.REGISTRY_MANAGE)
    check_source(db, ctx, s)
    if s.status != "DRAFT":
        raise Conflict(f"Only a DRAFT submission can be frozen (it is {s.status}).", error_code="SUBMISSION_NOT_DRAFT")
    mp = _period(db, p, s.monitoring_period_id)
    a = db.get(RegistryAccount, s.registry_account_id)
    assert a is not None
    blockers, warnings, d = eligibility(db, ctx, p, mp, a, s, for_freeze=True, adapter=adapter)
    if not blockers and d is not None and d.id != s.verification_decision_id:
        blockers.append(blocker("NO_VERIFIED_DECISION", "The VVB decision changed since the submission was created."))
    if blockers:
        raise _conflict(blockers)
    assert d is not None
    snap = build_snapshot(db, s, p, mp, a, d)
    s.snapshot, s.snapshot_sha256 = fw.canonical_json(snap), fw.sha256(snap)
    s.idempotency_key, s.frozen_by, s.frozen_at = uuid.uuid4().hex, principal.user_id, utcnow()
    _transition(db, ctx, s, p, "FROZEN", "REGISTRY_SUBMISSION_FROZEN", None, snapshot_sha256=s.snapshot_sha256,
                idempotency_key=s.idempotency_key, warnings=[w["code"] for w in warnings])
    db.commit()
    return s


def _resubmit_checks(db: Session, ctx: RequestContext, s: RegistrySubmission, p: Project, adapter: RegistryAdapter | None) -> RegistryAccount:
    check_source(db, ctx, s)
    if s.status == "INVALIDATED":
        raise Conflict("The VVB decision behind this submission is superseded; the submission was invalidated.",
                       error_code="SUBMISSION_INVALIDATED")
    mp = _period(db, p, s.monitoring_period_id)
    a = db.get(RegistryAccount, s.registry_account_id)
    assert a is not None
    blockers, _, d = eligibility(db, ctx, p, mp, a, s, adapter=adapter)
    snap = json.loads(s.snapshot or "{}")
    frozen = snap["verification_decision"]
    if not blockers and (d is None or str(d.id) != frozen["id"] or d.manifest_sha256 != frozen["manifest_sha256"]):
        blockers.append(blocker("SNAPSHOT_STALE", "The verification behind the frozen snapshot changed."))
    if blockers:
        raise _conflict(blockers)
    return a


def submit(db: Session, ctx: RequestContext, principal: Principal, submission_id: uuid.UUID, adapter: RegistryAdapter | None = None
           ) -> RegistrySubmission:
    """API mode: SUBMITTING + idempotency key are committed BEFORE the external call; never retried automatically."""
    s, p = ra.submission_for(db, principal, submission_id, P.REGISTRY_MANAGE)
    if s.status != "FROZEN":
        raise Conflict(f"Only a FROZEN submission can be sent (it is {s.status}).", error_code="SUBMISSION_NOT_FROZEN")
    a = _resubmit_checks(db, ctx, s, p, adapter)
    impl = ra.adapter_for(a, adapter)
    if impl.mode == "MANUAL":
        raise Conflict("This registry is operated manually: record the external submission reference with its receipt.",
                       error_code="MANUAL_ACTION_REQUIRED")
    assert s.idempotency_key is not None
    s.submitted_by = principal.user_id
    _transition(db, ctx, s, p, "SUBMITTING", "REGISTRY_SUBMISSION_SUBMIT_ATTEMPTED", None, idempotency_key=s.idempotency_key)
    ra.event(db, a, "SUBMIT_ATTEMPT", principal.user_id, adapter_code=a.adapter_code, submission_id=s.id, idempotency_key=s.idempotency_key,
             payload_sha256=s.snapshot_sha256)
    db.commit()                                                   # persisted before the registry is called
    snap = json.loads(s.snapshot or "{}")
    package = SubmissionPackage(submission_code=s.submission_code, snapshot_sha256=s.snapshot_sha256 or "", snapshot=snap,
                                documents=tuple(snap.get("documents", [])))
    try:
        result = impl.submit_issuance_request(ra.account_ref(db, a), package, s.idempotency_key)
    except RegistryUnavailable as e:
        ra.event(db, a, "ERROR", principal.user_id, submission_id=s.id, idempotency_key=s.idempotency_key, outcome="UNAVAILABLE", note=str(e)[:2000])
        _transition(db, ctx, s, p, "FROZEN", "REGISTRY_SUBMISSION_UNAVAILABLE", str(e)[:1000])
        db.commit()
        raise Conflict("The registry is unavailable; nothing was sent. Try again later.", error_code="REGISTRY_UNAVAILABLE") from None
    except ManualActionRequired:
        raise
    except Exception as e:                                        # timeout or unknown outcome: the registry may have it
        kind = "TIMEOUT" if isinstance(e, RegistryTimeout) else "ERROR"
        ra.event(db, a, kind, principal.user_id, submission_id=s.id, idempotency_key=s.idempotency_key, outcome="UNKNOWN", note=str(e)[:2000])
        _transition(db, ctx, s, p, "SUBMISSION_UNCONFIRMED", "REGISTRY_SUBMISSION_UNCONFIRMED", "No confirmation from the registry",
                    idempotency_key=s.idempotency_key)
        db.commit()
        return s
    s.external_submission_id, s.submitted_at = result.external_submission_id, utcnow()
    ra.event(db, a, "SUBMIT_CONFIRMED", principal.user_id, submission_id=s.id, idempotency_key=s.idempotency_key,
             external_ref=result.external_submission_id, payload_sha256=result.payload_sha256, outcome="RECEIVED")
    _transition(db, ctx, s, p, "SUBMITTED", "REGISTRY_SUBMISSION_SUBMITTED", None, external_submission_id=s.external_submission_id)
    db.commit()
    return s


def _duplicate_external_submission(db: Session, s: RegistrySubmission, external_id: str) -> None:
    if db.scalars(select(RegistrySubmission).where(RegistrySubmission.registry_organization_id == s.registry_organization_id,
                                                   RegistrySubmission.external_submission_id == external_id,
                                                   RegistrySubmission.id != s.id)).first():
        raise Conflict("This external submission reference is already recorded at this registry.", error_code="DUPLICATE_EXTERNAL_SUBMISSION")


def record_submitted(db: Session, ctx: RequestContext, principal: Principal, submission_id: uuid.UUID, external_submission_id: str,
                     document_id: uuid.UUID, note: str | None) -> RegistrySubmission:
    """Manual path: FROZEN → SUBMITTED with the registry's reference and its receipt (never a plain 'submitted' click)."""
    s, p = ra.submission_for(db, principal, submission_id, P.REGISTRY_MANAGE)
    if s.status != "FROZEN":
        raise Conflict(f"Only a FROZEN submission can be recorded as submitted (it is {s.status}).", error_code="SUBMISSION_NOT_FROZEN")
    a = _resubmit_checks(db, ctx, s, p, None)
    _evidence(db, ra.SUBMISSION_ENTITY, s.id, document_id, {DocumentCategory.REGISTRY_RESPONSE.value})
    _duplicate_external_submission(db, s, external_submission_id)
    s.external_submission_id, s.submission_evidence_document_id = external_submission_id, document_id
    s.submitted_by, s.submitted_at = principal.user_id, utcnow()
    ra.event(db, a, "EXTERNAL_REFERENCE_RECORDED", principal.user_id, submission_id=s.id, external_ref=external_submission_id,
             document_id=document_id, outcome="SUBMITTED", note=note)
    _transition(db, ctx, s, p, "SUBMITTED", "REGISTRY_SUBMISSION_SUBMITTED", note, external_submission_id=external_submission_id,
                evidence_document_id=document_id, mode="MANUAL")
    ra.audit(db, ctx, "REGISTRY_EXTERNAL_REFERENCE_ADDED", "registry_submission", s.id, p.organization_id,
             {"external_submission_id": external_submission_id, "document_id": document_id})
    db.commit()
    return s


def record_query(db: Session, ctx: RequestContext, principal: Principal, submission_id: uuid.UUID, note: str,
                 document_id: uuid.UUID | None) -> RegistryEvent:
    s, p = ra.submission_for(db, principal, submission_id, P.REGISTRY_MANAGE)
    if s.status not in ("SUBMITTED", "ACCEPTED", "SUBMISSION_UNCONFIRMED"):
        raise Conflict("Registry queries are recorded on a submission the registry has.", error_code="SUBMISSION_NOT_SUBMITTED")
    if document_id is not None:
        _evidence(db, ra.SUBMISSION_ENTITY, s.id, document_id, {DocumentCategory.REGISTRY_RESPONSE.value})
    a = db.get(RegistryAccount, s.registry_account_id)
    assert a is not None
    e = ra.event(db, a, "QUERY_RECEIVED", principal.user_id, submission_id=s.id, document_id=document_id, note=note)
    ra.audit(db, ctx, "REGISTRY_QUERY_RECORDED", "registry_submission", s.id, p.organization_id, {"document_id": document_id}, note)
    db.commit()
    return e


def record_response(db: Session, ctx: RequestContext, principal: Principal, submission_id: uuid.UUID, outcome: str, document_id: uuid.UUID,
                    reason: str | None, external_response_ref: str | None) -> RegistrySubmission:
    s, p = ra.submission_for(db, principal, submission_id, P.REGISTRY_MANAGE)
    if s.status != "SUBMITTED":
        raise Conflict(f"A registry response is recorded on a SUBMITTED submission (it is {s.status}).", error_code="SUBMISSION_NOT_SUBMITTED")
    if outcome not in ("ACCEPTED", "REJECTED"):
        raise ValidationFailed("Outcome must be ACCEPTED or REJECTED.", error_code="INVALID_OUTCOME")
    if outcome == "REJECTED" and not (reason and reason.strip()):
        raise ValidationFailed("A rejection needs the registry's reason.", error_code="REASON_REQUIRED")
    check_source(db, ctx, s)
    _evidence(db, ra.SUBMISSION_ENTITY, s.id, document_id, {DocumentCategory.REGISTRY_RESPONSE.value})
    a = db.get(RegistryAccount, s.registry_account_id)
    assert a is not None
    s.response_document_id, s.response_reason, s.external_response_ref = document_id, reason, external_response_ref
    s.response_by, s.response_at = principal.user_id, utcnow()
    ra.event(db, a, "RESPONSE_RECORDED", principal.user_id, submission_id=s.id, document_id=document_id, outcome=outcome,
             external_ref=external_response_ref, note=reason)
    ra.audit(db, ctx, "REGISTRY_RESPONSE_RECORDED", "registry_submission", s.id, p.organization_id, {"outcome": outcome, "document_id": document_id})
    _transition(db, ctx, s, p, outcome, f"REGISTRY_SUBMISSION_{outcome}", reason, external_response_ref=external_response_ref)
    db.commit()
    return s


def withdraw(db: Session, ctx: RequestContext, principal: Principal, submission_id: uuid.UUID, reason: str, document_id: uuid.UUID
             ) -> RegistrySubmission:
    s, p = ra.submission_for(db, principal, submission_id, P.REGISTRY_MANAGE)
    if s.status != "SUBMITTED":
        raise Conflict(f"Only a SUBMITTED submission can be withdrawn (it is {s.status}).", error_code="SUBMISSION_NOT_SUBMITTED")
    _evidence(db, ra.SUBMISSION_ENTITY, s.id, document_id, {DocumentCategory.REGISTRY_RESPONSE.value})
    a = db.get(RegistryAccount, s.registry_account_id)
    assert a is not None
    s.closed_by, s.closed_at, s.closed_reason = principal.user_id, utcnow(), reason
    ra.event(db, a, "RESPONSE_RECORDED", principal.user_id, submission_id=s.id, document_id=document_id, outcome="WITHDRAWN", note=reason)
    _transition(db, ctx, s, p, "WITHDRAWN", "REGISTRY_SUBMISSION_WITHDRAWN", reason, document_id=document_id)
    db.commit()
    return s


def cancel(db: Session, ctx: RequestContext, principal: Principal, submission_id: uuid.UUID, reason: str) -> RegistrySubmission:
    s, p = ra.submission_for(db, principal, submission_id, P.REGISTRY_MANAGE)
    if s.status not in ("DRAFT", "FROZEN"):
        raise Conflict(f"Only an unsent (DRAFT / FROZEN) submission can be cancelled (it is {s.status}).", error_code="SUBMISSION_ALREADY_SENT")
    s.closed_by, s.closed_at, s.closed_reason = principal.user_id, utcnow(), reason
    _transition(db, ctx, s, p, "CANCELLED", "REGISTRY_SUBMISSION_CANCELLED", reason)
    db.commit()
    return s


def reconcile(db: Session, ctx: RequestContext, principal: Principal, submission_id: uuid.UUID, data: Any,
              adapter: RegistryAdapter | None = None) -> RegistrySubmission:
    """Resolve SUBMISSION_UNCONFIRMED, query SUBMITTED status, or compare issuances (API); manual reconciliation needs evidence."""
    s, p = ra.submission_for(db, principal, submission_id, P.REGISTRY_MANAGE)
    a = db.get(RegistryAccount, s.registry_account_id)
    assert a is not None
    impl = ra.adapter_for(a, adapter)
    manual = impl.mode == "MANUAL"
    if manual and (data is None or data.document_id is None):
        raise ValidationFailed("Manual reconciliation needs the registry evidence (REGISTRY_RESPONSE document).", error_code="EVIDENCE_REQUIRED")
    if manual:
        _evidence(db, ra.SUBMISSION_ENTITY, s.id, data.document_id,
                  {DocumentCategory.REGISTRY_RESPONSE.value, DocumentCategory.ISSUANCE_STATEMENT.value})
    ref = ra.account_ref(db, a)
    if s.status == "SUBMISSION_UNCONFIRMED":
        if manual:
            found, ext = data.outcome == "FOUND", data.external_submission_id
            if found and not ext:
                raise ValidationFailed("FOUND needs the registry's submission reference.", error_code="EXTERNAL_REFERENCE_REQUIRED")
            payload = None
        else:
            try:
                st = impl.get_submission_status(ref, idempotency_key=s.idempotency_key)
            except (RegistryUnavailable, RegistryTimeout) as e:
                ra.event(db, a, "ERROR", principal.user_id, submission_id=s.id, idempotency_key=s.idempotency_key, outcome="UNKNOWN", note=str(e))
                db.commit()
                raise Conflict("The registry could not confirm either way; the submission stays unconfirmed.",
                               error_code="REGISTRY_UNAVAILABLE") from None
            found, ext, payload = st.status != "NOT_FOUND", st.external_submission_id, st.payload_sha256
        if found:
            assert ext is not None
            _duplicate_external_submission(db, s, ext)
            s.external_submission_id, s.submitted_at = ext, utcnow()
            ra.event(db, a, "RECONCILED", principal.user_id, submission_id=s.id, idempotency_key=s.idempotency_key, external_ref=ext,
                     payload_sha256=payload, outcome="FOUND", document_id=data.document_id if manual else None)
            _transition(db, ctx, s, p, "SUBMITTED", "REGISTRY_SUBMISSION_RECONCILED", "Registry has the submission", external_submission_id=ext)
        else:
            ra.event(db, a, "RECONCILED", principal.user_id, submission_id=s.id, idempotency_key=s.idempotency_key, payload_sha256=payload,
                     outcome="NOT_FOUND", document_id=data.document_id if manual else None)
            _transition(db, ctx, s, p, "FROZEN", "REGISTRY_SUBMISSION_RECONCILED", "Registry confirmed it has no such submission")
        ra.audit(db, ctx, "REGISTRY_RECONCILIATION_PERFORMED", "registry_submission", s.id, p.organization_id,
                 {"outcome": "FOUND" if found else "NOT_FOUND", "external_submission_id": s.external_submission_id})
        db.commit()
        return s
    if s.status == "SUBMITTED" and not manual:
        st = impl.get_submission_status(ref, external_submission_id=s.external_submission_id, idempotency_key=s.idempotency_key)
        ra.event(db, a, "STATUS_QUERIED", principal.user_id, submission_id=s.id, external_ref=s.external_submission_id,
                 payload_sha256=st.payload_sha256, outcome=st.status, note=st.reason)
        if st.status in ("ACCEPTED", "REJECTED"):
            s.response_payload_sha256, s.response_reason, s.response_by, s.response_at = st.payload_sha256, st.reason, principal.user_id, utcnow()
            if st.status == "REJECTED" and not s.response_reason:
                s.response_reason = "Rejected by the registry (no reason returned)"
            ra.event(db, a, "RESPONSE_RECORDED", principal.user_id, submission_id=s.id, outcome=st.status, payload_sha256=st.payload_sha256)
            _transition(db, ctx, s, p, st.status, f"REGISTRY_SUBMISSION_{st.status}", st.reason, response_payload_sha256=st.payload_sha256)
        db.commit()
        return s
    if s.status == "ACCEPTED":
        mismatches = issuance_mismatches(db, s, impl, ref) if not manual else ([] if data.outcome == "MATCH" else [data.note or "mismatch"])
        kind = "MISMATCH" if mismatches else "RECONCILED"
        ra.event(db, a, kind, principal.user_id, submission_id=s.id, outcome="ISSUANCES", note="; ".join(mismatches)[:2000] or None,
                 document_id=data.document_id if manual else None)
        ra.audit(db, ctx, "REGISTRY_RECONCILIATION_MISMATCH" if mismatches else "REGISTRY_RECONCILIATION_PERFORMED", "registry_submission", s.id,
                 p.organization_id, {"mismatches": mismatches})
        db.commit()
        return s
    raise Conflict(f"Nothing to reconcile for a {s.status} submission.", error_code="NOTHING_TO_RECONCILE")


def issuance_mismatches(db: Session, s: RegistrySubmission, impl: RegistryAdapter, ref: Any) -> list[str]:
    reg = db.get(RegistryProjectRegistration, s.registration_id)
    assert reg is not None and reg.external_project_id is not None
    external = {i.external_issuance_id: i for i in impl.get_issuances(ref, reg.external_project_id)}
    local = {i.external_issuance_id: i for i in db.scalars(select(CreditIssuance).where(CreditIssuance.registry_submission_id == s.id,
                                                                                       CreditIssuance.status == "CONFIRMED")).all()}
    out = [f"{k}: issued at the registry, not recorded" for k in external if k not in local]
    out += [f"{k}: recorded, unknown to the registry" for k in local if k not in external]
    out += [f"{k}: quantity {local[k].quantity} ≠ registry {external[k].quantity}" for k in local
            if k in external and Decimal(external[k].quantity) != local[k].quantity]
    return out


# ---------------------------------------------------------------- views
def submissions(db: Session, principal: Principal, project_id: uuid.UUID, period_id: uuid.UUID | None = None) -> list[RegistrySubmission]:
    ra.project_for(db, principal, project_id)
    stmt = select(RegistrySubmission).where(RegistrySubmission.project_id == project_id)
    if period_id:
        stmt = stmt.where(RegistrySubmission.monitoring_period_id == period_id)
    return list(db.scalars(stmt.order_by(RegistrySubmission.created_at)).all())


def events_of(db: Session, s: RegistrySubmission) -> list[RegistryEvent]:
    return list(db.scalars(select(RegistryEvent).where(RegistryEvent.submission_id == s.id).order_by(RegistryEvent.occurred_at)).all())


def registry_projects(db: Session, principal: Principal) -> list[Project]:
    orgs = visible_org_ids(principal, *ra.REGISTRY_VISIBLE)
    stmt = select(Project).where(Project.status.in_(("CALCULATED", "VERIFICATION", "VERIFIED", "ISSUED", "MONITORING", "CALCULATION_READY")))
    if orgs is not None:
        stmt = stmt.where(Project.organization_id.in_(orgs or {uuid.uuid4()}))
    return list(db.scalars(stmt.order_by(Project.project_code)).all())


def period_view(db: Session, ctx: RequestContext, principal: Principal, project_id: uuid.UUID, period_id: uuid.UUID) -> dict[str, Any]:
    p = ra.project_for(db, principal, project_id)
    mp = _period(db, p, period_id)
    subs = submissions(db, principal, project_id, period_id)
    for s in subs:
        check_source(db, ctx, s)
    from app.services import calculation_readiness as cr
    run = cr.current_run(db, period_id)
    d = current_decision(db, ctx, period_id)
    accts = [a for a in accounts(db, principal, p.organization_id) if a.status == "ACTIVE"]
    eligible = []
    for a in accts:
        b, w, _ = eligibility(db, ctx, p, mp, a)
        eligible.append({"account": a, "blockers": b, "warnings": w})
    if not accts:
        eligible.append({"account": None, "blockers": eligibility(db, ctx, p, mp, None)[0], "warnings": []})
    issuances = list(db.scalars(select(CreditIssuance).where(CreditIssuance.monitoring_period_id == period_id)
                                .order_by(CreditIssuance.recorded_at)).all())
    batches = list(db.scalars(select(CreditBatch).where(CreditBatch.monitoring_period_id == period_id, CreditBatch.status == "ISSUED")
                              .order_by(CreditBatch.batch_code)).all())
    status = "NONE"
    if any(i.status == "CONFIRMED" for i in issuances):
        status = "ISSUED"
    elif subs:
        status = subs[-1].status
    return {"project": p, "period": mp, "run": run, "decision": d, "submissions": subs, "issuances": issuances, "batches": batches,
            "eligibility": eligible, "registry_status": status, "registrations": registrations(db, principal, project_id),
            "can_manage": principal.can_in_org(P.REGISTRY_MANAGE, p.organization_id),
            "can_confirm": principal.can_in_org(P.REGISTRY_CONFIRM, p.organization_id)}
