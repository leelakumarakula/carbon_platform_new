import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { MessageResponse, Page, PageQuery } from '../core/api/api.models';
import { ApiService } from '../core/api/api.service';
import {
  AuditLog,
  LoginAudit,
  Member,
  OrgStatus,
  Organization,
  OrganizationInput,
  Permission,
  Role,
  RoleGrantInput,
  SecurityEvent,
  SessionInfo,
  User,
  UserCreateInput,
  UserStatus,
} from './admin.models';

export interface UserQuery extends PageQuery {
  search?: string | null;
  status?: UserStatus | null;
  organization_id?: string | null;
  role?: string | null;
  environment?: 'LIVE' | 'DEMO' | null;
}

export interface OrgQuery extends PageQuery {
  search?: string | null;
  org_type?: string | null;
  status?: OrgStatus | null;
  environment?: 'LIVE' | 'DEMO' | null;
}

export interface AuditQuery extends PageQuery {
  entity_type?: string | null;
  entity_id?: string | null;
  action?: string | null;
  user_id?: string | null;
  organization_id?: string | null;
  from?: string | null;
  to?: string | null;
}

@Injectable({ providedIn: 'root' })
export class UsersApi {
  private readonly api = inject(ApiService);
  list = (q: UserQuery): Observable<Page<User>> => this.api.get('/admin/users', { ...q });
  get = (id: string): Observable<User> => this.api.get(`/admin/users/${id}`);
  create = (body: UserCreateInput): Observable<User> => this.api.post('/admin/users', body);
  update = (id: string, body: { full_name?: string; phone?: string | null }): Observable<User> =>
    this.api.patch(`/admin/users/${id}`, body);
  changeStatus = (id: string, status: UserStatus, reason: string): Observable<User> =>
    this.api.post(`/admin/users/${id}/status`, { status, reason });
  resetPassword = (id: string, temporary_password: string, reason: string): Observable<User> =>
    this.api.post(`/admin/users/${id}/reset-password`, { temporary_password, reason });
  unlock = (id: string, reason: string): Observable<User> => this.api.post(`/admin/users/${id}/unlock`, { reason });
  grantRole = (id: string, grant: RoleGrantInput): Observable<User> => this.api.post(`/admin/users/${id}/roles`, grant);
  revokeRole = (id: string, userRoleId: string, reason: string): Observable<User> =>
    this.api.delete(`/admin/users/${id}/roles/${userRoleId}`, { reason });
}

@Injectable({ providedIn: 'root' })
export class OrganizationsApi {
  private readonly api = inject(ApiService);
  list = (q: OrgQuery): Observable<Page<Organization>> => this.api.get('/admin/organizations', { ...q });
  get = (id: string): Observable<Organization> => this.api.get(`/admin/organizations/${id}`);
  create = (body: OrganizationInput): Observable<Organization> => this.api.post('/admin/organizations', body);
  update = (id: string, body: OrganizationInput): Observable<Organization> => this.api.patch(`/admin/organizations/${id}`, body);
  changeStatus = (id: string, status: OrgStatus, reason: string): Observable<Organization> =>
    this.api.post(`/admin/organizations/${id}/status`, { status, reason });
  members = (id: string): Observable<Member[]> => this.api.get(`/admin/organizations/${id}/members`);
  addMember = (id: string, body: { user_id: string; title?: string | null; is_primary?: boolean }): Observable<MessageResponse> =>
    this.api.post(`/admin/organizations/${id}/members`, body);
  removeMember = (id: string, userId: string, reason: string): Observable<MessageResponse> =>
    this.api.post(`/admin/organizations/${id}/members/${userId}/remove`, { reason });
}

@Injectable({ providedIn: 'root' })
export class RolesApi {
  private readonly api = inject(ApiService);
  list = (): Observable<Role[]> => this.api.get('/admin/roles');
  get = (id: string): Observable<Role> => this.api.get(`/admin/roles/${id}`);
  permissions = (): Observable<Permission[]> => this.api.get('/admin/permissions');
  create = (body: { code: string; name: string; description?: string | null; scope: string; permissions: string[] }): Observable<Role> =>
    this.api.post('/admin/roles', body);
  update = (id: string, body: { name?: string; description?: string | null }): Observable<Role> => this.api.patch(`/admin/roles/${id}`, body);
  setPermissions = (id: string, permissions: string[]): Observable<Role> => this.api.put(`/admin/roles/${id}/permissions`, { permissions });
}

@Injectable({ providedIn: 'root' })
export class AuditApi {
  private readonly api = inject(ApiService);
  auditLogs = (q: AuditQuery): Observable<Page<AuditLog>> => this.api.get('/admin/audit-logs', { ...q });
  loginAudit = (q: PageQuery & { success?: boolean | null; user_id?: string | null }): Observable<Page<LoginAudit>> =>
    this.api.get('/admin/security/login-audit', { ...q });
  securityEvents = (q: PageQuery & { severity?: string | null; event_type?: string | null }): Observable<Page<SecurityEvent>> =>
    this.api.get('/admin/security/events', { ...q });
  sessions = (q: PageQuery & { user_id?: string | null; active_only?: boolean }): Observable<Page<SessionInfo>> =>
    this.api.get('/admin/security/sessions', { ...q });
  revokeSession = (id: string, reason: string): Observable<MessageResponse> =>
    this.api.post(`/admin/security/sessions/${id}/revoke`, { reason });
}
