"""Phase 11 — REAL concurrency and direct-SQL trigger tests for revenue, settlement and payouts.

As for Phases 9B / 10, this module takes a SQL Server database snapshot of the test database, builds a committed world (TEST registry
issuance → 9B ledger → verified buyer → listings → deliveries → approved revenue-share version, allocation and bank account), races
finance operations from separate threads (each with its own Session / connection), then reverts the database from the snapshot.

Races: recognition × delivery, calculation × 2, settlement approval × 2, payout creation × 2, execution × 2, bank-account change × execution,
reconciliation × 2, refund completion × settlement calculation. Every scenario asserts the financial invariants: one recognition per item,
one reversal per recognition, one active claim per revenue record / cost, one open payout per run and farmer, figures reproducible from the
frozen snapshot, Σ entitlements = farmer total, no payout ≤ 0.
"""
import threading
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.context import RequestContext
from app.core.database import get_db, get_engine
from app.core.errors import AppError
from app.core.rate_limit import limiter
from app.main import create_app
from app.models import (
    AuditLog,
    FarmerEntitlement,
    OrderItem,
    Payout,
    PayoutReconciliation,
    PayoutTransaction,
    ProjectFarm,
    RevenueRecord,
    SettlementRevenueItem,
    SettlementRun,
    User,
)
from app.models.documents import DocumentCategory
from app.services import farmer_service
from app.services import finance_service as fs
from app.services import order_service as os_
from app.services import payment_service as ps
from app.services import payout_service as pys
from app.services import settlement_service as ss
from tests.calc_fixture import calc_scenario
from tests.conftest import Actor, login, make_org, make_user
from tests.phase2 import staff
from tests.test_ledger import L
from tests.test_registry import PDF

SNAP = "carbon_platform_test_snap11"
RANGES = {"A": 100, "B": 100, "C": 100, "D": 100, "E": 100, "F": 100}
V = "/api/v1"


@dataclass
class World:
    engine: Engine
    project_id: uuid.UUID
    period_id: uuid.UUID
    share_id: uuid.UUID
    alloc_id: uuid.UUID
    farmer_id: uuid.UUID
    bank_id: uuid.UUID
    pm: uuid.UUID
    fin: uuid.UUID
    fin2: uuid.UUID
    fin3: uuid.UUID
    fin4: uuid.UUID
    qa: uuid.UUID
    orders: dict[str, dict[str, Any]] = field(default_factory=dict)          # name → {"order", "item", "transfer", "payment"}
    state: dict[str, Any] = field(default_factory=dict)


def _master() -> Engine:
    return create_engine(get_settings().database_url("master"), isolation_level="AUTOCOMMIT")


@pytest.fixture(scope="module")
def world() -> Iterator[World]:
    db_name = get_settings().SQL_SERVER_DATABASE
    assert db_name.endswith("_test")
    engine = get_engine()
    engine.dispose()
    master = _master()
    with master.connect() as m:
        logical, physical = m.execute(text("SELECT name, physical_name FROM sys.master_files WHERE database_id = DB_ID(:d) AND type = 0"),
                                      {"d": db_name}).one()
        sparse = physical.rsplit("\\", 1)[0] + f"\\{SNAP}.ss"
        m.execute(text(f"CREATE DATABASE [{SNAP}] ON (NAME = [{logical}], FILENAME = '{sparse}') AS SNAPSHOT OF [{db_name}]"))
    session = Session(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        app = create_app()
        app.dependency_overrides[get_db] = lambda: session
        app.state.access_log_writer = lambda _r: None
        limiter.reset()
        with TestClient(app, base_url="http://testserver") as client:
            k = calc_scenario(session, client, 84.20, 29.20, "9710 2000 3000")
            lg = L(client, session, k, ranges=[(f"Q{n}-0001", f"Q{n}-{q:04d}", q) for n, q in RANGES.items()])
            lg.open()
            org = lg.org
            fins = [staff(session, client, org, "FINANCE_MANAGER") for _ in range(4)]
            pm = k.x.c.t.pm
            cu = make_user(session, roles=[("MARKETPLACE_COMPLIANCE", None)])
            comp = Actor(cu, login(client, cu))
            buyer_org = make_org(session, org_type="BUYER")
            buyer = staff(session, client, buyer_org, "BUYER")
            session.commit()

            def post(url: str, who: Actor, body: Any = None, **kw: Any) -> Any:
                r = client.post(f"{V}{url}", headers=who.headers, json=body if body is not None else {}, **kw)
                assert r.status_code in (200, 201), (url, r.text)
                return r.json()

            def upload(url: str, who: Actor, data: dict | None = None) -> str:
                r = client.post(f"{V}{url}", headers=who.headers, files={"file": ("e.pdf", PDF, "application/pdf")}, data=data or {})
                assert r.status_code == 201, r.text
                return str(r.json()["document_id"])

            post("/marketplace/buyer-profile", buyer, {"legal_name": "TEST Buyer"})
            upload("/marketplace/buyer-profile/documents", buyer)
            pid = post("/marketplace/buyer-profile/submit-kyc", buyer)["id"]
            post(f"/marketplace/buyer-profiles/{pid}/verify", comp)
            pos = client.get(f"{V}/credits/batches/{lg.batch['id']}/positions", headers=lg.qa.headers).json()
            ranges = {p["registry_range"][1]: p["serial_range_id"] for p in pos}
            orders: dict[str, dict[str, Any]] = {}
            for name in RANGES:
                lst = post("/marketplace/listings", lg.cm, {"seller_organization_id": str(org.id), "batch_id": lg.batch["id"],
                                                            "serial_range_id": ranges[name], "title": f"TEST {name}", "listed_quantity": 10,
                                                            "unit_price": "10.00", "currency": "INR", "payment_window_hours": 24})
                post(f"/marketplace/listings/{lst['id']}/submit", lg.cm)
                post(f"/marketplace/listings/{lst['id']}/approve", fins[0])
                o = post("/orders", buyer, {"buyer_organization_id": str(buyer_org.id), "items": [{"listing_id": lst["id"], "quantity": 10}]})
                doc = upload(f"/orders/{o['id']}/documents", buyer)
                pay = post("/payments", buyer, {"order_id": o["id"], "amount": o["total"], "currency": "INR",
                                                "external_reference": f"BANK-{name}", "document_id": doc})
                post(f"/payments/{pay['id']}/confirm", fins[0])
                od = client.get(f"{V}/orders/{o['id']}", headers=buyer.headers).json()
                orders[name] = {"order": uuid.UUID(o["id"]), "item": uuid.UUID(od["items"][0]["id"]),
                                "transfer": uuid.UUID(od["items"][0]["transfer_id"]), "payment": uuid.UUID(pay["id"])}
            for name in ("A", "B"):                                                    # delivered before the races (A, B); C–F later
                post(f"/orders/transfers/{orders[name]['transfer']}/complete", lg.qa)
            rev = client.get(f"{V}/revenue", headers=fins[0].headers, params={"project_id": k.project_id}).json()
            period_id = rev[0]["monitoring_period_id"]
            sh = post("/revenue-share", pm, {"project_id": k.project_id, "farmer_share_pct": "40", "deduct_approved_costs": False,
                                             "rounding_mode": "HALF_UP", "effective_from": "2026-01-01", "source_reference": "TEST BSA"})
            post(f"/revenue-share/{sh['id']}/submit", pm)
            post(f"/revenue-share/{sh['id']}/approve", fins[0])
            pfs = session.scalars(select(ProjectFarm).where(ProjectFarm.project_id == uuid.UUID(k.project_id))).all()
            shares = ["50", "50"]
            al = post("/allocations", pm, {"project_id": k.project_id, "monitoring_period_id": period_id, "basis_reference": "TEST",
                                           "lines": [{"project_farm_id": str(pf.id), "share_pct": s} for pf, s in zip(pfs, shares, strict=True)]})
            post(f"/allocations/{al['id']}/submit", pm)
            post(f"/allocations/{al['id']}/approve", fins[0])
            farmer_id = pfs[0].farmer_id
            fr = post(f"/farmers/{farmer_id}/bank-accounts", pm, {"account_holder_name": "Asha Patil", "bank_name": "State Bank",
                                                                  "routing_code": "SBIN0001234", "account_number": "1234 5678 9012"})
            bank_id = fr["bank_accounts"][0]["id"]
            post(f"/farmers/{farmer_id}/bank-accounts/{bank_id}/decision", fins[0], {"decision": "VERIFIED", "notes": "TEST"})
            session.commit()
            yield World(engine, uuid.UUID(k.project_id), uuid.UUID(period_id), uuid.UUID(sh["id"]), uuid.UUID(al["id"]), farmer_id,
                        uuid.UUID(bank_id), pm.user.id, *(f.user.id for f in fins), lg.qa.user.id, orders)
    finally:
        session.close()
        limiter.reset()
        engine.dispose()
        with master.connect() as m:
            m.execute(text(f"ALTER DATABASE [{db_name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE"))
            try:
                m.execute(text(f"RESTORE DATABASE [{db_name}] FROM DATABASE_SNAPSHOT = '{SNAP}'"))
            finally:
                m.execute(text(f"ALTER DATABASE [{db_name}] SET MULTI_USER"))
            m.execute(text(f"DROP DATABASE [{SNAP}]"))
        master.dispose()
        engine.dispose()


Op = Callable[[Session, RequestContext, Any], Any]


def race(w: World, *ops: tuple[uuid.UUID, Op]) -> list[tuple[str, Any]]:
    """Each op in its own thread with its own Session (own connection), released together by a barrier."""
    from app.security.principal import load_principal
    barrier = threading.Barrier(len(ops))
    results: list[tuple[str, Any]] = [("", None)] * len(ops)

    def worker(i: int, user_id: uuid.UUID, op: Op) -> None:
        s = Session(bind=w.engine, expire_on_commit=False, autoflush=False)
        try:
            user = s.get(User, user_id)
            assert user is not None
            principal = load_principal(s, user, None)
            ctx = RequestContext(request_id=f"race11-{i}", user_id=user_id)
            s.commit()
            barrier.wait(timeout=30)
            results[i] = ("ok", op(s, ctx, principal))
        except AppError as e:
            results[i] = ("err", e.error_code)
        except Exception as e:                                       # surfaced in the assertion message
            results[i] = ("exc", repr(e))
        finally:
            s.close()

    threads = [threading.Thread(target=worker, args=(i, u, op)) for i, (u, op) in enumerate(ops)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=120)
    return results


def run_as(w: World, user_id: uuid.UUID, op: Op) -> Any:
    from app.security.principal import load_principal
    with Session(bind=w.engine, expire_on_commit=False, autoflush=False) as s:
        user = s.get(User, user_id)
        assert user is not None
        return op(s, RequestContext(request_id=f"setup-{uuid.uuid4().hex[:6]}", user_id=user_id), load_principal(s, user, None))


class _Run:
    def __init__(self, w: World) -> None:
        self.project_id, self.monitoring_period_id, self.currency = w.project_id, w.period_id, "INR"
        self.revenue_share_version_id, self.allocation_version_id = w.share_id, w.alloc_id


def new_run(w: World) -> uuid.UUID:
    return uuid.UUID(str(run_as(w, w.fin2, lambda s, ctx, p: ss.create(s, ctx, p, _Run(w), None).id)))


def deliver(w: World, name: str) -> None:
    class D:
        document_id = None
    run_as(w, w.qa, lambda s, ctx, p: os_.complete_transfer(s, ctx, p, w.orders[name]["transfer"], D, None))


def approved_run(w: World) -> uuid.UUID:
    rid = new_run(w)
    run_as(w, w.fin2, lambda s, ctx, p: ss.calculate(s, ctx, p, rid, None))
    run_as(w, w.fin2, lambda s, ctx, p: ss.action(s, ctx, p, rid, "submit", None, None))
    run_as(w, w.fin3, lambda s, ctx, p: ss.action(s, ctx, p, rid, "approve", None, None))
    return rid


def approved_payout(w: World, run_id: uuid.UUID) -> uuid.UUID:
    pid = run_as(w, w.fin2, lambda s, ctx, p: pys.create_for_run(s, ctx, p, run_id)[0].id)
    run_as(w, w.fin2, lambda s, ctx, p: pys.action(s, ctx, p, pid, "submit", None, None))
    run_as(w, w.fin3, lambda s, ctx, p: pys.action(s, ctx, p, pid, "approve", None, None))
    return uuid.UUID(str(pid))


def invariants(w: World) -> None:
    with Session(bind=w.engine) as s:
        rec = s.execute(select(RevenueRecord.order_item_id, func.count()).where(RevenueRecord.kind == "RECOGNITION")
                        .group_by(RevenueRecord.order_item_id)).all()
        assert all(n == 1 for _, n in rec), rec                                                   # one recognition per item
        rv = s.execute(select(RevenueRecord.reverses_revenue_id, func.count()).where(RevenueRecord.kind == "REVERSAL")
                       .group_by(RevenueRecord.reverses_revenue_id)).all()
        assert all(n == 1 for _, n in rv), rv                                                     # one reversal per recognition
        claims = s.execute(select(SettlementRevenueItem.revenue_record_id, func.count()).where(SettlementRevenueItem.active == True)  # noqa: E712
                           .group_by(SettlementRevenueItem.revenue_record_id)).all()
        assert all(n == 1 for _, n in claims), claims                                             # never settled twice
        open_ = s.execute(select(Payout.settlement_run_id, Payout.farmer_id, func.count()).where(
            Payout.status.not_in(("REJECTED", "CANCELLED", "FAILED"))).group_by(Payout.settlement_run_id, Payout.farmer_id)).all()
        assert all(n == 1 for *_, n in open_), open_                                              # one open payout per run & farmer
        assert s.scalar(select(func.count()).select_from(Payout).where(Payout.amount <= 0)) == 0
        for r in s.scalars(select(SettlementRun).where(SettlementRun.input_snapshot.is_not(None))).all():
            ents = s.scalar(select(func.coalesce(func.sum(FarmerEntitlement.amount), 0)).where(FarmerEntitlement.settlement_run_id == r.id))
            assert ents == r.farmer_total, r.run_code
            assert r.distributable == r.farmer_total + r.developer_residual, r.run_code
            links = s.scalar(select(func.coalesce(func.sum(SettlementRevenueItem.amount), 0)).where(SettlementRevenueItem.settlement_run_id == r.id))
            assert links == r.gross_revenue, r.run_code
        for p in s.scalars(select(Payout).where(Payout.status.in_(("CALCULATED", "PENDING_APPROVAL", "APPROVED", "PAYMENT_PENDING", "PAID",
                                                                    "RECONCILED")))).all():
            owed = s.scalar(select(func.sum(FarmerEntitlement.amount)).where(FarmerEntitlement.settlement_run_id == p.settlement_run_id,
                                                                            FarmerEntitlement.farmer_id == p.farmer_id))
            assert owed == p.amount, p.payout_code                                                # payout = Σ entitlements (calculated)


def _ok(results: list[tuple[str, Any]]) -> list[Any]:
    assert all(k in ("ok", "err") for k, _ in results), results
    return [v for k, v in results if k == "ok"]


# ---------------------------------------------------------------- 1 delivery (recognizes) × explicit re-recognition
def test_1_recognition_races_delivery(world: World) -> None:
    w = world
    item = w.orders["C"]["item"]
    res = race(w, (w.qa, lambda s, ctx, p: (os_.complete_transfer(s, ctx, p, w.orders["C"]["transfer"], type("D", (), {"document_id": None}),
                                                                   None), "delivered")[1]),
               (w.fin, lambda s, ctx, p: fs.recognize(s, ctx, p, item).id))
    assert res[0] == ("ok", "delivered"), res
    assert res[1][0] == "ok" or res[1] == ("err", "REVENUE_NOT_RECOGNIZABLE"), res
    with Session(bind=w.engine) as s:
        assert s.scalar(select(func.count()).select_from(RevenueRecord).where(RevenueRecord.order_item_id == item)) == 1
    again = race(w, (w.fin, lambda s, ctx, p: fs.recognize(s, ctx, p, item).id), (w.fin4, lambda s, ctx, p: fs.recognize(s, ctx, p, item).id))
    assert len(set(_ok(again))) == 1, again                                                       # idempotent under concurrency
    invariants(w)


# ---------------------------------------------------------------- 2 two calculations claim the same revenue
def test_2_two_calculations_one_claim(world: World) -> None:
    w = world
    r1, r2 = new_run(w), new_run(w)
    res = race(w, (w.fin2, lambda s, ctx, p: ss.calculate(s, ctx, p, r1, None).status),
               (w.fin4, lambda s, ctx, p: ss.calculate(s, ctx, p, r2, None).status))
    assert sorted(str(v) for _, v in res) == ["CALCULATED", "NOTHING_TO_SETTLE"], res
    winner = r1 if res[0] == ("ok", "CALCULATED") else r2
    w.state["run"] = winner
    w.state["calculator"] = w.fin2 if winner == r1 else w.fin4
    invariants(w)


# ---------------------------------------------------------------- 3 two approvers approve the same run
def test_3_double_settlement_approval(world: World) -> None:
    w = world
    rid = w.state["run"]
    run_as(w, w.state["calculator"], lambda s, ctx, p: ss.action(s, ctx, p, rid, "submit", None, None))
    res = race(w, (w.fin3, lambda s, ctx, p: ss.action(s, ctx, p, rid, "approve", None, None).status),
               (w.fin, lambda s, ctx, p: ss.action(s, ctx, p, rid, "approve", None, None).status))
    assert sorted(str(v) for _, v in res) == ["APPROVED", "INVALID_STATUS_TRANSITION"], res
    with Session(bind=w.engine) as s:
        n = s.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "SETTLEMENT_APPROVED", AuditLog.entity_id == str(rid)))
        assert n == 1
    invariants(w)


# ---------------------------------------------------------------- 4 two payout calculations for the same run
def test_4_double_payout_creation(world: World) -> None:
    w = world
    rid = w.state["run"]
    res = race(w, (w.fin2, lambda s, ctx, p: len(pys.create_for_run(s, ctx, p, rid))),
               (w.fin4, lambda s, ctx, p: len(pys.create_for_run(s, ctx, p, rid))))
    created = [v for k, v in res if k == "ok"]
    assert all(k in ("ok", "err") for k, _ in res) and sum(created) == 1, res
    with Session(bind=w.engine) as s:
        po = s.scalars(select(Payout).where(Payout.settlement_run_id == rid)).one()
    w.state["payout"], w.state["payout_calc"] = po.id, po.calculated_by
    invariants(w)


# ---------------------------------------------------------------- 5 two executors initiate the same payout
def test_5_double_execution(world: World) -> None:
    w = world
    pid = w.state["payout"]
    calc = w.state["payout_calc"]
    run_as(w, calc, lambda s, ctx, p: pys.action(s, ctx, p, pid, "submit", None, None))
    approver = w.fin3 if calc != w.fin3 else w.fin
    run_as(w, approver, lambda s, ctx, p: pys.action(s, ctx, p, pid, "approve", None, None))
    executors = [u for u in (w.fin, w.fin2, w.fin3, w.fin4) if u not in (calc, approver)][:2]
    res = race(w, *[(u, lambda s, ctx, p: pys.initiate(s, ctx, p, pid, None).status) for u in executors])
    assert sorted(str(v) for _, v in res) == ["INVALID_STATUS_TRANSITION", "PAYMENT_PENDING"], res
    with Session(bind=w.engine) as s:
        assert s.scalar(select(func.count()).select_from(PayoutTransaction).where(PayoutTransaction.payout_id == pid,
                                                                                   PayoutTransaction.kind == "INITIATED")) == 1
        w.state["executor"] = s.get(Payout, pid).executed_by
    invariants(w)


# ---------------------------------------------------------------- 6 two reconcilers reconcile the same PAID payout
def test_6_double_reconciliation(world: World) -> None:
    w = world
    pid, ex = w.state["payout"], w.state["executor"]
    ev = run_as(w, ex, lambda s, ctx, p: pys.upload_evidence(s, ctx, p, pid, DocumentCategory.PAYOUT_EVIDENCE.value, "e.pdf", PDF, None).id)

    class Paid:
        external_reference, document_id, note = "TEST-NEFT-RACE", ev, None
    run_as(w, ex, lambda s, ctx, p: pys.confirm_paid(s, ctx, p, pid, Paid, None))
    others = [u for u in (w.fin, w.fin2, w.fin3, w.fin4) if u != ex][:2]
    st = run_as(w, others[0], lambda s, ctx, p: pys.upload_evidence(s, ctx, p, pid, DocumentCategory.RECONCILIATION_EVIDENCE.value, "s.pdf",
                                                                    PDF, None).id)
    with Session(bind=w.engine) as s:
        amount = s.get(Payout, pid).amount

    class Stmt:
        statement_reference, statement_amount, statement_currency, statement_date, document_id, note = (
            "TEST-NEFT-RACE", amount, "INR", __import__("datetime").date(2026, 10, 3), st, None)
    res = race(w, *[(u, lambda s, ctx, p: pys.reconcile(s, ctx, p, pid, Stmt, None).result) for u in others])
    assert sorted(str(v) for _, v in res) == ["MATCHED", "PAYOUT_NOT_PAID"], res
    with Session(bind=w.engine) as s:
        assert s.scalar(select(func.count()).select_from(PayoutReconciliation).where(PayoutReconciliation.payout_id == pid)) == 1
        assert s.get(Payout, pid).status == "RECONCILED"
        assert s.get(SettlementRun, w.state["run"]).status == "COMPLETED"
    invariants(w)


# ---------------------------------------------------------------- 7 bank account deactivated while the payout is executed
def test_7_bank_change_races_execution(world: World) -> None:
    w = world
    deliver(w, "D")
    rid = approved_run(w)
    pid = approved_payout(w, rid)
    res = race(w, (w.fin4, lambda s, ctx, p: pys.initiate(s, ctx, p, pid, None).status),
               (w.pm, lambda s, ctx, p: (farmer_service.deactivate_bank_account(s, ctx, p, w.farmer_id, w.bank_id, "TEST: closed"), "off")[1]))
    assert res[1] == ("ok", "off"), res
    with Session(bind=w.engine) as s:
        po = s.get(Payout, pid)
        initiated = s.scalar(select(func.count()).select_from(PayoutTransaction).where(PayoutTransaction.payout_id == pid,
                                                                                         PayoutTransaction.kind == "INITIATED"))
    if res[0] == ("ok", "PAYMENT_PENDING"):
        assert po.status == "PAYMENT_PENDING" and initiated == 1                                   # executed against the then-verified account
    else:
        assert res[0] == ("err", "BANK_ACCOUNT_CHANGED") and po.status == "ON_HOLD" and initiated == 0, res
    invariants(w)


# ---------------------------------------------------------------- 8 refund completion races a settlement calculation
def test_8_refund_races_settlement(world: World) -> None:
    w = world
    deliver(w, "E")
    pay = w.orders["E"]["payment"]
    rf = run_as(w, w.fin, lambda s, ctx, p: ps.request_refund(s, ctx, p, pay, "TEST: refund race", None).id)
    run_as(w, w.fin2, lambda s, ctx, p: ps.decide_refund(s, ctx, p, rf, "approve", type("A", (), {"reason": None}), None))
    doc = run_as(w, w.fin, lambda s, ctx, p: ps.upload_refund_document(s, ctx, p, rf, "r.pdf", PDF, None).id)
    done = type("C", (), {"external_reference": "TEST-RF-RACE", "document_id": doc, "reason": None})
    rid = new_run(w)
    res = race(w, (w.fin, lambda s, ctx, p: ps.decide_refund(s, ctx, p, rf, "complete", done, None).status),
               (w.fin2, lambda s, ctx, p: ss.calculate(s, ctx, p, rid, None).status))
    assert res[0] == ("ok", "COMPLETED"), res
    assert res[1] in (("ok", "CALCULATED"), ("err", "NOTHING_TO_SETTLE")), res
    with Session(bind=w.engine) as s:
        rec = s.scalars(select(RevenueRecord).where(RevenueRecord.order_item_id == w.orders["E"]["item"],
                                                    RevenueRecord.kind == "RECOGNITION")).one()
        rev = s.scalars(select(RevenueRecord).where(RevenueRecord.reverses_revenue_id == rec.id)).one()     # exactly one reversal
        claimed = set(s.scalars(select(SettlementRevenueItem.revenue_record_id).where(SettlementRevenueItem.active == True)).all())  # noqa: E712
        assert rec.id in claimed                                                                  # the recognition is settled once
        if rev.id not in claimed:                                                                 # unseen reversal waits for the next run
            assert s.scalar(select(func.count()).select_from(SettlementRevenueItem).where(SettlementRevenueItem.revenue_record_id == rev.id)) == 0
    v = run_as(w, w.fin, lambda s, ctx, p: ss.verify(s, p, rid))
    assert v["reproducible"] is True
    invariants(w)


# ---------------------------------------------------------------- direct-SQL triggers (immutability / append-only)
def _refused(w: World, sql: str, params: dict[str, Any], message: str) -> None:
    with w.engine.connect() as c:
        t = c.begin()
        try:
            with pytest.raises(DBAPIError) as e:
                c.execute(text(sql), params)
            assert any(m in str(e.value) for m in message.split("|")), str(e.value)[:400]
        finally:
            if t.is_active:
                t.rollback()


def _allowed(w: World, sql: str, params: dict[str, Any]) -> None:
    with w.engine.connect() as c:
        t = c.begin()
        try:
            c.execute(text(sql), params)
        finally:
            t.rollback()


def test_9_finance_triggers(world: World) -> None:
    w = world
    with Session(bind=w.engine) as s:
        # a RECOGNITION row: on a REVERSAL row (amount < 0) "SET amount = 1" trips the kind_shape CHECK before the append-only trigger,
        # and which row .first() returns without ORDER BY depends on random UUIDs (flaky since Phase 11)
        rec = s.scalars(select(RevenueRecord).where(RevenueRecord.kind == "RECOGNITION").order_by(RevenueRecord.id)).first()
        run = s.get(SettlementRun, w.state["run"])
        po = s.get(Payout, w.state["payout"])
        link = s.scalars(select(SettlementRevenueItem).where(SettlementRevenueItem.settlement_run_id == run.id)).first()
        item = s.get(OrderItem, w.orders["A"]["item"])
    assert rec is not None and run is not None and po is not None and link is not None and item is not None
    _refused(w, "UPDATE dbo.revenue_records SET amount = 1 WHERE id = :i", {"i": rec.id}, "append-only")
    _refused(w, "DELETE FROM dbo.revenue_records WHERE id = :i", {"i": rec.id}, "append-only|REFERENCE constraint")
    _refused(w, "UPDATE dbo.farmer_entitlements SET amount = amount + 1", {}, "append-only")
    _refused(w, "UPDATE dbo.payout_transactions SET amount = 1", {}, "append-only")
    _refused(w, "UPDATE dbo.payout_reconciliations SET result = 'EXCEPTION'", {}, "append-only")
    _refused(w, "UPDATE dbo.farm_allocation_lines SET share_pct = 1", {}, "append-only")
    _refused(w, "UPDATE dbo.revenue_share_versions SET farmer_share_pct = 99 WHERE id = :i", {"i": w.share_id}, "values frozen")
    _refused(w, "UPDATE dbo.revenue_share_versions SET status = 'DRAFT' WHERE id = :i", {"i": w.share_id}, "only become SUPERSEDED")
    _refused(w, "DELETE FROM dbo.revenue_share_versions WHERE id = :i", {"i": w.share_id}, "never deleted|REFERENCE constraint")
    _refused(w, "UPDATE dbo.farm_allocation_versions SET basis_reference = 'x' WHERE id = :i", {"i": w.alloc_id}, "values frozen")
    _refused(w, "UPDATE dbo.settlement_runs SET farmer_total = 1 WHERE id = :i", {"i": run.id}, "frozen once calculated")
    _refused(w, "UPDATE dbo.settlement_runs SET input_snapshot = '{}' WHERE id = :i", {"i": run.id}, "frozen once calculated")
    _refused(w, "UPDATE dbo.settlement_runs SET status = 'APPROVED' WHERE id = :i", {"i": run.id}, "are final")
    _refused(w, "UPDATE dbo.settlement_revenue_items SET amount = 1 WHERE id = :i", {"i": link.id}, "are fixed")
    with w.engine.connect() as c:                                                                 # 1 → 0 is allowed, 0 → 1 never
        t = c.begin()
        try:
            c.execute(text("UPDATE dbo.settlement_revenue_items SET active = 0 WHERE id = :i"), {"i": link.id})
            with pytest.raises(DBAPIError) as e:
                c.execute(text("UPDATE dbo.settlement_revenue_items SET active = 1 WHERE id = :i"), {"i": link.id})
            assert "never re-activated" in str(e.value)
        finally:
            if t.is_active:
                t.rollback()
    _refused(w, "UPDATE dbo.payouts SET amount = 1 WHERE id = :i", {"i": po.id}, "are fixed|amount_positive")
    _refused(w, "UPDATE dbo.payouts SET amount = amount + 1 WHERE id = :i", {"i": po.id}, "are fixed")
    _refused(w, "UPDATE dbo.payouts SET external_reference = 'X' WHERE id = :i", {"i": po.id}, "frozen once PAID|are final")
    _refused(w, "UPDATE dbo.payouts SET status = 'PAID' WHERE id = :i", {"i": po.id}, "are final")
    _refused(w, "DELETE FROM dbo.payouts WHERE id = :i", {"i": po.id}, "never deleted|REFERENCE constraint")
    _refused(w, "UPDATE dbo.payouts SET approved_by = calculated_by WHERE id = :i", {"i": po.id}, "approval_sod|are final|frozen")
    _refused(w, "UPDATE dbo.revenue_records SET kind = 'REVERSAL'", {}, "append-only|kind_shape")
    _refused(w, "UPDATE dbo.farm_allocation_versions SET status = 'IN_REVIEW' WHERE id = :i", {"i": w.alloc_id}, "only become SUPERSEDED")
    with Session(bind=w.engine) as s:
        paid = s.scalars(select(Payout).where(Payout.status == "PAYMENT_PENDING")).first()
    if paid is not None:
        _refused(w, "UPDATE dbo.payouts SET status = 'PAID' WHERE id = :i", {"i": paid.id}, "paid_evidence")       # PAID needs reference
    _allowed(w, "UPDATE dbo.settlement_revenue_items SET active = 0 WHERE id = :i", {"i": link.id})   # 1 → 0 only (rolled back)
    invariants(w)


def test_10_verify_restore_and_tamper_detection_on_the_finance_world(world: World) -> None:
    """Phase 12B-III D27: on the committed Phase 9B-11 world (ledger batches, settlement runs, payouts), verify-restore passes; a real
    COPY_ONLY backup restored into a scratch database verifies with identical row counts; tampering with the scratch copy is detected."""
    from app.ops import sqlserver as sq
    from app.ops.verify_restore import verify_restore
    live = verify_restore(get_settings().SQL_SERVER_DATABASE)
    checks = {c["name"]: c for c in live.checks}
    assert live.ok, [c for c in live.checks if not c["ok"]]
    assert checks["ledger_conservation"]["detail"]["batches_checked"] >= 1
    assert checks["settlement_reproducibility"]["detail"]["runs_checked"] >= 1
    scratch = f"{get_settings().SQL_SERVER_DATABASE}_finance{sq.SCRATCH_SUFFIX}"
    eng = sq.master_engine()
    b = sq.backup(get_settings().SQL_SERVER_DATABASE, "full", copy_only=True, verify=True)
    try:
        sq.restore_to_scratch(eng, b.destination, scratch)
        restored = verify_restore(scratch, compare_with=get_settings().SQL_SERVER_DATABASE)
        assert restored.ok, [c for c in restored.checks if not c["ok"]]
        teng = sq.database_engine(scratch)
        try:
            with teng.connect() as c:                                     # tamper with the SCRATCH copy only
                assert c.execute(text("SELECT DB_NAME()")).scalar() == scratch
                c.execute(text("DISABLE TRIGGER trg_settlement_runs_guard ON dbo.settlement_runs"))
                c.execute(text("UPDATE dbo.settlement_runs SET farmer_total = farmer_total + 1 WHERE input_snapshot IS NOT NULL"))
        finally:
            teng.dispose()
        bad = {c["name"]: c for c in verify_restore(scratch).checks}
        assert not bad["triggers_enabled"]["ok"] and "trg_settlement_runs_guard" in bad["triggers_enabled"]["detail"]["disabled"]
        assert not bad["settlement_reproducibility"]["ok"]
    finally:
        sq.drop_scratch(eng, scratch)
        sq.delete_backup_file(eng, b.destination)
        assert not sq.exists(eng, scratch)
        eng.dispose()
