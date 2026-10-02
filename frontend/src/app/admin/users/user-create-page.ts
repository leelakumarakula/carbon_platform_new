import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormArray, FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { Router } from '@angular/router';
import { map } from 'rxjs';

import { ApiError } from '../../core/api/api.models';
import { NotifyService } from '../../core/notify.service';
import { applyServerErrors, passwordPolicyValidator } from '../../shared/forms';
import { PageHeader } from '../../shared/page-header';
import { generateTemporaryPassword } from '../../shared/password';
import { OrganizationsApi, RolesApi, UsersApi } from '../admin.api';
import { Organization, Role, orgTypeLabel } from '../admin.models';

type GrantForm = FormGroup<{ role_code: FormControl<string>; organization_id: FormControl<string | null> }>;

@Component({
  selector: 'app-user-create-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, MatCardModule, MatFormFieldModule, MatInputModule, MatSelectModule, MatButtonModule, MatIconModule, PageHeader],
  templateUrl: './user-create-page.html',
})
export class UserCreatePage implements OnInit {
  private readonly users = inject(UsersApi);
  private readonly orgsApi = inject(OrganizationsApi);
  private readonly rolesApi = inject(RolesApi);
  private readonly router = inject(Router);
  private readonly notify = inject(NotifyService);

  protected readonly orgs = signal<Organization[]>([]);
  protected readonly roles = signal<Role[]>([]);
  protected readonly saving = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly orgLabel = orgTypeLabel;

  protected readonly form = new FormGroup({
    email: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.email, Validators.maxLength(320)] }),
    full_name: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.minLength(2), Validators.maxLength(200)] }),
    phone: new FormControl('', { nonNullable: true, validators: [Validators.pattern(/^\+?[0-9 ()-]{6,30}$/)] }),
    organization_id: new FormControl<string | null>(null),
    title: new FormControl('', { nonNullable: true, validators: [Validators.maxLength(120)] }),
    temporary_password: new FormControl(generateTemporaryPassword(), { nonNullable: true, validators: [Validators.required, passwordPolicyValidator] }),
    roles: new FormArray<GrantForm>([]),
  });

  private readonly selectedOrg = toSignal(this.form.controls.organization_id.valueChanges.pipe(map((v) => v)), { initialValue: null });
  protected readonly selectedOrgName = computed(() => this.orgs().find((o) => o.id === this.selectedOrg())?.name ?? null);

  ngOnInit(): void {
    this.orgsApi.list({ page_size: 100, status: 'ACTIVE', sort: 'name' }).subscribe((p) => this.orgs.set(p.items.filter((o) => o.org_type !== 'PLATFORM')));
    this.rolesApi.list().subscribe((r) => this.roles.set(r));
  }

  protected rolesFor(scope: 'PLATFORM' | 'ORGANIZATION'): Role[] {
    return this.roles().filter((r) => r.scope === scope);
  }

  protected roleScope(code: string): 'PLATFORM' | 'ORGANIZATION' | null {
    return this.roles().find((r) => r.code === code)?.scope ?? null;
  }

  protected addGrant(): void {
    this.form.controls.roles.push(
      new FormGroup({
        role_code: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
        organization_id: new FormControl<string | null>(null),
      }),
    );
  }

  protected removeGrant(i: number): void {
    this.form.controls.roles.removeAt(i);
  }

  protected regenerate(): void {
    this.form.controls.temporary_password.setValue(generateTemporaryPassword());
  }

  submit(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid || this.saving()) return;
    const v = this.form.getRawValue();
    const roles = v.roles.map((g) => ({
      role_code: g.role_code,
      organization_id: this.roleScope(g.role_code) === 'ORGANIZATION' ? v.organization_id : null,
    }));
    if (roles.some((r) => this.roleScope(r.role_code) === 'ORGANIZATION' && !r.organization_id)) {
      this.error.set('Organization roles need the user to belong to an organization. Choose one above.');
      return;
    }
    this.saving.set(true);
    this.error.set(null);
    this.users
      .create({
        email: v.email.trim(),
        full_name: v.full_name.trim(),
        phone: v.phone.trim() || null,
        organization_id: v.organization_id,
        title: v.title.trim() || null,
        temporary_password: v.temporary_password,
        roles,
      })
      .subscribe({
        next: (u) => {
          this.notify.success(`User ${u.email} created. Share the temporary password securely.`);
          void this.router.navigate(['/admin/users', u.id]);
        },
        error: (e: unknown) => {
          this.saving.set(false);
          const leftover = applyServerErrors(this.form, e);
          this.error.set(leftover.length ? leftover.join(' ') : ApiError.from(e).message);
        },
      });
  }

  cancel(): void {
    void this.router.navigate(['/admin/users']);
  }
}
