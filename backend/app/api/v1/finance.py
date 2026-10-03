"""Finance API (Phase 11): `/api/v1/revenue`, `/costs`, `/revenue-share`, `/allocations`, `/settlements`.

Revenue is recognized by the server from Phase 10 records (per order item, payment CONFIRMED + 9B transfer COMPLETED) and reversed by
completed refunds — no endpoint accepts a revenue amount. Revenue-share versions and farm allocations are authored from the project's
agreements and approved by someone else; settlement figures and entitlements are calculated, frozen and hashed by the server. DEMO
projects are refused (no fake financial data). Every POST accepts an Idempotency-Key."""
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile, status

from app.api.deps import DB, Ctx, read_upload, require_any
from app.models import FarmAllocationVersion, RevenueShareVersion
from app.schemas.finance import (
    AllocationIn,
    AllocationOut,
    CostIn,
    CostOut,
    FinanceProjectOut,
    OptionalReasonIn,
    ReasonIn,
    RecognizeIn,
    RevenueOut,
    ReverseRefundIn,
    SettlementIn,
    SettlementOut,
    ShareVersionIn,
    ShareVersionOut,
    SummaryOut,
    VerifyOut,
)
from app.schemas.lab import DocumentRef
from app.security.permissions import P
from app.security.principal import Principal
from app.services import finance_mappers as fm
from app.services import finance_service as fs
from app.services import payout_service as pys
from app.services import settlement_service as ss

router = APIRouter(tags=["finance — revenue, sharing, costs, settlements"])

FinanceReader = Annotated[Principal, Depends(require_any(*fs.FIN_VIEW))]
RevenueManager = Annotated[Principal, Depends(require_any(P.REVENUE_MANAGE))]
SharingAuthor = Annotated[Principal, Depends(require_any(P.SHARING_MANAGE))]
SharingApprover = Annotated[Principal, Depends(require_any(P.SHARING_APPROVE))]
SharingAny = Annotated[Principal, Depends(require_any(P.SHARING_MANAGE, P.SHARING_APPROVE))]
CostManager = Annotated[Principal, Depends(require_any(P.COSTS_MANAGE))]
CostApprover = Annotated[Principal, Depends(require_any(P.COSTS_APPROVE))]
Calculator = Annotated[Principal, Depends(require_any(P.SETTLEMENT_CALCULATE))]
SettlementApprover = Annotated[Principal, Depends(require_any(P.SETTLEMENT_APPROVE))]
SettlementReader = Annotated[Principal, Depends(require_any(P.SETTLEMENT_READ, P.SETTLEMENT_CALCULATE, P.SETTLEMENT_APPROVE, P.PAYOUTS_READ,
                                                            P.REVENUE_READ))]
IdemKey = Annotated[str | None, Header(alias="Idempotency-Key", max_length=80)]


# ---------------------------------------------------------------- revenue
@router.get("/revenue/projects", response_model=list[FinanceProjectOut],
            summary="Projects the caller may see financially, with their monitoring periods and farm participations")
def finance_projects(principal: FinanceReader, db: DB) -> list[FinanceProjectOut]:
    return [fm.finance_project_out(db, p) for p in fs.visible_projects(db, principal)]


@router.get("/revenue", response_model=list[RevenueOut], summary="Recognized revenue and reversals of a project (append-only)")
def list_revenue(project_id: uuid.UUID, principal: FinanceReader, db: DB, monitoring_period_id: uuid.UUID | None = None) -> list[RevenueOut]:
    return [fm.revenue_out(db, r) for r in fs.revenue_rows(db, principal, project_id, monitoring_period_id)]


@router.get("/revenue/summary", response_model=SummaryOut,
            summary="Recognized / reversed / net revenue, approved costs by category, distributable / farmer / residual, payouts by status")
def revenue_summary(principal: FinanceReader, db: DB, project_id: uuid.UUID | None = None) -> dict[str, Any]:
    return pys.summary(db, principal, project_id)


@router.post("/revenue/recognize", response_model=RevenueOut,
             summary="Re-run the idempotent recognition of a delivered order item (the amount is the item's line total — never an input)")
def recognize(body: RecognizeIn, principal: RevenueManager, db: DB, ctx: Ctx) -> RevenueOut:
    return fm.revenue_out(db, fs.recognize(db, ctx, principal, body.order_item_id))


@router.post("/revenue/reverse-refund", response_model=list[RevenueOut],
             summary="Re-run the idempotent reversal of an order's revenue for a completed refund")
def reverse_refund(body: ReverseRefundIn, principal: RevenueManager, db: DB, ctx: Ctx) -> list[RevenueOut]:
    return [fm.revenue_out(db, r) for r in fs.reverse_refund(db, ctx, principal, body.refund_id)]


# ---------------------------------------------------------------- revenue-share versions
@router.get("/revenue-share", response_model=list[ShareVersionOut], summary="Revenue-share versions of a project")
def list_share_versions(project_id: uuid.UUID, principal: FinanceReader, db: DB) -> list[ShareVersionOut]:
    return [fm.share_out(db, v) for v in fs.share_versions(db, principal, project_id)]


@router.post("/revenue-share", response_model=ShareVersionOut, status_code=status.HTTP_201_CREATED,
             summary="Author a revenue-share version (DRAFT) from the project's agreements — no value is defaulted")
def create_share_version(body: ShareVersionIn, principal: SharingAuthor, db: DB, ctx: Ctx, key: IdemKey = None) -> ShareVersionOut:
    return fm.share_out(db, fs.create_share_version(db, ctx, principal, body, key))


@router.post("/revenue-share/{version_id}/submit", response_model=ShareVersionOut, summary="Submit for review (DRAFT → IN_REVIEW)")
def submit_share_version(version_id: uuid.UUID, principal: SharingAuthor, db: DB, ctx: Ctx, key: IdemKey = None) -> ShareVersionOut:
    return fm.share_out(db, fs.config_action(db, ctx, principal, RevenueShareVersion, version_id, "submit", None, key))


@router.post("/revenue-share/{version_id}/approve", response_model=ShareVersionOut,
             summary="Approve (never the author); the previous approved version becomes SUPERSEDED; immutable afterwards")
def approve_share_version(version_id: uuid.UUID, principal: SharingApprover, db: DB, ctx: Ctx, key: IdemKey = None) -> ShareVersionOut:
    return fm.share_out(db, fs.config_action(db, ctx, principal, RevenueShareVersion, version_id, "approve", None, key))


@router.post("/revenue-share/{version_id}/return", response_model=ShareVersionOut, summary="Return to the author with a reason")
def return_share_version(version_id: uuid.UUID, body: ReasonIn, principal: SharingApprover, db: DB, ctx: Ctx,
                         key: IdemKey = None) -> ShareVersionOut:
    return fm.share_out(db, fs.config_action(db, ctx, principal, RevenueShareVersion, version_id, "return", body.reason, key))


# ---------------------------------------------------------------- farm allocations
@router.get("/allocations", response_model=list[AllocationOut], summary="Per-period farm allocation versions of a project")
def list_allocations(project_id: uuid.UUID, principal: FinanceReader, db: DB, monitoring_period_id: uuid.UUID | None = None
                     ) -> list[AllocationOut]:
    return [fm.allocation_out(db, v) for v in fs.allocations(db, principal, project_id, monitoring_period_id)]


@router.post("/allocations", response_model=AllocationOut, status_code=status.HTTP_201_CREATED,
             summary="Author a farm allocation table for a monitoring period (DRAFT; every farm once; shares must total 100 to submit)")
def create_allocation(body: AllocationIn, principal: SharingAuthor, db: DB, ctx: Ctx, key: IdemKey = None) -> AllocationOut:
    return fm.allocation_out(db, fs.create_allocation(db, ctx, principal, body, key))


@router.post("/allocations/{version_id}/submit", response_model=AllocationOut, summary="Submit for review (validated: total exactly 100)")
def submit_allocation(version_id: uuid.UUID, principal: SharingAuthor, db: DB, ctx: Ctx, key: IdemKey = None) -> AllocationOut:
    return fm.allocation_out(db, fs.config_action(db, ctx, principal, FarmAllocationVersion, version_id, "submit", None, key))


@router.post("/allocations/{version_id}/approve", response_model=AllocationOut, summary="Approve (never the author); immutable afterwards")
def approve_allocation(version_id: uuid.UUID, principal: SharingApprover, db: DB, ctx: Ctx, key: IdemKey = None) -> AllocationOut:
    return fm.allocation_out(db, fs.config_action(db, ctx, principal, FarmAllocationVersion, version_id, "approve", None, key))


@router.post("/allocations/{version_id}/return", response_model=AllocationOut, summary="Return to the author with a reason")
def return_allocation(version_id: uuid.UUID, body: ReasonIn, principal: SharingApprover, db: DB, ctx: Ctx, key: IdemKey = None) -> AllocationOut:
    return fm.allocation_out(db, fs.config_action(db, ctx, principal, FarmAllocationVersion, version_id, "return", body.reason, key))


# ---------------------------------------------------------------- project costs
@router.get("/costs", response_model=list[CostOut], summary="Project costs (pending, approved, rejected, corrections)")
def list_costs(project_id: uuid.UUID, principal: FinanceReader, db: DB) -> list[CostOut]:
    return [fm.cost_out(db, c) for c in fs.costs(db, principal, project_id)]


@router.post("/costs", response_model=CostOut, status_code=status.HTTP_201_CREATED,
             summary="Record a project cost actually incurred (PENDING_APPROVAL; a negative amount corrects an approved cost)")
def create_cost(body: CostIn, principal: CostManager, db: DB, ctx: Ctx, key: IdemKey = None) -> CostOut:
    return fm.cost_out(db, fs.create_cost(db, ctx, principal, body, key))


@router.post("/costs/{cost_id}/documents", response_model=DocumentRef, status_code=status.HTTP_201_CREATED,
             summary="Attach cost evidence (COST_EVIDENCE, PDF)")
def cost_document(cost_id: uuid.UUID, principal: CostManager, db: DB, ctx: Ctx, file: Annotated[UploadFile, File()],
                  title: Annotated[str | None, Form(max_length=200)] = None) -> DocumentRef:
    return fm.doc_ref(fs.cost_evidence(db, ctx, principal, cost_id, file.filename, read_upload(file), title))


@router.post("/costs/{cost_id}/approve", response_model=CostOut, summary="Approve a cost with its evidence (never the recorder)")
def approve_cost(cost_id: uuid.UUID, principal: CostApprover, db: DB, ctx: Ctx, key: IdemKey = None) -> CostOut:
    return fm.cost_out(db, fs.decide_cost(db, ctx, principal, cost_id, True, None, key))


@router.post("/costs/{cost_id}/reject", response_model=CostOut, summary="Reject a cost with a reason (never the recorder)")
def reject_cost(cost_id: uuid.UUID, body: ReasonIn, principal: CostApprover, db: DB, ctx: Ctx, key: IdemKey = None) -> CostOut:
    return fm.cost_out(db, fs.decide_cost(db, ctx, principal, cost_id, False, body.reason, key))


# ---------------------------------------------------------------- settlement runs
@router.get("/settlements", response_model=list[SettlementOut], summary="Settlement runs of the organization's projects")
def list_settlements(principal: SettlementReader, db: DB, project_id: uuid.UUID | None = None, status: str | None = None
                     ) -> list[SettlementOut]:
    return [fm.settlement_out(db, r, detail=False) for r in ss.runs(db, principal, project_id, status)]


@router.post("/settlements", response_model=SettlementOut, status_code=status.HTTP_201_CREATED,
             summary="Create a settlement run (DRAFT) for a project / monitoring period / currency with APPROVED configuration")
def create_settlement(body: SettlementIn, principal: Calculator, db: DB, ctx: Ctx, key: IdemKey = None) -> SettlementOut:
    return fm.settlement_out(db, ss.create(db, ctx, principal, body, key))


@router.get("/settlements/{run_id}", response_model=SettlementOut, summary="A settlement run with its entitlements")
def get_settlement(run_id: uuid.UUID, principal: SettlementReader, db: DB) -> SettlementOut:
    return fm.settlement_out(db, ss.run_for(db, principal, run_id)[0])


@router.post("/settlements/{run_id}/calculate", response_model=SettlementOut,
             summary="Calculate (DRAFT → CALCULATED): claims unsettled revenue / costs, freezes inputs, hashes the snapshot")
def calculate_settlement(run_id: uuid.UUID, principal: Calculator, db: DB, ctx: Ctx, key: IdemKey = None) -> SettlementOut:
    return fm.settlement_out(db, ss.calculate(db, ctx, principal, run_id, key))


@router.get("/settlements/{run_id}/verify", response_model=VerifyOut, summary="Recompute the run from its frozen snapshot")
def verify_settlement(run_id: uuid.UUID, principal: SettlementReader, db: DB) -> dict[str, Any]:
    return ss.verify(db, principal, run_id)


@router.get("/settlements/{run_id}/lineage", summary="Run → configuration versions → revenue records → order / payment / transfer / batch")
def settlement_lineage(run_id: uuid.UUID, principal: SettlementReader, db: DB) -> dict[str, Any]:
    return pys.run_lineage(db, ss.run_for(db, principal, run_id)[0])


@router.post("/settlements/{run_id}/submit", response_model=SettlementOut, summary="Submit for approval")
def submit_settlement(run_id: uuid.UUID, principal: Calculator, db: DB, ctx: Ctx, key: IdemKey = None) -> SettlementOut:
    return fm.settlement_out(db, ss.action(db, ctx, principal, run_id, "submit", None, key))


@router.post("/settlements/{run_id}/approve", response_model=SettlementOut,
             summary="Approve (never the calculator; the run must reproduce from its snapshot)")
def approve_settlement(run_id: uuid.UUID, principal: SettlementApprover, db: DB, ctx: Ctx, key: IdemKey = None) -> SettlementOut:
    return fm.settlement_out(db, ss.action(db, ctx, principal, run_id, "approve", None, key))


@router.post("/settlements/{run_id}/reject", response_model=SettlementOut, summary="Reject with a reason (frees the inputs for a new run)")
def reject_settlement(run_id: uuid.UUID, body: ReasonIn, principal: SettlementApprover, db: DB, ctx: Ctx, key: IdemKey = None) -> SettlementOut:
    return fm.settlement_out(db, ss.action(db, ctx, principal, run_id, "reject", body.reason, key))


@router.post("/settlements/{run_id}/cancel", response_model=SettlementOut, summary="Cancel a DRAFT / CALCULATED run with a reason")
def cancel_settlement(run_id: uuid.UUID, body: OptionalReasonIn, principal: Calculator, db: DB, ctx: Ctx, key: IdemKey = None) -> SettlementOut:
    return fm.settlement_out(db, ss.action(db, ctx, principal, run_id, "cancel", body.reason, key))
