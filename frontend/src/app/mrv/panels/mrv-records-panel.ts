import { ChangeDetectionStrategy, Component, computed, effect, inject, input, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';

import { AuthService } from '../../core/auth/auth.service';
import { P } from '../../core/auth/permissions';
import { NotifyService } from '../../core/notify.service';
import { label } from '../../farmer/farmer.models';
import { ProjectFarm } from '../../projects/project.models';
import { askReason } from '../../shared/reason-dialog';
import { runAction } from '../../shared/run-action';
import { StatusBadge } from '../../shared/status-badge';
import { MrvApi } from '../mrv.api';
import { Measurement, MonitoringRecord, Period, Plan, SamplingPoint, Stratum, capturableInMrv, dataRoleLabel, mrvBadge, parseMeasurementValue } from '../mrv.models';

/** Monitoring data entry against the approved plan's configurable measurement definitions. Corrections create new versions. */
@Component({
  selector: 'app-mrv-records-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, MatButtonModule, MatCheckboxModule, MatFormFieldModule, MatInputModule, MatSelectModule, StatusBadge],
  template: `
    <div class="tab-body">
      @if (!period()) { <p class="muted">Create a monitoring period first.</p> }
      @if (canRecord && period() && editable()) {
        <form [formGroup]="form" (ngSubmit)="add()" class="form-grid">
          <mat-form-field subscriptSizing="dynamic"><mat-label>Measurement</mat-label>
            <mat-select formControlName="measurement_id" data-testid="measurement">
              @for (m of farmMeasurements(); track m.id) { <mat-option [value]="m.id">{{ m.code }} · {{ m.name }}{{ m.unit ? ' (' + m.unit + ')' : '' }}</mat-option> }
            </mat-select></mat-form-field>
          @if (measurement()?.level === 'STRATUM') {
            <mat-form-field subscriptSizing="dynamic"><mat-label>Stratum</mat-label>
              <mat-select formControlName="stratum_id" data-testid="record-stratum">@for (s of projectStrata(); track s.id) { <mat-option [value]="s.id">{{ s.code }} · {{ s.name }}</mat-option> }</mat-select></mat-form-field>
          } @else if (measurement()?.level === 'SAMPLING_POINT') {
            <mat-form-field subscriptSizing="dynamic"><mat-label>Sampling point / planting unit</mat-label>
              <mat-select formControlName="sampling_point_id" data-testid="record-point">@for (x of points(); track x.id) { <mat-option [value]="x.id">{{ x.point_code }} · {{ x.stratum_code }}</mat-option> }</mat-select></mat-form-field>
          } @else if (measurement()?.level !== 'PROJECT') {
            <mat-form-field subscriptSizing="dynamic"><mat-label>Farm</mat-label>
              <mat-select formControlName="farm_id">@for (f of farms(); track f.farm_id) { <mat-option [value]="f.farm_id">{{ f.farm_code }} · {{ f.farm_name }}</mat-option> }</mat-select></mat-form-field>
          }
          @if (measurement(); as m) {
            @if (m.value_type === 'CHOICE') {
              <mat-form-field subscriptSizing="dynamic"><mat-label>Value</mat-label>
                <mat-select formControlName="value">@for (v of m.allowed_values ?? []; track v) { <mat-option [value]="v">{{ label(v) }}</mat-option> }</mat-select></mat-form-field>
            } @else if (m.value_type === 'BOOLEAN') {
              <mat-form-field subscriptSizing="dynamic"><mat-label>Value</mat-label>
                <mat-select formControlName="value"><mat-option value="true">Yes</mat-option><mat-option value="false">No</mat-option></mat-select></mat-form-field>
            } @else {
              <mat-form-field subscriptSizing="dynamic"><mat-label>Value{{ m.unit ? ' (' + m.unit + ')' : '' }}</mat-label>
                <input matInput formControlName="value" [type]="m.value_type === 'NUMBER' ? 'number' : m.value_type === 'DATE' ? 'date' : 'text'" /></mat-form-field>
            }
          }
          <mat-form-field subscriptSizing="dynamic"><mat-label>Observed on</mat-label><input matInput type="date" formControlName="observed_on" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Phase</mat-label>
            <mat-select formControlName="measurement_phase">@for (x of phases; track x) { <mat-option [value]="x">{{ label(x) }}</mat-option> }</mat-select></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Source</mat-label>
            <mat-select formControlName="source">@for (x of sources; track x) { <mat-option [value]="x">{{ label(x) }}</mat-option> }</mat-select></mat-form-field>
          <div><button mat-flat-button type="submit" [disabled]="busy() || form.invalid">Record value</button></div>
        </form>
        <p class="muted small">Parameters the methodology declares LABORATORY come only from approved laboratory results and are not entered here; FIELD and FIELD_ACTIVITY parameters (including field-kit measurements the methodology declares FIELD) are.</p>
      }
      <mat-checkbox [checked]="history()" (change)="history.set($event.checked)">Show superseded versions</mat-checkbox>
      <div class="table-wrap"><table class="table">
        <thead><tr><th>Measurement</th><th>Farm / stratum</th><th>Value</th><th>Observed</th><th>Phase</th><th>Source</th><th>Role</th><th>Version</th><th>Status</th><th></th></tr></thead>
        <tbody>
          @for (r of records(); track r.id) {
            <tr>
              <td>{{ r.measurement_code }} · {{ r.measurement_name }}</td><td>{{ where(r) }}</td>
              <td>{{ show(r.value) }} {{ r.unit ?? '' }}</td><td>{{ r.observed_on }}</td><td>{{ label(r.measurement_phase) }}</td><td>{{ label(r.source) }}</td><td [class.muted]="!r.authoritative">{{ roleLabel(r.data_role) }}</td>
              <td>v{{ r.version }}{{ r.change_reason ? ' · ' + r.change_reason : '' }}</td>
              <td><app-status-badge [status]="badge(r.status)" [text]="label(r.status)" /></td>
              <td>@if (canRecord && r.is_current && editable()) { <button mat-button type="button" (click)="amend(r)">Correct</button> }</td>
            </tr>
          } @empty { <tr><td colspan="10" class="muted">No monitoring records.</td></tr> }
        </tbody>
      </table></div>
    </div>
  `,
})
export class MrvRecordsPanel {
  readonly period = input<Period | null>(null);
  readonly farms = input<ProjectFarm[]>([]);
  readonly strata = input<Stratum[]>([]);
  private readonly api = inject(MrvApi);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotifyService);
  private readonly auth = inject(AuthService);
  protected readonly canRecord = this.auth.has(P.MRV_COLLECT) || this.auth.has(P.MRV_MANAGE);
  protected readonly label = label;
  protected readonly badge = mrvBadge;
  protected readonly roleLabel = dataRoleLabel;
  protected readonly phases = ['MONITORING', 'PROJECT', 'BASELINE'];
  protected readonly sources = ['FIELD_OBSERVATION', 'FARMER_CLAIM', 'DOCUMENT', 'INSTRUMENT', 'OTHER'];
  protected readonly busy = signal(false);
  protected readonly history = signal(false);
  protected readonly plan = signal<Plan | null>(null);
  protected readonly records = signal<MonitoringRecord[]>([]);
  /** Sampling points of the period (census methods record one value per sampled planting unit). */
  protected readonly points = signal<SamplingPoint[]>([]);
  protected readonly editable = computed(() => ['ACTIVE', 'DATA_COLLECTION'].includes(this.period()?.status ?? ''));
  protected readonly farmMeasurements = computed(() => (this.plan()?.measurements ?? []).filter((m) => capturableInMrv(m)));
  protected readonly form = new FormGroup({
    measurement_id: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    farm_id: new FormControl('', { nonNullable: true }),
    stratum_id: new FormControl('', { nonNullable: true }),
    sampling_point_id: new FormControl('', { nonNullable: true }),
    value: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    observed_on: new FormControl(new Date().toISOString().slice(0, 10), { nonNullable: true, validators: [Validators.required] }),
    measurement_phase: new FormControl('MONITORING', { nonNullable: true }),
    source: new FormControl('FIELD_OBSERVATION', { nonNullable: true }),
  });
  private readonly measurementId = signal('');
  protected readonly measurement = computed<Measurement | null>(() => this.farmMeasurements().find((m) => m.id === this.measurementId()) ?? null);

  constructor() {
    this.form.controls.measurement_id.valueChanges.subscribe((v) => { this.measurementId.set(v); this.form.controls.value.setValue(''); });
    effect(() => {
      const p = this.period();
      const h = this.history();
      if (!p) return;
      this.api.plan(p.mrv_plan_id).subscribe((x) => this.plan.set(x));
      this.api.records(p.id, h).subscribe((r) => this.records.set(r));
    });
    effect(() => {
      const p = this.period();
      if (p && this.measurement()?.level === 'SAMPLING_POINT' && !this.points().length) {
        this.api.points({ monitoring_period_id: p.id }).subscribe((x) => this.points.set(x));
      }
    });
  }

  /** Current approved project strata (Approach 3 factors and other per-stratum values are recorded against them). */
  protected readonly projectStrata = computed(() => this.strata().filter((s) => s.is_current && s.status === 'APPROVED' && s.role !== 'CONTROL'));

  protected where(r: MonitoringRecord): string {
    if (r.sampling_point_id) return 'point ' + (this.points().find((x) => x.id === r.sampling_point_id)?.point_code ?? r.sampling_point_id);
    if (r.stratum_id) return 'stratum ' + (this.strata().find((s) => s.id === r.stratum_id)?.code ?? r.stratum_id);
    return r.farm_id ? (this.farms().find((f) => f.farm_id === r.farm_id)?.farm_code ?? r.farm_id) : 'project';
  }

  protected show(v: unknown): string {
    if (v === true) return 'Yes';
    if (v === false) return 'No';
    return v === null || v === undefined ? '—' : String(v);
  }

  private reload(): void {
    const p = this.period();
    if (p) this.api.records(p.id, this.history()).subscribe((r) => this.records.set(r));
  }

  protected add(): void {
    const p = this.period();
    const m = this.measurement();
    if (!p || !m) return;
    const v = this.form.getRawValue();
    runAction(this.api.addRecord({ monitoring_period_id: p.id, measurement_id: m.id, farm_id: m.level === 'FARM' ? v.farm_id || null : null,
      stratum_id: m.level === 'STRATUM' ? v.stratum_id || null : null,
      sampling_point_id: m.level === 'SAMPLING_POINT' ? v.sampling_point_id || null : null,
      value: parseMeasurementValue(m, v.value), observed_on: v.observed_on, measurement_phase: v.measurement_phase, source: v.source }),
    this.busy, this.notify, 'Value recorded.', () => { this.form.controls.value.setValue(''); this.reload(); });
  }

  protected amend(r: MonitoringRecord): void {
    const m = this.plan()?.measurements.find((x) => x.id === r.measurement_id);
    const raw = window.prompt(`New value for ${r.measurement_code}${m?.allowed_values ? ' (' + m.allowed_values.join(' / ') + ')' : ''}`, this.show(r.value));
    if (raw === null || !m) return;
    askReason(this.dialog, { title: `Correct ${r.measurement_code}?`, confirmLabel: 'Save new version',
      message: 'The current value is kept as a superseded version.' }).subscribe((x) => {
      if (x) runAction(this.api.amendRecord(r.record_id, { value: parseMeasurementValue(m, raw), reason: x.reason }), this.busy, this.notify,
        'New version recorded.', () => this.reload());
    });
  }
}
