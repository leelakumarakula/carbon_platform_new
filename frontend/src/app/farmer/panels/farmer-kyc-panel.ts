import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, input, output, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { switchMap } from 'rxjs';

import { AuthService } from '../../core/auth/auth.service';
import { NotifyService } from '../../core/notify.service';
import { runAction } from '../../shared/run-action';
import { StatusBadge } from '../../shared/status-badge';
import { Farmer, KYC_ID_TYPES, label } from '../farmer.models';
import { FarmersApi } from '../farmers.api';

/** KYC: the identity number is sent once and never shown again (only ••••last4). */
@Component({
  selector: 'app-farmer-kyc-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, DatePipe, MatFormFieldModule, MatInputModule, MatSelectModule, MatButtonModule, MatIconModule,
    MatCheckboxModule, StatusBadge],
  template: `
    <div class="tab-body detail-grid">
      <div>
        <h3>Identity</h3>
        <dl class="kv">
          <dt>Status</dt><dd><app-status-badge [status]="farmer().status" /></dd>
          <dt>ID type</dt><dd>{{ label(k().id_type) || '—' }}</dd>
          <dt>ID number</dt><dd>{{ k().id_number_masked ?? '—' }}</dd>
          <dt>Submitted</dt><dd>{{ k().submitted_at ? (k().submitted_at | date: 'medium') : '—' }}</dd>
          <dt>Verified</dt><dd>{{ k().verified_at ? (k().verified_at | date: 'medium') : '—' }}</dd>
          <dt>Reviewer notes</dt><dd>{{ k().notes ?? '—' }}</dd>
        </dl>
        @if (k().possible_duplicate) {
          <p class="notice">Another farmer has the same identity number. The reviewer must confirm this is not a duplicate registration.</p>
        }
        <p class="muted small">The full identity number is never stored — only its type, last four characters and a keyed fingerprint used
          to detect duplicates.</p>
      </div>
      <div>
        @if (canSubmit()) {
          <h3>Submit KYC</h3>
          <form [formGroup]="submitForm" (ngSubmit)="submit()" class="stack">
            <mat-form-field><mat-label>ID type</mat-label>
              <mat-select formControlName="id_type">@for (t of idTypes; track t) { <mat-option [value]="t">{{ label(t) }}</mat-option> }</mat-select>
            </mat-form-field>
            <mat-form-field><mat-label>ID number</mat-label><input matInput formControlName="id_number" autocomplete="off" /></mat-form-field>
            <input #f type="file" hidden accept=".pdf,.png,.jpg,.jpeg,.webp" (change)="file.set(f.files?.[0] ?? null)" />
            <button mat-stroked-button type="button" (click)="f.click()"><mat-icon>badge</mat-icon> {{ file()?.name ?? 'Attach ID document' }}</button>
            <div class="row-actions"><button mat-flat-button type="submit" [disabled]="busy() || submitForm.invalid || !file()">Submit for review</button></div>
          </form>
        } @else if (canDecide()) {
          <h3>Review KYC</h3>
          @if (isSubmitter()) {
            <p class="notice">You submitted this KYC, so another reviewer must decide (separation of duties).</p>
          } @else {
            <form [formGroup]="decisionForm" class="stack">
              <mat-form-field><mat-label>Review notes (recorded)</mat-label><textarea matInput rows="3" formControlName="notes"></textarea></mat-form-field>
              @if (k().possible_duplicate) {
                <mat-checkbox formControlName="ack">I reviewed the possible duplicate and this is a different person</mat-checkbox>
              }
              <div class="row-actions">
                <button mat-stroked-button type="button" [disabled]="busy() || decisionForm.invalid" (click)="decide('RETURNED')">Return for correction</button>
                <button mat-flat-button type="button" [disabled]="busy() || decisionForm.invalid" (click)="decide('VERIFIED')">Verify KYC</button>
              </div>
            </form>
          }
        } @else if (farmer().status === 'DRAFT') {
          <p class="muted">Register the farmer before submitting KYC.</p>
        }
      </div>
    </div>
  `,
  styles: `h3 { margin: 0 0 12px; font: var(--mat-sys-title-medium); }`,
})
export class FarmerKycPanel {
  readonly farmer = input.required<Farmer>();
  readonly changed = output<Farmer>();
  private readonly api = inject(FarmersApi);
  private readonly notify = inject(NotifyService);
  private readonly auth = inject(AuthService);
  protected readonly busy = signal(false);
  protected readonly file = signal<File | null>(null);
  protected readonly label = label;
  protected readonly idTypes = KYC_ID_TYPES;
  protected readonly k = computed(() => this.farmer().kyc);
  protected readonly canSubmit = computed(() => this.farmer().can_manage && this.farmer().status === 'REGISTERED');
  protected readonly canDecide = computed(() => this.farmer().can_verify_kyc && this.farmer().status === 'KYC_PENDING');
  protected readonly isSubmitter = computed(() => this.k().submitted_by === this.auth.user()?.id);

  protected readonly submitForm = new FormGroup({
    id_type: new FormControl('NATIONAL_ID', { nonNullable: true, validators: [Validators.required] }),
    id_number: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.minLength(4), Validators.maxLength(40)] }),
  });
  protected readonly decisionForm = new FormGroup({
    notes: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.minLength(3)] }),
    ack: new FormControl(false, { nonNullable: true }),
  });

  submit(): void {
    const file = this.file();
    if (!file) return;
    const v = this.submitForm.getRawValue();
    const id = this.farmer().id;
    runAction(
      this.api.uploadDocument(id, file, 'KYC_ID', 'KYC identity document').pipe(
        switchMap((doc) => this.api.submitKyc(id, { id_type: v.id_type, id_number: v.id_number, document_id: doc.id })),
      ),
      this.busy, this.notify, 'KYC submitted for review.', (f) => {
        this.submitForm.reset({ id_type: 'NATIONAL_ID', id_number: '' });
        this.file.set(null);
        this.changed.emit(f);
      });
  }

  decide(decision: 'VERIFIED' | 'RETURNED'): void {
    const v = this.decisionForm.getRawValue();
    runAction(this.api.decideKyc(this.farmer().id, { decision, notes: v.notes.trim(), acknowledge_possible_duplicate: v.ack }),
      this.busy, this.notify, decision === 'VERIFIED' ? 'KYC verified.' : 'KYC returned for correction.', (f) => this.changed.emit(f));
  }
}
