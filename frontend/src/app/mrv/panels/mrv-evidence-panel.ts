import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, effect, inject, input, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';

import { AuthService } from '../../core/auth/auth.service';
import { P } from '../../core/auth/permissions';
import { NotifyService } from '../../core/notify.service';
import { label } from '../../farmer/farmer.models';
import { ProjectFarm } from '../../projects/project.models';
import { runAction } from '../../shared/run-action';
import { MrvApi } from '../mrv.api';
import { EVIDENCE_TYPES, Evidence, Period } from '../mrv.models';

/** MRV evidence linked to the project, a farm or the monitoring period (field photos are attached on the collection screen). */
@Component({
  selector: 'app-mrv-evidence-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, ReactiveFormsModule, MatButtonModule, MatFormFieldModule, MatInputModule, MatSelectModule],
  template: `
    <div class="tab-body">
      <div class="table-wrap"><table class="table">
        <thead><tr><th>Type</th><th>Linked to</th><th>Description</th><th>Location</th><th>SHA-256</th><th>Uploaded</th></tr></thead>
        <tbody>
          @for (e of items(); track e.id) {
            <tr>
              <td>{{ label(e.evidence_type) }}</td><td>{{ label(e.entity_type) }}{{ e.entity_type === 'FARM' ? ' ' + farmCode(e.entity_id) : '' }}</td>
              <td>{{ e.description ?? '—' }}</td><td>{{ e.latitude ? e.latitude + ', ' + e.longitude : '—' }}</td>
              <td class="mono">{{ e.checksum_sha256 ? e.checksum_sha256.slice(0, 12) + '…' : '—' }}</td><td>{{ e.uploaded_at | date: 'medium' }}</td>
            </tr>
          } @empty { <tr><td colspan="6" class="muted">No evidence yet.</td></tr> }
        </tbody>
      </table></div>
      @if (canAdd) {
        <h3>Add evidence</h3>
        <form [formGroup]="form" (ngSubmit)="add()" class="form-grid">
          <mat-form-field subscriptSizing="dynamic"><mat-label>Linked to</mat-label>
            <mat-select formControlName="entity">
              <mat-option value="PROJECT">Project</mat-option>
              @if (period()) { <mat-option value="MONITORING_PERIOD">Monitoring period {{ period()!.name }}</mat-option> }
              @for (f of farms(); track f.farm_id) { <mat-option [value]="'FARM:' + f.farm_id">Farm {{ f.farm_code }}</mat-option> }
            </mat-select></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Evidence type</mat-label>
            <mat-select formControlName="evidence_type">@for (t of types; track t) { <mat-option [value]="t">{{ label(t) }}</mat-option> }</mat-select></mat-form-field>
          <mat-form-field subscriptSizing="dynamic" class="span-all"><mat-label>Description</mat-label><input matInput formControlName="description" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Latitude (GPS evidence)</mat-label><input matInput type="number" formControlName="latitude" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Longitude</mat-label><input matInput type="number" formControlName="longitude" /></mat-form-field>
          <div class="span-all file"><input type="file" (change)="pick($event)" aria-label="Evidence file" />
            <button mat-flat-button type="submit" [disabled]="busy() || form.invalid">Add evidence</button></div>
        </form>
        <p class="muted small">Photos and documents need a file; GPS evidence needs coordinates. Files are stored with a SHA-256 checksum. No satellite data is generated.</p>
      }
    </div>
  `,
  styles: `.mono { font-family: monospace; font-size: 12px; } h3 { margin: 16px 0 8px; font: var(--mat-sys-title-small); } .file { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }`,
})
export class MrvEvidencePanel {
  readonly projectId = input.required<string>();
  readonly period = input<Period | null>(null);
  readonly farms = input<ProjectFarm[]>([]);
  private readonly api = inject(MrvApi);
  private readonly notify = inject(NotifyService);
  private readonly auth = inject(AuthService);
  protected readonly canAdd = this.auth.has(P.MRV_COLLECT) || this.auth.has(P.MRV_MANAGE);
  protected readonly label = label;
  protected readonly types = EVIDENCE_TYPES;
  protected readonly busy = signal(false);
  protected readonly items = signal<Evidence[]>([]);
  private file: File | null = null;
  protected readonly form = new FormGroup({
    entity: new FormControl('PROJECT', { nonNullable: true, validators: [Validators.required] }),
    evidence_type: new FormControl('DOCUMENT', { nonNullable: true }),
    description: new FormControl('', { nonNullable: true }),
    latitude: new FormControl<number | null>(null),
    longitude: new FormControl<number | null>(null),
  });
  private readonly periodId = computed(() => this.period()?.id ?? null);

  constructor() {
    effect(() => this.load(this.periodId()));
  }

  private load(periodId: string | null): void {
    this.api.evidence({ project_id: this.projectId(), monitoring_period_id: periodId }).subscribe((e) => this.items.set(e));
  }

  protected farmCode(id: string): string {
    return this.farms().find((f) => f.farm_id === id)?.farm_code ?? '';
  }

  protected pick(ev: Event): void {
    this.file = (ev.target as HTMLInputElement).files?.[0] ?? null;
  }

  protected add(): void {
    const v = this.form.getRawValue();
    const [entityType, farmId] = v.entity.split(':');
    const entityId = entityType === 'FARM' ? farmId : entityType === 'MONITORING_PERIOD' ? this.period()!.id : this.projectId();
    const fields: Record<string, string> = { project_id: this.projectId(), entity_type: entityType, entity_id: entityId, evidence_type: v.evidence_type };
    if (v.description.trim()) fields['description'] = v.description.trim();
    if (v.latitude !== null && v.longitude !== null) { fields['latitude'] = String(v.latitude); fields['longitude'] = String(v.longitude); }
    runAction(this.api.addEvidence(this.file, fields), this.busy, this.notify, 'Evidence added.', () => {
      this.form.patchValue({ description: '', latitude: null, longitude: null });
      this.load(this.periodId());
    });
  }
}
