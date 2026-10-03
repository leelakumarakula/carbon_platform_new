"""Permission catalog and system roles (spec section 4).

This module is the single source of truth for permissions and for the baseline
permissions of the system roles (the 19 roles of spec section 4 plus Platform GIS Specialist, decision D5). `python -m app.seed.reference` syncs it to the
database. Each later phase adds its module's permissions here and grants them to roles.
Custom (non-system) roles are managed by Platform Admins through the API.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionDef:
    code: str
    module: str
    name: str
    description: str


class P:
    """Permission codes (use these constants in route dependencies, never raw strings)."""
    USERS_READ = "users.read"
    USERS_MANAGE = "users.manage"
    USERS_ASSIGN_ROLES = "users.assign_roles"
    ROLES_READ = "roles.read"
    ROLES_MANAGE = "roles.manage"
    ORGANIZATIONS_READ = "organizations.read"
    ORGANIZATIONS_MANAGE = "organizations.manage"
    ORGANIZATIONS_MANAGE_MEMBERS = "organizations.manage_members"
    AUDIT_READ = "audit.read"
    SECURITY_READ = "security.read"
    SECURITY_MANAGE = "security.manage"
    # Phase 2 — farmer & farm
    FARMERS_READ = "farmers.read"
    FARMERS_MANAGE = "farmers.manage"
    FARMERS_KYC_VERIFY = "farmers.kyc_verify"
    FARMERS_BANK_MANAGE = "farmers.bank_manage"
    FARMERS_BANK_VERIFY = "farmers.bank_verify"
    FARMERS_SELF = "farmers.self"
    FARMS_READ = "farms.read"
    FARMS_MANAGE = "farms.manage"
    FARMS_REVIEW = "farms.review"
    FARMS_REVIEW_CROSS_ORG = "farms.review_cross_org"
    CONSENTS_CONFIGURE = "consents.configure"
    # Phase 3 — projects, standard/activity catalog
    PROJECTS_READ = "projects.read"
    PROJECTS_MANAGE = "projects.manage"
    PROJECTS_REVIEW = "projects.review"
    STANDARDS_MANAGE = "standards.manage"
    # Phase 4 — methodologies
    METHODOLOGIES_READ = "methodologies.read"
    METHODOLOGIES_MANAGE = "methodologies.manage"
    METHODOLOGIES_APPROVE = "methodologies.approve"
    METHODOLOGIES_REVIEW_PROJECT = "methodologies.review_project"
    # Phase 5 — MRV and sampling
    MRV_READ = "mrv.read"
    MRV_MANAGE = "mrv.manage"
    MRV_COLLECT = "mrv.collect"
    MRV_REVIEW = "mrv.review"
    MRV_APPROVE = "mrv.approve"
    SAMPLING_MANAGE = "sampling.manage"
    SAMPLING_ASSIGN = "sampling.assign"
    SAMPLING_COLLECT = "sampling.collect"
    SAMPLING_REVIEW = "sampling.review"
    # Phase 6 — laboratory & sample analysis
    LAB_READ = "lab.read"                          # project side: samples, custody, shipments, non-draft results, lineage
    LAB_SAMPLE_REGISTER = "lab.sample_register"    # register + seal samples (field agents: own collections only)
    LAB_SAMPLE_MANAGE = "lab.sample_manage"        # correct / void samples, project-side custody exceptions and transfers
    LAB_SHIPMENT_MANAGE = "lab.shipment_manage"    # create shipments, add / remove samples, dispatch, cancel
    LAB_ENGAGE = "lab.engage"                      # propose / end project ↔ laboratory engagements (project side)
    LAB_ENGAGEMENT_ACCEPT = "lab.engagement_accept"  # accept / end engagements (laboratory side)
    LAB_LAB_READ = "lab.lab_read"                  # laboratory side: restricted, allow-listed views only
    LAB_RECEIVE = "lab.receive"                    # receive / reject samples, accession numbers, lab-side custody
    LAB_TEST = "lab.test"                          # start tests, enter / submit results, attach reports
    LAB_QA = "lab.qa"                              # laboratory QA decisions (never on your own work)
    LAB_RETEST_REQUEST = "lab.retest_request"      # request a retest (with a reason)
    # Phase 7 — carbon calculation (decision A16: exactly these four)
    CALCULATION_READ = "calculation.read"          # readiness, runs, inputs, outputs, QA, lineage, compare
    CALCULATION_MANAGE = "calculation.manage"      # create, freeze inputs, execute, submit, cancel, recalculate
    CALCULATION_REVIEW = "calculation.review"      # calculation QA (never on a run you created / froze / executed / submitted)
    CALCULATION_APPROVE = "calculation.approve"    # approve / reject a calculation run (same separation of duties)


PERMISSIONS: tuple[PermissionDef, ...] = (
    PermissionDef(P.USERS_READ, "admin", "View users", "List and view user accounts."),
    PermissionDef(P.USERS_MANAGE, "admin", "Manage users", "Create users, edit profiles, change status, reset passwords."),
    PermissionDef(P.USERS_ASSIGN_ROLES, "admin", "Assign roles", "Grant and revoke roles. Cannot grant more than the assigner holds."),
    PermissionDef(P.ROLES_READ, "admin", "View roles", "View roles and their permissions."),
    PermissionDef(P.ROLES_MANAGE, "admin", "Manage roles", "Create custom roles and edit their permissions."),
    PermissionDef(P.ORGANIZATIONS_READ, "admin", "View organizations", "List and view organizations and members."),
    PermissionDef(P.ORGANIZATIONS_MANAGE, "admin", "Manage organizations", "Create and edit organizations, change status."),
    PermissionDef(P.ORGANIZATIONS_MANAGE_MEMBERS, "admin", "Manage members", "Add and remove organization members."),
    PermissionDef(P.AUDIT_READ, "audit", "View audit logs", "Read the append-only audit trail and workflow events."),
    PermissionDef(P.SECURITY_READ, "security", "View security events", "Read security events, login audit and sessions."),
    PermissionDef(P.SECURITY_MANAGE, "security", "Manage security", "Revoke sessions, unlock accounts, manage access policies."),
    PermissionDef(P.FARMERS_READ, "farmers", "View farmers", "View farmer profiles, consents and agreements (KYC and bank data always masked)."),
    PermissionDef(P.FARMERS_MANAGE, "farmers", "Manage farmers", "Register farmers; maintain contacts, consents, agreements and documents; submit KYC."),
    PermissionDef(P.FARMERS_KYC_VERIFY, "farmers", "Verify KYC", "Verify or return a farmer's KYC submission. Cannot verify a submission you made."),
    PermissionDef(P.FARMERS_BANK_MANAGE, "farmers", "Manage bank details", "Add or deactivate farmer bank accounts (numbers stored encrypted, shown masked)."),
    PermissionDef(P.FARMERS_BANK_VERIFY, "farmers", "Verify bank details", "Verify or reject a farmer bank account."),
    PermissionDef(P.FARMERS_SELF, "farmers", "Farmer self-service", "A farmer manages their own profile, consents, farms and history — never others'."),
    PermissionDef(P.FARMS_READ, "farms", "View farms", "View farms, boundaries, ownership, history, evidence and overlap flags."),
    PermissionDef(P.FARMS_MANAGE, "farms", "Manage farms", "Create farms; record boundaries, ownership, history and evidence; submit for review."),
    PermissionDef(P.FARMS_REVIEW, "farms", "Review farms (GIS)", "Start GIS review, resolve overlap flags, verify or reject farms and ownership."),
    PermissionDef(P.FARMS_REVIEW_CROSS_ORG, "farms", "Review cross-organization overlaps",
                  "Clear or confirm boundary overlaps between farms of different organizations (platform-wide grant only)."),
    PermissionDef(P.PROJECTS_READ, "projects", "View projects",
                  "View projects of permitted organizations: farms, team, boundary, standard/activity, periods, carbon-rights references."),
    PermissionDef(P.PROJECTS_MANAGE, "projects", "Manage projects",
                  "Create projects; add/remove farms, team, standard/activity references, crediting period, baseline metadata, "
                  "carbon-rights references, documents; submit for eligibility review."),
    PermissionDef(P.PROJECTS_REVIEW, "projects", "Review project eligibility",
                  "Verify carbon-rights references and approve or return a project's eligibility review (never one you submitted)."),
    PermissionDef(P.STANDARDS_MANAGE, "standards", "Manage standards & activities",
                  "Maintain the standard/route and activity catalog and their links (reference data; no methodology rules)."),
    PermissionDef(P.METHODOLOGIES_READ, "methodologies", "View methodologies",
                  "View methodologies, versions, rules, documents and change history."),
    PermissionDef(P.METHODOLOGIES_MANAGE, "methodologies", "Manage methodologies",
                  "Create methodologies and draft versions; edit draft rules; submit versions for approval; supersede/retire."),
    PermissionDef(P.METHODOLOGIES_APPROVE, "methodologies", "Approve methodology versions",
                  "Approve or return a submitted methodology version (never one you submitted). Drafts never become active by themselves."),
    PermissionDef(P.METHODOLOGIES_REVIEW_PROJECT, "methodologies", "Review project methodology candidates",
                  "Run the candidate rules engine for a project and record the specialist recommendation for a candidate."),
    PermissionDef(P.MRV_READ, "mrv", "View MRV", "View MRV plans, monitoring periods, strata, sampling, field records, data, datasets and QA."),
    PermissionDef(P.MRV_MANAGE, "mrv", "Manage MRV", "Create MRV plans and versions, monitoring periods and datasets; submit them."),
    PermissionDef(P.MRV_COLLECT, "mrv", "Record monitoring data", "Record monitoring (activity) data and MRV evidence."),
    PermissionDef(P.MRV_REVIEW, "mrv", "Review MRV datasets", "Run MRV QA reviews (automated checks + result)."),
    PermissionDef(P.MRV_APPROVE, "mrv", "Approve MRV", "Approve or return MRV plans; approve or reject MRV datasets (never your own submission)."),
    PermissionDef(P.SAMPLING_MANAGE, "sampling", "Manage stratification & sampling",
                  "Create strata and sampling designs; generate sampling points from an approved design."),
    PermissionDef(P.SAMPLING_ASSIGN, "sampling", "Assign sampling points", "Assign sampling points to field collectors."),
    PermissionDef(P.SAMPLING_COLLECT, "sampling", "Collect samples (field)",
                  "Field collection on sampling points assigned to you; request point relocations."),
    PermissionDef(P.SAMPLING_REVIEW, "sampling", "Review sampling",
                  "Approve strata and sampling design versions; accept/return field collections; decide relocations (never your own)."),
    PermissionDef(P.LAB_READ, "lab", "View laboratory work (project)",
                  "View the project's samples, custody, shipments, submitted/approved laboratory results and their full lineage."),
    PermissionDef(P.LAB_SAMPLE_REGISTER, "lab", "Register & seal samples",
                  "Register a physical sample (SMP code) from a submitted/accepted field collection and seal it (field agents: own collections)."),
    PermissionDef(P.LAB_SAMPLE_MANAGE, "lab", "Manage samples", "Correct or void samples before dispatch; record project-side custody events."),
    PermissionDef(P.LAB_SHIPMENT_MANAGE, "lab", "Manage shipments", "Create laboratory shipments, add or remove sealed samples, dispatch or cancel."),
    PermissionDef(P.LAB_ENGAGE, "lab", "Engage laboratories", "Propose or end the project's engagement with a laboratory organization."),
    PermissionDef(P.LAB_ENGAGEMENT_ACCEPT, "lab", "Accept engagements (laboratory)",
                  "Accept or end an engagement proposed to your laboratory (never one you proposed)."),
    PermissionDef(P.LAB_LAB_READ, "lab", "Laboratory workspace",
                  "Laboratory-facing views only: sample codes, physical details, requested parameters, shipments and lab documents."),
    PermissionDef(P.LAB_RECEIVE, "lab", "Receive samples", "Receive or reject shipped samples, record condition, accession numbers and lab custody."),
    PermissionDef(P.LAB_TEST, "lab", "Perform tests", "Start requested tests, enter and submit results, attach PDF reports."),
    PermissionDef(P.LAB_QA, "lab", "Laboratory QA", "Approve, reject or require a retest of a laboratory result (never your own work)."),
    PermissionDef(P.LAB_RETEST_REQUEST, "lab", "Request retests", "Request a retest of a laboratory result, with a reason."),
    PermissionDef(P.CALCULATION_READ, "calculation", "View calculations",
                  "View calculation readiness, runs, frozen inputs, outputs, QA, lineage and comparisons of the organization's projects."),
    PermissionDef(P.CALCULATION_MANAGE, "calculation", "Manage calculation runs",
                  "Create calculation runs, freeze inputs, execute the registered methodology module, submit, cancel, recalculate."),
    PermissionDef(P.CALCULATION_REVIEW, "calculation", "Calculation QA", "Run and complete calculation QA (never on your own run)."),
    PermissionDef(P.CALCULATION_APPROVE, "calculation", "Approve calculations",
                  "Approve or reject a calculation run after QA PASS (never your own run). Calculated is not verified or issued."),
    PermissionDef(P.CONSENTS_CONFIGURE, "admin", "Configure consent types",
                  "Publish versioned consent definitions and choose which are required for farmer activation."),
)

ALL_PERMISSION_CODES = frozenset(p.code for p in PERMISSIONS)

# Escalation guard scope: nobody may grant (or put into a role) a *privileged* permission they do not hold
# themselves in that scope. Business-module permissions (farmers, farms, …) are delegated through
# users.assign_roles so a Platform Admin can staff organizations without holding every business permission.
PRIVILEGED_MODULES = frozenset({"admin", "audit", "security"})
PRIVILEGED_CODES = frozenset(p.code for p in PERMISSIONS if p.module in PRIVILEGED_MODULES)


@dataclass(frozen=True)
class RoleDef:
    code: str
    name: str
    scope: str  # PLATFORM | ORGANIZATION
    description: str
    permissions: frozenset[str]


def _r(code: str, name: str, scope: str, description: str, *perms: str) -> RoleDef:
    return RoleDef(code, name, scope, description, frozenset(perms))


PLATFORM, ORG = "PLATFORM", "ORGANIZATION"

SYSTEM_ROLES: tuple[RoleDef, ...] = (
    _r("FARMER", "Farmer", ORG, "Maintains profile, KYC, farms and history; views participation, sampling, credits and payouts.",
       P.FARMERS_SELF),
    _r("FIELD_AGENT", "Field Collector / Field Agent", ORG, "Performs assigned field visits, sampling, evidence capture and chain of custody.",
       P.FARMERS_READ, P.FARMERS_MANAGE, P.FARMS_READ, P.FARMS_MANAGE, P.PROJECTS_READ, P.MRV_COLLECT, P.SAMPLING_COLLECT,
       P.LAB_SAMPLE_REGISTER),
    _r("FIELD_SUPERVISOR", "Field Supervisor", ORG, "Assigns collectors and sampling points; reviews field submissions.",
       P.FARMERS_READ, P.FARMERS_MANAGE, P.FARMS_READ, P.FARMS_MANAGE, P.PROJECTS_READ, P.MRV_READ, P.MRV_COLLECT,
       P.SAMPLING_ASSIGN, P.SAMPLING_COLLECT, P.SAMPLING_REVIEW, P.LAB_READ, P.LAB_SAMPLE_REGISTER, P.LAB_SAMPLE_MANAGE,
       P.LAB_SHIPMENT_MANAGE),
    _r("PROJECT_MANAGER", "Project Manager / Project Developer", ORG, "Creates projects, selects standard/activity/methodology, manages MRV, VVB and registry workflows.",
       P.FARMERS_READ, P.FARMERS_MANAGE, P.FARMERS_KYC_VERIFY, P.FARMERS_BANK_MANAGE, P.FARMS_READ, P.FARMS_MANAGE,
       P.PROJECTS_READ, P.PROJECTS_MANAGE, P.METHODOLOGIES_READ, P.MRV_READ, P.MRV_MANAGE, P.LAB_READ, P.LAB_ENGAGE, P.CALCULATION_READ),
    _r("METHODOLOGY_SPECIALIST", "Methodology Specialist", PLATFORM, "Manages versioned, approval-controlled methodology configuration.",
       P.PROJECTS_READ, P.STANDARDS_MANAGE, P.METHODOLOGIES_READ, P.METHODOLOGIES_MANAGE, P.METHODOLOGIES_APPROVE,
       P.METHODOLOGIES_REVIEW_PROJECT, P.MRV_READ),
    _r("GIS_SPECIALIST", "GIS / Remote Sensing Specialist", ORG, "Reviews polygons, overlaps, strata, sampling points and satellite observations.",
       P.FARMERS_READ, P.FARMS_READ, P.FARMS_REVIEW, P.PROJECTS_READ, P.MRV_READ, P.SAMPLING_MANAGE, P.SAMPLING_REVIEW),
    _r("PLATFORM_GIS_SPECIALIST", "Platform GIS Specialist", PLATFORM,
       "Platform-wide GIS reviewer: resolves boundary overlaps between farms of different organizations.",
       P.FARMERS_READ, P.FARMS_READ, P.FARMS_REVIEW_CROSS_ORG, P.PROJECTS_READ, P.MRV_READ),
    _r("MRV_MANAGER", "MRV Manager", ORG, "Manages MRV plans, monitoring periods and approves monitoring datasets.",
       P.FARMERS_READ, P.FARMS_READ, P.PROJECTS_READ, P.METHODOLOGIES_READ, P.MRV_READ, P.MRV_MANAGE, P.MRV_COLLECT, P.MRV_REVIEW,
       P.SAMPLING_MANAGE, P.SAMPLING_ASSIGN, P.LAB_READ, P.LAB_SAMPLE_REGISTER, P.LAB_SAMPLE_MANAGE, P.LAB_SHIPMENT_MANAGE, P.LAB_ENGAGE,
       P.CALCULATION_READ),
    _r("LAB_TECHNICIAN", "Lab Technician", ORG, "Receives samples, enters results and uploads lab reports.",
       P.LAB_LAB_READ, P.LAB_RECEIVE, P.LAB_TEST),
    _r("LAB_MANAGER", "Lab Manager / Lab QA", ORG, "Approves or rejects lab results and requests retests.",
       P.LAB_LAB_READ, P.LAB_RECEIVE, P.LAB_TEST, P.LAB_QA, P.LAB_RETEST_REQUEST, P.LAB_ENGAGEMENT_ACCEPT),
    _r("CALCULATION_ANALYST", "Carbon Calculation Analyst", ORG, "Runs approved calculation engines; cannot type a final credit quantity.",
       P.METHODOLOGIES_READ, P.MRV_READ, P.LAB_READ, P.CALCULATION_READ, P.CALCULATION_MANAGE),
    _r("QA_OFFICER", "Data Quality / QA Officer", ORG, "Reviews anomalies and duplicates; approves or rejects datasets.",
       P.FARMERS_READ, P.FARMERS_KYC_VERIFY, P.FARMS_READ, P.PROJECTS_READ, P.PROJECTS_REVIEW, P.METHODOLOGIES_READ, P.MRV_READ,
       P.MRV_REVIEW, P.MRV_APPROVE, P.LAB_READ, P.CALCULATION_READ, P.CALCULATION_REVIEW, P.CALCULATION_APPROVE),
    _r("VVB_REVIEWER", "VVB / ACVA Reviewer", ORG, "External verifier: reviews assigned projects, raises findings, submits decisions."),
    _r("REGISTRY_MANAGER", "Registry Manager", ORG, "Manages registry submissions, issuance tracking and serial reconciliation."),
    _r("CREDIT_MANAGER", "Credit Manager", ORG, "Manages issued-credit inventory, reservations, transfers and retirements."),
    _r("BUYER", "Buyer", ORG, "Browses eligible issued credits, orders, pays, requests transfer/retirement."),
    _r("FINANCE_MANAGER", "Finance / Payout Manager", ORG, "Reconciles payments, calculates farmer share per agreement, approves payouts.",
       P.FARMERS_READ, P.FARMERS_BANK_MANAGE, P.FARMERS_BANK_VERIFY, P.PROJECTS_READ),
    _r("PLATFORM_ADMIN", "Platform Admin", PLATFORM, "Manages users, roles, organizations, master data and configuration; views audit logs.",
       P.USERS_READ, P.USERS_MANAGE, P.USERS_ASSIGN_ROLES, P.ROLES_READ, P.ROLES_MANAGE,
       P.ORGANIZATIONS_READ, P.ORGANIZATIONS_MANAGE, P.ORGANIZATIONS_MANAGE_MEMBERS, P.AUDIT_READ, P.SECURITY_READ,
       P.CONSENTS_CONFIGURE, P.FARMERS_READ, P.FARMS_READ, P.PROJECTS_READ, P.STANDARDS_MANAGE, P.METHODOLOGIES_READ, P.MRV_READ),
    _r("SECURITY_ADMIN", "Security Admin", PLATFORM,
       "Manages access policies, MFA, integration secrets, security events and access reviews.",
       P.USERS_READ, P.ROLES_READ, P.ORGANIZATIONS_READ, P.AUDIT_READ, P.SECURITY_READ, P.SECURITY_MANAGE),
    _r("SUPPORT", "Support / Operations", PLATFORM, "Assists farmers and field agents; limited read access.",
       P.USERS_READ, P.ORGANIZATIONS_READ, P.FARMERS_READ, P.FARMS_READ, P.PROJECTS_READ, P.METHODOLOGIES_READ, P.MRV_READ),
)

SYSTEM_ROLE_CODES = frozenset(r.code for r in SYSTEM_ROLES)

assert all(p in ALL_PERMISSION_CODES for r in SYSTEM_ROLES for p in r.permissions), "unknown permission in role"
