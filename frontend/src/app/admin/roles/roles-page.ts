import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatListModule } from '@angular/material/list';
import { MatSelectModule } from '@angular/material/select';
import { MatTooltipModule } from '@angular/material/tooltip';
import { forkJoin } from 'rxjs';

import { ApiError } from '../../core/api/api.models';
import { AuthService } from '../../core/auth/auth.service';
import { P } from '../../core/auth/permissions';
import { NotifyService } from '../../core/notify.service';
import { PageHeader } from '../../shared/page-header';
import { StateView } from '../../shared/state-view';
import { StatusBadge } from '../../shared/status-badge';
import { RolesApi } from '../admin.api';
import { Permission, Role } from '../admin.models';

interface PermissionGroup {
  module: string;
  permissions: Permission[];
}

/** Master/detail: role list on the left, permission matrix of the selected role on the right. */
@Component({
  selector: 'app-roles-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, MatCardModule, MatListModule, MatCheckboxModule, MatButtonModule, MatIconModule, MatFormFieldModule,
    MatInputModule, MatSelectModule, MatTooltipModule, PageHeader, StateView, StatusBadge],
  templateUrl: './roles-page.html',
  styles: `
    .layout { display: grid; grid-template-columns: minmax(260px, 340px) 1fr; gap: 16px; align-items: start; }
    @media (max-width: 900px) { .layout { grid-template-columns: 1fr; } }
    .role-item small { color: var(--mat-sys-on-surface-variant); }
    .selected { background: var(--mat-sys-secondary-container); }
    .group h3 { font: var(--mat-sys-title-small); text-transform: capitalize; margin: 16px 0 4px; }
    .perm { display: flex; flex-direction: column; margin-left: 40px; margin-top: -8px; margin-bottom: 6px; color: var(--mat-sys-on-surface-variant); font-size: 12px; }
  `,
})
export class RolesPage implements OnInit {
  private readonly api = inject(RolesApi);
  private readonly notify = inject(NotifyService);
  private readonly auth = inject(AuthService);

  protected readonly roles = signal<Role[]>([]);
  protected readonly permissions = signal<Permission[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<ApiError | null>(null);
  protected readonly selectedId = signal<string | null>(null);
  protected readonly draft = signal<Set<string>>(new Set());
  protected readonly saving = signal(false);
  protected readonly creating = signal(false);

  protected readonly canManage = this.auth.has(P.ROLES_MANAGE);
  protected readonly selected = computed(() => this.roles().find((r) => r.id === this.selectedId()) ?? null);
  protected readonly editable = computed(() => this.canManage && !!this.selected() && !this.selected()!.is_system);
  protected readonly dirty = computed(() => {
    const r = this.selected();
    if (!r) return false;
    const d = this.draft();
    return d.size !== r.permissions.length || r.permissions.some((p) => !d.has(p));
  });
  protected readonly groups = computed<PermissionGroup[]>(() => {
    const byModule = new Map<string, Permission[]>();
    for (const p of this.permissions()) byModule.set(p.module, [...(byModule.get(p.module) ?? []), p]);
    return Array.from(byModule, ([module, permissions]) => ({ module, permissions }));
  });

  protected readonly createForm = new FormGroup({
    code: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.pattern(/^[A-Za-z][A-Za-z0-9_]{2,59}$/)] }),
    name: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.minLength(2)] }),
    description: new FormControl('', { nonNullable: true }),
    scope: new FormControl<'PLATFORM' | 'ORGANIZATION'>('ORGANIZATION', { nonNullable: true }),
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set(null);
    forkJoin({ roles: this.api.list(), permissions: this.api.permissions() }).subscribe({
      next: ({ roles, permissions }) => {
        this.roles.set(roles);
        this.permissions.set(permissions);
        this.loading.set(false);
        this.select(this.selectedId() ?? roles[0]?.id ?? null);
      },
      error: (e: unknown) => {
        this.error.set(ApiError.from(e));
        this.loading.set(false);
      },
    });
  }

  select(id: string | null): void {
    this.selectedId.set(id);
    this.draft.set(new Set(this.roles().find((r) => r.id === id)?.permissions ?? []));
  }

  /** You may only add permissions you hold platform-wide (server enforces the same rule). */
  protected grantable(code: string): boolean {
    return this.auth.me()?.platform_permissions.includes(code) ?? false;
  }

  toggle(code: string, on: boolean): void {
    const next = new Set(this.draft());
    if (on) next.add(code);
    else next.delete(code);
    this.draft.set(next);
  }

  save(): void {
    const r = this.selected();
    if (!r) return;
    this.saving.set(true);
    this.api.setPermissions(r.id, Array.from(this.draft()).sort()).subscribe({
      next: (updated) => {
        this.roles.update((list) => list.map((x) => (x.id === updated.id ? updated : x)));
        this.select(updated.id);
        this.saving.set(false);
        this.notify.success('Permissions saved.');
      },
      error: (e: unknown) => {
        this.saving.set(false);
        this.notify.error(e);
      },
    });
  }

  create(): void {
    this.createForm.markAllAsTouched();
    if (this.createForm.invalid) return;
    const v = this.createForm.getRawValue();
    this.saving.set(true);
    this.api.create({ code: v.code, name: v.name.trim(), description: v.description.trim() || null, scope: v.scope, permissions: [] }).subscribe({
      next: (role) => {
        this.saving.set(false);
        this.creating.set(false);
        this.createForm.reset({ code: '', name: '', description: '', scope: 'ORGANIZATION' });
        this.roles.update((list) => [...list, role]);
        this.select(role.id);
        this.notify.success(`Role ${role.name} created. Now choose its permissions.`);
      },
      error: (e: unknown) => {
        this.saving.set(false);
        this.notify.error(e);
      },
    });
  }
}
