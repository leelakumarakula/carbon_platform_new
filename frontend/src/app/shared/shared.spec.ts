import { TestBed } from '@angular/core/testing';
import { FormControl, FormGroup } from '@angular/forms';
import { MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';

import { ApiError } from '../core/api/api.models';
import { toParams } from '../core/api/api.service';
import { applyServerErrors, passwordPolicyProblem } from './forms';
import { generateTemporaryPassword } from './password';
import { ReasonDialog } from './reason-dialog';
import { StatusBadge } from './status-badge';

describe('password policy (mirrors backend)', () => {
  it.each([
    ['short1', 'Use at least 12 characters.'],
    ['onlylettersaaaa', 'Include at least one letter and one digit.'],
    ['123456789012', 'Include at least one letter and one digit.'],
    [' Leading-space-1', 'Remove leading or trailing spaces.'],
  ])('rejects %s', (pw, msg) => expect(passwordPolicyProblem(pw)).toBe(msg));

  it('accepts a compliant password and generated temporary passwords', () => {
    expect(passwordPolicyProblem('Correct-Horse-42')).toBeNull();
    for (let i = 0; i < 20; i++) expect(passwordPolicyProblem(generateTemporaryPassword())).toBeNull();
  });
});

describe('applyServerErrors', () => {
  it('attaches field errors to controls and returns the rest', () => {
    const form = new FormGroup({ email: new FormControl('x') });
    const err = new ApiError(422, 'VALIDATION_FAILED', 'invalid', {
      errors: [{ field: 'email', message: 'not valid' }, { field: 'roles.0.role_code', message: 'unknown role' }],
    });
    expect(applyServerErrors(form, err)).toEqual(['unknown role']);
    expect(form.controls.email.getError('server')).toBe('not valid');
  });
});

describe('toParams', () => {
  it('drops empty values', () => {
    const p = toParams({ a: 'x', b: '', c: null, d: undefined, e: 0, f: false });
    expect(p.keys().sort()).toEqual(['a', 'e', 'f']);
  });
});

describe('StatusBadge', () => {
  it('maps statuses to tones and humanises labels', async () => {
    const f = TestBed.createComponent(StatusBadge);
    f.componentRef.setInput('status', 'SUSPENDED');
    await f.whenStable();
    const el = f.nativeElement.querySelector('span') as HTMLElement;
    expect(el.className).toContain('badge-warn');
    expect(el.textContent?.trim()).toBe('Suspended');
  });
});

describe('ReasonDialog', () => {
  it('requires a reason and returns it trimmed', async () => {
    const close = vi.fn();
    TestBed.configureTestingModule({
      imports: [ReasonDialog],
      providers: [{ provide: MAT_DIALOG_DATA, useValue: { title: 'Suspend?' } }, { provide: MatDialogRef, useValue: { close } }],
    });
    const f = TestBed.createComponent(ReasonDialog);
    await f.whenStable();
    const c = f.componentInstance as unknown as { form: FormGroup; submit(): void };
    c.submit();
    expect(close).not.toHaveBeenCalled();
    c.form.controls['reason'].setValue('  left the company  ');
    c.submit();
    expect(close).toHaveBeenCalledWith({ reason: 'left the company', password: undefined });
  });
});
