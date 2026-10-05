import { ChangeDetectionStrategy, Component, OnInit, computed, effect, inject, input, output, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';

import { NotifyService } from '../../core/notify.service';
import { label } from '../../farmer/farmer.models';
import { askReason } from '../../shared/reason-dialog';
import { runAction } from '../../shared/run-action';
import { StatusBadge } from '../../shared/status-badge';
import { Farm, Ownership } from '../farm.models';
import { FarmsApi } from '../farms.api';

const EVIDENCE_CATEGORIES = ['LAND_RECORD', 'LAND_TITLE', 'LEASE_AGREEMENT', 'OTHER'];

/** Who owns or holds rights to the land — recorded separately because the farmer may not be the owner. */
@Component({
  selector: 'app-farm-ownership-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, MatFormFieldModule, MatInputModule, MatSelectModule, MatButtonModule, MatIconModule, StatusBadge],
  template: `
    <div class="tab-body">
      @for (o of records(); track o.id) {
        <div class="line" [class.ended]="!o.is_current">
          <div class="grow">
            <strong>{{ o.owner_name }}</strong> · {{ label(o.owner_type) }} · operator is {{ label(o.operator_relationship) }}
            {{ o.ownership_share_pct ? '· ' + o.ownership_share_pct + '%' : '' }}
            <div class="muted small">{{ o.title_reference ?? 'no title reference' }} · {{ o.valid_from ?? '—' }} → {{ o.valid_to ?? 'current' }}
              @if (o.end_reason) { · ended: {{ o.end_reason }} }</div>
            <div class="small" [class.muted]="!o.evidence_document_id" data-testid="ownership-evidence">
              Evidence: {{ o.evidence_document_id ? docTitle(o.evidence_document_id) : 'no document linked' }}</div>
            @if (o.review_notes) { <div class="muted small">Review: {{ o.review_notes }}</div> }
          </div>
          <app-status-badge [status]="o.verification_status === 'VERIFIED' ? 'ACTIVE' : o.verification_status === 'REJECTED' ? 'FAILED' : 'INFO'"
                            [text]="label(o.verification_status)" />
          @if (farm().can_review && o.is_current && pending(o)) {
            <button mat-button type="button" (click)="review(o, 'REJECTED')" [disabled]="busy()">Reject</button>
            <button mat-stroked-button type="button" (click)="review(o, 'VERIFIED')" [disabled]="busy()">Verify</button>
          }
          @if (editable() && o.is_current) {
            <button mat-icon-button type="button" (click)="end(o)" aria-label="End ownership record"><mat-icon>event_busy</mat-icon></button>
          }
        </div>
      } @empty { <p class="muted">No ownership or tenure records. At least one is required before submitting the farm.</p> }
      @if (editable()) {
        <form [formGroup]="form" (ngSubmit)="add()" class="form-grid add">
          <mat-form-field><mat-label>Owner type</mat-label>
            <mat-select formControlName="owner_type">@for (t of ownerTypes; track t) { <mat-option [value]="t">{{ label(t) }}</mat-option> }</mat-select>
          </mat-form-field>
          @if (form.controls.owner_type.value !== 'FARMER') {
            <mat-form-field><mat-label>Owner name</mat-label><input matInput formControlName="owner_name" /></mat-form-field>
          }
          <mat-form-field><mat-label>Farmer's relationship</mat-label>
            <mat-select formControlName="operator_relationship">@for (r of relationships; track r) { <mat-option [value]="r">{{ label(r) }}</mat-option> }</mat-select>
          </mat-form-field>
          <mat-form-field><mat-label>Share %</mat-label><input matInput type="number" min="0.01" max="100" formControlName="share" /></mat-form-field>
          <mat-form-field><mat-label>Title / survey reference</mat-label><input matInput formControlName="title_reference" /></mat-form-field>
          <mat-form-field><mat-label>Valid from</mat-label><input matInput type="date" formControlName="valid_from" /></mat-form-field>
          <mat-form-field><mat-label>Evidence document</mat-label>
            <mat-select formControlName="evidence_document_id" data-testid="ownership-evidence-select">
              <mat-option [value]="null">None</mat-option>
              @for (d of evidenceDocs(); track d.id) { <mat-option [value]="d.id">{{ d.title }} · {{ label(d.category) }}</mat-option> }
            </mat-select>
            <mat-hint>{{ evidenceDocs().length ? 'The 7/12 extract, title deed or lease the GIS specialist will check.'
              : 'Upload the land record in the Documents tab first.' }}</mat-hint>
          </mat-form-field>
          <div class="row-actions span-all"><button mat-flat-button type="submit" [disabled]="busy() || form.invalid">Record ownership</button></div>
        </form>
      }
    </div>
  `,
  styles: `
    .line { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--mat-sys-outline-variant); flex-wrap: wrap; }
    .grow { flex: 1; min-width: 220px; } .ended { opacity: .6; } .add { margin-top: 16px; }
  `,
})
export class FarmOwnershipPanel implements OnInit {
  readonly farm = input.required<Farm>();
  readonly changed = output<void>();
  private readonly api = inject(FarmsApi);
  private readonly notify = inject(NotifyService);
  private readonly dialog = inject(MatDialog);
  protected readonly records = signal<Ownership[]>([]);
  protected readonly busy = signal(false);
  protected readonly label = label;
  protected readonly ownerTypes = ['FARMER', 'INDIVIDUAL', 'ORGANIZATION', 'GOVERNMENT', 'COMMUNITY'];
  protected readonly relationships = ['OWNER', 'CO_OWNER', 'TENANT', 'LESSEE', 'SHARECROPPER', 'CUSTODIAN', 'OTHER'];
  /** Only unreviewed records can be reviewed; the server refuses re-review. */
  protected readonly pending = (o: Ownership) => o.verification_status === 'UNVERIFIED' || o.verification_status === 'NEEDS_REVIEW';
  protected readonly editable = computed(() => this.farm().can_manage && this.farm().status === 'DRAFT');
  protected readonly form = new FormGroup({
    owner_type: new FormControl('FARMER', { nonNullable: true }),
    owner_name: new FormControl('', { nonNullable: true }),
    operator_relationship: new FormControl('OWNER', { nonNullable: true }),
    share: new FormControl<number | null>(null),
    title_reference: new FormControl('', { nonNullable: true }),
    valid_from: new FormControl('', { nonNullable: true }),
    evidence_document_id: new FormControl<string | null>(null),
  });
  /** Documents the server accepts as ownership evidence (land record, title, lease, other), newest land record first. */
  protected readonly evidenceDocs = computed(() => (this.farm().documents ?? [])
    .filter((d) => EVIDENCE_CATEGORIES.includes(d.category) && d.status !== 'DELETED')
    .sort((a, b) => Number(b.category !== 'OTHER') - Number(a.category !== 'OTHER') || b.created_at.localeCompare(a.created_at)));

  constructor() {
    effect(() => {   // preselect the newest land document when the form is empty
      const first = this.evidenceDocs()[0];
      if (first && !this.form.controls.evidence_document_id.value) this.form.controls.evidence_document_id.setValue(first.id);
    });
  }

  protected docTitle(id: string): string {
    return (this.farm().documents ?? []).find((d) => d.id === id)?.title ?? 'document';
  }

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.api.ownership(this.farm().id).subscribe((r) => this.records.set(r));
  }

  add(): void {
    const v = this.form.getRawValue();
    const self = v.owner_type === 'FARMER';
    runAction(this.api.addOwnership(this.farm().id, {
      owner_type: v.owner_type, owner_farmer_id: self ? this.farm().farmer_id : null, owner_name: self ? null : v.owner_name.trim() || null,
      operator_relationship: v.operator_relationship, ownership_share_pct: v.share, title_reference: v.title_reference.trim() || null,
      valid_from: v.valid_from || null, evidence_document_id: v.evidence_document_id || null,
    }), this.busy, this.notify, 'Ownership recorded.', () => {
      this.form.reset({ owner_type: 'FARMER', operator_relationship: 'OWNER', owner_name: '', share: null, title_reference: '', valid_from: '',
        evidence_document_id: this.evidenceDocs()[0]?.id ?? null });
      this.load();
      this.changed.emit();
    });
  }

  end(o: Ownership): void {
    askReason(this.dialog, { title: `End ownership by ${o.owner_name}?`, message: 'The record is kept with today as its end date.',
      confirmLabel: 'End record' }).subscribe((r) => {
      if (r) runAction(this.api.endOwnership(this.farm().id, o.id, new Date().toISOString().slice(0, 10), r.reason), this.busy, this.notify,
        'Ownership record ended.', () => {
          this.load();
          this.changed.emit();
        });
    });
  }

  review(o: Ownership, status: 'VERIFIED' | 'REJECTED'): void {
    askReason(this.dialog, { title: `${status === 'VERIFIED' ? 'Verify' : 'Reject'} ownership by ${o.owner_name}?`,
      message: 'Record which land record or document you checked.', confirmLabel: status === 'VERIFIED' ? 'Verify' : 'Reject',
      danger: status === 'REJECTED' }).subscribe((r) => {
      if (r) runAction(this.api.reviewOwnership(this.farm().id, o.id, status, r.reason), this.busy, this.notify, 'Ownership reviewed.', () => {
        this.load();
        this.changed.emit();
      });
    });
  }
}
