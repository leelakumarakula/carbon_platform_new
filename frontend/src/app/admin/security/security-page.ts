import { DatePipe, JsonPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { MatPaginatorModule } from '@angular/material/paginator';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatTableModule } from '@angular/material/table';
import { MatTabsModule } from '@angular/material/tabs';
import { MatTooltipModule } from '@angular/material/tooltip';

import { AuthService } from '../../core/auth/auth.service';
import { P } from '../../core/auth/permissions';
import { NotifyService } from '../../core/notify.service';
import { PageHeader } from '../../shared/page-header';
import { PagedList } from '../../shared/paged-list';
import { askReason } from '../../shared/reason-dialog';
import { StateView } from '../../shared/state-view';
import { StatusBadge } from '../../shared/status-badge';
import { AuditApi } from '../admin.api';
import { LoginAudit, SecurityEvent, SessionInfo } from '../admin.models';

@Component({
  selector: 'app-security-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, JsonPipe, MatTabsModule, MatTableModule, MatPaginatorModule, MatButtonModule, MatIconModule, MatSlideToggleModule,
    MatTooltipModule, PageHeader, StateView, StatusBadge],
  templateUrl: './security-page.html',
  styles: `.toolbar { display: flex; align-items: center; gap: 16px; margin: 12px 0; } .details { font-size: 12px; max-width: 420px; white-space: pre-wrap; }`,
})
export class SecurityPage implements OnInit {
  private readonly api = inject(AuditApi);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotifyService);
  private readonly destroyRef = inject(DestroyRef);
  protected readonly canManage = inject(AuthService).has(P.SECURITY_MANAGE);

  protected readonly failedOnly = signal(false);
  protected readonly activeOnly = signal(true);

  protected readonly events = new PagedList<SecurityEvent>((q) => this.api.securityEvents(q), this.destroyRef, '-occurred_at');
  protected readonly logins = new PagedList<LoginAudit>(
    (q) => this.api.loginAudit({ ...q, success: this.failedOnly() ? false : null }), this.destroyRef, '-occurred_at');
  protected readonly sessions = new PagedList<SessionInfo>(
    (q) => this.api.sessions({ ...q, active_only: this.activeOnly() }), this.destroyRef, '-last_seen_at');

  protected readonly eventColumns = ['when', 'type', 'severity', 'details'];
  protected readonly loginColumns = ['when', 'email', 'result', 'ip'];
  protected readonly sessionColumns = ['user', 'created', 'last_seen', 'expires', 'state', 'actions'];

  ngOnInit(): void {
    this.events.load();
    this.logins.load();
    this.sessions.load();
  }

  setFailedOnly(v: boolean): void {
    this.failedOnly.set(v);
    this.logins.reset();
  }

  setActiveOnly(v: boolean): void {
    this.activeOnly.set(v);
    this.sessions.reset();
  }

  revoke(s: SessionInfo): void {
    askReason(this.dialog, { title: `Revoke session for ${s.user_email}?`, message: 'The device is signed out immediately.',
      confirmLabel: 'Revoke', danger: true }).subscribe((r) => {
      if (!r) return;
      this.api.revokeSession(s.id, r.reason).subscribe({
        next: () => {
          this.notify.success('Session revoked.');
          this.sessions.load();
        },
        error: (e: unknown) => this.notify.error(e),
      });
    });
  }
}
