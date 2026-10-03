"""Phase 11 — settlement runs: a frozen, reproducible calculation of farmer entitlements for one project / monitoring period / currency.

Inputs (all immutable when used): the recognized and reversed revenue not yet in an active run, the approved costs not yet in an active
run (only when the revenue-share version deducts costs), one APPROVED revenue-share version covering the period, one APPROVED farm
allocation version of the period. Model (`calculate_figures`, fin-calc-1):

    gross          = Σ included revenue records (recognitions > 0, reversals < 0)
    deducted_costs = Σ included approved costs            (0 when the version does not deduct costs)
    distributable  = gross − deducted_costs               (must be ≥ 0, otherwise nothing is settled)
    line amount    = quantize(distributable × farmer_share_pct / 100 × line share_pct / 100, currency minor unit, version rounding_mode)
    farmer_total   = Σ line amounts                       (must not exceed distributable)
    developer_residual = distributable − farmer_total

Every input and result is written to a canonical JSON snapshot whose SHA-256 is stored; `verify` recomputes the results from the snapshot.
A reversal whose recognition was already paid out (payout PAYMENT_PENDING / UNCONFIRMED / PAID / RECONCILED) is not netted: it opens a
recovery case (PayoutAdjustment) — never an automatic clawback. Changed inputs mean a new run; a rejected / cancelled run frees its inputs.
"""
import hashlib
import json
import uuid
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import select, true
from sqlalchemy.orm import Session

from app.core.context import RequestContext
from app.core.errors import Conflict, PermissionDenied, ValidationFailed
from app.integrations.payment import CURRENCY_EXPONENTS
from app.models import (
    FarmAllocationVersion,
    FarmerEntitlement,
    MonitoringPeriod,
    Payout,
    PayoutAdjustment,
    Project,
    ProjectCost,
    RevenueRecord,
    RevenueShareVersion,
    SettlementCostItem,
    SettlementRevenueItem,
    SettlementRun,
)
from app.models.base import utcnow
from app.repositories.sequences import next_code
from app.security.permissions import P
from app.security.principal import Principal
from app.services import finance_service as fs
from app.services import ledger_service as ls
from app.services import marketplace_service as ms
from app.services.workflows import SETTLEMENT_MACHINE

ENTITY = "settlement_run"
CALCULATION_VERSION = "fin-calc-1"
ROUNDING = {"HALF_UP": ROUND_HALF_UP, "HALF_EVEN": ROUND_HALF_EVEN, "DOWN": ROUND_DOWN}
EXECUTED = ("PAYMENT_PENDING", "UNCONFIRMED", "PAID", "RECONCILED")      # money has (possibly) left: no netting, a recovery case instead


# ---------------------------------------------------------------- pure calculation (deterministic, Decimal only)
def _d(v: Any) -> Decimal:
    return Decimal(str(v))


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def calculate_figures(inputs: dict[str, Any]) -> dict[str, Any]:
    """The fin-calc-1 model on a snapshot's `inputs`. Money and percentages travel as strings and are computed as Decimal."""
    rule = inputs["revenue_share_version"]
    unit = Decimal(1).scaleb(-CURRENCY_EXPONENTS[inputs["currency"]])
    mode = ROUNDING[rule["rounding_mode"]]
    gross = sum((_d(r["amount"]) for r in inputs["revenue"]), Decimal(0))
    costs = sum((_d(c["amount"]) for c in inputs["costs"]), Decimal(0)) if rule["deduct_approved_costs"] else Decimal(0)
    distributable = gross - costs
    pool_pct = _d(rule["farmer_share_pct"])
    lines = []
    for ln in sorted(inputs["allocation"]["lines"], key=lambda x: x["allocation_line_id"]):
        raw = distributable * pool_pct / Decimal(100) * _d(ln["share_pct"]) / Decimal(100)
        lines.append({"allocation_line_id": ln["allocation_line_id"], "farmer_id": ln["farmer_id"],
                      "amount": str(raw.quantize(unit, rounding=mode))})
    farmer_total = sum((_d(x["amount"]) for x in lines), Decimal(0))

    def q(v: Decimal) -> str:
        return str(v.quantize(unit))
    return {"gross_revenue": q(gross), "deducted_costs": q(costs), "distributable": q(distributable), "farmer_total": q(farmer_total),
            "developer_residual": q(distributable - farmer_total), "entitlements": lines}


# ---------------------------------------------------------------- reads
def run_for(db: Session, principal: Principal, run_id: uuid.UUID, *codes: str) -> tuple[SettlementRun, Project]:
    r = db.get(SettlementRun, run_id)
    if r is None:
        raise ms.nf("Settlement run", "SETTLEMENT_NOT_FOUND")
    p = fs.project_for(db, principal, r.project_id, *(codes or (P.SETTLEMENT_READ, P.SETTLEMENT_CALCULATE, P.SETTLEMENT_APPROVE,
                                                                 P.PAYOUTS_READ, P.REVENUE_READ)))
    return r, p


def runs(db: Session, principal: Principal, project_id: uuid.UUID | None = None, status: str | None = None) -> list[SettlementRun]:
    ids = [p.id for p in fs.visible_projects(db, principal)
           if any(principal.can_in_org(c, p.organization_id) for c in (P.SETTLEMENT_READ, P.SETTLEMENT_CALCULATE, P.SETTLEMENT_APPROVE))]
    if project_id is not None:
        ids = [i for i in ids if i == project_id]
    if not ids:
        return []
    stmt = select(SettlementRun).where(SettlementRun.project_id.in_(ids))
    if status:
        stmt = stmt.where(SettlementRun.status == status)
    return list(db.scalars(stmt.order_by(SettlementRun.created_at.desc())).all())


def entitlements(db: Session, run_id: uuid.UUID) -> list[FarmerEntitlement]:
    return list(db.scalars(select(FarmerEntitlement).where(FarmerEntitlement.settlement_run_id == run_id)
                           .order_by(FarmerEntitlement.farmer_id, FarmerEntitlement.allocation_line_id)).all())


def revenue_items(db: Session, run_id: uuid.UUID) -> list[tuple[SettlementRevenueItem, RevenueRecord]]:
    return [(i, r) for i, r in db.execute(select(SettlementRevenueItem, RevenueRecord).join(
        RevenueRecord, RevenueRecord.id == SettlementRevenueItem.revenue_record_id).where(
        SettlementRevenueItem.settlement_run_id == run_id).order_by(RevenueRecord.revenue_code)).tuples().all()]


def cost_items(db: Session, run_id: uuid.UUID) -> list[tuple[SettlementCostItem, ProjectCost]]:
    return [(i, c) for i, c in db.execute(select(SettlementCostItem, ProjectCost).join(
        ProjectCost, ProjectCost.id == SettlementCostItem.project_cost_id).where(
        SettlementCostItem.settlement_run_id == run_id).order_by(ProjectCost.cost_code)).tuples().all()]


# ---------------------------------------------------------------- create (DRAFT)
def create(db: Session, ctx: RequestContext, principal: Principal, data: Any, key: str | None) -> SettlementRun:
    if key and (prior := db.scalars(select(SettlementRun).where(SettlementRun.request_key == key)).first()) is not None:
        return prior
    p = fs.project_for(db, principal, data.project_id, P.SETTLEMENT_CALCULATE)
    fs.writable(p)
    mp = fs.period_of(db, p, data.monitoring_period_id)
    currency = data.currency.upper()
    if currency not in CURRENCY_EXPONENTS:
        raise ValidationFailed(f"Currency {currency!r} is not supported.", error_code="UNSUPPORTED_CURRENCY")
    rv = _approved_share(db, p, mp, data.revenue_share_version_id)
    av = _approved_allocation(db, p, mp, data.allocation_version_id)

    def op() -> SettlementRun:
        ms.lock(db, Project, p.id)
        r = SettlementRun(run_code=next_code(db, "settlement", utcnow().year), project_id=p.id, organization_id=p.organization_id,
                          monitoring_period_id=mp.id, currency=currency, revenue_share_version_id=rv.id, allocation_version_id=av.id,
                          status="DRAFT", created_by=principal.user_id, request_key=key, environment=p.environment)
        db.add(r)
        db.flush()
        ls.workflow(db, ctx, ENTITY, r.id, None, "DRAFT", None)
        ls.audit(db, ctx, "SETTLEMENT_CREATED", ENTITY, r.id, [p.organization_id],
                 {"run_code": r.run_code, "period": mp.period_number, "currency": currency, "revenue_share_version": rv.version_code,
                  "allocation_version": av.version_code})
        return r
    return ls.run(db, ctx, op)


def _approved_share(db: Session, p: Project, mp: MonitoringPeriod, version_id: uuid.UUID) -> RevenueShareVersion:
    v = db.get(RevenueShareVersion, version_id)
    if v is None or v.project_id != p.id:
        raise ms.nf("Revenue-share version", "CONFIG_VERSION_NOT_FOUND")
    if v.status != "APPROVED":
        raise Conflict(f"Revenue-share version {v.version_code} is {v.status}; only an APPROVED version is used for settlement.",
                       error_code="SHARING_RULE_NOT_APPROVED")
    if v.effective_from > mp.start_date or (v.effective_to is not None and v.effective_to < mp.end_date):
        raise Conflict(f"Revenue-share version {v.version_code} does not cover the whole monitoring period.",
                       error_code="SHARING_RULE_NOT_EFFECTIVE")
    return v


def _approved_allocation(db: Session, p: Project, mp: MonitoringPeriod, version_id: uuid.UUID) -> FarmAllocationVersion:
    v = db.get(FarmAllocationVersion, version_id)
    if v is None or v.project_id != p.id or v.monitoring_period_id != mp.id:
        raise ms.nf("Farm allocation", "CONFIG_VERSION_NOT_FOUND")
    if v.status != "APPROVED":
        raise Conflict(f"Farm allocation {v.version_code} is {v.status}; settlement uses only an APPROVED allocation.",
                       error_code="ALLOCATION_NOT_APPROVED")
    return v


# ---------------------------------------------------------------- calculate (DRAFT → CALCULATED)
def _executed_run_of(db: Session, recognition_id: uuid.UUID) -> uuid.UUID | None:
    """The active run that settled this recognition, if one of its payouts has (possibly) left the bank."""
    run_id = db.scalar(select(SettlementRevenueItem.settlement_run_id).where(SettlementRevenueItem.revenue_record_id == recognition_id,
                                                                             SettlementRevenueItem.active == true()))
    if run_id is None:
        return None
    hit = db.scalars(select(Payout.id).where(Payout.settlement_run_id == run_id, Payout.status.in_(EXECUTED))).first()
    return run_id if hit else None


def calculate(db: Session, ctx: RequestContext, principal: Principal, run_id: uuid.UUID, key: str | None) -> SettlementRun:
    r, p = run_for(db, principal, run_id, P.SETTLEMENT_CALCULATE)
    fs.writable(p)
    if ms.replay_action(r, key, "CALCULATED"):
        return r

    def op() -> SettlementRun:
        ms.lock(db, Project, p.id)                                  # one calculation per project at a time (inputs are claimed below)
        x = ms.lock(db, SettlementRun, r.id)
        SETTLEMENT_MACHINE.assert_transition(x.status, "CALCULATED")
        rv = db.get(RevenueShareVersion, x.revenue_share_version_id)
        av = db.get(FarmAllocationVersion, x.allocation_version_id)
        mp = db.get(MonitoringPeriod, x.monitoring_period_id)
        assert rv is not None and av is not None and mp is not None
        if rv.status != "APPROVED" or av.status != "APPROVED":
            raise Conflict("The run's revenue-share version or farm allocation is no longer APPROVED (superseded): create a new run.",
                           error_code="CONFIGURATION_SUPERSEDED")
        claimed = select(SettlementRevenueItem.revenue_record_id).where(SettlementRevenueItem.active == true())
        candidates = db.scalars(select(RevenueRecord).where(
            RevenueRecord.project_id == p.id, RevenueRecord.monitoring_period_id == mp.id, RevenueRecord.currency == x.currency,
            RevenueRecord.environment == x.environment,
            RevenueRecord.seller_organization_id == p.organization_id,     # D16 / D38: only revenue the project organization received
            RevenueRecord.id.not_in(claimed)).order_by(RevenueRecord.revenue_code)).all()
        revenue: list[RevenueRecord] = []
        recovery: list[tuple[RevenueRecord, uuid.UUID]] = []
        for rec in candidates:
            if rec.kind == "REVERSAL":
                assert rec.reverses_revenue_id is not None
                if db.scalars(select(PayoutAdjustment.id).where(PayoutAdjustment.reversal_revenue_id == rec.id)).first():
                    continue                                        # already a recovery case
                paid_run = _executed_run_of(db, rec.reverses_revenue_id)
                if paid_run is not None:
                    recovery.append((rec, paid_run))
                    continue
            revenue.append(rec)
        costs: list[ProjectCost] = []
        if rv.deduct_approved_costs:
            used = select(SettlementCostItem.project_cost_id).where(SettlementCostItem.active == true())
            costs = list(db.scalars(select(ProjectCost).where(
                ProjectCost.project_id == p.id, ProjectCost.status == "APPROVED", ProjectCost.currency == x.currency,
                ProjectCost.environment == x.environment,
                (ProjectCost.monitoring_period_id == mp.id) | ProjectCost.monitoring_period_id.is_(None),
                ProjectCost.id.not_in(used)).order_by(ProjectCost.cost_code)).all())
        for rec, paid_run in recovery:                              # recovery cases stand even if this run is later refused
            _open_recovery(db, ctx, p, rec, paid_run)
        if not revenue:
            db.commit()
            raise Conflict("There is no unsettled revenue for this project, period and currency.", error_code="NOTHING_TO_SETTLE",
                           details={"recovery_cases_opened": len(recovery)})
        lines = fs.allocation_lines(db, av.id)
        inputs = {
            "calculation_version": CALCULATION_VERSION, "run_code": x.run_code, "project_id": str(p.id), "monitoring_period_id": str(mp.id),
            "currency": x.currency,
            "revenue_share_version": {"id": str(rv.id), "version_code": rv.version_code, "farmer_share_pct": str(rv.farmer_share_pct),
                                      "deduct_approved_costs": rv.deduct_approved_costs, "rounding_mode": rv.rounding_mode},
            "allocation": {"id": str(av.id), "version_code": av.version_code,
                           "lines": [{"allocation_line_id": str(ln.id), "project_farm_id": str(ln.project_farm_id), "farm_id": str(ln.farm_id),
                                      "farmer_id": str(ln.farmer_id), "share_pct": str(ln.share_pct)} for ln in lines]},
            "revenue": [{"id": str(rec.id), "revenue_code": rec.revenue_code, "kind": rec.kind, "amount": str(rec.amount),
                         "order_item_id": str(rec.order_item_id)} for rec in revenue],
            "costs": [{"id": str(c.id), "cost_code": c.cost_code, "category": c.category, "amount": str(c.amount)} for c in costs],
        }
        res = calculate_figures(inputs)
        if Decimal(res["distributable"]) < 0:
            raise Conflict("Costs and reversals exceed the revenue of this run: nothing can be distributed (no negative entitlements, no "
                           "automatic clawback).", error_code="NEGATIVE_DISTRIBUTABLE", details={k: res[k] for k in ("gross_revenue",
                                                                                                                     "deducted_costs")})
        if Decimal(res["developer_residual"]) < 0:
            raise Conflict("With this rounding mode the rounded entitlements exceed the distributable amount; approve a version with a "
                           "different rounding mode.", error_code="ROUNDING_EXCEEDS_DISTRIBUTABLE")
        snapshot = canonical({"inputs": inputs, "results": res})
        x.input_snapshot, x.input_sha256 = snapshot, hashlib.sha256(snapshot.encode("utf-8")).hexdigest()
        x.calculation_version = CALCULATION_VERSION
        x.gross_revenue, x.deducted_costs, x.distributable = _d(res["gross_revenue"]), _d(res["deducted_costs"]), _d(res["distributable"])
        x.farmer_total, x.developer_residual = _d(res["farmer_total"]), _d(res["developer_residual"])
        x.calculated_by, x.calculated_at, x.action_key = principal.user_id, utcnow(), key
        for rec in revenue:
            db.add(SettlementRevenueItem(settlement_run_id=x.id, revenue_record_id=rec.id, amount=rec.amount))
        for c in costs:
            db.add(SettlementCostItem(settlement_run_id=x.id, project_cost_id=c.id, amount=c.amount))
        by_line = {ln.id: ln for ln in lines}
        for e in res["entitlements"]:
            ln = by_line[uuid.UUID(e["allocation_line_id"])]
            db.add(FarmerEntitlement(settlement_run_id=x.id, allocation_line_id=ln.id, project_farm_id=ln.project_farm_id, farm_id=ln.farm_id,
                                     farmer_id=ln.farmer_id, share_pct=ln.share_pct, amount=_d(e["amount"]), currency=x.currency))
        db.flush()                                                  # the filtered unique indexes reject a concurrently claimed input
        frm = ms.transition(db, ctx, SETTLEMENT_MACHINE, x, ENTITY, "CALCULATED")
        ls.audit(db, ctx, "SETTLEMENT_CALCULATED", ENTITY, x.id, [p.organization_id],
                 {"run_code": x.run_code, "calculation_version": CALCULATION_VERSION, "input_sha256": x.input_sha256,
                  "revenue_records": len(revenue), "costs": len(costs), "gross_revenue": res["gross_revenue"],
                  "deducted_costs": res["deducted_costs"], "distributable": res["distributable"], "farmer_total": res["farmer_total"],
                  "developer_residual": res["developer_residual"], "recovery_cases_opened": len(recovery)}, None, {"status": frm})
        return x
    return ls.run(db, ctx, op)


def _open_recovery(db: Session, ctx: RequestContext, p: Project, rec: RevenueRecord, paid_run: uuid.UUID) -> None:
    if db.scalars(select(PayoutAdjustment.id).where(PayoutAdjustment.reversal_revenue_id == rec.id)).first():
        return
    a = PayoutAdjustment(adjustment_code=next_code(db, "adjustment", utcnow().year), project_id=p.id, organization_id=p.organization_id,
                         reversal_revenue_id=rec.id, original_settlement_run_id=paid_run, amount=rec.amount, currency=rec.currency,
                         status="OPEN", environment=rec.environment)
    db.add(a)
    db.flush()
    ls.workflow(db, ctx, "payout_adjustment", a.id, None, "OPEN", None)
    ls.audit(db, ctx, "PAYOUT_RECOVERY_CASE_OPENED", "payout_adjustment", a.id, [p.organization_id],
             {"adjustment_code": a.adjustment_code, "reversal": rec.revenue_code, "amount": str(a.amount), "currency": a.currency,
              "original_settlement_run_id": paid_run})


# ---------------------------------------------------------------- verify (recompute from the frozen snapshot)
def verify(db: Session, principal: Principal, run_id: uuid.UUID) -> dict[str, Any]:
    r, _ = run_for(db, principal, run_id)
    if not r.input_snapshot:
        raise Conflict("The run has not been calculated.", error_code="SETTLEMENT_NOT_CALCULATED")
    snap = json.loads(r.input_snapshot)
    recomputed = calculate_figures(snap["inputs"])
    stored = {"gross_revenue": r.gross_revenue, "deducted_costs": r.deducted_costs, "distributable": r.distributable,
              "farmer_total": r.farmer_total, "developer_residual": r.developer_residual}
    rows = {str(e.allocation_line_id): e.amount for e in entitlements(db, r.id)}
    lines_ok = len(rows) == len(recomputed["entitlements"]) and all(
        rows.get(e["allocation_line_id"]) == _d(e["amount"]) for e in recomputed["entitlements"])
    hash_ok = hashlib.sha256(r.input_snapshot.encode("utf-8")).hexdigest() == r.input_sha256
    figures_ok = all(_d(recomputed[k]) == v for k, v in stored.items()) and recomputed == snap["results"]
    links = {str(rec.id) for i, rec in revenue_items(db, r.id)}
    inputs_ok = links == {x["id"] for x in snap["inputs"]["revenue"]}
    return {"run_code": r.run_code, "calculation_version": r.calculation_version, "input_sha256": r.input_sha256, "hash_ok": hash_ok,
            "figures_ok": figures_ok, "entitlements_ok": lines_ok, "inputs_ok": inputs_ok,
            "reproducible": hash_ok and figures_ok and lines_ok and inputs_ok}


# ---------------------------------------------------------------- submit / approve / reject / cancel
def action(db: Session, ctx: RequestContext, principal: Principal, run_id: uuid.UUID, act: str, reason: str | None, key: str | None
           ) -> SettlementRun:
    code = P.SETTLEMENT_APPROVE if act in ("approve", "reject") else P.SETTLEMENT_CALCULATE
    r, p = run_for(db, principal, run_id, code)
    target = {"submit": "PENDING_APPROVAL", "approve": "APPROVED", "reject": "REJECTED", "cancel": "CANCELLED"}[act]
    if ms.replay_action(r, key, target):
        return r
    fs.writable(p)
    if act in ("approve", "reject") and principal.user_id == r.calculated_by:
        raise PermissionDenied("You calculated this run, so someone else must decide on it.", error_code="SEPARATION_OF_DUTIES")
    if act in ("reject", "cancel") and not (reason and reason.strip()):
        raise ValidationFailed("Give a reason.", error_code="REASON_REQUIRED")
    if act == "approve" and not verify(db, principal, r.id)["reproducible"]:
        raise Conflict("The run no longer reproduces from its frozen inputs.", error_code="SETTLEMENT_NOT_REPRODUCIBLE")

    def op() -> SettlementRun:
        x = ms.lock(db, SettlementRun, r.id)
        frm = ms.transition(db, ctx, SETTLEMENT_MACHINE, x, ENTITY, target, reason)
        x.action_key = key
        if act == "approve":
            x.approved_by, x.approved_at = principal.user_id, utcnow()
        if act in ("reject", "cancel"):
            x.close_reason = reason
            for ri in db.scalars(select(SettlementRevenueItem).where(SettlementRevenueItem.settlement_run_id == x.id,
                                                                     SettlementRevenueItem.active == true())).all():
                ri.active = False                                   # the inputs become available to a new run
            for ci in db.scalars(select(SettlementCostItem).where(SettlementCostItem.settlement_run_id == x.id,
                                                                  SettlementCostItem.active == true())).all():
                ci.active = False
        event = {"submit": "SETTLEMENT_SUBMITTED", "approve": "SETTLEMENT_APPROVED", "reject": "SETTLEMENT_REJECTED",
                 "cancel": "SETTLEMENT_CANCELLED"}[act]
        ls.audit(db, ctx, event, ENTITY, x.id, [p.organization_id], {"run_code": x.run_code, "status": target,
                                                                    "input_sha256": x.input_sha256}, reason, {"status": frm})
        return x
    return ls.run(db, ctx, op)


def complete_if_done(db: Session, ctx: RequestContext, run: SettlementRun) -> bool:
    """APPROVED → COMPLETED once every live payout of the run is RECONCILED (caller holds the run lock)."""
    if run.status != "APPROVED":
        return False
    db.flush()                                                      # sessions do not autoflush: the caller's payout change must be visible
    live = db.scalars(select(Payout.status).where(Payout.settlement_run_id == run.id,
                                                   Payout.status.not_in(("REJECTED", "CANCELLED", "FAILED")))).all()
    owed = {e.farmer_id for e in entitlements(db, run.id) if e.amount > 0}
    paid_to = set(db.scalars(select(Payout.farmer_id).where(Payout.settlement_run_id == run.id, Payout.status == "RECONCILED")).all())
    if any(s != "RECONCILED" for s in live) or not owed <= paid_to:
        return False
    frm = ms.transition(db, ctx, SETTLEMENT_MACHINE, run, ENTITY, "COMPLETED")
    ls.audit(db, ctx, "SETTLEMENT_COMPLETED", ENTITY, run.id, [run.organization_id], {"run_code": run.run_code, "status": "COMPLETED"},
             None, {"status": frm})
    return True


def adjustments(db: Session, principal: Principal, project_id: uuid.UUID | None = None) -> list[PayoutAdjustment]:
    ids = [p.id for p in fs.visible_projects(db, principal)
           if any(principal.can_in_org(c, p.organization_id) for c in (P.PAYOUTS_READ, P.PAYOUTS_RECONCILE, P.SETTLEMENT_READ))]
    if project_id is not None:
        ids = [i for i in ids if i == project_id]
    if not ids:
        return []
    return list(db.scalars(select(PayoutAdjustment).where(PayoutAdjustment.project_id.in_(ids)).order_by(PayoutAdjustment.created_at.desc())))

