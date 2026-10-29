"""Fixes from the 13-14 Oct 2026 calculation-pipeline review: field records frozen outside data collection and re-checked at dataset
approval (A2), laboratory results following a corrected field collection (A3), immutable laboratory / calculation documents and the
report PDF integrity check (A4), period overlap including CLOSED periods (A5), unexpected module exceptions as CALCULATION_ERROR (A6),
control sites outside other open projects (A7) and revoked production readiness (A8). Successful calculation paths use the TEST-only
Phase 7 fixture module, handed to the service layer (never registered)."""
import uuid
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calculation import framework as fw
from app.core.config import get_settings
from app.core.errors import Conflict
from app.models import CalculationRun, FieldCollectionRecord, LabResult, MethodologyVersion, MonitoringPeriod, MrvEvidence, Project
from app.schemas.calculation import RunIn
from app.services import calculation_inputs as ci
from app.services import calculation_readiness as cr
from app.services import calculation_report as crep
from app.services import calculation_service as cs
from app.services import document_service
from tests.calc_fixture import CALC, CalcCtx, FixtureModule, as_principal, calc_scenario, fixture_module, resolver_for
from tests.phase2 import square
from tests.phase3 import PR, add_farm, create_project, verified_farm
from tests.phase5 import MRV, SIZE, approved_plan, approved_stratum, locked_project, photo
from tests.phase6 import LABV, PDF, now_iso

DOCS = "/api/v1/evidence/documents"


def _boom(self: Any, ctx: Any) -> list:
    raise KeyError("T_AREA_MISSING")          # a module bug, not a deterministic blocker


def _new_run(db: Session, k: CalcCtx, resolver: Any) -> CalculationRun:
    a, actx = as_principal(db, k.analyst)
    run = cs.create_run(db, actx, a, RunIn(project_id=uuid.UUID(k.project_id), monitoring_period_id=uuid.UUID(k.period_id)))
    return cs.freeze(db, actx, a, run.id, resolver=resolver)


def _status_of(db: Session, run_id: uuid.UUID) -> str:
    db.expire_all()
    run = db.get(CalculationRun, run_id)
    assert run is not None
    return run.status


# ---------------------------------------------------------------- A6 (pure)
def test_unexpected_module_exception_is_a_calculation_error() -> None:
    rows = [{"seq": 1, "variable": "TEST_LAB", "value": "1.5", "value_kind": "NUMBER", "unit": "t C/ha", "level": "SAMPLING_POINT"},
            {"seq": 2, "variable": "TEST_AREA", "value": "2", "value_kind": "NUMBER", "unit": "ha", "level": "STRATUM"},
            {"seq": 3, "variable": "TEST_K", "value": "2", "value_kind": "NUMBER", "unit": "TEST", "level": "PROJECT"}]
    module = type("Boom", (FixtureModule,), {"methodology_code": "TEST", "version_label": "1", "calculate_removals": _boom})()
    with pytest.raises(fw.CalculationBlocked) as e:
        fw.execute(module, {"inputs": rows})
    assert e.value.code == "CALCULATION_ERROR" and "KeyError" in e.value.message and "T_AREA_MISSING" not in e.value.message  # internals logged, not shown
    assert e.value.details == {"reason": "MODULE_EXCEPTION", "exception": "KeyError"}
    # a malformed frozen value is refused the same way (never an unhandled server error)
    bad = [dict(r, value="not-a-number") if r["seq"] == 1 else r for r in rows]
    with pytest.raises(fw.CalculationBlocked) as e:
        fw.execute(type("Ok", (FixtureModule,), {})(), {"inputs": bad})
    assert e.value.code == "CALCULATION_ERROR"
    # the same module without the bug runs normally
    assert fw.execute(type("Ok", (FixtureModule,), {})(), {"inputs": rows}).net_value


# ---------------------------------------------------------------- A6 / A8 / A4 on a real run
def test_revoked_readiness_module_errors_and_immutable_calculation_documents(client: TestClient, db: Session,
                                                                             monkeypatch: pytest.MonkeyPatch) -> None:
    k = calc_scenario(db, client, 79.20, 24.20, "9920 2000 3000")
    vid = k.x.c.version_id
    a, actx = as_principal(db, k.analyst)
    q, qctx = as_principal(db, k.qa)
    v = db.get(MethodologyVersion, uuid.UUID(vid))
    assert v is not None
    prod = resolver_for(fixture_module(db, vid, readiness=fw.PRODUCTION_READY))

    def readiness(value: str) -> None:
        v.calculation_readiness = value
        db.flush()

    def production(on: bool) -> None:
        monkeypatch.setattr(get_settings(), "APP_ENV", "production" if on else "test")

    # A8: frozen while the version was PRODUCTION_READY, revoked afterwards -> execution is blocked in production
    readiness("PRODUCTION_READY")
    run = _new_run(db, k, prod)
    assert run.module_readiness == "PRODUCTION_READY"
    readiness("NOT_PRODUCTION_READY")
    production(True)
    with pytest.raises(Conflict) as e:
        cs.execute(db, actx, a, run.id, resolver=prod)
    production(False)
    assert e.value.error_code == "NOT_PRODUCTION_READY" and e.value.details["reason"] == "READINESS_REVOKED"
    assert _status_of(db, run.id) == "BLOCKED"
    # outside production the revocation only warns in calculation QA; in production QA fails, approval and readiness are refused
    readiness("PRODUCTION_READY")
    run = _new_run(db, k, prod)
    run = cs.submit(db, actx, a, cs.execute(db, actx, a, run.id, resolver=prod).id)
    readiness("NOT_PRODUCTION_READY")
    check = {c["key"]: c for c in cs.qa_checks(db, run, q.user_id, prod)}["module_readiness"]
    assert check["result"] == "WARN" and "revoked" in check["details"][0]
    production(True)
    check = {c["key"]: c for c in cs.qa_checks(db, run, q.user_id, prod)}["module_readiness"]
    production(False)
    assert check["result"] == "FAIL"
    cs.start_qa(db, qctx, q, run.id)
    cs.complete_qa(db, qctx, q, run.id, "PASS", "TEST checks pass", resolver=prod)
    production(True)
    with pytest.raises(Conflict) as e:
        cs.approve(db, *as_principal(db, k.signer)[::-1], run.id, "TEST approved")
    production(False)
    assert e.value.error_code == "NOT_PRODUCTION_READY" and e.value.details["reason"] == "READINESS_REVOKED"
    s_, sctx = as_principal(db, k.signer)                                   # approver ≠ QA reviewer
    run = cs.approve(db, sctx, s_, run.id, "TEST approved")
    production(True)
    blockers, _, _ = cr.evaluate(db, run.monitoring_period_id, run)
    production(False)
    assert ("NOT_PRODUCTION_READY", "READINESS_REVOKED") in [(b.code, b.reason) for b in blockers]
    assert "NOT_PRODUCTION_READY" not in [b.code for b in cr.evaluate(db, run.monitoring_period_id, run)[0]]

    # A6: a module exception in the calculation-QA re-run fails "reproducible" instead of raising
    boom_prod = resolver_for(fixture_module(db, vid, readiness=fw.PRODUCTION_READY, calculate_removals=_boom))
    check = {c["key"]: c for c in cs.qa_checks(db, run, q.user_id, boom_prod)}["reproducible"]
    assert check["result"] == "FAIL" and "CALCULATION_ERROR" in check["details"][0]
    # ... and in execution it blocks the run with CALCULATION_ERROR (no HTTP 500)
    run2 = _new_run(db, k, k.resolver)
    with pytest.raises(Conflict) as e:
        cs.execute(db, actx, a, run2.id, resolver=resolver_for(fixture_module(db, vid, calculate_removals=_boom)))
    assert e.value.error_code == "CALCULATION_ERROR" and "KeyError" in str(e.value.message)
    assert e.value.details["blockers"][0]["details"]["exception"] == "KeyError" and _status_of(db, run2.id) == "BLOCKED"

    # A4: calculation documents (report, finding evidence) are never replaced through the generic documents API
    assert client.post(f"{CALC}/runs/{run.id}/reports", headers=k.analyst.headers).status_code == 201
    rep = crep.current_report(db, run.id)
    assert rep is not None
    url = f"{DOCS}/{rep.document_id}/versions"
    r = client.post(url, headers=k.analyst.headers, files={"file": ("x.pdf", PDF, "application/pdf")})
    assert r.status_code == 403 and r.json()["error_code"] == "DOCUMENT_IMMUTABLE"
    ev = client.post(f"{CALC}/runs/{run.id}/evidence", headers=k.qa.headers, files={"file": ("e.pdf", PDF, "application/pdf")}).json()
    r = client.post(f"{DOCS}/{ev['document_id']}/versions", headers=k.qa.headers, files={"file": ("e.pdf", PDF, "application/pdf")})
    assert r.status_code == 403 and r.json()["error_code"] == "DOCUMENT_IMMUTABLE"
    pdf_url = f"{CALC}/reports/{rep.id}/pdf"
    assert client.get(pdf_url, headers=k.qa.headers).status_code == 200
    # a PDF swapped behind the report (here by bypassing the resolver) is refused on download
    with monkeypatch.context() as m:
        m.setitem(document_service._RESOLVERS, "calculation_run", lambda *_: None)
        assert client.post(url, headers=k.analyst.headers, files={"file": ("x.pdf", PDF + b"%swapped", "application/pdf")}).status_code == 200
    r = client.get(pdf_url, headers=k.qa.headers)
    assert r.status_code == 409 and r.json()["error_code"] == "REPORT_INTEGRITY_FAILED"

    # A4: a laboratory report is replaceable only while its result is DRAFT
    tech = k.x.tech.headers
    approved = db.get(LabResult, uuid.UUID(k.results[0]["id"]))
    assert approved is not None and approved.report_document_id is not None
    r = client.post(f"{DOCS}/{approved.report_document_id}/versions", headers=tech, files={"file": ("r.pdf", PDF, "application/pdf")})
    assert r.status_code == 403 and r.json()["error_code"] == "DOCUMENT_IMMUTABLE"
    corr = client.post(f"{LABV}/results/{k.results[1]['id']}/correct", headers=tech, json={
        "reason": "transcription error", "result_type": "NUMERIC", "value_number": "1.9", "unit": "t C/ha", "analysed_at": now_iso(1)}).json()
    assert client.post(f"{LABV}/results/{corr['id']}/report", headers=tech, files={"file": ("r.pdf", PDF, "application/pdf")}).status_code == 200
    db.expire_all()
    draft = db.get(LabResult, uuid.UUID(corr["id"]))
    assert draft is not None and draft.status == "DRAFT" and draft.report_document_id is not None
    doc_url = f"{DOCS}/{draft.report_document_id}/versions"
    assert client.post(doc_url, headers=tech, files={"file": ("r.pdf", PDF + b"%v2", "application/pdf")}).status_code == 200
    assert client.post(f"{LABV}/results/{corr['id']}/submit", headers=tech).status_code == 200
    r = client.post(doc_url, headers=tech, files={"file": ("r.pdf", PDF + b"%v3", "application/pdf")})
    assert r.status_code == 403 and r.json()["error_code"] == "DOCUMENT_IMMUTABLE"


# ---------------------------------------------------------------- A2 / A3
def test_field_records_frozen_outside_collection_and_lab_results_follow_corrections(client: TestClient, db: Session) -> None:
    k = calc_scenario(db, client, 79.30, 24.30, "9930 2000 3000")
    x, c = k.x, k.x.c
    fc0, fc1 = x.fcs
    a, actx = as_principal(db, k.analyst)

    def correct(fc: dict) -> Any:
        return client.post(f"{MRV}/field-collections/{fc['id']}/correct", headers=c.collector.headers, json={"reason": "depth typo in the record"})

    # A2: the dataset is approved (period APPROVED): field records cannot be corrected in place
    r = correct(fc0)
    assert r.status_code == 409 and r.json()["error_code"] == "PERIOD_NOT_COLLECTING"
    run1 = _new_run(db, k, k.resolver)                      # frozen on dataset v1
    # a correction is a new dataset version, which re-opens the period
    ds2 = client.post(f"{MRV}/datasets", headers=c.mrv.headers, json={"monitoring_period_id": x.period["id"]}).json()
    assert ds2["status"] == "COLLECTING"
    corr = correct(fc0).json()
    assert corr["status"] == "IN_PROGRESS" and corr["supersedes_id"] == fc0["id"]
    assert client.patch(f"{MRV}/field-collections/{corr['id']}", headers=c.collector.headers,
                        json={"actual_depth_bottom_cm": "25"}).status_code == 200
    photo(client, c, c.collector, "FIELD_COLLECTION", corr["id"])
    assert client.post(f"{MRV}/field-collections/{corr['id']}/submit", headers=c.collector.headers).status_code == 200
    # a returned correction leaves the point COLLECTED: the accepted version it corrects stays in force
    r = client.post(f"{MRV}/field-collections/{corr['id']}/review", headers=c.supervisor.headers, json={"decision": "RETURNED", "notes": "check it"})
    assert r.status_code == 200 and r.json()["status"] == "RETURNED"
    assert client.get(f"{MRV}/sampling-points/{x.points[0]['id']}", headers=c.mrv.headers).json()["status"] == "COLLECTED"
    assert client.post(f"{MRV}/field-collections/{corr['id']}/submit", headers=c.collector.headers).status_code == 200
    r = client.post(f"{MRV}/field-collections/{corr['id']}/review", headers=c.supervisor.headers, json={"decision": "ACCEPTED", "notes": "ok ok"})
    assert r.status_code == 200 and r.json()["status"] == "ACCEPTED"
    # the run frozen on dataset v1 now reads a replaced field record (the dataset itself is still APPROVED)
    with pytest.raises(Conflict) as e:
        cs.execute(db, actx, a, run1.id, resolver=k.resolver)
    problems = e.value.details["blockers"][0]["details"]["problems"]
    assert e.value.error_code == "INPUTS_OUT_OF_DATE" and any(fc0["collection_code"] in p and "accepted version" in p for p in problems)
    # submitted: field records are frozen again while the dataset is reviewed
    assert client.post(f"{MRV}/datasets/{ds2['id']}/submit", headers=c.mrv.headers, json={"reason": "corrected depth"}).status_code == 200
    r = correct(fc1)
    assert r.status_code == 409 and r.json()["error_code"] == "PERIOD_NOT_COLLECTING"
    assert client.post(f"{MRV}/qa/{ds2['id']}/start", headers=c.t.qa.headers).status_code == 200
    r = client.post(f"{MRV}/qa/{ds2['id']}/complete", headers=c.t.qa.headers, json={"result": "PASS", "notes": "all checks pass"})
    assert r.status_code == 200, r.text
    approve = f"{MRV}/datasets/{ds2['id']}/approve"
    # approval re-checks: a snapshot field record that is no longer accepted, then a QA check that fails now
    row = db.get(FieldCollectionRecord, uuid.UUID(fc1["id"]))
    assert row is not None
    row.status = "RETURNED"
    db.flush()
    r = client.post(approve, headers=k.signer.headers, json={"reason": "dataset approved"})
    assert r.status_code == 409 and r.json()["error_code"] == "SNAPSHOT_OUT_OF_DATE"
    row.status = "ACCEPTED"
    ev = db.scalars(select(MrvEvidence).where(MrvEvidence.entity_id == uuid.UUID(corr["id"]))).first()
    assert ev is not None
    kept, ev.status = ev.status, "REJECTED"
    db.flush()
    r = client.post(approve, headers=k.signer.headers, json={"reason": "dataset approved"})
    assert r.status_code == 409 and r.json()["error_code"] == "QA_CHECKS_FAILED" and "evidence" in r.json()["details"]["failed"]
    ev.status = kept
    db.flush()
    assert client.post(approve, headers=k.signer.headers, json={"reason": "dataset approved"}).status_code == 200

    # A3: the approved results of the superseded version follow the accepted correction (no MISSING_APPROVED_LAB_RESULT)
    p, mp = db.get(Project, uuid.UUID(k.project_id)), db.get(MonitoringPeriod, uuid.UUID(k.period_id))
    assert p is not None and mp is not None
    evaluation = ci.evaluate(db, p, mp, None, k.resolver)
    assert evaluation.ready, [b.as_dict() for b in evaluation.blockers]
    lab = [r for r in evaluation.inputs if r["source_type"] == "LAB_RESULT"]
    moved = [r for r in lab if r["context"].get("original_field_collection_id") == fc0["id"]]
    assert len(lab) == 2 and len(moved) == 1 and moved[0]["field_collection_id"] == corr["id"]
    assert Decimal(moved[0]["context"]["depth_bottom_cm"]) == 25       # the whole-core sample follows the corrected depth
    assert all("original_field_collection_id" not in r["context"] for r in lab if r is not moved[0])
    run2 = _new_run(db, k, k.resolver)
    assert cs.execute(db, actx, a, run2.id, resolver=k.resolver).status == "CALCULATED"
    # a CLOSED period: field records stay frozen
    assert client.post(f"{MRV}/monitoring-periods/{x.period['id']}/close", headers=c.mrv.headers, json={"reason": "period closed"}).status_code == 200
    r = correct({"id": corr["id"]})
    assert r.status_code == 409 and r.json()["error_code"] == "PERIOD_NOT_COLLECTING" and r.json()["details"]["period_status"] == "CLOSED"


# ---------------------------------------------------------------- A5
def test_period_overlap_includes_closed_periods(client: TestClient, db: Session) -> None:
    c = locked_project(db, client, 79.40, 24.40, "9940 2000 3000", n_farms=1)
    approved_plan(client, c)
    url = f"{MRV}/monitoring-periods"
    body = {"project_id": c.project["id"], "name": "Monitoring 1", "purpose": "MONITORING", "start_date": "2026-06-01", "end_date": "2027-05-31"}
    r = client.post(url, headers=c.mrv.headers, json=body)
    assert r.status_code == 201, r.text
    first = db.get(MonitoringPeriod, uuid.UUID(r.json()["id"]))
    assert first is not None
    first.status = "CLOSED"
    db.flush()
    r = client.post(url, headers=c.mrv.headers, json={**body, "name": "Monitoring 1b", "start_date": "2026-12-01", "end_date": "2027-11-30"})
    assert r.status_code == 409 and r.json()["error_code"] == "PERIOD_OVERLAP"
    assert r.json()["details"]["periods"][0]["status"] == "CLOSED"
    # adjacent dates and another purpose do not clash
    assert client.post(url, headers=c.mrv.headers, json={**body, "name": "Monitoring 2", "start_date": "2027-06-01",
                                                         "end_date": "2028-05-31"}).status_code == 201
    assert client.post(url, headers=c.mrv.headers, json={**body, "name": "Baseline", "purpose": "BASELINE"}).status_code == 201


# ---------------------------------------------------------------- A7
def test_control_site_farm_cannot_take_part_in_another_open_project(client: TestClient, db: Session) -> None:
    c = locked_project(db, client, 79.50, 24.50, "9950 2000 3000", n_farms=1)
    approved_plan(client, c)
    s1 = approved_stratum(client, c, "S1", [c.farms[0]["id"]])
    farm = verified_farm(client, c.t, c.farms[0]["farmer_id"], square(79.52, 24.50, SIZE))
    other = create_project(client, c.t, name="Another pilot")
    assert client.post(f"{PR}/{other['id']}/start-data-collection", headers=c.t.pm.headers, json={"reason": "collect"}).status_code == 200
    assert add_farm(client, c.t, other["id"], farm["id"]).status_code == 201

    def candidates() -> set[str]:
        return {x["farm_id"] for x in client.get(f"{MRV}/projects/{c.project['id']}/control-site-candidates", headers=c.mrv.headers).json()}

    body = {"code": "C1", "name": "Control C1", "farm_ids": [farm["id"]], "role": "CONTROL", "linked_stratum_ids": [s1["id"]],
            "characteristics": [{"characteristic": "SOIL_TYPE", "value": "Vertisol"}]}
    assert farm["id"] not in candidates()
    r = client.post(f"{MRV}/projects/{c.project['id']}/strata", headers=c.mrv.headers, json=body)
    assert r.status_code == 422 and r.json()["error_code"] == "CONTROL_FARM_IN_OTHER_PROJECT"
    assert r.json()["details"]["farms"] == {farm["id"]: [other["project_code"]]}
    # once that project is closed, the farm may serve as a control site
    assert client.post(f"{PR}/{other['id']}/close", headers=c.t.pm.headers, json={"reason": "pilot cancelled"}).status_code == 200
    assert farm["id"] in candidates()
    assert client.post(f"{MRV}/projects/{c.project['id']}/strata", headers=c.mrv.headers, json=body).status_code == 201
