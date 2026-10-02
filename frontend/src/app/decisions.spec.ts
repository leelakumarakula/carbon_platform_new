import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';

import { ClientConfig, ClientConfigService, FALLBACK_MAP } from './core/api/client-config.service';
import { NAVIGATION, visibleNavigation } from './core/navigation/nav.config';
import { Farm, Overlap } from './farms/farm.models';
import { FarmOverlapsPanel } from './farms/panels/farm-overlaps-panel';

/** Phase 2 decisions: D3 consent configuration nav, D5 cross-org overlap authorization, D6 configurable basemap. */
describe('Phase 2 decisions', () => {
  beforeEach(() =>
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] }));

  it('D6: loads the basemap from server configuration once, with a dev fallback on failure', () => {
    const svc = TestBed.inject(ClientConfigService);
    const http = TestBed.inject(HttpTestingController);
    const seen: ClientConfig[] = [];
    svc.config().subscribe((c) => seen.push(c));
    svc.config().subscribe((c) => seen.push(c));
    const req = http.expectOne('/api/v1/config/client');
    req.flush({ map: { provider: 'acme', tile_url: 'https://tiles.example/{z}/{x}/{y}.png', attribution: 'Acme', max_zoom: 18, subdomains: [] } });
    expect(seen.map((c) => c.map.provider)).toEqual(['acme', 'acme']);
    http.verify(); // cached: one request for both subscribers
  });

  it('D6: falls back to the development tile source when the endpoint fails', () => {
    const svc = TestBed.inject(ClientConfigService);
    const http = TestBed.inject(HttpTestingController);
    let got: ClientConfig | undefined;
    svc.config().subscribe((c) => (got = c));
    http.expectOne('/api/v1/config/client').flush('down', { status: 503, statusText: 'Unavailable' });
    expect(got?.map).toEqual(FALLBACK_MAP);
  });

  it('D3: consent types are an admin item for consent configurers only', () => {
    const titles = (codes: string[]) =>
      visibleNavigation(NAVIGATION, (c) => codes.includes(c)).flatMap((s) => s.items.map((i) => i.label));
    expect(titles(['consents.configure'])).toContain('Consent types');
    expect(titles(['farmers.read', 'farms.read'])).not.toContain('Consent types');
  });

  it('D5: a cross-organization overlap shows no Clear button unless the server allows it', async () => {
    const overlap = (over: Partial<Overlap>): Overlap => ({
      id: 'o1', farm_id: 'f1', other_farm_id: null, other_farm_code: null, other_farm_visible: false, relation: 'PARTIAL',
      overlap_area_m2: '120', overlap_pct_of_farm: '10', overlap_pct_of_other: '12', same_farmer: false, same_organization: false,
      status: 'OPEN', detected_at: '2026-10-02T10:00:00Z', resolved_at: null, resolution_notes: null, other_geojson: null,
      can_confirm: true, can_clear: false, ...over,
    });
    const f = TestBed.createComponent(FarmOverlapsPanel);
    f.componentRef.setInput('farm', { id: 'f1', can_review: true } as Farm);
    f.componentRef.setInput('overlaps', [overlap({})]);
    await f.whenStable();
    let el = f.nativeElement as HTMLElement;
    const buttons = () => Array.from(el.querySelectorAll('button')).map((b) => b.textContent?.trim());
    expect(buttons()).toEqual(['Confirm conflict']);
    expect(el.textContent).toContain('Only a Platform GIS Specialist can clear');

    f.componentRef.setInput('overlaps', [overlap({ can_clear: true, other_farm_visible: true, other_farm_code: 'FARM-2026-000002' })]);
    await f.whenStable();
    el = f.nativeElement as HTMLElement;
    expect(buttons()).toEqual(['Confirm conflict', 'Clear']);
  });
});
