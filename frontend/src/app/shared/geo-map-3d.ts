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

/** The 3D view's style: configured basemap, plus terrain relief and hillshade when an elevation source is configured (D6). */
export function style3d(cfg: MapConfig): StyleSpecification {
  const t = cfg.terrain;
  const style: StyleSpecification = {
    version: 8,
    sources: {
      base: { type: 'raster', tiles: expandTileUrl(cfg.tile_url, cfg.subdomains), tileSize: 256, maxzoom: cfg.max_zoom,
        attribution: cfg.attribution },
    },
    layers: [{ id: 'base', type: 'raster', source: 'base' }],
  };
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

/**
 * 3D, view-only counterpart of GeoMap: tilted / rotatable MapLibre view with terrain relief, the same layers and points draped on
 * the ground. Areas and validation stay with SQL Server; nothing here is measured or saved.
 */
@Component({
  selector: 'app-geo-map-3d',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div #host class="map3d" [style.height]="height()" role="region" aria-label="3D map"></div>
    @if (error(); as e) { <div class="msg bad">{{ e }}</div> }
    @else if (loading()) { <div class="msg">Loading 3D view…</div> }
  `,
  styles: `
    :host { display: block; position: relative; }
    .map3d { width: 100%; border-radius: 8px; border: 1px solid var(--mat-sys-outline-variant); overflow: hidden; }
    .msg { position: absolute; inset: 0; display: grid; place-items: center; color: var(--mat-sys-on-surface-variant); font: var(--mat-sys-body-medium); }
    .bad { color: var(--mat-sys-error); padding: 16px; text-align: center; }
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
  private readonly host = viewChild.required<ElementRef<HTMLDivElement>>('host');
  private readonly clientConfig = inject(ClientConfigService);
  private map?: MlMap;
  private ready = false;
  private destroyed = false;
  private fittedFor = '';

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
      const map = new ml.Map({ container: this.host().nativeElement, style: style3d(cfg.map), center: [lon, lat], zoom: 13, pitch: 60,
        bearing: -20, maxPitch: 85, attributionControl: { compact: true } });
      this.map = map;
      map.addControl(new ml.NavigationControl({ visualizePitch: true }), 'top-left');
      map.addControl(new ml.ScaleControl({ unit: 'metric' }), 'bottom-left');
      if (cfg.map.terrain) map.addControl(new ml.TerrainControl({ source: 'terrain', exaggeration: 1.5 }), 'top-left');
      map.on('error', (e) => console.warn('3D map:', e.error?.message ?? e));   // e.g. one tile failed; the map keeps working
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
    this.map?.remove();
    this.map = undefined;
  }

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
      } else {
        map.fitBounds(b, { padding: 60, maxZoom: 17, pitch: 60, bearing: -20, duration: 0 });
      }
    }
  }
}
