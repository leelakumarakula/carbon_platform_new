import { JsonPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';

import { label } from '../farmer/farmer.models';
import { PageHeader } from '../shared/page-header';
import { StatusBadge } from '../shared/status-badge';
import { CreditsApi } from './registry.api';
import { Batch, BatchLineage, ISSUED_LABEL, issuanceBadge, serialText } from './registry.models';

/** Registry-issued credit batches — read-only. No available inventory, reservation, transfer or retirement exists in Phase 9A. */
@Component({
  selector: 'app-credits-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [JsonPipe, MatButtonModule, PageHeader, StatusBadge],
  template: `
    <app-page-header title="Issued credits" subtitle="Registry-issued credit batches as stated by the registry (read-only)" />
    <p class="note">{{ issuedLabel }}: quantities, vintages and serial numbers come from the registry's issuance statements and were confirmed by a
      second person. This is not available inventory; there is no transfer or retirement here.</p>
    <div class="table-wrap"><table class="table" data-testid="credit-batches">
      <thead><tr><th>Batch</th><th>Project · period</th><th>Registry</th><th>Vintage</th><th>Credits</th><th>Serial numbers (as supplied)</th><th>Status</th><th></th></tr></thead>
      <tbody>
        @for (b of rows(); track b.id) {
          <tr [attr.data-batch]="b.batch_code">
            <td>{{ b.batch_code }}<div class="small muted">{{ b.issuance_code }} · registry {{ b.external_issuance_id }}</div></td>
            <td>{{ b.project_code }} · #{{ b.period_number }}</td><td>{{ b.registry_name }}</td><td>{{ b.vintage }}</td>
            <td>{{ b.quantity }} {{ b.unit }}</td>
            <td>@for (r of b.serial_ranges; track r.seq) { <div class="mono">{{ serial(r) }}</div> }</td>
            <td><app-status-badge [status]="badge(b.status)" [text]="label(b.status)" />
              @if (b.source_superseded) { <app-status-badge status="WARNING" text="Source superseded" /> }
              @if (b.environment === 'DEMO') { <app-status-badge status="DEMO" text="DEMO" /> }</td>
            <td><button mat-button type="button" (click)="showLineage(b)">Lineage</button></td>
          </tr>
        } @empty { <tr><td colspan="8" class="muted" data-testid="no-credits">No registry-issued credit batch.</td></tr> }
      </tbody>
    </table></div>
    @if (lineage(); as l) { <pre class="mono" data-testid="batch-lineage">{{ l.chain | json }}</pre> }
  `,
  styles: `.mono { font-family: monospace; font-size: 11px; word-break: break-all; } pre { max-height: 360px; overflow: auto; white-space: pre-wrap; }`,
})
export class CreditsPage implements OnInit {
  private readonly api = inject(CreditsApi);
  protected readonly label = label;
  protected readonly badge = issuanceBadge;
  protected readonly serial = serialText;
  protected readonly issuedLabel = ISSUED_LABEL;
  protected readonly rows = signal<Batch[]>([]);
  protected readonly lineage = signal<BatchLineage | null>(null);

  ngOnInit(): void {
    this.api.batches().subscribe((b) => this.rows.set(b));
  }

  protected showLineage(b: Batch): void {
    this.api.lineage(b.id).subscribe((l) => this.lineage.set(l));
  }
}
