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
    this.snack.open(`${e.message || fallback}${ref}`, 'Dismiss', { duration: 7000, panelClass: 'snack-error' });
  }
}
