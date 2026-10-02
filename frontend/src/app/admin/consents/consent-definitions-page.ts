import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';

import { ApiError } from '../../core/api/api.models';
import { ConsentDefinition, ConsentsApi } from '../../core/api/consents.api';
import { NotifyService } from '../../core/notify.service';
import { PageHeader } from '../../shared/page-header';
import { askReason } from '../../shared/reason-dialog';
import { runAction } from '../../shared/run-action';
import { StateView } from '../../shared/state-view';
import { StatusBadge } from '../../shared/status-badge';

/**
 * Consent types (decision D3). Publishing an existing type creates its next version and retires the previous
 * one; definitions are never edited. "Required for activation" ones must be granted (current version) before a
 * farmer can become ACTIVE. The legal wording itself lives in the consent form identified by "text version".
 */
@Component({
  selector: 'app-consent-definitions-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, ReactiveFormsModule, MatCardModule, MatButtonModule, MatCheckboxModule, MatFormFieldModule, MatInputModule,
    PageHeader, StateView, StatusBadge],
  template: `
    <app-page-header title="Consent types" subtitle="Versioned consent definitions used during farmer onboarding" />
    <app-state-view [loading]="loading()" [error]="error()" (retry)="load()" />
    @if (!loading() && !error()) {
      <mat-card appearance="outlined"><mat-card-content>
        <div class="table-wrap">
          <table class="simple">
            <thead><tr><th>Type</th><th>Version</th><th>Title</th><th>Text version</th><th>Required for activation</th><th>Status</th><th></th></tr></thead>
            <tbody>
              @for (d of items(); track d.id) {
                <tr>
                  <td><code>{{ d.consent_type }}</code></td><td>v{{ d.version }}</td><td>{{ d.title }}</td><td>{{ d.text_version ?? '—' }}</td>
                  <td>{{ d.required_for_activation ? 'Yes' : 'No' }}</td>
                  <td><app-status-badge [status]="d.status === 'ACTIVE' ? 'ACTIVE' : 'REVOKED'" [text]="d.status" />
                    <div class="muted small">{{ d.created_at | date: 'mediumDate' }}</div></td>
                  <td>@if (d.status === 'ACTIVE') { <button mat-button type="button" (click)="retire(d)" [disabled]="busy()">Retire</button> }</td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      </mat-card-content></mat-card>
      <mat-card appearance="outlined" class="publish"><mat-card-content>
        <h3>Publish a consent type or a new version</h3>
        <form [formGroup]="form" (ngSubmit)="publish()" class="form">
          <mat-form-field subscriptSizing="dynamic"><mat-label>Type code</mat-label><input matInput formControlName="consent_type" placeholder="DATA_PROCESSING" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Title</mat-label><input matInput formControlName="title" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Text version</mat-label><input matInput formControlName="text_version" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Description</mat-label><input matInput formControlName="description" /></mat-form-field>
          <mat-checkbox formControlName="required_for_activation">Required for farmer activation</mat-checkbox>
          <button mat-flat-button type="submit" [disabled]="busy() || form.invalid">Publish</button>
        </form>
        <p class="muted small">Publishing a type that already exists creates the next version and retires the current one. Farmers activated
          afterwards must consent to the new version; existing grants are kept as history.</p>
      </mat-card-content></mat-card>
    }
  `,
  styles: `
    .publish { margin-top: 16px; } h3 { margin: 0 0 12px; font: var(--mat-sys-title-small); }
    .form { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; } .wide { min-width: 240px; flex: 1; }
    .table-wrap { overflow-x: auto; }
    table.simple { width: 100%; border-collapse: collapse; }
    table.simple th, table.simple td { text-align: left; padding: 8px; border-bottom: 1px solid var(--mat-sys-outline-variant); vertical-align: top; }
  `,
})
export class ConsentDefinitionsPage implements OnInit {
  private readonly api = inject(ConsentsApi);
  private readonly notify = inject(NotifyService);
  private readonly dialog = inject(MatDialog);
  protected readonly items = signal<ConsentDefinition[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<ApiError | null>(null);
  protected readonly busy = signal(false);
  protected readonly form = new FormGroup({
    consent_type: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.pattern(/^[A-Za-z][A-Za-z0-9_]{2,39}$/)] }),
    title: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.minLength(2)] }),
    text_version: new FormControl('', { nonNullable: true }),
    description: new FormControl('', { nonNullable: true }),
    required_for_activation: new FormControl(false, { nonNullable: true }),
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.error.set(null);
    this.api.all().subscribe({
      next: (d) => {
        this.items.set(d);
        this.loading.set(false);
      },
      error: (e: unknown) => {
        this.error.set(ApiError.from(e));
        this.loading.set(false);
      },
    });
  }

  publish(): void {
    const v = this.form.getRawValue();
    runAction(this.api.publish({ ...v, text_version: v.text_version.trim() || null, description: v.description.trim() || null }),
      this.busy, this.notify, 'Consent definition published.', () => {
        this.form.reset();
        this.load();
      });
  }

  retire(d: ConsentDefinition): void {
    askReason(this.dialog, { title: `Retire ${d.consent_type} v${d.version}?`, confirmLabel: 'Retire', danger: true,
      message: d.required_for_activation ? 'It will no longer be required for farmer activation.' : undefined }).subscribe((r) => {
      if (r) runAction(this.api.retire(d.id, r.reason), this.busy, this.notify, 'Consent definition retired.', () => this.load());
    });
  }
}
