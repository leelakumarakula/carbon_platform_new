"""Phase 5 review decisions: V1 (production block of plan approval with CONFIGURATION_REQUIRED gaps — a platform governance
rule), S1/S2 (GPS tolerance, duplicate threshold, checklist and minimum photos are PLATFORM DEFAULTS, overridable by a
methodology SAMPLING rule, frozen per design version and per field record), SOC never invented (AWAITING_ANALYSIS), and V2
(sample-based parameters are authoritative only as approved Phase 6 laboratory results — Phase 5 cannot enter them)."""
import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import MonitoringRecord, MrvPlanMeasurement, Project
from app.services import mrv_service
from tests.phase5 import MRV, MrvCtx, approved_design, approved_plan, approved_stratum, collect, collecting_period, locked_project, photo

CONFIGURED = {"quantification_approach": "MEASURE_AND_REMEASURE", "depth_top_cm": 0, "depth_bottom_cm": 30, "min_samples_per_stratum": 1,
              "statistical_design": "STRATIFIED_RANDOM"}


def _submitted_plan(client: TestClient, c: MrvCtx, **kw: object) -> dict:
    body = {"project_id": c.project["id"], "monitoring_frequency": "Once per period", "monitoring_start": "2026-06-01",
            "monitoring_end": "2036-05-31", **kw}
    plan = client.post(f"{MRV}/plans", headers=c.mrv.headers, json=body).json()
    assert client.post(f"{MRV}/plans/{plan['id']}/submit", headers=c.mrv.headers, json={"reason": "ready"}).status_code == 200
    return plan


def test_v1_production_blocks_gap_approval(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    c = locked_project(db, client, 76.10, 22.10, "8400 2000 3000")
    plan = _submitted_plan(client, c, quantification_approach="MEASURE_AND_REMEASURE", required_evidence="Photo per sample")
    monkeypatch.setattr(get_settings(), "APP_ENV", "production")
    view = client.get(f"{MRV}/plans/{plan['id']}", headers=c.t.qa.headers).json()
    assert view["gap_approval_policy"] == "PRODUCTION_BLOCK" and not view["can_approve"]
    assert any("CONFIGURATION_REQUIRED" in b for b in view["approval_blockers"])
    r = client.post(f"{MRV}/plans/{plan['id']}/approve", headers=c.t.qa.headers, json={"reason": "try anyway", "acknowledge_configuration_gaps": True})
    assert r.status_code == 409 and r.json()["error_code"] == "CONFIGURATION_REQUIRED"
    assert r.json()["details"]["policy"] == "PRODUCTION_BLOCK"   # acknowledgement is not an exception in production
    # outside production the audited acknowledgement still works (DEMO / development)
    monkeypatch.setattr(get_settings(), "APP_ENV", "development")
    r = client.post(f"{MRV}/plans/{plan['id']}/approve", headers=c.t.qa.headers, json={"reason": "dev ok", "acknowledge_configuration_gaps": True})
    assert r.status_code == 200 and r.json()["gaps_acknowledged_by"] == str(c.t.qa.user.id)


def test_v1_production_approval_when_fully_configured(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    c = locked_project(db, client, 76.20, 22.20, "8500 2000 3000", sampling=CONFIGURED)
    monkeypatch.setattr(get_settings(), "APP_ENV", "production")
    no_evidence = _submitted_plan(client, c)
    r = client.post(f"{MRV}/plans/{no_evidence['id']}/approve", headers=c.t.qa.headers, json={"reason": "configured"})
    assert r.json()["error_code"] == "CONFIGURATION_REQUIRED" and "required evidence" in r.json()["details"]["blockers"][0]
    assert client.post(f"{MRV}/plans/{no_evidence['id']}/return", headers=c.t.qa.headers, json={"reason": "configure evidence"}).status_code == 200
    client.patch(f"{MRV}/plans/{no_evidence['id']}", headers=c.mrv.headers, json={"required_evidence": "One field photo per sample"})
    assert client.post(f"{MRV}/plans/{no_evidence['id']}/submit", headers=c.mrv.headers, json={"reason": "again"}).status_code == 200
    r = client.post(f"{MRV}/plans/{no_evidence['id']}/approve", headers=c.t.qa.headers, json={"reason": "fully configured"})
    assert r.status_code == 200, r.text
    assert r.json()["configuration_status"] == "CONFIGURED" and r.json()["gaps_acknowledged_by"] is None


def test_v1_demo_projects_keep_acknowledgement(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "APP_ENV", "production")
    assert mrv_service.gap_approval_allowed(Project(environment="DEMO"))
    assert not mrv_service.gap_approval_allowed(Project(environment="LIVE"))


def test_s1_s2_platform_defaults_frozen_on_records(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    c = locked_project(db, client, 76.30, 22.30, "8600 2000 3000")
    approved_plan(client, c)
    mp = collecting_period(client, c)
    st = approved_stratum(client, c, "S1", [c.farms[0]["id"]])
    d = approved_design(client, c, mp["id"], [{"stratum_id": st["id"], "sample_count": 2}])
    fr = d["current"]["field_rules"]
    assert (fr["gps_tolerance_m"], fr["duplicate_distance_m"], fr["min_photos"], fr["checklist_version"]) == (30.0, 1.0, 1, "PLATFORM-DEFAULT-1")
    assert {fr["gps_tolerance_source"], fr["duplicate_distance_source"], fr["min_photos_source"], fr["checklist_source"]} == {"PLATFORM_DEFAULT"}
    assert "not requirements of any methodology" in fr["note"]
    pts = client.post(f"{MRV}/sampling-designs/{d['id']}/generate-points", headers=c.mrv.headers).json()["points"]
    client.post(f"{MRV}/sampling-points/assign", headers=c.supervisor.headers,
                json={"point_ids": [x["id"] for x in pts], "collector_id": str(c.collector.user.id)})
    fc = collect(client, c, pts[0], c.collector)
    assert fc["checklist_version"] == "PLATFORM-DEFAULT-1" and float(fc["gps_tolerance_m"]) == 30.0 and fc["min_photos"] == 1
    assert [i["key"] for i in fc["checklist_items"]] == fc["required_checklist"] and fc["checklist"]["photo_taken"] is True
    assert fc["analysis_status"] == "AWAITING_ANALYSIS"   # SOC comes from Phase 6; no value is entered
    # changing the defaults later never alters historical records or the existing design version
    monkeypatch.setattr(get_settings(), "GPS_MAX_DISTANCE_M", 5.0)
    monkeypatch.setattr(get_settings(), "FIELD_MIN_PHOTOS_PER_SAMPLE", 3)
    again = client.get(f"{MRV}/field-collections/{fc['id']}", headers=c.mrv.headers).json()
    assert float(again["gps_tolerance_m"]) == 30.0 and again["min_photos"] == 1
    second = collect(client, c, pts[1], c.collector)       # same design version → still 1 photo / 30 m
    assert second["min_photos"] == 1
    d2 = client.post(f"{MRV}/sampling-designs/{d['id']}/versions", headers=c.mrv.headers,
                     json={"statistical_design": "STRATIFIED_RANDOM", "depth_top_cm": "0", "depth_bottom_cm": "30",
                           "allocations": [{"stratum_id": st["id"], "sample_count": 1}]}).json()
    assert d2["field_rules"]["gps_tolerance_m"] == 5.0 and d2["field_rules"]["min_photos"] == 3   # only new versions pick up new defaults


def test_s1_s2_methodology_values_override_defaults(client: TestClient, db: Session) -> None:
    sampling = {**CONFIGURED, "gps_max_distance_m": 10, "min_photos_per_sample": 2, "duplicate_point_distance_m": 5,
                "field_checklist": [{"key": "soil_moisture_noted", "label": "Soil moisture noted (TEST rule)"}]}
    c = locked_project(db, client, 76.40, 22.40, "8700 2000 3000", sampling=sampling)
    approved_plan(client, c, quantification_approach=None)
    mp = collecting_period(client, c)
    st = approved_stratum(client, c, "S1", [c.farms[0]["id"]])
    d = approved_design(client, c, mp["id"], [{"stratum_id": st["id"], "sample_count": 1}])
    fr = d["current"]["field_rules"]
    assert (fr["gps_tolerance_m"], fr["min_photos"], fr["duplicate_distance_m"]) == (10.0, 2, 5.0)
    assert fr["gps_tolerance_source"] == fr["checklist_source"] == "METHODOLOGY" and fr["gps_tolerance_rule"] == "SMP"
    assert fr["checklist_version"].startswith("METHODOLOGY:") and [i["key"] for i in fr["checklist_items"]] == ["soil_moisture_noted"]
    (pt,) = client.post(f"{MRV}/sampling-designs/{d['id']}/generate-points", headers=c.mrv.headers).json()["points"]
    client.post(f"{MRV}/sampling-points/{pt['id']}/assign", headers=c.supervisor.headers, json={"collector_id": str(c.collector.user.id)})
    fc = client.post(f"{MRV}/field-collections", headers=c.collector.headers, json={"sampling_point_id": pt["id"]}).json()
    client.patch(f"{MRV}/field-collections/{fc['id']}", headers=c.collector.headers, json={
        "collected_at": "2026-07-01T09:00:00Z", "gps_latitude": float(pt["latitude"]) + 0.00015, "gps_longitude": float(pt["longitude"]),
        "actual_depth_top_cm": "0", "actual_depth_bottom_cm": "30", "checklist": {"location_confirmed": True}})
    photo(client, c, c.collector, "FIELD_COLLECTION", fc["id"])
    r = client.post(f"{MRV}/field-collections/{fc['id']}/submit", headers=c.collector.headers)
    missing = " ".join(r.json()["details"]["missing"])
    assert "at least 2 field photo(s)" in missing and "soil_moisture_noted" in missing
    assert "note explaining" in missing   # ~17 m from the point: beyond the methodology's 10 m (the 30 m default would pass)
    client.patch(f"{MRV}/field-collections/{fc['id']}", headers=c.collector.headers,
                 json={"checklist": {"soil_moisture_noted": True}, "deviation_note": "Shifted off the bund"})
    photo(client, c, c.collector, "FIELD_COLLECTION", fc["id"])
    assert client.post(f"{MRV}/field-collections/{fc['id']}/submit", headers=c.collector.headers).json()["status"] == "SUBMITTED"


def test_v2_sample_based_values_are_not_entered_in_phase5(client: TestClient, db: Session) -> None:
    """Decision V2: SOC (a methodology monitoring parameter measured on the samples) cannot be recorded as MRV monitoring data by
    anyone, through create or amend; the field collection is recorded instead and the value stays AWAITING_ANALYSIS."""
    c = locked_project(db, client, 76.50, 22.50, "8800 2000 3000")
    plan = approved_plan(client, c)
    soc = next(m for m in plan["measurements"] if m["code"] == "SOC")
    assert (soc["source"], soc["level"], soc["value_type"]) == ("METHODOLOGY", "SAMPLING_POINT", "NUMBER")
    mp = collecting_period(client, c)
    st = approved_stratum(client, c, "S1", [c.farms[0]["id"]])
    d = approved_design(client, c, mp["id"], [{"stratum_id": st["id"], "sample_count": 1}])
    (pt,) = client.post(f"{MRV}/sampling-designs/{d['id']}/generate-points", headers=c.mrv.headers).json()["points"]
    client.post(f"{MRV}/sampling-points/{pt['id']}/assign", headers=c.supervisor.headers, json={"collector_id": str(c.collector.user.id)})
    fc = collect(client, c, pt, c.collector)
    body = {"monitoring_period_id": mp["id"], "measurement_id": soc["id"], "sampling_point_id": pt["id"], "field_collection_id": fc["id"],
            "value": 42.5, "unit": "t C/ha", "observed_on": "2026-07-01", "source": "INSTRUMENT"}
    for actor in (c.collector, c.mrv):   # neither the collector nor the MRV manager can enter it
        r = client.post(f"{MRV}/monitoring-records", headers=actor.headers, json=body)
        assert r.status_code == 422 and r.json()["error_code"] == "LABORATORY_RESULT_REQUIRED"
        assert r.json()["details"]["analysis_status"] == "AWAITING_ANALYSIS"
    stored = db.scalar(select(func.count()).select_from(MonitoringRecord).where(MonitoringRecord.measurement_id == uuid.UUID(soc["id"])))
    assert stored == 0
    # a pre-existing value (e.g. imported before this guard) cannot be amended into an authoritative-looking record either
    legacy = MonitoringRecord(project_id=uuid.UUID(c.project["id"]), monitoring_period_id=uuid.UUID(mp["id"]), measurement_id=uuid.UUID(soc["id"]),
                              record_id=uuid.uuid4(), sampling_point_id=uuid.UUID(pt["id"]), value_number=1, unit="t C/ha", observed_on=date(2026, 7, 1))
    db.add(legacy)
    db.flush()
    r = client.post(f"{MRV}/monitoring-records/{legacy.record_id}/amend", headers=c.mrv.headers, json={"value": 50, "reason": "lab said so"})
    assert r.json()["error_code"] == "LABORATORY_RESULT_REQUIRED"
    # project-configured farm activity data is unaffected
    till = next(m for m in plan["measurements"] if m["code"] == "TILL")
    assert not mrv_service.is_laboratory_parameter(db, db.get(MrvPlanMeasurement, uuid.UUID(till["id"])))  # type: ignore[arg-type]
    assert fc["analysis_status"] == "AWAITING_ANALYSIS"


PROVENANCE_RULES = [  # TEST fixtures: the provenance is declared, deliberately independent of unit, name and type
    {"rule_code": "SOC", "title": "Soil organic carbon", "parameter": "Soil organic carbon", "unit": "t C/ha", "measurement_source": "LABORATORY"},
    {"rule_code": "TEXT", "title": "Texture class", "parameter": "Parameter X", "unit": None, "measurement_source": "LABORATORY"},
    {"rule_code": "NADD", "title": "Compost carbon", "parameter": "Organic carbon added in compost", "unit": "t C/ha",
     "measurement_source": "FIELD_ACTIVITY"},
    {"rule_code": "PHT", "title": "Plant height", "parameter": "Plant height", "unit": "cm", "measurement_source": "FIELD"},
]


def test_v2a_guard_uses_declared_provenance_not_unit_or_name(client: TestClient, db: Session) -> None:
    c = locked_project(db, client, 76.60, 22.60, "8900 2000 3000", monitoring_rules=PROVENANCE_RULES)
    req = client.get(f"{MRV}/projects/{c.project['id']}/requirements", headers=c.mrv.headers).json()
    assert {m["rule_code"]: m["measurement_source"] for m in req["monitoring"]} == {r["rule_code"]: r["measurement_source"] for r in PROVENANCE_RULES}
    plan = approved_plan(client, c)
    ms = {m["code"]: m for m in plan["measurements"]}
    assert {k: ms[k]["measurement_source"] for k in ("SOC", "TEXT", "NADD", "PHT")} == \
        {"SOC": "LABORATORY", "TEXT": "LABORATORY", "NADD": "FIELD_ACTIVITY", "PHT": "FIELD"}
    assert ms["TILL"]["measurement_source"] is None   # project-configured: no methodology provenance
    assert ms["TEXT"]["level"] == "SAMPLING_POINT"    # LABORATORY attaches to samples even without a unit
    mp = collecting_period(client, c)
    st = approved_stratum(client, c, "S1", [c.farms[0]["id"]])
    d = approved_design(client, c, mp["id"], [{"stratum_id": st["id"], "sample_count": 1}])
    (pt,) = client.post(f"{MRV}/sampling-designs/{d['id']}/generate-points", headers=c.mrv.headers).json()["points"]
    base = {"monitoring_period_id": mp["id"], "sampling_point_id": pt["id"], "observed_on": "2026-07-01"}
    # LABORATORY: refused with and without a unit, whatever the name
    for code, value in (("SOC", 41.0), ("TEXT", "Clay loam")):
        r = client.post(f"{MRV}/monitoring-records", headers=c.mrv.headers, json={**base, "measurement_id": ms[code]["id"], "value": value})
        assert r.status_code == 422 and r.json()["error_code"] == "LABORATORY_RESULT_REQUIRED", code
        assert r.json()["details"]["measurement_source"] == "LABORATORY"
    # FIELD_ACTIVITY with a lab-looking unit and name, and FIELD: normal Phase 5 rules apply
    for code, value in (("NADD", 1.2), ("PHT", 54)):
        r = client.post(f"{MRV}/monitoring-records", headers=c.collector.headers, json={**base, "measurement_id": ms[code]["id"], "value": value})
        assert r.status_code == 201, (code, r.text)
    # QA lists only the declared LABORATORY parameters as awaiting analysis
    assert {mrv_service.measurement_source(db, db.get(MrvPlanMeasurement, uuid.UUID(ms[k]["id"])))  # type: ignore[arg-type]
            for k in ("SOC", "TEXT")} == {"LABORATORY"}


def test_v2a_unclassified_rule_is_explicit_configuration_gap(client: TestClient, db: Session) -> None:
    """A pre-existing rule without a declared provenance is never guessed: it is a CONFIGURATION_REQUIRED gap and cannot be captured."""
    from app.models import MethodologyMonitoringRule
    c = locked_project(db, client, 76.70, 22.70, "9000 2000 3000")
    db.add(MethodologyMonitoringRule(methodology_version_id=uuid.UUID(c.version_id), rule_code="OLD1", title="Legacy rule",
                                     parameter="Legacy parameter", unit="kg/ha", measurement_source="UNCLASSIFIED"))
    db.flush()
    req = client.get(f"{MRV}/projects/{c.project['id']}/requirements", headers=c.mrv.headers).json()
    assert any("OLD1" in g for g in req["gaps"])
    plan = approved_plan(client, c)
    old = next(m for m in plan["measurements"] if m["code"] == "OLD1")
    assert old["measurement_source"] == "UNCLASSIFIED"
    mp = collecting_period(client, c)
    st = approved_stratum(client, c, "S1", [c.farms[0]["id"]])
    d = approved_design(client, c, mp["id"], [{"stratum_id": st["id"], "sample_count": 1}])
    (pt,) = client.post(f"{MRV}/sampling-designs/{d['id']}/generate-points", headers=c.mrv.headers).json()["points"]
    r = client.post(f"{MRV}/monitoring-records", headers=c.mrv.headers, json={
        "monitoring_period_id": mp["id"], "measurement_id": old["id"], "sampling_point_id": pt["id"], "value": 3, "observed_on": "2026-07-01"})
    assert r.status_code == 422 and r.json()["error_code"] == "MEASUREMENT_SOURCE_UNCLASSIFIED"


TILL = {"code": "TILL", "name": "Tillage operations", "category": "TILLAGE", "value_type": "CHOICE",
        "allowed_values": ["CONVENTIONAL", "REDUCED", "NO_TILL"], "level": "FARM"}


def test_v2b_custom_measurements_are_supplementary_never_laboratory(client: TestClient, db: Session) -> None:
    """Decision V2-B: a user-created measurement named like a lab parameter is a supplementary observation — it can be recorded,
    is marked non-authoritative everywhere (API, records, snapshot) and never replaces the methodology LABORATORY parameter."""
    c = locked_project(db, client, 76.80, 22.80, "9100 2000 3000", monitoring_rules=PROVENANCE_RULES)
    soc_rule = next(r for r in client.get(f"{MRV}/projects/{c.project['id']}/requirements", headers=c.mrv.headers).json()["monitoring"]
                    if r["rule_code"] == "SOC")
    custom = {"code": "SOC_PCT", "name": "SOC %", "category": "SOIL", "value_type": "NUMBER", "unit": "%", "level": "SAMPLING_POINT"}
    spoof = {"code": "SOC2", "name": "Soil organic carbon", "category": "SOIL", "value_type": "NUMBER", "unit": "t C/ha", "level": "SAMPLING_POINT",
             "source": "METHODOLOGY", "monitoring_rule_id": soc_rule["rule_id"], "measurement_source": "LABORATORY"}  # extra fields ignored
    plan = approved_plan(client, c, measurements=[TILL, custom, spoof])
    ms = {m["code"]: m for m in plan["measurements"]}
    for code in ("SOC_PCT", "SOC2", "TILL"):   # user-created: no methodology origin or provenance, whatever the name or unit
        assert (ms[code]["source"], ms[code]["monitoring_rule_id"], ms[code]["measurement_source"]) == ("PROJECT_CONFIGURED", None, None), code
        assert (ms[code]["data_role"], ms[code]["authoritative"]) == ("SUPPLEMENTARY_OBSERVATION", False), code
    assert (ms["SOC"]["data_role"], ms["SOC"]["authoritative"]) == ("LABORATORY_PARAMETER", False)
    assert (ms["NADD"]["data_role"], ms["NADD"]["authoritative"]) == ("METHODOLOGY_PARAMETER", True)
    assert (ms["PHT"]["data_role"], ms["PHT"]["authoritative"]) == ("METHODOLOGY_PARAMETER", True)
    # a custom measurement cannot take over the methodology parameter's code in a plan
    draft = client.post(f"{MRV}/plans", headers=c.mrv.headers, json={"project_id": c.project["id"]}).json()
    r = client.post(f"{MRV}/plans/{draft['id']}/measurements", headers=c.mrv.headers, json={**custom, "code": "SOC"})
    assert r.status_code == 409 and r.json()["error_code"] == "MEASUREMENT_EXISTS"
    client.post(f"{MRV}/plans/{draft['id']}/withdraw", headers=c.mrv.headers, json={"reason": "test draft only"})

    mp = collecting_period(client, c)
    st = approved_stratum(client, c, "S1", [c.farms[0]["id"]])
    d = approved_design(client, c, mp["id"], [{"stratum_id": st["id"], "sample_count": 1}])
    (pt,) = client.post(f"{MRV}/sampling-designs/{d['id']}/generate-points", headers=c.mrv.headers).json()["points"]
    client.post(f"{MRV}/sampling-points/{pt['id']}/assign", headers=c.supervisor.headers, json={"collector_id": str(c.collector.user.id)})
    fc = collect(client, c, pt, c.collector)
    base = {"monitoring_period_id": mp["id"], "sampling_point_id": pt["id"], "field_collection_id": fc["id"], "observed_on": "2026-07-01"}
    # 1. the methodology LABORATORY parameter stays protected
    r = client.post(f"{MRV}/monitoring-records", headers=c.mrv.headers, json={**base, "measurement_id": ms["SOC"]["id"], "value": 1.72})
    assert r.json()["error_code"] == "LABORATORY_RESULT_REQUIRED"
    # 2./3. the custom "SOC %" value is kept, but only as a non-authoritative supplementary observation
    r = client.post(f"{MRV}/monitoring-records", headers=c.collector.headers, json={**base, "measurement_id": ms["SOC_PCT"]["id"], "value": 1.72})
    assert r.status_code == 201 and (r.json()["data_role"], r.json()["authoritative"]) == ("SUPPLEMENTARY_OBSERVATION", False)
    # 5. methodology FIELD / FIELD_ACTIVITY parameters keep working and are authoritative
    for code, value in (("NADD", 1.2), ("PHT", 54)):
        r = client.post(f"{MRV}/monitoring-records", headers=c.collector.headers, json={**base, "measurement_id": ms[code]["id"], "value": value})
        assert r.status_code == 201 and (r.json()["data_role"], r.json()["authoritative"]) == ("METHODOLOGY_PARAMETER", True), code
    # 4. in the dataset the custom value never stands in for the laboratory parameter
    ds = client.post(f"{MRV}/datasets", headers=c.mrv.headers, json={"monitoring_period_id": mp["id"]}).json()
    assert client.post(f"{MRV}/datasets/{ds['id']}/submit", headers=c.mrv.headers, json={"reason": "collected"}).status_code == 200
    snap = client.get(f"{MRV}/datasets/{ds['id']}/snapshot", headers=c.t.qa.headers).json()["snapshot"]
    recs = {x["measurement_code"]: x for x in snap["monitoring_records"]}
    assert (recs["SOC_PCT"]["origin"], recs["SOC_PCT"]["data_role"], recs["SOC_PCT"]["authoritative"]) == \
        ("PROJECT_CONFIGURED", "SUPPLEMENTARY_OBSERVATION", False)
    assert recs["NADD"]["authoritative"] and recs["PHT"]["authoritative"] and recs["NADD"]["measurement_source"] == "FIELD_ACTIVITY"
    assert "SOC" not in recs and not any(x["data_role"] == "LABORATORY_PARAMETER" for x in snap["monitoring_records"])
    roles = snap["data_roles"]
    assert roles["laboratory_parameters_awaiting_analysis"] == ["SOC", "TEXT"]
    assert (roles["authoritative_methodology_records"], roles["supplementary_observations"]) == (2, 1)
    client.post(f"{MRV}/qa/{ds['id']}/start", headers=c.t.qa.headers)
    checks = {x["key"]: x for x in client.get(f"{MRV}/qa/{ds['id']}", headers=c.t.qa.headers).json()["checks"]}
    assert any(x.startswith("SOC (") and "AWAITING_ANALYSIS" in x for x in checks["sample_analysis_pending"]["details"])


FIELD_KIT_RULES = [  # TEST fixtures: same names/units on both sides — only the declared measurement_source differs
    {"rule_code": "PHF", "title": "Soil pH (field kit)", "parameter": "Soil pH", "unit": "pH units", "measurement_source": "FIELD"},
    {"rule_code": "PHL", "title": "Soil pH (laboratory)", "parameter": "Soil pH", "unit": "pH units", "measurement_source": "LABORATORY"},
    {"rule_code": "BDF", "title": "Bulk density (core in field)", "parameter": "Bulk density", "unit": "g/cm3", "measurement_source": "FIELD"},
    {"rule_code": "SOCF", "title": "SOC field estimate", "parameter": "Soil organic carbon", "unit": "%", "measurement_source": "FIELD"},
    {"rule_code": "NUTL", "title": "Available phosphorus", "parameter": "Parameter Y", "unit": None, "measurement_source": "LABORATORY"},
]


def test_v2c_field_kit_provenance_is_only_the_declared_source(client: TestClient, db: Session) -> None:
    """Decision V2-C: FIELD vs LABORATORY follows the methodology's declared measurement_source only — a field-kit pH, a field bulk
    density or a field SOC estimate declared FIELD is recorded in Phase 5; the same parameter declared LABORATORY is refused."""
    c = locked_project(db, client, 76.90, 22.90, "9200 2000 3000", monitoring_rules=FIELD_KIT_RULES)
    plan = approved_plan(client, c)
    ms = {m["code"]: m for m in plan["measurements"]}
    mp = collecting_period(client, c)
    st = approved_stratum(client, c, "S1", [c.farms[0]["id"]])
    d = approved_design(client, c, mp["id"], [{"stratum_id": st["id"], "sample_count": 1}])
    (pt,) = client.post(f"{MRV}/sampling-designs/{d['id']}/generate-points", headers=c.mrv.headers).json()["points"]
    base = {"monitoring_period_id": mp["id"], "sampling_point_id": pt["id"], "observed_on": "2026-07-01"}
    # a. FIELD parameters that "look like" laboratory tests are recorded normally and are authoritative
    for code, value in (("PHF", 6.8), ("BDF", 1.31), ("SOCF", 1.9)):
        r = client.post(f"{MRV}/monitoring-records", headers=c.collector.headers, json={**base, "measurement_id": ms[code]["id"], "value": value})
        assert r.status_code == 201, (code, r.text)
        assert (r.json()["data_role"], r.json()["authoritative"]) == ("METHODOLOGY_PARAMETER", True), code
    # b. LABORATORY parameters are refused, whatever their name or unit
    for code, value in (("PHL", 6.8), ("NUTL", 12)):
        r = client.post(f"{MRV}/monitoring-records", headers=c.mrv.headers, json={**base, "measurement_id": ms[code]["id"], "value": value})
        assert r.status_code == 422 and r.json()["error_code"] == "LABORATORY_RESULT_REQUIRED", code
    # c. identical name and unit (Soil pH, pH units) → different treatment, decided by the declared source alone
    assert (ms["PHF"]["name"], ms["PHF"]["unit"]) == (ms["PHL"]["name"], ms["PHL"]["unit"])
    assert (ms["PHF"]["measurement_source"], ms["PHL"]["measurement_source"]) == ("FIELD", "LABORATORY")


def test_v2c_declared_source_is_authoritative_not_name_unit_type_or_level(client: TestClient, db: Session) -> None:
    """d. Changing a measurement's name, unit, type or level never changes its role; changing only the rule's declared
    measurement_source does (in-session only; nothing is committed)."""
    from app.models import MethodologyMonitoringRule
    c = locked_project(db, client, 77.00, 23.00, "9300 2000 3000", monitoring_rules=FIELD_KIT_RULES[:1])
    plan = approved_plan(client, c)
    m = db.get(MrvPlanMeasurement, uuid.UUID(next(x["id"] for x in plan["measurements"] if x["code"] == "PHF")))
    assert m is not None and mrv_service.data_role(db, m) == mrv_service.METHODOLOGY_PARAMETER
    for name, unit, value_type, level in (("Soil organic carbon", "%", "NUMBER", "SAMPLING_POINT"), ("Bulk density", "g/cm3", "NUMBER", "FARM"),
                                          ("Lab nitrate analysis", None, "TEXT", "PROJECT"), ("pH (laboratory)", "pH units", "NUMBER", "STRATUM")):
        m.name, m.unit, m.value_type, m.level = name, unit, value_type, level
        assert mrv_service.data_role(db, m) == mrv_service.METHODOLOGY_PARAMETER, name
        assert not mrv_service.is_laboratory_parameter(db, m)
    rule = db.get(MethodologyMonitoringRule, m.monitoring_rule_id)
    assert rule is not None
    rule.measurement_source = "LABORATORY"
    assert mrv_service.data_role(db, m) == mrv_service.LABORATORY_PARAMETER and mrv_service.is_laboratory_parameter(db, m)
    rule.measurement_source = "FIELD"   # restore (the test transaction is rolled back anyway)
