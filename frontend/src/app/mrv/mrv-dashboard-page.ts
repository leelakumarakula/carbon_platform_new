import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { RouterLink } from '@angular/router';

import { ApiError } from '../core/api/api.models';
import { label } from '../farmer/farmer.models';
import { PageHeader } from '../shared/page-header';
import { StateView } from '../shared/state-view';
import { StatusBadge } from '../shared/status-badge';
import { MrvApi } from './mrv.api';
import { MrvProjectSummary, mrvBadge } from './mrv.models';

/** MRV dashboard: projects whose methodology version is locked, with their MRV progress. */
@Component({
  selector: 'app-mrv-dashboard-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, MatButtonModule, PageHeader, StateView, StatusBadge],
  template: `
    <app-page-header title="MRV" subtitle="Monitoring plans, periods, stratification, sampling and field collection" />
    <div class="stats">
      <div class="stat"><span class="n">{{ items().length }}</span><span>projects with a locked methodology</span></div>
      <div class="stat"><span class="n">{{ totals().points }}</span><span>sampling points</span></div>
      <div class="stat"><span class="n">{{ totals().collected }}</span><span>collected</span></div>
      <div class="stat"><span class="n">{{ totals().open }}</span><span>open monitoring periods</span></div>
    </div>
    <app-state-view [loading]="loading()" [error]="error()" [empty]="!loading() && !items().length"
                    emptyText="No project has a locked methodology version yet. MRV starts after the methodology is confirmed." (retry)="load()" />
    <div class="grid">
      @for (p of items(); track p.project_id) {
        <a class="card" [routerLink]="['/mrv/projects', p.project_id]">
          <div class="head"><strong>{{ p.project_code }}</strong>
            @if (p.environment === 'DEMO') { <app-status-badge status="DEMO" /> }
            <app-status-badge [status]="'INFO'" [text]="label(p.project_status)" /></div>
          <div class="name">{{ p.project_name }}</div>
          <div class="muted small">{{ p.organization_name }} · {{ p.methodology_label }}</div>
          <dl class="kv small">
            <dt>MRV plan</dt><dd>{{ p.approved_plan_version ? 'v' + p.approved_plan_version + ' approved' : (p.plan_count ? 'draft' : 'none') }}</dd>
            <dt>Periods</dt><dd>{{ p.period_count }}{{ p.open_period ? ' · open: ' + p.open_period : '' }}</dd>
            <dt>Sampling</dt><dd>{{ p.collected_count }} / {{ p.point_count }} points collected</dd>
            <dt>Dataset</dt><dd>@if (p.dataset_status) { <app-status-badge [status]="badge(p.dataset_status)" [text]="label(p.dataset_status)" /> } @else { — }</dd>
          </dl>
        </a>
      }
    </div>
    <p class="muted small">MRV ends at an approved dataset. Laboratory analysis, calculation, verification and issuance are later phases.</p>
  `,
  styles: `
    .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 16px; }
    .stat { display: flex; flex-direction: column; padding: 12px 16px; border-radius: 8px; background: var(--mat-sys-surface-container); }
    .stat .n { font: var(--mat-sys-headline-small); }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 12px; }
    .card { display: block; padding: 14px 16px; border-radius: 10px; border: 1px solid var(--mat-sys-outline-variant); color: inherit; text-decoration: none; }
    .card:hover { border-color: var(--mat-sys-primary); }
    .head { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; } .name { margin: 4px 0; }
  `,
})
export class MrvDashboardPage implements OnInit {
  private readonly api = inject(MrvApi);
  protected readonly label = label;
  protected readonly badge = mrvBadge;
  protected readonly items = signal<MrvProjectSummary[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<ApiError | null>(null);
  protected readonly totals = computed(() => ({
    points: this.items().reduce((a, p) => a + p.point_count, 0),
    collected: this.items().reduce((a, p) => a + p.collected_count, 0),
    open: this.items().filter((p) => p.open_period).length,
  }));

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.api.projects().subscribe({
      next: (x) => { this.items.set(x); this.loading.set(false); },
      error: (e: unknown) => { this.error.set(ApiError.from(e)); this.loading.set(false); },
    });
  }
}
