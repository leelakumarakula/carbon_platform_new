import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, inject, input, output, signal } from '@angular/core';
import { FormControl, FormGroup, FormGroupDirective, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';

import { NotifyService } from '../../core/notify.service';
import { label } from '../../farmer/farmer.models';
import { MethodologiesApi } from '../../methodologies/methodologies.api';
import { Candidate, ProjectMethodologyView, SYSTEM_FACTS, confirmable, outcomeBadge, parseFactValue, show } from '../../methodologies/methodology.models';
import { askReason } from '../../shared/reason-dialog';
import { runAction } from '../../shared/run-action';
import { StatusBadge } from '../../shared/status-badge';
import { Project } from '../project.models';

/**
 * Project → candidate methodologies → specialist review → confirm → lock (spec section 9).
 * The rules engine only proposes; it never selects. Confirmation locks methodology + version; unlocking is explicit.
 */
@Component({
  selector: 'app-project-methodology-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, ReactiveFormsModule, MatButtonModule, MatExpansionModule, MatFormFieldModule, MatIconModule, MatInputModule, StatusBadge],
  template: `
    <div class="tab-body">
      @if (view(); as v) {
        @if (v.current; as c) {
          <div class="locked">
            <mat-icon>lock</mat-icon>
            <div class="grow">
              <strong>{{ c.methodology_code }} · version {{ c.version_label }}</strong> — {{ c.methodology_name }}
              <div class="muted small">Locked {{ c.locked_at | date: 'medium' }} · rules r{{ c.rules_version }}, monitoring r{{ c.monitoring_rules_version }},
                calculation r{{ c.calculation_rules_version }} · calculation: {{ label(c.calculation_readiness) }}</div>
              <div class="small">{{ c.confirmation_notes }}</div>
              @if (c.newer_version_available) { <div class="note">A newer approved version exists. The lock does not change unless you unlock and confirm again.</div> }
            </div>
            @if (v.can_unlock) { <button mat-stroked-button type="button" class="danger" (click)="unlock()" [disabled]="busy()">Unlock</button> }
          </div>
          @for (f of v.findings; track $index) { <p class="note warn">{{ f }}</p> }
        } @else {
          <p>Methodology: <app-status-badge [status]="v.methodology_status === 'UNDER_REVIEW' ? 'WARNING' : 'INFO'" [text]="label(v.methodology_status)" /></p>
        }

        @if (v.can_evaluate) {
          <form [formGroup]="fact" #fd="ngForm" (ngSubmit)="addFact(fd)" class="facts">
            <strong class="small">Declared facts (optional — recorded as DECLARED, evidence still required):</strong>
            @for (k of declaredKeys(); track k) { <span class="chip">{{ k }} = {{ show(declared()[k]) }} <button type="button" class="x" (click)="removeFact(k)">×</button></span> }
            <mat-form-field subscriptSizing="dynamic"><mat-label>Fact key</mat-label><input matInput formControlName="key" placeholder="additionality_assessment" /></mat-form-field>
            <mat-form-field subscriptSizing="dynamic"><mat-label>Value</mat-label><input matInput formControlName="value" placeholder="COMPLETED" /></mat-form-field>
            <button mat-button type="submit" [disabled]="fact.invalid">Add fact</button>
            <button mat-flat-button type="button" (click)="evaluate()" [disabled]="busy()"><mat-icon>rule</mat-icon> Evaluate candidates</button>
          </form>
          @if (factError(); as e) { <p class="form-error">{{ e }}</p> }
        }

        @if (v.latest_evaluation; as ev) {
          <p class="muted small">Evaluation {{ ev.evaluated_at | date: 'medium' }} · engine {{ ev.engine_version }} · {{ ev.candidate_count }} candidate(s)
            · {{ v.evaluation_count }} evaluation(s) kept. {{ ev.note }}</p>
          <mat-accordion multi>
            @for (c of ev.candidates; track c.id) {
              <mat-expansion-panel>
                <mat-expansion-panel-header>
                  <mat-panel-title>{{ c.methodology_code }} v{{ c.version_label }}</mat-panel-title>
                  <mat-panel-description>
                    <app-status-badge [status]="badge(c.outcome)" [text]="label(c.outcome)" />
                    @if (c.is_demo_illustrative) { <app-status-badge status="DEMO" text="Illustrative" /> }
                    @if (confirmable(c)) { <app-status-badge status="ACTIVE" text="Recommended" /> }
                  </mat-panel-description>
                </mat-expansion-panel-header>
                <div class="muted small">{{ c.methodology_name }} · version {{ label(c.version_status) }} · rules r{{ c.rules_version }}</div>
                <table class="simple">
                  <thead><tr><th>Rule</th><th>Fact</th><th>Expected</th><th>Actual</th><th>Result</th><th>Reason</th></tr></thead>
                  <tbody>@for (r of c.rules; track r.rule_code) {
                    <tr><td><strong>{{ r.rule_code }}</strong> {{ r.title }}<div class="muted small">{{ label(r.category) }}{{ r.source_reference ? ' · ' + r.source_reference : '' }}</div></td>
                      <td><code>{{ r.fact_key }}</code><div class="muted small">{{ r.fact_source ?? '' }}</div></td>
                      <td>{{ r.operator }} {{ show(r.expected) }}</td><td>{{ show(r.actual) }}</td>
                      <td><app-status-badge [status]="badge(r.effect)" [text]="r.check" /></td>
                      <td class="small">{{ r.reason }}@if (r.evidence_requirement) { <div class="muted">Evidence: {{ r.evidence_requirement }}</div> }</td></tr>
                  }</tbody>
                </table>
                @if (c.evidence_requirements.length) { <p class="small"><strong>Evidence required:</strong> {{ c.evidence_requirements.join('; ') }}</p> }
                @for (rv of c.reviews; track rv.id) {
                  <div class="small review">{{ label(rv.recommendation) }} by {{ rv.reviewer_name ?? 'specialist' }} · {{ rv.reviewed_at | date: 'medium' }} — {{ rv.notes }}</div>
                }
                <div class="actions">
                  @if (v.can_review) {
                    <button mat-stroked-button type="button" (click)="review(c, 'RECOMMENDED')" [disabled]="busy() || c.outcome === 'NOT_APPLICABLE' || c.outcome === 'NEEDS_INFORMATION'">Recommend</button>
                    <button mat-button type="button" (click)="review(c, 'NOT_RECOMMENDED')" [disabled]="busy()">Not recommended</button>
                  }
                  @if (v.can_confirm) {
                    <button mat-flat-button type="button" (click)="confirm(c)" [disabled]="busy() || !confirmable(c)"><mat-icon>lock</mat-icon> Confirm & lock</button>
                  }
                </div>
              </mat-expansion-panel>
            } @empty { <p class="muted">No approved methodology version matches this project's standard and activity.</p> }
          </mat-accordion>
          <details class="factlist"><summary class="small">Facts used ({{ factCount(ev.facts) }})</summary>
            <table class="simple"><tbody>@for (f of factRows(ev.facts); track f.key) {
              <tr><td><code>{{ f.key }}</code></td><td>{{ show(f.value) }}</td><td class="muted small">{{ f.source }} {{ f.detail }}</td></tr>
            }</tbody></table>
          </details>
        } @else if (!v.current) {
          <p class="muted">No candidates evaluated yet.{{ v.can_evaluate ? '' : ' Candidates can be evaluated once the activity is confirmed.' }}</p>
        }
      }
    </div>
  `,
  styles: `
    .locked { display: flex; gap: 12px; align-items: flex-start; padding: 12px; border-radius: 10px; background: #e8f5e9; margin-bottom: 12px; }
    .grow { flex: 1; }
    .note { padding: 6px 10px; border-radius: 8px; background: var(--mat-sys-surface-container); font-size: 13px; }
    .note.warn { background: #fff3e0; color: #e65100; }
    .facts { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 8px 0 12px; }
    .chip { font-size: 12px; padding: 2px 8px; border-radius: 999px; background: var(--mat-sys-surface-container-high); }
    .x { border: 0; background: none; cursor: pointer; }
    table.simple { width: 100%; border-collapse: collapse; margin: 8px 0; }
    table.simple th, table.simple td { text-align: left; padding: 6px; border-bottom: 1px solid var(--mat-sys-outline-variant); vertical-align: top; }
    .actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; } .review { margin-top: 4px; }
    .factlist { margin-top: 12px; }
  `,
})
export class ProjectMethodologyPanel implements OnInit {
  readonly project = input.required<Project>();
  readonly changed = output<void>();
  private readonly api = inject(MethodologiesApi);
  private readonly notify = inject(NotifyService);
  private readonly dialog = inject(MatDialog);
  protected readonly label = label;
  protected readonly badge = outcomeBadge;
  protected readonly show = show;
  protected readonly confirmable = confirmable;
  protected readonly view = signal<ProjectMethodologyView | null>(null);
  protected readonly busy = signal(false);
  protected readonly declared = signal<Record<string, unknown>>({});
  protected readonly factError = signal<string | null>(null);
  protected readonly fact = new FormGroup({
    key: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.pattern(/^[a-z][a-z0-9_]{1,59}$/)] }),
    value: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.api.projectView(this.project().id).subscribe((v) => this.view.set(v));
  }

  declaredKeys(): string[] {
    return Object.keys(this.declared());
  }

  factCount(f: Record<string, unknown>): number {
    return Object.keys(f).length;
  }

  factRows(f: Record<string, { value: unknown; source: string; detail: string }>): { key: string; value: unknown; source: string; detail: string }[] {
    return Object.entries(f).map(([key, x]) => ({ key, ...x }));
  }

  addFact(fd?: FormGroupDirective): void {
    const { key, value } = this.fact.getRawValue();
    if ((SYSTEM_FACTS as readonly string[]).includes(key)) {
      this.factError.set(`'${key}' comes from project data and cannot be declared.`);
      return;
    }
    this.factError.set(null);
    this.declared.update((d) => ({ ...d, [key]: parseFactValue(value) }));
    (fd ?? this.fact).reset();
  }

  removeFact(key: string): void {
    this.declared.update((d) => Object.fromEntries(Object.entries(d).filter(([k]) => k !== key)));
  }

  evaluate(): void {
    runAction(this.api.evaluate(this.project().id, this.declared()), this.busy, this.notify, 'Candidates evaluated.', () => {
      this.load();
      this.changed.emit();
    });
  }

  review(c: Candidate, recommendation: 'RECOMMENDED' | 'NOT_RECOMMENDED'): void {
    const evidence = recommendation === 'RECOMMENDED' && c.outcome === 'EVIDENCE_REQUIRED';
    askReason(this.dialog, {
      title: recommendation === 'RECOMMENDED' ? `Recommend ${c.methodology_code} v${c.version_label}?` : `Not recommended: ${c.methodology_code} v${c.version_label}?`,
      message: evidence ? `By recommending, you confirm this evidence has been checked or requested: ${c.evidence_requirements.join('; ')}.`
        : 'Record your professional assessment; the project developer confirms.',
      confirmLabel: recommendation === 'RECOMMENDED' ? 'Recommend' : 'Record',
    }).subscribe((r) => {
      if (r) runAction(this.api.review(this.project().id, { evaluation_result_id: c.id, recommendation, notes: r.reason, evidence_acknowledged: evidence }),
        this.busy, this.notify, 'Review recorded.', () => this.load());
    });
  }

  confirm(c: Candidate): void {
    askReason(this.dialog, { title: `Confirm and lock ${c.methodology_code} version ${c.version_label}?`, confirmLabel: 'Confirm & lock',
      message: 'The methodology and version are locked for this project. Changing them later requires an explicit, audited unlock.' }).subscribe((r) => {
      if (r) runAction(this.api.confirm(this.project().id, c.id, r.reason), this.busy, this.notify, 'Methodology confirmed and locked.', (v) => {
        this.view.set(v);
        this.changed.emit();
      });
    });
  }

  unlock(): void {
    askReason(this.dialog, { title: 'Unlock the methodology?', confirmLabel: 'Unlock', danger: true,
      message: 'The lock is ended (kept in history) and the project returns to methodology review.' }).subscribe((r) => {
      if (r) runAction(this.api.unlock(this.project().id, r.reason), this.busy, this.notify, 'Methodology unlocked.', (v) => {
        this.view.set(v);
        this.changed.emit();
      });
    });
  }
}
