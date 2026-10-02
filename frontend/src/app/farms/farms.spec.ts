import { TestBed } from '@angular/core/testing';
import { ActivatedRouteSnapshot, Router, RouterStateSnapshot, UrlTree, provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';

import { makeMe } from '../../testing/fixtures';
import { AuthService } from '../core/auth/auth.service';
import { permissionGuard } from '../core/auth/guards';
import { NAVIGATION, visibleNavigation } from '../core/navigation/nav.config';
import { ReadinessPanel } from '../shared/readiness-panel';
import { formatArea, isKml, polygonFromVertices } from '../shared/geo';
import { HISTORY_FIELDS, changedFields, toPayload } from './panels/history-fields';

describe('geometry helpers', () => {
  it('closes the ring and rejects degenerate shapes', () => {
    const poly = polygonFromVertices([[73.8, 20.0], [73.801, 20.0], [73.801, 20.001]]);
    expect(poly?.coordinates).toEqual([[[73.8, 20.0], [73.801, 20.0], [73.801, 20.001], [73.8, 20.0]]]);
    expect(polygonFromVertices([[1, 1], [1, 1], [2, 2]])).toBeNull();
    expect(polygonFromVertices([[1, 1], [2, 2]])).toBeNull();
  });

  it('formats areas and detects KML', () => {
    expect(formatArea('1.15850')).toBe('1.1585 ha');
    expect(formatArea(null)).toBe('—');
    expect(isKml('plot.kml', '')).toBe(true);
    expect(isKml('plot.txt', '<?xml version="1.0"?>\n<kml xmlns="x">')).toBe(true);
    expect(isKml('plot.geojson', '{"type":"Polygon"}')).toBe(false);
  });
});

describe('history form helpers', () => {
  it('turns blanks into null and keeps numbers numeric', () => {
    const p = toPayload(HISTORY_FIELDS.crop, { year: '2023', crop_name: 'Soybean', season: '', yield_quantity: '1.8', source: 'FARMER_CLAIM' });
    expect(p['year']).toBe(2023);
    expect(p['season']).toBeNull();
    expect(p['yield_quantity']).toBe(1.8);
    expect(p['irrigation']).toBeNull();
  });

  it('sends only changed fields when amending', () => {
    const before = { year: 2023, crop_name: 'Soybean', yield_quantity: '1.8', source: 'FARMER_CLAIM' };
    const after = toPayload(HISTORY_FIELDS.crop, { year: 2023, crop_name: 'Soybean', yield_quantity: '2.1', source: 'FARMER_CLAIM' });
    expect(changedFields(HISTORY_FIELDS.crop, before, after)).toEqual({ yield_quantity: 2.1 });
    expect(changedFields(HISTORY_FIELDS.crop, before, toPayload(HISTORY_FIELDS.crop, before))).toEqual({});
  });
});

describe('Phase 2 navigation and guards', () => {
  beforeEach(() => TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] }));

  it('shows field operations to staff and "My farm" to farmers only', () => {
    const staff = visibleNavigation(NAVIGATION, (c) => ['farmers.read', 'farms.read'].includes(c)).map((s) => s.title);
    expect(staff).toContain('Field operations');
    expect(staff).not.toContain('My farm');
    const farmer = visibleNavigation(NAVIGATION, (c) => c === 'farmers.self');
    expect(farmer.map((s) => s.title)).toEqual(['Overview', 'My farm']);
  });

  it('anyPermissions lets either staff or self-service through', () => {
    const auth = TestBed.inject(AuthService);
    const router = TestBed.inject(Router);
    const route = { data: { anyPermissions: ['farms.read', 'farmers.self'] } } as unknown as ActivatedRouteSnapshot;
    const run = () => TestBed.runInInjectionContext(() => permissionGuard(route, {} as RouterStateSnapshot));
    auth.me.set(makeMe(['farmers.self']));
    expect(run()).toBe(true);
    auth.me.set(makeMe(['users.read']));
    expect(router.serializeUrl(run() as UrlTree)).toBe('/forbidden');
  });
});

describe('ReadinessPanel', () => {
  it('lists missing requirements and marks optional ones', async () => {
    const f = TestBed.createComponent(ReadinessPanel);
    f.componentRef.setInput('readiness', [{ target: 'SUBMITTED', ready: false, items: [
      { key: 'boundary', label: 'A valid boundary is saved', done: true, required: true },
      { key: 'ownership', label: 'At least one current ownership / tenure record', done: false, required: true },
      { key: 'land', label: 'Land-use history recorded', done: false, required: false },
    ] }]);
    await f.whenStable();
    const text = (f.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Submitted');
    expect(text).toContain('not yet');
    expect(text).toContain('(recommended)');
    expect((f.nativeElement as HTMLElement).querySelectorAll('li.done').length).toBe(1);
  });
});
