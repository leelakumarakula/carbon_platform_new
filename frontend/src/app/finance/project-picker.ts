import { ChangeDetectionStrategy, Component, OnInit, inject, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';

import { AuthService } from '../core/auth/auth.service';
import { FinanceApi } from './finance.api';
import { FIN_DEMO_NOTE, FinanceProject } from './finance.models';

export const FIN_STYLES = `.box { border: 1px solid var(--mat-sys-outline-variant); border-radius: 8px; padding: 10px 12px; margin: 10px 0; }
  .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-bottom: 4px; } .wide { min-width: 280px; flex: 1; }
  h3 { margin: 12px 0 8px; font: var(--mat-sys-title-small); } .figs { display: flex; gap: 16px; flex-wrap: wrap; }
  .fig { min-width: 150px; } .fig b { display: block; font-size: 16px; }`;

/** Projects the user may see financially (with periods and farm participations); DEMO shows the empty-state note. */
@Component({
  selector: 'app-finance-project-picker',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule, MatFormFieldModule, MatSelectModule],
  template: `
    @if (demo) { <p class="note warn" data-testid="fin-demo-note">{{ demoNote }}</p> }
    @if (projects().length) {
      <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Project</mat-label>
        <mat-select data-testid="fin-project" [ngModel]="selected()?.id" (ngModelChange)="pick($event)">
          @for (p of projects(); track p.id) { <mat-option [value]="p.id">{{ p.project_code }} · {{ p.name }}</mat-option> }
        </mat-select></mat-form-field>
    } @else if (loaded()) { <p class="muted" data-testid="fin-no-project">No project with financial records is visible to you.</p> }
  `,
  styles: `.wide { min-width: 320px; }`,
})
export class FinanceProjectPicker implements OnInit {
  private readonly api = inject(FinanceApi);
  protected readonly demo = inject(AuthService).isDemo();
  protected readonly demoNote = FIN_DEMO_NOTE;
  protected readonly projects = signal<FinanceProject[]>([]);
  protected readonly selected = signal<FinanceProject | null>(null);
  protected readonly loaded = signal(false);
  readonly changed = output<FinanceProject>();

  ngOnInit(): void {
    this.api.projects().subscribe((ps) => {
      this.projects.set(ps);
      this.loaded.set(true);
      if (ps.length) this.pick(ps[0].id);
    });
  }

  protected pick(id: string): void {
    const p = this.projects().find((x) => x.id === id) ?? null;
    this.selected.set(p);
    if (p) this.changed.emit(p);
  }
}
