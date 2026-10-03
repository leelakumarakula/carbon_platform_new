/** Phase 8B — VVB / ACVA verification. Verification only: the platform records an external VVB's decision; nothing here is a credit. */
export const CALCULATED_LABEL = 'Calculated tCO2e — not verified, not issued';
export const VERIFIED_QUANTITY_LABEL = 'VVB-stated verified quantity';
export const VERIFIED_QUANTITY_NOTE = 'Recorded as stated in the VVB report. Not issued; not a credit.';
export const DECISION_NOTE = 'The platform records the external VVB decision; it does not verify.';

/** C13: exactly the six categories (same codes as Phase 8A); no severity scale. */
export const VFINDING_CATEGORIES: { code: string; label: string }[] = [
  { code: 'OBSERVATION', label: 'Observation' },
  { code: 'NON_CONFORMITY', label: 'Non-conformity' },
  { code: 'CLARIFICATION', label: 'Clarification' },
  { code: 'MISSING_EVIDENCE', label: 'Missing Evidence' },
  { code: 'CALCULATION_ISSUE', label: 'Calculation Issue' },
  { code: 'METHODOLOGY_ISSUE', label: 'Methodology Issue' },
];

export const TARGET_TYPES = ['SUBMISSION', 'MONITORING_PERIOD', 'CALCULATION_RUN', 'INPUT', 'OUTPUT', 'LAB_RESULT', 'MRV_EVIDENCE', 'DATASET',
  'CALCULATION_REPORT', 'METHODOLOGY', 'DOCUMENT'] as const;

export interface VvbOrg { id: string; name: string; code: string | null }

export interface Submission {
  id: string;
  submission_code: string;
  seq: number;
  status: 'SUBMITTED' | 'SUPERSEDED' | 'INVALIDATED';
  readiness_review_id: string;
  readiness_code: string | null;
  calculation_run_id: string;
  run_code: string | null;
  calculation_report_id: string;
  report_code: string | null;
  report_version: number | null;
  manifest_sha256: string;
  calculated_value: string | null;
  calculated_unit: string | null;
  calculated_label: string;
  submitted_by_name: string | null;
  submitted_at: string;
  closed_at: string | null;
  closed_reason: string | null;
  superseded_by_submission_id: string | null;
}

export interface Decision {
  id: string;
  decision_code: string;
  assignment_id: string;
  submission_id: string;
  submission_code: string | null;
  monitoring_period_id: string;
  vvb_organization_id: string;
  vvb_organization_name: string | null;
  outcome: 'VERIFIED' | 'NOT_VERIFIED';
  verified_quantity: string | null;
  verified_quantity_unit: string | null;
  verified_quantity_label: string;
  verified_quantity_note: string;
  rationale: string;
  report_document_id: string;
  report_sha256: string;
  manifest_sha256: string;
  decided_by_name: string | null;
  decided_at: string;
  status: 'CURRENT' | 'SUPERSEDED';
  superseded_at: string | null;
  superseded_reason: string | null;
  note: string;
}

export interface Assignment {
  id: string;
  assignment_code: string;
  project_id: string;
  project_code: string | null;
  project_name: string | null;
  monitoring_period_id: string;
  period_number: number | null;
  period_start: string | null;
  period_end: string | null;
  vvb_organization_id: string;
  vvb_organization_name: string | null;
  status: 'PROPOSED' | 'ACCEPTED' | 'COMPLETED' | 'DECLINED' | 'WITHDRAWN' | 'TERMINATED';
  previous_assignment_id: string | null;
  notes: string | null;
  proposed_by_name: string | null;
  proposed_at: string;
  accepted_by_name: string | null;
  accepted_at: string | null;
  coi_declaration: string | null;
  coi_declared_by_name: string | null;
  coi_declared_at: string | null;
  completed_at: string | null;
  closed_side: string | null;
  closed_reason: string | null;
  closed_at: string | null;
  environment: string;
  current_submission: Submission | null;
  submissions: Submission[];
  decisions: Decision[];
  actions: string[];
  decision_blockers: string[];
}

export interface VEvent {
  seq: number;
  action: string;
  from_status: string | null;
  to_status: string;
  actor_name: string | null;
  actor_side: 'PROJECT' | 'VVB';
  occurred_at: string;
  note: string | null;
  document_id: string | null;
}

export interface CorrectiveAction {
  id: string;
  action_code: string;
  finding_id: string;
  description: string;
  due_date: string | null;
  overdue: boolean;
  status: 'REQUESTED' | 'RESPONDED' | 'ACCEPTED' | 'CANCELLED';
  requested_by_name: string | null;
  requested_at: string;
  response_text: string | null;
  response_document_id: string | null;
  responded_by_name: string | null;
  responded_at: string | null;
  reviewed_by_name: string | null;
  reviewed_at: string | null;
  review_note: string | null;
  events: VEvent[];
}

export interface VFinding {
  id: string;
  finding_code: string;
  assignment_id: string;
  submission_id: string;
  category: string;
  category_label: string;
  blocking: boolean;
  title: string;
  description: string;
  target_type: string;
  target_ref: string | null;
  status: 'OPEN' | 'RESPONDED' | 'CLOSED';
  raised_by_name: string | null;
  raised_at: string;
  response_text: string | null;
  response_document_id: string | null;
  responded_by_name: string | null;
  responded_at: string | null;
  closure_note: string | null;
  closed_by_name: string | null;
  closed_at: string | null;
  events: VEvent[];
  corrective_actions: CorrectiveAction[];
}

export interface VDocument {
  document_id: string;
  source: string;
  category: string;
  title: string;
  status: string;
  file_name: string | null;
  mime_type: string | null;
  size_bytes: number | null;
  sha256: string | null;
  uploaded_at: string | null;
}

export interface Farm { farm_id: string; farm_code: string; farmer_code: string | null; area_hectares: string | null; boundary_version: number | null }

export interface Package {
  submission: Submission;
  label: string;
  project: { code: string; name: string; environment: string };
  period: { id: string; number: number; start_date: string; end_date: string } | null;
  manifest: Record<string, unknown>;
  manifest_sha256: string;
  methodology: { code: string | null; version_label: string | null; is_demo_illustrative: boolean | null; calculation_rules_version: string | null };
  calculation: {
    run: Record<string, unknown> | null;
    inputs: { id: string; seq: number; variable_code: string; source_type: string; source_code: string | null; value: string; unit: string | null; level: string }[];
    outputs: { id: string; seq: number; step: string; output_code: string; rule_code: string; value: string; unit: string; is_final: boolean }[];
  };
  report: { id: string; report_code: string; version: number; content_sha256: string; pdf_sha256: string; document_id: string } | null;
  dataset: { ref: Record<string, unknown>; sampling_points: { id: string; code: string; lat: string; lon: string }[]; field_collections: { id: string; code: string }[] };
  farms: Farm[];
  laboratory_results: { result_id: string; version: number; sample: string | null; value_number: string | null; value_text: string | null; unit: string | null; method_reported: string | null }[];
  documents: VDocument[];
}

export interface PeriodVerification {
  project_id: string;
  project_status: string;
  monitoring_period_id: string;
  period_number: number;
  ready_review_code: string | null;
  calculated_value: string | null;
  calculated_unit: string | null;
  calculated_label: string;
  assignments: Assignment[];
  current_decision: Decision | null;
  submit_blockers: string[];
  can_manage: boolean;
  can_respond: boolean;
}

export interface Lineage { decision: Record<string, unknown>; chain: Record<string, unknown>[] }

export function assignmentBadge(status: string): string {
  return { PROPOSED: 'INFO', ACCEPTED: 'WARNING', COMPLETED: 'ACTIVE', DECLINED: 'ARCHIVED', WITHDRAWN: 'ARCHIVED', TERMINATED: 'FAILED' }[status] ?? 'INFO';
}

export function submissionBadge(status: string): string {
  return { SUBMITTED: 'ACTIVE', SUPERSEDED: 'ARCHIVED', INVALIDATED: 'FAILED' }[status] ?? 'INFO';
}

export function findingBadge(status: string): string {
  return { OPEN: 'WARNING', RESPONDED: 'INFO', CLOSED: 'ACTIVE', REQUESTED: 'WARNING', ACCEPTED: 'ACTIVE', CANCELLED: 'ARCHIVED' }[status] ?? 'INFO';
}

export function decisionBadge(d: Pick<Decision, 'outcome' | 'status'>): string {
  if (d.status === 'SUPERSEDED') return 'ARCHIVED';
  return d.outcome === 'VERIFIED' ? 'ACTIVE' : 'FAILED';
}

/** The VVB-stated quantity is shown only with its label and unit — never as an issued credit. */
export function statedQuantity(d: Pick<Decision, 'verified_quantity' | 'verified_quantity_unit'>): string | null {
  return d.verified_quantity === null ? null : `${d.verified_quantity} ${d.verified_quantity_unit ?? ''}`.trim();
}
