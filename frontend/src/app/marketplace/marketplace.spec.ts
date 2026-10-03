import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { Me } from '../core/auth/auth.models';
import { AuthService } from '../core/auth/auth.service';
import { NAVIGATION, visibleNavigation } from '../core/navigation/nav.config';
import { KycReviewPage } from './kyc-review-page';
import { MarketplaceApi } from './marketplace.api';
import { DEMO_NOTE, BuyerProfile, Listing, Order, marketBadge, money } from './marketplace.models';
import { MarketplacePage } from './marketplace-page';
import { OrdersPage } from './orders-page';

function signIn(permissions: string[]): void {
  TestBed.inject(AuthService).me.set({ user: { id: 'u1', email: 'x@test.example', full_name: 'X', environment: 'LIVE', must_change_password: false },
    permissions } as unknown as Me);
}

const LISTING: Listing = { id: 'l1', listing_code: 'LST-2026-000001', title: 'Rice credits', seller_organization_id: 's1', seller_name: 'Developer A',
  batch_id: 'b1', batch_code: 'CB-1', serial_range_id: null, listed_quantity: 500, remaining_quantity: 400, available_quantity: 400,
  unit_price: '12.5000', currency: 'INR', min_quantity: null, max_quantity: null, payment_window_hours: 24, valid_until: null, co_benefits: null,
  disclosure: { project_code: 'PRJ-1', vintage: '2026', methodology: '2.2', standard: 'VCS', registry: 'Registry R' }, disclosure_sha256: 'a'.repeat(64),
  status: 'ACTIVE', created_by_name: null, approved_by_name: null, approved_at: null, close_reason: null, documents: [], environment: 'LIVE',
  seller_side: false, can_manage: false, can_approve: false };

function order(over: Partial<Order> = {}): Order {
  return { id: 'o1', order_code: 'ORD-2026-000001', buyer_organization_id: 'b1', buyer_name: 'Buyer D', seller_organization_id: 's1',
    seller_name: 'Developer A', currency: 'INR', subtotal: '1250.0000', total: '1250.0000', status: 'PLACED', transfer_kind: 'INTERNAL',
    recipient_registry_account: null, expires_at: '2026-10-04T00:00:00Z', placed_at: '2026-10-03T00:00:00Z', paid_at: null, completed_at: null,
    close_reason: null, attention_reason: null, items: [], payments: [], refunds: [], documents: [], environment: 'LIVE', viewer_side: 'BUYER',
    can_cancel: true, can_pay: true, can_retry: false, ...over };
}

describe('Marketplace helpers and navigation', () => {
  it('formats decimal money strings without float arithmetic and maps badges', () => {
    expect(money('1250.0000', 'INR')).toBe('1250.00 INR');
    expect(money('12.5000', 'INR')).toBe('12.50 INR');
    expect(money('100.0000', 'JPY')).toBe('100 JPY');
    expect(money('0.1250', 'BHD')).toBe('0.125 BHD');
    expect(marketBadge('KYC_VERIFIED')).toBe('ACTIVE');
    expect(marketBadge('ATTENTION_REQUIRED')).toBe('FAILED');
    expect(DEMO_NOTE).toBe('DEMO — no registry-issued credits; nothing is listed');
  });

  it('shows marketplace navigation only to roles holding the permissions; no payout or checkout entry', () => {
    const labels = (perms: string[]) => visibleNavigation(NAVIGATION, (c) => perms.includes(c)).flatMap((s) => s.items.map((i) => i.label));
    const buyer = labels(['marketplace.read', 'orders.place', 'orders.read', 'payments.record', 'buyers.kyc_submit', 'credits.holder_read']);
    expect(buyer).toEqual(expect.arrayContaining(['Marketplace', 'Orders', 'Buyer profile', 'My credits']));
    expect(buyer).not.toContain('Payments');
    expect(buyer).not.toContain('Listings');
    const finance = labels(['marketplace.read', 'listings.approve', 'orders.read', 'payments.confirm', 'refunds.request', 'refunds.approve']);
    expect(finance).toEqual(expect.arrayContaining(['Listings', 'Payments', 'Orders']));
    expect(labels(['buyers.kyc_verify'])).toContain('KYC review');
    for (const perms of [['credits.read', 'credits.confirm'], ['verification.vvb_read'], ['lab.lab_read'], ['farmers.self']]) {
      expect(labels(perms).filter((l) => ['Marketplace', 'Orders', 'Payments', 'Listings', 'KYC review'].includes(l))).toEqual([]);
    }
    const all = NAVIGATION.flatMap((s) => s.items.map((i) => `${i.label} ${i.route}`.toLowerCase())).join(' ');
    for (const word of ['payout', 'checkout', 'invoice', 'commission']) expect(all).not.toContain(word);
  });
});

describe('Marketplace screens', () => {
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
  });

  it('DEMO marketplace shows the honest note and no listing', async () => {
    signIn(['marketplace.read']);
    const f = TestBed.createComponent(MarketplacePage);
    f.detectChanges();
    http.expectOne((r) => r.url === '/api/v1/marketplace/listings').flush({ listings: [], demo_note: DEMO_NOTE, note: 'n' });
    await f.whenStable();
    f.detectChanges();
    const el = f.nativeElement as HTMLElement;
    expect(el.querySelector('[data-testid="market-demo-note"]')?.textContent).toContain(DEMO_NOTE);
    expect(el.querySelector('[data-testid="no-listings"]')).not.toBeNull();
  });

  it('asks a buyer without KYC verification to complete KYC before ordering', async () => {
    signIn(['marketplace.read', 'orders.place', 'buyers.kyc_submit']);
    const f = TestBed.createComponent(MarketplacePage);
    f.detectChanges();
    http.expectOne((r) => r.url === '/api/v1/marketplace/listings').flush({ listings: [LISTING], demo_note: null, note: 'n' });
    http.expectOne('/api/v1/marketplace/buyer-profile').flush({ organization_id: 'b1', organization_name: 'Buyer D', profile: null, note: 'k' });
    await f.whenStable();
    f.detectChanges();
    const el = f.nativeElement as HTMLElement;
    expect(el.querySelector('[data-testid="kyc-required"]')).not.toBeNull();
    expect(el.querySelector('[data-listing="LST-2026-000001"]')?.textContent).toContain('12.50 INR');
    expect(el.textContent?.toLowerCase()).not.toMatch(/farmer|gps|kyc number/);
  });

  it('order detail: the buyer records a payment of the exact total; never sees confirmation controls', async () => {
    signIn(['orders.read', 'orders.place', 'payments.record']);
    const f = TestBed.createComponent(OrdersPage);
    f.detectChanges();
    http.expectOne((r) => r.url === '/api/v1/orders').flush({ orders: [order()], demo_note: null });
    f.componentInstance.open('o1');
    http.expectOne('/api/v1/orders/o1').flush(order({ payments: [{ id: 'p1', payment_code: 'PAY-1', order_id: 'o1', order_code: 'ORD-1',
      adapter_code: 'MANUAL', amount: '1250.0000', currency: 'INR', status: 'REJECTED', external_reference: null, evidence_document_id: null,
      recorded_by_name: 'B', recorded_at: '2026-10-03T00:00:00Z', confirmed_by_name: null, confirmed_at: null, reject_reason: 'not received',
      payer_name: 'Buyer D', payee_name: 'Developer A', can_confirm: false, can_refund: false }] }));
    await f.whenStable();
    f.detectChanges();
    const el = f.nativeElement as HTMLElement;
    expect(el.querySelector('[data-testid="pay-form"]')?.textContent).toContain('1250.00 INR');
    expect([...el.querySelectorAll('button')].map((b) => b.textContent?.trim())).not.toContain('Confirm receipt');
    expect(el.textContent).toContain('not a tax invoice');
  });

  it('KYC review offers decisions only when the API allows them (never on your own submission)', async () => {
    signIn(['buyers.kyc_verify']);
    const p = (over: Partial<BuyerProfile>): BuyerProfile => ({ id: 'bp1', organization_id: 'b1', organization_name: 'Buyer D', organization_code: 'B-1',
      status: 'KYC_SUBMITTED', legal_name: 'Buyer D Pvt Ltd', registration_number: null, country: 'IN', contact_name: null, contact_email: null,
      identifier_type: null, identifier_last4: null, submitted_by_name: 'B', submitted_at: '2026-10-03T00:00:00Z', verified_by_name: null,
      verified_at: null, return_reason: null, suspension_reason: null, documents: [], reviews: [], environment: 'LIVE', can_edit: false,
      can_review: true, ...over });
    const f = TestBed.createComponent(KycReviewPage);
    f.detectChanges();
    http.expectOne((r) => r.url === '/api/v1/marketplace/buyer-profiles').flush([p({}), p({ id: 'bp2', organization_code: 'B-2', can_review: false })]);
    await f.whenStable();
    f.detectChanges();
    const el = f.nativeElement as HTMLElement;
    expect(el.querySelector('[data-org="B-1"]')?.textContent).toContain('Verify');
    expect(el.querySelector('[data-org="B-2"]')?.textContent).not.toContain('Verify');
  });

  it('sends an Idempotency-Key with an order and never a balance or price', () => {
    TestBed.inject(MarketplaceApi).place({ buyer_organization_id: 'b1', items: [{ listing_id: 'l1', quantity: 10 }] }, 'k-1').subscribe();
    const req = http.expectOne('/api/v1/orders');
    expect(req.request.headers.get('Idempotency-Key')).toBe('k-1');
    expect(JSON.stringify(req.request.body)).not.toMatch(/price|total|available|balance/);
    req.flush(order());
  });
});
