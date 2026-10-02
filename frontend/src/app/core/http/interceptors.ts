import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, switchMap, throwError } from 'rxjs';

import { API_BASE } from '../api/api.service';
import { ApiError, ApiErrorBody } from '../api/api.models';
import { AuthService } from '../auth/auth.service';

const AUTH_ENDPOINT = /\/auth\/(login|refresh|logout|token)$/;

/** Adds the bearer token; on a 401 refreshes once and retries the original request. */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  if (!req.url.startsWith(API_BASE)) return next(req);
  const auth = inject(AuthService);
  const isAuthCall = AUTH_ENDPOINT.test(req.url);
  const token = auth.accessToken();
  const withToken = token && !isAuthCall ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : req;

  return next(withToken).pipe(
    catchError((err: unknown) => {
      if (!(err instanceof HttpErrorResponse) || err.status !== 401 || isAuthCall || !token) {
        return throwError(() => err);
      }
      return auth.refresh().pipe(
        catchError((refreshErr: unknown) => {
          auth.sessionEnded();
          return throwError(() => refreshErr);
        }),
        switchMap((fresh) => next(req.clone({ setHeaders: { Authorization: `Bearer ${fresh}` } }))),
      );
    }),
  );
};

/** Converts every HTTP failure into an ApiError carrying the backend's error envelope. */
export const errorInterceptor: HttpInterceptorFn = (req, next) =>
  next(req).pipe(
    catchError((err: unknown) => {
      if (!(err instanceof HttpErrorResponse)) return throwError(() => ApiError.from(err));
      if (err.status === 0) {
        return throwError(() => new ApiError(0, 'NETWORK_ERROR', 'Cannot reach the server. Check your connection and try again.'));
      }
      const body = err.error as Partial<ApiErrorBody> | null;
      if (body && typeof body === 'object' && typeof body.error_code === 'string') {
        return throwError(
          () => new ApiError(err.status, body.error_code!, body.message ?? 'Request failed.', body.details ?? {}, body.request_id ?? null),
        );
      }
      const fallback = err.status >= 500 ? 'The server had a problem. Please try again.' : 'The request failed.';
      return throwError(() => new ApiError(err.status, 'HTTP_ERROR', fallback, {}, err.headers.get('X-Request-ID')));
    }),
  );
