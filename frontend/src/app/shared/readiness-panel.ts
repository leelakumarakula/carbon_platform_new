import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';

import { TransitionReadiness, label } from '../farmer/farmer.models';

/** "What is still needed before the next status" — mirrors the server's readiness checks. */
@Component({
  selector: 'app-readiness-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatIconModule],
  template: `
    @for (r of readiness(); track r.target) {
      @if (r.items.length) {
        <div class="target">
          <div class="head">To move to <strong>{{ label(r.target) }}</strong>
            @if (r.ready) { <span class="ok">— ready</span> } @else { <span class="todo">— not yet</span> }
          </div>
          <ul>
            @for (i of r.items; track i.key) {
              <li [class.done]="i.done">
                <mat-icon inline>{{ i.done ? 'check_circle' : (i.required ? 'radio_button_unchecked' : 'remove_circle_outline') }}</mat-icon>
                {{ i.label }} @if (!i.required) { <span class="opt">(recommended)</span> }
              </li>
            }
          </ul>
        </div>
      }
    }
  `,
  styles: `
    .target { margin-bottom: 12px; }
    .head { margin-bottom: 4px; }
    ul { list-style: none; padding: 0; margin: 0; }
    li { display: flex; align-items: center; gap: 6px; padding: 2px 0; color: var(--mat-sys-on-surface-variant); }
    li.done { color: #1b5e20; }
    .ok { color: #1b5e20; } .todo { color: #7a5200; } .opt { font-size: 12px; opacity: .8; }
  `,
})
export class ReadinessPanel {
  readonly readiness = input<TransitionReadiness[]>([]);
  protected readonly label = label;
}
