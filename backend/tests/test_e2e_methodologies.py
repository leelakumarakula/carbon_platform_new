"""End-to-end API tests of the registered calculation modules not covered by test_e2e_vm0042_coffee.py: VM0044 biochar, VM0051 and
CCTS AG04.002 rice, GS 402 (Approach 3 and Approach 1), GS 403 and CCTS FR05.002 / FR05.001 afforestation.

Every scenario goes through the HTTP API (SQL Server test database, rolled back after each test) the way a user does it in the app:
standard and activity -> methodology version with the REAL module selected and approved by a second specialist -> farmer onboarded
(KYC, consent, ACTIVE) -> farm drawn, owned and GIS-verified with its land-use history -> project with carbon rights, eligibility and
the methodology locked -> MRV plan from the module's rules -> strata, sampling plots, laboratory results and monitoring records ->
dataset QA and approval -> calculation run frozen and executed -> calculation QA and approval.

The values are those of the module unit tests (test_vm0044_biochar.py, test_rice.py, test_ccts_ar.py, ...) so the outputs are checked
against the same independent hand calculations; every run is also re-executed from its frozen snapshot (same output hash).
All values are TEST values, not project data. The credits-to-payout steps are methodology-independent and covered by the VM0042 test.
"""
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.calculation import framework as fw
from app.calculation import registry
from app.core.config import get_settings
from tests.conftest import Actor
from tests.phase2 import PDF, create_farm, set_boundary, square, staff, upload
from tests.phase3 import PR, Team, active_farmer, add_farm, create_project, rights, team
from tests.phase4 import M, methodology, specialists
from tests.phase5 import MRV, MrvCtx, approved_plan, approved_stratum
from tests.phase6 import LAB, LABV

V = "/api/v1"
CALC = f"{V}/calculations"
UTC = timezone.utc


@pytest.fixture(autouse=True)
def _bulk_api_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hundreds of API calls per test from one client address: the per-IP / per-user limits are raised for these tests only."""
    s = get_settings()
    for name in ("GLOBAL_RATE_LIMIT_PER_MINUTE", "USER_RATE_LIMIT_PER_MINUTE", "ORGANIZATION_RATE_LIMIT_PER_MINUTE",
                 "UPLOAD_RATE_LIMIT_PER_MINUTE", "API_BURST_RATE_LIMIT_PER_MINUTE"):
        monkeypatch.setattr(s, name, 1_000_000)


def ok(r: Any, *codes: int) -> Any:
    assert r.status_code in (codes or (200, 201)), r.text
    return r.json()


def now_iso(delta_min: int = 0) -> str:
    return (datetime.now(UTC) + timedelta(minutes=delta_min)).isoformat()


def module_of(code: str) -> Any:
    """The registered module (Any: the GS 402 modules carry activity / seed / reference_depth_cm class attributes)."""
    m = registry.by_code(code)
    assert m is not None, code
    return m


# ---------------------------------------------------------------- scenario description
@dataclass(frozen=True)
class Spec:
    module: str                      # registered calculation module code
    methodology: str                 # methodology code the module implements
    version: str                     # version label
    standard: tuple[str, str, str]   # code, name, owner
    activity: tuple[str, str]        # code, name
    land_use: str                    # farm land-use history (and the applicability rule)
    project_type: str
    region: tuple[str, str, str]     # village, district, state
    lon: float
    lat: float
    start: str = "2025-06-01"        # project / crediting / participation start


@dataclass
class Run:
    spec: Spec
    c: MrvCtx
    analyst: Actor
    farmer: dict
    farms: list[dict]
    version: dict
    measurements: dict[str, dict]
    periods: dict[int, dict] = field(default_factory=dict)
    records: dict[int, list[dict]] = field(default_factory=dict)
    strata: dict[str, dict] = field(default_factory=dict)

    @property
    def t(self) -> Team:
        return self.c.t

    @property
    def pid(self) -> str:
        return str(self.c.project["id"])


# ---------------------------------------------------------------- set-up through the API
def methodology_version(db: Session, client: TestClient, admin: Actor, s: Spec) -> tuple[Actor, dict, str, str]:
    """Standard + activity (platform admin), methodology version with the real module selected, approved by a second specialist."""
    std = ok(client.post(f"{V}/standards", headers=admin.headers, json={
        "code": s.standard[0], "name": s.standard[1], "owner_name": s.standard[2], "program_type": "VOLUNTARY"}), 201)
    act = ok(client.post(f"{V}/activities", headers=admin.headers, json={
        "code": s.activity[0], "name": s.activity[1], "standard_ids": [std["id"]]}), 201)
    author, approver = specialists(db, client)
    m = methodology(client, author, std["id"], [act["id"]], s.methodology, name=f"{s.methodology} (e2e)", owner_name=s.standard[2])
    v = ok(client.post(f"{M}/{m['id']}/versions", headers=author.headers, json={
        "version_label": s.version, "effective_from": "2020-01-01", "source_name": f"{s.methodology} v{s.version} (TEST e2e)"}), 201)
    vid = v["id"]
    opts = ok(client.get(f"{M}/versions/{vid}/calculation-modules", headers=author.headers))
    assert s.module in [o["code"] for o in opts if o["compatible"]], opts
    ok(client.post(f"{M}/versions/{vid}/calculation-module", headers=author.headers,
                   json={"module_code": s.module, "reason": f"Registered module {s.module}"}))
    for rule in ({"rule_code": "A1", "title": "Project in India", "category": "COUNTRY", "fact_key": "country", "operator": "IN",
                  "expected_value": ["IN"]},
                 {"rule_code": "A2", "title": f"Land is {s.land_use.lower()}", "category": "LAND_USE", "fact_key": "land_use_current",
                  "operator": "ALL_IN", "expected_value": [s.land_use]}):
        ok(client.post(f"{M}/versions/{vid}/rules/applicability", headers=author.headers, json=rule), 201)
    ok(client.post(f"{M}/versions/{vid}/submit", headers=author.headers, json={"reason": "ready for approval"}))
    assert client.post(f"{M}/versions/{vid}/approve", headers=author.headers, json={"reason": "own work"}).status_code == 403
    v = ok(client.post(f"{M}/versions/{vid}/approve", headers=approver.headers, json={"reason": "checked against the source"}))
    assert v["status"] == "APPROVED" and v["calculation_module_code"] == s.module, v
    return author, v, std["id"], act["id"]


def verified_farm(client: TestClient, t: Team, s: Spec, farmer: dict, name: str, lon: float, lat: float, size: float) -> dict:
    """Drawn boundary, land record, ownership, five years of land-use history, GIS verification."""
    h = t.agent.headers
    farm = create_farm(client, h, farmer["id"], name=name, village=s.region[0], district=s.region[1], state=s.region[2],
                       declared_area_hectares=f"{size * size * 1.21e4:.2f}")
    fid = farm["id"]
    set_boundary(client, h, fid, square(lon, lat, size))
    doc = ok(upload(client, h, f"{V}/farms/{fid}/documents", "LAND_RECORD", PDF, "7-12.pdf", f"Land record {name}"), 201)["id"]
    own = ok(client.post(f"{V}/farms/{fid}/ownership", headers=h, json={
        "owner_type": "FARMER", "owner_farmer_id": farmer["id"], "operator_relationship": "OWNER", "ownership_share_pct": "100",
        "title_reference": f"Survey {name}", "evidence_document_id": doc}), 201)
    for url, actor, body in ((f"{V}/farms/{fid}/submit", t.agent, {"reason": "farm ready for review"}),
                             (f"{V}/farms/{fid}/start-review", t.gis, {"reason": "start GIS review"}),
                             (f"{V}/farms/{fid}/ownership/{own['id']}/review", t.gis, {"status": "VERIFIED", "notes": "title matches"}),
                             (f"{V}/farms/{fid}/verify", t.gis, {"reason": "boundary and tenure confirmed"})):
        ok(client.post(url, headers=actor.headers, json=body))
    for year in range(2020, 2025):
        ok(client.post(f"{V}/farms/{fid}/history/land", headers=h, json={"year": year, "land_use": s.land_use}), 201)
    got = ok(client.get(f"{V}/farms/{fid}", headers=t.gis.headers))
    assert got["status"] == "VERIFIED", got
    return got


def setup(db: Session, client: TestClient, admin: Actor, s: Spec, sizes: tuple[float, ...] = (0.0015,), **plan: Any) -> Run:
    """Steps 1-5: team, methodology version, farmer and verified farms, locked project, approved MRV plan from the module's rules."""
    t = team(db, client)
    author, v, std_id, act_id = methodology_version(db, client, admin, s)
    farmer = active_farmer(client, t, f"7{abs(hash(s.module)) % 10**11:011d}", full_name=f"{s.module} e2e farmer", village=s.region[0],
                           district=s.region[1], state=s.region[2])
    assert farmer["status"] == "ACTIVE", farmer
    farms, lon = [], s.lon
    for i, size in enumerate(sizes):                                   # side by side, ~size x size degrees each
        farms.append(verified_farm(client, t, s, farmer, f"{s.module} plot {i + 1}", lon, s.lat, size))
        lon += size * 1.5
    p = create_project(client, t, name=f"{s.module} e2e project", project_type=s.project_type, region=f"{s.region[1]}, {s.region[2]}",
                       start_date=s.start)
    pid, h = p["id"], t.pm.headers
    ok(client.post(f"{PR}/{pid}/start-data-collection", headers=h, json={"reason": "collect farm data"}))
    for f in farms:
        ok(add_farm(client, t, pid, f["id"], participation_start=s.start,
                    carbon_rights=rights(f"Carbon rights clause, {f['name']}", effective_from=s.start)), 201)
    for path, body in (("standard", {"standard_id": std_id}), ("activity", {"activity_id": act_id}),
                       ("crediting-period", {"start_date": s.start, "end_date": "2035-05-31"})):
        ok(client.post(f"{PR}/{pid}/{path}", headers=h, json=body))
    ok(client.patch(f"{PR}/{pid}/baseline", headers=h, json={"period_start": "2022-06-01", "period_end": "2025-05-31"}))
    ok(client.post(f"{PR}/{pid}/submit", headers=h, json={"reason": "complete for eligibility review"}))
    ok(client.post(f"{PR}/{pid}/boundary/review", headers=t.gis.headers, json={"decision": "ACCEPTED", "notes": "boundaries ok"}))
    for cr in ok(client.get(f"{PR}/{pid}/carbon-rights", headers=t.qa.headers)):
        ok(client.post(f"{PR}/{pid}/carbon-rights/{cr['id']}/review", headers=t.qa.headers, json={"status": "VERIFIED", "notes": "clause seen"}))
    ok(client.post(f"{PR}/{pid}/approve-eligibility", headers=t.qa.headers, json={"reason": "eligible"}))
    ok(client.post(f"{PR}/{pid}/confirm-activity", headers=h, json={"reason": "activity confirmed"}))
    ev = ok(client.post(f"{PR}/{pid}/methodology/candidates", headers=h, json={"declared_facts": {}}), 201)
    cand = next(x for x in ev["candidates"] if x["methodology_version_id"] == v["id"])
    assert cand["outcome"] == "APPLICABLE", cand
    ok(client.post(f"{PR}/{pid}/methodology/reviews", headers=author.headers, json={
        "evaluation_result_id": cand["id"], "recommendation": "RECOMMENDED", "notes": f"Applicable; module {s.module}",
        "evidence_acknowledged": True}), 201)
    ok(client.post(f"{PR}/{pid}/methodology/confirm", headers=h, json={"evaluation_result_id": cand["id"], "notes": "confirmed and locked"}))
    project = ok(client.get(f"{PR}/{pid}", headers=h))
    assert project["methodology_status"] == "CONFIRMED", project
    org = t.org
    c = MrvCtx(t, staff(db, client, org, "MRV_MANAGER"), staff(db, client, org, "FIELD_SUPERVISOR"), staff(db, client, org, "FIELD_AGENT"),
               staff(db, client, org, "FIELD_AGENT"), project, farms, v["id"])
    pl = approved_plan(client, c, monitoring_start=s.start, monitoring_end="2035-05-31", measurements=[],
                       required_evidence="Field photos, GPS, records", **plan)
    expected = {r["rule_code"] for r in module_of(s.module).monitoring_rule_definitions}
    measurements = {m["code"]: m for m in pl["measurements"]}
    assert expected <= set(measurements), expected - set(measurements)
    return Run(s, c, staff(db, client, org, "CALCULATION_ANALYST"), farmer, farms, v, measurements)


def open_period(client: TestClient, k: Run, n: int, dates: tuple[str, str], purpose: str = "MONITORING") -> dict:
    c = k.c
    mp = ok(client.post(f"{MRV}/monitoring-periods", headers=c.mrv.headers, json={
        "project_id": k.pid, "name": f"Period {n}", "purpose": purpose, "start_date": dates[0], "end_date": dates[1]}), 201)
    for action in ("plan", "start", "open-collection"):
        mp = ok(client.post(f"{MRV}/monitoring-periods/{mp['id']}/{action}", headers=c.mrv.headers, json={"reason": f"{action} now"}))
    assert mp["status"] == "DATA_COLLECTION"
    k.periods[n] = mp
    return mp


def record(client: TestClient, k: Run, n: int, code: str, value: Any, observed_on: str, phase: str = "MONITORING", *,
           farm: dict | None = None, stratum: dict | None = None, point: dict | None = None) -> dict:
    m = k.measurements[code]
    r = ok(client.post(f"{MRV}/monitoring-records", headers=k.c.mrv.headers, json={
        "monitoring_period_id": k.periods[n]["id"], "measurement_id": m["id"], "farm_id": farm["id"] if farm else None,
        "stratum_id": stratum["id"] if stratum else None, "sampling_point_id": point["id"] if point else None,
        "measurement_phase": phase, "value": str(value), "observed_on": observed_on, "source": "DOCUMENT", "notes": "e2e register"}), 201)
    k.records.setdefault(n, []).append(r)
    return r


def approve_dataset(client: TestClient, k: Run, n: int) -> dict:
    c = k.c
    ds = ok(client.post(f"{MRV}/datasets", headers=c.mrv.headers, json={"monitoring_period_id": k.periods[n]["id"]}), 201)
    ok(client.post(f"{MRV}/datasets/{ds['id']}/submit", headers=c.mrv.headers, json={"reason": "period complete"}))
    ok(client.post(f"{MRV}/qa/{ds['id']}/start", headers=c.t.qa.headers))
    checks = {x["key"]: x["result"] for x in ok(client.get(f"{MRV}/qa/{ds['id']}", headers=c.t.qa.headers))["checks"]}
    assert "FAIL" not in checks.values(), checks
    ok(client.post(f"{MRV}/qa/{ds['id']}/complete", headers=c.t.qa.headers, json={"result": "PASS", "notes": "all checks pass"}))
    ds = ok(client.post(f"{MRV}/datasets/{ds['id']}/approve", headers=c.t.qa.headers, json={"reason": "dataset approved"}))
    assert ds["status"] == "APPROVED", ds
    return ds


def calculate(client: TestClient, k: Run, n: int) -> tuple[dict, dict[str, float], dict]:
    """Create -> freeze -> execute (analyst); the run must be CALCULATED with the real module. Returns (run, outputs, frozen inputs)."""
    run = ok(client.post(f"{CALC}/runs", headers=k.analyst.headers, json={"project_id": k.pid, "monitoring_period_id": k.periods[n]["id"]}), 201)
    frozen = ok(client.post(f"{CALC}/runs/{run['id']}/freeze", headers=k.analyst.headers))
    assert frozen["status"] == "INPUTS_FROZEN" and frozen["module_code"] == k.spec.module, frozen
    run = ok(client.post(f"{CALC}/runs/{run['id']}/execute", headers=k.analyst.headers))
    assert run["status"] == "CALCULATED", run
    outs = ok(client.get(f"{CALC}/runs/{run['id']}/outputs", headers=k.analyst.headers))
    inp = ok(client.get(f"{CALC}/runs/{run['id']}/inputs", headers=k.analyst.headers))
    module = module_of(k.spec.module)
    assert fw.execute(module, inp["snapshot"]).output_sha256 == run["output_sha256"] == outs["output_sha256"]
    assert {o["rule_code"] for o in outs["outputs"]} == set(module.rules)
    return run, {o["output_code"]: float(o["value"]) for o in outs["outputs"]}, inp


def approve_run(client: TestClient, k: Run, run: dict) -> None:
    """Calculation QA by the QA officer (never the analyst) -> APPROVED; the project becomes CALCULATED."""
    qa = k.t.qa
    ok(client.post(f"{CALC}/runs/{run['id']}/submit", headers=k.analyst.headers))
    assert client.post(f"{CALC}/runs/{run['id']}/approve", headers=k.analyst.headers, json={"reason": "own run"}).status_code == 403
    ok(client.post(f"{CALC}/qa/{run['id']}/start", headers=qa.headers))
    view = ok(client.post(f"{CALC}/qa/{run['id']}/complete", headers=qa.headers, json={"result": "PASS", "notes": "checked against hand calc"}))
    assert "FAIL" not in {x["result"] for x in view["checks"]}, view["checks"]
    assert ok(client.post(f"{CALC}/runs/{run['id']}/approve", headers=qa.headers, json={"reason": "calculation approved"}))["status"] == "APPROVED"
    assert ok(client.get(f"{PR}/{k.pid}", headers=k.t.pm.headers))["status"] == "CALCULATED"


def sources(inp: dict, source_type: str) -> list[dict]:
    return [x for x in inp["inputs"] if x["source_type"] == source_type]


# ---------------------------------------------------------------- VM0044 v1.2 biochar
VM0044 = Spec("VM0044-V1.2", "VM0044", "1.2", ("VCS", "Verified Carbon Standard", "Verra"), ("BIOCHAR", "Biochar utilization"),
              "CROPLAND", "AGRICULTURAL_LAND_MANAGEMENT", ("Pimpalgaon", "Nashik", "Maharashtra"), 73.95, 20.17)


def test_vm0044_biochar_farmer_to_calculation(client: TestClient, db: Session, admin: Actor) -> None:
    """A biochar kiln on the farmer's land; soil application on the enrolled farm. Values of test_vm0044_biochar._snap()."""
    k = setup(db, client, admin, VM0044)
    open_period(client, k, 1, ("2026-01-01", "2026-12-31"))
    batches = {"V44_PRODUCED": ["120"], "V44_USED_SOIL": ["70", "30"], "V44_USED_NONSOIL": ["10"], "V44_FCP": ["0.72"],
               "V44_HC_RATIO": ["0.35", "0.41"], "V44_TEMP": ["620"], "V44_TECH": ["HIGH"], "V44_PE_PRETREAT": ["4.5"], "V44_PE_AUX": ["1.5"],
               "V44_PE_PROCESSING": ["0.8"], "V44_LE_TRANSPORT": ["2.2"]}
    for code, values in batches.items():
        for i, value in enumerate(values):
            record(client, k, 1, code, value, f"2026-0{i + 1}-15")
    approve_dataset(client, k, 1)
    run, val, inp = calculate(client, k, 1)
    # hand calculation (test_vm0044_biochar.test_high_technology_matches_hand_calculation): PR_de 0.89 at 620 degC, high technology
    used = 110.0
    cc = used * 0.72 * 0.89
    pe = (4.5 + 0 + 1.5) * used / 120 + 0.8
    er = cc * 44 / 12 - pe - 2.2
    assert len(sources(inp, "MONITORING_RECORD")) == len(k.records[1]) == 13
    assert val["VCU_TOTAL"] == math.floor(er) and run["net_result"] == str(math.floor(er)) and math.floor(er) > 0, val
    approve_run(client, k, run)


# ---------------------------------------------------------------- VM0051 v1.1 QA3 and CCTS AG04.002 v1.0 rice
VM0051 = Spec("VM0051-V1.1-QA3", "VM0051", "1.1", ("VCS", "Verified Carbon Standard", "Verra"), ("RICE", "Improved rice management"),
              "CROPLAND", "RICE_CULTIVATION", ("Karjat", "Raigad", "Maharashtra"), 73.33, 18.91)
AG04 = Spec("CCTS-AG04.002", "BM-AG04.002", "1.0", ("CCTS", "Carbon Credit Trading Scheme (offset mechanism)", "Bureau of Energy Efficiency"),
            ("RICE", "Improved rice management"), "CROPLAND", "RICE_CULTIVATION", ("Karjat", "Raigad", "Maharashtra"), 73.33, 18.91)
# test_rice.PROJECT / BASELINE, seasons one year earlier (a record cannot be dated in the future): kharif and rabi seasons of 2025-26
RICE_SEASONS = {"2025-10-20": {"AREA": 2.0, "DAYS": 110, "WATER": "MULTIPLE", "PRESEASON": "SHORT", "STRAW": 3.0, "STRAW_TIMING": "LONG",
                               "FYM": 2.0, "N": 120},
                "2026-04-10": {"AREA": 2.0, "DAYS": 100, "WATER": "SINGLE", "PRESEASON": "SHORT", "N": 100}}
RICE_BASELINE = [{"WATER": "CONTINUOUS", "PRESEASON": "SHORT", "DAYS": 115, "N": 120, "FYM": 2.0},
                 {"WATER": "CONTINUOUS", "PRESEASON": "SHORT", "DAYS": 118, "N": 120, "FYM": 2.0}]


def rice_run(client: TestClient, db: Session, admin: Actor, s: Spec, diesel: bool) -> tuple[Run, dict, dict[str, float]]:
    """A paddy farmer's field: two seasons in the reporting period (one record per parameter and season, same observed-on date) and
    two look-back years (BASELINE), the IPCC region at project level."""
    k = setup(db, client, admin, s)
    farm = k.farms[0]
    open_period(client, k, 1, ("2025-06-01", "2026-05-31"))
    for season, values in RICE_SEASONS.items():
        for var, value in {**values, **({"DIESEL": 40} if diesel and season == "2025-10-20" else {})}.items():
            record(client, k, 1, f"RI_{var}", value, season, "PROJECT", farm=farm)
    for i, values in enumerate(RICE_BASELINE):
        for var, value in {**values, **({"DIESEL": 50} if diesel else {})}.items():
            record(client, k, 1, f"RI_{var}", value, f"202{i}-10-15", "BASELINE", farm=farm)
    record(client, k, 1, "RI_REGION", "SOUTH_ASIA", "2025-06-01")
    approve_dataset(client, k, 1)
    run, val, inp = calculate(client, k, 1)
    rows = sources(inp, "MONITORING_RECORD")
    assert {x["source_id"] for x in rows} == {r["id"] for r in k.records[1]}
    approve_run(client, k, run)
    return k, run, val


def test_vm0051_rice_farmer_to_calculation(client: TestClient, db: Session, admin: Actor) -> None:
    from tests.test_rice import _expected
    k, run, val = rice_run(client, db, admin, VM0051, diesel=True)
    e = _expected(28, 265)
    fuel = (50 - 40) * 0.002886 + (50 - 0) * 0.002886               # second season has no diesel record: baseline 50 - 0
    er = fuel + (e["ch4_b"] - e["ch4_p"]) * 0.85 + e["d_n2o"] * 0.85 - e["drying"]
    assert val["CH4_BSL"] == pytest.approx(e["ch4_b"], rel=1e-9) and val["CH4_WP"] == pytest.approx(e["ch4_p"], rel=1e-9)
    assert val["PE_DRYING"] == pytest.approx(e["drying"], rel=1e-9)
    assert val["ER_NET"] == pytest.approx(er, rel=1e-9)
    assert val["CREDITS"] == math.floor(er) and run["net_result"] == str(math.floor(er))


def test_ccts_ag04002_rice_farmer_to_calculation(client: TestClient, db: Session, admin: Actor) -> None:
    from tests.test_rice import _expected
    k, run, val = rice_run(client, db, admin, AG04, diesel=False)
    e = _expected(29.8, 273)
    er = ((e["ch4_b"] - e["ch4_p"]) + 0 - e["drying"]) * 0.85       # N2O decrease not credited; 15 % once on the whole reduction
    assert val["D_N2O_SOIL"] == 0
    assert val["ER_NET"] == pytest.approx(er, rel=1e-9)
    assert val["CREDITS"] == math.floor(er) and run["net_result"] == str(math.floor(er))


# ---------------------------------------------------------------- GS 402 v1.0 SOC framework
GS402 = ("GS", "Gold Standard for the Global Goals", "Gold Standard Foundation")
GS_ACTIVITY = {"402.1": ("IALM", "Improved agricultural land management"), "402.4": ("ZT", "Zero tillage"),
               "402.6": ("CC", "Cover crops")}


def gs402(module: str) -> Spec:
    act = GS_ACTIVITY[module_of(module).activity]
    return Spec(module, "GS402", "1.0", GS402, act, "CROPLAND", "AGRICULTURAL_LAND_MANAGEMENT", ("Sinnar", "Nashik", "Maharashtra"), 74.0, 19.85)


GS_FACTORS = {"SOC_REF": 47.0, "F_LU": 0.83, "F_MG_BL": 1.00, "F_I_BL": 1.00, "F_MG_PR": 1.04, "F_I_PR": 1.00}
GS_U = {"F_LU": 11.0, "F_MG_PR": 7.0}
# 402.6 Eq. 7: S x (EF_SP + EF_ST x Dist). EF_ST x Dist as in test_gs_soc_402 (1e-7 x 300), entered as 1e-6 x 30: monitoring records
# keep 6 decimals (mrv value_number Numeric(18, 6)), so 0.0000001 would be stored as 0
GS_SEED = 1500 * (0.0008 + 0.000001 * 30)


def gs_farm_activity(client: TestClient, k: Run, n: int, project_day: str) -> None:
    """test_gs_soc_402._activities: two baseline years and the project year of fertiliser N, diesel, agrochemicals and yield (unchanged:
    no leakage); the diesel emission factor and the Paris-alignment status at project level; cover crops: seed and its factors."""
    farm = k.farms[0]
    for code, bsl, prj in (("GS_FERT_N", (100, 120), 150), ("GS_DIESEL", (900, 1100), 1200), ("GS_AGROCHEM", (1, 1), 0.5),
                           ("GS_YIELD", (4000, 4000), 4000)):
        for year, value in zip(("2023-06-01", "2024-06-01"), bsl, strict=True):
            record(client, k, n, code, value, year, "BASELINE", farm=farm)
        record(client, k, n, code, prj, project_day, "PROJECT", farm=farm)
    record(client, k, n, "GS_FEF_DIESEL", "0.00268", project_day)
    record(client, k, n, "GS_PAA", "YES", project_day)
    if module_of(k.spec.module).seed:
        record(client, k, n, "GS_CC_SEED", 1500, project_day, "PROJECT", farm=farm)
        for code, factor in (("GS_CC_EF_SP", "0.0008"), ("GS_CC_EF_ST", "0.000001"), ("GS_CC_DIST", "30")):
            record(client, k, n, code, factor, project_day)


@pytest.mark.parametrize("module", ["GS402-IT-A3", "GS402-CC-A3"])
def test_gs402_approach3_farmer_to_calculation(client: TestClient, db: Session, admin: Actor, module: str) -> None:
    """IPCC stock-change factors per stratum (no sampling): test_gs_soc_402.test_improved_tillage_approach3 on the drawn farm area;
    cover crops add the seed emissions (402.6 Eq. 7)."""
    from itertools import product

    from app.calculation.modules.gs_soc_402 import FACTORS
    from tests.test_gs_soc_402 import _credits, _pe
    k = setup(db, client, admin, gs402(module), sizes=(0.0064,))                 # ~50 ha
    s1 = approved_stratum(client, k.c, "S1", [k.farms[0]["id"]], name="Reduced tillage, tropical moist")
    open_period(client, k, 1, ("2025-06-01", "2026-05-31"))
    for f, v in GS_FACTORS.items():
        record(client, k, 1, f"GS_{f}", v, "2025-06-01", stratum=s1)
    for f, v in GS_U.items():
        record(client, k, 1, f"GS_U_{f}", v, "2025-06-01", stratum=s1)
    record(client, k, 1, "GS_T_BL", 20, "2025-06-01", stratum=s1)
    record(client, k, 1, "GS_T_PR", 3, "2026-05-31", stratum=s1)
    gs_farm_activity(client, k, 1, "2025-09-01")
    approve_dataset(client, k, 1)
    run, val, inp = calculate(client, k, 1)
    (area_row,) = sources(inp, "STRATUM_AREA")
    area = float(area_row["value"])
    assert 45 < area < 55, area

    def dsoc(x: dict) -> float:
        return x["SOC_REF"] * x["F_LU"] * (x["F_MG_PR"] * x["F_I_PR"] - x["F_MG_BL"] * x["F_I_BL"]) * (min(3, 20) - min(2, 20)) / 20
    ranges = []
    for f in FACTORS:
        half = GS_FACTORS[f] * GS_U[f] / 200 * 1.675 if f in GS_U else GS_FACTORS[f] * 0.5 * 3
        ranges.append((max(0.0, GS_FACTORS[f] - half), GS_FACTORS[f] + half))
    vals = [dsoc(dict(zip(FACTORS, c, strict=True))) for c in product(*ranges)]
    d = dsoc(GS_FACTORS) * area
    unc = min(1.0, (max(vals) - min(vals)) * area / (2 * d))
    ud = min(1.0, max(0.0, unc - 0.2))
    pe = _pe()["total"] + (GS_SEED if module == "GS402-CC-A3" else 0.0)
    c = _credits(d, ud, pe, 0.0)
    assert val["DSOC_C"] == pytest.approx(d, rel=1e-9) and val["UD"] == pytest.approx(ud, rel=1e-9)
    assert val["PE_TOTAL"] == pytest.approx(pe, rel=1e-9) and val["LK_TOTAL"] == 0
    assert val["GS_VER_TOTAL"] == c["vers"] and run["net_result"] == str(c["vers"]), (val, c)
    approve_run(client, k, run)


def soil_campaign(client: TestClient, k: Run, n: int, lab: dict[str, Any], profiles: list[list[tuple]], when: str) -> None:
    """Soil sampling design (3 points in S1) -> field collection with core details (21.5 mm probe, 4 cores, 0-50 cm) -> one sample per
    depth increment -> custody to the laboratory -> OC and fine-soil mass per sample -> laboratory QA (test_gs_soc_402.PROFILES)."""
    from tests.phase5 import approved_design
    from tests.test_gs_soc_402 import CORES, D_MM
    c = k.c
    d = approved_design(client, c, k.periods[n]["id"], [{"stratum_id": k.strata["S1"]["id"], "sample_count": 3}], code=f"SOIL-P{n}",
                        name=f"Soil campaign {n}", depth_bottom_cm="50", sampling_method=f"Auger {D_MM} mm, {CORES}-core composite")
    pts = sorted(ok(client.post(f"{MRV}/sampling-designs/{d['id']}/generate-points", headers=c.mrv.headers), 201)["points"],
                 key=lambda p: p["sequence"])
    assert len(pts) == 3
    ok(client.post(f"{MRV}/sampling-points/assign", headers=c.supervisor.headers,
                   json={"point_ids": [p["id"] for p in pts], "collector_id": str(c.collector.user.id)}))
    samples: list[tuple[dict, float, float]] = []                  # (sample, fine mass g, OC g/kg)
    for p, prof in zip(pts, profiles, strict=True):
        fc = ok(client.post(f"{MRV}/field-collections", headers=c.collector.headers, json={"sampling_point_id": p["id"]}), 201)
        ok(client.patch(f"{MRV}/field-collections/{fc['id']}", headers=c.collector.headers, json={
            "collected_at": when, "gps_latitude": float(p["latitude"]), "gps_longitude": float(p["longitude"]), "gps_accuracy_m": "3",
            "actual_depth_top_cm": "0", "actual_depth_bottom_cm": "50", "probe_diameter_mm": str(D_MM), "cores_count": CORES,
            "sample_quantity": "1.2", "sample_unit": "kg", "observations": "Black cotton soil, residue retained",
            "checklist": dict.fromkeys(fc["required_checklist"], True)}))
        ok(client.post(f"{MRV}/evidence", headers=c.collector.headers, files={"file": ("pit.png", PNG, "image/png")},
                       data={"project_id": k.pid, "entity_type": "FIELD_COLLECTION", "entity_id": fc["id"], "evidence_type": "FIELD_PHOTO",
                             "latitude": str(p["latitude"]), "longitude": str(p["longitude"]), "description": "cores"}), 201)
        ok(client.post(f"{MRV}/field-collections/{fc['id']}/submit", headers=c.collector.headers))
        fc = ok(client.post(f"{MRV}/field-collections/{fc['id']}/review", headers=c.supervisor.headers,
                            json={"decision": "ACCEPTED", "notes": "cores and depth checked"}))
        for top, bottom, mass, oc in prof:
            s = ok(client.post(f"{LAB}/samples", headers=c.collector.headers, json={
                "field_collection_id": fc["id"], "description": f"Soil {top}-{bottom} cm", "depth_top_cm": str(top),
                "depth_bottom_cm": str(bottom), "quantity": "0.6", "quantity_unit": "kg", "container_label": f"{p['point_code']}-{top}"}), 201)
            assert s["test_count"] == 2, s                          # GS_OC + GS_SOIL_MASS, automatically
            ok(client.post(f"{LAB}/samples/{s['id']}/seal", headers=c.collector.headers, json={"seal_number": f"S{n}-{p['point_code']}-{top}"}))
            samples.append((s, mass, oc))
    sh = ok(client.post(f"{LAB}/shipments", headers=c.supervisor.headers, json={
        "project_id": k.pid, "laboratory_org_id": str(lab["org"].id), "carrier": "Nashik courier"}), 201)
    ok(client.post(f"{LAB}/shipments/{sh['id']}/items", headers=c.supervisor.headers, json={"sample_ids": [s["id"] for s, *_ in samples]}))
    ok(client.post(f"{LAB}/shipments/{sh['id']}/dispatch", headers=c.supervisor.headers, json={}))
    seals = {s["id"]: ok(client.get(f"{LAB}/samples/{s['id']}", headers=c.supervisor.headers))["seal_number"] for s, *_ in samples}
    tech, lqa = lab["tech"], lab["qa"]
    ok(client.post(f"{LABV}/shipments/{sh['id']}/receive", headers=tech.headers, json={"items": [
        {"sample_id": s["id"], "accepted": True, "condition": "intact", "seal_number_observed": seals[s["id"]]} for s, *_ in samples]}))
    for i, (s, mass, oc) in enumerate(samples):
        ok(client.post(f"{LABV}/samples/{s['id']}/accession", headers=tech.headers, json={"accession_number": f"NK{n}-{i + 1:03d}"}))
        for test in ok(client.get(f"{LABV}/samples/{s['id']}", headers=tech.headers))["tests"]:
            oc_test = test["rule"]["rule_code"] == "GS_OC"
            ok(client.post(f"{LABV}/tests/{test['id']}/start", headers=tech.headers,
                           json={"method_reported": "Dry combustion" if oc_test else "Oven-dry 105 C, < 2 mm"}))
            res = ok(client.post(f"{LABV}/tests/{test['id']}/results", headers=tech.headers, json={
                "result_type": "NUMERIC", "value_number": str(oc if oc_test else mass), "unit": "g/kg" if oc_test else "g",
                "analysed_at": now_iso(1)}), 201)
            ok(client.post(f"{LABV}/results/{res['id']}/report", headers=tech.headers, files={"file": ("report.pdf", PDF, "application/pdf")}))
            ok(client.post(f"{LABV}/results/{res['id']}/submit", headers=tech.headers))
            ok(client.post(f"{LABV}/qa/{res['id']}/start", headers=lqa.headers))
            q = ok(client.post(f"{LABV}/qa/{res['id']}/decision", headers=lqa.headers, json={"decision": "APPROVED", "notes": "QC ok"}))
            assert q["result"]["status"] == "APPROVED", q


@pytest.mark.parametrize("module", ["GS402-ZT-A1", "GS402-IT-A1", "GS402-CC-A1"])
def test_gs402_approach1_soil_sampling_farmer_to_calculation(client: TestClient, db: Session, admin: Actor, module: str) -> None:
    """On-site SOC measurement: project-start campaign (period 1) and remeasurement (period 2) at 3 points, laboratory OC and fine-soil
    mass per depth increment, equivalent soil mass at 50 cm (402.4) or 30 cm (402.1 / 402.6); test_gs_soc_402 hand calculation."""
    from tests.conftest import make_org
    from tests.test_gs_soc_402 import PROFILES, _credits, _measured, _pe
    mod = module_of(module)
    k = setup(db, client, admin, gs402(module), sizes=(0.0064,))
    k.strata["S1"] = approved_stratum(client, k.c, "S1", [k.farms[0]["id"]], name="Vertisol, conventional tillage before")
    lab_org = make_org(db, org_type="LABORATORY")
    lab: dict[str, Any] = {"org": lab_org, "tech": staff(db, client, lab_org, "LAB_TECHNICIAN"), "mgr": staff(db, client, lab_org, "LAB_MANAGER"),
           "qa": staff(db, client, lab_org, "LAB_MANAGER")}
    rules = {r["rule_code"]: r for r in ok(client.get(f"{LAB}/projects/{k.pid}/laboratory-rules", headers=k.c.mrv.headers))}
    assert set(rules) == {"GS_OC", "GS_SOIL_MASS"}
    e = ok(client.post(f"{LAB}/engagements", headers=k.c.mrv.headers, json={
        "project_id": k.pid, "laboratory_org_id": str(lab_org.id), "rule_ids": [r["rule_id"] for r in rules.values()]}), 201)
    ok(client.post(f"{LABV}/engagements/{e['id']}/accept", headers=lab["mgr"].headers))
    open_period(client, k, 1, ("2025-06-01", "2025-09-30"), purpose="BASELINE")
    soil_campaign(client, k, 1, lab, PROFILES["PREVIOUS"], "2025-07-15T05:00:00Z")
    approve_dataset(client, k, 1)
    # the project-start campaign alone cannot be calculated: Approach 1 requires the earlier campaign (required T0 lab variables)
    early = ok(client.post(f"{CALC}/runs", headers=k.analyst.headers, json={"project_id": k.pid, "monitoring_period_id": k.periods[1]["id"]}), 201)
    r = client.post(f"{CALC}/runs/{early['id']}/freeze", headers=k.analyst.headers)
    if r.status_code == 200:
        r = client.post(f"{CALC}/runs/{early['id']}/execute", headers=k.analyst.headers)
    assert r.status_code == 409 and r.json()["error_code"] == "PREVIOUS_PERIOD_REQUIRED", r.text
    open_period(client, k, 2, ("2025-10-01", "2026-09-30"))                     # 365 days
    soil_campaign(client, k, 2, lab, PROFILES["CURRENT"], "2026-08-01T05:00:00Z")
    gs_farm_activity(client, k, 2, "2026-03-01")
    approve_dataset(client, k, 2)
    run, val, inp = calculate(client, k, 2)
    lab_rows = sources(inp, "LAB_RESULT")
    assert len(lab_rows) == 24 and {x["variable_code"] for x in lab_rows} == {"OC_T", "MASS_T", "OC_T0", "MASS_T0"}
    (area_row,) = sources(inp, "STRATUM_AREA")
    area = float(area_row["value"])
    exp = _measured(float(mod.reference_depth_cm))                  # computed for 50 ha: dSOC scales with the area, UNC / UD do not
    d = exp["dsoc"] * area / 50.0
    pe = _pe()["total"] + (GS_SEED if mod.seed else 0.0)
    c = _credits(d, exp["ud"], pe, 0.0)
    assert val["DSOC_C"] == pytest.approx(d, rel=1e-9)
    assert val["UNC"] == pytest.approx(exp["unc"], rel=1e-4)        # t from the quantile vs GS Table 6 (4 decimals)
    assert val["PE_TOTAL"] == pytest.approx(pe, rel=1e-9) and val["LK_TOTAL"] == 0
    assert val["GS_VER_TOTAL"] == c["vers"] and run["net_result"] == str(c["vers"]) and c["vers"] > 0, (val, c)
    approve_run(client, k, run)


# ---------------------------------------------------------------- afforestation / reforestation: plot inventories
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def visit(client: TestClient, k: Run, pt: dict, when: str) -> dict:
    """Field visit of an inventory plot: GPS at the plot centre, checklist, photo -> submit (collector) -> accept (supervisor)."""
    c = k.c
    fc = ok(client.post(f"{MRV}/field-collections", headers=c.collector.headers, json={"sampling_point_id": pt["id"]}), 201)
    ok(client.patch(f"{MRV}/field-collections/{fc['id']}", headers=c.collector.headers, json={
        "collected_at": when, "gps_latitude": float(pt["latitude"]), "gps_longitude": float(pt["longitude"]), "gps_accuracy_m": "3",
        "actual_depth_top_cm": pt["planned_depth_top_cm"], "actual_depth_bottom_cm": pt["planned_depth_bottom_cm"],
        "observations": "Plot marked; every tree measured (DBH, height)", "checklist": dict.fromkeys(fc["required_checklist"], True)}))
    ok(client.post(f"{MRV}/evidence", headers=c.collector.headers, files={"file": ("plot.png", PNG, "image/png")},
                   data={"project_id": k.pid, "entity_type": "FIELD_COLLECTION", "entity_id": fc["id"], "evidence_type": "FIELD_PHOTO",
                         "latitude": str(pt["latitude"]), "longitude": str(pt["longitude"]), "description": "plot centre"}), 201)
    ok(client.post(f"{MRV}/field-collections/{fc['id']}/submit", headers=c.collector.headers))
    return ok(client.post(f"{MRV}/field-collections/{fc['id']}/review", headers=c.supervisor.headers,
                          json={"decision": "ACCEPTED", "notes": "plot and photo checked"}))


def plot_inventory(client: TestClient, k: Run, n: int, rule: str, plots: dict[str, list[float]], plot_ha: float, when: str,
                   **design: Any) -> None:
    """Sampling design (plots per stratum) -> generated plot locations -> assigned -> visited -> one plot value per plot, plot size."""
    c = k.c
    body = {"monitoring_period_id": k.periods[n]["id"], "code": f"INV-P{n}", "name": f"Forest inventory {n}",
            "statistical_design": "STRATIFIED_RANDOM", "depth_top_cm": "0", "depth_bottom_cm": "30", "min_distance_m": "20",
            "random_seed": 7 + n, "allocations": [{"stratum_id": k.strata[code]["id"], "sample_count": len(v)} for code, v in plots.items()],
            "sampling_method": "Circular plots, all trees measured", **design}
    d = ok(client.post(f"{MRV}/sampling-designs", headers=c.mrv.headers, json=body), 201)
    ok(client.post(f"{MRV}/sampling-designs/{d['id']}/versions/{d['current']['id']}/approve", headers=c.t.gis.headers, json={"reason": "design ok"}))
    pts = ok(client.post(f"{MRV}/sampling-designs/{d['id']}/generate-points", headers=c.mrv.headers), 201)["points"]
    assert sorted(p["stratum_code"] for p in pts) == sorted(code for code, v in plots.items() for _ in v)
    ok(client.post(f"{MRV}/sampling-points/assign", headers=c.supervisor.headers,
                   json={"point_ids": [p["id"] for p in pts], "collector_id": str(c.collector.user.id)}))
    for p in sorted(pts, key=lambda x: (x["stratum_code"], x["sequence"])):
        visit(client, k, p, when)
        record(client, k, n, rule, plots[p["stratum_code"]][p["sequence"] - 1], when[:10], point=p)
    record(client, k, n, rule.replace("_AGB", "_AREA").replace("_VOL", "_AREA"), plot_ha, when[:10])


def ar_setup(db: Session, client: TestClient, admin: Actor, s: Spec, sizes: tuple[float, float], codes: tuple[str, str]) -> Run:
    k = setup(db, client, admin, s, sizes=sizes, quantification_approach=None)
    for code, farm in zip(codes, k.farms, strict=True):
        k.strata[code] = approved_stratum(client, k.c, code, [farm["id"]], name=f"Planting unit {code}")
    return k


def stratum_areas(k: Run, inp: dict) -> dict[str, float]:
    return {x["source_code"]: float(x["value"]) for x in sources(inp, "STRATUM_AREA")}


def ar_stock(areas: dict[str, float], plots: dict[str, list[float]], plot_ha: float) -> tuple[float, float]:
    """test_ccts_ar._stock on the drawn strata: Mokany root-shoot per plot, stratified mean and its 90 % uncertainty (BM-T-AR-0004)."""
    from app.calculation.library import stats
    area = sum(areas[s] for s in plots)
    mean, var, n = 0.0, 0.0, 0
    for s, values in plots.items():
        b = [v / plot_ha for v in values]
        tot = [x * (1 + math.exp(-1.085 + 0.9256 * math.log(x)) / x) for x in b]
        w = areas[s] / area
        m = sum(tot) / len(tot)
        mean += w * m
        var += w * w * (sum((x - m) ** 2 for x in tot) / (len(tot) - 1)) / len(tot)
        n += len(tot)
    t = float(stats.t_quantile(0.95, Decimal(n - len(plots))))
    return 44 / 12 * 0.47 * area * mean, t * math.sqrt(var) / mean


CCTS = ("CCTS", "Carbon Credit Trading Scheme (offset mechanism)", "Bureau of Energy Efficiency")
FR05002 = Spec("CCTS-FR05.002", "BM-FR05.002", "1.0", CCTS, ("ARR", "Afforestation and reforestation"), "GRASSLAND", "AGROFORESTRY",
               ("Jawhar", "Palghar", "Maharashtra"), 73.23, 19.91)
FR05001 = Spec("CCTS-FR05.001", "BM-FR05.001", "1.0", CCTS, ("ARR", "Afforestation and reforestation"), "WETLAND", "OTHER",
               ("Dahanu", "Palghar", "Maharashtra"), 72.71, 19.97)
AR_CUR = {"S1": [4.1, 3.6, 4.8, 4.0], "S2": [2.9, 3.3, 2.6]}          # test_ccts_ar: t d.m. above ground per 0.05 ha plot
AR_PREV = {"S1": [1.9, 1.6, 2.2, 1.8], "S2": [1.2, 1.5, 1.1]}


def test_ccts_fr05002_afforestation_two_verifications(client: TestClient, db: Session, admin: Actor) -> None:
    """Two plot inventories in two approved periods; the second verification uses the first as C_T1 (Eqs. 1-2, Appendix 2 discount)."""
    from tests.test_ccts_ar import _discounted
    k = ar_setup(db, client, admin, FR05002, (0.005, 0.0041), ("S1", "S2"))       # ~30 ha and ~20 ha
    open_period(client, k, 1, ("2025-06-01", "2025-12-31"))
    plot_inventory(client, k, 1, "AR_PLOT_AGB", AR_PREV, 0.05, "2025-11-15T05:00:00Z")
    approve_dataset(client, k, 1)
    open_period(client, k, 2, ("2026-01-01", "2026-09-30"))
    plot_inventory(client, k, 2, "AR_PLOT_AGB", AR_CUR, 0.05, "2026-08-15T05:00:00Z")
    record(client, k, 2, "AR_GHG_E", "3.5", "2026-08-15")
    record(client, k, 2, "AR_LK", "2.0", "2026-08-15")
    approve_dataset(client, k, 2)
    run, val, inp = calculate(client, k, 2)
    areas = stratum_areas(k, inp)
    assert 25 < areas["S1"] < 35 and 15 < areas["S2"] < 25, areas
    c2, u2 = ar_stock(areas, AR_CUR, 0.05)
    c1, u1 = ar_stock(areas, AR_PREV, 0.05)
    net = _discounted(c1, u1, c2, u2) - 3.5 - 0 - 2.0
    assert val["C_T2"] == pytest.approx(c2, rel=1e-9) and val["U_T2"] == pytest.approx(u2, rel=1e-6)
    assert val["C_T1"] == pytest.approx(c1, rel=1e-9)
    assert val["DC_AR"] == pytest.approx(net, rel=1e-6)
    assert val["LCCC"] == math.floor(net) and run["net_result"] == str(math.floor(net)) and net > 0
    assert len([x for x in sources(inp, "MONITORING_RECORD") if x["variable_code"] == "PLOT_AGB_T0"]) == 7   # previous inventory
    approve_run(client, k, run)


def test_ccts_fr05001_mangrove_first_verification(client: TestClient, db: Session, admin: Actor) -> None:
    """First verification: pre-project stock, shrubs from crown cover and the FR05.001 mangrove SOC default (0.50 t C/ha/yr)."""
    from tests.test_ccts_ar import _discounted
    k = ar_setup(db, client, admin, FR05001, (0.005, 0.0041), ("S1", "S2"))
    open_period(client, k, 1, ("2025-06-01", "2026-05-31"))
    plot_inventory(client, k, 1, "AR_PLOT_AGB", AR_CUR, 0.05, "2026-03-15T05:00:00Z")
    record(client, k, 1, "AR_PLANT_YEAR", 2024, "2025-06-01", stratum=k.strata["S1"])
    record(client, k, 1, "AR_SHRUB_CC", "0.30", "2026-03-15", stratum=k.strata["S2"])
    record(client, k, 1, "AR_SHRUB_CC", "0.03", "2026-03-15", stratum=k.strata["S1"])
    record(client, k, 1, "AR_B_FOREST", 120, "2025-06-01")
    record(client, k, 1, "AR_BSL_STOCK", 40, "2025-06-01")
    approve_dataset(client, k, 1)
    run, val, inp = calculate(client, k, 1)
    areas = stratum_areas(k, inp)
    c2, u2 = ar_stock(areas, AR_CUR, 0.05)
    shrubs = 44 / 12 * 0.47 * 1.40 * (areas["S2"] * 0.10 * 120 * 0.30)          # S1 below 5 % crown cover counts as 0
    soc = 44 / 12 * areas["S1"] * 0.50 * 2                                      # 2025 and 2026, planted 2024
    net = _discounted(40, 0, c2 + shrubs, u2 * c2 / (c2 + shrubs)) + soc
    assert val["C_TREE_T2"] == pytest.approx(c2, rel=1e-9) and val["C_T1"] == 40
    assert val["C_SHRUB_T2"] == pytest.approx(shrubs, rel=1e-9)
    assert val["DSOC"] == pytest.approx(soc, rel=1e-9)
    assert val["LCCC"] == math.floor(val["DC_AR"]) and val["DC_AR"] > 0
    assert abs(val["DC_AR"] - net) / net < 0.05                                   # as test_ccts_ar (uncertainty of trees vs total)
    approve_run(client, k, run)


GS403 = Spec("GS403-V2.1", "GS403", "2.1", GS402, ("ARR", "Afforestation and reforestation"), "GRASSLAND", "AGROFORESTRY",
             ("Mokhada", "Palghar", "Maharashtra"), 73.33, 19.93)
GS_MU = {"M1": [4.4, 3.9, 4.8, 4.1, 3.6], "M2": [2.0, 3.1, 1.4, 2.6]}       # test_gs_ar_403: stem volume m3 per 0.04 ha plot


def test_gs403_afforestation_farmer_to_calculation(client: TestClient, db: Session, admin: Actor) -> None:
    """Forest inventory per modelling unit, MU wood density and long-term cap, one-off baseline / leakage / burning, fertiliser,
    units already issued, Paris alignment recorded (the period runs into 2026)."""
    from tests.test_gs_ar_403 import _mu_stock
    k = ar_setup(db, client, admin, GS403, (0.00575, 0.00455), ("M1", "M2"))     # ~40 ha and ~25 ha
    open_period(client, k, 1, ("2025-06-01", "2026-05-31"))
    plot_inventory(client, k, 1, "GA_PLOT_VOL", GS_MU, 0.04, "2026-02-10T05:00:00Z", target_precision_pct="20", confidence_level_pct="90")
    record(client, k, 1, "GA_WD", "0.55", "2025-06-01", stratum=k.strata["M1"])
    record(client, k, 1, "GA_CR_LT", 150, "2025-06-01", stratum=k.strata["M1"])
    for code, value in (("GA_BSL", 300), ("GA_BURNING", "YES"), ("GA_LK", 120), ("GA_ISSUED_PRIOR", 500), ("GA_PAA", "YES")):
        record(client, k, 1, code, value, "2025-06-01")
    record(client, k, 1, "GA_FERT_N", 2000, "2025-07-01", "PROJECT", farm=k.farms[0])
    approve_dataset(client, k, 1)
    run, val, inp = calculate(client, k, 1)
    areas = stratum_areas(k, inp)
    assert 35 < areas["M1"] < 45 and 20 < areas["M2"] < 30, areas
    s1, _ = _mu_stock(GS_MU["M1"], 0.55)
    s2, e2 = _mu_stock(GS_MU["M2"], 0.3)
    stock = min(s1, 150) * areas["M1"] + s2 * areas["M2"]
    net = stock - 300 - 120 - 30 - 2000 * 0.005
    vers = math.floor(max(0.0, net - 500) * 0.8)
    assert e2 > 0.20                                                          # M2 imprecise: the excess error is deducted
    assert val["NET_CUMULATIVE"] == pytest.approx(net, rel=1e-9) and val["PAA_BLOCKED_SHARE"] == 0
    assert val["GSVER_PROJECT"] == vers and run["net_result"] == str(vers) and vers > 0
    approve_run(client, k, run)
