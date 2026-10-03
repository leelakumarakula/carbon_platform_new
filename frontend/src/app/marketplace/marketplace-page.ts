import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { Router, RouterLink } from '@angular/router';

import { DocumentsApi } from '../core/api/documents.api';
import { AuthService } from '../core/auth/auth.service';
import { P } from '../core/auth/permissions';
import { NotifyService } from '../core/notify.service';
import { PageHeader } from '../shared/page-header';
import { runAction } from '../shared/run-action';
import { StatusBadge } from '../shared/status-badge';
import { MarketplaceApi } from './marketplace.api';
import { BuyerProfileView, Listing, Listings, marketBadge, money, mlabel, newKey } from './marketplace.models';

interface CartLine { listing: Listing; quantity: number | null }

/** Marketplace (authenticated only): ACTIVE listings with allow-listed disclosure; KYC-verified buyers build an order (one seller, one
 *  currency). Placing the order reserves the credits in the ledger; nothing is owned until the seller confirms payment and the custodian
 *  completes the ledger transfer. */
@Component({
  selector: 'app-marketplace-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, MatButtonModule, MatFormFieldModule, MatInputModule, MatSelectModule, RouterLink, PageHeader, StatusBadge],
  template: `
    <app-page-header title="Marketplace" subtitle="Registry-issued credits offered at a fixed price per credit" />
    @if (data(); as d) {
      <p class="note" data-testid="market-note">{{ d.note }}</p>
      @if (d.demo_note) { <p class="note demo" data-testid="market-demo-note"><app-status-badge status="DEMO" text="DEMO" /> {{ d.demo_note }}</p> }
      @if (canOrder && kyc(); as k) {
        @if (k.profile?.status !== 'KYC_VERIFIED') {
          <p class="note warn" data-testid="kyc-required">Your organization must be KYC verified to place orders
            (status: {{ k.profile ? label(k.profile.status) : 'no buyer profile' }}). <a routerLink="/marketplace/profile">Buyer profile</a></p>
        }
      }
      <div class="table-wrap"><table class="table" data-testid="market-listings">
        <thead><tr><th>Listing</th><th>Project · vintage</th><th>Methodology · standard</th><th>Registry</th><th>Price per credit</th>
          <th>Available</th><th>Seller</th><th></th></tr></thead>
        <tbody>
          @for (l of d.listings; track l.id) {
            <tr [attr.data-listing]="l.listing_code">
              <td>{{ l.listing_code }}<div class="small">{{ l.title }}</div></td>
              <td>{{ l.disclosure['project_code'] }} · {{ l.disclosure['vintage'] }}</td>
              <td>{{ l.disclosure['methodology'] }}<div class="small">{{ l.disclosure['standard'] }}</div></td>
              <td>{{ l.disclosure['registry'] }}</td><td>{{ money(l.unit_price, l.currency) }}</td>
              <td>{{ l.available_quantity }}</td><td>{{ l.seller_name }}</td>
              <td><button mat-button type="button" (click)="show(l)">Details</button></td>
            </tr>
          } @empty { <tr><td colspan="8" class="muted" data-testid="no-listings">No listing is available.</td></tr> }
        </tbody>
      </table></div>
    }

    @if (sel(); as l) {
      <section class="box" data-testid="listing-detail">
        <h3>{{ l.listing_code }} · {{ l.title }} <app-status-badge [status]="badge(l.status)" [text]="label(l.status)" /></h3>
        <div class="grid">
          @for (kv of disclosure(l); track kv[0]) { <div><span class="muted small">{{ label(kv[0]) }}</span><div>{{ kv[1] ?? '—' }}</div></div> }
          <div><span class="muted small">Price per credit</span><div>{{ money(l.unit_price, l.currency) }}</div></div>
          <div><span class="muted small">Available now</span><div>{{ l.available_quantity }} of {{ l.listed_quantity }} listed</div></div>
          <div><span class="muted small">Order size</span><div>{{ l.min_quantity ?? 1 }} – {{ l.max_quantity ?? 'any' }} credits</div></div>
          <div><span class="muted small">Payment window</span><div>{{ l.payment_window_hours }} h after ordering</div></div>
        </div>
        @if (l.co_benefits) { <p><b>Co-benefits (seller's statement):</b> {{ l.co_benefits }}</p> }
        @for (doc of l.documents; track doc.document_id) {
          <button mat-button type="button" (click)="download(doc.document_id, doc.title)">{{ doc.title }} (PDF)</button>
        }
        <p class="small muted">Disclosure fingerprint (SHA-256): {{ l.disclosure_sha256 }}</p>
        @if (canOrder && l.available_quantity > 0) {
          <div class="row">
            <mat-form-field subscriptSizing="dynamic"><mat-label>Quantity (whole credits)</mat-label>
              <input matInput type="number" min="1" step="1" [(ngModel)]="qty" data-testid="order-qty" /></mat-form-field>
            <button mat-stroked-button type="button" (click)="add(l)" [disabled]="!whole(qty)">Add to order</button>
          </div>
        }
      </section>
    }

    @if (canOrder && cart().length) {
      <section class="box" data-testid="order-builder">
        <h3>Order (one seller, one currency)</h3>
        <table class="table"><thead><tr><th>Listing</th><th>Quantity</th><th>Price per credit</th><th></th></tr></thead><tbody>
          @for (c of cart(); track c.listing.id) {
            <tr><td>{{ c.listing.listing_code }}</td><td>{{ c.quantity }}</td><td>{{ money(c.listing.unit_price, c.listing.currency) }}</td>
              <td><button mat-button type="button" (click)="remove(c)">Remove</button></td></tr>
          }
        </tbody></table>
        <div class="row">
          <mat-form-field subscriptSizing="dynamic"><mat-label>Delivery</mat-label>
            <mat-select [(ngModel)]="kind"><mat-option value="INTERNAL">Ledger transfer (default)</mat-option>
              <mat-option value="REGISTRY">Registry transfer to my registry account</mat-option></mat-select></mat-form-field>
          @if (kind === 'REGISTRY') {
            <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>My registry account id</mat-label><input matInput [(ngModel)]="account" /></mat-form-field>
          }
          <button mat-flat-button type="button" data-testid="place-order" [disabled]="busy() || !kyc()?.profile || (kind === 'REGISTRY' && !account.trim())"
            (click)="place()">Place order</button>
        </div>
        <p class="small muted">The total is computed by the platform when you place the order (no fee, commission or tax).</p>
      </section>
    }
  `,
  styles: `.demo { display: flex; gap: 8px; align-items: center; } .warn { color: #7a5200; } h3 { margin: 0 0 8px; font: var(--mat-sys-title-small); }
    .box { border: 1px solid var(--mat-sys-outline-variant); border-radius: 8px; padding: 10px 12px; margin: 12px 0; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 8px; margin-bottom: 8px; }
    .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; } .wide { min-width: 260px; }`,
})
export class MarketplacePage implements OnInit {
  private readonly api = inject(MarketplaceApi);
  private readonly docs = inject(DocumentsApi);
  private readonly notify = inject(NotifyService);
  private readonly router = inject(Router);
  private readonly auth = inject(AuthService);
  protected readonly label = mlabel;
  protected readonly badge = marketBadge;
  protected readonly money = money;
  protected readonly canOrder = this.auth.has(P.ORDERS_PLACE);
  protected readonly data = signal<Listings | null>(null);
  protected readonly sel = signal<Listing | null>(null);
  protected readonly kyc = signal<BuyerProfileView | null>(null);
  protected readonly cart = signal<CartLine[]>([]);
  protected readonly busy = signal(false);
  protected qty: number | null = null;
  protected kind: 'INTERNAL' | 'REGISTRY' = 'INTERNAL';
  protected account = '';
  private key = newKey();

  ngOnInit(): void {
    this.api.listings().subscribe((d) => this.data.set(d));
    if (this.auth.has(P.BUYERS_KYC_SUBMIT)) this.api.profile().subscribe((k) => this.kyc.set(k));
  }

  protected whole(v: unknown): boolean {
    return Number.isInteger(Number(v)) && Number(v) > 0;
  }

  protected show(l: Listing): void {
    this.api.listing(l.id).subscribe((x) => this.sel.set(x));
  }

  protected disclosure(l: Listing): [string, string | number | null][] {
    return Object.entries(l.disclosure);
  }

  protected add(l: Listing): void {
    const rest = this.cart().filter((c) => c.listing.id !== l.id);
    if (rest.length && (rest[0].listing.seller_organization_id !== l.seller_organization_id || rest[0].listing.currency !== l.currency)) {
      this.notify.error(new Error('An order holds credits of one seller in one currency — place a separate order.'));
      return;
    }
    this.cart.set([...rest, { listing: l, quantity: Number(this.qty) }]);
    this.qty = null;
  }

  protected remove(c: CartLine): void {
    this.cart.set(this.cart().filter((x) => x !== c));
  }

  protected place(): void {
    const buyer = this.kyc()?.organization_id;
    if (!buyer) return;
    runAction(this.api.place({ buyer_organization_id: buyer, items: this.cart().map((c) => ({ listing_id: c.listing.id, quantity: c.quantity })),
      transfer_kind: this.kind, recipient_registry_account: this.kind === 'REGISTRY' ? this.account.trim() : null }, this.key),
    this.busy, this.notify, 'Order placed — the credits are reserved until the payment deadline.', (o) => {
      this.key = newKey();
      this.cart.set([]);
      void this.router.navigate(['/orders'], { queryParams: { id: o.id } });
    });
  }

  protected download(id: string, title: string): void {
    this.docs.download(id, `${title}.pdf`).subscribe({ error: (e: unknown) => this.notify.error(e) });
  }
}
