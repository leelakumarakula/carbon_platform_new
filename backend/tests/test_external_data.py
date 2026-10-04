"""External farm reference data (weather, soil, satellite NDVI, land records): provider parsing, the evidence-only API, RBAC,
append-only storage. No test reaches the internet: providers are replaced by TEST doubles or a fake transport."""
import json
import uuid
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.integrations import geodata
from app.models import AuditLog, FarmExternalObservation
from app.services import external_data_service as ext
from tests.phase2 import create_farm, dev_org, kyc_verified_farmer, set_boundary, square, staff

FA = "/api/v1/farms"
OPEN_METEO = {"latitude": 20.07, "longitude": 73.87, "daily_units": {"precipitation_sum": "mm"},
              "daily": {"time": ["2026-06-01", "2026-06-02", "2026-06-03"], "precipitation_sum": [0.0, 1.1, None],
                        "temperature_2m_max": [36.2, 35.4, 36.3], "temperature_2m_min": [24.0, 23.6, 23.8],
                        "et0_fao_evapotranspiration": [6.76, 5.81, 6.3]}}
SOILGRIDS = {"properties": {"layers": [
    {"name": "phh2o", "unit_measure": {"d_factor": 10, "mapped_units": "pH*10", "target_units": "-"},
     "depths": [{"label": "5-15cm", "values": {"mean": 70}}, {"label": "0-5cm", "values": {"mean": 69}}]},
    {"name": "soc", "unit_measure": {"d_factor": 10, "mapped_units": "dg/kg", "target_units": "g/kg"},
     "depths": [{"label": "0-5cm", "values": {"mean": 160}}, {"label": "15-30cm", "values": {"mean": None}}]},
    {"name": "ocs", "unit_measure": {"d_factor": 10}, "depths": [{"label": "0-30cm", "values": {"mean": 1}}]}]}}
SENTINEL = {"data": [
    {"interval": {"from": "2026-06-01T00:00:00Z", "to": "2026-06-11T00:00:00Z"},
     "outputs": {"ndvi": {"bands": {"B0": {"stats": {"min": 0.1, "max": 0.8, "mean": 0.456789, "stDev": 0.1, "sampleCount": 400,
                                                     "noDataCount": 40}}}}}},
    {"interval": {"from": "2026-06-11T00:00:00Z", "to": "2026-06-21T00:00:00Z"},
     "outputs": {"ndvi": {"bands": {"B0": {"stats": {"min": "NaN", "max": "NaN", "mean": "NaN", "sampleCount": 400,
                                                     "noDataCount": 400}}}}}}]}


# ---------------------------------------------------------------- provider parsing (canonical shapes)
def test_open_meteo_is_normalised_with_totals() -> None:
    s = geodata.parse_open_meteo(OPEN_METEO)
    assert [d["date"] for d in s["daily"]] == ["2026-06-01", "2026-06-02", "2026-06-03"] and s["daily"][2]["precipitation_mm"] is None
    assert s["totals"] == {"days": 3, "precipitation_mm": 1.1, "et0_mm": 18.87, "temp_max_mean_c": 35.97, "temp_min_mean_c": 23.8}
    with pytest.raises(geodata.ProviderUnavailable):
        geodata.parse_open_meteo({"daily": {"time": ["2026-06-01"], "precipitation_sum": [1, 2]}})


def test_soilgrids_values_are_scaled_ordered_and_unknown_properties_ignored() -> None:
    layers = geodata.parse_soilgrids(SOILGRIDS)["layers"]
    assert [(x["property"], x["depth"], x["value"], x["unit"]) for x in layers] == [
        ("soc", "0-5cm", 16.0, "g/kg"), ("soc", "15-30cm", None, "g/kg"), ("phh2o", "0-5cm", 6.9, ""), ("phh2o", "5-15cm", 7.0, "")]


def test_sentinel_statistics_keep_only_clear_intervals() -> None:
    rows = geodata.parse_sentinel_statistics(SENTINEL)
    assert rows[0] == {"from": "2026-06-01", "to": "2026-06-11", "mean": 0.4568, "min": 0.1, "max": 0.8, "stdev": 0.1, "sample_count": 400,
                       "no_data_count": 40}
    assert rows[1]["mean"] is None and rows[1]["sample_count"] == rows[1]["no_data_count"] == 400   # fully clouded: no statistic


def test_real_adapters_build_requests_without_leaking_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def transport(url: str, *, data: bytes | None = None, headers: dict[str, str] | None = None, timeout: int) -> bytes:
        calls.append({"url": url, "data": data, "headers": headers or {}})
        if "token" in url:
            return json.dumps({"access_token": "tok-123"}).encode()
        return json.dumps(SENTINEL if "statistics" in url else OPEN_METEO).encode()
    with pytest.raises(geodata.ProviderUnavailable):
        geodata._http("http://plain.example", timeout=1)                                          # HTTPS only
    monkeypatch.setattr(geodata, "_http", transport)
    req = geodata.FetchRequest(20.1, 73.9, square(), date(2026, 6, 1), date(2026, 6, 30))
    w = geodata.OpenMeteoWeather("https://weather.example/archive", 10).fetch(req)
    assert "start_date=2026-06-01" in calls[0]["url"] and "latitude=20.10000" in calls[0]["url"] and w.summary["totals"]["days"] == 3
    sat = geodata.CopernicusNdvi("https://id.example/token", "https://sh.example/statistics", "client", "s3cret", 30, 10).fetch(req)
    assert calls[2]["headers"]["Authorization"] == "Bearer tok-123"
    body = json.loads(calls[2]["data"])
    assert body["input"]["bounds"]["geometry"] == square() and body["input"]["data"][0]["dataFilter"]["maxCloudCoverage"] == 30
    assert "s3cret" not in json.dumps(sat.request) and "tok-123" not in json.dumps(sat.request)        # the stored request is clean
    assert len(sat.summary["intervals"]) == 2 and len(sat.raw_sha256) == 64
    with pytest.raises(geodata.ProviderNotConfigured):
        geodata.NoLandRecords().fetch(req)


# ---------------------------------------------------------------- the API (TEST doubles; nothing simulated at runtime)
class Fake:
    def __init__(self, provider: str, summary: dict[str, Any], fail: Exception | None = None) -> None:
        self.provider, self.label, self.summary, self.fail = provider, f"TEST {provider}", summary, fail
        self.requests: list[geodata.FetchRequest] = []

    def fetch(self, req: geodata.FetchRequest) -> geodata.Fetched:
        self.requests.append(req)
        if self.fail:
            raise self.fail
        return geodata.Fetched(self.provider, f"TEST {self.provider} dataset", self.summary, {"url": "https://test.invalid"}, "a" * 64)


@pytest.fixture()
def fakes(monkeypatch: pytest.MonkeyPatch) -> dict[str, Fake]:
    f = {"WEATHER": Fake("test-weather", geodata.parse_open_meteo(OPEN_METEO)), "SOIL": Fake("test-soil", geodata.parse_soilgrids(SOILGRIDS)),
         "SATELLITE_NDVI": Fake("test-ndvi", {"intervals": geodata.parse_sentinel_statistics(SENTINEL), "max_cloud_pct": 30})}

    def resolve(dt: str) -> tuple[Any, str, str, str | None]:
        if dt in f:
            return f[dt], f[dt].provider, f[dt].label, None
        return None, "manual", "Land records", "No public land-records API."
    monkeypatch.setattr(ext, "_resolve", resolve)
    return f


@pytest.fixture()
def world(db: Session, client: TestClient) -> dict[str, Any]:
    org = dev_org(db)
    agent, qa, gis = staff(db, client, org, "FIELD_AGENT"), staff(db, client, org, "QA_OFFICER"), staff(db, client, org, "GIS_SPECIALIST")
    farmer = kyc_verified_farmer(client, agent, qa, org)
    farm = create_farm(client, agent.headers, farmer["id"])
    return {"org": org, "agent": agent, "qa": qa, "gis": gis, "farm": farm}


def _period(days: int = 30, end_offset: int = 7) -> dict[str, str]:
    end = date.today() - timedelta(days=end_offset)
    return {"period_start": (end - timedelta(days=days)).isoformat(), "period_end": end.isoformat()}


def test_fetch_is_evidence_only_append_only_and_audited(client: TestClient, db: Session, world: dict[str, Any],
                                                        fakes: dict[str, Fake]) -> None:
    fid, h = world["farm"]["id"], world["agent"].headers
    ov = client.get(f"{FA}/{fid}/external-data", headers=h).json()
    assert ov["can_fetch"] is True and ov["has_boundary"] is False and ov["observations"] == []
    assert [(p["data_type"], p["enabled"]) for p in ov["providers"]] == [("WEATHER", True), ("SOIL", True), ("SATELLITE_NDVI", True),
                                                                         ("LAND_RECORD", False)]
    r = client.post(f"{FA}/{fid}/external-data/weather", headers=h, json=_period())
    assert r.status_code == 409 and r.json()["error_code"] == "NO_BOUNDARY"
    set_boundary(client, h, fid, square(74.30, 19.30))
    r = client.post(f"{FA}/{fid}/external-data/weather", headers=h, json=_period())
    assert r.status_code == 201, r.text
    w = r.json()
    assert w["data_type"] == "WEATHER" and w["boundary_version"] == 1 and w["summary"]["totals"]["days"] == 3 and w["fetched_at"].endswith("Z")
    assert w["sha256"] == "a" * 64 and w["environment"] == "LIVE" and w["fetched_by_name"]
    sent = fakes["WEATHER"].requests[0]
    assert abs(sent.latitude - 19.3005) < 1e-6 and sent.geometry is None                         # the boundary centroid
    again = client.post(f"{FA}/{fid}/external-data/weather", headers=h, json=_period())
    assert again.status_code == 409 and again.json()["error_code"] == "FETCHED_RECENTLY"
    soil = client.post(f"{FA}/{fid}/external-data/soil", headers=h, json=_period()).json()
    assert soil["period_start"] is None and soil["summary"]["layers"][0]["property"] == "soc"     # not a time series
    sat = client.post(f"{FA}/{fid}/external-data/satellite-ndvi", headers=world["gis"].headers, json=_period(90, 0))
    assert sat.status_code == 201 and fakes["SATELLITE_NDVI"].requests[0].geometry["type"] == "Polygon"   # GIS reviewers may fetch
    land = client.post(f"{FA}/{fid}/external-data/land-records", headers=h, json={})
    assert land.status_code == 409 and land.json()["error_code"] == "PROVIDER_NOT_CONFIGURED"
    ov = client.get(f"{FA}/{fid}/external-data", headers=h).json()
    assert [o["data_type"] for o in ov["observations"]] == ["SATELLITE_NDVI", "SOIL", "WEATHER"]           # newest first
    # evidence only: the farm itself is untouched
    assert client.get(f"{FA}/{fid}", headers=h).json()["status"] == "DRAFT"
    audit = db.scalars(select(AuditLog).where(AuditLog.action == "FARM_EXTERNAL_DATA_FETCHED", AuditLog.entity_id == fid)).all()
    assert len(audit) == 3
    assert db.scalars(select(FarmExternalObservation).where(FarmExternalObservation.farm_id == uuid.UUID(fid))).first() is not None


def test_observations_are_append_only_in_the_database() -> None:
    """The trigger fires per statement (even for zero rows) and aborts the transaction: run on a throwaway connection."""
    from app.core.database import get_engine
    for stmt in ("UPDATE dbo.farm_external_observations SET provider = provider WHERE 1 = 0",
                 "DELETE FROM dbo.farm_external_observations WHERE 1 = 0"):
        with get_engine().connect() as conn:
            with pytest.raises(DBAPIError, match="append-only"):
                conn.execute(text(stmt))
            conn.rollback()


def test_periods_permissions_and_provider_outage(client: TestClient, db: Session, world: dict[str, Any], fakes: dict[str, Fake]) -> None:
    fid, h = world["farm"]["id"], world["agent"].headers
    set_boundary(client, h, fid, square(74.32, 19.32))
    for body in ({}, _period(10, -3), {"period_start": "2026-06-30", "period_end": "2026-06-01"}, _period(800)):
        r = client.post(f"{FA}/{fid}/external-data/weather", headers=h, json=body)
        assert r.status_code == 422 and r.json()["error_code"] == "INVALID_PERIOD", body
    early = client.post(f"{FA}/{fid}/external-data/satellite-ndvi", headers=h, json={"period_start": "2016-01-01", "period_end": "2016-02-01"})
    assert early.json()["error_code"] == "INVALID_PERIOD"                                        # before the Sentinel-2 archive
    # read-only staff see the data but cannot fetch; another organization cannot even see the farm
    assert client.get(f"{FA}/{fid}/external-data", headers=world["qa"].headers).json()["can_fetch"] is False
    assert client.post(f"{FA}/{fid}/external-data/soil", headers=world["qa"].headers, json={}).status_code == 403
    outsider = staff(db, client, dev_org(db), "FIELD_AGENT")
    assert client.get(f"{FA}/{fid}/external-data", headers=outsider.headers).status_code == 404
    # an outage is a clear 503 and writes nothing
    fakes["SOIL"].fail = geodata.ProviderUnavailable("the provider answered HTTP 502")
    r = client.post(f"{FA}/{fid}/external-data/soil", headers=h, json={})
    assert r.status_code == 503 and r.json()["error_code"] == "EXTERNAL_PROVIDER_UNAVAILABLE" and "HTTP 502" in r.json()["message"]
    assert db.scalars(select(FarmExternalObservation).where(FarmExternalObservation.farm_id == uuid.UUID(fid))).all() == []


def test_runtime_defaults_never_simulate(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import Settings, get_settings
    s = get_settings()
    assert ext.adapter_for("WEATHER")[0] is None and ext.adapter_for("SOIL")[0] is None                 # switched off in tests
    assert ext.adapter_for("SATELLITE_NDVI")[0] is None and ext.adapter_for("LAND_RECORD")[0] is None   # manual by default
    base = s.model_dump()
    with pytest.raises(ValueError, match="COPERNICUS_CLIENT_ID"):
        Settings(**{**base, "SATELLITE_PROVIDER": "copernicus", "COPERNICUS_CLIENT_ID": None})
    with pytest.raises(ValueError, match="WEATHER_PROVIDER"):
        Settings(**{**base, "WEATHER_PROVIDER": "mock"})
    with pytest.raises(ValueError, match="https"):
        Settings(**{**base, "SOILGRIDS_URL": "http://rest.isric.org/x"})
