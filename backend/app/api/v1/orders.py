"""Orders API (`/api/v1/orders`, Phase 10): placement (one transaction with the Phase 9B reservations), cancellation, payment evidence,
order-linked transfer completion / rejection (the Phase 10 wrapper around the composable 9B transfer functions — the 9B second-person rule
applies), manual resolution, deterministic order confirmation and lineage. Every POST accepts an Idempotency-Key."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile, status

from app.api.deps import DB, Ctx, read_upload, require_any
from app.schemas.lab import DocumentRef
from app.schemas.marketplace import LineageOut, OrderIn, OrderListOut, OrderOut, ReasonIn, TransferCompleteIn
from app.security.permissions import P
from app.security.principal import Principal
from app.services import marketplace_mappers as mm
from app.services import marketplace_service as ms
from app.services import order_service as os_

router = APIRouter(prefix="/orders", tags=["marketplace — orders"])

Placer = Annotated[Principal, Depends(require_any(P.ORDERS_PLACE))]
Reader = Annotated[Principal, Depends(require_any(P.ORDERS_READ, P.ORDERS_PLACE, P.ORDERS_MANAGE, P.PAYMENTS_RECORD, P.PAYMENTS_CONFIRM))]
Canceller = Annotated[Principal, Depends(require_any(P.ORDERS_PLACE, P.ORDERS_MANAGE))]
Payer = Annotated[Principal, Depends(require_any(P.PAYMENTS_RECORD, P.ORDERS_PLACE))]
Manager = Annotated[Principal, Depends(require_any(P.ORDERS_MANAGE))]
Confirmer = Annotated[Principal, Depends(require_any(P.CREDITS_CONFIRM))]
IdemKey = Annotated[str | None, Header(alias="Idempotency-Key", max_length=80)]


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED,
             summary="Place an order (KYC-verified buyer): one transaction — listings locked, items created, one 9B reservation per item")
def place_order(body: OrderIn, principal: Placer, db: DB, ctx: Ctx, key: IdemKey = None) -> OrderOut:
    return mm.order_out(db, principal, os_.place(db, ctx, principal, body, key))


@router.get("", response_model=OrderListOut, summary="The organization's orders (as buyer or as seller)")
def list_orders(principal: Reader, db: DB, ctx: Ctx, status: str | None = None) -> OrderListOut:
    rows = os_.visible_orders(db, ctx, principal, status)
    return OrderListOut(orders=[mm.order_out(db, principal, o) for o in rows], demo_note=ms.demo_note(principal, bool(rows)))


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: uuid.UUID, principal: Reader, db: DB, ctx: Ctx) -> OrderOut:
    o = os_.get_order(db, principal, order_id)
    os_.expire_if_due(db, ctx, o)
    db.refresh(o)
    return mm.order_out(db, principal, o)


@router.post("/{order_id}/cancel", response_model=OrderOut, summary="Cancel an unpaid order (buyer or seller); its reservations are released")
def cancel_order(order_id: uuid.UUID, body: ReasonIn, principal: Canceller, db: DB, ctx: Ctx, key: IdemKey = None) -> OrderOut:
    return mm.order_out(db, principal, os_.cancel(db, ctx, principal, order_id, body.reason, key))


@router.post("/{order_id}/documents", response_model=DocumentRef, status_code=status.HTTP_201_CREATED,
             summary="Attach payment evidence (PAYMENT_EVIDENCE, PDF) before recording the payment")
def order_document(order_id: uuid.UUID, principal: Payer, db: DB, ctx: Ctx, file: Annotated[UploadFile, File()],
                   title: Annotated[str | None, Form(max_length=200)] = None) -> DocumentRef:
    return mm.doc_ref(os_.upload_document(db, ctx, principal, order_id, file.filename, read_upload(file), title))


@router.post("/{order_id}/retry-transfer", response_model=OrderOut,
             summary="Resolve an order that needs attention: re-reserve (when lost) and re-request the 9B transfers (seller, manual)")
def retry_transfer(order_id: uuid.UUID, body: ReasonIn, principal: Manager, db: DB, ctx: Ctx, key: IdemKey = None) -> OrderOut:
    return mm.order_out(db, principal, os_.retry_transfer(db, ctx, principal, order_id, body.reason, key))


@router.post("/{order_id}/confirmation", response_model=DocumentRef,
             summary="Deterministic ORDER_CONFIRMATION PDF (not a tax invoice) once the payment is confirmed")
def order_confirmation(order_id: uuid.UUID, principal: Reader, db: DB, ctx: Ctx) -> DocumentRef:
    return mm.doc_ref(os_.confirmation(db, ctx, principal, order_id))


@router.get("/{order_id}/lineage", response_model=LineageOut,
            summary="order → items → listing → 9B reservation → 9B transfer → ledger entry → batch (→ 9A lineage for credits.read)")
def order_lineage(order_id: uuid.UUID, principal: Reader, db: DB) -> LineageOut:
    return LineageOut(**os_.lineage(db, principal, order_id))


@router.post("/transfers/{transfer_id}/complete", response_model=OrderOut,
             summary="Complete an order-linked 9B transfer (custodian credits.confirm, never the requester; REGISTRY needs reference + PDF)")
def complete_order_transfer(transfer_id: uuid.UUID, principal: Confirmer, db: DB, ctx: Ctx, body: TransferCompleteIn | None = None,
                            key: IdemKey = None) -> OrderOut:
    return mm.order_out(db, principal, os_.complete_transfer(db, ctx, principal, transfer_id, body, key))


@router.post("/transfers/{transfer_id}/reject", response_model=OrderOut,
             summary="Reject an order-linked 9B transfer: credits return to the seller, the order needs attention (no silent retry)")
def reject_order_transfer(transfer_id: uuid.UUID, body: ReasonIn, principal: Confirmer, db: DB, ctx: Ctx, key: IdemKey = None) -> OrderOut:
    return mm.order_out(db, principal, os_.reject_transfer(db, ctx, principal, transfer_id, body.reason, key))
