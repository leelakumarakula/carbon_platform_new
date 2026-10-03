import { DatePipe, JsonPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { ActivatedRoute } from '@angular/router';
import { Observable, switchMap } from 'rxjs';

import { DocumentsApi } from '../core/api/documents.api';
import { NotifyService } from '../core/notify.service';
import { PageHeader } from '../shared/page-header';
import { askReason } from '../shared/reason-dialog';
import { runAction } from '../shared/run-action';
import { StatusBadge } from '../shared/status-badge';
import { MarketplaceApi } from './marketplace.api';
import { LineageStep, NOT_INVOICE, Order, OrderItem, Orders, Payment, Refund, marketBadge, money, mlabel, newKey } from './marketplace.models';

/** Orders as buyer (pay with evidence, cancel, confirmation, lineage) or as seller (cancel unpaid orders, confirm payments, resolve
 *  orders that need attention, refunds). Ownership changes only when the custodian completes the ledger transfer. */
@Component({
  selector: 'app-orders-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, JsonPipe, FormsModule, MatButtonModule, MatFormFieldModule, MatInputModule, PageHeader, StatusBadge],
  template: `
    <app-page-header title="Orders" subtitle="Marketplace orders of your organization" />
    @if (list(); as l) {
      @if (l.demo_note) { <p class="note demo" data-testid="orders-demo-note"><app-status-badge status="DEMO" text="DEMO" /> {{ l.demo_note }}</p> }
      <div class="table-wrap"><table class="table" data-testid="orders">
        <thead><tr><th>Order</th><th>Buyer → seller</th><th>Total</th><th>Status</th><th>Payment deadline</th><th></th></tr></thead>
        <tbody>
          @for (o of l.orders; track o.id) {
            <tr [attr.data-order]="o.order_code"><td>{{ o.order_code }}</td><td>{{ o.buyer_name }} → {{ o.seller_name }}</td>
              <td>{{ money(o.total, o.currency) }}</td><td><app-status-badge [status]="badge(o.status)" [text]="label(o.status)" /></td>
              <td>{{ o.expires_at | date: 'medium' }}</td><td><button mat-button type="button" (click)="open(o.id)">Open</button></td></tr>
          } @empty { <tr><td colspan="6" class="muted" data-testid="no-orders">No order.</td></tr> }
        </tbody>
      </table></div>
    }

    @if (sel(); as o) {
      <section class="box" data-testid="order-detail">
        <h3>{{ o.order_code }} <app-status-badge [status]="badge(o.status)" [text]="label(o.status)" /></h3>
        <p class="small">{{ o.buyer_name }} → {{ o.seller_name }} · total {{ money(o.total, o.currency) }} (no fee, commission or tax) ·
          delivery {{ label(o.transfer_kind) }}@if (o.recipient_registry_account) { to {{ o.recipient_registry_account }} }</p>
        @if (o.attention_reason) { <p class="note warn" data-testid="attention">{{ o.attention_reason }}</p> }
        <table class="table"><thead><tr><th>Item</th><th>Batch · vintage</th><th>Quantity</th><th>Price</th><th>Line total</th><th>Reservation</th>
          <th>Delivery</th><th></th></tr></thead><tbody>
          @for (it of o.items; track it.id) {
            <tr [attr.data-item]="it.item_code"><td>{{ it.item_code }}<div class="small">{{ label(it.status) }}</div></td>
              <td>{{ it.batch_code }} · {{ it.vintage }}</td><td>{{ it.quantity }}</td><td>{{ money(it.unit_price, o.currency) }}</td>
              <td>{{ money(it.line_total, o.currency) }}</td><td>{{ it.reservation_code }} {{ it.reservation_status ? label(it.reservation_status) : '' }}</td>
              <td>{{ it.transfer_code }} {{ it.transfer_status ? label(it.transfer_status) : '' }}</td>
              <td>@if (it.can_complete) {
                <button mat-flat-button type="button" [disabled]="busy()" (click)="complete(it)">Complete delivery</button>
                <button mat-button type="button" [disabled]="busy()" (click)="rejectDelivery(it)">Reject</button> }</td></tr>
          }
        </tbody></table>

        @if (o.can_pay) {
          <div class="box inner" data-testid="pay-form"><h4>Record your payment of {{ money(o.total, o.currency) }}</h4>
            <p class="small muted">Pay the seller as agreed, then attach the payment evidence (PDF). The seller's finance team confirms it.</p>
            <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Payment reference (bank / transfer id)</mat-label>
              <input matInput [(ngModel)]="payRef" data-testid="pay-ref" /></mat-form-field>
            <input type="file" accept="application/pdf" data-testid="pay-file" (change)="pick($event)" />
            <button mat-flat-button type="button" data-testid="record-payment" [disabled]="busy() || !file" (click)="pay(o)">Record payment</button>
          </div>
        }
        <h4>Payments</h4>
        @for (p of o.payments; track p.id) {
          <div class="line" [attr.data-payment]="p.payment_code">{{ p.payment_code }} · {{ money(p.amount, p.currency) }} · <app-status-badge [status]="badge(p.status)" [text]="label(p.status)" />
            · recorded by {{ p.recorded_by_name }}@if (p.external_reference) { · ref {{ p.external_reference }} }
            @if (p.reject_reason) { · {{ p.reject_reason }} }
            @if (p.can_confirm) {
              <button mat-flat-button type="button" [disabled]="busy()" (click)="confirm(p)">Confirm receipt</button>
              <button mat-button type="button" [disabled]="busy()" (click)="rejectPayment(p)">Reject</button> }
            @if (p.can_refund) { <button mat-button type="button" [disabled]="busy()" (click)="refund(p)">Request refund</button> }
          </div>
        } @empty { <p class="small muted">No payment recorded.</p> }
        @if (o.refunds.length) {
          <h4>Refunds (money only — credits never move with a refund)</h4>
          @for (r of o.refunds; track r.id) {
            <div class="line">{{ r.refund_code }} · {{ money(r.amount, r.currency) }} · <app-status-badge [status]="badge(r.status)" [text]="label(r.status)" />
              @if (r.after_transfer) { · after delivery (credits stay with the buyer) } · {{ r.reason }}
              @if (r.can_approve) { <button mat-button type="button" [disabled]="busy()" (click)="approveRefund(r)">Approve</button>
                <button mat-button type="button" [disabled]="busy()" (click)="rejectRefund(r)">Reject</button> }
              @if (r.can_complete) {
                <input class="ref" placeholder="Refund reference" [(ngModel)]="refundRef[r.id]" />
                <input type="file" accept="application/pdf" (change)="pickRefund(r, $event)" />
                <button mat-flat-button type="button" [disabled]="busy() || !refundFile[r.id] || !refundRef[r.id]" (click)="completeRefund(r)">Record refund</button> }
            </div>
          }
        }
        <div class="row">
          @if (o.can_cancel) { <button mat-button type="button" data-testid="cancel-order" [disabled]="busy()" (click)="cancel(o)">Cancel order</button> }
          @if (o.can_retry) { <button mat-stroked-button type="button" [disabled]="busy()" (click)="retry(o)">Re-reserve and request delivery</button> }
          @if (paid(o)) { <button mat-button type="button" (click)="confirmation(o)">Order confirmation (PDF)</button> }
          <button mat-button type="button" (click)="showLineage(o)">Lineage</button>
        </div>
        <p class="small muted">{{ notInvoice }}</p>
        @if (lineage(); as l) { <pre class="mono" data-testid="order-lineage">{{ l | json }}</pre> }
      </section>
    }
  `,
  styles: `.box { border: 1px solid var(--mat-sys-outline-variant); border-radius: 8px; padding: 10px 12px; margin: 12px 0; }
    .box.inner { background: var(--mat-sys-surface-container-low); } .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-top: 8px; }
    .line { margin: 4px 0; } .wide { min-width: 260px; } .ref { width: 160px; } .warn { color: #7a5200; } .demo { display: flex; gap: 8px; align-items: center; }
    h3 { margin: 0 0 6px; font: var(--mat-sys-title-small); } h4 { margin: 10px 0 4px; }
    .mono { font-family: monospace; font-size: 11px; } pre { max-height: 300px; overflow: auto; white-space: pre-wrap; }`,
})
export class OrdersPage implements OnInit {
  private readonly api = inject(MarketplaceApi);
  private readonly docs = inject(DocumentsApi);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotifyService);
  private readonly route = inject(ActivatedRoute);
  protected readonly label = mlabel;
  protected readonly badge = marketBadge;
  protected readonly money = money;
  protected readonly notInvoice = NOT_INVOICE;
  protected readonly list = signal<Orders | null>(null);
  protected readonly sel = signal<Order | null>(null);
  protected readonly lineage = signal<LineageStep[] | null>(null);
  protected readonly busy = signal(false);
  protected payRef = '';
  protected file: File | undefined;
  protected refundRef: Record<string, string> = {};
  protected refundFile: Record<string, File | undefined> = {};
  private keys: Record<string, string> = {};

  ngOnInit(): void {
    this.reload();
    const id = this.route.snapshot.queryParamMap.get('id');
    if (id) this.open(id);
  }

  private reload(): void {
    this.api.orders().subscribe((l) => this.list.set(l));
  }

  open(id: string): void {
    this.lineage.set(null);
    this.api.order(id).subscribe((o) => this.sel.set(o));
  }

  private key(name: string): string {
    return (this.keys[name] ??= newKey());
  }

  private act<T>(obs: Observable<T>, message: string, keyName?: string): void {
    runAction(obs, this.busy, this.notify, message, () => {
      if (keyName) delete this.keys[keyName];
      this.reload();
      const o = this.sel();
      if (o) this.open(o.id);
    });
  }

  protected paid(o: Order): boolean {
    return ['PAID', 'TRANSFER_PENDING', 'COMPLETED', 'ATTENTION_REQUIRED', 'REFUND_PENDING', 'REFUNDED'].includes(o.status);
  }

  protected pick(ev: Event): void {
    this.file = (ev.target as HTMLInputElement).files?.[0];
  }

  protected pickRefund(r: Refund, ev: Event): void {
    this.refundFile[r.id] = (ev.target as HTMLInputElement).files?.[0];
  }

  protected pay(o: Order): void {
    const file = this.file;
    if (!file) return;
    this.act(this.api.orderDocument(o.id, file).pipe(switchMap((d) => this.api.recordPayment({ order_id: o.id, amount: o.total, currency: o.currency,
      external_reference: this.payRef.trim() || null, document_id: d.document_id }, this.key('pay-' + o.id)))),
    'Payment recorded — awaiting the seller\'s confirmation.', 'pay-' + o.id);
    this.file = undefined;
    this.payRef = '';
  }

  protected confirm(p: Payment): void {
    askReason(this.dialog, { title: `Confirm receipt of ${money(p.amount, p.currency)}?`, confirmLabel: 'Confirm receipt',
      message: 'Confirm only money actually received. This requests the ledger transfer to the buyer; the custodian completes it.' })
      .subscribe((x) => { if (x) this.act(this.api.confirmPayment(p.id, this.key('conf-' + p.id)), 'Payment confirmed — delivery requested.', 'conf-' + p.id); });
  }

  protected rejectPayment(p: Payment): void {
    askReason(this.dialog, { title: `Reject ${p.payment_code}?`, confirmLabel: 'Reject payment', danger: true })
      .subscribe((x) => { if (x) this.act(this.api.rejectPayment(p.id, x.reason), 'Payment rejected — the order stays open until its deadline.'); });
  }

  protected refund(p: Payment): void {
    askReason(this.dialog, { title: `Request a refund of ${p.payment_code}?`, confirmLabel: 'Request refund', danger: true,
      message: 'Money only: a refund never moves credits. After delivery the credits stay with the buyer.' })
      .subscribe((x) => { if (x) this.act(this.api.requestRefund(p.id, x.reason, newKey()), 'Refund requested — another person approves it.'); });
  }

  protected approveRefund(r: Refund): void {
    this.act(this.api.approveRefund(r.id, newKey()), 'Refund approved.');
  }

  protected rejectRefund(r: Refund): void {
    askReason(this.dialog, { title: `Reject ${r.refund_code}?`, confirmLabel: 'Reject refund', danger: true })
      .subscribe((x) => { if (x) this.act(this.api.rejectRefund(r.id, x.reason), 'Refund rejected.'); });
  }

  protected completeRefund(r: Refund): void {
    const file = this.refundFile[r.id];
    if (!file) return;
    this.act(this.api.refundDocument(r.id, file).pipe(switchMap((d) => this.api.completeRefund(r.id, {
      external_reference: (this.refundRef[r.id] ?? '').trim(), document_id: d.document_id }, this.key('rf-' + r.id)))), 'Refund recorded.', 'rf-' + r.id);
  }

  protected cancel(o: Order): void {
    askReason(this.dialog, { title: `Cancel ${o.order_code}?`, confirmLabel: 'Cancel order', danger: true,
      message: 'The reserved credits are released.' })
      .subscribe((x) => { if (x) this.act(this.api.cancel(o.id, x.reason, newKey()), 'Order cancelled.'); });
  }

  protected retry(o: Order): void {
    askReason(this.dialog, { title: `Resolve ${o.order_code}?`, confirmLabel: 'Re-reserve and request delivery',
      message: 'Credits are re-reserved from your available ledger credits where the reservation was lost, then the ledger transfer is requested.' })
      .subscribe((x) => { if (x) this.act(this.api.retry(o.id, x.reason, newKey()), 'Delivery requested again.'); });
  }

  protected complete(it: OrderItem): void {
    if (!it.transfer_id) return;
    const id = it.transfer_id;
    this.act(this.api.completeTransfer(id, {}, this.key('del-' + id)), 'Delivery completed — the buyer now holds the credits.', 'del-' + id);
  }

  protected rejectDelivery(it: OrderItem): void {
    const id = it.transfer_id;
    if (!id) return;
    askReason(this.dialog, { title: `Reject the delivery of ${it.item_code}?`, confirmLabel: 'Reject', danger: true,
      message: 'The credits return to the seller and the order needs attention (re-request or refund).' })
      .subscribe((x) => { if (x) this.act(this.api.rejectTransfer(id, x.reason), 'Delivery rejected.'); });
  }

  protected confirmation(o: Order): void {
    this.api.confirmation(o.id).pipe(switchMap((d) => this.docs.download(d.document_id, `${o.order_code}-confirmation.pdf`)))
      .subscribe({ error: (e: unknown) => this.notify.error(e) });
  }

  protected showLineage(o: Order): void {
    this.api.lineage(o.id).subscribe((l) => this.lineage.set(l.chain));
  }
}
