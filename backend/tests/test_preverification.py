"""Phase 8A — internal pre-verification (not VVB / ACVA): the deterministic PDF writer, findings (lifecycle, categories, targets,
separation of duties, blocking, recalculation), calculation reports (APPROVED only, deterministic hashes, tamper detection,
immutability, supersession, size guard), internal verification readiness per monitoring period (blockers, approval / rejection /
withdrawal, separation of duties, manifest, automatic invalidation), RBAC, organization isolation, the DEMO Niphad path (still blocked:
CONFIGURATION_REQUIRED — NO_CALCULATION_MODULE), audit and the database triggers. Successful paths use the TEST-only Phase 7 fixture,
which is never registered in the application or reachable through the API."""
import contextlib
import hashlib
import re
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.calculation import framework as fw
from app.core.config import get_settings
from app.integrations.storage import get_storage
from app.models import (
    AuditLog,
    CalculationFinding,
    CalculationReadinessReview,
    CalculationReport,
    CalculationRun,
    Document,
    DocumentVersion,
    MethodologyCalculationRule,
    Organization,
    Project,
)
from app.reports import pdf
from app.schemas.calculation import CALCULATED_LABEL, RunIn
from app.services import calculation_report as crep
from app.services import calculation_service as cs
from tests.calc_fixture import CALC, CalcCtx, as_principal, calc_scenario
from tests.conftest import Actor, login, make_org, make_user
from tests.phase2 import staff
from tests.phase6 import LAB


def _run(db: Session, k: CalcCtx, actor: Actor | None = None, approve: bool = True) -> CalculationRun:
    """Create → freeze → execute → submit (analyst); QA → PASS → approve (QA officer), with the TEST-only resolver."""
    a, actx = as_principal(db, actor or k.analyst)
    q, qctx = as_principal(db, k.qa)
    run = cs.create_run(db, actx, a, RunIn(project_id=uuid.UUID(k.project_id), monitoring_period_id=uuid.UUID(k.period_id)))
    run = cs.freeze(db, actx, a, run.id, resolver=k.resolver)
    run = cs.execute(db, actx, a, run.id, resolver=k.resolver)
    if not approve:
        return run
    run = cs.submit(db, actx, a, run.id)
    cs.start_qa(db, qctx, q, run.id)
    cs.complete_qa(db, qctx, q, run.id, "PASS", "TEST checks pass", resolver=k.resolver)
    return cs.approve(db, qctx, q, run.id, "TEST approved")


def _recalc(db: Session, k: CalcCtx, prev: CalculationRun) -> CalculationRun:
    a, actx = as_principal(db, k.analyst)
    q, qctx = as_principal(db, k.qa)
    run = cs.recalculate(db, actx, a, prev.id, "TEST re-run")
    run = cs.freeze(db, actx, a, run.id, resolver=k.resolver)
    run = cs.execute(db, actx, a, run.id, resolver=k.resolver)
    run = cs.submit(db, actx, a, run.id)
    cs.start_qa(db, qctx, q, run.id)
    cs.complete_qa(db, qctx, q, run.id, "PASS", "TEST checks pass", resolver=k.resolver)
    return cs.approve(db, qctx, q, run.id, "TEST re-run approved")


def _finding(client: TestClient, actor: Actor, run_id: Any, **kw: Any) -> Any:
    body = {"category": "CALCULATION_ISSUE", "blocking": True, "title": "TEST finding", "description": "TEST: please explain this value", **kw}
    return client.post(f"{CALC}/runs/{run_id}/findings", headers=actor.headers, json=body)


def _view(client: TestClient, actor: Actor, k: CalcCtx) -> Any:
    r = client.get(f"{CALC}/projects/{k.project_id}/verification-readiness", headers=actor.headers, params={"monitoring_period_id": k.period_id})
    assert r.status_code == 200, r.text
    return r.json()


def _codes(view: Any) -> list[str]:
    return [b["code"] for b in view["blockers"]]


def _actions(db: Session, entity_type: str) -> set[str]:
    return {a for (a,) in db.execute(select(AuditLog.action).where(AuditLog.entity_type == entity_type))}


# ---------------------------------------------------------------- PDF writer (pure)
def test_pdf_writer_is_deterministic_text_only_and_structurally_valid() -> None:
    lines = [CALCULATED_LABEL, "x → y ≠ z (paren) \\ back", "w " * 400] + [f"line {i}" for i in range(150)]
    a, b = pdf.render(lines), pdf.render(list(lines))
    assert a == b and a.startswith(b"%PDF-1.4") and a.rstrip().endswith(b"%%EOF")
    for forbidden in (b"/CreationDate", b"/ModDate", b"/ID", b"/Info", b"/Image", b"/FontFile"):
        assert forbidden not in a
    assert a.count(b"/BaseFont /Helvetica") == 1 and b"Page 3 of 3" in a and b"->" in a and b"!=" in a and b"\\(paren\\)" in a
    assert "—".encode("cp1252") in a                                   # the em dash of the label (WinAnsi)
    start = int(re.search(rb"startxref\n(\d+)", a).group(1))           # type: ignore[union-attr]
    entries = re.findall(rb"(\d{10}) 00000 n ", a[start:])
    for n, off in enumerate(entries, start=1):                          # every xref offset points at its object
        assert a[int(off):].startswith(f"{n} 0 obj".encode())
    assert pdf.render([*lines, "extra"]) != a


# ---------------------------------------------------------------- findings
def test_findings_lifecycle_categories_targets_sod_and_recalculation(client: TestClient, db: Session) -> None:
    k = calc_scenario(db, client, 78.10, 23.10, "9100 2000 3000")
    run = _run(db, k)
    inputs, outputs = cs.inputs(db, run.id), cs.outputs(db, run.id)
    lab = next(i for i in inputs if i.source_type == "LAB_RESULT")
    rule = db.scalars(select(MethodologyCalculationRule).where(MethodologyCalculationRule.methodology_version_id == run.methodology_version_id,
                                                               MethodologyCalculationRule.rule_code == "TC8")).one()
    lab_doc = client.get(f"{LAB}/results", headers=k.x.c.mrv.headers, params={"project_id": k.project_id}).json()[0]["report"]["document_id"]
    # categories: exactly the six of the specification; no severity scale
    assert _finding(client, k.qa, run.id, category="CRITICAL").status_code == 422
    assert _finding(client, k.qa, run.id, severity="HIGH").status_code == 422
    # who may raise: QA (calculation.review), not the analyst
    assert _finding(client, k.analyst, run.id).status_code == 403
    # targets must belong to this run
    for bad in ({"target_input_seq": 999}, {"target_output_seq": 999}, {"target_calculation_rule_id": str(uuid.uuid4())},
                {"target_source_type": "LAB_RESULT", "target_source_id": str(uuid.uuid4())}, {"target_source_type": "LAB_RESULT"},
                {"evidence_document_id": str(uuid.uuid4())}):
        r = _finding(client, k.qa, run.id, **bad)
        assert r.status_code == 409 and r.json()["error_code"] == "INVALID_FINDING_TARGET", (bad, r.text)
    f = _finding(client, k.qa, run.id, target_input_seq=lab.seq, target_output_seq=outputs[-1].seq, target_calculation_rule_id=str(rule.id),
                 target_source_type="LAB_RESULT", target_source_id=str(lab.source_id), evidence_document_id=lab_doc).json()
    assert f["status"] == "OPEN" and f["finding_code"].startswith("CFND-") and f["category_label"] == "Calculation Issue"
    assert f["target_rule_code"] == "TC8" and f["can_withdraw"] is True
    fid = f["id"]
    # respond: the analyst (calculation.manage), with evidence attached to this run
    assert client.post(f"{CALC}/findings/{fid}/respond", headers=k.qa.headers, json={"response": "QA cannot respond"}).status_code == 403
    ev = client.post(f"{CALC}/runs/{run.id}/evidence", headers=k.analyst.headers,
                     files={"file": ("e.pdf", b"%PDF-1.4\n%TEST evidence\n%%EOF\n", "application/pdf")}, data={"title": "TEST evidence"})
    assert ev.status_code == 201, ev.text
    r = client.post(f"{CALC}/findings/{fid}/respond", headers=k.analyst.headers, json={"response": "TEST value checked", "document_id":
                                                                                     ev.json()["document_id"]})
    assert r.json()["status"] == "RESPONDED"
    assert client.post(f"{CALC}/findings/{fid}/respond", headers=k.analyst.headers, json={"response": "again"}).json()["error_code"] == "FINDING_NOT_OPEN"
    # return → OPEN, respond again, resolve (QA), reopen (reason), respond, resolve
    assert client.post(f"{CALC}/findings/{fid}/return", headers=k.qa.headers, json={"reason": "not enough"}).json()["status"] == "OPEN"
    client.post(f"{CALC}/findings/{fid}/respond", headers=k.analyst.headers, json={"response": "TEST more detail"})
    r = client.post(f"{CALC}/findings/{fid}/resolve", headers=k.qa.headers, json={"note": "explained"})
    assert r.json()["status"] == "RESOLVED"
    assert client.post(f"{CALC}/findings/{fid}/resolve", headers=k.qa.headers, json={"note": "x y z"}).json()["error_code"] == "FINDING_NOT_RESPONDED"
    assert client.post(f"{CALC}/findings/{fid}/reopen", headers=k.qa.headers, json={"reason": "new doubt"}).json()["status"] == "OPEN"
    # separation of duties: the responder never resolves (even holding QA)
    dual = staff(db, client, k.x.c.t.org, "CALCULATION_ANALYST", "QA_OFFICER")
    client.post(f"{CALC}/findings/{fid}/respond", headers=dual.headers, json={"response": "TEST responded by dual"})
    r = client.post(f"{CALC}/findings/{fid}/resolve", headers=dual.headers, json={"note": "self resolve"})
    assert r.status_code == 403 and r.json()["error_code"] == "SEPARATION_OF_DUTIES"
    # withdraw: only the raiser, with a reason
    other_qa = staff(db, client, k.x.c.t.org, "QA_OFFICER")
    assert client.post(f"{CALC}/findings/{fid}/withdraw", headers=other_qa.headers, json={"reason": "not mine"}).json()["error_code"] == "NOT_RAISER"
    assert client.post(f"{CALC}/findings/{fid}/withdraw", headers=k.qa.headers, json={}).status_code == 422
    w = client.post(f"{CALC}/findings/{fid}/withdraw", headers=k.qa.headers, json={"reason": "raised in error"}).json()
    assert w["status"] == "WITHDRAWN" and w["withdraw_reason"] == "raised in error"
    assert client.post(f"{CALC}/findings/{fid}/reopen", headers=k.qa.headers, json={"reason": "again"}).json()["error_code"] == "FINDING_NOT_RESOLVED"
    hist = client.get(f"{CALC}/findings/{fid}/history", headers=k.x.c.mrv.headers).json()["events"]
    assert [e["action"] for e in hist] == ["RAISED", "RESPONDED", "RESPONSE_RETURNED", "RESPONDED", "RESOLVED", "REOPENED", "RESPONDED", "WITHDRAWN"]
    # findings survive recalculation; a new DRAFT run takes no finding; Phase 7 approval is unchanged by an open blocking finding
    blocking = _finding(client, k.qa, run.id, category="METHODOLOGY_ISSUE").json()
    a, actx = as_principal(db, k.analyst)
    draft = cs.recalculate(db, actx, a, run.id, "TEST draft")
    r = _finding(client, k.qa, draft.id)
    assert r.status_code == 409 and r.json()["error_code"] == "FINDING_RUN_DRAFT"
    cs.cancel(db, actx, a, draft.id, "TEST cancel")
    run2 = _recalc(db, k, run)
    assert run2.status == "APPROVED"                                                    # B6: not blocked by the open finding
    listed = client.get(f"{CALC}/findings", headers=k.qa.headers, params={"project_id": k.project_id, "monitoring_period_id": k.period_id}).json()
    assert blocking["id"] in [x["id"] for x in listed]
    r = client.post(f"{CALC}/findings/{blocking['id']}/respond", headers=k.analyst.headers, json={"response": "TEST fixed by re-run"})
    r = client.post(f"{CALC}/findings/{blocking['id']}/resolve", headers=k.qa.headers, json={"note": "fixed", "resolved_by_run_id": str(run2.id)})
    assert r.json()["resolved_by_run_id"] == str(run2.id)
    assert {"CALCULATION_FINDING_RAISED", "CALCULATION_FINDING_RESPONDED", "CALCULATION_FINDING_RESPONSE_RETURNED", "CALCULATION_FINDING_RESOLVED",
            "CALCULATION_FINDING_REOPENED", "CALCULATION_FINDING_WITHDRAWN"} <= _actions(db, "calculation_finding")


# ---------------------------------------------------------------- reports
def test_report_approved_only_deterministic_tamper_supersession_and_guard(client: TestClient, db: Session,
                                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    k = calc_scenario(db, client, 78.20, 23.20, "9200 2000 3000")
    calculated = _run(db, k, approve=False)
    r = client.post(f"{CALC}/runs/{calculated.id}/reports", headers=k.analyst.headers)
    assert r.status_code == 409 and r.json()["error_code"] == "RUN_NOT_APPROVED"                      # B7
    a, actx = as_principal(db, k.analyst)
    q, qctx = as_principal(db, k.qa)
    cs.submit(db, actx, a, calculated.id)
    cs.start_qa(db, qctx, q, calculated.id)
    cs.complete_qa(db, qctx, q, calculated.id, "PASS", "TEST checks pass", resolver=k.resolver)
    run = cs.approve(db, qctx, q, calculated.id, "TEST approved")
    assert client.post(f"{CALC}/runs/{run.id}/reports", headers=k.qa.headers).status_code == 403             # manage only
    monkeypatch.setattr(get_settings(), "CALCULATION_REPORT_MAX_ROWS", 2)
    assert client.post(f"{CALC}/runs/{run.id}/reports", headers=k.analyst.headers).json()["error_code"] == "REPORT_TOO_LARGE"
    monkeypatch.setattr(get_settings(), "CALCULATION_REPORT_MAX_ROWS", 20000)
    r = client.post(f"{CALC}/runs/{run.id}/reports", headers=k.analyst.headers)
    assert r.status_code == 201, r.text
    rep = r.json()
    assert rep["report_code"].startswith("CRPT-") and rep["status"] == "CURRENT" and rep["version"] == 1
    detail = client.get(f"{CALC}/reports/{rep['id']}", headers=k.x.c.mrv.headers).json()
    content = detail["content"]
    assert CALCULATED_LABEL in content["labels"] and any("TEST" in lbl for lbl in content["labels"])
    assert content["calculation_run"]["input_sha256"] == run.input_sha256 and len(content["inputs"]) == 4
    assert fw.sha256(content) == rep["content_sha256"] == fw.sha256(crep.build_content(db, run))      # deterministic
    pdf_bytes = client.get(f"{CALC}/reports/{rep['id']}/pdf", headers=k.qa.headers).content
    assert pdf_bytes.startswith(b"%PDF-1.4") and hashlib.sha256(pdf_bytes).hexdigest() == rep["pdf_sha256"]
    assert hashlib.sha256(crep.render_pdf(content)).hexdigest() == rep["pdf_sha256"]                    # re-render is byte-identical
    assert b"not verified, not issued" in pdf_bytes
    v = client.get(f"{CALC}/reports/{rep['id']}/verify", headers=k.qa.headers).json()
    assert v["valid"] and not v["stale"] and v["problems"] == []
    assert client.post(f"{CALC}/runs/{run.id}/reports", headers=k.analyst.headers).json()["error_code"] == "REPORT_UNCHANGED"
    # a finding changes the deterministic content → the report is stale → a new version supersedes it (never edited)
    _finding(client, k.qa, run.id, blocking=False, category="OBSERVATION")
    assert client.get(f"{CALC}/reports/{rep['id']}/verify", headers=k.qa.headers).json()["stale"] is True
    rep2 = client.post(f"{CALC}/runs/{run.id}/reports", headers=k.analyst.headers).json()
    assert rep2["version"] == 2 and rep2["content_sha256"] != rep["content_sha256"]
    old = client.get(f"{CALC}/reports/{rep['id']}", headers=k.qa.headers).json()
    assert old["status"] == "SUPERSEDED" and old["superseded_by_report_id"] == rep2["id"] and old["content_sha256"] == rep["content_sha256"]
    assert [x["version"] for x in client.get(f"{CALC}/runs/{run.id}/reports", headers=k.qa.headers).json()] == [1, 2]
    # tamper detection: the stored PDF is altered behind the system's back
    rep2_row = db.get(CalculationReport, uuid.UUID(rep2["id"]))
    assert rep2_row is not None
    doc = db.get(Document, rep2_row.document_id)
    dv = db.scalars(select(DocumentVersion).where(DocumentVersion.document_id == rep2_row.document_id)).one()
    assert doc is not None and doc.category == "CALCULATION_REPORT" and doc.entity_type == "calculation_run"
    get_storage().put(dv.storage_key, pdf_bytes.replace(b"Page 1", b"Page X"), "application/pdf")
    v = client.get(f"{CALC}/reports/{rep2['id']}/verify", headers=k.qa.headers).json()
    assert v["valid"] is False and any("stored PDF" in p for p in v["problems"])
    assert client.get(f"{CALC}/reports/{rep2['id']}/pdf", headers=k.qa.headers).json()["error_code"] == "DOCUMENT_INTEGRITY_FAILURE"
    assert {"CALCULATION_REPORT_GENERATED", "CALCULATION_REPORT_SUPERSEDED"} <= _actions(db, "calculation_report")


# ---------------------------------------------------------------- readiness
def test_readiness_blockers_approval_manifest_and_invalidation(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    k = calc_scenario(db, client, 78.30, 23.30, "9300 2000 3000")
    v = _view(client, k.qa, k)
    assert _codes(v) == ["NO_APPROVED_CALCULATION"] and v["label"] == "Internal readiness — not verification"
    new = {"monitoring_period_id": k.period_id}
    url = f"{CALC}/projects/{k.project_id}/verification-readiness"
    assert client.post(url, headers=k.analyst.headers, json=new).json()["error_code"] == "NO_APPROVED_CALCULATION"
    run = _run(db, k)
    assert _codes(_view(client, k.qa, k)) == ["REPORT_MISSING"]
    client.post(f"{CALC}/runs/{run.id}/reports", headers=k.analyst.headers)
    f = _finding(client, k.qa, run.id, category="MISSING_EVIDENCE").json()                    # blocking
    assert _codes(_view(client, k.qa, k)) == ["REPORT_STALE", "OPEN_BLOCKING_FINDINGS"]
    client.post(f"{CALC}/findings/{f['id']}/respond", headers=k.analyst.headers, json={"response": "TEST evidence supplied"})
    client.post(f"{CALC}/findings/{f['id']}/resolve", headers=k.qa.headers, json={"note": "evidence ok"})
    client.post(f"{CALC}/runs/{run.id}/reports", headers=k.analyst.headers)                       # regenerate (findings changed)
    v = _view(client, k.qa, k)
    assert v["ready_to_submit"] and v["blockers"] == [] and v["current_run_code"] == run.run_code
    monkeypatch.setattr(get_settings(), "APP_ENV", "production")
    assert "NOT_PRODUCTION_READY" in _codes(_view(client, k.qa, k))
    monkeypatch.setattr(get_settings(), "APP_ENV", "test")
    # create → submit (analyst) → approve (QA, independent) = READY ("internally approved for submission to verification")
    r = client.post(url, headers=k.analyst.headers, json=new).json()
    assert r["status"] == "DRAFT" and r["readiness_code"].startswith("RDY-")
    assert client.post(url, headers=k.analyst.headers, json=new).json()["error_code"] == "READINESS_EXISTS"
    rid = r["id"]
    assert client.post(f"{CALC}/readiness/{rid}/approve", headers=k.qa.headers, json={"notes": "early"}).json()["error_code"] == \
        "READINESS_NOT_SUBMITTED"
    assert client.post(f"{CALC}/readiness/{rid}/submit", headers=k.analyst.headers).json()["status"] == "SUBMITTED"
    assert client.post(f"{CALC}/readiness/{rid}/approve", headers=k.analyst.headers, json={"notes": "self"}).status_code == 403
    r = client.post(f"{CALC}/readiness/{rid}/approve", headers=k.qa.headers, json={"notes": "internal checks complete"})
    assert r.status_code == 200 and r.json()["status"] == "READY", r.text
    assert r.json()["meaning"] == "Internally approved for submission to verification."
    pkg = client.get(f"{CALC}/readiness/{rid}/package", headers=k.x.c.t.pm.headers).json()
    m = pkg["manifest"]
    assert pkg["manifest_sha256"] == fw.sha256(m) and m["label"] == "Internal readiness — not verification"
    assert m["calculation_run"]["output_sha256"] == run.output_sha256 and len(m["laboratory_results"]) == 2
    assert m["calculation_report"]["version"] == 2 and m["dataset"]["snapshot_sha256"] and m["findings"][0]["status"] == "RESOLVED"
    assert {"project", "reporting_period", "crediting_period", "methodology", "mrv_evidence", "qa_reviews"} <= set(m)
    assert db.get(Project, uuid.UUID(k.project_id)).status == "CALCULATED"                    # B9: no project state added  # type: ignore[union-attr]
    lin = client.get(f"{CALC}/runs/{run.id}/lineage", headers=k.qa.headers).json()
    assert lin["readiness"][0]["status"] == "READY" and len(lin["reports"]) == 2 and lin["findings"][0]["status"] == "RESOLVED"
    # B12: a blocking finding invalidates READY immediately
    f2 = _finding(client, k.qa, run.id, category="NON_CONFORMITY").json()
    assert client.get(f"{CALC}/readiness/{rid}", headers=k.qa.headers).json()["status"] == "INVALIDATED"
    client.post(f"{CALC}/findings/{f2['id']}/respond", headers=k.analyst.headers, json={"response": "TEST corrected"})
    client.post(f"{CALC}/findings/{f2['id']}/resolve", headers=k.qa.headers, json={"note": "corrected"})
    client.post(f"{CALC}/runs/{run.id}/reports", headers=k.analyst.headers)
    # rejection and withdrawal paths
    r2 = client.post(url, headers=k.analyst.headers, json=new).json()
    client.post(f"{CALC}/readiness/{r2['id']}/submit", headers=k.analyst.headers)
    assert client.post(f"{CALC}/readiness/{r2['id']}/reject", headers=k.qa.headers, json={"notes": "not yet"}).json()["status"] == "REJECTED"
    r3 = client.post(url, headers=k.analyst.headers, json=new).json()
    assert client.post(f"{CALC}/readiness/{r3['id']}/withdraw", headers=k.analyst.headers, json={"reason": "TEST later"}).json()["status"] == \
        "WITHDRAWN"
    # SoD: a person who submitted (or ran the calculation) never approves
    dual = staff(db, client, k.x.c.t.org, "CALCULATION_ANALYST", "QA_OFFICER")
    r4 = client.post(url, headers=dual.headers, json=new).json()
    client.post(f"{CALC}/readiness/{r4['id']}/submit", headers=dual.headers)
    r = client.post(f"{CALC}/readiness/{r4['id']}/approve", headers=dual.headers, json={"notes": "self approval"})
    assert r.status_code == 403 and r.json()["error_code"] == "SEPARATION_OF_DUTIES"
    assert client.post(f"{CALC}/readiness/{r4['id']}/approve", headers=k.qa.headers, json={"notes": "independent"}).json()["status"] == "READY"
    # B12: a newer approved run supersedes the run → READY is invalidated when read
    _recalc(db, k, run)
    v = _view(client, k.qa, k)
    assert next(x for x in v["reviews"] if x["id"] == r4["id"])["status"] == "INVALIDATED" and "REPORT_MISSING" in _codes(v)
    actions = _actions(db, "calculation_readiness")
    assert {"CALCULATION_READINESS_CREATED", "CALCULATION_READINESS_SUBMITTED", "CALCULATION_READINESS_READY", "CALCULATION_READINESS_REJECTED",
            "CALCULATION_READINESS_WITHDRAWN", "CALCULATION_READINESS_INVALIDATED"} <= actions
    db.expire_all()
    rows = db.scalars(select(CalculationReadinessReview).where(CalculationReadinessReview.project_id == uuid.UUID(k.project_id))).all()
    assert all(x.environment == "LIVE" for x in rows) and db.scalars(select(CalculationFinding)).first() is not None


# ---------------------------------------------------------------- RBAC, isolation, DEMO
def test_rbac_and_organization_isolation(client: TestClient, db: Session) -> None:
    k = calc_scenario(db, client, 78.40, 23.40, "9400 2000 3000")
    run = _run(db, k)
    rep = client.post(f"{CALC}/runs/{run.id}/reports", headers=k.analyst.headers).json()
    f = _finding(client, k.qa, run.id, blocking=False, category="CLARIFICATION").json()
    params = {"project_id": k.project_id}
    for actor in (k.x.c.mrv, k.x.c.t.pm, k.analyst, k.qa):
        assert client.get(f"{CALC}/findings", headers=actor.headers, params=params).status_code == 200
        assert client.get(f"{CALC}/reports/{rep['id']}", headers=actor.headers).status_code == 200
    assert _finding(client, k.x.c.mrv, run.id).status_code == 403                                  # MRV manager reads only
    vvb_org = make_org(db, org_type="VVB")
    outsiders = [k.x.tech, k.x.mgr, staff(db, client, k.x.c.t.org, "FINANCE_MANAGER"), staff(db, client, vvb_org, "VVB_REVIEWER"),
                 staff(db, client, make_org(db, org_type="BUYER"), "BUYER"), Actor(u := make_user(db, roles=[("FARMER", k.x.c.t.org)]), login(client, u))]
    for actor in outsiders:                                                                         # incl. VVB: no Phase 8A access
        for path in (f"/findings/{f['id']}", f"/reports/{rep['id']}", f"/reports/{rep['id']}/pdf"):
            assert client.get(f"{CALC}{path}", headers=actor.headers).status_code in (403, 404), (path, actor)
        assert client.get(f"{CALC}/projects/{k.project_id}/verification-readiness", headers=actor.headers,
                          params={"monitoring_period_id": k.period_id}).status_code in (403, 404)
    other = staff(db, client, make_org(db), "CALCULATION_ANALYST", "QA_OFFICER")                    # another organization
    for path in (f"/findings/{f['id']}", f"/reports/{rep['id']}", f"/reports/{rep['id']}/verify"):
        assert client.get(f"{CALC}{path}", headers=other.headers).status_code == 404
    assert client.get(f"{CALC}/findings", headers=other.headers, params=params).status_code == 404
    assert _finding(client, other, run.id).status_code == 404
    assert client.post(f"{CALC}/projects/{k.project_id}/verification-readiness", headers=other.headers,
                       json={"monitoring_period_id": k.period_id}).status_code == 404
    doc = client.get(f"/api/v1/evidence/documents/{rep['document_id']}", headers=other.headers)
    assert doc.status_code == 404                                                                   # the report document follows the run


def test_demo_niphad_stays_blocked_with_no_calculation_module(client: TestClient, db: Session) -> None:
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
    from app.models import MonitoringPeriod
    p = db.scalars(select(Project).where(Project.environment == "DEMO", Project.name.like("Niphad%"))).one()
    mp = db.scalars(select(MonitoringPeriod).where(MonitoringPeriod.project_id == p.id)).first()
    assert mp is not None
    org = db.scalars(select(Organization).where(Organization.code == "DEMO-DEV-A")).one()
    an = login(client, make_user(db, roles=[("CALCULATION_ANALYST", org)], environment="DEMO"))
    qa = login(client, make_user(db, roles=[("QA_OFFICER", org)], environment="DEMO"))
    v = client.get(f"{CALC}/projects/{p.id}/verification-readiness", headers=qa, params={"monitoring_period_id": str(mp.id)}).json()
    assert [b["code"] for b in v["blockers"]] == ["NO_APPROVED_CALCULATION"] and v["environment"] == "DEMO"
    assert (v["calculation_blockers"][0]["code"], v["calculation_blockers"][0]["reason"]) == ("CONFIGURATION_REQUIRED", "NO_CALCULATION_MODULE")
    assert client.post(f"{CALC}/projects/{p.id}/verification-readiness", headers=an,
                       json={"monitoring_period_id": str(mp.id)}).json()["error_code"] == "NO_APPROVED_CALCULATION"
    run = client.post(f"{CALC}/runs", headers=an, json={"project_id": str(p.id), "monitoring_period_id": str(mp.id)}).json()
    assert client.post(f"{CALC}/runs/{run['id']}/freeze", headers=an).json()["details"]["reason"] == "NO_CALCULATION_MODULE"
    assert client.post(f"{CALC}/runs/{run['id']}/reports", headers=an).json()["error_code"] == "RUN_NOT_APPROVED"   # no report for BLOCKED
    f = client.post(f"{CALC}/runs/{run['id']}/findings", headers=qa, json={"category": "METHODOLOGY_ISSUE", "blocking": True,
                                                                          "title": "No calculation module", "description": "DEMO: blocked"})
    assert f.status_code == 201 and f.json()["environment"] == "DEMO"                              # findings on a non-DRAFT (BLOCKED) run
    assert db.get(Project, p.id).status == "MONITORING"  # type: ignore[union-attr]


# ---------------------------------------------------------------- database triggers
def _dedicated(build: Any) -> None:
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
            stmt, params, msg = build(session, client)
        session.flush()
        with pytest.raises(DBAPIError) as exc:
            conn.execute(text(stmt), params)
        assert msg in str(exc.value)
    finally:
        limiter.reset()
        conn.invalidate()
        with contextlib.suppress(Exception):
            session.close()


def test_triggers_protect_reports_and_finding_events() -> None:
    def build(session: Session, client: TestClient) -> tuple[str, dict, str]:
        k = calc_scenario(session, client, 78.60, 23.60, "9600 2000 3000")
        run = _run(session, k)
        rep = client.post(f"{CALC}/runs/{run.id}/reports", headers=k.analyst.headers).json()
        return "UPDATE calculation_reports SET content_sha256 = N'0' WHERE id = :i", {"i": rep["id"]}, "immutable"
    _dedicated(build)
    from sqlalchemy.exc import DBAPIError

    from app.core.database import get_engine
    with get_engine().connect() as c2:
        t2 = c2.begin()
        with pytest.raises(DBAPIError) as e2:
            c2.execute(text("UPDATE calculation_finding_events SET note = N'x' WHERE 1 = 0"))
        assert "append-only" in str(e2.value)
        if t2.is_active:
            t2.rollback()


def test_triggers_protect_findings_and_readiness() -> None:
    def build(session: Session, client: TestClient) -> tuple[str, dict, str]:
        k = calc_scenario(session, client, 78.70, 23.70, "9700 2000 3000")
        run = _run(session, k)
        f = _finding(client, k.qa, run.id).json()
        return "UPDATE calculation_findings SET description = N'rewritten' WHERE id = :i", {"i": f["id"]}, "immutable"
    _dedicated(build)

    def build2(session: Session, client: TestClient) -> tuple[str, dict, str]:
        k = calc_scenario(session, client, 78.80, 23.80, "9800 2000 3000")
        run = _run(session, k)
        client.post(f"{CALC}/runs/{run.id}/reports", headers=k.analyst.headers)
        url = f"{CALC}/projects/{k.project_id}/verification-readiness"
        r = client.post(url, headers=k.analyst.headers, json={"monitoring_period_id": k.period_id}).json()
        client.post(f"{CALC}/readiness/{r['id']}/submit", headers=k.analyst.headers)
        ok = client.post(f"{CALC}/readiness/{r['id']}/approve", headers=k.qa.headers, json={"notes": "ready"}).json()
        assert ok["status"] == "READY", ok
        return "UPDATE calculation_readiness_reviews SET status = N'DRAFT' WHERE id = :i", {"i": r["id"]}, "immutable"
    _dedicated(build2)



