import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';

import { DocumentsApi } from '../core/api/documents.api';
import { NotifyService } from '../core/notify.service';
import { PageHeader } from '../shared/page-header';
import { runAction } from '../shared/run-action';
import { StatusBadge } from '../shared/status-badge';
import { MarketplaceApi } from './marketplace.api';
import { BuyerProfileView, marketBadge, mlabel, newKey } from './marketplace.models';

/** The buyer organization's profile and KYC (organization level). Documents are restricted (the buyer and the platform reviewer only) and
 *  PDF only; no particular legal document is assumed — upload what your compliance contact asked for. */
@Component({
  selector: 'app-buyer-profile-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, FormsModule, MatButtonModule, MatFormFieldModule, MatInputModule, PageHeader, StatusBadge],
  template: `
    <app-page-header title="Buyer profile" subtitle="Organization profile and KYC for marketplace purchases" />
    @if (view(); as v) {
      <p class="note">{{ v.note }}</p>
      @if (v.profile; as p) {
        <p data-testid="kyc-status">KYC status: <app-status-badge [status]="badge(p.status)" [text]="label(p.status)" />
          @if (p.verified_at) { <span class="small"> verified {{ p.verified_at | date: 'mediumDate' }} by {{ p.verified_by_name }}</span> }</p>
        @if (p.return_reason && p.status === 'KYC_RETURNED') { <p class="note warn">Returned: {{ p.return_reason }}</p> }
        @if (p.suspension_reason && p.status === 'SUSPENDED') { <p class="note warn">Suspended: {{ p.suspension_reason }}</p> }
        @if (!p.can_edit) {
          <p class="small" data-testid="profile-summary">{{ p.legal_name }}@if (p.registration_number) { · {{ p.registration_number }} }
            @if (p.country) { · {{ p.country }} } · {{ p.documents.length }} KYC document(s)</p>
        }
      }
      @if (!v.profile || v.profile.can_edit) {
        <section class="box" data-testid="buyer-profile-form">
          <mat-form-field subscriptSizing="dynamic" class="full"><mat-label>Legal name</mat-label><input matInput [(ngModel)]="f.legal_name" /></mat-form-field>
          <div class="row">
            <mat-form-field subscriptSizing="dynamic"><mat-label>Registration number</mat-label><input matInput [(ngModel)]="f.registration_number" /></mat-form-field>
            <mat-form-field subscriptSizing="dynamic"><mat-label>Country (ISO code)</mat-label><input matInput maxlength="2" [(ngModel)]="f.country" /></mat-form-field>
            <mat-form-field subscriptSizing="dynamic"><mat-label>Contact name</mat-label><input matInput [(ngModel)]="f.contact_name" /></mat-form-field>
            <mat-form-field subscriptSizing="dynamic"><mat-label>Contact email</mat-label><input matInput [(ngModel)]="f.contact_email" /></mat-form-field>
          </div>
          <button mat-flat-button type="button" data-testid="save-profile" [disabled]="busy() || f.legal_name.trim().length < 2" (click)="save()">Save</button>
        </section>
        @if (v.profile; as p) {
          <section class="box">
            <h4>KYC documents (PDF)</h4>
            @for (d of p.documents; track d.document_id) {
              <div><button mat-button type="button" (click)="download(d.document_id, d.title)">{{ d.title }}</button></div>
            } @empty { <p class="muted small">No document yet.</p> }
            <input type="file" accept="application/pdf" data-testid="kyc-file" (change)="pick($event)" />
            <button mat-stroked-button type="button" [disabled]="busy() || !file" (click)="upload()">Upload</button>
            <div class="row"><button mat-flat-button type="button" data-testid="submit-kyc" [disabled]="busy() || !p.documents.length" (click)="submit()">
              Submit for KYC review</button></div>
          </section>
        }
      }
      @if (v.profile?.reviews?.length) {
        <h4>History</h4>
        @for (r of v.profile!.reviews; track $index) {
          <div class="small">{{ r.created_at | date: 'medium' }} · {{ label(r.action) }} · {{ r.actor_name }}@if (r.note) { · {{ r.note }} }</div>
        }
      }
    }
  `,
  styles: `.box { border: 1px solid var(--mat-sys-outline-variant); border-radius: 8px; padding: 10px 12px; margin: 10px 0; max-width: 820px; }
    .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin: 6px 0; } .full { width: 100%; } .warn { color: #7a5200; }
    h4 { margin: 6px 0; }`,
})
export class BuyerProfilePage implements OnInit {
  private readonly api = inject(MarketplaceApi);
  private readonly docs = inject(DocumentsApi);
  private readonly notify = inject(NotifyService);
  protected readonly label = mlabel;
  protected readonly badge = marketBadge;
  protected readonly view = signal<BuyerProfileView | null>(null);
  protected readonly busy = signal(false);
  protected f = { legal_name: '', registration_number: '', country: '', contact_name: '', contact_email: '' };
  protected file: File | undefined;
  private key = newKey();

  ngOnInit(): void {
    this.reload();
  }

  private reload(): void {
    this.api.profile().subscribe((v) => {
      this.view.set(v);
      const p = v.profile;
      if (p) {
        this.f = { legal_name: p.legal_name, registration_number: p.registration_number ?? '', country: p.country ?? '',
          contact_name: p.contact_name ?? '', contact_email: p.contact_email ?? '' };
      }
    });
  }

  protected save(): void {
    const f = this.f;
    runAction(this.api.saveProfile({ legal_name: f.legal_name.trim(), registration_number: f.registration_number.trim() || null,
      country: f.country.trim() || null, contact_name: f.contact_name.trim() || null, contact_email: f.contact_email.trim() || null }),
    this.busy, this.notify, 'Buyer profile saved.', () => this.reload());
  }

  protected pick(ev: Event): void {
    this.file = (ev.target as HTMLInputElement).files?.[0];
  }

  protected upload(): void {
    if (!this.file) return;
    runAction(this.api.kycDocument(this.file), this.busy, this.notify, 'KYC document attached.', () => {
      this.file = undefined;
      this.reload();
    });
  }

  protected submit(): void {
    runAction(this.api.submitKyc(this.key), this.busy, this.notify, 'Submitted for KYC review.', () => {
      this.key = newKey();
      this.reload();
    });
  }

  protected download(id: string, title: string): void {
    this.docs.download(id, `${title}.pdf`).subscribe({ error: (e: unknown) => this.notify.error(e) });
  }
}
