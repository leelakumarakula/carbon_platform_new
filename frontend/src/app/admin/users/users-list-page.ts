import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatPaginatorModule } from '@angular/material/paginator';
import { MatSelectModule } from '@angular/material/select';
import { MatSortModule } from '@angular/material/sort';
import { MatTableModule } from '@angular/material/table';
import { Router, RouterLink } from '@angular/router';
import { debounceTime, distinctUntilChanged } from 'rxjs';

import { AuthService } from '../../core/auth/auth.service';
import { P } from '../../core/auth/permissions';
import { PageHeader } from '../../shared/page-header';
import { PagedList } from '../../shared/paged-list';
import { StateView } from '../../shared/state-view';
import { StatusBadge } from '../../shared/status-badge';
import { UsersApi } from '../admin.api';
import { User, UserStatus } from '../admin.models';

@Component({
  selector: 'app-users-list-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, RouterLink, DatePipe, MatTableModule, MatPaginatorModule, MatSortModule, MatFormFieldModule,
    MatInputModule, MatSelectModule, MatButtonModule, MatIconModule, PageHeader, StateView, StatusBadge],
  template: `
    <app-page-header title="Users" subtitle="Accounts, their organizations and role grants.">
      @if (canManage) { <a mat-flat-button routerLink="/admin/users/new"><mat-icon>person_add</mat-icon> New user</a> }
    </app-page-header>

    <form class="filters" [formGroup]="filters">
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Search name, email or phone</mat-label>
        <input matInput formControlName="search" />
        <mat-icon matSuffix>search</mat-icon>
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Status</mat-label>
        <mat-select formControlName="status">
          <mat-option [value]="null">Any</mat-option>
          @for (s of statuses; track s) { <mat-option [value]="s">{{ s }}</mat-option> }
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>Environment</mat-label>
        <mat-select formControlName="environment">
          <mat-option [value]="null">Any</mat-option>
          <mat-option value="LIVE">Live</mat-option>
          <mat-option value="DEMO">Demo</mat-option>
        </mat-select>
      </mat-form-field>
    </form>

    <app-state-view [loading]="list.loading()" [error]="list.error()" [empty]="!list.loading() && !list.error() && list.total() === 0"
                    emptyText="No users match these filters." (retry)="list.load()" />

    <div class="table-wrap" [hidden]="list.total() === 0">
      <table mat-table [dataSource]="list.items()" matSort (matSortChange)="list.onSort($event)" matSortActive="email" matSortDirection="asc">
        <ng-container matColumnDef="email">
          <th mat-header-cell *matHeaderCellDef mat-sort-header>Email</th>
          <td mat-cell *matCellDef="let u"><a [routerLink]="['/admin/users', u.id]">{{ u.email }}</a></td>
        </ng-container>
        <ng-container matColumnDef="full_name">
          <th mat-header-cell *matHeaderCellDef mat-sort-header>Name</th>
          <td mat-cell *matCellDef="let u">{{ u.full_name }}</td>
        </ng-container>
        <ng-container matColumnDef="status">
          <th mat-header-cell *matHeaderCellDef mat-sort-header>Status</th>
          <td mat-cell *matCellDef="let u">
            <app-status-badge [status]="u.status" />
            @if (u.is_locked) { <app-status-badge status="LOCKED" /> }
            @if (u.must_change_password) { <app-status-badge status="WARNING" text="Must change password" /> }
            @if (u.environment === 'DEMO') { <app-status-badge status="DEMO" /> }
          </td>
        </ng-container>
        <ng-container matColumnDef="roles">
          <th mat-header-cell *matHeaderCellDef>Roles</th>
          <td mat-cell *matCellDef="let u" class="roles">{{ roleNames(u) }}</td>
        </ng-container>
        <ng-container matColumnDef="orgs">
          <th mat-header-cell *matHeaderCellDef>Organizations</th>
          <td mat-cell *matCellDef="let u">{{ orgNames(u) }}</td>
        </ng-container>
        <ng-container matColumnDef="last_login_at">
          <th mat-header-cell *matHeaderCellDef mat-sort-header>Last sign-in</th>
          <td mat-cell *matCellDef="let u">{{ u.last_login_at ? (u.last_login_at | date: 'short') : 'Never' }}</td>
        </ng-container>
        <tr mat-header-row *matHeaderRowDef="columns"></tr>
        <tr mat-row *matRowDef="let row; columns: columns" class="clickable" (click)="open(row)"></tr>
      </table>
      <mat-paginator [length]="list.total()" [pageIndex]="list.page() - 1" [pageSize]="list.pageSize()"
                     [pageSizeOptions]="[10, 25, 50, 100]" (page)="list.onPage($event)" showFirstLastButtons />
    </div>
  `,
})
export class UsersListPage implements OnInit {
  private readonly api = inject(UsersApi);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);
  protected readonly canManage = inject(AuthService).has(P.USERS_MANAGE);

  protected readonly columns = ['email', 'full_name', 'status', 'roles', 'orgs', 'last_login_at'];
  protected readonly statuses: UserStatus[] = ['ACTIVE', 'SUSPENDED', 'DEACTIVATED'];
  protected readonly filters = new FormGroup({
    search: new FormControl('', { nonNullable: true }),
    status: new FormControl<UserStatus | null>(null),
    environment: new FormControl<'LIVE' | 'DEMO' | null>(null),
  });

  protected readonly list = new PagedList<User>(
    (q) => this.api.list({ ...q, ...this.filters.getRawValue(), search: this.filters.controls.search.value.trim() }),
    this.destroyRef,
    'email',
  );

  ngOnInit(): void {
    this.filters.valueChanges
      .pipe(debounceTime(300), distinctUntilChanged((a, b) => JSON.stringify(a) === JSON.stringify(b)), takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.list.reset());
    this.list.load();
  }

  protected roleNames(u: User): string {
    return Array.from(new Set(u.roles.map((r) => r.role_name))).join(', ') || '—';
  }

  protected orgNames(u: User): string {
    return u.organizations.map((o) => o.organization_name).join(', ') || '—';
  }

  protected open(u: User): void {
    void this.router.navigate(['/admin/users', u.id]);
  }
}
