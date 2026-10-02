import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, input, output, signal } from '@angular/core';
import { FormControl, FormGroup, FormGroupDirective, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { RouterLink } from '@angular/router';

import { ApiError } from '../../core/api/api.models';
import { NotifyService } from '../../core/notify.service';
import { label } from '../../farmer/farmer.models';
import { formatArea } from '../../shared/geo';
import { askReason } from '../../shared/reason-dialog';
import { runAction } from '../../shared/run-action';
import { StatusBadge } from '../../shared/status-badge';
import { Conflict, EligibleFarm, HOLDER_TYPES, Project, ProjectFarm } from '../project.models';
import { ProjectsApi } from '../projects.api';

/**
 * Participating farms (spec 7.4, 41). Only verified farms of active farmers can join; overlaps and other participations
 * are shown and must be acknowledged with a note — they never reject a farm automatically. Removing a farm ends its
 * participation and carbon-rights records; the history is kept.
 */
@Component({
  selector: 'app-project-farms-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, ReactiveFormsModule, RouterLink, MatButtonModule, MatCheckboxModule, MatFormFieldModule, MatIconModule, MatInputModule,
    MatSelectModule, StatusBadge],
  template: `
    <div class="tab-body">
      @for (f of farms(); track f.id) {
        <div class="line" [class.removed]="f.status === 'REMOVED'">
          <div class="grow">
            <a [routerLink]="['/farms', f.farm_id]"><strong>{{ f.farm_code }}</strong></a> {{ f.farm_name }}
            <span class="muted small">· {{ f.farmer_name }} ({{ f.farmer_code }}) · {{ area(f.farm_area_hectares) }}</span>
            <div class="muted small">Participation {{ f.participation_start }} → {{ f.participation_end ?? 'open' }}
              · added {{ f.added_at | date: 'mediumDate' }}
              @if (f.removal_reason) { · removed: {{ f.removal_reason }} }</div>
            <div class="chips">
              @for (r of f.carbon_rights; track r.id) {
                <span class="chip" [class.ok]="r.verification_status === 'VERIFIED'" [class.off]="r.status !== 'ACTIVE'">
                  Rights: {{ r.holder_name }} ({{ label(r.holder_type) }}{{ r.share_pct ? ', ' + r.share_pct + '%' : '' }}) · {{ label(r.verification_status) }}
                  @if (r.status !== 'ACTIVE') { · {{ label(r.status) }} }
                </span>
              }
              @if (f.farm_status !== 'VERIFIED' && f.status === 'ACTIVE') { <span class="chip warn">Farm is {{ label(f.farm_status) }}</span> }
              @if (f.boundary_changed && f.status === 'ACTIVE') { <span class="chip warn">Farm boundary changed since it joined</span> }
              @for (c of f.conflicts; track $index) { <span class="chip warn" [title]="c.detail">{{ conflictText(c) }}</span> }
            </div>
            @if (f.conflict_notes) { <div class="muted small">Acknowledged: {{ f.conflict_notes }}</div> }
          </div>
          <app-status-badge [status]="f.status === 'ACTIVE' ? 'ACTIVE' : 'REVOKED'" [text]="label(f.status)" />
          @if (canEdit() && f.status === 'ACTIVE') {
            <button mat-button type="button" class="danger" (click)="remove(f)" [disabled]="busy()">Remove</button>
          }
        </div>
      } @empty { <p class="muted">No farms in this project yet.</p> }
      <label class="toggle"><mat-checkbox [checked]="showRemoved()" (change)="showRemoved.set($event.checked); load()">Show removed farms</mat-checkbox></label>

      @if (canEdit()) {
        <h3>Add a verified farm</h3>
        <form [formGroup]="form" #fd="ngForm" (ngSubmit)="add(fd)" class="add">
          <mat-form-field subscriptSizing="dynamic" class="wide">
            <mat-label>Farm</mat-label>
            <mat-select formControlName="farm_id">
              @for (e of eligible(); track e.farm_id) {
                <mat-option [value]="e.farm_id" [disabled]="!e.eligible">
                  {{ e.farm_code }} · {{ e.farm_name }} · {{ e.farmer_name }}{{ e.eligible ? '' : ' — ' + e.reasons.join(' ') }}
                </mat-option>
              }
            </mat-select>
          </mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Participation from</mat-label><input matInput type="date" formControlName="participation_start" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Participation to (optional)</mat-label><input matInput type="date" formControlName="participation_end" /></mat-form-field>
          <div class="sub">Carbon rights for this farm</div>
          <mat-form-field subscriptSizing="dynamic">
            <mat-label>Rights holder</mat-label>
            <mat-select formControlName="holder_type">@for (h of holders; track h) { <mat-option [value]="h">{{ label(h) }}</mat-option> }</mat-select>
          </mat-form-field>
          @if (form.controls.holder_type.value !== 'FARMER') {
            <mat-form-field subscriptSizing="dynamic"><mat-label>Holder name</mat-label><input matInput formControlName="holder_name" /></mat-form-field>
          }
          <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Agreement / evidence reference</mat-label>
            <input matInput formControlName="reference" placeholder="e.g. carbon-rights clause of agreement AGR-…" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Share % (optional)</mat-label><input matInput formControlName="share_pct" inputmode="decimal" /></mat-form-field>
          @if (selectedConflicts().length) {
            <div class="conflicts" role="alert">
              <strong>Conflicts to acknowledge (reviewed during eligibility review — not an automatic rejection):</strong>
              <ul>@for (c of selectedConflicts(); track $index) { <li>{{ c.detail }}</li> }</ul>
              <mat-checkbox formControlName="acknowledge_conflicts">I acknowledge these conflicts</mat-checkbox>
              <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Why the farm can still join</mat-label>
                <input matInput formControlName="conflict_notes" /></mat-form-field>
            </div>
          }
          <button mat-flat-button type="submit" [disabled]="busy() || form.invalid">Add farm</button>
        </form>
        @if (error(); as e) { <p class="form-error" role="alert">{{ e }}</p> }
      } @else if (!project().is_editable) {
        <p class="muted small">Farms can be changed only while the project is Draft or in Data collection.</p>
      }
    </div>
  `,
  styles: `
    .line { display: flex; align-items: flex-start; gap: 10px; padding: 10px 0; border-bottom: 1px solid var(--mat-sys-outline-variant); flex-wrap: wrap; }
    .line.removed { opacity: .65; } .grow { flex: 1; min-width: 260px; }
    .chips { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 4px; }
    .chip { font-size: 11px; padding: 2px 8px; border-radius: 999px; background: var(--mat-sys-surface-container-high); }
    .chip.ok { background: #e8f5e9; color: #1b5e20; } .chip.warn { background: #fff3e0; color: #e65100; } .chip.off { text-decoration: line-through; }
    .add { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; } .wide { min-width: 300px; flex: 1; }
    .sub { width: 100%; font-weight: 600; margin-top: 4px; } h3 { margin: 20px 0 8px; font: var(--mat-sys-title-small); }
    .conflicts { width: 100%; padding: 10px; border: 1px solid #ffb74d; border-radius: 8px; background: #fff8e1; }
    .toggle { display: block; margin: 8px 0; } .danger { color: #b71c1c; }
  `,
})
export class ProjectFarmsPanel implements OnInit {
  readonly project = input.required<Project>();
  readonly changed = output<void>();
  private readonly api = inject(ProjectsApi);
  private readonly notify = inject(NotifyService);
  private readonly dialog = inject(MatDialog);
  protected readonly label = label;
  protected readonly area = formatArea;
  protected readonly holders = HOLDER_TYPES;
  protected readonly farms = signal<ProjectFarm[]>([]);
  protected readonly eligible = signal<EligibleFarm[]>([]);
  protected readonly busy = signal(false);
  protected readonly showRemoved = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly selectedFarm = signal<string>('');
  protected readonly canEdit = computed(() => this.project().can_manage && this.project().is_editable);
  protected readonly selectedConflicts = computed(() => this.eligible().find((e) => e.farm_id === this.selectedFarm())?.conflicts ?? []);
  protected readonly form = new FormGroup({
    farm_id: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    participation_start: new FormControl(new Date().toISOString().slice(0, 10), { nonNullable: true, validators: [Validators.required] }),
    participation_end: new FormControl('', { nonNullable: true }),
    holder_type: new FormControl<string>('FARMER', { nonNullable: true }),
    holder_name: new FormControl('', { nonNullable: true }),
    reference: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.maxLength(200)] }),
    share_pct: new FormControl('', { nonNullable: true, validators: [Validators.pattern(/^\d{1,3}(\.\d{1,3})?$/)] }),
    acknowledge_conflicts: new FormControl(false, { nonNullable: true }),
    conflict_notes: new FormControl('', { nonNullable: true }),
  });

  ngOnInit(): void {
    this.form.controls.farm_id.valueChanges.subscribe((v) => this.selectedFarm.set(v));
    this.load();
  }

  load(): void {
    this.api.farms(this.project().id, this.showRemoved()).subscribe((f) => this.farms.set(f));
    if (this.canEdit()) this.api.eligibleFarms(this.project().id).subscribe((e) => this.eligible.set(e));
  }

  conflictText(c: Conflict): string {
    return c.kind === 'FARM_OVERLAP' ? `Overlap (${label(c.status)})` : `Also in ${c.other_project_code ?? 'another project'}`;
  }

  add(fd?: FormGroupDirective): void {
    const v = this.form.getRawValue();
    const blank = (s: string) => (s.trim() ? s.trim() : null);
    this.error.set(null);
    this.busy.set(true);
    this.api.addFarm(this.project().id, {
      farm_id: v.farm_id, participation_start: v.participation_start, participation_end: blank(v.participation_end),
      carbon_rights: { holder_type: v.holder_type, holder_name: blank(v.holder_name), reference: blank(v.reference), share_pct: blank(v.share_pct),
        effective_from: v.participation_start },
      acknowledge_conflicts: v.acknowledge_conflicts, conflict_notes: blank(v.conflict_notes),
    }).subscribe({
      next: (f) => {
        this.busy.set(false);
        this.notify.success(`${f.farm_code} added; project boundary recomputed by SQL Server.`);
        (fd ?? this.form).reset({ participation_start: v.participation_start, holder_type: 'FARMER' });
        this.load();
        this.changed.emit();
      },
      error: (e: unknown) => {
        this.busy.set(false);
        const err = ApiError.from(e);
        this.error.set(err.code === 'CONFLICTS_REQUIRE_ACKNOWLEDGEMENT' ? 'Acknowledge the conflicts listed above with a note.' : err.message);
      },
    });
  }

  remove(f: ProjectFarm): void {
    askReason(this.dialog, { title: `Remove ${f.farm_code} from the project?`, confirmLabel: 'Remove', danger: true,
      message: 'The participation and its carbon-rights records are ended, not deleted. The project boundary is recomputed.' }).subscribe((r) => {
      if (r) runAction(this.api.removeFarm(this.project().id, f.farm_id, r.reason), this.busy, this.notify, 'Farm removed from the project.', () => {
        this.load();
        this.changed.emit();
      });
    });
  }
}
