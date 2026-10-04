import { ChangeDetectionStrategy, Component, DestroyRef, effect, inject, input, signal } from '@angular/core';

/** Animated number: eases from the previous value to `value` (ease-out cubic). `null` shows an em dash. Honors reduced motion. */
@Component({
  selector: 'app-count-up',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `{{ shown() }}`,
})
export class CountUp {
  readonly value = input<number | null>(null);
  readonly duration = input(700);
  protected readonly shown = signal('—');
  private current = 0;
  private frame = 0;

  constructor() {
    inject(DestroyRef).onDestroy(() => cancelAnimationFrame(this.frame));
    effect(() => {
      const target = this.value();
      cancelAnimationFrame(this.frame);
      if (target === null || !Number.isFinite(target)) {
        this.shown.set('—');
        return;
      }
      const reduce = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
      if (reduce || typeof requestAnimationFrame !== 'function') {
        this.current = target;
        this.shown.set(target.toLocaleString());
        return;
      }
      const from = this.current, start = performance.now(), dur = this.duration();
      const step = (now: number) => {
        const t = Math.min(1, (now - start) / dur), eased = 1 - (1 - t) ** 3;
        this.current = Math.round(from + (target - from) * eased);
        this.shown.set(this.current.toLocaleString());
        if (t < 1) this.frame = requestAnimationFrame(step);
      };
      this.frame = requestAnimationFrame(step);
    });
  }
}
