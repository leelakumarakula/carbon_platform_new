import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { SecurityDocument } from '../../core/api/documents.api';
import { Me } from '../../core/auth/auth.models';
import { AuthService } from '../../core/auth/auth.service';
import { NAVIGATION, visibleNavigation } from '../../core/navigation/nav.config';
import { DocumentInfo } from '../../farmer/farmer.models';
import { DocumentsPanel } from '../../shared/documents-panel';
import { QuarantinePage, scanBadge } from './quarantine-page';

function signIn(permissions: string[]): void {
  TestBed.inject(AuthService).me.set({ user: { id: 'u1', email: 'x@test.example', full_name: 'X', environment: 'LIVE', must_change_password: false },
    permissions } as unknown as Me);
}

function doc(over: Partial<DocumentInfo> = {}): DocumentInfo {
  return { id: 'd1', entity_type: 'farmer', entity_id: 'f1', category: 'LAND_RECORD', title: 'Land record', sensitivity: 'INTERNAL',
    status: 'ACTIVE', current_version: 1, environment: 'LIVE', created_at: '2026-10-03T00:00:00Z', scan_state: 'CLEAN',
    versions: [{ version: 1, file_name: 'a.pdf', mime_type: 'application/pdf', size_bytes: 2048, checksum_sha256: 'ab'.repeat(32),
      scan_status: 'CLEAN', uploaded_by: null, uploaded_at: '2026-10-03T00:00:00Z' }], ...over };
}

function secDoc(over: Partial<SecurityDocument> = {}): SecurityDocument {
  return { ...doc({ status: 'QUARANTINED', scan_state: 'INFECTED' }), organization_id: 'o1',
    latest_scan: { id: 's1', document_id: 'd1', document_version_id: 'v1', checksum_sha256: 'ab'.repeat(32), result: 'INFECTED', provider: 'vendor',
      engine_version: '1.0', threat_name: 'EICAR-Test-File', error_code: null, detail: null, trigger_type: 'RESCAN', background_job_id: 'j1',
      actor_id: null, duration_ms: 12, scanned_at: '2026-10-03T01:00:00Z' }, ...over };
}

describe('Document quarantine (Phase 12B)', () => {
  it('is in the Security menu for security.read only', () => {
    const labels = (perms: string[]) => visibleNavigation(NAVIGATION, (c) => perms.includes(c)).flatMap((s) => s.items.map((i) => i.label));
    expect(labels(['security.read'])).toContain('Document quarantine');
    for (const perms of [['users.read'], ['farmers.read', 'farmers.manage'], ['jobs.read']]) expect(labels(perms)).not.toContain('Document quarantine');
    expect(scanBadge('CLEAN')).toBe('ACTIVE');
    expect(scanBadge('INFECTED')).toBe('CRITICAL');
    expect(scanBadge('NOT_SCANNED')).toBe('WARNING');                 // a test-signature result is never shown as clean
  });

  describe('with HTTP', () => {
    let http: HttpTestingController;
    beforeEach(() => {
      TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
      http = TestBed.inject(HttpTestingController);
    });
    afterEach(() => http.verify());

    it('lists quarantined documents with history; read-only users get no actions', async () => {
      signIn(['security.read']);
      const f = TestBed.createComponent(QuarantinePage);
      f.detectChanges();
      http.expectOne('/api/v1/evidence/documents/quarantined').flush([secDoc()]);
      await f.whenStable();
      f.detectChanges();
      const el = f.nativeElement as HTMLElement;
      expect(el.querySelector('[data-doc="d1"]')?.textContent).toContain('EICAR-Test-File');
      expect(el.querySelectorAll('[data-doc="d1"] button').length).toBe(0);
      (el.querySelector('[data-doc="d1"] a') as HTMLAnchorElement).click();
      http.expectOne('/api/v1/evidence/documents/d1/scans').flush([secDoc().latest_scan]);
      await f.whenStable();
      f.detectChanges();
      expect(el.querySelector('[data-testid="scan-history"]')?.textContent).toContain('INFECTED');
    });

    it('security.manage can queue a rescan (never a release by itself)', async () => {
      signIn(['security.read', 'security.manage']);
      const f = TestBed.createComponent(QuarantinePage);
      f.detectChanges();
      http.expectOne('/api/v1/evidence/documents/quarantined').flush([secDoc()]);
      await f.whenStable();
      f.detectChanges();
      const buttons = [...(f.nativeElement as HTMLElement).querySelectorAll('[data-doc="d1"] button')] as HTMLButtonElement[];
      expect(buttons.map((b) => b.textContent?.trim())).toEqual(['Rescan', 'Release']);
      buttons[0].click();
      const req = http.expectOne('/api/v1/evidence/documents/d1/rescan');
      expect(req.request.method).toBe('POST');
      req.flush({ job_id: 'j9' });
      http.expectOne('/api/v1/evidence/documents/quarantined').flush([]);
    });

    it('the documents panel shows scan state and hides download for quarantined files', async () => {
      const f = TestBed.createComponent(DocumentsPanel);
      f.componentRef.setInput('documents', [doc(), doc({ id: 'd2', scan_state: 'NOT_SCANNED' }),
        doc({ id: 'd3', status: 'QUARANTINED', scan_state: 'SCANNER_UNAVAILABLE' })]);
      f.detectChanges();
      const el = f.nativeElement as HTMLElement;
      const rows = [...el.querySelectorAll('.doc')];
      expect(rows[0].querySelector('[data-testid="scan-clean"]')).toBeTruthy();
      expect(rows[1].querySelector('[data-testid="scan-not-scanned"]')).toBeTruthy();
      expect(rows[1].querySelector('[data-testid="scan-clean"]')).toBeNull();
      expect(rows[2].querySelector('[data-testid="scan-quarantined"]')?.textContent).toContain('awaiting scan');
      expect(rows[2].querySelector('button[aria-label="Download"]')).toBeNull();
      expect(rows[0].querySelector('button[aria-label="Download"]')).toBeTruthy();
    });
  });
});
