/** Phase 9B — credit ledger. Ledger quantities derive only from registry-issued credits; calculated and VVB-stated quantities stay in the
 *  Phase 9A Registry area. Not a marketplace: no price, order, checkout or payment. */
export const DEMO_NOTE = 'DEMO — no registry-issued credits';
export const LEDGER_NOTE = 'Ledger quantities derive from registry-issued credits only. Not a marketplace: no price, order or payment.';

export const BALANCE_COLUMNS: { key: keyof Balance; label: string }[] = [
  { key: 'available', label: 'Available' },
  { key: 'reserved', label: 'Reserved' },
  { key: 'pending_transfer', label: 'Pending transfer' },
  { key: 'pending_retirement', label: 'Pending retirement' },
  { key: 'transferred_out', label: 'Transferred out' },
  { key: 'retired', label: 'Retired' },
];

export interface Balance {
  owner_organization_id: string;
  owner_name: string | null;
  available: number;
  reserved: number;
  pending_transfer: number;
  pending_retirement: number;
  retired: number;
  transferred_out: number;
}

export interface Opening {
  id: string;
  opening_code: string;
  batch_id: string;
  owner_organization_id: string;
  status: 'REQUESTED' | 'CONFIRMED' | 'CANCELLED';
  requested_by_name: string | null;
  requested_at: string;
  confirmed_by_name: string | null;
  confirmed_at: string | null;
  cancel_reason: string | null;
  can_confirm: boolean;
}

export interface InventoryBatch {
  batch_id: string;
  batch_code: string;
  project_id: string;
  project_code: string | null;
  period_number: number | null;
  vintage: string;
  unit: string;
  registry_name: string | null;
  batch_status: string;
  issued: number;
  opening: Opening | null;
  balances: Balance[];
  environment: string;
}

export interface Inventory { batches: InventoryBatch[]; note: string; demo_note: string | null }

export interface Position {
  id: string;
  batch_id: string;
  batch_code: string | null;
  serial_range_id: string;
  registry_range: string;
  owner_organization_id: string;
  owner_name: string | null;
  holding_external_account_id: string;
  state: 'AVAILABLE' | 'RESERVED' | 'TRANSFER_PENDING' | 'RETIREMENT_PENDING' | 'RETIRED';
  status: 'OPEN' | 'CONSUMED';
  quantity: number;
  sub_range: string | null;
  parsed: boolean;
  reservation_id: string | null;
  transfer_id: string | null;
  retirement_id: string | null;
  created_by_entry_id: string;
  consumed_by_entry_id: string | null;
  created_at: string;
}

export interface Reservation {
  id: string;
  reservation_code: string;
  batch_id: string;
  batch_code: string | null;
  owner_organization_id: string;
  recipient_organization_id: string | null;
  purpose: string;
  purpose_reference: string | null;
  quantity: number;
  expires_at: string;
  status: 'ACTIVE' | 'CONSUMED' | 'RELEASED' | 'EXPIRED';
  created_by_name: string | null;
  created_at: string;
  release_reason: string | null;
  closed_at: string | null;
}

export interface Transfer {
  id: string;
  transfer_code: string;
  kind: 'INTERNAL' | 'REGISTRY';
  batch_id: string;
  batch_code: string | null;
  sender_organization_id: string;
  sender_name: string | null;
  recipient_organization_id: string;
  recipient_name: string | null;
  recipient_external_account_id: string | null;
  quantity: number;
  purpose: string | null;
  purpose_reference: string | null;
  reservation_id: string | null;
  status: 'REQUESTED' | 'COMPLETED' | 'CANCELLED' | 'REJECTED';
  requested_by_name: string | null;
  requested_at: string;
  completed_by_name: string | null;
  completed_at: string | null;
  registry_transfer_reference: string | null;
  evidence_document_id: string | null;
  close_reason: string | null;
  completion_entry_id: string | null;
  can_complete: boolean;
}

export interface Retirement {
  id: string;
  retirement_code: string;
  batch_id: string;
  batch_code: string | null;
  owner_organization_id: string;
  owner_name: string | null;
  quantity: number;
  beneficiary: string;
  reason: string;
  status: 'REQUESTED' | 'RETIRED' | 'REJECTED' | 'CANCELLED';
  requested_by_name: string | null;
  requested_at: string;
  retired_by_name: string | null;
  retired_at: string | null;
  registry_retirement_reference: string | null;
  retirement_date: string | null;
  certificate_document_id: string | null;
  retired_serials: { serial_start: string | null; serial_end: string | null; quantity: number }[] | null;
  close_reason: string | null;
  can_retire: boolean;
}

export interface Reversal {
  id: string;
  reversal_code: string;
  reversed_entry_id: string;
  batch_id: string;
  reason: string;
  status: 'REQUESTED' | 'APPLIED' | 'REJECTED';
  requested_by_name: string | null;
  decided_by_name: string | null;
  decision_note: string | null;
  entry_id: string | null;
}

export interface Entry {
  id: string;
  entry_code: string;
  entry_type: string;
  batch_id: string;
  organization_id: string;
  counterparty_organization_id: string | null;
  quantity: number;
  actor_name: string | null;
  confirmed_by_name: string | null;
  reason: string | null;
  created_at: string;
  inputs: Position[];
  outputs: Position[];
}

export interface Holding {
  position_id: string;
  batch_id: string;
  batch_code: string;
  owner_organization_id: string;
  state: string;
  quantity: number;
  project_code: string | null;
  project_name: string | null;
  period_number: number | null;
  vintage: string;
  methodology: string | null;
  standard: string | null;
  registry_name: string | null;
  issuance_code: string | null;
  external_issuance_id: string | null;
  registry_range: string;
  sub_range: string | null;
  environment: string;
}

export interface Holdings { holdings: Holding[]; demo_note: string | null; note: string }

export function ledgerBadge(status: string): string {
  return ({ AVAILABLE: 'ACTIVE', ACTIVE: 'WARNING', RESERVED: 'WARNING', TRANSFER_PENDING: 'WARNING', RETIREMENT_PENDING: 'WARNING',
    REQUESTED: 'WARNING', CONFIRMED: 'ACTIVE', COMPLETED: 'ACTIVE', APPLIED: 'ACTIVE', RETIRED: 'INFO', CONSUMED: 'ARCHIVED',
    RELEASED: 'ARCHIVED', EXPIRED: 'ARCHIVED', CANCELLED: 'ARCHIVED', REJECTED: 'FAILED' } as Record<string, string>)[status] ?? 'INFO';
}

/** Sum of a balance column over all owners of a batch (display only — the server derives every figure). */
export function total(b: InventoryBatch, key: keyof Balance): number {
  return b.balances.reduce((t, x) => t + (Number(x[key]) || 0), 0);
}

export interface Recipient { id: string; code: string; name: string; org_type: string }
