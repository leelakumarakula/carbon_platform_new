"""Fixes from the 29 Oct 2026 pipeline review:
1  a CLOSED project's MRV / laboratory / calculation history stays readable, every write is refused (PROJECT_CLOSED)
2  an APPROVED period whose calculation was approved cannot be re-opened by a new dataset version (PERIOD_LOCKED)
3  the QA reviewer of a dataset / calculation run never approves it (SEPARATION_OF_DUTIES)
4  catalog management needs a PLATFORM-scope grant in the caller's environment
5  a version locked by an open project cannot be retired (VERSION_IN_USE)
6  production readiness holds only for the module code version it was approved for (+ 13: the version must still be APPROVED)
7  long exact output values are stored (calculation_outputs.value widened)
8  duplicate inputs block the freeze (DUPLICATE_INPUT); 9 double counting is re-checked at calculation (DOUBLE_COUNTING_CONFLICT)
10 CONFIRMED_CONFLICT overlaps block eligibility; farm verification re-detects overlaps
11 a control-site farm is locked while its project runs; 12 farmer status changes are staff-only
13 a lab report cannot be replaced once the result is submitted; 14 a refused upload does not commit the caller's work
Successful calculation paths use the TEST-only Phase 7 fixture module, handed to the service layer (never registered)."""
import uuid
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calculation import registry
from app.calculation.framework import Output
from app.core.context import RequestContext
from app.core.errors import Conflict, PermissionDenied, ValidationFailed
from app.integrations.malware import ScanResult
from app.models import (
    CalculationOutput,
    CalculationRun,
    FarmOverlapCheck,
    MethodologyVersion,
    Project,
    ProjectStratum,
    SecurityEvent,
    Standard,
    StratumFarm,
)
from app.schemas.calculation import RunIn
from app.services import calculation_inputs as ci
from app.services import calculation_service as cs
from app.services import document_service
from app.services import methodology_service as msvc
from app.services import project_farm_service as pfs
from tests.calc_fixture import CALC, CalcCtx, as_principal, calc_scenario, fixture_module, resolver_for
from tests.conftest import Actor, login, make_org, make_user
from tests.phase2 import add_owner, create_farm, set_boundary, square, staff
from tests.phase3 import PR, active_farmer, add_farm, catalog, create_project, team, verified_farm
from tests.phase4 import M, approved_version, methodology, specialists
from tests.phase5 import MRV, SIZE, locked_project
from tests.phase6 import LAB, LABV, PDF, enter_result, lab_project, to_lab

FA = "/api/v1/farms"
F = "/api/v1/farmers"


def _reason(text: str) -> dict:
    return {"reason": text}


def _approve_dataset(client: TestClient, k: CalcCtx, signer: Actor) -> dict:
    """Submit (MRV manager), QA (QA officer), approve (a second QA officer: the reviewer may not approve)."""
    c = k.x.c
    ds = client.post(f"{MRV}/datasets", headers=c.mrv.headers, json={"monitoring_period_id": k.period_id}).json()
    assert client.post(f"{MRV}/datasets/{ds['id']}/submit", headers=c.mrv.headers, json=_reason("collection complete")).status_code == 200
    assert client.post(f"{MRV}/qa/{ds['id']}/start", headers=c.t.qa.headers).status_code == 200
    r = client.post(f"{MRV}/qa/{ds['id']}/complete", headers=c.t.qa.headers, json={"result": "PASS", "notes": "all checks pass"})
    assert r.status_code == 200, r.text
    r = client.post(f"{MRV}/datasets/{ds['id']}/approve", headers=c.t.qa.headers, json=_reason("my own review"))
    assert r.status_code == 403 and r.json()["error_code"] == "SEPARATION_OF_DUTIES", r.text
    r = client.post(f"{MRV}/datasets/{ds['id']}/approve", headers=signer.headers, json=_reason("dataset approved"))
    assert r.status_code == 200, r.text
    return r.json()


def _calculated_run(db: Session, k: CalcCtx, resolver: Any) -> CalculationRun:
    a, actx = as_principal(db, k.analyst)
    run = cs.create_run(db, actx, a, RunIn(project_id=uuid.UUID(k.project_id), monitoring_period_id=uuid.UUID(k.period_id)))
    run = cs.freeze(db, actx, a, run.id, resolver=resolver)
    return cs.execute(db, actx, a, run.id, resolver=resolver)


# ---------------------------------------------------------------- 1, 2, 3, 7, 9
def test_closed_project_history_readable_and_read_only(client: TestClient, db: Session) -> None:
    k = calc_scenario(db, client, 79.10, 25.10, "2910 2000 3000", approve_ds=False)
    c = k.x.c
    pid = k.project_id
    signer = staff(db, client, c.t.org, "QA_OFFICER")
    _approve_dataset(client, k, signer)
    a, actx = as_principal(db, k.analyst)
    q, qctx = as_principal(db, k.qa)
    s, sctx = as_principal(db, signer)

    # 9: the project farm also enrolled in another project (enrolment only acknowledged) blocks the calculation even in MONITORING
    other = create_project(client, c.t, name="Second project on the same land")
    assert client.post(f"{PR}/{other['id']}/start-data-collection", headers=c.t.pm.headers, json=_reason("collect")).status_code == 200
    farm = c.farms[0]
    assert add_farm(client, c.t, other["id"], farm["id"], acknowledge_conflicts=True, conflict_notes="to be assessed").status_code == 201
    ev = cs.readiness(db, a, uuid.UUID(pid), uuid.UUID(k.period_id), resolver=k.resolver)
    dc = [b for b in ev.blockers if b.code == "DOUBLE_COUNTING_CONFLICT"]
    assert dc and dc[0].details["conflicts"][0]["other_project_code"] == other["project_code"]
    r = client.request("DELETE", f"{PR}/{other['id']}/farms/{farm['id']}", headers=c.t.pm.headers, json=_reason("enrolled elsewhere"))
    assert r.status_code == 200, r.text
    assert cs.readiness(db, a, uuid.UUID(pid), uuid.UUID(k.period_id), resolver=k.resolver).blockers == []

    # 3: the run's QA reviewer may not approve it; a second QA officer does
    run = cs.submit(db, actx, a, _calculated_run(db, k, k.resolver).id)
    cs.start_qa(db, qctx, q, run.id)
    cs.complete_qa(db, qctx, q, run.id, "PASS", "TEST checks pass", resolver=k.resolver)
    with pytest.raises(PermissionDenied) as e:
        cs.approve(db, qctx, q, run.id, "my own review")
    assert e.value.error_code == "SEPARATION_OF_DUTIES"
    run = cs.approve(db, sctx, s, run.id, "TEST approved by a second officer")
    assert run.status == "APPROVED"

    # 2: the approved calculation locks the period: no correction by a new dataset version
    r = client.post(f"{MRV}/datasets", headers=c.mrv.headers, json={"monitoring_period_id": k.period_id})
    assert r.status_code == 409 and r.json()["error_code"] == "PERIOD_LOCKED", r.text
    assert r.json()["details"]["calculation_runs"] == [run.run_code]

    # 7: an exact output far below 1 (1E-60 scale, 34 digits) is longer than 80 characters and is stored as computed
    def tiny_leakage(self: Any, ctx: Any) -> list[Output]:
        return [Output("T_QUARTER", "LEAKAGE", "TC5", ctx.output("T_SUM").value * Decimal("1E-60") / Decimal(7), "TEST", outputs=("T_SUM",))]
    tiny = fixture_module(db, c.version_id, calculate_leakage=tiny_leakage)
    run2 = _calculated_run(db, k, resolver_for(tiny))
    assert run2.status == "CALCULATED"
    db.expire_all()
    values = {o.output_code: o.value for o in db.scalars(select(CalculationOutput).where(CalculationOutput.run_id == run2.id)).all()}
    assert len(values["T_QUARTER"]) > 80 and Decimal(values["T_QUARTER"]) < Decimal("1E-59")

    # 1: close the project; the whole history stays readable ...
    assert client.post(f"{PR}/{pid}/close", headers=c.t.pm.headers, json=_reason("crediting ended")).json()["status"] == "CLOSED"
    h = c.mrv.headers
    for url, params in ((f"{MRV}/projects/{pid}/requirements", {}), (f"{MRV}/plans", {"project_id": pid}),
                        (f"{MRV}/monitoring-periods", {"project_id": pid}), (f"{MRV}/projects/{pid}/strata", {}),
                        (f"{MRV}/datasets", {"project_id": pid}), (f"{MRV}/sampling-points", {"project_id": pid}),
                        (f"{LAB}/projects/{pid}/laboratory-rules", {}), (f"{LAB}/results", {"project_id": pid, "status": "ALL"}),
                        (f"{LAB}/samples", {"project_id": pid})):
        r = client.get(url, headers=h, params=params)
        assert r.status_code == 200, (url, r.text)
    assert client.get(f"{LAB}/results", headers=h, params={"project_id": pid}).json()
    ah = k.analyst.headers
    assert pid in {p["id"] for p in client.get(f"{CALC}/projects", headers=ah).json()}
    assert {x["id"] for x in client.get(f"{CALC}/runs", headers=ah, params={"project_id": pid}).json()} >= {str(run.id), str(run2.id)}
    for url in (f"{CALC}/runs/{run.id}", f"{CALC}/runs/{run.id}/inputs", f"{CALC}/runs/{run.id}/outputs", f"{CALC}/qa/{run.id}"):
        assert client.get(url, headers=ah).status_code == 200, url
    # ... and every write is refused
    refused = [client.post(f"{MRV}/monitoring-periods", headers=h, json={"project_id": pid, "name": "Later", "purpose": "MONITORING",
                                                                      "start_date": "2030-01-01", "end_date": "2030-12-31"}),
               client.post(f"{MRV}/datasets", headers=h, json={"monitoring_period_id": k.period_id}),
               client.post(f"{CALC}/runs", headers=ah, json={"project_id": pid, "monitoring_period_id": k.period_id}),
               client.post(f"{MRV}/field-collections", headers=c.collector.headers, json={"sampling_point_id": k.x.points[0]["id"]})]
    for r in refused:
        assert r.status_code == 409 and r.json()["error_code"] == "PROJECT_CLOSED", r.text
    with pytest.raises(Conflict) as e2:
        cs.submit(db, actx, a, run2.id)
    assert e2.value.error_code == "PROJECT_CLOSED"


# ---------------------------------------------------------------- 4, 5, 6, 13
def test_catalog_management_is_platform_scoped_and_in_environment(client: TestClient, db: Session) -> None:
    cat = catalog(db)
    author, approver = specialists(db, client)
    org = make_org(db)
    scoped = make_user(db, roles=[("METHODOLOGY_SPECIALIST", org)])           # an organization-scoped grant of the same role
    sh = login(client, scoped)
    body = {"code": f"ORG-{cat['s1'].code[-6:]}", "name": "Org methodology", "standard_id": str(cat["s1"].id),
            "activity_ids": [str(cat["a1"].id)]}
    assert client.post(M, headers=sh, json=body).status_code == 403
    m = methodology(client, author, str(cat["s1"].id), [str(cat["a1"].id)], f"PLT-{cat['s1'].code[-6:]}")
    v = client.post(f"{M}/{m['id']}/versions", headers=author.headers,
                    json={"version_label": "1.0", "effective_from": "2020-01-01", "source_name": "TEST source"}).json()
    client.post(f"{M}/versions/{v['id']}/rules/applicability", headers=author.headers, json={
        "rule_code": "A1", "title": "Country", "category": "COUNTRY", "fact_key": "country", "operator": "IN", "expected_value": ["IN"]})
    assert client.post(f"{M}/versions/{v['id']}/submit", headers=author.headers, json=_reason("ready")).status_code == 200
    r = client.post(f"{M}/versions/{v['id']}/approve", headers=sh, json=_reason("org-scoped approval"))
    assert r.status_code == 403, r.text
    # a DEMO platform specialist does not approve a LIVE catalog entry
    demo = make_user(db, roles=[("METHODOLOGY_SPECIALIST", None)], environment="DEMO")
    r = client.post(f"{M}/versions/{v['id']}/approve", headers=login(client, demo), json=_reason("other environment"))
    assert r.status_code == 403 and r.json()["error_code"] == "ENVIRONMENT_MISMATCH", r.text
    assert client.post(f"{M}/versions/{v['id']}/approve", headers=approver.headers, json=_reason("checked")).status_code == 200
    assert db.scalars(select(Standard).where(Standard.id == cat["s1"].id)).one()


def test_locked_version_cannot_be_retired_while_project_open(client: TestClient, db: Session) -> None:
    c = locked_project(db, client, 79.20, 25.20, "2920 2000 3000", n_farms=1)
    manager = make_user(db, roles=[("METHODOLOGY_SPECIALIST", None)])
    mh = login(client, manager)
    r = client.post(f"{M}/versions/{c.version_id}/retire", headers=mh, json=_reason("replaced by a newer version"))
    assert r.status_code == 409 and r.json()["error_code"] == "VERSION_IN_USE", r.text
    assert r.json()["details"]["projects"][0]["project_code"] == c.project["project_code"]
    assert client.post(f"{PR}/{c.project['id']}/close", headers=c.t.pm.headers, json=_reason("project abandoned")).status_code == 200
    assert client.post(f"{M}/versions/{c.version_id}/retire", headers=mh, json=_reason("replaced")).json()["status"] == "RETIRED"
    # the CLOSED project's requirements remain readable although its locked version is retired now
    assert client.get(f"{MRV}/projects/{c.project['id']}/requirements", headers=c.mrv.headers).status_code == 200


def test_production_readiness_is_bound_to_the_module_code_version(client: TestClient, db: Session) -> None:
    mod = registry.by_code("VM0042-V2.2-QA2-QA3")
    assert mod is not None and mod.calculation_rules_version == 0
    assert registry.bind(mod, 3, "PRODUCTION_READY", mod.version).readiness == "PRODUCTION_READY"          # type: ignore[union-attr]
    for recorded in (None, "0.0.1"):   # an approval for other module code, or one recorded before 0024: not ready
        assert registry.bind(mod, 3, "PRODUCTION_READY", recorded).readiness == "NOT_PRODUCTION_READY"     # type: ignore[union-attr]
    cat = catalog(db)
    author, approver = specialists(db, client)
    m = methodology(client, author, str(cat["s1"].id), [str(cat["a1"].id)], f"RDY-{cat['s1'].code[-6:]}")
    rule = {"rule_code": "A1", "title": "Country", "category": "COUNTRY", "fact_key": "country", "operator": "IN", "expected_value": ["IN"]}
    v = approved_version(client, author, approver, m["id"], "1.0", [rule])
    mv = db.get(MethodologyVersion, uuid.UUID(v["id"]))
    assert mv is not None
    mv.calculation_module_code = mod.code      # (the Calculation tab is only usable on drafts of the module's own methodology)
    db.flush()
    url = f"{M}/versions/{v['id']}/calculation-readiness"
    assert client.post(f"{url}/request", headers=author.headers, json=_reason("Equations reviewed; worked examples pass")).status_code == 200
    r = client.post(f"{url}/decide", headers=approver.headers, json={"approve": True, "reason": "verified"})
    assert r.status_code == 200 and r.json()["calculation_readiness"] == "PRODUCTION_READY", r.text
    db.expire_all()
    mv = db.get(MethodologyVersion, uuid.UUID(v["id"]))
    assert mv is not None and mv.calculation_readiness_module_version == mod.version and msvc.readiness_current(mv)
    # the module code changes (1.2.0 -> a later version): the old approval no longer holds and a new request is accepted
    mv.calculation_readiness_module_version = "0.0.1"
    db.flush()
    assert not msvc.readiness_current(mv)
    assert client.post(f"{url}/request", headers=author.headers, json=_reason("Module code changed; re-reviewed")).status_code == 200
    # 13: the version was retired meanwhile -> the open request cannot be approved
    assert client.post(f"{M}/versions/{v['id']}/retire", headers=author.headers, json=_reason("withdrawn by the standard")).status_code == 200
    r = client.post(f"{url}/decide", headers=approver.headers, json={"approve": True, "reason": "verified"})
    assert r.status_code == 409 and r.json()["error_code"] == "READINESS_NOT_APPLICABLE", r.text


# ---------------------------------------------------------------- 8 (pure)
def test_duplicate_lab_inputs_block_the_freeze() -> None:
    def row(source_id: str, root: str, fc: str = "fc-1", top: str = "0", bottom: str = "30") -> dict:
        return {"variable": "OC_T", "source_type": "LAB_RESULT", "source_id": source_id, "source_code": f"S-{source_id}", "root_sample_id": root,
                "field_collection_id": fc, "context": {"depth_top_cm": top, "depth_bottom_cm": bottom}}
    assert ci.duplicate_blockers([row("a", "r1"), row("b", "r2", top="30", bottom="60"), row("c", "r3", fc="fc-2")]) == []
    # two root samples analysed for the same core and depth (the module would silently keep one of them)
    b = ci.duplicate_blockers([row("a", "r1"), row("b", "r2")])
    assert [x.code for x in b] == ["DUPLICATE_INPUT"] and "fc-1" in b[0].details["duplicates"][0]
    assert ci.duplicate_blockers([row("a", "r1"), row("b", "r1", top="30", bottom="60")])[0].code == "DUPLICATE_INPUT"   # same root
    assert ci.duplicate_blockers([row("a", "r1"), row("a", "r2", fc="fc-2")])[0].code == "DUPLICATE_INPUT"                # same source


# ---------------------------------------------------------------- 10, 11
def test_confirmed_overlap_blocks_eligibility_and_verify_redetects(client: TestClient, db: Session) -> None:
    t = team(db, client)
    farmer = active_farmer(client, t, "2930 2000 3000")
    a = verified_farm(client, t, farmer["id"], square(79.30, 25.30))
    b = verified_farm(client, t, farmer["id"], square(79.33, 25.30))
    p = create_project(client, t)
    assert client.post(f"{PR}/{p['id']}/start-data-collection", headers=t.pm.headers, json=_reason("collect")).status_code == 200
    assert add_farm(client, t, p["id"], a["id"]).status_code == 201
    project = db.get(Project, uuid.UUID(p["id"]))
    assert project is not None
    farms = pfs.repo.project_farms(db, project.id, active_only=True)
    assert pfs.farm_facts(db, project, farms)["open_overlaps"] == 0
    db.add(FarmOverlapCheck(farm_id=uuid.UUID(a["id"]), boundary_id=uuid.UUID(a["current_boundary"]["id"]), other_farm_id=uuid.UUID(b["id"]),
                            other_boundary_id=uuid.UUID(b["current_boundary"]["id"]), relation="PARTIAL", overlap_area_m2=Decimal("500"),
                            overlap_pct_of_farm=Decimal("1"), overlap_pct_of_other=Decimal("1"), same_farmer=True, same_organization=True,
                            status="CONFIRMED_CONFLICT"))
    db.flush()
    assert pfs.farm_facts(db, project, farms)["open_overlaps"] == 1        # a confirmed conflict blocks eligibility like an open one
    # verification re-runs overlap detection: an INACTIVE farm re-opened while this one was under review is flagged at verify
    base = verified_farm(client, t, farmer["id"], square(79.36, 25.30))
    assert client.post(f"{FA}/{base['id']}/inactivate", headers=t.agent.headers, json=_reason("farm sold")).status_code == 200
    new = create_farm(client, t.agent.headers, farmer["id"])
    set_boundary(client, t.agent.headers, new["id"], square(79.36 + SIZE / 2, 25.30))
    own = add_owner(client, t.agent.headers, new["id"])
    for url, actor, body in ((f"{FA}/{new['id']}/submit", t.agent, _reason("ready")), (f"{FA}/{new['id']}/start-review", t.gis, _reason("start")),
                             (f"{FA}/{new['id']}/ownership/{own['id']}/review", t.gis, {"status": "VERIFIED", "notes": "title ok"})):
        assert client.post(url, headers=actor.headers, json=body).status_code in (200, 201), url
    assert client.get(f"{FA}/{new['id']}/overlaps", headers=t.gis.headers).json() == []
    assert client.post(f"{FA}/{base['id']}/reopen", headers=t.agent.headers, json=_reason("bought back")).status_code == 200
    r = client.post(f"{FA}/{new['id']}/verify", headers=t.gis.headers, json=_reason("boundary and tenure confirmed"))
    assert r.status_code == 409 and r.json()["error_code"] == "REQUIREMENTS_NOT_MET", r.text
    db.rollback()   # the test session is shared with the app: drop what the refused request left uncommitted
    flags = client.get(f"{FA}/{new['id']}/overlaps", headers=t.gis.headers).json()
    assert [(f["status"], f["other_farm_id"]) for f in flags] in ([("OPEN", base["id"])], [("OPEN", new["id"])]), flags


def test_control_site_farm_is_locked_while_its_project_runs(client: TestClient, db: Session) -> None:
    t = team(db, client)
    farmer = active_farmer(client, t, "2940 2000 3000")
    farm = verified_farm(client, t, farmer["id"], square(79.40, 25.40))
    p = create_project(client, t, name="Project with a control site")
    stratum = ProjectStratum(project_id=uuid.UUID(p["id"]), record_id=uuid.uuid4(), code="C1", name="Control C1", role="CONTROL",
                             linked_stratum_record_ids="[]", status="APPROVED")
    db.add(stratum)
    db.flush()
    db.add(StratumFarm(stratum_id=stratum.id, farm_id=uuid.UUID(farm["id"]), farm_boundary_id=uuid.UUID(farm["current_boundary"]["id"])))
    db.flush()
    for action in ("reopen", "inactivate"):
        r = client.post(f"{FA}/{farm['id']}/{action}", headers=t.agent.headers, json=_reason("change the boundary"))
        assert r.status_code == 409 and r.json()["error_code"] == "FARM_IN_ACTIVE_PROJECT", r.text
        assert r.json()["details"]["projects"] == [{"project_code": p["project_code"], "status": p["status"]}]
    assert client.post(f"{PR}/{p['id']}/close", headers=t.pm.headers, json=_reason("project abandoned")).status_code == 200
    assert client.post(f"{FA}/{farm['id']}/reopen", headers=t.agent.headers, json=_reason("correct the boundary")).status_code == 200


# ---------------------------------------------------------------- 12
def test_farmer_cannot_change_own_status(client: TestClient, db: Session) -> None:
    t = team(db, client)
    group = make_org(db, org_type="FARMER_GROUP")
    r = client.post(F, headers=t.pm.headers, json={"organization_id": str(t.org.id), "full_name": "Self Service", "village": "V",
                                                   "district": "D", "state": "Karnataka", "country": "IN", "primary_phone": "+91 98765 00029",
                                                   "participation_type": "GROUP_MEMBER", "group_organization_id": str(group.id)})
    assert r.status_code == 201, r.text
    f = r.json()
    user = make_user(db, roles=[("FARMER", group)])
    assert client.post(f"{F}/{f['id']}/link-user", headers=t.pm.headers, json={"user_id": str(user.id)}).status_code == 200
    h = login(client, user)
    r = client.post(f"{F}/{f['id']}/status", headers=h, json={"status": "REGISTERED", "reason": "self"})
    assert r.status_code == 403, r.text
    assert client.post(f"{F}/{f['id']}/status", headers=t.pm.headers, json={"status": "REGISTERED", "reason": "profile complete"}).status_code == 200


# ---------------------------------------------------------------- 13
def test_lab_report_cannot_be_replaced_after_submission(client: TestClient, db: Session) -> None:
    x = lab_project(db, client, 79.50, 25.50, "2950 2000 3000", n_points=1)
    sample = to_lab(client, x)
    res = enter_result(client, x, sample["tests"][0]["id"])
    assert res["status"] == "SUBMITTED"
    r = client.post(f"{LABV}/results/{res['id']}/report", headers=x.tech.headers, files={"file": ("other.pdf", PDF, "application/pdf")})
    assert r.status_code == 409 and r.json()["error_code"] == "RESULT_NOT_EDITABLE", r.text


# ---------------------------------------------------------------- 14
def test_refused_upload_records_the_event_without_committing_the_callers_work(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    class Infected:
        name = "test-scanner"

        def scan(self, data: bytes, filename: str | None) -> ScanResult:
            return ScanResult("INFECTED", "test-scanner", "1", "TEST-THREAT", "test signature")

    monkeypatch.setattr(document_service, "get_scanner", lambda: Infected())
    org = make_org(db)
    db.commit()                                      # (the savepoint the request would start from)
    tag = uuid.uuid4().hex[:6].upper()
    db.add(Standard(code=f"STD-UNRELATED-{tag}", name=f"Unrelated {tag}", program_type="VOLUNTARY", environment="LIVE"))
    db.flush()                                       # the caller's uncommitted, unrelated work
    ctx = RequestContext(request_id=f"test-av-{tag}", user_id=None)
    with pytest.raises(ValidationFailed) as e:
        document_service.create_document(db, ctx, entity_type="methodology", entity_id=uuid.uuid4(), organization_id=org.id, environment="LIVE",
                                         category="OTHER", title="infected", filename="x.pdf", data=PDF)
    assert e.value.error_code == "MALWARE_DETECTED"
    db.rollback()                                    # what the request does after the error
    assert db.scalars(select(Standard).where(Standard.code == f"STD-UNRELATED-{tag}")).first() is None
    assert db.scalars(select(SecurityEvent).where(SecurityEvent.event_type == "MALWARE_UPLOAD_BLOCKED",
                                                  SecurityEvent.request_id == f"test-av-{tag}")).first() is not None
