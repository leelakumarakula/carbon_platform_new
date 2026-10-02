# Roles and permissions

Source of truth: `backend/app/security/permissions.py`. `python manage.py seed-reference` syncs it to the
database (idempotent). System roles are read-only through the API. Platform Admins can create custom roles.

## How access is decided

A user's effective permissions are the union of their role grants. Each grant is either:

- **platform-wide**: `organization_id` NULL, allowed only for PLATFORM-scope roles; or
- **organization-scoped**: valid only for records belonging to that organization. The user must be a member.

Services call `principal.scope_for(permission)` and filter every query by the returned organizations.
Requests for records outside the caller's scope return 404.

Guards: nobody can grant a role carrying **privileged** permissions (`users.*`, `roles.*`,
`organizations.*`, `audit.*`, `security.*` — `PRIVILEGED_CODES`) they don't hold in that scope, change their own roles
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

## Phase 2 permissions

| Code | Meaning |
|---|---|
| farmers.read / farmers.manage | view farmers · create, edit, status, contacts, consents, agreements, documents, link login |
| farmers.kyc_verify | approve or reject KYC (never your own submission) |
| farmers.bank_manage / farmers.bank_verify | add or deactivate bank accounts · verify them (never one you added) |
| farmers.self | farmer self-service: own profile, KYC submission, consents, bank accounts, farms — nothing else |
| farms.read / farms.manage | view farms · create, boundary, ownership, history, evidence, submit / withdraw / reopen |
| farms.review | GIS review: start review, verify or reject, resolve overlaps, review ownership, history and evidence |
| farms.review_cross_org | clear or confirm overlaps between farms of different organizations (platform-wide only) |
| consents.configure | publish versioned consent definitions; choose which are required for activation (privileged) |

## Permission-grant matrix (decision D4, approved)

Granting a role needs `users.assign_roles` in the scope of the grant, plus every *privileged* permission the role
carries (`PRIVILEGED_CODES`: `users.*`, `roles.*`, `organizations.*`, `audit.*`, `security.*`, `consents.*`).
Operational (business) permissions are delegated through `users.assign_roles`.

| Grantor | Operational org roles (Field Agent, Field Supervisor, GIS Specialist, MRV Manager, QA Officer, Project Manager, Finance Manager) | Platform operational roles (Support, Platform GIS Specialist, Methodology Specialist) | Platform Admin | Security Admin | Own roles |
|---|---|---|---|---|---|
| Platform Admin (platform-wide `users.assign_roles`) | ✅ any organization | ✅ | ✅ | ❌ lacks `security.manage` | ❌ |
| Org-scoped user admin (custom role with `users.assign_roles` in org X) | ✅ in org X only | ❌ needs a platform-wide grant | ❌ | ❌ | ❌ |
| Any role without `users.assign_roles` (Project Manager, Field Agent, GIS, QA, Farmer, Buyer, …) | ❌ | ❌ | ❌ | ❌ | ❌ |

Always enforced:
- nobody changes their own roles or status (`SELF_ROLE_CHANGE`);
- a role (system or custom) with a privileged permission the grantor lacks is refused (`ROLE_ESCALATION_BLOCKED`);
  the same check applies when creating or editing custom roles;
- platform roles cannot be scoped to an organization, and organization roles need membership (`ROLE_SCOPE_MISMATCH`,
  `USER_NOT_MEMBER`);
- the last active Platform Admin cannot be suspended or lose the role (`LAST_PLATFORM_ADMIN`).

Tests: `backend/tests/test_privilege_escalation.py` (matrix), `test_admin_users_api.py`, `test_multitenancy_api.py`.

**Record access** = organization-scoped permission **or** self-service: a user holding `farmers.self` and linked
to the farmer (`farmers.user_id`) can act on that farmer and their farms with read / manage / bank_manage
rights only. They cannot verify, review, suspend themselves, create agreements or link logins.

**Restricted documents** (KYC_ID, BANK_PROOF) can be read only by the farmer and by holders of
farmers.manage, farmers.kyc_verify, farmers.bank_manage or farmers.bank_verify. Others with farmers.read get
`RESTRICTED_DOCUMENT`. Identity numbers and bank account numbers are never returned, only the last 4 digits.

**Cross-organization overlaps (decision D5).** Flags between farms of different organizations hide the other farm's
details from organization-scoped users. An organization-scoped GIS Specialist may *confirm* the conflict on its own
farm but cannot *clear* it (`CROSS_ORG_OVERLAP`). Only the **Platform GIS Specialist** role (platform-wide
`farms.review_cross_org`) can clear it; it sees both farms and the decision is audited as
`FARM_CROSS_ORG_OVERLAP_RESOLVED` in both organizations' trails. The role cannot verify farms (no `farms.review`).

## System roles (spec §4)

| Code | Scope | Phase 1 permissions |
|---|---|---|
| PLATFORM_ADMIN | platform | all users/roles/organizations permissions, audit.read, security.read, consents.configure, farmers.read, farms.read |
| PLATFORM_GIS_SPECIALIST | platform | farmers.read, farms.read, farms.review_cross_org (decision D5; not one of the 19 spec roles) |
| SECURITY_ADMIN | platform | users.read, roles.read, organizations.read, audit.read, security.read, security.manage |
| SUPPORT | platform | users.read, organizations.read, farmers.read, farms.read |
| METHODOLOGY_SPECIALIST | platform | (Phase 4) |
| FARMER | organization | farmers.self |
| FIELD_AGENT, FIELD_SUPERVISOR | organization | farmers.read, farmers.manage, farms.read, farms.manage |
| PROJECT_MANAGER | organization | the above + farmers.kyc_verify, farmers.bank_manage |
| GIS_SPECIALIST | organization | farmers.read, farms.read, farms.review |
| MRV_MANAGER | organization | farmers.read, farms.read |
| QA_OFFICER | organization | farmers.read, farmers.kyc_verify, farms.read |
| FINANCE_MANAGER | organization | farmers.read, farmers.bank_manage, farmers.bank_verify |
| LAB_TECHNICIAN, LAB_MANAGER, CALCULATION_ANALYST, VVB_REVIEWER, REGISTRY_MANAGER, CREDIT_MANAGER, BUYER | organization | added in their module's phase (BUYER never gets farmer data) |

Platform Admin deliberately lacks `security.manage`, so it cannot grant Security Admin or unlock accounts.
That is separation of duties.
