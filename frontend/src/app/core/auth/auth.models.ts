export interface TokenResponse {
  access_token: string;
  token_type: 'bearer';
  expires_in: number;
  must_change_password: boolean;
}

export interface RoleGrant {
  id: string;
  role_code: string;
  role_name: string;
  scope: 'PLATFORM' | 'ORGANIZATION';
  organization_id: string | null;
  organization_name: string | null;
  assigned_at: string;
}

export interface Membership {
  organization_id: string;
  organization_code: string;
  organization_name: string;
  org_type: string;
  title: string | null;
  is_primary: boolean;
}

export type UserStatus = 'ACTIVE' | 'SUSPENDED' | 'DEACTIVATED';
export type Environment = 'LIVE' | 'DEMO';

export interface User {
  id: string;
  email: string;
  full_name: string;
  phone: string | null;
  status: UserStatus;
  must_change_password: boolean;
  mfa_enabled: boolean;
  is_locked: boolean;
  locked_until: string | null;
  last_login_at: string | null;
  environment: Environment;
  created_at: string;
  updated_at: string;
  roles: RoleGrant[];
  organizations: Membership[];
}

export interface Me {
  user: User;
  permissions: string[];
  platform_permissions: string[];
}
