# Roles and permissions

Source of truth: `backend/app/security/permissions.py`. `python manage.py seed-reference` syncs it to the
database (idempotent). System roles are read-only through the API. Platform Admins can create custom roles.

## How access is decided

A user's effective permissions are the union of their role grants. Each grant is either:

- **platform-wide**: `organization_id` NULL, allowed only for PLATFORM-scope roles; or
- **organization-scoped**: valid only for records belonging to that organization. The user must be a member.

Services call `principal.scope_for(permission)` and filter every query by the returned organizations.
Requests for records outside the caller's scope return 404.

Guards: nobody can grant a role carrying permissions they don't hold in that scope, change their own roles
or status, or remove or suspend the last active Platform Admin. Removing someone from an organization
revokes every role they hold in it.

## Phase 1 permissions

| Code | Meaning |
|---|---|
| users.read / users.manage / users.assign_roles | view users · create/edit/status/reset · grant & revoke roles |
| roles.read / roles.manage | view roles · create and edit custom roles |
| organizations.read / organizations.manage / organizations.manage_members | view · create/edit/status · members |
| audit.read | audit log and workflow events |
| security.read / security.manage | security events, sign-ins, sessions · revoke sessions, unlock accounts |

## System roles (spec §4)

| Code | Scope | Phase 1 permissions |
|---|---|---|
| PLATFORM_ADMIN | platform | all users/roles/organizations permissions, audit.read, security.read |
| SECURITY_ADMIN | platform | users.read, roles.read, organizations.read, audit.read, security.read, security.manage |
| SUPPORT | platform | users.read, organizations.read |
| METHODOLOGY_SPECIALIST | platform | (Phase 4) |
| FARMER, FIELD_AGENT, FIELD_SUPERVISOR, PROJECT_MANAGER, GIS_SPECIALIST, MRV_MANAGER, LAB_TECHNICIAN, LAB_MANAGER, CALCULATION_ANALYST, QA_OFFICER, VVB_REVIEWER, REGISTRY_MANAGER, CREDIT_MANAGER, BUYER, FINANCE_MANAGER | organization | added in their module's phase |

Platform Admin deliberately lacks `security.manage`, so it cannot grant Security Admin or unlock accounts.
That is separation of duties.
