/** Methodology catalog + project candidate selection (Phase 4). The server is the source of truth for every rule. */

export type VersionStatus = 'DRAFT' | 'IN_REVIEW' | 'APPROVED' | 'SUPERSEDED' | 'RETIRED' | 'WITHDRAWN';
export type Outcome = 'APPLICABLE' | 'NOT_APPLICABLE' | 'NEEDS_INFORMATION' | 'EVIDENCE_REQUIRED';
export type RuleKind = 'applicability' | 'monitoring' | 'calculation' | 'general';

export const RULE_CATEGORIES = ['STANDARD', 'ACTIVITY', 'COUNTRY', 'GEOGRAPHY', 'LAND_USE', 'HISTORICAL_PRACTICE', 'CURRENT_PRACTICE',
  'PROPOSED_PRACTICE', 'START_DATE', 'DATA_AVAILABILITY', 'BASELINE', 'ADDITIONALITY', 'MONITORING', 'QUANTIFICATION', 'SAMPLING',
  'EVIDENCE', 'OTHER'] as const;
export const OPERATORS = ['EQUALS', 'NOT_EQUALS', 'IN', 'NOT_IN', 'ANY_IN', 'ALL_IN', 'NONE_IN', 'GTE', 'LTE', 'BETWEEN',
  'DATE_ON_OR_AFTER', 'DATE_ON_OR_BEFORE', 'IS_TRUE', 'IS_FALSE', 'EXISTS'] as const;
export const CALC_STEPS = ['BASELINE', 'PROJECT', 'EMISSIONS', 'REMOVALS', 'LEAKAGE', 'UNCERTAINTY', 'ADJUSTMENT', 'NET'] as const;
export const GENERAL_RULE_TYPES = ['CREDITING_PERIOD', 'BASELINE', 'ADDITIONALITY', 'LEAKAGE', 'UNCERTAINTY', 'SAMPLING', 'PERMANENCE',
  'GENERAL'] as const;
/** Facts the server derives from project data (docs/methodology-engine.md). Others can be declared. */
export const SYSTEM_FACTS = ['standard_code', 'activity_code', 'country', 'project_type', 'project_start_date', 'farm_count', 'farm_countries',
  'farm_states', 'farm_districts', 'farms_all_verified', 'project_area_ha', 'land_use_current', 'land_use_all_years',
  'land_use_history_years_min', 'crop_history_years_min', 'crops', 'historical_practice_categories', 'historical_practice_types',
  'current_practice_categories', 'current_practice_types', 'proposed_practice_categories', 'proposed_practice_types', 'baseline_recorded',
  'baseline_period_years', 'crediting_period_years', 'carbon_rights_all_verified', 'verified_evidence_count'] as const;

export interface VersionInfo {
  id: string;
  methodology_id: string;
  version_number: number;
  version_label: string;
  status: VersionStatus;
  effective_from: string | null;
  effective_to: string | null;
  source_name: string | null;
  source_url: string | null;
  source_document_id: string | null;
  rules_version: number;
  monitoring_rules_version: number;
  calculation_rules_version: number;
  calculation_readiness: 'NOT_PRODUCTION_READY' | 'PRODUCTION_READY';
  is_demo_illustrative: boolean;
  notes: string | null;
  based_on_version_id: string | null;
  created_at: string;
  submitted_by: string | null;
  submitted_at: string | null;
  approved_by: string | null;
  approved_at: string | null;
  superseded_at: string | null;
  superseded_by_id: string | null;
  status_reason: string | null;
  rule_counts: Record<RuleKind, number>;
}

export interface Rule {
  id: string;
  kind: RuleKind;
  rule_code: string;
  title: string;
  description: string | null;
  source_reference: string | null;
  sort_order: number;
  data: Record<string, unknown>;
}

export interface VersionDetail extends VersionInfo {
  methodology_code: string;
  methodology_name: string;
  rules: Rule[];
  can_edit: boolean;
  can_submit: boolean;
  can_approve: boolean;
}

export interface Methodology {
  id: string;
  code: string;
  name: string;
  standard_id: string;
  standard_name: string | null;
  activity_ids: string[];
  owner_name: string | null;
  description: string | null;
  source_url: string | null;
  status: 'ACTIVE' | 'INACTIVE';
  environment: 'LIVE' | 'DEMO';
  versions: VersionInfo[];
}

export interface Change {
  id: number;
  methodology_version_id: string | null;
  change_type: string;
  summary: string;
  reason: string | null;
  changed_at: string;
  request_id: string | null;
}

export interface RuleResult {
  rule_code: string;
  title: string;
  category: string;
  fact_key: string;
  operator: string;
  expected: unknown;
  actual: unknown;
  fact_source: string | null;
  check: 'PASS' | 'FAIL' | 'MISSING' | 'SKIPPED';
  effect: Outcome;
  reason: string;
  evidence_requirement: string | null;
  source_reference: string | null;
}

export interface Review {
  id: string;
  evaluation_result_id: string;
  recommendation: 'RECOMMENDED' | 'NOT_RECOMMENDED';
  notes: string;
  evidence_acknowledged: boolean;
  reviewer_name: string | null;
  reviewed_at: string;
}

export interface Candidate {
  id: string;
  methodology_id: string;
  methodology_code: string;
  methodology_name: string;
  methodology_version_id: string;
  version_label: string;
  version_status: string;
  calculation_readiness: string;
  is_demo_illustrative: boolean;
  outcome: Outcome;
  rules_version: number;
  rules: RuleResult[];
  evidence_requirements: string[];
  reviews: Review[];
}

export interface Evaluation {
  id: string;
  engine_version: string;
  facts: Record<string, { value: unknown; source: string; detail: string }>;
  candidate_count: number;
  evaluated_at: string;
  candidates: Candidate[];
  note: string;
}

export interface LockedMethodology {
  id: string;
  methodology_code: string;
  methodology_name: string;
  methodology_version_id: string;
  version_label: string;
  version_status: string;
  rules_version: number;
  monitoring_rules_version: number;
  calculation_rules_version: number;
  calculation_readiness: string;
  status: 'LOCKED' | 'UNLOCKED';
  confirmation_notes: string;
  locked_at: string;
  unlocked_at: string | null;
  unlock_reason: string | null;
  newer_version_available: boolean;
}

export interface ProjectMethodologyView {
  methodology_status: 'NOT_SELECTED' | 'UNDER_REVIEW' | 'CONFIRMED';
  project_status: string;
  current: LockedMethodology | null;
  history: LockedMethodology[];
  latest_evaluation: Evaluation | null;
  evaluation_count: number;
  can_evaluate: boolean;
  can_review: boolean;
  can_confirm: boolean;
  can_unlock: boolean;
  findings: string[];
}

export function outcomeBadge(o: string): string {
  return o === 'APPLICABLE' ? 'ACTIVE' : o === 'NOT_APPLICABLE' ? 'FAILED' : o === 'EVIDENCE_REQUIRED' ? 'WARNING' : 'INFO';
}

export function versionBadge(s: string): string {
  return s === 'APPROVED' ? 'ACTIVE' : s === 'IN_REVIEW' ? 'WARNING' : s === 'DRAFT' ? 'INFO' : 'REVOKED';
}

/** A candidate can be confirmed when its outcome allows it and its latest review recommends it. */
export function confirmable(c: Candidate): boolean {
  const last = c.reviews[c.reviews.length - 1];
  return (c.outcome === 'APPLICABLE' || c.outcome === 'EVIDENCE_REQUIRED') && last?.recommendation === 'RECOMMENDED';
}

/** Parse a declared fact typed in the UI: numbers, true/false and comma-separated lists. */
export function parseFactValue(raw: string): string | number | boolean | string[] {
  const v = raw.trim();
  if (v === 'true' || v === 'false') return v === 'true';
  if (v !== '' && !Number.isNaN(Number(v))) return Number(v);
  if (v.includes(',')) return v.split(',').map((x) => x.trim()).filter((x) => x);
  return v;
}

export function show(v: unknown): string {
  if (v === null || v === undefined) return '—';
  if (Array.isArray(v)) return v.length ? v.join(', ') : '(none)';
  return String(v);
}

/** Measurement provenance of a monitoring rule (decision V2-A) — declared explicitly, never inferred. */
export const MEASUREMENT_SOURCES = ['FIELD', 'FIELD_ACTIVITY', 'LABORATORY'] as const;
