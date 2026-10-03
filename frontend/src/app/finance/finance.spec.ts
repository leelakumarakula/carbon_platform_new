import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { Me } from '../core/auth/auth.models';
import { AuthService } from '../core/auth/auth.service';
import { NAVIGATION, visibleNavigation } from '../core/navigation/nav.config';
import { FinanceApi } from './finance.api';
import { FIN_DEMO_NOTE, MyPayouts, Payout, finBadge, money, pctTotal } from './finance.models';
import { MyPayoutsPage } from './my-payouts-page';
import { PayoutsPage } from './payouts-page';
import { RevenuePage } from './revenue-page';
import { SharingPage } from './sharing-page';

function signIn(permissions: string[], environment = 'LIVE'): void {
  TestBed.inject(AuthService).me.set({ user: { id: 'u1', email: 'x@test.example', full_name: 'X', environment, must_change_password: false },
    permissions } as unknown as Me);
}

function payout(over: Partial<Payout> = {}): Payout {
  return { id: 'po1', payout_code: 'PYT-2026-000001', settlement_run_id: 'r1', run_code: 'SET-2026-000001', farmer_id: 'f1', farmer_name: 'Asha',
    amount: '460.0000', currency: 'INR', status: 'PENDING_APPROVAL', adapter_code: 'MANUAL', bank_last4: null, external_reference: null,
    replaces_payout_code: null, reason: null, calculated_by_name: 'A', approved_by_name: null, executed_by_name: null, paid_at: null,
    reconciled_at: null, calculated_at: '2026-10-03T00:00:00Z', transactions: [], reconciliations: [], documents: [], environment: 'LIVE', ...over };
}

describe('Finance helpers and navigation', () => {
  it('sums allocation percentages exactly (no float drift) and formats money strings', () => {
    expect(pctTotal(['33.333333', '66.666667'])).toBe('100');
    expect(pctTotal(['0.1', '0.2'])).toBe('0.3');
    expect(pctTotal(['50', 'abc'])).toBe('invalid');
    expect(pctTotal(['12.1234567'])).toBe('invalid');
    expect(money('153.3300', 'INR')).toBe('153.33 INR');
    expect(finBadge('RECONCILED')).toBe('ACTIVE');
    expect(finBadge('ON_HOLD')).toBe('WARNING');
    expect(finBadge('EXCEPTION')).toBe('FAILED');
    expect(FIN_DEMO_NOTE).toBe('DEMO — no registry-issued credits; no revenue, cost, entitlement or payout exists in DEMO');
  });

  it('shows the Finance section by permission and My payouts to farmers only', () => {
    const labels = (perms: string[]) => visibleNavigation(NAVIGATION, (c) => perms.includes(c)).flatMap((s) => s.items.map((i) => i.label));
    const finance = labels(['revenue.read', 'revenue.manage', 'settlement.read', 'settlement.calculate', 'settlement.approve', 'payouts.read',
      'payouts.calculate', 'payouts.approve', 'payouts.execute', 'payouts.reconcile', 'sharing.approve', 'costs.manage', 'costs.approve']);
    expect(finance).toEqual(expect.arrayContaining(['Revenue & costs', 'Revenue sharing', 'Settlements', 'Payouts']));
    expect(finance).not.toContain('My payouts');
    const pm = labels(['revenue.read', 'settlement.read', 'payouts.read', 'sharing.manage', 'costs.manage']);
    expect(pm).toEqual(expect.arrayContaining(['Revenue & costs', 'Revenue sharing', 'Settlements', 'Payouts']));
    const farmer = labels(['farmers.self']);
    expect(farmer).toContain('My payouts');
    expect(farmer.filter((l) => ['Revenue & costs', 'Revenue sharing', 'Settlements', 'Payouts'].includes(l))).toEqual([]);
    for (const perms of [['marketplace.read', 'orders.place'], ['verification.vvb_read'], ['lab.lab_read'], ['credits.read']]) {
      expect(labels(perms).filter((l) => ['Revenue & costs', 'Revenue sharing', 'Settlements', 'Payouts', 'My payouts'].includes(l))).toEqual([]);
    }
  });
});

describe('Finance screens', () => {
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
  });

  it('never sends a payout amount: payouts are created from a run with an empty body', () => {
    signIn(['payouts.calculate']);
    TestBed.inject(FinanceApi).createPayouts('r1').subscribe();
    const req = http.expectOne('/api/v1/payouts/from-settlement/r1');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({});
    req.flush([]);
  });

  it('DEMO revenue page shows the honest note and no project', async () => {
    signIn(['revenue.read', 'costs.manage'], 'DEMO');
    const f = TestBed.createComponent(RevenuePage);
    f.detectChanges();
    http.expectOne('/api/v1/revenue/projects').flush([]);
    await f.whenStable();
    f.detectChanges();
    const el = f.nativeElement as HTMLElement;
    expect(el.querySelector('[data-testid="fin-demo-note"]')?.textContent).toContain(FIN_DEMO_NOTE);
    expect(el.querySelector('[data-testid="fin-no-project"]')).not.toBeNull();
    expect(el.querySelector('[data-testid="cost-form"]')).toBeNull();
  });

  it('sharing form has no default farmer percentage or rounding mode', async () => {
    signIn(['sharing.manage']);
    const f = TestBed.createComponent(SharingPage);
    f.detectChanges();
    http.expectOne('/api/v1/revenue/projects').flush([{ id: 'p1', project_code: 'PRJ-1', name: 'Rice', organization_id: 'o1', environment: 'LIVE',
      periods: [{ id: 'm1', period_number: 1, name: 'P1', start_date: '2026-01-01', end_date: '2026-12-31' }],
      farms: [{ project_farm_id: 'pf1', farm_name: 'North', farmer_name: 'Asha', status: 'ACTIVE' }] }]);
    http.expectOne((r) => r.url === '/api/v1/revenue-share').flush([]);
    http.expectOne((r) => r.url === '/api/v1/allocations').flush([]);
    await f.whenStable();
    f.detectChanges();
    const el = f.nativeElement as HTMLElement;
    const inputs = Array.from(el.querySelectorAll('[data-testid="share-form"] input')) as HTMLInputElement[];
    expect(inputs.every((i) => i.type === 'checkbox' || i.value === '')).toBe(true);
    expect(el.querySelector('[data-testid="no-share"]')).not.toBeNull();
    expect(el.querySelector('[data-testid="alloc-total"]')?.textContent).toContain('Total: 0 %');
  });

  it('payouts page offers actions by permission: an approver approves, never executes', async () => {
    signIn(['payouts.read', 'payouts.approve']);
    const f = TestBed.createComponent(PayoutsPage);
    f.detectChanges();
    http.expectOne((r) => r.url === '/api/v1/payouts').flush([payout(), payout({ id: 'po2', payout_code: 'PYT-2', status: 'APPROVED', bank_last4: '7890' })]);
    http.expectOne('/api/v1/payouts/adjustments').flush([]);
    await f.whenStable();
    f.detectChanges();
    const el = f.nativeElement as HTMLElement;
    const text = el.querySelector('[data-testid="payouts"]')?.textContent ?? '';
    expect(text).toContain('Approve');
    expect(text).not.toContain('Execute');
    expect(text).toContain('••••7890');
    expect(text).toContain('460.00 INR');
  });

  it('My payouts lists only the farmer\'s own payouts or the unlinked note', async () => {
    signIn(['farmers.self']);
    const f = TestBed.createComponent(MyPayoutsPage);
    f.detectChanges();
    const body: MyPayouts = { farmer_linked: true, note: null, payouts: [{ payout_code: 'PYT-1', amount: '460.0000', currency: 'INR', status: 'PAID',
      project_code: 'PRJ-1', period_number: 1, bank_last4: '5544', paid_at: '2026-10-03T00:00:00Z', reconciled_at: null,
      calculated_at: '2026-10-02T00:00:00Z' }] };
    http.expectOne('/api/v1/payouts/me').flush(body);
    await f.whenStable();
    f.detectChanges();
    const el = f.nativeElement as HTMLElement;
    expect(el.querySelector('[data-testid="my-payouts"]')?.textContent).toContain('460.00 INR');
    expect(el.querySelector('[data-testid="my-payouts"]')?.textContent).toContain('••••5544');
  });
});
