"""Phase 9A registry API (`/api/v1/registry`) — project-organization side only (D2: registries are external counterparties; there is no
registry portal). Registry accounts, project registrations (recorded external facts), registry submissions with a frozen snapshot,
registry responses and reconciliation, and registry-stated issuances confirmed by a second person. No endpoint accepts a calculated or
VVB-verified quantity as an issuance quantity; no inventory, transfer or retirement endpoint exists."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile, status

from app.api.deps import DB, Ctx, read_upload, require_any
from app.schemas.lab import DocumentRef
from app.schemas.registry import (
    AccountConfigIn,
    AccountIn,
    AccountOut,
    CancelIn,
    CorrectionIn,
    EventOut,
    IssuanceIn,
    IssuanceOut,
    NoteIn,
    OrgRef,
    PeriodRegistryView,
    QueryIn,
    ReasonIn,
    ReconcileIn,
    RecordSubmittedIn,
    RegisteredIn,
    RegistrationIn,
    RegistrationOut,
    RegistrationRejectedIn,
    RegistryProjectOut,
    ResponseIn,
    SubmissionDetail,
    SubmissionIn,
    SubmissionOut,
    WithdrawIn,
)
from app.security.permissions import P
from app.security.principal import Principal
from app.services import credit_issuance as ci
from app.services import registry_access as ra
from app.services import registry_mappers as rm
from app.services import registry_service as rs
from app.services.mrv_service import periods as periods_of

router = APIRouter(prefix="/registry", tags=["registry — submission & issuance (project side)"])

Reader = Annotated[Principal, Depends(require_any(*ra.REGISTRY_VISIBLE))]
Manager = Annotated[Principal, Depends(require_any(P.REGISTRY_MANAGE))]
Confirmer = Annotated[Principal, Depends(require_any(P.REGISTRY_CONFIRM))]
IdemKey = Annotated[str | None, Header(alias="Idempotency-Key", max_length=80)]


# ---------------------------------------------------------------- registries, projects, accounts
@router.get("/organizations", response_model=list[OrgRef], summary="Active registry organizations (external counterparties) of an environment")
def organizations(principal: Reader, db: DB, environment: str = "LIVE") -> list[OrgRef]:
    return [OrgRef(id=o.id, code=o.code, name=o.name) for o in rs.registries(db, environment)]


@router.get("/projects", response_model=list[RegistryProjectOut], summary="Projects visible for registry work (registry.read only)")
def projects(principal: Reader, db: DB) -> list[RegistryProjectOut]:
    return [RegistryProjectOut(id=p.id, project_code=p.project_code, name=p.name, status=p.status, environment=p.environment,
                               periods=[{"id": str(mp.id), "number": mp.period_number, "name": mp.name, "status": mp.status}
                                        for mp in periods_of(db, p.id)])
            for p in rs.registry_projects(db, principal)]


@router.get("/accounts", response_model=list[AccountOut])
def list_accounts(principal: Reader, db: DB, organization_id: uuid.UUID | None = None) -> list[AccountOut]:
    return [rm.account_out(db, a) for a in rs.accounts(db, principal, organization_id)]


@router.post("/accounts", response_model=AccountOut, status_code=status.HTTP_201_CREATED,
             summary="Record the organization's account at a registry (adapter MANUAL by default; unit equivalence and checklist are explicit)")
def create_account(body: AccountIn, principal: Manager, db: DB, ctx: Ctx) -> AccountOut:
    return rm.account_out(db, rs.create_account(db, ctx, principal, body))


@router.post("/accounts/{account_id}/configure", response_model=AccountOut,
             summary="Set the explicit unit equivalence (D5) and the registry document checklist (D16)")
def configure_account(account_id: uuid.UUID, body: AccountConfigIn, principal: Manager, db: DB, ctx: Ctx) -> AccountOut:
    return rm.account_out(db, rs.configure_account(db, ctx, principal, account_id, body))


@router.post("/accounts/{account_id}/close", response_model=AccountOut)
def close_account(account_id: uuid.UUID, body: ReasonIn, principal: Manager, db: DB, ctx: Ctx) -> AccountOut:
    return rm.account_out(db, rs.close_account(db, ctx, principal, account_id, body.reason))


# ---------------------------------------------------------------- project registrations (D3)
@router.get("/projects/{project_id}/registrations", response_model=list[RegistrationOut])
def list_registrations(project_id: uuid.UUID, principal: Reader, db: DB) -> list[RegistrationOut]:
    return [rm.registration_out(db, r) for r in rs.registrations(db, principal, project_id)]


@router.post("/projects/{project_id}/registrations", response_model=RegistrationOut, status_code=status.HTTP_201_CREATED)
def create_registration(project_id: uuid.UUID, body: RegistrationIn, principal: Manager, db: DB, ctx: Ctx) -> RegistrationOut:
    return rm.registration_out(db, rs.create_registration(db, ctx, principal, project_id, body.registry_account_id, body.notes))


@router.post("/registrations/{registration_id}/documents", response_model=DocumentRef, status_code=status.HTTP_201_CREATED,
             summary="Attach registry evidence (REGISTRY_RESPONSE, PDF) to a registration")
def registration_document(registration_id: uuid.UUID, principal: Manager, db: DB, ctx: Ctx, file: Annotated[UploadFile, File()],
                          title: Annotated[str | None, Form(max_length=200)] = None) -> DocumentRef:
    d = rs.upload_document(db, ctx, principal, ra.REGISTRATION_ENTITY, registration_id, "REGISTRY_RESPONSE", file.filename, read_upload(file), title)
    return DocumentRef(document_id=d.id, category=d.category, title=d.title, file_name=None, sha256=None, uploaded_at=d.created_at)


@router.post("/registrations/{registration_id}/record-registered", response_model=RegistrationOut,
             summary="Record the registry's registration (external project ID + evidence) — the platform does not register projects")
def record_registered(registration_id: uuid.UUID, body: RegisteredIn, principal: Manager, db: DB, ctx: Ctx) -> RegistrationOut:
    return rm.registration_out(db, rs.record_registered(db, ctx, principal, registration_id, body.external_project_id, body.registered_on,
                                                       body.document_id, body.note))


@router.post("/registrations/{registration_id}/record-rejected", response_model=RegistrationOut)
def record_rejected(registration_id: uuid.UUID, body: RegistrationRejectedIn, principal: Manager, db: DB, ctx: Ctx) -> RegistrationOut:
    return rm.registration_out(db, rs.record_registration_rejected(db, ctx, principal, registration_id, body.reason, body.document_id))


# ---------------------------------------------------------------- per-period view and submissions
@router.get("/projects/{project_id}/periods/{period_id}", response_model=PeriodRegistryView,
            summary="Registry panel of one monitoring period: calculated / VVB-stated / registry-issued quantities kept apart")
def period_view(project_id: uuid.UUID, period_id: uuid.UUID, principal: Reader, db: DB, ctx: Ctx) -> PeriodRegistryView:
    return rm.period_view_out(db, principal, rs.period_view(db, ctx, principal, project_id, period_id))


@router.post("/projects/{project_id}/submissions", response_model=SubmissionOut, status_code=status.HTTP_201_CREATED,
             summary="Create a registry submission (DRAFT) for one period's CURRENT VERIFIED VVB decision; optional Idempotency-Key")
def create_submission(project_id: uuid.UUID, body: SubmissionIn, principal: Manager, db: DB, ctx: Ctx, key: IdemKey = None) -> SubmissionOut:
    return rm.submission_out(db, rs.create_submission(db, ctx, principal, project_id, body.monitoring_period_id, body.registry_account_id,
                                                      body.previous_submission_id, key))


@router.get("/submissions/{submission_id}", response_model=SubmissionDetail)
def get_submission(submission_id: uuid.UUID, principal: Reader, db: DB, ctx: Ctx) -> SubmissionDetail:
    s, _ = ra.submission_for(db, principal, submission_id)
    rs.check_source(db, ctx, s)
    return rm.submission_detail(db, principal, s)


@router.get("/submissions/{submission_id}/snapshot", summary="The frozen registry-submission-v1 snapshot and its SHA-256")
def snapshot(submission_id: uuid.UUID, principal: Reader, db: DB) -> dict:
    s, _ = ra.submission_for(db, principal, submission_id)
    import json
    return {"submission_code": s.submission_code, "snapshot_sha256": s.snapshot_sha256, "snapshot": json.loads(s.snapshot) if s.snapshot else None}


@router.get("/submissions/{submission_id}/events", response_model=list[EventOut])
def events(submission_id: uuid.UUID, principal: Reader, db: DB) -> list[EventOut]:
    s, _ = ra.submission_for(db, principal, submission_id)
    evs = rs.events_of(db, s)
    names = rm._names(db, {e.actor_id for e in evs})
    return [rm.event_out(names, e) for e in evs]


@router.post("/submissions/{submission_id}/documents", response_model=DocumentRef, status_code=status.HTTP_201_CREATED,
             summary="Attach a registry document (PDF): REGISTRY_SUBMISSION (before freeze, optionally for a checklist item), REGISTRY_RESPONSE or "
                     "ISSUANCE_STATEMENT")
def submission_document(submission_id: uuid.UUID, principal: Manager, db: DB, ctx: Ctx, file: Annotated[UploadFile, File()],
                        category: Annotated[str, Form(max_length=30)], title: Annotated[str | None, Form(max_length=200)] = None,
                        checklist_item: Annotated[str | None, Form(max_length=60)] = None) -> DocumentRef:
    d = rs.upload_document(db, ctx, principal, ra.SUBMISSION_ENTITY, submission_id, category, file.filename, read_upload(file), title,
                           checklist_item)
    return DocumentRef(document_id=d.id, category=d.category, title=d.title, file_name=None, sha256=None, uploaded_at=d.created_at)


@router.post("/submissions/{submission_id}/freeze", response_model=SubmissionOut, summary="Re-check eligibility and freeze the snapshot")
def freeze(submission_id: uuid.UUID, principal: Manager, db: DB, ctx: Ctx) -> SubmissionOut:
    return rm.submission_out(db, rs.freeze(db, ctx, principal, submission_id))


@router.post("/submissions/{submission_id}/submit", response_model=SubmissionOut,
             summary="Send through the account's registry API adapter (MANUAL accounts: MANUAL_ACTION_REQUIRED)")
def submit(submission_id: uuid.UUID, principal: Manager, db: DB, ctx: Ctx) -> SubmissionOut:
    return rm.submission_out(db, rs.submit(db, ctx, principal, submission_id))


@router.post("/submissions/{submission_id}/record-submitted", response_model=SubmissionOut,
             summary="Manual: record the registry's submission reference with its receipt (REGISTRY_RESPONSE)")
def record_submitted(submission_id: uuid.UUID, body: RecordSubmittedIn, principal: Manager, db: DB, ctx: Ctx) -> SubmissionOut:
    return rm.submission_out(db, rs.record_submitted(db, ctx, principal, submission_id, body.external_submission_id, body.document_id, body.note))


@router.post("/submissions/{submission_id}/record-query", response_model=EventOut, summary="Record a registry query / clarification request")
def record_query(submission_id: uuid.UUID, body: QueryIn, principal: Manager, db: DB, ctx: Ctx) -> EventOut:
    e = rs.record_query(db, ctx, principal, submission_id, body.note, body.document_id)
    return rm.event_out(rm._names(db, {e.actor_id}), e)


@router.post("/submissions/{submission_id}/record-response", response_model=SubmissionOut,
             summary="Record the registry's acceptance or rejection with its evidence (a rejection never changes the verification)")
def record_response(submission_id: uuid.UUID, body: ResponseIn, principal: Manager, db: DB, ctx: Ctx) -> SubmissionOut:
    return rm.submission_out(db, rs.record_response(db, ctx, principal, submission_id, body.outcome, body.document_id, body.reason,
                                                    body.external_response_ref))


@router.post("/submissions/{submission_id}/withdraw", response_model=SubmissionOut)
def withdraw(submission_id: uuid.UUID, body: WithdrawIn, principal: Manager, db: DB, ctx: Ctx) -> SubmissionOut:
    return rm.submission_out(db, rs.withdraw(db, ctx, principal, submission_id, body.reason, body.document_id))


@router.post("/submissions/{submission_id}/cancel", response_model=SubmissionOut, summary="Cancel an unsent (DRAFT / FROZEN) submission")
def cancel(submission_id: uuid.UUID, body: ReasonIn, principal: Manager, db: DB, ctx: Ctx) -> SubmissionOut:
    return rm.submission_out(db, rs.cancel(db, ctx, principal, submission_id, body.reason))


@router.post("/submissions/{submission_id}/reconcile", response_model=SubmissionOut,
             summary="Resolve an unconfirmed submission, query its status or compare issuances (never re-sends automatically)")
def reconcile(submission_id: uuid.UUID, principal: Manager, db: DB, ctx: Ctx, body: ReconcileIn | None = None) -> SubmissionOut:
    return rm.submission_out(db, rs.reconcile(db, ctx, principal, submission_id, body))


# ---------------------------------------------------------------- issuances
@router.post("/submissions/{submission_id}/issuances", response_model=IssuanceOut, status_code=status.HTTP_201_CREATED,
             summary="Record a registry-stated issuance (batches + serial ranges as supplied, ISSUANCE_STATEMENT evidence); optional Idempotency-Key")
def record_issuance(submission_id: uuid.UUID, body: IssuanceIn, principal: Manager, db: DB, ctx: Ctx, key: IdemKey = None) -> IssuanceOut:
    return rm.issuance_out(db, principal, ci.record(db, ctx, principal, submission_id, body, request_key=key))


@router.post("/issuances/{issuance_id}/confirm", response_model=IssuanceOut,
             summary="Independently confirm a recorded issuance (registry.confirm; never the recorder)")
def confirm_issuance(issuance_id: uuid.UUID, principal: Confirmer, db: DB, ctx: Ctx, body: NoteIn | None = None) -> IssuanceOut:
    return rm.issuance_out(db, principal, ci.confirm(db, ctx, principal, issuance_id, body.note if body else None))


@router.post("/issuances/{issuance_id}/void", response_model=IssuanceOut, summary="Void an unconfirmed (RECORDED) issuance entry")
def void_issuance(issuance_id: uuid.UUID, body: ReasonIn, principal: Manager, db: DB, ctx: Ctx) -> IssuanceOut:
    return rm.issuance_out(db, principal, ci.void(db, ctx, principal, issuance_id, body.reason))


@router.post("/issuances/{issuance_id}/cancel", response_model=IssuanceOut, summary="Record the registry's cancellation of a confirmed issuance")
def cancel_issuance(issuance_id: uuid.UUID, body: CancelIn, principal: Manager, db: DB, ctx: Ctx) -> IssuanceOut:
    return rm.issuance_out(db, principal, ci.cancel(db, ctx, principal, issuance_id, body.reason, body.document_id))


@router.post("/issuances/{issuance_id}/correct", response_model=IssuanceOut, status_code=status.HTTP_201_CREATED,
             summary="Record a correcting issuance (new record referencing the original; the original stays as history)")
def correct_issuance(issuance_id: uuid.UUID, body: CorrectionIn, principal: Manager, db: DB, ctx: Ctx) -> IssuanceOut:
    data = IssuanceIn(**body.model_dump(exclude={"reason"}))
    return rm.issuance_out(db, principal, ci.correct(db, ctx, principal, issuance_id, data, body.reason))
