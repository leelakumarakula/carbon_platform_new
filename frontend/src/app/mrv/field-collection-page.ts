import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';

import { ApiError } from '../core/api/api.models';
import { NotifyService } from '../core/notify.service';
import { label } from '../farmer/farmer.models';
import { GeoMap, MapPoint } from '../shared/geo-map';
import { PageHeader } from '../shared/page-header';
import { runAction } from '../shared/run-action';
import { StateView } from '../shared/state-view';
import { StatusBadge } from '../shared/status-badge';
import { MrvApi } from './mrv.api';
import { CHECKLIST_LABELS, Evidence, FieldCollection, RuleSource, SamplingPoint, collectionMissing, mrvBadge, ruleSourceLabel } from './mrv.models';

function localInput(iso: string | null): string {
  const d = iso ? new Date(iso) : new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/**
 * Field collection screen (mobile-first): GPS (device or manual), time, depth, sample, checklist, photo, submit.
 * The server measures the GPS distance to the point and the inside-farm check (SQL Server). Collectors never approve.
 */
@Component({
  selector: 'app-field-collection-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, ReactiveFormsModule, MatButtonModule, MatCheckboxModule, MatFormFieldModule, MatInputModule, PageHeader, StateView, StatusBadge, GeoMap],
  template: `
    <app-state-view [loading]="loading()" [error]="error()" (retry)="load()" />
    @if (c(); as c) {
      <app-page-header [title]="c.collection_code" [subtitle]="(point()?.point_code ?? '') + ' · ' + (point()?.farm_code ?? '')" backLink="/field" backLabel="Field work" />
      <div class="status-row"><app-status-badge [status]="badge(c.status)" [text]="label(c.status)" /> <span class="small muted">v{{ c.version }}</span></div>
      @if (c.status === 'RETURNED') { <div class="note warn">Returned: {{ c.review_notes }}</div> }
      @if (c.correction_reason) { <div class="note">Correction of an accepted record: {{ c.correction_reason }}</div> }
      <app-geo-map [points]="mapPoints()" height="220px" />
      @if (point(); as p) {
        <p class="small">Planned point <span class="mono">{{ p.latitude }}, {{ p.longitude }}</span> · depth {{ p.planned_depth_top_cm }}–{{ p.planned_depth_bottom_cm }} cm</p>
      }
      @if (c.distance_from_point_m !== null) {
        <div class="note" [class.warn]="far(c) || c.gps_inside_farm === false">
          GPS is {{ c.distance_from_point_m }} m from the planned point (tolerance {{ c.gps_tolerance_m }} m){{ c.gps_inside_farm === false ? ' and outside the farm boundary' : '' }} (measured by SQL Server).
          @if (far(c) || c.gps_inside_farm === false) { A deviation note is required. }
        </div>
      }
      <p class="small muted rules" data-testid="field-rules">
        Checklist {{ c.checklist_version }} · GPS tolerance {{ c.gps_tolerance_m }} m ({{ src(c.field_rules?.gps_tolerance_source) }}) ·
        at least {{ c.min_photos }} photo(s) ({{ src(c.field_rules?.min_photos_source) }}).
        @if (c.analysis_status === 'AWAITING_ANALYSIS') { Soil organic carbon: awaiting laboratory analysis — no value is entered in the field. }
      </p>
      <form [formGroup]="form" class="stack">
        <div class="row">
          <button mat-flat-button type="button" [disabled]="!c.can_edit || locating()" (click)="locate()" data-testid="use-gps">
            {{ locating() ? 'Locating…' : 'Use my GPS position' }}</button>
          <span class="small muted">{{ gpsInfo() }}</span>
        </div>
        <div class="grid2">
          <mat-form-field subscriptSizing="dynamic"><mat-label>Latitude</mat-label><input matInput type="number" formControlName="gps_latitude" inputmode="decimal" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Longitude</mat-label><input matInput type="number" formControlName="gps_longitude" inputmode="decimal" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>GPS accuracy (m)</mat-label><input matInput type="number" formControlName="gps_accuracy_m" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Collected at</mat-label><input matInput type="datetime-local" formControlName="collected_at" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Depth top (cm)</mat-label><input matInput type="number" formControlName="actual_depth_top_cm" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Depth bottom (cm)</mat-label><input matInput type="number" formControlName="actual_depth_bottom_cm" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Sample quantity</mat-label><input matInput type="number" formControlName="sample_quantity" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Unit</mat-label><input matInput formControlName="sample_unit" /></mat-form-field>
        </div>
        <mat-form-field subscriptSizing="dynamic"><mat-label>Field observations</mat-label><textarea matInput rows="2" formControlName="observations"></textarea></mat-form-field>
        <mat-form-field subscriptSizing="dynamic"><mat-label>Deviation note (if the GPS is far from the point or outside the farm)</mat-label>
          <input matInput formControlName="deviation_note" /></mat-form-field>
        <fieldset class="checklist"><legend class="small">Field checklist</legend>
          @for (k of c.required_checklist; track k) {
            <mat-checkbox [checked]="!!checklist()[k]" [disabled]="!c.can_edit" (change)="tick(k, $event.checked)" [attr.data-check]="k">{{ checkLabel(k) }}</mat-checkbox>
          }
        </fieldset>
      </form>
      <h3>Photos ({{ photos().length }})</h3>
      <div class="photos">
        @for (e of photos(); track e.id) { <div class="small">{{ e.description ?? 'Field photo' }} · {{ e.uploaded_at | date: 'short' }} · <span class="mono">{{ e.checksum_sha256?.slice(0, 10) }}</span></div> }
        @if (c.can_edit) {
          <label class="upload"><input type="file" accept="image/*" capture="environment" (change)="upload($event)" data-testid="photo" />
            <span>{{ uploading() ? 'Uploading…' : 'Take / add photo' }}</span></label>
        }
      </div>
      @if (c.can_edit) {
        @if (missing().length) { <p class="small muted">Still needed: {{ missing().join('; ') }}.</p> }
        <div class="actions">
          <button mat-stroked-button type="button" [disabled]="busy()" (click)="save()" data-testid="save-collection">Save</button>
          <button mat-flat-button type="button" [disabled]="busy()" (click)="submit()" data-testid="submit-collection">Save &amp; submit</button>
        </div>
        <details class="reloc"><summary class="small">Point not reachable? Request relocation</summary>
          <p class="small muted">The new location must lie inside the same farm. A supervisor approves the move; the old and new positions are kept.</p>
          <div class="row"><button mat-stroked-button type="button" [disabled]="busy()" (click)="relocate()">Request move to the GPS position above</button></div>
        </details>
      } @else {
        <p class="small muted">This record is {{ label(c.status) }} and can no longer be edited by you.</p>
      }
    }
  `,
  styles: `
    .status-row { display: flex; gap: 6px; align-items: center; margin: -8px 0 8px; }
    .stack { display: flex; flex-direction: column; gap: 8px; max-width: 640px; margin-top: 12px; }
    .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; } @media (max-width: 480px) { .grid2 { grid-template-columns: 1fr; } }
    .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; } .row button { min-height: 44px; }
    .checklist { display: flex; flex-direction: column; border: 1px solid var(--mat-sys-outline-variant); border-radius: 8px; padding: 8px 12px; }
    h3 { margin: 16px 0 8px; font: var(--mat-sys-title-small); } .mono { font-family: monospace; }
    .upload { display: inline-flex; align-items: center; gap: 8px; padding: 10px 14px; border: 1px dashed var(--mat-sys-outline); border-radius: 8px; cursor: pointer; margin-top: 6px; }
    .actions { display: flex; gap: 8px; margin: 16px 0; } .actions button { min-height: 48px; flex: 1; max-width: 240px; }
    .reloc { margin: 8px 0 24px; max-width: 640px; }
  `,
})
export class FieldCollectionPage implements OnInit {
  readonly id = input.required<string>();
  private readonly api = inject(MrvApi);
  private readonly notify = inject(NotifyService);
  protected readonly label = label;
  protected readonly badge = mrvBadge;
  protected readonly c = signal<FieldCollection | null>(null);
  protected readonly point = signal<SamplingPoint | null>(null);
  protected readonly photos = signal<Evidence[]>([]);
  protected readonly checklist = signal<Record<string, boolean>>({});
  protected readonly loading = signal(true);
  protected readonly error = signal<ApiError | null>(null);
  protected readonly busy = signal(false);
  protected readonly locating = signal(false);
  protected readonly uploading = signal(false);
  protected readonly gpsInfo = signal('');
  protected readonly form = new FormGroup({
    gps_latitude: new FormControl<number | null>(null),
    gps_longitude: new FormControl<number | null>(null),
    gps_accuracy_m: new FormControl<number | null>(null),
    collected_at: new FormControl(localInput(null), { nonNullable: true }),
    actual_depth_top_cm: new FormControl<number | null>(null),
    actual_depth_bottom_cm: new FormControl<number | null>(null),
    sample_quantity: new FormControl<number | null>(null),
    sample_unit: new FormControl('kg', { nonNullable: true }),
    observations: new FormControl('', { nonNullable: true }),
    deviation_note: new FormControl('', { nonNullable: true }),
  });
  private readonly formValue = toSignal(this.form.valueChanges, { initialValue: this.form.getRawValue() });
  /** What is still missing, from the values on screen (the server re-checks on submit). */
  protected readonly missing = computed(() => {
    const c = this.c();
    if (!c) return [];
    const v = this.formValue();
    const str = (x: number | null | undefined) => (x === null || x === undefined || `${x}` === '' ? null : String(x));
    return collectionMissing({ ...c, checklist: this.checklist(), collected_at: v.collected_at || null, gps_latitude: str(v.gps_latitude),
      gps_longitude: str(v.gps_longitude), actual_depth_top_cm: str(v.actual_depth_top_cm), actual_depth_bottom_cm: str(v.actual_depth_bottom_cm),
      deviation_note: v.deviation_note?.trim() || null }, this.photos().length);
  });
  protected readonly mapPoints = computed<MapPoint[]>(() => {
    const out: MapPoint[] = [];
    const p = this.point();
    const c = this.c();
    if (p) out.push({ lat: Number(p.latitude), lon: Number(p.longitude), color: '#e65100', label: `Planned ${p.point_code}` });
    if (c?.gps_latitude && c.gps_longitude) out.push({ lat: Number(c.gps_latitude), lon: Number(c.gps_longitude), color: '#1565c0', label: 'Recorded GPS' });
    return out;
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.api.collection(this.id()).subscribe({
      next: (c) => {
        this.set(c);
        this.loading.set(false);
        this.api.point(c.sampling_point_id).subscribe((p) => {
          this.point.set(p);
          if (c.actual_depth_top_cm === null) this.form.patchValue({ actual_depth_top_cm: Number(p.planned_depth_top_cm),
            actual_depth_bottom_cm: Number(p.planned_depth_bottom_cm) });
        });
        this.loadPhotos(c);
      },
      error: (e: unknown) => { this.error.set(ApiError.from(e)); this.loading.set(false); },
    });
  }

  private set(c: FieldCollection): void {
    this.c.set(c);
    this.checklist.set({ ...(c.checklist ?? {}) });
    const n = (v: string | null) => (v === null ? null : Number(v));
    this.form.patchValue({ gps_latitude: n(c.gps_latitude), gps_longitude: n(c.gps_longitude), gps_accuracy_m: n(c.gps_accuracy_m),
      collected_at: localInput(c.collected_at), actual_depth_top_cm: n(c.actual_depth_top_cm), actual_depth_bottom_cm: n(c.actual_depth_bottom_cm),
      sample_quantity: n(c.sample_quantity), sample_unit: c.sample_unit ?? 'kg', observations: c.observations ?? '', deviation_note: c.deviation_note ?? '' });
    if (!c.can_edit) this.form.disable();
  }

  private loadPhotos(c: FieldCollection): void {
    this.api.evidence({ project_id: c.project_id, entity_type: 'FIELD_COLLECTION', entity_id: c.id })
      .subscribe((e) => this.photos.set(e.filter((x) => x.evidence_type === 'FIELD_PHOTO')));
  }

  protected far(c: FieldCollection): boolean {
    return c.distance_from_point_m !== null && Number(c.distance_from_point_m) > Number(c.gps_tolerance_m ?? 30);
  }

  protected checkLabel(k: string): string {
    return this.c()?.checklist_items.find((i) => i.key === k)?.label ?? CHECKLIST_LABELS[k] ?? label(k);
  }

  protected src(s: RuleSource | undefined): string {
    return ruleSourceLabel(s);
  }

  protected tick(k: string, v: boolean): void {
    this.checklist.update((x) => ({ ...x, [k]: v }));
  }

  protected locate(): void {
    if (!('geolocation' in navigator)) {
      this.gpsInfo.set('This device has no GPS; enter the coordinates manually.');
      return;
    }
    this.locating.set(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        this.locating.set(false);
        this.form.patchValue({ gps_latitude: Number(pos.coords.latitude.toFixed(7)), gps_longitude: Number(pos.coords.longitude.toFixed(7)),
          gps_accuracy_m: Math.round(pos.coords.accuracy * 10) / 10 });
        this.gpsInfo.set(`±${Math.round(pos.coords.accuracy)} m`);
      },
      (err) => { this.locating.set(false); this.gpsInfo.set(`GPS unavailable (${err.message}); enter the coordinates manually.`); },
      { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 },
    );
  }

  private body(): Record<string, unknown> {
    const v = this.form.getRawValue();
    const blank = (s: string) => s.trim() || null;
    return { gps_latitude: v.gps_latitude, gps_longitude: v.gps_longitude, gps_accuracy_m: v.gps_accuracy_m,
      collected_at: v.collected_at ? new Date(v.collected_at).toISOString() : null, actual_depth_top_cm: v.actual_depth_top_cm,
      actual_depth_bottom_cm: v.actual_depth_bottom_cm, sample_quantity: v.sample_quantity, sample_unit: blank(v.sample_unit),
      observations: blank(v.observations), deviation_note: blank(v.deviation_note), checklist: this.checklist() };
  }

  protected save(): void {
    runAction(this.api.updateCollection(this.id(), this.body()), this.busy, this.notify, 'Saved.', (c) => this.set(c));
  }

  protected submit(): void {
    this.busy.set(true);
    this.api.updateCollection(this.id(), this.body()).subscribe({
      next: (c) => {
        this.set(c);
        runAction(this.api.submitCollection(this.id()), this.busy, this.notify, 'Submitted for review.', (x) => this.set(x));
      },
      error: (e: unknown) => { this.busy.set(false); this.notify.error(e); },
    });
  }

  protected upload(ev: Event): void {
    const c = this.c();
    const file = (ev.target as HTMLInputElement).files?.[0];
    if (!c || !file) return;
    const v = this.form.getRawValue();
    const fields: Record<string, string> = { project_id: c.project_id, entity_type: 'FIELD_COLLECTION', entity_id: c.id, evidence_type: 'FIELD_PHOTO',
      description: `Field photo ${c.collection_code}` };
    if (v.gps_latitude !== null && v.gps_longitude !== null) { fields['latitude'] = String(v.gps_latitude); fields['longitude'] = String(v.gps_longitude); }
    runAction(this.api.addEvidence(file, fields), this.uploading, this.notify, 'Photo added.', () => {
      this.tick('photo_taken', true);
      this.loadPhotos(c);
    });
  }

  protected relocate(): void {
    const c = this.c();
    const v = this.form.getRawValue();
    if (!c || v.gps_latitude === null || v.gps_longitude === null) {
      this.notify.error(new Error('Record a GPS position first.'));
      return;
    }
    const reason = v.deviation_note.trim() || window.prompt('Why must the point move?')?.trim();
    if (!reason) return;
    runAction(this.api.requestRelocation(c.sampling_point_id, { latitude: v.gps_latitude, longitude: v.gps_longitude, reason }), this.busy, this.notify,
      'Relocation requested — a supervisor will decide.', () => this.api.point(c.sampling_point_id).subscribe((p) => this.point.set(p)));
  }
}
