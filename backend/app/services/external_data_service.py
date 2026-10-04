"""External farm reference data (weather, soil, satellite NDVI, land records) — fetched on request, stored append-only, evidence only.

Nothing here is called by a workflow: a farm's status, verification, eligibility, MRV or calculation never reads these rows. A fetch
needs farms.manage or farms.review in the farm's organization and a saved boundary (the centroid / polygon of its current version).
The provider is called before anything is written, so an outage leaves the database untouched.
"""
import json
import uuid
from collections.abc import Callable
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import record
from app.core.config import get_settings
from app.core.context import RequestContext
from app.core.errors import Conflict, ServiceUnavailable, ValidationFailed
from app.integrations import geodata
from app.models import Farm, FarmBoundary, FarmExternalObservation, User
from app.models.base import utcnow
from app.schemas.farms import ExternalDataOut, ExternalObservationOut, ExternalProviderOut
from app.security.permissions import P
from app.security.principal import Principal
from app.services import farm_service

KINDS = {"weather": "WEATHER", "soil": "SOIL", "satellite-ndvi": "SATELLITE_NDVI", "land-records": "LAND_RECORD"}
_PERIOD = {"WEATHER": date(1950, 1, 1), "SATELLITE_NDVI": date(2017, 3, 28)}   # earliest data: ERA5 / Sentinel-2 L2A global archive
MAX_PERIOD_DAYS = 731
REFETCH_SECONDS = 60                                                 # the free public services are not hammered by repeated clicks


def adapter_for(data_type: str) -> tuple[geodata.GeoDataAdapter | None, str, str, str | None]:
    """(adapter or None when disabled, provider code, label, note). Tests replace this function; runtime never simulates."""
    s = get_settings()
    timeout = s.EXTERNAL_DATA_TIMEOUT_SECONDS
    if data_type == "WEATHER":
        a = geodata.OpenMeteoWeather(s.OPEN_METEO_ARCHIVE_URL, timeout)
        return (a, a.provider, a.label, None) if s.WEATHER_PROVIDER == "open-meteo" else \
            (None, "none", a.label, "Weather data is switched off (WEATHER_PROVIDER=none).")
    if data_type == "SOIL":
        b = geodata.SoilGrids(s.SOILGRIDS_URL, timeout)
        return (b, b.provider, b.label, "Modelled regional estimates — not a laboratory measurement.") if s.SOIL_PROVIDER == "soilgrids" else \
            (None, "none", b.label, "Soil data is switched off (SOIL_PROVIDER=none).")
    if data_type == "SATELLITE_NDVI":
        label = geodata.CopernicusNdvi.label
        if s.SATELLITE_PROVIDER == "copernicus" and s.COPERNICUS_CLIENT_ID and s.COPERNICUS_CLIENT_SECRET:
            return (geodata.CopernicusNdvi(s.COPERNICUS_TOKEN_URL, s.COPERNICUS_STATISTICS_URL, s.COPERNICUS_CLIENT_ID,
                                           s.COPERNICUS_CLIENT_SECRET, s.SATELLITE_MAX_CLOUD_PCT, timeout), "copernicus", label, None)
        return None, "manual", label, "Configure SATELLITE_PROVIDER=copernicus with a free Copernicus Data Space OAuth client to enable."
    return None, "manual", geodata.NoLandRecords.label, ("No public land-records API exists: upload the land record (e.g. 7/12 extract) "
                                                         "in the Documents tab.")


_resolve: Callable[[str], tuple[geodata.GeoDataAdapter | None, str, str, str | None]] = adapter_for


def can_fetch(principal: Principal, farm: Farm) -> bool:
    return principal.can_in_org(P.FARMS_MANAGE, farm.organization_id) or principal.can_in_org(P.FARMS_REVIEW, farm.organization_id)


def _out(o: FarmExternalObservation, names: dict[uuid.UUID, str], versions: dict[uuid.UUID, int]) -> ExternalObservationOut:
    return ExternalObservationOut(id=o.id, data_type=o.data_type, provider=o.provider, dataset=o.dataset,  # type: ignore[arg-type]
                                  period_start=o.period_start, period_end=o.period_end, latitude=float(o.latitude),
                                  longitude=float(o.longitude), boundary_version=versions.get(o.boundary_id) if o.boundary_id else None,
                                  summary=json.loads(o.summary), sha256=o.raw_sha256, fetched_at=o.fetched_at,
                                  fetched_by_name=names.get(o.fetched_by), environment=o.environment)


def _outs(db: Session, rows: list[FarmExternalObservation]) -> list[ExternalObservationOut]:
    users = {o.fetched_by for o in rows}
    bids = {o.boundary_id for o in rows if o.boundary_id}
    names = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_(users)))} if users else {}
    versions = {b.id: b.version for b in db.scalars(select(FarmBoundary).where(FarmBoundary.id.in_(bids)))} if bids else {}
    return [_out(o, names, versions) for o in rows]


def overview(db: Session, principal: Principal, farm_id: uuid.UUID) -> ExternalDataOut:
    farm = farm_service.get_farm(db, principal, farm_id)
    providers = []
    for dt in geodata.DATA_TYPES:
        adapter, provider, label, note = _resolve(dt)
        providers.append(ExternalProviderOut(data_type=dt, provider=provider, label=label, enabled=adapter is not None, note=note))  # type: ignore[arg-type]
    rows = list(db.scalars(select(FarmExternalObservation).where(FarmExternalObservation.farm_id == farm.id)
                           .order_by(FarmExternalObservation.fetched_at.desc())).all())
    return ExternalDataOut(can_fetch=can_fetch(principal, farm), has_boundary=farm.current_boundary_id is not None,
                           providers=providers, observations=_outs(db, rows))


def _period(data_type: str, start: date | None, end: date | None) -> tuple[date | None, date | None]:
    if data_type not in _PERIOD:
        return None, None                                            # soil / land records are not time series
    if start is None or end is None:
        raise ValidationFailed("Choose the period (start and end dates).", error_code="INVALID_PERIOD")
    today = date.today()
    if start > end or end > today or start < _PERIOD[data_type] or (end - start).days >= MAX_PERIOD_DAYS:
        raise ValidationFailed(f"The period must run forwards, end by today, start on or after {_PERIOD[data_type].isoformat()} and "
                               f"span at most {MAX_PERIOD_DAYS} days.", error_code="INVALID_PERIOD")
    return start, end


def fetch(db: Session, ctx: RequestContext, principal: Principal, farm_id: uuid.UUID, kind: str, start: date | None,
          end: date | None) -> ExternalObservationOut:
    farm = farm_service.get_farm(db, principal, farm_id)
    if not can_fetch(principal, farm):
        principal.require_in_org(P.FARMS_MANAGE, farm.organization_id)  # raises the standard permission error
    data_type = KINDS[kind]
    adapter, _, label, note = _resolve(data_type)
    if adapter is None:
        raise Conflict(note or f"{label} is not configured.", error_code="PROVIDER_NOT_CONFIGURED")
    b = db.get(FarmBoundary, farm.current_boundary_id) if farm.current_boundary_id else None
    if b is None or b.centroid_lat is None or b.centroid_lon is None:
        raise Conflict("Save the farm boundary first: external data is fetched for its location.", error_code="NO_BOUNDARY")
    period_start, period_end = _period(data_type, start, end)
    last = db.scalars(select(FarmExternalObservation.fetched_at).where(FarmExternalObservation.farm_id == farm.id,
                                                                       FarmExternalObservation.data_type == data_type)
                      .order_by(FarmExternalObservation.fetched_at.desc())).first()
    if last is not None and last > utcnow() - timedelta(seconds=REFETCH_SECONDS):
        raise Conflict("This data was fetched a moment ago; wait a minute before fetching again.", error_code="FETCHED_RECENTLY")
    req = geodata.FetchRequest(latitude=float(b.centroid_lat), longitude=float(b.centroid_lon),
                               geometry=farm_service.boundary_out_geojson(b) if data_type == "SATELLITE_NDVI" else None,
                               period_start=period_start, period_end=period_end)
    try:
        got = adapter.fetch(req)                                     # outside any write: an outage leaves nothing behind
    except geodata.ProviderNotConfigured as e:
        raise Conflict(str(e), error_code="PROVIDER_NOT_CONFIGURED") from None
    except geodata.ProviderUnavailable as e:
        raise ServiceUnavailable(f"{label}: {e}. Try again later.", error_code="EXTERNAL_PROVIDER_UNAVAILABLE") from None
    o = FarmExternalObservation(farm_id=farm.id, boundary_id=b.id, organization_id=farm.organization_id, environment=farm.environment,
                                data_type=data_type, provider=got.provider, dataset=got.dataset[:120], period_start=period_start,
                                period_end=period_end, latitude=b.centroid_lat, longitude=b.centroid_lon,
                                request=json.dumps(got.request, sort_keys=True, default=str),
                                summary=json.dumps(got.summary, sort_keys=True, default=str), raw_sha256=got.raw_sha256,
                                fetched_by=principal.user_id)
    db.add(o)
    db.flush()
    record(db, ctx, "FARM_EXTERNAL_DATA_FETCHED", "farm", farm.id, None,
           {"observation_id": o.id, "data_type": data_type, "provider": got.provider, "dataset": got.dataset, "boundary_version": b.version,
            "period_start": period_start, "period_end": period_end, "raw_sha256": got.raw_sha256}, None,
           organization_id=farm.organization_id)
    db.commit()
    return _outs(db, [o])[0]
