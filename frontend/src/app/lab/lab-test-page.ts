import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { RouterLink } from '@angular/router';

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
import { LaboratoryApi } from './lab.api';
import { ResultLabView, TestLabView, labBadge, resultTypeApprovable, resultValue, unitMatches } from './lab.models';

/** Test workspace (technician): start, enter a result (numeric or verbatim text), attach the PDF report, submit. */
@Component({
  selector: 'app-lab-test-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, FormsModule, RouterLink, MatButtonModule, MatFormFieldModule, MatInputModule, MatSelectModule, PageHeader, StateView, StatusBadge],
  template: `
    <app-state-view [loading]="loading()" [error]="error()" (retry)="load()" />
    @if (t(); as t) {
      <app-page-header [title]="t.test_code" [subtitle]="t.sample_code + ' · ' + t.project_code + ' · ' + t.rule.rule_code + ' ' + t.rule.parameter"
                       backLink="/laboratory" backLabel="Laboratory" />
      <div class="status-row"><app-status-badge [status]="badge(t.status)" [text]="label(t.status)" />
        @if (t.retest_of_test_code) { <app-status-badge status="WARNING" [text]="'Retest of ' + t.retest_of_test_code" /> }</div>
      <dl class="kv">
        <dt>Required unit</dt><dd>{{ t.required_unit ?? 'CONFIGURATION_REQUIRED — the methodology rule declares no unit' }}</dd>
        <dt>Value type</dt><dd>{{ t.value_type === 'NUMBER' ? 'Numeric (a text result such as "ND" or "<0.05" can never be approved)' : 'Text' }}</dd>
        <dt>Methodology method</dt><dd>{{ t.rule.method ?? 'not configured' }}</dd>
        @if (t.retest_reason) { <dt>Retest reason</dt><dd>{{ t.retest_reason }}</dd> }
      </dl>
      @if (t.can_start) {
        <div class="row"><mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Method used (as performed)</mat-label><input matInput [(ngModel)]="method" /></mat-form-field>
          <button mat-flat-button type="button" [disabled]="busy()" (click)="start()" data-testid="start-test">Start test</button></div>
      }
      @if (t.can_enter_result) {
        <h3>Enter result</h3>
        <div class="row">
          <mat-form-field subscriptSizing="dynamic"><mat-label>Result type</mat-label>
            <mat-select [(ngModel)]="resultType"><mat-option value="NUMERIC">Numeric</mat-option><mat-option value="TEXT">Text as reported</mat-option></mat-select></mat-form-field>
          @if (resultType === 'NUMERIC') {
            <mat-form-field subscriptSizing="dynamic"><mat-label>Value</mat-label><input matInput type="number" [(ngModel)]="valueNumber" data-testid="result-value" /></mat-form-field>
          } @else {
            <mat-form-field subscriptSizing="dynamic"><mat-label>Value (verbatim)</mat-label><input matInput [(ngModel)]="valueText" data-testid="result-text" /></mat-form-field>
          }
          <mat-form-field subscriptSizing="dynamic"><mat-label>Unit</mat-label><input matInput [(ngModel)]="unit" data-testid="result-unit" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Analysed at</mat-label><input matInput type="datetime-local" step="1" [(ngModel)]="analysedAt" /></mat-form-field>
          <button mat-flat-button type="button" [disabled]="busy() || !canSave()" (click)="save()" data-testid="save-result">Save result</button>
        </div>
        @if (unitState() === 'MISMATCH') { <p class="note warn">The unit differs from the required "{{ t.required_unit }}". Values are never converted — QA will fail (UNIT_MISMATCH).</p> }
        @if (!typeApprovable()) { <p class="note warn">A text result cannot be approved for a numeric parameter; it will be stored exactly as entered.</p> }
      }
      <h3>Results</h3>
      @for (r of t.results; track r.id) {
        <div class="result">
          <div><strong>v{{ r.version }}</strong> · {{ value(r) }} · <app-status-badge [status]="badge(r.status)" [text]="label(r.status)" />
            <span class="small muted"> · {{ r.analyst_name }} · {{ r.analysed_at | date: 'medium' }}</span></div>
          @if (r.report) { <div class="small">Report: {{ r.report.file_name }} · SHA-256 {{ r.report.sha256?.slice(0, 16) }}…</div> }
          @if (r.status_reason) { <div class="small muted">{{ r.status_reason }}</div> }
          <div class="row">
            @if (r.can_edit || r.status === 'SUBMITTED') {
              <label class="upload">PDF report <input type="file" accept="application/pdf" (change)="upload(r, $event)" [attr.data-testid]="'report-' + r.version" /></label>
            }
            @if (r.can_submit) { <button mat-flat-button type="button" [disabled]="busy()" (click)="submit(r)" data-testid="submit-result">Submit for QA</button> }
            @if (r.can_submit) { <button mat-button type="button" (click)="withdraw(r)">Withdraw</button> }
            @if (r.status === 'SUBMITTED' || r.status === 'QA_REVIEW') { <a mat-button [routerLink]="['/laboratory/qa', r.id]">Laboratory QA</a> }
            @if (r.status === 'APPROVED' && canRetest) { <button mat-button type="button" (click)="retest(r)">Request retest</button> }
          </div>
        </div>
      } @empty { <p class="muted small">No result yet.</p> }
    }
  `,
  styles: `.status-row { display: flex; gap: 6px; margin: -8px 0 12px; } h3 { margin: 14px 0 8px; font: var(--mat-sys-title-small); }
    .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; } .wide { min-width: 260px; flex: 1; }
    .result { border-bottom: 1px solid var(--mat-sys-outline-variant); padding: 6px 0; } .upload { font-size: 13px; }`,
})
export class LabTestPage implements OnInit {
  readonly id = input.required<string>();
  private readonly api = inject(LaboratoryApi);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotifyService);
  protected readonly canRetest = inject(AuthService).has(P.LAB_RETEST_REQUEST);
  protected readonly label = label;
  protected readonly badge = labBadge;
  protected readonly value = resultValue;
  protected readonly t = signal<TestLabView | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<ApiError | null>(null);
  protected readonly busy = signal(false);
  protected method = '';
  protected resultType: 'NUMERIC' | 'TEXT' = 'NUMERIC';
  protected valueNumber: number | null = null;
  protected valueText = '';
  protected unit = '';
  /** Local time with seconds: laboratory QA compares it with the receipt time. */
  protected analysedAt = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 19);

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.api.test(this.id()).subscribe({
      next: (t) => {
        this.t.set(t);
        this.loading.set(false);
        if (!this.unit) this.unit = t.required_unit ?? '';      // pre-filled with the rule's exact unit text
        if (t.value_type !== 'NUMBER') this.resultType = 'TEXT';
      },
      error: (e: unknown) => { this.error.set(ApiError.from(e)); this.loading.set(false); },
    });
  }

  protected unitState(): 'MATCH' | 'MISMATCH' | 'CONFIGURATION_REQUIRED' {
    return unitMatches(this.t()?.required_unit ?? null, this.unit);
  }

  protected typeApprovable(): boolean {
    return resultTypeApprovable(this.t()?.value_type ?? 'NUMBER', this.resultType);
  }

  protected canSave(): boolean {
    return this.resultType === 'NUMERIC' ? this.valueNumber !== null && `${this.valueNumber}` !== '' : !!this.valueText.trim();
  }

  protected start(): void {
    runAction(this.api.start(this.id(), this.method.trim() || null), this.busy, this.notify, 'Test started.', (t) => this.t.set(t));
  }

  protected save(): void {
    const body: Record<string, unknown> = { result_type: this.resultType, unit: this.unit.trim() || null, analysed_at: new Date(this.analysedAt).toISOString(),
      method_reported: this.method.trim() || null };
    if (this.resultType === 'NUMERIC') body['value_number'] = this.valueNumber;
    else body['value_text'] = this.valueText;            // verbatim, never parsed
    runAction(this.api.createResult(this.id(), body), this.busy, this.notify, 'Result saved (draft).', () => this.load());
  }

  protected upload(r: ResultLabView, ev: Event): void {
    const file = (ev.target as HTMLInputElement).files?.[0];
    if (file) runAction(this.api.report(r.id, file), this.busy, this.notify, 'Report attached.', () => this.load());
  }

  protected submit(r: ResultLabView): void {
    runAction(this.api.submit(r.id), this.busy, this.notify, 'Submitted for laboratory QA.', () => this.load());
  }

  protected withdraw(r: ResultLabView): void {
    askReason(this.dialog, { title: `Withdraw result v${r.version}?`, confirmLabel: 'Withdraw', danger: true }).subscribe((x) => {
      if (x) runAction(this.api.withdraw(r.id, x.reason), this.busy, this.notify, 'Result withdrawn.', () => this.load());
    });
  }

  protected retest(r: ResultLabView): void {
    askReason(this.dialog, { title: `Request a retest of v${r.version}?`, confirmLabel: 'Request retest',
      message: 'The approved result is kept until a retest result is approved by another manager.' }).subscribe((x) => {
      if (x) runAction(this.api.retest(r.id, x.reason), this.busy, this.notify, 'Retest requested.', () => this.load());
    });
  }
}
