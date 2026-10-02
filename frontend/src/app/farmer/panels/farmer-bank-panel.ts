import { ChangeDetectionStrategy, Component, inject, input, output, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';

import { NotifyService } from '../../core/notify.service';
import { askReason } from '../../shared/reason-dialog';
import { runAction } from '../../shared/run-action';
import { StatusBadge } from '../../shared/status-badge';
import { BankAccount, Farmer, label } from '../farmer.models';
import { FarmersApi } from '../farmers.api';

/** Account numbers are write-only: stored encrypted, only ever shown as ••••last4. */
@Component({
  selector: 'app-farmer-bank-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, MatFormFieldModule, MatInputModule, MatButtonModule, MatIconModule, StatusBadge],
  template: `
    <div class="tab-body">
      @for (b of farmer().bank_accounts; track b.id) {
        <div class="line">
          <mat-icon>account_balance</mat-icon>
          <div class="grow">
            <strong>{{ b.bank_name }}</strong> · {{ b.account_number_masked }} {{ b.is_primary ? '· primary' : '' }}
            <div class="muted small">{{ b.account_holder_name }} · {{ b.routing_code }} {{ b.branch_name ? '· ' + b.branch_name : '' }}</div>
            @if (b.review_notes) { <div class="muted small">Review: {{ b.review_notes }}</div> }
          </div>
          <app-status-badge [status]="tone(b)" [text]="label(b.status)" />
          @if (farmer().can_verify_bank && b.status === 'PENDING_VERIFICATION') {
            <button mat-button type="button" (click)="decide(b, 'REJECTED')" [disabled]="busy()">Reject</button>
            <button mat-stroked-button type="button" (click)="decide(b, 'VERIFIED')" [disabled]="busy()">Verify</button>
          }
          @if (farmer().can_manage_bank && b.status !== 'INACTIVE') {
            <button mat-icon-button type="button" (click)="deactivate(b)" aria-label="Deactivate account"><mat-icon>block</mat-icon></button>
          }
        </div>
      } @empty { <p class="muted">No bank accounts.</p> }
      @if (farmer().can_manage_bank) {
        <form [formGroup]="form" (ngSubmit)="add()" class="form-grid add">
          <mat-form-field><mat-label>Account holder</mat-label><input matInput formControlName="account_holder_name" /></mat-form-field>
          <mat-form-field><mat-label>Bank</mat-label><input matInput formControlName="bank_name" /></mat-form-field>
          <mat-form-field><mat-label>Branch</mat-label><input matInput formControlName="branch_name" /></mat-form-field>
          <mat-form-field><mat-label>Routing code (IFSC / SWIFT)</mat-label><input matInput formControlName="routing_code" /></mat-form-field>
          <mat-form-field><mat-label>Account number</mat-label><input matInput formControlName="account_number" autocomplete="off" inputmode="numeric" />
            <mat-hint>Stored encrypted; you will only see the last 4 digits.</mat-hint></mat-form-field>
          <div class="row-actions span-all"><button mat-flat-button type="submit" [disabled]="busy() || form.invalid">Add bank account</button></div>
        </form>
      }
    </div>
  `,
  styles: `
    .line { display: flex; align-items: center; gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--mat-sys-outline-variant); flex-wrap: wrap; }
    .grow { flex: 1; min-width: 220px; } .add { margin-top: 16px; }
  `,
})
export class FarmerBankPanel {
  readonly farmer = input.required<Farmer>();
  readonly changed = output<Farmer>();
  private readonly api = inject(FarmersApi);
  private readonly notify = inject(NotifyService);
  private readonly dialog = inject(MatDialog);
  protected readonly busy = signal(false);
  protected readonly label = label;
  protected readonly form = new FormGroup({
    account_holder_name: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.minLength(2)] }),
    bank_name: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.minLength(2)] }),
    branch_name: new FormControl('', { nonNullable: true }),
    routing_code: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.pattern(/^[A-Za-z0-9]{4,30}$/)] }),
    account_number: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.pattern(/^[A-Za-z0-9 -]{6,40}$/)] }),
  });

  tone(b: BankAccount): string {
    return { VERIFIED: 'ACTIVE', PENDING_VERIFICATION: 'WARNING', REJECTED: 'FAILED', INACTIVE: 'ARCHIVED' }[b.status];
  }

  add(): void {
    const v = this.form.getRawValue();
    runAction(this.api.addBankAccount(this.farmer().id, { ...v, branch_name: v.branch_name.trim() || null, is_primary: true }), this.busy,
      this.notify, 'Bank account added; awaiting verification.', (f) => {
        this.form.reset();
        this.changed.emit(f);
      });
  }

  decide(b: BankAccount, decision: 'VERIFIED' | 'REJECTED'): void {
    askReason(this.dialog, { title: `${decision === 'VERIFIED' ? 'Verify' : 'Reject'} account ${b.account_number_masked}?`,
      confirmLabel: decision === 'VERIFIED' ? 'Verify' : 'Reject', danger: decision === 'REJECTED' }).subscribe((r) => {
      if (r) runAction(this.api.decideBankAccount(this.farmer().id, b.id, decision, r.reason), this.busy, this.notify, 'Bank account reviewed.',
        (f) => this.changed.emit(f));
    });
  }

  deactivate(b: BankAccount): void {
    askReason(this.dialog, { title: `Deactivate ${b.account_number_masked}?`, confirmLabel: 'Deactivate', danger: true }).subscribe((r) => {
      if (r) runAction(this.api.deactivateBankAccount(this.farmer().id, b.id, r.reason), this.busy, this.notify, 'Account deactivated.',
        (f) => this.changed.emit(f));
    });
  }
}
