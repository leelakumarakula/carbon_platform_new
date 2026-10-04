import { ChangeDetectionStrategy, Component, OnInit, computed, inject, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatSelectModule } from '@angular/material/select';

import { AuthService } from '../core/auth/auth.service';
import { P } from '../core/auth/permissions';
import { NotifyService } from '../core/notify.service';
import { label } from '../farmer/farmer.models';
import { askReason } from '../shared/reason-dialog';
import { runAction } from '../shared/run-action';
import { StatusBadge } from '../shared/status-badge';
import { MethodologiesApi } from './methodologies.api';
import { CalculationModuleOption, VersionDetail } from './methodology.models';

/** Calculation tab: choose the registered calculation module for this version (copies its rule set; approved with the version)
 *  and run the production-readiness approval once the version is approved. */
@Component({
  selector: 'app-calculation-module-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, MatButtonModule, MatFormFieldModule, MatIconModule, MatSelectModule, StatusBadge],
  template: `
    <section class="panel" data-testid="calculation-module">
      <div class="head">
        <div>
          <h3>Calculation module</h3>
          <p class="muted small">The calculation is code written from the official methodology document. Choosing a module copies the
            calculation rules, monitoring rules and sampling settings it needs into this draft; approving the version approves the choice.</p>
        </div>
        @if (selected(); as s) {
          <app-status-badge [status]="ready() ? 'ACTIVE' : 'WARNING'" [text]="ready() ? 'Production ready' : 'Not production ready'" />
        }
      </div>

      @if (v().can_edit) {
        <div class="pick">
          <mat-form-field subscriptSizing="dynamic" class="grow"><mat-label>Calculation module</mat-label>
            <mat-select [(ngModel)]="choice" data-testid="module-select">
              <mat-option [value]="null">None (calculation not available)</mat-option>
              @for (o of options(); track o.code) {
                <mat-option [value]="o.code" [disabled]="!o.compatible">
                  {{ o.label }} · v{{ o.version }}{{ o.compatible ? '' : ' — for ' + o.methodology_code + ' ' + o.version_label }}
                </mat-option>
              }
            </mat-select>
          </mat-form-field>
          <button mat-flat-button type="button" (click)="select()" [disabled]="busy() || choice === (v().calculation_module_code ?? null)">
            {{ choice ? 'Use this module' : 'Clear' }}</button>
        </div>
        @if (!compatibleCount()) { <p class="muted small">No module is available for {{ v().methodology_code }} {{ v().version_label }} yet.</p> }
      }

      @if (selected(); as s) {
        <div class="card">
          <div class="title"><mat-icon>functions</mat-icon><strong>{{ s.label }}</strong> <span class="muted small">{{ s.code }} · v{{ s.version }}</span></div>
          <div class="cols">
            <div>
              <h4>Calculation steps</h4>
              <ol class="steps">
                @for (r of s.calculation_rules; track r.rule_code) {
                  <li><span class="code">{{ r.rule_code }}</span> {{ label(r.step) }} — {{ r.title }}
                    @if (r.equation_reference) { <div class="muted small">{{ r.equation_reference }}</div> }</li>
                }
              </ol>
            </div>
            <div>
              <h4>Data the module needs</h4>
              <ul class="data">
                @for (m of s.monitoring_rules; track m.rule_code) {
                  <li><span class="code">{{ m.rule_code }}</span> {{ m.title }}
                    <span class="muted small">{{ m.unit ? '(' + m.unit + ')' : '' }} · {{ label(m.measurement_source) }}{{ m.data_level ? ' · per ' + label(m.data_level).toLowerCase() : '' }}</span></li>
                }
              </ul>
              @if (samplingText(s); as t) { <p class="small"><strong>Sampling settings:</strong> {{ t }}</p> }
            </div>
          </div>
          <details>
            <summary>Interpretations used ({{ s.assumptions.length }}) — for the methodology expert's review</summary>
            <ul class="small">@for (a of s.assumptions; track $index) { <li>{{ a }}</li> }</ul>
          </details>
        </div>

        @if (v().status === 'APPROVED') {
          <div class="readiness" data-testid="readiness">
            <h4>Production readiness</h4>
            @if (ready()) {
              <p class="small">Approved for production: real credits may be calculated with this version.</p>
              @if (canApprove()) { <button mat-button type="button" class="danger" (click)="revoke()" [disabled]="busy()">Revoke</button> }
            } @else if (v().readiness_request; as req) {
              <p class="small">Requested {{ req.requested_at.slice(0, 10) }} — evidence: {{ req.evidence }}</p>
              @if (canApprove()) {
                <button mat-flat-button type="button" (click)="decide(true)" [disabled]="busy()">Approve</button>
                <button mat-button type="button" (click)="decide(false)" [disabled]="busy()">Reject</button>
                <p class="muted small">You cannot decide a request you made.</p>
              }
            } @else {
              <p class="small">Calculations run in testing only until a methodology expert has checked the module against the official
                document and a second person approves it.</p>
              @if (canManage()) { <button mat-stroked-button type="button" (click)="request()" [disabled]="busy()">Request production readiness</button> }
            }
          </div>
        }
      }
    </section>
  `,
  styles: `
    .panel { border: 1px solid var(--cp-line); border-radius: var(--cp-radius); background: #fff; padding: 14px 16px; margin-bottom: 14px; }
    .head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
    h3 { margin: 0 0 4px; font: 500 15px var(--cp-font); } h4 { margin: 10px 0 6px; font: 500 13px var(--cp-font); color: var(--cp-navy); }
    .pick { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin: 10px 0; } .grow { flex: 1; min-width: 280px; }
    .card { border: 1px solid var(--cp-line); border-radius: 10px; padding: 12px 14px; background: var(--cp-mint-2); margin-top: 8px; }
    .title { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; } .title mat-icon { color: var(--cp-forest); }
    .cols { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; } @media (max-width: 900px) { .cols { grid-template-columns: 1fr; } }
    .steps, .data { margin: 0; padding-left: 18px; font-size: 13px; } .steps li, .data li { margin: 3px 0; }
    .code { font: 600 11.5px ui-monospace, Consolas, monospace; color: var(--cp-forest); }
    .readiness { margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--cp-line); }
    details { margin-top: 8px; font-size: 13px; }
  `,
})
export class CalculationModulePanel implements OnInit {
  readonly v = input.required<VersionDetail>();
  readonly changed = output<VersionDetail>();
  private readonly api = inject(MethodologiesApi);
  private readonly notify = inject(NotifyService);
  private readonly dialog = inject(MatDialog);
  private readonly auth = inject(AuthService);
  protected readonly label = label;
  protected readonly busy = signal(false);
  protected readonly options = signal<CalculationModuleOption[]>([]);
  protected choice: string | null = null;
  protected readonly canManage = computed(() => this.auth.has(P.METHODOLOGIES_MANAGE));
  protected readonly canApprove = computed(() => this.auth.has(P.METHODOLOGIES_APPROVE));
  protected readonly selected = computed(() => this.options().find((o) => o.code === this.v().calculation_module_code) ?? null);
  protected readonly ready = computed(() => this.v().calculation_readiness === 'PRODUCTION_READY');
  protected readonly compatibleCount = computed(() => this.options().filter((o) => o.compatible).length);

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.choice = this.v().calculation_module_code ?? null;
    this.api.calculationModules(this.v().id).subscribe({ next: (o) => this.options.set(o), error: () => this.options.set([]) });
  }

  protected samplingText(s: CalculationModuleOption): string {
    return Object.entries(s.sampling_parameters).map(([k, val]) => `${label(k.toUpperCase())} = ${String(val)}`).join(' · ');
  }

  protected select(): void {
    const code = this.choice;
    askReason(this.dialog, { title: code ? 'Use this calculation module?' : 'Clear the calculation module?', confirmLabel: code ? 'Use module' : 'Clear',
      message: code ? 'Its calculation rules replace this draft\'s calculation rules; its monitoring rules and sampling settings are added.' : undefined })
      .subscribe((r) => {
        if (r) runAction(this.api.selectModule(this.v().id, code, r.reason), this.busy, this.notify,
          code ? 'Module selected; its rules were added to this draft.' : 'Module cleared.', (v) => { this.changed.emit(v); this.load(); });
      });
  }

  protected request(): void {
    askReason(this.dialog, { title: 'Request production readiness', confirmLabel: 'Request',
      message: 'Summarise the verification evidence: who checked the equations against the official document, and which worked examples pass.' })
      .subscribe((r) => {
        if (r) runAction(this.api.requestReadiness(this.v().id, r.reason), this.busy, this.notify, 'Readiness requested.', (v) => this.changed.emit(v));
      });
  }

  protected decide(approve: boolean): void {
    askReason(this.dialog, { title: approve ? 'Approve production readiness?' : 'Reject the request?', confirmLabel: approve ? 'Approve' : 'Reject',
      danger: !approve }).subscribe((r) => {
      if (r) runAction(this.api.decideReadiness(this.v().id, approve, r.reason), this.busy, this.notify,
        approve ? 'The calculation is production ready.' : 'Request rejected.', (v) => this.changed.emit(v));
    });
  }

  protected revoke(): void {
    askReason(this.dialog, { title: 'Revoke production readiness?', confirmLabel: 'Revoke', danger: true }).subscribe((r) => {
      if (r) runAction(this.api.revokeReadiness(this.v().id, r.reason), this.busy, this.notify, 'Production readiness revoked.', (v) => this.changed.emit(v));
    });
  }
}
