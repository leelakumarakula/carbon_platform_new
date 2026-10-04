import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';

import { NAVIGATION, visibleNavigation } from '../core/navigation/nav.config';
import { ProjectMethodologyPanel } from '../projects/panels/project-methodology-panel';
import { Project } from '../projects/project.models';
import { CalculationModulePanel } from './calculation-module-panel';
import { MethodologyVersionPage } from './methodology-version-page';
import { CalculationModuleOption, Candidate, ProjectMethodologyView, VersionDetail, confirmable, outcomeBadge, parseFactValue } from './methodology.models';

const project = { id: 'p1', status: 'METHODOLOGY_REVIEW' } as Project;

function candidate(over: Partial<Candidate> = {}): Candidate {
  return {
    id: 'r1', methodology_id: 'm1', methodology_code: 'TEST-ALM', methodology_name: 'Test ALM', methodology_version_id: 'v1', version_label: '1.0',
    version_status: 'APPROVED', calculation_readiness: 'NOT_PRODUCTION_READY', is_demo_illustrative: false, outcome: 'EVIDENCE_REQUIRED',
    rules_version: 1, evidence_requirements: ['Additionality document'], reviews: [],
    rules: [{ rule_code: 'A1', title: 'Country', category: 'COUNTRY', fact_key: 'country', operator: 'IN', expected: ['IN'], actual: 'IN',
      fact_source: 'PROJECT', check: 'PASS', effect: 'APPLICABLE', reason: 'country = IN satisfies IN', evidence_requirement: null, source_reference: '§1' }],
    ...over,
  };
}

function view(c: Candidate, over: Partial<ProjectMethodologyView> = {}): ProjectMethodologyView {
  return { methodology_status: 'UNDER_REVIEW', project_status: 'METHODOLOGY_REVIEW', current: null, history: [], evaluation_count: 1,
    latest_evaluation: { id: 'e1', engine_version: '1.0.0', facts: { country: { value: 'IN', source: 'PROJECT', detail: '' } }, candidate_count: 1,
      evaluated_at: '2026-10-02T10:00:00Z', candidates: [c], note: 'Candidates are proposals.' },
    can_evaluate: true, can_review: false, can_confirm: true, can_unlock: false, findings: [], ...over };
}

describe('Methodology helpers', () => {
  it('only recommended, applicable or evidence-required candidates can be confirmed', () => {
    const rec = { id: 'x', evaluation_result_id: 'r1', recommendation: 'RECOMMENDED' as const, notes: 'ok', evidence_acknowledged: true,
      reviewer_name: 'S', reviewed_at: '2026-10-02T10:00:00Z' };
    expect(confirmable(candidate())).toBe(false);
    expect(confirmable(candidate({ reviews: [rec] }))).toBe(true);
    expect(confirmable(candidate({ reviews: [rec, { ...rec, recommendation: 'NOT_RECOMMENDED' }] }))).toBe(false);
    expect(confirmable(candidate({ outcome: 'NOT_APPLICABLE', reviews: [rec] }))).toBe(false);
    expect(outcomeBadge('NEEDS_INFORMATION')).toBe('INFO');
  });

  it('parses declared fact values', () => {
    expect(parseFactValue('COMPLETED')).toBe('COMPLETED');
    expect(parseFactValue('5')).toBe(5);
    expect(parseFactValue('true')).toBe(true);
    expect(parseFactValue('TILLAGE, RESIDUE')).toEqual(['TILLAGE', 'RESIDUE']);
  });

  it('shows Methodologies to readers only', () => {
    const items = (codes: string[]) => visibleNavigation(NAVIGATION, (c) => codes.includes(c)).flatMap((s) => s.items.map((i) => i.label));
    expect(items(['methodologies.read'])).toContain('Methodologies');
    expect(items(['farmers.self'])).not.toContain('Methodologies');
  });
});

describe('Methodology screens', () => {
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
  });

  async function panel(v: ProjectMethodologyView) {
    const f = TestBed.createComponent(ProjectMethodologyPanel);
    f.componentRef.setInput('project', project);
    f.detectChanges();
    http.expectOne('/api/v1/projects/p1/methodology').flush(v);
    await f.whenStable();
    f.detectChanges();
    return f;
  }

  it('lists candidates with outcome and keeps Confirm disabled until a specialist recommends', async () => {
    const f = await panel(view(candidate()));
    const el = f.nativeElement as HTMLElement;
    expect(el.textContent).toContain('TEST-ALM v1.0');
    expect(el.textContent).toContain('Evidence required');
    const confirmBtn = Array.from(el.querySelectorAll('button')).find((b) => b.textContent?.includes('Confirm & lock')) as HTMLButtonElement;
    expect(confirmBtn.disabled).toBe(true);
  });

  it('refuses to declare a fact derived from project data and sends declared facts', async () => {
    const f = await panel(view(candidate()));
    const c = f.componentInstance as unknown as { fact: { setValue: (v: object) => void }; addFact: () => void; evaluate: () => void;
      factError: () => string | null; declared: () => Record<string, unknown> };
    c.fact.setValue({ key: 'country', value: 'BR' });
    c.addFact();
    expect(c.factError()).toContain('comes from project data');
    c.fact.setValue({ key: 'additionality_assessment', value: 'COMPLETED' });
    c.addFact();
    expect(c.declared()).toEqual({ additionality_assessment: 'COMPLETED' });
    c.evaluate();
    const req = http.expectOne('/api/v1/projects/p1/methodology/candidates');
    expect(req.request.body).toEqual({ declared_facts: { additionality_assessment: 'COMPLETED' } });
  });

  it('shows the lock and hides evaluation once confirmed', async () => {
    const locked = { id: 'l1', methodology_code: 'TEST-ALM', methodology_name: 'Test ALM', methodology_version_id: 'v1', version_label: '1.0',
      version_status: 'APPROVED', rules_version: 1, monitoring_rules_version: 1, calculation_rules_version: 1, calculation_readiness: 'NOT_PRODUCTION_READY',
      status: 'LOCKED' as const, confirmation_notes: 'Confirmed', locked_at: '2026-10-02T10:00:00Z', unlocked_at: null, unlock_reason: null,
      newer_version_available: true };
    const f = await panel(view(candidate(), { current: locked, can_evaluate: false, can_confirm: false, can_unlock: true,
      methodology_status: 'CONFIRMED', project_status: 'METHODOLOGY_CONFIRMED' }));
    const el = f.nativeElement as HTMLElement;
    expect(el.textContent).toContain('TEST-ALM · version 1.0');
    expect(el.textContent).toContain('A newer approved version exists');
    expect(el.textContent).not.toContain('Evaluate candidates');
    expect(Array.from(el.querySelectorAll('button')).some((b) => b.textContent?.trim() === 'Unlock')).toBe(true);
  });

  it('version page: approved versions cannot be edited, drafts can', async () => {
    const base: VersionDetail = { id: 'v1', methodology_id: 'm1', version_number: 1, version_label: '1.0', status: 'APPROVED', effective_from: '2020-01-01',
      effective_to: null, source_name: 'Source', source_url: null, source_document_id: null, rules_version: 1, monitoring_rules_version: 1,
      calculation_rules_version: 1, calculation_readiness: 'NOT_PRODUCTION_READY', is_demo_illustrative: false, notes: null, based_on_version_id: null,
      created_at: '2026-10-02T00:00:00Z', submitted_by: 'a', submitted_at: null, approved_by: 'b', approved_at: null, superseded_at: null,
      superseded_by_id: null, status_reason: null, rule_counts: { applicability: 0, monitoring: 0, calculation: 0, general: 0 },
      methodology_code: 'TEST-ALM', methodology_name: 'Test ALM', rules: [], can_edit: false, can_submit: false, can_approve: false };
    for (const [v, editable] of [[base, false], [{ ...base, status: 'DRAFT' as const, can_edit: true, can_submit: true }, true]] as const) {
      const f = TestBed.createComponent(MethodologyVersionPage);
      f.componentRef.setInput('id', 'v1');
      f.detectChanges();
      http.expectOne('/api/v1/methodologies/versions/v1').flush(v);
      http.expectOne('/api/v1/methodologies/m1/history').flush([]);
      await f.whenStable();
      f.detectChanges();
      const text = (f.nativeElement as HTMLElement).textContent ?? '';
      expect(text.includes('Add rule')).toBe(editable);
      expect(text.includes('cannot be edited')).toBe(!editable);
      f.destroy();
    }
  });

  it('calculation tab shows the selected VM0042 module, the data it needs and the readiness step', async () => {
    const v = { id: 'v2', methodology_id: 'm1', version_number: 1, version_label: '2.2', status: 'APPROVED', effective_from: '2025-10-21',
      effective_to: null, source_name: 'Verra', source_url: null, source_document_id: null, rules_version: 1, monitoring_rules_version: 1,
      calculation_rules_version: 1, calculation_readiness: 'NOT_PRODUCTION_READY', calculation_module_code: 'VM0042-V2.2-QA2-QA3',
      is_demo_illustrative: false, notes: null, based_on_version_id: null, created_at: '2026-10-05T00:00:00Z', submitted_by: 'a', submitted_at: null,
      approved_by: 'b', approved_at: null, superseded_at: null, superseded_by_id: null, status_reason: null,
      rule_counts: { applicability: 1, monitoring: 13, calculation: 8, general: 1 }, methodology_code: 'VM0042', methodology_name: 'IALM',
      rules: [], can_edit: false, can_submit: false, can_approve: false, readiness_request: null } as VersionDetail;
    const option: CalculationModuleOption = { code: 'VM0042-V2.2-QA2-QA3', version: '1.0.0', label: 'VM0042 v2.2 - SOC measure & remeasure',
      methodology_code: 'VM0042', version_label: '2.2', readiness: 'NOT_PRODUCTION_READY', compatible: true, selected: true,
      calculation_rules: [{ rule_code: 'V42-UNC', step: 'UNCERTAINTY', title: 'Approach 2 sampling uncertainty deduction', equation_reference: 'Eqs. 70, 71, 74' }],
      monitoring_rules: [{ rule_code: 'V42_OC', title: 'Soil organic carbon content', parameter: 'soil_organic_carbon', unit: 'g/kg',
        measurement_source: 'LABORATORY', data_level: 'SAMPLING_POINT' }],
      sampling_parameters: { min_samples_per_stratum: 3 }, assumptions: ['Q12: equivalent mineral soil mass'], variables: [] };
    const f = TestBed.createComponent(CalculationModulePanel);
    f.componentRef.setInput('v', v);
    f.detectChanges();
    http.expectOne('/api/v1/methodologies/versions/v2/calculation-modules').flush([option]);
    await f.whenStable();
    f.detectChanges();
    const text = (f.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('VM0042 v2.2 - SOC measure & remeasure');
    expect(text).toContain('V42-UNC');
    expect(text).toContain('Soil organic carbon content');
    expect(text).toContain('Min samples per stratum = 3');
    expect(text).toContain('Not production ready');
    expect(text).toContain('Production readiness');
  });
});
