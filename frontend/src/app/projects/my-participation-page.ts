import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { MatCardModule } from '@angular/material/card';

import { ApiError } from '../core/api/api.models';
import { label } from '../farmer/farmer.models';
import { PageHeader } from '../shared/page-header';
import { StateView } from '../shared/state-view';
import { StatusBadge } from '../shared/status-badge';
import { MyParticipation } from './project.models';
import { ProjectsApi } from './projects.api';

/** Farmer self-service: the projects the farmer's own farms take part in, with the carbon-rights references
 *  recorded for them. Other farmers' data and project internals are never shown here. */
@Component({
  selector: 'app-my-participation-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatCardModule, PageHeader, StateView, StatusBadge],
  template: `
    <app-page-header title="My project participation" subtitle="Projects your farms take part in and the carbon-rights references recorded." />
    <app-state-view [loading]="loading()" [error]="error()" [empty]="!loading() && !error() && !rows().length"
                    emptyText="Your farms are not part of any project yet." (retry)="load()" />
    <div class="cards">
      @for (r of rows(); track r.project_id + r.farm_id) {
        <mat-card appearance="outlined">
          <mat-card-header>
            <mat-card-title>{{ r.project_name }}</mat-card-title>
            <mat-card-subtitle>{{ r.project_code }} · {{ label(r.project_status) }}</mat-card-subtitle>
          </mat-card-header>
          <mat-card-content>
            <p><strong>{{ r.farm_code }}</strong> {{ r.farm_name }} · {{ label(r.participation_status) }} from {{ r.participation_start }}
              {{ r.participation_end ? 'to ' + r.participation_end : '' }}</p>
            @for (c of r.carbon_rights; track c.id) {
              <div class="right">
                Carbon rights: <strong>{{ c.holder_name }}</strong> ({{ label(c.holder_type) }}{{ c.share_pct ? ', ' + c.share_pct + '%' : '' }})
                {{ c.agreement_number ? '· agreement ' + c.agreement_number : '' }}
                <app-status-badge [status]="c.verification_status === 'VERIFIED' ? 'ACTIVE' : 'WARNING'" [text]="label(c.verification_status)" />
                @if (c.status !== 'ACTIVE') { <app-status-badge status="REVOKED" [text]="label(c.status)" /> }
              </div>
            }
          </mat-card-content>
        </mat-card>
      }
    </div>
  `,
  styles: `.cards { display: grid; gap: 12px; } .right { font-size: 13px; margin-top: 4px; display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }`,
})
export class MyParticipationPage implements OnInit {
  private readonly api = inject(ProjectsApi);
  protected readonly label = label;
  protected readonly rows = signal<MyParticipation[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<ApiError | null>(null);

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.error.set(null);
    this.api.myParticipation().subscribe({
      next: (r) => {
        this.rows.set(r);
        this.loading.set(false);
      },
      error: (e: unknown) => {
        this.error.set(ApiError.from(e));
        this.loading.set(false);
      },
    });
  }
}
