import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { ActivatedRoute, Router } from '@angular/router';

import { ApiError } from '../core/api/api.models';
import { AuthService } from '../core/auth/auth.service';
import { AuthLayout } from './auth-layout';

@Component({
  selector: 'app-login-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, MatFormFieldModule, MatInputModule, MatButtonModule, MatIconModule, MatProgressBarModule,
    AuthLayout],
  template: `
    <app-auth-layout>
      <span class="eyebrow">Welcome back</span>
      <h1>Sign in to your workspace</h1>
      <p class="lead">Use the work email your administrator registered.</p>
      @if (expired) { <p class="notice">Your session ended. Please sign in again.</p> }
      <form [formGroup]="form" (ngSubmit)="submit()" novalidate>
        <mat-form-field appearance="outline" class="full" subscriptSizing="dynamic">
          <mat-label>Email</mat-label>
          <input matInput id="login-email" type="email" formControlName="email" autocomplete="username" (blur)="trimEmail()" />
          @if (form.controls.email.touched && form.controls.email.invalid) { <mat-error>Enter a valid email address.</mat-error> }
        </mat-form-field>
        <mat-form-field appearance="outline" class="full" subscriptSizing="dynamic">
          <mat-label>Password</mat-label>
          <input matInput id="login-password" [type]="showPassword() ? 'text' : 'password'" formControlName="password"
                 autocomplete="current-password" />
          <button mat-icon-button matSuffix type="button" (click)="showPassword.set(!showPassword())"
                  [attr.aria-label]="showPassword() ? 'Hide password' : 'Show password'">
            <mat-icon>{{ showPassword() ? 'visibility_off' : 'visibility' }}</mat-icon>
          </button>
          @if (form.controls.password.touched && form.controls.password.invalid) { <mat-error>Enter your password.</mat-error> }
        </mat-form-field>
        @if (error(); as e) { <p class="form-error" role="alert"><mat-icon inline>error_outline</mat-icon> {{ e }}</p> }
        <button mat-flat-button class="full submit" type="submit" [disabled]="submitting()">
          {{ submitting() ? 'Signing in…' : 'Sign in' }}
          @if (!submitting()) { <mat-icon iconPositionEnd>arrow_forward</mat-icon> }
        </button>
        @if (submitting()) { <mat-progress-bar mode="indeterminate" class="bar" /> }
      </form>
      <ul class="trust">
        <li><mat-icon>shield</mat-icon>Role-based access</li>
        <li><mat-icon>fingerprint</mat-icon>Every action audited</li>
      </ul>
    </app-auth-layout>
  `,
  styles: `
    .eyebrow { display: block; margin-bottom: 10px; color: var(--cp-forest-3); }
    h1 { margin: 0; font: 600 30px/1.15 var(--cp-font); color: var(--cp-navy); letter-spacing: -.025em; }
    .lead { margin: 10px 0 30px; font: italic 15.5px/1.45 var(--cp-serif); color: var(--cp-maroon); }
    mat-form-field { margin-bottom: 16px; }
    .form-error { display: flex; align-items: center; gap: 6px; padding: 10px 12px; border-radius: 8px; background: #fdf0ee; border: 1px solid #f2cdc8;
      color: #8e1b1b; font-size: 13px; margin: 0 0 16px; }
    .submit { height: 48px; font-size: 15px; border-radius: 10px; }
    .submit mat-icon { transition: transform .2s var(--cp-ease); }
    .submit:hover mat-icon { transform: translateX(3px); }
    .trust { list-style: none; display: flex; gap: 20px; flex-wrap: wrap; margin: 28px 0 0; padding: 20px 0 0; border-top: 1px solid var(--cp-line);
      font-size: 12.5px; color: var(--cp-ink-2); }
    .trust li { display: inline-flex; align-items: center; gap: 6px; }
    .trust mat-icon { font-size: 17px; width: 17px; height: 17px; color: var(--cp-forest-3); }
    .bar { margin-top: 10px; border-radius: 4px; }
    .notice { margin: 0 0 20px; }
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
