import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, input, output, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';

import { NotifyService } from '../../core/notify.service';
import { label } from '../../farmer/farmer.models';
import { askReason } from '../../shared/reason-dialog';
import { runAction } from '../../shared/run-action';
import { StatusBadge } from '../../shared/status-badge';
import { CarbonRight, Project } from '../project.models';
import { ProjectsApi } from '../projects.api';

/** Carbon-rights references per participating farm: who holds the rights and on what agreement / document /
 *  reference. Internal tracking only — the referenced agreement is the source. Reviewed by someone other than
 *  the person who recorded it. Records are ended or voided, never deleted. */
@Component({
  selector: 'app-project-rights-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, MatButtonModule, StatusBadge],
  template: `
    <div class="tab-body">
      @for (r of rights(); track r.id) {
        <div class="line" [class.off]="r.status !== 'ACTIVE'">
          <div class="grow">
            <strong>{{ r.farm_code }}</strong> · {{ r.holder_name }} <span class="muted small">({{ label(r.holder_type) }}{{ r.share_pct ? ', ' + r.share_pct + '%' : '' }})</span>
            <div class="muted small">
              {{ r.agreement_number ? 'Agreement ' + r.agreement_number : '' }}{{ r.reference ? (r.agreement_number ? ' · ' : '') + r.reference : '' }}
              {{ r.document_id ? ' · document attached' : '' }} · effective {{ r.effective_from }} → {{ r.effective_to ?? 'open' }}
              · recorded {{ r.created_at | date: 'mediumDate' }}
            </div>
            @if (r.review_notes) { <div class="muted small">Review: {{ r.review_notes }}</div> }
            @if (r.end_reason) { <div class="muted small">{{ label(r.status) }}: {{ r.end_reason }}</div> }
          </div>
          <app-status-badge [status]="r.verification_status === 'VERIFIED' ? 'ACTIVE' : r.verification_status === 'REJECTED' ? 'FAILED' : 'WARNING'"
                            [text]="label(r.verification_status)" />
          @if (r.status !== 'ACTIVE') { <app-status-badge status="REVOKED" [text]="label(r.status)" /> }
          @if (r.status === 'ACTIVE' && project().can_review && r.verification_status !== 'VERIFIED') {
            <button mat-button type="button" (click)="review(r, 'VERIFIED')" [disabled]="busy()">Verify</button>
            <button mat-button type="button" class="danger" (click)="review(r, 'REJECTED')" [disabled]="busy()">Reject</button>
          }
          @if (r.status === 'ACTIVE' && canEdit()) {
            <button mat-button type="button" (click)="end(r, 'ENDED')" [disabled]="busy()">End</button>
            <button mat-button type="button" class="danger" (click)="end(r, 'VOID')" [disabled]="busy()">Void</button>
          }
        </div>
      } @empty { <p class="muted">No carbon-rights records. Each farm gets one when it is added to the project.</p> }
      <p class="muted small">You cannot verify carbon rights you recorded yourself. Every active record must be verified before eligibility can be approved.</p>
    </div>
  `,
  styles: `
    .line { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--mat-sys-outline-variant); flex-wrap: wrap; }
    .off { opacity: .6; } .grow { flex: 1; min-width: 260px; } .danger { color: #b71c1c; }
  `,
})
export class ProjectRightsPanel implements OnInit {
  readonly project = input.required<Project>();
  readonly changed = output<void>();
  private readonly api = inject(ProjectsApi);
  private readonly notify = inject(NotifyService);
  private readonly dialog = inject(MatDialog);
  protected readonly label = label;
  protected readonly rights = signal<CarbonRight[]>([]);
  protected readonly busy = signal(false);
  protected readonly canEdit = computed(() => this.project().can_manage && this.project().is_editable);

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.api.carbonRights(this.project().id).subscribe((r) => this.rights.set(r));
  }

  review(r: CarbonRight, status: 'VERIFIED' | 'REJECTED'): void {
    askReason(this.dialog, { title: status === 'VERIFIED' ? `Verify carbon rights of ${r.holder_name}?` : `Reject carbon rights of ${r.holder_name}?`,
      message: 'Record what you checked (agreement, assignment letter, land record).', confirmLabel: status === 'VERIFIED' ? 'Verify' : 'Reject',
      danger: status === 'REJECTED' }).subscribe((x) => {
      if (x) runAction(this.api.reviewCarbonRight(this.project().id, r.id, status, x.reason), this.busy, this.notify, 'Review recorded.', () => {
        this.load();
        this.changed.emit();
      });
    });
  }

  end(r: CarbonRight, status: 'ENDED' | 'VOID'): void {
    askReason(this.dialog, { title: status === 'ENDED' ? 'End this carbon-rights record?' : 'Void this record (recorded in error)?',
      confirmLabel: status === 'ENDED' ? 'End' : 'Void', danger: true }).subscribe((x) => {
      if (x) runAction(this.api.endCarbonRight(this.project().id, r.id, status, x.reason), this.busy, this.notify, 'Record updated.', () => {
        this.load();
        this.changed.emit();
      });
    });
  }
}
