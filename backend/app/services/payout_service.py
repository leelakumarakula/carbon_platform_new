"""Phase 11 — payouts, execution, reconciliation, recovery cases, lineage, financial summary, farmer self-service.

A payout is what one farmer is owed by one APPROVED settlement run: the sum of that farmer's entitlement lines (never a client-typed
amount). Lifecycle (D20): CALCULATED → PENDING_APPROVAL → APPROVED → PAYMENT_PENDING → PAID → RECONCILED, with REJECTED / CANCELLED /
FAILED / UNCONFIRMED / ON_HOLD. Calculator ≠ approver ≠ executor; executor ≠ reconciler. The beneficiary is the farmer's primary VERIFIED
Phase 2 bank account — referenced, never copied (last 4 only), re-checked under lock at execution (a change puts the payout ON_HOLD).

MANUAL adapter (the only runtime adapter): finance pays at the bank, then records the bank reference and a PAYOUT_EVIDENCE PDF (PAID).
PAID is not RECONCILED: a different person matches it against a statement (MATCHED → RECONCILED, otherwise EXCEPTION). A reversal of
already-paid revenue is a recovery case closed manually with a resolution — no automatic clawback.
"""
import uuid
from collections import defaultdict
from decimal import Decimal
from typing import Any

from sqlalchemy import select, true
from sqlalchemy.orm import Session

from app.core.context import RequestContext
from app.core.errors import Conflict, NotFound, PermissionDenied, ValidationFailed
from app.integrations.payout import ADAPTERS, ManualPayoutAdapter, PayoutAdapter, PayoutRequest, PayoutTimeout, PayoutUnavailable
from app.models import (
    CreditTransfer,
    Document,
    FarmAllocationVersion,
    Farmer,
    FarmerBankAccount,
    MonitoringPeriod,
    Order,
    OrderItem,
    Payment,
    Payout,
    PayoutAdjustment,
    PayoutReconciliation,
    PayoutTransaction,
    Project,
    ProjectCost,
    RevenueRecord,
    RevenueShareVersion,
    SettlementRun,
)
from app.models.base import utcnow
from app.models.documents import DocumentCategory
from app.repositories.sequences import next_code
from app.security.permissions import P
from app.security.principal import Principal
from app.services import document_service
from app.services import finance_service as fs
from app.services import ledger_service as ls
from app.services import marketplace_service as ms
from app.services import settlement_service as ss
from app.services.workflows import PAYOUT_ADJUSTMENT_MACHINE, PAYOUT_MACHINE

ENTITY = "payout"
PAYOUT_VIEW = (P.PAYOUTS_READ, P.PAYOUTS_CALCULATE, P.PAYOUTS_APPROVE, P.PAYOUTS_EXECUTE, P.PAYOUTS_RECONCILE)
LIVE = ("REJECTED", "CANCELLED", "FAILED")                     # statuses that free the (run, farmer) slot


def adapter_for(code: str, override: PayoutAdapter | None = None) -> PayoutAdapter:
    """The runtime adapter (MANUAL only). Tests inject their adapter explicitly via `override`; it is never registered."""
    if override is not None:
        return override
    a = ADAPTERS.get(code)
    if a is None:
        raise Conflict(f"No payout adapter {code!r} is available.", error_code="UNKNOWN_PAYOUT_ADAPTER")
    return a


def _move(db: Session, ctx: RequestContext, p: Payout, to: str, reason: str | None = None) -> str:
    return ms.transition(db, ctx, PAYOUT_MACHINE, p, ENTITY, to, reason)


def _tx(db: Session, p: Payout, kind: str, actor: uuid.UUID | None, *, note: str | None = None, evidence: uuid.UUID | None = None) -> None:
    db.add(PayoutTransaction(payout_id=p.id, kind=kind, adapter_code=p.adapter_code, external_reference=p.external_reference, amount=p.amount,
                             currency=p.currency, evidence_document_id=evidence, note=note, actor_id=actor))


def _audit(db: Session, ctx: RequestContext, event: str, p: Payout, payload: dict[str, Any], reason: str | None = None,
           old: dict[str, Any] | None = None) -> None:
    """Never bank credentials: only the bank account record id is referenced."""
    ls.audit(db, ctx, event, ENTITY, p.id, [p.organization_id],
             {"payout_code": p.payout_code, "amount": str(p.amount), "currency": p.currency, **payload}, reason, old)


# ---------------------------------------------------------------- reads
def payout_for(db: Session, principal: Principal, payout_id: uuid.UUID, *codes: str) -> Payout:
    p = db.get(Payout, payout_id)
    if p is None:
        raise ms.nf("Payout", "PAYOUT_NOT_FOUND")
    ms.require(principal, p.organization_id, *(codes or PAYOUT_VIEW), visible=PAYOUT_VIEW, what="Payout", nf_code="PAYOUT_NOT_FOUND")
    return p


def payouts(db: Session, principal: Principal, *, run_id: uuid.UUID | None = None, status: str | None = None) -> list[Payout]:
    orgs = {p.organization_id for p in fs.visible_projects(db, principal) if any(principal.can_in_org(c, p.organization_id) for c in PAYOUT_VIEW)}
    if not orgs:
        return []
    stmt = select(Payout).where(Payout.organization_id.in_(orgs))
    if run_id:
        stmt = stmt.where(Payout.settlement_run_id == run_id)
    if status:
        stmt = stmt.where(Payout.status == status)
    return list(db.scalars(stmt.order_by(Payout.calculated_at.desc(), Payout.payout_code.desc())).all())


def transactions(db: Session, payout_id: uuid.UUID) -> list[PayoutTransaction]:
    return list(db.scalars(select(PayoutTransaction).where(PayoutTransaction.payout_id == payout_id).order_by(PayoutTransaction.created_at)))


def reconciliations(db: Session, payout_id: uuid.UUID) -> list[PayoutReconciliation]:
    return list(db.scalars(select(PayoutReconciliation).where(PayoutReconciliation.payout_id == payout_id)
                           .order_by(PayoutReconciliation.created_at)))


def my_farmers(db: Session, principal: Principal) -> list[Farmer]:
    if not principal.has(P.FARMERS_SELF):
        return []
    return list(db.scalars(select(Farmer).where(Farmer.user_id == principal.user_id)).all())


def my_payouts(db: Session, principal: Principal) -> list[Payout]:
    ids = [f.id for f in my_farmers(db, principal)]
    if not ids:
        return []
    return list(db.scalars(select(Payout).where(Payout.farmer_id.in_(ids)).order_by(Payout.calculated_at.desc())).all())


def _owed(db: Session, run_id: uuid.UUID) -> dict[uuid.UUID, Decimal]:
    owed: dict[uuid.UUID, Decimal] = defaultdict(Decimal)
    for e in ss.entitlements(db, run_id):
        owed[e.farmer_id] += e.amount
    return owed


# ---------------------------------------------------------------- calculate (from an APPROVED run — the amount is never an input)
def create_for_run(db: Session, ctx: RequestContext, principal: Principal, run_id: uuid.UUID) -> list[Payout]:
    r, p = ss.run_for(db, principal, run_id, P.PAYOUTS_CALCULATE)
    fs.writable(p)
    if r.status not in ("APPROVED", "COMPLETED"):
        raise Conflict(f"Payouts are calculated only from an APPROVED settlement run (run {r.run_code} is {r.status}).",
                       error_code="SETTLEMENT_NOT_APPROVED")

    def op() -> list[Payout]:
        x = ms.lock(db, SettlementRun, r.id)
        taken = set(db.scalars(select(Payout.farmer_id).where(Payout.settlement_run_id == x.id, Payout.status.not_in(LIVE))).all())
        created = []
        for farmer_id, amount in sorted(_owed(db, x.id).items(), key=lambda kv: str(kv[0])):
            if amount <= 0 or farmer_id in taken:
                continue
            created.append(_new_payout(db, ctx, principal, x, farmer_id, amount, None))
        if not created and not taken:
            ss.complete_if_done(db, ctx, x)                         # nothing is owed by this run
        return created
    return ls.run(db, ctx, op)


def _new_payout(db: Session, ctx: RequestContext, principal: Principal, run: SettlementRun, farmer_id: uuid.UUID, amount: Decimal,
                replaces: Payout | None, key: str | None = None) -> Payout:
    po = Payout(payout_code=next_code(db, "payout", utcnow().year), settlement_run_id=run.id, organization_id=run.organization_id,
                farmer_id=farmer_id, amount=amount, currency=run.currency, status="CALCULATED", adapter_code="MANUAL",
                replaces_payout_id=replaces.id if replaces else None, calculated_by=principal.user_id, request_key=key,
                environment=run.environment)
    db.add(po)
    db.flush()
    ls.workflow(db, ctx, ENTITY, po.id, None, "CALCULATED", None)
    _audit(db, ctx, "PAYOUT_CALCULATED", po, {"run_code": run.run_code, "farmer_id": farmer_id,
                                              "replaces": replaces.payout_code if replaces else None})
    return po


def reissue(db: Session, ctx: RequestContext, principal: Principal, payout_id: uuid.UUID, key: str | None) -> Payout:
    """A FAILED payout is replaced by a new CALCULATED payout of the same entitlement (the failed record is never edited)."""
    if key and (prior := db.scalars(select(Payout).where(Payout.request_key == key)).first()) is not None:
        return prior
    po = payout_for(db, principal, payout_id, P.PAYOUTS_CALCULATE)
    run = db.get(SettlementRun, po.settlement_run_id)
    project = db.get(Project, run.project_id) if run else None
    assert run is not None and project is not None
    fs.writable(project)
    if po.status != "FAILED":
        raise Conflict("Only a FAILED payout is reissued.", error_code="PAYOUT_NOT_FAILED")

    def op() -> Payout:
        x = ms.lock(db, SettlementRun, run.id)
        return _new_payout(db, ctx, principal, x, po.farmer_id, _owed(db, x.id)[po.farmer_id], po, key)
    return ls.run(db, ctx, op)


# ---------------------------------------------------------------- approval chain
def _primary_verified(db: Session, farmer_id: uuid.UUID) -> FarmerBankAccount | None:
    return db.scalars(select(FarmerBankAccount).where(FarmerBankAccount.farmer_id == farmer_id, FarmerBankAccount.is_primary == true(),
                                                      FarmerBankAccount.status == "VERIFIED")).first()


def action(db: Session, ctx: RequestContext, principal: Principal, payout_id: uuid.UUID, act: str, reason: str | None, key: str | None
           ) -> Payout:
    """submit / cancel / release-hold (payouts.calculate) · approve / reject (payouts.approve, never the calculator)."""
    code = P.PAYOUTS_APPROVE if act in ("approve", "reject") else P.PAYOUTS_CALCULATE
    po = payout_for(db, principal, payout_id, code)
    target = {"submit": "PENDING_APPROVAL", "approve": "APPROVED", "reject": "REJECTED", "cancel": "CANCELLED",
              "release": "PENDING_APPROVAL"}[act]
    if ms.replay_action(po, key, target):
        return po
    if act in ("approve", "reject") and principal.user_id == po.calculated_by:
        raise PermissionDenied("You calculated this payout, so someone else must decide on it.", error_code="SEPARATION_OF_DUTIES")
    if act in ("reject", "cancel", "release") and not (reason and reason.strip()):
        raise ValidationFailed("Give a reason.", error_code="REASON_REQUIRED")
    if act == "release" and po.status != "ON_HOLD":
        raise Conflict("Only a payout ON_HOLD is released.", error_code="PAYOUT_NOT_ON_HOLD")

    def op() -> Payout:
        x = ms.lock(db, Payout, po.id)
        payload: dict[str, Any] = {"status": target}
        if act == "approve":
            acct = _primary_verified(db, x.farmer_id)
            if acct is None:
                raise Conflict("The farmer has no primary VERIFIED bank account; a payout is approved only to a verified account.",
                               error_code="BANK_ACCOUNT_NOT_VERIFIED")
            x.bank_account_id, x.bank_last4 = acct.id, acct.account_last4
            x.approved_by, x.approved_at = principal.user_id, utcnow()
            payload["bank_account_id"] = acct.id
        if act == "release":                                        # back to approval: the next approver re-checks the account
            x.bank_account_id, x.bank_last4, x.approved_by, x.approved_at = None, None, None, None
        if act in ("reject", "cancel"):
            x.reason = reason
        frm = _move(db, ctx, x, target, reason)
        x.action_key = key
        event = {"submit": "PAYOUT_SUBMITTED", "approve": "PAYOUT_APPROVED", "reject": "PAYOUT_REJECTED", "cancel": "PAYOUT_CANCELLED",
                 "release": "PAYOUT_HOLD_RELEASED"}[act]
        _audit(db, ctx, event, x, payload, reason, {"status": frm})
        return x
    return ls.run(db, ctx, op)


# ---------------------------------------------------------------- execution
def _executor_ok(principal: Principal, po: Payout) -> None:
    if principal.user_id in (po.approved_by, po.calculated_by):
        raise PermissionDenied("You calculated or approved this payout, so someone else must execute it.", error_code="SEPARATION_OF_DUTIES")


def initiate(db: Session, ctx: RequestContext, principal: Principal, payout_id: uuid.UUID, key: str | None,
             adapter: PayoutAdapter | None = None) -> Payout:
    """APPROVED → PAYMENT_PENDING after re-checking the bank account under lock (a change → ON_HOLD, BANK_ACCOUNT_CHANGED). With MANUAL,
    no provider is called: finance pays at the bank and confirms with evidence."""
    po = payout_for(db, principal, payout_id, P.PAYOUTS_EXECUTE)
    if ms.replay_action(po, key, ("PAYMENT_PENDING", "UNCONFIRMED", "PAID", "FAILED")):
        return po
    _executor_ok(principal, po)
    adp = adapter_for(po.adapter_code, adapter)
    held: list[bool] = []

    def op() -> Payout:
        x = ms.lock(db, Payout, po.id)
        PAYOUT_MACHINE.assert_transition(x.status, "PAYMENT_PENDING")
        acct = ms.lock(db, FarmerBankAccount, x.bank_account_id) if x.bank_account_id else None
        if acct is None or acct.status != "VERIFIED" or not acct.is_primary or acct.farmer_id != x.farmer_id:
            frm = _move(db, ctx, x, "ON_HOLD", "BANK_ACCOUNT_CHANGED")
            x.reason = "BANK_ACCOUNT_CHANGED"
            _audit(db, ctx, "PAYOUT_ON_HOLD", x, {"status": "ON_HOLD", "bank_account_id": x.bank_account_id}, "BANK_ACCOUNT_CHANGED",
                   {"status": frm})
            held.append(True)
            return x
        frm = _move(db, ctx, x, "PAYMENT_PENDING")
        x.adapter_code, x.executed_by, x.action_key = adp.code, principal.user_id, key
        _tx(db, x, "INITIATED", principal.user_id)
        _audit(db, ctx, "PAYOUT_INITIATED", x, {"status": "PAYMENT_PENDING", "adapter": adp.code, "bank_account_id": x.bank_account_id},
               None, {"status": frm})
        return x
    x = ls.run(db, ctx, op)
    if held:
        raise Conflict("The farmer's bank account changed after approval: the payout is ON_HOLD and must be re-approved.",
                       error_code="BANK_ACCOUNT_CHANGED", details={"payout_code": x.payout_code, "status": "ON_HOLD"})
    if isinstance(adp, ManualPayoutAdapter):
        return x
    try:                                                            # provider call outside the database transaction
        result = adp.create_payout(PayoutRequest(x.payout_code, x.amount, x.currency, str(x.bank_account_id), x.payout_code))
    except PayoutTimeout:
        return _provider_outcome(db, ctx, x, "UNCONFIRMED", None, "No answer from the payout provider")
    except PayoutUnavailable as e:
        return _provider_outcome(db, ctx, x, "FAILED", None, str(e)[:2000])
    return _provider_outcome(db, ctx, x, {"PENDING": "PAYMENT_PENDING", "PAID": "PAID", "FAILED": "FAILED"}[result.status], result.external_id,
                             None)


def _provider_outcome(db: Session, ctx: RequestContext, po: Payout, to: str, external_id: str | None, note: str | None) -> Payout:
    def op() -> Payout:
        x = ms.lock(db, Payout, po.id)
        if external_id:
            x.external_reference = external_id
        if to == x.status:
            _tx(db, x, "STATUS_QUERIED", None, note=note)
            return x
        frm = _move(db, ctx, x, to, note)
        if to == "PAID":
            x.paid_at = utcnow()
        if to == "FAILED":
            x.reason = note
        _tx(db, x, to if to in ("PAID", "FAILED", "UNCONFIRMED") else "STATUS_QUERIED", None, note=note)
        _audit(db, ctx, f"PAYOUT_{to}", x, {"status": to, "adapter": x.adapter_code, "external_reference": x.external_reference}, note,
               {"status": frm})
        return x
    return ls.run(db, ctx, op)


def query_status(db: Session, ctx: RequestContext, principal: Principal, payout_id: uuid.UUID, adapter: PayoutAdapter | None = None) -> Payout:
    po = payout_for(db, principal, payout_id, P.PAYOUTS_EXECUTE)
    adp = adapter_for(po.adapter_code, adapter)
    if isinstance(adp, ManualPayoutAdapter):
        raise Conflict("No payout provider is contracted: confirm the payment with its bank reference and evidence.",
                       error_code="MANUAL_ACTION_REQUIRED")
    if po.status not in ("PAYMENT_PENDING", "UNCONFIRMED"):
        raise Conflict(f"Payout {po.payout_code} is {po.status}.", error_code="PAYOUT_NOT_PENDING")
    try:
        result = adp.get_status(po.external_reference or po.payout_code)
    except (PayoutTimeout, PayoutUnavailable):
        return _provider_outcome(db, ctx, po, "UNCONFIRMED" if po.status == "PAYMENT_PENDING" else po.status, None,
                                 "Status query: no answer from the payout provider")
    return _provider_outcome(db, ctx, po, {"PENDING": "PAYMENT_PENDING", "PAID": "PAID", "FAILED": "FAILED"}[result.status],
                             result.external_id, None)


def upload_evidence(db: Session, ctx: RequestContext, principal: Principal, payout_id: uuid.UUID, category: str, filename: str | None,
                    data: bytes, title: str | None) -> Document:
    if category == DocumentCategory.PAYOUT_EVIDENCE.value:
        po = payout_for(db, principal, payout_id, P.PAYOUTS_EXECUTE)
        if po.status not in ("PAYMENT_PENDING", "UNCONFIRMED"):
            raise Conflict("Remittance evidence is attached while the payment is pending.", error_code="PAYOUT_LOCKED")
    elif category == DocumentCategory.RECONCILIATION_EVIDENCE.value:
        po = payout_for(db, principal, payout_id, P.PAYOUTS_RECONCILE)
        if po.status != "PAID":
            raise Conflict("A statement is attached to a PAID payout awaiting reconciliation.", error_code="PAYOUT_LOCKED")
    else:
        raise ValidationFailed("Category must be PAYOUT_EVIDENCE or RECONCILIATION_EVIDENCE.", error_code="INVALID_CATEGORY")
    doc = document_service.create_document(db, ctx, entity_type=ENTITY, entity_id=po.id, organization_id=po.organization_id,
                                           environment=po.environment, category=category, title=title or category.replace("_", " ").title(),
                                           filename=filename, data=data)
    db.commit()
    return doc


def confirm_paid(db: Session, ctx: RequestContext, principal: Principal, payout_id: uuid.UUID, data: Any, key: str | None) -> Payout:
    """MANUAL: the money left the bank — record its reference and remittance evidence (PDF). PAID is not RECONCILED."""
    po = payout_for(db, principal, payout_id, P.PAYOUTS_EXECUTE)
    if ms.replay_action(po, key, "PAID"):
        return po
    _executor_ok(principal, po)
    ref = (data.external_reference or "").strip()
    if not ref:
        raise ValidationFailed("The bank / remittance reference is required.", error_code="PAYOUT_EVIDENCE_REQUIRED")
    document_service.require_attached(db, data.document_id, ENTITY, po.id, {DocumentCategory.PAYOUT_EVIDENCE.value})

    def op() -> Payout:
        x = ms.lock(db, Payout, po.id)
        frm = _move(db, ctx, x, "PAID")
        x.external_reference, x.evidence_document_id, x.paid_at, x.action_key = ref, data.document_id, utcnow(), key
        _tx(db, x, "PAID", principal.user_id, evidence=data.document_id, note=data.note)
        _audit(db, ctx, "PAYOUT_PAID", x, {"status": "PAID", "external_reference": ref, "evidence_document_id": data.document_id}, None,
               {"status": frm})
        return x
    return ls.run(db, ctx, op)


def fail(db: Session, ctx: RequestContext, principal: Principal, payout_id: uuid.UUID, reason: str, key: str | None) -> Payout:
    po = payout_for(db, principal, payout_id, P.PAYOUTS_EXECUTE)
    if ms.replay_action(po, key, "FAILED"):
        return po
    _executor_ok(principal, po)
    if not (reason and reason.strip()):
        raise ValidationFailed("Give a reason.", error_code="REASON_REQUIRED")

    def op() -> Payout:
        x = ms.lock(db, Payout, po.id)
        frm = _move(db, ctx, x, "FAILED", reason)
        x.reason, x.action_key = reason, key
        _tx(db, x, "FAILED", principal.user_id, note=reason)
        _audit(db, ctx, "PAYOUT_FAILED", x, {"status": "FAILED"}, reason, {"status": frm})
        return x
    return ls.run(db, ctx, op)


# ---------------------------------------------------------------- reconciliation (≠ executor)
def reconcile(db: Session, ctx: RequestContext, principal: Principal, payout_id: uuid.UUID, data: Any, key: str | None) -> PayoutReconciliation:
    po = payout_for(db, principal, payout_id, P.PAYOUTS_RECONCILE)
    if key and (prior := db.scalars(select(PayoutReconciliation).join(Payout, Payout.id == PayoutReconciliation.payout_id).where(
            Payout.id == po.id, Payout.action_key == key).order_by(PayoutReconciliation.created_at.desc())).first()) is not None:
        return prior
    payers = {po.executed_by} | {t.actor_id for t in transactions(db, po.id) if t.kind in ("INITIATED", "PAID")}
    if principal.user_id in payers:
        raise PermissionDenied("You executed this payout, so someone else must reconcile it.", error_code="SEPARATION_OF_DUTIES")
    document_service.require_attached(db, data.document_id, ENTITY, po.id, {DocumentCategory.RECONCILIATION_EVIDENCE.value})
    currency = data.statement_currency.upper()
    amount = Decimal(str(data.statement_amount))

    def op() -> PayoutReconciliation:
        x = ms.lock(db, Payout, po.id)
        if x.status != "PAID":
            raise Conflict(f"Payout {x.payout_code} is {x.status}; only a PAID payout is reconciled.", error_code="PAYOUT_NOT_PAID")
        had_exception = db.scalars(select(PayoutReconciliation.id).where(PayoutReconciliation.payout_id == x.id,
                                                                         PayoutReconciliation.result == "EXCEPTION")).first() is not None
        same_money = amount == x.amount and currency == x.currency
        same_ref = data.statement_reference.strip() == (x.external_reference or "")
        resolved = had_exception and bool(data.note and data.note.strip())
        result = "MATCHED" if same_money and (same_ref or resolved) else "EXCEPTION"
        rec = PayoutReconciliation(payout_id=x.id, result=result, statement_reference=data.statement_reference.strip(), statement_amount=amount,
                                   statement_currency=currency, statement_date=data.statement_date, evidence_document_id=data.document_id,
                                   note=data.note, reconciled_by=principal.user_id)
        db.add(rec)
        x.action_key = key
        payload = {"result": result, "statement_reference": rec.statement_reference, "statement_amount": str(amount),
                   "statement_currency": currency, "amount_matches": same_money, "reference_matches": same_ref}
        if result == "MATCHED":
            frm = _move(db, ctx, x, "RECONCILED")
            x.reconciled_at = utcnow()
            _audit(db, ctx, "PAYOUT_RECONCILED", x, {**payload, "status": "RECONCILED"}, data.note, {"status": frm})
            run = ms.lock(db, SettlementRun, x.settlement_run_id)
            ss.complete_if_done(db, ctx, run)
        else:
            _audit(db, ctx, "PAYOUT_RECONCILIATION_EXCEPTION", x, payload, data.note)
        db.flush()
        return rec
    return ls.run(db, ctx, op)


# ---------------------------------------------------------------- recovery cases (no automatic clawback)
def close_adjustment(db: Session, ctx: RequestContext, principal: Principal, adjustment_id: uuid.UUID, resolution: str, key: str | None
                     ) -> PayoutAdjustment:
    a = db.get(PayoutAdjustment, adjustment_id)
    if a is None:
        raise ms.nf("Recovery case", "ADJUSTMENT_NOT_FOUND")
    ms.require(principal, a.organization_id, P.PAYOUTS_RECONCILE, visible=PAYOUT_VIEW, what="Recovery case", nf_code="ADJUSTMENT_NOT_FOUND")
    if a.status == "CLOSED" and key:
        return a
    if not (resolution and resolution.strip()):
        raise ValidationFailed("Record how the case was resolved.", error_code="REASON_REQUIRED")

    def op() -> PayoutAdjustment:
        x = ms.lock(db, PayoutAdjustment, a.id)
        frm = ms.transition(db, ctx, PAYOUT_ADJUSTMENT_MACHINE, x, "payout_adjustment", "CLOSED", resolution)
        x.closed_by, x.closed_at, x.resolution = principal.user_id, utcnow(), resolution
        ls.audit(db, ctx, "PAYOUT_RECOVERY_CASE_CLOSED", "payout_adjustment", x.id, [x.organization_id],
                 {"adjustment_code": x.adjustment_code, "status": "CLOSED"}, resolution, {"status": frm})
        return x
    return ls.run(db, ctx, op)


# ---------------------------------------------------------------- lineage
def lineage(db: Session, principal: Principal, payout_id: uuid.UUID) -> dict[str, Any]:
    """payout → run (hash) → entitlement lines → allocation & revenue-share versions → revenue records → order item / payment / 9B transfer
    / batch / monitoring period → costs. Never bank credentials."""
    po = payout_for(db, principal, payout_id)
    run = db.get(SettlementRun, po.settlement_run_id)
    assert run is not None
    return {"payout": {"id": po.id, "payout_code": po.payout_code, "status": po.status, "amount": str(po.amount), "currency": po.currency,
                       "replaces_payout_id": po.replaces_payout_id},
            "farmer_entitlements": [{"allocation_line_id": e.allocation_line_id, "project_farm_id": e.project_farm_id, "farm_id": e.farm_id,
                                     "share_pct": str(e.share_pct), "amount": str(e.amount)}
                                    for e in ss.entitlements(db, run.id) if e.farmer_id == po.farmer_id],
            **run_lineage(db, run)}


def run_lineage(db: Session, run: SettlementRun) -> dict[str, Any]:
    rv = db.get(RevenueShareVersion, run.revenue_share_version_id)
    av = db.get(FarmAllocationVersion, run.allocation_version_id)
    mp = db.get(MonitoringPeriod, run.monitoring_period_id)
    assert rv is not None and av is not None and mp is not None
    revenue = []
    for item, rec in ss.revenue_items(db, run.id):
        oi = db.get(OrderItem, rec.order_item_id)
        o = db.get(Order, rec.order_id)
        pay = db.get(Payment, rec.payment_id)
        tr = db.get(CreditTransfer, rec.transfer_id)
        revenue.append({"revenue_code": rec.revenue_code, "kind": rec.kind, "amount": str(rec.amount), "active": item.active,
                        "order_code": o.order_code if o else None, "order_item_code": oi.item_code if oi else None,
                        "payment_code": pay.payment_code if pay else None, "transfer_code": tr.transfer_code if tr else None,
                        "batch_id": rec.batch_id, "monitoring_period_id": rec.monitoring_period_id, "refund_id": rec.refund_id})
    costs = [{"cost_code": c.cost_code, "category": c.category, "amount": str(c.amount), "active": i.active} for i, c in ss.cost_items(db, run.id)]
    return {"settlement_run": {"id": run.id, "run_code": run.run_code, "status": run.status, "calculation_version": run.calculation_version,
                               "input_sha256": run.input_sha256, "project_id": run.project_id, "monitoring_period": mp.period_number},
            "revenue_share_version": {"version_code": rv.version_code, "farmer_share_pct": str(rv.farmer_share_pct),
                                      "deduct_approved_costs": rv.deduct_approved_costs, "rounding_mode": rv.rounding_mode,
                                      "source_reference": rv.source_reference},
            "allocation_version": {"version_code": av.version_code, "basis_reference": av.basis_reference},
            "revenue": revenue, "costs": costs}


# ---------------------------------------------------------------- financial summary (reporting)
def summary(db: Session, principal: Principal, project_id: uuid.UUID | None = None) -> dict[str, Any]:
    projects = [p for p in fs.visible_projects(db, principal) if project_id is None or p.id == project_id]
    if project_id is not None and not projects:
        raise NotFound("Project not found.", error_code="PROJECT_NOT_FOUND")
    ids = [p.id for p in projects]
    rev: dict[str, dict[str, Decimal]] = defaultdict(lambda: {"recognized": Decimal(0), "reversed": Decimal(0)})
    costs: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    runs: dict[str, dict[str, Decimal]] = defaultdict(lambda: {"distributable": Decimal(0), "farmer_total": Decimal(0),
                                                               "developer_residual": Decimal(0)})
    pays: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "amounts": defaultdict(Decimal)})
    open_cases = 0
    if ids:
        for r in db.scalars(select(RevenueRecord).where(RevenueRecord.project_id.in_(ids))):
            rev[r.currency]["recognized" if r.kind == "RECOGNITION" else "reversed"] += r.amount
        for c in db.scalars(select(ProjectCost).where(ProjectCost.project_id.in_(ids), ProjectCost.status == "APPROVED")):
            costs[c.currency][c.category] += c.amount
        for s in db.scalars(select(SettlementRun).where(SettlementRun.project_id.in_(ids), SettlementRun.status.in_(("APPROVED", "COMPLETED")))):
            for k in ("distributable", "farmer_total", "developer_residual"):
                runs[s.currency][k] += getattr(s, k) or Decimal(0)
        orgs = {p.organization_id for p in projects}
        for po in db.scalars(select(Payout).where(Payout.organization_id.in_(orgs))):
            pays[po.status]["count"] += 1
            pays[po.status]["amounts"][po.currency] += po.amount
        open_cases = len(db.scalars(select(PayoutAdjustment.id).where(PayoutAdjustment.project_id.in_(ids),
                                                                      PayoutAdjustment.status == "OPEN")).all())
    return {
        "revenue": [{"currency": c, "recognized": str(v["recognized"]), "reversed": str(v["reversed"]), "net": str(v["recognized"] + v["reversed"])}
                    for c, v in sorted(rev.items())],
        "costs_by_category": [{"currency": c, "category": k, "amount": str(a)} for c, cats in sorted(costs.items()) for k, a in sorted(cats.items())],
        "settlements": [{"currency": c, **{k: str(a) for k, a in v.items()}} for c, v in sorted(runs.items())],
        "payouts_by_status": [{"status": st, "count": v["count"],
                               "amounts": [{"currency": c, "amount": str(a)} for c, a in sorted(v["amounts"].items())]}
                              for st, v in sorted(pays.items())],
        "open_recovery_cases": open_cases,
        "demo_note": fs.DEMO_NOTE if ms.env_of(principal) == "DEMO" else None,
    }


def _payout_resolver(db: Session, principal: Principal, entity_id: uuid.UUID, kind: str) -> None:
    po = db.get(Payout, entity_id)
    if kind == "manage":
        raise PermissionDenied("Payout evidence is immutable.", error_code="DOCUMENT_IMMUTABLE")
    if po is None or not any(principal.can_in_org(c, po.organization_id) for c in (P.PAYOUTS_EXECUTE, P.PAYOUTS_RECONCILE, P.PAYOUTS_APPROVE)):
        raise NotFound("Document not found.", error_code="DOCUMENT_NOT_FOUND")


document_service.register_resolver(ENTITY, _payout_resolver)
