import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router, convertToParamMap, provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';

import { ApiError } from '../core/api/api.models';
import { makeMe } from '../../testing/fixtures';
import { AuthService } from '../core/auth/auth.service';
import { LoginPage } from './login-page';

describe('LoginPage', () => {
  const login = vi.fn();

  function setup(query: Record<string, string> = {}) {
    login.mockReset();
    TestBed.configureTestingModule({
      imports: [LoginPage],
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: { login } },
        { provide: ActivatedRoute, useValue: { snapshot: { queryParamMap: convertToParamMap(query) } } },
      ],
    });
    const router = TestBed.inject(Router);
    const nav = vi.spyOn(router, 'navigateByUrl').mockResolvedValue(true);
    const fixture = TestBed.createComponent(LoginPage);
    return { fixture, page: fixture.componentInstance, nav };
  }

  function fill(page: LoginPage, email: string, password: string) {
    const form = (page as unknown as { form: { setValue(v: object): void } }).form;
    form.setValue({ email, password });
  }

  it('does not submit an invalid form', () => {
    const { page } = setup();
    fill(page, 'not-an-email', '');
    page.submit();
    expect(login).not.toHaveBeenCalled();
  });

  it('goes to the safe return URL after sign-in', () => {
    const { page, nav } = setup({ returnUrl: '/admin/users' });
    login.mockReturnValue(of(makeMe()));
    fill(page, ' ada@test.example ', 'pw');
    page.submit();
    expect(login).toHaveBeenCalledWith('ada@test.example', 'pw');
    expect(nav).toHaveBeenCalledWith('/admin/users');
  });

  it('ignores absolute return URLs (open-redirect protection)', () => {
    const { page, nav } = setup({ returnUrl: '//evil.example/steal' });
    login.mockReturnValue(of(makeMe()));
    fill(page, 'ada@test.example', 'pw');
    page.submit();
    expect(nav).toHaveBeenCalledWith('/dashboard');
  });

  it('sends users with a temporary password to change it', () => {
    const { page, nav } = setup();
    login.mockReturnValue(of(makeMe([], { must_change_password: true })));
    fill(page, 'ada@test.example', 'pw');
    page.submit();
    expect(nav).toHaveBeenCalledWith('/change-password');
  });

  it('shows the server message and clears the password on failure', async () => {
    const { fixture, page } = setup();
    login.mockReturnValue(throwError(() => new ApiError(401, 'INVALID_CREDENTIALS', 'Invalid email or password.')));
    fill(page, 'ada@test.example', 'wrong');
    page.submit();
    await fixture.whenStable();
    expect((fixture.nativeElement as HTMLElement).querySelector('.form-error')?.textContent).toContain('Invalid email or password.');
    expect((page as unknown as { form: { value: { password: string } } }).form.value.password).toBe('');
  });
});
