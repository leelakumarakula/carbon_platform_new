import { ChangeDetectionStrategy, Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';

import { AuthService } from '../core/auth/auth.service';
import { P } from '../core/auth/permissions';
import { NotifyService } from '../core/notify.service';
import { label } from '../farmer/farmer.models';
import { runAction } from '../shared/run-action';
import { StatusBadge } from '../shared/status-badge';
import { LabApi } from './lab.api';
import { Sample, labBadge } from './lab.models';

/**
 * "Register & seal sample" on the field collection screen. Only a SUBMITTED or ACCEPTED record can carry a sample;
 * laboratory tests are created automatically from the engaged methodology rules (nothing is entered here).
 */
@Component({
  selector: 'app-collection-samples',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, MatButtonModule, MatFormFieldModule, MatInputModule, StatusBadge],
  template: `
    <h3>Laboratory samples ({{ samples().length }})</h3>
    @for (s of samples(); track s.id) {
      <div class="sample">
        <div><strong class="mono">{{ s.sample_code }}</strong> <app-status-badge [status]="badge(s.status)" [text]="label(s.status)" />
          <span class="small muted" [attr.data-testid]="'sample-depth-' + s.sample_code"> · {{ +s.depth_top_cm }}–{{ +s.depth_bottom_cm }} cm · {{ s.laboratory_org_name }}
            · {{ s.test_count }} test(s){{ s.seal_number ? ' · seal ' + s.seal_number : '' }}</span></div>
        @if (s.can_seal) {
          <p class="small">Write <strong class="mono">{{ s.sample_code }}</strong> on the container, then seal it.</p>
          <div class="row">
            <mat-form-field subscriptSizing="dynamic"><mat-label>Seal number</mat-label>
              <input matInput [(ngModel)]="sealNo[s.id]" [attr.data-testid]="'seal-' + s.sample_code" /></mat-form-field>
            <button mat-flat-button type="button" [disabled]="busy() || !sealNo[s.id]?.trim()" (click)="seal(s)" data-testid="seal-sample">Seal sample</button>
          </div>
        }
      </div>
    }
    @if (canRegister()) {
      <details class="register" [open]="!samples().length"><summary class="small">Register &amp; seal sample</summary>
        <div class="stack">
          <mat-form-field subscriptSizing="dynamic"><mat-label>Description</mat-label>
            <input matInput [(ngModel)]="description" data-testid="sample-description" /></mat-form-field>
          <div class="row">
            <mat-form-field subscriptSizing="dynamic"><mat-label>Quantity</mat-label><input matInput type="number" [(ngModel)]="quantity" /></mat-form-field>
            <mat-form-field subscriptSizing="dynamic"><mat-label>Unit</mat-label><input matInput [(ngModel)]="quantityUnit" /></mat-form-field>
            <mat-form-field subscriptSizing="dynamic"><mat-label>Container label</mat-label><input matInput [(ngModel)]="containerLabel" /></mat-form-field>
          </div>
          <div class="row">
            <mat-form-field subscriptSizing="dynamic"><mat-label>Depth top (cm)</mat-label>
              <input matInput type="number" min="0" [(ngModel)]="depthTop" data-testid="sample-depth-top" /></mat-form-field>
            <mat-form-field subscriptSizing="dynamic"><mat-label>Depth bottom (cm)</mat-label>
              <input matInput type="number" min="0" [(ngModel)]="depthBottom" data-testid="sample-depth-bottom" /></mat-form-field>
          </div>
          <p class="small muted">Leave the depth empty to use the field record's whole depth. For a depth increment (e.g. 0–30 and 30–50 cm, as VM0042
            requires) register one sample per increment. The sample code is issued on registration; write it on the container before sealing.</p>
          @if (depthError()) { <p class="small error">{{ depthError() }}</p> }
          <button mat-flat-button type="button" [disabled]="busy() || description.trim().length < 2 || !!depthError()" (click)="register()"
            data-testid="register-sample">
            Register sample</button>
        </div>
      </details>
    } @else if (!ready()) {
      <p class="small muted">A sample can be registered once this record is submitted.</p>
    }
  `,
  styles: `h3 { margin: 16px 0 8px; font: var(--mat-sys-title-small); } .mono { font-family: monospace; }
    .sample { padding: 6px 0; border-bottom: 1px solid var(--mat-sys-outline-variant); max-width: 640px; }
    .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; } .row button { min-height: 44px; }
    .stack { display: flex; flex-direction: column; gap: 8px; max-width: 640px; margin-top: 8px; } .register { margin: 8px 0 16px; } .error { color: var(--mat-sys-error); }`,
})
export class CollectionSamples implements OnInit {
  readonly collectionId = input.required<string>();
  readonly collectionStatus = input.required<string>();
  private readonly api = inject(LabApi);
  private readonly notify = inject(NotifyService);
  private readonly auth = inject(AuthService);
  protected readonly label = label;
  protected readonly badge = labBadge;
  protected readonly samples = signal<Sample[]>([]);
  protected readonly busy = signal(false);
  protected readonly ready = computed(() => ['SUBMITTED', 'ACCEPTED'].includes(this.collectionStatus()));
  protected readonly canRegister = computed(() => this.ready() && this.auth.has(P.LAB_SAMPLE_REGISTER));
  protected sealNo: Record<string, string> = {};
  protected description = 'Composite soil core';
  protected quantity: number | null = null;
  protected quantityUnit = 'g';
  protected containerLabel = '';
  protected readonly depthTopS = signal<number | null>(null);
  protected readonly depthBottomS = signal<number | null>(null);
  protected get depthTop(): number | null { return this.depthTopS(); }
  protected set depthTop(v: number | null) { this.depthTopS.set(v === null || (v as unknown) === '' ? null : Number(v)); }
  protected get depthBottom(): number | null { return this.depthBottomS(); }
  protected set depthBottom(v: number | null) { this.depthBottomS.set(v === null || (v as unknown) === '' ? null : Number(v)); }
  protected readonly depthError = computed(() => {
    const t = this.depthTopS(), b = this.depthBottomS();
    if ((t === null) !== (b === null)) return 'Enter both depth top and depth bottom, or neither.';
    if (t !== null && b !== null && (t < 0 || b <= t)) return 'Depth bottom must be greater than depth top.';
    return '';
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.api.samples({ field_collection_id: this.collectionId() }).subscribe((s) => this.samples.set(s));
  }

  protected register(): void {
    const body = { field_collection_id: this.collectionId(), description: this.description.trim(), quantity: this.quantity,
      quantity_unit: this.quantity === null ? null : this.quantityUnit.trim() || null, container_label: this.containerLabel.trim() || null,
      ...(this.depthTopS() !== null ? { depth_top_cm: this.depthTopS(), depth_bottom_cm: this.depthBottomS() } : {}) };
    runAction(this.api.register(body), this.busy, this.notify, 'Sample registered — label the container and seal it.', () => {
      this.depthTopS.set(null);
      this.depthBottomS.set(null);
      this.load();
    });
  }

  protected seal(s: Sample): void {
    runAction(this.api.seal(s.id, this.sealNo[s.id].trim()), this.busy, this.notify, `${s.sample_code} sealed.`, () => this.load());
  }
}
