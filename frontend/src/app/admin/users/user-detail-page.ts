import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatTooltipModule } from '@angular/material/tooltip';
import { RouterLink } from '@angular/router';
import { Observable } from 'rxjs';

import { ApiError } from '../../core/api/api.models';
import { AuthService } from '../../core/auth/auth.service';
import { P } from '../../core/auth/permissions';
import { NotifyService } from '../../core/notify.service';
import { PageHeader } from '../../shared/page-header';
import { askReason } from '../../shared/reason-dialog';
import { reloadOn } from '../../shared/reload-on';
import { StateView } from '../../shared/state-view';
import { StatusBadge } from '../../shared/status-badge';
import { RolesApi, UsersApi } from '../admin.api';
import { Role, USER_TRANSITIONS, User, UserStatus } from '../admin.models';

const ACTION_LABEL: Record<UserStatus, string> = { ACTIVE: 'Reactivate', SUSPENDED: 'Suspend', DEACTIVATED: 'Deactivate' };

@Component({
  selector: 'app-user-detail-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, RouterLink, DatePipe, MatCardModule, MatFormFieldModule, MatInputModule, MatSelectModule, MatButtonModule,
    MatIconModule, MatTooltipModule, PageHeader, StateView, StatusBadge],
  templateUrl: './user-detail-page.html',
  styles: `
    .grant { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--mat-sys-outline-variant); }
    .grant small { color: var(--mat-sys-on-surface-variant); }
    .grant-form { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; margin-top: 16px; }
    .grant-form mat-form-field { min-width: 220px; }
    .lock { display: flex; align-items: center; gap: 12px; padding: 12px 16px; border-radius: 8px; background: #fdecec; color: #8e1b1b; margin-bottom: 16px; }
  `,
})
export class UserDetailPage implements OnInit {
  /** Route parameter (withComponentInputBinding). */
  readonly id = input.required<string>();

  private readonly api = inject(UsersApi);
  private readonly rolesApi = inject(RolesApi);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotifyService);
  protected readonly auth = inject(AuthService);

  protected readonly user = signal<User | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<ApiError | null>(null);
  protected readonly roles = signal<Role[]>([]);
  protected readonly busy = signal(false);

  protected readonly canManage = this.auth.has(P.USERS_MANAGE);
  protected readonly canAssign = this.auth.has(P.USERS_ASSIGN_ROLES);
  protected readonly canUnlock = this.auth.has(P.SECURITY_MANAGE);
  protected readonly isSelf = computed(() => this.user()?.id === this.auth.user()?.id);
  protected readonly transitions = computed(() => (this.user() ? USER_TRANSITIONS[this.user()!.status] : []));
  protected readonly actionLabel = ACTION_LABEL;

  protected readonly profile = new FormGroup({
    full_name: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.minLength(2), Validators.maxLength(200)] }),
    phone: new FormControl('', { nonNullable: true, validators: [Validators.pattern(/^\+?[0-9 ()-]{6,30}$/)] }),
  });

  protected readonly grant = new FormGroup({
    role_code: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    organization_id: new FormControl<string | null>(null),
  });

  protected readonly grantScope = signal<'PLATFORM' | 'ORGANIZATION' | null>(null);

  constructor() {
    reloadOn(this.id, () => {
      this.user.set(null);
      this.loading.set(true);
      this.load();
    });
  }

  ngOnInit(): void {
    if (this.canAssign) this.rolesApi.list().subscribe((r) => this.roles.set(r));
    this.grant.controls.role_code.valueChanges.subscribe((code) => {
      this.grantScope.set(this.roles().find((r) => r.code === code)?.scope ?? null);
      this.grant.controls.organization_id.setValue(null);
    });
  }

  load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.api.get(this.id()).subscribe({
      next: (u) => this.setUser(u),
      error: (e: unknown) => {
        this.error.set(ApiError.from(e));
        this.loading.set(false);
      },
    });
  }

  private setUser(u: User): void {
    this.user.set(u);
    this.loading.set(false);
    this.busy.set(false);
    this.profile.reset({ full_name: u.full_name, phone: u.phone ?? '' });
    if (!this.canManage || u.status === 'DEACTIVATED') this.profile.disable();
  }

  private run(obs: Observable<User>, success: string): void {
    this.busy.set(true);
    obs.subscribe({
      next: (u) => {
        this.setUser(u);
        this.notify.success(success);
      },
      error: (e: unknown) => {
        this.busy.set(false);
        this.notify.error(e);
      },
    });
  }

  saveProfile(): void {
    if (this.profile.invalid || !this.profile.dirty) return;
    const v = this.profile.getRawValue();
    this.run(this.api.update(this.id(), { full_name: v.full_name.trim(), phone: v.phone.trim() || null }), 'Profile saved.');
  }

  changeStatus(target: UserStatus): void {
    const u = this.user()!;
    askReason(this.dialog, {
      title: `${ACTION_LABEL[target]} ${u.full_name}?`,
      message:
        target === 'DEACTIVATED'
          ? 'Deactivation is permanent: the account can never be reactivated. All sessions end immediately.'
          : target === 'SUSPENDED'
            ? 'All sessions end immediately. The account can be reactivated later.'
            : undefined,
      confirmLabel: ACTION_LABEL[target],
      danger: target !== 'ACTIVE',
    }).subscribe((r) => {
      if (r) this.run(this.api.changeStatus(u.id, target, r.reason), `User ${ACTION_LABEL[target].toLowerCase()}d.`);
    });
  }

  resetPassword(): void {
    askReason(this.dialog, { title: 'Reset password', confirmLabel: 'Reset password', withPassword: true,
      message: 'All of the user’s sessions end. They must choose a new password at next sign-in.' })
      .subscribe((r) => {
        if (r?.password) this.run(this.api.resetPassword(this.id(), r.password, r.reason), 'Temporary password set.');
      });
  }

  unlock(): void {
    askReason(this.dialog, { title: 'Unlock account', confirmLabel: 'Unlock', message: 'Confirm you have verified the user’s identity.' })
      .subscribe((r) => {
        if (r) this.run(this.api.unlock(this.id(), r.reason), 'Account unlocked.');
      });
  }

  addRole(): void {
    if (this.grant.invalid) return;
    const v = this.grant.getRawValue();
    if (this.grantScope() === 'ORGANIZATION' && !v.organization_id) {
      this.notify.error(new ApiError(0, 'CLIENT', 'Choose the organization this role applies in.'));
      return;
    }
    this.run(this.api.grantRole(this.id(), { role_code: v.role_code, organization_id: this.grantScope() === 'ORGANIZATION' ? v.organization_id : null }),
      'Role granted.');
    this.grant.reset({ role_code: '', organization_id: null });
  }

  revokeRole(userRoleId: string, roleName: string): void {
    askReason(this.dialog, { title: `Revoke ${roleName}?`, confirmLabel: 'Revoke', danger: true }).subscribe((r) => {
      if (r) this.run(this.api.revokeRole(this.id(), userRoleId, r.reason), 'Role revoked.');
    });
  }
}
