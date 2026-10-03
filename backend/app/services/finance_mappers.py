"""Phase 11 mappers. Explicit allow-lists: finance users see the financial records of their organization's projects (farmer names,
amounts, the last 4 digits of the referenced bank account — never the account number, routing code or holder data); a farmer sees only
their own payouts (amount, status, dates, last 4) and nothing about other farmers, actors or documents."""
import uuid
from decimal import Decimal

from sqlalchemy import select, true
from sqlalchemy.orm import Session

from app.models import (
    CreditBatch,
    CreditTransfer,
    Document,
    Farm,
    FarmAllocationVersion,
    Farmer,
    MonitoringPeriod,
    Order,
    OrderItem,
    Payment,
    Payout,
    PayoutAdjustment,
    Project,
    ProjectCost,
    ProjectFarm,
    Refund,
    RevenueRecord,
    RevenueShareVersion,
    SettlementCostItem,
    SettlementRevenueItem,
    SettlementRun,
    User,
)
from app.schemas.finance import (
    AdjustmentOut,
    AllocationLineOut,
    AllocationOut,
    CostOut,
    EntitlementOut,
    FinanceProjectOut,
    MyPayoutOut,
    PayoutOut,
    PeriodRef,
    ProjectFarmRef,
    ReconciliationOut,
    RevenueOut,
    SettlementOut,
    ShareVersionOut,
    TransactionOut,
)
from app.schemas.lab import DocumentRef
from app.services import document_service
from app.services import finance_service as fs
from app.services import payout_service as pys
from app.services import settlement_service as ss


def _name(db: Session, user_id: uuid.UUID | None) -> str | None:
    u = db.get(User, user_id) if user_id else None
    return u.full_name if u else None


def _farmer(db: Session, farmer_id: uuid.UUID) -> str | None:
    f = db.get(Farmer, farmer_id)
    return f.full_name if f else None


def _farm(db: Session, farm_id: uuid.UUID) -> str | None:
    f = db.get(Farm, farm_id)
    return f.name if f else None


def _period(db: Session, period_id: uuid.UUID | None) -> int | None:
    mp = db.get(MonitoringPeriod, period_id) if period_id else None
    return mp.period_number if mp else None


def doc_ref(d: Document) -> DocumentRef:
    v = max(d.versions, key=lambda x: x.version) if d.versions else None
    return DocumentRef(document_id=d.id, category=d.category, title=d.title, file_name=v.file_name if v else None,
                       sha256=v.checksum_sha256 if v else None, uploaded_at=v.uploaded_at if v else d.created_at)


def _run_code(db: Session, model: type, column: str, record_id: uuid.UUID) -> str | None:
    run_id = db.scalar(select(model.settlement_run_id).where(getattr(model, column) == record_id, model.active == true()))  # type: ignore[attr-defined]
    run = db.get(SettlementRun, run_id) if run_id else None
    return run.run_code if run else None


def finance_project_out(db: Session, p: Project) -> FinanceProjectOut:
    periods = db.scalars(select(MonitoringPeriod).where(MonitoringPeriod.project_id == p.id).order_by(MonitoringPeriod.period_number)).all()
    pfs = db.scalars(select(ProjectFarm).where(ProjectFarm.project_id == p.id).order_by(ProjectFarm.added_at)).all()
    return FinanceProjectOut(id=p.id, project_code=p.project_code, name=p.name, organization_id=p.organization_id, environment=p.environment,
                             periods=[PeriodRef(id=m.id, period_number=m.period_number, name=m.name, start_date=m.start_date,
                                                end_date=m.end_date) for m in periods],
                             farms=[ProjectFarmRef(project_farm_id=pf.id, farm_name=_farm(db, pf.farm_id), farmer_name=_farmer(db, pf.farmer_id),
                                                   status=pf.status) for pf in pfs])


def revenue_out(db: Session, r: RevenueRecord) -> RevenueOut:
    o, oi = db.get(Order, r.order_id), db.get(OrderItem, r.order_item_id)
    pay, tr, b = db.get(Payment, r.payment_id), db.get(CreditTransfer, r.transfer_id), db.get(CreditBatch, r.batch_id)
    orig = db.get(RevenueRecord, r.reverses_revenue_id) if r.reverses_revenue_id else None
    rf = db.get(Refund, r.refund_id) if r.refund_id else None
    return RevenueOut(id=r.id, revenue_code=r.revenue_code, kind=r.kind, amount=r.amount, currency=r.currency, project_id=r.project_id,
                      monitoring_period_id=r.monitoring_period_id, order_code=o.order_code if o else None,
                      order_item_code=oi.item_code if oi else None, payment_code=pay.payment_code if pay else None,
                      transfer_code=tr.transfer_code if tr else None, batch_code=b.batch_code if b else None,
                      reverses_revenue_code=orig.revenue_code if orig else None, refund_code=rf.refund_code if rf else None,
                      seller_organization_id=r.seller_organization_id,
                      settled_in_run_code=_run_code(db, SettlementRevenueItem, "revenue_record_id", r.id), recorded_at=r.recorded_at,
                      environment=r.environment)


def share_out(db: Session, v: RevenueShareVersion) -> ShareVersionOut:
    return ShareVersionOut(id=v.id, version_code=v.version_code, project_id=v.project_id, version_no=v.version_no,
                           farmer_share_pct=v.farmer_share_pct, deduct_approved_costs=v.deduct_approved_costs, rounding_mode=v.rounding_mode,
                           effective_from=v.effective_from, effective_to=v.effective_to, source_reference=v.source_reference, notes=v.notes,
                           status=v.status, created_by_name=_name(db, v.created_by), approved_by_name=_name(db, v.approved_by),
                           approved_at=v.approved_at, return_reason=v.return_reason, created_at=v.created_at, environment=v.environment)


def allocation_out(db: Session, v: FarmAllocationVersion) -> AllocationOut:
    lines = fs.allocation_lines(db, v.id)
    return AllocationOut(id=v.id, version_code=v.version_code, project_id=v.project_id, monitoring_period_id=v.monitoring_period_id,
                         period_number=_period(db, v.monitoring_period_id), version_no=v.version_no, basis_reference=v.basis_reference,
                         status=v.status, total_pct=sum((ln.share_pct for ln in lines), Decimal(0)),
                         lines=[AllocationLineOut(id=ln.id, project_farm_id=ln.project_farm_id, farm_id=ln.farm_id, farm_name=_farm(db, ln.farm_id),
                                                  farmer_id=ln.farmer_id, farmer_name=_farmer(db, ln.farmer_id), share_pct=ln.share_pct)
                                for ln in lines],
                         created_by_name=_name(db, v.created_by), approved_by_name=_name(db, v.approved_by), approved_at=v.approved_at,
                         return_reason=v.return_reason, created_at=v.created_at, environment=v.environment)


def cost_out(db: Session, c: ProjectCost) -> CostOut:
    return CostOut(id=c.id, cost_code=c.cost_code, project_id=c.project_id, monitoring_period_id=c.monitoring_period_id, category=c.category,
                   description=c.description, amount=c.amount, currency=c.currency, incurred_on=c.incurred_on,
                   external_reference=c.external_reference, corrects_cost_id=c.corrects_cost_id, status=c.status,
                   created_by_name=_name(db, c.created_by), approved_by_name=_name(db, c.approved_by), reject_reason=c.reject_reason,
                   settled_in_run_code=_run_code(db, SettlementCostItem, "project_cost_id", c.id),
                   documents=[doc_ref(d) for d in document_service.list_for(db, fs.COST_ENTITY, c.id)], created_at=c.created_at,
                   environment=c.environment)


def settlement_out(db: Session, r: SettlementRun, *, detail: bool = True) -> SettlementOut:
    p = db.get(Project, r.project_id)
    rv, av = db.get(RevenueShareVersion, r.revenue_share_version_id), db.get(FarmAllocationVersion, r.allocation_version_id)
    ents = ss.entitlements(db, r.id) if detail else []
    return SettlementOut(
        id=r.id, run_code=r.run_code, project_id=r.project_id, project_code=p.project_code if p else None,
        monitoring_period_id=r.monitoring_period_id, period_number=_period(db, r.monitoring_period_id), currency=r.currency,
        revenue_share_version_code=rv.version_code if rv else None, allocation_version_code=av.version_code if av else None,
        calculation_version=r.calculation_version, gross_revenue=r.gross_revenue, deducted_costs=r.deducted_costs, distributable=r.distributable,
        farmer_total=r.farmer_total, developer_residual=r.developer_residual, input_sha256=r.input_sha256, status=r.status,
        created_by_name=_name(db, r.created_by), calculated_by_name=_name(db, r.calculated_by), calculated_at=r.calculated_at,
        approved_by_name=_name(db, r.approved_by), approved_at=r.approved_at, close_reason=r.close_reason,
        revenue_count=len(ss.revenue_items(db, r.id)) if detail else 0, cost_count=len(ss.cost_items(db, r.id)) if detail else 0,
        entitlements=[EntitlementOut(id=e.id, allocation_line_id=e.allocation_line_id, project_farm_id=e.project_farm_id, farm_id=e.farm_id,
                                     farm_name=_farm(db, e.farm_id), farmer_id=e.farmer_id, farmer_name=_farmer(db, e.farmer_id),
                                     share_pct=e.share_pct, amount=e.amount, currency=e.currency) for e in ents],
        created_at=r.created_at, environment=r.environment)


def payout_out(db: Session, po: Payout) -> PayoutOut:
    run = db.get(SettlementRun, po.settlement_run_id)
    prev = db.get(Payout, po.replaces_payout_id) if po.replaces_payout_id else None
    return PayoutOut(
        id=po.id, payout_code=po.payout_code, settlement_run_id=po.settlement_run_id, run_code=run.run_code if run else None,
        farmer_id=po.farmer_id, farmer_name=_farmer(db, po.farmer_id), amount=po.amount, currency=po.currency, status=po.status,
        adapter_code=po.adapter_code, bank_last4=po.bank_last4, external_reference=po.external_reference,
        replaces_payout_code=prev.payout_code if prev else None, reason=po.reason, calculated_by_name=_name(db, po.calculated_by),
        approved_by_name=_name(db, po.approved_by), executed_by_name=_name(db, po.executed_by), paid_at=po.paid_at,
        reconciled_at=po.reconciled_at, calculated_at=po.calculated_at,
        transactions=[TransactionOut(kind=t.kind, adapter_code=t.adapter_code, external_reference=t.external_reference, amount=t.amount,
                                     currency=t.currency, note=t.note, actor_name=_name(db, t.actor_id), created_at=t.created_at)
                      for t in pys.transactions(db, po.id)],
        reconciliations=[ReconciliationOut(id=x.id, result=x.result, statement_reference=x.statement_reference,
                                           statement_amount=x.statement_amount, statement_currency=x.statement_currency,
                                           statement_date=x.statement_date, note=x.note, reconciled_by_name=_name(db, x.reconciled_by),
                                           created_at=x.created_at) for x in pys.reconciliations(db, po.id)],
        documents=[doc_ref(d) for d in document_service.list_for(db, pys.ENTITY, po.id)], environment=po.environment)


def my_payout_out(db: Session, po: Payout) -> MyPayoutOut:
    run = db.get(SettlementRun, po.settlement_run_id)
    p = db.get(Project, run.project_id) if run else None
    return MyPayoutOut(payout_code=po.payout_code, amount=po.amount, currency=po.currency, status=po.status,
                       project_code=p.project_code if p else None, period_number=_period(db, run.monitoring_period_id if run else None),
                       bank_last4=po.bank_last4, paid_at=po.paid_at, reconciled_at=po.reconciled_at, calculated_at=po.calculated_at)


def adjustment_out(db: Session, a: PayoutAdjustment) -> AdjustmentOut:
    rec = db.get(RevenueRecord, a.reversal_revenue_id)
    run = db.get(SettlementRun, a.original_settlement_run_id)
    return AdjustmentOut(id=a.id, adjustment_code=a.adjustment_code, project_id=a.project_id,
                         reversal_revenue_code=rec.revenue_code if rec else None, original_run_code=run.run_code if run else None,
                         amount=a.amount, currency=a.currency, status=a.status, resolution=a.resolution, closed_by_name=_name(db, a.closed_by),
                         closed_at=a.closed_at, created_at=a.created_at)
