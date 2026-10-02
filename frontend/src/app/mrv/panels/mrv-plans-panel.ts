import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { RouterLink } from '@angular/router';

import { AuthService } from '../../core/auth/auth.service';
import { P } from '../../core/auth/permissions';
import { label } from '../../farmer/farmer.models';
import { StatusBadge } from '../../shared/status-badge';
import { MrvApi } from '../mrv.api';
import { Plan, Requirements, mrvBadge } from '../mrv.models';

/** MRV plan list (versions). Approved plans are never edited; a change is a new plan version. */
@Component({
  selector: 'app-mrv-plans-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, RouterLink, MatButtonModule, StatusBadge],
  template: `
    <div class="tab-body">
      <div class="bar">
        <h3>MRV plans</h3>
        @if (canCreate()) {
          <a mat-flat-button [routerLink]="['/mrv/projects', projectId(), 'plans', 'new']" data-testid="new-plan">
            {{ plans().length ? 'New plan version' : 'Create MRV plan' }}</a>
        }
      </div>
      <table class="table">
        <thead><tr><th>Version</th><th>Status</th><th>Methodology version</th><th>Quantification</th><th>Window</th><th>Measurements</th><th>Configuration</th><th></th></tr></thead>
        <tbody>
          @for (x of plans(); track x.id) {
            <tr>
              <td>v{{ x.plan_version }}</td>
              <td><app-status-badge [status]="badge(x.status)" [text]="label(x.status)" /></td>
              <td>{{ x.methodology_label }}</td>
              <td>{{ label(x.quantification_approach) }}</td>
              <td>{{ x.monitoring_start ?? '—' }} → {{ x.monitoring_end ?? '—' }}</td>
              <td>{{ x.measurements.length }}</td>
              <td><app-status-badge [status]="badge(x.configuration_status)" [text]="label(x.configuration_status)" /></td>
              <td><a mat-button [routerLink]="['/mrv/plans', x.id]">Open</a></td>
            </tr>
          } @empty { <tr><td colspan="8" class="muted">No MRV plan yet.</td></tr> }
        </tbody>
      </table>
      @if (requirements(); as r) {
        <h3>Methodology monitoring requirements (locked version)</h3>
        <ul class="small">
          @for (m of r.monitoring; track m.rule_code) { <li><strong>{{ m.rule_code }}</strong> {{ m.parameter ?? m.title }}{{ m.unit ? ' (' + m.unit + ')' : '' }}{{ m.frequency ? ' · ' + m.frequency : '' }}</li> }
          @empty { <li class="muted">No monitoring rules configured.</li> }
        </ul>
        <p class="muted small">Approved {{ approvedAt() ? (approvedAt() | date: 'medium') : '—' }}. Plans copy these requirements; the platform never invents sampling rules.</p>
      }
    </div>
  `,
  styles: `.bar { display: flex; align-items: center; gap: 12px; } .bar h3 { flex: 1; } h3 { margin: 12px 0 8px; font: var(--mat-sys-title-small); }`,
})
export class MrvPlansPanel implements OnInit {
  readonly projectId = input.required<string>();
  readonly requirements = input<Requirements | null>(null);
  private readonly api = inject(MrvApi);
  private readonly auth = inject(AuthService);
  protected readonly label = label;
  protected readonly badge = mrvBadge;
  protected readonly plans = signal<Plan[]>([]);
  protected readonly canCreate = computed(() => this.auth.has(P.MRV_MANAGE) && !this.plans().some((x) => ['DRAFT', 'SUBMITTED'].includes(x.status)));
  protected readonly approvedAt = computed(() => this.plans().find((x) => x.status === 'APPROVED')?.approved_at ?? null);

  ngOnInit(): void {
    this.api.plans(this.projectId()).subscribe((x) => this.plans.set(x));
  }
}
