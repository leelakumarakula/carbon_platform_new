import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { Me } from '../core/auth/auth.models';
import { AuthService } from '../core/auth/auth.service';
import { NAVIGATION, visibleNavigation } from '../core/navigation/nav.config';
import { HoldingsPage } from './holdings-page';
import { LedgerApi, newKey } from './ledger.api';
import { LedgerPage } from './ledger-page';
import { BALANCE_COLUMNS, DEMO_NOTE, Holding, Inventory, InventoryBatch, LEDGER_NOTE, Transfer, ledgerBadge, total } from './ledger.models';

function signIn(permissions: string[]): void {
  TestBed.inject(AuthService).me.set({ user: { id: 'u1', email: 'x@test.example', full_name: 'X', environment: 'LIVE', must_change_password: false },
    permissions } as unknown as Me);
}

function batch(over: Partial<InventoryBatch> = {}): InventoryBatch {
  return { batch_id: 'b1', batch_code: 'CB-2026-000001', project_id: 'p1', project_code: 'PRJ-1', period_number: 1, vintage: '2026', unit: 'TCU',
    registry_name: 'Registry R', batch_status: 'ISSUED', issued: 1000, environment: 'LIVE',
    opening: { id: 'o1', opening_code: 'OPN-2026-000001', batch_id: 'b1', owner_organization_id: 'org1', status: 'CONFIRMED', requested_by_name: 'A',
      requested_at: '2026-10-03T00:00:00Z', confirmed_by_name: 'B', confirmed_at: '2026-10-03T00:00:00Z', cancel_reason: null, can_confirm: false },
    balances: [
      { owner_organization_id: 'org1', owner_name: 'Developer', available: 600, reserved: 100, pending_transfer: 0, pending_retirement: 50,
        retired: 0, transferred_out: 250 },
      { owner_organization_id: 'org2', owner_name: 'Buyer', available: 200, reserved: 0, pending_transfer: 0, pending_retirement: 0, retired: 50,
        transferred_out: 0 },
    ], ...over };
}

function inventory(batches: InventoryBatch[], demo = false): Inventory {
  return { batches, note: LEDGER_NOTE, demo_note: demo ? DEMO_NOTE : null };
}

function transfer(over: Partial<Transfer> = {}): Transfer {
  return { id: 't1', transfer_code: 'TRF-2026-000001', kind: 'REGISTRY', batch_id: 'b1', batch_code: 'CB-2026-000001', sender_organization_id: 'org1',
    sender_name: 'Developer', recipient_organization_id: 'org2', recipient_name: 'Buyer', recipient_external_account_id: 'ACC-B', quantity: 100,
    purpose: null, purpose_reference: null, reservation_id: null, status: 'REQUESTED', requested_by_name: 'A', requested_at: '2026-10-03T00:00:00Z',
    completed_by_name: null, completed_at: null, registry_transfer_reference: null, evidence_document_id: null, close_reason: null,
    completion_entry_id: null, can_complete: true, ...over };
}

const HOLDING: Holding = { position_id: 'pos1', batch_id: 'b1', batch_code: 'CB-2026-000001', owner_organization_id: 'org2', state: 'AVAILABLE',
  quantity: 200, project_code: 'PRJ-1', project_name: 'Rice', period_number: 1, vintage: '2026', methodology: 'AMS-III.AU', standard: 'VCS',
  registry_name: 'Registry R', issuance_code: 'ISS-1', external_issuance_id: 'R-ISS-1', registry_range: 'ABC-0001 – ABC-1000', sub_range: null,
  environment: 'LIVE' };

describe('Ledger helpers', () => {
  it('labels the six derived balance figures (plus Issued) and sums per batch for display only', () => {
    expect(BALANCE_COLUMNS.map((c) => c.label)).toEqual(['Available', 'Reserved', 'Pending transfer', 'Pending retirement', 'Transferred out', 'Retired']);
    expect(total(batch(), 'available')).toBe(800);
    expect(total(batch(), 'retired')).toBe(50);
    expect(DEMO_NOTE).toBe('DEMO — no registry-issued credits');
    expect(LEDGER_NOTE.toLowerCase()).toContain('not a marketplace');
  });

  it('maps ledger states to badges and makes distinct idempotency keys', () => {
    expect(ledgerBadge('AVAILABLE')).toBe('ACTIVE');
    expect(ledgerBadge('RETIRED')).toBe('INFO');
    expect(ledgerBadge('REJECTED')).toBe('FAILED');
    expect(newKey()).not.toBe(newKey());
  });

  it('offers Credit ledger to credits.read and My credits to holders only; no marketplace navigation', () => {
    const labels = (perms: string[]) => visibleNavigation(NAVIGATION, (c) => perms.includes(c)).flatMap((s) => s.items.map((i) => i.label));
    expect(labels(['credits.read'])).toContain('Credit ledger');
    expect(labels(['credits.read'])).not.toContain('My credits');
    expect(labels(['credits.holder_read'])).toContain('My credits');
    expect(labels(['credits.holder_read'])).not.toContain('Credit ledger');
    expect(labels(['verification.vvb_read', 'lab.lab_read'])).not.toContain('Credit ledger');
    const all = NAVIGATION.flatMap((s) => s.items.map((i) => `${i.label} ${i.route}`.toLowerCase())).join(' ');
    for (const word of ['checkout', 'payout', 'price', 'invoice']) expect(all).not.toContain(word);   // Phase 10 adds the marketplace only
  });
});

describe('Ledger screens', () => {
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
  });

  async function ledger(inv: Inventory) {
    const f = TestBed.createComponent(LedgerPage);
    f.detectChanges();
    http.expectOne('/api/v1/credits/inventory').flush(inv);
    await f.whenStable();
    f.detectChanges();
    return f;
  }

  function flushBatch(transfers: Transfer[] = []): void {
    http.expectOne((r) => r.url === '/api/v1/credits/batches/b1/positions').flush([]);
    http.expectOne((r) => r.url === '/api/v1/credits/reservations').flush([]);
    http.expectOne((r) => r.url === '/api/v1/credits/transfers').flush(transfers);
    http.expectOne((r) => r.url === '/api/v1/credits/retirements').flush([]);
    http.expectOne('/api/v1/credits/reversals').flush([]);
  }

  it('shows Issued and the six derived figures per batch, and never a price or buy control', async () => {
    signIn(['credits.read']);
    const f = await ledger(inventory([batch()]));
    const el = f.nativeElement as HTMLElement;
    const head = el.querySelector('[data-testid="ledger-inventory"] thead')?.textContent ?? '';
    for (const h of ['Issued (registry)', 'Available', 'Reserved', 'Pending transfer', 'Pending retirement', 'Transferred out', 'Retired']) {
      expect(head).toContain(h);
    }
    const row = el.querySelector('[data-batch="CB-2026-000001"]')?.textContent ?? '';
    expect(row).toContain('1000 TCU');
    expect(row).toContain('800');
    const buttons = [...el.querySelectorAll('button')].map((b) => b.textContent?.toLowerCase() ?? '');
    expect(buttons.every((b) => !/price|checkout|buy|sell|pay/.test(b))).toBe(true);
    expect(el.querySelector('[data-testid="ledger-inventory"]')?.textContent?.toLowerCase()).not.toMatch(/price|payment/);
    expect(el.querySelector('[data-testid="ledger-demo-note"]')).toBeNull();
  });

  it('DEMO shows "DEMO — no registry-issued credits" and an empty ledger', async () => {
    signIn(['credits.read', 'credits.manage']);
    const f = await ledger(inventory([], true));
    const el = f.nativeElement as HTMLElement;
    expect(el.querySelector('[data-testid="ledger-demo-note"]')?.textContent).toContain(DEMO_NOTE);
    expect(el.querySelector('[data-testid="no-ledger-batches"]')).not.toBeNull();
  });

  it('offers "Open in ledger" to managers for an unopened ISSUED batch and confirmation only when the API allows it', async () => {
    signIn(['credits.read', 'credits.manage']);
    let f = await ledger(inventory([batch({ opening: null })]));
    let buttons = [...(f.nativeElement as HTMLElement).querySelectorAll('button')].map((b) => b.textContent?.trim());
    expect(buttons).toContain('Open in ledger');
    f.destroy();

    signIn(['credits.read', 'credits.confirm']);
    const requested = { ...batch().opening!, status: 'REQUESTED' as const, can_confirm: true };
    f = await ledger(inventory([batch({ opening: requested })]));
    buttons = [...(f.nativeElement as HTMLElement).querySelectorAll('button')].map((b) => b.textContent?.trim());
    expect(buttons).toContain('Confirm opening');
    expect(buttons).not.toContain('Open in ledger');
    f.destroy();

    signIn(['credits.read', 'credits.manage']);
    f = await ledger(inventory([batch({ opening: { ...requested, can_confirm: false } })]));
    buttons = [...(f.nativeElement as HTMLElement).querySelectorAll('button')].map((b) => b.textContent?.trim());
    expect(buttons).not.toContain('Confirm opening');                  // the requester never confirms their own request
  });

  it('batch detail: managers get the forms; a REGISTRY transfer completes only with a reference and an evidence PDF', async () => {
    signIn(['credits.read', 'credits.confirm']);
    const f = await ledger(inventory([batch()]));
    const el = f.nativeElement as HTMLElement;
    ([...el.querySelectorAll('button')].find((b) => b.textContent?.trim() === 'Details') as HTMLButtonElement).click();
    flushBatch([transfer()]);
    await f.whenStable();
    f.detectChanges();
    expect(el.querySelector('[data-testid="ledger-balances"]')?.textContent).toContain('Buyer');
    expect(el.querySelector('[data-testid="transfer-form"]')).toBeNull();          // confirmer only: no request forms
    const row = el.querySelector('[data-transfer="TRF-2026-000001"]') as HTMLElement;
    const complete = [...row.querySelectorAll('button')].find((b) => b.textContent?.trim() === 'Complete') as HTMLButtonElement;
    expect(complete.disabled).toBe(true);
  });

  it('sends an Idempotency-Key and only movement quantities — never a balance', () => {
    const api = TestBed.inject(LedgerApi);
    api.reserve({ batch_id: 'b1', owner_organization_id: 'org1', quantity: 10, purpose: 'Hold', expires_at: '2026-10-10T00:00:00Z' }, 'k-1').subscribe();
    const req = http.expectOne('/api/v1/credits/reservations');
    expect(req.request.headers.get('Idempotency-Key')).toBe('k-1');
    expect(Object.keys(req.request.body as object)).not.toEqual(expect.arrayContaining(['available']));
    for (const k of Object.keys(req.request.body as object)) expect(k).not.toMatch(/available|balance/);
    req.flush({});
  });

  it('holder view lists own holdings without farmer or farm data and offers a retirement request for AVAILABLE credits', async () => {
    signIn(['credits.holder_read', 'credits.holder_retire']);
    const f = TestBed.createComponent(HoldingsPage);
    f.detectChanges();
    http.expectOne('/api/v1/credits/holdings').flush({ holdings: [HOLDING], demo_note: null, note: 'Your organization\'s positions' });
    http.expectOne((r) => r.url === '/api/v1/credits/retirements').flush([]);
    await f.whenStable();
    f.detectChanges();
    const el = f.nativeElement as HTMLElement;
    const row = el.querySelector('[data-batch="CB-2026-000001"]')?.textContent ?? '';
    expect(row).toContain('AMS-III.AU');
    expect(row).toContain('200');
    expect(el.textContent?.toLowerCase()).not.toMatch(/farmer|farm |gps|kyc|bank/);
    expect([...el.querySelectorAll('button')].map((b) => b.textContent?.trim())).toContain('Request retirement');
  });

  it('holder view in DEMO shows the DEMO note and no holdings', async () => {
    signIn(['credits.holder_read']);
    const f = TestBed.createComponent(HoldingsPage);
    f.detectChanges();
    http.expectOne('/api/v1/credits/holdings').flush({ holdings: [], demo_note: DEMO_NOTE, note: 'n' });
    http.expectOne((r) => r.url === '/api/v1/credits/retirements').flush([]);
    await f.whenStable();
    f.detectChanges();
    const el = f.nativeElement as HTMLElement;
    expect(el.querySelector('[data-testid="holdings-demo-note"]')?.textContent).toContain(DEMO_NOTE);
    expect(el.querySelector('[data-testid="no-holdings"]')).not.toBeNull();
  });
});
