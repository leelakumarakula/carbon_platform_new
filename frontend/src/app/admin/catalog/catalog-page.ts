import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';

import { ApiError } from '../../core/api/api.models';
import { NotifyService } from '../../core/notify.service';
import { label } from '../../farmer/farmer.models';
import { CatalogActivity, CatalogStandard } from '../../projects/project.models';
import { CatalogApi } from '../../projects/projects.api';
import { PageHeader } from '../../shared/page-header';
import { runAction } from '../../shared/run-action';
import { StateView } from '../../shared/state-view';
import { StatusBadge } from '../../shared/status-badge';

/** Standard / route and activity catalog (reference data). No methodology rules live here — record entries from
 *  the official source and link each activity to the standards that offer it. */
@Component({
  selector: 'app-catalog-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, MatCardModule, MatButtonModule, MatFormFieldModule, MatInputModule, MatSelectModule, PageHeader, StateView,
    StatusBadge],
  template: `
    <app-page-header title="Standards & activities" subtitle="Reference catalog used by projects. Methodologies are managed separately." />
    <app-state-view [loading]="loading()" [error]="error()" (retry)="load()" />
    @if (!loading() && !error()) {
      <div class="cols">
        <mat-card appearance="outlined"><mat-card-content>
          <h3>Standards / crediting routes</h3>
          @for (s of standards(); track s.id) {
            <div class="line">
              <div class="grow"><strong>{{ s.name }}</strong> <span class="muted small">{{ s.code }} · {{ label(s.program_type) }}{{ s.owner_name ? ' · ' + s.owner_name : '' }}</span>
                @if (s.source_url) { <div class="small"><a [href]="s.source_url" target="_blank" rel="noopener noreferrer">Official source</a></div> }
                <div class="muted small">{{ s.activity_ids.length }} activit{{ s.activity_ids.length === 1 ? 'y' : 'ies' }}</div></div>
              @if (s.environment === 'DEMO') { <app-status-badge status="DEMO" /> }
              <app-status-badge [status]="s.status === 'ACTIVE' ? 'ACTIVE' : 'REVOKED'" [text]="label(s.status)" />
              <button mat-button type="button" (click)="toggleStandard(s)" [disabled]="busy()">{{ s.status === 'ACTIVE' ? 'Deactivate' : 'Activate' }}</button>
            </div>
          } @empty { <p class="muted">No standards yet.</p> }
          <form [formGroup]="std" (ngSubmit)="addStandard()" class="form">
            <mat-form-field subscriptSizing="dynamic"><mat-label>Code</mat-label><input matInput formControlName="code" /></mat-form-field>
            <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Name</mat-label><input matInput formControlName="name" /></mat-form-field>
            <mat-form-field subscriptSizing="dynamic"><mat-label>Programme owner</mat-label><input matInput formControlName="owner_name" /></mat-form-field>
            <mat-form-field subscriptSizing="dynamic"><mat-label>Type</mat-label>
              <mat-select formControlName="program_type">@for (t of ['VOLUNTARY', 'COMPLIANCE', 'OTHER']; track t) { <mat-option [value]="t">{{ label(t) }}</mat-option> }</mat-select>
            </mat-form-field>
            <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Official source URL</mat-label><input matInput formControlName="source_url" /></mat-form-field>
            <button mat-flat-button type="submit" [disabled]="busy() || std.invalid">Add standard</button>
          </form>
        </mat-card-content></mat-card>
        <mat-card appearance="outlined"><mat-card-content>
          <h3>Activities</h3>
          @for (a of activities(); track a.id) {
            <div class="line">
              <div class="grow"><strong>{{ a.name }}</strong> <span class="muted small">{{ a.code }}</span>
                <div class="muted small">Offered under: {{ standardNames(a) || '—' }}</div></div>
              @if (a.environment === 'DEMO') { <app-status-badge status="DEMO" /> }
              <app-status-badge [status]="a.status === 'ACTIVE' ? 'ACTIVE' : 'REVOKED'" [text]="label(a.status)" />
            </div>
          } @empty { <p class="muted">No activities yet.</p> }
          <form [formGroup]="act" (ngSubmit)="addActivity()" class="form">
            <mat-form-field subscriptSizing="dynamic"><mat-label>Code</mat-label><input matInput formControlName="code" /></mat-form-field>
            <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Name</mat-label><input matInput formControlName="name" /></mat-form-field>
            <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Offered under</mat-label>
              <mat-select formControlName="standard_ids" multiple>@for (s of liveStandards(); track s.id) { <mat-option [value]="s.id">{{ s.name }}</mat-option> }</mat-select>
            </mat-form-field>
            <button mat-flat-button type="submit" [disabled]="busy() || act.invalid">Add activity</button>
          </form>
        </mat-card-content></mat-card>
      </div>
    }
  `,
  styles: `
    .cols { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; } @media (max-width: 1000px) { .cols { grid-template-columns: 1fr; } }
    h3 { margin: 0 0 8px; font: var(--mat-sys-title-small); }
    .line { display: flex; align-items: center; gap: 8px; padding: 8px 0; border-bottom: 1px solid var(--mat-sys-outline-variant); flex-wrap: wrap; }
    .grow { flex: 1; min-width: 220px; } .form { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 12px; }
    .wide { min-width: 220px; flex: 1; }
  `,
})
export class CatalogPage implements OnInit {
  private readonly api = inject(CatalogApi);
  private readonly notify = inject(NotifyService);
  protected readonly label = label;
  protected readonly standards = signal<CatalogStandard[]>([]);
  protected readonly activities = signal<CatalogActivity[]>([]);
  protected readonly loading = signal(true);
  protected readonly error = signal<ApiError | null>(null);
  protected readonly busy = signal(false);
  protected readonly liveStandards = computed(() => this.standards().filter((s) => s.environment === 'LIVE'));
  protected readonly std = new FormGroup({
    code: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.pattern(/^[A-Za-z][A-Za-z0-9_-]{1,39}$/)] }),
    name: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.minLength(2)] }),
    owner_name: new FormControl('', { nonNullable: true }),
    program_type: new FormControl('VOLUNTARY', { nonNullable: true }),
    source_url: new FormControl('', { nonNullable: true, validators: [Validators.pattern(/^(https?:\/\/\S+)?$/)] }),
  });
  protected readonly act = new FormGroup({
    code: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.pattern(/^[A-Za-z][A-Za-z0-9_-]{1,39}$/)] }),
    name: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.minLength(2)] }),
    standard_ids: new FormControl<string[]>([], { nonNullable: true }),
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.error.set(null);
    this.api.standards().subscribe({
      next: (s) => {
        this.standards.set(s);
        this.api.activities().subscribe((a) => {
          this.activities.set(a);
          this.loading.set(false);
        });
      },
      error: (e: unknown) => {
        this.error.set(ApiError.from(e));
        this.loading.set(false);
      },
    });
  }

  standardNames(a: CatalogActivity): string {
    return this.standards().filter((s) => a.standard_ids.includes(s.id)).map((s) => s.name).join(', ');
  }

  addStandard(): void {
    const v = this.std.getRawValue();
    runAction(this.api.createStandard({ ...v, owner_name: v.owner_name.trim() || null, source_url: v.source_url.trim() || null }), this.busy,
      this.notify, 'Standard added.', () => {
        this.std.reset({ program_type: 'VOLUNTARY' });
        this.load();
      });
  }

  addActivity(): void {
    runAction(this.api.createActivity(this.act.getRawValue()), this.busy, this.notify, 'Activity added.', () => {
      this.act.reset();
      this.load();
    });
  }

  toggleStandard(s: CatalogStandard): void {
    runAction(this.api.updateStandard(s.id, { status: s.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE' }), this.busy, this.notify, 'Standard updated.',
      () => this.load());
  }
}
