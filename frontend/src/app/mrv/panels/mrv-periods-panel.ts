import { ChangeDetectionStrategy, Component, inject, input, output, signal } from '@angular/core';
import { FormControl, FormGroup, FormGroupDirective, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';

import { AuthService } from '../../core/auth/auth.service';
import { P } from '../../core/auth/permissions';
import { NotifyService } from '../../core/notify.service';
import { label } from '../../farmer/farmer.models';
import { askReason } from '../../shared/reason-dialog';
import { runAction } from '../../shared/run-action';
import { StatusBadge } from '../../shared/status-badge';
import { MrvApi } from '../mrv.api';
import { PERIOD_ACTIONS, Period, PeriodStatus, mrvBadge } from '../mrv.models';

/** Monitoring periods: DRAFT → PLANNED → ACTIVE → DATA_COLLECTION → (dataset) SUBMITTED → QA_REVIEW → APPROVED / REJECTED → CLOSED. */
@Component({
  selector: 'app-mrv-periods-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, MatButtonModule, MatFormFieldModule, MatInputModule, MatSelectModule, StatusBadge],
  template: `
    <div class="tab-body">
      <div class="table-wrap"><table class="table">
        <thead><tr><th>#</th><th>Name</th><th>Purpose</th><th>Dates</th><th>Plan</th><th>Status</th><th>Points</th><th>Collected</th><th></th></tr></thead>
        <tbody>
          @for (x of periods(); track x.id) {
            <tr>
              <td>{{ x.period_number }}</td><td>{{ x.name }}</td><td>{{ label(x.purpose) }}</td><td>{{ x.start_date }} → {{ x.end_date }}</td>
              <td>v{{ x.plan_version }}</td>
              <td><app-status-badge [status]="badge(x.status)" [text]="label(x.status)" /></td>
              <td>{{ x.counts['points'] }}</td><td>{{ x.counts['collected'] }}</td>
              <td class="actions">
                @if (canManage) {
                  @for (t of buttons(x); track t.action) {
                    <button mat-stroked-button type="button" [disabled]="busy()" (click)="act(x, t.action, t.label)">{{ t.label }}</button>
                  }
                }
              </td>
            </tr>
          } @empty { <tr><td colspan="9" class="muted">No monitoring period yet. An approved MRV plan is required first.</td></tr> }
        </tbody>
      </table></div>
      <p class="muted small">Submission, QA review and approval happen through the period's MRV dataset (Datasets &amp; QA tab). Nothing proceeds to calculation in this phase.</p>
      @if (canManage) {
        <h3>New monitoring period</h3>
        <form [formGroup]="form" #fd="ngForm" (ngSubmit)="create(fd)" class="form">
          <mat-form-field subscriptSizing="dynamic" class="wide"><mat-label>Name</mat-label><input matInput formControlName="name" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Purpose</mat-label>
            <mat-select formControlName="purpose">@for (p of purposes; track p) { <mat-option [value]="p">{{ label(p) }}</mat-option> }</mat-select></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>Start</mat-label><input matInput type="date" formControlName="start_date" /></mat-form-field>
          <mat-form-field subscriptSizing="dynamic"><mat-label>End</mat-label><input matInput type="date" formControlName="end_date" /></mat-form-field>
          <button mat-flat-button type="submit" [disabled]="busy() || form.invalid">Create period</button>
        </form>
      }
    </div>
  `,
  styles: `
    h3 { margin: 16px 0 8px; font: var(--mat-sys-title-small); } .actions { display: flex; gap: 6px; flex-wrap: wrap; }
    .form { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; } .wide { min-width: 220px; flex: 1; }
  `,
})
export class MrvPeriodsPanel {
  readonly projectId = input.required<string>();
  readonly periods = input<Period[]>([]);
  readonly changed = output<void>();
  private readonly api = inject(MrvApi);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotifyService);
  protected readonly canManage = inject(AuthService).has(P.MRV_MANAGE);
  protected readonly label = label;
  protected readonly badge = mrvBadge;
  protected readonly busy = signal(false);
  protected readonly purposes = ['MONITORING', 'BASELINE', 'VERIFICATION', 'OTHER'];
  protected readonly form = new FormGroup({
    name: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.minLength(2)] }),
    purpose: new FormControl('MONITORING', { nonNullable: true }),
    start_date: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
    end_date: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
  });

  protected buttons(x: Period): { action: string; label: string }[] {
    return x.allowed_transitions.map((t: PeriodStatus) => PERIOD_ACTIONS[t]).filter((a): a is { action: string; label: string } => !!a)
      .filter((a) => !(x.status === 'APPROVED' && a.action === 'open-collection'));
  }

  protected act(x: Period, action: string, text: string): void {
    askReason(this.dialog, { title: `${text}: ${x.name}?`, confirmLabel: text }).subscribe((r) => {
      if (r) runAction(this.api.periodAction(x.id, action, r.reason), this.busy, this.notify, `Period is now ${label(this.target(action))}.`,
        () => this.changed.emit());
    });
  }

  private target(action: string): string {
    return ({ plan: 'PLANNED', start: 'ACTIVE', 'open-collection': 'DATA_COLLECTION', close: 'CLOSED' } as Record<string, string>)[action] ?? action;
  }

  protected create(fd: FormGroupDirective): void {
    runAction(this.api.createPeriod({ project_id: this.projectId(), ...this.form.getRawValue() }), this.busy, this.notify, 'Monitoring period created.',
      () => { fd.resetForm({ name: '', purpose: 'MONITORING', start_date: '', end_date: '' }); this.changed.emit(); });
  }
}
