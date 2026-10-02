import { ChangeDetectionStrategy, Component } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-forbidden-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, MatButtonModule, MatIconModule],
  template: `
    <section class="centered">
      <mat-icon class="big">lock</mat-icon>
      <h1>You don't have access to this page</h1>
      <p>Your roles do not include the permission it needs. Ask a Platform Admin if you think this is wrong.</p>
      <a mat-flat-button routerLink="/dashboard">Back to dashboard</a>
    </section>
  `,
})
export class ForbiddenPage {}

@Component({
  selector: 'app-not-found-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, MatButtonModule, MatIconModule],
  template: `
    <section class="centered">
      <mat-icon class="big">search_off</mat-icon>
      <h1>Page not found</h1>
      <p>The address may be mistyped, or the record no longer exists.</p>
      <a mat-flat-button routerLink="/dashboard">Back to dashboard</a>
    </section>
  `,
})
export class NotFoundPage {}
