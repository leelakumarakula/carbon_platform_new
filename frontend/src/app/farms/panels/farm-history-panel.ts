import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, input, output, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatTooltipModule } from '@angular/material/tooltip';

import { NotifyService } from '../../core/notify.service';
import { label } from '../../farmer/farmer.models';
import { askReason } from '../../shared/reason-dialog';
import { runAction } from '../../shared/run-action';
import { StatusBadge } from '../../shared/status-badge';
import { Farm, HistoryKind, HistoryRecord } from '../farm.models';
import { FarmsApi } from '../farms.api';
import { FieldDef, HISTORY_FIELDS, changedFields, toPayload } from './history-fields';

/** Land / crop / practice history. Edits create new versions; earlier versions stay visible and unchanged. */
@Component({
  selector: 'app-farm-history-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, DatePipe, MatButtonToggleModule, MatFormFieldModule, MatInputModule, MatSelectModule, MatButtonModule,
    MatIconModule, MatTooltipModule, StatusBadge],
  template: `
    <div class="tab-body">
      <mat-button-toggle-group [value]="kind()" (change)="setKind($event.value)" aria-label="History type">
        <mat-button-toggle value="land">Land use ({{ farm().history_counts.land }})</mat-button-toggle>
        <mat-button-toggle value="crop">Crops ({{ farm().history_counts.crop }})</mat-button-toggle>
        <mat-button-toggle value="practice">Practices ({{ farm().history_counts.practice }})</mat-button-toggle>
      </mat-button-toggle-group>

      @for (r of records(); track r.id) {
        <div class="record">
          <div class="grow">
            <strong>{{ title(r) }}</strong>
            <div class="muted small">{{ summary(r) }}</div>
            <div class="muted small">v{{ r.version }} · {{ label(r.source) }} · {{ r.recorded_at | date: 'medium' }}
              @if (r.change_reason) { · “{{ r.change_reason }}” }</div>
            @if (openVersions() === r.record_id) {
              <div class="versions">
                @for (v of versions(); track v.id) {
                  <div class="small">v{{ v.version }} {{ v.is_retracted ? '(retracted)' : '' }} — {{ summary(v) }} · {{ v.recorded_at | date: 'short' }}
                    @if (v.change_reason) { · {{ v.change_reason }} }</div>
                }
              </div>
            }
          </div>
          <app-status-badge [status]="tone(r.verification_status)" [text]="label(r.verification_status)" />
          @if (r.version > 1) {
            <button mat-icon-button type="button" (click)="showVersions(r)" matTooltip="Version history" aria-label="Version history"><mat-icon>history</mat-icon></button>
          }
          @if (farm().can_manage && editable()) {
            <button mat-icon-button type="button" (click)="startAmend(r)" matTooltip="Amend (new version)" aria-label="Amend"><mat-icon>edit</mat-icon></button>
            <button mat-icon-button type="button" (click)="retract(r)" matTooltip="Retract" aria-label="Retract"><mat-icon>delete_outline</mat-icon></button>
          }
          @if (farm().can_review) {
            <button mat-icon-button type="button" (click)="review(r)" matTooltip="Review" aria-label="Review"><mat-icon>fact_check</mat-icon></button>
          }
        </div>
      } @empty { <p class="muted">No {{ kind() }} history recorded.</p> }

      @if (farm().can_manage && editable()) {
        <h3>{{ amending() ? 'Amend record (creates version ' + ((amending()?.version ?? 0) + 1) + ')' : 'Add record' }}</h3>
        <form [formGroup]="form" (ngSubmit)="submit()" class="form-grid">
          @for (d of defs(); track d.key) {
            <mat-form-field>
              <mat-label>{{ d.label }}</mat-label>
              @if (d.type === 'select') {
                <mat-select [formControlName]="d.key">
                  @if (!d.required) { <mat-option [value]="null">—</mat-option> }
                  @for (o of d.options; track o) { <mat-option [value]="o">{{ label(o) }}</mat-option> }
                </mat-select>
              } @else {
                <input matInput [type]="d.type" [formControlName]="d.key" />
              }
            </mat-form-field>
          }
          <div class="row-actions span-all">
            @if (amending()) { <button mat-button type="button" (click)="cancelAmend()">Cancel</button> }
            <button mat-flat-button type="submit" [disabled]="busy() || form.invalid">{{ amending() ? 'Save new version' : 'Add' }}</button>
          </div>
        </form>
      }
    </div>
  `,
  styles: `
    mat-button-toggle-group { margin-bottom: 12px; flex-wrap: wrap; }
    .record { display: flex; align-items: center; gap: 8px; padding: 8px 0; border-bottom: 1px solid var(--mat-sys-outline-variant); }
    .grow { flex: 1; min-width: 0; } .versions { margin-top: 6px; padding-left: 10px; border-left: 2px solid var(--mat-sys-outline-variant); }
    h3 { font: var(--mat-sys-title-medium); margin: 20px 0 8px; }
  `,
})
export class FarmHistoryPanel implements OnInit {
  readonly farm = input.required<Farm>();
  readonly changed = output<void>();
  private readonly api = inject(FarmsApi);
  private readonly notify = inject(NotifyService);
  private readonly dialog = inject(MatDialog);
  protected readonly label = label;
  protected readonly kind = signal<HistoryKind>('land');
  protected readonly records = signal<HistoryRecord[]>([]);
  protected readonly versions = signal<HistoryRecord[]>([]);
  protected readonly openVersions = signal<string | null>(null);
  protected readonly amending = signal<HistoryRecord | null>(null);
  protected readonly busy = signal(false);
  protected readonly defs = computed<FieldDef[]>(() => HISTORY_FIELDS[this.kind()]);
  protected readonly editable = computed(() => this.farm().status !== 'INACTIVE');
  protected form = this.buildForm('land');

  ngOnInit(): void {
    this.load();
  }

  setKind(k: HistoryKind): void {
    this.kind.set(k);
    this.amending.set(null);
    this.form = this.buildForm(k);
    this.load();
  }

  private buildForm(k: HistoryKind, values: Record<string, unknown> = {}): FormGroup {
    const group: Record<string, FormControl> = {};
    for (const d of HISTORY_FIELDS[k]) {
      const initial = values[d.key] ?? (d.key === 'source' ? 'FARMER_CLAIM' : d.key === 'year' ? new Date().getFullYear() : null);
      group[d.key] = new FormControl(initial, d.required ? [Validators.required] : []);
    }
    return new FormGroup(group);
  }

  load(): void {
    this.api.history(this.farm().id, this.kind()).subscribe((r) => this.records.set(r));
  }

  title(r: HistoryRecord): string {
    const f = r.fields;
    const k = this.kind();
    if (k === 'land') return `${f['year']} · ${label(String(f['land_use']))}`;
    if (k === 'crop') return `${f['year']} ${f['season'] ?? ''} · ${f['crop_name']}`;
    return `${f['year']} · ${label(String(f['practice_phase']))} · ${f['practice_type']}`;
  }

  summary(r: HistoryRecord): string {
    const skip = new Set(['year', 'land_use', 'crop_name', 'practice_type', 'practice_phase']);
    return Object.entries(r.fields).filter(([k, v]) => v !== null && v !== '' && !skip.has(k)).map(([k, v]) => `${label(k)}: ${v}`).join(' · ');
  }

  tone(s: string): string {
    return { VERIFIED: 'ACTIVE', NEEDS_REVIEW: 'WARNING', REJECTED: 'FAILED' }[s] ?? 'INFO';
  }

  showVersions(r: HistoryRecord): void {
    if (this.openVersions() === r.record_id) {
      this.openVersions.set(null);
      return;
    }
    this.api.historyVersions(this.farm().id, this.kind(), r.record_id).subscribe((v) => {
      this.versions.set(v);
      this.openVersions.set(r.record_id);
    });
  }

  startAmend(r: HistoryRecord): void {
    this.amending.set(r);
    this.form = this.buildForm(this.kind(), { ...r.fields, source: r.source, notes: r.notes });
  }

  cancelAmend(): void {
    this.amending.set(null);
    this.form = this.buildForm(this.kind());
  }

  submit(): void {
    const payload = toPayload(this.defs(), this.form.getRawValue() as Record<string, unknown>);
    const rec = this.amending();
    if (!rec) {
      runAction(this.api.addHistory(this.farm().id, this.kind(), payload), this.busy, this.notify, 'Record added.', () => this.done());
      return;
    }
    const diff = changedFields(this.defs(), { ...rec.fields, source: rec.source, notes: rec.notes }, payload);
    if (!Object.keys(diff).length) {
      this.notify.error(new Error('Nothing changed.'));
      return;
    }
    askReason(this.dialog, { title: 'Why is this record being amended?', confirmLabel: 'Save new version' }).subscribe((r) => {
      if (r) runAction(this.api.amendHistory(this.farm().id, this.kind(), rec.record_id, diff, r.reason), this.busy, this.notify,
        'New version saved; the previous version is kept.', () => this.done());
    });
  }

  retract(r: HistoryRecord): void {
    askReason(this.dialog, { title: 'Retract this record?', message: 'It stays in the version history, marked as retracted.',
      confirmLabel: 'Retract', danger: true }).subscribe((res) => {
      if (res) runAction(this.api.retractHistory(this.farm().id, this.kind(), r.record_id, res.reason), this.busy, this.notify,
        'Record retracted.', () => this.done());
    });
  }

  review(r: HistoryRecord): void {
    askReason(this.dialog, { title: `Mark "${this.title(r)}" as verified?`, message: 'Use the review notes to record what evidence you checked.',
      confirmLabel: 'Mark verified' }).subscribe((res) => {
      if (res) runAction(this.api.reviewHistory(this.farm().id, this.kind(), r.record_id, 'VERIFIED', res.reason), this.busy, this.notify,
        'Record reviewed.', () => this.done());
    });
  }

  private done(): void {
    this.cancelAmend();
    this.load();
    this.changed.emit();
  }
}
