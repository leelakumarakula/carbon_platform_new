import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { Me } from '../core/auth/auth.models';
import { AuthService } from '../core/auth/auth.service';
import { NAVIGATION, visibleNavigation } from '../core/navigation/nav.config';
import { CreditsPage } from './credits-page';
import { RegistryPanel } from './registry-panel';
import {
  Batch, CALCULATED_LABEL, DEMO_NOTE, ISSUED_LABEL, Issuance, PeriodRegistry, SubmissionDetail, VERIFIED_LABEL, isOpen, issuanceBadge, serialText,
  submissionBadge,
} from './registry.models';

function signIn(permissions: string[]): void {
  TestBed.inject(AuthService).me.set({ user: { id: 'u1', email: 'x@test.example', full_name: 'X', environment: 'LIVE', must_change_password: false },
    permissions } as unknown as Me);
}

function view(over: Partial<PeriodRegistry> = {}): PeriodRegistry {
  return { project_id: 'p1', organization_id: 'o1', project_status: 'VERIFIED', environment: 'LIVE', demo_note: null, monitoring_period_id: 'mp1',
    period_number: 1, registry_status: 'NONE',
    calculated: { label: CALCULATED_LABEL, value: '10500', unit: 'tCO2e', note: null },
    verified: { label: VERIFIED_LABEL, value: '10000', unit: 'tCO2e', note: 'VDEC-1 · VERIFIED' },
    issued: [{ label: ISSUED_LABEL, value: null, unit: null, note: 'No confirmed registry issuance.' }], remaining: null, decision_code: 'VDEC-1',
    eligibility: [{ registry_account_id: 'a1', account_label: 'Account', blockers: [], warnings: [] }], registrations: [], submissions: [], issuances: [],
    can_manage: true, can_confirm: false, ...over };
}

const BATCH: Batch = { id: 'b1', batch_code: 'CB-2026-000001', issuance_id: 'i1', issuance_code: 'ISS-2026-000001', external_issuance_id: 'R-ISS-1',
  project_id: 'p1', project_code: 'PRJ-1', monitoring_period_id: 'mp1', period_number: 1, registry_name: 'Registry R', vintage: '2026', quantity: 9800,
  unit: 'TCU', status: 'ISSUED', issuance_date: '2026-10-01', serial_ranges: [{ seq: 1, serial_start: 'ABC-0001', serial_end: 'ABC-9800', quantity: 9800,
    parsed: false, is_current: true }], source_superseded: false, environment: 'LIVE', label: ISSUED_LABEL, note: 'As stated by the registry' };

function issuance(over: Partial<Issuance> = {}): Issuance {
  return { id: 'i1', issuance_code: 'ISS-2026-000001', registry_submission_id: 's1', external_issuance_id: 'R-ISS-1', issuance_date: '2026-10-01',
    quantity: 9800, unit: 'TCU', source: 'MANUAL', evidence_document_id: 'd1', api_response_sha256: null, status: 'RECORDED', corrects_issuance_id: null,
    corrected_by_issuance_id: null, correction_reason: null, recorded_by_name: 'Registry Manager', recorded_at: '2026-10-03T00:00:00Z',
    confirmed_by_name: null, confirmed_at: null, void_reason: null, cancel_reason: null, batches: [{ ...BATCH, status: 'RECORDED' }], can_confirm: true,
    label: ISSUED_LABEL, ...over };
}

function detail(over: Partial<SubmissionDetail> = {}): SubmissionDetail {
  return { id: 's1', submission_code: 'RSUB-2026-000001', project_id: 'p1', monitoring_period_id: 'mp1', registration_id: 'r1', registration_code: 'RREG-1',
    external_project_id: 'R-PRJ-1', registry_account_id: 'a1', registry_name: 'Registry R', verification_decision_id: 'd1', decision_code: 'VDEC-1',
    decision_status: 'CURRENT', previous_submission_id: null, status: 'ACCEPTED', snapshot_sha256: 'a'.repeat(64), idempotency_key: 'k',
    external_submission_id: 'R-SUB-1', submission_evidence_document_id: 'x', response_document_id: 'y', response_payload_sha256: null,
    external_response_ref: null, response_reason: null, created_at: '2026-10-03T00:00:00Z', frozen_at: null, submitted_at: null, response_at: null,
    closed_reason: null, source_superseded: false, environment: 'LIVE', snapshot: { schema: 'registry-submission-v1' }, events: [], issuances: [issuance()],
    checklist: null, documents: [], ...over };
}

describe('Registry helpers', () => {
  it('keeps the three quantity labels distinct and never calls calculated or verified quantities credits', () => {
    expect(new Set([CALCULATED_LABEL, VERIFIED_LABEL, ISSUED_LABEL]).size).toBe(3);
    expect(CALCULATED_LABEL).toBe('Calculated tCO2e — not verified, not issued');
    expect(VERIFIED_LABEL).toBe('VVB-stated verified quantity');
    expect(ISSUED_LABEL).toBe('Registry-issued credits');
    expect(DEMO_NOTE).toBe('DEMO — no registry issuance');
  });

  it('shows registry serials verbatim and maps lifecycle badges', () => {
    expect(serialText(BATCH.serial_ranges[0])).toBe('ABC-0001 – ABC-9800');
    expect(serialText({ ...BATCH.serial_ranges[0], serial_start: null, serial_end: null })).toBe('serials not supplied by the registry');
    expect(isOpen('ACCEPTED')).toBe(true);
    expect(isOpen('REJECTED')).toBe(false);
    expect(submissionBadge('INVALIDATED')).toBe('FAILED');
    expect(issuanceBadge('CONFIRMED')).toBe('ACTIVE');
  });

  it('offers Registry and Issued credits navigation by permission, and no marketplace / transfer / retirement entry', () => {
    const labels = (perms: string[]) => visibleNavigation(NAVIGATION, (c) => perms.includes(c)).flatMap((s) => s.items.map((i) => i.label));
    expect(labels(['registry.read'])).toContain('Registry');
    expect(labels(['credits.read'])).toEqual(expect.arrayContaining(['Issued credits']));
    expect(labels(['verification.vvb_read'])).not.toContain('Registry');
    const all = NAVIGATION.flatMap((s) => s.items.map((i) => `${i.label} ${i.route}`.toLowerCase())).join(' ');
    for (const word of ['transfer', 'retire', 'reservation', 'inventory', 'payout']) expect(all).not.toContain(word);
  });
});

describe('Registry screens', () => {
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
  });

  function panel(v: PeriodRegistry, d?: SubmissionDetail) {
    const f = TestBed.createComponent(RegistryPanel);
    f.componentRef.setInput('projectId', 'p1');
    f.componentRef.setInput('periodId', 'mp1');
    f.detectChanges();
    http.expectOne('/api/v1/registry/projects/p1/periods/mp1').flush(v);
    http.expectOne((r) => r.url === '/api/v1/registry/accounts').flush([]);
    if (v.can_manage) http.expectOne((r) => r.url === '/api/v1/registry/organizations').flush([]);
    if (d) http.expectOne(`/api/v1/registry/submissions/${d.id}`).flush(d);
    return f;
  }

  it('renders three separate quantity cards and the eligibility blockers', async () => {
    signIn(['registry.read', 'registry.manage']);
    const f = panel(view({ eligibility: [{ registry_account_id: null, account_label: null, blockers: [{ code: 'NO_VERIFIED_DECISION', message: 'none' }],
      warnings: [] }], verified: { label: VERIFIED_LABEL, value: null, unit: null, note: 'No current VVB decision.' } }));
    await f.whenStable();
    f.detectChanges();
    const el = f.nativeElement as HTMLElement;
    expect(el.querySelector('[data-testid="qty-calculated"]')?.textContent).toContain(CALCULATED_LABEL);
    expect(el.querySelector('[data-testid="qty-calculated"]')?.textContent).toContain('10500');
    expect(el.querySelector('[data-testid="qty-verified"]')?.textContent).toContain(VERIFIED_LABEL);
    expect(el.querySelector('[data-testid="qty-issued"]')?.textContent).toContain(ISSUED_LABEL);
    expect(el.querySelector('[data-testid="qty-issued"]')?.textContent).not.toContain('10500');
    expect(el.querySelector('[data-testid="registry-blockers"]')?.textContent).toContain('NO_VERIFIED_DECISION');
    expect(el.textContent?.toLowerCase()).not.toMatch(/transfer|retire|marketplace/);
  });

  it('DEMO shows "DEMO — no registry issuance"', async () => {
    signIn(['registry.read']);
    const f = panel(view({ environment: 'DEMO', demo_note: DEMO_NOTE, can_manage: false }));
    await f.whenStable();
    f.detectChanges();
    expect((f.nativeElement as HTMLElement).querySelector('[data-testid="demo-registry"]')?.textContent).toContain(DEMO_NOTE);
  });

  it('confirmation is offered only when the API says so (second person); managers get the issuance form on an ACCEPTED submission', async () => {
    signIn(['registry.read', 'registry.confirm']);
    const s = { ...detail(), snapshot: undefined } as unknown as PeriodRegistry['submissions'][number];
    const f = panel(view({ can_manage: false, can_confirm: true, submissions: [s] }), detail());
    await f.whenStable();
    f.detectChanges();
    let el = f.nativeElement as HTMLElement;
    expect(el.querySelector('[data-testid="confirm-issuance"]')).not.toBeNull();
    expect(el.querySelector('[data-testid="record-issuance"]')).toBeNull();          // the confirmer does not record
    expect(el.querySelector('[data-issuance="ISS-2026-000001"]')?.textContent).toContain('ABC-0001 – ABC-9800');
    f.destroy();

    signIn(['registry.read', 'registry.manage']);
    const g = panel(view({ submissions: [s] }), detail({ issuances: [issuance({ can_confirm: false })] }));
    await g.whenStable();
    g.detectChanges();
    el = g.nativeElement as HTMLElement;
    expect(el.querySelector('[data-testid="record-issuance"]')).not.toBeNull();
    expect((el.querySelector('[data-testid="record-issuance"]') as HTMLButtonElement).disabled).toBe(true);   // evidence and data first
    expect(el.querySelector('[data-testid="confirm-issuance"]')).toBeNull();
  });

  it('credits page lists registry-issued batches read-only, with no transfer or retirement controls', async () => {
    signIn(['credits.read']);
    const f = TestBed.createComponent(CreditsPage);
    f.detectChanges();
    http.expectOne((r) => r.url === '/api/v1/credits/batches').flush([BATCH]);
    await f.whenStable();
    f.detectChanges();
    const el = f.nativeElement as HTMLElement;
    expect(el.querySelector('[data-batch="CB-2026-000001"]')?.textContent).toContain('9800 TCU');
    expect(el.querySelector('[data-batch="CB-2026-000001"]')?.textContent).toContain('ABC-0001 – ABC-9800');
    const buttons = [...el.querySelectorAll('button')].map((b) => b.textContent?.toLowerCase() ?? '');
    expect(buttons.every((b) => !/transfer|retire|reserve|sell/.test(b))).toBe(true);
  });
});
