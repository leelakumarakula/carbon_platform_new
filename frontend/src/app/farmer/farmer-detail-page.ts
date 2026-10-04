import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatDialog } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { MatTabsModule } from '@angular/material/tabs';

import { ApiError } from '../core/api/api.models';
import { NotifyService } from '../core/notify.service';
import { DocumentsPanel, UploadFn } from '../shared/documents-panel';
import { PageHeader } from '../shared/page-header';
import { ReadinessPanel } from '../shared/readiness-panel';
import { askReason } from '../shared/reason-dialog';
import { reloadOn } from '../shared/reload-on';
import { StateView } from '../shared/state-view';
import { StatusBadge } from '../shared/status-badge';
import { FARMER_DOC_CATEGORIES, Farmer, label } from './farmer.models';
import { FarmersApi } from './farmers.api';
import { FarmerAgreementsPanel } from './panels/farmer-agreements-panel';
import { FarmerBankPanel } from './panels/farmer-bank-panel';
import { FarmerConsentsPanel } from './panels/farmer-consents-panel';
import { FarmerFarmsPanel } from './panels/farmer-farms-panel';
import { FarmerKycPanel } from './panels/farmer-kyc-panel';
import { FarmerProfilePanel } from './panels/farmer-profile-panel';

const ACTION: Record<string, string> = { REGISTERED: 'Register', ACTIVE: 'Activate', SUSPENDED: 'Suspend' };

@Component({
  selector: 'app-farmer-detail-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MatTabsModule, MatCardModule, MatButtonModule, MatIconModule, PageHeader, StateView, StatusBadge, ReadinessPanel, DocumentsPanel,
    FarmerProfilePanel, FarmerKycPanel, FarmerConsentsPanel, FarmerAgreementsPanel, FarmerBankPanel, FarmerFarmsPanel],
  template: `
    <app-state-view [loading]="loading()" [error]="error()" (retry)="load()" />
    @if (farmer(); as f) {
      <app-page-header [title]="f.full_name" [subtitle]="f.farmer_code + ' · ' + (f.village ?? f.district ?? '') + ' · ' + (f.organization_name ?? '')"
                       [backLink]="f.is_self ? null : '/farmers'" backLabel="Farmers">
        @if (f.can_manage) {
          @for (t of f.allowed_transitions; track t) {
            <button mat-stroked-button type="button" [disabled]="busy()" (click)="transition(t)">{{ action(t) }}</button>
          }
        }
      </app-page-header>
      <div class="status-row">
        <app-status-badge [status]="f.status" />
        @if (f.environment === 'DEMO') { <app-status-badge status="DEMO" /> }
        @if (f.kyc.possible_duplicate) { <app-status-badge status="WARNING" text="Possible duplicate identity" /> }
      </div>
      @if (hasReadiness()) {
        <mat-card appearance="outlined" class="section"><mat-card-content><app-readiness-panel [readiness]="f.readiness" /></mat-card-content></mat-card>
      }
      <mat-tab-group animationDuration="0ms" mat-stretch-tabs="false">
        <mat-tab label="Profile">
          <ng-template matTabContent><app-farmer-profile-panel [farmer]="f" (changed)="set($event)" /></ng-template>
        </mat-tab>
        <mat-tab label="KYC">
          <ng-template matTabContent><app-farmer-kyc-panel [farmer]="f" (changed)="set($event)" /></ng-template>
        </mat-tab>
        <mat-tab [label]="'Consents (' + f.consents.length + ')'">
          <ng-template matTabContent><app-farmer-consents-panel [farmer]="f" (changed)="set($event)" /></ng-template>
        </mat-tab>
        <mat-tab [label]="'Agreements (' + f.agreements.length + ')'">
          <ng-template matTabContent><app-farmer-agreements-panel [farmer]="f" (changed)="set($event)" /></ng-template>
        </mat-tab>
        <mat-tab label="Bank">
          <ng-template matTabContent><app-farmer-bank-panel [farmer]="f" (changed)="set($event)" /></ng-template>
        </mat-tab>
        <mat-tab [label]="'Documents (' + f.documents.length + ')'">
          <ng-template matTabContent>
            <div class="tab-body">
              <app-documents-panel [documents]="f.documents" [categories]="categories" [canUpload]="f.can_manage"
                                   [uploadFn]="uploadFn" (uploaded)="load()" />
            </div>
          </ng-template>
        </mat-tab>
        <mat-tab [label]="'Farms (' + f.farm_count + ')'">
          <ng-template matTabContent><app-farmer-farms-panel [farmer]="f" /></ng-template>
        </mat-tab>
      </mat-tab-group>
    }
  `,
  styles: `.status-row { display: flex; gap: 6px; margin: -8px 0 16px; flex-wrap: wrap; }`,
})
export class FarmerDetailPage {
  readonly id = input.required<string>();
  private readonly api = inject(FarmersApi);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotifyService);

  protected readonly farmer = signal<Farmer | null>(null);
  protected readonly loading = signal(true);
  protected readonly error = signal<ApiError | null>(null);
  protected readonly busy = signal(false);
  protected readonly categories = FARMER_DOC_CATEGORIES;
  protected readonly hasReadiness = computed(() => (this.farmer()?.readiness ?? []).some((r) => r.items.length));
  protected readonly uploadFn: UploadFn = (file, category, title) => this.api.uploadDocument(this.id(), file, category, title);

  constructor() {
    reloadOn(this.id, () => {
      this.farmer.set(null);
      this.load();
    });
  }

  load(): void {
    this.loading.set(this.farmer() === null);
    this.error.set(null);
    this.api.get(this.id()).subscribe({
      next: (f) => this.set(f),
      error: (e: unknown) => {
        this.error.set(ApiError.from(e));
        this.loading.set(false);
      },
    });
  }

  set(f: Farmer): void {
    this.farmer.set(f);
    this.loading.set(false);
    this.busy.set(false);
  }

  action(t: string): string {
    return ACTION[t] ?? label(t);
  }

  transition(target: string): void {
    askReason(this.dialog, { title: `${this.action(target)} ${this.farmer()?.full_name}?`, confirmLabel: this.action(target),
      danger: target === 'SUSPENDED' }).subscribe((r) => {
      if (!r) return;
      this.busy.set(true);
      this.api.changeStatus(this.id(), target, r.reason).subscribe({
        next: (f) => {
          this.set(f);
          this.notify.success(`Farmer is now ${label(f.status)}.`);
        },
        error: (e: unknown) => {
          this.busy.set(false);
          this.notify.error(e);
        },
      });
    });
  }
}
