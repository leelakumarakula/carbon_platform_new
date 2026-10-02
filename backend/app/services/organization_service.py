"""Organizations (multi-tenancy, spec section 31) and their members."""
import uuid

from sqlalchemy.orm import Session

from app.audit.service import AuditAction, record, record_transition, snapshot
from app.core.context import RequestContext
from app.core.errors import Conflict, NotFound, PermissionDenied
from app.models import Organization, OrganizationUser, UserRole
from app.models.base import Environment
from app.repositories import identity as repo
from app.schemas.common import PageParams
from app.schemas.identity import MemberAdd, OrganizationCreate, OrganizationUpdate
from app.security.permissions import P
from app.security.principal import Principal
from app.services.workflows import ORGANIZATION_MACHINE

ORG_FIELDS = ("code", "name", "org_type", "country", "registration_number", "contact_email", "status", "environment")


def get_visible(db: Session, principal: Principal, org_id: uuid.UUID, code: str = P.ORGANIZATIONS_READ) -> Organization:
    org = repo.get_organization(db, org_id)
    if org is None or not principal.can_in_org(code, org.id):
        raise NotFound("Organization not found.", error_code="ORGANIZATION_NOT_FOUND")
    return org


def list_orgs(db: Session, principal: Principal, params: PageParams, **filters: object) -> tuple[list[Organization], int]:
    return repo.list_organizations(db, params, scope=principal.scope_for(P.ORGANIZATIONS_READ), **filters)  # type: ignore[arg-type]


def create(db: Session, ctx: RequestContext, principal: Principal, data: OrganizationCreate,
           environment: str = Environment.LIVE.value) -> Organization:
    if not principal.has_platform(P.ORGANIZATIONS_MANAGE):
        raise PermissionDenied(details={"required_permission": P.ORGANIZATIONS_MANAGE})
    if repo.get_organization_by_code(db, data.code):
        raise Conflict("An organization with this code already exists.", error_code="ORGANIZATION_CODE_EXISTS")
    if data.org_type == "PLATFORM":
        raise Conflict("The platform organization is created by the reference seed only.", error_code="PLATFORM_ORG_RESERVED")
    org = Organization(**data.model_dump(), environment=environment)
    db.add(org)
    db.flush()
    record(db, ctx, AuditAction.ORGANIZATION_CREATED, "organization", org.id, None, snapshot(org, ORG_FIELDS),
           organization_id=org.id)
    db.commit()
    return org


def update(db: Session, ctx: RequestContext, principal: Principal, org_id: uuid.UUID,
           data: OrganizationUpdate) -> Organization:
    org = get_visible(db, principal, org_id)
    principal.require_in_org(P.ORGANIZATIONS_MANAGE, org.id)
    changes = data.model_dump(exclude_unset=True)
    old = {k: getattr(org, k) for k in changes}
    for k, v in changes.items():
        setattr(org, k, v)
    if old != changes:
        record(db, ctx, AuditAction.ORGANIZATION_UPDATED, "organization", org.id, old, changes, organization_id=org.id)
    db.commit()
    return org


def change_status(db: Session, ctx: RequestContext, principal: Principal, org_id: uuid.UUID,
                  status: str, reason: str) -> Organization:
    org = get_visible(db, principal, org_id)
    if not principal.has_platform(P.ORGANIZATIONS_MANAGE):
        raise PermissionDenied(details={"required_permission": P.ORGANIZATIONS_MANAGE})
    if org.org_type == "PLATFORM":
        raise Conflict("The platform organization cannot change status.", error_code="PLATFORM_ORG_RESERVED")
    record_transition(db, ctx, ORGANIZATION_MACHINE, org.id, org.status, status,
                      AuditAction.ORGANIZATION_STATUS_CHANGED, reason, org.id)
    org.status = status
    db.commit()
    return org


def list_members(db: Session, principal: Principal, org_id: uuid.UUID) -> list[OrganizationUser]:
    get_visible(db, principal, org_id)
    return repo.list_members(db, org_id)


def add_member(db: Session, ctx: RequestContext, principal: Principal, org_id: uuid.UUID,
               data: MemberAdd) -> OrganizationUser:
    org = get_visible(db, principal, org_id)
    principal.require_in_org(P.ORGANIZATIONS_MANAGE_MEMBERS, org.id)
    if org.status != "ACTIVE":
        raise Conflict("Members can only be added to active organizations.", error_code="ORGANIZATION_INACTIVE")
    user = repo.get_user(db, data.user_id)
    if user is None:
        raise NotFound("User not found.", error_code="USER_NOT_FOUND")
    if user.environment != org.environment:
        raise Conflict("Demo and live records cannot be mixed.", error_code="ENVIRONMENT_MISMATCH")
    if repo.get_membership(db, org.id, user.id):
        raise Conflict("The user is already a member of this organization.", error_code="ALREADY_MEMBER")
    m = OrganizationUser(organization_id=org.id, user_id=user.id, title=data.title, is_primary=data.is_primary)
    db.add(m)
    db.flush()
    record(db, ctx, AuditAction.MEMBER_ADDED, "organization", org.id, None,
           {"user_id": user.id, "title": data.title}, organization_id=org.id)
    db.commit()
    return m


def remove_member(db: Session, ctx: RequestContext, principal: Principal, org_id: uuid.UUID,
                  user_id: uuid.UUID, reason: str) -> None:
    org = get_visible(db, principal, org_id)
    principal.require_in_org(P.ORGANIZATIONS_MANAGE_MEMBERS, org.id)
    m = repo.get_membership(db, org.id, user_id)
    if m is None:
        raise NotFound("Membership not found.", error_code="MEMBERSHIP_NOT_FOUND")
    if user_id == principal.user_id:
        raise Conflict("You cannot remove yourself from an organization.", error_code="SELF_MEMBERSHIP_CHANGE")
    # Leaving an organization ends every role held inside it.
    grants = db.query(UserRole).filter(UserRole.user_id == user_id, UserRole.organization_id == org.id).all()
    for g in grants:
        record(db, ctx, AuditAction.ROLE_REVOKED, "user", user_id,
               {"role_id": g.role_id, "organization_id": org.id, "user_role_id": g.id}, None,
               "membership removed", organization_id=org.id)
        db.delete(g)
    record(db, ctx, AuditAction.MEMBER_REMOVED, "organization", org.id, {"user_id": user_id}, None, reason,
           organization_id=org.id)
    db.delete(m)
    db.commit()
