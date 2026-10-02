import { inject } from '@angular/core';
import { CanActivateChildFn, CanActivateFn, Router } from '@angular/router';

import { AuthService } from './auth.service';

/** Signed-in users only; remembers where the user was going. */
export const authGuard: CanActivateFn = (_route, state) => {
  const auth = inject(AuthService);
  return auth.isAuthenticated() ? true : inject(Router).createUrlTree(['/login'], { queryParams: { returnUrl: state.url } });
};

/** Keep signed-in users away from the login page. */
export const guestGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  return auth.isAuthenticated() ? inject(Router).createUrlTree(['/']) : true;
};

/** A temporary password must be replaced before anything else (mirrors the API rule). */
export const passwordChangedGuard: CanActivateChildFn = () => {
  const auth = inject(AuthService);
  return auth.mustChangePassword() ? inject(Router).createUrlTree(['/change-password']) : true;
};

/** Route `data: { permissions: [...] }` — every listed permission is required. */
export const permissionGuard: CanActivateFn = (route) => {
  const required = (route.data['permissions'] as string[] | undefined) ?? [];
  const auth = inject(AuthService);
  return auth.hasAll(required) ? true : inject(Router).createUrlTree(['/forbidden']);
};
