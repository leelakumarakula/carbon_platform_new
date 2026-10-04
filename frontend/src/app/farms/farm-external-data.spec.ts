import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { ExternalDataView, ExternalObservation, Farm } from './farm.models';
import { FarmExternalDataPanel, monthlyWeather } from './panels/farm-external-data-panel';

const FARM = { id: 'f1', current_boundary: { version: 2 } } as unknown as Farm;
const URL = '/api/v1/farms/f1/external-data';
const SHA = 'a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2';

function obs(over: Partial<ExternalObservation>): ExternalObservation {
  return { id: 'o1', data_type: 'WEATHER', provider: 'Open-Meteo', dataset: 'ERA5 archive', period_start: '2025-01-01', period_end: '2025-02-28',
    latitude: 20.0057, longitude: 73.79175, boundary_version: 2, summary: {}, sha256: SHA, fetched_at: '2026-10-01T08:30:00Z',
    fetched_by_name: 'Field Agent', environment: 'LIVE', ...over };
}

function view(over: Partial<ExternalDataView> = {}): ExternalDataView {
  return { can_fetch: true, has_boundary: true, providers: [
    { data_type: 'WEATHER', provider: 'Open-Meteo', label: 'Weather', enabled: true, note: null },
    { data_type: 'SOIL', provider: 'ISRIC SoilGrids', label: 'Soil', enabled: true, note: null },
    { data_type: 'SATELLITE_NDVI', provider: 'Copernicus Sentinel-2', label: 'Satellite NDVI', enabled: false,
      note: 'Configure Copernicus credentials to enable' },
    { data_type: 'LAND_RECORD', provider: 'None', label: 'Land records', enabled: false,
      note: 'No public land-records API; upload land record documents in the Documents tab' },
  ], observations: [
    obs({ id: 'w1', summary: { daily: [
      { date: '2025-01-01', precipitation_mm: 2, temp_max_c: 30, temp_min_c: 14, et0_mm: 4 },
      { date: '2025-01-02', precipitation_mm: 3.5, temp_max_c: 32, temp_min_c: null, et0_mm: 4.2 },
      { date: '2025-02-01', precipitation_mm: null, temp_max_c: 33, temp_min_c: 16, et0_mm: 5 },
    ], totals: { days: 3, precipitation_mm: 5.5, et0_mm: 13.2, temp_max_mean_c: 31.7, temp_min_mean_c: 15 } } }),
    obs({ id: 's1', data_type: 'SOIL', provider: 'ISRIC SoilGrids', dataset: 'SoilGrids 2.0', period_start: null, period_end: null, environment: 'DEMO',
      summary: { layers: [{ property: 'soc', label: 'Soil organic carbon', depth: '0-5cm', value: 12.4, unit: 'g/kg' }] } }),
    obs({ id: 'n1', data_type: 'SATELLITE_NDVI', provider: 'Copernicus Sentinel-2', dataset: 'S2 L2A NDVI', summary: { max_cloud_pct: 30, intervals: [
      { from: '2025-01-01', to: '2025-01-31', mean: 0.42, min: 0.1, max: 0.7, stdev: 0.1, sample_count: 120, no_data_count: 20 },
      { from: '2025-02-01', to: '2025-02-28', mean: null, min: null, max: null, stdev: null, sample_count: 120, no_data_count: 120 },
    ] } }),
  ], ...over };
}

describe('External data helpers', () => {
  it('aggregates daily weather into months, skipping missing values', () => {
    const m = monthlyWeather(view().observations[0].summary.daily!);
    expect(m.map((r) => [r.label, r.days, r.rain, r.tmax, r.tmin])).toEqual([['Jan 2025', 2, 5.5, 31, 14], ['Feb 2025', 1, null, 33, 16]]);
  });
});

describe('FarmExternalDataPanel', () => {
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  async function render(v: ExternalDataView) {
    const f = TestBed.createComponent(FarmExternalDataPanel);
    f.componentRef.setInput('farm', FARM);
    f.detectChanges();
    http.expectOne(URL).flush(v);
    await f.whenStable();
    f.detectChanges();
    return f;
  }

  it('shows the reference-only notice, providers and one observation of each type', async () => {
    const el = (await render(view())).nativeElement as HTMLElement;
    const text = el.textContent ?? '';
    expect(text).toContain("It never changes a farm's status, verification or any calculation.");
    expect(el.querySelectorAll('[data-provider]').length).toBe(4);
    expect(text).toContain('Configure Copernicus credentials to enable');
    expect(text).toContain('No public land-records API');
    expect(el.querySelector<HTMLButtonElement>('[data-testid="fetch-satellite-ndvi"]')?.disabled).toBe(true);
    expect(el.querySelector('[data-testid="fetch-land-records"]')).toBeNull();
    expect(el.querySelector('[data-observation="WEATHER"]')).not.toBeNull();
    expect(el.querySelector('[data-testid="weather-totals"]')?.textContent).toContain('rainfall 5.5 mm');
    expect(text).toContain('Jan 2025');
    expect(el.querySelector('[data-testid="rain-chart"]')?.getAttribute('aria-label')).toContain('Monthly rainfall');
    expect(el.querySelector('[data-observation="SOIL"]')?.textContent).toContain('Soil organic carbon');
    expect(el.querySelector('[data-observation="SOIL"]')?.textContent).toContain('Demo');
    const ndvi = el.querySelector('[data-observation="SATELLITE_NDVI"]')?.textContent ?? '';
    expect(ndvi).toContain('0.420');
    expect(ndvi).toContain('100');                         // valid pixels = 120 - 20
    expect(el.querySelectorAll('[data-testid="ndvi-chart"] circle').length).toBe(1);   // null mean skipped
    expect(text).toContain(SHA.slice(0, 12));
    expect(text).not.toContain(SHA);
    expect(text).toContain('Field Agent');
  });

  it('fetches weather for the chosen period and reloads', async () => {
    const f = await render(view({ observations: [] }));
    const el = f.nativeElement as HTMLElement;
    const [from, to] = Array.from(el.querySelectorAll<HTMLInputElement>('[data-provider="WEATHER"] input[type="date"]'));
    from.value = '2025-01-01';
    from.dispatchEvent(new Event('input'));
    to.value = '2025-12-31';
    to.dispatchEvent(new Event('input'));
    f.detectChanges();
    el.querySelector<HTMLButtonElement>('[data-testid="fetch-weather"]')!.click();
    const req = http.expectOne(`${URL}/weather`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ period_start: '2025-01-01', period_end: '2025-12-31' });
    req.flush(obs({}));
    http.expectOne(URL).flush(view());
    await f.whenStable();
    f.detectChanges();
    expect(el.querySelector('[data-observation="WEATHER"]')).not.toBeNull();
  });

  it('asks for a boundary before fetching', async () => {
    const el = (await render(view({ has_boundary: false, observations: [] }))).nativeElement as HTMLElement;
    expect(el.querySelector('[data-testid="no-boundary"]')?.textContent).toContain('Save a boundary first');
    expect(el.querySelector('[data-testid="fetch-weather"]')).toBeNull();
    expect(el.querySelector('[data-testid="fetch-soil"]')).toBeNull();
  });
});
