import { AbstractControl, FormGroup, ValidationErrors, ValidatorFn } from '@angular/forms';

import { ApiError } from '../core/api/api.models';

/** Mirrors backend app/security/passwords.py so users get instant feedback. The API stays authoritative. */
export function passwordPolicyProblem(value: string): string | null {
  if (!value) return null;
  if (value.length < 12) return 'Use at least 12 characters.';
  if (new TextEncoder().encode(value).length > 72) return 'Use at most 72 bytes.';
  if (!/[A-Za-z]/.test(value) || !/\d/.test(value)) return 'Include at least one letter and one digit.';
  if (value.trim() !== value) return 'Remove leading or trailing spaces.';
  return null;
}

export const passwordPolicyValidator: ValidatorFn = (c: AbstractControl): ValidationErrors | null => {
  const problem = passwordPolicyProblem(String(c.value ?? ''));
  return problem ? { policy: problem } : null;
};

export function matchValidator(a: string, b: string): ValidatorFn {
  return (group: AbstractControl): ValidationErrors | null => {
    const g = group as FormGroup;
    return g.get(a)?.value === g.get(b)?.value ? null : { mismatch: true };
  };
}

/**
 * Puts server-side field errors (422 details.errors[]) onto the matching form controls.
 * Returns messages that could not be attached to a control.
 */
export function applyServerErrors(form: FormGroup, err: unknown): string[] {
  if (!(err instanceof ApiError)) return [];
  const unmatched: string[] = [];
  for (const fe of err.fieldErrors) {
    const control = form.get(fe.field.split('.')[0]);
    if (control) {
      control.setErrors({ ...(control.errors ?? {}), server: fe.message });
      control.markAsTouched();
    } else {
      unmatched.push(fe.message);
    }
  }
  return unmatched;
}
