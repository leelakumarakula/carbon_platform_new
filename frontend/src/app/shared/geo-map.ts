import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnDestroy,
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

/**
 * Reusable map (spec §28 "reusable map components"). Display-only unless the parent listens to mapClick.
 * 2D (Leaflet) is the working view: drawing and clicks happen there. The 3D toggle opens a view-only MapLibre view with terrain
 * (GeoMap3d, loaded on first use); the 2D map is kept alive underneath so nothing is lost when switching back.
 */
@Component({
  selector: 'app-geo-map',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [GeoMap3d],
  template: `
    <div class="wrap">
      <div #host class="map" [class.hidden]="mode() === '3d'" [style.height]="height()" role="region" aria-label="Map"></div>
      @if (mode() === '3d') {
        <app-geo-map-3d [layers]="layers()" [points]="points()" [drawing]="drawing()" [height]="height()" [center]="center()" />
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
export class GeoMap implements AfterViewInit, OnDestroy {
  readonly layers = input<MapLayer[]>([]);
  readonly points = input<MapPoint[]>([]);
  readonly drawing = input<LonLat[] | null>(null);
  readonly height = input('360px');
  readonly center = input<[number, number]>([20.0, 73.8]); // lat, lon
  /** Offer the 2D / 3D switch (on by default). */
  readonly allow3d = input(true);
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
