"""Marketplace API (`/api/v1/marketplace`, Phase 10): buyer profile and KYC, platform KYC review, listings. Authenticated only — no public
catalogue (D25). Every POST accepts an Idempotency-Key. No fee, commission, payout or resale endpoint exists."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile, status
from sqlalchemy import select

from app.api.deps import DB, Ctx, ListLimit, ListOffset, read_upload, require_any
from app.models import BuyerProfile, CreditBatch, Organization
from app.schemas.lab import DocumentRef
from app.schemas.marketplace import (
    BuyerProfileIn,
    BuyerProfileOut,
    BuyerProfileView,
    ListingIn,
    ListingOut,
    ListingsOut,
    OptionalReasonIn,
    OrgIn,
    ReasonIn,
    ReviewIn,
)
from app.security.permissions import P
from app.security.principal import Principal
from app.security.scoping import preload
from app.services import marketplace_mappers as mm
from app.services import marketplace_service as ms

router = APIRouter(prefix="/marketplace", tags=["marketplace — buyers, KYC, listings"])

KycSubmitter = Annotated[Principal, Depends(require_any(P.BUYERS_KYC_SUBMIT))]
KycReviewer = Annotated[Principal, Depends(require_any(P.BUYERS_KYC_VERIFY))]
Browser = Annotated[Principal, Depends(require_any(P.MARKETPLACE_READ, P.LISTINGS_MANAGE, P.LISTINGS_APPROVE))]
ListingManager = Annotated[Principal, Depends(require_any(P.LISTINGS_MANAGE))]
ListingApprover = Annotated[Principal, Depends(require_any(P.LISTINGS_APPROVE))]
ListingCloser = Annotated[Principal, Depends(require_any(P.LISTINGS_MANAGE, P.LISTINGS_APPROVE))]
IdemKey = Annotated[str | None, Header(alias="Idempotency-Key", max_length=80)]
KYC_NOTE = ("KYC is reviewed by the platform's marketplace compliance team. A buyer organization must be KYC verified to place orders, pay "
            "and receive marketplace deliveries. Upload the documents your compliance contact asked for (PDF).")


def _doc(d: object) -> DocumentRef:
    return mm.doc_ref(d)  # type: ignore[arg-type]


# ---------------------------------------------------------------- buyer profile (own organization)
@router.get("/buyer-profile", response_model=BuyerProfileView, summary="The caller's buyer organization profile and KYC status")
def get_buyer_profile(principal: KycSubmitter, db: DB, organization_id: uuid.UUID | None = None) -> BuyerProfileView:
    o = ms.buyer_org(db, principal, organization_id, P.BUYERS_KYC_SUBMIT)
    p = ms.profile_of(db, o.id)
    return BuyerProfileView(organization_id=o.id, organization_name=o.name, profile=mm.profile_out(db, principal, p) if p else None, note=KYC_NOTE)


@router.post("/buyer-profile", response_model=BuyerProfileOut, summary="Create or edit the buyer profile (DRAFT or KYC_RETURNED)")
def save_buyer_profile(body: BuyerProfileIn, principal: KycSubmitter, db: DB, ctx: Ctx, key: IdemKey = None) -> BuyerProfileOut:
    return mm.profile_out(db, principal, ms.save_profile(db, ctx, principal, body, key))


@router.post("/buyer-profile/documents", response_model=DocumentRef, status_code=status.HTTP_201_CREATED,
             summary="Attach a KYC document (BUYER_KYC_DOCUMENT, PDF, restricted)")
def buyer_kyc_document(principal: KycSubmitter, db: DB, ctx: Ctx, file: Annotated[UploadFile, File()],
                       title: Annotated[str | None, Form(max_length=200)] = None,
                       organization_id: Annotated[uuid.UUID | None, Form()] = None) -> DocumentRef:
    return _doc(ms.upload_kyc_document(db, ctx, principal, organization_id, file.filename, read_upload(file), title))


@router.post("/buyer-profile/submit-kyc", response_model=BuyerProfileOut, summary="Submit the buyer profile and KYC documents for review")
def submit_buyer_kyc(principal: KycSubmitter, db: DB, ctx: Ctx, body: OrgIn | None = None, key: IdemKey = None) -> BuyerProfileOut:
    return mm.profile_out(db, principal, ms.submit_kyc(db, ctx, principal, body.organization_id if body else None, key))


# ---------------------------------------------------------------- platform KYC review (D28)
@router.get("/buyer-profiles", response_model=list[BuyerProfileOut], summary="Buyer KYC review queue (platform compliance)")
def list_buyer_profiles(principal: KycReviewer, db: DB, status: str | None = None) -> list[BuyerProfileOut]:
    if not principal.has_platform(P.BUYERS_KYC_VERIFY):
        return []
    stmt = select(BuyerProfile).where(BuyerProfile.environment == ms.env_of(principal)).order_by(BuyerProfile.updated_at.desc())
    if status:
        stmt = stmt.where(BuyerProfile.status == status)
    return [mm.profile_out(db, principal, p) for p in db.scalars(stmt).all()]


@router.get("/buyer-profiles/{profile_id}", response_model=BuyerProfileOut)
def get_buyer_profile_for_review(profile_id: uuid.UUID, principal: KycReviewer, db: DB) -> BuyerProfileOut:
    return mm.profile_out(db, principal, ms.reviewer_profile(db, principal, profile_id))


@router.post("/buyer-profiles/{profile_id}/verify", response_model=BuyerProfileOut,
             summary="Verify KYC (or reinstate a suspended buyer) — never the submitter")
def verify_buyer(profile_id: uuid.UUID, principal: KycReviewer, db: DB, ctx: Ctx, body: ReviewIn | None = None,
                 key: IdemKey = None) -> BuyerProfileOut:
    return mm.profile_out(db, principal, ms.review(db, ctx, principal, profile_id, "VERIFY", body.note if body else None, key))


@router.post("/buyer-profiles/{profile_id}/return", response_model=BuyerProfileOut, summary="Return KYC to the buyer with a reason")
def return_buyer(profile_id: uuid.UUID, body: ReasonIn, principal: KycReviewer, db: DB, ctx: Ctx, key: IdemKey = None) -> BuyerProfileOut:
    return mm.profile_out(db, principal, ms.review(db, ctx, principal, profile_id, "RETURN", body.reason, key))


@router.post("/buyer-profiles/{profile_id}/suspend", response_model=BuyerProfileOut,
             summary="Suspend a verified buyer (no new orders; existing holdings are never removed)")
def suspend_buyer(profile_id: uuid.UUID, body: ReasonIn, principal: KycReviewer, db: DB, ctx: Ctx, key: IdemKey = None) -> BuyerProfileOut:
    return mm.profile_out(db, principal, ms.review(db, ctx, principal, profile_id, "SUSPEND", body.reason, key))


# ---------------------------------------------------------------- listings
@router.get("/listings", response_model=ListingsOut, summary="ACTIVE listings (buyers) or the organization's own listings (sellers, mine=true)")
def list_listings(principal: Browser, db: DB, ctx: Ctx, mine: bool = False, status: str | None = None, limit: ListLimit = None,
                  offset: ListOffset = 0) -> ListingsOut:
    rows = ms.listings(db, ctx, principal, mine=mine, status=status, limit=limit, offset=offset)
    preload(db, Organization, [x.seller_organization_id for x in rows])
    preload(db, CreditBatch, [x.batch_id for x in rows])
    return ListingsOut(listings=[mm.listing_out(db, principal, x) for x in rows], demo_note=ms.demo_note(principal, bool(rows)),
                       note=mm.LISTING_NOTE)


@router.get("/listings/{listing_id}", response_model=ListingOut)
def get_listing(listing_id: uuid.UUID, principal: Browser, db: DB, ctx: Ctx) -> ListingOut:
    return mm.listing_out(db, principal, ms.get_listing(db, ctx, principal, listing_id))


@router.post("/listings", response_model=ListingOut, status_code=status.HTTP_201_CREATED,
             summary="Create a DRAFT listing of the organization's AVAILABLE ledger credits of one batch (no reservation is made)")
def create_listing(body: ListingIn, principal: ListingManager, db: DB, ctx: Ctx, key: IdemKey = None) -> ListingOut:
    return mm.listing_out(db, principal, ms.create_listing(db, ctx, principal, body, key))


@router.post("/listings/{listing_id}/documents", response_model=DocumentRef, status_code=status.HTTP_201_CREATED,
             summary="Publish a document on a listing before approval (LISTING_DOCUMENT, PDF; visible to buyers)")
def listing_document(listing_id: uuid.UUID, principal: ListingManager, db: DB, ctx: Ctx, file: Annotated[UploadFile, File()],
                     title: Annotated[str | None, Form(max_length=200)] = None) -> DocumentRef:
    return _doc(ms.upload_listing_document(db, ctx, principal, listing_id, file.filename, read_upload(file), title))


@router.post("/listings/{listing_id}/submit", response_model=ListingOut, summary="Submit a DRAFT listing for approval")
def submit_listing(listing_id: uuid.UUID, principal: ListingManager, db: DB, ctx: Ctx, key: IdemKey = None) -> ListingOut:
    return mm.listing_out(db, principal, ms.listing_action(db, ctx, principal, listing_id, "submit", None, key))


@router.post("/listings/{listing_id}/approve", response_model=ListingOut,
             summary="Approve (publish) a listing — never its creator; price and disclosure are frozen from now on")
def approve_listing(listing_id: uuid.UUID, principal: ListingApprover, db: DB, ctx: Ctx, key: IdemKey = None) -> ListingOut:
    return mm.listing_out(db, principal, ms.listing_action(db, ctx, principal, listing_id, "approve", None, key))


@router.post("/listings/{listing_id}/pause", response_model=ListingOut)
def pause_listing(listing_id: uuid.UUID, principal: ListingManager, db: DB, ctx: Ctx, body: OptionalReasonIn | None = None,
                  key: IdemKey = None) -> ListingOut:
    return mm.listing_out(db, principal, ms.listing_action(db, ctx, principal, listing_id, "pause", body.reason if body else None, key))


@router.post("/listings/{listing_id}/resume", response_model=ListingOut)
def resume_listing(listing_id: uuid.UUID, principal: ListingManager, db: DB, ctx: Ctx, key: IdemKey = None) -> ListingOut:
    return mm.listing_out(db, principal, ms.listing_action(db, ctx, principal, listing_id, "resume", None, key))


@router.post("/listings/{listing_id}/close", response_model=ListingOut,
             summary="Close an ACTIVE / PAUSED listing (CLOSED) or withdraw a draft / submitted one (CANCELLED); placed orders are unaffected")
def close_listing(listing_id: uuid.UUID, body: ReasonIn, principal: ListingCloser, db: DB, ctx: Ctx, key: IdemKey = None) -> ListingOut:
    return mm.listing_out(db, principal, ms.listing_action(db, ctx, principal, listing_id, "close", body.reason, key))

