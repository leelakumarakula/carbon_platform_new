import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { authInterceptor, errorInterceptor } from '../http/interceptors';
import { makeMe } from '../../../testing/fixtures';
import { AuthService } from './auth.service';

describe('AuthService', () => {
  let auth: AuthService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideRouter([]), provideHttpClient(withInterceptors([errorInterceptor, authInterceptor])), provideHttpClientTesting()],
    });
    auth = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('login stores the access token in memory and loads the profile', async () => {
    const done = firstValueFrom(auth.login('a@test.example', 'pw'));
    const login = http.expectOne('/api/v1/auth/login');
    expect(login.request.withCredentials).toBe(true);
    login.flush({ access_token: 'tok-1', token_type: 'bearer', expires_in: 900, must_change_password: false });
    const me = http.expectOne('/api/v1/auth/me');
    expect(me.request.headers.get('Authorization')).toBe('Bearer tok-1');
    me.flush(makeMe(['users.read']));
    await done;
    expect(auth.isAuthenticated()).toBe(true);
    expect(auth.has('users.read')).toBe(true);
    expect(auth.has('users.manage')).toBe(false);
    expect(auth.accessToken()).toBe('tok-1');
  });

  it('concurrent refresh calls share one request', async () => {
    const a = firstValueFrom(auth.refresh());
    const b = firstValueFrom(auth.refresh());
    http.expectOne('/api/v1/auth/refresh').flush({ access_token: 'tok-2', token_type: 'bearer', expires_in: 900, must_change_password: false });
    expect(await a).toBe('tok-2');
    expect(await b).toBe('tok-2');
  });

  it('restoreSession leaves the user signed out when there is no refresh cookie', async () => {
    const p = auth.restoreSession();
    http.expectOne('/api/v1/auth/refresh').flush(
      { success: false, error_code: 'REFRESH_MISSING', message: 'No refresh token', details: {}, request_id: 'r' },
      { status: 401, statusText: 'Unauthorized' },
    );
    await p;
    expect(auth.isAuthenticated()).toBe(false);
    expect(auth.accessToken()).toBeNull();
  });

  it('logout clears state and returns to the login page', async () => {
    const router = TestBed.inject(Router);
    const nav = vi.spyOn(router, 'navigate').mockResolvedValue(true);
    const done = firstValueFrom(auth.login('a@test.example', 'pw'));
    http.expectOne('/api/v1/auth/login').flush({ access_token: 't', token_type: 'bearer', expires_in: 900, must_change_password: false });
    http.expectOne('/api/v1/auth/me').flush(makeMe());
    await done;
    auth.logout().subscribe();
    http.expectOne('/api/v1/auth/logout').flush({ success: true, message: 'Signed out.' });
    expect(auth.isAuthenticated()).toBe(false);
    expect(nav).toHaveBeenCalledWith(['/login']);
  });
});
