"""FarmFuture (api.farmfuture.io) — estates, farms and mapped farm areas of a FarmFuture user, found by mobile number.

Three calls, in order:
  POST /controller/ValidateMobileNumber          {"phoneNumber": "+91…"}  -> data.token (JWT, ~7 days)
  GET  /Estate/GetUserEstatesAndFarmsList        Bearer token            -> estates, each with its farms and crops
  GET  /Data/GetFarmCoordinates/{farmId}         Bearer token            -> mapped areas (WKT polygons) and sensor locations

The result is a CANDIDATE only: an imported area becomes a farm boundary solely through the normal boundary flow (SQL Server
validation, a new boundary version with source IMPORT, overlap checks, GIS review). Tokens are cached in this process only, keyed
by phone number, and never leave the backend. Nothing is simulated at runtime: an unreachable service raises ProviderUnavailable.
"""
import base64
import json
import ssl
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, ClassVar

from app.integrations.geodata import ProviderUnavailable
from app.rules.geometry_io import GeometryError, wkt_to_geojson

_MAX_RESPONSE_BYTES = 5 * 1024 * 1024
_TOKEN_MARGIN_SECONDS = 300                       # re-validate the number this long before the token expires


class FarmFutureUserNotFound(RuntimeError):
    pass


@dataclass(frozen=True)
class _Response:
    status: int
    body: bytes


def _request(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None, token: str | None = None,
             timeout: int) -> _Response:
    """HTTPS only, certificate-verified, bounded response size. 401 is returned (not raised) so an expired token can be renewed."""
    if not url.startswith("https://"):
        raise ProviderUnavailable("FarmFuture is reached over HTTPS only")
    headers = {"Accept": "application/json", "User-Agent": "carbon-platform/1.0"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)  # noqa: S310 (https enforced)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as r:  # noqa: S310
            body = r.read(_MAX_RESPONSE_BYTES + 1)
            status = r.status
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return _Response(e.code, b"")
        raise ProviderUnavailable(f"FarmFuture answered HTTP {e.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ProviderUnavailable(f"FarmFuture could not be reached ({type(e).__name__})") from None
    if len(body) > _MAX_RESPONSE_BYTES:
        raise ProviderUnavailable("FarmFuture's response is too large")
    return _Response(status, body)


def _data(body: bytes) -> Any:
    """FarmFuture wraps every answer as {"succeeded": bool, "data": …}."""
    try:
        doc = json.loads(body)
    except ValueError:
        raise ProviderUnavailable("FarmFuture's response is not valid JSON") from None
    if not isinstance(doc, dict) or doc.get("succeeded") is not True:
        raise ProviderUnavailable("FarmFuture reported the request as unsuccessful")
    return doc.get("data")


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _str(v: Any) -> str:
    return v.strip() if isinstance(v, str) else ""


def token_expiry(token: str) -> float:
    """`exp` of the JWT (unverified — only used to decide when to ask FarmFuture for a new one). 0 when unreadable."""
    try:
        part = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
        return float(claims.get("exp") or 0)
    except (IndexError, ValueError, TypeError, AttributeError):
        return 0.0


# ---------------------------------------------------------------- parsing (canonical shapes)
def parse_token(data: Any) -> str:
    token = data.get("token") if isinstance(data, dict) else None
    if not isinstance(token, str) or not token:
        raise FarmFutureUserNotFound("FarmFuture has no user with this mobile number.")
    return token


def parse_estates(data: Any) -> list[dict[str, Any]]:
    estates = []
    for e in data if isinstance(data, list) else []:
        farms = [{"farm_id": _str(f.get("farmId")), "name": _str(f.get("farmName")), "postal_code": _str(f.get("postalCode")) or None,
                  "crops": [_str(c.get("name")) for c in f.get("crops") or [] if isinstance(c, dict) and _str(c.get("name"))],
                  "plants_per_hectare": _num(f.get("plantsPerHectare")), "is_owner_estate": bool(f.get("isOwnerEstate")),
                  "active_subscription": bool(f.get("isActiveSubscription"))}
                 for f in e.get("farms") or [] if isinstance(f, dict) and _str(f.get("farmId"))]
        estates.append({"estate_id": _str(e.get("estateId")), "name": _str(e.get("estateName")),
                        "postal_code": _str(e.get("zipCode")) or None, "is_fpo": bool(e.get("isFpo")), "farms": farms})
    return estates


def _zone_geometry(area: dict[str, Any], coordinates: list[Any]) -> dict[str, Any] | None:
    """The zone's WKT polygon; failing that, its numbered corner points (closed into a ring)."""
    wkt = _str(area.get("polygon"))
    if wkt:
        try:
            geo = wkt_to_geojson(wkt)
            if geo["coordinates"]:
                return geo
        except GeometryError:
            pass
    pts = sorted((c for c in coordinates if isinstance(c, dict) and _num(c.get("lat")) is not None and _num(c.get("long")) is not None),
                 key=lambda c: _num(c.get("number")) or 0)
    ring = [[_num(c["long"]), _num(c["lat"])] for c in pts]
    if len(ring) < 3:
        return None
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def parse_coordinates(data: Any) -> dict[str, Any]:
    data = data if isinstance(data, dict) else {}
    zones = []
    for z in data.get("farmCoordinates") or []:
        area = z.get("area") if isinstance(z, dict) else None
        if not isinstance(area, dict):
            continue
        coordinates = z.get("coordinates") or []
        geo = _zone_geometry(area, coordinates)
        if geo is None:
            continue
        alts = [a for a in (_num(c.get("alt")) for c in coordinates if isinstance(c, dict)) if a]   # 0 = not recorded
        zones.append({"zone_id": _str(area.get("id")), "name": _str(area.get("areaName")) or "Unnamed area",
                      "is_main": bool(area.get("mainMapType")), "geojson": geo, "vertex_count": max(len(geo["coordinates"][0]) - 1, 0),
                      "mean_altitude_m": round(sum(alts) / len(alts), 1) if alts else None})
    devices = [{"name": _str(d.get("deviceName")) or "Device", "lat": _num(d.get("lat")), "lon": _num(d.get("long")),
                "device_type": _num(d.get("deviceType"))}
               for d in data.get("deviceCoordinates") or []
               if isinstance(d, dict) and _num(d.get("lat")) is not None and _num(d.get("long")) is not None]
    return {"zones": zones, "devices": devices}


# ---------------------------------------------------------------- client
class FarmFutureClient:
    provider, label = "farmfuture", "FarmFuture (estates, farms and mapped farm areas)"

    _tokens: ClassVar[dict[str, tuple[str, float]]] = {}    # phone -> (token, exp); process-local, shared by every client instance
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self, base_url: str, timeout: int) -> None:
        self.base_url, self.timeout = base_url.rstrip("/"), timeout

    def _login(self, phone: str) -> str:
        r = _request(f"{self.base_url}/controller/ValidateMobileNumber", method="POST", payload={"phoneNumber": phone},
                     timeout=self.timeout)
        if r.status in (401, 403):
            raise FarmFutureUserNotFound("FarmFuture refused this mobile number.")
        token = parse_token(_data(r.body))
        with self._lock:
            self._tokens[phone] = (token, token_expiry(token))
        return token

    def _token(self, phone: str) -> str:
        with self._lock:
            cached = self._tokens.get(phone)
        if cached and cached[1] - _TOKEN_MARGIN_SECONDS > time.time():
            return cached[0]
        return self._login(phone)

    def _get(self, phone: str, path: str) -> Any:
        r = _request(f"{self.base_url}{path}", token=self._token(phone), timeout=self.timeout)
        if r.status in (401, 403):                # token revoked or expired early: validate the number once more
            r = _request(f"{self.base_url}{path}", token=self._login(phone), timeout=self.timeout)
            if r.status in (401, 403):
                raise ProviderUnavailable("FarmFuture refused the session token")
        return _data(r.body)

    def estates(self, phone: str) -> list[dict[str, Any]]:
        return parse_estates(self._get(phone, "/Estate/GetUserEstatesAndFarmsList"))

    def farm_coordinates(self, phone: str, farm_id: str) -> dict[str, Any]:
        return parse_coordinates(self._get(phone, f"/Data/GetFarmCoordinates/{farm_id}"))

    @classmethod
    def forget_tokens(cls) -> None:
        with cls._lock:
            cls._tokens.clear()
