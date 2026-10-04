import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { Router } from '@angular/router';

import { ApiError } from '../core/api/api.models';
import { AuthService } from '../core/auth/auth.service';
import { P } from '../core/auth/permissions';
import { NotifyService } from '../core/notify.service';
import { label } from '../farmer/farmer.models';
import { applyServerErrors } from '../shared/forms';
import { PageHeader } from '../shared/page-header';
import { PROJECT_TYPES } from './project.models';
import { ProjectsApi } from './projects.api';

const OWNER_TYPES = new Set(['PROJECT_DEVELOPER', 'FIELD_PARTNER', 'FARMER_GROUP']);

@Component({
  selector: 'app-project-create-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, MatCardModule, MatFormFieldModule, MatInputModule, MatSelectModule, MatButtonModule, PageHeader],
  template: `
    <app-page-header title="New project" subtitle="Starts as DRAFT. Add verified farms, the team, standard / activity, crediting period and baseline next."
                     backLink="/projects" backLabel="Projects" />
    <form [formGroup]="form" (ngSubmit)="submit()" novalidate>
      <mat-card appearance="outlined" class="section">
        <mat-card-content class="form-grid">
          <mat-form-field>
            <mat-label>Organization</mat-label>
            <mat-select formControlName="organization_id">
              @for (o of orgs(); track o.id) { <mat-option [value]="o.id">{{ o.name }} ({{ o.code }})</mat-option> }
            </mat-select>
            @if (!orgs().length) { <mat-hint>You do not manage projects in any organization.</mat-hint> }
          </mat-form-field>
          <mat-form-field>
            <mat-label>Project name</mat-label>
            <input matInput formControlName="name" autocomplete="off" />
            @if (form.controls.name.invalid) { <mat-error>Enter a name (2–200 characters).</mat-error> }
          </mat-form-field>
          <mat-form-field>
            <mat-label>Project type</mat-label>
            <mat-select formControlName="project_type">
              @for (t of types; track t) { <mat-option [value]="t">{{ label(t) }}</mat-option> }
            </mat-select>
          </mat-form-field>
          <mat-form-field>
            <mat-label>Country (ISO code)</mat-label>
            <input matInput formControlName="country" maxlength="2" />
            @if (form.controls.country.invalid) { <mat-error>Two letters, e.g. IN.</mat-error> }
          </mat-form-field>
          <mat-form-field><mat-label>Region</mat-label><input matInput formControlName="region" /></mat-form-field>
          <mat-form-field>
            <mat-label>Planned start date</mat-label>
            <input matInput type="date" formControlName="start_date" />
          </mat-form-field>
          <mat-form-field class="full">
            <mat-label>Description</mat-label>
            <textarea matInput rows="3" formControlName="description"></textarea>
          </mat-form-field>
        </mat-card-content>
      </mat-card>
      <p class="muted small">No methodology is selected here. Methodology candidates and confirmation come with the methodology module;
        the project only records the standard / route and activity references.</p>
      @if (error(); as e) { <p class="form-error" role="alert">{{ e }}</p> }
      <div class="row-actions">
        <button mat-button type="button" (click)="cancel()">Cancel</button>
        <button mat-flat-button type="submit" [disabled]="saving()">Create project</button>
      </div>
    </form>
  `,
  styles: `.full { grid-column: 1 / -1; }`,
})
export class ProjectCreatePage implements OnInit {
  private readonly api = inject(ProjectsApi);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly notify = inject(NotifyService);
  protected readonly label = label;
  protected readonly types = PROJECT_TYPES;
  protected readonly orgs = signal<{ id: string; name: string; code: string }[]>([]);
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly form = new FormGroup({
    organization_id: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    name: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.minLength(2), Validators.maxLength(200)] }),
    project_type: new FormControl<string>('AGRICULTURAL_LAND_MANAGEMENT', { nonNullable: true }),
    country: new FormControl('IN', { nonNullable: true, validators: [Validators.required, Validators.pattern(/^[A-Za-z]{2}$/)] }),
    region: new FormControl('', { nonNullable: true }),
    start_date: new FormControl('', { nonNullable: true }),
    description: new FormControl('', { nonNullable: true }),
  });

  ngOnInit(): void {
    // Organizations where the user holds a role (and projects.manage somewhere); the server re-checks the exact scope.
    const user = this.auth.user();
    const grantOrgs = new Set((user?.roles ?? []).map((g) => g.organization_id).filter((o): o is string => !!o));
    const allowed = this.auth.has(P.PROJECTS_MANAGE)
      ? (user?.organizations ?? []).filter((m) => OWNER_TYPES.has(m.org_type) && grantOrgs.has(m.organization_id)) : [];
    this.orgs.set(allowed.map((m) => ({ id: m.organization_id, name: m.organization_name, code: m.organization_code })));
    if (allowed.length === 1) this.form.controls.organization_id.setValue(allowed[0].organization_id);
  }

  submit(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid || this.saving()) return;
    const v = this.form.getRawValue();
    const blank = (s: string) => (s.trim() ? s.trim() : null);
    this.saving.set(true);
    this.api.create({ organization_id: v.organization_id, name: v.name.trim(), project_type: v.project_type, country: v.country.toUpperCase(),
      region: blank(v.region), start_date: blank(v.start_date), description: blank(v.description) }).subscribe({
      next: (p) => {
        this.notify.success(`Project ${p.project_code} created.`);
        void this.router.navigate(['/projects', p.id]);
      },
      error: (e: unknown) => {
        this.saving.set(false);
        const rest = applyServerErrors(this.form, e);
        this.error.set(rest.length ? rest.join(' ') : ApiError.from(e).message);
      },
    });
  }

  cancel(): void {
    void this.router.navigate(['/projects']);
  }
}
