import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, inject, input, signal } from '@angular/core';

import { label } from '../../farmer/farmer.models';
import { MrvApi } from '../mrv.api';
import { MrvHistoryEntry } from '../mrv.models';

/** MRV audit trail of the project (plans, periods, strata, sampling, field records, datasets, QA). Append-only. */
@Component({
  selector: 'app-mrv-history-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe],
  template: `
    <div class="tab-body">
      <div class="table-wrap"><table class="table">
        <thead><tr><th>When</th><th>Event</th><th>By</th><th>Reason</th></tr></thead>
        <tbody>
          @for (h of items(); track h.id) {
            <tr><td>{{ h.occurred_at | date: 'medium' }}</td><td>{{ label(h.action) }}</td><td>{{ h.user_email ?? 'system' }}</td><td>{{ h.reason ?? '—' }}</td></tr>
          } @empty { <tr><td colspan="4" class="muted">No MRV activity yet.</td></tr> }
        </tbody>
      </table></div>
    </div>
  `,
})
export class MrvHistoryPanel implements OnInit {
  readonly projectId = input.required<string>();
  private readonly api = inject(MrvApi);
  protected readonly label = label;
  protected readonly items = signal<MrvHistoryEntry[]>([]);

  ngOnInit(): void {
    this.api.history(this.projectId()).subscribe((h) => this.items.set(h));
  }
}
