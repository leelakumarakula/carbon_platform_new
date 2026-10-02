"""Client configuration served to the signed-in SPA (decision D6: the basemap tile source is configuration)."""
from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import ActivePrincipal
from app.core.config import get_settings

router = APIRouter(prefix="/config", tags=["config"])


class MapConfigOut(BaseModel):
    provider: str
    tile_url: str
    attribution: str
    max_zoom: int
    subdomains: list[str]


class ClientConfigOut(BaseModel):
    map: MapConfigOut


@router.get("/client", response_model=ClientConfigOut, summary="Non-secret client configuration (basemap tiles)")
def client_config(_: ActivePrincipal) -> ClientConfigOut:
    s = get_settings()
    return ClientConfigOut(map=MapConfigOut(provider=s.MAP_TILE_PROVIDER, tile_url=s.MAP_TILE_URL, attribution=s.MAP_TILE_ATTRIBUTION,
                                            max_zoom=s.MAP_TILE_MAX_ZOOM,
                                            subdomains=[x.strip() for x in s.MAP_TILE_SUBDOMAINS.split(",") if x.strip()]))
