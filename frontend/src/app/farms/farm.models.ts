/** Farm API shapes (backend: app/schemas/farms.py). */
import { DocumentInfo, TransitionReadiness } from '../farmer/farmer.models';

export type FarmStatus = 'DRAFT' | 'SUBMITTED' | 'GIS_REVIEW' | 'VERIFIED' | 'REJECTED' | 'INACTIVE';
export type HistoryKind = 'land' | 'crop' | 'practice';
// GeoJSON geometry as exchanged with the API (Polygon / MultiPolygon only for farm boundaries).
export interface GeoGeometry {
  type: 'Polygon' | 'MultiPolygon';
  coordinates: number[][][] | number[][][][];
}

export interface Boundary {
  id: string;
  version: number;
  status: 'CURRENT' | 'SUPERSEDED';
  source: string;
  source_document_id: string | null;
  geojson: GeoGeometry;
  area_hectares: string;
  area_m2: string;
  perimeter_m: string;
  centroid_lat: string;
  centroid_lon: string;
  vertex_count: number;
  validation_notes: string | null;
  created_at: string;
  superseded_at: string | null;
}

export interface FarmSummary {
  id: string;
  farm_code: string;
  name: string;
  farmer_id: string;
  farmer_code: string;
  farmer_name: string;
  organization_id: string;
  village: string | null;
  district: string | null;
  state: string | null;
  country: string;
  land_tenure: string;
  declared_area_hectares: string | null;
  area_hectares: string | null;
  status: FarmStatus;
  open_overlaps: number;
  environment: 'LIVE' | 'DEMO';
  centroid_lat: string | null;
  centroid_lon: string | null;
  created_at: string;
}

export interface Farm extends FarmSummary {
  sub_district: string | null;
  current_boundary: Boundary | null;
  submitted_at: string | null;
  submitted_by: string | null;
  verified_at: string | null;
  verified_by: string | null;
  review_notes: string | null;
  updated_at: string;
  allowed_transitions: string[];
  readiness: TransitionReadiness[];
  history_counts: Record<HistoryKind, number>;
  evidence_count: number;
  ownership_count: number;
  can_manage: boolean;
  can_review: boolean;
  is_self: boolean;
  documents: DocumentInfo[];
}

export interface GeometryReport {
  geojson: GeoGeometry;
  area_m2: number;
  area_hectares: number;
  perimeter_m: number;
  centroid_lat: number;
  centroid_lon: number;
  vertex_count: number;
  notes: string[];
  warnings: string[];
}

export interface Overlap {
  id: string;
  farm_id: string;
  other_farm_id: string | null;
  other_farm_code: string | null;
  other_farm_visible: boolean;
  relation: string;
  overlap_area_m2: string;
  overlap_pct_of_farm: string;
  overlap_pct_of_other: string;
  same_farmer: boolean;
  same_organization: boolean;
  status: 'OPEN' | 'CLEARED' | 'CONFIRMED_CONFLICT' | 'OBSOLETE';
  detected_at: string;
  resolved_at: string | null;
  resolution_notes: string | null;
  other_geojson: GeoGeometry | null;
}

export interface Ownership {
  id: string;
  owner_type: string;
  owner_farmer_id: string | null;
  owner_name: string;
  operator_relationship: string;
  ownership_share_pct: string | null;
  title_reference: string | null;
  evidence_document_id: string | null;
  valid_from: string | null;
  valid_to: string | null;
  end_reason: string | null;
  is_current: boolean;
  verification_status: string;
  review_notes: string | null;
  recorded_at: string;
}

export interface HistoryRecord {
  id: string;
  record_id: string;
  version: number;
  is_current: boolean;
  is_retracted: boolean;
  source: string;
  evidence_document_id: string | null;
  verification_status: string;
  review_notes: string | null;
  change_reason: string | null;
  notes: string | null;
  recorded_by: string | null;
  recorded_at: string;
  fields: Record<string, string | number | null>;
}

export interface Evidence {
  id: string;
  claim_type: string;
  claim_record_id: string | null;
  source_type: string;
  description: string;
  document_id: string | null;
  external_reference: string | null;
  observed_at: string | null;
  latitude: string | null;
  longitude: string | null;
  distance_to_boundary_m: number | null;
  verification_status: string;
  review_notes: string | null;
  captured_by: string | null;
  created_at: string;
}

export const TENURES = ['OWNED', 'LEASED', 'SHARECROPPED', 'COMMUNITY', 'GOVERNMENT_ALLOTTED', 'CUSTOMARY', 'OTHER'] as const;
export const LAND_USES = ['CROPLAND', 'GRASSLAND', 'FOREST', 'FALLOW', 'WETLAND', 'SETTLEMENT', 'AGROFORESTRY', 'OTHER'] as const;
export const PRACTICE_CATEGORIES = ['TILLAGE', 'FERTILIZER', 'MANURE', 'IRRIGATION', 'RESIDUE', 'WATER_MANAGEMENT', 'GRAZING',
  'COVER_CROP', 'CROP_ROTATION', 'AGROFORESTRY', 'OTHER'] as const;
export const EVIDENCE_SOURCES = ['FARMER_CLAIM', 'FIELD_AGENT', 'SATELLITE', 'DOCUMENT', 'INPUT_RECORD', 'OTHER'] as const;
export const CLAIM_TYPES = ['BOUNDARY', 'OWNERSHIP', 'LAND_USE', 'CROP', 'PRACTICE', 'OTHER'] as const;
export const FARM_DOC_CATEGORIES = ['LAND_TITLE', 'LEASE_AGREEMENT', 'LAND_RECORD', 'FIELD_PHOTO', 'INPUT_RECORD', 'OTHER'] as const;

/** Workflow action per target status, from the farm's point of view. */
export const FARM_ACTIONS: Record<string, { label: string; endpoint: string; review: boolean; danger?: boolean }> = {
  SUBMITTED: { label: 'Submit for review', endpoint: 'submit', review: false },
  GIS_REVIEW: { label: 'Start GIS review', endpoint: 'start-review', review: true },
  VERIFIED: { label: 'Verify farm', endpoint: 'verify', review: true },
  REJECTED: { label: 'Reject', endpoint: 'reject', review: true, danger: true },
  DRAFT: { label: 'Re-open for correction', endpoint: 'reopen', review: false },
  INACTIVE: { label: 'Make inactive', endpoint: 'inactivate', review: false, danger: true },
};
