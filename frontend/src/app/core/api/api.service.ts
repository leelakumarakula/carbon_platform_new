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

  /** `idempotencyKey` is sent as `Idempotency-Key` so a retried submission replays instead of acting twice. */
  post<T>(path: string, body: unknown = {}, idempotencyKey?: string): Observable<T> {
    const headers = idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : undefined;
    return this.http.post<T>(this.url(path), body, { withCredentials: true, headers });
  }

  patch<T>(path: string, body: unknown): Observable<T> {
    return this.http.patch<T>(this.url(path), body);
  }

  put<T>(path: string, body: unknown): Observable<T> {
    return this.http.put<T>(this.url(path), body);
  }

  /** multipart/form-data upload: one file plus simple text fields. */
  upload<T>(path: string, file: File, fields: Record<string, string>): Observable<T> {
    const form = new FormData();
    form.append('file', file, file.name);
    for (const [k, v] of Object.entries(fields)) form.append(k, v);
    return this.http.post<T>(this.url(path), form);
  }

  /** DELETE; `body` carries e.g. the reason for ending a record (the server keeps the record, see projects). */
  delete<T>(path: string, query?: Query, body?: unknown): Observable<T> {
    return this.http.delete<T>(this.url(path), { params: toParams(query), body });
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
