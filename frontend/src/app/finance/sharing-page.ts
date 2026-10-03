import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { Observable } from 'rxjs';

import { AuthService } from '../core/auth/auth.service';
import { P } from '../core/auth/permissions';
import { NotifyService } from '../core/notify.service';
import { PageHeader } from '../shared/page-header';
import { askReason } from '../shared/reason-dialog';
import { runAction } from '../shared/run-action';
import { StatusBadge } from '../shared/status-badge';
import { FinanceApi } from './finance.api';
import { Allocation, FinanceProject, ROUNDING_MODES, ShareVersion, finBadge, label, newKey, pctTotal } from './finance.models';
import { FIN_STYLES, FinanceProjectPicker } from './project-picker';

/** Revenue-share versions (the farmer share percentage, cost deduction and rounding mode come from the project's agreements — the platform
 *  has no default) and per-period farm allocation tables (every farm once, total exactly 100). Authored by sharing.manage, approved by a
 *  different person (sharing.approve); immutable once approved, replaced by a new version. */
@Component({
  selector: 'app-sharing-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, MatButtonModule, MatCheckboxModule, MatFormFieldModule, MatInputModule, MatSelectModule, PageHeader, StatusBadge,
            FinanceProjectPicker],
  template: `
    <app-page-header title="Revenue sharing" subtitle="Approved, versioned configuration used by settlements" />
    <p class="note">Enter the values your agreements specify. Nothing is pre-filled: there is no default farmer percentage, rounding mode or
      allocation. Acreage and carbon tonnes are not used automatically.</p>
    <app-finance-project-picker (changed)="select($event)" />
    <h3>Revenue-share versions</h3>
    @if (canAuthor && project()) {
      <section class="box" data-testid="share-form">
        <div class="row">
          <mat-form-field subscriptSizing="dynamic"><mat-label>Farmer share % (0–100]</mat-label><input matInput [(ngModel)]="s.pct" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Rounding mode</mat-label>
            <mat-select [(ngModel)]="s.rounding">@for (m of modes; track m) { <mat-option [value]="m">{{ m }}</mat-option> }</mat-select></mat-form-field>
          <mat-checkbox [(ngModel)]="s.deduct">Deduct approved project costs</mat-checkbox>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Effective from</mat-label><input matInput type="date" [(ngModel)]="s.from" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Effective to (optional)</mat-label><input matInput type="date" [(ngModel)]="s.to" /></mat-form-field>
        </div>
        <mat-form-field subscriptSizing="dynamic" class="full"><mat-label>Source (agreement / clause)</mat-label><input matInput [(ngModel)]="s.source" /></mat-form-field>
        <button mat-flat-button type="button" [disabled]="busy() || !shareValid()" (click)="createShare()">Create draft version</button>
      </section>
    }
    <div class="table-wrap"><table class="table" data-testid="share-versions">
      <thead><tr><th>Version</th><th>Farmer share</th><th>Costs</th><th>Rounding</th><th>Effective</th><th>Source</th><th>Status</th><th></th></tr></thead>
      <tbody>
        @for (v of versions(); track v.id) {
          <tr><td>{{ v.version_code }} (v{{ v.version_no }})</td><td>{{ v.farmer_share_pct }} %</td><td>{{ v.deduct_approved_costs ? 'deducted' : 'not deducted' }}</td>
            <td>{{ v.rounding_mode }}</td><td>{{ v.effective_from }} → {{ v.effective_to ?? 'open' }}</td><td class="small">{{ v.source_reference }}</td>
            <td><app-status-badge [status]="badge(v.status)" [text]="label(v.status)" />@if (v.return_reason) { <div class="small">{{ v.return_reason }}</div> }</td>
            <td>@if (canAuthor && v.status === 'DRAFT') { <button mat-button type="button" [disabled]="busy()" (click)="shareAct(v, 'submit')">Submit</button> }
              @if (canApprove && v.status === 'IN_REVIEW') { <button mat-button type="button" [disabled]="busy()" (click)="shareAct(v, 'approve')">Approve</button>
                <button mat-button type="button" [disabled]="busy()" (click)="shareReturn(v)">Return</button> }</td></tr>
        } @empty { <tr><td colspan="8" class="muted" data-testid="no-share">No revenue-share version — settlements need an approved one.</td></tr> }
      </tbody>
    </table></div>
    <h3>Farm allocation per monitoring period</h3>
    @if (canAuthor && project(); as p) {
      <section class="box" data-testid="alloc-form">
        <div class="row">
          <mat-form-field subscriptSizing="dynamic"><mat-label>Monitoring period</mat-label>
            <mat-select [(ngModel)]="a.period">@for (m of p.periods; track m.id) { <mat-option [value]="m.id">Period {{ m.period_number }} · {{ m.name }}</mat-option> }</mat-select></mat-form-field>
          <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Basis (document / decision)</mat-label><input matInput [(ngModel)]="a.basis" /></mat-form-field>
        </div>
        @for (f of p.farms; track f.project_farm_id) {
          <div class="row"><span class="wide">{{ f.farm_name }} · {{ f.farmer_name }} <span class="small muted">({{ f.status }})</span></span>
            <mat-form-field subscriptSizing="dynamic"><mat-label>Share %</mat-label><input matInput [(ngModel)]="a.shares[f.project_farm_id]" /></mat-form-field></div>
        }
        <p class="small" data-testid="alloc-total">Total: {{ total() }} % (must be exactly 100 to submit; leave a farm empty to exclude it)</p>
        <button mat-flat-button type="button" [disabled]="busy() || !allocValid()" (click)="createAlloc()">Create draft allocation</button>
      </section>
    }
    <div class="table-wrap"><table class="table" data-testid="allocations">
      <thead><tr><th>Allocation</th><th>Period</th><th>Lines</th><th>Total</th><th>Basis</th><th>Status</th><th></th></tr></thead>
      <tbody>
        @for (x of allocations(); track x.id) {
          <tr><td>{{ x.version_code }} (v{{ x.version_no }})</td><td>{{ x.period_number }}</td>
            <td class="small">@for (l of x.lines; track l.id) { <div>{{ l.farm_name }} · {{ l.farmer_name }}: {{ l.share_pct }} %</div> }</td>
            <td>{{ x.total_pct }} %</td><td class="small">{{ x.basis_reference }}</td>
            <td><app-status-badge [status]="badge(x.status)" [text]="label(x.status)" /></td>
            <td>@if (canAuthor && x.status === 'DRAFT') { <button mat-button type="button" [disabled]="busy()" (click)="allocAct(x, 'submit')">Submit</button> }
              @if (canApprove && x.status === 'IN_REVIEW') { <button mat-button type="button" [disabled]="busy()" (click)="allocAct(x, 'approve')">Approve</button>
                <button mat-button type="button" [disabled]="busy()" (click)="allocReturn(x)">Return</button> }</td></tr>
        } @empty { <tr><td colspan="7" class="muted" data-testid="no-alloc">No farm allocation — settlements need an approved one per period.</td></tr> }
      </tbody>
    </table></div>
  `,
  styles: FIN_STYLES + ' .full { width: 100%; }',
})
export class SharingPage {
  private readonly api = inject(FinanceApi);
  private readonly auth = inject(AuthService);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotifyService);
  protected readonly label = label;
  protected readonly badge = finBadge;
  protected readonly modes = ROUNDING_MODES;
  protected readonly canAuthor = this.auth.has(P.SHARING_MANAGE);
  protected readonly canApprove = this.auth.has(P.SHARING_APPROVE);
  protected readonly project = signal<FinanceProject | null>(null);
  protected readonly versions = signal<ShareVersion[]>([]);
  protected readonly allocations = signal<Allocation[]>([]);
  protected readonly busy = signal(false);
  protected s = { pct: '', rounding: '', deduct: false, from: '', to: '', source: '' };
  protected a: { period: string; basis: string; shares: Record<string, string> } = { period: '', basis: '', shares: {} };

  protected select(p: FinanceProject): void {
    this.project.set(p);
    this.a = { period: '', basis: '', shares: {} };
    this.reload();
  }

  private reload(): void {
    const p = this.project();
    if (!p) return;
    this.api.shareVersions(p.id).subscribe((v) => this.versions.set(v));
    this.api.allocations(p.id).subscribe((x) => this.allocations.set(x));
  }

  private act<T>(obs: Observable<T>, message: string): void {
    runAction(obs, this.busy, this.notify, message, () => this.reload());
  }

  protected shareValid(): boolean {
    const pct = this.s.pct.trim();
    return /^\d{1,3}(\.\d{1,6})?$/.test(pct) && Number(pct) > 0 && Number(pct) <= 100 && !!this.s.rounding && !!this.s.from
      && this.s.source.trim().length >= 3;
  }

  protected createShare(): void {
    const p = this.project();
    if (!p) return;
    this.act(this.api.createShareVersion({ project_id: p.id, farmer_share_pct: this.s.pct.trim(), deduct_approved_costs: this.s.deduct,
      rounding_mode: this.s.rounding, effective_from: this.s.from, effective_to: this.s.to || null, source_reference: this.s.source.trim() },
    newKey()), 'Draft version created.');
  }

  protected shareAct(v: ShareVersion, action: 'submit' | 'approve'): void {
    this.act(this.api.shareAction(v.id, action, {}, newKey()), action === 'submit' ? 'Submitted for review.' : 'Version approved.');
  }

  protected shareReturn(v: ShareVersion): void {
    askReason(this.dialog, { title: `Return ${v.version_code}?`, confirmLabel: 'Return to author' })
      .subscribe((r) => { if (r) this.act(this.api.shareAction(v.id, 'return', { reason: r.reason }, newKey()), 'Returned.'); });
  }

  private lines(): { project_farm_id: string; share_pct: string }[] {
    return Object.entries(this.a.shares).filter(([, v]) => (v ?? '').trim() !== '')
      .map(([id, v]) => ({ project_farm_id: id, share_pct: v.trim() }));
  }

  protected total(): string {
    return pctTotal(this.lines().map((l) => l.share_pct));
  }

  protected allocValid(): boolean {
    return !!this.a.period && this.a.basis.trim().length >= 3 && this.lines().length > 0 && this.total() !== 'invalid';
  }

  protected createAlloc(): void {
    const p = this.project();
    if (!p) return;
    this.act(this.api.createAllocation({ project_id: p.id, monitoring_period_id: this.a.period, basis_reference: this.a.basis.trim(),
      lines: this.lines() }, newKey()), 'Draft allocation created.');
  }

  protected allocAct(x: Allocation, action: 'submit' | 'approve'): void {
    this.act(this.api.allocationAction(x.id, action, {}, newKey()), action === 'submit' ? 'Submitted for review.' : 'Allocation approved.');
  }

  protected allocReturn(x: Allocation): void {
    askReason(this.dialog, { title: `Return ${x.version_code}?`, confirmLabel: 'Return to author' })
      .subscribe((r) => { if (r) this.act(this.api.allocationAction(x.id, 'return', { reason: r.reason }, newKey()), 'Returned.'); });
  }
}
