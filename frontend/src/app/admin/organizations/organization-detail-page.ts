import { AsyncPipe, DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatTableModule } from '@angular/material/table';
import { RouterLink } from '@angular/router';
import { Observable, debounceTime, distinctUntilChanged, filter, map, of, switchMap } from 'rxjs';

import { ApiError } from '../../core/api/api.models';
import { AuthService } from '../../core/auth/auth.service';
import { P } from '../../core/auth/permissions';
import { NotifyService } from '../../core/notify.service';
import { PageHeader } from '../../shared/page-header';
import { askReason } from '../../shared/reason-dialog';
import { StateView } from '../../shared/state-view';
import { StatusBadge } from '../../shared/status-badge';
import { OrganizationsApi, UsersApi } from '../admin.api';
import { Member, ORG_TRANSITIONS, OrgStatus, Organization, User, orgTypeLabel } from '../admin.models';

const ACTION: Record<OrgStatus, string> = { ACTIVE: 'Reactivate', SUSPENDED: 'Suspend', ARCHIVED: 'Archive' };

@Component({
  selector: 'app-organization-detail-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, RouterLink, DatePipe, AsyncPipe, MatCardModule, MatFormFieldModule, MatInputModule, MatButtonModule, MatIconModule,
    MatTableModule, MatAutocompleteModule, PageHeader, StateView, StatusBadge],
  templateUrl: './organization-detail-page.html',
  styles: `.add-member { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-top: 16px; } .add-member mat-form-field { min-width: 260px; }`,
})
export class OrganizationDetailPage implements OnInit {
  readonly id = input.required<string>();

  private readonly api = inject(OrganizationsApi);
  private readonly usersApi = inject(UsersApi);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotifyService);
  protected readonly auth = inject(AuthService);

  protected readonly org = signal<Organization | null>(null);
  protected readonly members = signal<Member[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<ApiError | null>(null);
  protected readonly busy = signal(false);
  protected readonly typeLabel = orgTypeLabel;
  protected readonly action = ACTION;
  protected readonly memberColumns = ['name', 'title', 'status', 'joined', 'actions'];

  protected readonly canEdit = this.auth.has(P.ORGANIZATIONS_MANAGE);
  protected readonly canStatus = this.auth.has(P.ORGANIZATIONS_MANAGE);
  protected readonly canMembers = this.auth.has(P.ORGANIZATIONS_MANAGE_MEMBERS);
  protected readonly transitions = computed(() => {
    const o = this.org();
    return o && o.org_type !== 'PLATFORM' ? ORG_TRANSITIONS[o.status] : [];
  });

  protected readonly form = new FormGroup({
    name: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.minLength(2), Validators.maxLength(200)] }),
    country: new FormControl('', { nonNullable: true, validators: [Validators.pattern(/^[A-Za-z]{2}$/)] }),
    registration_number: new FormControl('', { nonNullable: true, validators: [Validators.maxLength(100)] }),
    contact_email: new FormControl('', { nonNullable: true, validators: [Validators.email] }),
  });

  protected readonly memberSearch = new FormControl<string | User>('', { nonNullable: true });
  protected readonly memberTitle = new FormControl('', { nonNullable: true, validators: [Validators.maxLength(120)] });
  protected readonly candidates: Observable<User[]> = this.memberSearch.valueChanges.pipe(
    filter((v): v is string => typeof v === 'string'),
    debounceTime(250),
    distinctUntilChanged(),
    switchMap((q) => (q.trim().length < 2 ? of([]) : this.usersApi.list({ search: q.trim(), page_size: 10 }).pipe(map((p) => p.items)))),
    map((users) => users.filter((u) => !this.members().some((m) => m.user_id === u.id))),
  );

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.api.get(this.id()).subscribe({
      next: (o) => {
        this.setOrg(o);
        this.loadMembers();
      },
      error: (e: unknown) => {
        this.error.set(ApiError.from(e));
        this.loading.set(false);
      },
    });
  }

  private setOrg(o: Organization): void {
    this.org.set(o);
    this.loading.set(false);
    this.busy.set(false);
    this.form.reset({ name: o.name, country: o.country ?? '', registration_number: o.registration_number ?? '', contact_email: o.contact_email ?? '' });
    if (!this.canEdit || o.status === 'ARCHIVED') this.form.disable();
  }

  private loadMembers(): void {
    this.api.members(this.id()).subscribe({ next: (m) => this.members.set(m), error: (e: unknown) => this.notify.error(e) });
  }

  protected display(u: User | string | null): string {
    return typeof u === 'string' ? u : u ? `${u.full_name} <${u.email}>` : '';
  }

  save(): void {
    if (this.form.invalid || !this.form.dirty) return;
    const v = this.form.getRawValue();
    this.busy.set(true);
    this.api.update(this.id(), { name: v.name.trim(), country: v.country || null, registration_number: v.registration_number.trim() || null,
      contact_email: v.contact_email.trim() || null }).subscribe({
      next: (o) => {
        this.setOrg(o);
        this.notify.success('Organization saved.');
      },
      error: (e: unknown) => {
        this.busy.set(false);
        this.notify.error(e);
      },
    });
  }

  changeStatus(target: OrgStatus): void {
    const o = this.org()!;
    askReason(this.dialog, {
      title: `${ACTION[target]} ${o.name}?`,
      message: target === 'ARCHIVED' ? 'Archiving is permanent. The organization becomes read-only.' : undefined,
      confirmLabel: ACTION[target],
      danger: target !== 'ACTIVE',
    }).subscribe((r) => {
      if (!r) return;
      this.busy.set(true);
      this.api.changeStatus(o.id, target, r.reason).subscribe({
        next: (updated) => {
          this.setOrg(updated);
          this.notify.success(`Organization ${ACTION[target].toLowerCase()}d.`);
        },
        error: (e: unknown) => {
          this.busy.set(false);
          this.notify.error(e);
        },
      });
    });
  }

  addMember(): void {
    const picked = this.memberSearch.value;
    if (typeof picked === 'string') {
      this.notify.error(new ApiError(0, 'CLIENT', 'Pick a user from the suggestions.'));
      return;
    }
    this.busy.set(true);
    this.api.addMember(this.id(), { user_id: picked.id, title: this.memberTitle.value.trim() || null }).subscribe({
      next: () => {
        this.busy.set(false);
        this.memberSearch.setValue('');
        this.memberTitle.setValue('');
        this.notify.success(`${picked.full_name} added.`);
        this.load();
      },
      error: (e: unknown) => {
        this.busy.set(false);
        this.notify.error(e);
      },
    });
  }

  removeMember(m: Member): void {
    askReason(this.dialog, {
      title: `Remove ${m.full_name}?`,
      message: 'Every role this person holds inside this organization is revoked as well.',
      confirmLabel: 'Remove',
      danger: true,
    }).subscribe((r) => {
      if (!r) return;
      this.api.removeMember(this.id(), m.user_id, r.reason).subscribe({
        next: () => {
          this.notify.success(`${m.full_name} removed.`);
          this.load();
        },
        error: (e: unknown) => this.notify.error(e),
      });
    });
  }
}
