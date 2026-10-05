import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { Farm } from './farm.models';
import { FarmOwnershipPanel } from './panels/farm-ownership-panel';

const doc = (id: string, category: string, title: string, created: string) => ({ id, entity_type: 'farm', entity_id: 'f1', category, title,
  sensitivity: 'INTERNAL', status: 'ACTIVE', current_version: 1, environment: 'LIVE', created_at: created, versions: [], scan_state: 'NOT_SCANNED' });
const FARM = { id: 'f1', farmer_id: 'fr1', status: 'DRAFT', can_manage: true, can_review: false, documents: [
  doc('d1', 'OTHER', 'Old scan', '2026-09-01T00:00:00Z'), doc('d2', 'FIELD_PHOTO', 'Field photo', '2026-10-02T00:00:00Z'),
  doc('d3', 'LAND_RECORD', '7/12 extract - Survey 445', '2026-10-01T00:00:00Z'),
] } as unknown as Farm;
const OWN = '/api/v1/farms/f1/ownership';

describe('FarmOwnershipPanel', () => {
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it('records ownership with the land record as evidence and shows which document backs each record', async () => {
    const f = TestBed.createComponent(FarmOwnershipPanel);
    f.componentRef.setInput('farm', FARM);
    f.detectChanges();
    http.expectOne(OWN).flush([{ id: 'o0', owner_type: 'INDIVIDUAL', owner_farmer_id: null, owner_name: 'Asha Patil', operator_relationship: 'OWNER',
      ownership_share_pct: null, title_reference: '7/12-132016', evidence_document_id: null, valid_from: null, valid_to: null, end_reason: null,
      is_current: true, verification_status: 'VERIFIED', review_notes: 'title matches', recorded_at: '2026-10-01T00:00:00Z' }]);
    await f.whenStable();
    f.detectChanges();
    const el = f.nativeElement as HTMLElement;
    expect(el.querySelector('[data-testid="ownership-evidence"]')?.textContent).toContain('no document linked');
    const cmp = f.componentInstance as unknown as { form: { controls: Record<string, { value: unknown; setValue(v: unknown): void }> };
      evidenceDocs(): { id: string }[]; add(): void };
    expect(cmp.evidenceDocs().map((d) => d.id)).toEqual(['d3', 'd1']);          // land record first; field photos are not evidence
    expect(cmp.form.controls['evidence_document_id'].value).toBe('d3');         // preselected
    cmp.form.controls['title_reference'].setValue('7/12 Survey 445');
    cmp.add();
    const req = http.expectOne((r) => r.method === 'POST' && r.url === OWN);
    expect(req.request.body).toMatchObject({ owner_type: 'FARMER', owner_farmer_id: 'fr1', title_reference: '7/12 Survey 445', evidence_document_id: 'd3' });
    req.flush({});
    http.expectOne(OWN).flush([]);
  });
});
