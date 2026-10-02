import { WritableSignal } from '@angular/core';
import { Observable } from 'rxjs';

import { NotifyService } from '../core/notify.service';

/** Run one API mutation with a busy flag, success toast and error toast. */
export function runAction<T>(obs: Observable<T>, busy: WritableSignal<boolean>, notify: NotifyService, success: string,
                             done: (value: T) => void): void {
  busy.set(true);
  obs.subscribe({
    next: (v) => {
      busy.set(false);
      notify.success(success);
      done(v);
    },
    error: (e: unknown) => {
      busy.set(false);
      notify.error(e);
    },
  });
}
