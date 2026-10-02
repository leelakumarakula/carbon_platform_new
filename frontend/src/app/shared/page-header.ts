import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-page-header',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, MatIconModule],
  template: `
    <header class="page-header">
      <div class="titles">
        @if (backLink()) {
          <a class="back" [routerLink]="backLink()"><mat-icon inline>arrow_back</mat-icon> {{ backLabel() }}</a>
        }
        <h1>{{ title() }}</h1>
        @if (subtitle()) { <p class="subtitle">{{ subtitle() }}</p> }
      </div>
      <div class="actions"><ng-content /></div>
    </header>
  `,
  styles: `
    .page-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; flex-wrap: wrap; margin-bottom: 20px; }
    h1 { margin: 0; font: var(--mat-sys-headline-small); }
    .subtitle { margin: 4px 0 0; color: var(--mat-sys-on-surface-variant); }
    .back { display: inline-flex; align-items: center; gap: 4px; color: var(--mat-sys-primary); text-decoration: none; font-size: 13px; margin-bottom: 6px; }
    .actions { display: flex; gap: 8px; flex-wrap: wrap; }
  `,
})
export class PageHeader {
  readonly title = input.required<string>();
  readonly subtitle = input<string | null>(null);
  readonly backLink = input<string | null>(null);
  readonly backLabel = input('Back');
}
