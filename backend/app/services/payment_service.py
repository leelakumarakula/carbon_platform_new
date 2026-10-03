"""Phase 10 payments and refunds (D15–D20, D33).

- T2 — a MANUAL payment is recorded by the buyer with PAYMENT_EVIDENCE: PENDING_CONFIRMATION; the order stays PLACED; no credit moves.
- T3 — the seller's finance (the payee, D16; never the recorder) confirms in ONE transaction: order → payment → each item's 9B reservation
  is locked; if every reservation is still ACTIVE and not due it is consumed into a 9B transfer request (`request_transfer_in_tx`) and the
  order goes PAID → TRANSFER_PENDING; otherwise the money is acknowledged (CONFIRMED) but no transfer is created and the order goes PAID →
  ATTENTION_REQUIRED (manual resolution: re-reserve or refund, D23). Nothing is fabricated, nothing is silently retried.
- Provider payments (TEST adapter only, injected by tests — D15) follow the outbox pattern of Phase 9A: the payment row and its key are
  committed before the provider is called; a timeout leaves UNCONFIRMED (no automatic retry); provider events are append-only and
  deduplicated on (provider, external event id) (D17); a provider "succeeded" still needs the seller-finance confirmation (T3).
- Refunds are money only (D19): never a carbon quantity, never an ownership change; requested and approved by different people.
"""
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit.service import record
from app.core.context import RequestContext
from app.core.errors import Conflict, PermissionDenied, ValidationFailed
from app.integrations.payment import (
    ADAPTERS,
    ManualActionRequired,
    PaymentAdapter,
    PaymentRequest,
    PaymentTimeout,
    PaymentUnavailable,
)
from app.models import Document, Order, Payment, PaymentEvent, Refund
from app.models.base import utcnow
from app.models.documents import DocumentCategory
from app.repositories.sequences import next_code
from app.security.permissions import P
from app.security.principal import Principal
from app.services import document_service, finance_service
from app.services import ledger_service as ls
from app.services import marketplace_service as ms
from app.services import order_service as os_
from app.services.workflows import PAYMENT_MACHINE, REFUND_MACHINE

PAYMENT_ENTITY = "payment"
REFUND_ENTITY = "refund"
FINANCE = (P.PAYMENTS_CONFIRM, P.REFUNDS_REQUEST, P.REFUNDS_APPROVE)


def adapter_for(code: str, override: PaymentAdapter | None = None) -> PaymentAdapter:
    """The runtime adapter (MANUAL only). Tests inject their adapter explicitly via `override`; it is never registered (D15, D33)."""
    if override is not None:
        return override
    a = ADAPTERS.get(code)
    if a is None:
        raise Conflict(f"No payment adapter {code!r} is available.", error_code="UNKNOWN_PAYMENT_ADAPTER")
    return a


def _pay(db: Session, ctx: RequestContext, p: Payment, to: str, reason: str | None = None) -> str:
    return ms.transition(db, ctx, PAYMENT_MACHINE, p, PAYMENT_ENTITY, to, reason)


def get_payment(db: Session, principal: Principal, payment_id: uuid.UUID) -> tuple[Payment, Order]:
    p = db.get(Payment, payment_id)
    o = db.get(Order, p.order_id) if p else None
    if p is None or o is None or os_.side(principal, o) is None:
        raise ms.nf("Payment", "PAYMENT_NOT_FOUND")
    return p, o


def visible_payments(db: Session, principal: Principal, status: str | None = None) -> list[Payment]:
    stmt = select(Payment).order_by(Payment.created_at.desc())
    if status:
        stmt = stmt.where(Payment.status == status)
    out = []
    for p in db.scalars(stmt).all():
        o = db.get(Order, p.order_id)
        if o is not None and os_.side(principal, o) is not None:
            out.append(p)
    return out


def _payable(db: Session, ctx: RequestContext, principal: Principal, order_id: uuid.UUID, amount: Any, currency: str) -> tuple[Order, Decimal]:
    o = os_.get_order(db, principal, order_id)
    ms.require(principal, o.buyer_organization_id, P.PAYMENTS_RECORD, visible=(*os_.BUYER_SIDE, *os_.SELLER_SIDE), what="Order",
               nf_code="ORDER_NOT_FOUND")
    ms.require_kyc(db, o.buyer_organization_id)                     # D1
    os_.expire_if_due(db, ctx, o)
    db.refresh(o)
    if o.status != "PLACED":
        raise Conflict(f"Order {o.order_code} is {o.status}; it cannot be paid.", error_code="ORDER_NOT_PAYABLE")
    amt = ms.money(amount, currency.upper())
    if currency.upper() != o.currency or amt != o.total:
        # D18 / data model: no partial payment — the amount must equal the order total in the order currency
        raise ValidationFailed(f"The payment must be exactly {o.total} {o.currency}.", error_code="PAYMENT_AMOUNT_MISMATCH",
                               details={"total": str(o.total), "currency": o.currency})
    return o, amt


# ---------------------------------------------------------------- T2 manual recording
def record_manual(db: Session, ctx: RequestContext, principal: Principal, data: Any, key: str | None) -> Payment:
    if key and (prior := db.scalars(select(Payment).where(Payment.request_key == key)).first()) is not None:
        return prior
    o, amt = _payable(db, ctx, principal, data.order_id, data.amount, data.currency)
    document_service.require_attached(db, data.document_id, os_.ORDER_ENTITY, o.id, {DocumentCategory.PAYMENT_EVIDENCE.value})

    def op() -> Payment:
        x = ms.lock(db, Order, o.id)                                # D26: order → payment
        if x.status != "PLACED":
            raise Conflict(f"Order {x.order_code} is {x.status}; it cannot be paid.", error_code="ORDER_NOT_PAYABLE")
        if db.scalars(select(Payment.id).where(Payment.order_id == x.id, Payment.status.in_(
                ("CREATED", "PENDING", "UNCONFIRMED", "PENDING_CONFIRMATION", "CONFIRMED")))).first():
            raise Conflict("A payment for this order is already in progress.", error_code="PAYMENT_IN_PROGRESS")
        p = Payment(payment_code=next_code(db, "payment", utcnow().year), order_id=x.id, payee_organization_id=x.seller_organization_id,
                    payer_organization_id=x.buyer_organization_id, adapter_code="MANUAL", amount=amt, currency=x.currency,
                    status="PENDING_CONFIRMATION", external_reference=(data.external_reference or "").strip() or None,
                    evidence_document_id=data.document_id, recorded_by=principal.user_id, note=data.note, request_key=key,
                    environment=x.environment)
        db.add(p)
        db.flush()
        ls.workflow(db, ctx, PAYMENT_ENTITY, p.id, None, p.status, None)
        ls.audit(db, ctx, "PAYMENT_RECORDED", PAYMENT_ENTITY, p.id, os_.parties(x),
                 {"payment_code": p.payment_code, "order_code": x.order_code, "amount": str(amt), "currency": p.currency, "adapter": "MANUAL",
                  "external_reference": p.external_reference, "evidence_document_id": p.evidence_document_id, "status": p.status})
        return p
    try:
        return ls.run(db, ctx, op)
    except IntegrityError:
        raise Conflict("A payment for this order is already in progress, or this reference is already recorded.",
                       error_code="PAYMENT_IN_PROGRESS") from None


# ---------------------------------------------------------------- provider payments (TEST adapter only until a provider is contracted)
def start_provider_payment(db: Session, ctx: RequestContext, principal: Principal, order_id: uuid.UUID, adapter: PaymentAdapter,
                           key: str | None = None) -> Payment:
    if adapter.code == "MANUAL":
        raise Conflict("No payment provider is contracted: record the payment manually with evidence.", error_code="MANUAL_ACTION_REQUIRED")
    if key and (prior := db.scalars(select(Payment).where(Payment.request_key == key)).first()) is not None:
        return prior
    o = os_.get_order(db, principal, order_id)
    o, amt = _payable(db, ctx, principal, order_id, o.total, o.currency)

    def create() -> Payment:
        x = ms.lock(db, Order, o.id)
        if db.scalars(select(Payment.id).where(Payment.order_id == x.id, Payment.status.in_(
                ("CREATED", "PENDING", "UNCONFIRMED", "PENDING_CONFIRMATION", "CONFIRMED")))).first():
            raise Conflict("A payment for this order is already in progress.", error_code="PAYMENT_IN_PROGRESS")
        p = Payment(payment_code=next_code(db, "payment", utcnow().year), order_id=x.id, payee_organization_id=x.seller_organization_id,
                    payer_organization_id=x.buyer_organization_id, adapter_code=adapter.code, amount=amt, currency=x.currency, status="CREATED",
                    recorded_by=principal.user_id, request_key=key, environment=x.environment)
        db.add(p)
        db.flush()
        ls.workflow(db, ctx, PAYMENT_ENTITY, p.id, None, "CREATED", None)
        ls.audit(db, ctx, "PAYMENT_RECORDED", PAYMENT_ENTITY, p.id, os_.parties(x),
                 {"payment_code": p.payment_code, "order_code": x.order_code, "amount": str(amt), "adapter": adapter.code, "status": "CREATED"})
        return p
    p = ls.run(db, ctx, create)                                     # outbox: persisted with its key BEFORE the provider is called
    try:
        result = adapter.create_payment(PaymentRequest(p.payment_code, o.order_code, p.amount, p.currency, p.payment_code))
    except PaymentTimeout:
        _pay(db, ctx, p, "UNCONFIRMED", "No answer from the payment provider")
        ls.audit(db, ctx, "PAYMENT_UNCONFIRMED", PAYMENT_ENTITY, p.id, os_.parties(o), {"payment_code": p.payment_code, "status": "UNCONFIRMED"})
        db.commit()
        return p
    except PaymentUnavailable as e:
        _pay(db, ctx, p, "FAILED", str(e)[:2000])
        db.commit()
        return p
    p.external_reference = result.external_id
    _pay(db, ctx, p, "PENDING")
    db.commit()
    return p


def _apply(db: Session, ctx: RequestContext, p: Payment, o: Order, event_type: str) -> str:
    """One provider outcome on a locked payment / order; returns the event outcome. Never confirms (T3 is a human decision)."""
    if event_type == "SUCCEEDED":
        if p.status in ("CREATED", "PENDING", "UNCONFIRMED"):
            if o.status == "PLACED":
                _pay(db, ctx, p, "PENDING_CONFIRMATION", "provider reports the payment succeeded")
                return "APPLIED"
            _pay(db, ctx, p, "UNMATCHED", f"order {o.order_code} is {o.status}")
            ls.audit(db, ctx, "PAYMENT_UNMATCHED", PAYMENT_ENTITY, p.id, os_.parties(o),
                     {"payment_code": p.payment_code, "order_code": o.order_code, "order_status": o.status, "action": "refund required"})
            return "UNMATCHED"
        if p.status == "FAILED":                                     # money reported after a failure: never silently applied
            ls.audit(db, ctx, "PAYMENT_UNMATCHED", PAYMENT_ENTITY, p.id, os_.parties(o),
                     {"payment_code": p.payment_code, "payment_status": p.status, "action": "manual reconciliation required"})
            return "UNMATCHED"
        return "IGNORED"
    if event_type in ("FAILED", "CANCELLED"):
        if p.status in ("CREATED", "PENDING", "UNCONFIRMED"):
            _pay(db, ctx, p, "FAILED", f"provider reports {event_type}")
            return "APPLIED"                                         # D18: the order stays PLACED; the buyer may retry before the deadline
        return "IGNORED"
    if event_type == "PENDING" and p.status in ("CREATED", "UNCONFIRMED"):
        _pay(db, ctx, p, "PENDING")
        return "APPLIED"
    return "IGNORED"


def ingest_event(db: Session, ctx: RequestContext, adapter: PaymentAdapter, raw: bytes) -> str:
    """D17: append-only, deduplicated provider events. A duplicate is a recorded no-op (no state change, transfer or refund repeated)."""
    ev = adapter.parse_event(raw)
    p0 = db.scalars(select(Payment).where(Payment.adapter_code == adapter.code, Payment.external_reference == ev.external_payment_id)).first()

    def duplicate() -> str:
        payload = {"provider": adapter.code, "external_event_id": ev.external_event_id, "payment_code": p0.payment_code if p0 else None}
        if p0 is None:
            record(db, ctx, "PAYMENT_EVENT_DUPLICATE", "payment_event", None, None, payload)
        else:
            ls.audit(db, ctx, "PAYMENT_EVENT_DUPLICATE", PAYMENT_ENTITY, p0.id, [p0.payer_organization_id, p0.payee_organization_id], payload)
        db.commit()
        return "DUPLICATE"

    if db.scalars(select(PaymentEvent.id).where(PaymentEvent.provider == adapter.code,
                                                PaymentEvent.external_event_id == ev.external_event_id)).first():
        return duplicate()                                           # no state change, no transfer, no refund — a recorded no-op

    def op() -> str:
        if p0 is None:
            db.add(PaymentEvent(provider=adapter.code, external_event_id=ev.external_event_id, external_payment_id=ev.external_payment_id,
                                event_type=ev.event_type, payload_sha256=ev.payload_sha256, outcome="IGNORED", note="unknown payment"))
            return "IGNORED"
        o = ms.lock(db, Order, p0.order_id)                          # D26: order → payment
        p = ms.lock(db, Payment, p0.id)
        outcome = _apply(db, ctx, p, o, ev.event_type)
        db.add(PaymentEvent(payment_id=p.id, provider=adapter.code, external_event_id=ev.external_event_id,
                            external_payment_id=ev.external_payment_id, event_type=ev.event_type, payload_sha256=ev.payload_sha256,
                            outcome=outcome))
        db.flush()                                                   # the unique (provider, event id) index rejects a concurrent duplicate
        ls.audit(db, ctx, "PAYMENT_EVENT_RECEIVED", PAYMENT_ENTITY, p.id, os_.parties(o),
                 {"payment_code": p.payment_code, "event": ev.event_type, "external_event_id": ev.external_event_id, "outcome": outcome,
                  "status": p.status})
        return outcome
    try:
        return ls.run(db, ctx, op)
    except IntegrityError:                                           # a concurrent duplicate lost the unique (provider, event id) race
        db.rollback()
        return duplicate()


# ---------------------------------------------------------------- T3 confirmation (D16, D20)
def _payee(principal: Principal, p: Payment, code: str) -> None:
    ms.require(principal, p.payee_organization_id, code, visible=(*os_.SELLER_SIDE, *os_.BUYER_SIDE), what="Payment", nf_code="PAYMENT_NOT_FOUND")


def confirm(db: Session, ctx: RequestContext, principal: Principal, payment_id: uuid.UUID, key: str | None) -> Payment:
    p, o = get_payment(db, principal, payment_id)
    if ms.replay_action(p, key, "CONFIRMED"):
        return p
    _payee(principal, p, P.PAYMENTS_CONFIRM)
    if p.recorded_by == principal.user_id:
        raise PermissionDenied("You recorded this payment, so someone else must confirm it.", error_code="SEPARATION_OF_DUTIES")
    ms.require_kyc(db, o.buyer_organization_id)                     # D1

    def op() -> Payment:
        x = ms.lock(db, Order, o.id)                                # D26: order → payment → reservations → positions
        pay = ms.lock(db, Payment, p.id)
        if pay.status != "PENDING_CONFIRMATION":
            raise Conflict(f"The payment is {pay.status}.", error_code="PAYMENT_NOT_PENDING")
        if x.status != "PLACED":
            raise Conflict(f"Order {x.order_code} is {x.status}.", error_code="ORDER_NOT_PAYABLE")
        if pay.currency != x.currency or pay.amount != x.total:
            raise ValidationFailed("The payment does not equal the order total.", error_code="PAYMENT_AMOUNT_MISMATCH")
        items = sorted(os_.items_of(db, x.id), key=lambda i: str(i.reservation_id))
        lost = []
        for it in items:
            r = ls.lock_reservation(db, it.reservation_id) if it.reservation_id else None
            if r is not None and r.status == "ACTIVE" and ms.is_due(r.expires_at):
                ls.expire_reservation_in_tx(db, ctx, r, principal.user_id)          # the 9B lazy expiry, under the same locks
            if r is None or r.status != "ACTIVE":
                lost.append(it)
        frm_pay = _pay(db, ctx, pay, "CONFIRMED")
        pay.confirmed_by, pay.confirmed_at, pay.action_key = principal.user_id, utcnow(), key
        frm = os_._order(db, ctx, x, "PAID")
        x.paid_at = utcnow()
        ls.audit(db, ctx, "PAYMENT_CONFIRMED", PAYMENT_ENTITY, pay.id, os_.parties(x),
                 {"payment_code": pay.payment_code, "order_code": x.order_code, "amount": str(pay.amount), "currency": pay.currency},
                 None, {"status": frm_pay})
        ls.audit(db, ctx, "ORDER_PAID", os_.ORDER_ENTITY, x.id, os_.parties(x), {"order_code": x.order_code, "payment_code": pay.payment_code},
                 None, {"status": frm})
        if lost:
            for it in lost:
                if it.status == "RESERVED":
                    os_._item(db, ctx, it, "FAILED", "reservation expired before payment confirmation")
            os_.attention(db, ctx, x, "RESERVATION_EXPIRED: the payment was confirmed after the reservation of "
                          + ", ".join(i.item_code for i in lost) + " expired; re-reserve and request the transfer, or refund.")
            return pay
        for it in items:
            os_.request_delivery(db, ctx, x, it, principal.user_id, reuse_active=True)   # consumes the ACTIVE reservation (no re-reserve)
        os_._order(db, ctx, x, "TRANSFER_PENDING")
        return pay
    return ls.run(db, ctx, op, conflict_org=o.seller_organization_id)


def reject(db: Session, ctx: RequestContext, principal: Principal, payment_id: uuid.UUID, reason: str, key: str | None) -> Payment:
    """The payee's finance did not receive / cannot accept the payment. D18: the order stays PLACED; the buyer may pay again before the
    deadline."""
    p, o = get_payment(db, principal, payment_id)
    if ms.replay_action(p, key, "REJECTED"):
        return p
    _payee(principal, p, P.PAYMENTS_CONFIRM)
    if p.recorded_by == principal.user_id:
        raise PermissionDenied("You recorded this payment, so someone else must decide on it.", error_code="SEPARATION_OF_DUTIES")

    def op() -> Payment:
        ms.lock(db, Order, o.id)
        pay = ms.lock(db, Payment, p.id)
        if pay.status != "PENDING_CONFIRMATION":
            raise Conflict(f"The payment is {pay.status}.", error_code="PAYMENT_NOT_PENDING")
        frm = _pay(db, ctx, pay, "REJECTED", reason)
        pay.rejected_by, pay.rejected_at, pay.reject_reason, pay.action_key = principal.user_id, utcnow(), reason, key
        ls.audit(db, ctx, "PAYMENT_REJECTED", PAYMENT_ENTITY, pay.id, os_.parties(o), {"payment_code": pay.payment_code, "status": "REJECTED"},
                 reason, {"status": frm})
        return pay
    return ls.run(db, ctx, op)


def reconcile(db: Session, ctx: RequestContext, principal: Principal, payment_id: uuid.UUID, adapter: PaymentAdapter | None = None) -> Payment:
    """Manual reconciliation (D35): a provider payment's status is queried once on request — no job, no automatic retry. A MANUAL payment
    is reconciled by its confirmation / rejection with evidence."""
    p, o = get_payment(db, principal, payment_id)
    _payee(principal, p, P.PAYMENTS_CONFIRM)
    impl = adapter_for(p.adapter_code, adapter)
    if p.adapter_code != "MANUAL" and p.status not in ("CREATED", "PENDING", "UNCONFIRMED"):
        raise Conflict(f"The payment is {p.status}; nothing to reconcile.", error_code="NOTHING_TO_RECONCILE")
    try:
        found = impl.get_status(p.external_reference or p.payment_code)    # by our idempotency key when the provider never answered
    except ManualActionRequired as e:
        raise Conflict(str(e), error_code="MANUAL_ACTION_REQUIRED") from None
    except (PaymentTimeout, PaymentUnavailable) as e:
        raise Conflict(f"The payment provider did not answer: {e}", error_code="PAYMENT_PROVIDER_UNAVAILABLE") from None
    status = found.status

    def op() -> Payment:
        x = ms.lock(db, Order, o.id)
        pay = ms.lock(db, Payment, p.id)
        if pay.external_reference is None:
            pay.external_reference = found.external_id
        outcome = _apply(db, ctx, pay, x, status)
        ls.audit(db, ctx, "PAYMENT_RECONCILED", PAYMENT_ENTITY, pay.id, os_.parties(x),
                 {"payment_code": pay.payment_code, "provider_status": status, "outcome": outcome, "status": pay.status})
        return pay
    return ls.run(db, ctx, op)


# ---------------------------------------------------------------- refunds (D19)
def get_refund(db: Session, principal: Principal, refund_id: uuid.UUID) -> tuple[Refund, Payment, Order]:
    r = db.get(Refund, refund_id)
    if r is None:
        raise ms.nf("Refund", "REFUND_NOT_FOUND")
    p, o = get_payment(db, principal, r.payment_id)
    return r, p, o


def visible_refunds(db: Session, principal: Principal) -> list[Refund]:
    out = []
    for r in db.scalars(select(Refund).order_by(Refund.created_at.desc())).all():
        o = db.get(Order, r.order_id)
        if o is not None and os_.side(principal, o) is not None:
            out.append(r)
    return out


def request_refund(db: Session, ctx: RequestContext, principal: Principal, payment_id: uuid.UUID, reason: str, key: str | None) -> Refund:
    """Whole-payment refunds (partial refunds are not implemented):
    - an UNMATCHED payment (money received for an order that could not take it) — the order is untouched;
    - before delivery (order PAID / ATTENTION_REQUIRED with no item delivered or in delivery) — the order goes REFUND_PENDING;
    - after delivery (order COMPLETED) — money-only remediation: credits stay with the buyer (any return of credits is a separate,
      manual 9B reversal where 9B allows it; a REGISTRY transfer is never reversed)."""
    if key and (prior := db.scalars(select(Refund).where(Refund.request_key == key)).first()) is not None:
        return prior
    p, o = get_payment(db, principal, payment_id)
    _payee(principal, p, P.REFUNDS_REQUEST)

    def op() -> Refund:
        x = ms.lock(db, Order, o.id)                                # D26: order → payment
        pay = ms.lock(db, Payment, p.id)
        if pay.status not in ("CONFIRMED", "UNMATCHED"):
            raise Conflict(f"Only a confirmed or unmatched payment can be refunded (this one is {pay.status}).", error_code="REFUND_NOT_ALLOWED")
        if db.scalars(select(Refund.id).where(Refund.payment_id == pay.id, Refund.status.in_(("REQUESTED", "APPROVED", "COMPLETED")))).first():
            raise Conflict("A refund of this payment already exists.", error_code="REFUND_EXISTS")
        after = False
        if pay.status == "CONFIRMED":
            states = {i.status for i in os_.items_of(db, x.id)}
            if x.status == "COMPLETED":
                after = True
            elif x.status in ("PAID", "ATTENTION_REQUIRED") and not states & {"DELIVERED", "TRANSFER_PENDING"}:
                frm = os_._order(db, ctx, x, "REFUND_PENDING", reason)
                ls.audit(db, ctx, "ORDER_REFUND_PENDING", os_.ORDER_ENTITY, x.id, os_.parties(x), {"order_code": x.order_code}, reason,
                         {"status": frm})
            else:
                raise Conflict(f"Order {x.order_code} is {x.status} with deliveries in progress or partly delivered; resolve the deliveries "
                               "first (a refund never moves credits).", error_code="REFUND_NOT_ALLOWED")
        r = Refund(refund_code=next_code(db, "refund", utcnow().year), payment_id=pay.id, order_id=x.id, amount=pay.amount, currency=pay.currency,
                   after_transfer=after, reason=reason, status="REQUESTED", requested_by=principal.user_id, request_key=key,
                   environment=pay.environment)
        db.add(r)
        db.flush()
        ls.workflow(db, ctx, REFUND_ENTITY, r.id, None, "REQUESTED", reason)
        ls.audit(db, ctx, "REFUND_REQUESTED", REFUND_ENTITY, r.id, os_.parties(x),
                 {"refund_code": r.refund_code, "payment_code": pay.payment_code, "order_code": x.order_code, "amount": str(r.amount),
                  "currency": r.currency, "after_transfer": after}, reason)
        return r
    try:
        return ls.run(db, ctx, op)
    except IntegrityError:
        raise Conflict("A refund of this payment already exists.", error_code="REFUND_EXISTS") from None


def upload_refund_document(db: Session, ctx: RequestContext, principal: Principal, refund_id: uuid.UUID, filename: str | None, data: bytes,
                           title: str | None) -> Document:
    r, p, o = get_refund(db, principal, refund_id)
    ms.require(principal, p.payee_organization_id, P.REFUNDS_APPROVE, P.REFUNDS_REQUEST, visible=(*os_.SELLER_SIDE, *os_.BUYER_SIDE),
               what="Refund", nf_code="REFUND_NOT_FOUND")
    doc = document_service.create_document(db, ctx, entity_type=REFUND_ENTITY, entity_id=r.id, organization_id=p.payee_organization_id,
                                           environment=r.environment, category=DocumentCategory.REFUND_EVIDENCE.value,
                                           title=title or "Refund evidence", filename=filename, data=data)
    db.commit()
    return doc


def decide_refund(db: Session, ctx: RequestContext, principal: Principal, refund_id: uuid.UUID, action: str, data: Any, key: str | None,
                  adapter: PaymentAdapter | None = None) -> Refund:
    """approve (≠ requester) → complete (evidence; payment REFUNDED; before delivery the order's reservations are released and the order
    is REFUNDED) / reject (≠ requester; a REFUND_PENDING order returns to ATTENTION_REQUIRED)."""
    r, p, o = get_refund(db, principal, refund_id)
    target = {"approve": "APPROVED", "complete": "COMPLETED", "reject": "REJECTED"}[action]
    if ms.replay_action(r, key, target):
        return r
    if action == "complete":
        ms.require(principal, p.payee_organization_id, P.REFUNDS_APPROVE, P.REFUNDS_REQUEST, visible=(*os_.SELLER_SIDE, *os_.BUYER_SIDE),
                   what="Refund", nf_code="REFUND_NOT_FOUND")
    else:
        _payee(principal, p, P.REFUNDS_APPROVE)
        if r.requested_by == principal.user_id:
            raise PermissionDenied("You requested this refund, so someone else must decide on it.", error_code="SEPARATION_OF_DUTIES")
    ext_ref, doc_id = None, None
    if action == "complete":
        if p.adapter_code == "MANUAL":
            ext_ref = (getattr(data, "external_reference", None) or "").strip()
            doc_id = getattr(data, "document_id", None)
            if not ext_ref or doc_id is None:
                raise ValidationFailed("A manual refund completes only with its payment reference and evidence (PDF).",
                                       error_code="REFUND_EVIDENCE_REQUIRED")
            document_service.require_attached(db, doc_id, REFUND_ENTITY, r.id, {DocumentCategory.REFUND_EVIDENCE.value})
        elif r.status == "APPROVED":
            try:
                ext_ref = adapter_for(p.adapter_code, adapter).refund(p.external_reference or "", r.amount, r.currency, r.refund_code).external_id
            except ManualActionRequired as e:
                raise Conflict(str(e), error_code="MANUAL_ACTION_REQUIRED") from None
    reason = getattr(data, "reason", None)
    if action == "reject" and not (reason and reason.strip()):
        raise ValidationFailed("Give a reason.", error_code="REASON_REQUIRED")

    def op() -> Refund:
        x = ms.lock(db, Order, o.id)
        pay = ms.lock(db, Payment, p.id)
        ref = ms.lock(db, Refund, r.id)
        frm = ms.transition(db, ctx, REFUND_MACHINE, ref, REFUND_ENTITY, target, reason)
        ref.action_key = key
        now = utcnow()
        if action == "approve":
            ref.approved_by, ref.approved_at = principal.user_id, now
        elif action == "reject":
            ref.rejected_by, ref.reject_reason = principal.user_id, reason
            if x.status == "REFUND_PENDING":
                os_.attention(db, ctx, x, f"Refund {ref.refund_code} rejected: {reason}")
        else:
            ref.completed_by, ref.completed_at, ref.external_reference, ref.evidence_document_id = principal.user_id, now, ext_ref, doc_id
            _pay(db, ctx, pay, "REFUNDED", ref.refund_code)
            finance_service.reverse_for_refund_in_tx(db, ctx, refund=ref, order=x, actor_id=principal.user_id)   # Phase 11 D10 (reversal)
            if x.status == "REFUND_PENDING":
                for it in os_.items_of(db, x.id):
                    res = ls.lock_reservation(db, it.reservation_id) if it.reservation_id else None
                    if res is not None and res.status == "ACTIVE":
                        ls.release_in_tx(db, ctx, res, principal.user_id, f"Order {x.order_code} refunded ({ref.refund_code})")
                    if it.status in ("RESERVED", "FAILED"):
                        os_._item(db, ctx, it, "RELEASED", f"refunded ({ref.refund_code})")
                fo = os_._order(db, ctx, x, "REFUNDED", ref.refund_code)
                x.closed_at, x.close_reason = now, f"Refunded ({ref.refund_code})"
                ls.audit(db, ctx, "ORDER_REFUNDED", os_.ORDER_ENTITY, x.id, os_.parties(x), {"order_code": x.order_code}, None, {"status": fo})
        event = {"approve": "REFUND_APPROVED", "complete": "REFUND_COMPLETED", "reject": "REFUND_REJECTED"}[action]
        ls.audit(db, ctx, event, REFUND_ENTITY, ref.id, os_.parties(x),
                 {"refund_code": ref.refund_code, "status": target, "external_reference": ref.external_reference,
                  "after_transfer": ref.after_transfer}, reason, {"status": frm})
        return ref
    return ls.run(db, ctx, op)


def _payment_resolver(db: Session, principal: Principal, entity_id: uuid.UUID, kind: str) -> None:
    r = db.get(Refund, entity_id)
    if kind == "manage":
        raise PermissionDenied("Refund evidence is immutable.", error_code="DOCUMENT_IMMUTABLE")
    o = db.get(Order, r.order_id) if r else None
    if o is None or os_.side(principal, o) is None:
        raise ms.nf("Document", "DOCUMENT_NOT_FOUND")


document_service.register_resolver(REFUND_ENTITY, _payment_resolver)
