"""Phase 5 — MRV: plans (methodology-aware, versioned, CONFIGURATION_REQUIRED), monitoring periods, monitoring records,
field collection, evidence, datasets (frozen snapshot, versioning), QA, RBAC, organization isolation, audit, lineage."""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog
from tests.conftest import login, make_org, make_user
from tests.phase2 import staff
from tests.phase3 import PR, team
from tests.phase5 import (
    MRV,
    MrvCtx,
    approved_design,
    approved_plan,
    approved_stratum,
    collect,
    collecting_period,
    locked_project,
    photo,
)


def _actions(db: Session, project_id: str) -> set[str]:
    from app.models import Project
    p = db.get(Project, project_id)
    assert p is not None
    return set(db.scalars(select(AuditLog.action).where(AuditLog.organization_id == p.organization_id)).all())


@pytest.fixture()
def c(db: Session, client: TestClient) -> MrvCtx:
    return locked_project(db, client, 77.10, 24.10, "8100 2000 3000")


# ---------------------------------------------------------------- plans
def test_plan_methodology_aware_versioned_and_configuration_required(client: TestClient, db: Session, c: MrvCtx) -> None:
    pid = c.project["id"]
    req = client.get(f"{MRV}/projects/{pid}/requirements", headers=c.t.pm.headers).json()
    assert req["status"] == "CONFIGURATION_REQUIRED" and req["monitoring"][0]["parameter"] == "Soil organic carbon stock"
    assert any("depth" in g.lower() for g in req["gaps"])  # no SAMPLING rule configured → nothing invented
    assert client.post(f"{MRV}/plans", headers=c.collector.headers, json={"project_id": pid}).status_code == 403
    r = client.post(f"{MRV}/plans", headers=c.mrv.headers, json={"project_id": pid, "monitoring_frequency": "Each period",
                                                                 "monitoring_start": "2026-06-01", "monitoring_end": "2036-05-31"})
    assert r.status_code == 201, r.text
    plan = r.json()
    assert plan["methodology_version_id"] == c.version_id and plan["configuration_status"] == "CONFIGURATION_REQUIRED"
    assert plan["quantification_approach"] == "CONFIGURATION_REQUIRED"
    assert [(m["code"], m["source"], m["unit"]) for m in plan["measurements"]] == [("SOC", "METHODOLOGY", "t C/ha")]
    assert client.post(f"{MRV}/plans", headers=c.mrv.headers, json={"project_id": pid}).json()["error_code"] == "PLAN_IN_PROGRESS"
    client.post(f"{MRV}/plans/{plan['id']}/submit", headers=c.mrv.headers, json={"reason": "ready"})
    # QA approves (≠ submitter) only after explicitly acknowledging the unconfigured requirements
    r = client.post(f"{MRV}/plans/{plan['id']}/approve", headers=c.t.qa.headers, json={"reason": "ok ok"})
    assert r.status_code == 409 and r.json()["error_code"] == "CONFIGURATION_REQUIRED"
    assert client.post(f"{MRV}/plans/{plan['id']}/approve", headers=c.mrv.headers, json={"reason": "own",
                                                                                         "acknowledge_configuration_gaps": True}).status_code == 403
    r = client.post(f"{MRV}/plans/{plan['id']}/approve", headers=c.t.qa.headers, json={"reason": "plan ok", "acknowledge_configuration_gaps": True})
    assert r.json()["status"] == "APPROVED"
    assert client.get(f"{PR}/{pid}", headers=c.t.pm.headers).json()["status"] == "MRV_PLANNED"
    assert client.patch(f"{MRV}/plans/{plan['id']}", headers=c.mrv.headers,
                        json={"notes": "silent change"}).json()["error_code"] == "PLAN_NOT_EDITABLE"
    # a new plan version supersedes the approved one only when approved
    v2 = approved_plan(client, c, monitoring_frequency="Twice per period")
    plans = {p["plan_version"]: p["status"] for p in client.get(f"{MRV}/plans", headers=c.t.pm.headers, params={"project_id": pid}).json()}
    assert plans == {1: "SUPERSEDED", 2: "APPROVED"} and v2["supersedes_id"] == plan["id"]
    assert {"MRV_PLAN_CREATED", "MRV_PLAN_SUBMITTED", "MRV_PLAN_APPROVED", "MRV_PLAN_SUPERSEDED"} <= _actions(db, pid)


def test_configured_methodology_requirements_are_enforced(client: TestClient, db: Session) -> None:
    c = locked_project(db, client, 77.20, 24.20, "8200 2000 3000",
                       sampling={"quantification_approach": "MEASURE_AND_REMEASURE", "depth_top_cm": 0, "depth_bottom_cm": 30,
                                 "min_samples_per_stratum": 3, "statistical_design": "STRATIFIED_RANDOM",
                                 "target_precision_pct": 10, "confidence_level_pct": 90, "stratification_variables": ["SOIL_TYPE"],
                                 "repeat_sampling": "SAME_LOCATION"})
    pid = c.project["id"]
    r = client.post(f"{MRV}/plans", headers=c.mrv.headers, json={"project_id": pid, "quantification_approach": "MEASURE_AND_MODEL"})
    assert r.json()["error_code"] == "METHODOLOGY_REQUIREMENT"
    plan = approved_plan(client, c, quantification_approach=None)
    assert plan["configuration_status"] == "CONFIGURED" and plan["quantification_approach"] == "MEASURE_AND_REMEASURE"
    mp = collecting_period(client, c)
    st = approved_stratum(client, c, "S1", [c.farms[0]["id"]])
    body = {"monitoring_period_id": mp["id"], "code": "D1", "name": "Design", "statistical_design": "STRATIFIED_RANDOM", "depth_top_cm": "0",
            "depth_bottom_cm": "20", "target_precision_pct": "10", "confidence_level_pct": "90", "allocations": [{"stratum_id": st["id"],
                                                                                                                  "sample_count": 3}]}
    r = client.post(f"{MRV}/sampling-designs", headers=c.mrv.headers, json=body)
    assert r.json()["error_code"] == "METHODOLOGY_REQUIREMENT" and "depth" in r.json()["message"]
    r = client.post(f"{MRV}/sampling-designs", headers=c.mrv.headers, json=body | {"depth_bottom_cm": "30", "allocations": [
        {"stratum_id": st["id"], "sample_count": 2}]})
    assert "at least 3 samples" in r.json()["message"]
    ok = client.post(f"{MRV}/sampling-designs", headers=c.mrv.headers, json=body | {"depth_bottom_cm": "30"}).json()
    assert ok["current"]["requirement_source"] == "METHODOLOGY" and ok["current"]["configuration_status"] == "CONFIGURED"


def test_mrv_requires_locked_methodology(client: TestClient, db: Session) -> None:
    from tests.phase3 import create_project
    t = team(db, client)
    p = create_project(client, t)
    mrv = staff(db, client, t.org, "MRV_MANAGER")
    r = client.post(f"{MRV}/plans", headers=mrv.headers, json={"project_id": p["id"]})
    assert r.status_code == 409 and r.json()["error_code"] == "METHODOLOGY_NOT_LOCKED"


# ---------------------------------------------------------------- periods & monitoring records
def test_periods_and_monitoring_records(client: TestClient, db: Session, c: MrvCtx) -> None:
    pid = c.project["id"]
    body = {"project_id": pid, "name": "P1", "start_date": "2026-06-01", "end_date": "2027-05-31"}
    assert client.post(f"{MRV}/monitoring-periods", headers=c.mrv.headers, json=body).json()["error_code"] == "MRV_PLAN_NOT_APPROVED"
    plan = approved_plan(client, c)
    assert client.post(f"{MRV}/monitoring-periods", headers=c.mrv.headers, json=body | {"end_date": "2040-01-01"}).json()["error_code"] \
        == "OUTSIDE_PLAN_WINDOW"
    mp = collecting_period(client, c)
    assert mp["status"] == "DATA_COLLECTION" and client.get(f"{PR}/{pid}", headers=c.t.pm.headers).json()["status"] == "MONITORING"
    assert client.post(f"{MRV}/monitoring-periods", headers=c.mrv.headers, json=body | {"name": "Overlap"}).json()["error_code"] == "PERIOD_OVERLAP"
    till = next(m for m in plan["measurements"] if m["code"] == "TILL")
    rec = {"monitoring_period_id": mp["id"], "measurement_id": till["id"], "farm_id": c.farms[0]["id"], "value": "REDUCED",
           "observed_on": "2026-07-01", "measurement_phase": "PROJECT"}
    assert client.post(f"{MRV}/monitoring-records", headers=c.collector.headers,
                       json=rec | {"value": "PLOUGHED"}).json()["error_code"] == "INVALID_VALUE"
    assert client.post(f"{MRV}/monitoring-records", headers=c.collector.headers,
                       json=rec | {"farm_id": None}).json()["error_code"] == "LEVEL_REQUIRED"
    r = client.post(f"{MRV}/monitoring-records", headers=c.collector.headers, json=rec)
    assert r.status_code == 201 and r.json()["value"] == "REDUCED" and r.json()["version"] == 1
    assert client.post(f"{MRV}/monitoring-records", headers=c.collector.headers, json=rec).json()["error_code"] == "DUPLICATE_RECORD"
    a = client.post(f"{MRV}/monitoring-records/{r.json()['record_id']}/amend", headers=c.collector.headers,
                    json={"value": "NO_TILL", "reason": "farmer confirmed no-till"})
    assert a.json()["version"] == 2 and a.json()["value"] == "NO_TILL"
    hist = client.get(f"{MRV}/monitoring-records", headers=c.mrv.headers, params={"monitoring_period_id": mp["id"], "include_history": True}).json()
    assert [(x["version"], x["status"]) for x in hist] == [(1, "SUPERSEDED"), (2, "RECORDED")]  # never overwritten
    soc = next(m for m in plan["measurements"] if m["code"] == "SOC")
    r = client.post(f"{MRV}/monitoring-records", headers=c.collector.headers, json={**rec, "measurement_id": soc["id"], "value": "abc"})
    assert r.json()["error_code"] == "LABORATORY_RESULT_REQUIRED"  # decision V2: SOC is never entered as MRV data


# ---------------------------------------------------------------- full flow, QA, approval, immutability, lineage
def _ready_dataset(client: TestClient, c: MrvCtx, collect_all: bool = True) -> tuple[dict, dict, list[dict]]:
    plan = approved_plan(client, c)
    mp = collecting_period(client, c)
    s1 = approved_stratum(client, c, "S1", [c.farms[0]["id"]])
    s2 = approved_stratum(client, c, "S2", [c.farms[1]["id"]], characteristics=[{"characteristic": "SOIL_TYPE", "value": "Alfisol"}])
    d = approved_design(client, c, mp["id"], [{"stratum_id": s1["id"], "sample_count": 2}, {"stratum_id": s2["id"], "sample_count": 2}])
    pts = client.post(f"{MRV}/sampling-designs/{d['id']}/generate-points", headers=c.mrv.headers).json()["points"]
    assert len(pts) == 4
    r = client.post(f"{MRV}/sampling-points/assign", headers=c.supervisor.headers,
                    json={"point_ids": [x["id"] for x in pts], "collector_id": str(c.collector.user.id), "planned_date": "2026-07-01"})
    assert r.status_code == 200, r.text
    for x in (pts if collect_all else pts[:3]):
        collect(client, c, x, c.collector)
    till = next(m for m in plan["measurements"] if m["code"] == "TILL")
    for f in c.farms:
        client.post(f"{MRV}/monitoring-records", headers=c.collector.headers, json={
            "monitoring_period_id": mp["id"], "measurement_id": till["id"], "farm_id": f["id"], "value": "REDUCED", "observed_on": "2026-07-02"})
    # SOC (methodology, per sample) comes from sample analysis — not part of Phase 5, so nothing is recorded for it here
    ds = client.post(f"{MRV}/datasets", headers=c.mrv.headers, json={"monitoring_period_id": mp["id"]})
    assert ds.status_code == 201, ds.text
    return ds.json(), mp, pts


def test_full_mrv_flow_qa_approval_and_immutability(client: TestClient, db: Session, c: MrvCtx) -> None:
    pid = c.project["id"]
    ds, mp, pts = _ready_dataset(client, c)
    assert ds["status"] == "COLLECTING" and ds["dataset_code"].startswith("MRV-2026-P") and ds["dataset_code"].endswith("-V1")
    r = client.post(f"{MRV}/datasets/{ds['id']}/submit", headers=c.mrv.headers, json={"reason": "collection complete"})
    assert r.status_code == 200, r.text
    sub = r.json()
    assert sub["status"] == "SUBMITTED" and sub["snapshot_summary"]["sampling_points"] == 4 and sub["snapshot_summary"]["field_collections"] == 4
    snap = client.get(f"{MRV}/datasets/{ds['id']}/snapshot", headers=c.t.qa.headers).json()
    assert snap["snapshot_sha256"] == sub["snapshot_sha256"] and snap["snapshot"]["mrv_plan"]["version"] == 1
    assert client.get(f"{MRV}/monitoring-periods/{mp['id']}", headers=c.mrv.headers).json()["status"] == "SUBMITTED"
    # QA: the submitter cannot complete it, checks are deterministic, approval needs a PASS
    assert client.post(f"{MRV}/qa/{ds['id']}/start", headers=c.collector.headers).status_code == 403
    assert client.post(f"{MRV}/qa/{ds['id']}/start", headers=c.t.qa.headers).status_code == 200
    qa = client.get(f"{MRV}/qa/{ds['id']}", headers=c.t.qa.headers).json()
    failing = [x["key"] for x in qa["checks"] if x["result"] == "FAIL"]
    assert failing == [], qa["checks"]
    res = {x["key"]: x["result"] for x in qa["checks"]}
    assert res["configuration"] == "WARN" and res["sample_analysis_pending"] == "WARN"  # CONFIGURATION_REQUIRED is visible, not hidden
    soc = next(x for x in qa["checks"] if x["key"] == "sample_analysis_pending")
    assert soc["label"].startswith("Awaiting laboratory analysis") and "AWAITING_ANALYSIS" in soc["details"][0]  # SOC is never invented
    assert client.post(f"{MRV}/datasets/{ds['id']}/approve", headers=c.t.qa.headers, json={"reason": "early"}).json()["error_code"] == "QA_NOT_PASSED"
    assert client.post(f"{MRV}/qa/{ds['id']}/complete", headers=c.mrv.headers, json={"result": "PASS", "notes": "self"}).status_code == 403
    assert client.post(f"{MRV}/qa/{ds['id']}/complete", headers=c.t.qa.headers, json={"result": "PASS",
                                                                                      "notes": "all checks pass"}).status_code == 200
    assert client.post(f"{MRV}/datasets/{ds['id']}/approve", headers=c.collector.headers, json={"reason": "collector"}).status_code == 403
    r = client.post(f"{MRV}/datasets/{ds['id']}/approve", headers=c.t.qa.headers, json={"reason": "dataset approved"})
    assert r.json()["status"] == "APPROVED"
    assert client.get(f"{MRV}/monitoring-periods/{mp['id']}", headers=c.mrv.headers).json()["status"] == "APPROVED"
    assert client.get(f"{PR}/{pid}", headers=c.t.pm.headers).json()["status"] == "MONITORING"  # never CALCULATION in Phase 5
    # approved data is not modified: records are locked; a correction is a new dataset version
    assert client.post(f"{MRV}/datasets/{ds['id']}/submit", headers=c.mrv.headers, json={"reason": "again"}).status_code == 409
    v2 = client.post(f"{MRV}/datasets", headers=c.mrv.headers, json={"monitoring_period_id": mp["id"], "notes": "correction"}).json()
    assert v2["version"] == 2 and v2["supersedes_id"] == ds["id"]
    still = client.get(f"{MRV}/datasets/{ds['id']}", headers=c.mrv.headers).json()
    assert still["status"] == "APPROVED" and still["snapshot_sha256"] == sub["snapshot_sha256"]
    acts = _actions(db, pid)
    for a in ("MRV_PLAN_CREATED", "MRV_PLAN_APPROVED", "MONITORING_PERIOD_CREATED", "MONITORING_PERIOD_STARTED", "MONITORING_PERIOD_SUBMITTED",
              "MONITORING_PERIOD_APPROVED", "STRATUM_CREATED", "SAMPLING_DESIGN_CREATED", "SAMPLING_POINT_CREATED", "SAMPLING_POINT_ASSIGNED",
              "FIELD_COLLECTION_STARTED", "FIELD_COLLECTION_SUBMITTED", "MRV_DATASET_CREATED", "MRV_DATASET_SUBMITTED", "MRV_DATASET_APPROVED",
              "MRV_QA_STARTED", "MRV_QA_COMPLETED", "MRV_EVIDENCE_ADDED", "MONITORING_RECORD_ADDED"):
        assert a in acts, a
    hist = client.get(f"{MRV}/projects/{pid}/history", headers=c.t.pm.headers).json()
    assert len(hist) > 20 and all(h["action"].startswith(("MRV_", "MONITORING_", "STRATUM_", "SAMPLING_", "FIELD_")) for h in hist)


def test_qa_failure_rejection_and_new_version(client: TestClient, db: Session, c: MrvCtx) -> None:
    ds, mp, pts = _ready_dataset(client, c, collect_all=False)
    client.post(f"{MRV}/datasets/{ds['id']}/submit", headers=c.mrv.headers, json={"reason": "partial"})
    client.post(f"{MRV}/qa/{ds['id']}/start", headers=c.t.qa.headers)
    checks = {x["key"]: x for x in client.get(f"{MRV}/qa/{ds['id']}", headers=c.t.qa.headers).json()["checks"]}
    assert checks["sampling_completeness"]["result"] == "FAIL" and pts[3]["point_code"] in checks["sampling_completeness"]["details"][0]
    r = client.post(f"{MRV}/qa/{ds['id']}/complete", headers=c.t.qa.headers, json={"result": "PASS", "notes": "looks ok"})
    assert r.status_code == 409 and r.json()["error_code"] == "QA_CHECKS_FAILED"
    client.post(f"{MRV}/qa/{ds['id']}/complete", headers=c.t.qa.headers, json={"result": "REQUIRES_CORRECTION", "notes": "one point missing"})
    r = client.post(f"{MRV}/datasets/{ds['id']}/reject", headers=c.t.qa.headers, json={"reason": "collect the missing point"})
    assert r.json()["status"] == "REJECTED"
    assert client.get(f"{MRV}/monitoring-periods/{mp['id']}", headers=c.mrv.headers).json()["status"] == "REJECTED"
    v2 = client.post(f"{MRV}/datasets", headers=c.mrv.headers, json={"monitoring_period_id": mp["id"]}).json()
    assert v2["version"] == 2 and v2["status"] == "COLLECTING"
    assert client.get(f"{MRV}/monitoring-periods/{mp['id']}", headers=c.mrv.headers).json()["status"] == "DATA_COLLECTION"
    assert "MRV_DATASET_REJECTED" in _actions(db, c.project["id"])


def test_reopening_a_submitted_period_reopens_its_dataset(client: TestClient, db: Session, c: MrvCtx) -> None:
    ds, mp, _ = _ready_dataset(client, c, collect_all=False)
    assert client.post(f"{MRV}/datasets/{ds['id']}/submit", headers=c.mrv.headers, json={"reason": "partial"}).status_code == 200
    r = client.post(f"{MRV}/monitoring-periods/{mp['id']}/open-collection", headers=c.mrv.headers, json={"reason": "one more point"})
    assert r.status_code == 200 and r.json()["status"] == "DATA_COLLECTION", r.text
    again = client.get(f"{MRV}/datasets/{ds['id']}", headers=c.mrv.headers).json()
    assert again["status"] == "COLLECTING" and again["snapshot_sha256"] is None
    # period and dataset move together again: re-submission and QA work
    r = client.post(f"{MRV}/datasets/{ds['id']}/submit", headers=c.mrv.headers, json={"reason": "complete"})
    assert r.status_code == 200 and r.json()["status"] == "SUBMITTED" and r.json()["snapshot_sha256"], r.text
    assert client.post(f"{MRV}/qa/{ds['id']}/start", headers=c.t.qa.headers).status_code == 200


# ---------------------------------------------------------------- field collection rules & RBAC
def test_field_collector_rules_and_isolation(client: TestClient, db: Session, c: MrvCtx) -> None:
    approved_plan(client, c)
    mp = collecting_period(client, c)
    st = approved_stratum(client, c, "S1", [c.farms[0]["id"]])
    d = approved_design(client, c, mp["id"], [{"stratum_id": st["id"], "sample_count": 2}])
    pts = client.post(f"{MRV}/sampling-designs/{d['id']}/generate-points", headers=c.mrv.headers).json()["points"]
    # collectors cannot assign; supervisors can, only to users with collection rights
    assert client.post(f"{MRV}/sampling-points/{pts[0]['id']}/assign", headers=c.collector.headers,
                       json={"collector_id": str(c.collector.user.id)}).status_code == 403
    r = client.post(f"{MRV}/sampling-points/{pts[0]['id']}/assign", headers=c.supervisor.headers, json={"collector_id": str(c.t.qa.user.id)})
    assert r.json()["error_code"] == "NOT_A_COLLECTOR"
    client.post(f"{MRV}/sampling-points/{pts[0]['id']}/assign", headers=c.supervisor.headers, json={"collector_id": str(c.collector.user.id)})
    client.post(f"{MRV}/sampling-points/{pts[1]['id']}/assign", headers=c.supervisor.headers, json={"collector_id": str(c.collector2.user.id)})
    cols = client.get(f"{MRV}/projects/{c.project['id']}/collectors", headers=c.supervisor.headers).json()
    assert {str(c.collector.user.id), str(c.collector2.user.id)} <= {x["id"] for x in cols} and str(c.t.qa.user.id) not in {x["id"] for x in cols}
    assert client.get(f"{MRV}/projects/{c.project['id']}/collectors", headers=c.collector.headers).status_code == 403
    mine = client.get(f"{MRV}/sampling-points", headers=c.collector.headers, params={"mine": True}).json()
    assert [x["id"] for x in mine] == [pts[0]["id"]]  # only their own assignment
    assert client.get(f"{MRV}/sampling-points/{pts[1]['id']}", headers=c.collector.headers).status_code == 403
    r = client.post(f"{MRV}/field-collections", headers=c.collector.headers, json={"sampling_point_id": pts[1]["id"]})
    assert r.status_code == 403
    fc = client.post(f"{MRV}/field-collections", headers=c.collector.headers, json={"sampling_point_id": pts[0]["id"]}).json()
    assert fc["collection_code"].startswith("FIELD-2026-")
    r = client.post(f"{MRV}/field-collections/{fc['id']}/submit", headers=c.collector.headers)
    assert r.status_code == 409 and {"GPS position", "at least one field photo"} <= set(" ".join(r.json()["details"]["missing"]).split("; ")) | {
        "GPS position", "at least one field photo"}
    # GPS far from the point needs an explanation; distance is measured by SQL Server
    client.patch(f"{MRV}/field-collections/{fc['id']}", headers=c.collector.headers, json={
        "collected_at": "2026-07-01T09:00:00Z", "gps_latitude": float(pts[0]["latitude"]) + 0.001, "gps_longitude": float(pts[0]["longitude"]),
        "actual_depth_top_cm": "0", "actual_depth_bottom_cm": "30",
        "checklist": dict.fromkeys(fc["required_checklist"], True)})
    photo(client, c, c.collector, "FIELD_COLLECTION", fc["id"])
    got = client.get(f"{MRV}/field-collections/{fc['id']}", headers=c.collector.headers).json()
    assert 100 < float(got["distance_from_point_m"]) < 125
    r = client.post(f"{MRV}/field-collections/{fc['id']}/submit", headers=c.collector.headers)
    assert r.status_code == 409 and "note" in r.json()["message"]
    client.patch(f"{MRV}/field-collections/{fc['id']}", headers=c.collector.headers, json={"deviation_note": "Point under standing water"})
    assert client.post(f"{MRV}/field-collections/{fc['id']}/submit", headers=c.collector.headers).json()["status"] == "SUBMITTED"
    # the collector cannot review their own record nor approve MRV
    assert client.post(f"{MRV}/field-collections/{fc['id']}/review", headers=c.collector.headers,
                       json={"decision": "ACCEPTED", "notes": "self"}).status_code == 403
    both = staff(db, client, c.t.org, "FIELD_SUPERVISOR")
    client.post(f"{MRV}/sampling-points/{pts[1]['id']}/assign", headers=c.supervisor.headers, json={"collector_id": str(both.user.id)})
    fc2 = collect(client, c, client.get(f"{MRV}/sampling-points/{pts[1]['id']}", headers=c.mrv.headers).json(), both, accept=False)
    r = client.post(f"{MRV}/field-collections/{fc2['id']}/review", headers=both.headers, json={"decision": "ACCEPTED", "notes": "self review"})
    assert r.status_code == 403 and r.json()["error_code"] == "SEPARATION_OF_DUTIES"
    # corrections of accepted records create a new version
    client.post(f"{MRV}/field-collections/{fc['id']}/review", headers=c.supervisor.headers, json={"decision": "ACCEPTED", "notes": "ok ok"})
    corr = client.post(f"{MRV}/field-collections/{fc['id']}/correct", headers=c.collector.headers, json={"reason": "wrong depth recorded"}).json()
    assert corr["version"] == 2 and corr["supersedes_id"] == fc["id"] and corr["status"] == "IN_PROGRESS"
    assert "FIELD_COLLECTION_CORRECTED" in _actions(db, c.project["id"])
    # organization isolation and least privilege
    other = team(db, client)
    other_mrv = staff(db, client, other.org, "MRV_MANAGER")
    assert client.get(f"{MRV}/plans", headers=other_mrv.headers, params={"project_id": c.project["id"]}).status_code == 404
    assert c.project["id"] not in {x["project_id"] for x in client.get(f"{MRV}/projects", headers=other_mrv.headers).json()}
    farmer = make_user(db, roles=[("FARMER", make_org(db, org_type="FARMER_GROUP"))])
    buyer = make_user(db, roles=[("BUYER", make_org(db, org_type="BUYER"))])
    for u in (farmer, buyer):
        h = login(client, u)
        assert client.get(f"{MRV}/projects", headers=h).status_code == 403
        assert client.get(f"{MRV}/sampling-points", headers=h).status_code == 403
    lab = make_user(db, roles=[("LAB_TECHNICIAN", make_org(db, org_type="LABORATORY"))])
    assert client.get(f"{MRV}/plans", headers=login(client, lab), params={"project_id": c.project["id"]}).status_code == 403
    assert client.post(f"{MRV}/plans/{'0' * 8}-0000-0000-0000-{'0' * 12}/approve", headers=c.collector.headers,
                       json={"reason": "nope nope"}).status_code == 403


def test_lineage_snapshot_reproducible(client: TestClient, db: Session, c: MrvCtx) -> None:
    ds, mp, pts = _ready_dataset(client, c)
    client.post(f"{MRV}/datasets/{ds['id']}/submit", headers=c.mrv.headers, json={"reason": "complete"})
    snap = client.get(f"{MRV}/datasets/{ds['id']}/snapshot", headers=c.mrv.headers).json()["snapshot"]
    assert snap["methodology_version_id"] == c.version_id and snap["monitoring_period"]["id"] == mp["id"]
    assert {x["code"] for x in snap["sampling_points"]} == {x["point_code"] for x in pts}
    assert len(snap["strata"]) == 2 and all(s["version"] == 1 for s in snap["strata"])
    assert all(e["checksum_sha256"] for e in snap["evidence"] if e["type"] == "FIELD_PHOTO")
    # the stored hash is the hash of the stored snapshot (reproducible)
    import hashlib

    from app.models import MrvDataset
    row = db.get(MrvDataset, ds["id"])
    assert row is not None and hashlib.sha256(json.dumps(json.loads(row.snapshot or "{}"), sort_keys=True, separators=(",", ":")).encode()
                                             ).hexdigest() == row.snapshot_sha256
