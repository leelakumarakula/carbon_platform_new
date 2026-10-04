"""External farm reference data — weather, soil, satellite vegetation index, land records (spec §11 / §42).

Every result is EVIDENCE ONLY: it is fetched when a user asks for it, stored append-only with the provider, dataset, request and the
SHA-256 of the provider's raw response, and is never an input to a status change, a verification decision or a calculation (a
methodology would have to name a dataset explicitly for that).

Adapters translate one provider into the canonical, normalised `Fetched` result. Nothing is simulated at runtime: a disabled provider
raises `ProviderNotConfigured`, an unreachable one `ProviderUnavailable`. Test doubles live in the test suite only (D38).

  WEATHER         open-meteo   Open-Meteo historical weather API (ERA5 reanalysis), daily, no key
  SOIL            soilgrids    ISRIC SoilGrids 2.0 REST (250 m modelled soil properties), no key
  SATELLITE_NDVI  copernicus   Copernicus Data Space Ecosystem, Sentinel Hub Statistical API on Sentinel-2 L2A (OAuth client)
  LAND_RECORD     manual       no public land-records API exists (Indian state portals are browse-only) — documents are uploaded
"""
import hashlib
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

DATA_TYPES = ("WEATHER", "SOIL", "SATELLITE_NDVI", "LAND_RECORD")
_MAX_RESPONSE_BYTES = 5 * 1024 * 1024


class ProviderNotConfigured(RuntimeError):
    pass


class ProviderUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class FetchRequest:
    latitude: float                       # boundary centroid
    longitude: float
    geometry: dict[str, Any] | None       # boundary GeoJSON (WGS84), for area statistics
    period_start: date | None
    period_end: date | None


@dataclass(frozen=True)
class Fetched:
    provider: str
    dataset: str
    summary: dict[str, Any]               # normalised, provider-independent shape
    request: dict[str, Any]               # what was asked (no credentials)
    raw_sha256: str                       # of the provider's raw response bytes


class GeoDataAdapter(Protocol):
    provider: str
    label: str

    def fetch(self, req: FetchRequest) -> Fetched: ...


def _http(url: str, *, data: bytes | None = None, headers: dict[str, str] | None = None, timeout: int) -> bytes:
    """HTTPS only, certificate-verified, bounded response size. Errors never carry the request's credentials."""
    if not url.startswith("https://"):
        raise ProviderUnavailable("external data providers are reached over HTTPS only")
    req = urllib.request.Request(url, data=data, headers={"Accept": "application/json", "User-Agent": "carbon-platform/1.0",  # noqa: S310
                                                          **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as r:  # noqa: S310 (https enforced)
            body = r.read(_MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as e:
        raise ProviderUnavailable(f"the provider answered HTTP {e.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ProviderUnavailable(f"the provider could not be reached ({type(e).__name__})") from None
    if len(body) > _MAX_RESPONSE_BYTES:
        raise ProviderUnavailable("the provider's response is too large")
    return body


def _json(body: bytes) -> Any:
    try:
        return json.loads(body)
    except ValueError:
        raise ProviderUnavailable("the provider's response is not valid JSON") from None


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _mean(xs: list[float | None]) -> float | None:
    vals = [x for x in xs if x is not None]
    return round(sum(vals) / len(vals), 2) if vals else None


def _sum(xs: list[float | None]) -> float | None:
    vals = [x for x in xs if x is not None]
    return round(sum(vals), 2) if vals else None


def _sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


# ---------------------------------------------------------------- weather: Open-Meteo historical (ERA5)
WEATHER_DAILY = ("precipitation_sum", "temperature_2m_max", "temperature_2m_min", "et0_fao_evapotranspiration")


def parse_open_meteo(doc: dict[str, Any]) -> dict[str, Any]:
    d = doc.get("daily") or {}
    days = d.get("time") or []
    cols = {k: list(d.get(k) or [None] * len(days)) for k in WEATHER_DAILY}
    if any(len(v) != len(days) for v in cols.values()):
        raise ProviderUnavailable("the weather response is inconsistent")
    daily = [{"date": t, "precipitation_mm": _num(cols["precipitation_sum"][i]), "temp_max_c": _num(cols["temperature_2m_max"][i]),
              "temp_min_c": _num(cols["temperature_2m_min"][i]), "et0_mm": _num(cols["et0_fao_evapotranspiration"][i])}
             for i, t in enumerate(days)]
    totals = {"days": len(daily), "precipitation_mm": _sum([x["precipitation_mm"] for x in daily]),
              "et0_mm": _sum([x["et0_mm"] for x in daily]), "temp_max_mean_c": _mean([x["temp_max_c"] for x in daily]),
              "temp_min_mean_c": _mean([x["temp_min_c"] for x in daily])}
    return {"daily": daily, "totals": totals, "grid_latitude": _num(doc.get("latitude")), "grid_longitude": _num(doc.get("longitude"))}


class OpenMeteoWeather:
    provider, label = "open-meteo", "Open-Meteo historical weather (ERA5 reanalysis, daily)"

    def __init__(self, url: str, timeout: int) -> None:
        self.url, self.timeout = url, timeout

    def fetch(self, req: FetchRequest) -> Fetched:
        assert req.period_start is not None and req.period_end is not None
        params = {"latitude": f"{req.latitude:.5f}", "longitude": f"{req.longitude:.5f}", "start_date": req.period_start.isoformat(),
                  "end_date": req.period_end.isoformat(), "daily": ",".join(WEATHER_DAILY), "timezone": "UTC"}
        body = _http(f"{self.url}?{urllib.parse.urlencode(params)}", timeout=self.timeout)
        return Fetched(self.provider, "ERA5 reanalysis (daily)", parse_open_meteo(_json(body)), {"url": self.url, **params}, _sha(body))


# ---------------------------------------------------------------- soil: ISRIC SoilGrids 2.0
SOIL_PROPERTIES = {"soc": "Soil organic carbon", "phh2o": "pH (water)", "clay": "Clay", "sand": "Sand", "silt": "Silt",
                   "bdod": "Bulk density", "nitrogen": "Total nitrogen", "cec": "Cation exchange capacity"}
SOIL_DEPTHS = ("0-5cm", "5-15cm", "15-30cm")


def parse_soilgrids(doc: dict[str, Any]) -> dict[str, Any]:
    layers = []
    for layer in (doc.get("properties") or {}).get("layers") or []:
        name = layer.get("name")
        if name not in SOIL_PROPERTIES:
            continue
        um = layer.get("unit_measure") or {}
        factor = _num(um.get("d_factor")) or 1.0
        unit = um.get("target_units") or um.get("mapped_units") or ""
        for d in layer.get("depths") or []:
            raw = _num((d.get("values") or {}).get("mean"))
            layers.append({"property": name, "label": SOIL_PROPERTIES[name], "depth": d.get("label"),
                           "value": round(raw / factor, 3) if raw is not None else None, "unit": "" if unit == "-" else unit})
    order = {p: i for i, p in enumerate(SOIL_PROPERTIES)}
    layers.sort(key=lambda x: (order[x["property"]], SOIL_DEPTHS.index(x["depth"]) if x["depth"] in SOIL_DEPTHS else 99))
    return {"layers": layers, "note": "Modelled 250 m estimates (mean), not a measurement of this farm."}


class SoilGrids:
    provider, label = "soilgrids", "ISRIC SoilGrids 2.0 (modelled soil properties, 250 m)"

    def __init__(self, url: str, timeout: int) -> None:
        self.url, self.timeout = url, timeout

    def fetch(self, req: FetchRequest) -> Fetched:
        params: list[tuple[str, str]] = [("lon", f"{req.longitude:.5f}"), ("lat", f"{req.latitude:.5f}")]
        params += [("property", p) for p in SOIL_PROPERTIES] + [("depth", d) for d in SOIL_DEPTHS] + [("value", "mean")]
        body = _http(f"{self.url}?{urllib.parse.urlencode(params)}", timeout=self.timeout)
        summary = parse_soilgrids(_json(body))
        if not any(x["value"] is not None for x in summary["layers"]):
            raise ProviderUnavailable("SoilGrids has no soil estimate for this location (water, urban or outside coverage)")
        return Fetched(self.provider, "SoilGrids 2.0 (mean, 0-30 cm)", summary,
                       {"url": self.url, "lon": params[0][1], "lat": params[1][1], "properties": list(SOIL_PROPERTIES),
                        "depths": list(SOIL_DEPTHS)}, _sha(body))


# ---------------------------------------------------------------- satellite: Sentinel-2 NDVI (Copernicus Data Space, Statistical API)
NDVI_EVALSCRIPT = """//VERSION=3
function setup() {
  return { input: [{ bands: ["B04", "B08", "SCL", "dataMask"] }],
           output: [{ id: "ndvi", bands: 1, sampleType: "FLOAT32" }, { id: "dataMask", bands: 1 }] };
}
function evaluatePixel(s) {
  // scene classification: 3 cloud shadow, 8/9 cloud, 10 cirrus, 11 snow — excluded
  var clear = s.SCL != 3 && s.SCL != 8 && s.SCL != 9 && s.SCL != 10 && s.SCL != 11;
  var sum = s.B08 + s.B04;
  return { ndvi: [sum == 0 ? 0 : (s.B08 - s.B04) / sum], dataMask: [s.dataMask && clear && sum != 0 ? 1 : 0] };
}"""


def parse_sentinel_statistics(doc: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for row in doc.get("data") or []:
        iv = row.get("interval") or {}
        stats = (((row.get("outputs") or {}).get("ndvi") or {}).get("bands") or {}).get("B0", {}).get("stats") or {}
        sample, nodata = _num(stats.get("sampleCount")), _num(stats.get("noDataCount"))
        valid = sample is not None and nodata is not None and sample > nodata

        def r(key: str, stats: dict[str, Any] = stats, valid: bool = valid) -> float | None:
            v = _num(stats.get(key))
            return round(v, 4) if valid and v is not None else None    # an interval with no clear pixel has no statistics
        out.append({"from": str(iv.get("from", ""))[:10], "to": str(iv.get("to", ""))[:10], "mean": r("mean"), "min": r("min"),
                    "max": r("max"), "stdev": r("stDev"), "sample_count": int(sample or 0), "no_data_count": int(nodata or 0)})
    return out


class CopernicusNdvi:
    provider, label = "copernicus", "Sentinel-2 L2A NDVI (Copernicus Data Space, 10-day, cloud-masked)"

    def __init__(self, token_url: str, statistics_url: str, client_id: str, client_secret: str, max_cloud_pct: int, timeout: int) -> None:
        self.token_url, self.statistics_url, self.timeout = token_url, statistics_url, timeout
        self._client_id, self._client_secret, self.max_cloud = client_id, client_secret, max_cloud_pct

    def _token(self) -> str:
        form = urllib.parse.urlencode({"grant_type": "client_credentials", "client_id": self._client_id,
                                       "client_secret": self._client_secret}).encode()
        tok = _json(_http(self.token_url, data=form, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=self.timeout))
        if not isinstance(tok, dict) or not tok.get("access_token"):
            raise ProviderUnavailable("Copernicus refused the client credentials")
        return str(tok["access_token"])

    def fetch(self, req: FetchRequest) -> Fetched:
        assert req.geometry is not None and req.period_start is not None and req.period_end is not None
        payload = {
            "input": {"bounds": {"geometry": req.geometry, "properties": {"crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"}},
                      "data": [{"type": "sentinel-2-l2a", "dataFilter": {"maxCloudCoverage": self.max_cloud}}]},
            "aggregation": {"timeRange": {"from": f"{req.period_start.isoformat()}T00:00:00Z", "to": f"{req.period_end.isoformat()}T23:59:59Z"},
                            "aggregationInterval": {"of": "P10D"}, "evalscript": NDVI_EVALSCRIPT, "resx": 0.0001, "resy": 0.0001},
            "calculations": {"default": {}},
        }
        body = _http(self.statistics_url, data=json.dumps(payload).encode(), timeout=self.timeout,
                     headers={"Content-Type": "application/json", "Authorization": f"Bearer {self._token()}"})
        intervals = parse_sentinel_statistics(_json(body))
        request = {"url": self.statistics_url, "collection": "sentinel-2-l2a", "interval": "P10D", "max_cloud_pct": self.max_cloud,
                   "resolution_deg": 0.0001, "from": req.period_start.isoformat(), "to": req.period_end.isoformat(),
                   "geometry_sha256": _sha(json.dumps(req.geometry, sort_keys=True).encode())}
        return Fetched(self.provider, "Sentinel-2 L2A NDVI (10-day mean)", {"intervals": intervals, "max_cloud_pct": self.max_cloud},
                       request, _sha(body))


# ---------------------------------------------------------------- land records: no public API
class NoLandRecords:
    provider, label = "manual", "Land records (no public API — upload documents)"

    def fetch(self, req: FetchRequest) -> Fetched:
        raise ProviderNotConfigured("There is no public land-records API: upload the land record (7/12 extract, title) as a document.")
