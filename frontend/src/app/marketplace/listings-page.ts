import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';

import { AuthService } from '../core/auth/auth.service';
import { P } from '../core/auth/permissions';
import { NotifyService } from '../core/notify.service';
import { LedgerApi } from '../ledger/ledger.api';
import { InventoryBatch } from '../ledger/ledger.models';
import { PageHeader } from '../shared/page-header';
import { askReason } from '../shared/reason-dialog';
import { runAction } from '../shared/run-action';
import { StatusBadge } from '../shared/status-badge';
import { MarketplaceApi } from './marketplace.api';
import { Listing, Listings, marketBadge, money, mlabel, newKey } from './marketplace.models';

interface Owner { batch: InventoryBatch; owner_id: string; owner_name: string | null; available: number }

/** Seller side: list AVAILABLE ledger credits of one batch at a fixed price (no reservation until a buyer orders), submit, approve (a
 *  different person — price and disclosure freeze), pause / resume, close. A price change means closing and listing again. */
@Component({
  selector: 'app-listings-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, FormsModule, MatButtonModule, MatFormFieldModule, MatInputModule, MatSelectModule, PageHeader, StatusBadge],
  template: `
    <app-page-header title="Listings" subtitle="Your organization's offers of registry-issued credits" />
    @if (canCreate) {
      <section class="box" data-testid="listing-form">
        <h3>New listing</h3>
        <div class="row">
          <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Credits (batch · owner · available)</mat-label>
            <mat-select [(ngModel)]="source" (ngModelChange)="loadRanges()">@for (o of owners(); track o.batch.batch_id + o.owner_id) {
              <mat-option [value]="o">{{ o.batch.batch_code }} · {{ o.batch.vintage }} · {{ o.owner_name }} · {{ o.available }} available</mat-option>
            }</mat-select></mat-form-field>
          <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Registry range (optional)</mat-label>
            <mat-select [(ngModel)]="f.range"><mat-option value="">Any range of the batch</mat-option>@for (r of ranges(); track r.id) {
              <mat-option [value]="r.id">{{ r.text }}</mat-option> }</mat-select></mat-form-field>
        </div>
        <div class="row">
          <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Title</mat-label><input matInput [(ngModel)]="f.title" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Listed quantity (credits)</mat-label><input matInput type="number" min="1" step="1" [(ngModel)]="f.qty" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Price per credit</mat-label><input matInput [(ngModel)]="f.price" placeholder="12.50" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Currency (ISO 4217)</mat-label><input matInput maxlength="3" [(ngModel)]="f.currency" /></mat-form-field>
        </div>
        <div class="row">
          <mat-form-field subscriptSizing="dynamic"><mat-label>Min order (optional)</mat-label><input matInput type="number" min="1" [(ngModel)]="f.min" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Max order (optional)</mat-label><input matInput type="number" min="1" [(ngModel)]="f.max" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Payment window (hours)</mat-label><input matInput type="number" min="1" max="720" [(ngModel)]="f.window" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Valid until (optional)</mat-label><input matInput type="datetime-local" [(ngModel)]="f.until" /></mat-form-field>
        </div>
        <mat-form-field subscriptSizing="dynamic" class="full"><mat-label>Co-benefits (your statement, optional)</mat-label><input matInput [(ngModel)]="f.cob" /></mat-form-field>
        <button mat-flat-button type="button" [disabled]="busy() || !valid()" (click)="create()">Create draft</button>
        <p class="small muted">Nothing is reserved by a listing: credits are reserved only when a buyer orders.</p>
      </section>
    }
    @if (data(); as d) {
      @if (d.demo_note) { <p class="note demo"><app-status-badge status="DEMO" text="DEMO" /> {{ d.demo_note }}</p> }
      <div class="table-wrap"><table class="table" data-testid="seller-listings">
        <thead><tr><th>Listing</th><th>Batch</th><th>Price</th><th>Listed · remaining · available</th><th>Status</th><th></th></tr></thead>
        <tbody>
          @for (l of d.listings; track l.id) {
            <tr [attr.data-listing]="l.listing_code">
              <td>{{ l.listing_code }}<div class="small">{{ l.title }}</div></td><td>{{ l.batch_code }}</td><td>{{ money(l.unit_price, l.currency) }}</td>
              <td>{{ l.listed_quantity }} · {{ l.remaining_quantity }} · {{ l.available_quantity }}</td>
              <td><app-status-badge [status]="badge(l.status)" [text]="label(l.status)" />
                @if (l.approved_by_name) { <div class="small muted">approved by {{ l.approved_by_name }} {{ l.approved_at | date: 'mediumDate' }}</div> }</td>
              <td>
                @if (l.can_manage && l.status === 'DRAFT') {
                  <input type="file" accept="application/pdf" (change)="pick(l, $event)" />
                  <button mat-button type="button" (click)="act(l, 'submit')">Submit</button> }
                @if (l.can_approve && l.status === 'PENDING_APPROVAL') { <button mat-flat-button type="button" (click)="act(l, 'approve')">Approve</button> }
                @if (l.can_manage && l.status === 'ACTIVE') { <button mat-button type="button" (click)="act(l, 'pause')">Pause</button> }
                @if (l.can_manage && l.status === 'PAUSED') { <button mat-button type="button" (click)="act(l, 'resume')">Resume</button> }
                @if ((l.can_manage || l.can_approve) && ['DRAFT', 'PENDING_APPROVAL', 'ACTIVE', 'PAUSED'].includes(l.status)) {
                  <button mat-button type="button" (click)="close(l)">Close</button> }
              </td>
            </tr>
          } @empty { <tr><td colspan="6" class="muted" data-testid="no-seller-listings">No listing.</td></tr> }
        </tbody>
      </table></div>
    }
  `,
  styles: `.box { border: 1px solid var(--mat-sys-outline-variant); border-radius: 8px; padding: 10px 12px; margin: 10px 0; }
    .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-bottom: 4px; } .wide { min-width: 280px; flex: 1; } .full { width: 100%; }
    h3 { margin: 0 0 8px; font: var(--mat-sys-title-small); } .demo { display: flex; gap: 8px; align-items: center; }`,
})
export class ListingsPage implements OnInit {
  private readonly api = inject(MarketplaceApi);
  private readonly ledger = inject(LedgerApi);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotifyService);
  protected readonly label = mlabel;
  protected readonly badge = marketBadge;
  protected readonly money = money;
  protected readonly canCreate = inject(AuthService).has(P.LISTINGS_MANAGE);
  protected readonly data = signal<Listings | null>(null);
  protected readonly owners = signal<Owner[]>([]);
  protected readonly ranges = signal<{ id: string; text: string }[]>([]);
  protected readonly busy = signal(false);
  protected source: Owner | null = null;
  protected f = { range: '', title: '', qty: null as number | null, price: '', currency: 'INR', min: null as number | null, max: null as number | null,
    window: 48, until: '', cob: '' };
  private key = newKey();

  ngOnInit(): void {
    this.reload();
    if (this.canCreate) {
      this.ledger.inventory().subscribe((inv) => this.owners.set(inv.batches.filter((b) => b.opening?.status === 'CONFIRMED').flatMap((b) =>
        b.balances.filter((x) => x.available > 0).map((x) => ({ batch: b, owner_id: x.owner_organization_id, owner_name: x.owner_name, available: x.available })))));
    }
  }

  private reload(): void {
    this.api.listings(true).subscribe((d) => this.data.set(d));
  }

  protected loadRanges(): void {
    const s = this.source;
    this.f.range = '';
    if (!s) return;
    this.ledger.positions(s.batch.batch_id).subscribe((ps) => {
      const seen = new Map<string, string>();
      for (const p of ps) if (p.owner_organization_id === s.owner_id && !seen.has(p.serial_range_id)) seen.set(p.serial_range_id, p.registry_range);
      this.ranges.set([...seen].map(([id, text]) => ({ id, text })));
    });
  }

  protected valid(): boolean {
    const q = Number(this.f.qty);
    return !!this.source && this.f.title.trim().length > 0 && Number.isInteger(q) && q > 0 && /^\d+(\.\d{1,4})?$/.test(this.f.price.trim())
      && /^[A-Za-z]{3}$/.test(this.f.currency.trim()) && Number(this.f.window) >= 1 && Number(this.f.window) <= 720;
  }

  protected create(): void {
    const f = this.f;
    const s = this.source;
    if (!s) return;
    runAction(this.api.createListing({ seller_organization_id: s.owner_id, batch_id: s.batch.batch_id, serial_range_id: f.range || null,
      title: f.title.trim(), listed_quantity: Number(f.qty), unit_price: f.price.trim(), currency: f.currency.trim().toUpperCase(),
      min_quantity: f.min || null, max_quantity: f.max || null, payment_window_hours: Number(f.window),
      valid_until: f.until ? new Date(f.until).toISOString() : null, co_benefits: f.cob.trim() || null }, this.key),
    this.busy, this.notify, 'Draft listing created — submit it for approval.', () => {
      this.key = newKey();
      this.reload();
    });
  }

  protected pick(l: Listing, ev: Event): void {
    const file = (ev.target as HTMLInputElement).files?.[0];
    if (file) runAction(this.api.listingDocument(l.id, file), this.busy, this.notify, 'Document published on the listing.', () => this.reload());
  }

  protected act(l: Listing, action: 'submit' | 'approve' | 'pause' | 'resume'): void {
    const message = { submit: 'Listing submitted for approval.', approve: 'Listing approved — price and disclosure are frozen.',
      pause: 'Listing paused.', resume: 'Listing resumed.' }[action];
    runAction(this.api.listingAction(l.id, action, {}, newKey()), this.busy, this.notify, message, () => this.reload());
  }

  protected close(l: Listing): void {
    askReason(this.dialog, { title: `Close ${l.listing_code}?`, confirmLabel: 'Close listing', danger: true,
      message: 'Orders already placed are not affected.' }).subscribe((x) => {
      if (x) runAction(this.api.listingAction(l.id, 'close', { reason: x.reason }), this.busy, this.notify, 'Listing closed.', () => this.reload());
    });
  }
}
