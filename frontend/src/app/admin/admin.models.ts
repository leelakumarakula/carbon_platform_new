import { Environment, User, UserStatus } from '../core/auth/auth.models';

export type { User, UserStatus };

export type OrgType =
  | 'PLATFORM'
  | 'PROJECT_DEVELOPER'
  | 'FIELD_PARTNER'
  | 'FARMER_GROUP'
  | 'LABORATORY'
  | 'VVB'
  | 'REGISTRY'
  | 'BUYER';

export type OrgStatus = 'ACTIVE' | 'SUSPENDED' | 'ARCHIVED';

export const ORG_TYPES: readonly { value: OrgType; label: string }[] = [
  { value: 'PROJECT_DEVELOPER', label: 'Project developer' },
  { value: 'FIELD_PARTNER', label: 'Field partner' },
  { value: 'FARMER_GROUP', label: 'Farmer group' },
  { value: 'LABORATORY', label: 'Laboratory' },
  { value: 'VVB', label: 'VVB / ACVA' },
  { value: 'REGISTRY', label: 'Registry' },
  { value: 'BUYER', label: 'Buyer' },
];

export function orgTypeLabel(t: string): string {
  return t === 'PLATFORM' ? 'Platform operator' : (ORG_TYPES.find((o) => o.value === t)?.label ?? t);
}

/** Client mirrors of the backend state machines (app/services/workflows.py). The API remains authoritative. */
export const USER_TRANSITIONS: Record<UserStatus, UserStatus[]> = {
  ACTIVE: ['SUSPENDED', 'DEACTIVATED'],
  SUSPENDED: ['ACTIVE', 'DEACTIVATED'],
  DEACTIVATED: [],
};

export const ORG_TRANSITIONS: Record<OrgStatus, OrgStatus[]> = {
  ACTIVE: ['SUSPENDED', 'ARCHIVED'],
  SUSPENDED: ['ACTIVE', 'ARCHIVED'],
  ARCHIVED: [],
};

export interface Organization {
  id: string;
  code: string;
  name: string;
  org_type: OrgType;
  country: string | null;
  registration_number: string | null;
  contact_email: string | null;
  status: OrgStatus;
  environment: Environment;
  member_count: number;
  created_at: string;
  updated_at: string;
}

export interface OrganizationInput {
  code?: string;
  name?: string;
  org_type?: OrgType;
  country?: string | null;
  registration_number?: string | null;
  contact_email?: string | null;
}

export interface Member {
  id: string;
  user_id: string;
  email: string;
  full_name: string;
  user_status: UserStatus;
  title: string | null;
  is_primary: boolean;
  joined_at: string;
}

export interface Permission {
  code: string;
  module: string;
  name: string;
  description: string | null;
}

export interface Role {
  id: string;
  code: string;
  name: string;
  description: string | null;
  scope: 'PLATFORM' | 'ORGANIZATION';
  is_system: boolean;
  permissions: string[];
  assignment_count: number;
}

export interface RoleGrantInput {
  role_code: string;
  organization_id?: string | null;
}

export interface UserCreateInput {
  email: string;
  full_name: string;
  phone?: string | null;
  temporary_password: string;
  organization_id?: string | null;
  title?: string | null;
  roles: RoleGrantInput[];
}

export interface AuditLog {
  id: number;
  occurred_at: string;
  user_id: string | null;
  user_email: string | null;
  organization_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
  reason: string | null;
  request_id: string | null;
  ip_address: string | null;
}

export interface LoginAudit {
  id: number;
  occurred_at: string;
  user_id: string | null;
  email_attempted: string;
  success: boolean;
  failure_reason: string | null;
  ip_address: string | null;
}

export interface SecurityEvent {
  id: number;
  occurred_at: string;
  event_type: string;
  severity: 'INFO' | 'WARNING' | 'CRITICAL';
  user_id: string | null;
  ip_address: string | null;
  details: Record<string, unknown> | null;
  request_id: string | null;
}

export interface SessionInfo {
  id: string;
  user_id: string;
  user_email: string;
  created_at: string;
  last_seen_at: string;
  expires_at: string;
  revoked_at: string | null;
  revoked_reason: string | null;
  ip_address: string | null;
  user_agent: string | null;
  is_active: boolean;
}
