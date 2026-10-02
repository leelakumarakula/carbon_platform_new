import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { RouterLink } from '@angular/router';

import { AuthService } from '../../core/auth/auth.service';
import { P } from '../../core/auth/permissions';
import { NotifyService } from '../../core/notify.service';
import { label } from '../../farmer/farmer.models';
import { runAction } from '../../shared/run-action';
import { StatusBadge } from '../../shared/status-badge';
import { MrvApi } from '../mrv.api';
import { Dataset, Period, mrvBadge } from '../mrv.models';

/** Versioned MRV datasets (one per period version). Approved datasets are immutable; corrections create a new version. */
@Component({
  selector: 'app-mrv-datasets-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, FormsModule, RouterLink, MatButtonModule, MatFormFieldModule, MatSelectModule, StatusBadge],
  template: `
    <div class="tab-body">
      <div class="table-wrap"><table class="table">
        <thead><tr><th>Dataset</th><th>Period</th><th>Plan</th><th>Status</th><th>Snapshot</th><th>Submitted</th><th>Approved</th><th></th></tr></thead>
        <tbody>
          @for (d of items(); track d.id) {
            <tr>
              <td><strong>{{ d.dataset_code }}</strong>@if (d.environment === 'DEMO') { <app-status-badge status="DEMO" /> }</td>
              <td>{{ d.monitoring_period_name }}</td><td>v{{ d.plan_version }}</td>
              <td><app-status-badge [status]="badge(d.status)" [text]="label(d.status)" /></td>
              <td class="small">@if (d.snapshot_summary; as s) { {{ s['sampling_points'] }} points · {{ s['field_collections'] }} collections · {{ s['monitoring_records'] }} records }
                @else { — }</td>
              <td>{{ d.submitted_at ? (d.submitted_at | date: 'mediumDate') : '—' }}</td><td>{{ d.approved_at ? (d.approved_at | date: 'mediumDate') : '—' }}</td>
              <td><a mat-button [routerLink]="['/mrv/datasets', d.id]">Open / QA</a></td>
            </tr>
          } @empty { <tr><td colspan="8" class="muted">No MRV dataset yet.</td></tr> }
        </tbody>
      </table></div>
      @if (canManage && openable().length) {
        <div class="create">
          <mat-form-field subscriptSizing="dynamic"><mat-label>Monitoring period</mat-label>
            <mat-select [(ngModel)]="periodId">@for (p of openable(); track p.id) { <mat-option [value]="p.id">#{{ p.period_number }} {{ p.name }} · {{ label(p.status) }}</mat-option> }</mat-select>
          </mat-form-field>
          <button mat-flat-button type="button" [disabled]="busy() || !periodId" (click)="create()">Create dataset version</button>
        </div>
        <p class="muted small">A new version after approval or rejection re-opens the period for data collection; the approved version stays unchanged.</p>
      }
    </div>
  `,
  styles: `.create { display: flex; gap: 8px; align-items: center; margin-top: 12px; flex-wrap: wrap; }`,
})
export class MrvDatasetsPanel implements OnInit {
  readonly projectId = input.required<string>();
  readonly periods = input<Period[]>([]);
  readonly changed = output<void>();
  private readonly api = inject(MrvApi);
  private readonly notify = inject(NotifyService);
  protected readonly canManage = inject(AuthService).has(P.MRV_MANAGE);
  protected readonly label = label;
  protected readonly badge = mrvBadge;
  protected readonly busy = signal(false);
  protected readonly items = signal<Dataset[]>([]);
  protected periodId = '';
  protected readonly openable = computed(() => {
    const open = new Set(this.items().filter((d) => ['DRAFT', 'COLLECTING', 'SUBMITTED', 'QA_REVIEW'].includes(d.status)).map((d) => d.monitoring_period_id));
    return this.periods().filter((p) => ['ACTIVE', 'DATA_COLLECTION', 'REJECTED', 'APPROVED'].includes(p.status) && !open.has(p.id));
  });

  ngOnInit(): void {
    this.load();
  }

  private load(): void {
    this.api.datasets(this.projectId()).subscribe((d) => this.items.set(d));
  }

  protected create(): void {
    runAction(this.api.createDataset(this.periodId), this.busy, this.notify, 'Dataset version created.', () => { this.load(); this.changed.emit(); });
  }
}
