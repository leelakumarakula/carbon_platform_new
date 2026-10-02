import { DatePipe, JsonPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatTabsModule } from '@angular/material/tabs';

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
import { MethodologiesApi } from './methodologies.api';
import { CALC_STEPS, Change, GENERAL_RULE_TYPES, OPERATORS, RULE_CATEGORIES, Rule, RuleKind, VersionDetail, show, versionBadge } from './methodology.models';

/** One methodology version: metadata, rules (editable only while DRAFT), approval workflow and change history. */
@Component({
  selector: 'app-methodology-version-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, JsonPipe, ReactiveFormsModule, MatButtonModule, MatCheckboxModule, MatFormFieldModule, MatInputModule, MatSelectModule,
    MatTabsModule, PageHeader, StateView, StatusBadge],
  template: `
    <app-state-view [loading]="loading()" [error]="error()" (retry)="load()" />
    @if (v(); as v) {
      <app-page-header [title]="v.methodology_code + ' — version ' + v.version_label" [subtitle]="v.methodology_name" backLink="/methodologies" backLabel="Methodologies">
        @if (v.can_submit) { <button mat-stroked-button type="button" (click)="act('submit', 'Submit for approval')" [disabled]="busy()">Submit for approval</button> }
        @if (v.status === 'DRAFT' && v.can_edit) { <button mat-button type="button" class="danger" (click)="act('withdraw', 'Withdraw draft')" [disabled]="busy()">Withdraw</button> }
        @if (v.can_approve) {
          <button mat-flat-button type="button" (click)="act('approve', 'Approve version')" [disabled]="busy()">Approve</button>
          <button mat-button type="button" (click)="act('return', 'Return to draft')" [disabled]="busy()">Return to draft</button>
        }
        @if (v.status === 'APPROVED' && canManage()) { <button mat-button type="button" class="danger" (click)="act('retire', 'Retire version')" [disabled]="busy()">Retire</button> }
      </app-page-header>
      <div class="status-row">
        <app-status-badge [status]="badge(v.status)" [text]="label(v.status)" />
        <app-status-badge status="INFO" [text]="'Calculation: ' + label(v.calculation_readiness)" />
        @if (v.is_demo_illustrative) { <app-status-badge status="DEMO" text="Illustrative (DEMO)" /> }
      </div>
      <dl class="kv">
        <dt>Effective</dt><dd>{{ v.effective_from ?? '—' }} → {{ v.effective_to ?? 'open' }}</dd>
        <dt>Source</dt><dd>{{ v.source_name ?? '—' }} @if (v.source_url) { · <a [href]="v.source_url" target="_blank" rel="noopener noreferrer">link</a> }</dd>
        <dt>Rule revisions</dt><dd>applicability/general r{{ v.rules_version }} · monitoring r{{ v.monitoring_rules_version }} · calculation r{{ v.calculation_rules_version }}</dd>
        <dt>Approved</dt><dd>{{ v.approved_at ? (v.approved_at | date: 'medium') : '—' }}</dd>
        @if (v.status_reason) { <dt>Last decision</dt><dd>{{ v.status_reason }}</dd> }
        @if (v.notes) { <dt>Notes</dt><dd>{{ v.notes }}</dd> }
      </dl>
      @if (v.can_edit) {
        <form [formGroup]="meta" (ngSubmit)="saveMeta()" class="form">
          <mat-form-field subscriptSizing="dynamic"><mat-label>Effective from</mat-label><input matInput type="date" formControlName="effective_from" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Effective to</mat-label><input matInput type="date" formControlName="effective_to" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Source (publisher, title)</mat-label><input matInput formControlName="source_name" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Source URL</mat-label><input matInput formControlName="source_url" /></mat-form-field>
          <button mat-stroked-button type="submit" [disabled]="busy()">Save details</button>
        </form>
      } @else { <p class="muted small">This version is {{ label(v.status) }} and cannot be edited. Create a new draft version to change rules.</p> }

      <mat-tab-group animationDuration="0ms" mat-stretch-tabs="false">
        @for (k of kinds; track k) {
          <mat-tab [label]="label(k) + ' (' + rulesOf(k).length + ')'">
            <div class="tab-body">
              @for (r of rulesOf(k); track r.id) {
                <div class="line">
                  <div class="grow"><strong>{{ r.rule_code }}</strong> {{ r.title }}
                    <div class="muted small">{{ summary(r) }}{{ r.source_reference ? ' · ' + r.source_reference : '' }}</div></div>
                  @if (v.can_edit) { <button mat-button type="button" class="danger" (click)="removeRule(r)" [disabled]="busy()">Remove</button> }
                </div>
              } @empty { <p class="muted">No {{ k }} rules.</p> }
              @if (v.can_edit) {
                <form [formGroup]="rule" (ngSubmit)="addRule(k)" class="form">
                  <mat-form-field subscriptSizing="dynamic"><mat-label>Code</mat-label><input matInput formControlName="rule_code" /></mat-form-field>
                  <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Title</mat-label><input matInput formControlName="title" /></mat-form-field>
                  <mat-form-field subscriptSizing="dynamic"><mat-label>Source reference</mat-label><input matInput formControlName="source_reference" /></mat-form-field>
                  @if (k === 'applicability') {
                    <mat-form-field subscriptSizing="dynamic"><mat-label>Category</mat-label>
                      <mat-select formControlName="category">@for (c of categories; track c) { <mat-option [value]="c">{{ label(c) }}</mat-option> }</mat-select></mat-form-field>
                    <mat-form-field subscriptSizing="dynamic"><mat-label>Fact key</mat-label><input matInput formControlName="fact_key" /></mat-form-field>
                    <mat-form-field subscriptSizing="dynamic"><mat-label>Operator</mat-label>
                      <mat-select formControlName="operator">@for (o of operators; track o) { <mat-option [value]="o">{{ o }}</mat-option> }</mat-select></mat-form-field>
                    <mat-form-field subscriptSizing="dynamic"><mat-label>Expected value (JSON)</mat-label><input matInput formControlName="expected" placeholder='["CROPLAND"]' /></mat-form-field>
                    <mat-form-field subscriptSizing="dynamic"><mat-label>If it fails</mat-label>
                      <mat-select formControlName="on_fail">@for (o of ['NOT_APPLICABLE', 'EVIDENCE_REQUIRED', 'NEEDS_INFORMATION']; track o) { <mat-option [value]="o">{{ label(o) }}</mat-option> }</mat-select></mat-form-field>
                    <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Evidence requirement</mat-label><input matInput formControlName="evidence" /></mat-form-field>
                  } @else if (k === 'monitoring') {
                    <mat-form-field subscriptSizing="dynamic"><mat-label>Parameter</mat-label><input matInput formControlName="parameter" /></mat-form-field>
                    <mat-form-field subscriptSizing="dynamic"><mat-label>Unit</mat-label><input matInput formControlName="unit" /></mat-form-field>
                    <mat-form-field subscriptSizing="dynamic"><mat-label>Frequency</mat-label><input matInput formControlName="frequency" /></mat-form-field>
                  } @else if (k === 'calculation') {
                    <mat-form-field subscriptSizing="dynamic"><mat-label>Step</mat-label>
                      <mat-select formControlName="step">@for (s of steps; track s) { <mat-option [value]="s">{{ label(s) }}</mat-option> }</mat-select></mat-form-field>
                    <mat-form-field subscriptSizing="dynamic"><mat-label>Equation reference in the source</mat-label><input matInput formControlName="equation_reference" /></mat-form-field>
                  } @else {
                    <mat-form-field subscriptSizing="dynamic"><mat-label>Rule type</mat-label>
                      <mat-select formControlName="rule_type">@for (s of generalTypes; track s) { <mat-option [value]="s">{{ label(s) }}</mat-option> }</mat-select></mat-form-field>
                    <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Parameters (JSON object)</mat-label><input matInput formControlName="parameters" placeholder='{"min_years": 5}' /></mat-form-field>
                  }
                  <button mat-flat-button type="submit" [disabled]="busy()">Add rule</button>
                </form>
                @if (k === 'calculation') { <p class="muted small">Calculation rules document the source equation reference only. No equation is executed until it is implemented and verified (Phase 7).</p> }
                @if (ruleError(); as e) { <p class="form-error">{{ e }}</p> }
              }
            </div>
          </mat-tab>
        }
        <mat-tab label="Change history">
          <div class="tab-body">
            @for (c of changes(); track c.id) {
              <div class="line"><div class="grow">{{ c.summary }}<div class="muted small">{{ label(c.change_type) }} · {{ c.changed_at | date: 'medium' }}{{ c.reason ? ' · ' + c.reason : '' }}</div></div></div>
            }
          </div>
        </mat-tab>
      </mat-tab-group>
      <details class="small"><summary>Raw rule data</summary><pre>{{ v.rules | json }}</pre></details>
    }
  `,
  styles: `
    .status-row { display: flex; gap: 6px; margin: -8px 0 12px; flex-wrap: wrap; } .danger { color: #b71c1c; }
    .form { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 12px 0; } .wide { min-width: 220px; flex: 1; }
    .line { display: flex; gap: 8px; align-items: center; padding: 6px 0; border-bottom: 1px solid var(--mat-sys-outline-variant); } .grow { flex: 1; }
    pre { white-space: pre-wrap; font-size: 11px; }
  `,
})
export class MethodologyVersionPage implements OnInit {
  readonly id = input.required<string>();
  private readonly api = inject(MethodologiesApi);
  private readonly notify = inject(NotifyService);
  private readonly dialog = inject(MatDialog);
  protected readonly label = label;
  protected readonly badge = versionBadge;
  protected readonly kinds: RuleKind[] = ['applicability', 'monitoring', 'calculation', 'general'];
  protected readonly categories = RULE_CATEGORIES;
  protected readonly operators = OPERATORS;
  protected readonly steps = CALC_STEPS;
  protected readonly generalTypes = GENERAL_RULE_TYPES;
  protected readonly v = signal<VersionDetail | null>(null);
  protected readonly changes = signal<Change[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<ApiError | null>(null);
  protected readonly busy = signal(false);
  protected readonly ruleError = signal<string | null>(null);
  private readonly auth = inject(AuthService);
  protected readonly canManage = computed(() => this.auth.has(P.METHODOLOGIES_MANAGE));
  protected readonly meta = new FormGroup({
    effective_from: new FormControl('', { nonNullable: true }),
    effective_to: new FormControl('', { nonNullable: true }),
    source_name: new FormControl('', { nonNullable: true }),
    source_url: new FormControl('', { nonNullable: true }),
  });
  protected readonly rule = new FormGroup({
    rule_code: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    title: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    source_reference: new FormControl('', { nonNullable: true }),
    category: new FormControl('OTHER', { nonNullable: true }),
    fact_key: new FormControl('', { nonNullable: true }),
    operator: new FormControl('EQUALS', { nonNullable: true }),
    expected: new FormControl('', { nonNullable: true }),
    on_fail: new FormControl('NOT_APPLICABLE', { nonNullable: true }),
    evidence: new FormControl('', { nonNullable: true }),
    parameter: new FormControl('', { nonNullable: true }),
    unit: new FormControl('', { nonNullable: true }),
    frequency: new FormControl('', { nonNullable: true }),
    step: new FormControl('NET', { nonNullable: true }),
    equation_reference: new FormControl('', { nonNullable: true }),
    rule_type: new FormControl('GENERAL', { nonNullable: true }),
    parameters: new FormControl('', { nonNullable: true }),
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.error.set(null);
    this.api.version(this.id()).subscribe({
      next: (v) => {
        this.v.set(v);
        this.loading.set(false);
        this.meta.patchValue({ effective_from: v.effective_from ?? '', effective_to: v.effective_to ?? '', source_name: v.source_name ?? '',
          source_url: v.source_url ?? '' });
        this.api.history(v.methodology_id).subscribe((h) => this.changes.set(h.filter((c) => !c.methodology_version_id || c.methodology_version_id === v.id)));
      },
      error: (e: unknown) => {
        this.error.set(ApiError.from(e));
        this.loading.set(false);
      },
    });
  }

  rulesOf(kind: RuleKind): Rule[] {
    return (this.v()?.rules ?? []).filter((r) => r.kind === kind);
  }

  summary(r: Rule): string {
    const d = r.data;
    if (r.kind === 'applicability') return `${d['fact_key']} ${d['operator']} ${show(d['expected_value'])} → else ${d['on_fail']}`
      + (d['evidence_requirement'] ? ` · evidence: ${d['evidence_requirement']}` : '');
    if (r.kind === 'monitoring') return `${d['parameter']}${d['unit'] ? ' (' + d['unit'] + ')' : ''}${d['frequency'] ? ' · ' + d['frequency'] : ''}`;
    if (r.kind === 'calculation') return `${d['step']} · ${d['equation_reference'] ?? 'no reference'} · ${d['implementation_status']}`;
    return `${d['rule_type']} ${d['parameters'] ? JSON.stringify(d['parameters']) : ''}`;
  }

  saveMeta(): void {
    const m = this.meta.getRawValue();
    const blank = (s: string) => (s.trim() ? s.trim() : null);
    runAction(this.api.updateVersion(this.id(), { effective_from: blank(m.effective_from), effective_to: blank(m.effective_to),
      source_name: blank(m.source_name), source_url: blank(m.source_url) }), this.busy, this.notify, 'Version details saved.', (v) => this.v.set(v));
  }

  addRule(kind: RuleKind): void {
    const f = this.rule.getRawValue();
    const blank = (s: string) => (s.trim() ? s.trim() : null);
    const body: Record<string, unknown> = { rule_code: f.rule_code, title: f.title, source_reference: blank(f.source_reference) };
    try {
      if (kind === 'applicability') Object.assign(body, { category: f.category, fact_key: f.fact_key, operator: f.operator, on_fail: f.on_fail,
        expected_value: f.expected.trim() ? JSON.parse(f.expected) : null, evidence_requirement: blank(f.evidence) });
      if (kind === 'monitoring') Object.assign(body, { parameter: f.parameter, unit: blank(f.unit), frequency: blank(f.frequency) });
      if (kind === 'calculation') Object.assign(body, { step: f.step, equation_reference: blank(f.equation_reference) });
      if (kind === 'general') Object.assign(body, { rule_type: f.rule_type, parameters: f.parameters.trim() ? JSON.parse(f.parameters) : null });
    } catch {
      this.ruleError.set('Expected value / parameters must be valid JSON (e.g. ["CROPLAND"], 5, "COMPLETED", {"min_years": 5}).');
      return;
    }
    this.ruleError.set(null);
    runAction(this.api.addRule(this.id(), kind, body), this.busy, this.notify, 'Rule added.', () => {
      this.rule.patchValue({ rule_code: '', title: '', fact_key: '', expected: '', evidence: '', parameter: '', parameters: '' });
      this.load();
    });
  }

  removeRule(r: Rule): void {
    askReason(this.dialog, { title: `Remove rule ${r.rule_code} from this draft?`, confirmLabel: 'Remove', danger: true }).subscribe((x) => {
      if (x) runAction(this.api.deleteRule(this.id(), r.kind, r.id, x.reason), this.busy, this.notify, 'Rule removed.', () => this.load());
    });
  }

  act(action: 'submit' | 'approve' | 'return' | 'retire' | 'withdraw', title: string): void {
    askReason(this.dialog, { title: `${title}?`, confirmLabel: title, danger: action === 'retire' || action === 'withdraw',
      message: action === 'approve' ? 'Approving makes this version a candidate for projects. You cannot approve a version you submitted.' : undefined,
    }).subscribe((r) => {
      if (r) runAction(this.api.versionAction(this.id(), action, r.reason), this.busy, this.notify, 'Version updated.', (v) => {
        this.v.set(v);
        this.load();
      });
    });
  }
}
