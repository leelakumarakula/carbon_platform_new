import { DatePipe, JsonPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, effect, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { Observable, of, switchMap } from 'rxjs';

import { NotifyService } from '../core/notify.service';
import { label } from '../farmer/farmer.models';
import { askReason } from '../shared/reason-dialog';
import { runAction } from '../shared/run-action';
import { StatusBadge } from '../shared/status-badge';
import { RegistryApi } from './registry.api';
import {
  Account, CALCULATED_LABEL, ISSUED_LABEL, Issuance, OrgRef, PeriodRegistry, Registration, SubmissionDetail, VERIFIED_LABEL, isOpen, issuanceBadge,
  serialText, submissionBadge,
} from './registry.models';

interface BatchDraft { vintage: string; quantity: number | null; serialStart: string; serialEnd: string }

/** Registry workflow of one monitoring period (period records are authoritative). Every manual record needs the registry's reference and a
 *  PDF; issuances are confirmed by a second person. Calculated, VVB-stated and registry-issued quantities are never interchangeable. */
@Component({
  selector: 'app-registry-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, JsonPipe, FormsModule, MatButtonModule, MatFormFieldModule, MatInputModule, MatSelectModule, StatusBadge],
  template: `
    <div class="tab-body" data-testid="registry-panel">
      @if (!periodId()) { <p class="muted">Select a monitoring period.</p> }
      @if (v(); as v) {
        @if (v.demo_note) { <p class="note warn" data-testid="demo-registry">{{ v.demo_note }}</p> }
        <div class="cards">
          <div class="card calc" data-testid="qty-calculated"><div class="small">{{ calculatedLabel }}</div>
            <strong>{{ v.calculated.value ?? '—' }} {{ v.calculated.unit }}</strong></div>
          <div class="card verified" data-testid="qty-verified"><div class="small">{{ verifiedLabel }}</div>
            <strong>{{ v.verified.value ?? '—' }} {{ v.verified.unit }}</strong><div class="small muted">{{ v.verified.note }}</div></div>
          <div class="card issued" data-testid="qty-issued"><div class="small">{{ issuedLabel }}</div>
            @for (q of v.issued; track $index) { <strong>{{ q.value ?? '—' }} {{ q.unit }}</strong> }
            <div class="small muted">{{ v.issued[0].note }}</div>
            @if (v.remaining; as r) { <div class="small">{{ r.label }}: {{ r.value }} {{ r.unit }} — {{ r.note }}</div> }</div>
        </div>
        <p class="small">Registry status of period #{{ v.period_number }}: <app-status-badge [status]="iBadge(v.registry_status)" [text]="label(v.registry_status)" />
          · project status {{ label(v.project_status) }} (aggregate; periods are authoritative)</p>
        @for (e of v.eligibility; track $index) {
          @if (e.blockers.length || e.warnings.length) {
            <ul class="small blockers" [attr.data-testid]="'registry-blockers'">
              @for (b of e.blockers; track $index) { <li><strong>{{ b.code }}</strong> — {{ b.message }} {{ e.account_label ? '(' + e.account_label + ')' : '' }}</li> }
              @for (w of e.warnings; track $index) { <li class="warn-text">{{ w.code }} — {{ w.message }}</li> }
            </ul>
          }
        }

        <h3>Registry accounts and project registrations</h3>
        @for (a of accounts(); track a.id) {
          <div class="small" [attr.data-account]="a.label">{{ a.label }} · {{ a.registry_name }} · account {{ a.external_account_id }} · adapter {{ a.adapter_code }}
            · {{ a.credit_unit ? '1 ' + a.credit_unit + ' = 1 ' + a.verified_unit_equivalent : 'unit equivalence not configured' }}
            · checklist {{ a.document_checklist ? a.document_checklist.length + ' item(s)' : 'not configured' }}
            <app-status-badge [status]="a.status === 'ACTIVE' ? 'ACTIVE' : 'ARCHIVED'" [text]="label(a.status)" /></div>
        } @empty { <p class="small muted">No registry account recorded for this organization.</p> }
        @for (r of v.registrations; track r.id) {
          <div class="box small" [attr.data-registration]="r.registration_code"><strong>{{ r.registration_code }}</strong> · {{ r.registry_name }}
            <app-status-badge [status]="iBadge(r.status)" [text]="label(r.status)" />
            {{ r.external_project_id ? '· registry project ' + r.external_project_id : '' }} {{ r.registered_on ? '(' + r.registered_on + ')' : '' }}
            <span class="muted">{{ r.label }}</span>
            @if (v.can_manage && r.status === 'PENDING') {
              <div class="row">
                <mat-form-field subscriptSizing="dynamic"><mat-label>Registry project ID</mat-label><input matInput [(ngModel)]="text['ext-' + r.id]" /></mat-form-field>
                <mat-form-field subscriptSizing="dynamic"><mat-label>Registered on</mat-label><input matInput type="date" [(ngModel)]="text['date-' + r.id]" /></mat-form-field>
                <label class="small">Registry evidence (PDF) <input type="file" accept="application/pdf" (change)="pick('reg-' + r.id, $event)" /></label>
                <button mat-flat-button type="button" [disabled]="busy() || !text['ext-' + r.id] || !files['reg-' + r.id]" (click)="registered(r)">Record registered</button>
                <button mat-button type="button" [disabled]="busy() || !files['reg-' + r.id]" (click)="registrationRejected(r)">Record rejected</button>
              </div>
            }
          </div>
        }
        @if (v.can_manage) {
          <details class="small"><summary>Record a registry account / registration</summary>
            <div class="row">
              <mat-form-field subscriptSizing="dynamic"><mat-label>Registry</mat-label>
                <mat-select [(ngModel)]="newAccount.registry">@for (o of registries(); track o.id) { <mat-option [value]="o.id">{{ o.name }}</mat-option> }</mat-select></mat-form-field>
              <mat-form-field subscriptSizing="dynamic"><mat-label>Registry account ID</mat-label><input matInput [(ngModel)]="newAccount.external" /></mat-form-field>
              <mat-form-field subscriptSizing="dynamic"><mat-label>Label</mat-label><input matInput [(ngModel)]="newAccount.label" /></mat-form-field>
              <mat-form-field subscriptSizing="dynamic"><mat-label>Registry credit unit</mat-label><input matInput [(ngModel)]="newAccount.creditUnit" /></mat-form-field>
              <mat-form-field subscriptSizing="dynamic"><mat-label>= 1 verified unit (explicit)</mat-label><input matInput [(ngModel)]="newAccount.verifiedUnit" /></mat-form-field>
              <button mat-stroked-button type="button" [disabled]="busy() || !newAccount.registry || !newAccount.external || newAccount.label.length < 2"
                      (click)="createAccount(v)">Record account</button>
            </div>
            <mat-form-field class="full" subscriptSizing="dynamic"><mat-label>Document checklist (JSON, from the registry's requirements — optional)</mat-label>
              <textarea matInput rows="2" [(ngModel)]="newAccount.checklist"></textarea></mat-form-field>
            <div class="row">
              <mat-form-field subscriptSizing="dynamic"><mat-label>Account for registration</mat-label>
                <mat-select [(ngModel)]="registrationAccount">@for (a of activeAccounts(); track a.id) { <mat-option [value]="a.id">{{ a.label }}</mat-option> }</mat-select></mat-form-field>
              <button mat-stroked-button type="button" [disabled]="busy() || !registrationAccount" (click)="createRegistration(v)">Start registration record</button>
            </div>
          </details>
        }

        <h3>Registry submissions</h3>
        @for (s of v.submissions; track s.id) {
          <div class="sub" [attr.data-rsub]="s.submission_code"><a href="" (click)="$event.preventDefault(); open(s.id)">{{ s.submission_code }}</a>
            <app-status-badge [status]="sBadge(s.status)" [text]="label(s.status)" /> · {{ s.registry_name }} · decision {{ s.decision_code }}
            {{ s.external_submission_id ? '· registry ref ' + s.external_submission_id : '' }}
            @if (s.source_superseded) { <app-status-badge status="WARNING" text="Source superseded" /> }</div>
        } @empty { <p class="small muted" data-testid="no-registry-submission">No registry submission for this period.</p> }
        @if (v.can_manage && !hasOpen(v)) {
          <div class="row">
            <mat-form-field subscriptSizing="dynamic"><mat-label>Registry account</mat-label>
              <mat-select [(ngModel)]="submissionAccount" data-testid="rsub-account">@for (a of activeAccounts(); track a.id) { <mat-option [value]="a.id">{{ a.label }}</mat-option> }</mat-select></mat-form-field>
            <button mat-flat-button type="button" [disabled]="busy() || !submissionAccount" (click)="createSubmission(v)" data-testid="create-rsub">Prepare registry submission</button>
          </div>
        }

        @if (detail(); as d) {
          <div class="box" data-testid="rsub-detail">
            <h4>{{ d.submission_code }} <app-status-badge [status]="sBadge(d.status)" [text]="label(d.status)" /></h4>
            <div class="small">Snapshot SHA-256 <span class="mono">{{ d.snapshot_sha256 ?? 'not frozen' }}</span> · idempotency key <span class="mono">{{ d.idempotency_key ?? '—' }}</span>
              {{ d.response_reason ? '· ' + d.response_reason : '' }} {{ d.closed_reason ? '· ' + d.closed_reason : '' }}</div>
            @if (d.source_superseded) { <p class="note warn small">The VVB decision behind this submission is superseded. Nothing was changed automatically; any correction needs a controlled registry action.</p> }
            @if (d.checklist) {
              <div class="small">Checklist: @for (c of d.checklist; track c.code) { <span [class.ok]="c.satisfied">{{ c.code }} {{ c.satisfied ? '✓' : '✗' }}</span>{{ $last ? '' : ' · ' }} }</div>
            }
            @if (v.can_manage) {
              <div class="row">
                @if (d.status === 'DRAFT') {
                  <label class="small">Document sent to the registry (PDF) <input type="file" accept="application/pdf" (change)="pick('send', $event)" /></label>
                  <mat-form-field subscriptSizing="dynamic"><mat-label>Checklist item</mat-label>
                    <mat-select [(ngModel)]="checklistItem">@for (c of d.checklist ?? []; track c.code) { <mat-option [value]="c.code">{{ c.code }}</mat-option> }</mat-select></mat-form-field>
                  <button mat-stroked-button type="button" [disabled]="busy() || !files['send']" (click)="attach(d, 'REGISTRY_SUBMISSION', 'send')">Attach</button>
                  <button mat-flat-button type="button" [disabled]="busy()" (click)="act(api.freeze(d.id), 'Snapshot frozen.')" data-testid="freeze-rsub">Freeze snapshot</button>
                }
                @if (d.status === 'FROZEN') {
                  <mat-form-field subscriptSizing="dynamic"><mat-label>Registry submission reference</mat-label><input matInput [(ngModel)]="text['subref']" /></mat-form-field>
                  <label class="small">Registry receipt (PDF) <input type="file" accept="application/pdf" (change)="pick('receipt', $event)" /></label>
                  <button mat-flat-button type="button" [disabled]="busy() || !text['subref'] || !files['receipt']" (click)="recordSubmitted(d)">Record submitted</button>
                  <button mat-button type="button" (click)="act(api.submit(d.id), 'Sent to the registry.')">Send via registry API</button>
                }
                @if (d.status === 'DRAFT' || d.status === 'FROZEN') { <button mat-button type="button" (click)="cancel(d)">Cancel</button> }
                @if (d.status === 'SUBMITTED') {
                  <mat-form-field subscriptSizing="dynamic"><mat-label>Outcome</mat-label>
                    <mat-select [(ngModel)]="outcome"><mat-option value="ACCEPTED">Accepted</mat-option><mat-option value="REJECTED">Rejected</mat-option></mat-select></mat-form-field>
                  <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Registry reason / note</mat-label><input matInput [(ngModel)]="text['reason']" /></mat-form-field>
                  <label class="small">Registry response (PDF) <input type="file" accept="application/pdf" (change)="pick('response', $event)" /></label>
                  <button mat-flat-button type="button" [disabled]="busy() || !files['response'] || (outcome === 'REJECTED' && !text['reason'])" (click)="recordResponse(d)">Record response</button>
                  <button mat-button type="button" [disabled]="busy() || !text['reason']" (click)="recordQuery(d)">Record registry query</button>
                }
                @if (d.status === 'SUBMISSION_UNCONFIRMED' || d.status === 'SUBMITTED' || d.status === 'ACCEPTED') {
                  <button mat-button type="button" (click)="act(api.reconcile(d.id, null), 'Reconciled with the registry.')">Reconcile (API)</button>
                }
              </div>
              @if (d.status === 'ACCEPTED') {
                <h4>Record a registry issuance</h4>
                <div class="row">
                  <mat-form-field subscriptSizing="dynamic"><mat-label>Registry issuance ID</mat-label><input matInput [(ngModel)]="iss.external" data-testid="iss-ext" /></mat-form-field>
                  <mat-form-field subscriptSizing="dynamic"><mat-label>Issuance date (registry)</mat-label><input matInput type="date" [(ngModel)]="iss.date" /></mat-form-field>
                  <mat-form-field subscriptSizing="dynamic"><mat-label>Unit (registry)</mat-label><input matInput [(ngModel)]="iss.unit" /></mat-form-field>
                  <label class="small">Issuance statement (PDF) <input type="file" accept="application/pdf" (change)="pick('statement', $event)" /></label>
                </div>
                @for (b of iss.batches; track $index) {
                  <div class="row">
                    <mat-form-field subscriptSizing="dynamic"><mat-label>Vintage (registry)</mat-label><input matInput [(ngModel)]="b.vintage" /></mat-form-field>
                    <mat-form-field subscriptSizing="dynamic"><mat-label>Whole credits</mat-label><input matInput type="number" min="1" step="1" [(ngModel)]="b.quantity" /></mat-form-field>
                    <mat-form-field subscriptSizing="dynamic"><mat-label>Serial start (as supplied)</mat-label><input matInput [(ngModel)]="b.serialStart" /></mat-form-field>
                    <mat-form-field subscriptSizing="dynamic"><mat-label>Serial end (as supplied)</mat-label><input matInput [(ngModel)]="b.serialEnd" /></mat-form-field>
                  </div>
                }
                <div class="row"><button mat-button type="button" (click)="addBatch()">Add batch</button>
                  <span class="small">Total {{ issuanceTotal() }} — entered from the registry statement, never from the calculated or VVB-stated quantity.</span>
                  <button mat-flat-button type="button" [disabled]="busy() || !canRecordIssuance()" (click)="recordIssuance(d)" data-testid="record-issuance">Record issuance</button></div>
              }
            }
            <h4>Issuances</h4>
            @for (i of d.issuances; track i.id) {
              <div class="iss" [attr.data-issuance]="i.issuance_code"><strong>{{ i.issuance_code }}</strong> · registry {{ i.external_issuance_id }} · {{ i.issuance_date }}
                · <strong>{{ i.quantity }} {{ i.unit }}</strong> ({{ issuedLabel }}) <app-status-badge [status]="iBadge(i.status)" [text]="label(i.status)" />
                <span class="small muted"> recorded by {{ i.recorded_by_name }}{{ i.confirmed_by_name ? ', confirmed by ' + i.confirmed_by_name : '' }}
                  {{ i.corrects_issuance_id ? '· corrects an earlier issuance' : '' }}</span>
                @for (b of i.batches; track b.id) {
                  <div class="small batch">{{ b.batch_code }} · vintage {{ b.vintage }} · {{ b.quantity }} {{ b.unit }} <app-status-badge [status]="iBadge(b.status)" [text]="label(b.status)" />
                    @for (r of b.serial_ranges; track r.seq) { <div class="mono">{{ serial(r) }} ({{ r.quantity }})</div> }</div>
                }
                <div class="row">
                  @if (i.can_confirm) { <button mat-flat-button type="button" (click)="confirm(i)" data-testid="confirm-issuance">Confirm (second person)</button> }
                  @if (v.can_manage && i.status === 'RECORDED') { <button mat-button type="button" (click)="voidIssuance(i)">Void entry</button> }
                </div>
              </div>
            } @empty { <p class="small muted">No issuance recorded.</p> }
            <details><summary class="small">Registry events ({{ d.events.length }})</summary>
              @for (e of d.events; track e.id) {
                <div class="small">{{ e.occurred_at | date: 'short' }} · {{ e.event_type }} · {{ e.outcome }} {{ e.external_ref ? '· ' + e.external_ref : '' }} · {{ e.actor_name }}
                  {{ e.note ? '— ' + e.note : '' }}</div>
              }
            </details>
            <details><summary class="small">Documents ({{ d.documents.length }})</summary>
              @for (x of d.documents; track x.document_id) { <div class="small">{{ x.category }} · {{ x.title }} {{ x.checklist_item ? '(' + x.checklist_item + ')' : '' }} · <span class="mono">{{ x.sha256 }}</span></div> }
            </details>
            @if (d.snapshot) { <details><summary class="small">Frozen snapshot (registry-submission-v1)</summary><pre class="mono">{{ d.snapshot | json }}</pre></details> }
          </div>
        }
      }
    </div>
  `,
  styles: `h3 { margin: 14px 0 6px; font: var(--mat-sys-title-small); } h4 { margin: 10px 0 4px; }
    .cards { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 8px; }
    .card { flex: 1 1 200px; border-radius: 8px; padding: 8px 12px; border: 1px solid var(--mat-sys-outline-variant); }
    .card.calc { background: #f4f4f4; } .card.verified { background: #e8f0fb; } .card.issued { background: #e3f4e4; }
    .box { border: 1px solid var(--mat-sys-outline-variant); border-radius: 8px; padding: 8px 10px; margin: 6px 0; }
    .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-top: 6px; } .wide { min-width: 220px; flex: 1; } .full { width: 100%; }
    .mono { font-family: monospace; font-size: 11px; word-break: break-all; } pre { max-height: 320px; overflow: auto; white-space: pre-wrap; }
    .blockers { padding-left: 20px; } .warn-text { color: #7a5200; } .ok { color: var(--mat-sys-primary); } .batch { margin-left: 14px; }
    .iss { border-top: 1px solid var(--mat-sys-outline-variant); padding: 4px 0; } .sub { margin: 2px 0; }`,
})
export class RegistryPanel {
  readonly projectId = input.required<string>();
  readonly periodId = input<string | null>(null);
  protected readonly api = inject(RegistryApi);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotifyService);
  protected readonly label = label;
  protected readonly sBadge = submissionBadge;
  protected readonly iBadge = issuanceBadge;
  protected readonly serial = serialText;
  protected readonly calculatedLabel = CALCULATED_LABEL;
  protected readonly verifiedLabel = VERIFIED_LABEL;
  protected readonly issuedLabel = ISSUED_LABEL;
  protected readonly v = signal<PeriodRegistry | null>(null);
  protected readonly accounts = signal<Account[]>([]);
  protected readonly registries = signal<OrgRef[]>([]);
  protected readonly detail = signal<SubmissionDetail | null>(null);
  protected readonly busy = signal(false);
  protected text: Record<string, string | undefined> = {};
  protected files: Record<string, File | undefined> = {};
  protected newAccount = { registry: '', external: '', label: '', creditUnit: '', verifiedUnit: '', checklist: '' };
  protected registrationAccount = '';
  protected submissionAccount = '';
  protected checklistItem = '';
  protected outcome: 'ACCEPTED' | 'REJECTED' = 'ACCEPTED';
  protected iss: { external: string; date: string; unit: string; batches: BatchDraft[] } = { external: '', date: '', unit: '', batches: [this.batch()] };

  constructor() {
    effect(() => {
      const id = this.periodId();
      this.v.set(null);
      this.detail.set(null);
      if (id) this.load(id);
    });
  }

  private batch(): BatchDraft {
    return { vintage: '', quantity: null, serialStart: '', serialEnd: '' };
  }

  private load(periodId: string): void {
    this.api.period(this.projectId(), periodId).subscribe((v) => {
      this.v.set(v);
      this.api.accounts(v.organization_id).subscribe((a) => this.accounts.set(a));
      if (v.can_manage && !this.registries().length) this.api.registries(v.environment).subscribe((r) => this.registries.set(r));
      const open = v.submissions.find((s) => isOpen(s.status)) ?? v.submissions.at(-1);
      if (open && !this.detail()) this.open(open.id);
    });
  }

  reload(): void {
    const id = this.periodId();
    if (id) this.load(id);
    const d = this.detail();
    if (d) this.open(d.id);
  }

  protected activeAccounts(): Account[] {
    return this.accounts().filter((a) => a.status === 'ACTIVE');
  }

  protected hasOpen(v: PeriodRegistry): boolean {
    return v.submissions.some((s) => isOpen(s.status));
  }

  protected open(id: string): void {
    this.api.submission(id).subscribe((d) => this.detail.set(d));
  }

  protected pick(key: string, ev: Event): void {
    this.files[key] = (ev.target as HTMLInputElement).files?.[0];
  }

  protected act(obs: Observable<unknown>, message: string): void {
    runAction(obs, this.busy, this.notify, message, () => this.reload());
  }

  /** Upload the picked PDF to the submission first, then run the record call with its document id. */
  private withDoc(submissionId: string, key: string, category: string, call: (documentId: string) => Observable<unknown>): Observable<unknown> {
    const file = this.files[key];
    if (!file) return of(null);
    return this.api.submissionDoc(submissionId, file, category).pipe(switchMap((d) => call(d.document_id)));
  }

  protected createAccount(v: PeriodRegistry): void {
    const a = this.newAccount;
    let checklist: unknown = null;
    if (a.checklist.trim()) {
      try { checklist = JSON.parse(a.checklist); } catch { this.notify.error(new Error('The checklist must be JSON.')); return; }
    }
    this.act(this.api.createAccount({ organization_id: v.organization_id, registry_organization_id: a.registry, external_account_id: a.external.trim(),
      label: a.label.trim(), credit_unit: a.creditUnit.trim() || null, verified_unit_equivalent: a.verifiedUnit.trim() || null, document_checklist: checklist }),
    'Registry account recorded.');
  }

  protected createRegistration(v: PeriodRegistry): void {
    this.act(this.api.createRegistration(v.project_id, this.registrationAccount), 'Registration record started (PENDING).');
  }

  protected registered(r: Registration): void {
    const file = this.files['reg-' + r.id];
    if (!file) return;
    this.act(this.api.registrationDoc(r.id, file).pipe(switchMap((d) => this.api.recordRegistered(r.id, {
      external_project_id: (this.text['ext-' + r.id] ?? '').trim(), registered_on: this.text['date-' + r.id] || null, document_id: d.document_id }))),
    'Registry registration recorded (external fact).');
  }

  protected registrationRejected(r: Registration): void {
    const file = this.files['reg-' + r.id];
    if (!file) return;
    askReason(this.dialog, { title: `Registry rejected ${r.registration_code}?`, confirmLabel: 'Record rejection', danger: true }).subscribe((x) => {
      if (x) this.act(this.api.registrationDoc(r.id, file).pipe(switchMap((d) => this.api.recordRegistrationRejected(r.id, { reason: x.reason, document_id: d.document_id }))),
        'Registry rejection recorded.');
    });
  }

  protected createSubmission(v: PeriodRegistry): void {
    runAction(this.api.createSubmission(v.project_id, { monitoring_period_id: v.monitoring_period_id, registry_account_id: this.submissionAccount }),
      this.busy, this.notify, 'Registry submission prepared (DRAFT).', (s) => { this.detail.set(null); this.reload(); this.open(s.id); });
  }

  protected attach(d: SubmissionDetail, category: string, key: string): void {
    const file = this.files[key];
    if (!file) return;
    this.act(this.api.submissionDoc(d.id, file, category, this.checklistItem || null), 'Document attached.');
    this.files[key] = undefined;
  }

  protected recordSubmitted(d: SubmissionDetail): void {
    this.act(this.withDoc(d.id, 'receipt', 'REGISTRY_RESPONSE', (doc) => this.api.recordSubmitted(d.id, {
      external_submission_id: (this.text['subref'] ?? '').trim(), document_id: doc })), 'Registry submission reference recorded.');
  }

  protected recordResponse(d: SubmissionDetail): void {
    this.act(this.withDoc(d.id, 'response', 'REGISTRY_RESPONSE', (doc) => this.api.recordResponse(d.id, {
      outcome: this.outcome, document_id: doc, reason: this.text['reason']?.trim() || null })), `Registry response recorded (${this.outcome}).`);
  }

  protected recordQuery(d: SubmissionDetail): void {
    this.act(this.api.recordQuery(d.id, { note: (this.text['reason'] ?? '').trim() }), 'Registry query recorded.');
  }

  protected cancel(d: SubmissionDetail): void {
    askReason(this.dialog, { title: `Cancel ${d.submission_code}?`, confirmLabel: 'Cancel submission', danger: true })
      .subscribe((x) => { if (x) this.act(this.api.cancel(d.id, x.reason), 'Submission cancelled.'); });
  }

  protected addBatch(): void {
    this.iss.batches = [...this.iss.batches, this.batch()];
  }

  protected issuanceTotal(): number {
    return this.iss.batches.reduce((t, b) => t + (Number(b.quantity) || 0), 0);
  }

  protected canRecordIssuance(): boolean {
    const i = this.iss;
    return !!i.external.trim() && !!i.date && !!i.unit.trim() && !!this.files['statement']
      && i.batches.every((b) => !!b.vintage.trim() && Number.isInteger(Number(b.quantity)) && Number(b.quantity) > 0
        && (!b.serialStart) === (!b.serialEnd));
  }

  protected recordIssuance(d: SubmissionDetail): void {
    const i = this.iss;
    const batches = i.batches.map((b) => ({ vintage: b.vintage.trim(), quantity: Number(b.quantity),
      serial_ranges: [{ serial_start: b.serialStart || null, serial_end: b.serialEnd || null, quantity: Number(b.quantity) }] }));
    this.act(this.withDoc(d.id, 'statement', 'ISSUANCE_STATEMENT', (doc) => this.api.recordIssuance(d.id, {
      external_issuance_id: i.external.trim(), issuance_date: i.date, quantity: this.issuanceTotal(), unit: i.unit.trim(), source: 'MANUAL',
      document_id: doc, batches })), 'Issuance recorded — awaiting confirmation by a second person.');
  }

  protected confirm(i: Issuance): void {
    askReason(this.dialog, { title: `Confirm ${i.issuance_code}?`, confirmLabel: 'Confirm',
      message: 'Confirm only after checking the quantity, vintage and serial numbers against the registry statement. You cannot confirm your own entry.' })
      .subscribe((x) => { if (x) this.act(this.api.confirm(i.id, x.reason), 'Issuance confirmed.'); });
  }

  protected voidIssuance(i: Issuance): void {
    askReason(this.dialog, { title: `Void ${i.issuance_code}?`, confirmLabel: 'Void', danger: true })
      .subscribe((x) => { if (x) this.act(this.api.void(i.id, x.reason), 'Issuance entry voided.'); });
  }
}
