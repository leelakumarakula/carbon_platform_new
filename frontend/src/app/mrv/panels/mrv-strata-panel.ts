import { NgTemplateOutlet } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, input, output, signal } from '@angular/core';
import { FormControl, FormGroup, FormGroupDirective, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
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
import { CHARACTERISTICS, CONTROL_SITE_CRITERIA, Characteristic, ControlCandidate, Stratum, mrvBadge } from '../mrv.models';

const COLORS = ['#2e7d32', '#6a1b9a', '#ef6c00', '#00838f', '#ad1457', '#558b2f'];
const CONTROL_COLOR = '#455a64';
type Role = 'PROJECT' | 'CONTROL';

/** Strata: groups of participating farms (PROJECT) and baseline control sites (CONTROL, VM0042 measure & remeasure).
 *  Geometry and area are the SQL Server union of the farm boundaries. Versioned; approval by someone other than the creator. */
@Component({
  selector: 'app-mrv-strata-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NgTemplateOutlet, ReactiveFormsModule, MatButtonModule, MatButtonToggleModule, MatFormFieldModule, MatIconModule, MatInputModule, MatSelectModule,
    StatusBadge, GeoMap],
  template: `
    <div class="tab-body cols">
      <app-geo-map [layers]="layers()" height="380px" />
      <div>
        @if (projectStrata().length) {
          <div class="checklist" data-testid="control-checklist">
            <strong>Baseline control sites</strong>
            <span [class.ok]="controlSites().length >= 3" [class.bad]="controlSites().length < 3">
              <mat-icon inline>{{ controlSites().length >= 3 ? 'check_circle' : 'error' }}</mat-icon>
              {{ controlSites().length }} of at least 3</span>
            <span [class.ok]="!uncovered().length" [class.bad]="uncovered().length">
              <mat-icon inline>{{ uncovered().length ? 'error' : 'check_circle' }}</mat-icon>
              @if (uncovered().length) { No control site yet for {{ uncovered().join(', ') }} } @else { Every stratum has a control site }</span>
          </div>
        }

        <h3>Project strata</h3>
        @for (s of projectStrata(); track s.id) {
          <ng-container *ngTemplateOutlet="row; context: { $implicit: s }" />
        } @empty { <p class="muted small">No strata yet.</p> }

        <h3>Control sites <span class="muted small">(baseline, measure &amp; remeasure)</span></h3>
        @for (s of controlSites(); track s.id) {
          <ng-container *ngTemplateOutlet="row; context: { $implicit: s }" />
        } @empty { <p class="muted small">No control sites yet. Farms that keep the baseline practices; they are sampled like project farms but never earn credits.</p> }

        <ng-template #row let-s>
          <div class="item">
            <div class="line"><span class="swatch" [style.background]="color(s)"></span><strong>{{ s.code }}</strong> {{ s.name }}
              <span class="muted small">v{{ s.version }}</span>
              <app-status-badge [status]="badge(s.status)" [text]="label(s.status)" />
              @if (!s.is_current) { <app-status-badge status="INFO" text="Revision (draft)" /> }</div>
            <div class="small">{{ s.area_hectares ?? '—' }} ha (SQL Server) · farms {{ s.farm_codes.join(', ') }}</div>
            @if (s.role === 'CONTROL') {
              <div class="small">Represents {{ linkedCodes(s) }}</div>
            }
            @if (s.characteristics.length) {
              <div class="chips">@for (c of s.characteristics; track $index) { <span class="chip">{{ label(c.characteristic) }}: {{ c.value }}</span> }</div>
            }
            @if (s.missing_required_characteristics.length) {
              <div class="small bad">Methodology requires: {{ s.missing_required_characteristics.join(', ') }}</div>
            }
            @if (s.change_reason) { <div class="small muted">Change: {{ s.change_reason }}</div> }
            <div class="actions">
              @if (canReview && s.status === 'DRAFT') { <button mat-stroked-button type="button" [disabled]="busy()" (click)="approve(s)">Approve</button> }
              @if (canManage && s.status === 'APPROVED' && s.is_current) { <button mat-button type="button" [disabled]="busy()" (click)="revise(s)">Revise (new version)</button> }
            </div>
          </div>
        </ng-template>

        @if (canManage) {
          <h3>New</h3>
          <mat-button-toggle-group [value]="role()" (change)="setRole($event.value)" class="role" aria-label="What to create">
            <mat-button-toggle value="PROJECT">Project stratum</mat-button-toggle>
            <mat-button-toggle value="CONTROL" data-testid="role-control">Control site</mat-button-toggle>
          </mat-button-toggle-group>
          <form [formGroup]="form" #fd="ngForm" (ngSubmit)="create(fd)" class="form-grid">
            <mat-form-field subscriptSizing="dynamic"><mat-label>Code</mat-label><input matInput formControlName="code" /></mat-form-field>
            <mat-form-field subscriptSizing="dynamic"><mat-label>Name</mat-label><input matInput formControlName="name" /></mat-form-field>
            <mat-form-field subscriptSizing="dynamic" class="span-all"><mat-label>Farms</mat-label>
              <mat-select formControlName="farm_ids" multiple data-testid="stratum-farms">
                @if (role() === 'PROJECT') {
                  @for (f of freeFarms(); track f.farm_id) { <mat-option [value]="f.farm_id">{{ f.farm_code }} · {{ f.farm_name }} ({{ f.farm_area_hectares }} ha)</mat-option> }
                } @else {
                  @for (f of freeCandidates(); track f.farm_id) { <mat-option [value]="f.farm_id">{{ f.farm_code }} · {{ f.farm_name }} ({{ f.area_hectares }} ha)</mat-option> }
                }
              </mat-select>
              @if (role() === 'CONTROL') { <mat-hint>Verified farms of your organization that are not in this project</mat-hint> }
            </mat-form-field>
            @if (role() === 'CONTROL') {
              <mat-form-field subscriptSizing="dynamic" class="span-all"><mat-label>Represents (project strata)</mat-label>
                <mat-select formControlName="linked" multiple data-testid="control-links">
                  @for (s of linkable(); track s.id) { <mat-option [value]="s.id">{{ s.code }} · {{ s.name }}</mat-option> }
                </mat-select>
                <mat-hint>Within 250 km; matching texture, soil group, slope, ecoregion, climate; rainfall within 100 mm</mat-hint>
              </mat-form-field>
            }
            <div class="span-all chars">
              @for (c of chars(); track $index) {
                <span class="chip removable">{{ label(c.characteristic) }}: {{ c.value }}
                  <button type="button" class="x" (click)="removeChar($index)" [attr.aria-label]="'Remove ' + label(c.characteristic)">×</button></span>
              }
            </div>
            <mat-form-field subscriptSizing="dynamic"><mat-label>Characteristic</mat-label>
              <mat-select formControlName="characteristic">@for (c of charOptions(); track c) { <mat-option [value]="c">{{ label(c) }}</mat-option> }</mat-select></mat-form-field>
            <mat-form-field subscriptSizing="dynamic"><mat-label>Value</mat-label><input matInput formControlName="value" (keydown.enter)="$event.preventDefault(); addChar()" />
              <button mat-icon-button matSuffix type="button" (click)="addChar()" aria-label="Add characteristic"><mat-icon>add</mat-icon></button></mat-form-field>
            <div class="span-all"><button mat-flat-button type="submit" [disabled]="busy() || form.invalid || (role() === 'CONTROL' && !form.value.linked?.length)">
              {{ role() === 'CONTROL' ? 'Create control site' : 'Create stratum' }}</button></div>
          </form>
          <p class="muted small">A farm belongs to one current stratum or control site. Approved versions are never changed in place; revisions create a new version.</p>
        }
      </div>
    </div>
  `,
  styles: `
    .cols { display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); gap: 20px; } @media (max-width: 900px) { .cols { grid-template-columns: 1fr; } }
    .item { padding: 10px 0; border-bottom: 1px solid var(--cp-line); } .line { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
    .swatch { width: 12px; height: 12px; border-radius: 3px; display: inline-block; } .bad { color: #b3261e; } .ok { color: #2f6b18; }
    .actions { display: flex; gap: 6px; margin-top: 4px; } h3 { margin: 18px 0 6px; font: 500 15px var(--cp-font); color: var(--cp-navy); }
    .checklist { display: flex; flex-direction: column; gap: 4px; padding: 10px 12px; border-radius: 10px; background: #fff; border: 1px solid var(--cp-line);
      font-size: 13px; }
    .checklist span { display: inline-flex; align-items: center; gap: 6px; }
    .chips, .chars { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
    .chip { display: inline-flex; align-items: center; gap: 4px; padding: 2px 10px; border-radius: 99px; font-size: 12px; background: var(--cp-mint);
      border: 1px solid var(--cp-line); }
    .x { border: 0; background: none; cursor: pointer; font-size: 15px; line-height: 1; color: var(--cp-ink-2); padding: 0 0 0 2px; }
    .role { margin: 4px 0 12px; }
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
  protected readonly busy = signal(false);
  protected readonly role = signal<Role>('PROJECT');
  protected readonly candidates = signal<ControlCandidate[]>([]);
  protected readonly chars = signal<Characteristic[]>([]);
  protected readonly form = new FormGroup({
    code: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    name: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.minLength(2)] }),
    farm_ids: new FormControl<string[]>([], { nonNullable: true, validators: [Validators.required] }),
    linked: new FormControl<string[]>([], { nonNullable: true }),
    characteristic: new FormControl<string>('SOIL_TYPE', { nonNullable: true }),
    value: new FormControl('', { nonNullable: true }),
  });

  protected readonly projectStrata = computed(() => this.strata().filter((s) => s.role !== 'CONTROL'));
  protected readonly controlSites = computed(() => this.strata().filter((s) => s.role === 'CONTROL'));
  /** Current project strata that no current control site represents yet (VM0042: at least one control site per stratum). */
  protected readonly uncovered = computed(() => {
    const covered = new Set(this.controlSites().filter((s) => s.is_current).flatMap((s) => s.linked_strata.map((l) => l.record_id)));
    return this.projectStrata().filter((s) => s.is_current && !covered.has(s.record_id)).map((s) => s.code);
  });
  protected readonly linkable = computed(() => this.projectStrata().filter((s) => s.is_current));
  private readonly usedFarms = computed(() => new Set(this.strata().filter((s) => s.is_current).flatMap((s) => s.farm_ids)));
  protected readonly freeFarms = computed(() => this.farms().filter((f) => !this.usedFarms().has(f.farm_id)));
  protected readonly freeCandidates = computed(() => this.candidates().filter((f) => !this.usedFarms().has(f.farm_id)));
  /** Control sites lead with the Table 7 matching criteria. */
  protected readonly charOptions = computed<readonly string[]>(() =>
    this.role() === 'CONTROL' ? [...CONTROL_SITE_CRITERIA, ...CHARACTERISTICS.filter((c) => !(CONTROL_SITE_CRITERIA as readonly string[]).includes(c))]
      : CHARACTERISTICS);
  protected readonly layers = computed<MapLayer[]>(() =>
    this.strata().filter((s) => s.geojson && s.is_current).map((s) => ({
      geojson: s.geojson!, color: this.color(s), label: `${s.role === 'CONTROL' ? 'Control site ' : ''}${s.code} · ${s.name}`,
      fillOpacity: s.role === 'CONTROL' ? 0.12 : 0.25, dashed: s.role === 'CONTROL' })));

  protected color(s: Stratum): string {
    if (s.role === 'CONTROL') return CONTROL_COLOR;
    const codes = [...new Set(this.projectStrata().map((x) => x.code))];
    return COLORS[codes.indexOf(s.code) % COLORS.length];
  }

  protected linkedCodes(s: Stratum): string {
    return s.linked_strata.map((l) => l.code ?? 'a removed stratum').join(', ');
  }

  protected setRole(role: Role): void {
    this.role.set(role);
    this.form.patchValue({ farm_ids: [], linked: [], characteristic: role === 'CONTROL' ? 'SOIL_TEXTURE' : 'SOIL_TYPE' });
    if (role === 'CONTROL' && !this.candidates().length) {
      this.api.controlCandidates(this.projectId()).subscribe({ next: (c) => this.candidates.set(c), error: () => this.candidates.set([]) });
    }
  }

  protected addChar(): void {
    const { characteristic, value } = this.form.getRawValue();
    if (!value.trim()) return;
    this.chars.update((list) => [...list.filter((c) => c.characteristic !== characteristic),
      { characteristic: characteristic as Characteristic['characteristic'], value: value.trim() }]);
    this.form.patchValue({ value: '' });
  }

  protected removeChar(i: number): void {
    this.chars.update((list) => list.filter((_, j) => j !== i));
  }

  protected create(fd: FormGroupDirective): void {
    this.addChar();   // a value typed but not added still counts
    const v = this.form.getRawValue();
    const control = this.role() === 'CONTROL';
    const body = { code: v.code.trim(), name: v.name.trim(), farm_ids: v.farm_ids, characteristics: this.chars(), role: this.role(),
      linked_stratum_ids: control ? v.linked : [] };
    runAction(this.api.createStratum(this.projectId(), body), this.busy, this.notify, control ? 'Control site created (draft).' : 'Stratum created (draft).',
      () => {
        fd.resetForm({ code: '', name: '', farm_ids: [], linked: [], characteristic: control ? 'SOIL_TEXTURE' : 'SOIL_TYPE', value: '' });
        this.chars.set([]);
        this.changed.emit();
      });
  }

  protected approve(s: Stratum): void {
    const control = s.role === 'CONTROL';
    askReason(this.dialog, { title: `Approve ${control ? 'control site' : 'stratum'} ${s.code} v${s.version}?`, confirmLabel: 'Approve',
      message: control ? 'The control site is checked against every stratum it represents (distance, soil texture and group, slope, ecoregion, climate, rainfall). You cannot approve one you created.'
        : 'Approval freezes this version. You cannot approve a stratum you created.' }).subscribe((r) => {
      if (r) runAction(this.api.approveStratum(s.id, r.reason), this.busy, this.notify, control ? 'Control site approved.' : 'Stratum approved.',
        () => this.changed.emit());
    });
  }

  protected revise(s: Stratum): void {
    askReason(this.dialog, { title: `Revise ${s.role === 'CONTROL' ? 'control site' : 'stratum'} ${s.code}?`, confirmLabel: 'Create revision',
      message: 'A new draft version is created with the same farms; edit and approve it to replace the current version.' }).subscribe((r) => {
      if (r) runAction(this.api.updateStratum(s.id, { name: s.name, reason: r.reason }), this.busy, this.notify, 'Draft revision created.',
        () => this.changed.emit());
    });
  }
}
