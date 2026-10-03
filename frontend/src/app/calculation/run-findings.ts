import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { Observable } from 'rxjs';

import { AuthService } from '../core/auth/auth.service';
import { P } from '../core/auth/permissions';
import { NotifyService } from '../core/notify.service';
import { label } from '../farmer/farmer.models';
import { askReason } from '../shared/reason-dialog';
import { runAction } from '../shared/run-action';
import { StatusBadge } from '../shared/status-badge';
import { CalcRun } from './calculation.models';
import { PreverificationApi } from './preverification.api';
import { FINDING_CATEGORIES, Finding, findingBadge } from './preverification.models';

/** Internal findings of one run (QA raises / resolves / reopens / withdraws; the analyst responds). Not VVB findings. */
@Component({
  selector: 'app-run-findings',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, FormsModule, MatButtonModule, MatCheckboxModule, MatFormFieldModule, MatInputModule, MatSelectModule, StatusBadge],
  template: `
    <p class="small muted">Internal QA findings on this run. Blocking findings gate internal readiness only; they never change the run.</p>
    @for (f of findings(); track f.id) {
      <div class="finding" [attr.data-finding]="f.finding_code">
        <div><strong>{{ f.finding_code }}</strong> · {{ f.category_label }} {{ f.blocking ? '· BLOCKING' : '· informational' }}
          <app-status-badge [status]="badge(f.status)" [text]="label(f.status)" /> — {{ f.title }}</div>
        <div class="small">{{ f.description }}
          {{ f.target_input_seq ? ' · input #' + f.target_input_seq : '' }}{{ f.target_output_seq ? ' · output #' + f.target_output_seq : '' }}
          {{ f.target_rule_code ? ' · rule ' + f.target_rule_code : '' }}</div>
        @if (f.response_text) { <div class="small">Response ({{ f.responded_by_name }}): {{ f.response_text }}</div> }
        @if (f.resolution_note) { <div class="small">Resolved by {{ f.resolved_by_name }}: {{ f.resolution_note }}</div> }
        @if (f.withdraw_reason) { <div class="small muted">Withdrawn: {{ f.withdraw_reason }}</div> }
        <div class="row">
          @if (f.can_respond) {
            <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Response</mat-label>
              <input matInput [(ngModel)]="response[f.id]" [attr.data-testid]="'response-' + f.finding_code" /></mat-form-field>
            <button mat-flat-button type="button" [disabled]="busy() || (response[f.id] ?? '').trim().length < 3" (click)="respond(f)"
                    data-testid="respond-finding">Respond</button>
          }
          @if (f.can_resolve) { <button mat-flat-button type="button" (click)="withReason(f, 'Resolve')" data-testid="resolve-finding">Resolve</button> }
          @if (f.can_return) { <button mat-button type="button" (click)="withReason(f, 'Return')">Return response</button> }
          @if (f.can_reopen) { <button mat-button type="button" (click)="withReason(f, 'Reopen')">Reopen</button> }
          @if (f.can_withdraw) { <button mat-button type="button" (click)="withReason(f, 'Withdraw')">Withdraw</button> }
        </div>
        <details><summary class="small">History ({{ f.events.length }})</summary>
          @for (e of f.events; track e.seq) { <div class="small">{{ e.occurred_at | date: 'short' }} · {{ e.action }} · {{ e.actor_name }} {{ e.note ? '— ' + e.note : '' }}</div> }
        </details>
      </div>
    } @empty { <p class="muted small">No finding.</p> }
    @if (canRaise && run().status !== 'DRAFT') {
      <h4>Raise a finding</h4>
      <div class="row">
        <mat-form-field subscriptSizing="dynamic"><mat-label>Category</mat-label>
          <mat-select [(ngModel)]="category" data-testid="finding-category">
            @for (c of categories; track c.code) { <mat-option [value]="c.code">{{ c.label }}</mat-option> }</mat-select></mat-form-field>
        <mat-checkbox [(ngModel)]="blocking" data-testid="finding-blocking">Blocking (gates internal readiness)</mat-checkbox>
        <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Title</mat-label><input matInput [(ngModel)]="title" data-testid="finding-title" /></mat-form-field>
      </div>
      <div class="row">
        <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Description</mat-label>
          <input matInput [(ngModel)]="description" data-testid="finding-description" /></mat-form-field>
        <mat-form-field subscriptSizing="dynamic"><mat-label>Input # (optional)</mat-label><input matInput type="number" [(ngModel)]="inputSeq" /></mat-form-field>
        <mat-form-field subscriptSizing="dynamic"><mat-label>Output # (optional)</mat-label><input matInput type="number" [(ngModel)]="outputSeq" /></mat-form-field>
        <button mat-flat-button type="button" [disabled]="busy() || !category || title.trim().length < 3 || description.trim().length < 3"
                (click)="raise()" data-testid="raise-finding">Raise finding</button>
      </div>
    }
  `,
  styles: `.finding { border-bottom: 1px solid var(--mat-sys-outline-variant); padding: 6px 0; } .row { display: flex; gap: 8px; flex-wrap: wrap;
    align-items: center; margin-top: 6px; } .wide { min-width: 240px; flex: 1; } h4 { margin: 12px 0 4px; }`,
})
export class RunFindings implements OnInit {
  readonly run = input.required<CalcRun>();
  private readonly api = inject(PreverificationApi);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotifyService);
  protected readonly canRaise = inject(AuthService).has(P.CALCULATION_REVIEW);
  protected readonly label = label;
  protected readonly badge = findingBadge;
  protected readonly categories = FINDING_CATEGORIES;
  protected readonly findings = signal<Finding[]>([]);
  protected readonly busy = signal(false);
  protected response: Record<string, string | undefined> = {};
  protected category = '';
  protected blocking = true;
  protected title = '';
  protected description = '';
  protected inputSeq: number | null = null;
  protected outputSeq: number | null = null;

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.api.findings(this.run().project_id, this.run().id).subscribe((f) => this.findings.set(f));
  }

  protected raise(): void {
    const body: Record<string, unknown> = { category: this.category, blocking: this.blocking, title: this.title.trim(), description: this.description.trim() };
    if (this.inputSeq) body['target_input_seq'] = this.inputSeq;
    if (this.outputSeq) body['target_output_seq'] = this.outputSeq;
    runAction(this.api.raise(this.run().id, body), this.busy, this.notify, 'Finding raised.', () => {
      this.title = this.description = '';
      this.inputSeq = this.outputSeq = null;
      this.load();
    });
  }

  protected respond(f: Finding): void {
    runAction(this.api.respond(f.id, (this.response[f.id] ?? '').trim()), this.busy, this.notify, 'Response recorded.', () => this.load());
  }

  protected withReason(f: Finding, what: 'Resolve' | 'Return' | 'Reopen' | 'Withdraw'): void {
    const call: Record<typeof what, (id: string, text: string) => Observable<Finding>> = {
      Resolve: this.api.resolve, Return: this.api.returnResponse, Reopen: this.api.reopen, Withdraw: this.api.withdraw };
    askReason(this.dialog, { title: `${what} ${f.finding_code}?`, confirmLabel: what, danger: what === 'Withdraw' }).subscribe((x) => {
      if (x) runAction(call[what](f.id, x.reason), this.busy, this.notify, `${what}: done.`, () => this.load());
    });
  }
}
