import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, input, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { ApiError } from '../core/api/api.models';
import { label } from '../farmer/farmer.models';
import { PageHeader } from '../shared/page-header';
import { reloadOn } from '../shared/reload-on';
import { StateView } from '../shared/state-view';
import { StatusBadge } from '../shared/status-badge';
import { LabApi } from './lab.api';
import { Lineage, labBadge, resultValue } from './lab.models';

/** Approved laboratory result with its full lineage (project side). Nothing is calculated from it in Phase 6. */
@Component({
  selector: 'app-lab-result-lineage-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, RouterLink, PageHeader, StateView, StatusBadge],
  template: `
    <app-state-view [loading]="loading()" [error]="error()" (retry)="load()" />
    @if (l(); as l) {
      <app-page-header [title]="l.result.rule_code + ' · ' + value(l.result)" [subtitle]="l.sample.sample_code + ' · ' + l.project.project_code"
                       [backLink]="'/mrv/projects/' + l.project.id" backLabel="MRV workspace" />
      <div class="status-row"><app-status-badge [status]="badge(l.result.status)" [text]="label(l.result.status)" />
        <span class="small muted">Authoritative laboratory result (approved by laboratory QA). Phase 6 produces no calculation.</span></div>
      <ol class="chain" data-testid="lineage">
        <li><strong>Result</strong> v{{ l.result.version }} · {{ value(l.result) }} · analysed {{ l.result.analysed_at | date: 'medium' }} by {{ l.result.analyst_name }}
          · approved {{ l.result.approved_at | date: 'medium' }} by {{ l.result.approved_by_name }}
          @if (l.result.report) { · report {{ l.result.report.file_name }} <span class="mono">SHA-256 {{ l.result.report.sha256?.slice(0, 16) }}…</span> }</li>
        <li><strong>Test</strong> {{ l.test.test_code }} · {{ l.test.laboratory }} · chain {{ l.test.retest_chain.join(' ← ') }}</li>
        <li><strong>Sample</strong> {{ l.sample.sample_code }} (root {{ l.root_sample.sample_code }}) · seal {{ l.sample.seal_number }} · accession {{ l.sample.accession_number }}</li>
        <li><strong>Field collection</strong> {{ l.field_collection.collection_code }} v{{ l.field_collection.version }} ({{ label(l.field_collection.status) }})</li>
        <li><strong>Sampling point</strong> {{ l.sampling_point.point_code }} · {{ l.sampling_point.latitude }}, {{ l.sampling_point.longitude }}</li>
        <li><strong>Stratum</strong> {{ l.stratum ? l.stratum.code + ' v' + l.stratum.version : '—' }}</li>
        <li><strong>Farm</strong> {{ l.farm.farm_code }} · {{ l.farm.name }} (boundary v{{ l.farm.boundary_version }})</li>
        <li><strong>Project</strong> <a [routerLink]="['/projects', l.project.id]">{{ l.project.project_code }}</a> · {{ l.project.name }}</li>
        <li><strong>Methodology</strong> {{ l.methodology.methodology_code }} v{{ l.methodology.version_label }} {{ l.methodology.locked ? '(locked)' : '' }}</li>
        <li><strong>Rule</strong> {{ l.methodology_rule.rule_code }} · {{ l.methodology_rule.parameter }} · {{ l.methodology_rule.unit }} · {{ l.methodology_rule.measurement_source }}</li>
        <li><strong>Plan measurement</strong> {{ l.plan_measurement.code }} ({{ l.plan_measurement.value_type }}) · plan v{{ l.plan_measurement.plan_version }}</li>
      </ol>
      <h3>Versions</h3>
      <ul>@for (v of l.versions; track v.id) { <li>v{{ v.version }} · {{ value(v) }} · {{ label(v.status) }}{{ v.status_reason ? ' — ' + v.status_reason : '' }}</li> }</ul>
      <h3>Shipment & receipt</h3>
      <ul>@for (s of l.shipments; track s.shipment_code) { <li>{{ s.shipment_code }} · dispatched {{ s.dispatched_at | date: 'medium' }} · {{ label(s.receipt_status) }}
        {{ s.received_at | date: 'medium' }} · {{ s.receipt_condition }}</li> }</ul>
      <h3>Laboratory QA</h3>
      <ul>@for (q of l.qa_reviews; track q.id) { <li>{{ q.decision }} by {{ q.reviewer_name }} · {{ q.reviewed_at | date: 'medium' }} — {{ q.notes }}</li> }</ul>
      <h3>Chain of custody</h3>
      <ol>@for (e of l.custody; track e.sequence_no) { <li>{{ label(e.event_type) }} → {{ label(e.to_state) }} · {{ e.occurred_at | date: 'short' }} · {{ e.actor_org_name }}</li> }</ol>
    }
  `,
  styles: `.status-row { display: flex; gap: 8px; align-items: center; margin: -8px 0 12px; } .chain li { margin: 6px 0; }
    h3 { margin: 14px 0 6px; font: var(--mat-sys-title-small); } .mono { font-family: monospace; font-size: 12px; }`,
})
export class LabResultLineagePage {
  readonly id = input.required<string>();
  private readonly api = inject(LabApi);
  protected readonly label = label;
  protected readonly badge = labBadge;
  protected readonly value = resultValue;
  protected readonly l = signal<Lineage | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<ApiError | null>(null);

  constructor() {
    reloadOn(this.id, () => {
      this.l.set(null);
      this.error.set(null);
      this.loading.set(true);
      this.load();
    });
  }

  load(): void {
    this.api.lineage(this.id()).subscribe({
      next: (l) => { this.l.set(l); this.loading.set(false); },
      error: (e: unknown) => { this.error.set(ApiError.from(e)); this.loading.set(false); },
    });
  }
}
