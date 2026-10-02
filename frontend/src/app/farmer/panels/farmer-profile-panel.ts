import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnChanges, inject, input, output, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';

import { NotifyService } from '../../core/notify.service';
import { askReason } from '../../shared/reason-dialog';
import { runAction } from '../../shared/run-action';
import { Farmer, label } from '../farmer.models';
import { FarmersApi } from '../farmers.api';

const LOCKED = new Set(['KYC_VERIFIED', 'ACTIVE', 'SUSPENDED']);

@Component({
  selector: 'app-farmer-profile-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, DatePipe, MatFormFieldModule, MatInputModule, MatSelectModule, MatButtonModule, MatIconModule, MatCheckboxModule],
  template: `
    <div class="tab-body detail-grid">
      <form [formGroup]="form" (ngSubmit)="save()" class="stack">
        <h3>Profile</h3>
        <mat-form-field><mat-label>Full name</mat-label><input matInput formControlName="full_name" />
          @if (identityLocked) { <mat-hint>Locked after KYC verification.</mat-hint> }</mat-form-field>
        <mat-form-field><mat-label>Date of birth</mat-label><input matInput type="date" formControlName="date_of_birth" /></mat-form-field>
        <mat-form-field><mat-label>Preferred language</mat-label><input matInput formControlName="preferred_language" /></mat-form-field>
        <mat-form-field><mat-label>Address</mat-label><input matInput formControlName="address_line" /></mat-form-field>
        <div class="form-grid">
          <mat-form-field><mat-label>Village</mat-label><input matInput formControlName="village" /></mat-form-field>
          <mat-form-field><mat-label>Sub-district</mat-label><input matInput formControlName="sub_district" /></mat-form-field>
          <mat-form-field><mat-label>District</mat-label><input matInput formControlName="district" /></mat-form-field>
          <mat-form-field><mat-label>State</mat-label><input matInput formControlName="state" /></mat-form-field>
          <mat-form-field><mat-label>Postal code</mat-label><input matInput formControlName="postal_code" /></mat-form-field>
        </div>
        @if (farmer().can_manage) {
          <div class="row-actions"><button mat-flat-button type="submit" [disabled]="busy() || form.invalid || !form.dirty">Save profile</button></div>
        }
      </form>
      <div>
        <h3>Contacts</h3>
        @for (c of farmer().contacts; track c.id) {
          <div class="line" [class.inactive]="!c.is_active">
            <mat-icon>{{ c.contact_type === 'EMAIL' ? 'mail' : c.contact_type === 'ADDRESS' ? 'home' : 'call' }}</mat-icon>
            <span class="grow">{{ c.value }} <span class="muted small">{{ label(c.contact_type) }}{{ c.is_primary ? ' · primary' : '' }}
              {{ c.is_active ? '' : ' · inactive' }}</span></span>
            @if (farmer().can_manage && c.is_active) {
              <button mat-icon-button type="button" (click)="deactivate(c.id)" aria-label="Deactivate contact"><mat-icon>block</mat-icon></button>
            }
          </div>
        } @empty { <p class="muted">No contacts.</p> }
        @if (farmer().can_manage) {
          <form [formGroup]="contact" (ngSubmit)="addContact()" class="contact-form">
            <mat-form-field subscriptSizing="dynamic"><mat-label>Type</mat-label>
              <mat-select formControlName="contact_type">
                @for (t of ['PHONE', 'ALTERNATE_PHONE', 'EMAIL', 'ADDRESS']; track t) { <mat-option [value]="t">{{ label(t) }}</mat-option> }
              </mat-select></mat-form-field>
            <mat-form-field subscriptSizing="dynamic"><mat-label>Value</mat-label><input matInput formControlName="value" /></mat-form-field>
            <mat-checkbox formControlName="is_primary">Primary</mat-checkbox>
            <button mat-stroked-button type="submit" [disabled]="busy() || contact.invalid">Add contact</button>
          </form>
        }
        <p class="muted small">Registered {{ farmer().created_at | date: 'mediumDate' }} · updated {{ farmer().updated_at | date: 'medium' }}</p>
      </div>
    </div>
  `,
  styles: `
    h3 { margin: 0 0 12px; font: var(--mat-sys-title-medium); }
    .line { display: flex; align-items: center; gap: 8px; padding: 6px 0; border-bottom: 1px solid var(--mat-sys-outline-variant); }
    .inactive { opacity: .55; } .grow { flex: 1; }
    .contact-form { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 12px; }
  `,
})
export class FarmerProfilePanel implements OnChanges {
  readonly farmer = input.required<Farmer>();
  readonly changed = output<Farmer>();
  private readonly api = inject(FarmersApi);
  private readonly notify = inject(NotifyService);
  private readonly dialog = inject(MatDialog);
  protected readonly busy = signal(false);
  protected readonly label = label;
  protected identityLocked = false;

  protected readonly form = new FormGroup({
    full_name: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.minLength(2)] }),
    date_of_birth: new FormControl('', { nonNullable: true }),
    preferred_language: new FormControl('', { nonNullable: true }),
    address_line: new FormControl('', { nonNullable: true }),
    village: new FormControl('', { nonNullable: true }),
    sub_district: new FormControl('', { nonNullable: true }),
    district: new FormControl('', { nonNullable: true }),
    state: new FormControl('', { nonNullable: true }),
    postal_code: new FormControl('', { nonNullable: true }),
  });
  protected readonly contact = new FormGroup({
    contact_type: new FormControl('PHONE', { nonNullable: true }),
    value: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.minLength(3)] }),
    is_primary: new FormControl(false, { nonNullable: true }),
  });

  ngOnChanges(): void {
    const f = this.farmer();
    this.form.reset({ full_name: f.full_name, date_of_birth: f.date_of_birth ?? '', preferred_language: f.preferred_language ?? '',
      address_line: f.address_line ?? '', village: f.village ?? '', sub_district: f.sub_district ?? '', district: f.district ?? '',
      state: f.state ?? '', postal_code: f.postal_code ?? '' });
    this.identityLocked = LOCKED.has(f.status);
    if (!f.can_manage) this.form.disable();
    if (this.identityLocked) {
      this.form.controls.full_name.disable();
      this.form.controls.date_of_birth.disable();
    }
  }

  save(): void {
    const raw = this.form.getRawValue();
    const changes: Record<string, string | null> = {};
    for (const [k, v] of Object.entries(raw)) {
      const ctrl = this.form.get(k);
      if (ctrl?.dirty && ctrl.enabled) changes[k] = v.trim() || null;
    }
    runAction(this.api.update(this.farmer().id, changes), this.busy, this.notify, 'Profile saved.', (f) => this.changed.emit(f));
  }

  addContact(): void {
    const v = this.contact.getRawValue();
    runAction(this.api.addContact(this.farmer().id, { ...v, value: v.value.trim() }), this.busy, this.notify, 'Contact added.', (f) => {
      this.contact.reset({ contact_type: 'PHONE', value: '', is_primary: false });
      this.changed.emit(f);
    });
  }

  deactivate(contactId: string): void {
    askReason(this.dialog, { title: 'Deactivate contact?', confirmLabel: 'Deactivate' }).subscribe((r) => {
      if (r) runAction(this.api.deactivateContact(this.farmer().id, contactId, r.reason), this.busy, this.notify, 'Contact deactivated.',
        (f) => this.changed.emit(f));
    });
  }
}
