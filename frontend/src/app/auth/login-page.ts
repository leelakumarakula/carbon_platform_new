import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { ActivatedRoute, Router } from '@angular/router';

import { ApiError } from '../core/api/api.models';
import { AuthService } from '../core/auth/auth.service';

@Component({
  selector: 'app-login-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, MatCardModule, MatFormFieldModule, MatInputModule, MatButtonModule, MatIconModule, MatProgressBarModule],
  template: `
    <main class="auth-screen">
      <mat-card class="auth-card" appearance="outlined">
        @if (submitting()) { <mat-progress-bar mode="indeterminate" /> }
        <mat-card-content>
          <div class="brand"><mat-icon>eco</mat-icon><span>Carbon Platform</span></div>
          <h1>Sign in</h1>
          @if (expired) { <p class="notice">Your session ended. Please sign in again.</p> }
          <form [formGroup]="form" (ngSubmit)="submit()" novalidate>
            <mat-form-field appearance="outline" class="full">
              <mat-label>Email</mat-label>
              <input matInput type="email" formControlName="email" autocomplete="username" (blur)="trimEmail()" />
              @if (form.controls.email.touched && form.controls.email.invalid) { <mat-error>Enter a valid email address.</mat-error> }
            </mat-form-field>
            <mat-form-field appearance="outline" class="full">
              <mat-label>Password</mat-label>
              <input matInput [type]="showPassword() ? 'text' : 'password'" formControlName="password" autocomplete="current-password" />
              <button mat-icon-button matSuffix type="button" (click)="showPassword.set(!showPassword())"
                      [attr.aria-label]="showPassword() ? 'Hide password' : 'Show password'">
                <mat-icon>{{ showPassword() ? 'visibility_off' : 'visibility' }}</mat-icon>
              </button>
              @if (form.controls.password.touched && form.controls.password.invalid) { <mat-error>Enter your password.</mat-error> }
            </mat-form-field>
            @if (error(); as e) { <p class="form-error" role="alert">{{ e }}</p> }
            <button mat-flat-button class="full" type="submit" [disabled]="submitting()">Sign in</button>
          </form>
        </mat-card-content>
      </mat-card>
    </main>
  `,
})
export class LoginPage {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  protected readonly submitting = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly showPassword = signal(false);
  protected readonly expired = this.route.snapshot.queryParamMap.get('reason') === 'expired';

  protected readonly form = new FormGroup({
    email: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.email] }),
    password: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
  });

  /** Pasted addresses often carry spaces; Validators.email would reject them. */
  trimEmail(): void {
    const c = this.form.controls.email;
    if (c.value !== c.value.trim()) c.setValue(c.value.trim());
  }

  submit(): void {
    this.trimEmail();
    this.form.markAllAsTouched();
    if (this.form.invalid || this.submitting()) return;
    this.submitting.set(true);
    this.error.set(null);
    const { email, password } = this.form.getRawValue();
    this.auth.login(email.trim(), password).subscribe({
      next: (me) => {
        this.submitting.set(false);
        const target = me.user.must_change_password ? '/change-password' : this.safeReturnUrl();
        void this.router.navigateByUrl(target);
      },
      error: (e: unknown) => {
        this.submitting.set(false);
        this.error.set(ApiError.from(e).message);
        this.form.controls.password.reset();
      },
    });
  }

  /** Only allow in-app paths, never an absolute URL (open-redirect protection). */
  private safeReturnUrl(): string {
    const url = this.route.snapshot.queryParamMap.get('returnUrl') ?? '/dashboard';
    return url.startsWith('/') && !url.startsWith('//') ? url : '/dashboard';
  }
}
