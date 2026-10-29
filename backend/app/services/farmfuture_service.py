"""FarmFuture boundary import — find a farm owner's FarmFuture estates, farms and mapped areas by mobile number.

Read-only towards the platform: nothing here saves a boundary. The chosen area is returned to the boundary editor, which validates it
with SQL Server and saves it as a new boundary version (source IMPORT) through farm_service.save_boundary, so overlap checks, audit
and GIS review apply unchanged. Needs farms.manage on the farm (a farmer may only use their own registered phone numbers).
"""
import re
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import record
from app.core.config import get_settings
from app.core.context import RequestContext
from app.core.errors import Conflict, NotFound, PermissionDenied, ServiceUnavailable, ValidationFailed
from app.integrations import farmfuture
from app.integrations.geodata import ProviderUnavailable
from app.models import Farm, FarmerContact
from app.repositories import gis
from app.rules.geometry_io import GeometryError, parse_geojson, wkt_to_geojson
from app.schemas.farms import FarmFutureAreasOut, FarmFutureEstatesOut
from app.security.permissions import P
from app.security.principal import Principal
from app.services import farm_service


def client_for() -> farmfuture.FarmFutureClient | None:
    """The configured client, or None when switched off. Tests replace this function; runtime never simulates."""
    s = get_settings()
    if s.FARMFUTURE_PROVIDER != "farmfuture":
        return None
    return farmfuture.FarmFutureClient(s.FARMFUTURE_API_URL, s.EXTERNAL_DATA_TIMEOUT_SECONDS)


_client: Callable[[], farmfuture.FarmFutureClient | None] = client_for


def normalise_phone(raw: str, country_code: str) -> str:
    """E.164 (+<country><number>) as FarmFuture expects it. A bare 10-digit number (or 0 + 10 digits) gets the default country code."""
    digits = re.sub(r"\D", "", raw)
    if raw.strip().startswith("+"):
        phone = "+" + digits
    elif raw.strip().startswith("00"):
        phone = "+" + digits[2:]
    elif len(digits) == 10:
        phone = country_code + digits
    elif len(digits) == 11 and digits.startswith("0"):
        phone = country_code + digits[1:]
    else:
        phone = "+" + digits
    if not re.fullmatch(r"\+[1-9][0-9]{7,14}", phone):
        raise ValidationFailed("Enter the mobile number with its country code, e.g. +91 98765 43210.", error_code="INVALID_PHONE")
    return phone


def mask(phone: str) -> str:
    return phone[:3] + "*" * max(len(phone) - 6, 0) + phone[-3:]


def _farmer_phones(db: Session, farm: Farm, cc: str) -> list[str]:
    """Active phone contacts of the farm's farmer, primary phone first."""
    rows = db.scalars(select(FarmerContact).where(FarmerContact.farmer_id == farm.farmer_id, FarmerContact.is_active == True,  # noqa: E712
                                                  FarmerContact.contact_type.in_(("PHONE", "ALTERNATE_PHONE")))).all()
    rows = sorted(rows, key=lambda c: (not c.is_primary, c.contact_type != "PHONE", c.created_at))
    out = []
    for c in rows:
        try:
            out.append(normalise_phone(c.value, cc))
        except ValidationFailed:
            continue
    return out


def _resolve(db: Session, principal: Principal, farm_id: uuid.UUID, entered: str | None) -> tuple[Farm, str, str]:
    """(farm, E.164 phone, ENTERED | FARMER_PRIMARY_PHONE). Only a phone on file for the farm's farmer is looked up — by staff and the
    farmer alike: FarmFuture returns a person's estates and boundaries, so an arbitrary number would expose a stranger's land. A new
    number is first recorded as the farmer's contact (audited), then used here."""
    farm = farm_service.get_farm(db, principal, farm_id, P.FARMS_MANAGE)
    cc = get_settings().FARMFUTURE_DEFAULT_COUNTRY_CODE
    own = _farmer_phones(db, farm, cc)
    if not entered:
        if not own:
            raise ValidationFailed("The farmer has no phone number on file: enter the FarmFuture mobile number.", error_code="PHONE_REQUIRED")
        return farm, own[0], "FARMER_PRIMARY_PHONE"
    phone = normalise_phone(entered, cc)
    if phone not in own:
        raise PermissionDenied("Only a phone number on file for this farm's farmer can be looked up. Add the number to the farmer's "
                               "contacts first.", error_code="PHONE_NOT_OWN")
    return farm, phone, "ENTERED"


def _client_or_conflict() -> farmfuture.FarmFutureClient:
    c = _client()
    if c is None:
        raise Conflict("FarmFuture import is switched off (FARMFUTURE_PROVIDER=none).", error_code="PROVIDER_NOT_CONFIGURED")
    return c


def _unavailable(e: Exception) -> ServiceUnavailable:
    return ServiceUnavailable(f"FarmFuture: {e}. Try again later.", error_code="EXTERNAL_PROVIDER_UNAVAILABLE")


def _estates(client: farmfuture.FarmFutureClient, phone: str) -> list[dict[str, Any]]:
    try:
        return client.estates(phone)
    except farmfuture.FarmFutureUserNotFound as e:
        raise NotFound(str(e), error_code="FARMFUTURE_USER_NOT_FOUND") from None
    except ProviderUnavailable as e:
        raise _unavailable(e) from None


def estates(db: Session, ctx: RequestContext, principal: Principal, farm_id: uuid.UUID, entered: str | None) -> FarmFutureEstatesOut:
    farm, phone, source = _resolve(db, principal, farm_id, entered)
    found = _estates(_client_or_conflict(), phone)
    record(db, ctx, "FARMFUTURE_LOOKUP", "farm", farm.id, None,
           {"phone": mask(phone), "phone_source": source, "estates": len(found), "farms": sum(len(e["farms"]) for e in found)},
           None, organization_id=farm.organization_id)
    db.commit()
    return FarmFutureEstatesOut(phone_masked=mask(phone), phone_source=source, estates=found)  # type: ignore[arg-type]


def _combined(db: Session, zones: list[dict[str, Any]]) -> dict[str, Any] | None:
    """All zones dissolved into one shape by SQL Server (adjacent zones share edges, which a MultiPolygon may not)."""
    if len(zones) < 2:
        return None
    try:
        wkts = [parse_geojson(z["geojson"]).to_wkt() for z in zones]
    except GeometryError:
        return None
    wkt = gis.union_polygons(db, wkts)
    return wkt_to_geojson(wkt) if wkt else None


def areas(db: Session, ctx: RequestContext, principal: Principal, farm_id: uuid.UUID, ff_farm_id: uuid.UUID,
          entered: str | None) -> FarmFutureAreasOut:
    farm, phone, _ = _resolve(db, principal, farm_id, entered)
    client = _client_or_conflict()
    # FarmFuture does not tie a farm's coordinates to the caller, so only farms listed for this number are served.
    if not any(f["farm_id"] == str(ff_farm_id) for e in _estates(client, phone) for f in e["farms"]):
        raise NotFound("This FarmFuture farm is not linked to the mobile number.", error_code="FARMFUTURE_FARM_NOT_FOUND")
    try:
        got = client.farm_coordinates(phone, str(ff_farm_id))
    except farmfuture.FarmFutureUserNotFound as e:
        raise NotFound(str(e), error_code="FARMFUTURE_USER_NOT_FOUND") from None
    except ProviderUnavailable as e:
        raise _unavailable(e) from None
    combined = _combined(db, got["zones"])
    record(db, ctx, "FARMFUTURE_AREAS_FETCHED", "farm", farm.id, None,
           {"phone": mask(phone), "farmfuture_farm_id": str(ff_farm_id), "zones": len(got["zones"]), "devices": len(got["devices"])},
           None, organization_id=farm.organization_id)
    db.commit()
    return FarmFutureAreasOut(farm_id=ff_farm_id, zones=got["zones"], combined_geojson=combined, devices=got["devices"])  # type: ignore[arg-type]
