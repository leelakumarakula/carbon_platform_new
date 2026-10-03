import { DatePipe, JsonPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { Observable, switchMap } from 'rxjs';

import { AuthService } from '../core/auth/auth.service';
import { P } from '../core/auth/permissions';
import { NotifyService } from '../core/notify.service';
import { label } from '../farmer/farmer.models';
import { PageHeader } from '../shared/page-header';
import { askReason } from '../shared/reason-dialog';
import { runAction } from '../shared/run-action';
import { StatusBadge } from '../shared/status-badge';
import { LedgerApi, newKey } from './ledger.api';
import {
  BALANCE_COLUMNS, Entry, Inventory, InventoryBatch, Position, Recipient, Reservation, Retirement, Reversal, Transfer, ledgerBadge, total,
} from './ledger.models';

interface RangeOption { id: string; text: string }

/** Credit ledger: registry-issued batches opened (dual control) into positions owned by organizations; reservations, transfers and retirements
 *  move whole positions atomically. Every balance is derived by the server; no request carries a balance. No price, order or payment. */
@Component({
  selector: 'app-ledger-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, JsonPipe, FormsModule, MatButtonModule, MatCheckboxModule, MatFormFieldModule, MatInputModule, MatSelectModule, PageHeader,
    StatusBadge],
  template: `
    <app-page-header title="Credit ledger" subtitle="Ownership, reservation, transfer and retirement of registry-issued credits" />
    @if (inv(); as v) {
      <p class="note" data-testid="ledger-note">{{ v.note }}</p>
      @if (v.demo_note) { <p class="note demo" data-testid="ledger-demo-note"><app-status-badge status="DEMO" text="DEMO" /> {{ v.demo_note }}</p> }
      <div class="table-wrap"><table class="table" data-testid="ledger-inventory">
        <thead><tr><th>Batch</th><th>Project · period</th><th>Vintage</th><th>Issued (registry)</th>
          @for (c of columns; track c.key) { <th>{{ c.label }}</th> }<th>Ledger</th></tr></thead>
        <tbody>
          @for (b of v.batches; track b.batch_id) {
            <tr [attr.data-batch]="b.batch_code" [class.sel]="sel()?.batch_id === b.batch_id">
              <td>{{ b.batch_code }}<div class="small muted">{{ b.registry_name }}</div></td>
              <td>{{ b.project_code }} · #{{ b.period_number }}</td><td>{{ b.vintage }}</td><td>{{ b.issued }} {{ b.unit }}</td>
              @for (c of columns; track c.key) { <td>{{ sum(b, c.key) }}</td> }
              <td>
                @if (b.opening; as o) {
                  <app-status-badge [status]="badge(o.status)" [text]="o.opening_code + ' · ' + label(o.status)" />
                  @if (o.status === 'REQUESTED') {
                    @if (o.can_confirm) { <button mat-button type="button" [disabled]="busy()" (click)="confirmOpening(o.id)">Confirm opening</button> }
                    @if (canManage || canConfirm) { <button mat-button type="button" [disabled]="busy()" (click)="cancelOpening(o.id)">Cancel</button> }
                  }
                }
                @if (canOpen(b)) { <button mat-stroked-button type="button" [disabled]="busy()" (click)="open(b)">Open in ledger</button> }
                @if (b.opening?.status === 'CONFIRMED') { <button mat-button type="button" (click)="select(b)">Details</button> }
              </td>
            </tr>
          } @empty { <tr><td [attr.colspan]="columns.length + 5" class="muted" data-testid="no-ledger-batches">No registry-issued credit batch.</td></tr> }
        </tbody>
      </table></div>
    }

    @if (sel(); as b) {
      <section data-testid="ledger-batch">
        <h3>{{ b.batch_code }} · {{ b.vintage }} · issued {{ b.issued }} {{ b.unit }}</h3>
        <div class="table-wrap"><table class="table" data-testid="ledger-balances">
          <thead><tr><th>Owner</th>@for (c of columns; track c.key) { <th>{{ c.label }}</th> }</tr></thead>
          <tbody>@for (o of b.balances; track o.owner_organization_id) {
            <tr><td>{{ o.owner_name }}</td>@for (c of columns; track c.key) { <td>{{ o[c.key] }}</td> }</tr>
          }</tbody>
        </table></div>

        <h4>Positions <mat-checkbox [(ngModel)]="includeConsumed" (ngModelChange)="loadBatch()">include consumed</mat-checkbox></h4>
        <div class="table-wrap"><table class="table" data-testid="ledger-positions">
          <thead><tr><th>Owner</th><th>Registry range</th><th>Sub-range</th><th>State</th><th>Quantity</th><th>Account</th><th>Entries</th></tr></thead>
          <tbody>@for (p of positions(); track p.id) {
            <tr [class.muted]="p.status === 'CONSUMED'">
              <td>{{ p.owner_name }}</td><td class="mono">{{ p.registry_range }}</td><td class="mono">{{ p.sub_range ?? 'quantity within range' }}</td>
              <td><app-status-badge [status]="badge(p.state)" [text]="label(p.state)" />@if (p.status === 'CONSUMED') { <span class="small"> consumed</span> }</td>
              <td>{{ p.quantity }}</td><td class="mono">{{ p.holding_external_account_id }}</td>
              <td><button mat-button type="button" (click)="showEntry(p.created_by_entry_id)">created by</button>
                @if (p.consumed_by_entry_id; as e) { <button mat-button type="button" (click)="showEntry(e)">consumed by</button> }</td>
            </tr>
          }</tbody>
        </table></div>

        @if (canManage) {
          <div class="forms">
            <div class="box" data-testid="reserve-form"><h4>Reserve</h4>
              <mat-form-field subscriptSizing="dynamic" class="full"><mat-label>Owner</mat-label>
                <mat-select [(ngModel)]="rsv.owner">@for (o of b.balances; track o.owner_organization_id) {
                  <mat-option [value]="o.owner_organization_id">{{ o.owner_name }} ({{ o.available }} available)</mat-option> }</mat-select></mat-form-field>
              <mat-form-field subscriptSizing="dynamic" class="full"><mat-label>Quantity (whole credits)</mat-label>
                <input matInput type="number" min="1" step="1" [(ngModel)]="rsv.quantity" /></mat-form-field>
              <mat-form-field subscriptSizing="dynamic" class="full"><mat-label>Purpose</mat-label><input matInput [(ngModel)]="rsv.purpose" /></mat-form-field>
              <mat-form-field subscriptSizing="dynamic" class="full"><mat-label>Purpose reference (optional)</mat-label>
                <input matInput [(ngModel)]="rsv.reference" /></mat-form-field>
              <mat-form-field subscriptSizing="dynamic" class="full"><mat-label>Recipient (optional)</mat-label>
                <mat-select [(ngModel)]="rsv.recipient"><mat-option value="">—</mat-option>@for (r of recipients(); track r.id) {
                  <mat-option [value]="r.id">{{ r.name }} ({{ label(r.org_type) }})</mat-option> }</mat-select></mat-form-field>
              <mat-form-field subscriptSizing="dynamic" class="full"><mat-label>Registry range (optional)</mat-label>
                <mat-select [(ngModel)]="rsv.range"><mat-option value="">Any</mat-option>@for (r of ranges(); track r.id) {
                  <mat-option [value]="r.id">{{ r.text }}</mat-option> }</mat-select></mat-form-field>
              <mat-form-field subscriptSizing="dynamic" class="full"><mat-label>Expires at</mat-label>
                <input matInput type="datetime-local" [(ngModel)]="rsv.expires" /></mat-form-field>
              <button mat-flat-button type="button" [disabled]="busy() || !rsv.owner || !whole(rsv.quantity) || rsv.purpose.trim().length < 3 || !rsv.expires"
                (click)="reserve(b)">Reserve</button>
            </div>

            <div class="box" data-testid="transfer-form"><h4>Request transfer</h4>
              <mat-form-field subscriptSizing="dynamic" class="full"><mat-label>Kind</mat-label>
                <mat-select [(ngModel)]="trf.kind"><mat-option value="INTERNAL">Internal (platform ownership)</mat-option>
                  <mat-option value="REGISTRY">Registry (recorded at the registry)</mat-option></mat-select></mat-form-field>
              <mat-form-field subscriptSizing="dynamic" class="full"><mat-label>Sender</mat-label>
                <mat-select [(ngModel)]="trf.sender">@for (o of b.balances; track o.owner_organization_id) {
                  <mat-option [value]="o.owner_organization_id">{{ o.owner_name }} ({{ o.available }} available)</mat-option> }</mat-select></mat-form-field>
              <mat-form-field subscriptSizing="dynamic" class="full"><mat-label>Recipient</mat-label>
                <mat-select [(ngModel)]="trf.recipient">@for (r of recipients(); track r.id) {
                  <mat-option [value]="r.id">{{ r.name }} ({{ label(r.org_type) }})</mat-option> }</mat-select></mat-form-field>
              <mat-form-field subscriptSizing="dynamic" class="full"><mat-label>From reservation (optional)</mat-label>
                <mat-select [(ngModel)]="trf.reservation"><mat-option value="">—</mat-option>@for (r of activeReservations(); track r.id) {
                  <mat-option [value]="r.id">{{ r.reservation_code }} · {{ r.quantity }}</mat-option> }</mat-select></mat-form-field>
              @if (!trf.reservation) {
                <mat-form-field subscriptSizing="dynamic" class="full"><mat-label>Quantity (whole credits)</mat-label>
                  <input matInput type="number" min="1" step="1" [(ngModel)]="trf.quantity" /></mat-form-field>
                <mat-form-field subscriptSizing="dynamic" class="full"><mat-label>Registry range (optional)</mat-label>
                  <mat-select [(ngModel)]="trf.range"><mat-option value="">Any</mat-option>@for (r of ranges(); track r.id) {
                    <mat-option [value]="r.id">{{ r.text }}</mat-option> }</mat-select></mat-form-field>
              }
              @if (trf.kind === 'REGISTRY') {
                <mat-form-field subscriptSizing="dynamic" class="full"><mat-label>Recipient registry account id</mat-label>
                  <input matInput [(ngModel)]="trf.external" /></mat-form-field>
              }
              <mat-form-field subscriptSizing="dynamic" class="full"><mat-label>Purpose (optional)</mat-label><input matInput [(ngModel)]="trf.purpose" /></mat-form-field>
              <button mat-flat-button type="button" [disabled]="busy() || !canRequestTransfer()" (click)="requestTransfer(b)">Request transfer</button>
            </div>

            <div class="box" data-testid="retire-form"><h4>Request retirement</h4>
              <mat-form-field subscriptSizing="dynamic" class="full"><mat-label>Owner</mat-label>
                <mat-select [(ngModel)]="ret.owner">@for (o of b.balances; track o.owner_organization_id) {
                  <mat-option [value]="o.owner_organization_id">{{ o.owner_name }} ({{ o.available }} available)</mat-option> }</mat-select></mat-form-field>
              <mat-form-field subscriptSizing="dynamic" class="full"><mat-label>From reservation (optional)</mat-label>
                <mat-select [(ngModel)]="ret.reservation"><mat-option value="">—</mat-option>@for (r of activeReservations(); track r.id) {
                  <mat-option [value]="r.id">{{ r.reservation_code }} · {{ r.quantity }}</mat-option> }</mat-select></mat-form-field>
              @if (!ret.reservation) {
                <mat-form-field subscriptSizing="dynamic" class="full"><mat-label>Quantity (whole credits)</mat-label>
                  <input matInput type="number" min="1" step="1" [(ngModel)]="ret.quantity" /></mat-form-field>
              }
              <mat-form-field subscriptSizing="dynamic" class="full"><mat-label>Beneficiary</mat-label><input matInput [(ngModel)]="ret.beneficiary" /></mat-form-field>
              <mat-form-field subscriptSizing="dynamic" class="full"><mat-label>Retirement reason</mat-label><input matInput [(ngModel)]="ret.reason" /></mat-form-field>
              <button mat-flat-button type="button" [disabled]="busy() || !canRequestRetirement()" (click)="requestRetirement(b)">Request retirement</button>
            </div>
          </div>
        }

        <h4>Reservations</h4>
        <div class="table-wrap"><table class="table" data-testid="ledger-reservations">
          <thead><tr><th>Code</th><th>Quantity</th><th>Purpose</th><th>Expires</th><th>Status</th><th></th></tr></thead>
          <tbody>@for (r of reservations(); track r.id) {
            <tr><td>{{ r.reservation_code }}</td><td>{{ r.quantity }}</td><td>{{ r.purpose }}@if (r.purpose_reference) { · {{ r.purpose_reference }} }</td>
              <td>{{ r.expires_at | date: 'medium' }}</td><td><app-status-badge [status]="badge(r.status)" [text]="label(r.status)" /></td>
              <td>@if (r.status === 'ACTIVE' && canManage) { <button mat-button type="button" [disabled]="busy()" (click)="release(r)">Release</button> }</td></tr>
          } @empty { <tr><td colspan="6" class="muted">No reservation.</td></tr> }</tbody>
        </table></div>

        <h4>Transfers</h4>
        <div class="table-wrap"><table class="table" data-testid="ledger-transfers">
          <thead><tr><th>Code</th><th>Kind</th><th>From → to</th><th>Quantity</th><th>Status</th><th>Second-person action</th></tr></thead>
          <tbody>@for (t of transfers(); track t.id) {
            <tr [attr.data-transfer]="t.transfer_code"><td>{{ t.transfer_code }}<div class="small muted">by {{ t.requested_by_name }}</div></td>
              <td>{{ label(t.kind) }}</td><td>{{ t.sender_name }} → {{ t.recipient_name }}
                @if (t.recipient_external_account_id) { <div class="small mono">{{ t.recipient_external_account_id }}</div> }</td>
              <td>{{ t.quantity }}</td>
              <td><app-status-badge [status]="badge(t.status)" [text]="label(t.status)" />
                @if (t.registry_transfer_reference) { <div class="small">registry {{ t.registry_transfer_reference }}</div> }
                @if (t.completed_by_name) { <div class="small muted">completed by {{ t.completed_by_name }}</div> }</td>
              <td>
                @if (t.status === 'REQUESTED') {
                  @if (t.can_complete) {
                    @if (t.kind === 'REGISTRY') {
                      <input class="ref" placeholder="Registry transfer reference" [(ngModel)]="text['tref-' + t.id]" />
                      <input type="file" accept="application/pdf" (change)="pick('tdoc-' + t.id, $event)" />
                    }
                    <button mat-flat-button type="button" [disabled]="busy() || !canComplete(t)" (click)="complete(t)">Complete</button>
                    <button mat-button type="button" [disabled]="busy()" (click)="closeTransfer(t, 'reject')">Reject</button>
                  }
                  @if (canManage) { <button mat-button type="button" [disabled]="busy()" (click)="closeTransfer(t, 'cancel')">Cancel</button> }
                }
                @if (t.status === 'COMPLETED' && t.kind === 'INTERNAL' && t.completion_entry_id && canManage) {
                  <button mat-button type="button" [disabled]="busy()" (click)="reverse(t)">Request reversal</button>
                }
                @if (t.completion_entry_id; as e) { <button mat-button type="button" (click)="showEntry(e)">Entry</button> }
              </td></tr>
          } @empty { <tr><td colspan="6" class="muted">No transfer.</td></tr> }</tbody>
        </table></div>

        <h4>Retirements</h4>
        <div class="table-wrap"><table class="table" data-testid="ledger-retirements">
          <thead><tr><th>Code</th><th>Owner</th><th>Quantity</th><th>Beneficiary · reason</th><th>Status</th><th>Second-person action</th></tr></thead>
          <tbody>@for (r of retirements(); track r.id) {
            <tr [attr.data-retirement]="r.retirement_code"><td>{{ r.retirement_code }}<div class="small muted">by {{ r.requested_by_name }}</div></td>
              <td>{{ r.owner_name }}</td><td>{{ r.quantity }}</td><td>{{ r.beneficiary }}<div class="small">{{ r.reason }}</div></td>
              <td><app-status-badge [status]="badge(r.status)" [text]="label(r.status)" />
                @if (r.registry_retirement_reference) { <div class="small">registry {{ r.registry_retirement_reference }} · {{ r.retirement_date }}</div> }</td>
              <td>
                @if (r.status === 'REQUESTED') {
                  @if (r.can_retire) {
                    <input class="ref" placeholder="Registry retirement reference" [(ngModel)]="text['rref-' + r.id]" />
                    <input type="date" [(ngModel)]="text['rdate-' + r.id]" />
                    <input class="ref" placeholder="Serial start (as stated, optional)" [(ngModel)]="text['rs-' + r.id]" />
                    <input class="ref" placeholder="Serial end (as stated, optional)" [(ngModel)]="text['re-' + r.id]" />
                    <input type="file" accept="application/pdf" (change)="pick('rdoc-' + r.id, $event)" />
                    <button mat-flat-button type="button" [disabled]="busy() || !canRetire(r)" (click)="retire(r)">Record retirement</button>
                    <button mat-button type="button" [disabled]="busy()" (click)="closeRetirement(r, 'reject')">Reject</button>
                  }
                  @if (canManage) { <button mat-button type="button" [disabled]="busy()" (click)="closeRetirement(r, 'cancel')">Cancel</button> }
                }
                <button mat-button type="button" (click)="showLineage(r)">Lineage</button>
              </td></tr>
          } @empty { <tr><td colspan="6" class="muted">No retirement.</td></tr> }</tbody>
        </table></div>

        <h4>Reversals</h4>
        <div class="table-wrap"><table class="table" data-testid="ledger-reversals">
          <thead><tr><th>Code</th><th>Reason</th><th>Status</th><th></th></tr></thead>
          <tbody>@for (x of reversals(); track x.id) {
            <tr><td>{{ x.reversal_code }}<div class="small muted">by {{ x.requested_by_name }}</div></td><td>{{ x.reason }}</td>
              <td><app-status-badge [status]="badge(x.status)" [text]="label(x.status)" />@if (x.decision_note) { <div class="small">{{ x.decision_note }}</div> }</td>
              <td>@if (x.status === 'REQUESTED' && canConfirm) {
                <button mat-button type="button" [disabled]="busy()" (click)="decideReversal(x, true)">Apply</button>
                <button mat-button type="button" [disabled]="busy()" (click)="decideReversal(x, false)">Reject</button> }</td></tr>
          } @empty { <tr><td colspan="4" class="muted">No reversal.</td></tr> }</tbody>
        </table></div>
      </section>
    }

    @if (entry(); as e) {
      <section class="box" data-testid="ledger-entry">
        <h4>{{ e.entry_code }} · {{ label(e.entry_type) }} · {{ e.quantity }}</h4>
        <div class="small">by {{ e.actor_name }}@if (e.confirmed_by_name) { · confirmed by {{ e.confirmed_by_name }} } · {{ e.created_at | date: 'medium' }}
          @if (e.reason) { · {{ e.reason }} }</div>
        <div class="io"><div><b>Inputs</b>@for (p of e.inputs; track p.id) { <div class="small">{{ p.owner_name }} · {{ label(p.state) }} · {{ p.quantity }}</div> }
          @empty { <div class="small muted">none</div> }</div>
          <div><b>Outputs</b>@for (p of e.outputs; track p.id) { <div class="small">{{ p.owner_name }} · {{ label(p.state) }} · {{ p.quantity }}</div> }</div></div>
      </section>
    }
    @if (lineage(); as l) { <pre class="mono" data-testid="retirement-lineage">{{ l | json }}</pre> }
  `,
  styles: `h3 { margin: 16px 0 6px; font: var(--mat-sys-title-small); } h4 { margin: 12px 0 4px; }
    .demo { display: flex; gap: 8px; align-items: center; } tr.sel { background: var(--mat-sys-surface-container); }
    .forms { display: flex; gap: 10px; flex-wrap: wrap; } .forms .box { flex: 1 1 260px; }
    .box { border: 1px solid var(--mat-sys-outline-variant); border-radius: 8px; padding: 8px 10px; margin: 6px 0; } .full { width: 100%; margin-bottom: 4px; }
    .mono { font-family: monospace; font-size: 11px; word-break: break-all; } pre { max-height: 360px; overflow: auto; white-space: pre-wrap; }
    .ref { width: 170px; margin: 2px; } .io { display: flex; gap: 24px; margin-top: 6px; }`,
})
export class LedgerPage implements OnInit {
  private readonly api = inject(LedgerApi);
  private readonly auth = inject(AuthService);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotifyService);
  protected readonly label = label;
  protected readonly badge = ledgerBadge;
  protected readonly columns = BALANCE_COLUMNS;
  protected readonly canManage = this.auth.has(P.CREDITS_MANAGE);
  protected readonly canConfirm = this.auth.has(P.CREDITS_CONFIRM);
  protected readonly inv = signal<Inventory | null>(null);
  protected readonly sel = signal<InventoryBatch | null>(null);
  protected readonly positions = signal<Position[]>([]);
  protected readonly reservations = signal<Reservation[]>([]);
  protected readonly transfers = signal<Transfer[]>([]);
  protected readonly retirements = signal<Retirement[]>([]);
  protected readonly reversals = signal<Reversal[]>([]);
  protected readonly recipients = signal<Recipient[]>([]);
  protected readonly entry = signal<Entry | null>(null);
  protected readonly lineage = signal<unknown>(null);
  protected readonly busy = signal(false);
  protected includeConsumed = false;
  protected text: Record<string, string | undefined> = {};
  protected files: Record<string, File | undefined> = {};
  protected rsv = this.blankReservation();
  protected trf = this.blankTransfer();
  protected ret = this.blankRetirement();
  /** One Idempotency-Key per submission: a retry after a network error replays rather than acting twice. */
  private keys: Record<string, string> = {};

  ngOnInit(): void {
    this.reload();
  }

  protected sum(b: InventoryBatch, key: (typeof BALANCE_COLUMNS)[number]['key']): number {
    return total(b, key);
  }

  protected whole(v: unknown): boolean {
    return Number.isInteger(Number(v)) && Number(v) > 0;
  }

  protected canOpen(b: InventoryBatch): boolean {
    return this.canManage && b.batch_status === 'ISSUED' && b.environment !== 'DEMO' && (!b.opening || b.opening.status === 'CANCELLED');
  }

  private reload(): void {
    this.api.inventory().subscribe((v) => {
      this.inv.set(v);
      const s = this.sel();
      if (s) {
        const again = v.batches.find((b) => b.batch_id === s.batch_id) ?? null;
        this.sel.set(again);
        if (again) this.loadBatch();
      }
    });
  }

  protected select(b: InventoryBatch): void {
    this.sel.set(b);
    this.entry.set(null);
    this.lineage.set(null);
    this.rsv = this.blankReservation();
    this.trf = this.blankTransfer();
    this.ret = this.blankRetirement();
    if (this.canManage) this.api.recipients(b.environment).subscribe((r) => this.recipients.set(r));
    this.loadBatch();
  }

  loadBatch(): void {
    const b = this.sel();
    if (!b) return;
    this.api.positions(b.batch_id, this.includeConsumed).subscribe((p) => this.positions.set(p));
    this.api.reservations(b.batch_id).subscribe((r) => this.reservations.set(r));
    this.api.transfers(b.batch_id).subscribe((t) => this.transfers.set(t));
    this.api.retirements(b.batch_id).subscribe((r) => this.retirements.set(r));
    this.api.reversals().subscribe((r) => this.reversals.set(r.filter((x) => x.batch_id === b.batch_id)));
  }

  protected ranges(): RangeOption[] {
    const seen = new Map<string, string>();
    for (const p of this.positions()) if (!seen.has(p.serial_range_id)) seen.set(p.serial_range_id, p.registry_range);
    return [...seen].map(([id, text]) => ({ id, text }));
  }

  protected activeReservations(): Reservation[] {
    return this.reservations().filter((r) => r.status === 'ACTIVE');
  }

  protected pick(key: string, ev: Event): void {
    this.files[key] = (ev.target as HTMLInputElement).files?.[0];
  }

  private key(name: string): string {
    return (this.keys[name] ??= newKey());
  }

  private act<T>(obs: Observable<T>, message: string, keyName?: string, done?: (v: T) => void): void {
    runAction(obs, this.busy, this.notify, message, (v) => {
      if (keyName) delete this.keys[keyName];
      done?.(v);
      this.reload();
    });
  }

  protected open(b: InventoryBatch): void {
    askReason(this.dialog, { title: `Open ${b.batch_code} in the ledger?`, confirmLabel: 'Request opening',
      message: 'All registry-issued credits of the batch become AVAILABLE to the holding account\'s organization once a second person confirms.' })
      .subscribe((x) => { if (x) this.act(this.api.open(b.batch_id), 'Opening requested — a second person confirms.'); });
  }

  protected confirmOpening(id: string): void {
    this.act(this.api.confirmOpening(id), 'Batch opened in the ledger.');
  }

  protected cancelOpening(id: string): void {
    askReason(this.dialog, { title: 'Cancel the opening request?', confirmLabel: 'Cancel opening', danger: true })
      .subscribe((x) => { if (x) this.act(this.api.cancelOpening(id, x.reason), 'Opening request cancelled.'); });
  }

  protected reserve(b: InventoryBatch): void {
    const r = this.rsv;
    this.act(this.api.reserve({ batch_id: b.batch_id, owner_organization_id: r.owner, quantity: Number(r.quantity), purpose: r.purpose.trim(),
      purpose_reference: r.reference.trim() || null, recipient_organization_id: r.recipient || null, serial_range_id: r.range || null,
      expires_at: new Date(r.expires).toISOString() }, this.key('rsv')), 'Credits reserved.', 'rsv', () => { this.rsv = this.blankReservation(); });
  }

  protected release(r: Reservation): void {
    askReason(this.dialog, { title: `Release ${r.reservation_code}?`, confirmLabel: 'Release' })
      .subscribe((x) => { if (x) this.act(this.api.release(r.id, x.reason), 'Reservation released.'); });
  }

  protected canRequestTransfer(): boolean {
    const t = this.trf;
    return !!t.sender && !!t.recipient && t.sender !== t.recipient && (!!t.reservation || this.whole(t.quantity))
      && (t.kind === 'INTERNAL' || !!t.external.trim());
  }

  protected requestTransfer(b: InventoryBatch): void {
    const t = this.trf;
    this.act(this.api.requestTransfer({ kind: t.kind, batch_id: b.batch_id, sender_organization_id: t.sender, recipient_organization_id: t.recipient,
      quantity: t.reservation ? null : Number(t.quantity), reservation_id: t.reservation || null, serial_range_id: t.reservation ? null : t.range || null,
      recipient_external_account_id: t.kind === 'REGISTRY' ? t.external.trim() : null, purpose: t.purpose.trim() || null }, this.key('trf')),
    'Transfer requested — a second person completes it.', 'trf', () => { this.trf = this.blankTransfer(); });
  }

  protected canComplete(t: Transfer): boolean {
    return t.kind === 'INTERNAL' || (!!this.text['tref-' + t.id]?.trim() && !!this.files['tdoc-' + t.id]);
  }

  protected complete(t: Transfer): void {
    const name = 'tc-' + t.id;
    if (t.kind === 'INTERNAL') {
      this.act(this.api.completeTransfer(t.id, {}, this.key(name)), 'Transfer completed.', name);
      return;
    }
    const file = this.files['tdoc-' + t.id];
    if (!file) return;
    this.act(this.api.transferDoc(t.id, file).pipe(switchMap((d) => this.api.completeTransfer(t.id, {
      registry_transfer_reference: (this.text['tref-' + t.id] ?? '').trim(), document_id: d.document_id }, this.key(name)))),
    'Registry transfer recorded and completed.', name);
  }

  protected closeTransfer(t: Transfer, how: 'cancel' | 'reject'): void {
    askReason(this.dialog, { title: `${how === 'cancel' ? 'Cancel' : 'Reject'} ${t.transfer_code}?`, confirmLabel: how === 'cancel' ? 'Cancel transfer' : 'Reject',
      danger: true }).subscribe((x) => {
      if (x) this.act(how === 'cancel' ? this.api.cancelTransfer(t.id, x.reason) : this.api.rejectTransfer(t.id, x.reason), how === 'cancel' ? 'Transfer cancelled.' : 'Transfer rejected.');
    });
  }

  protected reverse(t: Transfer): void {
    const entryId = t.completion_entry_id;
    if (!entryId) return;
    askReason(this.dialog, { title: `Reverse ${t.transfer_code}?`, confirmLabel: 'Request reversal', danger: true,
      message: 'A compensating entry returns the credits to the sender, provided the recipient has not moved them. A second person applies it.' })
      .subscribe((x) => { if (x) this.act(this.api.reverse(entryId, x.reason), 'Reversal requested — a second person applies it.'); });
  }

  protected decideReversal(x: Reversal, apply: boolean): void {
    askReason(this.dialog, { title: `${apply ? 'Apply' : 'Reject'} ${x.reversal_code}?`, confirmLabel: apply ? 'Apply' : 'Reject', danger: !apply })
      .subscribe((r) => {
        if (r) this.act(apply ? this.api.applyReversal(x.id, r.reason) : this.api.rejectReversal(x.id, r.reason), apply ? 'Reversal applied.' : 'Reversal rejected.');
      });
  }

  protected canRequestRetirement(): boolean {
    const r = this.ret;
    return !!r.owner && (!!r.reservation || this.whole(r.quantity)) && r.beneficiary.trim().length >= 2 && r.reason.trim().length >= 3;
  }

  protected requestRetirement(b: InventoryBatch): void {
    const r = this.ret;
    this.act(this.api.requestRetirement({ batch_id: b.batch_id, owner_organization_id: r.owner, quantity: r.reservation ? null : Number(r.quantity),
      reservation_id: r.reservation || null, beneficiary: r.beneficiary.trim(), reason: r.reason.trim() }, this.key('ret')),
    'Retirement requested — RETIRED only once the registry\'s certificate is recorded.', 'ret', () => { this.ret = this.blankRetirement(); });
  }

  protected canRetire(r: Retirement): boolean {
    const start = this.text['rs-' + r.id]?.trim();
    const end = this.text['re-' + r.id]?.trim();
    return !!this.text['rref-' + r.id]?.trim() && !!this.text['rdate-' + r.id] && !!this.files['rdoc-' + r.id] && !start === !end;
  }

  protected retire(r: Retirement): void {
    const file = this.files['rdoc-' + r.id];
    if (!file) return;
    const start = this.text['rs-' + r.id]?.trim();
    const end = this.text['re-' + r.id]?.trim();
    const name = 'rt-' + r.id;
    this.act(this.api.retirementDoc(r.id, file).pipe(switchMap((d) => this.api.retire(r.id, {
      registry_retirement_reference: (this.text['rref-' + r.id] ?? '').trim(), retirement_date: this.text['rdate-' + r.id], document_id: d.document_id,
      retired_serials: start && end ? [{ serial_start: start, serial_end: end, quantity: r.quantity }] : null }, this.key(name)))),
    'Retirement recorded from the registry certificate.', name);
  }

  protected closeRetirement(r: Retirement, how: 'cancel' | 'reject'): void {
    askReason(this.dialog, { title: `${how === 'cancel' ? 'Cancel' : 'Reject'} ${r.retirement_code}?`,
      confirmLabel: how === 'cancel' ? 'Cancel retirement' : 'Reject', danger: true }).subscribe((x) => {
      if (x) this.act(how === 'cancel' ? this.api.cancelRetirement(r.id, x.reason) : this.api.rejectRetirement(r.id, x.reason), how === 'cancel' ? 'Retirement cancelled.' : 'Retirement rejected.');
    });
  }

  protected showEntry(id: string): void {
    this.api.entry(id).subscribe((e) => this.entry.set(e));
  }

  protected showLineage(r: Retirement): void {
    this.api.retirementLineage(r.id).subscribe((l) => this.lineage.set(l));
  }

  private blankReservation() {
    return { owner: '', quantity: null as number | null, purpose: '', reference: '', recipient: '', range: '', expires: '' };
  }

  private blankTransfer() {
    return { kind: 'INTERNAL' as 'INTERNAL' | 'REGISTRY', sender: '', recipient: '', quantity: null as number | null, reservation: '', range: '',
      external: '', purpose: '' };
  }

  private blankRetirement() {
    return { owner: '', quantity: null as number | null, reservation: '', beneficiary: '', reason: '' };
  }
}
