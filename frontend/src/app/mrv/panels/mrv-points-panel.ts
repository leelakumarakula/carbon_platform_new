import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, effect, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { forkJoin } from 'rxjs';

import { NotifyService } from '../../core/notify.service';
import { label } from '../../farmer/farmer.models';
import { GeoMap, MapLayer, MapPoint } from '../../shared/geo-map';
import { askReason } from '../../shared/reason-dialog';
import { runAction } from '../../shared/run-action';
import { StatusBadge } from '../../shared/status-badge';
import { MrvApi } from '../mrv.api';
import { Collector, FieldCollection, Period, Relocation, SamplingPoint, Stratum, mrvBadge, pointColor } from '../mrv.models';

/** Sampling-point map, assignment to field collectors, relocation decisions and review of submitted field records. */
@Component({
  selector: 'app-mrv-points-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, FormsModule, MatButtonModule, MatCheckboxModule, MatFormFieldModule, MatInputModule, MatSelectModule, StatusBadge, GeoMap],
  template: `
    <div class="tab-body">
      @if (!period()) { <p class="muted">Create a monitoring period first.</p> }
      <app-geo-map [layers]="layers()" [points]="mapPoints()" height="380px" />
      <p class="muted small legend"><span style="color:#e65100">●</span> planned <span style="color:#1565c0">●</span> assigned
        <span style="color:#2e7d32">●</span> collected <span style="color:#9e9e9e">●</span> skipped — locations validated inside the farm boundaries by SQL Server.</p>
      @if (canAssign() && points().length) {
        <div class="assign">
          <mat-form-field subscriptSizing="dynamic"><mat-label>Field collector</mat-label>
            <mat-select [(ngModel)]="collectorId" data-testid="collector">
              @for (c of collectors(); track c.id) { <mat-option [value]="c.id">{{ c.full_name }} · {{ c.email }}</mat-option> }
            </mat-select></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Planned date</mat-label><input matInput type="date" [(ngModel)]="plannedDate" /></mat-form-field>
          <button mat-flat-button type="button" [disabled]="busy() || !collectorId || !selected().size" (click)="assign()" data-testid="assign">
            Assign {{ selected().size }} point(s)</button>
          <button mat-button type="button" (click)="selectUnassigned()">Select unassigned</button>
        </div>
      }
      <div class="table-wrap"><table class="table">
        <thead><tr><th></th><th>Point</th><th>Stratum</th><th>Farm</th><th>Lat, lon</th><th>Depth</th><th>Status</th><th>Collector</th><th>Field record</th><th></th></tr></thead>
        <tbody>
          @for (p of points(); track p.id) {
            <tr>
              <td>@if (canAssign() && ['PLANNED', 'ASSIGNED'].includes(p.status)) { <mat-checkbox [checked]="selected().has(p.id)" (change)="toggle(p.id)" /> }</td>
              <td>{{ p.point_code }}</td><td>{{ p.stratum_code }}</td><td>{{ p.farm_code }}</td>
              <td class="mono">{{ p.latitude }}, {{ p.longitude }}</td><td>{{ p.planned_depth_top_cm }}–{{ p.planned_depth_bottom_cm }} cm</td>
              <td><app-status-badge [status]="badge(p.status)" [text]="label(p.status)" />
                @if (p.pending_relocation) { <app-status-badge status="WARNING" text="Relocation pending" /> }</td>
              <td>{{ p.assigned_collector_name ?? '—' }}{{ p.planned_date ? ' · ' + p.planned_date : '' }}</td>
              <td>{{ p.collection_status ? label(p.collection_status) : '—' }}</td>
              <td>@if (canReview() && ['PLANNED', 'ASSIGNED'].includes(p.status)) { <button mat-button type="button" (click)="skip(p)">Skip</button> }</td>
            </tr>
          } @empty { <tr><td colspan="10" class="muted">No sampling points yet — approve a sampling design and generate them.</td></tr> }
        </tbody>
      </table></div>

      @if (canReview()) {
        <h3>Relocation requests</h3>
        @for (r of pending(); track r.id) {
          <div class="line"><div class="grow small">{{ pointCode(r.sampling_point_id) }}: {{ r.old_latitude }}, {{ r.old_longitude }} → {{ r.new_latitude }}, {{ r.new_longitude }}
            ({{ r.distance_m }} m) — {{ r.reason }}</div>
            <button mat-stroked-button type="button" [disabled]="busy()" (click)="decide(r, 'APPROVED')">Approve</button>
            <button mat-button type="button" [disabled]="busy()" (click)="decide(r, 'REJECTED')">Reject</button></div>
        } @empty { <p class="muted small">No pending relocation request.</p> }

        <h3>Submitted field records</h3>
        @for (c of submitted(); track c.id) {
          <div class="line"><div class="grow small"><strong>{{ c.collection_code }}</strong> · {{ c.point_code }} · {{ c.collector_name }} ·
            {{ c.collected_at | date: 'medium' }} · depth {{ c.actual_depth_top_cm }}–{{ c.actual_depth_bottom_cm }} cm ·
            GPS {{ c.distance_from_point_m ?? '?' }} m from point{{ c.gps_inside_farm === false ? ', outside the farm' : '' }} · {{ c.evidence_count }} photo(s)
            @if (c.deviation_note) { <div class="muted">Deviation: {{ c.deviation_note }}</div> }</div>
            @if (c.can_review) {
              <button mat-stroked-button type="button" [disabled]="busy()" (click)="review(c, 'ACCEPTED')" data-testid="accept">Accept</button>
              <button mat-button type="button" [disabled]="busy()" (click)="review(c, 'RETURNED')">Return</button>
            } @else { <span class="muted small">You collected it — another reviewer decides.</span> }
          </div>
        } @empty { <p class="muted small">Nothing waiting for review.</p> }
      }
    </div>
  `,
  styles: `
    .assign { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin: 8px 0; } .mono { font-family: monospace; font-size: 12px; }
    h3 { margin: 16px 0 8px; font: var(--mat-sys-title-small); } .legend { margin: 4px 0 8px; }
    .line { display: flex; gap: 8px; align-items: center; padding: 6px 0; border-bottom: 1px solid var(--mat-sys-outline-variant); flex-wrap: wrap; } .grow { flex: 1; min-width: 240px; }
  `,
})
export class MrvPointsPanel {
  readonly projectId = input.required<string>();
  readonly period = input<Period | null>(null);
  readonly strata = input<Stratum[]>([]);
  readonly canAssign = input(false);
  readonly canReview = input(false);
  private readonly api = inject(MrvApi);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotifyService);
  protected readonly label = label;
  protected readonly badge = mrvBadge;
  protected readonly busy = signal(false);
  protected readonly points = signal<SamplingPoint[]>([]);
  protected readonly collections = signal<FieldCollection[]>([]);
  protected readonly relocations = signal<Relocation[]>([]);
  protected readonly collectors = signal<Collector[]>([]);
  protected readonly selected = signal(new Set<string>());
  protected collectorId = '';
  protected plannedDate = '';
  protected readonly pending = computed(() => this.relocations().filter((r) => r.status === 'PENDING'));
  protected readonly submitted = computed(() => this.collections().filter((c) => c.status === 'SUBMITTED'));
  protected readonly layers = computed<MapLayer[]>(() =>
    this.strata().filter((s) => s.geojson && s.is_current).map((s) => ({ geojson: s.geojson!, color: '#607d8b', label: s.code, fillOpacity: 0.08 })));
  protected readonly mapPoints = computed<MapPoint[]>(() => this.points().filter((p) => p.status !== 'CANCELLED')
    .map((p) => ({ lat: Number(p.latitude), lon: Number(p.longitude), color: pointColor(p), label: `${p.point_code} · ${p.status}` })));

  constructor() {
    effect(() => {
      const p = this.period();
      if (p) this.load(p.id);
    });
    effect(() => {
      if (this.canAssign()) this.api.collectors(this.projectId()).subscribe((c) => this.collectors.set(c));
    });
  }

  private load(periodId: string): void {
    this.api.points({ monitoring_period_id: periodId }).subscribe((pts) => {
      this.points.set(pts.filter((p) => p.status !== 'CANCELLED'));
      this.selected.set(new Set());
      const withRequests = pts.filter((p) => p.pending_relocation);
      if (withRequests.length && this.canReview()) {
        forkJoin(withRequests.map((p) => this.api.relocations(p.id))).subscribe((rs) => this.relocations.set(rs.flat()));
      } else this.relocations.set([]);
    });
    this.api.collections({ monitoring_period_id: periodId }).subscribe((c) => this.collections.set(c));
  }

  private reload(): void {
    const p = this.period();
    if (p) this.load(p.id);
  }

  protected pointCode(id: string): string {
    return this.points().find((p) => p.id === id)?.point_code ?? id;
  }

  protected toggle(id: string): void {
    const s = new Set(this.selected());
    if (s.has(id)) s.delete(id);
    else s.add(id);
    this.selected.set(s);
  }

  protected selectUnassigned(): void {
    this.selected.set(new Set(this.points().filter((p) => p.status === 'PLANNED').map((p) => p.id)));
  }

  protected assign(): void {
    runAction(this.api.bulkAssign({ point_ids: [...this.selected()], collector_id: this.collectorId, planned_date: this.plannedDate || null }),
      this.busy, this.notify, 'Points assigned.', () => this.reload());
  }

  protected skip(p: SamplingPoint): void {
    askReason(this.dialog, { title: `Skip ${p.point_code}?`, confirmLabel: 'Skip point', danger: true,
      message: 'Skipped points stay in the record with the reason; QA reports them.' }).subscribe((r) => {
      if (r) runAction(this.api.skip(p.id, r.reason), this.busy, this.notify, 'Point skipped.', () => this.reload());
    });
  }

  protected decide(r: Relocation, decision: 'APPROVED' | 'REJECTED'): void {
    askReason(this.dialog, { title: `${decision === 'APPROVED' ? 'Approve' : 'Reject'} relocation?`, confirmLabel: label(decision) }).subscribe((x) => {
      if (x) runAction(this.api.decideRelocation(r.id, decision, x.reason), this.busy, this.notify, `Relocation ${label(decision).toLowerCase()}.`,
        () => this.reload());
    });
  }

  protected review(c: FieldCollection, decision: 'ACCEPTED' | 'RETURNED'): void {
    askReason(this.dialog, { title: `${decision === 'ACCEPTED' ? 'Accept' : 'Return'} ${c.collection_code}?`, confirmLabel: label(decision) }).subscribe((x) => {
      if (x) runAction(this.api.reviewCollection(c.id, decision, x.reason), this.busy, this.notify, `Field record ${label(decision).toLowerCase()}.`,
        () => this.reload());
    });
  }
}
