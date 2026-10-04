import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import { label as humanize } from '../farmer/farmer.models';

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
    .badge { display: inline-flex; align-items: center; gap: 6px; padding: 2px 10px 2px 8px; border-radius: 999px; font: 500 12px/20px var(--cp-font);
      letter-spacing: .01em; white-space: nowrap; border: 1px solid transparent; }
    .badge::before { content: ''; width: 6px; height: 6px; border-radius: 50%; background: currentColor; opacity: .85; }
    .badge-ok { background: #e6f3dc; color: #2f5f12; border-color: #c7e2ad; }
    .badge-warn { background: #fff5d9; color: #7a5200; border-color: #f0dc9a; }
    .badge-bad { background: #fcecea; color: #a1241c; border-color: #f2c4bf; }
    .badge-muted { background: #eef2ee; color: #4b5e54; border-color: #d6e0d7; }
    .badge-info { background: #e5f0f6; color: #0d4a6e; border-color: #c2dbe9; }
    .badge-demo { background: #f4eaf7; color: #6a1b9a; border-color: #e0c8ec; }
  `,
})
export class StatusBadge {
  readonly status = input.required<string>();
  readonly text = input<string | null>(null);
  protected readonly tone = computed(() => TONES[this.status()] ?? 'muted');
  protected readonly label = computed(() => this.text() ?? humanize(this.status()));
}
