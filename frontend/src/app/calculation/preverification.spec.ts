import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { Me } from '../core/auth/auth.models';
import { AuthService } from '../core/auth/auth.service';
import { CalcReadinessPanel } from './calc-readiness-panel';
import { CalcRun } from './calculation.models';
import { FINDING_CATEGORIES, Finding, READINESS_LABEL, ReadinessState, findingBadge, readinessBadge } from './preverification.models';
import { RunFindings } from './run-findings';
import { RunReports } from './run-reports';

function signIn(permissions: string[]): void {
  TestBed.inject(AuthService).me.set({ user: { id: 'u1', email: 'x@test.example', full_name: 'X', environment: 'LIVE', must_change_password: false },
    permissions } as unknown as Me);
}

const RUN = { id: 'r1', run_code: 'CALC-2026-000001', project_id: 'p1', status: 'BLOCKED' } as CalcRun;

function finding(over: Partial<Finding> = {}): Finding {
  return { id: 'f1', finding_code: 'CFND-2026-000001', run_id: 'r1', run_code: RUN.run_code, category: 'METHODOLOGY_ISSUE',
    category_label: 'Methodology Issue', blocking: true, title: 'No calculation module', description: 'Blocked run', target_input_seq: null,
    target_output_seq: null, target_rule_code: null, target_source_type: null, evidence_document_id: null, status: 'OPEN', raised_by_name: 'QA',
    raised_at: '2026-10-03T00:00:00Z', response_text: null, responded_by_name: null, resolution_note: null, resolved_by_name: null,
    withdraw_reason: null, environment: 'DEMO', events: [{ seq: 1, action: 'RAISED', from_status: null, to_status: 'OPEN', actor_name: 'QA',
      occurred_at: '2026-10-03T00:00:00Z', note: null, document_id: null, run_id: null }],
    can_respond: true, can_resolve: false, can_return: false, can_reopen: false, can_withdraw: false, ...over };
}

describe('Pre-verification helpers', () => {
  it('offers exactly the six categories of the specification', () => {
    expect(FINDING_CATEGORIES.map((c) => c.label)).toEqual(['Observation', 'Non-conformity', 'Clarification', 'Missing Evidence', 'Calculation Issue',
      'Methodology Issue']);
  });

  it('maps finding and readiness statuses to badge tones', () => {
    expect(findingBadge('RESOLVED')).toBe('ACTIVE');
    expect(findingBadge('OPEN')).toBe('WARNING');
    expect(readinessBadge('READY')).toBe('ACTIVE');
    expect(readinessBadge('INVALIDATED')).toBe('FAILED');
  });
});

describe('Pre-verification screens', () => {
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
  });

  it('findings: QA may raise on a non-DRAFT run; the analyst sees respond; a DRAFT run takes no finding', async () => {
    for (const [perms, status, canRaise] of [[['calculation.review'], 'BLOCKED', true], [['calculation.manage'], 'BLOCKED', false],
      [['calculation.review'], 'DRAFT', false]] as const) {
      signIn([...perms]);
      const f = TestBed.createComponent(RunFindings);
      f.componentRef.setInput('run', { ...RUN, status });
      f.detectChanges();
      http.expectOne((r) => r.url === '/api/v1/calculations/findings' && r.params.get('run_id') === 'r1').flush([finding()]);
      await f.whenStable();
      f.detectChanges();
      const el = f.nativeElement as HTMLElement;
      expect(el.querySelector('[data-finding="CFND-2026-000001"]')?.textContent).toContain('Methodology Issue');
      expect(!!el.querySelector('[data-testid="raise-finding"]')).toBe(canRaise);
      expect(el.querySelector('[data-testid="respond-finding"]')).not.toBeNull();
      f.destroy();
    }
  });

  it('reports: none for a non-APPROVED run; generate offered for an APPROVED run to calculation managers', async () => {
    signIn(['calculation.read', 'calculation.manage']);
    for (const [status, generate] of [['BLOCKED', false], ['APPROVED', true]] as const) {
      const f = TestBed.createComponent(RunReports);
      f.componentRef.setInput('run', { ...RUN, status });
      f.detectChanges();
      http.expectOne('/api/v1/calculations/runs/r1/reports').flush([]);
      await f.whenStable();
      f.detectChanges();
      const el = f.nativeElement as HTMLElement;
      expect(!!el.querySelector('[data-testid="report-not-available"]')).toBe(!generate);
      expect(!!el.querySelector('[data-testid="generate-report"]')).toBe(generate);
      expect(el.textContent).toContain('not verified, not issued');
      f.destroy();
    }
  });

  it('readiness panel: "Internal readiness — not verification", the real blockers and the manifest of a READY review', async () => {
    signIn(['calculation.read']);
    const f = TestBed.createComponent(CalcReadinessPanel);
    f.componentRef.setInput('projectId', 'p1');
    f.componentRef.setInput('periodId', 'mp1');
    f.detectChanges();
    const state: ReadinessState = { project_id: 'p1', project_code: 'PRJ-1', project_status: 'MONITORING', monitoring_period_id: 'mp1',
      environment: 'DEMO', label: READINESS_LABEL, meaning: 'Internally approved for submission to verification.', current_run_id: null,
      current_run_code: null, current_report_id: null, ready_to_submit: false,
      blockers: [{ code: 'NO_APPROVED_CALCULATION', message: 'The reporting period has no APPROVED calculation run.', reason: null, details: {} }],
      checks: [], calculation_blockers: [{ code: 'CONFIGURATION_REQUIRED', message: 'No module', reason: 'NO_CALCULATION_MODULE', details: {} }],
      open_blocking_findings: [], can_create: false,
      reviews: [{ id: 'rd1', readiness_code: 'RDY-2026-000001', run_id: 'r0', run_code: 'CALC-0', report_code: 'CRPT-1', status: 'READY', checks: [],
        manifest_sha256: 'ab'.repeat(32), created_by_name: 'A', created_at: '2026-10-03T00:00:00Z', submitted_by_name: 'A', decided_by_name: 'Q',
        decided_at: null, decision_notes: null, withdraw_reason: null, invalidation_reason: null, label: READINESS_LABEL, meaning: '',
        can_submit: false, can_approve: false, can_reject: false, can_withdraw: false }] };
    http.expectOne((r) => r.url === '/api/v1/calculations/projects/p1/verification-readiness').flush(state);
    await f.whenStable();
    f.detectChanges();
    const el = f.nativeElement as HTMLElement;
    expect(el.querySelector('[data-testid="readiness-label"]')?.textContent).toContain('Internal readiness — not verification');
    expect(el.querySelector('[data-testid="readiness-blockers"]')?.textContent).toContain('NO_APPROVED_CALCULATION');
    expect(el.textContent).toContain('CONFIGURATION_REQUIRED — NO_CALCULATION_MODULE');
    expect(el.querySelector('[data-testid="create-readiness"]')).toBeNull();
    (el.querySelector('[data-testid="show-manifest"]') as HTMLButtonElement).click();
    http.expectOne('/api/v1/calculations/readiness/rd1/package').flush({ readiness_id: 'rd1', readiness_code: 'RDY-2026-000001', status: 'READY',
      manifest_sha256: 'ab'.repeat(32), manifest: { schema: 'pre-verification-manifest-v1' }, label: READINESS_LABEL });
    await f.whenStable();
    f.detectChanges();
    expect(el.querySelector('[data-testid="manifest"]')?.textContent).toContain('pre-verification-manifest-v1');
  });
});
