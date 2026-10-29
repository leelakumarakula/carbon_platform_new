"""Integrity fixes (2026-10-14 review) for money and credits:

- C1 issued ≤ verified across concurrently confirmed tranches (SQL Server lock hint on the registry submission);
- C2 an order-linked (paid) delivery is reversed only after the order's payment was refunded after the delivery;
- C3 an UNCONFIRMED / provider-pending payout is FAILED only by the provider's answer or with bank evidence (no double payout on reissue);
- C4 cost corrections stay in the cost's currency and never take it below zero;
- C5 an Idempotency-Key never returns another organization's (or caller's) record: 409 IDEMPOTENCY_KEY_REUSED.

Functional tests run inside the rolled-back test database; the C1 race runs on separate connections against a committed world restored
from a database snapshot (same pattern as tests/test_ledger_concurrency.py)."""
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.dialects import mssql
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.context import RequestContext
from app.core.database import get_db, get_engine
from app.core.rate_limit import limiter
from app.main import create_app
from app.models import CreditIssuance, CreditLedgerEntry, Payout, PayoutTransaction
from app.security.principal import load_principal
from app.services import credit_issuance as ci
from app.services import ledger_service as ls
from app.services import payout_service as pys
from tests.calc_fixture import calc_scenario
from tests.conftest import make_org
from tests.payout_fixture import TestPayoutAdapter
from tests.phase2 import staff
from tests.test_finance import F
from tests.test_ledger import L
from tests.test_ledger_concurrency import race
from tests.test_marketplace import MP, ORD, PAY, M
from tests.test_registry import Reg, codes

C = "/api/v1/credits"


# ---------------------------------------------------------------- C1 issued ≤ verified under concurrent confirmations
def test_confirmation_lock_renders_the_sql_server_hint() -> None:
    sql = str(ci.lock_submission_stmt(uuid.uuid4()).compile(dialect=mssql.dialect()))
    assert "FROM registry_submissions WITH (UPDLOCK, HOLDLOCK, ROWLOCK)" in sql, sql


@dataclass
class IssuanceWorld:
    engine: Engine
    qa1: uuid.UUID
    qa2: uuid.UUID
    tranche_a: uuid.UUID
    tranche_b: uuid.UUID
    decision_id: uuid.UUID


@pytest.fixture(scope="module")
def issuance_world() -> Iterator[IssuanceWorld]:
    """A committed world: one ACCEPTED submission (VVB-verified 1000 tCO2e) with two RECORDED 600-credit tranches and two QA officers
    (registry.confirm), none of them the recorder. Restored from a database snapshot afterwards."""
    db_name = get_settings().SQL_SERVER_DATABASE
    assert db_name.endswith("_test")
    snap = f"{db_name}_snap_fixmoney"
    engine = get_engine()
    engine.dispose()
    master = create_engine(get_settings().database_url("master"), isolation_level="AUTOCOMMIT")
    with master.connect() as m:
        logical, physical = m.execute(text("SELECT name, physical_name FROM sys.master_files WHERE database_id = DB_ID(:d) AND type = 0"),
                                      {"d": db_name}).one()
        sparse = physical.rsplit("\\", 1)[0] + f"\\{snap}.ss"
        m.execute(text(f"CREATE DATABASE [{snap}] ON (NAME = [{logical}], FILENAME = '{sparse}') AS SNAPSHOT OF [{db_name}]"))
    session = Session(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        app = create_app()
        app.dependency_overrides[get_db] = lambda: session
        app.state.access_log_writer = lambda _r: None
        limiter.reset()
        with TestClient(app, base_url="http://testserver") as client:
            k = calc_scenario(session, client, 84.50, 29.50, "9950 2000 3000")
            reg = Reg(client, session, k)                                   # VVB-verified 1000 tCO2e
            sid = reg.accepted("TEST-SUB-RACE")["id"]
            a = reg.issue(sid, 600, "TEST-ISS-RACE-A")
            b = reg.issue(sid, 600, "TEST-ISS-RACE-B")                      # each fits alone; together they exceed the verified 1000
            assert a.status_code == 201 and b.status_code == 201, (a.text, b.text)
            qa2 = staff(session, client, reg.org, "QA_OFFICER")
            session.commit()
            yield IssuanceWorld(engine, reg.qa.user.id, qa2.user.id, uuid.UUID(a.json()["id"]), uuid.UUID(b.json()["id"]),
                                uuid.UUID(reg.decision["id"]))
    finally:
        session.close()
        limiter.reset()
        engine.dispose()
        with master.connect() as m:
            m.execute(text(f"ALTER DATABASE [{db_name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE"))
            try:
                m.execute(text(f"RESTORE DATABASE [{db_name}] FROM DATABASE_SNAPSHOT = '{snap}'"))
            finally:
                m.execute(text(f"ALTER DATABASE [{db_name}] SET MULTI_USER"))
            m.execute(text(f"DROP DATABASE [{snap}]"))
        master.dispose()
        engine.dispose()


def test_concurrent_tranche_confirmations_never_exceed_the_verified_quantity(issuance_world: IssuanceWorld,
                                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    w = issuance_world
    real = ci.confirmed_total

    def slow_total(db: Session, decision_id: uuid.UUID, exclude: tuple[uuid.UUID | None, ...] = ()) -> Decimal:
        total = real(db, decision_id, exclude)
        time.sleep(0.5)                                             # widen the read → write window: without the lock both read 0
        return total
    monkeypatch.setattr(ci, "confirmed_total", slow_total)

    def confirm(issuance_id: uuid.UUID) -> Any:
        return lambda s, ctx, p: ci.confirm(s, ctx, p, issuance_id, "TEST: checked against the registry statement").status
    results = race(w, (w.qa1, confirm(w.tranche_a)), (w.qa2, confirm(w.tranche_b)))   # type: ignore[arg-type]
    assert sorted(r[0] for r in results) == ["err", "ok"], results
    assert next(r[1] for r in results if r[0] == "err") == "QUANTITY_EXCEEDS_VERIFIED", results
    with Session(bind=w.engine) as s:
        assert real(s, w.decision_id) == Decimal(600)
        assert sorted(s.scalars(select(CreditIssuance.status).where(CreditIssuance.id.in_((w.tranche_a, w.tranche_b)))).all()) == [
            "CONFIRMED", "RECORDED"]


# ---------------------------------------------------------------- C2 order-linked delivery reversal needs a completed refund
def _completion_entry(db: Session, transfer_id: str) -> CreditLedgerEntry:
    return db.scalars(select(CreditLedgerEntry).where(CreditLedgerEntry.transfer_id == uuid.UUID(transfer_id),
                                                      CreditLedgerEntry.entry_type == "TRANSFER_COMPLETE")).one()


def test_paid_delivery_is_reversed_only_after_the_refund(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    m = M(client, db, 83.51, 28.51, "9851 2000 3000")
    m.verify_buyer()
    lst = m.listing(300, "12.50", rng=m.range600)
    od = m.purchase(lst["id"], 100)
    tr = od["items"][0]["transfer_id"]
    assert m.post(f"{ORD}/transfers/{tr}/complete", {}, m.qa).json()["status"] == "COMPLETED"
    assert m.holdings() == {"AVAILABLE": 100}
    entry = _completion_entry(db, tr)
    # the seller's credit manager cannot take the paid-for credits back
    r = m.lg.post(f"/entries/{entry.id}/reverse", {"reason": "TEST: seller takes the credits back"})
    assert r.status_code == 409 and codes(r) == "ORDER_LINKED" and r.json()["details"]["order_code"] == od["order_code"], r.text
    # a reversal requested before this guard existed cannot be applied either — but it can still be rejected
    with monkeypatch.context() as mp:
        mp.setattr(ls, "guard_reversal", lambda _db, _t: None)
        legacy = m.lg.post(f"/entries/{entry.id}/reverse", {"reason": "TEST: requested before the fix"})
    assert legacy.status_code == 201, legacy.text
    assert codes(m.lg.post(f"/reversals/{legacy.json()['id']}/apply", {"note": "TEST"}, who=m.qa)) == "ORDER_LINKED"
    assert m.lg.post(f"/reversals/{legacy.json()['id']}/reject", {"note": "TEST: paid delivery"}, who=m.qa).json()["status"] == "REJECTED"
    assert m.holdings() == {"AVAILABLE": 100}
    # a refund that is only requested / approved is not enough
    pay_id = m.get(f"{ORD}/{od['id']}", m.fin).json()["payments"][0]["id"]
    rf = m.post(f"{PAY}/{pay_id}/refunds", {"reason": "TEST: refund after delivery"}, m.fin).json()
    assert rf["after_transfer"] is True
    assert m.post(f"/api/v1/refunds/{rf['id']}/approve", {}, m.fin2).json()["status"] == "APPROVED"
    assert codes(m.lg.post(f"/entries/{entry.id}/reverse", {"reason": "TEST"})) == "ORDER_LINKED"
    ev = m.upload(f"/api/v1/refunds/{rf['id']}/documents", m.fin).json()["document_id"]
    assert m.post(f"/api/v1/refunds/{rf['id']}/complete", {"external_reference": "TEST-RF-FX", "document_id": ev}, m.fin).json()["status"] == \
        "COMPLETED"
    # money back to the buyer → the credits may come back to the seller (9B dual control, untouched outputs)
    v = m.lg.post(f"/entries/{entry.id}/reverse", {"reason": "TEST: refunded order, credits returned"})
    assert v.status_code == 201 and v.json()["status"] == "REQUESTED", v.text
    applied = m.lg.post(f"/reversals/{v.json()['id']}/apply", {"note": "TEST: refund completed"}, who=m.qa)
    assert applied.json()["status"] == "APPLIED", applied.text
    assert m.holdings() == {} and m.available(m.seller.id) == 1000


def test_unlinked_internal_transfer_reversal_is_unchanged(client: TestClient, db: Session) -> None:
    k = calc_scenario(db, client, 83.52, 28.52, "9852 2000 3000")
    lg = L(client, db, k)
    lg.open()
    buyer = make_org(db, org_type="BUYER")
    t = lg.transfer(50, buyer.id).json()
    done = lg.post(f"/transfers/{t['id']}/complete", who=lg.qa).json()
    v = lg.post(f"/entries/{done['completion_entry_id']}/reverse", {"reason": "TEST: wrong recipient"})
    assert v.status_code == 201, v.text
    assert lg.post(f"/reversals/{v.json()['id']}/apply", {"note": "TEST"}, who=lg.qa).json()["status"] == "APPLIED"


# ---------------------------------------------------------------- C3 no manual FAILED on an unknown provider outcome
def _approved_payout(f: F, share: dict, alloc: dict) -> dict:
    run = f.run(share, alloc)
    po = f.post(f"/payouts/from-settlement/{run['id']}", {}, f.fin2).json()[0]
    return _approve(f, po)


def _approve(f: F, po: dict) -> dict:
    assert f.post(f"/payouts/{po['id']}/submit", {}, f.fin2).status_code == 200
    a = f.post(f"/payouts/{po['id']}/approve", {}, f.fin3)
    assert a.status_code == 200, a.text
    return dict(a.json())


def test_unconfirmed_payout_fails_only_on_provider_answer_or_bank_evidence(client: TestClient, db: Session) -> None:
    f = F(client, db, 83.53, 28.53, "9853 2000 3000")
    f.sale(10, "10.00")
    share, alloc = f.share("100", deduct=False, rounding="DOWN"), f.allocation(["50", "50"])
    run = f.run(share, alloc)
    po = f.post(f"/payouts/from-settlement/{run['id']}", {}, f.fin2).json()[0]
    f.bank(uuid.UUID(po["farmer_id"]), "7777 8888 9999")
    _approve(f, po)
    adapter = TestPayoutAdapter()
    p4, ctx = load_principal(db, f.fin4.user, None), RequestContext(user_id=f.fin4.user.id)
    adapter.timeout_next = True
    x = pys.initiate(db, ctx, p4, uuid.UUID(po["id"]), None, adapter=adapter)
    assert x.status == "UNCONFIRMED"
    # a person's word alone does not fail it (the provider may still pay) — so it cannot be reissued
    r = f.post(f"/payouts/{po['id']}/fail", {"reason": "TEST: farmer says nothing arrived"}, f.fin4)
    assert r.status_code == 409 and codes(r) == "PAYOUT_FAILURE_EVIDENCE_REQUIRED", r.text
    assert codes(f.post(f"/payouts/{po['id']}/reissue", {}, f.fin2)) == "PAYOUT_NOT_FAILED"
    # 1. the provider's own answer fails it
    adapter.settle(f"TPYT-{x.payout_code}", "FAILED")
    assert pys.query_status(db, ctx, p4, x.id, adapter=adapter).status == "FAILED"
    re1 = f.post(f"/payouts/{po['id']}/reissue", {}, f.fin2)
    assert re1.status_code == 201, re1.text
    # 2. bank evidence attached to the payout fails it
    p2 = _approve(f, re1.json())
    adapter.timeout_next = True
    assert pys.initiate(db, ctx, p4, uuid.UUID(p2["id"]), None, adapter=adapter).status == "UNCONFIRMED"
    assert codes(f.post(f"/payouts/{p2['id']}/fail", {"reason": "TEST"}, f.fin4)) == "PAYOUT_FAILURE_EVIDENCE_REQUIRED"
    ev = f.doc(f"/payouts/{p2['id']}/documents", f.fin4, "PAYOUT_EVIDENCE")
    # evidence already on the payout is not enough: it may be a remittance proof — the failure names its evidence explicitly
    assert codes(f.post(f"/payouts/{p2['id']}/fail", {"reason": "TEST: unnamed"}, f.fin4)) == "PAYOUT_FAILURE_EVIDENCE_REQUIRED"
    failed = f.post(f"/payouts/{p2['id']}/fail", {"reason": "TEST: bank return advice attached", "document_id": ev}, f.fin4)
    assert failed.status_code == 200 and failed.json()["status"] == "FAILED", failed.text
    tx = db.scalars(select(PayoutTransaction).where(PayoutTransaction.payout_id == uuid.UUID(p2["id"]), PayoutTransaction.kind == "FAILED")).one()
    assert tx.evidence_document_id == uuid.UUID(ev)
    # 3. a payout a provider accepted (PAYMENT_PENDING at the provider) is not failed by hand either
    p3 = _approve(f, f.post(f"/payouts/{p2['id']}/reissue", {}, f.fin2).json())
    assert pys.initiate(db, ctx, p4, uuid.UUID(p3["id"]), None, adapter=adapter).status == "PAYMENT_PENDING"
    assert codes(f.post(f"/payouts/{p3['id']}/fail", {"reason": "TEST"}, f.fin4)) == "PAYOUT_FAILURE_EVIDENCE_REQUIRED"
    assert db.get(Payout, uuid.UUID(p3["id"])).status == "PAYMENT_PENDING"


# ---------------------------------------------------------------- C4 cost corrections
def test_cost_corrections_keep_the_currency_and_never_go_below_zero(client: TestClient, db: Session) -> None:
    f = F(client, db, 83.54, 28.54, "9854 2000 3000")
    c = f.cost("100.00")

    def correct(amount: str, currency: str = "INR", target: str | None = None) -> Any:
        return f.post("/costs", {"project_id": f.project_id, "category": "FIELD_OPERATIONS", "description": "TEST correction", "amount": amount,
                                 "currency": currency, "incurred_on": "2026-09-20", "corrects_cost_id": target or c["id"]}, f.pm)
    assert codes(correct("-10.00", "USD")) == "CORRECTION_CURRENCY_MISMATCH"
    assert codes(correct("-100.01")) == "CORRECTION_EXCEEDS_COST"
    c1 = correct("-60.00")
    assert c1.status_code == 201, c1.text
    assert codes(correct("-40.01")) == "CORRECTION_EXCEEDS_COST"            # a pending correction counts
    c2 = correct("-40.00")                                                   # exactly back to zero
    assert c2.status_code == 201, c2.text
    assert codes(correct("-0.01")) == "CORRECTION_EXCEEDS_COST"
    assert f.post(f"/costs/{c2.json()['id']}/reject", {"reason": "TEST: duplicate"}, f.fin).json()["status"] == "REJECTED"
    assert correct("-15.00").status_code == 201                              # a rejected correction frees its room
    f.doc(f"/costs/{c1.json()['id']}/documents", f.pm)
    assert f.post(f"/costs/{c1.json()['id']}/approve", {}, f.fin).json()["status"] == "APPROVED"
    assert codes(correct("-1.00", target=c1.json()["id"])) == "CORRECTION_TARGET_REQUIRED"   # a correction is not itself corrected


# ---------------------------------------------------------------- C5 Idempotency-Key replay never crosses organizations
def test_ledger_replay_is_scoped_to_the_caller(client: TestClient, db: Session) -> None:
    k = calc_scenario(db, client, 83.55, 28.55, "9855 2000 3000")
    lg = L(client, db, k)
    lg.open()
    other = make_org(db)
    cm_b = staff(db, client, other, "CREDIT_MANAGER")
    cm_a2 = staff(db, client, lg.org, "CREDIT_MANAGER")
    r1 = lg.reserve(10, key="fx-res-1")
    assert r1.status_code == 201, r1.text
    assert lg.reserve(10, key="fx-res-1").json()["id"] == r1.json()["id"]                       # the caller's own retry replays
    for owner in (other.id, lg.org.id):                                                        # another organization: never A's record
        r = lg.reserve(10, owner=owner, who=cm_b, key="fx-res-1")
        assert r.status_code == 409 and codes(r) == "IDEMPOTENCY_KEY_REUSED" and r1.json()["reservation_code"] not in r.text, r.text
    buyer = make_org(db, org_type="BUYER")
    body = {"kind": "INTERNAL", "batch_id": lg.batch["id"], "sender_organization_id": str(lg.org.id), "recipient_organization_id": str(buyer.id),
            "quantity": 5}
    t1 = lg.post("/transfers", body, key="fx-tr-1")
    assert t1.status_code == 201 and lg.post("/transfers", body, key="fx-tr-1").json()["id"] == t1.json()["id"]
    assert codes(lg.post("/transfers", body, who=cm_b, key="fx-tr-1")) == "IDEMPOTENCY_KEY_REUSED"
    assert codes(lg.post("/transfers", {**body, "quantity": 5, "recipient_organization_id": str(other.id)}, key="fx-tr-1")) == \
        "IDEMPOTENCY_KEY_REUSED"                                                                # same key, another request
    done = lg.post(f"/transfers/{t1.json()['id']}/complete", who=lg.qa).json()
    v = lg.post(f"/entries/{done['completion_entry_id']}/reverse", {"reason": "TEST"}, key="fx-rv-1")
    assert v.status_code == 201 and lg.post(f"/entries/{done['completion_entry_id']}/reverse", {"reason": "TEST"}, key="fx-rv-1").json()["id"] == \
        v.json()["id"]
    assert codes(lg.post(f"/entries/{done['completion_entry_id']}/reverse", {"reason": "TEST"}, who=cm_a2, key="fx-rv-1")) == \
        "IDEMPOTENCY_KEY_REUSED"


def test_order_payment_and_listing_replay_is_scoped_to_the_caller(client: TestClient, db: Session) -> None:
    m = M(client, db, 83.56, 28.56, "9856 2000 3000")
    m.verify_buyer()
    lst = m.listing(300, "12.50", rng=m.range600)
    o1 = m.order([(lst["id"], 10)], key="fx-ord-1")
    assert o1.status_code == 201, o1.text
    assert m.order([(lst["id"], 10)], key="fx-ord-1").json()["id"] == o1.json()["id"]          # the buyer's own retry replays
    org2 = make_org(db, org_type="BUYER")
    buyer2 = staff(db, client, org2, "BUYER")
    for claimed in (m.buyer_org.id, org2.id):          # the body's buyer organization is caller-controlled: it never unlocks the record
        r = m.order([(lst["id"], 10)], who=buyer2, key="fx-ord-1", buyer=claimed)
        assert r.status_code == 409 and codes(r) == "IDEMPOTENCY_KEY_REUSED" and o1.json()["order_code"] not in r.text, r.text
    p1 = m.pay(o1.json(), key="fx-pay-1")
    assert p1.status_code == 201, p1.text
    r = m.post(PAY, {"order_id": o1.json()["id"], "amount": o1.json()["total"], "currency": "INR", "external_reference": "X",
                     "document_id": str(uuid.uuid4())}, buyer2, key="fx-pay-1")
    assert r.status_code == 409 and codes(r) == "IDEMPOTENCY_KEY_REUSED" and p1.json()["payment_code"] not in r.text, r.text
    body = {"seller_organization_id": str(m.seller.id), "batch_id": m.lg.batch["id"], "title": "TEST", "listed_quantity": 10,
            "unit_price": "1.00", "currency": "INR", "payment_window_hours": 24}
    l1 = m.post(f"{MP}/listings", body, m.cm, key="fx-lst-1")
    assert l1.status_code == 201 and m.post(f"{MP}/listings", body, m.cm, key="fx-lst-1").json()["id"] == l1.json()["id"]
    seller2 = make_org(db)
    cm2 = staff(db, client, seller2, "CREDIT_MANAGER")
    r = m.post(f"{MP}/listings", {**body, "seller_organization_id": str(seller2.id)}, cm2, key="fx-lst-1")
    assert r.status_code == 409 and codes(r) == "IDEMPOTENCY_KEY_REUSED" and l1.json()["listing_code"] not in r.text, r.text
