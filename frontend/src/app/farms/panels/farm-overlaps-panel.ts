import { DatePipe, DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, input, output, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { RouterLink } from '@angular/router';

import { NotifyService } from '../../core/notify.service';
import { label } from '../../farmer/farmer.models';
import { askReason } from '../../shared/reason-dialog';
import { runAction } from '../../shared/run-action';
import { StatusBadge } from '../../shared/status-badge';
import { Farm, Overlap } from '../farm.models';
import { FarmsApi } from '../farms.api';

/** Overlap flags (spec §41): reviewed by a person, never auto-rejected. Other organizations' farms stay anonymous. */
@Component({
  selector: 'app-farm-overlaps-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, DecimalPipe, RouterLink, MatButtonModule, StatusBadge],
  template: `
    <div class="tab-body">
      @for (o of overlaps(); track o.id) {
        <div class="line">
          <div class="grow">
            <strong>{{ o.overlap_area_m2 | number: '1.0-0' }} m²</strong>
            ({{ o.overlap_pct_of_farm | number: '1.0-1' }}% of this farm, {{ o.overlap_pct_of_other | number: '1.0-1' }}% of the other) ·
            {{ label(o.relation) }}
            <div class="muted small">
              @if (o.other_farm_visible) { with <a [routerLink]="['/farms', o.other_farm_id]">{{ o.other_farm_code }}</a> }
              @else { with a farm in another organization (details restricted) }
              {{ o.same_farmer ? '· same farmer' : '' }} · detected {{ o.detected_at | date: 'medium' }}
            </div>
            @if (o.resolution_notes) { <div class="muted small">Resolution: {{ o.resolution_notes }}</div> }
          </div>
          <app-status-badge [status]="o.status === 'OPEN' ? 'WARNING' : o.status === 'CONFIRMED_CONFLICT' ? 'FAILED' : 'ACTIVE'" [text]="label(o.status)" />
          @if (farm().can_review && o.status === 'OPEN') {
            <button mat-button type="button" (click)="resolve(o, 'CONFIRMED_CONFLICT')" [disabled]="busy()">Confirm conflict</button>
            <button mat-stroked-button type="button" (click)="resolve(o, 'CLEARED')" [disabled]="busy()">Clear</button>
          }
        </div>
      } @empty { <p class="muted">No overlaps with other farm boundaries.</p> }
      <p class="muted small">Every saved boundary is compared with all current farm boundaries (all organizations). Open or confirmed overlaps
        block verification until a GIS reviewer resolves them.</p>
    </div>
  `,
  styles: `
    .line { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--mat-sys-outline-variant); flex-wrap: wrap; }
    .grow { flex: 1; min-width: 240px; }
  `,
})
export class FarmOverlapsPanel {
  readonly farm = input.required<Farm>();
  readonly overlaps = input<Overlap[]>([]);
  readonly changed = output<void>();
  private readonly api = inject(FarmsApi);
  private readonly notify = inject(NotifyService);
  private readonly dialog = inject(MatDialog);
  protected readonly busy = signal(false);
  protected readonly label = label;

  resolve(o: Overlap, resolution: 'CLEARED' | 'CONFIRMED_CONFLICT'): void {
    askReason(this.dialog, {
      title: resolution === 'CLEARED' ? 'Clear this overlap?' : 'Confirm this is a real conflict?',
      message: resolution === 'CLEARED' ? 'Explain why the overlap is acceptable (e.g. digitising tolerance, shared bund).'
        : 'The farm cannot be verified while a confirmed conflict exists; correct or reject the boundary.',
      confirmLabel: resolution === 'CLEARED' ? 'Clear' : 'Confirm conflict', danger: resolution === 'CONFIRMED_CONFLICT',
    }).subscribe((r) => {
      if (r) runAction(this.api.resolveOverlap(this.farm().id, o.id, resolution, r.reason), this.busy, this.notify, 'Overlap resolved.',
        () => this.changed.emit());
    });
  }
}
