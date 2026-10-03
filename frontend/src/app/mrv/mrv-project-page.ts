import { ChangeDetectionStrategy, Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatTabsModule } from '@angular/material/tabs';
import { ActivatedRoute } from '@angular/router';
import { forkJoin } from 'rxjs';

import { ApiError } from '../core/api/api.models';
import { AuthService } from '../core/auth/auth.service';
import { P } from '../core/auth/permissions';
import { label } from '../farmer/farmer.models';
import { Project, ProjectFarm } from '../projects/project.models';
import { ProjectsApi } from '../projects/projects.api';
import { PageHeader } from '../shared/page-header';
import { StateView } from '../shared/state-view';
import { StatusBadge } from '../shared/status-badge';
import { MrvApi } from './mrv.api';
import { Period, Requirements, Stratum, mrvBadge } from './mrv.models';
import { MrvDatasetsPanel } from './panels/mrv-datasets-panel';
import { MrvDesignPanel } from './panels/mrv-design-panel';
import { MrvEvidencePanel } from './panels/mrv-evidence-panel';
import { MrvHistoryPanel } from './panels/mrv-history-panel';
import { MrvCalculationsPanel } from './panels/mrv-calculations-panel';
import { VerificationPanel } from '../verification/verification-panel';
import { MrvSamplesPanel } from './panels/mrv-samples-panel';
import { MrvPeriodsPanel } from './panels/mrv-periods-panel';
import { MrvPlansPanel } from './panels/mrv-plans-panel';
import { MrvPointsPanel } from './panels/mrv-points-panel';
import { MrvRecordsPanel } from './panels/mrv-records-panel';
import { MrvStrataPanel } from './panels/mrv-strata-panel';

const TABS = ['plans', 'periods', 'strata', 'design', 'points', 'data', 'evidence', 'samples', 'datasets', 'calculations', 'history', 'verification'];

/** MRV workspace of one project (locked methodology). Tabs that work per monitoring period share the period picker. */
@Component({
  selector: 'app-mrv-project-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, MatTabsModule, MatFormFieldModule, MatSelectModule, PageHeader, StateView, StatusBadge, MrvPlansPanel, MrvPeriodsPanel,
    MrvStrataPanel, MrvDesignPanel, MrvPointsPanel, MrvRecordsPanel, MrvEvidencePanel, MrvDatasetsPanel, MrvHistoryPanel, MrvSamplesPanel,
    MrvCalculationsPanel, VerificationPanel],
  template: `
    <app-state-view [loading]="loading()" [error]="error()" (retry)="load()" />
    @if (project(); as p) {
      <app-page-header [title]="'MRV · ' + p.name" [subtitle]="p.project_code + ' · ' + (p.methodology_label ?? '')" backLink="/mrv" backLabel="MRV" />
      <div class="status-row">
        <app-status-badge status="INFO" [text]="label(p.status)" />
        @if (req(); as r) { <app-status-badge [status]="badge(r.status)" [text]="'Methodology MRV requirements: ' + label(r.status)" /> }
        @if (p.environment === 'DEMO') { <app-status-badge status="DEMO" /> }
        <span class="spacer"></span>
        @if (periods().length) {
          <mat-form-field subscriptSizing="dynamic" class="picker">
            <mat-label>Monitoring period</mat-label>
            <mat-select [ngModel]="periodId()" (ngModelChange)="periodId.set($event)" data-testid="period-picker">
              @for (x of periods(); track x.id) { <mat-option [value]="x.id">#{{ x.period_number }} {{ x.name }} · {{ label(x.status) }}</mat-option> }
            </mat-select>
          </mat-form-field>
        }
      </div>
      @if (req()?.status === 'CONFIGURATION_REQUIRED') {
        <div class="note warn" role="note">
          <strong>CONFIGURATION_REQUIRED.</strong> The locked methodology version does not configure: {{ req()!.gaps.join('; ') }}.
          Project-configured values are used and recorded as such — nothing is invented.
        </div>
      }
      <mat-tab-group animationDuration="0ms" mat-stretch-tabs="false" [selectedIndex]="tab()" (selectedIndexChange)="tab.set($event)">
        <mat-tab label="MRV plans"><ng-template matTabContent>
          <app-mrv-plans-panel [projectId]="p.id" [requirements]="req()" />
        </ng-template></mat-tab>
        <mat-tab [label]="'Monitoring periods (' + periods().length + ')'"><ng-template matTabContent>
          <app-mrv-periods-panel [projectId]="p.id" [periods]="periods()" (changed)="reloadPeriods()" />
        </ng-template></mat-tab>
        <mat-tab label="Stratification"><ng-template matTabContent>
          <app-mrv-strata-panel [projectId]="p.id" [farms]="farms()" [strata]="strata()" (changed)="reloadStrata()" />
        </ng-template></mat-tab>
        <mat-tab label="Sampling design"><ng-template matTabContent>
          <app-mrv-design-panel [projectId]="p.id" [period]="period()" [strata]="strata()" (changed)="reloadPeriods()" />
        </ng-template></mat-tab>
        <mat-tab label="Points & assignments"><ng-template matTabContent>
          <app-mrv-points-panel [projectId]="p.id" [period]="period()" [strata]="strata()" [canAssign]="auth.has(P.SAMPLING_ASSIGN)"
                                [canReview]="auth.has(P.SAMPLING_REVIEW)" />
        </ng-template></mat-tab>
        <mat-tab label="Monitoring data"><ng-template matTabContent>
          <app-mrv-records-panel [period]="period()" [farms]="farms()" />
        </ng-template></mat-tab>
        <mat-tab label="Evidence"><ng-template matTabContent>
          <app-mrv-evidence-panel [projectId]="p.id" [period]="period()" [farms]="farms()" />
        </ng-template></mat-tab>
        <mat-tab label="Samples & laboratory"><ng-template matTabContent>
          <app-mrv-samples-panel [projectId]="p.id" [period]="period()" />
        </ng-template></mat-tab>
        <mat-tab label="Datasets & QA"><ng-template matTabContent>
          <app-mrv-datasets-panel [projectId]="p.id" [periods]="periods()" (changed)="reloadPeriods()" />
        </ng-template></mat-tab>
        <mat-tab label="Calculations"><ng-template matTabContent>
          <app-mrv-calculations-panel [projectId]="p.id" [period]="period()" />
        </ng-template></mat-tab>
        <mat-tab label="MRV history"><ng-template matTabContent>
          <app-mrv-history-panel [projectId]="p.id" />
        </ng-template></mat-tab>
        @if (canVerify) {
          <mat-tab label="Verification"><ng-template matTabContent>
            <app-verification-panel [projectId]="p.id" [periodId]="period()?.id ?? null" />
          </ng-template></mat-tab>
        }
      </mat-tab-group>
    }
  `,
  styles: `
    .status-row { display: flex; gap: 6px; margin: -8px 0 12px; flex-wrap: wrap; align-items: center; }
    .spacer { flex: 1; } .picker { min-width: 280px; }
    .note { padding: 10px 14px; border-radius: 8px; margin-bottom: 12px; font-size: 13px; }
    .warn { background: #fff4d6; color: #5d4000; }
  `,
})
export class MrvProjectPage implements OnInit {
  readonly id = input.required<string>();
  protected readonly auth = inject(AuthService);
  protected readonly P = P;
  protected readonly canVerify = [P.VERIFICATION_READ, P.VERIFICATION_MANAGE, P.VERIFICATION_RESPOND].some((c) => this.auth.has(c));
  private readonly api = inject(MrvApi);
  private readonly projectsApi = inject(ProjectsApi);
  private readonly route = inject(ActivatedRoute);
  protected readonly label = label;
  protected readonly badge = mrvBadge;
  protected readonly project = signal<Project | null>(null);
  protected readonly req = signal<Requirements | null>(null);
  protected readonly farms = signal<ProjectFarm[]>([]);
  protected readonly periods = signal<Period[]>([]);
  protected readonly strata = signal<Stratum[]>([]);
  protected readonly periodId = signal<string | null>(null);
  protected readonly period = computed(() => this.periods().find((x) => x.id === this.periodId()) ?? null);
  protected readonly loading = signal(true);
  protected readonly error = signal<ApiError | null>(null);
  protected readonly tab = signal(Math.max(0, TABS.indexOf(this.route.snapshot.queryParamMap.get('tab') ?? 'plans')));

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.error.set(null);
    forkJoin({ p: this.projectsApi.get(this.id()), r: this.api.requirements(this.id()), f: this.projectsApi.farms(this.id()) }).subscribe({
      next: ({ p, r, f }) => {
        this.project.set(p);
        this.req.set(r);
        this.farms.set(f.filter((x) => x.status === 'ACTIVE'));
        this.loading.set(false);
        this.reloadPeriods();
        this.reloadStrata();
      },
      error: (e: unknown) => { this.error.set(ApiError.from(e)); this.loading.set(false); },
    });
  }

  reloadPeriods(): void {
    this.api.periods(this.id()).subscribe((ps) => {
      this.periods.set(ps);
      if (!ps.some((x) => x.id === this.periodId())) {
        const open = ps.find((x) => !['APPROVED', 'CLOSED'].includes(x.status)) ?? ps[0];
        this.periodId.set(open?.id ?? null);
      }
    });
  }

  reloadStrata(): void {
    this.api.strata(this.id()).subscribe((s) => this.strata.set(s));
  }
}
