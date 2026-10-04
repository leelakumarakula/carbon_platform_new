import { Injectable, inject } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';

import { ApiError } from './api/api.models';

@Injectable({ providedIn: 'root' })
export class NotifyService {
  private readonly snack = inject(MatSnackBar);

  success(message: string): void {
    this.snack.open(message, 'OK', { duration: 3500, panelClass: 'snack-success' });
  }

  error(err: unknown, fallback = 'Something went wrong.'): void {
    const e = err instanceof ApiError ? err : ApiError.from(err);
    const ref = e.requestId ? ` (ref ${e.requestId.slice(0, 8)})` : '';
    const fields = fieldSummary(e);
    this.snack.open(`${e.message || fallback}${fields}${ref}`, 'Dismiss', { duration: fields ? 12000 : 7000, panelClass: 'snack-error' });
  }
}

/** " — Depth top cm: …; …" for a 422 with field errors, so the user can see which value the server refused (at most 3). */
export function fieldSummary(e: ApiError): string {
  const errs = e.fieldErrors.filter((f) => f.message);
  if (!errs.length) return '';
  const human = (f: string) => (f.split('.').pop() || f).replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());
  const parts = errs.slice(0, 3).map((f) => (f.field ? `${human(f.field)}: ${f.message}` : f.message));
  return ` — ${parts.join('; ')}${errs.length > 3 ? ` (+${errs.length - 3} more)` : ''}`;
}
