"""Phase 10 orders (D6, D11–D14, D18, D20–D24, D26).

T1 — placement is ONE transaction: KYC gate → listings locked (id order) → listing state / expiry / quantity under the lock → order + items →
one Phase 9B reservation per item through `ledger_service.reserve_in_tx` (same locking, guarded consumption and posting checks as every
ledger movement). Any failure rolls everything back: no partial order, no partial reservation.

T4 — an order-linked transfer is completed / rejected only through this module (the public 9B endpoints refuse ORDER_LINKED), so the 9B
transfer, the buyer's ownership, the item and the order change in one transaction. The 9B second-person rule (credits.confirm in the
custodian organization, never the requester) is the same `check_completion` / `check_close`.

Ownership is never stored here (D24): items only reference the 9B batch / serial range / reservation / transfer.
"""
import hashlib
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import RequestContext
from app.core.errors import Conflict, PermissionDenied, ValidationFailed
from app.models import (
    CreditBatch,
    CreditLedgerEntry,
    CreditReservation,
    CreditTransfer,
    Document,
    MarketplaceListing,
    Order,
    OrderItem,
    Organization,
    Payment,
)
from app.models.base import utcnow
from app.models.documents import DocumentCategory
from app.reports import pdf
from app.repositories.sequences import next_code
from app.security.permissions import P
from app.security.principal import Principal
from app.services import document_service, finance_service
from app.services import ledger_service as ls
from app.services import marketplace_service as ms
from app.services.workflows import ORDER_ITEM_MACHINE, ORDER_MACHINE

ORDER_ENTITY = "order"
PURPOSE = "MARKETPLACE_ORDER"
BUYER_SIDE = (P.ORDERS_PLACE, P.ORDERS_READ, P.PAYMENTS_RECORD)
SELLER_SIDE = (P.ORDERS_READ, P.ORDERS_MANAGE, P.PAYMENTS_CONFIRM, P.REFUNDS_REQUEST, P.REFUNDS_APPROVE)
T = TypeVar("T")
PAYMENT_HOLDS_ORDER = ("PENDING_CONFIRMATION", "CONFIRMED")      # money reported received: the order is neither cancelled nor expired


# ---------------------------------------------------------------- links owned by orders (9B public actions refuse them)
def _link_guard(db: Session, kind: str, entity_id: uuid.UUID) -> str | None:
    col = OrderItem.reservation_id if kind == "reservation" else OrderItem.transfer_id if kind == "transfer" else None
    if col is None:
        return None
    return db.scalar(select(Order.order_code).join(OrderItem, OrderItem.order_id == Order.id).where(col == entity_id))


ls.register_link_guard(_link_guard)


def linked_order_code(db: Session, kind: str, entity_id: uuid.UUID) -> str | None:
    return _link_guard(db, kind, entity_id)


# ---------------------------------------------------------------- access
def side(principal: Principal, o: Order) -> str | None:
    if any(principal.can_in_org(c, o.buyer_organization_id) for c in BUYER_SIDE):
        return "BUYER"
    if any(principal.can_in_org(c, o.seller_organization_id) for c in SELLER_SIDE):
        return "SELLER"
    return None


def get_order(db: Session, principal: Principal, order_id: uuid.UUID) -> Order:
    o = db.get(Order, order_id)
    if o is None or side(principal, o) is None:
        raise ms.nf("Order", "ORDER_NOT_FOUND")
    return o


def items_of(db: Session, order_id: uuid.UUID) -> list[OrderItem]:
    return list(db.scalars(select(OrderItem).where(OrderItem.order_id == order_id).order_by(OrderItem.item_code)).all())


def visible_orders(db: Session, ctx: RequestContext, principal: Principal, status: str | None = None) -> list[Order]:
    stmt = select(Order).order_by(Order.placed_at.desc())
    if status:
        stmt = stmt.where(Order.status == status)
    out = []
    for o in db.scalars(stmt).all():
        if side(principal, o) is None:
            continue
        expire_if_due(db, ctx, o)
        out.append(o)
    return out


def _item(db: Session, ctx: RequestContext, item: OrderItem, to: str, reason: str | None = None) -> None:
    ms.transition(db, ctx, ORDER_ITEM_MACHINE, item, "order_item", to, reason)


def _order(db: Session, ctx: RequestContext, o: Order, to: str, reason: str | None = None) -> str:
    return ms.transition(db, ctx, ORDER_MACHINE, o, ORDER_ENTITY, to, reason)


def parties(o: Order) -> list[uuid.UUID | None]:
    return [o.buyer_organization_id, o.seller_organization_id]


# ---------------------------------------------------------------- T1 placement
def place(db: Session, ctx: RequestContext, principal: Principal, data: Any, key: str | None) -> Order:
    if key and (prior := db.scalars(select(Order).where(Order.request_key == key)).first()) is not None:
        if prior.buyer_organization_id != data.buyer_organization_id:
            raise Conflict("This Idempotency-Key was used for another request.", error_code="IDEMPOTENCY_KEY_REUSED")
        return prior
    buyer = ms.org(db, data.buyer_organization_id)
    ms.require(principal, buyer.id, P.ORDERS_PLACE, visible=BUYER_SIDE, what="Organization", nf_code="ORGANIZATION_NOT_FOUND")
    if buyer.org_type != "BUYER":
        raise Conflict("Orders are placed by buyer organizations.", error_code="NOT_A_BUYER")
    ms.require_kyc(db, buyer.id)                                    # D1
    ids = [i.listing_id for i in data.items]
    if len(set(ids)) != len(ids):
        raise ValidationFailed("Each listing may appear once in an order.", error_code="DUPLICATE_LISTING")
    if data.transfer_kind == "REGISTRY" and not (data.recipient_registry_account or "").strip():
        raise ValidationFailed("A registry transfer needs the buyer's registry account.", error_code="RECIPIENT_ACCOUNT_REQUIRED")
    pre = {}
    for lid in ids:
        lst = db.get(MarketplaceListing, lid)
        if lst is None or not ms.can_see_listing(principal, lst):
            raise ms.nf("Listing", "LISTING_NOT_FOUND")
        ms.expire_listing_if_due(db, ctx, lst)
        pre[lid] = lst
    sellers = {x.seller_organization_id for x in pre.values()}
    if len(sellers) != 1:
        raise ValidationFailed("All items of an order must come from the same seller (place one order per seller).",
                               error_code="SINGLE_SELLER_REQUIRED")
    if len({x.currency for x in pre.values()}) != 1:
        raise ValidationFailed("All items of an order must use the same currency.", error_code="SINGLE_CURRENCY_REQUIRED")
    seller_id = next(iter(sellers))
    for o in ms.orders_on(db, ids):                                # lazily expire unpaid orders on these listings first
        expire_if_due(db, ctx, o)
    ls.expire_due(db, ctx, batch_ids=list({x.batch_id for x in pre.values()}))
    ls._recipient(db, buyer.id, next(iter(pre.values())).environment)
    qty = {i.listing_id: Decimal(i.quantity) for i in data.items}

    def op() -> Order:
        locked = ms.lock_listings(db, ids)                         # D26: listing locks first, in id order
        now = utcnow()
        for lid, lst in locked.items():
            if lst.status != "ACTIVE" or ms.is_due(lst.valid_until):
                raise Conflict(f"Listing {lst.listing_code} is not available ({lst.status}).", error_code="LISTING_NOT_ACTIVE")
            if lst.environment != buyer.environment:
                raise Conflict("Demo and live records cannot be mixed.", error_code="ENVIRONMENT_MISMATCH")
            q = qty[lid]
            if (lst.min_quantity and q < lst.min_quantity) or (lst.max_quantity and q > lst.max_quantity):
                raise ValidationFailed(f"Listing {lst.listing_code} accepts orders of {lst.min_quantity or 1}–{lst.max_quantity or 'any'} credits.",
                                       error_code="QUANTITY_OUT_OF_RANGE")
            left = ms.remaining(db, lst)                            # derived under the listing lock (no stored balance)
            if q > left:
                raise Conflict(f"Only {left} credits remain on listing {lst.listing_code}.", error_code="LISTING_QUANTITY_EXCEEDED",
                               details={"remaining": str(left), "requested": str(q)})
        window = min(lst.payment_window_hours for lst in locked.values())
        code = next_code(db, "order", now.year)
        subtotal = sum((locked[lid].unit_price * qty[lid] for lid in ids), Decimal(0))
        o = Order(order_code=code, buyer_organization_id=buyer.id, seller_organization_id=seller_id, currency=locked[ids[0]].currency,
                  subtotal=subtotal, total=subtotal, transfer_kind=data.transfer_kind,
                  recipient_registry_account=(data.recipient_registry_account or "").strip() or None if data.transfer_kind == "REGISTRY" else None,
                  status="PLACED", expires_at=now + timedelta(hours=window), placed_by=principal.user_id, request_key=key,
                  environment=buyer.environment)
        db.add(o)
        db.flush()
        for n, lid in enumerate(sorted(ids, key=str), start=1):
            lst = locked[lid]
            b = ls.get_batch(db, lst.batch_id)
            it = OrderItem(item_code=f"{code}-{n}", order_id=o.id, listing_id=lst.id, batch_id=lst.batch_id, serial_range_id=lst.serial_range_id,
                           quantity=qty[lid], unit_price=lst.unit_price, line_total=lst.unit_price * qty[lid], status="RESERVED")
            db.add(it)
            r = ls.reserve_in_tx(db, ctx, batch=b, owner_id=seller_id, quantity=qty[lid], actor_id=principal.user_id, purpose=PURPOSE,
                                 purpose_reference=it.item_code, recipient_id=buyer.id, serial_range_id=lst.serial_range_id,
                                 expires_at=o.expires_at)
            it.reservation_id = r.id
        db.flush()
        ls.workflow(db, ctx, ORDER_ENTITY, o.id, None, "PLACED", None)
        ls.audit(db, ctx, "ORDER_PLACED", ORDER_ENTITY, o.id, parties(o),
                 {"order_code": o.order_code, "items": len(ids), "currency": o.currency, "total": str(o.total), "expires_at": o.expires_at,
                  "transfer_kind": o.transfer_kind})
        return o
    return ls.run(db, ctx, op, conflict_org=seller_id)


# ---------------------------------------------------------------- lazy expiry (D18)
def _holds(db: Session, o: Order) -> bool:
    return db.scalars(select(Payment.id).where(Payment.order_id == o.id, Payment.status.in_(PAYMENT_HOLDS_ORDER))).first() is not None


def expire_if_due(db: Session, ctx: RequestContext, o: Order) -> bool:
    """An unpaid PLACED order past its payment deadline expires with its 9B reservations (D18). A payment the buyer reported received
    (PENDING_CONFIRMATION) holds the order for the seller's finance decision (its 9B reservations still expire on their own)."""
    if o.status != "PLACED" or not ms.is_due(o.expires_at) or _holds(db, o):
        return False

    def op() -> bool:
        x = ms.lock(db, Order, o.id)
        if x.status != "PLACED" or not ms.is_due(x.expires_at) or _holds(db, x):
            return False
        for it in items_of(db, x.id):
            r = ls.lock_reservation(db, it.reservation_id) if it.reservation_id else None
            if r is not None and r.status == "ACTIVE":
                ls.expire_reservation_in_tx(db, ctx, r, ctx.user_id or r.created_by)
            if it.status == "RESERVED":
                _item(db, ctx, it, "EXPIRED", "payment deadline passed")
        frm = _order(db, ctx, x, "EXPIRED", "payment deadline passed")
        x.closed_at, x.close_reason = utcnow(), "Payment deadline passed"
        ls.audit(db, ctx, "ORDER_EXPIRED", ORDER_ENTITY, x.id, parties(x), {"order_code": x.order_code, "status": "EXPIRED"}, None,
                 {"status": frm})
        return True
    return ls.run(db, ctx, op)


# ---------------------------------------------------------------- cancel (PLACED only)
def cancel(db: Session, ctx: RequestContext, principal: Principal, order_id: uuid.UUID, reason: str, key: str | None) -> Order:
    o = get_order(db, principal, order_id)
    if ms.replay_action(o, key, "CANCELLED"):
        return o
    if not (principal.can_in_org(P.ORDERS_PLACE, o.buyer_organization_id) or principal.can_in_org(P.ORDERS_MANAGE, o.seller_organization_id)):
        raise PermissionDenied(details={"required_permission": "orders.place (buyer) or orders.manage (seller)"})
    expire_if_due(db, ctx, o)

    def op() -> Order:
        x = ms.lock(db, Order, o.id)
        if x.status != "PLACED":
            raise Conflict(f"Only an unpaid order can be cancelled (this one is {x.status}).", error_code="ORDER_NOT_CANCELLABLE")
        if _holds(db, x):
            raise Conflict("A payment for this order is awaiting confirmation; the seller's finance team must decide first.",
                           error_code="PAYMENT_IN_PROGRESS")
        for it in items_of(db, x.id):
            r = ls.lock_reservation(db, it.reservation_id) if it.reservation_id else None
            if r is not None and r.status == "ACTIVE":
                ls.release_in_tx(db, ctx, r, principal.user_id, f"Order {x.order_code} cancelled: {reason}")
            if it.status == "RESERVED":
                _item(db, ctx, it, "RELEASED" if r is None or r.status in ("RELEASED", "ACTIVE") else "EXPIRED", reason)
        frm = _order(db, ctx, x, "CANCELLED", reason)
        x.closed_by, x.closed_at, x.close_reason, x.action_key = principal.user_id, utcnow(), reason, key
        ls.audit(db, ctx, "ORDER_CANCELLED", ORDER_ENTITY, x.id, parties(x), {"order_code": x.order_code, "status": "CANCELLED"}, reason,
                 {"status": frm})
        return x
    return ls.run(db, ctx, op)


# ---------------------------------------------------------------- T4 order-linked transfer completion / rejection (D20, D23)
def _by_transfer(db: Session, transfer_id: uuid.UUID) -> tuple[Order, OrderItem, CreditTransfer]:
    it = db.scalars(select(OrderItem).where(OrderItem.transfer_id == transfer_id)).first()
    t = db.get(CreditTransfer, transfer_id)
    if it is None or t is None:
        raise ms.nf("Order-linked transfer", "ORDER_TRANSFER_NOT_FOUND")
    o = db.get(Order, it.order_id)
    assert o is not None
    return o, it, t


def complete_transfer(db: Session, ctx: RequestContext, principal: Principal, transfer_id: uuid.UUID, data: Any, key: str | None) -> Order:
    o, it, t = _by_transfer(db, transfer_id)
    ls._transfer(db, principal, t.id)                               # 9B visibility (404 outside)
    if ls.entry_replay(db, key, "TRANSFER_COMPLETE", transfer_id=t.id) is not None:
        return o
    ls.check_completion(db, principal, t, data)                     # credits.confirm in the custodian organization, ≠ requester, evidence
    ms.require_kyc(db, o.buyer_organization_id)                     # D1: no marketplace delivery to an unverified / suspended buyer
    b = ls.get_batch(db, t.batch_id)

    def op() -> Order:
        x = ms.lock(db, Order, o.id)                                # D26: order → transfer → positions
        tr = _must(ls.lock_transfer(db, t.id))
        item = _must(db.get(OrderItem, it.id))
        if x.status not in ("TRANSFER_PENDING", "ATTENTION_REQUIRED") or item.status != "TRANSFER_PENDING" or item.transfer_id != tr.id:
            raise Conflict(f"Order {x.order_code} is {x.status}; this delivery cannot be completed now.", error_code="ORDER_NOT_DELIVERABLE")
        ls.complete_transfer_in_tx(db, ctx, tr, batch=b, confirmer_id=principal.user_id, data=data, key=key)
        _item(db, ctx, item, "DELIVERED")
        finance_service.recognize_in_tx(db, ctx, order=x, item=item, actor_id=principal.user_id)   # Phase 11 D8 / D9 (same transaction)
        if all(i.status == "DELIVERED" for i in items_of(db, x.id)) and x.status == "TRANSFER_PENDING":
            frm = _order(db, ctx, x, "COMPLETED")
            x.completed_at = utcnow()
            ls.audit(db, ctx, "ORDER_COMPLETED", ORDER_ENTITY, x.id, parties(x), {"order_code": x.order_code, "status": "COMPLETED"}, None,
                     {"status": frm})
        return x
    return ls.run(db, ctx, op)


def reject_transfer(db: Session, ctx: RequestContext, principal: Principal, transfer_id: uuid.UUID, reason: str, key: str | None) -> Order:
    """The custodian refuses the delivery: credits return to the seller (9B), the item FAILS and the order needs attention (no retry)."""
    o, it, t = _by_transfer(db, transfer_id)
    ls._transfer(db, principal, t.id)
    if ls.entry_replay(db, key, "TRANSFER_REJECT", transfer_id=t.id) is not None:
        return o
    ls.check_close(db, principal, t, "REJECTED")
    b = ls.get_batch(db, t.batch_id)

    def op() -> Order:
        x = ms.lock(db, Order, o.id)
        tr = _must(ls.lock_transfer(db, t.id))
        item = _must(db.get(OrderItem, it.id))
        if item.status != "TRANSFER_PENDING" or item.transfer_id != tr.id:
            raise Conflict(f"The delivery of item {item.item_code} is not pending.", error_code="ORDER_NOT_DELIVERABLE")
        ls.close_transfer_in_tx(db, ctx, tr, batch=b, to="REJECTED", actor_id=principal.user_id, reason=reason, key=key)
        _item(db, ctx, item, "FAILED", reason)
        attention(db, ctx, x, f"Transfer {tr.transfer_code} rejected: {reason}")
        return x
    return ls.run(db, ctx, op)


def _must(x: T | None) -> T:
    if x is None:
        raise ms.nf("Record", "NOT_FOUND")
    return x


def attention(db: Session, ctx: RequestContext, x: Order, why: str) -> None:
    x.attention_reason = why
    if x.status == "ATTENTION_REQUIRED":
        return
    frm = _order(db, ctx, x, "ATTENTION_REQUIRED", why)
    ls.audit(db, ctx, "ORDER_ATTENTION_REQUIRED", ORDER_ENTITY, x.id, parties(x), {"order_code": x.order_code, "reason": why}, why,
             {"status": frm})


# ---------------------------------------------------------------- manual resolution: re-reserve + re-request the transfer (D23)
def retry_transfer(db: Session, ctx: RequestContext, principal: Principal, order_id: uuid.UUID, reason: str, key: str | None) -> Order:
    o = get_order(db, principal, order_id)
    if ms.replay_action(o, key, "TRANSFER_PENDING"):
        return o
    ms.require(principal, o.seller_organization_id, P.ORDERS_MANAGE, visible=(*SELLER_SIDE, *BUYER_SIDE), what="Order", nf_code="ORDER_NOT_FOUND")
    ms.require_kyc(db, o.buyer_organization_id)
    ls.expire_due(db, ctx, batch_ids=list({i.batch_id for i in items_of(db, o.id)}))

    def op() -> Order:
        x = ms.lock(db, Order, o.id)
        if x.status != "ATTENTION_REQUIRED":
            raise Conflict(f"Only an order that needs attention can be resolved this way (this one is {x.status}).",
                           error_code="ORDER_NOT_IN_ATTENTION")
        for item in items_of(db, x.id):
            if item.status not in ("FAILED", "RESERVED"):
                continue
            request_delivery(db, ctx, x, item, principal.user_id, reuse_active=True)
        frm = _order(db, ctx, x, "TRANSFER_PENDING", reason)
        x.attention_reason, x.action_key = None, key
        ls.audit(db, ctx, "ORDER_RESOLVED", ORDER_ENTITY, x.id, parties(x), {"order_code": x.order_code, "status": "TRANSFER_PENDING"}, reason,
                 {"status": frm})
        return x
    return ls.run(db, ctx, op, conflict_org=o.seller_organization_id)


def request_delivery(db: Session, ctx: RequestContext, x: Order, item: OrderItem, actor_id: uuid.UUID, *, reuse_active: bool) -> CreditTransfer:
    """Consume the item's ACTIVE 9B reservation (re-reserving from the seller's AVAILABLE positions when it was lost) into a 9B transfer
    request — inside the caller's transaction."""
    b = ls.get_batch(db, item.batch_id)
    r = ls.lock_reservation(db, item.reservation_id) if item.reservation_id else None
    if r is not None and r.status == "ACTIVE" and ms.is_due(r.expires_at):
        ls.expire_reservation_in_tx(db, ctx, r, actor_id)
    if not (reuse_active and r is not None and r.status == "ACTIVE"):
        lst = db.get(MarketplaceListing, item.listing_id)
        r = ls.reserve_in_tx(db, ctx, batch=b, owner_id=x.seller_organization_id, quantity=item.quantity, actor_id=actor_id, purpose=PURPOSE,
                             purpose_reference=item.item_code, recipient_id=x.buyer_organization_id, serial_range_id=item.serial_range_id,
                             expires_at=utcnow() + timedelta(hours=lst.payment_window_hours if lst else 1))
        item.reservation_id = r.id
        db.flush()
    t = ls.request_transfer_in_tx(db, ctx, batch=b, kind=x.transfer_kind, sender_id=x.seller_organization_id, recipient_id=x.buyer_organization_id,
                                  actor_id=actor_id, reservation_id=r.id, recipient_external_account_id=x.recipient_registry_account,
                                  purpose=PURPOSE, purpose_reference=item.item_code)
    item.transfer_id = t.id
    db.flush()
    _item(db, ctx, item, "TRANSFER_PENDING")
    return t


# ---------------------------------------------------------------- documents, confirmation PDF, lineage
def upload_document(db: Session, ctx: RequestContext, principal: Principal, order_id: uuid.UUID, filename: str | None, data: bytes,
                    title: str | None) -> Document:
    """The buyer's payment evidence (PAYMENT_EVIDENCE, PDF) — attached to the order before the payment is recorded."""
    o = get_order(db, principal, order_id)
    ms.require(principal, o.buyer_organization_id, P.PAYMENTS_RECORD, P.ORDERS_PLACE, visible=(*BUYER_SIDE, *SELLER_SIDE), what="Order",
               nf_code="ORDER_NOT_FOUND")
    if o.status != "PLACED":
        raise Conflict(f"Payment evidence can be added to an unpaid order (this one is {o.status}).", error_code="ORDER_NOT_PAYABLE")
    doc = document_service.create_document(db, ctx, entity_type=ORDER_ENTITY, entity_id=o.id, organization_id=o.buyer_organization_id,
                                           environment=o.environment, category=DocumentCategory.PAYMENT_EVIDENCE.value,
                                           title=title or "Payment evidence", filename=filename, data=data)
    ls.audit(db, ctx, "ORDER_DOCUMENT_ADDED", ORDER_ENTITY, o.id, parties(o), {"document_id": doc.id, "category": doc.category})
    db.commit()
    return doc


def confirmation_lines(db: Session, o: Order) -> list[str]:
    """Deterministic content (D10, D29): the same order data always gives the same PDF bytes. Not a tax invoice."""
    buyer, seller = db.get(Organization, o.buyer_organization_id), db.get(Organization, o.seller_organization_id)
    pay = db.scalars(select(Payment).where(Payment.order_id == o.id, Payment.status.in_(("CONFIRMED", "REFUNDED")))).first()
    lines = ["ORDER CONFIRMATION", "This document confirms a marketplace order. It is NOT a tax invoice; no tax or fee is calculated.", "",
             f"Order: {o.order_code}    Placed: {o.placed_at:%Y-%m-%d}    Status: {o.status}",
             f"Buyer: {buyer.name if buyer else '-'} ({buyer.code if buyer else '-'})",
             f"Seller (payee): {seller.name if seller else '-'} ({seller.code if seller else '-'})",
             f"Delivery: {o.transfer_kind} ledger transfer" + (f" to registry account {o.recipient_registry_account}" if o.recipient_registry_account
                                                               else ""), "", "Items:"]
    for it in items_of(db, o.id):
        lst = db.get(MarketplaceListing, it.listing_id)
        b = db.get(CreditBatch, it.batch_id)
        lines.append(f"  {it.item_code}  listing {lst.listing_code if lst else '-'}  batch {b.batch_code if b else '-'}  vintage "
                     f"{b.vintage if b else '-'}  quantity {it.quantity} credits  x  {it.unit_price} {o.currency}  =  {it.line_total} {o.currency}")
    lines += ["", f"Total: {o.total} {o.currency} (gross; no fee, commission or tax)"]
    if pay is not None:
        lines.append(f"Payment: {pay.payment_code}  reference {pay.external_reference or '-'}  confirmed {pay.confirmed_at:%Y-%m-%d}"
                     if pay.confirmed_at else f"Payment: {pay.payment_code}")
    lines += ["", "Credit quantities are registry-issued credits recorded in the platform's credit ledger; ownership changes only when the",
              "ledger transfer is completed by the custodian (second person)."]
    return lines


def confirmation(db: Session, ctx: RequestContext, principal: Principal, order_id: uuid.UUID) -> Document:
    o = get_order(db, principal, order_id)
    if o.status not in ("PAID", "TRANSFER_PENDING", "COMPLETED", "ATTENTION_REQUIRED", "REFUND_PENDING", "REFUNDED"):
        raise Conflict("An order confirmation exists only once the payment is confirmed.", error_code="ORDER_NOT_PAID")
    data = pdf.render(confirmation_lines(db, o))
    sha = hashlib.sha256(data).hexdigest()
    for d in document_service.list_for(db, ORDER_ENTITY, o.id):
        if d.category == DocumentCategory.ORDER_CONFIRMATION.value and any(v.checksum_sha256 == sha for v in d.versions):
            return d                                                 # deterministic: same content → the existing document
    doc = document_service.create_document(db, ctx, entity_type=ORDER_ENTITY, entity_id=o.id, organization_id=o.seller_organization_id,
                                           environment=o.environment, category=DocumentCategory.ORDER_CONFIRMATION.value,
                                           title=f"Order confirmation {o.order_code}", filename=f"{o.order_code}-confirmation.pdf", data=data)
    ls.audit(db, ctx, "ORDER_CONFIRMATION_GENERATED", ORDER_ENTITY, o.id, parties(o), {"document_id": doc.id, "sha256": sha})
    db.commit()
    return doc


def lineage(db: Session, principal: Principal, order_id: uuid.UUID) -> dict[str, Any]:
    """order → items → listing → 9B reservation → 9B transfer → ledger entry → batch. The credit chain beyond the batch is the existing
    9A lineage (credits.read only); buyers stop at the batch, as in the 9B holder view."""
    o = get_order(db, principal, order_id)
    chain: list[dict[str, Any]] = [{"kind": "ORDER", "code": o.order_code, "status": o.status}]
    for it in items_of(db, o.id):
        lst = db.get(MarketplaceListing, it.listing_id)
        r = db.get(CreditReservation, it.reservation_id) if it.reservation_id else None
        t = db.get(CreditTransfer, it.transfer_id) if it.transfer_id else None
        e = db.scalars(select(CreditLedgerEntry).where(CreditLedgerEntry.transfer_id == t.id, CreditLedgerEntry.entry_type == "TRANSFER_COMPLETE")
                       ).first() if t else None
        b = db.get(CreditBatch, it.batch_id)
        chain += [{"kind": "ORDER_ITEM", "code": it.item_code, "status": it.status, "quantity": int(it.quantity)},
                  {"kind": "LISTING", "code": lst.listing_code if lst else None, "disclosure_sha256": lst.disclosure_sha256 if lst else None},
                  {"kind": "CREDIT_RESERVATION", "code": r.reservation_code if r else None, "status": r.status if r else None},
                  {"kind": "CREDIT_TRANSFER", "code": t.transfer_code if t else None, "status": t.status if t else None},
                  {"kind": "LEDGER_ENTRY", "code": e.entry_code if e else None, "type": e.entry_type if e else None},
                  {"kind": "CREDIT_BATCH", "id": str(it.batch_id), "code": b.batch_code if b else None,
                   "batch_lineage": f"/api/v1/credits/batches/{it.batch_id}/lineage"
                   if principal.can_in_org(P.CREDITS_READ, o.seller_organization_id) else None}]
    return {"chain": chain}


def _order_resolver(db: Session, principal: Principal, entity_id: uuid.UUID, kind: str) -> None:
    o = db.get(Order, entity_id)
    if kind == "manage":
        raise PermissionDenied("Order documents are immutable.", error_code="DOCUMENT_IMMUTABLE")
    if o is None or side(principal, o) is None:
        raise ms.nf("Document", "DOCUMENT_NOT_FOUND")


document_service.register_resolver(ORDER_ENTITY, _order_resolver)
