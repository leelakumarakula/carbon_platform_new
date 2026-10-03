import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';

import { PageHeader } from '../shared/page-header';
import { StatusBadge } from '../shared/status-badge';
import { FinanceApi } from './finance.api';
import { MyPayouts, finBadge, label, money } from './finance.models';

/** Farmer self-service: the farmer's own payouts only (amount, status, dates, last 4 of the bank account). */
@Component({
  selector: 'app-my-payouts-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, PageHeader, StatusBadge],
  template: `
    <app-page-header title="My payouts" subtitle="Payments to you from your project's carbon revenue" />
    @if (data(); as d) {
      @if (d.note) { <p class="note" data-testid="my-payouts-note">{{ d.note }}</p> }
      <div class="table-wrap"><table class="table" data-testid="my-payouts">
        <thead><tr><th>Payout</th><th>Project · period</th><th>Amount</th><th>Status</th><th>Bank</th><th>Paid</th></tr></thead>
        <tbody>
          @for (p of d.payouts; track p.payout_code) {
            <tr><td>{{ p.payout_code }}</td><td>{{ p.project_code }} · {{ p.period_number }}</td><td>{{ money(p.amount, p.currency) }}</td>
              <td><app-status-badge [status]="badge(p.status)" [text]="label(p.status)" /></td>
              <td>{{ p.bank_last4 ? '••••' + p.bank_last4 : '—' }}</td><td>{{ p.paid_at ? (p.paid_at | date: 'mediumDate') : '—' }}</td></tr>
          } @empty { <tr><td colspan="6" class="muted" data-testid="no-my-payouts">No payout yet.</td></tr> }
        </tbody>
      </table></div>
    }
  `,
})
export class MyPayoutsPage implements OnInit {
  private readonly api = inject(FinanceApi);
  protected readonly money = money;
  protected readonly label = label;
  protected readonly badge = finBadge;
  protected readonly data = signal<MyPayouts | null>(null);

  ngOnInit(): void {
    this.api.myPayouts().subscribe((d) => this.data.set(d));
  }
}
