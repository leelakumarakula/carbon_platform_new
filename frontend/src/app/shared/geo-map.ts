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
  viewChild,
} from '@angular/core';
import * as L from 'leaflet';

import { ClientConfigService, MapConfig } from '../core/api/client-config.service';
import type { GeoGeometry } from '../farms/farm.models';
import type { LonLat } from './geo';

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

/** Reusable map (spec §28 "reusable map components"). Display-only unless the parent listens to mapClick. */
@Component({
  selector: 'app-geo-map',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<div #host class="map" [style.height]="height()" role="region" aria-label="Map"></div>`,
  styles: `.map { width: 100%; border-radius: 8px; border: 1px solid var(--mat-sys-outline-variant); z-index: 0; }`,
})
export class GeoMap implements AfterViewInit, OnDestroy {
  readonly layers = input<MapLayer[]>([]);
  readonly points = input<MapPoint[]>([]);
  readonly drawing = input<LonLat[] | null>(null);
  readonly height = input('360px');
  readonly center = input<[number, number]>([20.0, 73.8]); // lat, lon
  readonly mapClick = output<{ lat: number; lon: number }>();

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
      const shape = L.geoJSON(l.geojson as unknown as GeoJSON.GeoJsonObject, {
        style: { color: l.color, weight: 2, dashArray: l.dashed ? '6 4' : undefined, fillOpacity: l.fillOpacity ?? 0.15 },
      });
      if (l.label) shape.bindTooltip(l.label, { sticky: true });
      shape.addTo(this.group);
    }
    for (const p of points) {
      const m = L.circleMarker([p.lat, p.lon], { radius: 6, color: p.color ?? '#1565c0', weight: 2, fillOpacity: 0.8 });
      if (p.label) m.bindTooltip(p.label);
      m.addTo(this.group);
    }
    const key = JSON.stringify(layers.map((l) => l.geojson)) + JSON.stringify(points);
    const bounds = this.group.getBounds();
    if (key !== this.fittedFor && bounds.isValid()) {
      this.map.fitBounds(bounds.pad(0.25), { maxZoom: 17, animate: false });
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
  }
}
