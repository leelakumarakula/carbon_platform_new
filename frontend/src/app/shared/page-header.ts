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
        <span class="rule" aria-hidden="true"></span>
        @if (subtitle()) { <p class="subtitle">{{ subtitle() }}</p> }
      </div>
      <div class="actions"><ng-content /></div>
    </header>
  `,
  styles: `
    .page-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; flex-wrap: wrap; margin-bottom: 24px; }
    .titles { min-width: 0; }
    h1 { margin: 0; font: 600 clamp(22px, 2.2vw, 28px)/1.25 var(--cp-font); color: var(--cp-navy); letter-spacing: -.015em; }
    .rule { display: block; width: 32px; height: 3px; border-radius: 3px; background: var(--cp-lime); margin: 10px 0 0; }
    .subtitle { margin: 10px 0 0; font: italic 400 15.5px/1.45 var(--cp-serif); color: var(--cp-maroon); max-width: 760px; }
    .back { display: inline-flex; align-items: center; gap: 4px; color: var(--cp-forest-3); text-decoration: none; font-size: 13px; font-weight: 500;
      margin-bottom: 10px; }
    .back:hover { color: var(--cp-forest); text-decoration: underline; }
    .actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
  `,
})
export class PageHeader {
  readonly title = input.required<string>();
  readonly subtitle = input<string | null>(null);
  readonly backLink = input<string | null>(null);
  readonly backLabel = input('Back');
}
