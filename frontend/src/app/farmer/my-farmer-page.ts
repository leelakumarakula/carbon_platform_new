import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { Router } from '@angular/router';

import { ApiError } from '../core/api/api.models';
import { StateView } from '../shared/state-view';
import { FarmersApi } from './farmers.api';

/** Farmer self-service entry point: resolves the signed-in user's farmer record and opens it. */
@Component({
  selector: 'app-my-farmer-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [StateView],
  template: `<app-state-view [loading]="!error()" [error]="error()" (retry)="ngOnInit()" />`,
})
export class MyFarmerPage implements OnInit {
  private readonly api = inject(FarmersApi);
  private readonly router = inject(Router);
  protected readonly error = signal<ApiError | null>(null);

  ngOnInit(): void {
    this.error.set(null);
    this.api.me().subscribe({
      next: (f) => void this.router.navigate(['/farmers', f.id], { replaceUrl: true }),
      error: (e: unknown) => this.error.set(ApiError.from(e)),
    });
  }
}
