import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatTabsModule } from '@angular/material/tabs';
import { ActivatedRoute } from '@angular/router';

import { ApiError } from '../core/api/api.models';
import { NotifyService } from '../core/notify.service';
import { DocumentInfo, label } from '../farmer/farmer.models';
import { DocumentsPanel, UploadFn } from '../shared/documents-panel';
import { GeoMap, MapLayer } from '../shared/geo-map';
import { formatArea } from '../shared/geo';
import { PageHeader } from '../shared/page-header';
import { ReadinessPanel } from '../shared/readiness-panel';
import { askReason } from '../shared/reason-dialog';
import { runAction } from '../shared/run-action';
import { StateView } from '../shared/state-view';
import { StatusBadge } from '../shared/status-badge';
import { ProjectBoundaryPanel } from './panels/project-boundary-panel';
import { ProjectFarmsPanel } from './panels/project-farms-panel';
import { ProjectHistoryPanel } from './panels/project-history-panel';
import { ProjectPeriodsPanel } from './panels/project-periods-panel';
import { ProjectRightsPanel } from './panels/project-rights-panel';
import { ProjectStandardPanel } from './panels/project-standard-panel';
import { ProjectTeamPanel } from './panels/project-team-panel';
import { BoundaryView, PROJECT_DOC_CATEGORIES, Project, ProjectStatus, projectAction, projectBadge } from './project.models';
import { ProjectsApi } from './projects.api';

const TABS = ['overview', 'farms', 'team', 'boundary', 'standard', 'periods', 'rights', 'documents', 'history'];

@Component({
  selector: 'app-project-detail-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, MatTabsModule, MatButtonModule, PageHeader, StateView, StatusBadge, ReadinessPanel, DocumentsPanel, GeoMap,
    ProjectFarmsPanel, ProjectTeamPanel, ProjectBoundaryPanel, ProjectStandardPanel, ProjectPeriodsPanel, ProjectRightsPanel, ProjectHistoryPanel],
  template: `
    <app-state-view [loading]="loading()" [error]="error()" (retry)="load()" />
    @if (project(); as p) {
      <app-page-header [title]="p.name" [subtitle]="p.project_code + ' · ' + (p.organization_name ?? '') + (p.region ? ' · ' + p.region : '')"
                       backLink="/projects" backLabel="Projects">
        @for (a of actions(); track a.target) {
          <button mat-stroked-button type="button" [class.danger]="a.danger" [disabled]="busy()" (click)="transition(a.target)">{{ a.label }}</button>
        }
      </app-page-header>
      <div class="status-row">
        <app-status-badge [status]="badge(p.status)" [text]="label(p.status)" />
        <app-status-badge status="INFO" [text]="'Methodology: ' + label(p.methodology_status)" />
        @if (p.environment === 'DEMO') { <app-status-badge status="DEMO" /> }
      </div>
      <mat-tab-group animationDuration="0ms" mat-stretch-tabs="false" [selectedIndex]="tab()" (selectedIndexChange)="tab.set($event)">
        <mat-tab label="Overview">
          <ng-template matTabContent>
            <div class="tab-body overview">
              <app-geo-map [layers]="layers()" height="340px" />
              <div>
                <dl class="kv">
                  <dt>Type</dt><dd>{{ label(p.project_type) }}</dd>
                  <dt>Country / region</dt><dd>{{ p.country }}{{ p.region ? ' · ' + p.region : '' }}</dd>
                  <dt>Planned start</dt><dd>{{ p.start_date ?? '—' }}</dd>
                  <dt>Project area</dt><dd>{{ area(p.area_hectares) }} <span class="muted small">({{ p.farm_count }} farm(s), SQL Server)</span></dd>
                  <dt>Standard / route</dt><dd>{{ p.standard_name ?? '—' }}</dd>
                  <dt>Activity</dt><dd>{{ p.activity_name ?? '—' }}</dd>
                  <dt>Team</dt><dd>{{ p.counts['participants'] }} · carbon-rights records {{ p.counts['carbon_rights'] }} · documents {{ p.counts['documents'] }}</dd>
                  <dt>Submitted</dt><dd>{{ p.submitted_at ? (p.submitted_at | date: 'medium') : '—' }}</dd>
                  <dt>Eligibility review</dt><dd>{{ p.eligibility_reviewed_at ? (p.eligibility_reviewed_at | date: 'medium') : '—' }}</dd>
                  @if (p.review_notes) { <dt>Review notes</dt><dd>{{ p.review_notes }}</dd> }
                  @if (p.description) { <dt>Description</dt><dd>{{ p.description }}</dd> }
                </dl>
                <app-readiness-panel [readiness]="p.readiness" />
                <p class="muted small">Nothing is calculated, verified or issued at this stage. Methodology selection and MRV come later.</p>
              </div>
            </div>
          </ng-template>
        </mat-tab>
        <mat-tab [label]="'Farms (' + p.farm_count + ')'">
          <ng-template matTabContent><app-project-farms-panel [project]="p" (changed)="load()" /></ng-template>
        </mat-tab>
        <mat-tab [label]="'Team (' + p.counts['participants'] + ')'">
          <ng-template matTabContent><app-project-team-panel [project]="p" /></ng-template>
        </mat-tab>
        <mat-tab label="Boundary">
          <ng-template matTabContent><app-project-boundary-panel [project]="p" (changed)="load()" /></ng-template>
        </mat-tab>
        <mat-tab label="Standard & activity">
          <ng-template matTabContent><app-project-standard-panel [project]="p" (changed)="setProject($event)" /></ng-template>
        </mat-tab>
        <mat-tab label="Crediting & baseline">
          <ng-template matTabContent><app-project-periods-panel [project]="p" (changed)="load()" /></ng-template>
        </mat-tab>
        <mat-tab [label]="'Carbon rights (' + p.counts['carbon_rights'] + ')'">
          <ng-template matTabContent><app-project-rights-panel [project]="p" (changed)="load()" /></ng-template>
        </mat-tab>
        <mat-tab [label]="'Documents (' + p.counts['documents'] + ')'">
          <ng-template matTabContent>
            <div class="tab-body">
              <app-documents-panel [documents]="documents()" [categories]="categories" [canUpload]="p.can_manage && p.status !== 'CLOSED'"
                                   [uploadFn]="uploadFn" (uploaded)="load()" />
            </div>
          </ng-template>
        </mat-tab>
        <mat-tab label="Status history">
          <ng-template matTabContent><app-project-history-panel [project]="p" /></ng-template>
        </mat-tab>
      </mat-tab-group>
    }
  `,
  styles: `
    .status-row { display: flex; gap: 6px; margin: -8px 0 16px; flex-wrap: wrap; }
    .overview { display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); gap: 20px; }
    @media (max-width: 900px) { .overview { grid-template-columns: 1fr; } }
    .danger { color: #b71c1c; }
  `,
})
export class ProjectDetailPage implements OnInit {
  readonly id = input.required<string>();
  private readonly api = inject(ProjectsApi);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotifyService);
  private readonly route = inject(ActivatedRoute);
  protected readonly label = label;
  protected readonly badge = projectBadge;
  protected readonly area = formatArea;
  protected readonly categories = PROJECT_DOC_CATEGORIES;
  protected readonly project = signal<Project | null>(null);
  protected readonly boundary = signal<BoundaryView | null>(null);
  protected readonly documents = signal<DocumentInfo[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<ApiError | null>(null);
  protected readonly busy = signal(false);
  protected readonly tab = signal(Math.max(0, TABS.indexOf(this.route.snapshot.queryParamMap.get('tab') ?? 'overview')));
  protected readonly uploadFn: UploadFn = (file, category, title) => this.api.uploadDocument(this.id(), file, category, title);
  protected readonly actions = computed(() => {
    const p = this.project();
    if (!p) return [];
    return p.allowed_transitions.map((target) => ({ target, ...projectAction(p.status, target) }));
  });
  protected readonly layers = computed<MapLayer[]>(() => {
    const v = this.boundary();
    if (!v) return [];
    const out: MapLayer[] = v.farms.map((f) => ({ geojson: f.geojson, color: '#1565c0', dashed: true, fillOpacity: 0.05, label: f.farm_code }));
    if (v.current) out.unshift({ geojson: v.current.geojson, color: '#2e7d32', fillOpacity: 0.2, label: 'Project boundary' });
    return out;
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.error.set(null);
    this.api.get(this.id()).subscribe({
      next: (p) => this.setProject(p),
      error: (e: unknown) => {
        this.error.set(ApiError.from(e));
        this.loading.set(false);
      },
    });
  }

  setProject(p: Project): void {
    this.project.set(p);
    this.loading.set(false);
    this.api.boundary(p.id).subscribe((b) => this.boundary.set(b));
    this.api.documents(p.id).subscribe((d) => this.documents.set(d.documents));
  }

  transition(target: ProjectStatus): void {
    const p = this.project();
    if (!p) return;
    const a = projectAction(p.status, target);
    askReason(this.dialog, { title: `${a.label}?`, confirmLabel: a.label, danger: a.danger, message: a.confirm }).subscribe((r) => {
      if (r) runAction(this.api.transition(p.id, a.endpoint, r.reason), this.busy, this.notify, `Project is now ${label(target)}.`,
        (x) => this.setProject(x));
    });
  }
}
