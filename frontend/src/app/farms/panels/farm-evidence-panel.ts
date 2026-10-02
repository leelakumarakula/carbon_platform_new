import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, input, output, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { Observable, of, switchMap } from 'rxjs';

import { NotifyService } from '../../core/notify.service';
import { label } from '../../farmer/farmer.models';
import { askReason } from '../../shared/reason-dialog';
import { runAction } from '../../shared/run-action';
import { StatusBadge } from '../../shared/status-badge';
import { CLAIM_TYPES, EVIDENCE_SOURCES, Evidence, Farm } from '../farm.models';
import { FarmsApi } from '../farms.api';

/** Evidence engine inputs (spec §11): claims are never trusted blindly — each needs a source and review. */
@Component({
  selector: 'app-farm-evidence-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, DatePipe, MatFormFieldModule, MatInputModule, MatSelectModule, MatButtonModule, MatIconModule, StatusBadge],
  template: `
    <div class="tab-body">
      @for (e of items(); track e.id) {
        <div class="line">
          <mat-icon>{{ e.source_type === 'SATELLITE' ? 'satellite_alt' : e.document_id ? 'photo_camera' : 'fact_check' }}</mat-icon>
          <div class="grow">
            <strong>{{ label(e.claim_type) }}</strong> · {{ e.description }}
            <div class="muted small">{{ label(e.source_type) }} · {{ e.created_at | date: 'medium' }}
              @if (e.external_reference) { · ref {{ e.external_reference }} }
              @if (e.distance_to_boundary_m !== null) { · {{ e.distance_to_boundary_m === 0 ? 'inside the boundary' : e.distance_to_boundary_m + ' m from the boundary' }} }
            </div>
            @if (e.review_notes) { <div class="muted small">Review: {{ e.review_notes }}</div> }
          </div>
          <app-status-badge [status]="tone(e.verification_status)" [text]="label(e.verification_status)" />
          @if (farm().can_review) {
            <button mat-button type="button" (click)="review(e, 'NEEDS_REVIEW')" [disabled]="busy()">Flag</button>
            <button mat-stroked-button type="button" (click)="review(e, 'VERIFIED')" [disabled]="busy()">Accept</button>
          }
        </div>
      } @empty { <p class="muted">No evidence yet.</p> }
      @if (canAdd()) {
        <form [formGroup]="form" (ngSubmit)="add()" class="form-grid add">
          <mat-form-field><mat-label>Supports claim about</mat-label>
            <mat-select formControlName="claim_type">@for (c of claims; track c) { <mat-option [value]="c">{{ label(c) }}</mat-option> }</mat-select>
          </mat-form-field>
          <mat-form-field><mat-label>Source</mat-label>
            <mat-select formControlName="source_type">
              @for (s of sources(); track s) { <mat-option [value]="s">{{ label(s) }}</mat-option> }
            </mat-select>
          </mat-form-field>
          <mat-form-field class="span-all"><mat-label>Description</mat-label><input matInput formControlName="description" /></mat-form-field>
          <mat-form-field><mat-label>External reference (scene id, record no.)</mat-label><input matInput formControlName="external_reference" /></mat-form-field>
          <div class="row-actions span-all">
            <input #photo type="file" hidden accept="image/*,.pdf" capture="environment" (change)="file.set(photo.files?.[0] ?? null)" />
            <button mat-stroked-button type="button" (click)="photo.click()"><mat-icon>add_a_photo</mat-icon> {{ file()?.name ?? 'Photo / file' }}</button>
            <button mat-stroked-button type="button" (click)="locate()"><mat-icon>my_location</mat-icon> {{ coords() ? 'Location captured' : 'Capture location' }}</button>
            <button mat-flat-button type="submit" [disabled]="busy() || form.invalid">Add evidence</button>
          </div>
        </form>
      }
    </div>
  `,
  styles: `
    .line { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--mat-sys-outline-variant); flex-wrap: wrap; }
    .grow { flex: 1; min-width: 220px; } .add { margin-top: 16px; }
  `,
})
export class FarmEvidencePanel implements OnInit {
  readonly farm = input.required<Farm>();
  readonly changed = output<void>();
  private readonly api = inject(FarmsApi);
  private readonly notify = inject(NotifyService);
  private readonly dialog = inject(MatDialog);
  protected readonly items = signal<Evidence[]>([]);
  protected readonly busy = signal(false);
  protected readonly file = signal<File | null>(null);
  protected readonly coords = signal<{ lat: number; lon: number } | null>(null);
  protected readonly label = label;
  protected readonly claims = CLAIM_TYPES;
  /** Farmers record their own evidence as a farmer claim; staff choose the actual source. */
  protected readonly sources = computed(() => (this.farm().is_self ? ['FARMER_CLAIM'] : [...EVIDENCE_SOURCES]));
  protected readonly canAdd = computed(() => this.farm().can_manage && this.farm().status !== 'INACTIVE');
  protected readonly form = new FormGroup({
    claim_type: new FormControl('CROP', { nonNullable: true }),
    source_type: new FormControl('FIELD_AGENT', { nonNullable: true }),
    description: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.minLength(3)] }),
    external_reference: new FormControl('', { nonNullable: true }),
  });

  ngOnInit(): void {
    if (this.farm().is_self) this.form.controls.source_type.setValue('FARMER_CLAIM');
    this.load();
  }

  load(): void {
    this.api.evidence(this.farm().id).subscribe((e) => this.items.set(e));
  }

  tone(s: string): string {
    return { VERIFIED: 'ACTIVE', NEEDS_REVIEW: 'WARNING', REJECTED: 'FAILED' }[s] ?? 'INFO';
  }

  locate(): void {
    navigator.geolocation?.getCurrentPosition((p) => this.coords.set({ lat: p.coords.latitude, lon: p.coords.longitude }),
      (err) => this.notify.error(new Error(`Could not read location: ${err.message}`)), { enableHighAccuracy: true, timeout: 20000 });
  }

  add(): void {
    const v = this.form.getRawValue();
    const id = this.farm().id;
    const file = this.file();
    const category = file?.type.startsWith('image/') ? 'FIELD_PHOTO' : 'OTHER';
    const upload$: Observable<{ id: string } | null> = file ? this.api.uploadDocument(id, file, category, v.description) : of(null);
    const c = this.coords();
    runAction(upload$.pipe(switchMap((doc) => this.api.addEvidence(id, {
      claim_type: v.claim_type, source_type: v.source_type, description: v.description.trim(), document_id: doc?.id ?? null,
      external_reference: v.external_reference.trim() || null, observed_at: new Date().toISOString(),
      latitude: c ? c.lat.toFixed(7) : null, longitude: c ? c.lon.toFixed(7) : null,
    }))), this.busy, this.notify, 'Evidence added.', () => {
      this.form.patchValue({ description: '', external_reference: '' });
      this.file.set(null);
      this.coords.set(null);
      this.load();
      this.changed.emit();
    });
  }

  review(e: Evidence, status: 'VERIFIED' | 'NEEDS_REVIEW'): void {
    askReason(this.dialog, { title: status === 'VERIFIED' ? 'Accept this evidence?' : 'Flag this evidence for follow-up?',
      confirmLabel: status === 'VERIFIED' ? 'Accept' : 'Flag' }).subscribe((r) => {
      if (r) runAction(this.api.reviewEvidence(this.farm().id, e.id, status, r.reason), this.busy, this.notify, 'Evidence reviewed.', () => this.load());
    });
  }
}
