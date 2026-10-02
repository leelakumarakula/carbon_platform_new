import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, input, output, signal } from '@angular/core';
import { FormControl, FormGroup, FormGroupDirective, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';

import { NotifyService } from '../../core/notify.service';
import { label } from '../../farmer/farmer.models';
import { runAction } from '../../shared/run-action';
import { StatusBadge } from '../../shared/status-badge';
import { Baselines, CreditingPeriod, Project } from '../project.models';
import { ProjectsApi } from '../projects.api';

/**
 * Crediting period (proposed; methodology-specific rules are validated with the methodology later) and baseline
 * period metadata (versioned). Nothing is calculated here — no baseline emissions or removals.
 */
@Component({
  selector: 'app-project-periods-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, ReactiveFormsModule, MatButtonModule, MatFormFieldModule, MatInputModule, MatSelectModule, StatusBadge],
  template: `
    <div class="tab-body cols">
      <section>
        <h3>Crediting period</h3>
        @for (c of periods(); track c.id) {
          <div class="line">
            <div class="grow"><strong>#{{ c.period_number }}</strong> {{ c.start_date }} → {{ c.end_date }}
              <span class="muted small">({{ c.length_days }} days)</span>
              @if (c.notes) { <div class="muted small">{{ c.notes }}</div> }
              @if (c.status_reason) { <div class="muted small">{{ label(c.status) }}: {{ c.status_reason }}</div> }</div>
            <app-status-badge [status]="c.status === 'PROPOSED' ? 'INFO' : 'REVOKED'" [text]="label(c.status)" />
          </div>
        } @empty { <p class="muted">No crediting period recorded.</p> }
        @if (canEdit()) {
          <form [formGroup]="period" #pd="ngForm" (ngSubmit)="addPeriod(pd)" class="form">
            <mat-form-field subscriptSizing="dynamic"><mat-label>Start</mat-label><input matInput type="date" formControlName="start_date" /></mat-form-field>
            <mat-form-field subscriptSizing="dynamic"><mat-label>End</mat-label><input matInput type="date" formControlName="end_date" /></mat-form-field>
            @if (proposed().length) {
              <mat-form-field subscriptSizing="dynamic"><mat-label>Replaces (optional)</mat-label>
                <mat-select formControlName="replaces_id"><mat-option [value]="''">— none —</mat-option>
                  @for (c of proposed(); track c.id) { <mat-option [value]="c.id">#{{ c.period_number }} {{ c.start_date }} → {{ c.end_date }}</mat-option> }
                </mat-select></mat-form-field>
            }
            <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Notes / reason for replacing</mat-label><input matInput formControlName="notes" /></mat-form-field>
            <button mat-flat-button type="submit" [disabled]="busy() || period.invalid">Record period</button>
          </form>
          <p class="muted small">Stored as proposed. Length and start-date rules depend on the methodology and are checked when it is confirmed.</p>
        }
      </section>
      <section>
        <h3>Baseline period metadata</h3>
        @if (baseline(); as b) {
          @if (b.current; as c) {
            <dl class="kv">
              <dt>Period</dt><dd>{{ c.period_start }} → {{ c.period_end }}</dd>
              <dt>Description</dt><dd>{{ c.description ?? '—' }}</dd>
              <dt>Data sources</dt><dd>{{ c.data_sources ?? '—' }}</dd>
              <dt>Version</dt><dd>v{{ c.version }} · {{ c.created_at | date: 'medium' }}{{ c.change_reason ? ' · ' + c.change_reason : '' }}</dd>
            </dl>
          } @else { <p class="muted">No baseline metadata recorded.</p> }
          <p class="muted small">{{ b.note }}</p>
          @if (b.versions.length > 1) {
            <details><summary class="small">{{ b.versions.length }} versions</summary>
              <ul class="small">@for (v of b.versions; track v.id) { <li>v{{ v.version }}: {{ v.period_start }} → {{ v.period_end }}{{ v.change_reason ? ' — ' + v.change_reason : '' }}</li> }</ul>
            </details>
          }
          @if (canEdit()) {
            <form [formGroup]="base" (ngSubmit)="saveBaseline()" class="form">
              <mat-form-field subscriptSizing="dynamic"><mat-label>From</mat-label><input matInput type="date" formControlName="period_start" /></mat-form-field>
              <mat-form-field subscriptSizing="dynamic"><mat-label>To</mat-label><input matInput type="date" formControlName="period_end" /></mat-form-field>
              <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Baseline practices (description)</mat-label><input matInput formControlName="description" /></mat-form-field>
              <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Data sources</mat-label><input matInput formControlName="data_sources" /></mat-form-field>
              @if (b.current) { <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Reason for the change</mat-label><input matInput formControlName="reason" /></mat-form-field> }
              <button mat-flat-button type="submit" [disabled]="busy() || base.invalid">{{ b.current ? 'Save new version' : 'Record baseline' }}</button>
            </form>
          }
        }
      </section>
    </div>
  `,
  styles: `
    .cols { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; } @media (max-width: 900px) { .cols { grid-template-columns: 1fr; } }
    h3 { margin: 0 0 8px; font: var(--mat-sys-title-small); }
    .line { display: flex; align-items: center; gap: 10px; padding: 6px 0; border-bottom: 1px solid var(--mat-sys-outline-variant); }
    .grow { flex: 1; } .form { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 12px; } .wide { min-width: 220px; flex: 1; }
  `,
})
export class ProjectPeriodsPanel implements OnInit {
  readonly project = input.required<Project>();
  readonly changed = output<void>();
  private readonly api = inject(ProjectsApi);
  private readonly notify = inject(NotifyService);
  protected readonly label = label;
  protected readonly periods = signal<CreditingPeriod[]>([]);
  protected readonly baseline = signal<Baselines | null>(null);
  protected readonly busy = signal(false);
  protected readonly canEdit = computed(() => this.project().can_manage && this.project().is_editable);
  protected readonly proposed = computed(() => this.periods().filter((p) => p.status === 'PROPOSED'));
  protected readonly period = new FormGroup({
    start_date: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    end_date: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    replaces_id: new FormControl('', { nonNullable: true }),
    notes: new FormControl('', { nonNullable: true }),
  });
  protected readonly base = new FormGroup({
    period_start: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    period_end: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    description: new FormControl('', { nonNullable: true }),
    data_sources: new FormControl('', { nonNullable: true }),
    reason: new FormControl('', { nonNullable: true }),
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.api.creditingPeriods(this.project().id).subscribe((p) => this.periods.set(p));
    this.api.baseline(this.project().id).subscribe((b) => {
      this.baseline.set(b);
      if (b.current) this.base.patchValue({ period_start: b.current.period_start, period_end: b.current.period_end,
        description: b.current.description ?? '', data_sources: b.current.data_sources ?? '' });
    });
  }

  addPeriod(fd?: FormGroupDirective): void {
    const v = this.period.getRawValue();
    const notes = v.notes.trim() || null;
    runAction(this.api.addCreditingPeriod(this.project().id, { start_date: v.start_date, end_date: v.end_date, notes,
      replaces_id: v.replaces_id || null, reason: v.replaces_id ? notes : null }), this.busy, this.notify, 'Crediting period recorded.', () => {
      (fd ?? this.period).reset();
      this.load();
      this.changed.emit();
    });
  }

  saveBaseline(): void {
    const v = this.base.getRawValue();
    const blank = (s: string) => (s.trim() ? s.trim() : null);
    runAction(this.api.updateBaseline(this.project().id, { period_start: v.period_start, period_end: v.period_end, description: blank(v.description),
      data_sources: blank(v.data_sources), reason: blank(v.reason) }), this.busy, this.notify, 'Baseline metadata saved.', (b) => {
      this.baseline.set(b);
      this.base.controls.reason.setValue('');
      this.changed.emit();
    });
  }
}
