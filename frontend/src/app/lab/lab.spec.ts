import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { Me } from '../core/auth/auth.models';
import { AuthService } from '../core/auth/auth.service';
import { NAVIGATION, visibleNavigation } from '../core/navigation/nav.config';
import { CollectionSamples } from './collection-samples';
import { LabQaPage } from './lab-qa-page';
import { LabTestPage } from './lab-test-page';
import { LaboratoryPage } from './laboratory-page';
import { QaLabView, ResultLabView, Sample, TestLabView, labBadge, resultTypeApprovable, resultValue, unitMatches } from './lab.models';

const RULE = { rule_id: 'r1', rule_code: 'SOC', parameter: 'Soil organic carbon', unit: '% / t C ha-1', method: 'Walkley-Black', measurement_source: 'LABORATORY' };

function result(over: Partial<ResultLabView> = {}): ResultLabView {
  return { id: 'res1', version: 1, status: 'DRAFT', result_type: 'NUMERIC', value_number: '1.230000', value_text: null, unit: '% / t C ha-1',
    analysed_at: '2026-10-01T10:00:00Z', analyst_name: 'Lab Tech', method_reported: null, report: null, supersedes_result_id: null,
    status_reason: null, submitted_at: null, approved_at: null, can_edit: true, can_submit: false, ...over };
}

function test(over: Partial<TestLabView> = {}): TestLabView {
  return { id: 't1', test_code: 'LT-2026-000001', status: 'IN_PROGRESS', sample_id: 's1', sample_code: 'SMP-2026-000001', project_code: 'PRJ-1',
    rule: RULE, required_unit: '% / t C ha-1', value_type: 'NUMBER', unit_configuration: 'CONFIGURED', method_reported: null,
    retest_of_test_code: null, retest_reason: null, results: [], can_start: false, can_enter_result: true, ...over };
}

function signIn(permissions: string[]): void {
  TestBed.inject(AuthService).me.set({ user: { id: 'u1', email: 'x@test.example', full_name: 'X', environment: 'LIVE', must_change_password: false },
    permissions } as unknown as Me);
}

describe('Laboratory helpers', () => {
  it('compares units exactly (trimmed, case-sensitive) and never converts', () => {
    expect(unitMatches('% / t C ha-1', ' % / t C ha-1 ')).toBe('MATCH');
    expect(unitMatches('mg/kg', 'MG/KG')).toBe('MISMATCH');
    expect(unitMatches('g/kg', 'mg/kg')).toBe('MISMATCH');
    expect(unitMatches(null, 'mg/kg')).toBe('CONFIGURATION_REQUIRED');
    expect(unitMatches('  ', 'mg/kg')).toBe('CONFIGURATION_REQUIRED');
  });

  it('decides numeric vs text from the plan measurement type, never from the value', () => {
    expect(resultTypeApprovable('NUMBER', 'NUMERIC')).toBe(true);
    expect(resultTypeApprovable('NUMBER', 'TEXT')).toBe(false);
    expect(resultTypeApprovable('TEXT', 'TEXT')).toBe(true);
    expect(resultTypeApprovable('TEXT', 'NUMERIC')).toBe(false);
  });

  it('shows text results verbatim ("ND", "<0.05" are not parsed)', () => {
    expect(resultValue(result({ result_type: 'TEXT', value_number: null, value_text: '<0.05' }))).toBe('<0.05 (as reported)');
    expect(resultValue(result({ result_type: 'TEXT', value_number: null, value_text: 'ND' }))).toBe('ND (as reported)');
    expect(resultValue(result())).toBe('1.23 % / t C ha-1');
  });

  it('maps statuses to badge tones', () => {
    expect(labBadge('APPROVED')).toBe('ACTIVE');
    expect(labBadge('RETEST_REQUIRED')).toBe('WARNING');
    expect(labBadge('REJECTED_AT_RECEIPT')).toBe('FAILED');
    expect(labBadge('SUPERSEDED')).toBe('ARCHIVED');
  });

  it('shows the Laboratory workspace to laboratory users only; farmers and buyers keep their navigation', () => {
    const items = (codes: string[]) => visibleNavigation(NAVIGATION, (c) => codes.includes(c)).flatMap((s) => s.items.map((i) => i.label));
    expect(items(['lab.lab_read'])).toContain('Laboratory');
    expect(items(['lab.lab_read'])).not.toContain('MRV');
    expect(items(['lab.lab_read'])).not.toContain('Farmers');
    expect(items(['mrv.read', 'lab.read'])).not.toContain('Laboratory');
    expect(items(['farmers.self'])).toHaveLength(5);   // + My payouts (Phase 11)
    expect(items(['farmers.self'])).not.toContain('Laboratory');
  });
});

describe('Laboratory screens', () => {
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
  });

  it('test page pre-fills the exact rule unit and warns on a mismatch', async () => {
    const f = TestBed.createComponent(LabTestPage);
    f.componentRef.setInput('id', 't1');
    f.detectChanges();
    http.expectOne('/api/v1/laboratory/tests/t1').flush(test());
    await f.whenStable();
    f.detectChanges();
    const el = f.nativeElement as HTMLElement;
    const unit = el.querySelector<HTMLInputElement>('[data-testid="result-unit"]');
    expect(unit?.value).toBe('% / t C ha-1');
    expect(el.textContent).not.toContain('UNIT_MISMATCH');
    unit!.value = 'g/kg';
    unit!.dispatchEvent(new Event('input'));
    f.detectChanges();
    await f.whenStable();
    f.detectChanges();
    expect(el.textContent).toContain('UNIT_MISMATCH');
  });

  it('test page blocks Submit for QA until the PDF report is attached, even if the server says can_submit', async () => {
    const report = { document_id: 'd1', category: 'LAB_REPORT', title: 'Report', file_name: 'r.pdf', sha256: 'abc', uploaded_at: null };
    const f = TestBed.createComponent(LabTestPage);
    f.componentRef.setInput('id', 't1');
    f.detectChanges();
    http.expectOne('/api/v1/laboratory/tests/t1').flush(test({ results: [result({ can_submit: true })] }));
    await f.whenStable();
    f.detectChanges();
    const el = f.nativeElement as HTMLElement;
    expect(el.querySelector<HTMLButtonElement>('[data-testid="submit-result"]')?.disabled).toBe(true);
    expect(el.textContent).toContain('Attach the PDF laboratory report before submitting for QA.');
    f.componentRef.setInput('id', 't2');          // the router reuses the page for another test: it reloads
    f.detectChanges();
    http.expectOne('/api/v1/laboratory/tests/t2').flush(test({ id: 't2', results: [result({ can_submit: true, report })] }));
    await f.whenStable();
    f.detectChanges();
    expect(el.querySelector<HTMLButtonElement>('[data-testid="submit-result"]')?.disabled).toBe(false);
    expect(el.textContent).not.toContain('Attach the PDF laboratory report');
  });

  it('test page shows CONFIGURATION_REQUIRED when the rule declares no unit', async () => {
    const f = TestBed.createComponent(LabTestPage);
    f.componentRef.setInput('id', 't1');
    f.detectChanges();
    http.expectOne('/api/v1/laboratory/tests/t1').flush(test({ required_unit: null, unit_configuration: 'CONFIGURATION_REQUIRED' }));
    await f.whenStable();
    f.detectChanges();
    expect((f.nativeElement as HTMLElement).textContent).toContain('CONFIGURATION_REQUIRED');
  });

  it('QA page explains a separation-of-duties block and offers no approval start for own work', async () => {
    const view: QaLabView = { result: result({ status: 'QA_REVIEW' }), test: test(), sample_code: 'SMP-2026-000001',
      checks: [{ key: 'separation_of_duties', label: 'Separation of duties', result: 'FAIL', details: ['You entered this result'], acknowledgeable: false }],
      reviews: [], can_start: false, can_decide: true, can_approve: false, blocked_reasons: ['you are the analyst'] };
    const f = TestBed.createComponent(LabQaPage);
    f.componentRef.setInput('id', 'res1');
    f.detectChanges();
    http.expectOne('/api/v1/laboratory/qa/res1').flush(view);
    await f.whenStable();
    f.detectChanges();
    const el = f.nativeElement as HTMLElement;
    expect(el.textContent).toContain('separation of duties');
    expect(el.querySelector('[data-check="separation_of_duties"]')?.textContent).toContain('FAIL');
    expect(el.querySelector('[data-testid="start-lab-qa"]')).toBeNull();
  });

  it('laboratory workspace lists incoming shipments with item-level receipt (no farmer or GPS data)', async () => {
    signIn(['lab.lab_read', 'lab.receive']);
    const f = TestBed.createComponent(LaboratoryPage);
    f.detectChanges();
    http.expectOne('/api/v1/laboratory/dashboard').flush({ engagements_pending: 0, shipments_incoming: 1, samples_to_register: 0, tests_open: 0,
      results_awaiting_qa: 0 });
    http.expectOne('/api/v1/laboratory/engagements').flush([]);
    http.expectOne('/api/v1/laboratory/shipments').flush([{ id: 'sh1', shipment_code: 'SHP-2026-000001', project_code: 'PRJ-1', project_org_name: 'Dev A',
      laboratory_org_name: 'Lab A', status: 'DISPATCHED', carrier: null, tracking_number: null, dispatched_at: '2026-10-01T00:00:00Z', received_at: null,
      items: [{ sample_id: 's1', sample_code: 'SMP-2026-000001', status: 'IN_SHIPMENT', seal_number: 'SEAL-1', receipt_condition: null, receipt_reason: null,
        received_at: null }], documents: [], can_receive: true }]);
    http.expectOne('/api/v1/laboratory/samples').flush([]);
    http.expectOne('/api/v1/laboratory/tests').flush([]);
    http.expectOne('/api/v1/laboratory/qa').flush([]);
    await f.whenStable();
    f.detectChanges();
    const el = f.nativeElement as HTMLElement;
    const tab = Array.from(el.querySelectorAll<HTMLElement>('[role="tab"]')).find((t) => t.textContent?.includes('Incoming'));
    tab?.click();
    f.detectChanges();
    await f.whenStable();
    f.detectChanges();
    expect(el.textContent).toContain('SHP-2026-000001');
    expect(el.querySelector('[data-testid="receive"]')).not.toBeNull();
    expect(el.textContent).not.toMatch(/farmer|latitude|longitude/i);
  });

  it('collection screen offers "Register & seal sample" only on a submitted record and only with the permission', async () => {
    const sample: Sample = { id: 's1', sample_code: 'SMP-2026-000001', root_sample_code: 'SMP-2026-000001', parent_sample_code: null, status: 'REGISTERED',
      description: 'Core', depth_top_cm: '0', depth_bottom_cm: '30', quantity: null, quantity_unit: null, container_label: null, seal_number: null,
      accession_number: null, field_collection_id: 'c1', field_collection_code: 'FIELD-1', field_collection_version: 1, field_collection_status: 'SUBMITTED',
      sampling_point_code: 'SP-1', farm_code: 'F1', project_id: 'p1', project_code: 'PRJ-1', monitoring_period_id: 'mp1', laboratory_org_id: 'l1',
      laboratory_org_name: 'Lab A', registered_by_name: 'C', registered_at: '2026-10-01T00:00:00Z', sealed_at: null, environment: 'LIVE', test_count: 1,
      approved_count: 0, can_seal: true, can_edit: true };
    for (const [status, perms, registrable] of [['IN_PROGRESS', ['lab.sample_register'], false], ['SUBMITTED', ['lab.sample_register'], true],
      ['SUBMITTED', [], false]] as const) {
      signIn([...perms]);
      const f = TestBed.createComponent(CollectionSamples);
      f.componentRef.setInput('collectionId', 'c1');
      f.componentRef.setInput('collectionStatus', status);
      f.detectChanges();
      http.expectOne((r) => r.url === '/api/v1/lab/samples' && r.params.get('field_collection_id') === 'c1').flush(registrable ? [sample] : []);
      await f.whenStable();
      f.detectChanges();
      const el = f.nativeElement as HTMLElement;
      expect(!!el.querySelector('[data-testid="register-sample"]')).toBe(registrable);
      if (registrable) expect(el.querySelector('[data-testid="seal-SMP-2026-000001"]')).not.toBeNull();
      if (registrable) expect(el.querySelector('[data-testid="sample-depth-SMP-2026-000001"]')?.textContent).toContain('0–30 cm');
      f.destroy();
    }
  });

  it('registers depth increments of one core: sends the depth, then proposes the next layer; refuses depths outside the record', async () => {
    signIn(['lab.sample_register']);
    const f = TestBed.createComponent(CollectionSamples);
    f.componentRef.setInput('collectionId', 'c1');
    f.componentRef.setInput('collectionStatus', 'ACCEPTED');
    f.componentRef.setInput('recordDepthTop', '0.0');
    f.componentRef.setInput('recordDepthBottom', '50.0');
    f.detectChanges();
    http.expectOne((r) => r.url === '/api/v1/lab/samples' && r.params.get('field_collection_id') === 'c1').flush([]);
    await f.whenStable();
    f.detectChanges();
    const el = f.nativeElement as HTMLElement;
    const top = el.querySelector<HTMLInputElement>('[data-testid="sample-depth-top"]')!;
    const bottom = el.querySelector<HTMLInputElement>('[data-testid="sample-depth-bottom"]')!;
    expect([top.value, bottom.value]).toEqual(['0', '50']);            // defaults to the field record's depth
    expect(el.textContent).toContain('Field record depth 0–50 cm');

    const type = async (input: HTMLInputElement, value: string) => {
      input.value = value;
      input.dispatchEvent(new Event('input'));
      f.detectChanges();
      await f.whenStable();
      f.detectChanges();
    };
    await type(bottom, '60');                                           // deeper than the record: blocked before sending
    expect(el.querySelector('[data-testid="depth-problem"]')?.textContent).toContain('within the field record depth');
    expect(el.querySelector<HTMLButtonElement>('[data-testid="register-sample"]')?.disabled).toBe(true);

    await type(bottom, '30');
    expect(el.querySelector('[data-testid="depth-problem"]')).toBeNull();
    el.querySelector<HTMLButtonElement>('[data-testid="register-sample"]')!.click();
    const post = http.expectOne((r) => r.method === 'POST' && r.url === '/api/v1/lab/samples');
    expect(post.request.body).toMatchObject({ field_collection_id: 'c1', depth_top_cm: 0, depth_bottom_cm: 30 });
    post.flush({ id: 's1' });
    http.expectOne((r) => r.method === 'GET' && r.url === '/api/v1/lab/samples').flush([]);
    await f.whenStable();
    f.detectChanges();
    await f.whenStable();
    f.detectChanges();
    expect([top.value, bottom.value]).toEqual(['30', '50']);           // the next layer of the same core
  });
});
