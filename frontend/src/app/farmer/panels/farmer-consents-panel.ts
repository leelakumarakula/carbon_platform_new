import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, input, output, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';

import { NotifyService } from '../../core/notify.service';
import { askReason } from '../../shared/reason-dialog';
import { runAction } from '../../shared/run-action';
import { StatusBadge } from '../../shared/status-badge';
import { CONSENT_METHODS, CONSENT_TYPES, Farmer, label } from '../farmer.models';
import { FarmersApi } from '../farmers.api';

/** Consents are append-only: withdrawing keeps the record; granting again creates a new one. */
@Component({
  selector: 'app-farmer-consents-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, DatePipe, MatFormFieldModule, MatInputModule, MatSelectModule, MatButtonModule, StatusBadge],
  template: `
    <div class="tab-body">
      @for (c of farmer().consents; track c.id) {
        <div class="line">
          <div class="grow">
            <strong>{{ label(c.consent_type) }}</strong> <span class="muted small">text {{ c.consent_text_version }} · {{ label(c.capture_method) }}
              · {{ c.captured_at | date: 'medium' }}</span>
            @if (c.withdrawn_at) { <div class="muted small">Withdrawn {{ c.withdrawn_at | date: 'medium' }} — {{ c.withdrawal_reason }}</div> }
          </div>
          <app-status-badge [status]="c.status === 'GRANTED' ? 'ACTIVE' : 'REVOKED'" [text]="label(c.status)" />
          @if (farmer().can_manage && c.status === 'GRANTED') {
            <button mat-button type="button" (click)="withdraw(c.id)" [disabled]="busy()">Withdraw</button>
          }
        </div>
      } @empty { <p class="muted">No consents recorded.</p> }
      @if (farmer().can_manage) {
        <form [formGroup]="form" (ngSubmit)="grant()" class="grant">
          <mat-form-field subscriptSizing="dynamic"><mat-label>Consent</mat-label>
            <mat-select formControlName="consent_type">@for (t of types; track t) { <mat-option [value]="t">{{ label(t) }}</mat-option> }</mat-select>
          </mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Consent text version</mat-label><input matInput formControlName="consent_text_version" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Captured by</mat-label>
            <mat-select formControlName="capture_method">@for (m of methods; track m) { <mat-option [value]="m">{{ label(m) }}</mat-option> }</mat-select>
          </mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Language</mat-label><input matInput formControlName="language" /></mat-form-field>
          <button mat-flat-button type="submit" [disabled]="busy() || form.invalid">Record consent</button>
        </form>
      }
    </div>
  `,
  styles: `
    .line { display: flex; align-items: center; gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--mat-sys-outline-variant); }
    .grow { flex: 1; } .grant { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 16px; }
  `,
})
export class FarmerConsentsPanel {
  readonly farmer = input.required<Farmer>();
  readonly changed = output<Farmer>();
  private readonly api = inject(FarmersApi);
  private readonly notify = inject(NotifyService);
  private readonly dialog = inject(MatDialog);
  protected readonly busy = signal(false);
  protected readonly label = label;
  protected readonly types = CONSENT_TYPES;
  protected readonly methods = CONSENT_METHODS;
  protected readonly form = new FormGroup({
    consent_type: new FormControl('DATA_PROCESSING', { nonNullable: true, validators: [Validators.required] }),
    consent_text_version: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    capture_method: new FormControl('PAPER_SIGNED', { nonNullable: true }),
    language: new FormControl('', { nonNullable: true }),
  });

  grant(): void {
    const v = this.form.getRawValue();
    runAction(this.api.grantConsent(this.farmer().id, { ...v, language: v.language.trim() || null }), this.busy, this.notify,
      'Consent recorded.', (f) => this.changed.emit(f));
  }

  withdraw(consentId: string): void {
    askReason(this.dialog, { title: 'Withdraw consent?', message: 'The consent record is kept with its withdrawal date and reason.',
      confirmLabel: 'Withdraw', danger: true }).subscribe((r) => {
      if (r) runAction(this.api.withdrawConsent(this.farmer().id, consentId, r.reason), this.busy, this.notify, 'Consent withdrawn.',
        (f) => this.changed.emit(f));
    });
  }
}
