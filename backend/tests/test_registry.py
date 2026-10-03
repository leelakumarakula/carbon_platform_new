"""Phase 9A — registry submission & credit issuance (no inventory, ownership, reservation, transfer or retirement).

Eligibility (VVB decision, verified quantity, registration, account, registry, environment, one open submission per period, checklist),
the frozen registry-submission-v1 snapshot, the manual workflow (evidence-backed references), API-mode submission with idempotency,
timeout-after-success and reconciliation (TEST-only adapter injected into the service layer), registry rejection / acceptance, issuance
with dual confirmation, tranches, the issued ≤ verified invariant with explicit unit equivalence, whole units, registry serials (verbatim,
duplicates, parser-based length / overlap), correction and cancellation history, multi-period isolation, recalculation, the aggregate
project status, lineage, audit, RBAC, environment isolation, DEMO (no issuance) and the database triggers. Successful paths run on the
TEST-only Phase 7 fixture and Phase 8B decisions inside the rolled-back test database."""
import uuid
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calculation import framework as fw
from app.core.config import get_settings
from app.core.errors import AppError
from app.integrations.registry import ADAPTERS, ExternalBatch, ExternalIssuance, ExternalSerialRange
from app.models import (
    AuditLog,
    CreditBatch,
    CreditIssuance,
    Organization,
    Permission,
    Project,
    RegistryAccount,
    RegistryEvent,
    RegistrySubmission,
    Role,
    RolePermission,
    VerificationDecision,
)
from app.schemas.registry import IssuanceIn
from app.services import credit_issuance as ci
from app.services import registry_service as rs
from tests.calc_fixture import CalcCtx, as_principal, calc_scenario
from tests.conftest import Actor, login, make_org, make_user
from tests.phase2 import staff
from tests.registry_fixture import TestRegistryAdapter
from tests.test_preverification import _dedicated, _recalc
from tests.test_verification import COI, VVB, _decide, _ready, _submitted, _vvb

R = "/api/v1/registry"
C = "/api/v1/credits"
V = "/api/v1/verification"
PDF = b"%PDF-1.4\n%TEST registry document\n%%EOF\n"
CHECKLIST = [{"code": "PDD", "title": "Project description (as required by this TEST registry)", "source": "REGISTRY_SUBMISSION"},
             {"code": "VR", "title": "Verification report", "source": "VERIFICATION_REPORT"}]


class Reg:
    """A project with a CURRENT VERIFIED VVB decision (stated quantity) and a REGISTERED registration at a TEST registry."""

    def __init__(self, client: TestClient, db: Session, k: CalcCtx, quantity: str | None = "1000", checklist: list | None = CHECKLIST,
                 equivalence: bool = True) -> None:
        self.client, self.db, self.k = client, db, k
        self.org = k.x.c.t.org
        self.rm = staff(db, client, self.org, "REGISTRY_MANAGER")           # records
        self.qa = k.qa                                                       # QA officer: registry.confirm
        self.registry = make_org(db, org_type="REGISTRY")
        self.account = self.post(f"{R}/accounts", {
            "organization_id": str(self.org.id), "registry_organization_id": str(self.registry.id), "external_account_id": f"TEST-ACC-{uuid.uuid4().hex[:6]}",
            "label": "TEST registry account", "credit_unit": "TCU" if equivalence else None,
            "verified_unit_equivalent": "tCO2e" if equivalence else None, "document_checklist": checklist}).json()
        self.registration = self.register(self.account["id"])
        if quantity is not None:
            self.run, self.decision = verified(client, db, k, quantity)

    def post(self, url: str, body: dict | None = None, who: Actor | None = None, **kw: Any) -> Any:
        return self.client.post(url, headers={**(who or self.rm).headers, **kw.pop("headers", {})}, json=body if body is not None else {}, **kw)

    def doc(self, url: str, category: str, who: Actor | None = None, **data: str) -> str:
        r = self.client.post(url, headers=(who or self.rm).headers, files={"file": ("d.pdf", PDF, "application/pdf")},
                             data={"category": category, **data})
        assert r.status_code == 201, r.text
        return str(r.json()["document_id"])

    def register(self, account_id: str, external: str | None = None) -> dict:
        reg = self.post(f"{R}/projects/{self.k.project_id}/registrations", {"registry_account_id": account_id}).json()
        evidence = self.doc(f"{R}/registrations/{reg['id']}/documents", "REGISTRY_RESPONSE")
        r = self.post(f"{R}/registrations/{reg['id']}/record-registered",
                      {"external_project_id": external or f"TEST-PRJ-{uuid.uuid4().hex[:6]}", "registered_on": "2026-09-01", "document_id": evidence})
        assert r.status_code == 200, r.text
        return r.json()

    def create(self, period_id: str | None = None, account_id: str | None = None, **kw: Any) -> Any:
        return self.post(f"{R}/projects/{self.k.project_id}/submissions",
                         {"monitoring_period_id": period_id or self.k.period_id, "registry_account_id": account_id or self.account["id"], **kw})

    def frozen(self) -> dict:
        s = self.create()
        assert s.status_code == 201, s.text
        sid = s.json()["id"]
        self.doc(f"{R}/submissions/{sid}/documents", "REGISTRY_SUBMISSION", checklist_item="PDD")
        f = self.post(f"{R}/submissions/{sid}/freeze")
        assert f.status_code == 200, f.text
        return f.json()

    def submitted(self, sid: str, external: str = "TEST-SUB-1") -> Any:
        receipt = self.doc(f"{R}/submissions/{sid}/documents", "REGISTRY_RESPONSE")
        return self.post(f"{R}/submissions/{sid}/record-submitted", {"external_submission_id": external, "document_id": receipt})

    def accepted(self, external: str = "TEST-SUB-1") -> dict:
        sid = self.frozen()["id"]
        assert self.submitted(sid, external).json()["status"] == "SUBMITTED"
        ev = self.doc(f"{R}/submissions/{sid}/documents", "REGISTRY_RESPONSE")
        r = self.post(f"{R}/submissions/{sid}/record-response", {"outcome": "ACCEPTED", "document_id": ev, "external_response_ref": "TEST-ACK"})
        assert r.json()["status"] == "ACCEPTED", r.text
        return r.json()

    def issue(self, sid: str, quantity: int, ext: str, batches: list | None = None, unit: str = "TCU", key: str | None = None, **kw: Any) -> Any:
        stmt = self.doc(f"{R}/submissions/{sid}/documents", "ISSUANCE_STATEMENT")
        body = {"external_issuance_id": ext, "issuance_date": "2026-10-01", "quantity": quantity, "unit": unit, "document_id": stmt,
                "batches": batches or [{"vintage": "2026", "quantity": quantity, "serial_ranges": [{"quantity": quantity}]}], **kw}
        return self.post(f"{R}/submissions/{sid}/issuances", body, headers={"Idempotency-Key": key} if key else {})

    def confirm(self, issuance_id: str, who: Actor | None = None) -> Any:
        return self.post(f"{R}/issuances/{issuance_id}/confirm", {"note": "checked against the registry statement"}, who=who or self.qa)

    def view(self, period_id: str | None = None) -> dict:
        r = self.client.get(f"{R}/projects/{self.k.project_id}/periods/{period_id or self.k.period_id}", headers=self.rm.headers)
        assert r.status_code == 200, r.text
        return r.json()


def verified(client: TestClient, db: Session, k: CalcCtx, quantity: str | None = "1000") -> tuple[Any, dict]:
    _, s, _, v1, _, run = _submitted(client, db, k)
    d = _decide(client, v1, s["id"], **({"verified_quantity": quantity, "verified_quantity_unit": "tCO2e"} if quantity else {}))
    assert d.status_code == 201, d.text
    return run, d.json()


def codes(r: Any) -> str:
    return str(r.json().get("error_code"))


def _project(db: Session, k: CalcCtx) -> Project:
    p = db.get(Project, uuid.UUID(k.project_id))
    assert p is not None
    db.refresh(p)
    return p


def _actions(db: Session, entity_type: str) -> set[str]:
    return {a for (a,) in db.execute(select(AuditLog.action).where(AuditLog.entity_type == entity_type))}


# ---------------------------------------------------------------- RBAC matrix, API surface (D18, D1, D2)
def test_permission_grants_and_api_surface(db: Session) -> None:
    def perms(role: str) -> set[str]:
        return {c for (c,) in db.execute(select(Permission.code).join(RolePermission, RolePermission.permission_id == Permission.id)
                                         .join(Role, Role.id == RolePermission.role_id).where(Role.code == role))
                if c.startswith(("registry.", "credits."))}
    assert perms("PROJECT_MANAGER") == perms("REGISTRY_MANAGER") == {"registry.read", "registry.manage", "credits.read"}
    assert perms("QA_OFFICER") == {"registry.read", "registry.confirm", "credits.read", "credits.confirm"}   # + Phase 9B ledger confirmer
    assert perms("MRV_MANAGER") == perms("CALCULATION_ANALYST") == {"registry.read"}
    assert perms("FINANCE_MANAGER") == {"credits.read"} and perms("CREDIT_MANAGER") == {"credits.read", "credits.manage"}   # 9B
    assert perms("BUYER") == {"credits.holder_read", "credits.holder_retire"}                       # Phase 9B holder view
    for role in ("VVB_REVIEWER", "FARMER", "LAB_MANAGER", "METHODOLOGY_SPECIALIST"):
        assert perms(role) == set(), role
    from app.main import app
    paths = [r.path for r in app.routes if hasattr(r, "path")]
    assert not any(p.startswith("/api/v1/registry-portal") for p in paths)
    segments = {seg for p in paths for seg in p.split("/")}
    # Phase 9B adds the credit ledger under /credits; Phase 10 adds the marketplace only under /marketplace, /orders and /payments
    # (+ /refunds); payouts and checkout stay absent, and the 9A registry API itself never transfers, reserves or retires credits
    for word in ("payouts", "checkout"):
        assert word not in segments, word
    for word, prefix in (("marketplace", "/api/v1/marketplace"), ("orders", "/api/v1/orders"), ("payments", "/api/v1/payments")):
        assert all(p.startswith(prefix) for p in paths if word in p.split("/")), word
    assert not any(w in p for p in paths if p.startswith("/api/v1/registry") for w in ("transfer", "retire", "reserv", "inventory"))
    assert [p for p in paths if p.startswith("/api/v1/credits/batches")]                                      # 9A read-only batch views remain
    # the TEST adapter is never part of the application runtime
    assert set(ADAPTERS) == {"MANUAL"}


# ---------------------------------------------------------------- eligibility (D3, D11)
def test_eligibility_blockers(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    k = calc_scenario(db, client, 80.10, 25.10, "9210 2000 3000")
    reg = Reg(client, db, k, quantity=None)
    # 1. no VVB decision (nothing faked, the calculated quantity is never used)
    assert codes(reg.create()) == "NO_VERIFIED_DECISION"
    view = reg.view()
    assert view["eligibility"][0]["blockers"][0]["code"] == "NO_VERIFIED_DECISION" and view["issued"][0]["value"] is None
    assert view["calculated"]["label"] == "Calculated tCO2e — not verified, not issued"
    # 2. NOT_VERIFIED
    _, s, _, v1, v2, run = _submitted(client, db, k)
    assert _decide(client, v1, s["id"], outcome="NOT_VERIFIED", rationale="TEST: not verified").status_code == 201
    assert codes(reg.create()) == "DECISION_NOT_VERIFIED"
    # 4. VERIFIED without a VVB-stated quantity (new assignment of the same READY package)
    org, w1, _ = _vvb(db, client)
    a2 = client.post(f"{V}/projects/{k.project_id}/assignments", headers=k.x.c.t.pm.headers,
                     json={"monitoring_period_id": k.period_id, "vvb_organization_id": str(org.id)}).json()
    client.post(f"{VVB}/assignments/{a2['id']}/accept", headers=w1.headers, json={"coi_declaration": COI})
    s2 = client.post(f"{V}/assignments/{a2['id']}/submit", headers=k.x.c.t.pm.headers).json()
    assert _decide(client, w1, s2["id"]).status_code == 201
    assert codes(reg.create()) == "VERIFIED_QUANTITY_REQUIRED"
    # VERIFIED with a stated quantity: the remaining prerequisites
    org3, x1, _ = _vvb(db, client)
    a3 = client.post(f"{V}/projects/{k.project_id}/assignments", headers=k.x.c.t.pm.headers,
                     json={"monitoring_period_id": k.period_id, "vvb_organization_id": str(org3.id)}).json()
    client.post(f"{VVB}/assignments/{a3['id']}/accept", headers=x1.headers, json={"coi_declaration": COI})
    s3 = client.post(f"{V}/assignments/{a3['id']}/submit", headers=k.x.c.t.pm.headers).json()
    assert _decide(client, x1, s3["id"], verified_quantity="1000", verified_quantity_unit="tCO2e").status_code == 201
    # 5. no registration at the second registry
    other = make_org(db, org_type="REGISTRY")
    acc2 = reg.post(f"{R}/accounts", {"organization_id": str(reg.org.id), "registry_organization_id": str(other.id),
                                      "external_account_id": "TEST-ACC-2", "label": "second"}).json()
    assert codes(reg.create(account_id=acc2["id"])) == "REGISTRATION_REQUIRED"
    # 43. environment isolation: a DEMO registry is never usable from a LIVE organization
    demo_reg = make_org(db, org_type="REGISTRY", environment="DEMO")
    assert codes(reg.post(f"{R}/accounts", {"organization_id": str(reg.org.id), "registry_organization_id": str(demo_reg.id),
                                            "external_account_id": "X", "label": "demo"})) == "NOT_A_REGISTRY"
    assert codes(reg.post(f"{R}/accounts", {"organization_id": str(reg.org.id), "registry_organization_id": str(reg.org.id),
                                            "external_account_id": "Y", "label": "not a registry"})) == "NOT_A_REGISTRY"
    assert codes(reg.post(f"{R}/accounts", {"organization_id": str(reg.org.id), "registry_organization_id": str(other.id),
                                            "external_account_id": "Z", "label": "test", "adapter_code": "TEST"})) == "UNKNOWN_ADAPTER"
    # 6. a closed account and a suspended registry
    reg.post(f"{R}/accounts/{acc2['id']}/close", {"reason": "TEST closed"})
    assert codes(reg.create(account_id=acc2["id"])) in ("REGISTRY_ACCOUNT_INACTIVE", "REGISTRATION_REQUIRED")
    other.status = "SUSPENDED"
    db.flush()
    blockers = {b["code"] for b in rs.eligibility(db, as_principal(db, reg.rm)[1], _project(db, k),
                                                  rs._period(db, _project(db, k), uuid.UUID(k.period_id)),
                                                  db.get(rs.RegistryAccount, uuid.UUID(acc2["id"])))[0]}
    assert {"REGISTRY_ACCOUNT_INACTIVE", "REGISTRY_INACTIVE", "REGISTRATION_REQUIRED"} <= blockers
    # 8. one open submission per period across registries
    first = reg.create()
    assert first.status_code == 201, first.text
    assert codes(reg.create()) == "OPEN_REGISTRY_SUBMISSION_EXISTS"
    # 9. checklist: not configured → warning outside production, blocker in production (existing NOT_PRODUCTION_READY policy)
    reg.post(f"{R}/accounts/{reg.account['id']}/configure", {"credit_unit": "TCU", "verified_unit_equivalent": "tCO2e", "reason": "TEST no checklist"})
    v = reg.view()
    assert any(w["code"] == "CHECKLIST_NOT_CONFIGURED" for e in v["eligibility"] for w in e["warnings"])
    monkeypatch.setattr(get_settings(), "APP_ENV", "production")
    v = reg.view()
    assert any(b["code"] == "CHECKLIST_NOT_CONFIGURED" for e in v["eligibility"] for b in e["blockers"])
    monkeypatch.setattr(get_settings(), "APP_ENV", "test")
    # RBAC on creation
    assert reg.post(f"{R}/projects/{k.project_id}/submissions", {"monitoring_period_id": k.period_id, "registry_account_id": reg.account["id"]},
                    who=k.analyst).status_code == 403


# ---------------------------------------------------------------- snapshot (10–12) and the manual lifecycle (13, 14, 16–19, 28)
def test_snapshot_manual_lifecycle_rejection_and_resubmission(client: TestClient, db: Session) -> None:
    k = calc_scenario(db, client, 80.20, 25.20, "9220 2000 3000")
    reg = Reg(client, db, k)
    sid = reg.create().json()["id"]
    assert codes(reg.post(f"{R}/submissions/{sid}/freeze")) == "CHECKLIST_INCOMPLETE"
    reg.doc(f"{R}/submissions/{sid}/documents", "REGISTRY_SUBMISSION", checklist_item="PDD")
    bad = client.post(f"{R}/submissions/{sid}/documents", headers=reg.rm.headers, files={"file": ("x.png", b"\x89PNG\r\n\x1a\n" + b"0" * 64, "image/png")},
                      data={"category": "REGISTRY_SUBMISSION"})
    assert bad.status_code == 422                                                       # PDF only (D14)
    f = reg.post(f"{R}/submissions/{sid}/freeze").json()
    assert f["status"] == "FROZEN" and f["snapshot_sha256"] and f["idempotency_key"]
    snap = client.get(f"{R}/submissions/{sid}/snapshot", headers=reg.qa.headers).json()
    assert snap["snapshot_sha256"] == fw.sha256(snap["snapshot"])                     # 11. hash of the canonical snapshot
    sn = snap["snapshot"]
    assert sn["schema"] == "registry-submission-v1" and sn["verification_decision"]["verified_quantity"] == "1000"
    assert sn["verification_decision"]["label"] == "VVB-stated verified quantity" and sn["registration"]["external_project_id"]
    assert {d["role"] for d in sn["documents"]} == {"VERIFICATION_REPORT", "CALCULATION_REPORT", "REGISTRY_SUBMISSION"}
    assert {"crediting_period", "standard", "methodology", "verification_submission", "readiness", "calculation_report", "calculation_run",
            "dataset", "checklist"} <= set(sn)
    s_obj = db.get(RegistrySubmission, uuid.UUID(sid))
    assert s_obj is not None
    p = _project(db, k)
    again = rs.build_snapshot(db, s_obj, p, rs._period(db, p, s_obj.monitoring_period_id), db.get(rs.RegistryAccount, s_obj.registry_account_id),
                              db.get(VerificationDecision, s_obj.verification_decision_id))  # type: ignore[arg-type]
    assert fw.sha256(again) == f["snapshot_sha256"]                                      # 10. deterministic
    assert codes(client.post(f"{R}/submissions/{sid}/documents", headers=reg.rm.headers, files={"file": ("d.pdf", PDF, "application/pdf")},
                             data={"category": "REGISTRY_SUBMISSION"})) == "SUBMISSION_FROZEN"
    # 14. manual: no submit through an adapter; reference + receipt required
    assert codes(reg.post(f"{R}/submissions/{sid}/submit")) == "MANUAL_ACTION_REQUIRED"
    assert reg.post(f"{R}/submissions/{sid}/record-submitted", {"external_submission_id": "TEST-SUB-A"}).status_code == 422
    assert codes(reg.post(f"{R}/submissions/{sid}/record-submitted", {"external_submission_id": "TEST-SUB-A",
                                                                       "document_id": str(uuid.uuid4())})) == "DOCUMENT_NOT_ATTACHED"
    assert reg.submitted(sid, "TEST-SUB-A").json()["status"] == "SUBMITTED"
    # 19. issuance only after acceptance
    assert codes(reg.issue(sid, 100, "TEST-ISS-0")) == "SUBMISSION_NOT_ACCEPTED"
    q = reg.post(f"{R}/submissions/{sid}/record-query", {"note": "TEST: registry asks for the PDD annex"})
    assert q.json()["event_type"] == "QUERY_RECEIVED"
    # 16. rejection (reason + evidence); the VVB decision is untouched
    ev = reg.doc(f"{R}/submissions/{sid}/documents", "REGISTRY_RESPONSE")
    assert reg.post(f"{R}/submissions/{sid}/record-response", {"outcome": "REJECTED", "document_id": ev}).status_code == 422
    rej = reg.post(f"{R}/submissions/{sid}/record-response", {"outcome": "REJECTED", "document_id": ev, "reason": "TEST: annex missing"}).json()
    assert rej["status"] == "REJECTED"
    d = db.get(VerificationDecision, uuid.UUID(reg.decision["id"]))
    assert d is not None and d.status == "CURRENT" and d.outcome == "VERIFIED"
    assert codes(reg.post(f"{R}/submissions/{sid}/record-response", {"outcome": "ACCEPTED", "document_id": ev})) == "SUBMISSION_NOT_SUBMITTED"
    # 17. a new submission links the rejected one; 28. duplicate external submission reference
    s2 = reg.create(previous_submission_id=sid).json()
    assert s2["previous_submission_id"] == sid
    reg.doc(f"{R}/submissions/{s2['id']}/documents", "REGISTRY_SUBMISSION", checklist_item="PDD")
    reg.post(f"{R}/submissions/{s2['id']}/freeze")
    assert codes(reg.submitted(s2["id"], "TEST-SUB-A")) == "DUPLICATE_EXTERNAL_SUBMISSION"
    assert reg.submitted(s2["id"], "TEST-SUB-B").json()["status"] == "SUBMITTED"
    ev2 = reg.doc(f"{R}/submissions/{s2['id']}/documents", "REGISTRY_RESPONSE")
    acc = reg.post(f"{R}/submissions/{s2['id']}/record-response", {"outcome": "ACCEPTED", "document_id": ev2}).json()
    assert acc["status"] == "ACCEPTED"                                                  # 18
    detail = client.get(f"{R}/submissions/{s2['id']}", headers=reg.qa.headers).json()
    types = [e["event_type"] for e in detail["events"]]
    assert types[-1] == "RESPONSE_RECORDED" and types.count("EXTERNAL_REFERENCE_RECORDED") == 1 and types.count("DOCUMENT_ATTACHED") == 4
    assert detail["checklist"][0]["satisfied"] and _project(db, k).status == "VERIFIED"
    assert codes(reg.create()) == "OPEN_REGISTRY_SUBMISSION_EXISTS"                        # ACCEPTED blocks any other submission of the period
    actions = _actions(db, "registry_submission")
    for a in ("REGISTRY_SUBMISSION_CREATED", "REGISTRY_SUBMISSION_FROZEN", "REGISTRY_SUBMISSION_SUBMITTED", "REGISTRY_QUERY_RECORDED",
              "REGISTRY_RESPONSE_RECORDED", "REGISTRY_SUBMISSION_REJECTED", "REGISTRY_SUBMISSION_ACCEPTED", "REGISTRY_DOCUMENT_UPLOADED",
              "REGISTRY_EXTERNAL_REFERENCE_ADDED"):
        assert a in actions, a


# ---------------------------------------------------------------- issuance (19–30, 47, 48)
def test_issuance_dual_confirmation_tranches_invariants_correction_and_cancellation(client: TestClient, db: Session) -> None:
    k = calc_scenario(db, client, 80.30, 25.30, "9230 2000 3000")
    reg = Reg(client, db, k)
    sid = reg.accepted()["id"]
    # 25. unit equivalence must be explicit
    assert codes(reg.issue(sid, 600, "TEST-ISS-1", unit="OTHER")) == "UNIT_EQUIVALENCE_NOT_CONFIGURED"
    # D7 whole units; totals must add up
    two = [{"vintage": "2026", "quantity": 400, "serial_ranges": [{"serial_start": "R-2026-0001", "serial_end": "R-2026-0400", "quantity": 400}]},
           {"vintage": "2027", "quantity": 200, "serial_ranges": [{"serial_start": "R-2027-0001", "serial_end": "R-2027-0200", "quantity": 200}]}]
    assert reg.issue(sid, 600.5, "TEST-ISS-1", batches=two).status_code == 422          # type: ignore[arg-type]
    assert codes(reg.issue(sid, 700, "TEST-ISS-1", batches=two)) == "BATCH_TOTAL_MISMATCH"
    assert reg.post(f"{R}/submissions/{sid}/issuances", {"external_issuance_id": "X", "issuance_date": "2026-10-01", "quantity": 1, "unit": "TCU",
                                                         "batches": [{"vintage": "2026", "quantity": 1, "serial_ranges": [{"quantity": 1}]}]}
                    ).json()["error_code"] == "EVIDENCE_REQUIRED"
    assert reg.post(f"{R}/submissions/{sid}/issuances", {"calculated_quantity": 1}).status_code == 422   # no other quantity is ever accepted
    i1 = reg.issue(sid, 600, "TEST-ISS-1", batches=two, key="TEST-KEY-1").json()
    assert i1["status"] == "RECORDED" and [b["status"] for b in i1["batches"]] == ["RECORDED", "RECORDED"]
    assert reg.issue(sid, 600, "TEST-ISS-1", batches=two, key="TEST-KEY-1").json()["id"] == i1["id"]   # Idempotency-Key replay
    assert [r["serial_start"] for b in i1["batches"] for r in b["serial_ranges"]] == ["R-2026-0001", "R-2027-0001"]   # verbatim
    assert _project(db, k).status == "VERIFIED"
    # 20 / 21. dual confirmation: never the recorder; registry.confirm only
    r = reg.confirm(i1["id"], who=reg.rm)
    assert r.status_code == 403
    pm_can_confirm = reg.confirm(i1["id"], who=k.x.c.t.pm)
    assert pm_can_confirm.status_code == 403
    c1 = reg.confirm(i1["id"])
    assert c1.status_code == 200, c1.text
    c1j = c1.json()
    assert c1j["status"] == "CONFIRMED" and c1j["confirmed_by_name"] and {b["status"] for b in c1j["batches"]} == {"ISSUED"}
    assert _project(db, k).status == "ISSUED"                                            # 48 / D13
    # 29. duplicate external issuance; 30. duplicate serials
    assert codes(reg.issue(sid, 100, "TEST-ISS-1")) == "DUPLICATE_EXTERNAL_ISSUANCE"
    dup = [{"vintage": "2026", "quantity": 100, "serial_ranges": [{"serial_start": "R-2026-0001", "serial_end": "R-2026-0100", "quantity": 100}]}]
    assert codes(reg.issue(sid, 100, "TEST-ISS-X", batches=dup)) == "DUPLICATE_SERIAL"
    # 26 / 27. tranches
    i2 = reg.issue(sid, 300, "TEST-ISS-2").json()
    assert reg.confirm(i2["id"]).json()["status"] == "CONFIRMED"
    v = reg.view()
    assert v["issued"][0]["value"] == "900" and v["issued"][0]["unit"] == "TCU" and v["remaining"]["value"] == "100"
    assert v["verified"]["value"] == "1000" and v["registry_status"] == "ISSUED"
    # 24. cumulative issued ≤ verified (record and confirm)
    assert codes(reg.issue(sid, 200, "TEST-ISS-3")) == "QUANTITY_EXCEEDS_VERIFIED"
    i4 = reg.issue(sid, 100, "TEST-ISS-4").json()
    i5 = reg.issue(sid, 100, "TEST-ISS-5").json()
    assert reg.confirm(i4["id"]).status_code == 200
    assert codes(reg.confirm(i5["id"])) == "QUANTITY_EXCEEDS_VERIFIED"
    v5 = reg.post(f"{R}/issuances/{i5['id']}/void", {"reason": "TEST: entered twice"}).json()
    assert v5["status"] == "VOIDED" and {b["status"] for b in v5["batches"]} == {"VOIDED"}
    # 22. correction: a new issuance references the original; the original stays as history
    corr = reg.post(f"{R}/issuances/{i2['id']}/correct", {
        "external_issuance_id": "TEST-ISS-2", "issuance_date": "2026-10-02", "quantity": 250, "unit": "TCU", "reason": "TEST: registry corrected",
        "document_id": reg.doc(f"{R}/submissions/{sid}/documents", "ISSUANCE_STATEMENT"),
        "batches": [{"vintage": "2026", "quantity": 250, "serial_ranges": [{"quantity": 250}]}]}).json()
    assert corr["corrects_issuance_id"] == i2["id"] and corr["status"] == "RECORDED"
    assert reg.confirm(corr["id"]).json()["status"] == "CONFIRMED"
    orig = client.get(f"{R}/submissions/{sid}", headers=reg.qa.headers).json()["issuances"]
    o2 = next(x for x in orig if x["id"] == i2["id"])
    assert o2["status"] == "CORRECTED" and o2["quantity"] == 300 and o2["corrected_by_issuance_id"] == corr["id"]
    assert {b["status"] for b in o2["batches"]} == {"SUPERSEDED"}
    # 23. cancellation (registry evidence); serials stay allocated
    assert reg.post(f"{R}/issuances/{i1['id']}/cancel", {"reason": "TEST"}).status_code == 422
    cx = reg.post(f"{R}/issuances/{i1['id']}/cancel", {"reason": "TEST: registry cancelled",
                                                       "document_id": reg.doc(f"{R}/submissions/{sid}/documents", "REGISTRY_RESPONSE")}).json()
    assert cx["status"] == "CANCELLED" and {b["status"] for b in cx["batches"]} == {"CANCELLED"}
    assert codes(reg.issue(sid, 100, "TEST-ISS-6", batches=dup)) == "DUPLICATE_SERIAL"
    assert ci.confirmed_total(db, uuid.UUID(reg.decision["id"])) == 350
    assert _project(db, k).status == "ISSUED"                                            # aggregate: first issuance stays the fact
    # credits API: read-only, batches with history, never "available"
    batches = client.get(f"{C}/batches", headers=reg.rm.headers, params={"project_id": k.project_id}).json()
    assert {b["status"] for b in batches} == {"ISSUED", "SUPERSEDED", "CANCELLED"}
    assert all(b["label"] == "Registry-issued credits" for b in batches)
    assert client.get(f"{C}/batches", headers=k.analyst.headers).status_code == 403
    for action in ("CREDIT_ISSUANCE_RECORDED", "CREDIT_ISSUANCE_CONFIRMED", "CREDIT_ISSUANCE_VOIDED", "CREDIT_ISSUANCE_CORRECTION_RECORDED",
                   "CREDIT_ISSUANCE_CORRECTED", "CREDIT_ISSUANCE_CANCELLED"):
        assert action in _actions(db, "credit_issuance"), action
    assert {"CREDIT_BATCH_ISSUED", "CREDIT_BATCH_SUPERSEDED", "CREDIT_BATCH_CANCELLED", "CREDIT_BATCH_VOIDED"} <= _actions(db, "credit_batch")


def test_unit_equivalence_missing_blocks_issuance(client: TestClient, db: Session) -> None:
    k = calc_scenario(db, client, 80.35, 25.35, "9235 2000 3000")
    reg = Reg(client, db, k, equivalence=False)
    sid = reg.accepted()["id"]
    r = reg.issue(sid, 10, "TEST-ISS-1")
    assert codes(r) == "UNIT_EQUIVALENCE_NOT_CONFIGURED" and r.json()["details"]["account_credit_unit"] is None
    assert reg.view()["remaining"] is None


# ---------------------------------------------------------------- API adapter: idempotency, timeout, reconciliation, parser (15, 31–34)
def test_api_adapter_timeout_after_success_reconciliation_and_serial_parser(client: TestClient, db: Session) -> None:
    k = calc_scenario(db, client, 80.40, 25.40, "9240 2000 3000")
    reg = Reg(client, db, k)
    sid = uuid.UUID(reg.frozen()["id"])
    principal, ctx = as_principal(db, reg.rm)
    # unavailable: certainly not sent → back to FROZEN
    adapter = TestRegistryAdapter(behaviour="unavailable")
    with pytest.raises(AppError) as e:
        rs.submit(db, ctx, principal, sid, adapter=adapter)
    assert e.value.error_code == "REGISTRY_UNAVAILABLE" and db.get(RegistrySubmission, sid).status == "FROZEN"   # type: ignore[union-attr]
    # timeout before receipt → UNCONFIRMED → reconcile NOT_FOUND → FROZEN (only after the registry confirms it has nothing)
    adapter.behaviour = "timeout_before"
    assert rs.submit(db, ctx, principal, sid, adapter=adapter).status == "SUBMISSION_UNCONFIRMED"
    assert rs.reconcile(db, ctx, principal, sid, None, adapter=adapter).status == "FROZEN"
    # timeout AFTER the registry received it → UNCONFIRMED; no automatic retry; reconcile finds it → SUBMITTED, no duplicate
    adapter.behaviour = "timeout_after"
    s = rs.submit(db, ctx, principal, sid, adapter=adapter)
    assert s.status == "SUBMISSION_UNCONFIRMED" and len(adapter.received) == 1
    with pytest.raises(AppError) as e:
        rs.submit(db, ctx, principal, sid, adapter=adapter)
    assert e.value.error_code == "SUBMISSION_NOT_FROZEN"
    calls = len(adapter.calls)
    s = rs.reconcile(db, ctx, principal, sid, None, adapter=adapter)
    assert s.status == "SUBMITTED" and s.external_submission_id == "TEST-SUB-0001" and len(adapter.calls) == calls
    assert len(set(adapter.calls)) == 1 and len(adapter.received) == 1                  # every attempt carried the same idempotency key
    types = [e.event_type for e in db.scalars(select(RegistryEvent).where(RegistryEvent.submission_id == sid)
                                               .order_by(RegistryEvent.occurred_at)).all()]
    assert {"SUBMIT_ATTEMPT", "ERROR", "TIMEOUT", "RECONCILED"} <= set(types)
    # status query → ACCEPTED (registry payload hash is the evidence)
    rs.reconcile(db, ctx, principal, sid, None, adapter=adapter)
    adapter.decide("TEST-SUB-0001", "ACCEPTED")
    s = rs.reconcile(db, ctx, principal, sid, None, adapter=adapter)
    assert s.status == "ACCEPTED" and s.response_payload_sha256
    # API-sourced issuance must match the registry exactly; registry-specific serial parser checks length and overlaps
    ext_project = reg.registration["external_project_id"]
    batch = ExternalBatch(vintage="2026", quantity=600, serial_ranges=(ExternalSerialRange("TSER-A-000001", "TSER-A-000600", 600),))
    adapter.issue(ext_project, ExternalIssuance("TEST-ISS-API-1", date(2026, 10, 1), 600, "TCU", (batch,), payload_sha256="f" * 64))

    def body(q: int, start: str, end: str, ext: str = "TEST-ISS-API-1") -> IssuanceIn:
        return IssuanceIn(external_issuance_id=ext, issuance_date=date(2026, 10, 1), quantity=q, unit="TCU", source="API",
                          batches=[{"vintage": "2026", "quantity": q, "serial_ranges": [{"serial_start": start, "serial_end": end, "quantity": q}]}])
    with pytest.raises(AppError) as e:
        ci.record(db, ctx, principal, sid, body(600, "TSER-A-000001", "TSER-A-000601"), adapter=adapter)
    assert e.value.error_code == "SERIAL_RANGE_LENGTH_MISMATCH"
    with pytest.raises(AppError) as e:
        ci.record(db, ctx, principal, sid, body(500, "TSER-A-000001", "TSER-A-000500"), adapter=adapter)
    assert e.value.error_code == "ISSUANCE_MISMATCH"
    i = ci.record(db, ctx, principal, sid, body(600, "TSER-A-000001", "TSER-A-000600"), adapter=adapter)
    assert i.source == "API" and i.api_response_sha256 == "f" * 64 and i.evidence_document_id is None
    qa, qctx = as_principal(db, reg.qa)
    ci.confirm(db, qctx, qa, i.id, None)
    # 31. overlap detected through the parser (different text, overlapping numbers)
    adapter.issue(ext_project, ExternalIssuance("TEST-ISS-API-2", date(2026, 10, 1), 100, "TCU",
                                                (ExternalBatch("2026", 100, (ExternalSerialRange("TSER-A-000550", "TSER-A-000649", 100),)),)))
    with pytest.raises(AppError) as e:
        ci.record(db, ctx, principal, sid, body(100, "TSER-A-000550", "TSER-A-000649", "TEST-ISS-API-2"), adapter=adapter)
    assert e.value.error_code == "SERIAL_OVERLAP"
    # reconciliation of issuances against the registry
    rs.reconcile(db, ctx, principal, sid, None, adapter=adapter)
    mism = db.scalars(select(RegistryEvent).where(RegistryEvent.submission_id == sid, RegistryEvent.event_type == "MISMATCH")).all()
    assert any("TEST-ISS-API-2" in (m.note or "") for m in mism)                         # issued at the registry, not recorded


# ---------------------------------------------------------------- recalculation (36–38), multi-period (35, 49), lineage (39), RBAC (41–43)
def test_recalculation_multi_period_lineage_and_isolation(client: TestClient, db: Session) -> None:
    k = calc_scenario(db, client, 80.50, 25.50, "9250 2000 3000")
    reg = Reg(client, db, k)
    # 36. recalculation before freeze → the DRAFT is invalidated (never mutated)
    draft = reg.create().json()
    run2 = _recalc(db, k, reg.run)
    got = client.get(f"{R}/submissions/{draft['id']}", headers=reg.rm.headers).json()
    assert got["status"] == "INVALIDATED" and got["source_superseded"] and "superseded" in got["closed_reason"]
    assert codes(reg.create()) == "NO_VERIFIED_DECISION"
    # re-verify the recalculated package → registry → issuance
    _ready(client, db, k, run2)
    org, w1, _ = _vvb(db, client)
    a = client.post(f"{V}/projects/{k.project_id}/assignments", headers=k.x.c.t.pm.headers,
                    json={"monitoring_period_id": k.period_id, "vvb_organization_id": str(org.id)}).json()
    client.post(f"{VVB}/assignments/{a['id']}/accept", headers=w1.headers, json={"coi_declaration": COI})
    vsub = client.post(f"{V}/assignments/{a['id']}/submit", headers=k.x.c.t.pm.headers).json()
    reg.decision = _decide(client, w1, vsub["id"], verified_quantity="500", verified_quantity_unit="tCO2e").json()
    sid = reg.accepted("TEST-SUB-R")["id"]
    iss = reg.issue(sid, 400, "TEST-ISS-R", batches=[{"vintage": "2026", "quantity": 400,
                                                       "serial_ranges": [{"serial_start": "Q-1", "serial_end": "Q-400", "quantity": 400}]}]).json()
    reg.confirm(iss["id"])
    # 37 / 38. recalculation after submission and issuance: flagged, nothing rewritten
    _recalc(db, k, run2)
    v = reg.view()
    s = next(x for x in v["submissions"] if x["id"] == sid)
    assert s["status"] == "ACCEPTED" and s["source_superseded"] is True
    assert v["issuances"][0]["status"] == "CONFIRMED" and v["issuances"][0]["quantity"] == 400
    assert v["issuances"][0]["batches"][0]["source_superseded"] is True and v["verified"]["value"] is None
    ev = db.scalars(select(RegistryEvent).where(RegistryEvent.submission_id == uuid.UUID(sid), RegistryEvent.event_type == "SOURCE_SUPERSEDED")).all()
    assert len(ev) == 1
    reg.view()
    assert len(db.scalars(select(RegistryEvent).where(RegistryEvent.submission_id == uuid.UUID(sid),
                                                      RegistryEvent.event_type == "SOURCE_SUPERSEDED")).all()) == 1   # flagged once
    # a correction is still possible (controlled registry action, new issuance referencing the original)
    corr = reg.post(f"{R}/issuances/{iss['id']}/correct", {
        "external_issuance_id": "TEST-ISS-R", "issuance_date": "2026-10-05", "quantity": 380, "unit": "TCU", "reason": "TEST: registry corrected",
        "document_id": reg.doc(f"{R}/submissions/{sid}/documents", "ISSUANCE_STATEMENT"),
        "batches": [{"vintage": "2026", "quantity": 380, "serial_ranges": [{"serial_start": "Q-1", "serial_end": "Q-380", "quantity": 380}]}]})
    assert corr.status_code == 201, corr.text
    # 35 / 49. a later period stays independent
    op = client.post("/api/v1/mrv/monitoring-periods", headers=k.x.c.mrv.headers, json={
        "project_id": k.project_id, "name": "Monitoring 2", "start_date": "2030-06-01", "end_date": "2031-05-31"}).json()
    v2 = reg.view(op["id"])
    assert v2["registry_status"] == "NONE" and v2["issuances"] == [] and v2["eligibility"][0]["blockers"][0]["code"] == "NO_VERIFIED_DECISION"
    assert codes(reg.create(period_id=op["id"])) == "NO_VERIFIED_DECISION"
    assert reg.view()["registry_status"] == "ISSUED" and _project(db, k).status == "ISSUED"
    # 39. lineage: batch → issuance → submission → registration → registry → decision → … → project → farms / farmer codes
    batch_id = iss["batches"][0]["id"]
    lin = client.get(f"{C}/batches/{batch_id}/lineage", headers=k.x.c.t.pm.headers).json()
    assert [c["kind"] for c in lin["chain"]] == ["CREDIT_BATCH", "CREDIT_ISSUANCE", "REGISTRY_SUBMISSION", "REGISTRY_REGISTRATION", "REGISTRY",
                                                 "VERIFICATION_DECISION", "VERIFICATION_SUBMISSION", "READINESS_REVIEW", "CALCULATION_REPORT",
                                                 "CALCULATION_RUN", "METHODOLOGY_VERSION", "MRV_DATASET", "MONITORING_PERIOD", "PROJECT"]
    assert lin["sources"]["farms"] and lin["sources"]["farms"][0]["farmer_code"].startswith("FRM-")
    assert lin["calculation_lineage"]["run"]["id"] and lin["verification_lineage"]["chain"]
    cm = staff(db, client, reg.org, "CREDIT_MANAGER")
    lin_cm = client.get(f"{C}/batches/{batch_id}/lineage", headers=cm.headers).json()
    assert lin_cm["calculation_lineage"] is None and lin_cm["verification_lineage"] is None and lin_cm["sources"]["farms"]
    # 41 / 42 / 43. RBAC and isolation
    org_v, vvb_user, _ = _vvb(db, client)
    for url in (f"{R}/projects/{k.project_id}/periods/{k.period_id}", f"{R}/accounts", f"{C}/batches"):
        assert client.get(url, headers=vvb_user.headers).status_code == 403, url
    other_pm = staff(db, client, make_org(db), "PROJECT_MANAGER")
    assert client.get(f"{R}/submissions/{sid}", headers=other_pm.headers).status_code == 404
    assert client.get(f"{C}/batches/{batch_id}", headers=other_pm.headers).status_code == 404
    assert client.get(f"{C}/batches", headers=other_pm.headers).json() == []
    assert client.get(f"{R}/accounts", headers=other_pm.headers).json() == []
    assert client.get(f"{R}/submissions/{sid}", headers=k.analyst.headers).status_code == 200
    assert reg.post(f"{R}/submissions/{sid}/record-query", {"note": "analyst cannot"}, who=k.analyst).status_code == 403
    assert client.get(f"{R}/projects/{k.project_id}/periods/{k.period_id}", headers=cm.headers).status_code == 403
    # registry documents are immutable (no new versions through the generic documents API)
    doc_id = iss["evidence_document_id"]
    nv = client.post(f"/api/v1/evidence/documents/{doc_id}/versions", headers=reg.rm.headers, files={"file": ("x.pdf", PDF + b"%x", "application/pdf")})
    assert nv.status_code == 403 and nv.json()["error_code"] == "DOCUMENT_IMMUTABLE"
    assert client.get(f"/api/v1/evidence/documents/{doc_id}/download", headers=vvb_user.headers).status_code == 404
    # 40. audit
    assert "REGISTRY_ACCOUNT_CREATED" in _actions(db, "registry_account")
    assert {"REGISTRY_REGISTRATION_CREATED", "REGISTRY_REGISTRATION_REGISTERED"} <= _actions(db, "registry_registration")
    assert {"REGISTRY_SUBMISSION_INVALIDATED", "REGISTRY_SOURCE_SUPERSEDED"} <= _actions(db, "registry_submission")


# ---------------------------------------------------------------- DEMO (44, D15)
def test_demo_has_no_registry_issuance_and_stays_blocked(client: TestClient, db: Session) -> None:
    from app.models import MonitoringPeriod
    from app.seed.accounts import seed_demo
    from app.seed.demo_farms import seed_demo_farms
    from app.seed.demo_lab import seed_demo_lab
    from app.seed.demo_methodologies import seed_demo_methodologies
    from app.seed.demo_mrv import seed_demo_mrv
    from app.seed.demo_projects import seed_demo_projects
    seed_demo(db, "Demo-Password-123")
    seed_demo_farms(db)
    seed_demo_projects(db)
    seed_demo_methodologies(db)
    seed_demo_mrv(db)
    seed_demo_lab(db)
    reg_org = db.scalars(select(Organization).where(Organization.code == "DEMO-REG-R")).one()
    assert reg_org.org_type == "REGISTRY" and reg_org.environment == "DEMO" and "(DEMO)" in reg_org.name
    for real in ("verra", "gold standard", "ccts", "vcs"):
        assert real not in reg_org.name.lower()
    assert db.scalars(select(CreditIssuance).where(CreditIssuance.environment == "DEMO")).first() is None
    assert db.scalars(select(CreditBatch).where(CreditBatch.environment == "DEMO")).first() is None
    assert db.scalars(select(RegistrySubmission).where(RegistrySubmission.environment == "DEMO")).first() is None
    p = db.scalars(select(Project).where(Project.environment == "DEMO", Project.name.like("Niphad%"))).one()
    mp = db.scalars(select(MonitoringPeriod).where(MonitoringPeriod.project_id == p.id)).first()
    assert mp is not None
    dev = db.scalars(select(Organization).where(Organization.code == "DEMO-DEV-A")).one()
    pm = login(client, make_user(db, roles=[("PROJECT_MANAGER", dev)], environment="DEMO"))
    r = client.post(f"{R}/projects/{p.id}/submissions", headers=pm, json={"monitoring_period_id": str(mp.id), "registry_account_id": str(uuid.uuid4())})
    assert r.status_code == 409 and r.json()["error_code"] == "NO_VERIFIED_DECISION"
    v = client.get(f"{R}/projects/{p.id}/periods/{mp.id}", headers=pm).json()
    assert v["demo_note"] == "DEMO — no registry issuance" and v["issued"][0]["value"] is None
    assert v["eligibility"][0]["blockers"][0]["code"] == "NO_VERIFIED_DECISION"
    assert [o["code"] for o in client.get(f"{R}/organizations", headers=pm, params={"environment": "DEMO"}).json()] == ["DEMO-REG-R"]


# ---------------------------------------------------------------- database triggers (12) and the downgrade guard
def test_triggers_protect_snapshot_issuances_serials_and_events() -> None:
    def build(session: Session, client: TestClient) -> tuple[str, dict, str]:
        k = calc_scenario(session, client, 80.60, 25.60, "9260 2000 3000")
        reg = Reg(client, session, k)
        f = reg.frozen()
        return "UPDATE registry_submissions SET snapshot_sha256 = N'0' WHERE id = :i", {"i": f["id"]}, "fixed"
    _dedicated(build)

    def build2(session: Session, client: TestClient) -> tuple[str, dict, str]:
        k = calc_scenario(session, client, 80.65, 25.65, "9265 2000 3000")
        reg = Reg(client, session, k)
        sid = reg.accepted()["id"]
        i = reg.issue(sid, 10, "TEST-ISS-T").json()
        reg.confirm(i["id"])
        return "UPDATE credit_issuances SET quantity = 11 WHERE id = :i", {"i": i["id"]}, "immutable"
    _dedicated(build2)

    def build3(session: Session, client: TestClient) -> tuple[str, dict, str]:
        k = calc_scenario(session, client, 80.70, 25.70, "9270 2000 3000")
        reg = Reg(client, session, k)
        sid = reg.accepted()["id"]
        i = reg.issue(sid, 10, "TEST-ISS-S", batches=[{"vintage": "2026", "quantity": 10,
                                                       "serial_ranges": [{"serial_start": "S-1", "serial_end": "S-10", "quantity": 10}]}]).json()
        return ("UPDATE credit_serial_ranges SET serial_end = N'S-11' WHERE batch_id = :b", {"b": i["batches"][0]["id"]},
                "never change")
    _dedicated(build3)

    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from app.core.database import get_engine
    with get_engine().connect() as c:
        t = c.begin()
        try:
            c.execute(text("DELETE FROM registry_events WHERE 1 = 0"))
            raise AssertionError("registry_events accepted a delete")
        except DBAPIError as e:
            assert "append-only" in str(e)
        finally:
            if t.is_active:
                t.rollback()


def test_downgrade_guard_refuses_while_phase_9a_rows_exist() -> None:
    import pathlib

    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from app.core.database import get_engine
    src = (pathlib.Path(__file__).parents[1] / "alembic" / "versions" / "20261003_0013_phase9a_registry_credit_issuance.py").read_text(encoding="utf-8")
    guard = src.split("def downgrade() -> None:")[1].split('op.execute("""')[1].split('""")')[0]
    with get_engine().connect() as c:
        t = c.begin()
        session = Session(bind=c, join_transaction_mode="create_savepoint")
        try:
            org, registry = make_org(session), make_org(session, org_type="REGISTRY")
            user = make_user(session)
            session.add(RegistryAccount(organization_id=org.id, registry_organization_id=registry.id, external_account_id="GUARD", label="guard",
                                        adapter_code="MANUAL", status="ACTIVE", created_by=user.id, environment="LIVE"))
            session.flush()
            with pytest.raises(DBAPIError) as e:
                c.execute(text(guard))
            assert "Downgrade refused" in str(e.value)
        finally:
            session.close()
            if t.is_active:
                t.rollback()
