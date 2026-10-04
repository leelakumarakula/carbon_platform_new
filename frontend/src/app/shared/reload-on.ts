import { effect, untracked } from '@angular/core';

/**
 * Runs `fn` once and again whenever the signals read by `source` change. Routed detail pages pass their `id` input: the
 * router reuses the component when navigating between records of the same type, so loading once in ngOnInit would leave
 * the previous record on screen. Call from an injection context (constructor or field initializer).
 */
export function reloadOn(source: () => unknown, fn: () => void): void {
  effect(() => {
    source();
    untracked(fn);
  });
}
