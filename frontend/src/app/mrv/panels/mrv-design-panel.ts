import { ChangeDetectionStrategy, Component, computed, effect, inject, input, output, signal } from '@angular/core';
import { FormArray, FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';

import { AuthService } from '../../core/auth/auth.service';
import { P } from '../../core/auth/permissions';
import { NotifyService } from '../../core/notify.service';
import { label } from '../../farmer/farmer.models';
import { askReason } from '../../shared/reason-dialog';
import { runAction } from '../../shared/run-action';
import { StatusBadge } from '../../shared/status-badge';
import { MrvApi } from '../mrv.api';
import { DESIGNS, Design, DesignVersion, Period, RuleSource, Stratum, mrvBadge, ruleSourceLabel } from '../mrv.models';

/**
 * Sampling design per monitoring period. Sample counts are configured per stratum (no "1 sample per X acres" rule);
 * values the methodology version configures are enforced by the server, everything else is CONFIGURATION_REQUIRED.
 */
@Component({
  selector: 'app-mrv-design-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, MatButtonModule, MatFormFieldModule, MatInputModule, MatSelectModule, StatusBadge],
  template: `
    <div class="tab-body">
      @if (!period()) { <p class="muted">Create a monitoring period first.</p> }
      @for (d of designs(); track d.id) {
        <section class="design">
          <div class="row"><strong>{{ d.code }}</strong> {{ d.name }} <span class="muted small">· {{ d.monitoring_period_name }} · {{ d.point_count }} point(s)</span></div>
          @for (v of d.versions; track v.id) {
            <div class="version">
              <div class="row">v{{ v.version }} <app-status-badge [status]="badge(v.status)" [text]="label(v.status)" />
                <app-status-badge [status]="badge(v.configuration_status)" [text]="label(v.requirement_source) + ' · ' + label(v.configuration_status)" /></div>
              <dl class="kv small">
                <dt>Statistical design</dt><dd>{{ label(v.statistical_design) }}{{ v.sampling_method ? ' · ' + v.sampling_method : '' }}</dd>
                <dt>Depth</dt><dd>{{ v.depth_top_cm }}–{{ v.depth_bottom_cm }} cm</dd>
                <dt>Precision / confidence</dt><dd>{{ v.target_precision_pct ?? '—' }}% / {{ v.confidence_level_pct ?? '—' }}%</dd>
                <dt>Min. distance · seed</dt><dd>{{ v.min_distance_m ?? '—' }} m · {{ v.random_seed }}</dd>
                <dt>Allocation</dt><dd>@for (a of v.allocations; track a.stratum_id) { {{ a.stratum_code }}: {{ a.sample_count }} ({{ a.stratum_area_hectares ?? '?' }} ha); }</dd>
                @if (v.configuration_gaps.length) { <dt>CONFIGURATION_REQUIRED</dt><dd>{{ v.configuration_gaps.join('; ') }}</dd> }
                @if (v.field_rules; as fr) {
                  <dt>Field rules (frozen)</dt>
                  <dd>GPS {{ fr.gps_tolerance_m }} m ({{ src(fr.gps_tolerance_source) }}) · duplicates &lt; {{ fr.duplicate_distance_m }} m
                    ({{ src(fr.duplicate_distance_source) }}) · checklist {{ fr.checklist_version }} ({{ src(fr.checklist_source) }}) ·
                    ≥ {{ fr.min_photos }} photo(s) ({{ src(fr.min_photos_source) }})</dd>
                }
              </dl>
              <div class="actions">
                @if (canReview && v.status === 'DRAFT') { <button mat-stroked-button type="button" [disabled]="busy()" (click)="approve(d, v)">Approve design</button> }
                @if (canManage && v.status === 'APPROVED' && !v.points_generated_at) {
                  <button mat-flat-button type="button" [disabled]="busy()" (click)="generate(d)" data-testid="generate-points">Generate sampling points</button>
                }
                @if (v.points_generated_at) { <span class="muted small">Points generated (SQL Server validated).</span> }
              </div>
            </div>
          }
        </section>
      } @empty { @if (period()) { <p class="muted">No sampling design for this period.</p> } }
      @if (canManage && period()) {
        <h3>New sampling design</h3>
        <form [formGroup]="form" (ngSubmit)="create()" class="form-grid">
          <mat-form-field subscriptSizing="dynamic"><mat-label>Code</mat-label><input matInput formControlName="code" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Name</mat-label><input matInput formControlName="name" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Statistical design</mat-label>
            <mat-select formControlName="statistical_design">@for (x of designTypes; track x) { <mat-option [value]="x">{{ label(x) }}</mat-option> }</mat-select></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Sampling method</mat-label><input matInput formControlName="sampling_method" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Depth top (cm)</mat-label><input matInput type="number" formControlName="depth_top_cm" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Depth bottom (cm)</mat-label><input matInput type="number" formControlName="depth_bottom_cm" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Target precision (%)</mat-label><input matInput type="number" formControlName="target_precision_pct" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Confidence level (%)</mat-label><input matInput type="number" formControlName="confidence_level_pct" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Min. distance between points (m)</mat-label><input matInput type="number" formControlName="min_distance_m" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Random seed (optional)</mat-label><input matInput type="number" formControlName="random_seed" /></mat-form-field>
          <div class="span-all small muted">Samples per approved stratum (configured by you or required by the methodology):</div>
          @for (c of counts.controls; track $index; let i = $index) {
            <mat-form-field subscriptSizing="dynamic"><mat-label>{{ approved()[i]?.code }} · {{ approved()[i]?.area_hectares }} ha</mat-label>
              <input matInput type="number" min="0" [formControl]="c" [attr.data-testid]="'count-' + approved()[i]?.code" /></mat-form-field>
          }
          <div class="span-all"><button mat-flat-button type="submit" [disabled]="busy() || form.invalid || !total()">Create design ({{ total() }} samples)</button></div>
        </form>
        @if (!approved().length) { <p class="muted small">Approve at least one stratum first.</p> }
      }
    </div>
  `,
  styles: `
    .design { border: 1px solid var(--mat-sys-outline-variant); border-radius: 8px; padding: 10px 14px; margin-bottom: 12px; }
    .version { border-top: 1px dashed var(--mat-sys-outline-variant); padding-top: 8px; margin-top: 8px; }
    .row { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; } .actions { display: flex; gap: 8px; align-items: center; }
    h3 { margin: 16px 0 8px; font: var(--mat-sys-title-small); }
  `,
})
export class MrvDesignPanel {
  readonly projectId = input.required<string>();
  readonly period = input<Period | null>(null);
  readonly strata = input<Stratum[]>([]);
  readonly changed = output<void>();
  private readonly api = inject(MrvApi);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotifyService);
  private readonly auth = inject(AuthService);
  protected readonly canManage = this.auth.has(P.SAMPLING_MANAGE);
  protected readonly canReview = this.auth.has(P.SAMPLING_REVIEW);
  protected readonly label = label;
  protected readonly badge = mrvBadge;
  protected readonly designTypes = DESIGNS;
  protected readonly busy = signal(false);
  protected readonly designs = signal<Design[]>([]);
  protected readonly approved = computed(() => this.strata().filter((s) => s.status === 'APPROVED' && s.is_current));
  protected readonly counts = new FormArray<FormControl<number>>([]);
  private readonly countValues = signal<number[]>([]);
  protected readonly total = computed(() => this.countValues().reduce((a, b) => a + (Number(b) || 0), 0));
  protected readonly form = new FormGroup({
    code: new FormControl('SOIL-1', { nonNullable: true, validators: [Validators.required] }),
    name: new FormControl('Soil sampling design', { nonNullable: true, validators: [Validators.required, Validators.minLength(2)] }),
    statistical_design: new FormControl('STRATIFIED_RANDOM', { nonNullable: true }),
    sampling_method: new FormControl('', { nonNullable: true }),
    depth_top_cm: new FormControl<number | null>(0, { validators: [Validators.required] }),
    depth_bottom_cm: new FormControl<number | null>(30, { validators: [Validators.required] }),
    target_precision_pct: new FormControl<number | null>(null),
    confidence_level_pct: new FormControl<number | null>(null),
    min_distance_m: new FormControl<number | null>(10),
    random_seed: new FormControl<number | null>(null),
    counts: this.counts,
  });

  constructor() {
    effect(() => {
      const p = this.period();
      if (p) this.load(p.id);
      else this.designs.set([]);
    });
    effect(() => {
      const n = this.approved().length;
      this.counts.clear();
      for (let i = 0; i < n; i++) this.counts.push(new FormControl(0, { nonNullable: true, validators: [Validators.min(0)] }));
      this.countValues.set(this.counts.getRawValue());
    });
    this.counts.valueChanges.subscribe(() => this.countValues.set(this.counts.getRawValue()));
  }

  protected src(s: RuleSource): string {
    return ruleSourceLabel(s);
  }

  private load(periodId: string): void {
    this.api.designs(this.projectId(), periodId).subscribe((d) => this.designs.set(d));
  }

  protected create(): void {
    const p = this.period();
    if (!p) return;
    const v = this.form.getRawValue();
    const allocations = this.approved().map((s, i) => ({ stratum_id: s.id, sample_count: Number(v.counts[i]) || 0 })).filter((a) => a.sample_count > 0);
    const num = (x: number | null) => (x === null || x === undefined || `${x}` === '' ? null : x);
    runAction(this.api.createDesign({ monitoring_period_id: p.id, code: v.code.trim(), name: v.name.trim(), statistical_design: v.statistical_design,
      sampling_method: v.sampling_method.trim() || null, depth_top_cm: v.depth_top_cm, depth_bottom_cm: v.depth_bottom_cm,
      target_precision_pct: num(v.target_precision_pct), confidence_level_pct: num(v.confidence_level_pct), min_distance_m: num(v.min_distance_m),
      random_seed: num(v.random_seed), allocations }), this.busy, this.notify, 'Sampling design created (draft).', () => this.load(p.id));
  }

  protected approve(d: Design, v: DesignVersion): void {
    askReason(this.dialog, { title: `Approve ${d.code} v${v.version}?`, confirmLabel: 'Approve',
      message: 'You cannot approve a design version you created.' }).subscribe((r) => {
      if (r) runAction(this.api.approveDesign(d.id, v.id, r.reason), this.busy, this.notify, 'Design approved.', () => this.load(d.monitoring_period_id));
    });
  }

  protected generate(d: Design): void {
    runAction(this.api.generatePoints(d.id), this.busy, this.notify, 'Sampling points generated.', (r) => {
      this.notify.success(`${r.created} points: ` + Object.entries(r.per_stratum).map(([k, n]) => `${k} ${n}`).join(', '));
      this.load(d.monitoring_period_id);
      this.changed.emit();
    });
  }
}
