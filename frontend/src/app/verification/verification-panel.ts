import { DatePipe, JsonPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, effect, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { Observable } from 'rxjs';

import { NotifyService } from '../core/notify.service';
import { label } from '../farmer/farmer.models';
import { askReason } from '../shared/reason-dialog';
import { runAction } from '../shared/run-action';
import { StatusBadge } from '../shared/status-badge';
import { VerificationApi } from './verification.api';
import { VerificationFindings } from './verification-findings';
import {
  Assignment, CALCULATED_LABEL, DECISION_NOTE, Decision, Lineage, PeriodVerification, VERIFIED_QUANTITY_LABEL, VERIFIED_QUANTITY_NOTE, VvbOrg,
  assignmentBadge, decisionBadge, statedQuantity, submissionBadge,
} from './verification.models';

/** Project side of VVB / ACVA verification for one monitoring period (period records are authoritative). The project proposes the
 *  assignment, submits the Phase 8A READY package and answers findings; the external VVB accepts, reviews and decides. */
@Component({
  selector: 'app-verification-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, JsonPipe, FormsModule, MatButtonModule, MatFormFieldModule, MatInputModule, MatSelectModule, StatusBadge, VerificationFindings],
  template: `
    <div class="tab-body" data-testid="verification-panel">
      <p class="note">{{ decisionNote }} Verification only — no validation, registry, issuance or credits exist on this platform.</p>
      @if (!periodId()) { <p class="muted">Select a monitoring period.</p> }
      @if (state(); as s) {
        <div class="kv">
          <span data-testid="calculated-label">{{ calculatedLabel }}:</span>
          <strong>{{ s.calculated_value ? s.calculated_value + ' ' + s.calculated_unit : '—' }}</strong>
          · READY package {{ s.ready_review_code ?? 'none' }} · project status {{ label(s.project_status) }}
        </div>
        @if (s.current_decision; as d) {
          <div class="decision" data-testid="current-decision">
            <strong>{{ d.decision_code }}</strong> <app-status-badge [status]="dBadge(d)" [text]="label(d.outcome)" />
            by {{ d.vvb_organization_name }} ({{ d.decided_by_name }}) · {{ d.decided_at | date: 'short' }}
            @if (qty(d); as q) {
              <div data-testid="stated-quantity"><span>{{ quantityLabel }}:</span> <strong>{{ q }}</strong> <span class="small muted">{{ quantityNote }}</span></div>
            }
            <div class="small">{{ d.rationale }}</div>
            <div class="row">
              <button mat-button type="button" (click)="report(d)">VVB report (PDF)</button>
              <button mat-button type="button" (click)="showLineage(d)" data-testid="show-lineage">Lineage</button>
            </div>
          </div>
        }
        <h3>VVB assignments</h3>
        @for (a of s.assignments; track a.id) {
          <div class="assignment" [attr.data-assignment]="a.assignment_code">
            <div><strong>{{ a.assignment_code }}</strong> · {{ a.vvb_organization_name }}
              <app-status-badge [status]="aBadge(a.status)" [text]="label(a.status)" />
              <span class="small muted"> proposed {{ a.proposed_at | date: 'short' }} by {{ a.proposed_by_name }}</span></div>
            @if (a.coi_declaration) { <div class="small">COI declaration ({{ a.coi_declared_by_name }}, {{ a.coi_declared_at | date: 'short' }}): {{ a.coi_declaration }}</div> }
            @if (a.closed_reason) { <div class="small muted">{{ label(a.status) }} by {{ a.closed_side }}: {{ a.closed_reason }}</div> }
            <div class="row">
              @if (a.actions.includes('submit')) {
                <button mat-flat-button type="button" [disabled]="busy()" (click)="act(api.submit(a.id), 'READY package submitted to the VVB.')"
                        data-testid="submit-package">Submit READY package</button>
              }
              @if (a.actions.includes('withdraw')) { <button mat-button type="button" (click)="close(a, 'Withdraw')">Withdraw</button> }
              @if (a.actions.includes('terminate')) { <button mat-button type="button" (click)="close(a, 'Terminate')">Terminate</button> }
            </div>
            @for (x of a.submissions; track x.id) {
              <div class="small sub" [attr.data-submission]="x.submission_code">{{ x.submission_code }} (#{{ x.seq }})
                <app-status-badge [status]="sBadge(x.status)" [text]="label(x.status)" /> · readiness {{ x.readiness_code }} · run {{ x.run_code }}
                · report {{ x.report_code }} v{{ x.report_version }} · manifest <span class="mono">{{ x.manifest_sha256.slice(0, 12) }}…</span>
                {{ x.closed_reason ? '— ' + x.closed_reason : '' }}</div>
            }
            @if (a.current_submission; as cur) {
              <h4>Findings on {{ cur.submission_code }}</h4>
              <app-verification-findings [submissionId]="cur.id" side="PROJECT" [canAct]="a.actions.includes('respond')" (changed)="reload()" />
            }
            @for (d of a.decisions; track d.id) {
              <div class="small">Decision {{ d.decision_code }} <app-status-badge [status]="dBadge(d)" [text]="label(d.outcome) + ' · ' + label(d.status)" />
                {{ d.superseded_reason ? '— ' + d.superseded_reason : '' }}</div>
            }
          </div>
        } @empty { <p class="muted small" data-testid="no-assignment">No VVB assignment for this period.</p> }
        @if (s.submit_blockers.length && s.can_manage) {
          <ul class="small blockers" data-testid="submit-blockers">@for (b of s.submit_blockers; track $index) { <li>{{ b }}</li> }</ul>
        }
        @if (s.can_manage && !hasOpen(s)) {
          <h4>Propose a VVB assignment</h4>
          <div class="row">
            <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>VVB / ACVA organization</mat-label>
              <mat-select [(ngModel)]="vvbOrgId" data-testid="vvb-org">
                @for (o of orgs(); track o.id) { <mat-option [value]="o.id">{{ o.name }}</mat-option> }</mat-select></mat-form-field>
            <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Notes (optional)</mat-label><input matInput [(ngModel)]="notes" /></mat-form-field>
            <button mat-flat-button type="button" [disabled]="busy() || !vvbOrgId" (click)="propose(s)" data-testid="propose-assignment">Propose</button>
          </div>
        }
      }
      @if (lineage(); as l) { <pre class="mono" data-testid="lineage">{{ l.chain | json }}</pre> }
    </div>
  `,
  styles: `h3 { margin: 14px 0 6px; font: var(--mat-sys-title-small); } h4 { margin: 10px 0 4px; }
    .assignment, .decision { border: 1px solid var(--mat-sys-outline-variant); border-radius: 8px; padding: 8px 10px; margin: 6px 0; }
    .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-top: 6px; } .wide { min-width: 220px; flex: 1; }
    .sub { margin: 2px 0 2px 12px; } .mono { font-family: monospace; font-size: 11px; word-break: break-all; }
    pre { max-height: 320px; overflow: auto; white-space: pre-wrap; } .blockers { padding-left: 20px; }`,
})
export class VerificationPanel {
  readonly projectId = input.required<string>();
  readonly periodId = input<string | null>(null);
  protected readonly api = inject(VerificationApi);
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
  protected readonly state = signal<PeriodVerification | null>(null);
  protected readonly orgs = signal<VvbOrg[]>([]);
  protected readonly lineage = signal<Lineage | null>(null);
  protected readonly busy = signal(false);
  protected vvbOrgId = '';
  protected notes = '';

  constructor() {
    effect(() => {
      const id = this.periodId();
      this.state.set(null);
      this.lineage.set(null);
      if (id) this.load(id);
    });
  }

  private load(periodId: string): void {
    this.api.period(this.projectId(), periodId).subscribe((s) => {
      this.state.set(s);
      if (s.can_manage && !this.orgs().length) this.api.vvbOrgs(this.projectId()).subscribe((o) => this.orgs.set(o));
    });
  }

  reload(): void {
    const id = this.periodId();
    if (id) this.load(id);
  }

  protected hasOpen(s: PeriodVerification): boolean {
    return s.assignments.some((a) => a.status === 'PROPOSED' || a.status === 'ACCEPTED');
  }

  protected act(obs: Observable<unknown>, message: string): void {
    runAction(obs, this.busy, this.notify, message, () => this.reload());
  }

  protected propose(s: PeriodVerification): void {
    const prev = s.assignments.find((a) => !['PROPOSED', 'ACCEPTED'].includes(a.status));
    const body = { monitoring_period_id: s.monitoring_period_id, vvb_organization_id: this.vvbOrgId, notes: this.notes.trim() || null,
      previous_assignment_id: prev?.id ?? null };
    this.act(this.api.propose(this.projectId(), body), 'Assignment proposed to the VVB.');
    this.notes = '';
  }

  protected close(a: Assignment, what: 'Withdraw' | 'Terminate'): void {
    const call = what === 'Withdraw' ? this.api.withdraw : this.api.terminate;
    askReason(this.dialog, { title: `${what} ${a.assignment_code}?`, confirmLabel: what, danger: true,
      message: 'Closed assignments are never reactivated; a replacement assignment can be proposed afterwards.' })
      .subscribe((x) => { if (x) this.act(call(a.id, x.reason), `${what}: done.`); });
  }

  protected report(d: Decision): void {
    this.api.report(d).subscribe({ error: (e: unknown) => this.notify.error(e) });
  }

  protected showLineage(d: Decision): void {
    this.api.lineage(d.id).subscribe((l) => this.lineage.set(l));
  }
}
