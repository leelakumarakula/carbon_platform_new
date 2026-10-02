import type { DocumentInfo, TransitionReadiness } from '../farmer/farmer.models';
import type { GeoGeometry } from '../farms/farm.models';

/** Full lifecycle (spec section 8). Phase 3 only moves projects between the first five states and CLOSED. */
export type ProjectStatus =
  | 'DRAFT' | 'DATA_COLLECTION' | 'ELIGIBILITY_REVIEW' | 'STANDARD_SELECTED' | 'ACTIVITY_SELECTED' | 'METHODOLOGY_REVIEW'
  | 'METHODOLOGY_CONFIRMED' | 'MRV_PLANNED' | 'MONITORING' | 'CALCULATION_READY' | 'CALCULATED' | 'VALIDATION' | 'VERIFICATION'
  | 'VERIFIED' | 'REGISTRY_SUBMISSION' | 'REGISTERED' | 'ISSUANCE_PENDING' | 'ISSUED' | 'ACTIVE' | 'CLOSED';

export const PHASE3_STATUSES: ProjectStatus[] = ['DRAFT', 'DATA_COLLECTION', 'ELIGIBILITY_REVIEW', 'STANDARD_SELECTED', 'ACTIVITY_SELECTED', 'CLOSED'];
export const PROJECT_TYPES = ['AGRICULTURAL_LAND_MANAGEMENT', 'AGROFORESTRY', 'RICE_CULTIVATION', 'GRASSLAND_MANAGEMENT', 'OTHER'] as const;
export const PROJECT_ROLES = ['PROJECT_MANAGER', 'MRV_MANAGER', 'METHODOLOGY_SPECIALIST', 'FIELD_SUPERVISOR', 'FIELD_AGENT', 'GIS_SPECIALIST',
  'PLATFORM_GIS_SPECIALIST', 'QA_OFFICER', 'FINANCE_MANAGER', 'CALCULATION_ANALYST', 'REGISTRY_MANAGER', 'CREDIT_MANAGER', 'SUPPORT'] as const;
export const HOLDER_TYPES = ['FARMER', 'LANDOWNER', 'ORGANIZATION', 'FARMER_GROUP', 'OTHER'] as const;
export const PROJECT_DOC_CATEGORIES = ['PROJECT_DESIGN', 'CARBON_RIGHTS', 'BASELINE_DATA', 'AGREEMENT', 'GEOSPATIAL_FILE', 'OTHER'] as const;

export interface ProjectSummary {
  id: string;
  project_code: string;
  name: string;
  project_type: string;
  organization_id: string;
  organization_name: string | null;
  country: string;
  region: string | null;
  status: ProjectStatus;
  start_date: string | null;
  standard_name: string | null;
  activity_name: string | null;
  methodology_status: string;
  methodology_label?: string | null;
  farm_count: number;
  area_hectares: string | null;
  environment: 'LIVE' | 'DEMO';
  created_at: string;
}

export interface Project extends ProjectSummary {
  description: string | null;
  standard_id: string | null;
  activity_id: string | null;
  current_boundary_id: string | null;
  submitted_at: string | null;
  submitted_by: string | null;
  eligibility_reviewed_at: string | null;
  eligibility_reviewed_by: string | null;
  review_notes: string | null;
  updated_at: string;
  allowed_transitions: ProjectStatus[];
  readiness: TransitionReadiness[];
  can_manage: boolean;
  can_review: boolean;
  can_review_boundary: boolean;
  is_editable: boolean;
  counts: Record<string, number>;
}

export interface Conflict {
  kind: 'FARM_OVERLAP' | 'OTHER_PROJECT_PARTICIPATION';
  status: string | null;
  detail: string;
  other_farm_code: string | null;
  other_project_code: string | null;
  overlap_area_m2: string | null;
}

export interface CarbonRight {
  id: string;
  project_farm_id: string;
  farm_id: string;
  farm_code: string | null;
  farmer_id: string;
  holder_type: string;
  holder_farmer_id: string | null;
  holder_organization_id: string | null;
  holder_name: string;
  share_pct: string | null;
  agreement_id: string | null;
  agreement_number: string | null;
  document_id: string | null;
  reference: string | null;
  effective_from: string;
  effective_to: string | null;
  status: 'ACTIVE' | 'ENDED' | 'VOID';
  verification_status: 'UNVERIFIED' | 'VERIFIED' | 'REJECTED';
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_notes: string | null;
  end_reason: string | null;
  created_by: string | null;
  created_at: string;
}

export interface CarbonRightInput {
  holder_type: string;
  holder_farmer_id?: string | null;
  holder_organization_id?: string | null;
  holder_name?: string | null;
  share_pct?: string | null;
  agreement_id?: string | null;
  document_id?: string | null;
  reference?: string | null;
  effective_from: string;
  effective_to?: string | null;
}

export interface ProjectFarm {
  id: string;
  farm_id: string;
  farm_code: string;
  farm_name: string;
  farm_status: string;
  farmer_id: string;
  farmer_code: string;
  farmer_name: string;
  status: 'ACTIVE' | 'REMOVED';
  participation_start: string;
  participation_end: string | null;
  farm_boundary_id: string;
  farm_area_hectares: string;
  boundary_changed: boolean;
  conflicts_acknowledged: boolean;
  conflict_notes: string | null;
  conflicts: Conflict[];
  carbon_rights: CarbonRight[];
  added_at: string;
  removed_at: string | null;
  removal_reason: string | null;
}

export interface EligibleFarm {
  farm_id: string;
  farm_code: string;
  farm_name: string;
  farmer_id: string;
  farmer_name: string;
  farmer_status: string;
  farm_status: string;
  area_hectares: string | null;
  eligible: boolean;
  reasons: string[];
  conflicts: Conflict[];
  in_other_projects: string[];
}

export interface Participant {
  id: string;
  user_id: string;
  user_name: string;
  user_email: string;
  project_role: string;
  status: 'ACTIVE' | 'REMOVED';
  start_date: string | null;
  end_date: string | null;
  notes: string | null;
  added_at: string;
  removed_at: string | null;
  removal_reason: string | null;
}

export interface CandidateUser {
  user_id: string;
  full_name: string;
  email: string;
  roles: string[];
}

export interface CatalogStandard {
  id: string;
  code: string;
  name: string;
  owner_name: string | null;
  program_type: string;
  description: string | null;
  source_url: string | null;
  status: 'ACTIVE' | 'INACTIVE';
  environment: 'LIVE' | 'DEMO';
  activity_ids: string[];
}

export interface CatalogActivity {
  id: string;
  code: string;
  name: string;
  category: string | null;
  description: string | null;
  status: 'ACTIVE' | 'INACTIVE';
  environment: 'LIVE' | 'DEMO';
  standard_ids: string[];
}

export interface Selection {
  id: string;
  ref_id: string;
  code: string;
  name: string;
  is_current: boolean;
  reason: string | null;
  selected_at: string;
  superseded_at: string | null;
}

export interface ProjectStandards {
  current: CatalogStandard | null;
  history: Selection[];
  available: CatalogStandard[];
}

export interface ProjectActivities {
  current: CatalogActivity | null;
  history: Selection[];
  available: CatalogActivity[];
  methodology_status: string;
}

export interface CreditingPeriod {
  id: string;
  period_number: number;
  start_date: string;
  end_date: string;
  status: string;
  notes: string | null;
  replaces_id: string | null;
  created_at: string;
  status_changed_at: string | null;
  status_reason: string | null;
  length_days: number;
}

export interface Baseline {
  id: string;
  version: number;
  is_current: boolean;
  period_start: string;
  period_end: string;
  description: string | null;
  data_sources: string | null;
  notes: string | null;
  change_reason: string | null;
  created_at: string;
}

export interface Baselines {
  current: Baseline | null;
  versions: Baseline[];
  note: string;
}

export interface ProjectBoundary {
  id: string;
  version: number;
  status: 'CURRENT' | 'SUPERSEDED';
  geojson: GeoGeometry;
  area_m2: string;
  area_hectares: string;
  sum_farm_area_hectares: string;
  internal_overlap_hectares: string;
  farm_count: number;
  is_valid: boolean;
  validation_notes: string | null;
  computed_at: string;
  review_status: 'PENDING' | 'ACCEPTED' | 'ISSUES';
  reviewed_at: string | null;
  review_notes: string | null;
}

export interface BoundaryView {
  current: ProjectBoundary | null;
  stale: boolean;
  farms: { farm_id: string; farm_code: string; farm_name: string; area_hectares: string; geojson: GeoGeometry; open_overlaps: number }[];
  project_overlaps: { other_project_id: string | null; other_project_code: string | null; other_project_visible: boolean;
    same_organization: boolean; overlap_area_m2: string }[];
  versions: ProjectBoundary[];
  can_recompute: boolean;
  can_review: boolean;
}

export interface StatusHistoryEntry {
  id: number;
  from_status: string | null;
  to_status: string;
  action: string;
  reason: string | null;
  changed_by_name: string | null;
  changed_at: string;
  request_id: string | null;
}

export interface MyParticipation {
  project_id: string;
  project_code: string;
  project_name: string;
  project_status: string;
  farm_id: string;
  farm_code: string;
  farm_name: string;
  participation_status: string;
  participation_start: string;
  participation_end: string | null;
  carbon_rights: CarbonRight[];
}

export interface ProjectDocuments {
  documents: DocumentInfo[];
  categories: string[];
}

/** Workflow buttons. `endpoint` is the server action; the server decides who may use it (allowed_transitions). */
export interface ProjectAction {
  label: string;
  endpoint: string;
  danger?: boolean;
  confirm?: string;
}

export function projectAction(from: ProjectStatus, to: ProjectStatus): ProjectAction {
  if (to === 'DATA_COLLECTION' && from === 'DRAFT') return { label: 'Start data collection', endpoint: 'start-data-collection' };
  if (to === 'ELIGIBILITY_REVIEW') return { label: 'Submit for eligibility review', endpoint: 'submit',
    confirm: 'Farms, carbon rights, crediting period and baseline will be locked while the review is open.' };
  if (to === 'STANDARD_SELECTED') return { label: 'Approve eligibility', endpoint: 'approve-eligibility',
    confirm: 'You confirm the farms, boundary and carbon-rights references were reviewed. You cannot approve a project you submitted.' };
  if (to === 'DATA_COLLECTION' && from === 'ELIGIBILITY_REVIEW') return { label: 'Return for correction', endpoint: 'return', danger: true };
  if (to === 'DATA_COLLECTION') return { label: 'Re-open for correction', endpoint: 'reopen', danger: true,
    confirm: 'Eligibility (and the methodology selection) will have to be reviewed again.' };
  if (to === 'METHODOLOGY_REVIEW') return { label: 'Methodology review', endpoint: 'methodology' };
  if (to === 'METHODOLOGY_CONFIRMED') return { label: 'Confirm methodology', endpoint: 'methodology' };
  if (to === 'ACTIVITY_SELECTED') return { label: 'Confirm activity', endpoint: 'confirm-activity' };
  return { label: 'Close project', endpoint: 'close', danger: true, confirm: 'Closing is final in this phase.' };
}

export function projectBadge(status: string): string {
  if (status === 'CLOSED') return 'ARCHIVED';
  if (status === 'DRAFT') return 'INFO';
  if (status === 'ELIGIBILITY_REVIEW') return 'WARNING';
  return 'ACTIVE';
}
