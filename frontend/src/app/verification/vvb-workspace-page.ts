import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { label } from '../farmer/farmer.models';
import { PageHeader } from '../shared/page-header';
import { StatusBadge } from '../shared/status-badge';
import { VvbApi } from './verification.api';
import { Assignment, assignmentBadge } from './verification.models';

/** VVB / ACVA workspace: only the assignments of the caller's own VVB organization (no generic project, farmer or audit access). */
@Component({
  selector: 'app-vvb-workspace-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, RouterLink, PageHeader, StatusBadge],
  template: `
    <app-page-header title="VVB workspace" subtitle="Verification assignments of your organization — the platform records your decision; it does not verify" />
    <div class="table-wrap"><table class="table" data-testid="vvb-assignments">
      <thead><tr><th>Assignment</th><th>Project</th><th>Monitoring period</th><th>Status</th><th>Package</th><th>Proposed</th></tr></thead>
      <tbody>
        @for (a of rows(); track a.id) {
          <tr [attr.data-assignment]="a.assignment_code">
            <td><a [routerLink]="['/vvb/assignments', a.id]">{{ a.assignment_code }}</a></td>
            <td>{{ a.project_code }} · {{ a.project_name }}</td>
            <td>#{{ a.period_number }} ({{ a.period_start }} – {{ a.period_end }})</td>
            <td><app-status-badge [status]="badge(a.status)" [text]="label(a.status)" /></td>
            <td>{{ a.current_submission ? a.current_submission.submission_code : '—' }}</td>
            <td>{{ a.proposed_at | date: 'short' }}</td>
          </tr>
        } @empty { <tr><td colspan="6" class="muted" data-testid="vvb-empty">No assignment for your organization.</td></tr> }
      </tbody>
    </table></div>
  `,
})
export class VvbWorkspacePage implements OnInit {
  private readonly api = inject(VvbApi);
  protected readonly label = label;
  protected readonly badge = assignmentBadge;
  protected readonly rows = signal<Assignment[]>([]);

  ngOnInit(): void {
    this.api.assignments().subscribe((r) => this.rows.set(r));
  }
}
