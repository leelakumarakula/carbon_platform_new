import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, inject, input, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';

import { ApiError } from '../core/api/api.models';
import { NotifyService } from '../core/notify.service';
import { label } from '../farmer/farmer.models';
import { PageHeader } from '../shared/page-header';
import { askReason } from '../shared/reason-dialog';
import { runAction } from '../shared/run-action';
import { StateView } from '../shared/state-view';
import { StatusBadge } from '../shared/status-badge';
import { MrvApi } from './mrv.api';
import { Plan, mrvBadge } from './mrv.models';

/** MRV plan detail: submit (manager), approve / return (QA, never the submitter). An approved plan is never edited. */
@Component({
  selector: 'app-mrv-plan-detail-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, MatButtonModule, PageHeader, StateView, StatusBadge],
  template: `
    <app-state-view [loading]="loading()" [error]="error()" (retry)="load()" />
    @if (plan(); as p) {
      <app-page-header [title]="'MRV plan v' + p.plan_version" [subtitle]="p.project_code + ' · ' + p.methodology_label"
                       [backLink]="'/mrv/projects/' + p.project_id" backLabel="MRV workspace">
        @if (p.can_submit) { <button mat-flat-button type="button" [disabled]="busy()" (click)="act('submit')" data-testid="submit-plan">Submit for approval</button> }
        @if (p.status === 'DRAFT' && p.can_submit) { <button mat-button type="button" [disabled]="busy()" (click)="act('withdraw')">Withdraw</button> }
        @if (p.can_approve) {
          <button mat-flat-button type="button" [disabled]="busy()" (click)="act('approve')" data-testid="approve-plan">Approve</button>
          <button mat-button type="button" [disabled]="busy()" (click)="act('return')">Return</button>
        }
      </app-page-header>
      <div class="status-row"><app-status-badge [status]="badge(p.status)" [text]="label(p.status)" />
        <app-status-badge [status]="badge(p.configuration_status)" [text]="label(p.configuration_status)" /></div>
      @if (p.approval_blockers.length) {
        <div class="note bad" data-testid="production-block"><strong>Production approval blocked (CONFIGURATION_REQUIRED).</strong>
          Platform governance rule: in production a plan is approved only when every required MRV, sampling, monitoring and evidence
          requirement is configured. <ul>@for (b of p.approval_blockers; track b) { <li>{{ b }}</li> }</ul></div>
      }
      @if (p.configuration_gaps.length) {
        <div class="note warn"><strong>CONFIGURATION_REQUIRED</strong> — not configured by the methodology version:
          <ul>@for (g of p.configuration_gaps; track g) { <li>{{ g }}</li> }</ul>
          @if (p.gap_approval_policy === 'ACKNOWLEDGE_ALLOWED') { DEMO / non-production: approval requires explicitly acknowledging these gaps
            (audited). } Nothing is invented by the platform.</div>
      }
      <div class="detail-grid">
        <dl class="kv">
          <dt>Methodology version</dt><dd>{{ p.methodology_label }} (locked)</dd>
          <dt>Quantification</dt><dd>{{ label(p.quantification_approach) }} <span class="muted small">(no calculation in this phase)</span></dd>
          <dt>Frequency</dt><dd>{{ p.monitoring_frequency ?? '—' }}</dd>
          <dt>Window</dt><dd>{{ p.monitoring_start ?? '—' }} → {{ p.monitoring_end ?? '—' }}</dd>
          <dt>Sampling requirements</dt><dd>{{ p.sampling_requirements_ref ?? '—' }}</dd>
          <dt>Required evidence</dt><dd>{{ p.required_evidence ?? '—' }}</dd>
          <dt>Submitted</dt><dd>{{ p.submitted_at ? (p.submitted_at | date: 'medium') : '—' }}</dd>
          <dt>Approved</dt><dd>{{ p.approved_at ? (p.approved_at | date: 'medium') : '—' }}</dd>
          @if (p.status_reason) { <dt>Last decision</dt><dd>{{ p.status_reason }}</dd> }
        </dl>
        <div>
          <h3>Measurements ({{ p.measurements.length }})</h3>
          <div class="table-wrap"><table class="table">
            <thead><tr><th>Code</th><th>Name</th><th>Type</th><th>Level</th><th>Source</th></tr></thead>
            <tbody>@for (m of p.measurements; track m.id) {
              <tr><td>{{ m.code }}</td><td>{{ m.name }}{{ m.unit ? ' (' + m.unit + ')' : '' }}{{ m.required ? '' : ' · optional' }}</td>
                <td>{{ label(m.value_type) }}{{ m.allowed_values ? ': ' + m.allowed_values.join(' / ') : '' }}</td><td>{{ label(m.level) }}</td><td>{{ label(m.source) }}</td></tr>
            }</tbody>
          </table></div>
        </div>
      </div>
    }
  `,
  styles: `.status-row { display: flex; gap: 6px; margin: -8px 0 12px; } h3 { margin: 0 0 8px; font: var(--mat-sys-title-small); }`,
})
export class MrvPlanDetailPage implements OnInit {
  readonly id = input.required<string>();
  private readonly api = inject(MrvApi);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotifyService);
  protected readonly label = label;
  protected readonly badge = mrvBadge;
  protected readonly plan = signal<Plan | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<ApiError | null>(null);
  protected readonly busy = signal(false);

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.api.plan(this.id()).subscribe({
      next: (p) => { this.plan.set(p); this.loading.set(false); },
      error: (e: unknown) => { this.error.set(ApiError.from(e)); this.loading.set(false); },
    });
  }

  protected act(action: 'submit' | 'approve' | 'return' | 'withdraw'): void {
    const p = this.plan();
    if (!p) return;
    const gaps = action === 'approve' && p.configuration_gaps.length > 0;
    askReason(this.dialog, { title: `${label(action)} MRV plan v${p.plan_version}?`, confirmLabel: label(action), danger: action === 'withdraw',
      message: gaps ? 'By approving you acknowledge the CONFIGURATION_REQUIRED gaps listed on this page (recorded in the audit log).' : undefined })
      .subscribe((r) => {
        if (r) runAction(this.api.planAction(p.id, action, r.reason, gaps), this.busy, this.notify, `Plan ${label(action).toLowerCase()}ed.`,
          (x) => this.plan.set(x));
      });
  }
}
