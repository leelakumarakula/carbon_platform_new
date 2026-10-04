import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, effect, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { RouterLink } from '@angular/router';

import { AuthService } from '../../core/auth/auth.service';
import { P } from '../../core/auth/permissions';
import { NotifyService } from '../../core/notify.service';
import { label } from '../../farmer/farmer.models';
import { LabApi } from '../../lab/lab.api';
import { Engagement, LabResult, LaboratoryOrg, RuleRef, Sample, Shipment, labBadge, resultValue } from '../../lab/lab.models';
import { askReason } from '../../shared/reason-dialog';
import { runAction } from '../../shared/run-action';
import { StatusBadge } from '../../shared/status-badge';
import { MrvApi } from '../mrv.api';
import { FieldCollection, Period } from '../mrv.models';

/** Phase 6 project side: laboratory engagements, sample registration & sealing, shipments, approved results with lineage. */
@Component({
  selector: 'app-mrv-samples-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, FormsModule, RouterLink, MatButtonModule, MatCheckboxModule, MatFormFieldModule, MatInputModule, MatSelectModule, StatusBadge],
  template: `
    <div class="tab-body">
      <h3>Laboratory engagements</h3>
      @for (e of engagements(); track e.id) {
        <div class="line"><div class="grow"><strong>{{ e.laboratory_org_name }}</strong>
          <app-status-badge [status]="badge(e.status)" [text]="label(e.status)" />
          <span class="small muted"> · scope: {{ ruleCodes(e.rules) }} · {{ e.methodology_label }}</span>
          @if (e.end_reason) { <div class="small muted">Ended ({{ e.ended_side }}): {{ e.end_reason }}</div> }</div>
          @if (e.can_end) { <button mat-button type="button" (click)="endEngagement(e)">End</button> }
        </div>
      } @empty { <p class="muted small">No laboratory engaged. Laboratory work needs an ACTIVE engagement, accepted by the laboratory.</p> }
      @if (canEngage) {
        <div class="row">
          <mat-form-field subscriptSizing="dynamic"><mat-label>Laboratory</mat-label>
            <mat-select [(ngModel)]="labId" data-testid="engage-lab">@for (l of labs(); track l.id) { <mat-option [value]="l.id">{{ l.name }} ({{ l.code }})</mat-option> }</mat-select>
          </mat-form-field>
          <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>LABORATORY rules in scope</mat-label>
            <mat-select [(ngModel)]="ruleIds" multiple data-testid="engage-rules">
              @for (r of rules(); track r.rule_id) { <mat-option [value]="r.rule_id">{{ r.rule_code }} · {{ r.parameter }}{{ r.unit ? ' (' + r.unit + ')' : '' }}</mat-option> }
            </mat-select></mat-form-field>
          <button mat-flat-button type="button" [disabled]="busy() || !labId || !ruleIds.length" (click)="propose()" data-testid="propose-engagement">Propose engagement</button>
        </div>
        <p class="muted small">The laboratory accepts the proposal. Only methodology rules declared LABORATORY can be in scope; a scope change is a new engagement.</p>
      }

      <h3>Samples {{ period() ? '· ' + period()!.name : '' }}</h3>
      @if (!period()) { <p class="muted">Select a monitoring period.</p> }
      <div class="table-wrap"><table class="table">
        <thead><tr><th>Field record</th><th>Point</th><th>Record status</th><th>Samples</th><th></th></tr></thead>
        <tbody>
          @for (c of collections(); track c.id) {
            <tr>
              <td>{{ c.collection_code }} v{{ c.version }}</td><td>{{ c.point_code }}</td>
              <td><app-status-badge [status]="badge(c.status)" [text]="label(c.status)" />
                @if (c.analysis_status) { <app-status-badge [status]="badge(c.analysis_status)" [text]="label(c.analysis_status)" /> }</td>
              <td>
                @for (s of samplesOf(c.id); track s.id) {
                  <div class="sample"><a [routerLink]="['/mrv/samples', s.id]">{{ s.sample_code }}</a>
                    <app-status-badge [status]="badge(s.status)" [text]="label(s.status)" />
                    <span class="small muted">{{ s.laboratory_org_name }} · tests {{ s.approved_count }}/{{ s.test_count }} approved</span>
                    @if (s.can_seal) {
                      <input class="seal" placeholder="Seal no." [(ngModel)]="sealNo[s.id]" [attr.data-testid]="'seal-' + s.sample_code" />
                      <button mat-button type="button" [disabled]="busy() || !sealNo[s.id]" (click)="sealSample(s)">Seal</button>
                    }
                    @if (canManage && (s.status === 'REGISTERED' || s.status === 'SEALED')) { <button mat-button type="button" (click)="voidSample(s)">Void</button> }
                  </div>
                } @empty { <span class="muted small">—</span> }
              </td>
              <td>@if (canRegister && (c.status === 'SUBMITTED' || c.status === 'ACCEPTED')) {
                <button mat-stroked-button type="button" [disabled]="busy()" (click)="registerFor(c)">Register sample</button> }</td>
            </tr>
          } @empty { <tr><td colspan="5" class="muted">No submitted or accepted field records in this period.</td></tr> }
        </tbody>
      </table></div>

      @if (canShip || canRead) {
        <h3>Shipments</h3>
        @for (sh of shipments(); track sh.id) {
          <div class="ship">
            <div class="line"><div class="grow"><strong>{{ sh.shipment_code }}</strong> → {{ sh.laboratory_org_name }}
              <app-status-badge [status]="badge(sh.status)" [text]="label(sh.status)" />
              <span class="small muted">{{ sh.items.length }} item(s){{ sh.dispatched_at ? ' · dispatched ' + (sh.dispatched_at | date: 'short') : '' }}</span></div>
              @if (canShip && sh.status === 'DRAFT') {
                <button mat-flat-button type="button" [disabled]="busy() || !openItems(sh)" (click)="dispatch(sh)" data-testid="dispatch">Dispatch</button>
                <button mat-button type="button" (click)="cancel(sh)">Cancel</button>
              }
            </div>
            <div class="small">@for (i of sh.items; track i.sample_id) { <span class="chip">{{ i.sample_code }} · {{ label(i.status) }}</span> }</div>
            @if (canShip && sh.status === 'DRAFT') {
              <div class="row">
                <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Add sealed samples</mat-label>
                  <mat-select [(ngModel)]="addIds[sh.id]" multiple [attr.data-testid]="'add-samples-' + sh.shipment_code">
                    @for (s of sealedFor(sh); track s.id) { <mat-option [value]="s.id">{{ s.sample_code }}</mat-option> }
                  </mat-select></mat-form-field>
                <button mat-stroked-button type="button" [disabled]="busy() || !(addIds[sh.id] ?? []).length" (click)="addItems(sh)">Add</button>
              </div>
            }
          </div>
        } @empty { <p class="muted small">No shipments yet.</p> }
        @if (canShip) {
          <div class="row">
            <mat-form-field subscriptSizing="dynamic"><mat-label>Ship to laboratory</mat-label>
              <mat-select [(ngModel)]="shipLab" data-testid="ship-lab">@for (e of activeEngagements(); track e.id) { <mat-option [value]="e.laboratory_org_id">{{ e.laboratory_org_name }}{{ labCode(e.laboratory_org_id) }}</mat-option> }</mat-select>
            </mat-form-field>
            <mat-form-field subscriptSizing="dynamic"><mat-label>Carrier</mat-label><input matInput [(ngModel)]="carrier" /></mat-form-field>
            <button mat-flat-button type="button" [disabled]="busy() || !shipLab" (click)="createShipment()" data-testid="create-shipment">Create shipment</button>
          </div>
        }
      }

      @if (canRead) {
        <h3>Approved laboratory results</h3>
        <div class="table-wrap"><table class="table">
          <thead><tr><th>Test</th><th>Parameter</th><th>Value</th><th>Analysed</th><th>Approved by</th><th></th></tr></thead>
          <tbody>
            @for (r of results(); track r.id) {
              <tr><td>{{ r.test_code }} v{{ r.version }}</td><td>{{ r.rule_code }} · {{ r.parameter }}</td><td>{{ value(r) }}</td>
                <td>{{ r.analysed_at | date: 'mediumDate' }}</td><td>{{ r.approved_by_name }}</td>
                <td><a mat-button [routerLink]="['/mrv/lab-results', r.id]" data-testid="lineage-link">Lineage</a></td></tr>
            } @empty { <tr><td colspan="6" class="muted">No approved laboratory result yet. Values come only from laboratory QA approval.</td></tr> }
          </tbody>
        </table></div>
      }
    </div>
  `,
  styles: `
    h3 { margin: 16px 0 8px; font: var(--mat-sys-title-small); } .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
    .wide { min-width: 260px; flex: 1; } .line { display: flex; gap: 8px; align-items: center; padding: 4px 0; flex-wrap: wrap; } .grow { flex: 1; }
    .sample { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; padding: 2px 0; } .seal { width: 90px; padding: 4px; }
    .ship { border: 1px solid var(--mat-sys-outline-variant); border-radius: 8px; padding: 6px 10px; margin-bottom: 8px; }
    .chip { display: inline-block; padding: 1px 8px; margin: 2px; border-radius: 999px; background: var(--mat-sys-surface-container); }
  `,
})
export class MrvSamplesPanel {
  readonly projectId = input.required<string>();
  readonly period = input<Period | null>(null);
  private readonly lab = inject(LabApi);
  private readonly mrv = inject(MrvApi);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotifyService);
  private readonly auth = inject(AuthService);
  protected readonly canEngage = this.auth.has(P.LAB_ENGAGE);
  protected readonly canRegister = this.auth.has(P.LAB_SAMPLE_REGISTER);
  protected readonly canManage = this.auth.has(P.LAB_SAMPLE_MANAGE);
  protected readonly canShip = this.auth.has(P.LAB_SHIPMENT_MANAGE);
  protected readonly canRead = this.auth.has(P.LAB_READ);
  protected readonly label = label;
  protected readonly badge = labBadge;
  protected readonly value = resultValue;
  protected readonly busy = signal(false);
  protected readonly engagements = signal<Engagement[]>([]);
  protected readonly labs = signal<LaboratoryOrg[]>([]);
  protected readonly rules = signal<RuleRef[]>([]);
  protected readonly collections = signal<FieldCollection[]>([]);
  protected readonly samples = signal<Sample[]>([]);
  protected readonly shipments = signal<Shipment[]>([]);
  protected readonly results = signal<LabResult[]>([]);
  protected readonly activeEngagements = computed(() => this.engagements().filter((e) => e.status === 'ACTIVE'));
  protected labId = '';
  protected ruleIds: string[] = [];
  protected shipLab = '';
  protected carrier = '';
  protected sealNo: Record<string, string> = {};
  protected addIds: Record<string, string[] | undefined> = {};

  constructor() {
    effect(() => {
      const pid = this.projectId();
      this.loadProject(pid);
    });
    effect(() => {
      const p = this.period();
      if (p) this.loadPeriod(p.id);
    });
  }

  /** Engagements carry no laboratory code; show it when the laboratory list (engage permission) has it. */
  protected labCode(id: string): string {
    const code = this.labs().find((l) => l.id === id)?.code;
    return code ? ` (${code})` : '';
  }

  private loadProject(pid: string): void {
    if (this.canEngage || this.canRead) {
      this.lab.engagements(pid).subscribe((e) => this.engagements.set(e));
      this.lab.laboratoryRules(pid).subscribe((r) => this.rules.set(r));
    }
    if (this.canEngage) this.lab.laboratories(pid).subscribe((l) => this.labs.set(l));
    if (this.canShip || this.canRead) this.lab.shipments(pid).subscribe((s) => this.shipments.set(s));
    if (this.canRead) this.lab.results(pid).subscribe((r) => this.results.set(r));
  }

  private loadPeriod(periodId: string): void {
    this.mrv.collections({ monitoring_period_id: periodId }).subscribe((c) =>
      this.collections.set(c.filter((x) => ['SUBMITTED', 'ACCEPTED', 'SUPERSEDED'].includes(x.status))));
    this.lab.samples({ monitoring_period_id: periodId }).subscribe((s) => this.samples.set(s));
  }

  private reload(): void {
    this.loadProject(this.projectId());
    const p = this.period();
    if (p) this.loadPeriod(p.id);
  }

  protected ruleCodes(rs: RuleRef[]): string {
    return rs.map((r) => r.rule_code).join(', ');
  }

  protected samplesOf(fcId: string): Sample[] {
    return this.samples().filter((s) => s.field_collection_id === fcId);
  }

  protected sealedFor(sh: Shipment): Sample[] {
    return this.samples().filter((s) => s.status === 'SEALED' && s.laboratory_org_id === sh.laboratory_org_id);
  }

  protected openItems(sh: Shipment): number {
    return sh.items.filter((i) => i.status === 'IN_SHIPMENT').length;
  }

  protected propose(): void {
    runAction(this.lab.propose({ project_id: this.projectId(), laboratory_org_id: this.labId, rule_ids: this.ruleIds }), this.busy, this.notify,
      'Engagement proposed — waiting for the laboratory to accept.', () => { this.ruleIds = []; this.reload(); });
  }

  protected endEngagement(e: Engagement): void {
    askReason(this.dialog, { title: `End the engagement with ${e.laboratory_org_name}?`, confirmLabel: 'End', danger: true,
      message: 'Work already in progress may finish; no new shipments, tests or retests. It cannot be reactivated.' }).subscribe((r) => {
      if (r) runAction(this.lab.endEngagement(e.id, r.reason), this.busy, this.notify, 'Engagement ended.', () => this.reload());
    });
  }

  protected registerFor(c: FieldCollection): void {
    const active = this.activeEngagements();
    runAction(this.lab.register({ field_collection_id: c.id, description: 'Composite soil sample',
      laboratory_org_id: active.length === 1 ? active[0].laboratory_org_id : null }), this.busy, this.notify,
    'Sample registered; laboratory tests were created automatically.', () => this.reload());
  }

  protected sealSample(s: Sample): void {
    runAction(this.lab.seal(s.id, this.sealNo[s.id]), this.busy, this.notify, `${s.sample_code} sealed.`, () => this.reload());
  }

  protected voidSample(s: Sample): void {
    askReason(this.dialog, { title: `Void ${s.sample_code}?`, confirmLabel: 'Void', danger: true }).subscribe((r) => {
      if (r) runAction(this.lab.voidSample(s.id, r.reason), this.busy, this.notify, 'Sample voided.', () => this.reload());
    });
  }

  protected createShipment(): void {
    runAction(this.lab.createShipment({ project_id: this.projectId(), laboratory_org_id: this.shipLab, carrier: this.carrier || null }), this.busy,
      this.notify, 'Shipment created.', () => this.reload());
  }

  protected addItems(sh: Shipment): void {
    runAction(this.lab.addItems(sh.id, this.addIds[sh.id] ?? []), this.busy, this.notify, 'Samples added.', () => { this.addIds[sh.id] = []; this.reload(); });
  }

  protected dispatch(sh: Shipment): void {
    runAction(this.lab.dispatch(sh.id), this.busy, this.notify, `${sh.shipment_code} dispatched.`, () => this.reload());
  }

  protected cancel(sh: Shipment): void {
    askReason(this.dialog, { title: `Cancel ${sh.shipment_code}?`, confirmLabel: 'Cancel shipment', danger: true }).subscribe((r) => {
      if (r) runAction(this.lab.cancelShipment(sh.id, r.reason), this.busy, this.notify, 'Shipment cancelled.', () => this.reload());
    });
  }
}
