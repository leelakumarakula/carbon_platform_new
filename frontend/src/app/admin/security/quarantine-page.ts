import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { finalize } from 'rxjs';

import { P } from '../../core/auth/permissions';
import { AuthService } from '../../core/auth/auth.service';
import { DocumentScan, DocumentsApi, SecurityDocument } from '../../core/api/documents.api';
import { NotifyService } from '../../core/notify.service';
import { label } from '../../farmer/farmer.models';
import { PageHeader } from '../../shared/page-header';
import { askReason } from '../../shared/reason-dialog';
import { runAction } from '../../shared/run-action';
import { StatusBadge } from '../../shared/status-badge';

export function scanBadge(result: string): string {
  return result === 'CLEAN' ? 'ACTIVE' : result === 'INFECTED' ? 'CRITICAL' : result === 'ERROR' ? 'FAILED' : 'WARNING';
}

/** Security → Document quarantine (Phase 12B D12–D16). Quarantined documents of the caller's environment with their append-only scan
 *  history. security.manage may queue a background rescan or release a document; the server releases only after a clean rescan of every
 *  version performed at that moment (a refused release is audited and keeps the document quarantined). No file content is shown. */
@Component({
  selector: 'app-quarantine-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, MatButtonModule, PageHeader, StatusBadge],
  template: `
    <app-page-header title="Document quarantine" subtitle="Files held because malware was found, the scanner was unavailable, or security placed a hold" />
    <p class="small muted">Release requires a clean antivirus rescan of every version, run at release time. A test-signature result
      (NOT_SCANNED) is never treated as clean. Every scan is kept in the history.</p>
    <div class="table-wrap"><table class="table" data-testid="quarantine">
      <thead><tr><th>Document</th><th>State</th><th>Latest scan</th><th>Entity</th><th>Uploaded</th><th></th></tr></thead>
      <tbody>
        @for (d of docs(); track d.id) {
          <tr [attr.data-doc]="d.id" [class.sel]="selected()?.id === d.id">
            <td><a href="" (click)="$event.preventDefault(); open(d)">{{ d.title }}</a><div class="small muted">{{ label(d.category) }} · v{{ d.current_version }}</div></td>
            <td><app-status-badge [status]="d.scan_state === 'INFECTED' ? 'CRITICAL' : 'WARNING'" [text]="label(d.scan_state)" /></td>
            <td class="small">@if (d.latest_scan; as s) { {{ s.result }} · {{ s.provider }}@if (s.threat_name) { · {{ s.threat_name }} } } @else { — }</td>
            <td class="small">{{ label(d.entity_type) }}</td>
            <td>{{ d.created_at | date: 'short' }}</td>
            <td>@if (canManage()) {
              <button mat-button type="button" [disabled]="busy()" (click)="rescan(d)">Rescan</button>
              <button mat-button type="button" [disabled]="busy()" (click)="release(d)">Release</button>
            }</td>
          </tr>
        } @empty { <tr><td colspan="6" class="muted" data-testid="no-quarantine">No quarantined document.</td></tr> }
      </tbody>
    </table></div>
    @if (selected(); as d) {
      <section class="box" data-testid="scan-history"><h3>Scan history — {{ d.title }}</h3>
        <div class="table-wrap"><table class="table">
          <thead><tr><th>When</th><th>Trigger</th><th>Result</th><th>Scanner</th><th>Threat / error</th><th>SHA-256</th></tr></thead>
          <tbody>@for (s of scans(); track s.id) {
            <tr><td>{{ s.scanned_at | date: 'medium' }}</td><td>{{ label(s.trigger_type) }}</td>
              <td><app-status-badge [status]="badge(s.result)" [text]="s.result" /></td>
              <td class="small">{{ s.provider }}{{ s.engine_version ? ' ' + s.engine_version : '' }}</td>
              <td class="small">{{ s.threat_name ?? s.error_code ?? '—' }}</td><td class="small mono">{{ s.checksum_sha256.slice(0, 12) }}…</td></tr>
          } @empty { <tr><td colspan="6" class="muted">No scan recorded.</td></tr> }</tbody></table></div>
      </section>
    }
  `,
  styles: `.box { border: 1px solid var(--mat-sys-outline-variant); border-radius: 8px; padding: 10px 12px; margin: 10px 0; }
    h3 { margin: 4px 0 8px; font: var(--mat-sys-title-small); } .mono { font-family: monospace; } tr.sel { background: var(--mat-sys-surface-container); }`,
})
export class QuarantinePage implements OnInit {
  private readonly api = inject(DocumentsApi);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotifyService);
  private readonly auth = inject(AuthService);
  protected readonly label = label;
  protected readonly badge = scanBadge;
  protected readonly docs = signal<SecurityDocument[]>([]);
  protected readonly selected = signal<SecurityDocument | null>(null);
  protected readonly scans = signal<DocumentScan[]>([]);
  protected readonly busy = signal(false);
  protected readonly canManage = () => this.auth.has(P.SECURITY_MANAGE);

  ngOnInit(): void {
    this.reload();
  }

  reload(): void {
    this.api.quarantined().subscribe((d) => this.docs.set(d));
    const s = this.selected();
    if (s) this.open(s);
  }

  protected open(d: SecurityDocument): void {
    this.selected.set(d);
    this.api.scans(d.id).subscribe((s) => this.scans.set(s));
  }

  protected rescan(d: SecurityDocument): void {
    runAction(this.api.rescan(d.id), this.busy, this.notify, 'Rescan queued as a background job. A rescan never releases a document.',
      () => this.reload());
  }

  protected release(d: SecurityDocument): void {
    askReason(this.dialog, { title: `Release "${d.title}"?`, confirmLabel: 'Rescan and release',
      message: 'Every version is rescanned now. The document is released only if every result is CLEAN; otherwise it stays quarantined.' })
      .subscribe((r) => {
        if (!r) return;
        // a refused release still adds scan rows: refresh the history either way
        runAction(this.api.release(d.id, r.reason).pipe(finalize(() => this.reload())), this.busy, this.notify,
          'Document released after a clean rescan.', () => this.selected.set(null));
      });
  }
}
