import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { Router, RouterLink } from '@angular/router';

import { ApiError } from '../core/api/api.models';
import { AuthService } from '../core/auth/auth.service';
import { P } from '../core/auth/permissions';
import { NotifyService } from '../core/notify.service';
import { label } from '../farmer/farmer.models';
import { CatalogActivity, CatalogStandard } from '../projects/project.models';
import { CatalogApi } from '../projects/projects.api';
import { PageHeader } from '../shared/page-header';
import { runAction } from '../shared/run-action';
import { StateView } from '../shared/state-view';
import { StatusBadge } from '../shared/status-badge';
import { MethodologiesApi } from './methodologies.api';
import { Methodology, versionBadge } from './methodology.models';

/** Methodology catalog: standard → methodology → versions. Versions are drafted, reviewed and approved by different
 *  people; approved versions are never edited (a change is a new version). */
@Component({
  selector: 'app-methodologies-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, RouterLink, MatCardModule, MatButtonModule, MatFormFieldModule, MatInputModule, MatSelectModule,
    PageHeader, StateView, StatusBadge],
  template: `
    <app-page-header title="Methodologies" subtitle="Versioned, approval-controlled methodology configuration. Rules are taken from the authoritative source." />
    <app-state-view [loading]="loading()" [error]="error()" [empty]="!loading() && !error() && !items().length" emptyText="No methodologies yet." (retry)="load()" />
    @for (m of items(); track m.id) {
      <mat-card appearance="outlined" class="m">
        <mat-card-content>
          <div class="head">
            <div class="grow"><strong>{{ m.code }}</strong> — {{ m.name }}
              <div class="muted small">{{ m.standard_name }} · {{ activityNames(m) }}{{ m.owner_name ? ' · ' + m.owner_name : '' }}</div></div>
            @if (m.environment === 'DEMO') { <app-status-badge status="DEMO" /> }
            <app-status-badge [status]="m.status === 'ACTIVE' ? 'ACTIVE' : 'REVOKED'" [text]="label(m.status)" />
          </div>
          <table class="simple">
            <thead><tr><th>Version</th><th>Status</th><th>Effective</th><th>Rules</th><th>Calculation</th><th></th></tr></thead>
            <tbody>@for (v of m.versions; track v.id) {
              <tr><td>{{ v.version_label }}</td>
                <td><app-status-badge [status]="badge(v.status)" [text]="label(v.status)" /></td>
                <td>{{ v.effective_from ?? '—' }} → {{ v.effective_to ?? 'open' }}</td>
                <td>{{ v.rule_counts.applicability }} applicability · {{ v.rule_counts.monitoring }} monitoring · {{ v.rule_counts.calculation }} calculation</td>
                <td>{{ label(v.calculation_readiness) }}</td>
                <td><a [routerLink]="['/methodologies/versions', v.id]">Open</a></td></tr>
            }</tbody>
          </table>
          @if (canManage) {
            <div class="newv">
              <mat-form-field subscriptSizing="dynamic"><mat-label>New version label</mat-label><input matInput #lbl placeholder="2.2" /></mat-form-field>
              <button mat-button type="button" (click)="newVersion(m, lbl.value)" [disabled]="busy()">New draft version</button>
              <span class="muted small">copies the rules of the latest version, if any</span>
            </div>
          }
        </mat-card-content>
      </mat-card>
    }
    @if (canManage) {
      <mat-card appearance="outlined" class="m"><mat-card-content>
        <h3>Add a methodology</h3>
        <form [formGroup]="form" (ngSubmit)="create()" class="form">
          <mat-form-field subscriptSizing="dynamic"><mat-label>Code</mat-label><input matInput formControlName="code" placeholder="VM0042" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Name</mat-label><input matInput formControlName="name" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Standard / route</mat-label>
            <mat-select formControlName="standard_id">@for (s of standards(); track s.id) { <mat-option [value]="s.id">{{ s.name }}</mat-option> }</mat-select></mat-form-field>
          <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Activities</mat-label>
            <mat-select formControlName="activity_ids" multiple>@for (a of offered(); track a.id) { <mat-option [value]="a.id">{{ a.name }}</mat-option> }</mat-select></mat-form-field>
          <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Official source URL</mat-label><input matInput formControlName="source_url" /></mat-form-field>
          <button mat-flat-button type="submit" [disabled]="busy() || form.invalid">Add methodology</button>
        </form>
      </mat-card-content></mat-card>
    }
  `,
  styles: `
    .m { margin-bottom: 12px; } .head { display: flex; gap: 8px; align-items: center; } .grow { flex: 1; }
    table.simple { width: 100%; border-collapse: collapse; margin-top: 8px; }
    table.simple th, table.simple td { text-align: left; padding: 6px; border-bottom: 1px solid var(--mat-sys-outline-variant); }
    .newv { margin-top: 8px; display: flex; gap: 8px; align-items: center; } h3 { margin: 0 0 8px; font: var(--mat-sys-title-small); }
    .form { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; } .wide { min-width: 240px; flex: 1; }
  `,
})
export class MethodologiesPage implements OnInit {
  private readonly api = inject(MethodologiesApi);
  private readonly catalog = inject(CatalogApi);
  private readonly notify = inject(NotifyService);
  private readonly router = inject(Router);
  protected readonly canManage = inject(AuthService).has(P.METHODOLOGIES_MANAGE);
  protected readonly label = label;
  protected readonly badge = versionBadge;
  protected readonly items = signal<Methodology[]>([]);
  protected readonly standards = signal<CatalogStandard[]>([]);
  protected readonly activities = signal<CatalogActivity[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<ApiError | null>(null);
  protected readonly busy = signal(false);
  protected readonly selectedStandard = signal('');
  protected readonly offered = computed(() => this.activities().filter((a) => a.standard_ids.includes(this.selectedStandard())));
  protected readonly form = new FormGroup({
    code: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.pattern(/^[A-Za-z][A-Za-z0-9_.-]{1,39}$/)] }),
    name: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.minLength(2)] }),
    standard_id: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    activity_ids: new FormControl<string[]>([], { nonNullable: true, validators: [Validators.required] }),
    source_url: new FormControl('', { nonNullable: true, validators: [Validators.pattern(/^(https?:\/\/\S+)?$/)] }),
  });

  ngOnInit(): void {
    this.form.controls.standard_id.valueChanges.subscribe((v) => this.selectedStandard.set(v));
    this.load();
    if (this.canManage) {
      this.catalog.standards().subscribe((s) => this.standards.set(s));
      this.catalog.activities().subscribe((a) => this.activities.set(a));
    }
  }

  load(): void {
    this.error.set(null);
    this.api.list().subscribe({
      next: (m) => {
        this.items.set(m);
        this.loading.set(false);
      },
      error: (e: unknown) => {
        this.error.set(ApiError.from(e));
        this.loading.set(false);
      },
    });
    this.catalog.activities().subscribe({ next: (a) => this.activities.set(a), error: () => undefined });
  }

  activityNames(m: Methodology): string {
    return this.activities().filter((a) => m.activity_ids.includes(a.id)).map((a) => a.name).join(', ') || `${m.activity_ids.length} activities`;
  }

  create(): void {
    const v = this.form.getRawValue();
    const env = this.standards().find((s) => s.id === v.standard_id)?.environment ?? 'LIVE';
    runAction(this.api.create({ ...v, source_url: v.source_url.trim() || null, environment: env }), this.busy, this.notify, 'Methodology added.', () => {
      this.form.reset();
      this.load();
    });
  }

  newVersion(m: Methodology, label: string): void {
    label = label.trim();
    if (!label) return;
    const latest = m.versions[0];
    runAction(this.api.createVersion(m.id, { version_label: label, based_on_version_id: latest?.id ?? null }), this.busy, this.notify,
      'Draft version created.', (v) => void this.router.navigate(['/methodologies/versions', v.id]));
  }
}
