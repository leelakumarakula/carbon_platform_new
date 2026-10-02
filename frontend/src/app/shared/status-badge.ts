import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

const TONES: Record<string, string> = {
  ACTIVE: 'ok',
  SUCCESS: 'ok',
  INFO: 'info',
  SUSPENDED: 'warn',
  WARNING: 'warn',
  LOCKED: 'bad',
  FAILED: 'bad',
  CRITICAL: 'bad',
  DEACTIVATED: 'muted',
  ARCHIVED: 'muted',
  REVOKED: 'muted',
  DEMO: 'demo',
  PLATFORM: 'info',
  ORGANIZATION: 'muted',
};

/** Consistent status pill used for every workflow status in the app. */
@Component({
  selector: 'app-status-badge',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<span class="badge" [class]="'badge badge-' + tone()">{{ label() }}</span>`,
  styles: `
    .badge { display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 12px; font-weight: 500;
      letter-spacing: .02em; line-height: 20px; white-space: nowrap; border: 1px solid transparent; }
    .badge-ok { background: #e3f4e4; color: #1b5e20; border-color: #b9dfbb; }
    .badge-warn { background: #fff4d6; color: #7a5200; border-color: #f1d98e; }
    .badge-bad { background: #fdecec; color: #b71c1c; border-color: #f3c0c0; }
    .badge-muted { background: #eef1f3; color: #49545c; border-color: #d7dde1; }
    .badge-info { background: #e8f0fb; color: #0d47a1; border-color: #c4d7f2; }
    .badge-demo { background: #f3e8f8; color: #6a1b9a; border-color: #ddc3ea; }
  `,
})
export class StatusBadge {
  readonly status = input.required<string>();
  readonly text = input<string | null>(null);
  protected readonly tone = computed(() => TONES[this.status()] ?? 'muted');
  protected readonly label = computed(() => this.text() ?? this.status().replace(/_/g, ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase()));
}
