"""Phase 8B — VVB / ACVA verification workflow (verification only: no validation, registry, issuance or credits).

Assignments (two-sided, COI on acceptance, one open per period, no reactivation, replacement), submission of the currently valid Phase 8A
READY package only (and its invalidation after a recalculation), the VVB's allow-list package view and manifest-scoped downloads,
findings and corrective actions (VVB raises / closes, project responds), the recorded external decision (report PDF, separation of
duties, VVB-stated verified quantity kept apart from the calculated quantity), aggregate project status, lineage, cross-organization
isolation, two-organization audit, the DEMO Niphad assignment-only path and the database triggers. Successful paths use the TEST-only
Phase 7 fixture (never registered in the application, unreachable through the API) inside the rolled-back test database."""
import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    CalculationRun,
    Organization,
    Permission,
    Project,
    Role,
    RolePermission,
    VerificationAssignment,
    VerificationDecision,
)
from app.services import calculation_service as cs
from app.services import document_service
from tests.calc_fixture import CALC, CalcCtx, as_principal, calc_scenario
from tests.conftest import Actor, login, make_org, make_user
from tests.phase2 import staff
from tests.test_preverification import _dedicated, _recalc, _run

V = "/api/v1/verification"
VVB = "/api/v1/vvb"
PDF = b"%PDF-1.4\n%TEST verification document\n%%EOF\n"
COI = "TEST: no conflict of interest with the project, its developer or its farmers."


def _ready(client: TestClient, db: Session, k: CalcCtx, run: CalculationRun | None = None) -> tuple[CalculationRun, str]:
    """Approved run → report → readiness DRAFT → SUBMITTED → READY (Phase 8A)."""
    run = run or _run(db, k)
    assert client.post(f"{CALC}/runs/{run.id}/reports", headers=k.analyst.headers).status_code == 201
    r = client.post(f"{CALC}/projects/{k.project_id}/verification-readiness", headers=k.analyst.headers,
                    json={"monitoring_period_id": k.period_id}).json()
    client.post(f"{CALC}/readiness/{r['id']}/submit", headers=k.analyst.headers)
    ok = client.post(f"{CALC}/readiness/{r['id']}/approve", headers=k.qa.headers, json={"notes": "internal checks complete"}).json()
    assert ok["status"] == "READY", ok
    return run, r["id"]


def _vvb(db: Session, client: TestClient, environment: str = "LIVE") -> tuple[Organization, Actor, Actor]:
    org = make_org(db, org_type="VVB", environment=environment)
    a = make_user(db, roles=[("VVB_REVIEWER", org)], environment=environment)
    b = make_user(db, roles=[("VVB_REVIEWER", org)], environment=environment)
    return org, Actor(a, login(client, a)), Actor(b, login(client, b))


def _propose(client: TestClient, k: CalcCtx, org: Organization, period_id: str | None = None, **kw: Any) -> Any:
    return client.post(f"{V}/projects/{k.project_id}/assignments", headers=k.x.c.t.pm.headers,
                       json={"monitoring_period_id": period_id or k.period_id, "vvb_organization_id": str(org.id), **kw})


def _accepted(client: TestClient, k: CalcCtx, org: Organization, vvb: Actor) -> dict:
    a = _propose(client, k, org).json()
    r = client.post(f"{VVB}/assignments/{a['id']}/accept", headers=vvb.headers, json={"coi_declaration": COI})
    assert r.status_code == 200, r.text
    return r.json()


def _submitted(client: TestClient, db: Session, k: CalcCtx) -> tuple[dict, dict, Organization, Actor, Actor, CalculationRun]:
    run, _ = _ready(client, db, k)
    org, v1, v2 = _vvb(db, client)
    a = _accepted(client, k, org, v1)
    s = client.post(f"{V}/assignments/{a['id']}/submit", headers=k.x.c.t.pm.headers)
    assert s.status_code == 201, s.text
    return a, s.json(), org, v1, v2, run


def _vfinding(client: TestClient, vvb: Actor, sid: str, **kw: Any) -> Any:
    body = {"category": "MISSING_EVIDENCE", "blocking": True, "title": "TEST finding", "description": "TEST: evidence needed",
            "target_type": "SUBMISSION", **kw}
    return client.post(f"{VVB}/submissions/{sid}/findings", headers=vvb.headers, json=body)


def _decide(client: TestClient, vvb: Actor, sid: str, file: tuple | None = ("report.pdf", PDF, "application/pdf"), **form: Any) -> Any:
    data = {"outcome": "VERIFIED", "rationale": "TEST: the VVB's report concludes verification", **form}
    return client.post(f"{VVB}/submissions/{sid}/decision", headers=vvb.headers, data=data, files={"file": file} if file else None)


def _audit(db: Session, action: str) -> list[AuditLog]:
    return list(db.scalars(select(AuditLog).where(AuditLog.action == action)).all())


def _project(db: Session, k: CalcCtx) -> Project:
    p = db.get(Project, uuid.UUID(k.project_id))
    assert p is not None
    db.refresh(p)
    return p


# ---------------------------------------------------------------- roles (C19)
def test_permission_grants_are_exactly_the_phase_8b_matrix(db: Session) -> None:
    def perms(role: str) -> set[str]:
        return {c for (c,) in db.execute(select(Permission.code).join(RolePermission, RolePermission.permission_id == Permission.id)
                                         .join(Role, Role.id == RolePermission.role_id).where(Role.code == role))}
    verif = {r: {p for p in perms(r) if p.startswith("verification.")} for r in
             ("PROJECT_MANAGER", "MRV_MANAGER", "CALCULATION_ANALYST", "QA_OFFICER", "VVB_REVIEWER", "FARMER", "LAB_TECHNICIAN")}
    assert verif["PROJECT_MANAGER"] == {"verification.read", "verification.manage", "verification.respond"}
    assert verif["MRV_MANAGER"] == verif["CALCULATION_ANALYST"] == {"verification.read", "verification.respond"}
    assert verif["QA_OFFICER"] == {"verification.read"}
    assert verif["FARMER"] == verif["LAB_TECHNICIAN"] == set()
    assert perms("VVB_REVIEWER") == {"verification.vvb_read", "verification.vvb_review", "verification.decide"}   # nothing else


# ---------------------------------------------------------------- assignments (C3, C5, C7)
def test_assignment_lifecycle_coi_one_open_no_reactivation_and_replacement(client: TestClient, db: Session) -> None:
    k = calc_scenario(db, client, 79.10, 24.10, "9110 2000 3000")
    org, v1, _ = _vvb(db, client)
    pm, qa, an = k.x.c.t.pm, k.qa, k.analyst
    # who may propose: verification.manage (PM); read / respond holders may not
    assert _propose(client, k, org).status_code == 201
    assert client.post(f"{V}/projects/{k.project_id}/assignments", headers=qa.headers,
                       json={"monitoring_period_id": k.period_id, "vvb_organization_id": str(org.id)}).status_code == 403
    assert client.post(f"{V}/projects/{k.project_id}/assignments", headers=an.headers,
                       json={"monitoring_period_id": k.period_id, "vvb_organization_id": str(org.id)}).status_code == 403
    first = client.get(f"{V}/projects/{k.project_id}/assignments", headers=pm.headers).json()[0]
    assert first["status"] == "PROPOSED" and first["assignment_code"].startswith("VAS-") and first["actions"] == ["withdraw"]
    # one open assignment per project + period
    assert _propose(client, k, org).json()["error_code"] == "OPEN_ASSIGNMENT_EXISTS"
    # C3: only an ACTIVE VVB organization (org_type VVB) of the same environment
    dev = make_org(db)
    demo_vvb = make_org(db, org_type="VVB", environment="DEMO")
    inactive = make_org(db, org_type="VVB")
    inactive.status = "SUSPENDED"
    db.flush()
    for bad in (dev, demo_vvb, inactive):
        assert client.post(f"{V}/projects/{k.project_id}/assignments", headers=pm.headers, json={
            "monitoring_period_id": k.period_id, "vvb_organization_id": str(bad.id)}).json()["error_code"] == "NOT_A_VVB"
    assert {o["id"] for o in client.get(f"{V}/projects/{k.project_id}/vvb-organizations", headers=pm.headers).json()} >= {str(org.id)}
    assert str(dev.id) not in {o["id"] for o in client.get(f"{V}/projects/{k.project_id}/vvb-organizations", headers=pm.headers).json()}
    assert _propose(client, k, org, period_id=str(uuid.uuid4())).status_code == 404
    # the VVB sees the PROPOSED assignment (no package before acceptance); C7: COI declaration is mandatory
    mine = client.get(f"{VVB}/assignments", headers=v1.headers).json()
    assert [a["id"] for a in mine] == [first["id"]] and mine[0]["submissions"] == [] and mine[0]["actions"] == ["accept", "decline"]
    assert mine[0]["proposed_by_name"] == "Project team"
    assert client.post(f"{VVB}/assignments/{first['id']}/accept", headers=v1.headers, json={}).status_code == 422
    assert client.post(f"{VVB}/assignments/{first['id']}/accept", headers=v1.headers, json={"coi_declaration": "none"}).status_code == 422
    assert client.post(f"{V}/assignments/{first['id']}/accept", headers=pm.headers, json={"coi_declaration": COI}).status_code in (404, 405)
    acc = client.post(f"{VVB}/assignments/{first['id']}/accept", headers=v1.headers, json={"coi_declaration": COI}).json()
    assert acc["status"] == "ACCEPTED" and acc["coi_declaration"] == COI and acc["coi_declared_at"] and acc["accepted_by_name"]
    assert client.post(f"{VVB}/assignments/{first['id']}/decline", headers=v1.headers, json={"reason": "too late"}).json()["error_code"] == \
        "ASSIGNMENT_NOT_PROPOSED"
    assert client.post(f"{V}/assignments/{first['id']}/withdraw", headers=pm.headers, json={"reason": "too late"}).json()["error_code"] == \
        "ASSIGNMENT_NOT_PROPOSED"
    assert _project(db, k).status == "MONITORING"          # no approved calculation yet → no aggregate status change
    # terminate (project, reason required) → final; never reactivated
    assert client.post(f"{V}/assignments/{first['id']}/terminate", headers=pm.headers, json={}).status_code == 422
    t = client.post(f"{V}/assignments/{first['id']}/terminate", headers=pm.headers, json={"reason": "TEST: scope changed"}).json()
    assert t["status"] == "TERMINATED" and t["closed_side"] == "PROJECT"
    assert client.post(f"{VVB}/assignments/{first['id']}/accept", headers=v1.headers, json={"coi_declaration": COI}).status_code == 404
    # replacement links the previous (closed) assignment of the same period
    rep = _propose(client, k, org, previous_assignment_id=first["id"]).json()
    assert rep["previous_assignment_id"] == first["id"]
    assert client.post(f"{VVB}/assignments/{rep['id']}/decline", headers=v1.headers, json={}).status_code == 422
    assert client.post(f"{VVB}/assignments/{rep['id']}/decline", headers=v1.headers, json={"reason": "TEST: capacity"}).json()["status"] == \
        "DECLINED"
    third = _propose(client, k, org, previous_assignment_id=rep["id"]).json()
    assert _propose(client, k, org, previous_assignment_id=third["id"]).json()["error_code"] == "OPEN_ASSIGNMENT_EXISTS"
    assert client.post(f"{V}/assignments/{third['id']}/withdraw", headers=pm.headers, json={"reason": "TEST: re-plan"}).json()["status"] == \
        "WITHDRAWN"
    assert client.get(f"{VVB}/assignments/{third['id']}", headers=v1.headers).status_code == 404     # withdrawn: no longer visible
    op = client.post("/api/v1/mrv/monitoring-periods", headers=k.x.c.mrv.headers, json={
        "project_id": k.project_id, "name": "Monitoring 2", "start_date": "2030-06-01", "end_date": "2031-05-31"})
    assert op.status_code == 201, op.text
    other_period = op.json()
    assert _propose(client, k, org, period_id=other_period["id"], previous_assignment_id=rep["id"]).json()["error_code"] == "INVALID_REPLACEMENT"
    assert _propose(client, k, org, period_id=other_period["id"]).status_code == 201     # one open assignment per period, not per project
    # C12: audited in both organizations, with the actor side
    for action in ("VERIFICATION_ASSIGNMENT_PROPOSED", "VERIFICATION_ASSIGNMENT_ACCEPTED", "VERIFICATION_COI_DECLARED",
                   "VERIFICATION_ASSIGNMENT_TERMINATED", "VERIFICATION_ASSIGNMENT_DECLINED", "VERIFICATION_ASSIGNMENT_WITHDRAWN"):
        rows = [r for r in _audit(db, action) if r.entity_id in (first["id"], rep["id"], third["id"])]
        assert {r.organization_id for r in rows} == {k.x.c.t.org.id, org.id}, action
    assert '"actor_side": "VVB"' in next(r for r in _audit(db, "VERIFICATION_COI_DECLARED") if r.entity_id == first["id"]).new_value


# ---------------------------------------------------------------- submission (C6)
def test_submission_needs_valid_ready_package_and_recalculation_invalidates(client: TestClient, db: Session) -> None:
    k = calc_scenario(db, client, 79.20, 24.20, "9120 2000 3000")
    org, v1, _ = _vvb(db, client)
    pm = k.x.c.t.pm
    a = _propose(client, k, org).json()
    assert client.post(f"{V}/assignments/{a['id']}/submit", headers=pm.headers).json()["error_code"] == "ASSIGNMENT_NOT_ACCEPTED"
    client.post(f"{VVB}/assignments/{a['id']}/accept", headers=v1.headers, json={"coi_declaration": COI})
    # C6: assignment before READY is allowed; submission is not
    assert client.post(f"{V}/assignments/{a['id']}/submit", headers=pm.headers).json()["error_code"] == "NO_READY_PACKAGE"
    view = client.get(f"{V}/projects/{k.project_id}/periods/{k.period_id}", headers=pm.headers).json()
    assert any("READY" in b for b in view["submit_blockers"]) and view["calculated_label"] == "Calculated tCO2e — not verified, not issued"
    run, rid = _ready(client, db, k)
    assert _project(db, k).status == "CALCULATED"
    assert client.post(f"{V}/assignments/{a['id']}/submit", headers=k.analyst.headers).status_code == 403      # verification.manage only
    s = client.post(f"{V}/assignments/{a['id']}/submit", headers=pm.headers).json()
    assert s["status"] == "SUBMITTED" and s["submission_code"].startswith("VSUB-") and s["seq"] == 1 and s["readiness_review_id"] == rid
    assert s["calculated_value"] == run.net_result and s["calculation_run_id"] == str(run.id)
    pkg = client.get(f"{CALC}/readiness/{rid}/package", headers=pm.headers).json()
    assert s["manifest_sha256"] == pkg["manifest_sha256"]
    assert _project(db, k).status == "VERIFICATION"        # C2: aggregate — accepted assignment + approved calculation
    assert client.post(f"{V}/assignments/{a['id']}/submit", headers=pm.headers).json()["error_code"] == "SUBMISSION_EXISTS"
    # a recalculation supersedes the run → READY invalidated → the submission is INVALIDATED (never mutated otherwise)
    run2 = _recalc(db, k, run)
    got = client.get(f"{VVB}/assignments/{a['id']}", headers=v1.headers).json()
    old = next(x for x in got["submissions"] if x["id"] == s["id"])
    assert old["status"] == "INVALIDATED" and old["manifest_sha256"] == s["manifest_sha256"] and got["current_submission"] is None
    assert client.post(f"{V}/assignments/{a['id']}/submit", headers=pm.headers).json()["error_code"] == "NO_READY_PACKAGE"
    _, rid2 = _ready(client, db, k, run2)
    s2 = client.post(f"{V}/assignments/{a['id']}/submit", headers=pm.headers).json()
    assert s2["seq"] == 2 and s2["readiness_review_id"] == rid2 and s2["calculation_run_id"] == str(run2.id)
    # the invalidated package is no longer reachable for new VVB work
    assert _vfinding(client, v1, s["id"]).json()["error_code"] == "SUBMISSION_NOT_CURRENT"
    assert {"VERIFICATION_SUBMITTED", "VERIFICATION_SUBMISSION_INVALIDATED"} <= {r.action for r in db.scalars(
        select(AuditLog).where(AuditLog.entity_type == "verification_submission"))}


def test_submission_fails_for_stale_readiness_wrong_period_and_wrong_project(client: TestClient, db: Session) -> None:
    k = calc_scenario(db, client, 79.25, 24.25, "9125 2000 3000")
    run, rid = _ready(client, db, k)
    org, v1, _ = _vvb(db, client)
    pm = k.x.c.t.pm
    a = _accepted(client, k, org, v1)
    # stale: a blocking Phase 8A finding invalidates READY → no submission
    f = client.post(f"{CALC}/runs/{run.id}/findings", headers=k.qa.headers, json={"category": "NON_CONFORMITY", "blocking": True,
                                                                                  "title": "TEST", "description": "TEST: stale"}).json()
    assert client.post(f"{V}/assignments/{a['id']}/submit", headers=pm.headers).json()["error_code"] == "NO_READY_PACKAGE"
    assert client.get(f"{CALC}/readiness/{rid}", headers=k.qa.headers).json()["status"] == "INVALIDATED"
    client.post(f"{CALC}/findings/{f['id']}/respond", headers=k.analyst.headers, json={"response": "TEST corrected"})
    client.post(f"{CALC}/findings/{f['id']}/resolve", headers=k.qa.headers, json={"note": "corrected"})
    # wrong period: the READY package of period 1 is never submitted under an assignment of period 2
    op = client.post("/api/v1/mrv/monitoring-periods", headers=k.x.c.mrv.headers, json={
        "project_id": k.project_id, "name": "Monitoring 2", "start_date": "2030-06-01", "end_date": "2031-05-31"}).json()
    a2 = _propose(client, k, org, period_id=op["id"]).json()
    client.post(f"{VVB}/assignments/{a2['id']}/accept", headers=v1.headers, json={"coi_declaration": COI})
    _, rid2 = _ready(client, db, k, run)
    assert client.post(f"{V}/assignments/{a2['id']}/submit", headers=pm.headers).json()["error_code"] == "NO_READY_PACKAGE"
    # wrong project: another organization's manager cannot submit (or see) this assignment
    other_pm = staff(db, client, make_org(db), "PROJECT_MANAGER")
    assert client.post(f"{V}/assignments/{a['id']}/submit", headers=other_pm.headers).status_code == 404
    s = client.post(f"{V}/assignments/{a['id']}/submit", headers=pm.headers).json()
    assert s["readiness_review_id"] == rid2 and s["status"] == "SUBMITTED"
    assert client.get(f"{V}/submissions/{s['id']}", headers=k.qa.headers).json()["submission_code"] == s["submission_code"]
    assert [x["id"] for x in client.get(f"{V}/assignments/{a['id']}/submissions", headers=k.qa.headers).json()] == [s["id"]]
    # the VVB of period 1 cannot reach period 2's work through period 1's submission, nor another VVB's
    assert client.get(f"{VVB}/assignments/{a2['id']}", headers=v1.headers).json()["current_submission"] is None


# ---------------------------------------------------------------- VVB package view and documents (C8–C11)
def test_vvb_package_is_an_allow_list_and_downloads_are_manifest_scoped(client: TestClient, db: Session) -> None:
    k = calc_scenario(db, client, 79.30, 24.30, "9130 2000 3000")
    a, s, org, v1, _, run = _submitted(client, db, k)
    pkg = client.get(f"{VVB}/submissions/{s['id']}/package", headers=v1.headers)
    assert pkg.status_code == 200, pkg.text
    p = pkg.json()
    readiness = client.get(f"{CALC}/readiness/{s['readiness_review_id']}/package", headers=k.x.c.t.pm.headers).json()
    assert p["manifest"] == readiness["manifest"] and p["manifest_sha256"] == s["manifest_sha256"]      # C11: the manifest as-is
    assert p["manifest"]["findings"] is not None and p["label"] == "Calculated tCO2e — not verified, not issued"
    assert len(p["calculation"]["inputs"]) == len(cs.inputs(db, run.id)) and p["calculation"]["run"]["id"] == str(run.id)
    assert p["calculation"]["outputs"] and p["report"]["report_code"] and len(p["laboratory_results"]) == 2
    farm = p["farms"][0]
    assert set(farm) == {"farm_id", "farm_code", "farmer_code", "area_hectares", "boundary_version", "boundary"}
    assert farm["farmer_code"].startswith("FRM-") and farm["boundary"]["type"] == "Polygon"
    text = pkg.text.lower()
    for forbidden in ("primary_phone", "+91", "bank", "kyc", "id_number", "9130 2000 3000", "asha", "agreement_number", "audit"):
        assert forbidden not in text, forbidden
    docs = {d["source"]: d for d in p["documents"]}
    assert {"CALCULATION_REPORT", "LAB_REPORT"} <= set(docs)
    r = client.get(f"{VVB}/submissions/{s['id']}/documents/{docs['LAB_REPORT']['document_id']}", headers=v1.headers)
    assert r.status_code == 200 and r.headers["x-content-sha256"] == docs["LAB_REPORT"]["sha256"]
    rows = [x for x in _audit(db, "VVB_DOCUMENT_DOWNLOADED") if x.entity_id == s["id"]]
    assert {x.organization_id for x in rows} == {k.x.c.t.org.id, org.id}
    # a project document outside the manifest is never readable through the VVB API (and not through the generic one either)
    pm, pctx = as_principal(db, k.x.c.t.pm)
    other = document_service.create_document(db, pctx, entity_type="project", entity_id=uuid.UUID(k.project_id), organization_id=k.x.c.t.org.id,
                                             environment="LIVE", category="PROJECT_DESIGN", title="TEST internal", filename="x.pdf", data=PDF)
    db.flush()
    assert client.get(f"{VVB}/submissions/{s['id']}/documents/{other.id}", headers=v1.headers).status_code == 404
    gen = "/api/v1/evidence/documents"
    assert client.get(f"{gen}/{other.id}/download", headers=k.x.c.t.pm.headers).status_code == 200          # control: the route exists
    assert client.get(f"{gen}/{other.id}/download", headers=v1.headers).status_code == 404
    assert client.get(f"{gen}/{docs['CALCULATION_REPORT']['document_id']}/download", headers=v1.headers).status_code == 404
    # no generic project / calculation / farmer / audit access for the VVB user
    for url in (f"/api/v1/projects/{k.project_id}", f"{CALC}/runs/{run.id}", f"{V}/projects/{k.project_id}/assignments", "/api/v1/farmers"):
        assert client.get(url, headers=k.x.c.t.pm.headers).status_code == 200, url               # control: the route exists
        assert client.get(url, headers=v1.headers).status_code in (403, 404), url
    for url in ("/api/v1/admin/audit-logs", "/api/v1/admin/workflow-events"):
        assert client.get(url, headers=v1.headers).status_code == 403, url


# ---------------------------------------------------------------- findings and corrective actions (C13, C14)
def test_vvb_findings_and_corrective_actions_lifecycle(client: TestClient, db: Session) -> None:
    k = calc_scenario(db, client, 79.40, 24.40, "9140 2000 3000")
    a, s, org, v1, _, run = _submitted(client, db, k)
    pm, qa, an, sid = k.x.c.t.pm, k.qa, k.analyst, s["id"]
    assert _vfinding(client, v1, sid, category="CRITICAL").status_code == 422
    assert _vfinding(client, v1, sid, severity="HIGH").status_code == 422
    assert _vfinding(client, v1, sid, target_type="INPUT").json()["error_code"] == "TARGET_NOT_IN_PACKAGE"
    assert _vfinding(client, v1, sid, target_type="INPUT", target_ref="999").json()["error_code"] == "TARGET_NOT_IN_PACKAGE"
    assert _vfinding(client, v1, sid, target_type="LAB_RESULT", target_ref=str(uuid.uuid4())).json()["error_code"] == "TARGET_NOT_IN_PACKAGE"
    assert _vfinding(client, pm, sid).status_code == 403                                     # the project never raises VVB findings
    f = _vfinding(client, v1, sid, target_type="INPUT", target_ref="1", category="CALCULATION_ISSUE").json()
    assert f["status"] == "OPEN" and f["finding_code"].startswith("VFND-") and f["category_label"] == "Calculation Issue" and f["blocking"]
    fid = f["id"]
    # the project responds (verification.respond), with PDF evidence attached to the submission
    assert client.post(f"{V}/findings/{fid}/respond", headers=qa.headers, json={"response": "QA reads only"}).status_code == 403
    bad = client.post(f"{V}/submissions/{sid}/evidence", headers=an.headers, files={"file": ("e.png", b"\x89PNG\r\n\x1a\n" + b"0" * 64, "image/png")})
    assert bad.status_code == 422
    ev = client.post(f"{V}/submissions/{sid}/evidence", headers=an.headers, files={"file": ("e.pdf", PDF, "application/pdf")},
                     data={"title": "TEST evidence"})
    assert ev.status_code == 201, ev.text
    r = client.post(f"{V}/findings/{fid}/respond", headers=an.headers, json={"response": "TEST: input verified", "document_id":
                                                                              ev.json()["document_id"]}).json()
    assert r["status"] == "RESPONDED" and r["response_document_id"] == ev.json()["document_id"]
    # the project never closes a VVB finding
    assert client.post(f"{V}/findings/{fid}/close", headers=pm.headers, json={"note": "closing"}).status_code in (404, 405)
    assert client.post(f"{VVB}/findings/{fid}/close", headers=pm.headers, json={"note": "closing"}).status_code == 403
    # the VVB may read the response evidence (attached to the submission)
    vdocs = {d["document_id"]: d for d in client.get(f"{VVB}/submissions/{sid}/documents", headers=v1.headers).json()}
    assert vdocs[ev.json()["document_id"]]["source"] == "SUBMISSION"
    assert client.get(f"{VVB}/submissions/{sid}/documents/{ev.json()['document_id']}", headers=v1.headers).status_code == 200
    # documents attached to a submission are immutable: no new version through the generic documents API (either side)
    for who in (an, v1):
        r = client.post(f"/api/v1/evidence/documents/{ev.json()['document_id']}/versions", headers=who.headers,
                        files={"file": ("e2.pdf", PDF + b"%changed", "application/pdf")})
        assert r.status_code == 403 and r.json()["error_code"] == "DOCUMENT_IMMUTABLE", r.text
    # return → OPEN, respond, close; reopen needs a reason
    assert client.post(f"{VVB}/findings/{fid}/return", headers=v1.headers, json={"reason": "TEST: not enough"}).json()["status"] == "OPEN"
    client.post(f"{V}/findings/{fid}/respond", headers=an.headers, json={"response": "TEST: more detail"})
    # corrective action: request → respond → reject → respond → accept; overdue is derived
    ca = client.post(f"{VVB}/findings/{fid}/corrective-actions", headers=v1.headers,
                     json={"description": "TEST: provide the field sheet", "due_date": "2020-01-01"}).json()
    assert ca["status"] == "REQUESTED" and ca["overdue"] is True and ca["action_code"].startswith("CAR-")
    assert client.post(f"{VVB}/findings/{fid}/close", headers=v1.headers, json={"note": "done"}).json()["error_code"] == "OPEN_CORRECTIVE_ACTIONS"
    assert client.post(f"{V}/corrective-actions/{ca['id']}/respond", headers=an.headers, json={"response": "TEST: sheet attached"}).json()[
        "status"] == "RESPONDED"
    rj = client.post(f"{VVB}/corrective-actions/{ca['id']}/reject", headers=v1.headers, json={"note": "TEST: illegible"}).json()
    assert rj["status"] == "REQUESTED" and [e["action"] for e in rj["events"]] == ["REQUESTED", "RESPONDED", "REJECTED"]
    client.post(f"{V}/corrective-actions/{ca['id']}/respond", headers=an.headers, json={"response": "TEST: clear copy"})
    acc = client.post(f"{VVB}/corrective-actions/{ca['id']}/accept", headers=v1.headers, json={"note": "TEST: fine"}).json()
    assert acc["status"] == "ACCEPTED" and acc["overdue"] is False and acc["responded_by_name"] == "Project team"
    assert client.post(f"{VVB}/corrective-actions/{ca['id']}/cancel", headers=v1.headers, json={"reason": "late"}).json()["error_code"] == \
        "CORRECTIVE_ACTION_CLOSED"
    ca2 = client.post(f"{VVB}/findings/{fid}/corrective-actions", headers=v1.headers, json={"description": "TEST: optional extra"}).json()
    assert client.post(f"{VVB}/corrective-actions/{ca2['id']}/cancel", headers=v1.headers, json={"reason": "TEST: not needed"}).json()[
        "status"] == "CANCELLED"
    c = client.post(f"{VVB}/findings/{fid}/close", headers=v1.headers, json={"note": "TEST: resolved"}).json()
    assert c["status"] == "CLOSED"
    assert client.post(f"{VVB}/findings/{fid}/reopen", headers=v1.headers, json={}).status_code == 422
    ro = client.post(f"{VVB}/findings/{fid}/reopen", headers=v1.headers, json={"reason": "TEST: new doubt"}).json()
    assert ro["status"] == "OPEN"
    assert [e["action"] for e in ro["events"]] == ["RAISED", "RESPONDED", "RETURNED", "RESPONDED", "CLOSED", "REOPENED"]
    assert {e["actor_side"] for e in ro["events"]} == {"VVB", "PROJECT"}
    # project side sees names; VVB side sees "Project team" for project people
    proj = client.get(f"{V}/submissions/{sid}/findings", headers=qa.headers).json()[0]
    assert proj["responded_by_name"] == "Test User" and ro["responded_by_name"] == "Project team"
    for action in ("VERIFICATION_FINDING_RAISED", "VERIFICATION_FINDING_RESPONDED", "VERIFICATION_FINDING_RETURNED", "VERIFICATION_FINDING_CLOSED",
                   "VERIFICATION_FINDING_REOPENED", "CORRECTIVE_ACTION_REQUESTED", "CORRECTIVE_ACTION_RESPONDED", "CORRECTIVE_ACTION_REJECTED",
                   "CORRECTIVE_ACTION_ACCEPTED", "CORRECTIVE_ACTION_CANCELLED", "VERIFICATION_EVIDENCE_UPLOADED"):
        assert {r.organization_id for r in _audit(db, action)} >= {k.x.c.t.org.id, org.id}, action


# ---------------------------------------------------------------- decision (C15–C18), aggregate status, lineage
def test_decision_report_sod_quantity_status_lineage_and_supersession(client: TestClient, db: Session) -> None:
    k = calc_scenario(db, client, 79.50, 24.50, "9150 2000 3000")
    a, s, org, v1, v2, run = _submitted(client, db, k)
    pm, sid = k.x.c.t.pm, s["id"]
    op = client.post("/api/v1/mrv/monitoring-periods", headers=k.x.c.mrv.headers, json={
        "project_id": k.project_id, "name": "Monitoring 2", "start_date": "2030-06-01", "end_date": "2031-05-31"}).json()
    later = _propose(client, k, org, period_id=op["id"]).json()                                   # period 2: tracked on its own
    f = _vfinding(client, v1, sid).json()
    # C18: whoever raised a finding on this submission never decides; open findings block the decision
    r = _decide(client, v1, sid)
    assert r.status_code == 403 and r.json()["error_code"] == "SEPARATION_OF_DUTIES"
    assert _decide(client, v2, sid).json()["error_code"] == "OPEN_VERIFICATION_FINDINGS"
    v2view = client.get(f"{VVB}/assignments/{a['id']}", headers=v2.headers).json()
    assert "decide" not in v2view["actions"] and v2view["decision_blockers"]
    client.post(f"{V}/findings/{f['id']}/respond", headers=k.analyst.headers, json={"response": "TEST: evidence provided"})
    ca = client.post(f"{VVB}/findings/{f['id']}/corrective-actions", headers=v1.headers, json={"description": "TEST: one more item"}).json()
    assert _decide(client, v2, sid).json()["error_code"] in ("OPEN_VERIFICATION_FINDINGS", "OPEN_CORRECTIVE_ACTIONS")
    client.post(f"{VVB}/corrective-actions/{ca['id']}/cancel", headers=v1.headers, json={"reason": "TEST: not needed"})
    client.post(f"{VVB}/findings/{f['id']}/close", headers=v1.headers, json={"note": "TEST: resolved"})
    assert _decide(client, v1, sid).json()["error_code"] == "SEPARATION_OF_DUTIES"           # still the raiser
    # C15: the VVB report PDF is required; outcome and quantity rules (C16)
    assert _decide(client, v2, sid, file=None).status_code == 422
    assert _decide(client, v2, sid, file=("r.png", b"\x89PNG\r\n\x1a\n" + b"0" * 64, "image/png")).status_code == 422
    assert _decide(client, v2, sid, outcome="ISSUED").json()["error_code"] == "INVALID_OUTCOME"
    assert _decide(client, v2, sid, verified_quantity="12.5").json()["error_code"] == "QUANTITY_UNIT_REQUIRED"
    assert _decide(client, v2, sid, verified_quantity_unit="tCO2e").json()["error_code"] == "QUANTITY_UNIT_REQUIRED"
    assert _decide(client, v2, sid, verified_quantity="abc", verified_quantity_unit="tCO2e").json()["error_code"] == "INVALID_QUANTITY"
    assert _decide(client, v2, sid, verified_quantity="-1", verified_quantity_unit="tCO2e").json()["error_code"] == "INVALID_QUANTITY"
    assert _decide(client, v2, sid, outcome="NOT_VERIFIED", verified_quantity="1", verified_quantity_unit="tCO2e").json()["error_code"] == \
        "QUANTITY_NOT_ALLOWED"
    assert _decide(client, pm, sid).status_code == 403                                        # the project never records a decision
    d = _decide(client, v2, sid, verified_quantity="12.5000", verified_quantity_unit="tCO2e")
    assert d.status_code == 201, d.text
    dj = d.json()
    assert dj["outcome"] == "VERIFIED" and dj["decision_code"].startswith("VDEC-") and dj["status"] == "CURRENT"
    assert dj["verified_quantity"] == "12.5" and dj["verified_quantity_label"] == "VVB-stated verified quantity"
    assert dj["manifest_sha256"] == s["manifest_sha256"] and dj["report_sha256"] and dj["vvb_organization_id"] == str(org.id)
    for forbidden in ("credit", "serial", "issuance", "registry", "retire"):
        assert not any(forbidden in key for key in dj), forbidden
    # the calculated quantity is untouched and labelled separately
    view = client.get(f"{V}/projects/{k.project_id}/periods/{k.period_id}", headers=k.qa.headers).json()
    assert view["calculated_value"] == run.net_result and view["current_decision"]["id"] == dj["id"]
    assert view["assignments"][0]["status"] == "COMPLETED"
    assert _project(db, k).status == "VERIFIED"                                                  # C2: first VERIFIED period
    p2 = client.get(f"{V}/projects/{k.project_id}/periods/{op['id']}", headers=k.qa.headers).json()
    assert p2["current_decision"] is None and [x["id"] for x in p2["assignments"]] == [later["id"]]
    assert p2["assignments"][0]["status"] == "PROPOSED"                                            # later period stays independent
    assert _decide(client, v2, sid).json()["error_code"] == "ASSIGNMENT_NOT_ACCEPTED"           # one decision; immutable
    for who in (pm, v2):
        prefix = V if who is pm else VVB
        rep = client.get(f"{prefix}/decisions/{dj['id']}/report", headers=who.headers)
        assert rep.status_code == 200 and rep.content == PDF
    other_org, other_vvb, _ = _vvb(db, client)
    assert client.get(f"{VVB}/decisions/{dj['id']}/report", headers=other_vvb.headers).status_code == 404
    # lineage: decision → assignment → submission → readiness → manifest → report → run → … → project
    lin = client.get(f"{V}/decisions/{dj['id']}/lineage", headers=k.qa.headers).json()
    assert [c["kind"] for c in lin["chain"]] == ["VERIFICATION_DECISION", "VVB_ORGANIZATION", "VERIFICATION_ASSIGNMENT", "VERIFICATION_SUBMISSION",
                                                 "READINESS_REVIEW", "MANIFEST", "CALCULATION_REPORT", "CALCULATION_RUN", "METHODOLOGY_VERSION",
                                                 "MRV_DATASET", "MONITORING_PERIOD", "PROJECT"]
    assert lin["chain"][5]["matches_decision"] is True and lin["chain"][7]["id"] == str(run.id)
    cl = lin["calculation_lineage"]
    assert cl["run"]["id"] == str(run.id) and cl["inputs"]                                       # → inputs → lab results → samples → … → farms
    assert {r.organization_id for r in _audit(db, "VERIFICATION_DECISION_RECORDED")} == {k.x.c.t.org.id, org.id}
    # a recalculation after the decision: submission INVALIDATED, the decision SUPERSEDED (kept, not edited); project stays VERIFIED
    _recalc(db, k, run)
    view = client.get(f"{V}/projects/{k.project_id}/periods/{k.period_id}", headers=k.qa.headers).json()
    assert view["current_decision"] is None
    dec = db.get(VerificationDecision, uuid.UUID(dj["id"]))
    assert dec is not None
    db.refresh(dec)
    assert dec.status == "SUPERSEDED" and dec.superseded_reason and dec.outcome == "VERIFIED" and dec.verified_quantity is not None
    assert _project(db, k).status == "VERIFIED"
    assert _audit(db, "VERIFICATION_DECISION_SUPERSEDED")


def test_not_verified_decision_keeps_project_in_verification(client: TestClient, db: Session) -> None:
    k = calc_scenario(db, client, 79.60, 24.60, "9160 2000 3000")
    a, s, org, v1, _, _ = _submitted(client, db, k)
    d = _decide(client, v1, s["id"], outcome="NOT_VERIFIED", rationale="TEST: the VVB could not verify")
    assert d.status_code == 201 and d.json()["outcome"] == "NOT_VERIFIED" and d.json()["verified_quantity"] is None
    assert _project(db, k).status == "VERIFICATION"
    assert db.get(VerificationAssignment, uuid.UUID(a["id"])).status == "COMPLETED"  # type: ignore[union-attr]


# ---------------------------------------------------------------- isolation (C8, cross-organization checks)
def test_cross_organization_isolation_and_rbac(client: TestClient, db: Session) -> None:
    k = calc_scenario(db, client, 79.70, 24.70, "9170 2000 3000")
    a, s, org, v1, _, _ = _submitted(client, db, k)
    sid = s["id"]
    other_org, stranger, _ = _vvb(db, client)
    for url in (f"{VVB}/assignments/{a['id']}", f"{VVB}/submissions/{sid}/package", f"{VVB}/submissions/{sid}/findings",
                f"{VVB}/submissions/{sid}/documents"):
        assert client.get(url, headers=stranger.headers).status_code == 404, url
    assert client.get(f"{VVB}/assignments", headers=stranger.headers).json() == []
    assert _vfinding(client, stranger, sid).status_code == 404
    # a project user of another organization sees nothing; a VVB user gets no project-side API
    other_pm = staff(db, client, make_org(db), "PROJECT_MANAGER")
    assert client.get(f"{V}/assignments/{a['id']}", headers=other_pm.headers).status_code == 404
    assert client.get(f"{V}/projects/{k.project_id}/assignments", headers=other_pm.headers).status_code == 404
    assert client.get(f"{V}/assignments/{a['id']}", headers=v1.headers).status_code == 403
    assert client.get(f"{VVB}/assignments", headers=k.x.c.t.pm.headers).status_code == 403
    farmerless = staff(db, client, k.x.c.t.org, "FIELD_AGENT")
    assert client.get(f"{V}/projects/{k.project_id}/assignments", headers=farmerless.headers).status_code == 403
    # a VVB user who is also a member of another VVB cannot use it to reach this assignment; a SUSPENDED VVB loses access
    org.status = "SUSPENDED"
    db.flush()
    assert client.get(f"{VVB}/assignments/{a['id']}", headers=v1.headers).status_code == 404
    assert client.get(f"{VVB}/submissions/{sid}/package", headers=v1.headers).status_code == 404
    assert client.get(f"{VVB}/assignments", headers=v1.headers).json() == []
    org.status = "ACTIVE"
    db.flush()
    assert client.get(f"{VVB}/submissions/{sid}/package", headers=v1.headers).status_code == 200


def test_no_validation_registry_or_issuance_surface_exists() -> None:
    from app.main import app
    paths = [r.path for r in app.routes if hasattr(r, "path")]
    v = [p for p in paths if p.startswith(("/api/v1/verification", "/api/v1/vvb"))]
    assert len(v) >= 30
    segments = {seg for p in paths for seg in p.split("/")}
    # registry submission and issuance arrive in Phase 9A under their own prefixes (/registry, /credits), retirement in Phase 9B under
    # /credits only and the marketplace in Phase 10 under /marketplace only; validation, buffer and payout endpoints still do not exist, and
    # the verification APIs never register or issue
    for word in ("validation", "validations", "buffer", "payouts"):
        assert word not in segments, word
    assert all(p.startswith("/api/v1/marketplace") for p in paths if "marketplace" in p.split("/"))
    assert all(p.startswith("/api/v1/credits/") for p in paths if "retirements" in p.split("/"))
    for p in v:
        assert not any(w in p for w in ("registry", "issu", "credit", "serial", "retire", "valid", "buffer", "payout")), p


# ---------------------------------------------------------------- DEMO (C20)
def test_demo_niphad_assignment_and_coi_only_submission_blocked(client: TestClient, db: Session) -> None:
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
    p = db.scalars(select(Project).where(Project.environment == "DEMO", Project.name.like("Niphad%"))).one()
    mp = db.scalars(select(MonitoringPeriod).where(MonitoringPeriod.project_id == p.id)).first()
    assert mp is not None
    # no verification data is seeded (no fake assignment, submission, decision, report or quantity)
    from app.models import VerificationSubmission
    assert db.scalars(select(VerificationAssignment).where(VerificationAssignment.environment == "DEMO")).first() is None
    assert db.scalars(select(VerificationSubmission)).first() is None and db.scalars(select(VerificationDecision)).first() is None
    dev = db.scalars(select(Organization).where(Organization.code == "DEMO-DEV-A")).one()
    vorg = db.scalars(select(Organization).where(Organization.code == "DEMO-VVB-C")).one()
    assert vorg.org_type == "VVB" and vorg.environment == "DEMO"
    pm = login(client, make_user(db, roles=[("PROJECT_MANAGER", dev)], environment="DEMO"))
    vvb = login(client, make_user(db, roles=[("VVB_REVIEWER", vorg)], environment="DEMO"))
    live_vvb = make_org(db, org_type="VVB")
    url = f"{V}/projects/{p.id}/assignments"
    assert client.post(url, headers=pm, json={"monitoring_period_id": str(mp.id), "vvb_organization_id": str(live_vvb.id)}).json()[
        "error_code"] == "NOT_A_VVB"                                                            # DEMO never mixes with LIVE
    a = client.post(url, headers=pm, json={"monitoring_period_id": str(mp.id), "vvb_organization_id": str(vorg.id)}).json()
    assert a["status"] == "PROPOSED" and a["environment"] == "DEMO"
    acc = client.post(f"{VVB}/assignments/{a['id']}/accept", headers=vvb, json={"coi_declaration": COI}).json()
    assert acc["status"] == "ACCEPTED"
    r = client.post(f"{V}/assignments/{a['id']}/submit", headers=pm)
    assert r.status_code == 409 and r.json()["error_code"] == "NO_READY_PACKAGE"                 # Niphad is not READY
    db.refresh(p)
    assert p.status == "MONITORING"                                                               # no fake aggregate status
    assert db.scalars(select(VerificationDecision).where(VerificationDecision.project_id == p.id)).first() is None


# ---------------------------------------------------------------- database triggers
def test_triggers_protect_assignments_submissions_and_decisions() -> None:
    def build(session: Session, client: TestClient) -> tuple[str, dict, str]:
        k = calc_scenario(session, client, 79.80, 24.80, "9180 2000 3000")
        org, v1, _ = _vvb(session, client)
        a = _accepted(client, k, org, v1)
        return "UPDATE verification_assignments SET coi_declaration = N'rewritten' WHERE id = :i", {"i": a["id"]}, "immutable"
    _dedicated(build)

    def build2(session: Session, client: TestClient) -> tuple[str, dict, str]:
        k = calc_scenario(session, client, 79.85, 24.85, "9185 2000 3000")
        _, s, _, _, _, _ = _submitted(client, session, k)
        return "UPDATE verification_submissions SET manifest_sha256 = N'0' WHERE id = :i", {"i": s["id"]}, "never mutated"
    _dedicated(build2)

    def build3(session: Session, client: TestClient) -> tuple[str, dict, str]:
        k = calc_scenario(session, client, 79.90, 24.90, "9190 2000 3000")
        _, s, _, v1, _, _ = _submitted(client, session, k)
        d = _decide(client, v1, s["id"]).json()
        return "UPDATE verification_decisions SET outcome = N'NOT_VERIFIED' WHERE id = :i", {"i": d["id"]}, "immutable"
    _dedicated(build3)

    def build4(session: Session, client: TestClient) -> tuple[str, dict, str]:
        k = calc_scenario(session, client, 79.95, 24.95, "9195 2000 3000")
        _, s, _, v1, _, _ = _submitted(client, session, k)
        f = _vfinding(client, v1, s["id"]).json()
        return "UPDATE verification_findings SET description = N'rewritten' WHERE id = :i", {"i": f["id"]}, "immutable"
    _dedicated(build4)


def test_event_tables_are_append_only() -> None:
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from app.core.database import get_engine
    for table in ("verification_finding_events", "corrective_action_events"):
        with get_engine().connect() as c:
            t = c.begin()
            try:
                c.execute(text(f"DELETE FROM {table} WHERE 1 = 0"))
                raise AssertionError(f"{table} accepted a delete")
            except DBAPIError as e:
                assert "append-only" in str(e)
            finally:
                if t.is_active:
                    t.rollback()
