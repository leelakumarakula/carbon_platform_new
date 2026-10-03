/** Phase 11 — revenue, revenue-share configuration, farm allocation, costs, settlements, payouts. Money is a decimal STRING from the API
 *  (never a float); every figure (revenue, entitlement, payout) is calculated by the server — no form here ever sends a payout amount. */
import { DocumentRef } from '../lab/lab.models';
import { mlabel, money } from '../marketplace/marketplace.models';

export { money };
export const label = mlabel;
export const FIN_DEMO_NOTE = 'DEMO — no registry-issued credits; no revenue, cost, entitlement or payout exists in DEMO';
export const ROUNDING_MODES = ['HALF_UP', 'HALF_EVEN', 'DOWN'] as const;

export interface PeriodRef { id: string; period_number: number; name: string; start_date: string; end_date: string }
export interface ProjectFarmRef { project_farm_id: string; farm_name: string | null; farmer_name: string | null; status: string }
export interface FinanceProject {
  id: string; project_code: string; name: string; organization_id: string; environment: string; periods: PeriodRef[]; farms: ProjectFarmRef[];
}

export interface Revenue {
  id: string; revenue_code: string; kind: 'RECOGNITION' | 'REVERSAL'; amount: string; currency: string; project_id: string;
  monitoring_period_id: string; order_code: string | null; order_item_code: string | null; payment_code: string | null;
  transfer_code: string | null; batch_code: string | null; reverses_revenue_code: string | null; refund_code: string | null;
  seller_organization_id: string; settled_in_run_code: string | null; recorded_at: string; environment: string;
}

export interface ShareVersion {
  id: string; version_code: string; project_id: string; version_no: number; farmer_share_pct: string; deduct_approved_costs: boolean;
  rounding_mode: string; effective_from: string; effective_to: string | null; source_reference: string; notes: string | null;
  status: 'DRAFT' | 'IN_REVIEW' | 'APPROVED' | 'SUPERSEDED'; created_by_name: string | null; approved_by_name: string | null;
  approved_at: string | null; return_reason: string | null; created_at: string; environment: string;
}

export interface AllocationLine {
  id: string; project_farm_id: string; farm_id: string; farm_name: string | null; farmer_id: string; farmer_name: string | null; share_pct: string;
}
export interface Allocation {
  id: string; version_code: string; project_id: string; monitoring_period_id: string; period_number: number | null; version_no: number;
  basis_reference: string; status: ShareVersion['status']; total_pct: string; lines: AllocationLine[]; created_by_name: string | null;
  approved_by_name: string | null; approved_at: string | null; return_reason: string | null; created_at: string; environment: string;
}

export interface Cost {
  id: string; cost_code: string; project_id: string; monitoring_period_id: string | null; category: string; description: string;
  amount: string; currency: string; incurred_on: string; external_reference: string | null; corrects_cost_id: string | null;
  status: 'PENDING_APPROVAL' | 'APPROVED' | 'REJECTED'; created_by_name: string | null; approved_by_name: string | null;
  reject_reason: string | null; settled_in_run_code: string | null; documents: DocumentRef[]; created_at: string; environment: string;
}

export interface Entitlement {
  id: string; allocation_line_id: string; project_farm_id: string; farm_id: string; farm_name: string | null; farmer_id: string;
  farmer_name: string | null; share_pct: string; amount: string; currency: string;
}
export interface Settlement {
  id: string; run_code: string; project_id: string; project_code: string | null; monitoring_period_id: string; period_number: number | null;
  currency: string; revenue_share_version_code: string | null; allocation_version_code: string | null; calculation_version: string | null;
  gross_revenue: string | null; deducted_costs: string | null; distributable: string | null; farmer_total: string | null;
  developer_residual: string | null; input_sha256: string | null;
  status: 'DRAFT' | 'CALCULATED' | 'PENDING_APPROVAL' | 'APPROVED' | 'COMPLETED' | 'REJECTED' | 'CANCELLED';
  created_by_name: string | null; calculated_by_name: string | null; calculated_at: string | null; approved_by_name: string | null;
  approved_at: string | null; close_reason: string | null; revenue_count: number; cost_count: number; entitlements: Entitlement[];
  created_at: string; environment: string;
}
export interface Verify {
  run_code: string; calculation_version: string | null; input_sha256: string | null; hash_ok: boolean; figures_ok: boolean;
  entitlements_ok: boolean; inputs_ok: boolean; reproducible: boolean;
}

export interface PayoutTx { kind: string; adapter_code: string; external_reference: string | null; amount: string; currency: string;
  note: string | null; actor_name: string | null; created_at: string }
export interface Reconciliation { id: string; result: 'MATCHED' | 'EXCEPTION'; statement_reference: string; statement_amount: string;
  statement_currency: string; statement_date: string; note: string | null; reconciled_by_name: string | null; created_at: string }
export interface Payout {
  id: string; payout_code: string; settlement_run_id: string; run_code: string | null; farmer_id: string; farmer_name: string | null;
  amount: string; currency: string;
  status: 'CALCULATED' | 'PENDING_APPROVAL' | 'APPROVED' | 'PAYMENT_PENDING' | 'PAID' | 'RECONCILED' | 'REJECTED' | 'CANCELLED' | 'FAILED'
    | 'UNCONFIRMED' | 'ON_HOLD';
  adapter_code: string; bank_last4: string | null; external_reference: string | null; replaces_payout_code: string | null;
  reason: string | null; calculated_by_name: string | null; approved_by_name: string | null; executed_by_name: string | null;
  paid_at: string | null; reconciled_at: string | null; calculated_at: string; transactions: PayoutTx[]; reconciliations: Reconciliation[];
  documents: DocumentRef[]; environment: string;
}
export interface MyPayout { payout_code: string; amount: string; currency: string; status: Payout['status']; project_code: string | null;
  period_number: number | null; bank_last4: string | null; paid_at: string | null; reconciled_at: string | null; calculated_at: string }
export interface MyPayouts { farmer_linked: boolean; payouts: MyPayout[]; note: string | null }
export interface Adjustment {
  id: string; adjustment_code: string; project_id: string; reversal_revenue_code: string | null; original_run_code: string | null;
  amount: string; currency: string; status: 'OPEN' | 'CLOSED'; resolution: string | null; closed_by_name: string | null;
  closed_at: string | null; created_at: string;
}
export interface Summary {
  revenue: { currency: string; recognized: string; reversed: string; net: string }[];
  costs_by_category: { currency: string; category: string; amount: string }[];
  settlements: { currency: string; distributable: string; farmer_total: string; developer_residual: string }[];
  payouts_by_status: { status: string; count: number; amounts: { currency: string; amount: string }[] }[];
  open_recovery_cases: number;
  demo_note: string | null;
}

export function finBadge(status: string): string {
  return ({ APPROVED: 'ACTIVE', RECONCILED: 'ACTIVE', COMPLETED: 'ACTIVE', MATCHED: 'ACTIVE', RECOGNITION: 'ACTIVE', CLOSED: 'ARCHIVED',
    DRAFT: 'INFO', CALCULATED: 'INFO', IN_REVIEW: 'WARNING', PENDING_APPROVAL: 'WARNING', PAYMENT_PENDING: 'WARNING', PAID: 'WARNING',
    UNCONFIRMED: 'WARNING', ON_HOLD: 'WARNING', OPEN: 'WARNING', REVERSAL: 'WARNING', SUPERSEDED: 'ARCHIVED', CANCELLED: 'ARCHIVED',
    REJECTED: 'FAILED', FAILED: 'FAILED', EXCEPTION: 'FAILED' } as Record<string, string>)[status] ?? 'INFO';
}

/** Sum of decimal percentage strings without float drift (fixed 6-decimal integer arithmetic) — display / pre-check only; the server
 *  validates that an allocation totals exactly 100. */
export function pctTotal(values: readonly string[]): string {
  let micro = 0n;
  for (const v of values) {
    const t = (v ?? '').trim();
    if (!/^\d+(\.\d{1,6})?$/.test(t)) return 'invalid';
    const [w, f = ''] = t.split('.');
    micro += BigInt(w) * 1_000_000n + BigInt(f.padEnd(6, '0'));
  }
  const whole = micro / 1_000_000n;
  const frac = (micro % 1_000_000n).toString().padStart(6, '0').replace(/0+$/, '');
  return frac ? `${whole}.${frac}` : `${whole}`;
}

export function newKey(): string {
  return globalThis.crypto?.randomUUID?.() ?? `k-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
