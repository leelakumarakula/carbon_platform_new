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

import { NotifyService } from '../core/notify.service';
import { label } from '../farmer/farmer.models';
import { PageHeader } from '../shared/page-header';
import { askReason } from '../shared/reason-dialog';
import { runAction } from '../shared/run-action';
import { StatusBadge } from '../shared/status-badge';
import { VerificationFindings } from './verification-findings';
import { VvbApi } from './verification.api';
import {
  Assignment, CALCULATED_LABEL, DECISION_NOTE, Decision, Package, VDocument, VERIFIED_QUANTITY_LABEL, VERIFIED_QUANTITY_NOTE,
  assignmentBadge, decisionBadge, statedQuantity, submissionBadge,
} from './verification.models';

/** One assignment in the VVB workspace: accept (with COI) / decline, the submitted package (allow-list view), manifest documents,
 *  findings and corrective actions, and recording the VVB's own external decision with its report PDF. */
@Component({
  selector: 'app-vvb-assignment-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, JsonPipe, FormsModule, MatButtonModule, MatFormFieldModule, MatInputModule, MatSelectModule, MatTabsModule, PageHeader,
    StatusBadge, VerificationFindings],
  template: `
    @if (a(); as a) {
      <app-page-header [title]="a.assignment_code" [subtitle]="(a.project_code ?? '') + ' · ' + (a.project_name ?? '') + ' · period #' + a.period_number"
                       backLink="/vvb" backLabel="VVB workspace" />
      <div class="status-row"><app-status-badge [status]="aBadge(a.status)" [text]="label(a.status)" />
        @if (a.environment === 'DEMO') { <app-status-badge status="DEMO" text="DEMO" /> }
        <span class="small muted">proposed {{ a.proposed_at | date: 'short' }} by {{ a.proposed_by_name }}{{ a.notes ? ' · ' + a.notes : '' }}</span></div>
      <p class="note">{{ decisionNote }}</p>
      @if (a.coi_declaration) { <p class="small" data-testid="coi">COI declaration ({{ a.coi_declared_by_name }}, {{ a.coi_declared_at | date: 'short' }}): {{ a.coi_declaration }}</p> }
      @if (a.actions.includes('accept')) {
        <div class="box">
          <mat-form-field class="full" subscriptSizing="dynamic"><mat-label>Conflict-of-interest declaration (required to accept)</mat-label>
            <textarea matInput rows="3" [(ngModel)]="coi" data-testid="coi-input"></textarea></mat-form-field>
          <div class="row">
            <button mat-flat-button type="button" [disabled]="busy() || coi.trim().length < 10" (click)="accept(a)" data-testid="accept-assignment">Accept</button>
            <button mat-button type="button" (click)="withReason(a, 'Decline')" data-testid="decline-assignment">Decline</button>
          </div>
        </div>
      }
      @if (a.actions.includes('terminate')) { <button mat-button type="button" (click)="withReason(a, 'Terminate')">Terminate assignment</button> }
      @for (x of a.submissions; track x.id) {
        <div class="small" [attr.data-submission]="x.submission_code">{{ x.submission_code }} (#{{ x.seq }})
          <app-status-badge [status]="sBadge(x.status)" [text]="label(x.status)" /> · submitted {{ x.submitted_at | date: 'short' }}
          {{ x.closed_reason ? '— ' + x.closed_reason : '' }}</div>
      }
      @if (a.status === 'ACCEPTED' && !a.current_submission) {
        <p class="muted" data-testid="no-package">No package submitted yet. The project submits once its Phase 8A READY package is valid.</p>
      }
      @if (pkg(); as p) {
        <mat-tab-group animationDuration="0ms" mat-stretch-tabs="false">
          <mat-tab label="Package"><div class="tab-body" data-testid="vvb-package">
            <p class="note warn">{{ calculatedLabel }}: <strong>{{ p.submission.calculated_value ?? '—' }} {{ p.submission.calculated_unit }}</strong></p>
            <div class="kv small">Methodology {{ p.methodology.code }} {{ p.methodology.version_label }} · report {{ p.report?.report_code }} v{{ p.report?.version }}
              · manifest SHA-256 <span class="mono">{{ p.manifest_sha256 }}</span></div>
            <h3>Farms in the sample</h3>
            <div class="table-wrap"><table class="table"><thead><tr><th>Farm</th><th>Farmer code</th><th>Area (ha)</th><th>Boundary</th></tr></thead><tbody>
              @for (f of p.farms; track f.farm_id) { <tr><td>{{ f.farm_code }}</td><td>{{ f.farmer_code }}</td><td>{{ f.area_hectares }}</td><td>v{{ f.boundary_version }}</td></tr> }
            </tbody></table></div>
            <h3>Sampling points ({{ p.dataset.sampling_points.length }}) · field collections ({{ p.dataset.field_collections.length }})</h3>
            <div class="small">@for (pt of p.dataset.sampling_points; track pt.id) { {{ pt.code }} ({{ pt.lat }}, {{ pt.lon }}){{ $last ? '' : '; ' }} }</div>
            <h3>Laboratory results</h3>
            <div class="small">@for (r of p.laboratory_results; track r.result_id) { <div>{{ r.sample }} v{{ r.version }}: {{ r.value_number ?? r.value_text }} {{ r.unit }}</div> }</div>
            <h3>Calculation</h3>
            <div class="table-wrap"><table class="table"><thead><tr><th>#</th><th>Output</th><th>Rule</th><th>Value</th></tr></thead><tbody>
              @for (o of p.calculation.outputs; track o.id) { <tr><td>{{ o.seq }}</td><td>{{ o.output_code }}{{ o.is_final ? ' (final)' : '' }}</td><td>{{ o.rule_code }}</td><td>{{ o.value }} {{ o.unit }}</td></tr> }
            </tbody></table></div>
            <details><summary class="small">Inputs ({{ p.calculation.inputs.length }})</summary>
              @for (i of p.calculation.inputs; track i.id) { <div class="small">#{{ i.seq }} {{ i.variable_code }} = {{ i.value }} {{ i.unit }} · {{ i.source_type }} {{ i.source_code }}</div> }
            </details>
            <details><summary class="small">Manifest (as submitted)</summary><pre class="mono">{{ p.manifest | json }}</pre></details>
          </div></mat-tab>
          <mat-tab label="Documents"><div class="tab-body">
            <p class="small muted">Only documents referenced by the submitted manifest or attached to this submission. Every download is audited.</p>
            @for (d of p.documents; track d.document_id) {
              <div class="row" [attr.data-doc]="d.category"><span>{{ d.title }} · {{ label(d.category) }} · {{ d.source }}</span>
                <span class="mono">{{ d.sha256?.slice(0, 12) }}…</span>
                <button mat-button type="button" (click)="download(p, d)">Download</button></div>
            } @empty { <p class="muted small">No document.</p> }
          </div></mat-tab>
          <mat-tab label="Findings"><div class="tab-body">
            <app-verification-findings [submissionId]="p.submission.id" side="VVB" [canAct]="a.status === 'ACCEPTED' && p.submission.status === 'SUBMITTED'"
                                       (changed)="reload()" />
          </div></mat-tab>
          <mat-tab label="Decision"><div class="tab-body" data-testid="vvb-decision">
            @for (d of a.decisions; track d.id) {
              <div class="box"><strong>{{ d.decision_code }}</strong> <app-status-badge [status]="dBadge(d)" [text]="label(d.outcome) + ' · ' + label(d.status)" />
                {{ d.decided_at | date: 'short' }} · {{ d.decided_by_name }}
                @if (qty(d); as q) { <div>{{ quantityLabel }}: <strong>{{ q }}</strong> <span class="small muted">{{ quantityNote }}</span></div> }
                <div class="small">{{ d.rationale }}</div>
                <button mat-button type="button" (click)="report(d)">Report (PDF)</button></div>
            }
            @if (a.decision_blockers.length) {
              <ul class="small" data-testid="decision-blockers">@for (b of a.decision_blockers; track $index) { <li>{{ b }}</li> }</ul>
            }
            @if (a.actions.includes('decide')) {
              <div class="box">
                <div class="row">
                  <mat-form-field subscriptSizing="dynamic"><mat-label>Outcome</mat-label>
                    <mat-select [(ngModel)]="outcome"><mat-option value="VERIFIED">Verified</mat-option><mat-option value="NOT_VERIFIED">Not verified</mat-option></mat-select></mat-form-field>
                  @if (outcome === 'VERIFIED') {
                    <mat-form-field subscriptSizing="dynamic"><mat-label>{{ quantityLabel }} (optional)</mat-label><input matInput [(ngModel)]="quantity" /></mat-form-field>
                    <mat-form-field subscriptSizing="dynamic"><mat-label>Unit</mat-label><input matInput [(ngModel)]="unit" /></mat-form-field>
                  }
                </div>
                <mat-form-field class="full" subscriptSizing="dynamic"><mat-label>Rationale</mat-label><textarea matInput rows="3" [(ngModel)]="rationale"></textarea></mat-form-field>
                <div class="row"><label class="small">Verification report (PDF, required) <input type="file" accept="application/pdf" (change)="pick($event)" /></label>
                  <button mat-flat-button type="button" [disabled]="busy() || !file || rationale.trim().length < 3 || (quantity.trim() !== '' && unit.trim() === '')"
                          (click)="decide(p)">Record decision</button></div>
              </div>
            }
          </div></mat-tab>
        </mat-tab-group>
      }
    }
  `,
  styles: `.status-row { display: flex; gap: 6px; margin: -8px 0 12px; flex-wrap: wrap; align-items: center; } h3 { margin: 12px 0 4px; font: var(--mat-sys-title-small); }
    .box { border: 1px solid var(--mat-sys-outline-variant); border-radius: 8px; padding: 8px 10px; margin: 8px 0; } .full { width: 100%; }
    .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-top: 6px; } .mono { font-family: monospace; font-size: 11px; word-break: break-all; }
    pre { max-height: 360px; overflow: auto; white-space: pre-wrap; }`,
})
export class VvbAssignmentPage implements OnInit {
  readonly id = input.required<string>();
  private readonly api = inject(VvbApi);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotifyService);
  protected readonly label = label;
  protected readonly aBadge = assignmentBadge;
  protected readonly sBadge = submissionBadge;
  protected readonly dBadge = decisionBadge;
  protected readonly qty = statedQuantity;
  protected readonly calculatedLabel = CALCULATED_LABEL;
  protected readonly quantityLabel = VERIFIED_QUANTITY_LABEL;
  protected readonly quantityNote = VERIFIED_QUANTITY_NOTE;
  protected readonly decisionNote = DECISION_NOTE;
  protected readonly a = signal<Assignment | null>(null);
  protected readonly pkg = signal<Package | null>(null);
  protected readonly busy = signal(false);
  protected coi = '';
  protected outcome: 'VERIFIED' | 'NOT_VERIFIED' = 'VERIFIED';
  protected quantity = '';
  protected unit = '';
  protected rationale = '';
  protected file: File | null = null;

  ngOnInit(): void {
    this.reload();
  }

  reload(): void {
    this.api.assignment(this.id()).subscribe((a) => {
      this.a.set(a);
      const s = a.current_submission ?? a.submissions.at(-1) ?? null;
      if (s && a.status !== 'PROPOSED') this.api.package(s.id).subscribe((p) => this.pkg.set(p));
      else this.pkg.set(null);
    });
  }

  private act(obs: Observable<unknown>, message: string): void {
    runAction(obs, this.busy, this.notify, message, () => this.reload());
  }

  protected accept(a: Assignment): void {
    this.act(this.api.accept(a.id, this.coi.trim()), 'Assignment accepted; COI declaration recorded.');
  }

  protected withReason(a: Assignment, what: 'Decline' | 'Terminate'): void {
    const call = what === 'Decline' ? this.api.decline : this.api.terminate;
    askReason(this.dialog, { title: `${what} ${a.assignment_code}?`, confirmLabel: what, danger: true })
      .subscribe((x) => { if (x) this.act(call(a.id, x.reason), `${what}: done.`); });
  }

  protected download(p: Package, d: VDocument): void {
    this.api.download(p.submission.id, d).subscribe({ error: (e: unknown) => this.notify.error(e) });
  }

  protected report(d: Decision): void {
    this.api.report(d).subscribe({ error: (e: unknown) => this.notify.error(e) });
  }

  protected pick(ev: Event): void {
    this.file = (ev.target as HTMLInputElement).files?.[0] ?? null;
  }

  protected decide(p: Package): void {
    if (!this.file) return;
    const fields: Record<string, string> = { outcome: this.outcome, rationale: this.rationale.trim() };
    if (this.outcome === 'VERIFIED' && this.quantity.trim()) {
      fields['verified_quantity'] = this.quantity.trim();
      fields['verified_quantity_unit'] = this.unit.trim();
    }
    this.act(this.api.decide(p.submission.id, this.file, fields), 'Decision recorded.');
  }
}
