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
import { Allocation, FinanceProject, Settlement, ShareVersion, Verify, finBadge, label, money, newKey } from './finance.models';
import { FIN_STYLES, FinanceProjectPicker } from './project-picker';

/** Settlement runs: a frozen, hashed calculation of farmer entitlements for one project / period / currency from APPROVED configuration.
 *  Calculator ≠ approver; a rejected or cancelled run frees its inputs; changed inputs mean a new run. Payouts are created from an
 *  APPROVED run (amounts are the entitlements — never typed). */
@Component({
  selector: 'app-settlements-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, FormsModule, MatButtonModule, MatFormFieldModule, MatInputModule, MatSelectModule, PageHeader, StatusBadge,
            FinanceProjectPicker],
  template: `
    <app-page-header title="Settlements" subtitle="Reproducible farmer entitlement calculations" />
    <app-finance-project-picker (changed)="select($event)" />
    @if (canCalculate && project(); as p) {
      <section class="box" data-testid="run-form"><h3>New settlement run</h3>
        <div class="row">
          <mat-form-field subscriptSizing="dynamic"><mat-label>Monitoring period</mat-label>
            <mat-select [(ngModel)]="f.period">@for (m of p.periods; track m.id) { <mat-option [value]="m.id">Period {{ m.period_number }}</mat-option> }</mat-select></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Currency</mat-label><input matInput maxlength="3" [(ngModel)]="f.currency" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Approved revenue-share version</mat-label>
            <mat-select [(ngModel)]="f.share">@for (v of approvedShares(); track v.id) {
              <mat-option [value]="v.id">{{ v.version_code }} · {{ v.farmer_share_pct }} % · {{ v.rounding_mode }}</mat-option> }</mat-select></mat-form-field>
          <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Approved farm allocation</mat-label>
            <mat-select [(ngModel)]="f.alloc">@for (a of approvedAllocs(); track a.id) {
              @if (a.monitoring_period_id === f.period) { <mat-option [value]="a.id">{{ a.version_code }} (v{{ a.version_no }})</mat-option> } }</mat-select></mat-form-field>
        </div>
        @if (!approvedShares().length || !approvedAllocs().length) {
          <p class="note warn" data-testid="config-required">Configuration required: an APPROVED revenue-share version and an APPROVED farm allocation
            for the period are needed before any settlement can run.</p> }
        <button mat-flat-button type="button" [disabled]="busy() || !f.period || !f.share || !f.alloc || !f.currency" (click)="create()">Create run</button>
      </section>
    }
    <div class="table-wrap"><table class="table" data-testid="runs">
      <thead><tr><th>Run</th><th>Period</th><th>Gross</th><th>Costs</th><th>Distributable</th><th>Farmers</th><th>Residual</th><th>Status</th><th></th></tr></thead>
      <tbody>
        @for (r of runs(); track r.id) {
          <tr [class.sel]="detail()?.id === r.id"><td><a href="" (click)="$event.preventDefault(); open(r)">{{ r.run_code }}</a></td><td>{{ r.period_number }}</td>
            <td>{{ money(r.gross_revenue, r.currency) }}</td><td>{{ money(r.deducted_costs, r.currency) }}</td><td>{{ money(r.distributable, r.currency) }}</td>
            <td>{{ money(r.farmer_total, r.currency) }}</td><td>{{ money(r.developer_residual, r.currency) }}</td>
            <td><app-status-badge [status]="badge(r.status)" [text]="label(r.status)" /></td>
            <td>@if (canCalculate && r.status === 'DRAFT') { <button mat-button type="button" [disabled]="busy()" (click)="calculate(r)">Calculate</button> }
              @if (canCalculate && r.status === 'CALCULATED') { <button mat-button type="button" [disabled]="busy()" (click)="act2(r, 'submit')">Submit</button> }
              @if (canCalculate && (r.status === 'DRAFT' || r.status === 'CALCULATED')) { <button mat-button type="button" [disabled]="busy()" (click)="close(r, 'cancel')">Cancel</button> }
              @if (canApprove && r.status === 'PENDING_APPROVAL') { <button mat-button type="button" [disabled]="busy()" (click)="act2(r, 'approve')">Approve</button>
                <button mat-button type="button" [disabled]="busy()" (click)="close(r, 'reject')">Reject</button> }
              @if (canPayout && r.status === 'APPROVED') { <button mat-button type="button" [disabled]="busy()" (click)="payouts(r)">Create payouts</button> }</td></tr>
        } @empty { <tr><td colspan="9" class="muted" data-testid="no-runs">No settlement run.</td></tr> }
      </tbody>
    </table></div>
    @if (detail(); as d) {
      <section class="box" data-testid="run-detail"><h3>{{ d.run_code }} — {{ label(d.status) }}</h3>
        <p class="small">Calculation {{ d.calculation_version ?? '—' }} · inputs SHA-256 <code>{{ d.input_sha256 ?? '—' }}</code> ·
          {{ d.revenue_count }} revenue record(s), {{ d.cost_count }} cost(s) · rule {{ d.revenue_share_version_code }} · allocation {{ d.allocation_version_code }}</p>
        @if (d.input_sha256) { <button mat-button type="button" (click)="verify(d)">Verify (recompute from snapshot)</button> }
        @if (verified(); as v) { <span data-testid="verify-result" [class]="v.reproducible ? 'ok' : 'bad'">{{ v.reproducible ? 'Reproducible' : 'NOT reproducible' }}</span> }
        <div class="table-wrap"><table class="table"><thead><tr><th>Farm</th><th>Farmer</th><th>Allocation %</th><th>Entitlement</th></tr></thead>
          <tbody>@for (e of d.entitlements; track e.id) {
            <tr><td>{{ e.farm_name }}</td><td>{{ e.farmer_name }}</td><td>{{ e.share_pct }}</td><td>{{ money(e.amount, e.currency) }}</td></tr>
          } @empty { <tr><td colspan="4" class="muted">Not calculated.</td></tr> }</tbody></table></div>
        @if (d.calculated_at) { <p class="small muted">Calculated {{ d.calculated_at | date: 'medium' }} by {{ d.calculated_by_name }}
          @if (d.approved_at) { · approved {{ d.approved_at | date: 'medium' }} by {{ d.approved_by_name }} }</p> }
      </section>
    }
  `,
  styles: FIN_STYLES + ' tr.sel { background: var(--mat-sys-surface-container); } .ok { color: #1b6e2a; } .bad { color: #8e1b1b; }',
})
export class SettlementsPage {
  private readonly api = inject(FinanceApi);
  private readonly auth = inject(AuthService);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotifyService);
  protected readonly money = money;
  protected readonly label = label;
  protected readonly badge = finBadge;
  protected readonly canCalculate = this.auth.has(P.SETTLEMENT_CALCULATE);
  protected readonly canApprove = this.auth.has(P.SETTLEMENT_APPROVE);
  protected readonly canPayout = this.auth.has(P.PAYOUTS_CALCULATE);
  protected readonly project = signal<FinanceProject | null>(null);
  protected readonly runs = signal<Settlement[]>([]);
  protected readonly approvedShares = signal<ShareVersion[]>([]);
  protected readonly approvedAllocs = signal<Allocation[]>([]);
  protected readonly detail = signal<Settlement | null>(null);
  protected readonly verified = signal<Verify | null>(null);
  protected readonly busy = signal(false);
  protected f = { period: '', currency: 'INR', share: '', alloc: '' };

  protected select(p: FinanceProject): void {
    this.project.set(p);
    this.detail.set(null);
    this.reload();
    this.api.shareVersions(p.id).subscribe((v) => this.approvedShares.set(v.filter((x) => x.status === 'APPROVED')));
    this.api.allocations(p.id).subscribe((a) => this.approvedAllocs.set(a.filter((x) => x.status === 'APPROVED')));
  }

  private reload(): void {
    const p = this.project();
    if (!p) return;
    this.api.settlements(p.id).subscribe((r) => this.runs.set(r));
    const d = this.detail();
    if (d) this.api.settlement(d.id).subscribe((x) => this.detail.set(x));
  }

  private act<T>(obs: Observable<T>, message: string): void {
    runAction(obs, this.busy, this.notify, message, () => this.reload());
  }

  protected open(r: Settlement): void {
    this.verified.set(null);
    this.api.settlement(r.id).subscribe((x) => this.detail.set(x));
  }

  protected create(): void {
    const p = this.project();
    if (!p) return;
    this.act(this.api.createSettlement({ project_id: p.id, monitoring_period_id: this.f.period, currency: this.f.currency.toUpperCase(),
      revenue_share_version_id: this.f.share, allocation_version_id: this.f.alloc }, newKey()), 'Settlement run created.');
  }

  protected calculate(r: Settlement): void {
    runAction(this.api.calculate(r.id, newKey()), this.busy, this.notify, 'Calculated — inputs frozen.', (x) => { this.detail.set(x); this.reload(); });
  }

  protected act2(r: Settlement, action: 'submit' | 'approve'): void {
    this.act(this.api.settlementAction(r.id, action, {}, newKey()), action === 'submit' ? 'Submitted for approval.' : 'Settlement approved.');
  }

  protected close(r: Settlement, action: 'reject' | 'cancel'): void {
    askReason(this.dialog, { title: `${action === 'reject' ? 'Reject' : 'Cancel'} ${r.run_code}?`, danger: true,
      confirmLabel: action === 'reject' ? 'Reject run' : 'Cancel run', message: 'Its revenue and costs become available to a new run.' })
      .subscribe((x) => { if (x) this.act(this.api.settlementAction(r.id, action, { reason: x.reason }, newKey()), 'Run closed.'); });
  }

  protected verify(r: Settlement): void {
    this.api.verify(r.id).subscribe((v) => this.verified.set(v));
  }

  protected payouts(r: Settlement): void {
    runAction(this.api.createPayouts(r.id), this.busy, this.notify, 'Payouts calculated — see Payouts.', () => this.reload());
  }
}
