# 3D Map View: Integration Guide

This guide covers the map component used on the project screens (Stratification, Boundary, Points and others). It provides:

- a **2D / 3D** switch (2D uses Leaflet; 3D uses MapLibre GL with terrain relief),
- a **Satellite / Map** ground switch in 3D,
- a **Pause / Rotate** button that slowly orbits the camera around the data,
- polygons and points drawn on the ground in both views, with hover labels,
- automatic fallback to 2D when the browser has no WebGL or the 3D view fails to start.

The 3D view is **view-only**. Drawing and click handling happen in 2D, which stays mounted underneath the 3D view so no state is lost when switching between them.

---

## 1. Architecture

```
<app-geo-map>                      geo-map.ts: 2D (Leaflet) + the 2D/3D switch
 ├─ Leaflet map (always mounted; hidden while 3D shows)
 └─ <app-geo-map-3d>               geo-map-3d.ts: MapLibre 3D view
      ├─ base raster    ─┐ Satellite / Map switch toggles visibility
      ├─ satellite raster┘
      ├─ hillshade (raster-dem)
      ├─ terrain   (raster-dem, exaggeration 1.5)
      └─ GeoJSON overlays: shapes (fill / line / dashed), points, drawing

ClientConfigService ──GET /api/v1/config/client──► backend (tile URLs from env)
                    └─ FALLBACK_MAP if the endpoint fails
```

| Source file (this repo) | Purpose |
|---|---|
| `frontend/src/app/shared/geo-map-3d.ts` | 3D view: terrain, satellite toggle, orbit, overlays, camera fly-in |
| `frontend/src/app/shared/geo-map.ts` | Wrapper: 2D Leaflet map, 2D/3D switch, WebGL check, fallback |
| `frontend/src/app/core/api/client-config.service.ts` | `MapConfig` types, config loading and fallback |
| `frontend/src/app/shared/geo.ts` | `LonLat` type and `boundsOf()` helper |
| `frontend/src/app/farms/farm.models.ts` | `GeoGeometry` type |
| `backend/app/api/v1/client_config.py` | Optional: endpoint serving the tile URLs |
| `backend/app/core/config.py` | Optional: `MAP_*` settings |

---

## 2. Dependencies

```bash
npm i maplibre-gl@^6.12.0 leaflet@^1.9.4
npm i -D @types/leaflet@1.9
```

The code is written for Angular 21 (standalone components, signals, `input()` / `output()`). For other frameworks, see **section 7**.

---

## 3. Build setup (required)

MapLibre's web worker cannot be located by the Angular bundler, so the worker and stylesheet are copied as static assets to `/vendor/maplibre/`. **If you skip this step, the 3D map draws raster tiles but never finishes loading.** The component checks for the worker and reports a clear error if it is missing.

`angular.json` → `projects.<app>.architect.build.options`:

```json
"assets": [
  { "glob": "**/*", "input": "public" },
  {
    "glob": "{maplibre-gl-worker.mjs,maplibre-gl-shared.mjs,maplibre-gl.css}",
    "input": "node_modules/maplibre-gl/dist",
    "output": "vendor/maplibre"
  }
],
"styles": [
  "node_modules/leaflet/dist/leaflet.css",
  "src/styles.scss"
],
"allowedCommonJsDependencies": ["leaflet"]
```

**CSS variables** used by the buttons (define them in your global stylesheet or replace them):

```css
:root {
  --cp-forest: #004225;   /* button text and active-button background */
  --cp-font: 'Your Font', system-ui, sans-serif;
}
```

The components also use Angular Material system tokens (`--mat-sys-outline-variant`, `--mat-sys-on-surface-variant`, `--mat-sys-error`, `--mat-sys-body-medium`, `--mat-sys-body-small`). If you don't use Angular Material, replace them with your own colours and fonts.

---

## 4. Usage

```ts
import { GeoMap, MapLayer, MapPoint } from './shared/geo-map';

@Component({
  imports: [GeoMap],
  template: `<app-geo-map [layers]="layers" [points]="points" height="380px" />`,
})
export class MyPage {
  layers: MapLayer[] = [
    { geojson: { type: 'Polygon', coordinates: [[[73.80, 20.00], [73.81, 20.00], [73.81, 20.01], [73.80, 20.00]]] },
      color: '#2e7d32', label: 'Stratum A', fillOpacity: 0.2 },
  ];
  points: MapPoint[] = [{ lat: 20.005, lon: 73.805, label: 'Sample 1', color: '#1565c0' }];
}
```

### `<app-geo-map>` inputs and outputs

| Name | Type | Default | Notes |
|---|---|---|---|
| `layers` | `MapLayer[]` | `[]` | Polygons / MultiPolygons: `{ geojson, color, label?, dashed?, fillOpacity? }` |
| `points` | `MapPoint[]` | `[]` | `{ lat, lon, label?, color? }` |
| `drawing` | `LonLat[] \| null` | `null` | In-progress polygon vertices `[lon, lat]`; 3D shows a "view-only" hint |
| `height` | `string` | `'360px'` | |
| `center` | `[lat, lon]` | `[20.0, 73.8]` | Initial centre before the data is framed |
| `allow3d` | `boolean` | `true` | Show the 2D / 3D switch |
| `defaultMode` | `'2d' \| '3d'` | `'3d'` | Pass `'2d'` for editors where users draw or click |
| `(mapClick)` | `{ lat, lon }` | | Emitted by the 2D map only |

---

## 5. Tile configuration

The browser loads tiles directly from URL templates. In this repo the URLs come from the backend (`GET /api/v1/config/client`), so they can be changed without a rebuild. **If the endpoint isn't available, `FALLBACK_MAP` is used.** To run without a backend, return `of({ map: FALLBACK_MAP })` from `ClientConfigService.config()` and add a `terrain` block to `FALLBACK_MAP`:

```ts
terrain: {
  tile_url: 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png',
  encoding: 'terrarium',
  max_zoom: 15,
  attribution: 'Elevation: <a href="https://registry.opendata.aws/terrain-tiles/">AWS Terrain Tiles</a>',
},
```

Environment variables (`.env`):

```env
# 2D basemap and the 3D "Map" ground
MAP_TILE_PROVIDER=osm-dev
MAP_TILE_URL=https://tile.openstreetmap.org/{z}/{x}/{y}.png
MAP_TILE_ATTRIBUTION=&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors
MAP_TILE_MAX_ZOOM=19
MAP_TILE_SUBDOMAINS=
# 3D terrain (elevation). Empty = 3D without relief
MAP_TERRAIN_URL=https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png
# terrarium | mapbox
MAP_TERRAIN_ENCODING=terrarium
MAP_TERRAIN_MAX_ZOOM=15
# 3D satellite imagery. Empty = no Satellite option
MAP_SATELLITE_URL=https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}
MAP_SATELLITE_MAX_ZOOM=18
```

> **Licensing:** the defaults (public OpenStreetMap tiles, Esri World Imagery and AWS Terrain Tiles) are acceptable **for development only**. Production needs licensed or self-hosted sources, such as MapTiler, Mapbox, an ArcGIS licence or your own tile server. Keep the attribution strings.

---

## 6. Source code (Angular)

### 6.1 `shared/geo-map-3d.ts`: the 3D view

```ts
import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnDestroy,
  effect,
  inject,
  output,
  input,
  signal,
  viewChild,
} from '@angular/core';
import type { GeoJSONSource, Map as MlMap, StyleSpecification } from 'maplibre-gl';
import { firstValueFrom } from 'rxjs';

import { ClientConfigService, MapConfig } from '../core/api/client-config.service';
import { LonLat, boundsOf } from './geo';
import type { MapLayer, MapPoint } from './geo-map';

/** MapLibre's worker and stylesheet are copied to /vendor/maplibre by angular.json (the bundler cannot locate the worker itself). */
const VENDOR = 'vendor/maplibre/';
const reducedMotion = () => typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
let cssRequested = false;

function ensureCss(): void {
  if (cssRequested) return;
  cssRequested = true;
  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = new URL(`${VENDOR}maplibre-gl.css`, document.baseURI).href;
  document.head.appendChild(link);
}

/** Leaflet-style "{s}" subdomain templates become one URL per subdomain (MapLibre has no {s} placeholder). */
export function expandTileUrl(url: string, subdomains: readonly string[]): string[] {
  if (!url.includes('{s}')) return [url];
  return (subdomains.length ? subdomains : ['a', 'b', 'c']).map((s) => url.replace('{s}', s));
}

export type Ground = 'satellite' | 'map';

/**
 * The 3D view's style: configured basemap, satellite imagery when configured (shown instead of the basemap when `ground` is
 * 'satellite'), plus terrain relief and hillshade when an elevation source is configured (D6).
 */
export function style3d(cfg: MapConfig, ground: Ground = 'satellite'): StyleSpecification {
  const t = cfg.terrain;
  const sat = cfg.satellite;
  const showSat = !!sat && ground === 'satellite';
  const style: StyleSpecification = {
    version: 8,
    sources: {
      base: { type: 'raster', tiles: expandTileUrl(cfg.tile_url, cfg.subdomains), tileSize: 256, maxzoom: cfg.max_zoom,
        attribution: cfg.attribution },
    },
    layers: [{ id: 'base', type: 'raster', source: 'base', layout: { visibility: showSat ? 'none' : 'visible' } }],
  };
  if (sat) {
    style.sources['satellite'] = { type: 'raster', tiles: [sat.tile_url], tileSize: 256, maxzoom: sat.max_zoom, attribution: sat.attribution };
    style.layers.push({ id: 'satellite', type: 'raster', source: 'satellite', layout: { visibility: showSat ? 'visible' : 'none' } });
  }
  if (t) {
    // two sources over the same tiles: MapLibre advises not to share one raster-dem source between terrain and hillshade
    const dem = { type: 'raster-dem' as const, tiles: [t.tile_url], encoding: t.encoding, tileSize: 256, maxzoom: t.max_zoom };
    style.sources['terrain'] = { ...dem, attribution: t.attribution };
    style.sources['hillshade'] = dem;
    style.layers.push({ id: 'hillshade', type: 'hillshade', source: 'hillshade', paint: { 'hillshade-exaggeration': 0.35 } });
    style.terrain = { source: 'terrain', exaggeration: 1.5 };
  }
  return style;
}

/** One full turn around the field every 90 s: slow enough to read the terrain, fast enough to show it is a 3D view. */
const ORBIT_DEG_PER_MS = 360 / 90_000;

/**
 * 3D, view-only counterpart of GeoMap: tilted / rotatable MapLibre view with terrain relief, the same layers and points draped on
 * the ground. After framing the data the camera slowly orbits it (not with reduced motion); any map interaction stops the orbit.
 * Areas and validation stay with SQL Server; nothing here is measured or saved.
 */
@Component({
  selector: 'app-geo-map-3d',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div #host class="map3d" [style.height]="height()" role="region" aria-label="3D map"></div>
    @if (error(); as e) { <div class="msg bad">{{ e }}</div> }
    @else if (loading()) { <div class="msg">Loading 3D view…</div> }
    @else {
      <div class="ctl">
        @if (hasSatellite()) {
          <div class="seg" role="group" aria-label="Ground">
            <button type="button" [class.on]="ground() === 'satellite'" [attr.aria-pressed]="ground() === 'satellite'"
              (click)="setGround('satellite')" data-testid="ground-satellite">Satellite</button>
            <button type="button" [class.on]="ground() === 'map'" [attr.aria-pressed]="ground() === 'map'"
              (click)="setGround('map')" data-testid="ground-map">Map</button>
          </div>
        }
        <button type="button" class="orbit" (click)="toggleOrbit()" [attr.aria-pressed]="orbiting()" data-testid="orbit"
          [attr.aria-label]="orbiting() ? 'Stop rotating' : 'Rotate around the field'">{{ orbiting() ? '❚❚ Pause' : '▶ Rotate' }}</button>
      </div>
    }
  `,
  styles: `
    :host { display: block; position: relative; }
    .map3d { width: 100%; border-radius: 8px; border: 1px solid var(--mat-sys-outline-variant); overflow: hidden; }
    .msg { position: absolute; inset: 0; display: grid; place-items: center; color: var(--mat-sys-on-surface-variant); font: var(--mat-sys-body-medium); }
    .bad { color: var(--mat-sys-error); padding: 16px; text-align: center; }
    .ctl { position: absolute; top: 52px; right: 10px; z-index: 2; display: flex; flex-direction: column; align-items: flex-end; gap: 8px; }
    .seg { display: flex; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 4px rgb(0 0 0 / 30%); }
    .ctl button { border: 0; padding: 7px 12px; background: #fff; color: var(--cp-forest); font: 600 12px/1 var(--cp-font); cursor: pointer;
      transition: background .2s, color .2s; }
    .seg button.on { background: var(--cp-forest); color: #fff; }
    .orbit { border-radius: 10px; box-shadow: 0 1px 4px rgb(0 0 0 / 30%); }
  `,
})
export class GeoMap3d implements AfterViewInit, OnDestroy {
  readonly layers = input<MapLayer[]>([]);
  readonly points = input<MapPoint[]>([]);
  readonly drawing = input<LonLat[] | null>(null);
  readonly height = input('360px');
  readonly center = input<[number, number]>([20.0, 73.8]); // lat, lon
  /** Emitted when the 3D view cannot start (no WebGL, files missing); the 2D map takes over. */
  readonly failed = output<string>();

  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly hasSatellite = signal(false);
  protected readonly ground = signal<Ground>('satellite');
  protected readonly orbiting = signal(false);
  private readonly host = viewChild.required<ElementRef<HTMLDivElement>>('host');
  private readonly clientConfig = inject(ClientConfigService);
  private map?: MlMap;
  private ready = false;
  private destroyed = false;
  private fittedFor = '';
  private orbitFrame = 0;
  private orbitLast = 0;
  private userMoved = false;

  constructor() {
    effect(() => {
      const layers = this.layers();
      const points = this.points();
      const drawing = this.drawing();
      this.render(layers, points, drawing);
    });
  }

  async ngAfterViewInit(): Promise<void> {
    try {
      const [ml, cfg] = await Promise.all([import('maplibre-gl'), firstValueFrom(this.clientConfig.config())]);
      if (this.destroyed) return;
      // Without its worker MapLibre draws raster tiles but never finishes loading; fail clearly instead of spinning forever.
      const workerUrl = new URL(`${VENDOR}maplibre-gl-worker.mjs`, document.baseURI).href;
      const probe = await fetch(workerUrl, { method: 'HEAD' }).catch(() => null);
      if (!probe?.ok || (probe.headers.get('content-type') ?? '').includes('text/html')) {
        throw new Error('the 3D map files (/vendor/maplibre) are not being served — restart the frontend server');
      }
      ensureCss();
      ml.setWorkerUrl(workerUrl);
      const [lat, lon] = this.center();
      this.hasSatellite.set(!!cfg.map.satellite);
      this.ground.set(cfg.map.satellite ? 'satellite' : 'map');
      const map = new ml.Map({ container: this.host().nativeElement, style: style3d(cfg.map, this.ground()), center: [lon, lat], zoom: 13,
        pitch: 60, bearing: -20, maxPitch: 85, attributionControl: { compact: true } });
      this.map = map;
      map.addControl(new ml.NavigationControl({ visualizePitch: true }), 'top-left');
      map.addControl(new ml.ScaleControl({ unit: 'metric' }), 'bottom-left');
      if (cfg.map.terrain) map.addControl(new ml.TerrainControl({ source: 'terrain', exaggeration: 1.5 }), 'top-left');
      map.on('error', (e) => console.warn('3D map:', e.error?.message ?? e));   // e.g. one tile failed; the map keeps working
      // the user takes over (drag, zoom, compass, ...): stop orbiting. The orbit's own camera moves carry no originalEvent.
      map.on('movestart', (e) => {
        if (!e.originalEvent) return;
        this.userMoved = true;
        this.stopOrbit();
      });
      map.on('load', () => {
        this.addOverlays(map, ml);
        this.ready = true;
        this.loading.set(false);
        this.render(this.layers(), this.points(), this.drawing());
      });
    } catch (e) {
      this.loading.set(false);
      this.error.set(`The 3D view could not start: ${e instanceof Error ? e.message : 'unknown error'}. Use 2D meanwhile.`);
      this.failed.emit(this.error() ?? '3D view failed');
    }
  }

  ngOnDestroy(): void {
    this.destroyed = true;
    this.stopOrbit();
    this.map?.remove();
    this.map = undefined;
  }

  protected setGround(ground: Ground): void {
    const map = this.map;
    if (!map || !this.ready || ground === this.ground()) return;
    this.ground.set(ground);
    map.setLayoutProperty('satellite', 'visibility', ground === 'satellite' ? 'visible' : 'none');
    map.setLayoutProperty('base', 'visibility', ground === 'map' ? 'visible' : 'none');
  }

  protected toggleOrbit(): void {
    if (this.orbiting()) this.stopOrbit(); else this.startOrbit();
  }

  private startOrbit(): void {
    if (!this.map || this.orbiting()) return;
    this.orbiting.set(true);
    this.orbitLast = 0;
    this.orbitFrame = requestAnimationFrame(this.orbitStep);
  }

  private stopOrbit(): void {
    this.orbiting.set(false);
    cancelAnimationFrame(this.orbitFrame);
  }

  /** Turns the camera around the current centre; elapsed time is capped so a backgrounded tab does not jump on return. */
  private readonly orbitStep = (now: number): void => {
    const map = this.map;
    if (!map || !this.orbiting()) return;
    if (this.orbitLast) map.setBearing((map.getBearing() + Math.min(now - this.orbitLast, 100) * ORBIT_DEG_PER_MS) % 360);
    this.orbitLast = now;
    this.orbitFrame = requestAnimationFrame(this.orbitStep);
  };

  private addOverlays(map: MlMap, ml: typeof import('maplibre-gl')): void {
    const empty = { type: 'FeatureCollection' as const, features: [] };
    map.addSource('shapes', { type: 'geojson', data: empty });
    map.addSource('pts', { type: 'geojson', data: empty });
    map.addSource('drawing', { type: 'geojson', data: empty });
    map.addLayer({ id: 'shapes-fill', type: 'fill', source: 'shapes',
      paint: { 'fill-color': ['get', 'color'], 'fill-opacity': ['get', 'fill'] } });
    map.addLayer({ id: 'shapes-line', type: 'line', source: 'shapes', filter: ['!', ['get', 'dashed']],
      paint: { 'line-color': ['get', 'color'], 'line-width': 2.5 } });
    map.addLayer({ id: 'shapes-dash', type: 'line', source: 'shapes', filter: ['get', 'dashed'],
      paint: { 'line-color': ['get', 'color'], 'line-width': 2.5, 'line-dasharray': [3, 2] } });
    map.addLayer({ id: 'drawing-line', type: 'line', source: 'drawing', filter: ['==', ['geometry-type'], 'LineString'],
      paint: { 'line-color': '#e65100', 'line-width': 2, 'line-dasharray': [2, 2] } });
    map.addLayer({ id: 'drawing-pts', type: 'circle', source: 'drawing', filter: ['==', ['geometry-type'], 'Point'],
      paint: { 'circle-radius': 5, 'circle-color': '#e65100', 'circle-stroke-color': '#fff', 'circle-stroke-width': 1 } });
    map.addLayer({ id: 'pts', type: 'circle', source: 'pts',
      paint: { 'circle-radius': 6, 'circle-color': ['get', 'color'], 'circle-stroke-color': '#fff', 'circle-stroke-width': 1.5 } });
    // labels as hover tooltips, like the 2D map
    const popup = new ml.Popup({ closeButton: false, closeOnClick: false, offset: 8 });
    for (const id of ['shapes-fill', 'pts']) {
      map.on('mousemove', id, (e) => {
        const label = e.features?.[0]?.properties?.['label'] as string | undefined;
        map.getCanvas().style.cursor = label ? 'pointer' : '';
        if (label) popup.setLngLat(e.lngLat).setText(label).addTo(map); else popup.remove();
      });
      map.on('mouseleave', id, () => { map.getCanvas().style.cursor = ''; popup.remove(); });
    }
  }

  private render(layers: MapLayer[], points: MapPoint[], drawing: LonLat[] | null): void {
    const map = this.map;
    if (!map || !this.ready) return;
    (map.getSource('shapes') as GeoJSONSource).setData({ type: 'FeatureCollection', features: layers.map((l) => ({ type: 'Feature',
      geometry: l.geojson as unknown as GeoJSON.Geometry,
      properties: { color: l.color, dashed: !!l.dashed, fill: l.fillOpacity ?? 0.15, label: l.label ?? '' } })) });
    (map.getSource('pts') as GeoJSONSource).setData({ type: 'FeatureCollection', features: points.map((p) => ({ type: 'Feature',
      geometry: { type: 'Point', coordinates: [p.lon, p.lat] }, properties: { color: p.color ?? '#1565c0', label: p.label ?? '' } })) });
    const v = drawing ?? [];
    const ring = v.length > 2 ? [...v, v[0]] : v;
    (map.getSource('drawing') as GeoJSONSource).setData({ type: 'FeatureCollection', features: [
      ...(ring.length > 1 ? [{ type: 'Feature' as const, geometry: { type: 'LineString' as const, coordinates: ring }, properties: {} }] : []),
      ...v.map((c) => ({ type: 'Feature' as const, geometry: { type: 'Point' as const, coordinates: c }, properties: {} })),
    ] });
    // frame the data once per distinct data set (as the 2D map does), keeping the 3D tilt
    const key = JSON.stringify(layers.map((l) => l.geojson)) + JSON.stringify(points) + JSON.stringify(v);
    const b = boundsOf(layers.map((l) => l.geojson), [...points.map((p): LonLat => [p.lon, p.lat]), ...v]);
    if (b && key !== this.fittedFor) {
      const first = this.fittedFor === '';
      this.fittedFor = key;
      if (first && !reducedMotion()) {
        // short entrance from straight above into the tilted view (orients the user; no continuous motion)
        const cam = map.cameraForBounds(b, { padding: 60, maxZoom: 17, pitch: 60, bearing: -20 });
        map.jumpTo({ center: cam?.center ?? map.getCenter(), zoom: Math.max(1, (cam?.zoom ?? 14) - 1.5), pitch: 0, bearing: 0 });
        map.easeTo({ ...cam, pitch: 60, bearing: -20, duration: 1400, easing: (t) => 1 - (1 - t) ** 3 });
        // then circle the data; jumping the camera mid-ease would cut the entrance short, so wait for it to finish
        map.once('moveend', () => { if (!this.destroyed && !this.userMoved) this.startOrbit(); });
      } else {
        map.fitBounds(b, { padding: 60, maxZoom: 17, pitch: 60, bearing: -20, duration: 0 });
      }
    }
  }
}
```

### 6.2 `shared/geo-map.ts`: wrapper with the 2D / 3D switch

```ts
import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnDestroy,
  OnInit,
  effect,
  inject,
  input,
  output,
  signal,
  viewChild,
} from '@angular/core';
import * as L from 'leaflet';

import { ClientConfigService, MapConfig } from '../core/api/client-config.service';
import type { GeoGeometry } from '../farms/farm.models';
import type { LonLat } from './geo';
import { GeoMap3d } from './geo-map-3d';

export function prefersReducedMotion(): boolean {
  return typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
}

export interface MapLayer {
  geojson: GeoGeometry;
  color: string;
  label?: string;
  dashed?: boolean;
  fillOpacity?: number;
}

export interface MapPoint {
  lat: number;
  lon: number;
  label?: string;
  color?: string;
}

/** True when the browser can create a WebGL context (needed by the 3D view). */
export function supportsWebGl(): boolean {
  try {
    const c = document.createElement('canvas');
    return !!(c.getContext('webgl2') ?? c.getContext('webgl'));
  } catch {
    return false;
  }
}

/**
 * Reusable map (spec §28 "reusable map components"). Display-only unless the parent listens to mapClick.
 * Views open in 3D (a view-only MapLibre view with terrain, GeoMap3d) unless `defaultMode` is '2d' or the browser has no WebGL; 2D
 * (Leaflet) is the working view where drawing and clicks happen, and it stays alive underneath so nothing is lost when switching.
 */
@Component({
  selector: 'app-geo-map',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [GeoMap3d],
  template: `
    <div class="wrap">
      <div #host class="map" [class.hidden]="mode() === '3d'" [style.height]="height()" role="region" aria-label="Map"></div>
      @if (mode() === '3d') {
        <app-geo-map-3d [layers]="layers()" [points]="points()" [drawing]="drawing()" [height]="height()" [center]="center()"
                        (failed)="fallBack($event)" />
        @if (drawing() !== null) { <div class="hint">3D is view-only — switch to 2D to add or change corners.</div> }
      }
      @if (allow3d()) {
        <div class="mode" role="group" aria-label="Map view">
          <button type="button" [class.on]="mode() === '2d'" [attr.aria-pressed]="mode() === '2d'" (click)="setMode('2d')">2D</button>
          <button type="button" [class.on]="mode() === '3d'" [attr.aria-pressed]="mode() === '3d'" (click)="setMode('3d')"
            data-testid="map-3d">3D</button>
        </div>
      }
    </div>
  `,
  styles: `
    .wrap { position: relative; }
    .map { width: 100%; border-radius: 8px; border: 1px solid var(--mat-sys-outline-variant); z-index: 0; }
    .hidden { display: none; }
    .mode { position: absolute; top: 10px; right: 10px; z-index: 2; display: flex; border-radius: 10px; overflow: hidden;
      box-shadow: 0 1px 4px rgb(0 0 0 / 30%); }
    .mode button { border: 0; padding: 7px 14px; background: #fff; color: var(--cp-forest); font: 600 12px/1 var(--cp-font); cursor: pointer; transition: background .2s, color .2s; }
    .mode button.on { background: var(--cp-forest); color: #fff; }
    .hint { position: absolute; left: 50%; bottom: 12px; transform: translateX(-50%); z-index: 2; padding: 4px 10px; border-radius: 4px;
      background: rgb(0 0 0 / 65%); color: #fff; font: var(--mat-sys-body-small); pointer-events: none; }
  `,
})
export class GeoMap implements OnInit, AfterViewInit, OnDestroy {
  readonly layers = input<MapLayer[]>([]);
  readonly points = input<MapPoint[]>([]);
  readonly drawing = input<LonLat[] | null>(null);
  readonly height = input('360px');
  readonly center = input<[number, number]>([20.0, 73.8]); // lat, lon
  /** Offer the 2D / 3D switch (on by default). */
  readonly allow3d = input(true);
  /** View shown first: 3D for viewing; editors where the user draws or clicks pass '2d'. */
  readonly defaultMode = input<'2d' | '3d'>('3d');
  readonly mapClick = output<{ lat: number; lon: number }>();
  protected readonly mode = signal<'2d' | '3d'>('2d');

  private readonly host = viewChild.required<ElementRef<HTMLDivElement>>('host');
  private readonly clientConfig = inject(ClientConfigService);
  private map?: L.Map;
  private readonly group = L.featureGroup();
  private readonly drawGroup = L.featureGroup();
  private fittedFor = '';

  constructor() {
    effect(() => {
      const layers = this.layers();
      const points = this.points();
      this.render(layers, points);
    });
    effect(() => this.renderDrawing(this.drawing()));
  }

  ngOnInit(): void {
    if (this.allow3d() && this.defaultMode() === '3d' && supportsWebGl()) this.mode.set('3d');
  }

  /** The 3D view could not start: show the 2D map (kept alive underneath) instead of an error. */
  protected fallBack(reason: string): void {
    console.warn('3D map unavailable, showing 2D:', reason);
    this.setMode('2d');
  }

  ngAfterViewInit(): void {
    this.map = L.map(this.host().nativeElement, { zoomControl: true, attributionControl: true }).setView(this.center(), 13);
    // Basemap tiles come from server configuration (decision D6); the map works without them (shapes still draw).
    this.clientConfig.config().subscribe((c) => this.addTiles(c.map));
    this.group.addTo(this.map);
    this.drawGroup.addTo(this.map);
    this.map.on('click', (e: L.LeafletMouseEvent) => this.mapClick.emit({ lat: e.latlng.lat, lon: e.latlng.lng }));
    this.render(this.layers(), this.points());
    this.renderDrawing(this.drawing());
    setTimeout(() => this.map?.invalidateSize({ animate: false }), 50); // container may have been hidden (tabs/dialogs) when created
  }

  ngOnDestroy(): void {
    // Removing a map mid-animation makes Leaflet throw (_leaflet_pos); stop animations and listeners first.
    if (this.map) {
      this.map.stop();
      this.map.off();
      this.map.remove();
      this.map = undefined;
    }
  }

  protected setMode(mode: '2d' | '3d'): void {
    if (mode === this.mode()) return;
    this.mode.set(mode);
    if (mode === '2d') {   // Leaflet was hidden (display:none) while 3D showed: resize and re-frame once visible again
      setTimeout(() => {
        this.map?.invalidateSize({ animate: false });
        this.fittedFor = '';
        this.render(this.layers(), this.points());
        this.renderDrawing(this.drawing());
      }, 0);
    }
  }

  private addTiles(cfg: MapConfig): void {
    if (!this.map) return;
    const opts: L.TileLayerOptions = { maxZoom: cfg.max_zoom, attribution: cfg.attribution };
    if (cfg.subdomains.length) opts.subdomains = cfg.subdomains;
    L.tileLayer(cfg.tile_url, opts).addTo(this.map);
  }

  private render(layers: MapLayer[], points: MapPoint[]): void {
    if (!this.map) return;
    this.group.clearLayers();
    for (const l of layers) {
      // Solid outlines trace themselves in (styles.scss `path.cp-shape`); dashed ones (overlaps, previews) keep their dash pattern.
      const shape = L.geoJSON(l.geojson as unknown as GeoJSON.GeoJsonObject, {
        style: { color: l.color, weight: 2.5, dashArray: l.dashed ? '6 4' : undefined, fillOpacity: l.fillOpacity ?? 0.15,
          className: l.dashed ? 'cp-shape-dashed' : 'cp-shape', lineJoin: 'round' },
      });
      if (l.label) shape.bindTooltip(l.label, { sticky: true });
      shape.addTo(this.group);
      if (!l.dashed) shape.eachLayer((x) => (x as L.Path).getElement?.()?.setAttribute('pathLength', '1'));
    }
    for (const p of points) {
      // pulsing pin (CSS in styles.scss); the colour is passed as a custom property
      const icon = L.divIcon({ className: '', iconSize: [14, 14], iconAnchor: [7, 7],
        html: `<span class="cp-pin" style="--c:${(p.color ?? '#1565c0').replace(/[^#a-zA-Z0-9(),.%\s]/g, '')}"><i></i></span>` });
      const m = L.marker([p.lat, p.lon], { icon, keyboard: false });
      if (p.label) m.bindTooltip(p.label, { direction: 'top', offset: [0, -8] });
      m.addTo(this.group);
    }
    const key = JSON.stringify(layers.map((l) => l.geojson)) + JSON.stringify(points);
    const bounds = this.group.getBounds();
    if (key !== this.fittedFor && bounds.isValid()) {
      // First framing flies in from the overview; later changes (and hidden / zero-size maps) jump without animation.
      const fly = this.fittedFor === '' && this.map.getSize().x > 0 && !prefersReducedMotion();
      if (fly) this.map.flyToBounds(bounds.pad(0.25), { maxZoom: 17, duration: 1.2, easeLinearity: 0.2 });
      else this.map.fitBounds(bounds.pad(0.25), { maxZoom: 17, animate: false });
      this.fittedFor = key;
    }
  }

  private renderDrawing(vertices: LonLat[] | null): void {
    if (!this.map) return;
    this.drawGroup.clearLayers();
    if (!vertices?.length) return;
    const latlngs = vertices.map(([lon, lat]) => L.latLng(lat, lon));
    L.polyline(latlngs.length > 2 ? [...latlngs, latlngs[0]] : latlngs, { color: '#e65100', weight: 2, dashArray: '4 4' }).addTo(this.drawGroup);
    latlngs.forEach((ll, i) => L.circleMarker(ll, { radius: i === 0 ? 7 : 5, color: '#e65100', fillOpacity: 1 }).addTo(this.drawGroup));
    // Typed / pasted / GPS corners can lie outside the view: bring them in. Clicked corners are already visible, so no jump.
    if (this.map.getSize().x === 0) return;   // hidden (3D shown); setMode('2d') re-renders once visible
    const drawn = L.latLngBounds(latlngs);
    if (this.map.getBounds().contains(drawn)) return;
    if (latlngs.length === 1) this.map.panTo(latlngs[0], { animate: false });
    else this.map.fitBounds(drawn.pad(0.25), { maxZoom: 17, animate: false });
  }
}
```

> `render()` uses the CSS classes `cp-shape`, `cp-shape-dashed` and `cp-pin` for the outline trace-in and pulsing-pin animations, defined in this repo's `styles.scss`. They are optional; without them, shapes and pins render plainly.

### 6.3 `core/api/client-config.service.ts`: config types and loading

`ApiService` is this repo's HTTP wrapper. Replace it with `HttpClient.get('/api/v1/config/client')` or your own client.

```ts
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
```

### 6.4 `shared/geo.ts` (excerpt): `LonLat` and `boundsOf()`

```ts
import type { GeoGeometry } from '../farms/farm.models';

export type LonLat = [number, number];

/** [[minLon, minLat], [maxLon, maxLat]] over polygons and extra (lon, lat) positions; null when there is nothing to frame. */
export function boundsOf(geometries: readonly GeoGeometry[], extra: readonly LonLat[] = []): [LonLat, LonLat] | null {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  const visit = (c: unknown): void => {
    if (Array.isArray(c) && typeof c[0] === 'number') {
      const [x, y] = c as number[];
      minX = Math.min(minX, x); maxX = Math.max(maxX, x); minY = Math.min(minY, y); maxY = Math.max(maxY, y);
    } else if (Array.isArray(c)) {
      c.forEach(visit);
    }
  };
  geometries.forEach((g) => visit(g.coordinates));
  extra.forEach(visit);
  return Number.isFinite(minX) ? [[minX, minY], [maxX, maxY]] : null;
}
```

### 6.5 `farms/farm.models.ts` (excerpt): `GeoGeometry`

```ts
export interface GeoGeometry {
  type: 'Polygon' | 'MultiPolygon';
  coordinates: number[][][] | number[][][][];
}
```

### 6.6 Backend (optional): `api/v1/client_config.py` (FastAPI)

Register the router with your API router (here, `app/api/v1/router.py`). `ActivePrincipal` is this repo's auth dependency; replace it with yours or remove it.

```python
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


class SatelliteConfigOut(BaseModel):
    tile_url: str
    max_zoom: int
    attribution: str


class MapConfigOut(BaseModel):
    provider: str
    tile_url: str
    attribution: str
    max_zoom: int
    subdomains: list[str]
    terrain: TerrainConfigOut | None = None   # 3D view elevation tiles; None = 3D without relief
    satellite: SatelliteConfigOut | None = None   # 3D view imagery; None = street map only


class ClientConfigOut(BaseModel):
    map: MapConfigOut


@router.get("/client", response_model=ClientConfigOut, summary="Non-secret client configuration (basemap, terrain and imagery tiles)")
def client_config(_: ActivePrincipal) -> ClientConfigOut:
    s = get_settings()
    terrain = TerrainConfigOut(tile_url=s.MAP_TERRAIN_URL, encoding=s.MAP_TERRAIN_ENCODING, max_zoom=s.MAP_TERRAIN_MAX_ZOOM,
                               attribution=s.MAP_TERRAIN_ATTRIBUTION) if s.MAP_TERRAIN_URL.strip() else None
    satellite = SatelliteConfigOut(tile_url=s.MAP_SATELLITE_URL, max_zoom=s.MAP_SATELLITE_MAX_ZOOM,
                                   attribution=s.MAP_SATELLITE_ATTRIBUTION) if s.MAP_SATELLITE_URL.strip() else None
    return ClientConfigOut(map=MapConfigOut(provider=s.MAP_TILE_PROVIDER, tile_url=s.MAP_TILE_URL, attribution=s.MAP_TILE_ATTRIBUTION,
                                            max_zoom=s.MAP_TILE_MAX_ZOOM,
                                            subdomains=[x.strip() for x in s.MAP_TILE_SUBDOMAINS.split(",") if x.strip()],
                                            terrain=terrain, satellite=satellite))
```

Settings (`app/core/config.py`, a pydantic-settings `Settings` class):

```python
    # Basemap tiles for the map components (decision D6). The browser loads tiles directly from this URL
    # template; it is configuration, not business logic. The default is OpenStreetMap's public server, which is
    # for development only (usage policy: attribution, no heavy use) — set a licensed/self-hosted source for production.
    MAP_TILE_PROVIDER: str = "osm-dev"
    MAP_TILE_URL: str = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    MAP_TILE_ATTRIBUTION: str = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    MAP_TILE_MAX_ZOOM: int = 19
    MAP_TILE_SUBDOMAINS: str = ""
    # 3D view terrain (elevation) tiles for the map components — display only, never used for any area or business rule.
    # Default: the public AWS "Terrain Tiles" dataset (terrarium encoding), for development only; production sets a licensed /
    # self-hosted DEM source. Empty URL = the 3D view still tilts / rotates, but without relief.
    MAP_TERRAIN_URL: str = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
    MAP_TERRAIN_ENCODING: str = "terrarium"     # terrarium | mapbox (how elevation is packed in the PNG)
    MAP_TERRAIN_MAX_ZOOM: int = 15
    MAP_TERRAIN_ATTRIBUTION: str = 'Elevation: <a href="https://registry.opendata.aws/terrain-tiles/">AWS Terrain Tiles</a>'
    # 3D view satellite imagery draped on the terrain — display only. Default: Esri World Imagery, for development only
    # (production use needs an ArcGIS licence or a licensed / self-hosted imagery source). Empty URL = no satellite option.
    MAP_SATELLITE_URL: str = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
    MAP_SATELLITE_MAX_ZOOM: int = 18
    MAP_SATELLITE_ATTRIBUTION: str = "Imagery &copy; Esri, Maxar, Earthstar Geographics, and the GIS User Community"

    # in the settings validator:
    if self.MAP_TERRAIN_ENCODING not in ("terrarium", "mapbox"):
        raise ValueError("MAP_TERRAIN_ENCODING must be 'terrarium' or 'mapbox'")
```

---

## 7. Framework-agnostic version (React, Vue, plain JS)

The same 3D behaviour without Angular. With a bundler such as Vite, importing `maplibre-gl` normally resolves the worker automatically. If it doesn't, copy the worker as in section 3 and call `maplibregl.setWorkerUrl(...)`.

`map3d.ts`:

```ts
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

export interface Map3dConfig {
  base: string;          // street map tile URL
  satellite?: string;    // imagery tile URL (omit = no Satellite option)
  terrain?: string;      // terrarium DEM tile URL (omit = no relief)
}

/** Development-only public sources; replace them for production (see section 5). */
export const DEV_CONFIG: Map3dConfig = {
  base: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  satellite: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  terrain: 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png',
};

export interface Shape { geometry: GeoJSON.Geometry; color: string; label?: string; dashed?: boolean; fillOpacity?: number }
export interface Pin { lat: number; lon: number; color?: string; label?: string }

const ORBIT_DEG_PER_MS = 360 / 90_000;   // one full turn every 90 s

export function supportsWebGl(): boolean {
  try { const c = document.createElement('canvas'); return !!(c.getContext('webgl2') ?? c.getContext('webgl')); }
  catch { return false; }
}

export function createMap3d(container: HTMLElement, cfg: Map3dConfig, opts: { onOrbitChange?: (on: boolean) => void } = {}) {
  const ground: 'satellite' | 'map' = cfg.satellite ? 'satellite' : 'map';
  const style: maplibregl.StyleSpecification = {
    version: 8,
    sources: { base: { type: 'raster', tiles: [cfg.base], tileSize: 256, maxzoom: 19, attribution: '© OpenStreetMap contributors' } },
    layers: [{ id: 'base', type: 'raster', source: 'base', layout: { visibility: ground === 'map' ? 'visible' : 'none' } }],
  };
  if (cfg.satellite) {
    style.sources.satellite = { type: 'raster', tiles: [cfg.satellite], tileSize: 256, maxzoom: 18,
      attribution: 'Imagery © Esri, Maxar, Earthstar Geographics, and the GIS User Community' };
    style.layers.push({ id: 'satellite', type: 'raster', source: 'satellite' });
  }
  if (cfg.terrain) {
    // separate sources for terrain and hillshade (MapLibre advises not to share one raster-dem source)
    const dem = { type: 'raster-dem' as const, tiles: [cfg.terrain], encoding: 'terrarium' as const, tileSize: 256, maxzoom: 15 };
    style.sources.terrain = { ...dem, attribution: 'Elevation: AWS Terrain Tiles' };
    style.sources.hillshade = dem;
    style.layers.push({ id: 'hillshade', type: 'hillshade', source: 'hillshade', paint: { 'hillshade-exaggeration': 0.35 } });
    style.terrain = { source: 'terrain', exaggeration: 1.5 };
  }

  const map = new maplibregl.Map({ container, style, center: [73.8, 20.0], zoom: 13, pitch: 60, bearing: -20, maxPitch: 85,
    attributionControl: { compact: true } });
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-left');
  map.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-left');
  if (cfg.terrain) map.addControl(new maplibregl.TerrainControl({ source: 'terrain', exaggeration: 1.5 }), 'top-left');
  map.on('error', (e) => console.warn('3D map:', e.error?.message ?? e));   // e.g. one tile failed; the map keeps working

  // ---- orbit (Pause / Rotate) ----
  let orbiting = false, frame = 0, last = 0, userMoved = false, ready = false, fitted = false;
  const setOrbit = (on: boolean) => { orbiting = on; opts.onOrbitChange?.(on); };
  const step = (now: number) => {
    if (!orbiting) return;
    // elapsed time is capped so a backgrounded tab does not jump on return
    if (last) map.setBearing((map.getBearing() + Math.min(now - last, 100) * ORBIT_DEG_PER_MS) % 360);
    last = now;
    frame = requestAnimationFrame(step);
  };
  const startOrbit = () => { if (orbiting) return; setOrbit(true); last = 0; frame = requestAnimationFrame(step); };
  const stopOrbit = () => { setOrbit(false); cancelAnimationFrame(frame); };
  // a user drag / zoom / compass click stops the orbit; the orbit's own moves have no originalEvent
  map.on('movestart', (e) => { if (e.originalEvent) { userMoved = true; stopOrbit(); } });

  let pending: { shapes: Shape[]; pins: Pin[] } = { shapes: [], pins: [] };

  map.on('load', () => {
    const empty = { type: 'FeatureCollection' as const, features: [] };
    map.addSource('shapes', { type: 'geojson', data: empty });
    map.addSource('pts', { type: 'geojson', data: empty });
    map.addLayer({ id: 'shapes-fill', type: 'fill', source: 'shapes', paint: { 'fill-color': ['get', 'color'], 'fill-opacity': ['get', 'fill'] } });
    map.addLayer({ id: 'shapes-line', type: 'line', source: 'shapes', filter: ['!', ['get', 'dashed']],
      paint: { 'line-color': ['get', 'color'], 'line-width': 2.5 } });
    map.addLayer({ id: 'shapes-dash', type: 'line', source: 'shapes', filter: ['get', 'dashed'],
      paint: { 'line-color': ['get', 'color'], 'line-width': 2.5, 'line-dasharray': [3, 2] } });
    map.addLayer({ id: 'pts', type: 'circle', source: 'pts',
      paint: { 'circle-radius': 6, 'circle-color': ['get', 'color'], 'circle-stroke-color': '#fff', 'circle-stroke-width': 1.5 } });

    // labels as hover tooltips
    const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 8 });
    for (const id of ['shapes-fill', 'pts']) {
      map.on('mousemove', id, (e) => {
        const label = e.features?.[0]?.properties?.label as string | undefined;
        map.getCanvas().style.cursor = label ? 'pointer' : '';
        if (label) popup.setLngLat(e.lngLat).setText(label).addTo(map); else popup.remove();
      });
      map.on('mouseleave', id, () => { map.getCanvas().style.cursor = ''; popup.remove(); });
    }
    ready = true;
    setData(pending.shapes, pending.pins);
  });

  /** Replace the shapes and pins; the first data set is framed with a short fly-in, then the orbit starts. */
  function setData(shapes: Shape[], pins: Pin[]) {
    pending = { shapes, pins };
    if (!ready) return;
    (map.getSource('shapes') as maplibregl.GeoJSONSource).setData({ type: 'FeatureCollection', features: shapes.map((s) => ({
      type: 'Feature', geometry: s.geometry,
      properties: { color: s.color, dashed: !!s.dashed, fill: s.fillOpacity ?? 0.15, label: s.label ?? '' } })) });
    (map.getSource('pts') as maplibregl.GeoJSONSource).setData({ type: 'FeatureCollection', features: pins.map((p) => ({
      type: 'Feature', geometry: { type: 'Point', coordinates: [p.lon, p.lat] },
      properties: { color: p.color ?? '#1565c0', label: p.label ?? '' } })) });

    const b = new maplibregl.LngLatBounds();
    const visit = (c: any): void => { if (typeof c[0] === 'number') b.extend(c as [number, number]); else c.forEach(visit); };
    shapes.forEach((s) => visit((s.geometry as any).coordinates));
    pins.forEach((p) => b.extend([p.lon, p.lat]));
    if (b.isEmpty()) return;

    const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (!fitted && !reducedMotion) {
      // entrance: from straight above, ease into the tilted view, then start orbiting
      const cam = map.cameraForBounds(b, { padding: 60, maxZoom: 17, pitch: 60, bearing: -20 });
      map.jumpTo({ center: cam?.center ?? map.getCenter(), zoom: Math.max(1, (cam?.zoom ?? 14) - 1.5), pitch: 0, bearing: 0 });
      map.easeTo({ ...cam, pitch: 60, bearing: -20, duration: 1400, easing: (t) => 1 - (1 - t) ** 3 });
      map.once('moveend', () => { if (!userMoved) startOrbit(); });
    } else {
      map.fitBounds(b, { padding: 60, maxZoom: 17, pitch: 60, bearing: -20, duration: 0 });
    }
    fitted = true;
  }

  return {
    map,
    setData,
    hasSatellite: !!cfg.satellite,
    /** Satellite / Map button */
    setGround(g: 'satellite' | 'map') {
      if (!ready || !cfg.satellite) return;
      map.setLayoutProperty('satellite', 'visibility', g === 'satellite' ? 'visible' : 'none');
      map.setLayoutProperty('base', 'visibility', g === 'map' ? 'visible' : 'none');
    },
    /** Pause / Rotate button; returns the new state */
    toggleOrbit(): boolean { if (orbiting) stopOrbit(); else startOrbit(); return orbiting; },
    destroy() { stopOrbit(); map.remove(); },
  };
}
```

### React example

```tsx
import { useEffect, useRef, useState } from 'react';
import { createMap3d, DEV_CONFIG, supportsWebGl, Shape } from './map3d';

export function Map3d({ shapes, height = 380 }: { shapes: Shape[]; height?: number }) {
  const el = useRef<HTMLDivElement>(null);
  const api = useRef<ReturnType<typeof createMap3d>>();
  const [ground, setGround] = useState<'satellite' | 'map'>('satellite');
  const [orbiting, setOrbiting] = useState(false);

  useEffect(() => {
    if (!el.current || !supportsWebGl()) return;   // render your 2D map instead when there is no WebGL
    api.current = createMap3d(el.current, DEV_CONFIG, { onOrbitChange: setOrbiting });
    return () => api.current?.destroy();
  }, []);
  useEffect(() => { api.current?.setData(shapes, []); }, [shapes]);

  const btn = (on: boolean) => ({ border: 0, padding: '7px 12px', cursor: 'pointer', font: '600 12px/1 sans-serif',
    background: on ? '#004225' : '#fff', color: on ? '#fff' : '#004225' });
  const pick = (g: 'satellite' | 'map') => { setGround(g); api.current?.setGround(g); };

  return (
    <div style={{ position: 'relative' }}>
      <div ref={el} style={{ height, borderRadius: 8, overflow: 'hidden' }} />
      <div style={{ position: 'absolute', top: 10, right: 10, display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 8 }}>
        <div style={{ display: 'flex', borderRadius: 10, overflow: 'hidden', boxShadow: '0 1px 4px rgb(0 0 0 / 30%)' }}>
          <button style={btn(ground === 'satellite')} onClick={() => pick('satellite')}>Satellite</button>
          <button style={btn(ground === 'map')} onClick={() => pick('map')}>Map</button>
        </div>
        <button style={{ ...btn(false), borderRadius: 10, boxShadow: '0 1px 4px rgb(0 0 0 / 30%)' }}
                onClick={() => api.current?.toggleOrbit()}>{orbiting ? '❚❚ Pause' : '▶ Rotate'}</button>
      </div>
    </div>
  );
}
```

---

## 8. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| 3D shows "Loading 3D view…" forever | MapLibre worker not served. Check that `/vendor/maplibre/maplibre-gl-worker.mjs` returns JavaScript, not `index.html` (section 3) |
| "The 3D map files are not being served" | Same as above; restart the dev server after editing `angular.json` |
| 3D button missing, or always 2D | No WebGL (`supportsWebGl()` is false), or `allow3d` is false |
| Flat 3D view, no mountains | Terrain URL is empty or blocked by CORS / CSP; check the network tab for the DEM `.png` tiles |
| No Satellite / Map switch | `satellite` config is null (empty `MAP_SATELLITE_URL`) |
| Tiles blocked | Add the tile hosts to the CSP `img-src` and `connect-src`, and allow `worker-src 'self' blob:` |
| Controls look unstyled | `maplibre-gl.css` not loaded, or the CSS variables (`--cp-forest`, `--cp-font`) are not defined |
