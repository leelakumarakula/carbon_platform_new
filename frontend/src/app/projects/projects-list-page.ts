import { BreakpointObserver } from '@angular/cdk/layout';
import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, inject } from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
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
import { label } from '../farmer/farmer.models';
import { formatArea } from '../shared/geo';
import { PageHeader } from '../shared/page-header';
import { PagedList } from '../shared/paged-list';
import { StateView } from '../shared/state-view';
import { StatusBadge } from '../shared/status-badge';
import { PHASE3_STATUSES, ProjectStatus, ProjectSummary, projectBadge } from './project.models';
import { ProjectsApi } from './projects.api';

@Component({
  selector: 'app-projects-list-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, RouterLink, MatTableModule, MatSortModule, MatPaginatorModule, MatFormFieldModule, MatInputModule,
    MatSelectModule, MatIconModule, MatButtonModule, PageHeader, StateView, StatusBadge],
  template: `
    <app-page-header title="Projects" subtitle="Participating farms, team, boundary, standard / activity and eligibility review.">
      @if (canCreate) { <a mat-flat-button routerLink="/projects/new"><mat-icon>add</mat-icon> New project</a> }
    </app-page-header>
    <form class="filters" [formGroup]="filters">
      <mat-form-field subscriptSizing="dynamic">
        <mat-label>Search code, name, region</mat-label>
        <input matInput formControlName="search" /><mat-icon matSuffix>search</mat-icon>
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
                    emptyText="No projects match these filters." (retry)="list.load()" />
    @if (handset()) {
      <div class="cards">
        @for (p of list.items(); track p.id) {
          <a class="card" [routerLink]="['/projects', p.id]">
            <div class="row"><strong>{{ p.name }}</strong><app-status-badge [status]="badge(p.status)" [text]="label(p.status)" /></div>
            <div class="muted small">{{ p.project_code }} · {{ p.farm_count }} farm(s) · {{ area(p.area_hectares) }}</div>
          </a>
        }
      </div>
    } @else {
      <div class="table-wrap" [hidden]="list.total() === 0">
        <table mat-table [dataSource]="list.items()" matSort (matSortChange)="list.onSort($event)" matSortActive="created_at" matSortDirection="desc">
          <ng-container matColumnDef="project_code">
            <th mat-header-cell *matHeaderCellDef mat-sort-header>Code</th>
            <td mat-cell *matCellDef="let p"><a [routerLink]="['/projects', p.id]">{{ p.project_code }}</a></td>
          </ng-container>
          <ng-container matColumnDef="name">
            <th mat-header-cell *matHeaderCellDef mat-sort-header>Name</th>
            <td mat-cell *matCellDef="let p">{{ p.name }}<div class="muted small">{{ p.organization_name }} · {{ p.region }}</div></td>
          </ng-container>
          <ng-container matColumnDef="route">
            <th mat-header-cell *matHeaderCellDef>Standard / activity</th>
            <td mat-cell *matCellDef="let p">{{ p.standard_name ?? '—' }}<div class="muted small">{{ p.activity_name ?? 'No activity yet' }}</div></td>
          </ng-container>
          <ng-container matColumnDef="farms">
            <th mat-header-cell *matHeaderCellDef>Farms</th>
            <td mat-cell *matCellDef="let p">{{ p.farm_count }}<div class="muted small">{{ area(p.area_hectares) }}</div></td>
          </ng-container>
          <ng-container matColumnDef="created_at">
            <th mat-header-cell *matHeaderCellDef mat-sort-header>Created</th>
            <td mat-cell *matCellDef="let p">{{ p.created_at.slice(0, 10) }}</td>
          </ng-container>
          <ng-container matColumnDef="status">
            <th mat-header-cell *matHeaderCellDef mat-sort-header>Status</th>
            <td mat-cell *matCellDef="let p"><app-status-badge [status]="badge(p.status)" [text]="label(p.status)" />
              @if (p.environment === 'DEMO') { <app-status-badge status="DEMO" /> }</td>
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
export class ProjectsListPage implements OnInit {
  private readonly api = inject(ProjectsApi);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);
  protected readonly canCreate = inject(AuthService).has(P.PROJECTS_MANAGE);
  protected readonly handset = toSignal(inject(BreakpointObserver).observe('(max-width: 700px)').pipe(map((r) => r.matches)),
    { initialValue: false });
  protected readonly label = label;
  protected readonly badge = projectBadge;
  protected readonly area = formatArea;
  protected readonly statuses = PHASE3_STATUSES;
  protected readonly columns = ['project_code', 'name', 'route', 'farms', 'created_at', 'status'];
  protected readonly filters = new FormGroup({
    search: new FormControl('', { nonNullable: true }),
    status: new FormControl<ProjectStatus | null>(null),
  });
  protected readonly list = new PagedList<ProjectSummary>((q) => {
    const f = this.filters.getRawValue();
    return this.api.list({ ...q, search: f.search.trim(), status: f.status });
  }, this.destroyRef, '-created_at');

  ngOnInit(): void {
    this.filters.valueChanges.pipe(debounceTime(300), takeUntilDestroyed(this.destroyRef)).subscribe(() => this.list.reset());
    this.list.load();
  }

  open(p: ProjectSummary): void {
    void this.router.navigate(['/projects', p.id]);
  }
}
