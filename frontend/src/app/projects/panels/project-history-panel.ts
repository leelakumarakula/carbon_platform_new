import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, inject, input, signal } from '@angular/core';

import { label } from '../../farmer/farmer.models';
import { Project, StatusHistoryEntry } from '../project.models';
import { ProjectsApi } from '../projects.api';

/** Append-only project status history: who moved the project, when, why, and the request it came from. */
@Component({
  selector: 'app-project-history-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe],
  template: `
    <div class="tab-body">
      <ol class="timeline">
        @for (h of history(); track h.id) {
          <li>
            <div><strong>{{ label(h.to_status) }}</strong> <span class="muted small">{{ h.from_status ? 'from ' + label(h.from_status) : '' }} · {{ label(h.action) }}</span></div>
            <div class="muted small">{{ h.changed_at | date: 'medium' }} · {{ h.changed_by_name ?? 'system' }}
              @if (h.request_id) { · request {{ h.request_id }} }</div>
            @if (h.reason) { <div class="reason">{{ h.reason }}</div> }
          </li>
        }
      </ol>
    </div>
  `,
  styles: `
    .timeline { list-style: none; padding: 0; margin: 0; border-left: 2px solid var(--mat-sys-outline-variant); }
    .timeline li { position: relative; padding: 0 0 14px 16px; }
    .timeline li::before { content: ''; position: absolute; left: -6px; top: 4px; width: 10px; height: 10px; border-radius: 50%; background: #2e7d32; }
    .reason { margin-top: 2px; font-size: 13px; }
  `,
})
export class ProjectHistoryPanel implements OnInit {
  readonly project = input.required<Project>();
  private readonly api = inject(ProjectsApi);
  protected readonly label = label;
  protected readonly history = signal<StatusHistoryEntry[]>([]);

  ngOnInit(): void {
    this.api.statusHistory(this.project().id).subscribe((h) => this.history.set(h));
  }
}
