import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, effect, inject, input, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { RouterLink } from '@angular/router';

import { CalcReadinessPanel } from '../../calculation/calc-readiness-panel';
import { CalculationApi } from '../../calculation/calculation.api';
import { CALCULATED_LABEL, CalcRun, DEMO_LABEL, Readiness, blockerTitle, calcBadge, formatValue } from '../../calculation/calculation.models';
import { AuthService } from '../../core/auth/auth.service';
import { P } from '../../core/auth/permissions';
import { NotifyService } from '../../core/notify.service';
import { label } from '../../farmer/farmer.models';
import { runAction } from '../../shared/run-action';
import { StatusBadge } from '../../shared/status-badge';
import { Period } from '../mrv.models';

/** Phase 7 project side: readiness (the actual blockers, nothing pretended) and the calculation runs of the selected period. */
@Component({
  selector: 'app-mrv-calculations-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, RouterLink, MatButtonModule, StatusBadge, CalcReadinessPanel],
  template: `
    <div class="tab-body">
      <p class="note">{{ calculatedLabel }}. A calculation never creates credits; verification and issuance are later steps.</p>
      @if (!period()) { <p class="muted">Select a monitoring period.</p> }
      @if (readiness(); as r) {
        @if (r.environment === 'DEMO' || r.is_demo_illustrative) { <p class="note warn" data-testid="demo-label">{{ demoLabel }}</p> }
        <h3>Readiness · {{ r.monitoring_period }}</h3>
        <div class="kv small">Methodology {{ r.methodology_label ?? '—' }} · module {{ r.module_code ? r.module_code + ' ' + r.module_version : 'none registered' }}
          · dataset {{ r.dataset_code ?? '—' }} {{ r.dataset_status ? '(' + label(r.dataset_status) + ')' : '' }}</div>
        @if (r.ready) {
          <p class="ok" data-testid="calc-ready">Ready: {{ r.input_rows }} input rows would be frozen.</p>
        } @else {
          <ul class="blockers" data-testid="calc-blockers">
            @for (b of r.blockers; track $index) { <li><strong>{{ title(b) }}</strong> — {{ b.message }}</li> }
          </ul>
        }
        @for (w of r.warnings; track $index) { <p class="small warn">{{ w }}</p> }
        <div class="steps">
          @for (s of r.steps; track s.step) { <span class="step"><app-status-badge [status]="badge(s.status)" [text]="s.step + ': ' + s.label" /></span> }
        </div>
        @if (canManage) {
          <button mat-flat-button type="button" [disabled]="busy()" (click)="create()" data-testid="create-run">New calculation run</button>
        }
      }
      <h3>Calculation runs</h3>
      <div class="table-wrap"><table class="table">
        <thead><tr><th>Run</th><th>Status</th><th>Result</th><th>Module</th><th>Created</th></tr></thead>
        <tbody>
          @for (x of runs(); track x.id) {
            <tr><td><a [routerLink]="['/calculations/runs', x.id]" [attr.data-run]="x.run_code">{{ x.run_code }}</a>
                {{ x.recalculation_of_code ? '(recalculates ' + x.recalculation_of_code + ')' : '' }}</td>
              <td><app-status-badge [status]="badge(x.status)" [text]="label(x.status)" /></td>
              <td>{{ x.net_result ? value(x.net_result) + ' ' + x.net_unit : (x.blockers.length ? title(x.blockers[0]) : '—') }}</td>
              <td>{{ x.module_code ?? '—' }}</td><td>{{ x.created_at | date: 'short' }} · {{ x.created_by_name }}</td></tr>
          } @empty { <tr><td colspan="5" class="muted">No calculation run for this period.</td></tr> }
        </tbody>
      </table></div>
      @if (period(); as p) { <app-calc-readiness-panel [projectId]="projectId()" [periodId]="p.id" /> }
    </div>
  `,
  styles: `h3 { margin: 14px 0 6px; font: var(--mat-sys-title-small); } .blockers { margin: 6px 0; padding-left: 20px; }
    .blockers li { margin: 3px 0; } .steps { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0 12px; } .ok { color: var(--mat-sys-primary); }`,
})
export class MrvCalculationsPanel {
  readonly projectId = input.required<string>();
  readonly period = input<Pick<Period, 'id'> | null>(null);
  private readonly api = inject(CalculationApi);
  private readonly notify = inject(NotifyService);
  protected readonly canManage = inject(AuthService).has(P.CALCULATION_MANAGE);
  protected readonly label = label;
  protected readonly badge = calcBadge;
  protected readonly title = blockerTitle;
  protected readonly value = formatValue;
  protected readonly calculatedLabel = CALCULATED_LABEL;
  protected readonly demoLabel = DEMO_LABEL;
  protected readonly readiness = signal<Readiness | null>(null);
  protected readonly runs = signal<CalcRun[]>([]);
  protected readonly busy = signal(false);

  constructor() {
    effect(() => {
      const p = this.period();
      this.readiness.set(null);
      this.runs.set([]);
      if (p) this.load(p.id);
    });
  }

  private load(periodId: string): void {
    this.api.readiness(this.projectId(), periodId).subscribe((r) => this.readiness.set(r));
    this.api.runs(this.projectId(), periodId).subscribe((r) => this.runs.set(r));
  }

  protected create(): void {
    const p = this.period();
    if (p) runAction(this.api.create(this.projectId(), p.id), this.busy, this.notify, 'Calculation run created.', () => this.load(p.id));
  }
}
