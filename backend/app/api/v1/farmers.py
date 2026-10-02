import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from pydantic import BaseModel

from app.api.deps import DB, Ctx, Paging, read_upload, require_any
from app.schemas.common import IdRef, Page, Reason
from app.schemas.farmers import (
    AgreementCreate,
    AgreementSign,
    AgreementStatusChange,
    BankAccountIn,
    BankDecision,
    ConsentIn,
    ContactIn,
    FarmerCreate,
    FarmerOut,
    FarmerStatusChange,
    FarmerSummary,
    FarmerUpdate,
    KycDecision,
    KycSubmit,
    LinkUser,
)
from app.security.permissions import P
from app.security.principal import Principal
from app.services import farmer_service as svc
from app.services.farm_mappers import farmer_out, farmer_summaries

router = APIRouter(prefix="/farmers", tags=["farmers"])
Reader = Annotated[Principal, Depends(require_any(P.FARMERS_READ, P.FARMERS_SELF))]
Manager = Annotated[Principal, Depends(require_any(P.FARMERS_MANAGE, P.FARMERS_SELF))]
KycReviewer = Annotated[Principal, Depends(require_any(P.FARMERS_KYC_VERIFY))]
BankManager = Annotated[Principal, Depends(require_any(P.FARMERS_BANK_MANAGE, P.FARMERS_SELF))]
BankReviewer = Annotated[Principal, Depends(require_any(P.FARMERS_BANK_VERIFY))]


class ReasonBody(BaseModel):
    reason: Reason


@router.get("", response_model=Page[FarmerSummary])
def list_farmers(principal: Reader, db: DB, paging: Paging, search: Annotated[str | None, Query(max_length=100)] = None,
                 status_: Annotated[str | None, Query(alias="status", max_length=20)] = None,
                 organization_id: uuid.UUID | None = None, environment: Literal["LIVE", "DEMO"] | None = None) -> Page[FarmerSummary]:
    rows, total = svc.list_farmers(db, principal, paging, search=search, status=status_, organization_id=organization_id,
                                   environment=environment)
    return Page(items=farmer_summaries(db, rows), total=total, page=paging.page, page_size=paging.page_size)


@router.post("", response_model=FarmerOut, status_code=status.HTTP_201_CREATED)
def create_farmer(body: FarmerCreate, principal: Manager, db: DB, ctx: Ctx) -> FarmerOut:
    return farmer_out(db, principal, svc.create_farmer(db, ctx, principal, body))


@router.get("/me", response_model=FarmerOut, summary="The signed-in farmer's own profile (self-service)")
def my_profile(principal: Reader, db: DB) -> FarmerOut:
    return farmer_out(db, principal, svc.my_farmer(db, principal))


@router.get("/{farmer_id}", response_model=FarmerOut)
def get_farmer(farmer_id: uuid.UUID, principal: Reader, db: DB) -> FarmerOut:
    return farmer_out(db, principal, svc.get_farmer(db, principal, farmer_id))


@router.patch("/{farmer_id}", response_model=FarmerOut)
def update_farmer(farmer_id: uuid.UUID, body: FarmerUpdate, principal: Manager, db: DB, ctx: Ctx) -> FarmerOut:
    return farmer_out(db, principal, svc.update_farmer(db, ctx, principal, farmer_id, body))


@router.post("/{farmer_id}/status", response_model=FarmerOut, summary="REGISTERED / ACTIVE / SUSPENDED via the farmer state machine")
def change_status(farmer_id: uuid.UUID, body: FarmerStatusChange, principal: Manager, db: DB, ctx: Ctx) -> FarmerOut:
    return farmer_out(db, principal, svc.change_status(db, ctx, principal, farmer_id, body.status, body.reason))


@router.post("/{farmer_id}/kyc", response_model=FarmerOut, summary="Submit KYC (identity number is never stored in full)")
def submit_kyc(farmer_id: uuid.UUID, body: KycSubmit, principal: Manager, db: DB, ctx: Ctx) -> FarmerOut:
    return farmer_out(db, principal, svc.submit_kyc(db, ctx, principal, farmer_id, body.id_type, body.id_number, body.document_id))


@router.post("/{farmer_id}/kyc/decision", response_model=FarmerOut)
def decide_kyc(farmer_id: uuid.UUID, body: KycDecision, principal: KycReviewer, db: DB, ctx: Ctx) -> FarmerOut:
    return farmer_out(db, principal, svc.decide_kyc(db, ctx, principal, farmer_id, body.decision, body.notes,
                                                    body.acknowledge_possible_duplicate))


@router.post("/{farmer_id}/contacts", response_model=FarmerOut, status_code=status.HTTP_201_CREATED)
def add_contact(farmer_id: uuid.UUID, body: ContactIn, principal: Manager, db: DB, ctx: Ctx) -> FarmerOut:
    return farmer_out(db, principal, svc.add_contact(db, ctx, principal, farmer_id, body))


@router.post("/{farmer_id}/contacts/{contact_id}/deactivate", response_model=FarmerOut)
def deactivate_contact(farmer_id: uuid.UUID, contact_id: uuid.UUID, body: ReasonBody, principal: Manager, db: DB, ctx: Ctx) -> FarmerOut:
    return farmer_out(db, principal, svc.deactivate_contact(db, ctx, principal, farmer_id, contact_id, body.reason))


@router.post("/{farmer_id}/consents", response_model=FarmerOut, status_code=status.HTTP_201_CREATED)
def grant_consent(farmer_id: uuid.UUID, body: ConsentIn, principal: Manager, db: DB, ctx: Ctx) -> FarmerOut:
    return farmer_out(db, principal, svc.grant_consent(db, ctx, principal, farmer_id, body))


@router.post("/{farmer_id}/consents/{consent_id}/withdraw", response_model=FarmerOut)
def withdraw_consent(farmer_id: uuid.UUID, consent_id: uuid.UUID, body: ReasonBody, principal: Manager, db: DB, ctx: Ctx) -> FarmerOut:
    return farmer_out(db, principal, svc.withdraw_consent(db, ctx, principal, farmer_id, consent_id, body.reason))


@router.post("/{farmer_id}/agreements", response_model=FarmerOut, status_code=status.HTTP_201_CREATED)
def create_agreement(farmer_id: uuid.UUID, body: AgreementCreate, principal: Manager, db: DB, ctx: Ctx) -> FarmerOut:
    return farmer_out(db, principal, svc.create_agreement(db, ctx, principal, farmer_id, body))


@router.post("/{farmer_id}/agreements/{agreement_id}/sign", response_model=FarmerOut)
def sign_agreement(farmer_id: uuid.UUID, agreement_id: uuid.UUID, body: AgreementSign, principal: Manager, db: DB, ctx: Ctx) -> FarmerOut:
    return farmer_out(db, principal, svc.sign_agreement(db, ctx, principal, farmer_id, agreement_id, body.signed_document_id,
                                                        body.signature_method))


@router.post("/{farmer_id}/agreements/{agreement_id}/status", response_model=FarmerOut)
def agreement_status(farmer_id: uuid.UUID, agreement_id: uuid.UUID, body: AgreementStatusChange, principal: Manager, db: DB,
                     ctx: Ctx) -> FarmerOut:
    return farmer_out(db, principal, svc.change_agreement_status(db, ctx, principal, farmer_id, agreement_id, body.status, body.reason))


@router.post("/{farmer_id}/bank-accounts", response_model=FarmerOut, status_code=status.HTTP_201_CREATED)
def add_bank_account(farmer_id: uuid.UUID, body: BankAccountIn, principal: BankManager, db: DB, ctx: Ctx) -> FarmerOut:
    return farmer_out(db, principal, svc.add_bank_account(db, ctx, principal, farmer_id, body))


@router.post("/{farmer_id}/bank-accounts/{account_id}/decision", response_model=FarmerOut)
def decide_bank_account(farmer_id: uuid.UUID, account_id: uuid.UUID, body: BankDecision, principal: BankReviewer, db: DB,
                        ctx: Ctx) -> FarmerOut:
    return farmer_out(db, principal, svc.decide_bank_account(db, ctx, principal, farmer_id, account_id, body.decision, body.notes))


@router.post("/{farmer_id}/bank-accounts/{account_id}/deactivate", response_model=FarmerOut)
def deactivate_bank_account(farmer_id: uuid.UUID, account_id: uuid.UUID, body: ReasonBody, principal: BankManager, db: DB,
                            ctx: Ctx) -> FarmerOut:
    return farmer_out(db, principal, svc.deactivate_bank_account(db, ctx, principal, farmer_id, account_id, body.reason))


@router.post("/{farmer_id}/documents", response_model=IdRef, status_code=status.HTTP_201_CREATED,
             summary="Upload a farmer document (multipart). KYC and bank proofs are stored as RESTRICTED.")
def upload_document(farmer_id: uuid.UUID, principal: Manager, db: DB, ctx: Ctx, file: Annotated[UploadFile, File()],
                          category: Annotated[str, Form(max_length=30)], title: Annotated[str, Form(max_length=200)] = "") -> IdRef:
    data = read_upload(file)
    return IdRef(id=svc.upload_document(db, ctx, principal, farmer_id, category, title, file.filename, data))


@router.post("/{farmer_id}/link-user", response_model=FarmerOut, summary="Link a login account for farmer self-service")
def link_user(farmer_id: uuid.UUID, body: LinkUser, principal: Manager, db: DB, ctx: Ctx) -> FarmerOut:
    return farmer_out(db, principal, svc.link_user(db, ctx, principal, farmer_id, body.user_id))
