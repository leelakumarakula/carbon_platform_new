import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, effect, inject, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { Observable, map, of, switchMap } from 'rxjs';

import { NotifyService } from '../core/notify.service';
import { label } from '../farmer/farmer.models';
import { askReason } from '../shared/reason-dialog';
import { runAction } from '../shared/run-action';
import { StatusBadge } from '../shared/status-badge';
import { VerificationApi, VvbApi } from './verification.api';
import { CorrectiveAction, TARGET_TYPES, VFINDING_CATEGORIES, VFinding, findingBadge } from './verification.models';

/** VVB findings and corrective actions of one submission. The VVB raises, closes, returns, reopens and reviews corrective actions;
 *  the project only responds (it never closes a VVB finding). */
@Component({
  selector: 'app-verification-findings',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, FormsModule, MatButtonModule, MatCheckboxModule, MatFormFieldModule, MatInputModule, MatSelectModule, StatusBadge],
  template: `
    @for (f of findings(); track f.id) {
      <div class="finding" [attr.data-vfinding]="f.finding_code">
        <div><strong>{{ f.finding_code }}</strong> · {{ f.category_label }} {{ f.blocking ? '· blocking' : '· non-blocking' }}
          <app-status-badge [status]="badge(f.status)" [text]="label(f.status)" /> — {{ f.title }}</div>
        <div class="small">{{ f.description }} · target {{ label(f.target_type) }}{{ f.target_ref ? ' ' + f.target_ref : '' }}
          · raised {{ f.raised_at | date: 'short' }} by {{ f.raised_by_name }}</div>
        @if (f.response_text) { <div class="small">Response ({{ f.responded_by_name }}): {{ f.response_text }}{{ f.response_document_id ? ' · evidence attached' : '' }}</div> }
        @if (f.closure_note) { <div class="small">Closed by {{ f.closed_by_name }}: {{ f.closure_note }}</div> }
        @if (canAct()) {
          <div class="row">
            @if (side() === 'PROJECT' && f.status === 'OPEN') {
              <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Response</mat-label>
                <input matInput [(ngModel)]="text[f.id]" [attr.data-testid]="'vresponse-' + f.finding_code" /></mat-form-field>
              <input type="file" accept="application/pdf" (change)="pick(f.id, $event)" aria-label="Evidence PDF" />
              <button mat-flat-button type="button" [disabled]="busy() || (text[f.id] ?? '').trim().length < 3" (click)="respond(f)"
                      data-testid="vrespond">Respond</button>
            }
            @if (side() === 'VVB') {
              @if (f.status === 'RESPONDED') {
                <button mat-flat-button type="button" (click)="withReason('Close', f)" data-testid="vclose">Close</button>
                <button mat-button type="button" (click)="withReason('Return', f)">Return response</button>
              }
              @if (f.status === 'CLOSED') { <button mat-button type="button" (click)="withReason('Reopen', f)">Reopen</button> }
              @if (f.status !== 'CLOSED') {
                <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Corrective action requested</mat-label>
                  <input matInput [(ngModel)]="text[f.id]" /></mat-form-field>
                <mat-form-field subscriptSizing="dynamic"><mat-label>Due date</mat-label><input matInput type="date" [(ngModel)]="due[f.id]" /></mat-form-field>
                <button mat-stroked-button type="button" [disabled]="busy() || (text[f.id] ?? '').trim().length < 3" (click)="requestCa(f)">Request</button>
              }
            }
          </div>
        }
        @for (c of f.corrective_actions; track c.id) {
          <div class="ca" [attr.data-ca]="c.action_code"><strong>{{ c.action_code }}</strong>
            <app-status-badge [status]="badge(c.status)" [text]="label(c.status)" />
            @if (c.overdue) { <app-status-badge status="FAILED" text="Overdue" /> }
            — {{ c.description }}{{ c.due_date ? ' · due ' + c.due_date : '' }}
            @if (c.response_text) { <div class="small">Response ({{ c.responded_by_name }}): {{ c.response_text }}</div> }
            @if (c.review_note) { <div class="small">Review ({{ c.reviewed_by_name }}): {{ c.review_note }}</div> }
            @if (canAct()) {
              <div class="row">
                @if (side() === 'PROJECT' && c.status === 'REQUESTED') {
                  <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Response</mat-label><input matInput [(ngModel)]="text[c.id]" /></mat-form-field>
                  <input type="file" accept="application/pdf" (change)="pick(c.id, $event)" aria-label="Evidence PDF" />
                  <button mat-flat-button type="button" [disabled]="busy() || (text[c.id] ?? '').trim().length < 3" (click)="respondCa(c)">Respond</button>
                }
                @if (side() === 'VVB' && c.status === 'RESPONDED') {
                  <button mat-flat-button type="button" (click)="caReason('Accept', c)">Accept</button>
                  <button mat-button type="button" (click)="caReason('Reject', c)">Reject (re-request)</button>
                }
                @if (side() === 'VVB' && (c.status === 'REQUESTED' || c.status === 'RESPONDED')) {
                  <button mat-button type="button" (click)="caReason('Cancel', c)">Cancel</button>
                }
              </div>
            }
          </div>
        }
        <details><summary class="small">History ({{ f.events.length }})</summary>
          @for (e of f.events; track e.seq) {
            <div class="small">{{ e.occurred_at | date: 'short' }} · {{ e.action }} · {{ e.actor_side }} {{ e.actor_name }} {{ e.note ? '— ' + e.note : '' }}</div>
          }
        </details>
      </div>
    } @empty { <p class="muted small" data-testid="no-vfindings">No VVB finding on this submission.</p> }
    @if (side() === 'VVB' && canAct()) {
      <h4>Raise a finding</h4>
      <div class="row">
        <mat-form-field subscriptSizing="dynamic"><mat-label>Category</mat-label>
          <mat-select [(ngModel)]="category" data-testid="vfinding-category">
            @for (c of categories; track c.code) { <mat-option [value]="c.code">{{ c.label }}</mat-option> }</mat-select></mat-form-field>
        <mat-checkbox [(ngModel)]="blocking">Blocking</mat-checkbox>
        <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Title</mat-label><input matInput [(ngModel)]="title" data-testid="vfinding-title" /></mat-form-field>
      </div>
      <div class="row">
        <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Description</mat-label>
          <input matInput [(ngModel)]="description" data-testid="vfinding-description" /></mat-form-field>
        <mat-form-field subscriptSizing="dynamic"><mat-label>Target</mat-label>
          <mat-select [(ngModel)]="targetType">@for (t of targets; track t) { <mat-option [value]="t">{{ label(t) }}</mat-option> }</mat-select></mat-form-field>
        <mat-form-field subscriptSizing="dynamic"><mat-label>Target reference (id / #)</mat-label><input matInput [(ngModel)]="targetRef" /></mat-form-field>
        <button mat-flat-button type="button" [disabled]="busy() || !category || title.trim().length < 3 || description.trim().length < 3"
                (click)="raise()" data-testid="vraise">Raise finding</button>
      </div>
    }
  `,
  styles: `.finding { border-bottom: 1px solid var(--mat-sys-outline-variant); padding: 6px 0; } .ca { margin: 4px 0 4px 18px; font-size: 13px; }
    .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-top: 6px; } .wide { min-width: 220px; flex: 1; } h4 { margin: 12px 0 4px; }`,
})
export class VerificationFindings {
  readonly submissionId = input.required<string>();
  readonly side = input.required<'PROJECT' | 'VVB'>();
  readonly canAct = input(false);
  readonly changed = output<void>();
  private readonly projectApi = inject(VerificationApi);
  private readonly vvbApi = inject(VvbApi);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotifyService);
  protected readonly label = label;
  protected readonly badge = findingBadge;
  protected readonly categories = VFINDING_CATEGORIES;
  protected readonly targets = TARGET_TYPES;
  protected readonly findings = signal<VFinding[]>([]);
  protected readonly busy = signal(false);
  protected text: Record<string, string | undefined> = {};
  protected due: Record<string, string | undefined> = {};
  private files: Record<string, File | undefined> = {};
  protected category = '';
  protected blocking = true;
  protected title = '';
  protected description = '';
  protected targetType = 'SUBMISSION';
  protected targetRef = '';

  constructor() {
    effect(() => {
      const id = this.submissionId();
      this.findings.set([]);
      this.load(id);
    });
  }

  private load(id = this.submissionId()): void {
    const obs = this.side() === 'VVB' ? this.vvbApi.findings(id) : this.projectApi.findings(id);
    obs.subscribe((f) => this.findings.set(f));
  }

  private done(): void {
    this.load();
    this.changed.emit();
  }

  protected pick(id: string, ev: Event): void {
    this.files[id] = (ev.target as HTMLInputElement).files?.[0];
  }

  /** Optional PDF evidence is uploaded first (attached to the submission), then referenced by the response. */
  private withEvidence<T>(id: string, call: (documentId: string | null) => Observable<T>): Observable<T> {
    const file = this.files[id];
    const upload: Observable<string | null> = file ? this.projectApi.evidence(this.submissionId(), file).pipe(map((d) => d.document_id)) : of(null);
    return upload.pipe(switchMap((documentId) => call(documentId)));
  }

  protected respond(f: VFinding): void {
    const text = (this.text[f.id] ?? '').trim();
    runAction(this.withEvidence(f.id, (doc) => this.projectApi.respond(f.id, text, doc)), this.busy, this.notify, 'Response recorded.', () => {
      this.text[f.id] = this.files[f.id] = undefined;
      this.done();
    });
  }

  protected respondCa(c: CorrectiveAction): void {
    const text = (this.text[c.id] ?? '').trim();
    runAction(this.withEvidence(c.id, (doc) => this.projectApi.respondCa(c.id, text, doc)), this.busy, this.notify, 'Response recorded.', () => {
      this.text[c.id] = this.files[c.id] = undefined;
      this.done();
    });
  }

  protected raise(): void {
    const body = { category: this.category, blocking: this.blocking, title: this.title.trim(), description: this.description.trim(),
      target_type: this.targetType, target_ref: this.targetRef.trim() || null };
    runAction(this.vvbApi.raise(this.submissionId(), body), this.busy, this.notify, 'Finding raised.', () => {
      this.title = this.description = this.targetRef = '';
      this.done();
    });
  }

  protected requestCa(f: VFinding): void {
    const body = { description: (this.text[f.id] ?? '').trim(), due_date: this.due[f.id] || null };
    runAction(this.vvbApi.requestCa(f.id, body), this.busy, this.notify, 'Corrective action requested.', () => {
      this.text[f.id] = this.due[f.id] = undefined;
      this.done();
    });
  }

  protected withReason(what: 'Close' | 'Return' | 'Reopen', f: VFinding): void {
    const call: Record<typeof what, (id: string, text: string) => Observable<VFinding>> = {
      Close: this.vvbApi.close, Return: this.vvbApi.returnResponse, Reopen: this.vvbApi.reopen };
    askReason(this.dialog, { title: `${what} ${f.finding_code}?`, confirmLabel: what }).subscribe((x) => {
      if (x) runAction(call[what](f.id, x.reason), this.busy, this.notify, `${what}: done.`, () => this.done());
    });
  }

  protected caReason(what: 'Accept' | 'Reject' | 'Cancel', c: CorrectiveAction): void {
    const call: Record<typeof what, (id: string, text: string) => Observable<CorrectiveAction>> = {
      Accept: this.vvbApi.acceptCa, Reject: this.vvbApi.rejectCa, Cancel: this.vvbApi.cancelCa };
    askReason(this.dialog, { title: `${what} ${c.action_code}?`, confirmLabel: what, danger: what === 'Cancel' }).subscribe((x) => {
      if (x) runAction(call[what](c.id, x.reason), this.busy, this.notify, `${what}: done.`, () => this.done());
    });
  }
}
