/** Phase 9A — registry submission & credit issuance. Three quantities are shown side by side and never derived from one another:
 *  calculated (Phase 7) ≠ VVB-stated verified (Phase 8B) ≠ registry-issued (this phase). No inventory, transfer or retirement. */
export const CALCULATED_LABEL = 'Calculated tCO2e — not verified, not issued';
export const VERIFIED_LABEL = 'VVB-stated verified quantity';
export const ISSUED_LABEL = 'Registry-issued credits';
export const DEMO_NOTE = 'DEMO — no registry issuance';

export interface Quantity { label: string; value: string | null; unit: string | null; note: string | null }
export interface Blocker { code: string; message: string }
export interface OrgRef { id: string; code: string; name: string }

export interface ChecklistItem { code: string; title: string; source: 'REGISTRY_SUBMISSION' | 'VERIFICATION_REPORT' | 'CALCULATION_REPORT'; satisfied?: boolean }

export interface Account {
  id: string;
  organization_id: string;
  registry_organization_id: string;
  registry_name: string | null;
  external_account_id: string;
  label: string;
  adapter_code: string;
  adapter_mode: 'API' | 'MANUAL' | null;
  credit_unit: string | null;
  verified_unit_equivalent: string | null;
  document_checklist: ChecklistItem[] | null;
  status: 'ACTIVE' | 'CLOSED';
  created_at: string;
  closed_reason: string | null;
  environment: string;
}

export interface Registration {
  id: string;
  registration_code: string;
  project_id: string;
  registry_account_id: string;
  registry_organization_id: string;
  registry_name: string | null;
  status: 'PENDING' | 'REGISTERED' | 'REJECTED';
  external_project_id: string | null;
  registered_on: string | null;
  evidence_document_id: string | null;
  response_reason: string | null;
  notes: string | null;
  recorded_by_name: string | null;
  recorded_at: string | null;
  created_at: string;
  label: string;
}

export interface RegistryEvent {
  id: string;
  event_type: string;
  occurred_at: string;
  actor_name: string | null;
  adapter_code: string;
  idempotency_key: string | null;
  external_ref: string | null;
  payload_sha256: string | null;
  outcome: string | null;
  checklist_item: string | null;
  note: string | null;
  document_id: string | null;
}

export interface SerialRange { seq: number; serial_start: string | null; serial_end: string | null; quantity: number; parsed: boolean; is_current: boolean }

export interface Batch {
  id: string;
  batch_code: string;
  issuance_id: string;
  issuance_code: string | null;
  external_issuance_id: string | null;
  project_id: string;
  project_code: string | null;
  monitoring_period_id: string;
  period_number: number | null;
  registry_name: string | null;
  vintage: string;
  quantity: number;
  unit: string;
  status: 'RECORDED' | 'ISSUED' | 'VOIDED' | 'SUPERSEDED' | 'CANCELLED';
  issuance_date: string | null;
  serial_ranges: SerialRange[];
  source_superseded: boolean;
  environment: string;
  label: string;
  note: string;
}

export interface Issuance {
  id: string;
  issuance_code: string;
  registry_submission_id: string;
  external_issuance_id: string;
  issuance_date: string;
  quantity: number;
  unit: string;
  source: 'MANUAL' | 'API';
  evidence_document_id: string | null;
  api_response_sha256: string | null;
  status: 'RECORDED' | 'CONFIRMED' | 'VOIDED' | 'CORRECTED' | 'CANCELLED';
  corrects_issuance_id: string | null;
  corrected_by_issuance_id: string | null;
  correction_reason: string | null;
  recorded_by_name: string | null;
  recorded_at: string;
  confirmed_by_name: string | null;
  confirmed_at: string | null;
  void_reason: string | null;
  cancel_reason: string | null;
  batches: Batch[];
  can_confirm: boolean;
  label: string;
}

export type SubmissionStatus = 'DRAFT' | 'FROZEN' | 'SUBMITTING' | 'SUBMISSION_UNCONFIRMED' | 'SUBMITTED' | 'ACCEPTED' | 'REJECTED' | 'WITHDRAWN'
  | 'CANCELLED' | 'INVALIDATED';

export interface Submission {
  id: string;
  submission_code: string;
  project_id: string;
  monitoring_period_id: string;
  registration_id: string;
  registration_code: string | null;
  external_project_id: string | null;
  registry_account_id: string;
  registry_name: string | null;
  verification_decision_id: string;
  decision_code: string | null;
  decision_status: string | null;
  previous_submission_id: string | null;
  status: SubmissionStatus;
  snapshot_sha256: string | null;
  idempotency_key: string | null;
  external_submission_id: string | null;
  submission_evidence_document_id: string | null;
  response_document_id: string | null;
  response_payload_sha256: string | null;
  external_response_ref: string | null;
  response_reason: string | null;
  created_at: string;
  frozen_at: string | null;
  submitted_at: string | null;
  response_at: string | null;
  closed_reason: string | null;
  source_superseded: boolean;
  environment: string;
}

export interface SubmissionDetail extends Submission {
  snapshot: Record<string, unknown> | null;
  events: RegistryEvent[];
  issuances: Issuance[];
  checklist: ChecklistItem[] | null;
  documents: { document_id: string; category: string; title: string; sha256: string | null; checklist_item: string | null; attached_at: string }[];
}

export interface PeriodRegistry {
  project_id: string;
  organization_id: string;
  project_status: string;
  environment: string;
  demo_note: string | null;
  monitoring_period_id: string;
  period_number: number;
  registry_status: string;
  calculated: Quantity;
  verified: Quantity;
  issued: Quantity[];
  remaining: Quantity | null;
  decision_code: string | null;
  eligibility: { registry_account_id: string | null; account_label: string | null; blockers: Blocker[]; warnings: Blocker[] }[];
  registrations: Registration[];
  submissions: Submission[];
  issuances: Issuance[];
  can_manage: boolean;
  can_confirm: boolean;
}

export interface RegistryProject { id: string; project_code: string; name: string; status: string; environment: string;
  periods: { id: string; number: number; name: string; status: string }[] }

export interface BatchLineage { batch: Batch; chain: Record<string, unknown>[]; sources: { farms: { farm_code: string; farmer_code: string | null }[] } | null;
  verification_lineage: Record<string, unknown> | null; calculation_lineage: Record<string, unknown> | null }

const OPEN: SubmissionStatus[] = ['DRAFT', 'FROZEN', 'SUBMITTING', 'SUBMISSION_UNCONFIRMED', 'SUBMITTED', 'ACCEPTED'];

export function isOpen(status: SubmissionStatus): boolean {
  return OPEN.includes(status);
}

export function submissionBadge(status: string): string {
  return ({ DRAFT: 'INFO', FROZEN: 'INFO', SUBMITTING: 'WARNING', SUBMISSION_UNCONFIRMED: 'WARNING', SUBMITTED: 'WARNING', ACCEPTED: 'ACTIVE',
    REJECTED: 'FAILED', WITHDRAWN: 'ARCHIVED', CANCELLED: 'ARCHIVED', INVALIDATED: 'FAILED' } as Record<string, string>)[status] ?? 'INFO';
}

export function issuanceBadge(status: string): string {
  return ({ RECORDED: 'WARNING', CONFIRMED: 'ACTIVE', ISSUED: 'ACTIVE', VOIDED: 'ARCHIVED', CORRECTED: 'ARCHIVED', SUPERSEDED: 'ARCHIVED',
    CANCELLED: 'FAILED', PENDING: 'INFO', REGISTERED: 'ACTIVE', REJECTED: 'FAILED' } as Record<string, string>)[status] ?? 'INFO';
}

/** Serial numbers are shown exactly as the registry supplied them — never generated or reformatted. */
export function serialText(r: SerialRange): string {
  return r.serial_start ? `${r.serial_start} – ${r.serial_end}` : 'serials not supplied by the registry';
}
