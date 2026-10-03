import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { Me } from '../core/auth/auth.models';
import { AuthService } from '../core/auth/auth.service';
import { NAVIGATION, visibleNavigation } from '../core/navigation/nav.config';
import { VerificationFindings } from './verification-findings';
import { VerificationPanel } from './verification-panel';
import {
  Assignment, CALCULATED_LABEL, Decision, PeriodVerification, VERIFIED_QUANTITY_LABEL, VFINDING_CATEGORIES, VFinding, assignmentBadge, decisionBadge,
  statedQuantity,
} from './verification.models';
import { VvbAssignmentPage } from './vvb-assignment-page';
import { VvbWorkspacePage } from './vvb-workspace-page';

function signIn(permissions: string[]): void {
  TestBed.inject(AuthService).me.set({ user: { id: 'u1', email: 'x@test.example', full_name: 'X', environment: 'LIVE', must_change_password: false },
    permissions } as unknown as Me);
}

function assignment(over: Partial<Assignment> = {}): Assignment {
  return { id: 'a1', assignment_code: 'VAS-2026-000001', project_id: 'p1', project_code: 'PRJ-1', project_name: 'Test project', monitoring_period_id: 'mp1',
    period_number: 1, period_start: '2026-06-01', period_end: '2027-05-31', vvb_organization_id: 'v1', vvb_organization_name: 'VVB C', status: 'PROPOSED',
    previous_assignment_id: null, notes: null, proposed_by_name: 'Project team', proposed_at: '2026-10-03T00:00:00Z', accepted_by_name: null,
    accepted_at: null, coi_declaration: null, coi_declared_by_name: null, coi_declared_at: null, completed_at: null, closed_side: null, closed_reason: null,
    closed_at: null, environment: 'DEMO', current_submission: null, submissions: [], decisions: [], actions: [], decision_blockers: [], ...over };
}

function decision(over: Partial<Decision> = {}): Decision {
  return { id: 'd1', decision_code: 'VDEC-2026-000001', assignment_id: 'a1', submission_id: 's1', submission_code: 'VSUB-2026-000001',
    monitoring_period_id: 'mp1', vvb_organization_id: 'v1', vvb_organization_name: 'VVB C', outcome: 'VERIFIED', verified_quantity: '12.5',
    verified_quantity_unit: 'tCO2e', verified_quantity_label: VERIFIED_QUANTITY_LABEL, verified_quantity_note: 'Not issued; not a credit.',
    rationale: 'TEST', report_document_id: 'doc', report_sha256: 'x', manifest_sha256: 'y', decided_by_name: 'V', decided_at: '2026-10-03T00:00:00Z',
    status: 'CURRENT', superseded_at: null, superseded_reason: null, note: 'records', ...over };
}

function vfinding(over: Partial<VFinding> = {}): VFinding {
  return { id: 'f1', finding_code: 'VFND-2026-000001', assignment_id: 'a1', submission_id: 's1', category: 'MISSING_EVIDENCE',
    category_label: 'Missing Evidence', blocking: true, title: 'Field sheet', description: 'Missing', target_type: 'SUBMISSION', target_ref: null,
    status: 'OPEN', raised_by_name: 'V', raised_at: '2026-10-03T00:00:00Z', response_text: null, response_document_id: null, responded_by_name: null,
    responded_at: null, closure_note: null, closed_by_name: null, closed_at: null, events: [], corrective_actions: [], ...over };
}

describe('Verification helpers', () => {
  it('offers exactly the six finding categories', () => {
    expect(VFINDING_CATEGORIES.map((c) => c.label)).toEqual(['Observation', 'Non-conformity', 'Clarification', 'Missing Evidence', 'Calculation Issue',
      'Methodology Issue']);
  });

  it('labels quantities without ever calling them credits', () => {
    expect(CALCULATED_LABEL).toBe('Calculated tCO2e — not verified, not issued');
    expect(VERIFIED_QUANTITY_LABEL).toBe('VVB-stated verified quantity');
    expect(statedQuantity(decision())).toBe('12.5 tCO2e');
    expect(statedQuantity(decision({ verified_quantity: null, verified_quantity_unit: null }))).toBeNull();
    expect(decisionBadge(decision({ status: 'SUPERSEDED' }))).toBe('ARCHIVED');
    expect(decisionBadge(decision({ outcome: 'NOT_VERIFIED', verified_quantity: null }))).toBe('FAILED');
    expect(assignmentBadge('COMPLETED')).toBe('ACTIVE');
  });

  it('shows the VVB workspace only to VVB users; no marketplace, transfer or retirement navigation exists', () => {
    const labels = (perms: string[]) => visibleNavigation(NAVIGATION, (c) => perms.includes(c)).flatMap((s) => s.items.map((i) => i.label));
    expect(labels(['verification.vvb_read'])).toContain('VVB workspace');
    expect(labels(['verification.read', 'verification.manage', 'calculation.read'])).not.toContain('VVB workspace');
    const all = NAVIGATION.flatMap((s) => s.items.map((i) => `${i.label} ${i.route}`.toLowerCase())).join(' ');
    for (const word of ['marketplace', 'transfer', 'retire', 'reservation', 'inventory', 'payout']) expect(all).not.toContain(word);
  });
});

describe('Verification screens', () => {
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
  });

  function period(over: Partial<PeriodVerification> = {}): PeriodVerification {
    return { project_id: 'p1', project_status: 'CALCULATED', monitoring_period_id: 'mp1', period_number: 1, ready_review_code: null,
      calculated_value: '3.75', calculated_unit: 'TEST', calculated_label: CALCULATED_LABEL, assignments: [], current_decision: null,
      submit_blockers: ['No valid READY package (Phase 8A internal readiness) for this period.'], can_manage: true, can_respond: true, ...over };
  }

  it('project panel: labels the calculated quantity, offers propose to managers and shows submit blockers', async () => {
    signIn(['verification.read', 'verification.manage']);
    const f = TestBed.createComponent(VerificationPanel);
    f.componentRef.setInput('projectId', 'p1');
    f.componentRef.setInput('periodId', 'mp1');
    f.detectChanges();
    http.expectOne('/api/v1/verification/projects/p1/periods/mp1').flush(period());
    http.expectOne('/api/v1/verification/projects/p1/vvb-organizations').flush([{ id: 'v1', name: 'VVB C', code: 'DEMO-VVB-C' }]);
    await f.whenStable();
    f.detectChanges();
    const el = f.nativeElement as HTMLElement;
    expect(el.querySelector('[data-testid="calculated-label"]')?.textContent).toContain(CALCULATED_LABEL);
    expect(el.querySelector('[data-testid="propose-assignment"]')).not.toBeNull();
    expect(el.querySelector('[data-testid="submit-blockers"]')?.textContent).toContain('READY');
    expect(el.textContent?.toLowerCase()).not.toContain('issue credits');
  });

  it('project panel: an accepted assignment offers submit; a decision shows the VVB-stated quantity apart from the calculated one', async () => {
    signIn(['verification.read', 'verification.manage', 'verification.respond']);
    const f = TestBed.createComponent(VerificationPanel);
    f.componentRef.setInput('projectId', 'p1');
    f.componentRef.setInput('periodId', 'mp1');
    f.detectChanges();
    const a = assignment({ status: 'ACCEPTED', actions: ['submit', 'terminate', 'respond'], coi_declaration: 'No conflict', environment: 'LIVE' });
    http.expectOne('/api/v1/verification/projects/p1/periods/mp1').flush(period({ assignments: [a], current_decision: decision(), submit_blockers: [] }));
    http.expectOne('/api/v1/verification/projects/p1/vvb-organizations').flush([]);
    await f.whenStable();
    f.detectChanges();
    const el = f.nativeElement as HTMLElement;
    expect(el.querySelector('[data-testid="submit-package"]')).not.toBeNull();
    expect(el.querySelector('[data-testid="propose-assignment"]')).toBeNull();          // one open assignment per period
    expect(el.querySelector('[data-testid="stated-quantity"]')?.textContent).toContain(VERIFIED_QUANTITY_LABEL);
    expect(el.querySelector('[data-testid="stated-quantity"]')?.textContent).toContain('12.5 tCO2e');
    expect(el.querySelector('[data-testid="calculated-label"]')?.textContent).toContain('not verified, not issued');
  });

  it('findings: the project responds but never closes; the VVB closes, raises and requests corrective actions', async () => {
    signIn(['verification.respond']);
    const p = TestBed.createComponent(VerificationFindings);
    p.componentRef.setInput('submissionId', 's1');
    p.componentRef.setInput('side', 'PROJECT');
    p.componentRef.setInput('canAct', true);
    p.detectChanges();
    http.expectOne('/api/v1/verification/submissions/s1/findings').flush([vfinding(), vfinding({ id: 'f2', finding_code: 'VFND-2', status: 'RESPONDED' })]);
    await p.whenStable();
    p.detectChanges();
    let el = p.nativeElement as HTMLElement;
    expect(el.querySelectorAll('[data-testid="vrespond"]').length).toBe(1);
    expect(el.querySelector('[data-testid="vclose"]')).toBeNull();
    expect(el.querySelector('[data-testid="vraise"]')).toBeNull();
    p.destroy();

    signIn(['verification.vvb_read', 'verification.vvb_review']);
    const v = TestBed.createComponent(VerificationFindings);
    v.componentRef.setInput('submissionId', 's1');
    v.componentRef.setInput('side', 'VVB');
    v.componentRef.setInput('canAct', true);
    v.detectChanges();
    http.expectOne('/api/v1/vvb/submissions/s1/findings').flush([vfinding({ status: 'RESPONDED', corrective_actions: [{ id: 'c1', action_code: 'CAR-1',
      finding_id: 'f1', description: 'Sheet', due_date: '2020-01-01', overdue: true, status: 'REQUESTED', requested_by_name: 'V',
      requested_at: '2026-10-03T00:00:00Z', response_text: null, response_document_id: null, responded_by_name: null, responded_at: null,
      reviewed_by_name: null, reviewed_at: null, review_note: null, events: [] }] })]);
    await v.whenStable();
    v.detectChanges();
    el = v.nativeElement as HTMLElement;
    expect(el.querySelector('[data-testid="vclose"]')).not.toBeNull();
    expect(el.querySelector('[data-testid="vraise"]')).not.toBeNull();
    expect(el.querySelector('[data-testid="vrespond"]')).toBeNull();
    expect(el.querySelector('[data-ca="CAR-1"]')?.textContent).toContain('Overdue');
  });

  it('VVB workspace lists only what the VVB API returns', async () => {
    signIn(['verification.vvb_read']);
    const f = TestBed.createComponent(VvbWorkspacePage);
    f.detectChanges();
    http.expectOne('/api/v1/vvb/assignments').flush([assignment()]);
    await f.whenStable();
    f.detectChanges();
    expect((f.nativeElement as HTMLElement).querySelector('[data-assignment="VAS-2026-000001"]')?.textContent).toContain('PRJ-1');
  });

  it('VVB assignment: accept requires a COI declaration; no package before acceptance; no decision form without the decide action', async () => {
    signIn(['verification.vvb_read', 'verification.vvb_review', 'verification.decide']);
    const f = TestBed.createComponent(VvbAssignmentPage);
    f.componentRef.setInput('id', 'a1');
    f.detectChanges();
    http.expectOne('/api/v1/vvb/assignments/a1').flush(assignment({ actions: ['accept', 'decline'] }));
    await f.whenStable();
    f.detectChanges();
    const el = f.nativeElement as HTMLElement;
    const accept = el.querySelector('[data-testid="accept-assignment"]') as HTMLButtonElement;
    expect(accept.disabled).toBe(true);
    expect(el.querySelector('[data-testid="vvb-package"]')).toBeNull();
    http.expectNone((r) => r.url.includes('/package'));
  });
});
