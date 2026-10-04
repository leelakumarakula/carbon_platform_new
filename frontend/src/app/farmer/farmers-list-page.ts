import { BreakpointObserver } from '@angular/cdk/layout';
import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, inject } from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatPaginatorModule } from '@angular/material/paginator';
import { MatSelectModule } from '@angular/material/select';
import { MatSortModule } from '@angular/material/sort';
import { MatTableModule } from '@angular/material/table';
import { Router, RouterLink } from '@angular/router';
import { debounceTime, map } from 'rxjs';

import { AuthService } from '../core/auth/auth.service';
import { P } from '../core/auth/permissions';
import { PageHeader } from '../shared/page-header';
import { PagedList } from '../shared/paged-list';
import { StateView } from '../shared/state-view';
import { StatusBadge } from '../shared/status-badge';
import { FarmerStatus, FarmerSummary, label } from './farmer.models';
import { FarmersApi } from './farmers.api';

@Component({
  selector: 'app-farmers-list-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, RouterLink, MatTableModule, MatSortModule, MatPaginatorModule, MatFormFieldModule, MatInputModule,
    MatSelectModule, MatButtonModule, MatIconModule, MatCardModule, PageHeader, StateView, StatusBadge],
  template: `
    <app-page-header title="Farmers" subtitle="Registration, KYC, consents, agreements and bank details.">
      @if (canCreate) { <a mat-flat-button routerLink="/farmers/new"><mat-icon>person_add</mat-icon> Register farmer</a> }
    </app-page-header>
    <form class="filters" [formGroup]="filters">
      <mat-form-field subscriptSizing="dynamic">
        <mat-label>Search name, code, village, district</mat-label>
        <input matInput formControlName="search" />
        <mat-icon matPrefix>search</mat-icon>
      </mat-form-field>
      <mat-form-field subscriptSizing="dynamic">
        <mat-label>Status</mat-label>
        <mat-select formControlName="status">
          <mat-option [value]="null">Any</mat-option>
          @for (s of statuses; track s) { <mat-option [value]="s">{{ label(s) }}</mat-option> }
        </mat-select>
      </mat-form-field>
    </form>
    <app-state-view [loading]="list.loading()" [error]="list.error()" [empty]="!list.loading() && !list.error() && list.total() === 0"
                    emptyText="No farmers match these filters." (retry)="list.load()" />
    @if (handset()) {
      <div class="cards">
        @for (f of list.items(); track f.id) {
          <a class="card" [routerLink]="['/farmers', f.id]">
            <div class="row"><strong>{{ f.full_name }}</strong><app-status-badge [status]="f.status" /></div>
            <div class="muted small">{{ f.farmer_code }} · {{ f.village ?? f.district ?? '—' }} · {{ f.farm_count }} farm(s)</div>
          </a>
        }
      </div>
    } @else {
      <div class="table-wrap" [hidden]="list.total() === 0">
        <table mat-table [dataSource]="list.items()" matSort (matSortChange)="list.onSort($event)" matSortActive="farmer_code" matSortDirection="asc">
          <ng-container matColumnDef="farmer_code">
            <th mat-header-cell *matHeaderCellDef mat-sort-header>Code</th>
            <td mat-cell *matCellDef="let f"><a [routerLink]="['/farmers', f.id]">{{ f.farmer_code }}</a></td>
          </ng-container>
          <ng-container matColumnDef="full_name">
            <th mat-header-cell *matHeaderCellDef mat-sort-header>Name</th>
            <td mat-cell *matCellDef="let f">{{ f.full_name }}</td>
          </ng-container>
          <ng-container matColumnDef="village">
            <th mat-header-cell *matHeaderCellDef mat-sort-header>Village</th>
            <td mat-cell *matCellDef="let f">{{ f.village ?? '—' }}<div class="muted small">{{ f.district }}</div></td>
          </ng-container>
          <ng-container matColumnDef="org">
            <th mat-header-cell *matHeaderCellDef>Organization</th>
            <td mat-cell *matCellDef="let f">{{ f.organization_name }}</td>
          </ng-container>
          <ng-container matColumnDef="farms">
            <th mat-header-cell *matHeaderCellDef>Farms</th>
            <td mat-cell *matCellDef="let f">{{ f.farm_count }}</td>
          </ng-container>
          <ng-container matColumnDef="status">
            <th mat-header-cell *matHeaderCellDef mat-sort-header>Status</th>
            <td mat-cell *matCellDef="let f"><app-status-badge [status]="f.status" />
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
export class FarmersListPage implements OnInit {
  private readonly api = inject(FarmersApi);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);
  protected readonly canCreate = inject(AuthService).has(P.FARMERS_MANAGE);
  protected readonly handset = toSignal(inject(BreakpointObserver).observe('(max-width: 700px)').pipe(map((r) => r.matches)),
    { initialValue: false });
  protected readonly label = label;
  protected readonly statuses: FarmerStatus[] = ['DRAFT', 'REGISTERED', 'KYC_PENDING', 'KYC_VERIFIED', 'ACTIVE', 'SUSPENDED'];
  protected readonly columns = ['farmer_code', 'full_name', 'village', 'org', 'farms', 'status'];
  protected readonly filters = new FormGroup({
    search: new FormControl('', { nonNullable: true }),
    status: new FormControl<FarmerStatus | null>(null),
  });
  protected readonly list = new PagedList<FarmerSummary>(
    (q) => this.api.list({ ...q, status: this.filters.controls.status.value, search: this.filters.controls.search.value.trim() }),
    this.destroyRef, 'farmer_code');

  ngOnInit(): void {
    this.filters.valueChanges.pipe(debounceTime(300), takeUntilDestroyed(this.destroyRef)).subscribe(() => this.list.reset());
    this.list.load();
  }

  open(f: FarmerSummary): void {
    void this.router.navigate(['/farmers', f.id]);
  }
}
