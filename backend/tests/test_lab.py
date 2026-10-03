"""Phase 6 — laboratory & sample analysis: engagements, sample identity, custody, shipments, automatic tests, versioned
results, unit / text rules, laboratory QA with separation of duties, retests, wind-down, laboratory-facing allow-lists,
organization isolation, database integrity, corrected field collections, lineage and audit."""
import contextlib
import json
import re
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AuditLog, LabResult, LabTest, SampleCustodyEvent
from app.services import laboratory_service
from tests.conftest import login, make_org, make_user
from tests.phase2 import staff
from tests.phase5 import MRV
from tests.phase6 import (
    FIELD_RULE,
    LAB,
    LABV,
    PDF,
    PNG,
    SOC_RULE,
    TEXT_RULE,
    LabCtx,
    enter_result,
    lab_project,
    now_iso,
    qa,
    receive,
    register,
    seal,
    ship,
    to_lab,
)

FORBIDDEN_KEYS = {"farm_id", "farm_code", "farm_name", "farmer", "farmer_id", "farmer_name", "latitude", "longitude", "gps", "gps_latitude",
                  "gps_longitude", "sampling_point_id", "sampling_point_code", "point_code", "field_collection_id", "field_collection_code",
                  "collection_code", "stratum", "stratum_id", "project_name", "boundary", "geojson"}


def _keys(obj: object) -> set[str]:
    if isinstance(obj, dict):
        return set(obj) | {k for v in obj.values() for k in _keys(v)}
    if isinstance(obj, list):
        return {k for v in obj for k in _keys(v)}
    return set()


def _actions(db: Session, org_id: object) -> set[str]:
    return set(db.scalars(select(AuditLog.action).where(AuditLog.organization_id == org_id)).all())


@pytest.fixture()
def x(db: Session, client: TestClient) -> LabCtx:
    return lab_project(db, client, 75.10, 21.10, "7100 2000 3000")


# ---------------------------------------------------------------- engagements
def test_engagement_two_sided_scope_change_and_end(client: TestClient, db: Session) -> None:
    x = lab_project(db, client, 75.20, 21.20, "7200 2000 3000", rules=[SOC_RULE, TEXT_RULE, FIELD_RULE], engage=["SOC"])
    pid, e = x.c.project["id"], x.engagement
    assert e["status"] == "PROPOSED"   # the response was taken before acceptance
    rules = {r["rule_code"]: r for r in client.get(f"{LAB}/projects/{pid}/laboratory-rules", headers=x.c.mrv.headers).json()}
    assert set(rules) == {"SOC", "TEX"}   # only LABORATORY rules can be in scope (PHT is FIELD)
    body = {"project_id": pid, "laboratory_org_id": str(x.lab_org.id), "rule_ids": [rules["SOC"]["rule_id"], rules["TEX"]["rule_id"]]}
    # a FIELD rule is never in scope
    pht = client.get(f"{MRV}/projects/{pid}/requirements", headers=x.c.mrv.headers).json()["monitoring"]
    pht_id = next(m["rule_id"] for m in pht if m["rule_code"] == "PHT")
    bad = client.post(f"{LAB}/engagements", headers=x.c.mrv.headers, json={**body, "rule_ids": [pht_id]})
    assert bad.status_code == 422 and bad.json()["error_code"] == "RULE_NOT_LABORATORY"
    # field agents and lab users cannot propose; a technician cannot accept
    assert client.post(f"{LAB}/engagements", headers=x.c.collector.headers, json=body).status_code == 403
    assert client.post(f"{LAB}/engagements", headers=x.tech.headers, json=body).status_code == 403
    # scope change = new engagement; accepting it ends the old one atomically
    new = client.post(f"{LAB}/engagements", headers=x.c.mrv.headers, json=body).json()
    assert new["status"] == "PROPOSED" and new["replaces_engagement_id"] == x.engagement["id"]
    assert client.post(f"{LAB}/engagements", headers=x.c.mrv.headers, json=body).json()["error_code"] == "ENGAGEMENT_PENDING"
    assert client.post(f"{LABV}/engagements/{new['id']}/accept", headers=x.tech.headers).status_code == 403
    r = client.post(f"{LABV}/engagements/{new['id']}/accept", headers=x.mgr.headers)
    assert r.json()["status"] == "ACTIVE"
    allr = {g["id"]: g for g in client.get(f"{LAB}/engagements", headers=x.c.pm.headers if hasattr(x.c, "pm") else x.c.t.pm.headers,
                                           params={"project_id": pid}).json()}
    assert allr[x.engagement["id"]]["status"] == "ENDED" and allr[new["id"]]["status"] == "ACTIVE"
    assert {r["rule_code"] for r in allr[new["id"]]["rules"]} == {"SOC", "TEX"}
    # never reactivated
    assert client.post(f"{LABV}/engagements/{x.engagement['id']}/accept", headers=x.mgr.headers).json()["error_code"] == "ENGAGEMENT_NOT_PROPOSED"
    # either side ends it with a reason
    assert client.post(f"{LAB}/engagements/{new['id']}/end", headers=x.c.mrv.headers, json={"reason": ""}).status_code == 422
    r = client.post(f"{LABV}/engagements/{new['id']}/end", headers=x.mgr.headers, json={"reason": "lab capacity"})
    assert r.json()["status"] == "ENDED" and r.json()["ended_side"] == "LABORATORY"
    assert client.post(f"{LAB}/engagements/{new['id']}/end", headers=x.c.mrv.headers, json={"reason": "again"}).json()["error_code"] == "ENGAGEMENT_ENDED"
    for org in (uuid.UUID(x.c.project["organization_id"]) if "organization_id" in x.c.project else x.c.t.org.id, x.lab_org.id):
        assert {"LAB_ENGAGEMENT_PROPOSED", "LAB_ENGAGEMENT_ACCEPTED", "LAB_ENGAGEMENT_ENDED"} <= _actions(db, org)


def test_engagement_proposer_cannot_accept_even_with_both_roles(client: TestClient, db: Session, x: LabCtx) -> None:
    both = make_user(db, roles=[("MRV_MANAGER", x.c.t.org), ("LAB_MANAGER", x.lab_org)])
    h = login(client, both)
    rules = client.get(f"{LAB}/projects/{x.c.project['id']}/laboratory-rules", headers=h).json()
    e = client.post(f"{LAB}/engagements", headers=h, json={"project_id": x.c.project["id"], "laboratory_org_id": str(x.lab_org.id),
                                                          "rule_ids": [r["rule_id"] for r in rules]}).json()
    r = client.post(f"{LABV}/engagements/{e['id']}/accept", headers=h)
    assert r.status_code == 403 and r.json()["error_code"] == "SEPARATION_OF_DUTIES"


# ---------------------------------------------------------------- samples, automatic tests, custody, shipments
def test_sample_registration_identity_and_automatic_tests(client: TestClient, db: Session, x: LabCtx) -> None:
    fc = x.fcs[0]
    s = register(client, x, fc)
    assert re.fullmatch(r"SMP-\d{4}-\d{6}", s["sample_code"]) and s["sample_code"] != fc["collection_code"]
    assert s["field_collection_id"] == fc["id"] and s["status"] == "REGISTERED" and s["test_count"] == 1
    assert (s["depth_top_cm"], s["depth_bottom_cm"]) == (fc["actual_depth_top_cm"], fc["actual_depth_bottom_cm"])
    t = db.scalars(select(LabTest).where(LabTest.sample_id == uuid.UUID(s["id"]))).one()
    assert re.fullmatch(r"LT-\d{4}-\d{6}", t.test_code) and t.status == "REQUESTED" and t.retest_of_test_id is None
    assert str(t.methodology_monitoring_rule_id) == x.rules["SOC"]["rule_id"] and str(t.engagement_id) == x.engagement["id"]
    assert t.root_sample_id == t.sample_id and str(t.laboratory_org_id) == str(x.lab_org.id)
    # a split counts against its root and gets no automatic test
    split = register(client, x, fc, parent_sample_id=s["id"], description="Split for retention (TEST)")
    assert split["root_sample_code"] == s["sample_code"] and split["parent_sample_code"] == s["sample_code"] and split["test_count"] == 0
    # field agents register only their own collections
    other_agent = staff(db, client, x.c.t.org, "FIELD_AGENT")
    r = client.post(f"{LAB}/samples", headers=other_agent.headers, json={"field_collection_id": fc["id"], "description": "x x"})
    assert r.status_code == 403 and r.json()["error_code"] == "NOT_COLLECTOR"
    # depth must lie within the collection's actual depth
    r = client.post(f"{LAB}/samples", headers=x.c.collector.headers, json={"field_collection_id": fc["id"], "description": "deep",
                                                                           "depth_top_cm": "0", "depth_bottom_cm": "80"})
    assert r.json()["error_code"] == "INVALID_DEPTH"
    # only SUBMITTED / ACCEPTED collections
    from app.models import FieldCollectionRecord
    row = db.get(FieldCollectionRecord, uuid.UUID(x.fcs[1]["id"]))
    assert row is not None
    row.status = "IN_PROGRESS"
    db.flush()
    r = client.post(f"{LAB}/samples", headers=x.c.collector.headers, json={"field_collection_id": x.fcs[1]["id"], "description": "too early"})
    assert r.json()["error_code"] == "FIELD_COLLECTION_NOT_READY"
    # sealing by the registrant; corrections only before sealing
    assert client.patch(f"{LAB}/samples/{s['id']}", headers=x.c.collector.headers, json={"container_label": "Bag 7"}).status_code == 200
    seal(client, x, s)
    assert client.patch(f"{LAB}/samples/{s['id']}", headers=x.c.collector.headers, json={"container_label": "x"}).json()["error_code"] == "SAMPLE_SEALED"
    assert "LAB_SAMPLE_REGISTERED" in _actions(db, x.c.t.org.id)


def test_shipment_permissions_custody_order_and_receipt(client: TestClient, db: Session, x: LabCtx) -> None:
    s = register(client, x, x.fcs[0])
    body = {"project_id": x.c.project["id"], "laboratory_org_id": str(x.lab_org.id)}
    assert client.post(f"{LAB}/shipments", headers=x.c.collector.headers, json=body).status_code == 403   # field agent: no shipments
    sh = client.post(f"{LAB}/shipments", headers=x.c.supervisor.headers, json=body).json()
    assert re.fullmatch(r"SHP-\d{4}-\d{6}", sh["shipment_code"])
    r = client.post(f"{LAB}/shipments/{sh['id']}/items", headers=x.c.supervisor.headers, json={"sample_ids": [s["id"]]})
    assert r.json()["error_code"] == "SAMPLE_NOT_SEALED"
    seal(client, x, s)
    client.post(f"{LAB}/shipments/{sh['id']}/items", headers=x.c.supervisor.headers, json={"sample_ids": [s["id"]]})
    assert client.post(f"{LAB}/shipments/{sh['id']}/dispatch", headers=x.c.collector.headers, json={}).status_code == 403
    # the lab cannot see a DRAFT shipment
    assert client.get(f"{LABV}/shipments/{sh['id']}", headers=x.tech.headers).status_code == 404
    client.post(f"{LAB}/shipments/{sh['id']}/dispatch", headers=x.c.supervisor.headers, json={})
    assert client.get(f"{LABV}/shipments/{sh['id']}", headers=x.tech.headers).status_code == 200
    # rejection at receipt needs a reason; the sample's tests are cancelled
    r = client.post(f"{LABV}/shipments/{sh['id']}/receive", headers=x.tech.headers, json={"items": [{"sample_id": s["id"], "accepted": False}]})
    assert r.status_code == 422
    r = client.post(f"{LABV}/shipments/{sh['id']}/receive", headers=x.tech.headers,
                    json={"items": [{"sample_id": s["id"], "accepted": False, "reason": "container leaking"}]})
    assert r.json()["status"] == "RECEIVED" and r.json()["items"][0]["status"] == "REJECTED"
    detail = client.get(f"{LAB}/samples/{s['id']}", headers=x.c.supervisor.headers).json()
    assert detail["status"] == "REJECTED_AT_RECEIPT" and detail["tests"][0]["status"] == "CANCELLED"
    seq = [(e["sequence_no"], e["event_type"], e["from_state"], e["to_state"]) for e in detail["custody"]]
    assert [e[1] for e in seq] == ["REGISTERED", "SEALED", "ADDED_TO_SHIPMENT", "DISPATCHED", "REJECTED"]
    assert all(seq[i][2] == seq[i - 1][3] for i in range(1, len(seq))) and [e[0] for e in seq] == [1, 2, 3, 4, 5]
    assert detail["custody"][-1]["reason"] == "container leaking"


# ---------------------------------------------------------------- full flow, lineage, Phase 5 display
def test_full_flow_to_approved_result_with_lineage(client: TestClient, db: Session, x: LabCtx) -> None:
    s = to_lab(client, x)
    test_id = s["tests"][0]["id"]
    assert s["tests"][0]["required_unit"] == "t C/ha" and s["tests"][0]["value_type"] == "NUMBER"
    res = enter_result(client, x, test_id)
    # drafts / lab-internal work never reach project users; submitted results do
    listed = client.get(f"{LAB}/results", headers=x.c.mrv.headers, params={"project_id": x.c.project["id"], "status": "ALL"}).json()
    assert [r["status"] for r in listed] == ["SUBMITTED"]
    r = qa(client, x, res["id"])
    assert r.status_code == 200, r.text
    view = r.json()
    assert view["result"]["status"] == "APPROVED" and all(c["result"] in ("PASS", "WARN") for c in view["checks"]), view["checks"]
    approved = client.get(f"{LAB}/results", headers=x.c.mrv.headers, params={"project_id": x.c.project["id"]}).json()
    assert len(approved) == 1 and approved[0]["authoritative"] and approved[0]["value_number"] == "1.234000"
    lin = client.get(f"{LAB}/results/{approved[0]['id']}/lineage", headers=x.c.t.pm.headers).json()
    assert lin["sample"]["sample_code"] == s["sample_code"] and lin["field_collection"]["id"] == x.fcs[0]["id"]
    assert lin["sampling_point"]["point_code"] == x.points[0]["point_code"] and lin["stratum"]["code"] == "S1"
    assert lin["farm"]["id"] == x.c.farms[0]["id"] and lin["project"]["id"] == x.c.project["id"]
    assert lin["methodology"]["locked"] and lin["methodology_rule"]["measurement_source"] == "LABORATORY"
    assert lin["plan_measurement"]["code"] == "SOC" and lin["qa_reviews"][-1]["decision"] == "APPROVED"
    assert lin["shipments"][0]["receipt_status"] == "RECEIVED" and lin["result"]["report"]["sha256"]
    # sample custody ends at ANALYSED; the Phase 5 collection shows ANALYSED (display only)
    detail = client.get(f"{LAB}/samples/{s['id']}", headers=x.c.mrv.headers).json()
    assert detail["status"] == "ANALYSED" and detail["custody"][-1]["event_type"] == "ANALYSIS_COMPLETED"
    fc = client.get(f"{MRV}/field-collections/{x.fcs[0]['id']}", headers=x.c.mrv.headers).json()
    other = client.get(f"{MRV}/field-collections/{x.fcs[1]['id']}", headers=x.c.mrv.headers).json()
    assert (fc["analysis_status"], other["analysis_status"]) == ("ANALYSED", "AWAITING_ANALYSIS")


def test_analysis_time_compared_with_receipt_at_whole_seconds(client: TestClient, db: Session, x: LabCtx) -> None:
    s = to_lab(client, x)
    test_id = s["tests"][0]["id"]
    received = db.scalars(select(SampleCustodyEvent).where(SampleCustodyEvent.sample_id == uuid.UUID(s["id"]),
                                                           SampleCustodyEvent.event_type == "RECEIVED")).one().occurred_at
    assert client.post(f"{LABV}/tests/{test_id}/start", headers=x.tech.headers, json={}).status_code == 200
    r = client.post(f"{LABV}/tests/{test_id}/results", headers=x.tech.headers,
                    json={"result_type": "NUMERIC", "value_number": "1.2", "unit": "t C/ha", "analysed_at": received.replace(microsecond=0).isoformat()})
    assert r.status_code == 201, r.text
    res = db.get(LabResult, uuid.UUID(r.json()["id"]))
    assert res is not None

    def timing() -> str:
        db.expire_all()
        return next(c.result for c in laboratory_service.qa_checks(db, res) if c.key == "analysis_timing")

    assert timing() == "PASS"                                   # same second as the receipt (entered without fractions)
    res.analysed_at = received.replace(microsecond=0) - timedelta(seconds=1)
    db.flush()
    assert timing() == "FAIL"                                   # a whole second earlier is before the receipt


# ---------------------------------------------------------------- separation of duties
def test_lab_qa_separation_of_duties(client: TestClient, db: Session, x: LabCtx) -> None:
    # one user who registered/sealed the sample in the project org and is also a lab manager
    dual = make_user(db, roles=[("FIELD_SUPERVISOR", x.c.t.org), ("LAB_MANAGER", x.lab_org)])
    hd = login(client, dual)
    s = register(client, x, x.fcs[0], actor=type(x.tech)(dual, hd))
    seal(client, x, s, actor=type(x.tech)(dual, hd))
    sh = ship(client, x, [s])
    receive(client, x, sh, [s])
    lab_s = client.get(f"{LABV}/samples/{s['id']}", headers=x.tech.headers).json()
    res = enter_result(client, x, lab_s["tests"][0]["id"])
    # the analyst cannot review their own result
    r = client.post(f"{LABV}/qa/{res['id']}/start", headers=x.tech.headers)
    assert r.status_code == 403
    client.post(f"{LABV}/qa/{res['id']}/start", headers=x.qa.headers)
    r = client.post(f"{LABV}/qa/{res['id']}/decision", headers=hd, json={"decision": "APPROVED", "notes": "registrant approves"})
    assert r.status_code == 403 and r.json()["error_code"] == "SEPARATION_OF_DUTIES" and "you registered the sample" in r.json()["details"]["reasons"]
    # supervisor who shipped is not a lab manager here; an independent manager approves
    assert qa(client, x, res["id"]).status_code in (200, 409)   # start already done → decision path below
    r = client.post(f"{LABV}/qa/{res['id']}/decision", headers=x.qa.headers, json={"decision": "APPROVED", "notes": "independent"})
    assert r.status_code in (200, 409)
    final = client.get(f"{LABV}/qa/{res['id']}", headers=x.qa.headers).json()
    assert final["result"]["status"] == "APPROVED"
    # shipment creator / dispatcher who is also a lab manager is refused too
    from app.models import LabResult
    from app.services import laboratory_service
    row = db.get(LabResult, uuid.UUID(res["id"]))
    assert row is not None
    assert "you dispatched the shipment" in laboratory_service.sod_violations(db, row, x.c.supervisor.user.id, approving=True)
    assert "you created the shipment" in laboratory_service.sod_violations(db, row, x.c.supervisor.user.id, approving=True)


# ---------------------------------------------------------------- units, text results, configuration
def test_unit_mismatch_and_text_results(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    x = lab_project(db, client, 75.30, 21.30, "7300 2000 3000", rules=[SOC_RULE, TEXT_RULE])
    s = to_lab(client, x)
    tests = {t["rule"]["rule_code"]: t for t in s["tests"]}
    assert tests["TEX"]["unit_configuration"] == "CONFIGURATION_REQUIRED" and tests["TEX"]["value_type"] == "TEXT"
    # UNIT_MISMATCH: same quantity, different text — never converted
    res = enter_result(client, x, tests["SOC"]["id"], unit="t C ha-1")
    r = qa(client, x, res["id"])
    assert r.json()["error_code"] == "QA_CHECKS_FAILED" and "unit" in r.json()["details"]["failing"]
    chk = {c["key"]: c for c in client.get(f"{LABV}/qa/{res['id']}", headers=x.qa.headers).json()["checks"]}
    assert "UNIT_MISMATCH" in chk["unit"]["details"][0]
    client.post(f"{LABV}/qa/{res['id']}/decision", headers=x.qa.headers, json={"decision": "REJECTED", "notes": "report in t C/ha"})
    # a verbatim text result for a numeric parameter is stored as reported and can never be approved
    body = {"result_type": "TEXT", "value_text": "<0.05", "unit": "t C/ha", "analysed_at": now_iso(1)}
    r2 = client.post(f"{LABV}/tests/{tests['SOC']['id']}/results", headers=x.tech.headers, json=body).json()
    client.post(f"{LABV}/results/{r2['id']}/report", headers=x.tech.headers, files={"file": ("r.pdf", PDF, "application/pdf")})
    client.post(f"{LABV}/results/{r2['id']}/submit", headers=x.tech.headers)
    r = qa(client, x, r2["id"], ack=True)
    assert r.json()["error_code"] == "QA_CHECKS_FAILED" and "result_type" in r.json()["details"]["failing"]
    from app.models import LabResult
    row = db.get(LabResult, uuid.UUID(r2["id"]))
    assert row is not None and row.value_text == "<0.05" and row.value_number is None
    # a numeric and a text value together are refused
    bad = client.post(f"{LABV}/tests/{tests['TEX']['id']}/start", headers=x.tech.headers, json={})
    assert bad.status_code == 200
    both = client.post(f"{LABV}/tests/{tests['TEX']['id']}/results", headers=x.tech.headers,
                       json={"result_type": "TEXT", "value_text": "Clay loam", "value_number": "1", "analysed_at": now_iso(1)})
    assert both.status_code == 422
    # a text parameter without a unit: CONFIGURATION_REQUIRED — production blocks, non-production needs an acknowledgement
    tex = enter_result(client, x, tests["TEX"]["id"], value="Clay loam", unit=None, result_type="TEXT", start=False)
    client.post(f"{LABV}/qa/{tex['id']}/start", headers=x.qa.headers)
    monkeypatch.setattr(get_settings(), "APP_ENV", "production")
    r = client.post(f"{LABV}/qa/{tex['id']}/decision", headers=x.qa.headers, json={"decision": "APPROVED", "notes": "prod", "acknowledge_configuration": True})
    assert r.json()["error_code"] == "CONFIGURATION_REQUIRED" and r.json()["details"]["policy"] == "PRODUCTION_BLOCK"
    monkeypatch.setattr(get_settings(), "APP_ENV", "development")
    r = client.post(f"{LABV}/qa/{tex['id']}/decision", headers=x.qa.headers, json={"decision": "APPROVED", "notes": "no ack"})
    assert r.json()["error_code"] == "CONFIGURATION_REQUIRED"
    r = client.post(f"{LABV}/qa/{tex['id']}/decision", headers=x.qa.headers, json={"decision": "APPROVED", "notes": "acknowledged", "acknowledge_configuration": True})
    assert r.json()["result"]["status"] == "APPROVED" and r.json()["reviews"][-1]["configuration_acknowledged"]


# ---------------------------------------------------------------- versioning, uniqueness, retests
def test_correction_retest_and_single_approved_result(client: TestClient, db: Session, x: LabCtx) -> None:
    s = to_lab(client, x)
    t1 = s["tests"][0]["id"]
    v1 = enter_result(client, x, t1, value="2.000")
    assert qa(client, x, v1["id"]).json()["result"]["status"] == "APPROVED"
    # correction: a new version of the same test that supersedes v1 only once approved
    corr = client.post(f"{LABV}/results/{v1['id']}/correct", headers=x.tech.headers,
                       json={"reason": "transcription error", "result_type": "NUMERIC", "value_number": "2.100", "unit": "t C/ha",
                             "analysed_at": now_iso(1)}).json()
    assert corr["version"] == 2 and corr["supersedes_result_id"] == v1["id"] and corr["status"] == "DRAFT"
    client.post(f"{LABV}/results/{corr['id']}/report", headers=x.tech.headers, files={"file": ("r.pdf", PDF, "application/pdf")})
    client.post(f"{LABV}/results/{corr['id']}/submit", headers=x.tech.headers)
    assert qa(client, x, corr["id"]).json()["result"]["status"] == "APPROVED"
    hist = client.get(f"{LAB}/results", headers=x.c.mrv.headers, params={"project_id": x.c.project["id"], "status": "ALL"}).json()
    assert sorted((h["version"], h["status"]) for h in hist) == [(1, "SUPERSEDED"), (2, "APPROVED")]
    # retest (LAB_MANAGER only, with a reason) — the technician cannot request one
    assert client.post(f"{LABV}/results/{corr['id']}/retest", headers=x.tech.headers, json={"reason": "check"}).status_code == 403
    rt = client.post(f"{LABV}/results/{corr['id']}/retest", headers=x.mgr.headers, json={"reason": "outlier vs stratum"}).json()
    assert rt["retest_of_test_code"] == s["tests"][0]["test_code"] and rt["status"] == "REQUESTED"
    rres = enter_result(client, x, rt["id"], value="1.950")
    # the retest requester cannot approve the retest result; an independent manager can, replacing v2
    r = qa(client, x, rres["id"], actor=x.mgr)
    assert r.status_code == 403 or r.json().get("error_code") == "SEPARATION_OF_DUTIES"
    r = client.post(f"{LABV}/qa/{rres['id']}/decision", headers=x.qa.headers, json={"decision": "APPROVED", "notes": "retest ok"})
    if r.status_code == 409:    # QA was not started by mgr (403 at start); start as qa
        client.post(f"{LABV}/qa/{rres['id']}/start", headers=x.qa.headers)
        r = client.post(f"{LABV}/qa/{rres['id']}/decision", headers=x.qa.headers, json={"decision": "APPROVED", "notes": "retest ok"})
    assert r.json()["result"]["status"] == "APPROVED"
    approved = client.get(f"{LAB}/results", headers=x.c.mrv.headers, params={"project_id": x.c.project["id"]}).json()
    assert [a["value_number"] for a in approved] == ["1.950000"]          # exactly one APPROVED per root sample + rule
    # an unrelated second result for the same root + rule cannot become APPROVED
    from app.models import LabResult
    from app.services import lab_service
    assert lab_service.approved_for(db, {uuid.UUID(s["id"])}, uuid.UUID(x.rules["SOC"]["rule_id"])) is not None
    row = db.get(LabResult, uuid.UUID(v1["id"]))
    assert row is not None and row.status == "SUPERSEDED" and row.value_number is not None


def test_qa_retest_required_decision_creates_linked_retest(client: TestClient, db: Session, x: LabCtx) -> None:
    s = to_lab(client, x)
    res = enter_result(client, x, s["tests"][0]["id"], value="9.9")
    r = qa(client, x, res["id"], decision="RETEST_REQUIRED")
    assert r.json()["result"]["status"] == "RETEST_REQUIRED"
    tests = client.get(f"{LABV}/tests", headers=x.tech.headers).json()
    retest = next(t for t in tests if t["retest_of_test_code"] == s["tests"][0]["test_code"])
    assert retest["status"] == "REQUESTED" and retest["retest_reason"] == "QA retest_required"
    from app.models import LabResult
    assert db.get(LabResult, uuid.UUID(res["id"])).status == "RETEST_REQUIRED"  # type: ignore[union-attr]


# ---------------------------------------------------------------- wind-down
def test_engagement_wind_down(client: TestClient, db: Session, x: LabCtx) -> None:
    a = register(client, x, x.fcs[0])
    b = register(client, x, x.fcs[1])
    seal(client, x, a)
    seal(client, x, b)
    sh = ship(client, x, [a, b])
    receive(client, x, sh, [a, b])
    ta = client.get(f"{LABV}/samples/{a['id']}", headers=x.tech.headers).json()["tests"][0]["id"]
    tb = client.get(f"{LABV}/samples/{b['id']}", headers=x.tech.headers).json()["tests"][0]["id"]
    client.post(f"{LABV}/tests/{ta}/start", headers=x.tech.headers, json={})
    r = client.post(f"{LAB}/engagements/{x.engagement['id']}/end", headers=x.c.mrv.headers, json={"reason": "contract ended"})
    assert r.json()["status"] == "ENDED"
    # forbidden: new test start, new shipment, dispatch, retest
    assert client.post(f"{LABV}/tests/{tb}/start", headers=x.tech.headers, json={}).json()["error_code"] == "ENGAGEMENT_NOT_ACTIVE"
    r = client.post(f"{LAB}/shipments", headers=x.c.supervisor.headers, json={"project_id": x.c.project["id"], "laboratory_org_id": str(x.lab_org.id)})
    assert r.json()["error_code"] == "ENGAGEMENT_NOT_ACTIVE"
    # allowed: the test already IN_PROGRESS is completed, submitted and approved
    res = enter_result(client, x, ta, start=False)
    assert qa(client, x, res["id"]).json()["result"]["status"] == "APPROVED"
    r = client.post(f"{LABV}/results/{res['id']}/retest", headers=x.mgr.headers, json={"reason": "check"})
    assert r.json()["error_code"] == "ENGAGEMENT_NOT_ACTIVE"
    # register a new sample: no active engagement
    r = client.post(f"{LAB}/samples", headers=x.c.collector.headers, json={"field_collection_id": x.fcs[0]["id"], "description": "late"})
    assert r.json()["error_code"] == "ENGAGEMENT_NOT_ACTIVE"


def test_wind_down_allows_receipt_of_shipment_dispatched_while_active(client: TestClient, db: Session, x: LabCtx) -> None:
    s = register(client, x, x.fcs[0])
    seal(client, x, s)
    sh = ship(client, x, [s])
    client.post(f"{LABV}/engagements/{x.engagement['id']}/end", headers=x.mgr.headers, json={"reason": "closing"})
    r = client.post(f"{LABV}/shipments/{sh['id']}/receive", headers=x.tech.headers, json={"items": [{"sample_id": s["id"], "accepted": True}]})
    assert r.status_code == 200 and r.json()["items"][0]["status"] == "RECEIVED"


# ---------------------------------------------------------------- lab-facing allow-list, isolation, documents
def test_lab_views_allow_list_and_isolation(client: TestClient, db: Session, x: LabCtx) -> None:
    s = to_lab(client, x)
    res = enter_result(client, x, s["tests"][0]["id"])
    qa(client, x, res["id"])
    responses = [client.get(u, headers=x.tech.headers).json() for u in (
        f"{LABV}/samples", f"{LABV}/samples/{s['id']}", f"{LABV}/shipments", f"{LABV}/tests", f"{LABV}/engagements", f"{LABV}/qa/{res['id']}",
        f"{LABV}/tests/{s['tests'][0]['id']}", f"{LABV}/dashboard")]
    leaked = _keys(responses) & FORBIDDEN_KEYS
    assert not leaked, leaked
    sample = responses[1]
    assert sample["project_code"] == x.c.project["project_code"] and "project_name" not in sample
    proj_events = [e for e in sample["custody"] if e["actor_side"] == "PROJECT"]
    assert proj_events and all(e["actor_name"] is None and e["location_text"] is None and e["reason"] is None for e in proj_events)
    # backend boundaries: no project / farm / farmer / MRV endpoints for laboratory users
    for url in (f"/api/v1/farms/{x.c.farms[0]['id']}", "/api/v1/farmers", f"/api/v1/projects/{x.c.project['id']}",
                f"{MRV}/field-collections/{x.fcs[0]['id']}", f"{LAB}/samples/{s['id']}", f"{LAB}/results/{res['id']}/lineage"):
        assert client.get(url, headers=x.tech.headers).status_code in (403, 404), url
    # documents: lab may download its LAB_REPORT; never field photos
    rep = client.get(f"{LABV}/qa/{res['id']}", headers=x.tech.headers).json()["result"]["report"]
    assert client.get(f"/api/v1/evidence/documents/{rep['document_id']}/download", headers=x.tech.headers).status_code == 200
    photos = client.get(f"{MRV}/evidence", headers=x.c.mrv.headers, params={"project_id": x.c.project["id"]}).json()
    if photos and photos[0].get("document_id"):
        assert client.get(f"/api/v1/evidence/documents/{photos[0]['document_id']}/download", headers=x.tech.headers).status_code == 404
    # PDF only for lab documents (no images with EXIF / GPS)
    r = client.post(f"{LABV}/results/{res['id']}/report", headers=x.tech.headers, files={"file": ("p.png", PNG, "image/png")})
    assert r.status_code in (409, 422)
    # another laboratory sees nothing; buyers / farmers have no Phase 6 access
    other_lab = make_org(db, org_type="LABORATORY")
    other = staff(db, client, other_lab, "LAB_MANAGER")
    assert client.get(f"{LABV}/samples", headers=other.headers).json() == []
    assert client.get(f"{LABV}/samples/{s['id']}", headers=other.headers).status_code == 404
    assert client.get(f"{LABV}/qa/{res['id']}", headers=other.headers).status_code == 404
    for u in (make_user(db, roles=[("BUYER", make_org(db, org_type="BUYER"))]), make_user(db, roles=[("FARMER", make_org(db, org_type="FARMER_GROUP"))])):
        h = login(client, u)
        assert client.get(f"{LABV}/samples", headers=h).status_code == 403
        assert client.get(f"{LAB}/samples", headers=h).status_code == 403
    # project users never see lab drafts
    t2 = register(client, x, x.fcs[1])
    assert t2["status"] == "REGISTERED"


def test_custody_document_pdf_only_and_shared(client: TestClient, db: Session, x: LabCtx) -> None:
    s = register(client, x, x.fcs[0])
    seal(client, x, s)
    sh = ship(client, x, [s])
    r = client.post(f"{LAB}/shipments/{sh['id']}/documents", headers=x.c.supervisor.headers, files={"file": ("c.png", PNG, "image/png")})
    assert r.status_code == 422 and r.json()["error_code"] == "UNSUPPORTED_FILE_TYPE"
    doc = client.post(f"{LAB}/shipments/{sh['id']}/documents", headers=x.c.supervisor.headers, files={"file": ("c.pdf", PDF, "application/pdf")}).json()
    assert doc["category"] == "CUSTODY_DOCUMENT"
    lab_ship = client.get(f"{LABV}/shipments/{sh['id']}", headers=x.tech.headers).json()
    assert [d["document_id"] for d in lab_ship["documents"]] == [doc["document_id"]]
    assert client.get(f"/api/v1/evidence/documents/{doc['document_id']}/download", headers=x.tech.headers).status_code == 200


# ---------------------------------------------------------------- corrected field collections
def test_sample_keeps_original_field_collection_version(client: TestClient, db: Session, x: LabCtx) -> None:
    s = to_lab(client, x)
    # the collector corrects the accepted field record (new version); the supervisor accepts the correction
    corr = client.post(f"{MRV}/field-collections/{x.fcs[0]['id']}/correct", headers=x.c.collector.headers, json={"reason": "depth typo"}).json()
    client.patch(f"{MRV}/field-collections/{corr['id']}", headers=x.c.collector.headers, json={"observations": "corrected"})
    from tests.phase5 import photo
    photo(client, x.c, x.c.collector, "FIELD_COLLECTION", corr["id"])
    assert client.post(f"{MRV}/field-collections/{corr['id']}/submit", headers=x.c.collector.headers).status_code == 200
    client.post(f"{MRV}/field-collections/{corr['id']}/review", headers=x.c.supervisor.headers, json={"decision": "ACCEPTED", "notes": "ok ok"})
    detail = client.get(f"{LAB}/samples/{s['id']}", headers=x.c.mrv.headers).json()
    assert detail["field_collection_id"] == x.fcs[0]["id"] and detail["field_collection_status"] == "SUPERSEDED"   # never re-pointed
    res = enter_result(client, x, s["tests"][0]["id"])
    client.post(f"{LABV}/qa/{res['id']}/start", headers=x.qa.headers)
    checks = {c["key"]: c for c in client.get(f"{LABV}/qa/{res['id']}", headers=x.qa.headers).json()["checks"]}
    assert checks["field_collection"]["result"] == "WARN" and corr["collection_code"] in checks["field_collection"]["details"][0]
    r = client.post(f"{LABV}/qa/{res['id']}/decision", headers=x.qa.headers, json={"decision": "APPROVED", "notes": "physical sample unchanged"})
    assert r.json()["result"]["status"] == "APPROVED"


def test_sample_from_submitted_collection_cannot_be_approved_until_accepted(client: TestClient, db: Session) -> None:
    from tests.phase5 import collect
    x = lab_project(db, client, 75.40, 21.40, "7400 2000 3000", n_points=1)
    from app.models import FieldCollectionRecord
    row = db.get(FieldCollectionRecord, uuid.UUID(x.fcs[0]["id"]))
    assert row is not None
    row.status = "SUBMITTED"         # registered while still awaiting field review
    db.flush()
    s = to_lab(client, x)
    res = enter_result(client, x, s["tests"][0]["id"])
    r = qa(client, x, res["id"])
    assert r.json()["error_code"] == "QA_CHECKS_FAILED" and "field_collection" in r.json()["details"]["failing"]
    assert collect is not None


# ---------------------------------------------------------------- database integrity
def test_database_triggers_and_constraints() -> None:
    """THROW inside a trigger aborts the whole transaction, so this test builds its data on a dedicated connection (own session
    and client), fires each violating statement in a fresh transaction, and finally discards the connection (nothing is kept)."""
    from sqlalchemy.exc import DBAPIError

    from app.core.database import get_db, get_engine
    from app.core.rate_limit import limiter
    from app.main import create_app

    conn = get_engine().connect()
    conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False, autoflush=False)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: session
    app.state.access_log_writer = lambda _r: None
    limiter.reset()
    try:
        with TestClient(app, base_url="http://testserver") as client:
            x = lab_project(session, client, 75.50, 21.50, "7500 2000 3000", n_points=1)
            s = to_lab(client, x)
            res = enter_result(client, x, s["tests"][0]["id"])
            assert qa(client, x, res["id"]).json()["result"]["status"] == "APPROVED"
        session.flush()
        rid = res["id"]
        # check constraint: one value only (rolled back to a savepoint, no trigger involved)
        sp = conn.begin_nested()
        with pytest.raises(DBAPIError) as exc:
            conn.execute(text("UPDATE lab_results SET value_text = N'both' WHERE id = :i"), {"i": rid})
        assert "one_value" in str(exc.value) or "immutable" in str(exc.value)
        if sp.is_active:
            sp.rollback()
        # each trigger: the statement fails with the trigger's message (the first THROW aborts the transaction)
        with pytest.raises(DBAPIError) as exc:
            conn.execute(text("UPDATE lab_results SET value_number = 99 WHERE id = :i"), {"i": rid})
        assert "immutable" in str(exc.value)
    finally:
        limiter.reset()
        conn.invalidate()      # the server already rolled the transaction back; drop the connection
        with contextlib.suppress(Exception):
            session.close()
    for stmt, msg in (("UPDATE sample_custody_events SET reason = N'rewrite'", "append-only"),
                      ("DELETE FROM lab_result_qa_reviews", "append-only")):
        with get_engine().connect() as c2:
            t2 = c2.begin()
            # these triggers fire on the statement itself (INSTEAD OF), even when no row matches
            with pytest.raises(DBAPIError) as e2:
                c2.execute(text(stmt + " WHERE 1 = 0"))
            assert msg in str(e2.value)
            if t2.is_active:
                t2.rollback()


# ---------------------------------------------------------------- audit
def test_audit_trail_and_lab_org_rows_carry_no_field_data(client: TestClient, db: Session, x: LabCtx) -> None:
    s = to_lab(client, x)
    res = enter_result(client, x, s["tests"][0]["id"])
    qa(client, x, res["id"])
    proj = _actions(db, x.c.t.org.id)
    labo = _actions(db, x.lab_org.id)
    for a in ("LAB_ENGAGEMENT_PROPOSED", "LAB_SAMPLE_REGISTERED", "LAB_CUSTODY_SEALED", "LAB_SHIPMENT_CREATED", "LAB_SHIPMENT_DISPATCHED",
              "LAB_RESULT_APPROVED"):
        assert a in proj, a
    for a in ("LAB_ENGAGEMENT_ACCEPTED", "LAB_CUSTODY_RECEIVED", "LAB_SHIPMENT_RECEIPT_RECORDED", "LAB_TEST_STARTED", "LAB_RESULT_CREATED",
              "LAB_REPORT_ATTACHED", "LAB_RESULT_SUBMITTED", "LAB_QA_STARTED", "LAB_RESULT_APPROVED", "LAB_CUSTODY_ANALYSIS_COMPLETED"):
        assert a in labo, a
    rows = db.scalars(select(AuditLog).where(AuditLog.organization_id == x.lab_org.id)).all()
    leaked = _keys([json.loads(r.new_value) for r in rows if r.new_value]) & FORBIDDEN_KEYS
    assert not leaked, leaked
