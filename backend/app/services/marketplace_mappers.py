"""Phase 10 mappers. Every output is an explicit allow-list (D25): buyers see listing disclosure, their own orders / payments / refunds and
item delivery status — never farmer, farm, location, KYC of others, bank, MRV, laboratory, VVB-internal, calculation-internal or audit data;
sellers see the buyer organization's name and the order / payment data of orders against their own listings."""
import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    BuyerKycReview,
    BuyerProfile,
    CreditBatch,
    CreditPosition,
    CreditReservation,
    CreditTransfer,
    Document,
    ListingDocument,
    MarketplaceListing,
    Order,
    Organization,
    Payment,
    Project,
    Refund,
    User,
)
from app.schemas.lab import DocumentRef
from app.schemas.marketplace import (
    BuyerProfileOut,
    KycReviewOut,
    ListingOut,
    OrderItemOut,
    OrderOut,
    PaymentOut,
    RefundOut,
)
from app.security.permissions import P
from app.security.principal import Principal
from app.services import document_service
from app.services import ledger_service as ls
from app.services import marketplace_service as ms
from app.services import order_service as os_

LISTING_NOTE = ("Fixed-price offers of registry-issued credits held in the credit ledger. Prices are per credit; no fee, commission or tax "
                "is added. Credits are reserved when you order and delivered by a ledger transfer after the seller confirms your payment.")


def _name(db: Session, user_id: uuid.UUID | None) -> str | None:
    u = db.get(User, user_id) if user_id else None
    return u.full_name if u else None


def _org(db: Session, org_id: uuid.UUID | None) -> Organization | None:
    return db.get(Organization, org_id) if org_id else None


def _oname(db: Session, org_id: uuid.UUID | None) -> str | None:
    o = _org(db, org_id)
    return o.name if o else None


def doc_ref(d: Document) -> DocumentRef:
    v = max(d.versions, key=lambda x: x.version) if d.versions else None
    return DocumentRef(document_id=d.id, category=d.category, title=d.title, file_name=v.file_name if v else None,
                       sha256=v.checksum_sha256 if v else None, uploaded_at=v.uploaded_at if v else d.created_at)


def profile_out(db: Session, principal: Principal, p: BuyerProfile) -> BuyerProfileOut:
    o = _org(db, p.organization_id)
    reviews = db.scalars(select(BuyerKycReview).where(BuyerKycReview.buyer_profile_id == p.id).order_by(BuyerKycReview.created_at)).all()
    can_review = principal.has_platform(P.BUYERS_KYC_VERIFY) and p.submitted_by != principal.user_id
    return BuyerProfileOut(id=p.id, organization_id=p.organization_id, organization_name=o.name if o else None,
                           organization_code=o.code if o else None,
                           status=p.status, legal_name=p.legal_name, registration_number=p.registration_number, country=p.country,
                           contact_name=p.contact_name, contact_email=p.contact_email, identifier_type=p.identifier_type,
                           identifier_last4=p.identifier_last4, submitted_by_name=_name(db, p.submitted_by), submitted_at=p.submitted_at,
                           verified_by_name=_name(db, p.verified_by), verified_at=p.verified_at, return_reason=p.return_reason,
                           suspension_reason=p.suspension_reason, documents=[doc_ref(d) for d in ms.kyc_documents(db, p)],
                           reviews=[KycReviewOut(action=r.action, actor_name=_name(db, r.actor_id), note=r.note, created_at=r.created_at)
                                    for r in reviews],
                           environment=p.environment,
                           can_edit=p.status in ("DRAFT", "KYC_RETURNED") and principal.can_in_org(P.BUYERS_KYC_SUBMIT, p.organization_id),
                           can_review=can_review)


def listing_out(db: Session, principal: Principal, lst: MarketplaceListing) -> ListingOut:
    seller = _org(db, lst.seller_organization_id)
    b = db.get(CreditBatch, lst.batch_id)
    seller_side = ms.is_seller_side(principal, lst)
    docs = [db.get(Document, ld.document_id) for ld in db.scalars(select(ListingDocument).where(ListingDocument.listing_id == lst.id)).all()]
    return ListingOut(id=lst.id, listing_code=lst.listing_code, title=lst.title, seller_organization_id=lst.seller_organization_id,
                      seller_name=seller.name if seller else None, batch_id=lst.batch_id, batch_code=b.batch_code if b else None,
                      serial_range_id=lst.serial_range_id, listed_quantity=int(lst.listed_quantity),
                      remaining_quantity=int(ms.remaining(db, lst)), available_quantity=int(ms.displayed_available(db, lst)),
                      unit_price=lst.unit_price, currency=lst.currency,
                      min_quantity=int(lst.min_quantity) if lst.min_quantity else None,
                      max_quantity=int(lst.max_quantity) if lst.max_quantity else None,
                      payment_window_hours=lst.payment_window_hours, valid_until=lst.valid_until, co_benefits=lst.co_benefits,
                      disclosure=json.loads(lst.disclosure) if lst.disclosure else {}, disclosure_sha256=lst.disclosure_sha256, status=lst.status,
                      created_by_name=_name(db, lst.created_by) if seller_side else None,
                      approved_by_name=_name(db, lst.approved_by) if seller_side else None, approved_at=lst.approved_at,
                      close_reason=lst.close_reason if seller_side else None,
                      documents=[doc_ref(d) for d in docs if d is not None and d.status == "ACTIVE"], environment=lst.environment,
                      seller_side=seller_side, can_manage=principal.can_in_org(P.LISTINGS_MANAGE, lst.seller_organization_id),
                      can_approve=principal.can_in_org(P.LISTINGS_APPROVE, lst.seller_organization_id) and lst.created_by != principal.user_id)


def payment_out(db: Session, principal: Principal, p: Payment, o: Order | None = None) -> PaymentOut:
    o = o or db.get(Order, p.order_id)
    payee = principal.can_in_org(P.PAYMENTS_CONFIRM, p.payee_organization_id)
    return PaymentOut(id=p.id, payment_code=p.payment_code, order_id=p.order_id, order_code=o.order_code if o else None, adapter_code=p.adapter_code,
                      amount=p.amount, currency=p.currency, status=p.status, external_reference=p.external_reference,
                      evidence_document_id=p.evidence_document_id, recorded_by_name=_name(db, p.recorded_by), recorded_at=p.created_at,
                      confirmed_by_name=_name(db, p.confirmed_by), confirmed_at=p.confirmed_at, reject_reason=p.reject_reason,
                      payer_name=_oname(db, p.payer_organization_id), payee_name=_oname(db, p.payee_organization_id),
                      can_confirm=payee and p.status == "PENDING_CONFIRMATION" and p.recorded_by != principal.user_id,
                      can_refund=principal.can_in_org(P.REFUNDS_REQUEST, p.payee_organization_id) and p.status in ("CONFIRMED", "UNMATCHED"))


def refund_out(db: Session, principal: Principal, r: Refund) -> RefundOut:
    p = db.get(Payment, r.payment_id)
    o = db.get(Order, r.order_id)
    approver = p is not None and principal.can_in_org(P.REFUNDS_APPROVE, p.payee_organization_id)
    finance = p is not None and any(principal.can_in_org(c, p.payee_organization_id) for c in (P.REFUNDS_APPROVE, P.REFUNDS_REQUEST))
    return RefundOut(id=r.id, refund_code=r.refund_code, payment_id=r.payment_id, payment_code=p.payment_code if p else None, order_id=r.order_id,
                     order_code=o.order_code if o else None, amount=r.amount, currency=r.currency, after_transfer=r.after_transfer, reason=r.reason,
                     status=r.status, requested_by_name=_name(db, r.requested_by), approved_by_name=_name(db, r.approved_by),
                     completed_at=r.completed_at, external_reference=r.external_reference, reject_reason=r.reject_reason,
                     can_approve=approver and r.status == "REQUESTED" and r.requested_by != principal.user_id,
                     can_complete=finance and r.status == "APPROVED")


def _can_complete(db: Session, principal: Principal, t: CreditTransfer | None) -> bool:
    if t is None or t.status != "REQUESTED" or t.requested_by == principal.user_id:
        return False
    pending = list(db.scalars(select(CreditPosition).where(CreditPosition.transfer_id == t.id, CreditPosition.status == "OPEN")).all())
    custodians = {ls.custodian_org(db, p) for p in pending} or {t.sender_organization_id}
    return all(principal.can_in_org(P.CREDITS_CONFIRM, c) for c in custodians)


def order_out(db: Session, principal: Principal, o: Order) -> OrderOut:
    viewer = os_.side(principal, o) or "NONE"
    items = []
    for it in os_.items_of(db, o.id):
        lst = db.get(MarketplaceListing, it.listing_id)
        b = db.get(CreditBatch, it.batch_id)
        proj = db.get(Project, b.project_id) if b else None
        r = db.get(CreditReservation, it.reservation_id) if it.reservation_id else None
        t = db.get(CreditTransfer, it.transfer_id) if it.transfer_id else None
        items.append(OrderItemOut(id=it.id, item_code=it.item_code, listing_id=it.listing_id, listing_code=lst.listing_code if lst else None,
                                  batch_id=it.batch_id, batch_code=b.batch_code if b else None, vintage=b.vintage if b else None,
                                  project_code=proj.project_code if proj else None, quantity=int(it.quantity), unit_price=it.unit_price,
                                  line_total=it.line_total, status=it.status, reservation_code=r.reservation_code if r else None,
                                  reservation_status=r.status if r else None, transfer_id=it.transfer_id,
                                  transfer_code=t.transfer_code if t else None, transfer_status=t.status if t else None,
                                  can_complete=_can_complete(db, principal, t)))
    pays = db.scalars(select(Payment).where(Payment.order_id == o.id).order_by(Payment.created_at)).all()
    refunds = db.scalars(select(Refund).where(Refund.order_id == o.id).order_by(Refund.created_at)).all()
    docs = [d for d in document_service.list_for(db, os_.ORDER_ENTITY, o.id) if d.status == "ACTIVE"]
    buyer, seller = _org(db, o.buyer_organization_id), _org(db, o.seller_organization_id)
    open_pay = any(p.status in ("CREATED", "PENDING", "UNCONFIRMED", "PENDING_CONFIRMATION", "CONFIRMED") for p in pays)
    return OrderOut(id=o.id, order_code=o.order_code, buyer_organization_id=o.buyer_organization_id, buyer_name=buyer.name if buyer else None,
                    seller_organization_id=o.seller_organization_id, seller_name=seller.name if seller else None, currency=o.currency,
                    subtotal=o.subtotal, total=o.total, status=o.status, transfer_kind=o.transfer_kind,
                    recipient_registry_account=o.recipient_registry_account, expires_at=o.expires_at, placed_at=o.placed_at, paid_at=o.paid_at,
                    completed_at=o.completed_at, close_reason=o.close_reason, attention_reason=o.attention_reason, items=items,
                    payments=[payment_out(db, principal, p, o) for p in pays], refunds=[refund_out(db, principal, r) for r in refunds],
                    documents=[doc_ref(d) for d in docs], environment=o.environment, viewer_side=viewer,
                    can_cancel=o.status == "PLACED" and not any(p.status in ("PENDING_CONFIRMATION", "CONFIRMED") for p in pays) and (
                        principal.can_in_org(P.ORDERS_PLACE, o.buyer_organization_id)
                        or principal.can_in_org(P.ORDERS_MANAGE, o.seller_organization_id)),
                    can_pay=o.status == "PLACED" and not open_pay and principal.can_in_org(P.PAYMENTS_RECORD, o.buyer_organization_id),
                    can_retry=o.status == "ATTENTION_REQUIRED" and principal.can_in_org(P.ORDERS_MANAGE, o.seller_organization_id))

