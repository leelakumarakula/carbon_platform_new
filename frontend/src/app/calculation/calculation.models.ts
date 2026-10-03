/** Phase 7 — carbon calculation. Every value is computed by the server from frozen inputs; the client never sends one. */

export const CALCULATED_LABEL = 'Calculated tCO2e — not verified, not issued';
export const DEMO_LABEL = 'DEMO — not carbon accounting';

export interface CalcProject {
  id: string;
  project_code: string;
  name: string;
  status: string;
  environment: string;
  periods: { id: string; name: string; period_number: number; status: string; start_date: string; end_date: string }[];
}

export interface CalcBlocker {
  code: string;
  message: string;
  reason: string | null;
  details: Record<string, unknown>;
}

export interface StepStatus {
  step: string;
  status: 'IMPLEMENTED' | 'NOT_INCLUDED_DEMO' | 'NOT_CONFIGURED' | string;
  rule_code: string | null;
  label: string;
}

export interface Readiness {
  project_id: string;
  project_code: string;
  project_status: string;
  environment: string;
  monitoring_period_id: string;
  monitoring_period: string;
  methodology_label: string | null;
  is_demo_illustrative: boolean;
  module_code: string | null;
  module_version: string | null;
  module_readiness: string | null;
  dataset_id: string | null;
  dataset_code: string | null;
  dataset_status: string | null;
  ready: boolean;
  blockers: CalcBlocker[];
  warnings: string[];
  steps: StepStatus[];
  input_rows: number;
  calculation_rules: { rule_code: string; step: string; title: string; equation_reference: string | null; implementation_status: string }[];
}

export interface CalcRun {
  id: string;
  run_code: string;
  project_id: string;
  project_code: string;
  monitoring_period_id: string;
  monitoring_period: string;
  period_start: string;
  period_end: string;
  crediting_period_id: string | null;
  mrv_dataset_id: string | null;
  dataset_code: string | null;
  methodology_label: string;
  methodology_version_id: string;
  is_demo_illustrative: boolean;
  calculation_rules_version: number;
  module_code: string | null;
  module_version: string | null;
  module_readiness: string | null;
  engine_version: string;
  input_sha256: string | null;
  output_sha256: string | null;
  net_result: string | null;
  net_unit: string | null;
  status: string;
  status_reason: string | null;
  blockers: CalcBlocker[];
  notes: string | null;
  recalculation_of_run_id: string | null;
  recalculation_of_code: string | null;
  recalculation_reason: string | null;
  superseded_by_run_id: string | null;
  superseded_by_code: string | null;
  superseded_at: string | null;
  environment: string;
  created_by_name: string | null;
  created_at: string;
  frozen_by_name: string | null;
  frozen_at: string | null;
  executed_by_name: string | null;
  executed_at: string | null;
  submitted_by_name: string | null;
  submitted_at: string | null;
  approved_by_name: string | null;
  approved_at: string | null;
  closed_by_name: string | null;
  closed_at: string | null;
  result_label: string;
  demo_label: string | null;
  steps: StepStatus[];
  can_freeze: boolean;
  can_execute: boolean;
  can_submit: boolean;
  can_cancel: boolean;
  can_review: boolean;
  can_approve: boolean;
  can_recalculate: boolean;
}

export interface CalcInput {
  seq: number;
  variable_code: string;
  source_type: string;
  source_id: string | null;
  source_version: number | null;
  source_code: string | null;
  value: string;
  value_kind: string;
  unit: string | null;
  level: string;
  requirement_source: string | null;
  source_reference: string | null;
  source_sha256: string | null;
}

export interface CalcInputs {
  run_id: string;
  input_sha256: string | null;
  snapshot: Record<string, unknown> | null;
  inputs: CalcInput[];
}

export interface CalcOutput {
  seq: number;
  step: string;
  output_code: string;
  rule_code: string;
  equation_reference: string | null;
  value: string;
  unit: string;
  level: string;
  entity_id: string | null;
  input_seqs: number[];
  output_seqs: number[];
  is_final: boolean;
}

export interface CalcOutputs {
  run_id: string;
  output_sha256: string | null;
  net_result: string | null;
  net_unit: string | null;
  result_label: string;
  demo_label: string | null;
  steps: StepStatus[];
  outputs: CalcOutput[];
}

export interface CalcCheck {
  key: string;
  label: string;
  result: 'PASS' | 'FAIL' | 'WARN';
  details: string[];
}

export interface CalcQaReview {
  id: string;
  started_by_name: string | null;
  started_at: string;
  completed_by_name: string | null;
  completed_at: string | null;
  result: string | null;
  notes: string | null;
  checks: CalcCheck[];
}

export interface CalcQaView {
  run: CalcRun;
  checks: CalcCheck[];
  reviews: CalcQaReview[];
  can_start: boolean;
  can_complete: boolean;
  can_approve: boolean;
  blocked_reasons: string[];
}

export interface CalcLineage {
  run: CalcRun;
  methodology: { label: string; is_demo_illustrative: boolean; calculation_rules_version: number; rules: Record<string, unknown>[] };
  dataset: { code: string; version: number; snapshot_sha256: string } | null;
  final: { seq: number; output_code: string; value: string; unit: string; rule: Record<string, unknown> } | null;
  outputs: { seq: number; step: string; output_code: string; value: string; unit: string; rule: Record<string, unknown>; input_seqs: number[];
    output_seqs: number[]; is_final: boolean }[];
  inputs: { seq: number; variable_code: string; source_type: string; value: string; unit: string | null; chain: Record<string, unknown> }[];
  qa_reviews: CalcQaReview[];
  history: { from_status: string | null; to_status: string | null; user_name: string | null; at: string; reason: string | null }[];
}

export interface CalcCompare {
  run_a: CalcRun;
  run_b: CalcRun;
  same_inputs: boolean;
  same_outputs: boolean;
  changed_fields: Record<string, [string | null, string | null]>;
  inputs_added: Record<string, unknown>[];
  inputs_removed: Record<string, unknown>[];
  inputs_changed: { before: Record<string, unknown>; after: Record<string, unknown> }[];
  outputs_changed: { output_code: string; before: string | null; after: string | null; unit: string }[];
}

/** Badge tone for a calculation status / check result. */
export function calcBadge(status: string | null | undefined): string {
  if (!status) return 'INFO';
  if (['APPROVED', 'PASS', 'IMPLEMENTED', 'CALCULATED'].includes(status)) return 'ACTIVE';
  if (['BLOCKED', 'REJECTED', 'FAIL', 'NOT_CONFIGURED'].includes(status)) return 'FAILED';
  if (['SUPERSEDED', 'CANCELLED'].includes(status)) return 'ARCHIVED';
  if (['QA_REVIEW', 'INPUTS_FROZEN', 'WARN', 'NOT_INCLUDED_DEMO'].includes(status)) return 'WARNING';
  return 'INFO';
}

/** "CONFIGURATION_REQUIRED — NO_CALCULATION_MODULE": the code and, when present, its reason. */
export function blockerTitle(b: CalcBlocker): string {
  return b.reason ? `${b.code} — ${b.reason}` : b.code;
}

/** Display formatting only (the stored value is exact and never rounded): trailing zeros trimmed, at most `digits` decimals. */
export function formatValue(value: string | null, digits = 6): string {
  if (value === null || value === '') return '—';
  const [int, frac = ''] = value.split('.');
  const shown = frac.slice(0, digits).replace(/0+$/, '');
  return shown ? `${int}.${shown}${frac.length > digits ? '…' : ''}` : int;
}
