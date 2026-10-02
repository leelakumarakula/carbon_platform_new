"""Phase 5 review decisions: V1 (production block of plan approval with CONFIGURATION_REQUIRED gaps — a platform governance
rule), S1/S2 (GPS tolerance, duplicate threshold, checklist and minimum photos are PLATFORM DEFAULTS, overridable by a
methodology SAMPLING rule, frozen per design version and per field record), and SOC never invented (AWAITING_ANALYSIS)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Project
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
