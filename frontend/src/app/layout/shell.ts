import { BreakpointObserver } from '@angular/cdk/layout';
import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { MatBadgeModule } from '@angular/material/badge';
import { MatButtonModule } from '@angular/material/button';
import { MatDividerModule } from '@angular/material/divider';
import { MatIconModule } from '@angular/material/icon';
import { MatListModule } from '@angular/material/list';
import { MatMenuModule } from '@angular/material/menu';
import { MatSidenavModule } from '@angular/material/sidenav';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatTooltipModule } from '@angular/material/tooltip';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { catchError, map, of, startWith, switchMap, timer } from 'rxjs';

import { AuthService } from '../core/auth/auth.service';
import { NAVIGATION, visibleNavigation } from '../core/navigation/nav.config';
import { AppNotification, NotificationsApi } from '../core/notifications/notifications.api';

@Component({
  selector: 'app-shell',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, MatSidenavModule, MatToolbarModule, MatListModule, MatIconModule,
    MatButtonModule, MatMenuModule, MatDividerModule, MatTooltipModule, MatBadgeModule, DatePipe],
  templateUrl: './shell.html',
  styleUrl: './shell.scss',
})
export class Shell implements OnInit {
  protected readonly auth = inject(AuthService);
  private readonly notificationsApi = inject(NotificationsApi);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);
  protected readonly unread = signal(0);
  protected readonly notifications = signal<AppNotification[]>([]);
  protected readonly isHandset = toSignal(
    inject(BreakpointObserver).observe('(max-width: 900px)').pipe(map((r) => r.matches)),
    { initialValue: false },
  );
  protected readonly nav = computed(() => {
    const perms = this.auth.permissions();
    return visibleNavigation(NAVIGATION, (c) => perms.has(c));
  });
  protected readonly initials = computed(() =>
    (this.auth.user()?.full_name ?? '?').split(/\s+/).map((p) => p[0]).slice(0, 2).join('').toUpperCase(),
  );
  /** First role, shown under the name in the top bar (the menu lists all of them). */
  protected readonly primaryRole = computed(() => this.auth.user()?.roles?.[0]?.role_name ?? 'No role');
  protected readonly roleSummary = computed(() =>
    Array.from(new Set((this.auth.user()?.roles ?? []).map((r) => r.role_name))).join(', ') || 'No roles assigned',
  );

  ngOnInit(): void {
    // Poll the unread count once a minute; failures are silent (the bell simply stays as it was).
    timer(0, 60_000).pipe(
      switchMap(() => this.notificationsApi.unreadCount().pipe(catchError(() => of(null)))),
      takeUntilDestroyed(this.destroyRef),
    ).subscribe((r) => r && this.unread.set(r.unread));
  }

  openNotifications(): void {
    this.notificationsApi.list().pipe(startWith(null)).subscribe((p) => p && this.notifications.set(p.items));
  }

  openNotification(n: AppNotification): void {
    if (!n.read_at) this.notificationsApi.markRead(n.id).subscribe(() => this.unread.update((u) => Math.max(0, u - 1)));
    if (n.link) void this.router.navigateByUrl(n.link);
  }

  markAllRead(): void {
    this.notificationsApi.markAll().subscribe(() => {
      this.unread.set(0);
      this.notifications.update((list) => list.map((n) => ({ ...n, read_at: n.read_at ?? new Date().toISOString() })));
    });
  }

  signOut(): void {
    this.auth.logout().subscribe();
  }
}
