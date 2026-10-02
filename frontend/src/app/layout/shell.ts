import { BreakpointObserver } from '@angular/cdk/layout';
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatDividerModule } from '@angular/material/divider';
import { MatIconModule } from '@angular/material/icon';
import { MatListModule } from '@angular/material/list';
import { MatMenuModule } from '@angular/material/menu';
import { MatSidenavModule } from '@angular/material/sidenav';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatTooltipModule } from '@angular/material/tooltip';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { map } from 'rxjs';

import { AuthService } from '../core/auth/auth.service';
import { NAVIGATION, visibleNavigation } from '../core/navigation/nav.config';

@Component({
  selector: 'app-shell',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, MatSidenavModule, MatToolbarModule, MatListModule, MatIconModule,
    MatButtonModule, MatMenuModule, MatDividerModule, MatTooltipModule],
  templateUrl: './shell.html',
  styleUrl: './shell.scss',
})
export class Shell {
  protected readonly auth = inject(AuthService);
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
  protected readonly roleSummary = computed(() =>
    Array.from(new Set((this.auth.user()?.roles ?? []).map((r) => r.role_name))).join(', ') || 'No roles assigned',
  );

  signOut(): void {
    this.auth.logout().subscribe();
  }
}
