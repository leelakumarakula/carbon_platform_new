import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { Router } from '@angular/router';

import { OrganizationsApi } from '../admin/admin.api';
import { Organization } from '../admin/admin.models';
import { ApiError } from '../core/api/api.models';
import { AuthService } from '../core/auth/auth.service';
import { P } from '../core/auth/permissions';
import { NotifyService } from '../core/notify.service';
import { applyServerErrors } from '../shared/forms';
import { PageHeader } from '../shared/page-header';
import { FarmersApi } from './farmers.api';

const MANAGING = new Set(['PROJECT_DEVELOPER', 'FIELD_PARTNER', 'FARMER_GROUP']);

@Component({
  selector: 'app-farmer-create-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, MatCardModule, MatFormFieldModule, MatInputModule, MatSelectModule, MatButtonModule, PageHeader],
  template: `
    <app-page-header title="Register farmer" subtitle="The record starts as DRAFT. Complete contacts, then register and submit KYC."
                     backLink="/farmers" backLabel="Farmers" />
    <form [formGroup]="form" (ngSubmit)="submit()" novalidate>
      <mat-card appearance="outlined" class="section">
        <mat-card-header><mat-card-title>Farmer</mat-card-title></mat-card-header>
        <mat-card-content class="form-grid">
          <mat-form-field>
            <mat-label>Managing organization</mat-label>
            <mat-select formControlName="organization_id">
              @for (o of orgs(); track o.id) { <mat-option [value]="o.id">{{ o.name }}</mat-option> }
            </mat-select>
          </mat-form-field>
          <mat-form-field>
            <mat-label>Full name</mat-label>
            <input matInput formControlName="full_name" autocomplete="off" />
            @if (form.controls.full_name.invalid) { <mat-error>Enter the farmer's name.</mat-error> }
          </mat-form-field>
          <mat-form-field>
            <mat-label>Gender (optional)</mat-label>
            <mat-select formControlName="gender">
              <mat-option [value]="null">Not recorded</mat-option>
              @for (g of ['FEMALE', 'MALE', 'OTHER', 'UNDISCLOSED']; track g) { <mat-option [value]="g">{{ g }}</mat-option> }
            </mat-select>
          </mat-form-field>
          <mat-form-field>
            <mat-label>Preferred language (ISO code)</mat-label>
            <input matInput formControlName="preferred_language" placeholder="mr" />
          </mat-form-field>
          <mat-form-field>
            <mat-label>Primary phone</mat-label>
            <input matInput formControlName="primary_phone" inputmode="tel" placeholder="+91 98765 43210" />
            @if (form.controls.primary_phone.invalid) { <mat-error>Digits, spaces, +, ( ) and - only.</mat-error> }
          </mat-form-field>
        </mat-card-content>
      </mat-card>
      <mat-card appearance="outlined" class="section">
        <mat-card-header><mat-card-title>Location</mat-card-title></mat-card-header>
        <mat-card-content class="form-grid">
          <mat-form-field><mat-label>Village</mat-label><input matInput formControlName="village" /></mat-form-field>
          <mat-form-field><mat-label>Sub-district</mat-label><input matInput formControlName="sub_district" /></mat-form-field>
          <mat-form-field><mat-label>District</mat-label><input matInput formControlName="district" /></mat-form-field>
          <mat-form-field><mat-label>State</mat-label><input matInput formControlName="state" /></mat-form-field>
          <mat-form-field>
            <mat-label>Country (ISO code)</mat-label>
            <input matInput formControlName="country" maxlength="2" />
            @if (form.controls.country.invalid) { <mat-error>Two letters, e.g. IN.</mat-error> }
          </mat-form-field>
        </mat-card-content>
      </mat-card>
      @if (error(); as e) { <p class="form-error" role="alert">{{ e }}</p> }
      <div class="row-actions">
        <button mat-button type="button" (click)="cancel()">Cancel</button>
        <button mat-flat-button type="submit" [disabled]="saving()">Create farmer</button>
      </div>
    </form>
  `,
})
export class FarmerCreatePage implements OnInit {
  private readonly api = inject(FarmersApi);
  private readonly orgsApi = inject(OrganizationsApi);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly notify = inject(NotifyService);
  protected readonly orgs = signal<Pick<Organization, 'id' | 'name'>[]>([]);
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly form = new FormGroup({
    organization_id: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    full_name: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.minLength(2), Validators.maxLength(200)] }),
    gender: new FormControl<string | null>(null),
    preferred_language: new FormControl('', { nonNullable: true, validators: [Validators.pattern(/^[a-zA-Z]{2,3}(-[A-Za-z]{2})?$/)] }),
    primary_phone: new FormControl('', { nonNullable: true, validators: [Validators.pattern(/^\+?[0-9 ()-]{6,30}$/)] }),
    village: new FormControl('', { nonNullable: true }),
    sub_district: new FormControl('', { nonNullable: true }),
    district: new FormControl('', { nonNullable: true }),
    state: new FormControl('', { nonNullable: true }),
    country: new FormControl('IN', { nonNullable: true, validators: [Validators.required, Validators.pattern(/^[A-Za-z]{2}$/)] }),
  });

  ngOnInit(): void {
    // Organizations where the user may register farmers (from their role grants — no admin permission needed).
    const grants = this.auth.user()?.roles ?? [];
    const memberships = this.auth.user()?.organizations ?? [];
    const allowed = memberships.filter((m) => MANAGING.has(m.org_type) &&
      grants.some((g) => g.organization_id === m.organization_id) && this.auth.has(P.FARMERS_MANAGE));
    this.orgs.set(allowed.map((m) => ({ id: m.organization_id, name: m.organization_name })));
    if (allowed.length === 1) this.form.controls.organization_id.setValue(allowed[0].organization_id);
    if (!allowed.length && this.auth.has('organizations.read')) {
      this.orgsApi.list({ page_size: 100, status: 'ACTIVE' }).subscribe((p) =>
        this.orgs.set(p.items.filter((o) => MANAGING.has(o.org_type))));
    }
  }

  submit(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid || this.saving()) return;
    const v = this.form.getRawValue();
    const blank = (s: string) => (s.trim() ? s.trim() : null);
    this.saving.set(true);
    this.api.create({
      organization_id: v.organization_id, full_name: v.full_name.trim(), gender: v.gender, preferred_language: blank(v.preferred_language),
      primary_phone: blank(v.primary_phone), village: blank(v.village), sub_district: blank(v.sub_district), district: blank(v.district),
      state: blank(v.state), country: v.country.toUpperCase(),
    }).subscribe({
      next: (f) => {
        this.notify.success(`Farmer ${f.farmer_code} created.`);
        void this.router.navigate(['/farmers', f.id]);
      },
      error: (e: unknown) => {
        this.saving.set(false);
        const rest = applyServerErrors(this.form, e);
        this.error.set(rest.length ? rest.join(' ') : ApiError.from(e).message);
      },
    });
  }

  cancel(): void {
    void this.router.navigate(['/farmers']);
  }
}
