/** Farmer API shapes (backend: app/schemas/farmers.py). Identity and bank numbers only ever arrive masked. */

export type FarmerStatus = 'DRAFT' | 'REGISTERED' | 'KYC_PENDING' | 'KYC_VERIFIED' | 'ACTIVE' | 'SUSPENDED';

export interface ChecklistItem {
  key: string;
  label: string;
  done: boolean;
  required: boolean;
}

export interface TransitionReadiness {
  target: string;
  ready: boolean;
  items: ChecklistItem[];
}

export interface DocumentVersion {
  version: number;
  file_name: string;
  mime_type: string;
  size_bytes: number;
  checksum_sha256: string;
  scan_status: string;
  uploaded_by: string | null;
  uploaded_at: string;
}

export interface DocumentInfo {
  id: string;
  entity_type: string;
  entity_id: string;
  category: string;
  title: string;
  sensitivity: 'RESTRICTED' | 'INTERNAL';
  status: string;
  current_version: number;
  environment: string;
  created_at: string;
  versions: DocumentVersion[];
}

export interface Contact {
  id: string;
  contact_type: string;
  value: string;
  label: string | null;
  is_primary: boolean;
  is_active: boolean;
  created_at: string;
}

export interface Consent {
  id: string;
  consent_type: string;
  consent_text_version: string;
  language: string | null;
  capture_method: string;
  document_id: string | null;
  status: 'GRANTED' | 'WITHDRAWN';
  captured_at: string;
  withdrawn_at: string | null;
  withdrawal_reason: string | null;
}

export interface Agreement {
  id: string;
  agreement_number: string;
  agreement_type: string;
  template_version: string;
  terms_summary: string | null;
  effective_from: string | null;
  effective_to: string | null;
  status: 'DRAFT' | 'SIGNED' | 'TERMINATED' | 'EXPIRED' | 'VOID';
  signed_at: string | null;
  signature_method: string | null;
  signed_document_id: string | null;
  created_at: string;
}

export interface BankAccount {
  id: string;
  account_holder_name: string;
  bank_name: string;
  branch_name: string | null;
  routing_code: string;
  account_number_masked: string;
  is_primary: boolean;
  status: 'PENDING_VERIFICATION' | 'VERIFIED' | 'REJECTED' | 'INACTIVE';
  proof_document_id: string | null;
  verified_at: string | null;
  review_notes: string | null;
  created_at: string;
}

export interface Kyc {
  id_type: string | null;
  id_number_masked: string | null;
  document_id: string | null;
  possible_duplicate: boolean;
  submitted_at: string | null;
  submitted_by: string | null;
  verified_at: string | null;
  verified_by: string | null;
  notes: string | null;
}

export interface FarmerSummary {
  id: string;
  farmer_code: string;
  full_name: string;
  village: string | null;
  district: string | null;
  state: string | null;
  country: string;
  status: FarmerStatus;
  organization_id: string;
  organization_name: string | null;
  environment: 'LIVE' | 'DEMO';
  farm_count: number;
  created_at: string;
}

export interface Farmer extends FarmerSummary {
  group_organization_id: string | null;
  user_id: string | null;
  gender: string | null;
  date_of_birth: string | null;
  preferred_language: string | null;
  participation_type: 'INDIVIDUAL' | 'GROUP_MEMBER';
  address_line: string | null;
  sub_district: string | null;
  postal_code: string | null;
  updated_at: string;
  kyc: Kyc;
  contacts: Contact[];
  consents: Consent[];
  agreements: Agreement[];
  bank_accounts: BankAccount[];
  documents: DocumentInfo[];
  allowed_transitions: string[];
  readiness: TransitionReadiness[];
  can_manage: boolean;
  can_verify_kyc: boolean;
  can_manage_bank: boolean;
  can_verify_bank: boolean;
  is_self: boolean;
}

export interface FarmerInput {
  organization_id?: string;
  full_name?: string;
  gender?: string | null;
  date_of_birth?: string | null;
  preferred_language?: string | null;
  participation_type?: 'INDIVIDUAL' | 'GROUP_MEMBER';
  address_line?: string | null;
  village?: string | null;
  sub_district?: string | null;
  district?: string | null;
  state?: string | null;
  postal_code?: string | null;
  country?: string;
  primary_phone?: string | null;
  email?: string | null;
}

export const KYC_ID_TYPES = ['NATIONAL_ID', 'VOTER_ID', 'TAX_ID', 'PASSPORT', 'DRIVING_LICENSE', 'OTHER'] as const;
export const CONSENT_METHODS = ['PAPER_SIGNED', 'DIGITAL_SIGNATURE', 'VERBAL_RECORDED', 'OTP', 'ONLINE_CHECKBOX'] as const;
export const CONSENT_TYPES = ['DATA_PROCESSING', 'DATA_SHARING_PROJECT', 'PHOTO_AND_MEDIA', 'COMMUNICATIONS'] as const;
export const FARMER_DOC_CATEGORIES = ['KYC_ID', 'CONSENT_FORM', 'AGREEMENT', 'BANK_PROOF', 'LAND_TITLE', 'LEASE_AGREEMENT',
  'LAND_RECORD', 'INPUT_RECORD', 'OTHER'] as const;

export function label(code: string | null | undefined): string {
  return (code ?? '').replace(/_/g, ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase());
}
