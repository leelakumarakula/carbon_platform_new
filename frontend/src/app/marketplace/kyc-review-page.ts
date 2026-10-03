import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';

import { DocumentsApi } from '../core/api/documents.api';
import { NotifyService } from '../core/notify.service';
import { PageHeader } from '../shared/page-header';
import { askReason } from '../shared/reason-dialog';
import { runAction } from '../shared/run-action';
import { StatusBadge } from '../shared/status-badge';
import { MarketplaceApi } from './marketplace.api';
import { BuyerProfile, marketBadge, mlabel } from './marketplace.models';

/** Platform compliance: review buyer organizations' KYC — verify (or reinstate), return with a reason, suspend. Never the submitter. */
@Component({
  selector: 'app-kyc-review-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, MatButtonModule, PageHeader, StatusBadge],
  template: `
    <app-page-header title="Buyer KYC review" subtitle="Buyer organizations awaiting or holding KYC verification" />
    <div class="table-wrap"><table class="table" data-testid="kyc-queue">
      <thead><tr><th>Organization</th><th>Legal name</th><th>Status</th><th>Submitted</th><th>Documents</th><th></th></tr></thead>
      <tbody>
        @for (p of rows(); track p.id) {
          <tr [attr.data-org]="p.organization_code">
            <td>{{ p.organization_name }}<div class="small muted">{{ p.organization_code }}</div></td>
            <td>{{ p.legal_name }}@if (p.registration_number) { <div class="small">{{ p.registration_number }}</div> }</td>
            <td><app-status-badge [status]="badge(p.status)" [text]="label(p.status)" /></td>
            <td>@if (p.submitted_at) { {{ p.submitted_at | date: 'mediumDate' }} · {{ p.submitted_by_name }} }</td>
            <td>@for (d of p.documents; track d.document_id) { <button mat-button type="button" (click)="download(d.document_id, d.title)">{{ d.title }}</button> }</td>
            <td>
              @if (p.can_review && (p.status === 'KYC_SUBMITTED' || p.status === 'SUSPENDED')) {
                <button mat-flat-button type="button" [disabled]="busy()" (click)="act(p, 'verify')">{{ p.status === 'SUSPENDED' ? 'Reinstate' : 'Verify' }}</button>
              }
              @if (p.can_review && p.status === 'KYC_SUBMITTED') { <button mat-button type="button" [disabled]="busy()" (click)="act(p, 'return')">Return</button> }
              @if (p.can_review && p.status === 'KYC_VERIFIED') { <button mat-button type="button" [disabled]="busy()" (click)="act(p, 'suspend')">Suspend</button> }
            </td>
          </tr>
        } @empty { <tr><td colspan="6" class="muted" data-testid="no-kyc">No buyer profile.</td></tr> }
      </tbody>
    </table></div>
  `,
})
export class KycReviewPage implements OnInit {
  private readonly api = inject(MarketplaceApi);
  private readonly docs = inject(DocumentsApi);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotifyService);
  protected readonly label = mlabel;
  protected readonly badge = marketBadge;
  protected readonly rows = signal<BuyerProfile[]>([]);
  protected readonly busy = signal(false);

  ngOnInit(): void {
    this.reload();
  }

  private reload(): void {
    this.api.kycQueue().subscribe((r) => this.rows.set(r));
  }

  protected act(p: BuyerProfile, action: 'verify' | 'return' | 'suspend'): void {
    const title = { verify: `Verify ${p.legal_name}?`, return: `Return ${p.legal_name}'s KYC?`, suspend: `Suspend ${p.legal_name}?` }[action];
    askReason(this.dialog, { title, confirmLabel: mlabel(action), danger: action !== 'verify',
      message: action === 'suspend' ? 'A suspended buyer cannot place new orders; its existing holdings are never removed.' : undefined })
      .subscribe((x) => {
        if (!x) return;
        const body = action === 'verify' ? { note: x.reason } : { reason: x.reason };
        runAction(this.api.review(p.id, action, body), this.busy, this.notify, 'KYC decision recorded.', () => this.reload());
      });
  }

  protected download(id: string, title: string): void {
    this.docs.download(id, `${title}.pdf`).subscribe({ error: (e: unknown) => this.notify.error(e) });
  }
}
