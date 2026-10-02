import { ChangeDetectionStrategy, Component, computed, inject, input, output, signal } from '@angular/core';
import { FormControl, FormGroup, FormGroupDirective, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';

import { AuthService } from '../../core/auth/auth.service';
import { P } from '../../core/auth/permissions';
import { NotifyService } from '../../core/notify.service';
import { label } from '../../farmer/farmer.models';
import { ProjectFarm } from '../../projects/project.models';
import { GeoMap, MapLayer } from '../../shared/geo-map';
import { askReason } from '../../shared/reason-dialog';
import { runAction } from '../../shared/run-action';
import { StatusBadge } from '../../shared/status-badge';
import { MrvApi } from '../mrv.api';
import { CHARACTERISTICS, Stratum, mrvBadge } from '../mrv.models';

const COLORS = ['#2e7d32', '#6a1b9a', '#ef6c00', '#00838f', '#ad1457', '#558b2f'];

/** Strata: groups of participating farms; geometry and area are the SQL Server union of the farm boundaries. Versioned. */
@Component({
  selector: 'app-mrv-strata-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, MatButtonModule, MatFormFieldModule, MatInputModule, MatSelectModule, StatusBadge, GeoMap],
  template: `
    <div class="tab-body cols">
      <app-geo-map [layers]="layers()" height="380px" />
      <div>
        @for (s of strata(); track s.id) {
          <div class="item">
            <div class="row"><span class="swatch" [style.background]="color(s)"></span><strong>{{ s.code }}</strong> {{ s.name }} <span class="muted small">v{{ s.version }}</span>
              <app-status-badge [status]="badge(s.status)" [text]="label(s.status)" />
              @if (!s.is_current) { <app-status-badge status="INFO" text="Revision (draft)" /> }</div>
            <div class="small">{{ s.area_hectares ?? '—' }} ha (SQL Server) · farms {{ s.farm_codes.join(', ') }}</div>
            <div class="small muted">@for (c of s.characteristics; track $index) { {{ label(c.characteristic) }}: {{ c.value }}; }</div>
            @if (s.missing_required_characteristics.length) {
              <div class="small bad">Methodology requires: {{ s.missing_required_characteristics.join(', ') }}</div>
            }
            @if (s.change_reason) { <div class="small muted">Change: {{ s.change_reason }}</div> }
            <div class="actions">
              @if (canReview && s.status === 'DRAFT') { <button mat-stroked-button type="button" [disabled]="busy()" (click)="approve(s)">Approve</button> }
              @if (canManage && s.status === 'APPROVED' && s.is_current) { <button mat-button type="button" [disabled]="busy()" (click)="revise(s)">Revise (new version)</button> }
            </div>
          </div>
        } @empty { <p class="muted">No strata yet.</p> }
        @if (canManage) {
          <h3>New stratum</h3>
          <form [formGroup]="form" #fd="ngForm" (ngSubmit)="create(fd)" class="form-grid">
            <mat-form-field subscriptSizing="dynamic"><mat-label>Code</mat-label><input matInput formControlName="code" /></mat-form-field>
            <mat-form-field subscriptSizing="dynamic"><mat-label>Name</mat-label><input matInput formControlName="name" /></mat-form-field>
            <mat-form-field subscriptSizing="dynamic" class="span-all"><mat-label>Farms</mat-label>
              <mat-select formControlName="farm_ids" multiple data-testid="stratum-farms">
                @for (f of freeFarms(); track f.farm_id) { <mat-option [value]="f.farm_id">{{ f.farm_code }} · {{ f.farm_name }} ({{ f.farm_area_hectares }} ha)</mat-option> }
              </mat-select></mat-form-field>
            <mat-form-field subscriptSizing="dynamic"><mat-label>Characteristic</mat-label>
              <mat-select formControlName="characteristic">@for (c of chars; track c) { <mat-option [value]="c">{{ label(c) }}</mat-option> }</mat-select></mat-form-field>
            <mat-form-field subscriptSizing="dynamic"><mat-label>Value</mat-label><input matInput formControlName="value" /></mat-form-field>
            <div><button mat-flat-button type="submit" [disabled]="busy() || form.invalid">Create stratum</button></div>
          </form>
          <p class="muted small">A farm belongs to one current stratum. Approved strata are never changed in place; revisions create a new version.</p>
        }
      </div>
    </div>
  `,
  styles: `
    .cols { display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); gap: 20px; } @media (max-width: 900px) { .cols { grid-template-columns: 1fr; } }
    .item { padding: 8px 0; border-bottom: 1px solid var(--mat-sys-outline-variant); } .row { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
    .swatch { width: 12px; height: 12px; border-radius: 3px; display: inline-block; } .bad { color: #b71c1c; }
    .actions { display: flex; gap: 6px; margin-top: 4px; } h3 { margin: 16px 0 8px; font: var(--mat-sys-title-small); }
  `,
})
export class MrvStrataPanel {
  readonly projectId = input.required<string>();
  readonly farms = input<ProjectFarm[]>([]);
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
  protected readonly chars = CHARACTERISTICS;
  protected readonly busy = signal(false);
  protected readonly form = new FormGroup({
    code: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    name: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.minLength(2)] }),
    farm_ids: new FormControl<string[]>([], { nonNullable: true, validators: [Validators.required] }),
    characteristic: new FormControl('SOIL_TYPE', { nonNullable: true }),
    value: new FormControl('', { nonNullable: true }),
  });
  protected readonly freeFarms = computed(() => {
    const used = new Set(this.strata().filter((s) => s.is_current).flatMap((s) => s.farm_ids));
    return this.farms().filter((f) => !used.has(f.farm_id));
  });
  protected readonly layers = computed<MapLayer[]>(() =>
    this.strata().filter((s) => s.geojson && s.is_current).map((s) => ({ geojson: s.geojson!, color: this.color(s), label: `${s.code} · ${s.name}`, fillOpacity: 0.25 })));

  protected color(s: Stratum): string {
    const codes = [...new Set(this.strata().map((x) => x.code))];
    return COLORS[codes.indexOf(s.code) % COLORS.length];
  }

  protected create(fd: FormGroupDirective): void {
    const v = this.form.getRawValue();
    const characteristics = v.value.trim() ? [{ characteristic: v.characteristic, value: v.value.trim() }] : [];
    runAction(this.api.createStratum(this.projectId(), { code: v.code.trim(), name: v.name.trim(), farm_ids: v.farm_ids, characteristics }), this.busy,
      this.notify, 'Stratum created (draft).', () => { fd.resetForm({ code: '', name: '', farm_ids: [], characteristic: 'SOIL_TYPE', value: '' }); this.changed.emit(); });
  }

  protected approve(s: Stratum): void {
    askReason(this.dialog, { title: `Approve stratum ${s.code} v${s.version}?`, confirmLabel: 'Approve',
      message: 'Approval freezes this version. You cannot approve a stratum you created.' }).subscribe((r) => {
      if (r) runAction(this.api.approveStratum(s.id, r.reason), this.busy, this.notify, 'Stratum approved.', () => this.changed.emit());
    });
  }

  protected revise(s: Stratum): void {
    askReason(this.dialog, { title: `Revise stratum ${s.code}?`, confirmLabel: 'Create revision',
      message: 'A new draft version is created with the same farms; edit and approve it to replace the current version.' }).subscribe((r) => {
      if (r) runAction(this.api.updateStratum(s.id, { name: s.name, reason: r.reason }), this.busy, this.notify, 'Draft revision created.',
        () => this.changed.emit());
    });
  }
}
