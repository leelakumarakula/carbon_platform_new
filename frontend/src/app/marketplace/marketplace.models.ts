/** Phase 10 — marketplace. Money is a decimal STRING from the API (never a float) with an ISO-4217 currency; credit quantities are whole
 *  numbers. No fee, tax or commission exists; ownership is only ever changed by the credit ledger (custodian transfer completion). */
import { label } from '../farmer/farmer.models';
import { DocumentRef } from '../lab/lab.models';

export const DEMO_NOTE = 'DEMO — no registry-issued credits; nothing is listed';
export const NOT_INVOICE = 'Order confirmation — not a tax invoice; no fee, commission or tax is added.';

export interface KycReview { action: string; actor_name: string | null; note: string | null; created_at: string }

export interface BuyerProfile {
  id: string;
  organization_id: string;
  organization_name: string | null;
  organization_code: string | null;
  status: 'DRAFT' | 'KYC_SUBMITTED' | 'KYC_VERIFIED' | 'KYC_RETURNED' | 'SUSPENDED';
  legal_name: string;
  registration_number: string | null;
  country: string | null;
  contact_name: string | null;
  contact_email: string | null;
  identifier_type: string | null;
  identifier_last4: string | null;
  submitted_by_name: string | null;
  submitted_at: string | null;
  verified_by_name: string | null;
  verified_at: string | null;
  return_reason: string | null;
  suspension_reason: string | null;
  documents: DocumentRef[];
  reviews: KycReview[];
  environment: string;
  can_edit: boolean;
  can_review: boolean;
}

export interface BuyerProfileView { organization_id: string | null; organization_name: string | null; profile: BuyerProfile | null; note: string }

export interface Listing {
  id: string;
  listing_code: string;
  title: string;
  seller_organization_id: string;
  seller_name: string | null;
  batch_id: string;
  batch_code: string | null;
  serial_range_id: string | null;
  listed_quantity: number;
  remaining_quantity: number;
  available_quantity: number;
  unit_price: string;
  currency: string;
  min_quantity: number | null;
  max_quantity: number | null;
  payment_window_hours: number;
  valid_until: string | null;
  co_benefits: string | null;
  disclosure: Record<string, string | number | null>;
  disclosure_sha256: string | null;
  status: 'DRAFT' | 'PENDING_APPROVAL' | 'ACTIVE' | 'PAUSED' | 'CLOSED' | 'EXPIRED' | 'CANCELLED';
  created_by_name: string | null;
  approved_by_name: string | null;
  approved_at: string | null;
  close_reason: string | null;
  documents: DocumentRef[];
  environment: string;
  seller_side: boolean;
  can_manage: boolean;
  can_approve: boolean;
}

export interface Listings { listings: Listing[]; demo_note: string | null; note: string }

export interface OrderItem {
  id: string;
  item_code: string;
  listing_id: string;
  listing_code: string | null;
  batch_id: string;
  batch_code: string | null;
  vintage: string | null;
  project_code: string | null;
  quantity: number;
  unit_price: string;
  line_total: string;
  status: 'RESERVED' | 'TRANSFER_PENDING' | 'DELIVERED' | 'FAILED' | 'RELEASED' | 'EXPIRED';
  reservation_code: string | null;
  reservation_status: string | null;
  transfer_id: string | null;
  transfer_code: string | null;
  transfer_status: string | null;
  can_complete: boolean;
}

export interface Payment {
  id: string;
  payment_code: string;
  order_id: string;
  order_code: string | null;
  adapter_code: string;
  amount: string;
  currency: string;
  status: string;
  external_reference: string | null;
  evidence_document_id: string | null;
  recorded_by_name: string | null;
  recorded_at: string;
  confirmed_by_name: string | null;
  confirmed_at: string | null;
  reject_reason: string | null;
  payer_name: string | null;
  payee_name: string | null;
  can_confirm: boolean;
  can_refund: boolean;
}

export interface Refund {
  id: string;
  refund_code: string;
  payment_id: string;
  payment_code: string | null;
  order_id: string;
  order_code: string | null;
  amount: string;
  currency: string;
  after_transfer: boolean;
  reason: string;
  status: 'REQUESTED' | 'APPROVED' | 'COMPLETED' | 'REJECTED';
  requested_by_name: string | null;
  approved_by_name: string | null;
  completed_at: string | null;
  external_reference: string | null;
  reject_reason: string | null;
  can_approve: boolean;
  can_complete: boolean;
}

export interface Order {
  id: string;
  order_code: string;
  buyer_organization_id: string;
  buyer_name: string | null;
  seller_organization_id: string;
  seller_name: string | null;
  currency: string;
  subtotal: string;
  total: string;
  status: 'PLACED' | 'PAID' | 'TRANSFER_PENDING' | 'COMPLETED' | 'CANCELLED' | 'EXPIRED' | 'ATTENTION_REQUIRED' | 'REFUND_PENDING' | 'REFUNDED';
  transfer_kind: 'INTERNAL' | 'REGISTRY';
  recipient_registry_account: string | null;
  expires_at: string;
  placed_at: string;
  paid_at: string | null;
  completed_at: string | null;
  close_reason: string | null;
  attention_reason: string | null;
  items: OrderItem[];
  payments: Payment[];
  refunds: Refund[];
  documents: DocumentRef[];
  environment: string;
  viewer_side: 'BUYER' | 'SELLER' | 'NONE';
  can_cancel: boolean;
  can_pay: boolean;
  can_retry: boolean;
}

export interface Orders { orders: Order[]; demo_note: string | null }
export interface LineageStep { kind: string; code?: string | null; status?: string | null; [k: string]: unknown }

export function marketBadge(status: string): string {
  return ({ ACTIVE: 'ACTIVE', KYC_VERIFIED: 'ACTIVE', CONFIRMED: 'ACTIVE', COMPLETED: 'ACTIVE', DELIVERED: 'ACTIVE', APPROVED: 'ACTIVE',
    DRAFT: 'INFO', PENDING_APPROVAL: 'WARNING', KYC_SUBMITTED: 'WARNING', PLACED: 'WARNING', RESERVED: 'WARNING', PAID: 'WARNING',
    TRANSFER_PENDING: 'WARNING', PENDING_CONFIRMATION: 'WARNING', REQUESTED: 'WARNING', REFUND_PENDING: 'WARNING', PENDING: 'WARNING',
    UNCONFIRMED: 'WARNING', PAUSED: 'ARCHIVED', CLOSED: 'ARCHIVED', EXPIRED: 'ARCHIVED', CANCELLED: 'ARCHIVED', RELEASED: 'ARCHIVED',
    REFUNDED: 'ARCHIVED', KYC_RETURNED: 'FAILED', SUSPENDED: 'FAILED', REJECTED: 'FAILED', FAILED: 'FAILED', UNMATCHED: 'FAILED',
    ATTENTION_REQUIRED: 'FAILED' } as Record<string, string>)[status] ?? 'INFO';
}

/** Display a decimal money string with its currency (no float arithmetic — the server computes every amount). */
export function money(amount: string | null | undefined, currency: string): string {
  if (amount === null || amount === undefined) return '—';
  const [whole, frac = ''] = amount.split('.');
  const trimmed = frac.replace(/0+$/, '');
  const decimals = trimmed.length < 2 && currency !== 'JPY' && currency !== 'KRW' ? trimmed.padEnd(2, '0') : trimmed;
  return `${whole}${decimals ? '.' + decimals : ''} ${currency}`;
}

export function newKey(): string {
  return globalThis.crypto?.randomUUID?.() ?? `k-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

/** Status labels for the marketplace (keeps "KYC" upper-case). */
export function mlabel(code: string | null | undefined): string {
  return label(code).replace(/^Kyc/, 'KYC');
}
