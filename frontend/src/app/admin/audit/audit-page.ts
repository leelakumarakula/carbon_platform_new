import { DatePipe, JsonPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatPaginatorModule } from '@angular/material/paginator';
import { ActivatedRoute } from '@angular/router';
import { debounceTime } from 'rxjs';

import { PageHeader } from '../../shared/page-header';
import { PagedList } from '../../shared/paged-list';
import { StateView } from '../../shared/state-view';
import { AuditApi } from '../admin.api';
import { AuditLog } from '../admin.models';

/** Entity types the backend audits (audit.record / record_transition callers, state machines, document owners). Free text is
 *  still accepted, so a type added on the server can be filtered before this list is updated. */
const ENTITY_TYPES = [
  'activity', 'background_job', 'buyer_profile', 'calculation_finding', 'calculation_readiness', 'calculation_report', 'calculation_run',
  'consent_definition', 'corrective_action', 'credit_batch', 'credit_issuance', 'credit_opening', 'credit_reservation',
  'credit_retirement', 'credit_reversal', 'credit_transfer', 'demo', 'document', 'farm', 'farm_allocation_version', 'farm_overlap_check',
  'farmer', 'farmer_agreement', 'farmer_bank_account', 'field_collection', 'lab', 'lab_engagement', 'lab_result', 'lab_sample',
  'lab_shipment', 'lab_test', 'marketplace_listing', 'methodology', 'methodology_version', 'monitoring_period', 'mrv', 'mrv_dataset',
  'mrv_plan', 'order', 'order_item', 'organization', 'payment', 'payment_event', 'payout', 'payout_adjustment', 'project',
  'project_carbon_right', 'project_cost', 'reference_data', 'refund', 'registry_account', 'registry_registration', 'registry_submission',
  'retention_policy', 'revenue_record', 'revenue_share_version', 'role', 'session', 'settlement_run', 'sharing_config', 'standard',
  'storage_object', 'user', 'verification_assignment', 'verification_decision', 'verification_finding', 'verification_submission',
];

/** Append-only audit trail (spec section 35). Read-only by design: there is no edit or delete. */
@Component({
  selector: 'app-audit-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, DatePipe, JsonPipe, MatFormFieldModule, MatInputModule, MatAutocompleteModule, MatButtonModule, MatIconModule,
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

  protected readonly expanded = signal<Set<number>>(new Set());

  protected readonly filters = new FormGroup({
    entity_type: new FormControl('', { nonNullable: true }),
    entity_id: new FormControl('', { nonNullable: true }),
    action: new FormControl('', { nonNullable: true }),
    from: new FormControl('', { nonNullable: true }),
    to: new FormControl('', { nonNullable: true }),
  });
  private readonly entityQuery = toSignal(this.filters.controls.entity_type.valueChanges, { initialValue: '' });
  protected readonly entityTypes = computed(() => {
    const q = this.entityQuery().trim().toLowerCase();
    return ENTITY_TYPES.filter((t) => t.includes(q));
  });

  protected readonly list = new PagedList<AuditLog>((q) => {
    const f = this.filters.getRawValue();
    return this.api.auditLogs({
      ...q,
      entity_type: f.entity_type.trim().toLowerCase() || null,
      entity_id: f.entity_id.trim() || null,
      action: f.action.trim().toUpperCase() || null,
      from: f.from ? new Date(f.from).toISOString() : null,
      to: f.to ? new Date(f.to).toISOString() : null,
    });
  }, this.destroyRef, '-occurred_at');

  ngOnInit(): void {
    const qp = this.route.snapshot.queryParamMap;
    this.filters.patchValue({ entity_type: qp.get('entity_type') ?? '', entity_id: qp.get('entity_id') ?? '' }, { emitEvent: false });
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
    this.filters.reset({ entity_type: '', entity_id: '', action: '', from: '', to: '' });
  }
}
