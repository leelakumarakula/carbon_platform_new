import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { RouterLink } from '@angular/router';
import { Observable } from 'rxjs';

import { NotifyService } from '../core/notify.service';
import { PageHeader } from '../shared/page-header';
import { askReason } from '../shared/reason-dialog';
import { runAction } from '../shared/run-action';
import { StatusBadge } from '../shared/status-badge';
import { MarketplaceApi } from './marketplace.api';
import { Payment, Refund, marketBadge, money, mlabel, newKey } from './marketplace.models';

/** Seller finance (the payee): confirm received payments (never one you recorded — this requests the ledger delivery), reject, request /
 *  approve refunds (money only). Refund completion with evidence happens on the order. */
@Component({
  selector: 'app-payments-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, MatButtonModule, RouterLink, PageHeader, StatusBadge],
  template: `
    <app-page-header title="Payments" subtitle="Buyer payments to your organization and refunds" />
    <p class="note">LIVE payments are recorded manually with evidence until a payment provider is contracted; nothing is confirmed
      automatically. No fee or commission is deducted.</p>
    <div class="table-wrap"><table class="table" data-testid="payments">
      <thead><tr><th>Payment</th><th>Order</th><th>Payer</th><th>Amount</th><th>Status</th><th>Recorded</th><th></th></tr></thead>
      <tbody>
        @for (p of payments(); track p.id) {
          <tr [attr.data-payment]="p.payment_code"><td>{{ p.payment_code }}<div class="small muted">{{ p.adapter_code }}</div></td>
            <td><a routerLink="/orders" [queryParams]="{ id: p.order_id }">{{ p.order_code }}</a></td><td>{{ p.payer_name }}</td>
            <td>{{ money(p.amount, p.currency) }}</td><td><app-status-badge [status]="badge(p.status)" [text]="label(p.status)" /></td>
            <td>{{ p.recorded_at | date: 'medium' }} · {{ p.recorded_by_name }}</td>
            <td>@if (p.can_confirm) {
                <button mat-flat-button type="button" [disabled]="busy()" (click)="confirm(p)">Confirm receipt</button>
                <button mat-button type="button" [disabled]="busy()" (click)="reject(p)">Reject</button> }
              @if (p.can_refund) { <button mat-button type="button" [disabled]="busy()" (click)="refund(p)">Request refund</button> }</td></tr>
        } @empty { <tr><td colspan="7" class="muted" data-testid="no-payments">No payment.</td></tr> }
      </tbody>
    </table></div>
    <h3>Refunds</h3>
    <div class="table-wrap"><table class="table" data-testid="refunds">
      <thead><tr><th>Refund</th><th>Order</th><th>Amount</th><th>Status</th><th>Reason</th><th></th></tr></thead>
      <tbody>
        @for (r of refunds(); track r.id) {
          <tr><td>{{ r.refund_code }}</td><td><a routerLink="/orders" [queryParams]="{ id: r.order_id }">{{ r.order_code }}</a></td>
            <td>{{ money(r.amount, r.currency) }}@if (r.after_transfer) { <div class="small">after delivery — credits stay with the buyer</div> }</td>
            <td><app-status-badge [status]="badge(r.status)" [text]="label(r.status)" /></td><td>{{ r.reason }}</td>
            <td>@if (r.can_approve) { <button mat-button type="button" [disabled]="busy()" (click)="approve(r)">Approve</button>
              <button mat-button type="button" [disabled]="busy()" (click)="rejectRefund(r)">Reject</button> }
              @if (r.can_complete) { <a mat-button routerLink="/orders" [queryParams]="{ id: r.order_id }">Record refund on the order</a> }</td></tr>
        } @empty { <tr><td colspan="6" class="muted">No refund.</td></tr> }
      </tbody>
    </table></div>
  `,
  styles: `h3 { margin: 16px 0 6px; font: var(--mat-sys-title-small); }`,
})
export class PaymentsPage implements OnInit {
  private readonly api = inject(MarketplaceApi);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotifyService);
  protected readonly label = mlabel;
  protected readonly badge = marketBadge;
  protected readonly money = money;
  protected readonly payments = signal<Payment[]>([]);
  protected readonly refunds = signal<Refund[]>([]);
  protected readonly busy = signal(false);

  ngOnInit(): void {
    this.reload();
  }

  private reload(): void {
    this.api.payments().subscribe((p) => this.payments.set(p));
    this.api.refunds().subscribe((r) => this.refunds.set(r));
  }

  private act<T>(obs: Observable<T>, message: string): void {
    runAction(obs, this.busy, this.notify, message, () => this.reload());
  }

  protected confirm(p: Payment): void {
    askReason(this.dialog, { title: `Confirm receipt of ${money(p.amount, p.currency)}?`, confirmLabel: 'Confirm receipt',
      message: 'Confirm only money actually received. This requests the ledger transfer to the buyer; the custodian completes it.' })
      .subscribe((x) => { if (x) this.act(this.api.confirmPayment(p.id, newKey()), 'Payment confirmed — delivery requested.'); });
  }

  protected reject(p: Payment): void {
    askReason(this.dialog, { title: `Reject ${p.payment_code}?`, confirmLabel: 'Reject payment', danger: true })
      .subscribe((x) => { if (x) this.act(this.api.rejectPayment(p.id, x.reason), 'Payment rejected.'); });
  }

  protected refund(p: Payment): void {
    askReason(this.dialog, { title: `Request a refund of ${p.payment_code}?`, confirmLabel: 'Request refund', danger: true,
      message: 'Money only: a refund never moves credits.' })
      .subscribe((x) => { if (x) this.act(this.api.requestRefund(p.id, x.reason, newKey()), 'Refund requested.'); });
  }

  protected approve(r: Refund): void {
    this.act(this.api.approveRefund(r.id, newKey()), 'Refund approved.');
  }

  protected rejectRefund(r: Refund): void {
    askReason(this.dialog, { title: `Reject ${r.refund_code}?`, confirmLabel: 'Reject refund', danger: true })
      .subscribe((x) => { if (x) this.act(this.api.rejectRefund(r.id, x.reason), 'Refund rejected.'); });
  }
}
