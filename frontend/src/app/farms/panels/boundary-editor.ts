import { DatePipe, DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, input, output, signal } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatTooltipModule } from '@angular/material/tooltip';

import { NotifyService } from '../../core/notify.service';
import { GeoMap, MapLayer } from '../../shared/geo-map';
import { LonLat, formatArea, isKml, parseLatLonLines, polygonFromVertices, validLatLon } from '../../shared/geo';
import { runAction } from '../../shared/run-action';
import { Boundary, Farm, GeoGeometry, GeometryReport, Overlap } from '../farm.models';
import { BoundarySaved, FarmsApi } from '../farms.api';

/**
 * Draw (tap/click corners), type / paste latitude-longitude corners, walk with GPS, or upload GeoJSON/KML. Every candidate is
 * validated by SQL Server (validity, orientation, area) before it can be saved; saving creates a new boundary version.
 */
@Component({
  selector: 'app-boundary-editor',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, DecimalPipe, ReactiveFormsModule, MatButtonModule, MatFormFieldModule, MatIconModule, MatInputModule, MatTooltipModule,
    GeoMap],
  template: `
    <div class="tab-body">
      @if (editable()) {
        <div class="tools">
          <span class="muted small">Tap the map to add corners in order.</span>
          <button mat-stroked-button type="button" (click)="undo()" [disabled]="!vertices().length"><mat-icon>undo</mat-icon> Undo</button>
          <button mat-stroked-button type="button" (click)="clear()" [disabled]="!vertices().length && !uploaded()"><mat-icon>clear</mat-icon> Clear</button>
          <button mat-stroked-button type="button" (click)="gps()" matTooltip="Add your current GPS position as the next corner (walk the boundary)">
            <mat-icon>my_location</mat-icon> GPS point</button>
          <input #file type="file" hidden accept=".geojson,.json,.kml" (change)="loadFile(file.files?.[0] ?? null); file.value = ''" />
          <button mat-stroked-button type="button" (click)="file.click()"><mat-icon>upload_file</mat-icon> GeoJSON / KML</button>
          <button mat-flat-button type="button" (click)="validate()" [disabled]="busy() || (!candidate() && !uploaded())">Check boundary</button>
        </div>
        <div class="coords">
          <span class="muted small">Or enter corners as latitude / longitude (decimal degrees, WGS84), in order around the field.</span>
          <div class="coord-row">
            <mat-form-field subscriptSizing="dynamic"><mat-label>Latitude</mat-label>
              <input matInput type="number" step="any" placeholder="20.0063" [formControl]="lat" data-testid="corner-lat" /></mat-form-field>
            <mat-form-field subscriptSizing="dynamic"><mat-label>Longitude</mat-label>
              <input matInput type="number" step="any" placeholder="73.7910" [formControl]="lon" (keyup.enter)="addTyped()" data-testid="corner-lon" />
            </mat-form-field>
            <button mat-stroked-button type="button" (click)="addTyped()" data-testid="add-corner"><mat-icon>add_location</mat-icon> Add corner</button>
          </div>
          <mat-form-field subscriptSizing="dynamic" class="paste"><mat-label>Paste several corners — one "latitude, longitude" per line</mat-label>
            <textarea matInput rows="3" [formControl]="pasted" placeholder="20.0063, 73.7910&#10;20.0063, 73.7925&#10;20.0050, 73.7925" data-testid="corner-paste"></textarea>
          </mat-form-field>
          <div><button mat-stroked-button type="button" (click)="addPasted()" [disabled]="!pasted.value.trim()" data-testid="add-pasted">
            <mat-icon>playlist_add</mat-icon> Add these corners</button></div>
        </div>
        @if (vertices().length) {
          <div class="corners" data-testid="corners">
            <span class="muted small">{{ vertices().length }} corner(s){{ vertices().length < 3 ? ' — at least 3 are needed' : '' }}</span>
            @for (v of vertices(); track $index) {
              <span class="corner">{{ $index + 1 }}. {{ v[1] | number: '1.4-7' }}, {{ v[0] | number: '1.4-7' }}
                <button mat-icon-button type="button" (click)="remove($index)" [attr.aria-label]="'Remove corner ' + ($index + 1)"><mat-icon>close</mat-icon></button>
              </span>
            }
          </div>
        }
      } @else {
        <p class="muted">The boundary can only be changed while the farm is a DRAFT. Re-open the farm to correct it.</p>
      }
      <app-geo-map [layers]="layers()" [drawing]="vertices()" height="420px" defaultMode="2d" (mapClick)="add($event)" />
      @if (report(); as r) {
        <div class="report">
          <strong>Measured by SQL Server: {{ area(r.area_hectares) }}</strong>
          <span class="muted small">{{ r.vertex_count }} vertices · perimeter {{ r.perimeter_m.toFixed(0) }} m</span>
          @for (n of r.notes; track n) { <div class="note"><mat-icon inline>info</mat-icon> {{ n }}</div> }
          @for (w of r.warnings; track w) { <div class="warn"><mat-icon inline>warning</mat-icon> {{ w }}</div> }
          <div class="row-actions"><button mat-flat-button type="button" (click)="save()" [disabled]="busy()">Save as new boundary version</button></div>
        </div>
      }
      <h3>Boundary versions</h3>
      @for (b of versions(); track b.id) {
        <div class="line">
          <strong>v{{ b.version }}</strong>
          <span class="grow">{{ area(b.area_hectares) }} · {{ b.source }} · {{ b.created_at | date: 'medium' }}
            @if (b.validation_notes) { <div class="muted small">{{ b.validation_notes }}</div> }</span>
          <span [class.current]="b.status === 'CURRENT'" class="muted small">{{ b.status }}</span>
        </div>
      } @empty { <p class="muted">No boundary yet.</p> }
    </div>
  `,
  styles: `
    .tools { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 8px; }
    .report { margin: 12px 0; padding: 12px; border-radius: 8px; background: var(--mat-sys-surface-container-low); display: flex; flex-direction: column; gap: 4px; }
    .warn { color: #7a5200; } .note { color: var(--mat-sys-on-surface-variant); }
    h3 { font: var(--mat-sys-title-medium); margin: 20px 0 8px; }
    .line { display: flex; gap: 12px; align-items: center; padding: 6px 0; border-bottom: 1px solid var(--mat-sys-outline-variant); }
    .grow { flex: 1; } .current { color: #1b5e20; font-weight: 600; }
    .coords { display: flex; flex-direction: column; gap: 8px; margin-bottom: 8px; }
    .coord-row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
    .paste { width: 100%; max-width: 640px; }
    .corners { display: flex; flex-wrap: wrap; gap: 4px 12px; align-items: center; margin-bottom: 8px; }
    .corner { display: inline-flex; align-items: center; font-variant-numeric: tabular-nums; }
  `,
})
export class BoundaryEditor implements OnInit {
  readonly farm = input.required<Farm>();
  readonly overlaps = input<Overlap[]>([]);
  readonly saved = output<Farm>();
  private readonly api = inject(FarmsApi);
  private readonly notify = inject(NotifyService);

  protected readonly vertices = signal<LonLat[]>([]);
  protected readonly uploaded = signal<{ file: File; kml: boolean; text: string } | null>(null);
  protected readonly report = signal<GeometryReport | null>(null);
  protected readonly versions = signal<Boundary[]>([]);
  protected readonly busy = signal(false);
  protected readonly usedGps = signal(false);
  protected readonly typed = signal(false);
  protected readonly lat = new FormControl<number | null>(null);
  protected readonly lon = new FormControl<number | null>(null);
  protected readonly pasted = new FormControl('', { nonNullable: true });
  protected readonly area = formatArea;
  protected readonly editable = computed(() => this.farm().can_manage && this.farm().status === 'DRAFT');
  protected readonly candidate = computed<GeoGeometry | null>(() => polygonFromVertices(this.vertices()));
  protected readonly layers = computed<MapLayer[]>(() => {
    const out: MapLayer[] = [];
    const cur = this.farm().current_boundary;
    if (cur) out.push({ geojson: cur.geojson, color: '#2e7d32', label: `Current boundary v${cur.version}` });
    for (const o of this.overlaps()) {
      if (o.other_geojson && o.status !== 'OBSOLETE') out.push({ geojson: o.other_geojson, color: '#c62828', dashed: true,
        label: `Overlapping farm ${o.other_farm_code ?? ''}` });
    }
    const r = this.report();
    if (r) out.push({ geojson: r.geojson, color: '#e65100', label: 'Candidate (not saved)', fillOpacity: 0.25 });
    return out;
  });

  ngOnInit(): void {
    this.api.boundaries(this.farm().id).subscribe((v) => this.versions.set(v));
  }

  add(p: { lat: number; lon: number }): void {
    if (!this.editable()) return;
    this.uploaded.set(null);
    this.report.set(null);
    this.vertices.update((v) => [...v, [p.lon, p.lat]]);
  }

  addTyped(): void {
    const lat = Number(this.lat.value);
    const lon = Number(this.lon.value);
    if (this.lat.value === null || this.lon.value === null || !validLatLon(lat, lon)) {
      this.notify.error(new Error('Enter a latitude between −90 and 90 and a longitude between −180 and 180 (decimal degrees).'));
      return;
    }
    this.typed.set(true);
    this.add({ lat, lon });
    this.lat.reset();
    this.lon.reset();
  }

  addPasted(): void {
    const { points, errors } = parseLatLonLines(this.pasted.value);
    if (errors.length) {   // nothing is added until every line is usable
      this.notify.error(new Error(errors.slice(0, 3).join(' ') + (errors.length > 3 ? ` (+${errors.length - 3} more)` : '')));
      return;
    }
    if (!this.editable() || !points.length) return;
    this.typed.set(true);
    this.uploaded.set(null);
    this.report.set(null);
    this.vertices.update((v) => [...v, ...points]);
    this.pasted.reset();
  }

  remove(index: number): void {
    this.report.set(null);
    this.vertices.update((v) => v.filter((_, i) => i !== index));
  }

  undo(): void {
    this.report.set(null);
    this.vertices.update((v) => v.slice(0, -1));
  }

  clear(): void {
    this.vertices.set([]);
    this.uploaded.set(null);
    this.report.set(null);
    this.usedGps.set(false);
    this.typed.set(false);
  }

  gps(): void {
    if (!('geolocation' in navigator)) {
      this.notify.error(new Error('This device has no GPS / location service.'));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        this.usedGps.set(true);
        this.add({ lat: pos.coords.latitude, lon: pos.coords.longitude });
        if (pos.coords.accuracy > 15) this.notify.error(new Error(`GPS accuracy is ±${pos.coords.accuracy.toFixed(0)} m; wait for a better fix.`));
      },
      (err) => this.notify.error(new Error(`Could not read GPS position: ${err.message}`)),
      { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 },
    );
  }

  loadFile(file: File | null): void {
    if (!file) return;
    file.text().then((text) => {
      this.vertices.set([]);
      this.uploaded.set({ file, kml: isKml(file.name, text), text });
      this.validate();
    });
  }

  validate(): void {
    const up = this.uploaded();
    let body: { geojson?: object; kml?: string };
    if (up) {
      try {
        body = up.kml ? { kml: up.text } : { geojson: JSON.parse(up.text) as object };
      } catch {
        this.notify.error(new Error('The file is not valid JSON.'));
        return;
      }
    } else {
      const c = this.candidate();
      if (!c) return;
      body = { geojson: c };
    }
    runAction(this.api.validateGeometry(body), this.busy, this.notify, 'Boundary checked.', (r) => this.report.set(r));
  }

  save(): void {
    const up = this.uploaded();
    const id = this.farm().id;
    const call = up ? this.api.uploadBoundary(id, up.file)
      // typed coordinates come from a survey / handheld GPS reading, so they are recorded as SURVEY
      : this.api.saveBoundary(id, { geojson: this.candidate()!, source: this.usedGps() ? 'GPS_WALK' : this.typed() ? 'SURVEY' : 'DRAWN' });
    runAction(call, this.busy, this.notify, 'Boundary saved as a new version.', (res: BoundarySaved) => {
      this.clear();
      this.saved.emit(res.farm);
      this.ngOnInit();
    });
  }
}
