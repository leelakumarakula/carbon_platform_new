import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';

import { ApiError } from '../core/api/api.models';
import { AuthService } from '../core/auth/auth.service';
import { P } from '../core/auth/permissions';
import { NotifyService } from '../core/notify.service';
import { label } from '../farmer/farmer.models';
import { PageHeader } from '../shared/page-header';
import { askReason } from '../shared/reason-dialog';
import { runAction } from '../shared/run-action';
import { StateView } from '../shared/state-view';
import { StatusBadge } from '../shared/status-badge';
import { MrvApi } from './mrv.api';
import { QaView, mrvBadge } from './mrv.models';

/** MRV dataset + QA review. Deterministic checks; PASS → approval (QA officer, never the submitter). Ends at APPROVED. */
@Component({
  selector: 'app-mrv-dataset-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, FormsModule, MatButtonModule, MatFormFieldModule, MatSelectModule, PageHeader, StateView, StatusBadge],
  template: `
    <app-state-view [loading]="loading()" [error]="error()" (retry)="load()" />
    @if (view(); as v) {
      @let d = v.dataset;
      <app-page-header [title]="d.dataset_code" [subtitle]="d.project_code + ' · ' + d.monitoring_period_name + ' · plan v' + d.plan_version + ' · ' + d.methodology_label"
                       [backLink]="'/mrv/projects/' + d.project_id" backLabel="MRV workspace">
        @if (d.allowed_actions.includes('submit') && canManage) {
          <button mat-flat-button type="button" [disabled]="busy()" (click)="dsAction('submit')" data-testid="submit-dataset">Submit for QA</button> }
        @if (v.can_start) { <button mat-flat-button type="button" [disabled]="busy()" (click)="startQa()" data-testid="start-qa">Start QA review</button> }
        @if (v.can_approve) { <button mat-flat-button type="button" [disabled]="busy()" (click)="dsAction('approve')" data-testid="approve-dataset">Approve dataset</button> }
        @if (d.allowed_actions.includes('reject') && canApprove) {
          <button mat-button type="button" class="danger" [disabled]="busy()" (click)="dsAction('reject')">Reject</button> }
      </app-page-header>
      <div class="status-row"><app-status-badge [status]="badge(d.status)" [text]="label(d.status)" />
        @if (d.environment === 'DEMO') { <app-status-badge status="DEMO" /> }</div>
      <div class="detail-grid">
        <dl class="kv">
          <dt>Version</dt><dd>v{{ d.version }}{{ d.supersedes_id ? ' (supersedes an earlier version)' : '' }}</dd>
          <dt>Snapshot</dt><dd>@if (d.snapshot_summary; as s) { @for (e of entries(s); track e[0]) { {{ label(e[0]) }} {{ e[1] }}; } } @else { not frozen yet (frozen on submit) }</dd>
          <dt>SHA-256</dt><dd class="mono">{{ d.snapshot_sha256 ?? '—' }}</dd>
          <dt>Submitted</dt><dd>{{ d.submitted_at ? (d.submitted_at | date: 'medium') : '—' }}</dd>
          <dt>Approved</dt><dd>{{ d.approved_at ? (d.approved_at | date: 'medium') : '—' }}</dd>
          @if (d.status_reason) { <dt>Last decision</dt><dd>{{ d.status_reason }}</dd> }
          @if (d.configuration_gaps.length) { <dt>CONFIGURATION_REQUIRED</dt><dd>{{ d.configuration_gaps.join('; ') }}</dd> }
        </dl>
        <div>
          <h3>QA checks</h3>
          @for (c of v.checks; track c.key) {
            <div class="check" [attr.data-check]="c.key"><app-status-badge [status]="badge(c.result)" [text]="c.result" /> <span>{{ c.label }}</span>
              @if (c.details.length) { <ul class="small">@for (x of c.details.slice(0, 8); track $index) { <li>{{ x }}</li> }</ul> }</div>
          }
          @if (v.can_complete) {
            <div class="complete">
              <mat-form-field subscriptSizing="dynamic"><mat-label>QA result</mat-label>
                <mat-select [(ngModel)]="result" data-testid="qa-result">
                  <mat-option value="PASS">PASS</mat-option><mat-option value="REQUIRES_CORRECTION">REQUIRES_CORRECTION</mat-option><mat-option value="FAIL">FAIL</mat-option>
                </mat-select></mat-form-field>
              <button mat-flat-button type="button" [disabled]="busy()" (click)="completeQa()" data-testid="complete-qa">Record QA result</button>
            </div>
          }
          <h3>QA reviews</h3>
          @for (r of v.reviews; track r.id) {
            <div class="small">{{ r.started_at | date: 'medium' }} — {{ r.result ?? 'in progress' }}{{ r.notes ? ': ' + r.notes : '' }}</div>
          } @empty { <p class="muted small">No QA review yet.</p> }
        </div>
      </div>
      <p class="muted small">MRV ends at an approved dataset. Laboratory results, carbon calculation, verification and credits are not part of this phase.</p>
    }
  `,
  styles: `
    .status-row { display: flex; gap: 6px; margin: -8px 0 12px; } h3 { margin: 12px 0 8px; font: var(--mat-sys-title-small); }
    .check { padding: 4px 0; } .mono { font-family: monospace; font-size: 12px; word-break: break-all; }
    .complete { display: flex; gap: 8px; align-items: center; margin-top: 12px; flex-wrap: wrap; } .danger { color: #b71c1c; }
  `,
})
export class MrvDatasetPage implements OnInit {
  readonly id = input.required<string>();
  private readonly api = inject(MrvApi);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotifyService);
  private readonly auth = inject(AuthService);
  protected readonly canManage = this.auth.has(P.MRV_MANAGE);
  protected readonly canApprove = this.auth.has(P.MRV_APPROVE);
  protected readonly label = label;
  protected readonly badge = mrvBadge;
  protected readonly view = signal<QaView | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<ApiError | null>(null);
  protected readonly busy = signal(false);
  protected result: 'PASS' | 'FAIL' | 'REQUIRES_CORRECTION' = 'PASS';

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.api.qa(this.id()).subscribe({
      next: (v) => { this.view.set(v); this.loading.set(false); },
      error: (e: unknown) => { this.error.set(ApiError.from(e)); this.loading.set(false); },
    });
  }

  protected entries(s: Record<string, number>): [string, number][] {
    return Object.entries(s);
  }

  protected dsAction(action: 'submit' | 'approve' | 'reject'): void {
    const msg = { submit: 'The dataset is frozen (snapshot + SHA-256) and the period moves to SUBMITTED.',
      approve: 'Approved datasets are immutable. You cannot approve a dataset you submitted.', reject: 'The period returns for correction.' }[action];
    askReason(this.dialog, { title: `${label(action)} dataset?`, confirmLabel: label(action), danger: action === 'reject', message: msg }).subscribe((r) => {
      if (r) runAction(this.api.datasetAction(this.id(), action, r.reason), this.busy, this.notify, `Dataset ${label(action).toLowerCase()}ed.`, () => this.load());
    });
  }

  protected startQa(): void {
    runAction(this.api.startQa(this.id()), this.busy, this.notify, 'QA review started.', () => this.load());
  }

  protected completeQa(): void {
    askReason(this.dialog, { title: `Record QA result ${this.result}?`, confirmLabel: 'Record' }).subscribe((r) => {
      if (r) runAction(this.api.completeQa(this.id(), this.result, r.reason), this.busy, this.notify, 'QA result recorded.', () => this.load());
    });
  }
}
