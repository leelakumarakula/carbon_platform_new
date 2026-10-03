"""Phase 10 marketplace — shared access helpers, buyer profiles / KYC (D1, D2, D28) and listings (D3–D7, D25).

A listing is a seller's fixed-price offer of credits of ONE Phase 9B batch (optionally one serial range). Listing creates no reservation
(D6) and stores no available or remaining quantity (D4): `remaining` = listed − Σ committed order items (derived under the listing lock),
and what can be bought is further limited by the seller's derived 9B AVAILABLE positions. Phase 9B stays the final authority (guarded
consumption) — see order_service for order placement.
"""
import hashlib
import json
import uuid
from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, false, func, or_, select
from sqlalchemy.orm import Session

from app.core.context import RequestContext
from app.core.errors import Conflict, NotFound, PermissionDenied, ValidationFailed
from app.integrations.payment import CURRENCY_EXPONENTS, money_ok
from app.models import (
    BuyerKycReview,
    BuyerProfile,
    CreditBatch,
    CreditIssuance,
    CreditPosition,
    CreditSerialRange,
    Document,
    ListingDocument,
    MarketplaceListing,
    MethodologyVersion,
    MonitoringPeriod,
    Order,
    OrderItem,
    Organization,
    Project,
    Standard,
    VerificationDecision,
)
from app.models.base import utcnow
from app.models.documents import DocumentCategory
from app.repositories.sequences import next_code
from app.security import crypto
from app.security.permissions import P
from app.security.principal import Principal
from app.security.scoping import org_predicate
from app.services import document_service
from app.services import ledger_service as ls
from app.services.ledger_mappers import range_text
from app.services.workflows import BUYER_PROFILE_MACHINE, LISTING_MACHINE

DEMO_NOTE = "DEMO — no registry-issued credits; nothing is listed"
LOCK = ls.LOCK_HINT
BUYER_PROFILE_ENTITY = "buyer_profile"
LISTING_ENTITY = "marketplace_listing"
COMMITTED_ITEM_STATES = ("RESERVED", "TRANSFER_PENDING", "DELIVERED", "FAILED")   # count against a listing's cap
SELLER_ORG_TYPES = ("PROJECT_DEVELOPER",)                                          # D3: no buyer resale
SELLER_VIEW = (P.LISTINGS_MANAGE, P.LISTINGS_APPROVE, P.ORDERS_READ, P.ORDERS_MANAGE)


# ---------------------------------------------------------------- shared helpers
def nf(what: str, code: str) -> NotFound:
    return NotFound(f"{what} not found.", error_code=code)


def require(principal: Principal, org_id: uuid.UUID | None, *codes: str, visible: Iterable[str] = (), what: str = "Record",
            nf_code: str = "NOT_FOUND") -> None:
    """Organization scoping: 404 when the record is outside every scope of the caller, 403 when visible but not allowed."""
    if any(principal.can_in_org(c, org_id) for c in codes):
        return
    if any(principal.can_in_org(c, org_id) for c in visible):
        raise PermissionDenied(details={"required_permission": " or ".join(codes)})
    raise nf(what, nf_code)


def lock(db: Session, model: Any, entity_id: uuid.UUID) -> Any:
    return db.scalars(select(model).with_hint(model, LOCK, "mssql").where(model.id == entity_id).execution_options(populate_existing=True)).first()


def org(db: Session, org_id: uuid.UUID) -> Organization:
    o = db.get(Organization, org_id)
    if o is None:
        raise nf("Organization", "ORGANIZATION_NOT_FOUND")
    return o


def transition(db: Session, ctx: RequestContext, machine: Any, entity: Any, entity_type: str, to: str, reason: str | None = None) -> str:
    frm = entity.status
    machine.assert_transition(frm, to)
    entity.status = to
    ls.workflow(db, ctx, entity_type, entity.id, frm, to, reason)
    return str(frm)


def replay_action(entity: Any, key: str | None, target: str | Iterable[str]) -> bool:
    """A repeated state-change request with the same Idempotency-Key replays (no second effect)."""
    targets = {target} if isinstance(target, str) else set(target)
    return bool(key) and getattr(entity, "action_key", None) == key and entity.status in targets


def money(value: Decimal | str | int, currency: str, field: str = "amount") -> Decimal:
    d = Decimal(str(value))
    if currency not in CURRENCY_EXPONENTS:
        raise ValidationFailed(f"Currency {currency!r} is not supported (ISO 4217 codes with known minor units only).",
                               error_code="UNSUPPORTED_CURRENCY", details={"currency": currency})
    if d <= 0 or not money_ok(d, currency):
        raise ValidationFailed(f"The {field} must be positive with at most {CURRENCY_EXPONENTS[currency]} decimals for {currency}.",
                               error_code="INVALID_AMOUNT", details={"field": field})
    return d


def env_of(principal: Principal) -> str:
    return str(principal.user.environment)


# ---------------------------------------------------------------- buyer profile & KYC (D1, D2, D28)
def buyer_org(db: Session, principal: Principal, organization_id: uuid.UUID | None, code: str) -> Organization:
    """The caller's BUYER organization in which `code` is held (explicit when the caller holds it in several)."""
    candidates = [g.organization_id for g in principal.grants if g.organization_id and code in g.permissions]
    if organization_id is not None:
        if organization_id not in candidates:
            raise nf("Organization", "ORGANIZATION_NOT_FOUND")
        candidates = [organization_id]
    orgs = [o for o in (db.get(Organization, c) for c in dict.fromkeys(candidates)) if o is not None and o.org_type == "BUYER"]
    if not orgs:
        raise PermissionDenied("Only members of a buyer organization can do this.", error_code="NOT_A_BUYER")
    if len(orgs) > 1:
        raise ValidationFailed("Choose the buyer organization.", error_code="ORGANIZATION_REQUIRED")
    return orgs[0]


def profile_of(db: Session, org_id: uuid.UUID) -> BuyerProfile | None:
    return db.scalars(select(BuyerProfile).where(BuyerProfile.organization_id == org_id)).first()


def require_kyc(db: Session, buyer_org_id: uuid.UUID) -> BuyerProfile:
    """D1: the buyer organization must be KYC_VERIFIED to order, pay and receive marketplace transfers (marketplace layer only)."""
    p = profile_of(db, buyer_org_id)
    if p is None or p.status != "KYC_VERIFIED":
        raise Conflict("The buyer organization must be KYC verified for marketplace orders, payments and deliveries.",
                       error_code="BUYER_KYC_REQUIRED", details={"kyc_status": p.status if p else "NONE"})
    return p


def save_profile(db: Session, ctx: RequestContext, principal: Principal, data: Any, key: str | None) -> BuyerProfile:
    o = buyer_org(db, principal, data.organization_id, P.BUYERS_KYC_SUBMIT)
    if o.status != "ACTIVE":
        raise Conflict("The buyer organization is not active.", error_code="ORGANIZATION_INACTIVE")
    p = profile_of(db, o.id)
    if p is not None and p.status not in ("DRAFT", "KYC_RETURNED"):
        raise Conflict(f"The buyer profile is {p.status}; it can only be edited as a draft or after it was returned.",
                       error_code="BUYER_PROFILE_LOCKED")
    created = p is None
    if p is None:
        p = BuyerProfile(organization_id=o.id, status="DRAFT", legal_name=data.legal_name, created_by=principal.user_id, request_key=key,
                         environment=o.environment)
        db.add(p)
    p.legal_name, p.registration_number, p.country = data.legal_name, data.registration_number, data.country
    p.contact_name, p.contact_email = data.contact_name, data.contact_email
    if data.identifier:
        if not data.identifier_type:
            raise ValidationFailed("Give the identifier type with the identifier.", error_code="IDENTIFIER_TYPE_REQUIRED")
        p.identifier_type, p.identifier_last4 = data.identifier_type, crypto.last4(data.identifier)
        p.identifier_hash = crypto.fingerprint(data.identifier, "buyer_identifier")
    db.flush()
    ls.audit(db, ctx, "BUYER_PROFILE_CREATED" if created else "BUYER_PROFILE_UPDATED", BUYER_PROFILE_ENTITY, p.id, [o.id],
             {"legal_name": p.legal_name, "registration_number": p.registration_number, "country": p.country,
              "identifier_type": p.identifier_type, "identifier_last4": p.identifier_last4, "status": p.status})
    if created:
        ls.workflow(db, ctx, BUYER_PROFILE_ENTITY, p.id, None, "DRAFT", None)
    db.commit()
    return p


def kyc_documents(db: Session, p: BuyerProfile) -> list[Document]:
    return [d for d in document_service.list_for(db, BUYER_PROFILE_ENTITY, p.id)
            if d.category == DocumentCategory.BUYER_KYC_DOCUMENT.value and d.status == "ACTIVE"]


def upload_kyc_document(db: Session, ctx: RequestContext, principal: Principal, organization_id: uuid.UUID | None, filename: str | None,
                        data: bytes, title: str | None) -> Document:
    o = buyer_org(db, principal, organization_id, P.BUYERS_KYC_SUBMIT)
    p = profile_of(db, o.id)
    if p is None:
        raise nf("Buyer profile", "BUYER_PROFILE_NOT_FOUND")
    if p.status not in ("DRAFT", "KYC_RETURNED"):
        raise Conflict(f"KYC documents can be added to a draft or returned profile (this one is {p.status}).", error_code="BUYER_PROFILE_LOCKED")
    doc = document_service.create_document(db, ctx, entity_type=BUYER_PROFILE_ENTITY, entity_id=p.id, organization_id=o.id,
                                           environment=p.environment, category=DocumentCategory.BUYER_KYC_DOCUMENT.value,
                                           title=title or "Buyer KYC document", filename=filename, data=data)
    db.commit()
    return doc


def submit_kyc(db: Session, ctx: RequestContext, principal: Principal, organization_id: uuid.UUID | None, key: str | None) -> BuyerProfile:
    o = buyer_org(db, principal, organization_id, P.BUYERS_KYC_SUBMIT)
    p = profile_of(db, o.id)
    if p is None:
        raise nf("Buyer profile", "BUYER_PROFILE_NOT_FOUND")
    if replay_action(p, key, "KYC_SUBMITTED"):
        return p
    docs = kyc_documents(db, p)
    if not docs:
        # D28: no legal document list is invented — the review is document-driven, so at least one document must be supplied
        raise ValidationFailed("Attach at least one KYC document (PDF) before submitting.", error_code="KYC_DOCUMENT_REQUIRED")
    transition(db, ctx, BUYER_PROFILE_MACHINE, p, BUYER_PROFILE_ENTITY, "KYC_SUBMITTED")
    p.submitted_by, p.submitted_at, p.verified_by, p.verified_at, p.action_key = principal.user_id, utcnow(), None, None, key
    db.add(BuyerKycReview(buyer_profile_id=p.id, action="SUBMITTED", actor_id=principal.user_id,
                          document_ids=json.dumps(sorted(str(d.id) for d in docs))))
    ls.audit(db, ctx, "BUYER_KYC_SUBMITTED", BUYER_PROFILE_ENTITY, p.id, [o.id], {"documents": len(docs), "status": p.status})
    db.commit()
    return p


def reviewer_profile(db: Session, principal: Principal, profile_id: uuid.UUID) -> BuyerProfile:
    p = db.get(BuyerProfile, profile_id)
    if p is None or not principal.has_platform(P.BUYERS_KYC_VERIFY) or p.environment != env_of(principal):
        raise nf("Buyer profile", "BUYER_PROFILE_NOT_FOUND")
    return p


def review(db: Session, ctx: RequestContext, principal: Principal, profile_id: uuid.UUID, action: str, note: str | None,
           key: str | None) -> BuyerProfile:
    """VERIFY (from KYC_SUBMITTED, or reinstating a SUSPENDED buyer), RETURN, SUSPEND — never by the user who submitted the KYC."""
    p = reviewer_profile(db, principal, profile_id)
    target = {"VERIFY": "KYC_VERIFIED", "RETURN": "KYC_RETURNED", "SUSPEND": "SUSPENDED"}[action]
    if replay_action(p, key, target):
        return p
    if p.submitted_by == principal.user_id:
        raise PermissionDenied("You submitted this KYC, so someone else must review it.", error_code="SEPARATION_OF_DUTIES")
    if action in ("RETURN", "SUSPEND") and not (note and note.strip()):
        raise ValidationFailed("Give a reason.", error_code="REASON_REQUIRED")
    reinstated = action == "VERIFY" and p.status == "SUSPENDED"
    frm = transition(db, ctx, BUYER_PROFILE_MACHINE, p, BUYER_PROFILE_ENTITY, target, note)
    p.action_key = key
    if target == "KYC_VERIFIED":
        p.verified_by, p.verified_at, p.suspension_reason = principal.user_id, utcnow(), None
    elif target == "KYC_RETURNED":
        p.return_reason = note
    else:
        p.suspension_reason = note
    db.add(BuyerKycReview(buyer_profile_id=p.id, action="REINSTATED" if reinstated else {"VERIFY": "VERIFIED", "RETURN": "RETURNED",
                                                                                         "SUSPEND": "SUSPENDED"}[action],
                          actor_id=principal.user_id, note=note, document_ids=json.dumps(sorted(str(d.id) for d in kyc_documents(db, p)))))
    event = {"VERIFY": "BUYER_KYC_VERIFIED", "RETURN": "BUYER_KYC_RETURNED", "SUSPEND": "BUYER_SUSPENDED"}[action]
    ls.audit(db, ctx, event, BUYER_PROFILE_ENTITY, p.id, [p.organization_id], {"status": target, "reinstated": reinstated}, note,
             {"status": frm})
    db.commit()
    return p


def _profile_resolver(db: Session, principal: Principal, entity_id: uuid.UUID, kind: str) -> None:
    if kind == "manage":
        raise PermissionDenied("KYC documents are immutable; upload a new document instead.", error_code="DOCUMENT_IMMUTABLE")
    p = db.get(BuyerProfile, entity_id)
    if p is None or not (principal.can_in_org(P.BUYERS_KYC_SUBMIT, p.organization_id)
                         or (principal.has_platform(P.BUYERS_KYC_VERIFY) and p.environment == env_of(principal))):
        raise NotFound("Document not found.", error_code="DOCUMENT_NOT_FOUND")       # restricted: the buyer and the reviewer only


document_service.register_resolver(BUYER_PROFILE_ENTITY, _profile_resolver)


# ---------------------------------------------------------------- listings (D3–D7)
def seller_available(db: Session, listing_or_batch: Any, seller_id: uuid.UUID, serial_range_id: uuid.UUID | None) -> Decimal:
    """The seller's AVAILABLE credits in the batch (and range), derived from open 9B positions — never stored."""
    batch_id = listing_or_batch.batch_id if isinstance(listing_or_batch, MarketplaceListing) else listing_or_batch.id
    stmt = select(func.coalesce(func.sum(CreditPosition.quantity), 0)).where(
        CreditPosition.batch_id == batch_id, CreditPosition.owner_organization_id == seller_id, CreditPosition.state == "AVAILABLE",
        CreditPosition.status == "OPEN")
    if serial_range_id is not None:
        stmt = stmt.where(CreditPosition.serial_range_id == serial_range_id)
    return Decimal(db.scalar(stmt) or 0)


def committed(db: Session, listing_id: uuid.UUID) -> Decimal:
    return Decimal(db.scalar(select(func.coalesce(func.sum(OrderItem.quantity), 0)).where(
        OrderItem.listing_id == listing_id, OrderItem.status.in_(COMMITTED_ITEM_STATES))) or 0)


def remaining(db: Session, listing: MarketplaceListing) -> Decimal:
    return max(Decimal(0), listing.listed_quantity - committed(db, listing.id))


def displayed_available(db: Session, listing: MarketplaceListing) -> Decimal:
    """D4: min(listing remaining, seller's 9B AVAILABLE) — display only; order placement re-checks both under locks."""
    if listing.status != "ACTIVE":
        return Decimal(0)
    return max(Decimal(0), min(remaining(db, listing), seller_available(db, listing, listing.seller_organization_id, listing.serial_range_id)))


def disclosure(db: Session, b: CreditBatch, serial_range_id: uuid.UUID | None) -> dict[str, Any]:
    """Allow-listed listing disclosure (spec §25, D25): project, standard, methodology, vintage, verification status, registry, issuance.
    Never farmer, farm, location, KYC, bank, MRV, laboratory, calculation-internal or VVB-internal data."""
    proj = db.get(Project, b.project_id)
    mp = db.get(MonitoringPeriod, b.monitoring_period_id)
    mv = db.get(MethodologyVersion, b.methodology_version_id) if b.methodology_version_id else None
    std = db.get(Standard, b.standard_id) if b.standard_id else None
    iss = db.get(CreditIssuance, b.issuance_id)
    dec = db.get(VerificationDecision, b.verification_decision_id) if getattr(b, "verification_decision_id", None) else None
    reg = db.get(Organization, b.registry_organization_id)
    sr = db.get(CreditSerialRange, serial_range_id) if serial_range_id else None
    return {"project_code": proj.project_code if proj else None, "project_name": proj.name if proj else None,
            "standard": std.code if std else None, "methodology": mv.version_label if mv else None, "vintage": b.vintage,
            "monitoring_period": mp.period_number if mp else None, "batch_code": b.batch_code, "unit": b.unit,
            "registry": reg.name if reg else None, "issuance_code": iss.issuance_code if iss else None,
            "external_issuance_id": iss.external_issuance_id if iss else None,
            "verification_status": "VERIFIED (VVB decision recorded)" if dec is not None else None,
            "verification_decision_code": dec.decision_code if dec is not None else None,
            "serial_range": range_text(sr) if sr is not None else "any range of the batch"}


def _seal(d: dict[str, Any]) -> tuple[str, str]:
    body = json.dumps(d, sort_keys=True, separators=(",", ":"), default=str)
    return body, hashlib.sha256(body.encode()).hexdigest()


def expire_listing_if_due(db: Session, ctx: RequestContext, listing: MarketplaceListing) -> bool:
    """D5: lazy expiry (no worker) — checked on read and before relevant writes."""
    if listing.status not in ("ACTIVE", "PAUSED") or listing.valid_until is None or listing.valid_until > utcnow():
        return False

    def op() -> bool:
        lst = lock(db, MarketplaceListing, listing.id)
        if lst.status not in ("ACTIVE", "PAUSED") or lst.valid_until is None or lst.valid_until > utcnow():
            return False
        frm = transition(db, ctx, LISTING_MACHINE, lst, LISTING_ENTITY, "EXPIRED", "valid_until passed")
        lst.closed_at = utcnow()
        ls.audit(db, ctx, "MARKETPLACE_LISTING_EXPIRED", LISTING_ENTITY, lst.id, [lst.seller_organization_id],
                 {"listing_code": lst.listing_code, "status": "EXPIRED"}, None, {"status": frm})
        return True
    return ls.run(db, ctx, op)


def get_listing(db: Session, ctx: RequestContext, principal: Principal, listing_id: uuid.UUID) -> MarketplaceListing:
    lst = db.get(MarketplaceListing, listing_id)
    if lst is None:
        raise nf("Listing", "LISTING_NOT_FOUND")
    expire_listing_if_due(db, ctx, lst)
    if not can_see_listing(principal, lst):
        raise nf("Listing", "LISTING_NOT_FOUND")
    return lst


def is_seller_side(principal: Principal, lst: MarketplaceListing) -> bool:
    return any(principal.can_in_org(c, lst.seller_organization_id) for c in SELLER_VIEW)


def can_see_listing(principal: Principal, lst: MarketplaceListing) -> bool:
    if is_seller_side(principal, lst):
        return True
    return lst.status == "ACTIVE" and principal.has(P.MARKETPLACE_READ) and lst.environment == env_of(principal)


def listings(db: Session, ctx: RequestContext, principal: Principal, *, mine: bool = False, status: str | None = None,
             limit: int | None = None, offset: int = 0) -> list[MarketplaceListing]:
    """Phase 12B D32: scoped in SQL with the visibility of `can_see_listing` / `is_seller_side`, optionally paged. Lazy expiry stays:
    due listings within that scope are expired first (each re-checked under its lock), so the page shows their current state."""
    seller = org_predicate(principal, SELLER_VIEW, MarketplaceListing.seller_organization_id)
    buyer = and_(MarketplaceListing.status == "ACTIVE", MarketplaceListing.environment == env_of(principal)) \
        if principal.has(P.MARKETPLACE_READ) else false()
    scope = seller if mine else or_(seller, buyer)
    due = select(MarketplaceListing).where(scope, MarketplaceListing.status.in_(("ACTIVE", "PAUSED")),
                                           MarketplaceListing.valid_until <= utcnow())
    for lst in db.scalars(due).all():
        expire_listing_if_due(db, ctx, lst)
    stmt = select(MarketplaceListing).where(scope).order_by(MarketplaceListing.created_at.desc(), MarketplaceListing.id)
    if status:
        stmt = stmt.where(MarketplaceListing.status == status)
    if limit is not None:
        stmt = stmt.offset(offset).limit(limit)
    rows = db.scalars(stmt.execution_options(populate_existing=True)).all()
    return [x for x in rows if (is_seller_side(principal, x) if mine else can_see_listing(principal, x))]


def _check_quantity(db: Session, b: CreditBatch, seller_id: uuid.UUID, serial_range_id: uuid.UUID | None, quantity: Decimal) -> None:
    have = seller_available(db, b, seller_id, serial_range_id)
    if have <= 0:
        raise Conflict("The seller holds no AVAILABLE ledger credits in this batch.", error_code="NO_AVAILABLE_CREDITS")
    if quantity > have:
        raise Conflict(f"The listed quantity ({quantity}) exceeds the seller's AVAILABLE ledger credits ({have}).",
                       error_code="LISTED_QUANTITY_EXCEEDS_AVAILABLE", details={"available": str(have)})


def create_listing(db: Session, ctx: RequestContext, principal: Principal, data: Any, key: str | None) -> MarketplaceListing:
    if key and (prior := db.scalars(select(MarketplaceListing).where(MarketplaceListing.request_key == key)).first()) is not None:
        return prior
    seller = org(db, data.seller_organization_id)
    require(principal, seller.id, P.LISTINGS_MANAGE, visible=SELLER_VIEW, what="Organization", nf_code="ORGANIZATION_NOT_FOUND")
    if seller.org_type not in SELLER_ORG_TYPES or seller.status != "ACTIVE":
        raise Conflict("Only an active project-developer organization can sell (no buyer resale in Phase 10).", error_code="NOT_A_SELLER")
    b = db.get(CreditBatch, data.batch_id)
    if b is None or b.environment != seller.environment:
        raise nf("Credit batch", "CREDIT_BATCH_NOT_FOUND")
    if b.status != "ISSUED":
        raise Conflict(f"Only registry-issued credits can be listed (this batch is {b.status}).", error_code="BATCH_NOT_ISSUED")
    ls._source(db, b, data.serial_range_id)
    qty = Decimal(data.listed_quantity)
    _check_quantity(db, b, seller.id, data.serial_range_id, qty)
    currency = data.currency.upper()
    price = money(data.unit_price, currency, "unit price")
    if data.min_quantity and data.max_quantity and data.max_quantity < data.min_quantity:
        raise ValidationFailed("The maximum order quantity is below the minimum.", error_code="QUANTITY_RANGE_INVALID")
    if data.min_quantity and data.min_quantity > qty:
        raise ValidationFailed("The minimum order quantity exceeds the listed quantity.", error_code="QUANTITY_RANGE_INVALID")
    valid_until = ls.naive_utc(data.valid_until) if data.valid_until else None
    if valid_until is not None and valid_until <= utcnow():
        raise ValidationFailed("valid_until must be in the future.", error_code="VALID_UNTIL_IN_PAST")
    d = disclosure(db, b, data.serial_range_id)
    body, sha = _seal(d)
    lst = MarketplaceListing(listing_code=next_code(db, "listing", utcnow().year), seller_organization_id=seller.id, batch_id=b.id,
                             serial_range_id=data.serial_range_id, title=data.title, listed_quantity=qty, unit_price=price, currency=currency,
                             min_quantity=data.min_quantity, max_quantity=data.max_quantity, payment_window_hours=data.payment_window_hours,
                             valid_until=valid_until, co_benefits=data.co_benefits, disclosure=body, disclosure_sha256=sha, status="DRAFT",
                             created_by=principal.user_id, request_key=key, environment=b.environment)
    db.add(lst)
    db.flush()
    ls.workflow(db, ctx, LISTING_ENTITY, lst.id, None, "DRAFT", None)
    ls.audit(db, ctx, "MARKETPLACE_LISTING_CREATED", LISTING_ENTITY, lst.id, [seller.id],
             {"listing_code": lst.listing_code, "batch_code": b.batch_code, "listed_quantity": str(qty), "unit_price": str(price),
              "currency": currency, "status": "DRAFT"})
    db.commit()
    return lst


def _seller_listing(db: Session, ctx: RequestContext, principal: Principal, listing_id: uuid.UUID, *codes: str) -> MarketplaceListing:
    lst = db.get(MarketplaceListing, listing_id)
    if lst is None or not (is_seller_side(principal, lst) or can_see_listing(principal, lst)):
        raise nf("Listing", "LISTING_NOT_FOUND")
    expire_listing_if_due(db, ctx, lst)
    if not any(principal.can_in_org(c, lst.seller_organization_id) for c in codes):
        raise PermissionDenied(details={"required_permission": " or ".join(codes)})   # visible (catalogue or seller side) but not allowed
    return lst


def listing_action(db: Session, ctx: RequestContext, principal: Principal, listing_id: uuid.UUID, action: str, reason: str | None,
                   key: str | None) -> MarketplaceListing:
    """submit (DRAFT → PENDING_APPROVAL), approve (→ ACTIVE; never the creator), pause / resume, close (CLOSED, or CANCELLED before
    approval)."""
    codes = {"approve": (P.LISTINGS_APPROVE,), "close": (P.LISTINGS_MANAGE, P.LISTINGS_APPROVE)}.get(action, (P.LISTINGS_MANAGE,))
    lst = _seller_listing(db, ctx, principal, listing_id, *codes)    # an approver may also decline (cancel) a submitted listing
    target = {"submit": "PENDING_APPROVAL", "approve": "ACTIVE", "pause": "PAUSED", "resume": "ACTIVE",
              "close": "CANCELLED" if lst.status in ("DRAFT", "PENDING_APPROVAL") else "CLOSED"}[action]
    if replay_action(lst, key, target):
        return lst

    def op() -> MarketplaceListing:
        x = lock(db, MarketplaceListing, lst.id)
        if action == "approve":
            if x.created_by == principal.user_id:
                raise PermissionDenied("You created this listing, so someone else must approve it.", error_code="SEPARATION_OF_DUTIES")
            if x.status != "PENDING_APPROVAL":
                raise Conflict(f"The listing is {x.status}.", error_code="LISTING_NOT_PENDING")
        if action in ("approve", "resume"):
            if x.valid_until is not None and x.valid_until <= utcnow():
                raise Conflict("The listing's validity has passed.", error_code="LISTING_EXPIRED")
            b = ls.get_batch(db, x.batch_id)
            if action == "approve":
                _check_quantity(db, b, x.seller_organization_id, x.serial_range_id, x.listed_quantity)
                if b.status != "ISSUED":
                    raise Conflict(f"The batch is {b.status}.", error_code="BATCH_NOT_ISSUED")
                x.disclosure, x.disclosure_sha256 = _seal(disclosure(db, b, x.serial_range_id))      # frozen from now on (trigger)
            clash = db.scalars(select(MarketplaceListing).where(
                MarketplaceListing.seller_organization_id == x.seller_organization_id, MarketplaceListing.batch_id == x.batch_id,
                (MarketplaceListing.serial_range_id == x.serial_range_id) if x.serial_range_id else MarketplaceListing.serial_range_id.is_(None),
                MarketplaceListing.status.in_(("ACTIVE", "PAUSED")), MarketplaceListing.id != x.id)).first()
            if clash is not None:
                raise Conflict(f"Listing {clash.listing_code} already offers this batch / range.", error_code="LISTING_EXISTS")
        if action == "close" and not (reason and reason.strip()):
            raise ValidationFailed("Give a reason.", error_code="REASON_REQUIRED")
        frm = transition(db, ctx, LISTING_MACHINE, x, LISTING_ENTITY, target, reason)
        x.action_key = key
        now = utcnow()
        if action == "submit":
            x.submitted_by, x.submitted_at = principal.user_id, now
        elif action == "approve":
            x.approved_by, x.approved_at = principal.user_id, now
        elif action == "close":
            x.closed_by, x.closed_at, x.close_reason = principal.user_id, now, reason
        event = {"submit": "MARKETPLACE_LISTING_SUBMITTED", "approve": "MARKETPLACE_LISTING_APPROVED", "pause": "MARKETPLACE_LISTING_PAUSED",
                 "resume": "MARKETPLACE_LISTING_RESUMED",
                 "close": "MARKETPLACE_LISTING_CANCELLED" if target == "CANCELLED" else "MARKETPLACE_LISTING_CLOSED"}[action]
        ls.audit(db, ctx, event, LISTING_ENTITY, x.id, [x.seller_organization_id],
                 {"listing_code": x.listing_code, "status": target, "disclosure_sha256": x.disclosure_sha256}, reason, {"status": frm})
        return x
    return ls.run(db, ctx, op)


def upload_listing_document(db: Session, ctx: RequestContext, principal: Principal, listing_id: uuid.UUID, filename: str | None, data: bytes,
                            title: str | None) -> Document:
    lst = _seller_listing(db, ctx, principal, listing_id, P.LISTINGS_MANAGE)
    if lst.status not in ("DRAFT", "PENDING_APPROVAL"):
        raise Conflict("Documents can be published on a listing before it is approved.", error_code="LISTING_LOCKED")
    doc = document_service.create_document(db, ctx, entity_type=LISTING_ENTITY, entity_id=lst.id, organization_id=lst.seller_organization_id,
                                           environment=lst.environment, category=DocumentCategory.LISTING_DOCUMENT.value,
                                           title=title or "Listing document", filename=filename, data=data)
    db.add(ListingDocument(listing_id=lst.id, document_id=doc.id, published_by=principal.user_id))
    db.commit()
    return doc


def _listing_resolver(db: Session, principal: Principal, entity_id: uuid.UUID, kind: str) -> None:
    lst = db.get(MarketplaceListing, entity_id)
    if kind == "manage":
        raise PermissionDenied("Published listing documents are immutable.", error_code="DOCUMENT_IMMUTABLE")
    if lst is None or not can_see_listing(principal, lst):
        raise NotFound("Document not found.", error_code="DOCUMENT_NOT_FOUND")


document_service.register_resolver(LISTING_ENTITY, _listing_resolver)


def lock_listings(db: Session, listing_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, MarketplaceListing]:
    """D26: listings are always locked first, in id order (then order → payment → reservation → positions)."""
    out = {}
    for lid in sorted(set(listing_ids), key=str):
        x = lock(db, MarketplaceListing, lid)
        if x is None:
            raise nf("Listing", "LISTING_NOT_FOUND")
        out[lid] = x
    return out


def is_due(dt: datetime | None) -> bool:
    return dt is not None and dt <= utcnow()


def demo_note(principal: Principal, has_rows: bool) -> str | None:
    return DEMO_NOTE if env_of(principal) == "DEMO" and not has_rows else None


def orders_on(db: Session, listing_ids: Iterable[uuid.UUID]) -> list[Order]:
    ids = list(listing_ids)
    if not ids:
        return []
    return list(db.scalars(select(Order).where(Order.id.in_(select(OrderItem.order_id).where(OrderItem.listing_id.in_(ids))),
                                               Order.status == "PLACED")).all())
