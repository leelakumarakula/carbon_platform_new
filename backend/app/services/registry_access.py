"""Phase 9A access (D2, D18). Registries are external counterparties with no users on the platform: every registry account,
registration, submission, event, issuance and batch is owned by — and scoped to — the project's organization. Out-of-scope records are 404;
visible but forbidden actions are 403 (the platform convention). Documents attached to registry records are immutable after upload.
"""
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.audit.service import record
from app.core.context import RequestContext
from app.core.errors import Conflict, NotFound, PermissionDenied
from app.integrations.registry import ADAPTERS, AccountRef, RegistryAdapter
from app.models import (
    CreditBatch,
    CreditIssuance,
    Organization,
    Project,
    RegistryAccount,
    RegistryEvent,
    RegistryProjectRegistration,
    RegistrySubmission,
    WorkflowEvent,
)
from app.repositories import projects as project_repo
from app.security.permissions import P
from app.security.principal import Principal
from app.services import document_service

REGISTRY_VISIBLE = (P.REGISTRY_READ, P.REGISTRY_MANAGE, P.REGISTRY_CONFIRM)
REGISTRATION_ENTITY = "registry_registration"
SUBMISSION_ENTITY = "registry_submission"


def _nf(what: str, code: str) -> NotFound:
    return NotFound(f"{what} not found.", error_code=code)


def _check(principal: Principal, org_id: uuid.UUID, codes: tuple[str, ...], visible: tuple[str, ...], nf: NotFound) -> None:
    if any(principal.can_in_org(c, org_id) for c in codes):
        return
    if any(principal.can_in_org(c, org_id) for c in visible):
        raise PermissionDenied(details={"required_permission": " or ".join(codes)})
    raise nf


def project_for(db: Session, principal: Principal, project_id: uuid.UUID, *codes: str) -> Project:
    p = project_repo.get(db, project_id)
    nf = _nf("Project", "PROJECT_NOT_FOUND")
    if p is None:
        raise nf
    _check(principal, p.organization_id, codes or (P.REGISTRY_READ,), REGISTRY_VISIBLE, nf)
    return p


def credits_project(db: Session, principal: Principal, project_id: uuid.UUID) -> Project:
    p = project_repo.get(db, project_id)
    nf = _nf("Project", "PROJECT_NOT_FOUND")
    if p is None:
        raise nf
    _check(principal, p.organization_id, (P.CREDITS_READ,), (P.CREDITS_READ, *REGISTRY_VISIBLE), nf)
    return p


def account_for(db: Session, principal: Principal, account_id: uuid.UUID, *codes: str) -> RegistryAccount:
    a = db.get(RegistryAccount, account_id)
    nf = _nf("Registry account", "REGISTRY_ACCOUNT_NOT_FOUND")
    if a is None:
        raise nf
    _check(principal, a.organization_id, codes or (P.REGISTRY_READ,), REGISTRY_VISIBLE, nf)
    return a


def registration_for(db: Session, principal: Principal, registration_id: uuid.UUID, *codes: str
                     ) -> tuple[RegistryProjectRegistration, Project]:
    r = db.get(RegistryProjectRegistration, registration_id)
    nf = _nf("Registry registration", "REGISTRY_REGISTRATION_NOT_FOUND")
    if r is None:
        raise nf
    try:
        return r, project_for(db, principal, r.project_id, *codes)
    except NotFound:
        raise nf from None


def submission_for(db: Session, principal: Principal, submission_id: uuid.UUID, *codes: str) -> tuple[RegistrySubmission, Project]:
    s = db.get(RegistrySubmission, submission_id)
    nf = _nf("Registry submission", "REGISTRY_SUBMISSION_NOT_FOUND")
    if s is None:
        raise nf
    try:
        return s, project_for(db, principal, s.project_id, *codes)
    except NotFound:
        raise nf from None


def issuance_for(db: Session, principal: Principal, issuance_id: uuid.UUID, *codes: str
                 ) -> tuple[CreditIssuance, RegistrySubmission, Project]:
    i = db.get(CreditIssuance, issuance_id)
    nf = _nf("Credit issuance", "CREDIT_ISSUANCE_NOT_FOUND")
    if i is None:
        raise nf
    try:
        s, p = submission_for(db, principal, i.registry_submission_id, *codes)
    except NotFound:
        raise nf from None
    return i, s, p


def batch_for(db: Session, principal: Principal, batch_id: uuid.UUID) -> tuple[CreditBatch, Project]:
    b = db.get(CreditBatch, batch_id)
    nf = _nf("Credit batch", "CREDIT_BATCH_NOT_FOUND")
    if b is None:
        raise nf
    try:
        return b, credits_project(db, principal, b.project_id)
    except NotFound:
        raise nf from None


def registry_org_ok(db: Session, org_id: uuid.UUID, environment: str) -> Organization | None:
    org = db.get(Organization, org_id)
    if org is None or org.org_type != "REGISTRY" or org.status != "ACTIVE" or org.environment != environment:
        return None
    return org


# ---------------------------------------------------------------- adapters (D4)
def adapter_for(account: RegistryAccount, override: RegistryAdapter | None = None) -> RegistryAdapter:
    """The account's adapter from the application registry (MANUAL only). Tests inject their adapter explicitly via `override`."""
    if override is not None:
        return override
    adapter = ADAPTERS.get(account.adapter_code)
    if adapter is None:
        raise Conflict(f"No registry adapter {account.adapter_code!r} is available.", error_code="UNKNOWN_ADAPTER")
    return adapter


def account_ref(db: Session, account: RegistryAccount) -> AccountRef:
    org = db.get(Organization, account.registry_organization_id)
    return AccountRef(registry_code=org.code if org else "", external_account_id=account.external_account_id)


# ---------------------------------------------------------------- audit / workflow / events
def audit(db: Session, ctx: RequestContext, action: str, entity_type: str, entity_id: Any, org_id: uuid.UUID, payload: dict[str, Any],
          reason: str | None = None, old: dict[str, Any] | None = None) -> None:
    record(db, ctx, action, entity_type, entity_id, old, payload, reason, organization_id=org_id)


def workflow(db: Session, ctx: RequestContext, entity_type: str, entity_id: Any, frm: str | None, to: str, reason: str | None) -> None:
    db.add(WorkflowEvent(entity_type=entity_type, entity_id=str(entity_id), from_status=frm, to_status=to, user_id=ctx.user_id, reason=reason,
                         request_id=ctx.request_id))


def event(db: Session, account: RegistryAccount, event_type: str, actor_id: uuid.UUID | None, *, adapter_code: str | None = None,
          **fields: Any) -> RegistryEvent:
    e = RegistryEvent(registry_account_id=account.id, event_type=event_type, actor_id=actor_id, adapter_code=adapter_code or account.adapter_code,
                      environment=account.environment, **fields)
    db.add(e)
    return e


# ---------------------------------------------------------------- documents (immutable after upload, D14)
def document_resolver(entity_cls: Any) -> Any:
    def resolve(db: Session, principal: Principal, entity_id: uuid.UUID, kind: str) -> None:
        nf = NotFound("Document not found.", error_code="DOCUMENT_NOT_FOUND")
        if kind == "manage":
            raise PermissionDenied("Registry documents are immutable; upload a new document instead.", error_code="DOCUMENT_IMMUTABLE")
        rec = db.get(entity_cls, entity_id)
        p = db.get(Project, rec.project_id) if rec is not None else None
        if p is None or not any(principal.can_in_org(c, p.organization_id) for c in (*REGISTRY_VISIBLE, P.CREDITS_READ)):
            raise nf
    return resolve


document_service.register_resolver(REGISTRATION_ENTITY, document_resolver(RegistryProjectRegistration))
document_service.register_resolver(SUBMISSION_ENTITY, document_resolver(RegistrySubmission))
