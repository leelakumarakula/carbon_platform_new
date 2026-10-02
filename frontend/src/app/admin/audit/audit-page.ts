import { DatePipe, JsonPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatPaginatorModule } from '@angular/material/paginator';
import { MatSelectModule } from '@angular/material/select';
import { ActivatedRoute } from '@angular/router';
import { debounceTime } from 'rxjs';

import { PageHeader } from '../../shared/page-header';
import { PagedList } from '../../shared/paged-list';
import { StateView } from '../../shared/state-view';
import { AuditApi } from '../admin.api';
import { AuditLog } from '../admin.models';

const ENTITY_TYPES = ['user', 'organization', 'role', 'session', 'reference_data', 'demo'];

/** Append-only audit trail (spec section 35). Read-only by design: there is no edit or delete. */
@Component({
  selector: 'app-audit-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, DatePipe, JsonPipe, MatFormFieldModule, MatInputModule, MatSelectModule, MatButtonModule, MatIconModule,
    MatPaginatorModule, PageHeader, StateView],
  templateUrl: './audit-page.html',
  styles: `
    .entry { border: 1px solid var(--mat-sys-outline-variant); border-radius: 8px; margin-bottom: 8px; background: var(--mat-sys-surface); }
    .entry-head { display: grid; grid-template-columns: 170px 1fr auto; gap: 12px; align-items: center; padding: 10px 14px; cursor: pointer; }
    .entry-head:hover { background: var(--mat-sys-surface-container-low); }
    .action { font-family: ui-monospace, Consolas, monospace; font-weight: 600; }
    .when, .who { color: var(--mat-sys-on-surface-variant); font-size: 13px; }
    .diff { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; padding: 0 14px 14px; }
    @media (max-width: 700px) { .diff, .entry-head { grid-template-columns: 1fr; } }
    pre { margin: 0; padding: 10px; border-radius: 6px; background: var(--mat-sys-surface-container); font-size: 12px; overflow: auto; max-height: 260px; }
    .label { font-size: 12px; font-weight: 600; margin-bottom: 4px; }
    .meta { padding: 0 14px 12px; font-size: 12px; color: var(--mat-sys-on-surface-variant); }
  `,
})
export class AuditPage implements OnInit {
  private readonly api = inject(AuditApi);
  private readonly destroyRef = inject(DestroyRef);
  private readonly route = inject(ActivatedRoute);

  protected readonly entityTypes = ENTITY_TYPES;
  protected readonly expanded = signal<Set<number>>(new Set());

  protected readonly filters = new FormGroup({
    entity_type: new FormControl<string | null>(null),
    entity_id: new FormControl('', { nonNullable: true }),
    action: new FormControl('', { nonNullable: true }),
    from: new FormControl('', { nonNullable: true }),
    to: new FormControl('', { nonNullable: true }),
  });

  protected readonly list = new PagedList<AuditLog>((q) => {
    const f = this.filters.getRawValue();
    return this.api.auditLogs({
      ...q,
      entity_type: f.entity_type,
      entity_id: f.entity_id.trim() || null,
      action: f.action.trim().toUpperCase() || null,
      from: f.from ? new Date(f.from).toISOString() : null,
      to: f.to ? new Date(f.to).toISOString() : null,
    });
  }, this.destroyRef, '-occurred_at');

  ngOnInit(): void {
    const qp = this.route.snapshot.queryParamMap;
    this.filters.patchValue({ entity_type: qp.get('entity_type'), entity_id: qp.get('entity_id') ?? '' }, { emitEvent: false });
    this.filters.valueChanges.pipe(debounceTime(350), takeUntilDestroyed(this.destroyRef)).subscribe(() => this.list.reset());
    this.list.load();
  }

  toggle(id: number): void {
    const next = new Set(this.expanded());
    if (next.has(id)) next.delete(id);
    else next.add(id);
    this.expanded.set(next);
  }

  clear(): void {
    this.filters.reset({ entity_type: null, entity_id: '', action: '', from: '', to: '' });
  }
}
