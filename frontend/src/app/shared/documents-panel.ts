import { DatePipe, DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, effect, inject, input, output, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatTooltipModule } from '@angular/material/tooltip';
import { Observable } from 'rxjs';

import { DocumentsApi } from '../core/api/documents.api';
import { NotifyService } from '../core/notify.service';
import { DocumentInfo, label } from '../farmer/farmer.models';
import { StatusBadge } from './status-badge';

export type UploadFn = (file: File, category: string, title: string) => Observable<{ id: string }>;

/** Lists an entity's documents (all versions kept) and uploads new ones. Files are validated server-side. */
@Component({
  selector: 'app-documents-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, DatePipe, DecimalPipe, MatButtonModule, MatIconModule, MatFormFieldModule, MatInputModule, MatSelectModule,
    MatTooltipModule, StatusBadge],
  template: `
    @if (canUpload()) {
      <form class="upload" [formGroup]="form" (ngSubmit)="submit()">
        <mat-form-field subscriptSizing="dynamic">
          <mat-label>Category</mat-label>
          <mat-select formControlName="category">
            @for (c of categories(); track c) { <mat-option [value]="c">{{ label(c) }}</mat-option> }
          </mat-select>
        </mat-form-field>
        <mat-form-field subscriptSizing="dynamic">
          <mat-label>Title</mat-label>
          <input matInput formControlName="title" maxlength="200" />
        </mat-form-field>
        <input #fileInput type="file" hidden accept=".pdf,.png,.jpg,.jpeg,.webp" (change)="pick(fileInput.files)" />
        <button mat-stroked-button type="button" (click)="fileInput.click()"><mat-icon>attach_file</mat-icon> {{ file()?.name ?? 'Choose file' }}</button>
        <button mat-flat-button type="submit" [disabled]="busy() || form.invalid || !file()">Upload</button>
        <span class="muted small">PDF, PNG, JPEG or WebP · max 15 MB</span>
      </form>
    }
    @for (d of documents(); track d.id) {
      <div class="doc">
        <mat-icon>{{ d.versions[d.versions.length - 1]?.mime_type?.startsWith('image/') ? 'image' : 'description' }}</mat-icon>
        <div class="meta">
          <strong>{{ d.title }}</strong>
          <div class="muted small">
            {{ label(d.category) }} · v{{ d.current_version }} · {{ (d.versions[d.versions.length - 1]?.size_bytes ?? 0) / 1024 | number: '1.0-0' }} KB
            · {{ d.created_at | date: 'mediumDate' }}
          </div>
        </div>
        @if (d.sensitivity === 'RESTRICTED') { <app-status-badge status="WARNING" text="Restricted" /> }
        @switch (d.scan_state) {
          @case ('NOT_SCANNED') {
            <mat-icon class="muted" data-testid="scan-not-scanned" matTooltip="No antivirus engine configured; only a test-signature check ran.">gpp_maybe</mat-icon>
          }
          @case ('PENDING_SCAN') {
            <mat-icon class="muted" data-testid="scan-pending" matTooltip="Accepted before antivirus scanning; a background rescan is due.">hourglass_empty</mat-icon>
          }
          @case ('CLEAN') { <mat-icon class="ok" data-testid="scan-clean" matTooltip="Antivirus scan: clean">verified_user</mat-icon> }
        }
        @if (d.status === 'QUARANTINED') {
          <app-status-badge data-testid="scan-quarantined" status="CRITICAL" [text]="quarantineText(d)" />
        } @else {
          <button mat-icon-button type="button" (click)="download(d)" aria-label="Download" matTooltip="Download (audited)"><mat-icon>download</mat-icon></button>
        }
      </div>
    } @empty {
      <p class="muted">No documents yet.</p>
    }
  `,
  styles: `
    .upload { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 12px; }
    .doc { display: flex; align-items: center; gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--mat-sys-outline-variant); }
    .meta { flex: 1; min-width: 0; }
    .ok { color: var(--mat-sys-primary); }
  `,
})
export class DocumentsPanel {
  readonly documents = input<DocumentInfo[]>([]);
  readonly categories = input<readonly string[]>([]);
  readonly canUpload = input(false);
  readonly uploadFn = input<UploadFn | null>(null);
  /** Category to preselect (e.g. LAND_RECORD when arriving from the land-records card); ignored when not offered. */
  readonly presetCategory = input<string | null>(null);
  readonly uploaded = output<string>();

  private readonly docs = inject(DocumentsApi);
  private readonly notify = inject(NotifyService);
  protected readonly label = label;
  protected readonly file = signal<File | null>(null);
  protected readonly busy = signal(false);
  protected readonly form = new FormGroup({
    category: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    title: new FormControl('', { nonNullable: true }),
  });

  constructor() {
    effect(() => {
      const c = this.presetCategory();
      if (c && this.categories().includes(c)) this.form.controls.category.setValue(c);
    });
  }

  pick(files: FileList | null): void {
    this.file.set(files?.[0] ?? null);
  }

  submit(): void {
    const fn = this.uploadFn();
    const file = this.file();
    if (!fn || !file || this.form.invalid) return;
    this.busy.set(true);
    const { category, title } = this.form.getRawValue();
    fn(file, category, title || file.name).subscribe({
      next: (r) => {
        this.busy.set(false);
        this.file.set(null);
        const c = this.presetCategory();
        this.form.reset({ category: c && this.categories().includes(c) ? c : '', title: '' });
        this.notify.success('Document uploaded.');
        this.uploaded.emit(r.id);
      },
      error: (e: unknown) => {
        this.busy.set(false);
        this.notify.error(e);
      },
    });
  }

  protected quarantineText(d: DocumentInfo): string {
    return d.scan_state === 'INFECTED' ? 'Quarantined: malware' : d.scan_state === 'SCANNER_UNAVAILABLE' ? 'Quarantined: awaiting scan' : 'Quarantined';
  }

  download(d: DocumentInfo): void {
    const v = d.versions[d.versions.length - 1];
    this.docs.download(d.id, v?.file_name ?? 'document').subscribe({ error: (e: unknown) => this.notify.error(e) });
  }
}
