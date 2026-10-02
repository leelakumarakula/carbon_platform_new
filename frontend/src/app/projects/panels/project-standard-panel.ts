import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, input, output, signal } from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';

import { NotifyService } from '../../core/notify.service';
import { label } from '../../farmer/farmer.models';
import { runAction } from '../../shared/run-action';
import { Project, ProjectActivities, ProjectStandards } from '../project.models';
import { ProjectsApi } from '../projects.api';

/** Standard / crediting route and activity references (spec section 9). Selecting them runs no methodology rules:
 *  candidate methodologies, applicability and confirmation belong to the methodology module (Phase 4). */
@Component({
  selector: 'app-project-standard-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, ReactiveFormsModule, MatButtonModule, MatFormFieldModule, MatSelectModule],
  template: `
    <div class="tab-body cols">
      <section>
        <h3>Standard / crediting route</h3>
        @if (stds(); as s) {
          @if (s.current; as c) {
            <p><strong>{{ c.name }}</strong> <span class="muted small">{{ c.code }} · {{ label(c.program_type) }}{{ c.owner_name ? ' · ' + c.owner_name : '' }}</span></p>
            @if (c.source_url) { <p class="small"><a [href]="c.source_url" target="_blank" rel="noopener noreferrer">Official source</a></p> }
          } @else { <p class="muted">Not selected.</p> }
          @if (canEditStandard()) {
            <div class="pick">
              <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Standard / route</mat-label>
                <mat-select [formControl]="standard">@for (o of s.available; track o.id) { <mat-option [value]="o.id">{{ o.name }}</mat-option> }</mat-select>
              </mat-form-field>
              <button mat-flat-button type="button" (click)="selectStandard()" [disabled]="busy() || !standard.value">Select</button>
            </div>
          }
          <ul class="hist">@for (h of s.history; track h.id) {
            <li [class.old]="!h.is_current">{{ h.name }} · {{ h.selected_at | date: 'medium' }}{{ h.is_current ? ' (current)' : '' }}{{ h.reason ? ' — ' + h.reason : '' }}</li>
          }</ul>
        }
      </section>
      <section>
        <h3>Activity</h3>
        @if (acts(); as a) {
          @if (a.current; as c) { <p><strong>{{ c.name }}</strong> <span class="muted small">{{ c.code }}</span></p> }
          @else { <p class="muted">{{ project().standard_id ? 'Not selected.' : 'Select a standard first.' }}</p> }
          @if (canEditActivity() && project().standard_id) {
            <div class="pick">
              <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Activity offered under the standard</mat-label>
                <mat-select [formControl]="activity">@for (o of a.available; track o.id) { <mat-option [value]="o.id">{{ o.name }}</mat-option> }</mat-select>
              </mat-form-field>
              <button mat-flat-button type="button" (click)="selectActivity()" [disabled]="busy() || !activity.value">Select</button>
            </div>
          }
          <ul class="hist">@for (h of a.history; track h.id) {
            <li [class.old]="!h.is_current">{{ h.name }} · {{ h.selected_at | date: 'medium' }}{{ h.is_current ? ' (current)' : '' }}</li>
          }</ul>
          <div class="method">
            <strong>Methodology:</strong> {{ label(a.methodology_status) }}
            <div class="muted small">Methodology candidates, applicability checks and confirmation are not part of this phase.</div>
          </div>
        }
      </section>
    </div>
  `,
  styles: `
    .cols { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; } @media (max-width: 900px) { .cols { grid-template-columns: 1fr; } }
    h3 { margin: 0 0 8px; font: var(--mat-sys-title-small); } .pick { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    .wide { min-width: 260px; flex: 1; } .hist { padding-left: 18px; font-size: 13px; } .old { color: var(--mat-sys-on-surface-variant); }
    .method { margin-top: 12px; padding: 10px; border-radius: 8px; background: var(--mat-sys-surface-container); }
  `,
})
export class ProjectStandardPanel implements OnInit {
  readonly project = input.required<Project>();
  readonly changed = output<Project>();
  private readonly api = inject(ProjectsApi);
  private readonly notify = inject(NotifyService);
  protected readonly label = label;
  protected readonly stds = signal<ProjectStandards | null>(null);
  protected readonly acts = signal<ProjectActivities | null>(null);
  protected readonly busy = signal(false);
  protected readonly standard = new FormControl('', { nonNullable: true });
  protected readonly activity = new FormControl('', { nonNullable: true });
  protected readonly canEditStandard = computed(() => this.project().can_manage && ['DRAFT', 'DATA_COLLECTION'].includes(this.project().status));
  protected readonly canEditActivity = computed(() => this.project().can_manage &&
    ['DRAFT', 'DATA_COLLECTION', 'STANDARD_SELECTED'].includes(this.project().status));

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.api.standards(this.project().id).subscribe((s) => this.stds.set(s));
    this.api.activities(this.project().id).subscribe((a) => this.acts.set(a));
  }

  selectStandard(): void {
    runAction(this.api.selectStandard(this.project().id, this.standard.value), this.busy, this.notify, 'Standard / route selected.', (p) => {
      this.changed.emit(p);
      this.load();
    });
  }

  selectActivity(): void {
    runAction(this.api.selectActivity(this.project().id, this.activity.value), this.busy, this.notify, 'Activity selected.', (p) => {
      this.changed.emit(p);
      this.load();
    });
  }
}
