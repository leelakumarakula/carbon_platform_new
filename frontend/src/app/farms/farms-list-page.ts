import { BreakpointObserver } from '@angular/cdk/layout';
import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatPaginatorModule } from '@angular/material/paginator';
import { MatSelectModule } from '@angular/material/select';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatSortModule } from '@angular/material/sort';
import { MatTableModule } from '@angular/material/table';
import { Router, RouterLink } from '@angular/router';
import { debounceTime, map } from 'rxjs';

import { AuthService } from '../core/auth/auth.service';
import { P } from '../core/auth/permissions';
import { GeoMap, MapPoint } from '../shared/geo-map';
import { formatArea } from '../shared/geo';
import { PageHeader } from '../shared/page-header';
import { PagedList } from '../shared/paged-list';
import { StateView } from '../shared/state-view';
import { label } from '../farmer/farmer.models';
import { StatusBadge } from '../shared/status-badge';
import { FarmStatus, FarmSummary } from './farm.models';
import { FarmsApi } from './farms.api';

function readView(): 'list' | 'map' {
  try {
    return localStorage.getItem('farms.view') === 'map' ? 'map' : 'list';
  } catch {
    return 'list';
  }
}

@Component({
  selector: 'app-farms-list-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, RouterLink, MatTableModule, MatSortModule, MatPaginatorModule, MatFormFieldModule, MatInputModule,
    MatSelectModule, MatIconModule, MatSlideToggleModule, MatButtonModule, MatButtonToggleModule, PageHeader, StateView, StatusBadge, GeoMap],
  template: `
    <app-page-header title="Farms" subtitle="Boundaries, ownership, history, evidence and GIS verification.">
      @if (canCreate) { <a mat-flat-button routerLink="/farms/new"><mat-icon>add_location_alt</mat-icon> New farm</a> }
    </app-page-header>
    <form class="filters" [formGroup]="filters">
      <mat-form-field subscriptSizing="dynamic">
        <mat-label>Search code, name, village, farmer</mat-label>
        <input matInput formControlName="search" /><mat-icon matPrefix>search</mat-icon>
      </mat-form-field>
      <mat-form-field subscriptSizing="dynamic">
        <mat-label>Status</mat-label>
        <mat-select formControlName="status">
          <mat-option [value]="null">Any</mat-option>
          @for (s of statuses; track s) { <mat-option [value]="s">{{ label(s) }}</mat-option> }
        </mat-select>
      </mat-form-field>
      <mat-slide-toggle formControlName="overlaps">Open overlaps only</mat-slide-toggle>
      <mat-button-toggle-group [value]="view()" (change)="setView($event.value)" aria-label="View">
        <mat-button-toggle value="list"><mat-icon>list</mat-icon></mat-button-toggle>
        <mat-button-toggle value="map"><mat-icon>map</mat-icon></mat-button-toggle>
      </mat-button-toggle-group>
    </form>
    <app-state-view [loading]="list.loading()" [error]="list.error()" [empty]="!list.loading() && !list.error() && list.total() === 0"
                    emptyText="No farms match these filters." (retry)="list.load()" />
    @if (view() === 'map') {
      <app-geo-map [points]="points()" height="480px" />
      <p class="muted small">Farm centroids on this page. Open a farm to see its boundary.</p>
    } @else if (handset()) {
      <div class="cards">
        @for (f of list.items(); track f.id) {
          <a class="card" [routerLink]="['/farms', f.id]">
            <div class="row"><strong>{{ f.name }}</strong><app-status-badge [status]="badge(f.status)" [text]="label(f.status)" /></div>
            <div class="muted small">{{ f.farm_code }} · {{ area(f.area_hectares) }} · {{ f.farmer_name }}</div>
            @if (f.open_overlaps) { <app-status-badge status="WARNING" [text]="f.open_overlaps + ' overlap flag(s)'" /> }
          </a>
        }
      </div>
    } @else {
      <div class="table-wrap" [hidden]="list.total() === 0">
        <table mat-table [dataSource]="list.items()" matSort (matSortChange)="list.onSort($event)" matSortActive="farm_code" matSortDirection="asc">
          <ng-container matColumnDef="farm_code">
            <th mat-header-cell *matHeaderCellDef mat-sort-header>Code</th>
            <td mat-cell *matCellDef="let f"><a [routerLink]="['/farms', f.id]">{{ f.farm_code }}</a></td>
          </ng-container>
          <ng-container matColumnDef="name">
            <th mat-header-cell *matHeaderCellDef mat-sort-header>Name</th>
            <td mat-cell *matCellDef="let f">{{ f.name }}<div class="muted small">{{ f.village }}</div></td>
          </ng-container>
          <ng-container matColumnDef="farmer">
            <th mat-header-cell *matHeaderCellDef>Farmer</th>
            <td mat-cell *matCellDef="let f">{{ f.farmer_name }}<div class="muted small">{{ f.farmer_code }}</div></td>
          </ng-container>
          <ng-container matColumnDef="area_hectares">
            <th mat-header-cell *matHeaderCellDef mat-sort-header>Measured area</th>
            <td mat-cell *matCellDef="let f">{{ area(f.area_hectares) }}</td>
          </ng-container>
          <ng-container matColumnDef="tenure">
            <th mat-header-cell *matHeaderCellDef>Tenure</th>
            <td mat-cell *matCellDef="let f">{{ f.land_tenure }}</td>
          </ng-container>
          <ng-container matColumnDef="status">
            <th mat-header-cell *matHeaderCellDef mat-sort-header>Status</th>
            <td mat-cell *matCellDef="let f"><app-status-badge [status]="badge(f.status)" [text]="label(f.status)" />
              @if (f.open_overlaps) { <app-status-badge status="WARNING" [text]="f.open_overlaps + ' overlap'" /> }
              @if (f.environment === 'DEMO') { <app-status-badge status="DEMO" /> }</td>
          </ng-container>
          <tr mat-header-row *matHeaderRowDef="columns"></tr>
          <tr mat-row *matRowDef="let row; columns: columns" class="clickable" (click)="open(row)"></tr>
        </table>
      </div>
    }
    @if (list.total() > 0) {
      <mat-paginator [length]="list.total()" [pageIndex]="list.page() - 1" [pageSize]="list.pageSize()" [pageSizeOptions]="[10, 25, 50, 100]"
                     (page)="list.onPage($event)" />
    }
  `,
  styles: `
    .cards { display: flex; flex-direction: column; gap: 8px; }
    .card { display: block; padding: 12px 14px; border: 1px solid var(--mat-sys-outline-variant); border-radius: 10px; color: inherit;
      text-decoration: none; background: var(--mat-sys-surface); }
    .row { display: flex; justify-content: space-between; gap: 8px; align-items: center; margin-bottom: 4px; }
  `,
})
export class FarmsListPage implements OnInit {
  private readonly api = inject(FarmsApi);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);
  protected readonly handset = toSignal(inject(BreakpointObserver).observe('(max-width: 700px)').pipe(map((r) => r.matches)),
    { initialValue: false });
  protected readonly area = formatArea;
  /** Same rule as the /farms/new route guard. */
  private readonly auth = inject(AuthService);
  protected readonly canCreate = this.auth.has(P.FARMS_MANAGE) || this.auth.has(P.FARMERS_SELF);
  protected readonly label = label;
  protected readonly statuses: FarmStatus[] = ['DRAFT', 'SUBMITTED', 'GIS_REVIEW', 'VERIFIED', 'REJECTED', 'INACTIVE'];
  protected readonly columns = ['farm_code', 'name', 'farmer', 'area_hectares', 'tenure', 'status'];
  protected readonly filters = new FormGroup({
    search: new FormControl('', { nonNullable: true }),
    status: new FormControl<FarmStatus | null>(null),
    overlaps: new FormControl(false, { nonNullable: true }),
  });
  protected readonly list = new PagedList<FarmSummary>((q) => {
    const f = this.filters.getRawValue();
    return this.api.list({ ...q, search: f.search.trim(), status: f.status, has_open_overlaps: f.overlaps ? true : null });
  }, this.destroyRef, 'farm_code');
  protected readonly view = signal<'list' | 'map'>(readView());
  protected readonly points = computed<MapPoint[]>(() => this.list.items().filter((f) => f.centroid_lat && f.centroid_lon).map((f) => ({
    lat: Number(f.centroid_lat), lon: Number(f.centroid_lon), label: `${f.farm_code} · ${f.name}`,
    color: f.status === 'VERIFIED' ? '#2e7d32' : f.open_overlaps ? '#c62828' : '#1565c0',
  })));

  ngOnInit(): void {
    this.filters.valueChanges.pipe(debounceTime(300), takeUntilDestroyed(this.destroyRef)).subscribe(() => this.list.reset());
    this.list.load();
  }

  badge(status: string): string {
    return status === 'VERIFIED' ? 'ACTIVE' : status === 'REJECTED' ? 'FAILED' : status === 'DRAFT' ? 'INFO' : status;
  }

  setView(v: 'list' | 'map'): void {
    this.view.set(v);
    try {
      localStorage.setItem('farms.view', v);
    } catch { /* storage unavailable (private mode) — the choice just isn't remembered */ }
  }

  open(f: FarmSummary): void {
    void this.router.navigate(['/farms', f.id]);
  }
}
