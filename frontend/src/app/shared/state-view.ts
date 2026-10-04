import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';

import { ApiError } from '../core/api/api.models';

/** Loading / error / empty states, so every page handles them the same way (spec section 28). */
@Component({
  selector: 'app-state-view',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatProgressBarModule, MatIconModule, MatButtonModule],
  template: `
    @if (loading()) {
      <mat-progress-bar mode="indeterminate" aria-label="Loading" />
    } @else if (error(); as e) {
      <div class="state error" role="alert">
        <span class="ico"><mat-icon>error_outline</mat-icon></span>
        <div>
          <strong>{{ e.message }}</strong>
          @if (e.requestId) { <div class="ref">Reference: {{ e.requestId }}</div> }
        </div>
        <button mat-stroked-button type="button" (click)="retry.emit()">Try again</button>
      </div>
    } @else if (empty()) {
      <div class="state empty">
        <svg width="96" height="64" viewBox="0 0 96 64" aria-hidden="true">
          <ellipse cx="48" cy="56" rx="40" ry="6" fill="#dcebd5" />
          <path d="M48 52c0-14 6-24 20-28-2 15-9 23-20 28z" fill="#afc55b" />
          <path d="M48 52c0-11-5-19-16-22 2 11 7 18 16 22z" fill="#5f9442" />
          <path d="M48 52V34" stroke="#3f7a3a" stroke-width="2.5" stroke-linecap="round" />
        </svg>
        <span>{{ emptyText() }}</span>
      </div>
    }
  `,
  styles: `
    .state { display: flex; align-items: center; gap: 14px; padding: 22px 24px; border-radius: var(--cp-radius); }
    .error { background: #fdf0ee; color: #7c1d1d; border: 1px solid #f2cdc8; }
    .error .ico { display: grid; place-items: center; width: 40px; height: 40px; border-radius: 50%; background: #f9d9d4; flex: none; }
    .error button { margin-left: auto; }
    .empty { flex-direction: column; justify-content: center; color: var(--cp-ink-2); padding: 36px 24px; text-align: center;
      font: italic 15px var(--cp-serif); background: var(--cp-card); border: 1px solid var(--cp-line); }
    .ref { font-size: 12px; opacity: .8; margin-top: 2px; }
  `,
})
export class StateView {
  readonly loading = input(false);
  readonly error = input<ApiError | null>(null);
  readonly empty = input(false);
  readonly emptyText = input('Nothing to show yet.');
  readonly retry = output<void>();
}
