import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

export const API_BASE = '/api/v1';

export type QueryValue = string | number | boolean | null | undefined;
export type Query = Record<string, QueryValue>;

/** Centralised HTTP access: every feature API service goes through here (spec section 28). */
@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);

  get<T>(path: string, query?: Query): Observable<T> {
    return this.http.get<T>(this.url(path), { params: toParams(query) });
  }

  post<T>(path: string, body: unknown = {}): Observable<T> {
    return this.http.post<T>(this.url(path), body, { withCredentials: true });
  }

  patch<T>(path: string, body: unknown): Observable<T> {
    return this.http.patch<T>(this.url(path), body);
  }

  put<T>(path: string, body: unknown): Observable<T> {
    return this.http.put<T>(this.url(path), body);
  }

  delete<T>(path: string, query?: Query): Observable<T> {
    return this.http.delete<T>(this.url(path), { params: toParams(query) });
  }

  private url(path: string): string {
    return `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`;
  }
}

/** Drops empty values so the backend never receives `?status=` or `?search=null`. */
export function toParams(query?: Query): HttpParams {
  let params = new HttpParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value === null || value === undefined || value === '') continue;
    params = params.set(key, String(value));
  }
  return params;
}
