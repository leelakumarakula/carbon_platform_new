"""Phase 11 — shared finance access, revenue recognition / reversal, revenue-share versions, farm allocation tables, project costs.

Revenue (D8–D10, locked): recognized per ORDER ITEM, from immutable Phase 10 records, only when the order's payment is CONFIRMED and
the item's 9B transfer is COMPLETED — inside the Phase 10 delivery-completion transaction (`recognize_in_tx`); a completed refund of the
order creates one REVERSAL per recognition (`reverse_for_refund_in_tx`). Recognition is idempotent (one per order item, unique index) and
never edited. No endpoint accepts a revenue amount.

Configuration (D1 / D2 / D3 / D6 / D12 / D27 as configuration): the farmer share percentage, whether approved costs are deducted and the
rounding mode live in a project revenue-share VERSION; the split across farms lives in a per-period farm ALLOCATION version. Both are
authored from the project's agreements, approved by a different person, immutable once approved, superseded by new versions.
Nothing is defaulted. DEMO holds no financial record (D35): every write on a DEMO project is refused.
"""
import uuid
from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.context import RequestContext
from app.core.errors import Conflict, NotFound, PermissionDenied, ValidationFailed
from app.models import (
    CreditBatch,
    CreditTransfer,
    Document,
    FarmAllocationLine,
    FarmAllocationVersion,
    MonitoringPeriod,
    Order,
    OrderItem,
    Payment,
    Project,
    ProjectCost,
    ProjectFarm,
    Refund,
    RevenueRecord,
    RevenueShareVersion,
)
from app.models.base import utcnow
from app.models.documents import DocumentCategory
from app.repositories.sequences import next_code
from app.security.permissions import P
from app.security.principal import Principal
from app.services import document_service
from app.services import ledger_service as ls
from app.services import marketplace_service as ms
from app.services.workflows import PROJECT_COST_MACHINE, SHARING_CONFIG_MACHINE

COST_ENTITY = "project_cost"
FIN_VIEW = (P.REVENUE_READ, P.REVENUE_MANAGE, P.SETTLEMENT_READ, P.SETTLEMENT_CALCULATE, P.SETTLEMENT_APPROVE, P.PAYOUTS_READ,
            P.PAYOUTS_CALCULATE, P.PAYOUTS_APPROVE, P.PAYOUTS_EXECUTE, P.PAYOUTS_RECONCILE, P.SHARING_MANAGE, P.SHARING_APPROVE,
            P.COSTS_MANAGE, P.COSTS_APPROVE)
DEMO_NOTE = "DEMO — no registry-issued credits; no revenue, cost, entitlement or payout exists in DEMO"


# ---------------------------------------------------------------- access
def project_for(db: Session, principal: Principal, project_id: uuid.UUID, *codes: str) -> Project:
    """The project, if the caller holds one of `codes` in its organization (404 outside scope, 403 visible but not allowed)."""
    p = db.get(Project, project_id)
    if p is None:
        raise ms.nf("Project", "PROJECT_NOT_FOUND")
    ms.require(principal, p.organization_id, *(codes or FIN_VIEW), visible=FIN_VIEW, what="Project", nf_code="PROJECT_NOT_FOUND")
    return p


def writable(p: Project) -> None:
    if p.environment == "DEMO":
        raise Conflict("DEMO has no registry-issued credits: no revenue, cost, sharing configuration, settlement or payout is created in DEMO.",
                       error_code="DEMO_FINANCE_NOT_ALLOWED")


def period_of(db: Session, p: Project, period_id: uuid.UUID) -> MonitoringPeriod:
    mp = db.get(MonitoringPeriod, period_id)
    if mp is None or mp.project_id != p.id:
        raise ms.nf("Monitoring period", "MONITORING_PERIOD_NOT_FOUND")
    return mp


def visible_projects(db: Session, principal: Principal) -> list[Project]:
    return [p for p in db.scalars(select(Project).order_by(Project.project_code)).all()
            if any(principal.can_in_org(c, p.organization_id) for c in FIN_VIEW)]


# ---------------------------------------------------------------- revenue recognition (D8, D9) and reversal (D10)
def recognize_in_tx(db: Session, ctx: RequestContext, *, order: Order, item: OrderItem, actor_id: uuid.UUID | None) -> RevenueRecord | None:
    """One RECOGNITION per order item, inside the caller's transaction, when the order's payment is CONFIRMED and the item's 9B transfer
    is COMPLETED. Idempotent: an existing recognition is returned unchanged."""
    existing = db.scalars(select(RevenueRecord).where(RevenueRecord.order_item_id == item.id, RevenueRecord.kind == "RECOGNITION")).first()
    if existing is not None:
        return existing
    transfer = db.get(CreditTransfer, item.transfer_id) if item.transfer_id else None
    payment = db.scalars(select(Payment).where(Payment.order_id == order.id, Payment.status == "CONFIRMED")).first()
    if transfer is None or transfer.status != "COMPLETED" or payment is None:
        return None
    b = db.get(CreditBatch, item.batch_id)
    assert b is not None
    r = RevenueRecord(revenue_code=next_code(db, "revenue", utcnow().year), kind="RECOGNITION", order_item_id=item.id, order_id=order.id,
                      payment_id=payment.id, transfer_id=transfer.id, batch_id=b.id, project_id=b.project_id,
                      monitoring_period_id=b.monitoring_period_id, seller_organization_id=order.seller_organization_id, amount=item.line_total,
                      currency=order.currency, recorded_by=actor_id, environment=order.environment)
    db.add(r)
    db.flush()
    p = db.get(Project, b.project_id)
    ls.audit(db, ctx, "REVENUE_RECOGNIZED", "revenue_record", r.id, [order.seller_organization_id, p.organization_id if p else None],
             {"revenue_code": r.revenue_code, "order_item": item.item_code, "amount": str(r.amount), "currency": r.currency,
              "transfer_id": transfer.id, "payment_id": payment.id, "batch_id": b.id})
    return r


def reverse_for_refund_in_tx(db: Session, ctx: RequestContext, *, refund: Refund, order: Order, actor_id: uuid.UUID | None) -> list[RevenueRecord]:
    """A COMPLETED refund of an order reverses every recognition of that order not yet reversed (never an edit). Idempotent."""
    out = []
    for rec in db.scalars(select(RevenueRecord).where(RevenueRecord.order_id == order.id, RevenueRecord.kind == "RECOGNITION")
                          .order_by(RevenueRecord.revenue_code)).all():
        if db.scalars(select(RevenueRecord.id).where(RevenueRecord.reverses_revenue_id == rec.id)).first():
            continue
        rv = RevenueRecord(revenue_code=next_code(db, "revenue", utcnow().year), kind="REVERSAL", order_item_id=rec.order_item_id,
                           order_id=rec.order_id, payment_id=rec.payment_id, transfer_id=rec.transfer_id, batch_id=rec.batch_id,
                           project_id=rec.project_id, monitoring_period_id=rec.monitoring_period_id,
                           seller_organization_id=rec.seller_organization_id, reverses_revenue_id=rec.id, refund_id=refund.id,
                           amount=-rec.amount, currency=rec.currency, recorded_by=actor_id, environment=rec.environment)
        db.add(rv)
        db.flush()
        p = db.get(Project, rec.project_id)
        ls.audit(db, ctx, "REVENUE_REVERSED", "revenue_record", rv.id, [rec.seller_organization_id, p.organization_id if p else None],
                 {"revenue_code": rv.revenue_code, "reverses": rec.revenue_code, "refund": refund.refund_code, "amount": str(rv.amount)})
        out.append(rv)
    return out


def recognize(db: Session, ctx: RequestContext, principal: Principal, order_item_id: uuid.UUID) -> RevenueRecord:
    """Re-run the idempotent recognition for one order item (e.g. delivered before Phase 11 existed). Never takes an amount."""
    it = db.get(OrderItem, order_item_id)
    o = db.get(Order, it.order_id) if it else None
    if it is None or o is None:
        raise ms.nf("Order item", "ORDER_ITEM_NOT_FOUND")
    ms.require(principal, o.seller_organization_id, P.REVENUE_MANAGE, visible=FIN_VIEW, what="Order item", nf_code="ORDER_ITEM_NOT_FOUND")

    def op() -> RevenueRecord:
        x = ms.lock(db, Order, o.id)                                # serializes with the Phase 10 delivery completion (same lock order)
        item = db.get(OrderItem, it.id)
        assert item is not None
        if item.status != "DELIVERED":
            raise Conflict(f"Revenue is recognized only after delivery (item {item.item_code} is {item.status}).",
                           error_code="REVENUE_NOT_RECOGNIZABLE")
        r = recognize_in_tx(db, ctx, order=x, item=item, actor_id=principal.user_id)
        if r is None:
            raise Conflict("Revenue is recognized only when the payment is CONFIRMED and the credit transfer is COMPLETED.",
                           error_code="REVENUE_NOT_RECOGNIZABLE")
        return r
    return ls.run(db, ctx, op)


def reverse_refund(db: Session, ctx: RequestContext, principal: Principal, refund_id: uuid.UUID) -> list[RevenueRecord]:
    rf = db.get(Refund, refund_id)
    o = db.get(Order, rf.order_id) if rf else None
    if rf is None or o is None:
        raise ms.nf("Refund", "REFUND_NOT_FOUND")
    ms.require(principal, o.seller_organization_id, P.REVENUE_MANAGE, visible=FIN_VIEW, what="Refund", nf_code="REFUND_NOT_FOUND")
    if rf.status != "COMPLETED":
        raise Conflict("Only a completed refund reverses revenue.", error_code="REFUND_NOT_COMPLETED")

    def op() -> list[RevenueRecord]:
        x = ms.lock(db, Order, o.id)
        return reverse_for_refund_in_tx(db, ctx, refund=rf, order=x, actor_id=principal.user_id)
    return ls.run(db, ctx, op)


def revenue_rows(db: Session, principal: Principal, project_id: uuid.UUID, period_id: uuid.UUID | None = None) -> list[RevenueRecord]:
    p = project_for(db, principal, project_id, P.REVENUE_READ, P.REVENUE_MANAGE, P.SETTLEMENT_READ)
    stmt = select(RevenueRecord).where(RevenueRecord.project_id == p.id)
    if period_id:
        stmt = stmt.where(RevenueRecord.monitoring_period_id == period_id)
    return list(db.scalars(stmt.order_by(RevenueRecord.recorded_at, RevenueRecord.revenue_code)).all())


# ---------------------------------------------------------------- revenue-share versions (D1 / D2 / D3 / D6 / D27 as configuration)
def share_versions(db: Session, principal: Principal, project_id: uuid.UUID) -> list[RevenueShareVersion]:
    p = project_for(db, principal, project_id)
    return list(db.scalars(select(RevenueShareVersion).where(RevenueShareVersion.project_id == p.id)
                           .order_by(RevenueShareVersion.version_no.desc())).all())


def create_share_version(db: Session, ctx: RequestContext, principal: Principal, data: Any, key: str | None) -> RevenueShareVersion:
    if key and (prior := db.scalars(select(RevenueShareVersion).where(RevenueShareVersion.request_key == key)).first()) is not None:
        return prior
    p = project_for(db, principal, data.project_id, P.SHARING_MANAGE)
    writable(p)
    if data.effective_to and data.effective_to < data.effective_from:
        raise ValidationFailed("effective_to is before effective_from.", error_code="INVALID_DATES")

    def op() -> RevenueShareVersion:
        ms.lock(db, Project, p.id)
        n = int(db.scalar(select(func.coalesce(func.max(RevenueShareVersion.version_no), 0)).where(RevenueShareVersion.project_id == p.id)) or 0)
        v = RevenueShareVersion(version_code=next_code(db, "revenue_share", utcnow().year), project_id=p.id, version_no=n + 1,
                                farmer_share_pct=Decimal(data.farmer_share_pct), deduct_approved_costs=data.deduct_approved_costs,
                                rounding_mode=data.rounding_mode, effective_from=data.effective_from, effective_to=data.effective_to,
                                source_reference=data.source_reference, notes=data.notes, status="DRAFT", created_by=principal.user_id,
                                request_key=key, environment=p.environment)
        db.add(v)
        db.flush()
        ls.workflow(db, ctx, "revenue_share_version", v.id, None, "DRAFT", None)
        ls.audit(db, ctx, "REVENUE_SHARE_RULE_CREATED", "revenue_share_version", v.id, [p.organization_id],
                 {"version_code": v.version_code, "version_no": v.version_no, "farmer_share_pct": str(v.farmer_share_pct),
                  "deduct_approved_costs": v.deduct_approved_costs, "rounding_mode": v.rounding_mode, "source_reference": v.source_reference})
        return v
    return ls.run(db, ctx, op)


def config_action(db: Session, ctx: RequestContext, principal: Principal, model: Any, entity_id: uuid.UUID, action: str, reason: str | None,
                  key: str | None) -> Any:
    """submit (DRAFT → IN_REVIEW, author side) · approve (IN_REVIEW → APPROVED, never the author; the previous APPROVED version of the same
    scope becomes SUPERSEDED) · return (IN_REVIEW → DRAFT with a reason). Shared by revenue-share versions and farm allocation versions."""
    v = db.get(model, entity_id)
    if v is None:
        raise ms.nf("Configuration version", "CONFIG_VERSION_NOT_FOUND")
    p = project_for(db, principal, v.project_id, P.SHARING_APPROVE if action in ("approve", "return") else P.SHARING_MANAGE)
    writable(p)
    target = {"submit": "IN_REVIEW", "approve": "APPROVED", "return": "DRAFT"}[action]
    if ms.replay_action(v, key, target):
        return v
    if action in ("approve", "return") and v.created_by == principal.user_id:
        raise PermissionDenied("You authored this version, so someone else must review it.", error_code="SEPARATION_OF_DUTIES")
    if action == "return" and not (reason and reason.strip()):
        raise ValidationFailed("Give a reason.", error_code="REASON_REQUIRED")
    entity = "revenue_share_version" if model is RevenueShareVersion else "farm_allocation_version"

    def op() -> Any:
        x = ms.lock(db, model, v.id)
        if action == "submit" and model is FarmAllocationVersion:
            _validate_allocation(db, x)
        frm = ms.transition(db, ctx, SHARING_CONFIG_MACHINE, x, entity, target, reason)
        x.action_key = key
        if action == "submit":
            x.submitted_by, x.return_reason = principal.user_id, None
        elif action == "return":
            x.return_reason = reason
        else:
            x.approved_by, x.approved_at = principal.user_id, utcnow()
            scope = [model.project_id == x.project_id, model.status == "APPROVED", model.id != x.id]
            if model is FarmAllocationVersion:
                scope.append(model.monitoring_period_id == x.monitoring_period_id)
            for old in db.scalars(select(model).where(*scope)).all():
                ms.transition(db, ctx, SHARING_CONFIG_MACHINE, old, entity, "SUPERSEDED", f"superseded by {x.version_code}")
        prefix = "REVENUE_SHARE_RULE" if model is RevenueShareVersion else "ALLOCATION"
        event = {"submit": f"{prefix}_SUBMITTED", "approve": f"{prefix}_APPROVED", "return": f"{prefix}_RETURNED"}[action]
        ls.audit(db, ctx, event, entity, x.id, [p.organization_id], {"version_code": x.version_code, "status": target}, reason, {"status": frm})
        return x
    return ls.run(db, ctx, op)


# ---------------------------------------------------------------- farm allocation (D12 B — approved, versioned per-period table)
def allocations(db: Session, principal: Principal, project_id: uuid.UUID, period_id: uuid.UUID | None) -> list[FarmAllocationVersion]:
    p = project_for(db, principal, project_id)
    stmt = select(FarmAllocationVersion).where(FarmAllocationVersion.project_id == p.id)
    if period_id:
        stmt = stmt.where(FarmAllocationVersion.monitoring_period_id == period_id)
    return list(db.scalars(stmt.order_by(FarmAllocationVersion.monitoring_period_id, FarmAllocationVersion.version_no.desc())).all())


def allocation_lines(db: Session, version_id: uuid.UUID) -> list[FarmAllocationLine]:
    return list(db.scalars(select(FarmAllocationLine).where(FarmAllocationLine.allocation_version_id == version_id)
                           .order_by(FarmAllocationLine.project_farm_id)).all())


def create_allocation(db: Session, ctx: RequestContext, principal: Principal, data: Any, key: str | None) -> FarmAllocationVersion:
    if key and (prior := db.scalars(select(FarmAllocationVersion).where(FarmAllocationVersion.request_key == key)).first()) is not None:
        return prior
    p = project_for(db, principal, data.project_id, P.SHARING_MANAGE)
    writable(p)
    mp = period_of(db, p, data.monitoring_period_id)
    ids = [ln.project_farm_id for ln in data.lines]
    if len(set(ids)) != len(ids):
        raise ValidationFailed("A farm participation may appear once in an allocation.", error_code="DUPLICATE_FARM_ALLOCATION")
    pfs = {}
    for pfid in ids:
        pf = db.get(ProjectFarm, pfid)
        if pf is None or pf.project_id != p.id:
            raise ms.nf("Project farm", "PROJECT_FARM_NOT_FOUND")
        if pf.participation_start > mp.end_date or (pf.participation_end is not None and pf.participation_end < mp.start_date):
            raise ValidationFailed(f"Farm participation {pf.id} does not overlap the monitoring period.", error_code="FARM_NOT_IN_PERIOD")
        pfs[pfid] = pf

    def op() -> FarmAllocationVersion:
        ms.lock(db, Project, p.id)
        n = int(db.scalar(select(func.coalesce(func.max(FarmAllocationVersion.version_no), 0)).where(
            FarmAllocationVersion.project_id == p.id, FarmAllocationVersion.monitoring_period_id == mp.id)) or 0)
        v = FarmAllocationVersion(version_code=next_code(db, "allocation", utcnow().year), project_id=p.id, monitoring_period_id=mp.id,
                                  version_no=n + 1, basis_reference=data.basis_reference, status="DRAFT", created_by=principal.user_id,
                                  request_key=key, environment=p.environment)
        db.add(v)
        db.flush()
        for ln in data.lines:
            pf = pfs[ln.project_farm_id]
            db.add(FarmAllocationLine(allocation_version_id=v.id, project_farm_id=pf.id, farm_id=pf.farm_id, farmer_id=pf.farmer_id,
                                      share_pct=Decimal(ln.share_pct)))
        db.flush()
        ls.workflow(db, ctx, "farm_allocation_version", v.id, None, "DRAFT", None)
        ls.audit(db, ctx, "ALLOCATION_CREATED", "farm_allocation_version", v.id, [p.organization_id],
                 {"version_code": v.version_code, "period": mp.period_number, "lines": len(data.lines),
                  "total_pct": str(sum((Decimal(ln.share_pct) for ln in data.lines), Decimal(0)))})
        return v
    return ls.run(db, ctx, op)


def _validate_allocation(db: Session, v: FarmAllocationVersion) -> None:
    lines = allocation_lines(db, v.id)
    total = sum((ln.share_pct for ln in lines), Decimal(0))
    if not lines or total != Decimal(100):
        raise ValidationFailed(f"Farm allocation shares must total exactly 100 (they total {total}).", error_code="ALLOCATION_NOT_CONSERVED",
                               details={"total": str(total)})


# ---------------------------------------------------------------- project costs (controlled input; deducted only if the version says so)
def costs(db: Session, principal: Principal, project_id: uuid.UUID) -> list[ProjectCost]:
    p = project_for(db, principal, project_id, P.COSTS_MANAGE, P.COSTS_APPROVE, P.REVENUE_READ, P.SETTLEMENT_READ)
    return list(db.scalars(select(ProjectCost).where(ProjectCost.project_id == p.id).order_by(ProjectCost.created_at.desc())).all())


def create_cost(db: Session, ctx: RequestContext, principal: Principal, data: Any, key: str | None) -> ProjectCost:
    if key and (prior := db.scalars(select(ProjectCost).where(ProjectCost.request_key == key)).first()) is not None:
        return prior
    p = project_for(db, principal, data.project_id, P.COSTS_MANAGE)
    writable(p)
    if data.monitoring_period_id:
        period_of(db, p, data.monitoring_period_id)
    currency = data.currency.upper()
    amount = Decimal(str(data.amount))
    if amount == 0:
        raise ValidationFailed("A cost amount cannot be zero.", error_code="INVALID_AMOUNT")
    ms.money(abs(amount), currency, "amount")                      # ISO 4217 code with known minor units; no excess decimals
    if amount < 0:
        orig = db.get(ProjectCost, data.corrects_cost_id) if data.corrects_cost_id else None
        if orig is None or orig.project_id != p.id or orig.status != "APPROVED":
            raise ValidationFailed("A negative amount corrects an approved cost of the same project (corrects_cost_id).",
                                   error_code="CORRECTION_TARGET_REQUIRED")
    c = ProjectCost(cost_code=next_code(db, "cost", utcnow().year), project_id=p.id, monitoring_period_id=data.monitoring_period_id,
                    category=data.category, description=data.description, amount=amount, currency=currency, incurred_on=data.incurred_on,
                    external_reference=data.external_reference, corrects_cost_id=data.corrects_cost_id, status="PENDING_APPROVAL",
                    created_by=principal.user_id, request_key=key, environment=p.environment)
    db.add(c)
    db.flush()
    ls.workflow(db, ctx, COST_ENTITY, c.id, None, "PENDING_APPROVAL", None)
    ls.audit(db, ctx, "PROJECT_COST_CREATED", COST_ENTITY, c.id, [p.organization_id],
             {"cost_code": c.cost_code, "category": c.category, "amount": str(c.amount), "currency": c.currency})
    db.commit()
    return c


def cost_evidence(db: Session, ctx: RequestContext, principal: Principal, cost_id: uuid.UUID, filename: str | None, data: bytes,
                  title: str | None) -> Document:
    c = db.get(ProjectCost, cost_id)
    if c is None:
        raise ms.nf("Project cost", "PROJECT_COST_NOT_FOUND")
    p = project_for(db, principal, c.project_id, P.COSTS_MANAGE)
    if c.status != "PENDING_APPROVAL":
        raise Conflict("Evidence is attached before the cost is decided.", error_code="COST_LOCKED")
    doc = document_service.create_document(db, ctx, entity_type=COST_ENTITY, entity_id=c.id, organization_id=p.organization_id,
                                           environment=c.environment, category=DocumentCategory.COST_EVIDENCE.value,
                                           title=title or "Cost evidence", filename=filename, data=data)
    db.commit()
    return doc


def decide_cost(db: Session, ctx: RequestContext, principal: Principal, cost_id: uuid.UUID, approve: bool, reason: str | None,
                key: str | None) -> ProjectCost:
    c = db.get(ProjectCost, cost_id)
    if c is None:
        raise ms.nf("Project cost", "PROJECT_COST_NOT_FOUND")
    p = project_for(db, principal, c.project_id, P.COSTS_APPROVE)
    target = "APPROVED" if approve else "REJECTED"
    if ms.replay_action(c, key, target):
        return c
    if c.created_by == principal.user_id:
        raise PermissionDenied("You recorded this cost, so someone else must decide on it.", error_code="SEPARATION_OF_DUTIES")
    if approve and not any(d.category == DocumentCategory.COST_EVIDENCE.value for d in document_service.list_for(db, COST_ENTITY, c.id)):
        raise ValidationFailed("A cost is approved only with its evidence (PDF).", error_code="COST_EVIDENCE_REQUIRED")
    if not approve and not (reason and reason.strip()):
        raise ValidationFailed("Give a reason.", error_code="REASON_REQUIRED")

    def op() -> ProjectCost:
        x = ms.lock(db, ProjectCost, c.id)
        frm = ms.transition(db, ctx, PROJECT_COST_MACHINE, x, COST_ENTITY, target, reason)
        x.action_key = key
        if approve:
            x.approved_by, x.approved_at = principal.user_id, utcnow()
        else:
            x.approved_by, x.reject_reason = principal.user_id, reason
        ls.audit(db, ctx, "PROJECT_COST_APPROVED" if approve else "PROJECT_COST_REJECTED", COST_ENTITY, x.id, [p.organization_id],
                 {"cost_code": x.cost_code, "status": target}, reason, {"status": frm})
        return x
    return ls.run(db, ctx, op)


def _cost_resolver(db: Session, principal: Principal, entity_id: uuid.UUID, kind: str) -> None:
    c = db.get(ProjectCost, entity_id)
    if kind == "manage":
        raise PermissionDenied("Cost evidence is immutable.", error_code="DOCUMENT_IMMUTABLE")
    p = db.get(Project, c.project_id) if c else None
    if p is None or not any(principal.can_in_org(code, p.organization_id) for code in (P.COSTS_MANAGE, P.COSTS_APPROVE, P.SETTLEMENT_APPROVE)):
        raise NotFound("Document not found.", error_code="DOCUMENT_NOT_FOUND")


document_service.register_resolver(COST_ENTITY, _cost_resolver)


def money_sum(values: Iterable[Decimal]) -> Decimal:
    return sum(values, Decimal(0))
