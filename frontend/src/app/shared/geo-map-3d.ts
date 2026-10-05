import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnDestroy,
  effect,
  inject,
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
