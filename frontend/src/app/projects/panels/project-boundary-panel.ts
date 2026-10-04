import { DatePipe, DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, input, output, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';

import { NotifyService } from '../../core/notify.service';
import { label } from '../../farmer/farmer.models';
import { GeoMap, MapLayer } from '../../shared/geo-map';
import { formatArea } from '../../shared/geo';
import { askReason } from '../../shared/reason-dialog';
import { runAction } from '../../shared/run-action';
import { StatusBadge } from '../../shared/status-badge';
import { BoundaryView, Project } from '../project.models';
import { ProjectsApi } from '../projects.api';

/**
 * Project boundary: the union of the participating farms' current boundaries, computed by SQL Server
 * (geography::UnionAggregate; area by STArea, overlaps counted once). The browser only displays it.
 */
@Component({
  selector: 'app-project-boundary-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, DecimalPipe, MatButtonModule, MatIconModule, GeoMap, StatusBadge],
  template: `
    <div class="tab-body">
      @if (view(); as v) {
        <div class="grid">
          <app-geo-map [layers]="layers()" height="420px" />
          <div>
            @if (v.current; as b) {
              <dl class="kv">
                <dt>Project area</dt><dd><strong>{{ area(b.area_hectares) }}</strong>&nbsp;<span class="muted small">(SQL Server, overlaps counted once)</span></dd>
                <dt>Sum of farm areas</dt><dd>{{ area(b.sum_farm_area_hectares) }}</dd>
                <dt>Internal overlap</dt><dd>{{ area(b.internal_overlap_hectares) }}</dd>
                <dt>Farms</dt><dd>{{ b.farm_count }}</dd>
                <dt>Geometry</dt><dd><app-status-badge [status]="b.is_valid ? 'ACTIVE' : 'FAILED'" [text]="b.is_valid ? 'Valid' : 'Invalid'" /></dd>
                <dt>Version</dt><dd>v{{ b.version }} · {{ b.computed_at | date: 'medium' }}</dd>
                <dt>GIS review</dt><dd><app-status-badge [status]="b.review_status === 'ACCEPTED' ? 'ACTIVE' : b.review_status === 'ISSUES' ? 'FAILED' : 'WARNING'"
                  [text]="label(b.review_status)" />@if (b.review_notes) { <div class="muted small">{{ b.review_notes }}</div> }</dd>
              </dl>
              @if (b.validation_notes) { <p class="note">{{ b.validation_notes }}</p> }
            } @else { <p class="muted">No boundary yet — it is derived automatically when farms are added.</p> }
            @if (v.stale) { <p class="note warn" role="alert">Farm boundaries changed since this version was computed. Recompute before review.</p> }
            <div class="actions">
              @if (v.can_recompute) { <button mat-stroked-button type="button" (click)="recompute()" [disabled]="busy()"><mat-icon>refresh</mat-icon> Recompute</button> }
              @if (v.can_review && v.current && !v.stale) {
                <button mat-flat-button type="button" (click)="review('ACCEPTED')" [disabled]="busy()">Accept boundary</button>
                <button mat-button type="button" class="danger" (click)="review('ISSUES')" [disabled]="busy()">Report issues</button>
              }
            </div>
            <h4>Overlaps with other projects</h4>
            @for (o of v.project_overlaps; track $index) {
              <div class="muted small">{{ o.other_project_visible ? o.other_project_code : 'A project of another organization (details restricted)' }}
                · {{ o.overlap_area_m2 | number: '1.0-0' }} m² — flagged for review, not rejected</div>
            } @empty { <div class="muted small">None.</div> }
          </div>
        </div>
        <h4>Versions</h4>
        <div class="table-wrap">
          <table class="simple">
            <thead><tr><th>Version</th><th>Status</th><th>Area</th><th>Farms</th><th>Computed</th><th>Review</th></tr></thead>
            <tbody>@for (b of v.versions; track b.id) {
              <tr><td>v{{ b.version }}</td><td>{{ label(b.status) }}</td><td>{{ area(b.area_hectares) }}</td><td>{{ b.farm_count }}</td>
                <td>{{ b.computed_at | date: 'short' }}</td><td>{{ label(b.review_status) }}</td></tr>
            }</tbody>
          </table>
        </div>
      }
    </div>
  `,
  styles: `
    .grid { display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); gap: 20px; }
    @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
    .note { padding: 8px 10px; border-radius: 8px; background: var(--mat-sys-surface-container); font-size: 13px; white-space: pre-line; }
    .note.warn { background: #fff3e0; color: #e65100; } .actions { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0; }
    h4 { margin: 16px 0 6px; font: var(--mat-sys-title-small); }
    table.simple { width: 100%; border-collapse: collapse; }
    table.simple th, table.simple td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--mat-sys-outline-variant); }
  `,
})
export class ProjectBoundaryPanel implements OnInit {
  readonly project = input.required<Project>();
  readonly changed = output<void>();
  private readonly api = inject(ProjectsApi);
  private readonly notify = inject(NotifyService);
  private readonly dialog = inject(MatDialog);
  protected readonly label = label;
  protected readonly area = formatArea;
  protected readonly view = signal<BoundaryView | null>(null);
  protected readonly busy = signal(false);
  protected readonly layers = computed<MapLayer[]>(() => {
    const v = this.view();
    if (!v) return [];
    const out: MapLayer[] = v.farms.map((f) => ({ geojson: f.geojson, color: f.open_overlaps ? '#c62828' : '#1565c0', dashed: true, fillOpacity: 0.05,
      label: `${f.farm_code} · ${f.farm_name}${f.open_overlaps ? ' · open overlap' : ''}` }));
    if (v.current) out.unshift({ geojson: v.current.geojson, color: '#2e7d32', fillOpacity: 0.2, label: `Project boundary v${v.current.version}` });
    return out;
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.api.boundary(this.project().id).subscribe((v) => this.view.set(v));
  }

  recompute(): void {
    runAction(this.api.recomputeBoundary(this.project().id), this.busy, this.notify, 'Boundary recomputed.', (v) => {
      this.view.set(v);
      this.changed.emit();
    });
  }

  review(decision: 'ACCEPTED' | 'ISSUES'): void {
    askReason(this.dialog, { title: decision === 'ACCEPTED' ? 'Accept the project boundary?' : 'Report boundary issues?',
      confirmLabel: decision === 'ACCEPTED' ? 'Accept' : 'Report issues', danger: decision === 'ISSUES' }).subscribe((r) => {
      if (r) runAction(this.api.reviewBoundary(this.project().id, decision, r.reason), this.busy, this.notify, 'GIS review recorded.', (v) => {
        this.view.set(v);
        this.changed.emit();
      });
    });
  }
}
