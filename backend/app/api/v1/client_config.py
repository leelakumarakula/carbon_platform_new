"""Client configuration served to the signed-in SPA (decision D6: the basemap tile source is configuration)."""
from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import ActivePrincipal
from app.core.config import get_settings

router = APIRouter(prefix="/config", tags=["config"])


class TerrainConfigOut(BaseModel):
    tile_url: str
    encoding: str
    max_zoom: int
    attribution: str


class MapConfigOut(BaseModel):
    provider: str
    tile_url: str
    attribution: str
    max_zoom: int
    subdomains: list[str]
    terrain: TerrainConfigOut | None = None   # 3D view elevation tiles; None = 3D without relief


class ClientConfigOut(BaseModel):
    map: MapConfigOut


@router.get("/client", response_model=ClientConfigOut, summary="Non-secret client configuration (basemap and terrain tiles)")
def client_config(_: ActivePrincipal) -> ClientConfigOut:
    s = get_settings()
    terrain = TerrainConfigOut(tile_url=s.MAP_TERRAIN_URL, encoding=s.MAP_TERRAIN_ENCODING, max_zoom=s.MAP_TERRAIN_MAX_ZOOM,
                               attribution=s.MAP_TERRAIN_ATTRIBUTION) if s.MAP_TERRAIN_URL.strip() else None
    return ClientConfigOut(map=MapConfigOut(provider=s.MAP_TILE_PROVIDER, tile_url=s.MAP_TILE_URL, attribution=s.MAP_TILE_ATTRIBUTION,
                                            max_zoom=s.MAP_TILE_MAX_ZOOM,
                                            subdomains=[x.strip() for x in s.MAP_TILE_SUBDOMAINS.split(",") if x.strip()],
                                            terrain=terrain))
