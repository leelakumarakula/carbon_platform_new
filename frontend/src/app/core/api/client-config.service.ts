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
}

export interface ClientConfig {
  map: MapConfig;
}

/** Development fallback used only if the config endpoint cannot be reached (OpenStreetMap public tiles: dev use only). */
export const FALLBACK_MAP: MapConfig = {
  provider: 'osm-dev',
  tile_url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  max_zoom: 19,
  subdomains: [],
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
