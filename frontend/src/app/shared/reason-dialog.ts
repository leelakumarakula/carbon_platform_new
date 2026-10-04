import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialog, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { Observable } from 'rxjs';

import { passwordPolicyValidator } from './forms';
import { generateTemporaryPassword } from './password';

export interface ReasonDialogData {
  title: string;
  message?: string;
  confirmLabel?: string;
  danger?: boolean;
  /** Also ask for a temporary password (used by admin password reset). */
  withPassword?: boolean;
}

export interface ReasonDialogResult {
  reason: string;
  password?: string;
}

/** Every consequential admin action records why it was done (audit `reason`). */
@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatDialogModule, MatButtonModule, MatFormFieldModule, MatInputModule, ReactiveFormsModule],
  template: `
    <h2 mat-dialog-title>{{ data.title }}</h2>
    <form [formGroup]="form" (ngSubmit)="submit()">
      <mat-dialog-content>
        @if (data.message) { <p>{{ data.message }}</p> }
        @if (data.withPassword) {
          <mat-form-field appearance="outline" class="full">
            <mat-label>Temporary password</mat-label>
            <input matInput formControlName="password" autocomplete="off" />
            <button mat-button matSuffix type="button" (click)="generate()">Generate</button>
            <mat-hint>The user must change it at next sign-in. Share it through a secure channel.</mat-hint>
            @if (form.controls.password.hasError('policy')) {
              <mat-error>{{ form.controls.password.getError('policy') }}</mat-error>
            }
          </mat-form-field>
        }
        <mat-form-field appearance="outline" class="full">
          <mat-label>Reason (recorded in the audit log)</mat-label>
          <textarea matInput formControlName="reason" rows="3" cdkFocusInitial></textarea>
          @if (form.controls.reason.hasError('minlength') || form.controls.reason.hasError('required')) {
            <mat-error>Please give a reason (at least 3 characters).</mat-error>
          }
        </mat-form-field>
      </mat-dialog-content>
      <mat-dialog-actions align="end">
        <button mat-button type="button" mat-dialog-close>Cancel</button>
        <button mat-flat-button type="submit" [class.danger]="data.danger" [disabled]="form.invalid">
          {{ data.confirmLabel ?? 'Confirm' }}
        </button>
      </mat-dialog-actions>
    </form>
  `,
  styles: `.full { width: 100%; } form { min-width: min(440px, 80vw); }`,
})
export class ReasonDialog {
  protected readonly data = inject<ReasonDialogData>(MAT_DIALOG_DATA);
  private readonly ref = inject(MatDialogRef<ReasonDialog, ReasonDialogResult>);

  protected readonly form = new FormGroup({
    reason: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.minLength(3), Validators.maxLength(1000)] }),
    password: new FormControl('', { nonNullable: true, validators: this.data.withPassword ? [Validators.required, passwordPolicyValidator] : [] }),
  });

  protected generate(): void {
    this.form.controls.password.setValue(generateTemporaryPassword());
  }

  protected submit(): void {
    if (this.form.invalid) return;
    const { reason, password } = this.form.getRawValue();
    this.ref.close({ reason: reason.trim(), password: this.data.withPassword ? password : undefined });
  }
}

export function askReason(dialog: MatDialog, data: ReasonDialogData): Observable<ReasonDialogResult | undefined> {
  return dialog.open<ReasonDialog, ReasonDialogData, ReasonDialogResult>(ReasonDialog, { data, autoFocus: 'dialog' }).afterClosed();
}
