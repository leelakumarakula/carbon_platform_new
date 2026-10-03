import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';

import { AuthService } from '../core/auth/auth.service';
import { P } from '../core/auth/permissions';
import { NotifyService } from '../core/notify.service';
import { label } from '../farmer/farmer.models';
import { PageHeader } from '../shared/page-header';
import { askReason } from '../shared/reason-dialog';
import { runAction } from '../shared/run-action';
import { StatusBadge } from '../shared/status-badge';
import { LedgerApi, newKey } from './ledger.api';
import { Holding, Holdings, Retirement, ledgerBadge } from './ledger.models';

/** Holder view: the caller organization's own positions only — project, vintage, methodology and registry facts; never farmer, farm, location,
 *  KYC, agreement, audit or other holders' data. A holder may request retirement of its own AVAILABLE credits; the credits become RETIRED only
 *  when the registry's retirement certificate is recorded by the credit team. */
@Component({
  selector: 'app-holdings-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, MatButtonModule, MatFormFieldModule, MatInputModule, PageHeader, StatusBadge],
  template: `
    <app-page-header title="My credits" subtitle="Registry-issued credits held by your organization" />
    @if (data(); as d) {
      <p class="note" data-testid="holdings-note">{{ d.note }}</p>
      @if (d.demo_note) { <p class="note demo" data-testid="holdings-demo-note"><app-status-badge status="DEMO" text="DEMO" /> {{ d.demo_note }}</p> }
      <div class="table-wrap"><table class="table" data-testid="holdings">
        <thead><tr><th>Batch</th><th>Project · period</th><th>Vintage</th><th>Methodology · standard</th><th>Registry</th><th>Registry range</th>
          <th>State</th><th>Quantity</th><th></th></tr></thead>
        <tbody>
          @for (h of d.holdings; track h.position_id) {
            <tr [attr.data-batch]="h.batch_code">
              <td>{{ h.batch_code }}<div class="small muted">{{ h.issuance_code }} · registry {{ h.external_issuance_id }}</div></td>
              <td>{{ h.project_code }} · {{ h.project_name }} · #{{ h.period_number }}</td><td>{{ h.vintage }}</td>
              <td>{{ h.methodology }}<div class="small">{{ h.standard }}</div></td><td>{{ h.registry_name }}</td>
              <td class="mono">{{ h.registry_range }}@if (h.sub_range) { <div>{{ h.sub_range }}</div> }</td>
              <td><app-status-badge [status]="badge(h.state)" [text]="label(h.state)" /></td><td>{{ h.quantity }}</td>
              <td>@if (canRetire && h.state === 'AVAILABLE') { <button mat-button type="button" (click)="choose(h)">Request retirement</button> }</td>
            </tr>
          } @empty { <tr><td colspan="9" class="muted" data-testid="no-holdings">Your organization holds no registry-issued credits.</td></tr> }
        </tbody>
      </table></div>
    }

    @if (chosen(); as h) {
      <div class="box" data-testid="holder-retire-form"><h4>Request retirement · {{ h.batch_code }}</h4>
        <mat-form-field subscriptSizing="dynamic" class="full"><mat-label>Quantity (whole credits, up to {{ availableIn(h.batch_id) }})</mat-label>
          <input matInput type="number" min="1" step="1" [(ngModel)]="form.quantity" /></mat-form-field>
        <mat-form-field subscriptSizing="dynamic" class="full"><mat-label>Beneficiary</mat-label><input matInput [(ngModel)]="form.beneficiary" /></mat-form-field>
        <mat-form-field subscriptSizing="dynamic" class="full"><mat-label>Retirement reason</mat-label><input matInput [(ngModel)]="form.reason" /></mat-form-field>
        <button mat-flat-button type="button" [disabled]="busy() || !valid(h)" (click)="request(h)">Request retirement</button>
        <button mat-button type="button" (click)="chosen.set(null)">Close</button>
      </div>
    }

    <h4>Retirement requests</h4>
    <div class="table-wrap"><table class="table" data-testid="holder-retirements">
      <thead><tr><th>Code</th><th>Batch</th><th>Quantity</th><th>Beneficiary</th><th>Status</th><th></th></tr></thead>
      <tbody>@for (r of retirements(); track r.id) {
        <tr><td>{{ r.retirement_code }}</td><td>{{ r.batch_code }}</td><td>{{ r.quantity }}</td><td>{{ r.beneficiary }}</td>
          <td><app-status-badge [status]="badge(r.status)" [text]="label(r.status)" />
            @if (r.registry_retirement_reference) { <div class="small">registry {{ r.registry_retirement_reference }} · {{ r.retirement_date }}</div> }</td>
          <td>@if (r.status === 'REQUESTED' && canRetire) { <button mat-button type="button" [disabled]="busy()" (click)="cancel(r)">Cancel</button> }</td></tr>
      } @empty { <tr><td colspan="6" class="muted">No retirement request.</td></tr> }</tbody>
    </table></div>
  `,
  styles: `.demo { display: flex; gap: 8px; align-items: center; } h4 { margin: 14px 0 4px; }
    .box { border: 1px solid var(--mat-sys-outline-variant); border-radius: 8px; padding: 8px 10px; margin: 10px 0; max-width: 520px; }
    .full { width: 100%; margin-bottom: 4px; } .mono { font-family: monospace; font-size: 11px; word-break: break-all; }`,
})
export class HoldingsPage implements OnInit {
  private readonly api = inject(LedgerApi);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotifyService);
  protected readonly label = label;
  protected readonly badge = ledgerBadge;
  protected readonly canRetire = inject(AuthService).has(P.CREDITS_HOLDER_RETIRE);
  protected readonly data = signal<Holdings | null>(null);
  protected readonly retirements = signal<Retirement[]>([]);
  protected readonly chosen = signal<Holding | null>(null);
  protected readonly busy = signal(false);
  protected form = { quantity: null as number | null, beneficiary: '', reason: '' };
  private key = newKey();

  ngOnInit(): void {
    this.reload();
  }

  private reload(): void {
    this.api.holdings().subscribe((d) => this.data.set(d));
    this.api.retirements().subscribe((r) => this.retirements.set(r));
  }

  /** AVAILABLE credits of the batch held by the caller's organization (display aid only; the server re-checks under lock). */
  protected availableIn(batchId: string): number {
    return (this.data()?.holdings ?? []).filter((h) => h.batch_id === batchId && h.state === 'AVAILABLE').reduce((t, h) => t + Number(h.quantity), 0);
  }

  protected choose(h: Holding): void {
    this.chosen.set(h);
    this.form = { quantity: null, beneficiary: '', reason: '' };
    this.key = newKey();
  }

  protected valid(h: Holding): boolean {
    const q = Number(this.form.quantity);
    return Number.isInteger(q) && q > 0 && q <= this.availableIn(h.batch_id) && this.form.beneficiary.trim().length >= 2
      && this.form.reason.trim().length >= 3;
  }

  protected request(h: Holding): void {
    runAction(this.api.requestRetirement({ batch_id: h.batch_id, owner_organization_id: h.owner_organization_id, quantity: Number(this.form.quantity),
      beneficiary: this.form.beneficiary.trim(), reason: this.form.reason.trim() }, this.key), this.busy, this.notify,
    'Retirement requested — RETIRED only once the registry\'s certificate is recorded.', () => { this.chosen.set(null); this.reload(); });
  }

  protected cancel(r: Retirement): void {
    askReason(this.dialog, { title: `Cancel ${r.retirement_code}?`, confirmLabel: 'Cancel request', danger: true }).subscribe((x) => {
      if (x) runAction(this.api.cancelRetirement(r.id, x.reason), this.busy, this.notify, 'Retirement request cancelled.', () => this.reload());
    });
  }
}
