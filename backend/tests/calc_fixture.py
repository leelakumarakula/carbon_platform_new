"""TEST-ONLY calculation fixture (decision C2). NOT carbon accounting.

- The module below is never registered in `app.calculation.registry` and is unreachable through the API: tests hand it to the
  service layer explicitly as a `resolver`. The application keeps shipping no calculation module.
- Its arithmetic is deliberately non-carbon (sums, a product and divisions of TEST values) and every output unit is "TEST". It
  exists only to prove the framework mechanics: frozen inputs, Decimal execution, lineage, QA, separation of duties,
  recalculation / supersession and the project's CALCULATED status.
- The scenario uses the Phase 5 / 6 test builders (test database, rolled back after each test); no DEMO or LIVE seed data is touched.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, ClassVar

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.calculation import framework as fw
from app.calculation.framework import CalculationContext, CalculationModule, Constant, Output, Step, Variable
from app.calculation.registry import Resolver
from app.core.context import RequestContext
from app.models import Methodology, MethodologyVersion
from app.security.principal import Principal, load_principal
from tests.conftest import Actor
from tests.phase2 import staff
from tests.phase5 import MRV
from tests.phase6 import LAB, LABV, SOC_RULE, LabCtx, lab_project, now_iso, qa, receive, register, seal, ship

CALC = "/api/v1/calculations"
TEST_LABEL = "TEST FIXTURE — not carbon accounting"
FIXTURE_RULES = [{"rule_code": f"TC{i}", "title": f"TEST fixture step {step} (not a methodology rule)", "step": step,
                  "equation_reference": f"TEST-EQ-{i}", "description": TEST_LABEL} for i, step in enumerate(fw.STEPS, 1)]


class FixtureModule(CalculationModule):
    """Deliberately non-carbon arithmetic over TEST values (unit TEST)."""
    code = "TEST-FIXTURE-NON-CARBON"
    version = "1.0.0"
    readiness = fw.NOT_PRODUCTION_READY
    rules: ClassVar[dict[str, str]] = {r["rule_code"]: r["step"] for r in FIXTURE_RULES}
    variables = (Variable("TEST_LAB", "LAB_RESULT", "t C/ha", "SAMPLING_POINT", rule_code="SOC"),
                 Variable("TEST_AREA", "STRATUM_AREA", "ha", "STRATUM"))
    constants = (Constant("TEST_K", "2", "TEST", "TEST fixture constant — not from any methodology"),)
    steps = tuple(Step(s, fw.IMPLEMENTED, f"TC{i}") for i, s in enumerate(fw.STEPS, 1))
    label = TEST_LABEL

    def calculate_baseline(self, ctx: CalculationContext) -> list[Output]:
        vals = ctx.values("TEST_LAB")
        return [Output("T_SUM", "BASELINE", "TC1", sum((v.value for v in vals), Decimal(0)), "TEST",  # type: ignore[misc]
                       inputs=tuple(v.seq for v in vals))]

    def calculate_project(self, ctx: CalculationContext) -> list[Output]:
        area = ctx.values("TEST_AREA")
        return [Output("T_AREA", "PROJECT", "TC2", sum((a.value for a in area), Decimal(0)), "TEST",  # type: ignore[misc]
                       inputs=tuple(a.seq for a in area))]

    def calculate_emissions(self, ctx: CalculationContext) -> list[Output]:
        s = ctx.output("T_SUM")
        return [Output("T_ZERO", "EMISSIONS", "TC3", s.value - s.value, "TEST", outputs=("T_SUM",))]

    def calculate_removals(self, ctx: CalculationContext) -> list[Output]:
        k = ctx.constant("TEST_K")
        return [Output("T_PRODUCT", "REMOVALS", "TC4", ctx.output("T_AREA").value * k.value, "TEST",  # type: ignore[operator]
                       inputs=(k.seq,), outputs=("T_AREA",))]

    def calculate_leakage(self, ctx: CalculationContext) -> list[Output]:
        return [Output("T_QUARTER", "LEAKAGE", "TC5", ctx.output("T_SUM").value / Decimal(4), "TEST", outputs=("T_SUM",))]

    def calculate_uncertainty(self, ctx: CalculationContext) -> list[Output]:
        return [Output("T_THIRD", "UNCERTAINTY", "TC6", ctx.output("T_QUARTER").value / Decimal(3), "TEST", outputs=("T_QUARTER",))]

    def apply_methodology_adjustments(self, ctx: CalculationContext) -> list[Output]:
        return [Output("T_DIFF", "ADJUSTMENT", "TC7", ctx.output("T_PRODUCT").value - ctx.output("T_THIRD").value, "TEST",
                       outputs=("T_PRODUCT", "T_THIRD"))]

    def calculate_net_result(self, ctx: CalculationContext) -> list[Output]:
        o = ctx.output
        net = o("T_SUM").value + o("T_DIFF").value - o("T_ZERO").value - o("T_QUARTER").value
        return [Output("T_NET", "NET", "TC8", net, "TEST", outputs=("T_SUM", "T_DIFF", "T_ZERO", "T_QUARTER"), is_final=True)]


def expected_net(lab_values: list[str], area_total: Decimal) -> Decimal:
    """The same TEST arithmetic, written out, to check the engine's Decimal result exactly."""
    with fw.localcontext(fw.DECIMAL_CONTEXT):
        s = sum((Decimal(v) for v in lab_values), Decimal(0))
        quarter = s / Decimal(4)
        return s + (area_total * Decimal(2) - quarter / Decimal(3)) - (s - s) - quarter


def fixture_module(db: Session, version_id: str, **overrides: Any) -> CalculationModule:
    v = db.get(MethodologyVersion, version_id)
    assert v is not None
    m = db.get(Methodology, v.methodology_id)
    assert m is not None
    attrs = {"methodology_code": m.code, "version_label": v.version_label, "calculation_rules_version": v.calculation_rules_version,
             **overrides}
    return type("BoundFixtureModule", (FixtureModule,), attrs)()


def resolver_for(module: CalculationModule) -> Resolver:
    return lambda code, label: module if (code, label) == (module.methodology_code, module.version_label) else None


def as_principal(db: Session, actor: Actor) -> tuple[Principal, RequestContext]:
    return load_principal(db, actor.user, None), RequestContext(request_id="test-calc", user_id=actor.user.id)


@dataclass
class CalcCtx:
    x: LabCtx
    analyst: Actor
    qa: Actor                       # QA officer (calculation.review + calculation.approve)
    dataset: dict | None
    results: list[dict]
    module: CalculationModule
    resolver: Resolver
    lab_values: list[str]

    @property
    def project_id(self) -> str:
        return str(self.x.c.project["id"])

    @property
    def period_id(self) -> str:
        return str(self.x.period["id"])


def approve_dataset(client: TestClient, x: LabCtx) -> dict:
    c = x.c
    ds = client.post(f"{MRV}/datasets", headers=c.mrv.headers, json={"monitoring_period_id": x.period["id"]}).json()
    assert client.post(f"{MRV}/datasets/{ds['id']}/submit", headers=c.mrv.headers, json={"reason": "collection complete"}).status_code == 200
    assert client.post(f"{MRV}/qa/{ds['id']}/start", headers=c.t.qa.headers).status_code == 200
    r = client.post(f"{MRV}/qa/{ds['id']}/complete", headers=c.t.qa.headers, json={"result": "PASS", "notes": "all checks pass"})
    assert r.status_code == 200, r.text
    r = client.post(f"{MRV}/datasets/{ds['id']}/approve", headers=c.t.qa.headers, json={"reason": "dataset approved"})
    assert r.status_code == 200, r.text
    return r.json()


def calc_scenario(db: Session, client: TestClient, lon: float, lat: float, id_number: str, *, rules: list[dict] | None = None,
                  approve_results: int | None = None, approve_ds: bool = True, values: tuple[str, ...] = ("1.5", "2.25"),
                  text_value: str = "<0.05") -> CalcCtx:
    x = lab_project(db, client, lon, lat, id_number, rules=rules or [SOC_RULE], calculation_rules=FIXTURE_RULES)
    c = x.c
    plan = next(p for p in client.get(f"{MRV}/plans", headers=c.mrv.headers, params={"project_id": c.project["id"]}).json()
                if p["status"] == "APPROVED")
    till = next(m for m in plan["measurements"] if m["code"] == "TILL")
    for f in c.farms:   # the plan's FARM-level activity measurement (needed for dataset QA; not a calculation input here)
        r = client.post(f"{MRV}/monitoring-records", headers=c.collector.headers, json={
            "monitoring_period_id": x.period["id"], "measurement_id": till["id"], "farm_id": f["id"], "value": "REDUCED",
            "observed_on": date.today().isoformat()})
        assert r.status_code == 201, r.text
    samples = [register(client, x, fc) for fc in x.fcs]
    for s in samples:
        seal(client, x, s)
    receive(client, x, ship(client, x, samples), samples)
    results: list[dict] = []
    n = len(samples) if approve_results is None else approve_results
    for i, s in enumerate(samples):
        detail = client.get(f"{LABV}/samples/{s['id']}", headers=x.tech.headers).json()
        for t in detail["tests"]:
            code = t["rule"]["rule_code"]
            assert client.post(f"{LABV}/tests/{t['id']}/start", headers=x.tech.headers, json={}).status_code == 200
            body = ({"result_type": "NUMERIC", "value_number": values[i], "unit": "t C/ha"} if code == "SOC"
                    else {"result_type": "TEXT", "value_text": text_value, "unit": None})
            r = client.post(f"{LABV}/tests/{t['id']}/results", headers=x.tech.headers, json={**body, "analysed_at": now_iso(1)})
            assert r.status_code == 201, r.text
            res = r.json()
            client.post(f"{LABV}/results/{res['id']}/report", headers=x.tech.headers, files={"file": ("r.pdf", b"%PDF-1.4\n%TEST\n%%EOF\n",
                                                                                                        "application/pdf")})
            assert client.post(f"{LABV}/results/{res['id']}/submit", headers=x.tech.headers).status_code == 200
            if i < n:
                q = qa(client, x, res["id"], ack=code != "SOC")
                assert q.status_code == 200 and q.json()["result"]["status"] == "APPROVED", q.text
                results.append({**q.json()["result"], "rule_code": code, "sample_id": s["id"]})
    ds = approve_dataset(client, x) if approve_ds else None
    analyst = staff(db, client, c.t.org, "CALCULATION_ANALYST")
    module = fixture_module(db, c.version_id)
    return CalcCtx(x, analyst, c.t.qa, ds, results, module, resolver_for(module), list(values[:n]))


def lab_results(client: TestClient, x: LabCtx) -> list[dict]:
    return client.get(f"{LAB}/results", headers=x.c.mrv.headers, params={"project_id": x.c.project["id"], "status": "ALL"}).json()
