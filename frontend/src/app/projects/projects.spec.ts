import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';

import { makeMe } from '../../testing/fixtures';
import { AuthService } from '../core/auth/auth.service';
import { NAVIGATION, visibleNavigation } from '../core/navigation/nav.config';
import { ProjectBoundaryPanel } from './panels/project-boundary-panel';
import { ProjectFarmsPanel } from './panels/project-farms-panel';
import { ProjectStandardPanel } from './panels/project-standard-panel';
import { ProjectTeamPanel } from './panels/project-team-panel';
import { ProjectCreatePage } from './project-create-page';
import { BoundaryView, EligibleFarm, Project, projectAction, projectBadge } from './project.models';
import { ProjectsListPage } from './projects-list-page';

const SQUARE = { type: 'Polygon' as const, coordinates: [[[73.8, 20], [73.801, 20], [73.801, 20.001], [73.8, 20.001], [73.8, 20]]] };

function project(over: Partial<Project> = {}): Project {
  return {
    id: 'p1', project_code: 'PRJ-2026-000001', name: 'Pilot', project_type: 'AGRICULTURAL_LAND_MANAGEMENT', organization_id: 'o1',
    organization_name: 'Dev A', country: 'IN', region: 'Nashik', status: 'DATA_COLLECTION', start_date: '2026-06-01', standard_name: null,
    activity_name: null, methodology_status: 'NOT_SELECTED', farm_count: 0, area_hectares: null, environment: 'LIVE', created_at: '2026-10-02T00:00:00Z',
    description: null, standard_id: null, activity_id: null, current_boundary_id: null, submitted_at: null, submitted_by: null,
    eligibility_reviewed_at: null, eligibility_reviewed_by: null, review_notes: null, updated_at: '2026-10-02T00:00:00Z',
    allowed_transitions: ['ELIGIBILITY_REVIEW', 'CLOSED'], readiness: [], can_manage: true, can_review: false, can_review_boundary: false,
    is_editable: true, counts: { participants: 1, carbon_rights: 0, documents: 0 }, ...over,
  };
}

describe('Projects: workflow labels and navigation', () => {
  it('maps every Phase 3 transition to its server action', () => {
    expect(projectAction('DRAFT', 'DATA_COLLECTION').endpoint).toBe('start-data-collection');
    expect(projectAction('DATA_COLLECTION', 'ELIGIBILITY_REVIEW').endpoint).toBe('submit');
    expect(projectAction('ELIGIBILITY_REVIEW', 'STANDARD_SELECTED').endpoint).toBe('approve-eligibility');
    expect(projectAction('ELIGIBILITY_REVIEW', 'DATA_COLLECTION')).toMatchObject({ endpoint: 'return', danger: true });
    expect(projectAction('ACTIVITY_SELECTED', 'DATA_COLLECTION').endpoint).toBe('reopen');
    expect(projectAction('STANDARD_SELECTED', 'ACTIVITY_SELECTED').endpoint).toBe('confirm-activity');
    expect(projectAction('DRAFT', 'CLOSED').endpoint).toBe('close');
    expect(projectBadge('ELIGIBILITY_REVIEW')).toBe('WARNING');
  });

  it('shows projects to staff, the catalog to catalog managers and "My projects" to farmers only', () => {
    const items = (codes: string[]) => visibleNavigation(NAVIGATION, (c) => codes.includes(c)).flatMap((s) => s.items.map((i) => i.label));
    expect(items(['projects.read'])).toContain('Projects');
    expect(items(['projects.read'])).not.toContain('Standards & activities');
    expect(items(['standards.manage'])).toContain('Standards & activities');
    expect(items(['farmers.self'])).toEqual(['Dashboard', 'My farmer profile', 'My farms', 'My projects']);
    expect(items([])).toEqual(['Dashboard']); // e.g. a buyer: no project navigation
  });
});

describe('Projects: screens', () => {
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
  });

  it('lists projects from the server with paging and sort', async () => {
    TestBed.inject(AuthService).me.set(makeMe(['projects.read']));
    const f = TestBed.createComponent(ProjectsListPage);
    f.detectChanges();
    const req = http.expectOne((r) => r.url === '/api/v1/projects');
    expect(req.request.params.get('sort')).toBe('-created_at');
    req.flush({ items: [{ ...project(), farm_count: 3, area_hectares: '4.5000', standard_name: 'Std A' }], total: 1, page: 1, page_size: 25 });
    await f.whenStable();
    const text = (f.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('PRJ-2026-000001');
    expect(text).toContain('Std A');
    expect(text).not.toContain('New project'); // no projects.manage
  });

  it('create page offers only organizations the user manages projects in and posts the form', async () => {
    TestBed.inject(AuthService).me.set(makeMe(['projects.manage', 'projects.read'], {
      roles: [{ id: 'g1', role_code: 'PROJECT_MANAGER', role_name: 'PM', scope: 'ORGANIZATION', organization_id: 'o1', organization_name: 'Dev A',
        assigned_at: '2026-01-01T00:00:00Z' }],
      organizations: [
        { organization_id: 'o1', organization_code: 'DEV-A', organization_name: 'Dev A', org_type: 'PROJECT_DEVELOPER', title: null, is_primary: true },
        { organization_id: 'o2', organization_code: 'LAB', organization_name: 'Lab', org_type: 'LABORATORY', title: null, is_primary: false },
      ],
    }));
    const f = TestBed.createComponent(ProjectCreatePage);
    f.detectChanges();
    const page = f.componentInstance as unknown as { orgs: () => { id: string }[]; form: { patchValue: (v: object) => void }; submit: () => void };
    expect(page.orgs().map((o) => o.id)).toEqual(['o1']);
    page.form.patchValue({ name: 'Nashik pilot', region: 'Nashik' });
    page.submit();
    const req = http.expectOne('/api/v1/projects');
    expect(req.request.body).toMatchObject({ organization_id: 'o1', name: 'Nashik pilot', project_type: 'AGRICULTURAL_LAND_MANAGEMENT', country: 'IN' });
  });

  it('farm selection: ineligible farms are disabled and conflicts must be acknowledged', async () => {
    const f = TestBed.createComponent(ProjectFarmsPanel);
    f.componentRef.setInput('project', project());
    f.detectChanges();
    http.expectOne('/api/v1/projects/p1/farms').flush([]);
    const eligible: EligibleFarm[] = [
      { farm_id: 'f1', farm_code: 'FARM-1', farm_name: 'North', farmer_id: 'a', farmer_name: 'Asha', farmer_status: 'ACTIVE', farm_status: 'VERIFIED',
        area_hectares: '1.2', eligible: true, reasons: [], in_other_projects: ['PRJ-2026-000009'],
        conflicts: [{ kind: 'OTHER_PROJECT_PARTICIPATION', status: 'DATA_COLLECTION', detail: 'Already participating in PRJ-2026-000009',
          other_farm_code: null, other_project_code: 'PRJ-2026-000009', overlap_area_m2: null }] },
      { farm_id: 'f2', farm_code: 'FARM-2', farm_name: 'South', farmer_id: 'b', farmer_name: 'Ravi', farmer_status: 'KYC_VERIFIED', farm_status: 'DRAFT',
        area_hectares: '0.8', eligible: false, reasons: ['The farm is DRAFT, not VERIFIED.'], in_other_projects: [], conflicts: [] },
    ];
    http.expectOne('/api/v1/projects/p1/farms/eligible').flush(eligible);
    await f.whenStable();
    const panel = f.componentInstance as unknown as { form: { patchValue: (v: object) => void }; add: () => void };
    panel.form.patchValue({ farm_id: 'f1', reference: 'Clause 4, agreement AGR-1' });
    f.detectChanges();
    await f.whenStable();
    expect((f.nativeElement as HTMLElement).textContent).toContain('Already participating in PRJ-2026-000009');
    panel.form.patchValue({ acknowledge_conflicts: true, conflict_notes: 'Different practice' });
    panel.add();
    const req = http.expectOne('/api/v1/projects/p1/farms');
    expect(req.request.body).toMatchObject({ farm_id: 'f1', acknowledge_conflicts: true, conflict_notes: 'Different practice',
      carbon_rights: { holder_type: 'FARMER', reference: 'Clause 4, agreement AGR-1' } });
  });

  it('team panel only offers roles the person already holds', async () => {
    const f = TestBed.createComponent(ProjectTeamPanel);
    f.componentRef.setInput('project', project());
    f.detectChanges();
    http.expectOne('/api/v1/projects/p1/participants').flush([]);
    http.expectOne('/api/v1/projects/p1/participants/candidates').flush([
      { user_id: 'u2', full_name: 'Gita GIS', email: 'g@x', roles: ['GIS_SPECIALIST'] },
      { user_id: 'u3', full_name: 'Quinn QA', email: 'q@x', roles: ['QA_OFFICER', 'MRV_MANAGER'] }]);
    await f.whenStable();
    const panel = f.componentInstance as unknown as { form: { controls: { user_id: { setValue: (v: string) => void };
      project_role: { value: string } } }; rolesFor: () => string[] };
    panel.form.controls.user_id.setValue('u2');
    expect(panel.rolesFor()).toEqual(['GIS_SPECIALIST']);
    expect(panel.form.controls.project_role.value).toBe('GIS_SPECIALIST');
    panel.form.controls.user_id.setValue('u3');
    expect(panel.rolesFor()).toEqual(['MRV_MANAGER', 'QA_OFFICER']);
  });

  it('standard panel: activity needs a standard; methodology is not selected in this phase', async () => {
    const f = TestBed.createComponent(ProjectStandardPanel);
    f.componentRef.setInput('project', project());
    f.detectChanges();
    http.expectOne('/api/v1/projects/p1/standards').flush({ current: null, history: [], available: [
      { id: 's1', code: 'S1', name: 'Standard One', owner_name: null, program_type: 'VOLUNTARY', description: null, source_url: null, status: 'ACTIVE',
        environment: 'LIVE', activity_ids: [] }] });
    http.expectOne('/api/v1/projects/p1/activities').flush({ current: null, history: [], available: [], methodology_status: 'NOT_SELECTED' });
    await f.whenStable();
    const text = (f.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Select a standard first.');
    expect(text).toContain('Methodology: Not selected');
    expect(text).toContain('not part of this phase');
  });

  it('boundary panel shows SQL Server area, the stale warning, and review only when allowed', async () => {
    const view = (over: Partial<BoundaryView> = {}): BoundaryView => ({
      current: { id: 'b1', version: 2, status: 'CURRENT', geojson: SQUARE, area_m2: '12345', area_hectares: '1.2345', sum_farm_area_hectares: '1.5000',
        internal_overlap_hectares: '0.2655', farm_count: 2, is_valid: true, validation_notes: null, computed_at: '2026-10-02T00:00:00Z',
        review_status: 'PENDING', reviewed_at: null, review_notes: null },
      stale: false, farms: [], project_overlaps: [{ other_project_id: null, other_project_code: null, other_project_visible: false,
        same_organization: false, overlap_area_m2: '40' }], versions: [], can_recompute: true, can_review: true, ...over });
    const f = TestBed.createComponent(ProjectBoundaryPanel);
    f.componentRef.setInput('project', project());
    f.detectChanges();
    http.expectOne('/api/v1/projects/p1/boundary').flush(view());
    await f.whenStable();
    let el = f.nativeElement as HTMLElement;
    expect(el.textContent).toContain('1.2345 ha');
    expect(el.textContent).toContain('details restricted');
    expect(Array.from(el.querySelectorAll('button')).map((b) => b.textContent?.trim())).toContain('Accept boundary');
    (f.componentInstance as unknown as { view: { set: (v: BoundaryView) => void } }).view.set(view({ stale: true }));
    f.detectChanges();
    await f.whenStable();
    el = f.nativeElement as HTMLElement;
    expect(el.textContent).toContain('Recompute before review');
    expect(Array.from(el.querySelectorAll('button')).map((b) => b.textContent?.trim())).not.toContain('Accept boundary');
    http.match(() => true); // map tile config request (not under test)
  });
});
