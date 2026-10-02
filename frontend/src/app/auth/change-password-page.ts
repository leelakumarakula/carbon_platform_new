import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { Router } from '@angular/router';

import { ApiError } from '../core/api/api.models';
import { AuthService } from '../core/auth/auth.service';
import { NotifyService } from '../core/notify.service';
import { matchValidator, passwordPolicyValidator } from '../shared/forms';

@Component({
  selector: 'app-change-password-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, MatCardModule, MatFormFieldModule, MatInputModule, MatButtonModule, MatProgressBarModule],
  template: `
    <main class="auth-screen">
      <mat-card class="auth-card" appearance="outlined">
        @if (submitting()) { <mat-progress-bar mode="indeterminate" /> }
        <mat-card-content>
          <h1>Change your password</h1>
          @if (auth.mustChangePassword()) {
            <p class="notice">You signed in with a temporary password. Choose a new one to continue.</p>
          }
          <form [formGroup]="form" (ngSubmit)="submit()" novalidate>
            <mat-form-field appearance="outline" class="full">
              <mat-label>Current password</mat-label>
              <input matInput type="password" formControlName="current" autocomplete="current-password" />
            </mat-form-field>
            <mat-form-field appearance="outline" class="full">
              <mat-label>New password</mat-label>
              <input matInput type="password" formControlName="next" autocomplete="new-password" />
              <mat-hint>At least 12 characters, with letters and digits.</mat-hint>
              @if (form.controls.next.hasError('policy')) { <mat-error>{{ form.controls.next.getError('policy') }}</mat-error> }
            </mat-form-field>
            <mat-form-field appearance="outline" class="full">
              <mat-label>Confirm new password</mat-label>
              <input matInput type="password" formControlName="confirm" autocomplete="new-password" />
            </mat-form-field>
            @if (form.hasError('mismatch') && form.controls.confirm.touched) { <p class="form-error">The passwords do not match.</p> }
            @if (error(); as e) { <p class="form-error" role="alert">{{ e }}</p> }
            <div class="row-actions">
              @if (!auth.mustChangePassword()) { <button mat-button type="button" (click)="cancel()">Cancel</button> }
              <button mat-button type="button" (click)="signOut()">Sign out</button>
              <button mat-flat-button type="submit" [disabled]="submitting()">Change password</button>
            </div>
          </form>
        </mat-card-content>
      </mat-card>
    </main>
  `,
})
export class ChangePasswordPage {
  protected readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly notify = inject(NotifyService);

  protected readonly submitting = signal(false);
  protected readonly error = signal<string | null>(null);

  protected readonly form = new FormGroup(
    {
      current: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
      next: new FormControl('', { nonNullable: true, validators: [Validators.required, passwordPolicyValidator] }),
      confirm: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    },
    { validators: matchValidator('next', 'confirm') },
  );

  submit(): void {
    this.form.markAllAsTouched();
    if (this.form.invalid || this.submitting()) return;
    this.submitting.set(true);
    this.error.set(null);
    const { current, next } = this.form.getRawValue();
    this.auth.changePassword(current, next).subscribe({
      next: () => {
        this.submitting.set(false);
        this.notify.success('Password changed. Other sessions were signed out.');
        void this.router.navigateByUrl('/dashboard');
      },
      error: (e: unknown) => {
        this.submitting.set(false);
        this.error.set(ApiError.from(e).message);
      },
    });
  }

  cancel(): void {
    void this.router.navigateByUrl('/profile');
  }

  signOut(): void {
    this.auth.logout().subscribe();
  }
}
