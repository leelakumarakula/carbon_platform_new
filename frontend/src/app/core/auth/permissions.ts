/** Permission codes — must match backend app/security/permissions.py (class P). */
export const P = {
  USERS_READ: 'users.read',
  USERS_MANAGE: 'users.manage',
  USERS_ASSIGN_ROLES: 'users.assign_roles',
  ROLES_READ: 'roles.read',
  ROLES_MANAGE: 'roles.manage',
  ORGANIZATIONS_READ: 'organizations.read',
  ORGANIZATIONS_MANAGE: 'organizations.manage',
  ORGANIZATIONS_MANAGE_MEMBERS: 'organizations.manage_members',
  AUDIT_READ: 'audit.read',
  SECURITY_READ: 'security.read',
  SECURITY_MANAGE: 'security.manage',
} as const;

export type PermissionCode = (typeof P)[keyof typeof P];
