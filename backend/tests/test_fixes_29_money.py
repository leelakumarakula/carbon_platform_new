"""Fixes of 29/10 in the money / credit flow: superseded VVB decisions block issuance, concurrency-safe lazy re-checks (no double
transition), the verified-vs-calculated quantity check, 0-credit / reversal flags in the readiness package, issuance cancellation SoD,
provider refund outbox, payout exception resolution SoD (test_finance), stuck orders, explicit project-level costs in settlement, and
in-app notifications of the money flow. Everything runs inside the rolled-back test database with the TEST-only fixtures."""
import json
import uuid
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.context import RequestContext
from app.core.errors import Conflict, ValidationFailed
from app.integrations.payment import PaymentTimeout
from app.models import (
    AuditLog,
    CalculationReadinessReview,
    Notification,
    Order,
    PaymentEvent,
    SettlementRun,
    VerificationAssignment,
    VerificationDecision,
    VerificationSubmission,
    WorkflowEvent,
)
from app.security.principal import load_principal
from app.services import calculation_readiness as cr
from app.services import order_service as os_
from app.services import payment_service as ps
from app.services import verification_service as vs
from tests.calc_fixture import as_principal, calc_scenario
from tests.payment_fixture import TestPaymentAdapter
from tests.phase2 import staff
from tests.test_finance import F
from tests.test_marketplace import ORD, PAY, M
from tests.test_preverification import _recalc, _view
from tests.test_registry import R, Reg, codes
from tests.test_verification import VVB, _decide, _submitted


def _events(db: Session, entity_type: str, entity_id: Any, to: str) -> int:
    return int(db.scalar(select(func.count()).select_from(WorkflowEvent).where(WorkflowEvent.entity_type == entity_type,
                                                                              WorkflowEvent.entity_id == str(entity_id),
                                                                              WorkflowEvent.to_status == to)) or 0)


def _notified(db: Session, user_id: uuid.UUID, event_type: str) -> int:
    return int(db.scalar(select(func.count()).select_from(Notification).where(Notification.recipient_user_id == user_id,
                                                                              Notification.event_type == event_type)) or 0)


# ---------------------------------------------------------------- 1. issuance never proceeds on a superseded VVB decision
def test_superseded_decision_refuses_issuance_record_and_confirm(client: TestClient, db: Session) -> None:
    k = calc_scenario(db, client, 86.11, 30.11, "9761 2000 3000")
    reg = Reg(client, db, k)
    sid = reg.accepted()["id"]
    i1 = reg.issue(sid, 100, "TEST-ISS-SUP-1").json()
    assert i1["status"] == "RECORDED"
    _recalc(db, k, reg.run)                                         # a recalculation supersedes the run → package → VVB decision
    refused = reg.issue(sid, 100, "TEST-ISS-SUP-2")
    assert codes(refused) == "SOURCE_SUPERSEDED", refused.text
    assert codes(reg.confirm(i1["id"])) == "SOURCE_SUPERSEDED"
    d = db.get(VerificationDecision, uuid.UUID(reg.decision["id"]))
    db.refresh(d)
    assert d.status == "SUPERSEDED"
    detail = client.get(f"{R}/submissions/{sid}", headers=reg.qa.headers).json()
    assert [e["event_type"] for e in detail["events"]].count("SOURCE_SUPERSEDED") == 1          # flagged once, nothing rewritten
    assert next(x for x in detail["issuances"] if x["id"] == i1["id"])["status"] == "RECORDED"


# ---------------------------------------------------------------- 3. lazy re-checks transition at most once (re-entrant reader)
def test_readiness_and_submission_refresh_transition_once_under_reentry(client: TestClient, db: Session,
                                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    k = calc_scenario(db, client, 86.12, 30.12, "9762 2000 3000")
    a, s, _, _, _, run = _submitted(client, db, k)
    _, ctx = as_principal(db, k.qa)
    review_id = uuid.UUID(s["readiness_review_id"])
    _recalc(db, k, run)                                             # the READY package and the submission are now stale
    # a second reader re-enters between the outer reader's stale read and its lock: the outer one must find it done and do nothing
    orig_stale = cr._stale
    inner_result: dict[str, Any] = {}

    def racing_stale(db_: Session, period_id: uuid.UUID, ready: CalculationReadinessReview) -> list:
        if not inner_result:
            inner_result["readiness"] = None
            inner_result["readiness"] = cr.refresh(db_, ctx, period_id)
        return orig_stale(db_, period_id, ready)
    monkeypatch.setattr(cr, "_stale", racing_stale)
    outer = cr.refresh(db, ctx, uuid.UUID(k.period_id))
    assert inner_result["readiness"] is True and outer is False
    assert _events(db, "calculation_readiness", review_id, "INVALIDATED") == 1
    monkeypatch.setattr(cr, "_stale", orig_stale)
    assert cr.refresh(db, ctx, uuid.UUID(k.period_id)) is False                    # sequential re-entry: nothing left to do

    orig_problems = vs.package_problems
    inner: dict[str, Any] = {}

    def racing_problems(db_: Session, sub: VerificationSubmission) -> list[str]:
        if not inner:
            inner["submission"] = None
            inner["submission"] = vs.refresh(db_, ctx, assignment)
        return orig_problems(db_, sub)
    assignment = db.get(VerificationAssignment, uuid.UUID(a["id"]))
    monkeypatch.setattr(vs, "package_problems", racing_problems)
    outer_s = vs.refresh(db, ctx, assignment)
    monkeypatch.setattr(vs, "package_problems", orig_problems)
    assert inner["submission"] is True and outer_s is False
    assert _events(db, "verification_submission", s["id"], "INVALIDATED") == 1
    assert vs.refresh(db, ctx, assignment) is False
    db.commit()
    audits = db.scalars(select(AuditLog).where(AuditLog.action == "VERIFICATION_SUBMISSION_INVALIDATED",
                                               AuditLog.entity_id == s["id"])).all()
    assert len(audits) == 2                                         # one row per organization (project + VVB), written once
    # a GET view only persists the lazy invalidation; reading again changes nothing
    v1 = client.get(f"/api/v1/verification/submissions/{s['id']}", headers=k.x.c.t.pm.headers).json()
    assert v1["status"] == "INVALIDATED" and _events(db, "verification_submission", s["id"], "INVALIDATED") == 1


# ---------------------------------------------------------------- 10. VVB-stated quantity vs the calculated result
def test_verified_quantity_never_exceeds_a_comparable_calculated_result(client: TestClient, db: Session) -> None:
    run = SimpleNamespace(net_result="131", net_unit="VCU (t CO2e)")
    for unit in ("tCO2e", "t CO2e", "TCO2E", "VCU", "VCUs", "vcu (t co2e)", "t CO₂e"):
        c = vs.compare_with_calculation(run, Decimal("132"), unit)                # type: ignore[arg-type]
        assert c["comparable"] and c["calculated"] == "131", unit
    for unit in ("kg CO2e", "TEST", "credits"):
        assert not vs.compare_with_calculation(run, Decimal("132"), unit)["comparable"], unit   # never converted
    k = calc_scenario(db, client, 86.13, 30.13, "9763 2000 3000")
    _, s, _, v1, _, run2 = _submitted(client, db, k)
    net = Decimal(run2.net_result)
    over = _decide(client, v1, s["id"], verified_quantity=str(net + 1), verified_quantity_unit=run2.net_unit)
    assert over.json()["error_code"] == "VERIFIED_QUANTITY_EXCEEDS_CALCULATED", over.text
    ok = _decide(client, v1, s["id"], verified_quantity=str(net), verified_quantity_unit=run2.net_unit)
    assert ok.status_code == 201, ok.text
    rec = db.scalars(select(AuditLog).where(AuditLog.action == "VERIFICATION_DECISION_RECORDED",
                                            AuditLog.entity_id == ok.json()["id"])).first()
    assert rec is not None and json.loads(rec.new_value or "{}")["calculation_comparison"]["comparable"] is True


# ---------------------------------------------------------------- 11. a 0-credit / reversal result is stated in the package
def test_zero_or_reversal_result_is_flagged_not_blocking() -> None:
    zero = SimpleNamespace(net_result="0", net_unit="VCU (t CO2e)")
    flags = cr.result_flags(zero, [{"output_code": "REVERSAL", "value": "12.5", "unit": "t CO2e"}])   # type: ignore[arg-type]
    assert [f["code"] for f in flags] == ["ZERO_OR_NEGATIVE_RESULT", "REVERSAL_REPORTED"]
    assert cr.result_flags(SimpleNamespace(net_result="131", net_unit="VCU (t CO2e)"),               # type: ignore[arg-type]
                           [{"output_code": "REVERSAL", "value": "0", "unit": "t CO2e"}]) == []


def test_readiness_package_states_result_flags(client: TestClient, db: Session) -> None:
    k = calc_scenario(db, client, 86.14, 30.14, "9764 2000 3000")
    _, s, _, _, _, _ = _submitted(client, db, k)
    pkg = client.get(f"/api/v1/calculations/readiness/{s['readiness_review_id']}/package", headers=k.x.c.t.pm.headers).json()
    assert pkg["manifest"]["result_flags"] == []                    # a positive result: stated as such (no flag), still explicit
    view = _view(client, k.qa, k)
    assert next(c for c in view["checks"] if c["key"] == "net_result")["result"] == "PASS"


# ---------------------------------------------------------------- 2. issuance cancellation: another person, under the lock
def test_issuance_cancel_needs_a_second_person(client: TestClient, db: Session) -> None:
    k = calc_scenario(db, client, 86.15, 30.15, "9765 2000 3000")
    reg = Reg(client, db, k)
    sid = reg.accepted()["id"]
    i1 = reg.issue(sid, 100, "TEST-ISS-CX-1").json()
    assert reg.confirm(i1["id"]).status_code == 200
    assert _notified(db, reg.rm.user.id, "CREDIT_ISSUANCE_CONFIRMED") == 1               # 12. the recorder learns it is confirmed
    body = {"reason": "TEST: registry cancelled", "document_id": reg.doc(f"{R}/submissions/{sid}/documents", "REGISTRY_RESPONSE")}
    assert codes(reg.post(f"{R}/issuances/{i1['id']}/cancel", body)) == "SEPARATION_OF_DUTIES"
    other = staff(db, client, reg.org, "REGISTRY_MANAGER")
    done = reg.post(f"{R}/issuances/{i1['id']}/cancel", body, other)
    assert done.status_code == 200 and done.json()["status"] == "CANCELLED", done.text
    assert codes(reg.post(f"{R}/issuances/{i1['id']}/cancel", body, other)) == "ISSUANCE_NOT_CONFIRMED"


# ---------------------------------------------------------------- 12. notifications: VVB assignment and decision
def test_vvb_assignment_and_decision_notify_the_other_side(client: TestClient, db: Session) -> None:
    k = calc_scenario(db, client, 86.16, 30.16, "9766 2000 3000")
    a, s, _, v1, v2, run = _submitted(client, db, k)
    assert _notified(db, v1.user.id, "VERIFICATION_ASSIGNMENT_PROPOSED") == 1 and _notified(db, v2.user.id, "VERIFICATION_ASSIGNMENT_PROPOSED") == 1
    d = _decide(client, v1, s["id"], verified_quantity=run.net_result, verified_quantity_unit=run.net_unit)
    assert d.status_code == 201, d.text
    assert _notified(db, k.x.c.t.pm.user.id, "VERIFICATION_DECISION_RECORDED") == 1
    assert _notified(db, v1.user.id, "VERIFICATION_DECISION_RECORDED") == 0                     # the VVB side is not told its own decision
    assert client.get(f"{VVB}/assignments/{a['id']}", headers=v1.headers).status_code == 200


# ---------------------------------------------------------------- 8. orders never get stuck in ATTENTION_REQUIRED
def test_order_completes_from_attention_and_retry_refuses_when_nothing_is_pending(client: TestClient, db: Session) -> None:
    m = M(client, db, 86.17, 30.17, "9767 2000 3000")
    m.verify_buyer()
    lst = m.listing(600, "10.00", rng=m.range600)
    o = m.purchase(lst["id"], 50)
    assert o["status"] == "TRANSFER_PENDING"
    assert _notified(db, m.buyer.user.id, "ORDER_PAID") == 1 and _notified(db, m.fin.user.id, "ORDER_PAID") == 1
    x = db.get(Order, uuid.UUID(o["id"]))
    os_.attention(db, RequestContext(user_id=m.cm.user.id), x, "TEST: buyer asked to hold the delivery")   # attention, delivery in flight
    db.commit()
    assert codes(m.post(f"{ORD}/{o['id']}/retry-transfer", {"reason": "TEST"}, m.cm)) == "NOTHING_TO_RETRY"
    assert m.get(f"{ORD}/{o['id']}").json()["status"] == "ATTENTION_REQUIRED"
    done = m.post(f"{ORD}/transfers/{o['items'][0]['transfer_id']}/complete", {}, m.qa)
    assert done.status_code == 200 and done.json()["status"] == "COMPLETED", done.text        # the last delivery completes it
    assert done.json()["items"][0]["status"] == "DELIVERED"
    assert _notified(db, m.buyer.user.id, "ORDER_ITEM_DELIVERED") == 1 and _notified(db, m.buyer.user.id, "ORDER_COMPLETED") == 1
    assert _notified(db, m.fin.user.id, "ORDER_COMPLETED") == 1


# ---------------------------------------------------------------- 5. provider refund: outbox marker first, never called twice
def test_provider_refund_is_marked_before_the_call_and_never_repeated(client: TestClient, db: Session) -> None:
    m = M(client, db, 86.18, 30.18, "9768 2000 3000")
    m.verify_buyer()
    lst = m.listing(600, "10.00", rng=m.range600)
    adapter = TestPaymentAdapter()
    buyer_p, fin_p = load_principal(db, m.buyer.user, None), load_principal(db, m.fin.user, None)
    bctx, fctx, sys_ctx = RequestContext(user_id=m.buyer.user.id), RequestContext(user_id=m.fin.user.id), RequestContext.system()
    o = m.order([(lst["id"], 10)]).json()
    p = ps.start_provider_payment(db, bctx, buyer_p, uuid.UUID(o["id"]), adapter)
    assert m.post(f"{ORD}/{o['id']}/cancel", {"reason": "TEST: abandoned checkout"}).json()["status"] == "CANCELLED"
    assert ps.ingest_event(db, sys_ctx, adapter, adapter.event("EV-R1", p.external_reference, "SUCCEEDED")) == "UNMATCHED"
    rf = m.post(f"{PAY}/{p.id}/refunds", {"reason": "TEST: unmatched payment"}, m.fin).json()
    assert m.post(f"/api/v1/refunds/{rf['id']}/approve", {}, m.fin2).status_code == 200
    calls: list[str] = []

    def timeout(ext: str, amount: Decimal, currency: str, key: str) -> Any:
        calls.append(key)
        assert db.scalar(select(func.count()).select_from(PaymentEvent).where(PaymentEvent.event_type == "REFUND_ATTEMPT")) == 1
        raise PaymentTimeout("TEST provider did not answer")
    adapter.refund = timeout                                        # type: ignore[method-assign]
    with pytest.raises(Conflict) as e:
        ps.decide_refund(db, fctx, fin_p, uuid.UUID(rf["id"]), "complete", None, None, adapter)
    assert e.value.error_code == "REFUND_UNCONFIRMED" and calls == [rf["refund_code"]]
    with pytest.raises(ValidationFailed) as e2:                     # the outcome is unknown: completed by people, with evidence
        ps.decide_refund(db, fctx, fin_p, uuid.UUID(rf["id"]), "complete", None, None, adapter)
    assert e2.value.error_code == "REFUND_EVIDENCE_REQUIRED" and calls == [rf["refund_code"]]   # the provider is never called again
    ev = m.upload(f"/api/v1/refunds/{rf['id']}/documents", m.fin)
    assert ev.status_code == 201, ev.text
    done = ps.decide_refund(db, fctx, fin_p, uuid.UUID(rf["id"]), "complete",
                            SimpleNamespace(external_reference="TRFD-RECONCILED-1", document_id=uuid.UUID(ev.json()["document_id"])), None,
                            adapter)
    assert done.status == "COMPLETED" and done.external_reference == "TRFD-RECONCILED-1" and calls == [rf["refund_code"]]
    actions = {a for (a,) in db.execute(select(AuditLog.action).where(AuditLog.entity_id == rf["id"]))}
    assert {"REFUND_PROVIDER_ATTEMPTED", "REFUND_PROVIDER_UNCONFIRMED", "REFUND_COMPLETED"} <= actions


# ---------------------------------------------------------------- 13. project-level costs: explicit opt-in, deducted once
def test_project_level_costs_are_deducted_only_by_an_opted_in_run(client: TestClient, db: Session) -> None:
    f = F(client, db, 86.19, 30.19, "9769 2000 3000")
    f.sale(100, "12.50")                                            # 1250.00 INR
    share = f.share("40", deduct=True, rounding="HALF_UP")
    alloc = f.allocation(["50", "50"])
    f.cost("100.00")                                                # project-level (no monitoring period)
    plain = f.run(share, alloc, calculate=False)
    r1 = f.post(f"/settlements/{plain['id']}/calculate", {}, f.fin2).json()
    assert Decimal(r1["deducted_costs"]) == 0 and Decimal(r1["distributable"]) == Decimal("1250")    # never picked up implicitly
    snap = json.loads(db.get(SettlementRun, uuid.UUID(r1["id"])).input_snapshot)
    assert snap["inputs"]["include_project_costs"] is False and snap["inputs"]["project_level_costs_not_included"] == 1
    assert f.post(f"/settlements/{r1['id']}/cancel", {"reason": "TEST: include the project costs"}, f.fin2).status_code == 200
    opted = f.run(share, alloc, calculate=False)
    r2 = f.post(f"/settlements/{opted['id']}/calculate", {"include_project_costs": True}, f.fin2).json()
    assert Decimal(r2["deducted_costs"]) == Decimal("100") and Decimal(r2["distributable"]) == Decimal("1150")
    assert f.get(f"/settlements/{r2['id']}/verify").json()["reproducible"] is True
    no_costs = f.share("40", deduct=False, rounding="HALF_UP")
    other = f.run(no_costs, alloc, calculate=False)
    assert codes(f.post(f"/settlements/{other['id']}/calculate", {"include_project_costs": True}, f.fin2)) == "COSTS_NOT_DEDUCTED"
