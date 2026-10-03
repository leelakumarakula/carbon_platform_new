"""Phase 9B — REAL concurrency, fault injection and direct-SQL trigger tests.

Concurrency needs committed data visible to several connections, so this module:
  1. takes a SQL Server database snapshot of the test database (Developer edition),
  2. builds the TEST-only issuance → ledger chain with real commits,
  3. races operations from separate threads, each with its own Session / connection (never a shared savepoint session),
  4. reverts the test database from the snapshot and drops the snapshot — nothing is left behind.
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
from app.models import AuditLog, CreditBatch, CreditLedgerEntry, CreditPosition, CreditReservation, User
from app.models.base import utcnow
from app.schemas.ledger import ReservationIn, RetirementIn, TransferIn
from app.security.principal import load_principal
from app.services import ledger_service as ls
from tests.calc_fixture import calc_scenario
from tests.conftest import make_org
from tests.phase2 import staff
from tests.test_ledger import L

SNAP = "carbon_platform_test_snap9b"


@dataclass
class World:
    engine: Engine
    batch_id: uuid.UUID
    orgs: dict[str, uuid.UUID]
    managers: dict[str, uuid.UUID]
    buyer_org: uuid.UUID
    retired_position: uuid.UUID
    completed_transfer: uuid.UUID
    issued: Decimal


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
            k = calc_scenario(session, client, 82.10, 27.10, "9410 2000 3000")
            lg = L(client, session, k, ranges=[("CA-0001", "CA-1000", 1000), ("CB-0001", "CB-1000", 1000), ("CC-0001", "CC-0100", 100),
                                               ("CD-0001", "CD-0100", 100), ("CE-0001", "CE-0100", 100), ("CF-0001", "CF-0100", 100)])
            lg.open()
            ranges = {p["registry_range"][:2]: p["serial_range_id"]
                      for p in client.get(f"/api/v1/credits/batches/{lg.batch['id']}/positions", headers=lg.qa.headers).json()}
            orgs, managers, last = {}, {}, None
            for name in ("A", "B", "C", "D", "E"):
                org = make_org(session)
                cm = staff(session, client, org, "CREDIT_MANAGER")
                session.commit()
                t = lg.post("/transfers", {"kind": "INTERNAL", "batch_id": lg.batch["id"], "sender_organization_id": str(lg.org.id),
                                           "recipient_organization_id": str(org.id), "serial_range_id": ranges["C" + name],
                                           "quantity": 1000 if name in "AB" else 100})
                assert t.status_code == 201, t.text
                last = lg.post(f"/transfers/{t.json()['id']}/complete", who=lg.qa).json()
                orgs[name], managers[name] = org.id, cm.user.id
            buyer = make_org(session, org_type="BUYER")
            session.commit()
            r = lg.retire_req(10).json()                                  # a RETIRED position for the trigger tests (range CF)
            cert = lg.doc(f"/retirements/{r['id']}/documents")
            done = lg.post(f"/retirements/{r['id']}/retire", {"registry_retirement_reference": "TEST-RET-W", "retirement_date": "2026-10-03",
                                                              "document_id": cert}, who=lg.qa).json()
            assert done["status"] == "RETIRED", done
            retired = session.scalars(select(CreditPosition).where(CreditPosition.retirement_id == uuid.UUID(r["id"]),
                                                                   CreditPosition.state == "RETIRED")).one()
            session.commit()
            batch = session.get(CreditBatch, uuid.UUID(lg.batch["id"]))
            assert batch is not None and last is not None
            yield World(engine, batch.id, orgs, managers, buyer.id, retired.id, uuid.UUID(last["id"]), batch.quantity)
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


def race(w: World, *ops: tuple[uuid.UUID, Callable[[Session, RequestContext, Any], Any]]) -> list[tuple[str, Any]]:
    """Run each op in its own thread with its own Session (own connection), released together by a barrier."""
    barrier = threading.Barrier(len(ops))
    results: list[tuple[str, Any]] = [("", None)] * len(ops)

    def worker(i: int, user_id: uuid.UUID, op: Callable[[Session, RequestContext, Any], Any]) -> None:
        s = Session(bind=w.engine, expire_on_commit=False, autoflush=False)
        try:
            user = s.get(User, user_id)
            assert user is not None
            principal = load_principal(s, user, None)
            ctx = RequestContext(request_id=f"race-{i}", user_id=user_id)
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


def _check(w: World, owner: uuid.UUID, start: Decimal) -> dict[str, Decimal]:
    with Session(bind=w.engine) as s:
        total = s.scalar(select(func.sum(CreditPosition.quantity)).where(CreditPosition.batch_id == w.batch_id, CreditPosition.status == "OPEN"))
        assert Decimal(total) == w.issued                              # batch conservation
        assert s.scalar(select(func.count()).select_from(CreditPosition).where(CreditPosition.quantity <= 0)) == 0
        assert s.scalar(select(func.count()).select_from(CreditLedgerEntry).where(CreditLedgerEntry.posted == False)) == 0  # noqa: E712
        rows = s.execute(select(CreditPosition.state, func.sum(CreditPosition.quantity))
                         .where(CreditPosition.batch_id == w.batch_id, CreditPosition.owner_organization_id == owner, CreditPosition.status == "OPEN")
                         .group_by(CreditPosition.state)).all()
        by_state = {st: Decimal(q) for st, q in rows}
        assert sum(by_state.values(), Decimal(0)) == start              # the owner still holds exactly what it had (states differ)
        return by_state


def _outcome(results: list[tuple[str, Any]]) -> None:
    kinds = sorted(r[0] for r in results)
    assert kinds == ["err", "ok"], results
    assert next(r[1] for r in results if r[0] == "err") == "INSUFFICIENT_AVAILABLE", results


def _conflicts(w: World) -> int:
    with Session(bind=w.engine) as s:
        return int(s.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "CREDIT_DOUBLE_SPEND_CONFLICT")) or 0)


def _expiry() -> Any:
    return utcnow() + timedelta(hours=1)


# ---------------------------------------------------------------- A. two reservations 600 + 600 against 1000
def test_concurrent_reservations(world: World) -> None:
    w, before = world, _conflicts(world)

    def reserve(s: Session, ctx: RequestContext, p: Any) -> Any:
        return ls.create_reservation(s, ctx, p, ReservationIn(batch_id=w.batch_id, owner_organization_id=w.orgs["A"], quantity=600,
                                                              purpose="TEST race", expires_at=_expiry()), None).id
    results = race(w, (w.managers["A"], reserve), (w.managers["A"], reserve))
    _outcome(results)
    st = _check(w, w.orgs["A"], Decimal(1000))
    assert st == {"RESERVED": Decimal(600), "AVAILABLE": Decimal(400)}
    assert _conflicts(w) == before + 1


# ---------------------------------------------------------------- B. two transfers 600 + 600 against 1000
def test_concurrent_transfers(world: World) -> None:
    w = world

    def transfer(s: Session, ctx: RequestContext, p: Any) -> Any:
        return ls.request_transfer(s, ctx, p, TransferIn(kind="INTERNAL", batch_id=w.batch_id, sender_organization_id=w.orgs["B"],
                                                         recipient_organization_id=w.buyer_org, quantity=600), None).id
    _outcome(race(w, (w.managers["B"], transfer), (w.managers["B"], transfer)))
    assert _check(w, w.orgs["B"], Decimal(1000)) == {"TRANSFER_PENDING": Decimal(600), "AVAILABLE": Decimal(400)}


# ---------------------------------------------------------------- C. two retirements 80 + 80 against 100
def test_concurrent_retirements(world: World) -> None:
    w = world

    def retire(s: Session, ctx: RequestContext, p: Any) -> Any:
        return ls.request_retirement(s, ctx, p, RetirementIn(batch_id=w.batch_id, owner_organization_id=w.orgs["C"], quantity=80,
                                                             beneficiary="TEST", reason="TEST race"), None).id
    _outcome(race(w, (w.managers["C"], retire), (w.managers["C"], retire)))
    assert _check(w, w.orgs["C"], Decimal(100)) == {"RETIREMENT_PENDING": Decimal(80), "AVAILABLE": Decimal(20)}


# ---------------------------------------------------------------- D. a reservation racing a retirement for the same 80 of 100
def test_reservation_racing_retirement(world: World) -> None:
    w = world

    def reserve(s: Session, ctx: RequestContext, p: Any) -> Any:
        return ls.create_reservation(s, ctx, p, ReservationIn(batch_id=w.batch_id, owner_organization_id=w.orgs["D"], quantity=80,
                                                              purpose="TEST race", expires_at=_expiry()), None).id

    def retire(s: Session, ctx: RequestContext, p: Any) -> Any:
        return ls.request_retirement(s, ctx, p, RetirementIn(batch_id=w.batch_id, owner_organization_id=w.orgs["D"], quantity=80,
                                                             beneficiary="TEST", reason="TEST race"), None).id
    _outcome(race(w, (w.managers["D"], reserve), (w.managers["D"], retire)))
    st = _check(w, w.orgs["D"], Decimal(100))
    assert st.get("AVAILABLE") == Decimal(20) and (st.get("RESERVED", Decimal(0)) + st.get("RETIREMENT_PENDING", Decimal(0))) == Decimal(80)


# ---------------------------------------------------------------- E. fault injection between consumption and posting
def test_fault_between_consumption_and_posting_rolls_back(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    w = world
    with Session(bind=w.engine) as s:
        entries_before = s.scalar(select(func.count()).select_from(CreditLedgerEntry))
        reservations_before = s.scalar(select(func.count()).select_from(CreditReservation))

    def boom(entry: CreditLedgerEntry) -> None:
        raise RuntimeError("TEST fault after positions were consumed")
    monkeypatch.setattr(ls, "_before_post", boom)
    s = Session(bind=w.engine, expire_on_commit=False, autoflush=False)
    try:
        user = s.get(User, w.managers["E"])
        assert user is not None
        principal = load_principal(s, user, None)
        with pytest.raises(RuntimeError):
            ls.create_reservation(s, RequestContext(request_id="fault", user_id=user.id), principal,
                                  ReservationIn(batch_id=w.batch_id, owner_organization_id=w.orgs["E"], quantity=50, purpose="TEST fault",
                                                expires_at=_expiry()), None)
    finally:
        s.close()
    monkeypatch.undo()
    with Session(bind=w.engine) as s:
        assert s.scalar(select(func.count()).select_from(CreditLedgerEntry)) == entries_before        # no partial entry
        assert s.scalar(select(func.count()).select_from(CreditReservation)) == reservations_before
        open_e = s.scalars(select(CreditPosition).where(CreditPosition.owner_organization_id == w.orgs["E"], CreditPosition.status == "OPEN")).all()
        assert [(p.state, p.quantity) for p in open_e] == [("AVAILABLE", Decimal(100))]               # inventory unchanged, nothing orphaned
    _check(w, w.orgs["E"], Decimal(100))


# ---------------------------------------------------------------- database triggers (34–40)
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


def test_database_invariants(world: World) -> None:
    w = world
    with Session(bind=w.engine) as s:
        entry = s.scalars(select(CreditLedgerEntry).where(CreditLedgerEntry.batch_id == w.batch_id)).first()
        open_pos = s.scalars(select(CreditPosition).where(CreditPosition.owner_organization_id == w.orgs["E"], CreditPosition.status == "OPEN")).first()
        consumed = s.scalars(select(CreditPosition).where(CreditPosition.batch_id == w.batch_id, CreditPosition.status == "CONSUMED")).first()
        actor = s.scalars(select(User.id)).first()
        assert entry and open_pos and consumed and actor
        batch_org = entry.organization_id
    # 35 / 37. append-only ledger entries
    _refused(w, "UPDATE credit_ledger_entries SET reason = N'rewritten' WHERE id = :i", {"i": entry.id}, "append-only")
    _refused(w, "DELETE FROM credit_ledger_entries WHERE id = :i", {"i": entry.id}, "append-only|REFERENCE constraint")   # refused either way
    # 36 / 37. immutable positions, never deleted
    _refused(w, "UPDATE credit_positions SET quantity = quantity + 1 WHERE id = :i", {"i": open_pos.id}, "immutable")
    _refused(w, "UPDATE credit_positions SET owner_organization_id = :o WHERE id = :i", {"i": open_pos.id, "o": w.buyer_org}, "immutable")
    _refused(w, "DELETE FROM credit_positions WHERE id = :i", {"i": open_pos.id}, "never deleted")
    # 38. a consumed position is never reused
    _refused(w, "UPDATE credit_positions SET status = N'OPEN', consumed_by_entry_id = NULL WHERE id = :i", {"i": consumed.id}, "immutable")
    # 39. a RETIRED position is never consumed
    _refused(w, "UPDATE credit_positions SET status = N'CONSUMED', consumed_by_entry_id = :e WHERE id = :i",
             {"i": w.retired_position, "e": entry.id}, "retired_terminal")
    # 34. final states are frozen
    _refused(w, "UPDATE credit_transfers SET status = N'REQUESTED' WHERE id = :i", {"i": w.completed_transfer}, "final")
    _refused(w, "UPDATE credit_retirements SET retirement_date = '2020-01-01' WHERE status = N'RETIRED'", {}, "final")
    # 40. conservation: an unbalanced entry can never be posted (inputs != outputs / batch total)
    e_id = uuid.uuid4()
    with w.engine.connect() as c:
        t = c.begin()
        try:
            c.execute(text("INSERT INTO credit_ledger_entries (id, entry_code, entry_type, batch_id, organization_id, quantity, actor_id, posted, "
                           "created_at, environment) VALUES (:e, N'LEDG-TEST-X', N'RESERVE', :b, :o, 5, :a, 0, SYSUTCDATETIME(), N'LIVE')"),
                      {"e": e_id, "b": w.batch_id, "o": batch_org, "a": actor})
            c.execute(text("INSERT INTO credit_positions (id, batch_id, serial_range_id, owner_organization_id, holding_external_account_id, state, "
                           "status, quantity, created_by_entry_id, created_at, environment) SELECT NEWID(), batch_id, serial_range_id, "
                           "owner_organization_id, holding_external_account_id, N'AVAILABLE', N'OPEN', 5, :e, SYSUTCDATETIME(), N'LIVE' "
                           "FROM credit_positions WHERE id = :p"), {"e": e_id, "p": open_pos.id})
            with pytest.raises(DBAPIError) as err:
                c.execute(text("UPDATE credit_ledger_entries SET posted = 1 WHERE id = :e"), {"e": e_id})
            assert "conservation" in str(err.value)
        finally:
            if t.is_active:
                t.rollback()
    # positions can only be created inside an unposted entry
    _refused(w, """INSERT INTO credit_positions (id, batch_id, serial_range_id, owner_organization_id, holding_external_account_id, state, status,
                   quantity, created_by_entry_id, created_at, environment)
                   SELECT NEWID(), batch_id, serial_range_id, owner_organization_id, holding_external_account_id, N'AVAILABLE', N'OPEN', 1, :e,
                   SYSUTCDATETIME(), N'LIVE' FROM credit_positions WHERE id = :p""", {"e": entry.id, "p": open_pos.id}, "unposted")
    # the original 9A registry serial ranges are never modified
    _refused(w, "UPDATE credit_serial_ranges SET serial_start = N'CHANGED' WHERE id = :r", {"r": open_pos.serial_range_id}, "never change")
