import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, input, output, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { switchMap } from 'rxjs';

import { NotifyService } from '../../core/notify.service';
import { askReason } from '../../shared/reason-dialog';
import { runAction } from '../../shared/run-action';
import { StatusBadge } from '../../shared/status-badge';
import { Agreement, Farmer, label } from '../farmer.models';
import { FarmersApi } from '../farmers.api';

@Component({
  selector: 'app-farmer-agreements-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, DatePipe, MatFormFieldModule, MatInputModule, MatSelectModule, MatButtonModule, MatIconModule, StatusBadge],
  template: `
    <div class="tab-body">
      @for (a of farmer().agreements; track a.id) {
        <div class="line">
          <div class="grow">
            <strong>{{ a.agreement_number }}</strong> · {{ label(a.agreement_type) }} <span class="muted small">template {{ a.template_version }}</span>
            <div class="muted small">{{ a.effective_from ?? '—' }} → {{ a.effective_to ?? 'open' }}
              @if (a.signed_at) { · signed {{ a.signed_at | date: 'mediumDate' }} ({{ label(a.signature_method) }}) }</div>
            @if (a.terms_summary) { <div class="small">{{ a.terms_summary }}</div> }
          </div>
          <app-status-badge [status]="a.status === 'SIGNED' ? 'ACTIVE' : a.status === 'DRAFT' ? 'INFO' : 'ARCHIVED'" [text]="label(a.status)" />
          @if (farmer().can_manage && a.status === 'DRAFT') {
            <input #f type="file" hidden accept=".pdf,.png,.jpg,.jpeg" (change)="sign(a, f.files?.[0] ?? null)" />
            <button mat-stroked-button type="button" (click)="f.click()" [disabled]="busy()"><mat-icon>draw</mat-icon> Upload signed copy</button>
          }
          @if (canIssue && (a.status === 'SIGNED' || a.status === 'DRAFT')) {
            <button mat-button type="button" (click)="end(a)" [disabled]="busy()">{{ a.status === 'DRAFT' ? 'Void' : 'Terminate' }}</button>
          }
        </div>
      } @empty { <p class="muted">No agreements.</p> }
      @if (canIssue) {
        <form [formGroup]="form" (ngSubmit)="create()" class="grant">
          <mat-form-field subscriptSizing="dynamic"><mat-label>Agreement type</mat-label><input matInput formControlName="agreement_type"
                 placeholder="PROGRAM_PARTICIPATION" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Template version</mat-label><input matInput formControlName="template_version" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Effective from</mat-label><input matInput type="date" formControlName="effective_from" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Terms summary</mat-label><input matInput formControlName="terms_summary" /></mat-form-field>
          <button mat-flat-button type="submit" [disabled]="busy() || form.invalid">Create agreement</button>
        </form>
        <p class="muted small">Project participation and carbon-rights terms are added with projects (Phase 3).</p>
      }
    </div>
  `,
  styles: `
    .line { display: flex; align-items: center; gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--mat-sys-outline-variant); flex-wrap: wrap; }
    .grow { flex: 1; min-width: 220px; } .grant { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 16px; }
    .wide { min-width: 280px; }
  `,
})
export class FarmerAgreementsPanel {
  readonly farmer = input.required<Farmer>();
  readonly changed = output<Farmer>();
  private readonly api = inject(FarmersApi);
  private readonly notify = inject(NotifyService);
  private readonly dialog = inject(MatDialog);
  protected readonly busy = signal(false);
  protected readonly label = label;
  /** Agreements are issued by the organization; farmers can upload their signed copy. */
  protected get canIssue(): boolean {
    return this.farmer().can_manage && !this.farmer().is_self;
  }
  protected readonly form = new FormGroup({
    agreement_type: new FormControl('PROGRAM_PARTICIPATION', { nonNullable: true, validators: [Validators.required, Validators.pattern(/^[A-Za-z][A-Za-z0-9_]{2,39}$/)] }),
    template_version: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    effective_from: new FormControl('', { nonNullable: true }),
    terms_summary: new FormControl('', { nonNullable: true }),
  });

  create(): void {
    const v = this.form.getRawValue();
    runAction(this.api.createAgreement(this.farmer().id, { agreement_type: v.agreement_type, template_version: v.template_version,
      effective_from: v.effective_from || null, terms_summary: v.terms_summary.trim() || null }), this.busy, this.notify,
      'Agreement created.', (f) => this.changed.emit(f));
  }

  sign(a: Agreement, file: File | null): void {
    if (!file) return;
    const id = this.farmer().id;
    runAction(this.api.uploadDocument(id, file, 'AGREEMENT', `Signed ${a.agreement_number}`).pipe(
      switchMap((doc) => this.api.signAgreement(id, a.id, { signed_document_id: doc.id, signature_method: 'PAPER_SIGNED' }))),
      this.busy, this.notify, 'Signed agreement recorded.', (f) => this.changed.emit(f));
  }

  end(a: Agreement): void {
    const target = a.status === 'DRAFT' ? 'VOID' : 'TERMINATED';
    askReason(this.dialog, { title: `${label(target)} ${a.agreement_number}?`, confirmLabel: label(target), danger: true }).subscribe((r) => {
      if (r) runAction(this.api.agreementStatus(this.farmer().id, a.id, target, r.reason), this.busy, this.notify, 'Agreement updated.',
        (f) => this.changed.emit(f));
    });
  }
}
