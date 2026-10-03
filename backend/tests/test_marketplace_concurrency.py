"""Phase 10 — REAL concurrency (D26 scenarios A–I) and direct-SQL trigger tests for the marketplace.

As for Phase 9B, concurrency needs committed data visible to several connections, so this module:
  1. takes a SQL Server database snapshot of the test database,
  2. builds the TEST-only issuance → 9B ledger → listings / verified buyers chain with real commits,
  3. races marketplace operations from separate threads, each with its own Session / connection,
  4. reverts the test database from the snapshot and drops the snapshot — nothing is left behind.
Every scenario asserts: no double spend, no negative inventory, batch conservation, no orphan reservation or transfer, no duplicated payment,
transfer or refund effect, and a consistent order / payment / credit state.
"""
import threading
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
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
    CreditBatch,
    CreditLedgerEntry,
    CreditPosition,
    CreditReservation,
    CreditTransfer,
    MarketplaceListing,
    Order,
    OrderItem,
    Payment,
    PaymentEvent,
    Refund,
    User,
)
from app.models.base import utcnow
from app.schemas.marketplace import OrderIn, OrderItemIn
from app.security.principal import load_principal
from app.services import ledger_service as ls
from app.services import marketplace_service as ms
from app.services import order_service as os_
from app.services import payment_service as ps
from tests.calc_fixture import calc_scenario
from tests.conftest import Actor, login, make_org, make_user
from tests.payment_fixture import TestPaymentAdapter
from tests.phase2 import staff
from tests.test_ledger import L
from tests.test_registry import PDF

SNAP = "carbon_platform_test_snap10"
RANGES = {"A": 100, "B": 100, "C": 300, "D": 200, "E": 200, "F": 200, "G": 200, "H": 200, "I": 200, "X": 100}


@dataclass
class World:
    engine: Engine
    batch_id: uuid.UUID
    issued: Decimal
    seller: uuid.UUID
    buyers: list[uuid.UUID]
    buyer_users: list[uuid.UUID]
    cm: uuid.UUID
    fin: uuid.UUID
    fin2: uuid.UUID
    qa: uuid.UUID
    listings: dict[str, uuid.UUID]


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
            k = calc_scenario(session, client, 84.10, 29.10, "9610 2000 3000")
            lg = L(client, session, k, ranges=[(f"P{n}-0001", f"P{n}-{q:04d}", q) for n, q in RANGES.items()])
            lg.open()
            fin, fin2 = staff(session, client, lg.org, "FINANCE_MANAGER"), staff(session, client, lg.org, "FINANCE_MANAGER")
            cu = make_user(session, roles=[("MARKETPLACE_COMPLIANCE", None)])
            comp = Actor(cu, login(client, cu))
            buyers, buyer_users = [], []
            for _ in range(2):
                bo = make_org(session, org_type="BUYER")
                b = staff(session, client, bo, "BUYER")
                session.commit()
                h = b.headers
                assert client.post("/api/v1/marketplace/buyer-profile", headers=h, json={"legal_name": "TEST Buyer"}).status_code == 200
                assert client.post("/api/v1/marketplace/buyer-profile/documents", headers=h,
                                   files={"file": ("k.pdf", PDF, "application/pdf")}).status_code == 201
                pid = client.post("/api/v1/marketplace/buyer-profile/submit-kyc", headers=h, json={}).json()["id"]
                assert client.post(f"/api/v1/marketplace/buyer-profiles/{pid}/verify", headers=comp.headers, json={}).json()["status"] == "KYC_VERIFIED"
                buyers.append(bo.id)
                buyer_users.append(b.user.id)
            pos = client.get(f"/api/v1/credits/batches/{lg.batch['id']}/positions", headers=lg.qa.headers).json()
            ranges = {p["registry_range"][1]: p["serial_range_id"] for p in pos}
            listings = {}
            for name, q in RANGES.items():
                body = {"seller_organization_id": str(lg.org.id), "batch_id": lg.batch["id"], "serial_range_id": ranges[name],
                        "title": f"TEST {name}", "listed_quantity": q, "unit_price": "10.00", "currency": "INR", "payment_window_hours": 24}
                lst = client.post("/api/v1/marketplace/listings", headers=lg.cm.headers, json=body).json()
                client.post(f"/api/v1/marketplace/listings/{lst['id']}/submit", headers=lg.cm.headers, json={})
                a = client.post(f"/api/v1/marketplace/listings/{lst['id']}/approve", headers=fin.headers, json={})
                assert a.json()["status"] == "ACTIVE", a.text
                listings[name] = uuid.UUID(lst["id"])
            session.commit()
            batch = session.get(CreditBatch, uuid.UUID(lg.batch["id"]))
            assert batch is not None
            yield World(engine, batch.id, batch.quantity, lg.org.id, buyers, buyer_users, lg.cm.user.id, fin.user.id, fin2.user.id, lg.qa.user.id,
                        listings)
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
    barrier = threading.Barrier(len(ops))
    results: list[tuple[str, Any]] = [("", None)] * len(ops)

    def worker(i: int, user_id: uuid.UUID, op: Op) -> None:
        s = Session(bind=w.engine, expire_on_commit=False, autoflush=False)
        try:
            user = s.get(User, user_id)
            assert user is not None
            principal = load_principal(s, user, None)
            ctx = RequestContext(request_id=f"race10-{i}", user_id=user_id)
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
    """Sequential setup step on its own committed connection."""
    with Session(bind=w.engine, expire_on_commit=False, autoflush=False) as s:
        user = s.get(User, user_id)
        assert user is not None
        return op(s, RequestContext(request_id=f"setup-{uuid.uuid4().hex[:6]}", user_id=user_id), load_principal(s, user, None))


def place(w: World, buyer: int, listing: str, qty: int) -> Op:
    data = OrderIn(buyer_organization_id=w.buyers[buyer], items=[OrderItemIn(listing_id=w.listings[listing], quantity=qty)])
    return lambda s, ctx, p: os_.place(s, ctx, p, data, None).id


def pay_manual(w: World, order_id: uuid.UUID, buyer: int = 0) -> uuid.UUID:
    def op(s: Session, ctx: RequestContext, p: Any) -> uuid.UUID:
        o = s.get(Order, order_id)
        assert o is not None
        doc = os_.upload_document(s, ctx, p, order_id, "e.pdf", PDF, None)

        class D:
            order_id, amount, currency, external_reference, document_id, note = o.id, o.total, o.currency, None, doc.id, None
        return ps.record_manual(s, ctx, p, D, None).id
    return uuid.UUID(str(run_as(w, w.buyer_users[buyer], op)))


def transfer_pending(w: World, listing: str, qty: int) -> uuid.UUID:
    order_id = run_as(w, w.buyer_users[0], place(w, 0, listing, qty))
    pid = pay_manual(w, order_id)
    run_as(w, w.fin, lambda s, ctx, p: ps.confirm(s, ctx, p, pid, None))
    return uuid.UUID(str(order_id))


def invariants(w: World) -> None:
    """No double spend, no negative inventory, conservation, no orphan reservation / transfer, no duplicate payment effect."""
    with Session(bind=w.engine) as s:
        total = s.scalar(select(func.sum(CreditPosition.quantity)).where(CreditPosition.batch_id == w.batch_id, CreditPosition.status == "OPEN"))
        assert Decimal(total) == w.issued                                                     # batch conservation (9B)
        assert s.scalar(select(func.count()).select_from(CreditPosition).where(CreditPosition.quantity <= 0)) == 0
        assert s.scalar(select(func.count()).select_from(CreditLedgerEntry).where(CreditLedgerEntry.posted == False)) == 0  # noqa: E712
        # every ACTIVE order reservation belongs to a RESERVED item of a PLACED order (and vice versa for live items)
        for r in s.scalars(select(CreditReservation).where(CreditReservation.purpose == os_.PURPOSE, CreditReservation.status == "ACTIVE")).all():
            it = s.scalars(select(OrderItem).where(OrderItem.reservation_id == r.id)).first()
            assert it is not None and it.status in ("RESERVED", "FAILED"), r.reservation_code
            assert s.get(Order, it.order_id).status in ("PLACED", "ATTENTION_REQUIRED", "REFUND_PENDING"), r.reservation_code
        # every REQUESTED order transfer is the current transfer of a TRANSFER_PENDING item; no item has two live transfers
        for t in s.scalars(select(CreditTransfer).where(CreditTransfer.purpose == os_.PURPOSE, CreditTransfer.status == "REQUESTED")).all():
            it = s.scalars(select(OrderItem).where(OrderItem.transfer_id == t.id)).first()
            assert it is not None and it.status == "TRANSFER_PENDING", t.transfer_code
        live = s.execute(select(CreditTransfer.purpose_reference, func.count()).where(CreditTransfer.purpose == os_.PURPOSE,
                                                                                         CreditTransfer.status.in_(("REQUESTED", "COMPLETED")))
                         .group_by(CreditTransfer.purpose_reference)).all()
        assert all(n == 1 for _, n in live), live
        # a listing is never over-committed (derived, no stored balance)
        for lst in s.scalars(select(MarketplaceListing)).all():
            assert ms.committed(s, lst.id) <= lst.listed_quantity, lst.listing_code
        # one confirmed payment per order at most; at most one open / completed refund per payment
        assert all(n <= 1 for (n,) in s.execute(select(func.count()).select_from(Payment).where(Payment.status.in_(("CONFIRMED", "REFUNDED")))
                                                 .group_by(Payment.order_id)))
        assert all(n <= 1 for (n,) in s.execute(select(func.count()).select_from(Refund).where(Refund.status != "REJECTED")
                                                 .group_by(Refund.payment_id)))


def _one_ok(results: list[tuple[str, Any]], *codes: str) -> None:
    kinds = sorted(r[0] for r in results)
    assert kinds == ["err", "ok"], results
    assert next(r[1] for r in results if r[0] == "err") in codes, results


# ---------------------------------------------------------------- A. two buyers × 100 against a 100-credit listing
def test_a_two_buyers_whole_listing(world: World) -> None:
    w = world
    r = race(w, (w.buyer_users[0], place(w, 0, "A", 100)), (w.buyer_users[1], place(w, 1, "A", 100)))
    _one_ok(r, "LISTING_QUANTITY_EXCEEDED", "INSUFFICIENT_AVAILABLE")
    with Session(bind=w.engine) as s:
        assert s.scalar(select(func.count()).select_from(Order).join(OrderItem, OrderItem.order_id == Order.id)
                        .where(OrderItem.listing_id == w.listings["A"])) == 1
    invariants(w)


# ---------------------------------------------------------------- B. 60 + 60 against 100
def test_b_sixty_plus_sixty(world: World) -> None:
    w = world
    _one_ok(race(w, (w.buyer_users[0], place(w, 0, "B", 60)), (w.buyer_users[1], place(w, 1, "B", 60))),
            "LISTING_QUANTITY_EXCEEDED", "INSUFFICIENT_AVAILABLE")
    with Session(bind=w.engine) as s:
        assert ms.committed(s, w.listings["B"]) == 60
    invariants(w)


# ---------------------------------------------------------------- C. two simultaneous orders that both fit — no lost update
def test_c_two_orders_one_listing(world: World) -> None:
    w = world
    r = race(w, (w.buyer_users[0], place(w, 0, "C", 120)), (w.buyer_users[1], place(w, 1, "C", 130)))
    assert [k for k, _ in r] == ["ok", "ok"], r
    with Session(bind=w.engine) as s:
        lst = s.get(MarketplaceListing, w.listings["C"])
        assert lst is not None and ms.committed(s, lst.id) == 250 and ms.remaining(s, lst) == 50
        assert s.scalar(select(func.count()).select_from(CreditReservation).where(CreditReservation.purpose == os_.PURPOSE,
                                                                                    CreditReservation.status == "ACTIVE",
                                                                                    CreditReservation.serial_range_id == lst.serial_range_id)) == 2
    invariants(w)


# ---------------------------------------------------------------- D. payment confirmation races reservation expiry
def test_d_confirmation_races_expiry(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    w = world
    order_id = run_as(w, w.buyer_users[0], place(w, 0, "D", 50))
    pid = pay_manual(w, order_id)
    later = utcnow() + timedelta(hours=25)                           # the reservation is now due
    for mod in (ms, os_, ps, ls):
        monkeypatch.setattr(mod, "utcnow", lambda: later)
    with Session(bind=w.engine) as s:
        batch_id = s.get(CreditBatch, w.batch_id).id
    r = race(w, (w.fin, lambda s, ctx, p: ps.confirm(s, ctx, p, pid, None).status),
             (w.cm, lambda s, ctx, p: ls.expire_due(s, ctx, batch_ids=[batch_id])))
    assert all(k == "ok" for k, _ in r), r
    with Session(bind=w.engine) as s:
        o = s.get(Order, order_id)
        it = s.scalars(select(OrderItem).where(OrderItem.order_id == order_id)).one()
        res = s.get(CreditReservation, it.reservation_id)
        assert s.get(Payment, pid).status == "CONFIRMED"
        assert o.status == "ATTENTION_REQUIRED" and it.status == "FAILED" and it.transfer_id is None and res.status == "EXPIRED"
        assert s.scalar(select(func.count()).select_from(CreditLedgerEntry).where(CreditLedgerEntry.reservation_id == res.id,
                                                                                     CreditLedgerEntry.entry_type == "RESERVATION_EXPIRE")) == 1
    monkeypatch.undo()
    invariants(w)


# ---------------------------------------------------------------- E. the same provider event delivered twice at once
def test_e_duplicate_payment_event(world: World) -> None:
    w = world
    adapter = TestPaymentAdapter()
    order_id = run_as(w, w.buyer_users[0], place(w, 0, "E", 40))
    pay = run_as(w, w.buyer_users[0], lambda s, ctx, p: ps.start_provider_payment(s, ctx, p, order_id, adapter))
    raw = adapter.event("EV-RACE-1", pay.external_reference, "SUCCEEDED")
    r = race(w, (w.fin, lambda s, ctx, p: ps.ingest_event(s, ctx, adapter, raw)), (w.fin2, lambda s, ctx, p: ps.ingest_event(s, ctx, adapter, raw)))
    assert sorted(v for _, v in r) == ["APPLIED", "DUPLICATE"], r
    with Session(bind=w.engine) as s:
        assert s.scalar(select(func.count()).select_from(PaymentEvent).where(PaymentEvent.external_event_id == "EV-RACE-1")) == 1
        assert s.get(Payment, pay.id).status == "PENDING_CONFIRMATION"
    invariants(w)


# ---------------------------------------------------------------- F. a payment event arrives while the order is being cancelled
def test_f_event_after_cancellation(world: World) -> None:
    w = world
    adapter = TestPaymentAdapter()
    order_id = run_as(w, w.buyer_users[0], place(w, 0, "F", 30))
    pay = run_as(w, w.buyer_users[0], lambda s, ctx, p: ps.start_provider_payment(s, ctx, p, order_id, adapter))
    raw = adapter.event("EV-RACE-F", pay.external_reference, "SUCCEEDED")
    r = race(w, (w.buyer_users[0], lambda s, ctx, p: os_.cancel(s, ctx, p, order_id, "TEST: abandoned", None).status),
             (w.fin, lambda s, ctx, p: ps.ingest_event(s, ctx, adapter, raw)))
    with Session(bind=w.engine) as s:
        o, p = s.get(Order, order_id), s.get(Payment, pay.id)
        if r[0] == ("ok", "CANCELLED"):                              # cancelled first: the money is UNMATCHED (refund required)
            assert o.status == "CANCELLED" and p.status == "UNMATCHED" and r[1] == ("ok", "UNMATCHED"), r
        else:                                                        # the event first: the payment holds the order; cancel refused
            assert r[0] == ("err", "PAYMENT_IN_PROGRESS") and o.status == "PLACED" and p.status == "PENDING_CONFIRMATION", r
    invariants(w)


# ---------------------------------------------------------------- G. two users cancel the same order
def test_g_double_cancellation(world: World) -> None:
    w = world
    order_id = run_as(w, w.buyer_users[0], place(w, 0, "G", 70))
    r = race(w, (w.buyer_users[0], lambda s, ctx, p: os_.cancel(s, ctx, p, order_id, "TEST: buyer", None).status),
             (w.cm, lambda s, ctx, p: os_.cancel(s, ctx, p, order_id, "TEST: seller", None).status))
    _one_ok(r, "ORDER_NOT_CANCELLABLE")
    with Session(bind=w.engine) as s:
        it = s.scalars(select(OrderItem).where(OrderItem.order_id == order_id)).one()
        assert s.get(Order, order_id).status == "CANCELLED" and it.status == "RELEASED"
        assert s.scalar(select(func.count()).select_from(CreditLedgerEntry).where(CreditLedgerEntry.reservation_id == it.reservation_id,
                                                                                     CreditLedgerEntry.entry_type == "RESERVATION_RELEASE")) == 1
    invariants(w)


# ---------------------------------------------------------------- H. refund request races the delivery (transfer completion)
def test_h_refund_races_transfer_completion(world: World) -> None:
    w = world
    order_id = transfer_pending(w, "H", 60)
    with Session(bind=w.engine) as s:
        it = s.scalars(select(OrderItem).where(OrderItem.order_id == order_id)).one()
        tid, pid = it.transfer_id, s.scalars(select(Payment.id).where(Payment.order_id == order_id, Payment.status == "CONFIRMED")).one()
    r = race(w, (w.qa, lambda s, ctx, p: os_.complete_transfer(s, ctx, p, tid, None, None).status),
             (w.fin, lambda s, ctx, p: ps.request_refund(s, ctx, p, pid, "TEST: refund race", None).after_transfer))
    assert r[0] == ("ok", "COMPLETED"), r                            # delivery always succeeds — a refund never blocks or reverses credits
    with Session(bind=w.engine) as s:
        assert s.get(Order, order_id).status == "COMPLETED"
        assert s.scalar(select(func.sum(CreditPosition.quantity)).where(CreditPosition.owner_organization_id == w.buyers[0],
                                                                         CreditPosition.status == "OPEN", CreditPosition.state == "AVAILABLE")) >= 60
        refund = s.scalars(select(Refund).where(Refund.payment_id == pid)).first()
        if r[1][0] == "ok":
            assert r[1][1] is True and refund is not None and refund.after_transfer   # completion won: money-only remediation
        else:
            assert r[1] == ("err", "REFUND_NOT_ALLOWED") and refund is None, r        # refund first: deliveries in flight
    invariants(w)


# ---------------------------------------------------------------- I. a delivery fails while the seller resolves the order
def test_i_transfer_failure_during_resolution(world: World) -> None:
    w = world
    order_id = transfer_pending(w, "I", 80)
    with Session(bind=w.engine) as s:
        tid = s.scalars(select(OrderItem.transfer_id).where(OrderItem.order_id == order_id)).one()
    r = race(w, (w.qa, lambda s, ctx, p: os_.reject_transfer(s, ctx, p, tid, "TEST: rejected", None).status),
             (w.cm, lambda s, ctx, p: os_.retry_transfer(s, ctx, p, order_id, "TEST: resolve", None).status))
    assert r[0][0] == "ok", r
    with Session(bind=w.engine) as s:
        o = s.get(Order, order_id)
        it = s.scalars(select(OrderItem).where(OrderItem.order_id == order_id)).one()
        cur = s.get(CreditTransfer, it.transfer_id)
        if r[1][0] == "ok":                                          # rejected first, then resolved: a fresh transfer is pending
            assert o.status == "TRANSFER_PENDING" and it.status == "TRANSFER_PENDING" and cur.status == "REQUESTED" and cur.id != tid
        else:                                                        # resolution first (nothing to resolve), then the rejection
            assert r[1] == ("err", "ORDER_NOT_IN_ATTENTION") and o.status == "ATTENTION_REQUIRED" and it.status == "FAILED"
            assert cur.status == "REJECTED"
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


def test_marketplace_triggers(world: World) -> None:
    w = world
    order_id = run_as(w, w.buyer_users[1], place(w, 1, "X", 10))
    run_as(w, w.buyer_users[1], lambda s, ctx, p: os_.cancel(s, ctx, p, order_id, "TEST: trigger fixture", None))
    paid = run_as(w, w.buyer_users[1], place(w, 1, "X", 20))                       # a refund row: paid → delivery rejected → refund
    pid = pay_manual(w, paid, buyer=1)
    run_as(w, w.fin, lambda s, ctx, p: ps.confirm(s, ctx, p, pid, None))
    with Session(bind=w.engine) as s:
        tid = s.scalars(select(OrderItem.transfer_id).where(OrderItem.order_id == paid)).one()
    run_as(w, w.qa, lambda s, ctx, p: os_.reject_transfer(s, ctx, p, tid, "TEST: trigger fixture", None))
    run_as(w, w.fin, lambda s, ctx, p: ps.request_refund(s, ctx, p, pid, "TEST: trigger fixture", None))
    with Session(bind=w.engine) as s:
        lst = s.get(MarketplaceListing, w.listings["X"])
        it = s.scalars(select(OrderItem).where(OrderItem.order_id == order_id)).one()
        ev = s.scalars(select(PaymentEvent)).first()
    assert lst is not None and ev is not None
    _refused(w, "UPDATE dbo.marketplace_listings SET unit_price = 1 WHERE id = :i", {"i": lst.id}, "frozen once approved")
    _refused(w, "UPDATE dbo.marketplace_listings SET listed_quantity = 1000 WHERE id = :i", {"i": lst.id}, "frozen once approved")
    _refused(w, "DELETE FROM dbo.marketplace_listings WHERE id = :i", {"i": lst.id}, "never deleted|REFERENCE constraint")
    _refused(w, "UPDATE dbo.order_items SET quantity = 1, line_total = unit_price WHERE id = :i", {"i": it.id}, "price and quantity are immutable")
    _refused(w, "UPDATE dbo.order_items SET unit_price = 1, line_total = quantity WHERE id = :i", {"i": it.id}, "price and quantity are immutable")
    _refused(w, "UPDATE dbo.orders SET status = 'PLACED' WHERE id = :i", {"i": order_id}, "are final")
    _refused(w, "UPDATE dbo.orders SET total = 1, subtotal = 1 WHERE id = :i", {"i": order_id}, "are fixed")
    _refused(w, "UPDATE dbo.payment_events SET outcome = 'APPLIED' WHERE id = :i", {"i": ev.id}, "append-only")
    _refused(w, "DELETE FROM dbo.payment_events WHERE id = :i", {"i": ev.id}, "append-only")
    _refused(w, "UPDATE dbo.buyer_kyc_reviews SET note = 'x'", {}, "append-only")
    _refused(w, "UPDATE dbo.payments SET amount = 1", {}, "amount are fixed")
    _refused(w, "UPDATE dbo.refunds SET amount = 1", {}, "amount are fixed")
    _refused(w, "UPDATE dbo.listing_documents SET published_by = published_by", {}, "append-only")
    invariants(w)
