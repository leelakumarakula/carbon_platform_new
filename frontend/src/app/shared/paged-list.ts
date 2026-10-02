import { DestroyRef, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { PageEvent } from '@angular/material/paginator';
import { Sort } from '@angular/material/sort';
import { Observable, Subject, catchError, finalize, of, switchMap, tap } from 'rxjs';

import { ApiError, Page, PageQuery } from '../core/api/api.models';

/**
 * Server-side pagination + sorting state for a list page (spec section 38).
 * Overlapping requests are cancelled (switchMap) so results never arrive out of order.
 */
export class PagedList<T> {
  readonly items = signal<T[]>([]);
  readonly total = signal(0);
  readonly loading = signal(false);
  readonly error = signal<ApiError | null>(null);
  readonly page = signal(1);
  readonly pageSize = signal(25);
  readonly sort = signal<string | null>(null);

  private readonly trigger = new Subject<void>();

  constructor(fetch: (q: PageQuery) => Observable<Page<T>>, destroyRef: DestroyRef, defaultSort: string | null = null) {
    this.sort.set(defaultSort);
    this.trigger
      .pipe(
        tap(() => {
          this.loading.set(true);
          this.error.set(null);
        }),
        switchMap(() =>
          fetch({ page: this.page(), page_size: this.pageSize(), sort: this.sort() }).pipe(
            catchError((e: unknown) => {
              this.error.set(ApiError.from(e));
              return of(null);
            }),
            finalize(() => this.loading.set(false)),
          ),
        ),
        takeUntilDestroyed(destroyRef),
      )
      .subscribe((res) => {
        this.loading.set(false);
        if (!res) return;
        this.items.set(res.items);
        this.total.set(res.total);
      });
  }

  load(): void {
    this.trigger.next();
  }

  /** Filters changed: go back to page 1. */
  reset(): void {
    this.page.set(1);
    this.load();
  }

  onPage(e: PageEvent): void {
    this.page.set(e.pageIndex + 1);
    this.pageSize.set(e.pageSize);
    this.load();
  }

  onSort(s: Sort): void {
    this.sort.set(s.direction ? `${s.direction === 'desc' ? '-' : ''}${s.active}` : null);
    this.reset();
  }
}
