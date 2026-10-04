"""Phase 7 — carbon calculation: framework determinism (Decimal), registry (no module shipped), the real DEMO / Niphad path
(CONFIGURATION_REQUIRED, NO_CALCULATION_MODULE), and — with the TEST-ONLY, non-carbon fixture module handed to the service layer —
readiness blockers, frozen inputs and hashes, execution, lineage, QA, separation of duties, recalculation / supersession,
project CALCULATION_READY / CALCULATED, RBAC, organization isolation, audit and the database triggers."""
import contextlib
import json
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.calculation import framework as fw
from app.calculation import registry
from app.calculation.framework import CalculationBlocked, CalculationModule, Constant, Output, Step, Variable
from app.core.config import get_settings
from app.core.errors import Conflict
from app.models import (
    AuditLog,
    CalculationRun,
    MethodologyCalculationRule,
    MonitoringPeriod,
    Organization,
    Project,
    ProjectCreditingPeriod,
    ProjectMethodology,
    ProjectStatusHistory,
)
from app.schemas.calculation import CALCULATED_LABEL, DEMO_LABEL, RunIn
from app.services import calculation_inputs as ci
from app.services import calculation_service as cs
from tests.calc_fixture import (
    CALC,
    FixtureModule,
    approve_dataset,
    as_principal,
    calc_scenario,
    expected_net,
    fixture_module,
    lab_results,
    resolver_for,
)
from tests.conftest import Actor, login, make_org, make_user
from tests.phase2 import staff
from tests.phase3 import PR
from tests.phase6 import LABV, PDF, SOC_RULE, TEXT_RULE, now_iso, qa


def _objs(db: Session, k: Any) -> tuple[Project, MonitoringPeriod]:
    p, mp = db.get(Project, uuid.UUID(k.project_id)), db.get(MonitoringPeriod, uuid.UUID(k.period_id))
    assert p is not None and mp is not None
    return p, mp


def _create(db: Session, k: Any, actor: Actor | None = None) -> CalculationRun:
    p, ctx = as_principal(db, actor or k.analyst)
    return cs.create_run(db, ctx, p, RunIn(project_id=uuid.UUID(k.project_id), monitoring_period_id=uuid.UUID(k.period_id)))


def _do(db: Session, actor: Actor, fn: Any, run: CalculationRun, **kw: Any) -> Any:
    p, ctx = as_principal(db, actor)
    return fn(db, ctx, p, run.id, **kw)


def _codes(ev: ci.Evaluation) -> list[tuple[str, str | None]]:
    return [(b.code, b.reason) for b in ev.blockers]


def _status(db: Session, pid: str) -> str:
    db.expire_all()
    p = db.get(Project, uuid.UUID(pid))
    assert p is not None
    return p.status


# ---------------------------------------------------------------- framework (pure)
def _snapshot(values: tuple[str, ...] = ("1.5", "2.5"), areas: tuple[str, ...] = ("2.6", "1.4")) -> dict[str, Any]:
    rows, seq = [], 0
    for v in values:
        seq += 1
        rows.append({"seq": seq, "variable": "TEST_LAB", "value": v, "value_kind": "NUMBER", "unit": "t C/ha", "level": "SAMPLING_POINT"})
    for a in areas:
        seq += 1
        rows.append({"seq": seq, "variable": "TEST_AREA", "value": a, "value_kind": "NUMBER", "unit": "ha", "level": "STRATUM"})
    rows.append({"seq": seq + 1, "variable": "TEST_K", "value": "2", "value_kind": "NUMBER", "unit": "TEST", "level": "PROJECT"})
    return {"inputs": rows}


def _mod(**attrs: Any) -> CalculationModule:
    return type("M", (FixtureModule,), {"methodology_code": "TEST", "version_label": "1", **attrs})()


def test_framework_is_deterministic_decimal_and_never_invents_a_step() -> None:
    snap = _snapshot()
    a, b = fw.execute(_mod(), snap), fw.execute(_mod(), json.loads(json.dumps(snap)))
    assert a.output_sha256 == b.output_sha256 and a.outputs == b.outputs                      # same snapshot → same bytes
    assert Decimal(a.net_value) == expected_net(["1.5", "2.5"], Decimal("4.0")) and a.net_unit == "TEST"
    third = next(o for o in a.outputs if o["output_code"] == "T_THIRD")["value"]
    assert len(third.replace(".", "").lstrip("0")) == 34                                     # Decimal context: 34 digits, no float
    assert [o["step"] for o in a.outputs] == list(fw.STEPS) and sum(o["is_final"] for o in a.outputs) == 1
    assert fw.execute(_mod(), _snapshot(values=("1.5", "2.51"))).output_sha256 != a.output_sha256

    def blocked(module: CalculationModule) -> CalculationBlocked:
        with pytest.raises(CalculationBlocked) as e:
            fw.execute(module, snap)
        return e.value

    assert blocked(_mod(calculate_net_result=lambda self, ctx: [Output("N", "NET", "TC8", 1.5, "TEST", outputs=("T_SUM",),  # type: ignore[arg-type]
                                                                       is_final=True)])).code == "CALCULATION_ERROR"   # float refused
    assert blocked(_mod(calculate_leakage=lambda self, ctx: [Output("L", "LEAKAGE", "TC1", Decimal(1), "TEST", outputs=("T_SUM",))])
                   ).code == "CALCULATION_RULE_NOT_CONFIGURED"                                  # an output must cite its step's rule
    e = blocked(_mod(calculate_uncertainty=CalculationModule.calculate_uncertainty))            # no default formula exists
    assert (e.code, e.details["reason"]) == ("CONFIGURATION_REQUIRED", "STEP_NOT_IMPLEMENTED")
    e = blocked(_mod(steps=tuple(s for s in FixtureModule.steps if s.step != "BASELINE")))
    assert (e.code, e.details["reason"]) == ("CONFIGURATION_REQUIRED", "STEP_NOT_CONFIGURED")
    e = blocked(_mod(calculate_net_result=lambda self, ctx: [Output("N", "NET", "TC8", Decimal(1), "TEST", outputs=("T_SUM",))]))
    assert e.details["reason"] == "NO_FINAL_NET_OUTPUT"
    assert blocked(_mod(calculate_net_result=lambda self, ctx: [Output("N", "NET", "TC8", Decimal(1), "TEST", is_final=True)])
                   ).code == "CALCULATION_ERROR"                                                # an output without lineage is refused
    # "Not included — DEMO": the step is skipped visibly (never silently computed)
    only_net = (*(Step(s, fw.NOT_INCLUDED_DEMO) for s in fw.STEPS if s != "NET"), Step("NET", fw.IMPLEMENTED, "TC8"))
    demo = _mod(steps=only_net, calculate_net_result=lambda self, ctx: [Output(
        "N", "NET", "TC8", sum((v.value for v in ctx.values("TEST_LAB")), Decimal(0)), "TEST",
        inputs=tuple(v.seq for v in ctx.values("TEST_LAB")), is_final=True)])
    assert fw.execute(demo, snap).net_value == "4.0"
    with pytest.raises(ValueError):
        Variable("X", "LAB_RESULT", "", "SAMPLING_POINT", rule_code="SOC")       # a numeric variable must declare its unit
    with pytest.raises(ValueError):
        Constant("K", "2", "TEST", " ")                                           # a constant must cite its source


def test_registry_ships_only_vm0042_and_the_test_fixture_is_not_registered(client: TestClient, db: Session) -> None:
    assert [m.code for m in registry.modules()] == ["VM0042-V2.2-QA2-QA3"] and registry.resolve("TEST", "1") is None
    assert registry.modules()[0].readiness == fw.NOT_PRODUCTION_READY and registry.modules()[0].calculation_rules_version == 0
    u = make_user(db, roles=[("CALCULATION_ANALYST", make_org(db))])
    assert [m["code"] for m in client.get(f"{CALC}/modules", headers=login(client, u)).json()] == ["VM0042-V2.2-QA2-QA3"]


# ---------------------------------------------------------------- the real DEMO path stays blocked
def test_demo_niphad_is_blocked_configuration_required_no_calculation_module(client: TestClient, db: Session) -> None:
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
    assert p.status == "MONITORING" and mp is not None
    org = db.scalars(select(Organization).where(Organization.code == "DEMO-DEV-A")).one()
    h = login(client, make_user(db, roles=[("CALCULATION_ANALYST", org)], environment="DEMO"))
    r = client.get(f"{CALC}/projects/{p.id}/readiness", headers=h, params={"monitoring_period_id": str(mp.id)}).json()
    assert r["ready"] is False and (r["blockers"][0]["code"], r["blockers"][0]["reason"]) == ("CONFIGURATION_REQUIRED", "NO_CALCULATION_MODULE")
    assert "DATASET_NOT_APPROVED" in [b["code"] for b in r["blockers"]] and r["dataset_status"] == "COLLECTING"
    assert r["is_demo_illustrative"] and {s["status"] for s in r["steps"]} == {"NOT_CONFIGURED"}
    assert [c["implementation_status"] for c in r["calculation_rules"]] == ["NOT_IMPLEMENTED"]     # DEMO rules untouched
    run = client.post(f"{CALC}/runs", headers=h, json={"project_id": str(p.id), "monitoring_period_id": str(mp.id)}).json()
    assert run["status"] == "DRAFT" and run["environment"] == "DEMO" and run["demo_label"] == DEMO_LABEL
    r = client.post(f"{CALC}/runs/{run['id']}/freeze", headers=h)
    assert r.status_code == 409 and r.json()["error_code"] == "CONFIGURATION_REQUIRED"
    assert r.json()["details"]["reason"] == "NO_CALCULATION_MODULE"
    got = client.get(f"{CALC}/runs/{run['id']}", headers=h).json()
    assert got["status"] == "BLOCKED" and got["blockers"][0]["reason"] == "NO_CALCULATION_MODULE" and got["net_result"] is None
    assert client.get(f"{CALC}/runs/{run['id']}/inputs", headers=h).json()["inputs"] == []
    assert client.post(f"{CALC}/runs/{run['id']}/execute", headers=h).json()["error_code"] == "RUN_NOT_EDITABLE"
    assert _status(db, str(p.id)) == "MONITORING"                                 # an attempted run never moves the project
    assert db.scalars(select(AuditLog).where(AuditLog.action == "CALCULATION_BLOCKED", AuditLog.entity_id == run["id"])).first()


# ---------------------------------------------------------------- TEST fixture: complete lifecycle
def test_fixture_lifecycle_lineage_recalculation_and_project_calculated(client: TestClient, db: Session) -> None:
    k = calc_scenario(db, client, 77.10, 22.10, "8100 2000 3000")
    p, mp = _objs(db, k)
    ev = ci.evaluate(db, p, mp, None, k.resolver)
    assert ev.ready and ev.blockers == [] and ci.evaluate(db, p, mp, None, k.resolver).snapshot_sha256 == ev.snapshot_sha256
    run = _create(db, k)
    assert run.status == "DRAFT" and run.run_code.startswith("CALC-") and _status(db, k.project_id) == "MONITORING"
    run = _do(db, k.analyst, cs.freeze, run, resolver=k.resolver)
    assert run.status == "INPUTS_FROZEN" and run.input_sha256 == ev.snapshot_sha256 and run.module_readiness == "NOT_PRODUCTION_READY"
    assert _status(db, k.project_id) == "CALCULATION_READY"
    rows = cs.inputs(db, run.id)
    assert [r.source_type for r in rows] == ["LAB_RESULT", "LAB_RESULT", "STRATUM_AREA", "MODULE_CONSTANT"]
    assert sorted(Decimal(r.value) for r in rows if r.source_type == "LAB_RESULT") == sorted(Decimal(v) for v in k.lab_values)  # exact copies
    assert all(r.root_sample_id and r.field_collection_id and r.sampling_point_id and r.source_sha256 for r in rows
               if r.source_type == "LAB_RESULT")
    run = _do(db, k.analyst, cs.execute, run, resolver=k.resolver)
    area = sum(Decimal(r.value) for r in rows if r.source_type == "STRATUM_AREA")
    assert run.status == "CALCULATED" and Decimal(run.net_result) == expected_net(k.lab_values, area) and run.net_unit == "TEST"
    assert fw.execute(k.module, json.loads(run.input_snapshot)).output_sha256 == run.output_sha256     # reproducible
    outs = cs.outputs(db, run.id)
    rule_ids = {r.rule_code: r.id for r in db.scalars(select(MethodologyCalculationRule).where(
        MethodologyCalculationRule.methodology_version_id == run.methodology_version_id)).all()}
    assert [o.step for o in outs] == list(fw.STEPS) and all(o.calculation_rule_id == rule_ids[o.rule_code] for o in outs)
    h = k.qa.headers
    body = client.get(f"{CALC}/runs/{run.id}", headers=h).json()
    assert body["result_label"] == CALCULATED_LABEL and body["net_result"] == run.net_result and body["can_approve"] is False
    out = client.get(f"{CALC}/runs/{run.id}/outputs", headers=h).json()
    assert out["outputs"][-1]["is_final"] and out["steps"][0]["status"] == "IMPLEMENTED"
    lin = client.get(f"{CALC}/runs/{run.id}/lineage", headers=h).json()
    assert lin["final"]["output_code"] == "T_NET" and lin["final"]["rule"]["rule_code"] == "TC8" and lin["dataset"]["code"]
    lab_in = next(i for i in lin["inputs"] if i["source_type"] == "LAB_RESULT")
    for key in ("lab_result", "sample", "root_sample", "field_collection", "sampling_point", "stratum", "farm", "farmer", "project"):
        assert lab_in["chain"][key], key
    run = _do(db, k.analyst, cs.submit, run)
    assert run.status == "QA_REVIEW"
    assert client.post(f"{CALC}/runs/{run.id}/approve", headers=h, json={"reason": "too early"}).json()["error_code"] == "QA_NOT_PASSED"
    assert client.post(f"{CALC}/qa/{run.id}/start", headers=h).status_code == 200
    rv = _do(db, k.qa, cs.complete_qa, run, result="PASS", notes="all checks pass", resolver=k.resolver)
    checks = {c["key"]: c["result"] for c in json.loads(rv.checks)}
    assert "FAIL" not in checks.values() and checks["reproducible"] == "PASS" and checks["module_readiness"] == "WARN"
    r = client.post(f"{CALC}/runs/{run.id}/approve", headers=h, json={"reason": "TEST calculation approved"})
    assert r.status_code == 200 and r.json()["status"] == "APPROVED", r.text
    assert _status(db, k.project_id) == "CALCULATED"
    # recalculation: a new run with its own snapshot, outputs, QA and approval; the old run is untouched until then
    r2 = client.post(f"{CALC}/runs/{run.id}/recalculate", headers=k.analyst.headers, json={"reason": "TEST re-run after review"})
    assert r2.status_code == 201 and r2.json()["recalculation_of_code"] == run.run_code
    run2 = db.get(CalculationRun, uuid.UUID(r2.json()["id"]))
    assert run2 is not None
    for fn in (cs.freeze, cs.execute):
        run2 = _do(db, k.analyst, fn, run2, resolver=k.resolver)
    run2 = _do(db, k.analyst, cs.submit, run2)
    client.post(f"{CALC}/qa/{run2.id}/start", headers=h)
    _do(db, k.qa, cs.complete_qa, run2, result="PASS", notes="re-run checks pass", resolver=k.resolver)
    assert client.get(f"{CALC}/runs/{run.id}", headers=h).json()["status"] == "APPROVED"      # still authoritative
    assert client.post(f"{CALC}/runs/{run2.id}/approve", headers=h, json={"reason": "TEST re-run approved"}).status_code == 200
    db.expire_all()
    old, new = db.get(CalculationRun, run.id), db.get(CalculationRun, run2.id)
    assert old is not None and new is not None
    assert (old.status, old.superseded_by_run_id, new.status) == ("SUPERSEDED", new.id, "APPROVED")
    assert (new.input_sha256, new.output_sha256) == (old.input_sha256, old.output_sha256)       # same data → same bytes
    cmp = client.get(f"{CALC}/runs/{old.id}/compare/{new.id}", headers=h).json()
    assert cmp["same_inputs"] and cmp["same_outputs"] and cmp["inputs_changed"] == [] and cmp["outputs_changed"] == []
    assert [x["status"] for x in client.get(f"{CALC}/runs", headers=h, params={"project_id": k.project_id}).json()] == ["APPROVED", "SUPERSEDED"]
    assert _status(db, k.project_id) == "CALCULATED"
    actions = {a for (a,) in db.execute(select(AuditLog.action).where(AuditLog.entity_type == "calculation_run",
                                                                      AuditLog.entity_id.in_([str(old.id), str(new.id)])))}
    assert {"CALCULATION_RUN_CREATED", "CALCULATION_INPUTS_FROZEN", "CALCULATION_EXECUTED", "CALCULATION_SUBMITTED", "CALCULATION_QA_STARTED",
            "CALCULATION_QA_COMPLETED", "CALCULATION_APPROVED", "CALCULATION_SUPERSEDED"} <= actions
    approved = db.scalars(select(AuditLog).where(AuditLog.action == "CALCULATION_APPROVED", AuditLog.entity_id == str(new.id))).one()
    payload = json.loads(approved.new_value or "{}")
    for key in ("input_sha256", "output_sha256", "methodology_version_id", "calculation_rules_version", "module_version", "engine_version",
                "net_result"):
        assert payload[key], key
    hist = [h.to_status for h in db.scalars(select(ProjectStatusHistory).where(ProjectStatusHistory.project_id == p.id)).all()]
    assert hist[-2:] == ["CALCULATION_READY", "CALCULATED"]


# ---------------------------------------------------------------- blockers
def test_module_rule_step_unit_production_and_size_blockers(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    k = calc_scenario(db, client, 77.20, 22.20, "8200 2000 3000")
    p, mp = _objs(db, k)
    vid = k.x.c.version_id

    def first(**attrs: Any) -> tuple[str, str | None]:
        return _codes(ci.evaluate(db, p, mp, None, resolver_for(fixture_module(db, vid, **attrs))))[0]

    assert _codes(ci.evaluate(db, p, mp))[0] == ("CONFIGURATION_REQUIRED", "NO_CALCULATION_MODULE")       # application registry
    assert first(rules={c: s for c, s in FixtureModule.rules.items() if c != "TC5"}) == ("CALCULATION_RULE_NOT_CONFIGURED", "RULE_MODULE_MISMATCH")
    assert first(rules={**FixtureModule.rules, "TC9": "NET"}) == ("CALCULATION_RULE_NOT_CONFIGURED", "RULE_MODULE_MISMATCH")
    assert first(calculation_rules_version=99) == ("CALCULATION_RULE_NOT_CONFIGURED", "RULE_MODULE_MISMATCH")
    assert first(steps=tuple(s for s in FixtureModule.steps if s.step != "UNCERTAINTY")) == ("CONFIGURATION_REQUIRED", "STEP_NOT_CONFIGURED")
    leak_out = tuple(Step(s.step, fw.NOT_INCLUDED_DEMO) if s.step == "LEAKAGE" else s for s in FixtureModule.steps)
    assert first(steps=leak_out) == ("CONFIGURATION_REQUIRED", "STEP_NOT_INCLUDED")                       # LIVE: never left out
    p.environment = "DEMO"                                                         # (in memory only — DEMO may leave a step out, visibly)
    demo_ev = ci.evaluate(db, p, mp, None, resolver_for(fixture_module(db, vid, steps=leak_out)))
    p.environment = "LIVE"
    assert "STEP_NOT_INCLUDED" not in [b.reason for b in demo_ev.blockers] and "LEAKAGE: Not included — DEMO" in demo_ev.warnings
    wrong_unit = (Variable("TEST_LAB", "LAB_RESULT", "t C ha-1", "SAMPLING_POINT", rule_code="SOC"), FixtureModule.variables[1])
    assert first(variables=wrong_unit)[0] == "UNIT_MISMATCH"                                              # exact text, never converted
    assert first(variables=(Variable("V", "LAB_RESULT", "t C/ha", "SAMPLING_POINT", rule_code="NOPE"),))[0] == "CALCULATION_RULE_NOT_CONFIGURED"
    monkeypatch.setattr(get_settings(), "APP_ENV", "production")
    assert first()[0] == "NOT_PRODUCTION_READY"
    monkeypatch.setattr(get_settings(), "APP_ENV", "test")
    monkeypatch.setattr(get_settings(), "CALCULATION_MAX_INPUT_ROWS", 2)
    assert first()[0] == "INPUT_TOO_LARGE"
    monkeypatch.setattr(get_settings(), "CALCULATION_MAX_INPUT_ROWS", 20000)
    # a freeze that fails readiness makes the run BLOCKED (final); the project stays MONITORING
    run = _create(db, k)
    with pytest.raises(Conflict) as e:
        _do(db, k.analyst, cs.freeze, run, resolver=resolver_for(fixture_module(db, vid, variables=wrong_unit)))
    assert e.value.error_code == "UNIT_MISMATCH" and e.value.details["blockers"][0]["code"] == "UNIT_MISMATCH"
    db.expire_all()
    run = db.get(CalculationRun, run.id)
    assert run is not None and run.status == "BLOCKED" and run.input_snapshot is None and cs.inputs(db, run.id) == []
    assert _status(db, k.project_id) == "MONITORING"
    with pytest.raises(Conflict) as e:
        _do(db, k.analyst, cs.execute, run, resolver=k.resolver)
    assert e.value.error_code == "RUN_NOT_EDITABLE"
    assert _create(db, k).status == "DRAFT"                                       # a blocked run is not open: a new run may start


def test_missing_superseded_and_outdated_laboratory_results(client: TestClient, db: Session) -> None:
    k = calc_scenario(db, client, 77.30, 22.30, "8300 2000 3000", approve_results=1)
    p, mp = _objs(db, k)
    missing = ci.evaluate(db, p, mp, None, k.resolver).blockers
    assert [b.code for b in missing] == ["MISSING_APPROVED_LAB_RESULT"] and missing[0].details["point"]   # nothing substituted
    pending = next(r for r in lab_results(client, k.x) if r["status"] == "SUBMITTED")
    assert qa(client, k.x, pending["id"]).json()["result"]["status"] == "APPROVED"
    run = _do(db, k.analyst, cs.freeze, _create(db, k), resolver=k.resolver)
    assert run.status == "INPUTS_FROZEN"
    # a Phase 6 correction approved after the freeze supersedes a frozen result → the run cannot execute on it
    v1 = k.results[0]
    corr = client.post(f"{LABV}/results/{v1['id']}/correct", headers=k.x.tech.headers, json={
        "reason": "transcription error", "result_type": "NUMERIC", "value_number": "1.75", "unit": "t C/ha", "analysed_at": now_iso(1)}).json()
    client.post(f"{LABV}/results/{corr['id']}/report", headers=k.x.tech.headers, files={"file": ("r.pdf", PDF, "application/pdf")})
    client.post(f"{LABV}/results/{corr['id']}/submit", headers=k.x.tech.headers)
    assert qa(client, k.x, corr["id"]).json()["result"]["status"] == "APPROVED"
    with pytest.raises(Conflict) as e:
        _do(db, k.analyst, cs.execute, run, resolver=k.resolver)
    assert e.value.error_code == "INPUTS_OUT_OF_DATE"
    # a new run uses only the current APPROVED version; the SUPERSEDED one is never an input
    run2 = _do(db, k.analyst, cs.freeze, _create(db, k), resolver=k.resolver)
    lab = [r for r in cs.inputs(db, run2.id) if r.source_type == "LAB_RESULT"]
    assert Decimal("1.75") in [Decimal(r.value) for r in lab] and str(v1["id"]) not in [str(r.source_id) for r in lab]
    assert any(r.source_version == 2 for r in lab) and run2.input_sha256 != run.input_sha256


def test_text_result_for_a_numeric_variable_is_refused(client: TestClient, db: Session) -> None:
    k = calc_scenario(db, client, 77.40, 22.40, "8400 2000 3000", rules=[SOC_RULE, TEXT_RULE])
    p, mp = _objs(db, k)
    module = fixture_module(db, k.x.c.version_id, variables=(*FixtureModule.variables,
                                                             Variable("TEST_TEXT", "LAB_RESULT", "TEST", "SAMPLING_POINT", rule_code="TEX")))
    blockers = ci.evaluate(db, p, mp, None, resolver_for(module)).blockers
    assert {b.code for b in blockers} == {"INPUT_NOT_NUMERIC"} and len(blockers) == 2 and "<0.05" in blockers[0].message   # never parsed


def test_dataset_crediting_period_open_run_and_methodology_lock(client: TestClient, db: Session) -> None:
    k = calc_scenario(db, client, 77.50, 22.50, "8500 2000 3000", approve_ds=False)
    p, mp = _objs(db, k)
    ev = ci.evaluate(db, p, mp, None, k.resolver)
    assert [b.code for b in ev.blockers] == ["DATASET_NOT_APPROVED"] and ev.blockers[0].details["dataset_status"] is None
    approve_dataset(client, k.x)
    outside = ProjectCreditingPeriod(project_id=p.id, period_number=9, start_date=date(2030, 1, 1), end_date=date(2031, 1, 1))
    assert "OUTSIDE_CREDITING_PERIOD" in [b.code for b in ci.evaluate(db, p, mp, outside, k.resolver).blockers]
    run = _create(db, k)
    with pytest.raises(Conflict) as e:
        _create(db, k)
    assert e.value.error_code == "OPEN_RUN_EXISTS"
    run = _do(db, k.analyst, cs.freeze, run, resolver=k.resolver)
    pm = db.scalars(select(ProjectMethodology).where(ProjectMethodology.project_id == p.id, ProjectMethodology.status == "LOCKED")).one()
    pm.status = "UNLOCKED"                                                         # the lock changes after the freeze
    db.flush()
    with pytest.raises(Conflict) as e:
        _do(db, k.analyst, cs.execute, run, resolver=k.resolver)
    assert e.value.error_code == "INPUTS_OUT_OF_DATE"
    assert _codes(ci.evaluate(db, p, mp, None, k.resolver))[0][0] == "METHODOLOGY_NOT_LOCKED"


# ---------------------------------------------------------------- QA, separation of duties, RBAC, isolation
def test_qa_failure_reject_separation_of_duties_rbac_and_isolation(client: TestClient, db: Session) -> None:
    k = calc_scenario(db, client, 77.60, 22.60, "8600 2000 3000")
    org = k.x.c.t.org
    dual = staff(db, client, org, "CALCULATION_ANALYST", "QA_OFFICER")
    run = _create(db, k, dual)
    for fn in (cs.freeze, cs.execute):
        run = _do(db, dual, fn, run, resolver=k.resolver)
    run = _do(db, dual, cs.submit, run)
    for path, body in ((f"qa/{run.id}/start", None), (f"runs/{run.id}/approve", {"reason": "my own run"}),
                       (f"runs/{run.id}/reject", {"reason": "my own run"})):
        r = client.post(f"{CALC}/{path}", headers=dual.headers, json=body)
        assert r.status_code == 403 and r.json()["error_code"] == "SEPARATION_OF_DUTIES", r.text
    # QA through the API only knows the application registry: the TEST module is unreachable there, so PASS is refused
    h = k.qa.headers
    assert client.post(f"{CALC}/qa/{run.id}/start", headers=h).status_code == 200
    r = client.post(f"{CALC}/qa/{run.id}/complete", headers=h, json={"result": "PASS", "notes": "try to pass"})
    assert r.json()["error_code"] == "QA_CHECKS_FAILED" and {"module_rules", "reproducible"} <= set(r.json()["details"]["failed"])
    view = client.post(f"{CALC}/qa/{run.id}/complete", headers=h, json={"result": "FAIL", "notes": "module not available"}).json()
    assert view["reviews"][-1]["result"] == "FAIL"
    assert client.post(f"{CALC}/runs/{run.id}/approve", headers=h, json={"reason": "not passed"}).json()["error_code"] == "QA_NOT_PASSED"
    r = client.post(f"{CALC}/runs/{run.id}/reject", headers=h, json={"reason": "QA failed"})
    assert r.json()["status"] == "REJECTED" and _status(db, k.project_id) == "CALCULATION_READY"
    # RBAC: read for MRV manager / project manager; manage only for the analyst; nothing for lab, finance, buyer, farmer
    rid = str(run.id)
    for actor in (k.x.c.mrv, k.x.c.t.pm, k.analyst, k.qa):
        assert client.get(f"{CALC}/runs/{rid}", headers=actor.headers).status_code == 200
    new = {"project_id": k.project_id, "monitoring_period_id": k.period_id}
    assert client.post(f"{CALC}/runs", headers=k.x.c.mrv.headers, json=new).status_code == 403
    assert client.post(f"{CALC}/runs", headers=k.qa.headers, json=new).status_code == 403
    outsiders = [k.x.tech, k.x.mgr, staff(db, client, org, "FINANCE_MANAGER"), staff(db, client, make_org(db, org_type="BUYER"), "BUYER"),
                 Actor(u := make_user(db, roles=[("FARMER", org)]), login(client, u))]
    for actor in outsiders:
        assert client.get(f"{CALC}/runs/{rid}", headers=actor.headers).status_code in (403, 404)
        assert client.get(f"{CALC}/runs", headers=actor.headers, params={"project_id": k.project_id}).status_code in (403, 404)
    other = staff(db, client, make_org(db), "CALCULATION_ANALYST")                 # another organization: nothing is revealed
    assert k.project_id in [x["id"] for x in client.get(f"{CALC}/projects", headers=k.analyst.headers).json()]
    assert k.project_id not in [x["id"] for x in client.get(f"{CALC}/projects", headers=other.headers).json()]
    assert client.get(f"{CALC}/runs/{rid}", headers=other.headers).status_code == 404
    assert client.get(f"{CALC}/projects/{k.project_id}/readiness", headers=other.headers,
                      params={"monitoring_period_id": k.period_id}).status_code == 404
    assert client.post(f"{CALC}/runs", headers=other.headers, json=new).status_code == 404
    # no request can carry a calculated value
    assert client.post(f"{CALC}/runs", headers=k.analyst.headers, json={**new, "net_result": "999"}).status_code == 422
    assert client.post(f"{CALC}/runs/{rid}/approve", headers=h, json={"reason": "x y z", "net_result": "1"}).status_code == 422
    assert client.get(f"{PR}/{k.project_id}", headers=k.x.c.t.pm.headers).json()["status"] == "CALCULATION_READY"


# ---------------------------------------------------------------- database triggers
def test_database_triggers_protect_calculation_history() -> None:
    """A trigger THROW aborts the whole transaction: build the data on a dedicated connection, fire one violating statement,
    then discard the connection (nothing is kept)."""
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
            k = calc_scenario(session, client, 77.70, 22.70, "8700 2000 3000")
            run = _create(session, k)
            for fn in (cs.freeze, cs.execute):
                run = _do(session, k.analyst, fn, run, resolver=k.resolver)
        session.flush()
        with pytest.raises(DBAPIError) as exc:
            conn.execute(text("UPDATE calculation_runs SET net_result = N'1' WHERE id = :i"), {"i": str(run.id)})
        assert "immutable" in str(exc.value)
    finally:
        limiter.reset()
        conn.invalidate()
        with contextlib.suppress(Exception):
            session.close()
    for stmt, msg in (("UPDATE calculation_inputs SET value = N'0'", "append-only"), ("DELETE FROM calculation_outputs", "append-only")):
        with get_engine().connect() as c2:
            t2 = c2.begin()
            with pytest.raises(DBAPIError) as e2:
                c2.execute(text(stmt + " WHERE 1 = 0"))
            assert msg in str(e2.value)
            if t2.is_active:
                t2.rollback()
