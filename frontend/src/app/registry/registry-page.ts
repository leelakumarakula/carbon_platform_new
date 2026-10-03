import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';

import { label } from '../farmer/farmer.models';
import { PageHeader } from '../shared/page-header';
import { RegistryPanel } from './registry-panel';
import { RegistryApi } from './registry.api';
import { RegistryProject } from './registry.models';

/** Registry workspace for registry.read holders (e.g. the Registry Manager, who has no MRV or project permission). */
@Component({
  selector: 'app-registry-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, MatFormFieldModule, MatSelectModule, PageHeader, RegistryPanel],
  template: `
    <app-page-header title="Registry" subtitle="Registry submissions and registry-stated issuances — registries are external; nothing here is inventory" />
    <div class="row">
      <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Project</mat-label>
        <mat-select [(ngModel)]="projectId" (ngModelChange)="periodId = ''" data-testid="registry-project">
          @for (p of projects(); track p.id) { <mat-option [value]="p.id">{{ p.project_code }} · {{ p.name }} ({{ label(p.status) }})</mat-option> }
        </mat-select></mat-form-field>
      <mat-form-field subscriptSizing="dynamic"><mat-label>Monitoring period</mat-label>
        <mat-select [(ngModel)]="periodId" data-testid="registry-period">
          @for (mp of periodsOf(projectId); track mp.id) { <mat-option [value]="mp.id">#{{ mp.number }} {{ mp.name }}</mat-option> }
        </mat-select></mat-form-field>
    </div>
    @if (projectId && periodId) { <app-registry-panel [projectId]="projectId" [periodId]="periodId" /> }
  `,
  styles: `.row { display: flex; gap: 8px; flex-wrap: wrap; } .wide { min-width: 320px; flex: 1; }`,
})
export class RegistryPage implements OnInit {
  private readonly api = inject(RegistryApi);
  protected readonly label = label;
  protected readonly projects = signal<RegistryProject[]>([]);
  protected projectId = '';
  protected periodId = '';

  ngOnInit(): void {
    this.api.projects().subscribe((p) => this.projects.set(p));
  }

  protected periodsOf(id: string): RegistryProject['periods'] {
    return this.projects().find((p) => p.id === id)?.periods ?? [];
  }
}
