import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatPaginatorModule } from '@angular/material/paginator';
import { MatSelectModule } from '@angular/material/select';
import { MatSortModule } from '@angular/material/sort';
import { MatTableModule } from '@angular/material/table';
import { Router, RouterLink } from '@angular/router';
import { debounceTime } from 'rxjs';

import { ApiError } from '../../core/api/api.models';
import { AuthService } from '../../core/auth/auth.service';
import { P } from '../../core/auth/permissions';
import { NotifyService } from '../../core/notify.service';
import { applyServerErrors } from '../../shared/forms';
import { PageHeader } from '../../shared/page-header';
import { PagedList } from '../../shared/paged-list';
import { StateView } from '../../shared/state-view';
import { StatusBadge } from '../../shared/status-badge';
import { OrganizationsApi } from '../admin.api';
import { ORG_TYPES, OrgStatus, OrgType, Organization, orgTypeLabel } from '../admin.models';

@Component({
  selector: 'app-organizations-list-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, RouterLink, MatTableModule, MatPaginatorModule, MatSortModule, MatFormFieldModule, MatInputModule,
    MatSelectModule, MatButtonModule, MatIconModule, MatCardModule, PageHeader, StateView, StatusBadge],
  templateUrl: './organizations-list-page.html',
})
export class OrganizationsListPage implements OnInit {
  private readonly api = inject(OrganizationsApi);
  private readonly router = inject(Router);
  private readonly notify = inject(NotifyService);
  private readonly destroyRef = inject(DestroyRef);
  protected readonly canCreate = inject(AuthService).has(P.ORGANIZATIONS_MANAGE);

  protected readonly types = ORG_TYPES;
  protected readonly typeLabel = orgTypeLabel;
  protected readonly columns = ['code', 'name', 'org_type', 'country', 'members', 'status'];
  protected readonly showCreate = signal(false);
  protected readonly saving = signal(false);
  protected readonly createError = signal<string | null>(null);

  protected readonly filters = new FormGroup({
    search: new FormControl('', { nonNullable: true }),
    org_type: new FormControl<OrgType | null>(null),
    status: new FormControl<OrgStatus | null>(null),
  });

  protected readonly createForm = new FormGroup({
    code: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.pattern(/^[A-Za-z][A-Za-z0-9_-]{1,39}$/)] }),
    name: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.minLength(2), Validators.maxLength(200)] }),
    org_type: new FormControl<OrgType>('PROJECT_DEVELOPER', { nonNullable: true }),
    country: new FormControl('', { nonNullable: true, validators: [Validators.pattern(/^[A-Za-z]{2}$/)] }),
    registration_number: new FormControl('', { nonNullable: true, validators: [Validators.maxLength(100)] }),
    contact_email: new FormControl('', { nonNullable: true, validators: [Validators.email] }),
  });

  protected readonly list = new PagedList<Organization>(
    (q) => this.api.list({ ...q, ...this.filters.getRawValue(), search: this.filters.controls.search.value.trim() }),
    this.destroyRef,
    'name',
  );

  ngOnInit(): void {
    this.filters.valueChanges.pipe(debounceTime(300), takeUntilDestroyed(this.destroyRef)).subscribe(() => this.list.reset());
    this.list.load();
  }

  protected open(o: Organization): void {
    void this.router.navigate(['/admin/organizations', o.id]);
  }

  protected create(): void {
    this.createForm.markAllAsTouched();
    if (this.createForm.invalid) return;
    const v = this.createForm.getRawValue();
    this.saving.set(true);
    this.createError.set(null);
    this.api
      .create({ code: v.code, name: v.name.trim(), org_type: v.org_type, country: v.country || null,
        registration_number: v.registration_number.trim() || null, contact_email: v.contact_email.trim() || null })
      .subscribe({
        next: (o) => {
          this.notify.success(`Organization ${o.name} created.`);
          void this.router.navigate(['/admin/organizations', o.id]);
        },
        error: (e: unknown) => {
          this.saving.set(false);
          const rest = applyServerErrors(this.createForm, e);
          this.createError.set(rest.length ? rest.join(' ') : ApiError.from(e).message);
        },
      });
  }
}
