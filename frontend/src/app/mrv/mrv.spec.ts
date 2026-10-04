import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { AuthService } from '../core/auth/auth.service';
import { NAVIGATION, visibleNavigation } from '../core/navigation/nav.config';
import { FieldDashboardPage } from './field-dashboard-page';
import { MrvDashboardPage } from './mrv-dashboard-page';
import { MrvDatasetPage } from './mrv-dataset-page';
import { FieldCollection, Measurement, QaView, SamplingPoint, Stratum, capturableInMrv, collectionMissing, dataRoleLabel, mrvBadge, parseMeasurementValue } from './mrv.models';
import { MrvStrataPanel } from './panels/mrv-strata-panel';

function point(over: Partial<SamplingPoint> = {}): SamplingPoint {
  return { id: 'pt1', point_code: 'SP-2026-000001', project_id: 'p1', monitoring_period_id: 'mp1', design_version_id: 'dv1', stratum_id: 's1',
    stratum_code: 'S1', farm_id: 'f1', farm_code: 'FARM-1', farm_name: 'North', sequence: 1, latitude: '20.0000100', longitude: '73.8000100',
    planned_depth_top_cm: '0.0', planned_depth_bottom_cm: '30.0', status: 'ASSIGNED', assigned_collector_id: 'u1', assigned_collector_name: 'Collector',
    planned_date: '2026-09-15', status_reason: null, pending_relocation: false, collection_id: null, collection_status: null, ...over };
}

function collection(over: Partial<FieldCollection> = {}): FieldCollection {
  return { id: 'c1', collection_code: 'FIELD-2026-000145', sampling_point_id: 'pt1', point_code: 'SP-2026-000001', monitoring_period_id: 'mp1',
    project_id: 'p1', farm_id: 'f1', collector_id: 'u1', collector_name: 'Collector', version: 1, supersedes_id: null, status: 'IN_PROGRESS',
    collected_at: '2026-09-15T09:00:00Z', gps_latitude: '20.00001', gps_longitude: '73.80001', gps_accuracy_m: '4', distance_from_point_m: '2.1',
    gps_inside_farm: true, deviation_note: null, actual_depth_top_cm: '0', actual_depth_bottom_cm: '30', planned_depth_top_cm: '0',
    planned_depth_bottom_cm: '30', sample_quantity: '0.5', sample_unit: 'kg', observations: null, notes: null,
    checklist: { location_confirmed: true, depth_measured: true, sample_labelled: true, photo_taken: true },
    required_checklist: ['location_confirmed', 'depth_measured', 'sample_labelled', 'photo_taken'], correction_reason: null,
    checklist_version: 'PLATFORM-DEFAULT-1', checklist_items: [{ key: 'depth_measured', label: 'Sampling depth measured' }], gps_tolerance_m: '30.0',
    min_photos: 1, field_rules: null, analysis_status: null,
    created_at: '2026-09-15T08:00:00Z', submitted_at: null, reviewed_at: null, review_notes: null, evidence_count: 1, can_edit: true, can_review: false,
    ...over };
}

function stratum(over: Partial<Stratum> = {}): Stratum {
  return { id: 's1', record_id: 'r1', project_id: 'p1', version: 1, is_current: true, code: 'S1', name: 'Black soil', description: null, geojson: null,
    area_hectares: '5.2', farm_ids: ['f1'], farm_codes: ['FARM-1'], characteristics: [{ characteristic: 'SOIL_TEXTURE', value: 'Clay' }],
    missing_required_characteristics: [], role: 'PROJECT', linked_strata: [], source: 'FARM_GROUPING', status: 'APPROVED', change_reason: null,
    created_by: 'u1', created_at: '2026-10-01T00:00:00Z', approved_at: '2026-10-02T00:00:00Z', ...over };
}

describe('MRV helpers', () => {
  it('maps statuses to badge tones', () => {
    expect(mrvBadge('APPROVED')).toBe('ACTIVE');
    expect(mrvBadge('CONFIGURATION_REQUIRED')).toBe('WARNING');
    expect(mrvBadge('REJECTED')).toBe('FAILED');
    expect(mrvBadge('SUPERSEDED')).toBe('ARCHIVED');
  });

  it('lists what a collector still has to do before submitting', () => {
    expect(collectionMissing(collection(), 0)).toEqual([]);
    const far = collection({ distance_from_point_m: '120.5', evidence_count: 0, checklist: { location_confirmed: true } });
    const missing = collectionMissing(far, 0);
    expect(missing.join(' ')).toContain('a field photo');
    expect(missing.join(' ')).toContain('Sampling depth measured');
    expect(missing.join(' ')).toContain('GPS deviation');
    expect(collectionMissing({ ...far, deviation_note: 'flooded', checklist: collection().checklist }, 1)).toEqual([]);
    expect(collectionMissing(collection({ gps_inside_farm: false }), 1)).toEqual(['a note explaining the GPS deviation']);
  });

  it('asks for probe diameter and number of cores only when the methodology requires them', () => {
    expect(collectionMissing(collection(), 1)).toEqual([]);
    expect(collectionMissing(collection({ core_details_required: true }), 1)).toEqual(['probe diameter and number of cores']);
    expect(collectionMissing(collection({ core_details_required: true, probe_diameter_mm: '21.50', cores_count: 4 }), 1)).toEqual([]);
  });

  it('uses the rules frozen on the record (decisions S1, S2), not hard-coded values', () => {
    // a methodology tolerance of 10 m: 20 m away needs a note even though the platform default is 30 m
    expect(collectionMissing(collection({ gps_tolerance_m: '10.0', distance_from_point_m: '20.0' }), 1)).toEqual(['a note explaining the GPS deviation']);
    expect(collectionMissing(collection({ min_photos: 2, evidence_count: 1 }), 1)).toEqual(['1 more field photo(s) (2 required)']);
    const custom = collection({ required_checklist: ['soil_moisture_noted'], checklist: {}, checklist_items: [{ key: 'soil_moisture_noted', label: 'Soil moisture noted' }] });
    expect(collectionMissing(custom, 1)).toEqual(['checklist (Soil moisture noted)']);
  });

  it('offers only FIELD / FIELD_ACTIVITY / project measurements for MRV entry (decision V2-A, never from the unit)', () => {
    const m = (measurement_source: Measurement['measurement_source'], unit: string | null) => ({ measurement_source, unit } as Measurement);
    expect(capturableInMrv(m('LABORATORY', null))).toBe(false);
    expect(capturableInMrv(m('UNCLASSIFIED', 'kg/ha'))).toBe(false);
    expect(capturableInMrv(m('FIELD_ACTIVITY', 't C/ha'))).toBe(true);
    expect(capturableInMrv(m('FIELD', 'cm'))).toBe(true);
    expect(capturableInMrv(m(null, null))).toBe(true);
  });

  it('labels user-created measurements as supplementary, never authoritative (decision V2-B)', () => {
    expect(dataRoleLabel('SUPPLEMENTARY_OBSERVATION')).toBe('Supplementary (not authoritative)');
    expect(dataRoleLabel('LABORATORY_PARAMETER')).toContain('approved lab result only');
    expect(dataRoleLabel('METHODOLOGY_PARAMETER')).toBe('Methodology (authoritative)');
  });

  it('parses typed measurement values', () => {
    const m = { value_type: 'NUMBER' } as Measurement;
    expect(parseMeasurementValue(m, '12.5')).toBe(12.5);
    expect(parseMeasurementValue({ ...m, value_type: 'BOOLEAN' }, 'true')).toBe(true);
    expect(parseMeasurementValue({ ...m, value_type: 'CHOICE' }, 'NO_TILL')).toBe('NO_TILL');
    expect(parseMeasurementValue(m, ' ')).toBeNull();
  });

  it('shows MRV to readers and Field work to collectors; buyers and farmers see neither', () => {
    const items = (codes: string[]) => visibleNavigation(NAVIGATION, (c) => codes.includes(c)).flatMap((s) => s.items.map((i) => i.label));
    expect(items(['mrv.read'])).toContain('MRV');
    expect(items(['sampling.collect'])).toContain('Field work');
    expect(items(['sampling.collect'])).not.toContain('MRV');
    expect(items([])).toEqual(['Dashboard']);
    expect(items(['farmers.self'])).toHaveLength(5); // farmer navigation: + My payouts (Phase 11)
  });
});

describe('MRV screens', () => {
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
  });

  it('strata panel separates control sites and tracks the VM0042 control-site requirements', () => {
    const f = TestBed.createComponent(MrvStrataPanel);
    f.componentRef.setInput('projectId', 'p1');
    f.componentRef.setInput('strata', [
      stratum(),
      stratum({ id: 's2', record_id: 'r2', code: 'S2', name: 'Red soil', farm_ids: ['f2'], farm_codes: ['FARM-2'] }),
      stratum({ id: 'c1', record_id: 'rc1', code: 'C1', name: 'Control north', role: 'CONTROL', farm_ids: ['f9'], farm_codes: ['FARM-9'],
        linked_strata: [{ record_id: 'r1', code: 'S1' }] }),
    ]);
    f.detectChanges();
    const text = (f.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Control sites');
    expect(text).toContain('Represents S1');
    expect(text).toContain('1 of at least 3');
    expect(text).toContain('No control site yet for S2');
    expect(text).toContain('Soil texture: Clay');
  });

  it('MRV dashboard lists projects with a locked methodology', async () => {
    const f = TestBed.createComponent(MrvDashboardPage);
    f.detectChanges();
    http.expectOne('/api/v1/mrv/projects').flush([{ project_id: 'p1', project_code: 'PRJ-2026-000001', project_name: 'Niphad', project_status: 'MONITORING',
      organization_name: 'Dev A', methodology_label: 'DEMO-ALM-SOC v1.0', environment: 'DEMO', approved_plan_version: 1, plan_count: 1, period_count: 1,
      open_period: 'Monitoring 1', point_count: 6, collected_count: 3, dataset_status: 'COLLECTING' }]);
    await f.whenStable();
    f.detectChanges();
    const text = (f.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('PRJ-2026-000001');
    expect(text).toContain('3 / 6 points collected');
    expect(text).toContain('v1 approved');
  });

  it('field dashboard shows only assigned work with a start button', async () => {
    const f = TestBed.createComponent(FieldDashboardPage);
    f.detectChanges();
    http.expectOne((r) => r.url === '/api/v1/mrv/sampling-points' && r.params.get('mine') === 'true')
      .flush([point(), point({ id: 'pt2', point_code: 'SP-2026-000002', status: 'COLLECTED' })]);
    http.expectOne((r) => r.url === '/api/v1/mrv/field-collections').flush([]);
    await f.whenStable();
    f.detectChanges();
    const el = f.nativeElement as HTMLElement;
    expect(el.querySelector('[data-point="SP-2026-000001"]')).not.toBeNull();
    expect(el.querySelector('[data-point="SP-2026-000002"]')).toBeNull();
    expect(el.querySelector('[data-testid="start-collection"]')).not.toBeNull();
    expect(el.textContent).not.toContain('Approve');
  });

  it('dataset QA page shows checks and offers approval only when allowed', async () => {
    TestBed.inject(AuthService);
    const ds = { id: 'd1', dataset_code: 'MRV-2026-P001-M1-V1', project_id: 'p1', project_code: 'PRJ', monitoring_period_id: 'mp1',
      monitoring_period_name: 'M1', plan_version: 1, methodology_label: 'X v1', version: 1, supersedes_id: null, status: 'QA_REVIEW' as const,
      snapshot_summary: { sampling_points: 4 }, snapshot_sha256: 'ab'.repeat(32), configuration_gaps: [], notes: null, status_reason: null,
      environment: 'LIVE', created_at: '2026-10-01T00:00:00Z', submitted_at: '2026-10-01T00:00:00Z', approved_at: null, allowed_actions: [] };
    const view = (over: Partial<QaView>): QaView => ({ dataset: ds, reviews: [], can_start: false, can_complete: true, can_approve: false,
      checks: [{ key: 'sampling_completeness', label: 'All points collected', result: 'FAIL', details: ['SP-2026-000004 not collected'] }], ...over });
    for (const [v, approvable] of [[view({}), false], [view({ can_approve: true, checks: [] }), true]] as const) {
      const f = TestBed.createComponent(MrvDatasetPage);
      f.componentRef.setInput('id', 'd1');
      f.detectChanges();
      http.expectOne('/api/v1/mrv/qa/d1').flush(v);
      await f.whenStable();
      f.detectChanges();
      const el = f.nativeElement as HTMLElement;
      expect(!!el.querySelector('[data-testid="approve-dataset"]')).toBe(approvable);
      if (!approvable) expect(el.textContent).toContain('SP-2026-000004 not collected');
      f.destroy();
    }
  });
});
