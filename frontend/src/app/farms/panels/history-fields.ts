import { EVIDENCE_SOURCES, HistoryKind, LAND_USES, PRACTICE_CATEGORIES } from '../farm.models';

export interface FieldDef {
  key: string;
  label: string;
  type: 'number' | 'text' | 'date' | 'select';
  options?: readonly string[];
  required?: boolean;
}

const COMMON: FieldDef[] = [
  { key: 'source', label: 'Source', type: 'select', options: EVIDENCE_SOURCES, required: true },
  { key: 'notes', label: 'Notes', type: 'text' },
];

/** Form definitions for the three history record types (mirrors backend schemas; the API validates). */
export const HISTORY_FIELDS: Record<HistoryKind, FieldDef[]> = {
  land: [
    { key: 'year', label: 'Year', type: 'number', required: true },
    { key: 'land_use', label: 'Land use', type: 'select', options: LAND_USES, required: true },
    { key: 'land_use_detail', label: 'Detail', type: 'text' },
    ...COMMON,
  ],
  crop: [
    { key: 'year', label: 'Year', type: 'number', required: true },
    { key: 'season', label: 'Season', type: 'text' },
    { key: 'crop_name', label: 'Crop', type: 'text', required: true },
    { key: 'crop_variety', label: 'Variety', type: 'text' },
    { key: 'area_hectares', label: 'Area (ha)', type: 'number' },
    { key: 'planting_date', label: 'Planting date', type: 'date' },
    { key: 'harvest_date', label: 'Harvest date', type: 'date' },
    { key: 'yield_quantity', label: 'Yield', type: 'number' },
    { key: 'yield_unit', label: 'Yield unit', type: 'text' },
    { key: 'irrigation', label: 'Irrigation', type: 'select', options: ['RAINFED', 'IRRIGATED', 'PARTIAL'] },
    { key: 'residue_management', label: 'Residue management', type: 'text' },
    ...COMMON,
  ],
  practice: [
    { key: 'year', label: 'Year', type: 'number', required: true },
    { key: 'season', label: 'Season', type: 'text' },
    { key: 'practice_phase', label: 'Phase', type: 'select', options: ['HISTORICAL', 'CURRENT', 'PROPOSED'], required: true },
    { key: 'practice_category', label: 'Category', type: 'select', options: PRACTICE_CATEGORIES, required: true },
    { key: 'practice_type', label: 'Practice', type: 'text', required: true },
    { key: 'quantity', label: 'Quantity', type: 'number' },
    { key: 'unit', label: 'Unit', type: 'text' },
    { key: 'frequency', label: 'Frequency', type: 'text' },
    { key: 'start_date', label: 'Start date', type: 'date' },
    { key: 'implementation_status', label: 'Implementation', type: 'select', options: ['PLANNED', 'IN_PROGRESS', 'IMPLEMENTED', 'ABANDONED'] },
    { key: 'expected_change', label: 'Expected change', type: 'text' },
    ...COMMON,
  ],
};

/** Form value → API payload: empty strings become null, numbers stay numbers. */
export function toPayload(defs: FieldDef[], value: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const d of defs) {
    const v = value[d.key];
    if (v === '' || v === undefined || v === null) out[d.key] = null;
    else out[d.key] = d.type === 'number' ? Number(v) : v;
  }
  return out;
}

/** Only the fields that changed (for amendments). Values compared as strings to absorb 2.1 vs "2.1". */
export function changedFields(defs: FieldDef[], before: Record<string, unknown>, after: Record<string, unknown>): Record<string, unknown> {
  const diff: Record<string, unknown> = {};
  for (const d of defs) {
    const a = before[d.key] ?? null;
    const b = after[d.key] ?? null;
    if (String(a ?? '') !== String(b ?? '')) diff[d.key] = b;
  }
  return diff;
}
