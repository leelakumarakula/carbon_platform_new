import type { GeoGeometry } from '../farms/farm.models';

/** Phase 5 — MRV, monitoring periods, stratification, sampling design, field collection. Nothing here is calculated. */

export interface MrvProjectSummary {
  project_id: string;
  project_code: string;
  project_name: string;
  project_status: string;
  organization_name: string | null;
  methodology_label: string | null;
  environment: string;
  approved_plan_version: number | null;
  plan_count: number;
  period_count: number;
  open_period: string | null;
  point_count: number;
  collected_count: number;
  dataset_status: string | null;
}

export interface Requirements {
  status: 'CONFIGURED' | 'CONFIGURATION_REQUIRED';
  gaps: string[];
  monitoring: { rule_code: string; title: string; parameter: string | null; unit: string | null; frequency: string | null }[];
  sampling: Record<string, { value: unknown; rule_code: string }>;
}

export const MEASUREMENT_CATEGORIES = ['SOIL', 'CROP', 'PLANTING', 'HARVEST', 'TILLAGE', 'FERTILIZER', 'MANURE', 'RESIDUE', 'IRRIGATION',
  'WATER_MANAGEMENT', 'YIELD', 'PRACTICE_CHANGE', 'FUEL', 'OTHER'] as const;
export const VALUE_TYPES = ['NUMBER', 'TEXT', 'DATE', 'BOOLEAN', 'CHOICE'] as const;
export const LEVELS = ['PROJECT', 'FARM', 'STRATUM', 'SAMPLING_POINT'] as const;
export const QUANTIFICATION = ['MEASURE_AND_REMEASURE', 'MEASURE_AND_MODEL', 'OTHER'] as const;
export const DESIGNS = ['STRATIFIED_RANDOM', 'SIMPLE_RANDOM', 'SYSTEMATIC_GRID', 'OTHER'] as const;
export const CHARACTERISTICS = ['SOIL_TYPE', 'CROP', 'LAND_USE', 'MANAGEMENT_PRACTICE', 'IRRIGATION', 'GEOGRAPHY', 'CLIMATE', 'OTHER'] as const;
export const EVIDENCE_TYPES = ['FIELD_PHOTO', 'FIELD_NOTE', 'PRACTICE_RECORD', 'DOCUMENT', 'GPS', 'OBSERVATION'] as const;

export interface Measurement {
  id: string;
  code: string;
  name: string;
  category: string;
  value_type: (typeof VALUE_TYPES)[number];
  unit: string | null;
  allowed_values: string[] | null;
  level: (typeof LEVELS)[number];
  frequency: string | null;
  required: boolean;
  source: 'METHODOLOGY' | 'PROJECT_CONFIGURED';
  monitoring_rule_id: string | null;
  /** Provenance declared by the methodology rule (decision V2-A); null for project-configured measurements. */
  measurement_source: 'FIELD' | 'FIELD_ACTIVITY' | 'LABORATORY' | 'UNCLASSIFIED' | null;
  /** Decision V2-B: user-created measurements are SUPPLEMENTARY_OBSERVATION — never lab results or authoritative calculation inputs. */
  data_role: DataRole;
  authoritative: boolean;
}

export type DataRole = 'METHODOLOGY_PARAMETER' | 'LABORATORY_PARAMETER' | 'UNCLASSIFIED_PARAMETER' | 'SUPPLEMENTARY_OBSERVATION';

export function dataRoleLabel(role: DataRole | undefined): string {
  return ({ METHODOLOGY_PARAMETER: 'Methodology (authoritative)', LABORATORY_PARAMETER: 'Laboratory — approved lab result only',
    UNCLASSIFIED_PARAMETER: 'Methodology — source not classified', SUPPLEMENTARY_OBSERVATION: 'Supplementary (not authoritative)' } as const)[
    role ?? 'SUPPLEMENTARY_OBSERVATION'];
}

/** LABORATORY values come only from approved lab results; UNCLASSIFIED ones must be classified first (server refuses both). */
export function capturableInMrv(m: Measurement): boolean {
  return m.measurement_source !== 'LABORATORY' && m.measurement_source !== 'UNCLASSIFIED';
}

export interface Plan {
  id: string;
  project_id: string;
  project_code: string;
  plan_version: number;
  status: 'DRAFT' | 'SUBMITTED' | 'APPROVED' | 'SUPERSEDED' | 'WITHDRAWN';
  methodology_id: string;
  methodology_version_id: string;
  methodology_label: string;
  monitoring_frequency: string | null;
  monitoring_start: string | null;
  monitoring_end: string | null;
  quantification_approach: string;
  sampling_requirements_ref: string | null;
  required_evidence: string | null;
  configuration_status: 'CONFIGURED' | 'CONFIGURATION_REQUIRED';
  configuration_gaps: string[];
  notes: string | null;
  supersedes_id: string | null;
  created_at: string;
  submitted_at: string | null;
  approved_at: string | null;
  status_reason: string | null;
  measurements: Measurement[];
  can_edit: boolean;
  can_submit: boolean;
  can_approve: boolean;
  /** Decision V1 (platform governance): gaps may be acknowledged for DEMO / non-production only. */
  gap_approval_policy: 'ACKNOWLEDGE_ALLOWED' | 'PRODUCTION_BLOCK';
  approval_blockers: string[];
  gaps_acknowledged_by: string | null;
}

/** Field rules frozen on a design version / field record (decisions S1, S2). */
export interface FieldRules {
  gps_tolerance_m: number;
  gps_tolerance_source: RuleSource;
  duplicate_distance_m: number;
  duplicate_distance_source: RuleSource;
  min_photos: number;
  min_photos_source: RuleSource;
  checklist_version: string;
  checklist_items: { key: string; label: string }[];
  checklist_source: RuleSource;
  note: string;
}
export type RuleSource = 'PLATFORM_DEFAULT' | 'METHODOLOGY';

export type PeriodStatus = 'DRAFT' | 'PLANNED' | 'ACTIVE' | 'DATA_COLLECTION' | 'SUBMITTED' | 'QA_REVIEW' | 'APPROVED' | 'REJECTED' | 'CLOSED';

export interface Period {
  id: string;
  project_id: string;
  project_code: string;
  mrv_plan_id: string;
  plan_version: number;
  methodology_version_id: string;
  period_number: number;
  name: string;
  purpose: string;
  start_date: string;
  end_date: string;
  status: PeriodStatus;
  status_reason: string | null;
  created_at: string;
  counts: Record<string, number>;
  allowed_transitions: PeriodStatus[];
}

export interface Characteristic {
  characteristic: (typeof CHARACTERISTICS)[number];
  value: string;
  source?: string | null;
}

export interface Stratum {
  id: string;
  record_id: string;
  project_id: string;
  version: number;
  is_current: boolean;
  code: string;
  name: string;
  description: string | null;
  geojson: GeoGeometry | null;
  area_hectares: string | null;
  farm_ids: string[];
  farm_codes: string[];
  characteristics: Characteristic[];
  missing_required_characteristics: string[];
  source: string;
  status: 'DRAFT' | 'APPROVED' | 'SUPERSEDED' | 'RETIRED';
  change_reason: string | null;
  created_by: string | null;
  created_at: string;
  approved_at: string | null;
}

export interface Allocation {
  stratum_id: string;
  stratum_code: string;
  stratum_area_hectares: string | null;
  sample_count: number;
  allocation_basis: string | null;
}

export interface DesignVersion {
  id: string;
  version: number;
  status: 'DRAFT' | 'APPROVED' | 'SUPERSEDED';
  statistical_design: string;
  target_precision_pct: string | null;
  confidence_level_pct: string | null;
  sampling_method: string | null;
  depth_top_cm: string;
  depth_bottom_cm: string;
  min_distance_m: string | null;
  random_seed: number;
  requirement_source: string;
  configuration_status: string;
  configuration_gaps: string[];
  notes: string | null;
  allocations: Allocation[];
  created_by: string | null;
  created_at: string;
  approved_at: string | null;
  points_generated_at: string | null;
  field_rules: FieldRules | null;
}

export interface Design {
  id: string;
  project_id: string;
  monitoring_period_id: string;
  monitoring_period_name: string;
  code: string;
  name: string;
  current: DesignVersion | null;
  versions: DesignVersion[];
  point_count: number;
}

export interface SamplingPoint {
  id: string;
  point_code: string;
  project_id: string;
  monitoring_period_id: string;
  design_version_id: string;
  stratum_id: string;
  stratum_code: string | null;
  farm_id: string;
  farm_code: string | null;
  farm_name: string | null;
  sequence: number;
  latitude: string;
  longitude: string;
  planned_depth_top_cm: string;
  planned_depth_bottom_cm: string;
  status: 'PLANNED' | 'ASSIGNED' | 'COLLECTED' | 'SKIPPED' | 'CANCELLED';
  assigned_collector_id: string | null;
  assigned_collector_name: string | null;
  planned_date: string | null;
  status_reason: string | null;
  pending_relocation: boolean;
  collection_id: string | null;
  collection_status: string | null;
}

export interface Relocation {
  id: string;
  sampling_point_id: string;
  old_latitude: string;
  old_longitude: string;
  new_latitude: string;
  new_longitude: string;
  distance_m: string;
  reason: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
  requested_at: string;
  reviewed_at: string | null;
  review_notes: string | null;
}

export interface Collector {
  id: string;
  full_name: string;
  email: string;
}

export interface FieldCollection {
  id: string;
  collection_code: string;
  sampling_point_id: string;
  point_code: string | null;
  monitoring_period_id: string;
  project_id: string;
  farm_id: string;
  collector_id: string;
  collector_name: string | null;
  version: number;
  supersedes_id: string | null;
  status: 'IN_PROGRESS' | 'SUBMITTED' | 'ACCEPTED' | 'RETURNED' | 'SUPERSEDED';
  collected_at: string | null;
  gps_latitude: string | null;
  gps_longitude: string | null;
  gps_accuracy_m: string | null;
  distance_from_point_m: string | null;
  gps_inside_farm: boolean | null;
  deviation_note: string | null;
  actual_depth_top_cm: string | null;
  actual_depth_bottom_cm: string | null;
  planned_depth_top_cm: string | null;
  planned_depth_bottom_cm: string | null;
  sample_quantity: string | null;
  sample_unit: string | null;
  observations: string | null;
  notes: string | null;
  checklist: Record<string, boolean> | null;
  required_checklist: string[];
  correction_reason: string | null;
  created_at: string;
  submitted_at: string | null;
  reviewed_at: string | null;
  review_notes: string | null;
  evidence_count: number;
  can_edit: boolean;
  can_review: boolean;
  checklist_version: string | null;
  checklist_items: { key: string; label: string }[];
  gps_tolerance_m: string | null;
  min_photos: number;
  field_rules: FieldRules | null;
  /** Sample-based methodology parameters (e.g. SOC) come from Phase 6 laboratory analysis — never entered here. */
  analysis_status: 'AWAITING_ANALYSIS' | null;
}

export interface MonitoringRecord {
  id: string;
  record_id: string;
  version: number;
  is_current: boolean;
  monitoring_period_id: string;
  measurement_id: string;
  measurement_code: string;
  measurement_name: string;
  farm_id: string | null;
  stratum_id: string | null;
  sampling_point_id: string | null;
  measurement_phase: string;
  value: unknown;
  unit: string | null;
  observed_on: string;
  source: string;
  status: string;
  notes: string | null;
  change_reason: string | null;
  recorded_at: string;
  data_role: DataRole;
  authoritative: boolean;
}

export interface Evidence {
  id: string;
  project_id: string;
  monitoring_period_id: string | null;
  entity_type: string;
  entity_id: string;
  evidence_type: string;
  document_id: string | null;
  checksum_sha256: string | null;
  latitude: string | null;
  longitude: string | null;
  captured_at: string | null;
  description: string | null;
  source: string;
  status: string;
  uploaded_at: string;
}

export interface QaCheck {
  key: string;
  label: string;
  result: 'PASS' | 'FAIL' | 'WARN';
  details: string[];
}

export interface QaReview {
  id: string;
  dataset_id: string;
  started_at: string;
  checks: QaCheck[] | null;
  result: string | null;
  notes: string | null;
  completed_at: string | null;
}

export interface Dataset {
  id: string;
  dataset_code: string;
  project_id: string;
  project_code: string;
  monitoring_period_id: string;
  monitoring_period_name: string;
  plan_version: number;
  methodology_label: string;
  version: number;
  supersedes_id: string | null;
  status: 'DRAFT' | 'COLLECTING' | 'SUBMITTED' | 'QA_REVIEW' | 'APPROVED' | 'REJECTED' | 'SUPERSEDED';
  snapshot_summary: Record<string, number> | null;
  snapshot_sha256: string | null;
  configuration_gaps: string[];
  notes: string | null;
  status_reason: string | null;
  environment: string;
  created_at: string;
  submitted_at: string | null;
  approved_at: string | null;
  allowed_actions: string[];
}

export interface QaView {
  dataset: Dataset;
  checks: QaCheck[];
  reviews: QaReview[];
  can_start: boolean;
  can_complete: boolean;
  can_approve: boolean;
}

export interface MrvHistoryEntry {
  id: number;
  occurred_at: string;
  user_email: string | null;
  action: string;
  entity_type: string;
  reason: string | null;
  new_value: Record<string, unknown> | null;
}

/** Badge tone for any MRV status. */
export function mrvBadge(status: string | null | undefined): string {
  if (!status) return 'INFO';
  if (['APPROVED', 'ACCEPTED', 'COLLECTED', 'PASS', 'CONFIGURED', 'COMPLETED'].includes(status)) return 'ACTIVE';
  if (['REJECTED', 'FAIL', 'RETURNED', 'CANCELLED'].includes(status)) return 'FAILED';
  if (['SUPERSEDED', 'WITHDRAWN', 'CLOSED', 'SKIPPED', 'RETIRED'].includes(status)) return 'ARCHIVED';
  if (['SUBMITTED', 'QA_REVIEW', 'PENDING', 'WARN', 'CONFIGURATION_REQUIRED', 'REQUIRES_CORRECTION'].includes(status)) return 'WARNING';
  return 'INFO';
}

/** Monitoring-period workflow buttons (server checks permissions and order). */
export const PERIOD_ACTIONS: Partial<Record<PeriodStatus, { action: string; label: string }>> = {
  PLANNED: { action: 'plan', label: 'Mark planned' },
  ACTIVE: { action: 'start', label: 'Start period' },
  DATA_COLLECTION: { action: 'open-collection', label: 'Open data collection' },
  CLOSED: { action: 'close', label: 'Close period' },
};

export const CHECKLIST_LABELS: Record<string, string> = {
  location_confirmed: 'Location confirmed on site',
  depth_measured: 'Sampling depth measured',
  sample_labelled: 'Sample bag labelled with the collection code',
  photo_taken: 'Field photo taken',
};

/** "30 m (platform default)" / "10 m (methodology)". */
export function ruleSourceLabel(source: RuleSource | undefined): string {
  return source === 'METHODOLOGY' ? 'methodology' : 'platform default';
}

/** What a collector still has to do before submitting, using the rules frozen on the record (the server decides). */
export function collectionMissing(c: FieldCollection, photoCount: number): string[] {
  const out: string[] = [];
  if (!c.collected_at) out.push('collection time');
  if (c.gps_latitude === null || c.gps_longitude === null) out.push('GPS position');
  if (c.actual_depth_top_cm === null || c.actual_depth_bottom_cm === null) out.push('actual depth');
  const labels = new Map(c.checklist_items.map((i) => [i.key, i.label]));
  const missing = c.required_checklist.filter((k) => !c.checklist?.[k]);
  if (missing.length) out.push(`checklist (${missing.map((k) => labels.get(k) ?? CHECKLIST_LABELS[k] ?? k).join(', ')})`);
  const photos = Math.max(photoCount, c.evidence_count);
  const minPhotos = c.min_photos || 1;
  if (photos < minPhotos) out.push(minPhotos === 1 ? 'a field photo' : `${minPhotos - photos} more field photo(s) (${minPhotos} required)`);
  const tolerance = c.gps_tolerance_m !== null ? Number(c.gps_tolerance_m) : 30;
  const far = c.distance_from_point_m !== null && Number(c.distance_from_point_m) > tolerance;
  if ((far || c.gps_inside_farm === false) && !c.deviation_note) out.push('a note explaining the GPS deviation');
  return out;
}

/** Parse a typed measurement value from a form string. */
export function parseMeasurementValue(m: Measurement, raw: string): string | number | boolean | null {
  const v = raw.trim();
  if (!v) return null;
  if (m.value_type === 'NUMBER') return Number(v);
  if (m.value_type === 'BOOLEAN') return v === 'true' || v === 'yes';
  return v;
}

export function pointColor(p: SamplingPoint): string {
  if (p.status === 'COLLECTED') return '#2e7d32';
  if (p.status === 'ASSIGNED') return '#1565c0';
  if (p.status === 'SKIPPED' || p.status === 'CANCELLED') return '#9e9e9e';
  return '#e65100';
}
