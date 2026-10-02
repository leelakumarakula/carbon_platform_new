import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { Router } from '@angular/router';
import { forkJoin } from 'rxjs';

import { ApiError } from '../core/api/api.models';
import { NotifyService } from '../core/notify.service';
import { label } from '../farmer/farmer.models';
import { GeoMap, MapPoint } from '../shared/geo-map';
import { PageHeader } from '../shared/page-header';
import { runAction } from '../shared/run-action';
import { StateView } from '../shared/state-view';
import { StatusBadge } from '../shared/status-badge';
import { MrvApi } from './mrv.api';
import { FieldCollection, SamplingPoint, mrvBadge, pointColor } from './mrv.models';

/** Field collector dashboard (mobile-first): my assigned sampling points and field records. Collectors collect; they never approve. */
@Component({
  selector: 'app-field-dashboard-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatButtonModule, PageHeader, StateView, StatusBadge, GeoMap],
  template: `
    <app-page-header title="Field work" subtitle="Your assigned sampling points" />
    <app-state-view [loading]="loading()" [error]="error()" [empty]="!loading() && !points().length"
                    emptyText="No sampling points are assigned to you." (retry)="load()" />
    @if (points().length) {
      <div class="summary"><span><strong>{{ todo().length }}</strong> to collect</span><span><strong>{{ returned().length }}</strong> returned</span>
        <span><strong>{{ done().length }}</strong> collected</span></div>
      <app-geo-map [points]="mapPoints()" height="240px" />
    }
    @if (returned().length) {
      <h3>Returned for correction</h3>
      @for (c of returned(); track c.id) {
        <div class="card warn"><div class="head"><strong>{{ c.collection_code }}</strong> <app-status-badge status="FAILED" text="Returned" /></div>
          <div class="small">{{ c.point_code }} — {{ c.review_notes }}</div>
          <button mat-flat-button type="button" (click)="open(c.id)">Correct</button></div>
      }
    }
    <h3>To collect</h3>
    @for (p of todo(); track p.id) {
      <div class="card" [attr.data-point]="p.point_code">
        <div class="head"><strong>{{ p.point_code }}</strong><app-status-badge [status]="badge(p.status)" [text]="label(p.status)" />
          @if (p.pending_relocation) { <app-status-badge status="WARNING" text="Relocation pending" /> }</div>
        <div class="small">{{ p.farm_code }} · {{ p.farm_name }} · stratum {{ p.stratum_code }}</div>
        <div class="small">Depth {{ p.planned_depth_top_cm }}–{{ p.planned_depth_bottom_cm }} cm{{ p.planned_date ? ' · planned ' + p.planned_date : '' }}</div>
        <div class="small mono">{{ p.latitude }}, {{ p.longitude }}</div>
        <div class="buttons">
          @if (collectionFor(p); as c) { <button mat-flat-button type="button" (click)="open(c.id)">Continue {{ c.collection_code }}</button> }
          @else { <button mat-flat-button type="button" [disabled]="busy()" (click)="start(p)" data-testid="start-collection">Start collection</button> }
          <a mat-button [href]="navUrl(p)" target="_blank" rel="noopener">Navigate</a>
        </div>
      </div>
    } @empty { @if (points().length) { <p class="muted">All assigned points are collected.</p> } }
    @if (done().length) {
      <h3>Collected</h3>
      @for (c of submittedOrAccepted(); track c.id) {
        <div class="card done"><div class="head"><strong>{{ c.collection_code }}</strong> <app-status-badge [status]="badge(c.status)" [text]="label(c.status)" /></div>
          <div class="small">{{ c.point_code }} · v{{ c.version }}</div>
          <button mat-button type="button" (click)="open(c.id)">View</button></div>
      }
    }
  `,
  styles: `
    .summary { display: flex; gap: 16px; margin: 0 0 12px; flex-wrap: wrap; }
    h3 { margin: 16px 0 8px; font: var(--mat-sys-title-small); }
    .card { border: 1px solid var(--mat-sys-outline-variant); border-radius: 10px; padding: 12px 14px; margin-bottom: 10px; max-width: 640px; }
    .card.warn { border-color: #f1d98e; background: #fffbea; } .card.done { opacity: .85; }
    .head { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 4px; }
    .buttons { display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap; } .buttons button, .buttons a { min-height: 44px; }
    .mono { font-family: monospace; }
  `,
})
export class FieldDashboardPage implements OnInit {
  private readonly api = inject(MrvApi);
  private readonly router = inject(Router);
  private readonly notify = inject(NotifyService);
  protected readonly label = label;
  protected readonly badge = mrvBadge;
  protected readonly points = signal<SamplingPoint[]>([]);
  protected readonly collections = signal<FieldCollection[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<ApiError | null>(null);
  protected readonly busy = signal(false);
  protected readonly todo = computed(() => this.points().filter((p) => p.status === 'ASSIGNED'));
  protected readonly done = computed(() => this.points().filter((p) => p.status === 'COLLECTED'));
  protected readonly returned = computed(() => this.collections().filter((c) => c.status === 'RETURNED'));
  protected readonly submittedOrAccepted = computed(() => this.collections().filter((c) => ['SUBMITTED', 'ACCEPTED'].includes(c.status)));
  protected readonly mapPoints = computed<MapPoint[]>(() =>
    this.points().map((p) => ({ lat: Number(p.latitude), lon: Number(p.longitude), color: pointColor(p), label: p.point_code })));

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.error.set(null);
    forkJoin({ p: this.api.points({ mine: true }), c: this.api.collections({ mine: true }) }).subscribe({
      next: ({ p, c }) => { this.points.set(p); this.collections.set(c); this.loading.set(false); },
      error: (e: unknown) => { this.error.set(ApiError.from(e)); this.loading.set(false); },
    });
  }

  protected collectionFor(p: SamplingPoint): FieldCollection | undefined {
    return this.collections().find((c) => c.sampling_point_id === p.id && ['IN_PROGRESS', 'RETURNED'].includes(c.status));
  }

  protected navUrl(p: SamplingPoint): string {
    return `geo:${p.latitude},${p.longitude}?q=${p.latitude},${p.longitude}(${encodeURIComponent(p.point_code)})`;
  }

  protected start(p: SamplingPoint): void {
    runAction(this.api.startCollection(p.id), this.busy, this.notify, 'Field collection started.', (c) => this.open(c.id));
  }

  protected open(id: string): void {
    void this.router.navigate(['/field/collections', id]);
  }
}
