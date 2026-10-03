import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { Observable } from 'rxjs';

import { AuthService } from '../core/auth/auth.service';
import { P } from '../core/auth/permissions';
import { NotifyService } from '../core/notify.service';
import { PageHeader } from '../shared/page-header';
import { askReason } from '../shared/reason-dialog';
import { runAction } from '../shared/run-action';
import { StatusBadge } from '../shared/status-badge';
import { FinanceApi } from './finance.api';
import { Cost, FinanceProject, Revenue, Summary, finBadge, label, money, newKey } from './finance.models';
import { FIN_STYLES, FinanceProjectPicker } from './project-picker';

/** Recognized revenue (append-only, per order item, from Phase 10 records — never typed here), reversals of completed refunds, the
 *  financial summary and project costs (recorded with PDF evidence, approved by someone else; deducted only if the approved revenue-share
 *  version says so). */
@Component({
  selector: 'app-revenue-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, FormsModule, MatButtonModule, MatFormFieldModule, MatInputModule, MatSelectModule, PageHeader, StatusBadge,
            FinanceProjectPicker],
  template: `
    <app-page-header title="Revenue & costs" subtitle="Recognized revenue, reversals and project costs" />
    <p class="note">Revenue is recognized automatically per order item once the payment is confirmed and the credits are delivered. It is never
      typed or edited; a refund creates a reversal. No fee, commission or tax is calculated.</p>
    <app-finance-project-picker (changed)="select($event)" />
    @if (summary(); as s) {
      <section class="box" data-testid="fin-summary"><h3>Summary</h3>
        @for (r of s.revenue; track r.currency) {
          <div class="figs"><div class="fig">Recognized<b>{{ money(r.recognized, r.currency) }}</b></div>
            <div class="fig">Reversed<b>{{ money(r.reversed, r.currency) }}</b></div><div class="fig">Net<b>{{ money(r.net, r.currency) }}</b></div></div>
        } @empty { <p class="muted" data-testid="fin-no-revenue">No revenue recognized.</p> }
        @for (x of s.settlements; track x.currency) {
          <div class="figs"><div class="fig">Distributable (approved runs)<b>{{ money(x.distributable, x.currency) }}</b></div>
            <div class="fig">Farmer entitlements<b>{{ money(x.farmer_total, x.currency) }}</b></div>
            <div class="fig">Developer residual<b>{{ money(x.developer_residual, x.currency) }}</b></div></div>
        }
        @if (s.open_recovery_cases) { <p class="note warn">{{ s.open_recovery_cases }} open recovery case(s) — see Payouts.</p> }
      </section>
    }
    <h3>Revenue records</h3>
    <div class="table-wrap"><table class="table" data-testid="revenue">
      <thead><tr><th>Record</th><th>Kind</th><th>Amount</th><th>Order / item</th><th>Payment · transfer · batch</th><th>Settled in</th><th>Recorded</th></tr></thead>
      <tbody>
        @for (r of revenue(); track r.id) {
          <tr><td>{{ r.revenue_code }}</td><td><app-status-badge [status]="badge(r.kind)" [text]="label(r.kind)" />
              @if (r.reverses_revenue_code) { <div class="small">reverses {{ r.reverses_revenue_code }} ({{ r.refund_code }})</div> }</td>
            <td>{{ money(r.amount, r.currency) }}</td><td>{{ r.order_code }} · {{ r.order_item_code }}</td>
            <td class="small">{{ r.payment_code }} · {{ r.transfer_code }} · {{ r.batch_code }}</td>
            <td>{{ r.settled_in_run_code ?? '—' }}</td><td>{{ r.recorded_at | date: 'medium' }}</td></tr>
        } @empty { <tr><td colspan="7" class="muted">No revenue record.</td></tr> }
      </tbody>
    </table></div>
    <h3>Project costs</h3>
    @if (canRecord && project()) {
      <section class="box" data-testid="cost-form">
        <div class="row">
          <mat-form-field subscriptSizing="dynamic"><mat-label>Category</mat-label><input matInput [(ngModel)]="c.category" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Description</mat-label><input matInput [(ngModel)]="c.description" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Amount actually incurred</mat-label><input matInput [(ngModel)]="c.amount" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Currency</mat-label><input matInput maxlength="3" [(ngModel)]="c.currency" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Incurred on</mat-label><input matInput type="date" [(ngModel)]="c.incurred_on" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Period (optional)</mat-label>
            <mat-select [(ngModel)]="c.period"><mat-option value="">Any period</mat-option>@for (m of project()!.periods; track m.id) {
              <mat-option [value]="m.id">Period {{ m.period_number }}</mat-option> }</mat-select></mat-form-field>
        </div>
        <button mat-flat-button type="button" [disabled]="busy() || !costValid()" (click)="record()">Record cost</button>
        <span class="small muted"> Approval needs a PDF of the evidence and a different person.</span>
      </section>
    }
    <div class="table-wrap"><table class="table" data-testid="costs">
      <thead><tr><th>Cost</th><th>Category</th><th>Amount</th><th>Incurred</th><th>Status</th><th>Evidence</th><th></th></tr></thead>
      <tbody>
        @for (x of costs(); track x.id) {
          <tr><td>{{ x.cost_code }}<div class="small muted">{{ x.description }}</div></td><td>{{ x.category }}</td>
            <td>{{ money(x.amount, x.currency) }}@if (x.corrects_cost_id) { <div class="small">correction</div> }</td><td>{{ x.incurred_on }}</td>
            <td><app-status-badge [status]="badge(x.status)" [text]="label(x.status)" />@if (x.settled_in_run_code) {
              <div class="small">deducted in {{ x.settled_in_run_code }}</div> }</td>
            <td>{{ x.documents.length }} PDF @if (canRecord && x.status === 'PENDING_APPROVAL') {
              <input type="file" accept="application/pdf" (change)="evidence(x, $event)" /> }</td>
            <td>@if (canApprove && x.status === 'PENDING_APPROVAL') {
              <button mat-button type="button" [disabled]="busy()" (click)="approve(x)">Approve</button>
              <button mat-button type="button" [disabled]="busy()" (click)="reject(x)">Reject</button> }</td></tr>
        } @empty { <tr><td colspan="7" class="muted">No cost recorded.</td></tr> }
      </tbody>
    </table></div>
  `,
  styles: FIN_STYLES,
})
export class RevenuePage {
  private readonly api = inject(FinanceApi);
  private readonly auth = inject(AuthService);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotifyService);
  protected readonly money = money;
  protected readonly label = label;
  protected readonly badge = finBadge;
  protected readonly canRecord = this.auth.has(P.COSTS_MANAGE);
  protected readonly canApprove = this.auth.has(P.COSTS_APPROVE);
  protected readonly project = signal<FinanceProject | null>(null);
  protected readonly summary = signal<Summary | null>(null);
  protected readonly revenue = signal<Revenue[]>([]);
  protected readonly costs = signal<Cost[]>([]);
  protected readonly busy = signal(false);
  protected c = { category: '', description: '', amount: '', currency: 'INR', incurred_on: '', period: '' };

  protected select(p: FinanceProject): void {
    this.project.set(p);
    this.reload();
  }

  private reload(): void {
    const p = this.project();
    if (!p) return;
    this.api.summary(p.id).subscribe((s) => this.summary.set(s));
    this.api.revenue(p.id).subscribe((r) => this.revenue.set(r));
    this.api.costs(p.id).subscribe((c) => this.costs.set(c));
  }

  private act<T>(obs: Observable<T>, message: string): void {
    runAction(obs, this.busy, this.notify, message, () => this.reload());
  }

  protected costValid(): boolean {
    return !!(this.c.category.trim() && this.c.description.trim().length >= 3 && /^-?\d+(\.\d{1,4})?$/.test(this.c.amount.trim())
      && /^[A-Za-z]{3}$/.test(this.c.currency) && this.c.incurred_on);
  }

  protected record(): void {
    const p = this.project();
    if (!p) return;
    this.act(this.api.createCost({ project_id: p.id, monitoring_period_id: this.c.period || null, category: this.c.category,
      description: this.c.description, amount: this.c.amount.trim(), currency: this.c.currency.toUpperCase(), incurred_on: this.c.incurred_on },
    newKey()), 'Cost recorded — attach its evidence for approval.');
  }

  protected evidence(x: Cost, ev: Event): void {
    const f = (ev.target as HTMLInputElement).files?.[0];
    if (f) this.act(this.api.costDocument(x.id, f), 'Evidence attached.');
  }

  protected approve(x: Cost): void {
    this.act(this.api.approveCost(x.id, newKey()), 'Cost approved.');
  }

  protected reject(x: Cost): void {
    askReason(this.dialog, { title: `Reject ${x.cost_code}?`, confirmLabel: 'Reject cost', danger: true })
      .subscribe((r) => { if (r) this.act(this.api.rejectCost(x.id, r.reason, newKey()), 'Cost rejected.'); });
  }
}
