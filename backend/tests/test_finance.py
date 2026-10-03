"""Phase 11 — revenue, revenue-share configuration, farm allocation, costs, settlement runs, payouts, reconciliation, recovery cases.
Functional, RBAC / SoD, isolation, audit, lineage and DEMO / TEST / LIVE tests inside the rolled-back test database. Real cross-connection
concurrency and the direct-SQL trigger tests are in tests/test_finance_concurrency.py.

Every sale starts from the Phase 10 world (TEST registry issuance → 9B ledger → listing → manual payment → delivery); no financial value is
defaulted — every percentage, rounding mode and cost below is a TEST value entered as configuration."""
import json
import uuid
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Float, func, select
from sqlalchemy.orm import Session

from app.core.context import RequestContext
from app.core.errors import Conflict
from app.integrations.payout import ADAPTERS, ManualActionRequired, PayoutRequest
from app.models import (
    AuditLog,
    Document,
    FarmerBankAccount,
    Payout,
    PayoutAdjustment,
    Permission,
    Project,
    ProjectFarm,
    RevenueRecord,
    Role,
    RolePermission,
    SettlementRun,
)
from app.models.base import Base
from app.security.principal import load_principal
from app.services import finance_service as fs
from app.services import payout_service as pys
from app.services import settlement_service as ss
from tests.conftest import Actor, login, make_org, make_user
from tests.payout_fixture import TestPayoutAdapter
from tests.phase2 import staff
from tests.phase5 import locked_project
from tests.test_marketplace import ORD, PAY, M
from tests.test_registry import PDF, codes

V = "/api/v1"
FIN_PREFIXES = ("revenue", "settlement", "payouts", "sharing", "costs")
FIN_TABLES = ("revenue_records", "revenue_share_versions", "farm_allocation_versions", "farm_allocation_lines", "project_costs", "settlement_runs",
              "settlement_revenue_items", "settlement_cost_items", "farmer_entitlements", "payouts", "payout_transactions",
              "payout_reconciliations", "payout_adjustments")


class F:
    """The Phase 10 world plus the finance team: the project manager authors sharing configuration and records costs; four finance
    managers split approval, calculation, settlement approval, execution and reconciliation."""

    def __init__(self, client: TestClient, db: Session, lon: float, lat: float, idn: str) -> None:
        self.m = M(client, db, lon, lat, idn)
        self.client, self.db = client, db
        self.pm = self.m.k.x.c.t.pm
        self.fin, self.fin2 = self.m.fin, self.m.fin2
        self.fin3 = staff(db, client, self.m.seller, "FINANCE_MANAGER")
        self.fin4 = staff(db, client, self.m.seller, "FINANCE_MANAGER")
        self.project_id = self.m.k.project_id
        self.pfs = list(db.scalars(select(ProjectFarm).where(ProjectFarm.project_id == uuid.UUID(self.project_id))
                                   .order_by(ProjectFarm.added_at)).all())

    def post(self, url: str, body: dict | None = None, who: Actor | None = None, key: str | None = None) -> Any:
        h = {**(who or self.fin).headers, **({"Idempotency-Key": key} if key else {})}
        return self.client.post(f"{V}{url}", headers=h, json=body if body is not None else {})

    def get(self, url: str, who: Actor | None = None, **params: Any) -> Any:
        return self.client.get(f"{V}{url}", headers=(who or self.fin).headers, params=params)

    def doc(self, url: str, who: Actor, category: str | None = None, content: bytes = PDF) -> str:
        r = self.client.post(f"{V}{url}", headers=who.headers, files={"file": ("e.pdf", content, "application/pdf")},
                             data={"category": category} if category else {})
        assert r.status_code == 201, r.text
        return str(r.json()["document_id"])

    def sale(self, qty: int = 100, price: str = "12.50", rng: str | None = None) -> dict:
        """A delivered order item (payment CONFIRMED + 9B transfer COMPLETED)."""
        if not getattr(self, "_buyer_ok", False):
            self.m.verify_buyer()
            self._buyer_ok = True
        lst = self.m.listing(qty, price, rng=rng or self.m.range600)
        od = self.m.purchase(lst["id"], qty)
        tr = od["items"][0]["transfer_id"]
        done = self.m.post(f"{ORD}/transfers/{tr}/complete", {}, self.m.qa)
        assert done.status_code == 200 and done.json()["status"] == "COMPLETED", done.text
        return done.json()

    def period_id(self) -> str:
        rows = self.get("/revenue", project_id=self.project_id).json()
        return str(rows[0]["monitoring_period_id"])

    def share(self, pct: str = "40", deduct: bool = True, rounding: str = "HALF_UP", approve: bool = True) -> dict:
        v = self.post("/revenue-share", {"project_id": self.project_id, "farmer_share_pct": pct, "deduct_approved_costs": deduct,
                                         "rounding_mode": rounding, "effective_from": "2026-01-01",
                                         "source_reference": "TEST benefit-sharing agreement BSA-1 §4"}, self.pm)
        assert v.status_code == 201, v.text
        if approve:
            assert self.post(f"/revenue-share/{v.json()['id']}/submit", {}, self.pm).status_code == 200
            a = self.post(f"/revenue-share/{v.json()['id']}/approve", {}, self.fin)
            assert a.status_code == 200, a.text
            return dict(a.json())
        return dict(v.json())

    def allocation(self, shares: list[str], approve: bool = True) -> dict:
        lines = [{"project_farm_id": str(pf.id), "share_pct": s} for pf, s in zip(self.pfs, shares, strict=False)]
        a = self.post("/allocations", {"project_id": self.project_id, "monitoring_period_id": self.period_id(),
                                       "basis_reference": "TEST farm allocation minutes 2026-10", "lines": lines}, self.pm)
        assert a.status_code == 201, a.text
        if approve:
            assert self.post(f"/allocations/{a.json()['id']}/submit", {}, self.pm).status_code == 200
            ap = self.post(f"/allocations/{a.json()['id']}/approve", {}, self.fin)
            assert ap.status_code == 200, ap.text
            return dict(ap.json())
        return dict(a.json())

    def cost(self, amount: str = "100.00", approve: bool = True, category: str = "FIELD_OPERATIONS") -> dict:
        c = self.post("/costs", {"project_id": self.project_id, "category": category, "description": "TEST soil sampling contractor",
                                 "amount": amount, "currency": "INR", "incurred_on": "2026-09-15"}, self.pm)
        assert c.status_code == 201, c.text
        if approve:
            self.doc(f"/costs/{c.json()['id']}/documents", self.pm)
            a = self.post(f"/costs/{c.json()['id']}/approve", {}, self.fin)
            assert a.status_code == 200, a.text
            return dict(a.json())
        return dict(c.json())

    def run(self, share: dict, alloc: dict, calculate: bool = True, approve: bool = True) -> Any:
        r = self.post("/settlements", {"project_id": self.project_id, "monitoring_period_id": alloc["monitoring_period_id"], "currency": "INR",
                                       "revenue_share_version_id": share["id"], "allocation_version_id": alloc["id"]}, self.fin2)
        assert r.status_code == 201, r.text
        if not calculate:
            return r.json()
        c = self.post(f"/settlements/{r.json()['id']}/calculate", {}, self.fin2)
        if c.status_code != 200 or not approve:
            return c
        assert self.post(f"/settlements/{r.json()['id']}/submit", {}, self.fin2).status_code == 200
        a = self.post(f"/settlements/{r.json()['id']}/approve", {}, self.fin3)
        assert a.status_code == 200, a.text
        return a.json()

    def bank(self, farmer_id: uuid.UUID, number: str = "0012 3456 7890", verify: bool = True) -> str:
        r = self.client.post(f"{V}/farmers/{farmer_id}/bank-accounts", headers=self.pm.headers,
                             json={"account_holder_name": "Asha Patil", "bank_name": "State Bank", "routing_code": "SBIN0001234",
                                   "account_number": number})
        assert r.status_code == 201, r.text
        acct = next(a for a in r.json()["bank_accounts"] if a["account_number_masked"].endswith(number.replace(" ", "")[-4:]))
        if verify:
            v = self.client.post(f"{V}/farmers/{farmer_id}/bank-accounts/{acct['id']}/decision", headers=self.fin.headers,
                                 json={"decision": "VERIFIED", "notes": "TEST penny drop"})
            assert v.status_code == 200, v.text
        return str(acct["id"])


def _perms(db: Session, role: str) -> set[str]:
    return {c for (c,) in db.execute(select(Permission.code).join(RolePermission, RolePermission.permission_id == Permission.id)
                                     .join(Role, Role.id == RolePermission.role_id).where(Role.code == role))
            if c.split(".")[0] in FIN_PREFIXES}


def _actions(db: Session, *actions: str) -> set[str]:
    return {a for (a,) in db.execute(select(AuditLog.action).where(AuditLog.action.in_(actions)))}


# ---------------------------------------------------------------- RBAC, no client-entered payout amounts, MANUAL only, no FLOAT
def test_rbac_matrix_manual_adapter_and_no_client_amounts(db: Session) -> None:
    assert _perms(db, "FINANCE_MANAGER") == {
        "revenue.read", "revenue.manage", "settlement.read", "settlement.calculate", "settlement.approve", "payouts.read", "payouts.calculate",
        "payouts.approve", "payouts.execute", "payouts.reconcile", "sharing.approve", "costs.manage", "costs.approve"}
    assert _perms(db, "PROJECT_MANAGER") == {"revenue.read", "settlement.read", "payouts.read", "sharing.manage", "costs.manage"}
    for r in ("FARMER", "BUYER", "QA_OFFICER", "VVB_REVIEWER", "LAB_TECHNICIAN", "CREDIT_MANAGER", "REGISTRY_MANAGER", "MARKETPLACE_COMPLIANCE"):
        assert _perms(db, r) == set(), r
    assert set(ADAPTERS) == {"MANUAL"}
    manual = ADAPTERS["MANUAL"]
    for call in (lambda: manual.create_payout(PayoutRequest("P", Decimal(1), "INR", "b", "k")), lambda: manual.get_status("x"),
                 lambda: manual.cancel_payout("x")):
        with pytest.raises(ManualActionRequired):
            call()
    from app.main import app
    schema = app.openapi()
    for path, ops in schema["paths"].items():
        if not path.startswith(("/api/v1/payouts", "/api/v1/settlements", "/api/v1/revenue")):
            continue
        for op in ops.values():
            ref = op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {}).get("$ref")
            if ref:
                props = schema["components"]["schemas"][ref.split("/")[-1]].get("properties", {})
                assert not {"amount", "farmer_total", "distributable", "entitlement", "gross_revenue"} & set(props), (path, props)
    assert not any("webhook" in p for p in schema["paths"])
    for t in FIN_TABLES:
        assert not any(isinstance(c.type, Float) for c in Base.metadata.tables[t].columns), t
    assert {c.name for c in Base.metadata.tables["payouts"].columns}.isdisjoint({"account_number", "account_number_enc", "routing_code"})


# ---------------------------------------------------------------- revenue: per item, idempotent, lineage, reversal
def test_revenue_recognized_per_item_idempotent_and_reversed_by_refund(client: TestClient, db: Session) -> None:
    f = F(client, db, 83.31, 28.31, "9610 2000 3000")
    od = f.sale(100, "12.50")
    rows = f.get("/revenue", project_id=f.project_id).json()
    assert len(rows) == 1
    r = rows[0]
    assert r["kind"] == "RECOGNITION" and Decimal(r["amount"]) == Decimal("1250.00") and r["currency"] == "INR"
    assert r["order_code"] == od["order_code"] and r["order_item_code"] == od["items"][0]["item_code"]
    assert r["payment_code"] and r["transfer_code"] and r["batch_code"] and r["settled_in_run_code"] is None
    item_id = od["items"][0]["id"]
    again = f.post("/revenue/recognize", {"order_item_id": item_id}, f.fin)
    assert again.status_code == 200 and again.json()["id"] == r["id"]                                    # idempotent
    assert db.scalar(select(func.count()).select_from(RevenueRecord).where(RevenueRecord.order_item_id == uuid.UUID(item_id))) == 1
    assert f.post("/revenue/recognize", {"order_item_id": item_id}, f.pm).status_code == 403                 # revenue.manage only
    # buyers and outsiders never see revenue
    assert f.get("/revenue", f.m.buyer, project_id=f.project_id).status_code == 403
    other = staff(db, client, make_org(db), "FINANCE_MANAGER")
    assert f.get("/revenue", other, project_id=f.project_id).status_code == 404
    picker = {p["id"]: p for p in f.get("/revenue/projects").json()}                                 # the finance project picker
    assert f.project_id in picker and len(picker[f.project_id]["farms"]) == len(f.pfs) and picker[f.project_id]["periods"]
    assert f.project_id not in {p["id"] for p in f.get("/revenue/projects", other).json()}
    # a completed refund after delivery creates a REVERSAL (the recognition is never edited)
    pay_id = f.m.get(f"{ORD}/{od['id']}", f.fin).json()["payments"][0]["id"]
    rf = f.m.post(f"{PAY}/{pay_id}/refunds", {"reason": "TEST: refund after delivery"}, f.fin).json()
    assert f.m.post(f"/api/v1/refunds/{rf['id']}/approve", {}, f.fin2).json()["status"] == "APPROVED"
    ev = f.m.upload(f"/api/v1/refunds/{rf['id']}/documents", f.fin).json()["document_id"]
    assert f.m.post(f"/api/v1/refunds/{rf['id']}/complete", {"external_reference": "TEST-RF-11", "document_id": ev}, f.fin).status_code == 200
    rows = f.get("/revenue", project_id=f.project_id).json()
    rev = next(x for x in rows if x["kind"] == "REVERSAL")
    assert Decimal(rev["amount"]) == Decimal("-1250.00") and rev["reverses_revenue_code"] == r["revenue_code"] and rev["refund_code"]
    assert f.post("/revenue/reverse-refund", {"refund_id": rf["id"]}, f.fin).json() == []                     # idempotent
    s = f.get("/revenue/summary", project_id=f.project_id).json()
    assert s["revenue"] == [{"currency": "INR", "recognized": "1250.0000", "reversed": "-1250.0000", "net": "0.0000"}]
    assert _actions(db, "REVENUE_RECOGNIZED", "REVENUE_REVERSED") == {"REVENUE_RECOGNIZED", "REVENUE_REVERSED"}
    orgs = {o for (o,) in db.execute(select(AuditLog.organization_id).where(AuditLog.action == "REVENUE_RECOGNIZED"))}
    assert f.m.seller.id in orgs


# ---------------------------------------------------------------- configuration: versioned, SoD, no defaults, allocation conservation
def test_sharing_versions_allocations_and_costs_are_controlled(client: TestClient, db: Session) -> None:
    f = F(client, db, 83.32, 28.32, "9620 2000 3000")
    f.sale(10, "5.00")
    base = {"project_id": f.project_id, "deduct_approved_costs": True, "rounding_mode": "HALF_UP", "effective_from": "2026-01-01",
            "source_reference": "TEST BSA-1"}
    for bad in ({**base, "farmer_share_pct": "0"}, {**base, "farmer_share_pct": "100.5"}, {k: v for k, v in base.items() if k != "rounding_mode"}
                | {"farmer_share_pct": "40"}, {**base, "farmer_share_pct": "40", "rounding_mode": "UP"}, {**base}):
        assert f.post("/revenue-share", bad, f.pm).status_code == 422, bad                                      # no default, no invented value
    assert f.post("/revenue-share", {**base, "farmer_share_pct": "40"}, f.fin).status_code == 403              # sharing.manage only
    v1 = f.post("/revenue-share", {**base, "farmer_share_pct": "40"}, f.pm, key="rs-1").json()
    assert f.post("/revenue-share", {**base, "farmer_share_pct": "40"}, f.pm, key="rs-1").json()["id"] == v1["id"]
    assert v1["status"] == "DRAFT" and v1["version_no"] == 1
    assert f.post(f"/revenue-share/{v1['id']}/approve", {}, f.fin).status_code == 409                          # must be IN_REVIEW
    f.post(f"/revenue-share/{v1['id']}/submit", {}, f.pm)
    dual = make_user(db, roles=[("PROJECT_MANAGER", f.m.seller), ("FINANCE_MANAGER", f.m.seller)])
    dual_a = Actor(dual, login(client, dual))
    v_dual = f.post("/revenue-share", {**base, "farmer_share_pct": "35"}, dual_a).json()
    f.post(f"/revenue-share/{v_dual['id']}/submit", {}, dual_a)
    assert codes(f.post(f"/revenue-share/{v_dual['id']}/approve", {}, dual_a)) == "SEPARATION_OF_DUTIES"
    assert f.post(f"/revenue-share/{v1['id']}/return", {"reason": "x"}, f.fin).status_code == 422                # a real reason
    ret = f.post(f"/revenue-share/{v1['id']}/return", {"reason": "TEST: cite the clause"}, f.fin).json()
    assert ret["status"] == "DRAFT" and ret["return_reason"] == "TEST: cite the clause"
    v1 = f.post(f"/revenue-share/{v1['id']}/submit", {}, f.pm).json()
    a1 = f.post(f"/revenue-share/{v1['id']}/approve", {}, f.fin)
    assert a1.json()["status"] == "APPROVED" and a1.json()["approved_by_name"]
    v2 = f.share("45")
    assert v2["version_no"] == 3 and {x["id"]: x["status"] for x in f.get("/revenue-share", project_id=f.project_id).json()}[v1["id"]] == \
        "SUPERSEDED"
    # allocation: every farm once, total exactly 100, only the project's farms
    pf1 = f.pfs[0]
    body = {"project_id": f.project_id, "monitoring_period_id": f.period_id(), "basis_reference": "TEST allocation"}
    dup = f.post("/allocations", {**body, "lines": [{"project_farm_id": str(pf1.id), "share_pct": "50"},
                                                    {"project_farm_id": str(pf1.id), "share_pct": "50"}]}, f.pm)
    assert codes(dup) == "DUPLICATE_FARM_ALLOCATION"
    assert f.post("/allocations", {**body, "lines": [{"project_farm_id": str(uuid.uuid4()), "share_pct": "100"}]}, f.pm).status_code == 404
    short = f.allocation(["40", "50"], approve=False)
    assert Decimal(short["total_pct"]) == Decimal("90")
    assert codes(f.post(f"/allocations/{short['id']}/submit", {}, f.pm)) == "ALLOCATION_NOT_CONSERVED"
    ok = f.allocation(["33.333333", "66.666667"])
    assert ok["status"] == "APPROVED" and Decimal(ok["total_pct"]) == Decimal("100") and len(ok["lines"]) == 2
    # costs: evidence (PDF), recorder ≠ approver, rejection reason, corrections are negative costs against an approved cost
    c = f.cost(approve=False)
    assert codes(f.post(f"/costs/{c['id']}/approve", {}, f.fin)) == "COST_EVIDENCE_REQUIRED"
    f.doc(f"/costs/{c['id']}/documents", f.pm)
    dual_c = f.post("/costs", {"project_id": f.project_id, "category": "TRANSPORT", "description": "TEST lorry hire", "amount": "10.00",
                               "currency": "INR", "incurred_on": "2026-09-01"}, dual_a).json()
    f.doc(f"/costs/{dual_c['id']}/documents", dual_a)
    assert codes(f.post(f"/costs/{dual_c['id']}/approve", {}, dual_a)) == "SEPARATION_OF_DUTIES"
    assert f.post(f"/costs/{c['id']}/approve", {}, f.fin).json()["status"] == "APPROVED"
    assert codes(f.post("/costs", {"project_id": f.project_id, "category": "X1", "description": "TEST bad correction", "amount": "-5.00",
                                   "currency": "INR", "incurred_on": "2026-09-01"}, f.pm)) == "CORRECTION_TARGET_REQUIRED"
    corr = f.post("/costs", {"project_id": f.project_id, "category": "FIELD_OPERATIONS", "description": "TEST correction", "amount": "-20.00",
                             "currency": "INR", "incurred_on": "2026-09-01", "corrects_cost_id": c["id"]}, f.pm)
    assert corr.status_code == 201 and Decimal(corr.json()["amount"]) == Decimal("-20.00")
    assert codes(f.post("/costs", {"project_id": f.project_id, "category": "X1", "description": "TEST odd precision", "amount": "1.001",
                                   "currency": "INR", "incurred_on": "2026-09-01"}, f.pm)) == "INVALID_AMOUNT"
    assert f.post(f"/costs/{dual_c['id']}/reject", {"reason": "TEST: duplicate invoice"}, f.fin).json()["status"] == "REJECTED"
    assert _actions(db, "REVENUE_SHARE_RULE_APPROVED", "ALLOCATION_APPROVED", "PROJECT_COST_APPROVED", "PROJECT_COST_REJECTED") == {
        "REVENUE_SHARE_RULE_APPROVED", "ALLOCATION_APPROVED", "PROJECT_COST_APPROVED", "PROJECT_COST_REJECTED"}


# ---------------------------------------------------------------- settlement → payout → execution → reconciliation (end to end)
def test_settlement_payout_execution_and_reconciliation_lifecycle(client: TestClient, db: Session) -> None:
    f = F(client, db, 83.33, 28.33, "9630 2000 3000")
    f.sale(100, "12.50")                                                                              # 1250.00 INR recognized
    share = f.share("40", deduct=True, rounding="HALF_UP")
    unapproved = f.allocation(["33.333333", "66.666667"], approve=False)
    assert codes(f.post("/settlements", {"project_id": f.project_id, "monitoring_period_id": unapproved["monitoring_period_id"],
                                         "currency": "INR", "revenue_share_version_id": share["id"],
                                         "allocation_version_id": unapproved["id"]}, f.fin2)) == "ALLOCATION_NOT_APPROVED"
    alloc = f.allocation(["33.333333", "66.666667"])
    f.cost("100.00")
    f.cost("999.00", approve=False)                                                                   # pending costs are never deducted
    draft = f.run(share, alloc, calculate=False)
    assert draft["status"] == "DRAFT" and draft["gross_revenue"] is None
    calc = f.post(f"/settlements/{draft['id']}/calculate", {}, f.fin2, key="calc-1")
    assert calc.status_code == 200, calc.text
    r = calc.json()
    assert f.post(f"/settlements/{draft['id']}/calculate", {}, f.fin2, key="calc-1").json()["input_sha256"] == r["input_sha256"]
    assert (Decimal(r["gross_revenue"]), Decimal(r["deducted_costs"]), Decimal(r["distributable"])) == (Decimal("1250"), Decimal("100"),
                                                                                                        Decimal("1150"))
    # 1150 × 40% = 460; 460 × 33.333333% = 153.3333318 → 153.33; 460 × 66.666667% = 306.6666682 → 306.67 (HALF_UP, 2 decimals for INR)
    assert sorted(Decimal(e["amount"]) for e in r["entitlements"]) == [Decimal("153.33"), Decimal("306.67")]
    assert Decimal(r["farmer_total"]) == Decimal("460") and Decimal(r["developer_residual"]) == Decimal("690")
    assert r["calculation_version"] == "fin-calc-1" and len(r["input_sha256"]) == 64 and r["revenue_count"] == 1 and r["cost_count"] == 1
    v = f.get(f"/settlements/{r['id']}/verify").json()
    assert v["reproducible"] is True and v["hash_ok"] and v["figures_ok"] and v["entitlements_ok"] and v["inputs_ok"]
    snap = json.loads(db.get(SettlementRun, uuid.UUID(r["id"])).input_snapshot)
    assert snap["inputs"]["revenue_share_version"]["farmer_share_pct"] == "40.000000" and len(snap["inputs"]["costs"]) == 1
    # the inputs are claimed: a second run has nothing to settle; the calculator never approves
    other = f.run(share, alloc, approve=False)
    assert codes(other) == "NOTHING_TO_SETTLE"
    f.post(f"/settlements/{r['id']}/submit", {}, f.fin2)
    assert codes(f.post(f"/settlements/{r['id']}/approve", {}, f.fin2)) == "SEPARATION_OF_DUTIES"
    assert codes(f.post(f"/payouts/from-settlement/{r['id']}", {}, f.fin2)) == "SETTLEMENT_NOT_APPROVED"
    assert f.post(f"/settlements/{r['id']}/approve", {}, f.fin3).json()["status"] == "APPROVED"
    # payouts: one per farmer = Σ the farmer's entitlement lines (both farms belong to one farmer here)
    pos = f.post(f"/payouts/from-settlement/{r['id']}", {}, f.fin2).json()
    assert len(pos) == 1 and Decimal(pos[0]["amount"]) == Decimal("460.00") and pos[0]["status"] == "CALCULATED"
    assert f.post(f"/payouts/from-settlement/{r['id']}", {}, f.fin2).json() == []                     # idempotent
    po = pos[0]
    farmer_id = uuid.UUID(po["farmer_id"])
    f.post(f"/payouts/{po['id']}/submit", {}, f.fin2)
    assert codes(f.post(f"/payouts/{po['id']}/approve", {}, f.fin2)) == "SEPARATION_OF_DUTIES"          # calculator ≠ approver
    assert codes(f.post(f"/payouts/{po['id']}/approve", {}, f.fin3)) == "BANK_ACCOUNT_NOT_VERIFIED"
    acct1 = f.bank(farmer_id)
    ap = f.post(f"/payouts/{po['id']}/approve", {}, f.fin3)
    assert ap.json()["status"] == "APPROVED" and ap.json()["bank_last4"] == "7890", ap.text
    # bank account changed after approval → ON_HOLD (BANK_ACCOUNT_CHANGED), never paid to a stale account
    assert client.post(f"{V}/farmers/{farmer_id}/bank-accounts/{acct1}/deactivate", headers=f.pm.headers,
                       json={"reason": "TEST: farmer closed the account"}).status_code == 200
    assert codes(f.post(f"/payouts/{po['id']}/initiate", {}, f.fin3)) == "SEPARATION_OF_DUTIES"         # approver ≠ executor
    held = f.post(f"/payouts/{po['id']}/initiate", {}, f.fin4)
    assert held.status_code == 409 and codes(held) == "BANK_ACCOUNT_CHANGED"
    assert f.get(f"/payouts/{po['id']}").json()["status"] == "ON_HOLD"
    assert f.post(f"/payouts/{po['id']}/release-hold", {"reason": "TEST: new account provided"}, f.fin2).json()["status"] == "PENDING_APPROVAL"
    f.bank(farmer_id, "9988 7766 5544")
    assert f.post(f"/payouts/{po['id']}/approve", {}, f.fin3).json()["bank_last4"] == "5544"
    ini = f.post(f"/payouts/{po['id']}/initiate", {}, f.fin4, key="ini-1")
    assert ini.json()["status"] == "PAYMENT_PENDING" and ini.json()["adapter_code"] == "MANUAL", ini.text
    assert codes(f.post(f"/payouts/{po['id']}/query-status", {}, f.fin4)) == "MANUAL_ACTION_REQUIRED"
    # MANUAL execution: bank reference + remittance evidence (PDF) → PAID (not RECONCILED)
    with pytest.raises(AssertionError):
        f.doc(f"/payouts/{po['id']}/documents", f.fin4, "RECONCILIATION_EVIDENCE")                     # not yet PAID
    assert f.post(f"/payouts/{po['id']}/confirm-paid", {"external_reference": "TEST-NEFT-1", "document_id": str(uuid.uuid4())},
                  f.fin4).status_code == 422
    ev = f.doc(f"/payouts/{po['id']}/documents", f.fin4, "PAYOUT_EVIDENCE")
    paid = f.post(f"/payouts/{po['id']}/confirm-paid", {"external_reference": "TEST-NEFT-1", "document_id": ev}, f.fin4, key="paid-1")
    assert paid.json()["status"] == "PAID" and paid.json()["reconciled_at"] is None, paid.text
    assert f.get(f"/settlements/{r['id']}").json()["status"] == "APPROVED"                            # PAID is not RECONCILED
    # reconciliation by someone else; mismatch → EXCEPTION; a resolution note after an exception may match a reference mismatch only
    st = f.doc(f"/payouts/{po['id']}/documents", f.fin, "RECONCILIATION_EVIDENCE")
    stmt = {"statement_reference": "TEST-NEFT-1", "statement_amount": "460.00", "statement_currency": "INR", "statement_date": "2026-10-03",
            "document_id": st}
    assert codes(f.post(f"/payouts/{po['id']}/reconcile", stmt, f.fin4)) == "SEPARATION_OF_DUTIES"
    assert f.post(f"/payouts/{po['id']}/reconcile", {**stmt, "statement_amount": "406.00"}, f.fin).json()["result"] == "EXCEPTION"
    assert f.post(f"/payouts/{po['id']}/reconcile", {**stmt, "statement_reference": "NEFT 1"}, f.fin).json()["result"] == "EXCEPTION"
    assert f.post(f"/payouts/{po['id']}/reconcile", {**stmt, "statement_amount": "406.00", "note": "TEST typo"}, f.fin).json()["result"] == \
        "EXCEPTION"                                                                                    # money never matched by a note
    m = f.post(f"/payouts/{po['id']}/reconcile", {**stmt, "statement_reference": "NEFT 1", "note": "TEST: bank shortened the reference"}, f.fin)
    assert m.json()["result"] == "MATCHED", m.text
    final = f.get(f"/payouts/{po['id']}").json()
    assert final["status"] == "RECONCILED" and len(final["reconciliations"]) == 4
    assert [t["kind"] for t in final["transactions"]] == ["INITIATED", "PAID"]
    assert f.get(f"/settlements/{r['id']}").json()["status"] == "COMPLETED"
    # lineage payout → entitlements → run → configuration → revenue → Phase 10 / 9B
    lin = f.get(f"/payouts/{po['id']}/lineage").json()
    assert lin["settlement_run"]["input_sha256"] == r["input_sha256"] and len(lin["farmer_entitlements"]) == 2
    assert lin["revenue"][0]["order_code"] and lin["revenue"][0]["transfer_code"] and lin["revenue_share_version"]["source_reference"]
    # no bank credential anywhere in audit
    leaked = [v for (v,) in db.execute(select(AuditLog.new_value).where(AuditLog.entity_type == "payout"))
              if v and ("998877665544" in v or "SBIN" in v or "account_number" in v)]
    assert leaked == []
    assert _actions(db, "SETTLEMENT_CALCULATED", "SETTLEMENT_APPROVED", "SETTLEMENT_COMPLETED", "PAYOUT_CALCULATED", "PAYOUT_APPROVED",
                    "PAYOUT_ON_HOLD", "PAYOUT_INITIATED", "PAYOUT_PAID", "PAYOUT_RECONCILIATION_EXCEPTION", "PAYOUT_RECONCILED") == {
        "SETTLEMENT_CALCULATED", "SETTLEMENT_APPROVED", "SETTLEMENT_COMPLETED", "PAYOUT_CALCULATED", "PAYOUT_APPROVED", "PAYOUT_ON_HOLD",
        "PAYOUT_INITIATED", "PAYOUT_PAID", "PAYOUT_RECONCILIATION_EXCEPTION", "PAYOUT_RECONCILED"}
    # farmer self-service: own payouts only, last 4 only
    group = make_org(db, org_type="FARMER_GROUP")
    fu = make_user(db, roles=[("FARMER", group)])
    assert client.post(f"{V}/farmers/{farmer_id}/link-user", headers=f.pm.headers, json={"user_id": str(fu.id)}).status_code == 200
    me = client.get(f"{V}/payouts/me", headers=login(client, fu)).json()
    assert me["farmer_linked"] is True and [p["payout_code"] for p in me["payouts"]] == [po["payout_code"]]
    assert set(me["payouts"][0]) == {"payout_code", "amount", "currency", "status", "project_code", "period_number", "bank_last4", "paid_at",
                                     "reconciled_at", "calculated_at"}
    assert client.get(f"{V}/payouts", headers=login(client, fu)).status_code == 403
    stranger = make_user(db, roles=[("FARMER", make_org(db, org_type="FARMER_GROUP"))])
    assert client.get(f"{V}/payouts/me", headers=login(client, stranger)).json() == {
        "farmer_linked": False, "payouts": [], "note": "Your account is not linked to a farmer profile; ask your project developer."}
    # summary
    s = f.get("/revenue/summary", project_id=f.project_id).json()
    assert s["settlements"] == [{"currency": "INR", "distributable": "1150.0000", "farmer_total": "460.0000", "developer_residual": "690.0000"}]
    assert s["payouts_by_status"] == [{"status": "RECONCILED", "count": 1, "amounts": [{"currency": "INR", "amount": "460.0000"}]}]
    assert {c["category"] for c in s["costs_by_category"]} == {"FIELD_OPERATIONS"}


# ---------------------------------------------------------------- refunds after payout → recovery case; rejection frees inputs; reissue
def test_refund_after_payout_opens_recovery_case_and_rejected_runs_free_inputs(client: TestClient, db: Session) -> None:
    f = F(client, db, 83.34, 28.34, "9640 2000 3000")
    od = f.sale(40, "10.00")                                                                          # 400.00 INR
    share = f.share("50", deduct=False, rounding="DOWN")
    alloc = f.allocation(["50", "50"])
    c = f.run(share, alloc, approve=False).json()
    f.post(f"/settlements/{c['id']}/submit", {}, f.fin2)
    rej = f.post(f"/settlements/{c['id']}/reject", {"reason": "TEST: recheck the allocation basis"}, f.fin3)
    assert rej.json()["status"] == "REJECTED"
    assert codes(f.post(f"/settlements/{c['id']}/approve", {}, f.fin3)) == "INVALID_STATUS_TRANSITION"           # REJECTED is final
    r = f.run(share, alloc)                                                                           # the rejected run freed its inputs
    assert r["status"] == "APPROVED" and Decimal(r["farmer_total"]) == Decimal("200") and Decimal(r["deducted_costs"]) == 0
    po = f.post(f"/payouts/from-settlement/{r['id']}", {}, f.fin2).json()[0]
    farmer_id = uuid.UUID(po["farmer_id"])
    f.bank(farmer_id, "1111 2222 3333")
    f.post(f"/payouts/{po['id']}/submit", {}, f.fin2)
    f.post(f"/payouts/{po['id']}/approve", {}, f.fin3)
    f.post(f"/payouts/{po['id']}/initiate", {}, f.fin4)
    failed = f.post(f"/payouts/{po['id']}/fail", {"reason": "TEST: beneficiary bank returned the transfer"}, f.fin4)
    assert failed.json()["status"] == "FAILED"
    assert codes(f.post(f"/payouts/{po['id']}/fail", {"reason": "TEST again"}, f.fin4)) == "INVALID_STATUS_TRANSITION"   # FAILED is final
    re = f.post(f"/payouts/{po['id']}/reissue", {}, f.fin2, key="re-1")
    assert re.status_code == 201 and re.json()["replaces_payout_code"] == po["payout_code"] and Decimal(re.json()["amount"]) == Decimal("200")
    assert f.post(f"/payouts/{po['id']}/reissue", {}, f.fin2, key="re-1").json()["id"] == re.json()["id"]
    p2 = re.json()
    f.post(f"/payouts/{p2['id']}/submit", {}, f.fin2)
    f.post(f"/payouts/{p2['id']}/approve", {}, f.fin3)
    f.post(f"/payouts/{p2['id']}/initiate", {}, f.fin4)
    ev = f.doc(f"/payouts/{p2['id']}/documents", f.fin4, "PAYOUT_EVIDENCE")
    assert f.post(f"/payouts/{p2['id']}/confirm-paid", {"external_reference": "TEST-NEFT-2", "document_id": ev}, f.fin4).json()["status"] == "PAID"
    # refund after the payout left: a REVERSAL is recorded and a recovery case opened — no clawback, no negative payout
    pay_id = f.m.get(f"{ORD}/{od['id']}", f.fin).json()["payments"][0]["id"]
    rf = f.m.post(f"{PAY}/{pay_id}/refunds", {"reason": "TEST: refund after payout"}, f.fin).json()
    f.m.post(f"/api/v1/refunds/{rf['id']}/approve", {}, f.fin2)
    rev = f.m.upload(f"/api/v1/refunds/{rf['id']}/documents", f.fin).json()["document_id"]
    f.m.post(f"/api/v1/refunds/{rf['id']}/complete", {"external_reference": "TEST-RF-12", "document_id": rev}, f.fin)
    nxt = f.run(share, alloc, approve=False)
    assert codes(nxt) == "NOTHING_TO_SETTLE" and nxt.json()["details"]["recovery_cases_opened"] == 1
    cases = f.get("/payouts/adjustments", project_id=f.project_id).json()
    assert len(cases) == 1 and cases[0]["status"] == "OPEN" and Decimal(cases[0]["amount"]) == Decimal("-400")
    assert cases[0]["original_run_code"] == r["run_code"]
    assert f.get(f"/payouts/{p2['id']}").json()["status"] == "PAID"                                    # the paid payout is untouched
    assert codes(f.post(f"/payouts/adjustments/{cases[0]['id']}/close", {"resolution": "TEST: n/a"}, f.pm)) == "PERMISSION_DENIED"
    closed = f.post(f"/payouts/adjustments/{cases[0]['id']}/close", {"resolution": "TEST: offset agreed in writing with the farmer group"}, f.fin)
    assert closed.json()["status"] == "CLOSED" and closed.json()["resolution"]
    assert f.run(share, alloc, approve=False).json()["error_code"] == "NOTHING_TO_SETTLE"               # one case per reversal
    assert db.scalar(select(func.count()).select_from(PayoutAdjustment)) >= 1
    assert db.scalar(select(func.count()).select_from(Payout).where(Payout.amount <= 0)) == 0


# ---------------------------------------------------------------- reversal before execution is netted in the next run
def test_reversal_before_payout_is_netted_in_the_next_run(client: TestClient, db: Session) -> None:
    f = F(client, db, 83.35, 28.35, "9650 2000 3000")
    od1 = f.sale(20, "10.00")                                                                         # 200.00
    share = f.share("50", deduct=False, rounding="HALF_EVEN")
    alloc = f.allocation(["50", "50"])
    r1 = f.run(share, alloc)
    assert Decimal(r1["gross_revenue"]) == Decimal("200")
    pay_id = f.m.get(f"{ORD}/{od1['id']}", f.fin).json()["payments"][0]["id"]
    rf = f.m.post(f"{PAY}/{pay_id}/refunds", {"reason": "TEST: refund before payout"}, f.fin).json()
    f.m.post(f"/api/v1/refunds/{rf['id']}/approve", {}, f.fin2)
    ev = f.m.upload(f"/api/v1/refunds/{rf['id']}/documents", f.fin).json()["document_id"]
    f.m.post(f"/api/v1/refunds/{rf['id']}/complete", {"external_reference": "TEST-RF-13", "document_id": ev}, f.fin)
    assert codes(f.run(share, alloc, approve=False)) == "NEGATIVE_DISTRIBUTABLE"                       # never a negative entitlement
    f.sale(50, "10.00", rng=f.m.range400)                                                             # +500.00 (another listing)
    r2 = f.run(share, alloc)
    assert Decimal(r2["gross_revenue"]) == Decimal("300") and Decimal(r2["farmer_total"]) == Decimal("150")
    assert f.get("/payouts/adjustments", project_id=f.project_id).json() == []


# ---------------------------------------------------------------- TEST adapter (service layer only): timeout → UNCONFIRMED → status query
def test_test_payout_adapter_timeout_and_status_query(client: TestClient, db: Session) -> None:
    f = F(client, db, 83.36, 28.36, "9660 2000 3000")
    f.sale(10, "10.00")
    r = f.run(f.share("100", deduct=False, rounding="DOWN"), f.allocation(["50", "50"]))
    po = f.post(f"/payouts/from-settlement/{r['id']}", {}, f.fin2).json()[0]
    f.bank(uuid.UUID(po["farmer_id"]), "4444 5555 6666")
    f.post(f"/payouts/{po['id']}/submit", {}, f.fin2)
    f.post(f"/payouts/{po['id']}/approve", {}, f.fin3)
    adapter = TestPayoutAdapter()
    adapter.timeout_next = True
    p4 = load_principal(db, f.fin4.user, None)
    ctx = RequestContext(user_id=f.fin4.user.id)
    x = pys.initiate(db, ctx, p4, uuid.UUID(po["id"]), None, adapter=adapter)
    assert x.status == "UNCONFIRMED" and x.adapter_code == "TEST"
    adapter.settle(f"TPYT-{x.payout_code}", "PAID")
    x = pys.query_status(db, ctx, p4, x.id, adapter=adapter)
    assert x.status == "PAID" and x.external_reference == f"TPYT-{x.payout_code}"
    with pytest.raises(Conflict):
        pys.query_status(db, ctx, p4, x.id, adapter=adapter)                                         # no longer pending
    assert {t.kind for t in pys.transactions(db, x.id)} == {"INITIATED", "UNCONFIRMED", "PAID"}


# ---------------------------------------------------------------- deterministic rounding (pure calculation)
def test_rounding_policy_is_deterministic_per_version() -> None:
    def inputs(mode: str, currency: str, amount: str, pct: str, shares: list[str]) -> dict:
        return {"currency": currency, "revenue_share_version": {"farmer_share_pct": pct, "deduct_approved_costs": False, "rounding_mode": mode},
                "revenue": [{"amount": amount}], "costs": [],
                "allocation": {"lines": [{"allocation_line_id": f"l{i}", "farmer_id": f"f{i}", "share_pct": s} for i, s in enumerate(shares)]}}
    half_up = ss.calculate_figures(inputs("HALF_UP", "INR", "0.05", "50", ["50", "50"]))              # 0.0125 → 0.01 each
    assert [e["amount"] for e in half_up["entitlements"]] == ["0.01", "0.01"] and half_up["developer_residual"] == "0.03"
    even = ss.calculate_figures(inputs("HALF_EVEN", "INR", "0.10", "50", ["50", "50"]))               # 0.025 → 0.02
    up = ss.calculate_figures(inputs("HALF_UP", "INR", "0.10", "50", ["50", "50"]))                   # 0.025 → 0.03
    down = ss.calculate_figures(inputs("DOWN", "INR", "0.10", "50", ["50", "50"]))                    # 0.025 → 0.02
    assert [e["amount"] for e in even["entitlements"]] == ["0.02", "0.02"]
    assert [e["amount"] for e in up["entitlements"]] == ["0.03", "0.03"]
    assert [e["amount"] for e in down["entitlements"]] == ["0.02", "0.02"]
    jpy = ss.calculate_figures(inputs("DOWN", "JPY", "1000", "33.333333", ["100"]))                    # zero minor units
    assert jpy["entitlements"][0]["amount"] == "333" and jpy["developer_residual"] == "667"
    over = ss.calculate_figures(inputs("HALF_UP", "INR", "0.01", "100", ["50", "50"]))                # 0.005 → 0.01 each: exceeds
    assert Decimal(over["developer_residual"]) < 0                                                     # the service refuses this run
    assert ss.calculate_figures(inputs("DOWN", "INR", "0.10", "50", ["50", "50"])) == down             # same inputs → same figures


# ---------------------------------------------------------------- DEMO: no financial record; outsiders refused
def test_demo_projects_are_refused_and_demo_users_see_empty_states(client: TestClient, db: Session) -> None:
    c = locked_project(db, client, 83.37, 28.37, "9670 2000 3000")
    p = db.get(Project, uuid.UUID(c.project["id"]))
    assert p is not None
    p.environment = "DEMO"                                                                            # (inside the rolled-back test transaction)
    db.flush()
    fin = staff(db, client, c.t.org, "FINANCE_MANAGER")
    body = {"project_id": str(p.id), "farmer_share_pct": "40", "deduct_approved_costs": False, "rounding_mode": "DOWN",
            "effective_from": "2026-01-01", "source_reference": "TEST"}
    r = client.post(f"{V}/revenue-share", headers=c.t.pm.headers, json=body)
    assert r.status_code == 409 and r.json()["error_code"] == "DEMO_FINANCE_NOT_ALLOWED"
    r = client.post(f"{V}/costs", headers=c.t.pm.headers, json={"project_id": str(p.id), "category": "X1", "description": "TEST demo",
                                                                "amount": "1.00", "currency": "INR", "incurred_on": "2026-09-01"})
    assert r.json()["error_code"] == "DEMO_FINANCE_NOT_ALLOWED"
    assert client.get(f"{V}/revenue", headers=fin.headers, params={"project_id": str(p.id)}).json() == []
    demo_org = make_org(db, environment="DEMO")
    du = make_user(db, roles=[("FINANCE_MANAGER", demo_org)], environment="DEMO")
    dh = login(client, du)
    assert client.get(f"{V}/settlements", headers=dh).json() == [] and client.get(f"{V}/payouts", headers=dh).json() == []
    s = client.get(f"{V}/revenue/summary", headers=dh).json()
    assert s["revenue"] == [] and s["payouts_by_status"] == [] and s["demo_note"] == fs.DEMO_NOTE
    for t in ("revenue_records", "settlement_runs", "payouts"):
        model = {"revenue_records": RevenueRecord, "settlement_runs": SettlementRun, "payouts": Payout}[t]
        assert db.scalar(select(func.count()).select_from(model).where(model.environment == "DEMO")) == 0
    for role, org_type in (("VVB_REVIEWER", "VVB"), ("LAB_TECHNICIAN", "LABORATORY"), ("BUYER", "BUYER"), ("QA_OFFICER", "PROJECT_DEVELOPER")):
        a = staff(db, client, make_org(db, org_type=org_type), role)
        for url in ("/revenue/summary", "/settlements", "/payouts", "/payouts/adjustments"):
            assert client.get(f"{V}{url}", headers=a.headers).status_code == 403, (role, url)


def test_bank_details_are_referenced_not_copied(db: Session) -> None:
    cols = {c.name for c in Base.metadata.tables["payouts"].columns}
    assert {"bank_account_id", "bank_last4"} <= cols
    fk = next(iter(Base.metadata.tables["payouts"].c.bank_account_id.foreign_keys))
    assert fk.column.table.name == FarmerBankAccount.__tablename__


def test_downgrade_guard_refuses_while_phase_11_rows_exist() -> None:
    import pathlib

    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from app.core.database import get_engine
    src = (pathlib.Path(__file__).parents[1] / "alembic" / "versions" / "20261003_0016_phase11_financials.py").read_text(encoding="utf-8")
    guard = src.split("def downgrade() -> None:")[1].split('op.execute("""')[1].split('""")')[0]
    with get_engine().connect() as c:
        t = c.begin()
        session = Session(bind=c, join_transaction_mode="create_savepoint")
        try:
            assert "Downgrade refused" in guard
            c.execute(text(guard))                                                                    # empty finance tables → allowed
            org = make_org(session)
            user = make_user(session)
            session.add(Document(entity_type="project_cost", entity_id=uuid.uuid4(), organization_id=org.id, category="COST_EVIDENCE",
                                 title="GUARD", environment="LIVE", sensitivity="INTERNAL", created_by=user.id))
            session.flush()
            with pytest.raises(DBAPIError) as e:
                c.execute(text(guard))
            assert "Downgrade refused" in str(e.value)
        finally:
            session.close()
            if t.is_active:
                t.rollback()
