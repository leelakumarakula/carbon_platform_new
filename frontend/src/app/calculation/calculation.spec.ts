import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { Me } from '../core/auth/auth.models';
import { AuthService } from '../core/auth/auth.service';
import { NAVIGATION, visibleNavigation } from '../core/navigation/nav.config';
import { MrvCalculationsPanel } from '../mrv/panels/mrv-calculations-panel';
import { Period } from '../mrv/mrv.models';
import { CalculationApi } from './calculation.api';
import { CalculationRunPage } from './calculation-run-page';
import { CALCULATED_LABEL, CalcRun, DEMO_LABEL, Readiness, blockerTitle, calcBadge, formatValue } from './calculation.models';

const STEPS = ['BASELINE', 'PROJECT', 'EMISSIONS', 'REMOVALS', 'LEAKAGE', 'UNCERTAINTY', 'ADJUSTMENT', 'NET'];

function signIn(permissions: string[]): void {
  TestBed.inject(AuthService).me.set({ user: { id: 'u1', email: 'x@test.example', full_name: 'X', environment: 'LIVE', must_change_password: false },
    permissions } as unknown as Me);
}

function run(over: Partial<CalcRun> = {}): CalcRun {
  return { id: 'r1', run_code: 'CALC-2026-000001', project_id: 'p1', project_code: 'PRJ-1', monitoring_period_id: 'mp1', monitoring_period: 'M1 (#1)',
    period_start: '2026-06-01', period_end: '2027-05-31', crediting_period_id: null, mrv_dataset_id: null, dataset_code: null,
    methodology_label: 'DEMO-ALM-SOC v1.0', methodology_version_id: 'v1', is_demo_illustrative: true, calculation_rules_version: 2,
    module_code: null, module_version: null, module_readiness: null, engine_version: 'calc-framework-1.0', input_sha256: null, output_sha256: null,
    net_result: null, net_unit: null, status: 'BLOCKED', status_reason: null,
    blockers: [{ code: 'CONFIGURATION_REQUIRED', message: 'No calculation module is registered.', reason: 'NO_CALCULATION_MODULE', details: {} }],
    notes: null, recalculation_of_run_id: null, recalculation_of_code: null, recalculation_reason: null, superseded_by_run_id: null,
    superseded_by_code: null, superseded_at: null, environment: 'DEMO', created_by_name: 'Analyst', created_at: '2026-10-03T00:00:00Z',
    frozen_by_name: null, frozen_at: null, executed_by_name: null, executed_at: null, submitted_by_name: null, submitted_at: null,
    approved_by_name: null, approved_at: null, closed_by_name: 'Analyst', closed_at: '2026-10-03T00:00:00Z', result_label: CALCULATED_LABEL,
    demo_label: DEMO_LABEL, steps: STEPS.map((s) => ({ step: s, status: 'NOT_CONFIGURED', rule_code: null, label: 'CONFIGURATION_REQUIRED' })),
    can_freeze: false, can_execute: false, can_submit: false, can_cancel: false, can_review: false, can_approve: false, can_recalculate: true,
    ...over };
}

describe('Calculation helpers', () => {
  it('maps statuses and check results to badge tones', () => {
    expect(calcBadge('APPROVED')).toBe('ACTIVE');
    expect(calcBadge('BLOCKED')).toBe('FAILED');
    expect(calcBadge('NOT_INCLUDED_DEMO')).toBe('WARNING');
    expect(calcBadge('SUPERSEDED')).toBe('ARCHIVED');
  });

  it('names a blocker by its code and reason', () => {
    expect(blockerTitle({ code: 'CONFIGURATION_REQUIRED', reason: 'NO_CALCULATION_MODULE', message: '', details: {} }))
      .toBe('CONFIGURATION_REQUIRED — NO_CALCULATION_MODULE');
    expect(blockerTitle({ code: 'UNIT_MISMATCH', reason: null, message: '', details: {} })).toBe('UNIT_MISMATCH');
  });

  it('shows Calculations to calculation readers only; the farmer navigation is unchanged', () => {
    const items = (codes: string[]) => visibleNavigation(NAVIGATION, (c) => codes.includes(c)).flatMap((s) => s.items.map((i) => i.label));
    expect(items(['calculation.read'])).toContain('Calculations');
    expect(items(['mrv.read', 'lab.lab_read'])).not.toContain('Calculations');
    expect(items(['farmers.self'])).toHaveLength(5);   // + My payouts (Phase 11)
  });

  it('formats values for display only (the stored text stays exact)', () => {
    expect(formatValue('1.500000')).toBe('1.5');
    expect(formatValue('12')).toBe('12');
    expect(formatValue('-0.3333333333333333333333333333333333')).toBe('-0.333333…');
    expect(formatValue(null)).toBe('—');
  });
});

describe('Calculation screens', () => {
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
  });

  it('the creating request carries only the project and period — never a value', () => {
    TestBed.inject(CalculationApi).create('p1', 'mp1').subscribe();
    const req = http.expectOne('/api/v1/calculations/runs');
    expect(req.request.body).toEqual({ project_id: 'p1', monitoring_period_id: 'mp1' });
    req.flush(run());
  });

  it('MRV panel shows the actual readiness blocker (NO_CALCULATION_MODULE) and the DEMO label', async () => {
    signIn(['calculation.read', 'calculation.manage']);
    const f = TestBed.createComponent(MrvCalculationsPanel);
    f.componentRef.setInput('projectId', 'p1');
    f.componentRef.setInput('period', { id: 'mp1', name: 'Monitoring 1', period_number: 1, status: 'DATA_COLLECTION' } as Period);
    f.detectChanges();
    const readiness: Readiness = { project_id: 'p1', project_code: 'PRJ-1', project_status: 'MONITORING', environment: 'DEMO', monitoring_period_id: 'mp1',
      monitoring_period: 'Monitoring 1 (#1)', methodology_label: 'DEMO-ALM-SOC v1.0', is_demo_illustrative: true, module_code: null, module_version: null,
      module_readiness: null, dataset_id: 'd1', dataset_code: 'MRV-1', dataset_status: 'COLLECTING', ready: false,
      blockers: [{ code: 'CONFIGURATION_REQUIRED', message: 'No calculation module is registered for the locked methodology version.',
        reason: 'NO_CALCULATION_MODULE', details: {} }, { code: 'DATASET_NOT_APPROVED', message: 'No APPROVED dataset.', reason: null, details: {} }],
      warnings: [], steps: run().steps, input_rows: 0, calculation_rules: [] };
    http.expectOne((r) => r.url === '/api/v1/calculations/projects/p1/readiness').flush(readiness);
    http.expectOne((r) => r.url === '/api/v1/calculations/runs').flush([run()]);
    await f.whenStable();
    f.detectChanges();
    const el = f.nativeElement as HTMLElement;
    expect(el.querySelector('[data-testid="calc-blockers"]')?.textContent).toContain('CONFIGURATION_REQUIRED — NO_CALCULATION_MODULE');
    expect(el.querySelector('[data-testid="calc-ready"]')).toBeNull();
    expect(el.querySelector('[data-testid="demo-label"]')?.textContent).toContain(DEMO_LABEL);
    expect(el.textContent).toContain(CALCULATED_LABEL);
    expect(el.querySelector('[data-testid="create-run"]')).not.toBeNull();
    expect(el.querySelector('[data-run="CALC-2026-000001"]')).not.toBeNull();
  });

  it('run page: a blocked run shows its blockers; a calculated run shows the exact value with the label and no value input', async () => {
    for (const [r, blocked] of [[run(), true], [run({ status: 'CALCULATED', blockers: [], net_result: '7.6666666666', net_unit: 'TEST',
      output_sha256: 'ab'.repeat(32), environment: 'LIVE', demo_label: null, is_demo_illustrative: false, can_submit: true }), false]] as const) {
      const f = TestBed.createComponent(CalculationRunPage);
      f.componentRef.setInput('id', 'r1');
      f.detectChanges();
      http.expectOne('/api/v1/calculations/runs/r1').flush(r);
      http.expectOne('/api/v1/calculations/runs/r1/inputs').flush({ run_id: 'r1', input_sha256: null, snapshot: null, inputs: [] });
      http.expectOne('/api/v1/calculations/runs/r1/outputs').flush({ run_id: 'r1', output_sha256: null, net_result: r.net_result, net_unit: r.net_unit,
        result_label: CALCULATED_LABEL, demo_label: r.demo_label, steps: r.steps, outputs: [] });
      http.expectOne('/api/v1/calculations/qa/r1').flush({ run: r, checks: [], reviews: [], can_start: false, can_complete: false, can_approve: false,
        blocked_reasons: [] });
      http.expectOne('/api/v1/calculations/runs/r1/lineage').flush({ run: r, methodology: { label: 'x', is_demo_illustrative: false,
        calculation_rules_version: 1, rules: [] }, dataset: null, final: null, outputs: [], inputs: [], qa_reviews: [], history: [] });
      http.expectOne((x) => x.url === '/api/v1/calculations/runs' && x.params.get('project_id') === 'p1').flush([]);
      await f.whenStable();
      f.detectChanges();
      const el = f.nativeElement as HTMLElement;
      expect(el.querySelector('[data-testid="calc-label"]')?.textContent).toContain('Calculated tCO2e — not verified, not issued');
      expect(!!el.querySelector('[data-testid="run-blockers"]')).toBe(blocked);
      if (blocked) {
        expect(el.textContent).toContain('NO_CALCULATION_MODULE');
        expect(el.querySelector('[data-testid="demo-label"]')).not.toBeNull();
        expect(el.querySelector('[data-testid="net-result"]')).toBeNull();
      } else {
        expect(el.querySelector('[data-testid="net-result"]')?.textContent).toContain('7.6666666666');
        expect(el.querySelector('[data-testid="submit-run"]')).not.toBeNull();
      }
      expect(el.querySelector('input[name="net_result"], [data-testid="net-input"]')).toBeNull();
      f.destroy();
    }
  });
});
