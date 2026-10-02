import { ChangeDetectionStrategy, Component, OnInit, inject, input, signal } from '@angular/core';
import { FormArray, FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { Router } from '@angular/router';

import { NotifyService } from '../core/notify.service';
import { label } from '../farmer/farmer.models';
import { PageHeader } from '../shared/page-header';
import { runAction } from '../shared/run-action';
import { MrvApi } from './mrv.api';
import { LEVELS, MEASUREMENT_CATEGORIES, QUANTIFICATION, Requirements, VALUE_TYPES } from './mrv.models';

function measurementGroup(): FormGroup {
  return new FormGroup({
    code: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    name: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.minLength(2)] }),
    category: new FormControl('TILLAGE', { nonNullable: true }),
    value_type: new FormControl('CHOICE', { nonNullable: true }),
    unit: new FormControl('', { nonNullable: true }),
    allowed_values: new FormControl('', { nonNullable: true }),
    level: new FormControl('FARM', { nonNullable: true }),
    required: new FormControl(true, { nonNullable: true }),
  });
}

/** New MRV plan (version). Methodology monitoring rules are copied automatically; project measurements are added here. */
@Component({
  selector: 'app-mrv-plan-create-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, MatButtonModule, MatCheckboxModule, MatFormFieldModule, MatInputModule, MatSelectModule, PageHeader],
  template: `
    <app-page-header title="New MRV plan" [backLink]="'/mrv/projects/' + id()" backLabel="MRV workspace" />
    @if (req(); as r) {
      <div class="note" [class.warn]="r.status === 'CONFIGURATION_REQUIRED'">
        <strong>From the locked methodology version:</strong>
        {{ r.monitoring.length }} monitoring rule(s) become plan measurements automatically.
        @if (r.gaps.length) { <div>CONFIGURATION_REQUIRED: {{ r.gaps.join('; ') }}. The approver must acknowledge these gaps.</div> }
      </div>
    }
    <form [formGroup]="form" (ngSubmit)="save()">
      <div class="form-grid">
        <mat-form-field><mat-label>Monitoring frequency</mat-label><input matInput formControlName="monitoring_frequency" /></mat-form-field>
        <mat-form-field><mat-label>Quantification approach</mat-label>
          <mat-select formControlName="quantification_approach">
            <mat-option value="">(methodology-defined or CONFIGURATION_REQUIRED)</mat-option>
            @for (q of quant; track q) { <mat-option [value]="q">{{ label(q) }}</mat-option> }
          </mat-select>
          <mat-hint>No calculation happens in this phase.</mat-hint></mat-form-field>
        <mat-form-field><mat-label>Monitoring start</mat-label><input matInput type="date" formControlName="monitoring_start" /></mat-form-field>
        <mat-form-field><mat-label>Monitoring end</mat-label><input matInput type="date" formControlName="monitoring_end" /></mat-form-field>
        <mat-form-field class="span-all"><mat-label>Required evidence</mat-label><input matInput formControlName="required_evidence" /></mat-form-field>
        <mat-form-field class="span-all"><mat-label>Notes</mat-label><textarea matInput rows="2" formControlName="notes"></textarea></mat-form-field>
      </div>
      <h3>Project measurements (activity data)</h3>
      @for (g of measurements.controls; track $index; let i = $index) {
        <div class="form-grid measurement" [formGroup]="g">
          <mat-form-field subscriptSizing="dynamic"><mat-label>Code</mat-label><input matInput formControlName="code" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Name</mat-label><input matInput formControlName="name" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Category</mat-label>
            <mat-select formControlName="category">@for (c of cats; track c) { <mat-option [value]="c">{{ label(c) }}</mat-option> }</mat-select></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Value type</mat-label>
            <mat-select formControlName="value_type">@for (c of types; track c) { <mat-option [value]="c">{{ label(c) }}</mat-option> }</mat-select></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Unit</mat-label><input matInput formControlName="unit" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Allowed values (comma separated)</mat-label><input matInput formControlName="allowed_values" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Level</mat-label>
            <mat-select formControlName="level">@for (c of levels; track c) { <mat-option [value]="c">{{ label(c) }}</mat-option> }</mat-select></mat-form-field>
          <div class="row"><mat-checkbox formControlName="required">Required</mat-checkbox>
            <button mat-button type="button" (click)="measurements.removeAt(i)">Remove</button></div>
        </div>
      }
      <button mat-stroked-button type="button" (click)="measurements.push(newMeasurement())">Add measurement</button>
      <div class="actions"><button mat-flat-button type="submit" [disabled]="busy() || form.invalid" data-testid="create-plan">Create plan (draft)</button></div>
    </form>
  `,
  styles: `
    h3 { margin: 16px 0 8px; font: var(--mat-sys-title-small); } .measurement { border-top: 1px dashed var(--mat-sys-outline-variant); padding-top: 8px; }
    .row { display: flex; align-items: center; gap: 8px; } .actions { margin-top: 16px; }
  `,
})
export class MrvPlanCreatePage implements OnInit {
  readonly id = input.required<string>();
  private readonly api = inject(MrvApi);
  private readonly notify = inject(NotifyService);
  private readonly router = inject(Router);
  protected readonly label = label;
  protected readonly quant = QUANTIFICATION;
  protected readonly cats = MEASUREMENT_CATEGORIES;
  protected readonly types = VALUE_TYPES;
  protected readonly levels = LEVELS;
  protected readonly req = signal<Requirements | null>(null);
  protected readonly busy = signal(false);
  protected readonly newMeasurement = measurementGroup;
  protected readonly measurements = new FormArray<FormGroup>([]);
  protected readonly form = new FormGroup({
    monitoring_frequency: new FormControl('Once per monitoring period', { nonNullable: true }),
    quantification_approach: new FormControl('', { nonNullable: true }),
    monitoring_start: new FormControl('', { nonNullable: true }),
    monitoring_end: new FormControl('', { nonNullable: true }),
    required_evidence: new FormControl('', { nonNullable: true }),
    notes: new FormControl('', { nonNullable: true }),
    measurements: this.measurements,
  });

  ngOnInit(): void {
    this.api.requirements(this.id()).subscribe((r) => this.req.set(r));
  }

  protected save(): void {
    const v = this.form.getRawValue();
    const blank = (s: string) => s.trim() || null;
    const measurements = (v.measurements as Record<string, string | boolean>[]).map((m) => ({
      code: String(m['code']).trim(), name: String(m['name']).trim(), category: m['category'], value_type: m['value_type'], level: m['level'],
      unit: blank(String(m['unit'])), required: m['required'],
      allowed_values: m['value_type'] === 'CHOICE' ? String(m['allowed_values']).split(',').map((x) => x.trim()).filter(Boolean) : null,
    }));
    runAction(this.api.createPlan({ project_id: this.id(), monitoring_frequency: blank(v.monitoring_frequency),
      quantification_approach: blank(v.quantification_approach), monitoring_start: blank(v.monitoring_start), monitoring_end: blank(v.monitoring_end),
      required_evidence: blank(v.required_evidence), notes: blank(v.notes), measurements }), this.busy, this.notify, 'MRV plan created (draft).',
    (p) => void this.router.navigate(['/mrv/plans', p.id]));
  }
}
