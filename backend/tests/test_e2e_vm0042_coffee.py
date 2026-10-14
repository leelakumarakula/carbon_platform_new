"""End-to-end API test: a Kodagu (Karnataka) coffee estate credited under Verra VCS VM0042 v2.2 with the REAL registered calculation
module VM0042-V2.2-QA2-QA3 (soil carbon measured and remeasured at 3 control sites, default-factor emissions, Eq. 33 leakage), from
set-up to the farmer's payout.

Everything goes through the HTTP API (FastAPI TestClient, SQL Server test database rolled back after each test) with separation of
duties. The calculation is checked against an independent float hand calculation written out below (it mirrors `_expected()` in
test_vm0042_module.py, extended with the wet-climate factors, liming, leakage and the buffer of this scenario).

Dates. The VM0042 walkthrough (docs/e2e-test-walkthrough-vm0042.md) periods are used: baseline campaign 2025-11-01 -> 2026-05-31 and
monitoring period 2026-06-01 -> 2027-05-31 (one year: 365 days). A monitoring period starting 2026-11-01 cannot be sampled before that
date: the platform refuses a field collection dated in the future or outside its period (REQUIREMENTS_NOT_MET).

All values are TEST values chosen to look like a shade-grown Arabica estate (sandy loam, ~2200 mm rainfall); they are not project data.
"""
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.calculation import framework as fw
from app.calculation.library import stats
from app.calculation.modules.vm0042_v2_2 import Vm0042V22
from app.core.config import get_settings
from app.models import Organization
from tests.conftest import Actor, login, make_org, make_user
from tests.phase2 import PDF, create_farm, set_boundary, square, staff, upload
from tests.phase3 import PR, Team, active_farmer, add_farm, create_project, rights, team
from tests.phase4 import M, methodology, specialists
from tests.phase5 import MRV, MrvCtx, approved_design, approved_plan, approved_stratum
from tests.phase6 import LAB, LABV

V = "/api/v1"
CALC = f"{V}/calculations"
MODULE = "VM0042-V2.2-QA2-QA3"
UTC = timezone.utc
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64

# ---------------------------------------------------------------- scenario values
LON, LAT = 75.735, 12.420                    # Madikeri taluk, Kodagu
EST_SIZE, CTRL_SIZE = 0.003, 0.002           # ~10.9 ha estate, ~4.8 ha control estates
CONTROLS = {"C1": (0.012, 0.000, "2150"), "C2": (0.000, 0.012, "2180"), "C3": (0.012, 0.012, "2250")}   # offset lon/lat, rainfall
P1 = ("2025-11-01", "2026-05-31")            # baseline sampling campaign (t0)
P2 = ("2026-06-01", "2027-05-31")            # reporting period (t)
COLLECTED = {1: "2026-01-20T05:00:00Z", 2: "2026-10-01T05:00:00Z"}
D_MM, CORES = 50, 5                          # probe inside diameter (mm), cores per composite


def chars(rain: str) -> list[dict[str, str]]:
    return [{"characteristic": "SOIL_TEXTURE", "value": "Sandy loam"}, {"characteristic": "SOIL_GROUP", "value": "Nitisols"},
            {"characteristic": "SLOPE_CLASS", "value": "Moderate (8-15 %)"},
            {"characteristic": "ECOREGION", "value": "South Western Ghats moist deciduous forests"},
            {"characteristic": "PRECIPITATION_MM", "value": rain}, {"characteristic": "SOC_PERCENT", "value": "1.55"}]


# laboratory results per stratum, campaign and point (by sequence): (0-30 cm mass g, OC g/kg, 30-50 cm mass g, OC g/kg)
LABDATA: dict[str, dict[int, list[tuple[int, str, int, str]]]] = {
    "S1": {1: [(4140, "15.2", 2840, "9.1"), (4160, "15.8", 2860, "8.8"), (4150, "15.5", 2850, "9.0")],
           2: [(4145, "16.3", 2845, "9.3"), (4155, "16.8", 2855, "9.0"), (4150, "16.6", 2850, "9.2")]},
    "C1": {1: [(4150, "15.4", 2850, "9.0"), (4140, "15.6", 2860, "8.9"), (4160, "15.3", 2840, "9.1")],
           2: [(4150, "15.3", 2850, "9.0"), (4145, "15.6", 2855, "8.9"), (4155, "15.3", 2845, "9.0")]},
    "C2": {1: [(4135, "15.1", 2845, "8.8"), (4165, "15.5", 2855, "9.0"), (4150, "15.2", 2850, "8.9")],
           2: [(4140, "15.2", 2850, "8.8"), (4160, "15.4", 2850, "9.0"), (4150, "15.1", 2845, "8.9")]},
    "C3": {1: [(4155, "15.7", 2850, "9.2"), (4145, "15.4", 2845, "9.0"), (4150, "15.6", 2860, "9.1")],
           2: [(4150, "15.7", 2850, "9.1"), (4150, "15.5", 2850, "9.0"), (4145, "15.6", 2855, "9.1")]},
}
# farm activity: three look-back years (phase BASELINE, t = -1..-3) and the project year (phase PROJECT)
LOOK_BACK = {"V42_FSN": ("3900", "4000", "4100"), "V42_DIESEL": ("1150", "1200", "1250"), "V42_LIMESTONE": ("10", "10", "10"),
             "V42_BURN_OTHER": ("7800", "8000", "8200"), "V42_IRRIGATION": ("OTHER", "OTHER", "OTHER")}
LOOK_BACK_DATES = ("2023-03-15", "2024-03-15", "2025-03-15")
P1_PROJECT = {"V42_FSN": "2500", "V42_DIESEL": "700", "V42_LIMESTONE": "10", "V42_BURN_OTHER": "0", "V42_IRRIGATION": "OTHER",
              "V42_OA_IMPORTED": "0", "V42_WOODY": "NO"}
P2_PROJECT = {"V42_FSN": "3000", "V42_FON": "1500", "V42_DIESEL": "1000", "V42_LIMESTONE": "10", "V42_BURN_OTHER": "0",
              "V42_IRRIGATION": "OTHER", "V42_OA_IMPORTED": "100", "V42_OA_CARBON": "0.25", "V42_WOODY": "NO"}
NPR = "15"
APPLICABILITY = [
    {"rule_code": "A1", "title": "Standard is VCS", "category": "STANDARD", "fact_key": "standard_code", "operator": "EQUALS",
     "expected_value": "VCS", "source_reference": "VM0042 v2.2 §1"},
    {"rule_code": "A2", "title": "Activity is improved agricultural land management", "category": "ACTIVITY", "fact_key": "activity_code",
     "operator": "EQUALS", "expected_value": "IALM", "source_reference": "VM0042 v2.2 §4"},
    {"rule_code": "A3", "title": "Land is cropland (perennial coffee)", "category": "LAND_USE", "fact_key": "land_use_current",
     "operator": "ALL_IN", "expected_value": ["CROPLAND"], "source_reference": "VM0042 v2.2 §4 (1)"},
    {"rule_code": "A4", "title": "At least three years of land-use history", "category": "DATA_AVAILABILITY",
     "fact_key": "land_use_history_years_min", "operator": "GTE", "expected_value": 3, "source_reference": "VM0042 v2.2 §8.1 (look-back)"},
    {"rule_code": "A5", "title": "Project in India", "category": "COUNTRY", "fact_key": "country", "operator": "IN", "expected_value": ["IN"]},
]


@pytest.fixture(autouse=True)
def _bulk_api_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    """This test drives ~2,000 API calls within a few minutes from one client address: the per-IP limit (600/min) answers 429
    RATE_LIMITED otherwise. The limits are raised for this test only (as test_runtime_hardening does); the limiter stays on."""
    s = get_settings()
    for name in ("GLOBAL_RATE_LIMIT_PER_MINUTE", "USER_RATE_LIMIT_PER_MINUTE", "ORGANIZATION_RATE_LIMIT_PER_MINUTE",
                 "UPLOAD_RATE_LIMIT_PER_MINUTE", "API_BURST_RATE_LIMIT_PER_MINUTE"):
        monkeypatch.setattr(s, name, 1_000_000)


def ok(r: Any, *codes: int) -> Any:
    assert r.status_code in (codes or (200, 201)), r.text
    return r.json()


def now_iso(delta_min: int = 0) -> str:
    return (datetime.now(UTC) + timedelta(minutes=delta_min)).isoformat()


# ---------------------------------------------------------------- independent hand calculation (plain floats)
def _profile(prof: tuple[int, str, int, str]) -> tuple[list[float], list[float], list[float]]:
    """Cumulative mineral soil mass, cumulative OC (Mg/ha) and depth from the surface: VM0042 Eq. 3, soil mass per hectare from the
    sample mass over the cored area pi (d/2)^2 x cores; mineral mass = fine soil minus SOM (SOC / 0.58)."""
    area_mm2 = math.pi * (D_MM / 2) ** 2 * CORES
    mass, oc, depth = [0.0], [0.0], [0.0]
    for bottom, m, c in ((30, prof[0], float(prof[1])), (50, prof[2], float(prof[3]))):
        fine = m / area_mm2 * 10_000                          # g/mm2 -> Mg/ha
        mass.append(mass[-1] + fine * (1 - c / 1000 / 0.58))
        oc.append(oc[-1] + fine * c / 1000)
        depth.append(bottom)
    return mass, oc, depth


def _lin(x: list[float], y: list[float], t: float) -> float:
    i = max(k for k in range(len(x) - 1) if x[k] <= t) if t < x[-1] else len(x) - 2
    return y[i] + (y[i + 1] - y[i]) * (t - x[i]) / (x[i + 1] - x[i])


def hand_calculation(area_ha: float) -> dict[str, float]:
    controls = ("C1", "C2", "C3")
    ref = [_lin(_profile(p)[2], _profile(p)[0], 30.0) for c in controls for p in LABDATA[c][1]]
    ref_mass = sum(ref) / len(ref)                           # mean mineral mass to 30 cm at the control sites, earlier campaign
    soc = {(scen, n): [_lin(_profile(p)[0], _profile(p)[1], ref_mass) for s in strata for p in LABDATA[s][n]]
           for scen, strata in (("P", ("S1",)), ("B", controls)) for n in (1, 2)}
    mean = {k: sum(v) / len(v) for k, v in soc.items()}
    c2 = 44 / 12
    wp = (mean[("P", 2)] - mean[("P", 1)]) * area_ha * c2      # Eq. 47 x 44/12
    bsl = (mean[("B", 2)] - mean[("B", 1)]) * area_ha * c2     # Eq. 46 x 44/12
    comps = []
    for v in soc.values():
        n = len(v)
        m = sum(v) / n
        comps.append((c2 * c2 * (sum((x - m) ** 2 for x in v) / (n - 1)) / n, n))   # one project stratum: weight 1
    variance = sum(c for c, _ in comps)
    df = variance ** 2 / sum(c * c / (n - 1) for c, n in comps)                   # Welch-Satterthwaite
    t = float(stats.t_quantile(2 / 3, Decimal(str(df))))                          # one-sided 66.67 %
    unc = min(100.0, t * math.sqrt(variance) / abs((wp - bsl) / area_ha) * 100)
    sign = 1 if wp - bsl >= 0 else -1
    wp_adj, bsl_adj = wp * (1 - unc / 100 * sign), bsl * (1 - unc / 100 * sign)
    # emissions, IPCC 2019 Tier 1 WET factors (2200 mm > 1000 mm): direct, volatilised and leached N2O; diesel; limestone; burning
    n2o = 44 / 28 * 265 / 1000                                                    # kg N2O-N -> t CO2e
    fert = lambda fsn, fon: (fsn * 0.016 + fon * 0.006 + (fsn * 0.11 + fon * 0.21) * 0.014 + (fsn + fon) * 0.24 * 0.011) * n2o  # noqa: E731
    burn = lambda kg: kg * 0.80 * (2.7 / 1e6 * 28 + 0.07 / 1e6 * 265)                                                          # noqa: E731
    lb = {k: sum(float(x) for x in v) / 3 for k, v in LOOK_BACK.items() if k != "V42_IRRIGATION"}   # x 1 year (365 days)
    pr = {k: float(v) for k, v in P2_PROJECT.items() if k not in ("V42_IRRIGATION", "V42_WOODY")}
    er = {"N2O_FERT": fert(lb["V42_FSN"], 0) - fert(pr["V42_FSN"], pr["V42_FON"]),
          "FUEL": (lb["V42_DIESEL"] - pr["V42_DIESEL"]) * 0.002886,
          "LIME": (lb["V42_LIMESTONE"] - pr["V42_LIMESTONE"]) * 0.12 * 44 / 12,
          "BB": burn(lb["V42_BURN_OTHER"]) - burn(pr["V42_BURN_OTHER"])}
    er_sources = sum(er.values())
    lk = pr["V42_OA_IMPORTED"] * pr["V42_OA_CARBON"] * 0.12 * 44 / 12           # Eq. 33: 100 t x 0.25 x 0.12 x 44/12 = 11
    npr = max(float(NPR), 12.0) / 100
    i_wp = 1 if wp_adj > 0 else 0
    mx = max(0.0, wp_adj) - max(0.0, bsl_adj)
    mn = min(0.0, wp_adj) - min(0.0, bsl_adj)
    er_t = er_sources + mn + (1 - i_wp) * mx                                    # Eq. 37
    cr_t = i_wp * mx                                                            # Eq. 40
    bu_er = max(0.0, (i_wp * mn + (1 - i_wp) * (mn + mx)) * npr)                # Eq. 75
    bu_cr = max(0.0, i_wp * mx * npr)                                           # Eq. 76
    total = er_t + cr_t - lk - bu_er - bu_cr                                    # Eqs. 38/41 (leakage split pro rata) + 77-79
    return {"ref": ref_mass, "wp": wp, "bsl": bsl, "unc": unc, "er_sources": er_sources, "er_fuel": er["FUEL"], "lk": lk,
            "cr": cr_t, "bu_cr": bu_cr, "bu_er": bu_er, "total": total, "vcus": math.floor(max(0.0, total))}


# ---------------------------------------------------------------- builders
@dataclass
class Lab:
    org: Organization
    tech: Actor
    mgr: Actor
    qa: Actor
    engagement: dict


@dataclass
class Coffee:
    c: MrvCtx
    admin: Actor
    author: Actor
    approver: Actor
    farmer: dict
    estate: dict
    estate_area: float                      # SQL Server area of the drawn boundary (ha)
    controls: dict[str, dict]
    strata: dict[str, dict]
    lab: Lab
    analyst: Actor
    periods: dict[int, dict] = field(default_factory=dict)
    points: dict[int, list[dict]] = field(default_factory=dict)
    records: dict[int, list[dict]] = field(default_factory=dict)
    datasets: dict[int, dict] = field(default_factory=dict)
    measurements: dict[str, dict] = field(default_factory=dict)

    @property
    def t(self) -> Team:
        return self.c.t

    @property
    def pid(self) -> str:
        return str(self.c.project["id"])


def vcs_catalog(client: TestClient, admin: Actor) -> tuple[str, str]:
    """Stage 1 of the walkthrough: the Verra standard and the IALM activity (platform admin)."""
    std = ok(client.post(f"{V}/standards", headers=admin.headers, json={
        "code": "VCS", "name": "Verified Carbon Standard", "owner_name": "Verra", "program_type": "VOLUNTARY",
        "source_url": "https://verra.org/programs/verified-carbon-standard/"}), 201)
    act = ok(client.post(f"{V}/activities", headers=admin.headers, json={
        "code": "IALM", "name": "Improved agricultural land management", "standard_ids": [std["id"]]}), 201)
    return std["id"], act["id"]


def vm0042_version(db: Session, client: TestClient, std_id: str, act_id: str) -> tuple[Actor, Actor, dict]:
    """VM0042 2.2 with the registered module selected by one methodology specialist and approved by a second one."""
    author, approver = specialists(db, client)
    m = methodology(client, author, std_id, [act_id], "VM0042", name="Improved Agricultural Land Management", owner_name="Verra")
    v = ok(client.post(f"{M}/{m['id']}/versions", headers=author.headers, json={
        "version_label": "2.2", "effective_from": "2025-10-21", "source_name": "Verra VM0042 v2.2 (C&C 11 Jun 2026)",
        "source_url": "https://verra.org/methodologies/vm0042-improved-agricultural-land-management-v2-2/"}), 201)
    vid = v["id"]
    opts = ok(client.get(f"{M}/versions/{vid}/calculation-modules", headers=author.headers))
    assert [o["code"] for o in opts if o["compatible"]] == [MODULE]
    ok(client.post(f"{M}/versions/{vid}/calculation-module", headers=author.headers,
                   json={"module_code": MODULE, "reason": "VM0042 v2.2 QA2 + QA3 module for a measure-and-remeasure project"}))
    for rule in APPLICABILITY:
        ok(client.post(f"{M}/versions/{vid}/rules/applicability", headers=author.headers, json=rule), 201)
    ok(client.post(f"{M}/versions/{vid}/submit", headers=author.headers, json={"reason": "ready for approval"}))
    r = client.post(f"{M}/versions/{vid}/approve", headers=author.headers, json={"reason": "own work"})
    assert r.status_code == 403, r.text                                       # the author cannot approve
    v = ok(client.post(f"{M}/versions/{vid}/approve", headers=approver.headers, json={"reason": "checked against VM0042 v2.2"}))
    assert v["status"] == "APPROVED" and v["calculation_module_code"] == MODULE
    assert v["calculation_readiness"] == "NOT_PRODUCTION_READY"
    return author, approver, v


def coffee_farmer(client: TestClient, t: Team, id_number: str, name: str, village: str) -> dict:
    return active_farmer(client, t, id_number, full_name=name, village=village, district="Kodagu", state="Karnataka")


def estate(client: TestClient, t: Team, farmer: dict, name: str, lon: float, lat: float, size: float, survey_no: str) -> tuple[dict, float]:
    """A verified coffee estate: drawn boundary, RTC land record, ownership, land-use / crop / practice history, GIS verification."""
    h = t.agent.headers
    farm = create_farm(client, h, farmer["id"], name=name, village=farmer["village"], district="Kodagu", state="Karnataka",
                       declared_area_hectares=f"{size * size * 1.21e4:.2f}")
    fid = farm["id"]
    saved = set_boundary(client, h, fid, square(lon, lat, size))
    area = float(saved["farm"]["area_hectares"])
    doc = ok(upload(client, h, f"{V}/farms/{fid}/documents", "LAND_RECORD", PDF, "rtc.pdf", f"RTC {survey_no}"), 201)["id"]
    own = ok(client.post(f"{V}/farms/{fid}/ownership", headers=h, json={
        "owner_type": "FARMER", "owner_farmer_id": farmer["id"], "operator_relationship": "OWNER", "ownership_share_pct": "100",
        "title_reference": f"RTC Sy. No. {survey_no}", "evidence_document_id": doc}), 201)
    for url, actor, body in ((f"{V}/farms/{fid}/submit", t.agent, {"reason": "estate ready for review"}),
                             (f"{V}/farms/{fid}/start-review", t.gis, {"reason": "start GIS review"}),
                             (f"{V}/farms/{fid}/ownership/{own['id']}/review", t.gis, {"status": "VERIFIED", "notes": "RTC matches"}),
                             (f"{V}/farms/{fid}/verify", t.gis, {"reason": "boundary and tenure confirmed"})):
        ok(client.post(url, headers=actor.headers, json=body))
    for year in range(2019, 2026):
        ok(client.post(f"{V}/farms/{fid}/history/land", headers=h, json={
            "year": year, "land_use": "CROPLAND", "land_use_detail": "Shade-grown Arabica coffee (perennial cropland)"}), 201)
        ok(client.post(f"{V}/farms/{fid}/history/crop", headers=h, json={
            "year": year, "crop_name": "Coffee", "crop_variety": "Arabica S.795", "irrigation": "PARTIAL"}), 201)
    for body in ({"year": 2024, "practice_phase": "HISTORICAL", "practice_category": "FERTILIZER", "practice_type": "Urea, 4 t N per estate"},
                 {"year": 2024, "practice_phase": "HISTORICAL", "practice_category": "RESIDUE", "practice_type": "Prunings burned"},
                 {"year": 2025, "practice_phase": "PROPOSED", "practice_category": "FERTILIZER", "practice_type": "Compost replaces part of urea",
                  "implementation_status": "PLANNED"},
                 {"year": 2025, "practice_phase": "PROPOSED", "practice_category": "RESIDUE", "practice_type": "Prunings mulched, no burning",
                  "implementation_status": "PLANNED"}):
        ok(client.post(f"{V}/farms/{fid}/history/practice", headers=h, json=body), 201)
    got = ok(client.get(f"{V}/farms/{fid}", headers=t.gis.headers))
    assert got["status"] == "VERIFIED", got
    return got, area


def locked_coffee_project(client: TestClient, t: Team, vid: str, std_id: str, act_id: str, estate_farm: dict, author: Actor) -> dict:
    """Project -> estate enrolled with carbon rights -> eligibility -> VM0042 2.2 evaluated, recommended, confirmed and locked."""
    p = create_project(client, t, name="Kodagu shade-coffee soil carbon (VM0042)", region="Kodagu, Karnataka", start_date="2025-11-01")
    pid, h = p["id"], t.pm.headers
    ok(client.post(f"{PR}/{pid}/start-data-collection", headers=h, json={"reason": "collect estate data"}))
    ok(add_farm(client, t, pid, estate_farm["id"], participation_start="2025-11-01",
                carbon_rights=rights("Carbon rights clause 7, Kaveri Estate agreement KE-2025-01", effective_from="2025-11-01",
                                     share_pct="100")), 201)
    for path, body in (("standard", {"standard_id": std_id}), ("activity", {"activity_id": act_id}),
                       ("crediting-period", {"start_date": "2025-11-01", "end_date": "2035-10-31"})):
        ok(client.post(f"{PR}/{pid}/{path}", headers=h, json=body))
    ok(client.patch(f"{PR}/{pid}/baseline", headers=h, json={"period_start": "2022-11-01", "period_end": "2025-10-31"}))
    ok(client.post(f"{PR}/{pid}/submit", headers=h, json={"reason": "complete for eligibility review"}))
    ok(client.post(f"{PR}/{pid}/boundary/review", headers=t.gis.headers, json={"decision": "ACCEPTED", "notes": "estate boundary ok"}))
    for cr in ok(client.get(f"{PR}/{pid}/carbon-rights", headers=t.qa.headers)):
        ok(client.post(f"{PR}/{pid}/carbon-rights/{cr['id']}/review", headers=t.qa.headers, json={"status": "VERIFIED", "notes": "clause 7 seen"}))
    ok(client.post(f"{PR}/{pid}/approve-eligibility", headers=t.qa.headers, json={"reason": "eligible"}))
    assert ok(client.post(f"{PR}/{pid}/confirm-activity", headers=h, json={"reason": "IALM confirmed"}))["status"] == "ACTIVITY_SELECTED"
    ev = ok(client.post(f"{PR}/{pid}/methodology/candidates", headers=h, json={"declared_facts": {}}), 201)
    cand = next(x for x in ev["candidates"] if x["methodology_version_id"] == vid)
    assert cand["outcome"] == "APPLICABLE", cand
    ok(client.post(f"{PR}/{pid}/methodology/reviews", headers=author.headers, json={
        "evaluation_result_id": cand["id"], "recommendation": "RECOMMENDED", "notes": f"Applicable; module {MODULE}",
        "evidence_acknowledged": True}), 201)
    ok(client.post(f"{PR}/{pid}/methodology/confirm", headers=h, json={"evaluation_result_id": cand["id"], "notes": "confirmed and locked"}))
    view = ok(client.get(f"{PR}/{pid}", headers=h))
    assert view["methodology_status"] == "CONFIRMED", view
    return view


def open_period(client: TestClient, c: MrvCtx, name: str, purpose: str, dates: tuple[str, str]) -> dict:
    mp = ok(client.post(f"{MRV}/monitoring-periods", headers=c.mrv.headers, json={
        "project_id": c.project["id"], "name": name, "purpose": purpose, "start_date": dates[0], "end_date": dates[1]}), 201)
    for action in ("plan", "start", "open-collection"):
        mp = ok(client.post(f"{MRV}/monitoring-periods/{mp['id']}/{action}", headers=c.mrv.headers, json={"reason": f"{action} now"}))
    assert mp["status"] == "DATA_COLLECTION"
    return mp


def collect(client: TestClient, c: MrvCtx, pt: dict, when: str) -> dict:
    """Start -> GPS, depth 0-50 cm, probe 50 mm x 5 cores, checklist -> photo -> submit (collector) -> accept (supervisor)."""
    fc = ok(client.post(f"{MRV}/field-collections", headers=c.collector.headers, json={"sampling_point_id": pt["id"]}), 201)
    ok(client.patch(f"{MRV}/field-collections/{fc['id']}", headers=c.collector.headers, json={
        "collected_at": when, "gps_latitude": float(pt["latitude"]), "gps_longitude": float(pt["longitude"]), "gps_accuracy_m": "3",
        "actual_depth_top_cm": "0", "actual_depth_bottom_cm": "50", "probe_diameter_mm": str(D_MM), "cores_count": CORES,
        "sample_quantity": "1.5", "sample_unit": "kg", "observations": "Moist red sandy loam under silver oak shade",
        "checklist": dict.fromkeys(fc["required_checklist"], True)}))
    ok(client.post(f"{MRV}/evidence", headers=c.collector.headers, files={"file": ("pit.png", PNG, "image/png")},
                   data={"project_id": c.project["id"], "entity_type": "FIELD_COLLECTION", "entity_id": fc["id"], "evidence_type": "FIELD_PHOTO",
                         "latitude": str(pt["latitude"]), "longitude": str(pt["longitude"]), "description": "auger cores and composite"}), 201)
    ok(client.post(f"{MRV}/field-collections/{fc['id']}/submit", headers=c.collector.headers))
    return ok(client.post(f"{MRV}/field-collections/{fc['id']}/review", headers=c.supervisor.headers,
                          json={"decision": "ACCEPTED", "notes": "cores, depth and photo checked"}))


def sampling_campaign(client: TestClient, k: Coffee, n: int) -> None:
    """One sampling design (3 points in each of S1, C1, C2, C3; same seed in both campaigns, so the same locations), field work,
    two depth-increment samples per core (0-30, 30-50 cm), custody to the laboratory, OC + fine-soil mass per sample, laboratory QA."""
    c, lab, period = k.c, k.lab, k.periods[n]
    d = approved_design(client, c, period["id"], [{"stratum_id": s["id"], "sample_count": 3} for s in k.strata.values()],
                        code=f"SOIL-P{n}", name=f"Soil sampling campaign {n}", depth_bottom_cm="50", random_seed=42,
                        sampling_method=f"Soil auger {D_MM} mm ID, {CORES}-core composite per point")
    pts = ok(client.post(f"{MRV}/sampling-designs/{d['id']}/generate-points", headers=c.mrv.headers), 201)["points"]
    assert sorted(p["stratum_code"] for p in pts) == ["C1"] * 3 + ["C2"] * 3 + ["C3"] * 3 + ["S1"] * 3
    ok(client.post(f"{MRV}/sampling-points/assign", headers=c.supervisor.headers,
                   json={"point_ids": [p["id"] for p in pts], "collector_id": str(c.collector.user.id)}))
    k.points[n] = pts
    samples: list[tuple[dict, str, int, int]] = []                # (sample, stratum code, point sequence, increment 0/1)
    for p in sorted(pts, key=lambda x: (x["stratum_code"], x["sequence"])):
        fc = collect(client, c, p, COLLECTED[n])
        for inc, (top, bottom) in enumerate(((0, 30), (30, 50))):
            s = ok(client.post(f"{LAB}/samples", headers=c.collector.headers, json={
                "field_collection_id": fc["id"], "description": f"Soil {top}-{bottom} cm", "depth_top_cm": str(top), "depth_bottom_cm": str(bottom),
                "quantity": "0.75", "quantity_unit": "kg", "container_label": f"{p['point_code']}-{'AB'[inc]}"}), 201)
            assert s["test_count"] == 2, s                           # V42_OC + V42_SOIL_MASS, automatically
            ok(client.post(f"{LAB}/samples/{s['id']}/seal", headers=c.collector.headers,
                           json={"seal_number": f"SEAL-{p['point_code']}-{'AB'[inc]}{n}"}))
            samples.append((s, p["stratum_code"], p["sequence"], inc))
    # custody: one shipment (supervisor), item-level receipt + accession (technician)
    sh = ok(client.post(f"{LAB}/shipments", headers=c.supervisor.headers, json={
        "project_id": c.project["id"], "laboratory_org_id": str(lab.org.id), "carrier": "Professional Couriers, Madikeri"}), 201)
    ok(client.post(f"{LAB}/shipments/{sh['id']}/items", headers=c.supervisor.headers, json={"sample_ids": [s["id"] for s, *_ in samples]}))
    ok(client.post(f"{LAB}/shipments/{sh['id']}/dispatch", headers=c.supervisor.headers, json={}))
    seals = {s["id"]: ok(client.get(f"{LAB}/samples/{s['id']}", headers=c.supervisor.headers))["seal_number"] for s, *_ in samples}
    ok(client.post(f"{LABV}/shipments/{sh['id']}/receive", headers=lab.tech.headers, json={"items": [
        {"sample_id": s["id"], "accepted": True, "condition": "intact, cool box", "seal_number_observed": seals[s["id"]]} for s, *_ in samples]}))
    for i, (s, *_rest) in enumerate(samples):
        ok(client.post(f"{LABV}/samples/{s['id']}/accession", headers=lab.tech.headers, json={"accession_number": f"KA{n}-{i + 1:03d}"}))
    # analysis: OC (g/kg, dry combustion) and fine-soil mass (g, oven-dry, < 2 mm) -> PDF report -> submit; QA by the second manager
    for s, code, seq, inc in samples:
        top_mass, top_oc, sub_mass, sub_oc = LABDATA[code][n][seq - 1]
        value = {"V42_OC": (top_oc, sub_oc)[inc], "V42_SOIL_MASS": str((top_mass, sub_mass)[inc])}
        unit = {"V42_OC": "g/kg", "V42_SOIL_MASS": "g"}
        for test in ok(client.get(f"{LABV}/samples/{s['id']}", headers=lab.tech.headers))["tests"]:
            rc = test["rule"]["rule_code"]
            method = "Dry combustion (Dumas)" if rc == "V42_OC" else "Oven-dry 105 C, sieved < 2 mm"
            ok(client.post(f"{LABV}/tests/{test['id']}/start", headers=lab.tech.headers, json={"method_reported": method}))
            res = ok(client.post(f"{LABV}/tests/{test['id']}/results", headers=lab.tech.headers, json={
                "result_type": "NUMERIC", "value_number": value[rc], "unit": unit[rc], "analysed_at": now_iso(1)}), 201)
            ok(client.post(f"{LABV}/results/{res['id']}/report", headers=lab.tech.headers,
                           files={"file": ("report.pdf", PDF, "application/pdf")}))
            ok(client.post(f"{LABV}/results/{res['id']}/submit", headers=lab.tech.headers))
            ok(client.post(f"{LABV}/qa/{res['id']}/start", headers=lab.qa.headers))
            q = ok(client.post(f"{LABV}/qa/{res['id']}/decision", headers=lab.qa.headers,
                               json={"decision": "APPROVED", "notes": "QC standards within limits"}))
            assert q["result"]["status"] == "APPROVED", q


def record(client: TestClient, k: Coffee, n: int, code: str, value: str, observed_on: str, phase: str, farm: bool = True) -> dict:
    m = k.measurements[code]
    r = ok(client.post(f"{MRV}/monitoring-records", headers=k.c.mrv.headers, json={
        "monitoring_period_id": k.periods[n]["id"], "measurement_id": m["id"], "farm_id": k.estate["id"] if farm else None,
        "measurement_phase": phase, "value": value, "observed_on": observed_on, "source": "DOCUMENT",
        "notes": "estate input register / invoices"}), 201)
    k.records.setdefault(n, []).append(r)
    return r


def farm_activity(client: TestClient, k: Coffee, n: int, project_year: dict[str, str], observed: str) -> None:
    """The look-back years (BASELINE) are recorded in every period that is calculated: the calculation reads only the reporting
    period's approved dataset (walkthrough 10.3)."""
    for code, values in LOOK_BACK.items():
        for value, day in zip(values, LOOK_BACK_DATES, strict=True):
            record(client, k, n, code, value, day, "BASELINE")
    for code, value in project_year.items():
        record(client, k, n, code, value, observed, "PROJECT")
    record(client, k, n, "V42_NPR", NPR, observed, "MONITORING", farm=False)     # AFOLU non-permanence risk rating (project level)


def approve_dataset(client: TestClient, k: Coffee, n: int) -> dict:
    c = k.c
    ds = ok(client.post(f"{MRV}/datasets", headers=c.mrv.headers, json={"monitoring_period_id": k.periods[n]["id"]}), 201)
    ok(client.post(f"{MRV}/datasets/{ds['id']}/submit", headers=c.mrv.headers, json={"reason": "campaign complete"}))
    ok(client.post(f"{MRV}/qa/{ds['id']}/start", headers=c.t.qa.headers))
    checks = {x["key"]: x["result"] for x in ok(client.get(f"{MRV}/qa/{ds['id']}", headers=c.t.qa.headers))["checks"]}
    assert "FAIL" not in checks.values(), checks
    ok(client.post(f"{MRV}/qa/{ds['id']}/complete", headers=c.t.qa.headers, json={"result": "PASS", "notes": "all checks pass"}))
    ds = ok(client.post(f"{MRV}/datasets/{ds['id']}/approve", headers=c.t.qa.headers, json={"reason": "dataset approved"}))
    assert ds["status"] == "APPROVED"
    k.datasets[n] = ds
    return ds


def coffee_scenario(db: Session, client: TestClient, admin: Actor, p2_project: dict[str, str] | None = None) -> Coffee:
    """Steps 1-7: organizations and users, VM0042 2.2, estates, locked project, MRV plan, strata and control sites, two sampling
    campaigns with laboratory results and farm activity, both datasets approved."""
    # 1. organizations and users: the developer team, a soil laboratory
    t = team(db, client)
    std_id, act_id = vcs_catalog(client, admin)
    # 2. methodology VM0042 2.2 + the real module, approved by a second specialist
    author, approver, v = vm0042_version(db, client, std_id, act_id)
    vid = v["id"]
    mon = {r["rule_code"] for r in ok(client.get(f"{M}/versions/{vid}", headers=author.headers))["rules"] if r["kind"] == "monitoring"}
    assert {"V42_OA_IMPORTED", "V42_OA_CARBON", "V42_WOODY", "V42_OC", "V42_SOIL_MASS", "V42_NPR"} <= mon
    # 3. the estate of the project farmer and three neighbouring control estates (not in the project)
    farmer = coffee_farmer(client, t, "4321 8765 2109", "Kaveri Ponnappa", "Madapura")
    est, est_area = estate(client, t, farmer, "Kaveri Estate", LON, LAT, EST_SIZE, "112/2")
    controls = {}
    for i, (code, (dlon, dlat, _)) in enumerate(CONTROLS.items()):
        owner = coffee_farmer(client, t, f"5432 9876 310{i}", f"Neighbour {code} Muthanna", "Galibeedu")
        controls[code], _ = estate(client, t, owner, f"{code} control estate", LON + dlon, LAT + dlat, CTRL_SIZE, f"2{i}/1")
    # 4. project, eligibility, methodology locked to VM0042 2.2
    project = locked_coffee_project(client, t, vid, std_id, act_id, est, author)
    org = t.org
    c = MrvCtx(t, staff(db, client, org, "MRV_MANAGER"), staff(db, client, org, "FIELD_SUPERVISOR"), staff(db, client, org, "FIELD_AGENT"),
               staff(db, client, org, "FIELD_AGENT"), project, [est], vid)
    # 5. MRV plan from the version's rules (approach MEASURE_AND_REMEASURE from the module), approved by QA
    plan = approved_plan(client, c, monitoring_frequency="Annual soil sampling; farm activity per year", monitoring_start="2025-11-01",
                         monitoring_end="2035-10-31", measurements=[], required_evidence="Field photos, GPS, lab reports, input invoices")
    assert plan["quantification_approach"] == "MEASURE_AND_REMEASURE"
    measurements = {m["code"]: m for m in plan["measurements"]}
    assert {"V42_OC", "V42_SOIL_MASS", "V42_FSN", "V42_FON", "V42_NPR", "V42_OA_IMPORTED", "V42_OA_CARBON", "V42_WOODY"} <= set(measurements)
    #    strata: S1 (the estate) and three control sites linked to it; matching checked at approval (GIS specialist)
    s1 = approved_stratum(client, c, "S1", [est["id"]], name="Kaveri Estate shade coffee", characteristics=chars("2200"))
    cands = {x["farm_id"] for x in ok(client.get(f"{MRV}/projects/{c.project['id']}/control-site-candidates", headers=c.mrv.headers))}
    assert {f["id"] for f in controls.values()} <= cands and est["id"] not in cands
    strata = {"S1": s1}
    for code, (_, _, rain) in CONTROLS.items():
        strata[code] = approved_stratum(client, c, code, [controls[code]["id"]], name=f"Control {code}", role="CONTROL",
                                        linked_stratum_ids=[s1["id"]], characteristics=chars(rain))
        assert strata[code]["role"] == "CONTROL" and [x["code"] for x in strata[code]["linked_strata"]] == ["S1"]
    #    a soil laboratory engaged for V42_OC + V42_SOIL_MASS (proposed by MRV, accepted by the lab manager)
    lab_org = make_org(db, org_type="LABORATORY")
    tech, mgr, lqa = (staff(db, client, lab_org, r) for r in ("LAB_TECHNICIAN", "LAB_MANAGER", "LAB_MANAGER"))
    rules = {r["rule_code"]: r for r in ok(client.get(f"{LAB}/projects/{c.project['id']}/laboratory-rules", headers=c.mrv.headers))}
    assert set(rules) == {"V42_OC", "V42_SOIL_MASS"}
    e = ok(client.post(f"{LAB}/engagements", headers=c.mrv.headers, json={
        "project_id": c.project["id"], "laboratory_org_id": str(lab_org.id), "rule_ids": [r["rule_id"] for r in rules.values()]}), 201)
    ok(client.post(f"{LABV}/engagements/{e['id']}/accept", headers=mgr.headers))
    k = Coffee(c, admin, author, approver, farmer, est, est_area, controls, strata, Lab(lab_org, tech, mgr, lqa, e),
               staff(db, client, org, "CALCULATION_ANALYST"), measurements=measurements)
    # 6. period 1 — the baseline campaign (t0): sampling, laboratory, look-back + period activity, NPR, dataset approved
    k.periods[1] = open_period(client, c, "Campaign 1 (baseline t0)", "BASELINE", P1)
    sampling_campaign(client, k, 1)
    farm_activity(client, k, 1, P1_PROJECT, "2026-03-15")
    approve_dataset(client, k, 1)
    # 7. period 2 — the remeasurement at the same points, the project year's activity, imported compost, woody declaration
    k.periods[2] = open_period(client, c, "Monitoring period 1", "MONITORING", P2)
    sampling_campaign(client, k, 2)
    assert {(p["stratum_code"], p["sequence"], p["latitude"], p["longitude"]) for p in k.points[2]} == \
           {(p["stratum_code"], p["sequence"], p["latitude"], p["longitude"]) for p in k.points[1]}      # same locations
    farm_activity(client, k, 2, P2_PROJECT if p2_project is None else p2_project, "2026-09-15")
    approve_dataset(client, k, 2)
    return k


def calculation_run(client: TestClient, k: Coffee) -> tuple[dict, Any]:
    """Create -> freeze (readiness + frozen inputs) -> execute, all by the calculation analyst. Returns (run, execute response)."""
    run = ok(client.post(f"{CALC}/runs", headers=k.analyst.headers,
                         json={"project_id": k.pid, "monitoring_period_id": k.periods[2]["id"]}), 201)
    frozen = ok(client.post(f"{CALC}/runs/{run['id']}/freeze", headers=k.analyst.headers))
    assert frozen["status"] == "INPUTS_FROZEN" and frozen["module_code"] == MODULE and frozen["module_readiness"] == "NOT_PRODUCTION_READY"
    return run, client.post(f"{CALC}/runs/{run['id']}/execute", headers=k.analyst.headers)


# ---------------------------------------------------------------- tests
def test_coffee_estate_vm0042_field_to_payout(client: TestClient, db: Session, admin: Actor) -> None:
    k = coffee_scenario(db, client, admin)
    c = k.c
    # 8. calculation with the real module (NOT_PRODUCTION_READY is allowed outside production)
    run, r = calculation_run(client, k)
    run = ok(r)
    assert run["status"] == "CALCULATED", run
    outs = ok(client.get(f"{CALC}/runs/{run['id']}/outputs", headers=k.analyst.headers))
    s1_tag = str(k.strata["S1"]["record_id"])[:8]                    # stratum outputs are named by the stratum record id
    val = {o["output_code"].replace(s1_tag, "S1"): float(o["value"]) for o in outs["outputs"]}
    exp = hand_calculation(k.estate_area)
    assert val["REF_MASS_S1"] == pytest.approx(exp["ref"], rel=1e-9)
    assert val["DCO2_SOIL_WP"] == pytest.approx(exp["wp"], rel=1e-9)
    assert val["DCO2_SOIL_BSL"] == pytest.approx(exp["bsl"], rel=1e-9)
    assert val["UNC_PCT"] == pytest.approx(exp["unc"], rel=1e-6)
    assert val["ER_FUEL"] == pytest.approx(exp["er_fuel"], rel=1e-12)
    assert val["ER_SOURCES"] == pytest.approx(exp["er_sources"], rel=1e-9)
    assert val["LK_OA"] == val["LK_TOTAL"] == pytest.approx(11.0, rel=1e-12) and exp["lk"] == pytest.approx(11.0, rel=1e-12)
    assert val["CR_T"] == pytest.approx(exp["cr"], rel=1e-6)
    assert val["BUFFER_CR"] == pytest.approx(exp["bu_cr"], rel=1e-6)
    assert val["NPR_PCT"] == 15
    assert val["VCU_TOTAL"] == exp["vcus"] and run["net_result"] == str(exp["vcus"]) and exp["vcus"] > 0
    vcus = exp["vcus"]
    # the inputs came through the platform: approved laboratory results, monitoring records, area from the drawn boundaries
    inp = ok(client.get(f"{CALC}/runs/{run['id']}/inputs", headers=k.analyst.headers))
    rows = inp["inputs"]
    approved = {x["id"]: x for x in ok(client.get(f"{LAB}/results", headers=c.mrv.headers,
                                                  params={"project_id": k.pid, "status": "ALL"})) if x["status"] == "APPROVED"}
    lab_rows = [x for x in rows if x["source_type"] == "LAB_RESULT"]
    assert len(lab_rows) == 96 == len(approved)                    # 2 campaigns x 12 cores x 2 increments x (OC + mass)
    assert {x["source_id"] for x in lab_rows} == set(approved)
    assert all(Decimal(x["value"]) == Decimal(str(approved[x["source_id"]]["value_number"])) and x["source_sha256"] for x in lab_rows)
    assert sorted({x["variable_code"] for x in lab_rows}) == ["MASS_T", "MASS_T0", "OC_T", "OC_T0"]
    rec_rows = [x for x in rows if x["source_type"] == "MONITORING_RECORD"]
    assert {x["source_id"] for x in rec_rows} == {r["id"] for r in k.records[2]} and len(rec_rows) == 25
    strata_api = {s["code"]: s for s in ok(client.get(f"{MRV}/projects/{k.pid}/strata", headers=c.mrv.headers))}
    area_rows = {x["source_code"]: Decimal(x["value"]) for x in rows if x["source_type"] == "STRATUM_AREA"}
    assert area_rows == {code: Decimal(str(strata_api[code]["area_hectares"])) for code in ("S1", "C1", "C2", "C3")}
    assert float(area_rows["S1"]) == pytest.approx(k.estate_area, abs=1e-4) and 10 < k.estate_area < 12
    precip = {x["source_code"]: x["value"] for x in rows if x["source_type"] == "STRATUM_CHARACTERISTIC"}
    assert precip["S1:PRECIPITATION_MM"] == "2200"
    # the output hash is reproducible from the frozen snapshot
    assert fw.execute(Vm0042V22(), inp["snapshot"]).output_sha256 == run["output_sha256"] == outs["output_sha256"]
    # calculation QA and approval: the analyst submits, a QA officer reviews and approves (not the analyst)
    ok(client.post(f"{CALC}/runs/{run['id']}/submit", headers=k.analyst.headers))
    assert client.post(f"{CALC}/runs/{run['id']}/approve", headers=k.analyst.headers, json={"reason": "own run"}).status_code == 403
    ok(client.post(f"{CALC}/qa/{run['id']}/start", headers=c.t.qa.headers))
    qa_view = ok(client.post(f"{CALC}/qa/{run['id']}/complete", headers=c.t.qa.headers,
                             json={"result": "PASS", "notes": "Inputs, lineage and outputs checked against the hand calculation"}))
    assert "FAIL" not in {x["result"] for x in qa_view["checks"]}, qa_view["checks"]
    run = ok(client.post(f"{CALC}/runs/{run['id']}/approve", headers=c.t.qa.headers, json={"reason": "VM0042 calculation approved"}))
    assert run["status"] == "APPROVED"
    assert ok(client.get(f"{PR}/{k.pid}", headers=c.t.pm.headers))["status"] == "CALCULATED"
    assert val["BUFFER_ER"] == pytest.approx(exp["bu_er"], rel=1e-6, abs=1e-12)
    SUMMARY.update(vcus=vcus, ref=val["REF_MASS_S1"], wp=val["DCO2_SOIL_WP"], bsl=val["DCO2_SOIL_BSL"], unc=val["UNC_PCT"],
                   er=val["ER_SOURCES"], lk=val["LK_TOTAL"], buffer_cr=val["BUFFER_CR"], area=k.estate_area)
    credits_to_payout(client, db, k, run, vcus)


SUMMARY: dict[str, Any] = {}                 # key figures of the last run (printed with -s)
SALE_QTY, PRICE, COST, FARMER_SHARE = 100, Decimal("1800.00"), Decimal("15000.00"), Decimal("60")


def credits_to_payout(client: TestClient, db: Session, k: Coffee, run: dict, vcus: int) -> None:
    """Steps 10-14: internal pre-verification, VVB verification, registry issuance and ledger, marketplace sale, settlement and payout."""
    t, pid, mpid = k.t, k.pid, k.periods[2]["id"]
    qa, pm = t.qa, t.pm
    # 10. internal pre-verification: calculation report, readiness review submitted by the analyst, READY decided by QA
    rep = ok(client.post(f"{CALC}/runs/{run['id']}/reports", headers=k.analyst.headers), 201)
    assert rep["status"] == "CURRENT" and rep["version"] == 1
    view = ok(client.get(f"{CALC}/projects/{pid}/verification-readiness", headers=qa.headers, params={"monitoring_period_id": mpid}))
    assert view["ready_to_submit"] and view["blockers"] == [], view
    rr = ok(client.post(f"{CALC}/projects/{pid}/verification-readiness", headers=k.analyst.headers, json={"monitoring_period_id": mpid}), 201)
    assert ok(client.post(f"{CALC}/readiness/{rr['id']}/submit", headers=k.analyst.headers))["status"] == "SUBMITTED"
    r = client.post(f"{CALC}/readiness/{rr['id']}/approve", headers=k.analyst.headers, json={"notes": "own submission"})
    assert r.status_code == 403, r.text
    rr = ok(client.post(f"{CALC}/readiness/{rr['id']}/approve", headers=qa.headers, json={"notes": "internal pre-verification complete"}))
    assert rr["status"] == "READY"
    # 11. VVB: assignment proposed by the developer, accepted with a conflict-of-interest declaration, package, decision VERIFIED
    vvb_org = make_org(db, org_type="VVB")
    vvb = staff(db, client, vvb_org, "VVB_REVIEWER")
    coi = "No financial, family or contractual relationship with the developer, the estate or its owner in the last five years."
    a = ok(client.post(f"{V}/verification/projects/{pid}/assignments", headers=pm.headers,
                       json={"monitoring_period_id": mpid, "vvb_organization_id": str(vvb_org.id)}), 201)
    assert a["status"] == "PROPOSED"
    acc = ok(client.post(f"{V}/vvb/assignments/{a['id']}/accept", headers=vvb.headers, json={"coi_declaration": coi}))
    assert acc["status"] == "ACCEPTED" and acc["coi_declaration"] == coi
    sub = ok(client.post(f"{V}/verification/assignments/{a['id']}/submit", headers=pm.headers), 201)
    assert sub["status"] == "SUBMITTED" and sub["readiness_review_id"] == rr["id"]
    pkg = ok(client.get(f"{V}/vvb/submissions/{sub['id']}/package", headers=vvb.headers))
    assert pkg["manifest_sha256"] == sub["manifest_sha256"]
    form = {"outcome": "VERIFIED", "rationale": "Soil sampling, laboratory QA and the VM0042 calculation verified on site and on file",
            "verified_quantity": str(vcus), "verified_quantity_unit": "tCO2e"}
    report = {"file": ("verification-report.pdf", PDF, "application/pdf")}
    assert client.post(f"{V}/vvb/submissions/{sub['id']}/decision", headers=pm.headers, data=form, files=report).status_code == 403
    dec = ok(client.post(f"{V}/vvb/submissions/{sub['id']}/decision", headers=vvb.headers, data=form, files=report), 201)
    assert dec["outcome"] == "VERIFIED" and dec["verified_quantity"] == str(vcus) and dec["verified_quantity_unit"] == "tCO2e"
    assert ok(client.get(f"{PR}/{pid}", headers=pm.headers))["status"] == "VERIFIED"
    # 12. registry: account, registration, submission, issuance recorded (registry manager) and confirmed (QA); ledger opening
    rm, cm = staff(db, client, t.org, "REGISTRY_MANAGER"), staff(db, client, t.org, "CREDIT_MANAGER")
    registry_org = make_org(db, org_type="REGISTRY")
    reg_url, cr_url = f"{V}/registry", f"{V}/credits"

    def rdoc(url: str, category: str | None = None, **extra: str) -> str:
        r = client.post(url, headers=rm.headers, files={"file": ("registry.pdf", PDF, "application/pdf")},
                        data={**({"category": category} if category else {}), **extra})
        return str(ok(r, 201)["document_id"])
    acct = ok(client.post(f"{reg_url}/accounts", headers=rm.headers, json={
        "organization_id": str(t.org.id), "registry_organization_id": str(registry_org.id), "external_account_id": "VERRA-ACC-KA-001",
        "label": "Verra registry account", "credit_unit": "VCU", "verified_unit_equivalent": "tCO2e",
        "document_checklist": [{"code": "PD", "title": "VCS project description", "source": "REGISTRY_SUBMISSION"}]}), 201)
    reg = ok(client.post(f"{reg_url}/projects/{pid}/registrations", headers=rm.headers, json={"registry_account_id": acct["id"]}), 201)
    ok(client.post(f"{reg_url}/registrations/{reg['id']}/record-registered", headers=rm.headers, json={
        "external_project_id": "VCS-KA-5123", "registered_on": "2026-09-01",
        "document_id": rdoc(f"{reg_url}/registrations/{reg['id']}/documents")}))
    rs = ok(client.post(f"{reg_url}/projects/{pid}/submissions", headers=rm.headers,
                        json={"monitoring_period_id": mpid, "registry_account_id": acct["id"]}), 201)
    sdocs = f"{reg_url}/submissions/{rs['id']}/documents"
    rdoc(sdocs, "REGISTRY_SUBMISSION", checklist_item="PD")
    assert ok(client.post(f"{reg_url}/submissions/{rs['id']}/freeze", headers=rm.headers, json={}))["status"] == "FROZEN"
    ok(client.post(f"{reg_url}/submissions/{rs['id']}/record-submitted", headers=rm.headers, json={
        "external_submission_id": "VCS-KA-REQ-01", "document_id": rdoc(sdocs, "REGISTRY_RESPONSE")}))
    r = ok(client.post(f"{reg_url}/submissions/{rs['id']}/record-response", headers=rm.headers, json={
        "outcome": "ACCEPTED", "document_id": rdoc(sdocs, "REGISTRY_RESPONSE"), "external_response_ref": "VERRA-ACK-01"}))
    assert r["status"] == "ACCEPTED"
    serials = [{"serial_start": "VCS-KA26-000001", "serial_end": f"VCS-KA26-{vcus:06d}", "quantity": vcus}]
    iss = ok(client.post(f"{reg_url}/submissions/{rs['id']}/issuances", headers=rm.headers, json={
        "external_issuance_id": "VCS-KA-ISS-01", "issuance_date": date.today().isoformat(), "quantity": vcus, "unit": "VCU",
        "document_id": rdoc(sdocs, "ISSUANCE_STATEMENT"), "batches": [{"vintage": "2026", "quantity": vcus, "serial_ranges": serials}]}), 201)
    assert iss["status"] == "RECORDED"
    assert client.post(f"{reg_url}/issuances/{iss['id']}/confirm", headers=rm.headers, json={"note": "own record"}).status_code == 403
    iss = ok(client.post(f"{reg_url}/issuances/{iss['id']}/confirm", headers=qa.headers, json={"note": "checked against the Verra statement"}))
    assert iss["status"] == "CONFIRMED" and {b["status"] for b in iss["batches"]} == {"ISSUED"}
    batch_id = iss["batches"][0]["id"]
    rv = ok(client.get(f"{reg_url}/projects/{pid}/periods/{mpid}", headers=rm.headers))
    assert rv["registry_status"] == "ISSUED" and rv["verified"]["value"] == str(vcus) and rv["issued"][0]["value"] == str(vcus)
    assert ok(client.get(f"{PR}/{pid}", headers=pm.headers))["status"] == "ISSUED"
    op = ok(client.post(f"{cr_url}/batches/{batch_id}/open", headers=cm.headers), 201)
    assert op["status"] == "REQUESTED" and op["owner_organization_id"] == str(t.org.id)
    assert ok(client.post(f"{cr_url}/openings/{op['id']}/confirm", headers=qa.headers))["status"] == "CONFIRMED"

    def seller_balance() -> dict:
        inv = ok(client.get(f"{cr_url}/inventory", headers=qa.headers, params={"project_id": pid}))
        b = next(x for x in inv["batches"] if x["batch_id"] == batch_id)
        return dict(next(x for x in b["balances"] if x["owner_organization_id"] == str(t.org.id)))
    bal = seller_balance()
    assert bal["available"] == vcus and bal["reserved"] == bal["retired"] == 0
    assert {p["state"] for p in ok(client.get(f"{cr_url}/batches/{batch_id}/positions", headers=qa.headers))} == {"AVAILABLE"}
    # 13. marketplace: buyer KYC verified by compliance, listing approved by finance, order, manual payment, INTERNAL delivery
    assert vcus >= SALE_QTY
    mp_url, ord_url, pay_url = f"{V}/marketplace", f"{V}/orders", f"{V}/payments"
    buyer_org = make_org(db, org_type="BUYER")
    buyer = staff(db, client, buyer_org, "BUYER")
    u = make_user(db, roles=[("MARKETPLACE_COMPLIANCE", None)])
    comp = Actor(u, login(client, u))
    fin, fin2, fin3, fin4 = (staff(db, client, t.org, "FINANCE_MANAGER") for _ in range(4))

    def pdf(url: str, who: Actor, category: str | None = None) -> str:
        r = client.post(url, headers=who.headers, files={"file": ("evidence.pdf", PDF, "application/pdf")},
                        data={"category": category} if category else {})
        return str(ok(r, 201)["document_id"])
    ok(client.post(f"{mp_url}/buyer-profile", headers=buyer.headers, json={"legal_name": "Mysuru Green Mobility Pvt Ltd", "country": "IN"}))
    pdf(f"{mp_url}/buyer-profile/documents", buyer)
    prof = ok(client.post(f"{mp_url}/buyer-profile/submit-kyc", headers=buyer.headers, json={}))
    assert prof["status"] == "KYC_SUBMITTED"
    assert ok(client.post(f"{mp_url}/buyer-profiles/{prof['id']}/verify", headers=comp.headers, json={}))["status"] == "KYC_VERIFIED"
    lst = ok(client.post(f"{mp_url}/listings", headers=cm.headers, json={
        "seller_organization_id": str(t.org.id), "batch_id": batch_id, "serial_range_id": None,
        "title": "Kodagu shade-coffee soil carbon VCUs, vintage 2026", "listed_quantity": SALE_QTY, "unit_price": str(PRICE),
        "currency": "INR", "payment_window_hours": 48}), 201)
    assert ok(client.post(f"{mp_url}/listings/{lst['id']}/submit", headers=cm.headers, json={}))["status"] == "PENDING_APPROVAL"
    assert client.post(f"{mp_url}/listings/{lst['id']}/approve", headers=cm.headers, json={}).status_code == 403
    assert ok(client.post(f"{mp_url}/listings/{lst['id']}/approve", headers=fin.headers, json={}))["status"] == "ACTIVE"
    order = ok(client.post(ord_url, headers=buyer.headers, json={"buyer_organization_id": str(buyer_org.id),
                                                                 "items": [{"listing_id": lst["id"], "quantity": SALE_QTY}]}), 201)
    assert order["status"] == "PLACED" and Decimal(order["total"]) == SALE_QTY * PRICE and order["items"][0]["status"] == "RESERVED"
    pay = ok(client.post(pay_url, headers=buyer.headers, json={
        "order_id": order["id"], "amount": order["total"], "currency": "INR", "external_reference": "NEFT-MGM-0001",
        "document_id": pdf(f"{ord_url}/{order['id']}/documents", buyer)}), 201)
    assert pay["status"] == "PENDING_CONFIRMATION" and pay["adapter_code"] == "MANUAL"
    assert ok(client.post(f"{pay_url}/{pay['id']}/confirm", headers=fin.headers, json={}))["status"] == "CONFIRMED"
    od = ok(client.get(f"{ord_url}/{order['id']}", headers=buyer.headers))
    assert od["status"] == "TRANSFER_PENDING" and od["items"][0]["reservation_status"] == "CONSUMED"
    done = ok(client.post(f"{ord_url}/transfers/{od['items'][0]['transfer_id']}/complete", headers=qa.headers, json={}))
    assert done["status"] == "COMPLETED" and done["items"][0]["status"] == "DELIVERED"
    held = ok(client.get(f"{cr_url}/holdings", headers=buyer.headers))["holdings"]
    assert sum(x["quantity"] for x in held if x["state"] == "AVAILABLE" and x["batch_id"] == batch_id) == SALE_QTY
    assert seller_balance()["available"] == vcus - SALE_QTY
    # 14. finance: revenue recognised at delivery, a project cost, revenue share, allocation, settlement, payout to the farmer
    rev = ok(client.get(f"{V}/revenue", headers=fin.headers, params={"project_id": pid}))
    assert len(rev) == 1 and rev[0]["kind"] == "RECOGNITION" and Decimal(rev[0]["amount"]) == SALE_QTY * PRICE
    assert rev[0]["monitoring_period_id"] == mpid
    cost = ok(client.post(f"{V}/costs", headers=pm.headers, json={
        "project_id": pid, "monitoring_period_id": mpid, "category": "LABORATORY", "description": "Soil analysis, 96 results (2 campaigns)",
        "amount": str(COST), "currency": "INR", "incurred_on": "2026-10-05"}), 201)
    pdf(f"{V}/costs/{cost['id']}/documents", pm)
    assert ok(client.post(f"{V}/costs/{cost['id']}/approve", headers=fin.headers, json={}))["status"] == "APPROVED"
    sv = ok(client.post(f"{V}/revenue-share", headers=pm.headers, json={
        "project_id": pid, "farmer_share_pct": str(FARMER_SHARE), "deduct_approved_costs": True, "rounding_mode": "HALF_UP",
        "effective_from": "2025-11-01", "source_reference": "Benefit-sharing clause 9, agreement KE-2025-01"}), 201)
    ok(client.post(f"{V}/revenue-share/{sv['id']}/submit", headers=pm.headers, json={}))
    share = ok(client.post(f"{V}/revenue-share/{sv['id']}/approve", headers=fin.headers, json={}))
    assert share["status"] == "APPROVED"
    rp = next(x for x in ok(client.get(f"{V}/revenue/projects", headers=pm.headers)) if x["id"] == pid)
    (pf,) = rp["farms"]
    al = ok(client.post(f"{V}/allocations", headers=pm.headers, json={
        "project_id": pid, "monitoring_period_id": mpid, "basis_reference": "Single participating estate (Kaveri Estate)",
        "lines": [{"project_farm_id": pf["project_farm_id"], "share_pct": "100"}]}), 201)
    ok(client.post(f"{V}/allocations/{al['id']}/submit", headers=pm.headers, json={}))
    alloc = ok(client.post(f"{V}/allocations/{al['id']}/approve", headers=fin.headers, json={}))
    st = ok(client.post(f"{V}/settlements", headers=fin2.headers, json={
        "project_id": pid, "monitoring_period_id": mpid, "currency": "INR", "revenue_share_version_id": share["id"],
        "allocation_version_id": alloc["id"]}), 201)
    st = ok(client.post(f"{V}/settlements/{st['id']}/calculate", headers=fin2.headers, json={}))
    gross, distributable = SALE_QTY * PRICE, SALE_QTY * PRICE - COST
    expected_payout = (distributable * FARMER_SHARE / 100).quantize(Decimal("0.01"))      # 100 % of the allocation: one estate
    assert Decimal(st["gross_revenue"]) == gross and Decimal(st["deducted_costs"]) == COST and Decimal(st["distributable"]) == distributable
    assert Decimal(st["farmer_total"]) == expected_payout and Decimal(st["developer_residual"]) == distributable - expected_payout
    assert ok(client.get(f"{V}/settlements/{st['id']}/verify", headers=fin.headers))["reproducible"] is True
    ok(client.post(f"{V}/settlements/{st['id']}/submit", headers=fin2.headers, json={}))
    assert client.post(f"{V}/settlements/{st['id']}/approve", headers=fin2.headers, json={}).status_code == 403
    assert ok(client.post(f"{V}/settlements/{st['id']}/approve", headers=fin3.headers, json={}))["status"] == "APPROVED"
    (po,) = ok(client.post(f"{V}/payouts/from-settlement/{st['id']}", headers=fin2.headers), 201)
    assert po["farmer_id"] == k.farmer["id"] and Decimal(po["amount"]) == expected_payout and po["status"] == "CALCULATED"
    fo = ok(client.post(f"{V}/farmers/{k.farmer['id']}/bank-accounts", headers=pm.headers, json={
        "account_holder_name": "Kaveri Ponnappa", "bank_name": "Canara Bank, Madikeri", "routing_code": "CNRB0000616",
        "account_number": "0616 1010 0234 5678"}), 201)
    ba = next(b for b in fo["bank_accounts"] if b["account_number_masked"].endswith("5678"))
    ok(client.post(f"{V}/farmers/{k.farmer['id']}/bank-accounts/{ba['id']}/decision", headers=fin.headers,
                   json={"decision": "VERIFIED", "notes": "Cancelled cheque and penny drop match"}))
    ok(client.post(f"{V}/payouts/{po['id']}/submit", headers=fin2.headers, json={}))
    ap = ok(client.post(f"{V}/payouts/{po['id']}/approve", headers=fin3.headers, json={}))
    assert ap["status"] == "APPROVED" and ap["bank_last4"] == "5678"
    assert client.post(f"{V}/payouts/{po['id']}/initiate", headers=fin3.headers, json={}).status_code == 403
    ini = ok(client.post(f"{V}/payouts/{po['id']}/initiate", headers=fin4.headers, json={}))
    assert ini["status"] == "PAYMENT_PENDING" and ini["adapter_code"] == "MANUAL"
    paid = ok(client.post(f"{V}/payouts/{po['id']}/confirm-paid", headers=fin4.headers, json={
        "external_reference": "NEFT-KE-0001", "document_id": pdf(f"{V}/payouts/{po['id']}/documents", fin4, "PAYOUT_EVIDENCE")}))
    assert paid["status"] == "PAID"
    rec = ok(client.post(f"{V}/payouts/{po['id']}/reconcile", headers=fin.headers, json={
        "statement_reference": "NEFT-KE-0001", "statement_amount": str(expected_payout), "statement_currency": "INR",
        "statement_date": date.today().isoformat(),
        "document_id": pdf(f"{V}/payouts/{po['id']}/documents", fin, "RECONCILIATION_EVIDENCE")}))
    assert rec["result"] == "MATCHED"
    final = ok(client.get(f"{V}/payouts/{po['id']}", headers=fin.headers))
    assert final["status"] == "RECONCILED" and Decimal(final["amount"]) == expected_payout
    assert [x["kind"] for x in final["transactions"]] == ["INITIATED", "PAID"]
    assert ok(client.get(f"{V}/settlements/{st['id']}", headers=fin.headers))["status"] == "COMPLETED"
    SUMMARY.update(sold=SALE_QTY, gross=str(gross), distributable=str(distributable), farmer_payout=str(expected_payout))
    print("\nVM0042 coffee e2e:", SUMMARY)


def test_vm0042_platform_blocks_missing_period_record_and_woody_removal(client: TestClient, db: Session, admin: Actor) -> None:
    """Step 9: the same estate, but the period's fertiliser record is missing (baseline urea exists): the run is BLOCKED rather than
    reading the gap as zero; after the record is added in a corrected dataset version, a YES woody-biomass declaration blocks it."""
    k = coffee_scenario(db, client, admin, p2_project={code: v for code, v in P2_PROJECT.items() if code != "V42_FSN"})
    c = k.c
    run, r = calculation_run(client, k)
    assert r.status_code == 409, r.text
    err = r.json()
    assert err["error_code"] == "MISSING_REQUIRED_INPUT" and err["details"]["reason"] == "PERIOD_RECORD_MISSING", err
    assert err["details"]["blockers"][0]["details"]["missing"] == [{"farm_id": k.estate["id"], "variable": "FSN"}]
    assert ok(client.get(f"{CALC}/runs/{run['id']}", headers=k.analyst.headers))["status"] == "BLOCKED"
    # correction: a new dataset version re-opens the period; the urea record is added and the woody declaration amended to YES
    ds = ok(client.post(f"{MRV}/datasets", headers=c.mrv.headers, json={"monitoring_period_id": k.periods[2]["id"]}), 201)
    assert ds["version"] == 2
    record(client, k, 2, "V42_FSN", "3000", "2026-09-15", "PROJECT")
    woody = next(x for x in k.records[2] if x["measurement_id"] == k.measurements["V42_WOODY"]["id"])
    ok(client.post(f"{MRV}/monitoring-records/{woody['record_id']}/amend", headers=c.mrv.headers,
                   json={"value": "YES", "reason": "Six silver oaks felled and 200 coffee bushes uprooted in block 3"}))
    ok(client.post(f"{MRV}/datasets/{ds['id']}/submit", headers=c.mrv.headers, json={"reason": "corrected records"}))
    ok(client.post(f"{MRV}/qa/{ds['id']}/start", headers=c.t.qa.headers))
    ok(client.post(f"{MRV}/qa/{ds['id']}/complete", headers=c.t.qa.headers, json={"result": "PASS", "notes": "corrections checked"}))
    assert ok(client.post(f"{MRV}/datasets/{ds['id']}/approve", headers=c.t.qa.headers, json={"reason": "v2 approved"}))["status"] == "APPROVED"
    run2, r = calculation_run(client, k)
    assert r.status_code == 409, r.text
    err = r.json()
    assert err["error_code"] == "WOODY_BIOMASS_REMOVED" and err["details"]["blockers"][0]["details"]["farms"] == [k.estate["id"]], err
    assert ok(client.get(f"{CALC}/runs/{run2['id']}", headers=k.analyst.headers))["status"] == "BLOCKED"
