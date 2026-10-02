import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { RouterLink } from '@angular/router';

import { orgTypeLabel } from '../admin/admin.models';
import { AuthService } from '../core/auth/auth.service';
import { PageHeader } from '../shared/page-header';
import { StatusBadge } from '../shared/status-badge';

@Component({
  selector: 'app-profile-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatCardModule, MatButtonModule, RouterLink, DatePipe, PageHeader, StatusBadge],
  template: `
    <app-page-header title="My profile">
      <a mat-stroked-button routerLink="/change-password">Change password</a>
    </app-page-header>
    @if (auth.user(); as u) {
      <div class="cards">
        <mat-card appearance="outlined">
          <mat-card-content>
            <dl class="kv">
              <dt>Name</dt><dd>{{ u.full_name }}</dd>
              <dt>Email</dt><dd>{{ u.email }}</dd>
              <dt>Phone</dt><dd>{{ u.phone ?? '—' }}</dd>
              <dt>Status</dt><dd><app-status-badge [status]="u.status" /></dd>
              <dt>Environment</dt><dd><app-status-badge [status]="u.environment" /></dd>
              <dt>Last sign-in</dt><dd>{{ u.last_login_at ? (u.last_login_at | date: 'medium') : '—' }}</dd>
              <dt>Multi-factor</dt><dd>{{ u.mfa_enabled ? 'Enabled' : 'Not enabled' }}</dd>
            </dl>
          </mat-card-content>
        </mat-card>
        <mat-card appearance="outlined">
          <mat-card-header><mat-card-title>Organizations</mat-card-title></mat-card-header>
          <mat-card-content>
            @for (m of u.organizations; track m.organization_id) {
              <p><strong>{{ m.organization_name }}</strong> · {{ label(m.org_type) }} @if (m.title) { · {{ m.title }} }</p>
            } @empty { <p class="muted">Not a member of any organization.</p> }
          </mat-card-content>
        </mat-card>
        <mat-card appearance="outlined">
          <mat-card-header><mat-card-title>Roles</mat-card-title></mat-card-header>
          <mat-card-content>
            @for (r of u.roles; track r.id) {
              <p><strong>{{ r.role_name }}</strong> · {{ r.organization_name ?? 'Platform-wide' }}</p>
            } @empty { <p class="muted">No roles assigned.</p> }
          </mat-card-content>
        </mat-card>
      </div>
    }
  `,
  styles: `.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; } .muted { color: var(--mat-sys-on-surface-variant); }`,
})
export class ProfilePage {
  protected readonly auth = inject(AuthService);
  protected readonly label = orgTypeLabel;
}
