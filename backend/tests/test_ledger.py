"""Phase 9B — credit ledger (inventory, ownership positions, reservations, transfers, retirements). Functional, RBAC, isolation, 9A guard,
reconciliation and DEMO tests inside the rolled-back test database. Real cross-connection concurrency, fault injection and direct-SQL trigger
tests are in tests/test_ledger_concurrency.py (committed data on a database snapshot that is reverted afterwards).

Every successful path starts from a TEST-only registry issuance (Phase 7 fixture → 8B VVB decision → 9A manual registry flow)."""
import uuid
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.registry import ADAPTERS, AccountRef, CreditMovement, ManualActionRequired
from app.models import (
    AuditLog,
    CreditBatch,
    CreditLedgerEntry,
    CreditPosition,
    Organization,
    Permission,
    RegistryEvent,
    Role,
    RolePermission,
)
from app.models.base import utcnow
from app.services import ledger_service as ls
from tests.calc_fixture import CalcCtx, calc_scenario
from tests.conftest import Actor, login, make_org, make_user
from tests.phase2 import staff
from tests.test_registry import PDF, Reg, codes

C = "/api/v1/credits"
R = "/api/v1/registry"


class L:
    """A project whose period was VVB-verified (1000 tCO2e) and registry-issued (TEST fixture), opened in the ledger on request."""

    def __init__(self, client: TestClient, db: Session, k: CalcCtx, ranges: list[tuple[str | None, str | None, int]] | None = None) -> None:
        self.client, self.db, self.k = client, db, k
        self.reg = Reg(client, db, k, quantity="5000")     # headroom for several TEST issuances
        self.sid = self.reg.accepted(f"TEST-SUB-{uuid.uuid4().hex[:6]}")["id"]
        self.org = k.x.c.t.org
        self.cm = staff(db, client, self.org, "CREDIT_MANAGER")
        self.qa = k.qa
        self.batch, self.issuance = self.issue(ranges or [("TL-0001", "TL-0600", 600), ("TL-0601", "TL-1000", 400)])

    def issue(self, ranges: list[tuple[str | None, str | None, int]], vintage: str = "2026") -> tuple[dict, dict]:
        total = sum(q for _, _, q in ranges)
        batches = [{"vintage": vintage, "quantity": total,
                    "serial_ranges": [{"serial_start": a, "serial_end": b, "quantity": q} for a, b, q in ranges]}]
        i = self.reg.issue(self.sid, total, f"TEST-ISS-{uuid.uuid4().hex[:6]}", batches=batches).json()
        c = self.reg.confirm(i["id"]).json()
        assert c["status"] == "CONFIRMED", c
        return c["batches"][0], c

    def post(self, url: str, body: dict | None = None, who: Actor | None = None, key: str | None = None) -> Any:
        h = {**(who or self.cm).headers, **({"Idempotency-Key": key} if key else {})}
        return self.client.post(f"{C}{url}", headers=h, json=body if body is not None else {})

    def open(self, batch_id: str | None = None) -> dict:
        o = self.post(f"/batches/{batch_id or self.batch['id']}/open")
        assert o.status_code == 201, o.text
        c = self.post(f"/openings/{o.json()['id']}/confirm", who=self.qa)
        assert c.status_code == 200, c.text
        return c.json()

    def balance(self, owner: Any, batch_id: str | None = None) -> dict:
        inv = self.client.get(f"{C}/inventory", headers=self.qa.headers, params={"project_id": self.k.project_id}).json()
        b = next(x for x in inv["batches"] if x["batch_id"] == (batch_id or self.batch["id"]))
        return next((x for x in b["balances"] if x["owner_organization_id"] == str(owner)), {"available": 0, "reserved": 0, "retired": 0,
                                                                                            "pending_transfer": 0, "pending_retirement": 0,
                                                                                            "transferred_out": 0})

    def doc(self, url: str, who: Actor | None = None) -> str:
        r = self.client.post(f"{C}{url}", headers=(who or self.qa).headers, files={"file": ("e.pdf", PDF, "application/pdf")})
        assert r.status_code == 201, r.text
        return str(r.json()["document_id"])

    def reserve(self, q: int, owner: Any = None, who: Actor | None = None, key: str | None = None, **kw: Any) -> Any:
        return self.post("/reservations", {"batch_id": self.batch["id"], "owner_organization_id": str(owner or self.org.id), "quantity": q,
                                           "purpose": "TEST hold", "expires_at": (utcnow() + timedelta(hours=1)).isoformat() + "Z", **kw}, who=who,
                         key=key)

    def transfer(self, q: int | None, recipient: Any, kind: str = "INTERNAL", owner: Any = None, who: Actor | None = None, **kw: Any) -> Any:
        return self.post("/transfers", {"kind": kind, "batch_id": self.batch["id"], "sender_organization_id": str(owner or self.org.id),
                                        "recipient_organization_id": str(recipient), "quantity": q, **kw}, who=who)

    def retire_req(self, q: int | None, owner: Any = None, who: Actor | None = None, **kw: Any) -> Any:
        return self.post("/retirements", {"batch_id": self.batch["id"], "owner_organization_id": str(owner or self.org.id), "quantity": q,
                                          "beneficiary": "TEST Beneficiary Ltd", "reason": "TEST: voluntary claim", **kw}, who=who)


def _actions(db: Session, *actions: str) -> set[str]:
    return {a for (a,) in db.execute(select(AuditLog.action).where(AuditLog.action.in_(actions)))}


def _conserved(db: Session, batch_id: str) -> None:
    b = db.get(CreditBatch, uuid.UUID(batch_id))
    assert b is not None
    total = sum(p.quantity for p in db.scalars(select(CreditPosition).where(CreditPosition.batch_id == b.id, CreditPosition.status == "OPEN")))
    assert total == b.quantity, (total, b.quantity)


# ---------------------------------------------------------------- RBAC matrix and surface (D16, D21, D12)
def test_permission_grants_surface_and_registry_boundary(db: Session) -> None:
    def perms(role: str) -> set[str]:
        return {c for (c,) in db.execute(select(Permission.code).join(RolePermission, RolePermission.permission_id == Permission.id)
                                         .join(Role, Role.id == RolePermission.role_id).where(Role.code == role)) if c.startswith("credits.")}
    assert perms("CREDIT_MANAGER") == {"credits.read", "credits.manage"}
    assert perms("QA_OFFICER") == {"credits.read", "credits.confirm"}
    assert perms("PROJECT_MANAGER") == perms("REGISTRY_MANAGER") == perms("FINANCE_MANAGER") == {"credits.read"}
    assert perms("BUYER") == {"credits.holder_read", "credits.holder_retire"}
    for role in ("VVB_REVIEWER", "LAB_TECHNICIAN", "LAB_MANAGER", "FARMER", "METHODOLOGY_SPECIALIST", "FIELD_AGENT"):
        assert perms(role) == set(), role
    from app.main import app
    paths = [getattr(r, "path", "") for r in app.routes]
    segments = {seg for p in paths for seg in p.split("/")}
    for word in ("checkout", "invoices", "payouts", "offers", "prices", "pricing"):      # Phase 10 adds no checkout, invoice, offer or payout
        assert word not in segments, word
    for word, prefix in (("listings", "/api/v1/marketplace"), ("orders", "/api/v1/orders"), ("payments", "/api/v1/payments")):
        assert all(p.startswith(prefix) for p in paths if word in p.split("/")), word     # the marketplace never sits under /credits
    manual = ADAPTERS["MANUAL"]
    ref = AccountRef("R", "A")
    for call in (lambda: manual.transfer_credits(ref, CreditMovement("X", 1), "k"), lambda: manual.retire_credits(ref, CreditMovement("X", 1), "k"),
                 lambda: manual.get_credit_inventory(ref)):
        with pytest.raises(ManualActionRequired):                 # no fake registry success
            call()


# ---------------------------------------------------------------- opening (D2, 1–3), reservation (4–6), idempotency (32)
def test_opening_dual_control_reservations_expiry_and_idempotency(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    k = calc_scenario(db, client, 81.10, 26.10, "9310 2000 3000")
    lg = L(client, db, k)
    # 1. only a registry-ISSUED batch: a RECORDED (unconfirmed) issuance's batch cannot be opened
    stmt = lg.reg.doc(f"{R}/submissions/{lg.sid}/documents", "ISSUANCE_STATEMENT")
    pending = lg.reg.post(f"{R}/submissions/{lg.sid}/issuances", {"external_issuance_id": "TEST-ISS-P", "issuance_date": "2026-10-01", "quantity": 10,
                                                                   "unit": "TCU", "document_id": stmt,
                                                                   "batches": [{"vintage": "2026", "quantity": 10, "serial_ranges": [{"quantity": 10}]}]}).json()
    assert codes(lg.post(f"/batches/{pending['batches'][0]['id']}/open")) == "BATCH_NOT_ISSUED"
    inv = client.get(f"{C}/inventory", headers=lg.qa.headers, params={"project_id": k.project_id}).json()
    assert next(b for b in inv["batches"] if b["batch_id"] == lg.batch["id"])["balances"] == []   # not in the ledger until opened
    # 2. dual control: requester never confirms
    o = lg.post(f"/batches/{lg.batch['id']}/open", key="TEST-OPEN-1").json()
    assert lg.post(f"/batches/{lg.batch['id']}/open", key="TEST-OPEN-1").json()["id"] == o["id"]      # 32. Idempotency-Key replay
    assert lg.post(f"/openings/{o['id']}/confirm").status_code == 403                                  # the credit manager cannot confirm
    dual = staff(db, client, lg.org, "CREDIT_MANAGER", "QA_OFFICER")
    c = lg.post(f"/openings/{o['id']}/confirm", who=lg.qa).json()
    assert c["status"] == "CONFIRMED" and c["confirmed_by_name"]
    # 3. never twice
    assert codes(lg.post(f"/batches/{lg.batch['id']}/open")) == "OPENING_EXISTS"
    bal = lg.balance(lg.org.id)
    assert bal["available"] == 1000 and bal["reserved"] == 0
    positions = client.get(f"{C}/batches/{lg.batch['id']}/positions", headers=lg.qa.headers).json()
    assert sorted(p["quantity"] for p in positions) == [400, 600] and {p["state"] for p in positions} == {"AVAILABLE"}
    assert {p["registry_range"] for p in positions} == {"TL-0001 – TL-0600", "TL-0601 – TL-1000"}       # original registry ranges, verbatim
    # SoD as same person on the dual-role user's own request
    lg2 = lg.issue([("TL2-0001", "TL2-0100", 100)])
    o2 = lg.post(f"/batches/{lg2[0]['id']}/open", who=dual).json()
    r = lg.post(f"/openings/{o2['id']}/confirm", who=dual)
    assert r.status_code == 403 and r.json()["error_code"] == "SEPARATION_OF_DUTIES"
    # 4. reservation consumes AVAILABLE; insufficient → 409 + double-spend audit
    rs = lg.reserve(700, key="TEST-RSV-1").json()
    assert rs.get("status") == "ACTIVE" and rs["reservation_code"].startswith("RSV-"), rs
    assert lg.reserve(700, key="TEST-RSV-1").json()["id"] == rs["id"]
    assert lg.balance(lg.org.id)["available"] == 300 and lg.balance(lg.org.id)["reserved"] == 700
    bad = lg.reserve(301)
    assert bad.status_code == 409 and bad.json()["error_code"] == "INSUFFICIENT_AVAILABLE"
    assert "CREDIT_DOUBLE_SPEND_CONFLICT" in _actions(db, "CREDIT_DOUBLE_SPEND_CONFLICT")
    assert lg.post("/reservations", {"batch_id": lg.batch["id"], "owner_organization_id": str(lg.org.id), "quantity": 1, "purpose": "TEST",
                                     "expires_at": (utcnow() - timedelta(hours=1)).isoformat() + "Z"}).json()["error_code"] == "EXPIRY_IN_PAST"
    assert lg.post("/reservations", {"batch_id": lg.batch["id"], "owner_organization_id": str(lg.org.id), "quantity": 1, "purpose": "TEST",
                                     "available_quantity": 5, "expires_at": (utcnow() + timedelta(hours=1)).isoformat() + "Z"}).status_code == 422
    # 5. release
    assert lg.post(f"/reservations/{rs['id']}/release", {"reason": "TEST: not needed"}).json()["status"] == "RELEASED"
    assert lg.balance(lg.org.id)["available"] == 1000
    # 6. lazy expiry (on reads) and the explicit sweep
    r2 = lg.reserve(100).json()
    r3 = lg.reserve(50).json()
    later = utcnow() + timedelta(hours=2)
    monkeypatch.setattr(ls, "utcnow", lambda: later)
    assert lg.balance(lg.org.id)["available"] == 1000                                                  # expired on read
    rows = {x["id"]: x["status"] for x in client.get(f"{C}/reservations", headers=lg.cm.headers).json()}
    assert rows[r2["id"]] == rows[r3["id"]] == "EXPIRED"
    assert lg.post("/reservations/expire-due").json() == {"expired": 0}
    monkeypatch.undo()
    _conserved(db, lg.batch["id"])
    assert {"CREDIT_INVENTORY_OPENED", "CREDIT_INVENTORY_CONFIRMED", "CREDIT_RESERVATION_CREATED", "CREDIT_RESERVATION_RELEASED",
            "CREDIT_RESERVATION_EXPIRED"} <= _actions(db, "CREDIT_INVENTORY_OPENED", "CREDIT_INVENTORY_CONFIRMED", "CREDIT_RESERVATION_CREATED",
                                                       "CREDIT_RESERVATION_RELEASED", "CREDIT_RESERVATION_EXPIRED")


# ---------------------------------------------------------------- transfers (7–10, 15, 33), buyer (21, 22), environment (25)
def test_transfers_internal_registry_cancel_reject_reversal_and_buyer_view(client: TestClient, db: Session) -> None:
    k = calc_scenario(db, client, 81.20, 26.20, "9320 2000 3000")
    lg = L(client, db, k)
    lg.open()
    buyer_org = make_org(db, org_type="BUYER")
    buyer = staff(db, client, buyer_org, "BUYER")
    for bad in (make_org(db, org_type="VVB"), make_org(db, org_type="BUYER", environment="DEMO"), make_org(db, org_type="LABORATORY")):
        assert codes(lg.transfer(10, bad.id)) == "INVALID_RECIPIENT"
    assert codes(lg.transfer(10, lg.org.id)) == "SAME_PARTY"
    # 7. INTERNAL: pending → completed by a second person, atomically
    t = lg.transfer(250, buyer_org.id, purpose="TEST sale (no price)", purpose_reference="TEST-REF-1").json()
    assert t["status"] == "REQUESTED" and lg.balance(lg.org.id)["pending_transfer"] == 250 and lg.balance(lg.org.id)["available"] == 750
    assert lg.post(f"/transfers/{t['id']}/complete").status_code == 403                    # the credit manager cannot confirm
    done = lg.post(f"/transfers/{t['id']}/complete", who=lg.qa).json()
    assert done["status"] == "COMPLETED" and done["completion_entry_id"]
    assert lg.balance(buyer_org.id)["available"] == 250 and lg.balance(lg.org.id)["transferred_out"] == 250
    # 21 / 22. the buyer sees only its own holdings, allow-listed
    h = client.get(f"{C}/holdings", headers=buyer.headers)
    assert h.status_code == 200 and sum(x["quantity"] for x in h.json()["holdings"]) == 250
    text = h.text.lower()
    for forbidden in ("farmer", "farm_code", "kyc", "bank", "latitude", "agreement", "audit"):
        assert forbidden not in text, forbidden
    for url in (f"{C}/inventory", f"{C}/batches", f"/api/v1/projects/{k.project_id}", f"{R}/accounts", "/api/v1/farmers"):
        assert client.get(url, headers=buyer.headers).status_code in (403, 404), url
    assert lg.reserve(10, owner=buyer_org.id, who=buyer).status_code == 403                # buyers do not reserve or transfer
    other_buyer = staff(db, client, make_org(db, org_type="BUYER"), "BUYER")
    assert client.get(f"{C}/holdings", headers=other_buyer.headers).json()["holdings"] == []
    # 8. REGISTRY transfer needs the registry reference and evidence; 33. duplicate reference
    rt = lg.transfer(100, buyer_org.id, kind="REGISTRY", recipient_external_account_id="TEST-BUYER-ACC-9").json()
    assert codes(lg.post(f"/transfers/{rt['id']}/complete", who=lg.qa)) == "REGISTRY_EVIDENCE_REQUIRED"
    ev = lg.doc(f"/transfers/{rt['id']}/documents")
    rdone = lg.post(f"/transfers/{rt['id']}/complete", {"registry_transfer_reference": "TEST-RTR-1", "document_id": ev}, who=lg.qa).json()
    assert rdone["status"] == "COMPLETED" and rdone["registry_transfer_reference"] == "TEST-RTR-1"
    moved = [p for p in client.get(f"{C}/batches/{lg.batch['id']}/positions", headers=lg.qa.headers).json()
             if p["holding_external_account_id"] == "TEST-BUYER-ACC-9"]
    assert sum(p["quantity"] for p in moved) == 100
    rt2 = lg.transfer(10, buyer_org.id, kind="REGISTRY", recipient_external_account_id="TEST-BUYER-ACC-9").json()
    ev2 = lg.doc(f"/transfers/{rt2['id']}/documents")
    assert codes(lg.post(f"/transfers/{rt2['id']}/complete", {"registry_transfer_reference": "TEST-RTR-1", "document_id": ev2}, who=lg.qa)) == \
        "DUPLICATE_REGISTRY_REFERENCE"
    # 9 / 10. cancel (sender) and reject (confirmer) return the credits
    assert lg.post(f"/transfers/{rt2['id']}/cancel", {"reason": "TEST: wrong account"}).json()["status"] == "CANCELLED"
    t3 = lg.transfer(20, buyer_org.id).json()
    assert lg.post(f"/transfers/{t3['id']}/reject", {"reason": "TEST: not approved"}, who=lg.qa).json()["status"] == "REJECTED"
    assert codes(lg.post(f"/transfers/{t3['id']}/complete", who=lg.qa)) == "TRANSFER_NOT_REQUESTED"     # 34. final states
    assert lg.balance(lg.org.id)["available"] == 650 and lg.balance(lg.org.id)["pending_transfer"] == 0
    # 15. reversal of an INTERNAL transfer (dual control); registry transfers are never reversed internally
    assert codes(lg.post(f"/entries/{rdone['completion_entry_id']}/reverse", {"reason": "TEST"})) == "REVERSAL_NOT_ALLOWED"
    v = lg.post(f"/entries/{done['completion_entry_id']}/reverse", {"reason": "TEST: wrong recipient"}).json()
    assert v["status"] == "REQUESTED"
    assert lg.post(f"/reversals/{v['id']}/apply", {"note": "self"}, who=lg.cm).status_code == 403
    applied = lg.post(f"/reversals/{v['id']}/apply", {"note": "TEST: confirmed mistake"}, who=lg.qa).json()
    assert applied["status"] == "APPLIED" and applied["entry_id"]
    assert lg.balance(buyer_org.id)["available"] == 100 and lg.balance(lg.org.id)["available"] == 900   # only the REGISTRY 100 stays with the buyer
    assert db.get(CreditLedgerEntry, uuid.UUID(done["completion_entry_id"])) is not None                # the original entry is kept
    entry = client.get(f"{C}/entries/{applied['entry_id']}", headers=lg.qa.headers).json()
    assert entry["entry_type"] == "REVERSAL" and sum(p["quantity"] for p in entry["inputs"]) == sum(p["quantity"] for p in entry["outputs"]) == 250
    _conserved(db, lg.batch["id"])
    acts = _actions(db, "CREDIT_TRANSFER_REQUESTED", "CREDIT_TRANSFER_COMPLETED", "CREDIT_TRANSFER_CANCELLED", "CREDIT_TRANSFER_REJECTED",
                    "CREDIT_LEDGER_REVERSAL")
    assert len(acts) == 5
    # two-organization audit for transfers
    rows = db.scalars(select(AuditLog).where(AuditLog.action == "CREDIT_TRANSFER_COMPLETED", AuditLog.entity_id == t["id"])).all()
    assert {r.organization_id for r in rows} == {lg.org.id, buyer_org.id}


# ---------------------------------------------------------------- retirement (11–14, 39 via API), buyer retirement, lineage (27)
def test_retirement_registry_evidence_terminal_buyer_and_lineage(client: TestClient, db: Session) -> None:
    k = calc_scenario(db, client, 81.30, 26.30, "9330 2000 3000")
    lg = L(client, db, k)
    lg.open()
    r = lg.retire_req(100).json()
    assert r["status"] == "REQUESTED" and lg.balance(lg.org.id)["pending_retirement"] == 100
    cert = lg.doc(f"/retirements/{r['id']}/documents")
    body = {"registry_retirement_reference": "TEST-RET-1", "retirement_date": "2026-10-02", "document_id": cert,
            "retired_serials": [{"serial_start": "TL-0001", "serial_end": "TL-0100", "quantity": 100}]}
    assert lg.post(f"/retirements/{r['id']}/retire", body).status_code == 403             # requester side cannot confirm
    assert lg.post(f"/retirements/{r['id']}/retire", {k_: v for k_, v in body.items() if k_ != "document_id"}, who=lg.qa).status_code == 422
    assert codes(lg.post(f"/retirements/{r['id']}/retire", {**body, "retired_serials": [{"serial_start": "A", "serial_end": "B", "quantity": 99}]},
                         who=lg.qa)) == "RETIRED_SERIALS_MISMATCH"
    done = lg.post(f"/retirements/{r['id']}/retire", body, who=lg.qa).json()
    assert done["status"] == "RETIRED" and done["retired_serials"][0]["serial_start"] == "TL-0001" and done["certificate_document_id"] == cert
    assert lg.balance(lg.org.id)["retired"] == 100 and lg.balance(lg.org.id)["available"] == 900
    retired = [p for p in client.get(f"{C}/batches/{lg.batch['id']}/positions", headers=lg.qa.headers).json() if p["state"] == "RETIRED"]
    assert len(retired) == 1 and retired[0]["sub_range"] == "TL-0001 – TL-0100"           # registry-stated serials, verbatim
    # 14. terminal: retired credits are never available again (no reserve / transfer / retire of them)
    assert codes(lg.reserve(901)) == "INSUFFICIENT_AVAILABLE"
    assert codes(lg.post(f"/retirements/{r['id']}/cancel", {"reason": "TEST"})) == "RETIREMENT_NOT_REQUESTED"
    # 33. duplicate registry retirement reference
    r2 = lg.retire_req(10).json()
    cert2 = lg.doc(f"/retirements/{r2['id']}/documents")
    assert codes(lg.post(f"/retirements/{r2['id']}/retire", {**body, "document_id": cert2, "retired_serials": None}, who=lg.qa)) == \
        "DUPLICATE_REGISTRY_REFERENCE"
    # 12 / 13. reject and cancel return the credits
    assert lg.post(f"/retirements/{r2['id']}/reject", {"reason": "TEST: registry refused"}, who=lg.qa).json()["status"] == "REJECTED"
    r3 = lg.retire_req(5).json()
    assert lg.post(f"/retirements/{r3['id']}/cancel", {"reason": "TEST: changed mind"}).json()["status"] == "CANCELLED"
    assert lg.balance(lg.org.id)["available"] == 900
    # a buyer requests retirement of its own credits; the custodian (holding account organization) records the registry retirement
    buyer_org = make_org(db, org_type="BUYER")
    buyer = staff(db, client, buyer_org, "BUYER")
    t = lg.transfer(200, buyer_org.id).json()
    lg.post(f"/transfers/{t['id']}/complete", who=lg.qa)
    assert lg.retire_req(10, owner=buyer_org.id, who=buyer).status_code == 201
    assert lg.retire_req(500, owner=buyer_org.id, who=buyer).json()["error_code"] == "INSUFFICIENT_AVAILABLE"
    assert lg.retire_req(10, owner=lg.org.id, who=buyer).status_code in (403, 404)            # never another holder's credits
    br = next(x for x in client.get(f"{C}/retirements", headers=buyer.headers).json() if x["owner_organization_id"] == str(buyer_org.id))
    bcert = lg.doc(f"/retirements/{br['id']}/documents")
    assert lg.post(f"/retirements/{br['id']}/retire", {"registry_retirement_reference": "TEST-RET-B", "retirement_date": "2026-10-03",
                                                      "document_id": bcert}, who=lg.qa).json()["status"] == "RETIRED"
    held = client.get(f"{C}/holdings", headers=buyer.headers).json()["holdings"]
    assert sum(x["quantity"] for x in held if x["state"] == "RETIRED") == 10                 # may span positions (never merged)
    # 27. lineage: holders get the ledger chain only; project users also get the 9A → … → farmer-code chain
    lin_b = client.get(f"{C}/retirements/{br['id']}/lineage", headers=buyer.headers).json()
    assert lin_b["chain"][0]["kind"] == "CREDIT_RETIREMENT" and "batch_lineage" not in lin_b
    assert {"RETIREMENT_RETIRE", "RETIREMENT_REQUEST", "TRANSFER_COMPLETE", "TRANSFER_REQUEST", "OPEN_INVENTORY"} <= \
        {c.get("type") for c in lin_b["chain"]}
    lin_p = client.get(f"{C}/retirements/{done['id']}/lineage", headers=k.x.c.t.pm.headers).json()
    assert lin_p["batch_lineage"]["chain"][-1]["kind"] == "PROJECT" and lin_p["batch_lineage"]["sources"]["farms"][0]["farmer_code"]
    _conserved(db, lg.batch["id"])
    assert {"CREDIT_RETIREMENT_REQUESTED", "CREDIT_RETIREMENT_RETIRED", "CREDIT_RETIREMENT_REJECTED", "CREDIT_RETIREMENT_CANCELLED"} <= \
        _actions(db, "CREDIT_RETIREMENT_REQUESTED", "CREDIT_RETIREMENT_RETIRED", "CREDIT_RETIREMENT_REJECTED", "CREDIT_RETIREMENT_CANCELLED")


# ---------------------------------------------------------------- 9A correction guard (16, 17), batch / range isolation (19, 20), RBAC (23)
def test_9a_guard_isolation_and_rbac(client: TestClient, db: Session) -> None:
    k = calc_scenario(db, client, 81.40, 26.40, "9340 2000 3000")
    lg = L(client, db, k, ranges=[("TG-0001", "TG-0300", 300), ("TG-0301", "TG-0600", 300)])
    second, iss2 = lg.issue([("TH-0001", "TH-0200", 200)])
    third, iss3 = lg.issue([("TK-0001", "TK-0100", 100)])
    lg.open()
    lg.open(second["id"])
    # 19 / 20. operations stay inside one batch and, when asked, one registry range
    first_range = next(p["serial_range_id"] for p in client.get(f"{C}/batches/{lg.batch['id']}/positions", headers=lg.qa.headers).json()
                       if p["registry_range"].startswith("TG-0001"))
    res = lg.reserve(250, serial_range_id=first_range).json()
    assert res["status"] == "ACTIVE"
    assert codes(lg.reserve(100, serial_range_id=first_range)) == "INSUFFICIENT_AVAILABLE"            # only 50 left in that range
    assert lg.balance(lg.org.id, second["id"])["available"] == 200 and lg.balance(lg.org.id)["available"] == 350
    # 16. the 9A cancellation / correction is refused once ledger activity exists
    cx = lg.reg.doc(f"{R}/submissions/{lg.sid}/documents", "REGISTRY_RESPONSE")
    assert codes(lg.reg.post(f"{R}/issuances/{lg.issuance['id']}/cancel", {"reason": "TEST", "document_id": cx})) == "LEDGER_ACTIVITY_EXISTS"
    corr = lg.reg.post(f"{R}/issuances/{lg.issuance['id']}/correct", {
        "external_issuance_id": lg.issuance["external_issuance_id"], "issuance_date": "2026-10-02", "quantity": 590, "unit": "TCU",
        "reason": "TEST", "document_id": lg.reg.doc(f"{R}/submissions/{lg.sid}/documents", "ISSUANCE_STATEMENT"),
        "batches": [{"vintage": "2026", "quantity": 590, "serial_ranges": [{"quantity": 590}]}]})
    assert codes(corr) == "LEDGER_ACTIVITY_EXISTS"
    # 17. an untouched opened batch: the 9A cancellation proceeds with an explicit ISSUANCE_ADJUSTMENT; an unopened batch is unaffected
    cx2 = lg.reg.doc(f"{R}/submissions/{lg.sid}/documents", "REGISTRY_RESPONSE")
    ok = lg.reg.post(f"{R}/issuances/{iss2['id']}/cancel", {"reason": "TEST: registry cancelled", "document_id": cx2})
    assert ok.status_code == 200, ok.text
    adj = db.scalars(select(CreditLedgerEntry).where(CreditLedgerEntry.batch_id == uuid.UUID(second["id"]),
                                                     CreditLedgerEntry.entry_type == "ISSUANCE_ADJUSTMENT")).one()
    assert adj.posted and adj.quantity == 200
    assert lg.balance(lg.org.id, second["id"])["available"] == 0
    assert "CREDIT_ISSUANCE_ADJUSTMENT" in _actions(db, "CREDIT_ISSUANCE_ADJUSTMENT")
    cx3 = lg.reg.doc(f"{R}/submissions/{lg.sid}/documents", "REGISTRY_RESPONSE")
    assert lg.reg.post(f"{R}/issuances/{iss3['id']}/cancel", {"reason": "TEST", "document_id": cx3}).status_code == 200
    # 23. RBAC and organization isolation
    other_cm = staff(db, client, make_org(db), "CREDIT_MANAGER")
    assert client.get(f"{C}/batches/{lg.batch['id']}/positions", headers=other_cm.headers).status_code == 404
    assert client.get(f"{C}/inventory", headers=other_cm.headers).json()["batches"] == []
    assert codes(lg.reserve(1, who=other_cm)) == "CREDIT_BATCH_NOT_FOUND"
    assert lg.reserve(1, owner=lg.org.id, who=k.x.c.t.pm).status_code == 403                         # credits.read only
    for role in ("VVB_REVIEWER", "LAB_TECHNICIAN", "FIELD_AGENT"):
        u = staff(db, client, make_org(db, org_type="VVB" if role == "VVB_REVIEWER" else "PROJECT_DEVELOPER"), role)
        assert client.get(f"{C}/inventory", headers=u.headers).status_code == 403, role
    assert codes(lg.post(f"/reservations/{res['id']}/release", {"reason": "TEST"}, who=other_cm)) == "CREDIT_RESERVATION_NOT_FOUND"


# ---------------------------------------------------------------- reconciliation (28), DEMO (30)
def test_manual_reconciliation_and_demo_has_no_credits(client: TestClient, db: Session) -> None:
    k = calc_scenario(db, client, 81.50, 26.50, "9350 2000 3000")
    lg = L(client, db, k)
    lg.open()
    t = lg.transfer(100, make_org(db, org_type="BUYER").id, kind="REGISTRY", recipient_external_account_id="TEST-ELSEWHERE").json()
    ev = lg.doc(f"/transfers/{t['id']}/documents")
    lg.post(f"/transfers/{t['id']}/complete", {"registry_transfer_reference": "TEST-RTR-9", "document_id": ev}, who=lg.qa)
    account = lg.reg.account["id"]
    statement = client.post(f"{C}/accounts/{account}/statements", headers=lg.cm.headers, files={"file": ("s.pdf", PDF, "application/pdf")}).json()
    ok = lg.post(f"/accounts/{account}/reconcile", {"document_id": statement["document_id"],
                                                    "lines": [{"batch_id": lg.batch["id"], "registry_stated_quantity": 900}]}, key="TEST-REC-1").json()
    assert ok["event_type"] == "RECONCILED"
    assert lg.post(f"/accounts/{account}/reconcile", {"document_id": statement["document_id"], "lines": []}, key="TEST-REC-1").json()["event_id"] == \
        ok["event_id"]
    mm = lg.post(f"/accounts/{account}/reconcile", {"document_id": statement["document_id"],
                                                    "lines": [{"batch_id": lg.batch["id"], "registry_stated_quantity": 880}]}).json()
    assert mm["event_type"] == "MISMATCH" and "880" in mm["note"]
    assert lg.balance(lg.org.id)["available"] == 900                                                   # never auto-fixed
    assert db.scalars(select(RegistryEvent).where(RegistryEvent.event_type == "MISMATCH", RegistryEvent.outcome == "INVENTORY")).first()
    assert {"CREDIT_RECONCILIATION_PERFORMED", "CREDIT_RECONCILIATION_MISMATCH"} <= _actions(db, "CREDIT_RECONCILIATION_PERFORMED",
                                                                                              "CREDIT_RECONCILIATION_MISMATCH")
    # DEMO: no credits are seeded; the DEMO views say so
    from app.seed.accounts import seed_demo
    seed_demo(db, "Demo-Password-123")
    assert db.scalars(select(CreditPosition).where(CreditPosition.environment == "DEMO")).first() is None
    assert db.scalars(select(CreditBatch).where(CreditBatch.environment == "DEMO")).first() is None
    demo_buyer_org = db.scalars(select(Organization).where(Organization.code == "DEMO-BUYER-D")).one()
    demo_buyer = login(client, make_user(db, roles=[("BUYER", demo_buyer_org)], environment="DEMO"))
    h = client.get(f"{C}/holdings", headers=demo_buyer).json()
    assert h["holdings"] == [] and h["demo_note"] == "DEMO — no registry-issued credits"
    dev = db.scalars(select(Organization).where(Organization.code == "DEMO-DEV-A")).one()
    demo_cm = login(client, make_user(db, roles=[("CREDIT_MANAGER", dev)], environment="DEMO"))
    inv = client.get(f"{C}/inventory", headers=demo_cm).json()
    assert inv["batches"] == [] and inv["demo_note"] == "DEMO — no registry-issued credits"


# ---------------------------------------------------------------- full TEST lifecycle (31)
def test_complete_test_lifecycle(client: TestClient, db: Session) -> None:
    """issuance → confirmed batch → ledger opening → inventory → reservation → transfer → retirement (TEST fixture data only)."""
    k = calc_scenario(db, client, 81.60, 26.60, "9360 2000 3000")
    lg = L(client, db, k)
    lg.open()
    buyer_org = make_org(db, org_type="BUYER")
    buyer = staff(db, client, buyer_org, "BUYER")
    res = lg.reserve(300, recipient_organization_id=str(buyer_org.id), purpose_reference="TEST-PO-REF").json()
    t = lg.transfer(None, buyer_org.id, reservation_id=res["id"]).json()
    assert t["quantity"] == 300
    assert {x["id"]: x["status"] for x in client.get(f"{C}/reservations", headers=lg.cm.headers).json()}[res["id"]] == "CONSUMED"
    lg.post(f"/transfers/{t['id']}/complete", who=lg.qa)
    r = lg.retire_req(120, owner=buyer_org.id, who=buyer).json()
    cert = lg.doc(f"/retirements/{r['id']}/documents")
    assert lg.post(f"/retirements/{r['id']}/retire", {"registry_retirement_reference": "TEST-RET-L", "retirement_date": "2026-10-03",
                                                     "document_id": cert}, who=lg.qa).json()["status"] == "RETIRED"
    assert lg.balance(buyer_org.id)["available"] == 180 and lg.balance(buyer_org.id)["retired"] == 120
    assert lg.balance(lg.org.id)["available"] == 700 and lg.balance(lg.org.id)["transferred_out"] == 300
    _conserved(db, lg.batch["id"])
    assert "CREDIT_RESERVATION_CONSUMED" in _actions(db, "CREDIT_RESERVATION_CONSUMED")
