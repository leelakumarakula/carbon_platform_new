import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { ActivatedRoute, Router } from '@angular/router';

import { ApiError } from '../core/api/api.models';
import { NotifyService } from '../core/notify.service';
import { Farmer, label } from '../farmer/farmer.models';
import { FarmersApi } from '../farmer/farmers.api';
import { applyServerErrors } from '../shared/forms';
import { PageHeader } from '../shared/page-header';
import { TENURES } from './farm.models';
import { FarmsApi } from './farms.api';

@Component({
  selector: 'app-farm-create-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, MatCardModule, MatFormFieldModule, MatInputModule, MatSelectModule, MatButtonModule, PageHeader],
  template: `
    <app-page-header title="Add farm" [subtitle]="farmer() ? 'For ' + farmer()!.full_name + ' (' + farmer()!.farmer_code + ')' : null"
                     [backLink]="farmer() ? '/farmers/' + farmer()!.id : '/farms'" backLabel="Back" />
    <form [formGroup]="form" (ngSubmit)="submit()" novalidate>
      <mat-card appearance="outlined" class="section">
        <mat-card-content class="form-grid">
          <mat-form-field><mat-label>Farm name</mat-label><input matInput formControlName="name" placeholder="North field" /></mat-form-field>
          <mat-form-field><mat-label>Land tenure</mat-label>
            <mat-select formControlName="land_tenure">@for (t of tenures; track t) { <mat-option [value]="t">{{ label(t) }}</mat-option> }</mat-select>
          </mat-form-field>
          <mat-form-field><mat-label>Declared area (ha, optional)</mat-label><input matInput type="number" step="0.0001" min="0" formControlName="declared" />
            <mat-hint>The authoritative area is measured from the boundary.</mat-hint></mat-form-field>
          <mat-form-field><mat-label>Village</mat-label><input matInput formControlName="village" /></mat-form-field>
          <mat-form-field><mat-label>District</mat-label><input matInput formControlName="district" /></mat-form-field>
          <mat-form-field><mat-label>State</mat-label><input matInput formControlName="state" /></mat-form-field>
          <mat-form-field><mat-label>Country</mat-label><input matInput formControlName="country" maxlength="2" /></mat-form-field>
        </mat-card-content>
      </mat-card>
      @if (error(); as e) { <p class="form-error" role="alert">{{ e }}</p> }
      <div class="row-actions">
        <button mat-flat-button type="submit" [disabled]="saving() || !farmer()">Create farm and draw boundary</button>
      </div>
    </form>
  `,
})
export class FarmCreatePage implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly farmersApi = inject(FarmersApi);
  private readonly api = inject(FarmsApi);
  private readonly notify = inject(NotifyService);
  protected readonly farmer = signal<Farmer | null>(null);
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly tenures = TENURES;
  protected readonly label = label;
  protected readonly form = new FormGroup({
    name: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.minLength(2)] }),
    land_tenure: new FormControl('OWNED', { nonNullable: true }),
    declared: new FormControl<number | null>(null, { validators: [Validators.min(0.0001)] }),
    village: new FormControl('', { nonNullable: true }),
    district: new FormControl('', { nonNullable: true }),
    state: new FormControl('', { nonNullable: true }),
    country: new FormControl('IN', { nonNullable: true, validators: [Validators.required, Validators.pattern(/^[A-Za-z]{2}$/)] }),
  });

  ngOnInit(): void {
    const id = this.route.snapshot.queryParamMap.get('farmer');
    const load = id ? this.farmersApi.get(id) : this.farmersApi.me();
    load.subscribe({
      next: (f) => {
        this.farmer.set(f);
        this.form.patchValue({ village: f.village ?? '', district: f.district ?? '', state: f.state ?? '', country: f.country });
      },
      error: () => this.error.set('Open this page from a farmer record (Farmers → farmer → Farms → Add farm).'),
    });
  }

  submit(): void {
    this.form.markAllAsTouched();
    const f = this.farmer();
    if (!f || this.form.invalid) return;
    const v = this.form.getRawValue();
    this.saving.set(true);
    this.api.create({ farmer_id: f.id, name: v.name.trim(), land_tenure: v.land_tenure, declared_area_hectares: v.declared,
      village: v.village || null, district: v.district || null, state: v.state || null, country: v.country.toUpperCase() }).subscribe({
      next: (farm) => {
        this.notify.success(`Farm ${farm.farm_code} created. Now draw or upload its boundary.`);
        void this.router.navigate(['/farms', farm.id], { queryParams: { tab: 'boundary' } });
      },
      error: (e: unknown) => {
        this.saving.set(false);
        const rest = applyServerErrors(this.form, e);
        this.error.set(rest.length ? rest.join(' ') : ApiError.from(e).message);
      },
    });
  }
}
