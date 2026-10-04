import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatDialog } from '@angular/material/dialog';
import { MatTabsModule } from '@angular/material/tabs';
import { RouterLink } from '@angular/router';

import { AuthService } from '../core/auth/auth.service';
import { P } from '../core/auth/permissions';
import { NotifyService } from '../core/notify.service';
import { label } from '../farmer/farmer.models';
import { PageHeader } from '../shared/page-header';
import { askReason } from '../shared/reason-dialog';
import { runAction } from '../shared/run-action';
import { StatusBadge } from '../shared/status-badge';
import { LaboratoryApi } from './lab.api';
import { EngagementLabView, LabDashboardCounts, ResultLabView, SampleLabView, ShipmentLabView, TestLabView, labBadge, resultValue } from './lab.models';

interface ReceiptDraft { accepted: boolean; condition: string; seal: string; reason: string }

/** Laboratory workspace (restricted, allow-listed data only — no farmer, farm or GPS information). */
@Component({
  selector: 'app-laboratory-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, FormsModule, RouterLink, MatButtonModule, MatCheckboxModule, MatTabsModule, PageHeader, StatusBadge],
  template: `
    <app-page-header title="Laboratory" subtitle="Engagements, incoming samples, tests and laboratory QA" />
    @if (counts(); as c) {
      <div class="stats">
        <div class="stat"><span class="n">{{ c.engagements_pending }}</span>engagement requests</div>
        <div class="stat"><span class="n">{{ c.shipments_incoming }}</span>incoming shipments</div>
        <div class="stat"><span class="n">{{ c.samples_to_register }}</span>to register</div>
        <div class="stat"><span class="n">{{ c.tests_open }}</span>open tests</div>
        <div class="stat"><span class="n">{{ c.results_awaiting_qa }}</span>awaiting QA</div>
      </div>
    }
    <mat-tab-group animationDuration="0ms" mat-stretch-tabs="false">
      <mat-tab label="Engagements"><div class="tab-body">
        @for (e of engagements(); track e.id) {
          <div class="line"><div class="grow"><strong>{{ e.project_code }}</strong> · {{ e.project_org_name }} · {{ e.methodology_label }}
            <app-status-badge [status]="badge(e.status)" [text]="label(e.status)" />
            <div class="small">Scope: @for (r of e.rules; track r.rule_id) { {{ r.rule_code }} {{ r.parameter }}{{ r.unit ? ' (' + r.unit + ')' : '' }}; }</div></div>
            @if (e.can_accept) { <button mat-flat-button type="button" [disabled]="busy()" (click)="accept(e)" data-testid="accept-engagement">Accept</button> }
            @if (e.can_end) { <button mat-button type="button" (click)="end(e)">End</button> }
          </div>
        } @empty { <p class="muted">No engagement.</p> }
      </div></mat-tab>
      <mat-tab label="Incoming"><div class="tab-body">
        @for (sh of inbox(); track sh.id) {
          <div class="ship">
            <div class="line"><div class="grow"><strong>{{ sh.shipment_code }}</strong> · {{ sh.project_code }} · {{ sh.project_org_name }}
              <app-status-badge [status]="badge(sh.status)" [text]="label(sh.status)" />
              <span class="small muted"> dispatched {{ sh.dispatched_at | date: 'short' }}</span></div></div>
            @for (i of sh.items; track i.sample_id) {
              <div class="item"><span>{{ i.sample_code }} · seal {{ i.seal_number }}</span><app-status-badge [status]="badge(i.status)" [text]="label(i.status)" />
                @if (sh.can_receive && i.status === 'IN_SHIPMENT') {
                  <mat-checkbox [(ngModel)]="draft(i.sample_id, i.seal_number).accepted" [attr.data-testid]="'accept-' + i.sample_code">Accept</mat-checkbox>
                  <input placeholder="Seal observed" [(ngModel)]="draft(i.sample_id, i.seal_number).seal" />
                  <input placeholder="Condition" [(ngModel)]="draft(i.sample_id, i.seal_number).condition" />
                  @if (!draft(i.sample_id, i.seal_number).accepted) { <input placeholder="Rejection reason" [(ngModel)]="draft(i.sample_id, i.seal_number).reason" /> }
                }
              </div>
            }
            @if (sh.can_receive && sh.status === 'DISPATCHED') {
              <button mat-flat-button type="button" [disabled]="busy()" (click)="receive(sh)" data-testid="receive">Record receipt</button>
            }
          </div>
        } @empty { <p class="muted">No shipment addressed to your laboratory.</p> }
      </div></mat-tab>
      <mat-tab label="Samples"><div class="tab-body">
        <div class="table-wrap"><table class="table">
          <thead><tr><th>Sample</th><th>Project</th><th>Description</th><th>Depth</th><th>Status</th><th>Accession</th></tr></thead>
          <tbody>
            @for (s of samples(); track s.id) {
              <tr><td>{{ s.sample_code }}{{ s.parent_sample_code ? ' (split of ' + s.parent_sample_code + ')' : '' }}</td><td>{{ s.project_code }}</td>
                <td>{{ s.description }}</td><td>{{ s.depth_top_cm }}–{{ s.depth_bottom_cm }} cm</td>
                <td><app-status-badge [status]="badge(s.status)" [text]="label(s.status)" /></td>
                <td>@if (s.status === 'LAB_RECEIVED' && canReceive) {
                    <input placeholder="Accession no." [(ngModel)]="accessionNo[s.id]" [attr.data-testid]="'accession-' + s.sample_code" />
                    <button mat-button type="button" [disabled]="busy() || !accessionNo[s.id]" (click)="accession(s)">Register</button>
                  } @else { {{ s.accession_number ?? '—' }} }</td></tr>
            } @empty { <tr><td colspan="6" class="muted">No samples received.</td></tr> }
          </tbody>
        </table></div>
      </div></mat-tab>
      <mat-tab label="Worklist"><div class="tab-body">
        <div class="table-wrap"><table class="table">
          <thead><tr><th>Test</th><th>Sample</th><th>Parameter</th><th>Required unit</th><th>Status</th><th>Latest result</th></tr></thead>
          <tbody>
            @for (t of tests(); track t.id) {
              <tr><td><a [routerLink]="['/laboratory/tests', t.id]">{{ t.test_code }}</a>{{ t.retest_of_test_code ? ' (retest)' : '' }}</td><td>{{ t.sample_code }}</td>
                <td>{{ t.rule.rule_code }} · {{ t.rule.parameter }}</td><td>{{ t.required_unit ?? 'CONFIGURATION_REQUIRED' }}</td>
                <td><app-status-badge [status]="badge(t.status)" [text]="label(t.status)" /></td>
                <td>@if (t.results.length) { {{ value(t.results[t.results.length - 1]) }} · {{ label(t.results[t.results.length - 1].status) }} } @else { — }</td></tr>
            } @empty { <tr><td colspan="6" class="muted">No tests.</td></tr> }
          </tbody>
        </table></div>
      </div></mat-tab>
      <mat-tab label="QA"><div class="tab-body">
        @for (r of qaQueue(); track r.id) {
          <div class="line"><div class="grow">Result v{{ r.version }} · {{ value(r) }} · {{ r.analyst_name }}
            <app-status-badge [status]="badge(r.status)" [text]="label(r.status)" /></div>
            <a mat-button [routerLink]="['/laboratory/qa', r.id]" data-testid="open-qa">Review</a></div>
        } @empty { <p class="muted">Nothing waiting for laboratory QA.</p> }
      </div></mat-tab>
    </mat-tab-group>
  `,
  styles: `
    .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 14px; margin-bottom: 18px; }
    .stat { display: flex; flex-direction: column; gap: 4px; padding: 14px 18px; border-radius: var(--cp-radius); background: #fff;
      border: 1px solid var(--cp-line); border-top: 3px solid var(--cp-lime); font-size: 13px; color: var(--cp-ink-2); }
    .stat .n { font: 500 26px/1.15 var(--cp-font); color: var(--cp-forest); letter-spacing: -.01em; }
    .line { display: flex; gap: 8px; align-items: center; padding: 6px 0; border-bottom: 1px solid var(--mat-sys-outline-variant); flex-wrap: wrap; }
    .grow { flex: 1; min-width: 240px; } .ship { border: 1px solid var(--mat-sys-outline-variant); border-radius: 8px; padding: 8px 12px; margin-bottom: 10px; }
    .item { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; padding: 4px 0; } input { padding: 4px; }
  `,
})
export class LaboratoryPage implements OnInit {
  private readonly api = inject(LaboratoryApi);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotifyService);
  protected readonly canReceive = inject(AuthService).has(P.LAB_RECEIVE);
  protected readonly label = label;
  protected readonly badge = labBadge;
  protected readonly value = resultValue;
  protected readonly busy = signal(false);
  protected readonly counts = signal<LabDashboardCounts | null>(null);
  protected readonly engagements = signal<EngagementLabView[]>([]);
  protected readonly inbox = signal<ShipmentLabView[]>([]);
  protected readonly samples = signal<SampleLabView[]>([]);
  protected readonly tests = signal<TestLabView[]>([]);
  protected readonly qaQueue = signal<ResultLabView[]>([]);
  protected accessionNo: Record<string, string> = {};
  private readonly drafts = new Map<string, ReceiptDraft>();

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.api.dashboard().subscribe((c) => this.counts.set(c));
    this.api.engagements().subscribe((e) => this.engagements.set(e));
    this.api.inbox().subscribe((s) => this.inbox.set(s));
    this.api.samples().subscribe((s) => this.samples.set(s));
    this.api.tests().subscribe((t) => this.tests.set(t));
    this.api.qaQueue().subscribe((r) => this.qaQueue.set(r));
  }

  protected draft(sampleId: string, seal: string | null): ReceiptDraft {
    let d = this.drafts.get(sampleId);
    if (!d) {
      d = { accepted: true, condition: 'intact', seal: seal ?? '', reason: '' };
      this.drafts.set(sampleId, d);
    }
    return d;
  }

  protected accept(e: EngagementLabView): void {
    runAction(this.api.accept(e.id), this.busy, this.notify, 'Engagement accepted.', () => this.load());
  }

  protected end(e: EngagementLabView): void {
    askReason(this.dialog, { title: `End the engagement for ${e.project_code}?`, confirmLabel: 'End', danger: true }).subscribe((r) => {
      if (r) runAction(this.api.end(e.id, r.reason), this.busy, this.notify, 'Engagement ended.', () => this.load());
    });
  }

  protected receive(sh: ShipmentLabView): void {
    const items = sh.items.filter((i) => i.status === 'IN_SHIPMENT').map((i) => {
      const d = this.draft(i.sample_id, i.seal_number);
      return { sample_id: i.sample_id, accepted: d.accepted, condition: d.condition || null, seal_number_observed: d.seal || null,
        reason: d.accepted ? null : d.reason || null };
    });
    runAction(this.api.receive(sh.id, items), this.busy, this.notify, 'Receipt recorded.', () => this.load());
  }

  protected accession(s: SampleLabView): void {
    runAction(this.api.accession(s.id, this.accessionNo[s.id]), this.busy, this.notify, `${s.sample_code} registered at the laboratory.`,
      () => this.load());
  }
}
