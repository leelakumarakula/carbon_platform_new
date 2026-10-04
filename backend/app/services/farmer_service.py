"""Farmer onboarding: registration, contacts, KYC, consents, agreements, bank accounts, documents (spec §4.1, §10).

Rules enforced here:
- every status change goes through FARMER_MACHINE with requirement checks; KYC states only via the KYC endpoints
- KYC: raw ID number never stored; duplicate fingerprints are flagged; the person who submitted KYC cannot verify it
- identity fields are locked once KYC is verified
- consents are append-only grants with explicit withdrawal; agreements need a signed document to become SIGNED
- bank account numbers are encrypted; only last-4 is ever returned; the person who added an account cannot verify it
"""
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import record, record_transition, snapshot
from app.core.context import RequestContext
from app.core.errors import Conflict, NotFound, PermissionDenied, ValidationFailed
from app.models import (
    Farmer,
    FarmerAgreement,
    FarmerBankAccount,
    FarmerConsent,
    FarmerContact,
    FarmerDocument,
    Organization,
    User,
)
from app.models.base import utcnow
from app.models.documents import DocumentCategory
from app.repositories import farmers as repo
from app.repositories.sequences import next_code
from app.schemas.common import PageParams
from app.schemas.farmers import (
    AgreementCreate,
    BankAccountIn,
    ChecklistItem,
    ConsentIn,
    ContactIn,
    FarmerCreate,
    FarmerUpdate,
    TransitionReadiness,
)
from app.security import crypto
from app.security.permissions import P
from app.security.principal import Principal
from app.services import access, consent_service, document_service
from app.services.notification_service import notify
from app.services.workflows import AGREEMENT_MACHINE, BANK_ACCOUNT_MACHINE, FARMER_MACHINE

ENTITY = "farmer"
MANAGING_ORG_TYPES = {"PROJECT_DEVELOPER", "FIELD_PARTNER", "FARMER_GROUP"}
IDENTITY_FIELDS = {"full_name", "date_of_birth"}
PROFILE_FIELDS = ("farmer_code", "full_name", "gender", "date_of_birth", "preferred_language", "participation_type",
                  "group_organization_id", "address_line", "village", "sub_district", "district", "state", "postal_code",
                  "country", "status", "organization_id", "environment")
FARMER_DOC_CATEGORIES = {c.value for c in DocumentCategory} - {DocumentCategory.FIELD_PHOTO.value,
                                                                  DocumentCategory.GEOSPATIAL_FILE.value,
                                                                  DocumentCategory.PROJECT_DESIGN.value,
                                                                  DocumentCategory.CARBON_RIGHTS.value,
                                                                  DocumentCategory.BASELINE_DATA.value,
                                                                  DocumentCategory.METHODOLOGY_DOCUMENT.value}


def _not_found() -> NotFound:
    return NotFound("Farmer not found.", error_code="FARMER_NOT_FOUND")


# ---------------------------------------------------------------- access
def get_farmer(db: Session, principal: Principal, farmer_id: uuid.UUID, code: str = P.FARMERS_READ) -> Farmer:
    f = repo.get(db, farmer_id)
    if f is None:
        raise _not_found()
    access.require(principal, code, f.organization_id, f.user_id, _not_found())
    return f


def _document_resolver(db: Session, principal: Principal, farmer_id: uuid.UUID, kind: str) -> None:
    f = repo.get(db, farmer_id)
    if f is None:
        raise NotFound("Document not found.", error_code="DOCUMENT_NOT_FOUND")
    if kind == "read":
        access.require(principal, P.FARMERS_READ, f.organization_id, f.user_id, NotFound("Document not found.", error_code="DOCUMENT_NOT_FOUND"))
    elif kind == "manage":
        access.require(principal, P.FARMERS_MANAGE, f.organization_id, f.user_id, NotFound("Document not found.", error_code="DOCUMENT_NOT_FOUND"))
    else:  # restricted (KYC / bank proof): the farmer, their managers, KYC and bank reviewers only
        allowed = any(access.can(principal, c, f.organization_id, f.user_id)
                      for c in (P.FARMERS_MANAGE, P.FARMERS_KYC_VERIFY, P.FARMERS_BANK_MANAGE, P.FARMERS_BANK_VERIFY))
        if not allowed:
            if access.can(principal, P.FARMERS_READ, f.organization_id, f.user_id):
                raise PermissionDenied("This document contains restricted personal data.", error_code="RESTRICTED_DOCUMENT")
            raise NotFound("Document not found.", error_code="DOCUMENT_NOT_FOUND")


document_service.register_resolver(ENTITY, _document_resolver)


@dataclass(frozen=True)
class Capabilities:
    can_manage: bool
    can_verify_kyc: bool
    can_manage_bank: bool
    can_verify_bank: bool
    is_self: bool


def capabilities(principal: Principal, f: Farmer) -> Capabilities:
    return Capabilities(
        can_manage=access.can(principal, P.FARMERS_MANAGE, f.organization_id, f.user_id),
        can_verify_kyc=principal.can_in_org(P.FARMERS_KYC_VERIFY, f.organization_id),
        can_manage_bank=access.can(principal, P.FARMERS_BANK_MANAGE, f.organization_id, f.user_id),
        can_verify_bank=principal.can_in_org(P.FARMERS_BANK_VERIFY, f.organization_id),
        is_self=access.is_self(principal, f.user_id),
    )


def list_farmers(db: Session, principal: Principal, params: PageParams, **filters: object) -> tuple[list[Farmer], int]:
    scope, include_self = access.read_scope(principal, P.FARMERS_READ)
    org = filters.get("organization_id")
    if scope is not None and org is not None and org not in scope:
        raise PermissionDenied(details={"organization_id": str(org)})
    return repo.list_farmers(db, params, scope=scope, include_self=include_self, user_id=principal.user_id, **filters)  # type: ignore[arg-type]


# ---------------------------------------------------------------- registration
def create_farmer(db: Session, ctx: RequestContext, principal: Principal, data: FarmerCreate) -> Farmer:
    principal.require_in_org(P.FARMERS_MANAGE, data.organization_id)
    org = db.get(Organization, data.organization_id)
    if org is None or org.status != "ACTIVE":
        raise ValidationFailed("Choose an active organization.", error_code="ORGANIZATION_INACTIVE")
    if org.org_type not in MANAGING_ORG_TYPES:
        raise ValidationFailed("Farmers are managed by a project developer, field partner or farmer group.",
                               error_code="ORGANIZATION_TYPE_NOT_ALLOWED")
    _check_group(db, data.group_organization_id, data.participation_type, org.environment)
    f = Farmer(farmer_code=next_code(db, "farmer", date.today().year), organization_id=org.id, environment=org.environment,
               registered_by=ctx.user_id, **data.model_dump(exclude={"organization_id", "primary_phone", "email"}))
    db.add(f)
    db.flush()
    if data.primary_phone:
        db.add(FarmerContact(farmer_id=f.id, contact_type="PHONE", value=data.primary_phone, is_primary=True, created_by=ctx.user_id))
    if data.email:
        db.add(FarmerContact(farmer_id=f.id, contact_type="EMAIL", value=data.email, is_primary=True, created_by=ctx.user_id))
    record(db, ctx, "FARMER_CREATED", ENTITY, f.id, None, snapshot(f, PROFILE_FIELDS), organization_id=f.organization_id)
    db.commit()
    return repo.get(db, f.id)  # type: ignore[return-value]


def _check_group(db: Session, group_id: uuid.UUID | None, participation: str | None, environment: str) -> None:
    if participation == "GROUP_MEMBER" and group_id is None:
        raise ValidationFailed("Group members need a farmer group organization.", error_code="GROUP_REQUIRED")
    if group_id is not None:
        g = db.get(Organization, group_id)
        if g is None or g.org_type != "FARMER_GROUP" or g.environment != environment:
            raise ValidationFailed("The farmer group must be an existing FARMER_GROUP organization.", error_code="INVALID_GROUP")


def update_farmer(db: Session, ctx: RequestContext, principal: Principal, farmer_id: uuid.UUID, data: FarmerUpdate) -> Farmer:
    f = get_farmer(db, principal, farmer_id, P.FARMERS_MANAGE)
    changes = data.model_dump(exclude_unset=True)
    if f.status in ("KYC_VERIFIED", "ACTIVE", "SUSPENDED") and IDENTITY_FIELDS & {k for k, v in changes.items() if getattr(f, k) != v}:
        raise Conflict("Name and date of birth are locked after KYC verification.", error_code="IDENTITY_LOCKED")
    if "group_organization_id" in changes or "participation_type" in changes:
        _check_group(db, changes.get("group_organization_id", f.group_organization_id),
                     changes.get("participation_type", f.participation_type), f.environment)
    old = {k: getattr(f, k) for k in changes}
    for k, v in changes.items():
        setattr(f, k, v)
    if old != changes:
        record(db, ctx, "FARMER_UPDATED", ENTITY, f.id, old, changes, organization_id=f.organization_id)
    db.commit()
    return repo.get(db, f.id)  # type: ignore[return-value]


# ---------------------------------------------------------------- readiness / status
def _active_phone(f: Farmer) -> bool:
    return any(c.is_active and c.contact_type in ("PHONE", "ALTERNATE_PHONE") for c in f.contacts)


def _granted_definitions(f: Farmer) -> set[uuid.UUID]:
    return {c.consent_definition_id for c in f.consents if c.status == "GRANTED" and c.consent_definition_id}


def readiness(db: Session, f: Farmer) -> list[TransitionReadiness]:
    out: list[TransitionReadiness] = []
    for target in sorted(FARMER_MACHINE.allowed_from(f.status)):
        items: list[ChecklistItem] = []
        if target == "REGISTERED":
            items = [ChecklistItem(key="name", label="Full name recorded", done=bool(f.full_name)),
                     ChecklistItem(key="location", label="Village or district and country recorded",
                                   done=bool((f.village or f.district) and f.country)),
                     ChecklistItem(key="phone", label="An active phone contact", done=_active_phone(f))]
        elif target == "KYC_PENDING":
            items = [ChecklistItem(key="kyc", label="Identity type, number and KYC document submitted", done=f.kyc_id_hash is not None)]
        elif target == "KYC_VERIFIED":
            items = [ChecklistItem(key="kyc_review", label="KYC reviewed by someone other than the submitter", done=False)]
        elif target == "ACTIVE" and f.status == "KYC_VERIFIED":
            # Driven by the active consent definitions marked required_for_activation (decision D3): the farmer
            # must have granted the *current* version of each.
            granted = _granted_definitions(f)
            items = [ChecklistItem(key=f"consent_{d.consent_type.lower()}", label=f"{d.title} consent granted (version {d.version})",
                                   done=d.id in granted) for d in consent_service.required_for_activation(db)]
        out.append(TransitionReadiness(target=target, ready=all(i.done for i in items if i.required), items=items))
    return out


def change_status(db: Session, ctx: RequestContext, principal: Principal, farmer_id: uuid.UUID, target: str, reason: str) -> Farmer:
    f = get_farmer(db, principal, farmer_id, P.FARMERS_MANAGE)
    if target == "SUSPENDED" or (target == "ACTIVE" and f.status == "SUSPENDED"):
        principal.require_in_org(P.FARMERS_MANAGE, f.organization_id)  # farmers cannot suspend/reinstate themselves
    FARMER_MACHINE.assert_transition(f.status, target)
    if target in ("KYC_PENDING", "KYC_VERIFIED") or f.status == "KYC_PENDING":
        # KYC moves only through POST /kyc and the independent POST /kyc/decision (separation of duties)
        raise Conflict("KYC is submitted and decided on the KYC tab, not by a status change.", error_code="USE_KYC_WORKFLOW")
    ready = next((r for r in readiness(db, f) if r.target == target), None)
    if ready and not ready.ready:
        missing = [i.label for i in ready.items if i.required and not i.done]
        raise Conflict(f"Cannot move to {target} yet: " + "; ".join(missing) + ".", error_code="REQUIREMENTS_NOT_MET",
                       details={"missing": missing})
    record_transition(db, ctx, FARMER_MACHINE, f.id, f.status, target, "FARMER_STATUS_CHANGED", reason, f.organization_id)
    f.status = target
    db.commit()
    return repo.get(db, f.id)  # type: ignore[return-value]


# ---------------------------------------------------------------- KYC
def submit_kyc(db: Session, ctx: RequestContext, principal: Principal, farmer_id: uuid.UUID, id_type: str, id_number: str,
               document_id: uuid.UUID) -> Farmer:
    f = get_farmer(db, principal, farmer_id, P.FARMERS_MANAGE)
    FARMER_MACHINE.assert_transition(f.status, "KYC_PENDING")
    document_service.require_attached(db, document_id, ENTITY, f.id, {DocumentCategory.KYC_ID.value})
    if len(crypto.normalise_identifier(id_number)) < 4:
        raise ValidationFailed("The identity number is too short.", error_code="INVALID_ID_NUMBER")
    fp = crypto.fingerprint(id_number, f"kyc:{id_type}")
    duplicates = repo.kyc_duplicates(db, fp, f.environment, f.id)
    f.kyc_id_type, f.kyc_id_last4, f.kyc_id_hash = id_type, crypto.last4(id_number), fp
    f.kyc_document_id, f.kyc_possible_duplicate = document_id, bool(duplicates)
    f.kyc_submitted_at, f.kyc_submitted_by, f.kyc_verified_at, f.kyc_verified_by = utcnow(), ctx.user_id, None, None
    record_transition(db, ctx, FARMER_MACHINE, f.id, f.status, "KYC_PENDING", "FARMER_KYC_SUBMITTED",
                      "KYC submitted", f.organization_id)
    record(db, ctx, "FARMER_KYC_SUBMITTED", ENTITY, f.id, None,
           {"id_type": id_type, "id_last4": f.kyc_id_last4, "document_id": document_id,
            "possible_duplicate_of": [str(d) for d in duplicates]}, organization_id=f.organization_id)
    f.status = "KYC_PENDING"
    db.commit()
    return repo.get(db, f.id)  # type: ignore[return-value]


def decide_kyc(db: Session, ctx: RequestContext, principal: Principal, farmer_id: uuid.UUID, decision: str, notes: str,
               acknowledge_duplicate: bool) -> Farmer:
    f = get_farmer(db, principal, farmer_id, P.FARMERS_READ)
    principal.require_in_org(P.FARMERS_KYC_VERIFY, f.organization_id)
    if f.status != "KYC_PENDING":
        raise Conflict("There is no KYC submission waiting for review.", error_code="KYC_NOT_PENDING")
    if f.kyc_submitted_by == principal.user_id:
        raise PermissionDenied("You submitted this KYC, so someone else must review it.", error_code="SEPARATION_OF_DUTIES")
    target = "KYC_VERIFIED" if decision == "VERIFIED" else "REGISTERED"
    if decision == "VERIFIED" and f.kyc_possible_duplicate and not acknowledge_duplicate:
        raise Conflict("Another farmer has the same identity number. Review the possible duplicate and confirm.",
                       error_code="DUPLICATE_REVIEW_REQUIRED")
    record_transition(db, ctx, FARMER_MACHINE, f.id, f.status, target,
                      "FARMER_KYC_VERIFIED" if decision == "VERIFIED" else "FARMER_KYC_RETURNED", notes, f.organization_id)
    f.status, f.kyc_notes = target, notes
    if decision == "VERIFIED":
        f.kyc_verified_at, f.kyc_verified_by = utcnow(), principal.user_id
    fd = db.scalars(select(FarmerDocument).where(FarmerDocument.document_id == f.kyc_document_id)).first()
    if fd:
        fd.review_status = "ACCEPTED" if decision == "VERIFIED" else "REJECTED"
        fd.reviewed_by, fd.reviewed_at, fd.review_notes = principal.user_id, utcnow(), notes
    notify(db, [f.user_id, f.kyc_submitted_by], "FARMER_KYC_" + ("VERIFIED" if decision == "VERIFIED" else "RETURNED"),
           f"KYC {'verified' if decision == 'VERIFIED' else 'returned for correction'}: {f.full_name}", notes,
           ENTITY, f.id, f"/farmers/{f.id}")
    db.commit()
    return repo.get(db, f.id)  # type: ignore[return-value]


# ---------------------------------------------------------------- contacts
def add_contact(db: Session, ctx: RequestContext, principal: Principal, farmer_id: uuid.UUID, data: ContactIn) -> Farmer:
    f = get_farmer(db, principal, farmer_id, P.FARMERS_MANAGE)
    if data.is_primary:
        for c in f.contacts:
            if c.contact_type == data.contact_type and c.is_active:
                c.is_primary = False
    c = FarmerContact(farmer_id=f.id, created_by=ctx.user_id, **data.model_dump())
    db.add(c)
    db.flush()
    record(db, ctx, "FARMER_CONTACT_ADDED", ENTITY, f.id, None, {"contact_id": c.id, **data.model_dump()}, organization_id=f.organization_id)
    db.commit()
    return repo.get(db, f.id)  # type: ignore[return-value]


def deactivate_contact(db: Session, ctx: RequestContext, principal: Principal, farmer_id: uuid.UUID, contact_id: uuid.UUID,
                       reason: str) -> Farmer:
    f = get_farmer(db, principal, farmer_id, P.FARMERS_MANAGE)
    c = next((x for x in f.contacts if x.id == contact_id), None)
    if c is None or not c.is_active:
        raise NotFound("Contact not found.", error_code="CONTACT_NOT_FOUND")
    c.is_active, c.is_primary = False, False
    record(db, ctx, "FARMER_CONTACT_DEACTIVATED", ENTITY, f.id, {"contact_id": c.id, "value": c.value}, None, reason,
           organization_id=f.organization_id)
    db.commit()
    return repo.get(db, f.id)  # type: ignore[return-value]


# ---------------------------------------------------------------- consents
def grant_consent(db: Session, ctx: RequestContext, principal: Principal, farmer_id: uuid.UUID, data: ConsentIn) -> Farmer:
    f = get_farmer(db, principal, farmer_id, P.FARMERS_MANAGE)
    definition = consent_service.resolve_for_grant(db, data.consent_type)
    document_service.require_attached(db, data.document_id, ENTITY, f.id, {DocumentCategory.CONSENT_FORM.value})
    current = [c for c in f.consents if c.consent_type == data.consent_type and c.status == "GRANTED"]
    if any(c.consent_definition_id == definition.id for c in current):
        raise Conflict("This consent is already granted. Withdraw it first to record a new version.", error_code="CONSENT_ALREADY_GRANTED")
    for old in current:  # granted against an older definition version: kept, marked superseded by this grant
        old.status = "SUPERSEDED"
        record(db, ctx, "FARMER_CONSENT_SUPERSEDED", ENTITY, f.id, {"consent_id": old.id, "status": "GRANTED"},
               {"status": "SUPERSEDED", "by_definition_version": definition.version}, organization_id=f.organization_id)
    c = FarmerConsent(farmer_id=f.id, captured_by=ctx.user_id, captured_at=utcnow(), consent_definition_id=definition.id,
                      **data.model_dump())
    db.add(c)
    db.flush()
    record(db, ctx, "FARMER_CONSENT_GRANTED", ENTITY, f.id, None,
           {"consent_id": c.id, "consent_definition_id": definition.id, "definition_version": definition.version, **data.model_dump()},
           organization_id=f.organization_id)
    db.commit()
    return repo.get(db, f.id)  # type: ignore[return-value]


def withdraw_consent(db: Session, ctx: RequestContext, principal: Principal, farmer_id: uuid.UUID, consent_id: uuid.UUID,
                     reason: str) -> Farmer:
    f = get_farmer(db, principal, farmer_id, P.FARMERS_MANAGE)
    c = next((x for x in f.consents if x.id == consent_id), None)
    if c is None:
        raise NotFound("Consent not found.", error_code="CONSENT_NOT_FOUND")
    if c.status != "GRANTED":
        raise Conflict("This consent has already been withdrawn.", error_code="CONSENT_ALREADY_WITHDRAWN")
    c.status, c.withdrawn_at, c.withdrawn_by, c.withdrawal_reason = "WITHDRAWN", utcnow(), ctx.user_id, reason
    record(db, ctx, "FARMER_CONSENT_WITHDRAWN", ENTITY, f.id, {"consent_id": c.id, "status": "GRANTED"},
           {"status": "WITHDRAWN"}, reason, organization_id=f.organization_id)
    db.commit()
    return repo.get(db, f.id)  # type: ignore[return-value]


# ---------------------------------------------------------------- agreements
def create_agreement(db: Session, ctx: RequestContext, principal: Principal, farmer_id: uuid.UUID, data: AgreementCreate) -> Farmer:
    f = get_farmer(db, principal, farmer_id, P.FARMERS_MANAGE)
    principal.require_in_org(P.FARMERS_MANAGE, f.organization_id)  # agreements are issued by the organization, not self-service
    if data.effective_from and data.effective_to and data.effective_to < data.effective_from:
        raise ValidationFailed("The end date is before the start date.", error_code="INVALID_DATES")
    cp = data.counterparty_organization_id or f.organization_id
    if cp != f.organization_id:
        principal.require_in_org(P.FARMERS_MANAGE, cp)
    a = FarmerAgreement(farmer_id=f.id, agreement_number=next_code(db, "agreement", date.today().year), created_by=ctx.user_id,
                        counterparty_organization_id=cp, **data.model_dump(exclude={"counterparty_organization_id"}))
    db.add(a)
    db.flush()
    record(db, ctx, "FARMER_AGREEMENT_CREATED", ENTITY, f.id, None,
           {"agreement_id": a.id, "agreement_number": a.agreement_number, **data.model_dump()}, organization_id=f.organization_id)
    db.commit()
    return repo.get(db, f.id)  # type: ignore[return-value]


def sign_agreement(db: Session, ctx: RequestContext, principal: Principal, farmer_id: uuid.UUID, agreement_id: uuid.UUID,
                   signed_document_id: uuid.UUID, signature_method: str) -> Farmer:
    f = get_farmer(db, principal, farmer_id, P.FARMERS_MANAGE)
    a = next((x for x in f.agreements if x.id == agreement_id), None)
    if a is None:
        raise NotFound("Agreement not found.", error_code="AGREEMENT_NOT_FOUND")
    if f.status in ("DRAFT", "SUSPENDED"):
        raise Conflict("Register the farmer (and lift any suspension) before signing agreements.", error_code="FARMER_NOT_READY")
    document_service.require_attached(db, signed_document_id, ENTITY, f.id, {DocumentCategory.AGREEMENT.value})
    record_transition(db, ctx, AGREEMENT_MACHINE, a.id, a.status, "SIGNED", "FARMER_AGREEMENT_SIGNED", "signed copy recorded",
                      f.organization_id)
    a.status, a.signed_at, a.signature_method, a.signed_document_id = "SIGNED", utcnow(), signature_method, signed_document_id
    db.commit()
    return repo.get(db, f.id)  # type: ignore[return-value]


def change_agreement_status(db: Session, ctx: RequestContext, principal: Principal, farmer_id: uuid.UUID, agreement_id: uuid.UUID,
                            target: str, reason: str) -> Farmer:
    f = get_farmer(db, principal, farmer_id, P.FARMERS_READ)
    principal.require_in_org(P.FARMERS_MANAGE, f.organization_id)
    a = next((x for x in f.agreements if x.id == agreement_id), None)
    if a is None:
        raise NotFound("Agreement not found.", error_code="AGREEMENT_NOT_FOUND")
    record_transition(db, ctx, AGREEMENT_MACHINE, a.id, a.status, target, f"FARMER_AGREEMENT_{target}", reason, f.organization_id)
    a.status = target
    db.commit()
    return repo.get(db, f.id)  # type: ignore[return-value]


# ---------------------------------------------------------------- bank accounts
def add_bank_account(db: Session, ctx: RequestContext, principal: Principal, farmer_id: uuid.UUID, data: BankAccountIn) -> Farmer:
    f = get_farmer(db, principal, farmer_id, P.FARMERS_BANK_MANAGE)
    document_service.require_attached(db, data.proof_document_id, ENTITY, f.id, {DocumentCategory.BANK_PROOF.value})
    number = crypto.normalise_identifier(data.account_number)
    fp = crypto.fingerprint(number, "bank")
    if any(b.account_number_hash == fp and b.status != "INACTIVE" for b in f.bank_accounts):
        raise Conflict("This account is already registered for the farmer.", error_code="BANK_ACCOUNT_EXISTS")
    if data.is_primary:
        for b in f.bank_accounts:
            b.is_primary = False
    b = FarmerBankAccount(farmer_id=f.id, account_holder_name=data.account_holder_name, bank_name=data.bank_name,
                          branch_name=data.branch_name, routing_code=data.routing_code, account_number_enc=crypto.encrypt(number),
                          account_last4=crypto.last4(number), account_number_hash=fp, is_primary=data.is_primary,
                          proof_document_id=data.proof_document_id, created_by=ctx.user_id)
    db.add(b)
    db.flush()
    record(db, ctx, "FARMER_BANK_ACCOUNT_ADDED", ENTITY, f.id, None,
           {"bank_account_id": b.id, "bank_name": b.bank_name, "routing_code": b.routing_code, "account_last4": b.account_last4,
            "holder_matches_farmer": b.account_holder_name.casefold() == f.full_name.casefold()}, organization_id=f.organization_id)
    db.commit()
    return repo.get(db, f.id)  # type: ignore[return-value]


def decide_bank_account(db: Session, ctx: RequestContext, principal: Principal, farmer_id: uuid.UUID, account_id: uuid.UUID,
                        decision: str, notes: str) -> Farmer:
    f = get_farmer(db, principal, farmer_id, P.FARMERS_READ)
    principal.require_in_org(P.FARMERS_BANK_VERIFY, f.organization_id)
    b = next((x for x in f.bank_accounts if x.id == account_id), None)
    if b is None:
        raise NotFound("Bank account not found.", error_code="BANK_ACCOUNT_NOT_FOUND")
    if b.created_by == principal.user_id:
        raise PermissionDenied("You added this account, so someone else must verify it.", error_code="SEPARATION_OF_DUTIES")
    record_transition(db, ctx, BANK_ACCOUNT_MACHINE, b.id, b.status, decision, f"FARMER_BANK_ACCOUNT_{decision}", notes, f.organization_id)
    b.status, b.review_notes = decision, notes
    if decision == "VERIFIED":
        b.verified_at, b.verified_by = utcnow(), principal.user_id
    db.commit()
    return repo.get(db, f.id)  # type: ignore[return-value]


def deactivate_bank_account(db: Session, ctx: RequestContext, principal: Principal, farmer_id: uuid.UUID, account_id: uuid.UUID,
                            reason: str) -> Farmer:
    f = get_farmer(db, principal, farmer_id, P.FARMERS_BANK_MANAGE)
    b = next((x for x in f.bank_accounts if x.id == account_id), None)
    if b is None:
        raise NotFound("Bank account not found.", error_code="BANK_ACCOUNT_NOT_FOUND")
    record_transition(db, ctx, BANK_ACCOUNT_MACHINE, b.id, b.status, "INACTIVE", "FARMER_BANK_ACCOUNT_DEACTIVATED", reason,
                      f.organization_id)
    b.status, b.is_primary = "INACTIVE", False
    db.commit()
    return repo.get(db, f.id)  # type: ignore[return-value]


# ---------------------------------------------------------------- documents / user link
def upload_document(db: Session, ctx: RequestContext, principal: Principal, farmer_id: uuid.UUID, category: str, title: str,
                    filename: str | None, data: bytes) -> uuid.UUID:
    f = get_farmer(db, principal, farmer_id, P.FARMERS_MANAGE)
    if category not in FARMER_DOC_CATEGORIES:
        raise ValidationFailed("This document category is not used for farmers.", error_code="INVALID_CATEGORY")
    doc = document_service.create_document(db, ctx, entity_type=ENTITY, entity_id=f.id, organization_id=f.organization_id,
                                           environment=f.environment, category=category, title=title, filename=filename, data=data)
    db.add(FarmerDocument(farmer_id=f.id, document_id=doc.id))
    db.commit()
    return doc.id


def link_user(db: Session, ctx: RequestContext, principal: Principal, farmer_id: uuid.UUID, user_id: uuid.UUID) -> Farmer:
    f = get_farmer(db, principal, farmer_id, P.FARMERS_READ)
    principal.require_in_org(P.FARMERS_MANAGE, f.organization_id)
    user = db.get(User, user_id)
    if user is None or user.status != "ACTIVE":
        raise NotFound("User not found.", error_code="USER_NOT_FOUND")
    if user.environment != f.environment:
        raise Conflict("Demo and live records cannot be mixed.", error_code="ENVIRONMENT_MISMATCH")
    other = repo.get_by_user(db, user_id)
    if other is not None and other.id != f.id:
        raise Conflict("This login is already linked to another farmer.", error_code="USER_ALREADY_LINKED")
    old = f.user_id
    f.user_id = user_id
    record(db, ctx, "FARMER_USER_LINKED", ENTITY, f.id, {"user_id": old}, {"user_id": user_id}, organization_id=f.organization_id)
    db.commit()
    return repo.get(db, f.id)  # type: ignore[return-value]


def my_farmer(db: Session, principal: Principal) -> Farmer:
    f = repo.get_by_user(db, principal.user_id)
    if f is None or not principal.has(P.FARMERS_SELF):
        raise NotFound("No farmer profile is linked to your account.", error_code="FARMER_NOT_FOUND")
    return repo.get(db, f.id)  # type: ignore[return-value]
