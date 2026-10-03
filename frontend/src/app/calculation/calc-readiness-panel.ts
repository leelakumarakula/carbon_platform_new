import { DatePipe, JsonPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, effect, inject, input, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { Observable } from 'rxjs';

import { NotifyService } from '../core/notify.service';
import { label } from '../farmer/farmer.models';
import { askReason } from '../shared/reason-dialog';
import { runAction } from '../shared/run-action';
import { StatusBadge } from '../shared/status-badge';
import { blockerTitle } from './calculation.models';
import { PreverificationApi } from './preverification.api';
import { Manifest, READINESS_LABEL, ReadinessReview, ReadinessState, readinessBadge } from './preverification.models';

/** Internal verification readiness of one monitoring period. READY = internally approved for submission to verification; NOT verification. */
@Component({
  selector: 'app-calc-readiness-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, JsonPipe, MatButtonModule, StatusBadge],
  template: `
    <div class="panel" data-testid="readiness-panel">
      <h3>Verification readiness</h3>
      <p class="note warn" data-testid="readiness-label">{{ readinessLabel }}</p>
      @if (state(); as s) {
        <p class="small muted">{{ s.meaning }} The project status stays {{ s.project_status }}.</p>
        @if (s.blockers.length) {
          <ul class="blockers" data-testid="readiness-blockers">
            @for (b of s.blockers; track $index) { <li><strong>{{ title(b) }}</strong> — {{ b.message }}</li> }
          </ul>
        } @else { <p class="ok small" data-testid="readiness-ok">All internal prerequisites hold for {{ s.current_run_code }}.</p> }
        @if (s.calculation_blockers.length && !s.current_run_id) {
          <p class="small">Calculation blockers: @for (b of s.calculation_blockers; track $index) { <strong>{{ title(b) }}</strong>{{ $last ? '' : ', ' }} }</p>
        }
        @for (r of s.reviews; track r.id) {
          <div class="review" [attr.data-readiness]="r.readiness_code"><strong>{{ r.readiness_code }}</strong> · run {{ r.run_code }}
            <app-status-badge [status]="badge(r.status)" [text]="label(r.status)" />
            <span class="small muted"> · {{ r.created_at | date: 'short' }} {{ r.decision_notes ? '— ' + r.decision_notes : '' }}
              {{ r.invalidation_reason ? '— invalidated: ' + r.invalidation_reason : '' }}</span>
            <div class="row">
              @if (r.can_submit) { <button mat-flat-button type="button" [disabled]="busy()" (click)="act(api.submitReadiness(r.id), 'Submitted.')">Submit</button> }
              @if (r.can_approve) { <button mat-flat-button type="button" (click)="decide(r, 'Approve')" data-testid="approve-readiness">Approve (READY)</button> }
              @if (r.can_reject) { <button mat-button type="button" (click)="decide(r, 'Reject')">Reject</button> }
              @if (r.can_withdraw) { <button mat-button type="button" (click)="decide(r, 'Withdraw')">Withdraw</button> }
              @if (r.manifest_sha256) { <button mat-button type="button" (click)="showManifest(r)" data-testid="show-manifest">Package manifest</button> }
            </div>
          </div>
        }
        @if (s.can_create) {
          <button mat-stroked-button type="button" [disabled]="busy() || !s.ready_to_submit" (click)="create(s)" data-testid="create-readiness">
            Prepare readiness</button>
        }
      }
      @if (manifest(); as m) {
        <div class="manifest" data-testid="manifest"><p class="small">Manifest {{ m.readiness_code }} · SHA-256 <span class="mono">{{ m.manifest_sha256 }}</span></p>
          <pre class="mono">{{ m.manifest | json }}</pre></div>
      }
    </div>
  `,
  styles: `.panel { margin-top: 16px; } h3 { margin: 8px 0 4px; font: var(--mat-sys-title-small); } .blockers { padding-left: 20px; margin: 4px 0; }
    .review { padding: 4px 0; border-bottom: 1px solid var(--mat-sys-outline-variant); } .row { display: flex; gap: 6px; flex-wrap: wrap; }
    .mono { font-family: monospace; font-size: 11px; word-break: break-all; } pre { max-height: 320px; overflow: auto; white-space: pre-wrap; }
    .ok { color: var(--mat-sys-primary); }`,
})
export class CalcReadinessPanel {
  readonly projectId = input.required<string>();
  readonly periodId = input<string | null>(null);
  protected readonly api = inject(PreverificationApi);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotifyService);
  protected readonly label = label;
  protected readonly badge = readinessBadge;
  protected readonly title = blockerTitle;
  protected readonly readinessLabel = READINESS_LABEL;
  protected readonly state = signal<ReadinessState | null>(null);
  protected readonly manifest = signal<Manifest | null>(null);
  protected readonly busy = signal(false);

  constructor() {
    effect(() => {
      const id = this.periodId();
      this.state.set(null);
      this.manifest.set(null);
      if (id) this.load(id);
    });
  }

  private load(periodId: string): void {
    this.api.readiness(this.projectId(), periodId).subscribe((s) => this.state.set(s));
  }

  private reload(): void {
    const id = this.periodId();
    if (id) this.load(id);
  }

  protected act(obs: Observable<unknown>, message: string): void {
    runAction(obs, this.busy, this.notify, message, () => this.reload());
  }

  protected create(s: ReadinessState): void {
    this.act(this.api.createReadiness(s.project_id, s.monitoring_period_id), 'Readiness prepared (DRAFT).');
  }

  protected decide(r: ReadinessReview, what: 'Approve' | 'Reject' | 'Withdraw'): void {
    const call = { Approve: this.api.approveReadiness, Reject: this.api.rejectReadiness, Withdraw: this.api.withdrawReadiness }[what];
    askReason(this.dialog, { title: `${what} ${r.readiness_code}?`, confirmLabel: what, danger: what !== 'Approve',
      message: what === 'Approve' ? 'READY means internally approved for submission to verification. It is not verification.' : undefined })
      .subscribe((x) => { if (x) this.act(call(r.id, x.reason), `${what}: done.`); });
  }

  protected showManifest(r: ReadinessReview): void {
    this.api.manifest(r.id).subscribe((m) => this.manifest.set(m));
  }
}
