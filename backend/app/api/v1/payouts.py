"""Payouts API (`/api/v1/payouts`, Phase 11). Payouts are calculated from an APPROVED settlement run — no request carries a payout amount.
Calculator ≠ approver ≠ executor; executor ≠ reconciler. LIVE uses the MANUAL adapter: finance pays at the bank and records the reference
with a PAYOUT_EVIDENCE PDF (PAID); a different person reconciles it against a statement (RECONCILED). `/payouts/me` is the farmer's own
view. Recovery cases (`/payouts/adjustments`) are closed manually — never an automatic clawback. Every POST accepts an Idempotency-Key."""
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile, status

from app.api.deps import DB, Ctx, read_upload, require_any
from app.schemas.finance import (
    AdjustmentOut,
    ConfirmPaidIn,
    MyPayoutsOut,
    OptionalReasonIn,
    PayoutOut,
    ReasonIn,
    ReconcileIn,
    ReconciliationOut,
    ResolutionIn,
)
from app.schemas.lab import DocumentRef
from app.security.permissions import P
from app.security.principal import Principal
from app.services import finance_mappers as fm
from app.services import finance_service as fs
from app.services import payout_service as pys
from app.services import settlement_service as ss

router = APIRouter(tags=["finance — payouts"])

Reader = Annotated[Principal, Depends(require_any(*pys.PAYOUT_VIEW, P.SETTLEMENT_READ))]
Calculator = Annotated[Principal, Depends(require_any(P.PAYOUTS_CALCULATE))]
Approver = Annotated[Principal, Depends(require_any(P.PAYOUTS_APPROVE))]
Executor = Annotated[Principal, Depends(require_any(P.PAYOUTS_EXECUTE))]
Reconciler = Annotated[Principal, Depends(require_any(P.PAYOUTS_RECONCILE))]
EvidenceUploader = Annotated[Principal, Depends(require_any(P.PAYOUTS_EXECUTE, P.PAYOUTS_RECONCILE))]
FarmerSelf = Annotated[Principal, Depends(require_any(P.FARMERS_SELF))]
IdemKey = Annotated[str | None, Header(alias="Idempotency-Key", max_length=80)]


@router.get("/payouts/me", response_model=MyPayoutsOut, summary="My payouts (farmer self-service: own payouts only)")
def my_payouts(principal: FarmerSelf, db: DB) -> MyPayoutsOut:
    linked = bool(pys.my_farmers(db, principal))
    rows = pys.my_payouts(db, principal)
    note = fs.DEMO_NOTE if principal.user.environment == "DEMO" else (
        None if linked else "Your account is not linked to a farmer profile; ask your project developer.")
    return MyPayoutsOut(farmer_linked=linked, payouts=[fm.my_payout_out(db, p) for p in rows], note=note)


@router.get("/payouts/adjustments", response_model=list[AdjustmentOut],
            summary="Recovery cases: reversals of revenue that was already paid out (manual resolution, no automatic clawback)")
def list_adjustments(principal: Reader, db: DB, project_id: uuid.UUID | None = None) -> list[AdjustmentOut]:
    return [fm.adjustment_out(db, a) for a in ss.adjustments(db, principal, project_id)]


@router.post("/payouts/adjustments/{adjustment_id}/close", response_model=AdjustmentOut, summary="Close a recovery case with its resolution")
def close_adjustment(adjustment_id: uuid.UUID, body: ResolutionIn, principal: Reconciler, db: DB, ctx: Ctx, key: IdemKey = None
                     ) -> AdjustmentOut:
    return fm.adjustment_out(db, pys.close_adjustment(db, ctx, principal, adjustment_id, body.resolution, key))


@router.get("/payouts", response_model=list[PayoutOut], summary="Payouts of the organization's projects")
def list_payouts(principal: Reader, db: DB, settlement_run_id: uuid.UUID | None = None, status: str | None = None) -> list[PayoutOut]:
    return [fm.payout_out(db, p) for p in pys.payouts(db, principal, run_id=settlement_run_id, status=status)]


@router.post("/payouts/from-settlement/{run_id}", response_model=list[PayoutOut], status_code=status.HTTP_201_CREATED,
             summary="Calculate payouts from an APPROVED run (one per farmer: Σ the farmer's entitlements; idempotent)")
def create_payouts(run_id: uuid.UUID, principal: Calculator, db: DB, ctx: Ctx) -> list[PayoutOut]:
    return [fm.payout_out(db, p) for p in pys.create_for_run(db, ctx, principal, run_id)]


@router.get("/payouts/{payout_id}", response_model=PayoutOut, summary="A payout with its transactions and reconciliations")
def get_payout(payout_id: uuid.UUID, principal: Reader, db: DB) -> PayoutOut:
    return fm.payout_out(db, pys.payout_for(db, principal, payout_id))


@router.get("/payouts/{payout_id}/lineage", summary="Payout → entitlements → settlement run → configuration → revenue → Phase 10 / 9B records")
def payout_lineage(payout_id: uuid.UUID, principal: Reader, db: DB) -> dict[str, Any]:
    return pys.lineage(db, principal, payout_id)


@router.post("/payouts/{payout_id}/submit", response_model=PayoutOut, summary="Submit for approval")
def submit_payout(payout_id: uuid.UUID, principal: Calculator, db: DB, ctx: Ctx, key: IdemKey = None) -> PayoutOut:
    return fm.payout_out(db, pys.action(db, ctx, principal, payout_id, "submit", None, key))


@router.post("/payouts/{payout_id}/approve", response_model=PayoutOut,
             summary="Approve (never the calculator; requires the farmer's primary VERIFIED bank account)")
def approve_payout(payout_id: uuid.UUID, principal: Approver, db: DB, ctx: Ctx, key: IdemKey = None) -> PayoutOut:
    return fm.payout_out(db, pys.action(db, ctx, principal, payout_id, "approve", None, key))


@router.post("/payouts/{payout_id}/reject", response_model=PayoutOut, summary="Reject with a reason")
def reject_payout(payout_id: uuid.UUID, body: ReasonIn, principal: Approver, db: DB, ctx: Ctx, key: IdemKey = None) -> PayoutOut:
    return fm.payout_out(db, pys.action(db, ctx, principal, payout_id, "reject", body.reason, key))


@router.post("/payouts/{payout_id}/cancel", response_model=PayoutOut, summary="Cancel a payout not yet executed, with a reason")
def cancel_payout(payout_id: uuid.UUID, body: OptionalReasonIn, principal: Calculator, db: DB, ctx: Ctx, key: IdemKey = None) -> PayoutOut:
    return fm.payout_out(db, pys.action(db, ctx, principal, payout_id, "cancel", body.reason, key))


@router.post("/payouts/{payout_id}/release-hold", response_model=PayoutOut, summary="Return an ON_HOLD payout to approval, with a reason")
def release_hold(payout_id: uuid.UUID, body: ReasonIn, principal: Calculator, db: DB, ctx: Ctx, key: IdemKey = None) -> PayoutOut:
    return fm.payout_out(db, pys.action(db, ctx, principal, payout_id, "release", body.reason, key))


@router.post("/payouts/{payout_id}/reissue", response_model=PayoutOut, status_code=status.HTTP_201_CREATED,
             summary="Replace a FAILED payout by a new CALCULATED payout of the same entitlement")
def reissue_payout(payout_id: uuid.UUID, principal: Calculator, db: DB, ctx: Ctx, key: IdemKey = None) -> PayoutOut:
    return fm.payout_out(db, pys.reissue(db, ctx, principal, payout_id, key))


@router.post("/payouts/{payout_id}/initiate", response_model=PayoutOut,
             summary="Execute (never the approver or calculator): re-checks the bank account, then PAYMENT_PENDING (MANUAL: pay at the bank)")
def initiate_payout(payout_id: uuid.UUID, principal: Executor, db: DB, ctx: Ctx, key: IdemKey = None) -> PayoutOut:
    return fm.payout_out(db, pys.initiate(db, ctx, principal, payout_id, key))


@router.post("/payouts/{payout_id}/documents", response_model=DocumentRef, status_code=status.HTTP_201_CREATED,
             summary="Attach PAYOUT_EVIDENCE (executor, while pending) or RECONCILIATION_EVIDENCE (reconciler, when PAID) — PDF")
def payout_document(payout_id: uuid.UUID, principal: EvidenceUploader, db: DB, ctx: Ctx, file: Annotated[UploadFile, File()],
                    category: Annotated[str, Form()], title: Annotated[str | None, Form(max_length=200)] = None) -> DocumentRef:
    return fm.doc_ref(pys.upload_evidence(db, ctx, principal, payout_id, category, file.filename, read_upload(file), title))


@router.post("/payouts/{payout_id}/confirm-paid", response_model=PayoutOut,
             summary="MANUAL: record the bank reference and remittance evidence (PAID — not yet reconciled)")
def confirm_paid(payout_id: uuid.UUID, body: ConfirmPaidIn, principal: Executor, db: DB, ctx: Ctx, key: IdemKey = None) -> PayoutOut:
    return fm.payout_out(db, pys.confirm_paid(db, ctx, principal, payout_id, body, key))


@router.post("/payouts/{payout_id}/fail", response_model=PayoutOut, summary="Record that the payment failed, with a reason")
def fail_payout(payout_id: uuid.UUID, body: ReasonIn, principal: Executor, db: DB, ctx: Ctx, key: IdemKey = None) -> PayoutOut:
    return fm.payout_out(db, pys.fail(db, ctx, principal, payout_id, body.reason, key))


@router.post("/payouts/{payout_id}/query-status", response_model=PayoutOut,
             summary="Ask the payout provider for the status (MANUAL: refused — there is no provider)")
def query_status(payout_id: uuid.UUID, principal: Executor, db: DB, ctx: Ctx) -> PayoutOut:
    return fm.payout_out(db, pys.query_status(db, ctx, principal, payout_id))


@router.post("/payouts/{payout_id}/reconcile", response_model=ReconciliationOut,
             summary="Reconcile a PAID payout against a statement (never the executor): MATCHED → RECONCILED, otherwise EXCEPTION")
def reconcile_payout(payout_id: uuid.UUID, body: ReconcileIn, principal: Reconciler, db: DB, ctx: Ctx, key: IdemKey = None
                     ) -> ReconciliationOut:
    rec = pys.reconcile(db, ctx, principal, payout_id, body, key)
    return ReconciliationOut(id=rec.id, result=rec.result, statement_reference=rec.statement_reference, statement_amount=rec.statement_amount,
                             statement_currency=rec.statement_currency, statement_date=rec.statement_date, note=rec.note,
                             reconciled_by_name=principal.user.full_name, created_at=rec.created_at)
