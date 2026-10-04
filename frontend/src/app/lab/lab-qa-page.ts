import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';

import { ApiError } from '../core/api/api.models';
import { NotifyService } from '../core/notify.service';
import { label } from '../farmer/farmer.models';
import { PageHeader } from '../shared/page-header';
import { reloadOn } from '../shared/reload-on';
import { runAction } from '../shared/run-action';
import { StateView } from '../shared/state-view';
import { StatusBadge } from '../shared/status-badge';
import { LaboratoryApi } from './lab.api';
import { QaLabView, labBadge, resultValue } from './lab.models';

/** Laboratory QA (LAB_MANAGER): deterministic checks, then APPROVED / REJECTED / RETEST_REQUIRED — never on your own work. */
@Component({
  selector: 'app-lab-qa-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, FormsModule, MatButtonModule, MatCheckboxModule, MatFormFieldModule, MatInputModule, MatSelectModule, PageHeader, StateView,
    StatusBadge],
  template: `
    <app-state-view [loading]="loading()" [error]="error()" (retry)="load()" />
    @if (v(); as v) {
      <app-page-header [title]="'QA · ' + v.test.test_code + ' v' + v.result.version" [subtitle]="v.sample_code + ' · ' + v.test.rule.rule_code + ' ' + v.test.rule.parameter"
                       [backLink]="'/laboratory/tests/' + v.test.id" backLabel="Test" />
      <div class="status-row"><app-status-badge [status]="badge(v.result.status)" [text]="label(v.result.status)" />
        <strong>{{ value(v.result) }}</strong><span class="small muted"> · analysed {{ v.result.analysed_at | date: 'medium' }} by {{ v.result.analyst_name }}</span></div>
      @if (v.blocked_reasons.length) { <p class="note bad">You cannot approve this result: {{ v.blocked_reasons.join('; ') }} (separation of duties).</p> }
      <h3>Checks</h3>
      @for (c of v.checks; track c.key) {
        <div class="check" [attr.data-check]="c.key"><app-status-badge [status]="badge(c.result)" [text]="c.result" /> {{ c.label }}
          @if (c.details.length) { <ul class="small">@for (d of c.details; track $index) { <li>{{ d }}</li> }</ul> }</div>
      }
      @if (v.can_start) { <button mat-flat-button type="button" [disabled]="busy()" (click)="start()" data-testid="start-lab-qa">Start QA review</button> }
      @if (v.can_decide) {
        <div class="row">
          <mat-form-field subscriptSizing="dynamic"><mat-label>Decision</mat-label>
            <mat-select [(ngModel)]="decision" data-testid="lab-qa-decision">
              <mat-option value="APPROVED" [disabled]="!v.can_approve">APPROVED</mat-option><mat-option value="REJECTED">REJECTED</mat-option>
              <mat-option value="RETEST_REQUIRED">RETEST_REQUIRED</mat-option></mat-select></mat-form-field>
          <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Notes (required)</mat-label><input matInput [(ngModel)]="notes" data-testid="lab-qa-notes" /></mat-form-field>
          @if (acknowledgeable()) { <mat-checkbox [(ngModel)]="ack">Acknowledge CONFIGURATION_REQUIRED (DEMO / non-production only)</mat-checkbox> }
          <button mat-flat-button type="button" [disabled]="busy() || notes.trim().length < 3" (click)="decide()" data-testid="lab-qa-submit">Record decision</button>
        </div>
      }
      <h3>Reviews</h3>
      @for (r of v.reviews; track r.id) { <div class="small">{{ r.decision }} · {{ r.reviewer_name }} · {{ r.reviewed_at | date: 'medium' }} — {{ r.notes }}</div> }
      @empty { <p class="muted small">No review yet.</p> }
    }
  `,
  styles: `.status-row { display: flex; gap: 8px; align-items: center; margin: -8px 0 12px; } h3 { margin: 14px 0 8px; font: var(--mat-sys-title-small); }
    .check { padding: 3px 0; } .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-top: 10px; } .wide { min-width: 260px; flex: 1; }`,
})
export class LabQaPage {
  readonly id = input.required<string>();
  private readonly api = inject(LaboratoryApi);
  private readonly notify = inject(NotifyService);
  protected readonly label = label;
  protected readonly badge = labBadge;
  protected readonly value = resultValue;
  protected readonly v = signal<QaLabView | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<ApiError | null>(null);
  protected readonly busy = signal(false);
  protected decision = 'APPROVED';
  protected notes = '';
  protected ack = false;

  constructor() {
    reloadOn(this.id, () => {
      this.v.set(null);
      this.decision = 'APPROVED';
      this.notes = '';
      this.ack = false;
      this.error.set(null);
      this.loading.set(true);
      this.load();
    });
  }

  load(): void {
    this.api.qa(this.id()).subscribe({
      next: (v) => { this.v.set(v); this.loading.set(false); },
      error: (e: unknown) => { this.error.set(ApiError.from(e)); this.loading.set(false); },
    });
  }

  protected acknowledgeable(): boolean {
    return (this.v()?.checks ?? []).some((c) => c.result === 'CONFIGURATION_REQUIRED' && c.acknowledgeable);
  }

  protected start(): void {
    runAction(this.api.startQa(this.id()), this.busy, this.notify, 'QA review started.', (v) => this.v.set(v));
  }

  protected decide(): void {
    runAction(this.api.decide(this.id(), { decision: this.decision, notes: this.notes.trim(), acknowledge_configuration: this.ack }), this.busy,
      this.notify, `Decision recorded: ${this.decision}.`, (v) => this.v.set(v));
  }
}
