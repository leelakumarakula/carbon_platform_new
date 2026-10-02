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
        <mat-icon>error_outline</mat-icon>
        <div>
          <strong>{{ e.message }}</strong>
          @if (e.requestId) { <div class="ref">Reference: {{ e.requestId }}</div> }
        </div>
        <button mat-stroked-button type="button" (click)="retry.emit()">Try again</button>
      </div>
    } @else if (empty()) {
      <div class="state empty">
        <mat-icon>inbox</mat-icon>
        <span>{{ emptyText() }}</span>
      </div>
    }
  `,
  styles: `
    .state { display: flex; align-items: center; gap: 12px; padding: 24px; border-radius: 8px; }
    .error { background: #fdecec; color: #8e1b1b; }
    .error button { margin-left: auto; }
    .empty { color: var(--mat-sys-on-surface-variant); justify-content: center; }
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
