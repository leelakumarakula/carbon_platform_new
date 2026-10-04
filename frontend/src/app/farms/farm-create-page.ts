import { AsyncPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatAutocompleteModule, MatAutocompleteSelectedEvent } from '@angular/material/autocomplete';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { ActivatedRoute, Router } from '@angular/router';
import { Observable, debounceTime, distinctUntilChanged, filter, map, startWith, switchMap } from 'rxjs';

import { ApiError } from '../core/api/api.models';
import { AuthService } from '../core/auth/auth.service';
import { P } from '../core/auth/permissions';
import { NotifyService } from '../core/notify.service';
import { Farmer, FarmerSummary, label } from '../farmer/farmer.models';
import { FarmersApi } from '../farmer/farmers.api';
import { applyServerErrors } from '../shared/forms';
import { PageHeader } from '../shared/page-header';
import { TENURES } from './farm.models';
import { FarmsApi } from './farms.api';

@Component({
  selector: 'app-farm-create-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, AsyncPipe, MatAutocompleteModule, MatCardModule, MatFormFieldModule, MatInputModule, MatSelectModule, MatButtonModule,
    PageHeader],
  template: `
    <app-page-header title="Add farm" [subtitle]="farmer() ? 'For ' + farmer()!.full_name + ' (' + farmer()!.farmer_code + ')' : null"
                     [backLink]="farmer() && !picking() ? '/farmers/' + farmer()!.id : '/farms'" backLabel="Back" />
    @if (picking()) {
      <mat-card appearance="outlined" class="section">
        <mat-card-content>
          <mat-form-field class="full"><mat-label>Farmer</mat-label>
            <input matInput [formControl]="farmerSearch" [matAutocomplete]="auto" placeholder="Search name or code" />
            <mat-autocomplete #auto="matAutocomplete" [displayWith]="display" (optionSelected)="pick($event)">
              @for (f of candidates | async; track f.id) {
                <mat-option [value]="f">{{ f.full_name }} · {{ f.farmer_code }}<span class="muted small"> · {{ f.village }}</span></mat-option>
              }
            </mat-autocomplete>
            <mat-hint>Only registered, non-suspended farmers can have farms added.</mat-hint>
          </mat-form-field>
        </mat-card-content>
      </mat-card>
    }
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
  styles: `.full { width: 100%; }`,
})
export class FarmCreatePage implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly farmersApi = inject(FarmersApi);
  private readonly api = inject(FarmsApi);
  private readonly notify = inject(NotifyService);
  private readonly auth = inject(AuthService);
  protected readonly farmer = signal<Farmer | null>(null);
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);
  /** Staff opening /farms/new directly choose the farmer here (the farmer tab passes ?farmer=). */
  protected readonly picking = signal(false);
  protected readonly farmerSearch = new FormControl<string | FarmerSummary>('', { nonNullable: true });
  protected readonly candidates: Observable<FarmerSummary[]> = this.farmerSearch.valueChanges.pipe(
    startWith(''),
    filter((v): v is string => typeof v === 'string'),
    debounceTime(250),
    distinctUntilChanged(),
    switchMap((q) => this.farmersApi.list({ search: q.trim() || null, page_size: 20 })),
    map((p) => p.items.filter((f) => eligible(f.status))),
  );
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
    if (id) this.load(id);
    else if (this.auth.has(P.FARMERS_SELF)) this.load(null);
    else this.picking.set(true);
  }

  private load(id: string | null): void {
    this.error.set(null);
    (id ? this.farmersApi.get(id) : this.farmersApi.me()).subscribe({
      next: (f) => {
        if (!eligible(f.status)) {                                  // the server re-checks status and permission
          this.farmer.set(null);
          this.error.set(f.status === 'DRAFT' ? 'Register the farmer before adding farms.' : 'Farms cannot be added for a suspended farmer.');
          return;
        }
        this.farmer.set(f);
        this.form.patchValue({ village: f.village ?? '', district: f.district ?? '', state: f.state ?? '', country: f.country });
      },
      error: () => {
        // A staff member who is not a farmer falls back to picking one.
        if (!id && this.auth.has(P.FARMS_MANAGE)) this.picking.set(true);
        else this.error.set('Open this page from a farmer record (Farmers → farmer → Farms → Add farm).');
      },
    });
  }

  protected pick(e: MatAutocompleteSelectedEvent): void {
    this.load((e.option.value as FarmerSummary).id);
  }

  protected display(f: FarmerSummary | string | null): string {
    return f && typeof f === 'object' ? `${f.full_name} (${f.farmer_code})` : (f ?? '');
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

/** Mirrors the farmer Farms tab: no farms for DRAFT or SUSPENDED farmers. */
function eligible(status: string): boolean {
  return !['DRAFT', 'SUSPENDED'].includes(status);
}
