import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, input, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { RouterLink } from '@angular/router';

import { ApiError } from '../core/api/api.models';
import { label } from '../farmer/farmer.models';
import { PageHeader } from '../shared/page-header';
import { reloadOn } from '../shared/reload-on';
import { StateView } from '../shared/state-view';
import { StatusBadge } from '../shared/status-badge';
import { LabApi } from './lab.api';
import { SampleDetail, labBadge, resultValue } from './lab.models';

/** Project-side sample detail: lineage, custody timeline, tests and (non-draft) results. */
@Component({
  selector: 'app-sample-detail-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, RouterLink, MatButtonModule, PageHeader, StateView, StatusBadge],
  template: `
    <app-state-view [loading]="loading()" [error]="error()" (retry)="load()" />
    @if (s(); as s) {
      <app-page-header [title]="s.sample_code" [subtitle]="s.project_code + ' · ' + s.laboratory_org_name" [backLink]="'/mrv/projects/' + s.project_id"
                       backLabel="MRV workspace" />
      <div class="status-row"><app-status-badge [status]="badge(s.status)" [text]="label(s.status)" />
        @if (s.environment === 'DEMO') { <app-status-badge status="DEMO" /> }</div>
      <div class="detail-grid">
        <dl class="kv">
          <dt>Root / parent</dt><dd>{{ s.root_sample_code }}{{ s.parent_sample_code ? ' / ' + s.parent_sample_code : '' }}</dd>
          <dt>Field record</dt><dd>{{ s.field_collection_code }} v{{ s.field_collection_version }} ({{ label(s.field_collection_status) }}) — never re-pointed</dd>
          <dt>Point · farm</dt><dd>{{ s.sampling_point_code }} · {{ s.farm_code }}</dd>
          <dt>Description</dt><dd>{{ s.description }}</dd>
          <dt>Depth</dt><dd>{{ s.depth_top_cm }}–{{ s.depth_bottom_cm }} cm</dd>
          <dt>Quantity</dt><dd>{{ s.quantity ?? '—' }} {{ s.quantity_unit ?? '' }}</dd>
          <dt>Container · seal</dt><dd>{{ s.container_label ?? '—' }} · {{ s.seal_number ?? 'not sealed' }}</dd>
          <dt>Lab accession</dt><dd>{{ s.accession_number ?? '—' }}</dd>
          <dt>Registered</dt><dd>{{ s.registered_by_name }} · {{ s.registered_at | date: 'medium' }}</dd>
          <dt>Shipments</dt><dd>{{ s.shipments.join(', ') || '—' }}</dd>
        </dl>
        <div>
          <h3>Tests</h3>
          @for (t of s.tests; track t.id) {
            <div class="test"><strong>{{ t.test_code }}</strong> · {{ t.rule.rule_code }} {{ t.rule.parameter }}
              <app-status-badge [status]="badge(t.status)" [text]="label(t.status)" />
              @if (t.retest_of_test_code) { <span class="small muted">retest of {{ t.retest_of_test_code }}: {{ t.retest_reason }}</span> }
              @for (r of t.results; track r.id) {
                <div class="small">v{{ r.version }} · {{ value(r) }} · <app-status-badge [status]="badge(r.status)" [text]="label(r.status)" />
                  @if (r.status === 'APPROVED') { <a mat-button [routerLink]="['/mrv/lab-results', r.id]">Lineage</a> }</div>
              } @empty { <div class="small muted">No submitted result yet.</div> }
            </div>
          }
        </div>
      </div>
      <h3>Chain of custody</h3>
      <ol class="timeline">
        @for (e of s.custody; track e.sequence_no) {
          <li><strong>{{ e.sequence_no }}. {{ label(e.event_type) }}</strong> {{ e.from_state ? label(e.from_state) + ' → ' : '' }}{{ label(e.to_state) }}
            <span class="small muted"> · {{ e.occurred_at | date: 'medium' }} · {{ e.actor_name }} ({{ e.actor_org_name }}{{ e.actor_role ? ', ' + label(e.actor_role) : '' }})
              {{ e.seal_number ? '· seal ' + e.seal_number : '' }}{{ e.shipment_code ? ' · ' + e.shipment_code : '' }}</span>
            @if (e.reason) { <div class="small">{{ e.reason }}</div> }</li>
        }
      </ol>
    }
  `,
  styles: `.status-row { display: flex; gap: 6px; margin: -8px 0 12px; } h3 { margin: 12px 0 8px; font: var(--mat-sys-title-small); }
    .test { padding: 6px 0; border-bottom: 1px solid var(--mat-sys-outline-variant); } .timeline { padding-left: 20px; } .timeline li { margin: 4px 0; }`,
})
export class SampleDetailPage {
  readonly id = input.required<string>();
  private readonly api = inject(LabApi);
  protected readonly label = label;
  protected readonly badge = labBadge;
  protected readonly value = resultValue;
  protected readonly s = signal<SampleDetail | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<ApiError | null>(null);

  constructor() {
    reloadOn(this.id, () => {
      this.s.set(null);
      this.error.set(null);
      this.loading.set(true);
      this.load();
    });
  }

  load(): void {
    this.api.sample(this.id()).subscribe({
      next: (s) => { this.s.set(s); this.loading.set(false); },
      error: (e: unknown) => { this.error.set(ApiError.from(e)); this.loading.set(false); },
    });
  }
}
