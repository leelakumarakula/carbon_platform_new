import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatDialog } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { MatTabsModule } from '@angular/material/tabs';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { map } from 'rxjs';

import { ApiError } from '../core/api/api.models';
import { NotifyService } from '../core/notify.service';
import { label } from '../farmer/farmer.models';
import { DocumentsPanel, UploadFn } from '../shared/documents-panel';
import { GeoMap, MapLayer } from '../shared/geo-map';
import { formatArea } from '../shared/geo';
import { PageHeader } from '../shared/page-header';
import { ReadinessPanel } from '../shared/readiness-panel';
import { askReason } from '../shared/reason-dialog';
import { reloadOn } from '../shared/reload-on';
import { runAction } from '../shared/run-action';
import { StateView } from '../shared/state-view';
import { StatusBadge } from '../shared/status-badge';
import { FARM_ACTIONS, FARM_DOC_CATEGORIES, Farm, Overlap } from './farm.models';
import { FarmsApi } from './farms.api';
import { BoundaryEditor } from './panels/boundary-editor';
import { FarmEvidencePanel } from './panels/farm-evidence-panel';
import { FarmExternalDataPanel } from './panels/farm-external-data-panel';
import { FarmHistoryPanel } from './panels/farm-history-panel';
import { FarmOverlapsPanel } from './panels/farm-overlaps-panel';
import { FarmOwnershipPanel } from './panels/farm-ownership-panel';

const TABS = ['overview', 'boundary', 'ownership', 'history', 'evidence', 'overlaps', 'documents', 'external'];

@Component({
  selector: 'app-farm-detail-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, RouterLink, MatTabsModule, MatCardModule, MatButtonModule, MatIconModule, PageHeader, StateView, StatusBadge, ReadinessPanel,
    DocumentsPanel, GeoMap, BoundaryEditor, FarmOwnershipPanel, FarmHistoryPanel, FarmEvidencePanel, FarmOverlapsPanel,
    FarmExternalDataPanel],
  template: `
    <app-state-view [loading]="loading()" [error]="error()" (retry)="load()" />
    @if (farm(); as f) {
      <app-page-header [title]="f.name" [subtitle]="f.farm_code + ' · ' + f.farmer_name + ' · ' + (f.village ?? '')" backLink="/farms" backLabel="Farms">
        @for (a of actions(); track a.target) {
          <button mat-stroked-button type="button" [class.danger]="a.danger" [disabled]="busy()" (click)="transition(a.target)">{{ a.label }}</button>
        }
      </app-page-header>
      <div class="status-row">
        <app-status-badge [status]="badge(f.status)" [text]="f.status" />
        @if (f.open_overlaps) { <app-status-badge status="WARNING" [text]="f.open_overlaps + ' overlap flag(s)'" /> }
        @if (f.environment === 'DEMO') { <app-status-badge status="DEMO" /> }
      </div>
      <mat-tab-group animationDuration="0ms" mat-stretch-tabs="false" [selectedIndex]="tab()" (selectedIndexChange)="tab.set($event)">
        <mat-tab label="Overview">
          <ng-template matTabContent>
            <div class="tab-body overview">
              <app-geo-map [layers]="layers()" height="380px" />
              <div>
                <dl class="kv">
                  <dt>Measured area</dt><dd>{{ area(f.area_hectares) }} <span class="muted small">(SQL Server STArea)</span></dd>
                  <dt>Declared area</dt><dd>{{ area(f.declared_area_hectares) }}</dd>
                  <dt>Tenure</dt><dd>{{ label(f.land_tenure) }}</dd>
                  <dt>Farmer</dt><dd><a [routerLink]="['/farmers', f.farmer_id]">{{ f.farmer_name }}</a> ({{ f.farmer_code }})</dd>
                  <dt>Location</dt><dd>{{ place(f) }}</dd>
                  <dt>Records</dt><dd>{{ f.ownership_count }} ownership · {{ f.history_counts.land }} land · {{ f.history_counts.crop }} crop ·
                    {{ f.history_counts.practice }} practice · {{ f.evidence_count }} evidence</dd>
                  <dt>Submitted</dt><dd>{{ f.submitted_at ? (f.submitted_at | date: 'medium') : '—' }}</dd>
                  <dt>Verified</dt><dd>{{ f.verified_at ? (f.verified_at | date: 'medium') : '—' }}</dd>
                  @if (f.review_notes) { <dt>Review notes</dt><dd>{{ f.review_notes }}</dd> }
                </dl>
                <app-readiness-panel [readiness]="f.readiness" />
              </div>
            </div>
          </ng-template>
        </mat-tab>
        <mat-tab label="Boundary">
          <ng-template matTabContent><app-boundary-editor [farm]="f" [overlaps]="overlaps()" (saved)="setFarm($event)" /></ng-template>
        </mat-tab>
        <mat-tab [label]="'Ownership (' + f.ownership_count + ')'">
          <ng-template matTabContent><app-farm-ownership-panel [farm]="f" (changed)="load()" /></ng-template>
        </mat-tab>
        <mat-tab label="History">
          <ng-template matTabContent><app-farm-history-panel [farm]="f" (changed)="load()" /></ng-template>
        </mat-tab>
        <mat-tab [label]="'Evidence (' + f.evidence_count + ')'">
          <ng-template matTabContent><app-farm-evidence-panel [farm]="f" (changed)="load()" /></ng-template>
        </mat-tab>
        <mat-tab [label]="'Overlaps (' + overlaps().length + ')'">
          <ng-template matTabContent><app-farm-overlaps-panel [farm]="f" [overlaps]="overlaps()" (changed)="load()" /></ng-template>
        </mat-tab>
        <mat-tab [label]="'Documents (' + f.documents.length + ')'">
          <ng-template matTabContent>
            <div class="tab-body">
              <app-documents-panel [documents]="f.documents" [categories]="categories" [canUpload]="f.can_manage" [uploadFn]="uploadFn"
                [presetCategory]="categoryParam() ?? null" (uploaded)="load()" />
            </div>
          </ng-template>
        </mat-tab>
        <mat-tab label="External data">
          <ng-template matTabContent><app-farm-external-data-panel [farm]="f" /></ng-template>
        </mat-tab>
      </mat-tab-group>
    }
  `,
  styles: `
    .status-row { display: flex; gap: 6px; margin: -8px 0 16px; flex-wrap: wrap; }
    .overview { display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); gap: 20px; }
    @media (max-width: 900px) { .overview { grid-template-columns: 1fr; } }
  `,
})
export class FarmDetailPage {
  readonly id = input.required<string>();
  private readonly api = inject(FarmsApi);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotifyService);
  private readonly route = inject(ActivatedRoute);

  protected readonly farm = signal<Farm | null>(null);
  protected readonly overlaps = signal<Overlap[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<ApiError | null>(null);
  protected readonly busy = signal(false);
  protected readonly tab = signal(0);
  private readonly tabParam = toSignal(this.route.queryParamMap.pipe(map((q) => q.get('tab'))));
  protected readonly categoryParam = toSignal(this.route.queryParamMap.pipe(map((q) => q.get('category'))));
  protected readonly label = label;
  protected readonly area = formatArea;
  protected readonly categories = FARM_DOC_CATEGORIES;
  protected readonly uploadFn: UploadFn = (file, category, title) => this.api.uploadDocument(this.id(), file, category, title);

  protected readonly layers = computed<MapLayer[]>(() => {
    const f = this.farm();
    const out: MapLayer[] = [];
    if (f?.current_boundary) out.push({ geojson: f.current_boundary.geojson, color: '#2e7d32', label: `${f.farm_code} (v${f.current_boundary.version})` });
    for (const o of this.overlaps()) {
      if (o.other_geojson && o.status !== 'OBSOLETE') out.push({ geojson: o.other_geojson, color: '#c62828', dashed: true,
        label: `Overlap with ${o.other_farm_code}` });
    }
    return out;
  });

  protected readonly actions = computed(() => {
    const f = this.farm();
    if (!f) return [];
    return f.allowed_transitions.map((target) => {
      const a = FARM_ACTIONS[target];
      const endpoint = target === 'DRAFT' && f.status === 'SUBMITTED' ? 'withdraw' : a.endpoint;
      const text = target === 'DRAFT' && f.status === 'SUBMITTED' ? 'Withdraw submission' : a.label;
      return { target, label: text, endpoint, danger: a.danger ?? false, allowed: a.review ? f.can_review : f.can_manage };
    }).filter((a) => a.allowed);
  });

  constructor() {
    reloadOn(this.id, () => {
      this.farm.set(null);
      this.overlaps.set([]);
      this.loading.set(true);
      this.load();
    });
    reloadOn(() => [this.id(), this.tabParam()], () => this.tab.set(Math.max(0, TABS.indexOf(this.tabParam() ?? 'overview'))));
  }

  load(): void {
    this.error.set(null);
    this.api.get(this.id()).subscribe({
      next: (f) => this.setFarm(f),
      error: (e: unknown) => {
        this.error.set(ApiError.from(e));
        this.loading.set(false);
      },
    });
  }

  setFarm(f: Farm): void {
    this.farm.set(f);
    this.loading.set(false);
    this.api.overlaps(f.id).subscribe((o) => this.overlaps.set(o));
  }

  place(f: Farm): string {
    return [f.village, f.district, f.state].filter((x) => !!x).join(', ') + ' · ' + f.country;
  }

  badge(status: string): string {
    return status === 'VERIFIED' ? 'ACTIVE' : status === 'REJECTED' ? 'FAILED' : status === 'DRAFT' ? 'INFO' : status;
  }

  transition(target: string): void {
    const a = this.actions().find((x) => x.target === target);
    if (!a) return;
    askReason(this.dialog, { title: `${a.label}?`, confirmLabel: a.label, danger: a.danger,
      message: target === 'VERIFIED' ? 'You confirm the boundary, tenure and evidence were reviewed. You cannot verify a farm you submitted.' : undefined,
    }).subscribe((r) => {
      if (r) runAction(this.api.transition(this.id(), a.endpoint, r.reason), this.busy, this.notify, `Farm is now ${label(target)}.`,
        (f) => this.setFarm(f));
    });
  }
}
