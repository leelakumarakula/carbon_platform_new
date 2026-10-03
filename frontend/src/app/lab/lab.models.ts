/** Phase 6 — laboratory & sample analysis. Project-side types carry lineage; laboratory-facing (`*LabView`) types are allow-lists. */

export interface RuleRef {
  rule_id: string;
  rule_code: string;
  parameter: string;
  unit: string | null;
  method: string | null;
  measurement_source: string;
}

export interface DocumentRef {
  document_id: string;
  category: string;
  title: string;
  file_name: string | null;
  sha256: string | null;
  uploaded_at: string | null;
}

export interface LabQaCheck {
  key: string;
  label: string;
  result: 'PASS' | 'FAIL' | 'WARN' | 'CONFIGURATION_REQUIRED';
  details: string[];
  acknowledgeable: boolean;
}

export interface Engagement {
  id: string;
  project_id: string;
  project_code: string;
  project_name: string;
  project_org_name: string;
  laboratory_org_id: string;
  laboratory_org_name: string;
  methodology_label: string;
  status: 'PROPOSED' | 'ACTIVE' | 'ENDED';
  replaces_engagement_id: string | null;
  notes: string | null;
  rules: RuleRef[];
  proposed_by_name: string | null;
  proposed_at: string;
  accepted_by_name: string | null;
  accepted_at: string | null;
  ended_at: string | null;
  ended_side: string | null;
  end_reason: string | null;
  environment: string;
  can_end: boolean;
}

export interface LaboratoryOrg {
  id: string;
  code: string;
  name: string;
  environment: string;
}

export interface CustodyEvent {
  sequence_no: number;
  event_type: string;
  from_state: string | null;
  to_state: string;
  actor_name: string | null;
  actor_org_name: string | null;
  actor_role: string | null;
  actor_side: 'PROJECT' | 'LABORATORY';
  occurred_at: string;
  location_text: string | null;
  seal_number: string | null;
  shipment_code?: string | null;
  exception_type: string | null;
  reason: string | null;
}

export interface LabResult {
  id: string;
  test_id: string;
  test_code: string;
  version: number;
  status: string;
  result_type: 'NUMERIC' | 'TEXT';
  value_number: string | null;
  value_text: string | null;
  unit: string | null;
  analysed_at: string | null;
  analyst_name: string | null;
  method_reported: string | null;
  report: DocumentRef | null;
  supersedes_result_id: string | null;
  superseded_by_result_id: string | null;
  status_reason: string | null;
  approved_at: string | null;
  approved_by_name: string | null;
  rule_code: string;
  parameter: string;
  authoritative: boolean;
}

export interface LabTest {
  id: string;
  test_code: string;
  status: string;
  sample_code: string;
  rule: RuleRef;
  plan_measurement_code: string;
  plan_measurement_type: string;
  retest_of_test_code: string | null;
  retest_reason: string | null;
  laboratory_org_name: string;
  results: LabResult[];
}

export interface Sample {
  id: string;
  sample_code: string;
  root_sample_code: string;
  parent_sample_code: string | null;
  status: string;
  description: string;
  depth_top_cm: string;
  depth_bottom_cm: string;
  quantity: string | null;
  quantity_unit: string | null;
  container_label: string | null;
  seal_number: string | null;
  accession_number: string | null;
  field_collection_id: string;
  field_collection_code: string;
  field_collection_version: number;
  field_collection_status: string;
  sampling_point_code: string;
  farm_code: string | null;
  project_id: string;
  project_code: string;
  monitoring_period_id: string;
  laboratory_org_id: string;
  laboratory_org_name: string;
  registered_by_name: string | null;
  registered_at: string;
  sealed_at: string | null;
  environment: string;
  test_count: number;
  approved_count: number;
  can_seal: boolean;
  can_edit: boolean;
}

export interface SampleDetail extends Sample {
  custody: CustodyEvent[];
  tests: LabTest[];
  shipments: string[];
}

export interface ShipmentItem {
  sample_id: string;
  sample_code: string;
  status: string;
  receipt_condition: string | null;
  receipt_reason: string | null;
  received_at: string | null;
}

export interface Shipment {
  id: string;
  shipment_code: string;
  project_id: string;
  project_code: string;
  laboratory_org_id: string;
  laboratory_org_name: string;
  status: 'DRAFT' | 'DISPATCHED' | 'RECEIVED' | 'CANCELLED';
  carrier: string | null;
  tracking_number: string | null;
  created_at: string;
  dispatched_at: string | null;
  received_at: string | null;
  items: ShipmentItem[];
  documents: DocumentRef[];
}

export interface QaReview {
  id: string;
  decision: string;
  notes: string;
  reviewer_name: string | null;
  reviewed_at: string;
  configuration_acknowledged: boolean;
  checks: LabQaCheck[];
}

export interface Lineage {
  result: LabResult;
  versions: LabResult[];
  test: Record<string, unknown> & { test_code: string; retest_chain: string[]; laboratory: string };
  sample: Record<string, unknown> & { sample_code: string; seal_number: string | null; accession_number: string | null };
  root_sample: { id: string; sample_code: string };
  field_collection: { id: string; collection_code: string; version: number; status: string; collected_at: string | null };
  sampling_point: { id: string; point_code: string; latitude: string; longitude: string };
  stratum: { id: string; code: string; version: number } | null;
  farm: { id: string; farm_code: string; name: string; boundary_version: number | null };
  project: { id: string; project_code: string; name: string; status: string };
  methodology: { methodology_code: string; version_label: string; locked: boolean };
  methodology_rule: RuleRef;
  plan_measurement: { code: string; value_type: string; unit: string | null; plan_version: number | null };
  custody: CustodyEvent[];
  shipments: { shipment_code: string; status: string; dispatched_at: string | null; received_at: string | null; receipt_status: string | null;
    receipt_condition: string | null }[];
  qa_reviews: QaReview[];
}

// ---------------------------------------------------------------- laboratory-facing (allow-lists)
export interface EngagementLabView {
  id: string;
  project_code: string;
  project_org_name: string;
  laboratory_org_name: string;
  methodology_label: string;
  status: 'PROPOSED' | 'ACTIVE' | 'ENDED';
  rules: RuleRef[];
  proposed_at: string;
  accepted_at: string | null;
  ended_at: string | null;
  ended_side: string | null;
  end_reason: string | null;
  environment: string;
  can_accept: boolean;
  can_end: boolean;
}

export interface ResultLabView {
  id: string;
  version: number;
  status: string;
  result_type: 'NUMERIC' | 'TEXT';
  value_number: string | null;
  value_text: string | null;
  unit: string | null;
  analysed_at: string | null;
  analyst_name: string | null;
  method_reported: string | null;
  report: DocumentRef | null;
  supersedes_result_id: string | null;
  status_reason: string | null;
  submitted_at: string | null;
  approved_at: string | null;
  can_edit: boolean;
  can_submit: boolean;
}

export interface TestLabView {
  id: string;
  test_code: string;
  status: string;
  sample_id: string;
  sample_code: string;
  project_code: string;
  rule: RuleRef;
  required_unit: string | null;
  value_type: string;
  unit_configuration: 'CONFIGURED' | 'CONFIGURATION_REQUIRED';
  method_reported: string | null;
  retest_of_test_code: string | null;
  retest_reason: string | null;
  results: ResultLabView[];
  can_start: boolean;
  can_enter_result: boolean;
}

export interface SampleLabView {
  id: string;
  sample_code: string;
  parent_sample_code: string | null;
  status: string;
  description: string;
  depth_top_cm: string;
  depth_bottom_cm: string;
  quantity: string | null;
  quantity_unit: string | null;
  container_label: string | null;
  seal_number: string | null;
  accession_number: string | null;
  project_code: string;
  project_org_name: string;
  laboratory_org_name: string;
  methodology_label: string;
  tests: TestLabView[];
  custody: CustodyEvent[];
}

export interface ShipmentLabView {
  id: string;
  shipment_code: string;
  project_code: string;
  project_org_name: string;
  laboratory_org_name: string;
  status: string;
  carrier: string | null;
  tracking_number: string | null;
  dispatched_at: string | null;
  received_at: string | null;
  items: { sample_id: string; sample_code: string; status: string; seal_number: string | null; receipt_condition: string | null;
    receipt_reason: string | null; received_at: string | null }[];
  documents: DocumentRef[];
  can_receive: boolean;
}

export interface QaLabView {
  result: ResultLabView;
  test: TestLabView;
  sample_code: string;
  checks: LabQaCheck[];
  reviews: QaReview[];
  can_start: boolean;
  can_decide: boolean;
  can_approve: boolean;
  blocked_reasons: string[];
}

export interface LabDashboardCounts {
  engagements_pending: number;
  shipments_incoming: number;
  samples_to_register: number;
  tests_open: number;
  results_awaiting_qa: number;
}

/** Badge tone for any Phase 6 status. */
export function labBadge(status: string | null | undefined): string {
  if (!status) return 'INFO';
  if (['APPROVED', 'ACTIVE', 'RECEIVED', 'ANALYSED', 'CLOSED', 'PASS', 'LAB_RECEIVED', 'LAB_REGISTERED'].includes(status)) return 'ACTIVE';
  if (['REJECTED', 'REJECTED_AT_RECEIPT', 'FAIL', 'EXCEPTION', 'VOIDED', 'CANCELLED'].includes(status)) return 'FAILED';
  if (['SUPERSEDED', 'ENDED', 'WITHDRAWN', 'REMOVED'].includes(status)) return 'ARCHIVED';
  if (['SUBMITTED', 'QA_REVIEW', 'PROPOSED', 'RETEST_REQUIRED', 'WARN', 'CONFIGURATION_REQUIRED', 'DISPATCHED', 'IN_TRANSIT'].includes(status)) {
    return 'WARNING';
  }
  return 'INFO';
}

/** "1.234000" → "1.234"; text results are shown exactly as reported (never parsed). */
export function resultValue(r: { result_type: string; value_number: string | null; value_text: string | null; unit: string | null }): string {
  if (r.result_type === 'TEXT') return `${r.value_text ?? ''} (as reported)`;
  const n = r.value_number === null ? '' : r.value_number.replace(/(\.\d*?)0+$/, '$1').replace(/\.$/, '');
  return `${n}${r.unit ? ' ' + r.unit : ''}`;
}

/** Unit check preview, mirroring the server rule: exact text after trimming, case-sensitive, never converted. */
export function unitMatches(required: string | null, reported: string | null): 'MATCH' | 'MISMATCH' | 'CONFIGURATION_REQUIRED' {
  const req = (required ?? '').trim();
  if (!req) return 'CONFIGURATION_REQUIRED';
  return (reported ?? '').trim() === req ? 'MATCH' : 'MISMATCH';
}

/** Whether a result of this type can ever be approved for the plan measurement type (decision 12). */
export function resultTypeApprovable(valueType: string, resultType: 'NUMERIC' | 'TEXT'): boolean {
  return valueType === 'NUMBER' ? resultType === 'NUMERIC' : resultType === 'TEXT';
}
