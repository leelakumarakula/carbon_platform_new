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
 * A record can be split into depth increments (e.g. 0–30 and 30–50 cm for VM0042): each sample's depth must lie within the
 * record's actual depth (checked by the server); after a registration the form proposes the next increment.
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
          <span class="small muted" data-testid="sample-depth"> · {{ depthText(s.depth_top_cm) }}–{{ depthText(s.depth_bottom_cm) }} cm</span>
          <span class="small muted"> · {{ s.laboratory_org_name }} · {{ s.test_count }} test(s){{ s.seal_number ? ' · seal ' + s.seal_number : '' }}</span></div>
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
              <input matInput type="number" min="0" step="0.1" [(ngModel)]="depthTop" data-testid="sample-depth-top" /></mat-form-field>
            <mat-form-field subscriptSizing="dynamic"><mat-label>Depth bottom (cm)</mat-label>
              <input matInput type="number" min="0" step="0.1" [(ngModel)]="depthBottom" data-testid="sample-depth-bottom" /></mat-form-field>
          </div>
          <p class="small muted">
            @if (recordDepth(); as d) { Field record depth {{ d }} cm. }
            To split the core into layers (e.g. 0–30 and 30–50 cm), register one sample per layer. The sample code is issued on registration;
            write it on the container before sealing.</p>
          @if (depthProblem(); as problem) { <p class="small warn" data-testid="depth-problem">{{ problem }}</p> }
          <button mat-flat-button type="button" [disabled]="busy() || description.trim().length < 2 || !!depthProblem()" (click)="register()"
                  data-testid="register-sample">Register sample</button>
        </div>
      </details>
    } @else if (!ready()) {
      <p class="small muted">A sample can be registered once this record is submitted.</p>
    }
  `,
  styles: `h3 { margin: 16px 0 8px; font: var(--mat-sys-title-small); } .mono { font-family: monospace; }
    .sample { padding: 6px 0; border-bottom: 1px solid var(--mat-sys-outline-variant); max-width: 640px; }
    .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; } .row button { min-height: 44px; }
    .stack { display: flex; flex-direction: column; gap: 8px; max-width: 640px; margin-top: 8px; } .register { margin: 8px 0 16px; }
    .warn { color: var(--mat-sys-error); }`,
})
export class CollectionSamples implements OnInit {
  readonly collectionId = input.required<string>();
  readonly collectionStatus = input.required<string>();
  /** The field record's actual depth; the sample depth defaults to it and must lie within it. */
  readonly recordDepthTop = input<string | null>(null);
  readonly recordDepthBottom = input<string | null>(null);
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
  protected depthTop: number | null = null;
  protected depthBottom: number | null = null;
  protected readonly recordDepth = computed(() => {
    const top = this.recordDepthTop(), bottom = this.recordDepthBottom();
    return top !== null && bottom !== null ? `${this.depthText(top)}–${this.depthText(bottom)}` : null;
  });

  ngOnInit(): void {
    this.depthTop = this.num(this.recordDepthTop());
    this.depthBottom = this.num(this.recordDepthBottom());
    this.load();
  }

  load(): void {
    this.api.samples({ field_collection_id: this.collectionId() }).subscribe((s) => this.samples.set(s));
  }

  /** Client-side hint only; the server enforces the same rule (INVALID_DEPTH). */
  protected depthProblem(): string | null {
    const top = this.depthTop, bottom = this.depthBottom;
    if (top === null && bottom === null) return null;                  // both empty: the server uses the record's depth
    if (top === null || bottom === null) return 'Enter both depths, or leave both empty to use the field record depth.';
    if (top < 0 || bottom <= top) return 'Depth bottom must be greater than depth top.';
    const rTop = this.num(this.recordDepthTop()), rBottom = this.num(this.recordDepthBottom());
    if (rTop !== null && rBottom !== null && (top < rTop || bottom > rBottom)) {
      return `The sample depth must lie within the field record depth (${this.recordDepth()} cm).`;
    }
    return null;
  }

  protected register(): void {
    const top = this.depthTop, bottom = this.depthBottom;
    const body = { field_collection_id: this.collectionId(), description: this.description.trim(), quantity: this.quantity,
      quantity_unit: this.quantity === null ? null : this.quantityUnit.trim() || null, container_label: this.containerLabel.trim() || null,
      depth_top_cm: top, depth_bottom_cm: bottom };
    runAction(this.api.register(body), this.busy, this.notify, 'Sample registered — label the container and seal it.', () => {
      const rBottom = this.num(this.recordDepthBottom());
      if (bottom !== null && rBottom !== null && bottom < rBottom) {        // propose the next increment of the same core
        this.depthTop = bottom;
        this.depthBottom = rBottom;
      }
      this.containerLabel = '';
      this.load();
    });
  }

  protected depthText(v: string | number): string {
    return String(Number(v));
  }

  private num(v: string | null): number | null {
    return v === null || v === '' ? null : Number(v);
  }

  protected seal(s: Sample): void {
    runAction(this.api.seal(s.id, this.sealNo[s.id].trim()), this.busy, this.notify, `${s.sample_code} sealed.`, () => this.load());
  }
}
