import { DatePipe, JsonPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatTabsModule } from '@angular/material/tabs';
import { Observable } from 'rxjs';

import { ApiError } from '../core/api/api.models';
import { NotifyService } from '../core/notify.service';
import { label } from '../farmer/farmer.models';
import { PageHeader } from '../shared/page-header';
import { askReason } from '../shared/reason-dialog';
import { runAction } from '../shared/run-action';
import { StateView } from '../shared/state-view';
import { StatusBadge } from '../shared/status-badge';
import { CalculationApi } from './calculation.api';
import { RunFindings } from './run-findings';
import { RunReports } from './run-reports';
import {
  CALCULATED_LABEL,
  CalcCompare,
  CalcInputs,
  CalcLineage,
  CalcOutputs,
  CalcQaView,
  CalcRun,
  blockerTitle,
  calcBadge,
  formatValue,
} from './calculation.models';

/** One calculation run: actions, frozen inputs, results by step, QA, lineage and history / comparison. */
@Component({
  selector: 'app-calculation-run-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, JsonPipe, FormsModule, MatButtonModule, MatFormFieldModule, MatInputModule, MatSelectModule, MatTabsModule,
    PageHeader, StateView, StatusBadge, RunFindings, RunReports],
  template: `
    <app-state-view [loading]="loading()" [error]="error()" (retry)="load()" />
    @if (run(); as r) {
      <app-page-header [title]="r.run_code" [subtitle]="r.project_code + ' · ' + r.monitoring_period + ' · ' + r.methodology_label"
                       [backLink]="'/calculations'" backLabel="Calculations" />
      <div class="status-row"><app-status-badge [status]="badge(r.status)" [text]="label(r.status)" data-testid="run-status" />
        @if (r.environment === 'DEMO') { <app-status-badge status="DEMO" /> }
        <span class="small muted">engine {{ r.engine_version }} · module {{ r.module_code ? r.module_code + ' ' + r.module_version + ' (' + r.module_readiness + ')' : 'none' }}</span></div>
      <p class="note" data-testid="calc-label">{{ calculatedLabel }}</p>
      @if (r.demo_label) { <p class="note warn" data-testid="demo-label">{{ r.demo_label }}</p> }
      @if (r.blockers.length) {
        <div class="note bad" data-testid="run-blockers"><strong>Blocked:</strong>
          <ul>@for (b of r.blockers; track $index) { <li><strong>{{ title(b) }}</strong> — {{ b.message }}</li> }</ul></div>
      }
      @if (r.net_result) {
        <div class="result" data-testid="net-result"><span class="small muted">Final NET output</span>
          <strong>{{ value(r.net_result) }} {{ r.net_unit }}</strong><span class="small muted">(stored exactly: {{ r.net_result }})</span></div>
      }
      @if (r.recalculation_of_code) { <p class="small">Recalculates {{ r.recalculation_of_code }}: {{ r.recalculation_reason }}</p> }
      @if (r.superseded_by_code) { <p class="small warn">Superseded by {{ r.superseded_by_code }} ({{ r.superseded_at | date: 'medium' }})</p> }
      <div class="actions">
        @if (r.can_freeze) { <button mat-flat-button type="button" [disabled]="busy()" (click)="act(api.freeze(r.id), 'Inputs frozen.')" data-testid="freeze">Check readiness &amp; freeze inputs</button> }
        @if (r.can_execute) { <button mat-flat-button type="button" [disabled]="busy()" (click)="act(api.execute(r.id), 'Calculated.')" data-testid="execute">Execute</button> }
        @if (r.can_submit) { <button mat-flat-button type="button" [disabled]="busy()" (click)="act(api.submit(r.id), 'Submitted for calculation QA.')" data-testid="submit-run">Submit for QA</button> }
        @if (r.can_cancel) { <button mat-button type="button" (click)="decide('Cancel')">Cancel run</button> }
        @if (r.can_approve && qa()?.can_approve) { <button mat-flat-button type="button" (click)="decide('Approve')" data-testid="approve-run">Approve</button> }
        @if (r.can_approve) { <button mat-button type="button" (click)="decide('Reject')">Reject</button> }
        @if (r.can_recalculate) { <button mat-stroked-button type="button" (click)="recalculate(r)" data-testid="recalculate">Recalculate (new run)</button> }
      </div>
      <app-run-reports [run]="r" />
      <mat-tab-group animationDuration="0ms" mat-stretch-tabs="false">
        <mat-tab label="Inputs"><div class="tab-body">
          <p class="small mono">Input SHA-256 {{ r.input_sha256 ?? '— (not frozen)' }}</p>
          <div class="table-wrap"><table class="table">
            <thead><tr><th>#</th><th>Variable</th><th>Source</th><th>Value</th><th>Unit</th><th>Level</th><th>Requirement</th></tr></thead>
            <tbody>
              @for (i of inputs()?.inputs ?? []; track i.seq) {
                <tr><td>{{ i.seq }}</td><td>{{ i.variable_code }}</td><td>{{ label(i.source_type) }} {{ i.source_code }}{{ i.source_version ? ' v' + i.source_version : '' }}</td>
                  <td class="mono">{{ i.value }}</td><td>{{ i.unit }}</td><td>{{ label(i.level) }}</td>
                  <td>{{ i.requirement_source ?? '' }}{{ i.source_reference ? ' · ' + i.source_reference : '' }}</td></tr>
              } @empty { <tr><td colspan="7" class="muted">No frozen inputs.</td></tr> }
            </tbody>
          </table></div>
        </div></mat-tab>
        <mat-tab label="Results"><div class="tab-body">
          <div class="steps">@for (s of r.steps; track s.step) { <app-status-badge [status]="badge(s.status)" [text]="s.step + ': ' + s.label" /> }</div>
          <p class="small mono">Output SHA-256 {{ r.output_sha256 ?? '—' }}</p>
          <div class="table-wrap"><table class="table">
            <thead><tr><th>#</th><th>Step</th><th>Output</th><th>Rule</th><th>Value</th><th>Uses</th></tr></thead>
            <tbody>
              @for (o of outputs()?.outputs ?? []; track o.seq) {
                <tr [class.final]="o.is_final"><td>{{ o.seq }}</td><td>{{ o.step }}</td><td>{{ o.output_code }}{{ o.is_final ? ' (final)' : '' }}</td>
                  <td>{{ o.rule_code }}{{ o.equation_reference ? ' · ' + o.equation_reference : '' }}</td>
                  <td class="mono">{{ value(o.value) }} {{ o.unit }}</td>
                  <td class="small">inputs {{ o.input_seqs.join(', ') || '—' }} · outputs {{ o.output_seqs.join(', ') || '—' }}</td></tr>
              } @empty { <tr><td colspan="6" class="muted">Nothing calculated.</td></tr> }
            </tbody>
          </table></div>
        </div></mat-tab>
        <mat-tab label="QA"><div class="tab-body">
          @if (qa(); as q) {
            @if (q.blocked_reasons.length && r.status === 'QA_REVIEW') { <p class="note bad">You cannot review this run: {{ q.blocked_reasons.join('; ') }} (separation of duties).</p> }
            @for (c of q.checks; track c.key) {
              <div class="check" [attr.data-check]="c.key"><app-status-badge [status]="badge(c.result)" [text]="c.result" /> {{ c.label }}
                @if (c.details.length) { <ul class="small">@for (d of c.details; track $index) { <li>{{ d }}</li> }</ul> }</div>
            } @empty { <p class="muted small">QA checks run once inputs are frozen.</p> }
            @if (q.can_start) { <button mat-flat-button type="button" [disabled]="busy()" (click)="qaAct(api.startQa(r.id), 'QA started.')" data-testid="start-calc-qa">Start calculation QA</button> }
            @if (q.can_complete) {
              <div class="row">
                <mat-form-field subscriptSizing="dynamic"><mat-label>Result</mat-label>
                  <mat-select [(ngModel)]="qaResult"><mat-option value="PASS">PASS</mat-option><mat-option value="FAIL">FAIL</mat-option></mat-select></mat-form-field>
                <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Notes</mat-label><input matInput [(ngModel)]="qaNotes" /></mat-form-field>
                <button mat-flat-button type="button" [disabled]="busy() || qaNotes.trim().length < 3" (click)="completeQa()" data-testid="complete-calc-qa">Record QA</button>
              </div>
            }
            <h3>Reviews</h3>
            @for (v of q.reviews; track v.id) { <div class="small">{{ v.result ?? 'open' }} · {{ v.completed_by_name ?? v.started_by_name }} · {{ (v.completed_at ?? v.started_at) | date: 'medium' }} {{ v.notes ? '— ' + v.notes : '' }}</div> }
            @empty { <p class="muted small">No review yet.</p> }
          }
        </div></mat-tab>
        <mat-tab label="Findings"><div class="tab-body">
          <app-run-findings [run]="r" />
        </div></mat-tab>
        <mat-tab label="Lineage"><div class="tab-body" data-testid="calc-lineage">
          @if (lineage(); as l) {
            <p class="small">{{ l.methodology.label }} · calculation rules v{{ l.methodology.calculation_rules_version }}
              · dataset {{ l.dataset?.code ?? '—' }} <span class="mono">{{ l.dataset?.snapshot_sha256?.slice(0, 16) }}</span></p>
            @if (l.final) { <p><strong>{{ l.final.output_code }}</strong> = {{ value(l.final.value) }} {{ l.final.unit }} ← rule {{ l.final.rule['rule_code'] }}</p> }
            <h3>Internal pre-verification</h3>
            <div class="small">Findings: @for (f of l.findings; track f.id) { {{ f.code }} ({{ f.category_label }}, {{ f.status }}){{ $last ? '' : '; ' }} } @empty { none }</div>
            <div class="small">Reports: @for (x of l.reports; track x.id) { {{ x.report_code }} v{{ x.version }} {{ x.status }} <span class="mono">{{ x.content_sha256.slice(0, 12) }}</span>{{ $last ? '' : '; ' }} } @empty { none }</div>
            <div class="small">Readiness: @for (x of l.readiness; track x.id) { {{ x.readiness_code }} {{ x.status }}{{ x.manifest_sha256 ? ' · manifest ' + x.manifest_sha256.slice(0, 12) : '' }}{{ $last ? '' : '; ' }} } @empty { none }</div>
            <h3>Inputs and their sources</h3>
            @for (i of l.inputs; track i.seq) {
              <div class="small lin">#{{ i.seq }} {{ i.variable_code }} = {{ i.value }} {{ i.unit }} ← <span class="mono">{{ i.chain | json }}</span></div>
            } @empty { <p class="muted small">No inputs.</p> }
          }
        </div></mat-tab>
        <mat-tab label="History / Compare"><div class="tab-body">
          @for (h of lineage()?.history ?? []; track $index) {
            <div class="small">{{ h.at | date: 'medium' }} · {{ h.from_status ? label(h.from_status) + ' → ' : '' }}{{ label(h.to_status) }} · {{ h.user_name }} {{ h.reason ? '— ' + h.reason : '' }}</div>
          }
          <h3>Compare with another run</h3>
          <div class="row">
            <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Run</mat-label>
              <mat-select [(ngModel)]="otherId">@for (o of others(); track o.id) { <mat-option [value]="o.id">{{ o.run_code }} · {{ label(o.status) }}</mat-option> }</mat-select></mat-form-field>
            <button mat-stroked-button type="button" [disabled]="!otherId" (click)="compareWith()" data-testid="compare">Compare</button>
          </div>
          @if (comparison(); as c) {
            <p class="small">Inputs {{ c.same_inputs ? 'identical' : 'differ' }} · outputs {{ c.same_outputs ? 'identical' : 'differ' }}</p>
            @for (f of changedFields(c); track f[0]) { <div class="small">{{ f[0] }}: {{ f[1][0] }} → {{ f[1][1] }}</div> }
            @for (o of c.outputs_changed; track o.output_code) { <div class="small">{{ o.output_code }}: {{ o.before ?? '—' }} → {{ o.after ?? '—' }} {{ o.unit }}</div> }
          }
        </div></mat-tab>
      </mat-tab-group>
    }
  `,
  styles: `.status-row { display: flex; gap: 6px; align-items: center; margin: -8px 0 8px; flex-wrap: wrap; }
    .actions { display: flex; gap: 8px; flex-wrap: wrap; margin: 10px 0; } .result { display: flex; gap: 10px; align-items: baseline; margin: 8px 0; font-size: 18px; }
    .steps { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; } .mono { font-family: monospace; font-size: 12px; word-break: break-all; }
    tr.final td { font-weight: 600; } .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-top: 10px; } .wide { min-width: 260px; flex: 1; }
    h3 { margin: 14px 0 6px; font: var(--mat-sys-title-small); } .check { padding: 3px 0; } .lin { margin: 4px 0; }`,
})
export class CalculationRunPage implements OnInit {
  readonly id = input.required<string>();
  protected readonly api = inject(CalculationApi);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotifyService);
  protected readonly label = label;
  protected readonly badge = calcBadge;
  protected readonly title = blockerTitle;
  protected readonly value = formatValue;
  protected readonly calculatedLabel = CALCULATED_LABEL;
  protected readonly run = signal<CalcRun | null>(null);
  protected readonly inputs = signal<CalcInputs | null>(null);
  protected readonly outputs = signal<CalcOutputs | null>(null);
  protected readonly qa = signal<CalcQaView | null>(null);
  protected readonly lineage = signal<CalcLineage | null>(null);
  protected readonly others = signal<CalcRun[]>([]);
  protected readonly comparison = signal<CalcCompare | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<ApiError | null>(null);
  protected readonly busy = signal(false);
  protected qaResult: 'PASS' | 'FAIL' = 'PASS';
  protected qaNotes = '';
  protected otherId = '';

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    const id = this.id();
    this.api.run(id).subscribe({
      next: (r) => {
        this.run.set(r);
        this.loading.set(false);
        this.api.runs(r.project_id).subscribe((rs) => this.others.set(rs.filter((x) => x.id !== r.id)));
      },
      error: (e: unknown) => { this.error.set(ApiError.from(e)); this.loading.set(false); },
    });
    this.api.inputs(id).subscribe((x) => this.inputs.set(x));
    this.api.outputs(id).subscribe((x) => this.outputs.set(x));
    this.api.qa(id).subscribe((x) => this.qa.set(x));
    this.api.lineage(id).subscribe((x) => this.lineage.set(x));
  }

  protected act(obs: Observable<CalcRun>, message: string): void {
    // a blocked freeze / execution is recorded server-side (the run becomes BLOCKED with its blockers): reload either way
    this.busy.set(true);
    obs.subscribe({
      next: () => { this.busy.set(false); this.notify.success(message); this.load(); },
      error: (e: unknown) => { this.busy.set(false); this.notify.error(e); this.load(); },
    });
  }

  protected qaAct(obs: Observable<CalcQaView>, message: string): void {
    runAction(obs, this.busy, this.notify, message, () => this.load());
  }

  protected completeQa(): void {
    this.qaAct(this.api.completeQa(this.id(), this.qaResult, this.qaNotes.trim()), `QA recorded: ${this.qaResult}.`);
  }

  protected decide(what: 'Cancel' | 'Approve' | 'Reject'): void {
    const r = this.run();
    if (!r) return;
    const call = { Cancel: this.api.cancel, Approve: this.api.approve, Reject: this.api.reject }[what];
    askReason(this.dialog, { title: `${what} ${r.run_code}?`, confirmLabel: what, danger: what !== 'Approve' }).subscribe((x) => {
      if (x) runAction(call(r.id, x.reason), this.busy, this.notify, `${what}: done.`, () => this.load());
    });
  }

  protected recalculate(r: CalcRun): void {
    askReason(this.dialog, { title: `Recalculate ${r.run_code}?`, confirmLabel: 'Create new run',
      message: 'A new run is created with its own frozen inputs, outputs, QA and approval. This run is never changed.' }).subscribe((x) => {
      if (x) runAction(this.api.recalculate(r.id, x.reason), this.busy, this.notify, 'New calculation run created.', () => this.load());
    });
  }

  protected compareWith(): void {
    if (this.otherId) this.api.compare(this.id(), this.otherId).subscribe((c) => this.comparison.set(c));
  }

  protected changedFields(c: CalcCompare): [string, [string | null, string | null]][] {
    return Object.entries(c.changed_fields);
  }
}
