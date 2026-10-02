import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { RouterLink } from '@angular/router';
import { catchError, forkJoin, map, of } from 'rxjs';

import { AuditApi, OrganizationsApi, UsersApi } from '../admin/admin.api';
import { AuditLog } from '../admin/admin.models';
import { AuthService } from '../core/auth/auth.service';
import { P } from '../core/auth/permissions';
import { NAVIGATION, visibleNavigation } from '../core/navigation/nav.config';
import { PageHeader } from '../shared/page-header';
import { StatusBadge } from '../shared/status-badge';

interface Kpi {
  label: string;
  value: number | null;
  icon: string;
  link: string;
}

@Component({
  selector: 'app-dashboard-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatCardModule, MatIconModule, RouterLink, DatePipe, PageHeader, StatusBadge],
  templateUrl: './dashboard-page.html',
  styles: `
    .kpis { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
    .kpi { display: flex; align-items: center; gap: 14px; padding: 18px; text-decoration: none; color: inherit;
      border: 1px solid var(--mat-sys-outline-variant); border-radius: 12px; background: var(--mat-sys-surface); }
    .kpi:hover { border-color: var(--mat-sys-primary); }
    .kpi mat-icon { color: var(--mat-sys-primary); }
    .kpi .value { font: var(--mat-sys-headline-medium); }
    .kpi .label { color: var(--mat-sys-on-surface-variant); }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }
    .grants { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 8px; }
    .grants li { display: flex; justify-content: space-between; gap: 8px; }
    .muted { color: var(--mat-sys-on-surface-variant); }
    .activity { list-style: none; padding: 0; margin: 0; }
    .activity li { padding: 8px 0; border-bottom: 1px solid var(--mat-sys-outline-variant); }
    .activity small { color: var(--mat-sys-on-surface-variant); }
    .links { display: flex; flex-wrap: wrap; gap: 8px; }
    .links a { display: inline-flex; gap: 6px; align-items: center; padding: 6px 12px; border-radius: 8px;
      border: 1px solid var(--mat-sys-outline-variant); text-decoration: none; color: inherit; }
  `,
})
export class DashboardPage implements OnInit {
  protected readonly auth = inject(AuthService);
  private readonly users = inject(UsersApi);
  private readonly orgs = inject(OrganizationsApi);
  private readonly audit = inject(AuditApi);

  protected readonly kpis = signal<Kpi[]>([]);
  protected readonly recent = signal<AuditLog[] | null>(null);
  protected readonly shortcuts = computed(() =>
    visibleNavigation(NAVIGATION, (c) => this.auth.has(c)).flatMap((s) => s.items).filter((i) => i.route !== '/dashboard'),
  );

  ngOnInit(): void {
    const count = <T>(obs: import('rxjs').Observable<{ total: number } & T>) => obs.pipe(map((r) => r.total), catchError(() => of(null)));
    const wanted: Record<string, import('rxjs').Observable<number | null>> = {};
    if (this.auth.has(P.USERS_READ)) {
      wanted['users'] = count(this.users.list({ page_size: 1 }));
      wanted['active'] = count(this.users.list({ page_size: 1, status: 'ACTIVE' }));
    }
    if (this.auth.has(P.ORGANIZATIONS_READ)) wanted['orgs'] = count(this.orgs.list({ page_size: 1 }));
    if (Object.keys(wanted).length) {
      forkJoin(wanted).subscribe((r) => {
        const k: Kpi[] = [];
        if ('users' in r) k.push({ label: 'Users', value: r['users'], icon: 'group', link: '/admin/users' });
        if ('active' in r) k.push({ label: 'Active users', value: r['active'], icon: 'how_to_reg', link: '/admin/users' });
        if ('orgs' in r) k.push({ label: 'Organizations', value: r['orgs'], icon: 'domain', link: '/admin/organizations' });
        this.kpis.set(k);
      });
    }
    if (this.auth.has(P.AUDIT_READ)) {
      this.audit.auditLogs({ page_size: 6 }).subscribe({ next: (p) => this.recent.set(p.items), error: () => this.recent.set([]) });
    }
  }
}
