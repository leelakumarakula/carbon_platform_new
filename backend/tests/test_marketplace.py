"""Phase 10 — marketplace: buyer KYC, listings, orders, payments, refunds and their Phase 9B integration. Functional, RBAC, isolation,
document, audit, lineage, DEMO / TEST / LIVE tests inside the rolled-back test database. Real cross-connection concurrency (A–I) and the
direct-SQL trigger tests are in tests/test_marketplace_concurrency.py.

Every purchase starts from a TEST-only registry issuance (Phase 7 fixture → 8B VVB decision → 9A manual registry flow) opened in the 9B
ledger; the TEST payment adapter (tests/payment_fixture.py) is injected into the service layer only."""
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.context import RequestContext
from app.core.errors import Conflict
from app.integrations.payment import ADAPTERS, ManualActionRequired, PaymentRequest
from app.models import (
    AuditLog,
    BuyerProfile,
    CreditPosition,
    CreditReservation,
    CreditTransfer,
    Document,
    Order,
    Payment,
    PaymentEvent,
    Permission,
    Role,
    RolePermission,
)
from app.models.base import Base, utcnow
from app.security.principal import load_principal
from app.services import ledger_service as ls
from app.services import marketplace_service as ms
from app.services import order_service as os_
from app.services import payment_service as ps
from tests.calc_fixture import calc_scenario
from tests.conftest import Actor, login, make_org, make_user
from tests.payment_fixture import TestPaymentAdapter
from tests.phase2 import PNG, staff
from tests.test_ledger import L, _conserved
from tests.test_registry import PDF, codes

MP, ORD, PAY, C = "/api/v1/marketplace", "/api/v1/orders", "/api/v1/payments", "/api/v1/credits"


class M:
    """A seller (PROJECT_DEVELOPER) holding 1000 registry-issued credits in the 9B ledger (ranges of 600 + 400), its credit manager (lists),
    two finance managers (approve listings, confirm payments, refunds), the custodian QA officer (completes deliveries), a BUYER
    organization with a buyer user and a platform compliance officer."""

    def __init__(self, client: TestClient, db: Session, lon: float, lat: float, idn: str) -> None:
        self.client, self.db = client, db
        self.k = calc_scenario(db, client, lon, lat, idn)
        self.lg = L(client, db, self.k)
        self.lg.open()
        self.seller, self.cm, self.qa = self.lg.org, self.lg.cm, self.lg.qa
        self.fin = staff(db, client, self.seller, "FINANCE_MANAGER")
        self.fin2 = staff(db, client, self.seller, "FINANCE_MANAGER")
        self.buyer_org = make_org(db, org_type="BUYER")
        self.buyer = staff(db, client, self.buyer_org, "BUYER")
        u = make_user(db, roles=[("MARKETPLACE_COMPLIANCE", None)])
        self.comp = Actor(u, login(client, u))
        pos = client.get(f"{C}/batches/{self.lg.batch['id']}/positions", headers=self.qa.headers).json()
        self.range600 = next(p["serial_range_id"] for p in pos if p["quantity"] == 600)
        self.range400 = next(p["serial_range_id"] for p in pos if p["quantity"] == 400)

    def post(self, url: str, body: dict | None = None, who: Actor | None = None, key: str | None = None) -> Any:
        h = {**(who or self.buyer).headers, **({"Idempotency-Key": key} if key else {})}
        return self.client.post(url, headers=h, json=body if body is not None else {})

    def get(self, url: str, who: Actor | None = None, **params: Any) -> Any:
        return self.client.get(url, headers=(who or self.buyer).headers, params=params)

    def upload(self, url: str, who: Actor | None = None, content: bytes = PDF) -> Any:
        return self.client.post(url, headers=(who or self.buyer).headers, files={"file": ("d.pdf", content, "application/pdf")})

    def verify_buyer(self, who: Actor | None = None) -> dict:
        who = who or self.buyer
        assert self.post(f"{MP}/buyer-profile", {"legal_name": "TEST Buyer Pvt Ltd", "country": "IN"}, who).status_code == 200
        assert self.upload(f"{MP}/buyer-profile/documents", who).status_code == 201
        s = self.post(f"{MP}/buyer-profile/submit-kyc", {}, who)
        assert s.status_code == 200, s.text
        v = self.post(f"{MP}/buyer-profiles/{s.json()['id']}/verify", {}, self.comp)
        assert v.status_code == 200 and v.json()["status"] == "KYC_VERIFIED", v.text
        return v.json()

    def listing(self, qty: int = 500, price: str = "12.50", currency: str = "INR", approve: bool = True, rng: str | None = None,
                cm: Actor | None = None, fin: Actor | None = None, seller: Any = None, **kw: Any) -> dict:
        body = {"seller_organization_id": str(seller or self.seller.id), "batch_id": self.lg.batch["id"], "serial_range_id": rng,
                "title": "TEST rice-field credits", "listed_quantity": qty, "unit_price": price, "currency": currency,
                "payment_window_hours": 24, **kw}
        r = self.post(f"{MP}/listings", body, cm or self.cm)
        assert r.status_code == 201, r.text
        lst = r.json()
        if approve:
            assert self.post(f"{MP}/listings/{lst['id']}/submit", {}, cm or self.cm).status_code == 200
            a = self.post(f"{MP}/listings/{lst['id']}/approve", {}, fin or self.fin)
            assert a.status_code == 200, a.text
            lst = a.json()
        return lst

    def order(self, items: list[tuple[str, int]], who: Actor | None = None, key: str | None = None, buyer: Any = None, **kw: Any) -> Any:
        return self.post(ORD, {"buyer_organization_id": str(buyer or self.buyer_org.id), "items": [{"listing_id": i, "quantity": q} for i, q in items],
                             **kw}, who, key)

    def pay(self, order: dict, who: Actor | None = None, key: str | None = None, amount: str | None = None) -> Any:
        d = self.upload(f"{ORD}/{order['id']}/documents", who)
        assert d.status_code == 201, d.text
        return self.post(PAY, {"order_id": order["id"], "amount": amount or order["total"], "currency": order["currency"],
                               "external_reference": f"BANK-{uuid.uuid4().hex[:8]}", "document_id": d.json()["document_id"]}, who, key)

    def purchase(self, listing_id: str, qty: int) -> dict:
        """placed → paid (manual) → confirmed: returns the TRANSFER_PENDING order."""
        o = self.order([(listing_id, qty)])
        assert o.status_code == 201, o.text
        p = self.pay(o.json())
        assert p.status_code == 201, p.text
        c = self.post(f"{PAY}/{p.json()['id']}/confirm", {}, self.fin)
        assert c.status_code == 200, c.text
        return self.get(f"{ORD}/{o.json()['id']}").json()

    def available(self, owner: Any) -> int:
        return int(self.lg.balance(owner)["available"])

    def holdings(self, who: Actor | None = None) -> dict[str, int]:
        out: dict[str, int] = {}
        for h in self.get(f"{C}/holdings", who).json()["holdings"]:
            out[h["state"]] = out.get(h["state"], 0) + h["quantity"]
        return out


def _actions(db: Session, *actions: str) -> set[str]:
    return {a for (a,) in db.execute(select(AuditLog.action).where(AuditLog.action.in_(actions)))}


def _perms(db: Session, role: str) -> set[str]:
    return {c for (c,) in db.execute(select(Permission.code).join(RolePermission, RolePermission.permission_id == Permission.id)
                                     .join(Role, Role.id == RolePermission.role_id).where(Role.code == role))
            if c.split(".")[0] in ("marketplace", "listings", "orders", "payments", "refunds", "buyers")}


def _later(monkeypatch: pytest.MonkeyPatch, delta: timedelta) -> None:
    t = utcnow() + delta
    for mod in (ms, os_, ps, ls):
        monkeypatch.setattr(mod, "utcnow", lambda t=t: t)


# ---------------------------------------------------------------- 37 RBAC, 43 LIVE manual payment, 44 no provider without a contract
def test_rbac_matrix_payment_boundary_and_no_second_balance(db: Session) -> None:
    assert _perms(db, "BUYER") == {"marketplace.read", "orders.place", "orders.read", "payments.record", "buyers.kyc_submit"}
    assert _perms(db, "CREDIT_MANAGER") == {"marketplace.read", "listings.manage", "orders.read", "orders.manage"}
    assert _perms(db, "PROJECT_MANAGER") == {"marketplace.read", "orders.read"}
    assert _perms(db, "FINANCE_MANAGER") == {"marketplace.read", "listings.approve", "orders.read", "payments.confirm", "refunds.request",
                                             "refunds.approve"}
    assert _perms(db, "MARKETPLACE_COMPLIANCE") == {"buyers.kyc_verify"}
    for role in ("QA_OFFICER", "VVB_REVIEWER", "LAB_TECHNICIAN", "LAB_MANAGER", "FARMER", "METHODOLOGY_SPECIALIST", "REGISTRY_MANAGER"):
        assert _perms(db, role) == set(), role
    # 44: no payment provider without a contract — MANUAL is the only runtime adapter and never fakes a confirmation; no webhook / payout route
    assert set(ADAPTERS) == {"MANUAL"} and Settings.model_fields["PAYMENT_PROVIDER"].default == "manual"
    manual = ADAPTERS["MANUAL"]
    for call in (lambda: manual.create_payment(PaymentRequest("P", "O", Decimal(1), "INR", "k")), lambda: manual.get_status("x"),
                 lambda: manual.refund("x", Decimal(1), "INR", "k"), lambda: manual.parse_event(b"{}")):
        with pytest.raises(ManualActionRequired):
            call()
    from app.main import app
    paths = [getattr(r, "path", "") for r in app.routes]
    assert not any(w in p for p in paths for w in ("webhook", "payout", "checkout", "commission", "invoice"))
    # D24: no marketplace table stores a credit balance; carbon and money never share a column
    for t in ("marketplace_listings", "orders", "order_items", "payments", "refunds"):
        cols = {c.name for c in Base.metadata.tables[t].columns}
        assert not cols & {"available_quantity", "remaining_quantity", "owned_quantity", "sold_quantity", "balance"}, t
    assert {c.name for c in Base.metadata.tables["order_items"].columns} >= {"batch_id", "serial_range_id", "reservation_id", "transfer_id"}


# ---------------------------------------------------------------- 1–6 buyer profile & KYC, 38 restricted documents
def test_buyer_profile_kyc_lifecycle_sod_and_documents(client: TestClient, db: Session) -> None:
    m = M(client, db, 83.10, 28.10, "9510 2000 3000")
    view = m.get(f"{MP}/buyer-profile").json()
    assert view["profile"] is None and view["organization_id"] == str(m.buyer_org.id)
    p = m.post(f"{MP}/buyer-profile", {"legal_name": "TEST Buyer Pvt Ltd", "country": "in", "identifier_type": "COMPANY_ID",
                                       "identifier": "U12345MH2020PTC999999"})
    assert p.status_code == 200 and p.json()["status"] == "DRAFT" and p.json()["identifier_last4"] == "9999", p.text
    row = db.get(BuyerProfile, uuid.UUID(p.json()["id"]))
    assert row is not None and row.identifier_hash and "U12345" not in (row.identifier_hash or "")   # never stored in clear
    assert codes(m.post(f"{MP}/buyer-profile/submit-kyc")) == "KYC_DOCUMENT_REQUIRED"                 # document-driven, nothing invented
    assert codes(m.upload(f"{MP}/buyer-profile/documents", content=PNG)) == "UNSUPPORTED_FILE_TYPE"   # PDF only
    d = m.upload(f"{MP}/buyer-profile/documents")
    assert d.status_code == 201
    doc = db.get(Document, uuid.UUID(d.json()["document_id"]))
    assert doc is not None and doc.sensitivity == "RESTRICTED" and doc.category == "BUYER_KYC_DOCUMENT"
    s = m.post(f"{MP}/buyer-profile/submit-kyc", key="kyc-1")
    assert s.json()["status"] == "KYC_SUBMITTED"
    assert m.post(f"{MP}/buyer-profile/submit-kyc", key="kyc-1").json()["status"] == "KYC_SUBMITTED"     # replay
    assert codes(m.post(f"{MP}/buyer-profile", {"legal_name": "Changed"})) == "BUYER_PROFILE_LOCKED"
    pid = s.json()["id"]
    # restricted KYC documents: the buyer and the reviewer only
    assert m.get(f"/api/v1/evidence/documents/{doc.id}").status_code == 200
    assert m.get(f"/api/v1/evidence/documents/{doc.id}", m.comp).status_code == 200
    assert m.get(f"/api/v1/evidence/documents/{doc.id}", m.cm).status_code == 404
    other = staff(db, client, make_org(db, org_type="BUYER"), "BUYER")
    assert m.get(f"/api/v1/evidence/documents/{doc.id}", other).status_code == 404
    # 4: return (reason required) → resubmission
    assert m.post(f"{MP}/buyer-profiles/{pid}/return", {}, m.comp).status_code == 422
    r = m.post(f"{MP}/buyer-profiles/{pid}/return", {"reason": "TEST: legible registration document needed"}, m.comp)
    assert r.json()["status"] == "KYC_RETURNED" and r.json()["return_reason"].startswith("TEST")
    assert m.post(f"{MP}/buyer-profile", {"legal_name": "TEST Buyer Private Limited", "country": "IN"}).status_code == 200
    assert m.post(f"{MP}/buyer-profile/submit-kyc").json()["status"] == "KYC_SUBMITTED"
    # 6: SoD — a reviewer who submitted the KYC cannot verify it
    dual = make_user(db, roles=[("BUYER", m.buyer_org), ("MARKETPLACE_COMPLIANCE", None)])
    dual_a = Actor(dual, login(client, dual))
    assert m.post(f"{MP}/buyer-profile", {"legal_name": "TEST Buyer Private Limited"}, dual_a).status_code == 409   # locked (submitted)
    assert m.post(f"{MP}/buyer-profiles/{pid}/return", {"reason": "TEST: return again"}, m.comp).status_code == 200
    assert m.post(f"{MP}/buyer-profile/submit-kyc", {}, dual_a).json()["status"] == "KYC_SUBMITTED"
    assert codes(m.post(f"{MP}/buyer-profiles/{pid}/verify", {}, dual_a)) == "SEPARATION_OF_DUTIES"
    # 3: verification by someone else
    v = m.post(f"{MP}/buyer-profiles/{pid}/verify", {"note": "TEST documents checked"}, m.comp)
    assert v.json()["status"] == "KYC_VERIFIED" and v.json()["verified_by_name"]
    assert m.get(f"{MP}/buyer-profiles", m.buyer).status_code == 403                                   # the queue is platform-only
    assert any(x["id"] == pid for x in m.get(f"{MP}/buyer-profiles", m.comp, status="KYC_VERIFIED").json())
    # 5: suspension blocks new orders; reinstatement by a reviewer
    lst = m.listing(100)
    sp = m.post(f"{MP}/buyer-profiles/{pid}/suspend", {"reason": "TEST: compliance hold"}, m.comp)
    assert sp.json()["status"] == "SUSPENDED"
    assert codes(m.order([(lst["id"], 10)])) == "BUYER_KYC_REQUIRED"
    re = m.post(f"{MP}/buyer-profiles/{pid}/verify", {}, m.comp)
    assert re.json()["status"] == "KYC_VERIFIED" and re.json()["reviews"][-1]["action"] == "REINSTATED"
    assert m.order([(lst["id"], 10)]).status_code == 201
    assert _actions(db, "BUYER_PROFILE_CREATED", "BUYER_KYC_SUBMITTED", "BUYER_KYC_RETURNED", "BUYER_KYC_VERIFIED", "BUYER_SUSPENDED") == {
        "BUYER_PROFILE_CREATED", "BUYER_KYC_SUBMITTED", "BUYER_KYC_RETURNED", "BUYER_KYC_VERIFIED", "BUYER_SUSPENDED"}


# ---------------------------------------------------------------- 7–12 listings, 36 seller isolation
def test_listing_lifecycle_ownership_quantity_expiry_visibility(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    m = M(client, db, 83.11, 28.11, "9520 2000 3000")
    body = {"seller_organization_id": str(m.seller.id), "batch_id": m.lg.batch["id"], "title": "x", "listed_quantity": 10, "unit_price": "1.00",
            "currency": "INR", "payment_window_hours": 24}
    # 8: ownership — buyers cannot list (no resale); an organization without AVAILABLE credits cannot list
    assert m.post(f"{MP}/listings", body, m.buyer).status_code == 403
    reseller_cm = staff(db, client, m.buyer_org, "CREDIT_MANAGER")
    assert codes(m.post(f"{MP}/listings", {**body, "seller_organization_id": str(m.buyer_org.id)}, reseller_cm)) == "NOT_A_SELLER"
    dev2 = make_org(db)
    cm2 = staff(db, client, dev2, "CREDIT_MANAGER")
    assert codes(m.post(f"{MP}/listings", {**body, "seller_organization_id": str(dev2.id)}, cm2)) == "NO_AVAILABLE_CREDITS"
    assert m.post(f"{MP}/listings", body, cm2).status_code == 404                                     # someone else's organization
    # 9: quantity ≤ the seller's 9B AVAILABLE; money rules (D7, D8)
    assert codes(m.post(f"{MP}/listings", {**body, "listed_quantity": 1001}, m.cm)) == "LISTED_QUANTITY_EXCEEDS_AVAILABLE"
    assert codes(m.post(f"{MP}/listings", {**body, "currency": "XXX"}, m.cm)) == "UNSUPPORTED_CURRENCY"
    assert codes(m.post(f"{MP}/listings", {**body, "unit_price": "1.005"}, m.cm)) == "INVALID_AMOUNT"
    assert codes(m.post(f"{MP}/listings", {**body, "currency": "JPY", "unit_price": "100.5"}, m.cm)) == "INVALID_AMOUNT"
    assert m.post(f"{MP}/listings", {**body, "available_quantity": 5}, m.cm).status_code == 422          # no balance in a request
    # 7: lifecycle DRAFT → PENDING_APPROVAL → ACTIVE (never the creator) → PAUSED → ACTIVE → CLOSED
    d = m.listing(400, "12.50", approve=False, rng=m.range400, min_quantity=10, max_quantity=300, co_benefits="TEST: soil health")
    assert d["status"] == "DRAFT" and d["available_quantity"] == 0 and d["remaining_quantity"] == 400
    assert m.get(f"{MP}/listings/{d['id']}").status_code == 404                                       # buyers never see drafts
    assert m.upload(f"{MP}/listings/{d['id']}/documents", m.cm).status_code == 201
    assert m.post(f"{MP}/listings/{d['id']}/approve", {}, m.fin).status_code == 409                    # not submitted yet
    assert m.post(f"{MP}/listings/{d['id']}/submit", {}, m.cm, key="sub-1").json()["status"] == "PENDING_APPROVAL"
    assert m.post(f"{MP}/listings/{d['id']}/approve", {}, m.cm).status_code == 403                     # credit manager cannot approve
    dual = make_user(db, roles=[("CREDIT_MANAGER", m.seller), ("FINANCE_MANAGER", m.seller)])
    dual_a = Actor(dual, login(client, dual))
    own = m.listing(50, approve=False, cm=dual_a)
    assert m.post(f"{MP}/listings/{own['id']}/submit", {}, dual_a).status_code == 200
    assert codes(m.post(f"{MP}/listings/{own['id']}/approve", {}, dual_a)) == "SEPARATION_OF_DUTIES"
    assert m.post(f"{MP}/listings/{own['id']}/close", {"reason": "TEST: withdrawn"}, m.fin).json()["status"] == "CANCELLED"
    a = m.post(f"{MP}/listings/{d['id']}/approve", {}, m.fin).json()
    assert a["status"] == "ACTIVE" and a["disclosure_sha256"] and a["approved_by_name"]
    disc = a["disclosure"]
    assert disc["project_code"] and disc["vintage"] == "2026" and disc["verification_status"].startswith("VERIFIED")
    assert not any(w in str(disc).lower() for w in ("farmer", "gps", "kyc", "bank", "latitude", "polygon"))
    # 11: visibility — buyers see ACTIVE listings, allow-listed (no seller staff names)
    seen = m.get(f"{MP}/listings/{d['id']}").json()
    assert seen["available_quantity"] == 400 and seen["created_by_name"] is None and seen["seller_side"] is False
    assert seen["documents"] and m.get(f"/api/v1/evidence/documents/{seen['documents'][0]['document_id']}/download").status_code == 200
    assert any(x["id"] == d["id"] for x in m.get(f"{MP}/listings").json()["listings"])
    # D4: displayed availability = min(remaining, seller's 9B AVAILABLE) — a 9B reservation elsewhere lowers it, nothing is stored
    assert m.lg.reserve(150, serial_range_id=m.range400).status_code == 201
    assert m.get(f"{MP}/listings/{d['id']}").json()["available_quantity"] == 250
    # one ACTIVE / PAUSED listing per seller + batch + range
    dup = m.listing(10, approve=False, rng=m.range400)
    m.post(f"{MP}/listings/{dup['id']}/submit", {}, m.cm)
    assert codes(m.post(f"{MP}/listings/{dup['id']}/approve", {}, m.fin)) == "LISTING_EXISTS"
    # 12: price immutable once approved (no edit endpoint; pause / resume keep the terms)
    assert m.post(f"{MP}/listings/{d['id']}/pause", {}, m.cm).json()["status"] == "PAUSED"
    assert m.get(f"{MP}/listings/{d['id']}").status_code == 404
    r = m.post(f"{MP}/listings/{d['id']}/resume", {}, m.cm).json()
    assert r["status"] == "ACTIVE" and Decimal(r["unit_price"]) == Decimal("12.50") and r["disclosure_sha256"] == a["disclosure_sha256"]
    # 36: seller isolation — another seller sees ACTIVE listings only, never drafts or management actions
    assert m.get(f"{MP}/listings/{dup['id']}", cm2).status_code == 404
    assert m.get(f"{MP}/listings", cm2, mine=True).json()["listings"] == []
    assert m.post(f"{MP}/listings/{d['id']}/pause", {}, cm2).status_code == 403
    assert m.get(f"{MP}/listings", staff(db, client, make_org(db, org_type="VVB"), "VVB_REVIEWER")).status_code == 403
    # 10: lazy expiry (D5) — checked on read, no worker
    e = m.listing(20, valid_until=(utcnow() + timedelta(hours=2)).isoformat() + "Z")
    _later(monkeypatch, timedelta(hours=3))
    assert m.get(f"{MP}/listings/{e['id']}", m.cm).json()["status"] == "EXPIRED"
    assert m.get(f"{MP}/listings/{e['id']}").status_code == 404
    monkeypatch.undo()
    c = m.post(f"{MP}/listings/{d['id']}/close", {"reason": "TEST: sold elsewhere"}, m.cm)
    assert c.json()["status"] == "CLOSED"
    assert _actions(db, "MARKETPLACE_LISTING_CREATED", "MARKETPLACE_LISTING_SUBMITTED", "MARKETPLACE_LISTING_APPROVED", "MARKETPLACE_LISTING_PAUSED",
                    "MARKETPLACE_LISTING_CLOSED", "MARKETPLACE_LISTING_EXPIRED", "MARKETPLACE_LISTING_CANCELLED") == {
        "MARKETPLACE_LISTING_CREATED", "MARKETPLACE_LISTING_SUBMITTED", "MARKETPLACE_LISTING_APPROVED", "MARKETPLACE_LISTING_PAUSED",
        "MARKETPLACE_LISTING_CLOSED", "MARKETPLACE_LISTING_EXPIRED", "MARKETPLACE_LISTING_CANCELLED"}


# ---------------------------------------------------------------- 13–19 orders, KYC gate, reservations, rollback, 35 buyer isolation
def test_orders_kyc_gate_reservations_rollback_and_isolation(client: TestClient, db: Session) -> None:
    m = M(client, db, 83.12, 28.12, "9530 2000 3000")
    l1 = m.listing(300, "10.00", rng=m.range600, min_quantity=10)
    l2 = m.listing(200, "7.25", rng=m.range400)
    assert codes(m.order([(l1["id"], 50)])) == "BUYER_KYC_REQUIRED"                                    # 17
    m.verify_buyer()
    # 14: several items (same seller, same currency) — one 9B reservation per item, all in one transaction
    o = m.order([(l1["id"], 100), (l2["id"], 40)], key="ord-1")
    assert o.status_code == 201, o.text
    od = o.json()
    assert od["status"] == "PLACED" and Decimal(od["total"]) == Decimal("1290.00") and len(od["items"]) == 2
    assert all(i["status"] == "RESERVED" and i["reservation_status"] == "ACTIVE" for i in od["items"])
    assert m.order([(l1["id"], 100), (l2["id"], 40)], key="ord-1").json()["id"] == od["id"]          # idempotent replay
    res = db.scalars(select(CreditReservation).where(CreditReservation.purpose_reference.in_([i["item_code"] for i in od["items"]]))).all()
    assert len(res) == 2 and {r.recipient_organization_id for r in res} == {m.buyer_org.id}
    assert int(m.lg.balance(m.seller.id)["reserved"]) == 140 and m.available(m.seller.id) == 860
    assert m.get(f"{MP}/listings/{l1['id']}").json()["remaining_quantity"] == 200
    # 15 / 16: one seller, one currency per order
    l3 = m.listing(100, "3.00", "USD")
    assert codes(m.order([(l1["id"], 10), (l3["id"], 10)])) == "SINGLE_CURRENCY_REQUIRED"
    dev2 = make_org(db)
    assert m.lg.post("/transfers", {"kind": "INTERNAL", "batch_id": m.lg.batch["id"], "sender_organization_id": str(m.seller.id),
                                    "recipient_organization_id": str(dev2.id), "quantity": 50}).status_code == 201
    t = m.get(f"{C}/transfers", m.qa).json()[0]
    assert m.lg.post(f"/transfers/{t['id']}/complete", who=m.qa).status_code == 200
    l4 = m.listing(50, "10.00", seller=dev2.id, cm=staff(db, client, dev2, "CREDIT_MANAGER"), fin=staff(db, client, dev2, "FINANCE_MANAGER"))
    assert codes(m.order([(l1["id"], 10), (l4["id"], 10)])) == "SINGLE_SELLER_REQUIRED"
    assert codes(m.order([(l1["id"], 10), (l1["id"], 5)])) == "DUPLICATE_LISTING"
    assert codes(m.order([(l1["id"], 5)])) == "QUANTITY_OUT_OF_RANGE"
    assert codes(m.order([(l1["id"], 10)], transfer_kind="REGISTRY")) == "RECIPIENT_ACCOUNT_REQUIRED"
    assert m.order([(l1["id"], 10)], quantity_available=5).status_code == 422                       # no balance in a request
    # 19: rollback — a quantity beyond the listing, or beyond the seller's 9B AVAILABLE, leaves no order and no reservation at all
    before = (db.scalar(select(func.count()).select_from(Order)), db.scalar(select(func.count()).select_from(CreditReservation)))
    assert codes(m.order([(l1["id"], 50), (l2["id"], 161)])) == "LISTING_QUANTITY_EXCEEDED"
    assert m.lg.reserve(750).status_code == 201                                                     # 9B: the seller holds credits elsewhere
    assert codes(m.order([(l3["id"], 100)])) == "INSUFFICIENT_AVAILABLE"                            # 9B guarded consumption decides
    assert (db.scalar(select(func.count()).select_from(Order)), db.scalar(select(func.count()).select_from(CreditReservation))) == (
        before[0], before[1] + 1)                                                                   # only the explicit 9B reservation
    assert _actions(db, "CREDIT_DOUBLE_SPEND_CONFLICT") == {"CREDIT_DOUBLE_SPEND_CONFLICT"}
    _conserved(db, m.lg.batch["id"])
    # 18: the order owns its reservations — the public 9B actions refuse them
    rid = od["items"][0]
    r9 = next(r for r in m.get(f"{C}/reservations", m.cm).json() if r["reservation_code"] == rid["reservation_code"])
    assert r9["order_code"] == od["order_code"]
    assert codes(m.lg.post(f"/reservations/{r9['id']}/release", {"reason": "TEST"})) == "ORDER_LINKED"
    # 35: isolation — buyers see only their own orders; unrelated sellers / buyers get 404
    other = staff(db, client, make_org(db, org_type="BUYER"), "BUYER")
    assert m.get(f"{ORD}/{od['id']}", other).status_code == 404
    assert m.get(ORD, other).json()["orders"] == []
    assert m.get(f"{ORD}/{od['id']}", staff(db, client, dev2, "CREDIT_MANAGER")).status_code == 404
    seller_view = m.get(f"{ORD}/{od['id']}", m.cm).json()
    assert seller_view["viewer_side"] == "SELLER" and seller_view["buyer_name"]
    # 13: cancellation releases the reservations; final states are final
    c = m.post(f"{ORD}/{od['id']}/cancel", {"reason": "TEST: changed mind"}, key="cx-1")
    assert c.json()["status"] == "CANCELLED" and {i["status"] for i in c.json()["items"]} == {"RELEASED"}
    assert m.post(f"{ORD}/{od['id']}/cancel", {"reason": "TEST: again"}, key="cx-1").json()["status"] == "CANCELLED"   # replay
    assert codes(m.post(f"{ORD}/{od['id']}/cancel", {"reason": "TEST: again"})) == "ORDER_NOT_CANCELLABLE"
    assert int(m.lg.balance(m.seller.id)["reserved"]) == 750
    assert _actions(db, "ORDER_PLACED", "ORDER_CANCELLED", "CREDIT_RESERVATION_CREATED", "CREDIT_RESERVATION_RELEASED") == {
        "ORDER_PLACED", "ORDER_CANCELLED", "CREDIT_RESERVATION_CREATED", "CREDIT_RESERVATION_RELEASED"}


# ---------------------------------------------------------------- 20–23 payments, 27–29 transfer, 38–40, 42 complete TEST purchase lifecycle
def test_complete_purchase_lifecycle_manual_payment_transfer_lineage(client: TestClient, db: Session) -> None:
    m = M(client, db, 83.13, 28.13, "9540 2000 3000")
    m.verify_buyer()
    lst = m.listing(300, "12.50", rng=m.range600)
    o = m.order([(lst["id"], 100)]).json()
    assert Decimal(o["total"]) == Decimal("1250.00")
    # 20: manual recording — exact total, same currency, PDF evidence attached to the order
    assert codes(m.upload(f"{ORD}/{o['id']}/documents", content=PNG)) == "UNSUPPORTED_FILE_TYPE"
    assert codes(m.pay(o, amount="1000.00")) == "PAYMENT_AMOUNT_MISMATCH"                                # no partial payment
    p1 = m.pay(o, key="pay-1")
    assert p1.status_code == 201 and p1.json()["status"] == "PENDING_CONFIRMATION" and p1.json()["adapter_code"] == "MANUAL", p1.text
    assert m.pay(o, key="pay-1").json()["id"] == p1.json()["id"]                                       # 23: idempotent
    assert codes(m.pay(o)) == "PAYMENT_IN_PROGRESS"
    assert codes(m.post(f"{ORD}/{o['id']}/cancel", {"reason": "TEST"})) == "PAYMENT_IN_PROGRESS"
    assert m.get(f"{ORD}/{o['id']}").json()["status"] == "PLACED"                                        # no credit moved
    assert m.available(m.buyer_org.id) == 0
    # 22: rejection keeps the order PLACED (D18); the buyer pays again
    assert m.post(f"{PAY}/{p1.json()['id']}/confirm", {}, m.buyer).status_code == 403                  # buyers never confirm
    assert m.post(f"{PAY}/{p1.json()['id']}/reject", {"reason": "TEST: not received"}, m.fin).json()["status"] == "REJECTED"
    assert m.get(f"{ORD}/{o['id']}").json()["status"] == "PLACED"
    dual = make_user(db, roles=[("BUYER", m.buyer_org), ("FINANCE_MANAGER", m.seller)])
    dual_a = Actor(dual, login(client, dual))
    p2 = m.pay(o, who=dual_a).json()
    assert codes(m.post(f"{PAY}/{p2['id']}/confirm", {}, dual_a)) == "SEPARATION_OF_DUTIES"             # recorder ≠ confirmer
    # 21 / 27: confirmation consumes the reservation into a 9B transfer REQUEST (never completes it)
    c = m.post(f"{PAY}/{p2['id']}/confirm", {}, m.fin, key="conf-1")
    assert c.json()["status"] == "CONFIRMED", c.text
    assert m.post(f"{PAY}/{p2['id']}/confirm", {}, m.fin, key="conf-1").json()["status"] == "CONFIRMED"   # replay
    od = m.get(f"{ORD}/{o['id']}").json()
    item = od["items"][0]
    assert od["status"] == "TRANSFER_PENDING" and item["status"] == "TRANSFER_PENDING" and item["reservation_status"] == "CONSUMED"
    tr = db.get(CreditTransfer, uuid.UUID(item["transfer_id"]))
    assert tr is not None and tr.status == "REQUESTED" and tr.kind == "INTERNAL" and tr.requested_by == m.fin.user.id
    assert tr.purpose_reference == item["item_code"]
    # 28: completion only through the order wrapper, by the custodian's credits.confirm (never the requester)
    t9 = next(t for t in m.get(f"{C}/transfers", m.qa).json() if t["id"] == item["transfer_id"])
    assert t9["order_code"] == od["order_code"]
    assert codes(m.lg.post(f"/transfers/{tr.id}/complete", who=m.qa)) == "ORDER_LINKED"
    assert m.post(f"{ORD}/transfers/{tr.id}/complete", {}, m.fin).status_code == 403
    done = m.post(f"{ORD}/transfers/{tr.id}/complete", {}, m.qa, key="del-1")
    assert done.status_code == 200, done.text
    # 29: order, item, 9B transfer and the buyer's ownership changed together
    assert done.json()["status"] == "COMPLETED" and done.json()["items"][0]["status"] == "DELIVERED"
    assert m.post(f"{ORD}/transfers/{tr.id}/complete", {}, m.qa, key="del-1").json()["status"] == "COMPLETED"   # replay
    assert m.holdings() == {"AVAILABLE": 100}
    assert int(m.lg.balance(m.seller.id)["transferred_out"]) == 100
    _conserved(db, m.lg.batch["id"])
    # 38: deterministic order confirmation (not a tax invoice)
    c1 = m.post(f"{ORD}/{o['id']}/confirmation")
    c2 = m.post(f"{ORD}/{o['id']}/confirmation", {}, m.cm)
    assert c1.status_code == 200 and c1.json()["document_id"] == c2.json()["document_id"]
    pdf = m.get(f"/api/v1/evidence/documents/{c1.json()['document_id']}/download").content
    assert pdf.startswith(b"%PDF") and b"NOT a tax invoice" in pdf
    # 40: lineage order → item → listing → 9B reservation → 9B transfer → ledger entry → batch (buyers stop at the batch)
    lin = m.get(f"{ORD}/{o['id']}/lineage").json()["chain"]
    assert [x["kind"] for x in lin] == ["ORDER", "ORDER_ITEM", "LISTING", "CREDIT_RESERVATION", "CREDIT_TRANSFER", "LEDGER_ENTRY", "CREDIT_BATCH"]
    assert lin[5]["type"] == "TRANSFER_COMPLETE" and lin[-1]["batch_lineage"] is None
    assert m.get(f"{ORD}/{o['id']}/lineage", m.cm).json()["chain"][-1]["batch_lineage"].endswith("/lineage")
    # 42: optional retirement of the purchased credits through the existing 9B holder flow (custodian records the registry certificate)
    r = m.post(f"{C}/retirements", {"batch_id": m.lg.batch["id"], "owner_organization_id": str(m.buyer_org.id), "quantity": 40,
                                    "beneficiary": "TEST Buyer Pvt Ltd", "reason": "TEST: voluntary claim"})
    assert r.status_code == 201, r.text
    cert = m.lg.doc(f"/retirements/{r.json()['id']}/documents")
    rt = m.lg.post(f"/retirements/{r.json()['id']}/retire", {"registry_retirement_reference": "TEST-RET-P10", "retirement_date": "2026-10-03",
                                                              "document_id": cert}, who=m.qa)
    assert rt.json()["status"] == "RETIRED"
    assert m.holdings() == {"AVAILABLE": 60, "RETIRED": 40}
    assert _actions(db, "PAYMENT_RECORDED", "PAYMENT_REJECTED", "PAYMENT_CONFIRMED", "ORDER_PAID", "ORDER_COMPLETED", "CREDIT_TRANSFER_REQUESTED",
                    "CREDIT_TRANSFER_COMPLETED", "ORDER_CONFIRMATION_GENERATED") == {
        "PAYMENT_RECORDED", "PAYMENT_REJECTED", "PAYMENT_CONFIRMED", "ORDER_PAID", "ORDER_COMPLETED", "CREDIT_TRANSFER_REQUESTED",
        "CREDIT_TRANSFER_COMPLETED", "ORDER_CONFIRMATION_GENERATED"}
    # 39: cross-organization actions are audited in both organizations
    orgs = {o_ for (o_,) in db.execute(select(AuditLog.organization_id).where(AuditLog.action == "ORDER_COMPLETED"))}
    assert {m.buyer_org.id, m.seller.id} <= orgs


# ---------------------------------------------------------------- 30 transfer failure, 31–34 refunds
def test_transfer_failure_resolution_and_refunds(client: TestClient, db: Session) -> None:
    m = M(client, db, 83.14, 28.14, "9550 2000 3000")
    m.verify_buyer()
    lst = m.listing(600, "10.00", rng=m.range600)
    # 30: the custodian rejects the delivery → credits back to the seller, order ATTENTION_REQUIRED, no silent retry
    a = m.purchase(lst["id"], 100)
    ta = a["items"][0]["transfer_id"]
    rj = m.post(f"{ORD}/transfers/{ta}/reject", {"reason": "TEST: buyer account check pending"}, m.qa)
    assert rj.json()["status"] == "ATTENTION_REQUIRED" and rj.json()["items"][0]["status"] == "FAILED", rj.text
    assert m.available(m.seller.id) == 1000 and m.holdings() == {}
    assert m.post(f"{ORD}/{a['id']}/retry-transfer", {"reason": "TEST"}, m.buyer).status_code == 403
    rt = m.post(f"{ORD}/{a['id']}/retry-transfer", {"reason": "TEST: resolved"}, m.cm)
    assert rt.json()["status"] == "TRANSFER_PENDING", rt.text
    ta2 = rt.json()["items"][0]["transfer_id"]
    assert ta2 != ta and codes(m.post(f"{ORD}/{a['id']}/retry-transfer", {"reason": "TEST"}, m.cm)) == "ORDER_NOT_IN_ATTENTION"
    assert m.post(f"{ORD}/transfers/{ta2}/complete", {}, m.qa).json()["status"] == "COMPLETED"
    assert m.holdings() == {"AVAILABLE": 100}
    # 33: refund BEFORE delivery — dual control, evidence; the order is REFUNDED and the credits stay with the seller
    b = m.purchase(lst["id"], 50)
    assert codes(m.post(f"{PAY}/{b['payments'][0]['id']}/refunds", {"reason": "TEST"}, m.fin)) == "REFUND_NOT_ALLOWED"   # delivery in flight
    m.post(f"{ORD}/transfers/{b['items'][0]['transfer_id']}/reject", {"reason": "TEST: cannot deliver"}, m.qa)
    seller_before = m.available(m.seller.id)
    rf = m.post(f"{PAY}/{b['payments'][0]['id']}/refunds", {"reason": "TEST: buyer refund"}, m.fin, key="rf-1")
    assert rf.status_code == 201 and rf.json()["after_transfer"] is False, rf.text
    assert m.post(f"{PAY}/{b['payments'][0]['id']}/refunds", {"reason": "TEST: buyer refund"}, m.fin, key="rf-1").json()["id"] == rf.json()["id"]
    assert m.get(f"{ORD}/{b['id']}", m.cm).json()["status"] == "REFUND_PENDING"
    assert codes(m.post(f"/api/v1/refunds/{rf.json()['id']}/approve", {}, m.fin)) == "SEPARATION_OF_DUTIES"     # 32
    assert m.post(f"/api/v1/refunds/{rf.json()['id']}/approve", {}, m.fin2).json()["status"] == "APPROVED"
    assert codes(m.post(f"/api/v1/refunds/{rf.json()['id']}/complete", {"external_reference": "TEST-RF"}, m.fin)) == "REFUND_EVIDENCE_REQUIRED"
    ev = m.upload(f"/api/v1/refunds/{rf.json()['id']}/documents", m.fin).json()["document_id"]
    done = m.post(f"/api/v1/refunds/{rf.json()['id']}/complete", {"external_reference": "TEST-RF-1", "document_id": ev}, m.fin)
    assert done.json()["status"] == "COMPLETED", done.text
    ob = m.get(f"{ORD}/{b['id']}").json()
    assert ob["status"] == "REFUNDED" and ob["payments"][0]["status"] == "REFUNDED" and ob["items"][0]["status"] == "RELEASED"
    assert m.available(m.seller.id) == seller_before and m.holdings() == {"AVAILABLE": 100}         # no carbon moved by the refund
    # a rejected refund returns the order to attention
    c = m.purchase(lst["id"], 20)
    m.post(f"{ORD}/transfers/{c['items'][0]['transfer_id']}/reject", {"reason": "TEST"}, m.qa)
    rc = m.post(f"{PAY}/{c['payments'][0]['id']}/refunds", {"reason": "TEST"}, m.fin).json()
    assert m.post(f"/api/v1/refunds/{rc['id']}/reject", {"reason": "TEST: deliver instead"}, m.fin2).json()["status"] == "REJECTED"
    assert m.get(f"{ORD}/{c['id']}").json()["status"] == "ATTENTION_REQUIRED"
    # 34: refund AFTER delivery — money only; the credits stay with the buyer (no automatic reversal)
    rr = m.post(f"{PAY}/{a['payments'][-1]['id']}/refunds", {"reason": "TEST: goodwill refund after delivery"}, m.fin).json()
    assert rr["after_transfer"] is True
    m.post(f"/api/v1/refunds/{rr['id']}/approve", {}, m.fin2)
    ev2 = m.upload(f"/api/v1/refunds/{rr['id']}/documents", m.fin).json()["document_id"]
    assert m.post(f"/api/v1/refunds/{rr['id']}/complete", {"external_reference": "TEST-RF-2", "document_id": ev2}, m.fin).json()["status"] == "COMPLETED"
    assert m.get(f"{ORD}/{a['id']}").json()["status"] == "COMPLETED" and m.holdings() == {"AVAILABLE": 100}
    assert codes(m.post(f"{PAY}/{a['payments'][-1]['id']}/refunds", {"reason": "TEST: twice"}, m.fin)) == "REFUND_NOT_ALLOWED"
    _conserved(db, m.lg.batch["id"])
    assert _actions(db, "ORDER_ATTENTION_REQUIRED", "REFUND_REQUESTED", "REFUND_APPROVED", "REFUND_COMPLETED", "REFUND_REJECTED",
                    "CREDIT_TRANSFER_REJECTED") == {"ORDER_ATTENTION_REQUIRED", "REFUND_REQUESTED", "REFUND_APPROVED", "REFUND_COMPLETED",
                                                    "REFUND_REJECTED", "CREDIT_TRANSFER_REJECTED"}


# ---------------------------------------------------------------- 24–26 provider events & reconciliation (TEST adapter), 18 lazy expiry
def test_provider_events_reconciliation_and_lazy_expiry(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    m = M(client, db, 83.15, 28.15, "9560 2000 3000")
    m.verify_buyer()
    lst = m.listing(600, "10.00", rng=m.range600)
    adapter = TestPaymentAdapter()
    buyer_p = load_principal(db, m.buyer.user, None)
    fin_p = load_principal(db, m.fin.user, None)
    bctx, fctx, sys_ctx = RequestContext(user_id=m.buyer.user.id), RequestContext(user_id=m.fin.user.id), RequestContext.system()
    # 24 / 25: provider payment (outbox) → SUCCEEDED event → duplicate is a recorded no-op → seller finance confirms
    o = m.order([(lst["id"], 30)]).json()
    p = ps.start_provider_payment(db, bctx, buyer_p, uuid.UUID(o["id"]), adapter)
    assert p.status == "PENDING" and p.external_reference == f"TPAY-{p.payment_code}"
    ev = adapter.event("EV-1", p.external_reference, "SUCCEEDED")
    assert ps.ingest_event(db, sys_ctx, adapter, ev) == "APPLIED"
    assert ps.ingest_event(db, sys_ctx, adapter, ev) == "DUPLICATE"
    assert db.scalar(select(func.count()).select_from(PaymentEvent).where(PaymentEvent.external_event_id == "EV-1")) == 1
    db.refresh(p)
    assert p.status == "PENDING_CONFIRMATION"
    ps.confirm(db, fctx, fin_p, p.id, None)
    assert db.get(Order, uuid.UUID(o["id"])).status == "TRANSFER_PENDING"
    assert ps.ingest_event(db, sys_ctx, adapter, adapter.event("EV-1b", p.external_reference, "SUCCEEDED")) == "IGNORED"   # no second effect
    assert db.scalar(select(func.count()).select_from(CreditTransfer).where(CreditTransfer.purpose_reference == o["items"][0]["item_code"])) == 1
    # 26: timeout → UNCONFIRMED (no automatic retry) → manual reconciliation queries the provider once
    o2 = m.order([(lst["id"], 20)]).json()
    adapter.timeout_next = True
    p2 = ps.start_provider_payment(db, bctx, buyer_p, uuid.UUID(o2["id"]), adapter)
    assert p2.status == "UNCONFIRMED"
    assert p2.external_reference is None                                    # the provider never answered
    adapter.payments[f"TPAY-{p2.payment_code}"] = "SUCCEEDED"
    rec = ps.reconcile(db, fctx, fin_p, p2.id, adapter)
    assert rec.status == "PENDING_CONFIRMATION" and rec.external_reference == f"TPAY-{p2.payment_code}"
    # a FAILED provider payment keeps the order PLACED; the buyer may pay again (D18)
    o3 = m.order([(lst["id"], 10)]).json()
    p3 = ps.start_provider_payment(db, bctx, buyer_p, uuid.UUID(o3["id"]), adapter)
    assert ps.ingest_event(db, sys_ctx, adapter, adapter.event("EV-3", p3.external_reference, "FAILED")) == "APPLIED"
    db.refresh(p3)
    assert p3.status == "FAILED" and db.get(Order, uuid.UUID(o3["id"])).status == "PLACED"
    # F: a payment event after the order was cancelled → UNMATCHED (refund required); the order stays CANCELLED
    p3b = ps.start_provider_payment(db, bctx, buyer_p, uuid.UUID(o3["id"]), adapter)
    assert m.post(f"{ORD}/{o3['id']}/cancel", {"reason": "TEST: abandoned checkout"}).json()["status"] == "CANCELLED"
    assert ps.ingest_event(db, sys_ctx, adapter, adapter.event("EV-4", p3b.external_reference, "SUCCEEDED")) == "UNMATCHED"
    db.refresh(p3b)
    assert p3b.status == "UNMATCHED"
    rf = m.post(f"{PAY}/{p3b.id}/refunds", {"reason": "TEST: unmatched payment"}, m.fin)
    assert rf.status_code == 201 and m.get(f"{ORD}/{o3['id']}").json()["status"] == "CANCELLED"
    m.post(f"/api/v1/refunds/{rf.json()['id']}/approve", {}, m.fin2)
    done = ps.decide_refund(db, fctx, fin_p, uuid.UUID(rf.json()["id"]), "complete", None, None, adapter)      # provider refund
    assert done.status == "COMPLETED" and done.external_reference and adapter.refunds
    # 43: LIVE manual payments are reconciled by people, not by the platform
    o4 = m.order([(lst["id"], 10)]).json()
    p4 = m.pay(o4).json()
    assert codes(m.post(f"{PAY}/{p4['id']}/reconcile", {}, m.fin)) == "MANUAL_ACTION_REQUIRED"
    with pytest.raises(Conflict):
        ps.start_provider_payment(db, bctx, buyer_p, uuid.UUID(o4["id"]), ADAPTERS["MANUAL"])
    # 18: lazy expiry — an unpaid order past its deadline expires with its 9B reservations; the listing capacity returns
    o5 = m.order([(lst["id"], 40)]).json()
    left = m.get(f"{MP}/listings/{lst['id']}").json()["remaining_quantity"]
    _later(monkeypatch, timedelta(hours=25))
    x = m.get(f"{ORD}/{o5['id']}").json()
    assert x["status"] == "EXPIRED" and x["items"][0]["status"] == "EXPIRED" and x["items"][0]["reservation_status"] == "EXPIRED"
    # a payment reported received holds its order for the seller's decision: PENDING_CONFIRMATION (o4) is not expired …
    assert m.get(f"{ORD}/{o4['id']}").json()["status"] == "PLACED"
    assert m.get(f"{MP}/listings/{lst['id']}").json()["remaining_quantity"] == left + 40
    # … its 9B reservation still expires (D18) and the late confirmation routes the order to ATTENTION_REQUIRED (nothing fabricated)
    ls.expire_due(db, sys_ctx)
    c4 = m.post(f"{PAY}/{p4['id']}/confirm", {}, m.fin)
    assert c4.json()["status"] == "CONFIRMED", c4.text
    a4 = m.get(f"{ORD}/{o4['id']}").json()
    assert a4["status"] == "ATTENTION_REQUIRED" and a4["attention_reason"].startswith("RESERVATION_EXPIRED") and a4["items"][0]["status"] == "FAILED"
    assert a4["items"][0]["transfer_id"] is None
    assert _actions(db, "PAYMENT_EVENT_RECEIVED", "PAYMENT_EVENT_DUPLICATE", "PAYMENT_UNCONFIRMED", "PAYMENT_RECONCILED", "PAYMENT_UNMATCHED",
                    "ORDER_EXPIRED") == {"PAYMENT_EVENT_RECEIVED", "PAYMENT_EVENT_DUPLICATE", "PAYMENT_UNCONFIRMED", "PAYMENT_RECONCILED",
                                         "PAYMENT_UNMATCHED", "ORDER_EXPIRED"}
    _conserved(db, m.lg.batch["id"])


# ---------------------------------------------------------------- 41 DEMO, 37 outsiders, buyer / seller payment isolation
def test_demo_has_no_inventory_and_outsiders_are_refused(client: TestClient, db: Session) -> None:
    demo_org = make_org(db, org_type="BUYER", environment="DEMO")
    u = make_user(db, roles=[("BUYER", demo_org)], environment="DEMO")
    demo = Actor(u, login(client, u))
    r = client.get(f"{MP}/listings", headers=demo.headers).json()
    assert r["listings"] == [] and r["demo_note"] == "DEMO — no registry-issued credits; nothing is listed"
    o = client.post(ORD, headers=demo.headers, json={"buyer_organization_id": str(demo_org.id), "items": [{"listing_id": str(uuid.uuid4()),
                                                                                                         "quantity": 1}]})
    assert o.status_code in (404, 409) and o.json()["error_code"] in ("BUYER_KYC_REQUIRED", "LISTING_NOT_FOUND")
    assert client.get(ORD, headers=demo.headers).json() == {"orders": [], "demo_note": "DEMO — no registry-issued credits; nothing is listed"}
    for role, org_type in (("VVB_REVIEWER", "VVB"), ("LAB_TECHNICIAN", "LABORATORY"), ("FARMER", "FARMER_GROUP"), ("QA_OFFICER", "PROJECT_DEVELOPER")):
        a = staff(db, client, make_org(db, org_type=org_type), role)
        for url in (f"{MP}/listings", ORD, PAY, f"{MP}/buyer-profiles"):
            assert client.get(url, headers=a.headers).status_code == 403, (role, url)
    assert db.scalar(select(func.count()).select_from(Order).where(Order.environment == "DEMO")) == 0


def test_payment_isolation_between_buyers_and_sellers(client: TestClient, db: Session) -> None:
    m = M(client, db, 83.16, 28.16, "9570 2000 3000")
    m.verify_buyer()
    lst = m.listing(100, "5.00")
    o = m.order([(lst["id"], 10)]).json()
    p = m.pay(o).json()
    other_buyer = staff(db, client, make_org(db, org_type="BUYER"), "BUYER")
    other_fin = staff(db, client, make_org(db), "FINANCE_MANAGER")
    for who in (other_buyer, other_fin):
        assert client.get(f"{PAY}/{p['id']}", headers=who.headers).status_code == 404
        assert all(x["id"] != p["id"] for x in client.get(PAY, headers=who.headers).json())
    assert client.post(f"{PAY}/{p['id']}/confirm", headers=other_fin.headers).status_code == 404
    assert client.get(f"{PAY}/{p['id']}", headers=m.fin.headers).json()["can_confirm"] is True
    ev = p["evidence_document_id"]
    assert client.get(f"/api/v1/evidence/documents/{ev}", headers=m.fin.headers).status_code == 200
    assert client.get(f"/api/v1/evidence/documents/{ev}", headers=other_buyer.headers).status_code == 404
    pay_row = db.get(Payment, uuid.UUID(p["id"]))
    assert pay_row is not None and pay_row.payee_organization_id == m.seller.id                          # D16: the seller is the payee
    assert db.scalar(select(func.count()).select_from(CreditPosition).where(CreditPosition.owner_organization_id == m.buyer_org.id)) == 0


def test_downgrade_guard_refuses_while_phase_10_rows_exist() -> None:
    import pathlib

    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from app.core.database import get_engine
    src = (pathlib.Path(__file__).parents[1] / "alembic" / "versions" / "20261003_0015_phase10_marketplace.py").read_text(encoding="utf-8")
    guard = src.split("def downgrade() -> None:")[1].split('op.execute("""')[1].split('""")')[0]
    with get_engine().connect() as c:
        t = c.begin()
        session = Session(bind=c, join_transaction_mode="create_savepoint")
        try:
            org = make_org(session, org_type="BUYER")
            user = make_user(session)
            session.add(BuyerProfile(organization_id=org.id, status="DRAFT", legal_name="GUARD", created_by=user.id, environment="LIVE"))
            session.flush()
            with pytest.raises(DBAPIError) as e:
                c.execute(text(guard))
            assert "Downgrade refused" in str(e.value)
        finally:
            session.close()
            if t.is_active:
                t.rollback()
