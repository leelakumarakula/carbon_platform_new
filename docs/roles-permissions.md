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

## Phase 3 permissions

| Code | Meaning |
|---|---|
| projects.read | view projects of permitted organizations (farms, team, boundary, references, periods, carbon rights, documents, history) |
| projects.manage | create/edit projects; farms, team, standard/activity references, crediting period, baseline, carbon rights, documents; submit, confirm activity, re-open, close |
| projects.review | verify carbon-rights records; approve or return the eligibility review (never a project you submitted, never rights you recorded) |
| standards.manage | maintain the standard/route and activity catalog (platform-wide; reference data only) |

GIS review of a project boundary uses the existing `farms.review`. Farmers see only their own participation
(`GET /projects/my-participation`, via `farmers.self`). Buyers have no project access.

## Phase 4 permissions

| Code | Meaning |
|---|---|
| methodologies.read | view methodologies, versions, rules, documents, change history |
| methodologies.manage | create methodologies and draft versions, edit draft rules, submit, retire, withdraw |
| methodologies.approve | approve or return submitted versions (never one you submitted) |
| methodologies.review_project | run candidate evaluation for any project and record the specialist recommendation |

Methodology **confirmation and unlock** use `projects.manage` (project developer). The person who recommended a
candidate cannot confirm it. Labs, finance and buyers cannot change methodologies (tested).

## Phase 5 permissions

| Code | Meaning | Holders |
|---|---|---|
| mrv.read | view MRV plans, periods, strata, designs, points, records, evidence, datasets, QA, MRV history | MRV manager, project manager, field supervisor, GIS, platform GIS, methodology specialist, calculation analyst, QA, platform admin, support |
| mrv.manage | create/submit plans, periods and their actions, monitoring datasets | MRV manager, project manager |
| mrv.collect | record monitoring data and MRV evidence | MRV manager, field supervisor, field agent |
| mrv.review | run and complete QA reviews (never on a dataset you submitted) | MRV manager, QA officer |
| mrv.approve | approve MRV plans and datasets (never ones you submitted) | QA officer |
| sampling.manage | create strata and sampling designs, generate points | MRV manager, GIS specialist |
| sampling.assign | assign points to field collectors | MRV manager, field supervisor |
| sampling.collect | collect samples at **assigned** points only (field collection, photos, relocation requests) | field supervisor, field agent |
| sampling.review | approve strata, design versions, relocations; accept/return field records; skip points | field supervisor, GIS specialist |

Field collectors (field agents) only collect: they hold no review or approval permission, see only their own points
and cannot read the MRV workspace. Buyers, labs, VVB and finance have no MRV access; farmers keep only their
self-service pages. Separation of duties applies to every approval (plan, stratum, design, relocation, field record,
QA completion, dataset).

## Phase 6 permissions

| Code | Meaning | Holders |
|---|---|---|
| lab.read | project side: engagements, samples, shipments, approved results and lineage (never drafts) | MRV manager, project manager, field supervisor, QA officer, calculation analyst |
| lab.sample_register | register and seal samples (field agents: from their own SUBMITTED / ACCEPTED records only) | field agent, field supervisor, MRV manager |
| lab.sample_manage | correct / void samples before dispatch, project-side custody events | field supervisor, MRV manager |
| lab.shipment_manage | create, fill, dispatch, cancel shipments | field supervisor, MRV manager (never a field agent) |
| lab.engage | propose or end an engagement (project side) | project manager, MRV manager |
| lab.engagement_accept | accept or end an engagement (laboratory side) | lab manager |
| lab.lab_read | laboratory workspace: allow-listed views of samples shipped to the laboratory | lab technician, lab manager |
| lab.receive | receive / reject items, accession numbers, laboratory custody | lab technician, lab manager |
| lab.test | start tests, enter / submit / withdraw / correct results, attach PDF reports | lab technician, lab manager |
| lab.qa | laboratory QA decision (APPROVED / REJECTED / RETEST_REQUIRED) | lab manager |
| lab.retest_request | request a retest, with a reason | lab manager |

Laboratory users never see farmer, farm, GPS, sampling point, stratum, field-collection or MRV data, and project users never
see laboratory drafts. A LAB_MANAGER cannot approve a result they analysed or submitted, nor one whose sample they registered or
sealed, whose shipment they created or dispatched, or whose retest they requested (`SEPARATION_OF_DUTIES`). The proposer of an
engagement can never accept it. Buyers, VVB, finance and farmers have no Phase 6 access.

## Phase 7 permissions (decision A16)

| Code | Meaning | Holders |
|---|---|---|
| calculation.read | readiness, runs, frozen inputs, outputs, QA, lineage, comparisons (organization-scoped) | Calculation Analyst, QA Officer, MRV Manager, Project Manager |
| calculation.manage | create runs, freeze inputs, execute, submit, cancel, recalculate | Calculation Analyst |
| calculation.review | calculation QA (start / complete) | QA Officer |
| calculation.approve | approve / reject a run after QA PASS | QA Officer |

The reviewer and the approver are never the run's creator, freezer, executor or submitter (`SEPARATION_OF_DUTIES`); the same QA officer
may review and approve. Nobody can type a calculated value. Farmers, buyers, laboratory roles, finance and VVB/ACVA have no calculation
access in Phase 7. No new role was added.

## Phase 8A (decision B10) — no new permission or role

| Role | Permission | Phase 8A actions | Separation of duties |
|---|---|---|---|
| Calculation Analyst | calculation.read, calculation.manage | respond to findings, upload run evidence, generate reports, create / submit / withdraw readiness | never resolves a finding they answered; never approves readiness |
| QA Officer | calculation.read, calculation.review, calculation.approve | raise / return / resolve / reopen findings; withdraw own findings; approve / reject readiness | resolver ≠ responder; readiness approver ≠ submitter and ≠ the run's creator, freezer, executor, submitter |
| MRV Manager, Project Manager | calculation.read | read findings, reports, readiness, manifests | — |

VVB/ACVA, methodology specialists (platform-wide), farmers, buyers, laboratory roles and finance have no Phase 8A access.

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

| Code | Scope | Permissions (Phases 1–3) |
|---|---|---|
| PLATFORM_ADMIN | platform | all users/roles/organizations permissions, audit.read, security.read, consents.configure, farmers.read, farms.read, projects.read, standards.manage, methodologies.read |
| PLATFORM_GIS_SPECIALIST | platform | farmers.read, farms.read, farms.review_cross_org, projects.read (decision D5; not one of the 19 spec roles) |
| SECURITY_ADMIN | platform | users.read, roles.read, organizations.read, audit.read, security.read, security.manage |
| SUPPORT | platform | users.read, organizations.read, farmers.read, farms.read, projects.read, methodologies.read |
| METHODOLOGY_SPECIALIST | platform | projects.read, standards.manage, methodologies.read/manage/approve/review_project |
| FARMER | organization | farmers.self |
| FIELD_AGENT, FIELD_SUPERVISOR | organization | farmers.read, farmers.manage, farms.read, farms.manage, projects.read |
| PROJECT_MANAGER | organization | the above + farmers.kyc_verify, farmers.bank_manage, projects.manage, methodologies.read |
| GIS_SPECIALIST | organization | farmers.read, farms.read, farms.review, projects.read |
| MRV_MANAGER | organization | farmers.read, farms.read, projects.read, methodologies.read |
| QA_OFFICER | organization | farmers.read, farmers.kyc_verify, farms.read, projects.read, projects.review, methodologies.read |
| FINANCE_MANAGER | organization | farmers.read, farmers.bank_manage, farmers.bank_verify, projects.read |
| CALCULATION_ANALYST | organization | methodologies.read (calculation permissions in Phase 7) |
| LAB_TECHNICIAN, LAB_MANAGER, VVB_REVIEWER, REGISTRY_MANAGER, CREDIT_MANAGER, BUYER | organization | added in their module's phase (BUYER never gets farmer or project-private data) |

Platform Admin deliberately lacks `security.manage`, so it cannot grant Security Admin or unlock accounts.
That is separation of duties.
