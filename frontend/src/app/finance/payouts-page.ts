import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { Observable } from 'rxjs';

import { AuthService } from '../core/auth/auth.service';
import { P } from '../core/auth/permissions';
import { NotifyService } from '../core/notify.service';
import { PageHeader } from '../shared/page-header';
import { askReason } from '../shared/reason-dialog';
import { runAction } from '../shared/run-action';
import { StatusBadge } from '../shared/status-badge';
import { FinanceApi } from './finance.api';
import { Adjustment, FIN_DEMO_NOTE, Payout, finBadge, label, money, newKey } from './finance.models';
import { FIN_STYLES } from './project-picker';

/** Payouts: calculated from approved settlement runs (never typed), approved by someone other than the calculator to the farmer's VERIFIED
 *  bank account (last 4 shown), executed manually at the bank by a third person who records the reference and a remittance PDF (PAID),
 *  then reconciled against a statement by someone other than the executor (RECONCILED). Recovery cases are closed manually. */
@Component({
  selector: 'app-payouts-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, MatButtonModule, MatFormFieldModule, MatInputModule, PageHeader, StatusBadge],
  template: `
    <app-page-header title="Payouts" subtitle="Farmer payouts, execution and reconciliation" />
    @if (demo) { <p class="note warn" data-testid="fin-demo-note">{{ demoNote }}</p> }
    <p class="note">No payout provider is contracted: payouts are paid manually at the bank and recorded with evidence. Paid is not reconciled —
      a different person matches each payout to a bank statement. No fee or tax is deducted.</p>
    <div class="table-wrap"><table class="table" data-testid="payouts">
      <thead><tr><th>Payout</th><th>Farmer</th><th>Amount</th><th>Bank</th><th>Status</th><th>Reference</th><th></th></tr></thead>
      <tbody>
        @for (p of payouts(); track p.id) {
          <tr [attr.data-payout]="p.payout_code"><td>{{ p.payout_code }}<div class="small muted">{{ p.run_code }}@if (p.replaces_payout_code) { · replaces {{ p.replaces_payout_code }} }</div></td>
            <td>{{ p.farmer_name }}</td><td>{{ money(p.amount, p.currency) }}</td><td>{{ p.bank_last4 ? '••••' + p.bank_last4 : '—' }}</td>
            <td><app-status-badge [status]="badge(p.status)" [text]="label(p.status)" />@if (p.reason) { <div class="small">{{ p.reason }}</div> }</td>
            <td class="small">{{ p.external_reference ?? '—' }}@for (r of p.reconciliations; track r.id) { <div>{{ r.result }} · {{ r.statement_reference }}</div> }</td>
            <td>
              @if (can.calc && p.status === 'CALCULATED') { <button mat-button type="button" [disabled]="busy()" (click)="act(p, 'submit')">Submit</button> }
              @if (can.calc && (p.status === 'CALCULATED' || p.status === 'PENDING_APPROVAL' || p.status === 'ON_HOLD')) {
                <button mat-button type="button" [disabled]="busy()" (click)="withReason(p, 'cancel')">Cancel</button> }
              @if (can.calc && p.status === 'ON_HOLD') { <button mat-button type="button" [disabled]="busy()" (click)="withReason(p, 'release-hold')">Back to approval</button> }
              @if (can.calc && p.status === 'FAILED') { <button mat-button type="button" [disabled]="busy()" (click)="act(p, 'reissue')">Reissue</button> }
              @if (can.approve && p.status === 'PENDING_APPROVAL') { <button mat-button type="button" [disabled]="busy()" (click)="act(p, 'approve')">Approve</button>
                <button mat-button type="button" [disabled]="busy()" (click)="withReason(p, 'reject')">Reject</button> }
              @if (can.execute && p.status === 'APPROVED') { <button mat-flat-button type="button" [disabled]="busy()" (click)="act(p, 'initiate')">Execute</button> }
              @if (can.execute && (p.status === 'PAYMENT_PENDING' || p.status === 'UNCONFIRMED')) {
                <button mat-button type="button" [disabled]="busy()" (click)="openPaid(p)">Record paid</button>
                <button mat-button type="button" [disabled]="busy()" (click)="withReason(p, 'fail')">Failed</button> }
              @if (can.reconcile && p.status === 'PAID') { <button mat-button type="button" [disabled]="busy()" (click)="openRec(p)">Reconcile</button> }
            </td></tr>
        } @empty { <tr><td colspan="7" class="muted" data-testid="no-payouts">No payout.</td></tr> }
      </tbody>
    </table></div>
    @if (paying(); as p) {
      <section class="box" data-testid="paid-form"><h3>Record payment of {{ p.payout_code }} ({{ money(p.amount, p.currency) }})</h3>
        <div class="row"><mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Bank / remittance reference</mat-label><input matInput [(ngModel)]="paid.ref" /></mat-form-field>
          <input type="file" accept="application/pdf" (change)="pick($event)" /></div>
        <button mat-flat-button type="button" [disabled]="busy() || !paid.ref.trim() || !file" (click)="confirmPaid(p)">Upload evidence and record PAID</button>
        <button mat-button type="button" (click)="paying.set(null)">Close</button>
      </section>
    }
    @if (reconciling(); as p) {
      <section class="box" data-testid="rec-form"><h3>Reconcile {{ p.payout_code }} against a statement</h3>
        <div class="row">
          <mat-form-field subscriptSizing="dynamic"><mat-label>Statement reference</mat-label><input matInput [(ngModel)]="rec.ref" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Statement amount</mat-label><input matInput [(ngModel)]="rec.amount" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Currency</mat-label><input matInput maxlength="3" [(ngModel)]="rec.currency" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Statement date</mat-label><input matInput type="date" [(ngModel)]="rec.date" /></mat-form-field>
          <input type="file" accept="application/pdf" (change)="pick($event)" />
        </div>
        <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Resolution note (after an exception)</mat-label><input matInput [(ngModel)]="rec.note" /></mat-form-field>
        <button mat-flat-button type="button" [disabled]="busy() || !rec.ref.trim() || !rec.amount.trim() || !rec.date || !file" (click)="reconcile(p)">Upload statement and reconcile</button>
        <button mat-button type="button" (click)="reconciling.set(null)">Close</button>
      </section>
    }
    <h3>Recovery cases</h3>
    <p class="small muted">A refund of revenue that was already paid out opens a case here. There is no automatic clawback: record how it was resolved.</p>
    <div class="table-wrap"><table class="table" data-testid="adjustments">
      <thead><tr><th>Case</th><th>Reversal</th><th>Original run</th><th>Amount</th><th>Status</th><th></th></tr></thead>
      <tbody>
        @for (a of adjustments(); track a.id) {
          <tr><td>{{ a.adjustment_code }}</td><td>{{ a.reversal_revenue_code }}</td><td>{{ a.original_run_code }}</td><td>{{ money(a.amount, a.currency) }}</td>
            <td><app-status-badge [status]="badge(a.status)" [text]="label(a.status)" />@if (a.resolution) { <div class="small">{{ a.resolution }}</div> }</td>
            <td>@if (can.reconcile && a.status === 'OPEN') { <button mat-button type="button" [disabled]="busy()" (click)="closeCase(a)">Close case</button> }</td></tr>
        } @empty { <tr><td colspan="6" class="muted">No recovery case.</td></tr> }
      </tbody>
    </table></div>
  `,
  styles: FIN_STYLES,
})
export class PayoutsPage implements OnInit {
  private readonly api = inject(FinanceApi);
  private readonly auth = inject(AuthService);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotifyService);
  protected readonly money = money;
  protected readonly label = label;
  protected readonly badge = finBadge;
  protected readonly demo = this.auth.isDemo();
  protected readonly demoNote = FIN_DEMO_NOTE;
  protected readonly can = { calc: this.auth.has(P.PAYOUTS_CALCULATE), approve: this.auth.has(P.PAYOUTS_APPROVE),
    execute: this.auth.has(P.PAYOUTS_EXECUTE), reconcile: this.auth.has(P.PAYOUTS_RECONCILE) };
  protected readonly payouts = signal<Payout[]>([]);
  protected readonly adjustments = signal<Adjustment[]>([]);
  protected readonly paying = signal<Payout | null>(null);
  protected readonly reconciling = signal<Payout | null>(null);
  protected readonly busy = signal(false);
  protected file: File | undefined;
  protected paid = { ref: '' };
  protected rec = { ref: '', amount: '', currency: '', date: '', note: '' };

  ngOnInit(): void {
    this.reload();
  }

  private reload(): void {
    this.api.payouts().subscribe((p) => this.payouts.set(p));
    this.api.adjustments().subscribe((a) => this.adjustments.set(a));
  }

  private run<T>(obs: Observable<T>, message: string): void {
    runAction(obs, this.busy, this.notify, message, () => this.reload());
  }

  protected act(p: Payout, action: 'submit' | 'approve' | 'reissue' | 'initiate'): void {
    const msg = { submit: 'Submitted for approval.', approve: 'Payout approved.', reissue: 'Replacement payout calculated.',
      initiate: 'Payment pending — pay at the bank, then record it.' }[action];
    this.run(this.api.payoutAction(p.id, action, {}, newKey()), msg);
  }

  protected withReason(p: Payout, action: 'reject' | 'cancel' | 'release-hold' | 'fail'): void {
    askReason(this.dialog, { title: `${label(action)} ${p.payout_code}?`, confirmLabel: label(action), danger: action !== 'release-hold' })
      .subscribe((x) => { if (x) this.run(this.api.payoutAction(p.id, action, { reason: x.reason }, newKey()), 'Done.'); });
  }

  protected pick(ev: Event): void {
    this.file = (ev.target as HTMLInputElement).files?.[0];
  }

  protected openPaid(p: Payout): void {
    this.file = undefined;
    this.paid = { ref: '' };
    this.reconciling.set(null);
    this.paying.set(p);
  }

  protected openRec(p: Payout): void {
    this.file = undefined;
    this.rec = { ref: '', amount: '', currency: p.currency, date: '', note: '' };
    this.paying.set(null);
    this.reconciling.set(p);
  }

  protected confirmPaid(p: Payout): void {
    if (!this.file) return;
    this.busy.set(true);
    this.api.payoutDocument(p.id, this.file, 'PAYOUT_EVIDENCE').subscribe({
      next: (d) => { this.busy.set(false); this.paying.set(null);
        this.run(this.api.confirmPaid(p.id, { external_reference: this.paid.ref.trim(), document_id: d.document_id }, newKey()), 'Recorded as PAID.'); },
      error: (e: unknown) => { this.busy.set(false); this.notify.error(e); },
    });
  }

  protected reconcile(p: Payout): void {
    if (!this.file) return;
    this.busy.set(true);
    this.api.payoutDocument(p.id, this.file, 'RECONCILIATION_EVIDENCE').subscribe({
      next: (d) => { this.busy.set(false); this.reconciling.set(null);
        this.run(this.api.reconcile(p.id, { statement_reference: this.rec.ref.trim(), statement_amount: this.rec.amount.trim(),
          statement_currency: this.rec.currency.toUpperCase(), statement_date: this.rec.date, document_id: d.document_id,
          note: this.rec.note.trim() || null }, newKey()), 'Reconciliation recorded.'); },
      error: (e: unknown) => { this.busy.set(false); this.notify.error(e); },
    });
  }

  protected closeCase(a: Adjustment): void {
    askReason(this.dialog, { title: `Close ${a.adjustment_code}?`, confirmLabel: 'Close case', message: 'Record how the recovery was resolved.' })
      .subscribe((x) => { if (x) this.run(this.api.closeAdjustment(a.id, x.reason, newKey()), 'Case closed.'); });
  }
}
