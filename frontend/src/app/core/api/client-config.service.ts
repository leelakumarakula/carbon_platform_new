import { Injectable, inject } from '@angular/core';
import { Observable, catchError, of, shareReplay } from 'rxjs';

import { ApiService } from './api.service';

/** Basemap tile source (decision D6). Configured on the server (MAP_TILE_* settings), never chosen in code. */
export interface MapConfig {
  provider: string;
  tile_url: string;
  attribution: string;
  max_zoom: number;
  subdomains: string[];
  /** Elevation tiles for the 3D view (MAP_TERRAIN_* settings); absent = 3D without relief. */
  terrain?: TerrainConfig | null;
  /** Imagery draped on the 3D view (MAP_SATELLITE_* settings); absent = street map only. */
  satellite?: SatelliteConfig | null;
}

export interface SatelliteConfig {
  tile_url: string;
  max_zoom: number;
  attribution: string;
}

export interface TerrainConfig {
  tile_url: string;
  encoding: 'terrarium' | 'mapbox';
  max_zoom: number;
  attribution: string;
}

export interface ClientConfig {
  map: MapConfig;
}

/**
 * Development fallback used only if the config endpoint cannot be reached (OpenStreetMap public tiles and Esri World Imagery:
 * dev use only), so the 3D view still opens on satellite imagery.
 */
export const FALLBACK_MAP: MapConfig = {
  provider: 'osm-dev',
  tile_url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  max_zoom: 19,
  subdomains: [],
  satellite: {
    tile_url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    max_zoom: 18,
    attribution: 'Imagery &copy; Esri, Maxar, Earthstar Geographics, and the GIS User Community',
  },
};

@Injectable({ providedIn: 'root' })
export class ClientConfigService {
  private readonly api = inject(ApiService);
  private cached?: Observable<ClientConfig>;

  config(): Observable<ClientConfig> {
    this.cached ??= this.api.get<ClientConfig>('/config/client').pipe(
      catchError(() => of({ map: FALLBACK_MAP })),
      shareReplay({ bufferSize: 1, refCount: false }),
    );
    return this.cached;
  }
}
