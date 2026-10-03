/** Phase 8A — internal pre-verification. Internal only: READY is not verification, and nothing here is a credit. */
import { CalcBlocker } from './calculation.models';

export const READINESS_LABEL = 'Internal readiness — not verification';

/** B3: exactly the six categories of the specification. */
export const FINDING_CATEGORIES: { code: string; label: string }[] = [
  { code: 'OBSERVATION', label: 'Observation' },
  { code: 'NON_CONFORMITY', label: 'Non-conformity' },
  { code: 'CLARIFICATION', label: 'Clarification' },
  { code: 'MISSING_EVIDENCE', label: 'Missing Evidence' },
  { code: 'CALCULATION_ISSUE', label: 'Calculation Issue' },
  { code: 'METHODOLOGY_ISSUE', label: 'Methodology Issue' },
];

export interface FindingEvent {
  seq: number;
  action: string;
  from_status: string | null;
  to_status: string;
  actor_name: string | null;
  occurred_at: string;
  note: string | null;
  document_id: string | null;
  run_id: string | null;
}

export interface Finding {
  id: string;
  finding_code: string;
  run_id: string;
  run_code: string;
  category: string;
  category_label: string;
  blocking: boolean;
  title: string;
  description: string;
  target_input_seq: number | null;
  target_output_seq: number | null;
  target_rule_code: string | null;
  target_source_type: string | null;
  evidence_document_id: string | null;
  status: 'OPEN' | 'RESPONDED' | 'RESOLVED' | 'WITHDRAWN';
  raised_by_name: string | null;
  raised_at: string;
  response_text: string | null;
  responded_by_name: string | null;
  resolution_note: string | null;
  resolved_by_name: string | null;
  withdraw_reason: string | null;
  environment: string;
  events: FindingEvent[];
  can_respond: boolean;
  can_resolve: boolean;
  can_return: boolean;
  can_reopen: boolean;
  can_withdraw: boolean;
}

export interface CalcReport {
  id: string;
  report_code: string;
  run_id: string;
  run_code: string;
  version: number;
  generator_version: string;
  content_sha256: string;
  pdf_sha256: string;
  document_id: string;
  status: 'CURRENT' | 'SUPERSEDED';
  superseded_by_report_id: string | null;
  generated_by_name: string | null;
  generated_at: string;
  label: string;
}

export interface ReportVerify {
  report_id: string;
  report_code: string;
  valid: boolean;
  problems: string[];
  stale: boolean;
  content_sha256: string;
  pdf_sha256: string;
  stored_pdf_sha256: string | null;
}

export interface ReadinessCheck {
  key: string;
  label: string;
  result: 'PASS' | 'FAIL' | 'WARN';
  details: string[];
}

export interface ReadinessReview {
  id: string;
  readiness_code: string;
  run_id: string;
  run_code: string;
  report_code: string | null;
  status: 'DRAFT' | 'SUBMITTED' | 'READY' | 'REJECTED' | 'WITHDRAWN' | 'INVALIDATED';
  checks: ReadinessCheck[];
  manifest_sha256: string | null;
  created_by_name: string | null;
  created_at: string;
  submitted_by_name: string | null;
  decided_by_name: string | null;
  decided_at: string | null;
  decision_notes: string | null;
  withdraw_reason: string | null;
  invalidation_reason: string | null;
  label: string;
  meaning: string;
  can_submit: boolean;
  can_approve: boolean;
  can_reject: boolean;
  can_withdraw: boolean;
}

export interface ReadinessState {
  project_id: string;
  project_code: string;
  project_status: string;
  monitoring_period_id: string;
  environment: string;
  label: string;
  meaning: string;
  current_run_id: string | null;
  current_run_code: string | null;
  current_report_id: string | null;
  ready_to_submit: boolean;
  blockers: CalcBlocker[];
  checks: ReadinessCheck[];
  calculation_blockers: CalcBlocker[];
  open_blocking_findings: string[];
  reviews: ReadinessReview[];
  can_create: boolean;
}

export interface Manifest {
  readiness_id: string;
  readiness_code: string;
  status: string;
  manifest_sha256: string | null;
  manifest: Record<string, unknown> | null;
  label: string;
}

export function findingBadge(status: string): string {
  return { OPEN: 'WARNING', RESPONDED: 'INFO', RESOLVED: 'ACTIVE', WITHDRAWN: 'ARCHIVED' }[status] ?? 'INFO';
}

export function readinessBadge(status: string): string {
  return { READY: 'ACTIVE', SUBMITTED: 'WARNING', DRAFT: 'INFO', REJECTED: 'FAILED', INVALIDATED: 'FAILED', WITHDRAWN: 'ARCHIVED' }[status] ?? 'INFO';
}
