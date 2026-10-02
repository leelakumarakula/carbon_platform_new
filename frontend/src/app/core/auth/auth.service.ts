import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, finalize, firstValueFrom, map, of, shareReplay, switchMap, tap } from 'rxjs';

import { API_BASE } from '../api/api.service';
import { Me, TokenResponse } from './auth.models';

/**
 * Session state. The access token lives only in memory; the refresh token is an httpOnly
 * cookie set by the API (never readable from JavaScript), so a page reload restores the
 * session through a silent refresh.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);

  private readonly token = signal<string | null>(null);
  private refreshInFlight: Observable<string> | null = null;

  readonly me = signal<Me | null>(null);
  readonly isAuthenticated = computed(() => this.me() !== null);
  readonly user = computed(() => this.me()?.user ?? null);
  readonly permissions = computed(() => new Set(this.me()?.permissions ?? []));
  readonly mustChangePassword = computed(() => this.me()?.user.must_change_password ?? false);
  readonly isDemo = computed(() => this.me()?.user.environment === 'DEMO');

  accessToken(): string | null {
    return this.token();
  }

  has(permission: string): boolean {
    return this.permissions().has(permission);
  }

  hasAll(permissions: readonly string[]): boolean {
    return permissions.every((p) => this.has(p));
  }

  login(email: string, password: string): Observable<Me> {
    return this.http
      .post<TokenResponse>(`${API_BASE}/auth/login`, { email, password }, { withCredentials: true })
      .pipe(
        tap((t) => this.token.set(t.access_token)),
        switchMap(() => this.loadMe()),
      );
  }

  /** Rotates the refresh cookie. Concurrent callers share one request. */
  refresh(): Observable<string> {
    if (!this.refreshInFlight) {
      this.refreshInFlight = this.http
        .post<TokenResponse>(`${API_BASE}/auth/refresh`, {}, { withCredentials: true })
        .pipe(
          map((t) => t.access_token),
          tap((t) => this.token.set(t)),
          finalize(() => (this.refreshInFlight = null)),
          shareReplay({ bufferSize: 1, refCount: false }),
        );
    }
    return this.refreshInFlight;
  }

  loadMe(): Observable<Me> {
    return this.http.get<Me>(`${API_BASE}/auth/me`).pipe(tap((me) => this.me.set(me)));
  }

  /** Called once at start-up: restore the session from the refresh cookie if there is one. */
  async restoreSession(): Promise<void> {
    try {
      await firstValueFrom(this.refresh().pipe(switchMap(() => this.loadMe())));
    } catch {
      this.clear();
    }
  }

  changePassword(currentPassword: string, newPassword: string): Observable<Me> {
    return this.http
      .post(`${API_BASE}/auth/change-password`, { current_password: currentPassword, new_password: newPassword })
      .pipe(switchMap(() => this.loadMe()));
  }

  logout(): Observable<void> {
    const call = this.token()
      ? this.http.post(`${API_BASE}/auth/logout`, {}, { withCredentials: true }).pipe(map(() => undefined))
      : of(undefined);
    return call.pipe(
      finalize(() => {
        this.clear();
        void this.router.navigate(['/login']);
      }),
    );
  }

  /** The API rejected our session (revoked, expired, deactivated): drop local state and go to sign-in. */
  sessionEnded(): void {
    const returnUrl = this.router.url.startsWith('/login') ? undefined : this.router.url;
    this.clear();
    void this.router.navigate(['/login'], { queryParams: returnUrl ? { returnUrl, reason: 'expired' } : {} });
  }

  private clear(): void {
    this.token.set(null);
    this.me.set(null);
  }
}
