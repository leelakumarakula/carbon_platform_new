import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { Observable } from 'rxjs';

import { AuthService } from '../../core/auth/auth.service';
import { NotifyService } from '../../core/notify.service';
import { label } from '../../farmer/farmer.models';
import { PageHeader } from '../../shared/page-header';
import { askReason } from '../../shared/reason-dialog';
import { runAction } from '../../shared/run-action';
import { StatusBadge } from '../../shared/status-badge';
import { Job, JobAttempt, JobsApi, JobsStatus, TaskSpec, jobBadge } from './jobs.api';

const STATUSES = ['QUEUED', 'CLAIMED', 'RUNNING', 'RETRY_WAITING', 'SUCCEEDED', 'FAILED', 'CANCELLED'];

/** Administration → Background jobs (Phase 12A). Read-only operations view of the SQL Server job records of the caller's environment,
 *  with audited retry (FAILED) and cancel (QUEUED) for jobs.manage. There is deliberately no control to run an arbitrary task, and no
 *  stack trace is shown: errors are a code and a sanitized message. */
@Component({
  selector: 'app-jobs-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, FormsModule, MatButtonModule, MatFormFieldModule, MatSelectModule, PageHeader, StatusBadge],
  template: `
    <app-page-header title="Background jobs" subtitle="Scheduled maintenance work recorded in SQL Server (Redis only transports job ids)" />
    @if (status(); as s) {
      <section class="box" data-testid="jobs-status">
        @if (s.environment === 'DEMO') { <p class="note warn" data-testid="jobs-demo-note">{{ s.note }}</p> }
        <div class="figs">
          <div class="fig">Database<b>{{ s.database }}</b></div>
          <div class="fig">Broker (Redis)<b data-testid="jobs-broker">{{ label(s.broker) }}</b></div>
          <div class="fig">Workers<b data-testid="jobs-worker">{{ s.worker_alive ? 'Heartbeat received' : 'No heartbeat' }}</b></div>
          <div class="fig">Queued<b>{{ s.counts['QUEUED'] || 0 }}</b></div>
          <div class="fig">Retry waiting<b>{{ s.counts['RETRY_WAITING'] || 0 }}</b></div>
          <div class="fig">Failed<b data-testid="jobs-failed-count">{{ s.counts['FAILED'] || 0 }}</b></div>
          <div class="fig">Last scheduled<b>{{ s.last_scheduled_at ? (s.last_scheduled_at | date: 'short') : '—' }}</b></div>
        </div>
        @if (s.environment !== 'DEMO') { <p class="small muted">{{ s.note }}</p> }
        <p class="small muted">A reachable broker does not mean a worker is running. If workers or Redis are down, jobs stay queued and
          lazy expiry keeps every workflow correct.</p>
      </section>
    }
    <div class="row">
      <mat-form-field subscriptSizing="dynamic"><mat-label>Status</mat-label>
        <mat-select [(ngModel)]="statusFilter" (ngModelChange)="reload()"><mat-option value="">All</mat-option>
          @for (s of statuses; track s) { <mat-option [value]="s">{{ label(s) }}</mat-option> }</mat-select></mat-form-field>
      <mat-form-field subscriptSizing="dynamic"><mat-label>Task</mat-label>
        <mat-select [(ngModel)]="typeFilter" (ngModelChange)="reload()"><mat-option value="">All</mat-option>
          @for (t of registry(); track t.job_type) { <mat-option [value]="t.job_type">{{ t.job_type }}</mat-option> }</mat-select></mat-form-field>
    </div>
    <div class="table-wrap"><table class="table" data-testid="jobs">
      <thead><tr><th>Job</th><th>Task</th><th>Status</th><th>Queue</th><th>Created</th><th>Started</th><th>Completed</th><th>Retries</th><th>Last error</th><th>Env.</th><th></th></tr></thead>
      <tbody>
        @for (j of jobs(); track j.id) {
          <tr [attr.data-job]="j.job_code" [class.sel]="detail()?.id === j.id">
            <td><a href="" (click)="$event.preventDefault(); open(j)">{{ j.job_code }}</a><div class="small muted">{{ label(j.trigger_type) }}</div></td>
            <td>{{ j.job_type }}</td><td><app-status-badge [status]="badge(j.status)" [text]="label(j.status)" /></td><td>{{ j.queue_name }}</td>
            <td>{{ j.created_at | date: 'short' }}</td><td>{{ j.started_at ? (j.started_at | date: 'short') : '—' }}</td>
            <td>{{ j.completed_at ? (j.completed_at | date: 'short') : '—' }}</td><td>{{ j.retry_count }} / {{ j.max_retries }}</td>
            <td class="small">{{ j.error_code ?? (j.status === 'QUEUED' ? j.last_publish_error : null) ?? '—' }}</td><td>{{ j.environment }}</td>
            <td>@if (j.can_retry) { <button mat-button type="button" [disabled]="busy()" (click)="retry(j)">Retry</button> }
              @if (j.can_cancel) { <button mat-button type="button" [disabled]="busy()" (click)="cancel(j)">Cancel</button> }</td></tr>
        } @empty { <tr><td colspan="11" class="muted" data-testid="no-jobs">No background job.</td></tr> }
      </tbody>
    </table></div>
    @if (detail(); as d) {
      <section class="box" data-testid="job-detail"><h3>{{ d.job_code }} — {{ label(d.status) }}</h3>
        <p class="small">{{ d.task_name }} · queue {{ d.queue_name }} · {{ d.environment }} · created by {{ d.created_by_name }}
          @if (d.claimed_by) { · worker {{ d.claimed_by }} }</p>
        @if (d.error_message) { <p class="note bad">{{ d.error_code }}: {{ d.error_message }}</p> }
        @if (d.last_publish_error && d.status === 'QUEUED') { <p class="note warn">Not yet handed to the broker ({{ d.last_publish_error }}); the recovery tick republishes it.</p> }
        @if (d.reason) { <p class="small">Reason: {{ d.reason }}</p> }
        @if (d.result) { <p class="small" data-testid="job-result">Result: {{ summary(d.result) }}</p> }
        <h3>Attempts</h3>
        <div class="table-wrap"><table class="table" data-testid="job-attempts">
          <thead><tr><th>#</th><th>Worker</th><th>Status</th><th>Started</th><th>Finished</th><th>Duration</th><th>Error</th><th>Actor</th></tr></thead>
          <tbody>@for (a of attempts(); track a.id) {
            <tr><td>{{ a.attempt_number }}</td><td class="small">{{ a.worker_identity }}</td>
              <td><app-status-badge [status]="badge(a.status)" [text]="label(a.status)" /></td><td>{{ a.started_at | date: 'medium' }}</td>
              <td>{{ a.finished_at ? (a.finished_at | date: 'medium') : '—' }}</td><td>{{ a.duration_ms ?? '—' }} ms</td>
              <td class="small">{{ a.error_code ?? '—' }}</td><td class="small">{{ a.system_actor_name }}</td></tr>
          } @empty { <tr><td colspan="8" class="muted">Not executed yet.</td></tr> }</tbody></table></div>
      </section>
    }
    <h3>Allow-listed tasks</h3>
    <div class="table-wrap"><table class="table" data-testid="job-registry">
      <thead><tr><th>Task</th><th>What it does</th><th>Schedule</th><th>Retries</th><th>Idempotency</th></tr></thead>
      <tbody>@for (t of registry(); track t.job_type) {
        <tr><td>{{ t.job_type }}<div class="small muted">{{ t.task_name }}</div></td><td class="small">{{ t.description }}</td>
          <td>{{ every(t.scheduled_every_seconds) }}</td><td>{{ t.max_retries }}</td><td class="small">{{ t.idempotency }}</td></tr>
      }</tbody></table></div>
  `,
  styles: `.box { border: 1px solid var(--mat-sys-outline-variant); border-radius: 8px; padding: 10px 12px; margin: 10px 0; }
    .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin: 8px 0; } h3 { margin: 12px 0 8px; font: var(--mat-sys-title-small); }
    .figs { display: flex; gap: 16px; flex-wrap: wrap; } .fig { min-width: 120px; } .fig b { display: block; font-size: 15px; }
    tr.sel { background: var(--mat-sys-surface-container); }`,
})
export class JobsPage implements OnInit {
  private readonly api = inject(JobsApi);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotifyService);
  protected readonly auth = inject(AuthService);
  protected readonly label = label;
  protected readonly badge = jobBadge;
  protected readonly statuses = STATUSES;
  protected readonly status = signal<JobsStatus | null>(null);
  protected readonly registry = signal<TaskSpec[]>([]);
  protected readonly jobs = signal<Job[]>([]);
  protected readonly detail = signal<Job | null>(null);
  protected readonly attempts = signal<JobAttempt[]>([]);
  protected readonly busy = signal(false);
  protected statusFilter = '';
  protected typeFilter = '';

  ngOnInit(): void {
    this.api.registry().subscribe((r) => this.registry.set(r));
    this.reload();
  }

  reload(): void {
    this.api.status().subscribe((s) => this.status.set(s));
    this.api.list(this.statusFilter, this.typeFilter).subscribe((j) => this.jobs.set(j));
    const d = this.detail();
    if (d) this.open(d);
  }

  protected open(j: Job): void {
    this.api.get(j.id).subscribe((x) => this.detail.set(x));
    this.api.attempts(j.id).subscribe((a) => this.attempts.set(a));
  }

  private act(obs: Observable<Job>, message: string): void {
    runAction(obs, this.busy, this.notify, message, (x) => { this.detail.set(x); this.reload(); });
  }

  protected cancel(j: Job): void {
    askReason(this.dialog, { title: `Cancel ${j.job_code}?`, confirmLabel: 'Cancel job', danger: true,
      message: 'Only a queued job can be cancelled. Lazy expiry still keeps the platform correct without it.' })
      .subscribe((r) => { if (r) this.act(this.api.cancel(j.id, r.reason), 'Job cancelled.'); });
  }

  protected retry(j: Job): void {
    askReason(this.dialog, { title: `Requeue ${j.job_code}?`, confirmLabel: 'Requeue',
      message: 'The job runs again as a new attempt; every precondition is re-checked.' })
      .subscribe((r) => { if (r) this.act(this.api.retry(j.id, r.reason), 'Job requeued.'); });
  }

  protected every(seconds: number | null): string {
    if (!seconds) return 'on request only';
    return seconds % 86400 === 0 ? `every ${seconds / 86400} day(s)` : seconds % 3600 === 0 ? `every ${seconds / 3600} h` : `every ${Math.round(seconds / 60)} min`;
  }

  protected summary(result: Record<string, unknown>): string {
    return Object.entries(result).filter(([, v]) => typeof v !== 'object').map(([k, v]) => `${k.replace(/_/g, ' ')}: ${v}`).join(' · ');
  }
}
