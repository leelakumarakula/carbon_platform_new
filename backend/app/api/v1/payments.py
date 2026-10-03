"""Payments & refunds API (`/api/v1/payments`, `/api/v1/refunds`, Phase 10). LIVE payments are MANUAL until a provider is contracted
(D15, D33): the buyer records the payment with evidence; the seller's finance (the payee) confirms — a different person — which requests the
9B transfer (it never completes it). There is NO public webhook route (D17). Refunds are money only (D19). Every POST accepts an
Idempotency-Key."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile, status

from app.api.deps import DB, Ctx, ListLimit, ListOffset, read_upload, require_any
from app.schemas.lab import DocumentRef
from app.schemas.marketplace import PaymentIn, PaymentOut, ReasonIn, RefundCompleteIn, RefundOut
from app.security.permissions import P
from app.security.principal import Principal
from app.services import marketplace_mappers as mm
from app.services import payment_service as ps

router = APIRouter(tags=["marketplace — payments and refunds"])

Recorder = Annotated[Principal, Depends(require_any(P.PAYMENTS_RECORD))]
Reader = Annotated[Principal, Depends(require_any(P.ORDERS_READ, P.PAYMENTS_RECORD, P.PAYMENTS_CONFIRM, P.REFUNDS_REQUEST, P.REFUNDS_APPROVE))]
Confirmer = Annotated[Principal, Depends(require_any(P.PAYMENTS_CONFIRM))]
RefundRequester = Annotated[Principal, Depends(require_any(P.REFUNDS_REQUEST))]
RefundApprover = Annotated[Principal, Depends(require_any(P.REFUNDS_APPROVE))]
RefundFinance = Annotated[Principal, Depends(require_any(P.REFUNDS_REQUEST, P.REFUNDS_APPROVE))]
IdemKey = Annotated[str | None, Header(alias="Idempotency-Key", max_length=80)]


@router.post("/payments", response_model=PaymentOut, status_code=status.HTTP_201_CREATED,
             summary="Record a manual payment for an order (exact total, same currency, PAYMENT_EVIDENCE attached to the order)")
def record_payment(body: PaymentIn, principal: Recorder, db: DB, ctx: Ctx, key: IdemKey = None) -> PaymentOut:
    return mm.payment_out(db, principal, ps.record_manual(db, ctx, principal, body, key))


@router.get("/payments", response_model=list[PaymentOut], summary="Payments of the organization's orders (buyer or payee)")
def list_payments(principal: Reader, db: DB, status: str | None = None) -> list[PaymentOut]:
    return [mm.payment_out(db, principal, p) for p in ps.visible_payments(db, principal, status)]


@router.get("/payments/{payment_id}", response_model=PaymentOut)
def get_payment(payment_id: uuid.UUID, principal: Reader, db: DB) -> PaymentOut:
    p, o = ps.get_payment(db, principal, payment_id)
    return mm.payment_out(db, principal, p, o)


@router.post("/payments/{payment_id}/confirm", response_model=PaymentOut,
             summary="Payee finance confirms receipt (never the recorder): consumes the 9B reservations into 9B transfer requests")
def confirm_payment(payment_id: uuid.UUID, principal: Confirmer, db: DB, ctx: Ctx, key: IdemKey = None) -> PaymentOut:
    return mm.payment_out(db, principal, ps.confirm(db, ctx, principal, payment_id, key))


@router.post("/payments/{payment_id}/reject", response_model=PaymentOut,
             summary="Payee finance rejects a recorded payment; the order stays PLACED until its deadline")
def reject_payment(payment_id: uuid.UUID, body: ReasonIn, principal: Confirmer, db: DB, ctx: Ctx, key: IdemKey = None) -> PaymentOut:
    return mm.payment_out(db, principal, ps.reject(db, ctx, principal, payment_id, body.reason, key))


@router.post("/payments/{payment_id}/reconcile", response_model=PaymentOut,
             summary="Query a provider payment's status once (manual reconciliation); MANUAL payments answer MANUAL_ACTION_REQUIRED")
def reconcile_payment(payment_id: uuid.UUID, principal: Confirmer, db: DB, ctx: Ctx, key: IdemKey = None) -> PaymentOut:
    return mm.payment_out(db, principal, ps.reconcile(db, ctx, principal, payment_id))


@router.post("/payments/{payment_id}/refunds", response_model=RefundOut, status_code=status.HTTP_201_CREATED,
             summary="Request a whole-payment refund (money only — never moves credits)")
def request_refund(payment_id: uuid.UUID, body: ReasonIn, principal: RefundRequester, db: DB, ctx: Ctx, key: IdemKey = None) -> RefundOut:
    return mm.refund_out(db, principal, ps.request_refund(db, ctx, principal, payment_id, body.reason, key))


@router.get("/refunds", response_model=list[RefundOut])
def list_refunds(principal: Reader, db: DB, limit: ListLimit = None, offset: ListOffset = 0) -> list[RefundOut]:
    return [mm.refund_out(db, principal, r) for r in ps.visible_refunds(db, principal, limit=limit, offset=offset)]


@router.post("/refunds/{refund_id}/documents", response_model=DocumentRef, status_code=status.HTTP_201_CREATED,
             summary="Attach refund evidence (REFUND_EVIDENCE, PDF)")
def refund_document(refund_id: uuid.UUID, principal: RefundFinance, db: DB, ctx: Ctx, file: Annotated[UploadFile, File()],
                    title: Annotated[str | None, Form(max_length=200)] = None) -> DocumentRef:
    return mm.doc_ref(ps.upload_refund_document(db, ctx, principal, refund_id, file.filename, read_upload(file), title))


@router.post("/refunds/{refund_id}/approve", response_model=RefundOut, summary="Approve a refund (never the requester)")
def approve_refund(refund_id: uuid.UUID, principal: RefundApprover, db: DB, ctx: Ctx, key: IdemKey = None) -> RefundOut:
    return mm.refund_out(db, principal, ps.decide_refund(db, ctx, principal, refund_id, "approve", None, key))


@router.post("/refunds/{refund_id}/complete", response_model=RefundOut,
             summary="Record the completed refund (reference + REFUND_EVIDENCE); before delivery the order becomes REFUNDED")
def complete_refund(refund_id: uuid.UUID, body: RefundCompleteIn, principal: RefundFinance, db: DB, ctx: Ctx, key: IdemKey = None) -> RefundOut:
    return mm.refund_out(db, principal, ps.decide_refund(db, ctx, principal, refund_id, "complete", body, key))


@router.post("/refunds/{refund_id}/reject", response_model=RefundOut, summary="Reject a refund (never the requester)")
def reject_refund(refund_id: uuid.UUID, body: ReasonIn, principal: RefundApprover, db: DB, ctx: Ctx, key: IdemKey = None) -> RefundOut:
    return mm.refund_out(db, principal, ps.decide_refund(db, ctx, principal, refund_id, "reject", body, key))
