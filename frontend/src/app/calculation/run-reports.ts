import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, inject, input, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';

import { DocumentsApi } from '../core/api/documents.api';
import { AuthService } from '../core/auth/auth.service';
import { P } from '../core/auth/permissions';
import { NotifyService } from '../core/notify.service';
import { runAction } from '../shared/run-action';
import { StatusBadge } from '../shared/status-badge';
import { CALCULATED_LABEL, CalcRun } from './calculation.models';
import { PreverificationApi } from './preverification.api';
import { CalcReport, ReportVerify } from './preverification.models';

/** Official calculation report of an APPROVED run: generate (deterministic JSON + PDF), download, verify hashes. */
@Component({
  selector: 'app-run-reports',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, MatButtonModule, StatusBadge],
  template: `
    <div class="reports" data-testid="report-section">
      <h3>Calculation report</h3>
      @if (run().status !== 'APPROVED' && !reports().length) {
        <p class="small muted" data-testid="report-not-available">Official reports exist only for APPROVED runs (this run is {{ run().status }}).</p>
      }
      @for (r of reports(); track r.id) {
        <div class="report"><strong>{{ r.report_code }}</strong> v{{ r.version }}
          <app-status-badge [status]="r.status === 'CURRENT' ? 'ACTIVE' : 'ARCHIVED'" [text]="r.status" />
          <span class="small muted"> · {{ r.generated_at | date: 'short' }} · {{ r.generator_version }}</span>
          <div class="small mono">content {{ r.content_sha256 }} · PDF {{ r.pdf_sha256 }}</div>
          <button mat-button type="button" (click)="download(r)">Download PDF</button>
          <button mat-button type="button" (click)="check(r)" [attr.data-testid]="'verify-' + r.version">Verify</button>
          @if (verified()[r.id]; as v) {
            <span class="small" [class.bad]="!v.valid">{{ v.valid ? 'Hashes verify' : 'INTEGRITY FAILED: ' + v.problems.join('; ') }}{{ v.stale ? ' · out of date' : '' }}</span>
          }
        </div>
      }
      @if (canGenerate && run().status === 'APPROVED') {
        <button mat-stroked-button type="button" [disabled]="busy()" (click)="generate()" data-testid="generate-report">Generate report</button>
      }
      <p class="small muted">{{ calculatedLabel }}. The report is a deterministic rendering of frozen data; it is not a verification report.</p>
    </div>
  `,
  styles: `.reports { margin: 8px 0 12px; } h3 { margin: 8px 0 4px; font: var(--mat-sys-title-small); }
    .report { padding: 4px 0; } .mono { font-family: monospace; font-size: 11px; word-break: break-all; } .bad { color: var(--mat-sys-error); }`,
})
export class RunReports implements OnInit {
  readonly run = input.required<CalcRun>();
  private readonly api = inject(PreverificationApi);
  private readonly docs = inject(DocumentsApi);
  private readonly notify = inject(NotifyService);
  protected readonly canGenerate = inject(AuthService).has(P.CALCULATION_MANAGE);
  protected readonly calculatedLabel = CALCULATED_LABEL;
  protected readonly reports = signal<CalcReport[]>([]);
  protected readonly verified = signal<Record<string, ReportVerify>>({});
  protected readonly busy = signal(false);

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.api.reports(this.run().id).subscribe((r) => this.reports.set(r));
  }

  protected generate(): void {
    runAction(this.api.generate(this.run().id), this.busy, this.notify, 'Report generated.', () => this.load());
  }

  protected check(r: CalcReport): void {
    this.api.verify(r.id).subscribe((v) => this.verified.update((m) => ({ ...m, [r.id]: v })));
  }

  protected download(r: CalcReport): void {
    this.docs.download(r.document_id, `${r.report_code}.pdf`).subscribe({ error: (e: unknown) => this.notify.error(e) });
  }
}
